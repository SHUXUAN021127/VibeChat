"""
账号认证：邮箱密码 + JWT。
账号(Account)与匿名身份(User)解耦：
- 账号用于登录、归属历史记录
- 聊天时仍用临时匿名 User 身份，别人看不到真实账号
"""
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Account, User
from app.config import settings

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    """简单加盐哈希（演示用；生产建议 bcrypt）"""
    salt = "vibechat_salt_2024"
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def create_jwt(account_id: int) -> str:
    payload = {
        "account_id": account_id,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("account_id")
    except Exception:
        return None


async def get_account_by_email(email: str, db: AsyncSession) -> Account | None:
    result = await db.execute(select(Account).where(Account.email == email))
    return result.scalar_one_or_none()


async def get_account_by_provider(provider: str, provider_id: str, db: AsyncSession) -> Account | None:
    result = await db.execute(
        select(Account).where(Account.provider == provider, Account.provider_id == provider_id)
    )
    return result.scalar_one_or_none()


async def create_email_account(email: str, password: str, db: AsyncSession) -> Account:
    account = Account(
        email=email,
        password_hash=hash_password(password),
        provider="email",
        display_name=email.split("@")[0],
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def get_account_from_token(token: str, db: AsyncSession) -> Account | None:
    account_id = decode_jwt(token)
    if not account_id:
        return None
    result = await db.execute(select(Account).where(Account.id == account_id))
    return result.scalar_one_or_none()
