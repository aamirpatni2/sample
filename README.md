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
- One-click copy for each post

## Content language

Language is a single setting, not a per-platform instruction:

```
CONTENT_LANGUAGE=english    # default: clear English, Roman-Urdu CTA lines kept
CONTENT_LANGUAGE=hinglish   # Roman Urdu mixed with English throughout
```

All nine platforms share one brand definition in `backend/agent.py` — audience,
voice, banned phrases, and the verify-AI caveat are defined once.

## Tests

```bash
python -m unittest discover -s tests        # offline, no API key needed
python3 scripts/verify_live.py --content    # against the real API (~$0.01)
```

`verify_live.py` checks what offline tests cannot: that generated posts meet
their contract (variation count, hashtag count, length, CTA present, distinct
hooks, no filler phrases) and reports real token spend.

## Token spend

`agent.usage_summary()` returns calls, tokens, and cost in USD for the current
process, priced per model in `agent.PRICING`.
