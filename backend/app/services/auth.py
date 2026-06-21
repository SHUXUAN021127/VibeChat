import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User
from app.services.matching import generate_anonymous_identity

async def get_or_create_user(session_token: str | None, db: AsyncSession) -> tuple[User, str]:
    """
    无需注册：根据 session_token 获取或创建匿名用户
    返回 (user, token)
    """
    if session_token:
        result = await db.execute(select(User).where(User.session_token == session_token))
        user = result.scalar_one_or_none()
        if user:
            return user, session_token

    # 创建新匿名用户
    token = secrets.token_urlsafe(32)
    name, avatar = generate_anonymous_identity()
    user = User(
        anonymous_name=name,
        anonymous_avatar=avatar,
        session_token=token,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, token
