import os
import time
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from news_fetcher import fetch_ai_news
from agent import generate_posts

app = FastAPI(title="AI News Content Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_cache: dict = {"articles": [], "fetched_at": 0}
CACHE_TTL = 1800  # 30 minutes


@app.get("/news")
def get_news():
    now = time.time()
    if now - _cache["fetched_at"] > CACHE_TTL or not _cache["articles"]:
        _cache["articles"] = fetch_ai_news()
        _cache["fetched_at"] = now
    return {"articles": _cache["articles"], "count": len(_cache["articles"])}


@app.post("/news/refresh")
def refresh_news():
    _cache["articles"] = fetch_ai_news()
    _cache["fetched_at"] = time.time()
    return {"articles": _cache["articles"], "count": len(_cache["articles"])}


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
