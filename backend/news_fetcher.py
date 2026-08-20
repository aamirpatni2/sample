import feedparser
import time
from datetime import datetime, timezone

AI_SOURCES = [
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"},
    {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/"},
    {"name": "AI News", "url": "https://www.artificialintelligence-news.com/feed/"},
]

AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "llm",
    "chatgpt", "openai", "google gemini", "claude", "deep learning",
    "neural network", "generative ai", "gpt", "large language model",
    "robot", "automation", "algorithm", "nvidia", "deepmind", "mistral",
    "anthropic", "meta ai", "copilot", "gemini", "llama", "midjourney",
    "stable diffusion", "dall-e", "sora", "transformer", "diffusion model",
]

SECONDS_IN_24H = 86400


def _is_ai_related(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in AI_KEYWORDS)


def _parse_time(entry) -> datetime | None:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return None


def _time_ago(dt: datetime) -> str:
    diff = int((datetime.now(tz=timezone.utc) - dt).total_seconds())
    if diff < 3600:
        return f"{diff // 60} min ago"
    if diff < 86400:
        return f"{diff // 3600} hr ago"
    return f"{diff // 86400} day ago"


def fetch_ai_news() -> list[dict]:
    now = datetime.now(tz=timezone.utc)
    seen_urls = set()
    articles = []

    for source in AI_SOURCES:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries:
                url = entry.get("link", "")
                if url in seen_urls:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "") or entry.get("description", "")

                published = _parse_time(entry)
                if not published:
                    continue

                age_seconds = (now - published).total_seconds()
                if age_seconds > SECONDS_IN_24H:
                    continue

                if not _is_ai_related(title, summary):
                    continue

                seen_urls.add(url)
                articles.append({
                    "title": title,
                    "summary": summary[:400] if summary else "",
                    "url": url,
                    "source": source["name"],
                    "published_at": published.isoformat(),
                    "time_ago": _time_ago(published),
                    "age_hours": round(age_seconds / 3600, 1),
                })
        except Exception:
            continue

    articles.sort(key=lambda a: a["published_at"], reverse=True)
    return articles
