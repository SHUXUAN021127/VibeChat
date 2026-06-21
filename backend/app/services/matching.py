import math
import json
import secrets
import random
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models import EmotionRecord, Match, User

# 等待匹配超时时间（秒）
MATCH_TIMEOUT = 30

# 情绪相似度阈值（高于此值才能匹配）
SIMILARITY_THRESHOLD = 0.4

ANIMAL_NAMES = [
    "迷路的猫", "沉默的鱼", "发呆的熊", "夜行的狐", "漂泊的鸟",
    "思考的狼", "做梦的兔", "流浪的云", "寻光的萤", "等风的树",
    "听海的贝", "追月的鹿", "藏雨的伞", "数星的羊", "散步的象",
]

AVATARS = ["🐱", "🐟", "🐻", "🦊", "🐦", "🐺", "🐰", "☁️", "🌟", "🌙",
           "🐚", "🦌", "☂️", "🐑", "🐘", "🌊", "🍃", "🎐", "🌸", "🪐"]

def generate_anonymous_identity():
    name = random.choice(ANIMAL_NAMES) + str(random.randint(10, 99))
    avatar = random.choice(AVATARS)
    return name, avatar

def _parse_secondary(record):
    """解析次要情绪 JSON"""
    import json
    try:
        data = json.loads(record.secondary_emotions or "[]")
        return {item["label"]: float(item.get("weight", 0)) for item in data if "label" in item}
    except Exception:
        return {}

def emotion_similarity(record_a: EmotionRecord, record_b: EmotionRecord) -> float:
    """
    计算两个情绪记录的相似度（0~1）
    主情绪为主，次要情绪做微调
    """
    # 1. 主情绪标签相同加权
    label_score = 1.0 if record_a.emotion_label == record_b.emotion_label else 0.0

    # 2. 情绪强度相似度（差值越小越相似）
    score_diff = abs(record_a.emotion_score - record_b.emotion_score)
    intensity_score = 1.0 - score_diff

    # 3. 正负向相似度
    valence_diff = abs(record_a.emotion_valence - record_b.emotion_valence) / 2.0
    valence_score = 1.0 - valence_diff

    # 4. 次要情绪重叠度（微调项）：两人共享的次要情绪越多越相似
    sec_a = _parse_secondary(record_a)
    sec_b = _parse_secondary(record_b)
    # 主情绪也纳入对方次要情绪的考量（你的主情绪是对方的次要情绪也算共鸣）
    sec_a[record_a.emotion_label] = 1.0
    sec_b[record_b.emotion_label] = 1.0
    shared = set(sec_a.keys()) & set(sec_b.keys())
    if shared:
        overlap_score = sum(min(sec_a[k], sec_b[k]) for k in shared) / max(len(sec_a), len(sec_b))
    else:
        overlap_score = 0.0

    # 加权综合：主情绪 0.4 + 强度 0.2 + 正负向 0.15 + 次要情绪重叠 0.25
    similarity = (
        label_score * 0.4 +
        intensity_score * 0.2 +
        valence_score * 0.15 +
        overlap_score * 0.25
    )
    return similarity

def emotion_complement(record_a: EmotionRecord, record_b: EmotionRecord) -> float:
    """
    计算两个情绪记录的"互补度"（0~1）
    互补 = 正负向相反，但强度相近（如焦虑的人配上平静的人）
    用于"互补情绪"匹配模式：让需要被安抚的人遇到能提供平静的人
    """
    # 1. 正负向相反程度（一正一负得分高）
    # valence 范围 -1~1，相反时差值接近 2
    valence_diff = abs(record_a.emotion_valence - record_b.emotion_valence) / 2.0
    opposite_score = valence_diff  # 差值越大越互补

    # 2. 强度相近（都比较投入对话，体验更好）
    score_diff = abs(record_a.emotion_score - record_b.emotion_score)
    intensity_score = 1.0 - score_diff

    # 加权：主要看正负向相反
    complement = opposite_score * 0.7 + intensity_score * 0.3
    return complement

def match_score(record_a: EmotionRecord, record_b: EmotionRecord, mode: str = "similar") -> float:
    """根据匹配模式返回匹配分数"""
    if mode == "complementary":
        return emotion_complement(record_a, record_b)
    return emotion_similarity(record_a, record_b)

