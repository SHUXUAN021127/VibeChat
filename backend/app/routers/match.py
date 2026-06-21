from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import get_db, Match, EmotionRecord, Message
from app.services.matching import activate_solo_match, confirm_and_create_room
from app.services.pending import pending_pool
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/match", tags=["match"])

MATCH_TIMEOUT = 30  # 秒

class MatchStatusResponse(BaseModel):
    room_code: str
    status: str
    emotion_label: str
    emotion_color: str
    participant_count: int
    timed_out: bool

class MessageItem(BaseModel):
    id: int
    anonymous_name: str
    anonymous_avatar: str
    content: str
    created_at: str
    is_self: bool

class RoomInfoResponse(BaseModel):
    room_code: str
    status: str
    room_type: str
    emotion_label: str
    emotion_color: str
    participant_count: int
    messages: list[MessageItem]
    opening_line: str

@router.get("/status/{room_code}")
async def get_match_status(
    room_code: str,
    user_id: int,
    db: AsyncSession = Depends(get_db)
) -> MatchStatusResponse:
    # 心跳：标记该用户在线（用于避免幽灵房间匹配）
    from app.services.pending import presence
    presence.heartbeat(user_id)

    result = await db.execute(select(Match).where(Match.room_code == room_code))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="房间不存在")

    # 统计参与人数
    part_result = await db.execute(
        select(EmotionRecord).where(EmotionRecord.match_id == match.id)
    )
    participants = part_result.scalars().all()

    # 检查是否超时
    timed_out = False
    if match.status == "waiting":
        elapsed = (datetime.utcnow() - match.created_at).total_seconds()
        if elapsed >= MATCH_TIMEOUT:
            match = await activate_solo_match(match.id, db)
            timed_out = True

    return MatchStatusResponse(
        room_code=match.room_code,
        status=match.status,
        emotion_label=match.emotion_label,
        emotion_color=match.emotion_color,
        participant_count=len(participants),
        timed_out=timed_out,
    )

@router.get("/room/{room_code}")
async def get_room_info(
    room_code: str,
    user_id: int,
    db: AsyncSession = Depends(get_db)
) -> RoomInfoResponse:
    result = await db.execute(select(Match).where(Match.room_code == room_code))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="房间不存在")

    # 消息列表
    msg_result = await db.execute(
        select(Message).where(Message.match_id == match.id).order_by(Message.created_at.asc())
    )
    messages = msg_result.scalars().all()

    # 获取破冰语（来自第一个参与者的情绪记录）
    part_result = await db.execute(
        select(EmotionRecord).where(EmotionRecord.match_id == match.id).order_by(EmotionRecord.id.asc()).limit(1)
    )
    first_record = part_result.scalar_one_or_none()

    participant_result = await db.execute(
        select(EmotionRecord).where(EmotionRecord.match_id == match.id)
    )
    participant_count = len(participant_result.scalars().all())

    return RoomInfoResponse(
        room_code=match.room_code,
        status=match.status,
        room_type=match.room_type,
        emotion_label=match.emotion_label,
        emotion_color=match.emotion_color,
        participant_count=participant_count,
        messages=[
            MessageItem(
                id=m.id,
                anonymous_name=m.anonymous_name,
                anonymous_avatar=m.anonymous_avatar,
                content=m.content,
                created_at=m.created_at.isoformat(),
                is_self=(m.user_id == user_id),
            )
            for m in messages
        ],
        opening_line=first_record.emotion_summary if first_record else "",
    )


# ===== 互补模式：双向确认 =====

class ConfirmStatusResponse(BaseModel):
    state: str            # waiting_choice / confirmed / rejected / not_found
    other_emotion_label: str = ""
    other_emotion_color: str = ""
    other_emotion_summary: str = ""
    room_code: str = ""   # confirmed 时返回新房间；rejected 时返回原等待房间
    my_choice: bool | None = None
    seconds_left: int = 0

class ConfirmChoiceRequest(BaseModel):
    pair_id: str
    user_id: int
    agree: bool


@router.get("/confirm/status/{pair_id}")
async def confirm_status(
    pair_id: str,
    user_id: int,
    db: AsyncSession = Depends(get_db)
) -> ConfirmStatusResponse:
    """轮询互补确认状态"""
    pair = pending_pool.get_pair(pair_id)
    if not pair:
        return ConfirmStatusResponse(state="not_found")

    # 检查超时
    pending_pool.check_timeout(pair)

    # 给对方看的情绪信息（看对面那个人的情绪）
    if user_id == pair.user_a:
        other = pair.emotion_b
    else:
        other = pair.emotion_a

    seconds_left = max(0, 10 - int(__import__("time").time() - pair.created_at))

    if pair.resolved:
        if pair.success:
            # 双方同意 → 确保房间已创建
            existing = await db.execute(select(Match).where(Match.room_code == pair.room_code))
            if not existing.scalar_one_or_none():
                await confirm_and_create_room(pair, db)
            pending_pool.cleanup(pair_id)
            return ConfirmStatusResponse(
                state="confirmed",
                room_code=pair.room_code,
                other_emotion_label=other.get("emotion_label", ""),
                other_emotion_color=other.get("emotion_color", ""),
            )
        else:
            pending_pool.cleanup(pair_id)
            # 返回该用户原来的等待房间，让他继续等
            my_match_id = pair.match_a_id if user_id == pair.user_a else pair.match_b_id
            orig_room = ""
            if my_match_id:
                m = await db.execute(select(Match).where(Match.id == my_match_id))
                m = m.scalar_one_or_none()
                if m:
                    orig_room = m.room_code
            return ConfirmStatusResponse(state="rejected", room_code=orig_room)

    return ConfirmStatusResponse(
        state="waiting_choice",
        other_emotion_label=other.get("emotion_label", ""),
        other_emotion_color=other.get("emotion_color", ""),
        other_emotion_summary=other.get("emotion_summary", ""),
        my_choice=pair.choice.get(user_id),
        seconds_left=seconds_left,
    )


@router.post("/confirm/choice")
async def confirm_choice(req: ConfirmChoiceRequest) -> ConfirmStatusResponse:
    """提交同意/拒绝"""
    pair = pending_pool.get_pair(req.pair_id)
    if not pair:
        return ConfirmStatusResponse(state="not_found")
    pending_pool.set_choice(req.pair_id, req.user_id, req.agree)
    if pair.resolved and pair.success:
        return ConfirmStatusResponse(state="confirmed", room_code=pair.room_code)
    if pair.resolved and not pair.success:
        return ConfirmStatusResponse(state="rejected")
    return ConfirmStatusResponse(state="waiting_choice", my_choice=req.agree)
