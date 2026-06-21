from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import re
import json
import secrets

from app.models import get_db, Account, EmotionRecord, Message, Match
from app.services import account as acc
from app.config import settings

router = APIRouter(prefix="/api/account", tags=["account"])


# ===== 请求/响应模型 =====
class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    token: str
    account_id: int
    email: str | None
    display_name: str | None
    provider: str


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


# ===== 邮箱注册 =====
@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if not _is_valid_email(req.email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")

    existing = await acc.get_account_by_email(req.email, db)
    if existing:
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    account = await acc.create_email_account(req.email, req.password, db)
    token = acc.create_jwt(account.id)
    return AuthResponse(
        token=token, account_id=account.id, email=account.email,
        display_name=account.display_name, provider="email",
    )


# ===== 邮箱登录 =====
@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    account = await acc.get_account_by_email(req.email, db)
    if not account or not account.password_hash:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not acc.verify_password(req.password, account.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = acc.create_jwt(account.id)
    return AuthResponse(
        token=token, account_id=account.id, email=account.email,
        display_name=account.display_name, provider=account.provider,
    )


# ===== 当前账号信息 =====
@router.get("/me")
async def me(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ", 1)[1]
    account = await acc.get_account_from_token(token, db)
    if not account:
        raise HTTPException(status_code=401, detail="登录已过期")
    return {
        "account_id": account.id, "email": account.email,
        "display_name": account.display_name, "provider": account.provider,
    }


# ===== Google OAuth =====
@router.get("/google/login")
async def google_login():
    """重定向到 Google 授权页"""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google 登录未配置")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Google 回调：用 code 换 token，拿用户信息，创建/登录账号"""
    import httpx
    async with httpx.AsyncClient() as client:
        # 1. code 换 access_token
        token_res = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Google 授权失败")

        # 2. 拿用户信息
        userinfo_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        info = userinfo_res.json()

    google_id = info.get("id")
    email = info.get("email")
    name = info.get("name", "Google用户")

    account = await acc.get_account_by_provider("google", google_id, db)
    if not account:
        account = Account(
            email=email, provider="google", provider_id=google_id, display_name=name,
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)

    jwt_token = acc.create_jwt(account.id)
    # 重定向回前端，把 token 带在 URL（前端接收后存起来）
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}")


# ===== 微信登录（接口骨架，演示环境未接入真实服务）=====
@router.get("/wechat/login")
async def wechat_login():
    if not settings.WECHAT_APP_ID:
        raise HTTPException(
            status_code=503,
            detail="微信登录需要微信开放平台企业认证，演示环境暂未接入。接口已预留。",
        )
    # 真实实现：重定向到微信扫码授权页
    # https://open.weixin.qq.com/connect/qrconnect?appid=...&redirect_uri=...&scope=snsapi_login
    raise HTTPException(status_code=501, detail="微信登录接口骨架")


# ===== 手机号登录（接口骨架，需短信服务商）=====
class PhoneRequest(BaseModel):
    phone: str
    code: str | None = None

@router.post("/phone/send_code")
async def phone_send_code(req: PhoneRequest):
    # 真实实现：调用阿里云/腾讯云短信发送验证码
    raise HTTPException(
        status_code=503,
        detail="手机号登录需要短信服务商，演示环境暂未接入。接口已预留。",
    )

@router.post("/phone/verify")
async def phone_verify(req: PhoneRequest):
    raise HTTPException(status_code=501, detail="手机号登录接口骨架")


# ===== 历史记录：情绪卡片 =====
@router.get("/history/emotions")
async def history_emotions(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    account = await _require_account(authorization, db)
    result = await db.execute(
        select(EmotionRecord)
        .where(EmotionRecord.account_id == account.id)
        .order_by(desc(EmotionRecord.created_at))
        .limit(100)
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "input_text": r.input_text,
            "emotion_label": r.emotion_label,
            "emotion_score": r.emotion_score,
            "emotion_valence": r.emotion_valence,
            "emotion_color": r.emotion_color,
            "emotion_summary": r.emotion_summary,
            "emotion_keywords": json.loads(r.emotion_keywords) if r.emotion_keywords else [],
            "created_at": r.created_at.isoformat(),
            "match_id": r.match_id,
        }
        for r in records
    ]


# ===== 历史记录：聊天会话列表 =====
@router.get("/history/sessions")
async def history_sessions(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    account = await _require_account(authorization, db)
    # 找出该账号参与过的所有房间
    rec_result = await db.execute(
        select(EmotionRecord).where(EmotionRecord.account_id == account.id)
    )
    records = rec_result.scalars().all()
    match_ids = list({r.match_id for r in records if r.match_id})

    sessions = []
    for mid in match_ids:
        m_res = await db.execute(select(Match).where(Match.id == mid))
        match = m_res.scalar_one_or_none()
        if not match:
            continue
        # 消息数量
        msg_res = await db.execute(select(Message).where(Message.match_id == mid))
        msgs = msg_res.scalars().all()
        if not msgs:
            continue
        sessions.append({
            "match_id": mid,
            "room_code": match.room_code,
            "emotion_label": match.emotion_label,
            "emotion_color": match.emotion_color,
            "room_type": match.room_type,
            "message_count": len(msgs),
            "created_at": match.created_at.isoformat(),
        })
    sessions.sort(key=lambda s: s["created_at"], reverse=True)
    return sessions


# ===== 历史记录：单个会话的消息 =====
@router.get("/history/session/{match_id}")
async def history_session_messages(match_id: int, authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    account = await _require_account(authorization, db)
    # 校验该账号确实参与过这个房间
    own = await db.execute(
        select(EmotionRecord).where(
            EmotionRecord.account_id == account.id,
            EmotionRecord.match_id == match_id,
        )
    )
    if not own.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="无权查看此会话")

    msg_res = await db.execute(
        select(Message).where(Message.match_id == match_id).order_by(Message.created_at.asc())
    )
    messages = msg_res.scalars().all()
    return [
        {
            "anonymous_name": m.anonymous_name,
            "anonymous_avatar": m.anonymous_avatar,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


async def _require_account(authorization: str, db: AsyncSession) -> Account:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ", 1)[1]
    account = await acc.get_account_from_token(token, db)
    if not account:
        raise HTTPException(status_code=401, detail="登录已过期")
    return account