from app.config import settings
from app.services.pending import pending_pool, presence

class MatchResult:
    """匹配结果，区分三种情况"""
    def __init__(self, kind: str, match: Match = None, pair=None):
        self.kind = kind        # "matched" 直接进房 / "pending" 待确认 / "waiting" 等待
        self.match = match      # 直接进房或等待时的房间
        self.pair = pair        # 待确认时的 PendingPair

async def find_or_create_match(
    emotion_record: EmotionRecord,
    db: AsyncSession
) -> MatchResult:
    """
    核心匹配逻辑：
    - similar 模式：找到即直接进房（沿用旧逻辑）
    - complementary 模式：找到互补对象后，创建"待确认配对"，需双方同意
    - 找不到：创建等待房间
    """
    mode = settings.MATCH_MODE  # similar 或 complementary

    timeout_threshold = datetime.utcnow() - timedelta(seconds=MATCH_TIMEOUT)
    result = await db.execute(
        select(Match).where(
            and_(
                Match.status == "waiting",
                Match.created_at >= timeout_threshold
            )
        ).order_by(Match.created_at.asc())
    )
    waiting_matches = result.scalars().all()

    best_match = None
    best_score = 0.0
    best_record = None

    for waiting_match in waiting_matches:
        part_result = await db.execute(
            select(EmotionRecord).where(
                and_(
                    EmotionRecord.match_id == waiting_match.id,
                    EmotionRecord.user_id != emotion_record.user_id
                )
            )
        )
        existing_records = part_result.scalars().all()
        if not existing_records:
            continue

        # 只和当前在线的用户匹配（避免幽灵房间）
        existing_records = [
            r for r in existing_records if presence.is_online(r.user_id)
        ]
        if not existing_records:
            continue

        # 互补模式下，跳过之前已经拒绝过的对象
        if mode == "complementary":
            filtered = [
                r for r in existing_records
                if not pending_pool.is_rejected_before(emotion_record.user_id, r.user_id)
            ]
            if not filtered:
                continue
            existing_records = filtered

        avg_sim = sum(
            match_score(emotion_record, r, mode) for r in existing_records
        ) / len(existing_records)

        if avg_sim > best_score:
            best_score = avg_sim
            best_match = waiting_match
            best_record = existing_records[0]

    if best_match and best_score >= SIMILARITY_THRESHOLD:
        if mode == "complementary":
            # 互补模式：不直接进房，创建待确认配对
            pair = pending_pool.create_pair(
                user_a=best_record.user_id,
                user_b=emotion_record.user_id,
                record_a=best_record.id,
                record_b=emotion_record.id,
                emotion_a={
                    "emotion_label": best_record.emotion_label,
                    "emotion_color": best_record.emotion_color,
                    "emotion_summary": best_record.emotion_summary,
                },
                emotion_b={
                    "emotion_label": emotion_record.emotion_label,
                    "emotion_color": emotion_record.emotion_color,
                    "emotion_summary": emotion_record.emotion_summary,
                },
            )
            # 记下双方所属的等待房间，确认失败后好回到队列
            pair.match_a_id = best_match.id
            pair.match_b_id = emotion_record.match_id
            return MatchResult("pending", pair=pair)
        else:
            # 相似模式：直接进房
            emotion_record.match_id = best_match.id
            best_match.status = "active"
            await db.commit()
            await db.refresh(best_match)
            return MatchResult("matched", match=best_match)

    # 没有合适匹配，创建新等待房间
    room_code = secrets.token_urlsafe(8)
    new_match = Match(
        room_code=room_code,
        status="waiting",
        emotion_label=emotion_record.emotion_label,
        emotion_color=emotion_record.emotion_color,
    )
    db.add(new_match)
    await db.flush()
    emotion_record.match_id = new_match.id
    await db.commit()
    await db.refresh(new_match)
    return MatchResult("waiting", match=new_match)


