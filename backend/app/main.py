from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from app.models import init_db, AsyncSessionLocal
from app.routers import emotion, match, chat, account
from app.services.matching import cleanup_stale_rooms
from app.config import settings

async def periodic_cleanup():
    """每 10 秒清理一次过期的等待房间和闲置房间"""
    while True:
        await asyncio.sleep(10)
        try:
            async with AsyncSessionLocal() as db:
                await cleanup_stale_rooms(db)
        except Exception as e:
            print(f"清理任务出错: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(periodic_cleanup())
    yield
    task.cancel()

app = FastAPI(
    title="VibeChat API",
    description="AI 驱动的情绪社交平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(emotion.router)
app.include_router(match.router)
app.include_router(chat.router)
app.include_router(account.router)

@app.get("/")
async def root():
    return {"status": "ok", "app": "VibeChat", "llm_provider": settings.LLM_PROVIDER}

@app.get("/health")
async def health():
    return {"status": "healthy"}
