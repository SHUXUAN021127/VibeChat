from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import get_db, Match, Message, User
import json
from datetime import datetime
from typing import Dict, Set

router = APIRouter(tags=["chat"])

# 房间连接池: room_code -> set of websockets
class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, room_code: str):
        await ws.accept()
        if room_code not in self.rooms:
            self.rooms[room_code] = set()
        self.rooms[room_code].add(ws)

    def disconnect(self, ws: WebSocket, room_code: str):
        if room_code in self.rooms:
            self.rooms[room_code].discard(ws)

    async def broadcast(self, room_code: str, data: dict, exclude: WebSocket = None):
        if room_code not in self.rooms:
            return
        dead = set()
        for ws in self.rooms[room_code]:
            if ws == exclude:
                continue
            try:
                await ws.send_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.rooms[room_code].discard(ws)

    async def send_personal(self, ws: WebSocket, data: dict):
        await ws.send_text(json.dumps(data, ensure_ascii=False))

manager = ConnectionManager()

@router.websocket("/ws/chat/{room_code}")
async def chat_ws(
    websocket: WebSocket,
    room_code: str,
    user_id: int,
    session_token: str,
):
    # 独立获取 db session（WebSocket 不走 Depends）
    from app.models import AsyncSessionLocal
    db = AsyncSessionLocal()

    try:
        # 验证用户
        user_result = await db.execute(select(User).where(
            User.id == user_id,
            User.session_token == session_token
        ))
        user = user_result.scalar_one_or_none()
        if not user:
            await websocket.close(code=1008)
            return

        # 验证房间
        match_result = await db.execute(select(Match).where(Match.room_code == room_code))
        match = match_result.scalar_one_or_none()
        if not match:
            await websocket.close(code=1008)
            return

        await manager.connect(websocket, room_code)
        websocket.violation_count = 0  # 本房间内的违规次数

        # 通知其他人有人进入
        await manager.broadcast(room_code, {
            "type": "system",
            "content": f"{user.anonymous_avatar} {user.anonymous_name} 进入了对话",
            "timestamp": datetime.utcnow().isoformat(),
        }, exclude=websocket)

        # 发送欢迎消息给自己
        await manager.send_personal(websocket, {
            "type": "system",
            "content": f"你以「{user.anonymous_name}」的身份进入了对话",
            "timestamp": datetime.utcnow().isoformat(),
        })

        # AI 陪聊房间：若还没有消息，AI 主动打招呼
        if match.is_ai_companion:
            existing = await db.execute(
                select(Message).where(Message.match_id == match.id).limit(1)
            )
            if not existing.scalar_one_or_none():
                import asyncio
                asyncio.create_task(_ai_companion_greet(match.id, room_code, match.emotion_label))

        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("type") == "typing":
                # 转发"正在输入"状态给房间其他人（不入库）
                await manager.broadcast(room_code, {
                    "type": "typing",
                    "anonymous_name": user.anonymous_name,
                    "anonymous_avatar": user.anonymous_avatar,
                }, exclude=websocket)
                continue

            if data.get("type") == "leave_room":
                # 主动退出：1对1 房间解散，通知对方
                if match.room_type == "one_on_one":
                    match.status = "ended"
                    match.ended_at = datetime.utcnow()
                    await db.commit()
                    await manager.broadcast(room_code, {
                        "type": "room_dismissed",
                        "reason": "peer_left",
                        "content": f"{user.anonymous_avatar} {user.anonymous_name} 退出了聊天",
                    }, exclude=websocket)
                else:
                    # 多人房：只是离开，不解散
                    await manager.broadcast(room_code, {
                        "type": "system",
                        "content": f"{user.anonymous_avatar} {user.anonymous_name} 离开了房间",
                        "timestamp": datetime.utcnow().isoformat(),
                    }, exclude=websocket)
                await websocket.close()
                break

            if data.get("type") == "message":
                content = data.get("content", "").strip()
                if not content or len(content) > 1000:
                    continue

                # ===== 内容审核 =====
                from app.services.moderation import moderate
                is_violation, reason = await moderate(content)
                if is_violation:
                    websocket.violation_count += 1
                    remaining = 3 - websocket.violation_count

                    if websocket.violation_count >= 3:
                        # 第3次：踢出房间
                        await manager.send_personal(websocket, {
                            "type": "kicked",
                            "content": "因多次发送不当内容，你已被移出此对话。",
                        })
                        # 1对1：解散房间并让对方收到重新匹配询问
                        if match.room_type == "one_on_one":
                            match.status = "ended"
                            match.ended_at = datetime.utcnow()
                            await db.commit()
                            await manager.broadcast(room_code, {
                                "type": "room_dismissed",
                                "reason": "peer_kicked",
                                "content": "对方因不当言论被移出了对话",
                            }, exclude=websocket)
                        else:
                            # 多人房：只通知，不解散
                            await manager.broadcast(room_code, {
                                "type": "system",
                                "content": f"{user.anonymous_avatar} {user.anonymous_name} 因不当言论被移出对话",
                                "timestamp": datetime.utcnow().isoformat(),
                            }, exclude=websocket)
                        await websocket.close()
                        break
                    else:
                        # 第1、2次：警告，消息不发送
                        await manager.send_personal(websocket, {
                            "type": "warning",
                            "content": f"消息包含不当内容（{reason}），请文明发言。再违规 {remaining} 次将被移出对话。",
                            "violation_count": websocket.violation_count,
                        })
                        continue

                # 保存消息到数据库
                msg = Message(
                    match_id=match.id,
                    user_id=user.id,
                    anonymous_name=user.anonymous_name,
                    anonymous_avatar=user.anonymous_avatar,
                    content=content,
                )
                db.add(msg)
                await db.commit()
                await db.refresh(msg)

                # 更新房间活跃时间（用于闲置判断）
                from app.services.matching import touch_room
                await touch_room(room_code, db)

                payload = {
                    "type": "message",
                    "id": msg.id,
                    "anonymous_name": user.anonymous_name,
                    "anonymous_avatar": user.anonymous_avatar,
                    "content": content,
                    "timestamp": msg.created_at.isoformat(),
                    "is_self": False,
                }

                # 广播给其他人
                await manager.broadcast(room_code, payload, exclude=websocket)

                # 回传给自己（标记 is_self）
                payload["is_self"] = True
                await manager.send_personal(websocket, payload)

                # ===== AI 陪聊：如果是 AI 陪聊房间，生成回复 =====
                if match.is_ai_companion:
                    import asyncio
                    asyncio.create_task(_ai_companion_respond(
                        match.id, room_code, match.emotion_label, websocket
                    ))

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_code)
        # 1对1 房间：意外断开也视为退出，解散房间并通知对方
        if match.room_type == "one_on_one" and match.status == "active":
            try:
                match.status = "ended"
                match.ended_at = datetime.utcnow()
                await db.commit()
            except Exception:
                pass
            await manager.broadcast(room_code, {
                "type": "room_dismissed",
                "reason": "peer_left",
                "content": f"{user.anonymous_avatar} {user.anonymous_name} 退出了聊天",
            })
        else:
            await manager.broadcast(room_code, {
                "type": "system",
                "content": f"{user.anonymous_avatar} {user.anonymous_name} 离开了对话",
                "timestamp": datetime.utcnow().isoformat(),
            })
    except Exception as e:
        manager.disconnect(websocket, room_code)
    finally:
        await db.close()