async def confirm_and_create_room(pair, db: AsyncSession) -> Match:
    """双方都同意后，把两个等待用户合并进一个新的活跃房间"""
    from app.models import EmotionRecord as ER
    # 创建新房间
    new_match = Match(
        room_code=pair.room_code,
        status="active",
        emotion_label=pair.emotion_b.get("emotion_label", "互补"),
        emotion_color=pair.emotion_b.get("emotion_color", "#a78bfa"),
    )
    db.add(new_match)
    await db.flush()
    # 把两个人的情绪记录都挂到新房间
    for rid in (pair.record_a, pair.record_b):
        rec = await db.execute(select(ER).where(ER.id == rid))
        rec = rec.scalar_one_or_none()
        if rec:
            rec.match_id = new_match.id
    await db.commit()
    await db.refresh(new_match)
    return new_match


async def activate_solo_match(match_id: int, db: AsyncSession) -> Match:
    """超时后将等待房间转为 AI 陪聊房间（兜底，单人也能完整体验）"""
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if match and match.status == "waiting":
        match.status = "active"
        match.is_ai_companion = True  # 标记为 AI 陪聊
        await db.commit()
        await db.refresh(match)
    return match


# 情绪标签 → 公共房间分组（把相近情绪归到同一个大类房间）
EMOTION_GROUPS = {
    "焦虑": "焦虑", "迷茫": "焦虑", "压力": "焦虑", "紧张": "焦虑", "烦躁": "焦虑",
    "快乐": "快乐", "兴奋": "快乐", "开心": "快乐", "愉悦": "快乐", "期待": "快乐",
    "悲伤": "低落", "孤独": "低落", "失落": "低落", "空虚": "低落", "难过": "低落",
    "平静": "平静", "释然": "平静", "放松": "平静", "安宁": "平静",
    "愤怒": "愤怒", "生气": "愤怒",
}

GROUP_COLORS = {
    "焦虑": "#a78bfa", "快乐": "#fbbf24", "低落": "#60a5fa",
    "平静": "#6ee7b7", "愤怒": "#f87171", "其他": "#94a3b8",
}

def group_of(emotion_label: str) -> str:
    return EMOTION_GROUPS.get(emotion_label, "其他")

async def find_or_create_group_room(emotion_record: EmotionRecord, db: AsyncSession) -> Match:
    """
    多人模式：把用户归入按情绪大类划分的公共房间。
    同一情绪大类的人都进同一个活跃房间，没有就创建。
    """
    group = group_of(emotion_record.emotion_label)
    group_room_code = f"group-{group}"

    result = await db.execute(select(Match).where(Match.room_code == group_room_code))
    room = result.scalar_one_or_none()

    if room:
        # 房间存在，复用；若已结束则重新激活
        room.status = "active"
        room.last_activity = datetime.utcnow()
    else:
        room = Match(
            room_code=group_room_code,
            status="active",
            room_type="group",
            emotion_label=f"{group}房",
            emotion_color=GROUP_COLORS.get(group, "#94a3b8"),
            last_activity=datetime.utcnow(),
        )
        db.add(room)
        await db.flush()

    emotion_record.match_id = room.id
    await db.commit()
    await db.refresh(room)
    return room


async def cleanup_stale_rooms(db: AsyncSession):
    """
    后台清理：
    1. 把超过 MATCH_TIMEOUT 仍在 waiting 的房间标记为 ended
    2. 把闲置超过 2 分钟的 active 1对1 房间标记为 ended
    多人房间（group）不自动清理，保持长期开放。
    """
    now = datetime.utcnow()
    # 清理超时的等待房间
    stale_waiting = now - timedelta(seconds=MATCH_TIMEOUT + 5)
    result = await db.execute(
        select(Match).where(
            and_(Match.status == "waiting", Match.created_at < stale_waiting)
        )
    )
    for room in result.scalars().all():
        room.status = "ended"
        room.ended_at = now

    # 清理闲置的 1对1 活跃房间（2 分钟无活动）
    idle_threshold = now - timedelta(seconds=120)
    result2 = await db.execute(
        select(Match).where(
            and_(
                Match.status == "active",
                Match.room_type == "one_on_one",
                Match.last_activity < idle_threshold,
            )
        )
    )
    for room in result2.scalars().all():
        room.status = "ended"
        room.ended_at = now

    await db.commit()


async def touch_room(room_code: str, db: AsyncSession):
    """有人发消息时更新房间活跃时间"""
    result = await db.execute(select(Match).where(Match.room_code == room_code))
    room = result.scalar_one_or_none()
    if room:
        room.last_activity = datetime.utcnow()
        await db.commit()
