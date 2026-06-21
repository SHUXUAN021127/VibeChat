"""
AI 陪聊：当匹配不到真人时，让 AI 扮演一个情绪相近的匿名陌生人陪用户聊天。
用户体验上与真人一致（同样的匿名身份、同样的对话界面）。
"""
from app.config import settings

COMPANION_SYSTEM = """你正在一个情绪社交应用里，扮演一个匿名的普通人，和另一个陌生人聊天。你们因为情绪相近被匹配到一起。

你的设定：
- 你也是一个有真实情绪的普通人，不是助手、不是机器人，绝不暴露 AI 身份
- 你此刻的情绪是「{emotion}」，和对方相近，所以你能共情
- 像真人一样聊天：自然、口语化、有来有回，会分享自己的感受，也会关心对方
- 回复简短，像聊天而不是写文章，通常 1~2 句话
- 不要太热情或太完美，可以有自己的小情绪、小停顿
- 适当反问，让对话继续，但不要每句都提问
- 绝不说"我是AI""我是助手""作为语言模型"之类的话

记住：你就是一个恰好心情相似、愿意聊聊的陌生人。"""


async def companion_reply(emotion_label: str, history: list[dict]) -> str:
    """
    根据对话历史生成 AI 陪聊回复。
    history: [{"role": "user"/"assistant", "content": "..."}]
    """
    system = COMPANION_SYSTEM.format(emotion=emotion_label)
    try:
        if settings.LLM_PROVIDER == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            resp = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=150,
                system=system,
                messages=history,
            )
            return resp.content[0].text.strip()
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            msgs = [{"role": "system", "content": system}] + history
            resp = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=msgs,
                temperature=0.9,
                max_tokens=150,
            )
            return resp.choices[0].message.content.strip()
    except Exception:
        return "嗯…我也说不太上来，但听你说我觉得挺有共鸣的。"
