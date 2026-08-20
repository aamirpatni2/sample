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
from agent import generate_posts, generate_tweet, generate_thread
from trend_fetcher import fetch_and_score_trends

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


# Static files mount must be LAST — after all API routes
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
