"""
内容审核：双层防线
1. 本地敏感词库 —— 快速拦截明显的侮辱/歧视/违法词汇
2. AI 审核 —— 识别更隐晦的恶意表达（可选，调用 LLM）

返回 (is_violation, reason)
"""
import re
from app.config import settings

# 本地敏感词库（示例集，实际可扩充）
# 为避免在代码里堆砌攻击性词汇，这里用部分代表词 + 可外部扩展
BANNED_WORDS = [
    # 侮辱类
    "傻逼", "煞笔", "sb", "废物", "贱人", "婊子", "畜生", "杂种", "蠢货",
    "脑残", "智障", "白痴", "弱智", "去死", "滚蛋",
    # 歧视类
    "黑鬼", "支那", "尼哥", "残废",
    # 其他违背公序良俗（占位，可扩展）
]

# 规避变体的简单归一化（去空格、统一小写、去常见分隔符）
def _normalize(text: str) -> str:
    t = text.lower()
    t = re.sub(r"[\s\*\.\-_/\\|]+", "", t)
    return t


def check_local(text: str) -> tuple[bool, str]:
    """本地词库检查"""
    normalized = _normalize(text)
    for word in BANNED_WORDS:
        if _normalize(word) in normalized:
            return True, "包含不文明用语"
    return False, ""


AI_MODERATION_PROMPT = """你是内容安全审核员。判断下面这段聊天消息是否包含：侮辱谩骂、种族/性别/地域歧视、暴力威胁、色情低俗、违法或严重违背公序良俗的内容。

消息："{text}"

只返回一个 JSON（不要任何其他文字）：
{{"violation": true 或 false, "reason": "若违规，用不超过10字说明类别，否则为空"}}

注意：正常的负面情绪表达（如倾诉难过、焦虑、愤怒情绪本身）不算违规。只有针对他人的攻击、歧视、威胁等才算违规。"""


async def check_ai(text: str) -> tuple[bool, str]:
    """AI 审核（调用 LLM）。失败时返回不违规，避免误伤正常聊天。"""
    try:
        import json
        if settings.LLM_PROVIDER == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            resp = await client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=100,
                messages=[{"role": "user", "content": AI_MODERATION_PROMPT.format(text=text)}],
            )
            raw = resp.content[0].text.strip()
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": AI_MODERATION_PROMPT.format(text=text)}],
                temperature=0,
                max_tokens=100,
            )
            raw = resp.choices[0].message.content.strip()

        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            if data.get("violation"):
                return True, data.get("reason") or "内容不当"
        return False, ""
    except Exception:
        # AI 审核失败不阻断正常聊天
        return False, ""


async def moderate(text: str) -> tuple[bool, str]:
    """
    完整审核：先本地（快），本地放行再 AI（智能）。
    AI 审核由 ENABLE_AI_MODERATION 控制。
    """
    # 第一层：本地词库
    is_bad, reason = check_local(text)
    if is_bad:
        return True, reason

    # 第二层：AI 审核（可开关）
    if settings.ENABLE_AI_MODERATION:
        return await check_ai(text)

    return False, ""
