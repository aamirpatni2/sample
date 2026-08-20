import os
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

from news_fetcher import fetch_ai_news
from agent import (
    generate_posts, generate_tweet, generate_thread, rewrite_viral_post,
    generate_linkedin, generate_instagram, generate_tiktok_idea, generate_youtube_idea,
    generate_youtube_video, generate_single_tweet,
)
from trend_fetcher import fetch_and_score_trends
from google_sheets import fetch_morning_plan

app = FastAPI(title="AI Viral Content Intelligence Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

_news_cache: dict = {"articles": [], "fetched_at": 0}
_trend_cache: dict = {"trends": [], "fetched_at": 0}
CACHE_TTL = 1800  # 30 minutes


@app.get("/news")
def get_news():
    now = time.time()
    if now - _news_cache["fetched_at"] > CACHE_TTL or not _news_cache["articles"]:
        _news_cache["articles"] = fetch_ai_news()
        _news_cache["fetched_at"] = now
    return {"articles": _news_cache["articles"], "count": len(_news_cache["articles"])}


@app.post("/news/refresh")
def refresh_news():
    _news_cache["articles"] = fetch_ai_news()
    _news_cache["fetched_at"] = time.time()
    return {"articles": _news_cache["articles"], "count": len(_news_cache["articles"])}


@app.get("/trends")
def get_trends():
    now = time.time()
    if now - _trend_cache["fetched_at"] > CACHE_TTL or not _trend_cache["trends"]:
        _trend_cache["trends"] = fetch_and_score_trends()
        _trend_cache["fetched_at"] = now
    return {"trends": _trend_cache["trends"], "count": len(_trend_cache["trends"])}


@app.post("/trends/refresh")
def refresh_trends():
    _trend_cache["trends"] = fetch_and_score_trends()
    _trend_cache["fetched_at"] = time.time()
    return {"trends": _trend_cache["trends"], "count": len(_trend_cache["trends"])}


class GenerateRequest(BaseModel):
    headline: str
    summary: str = ""
    tone: str = "informative"


@app.post("/generate")
def generate(req: GenerateRequest):
    if not req.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")
    if req.tone not in ("informative", "breaking", "thought"):
        raise HTTPException(status_code=400, detail="tone must be informative, breaking, or thought")
    posts = generate_posts(req.headline, req.summary, req.tone)
    return {"posts": posts}


@app.post("/generate/tweet")
def generate_tweet_endpoint(req: GenerateRequest):
    if not req.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")
    if req.tone not in ("informative", "breaking", "thought"):
        raise HTTPException(status_code=400, detail="tone must be informative, breaking, or thought")
    tweets = generate_tweet(req.headline, req.summary, req.tone)
    return {"posts": tweets}


@app.post("/generate/thread")
def generate_thread_endpoint(req: GenerateRequest):
    if not req.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")
    if req.tone not in ("informative", "breaking", "thought"):
        raise HTTPException(status_code=400, detail="tone must be informative, breaking, or thought")
    thread = generate_thread(req.headline, req.summary, req.tone)
    return {"posts": thread}


@app.post("/generate/linkedin")
def generate_linkedin_endpoint(req: GenerateRequest):
    if not req.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")
    if req.tone not in ("informative", "breaking", "thought"):
        raise HTTPException(status_code=400, detail="tone must be informative, breaking, or thought")
    posts = generate_linkedin(req.headline, req.summary, req.tone)
    return {"posts": posts}


@app.post("/generate/instagram")
def generate_instagram_endpoint(req: GenerateRequest):
    if not req.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")
    if req.tone not in ("informative", "breaking", "thought"):
        raise HTTPException(status_code=400, detail="tone must be informative, breaking, or thought")
    posts = generate_instagram(req.headline, req.summary, req.tone)
    return {"posts": posts}


@app.post("/generate/tiktok")
def generate_tiktok_endpoint(req: GenerateRequest):
    if not req.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")
    if req.tone not in ("informative", "breaking", "thought"):
        raise HTTPException(status_code=400, detail="tone must be informative, breaking, or thought")
    posts = generate_tiktok_idea(req.headline, req.summary, req.tone)
    return {"posts": posts}


@app.post("/generate/youtube")
def generate_youtube_endpoint(req: GenerateRequest):
    if not req.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")
    if req.tone not in ("informative", "breaking", "thought"):
        raise HTTPException(status_code=400, detail="tone must be informative, breaking, or thought")
    posts = generate_youtube_idea(req.headline, req.summary, req.tone)
    return {"posts": posts}


@app.post("/generate/youtube-video")
def generate_youtube_video_endpoint(req: GenerateRequest):
    if not req.headline.strip():
        raise HTTPException(status_code=400, detail="headline is required")
    if req.tone not in ("informative", "breaking", "thought"):
        raise HTTPException(status_code=400, detail="tone must be informative, breaking, or thought")
    posts = generate_youtube_video(req.headline, req.summary, req.tone)
    return {"posts": posts}


@app.post("/auto-suggest")
def auto_suggest():
    """Fetch top 5 viral trends and auto-generate one tweet each."""
    import concurrent.futures

    # Use cached trends if available, otherwise fetch fresh
    now = time.time()
    if now - _trend_cache["fetched_at"] > CACHE_TTL or not _trend_cache["trends"]:
        _trend_cache["trends"] = fetch_and_score_trends()
        _trend_cache["fetched_at"] = now

    trends = sorted(_trend_cache["trends"], key=lambda t: t.get("viral_score", 0), reverse=True)[:5]

    def gen_tweet(t):
        headline = t.get("title") or t.get("text", "")[:200]
        summary = t.get("summary", "")
        try:
            tweet = generate_single_tweet(headline, summary)
        except Exception:
            tweet = ""
        return {
            "viral_score": t.get("viral_score", 0),
            "viral_tier": t.get("viral_tier", ""),
            "viral_reason": t.get("viral_reason", ""),
            "title": t.get("title", ""),
            "text": t.get("text", ""),
            "summary": t.get("summary", ""),
            "source": t.get("source", ""),
            "time_ago": t.get("time_ago", ""),
            "url": t.get("url", ""),
            "author_username": t.get("author_username", ""),
            "tweet": tweet,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(gen_tweet, trends))

    return {"suggestions": results, "count": len(results)}


@app.get("/morning-plan")
def get_morning_plan(csv_url: str = ""):
    if not csv_url:
        raise HTTPException(status_code=400, detail="csv_url query parameter is required")
    try:
        plan = fetch_morning_plan(csv_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    from datetime import date
    return {"plan": plan, "date": date.today().isoformat(), "count": len(plan)}


class RewriteRequest(BaseModel):
    text: str
    author: str = ""
    likes: int = 0
    reposts: int = 0


@app.post("/rewrite")
def rewrite(req: RewriteRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    result = rewrite_viral_post(req.text, "x", req.author, req.likes, req.reposts)
    return result


# Static files mount must be LAST — after all API routes
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
