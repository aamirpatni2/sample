import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are a Facebook content writer specializing in AI news for a Pakistani audience.
Write engaging Facebook posts in a mix of English and Urdu (Roman Urdu / Hinglish style).
Use relevant emojis and popular AI hashtags.
Keep posts between 100-200 words each.
Make the content feel authentic, not like a press release."""

TONE_INSTRUCTIONS = {
    "informative": "Write in a clear, educational tone. Share the key facts and why this matters.",
    "breaking": "Write like it's breaking news — urgent, exciting, immediate. Use words like 'JUST IN', 'BREAKING'.",
    "thought": "Write in a thought-provoking way. Ask a question, challenge assumptions, spark discussion.",
}


def generate_posts(headline: str, summary: str, tone: str) -> list[str]:
    tone_note = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["informative"])

    prompt = f"""AI News Headline: {headline}

Summary: {summary}

Tone instruction: {tone_note}

Generate exactly 3 different Facebook post variations about this AI news.
Separate each post with the delimiter: ---POST---
Do not number them. Just the post content."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    parts = [p.strip() for p in raw.split("---POST---") if p.strip()]
    return parts[:3]
