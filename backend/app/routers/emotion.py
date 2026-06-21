from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import get_db, EmotionRecord
from app.services.llm import analyze_emotion
from app.services.auth import get_or_create_user
from app.services.matching import find_or_create_match, find_or_create_group_room
import json

router = APIRouter(prefix="/api/emotion", tags=["emotion"])

class AnalyzeRequest(BaseModel):
    text: str
    session_token: str | None = None
    chat_mode: str = "one_on_one"   # one_on_one / group
    account_token: str | None = None  # 登录用户的 JWT（游客为空）

class AnalyzeResponse(BaseModel):
    session_token: str
    user_id: int
    anonymous_name: str
    anonymous_avatar: str
    emotion_label: str
    emotion_score: float
    emotion_valence: float
    emotion_keywords: list[str]
    emotion_color: str
    emotion_summary: str
    opening_line: str
    is_crisis: bool
    match_room_code: str
    match_status: str   # waiting / active / pending
    emotion_record_id: int
    pair_id: str | None = None   # 互补模式待确认时返回

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    if not req.text or len(req.text.strip()) < 2:
        raise HTTPException(status_code=400, detail="请输入更多内容")
    if len(req.text) > 500:
        raise HTTPException(status_code=400, detail="输入不能超过500字")

    # 1. 获取或创建用户
    user, token = await get_or_create_user(req.session_token, db)

    # 标记在线（让本用户立即可被匹配）
    from app.services.pending import presence
    presence.heartbeat(user.id)

    # 解析登录账号（游客为 None）
    account_id = None
    if req.account_token:
        from app.services.account import get_account_from_token
        account = await get_account_from_token(req.account_token, db)
        if account:
            account_id = account.id

    # 2. LLM 情绪分析
    try:
        emotion = await analyze_emotion(req.text)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI 服务暂时不可用，请稍后再试：{str(e)}")

    # 3. 保存情绪记录
    record = EmotionRecord(
        user_id=user.id,
        account_id=account_id,
        input_text=req.text,
        emotion_label=emotion["emotion_label"],
        emotion_score=float(emotion["emotion_score"]),
        emotion_valence=float(emotion["emotion_valence"]),
        emotion_keywords=json.dumps(emotion["emotion_keywords"], ensure_ascii=False),
        emotion_color=emotion["emotion_color"],
        emotion_summary=emotion["emotion_summary"],
    )
    db.add(record)
    await db.flush()

    # 4. 情绪匹配
    if req.chat_mode == "group":
        # 多人模式：进入按情绪划分的公共房间
        room = await find_or_create_group_room(record, db)
        await db.refresh(record)
        return AnalyzeResponse(
            session_token=token,
            user_id=user.id,
            anonymous_name=user.anonymous_name,
            anonymous_avatar=user.anonymous_avatar,
            emotion_label=emotion["emotion_label"],
            emotion_score=emotion["emotion_score"],
            emotion_valence=emotion["emotion_valence"],
            emotion_keywords=emotion["emotion_keywords"],
            emotion_color=emotion["emotion_color"],
            emotion_summary=emotion["emotion_summary"],
            opening_line=emotion.get("opening_line", ""),
            is_crisis=emotion.get("is_crisis", False),
            match_room_code=room.room_code,
            match_status="active",   # 多人房直接进
            emotion_record_id=record.id,
            pair_id=None,
        )

    # 1对1 模式
    match_result = await find_or_create_match(record, db)
    await db.refresh(record)

    # 根据匹配结果决定返回
    if match_result.kind == "pending":
        # 互补模式：进入待确认状态
        room_code = ""
        match_status = "pending"
        pair_id = match_result.pair.pair_id
    else:
        # matched 或 waiting：直接给房间码
        room_code = match_result.match.room_code
        match_status = match_result.match.status
        pair_id = None

    return AnalyzeResponse(
        session_token=token,
        user_id=user.id,
        anonymous_name=user.anonymous_name,
        anonymous_avatar=user.anonymous_avatar,
        emotion_label=emotion["emotion_label"],
        emotion_score=emotion["emotion_score"],
        emotion_valence=emotion["emotion_valence"],
        emotion_keywords=emotion["emotion_keywords"],
        emotion_color=emotion["emotion_color"],
        emotion_summary=emotion["emotion_summary"],
        opening_line=emotion.get("opening_line", ""),
        is_crisis=emotion.get("is_crisis", False),
        match_room_code=room_code,
        match_status=match_status,
        emotion_record_id=record.id,
        pair_id=pair_id,
    )


# ===== 重新匹配（复用已有情绪记录，不重新调用 LLM）=====

class RematchRequest(BaseModel):
    emotion_record_id: int
    session_token: str


@router.post("/rematch", response_model=AnalyzeResponse)
async def rematch(req: RematchRequest, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.services.pending import presence

    user, token = await get_or_create_user(req.session_token, db)
    presence.heartbeat(user.id)

    # 取出原情绪记录
    old = await db.execute(select(EmotionRecord).where(EmotionRecord.id == req.emotion_record_id))
    old = old.scalar_one_or_none()
    if not old:
        raise HTTPException(status_code=404, detail="找不到原情绪记录")

    # 复制一份新的情绪记录（用于新一轮匹配）
    record = EmotionRecord(
        user_id=user.id,
        input_text=old.input_text,
        emotion_label=old.emotion_label,
        emotion_score=old.emotion_score,
        emotion_valence=old.emotion_valence,
        emotion_keywords=old.emotion_keywords,
        emotion_color=old.emotion_color,
        emotion_summary=old.emotion_summary,
    )
    db.add(record)
    await db.flush()

    match_result = await find_or_create_match(record, db)
    await db.refresh(record)

    if match_result.kind == "pending":
        room_code = ""
        match_status = "pending"
        pair_id = match_result.pair.pair_id
    else:
        room_code = match_result.match.room_code
        match_status = match_result.match.status
        pair_id = None

    import json as _json
    return AnalyzeResponse(
        session_token=token,
        user_id=user.id,
        anonymous_name=user.anonymous_name,
        anonymous_avatar=user.anonymous_avatar,
        emotion_label=old.emotion_label,
        emotion_score=old.emotion_score,
        emotion_valence=old.emotion_valence,
        emotion_keywords=_json.loads(old.emotion_keywords) if old.emotion_keywords else [],
        emotion_color=old.emotion_color,
        emotion_summary=old.emotion_summary,
        opening_line="",
        is_crisis=False,
        match_room_code=room_code,
        match_status=match_status,
        emotion_record_id=record.id,
        pair_id=pair_id,
    )
