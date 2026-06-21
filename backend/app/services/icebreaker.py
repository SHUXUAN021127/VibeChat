"""根据双方共同情绪生成破冰开场白"""
from app.config import settings

ICEBREAKER_PROMPT = """两个陌生人因为相近的情绪被匹配到一起聊天。请生成一句温暖、自然的开场白，帮助他们打破沉默、开始对话。

第一个人的情绪：{emotion_a}
第二个人的情绪：{emotion_b}

要求：
- 30字以内，口语化，温暖不做作
- 点出他们的共同点或情绪连接，但不要太直白说教
- 像一个懂他们的朋友在轻轻推一把

只返回这句开场白，不要任何其他内容。"""


async def generate_icebreaker(emotion_a: str, emotion_b: str) -> str:
    """生成双方定制破冰语，失败时返回通用开场白"""
    try:
        prompt = ICEBREAKER_PROMPT.format(emotion_a=emotion_a, emotion_b=emotion_b)
        if settings.LLM_PROVIDER == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            resp = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip().strip('"').strip("「」")
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=100,
            )
            return resp.choices[0].message.content.strip().strip('"').strip("「」")
    except Exception:
        return "你们此刻的心情有些相似，不如从一句问候开始？"
