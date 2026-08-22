# Al Roshan Restaurant — RoshanBot Project Rules

## Project Overview
Al Roshan Restaurant AI ordering agent. RoshanBot is the customer-facing assistant.
Backend: Node.js / Express. AI: Anthropic Claude (claude-sonnet). Storage: JSON files (dev).

## Architecture
- frontend/ → static HTML/CSS/JS served by Express
- server.js → Express backend, POST /api/chat, PUT /api/orders/:id/status
- prompts/system-prompt.md → RoshanBot persona and rules (loaded at server start)
- data/menu.json → single source of truth for all menu items and prices
- data/promotions.json → active discount codes and rules
- data/orders.json → dev-only order persistence (replace with DB in production)
- staff/dashboard.html → staff-only order management view

## Coding Rules
- Keep functions small and single-purpose
- All money calculations happen in backend code — never ask Claude to do math
- Validate all tool inputs against menu.json before accepting them
- Use async/await throughout; always try/catch API calls
- No inline secrets; all keys come from process.env via dotenv

## Security Rules
- NEVER put API keys in frontend JavaScript
- .env stays local only — .env.example (placeholders) goes to GitHub
- Never commit node_modules or .env
- API route must validate req.body before passing to Claude

## Token-Saving Rules
- Load system-prompt.md once at server start, not per request
- Send only the last 10 conversation turns to Claude (sliding window)
- Menu is in the system prompt as grounding context — don't re-fetch per message
- Tool results should be concise JSON, not prose

## RoshanBot Rules (enforce in system prompt AND code)
- Only discuss Al Roshan menu items — never invent prices, products, or discount codes
- Require explicit customer confirmation before saving any order
- Never guess customer address details
- Only apply active promotions from promotions.json
- Collect full delivery address (name, phone, street, apt, instructions) — read back verbatim

## Dev vs Production
- orders.json is dev-only; add a comment block warning in server.js
- PORT defaults to 3000 locally; set via env var in Vercel
- Vercel env vars live in the dashboard, never in the repo
