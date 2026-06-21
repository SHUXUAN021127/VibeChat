import json
import re
from app.config import settings

EMOTION_PROMPT = """你是一个专业的情绪分析师。请分析以下用户输入的情绪，并以 JSON 格式返回结果。

用户输入："{text}"

请返回如下 JSON（不要包含任何其他文字，只返回 JSON）：
{{
  "emotion_label": "主情绪标签（如：平静、焦虑、兴奋、悲伤、愤怒、期待、孤独、快乐、迷茫、释然等）",
  "emotion_score": 情绪强度，0.0到1.0的浮点数（0=非常微弱，1=非常强烈）,
  "emotion_valence": 情绪正负向，-1.0到1.0的浮点数（-1=极度负面，0=中性，1=极度正面）,
  "secondary_emotions": [
    {{"label": "次要情绪1", "weight": 0.0到1.0的占比}},
    {{"label": "次要情绪2", "weight": 0.0到1.0的占比}}
  ],
  "emotion_keywords": ["关键词1", "关键词2", "关键词3"],
  "emotion_color": "代表该情绪的十六进制颜色（如 #6366f1）",
  "emotion_summary": "对用户情绪状态的简短解读，温暖且有共情，50字以内",
  "opening_line": "一句适合开启对话的破冰语，站在理解者角度，30字以内",
  "is_crisis": false（如果检测到极度悲观、自我伤害倾向等危机信号则为true）
}}

关于 secondary_emotions：人的情绪往往是复合的。请识别除主情绪外，文字中隐含的 2~3 个次要情绪及其占比（weight 0~1，表示这个情绪在整体中的比重）。例如"今天搞定了项目但好累，又有点担心下一步"主情绪可能是"疲惫"，次要情绪有"成就感"(0.4)、"焦虑"(0.3)。如果情绪很单一，secondary_emotions 可以为空数组。

情绪颜色参考（可根据具体情绪微调）：
- 平静/释然：#6ee7b7（薄荷绿）
- 快乐/兴奋：#fbbf24（暖黄）
- 焦虑/迷茫：#a78bfa（紫色）
- 悲伤/孤独：#60a5fa（蓝色）
- 愤怒/烦躁：#f87171（红色）
- 期待/好奇：#fb923c（橙色）
- 复杂/矛盾：#94a3b8（灰蓝）

重要：请用一致、确定的标准判断。对于相同或高度相似的输入，应给出相同的主情绪标签、正负向和强度，避免随意波动。优先选择最贴切、最稳定的判断。
"""

async def analyze_emotion(text: str) -> dict:
    """调用 LLM 分析情绪，自动根据配置选择 OpenAI 或 Anthropic"""
    if settings.LLM_PROVIDER == "anthropic":
        return await _analyze_with_anthropic(text)
    else:
        return await _analyze_with_openai(text)

async def _analyze_with_openai(text: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": EMOTION_PROMPT.format(text=text)}],
        temperature=0,      # 0 = 最确定，相同输入尽量给相同判断
        seed=42,            # 固定种子，进一步提升可复现性
        max_tokens=500,
    )
    raw = response.choices[0].message.content.strip()
    return _parse_emotion_json(raw)

async def _analyze_with_anthropic(text: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=500,
        temperature=0,      # 0 = 最确定
        messages=[{"role": "user", "content": EMOTION_PROMPT.format(text=text)}],
    )
    raw = response.content[0].text.strip()
    return _parse_emotion_json(raw)

def _parse_emotion_json(raw: str) -> dict:
    """解析 LLM 返回的 JSON，带容错处理"""
    try:
        # 尝试直接解析
        return json.loads(raw)
    except json.JSONDecodeError:
        # 尝试提取 JSON 块
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    # 兜底返回
    return {
        "emotion_label": "未知",
        "emotion_score": 0.5,
        "emotion_valence": 0.0,
        "secondary_emotions": [],
        "emotion_keywords": [],
        "emotion_color": "#94a3b8",
        "emotion_summary": "我感受到了你想说的，让我们继续聊聊吧。",
        "opening_line": "你好，很高兴认识你。",
        "is_crisis": False,
    }
