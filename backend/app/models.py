from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
from app.config import settings

def _normalize_db_url(url: str) -> str:
    """
    自动适配异步驱动：
    - Railway/Heroku 给的是 postgresql:// 或 postgres://，异步需要 postgresql+asyncpg://
    - 本地 sqlite 已经是 sqlite+aiosqlite://，保持不变
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

engine = create_async_engine(_normalize_db_url(settings.DATABASE_URL), echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Account(Base):
    """登录账号：负责身份认证和历史归属。与匿名聊天身份解耦。"""
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    # 登录方式标识
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)          # 邮箱密码登录
    provider = Column(String, default="email")             # email / google / wechat / phone
    provider_id = Column(String, index=True, nullable=True)  # 第三方唯一ID
    display_name = Column(String, nullable=True)           # 仅自己可见的账号名
    phone = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    anonymous_name = Column(String, nullable=False)       # 系统生成的匿名昵称
    anonymous_avatar = Column(String, nullable=False)     # emoji 头像
    session_token = Column(String, unique=True, index=True)  # 无需注册，token即身份
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)  # 关联的登录账号（游客为空）
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    emotion_records = relationship("EmotionRecord", back_populates="user")

class EmotionRecord(Base):
    __tablename__ = "emotion_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    input_text = Column(Text, nullable=False)             # 用户原始输入
    emotion_label = Column(String, nullable=False)        # 主情绪标签
    emotion_score = Column(Float, nullable=False)         # 情绪强度 0~1
    emotion_valence = Column(Float, nullable=False)       # 正负向 -1~1
    emotion_keywords = Column(String, nullable=False)     # 关键词 JSON
    secondary_emotions = Column(String, default="[]")     # 次要情绪 JSON [{label, weight}]
    emotion_color = Column(String, nullable=False)        # 情绪颜色 hex
    emotion_summary = Column(Text, nullable=False)        # AI 解读摘要
    created_at = Column(DateTime, default=datetime.utcnow)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)  # 登录用户的历史归属

    user = relationship("User", back_populates="emotion_records")
    match = relationship("Match", back_populates="participants")

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    room_code = Column(String, unique=True, index=True)   # 随机房间码
    status = Column(String, default="waiting")            # waiting / active / ended
    room_type = Column(String, default="one_on_one")      # one_on_one / group
    emotion_label = Column(String, nullable=False)        # 房间情绪主题
    emotion_color = Column(String, nullable=False)        # 房间颜色
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)  # 最后活跃时间（闲置判断）
    icebreaker = Column(Text, nullable=True)              # 双方定制破冰语
    is_ai_companion = Column(Boolean, default=False)      # 是否为 AI 陪聊房间
    ended_at = Column(DateTime, nullable=True)

    participants = relationship("EmotionRecord", back_populates="match")
    messages = relationship("Message", back_populates="match")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    anonymous_name = Column(String, nullable=False)
    anonymous_avatar = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="messages")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 轻量迁移：为已存在的表补充新增列（兼容 SQLite 和 PostgreSQL）
        await _safe_migrate(conn)

async def _safe_migrate(conn):
    """给旧表补充新列，列已存在时忽略错误"""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE emotion_records ADD COLUMN secondary_emotions TEXT DEFAULT '[]'",
        "ALTER TABLE emotion_records ADD COLUMN account_id INTEGER",
        "ALTER TABLE matches ADD COLUMN room_type VARCHAR DEFAULT 'one_on_one'",
        "ALTER TABLE matches ADD COLUMN last_activity TIMESTAMP",
        "ALTER TABLE matches ADD COLUMN icebreaker TEXT",
        "ALTER TABLE matches ADD COLUMN is_ai_companion BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN account_id INTEGER",
    ]
    for sql in migrations:
        try:
            await conn.execute(text(sql))
        except Exception:
            pass  # 列已存在，忽略

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
