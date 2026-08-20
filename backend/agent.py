import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ── Facebook ───────────────────────────────────────────────────────────────

FB_SYSTEM = """You are a Facebook content writer specializing in AI news.
Write engaging Facebook posts in clear English.
Use relevant emojis and popular AI hashtags.
Keep posts between 100-200 words each.
Make the content feel authentic, not like a press release."""

# ── X (Twitter) ────────────────────────────────────────────────────────────

TWEET_SYSTEM = """You are a viral X (Twitter) content writer for Aamir, an AI educator.
Write punchy, engaging tweets in clear English that get likes and retweets.
Use emojis strategically — not too many.
Always include 2-3 relevant hashtags at the end."""

THREAD_SYSTEM = """You are a viral X (Twitter) thread writer for Aamir, an AI educator.
Write compelling threads in clear English that educate and engage a tech audience.
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

2. REWRITE for Aamir (AI educator, clear English):
   - X Tweet version (max 280 chars) — same hook style, English
   - Facebook version (100-150 words) — same energy, English with emojis

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
        system="You are a viral content analyst and rewriter for Aamir, an AI educator. You analyze what makes posts go viral and recreate that magic in clear English for a tech-savvy audience.",
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


# ── LinkedIn ────────────────────────────────────────────────────────────────

LINKEDIN_SYSTEM = """You are a LinkedIn content writer for Aamir, an AI educator.
Write professional posts in clear English. At most 1-2 emojis — no overdoing it.
Length: 150-200 words. Lead with a strong insight or bold statement, not an announcement.
Use short paragraph breaks for readability. End with a thought-provoking question to drive comments."""

# ── Instagram ───────────────────────────────────────────────────────────────

INSTAGRAM_SYSTEM = """You are an Instagram caption writer for Aamir, an AI educator.
Write visual-first captions in clear English.
Structure: Bold hook line (stops the scroll) → 2-3 lines of value → CTA → 5-7 relevant hashtags.
Keep total under 220 words. Emojis are welcome but strategic."""

# ── TikTok ──────────────────────────────────────────────────────────────────

TIKTOK_SYSTEM = """You are a TikTok video script writer for Aamir, an AI educator.
Write punchy 60-second video script ideas in clear English.
Structure:
HOOK (0-3 sec): Must stop the scroll — bold claim or shocking fact
MAIN (4-50 sec): Deliver the value clearly
CTA (51-60 sec): Follow + comment prompt
Include on-screen text suggestions in [square brackets]."""

# ── YouTube Shorts ──────────────────────────────────────────────────────────

YOUTUBE_SYSTEM = """You are a YouTube Shorts idea writer for Aamir, an AI educator.
Write Shorts concepts in clear English. Format EXACTLY like this:
TITLE: (under 60 chars, curiosity gap)
HOOK: (first 3 seconds script — must make viewer stay)
KEY POINTS: (3 bullet points for the 45-sec body)
END SCREEN CTA: (subscribe/comment prompt)"""


def generate_linkedin(headline: str, summary: str, tone: str) -> list[str]:
    tone_note = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["informative"])

    prompt = f"""AI News Headline: {headline}

Summary: {summary}

Tone instruction: {tone_note}

Write exactly 3 different LinkedIn post variations about this AI news.
Separate each post with the delimiter: ---POST---
Do not number them. Just the post content."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        system=LINKEDIN_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    parts = [p.strip() for p in raw.split("---POST---") if p.strip()]
    return parts[:3]


def generate_instagram(headline: str, summary: str, tone: str) -> list[str]:
    tone_note = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["informative"])

    prompt = f"""AI News Headline: {headline}

Summary: {summary}

Tone instruction: {tone_note}

Write exactly 3 different Instagram caption variations about this AI news.
Separate each caption with the delimiter: ---POST---
Do not number them. Just the caption content including hashtags."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1200,
        system=INSTAGRAM_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    parts = [p.strip() for p in raw.split("---POST---") if p.strip()]
    return parts[:3]


def generate_tiktok_idea(headline: str, summary: str, tone: str) -> list[str]:
    tone_note = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["informative"])

    prompt = f"""AI News Headline: {headline}

Summary: {summary}

Tone instruction: {tone_note}

Write exactly 3 different TikTok video script ideas about this AI news.
Each idea should be a complete 60-second script with HOOK, MAIN, and CTA sections.
Separate each idea with the delimiter: ---IDEA---
Do not number them."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1400,
        system=TIKTOK_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    parts = [p.strip() for p in raw.split("---IDEA---") if p.strip()]
    return parts[:3]


def generate_youtube_idea(headline: str, summary: str, tone: str) -> list[str]:
    tone_note = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["informative"])

    prompt = f"""AI News Headline: {headline}

Summary: {summary}

Tone instruction: {tone_note}

Write exactly 3 different YouTube Shorts ideas about this AI news.
Each idea must follow this EXACT format:
TITLE: ...
HOOK: ...
KEY POINTS:
- ...
- ...
- ...
END SCREEN CTA: ...

Separate each idea with the delimiter: ---IDEA---
Do not number them."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1400,
        system=YOUTUBE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    parts = [p.strip() for p in raw.split("---IDEA---") if p.strip()]
    return parts[:3]


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
