# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository holds

Two independent systems that share only a test suite and a git history:

- **`backend/` + `frontend/`** — the AI News Content Agent. A FastAPI service that pulls AI news from RSS, scores X/Twitter trends, and generates social posts for nine platforms. `frontend/index.html` is a single 1,300-line dashboard served as a static file by the same app.
- **`agentic_dev/`** — a tool-using Claude agent that builds AI agents, running under the master prompt in `prompts/agentic-ai-developer.md`. Unrelated to the content agent; it just lives here.

## Commands

```bash
# Offline suite — no API key, no network.
python3 -m unittest discover -s tests

# One module, one class, one test
python3 -m unittest tests.test_guardrails
python3 -m unittest tests.test_content_agent.TestCharLimitEnforcement
python3 -m unittest tests.test_loop.TestToolUse.test_executes_tool_then_returns_final_text

# Live verification — the ONLY thing here that spends money (~$0.01)
python3 scripts/verify_live.py            # both systems
python3 scripts/verify_live.py --content  # content agent only

# Run the content dashboard
cd backend && uvicorn main:app --reload --port 8000   # then open http://127.0.0.1:8000
# Windows: start.bat does this and opens the browser

# Run the agentic developer
python3 -m agentic_dev --workspace ./some-project --log runs/session.jsonl
```

Check the suite's **exit code**, not piped output — `... | tail` has masked a
failure here before.

Dependencies split: `backend/requirements.txt` (web stack) and
`requirements-agent.txt` (agent only). `tests/test_api_integration.py` raises
`SkipTest` when the web stack is absent, so a content-only machine still runs
a green suite.

## Content agent architecture (`backend/agent.py`)

One `BRAND` block, one `PLATFORMS` registry, one `_call` path, one parser. Nine
public `generate_*` functions are thin wrappers. Before the rewrite these were
nine near-identical functions with drifting instructions.

**The public function signatures are frozen.** `backend/main.py` imports eleven
names, and `frontend/index.html` reads specific JSON keys (`posts`, `analysis`,
`x_tweet`, `facebook`, `plan`, `articles`, `trends`, `suggestions`, `count`).
`tests/test_api_integration.py` pins that contract — run it after any change to
`agent.py`.

Three constraints in this file exist because of live failures, and each has a
test guarding it:

1. **The language rule must be appended last** (`_system_prompt`). `CONTENT_LANGUAGE`
   sets English or Hinglish, but the Facebook template contains Roman Urdu CTA
   lines. When the language rule sat earlier in the prompt, the model matched
   the later template and wrote whole posts in Roman Urdu under
   `language=english`. Recency wins; emphasis does not. Do not move it.
2. **Hard character limits are enforced in code, never asked for in the prompt.**
   Models cannot count characters. Platforms declare `char_limit`; `fit_to_limit`
   guarantees it by dropping trailing hashtags, then whole words. Prompts ask for
   a *word* budget, which is obeyable.
3. **The fixed brand lines are repaired in code** (`repair_fixed_lines`). A live
   run published "ke lije" for "ke liye" — the model paraphrases lines it is told
   to copy verbatim. Near-identical lines are snapped back to canonical, which
   also keeps `roman_urdu_score` honest, since it strips those lines by exact
   match before scoring.
4. **`split_variations` assumes the model will break its contract** — it strips
   chatty preambles and numbering the prompt told it to omit.

`roman_urdu_score()` verifies output language; `usage_summary()` reports tokens
and USD cost from `PRICING`.

## Agentic developer architecture (`agentic_dev/`)

```
cli.py     → loop.py → tools.py → guardrails.py
server.py  ↗         → compaction.py, runlog.py
```

Two front ends over the same loop: `cli.py` for the terminal, `server.py` for the
browser dashboard (`python -m agentic_dev.server`). The agent loop is
synchronous, so the server runs it in a worker thread; `server.Bridge` is the
only place that boundary matters — it pushes events out and blocks the worker on
approval answers coming back. A closed socket or a silent human both resolve to
refusal, so a thread never parks forever and nothing runs unapproved.

`config.load_dotenv_key()` fills `ANTHROPIC_API_KEY` from `.env` when the
environment does not already carry it, so the dashboard works when launched by
double-click with no shell to export in. An existing environment variable always
wins.

**The Anthropic client is injected into `AgenticDeveloper`**, which is the single
decision that makes the whole package testable with no API key. Keep it that way;
tests drive it with a scripted fake client.

`edit_file` is the tool for changing an existing file; `write_file` rewrites
whole files and needs approval to overwrite. An `edit_file` call whose
`old_string` matches more than once is refused rather than guessed at — picking
the wrong match corrupts working code silently.

**Guardrails are enforced in code, never by prompting.** `tests/test_security.py`
asserts the load-bearing property: a model fully obeying an injected instruction,
with a human approving everything, still cannot run a blocked command.

Two rules in `guardrails.py` came from bypasses found by probing an earlier
version, and `tests/test_guardrail_bypass.py` locks both:

- Commands are tokenised **quote-aware** (`shlex` with `punctuation_chars`), so
  redirection is caught as a class and a `;` inside a quoted string is data.
  Without this, `echo pwned > /etc/passwd` classified as safe.
- The safe list holds only binaries where **no** invocation can write, execute,
  or reach the network. Interpreters (`python3`, `node`, `awk`, `bash`),
  flag-dependent tools (`sed -i`, `find -delete`, `env`) are deliberately absent —
  a binary-level allowlist cannot express "safe unless flag X". Adding any of
  them back reopens arbitrary code execution.

**`compaction.py`: the retained window must begin on an assistant message.** That
single rule keeps roles alternating *and* guarantees no `tool_result` is
separated from the `tool_use` it answers — the API rejects the request otherwise.

## Prompts

`prompts/agentic-ai-developer.md` is the agent's system prompt, loaded from disk
at startup so it can be edited and reviewed as a document.
`prompts/OPTIMIZATION-NOTES.md` records what changed from v1 and why.

## Measured, do not redo

**Prompt caching does not apply to the content agent.** Haiku 4.5 needs a
4096-token minimum cacheable prefix; the largest system prompt here is ~714
tokens, so a cache marker would silently no-op (`cache_creation_input_tokens: 0`,
no error). Output tokens are also ~70% of spend, so caching input would be a
small lever even if it worked. A measured run costs $0.0074 for three platform
generations. Do not add caching without re-measuring against the model actually
in use.

## Working notes

Three bugs here shipped past a fully green suite: output in the wrong language, a
tweet over the character limit, and a misspelled brand line ("ke lije"). All three
passed because the tests checked structure (counts, hashtags, presence) and never
the property that mattered. When adding a check, ask what would still be broken if
it passed.

All three had the same fix, and it is the rule to reach for first here: a
requirement the model must meet *exactly* belongs in code, not in a more forceful
prompt. Prompts set direction; code sets guarantees.

The author is based in Pakistan and the content targets an Urdu-speaking
audience; Roman Urdu in CTA lines and prompt text is intentional, not a typo.
