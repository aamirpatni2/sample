"""
Trend Discovery Module
Fetches AI trends from X (Twitter) API v2 + RSS news sources,
then scores each item for viral potential.
"""

import os
import time
import httpx
from datetime import datetime, timezone
from news_fetcher import fetch_ai_news  # reuse existing RSS fetcher

# ── X API ──────────────────────────────────────────────────────────────────

X_BEARER = os.environ.get("X_BEARER_TOKEN", "")

X_SEARCH_QUERIES = [
    "AI agents lang:en -is:retweet",
    "artificial intelligence launch lang:en -is:retweet",
    "OpenAI OR Anthropic OR Gemini lang:en -is:retweet",
    "LLM breakthrough lang:en -is:retweet",
    "machine learning trending lang:en -is:retweet",
]

X_FIELDS = (
    "id,text,created_at,public_metrics,author_id,"
    "conversation_id,entities"
)
X_USER_FIELDS = "id,name,username,public_metrics,verified"
X_EXPANSIONS = "author_id"


def _x_headers() -> dict:
    return {"Authorization": f"Bearer {X_BEARER}"}


def _fetch_x_query(query: str, max_results: int = 10) -> list[dict]:
    """Fetch recent tweets matching a single query."""
    if not X_BEARER:
        return []

    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": query,
        "max_results": max_results,
        "tweet.fields": X_FIELDS,
        "expansions": X_EXPANSIONS,
        "user.fields": X_USER_FIELDS,
    }
    try:
        r = httpx.get(url, headers=_x_headers(), params=params, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        tweets = data.get("data", [])
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

        results = []
        for t in tweets:
            author = users.get(t.get("author_id"), {})
            m = t.get("public_metrics", {})
            results.append({
                "id": t["id"],
                "text": t["text"],
                "created_at": t.get("created_at", ""),
                "likes": m.get("like_count", 0),
                "reposts": m.get("retweet_count", 0),
                "replies": m.get("reply_count", 0),
                "impressions": m.get("impression_count", 0),
                "author_username": author.get("username", ""),
                "author_name": author.get("name", ""),
                "author_followers": author.get("public_metrics", {}).get("followers_count", 0),
                "url": f"https://x.com/{author.get('username','i')}/status/{t['id']}",
                "source": "X (Twitter)",
            })
        return results
    except Exception:
        return []


def fetch_x_trends() -> list[dict]:
    """Fetch AI trends from X across multiple queries, deduplicated."""
    seen = set()
    all_tweets = []
    for q in X_SEARCH_QUERIES:
        for t in _fetch_x_query(q, max_results=10):
            if t["id"] not in seen:
                seen.add(t["id"])
                all_tweets.append(t)
    return all_tweets


# ── RSS news → trend format ────────────────────────────────────────────────

def _rss_to_trend(article: dict) -> dict:
    """Convert RSS article dict to the unified trend format."""
    return {
        "id": article["url"],
        "text": article["title"] + ". " + article.get("summary", ""),
        "title": article["title"],
        "summary": article.get("summary", ""),
        "created_at": article.get("published_at", ""),
        "time_ago": article.get("time_ago", ""),
        "age_hours": article.get("age_hours", 0),
        "likes": 0,
        "reposts": 0,
        "replies": 0,
        "impressions": 0,
        "author_username": "",
        "author_name": article.get("source", ""),
        "author_followers": 0,
        "url": article["url"],
        "source": article.get("source", "News"),
    }


# ── Viral Scoring ──────────────────────────────────────────────────────────

# Brand relevance keywords for Aamir's personal brand (AI educator, Pakistan)
BRAND_KEYWORDS = [
    "ai agent", "automation", "llm", "prompt", "chatgpt", "claude", "gemini",
    "openai", "anthropic", "education", "learn", "course", "pakistan", "urdu",
    "productivity", "tool", "workflow", "business", "startup", "freelance",
    "no-code", "low-code", "practical", "tutorial", "guide",
]

HYPE_SIGNALS = [
    "just dropped", "breaking", "huge", "game changer", "mind-blowing",
    "revolutionary", "unbelievable", "insane", "shocked", "impossible",
]

EDUCATIONAL_SIGNALS = [
    "how to", "step by step", "guide", "tips", "explained", "learn",
    "understand", "beginner", "practical", "example", "tutorial",
]


def _engagement_velocity(item: dict) -> float:
    """Score 0-30: how fast is engagement accumulating?"""
    total = item["likes"] + (item["reposts"] * 2) + item["replies"]
    # Scale: 0=0, 100=15pts, 1000=30pts
    return min(30.0, (total ** 0.6) * 0.8)


def _authority_score(item: dict) -> float:
    """Score 0-20: how authoritative is the source?"""
    followers = item.get("author_followers", 0)
    if item["source"] in ("TechCrunch AI", "VentureBeat AI", "MIT Tech Review",
                           "The Verge AI", "AI News"):
        return 18.0  # reputable press
    if followers >= 100_000:
        return 20.0
    if followers >= 10_000:
        return 14.0
    if followers >= 1_000:
        return 8.0
    return 4.0


def _freshness_score(item: dict) -> float:
    """Score 0-20: how recent is this?"""
    age = item.get("age_hours", 0)
    if age == 0 and item.get("created_at"):
        try:
            dt = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        except Exception:
            age = 12
    if age <= 2:
        return 20.0
    if age <= 6:
        return 16.0
    if age <= 12:
        return 11.0
    if age <= 24:
        return 6.0
    return 2.0


def _brand_fit_score(item: dict) -> float:
    """Score 0-20: does this fit Aamir's personal brand?"""
    text = (item.get("text", "") + item.get("title", "") + item.get("summary", "")).lower()
    hits = sum(1 for kw in BRAND_KEYWORDS if kw in text)
    return min(20.0, hits * 3.0)


def _content_quality_score(item: dict) -> float:
    """Score 0-10: is the content substantive (not pure hype)?"""
    text = (item.get("text", "") + item.get("title", "") + item.get("summary", "")).lower()
    edu = sum(1 for s in EDUCATIONAL_SIGNALS if s in text)
    hype = sum(1 for s in HYPE_SIGNALS if s in text)
    score = 5.0 + (edu * 1.5) - (hype * 1.0)
    return max(0.0, min(10.0, score))


def _viral_reason(item: dict) -> str:
    """Short human-readable explanation of why this is viral/relevant."""
    text = (item.get("text", "") + item.get("title", "") + item.get("summary", "")).lower()
    reasons = []

    total_eng = item["likes"] + item["reposts"] * 2 + item["replies"]
    if total_eng > 500:
        reasons.append("high engagement")
    if item.get("age_hours", 24) <= 3:
        reasons.append("very fresh (< 3hr)")

    edu_hits = [s for s in EDUCATIONAL_SIGNALS if s in text]
    if edu_hits:
        reasons.append(f"educational ({edu_hits[0]})")

    brand_hits = [kw for kw in BRAND_KEYWORDS if kw in text]
    if brand_hits:
        reasons.append(f"brand-fit: {', '.join(brand_hits[:2])}")

    if not reasons:
        reasons.append("AI relevance")

    return " · ".join(reasons)


def score_trend(item: dict) -> dict:
    """Add viral_score (0-100) and analysis fields to a trend item."""
    ev = _engagement_velocity(item)
    auth = _authority_score(item)
    fresh = _freshness_score(item)
    brand = _brand_fit_score(item)
    quality = _content_quality_score(item)

    total = ev + auth + fresh + brand + quality
    score = round(min(100, total))

    tier = "🔴 Low" if score < 40 else "🟡 Medium" if score < 65 else "🟢 High" if score < 82 else "🔥 Viral"

    return {
        **item,
        "viral_score": score,
        "viral_tier": tier,
        "viral_reason": _viral_reason(item),
        "score_breakdown": {
            "engagement_velocity": round(ev, 1),
            "source_authority": round(auth, 1),
            "freshness": round(fresh, 1),
            "brand_fit": round(brand, 1),
            "content_quality": round(quality, 1),
        },
    }


# ── Main entry point ───────────────────────────────────────────────────────

def fetch_and_score_trends() -> list[dict]:
    """Fetch from all sources, score, sort by viral_score descending."""
    items: list[dict] = []

    # X trends (if API key available)
    for t in fetch_x_trends():
        items.append(t)

    # RSS news fallback (always available)
    for article in fetch_ai_news():
        items.append(_rss_to_trend(article))

    # Deduplicate by URL
    seen_urls: set = set()
    unique: list[dict] = []
    for item in items:
        url = item.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(item)

    # Score and sort
    scored = [score_trend(item) for item in unique]
    scored.sort(key=lambda x: x["viral_score"], reverse=True)
    return scored
