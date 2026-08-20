# AI News Content Agent

Fresh AI news (last 24 hours only) → Facebook post generator powered by Claude AI.

## Setup

```bash
cd backend
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Then open `frontend/index.html` in your browser.

## Features

- Fetches AI news from 5 sources (TechCrunch, The Verge, VentureBeat, MIT Tech Review, AI News)
- Filters to last 24 hours only — no old articles
- Covers all AI content: news, tutorials, guides, announcements
- Generates 3 Facebook post variations per article
- Three tones: Informative, Breaking News, Thought-Provoking
- Hinglish style (English + Urdu mix) for Pakistani audience
- One-click copy for each post
