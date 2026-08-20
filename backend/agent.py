import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── Facebook ───────────────────────────────────────────────────────────────

FB_SYSTEM = """You are a Facebook content writer specializing in AI news for a Pakistani audience.
Write engaging Facebook posts in a mix of English and Urdu (Roman Urdu / Hinglish style).
Use relevant emojis and popular AI hashtags.
Keep posts between 100-200 words each.
Make the content feel authentic, not like a press release."""

# ── X (Twitter) ────────────────────────────────────────────────────────────

TWEET_SYSTEM = """You are a viral X (Twitter) content writer for Aamir, a Pakistani AI educator with a tech-savvy audience.
Write punchy, engaging tweets that get likes and retweets.
Mix English and Roman Urdu naturally (Hinglish style).
Use emojis strategically — not too many.
Always include 2-3 relevant hashtags at the end."""

THREAD_SYSTEM = """You are a viral X (Twitter) thread writer for Aamir, a Pakistani AI educator.
Write compelling threads that educate and engage a Pakistani tech audience.
Mix English and Roman Urdu naturally (Hinglish style).
Each tweet in the thread should flow naturally to the next.
Use emojis strategically. Include hashtags only in the last tweet."""

TONE_INSTRUCTIONS = {
    "informative": "Clear, educational tone. Share key facts and why this matters to the audience.",
    "breaking": "Breaking news style — urgent, exciting, immediate. Use 'BREAKING', 'JUST IN', 'BIG NEWS'.",
    "thought": "Thought-provoking — ask a question, challenge assumptions, spark discussion.",
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
        system=FB_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    parts = [p.strip() for p in raw.split("---POST---") if p.strip()]
    return parts[:3]


def generate_tweet(headline: str, summary: str, tone: str) -> list[str]:
    tone_note = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["informative"])

    prompt = f"""AI News Headline: {headline}

Summary: {summary}

Tone instruction: {tone_note}

Write exactly 3 viral tweet variations about this AI news.
Rules:
- Each tweet must be under 280 characters
- Hook in first line — grab attention instantly
- End with 2-3 hashtags
- Separate each tweet with: ---TWEET---
Do not number them."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        system=TWEET_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    parts = [p.strip() for p in raw.split("---TWEET---") if p.strip()]
    return parts[:3]


def rewrite_viral_post(original_text: str, platform: str, author: str, likes: int, reposts: int) -> dict:
    """Analyze a viral post and rewrite it in Aamir's style for both X and Facebook."""

    analysis_prompt = f"""This tweet/post went viral on X (Twitter):

---
{original_text}
---

Author: @{author} | Likes: {likes} | Reposts: {reposts}

Your task:
1. ANALYZE: What makes this post viral? Identify:
   - Hook (first line strategy)
   - Key hashtags used
   - CTA (call to action)
   - Tone/style

2. REWRITE for Aamir (Pakistani AI educator, Hinglish style):
   - X Tweet version (max 280 chars) — same hook style, Hinglish
   - Facebook version (100-150 words) — same energy, Hinglish with emojis

Format your response EXACTLY like this:
HOOK: [what the hook technique was]
HASHTAGS: [hashtags from original]
CTA: [what CTA was used]
STYLE: [tone description]
---XTWEET---
[rewritten tweet in Hinglish, max 280 chars]
---FACEBOOK---
[rewritten Facebook post in Hinglish]"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        system="You are a viral content analyst and rewriter for Aamir, a Pakistani AI educator. You analyze what makes posts go viral and recreate that magic in Hinglish (English + Roman Urdu mix) for a Pakistani tech audience.",
        messages=[{"role": "user", "content": analysis_prompt}],
    )

    raw = message.content[0].text

    analysis = {}
    for field in ["HOOK", "HASHTAGS", "CTA", "STYLE"]:
        for line in raw.split("\n"):
            if line.startswith(f"{field}:"):
                analysis[field.lower()] = line.replace(f"{field}:", "").strip()

    tweet = ""
    fb = ""
    if "---XTWEET---" in raw and "---FACEBOOK---" in raw:
        tweet = raw.split("---XTWEET---")[1].split("---FACEBOOK---")[0].strip()
        fb = raw.split("---FACEBOOK---")[1].strip()

    return {
        "analysis": analysis,
        "x_tweet": tweet,
        "facebook": fb,
    }


def generate_thread(headline: str, summary: str, tone: str) -> list[str]:
    tone_note = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["informative"])

    prompt = f"""AI News Headline: {headline}

Summary: {summary}

Tone instruction: {tone_note}

Write a viral Twitter/X thread about this AI news. The thread should have exactly 6 tweets.

Thread structure:
Tweet 1 (Hook): Bold statement or shocking fact — make people stop scrolling
Tweet 2 (What): What happened / what is this?
Tweet 3 (Why): Why does this matter?
Tweet 4 (Impact): Real-world impact — jobs, business, Pakistan mein kya asar hoga?
Tweet 5 (Insight): Your unique take or lesson
Tweet 6 (CTA): Call to action + 3 hashtags

Rules:
- Each tweet max 280 characters
- Separate each tweet with: ---TWEET---
- Use 🧵 at start of tweet 1
- Number format: e.g. "2/" at start of tweets 2-6"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        system=THREAD_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    parts = [p.strip() for p in raw.split("---TWEET---") if p.strip()]
    return parts[:6]
