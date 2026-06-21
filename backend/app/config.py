from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # LLM
    LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # App
    SECRET_KEY: str = "vibechat-dev-secret"
    DATABASE_URL: str = "sqlite+aiosqlite:///./vibechat.db"
    FRONTEND_URL: str = "http://localhost:3000"

    # 匹配模式: similar(相似情绪) / complementary(互补情绪)
    MATCH_MODE: str = "similar"

    # 是否启用 AI 内容审核（每条消息会额外调用一次 LLM，消耗 token）
    ENABLE_AI_MODERATION: bool = True

    # ===== 账号 & 第三方登录 =====
    # Google OAuth（在 Google Cloud Console 创建）
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/account/google/callback"
    # 微信开放平台（需企业认证，演示可留空）
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
