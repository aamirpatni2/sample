# Al Roshan Restaurant — RoshanBot AI Ordering Agent

Authentic Middle Eastern cuisine meets AI-powered ordering. RoshanBot handles pickup and delivery orders, applies promotions, and routes confirmed orders to the kitchen dashboard.

## Stack
- **Frontend**: HTML / CSS / Vanilla JS (static, served by Express)
- **Backend**: Node.js + Express
- **AI**: Anthropic Claude (claude-sonnet) with agent tools
- **Storage**: JSON files (dev) — swap for a real DB in production

## Local Setup

```bash
# 1. Clone and install
npm install

# 2. Set up environment
cp .env.example .env
# Fill in your ANTHROPIC_API_KEY in .env

# 3. Start server
npm start
# → http://localhost:3000
```

## URLs
| URL | Description |
|-----|-------------|
| `http://localhost:3000` | Customer-facing restaurant website with RoshanBot |
| `http://localhost:3000/staff/dashboard.html` | Kitchen order management dashboard |

## Project Structure
```
├── frontend/          # Static website (index.html, styles.css, app.js)
├── staff/             # Staff dashboard (dashboard.html)
├── data/              # JSON data files (menu, promotions, orders)
├── prompts/           # RoshanBot system prompt
├── server.js          # Express backend + Claude AI agent
├── CLAUDE.md          # Project rules for Claude Code
└── .env.example       # Environment variable template
```

## Security
- API keys live in `.env` only (never committed to git)
- `.env.example` (placeholders only) is what goes to GitHub
- All order math is calculated deterministically in backend code

## Deployment (Vercel)
1. Push to GitHub
2. Import repo in Vercel dashboard
3. Set `ANTHROPIC_API_KEY` in Vercel environment variables
4. Deploy