# ===== AI 陪聊回复 =====
import random as _random

# AI 陪聊的固定匿名身份（每个房间一个，存内存）
_ai_identities: dict[str, dict] = {}

def _get_ai_identity(room_code: str) -> dict:
    if room_code not in _ai_identities:
        from app.services.matching import ANIMAL_NAMES, AVATARS
        _ai_identities[room_code] = {
            "name": _random.choice(ANIMAL_NAMES) + str(_random.randint(10, 99)),
            "avatar": _random.choice(AVATARS),
        }
    return _ai_identities[room_code]


async def _ai_companion_respond(match_id: int, room_code: str, emotion_label: str, user_ws):
    """生成 AI 陪聊回复并发送"""
    import asyncio
    from app.models import AsyncSessionLocal
    from app.services.companion import companion_reply
    from sqlalchemy import select as _select

    # 模拟真人打字延迟
    await asyncio.sleep(_random.uniform(1.2, 2.5))

    identity = _get_ai_identity(room_code)

    db = AsyncSessionLocal()
    try:
        # 取最近的对话历史（最多20条）
        msg_res = await db.execute(
            _select(Message).where(Message.match_id == match_id).order_by(Message.created_at.desc()).limit(20)
        )
        recent = list(reversed(msg_res.scalars().all()))

        # 转成 LLM 对话格式：AI 自己发的算 assistant，其他人算 user
        history = []
        for m in recent:
            role = "assistant" if m.anonymous_name == identity["name"] else "user"
            history.append({"role": role, "content": m.content})

        if not history or history[-1]["role"] != "user":
            return

        # 发送"正在输入"
        await manager.broadcast(room_code, {
            "type": "typing",
            "anonymous_name": identity["name"],
            "anonymous_avatar": identity["avatar"],
        })

        reply = await companion_reply(emotion_label, history)

        # 保存 AI 回复（用匿名身份，user_id 用 -1 标记为虚拟）
        msg = Message(
            match_id=match_id,
            user_id=-1,
            anonymous_name=identity["name"],
            anonymous_avatar=identity["avatar"],
            content=reply,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)

        payload = {
            "type": "message",
            "id": msg.id,
            "anonymous_name": identity["name"],
            "anonymous_avatar": identity["avatar"],
            "content": reply,
            "timestamp": msg.created_at.isoformat(),
            "is_self": False,
        }
        await manager.broadcast(room_code, payload)
    except Exception:
        pass
    finally:
        await db.close()


async def _ai_companion_greet(match_id: int, room_code: str, emotion_label: str):
    """AI 陪聊房间的主动开场问候"""
    import asyncio
    from app.models import AsyncSessionLocal
    from app.services.companion import companion_reply

    await asyncio.sleep(_random.uniform(1.5, 2.5))
    identity = _get_ai_identity(room_code)

    db = AsyncSessionLocal()
    try:
        # 用一个引导让 AI 先开口
        history = [{"role": "user", "content": "（对方刚进入聊天，请你自然地先打个招呼开启对话）"}]
        reply = await companion_reply(emotion_label, history)

        msg = Message(
            match_id=match_id, user_id=-1,
            anonymous_name=identity["name"], anonymous_avatar=identity["avatar"],
            content=reply,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)

        await manager.broadcast(room_code, {
            "type": "message",
            "id": msg.id,
            "anonymous_name": identity["name"],
            "anonymous_avatar": identity["avatar"],
            "content": reply,
            "timestamp": msg.created_at.isoformat(),
            "is_self": False,
        })
    except Exception:
        pass
    finally:
        await db.close()
