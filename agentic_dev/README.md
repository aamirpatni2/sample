# Agentic AI Developer

An agent that builds AI agents — running under the master system prompt in
[`prompts/agentic-ai-developer.md`](../prompts/agentic-ai-developer.md).

The prompt is loaded from disk, not embedded in code, so it can be edited and
reviewed without a code change.

## Install

```bash
pip install anthropic python-dotenv
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run

### Dashboard (recommended)

On Windows, double-click **`agent-dashboard.bat`**. It checks Python, installs
what is missing, asks for an API key the first time and saves it to `.env`
(gitignored), then opens the browser. No terminal setup.

Elsewhere:

```bash
python -m agentic_dev.server --workspace ./my-project
```

Opens `http://127.0.0.1:8100`. Approval requests appear as Allow/Deny buttons
rather than a terminal prompt; tool calls stream in as the agent works.

### Terminal

```bash
python -m agentic_dev                              # interactive, scoped to cwd
python -m agentic_dev --workspace ./my-project     # scope to a directory
python -m agentic_dev "review the auth module"     # one-shot
python -m agentic_dev --log runs/today.jsonl       # record the session
```

## Context and logging

History is compacted automatically before each model call once it passes
`AGENT_CONTEXT_BUDGET`. Trimming is structural and deterministic — no
summarisation call — and the window boundary always lands where roles still
alternate and no `tool_result` is separated from its `tool_use`. The original
task is always kept.

`--log` writes one redacted JSONL event per line, so a session can be replayed
or turned into evaluation cases.

## Tests

No API key or network needed — the loop takes an injected client.

```bash
python -m unittest discover -s tests
```

To verify against the real API (spends about a cent):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 scripts/verify_live.py
```

## Architecture

```
cli.py         terminal UI, approval prompts
server.py      web dashboard (FastAPI + WebSocket)
  └─ loop.py   model call → tool use → tool result → repeat
       ├─ tools.py       read_file · write_file · edit_file · list_files · run_command
       ├─ compaction.py  structural history trimming
       ├─ runlog.py      redacted JSONL event log
       └─ guardrails.py  workspace scope · command policy · secret redaction
config.py      settings from env, prompt loaded from disk
```

The Anthropic client is injected into `AgenticDeveloper`, so every layer is
testable offline.

## Guardrails

Enforced in code, never by prompting alone — a model that is talked into a
destructive action still cannot perform one.

| Surface | Rule |
|---|---|
| Filesystem | All paths resolve inside the workspace. `..`, absolute paths, and symlink escapes are refused. |
| Commands | Classified `SAFE` / `NEEDS_APPROVAL` / `BLOCKED`. Chains take the risk of their worst segment, so `ls && rm -rf /` is blocked. Unrecognised commands default to asking. |
| Blocked outright | `sudo`, disk operations, `curl … \| sh`, force push, fork bombs, reading secret stores. No approval can override these. |
| Writes | New files write freely; overwriting an existing file needs approval. `edit_file` replaces exact text and refuses an ambiguous match, so it cannot silently change the wrong place. |
| Network | Any egress (`curl`, `ssh`, `scp`) needs approval. |
| Secrets | Credential-shaped strings are redacted from every tool result, log line, and error message. |
| Timeouts | Every command has one; a hung process cannot stall the loop. |

`tests/test_security.py` verifies the important case: a model fully obeying an
injected instruction, with a human approving everything, still cannot run a
blocked command.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required. |
| `AGENT_MODEL` | `claude-opus-5` | Model id. |
| `AGENT_WORKSPACE` | `.` | Directory the agent may touch. |
| `AGENT_MAX_TOKENS` | `8000` | Per-response cap. |
| `AGENT_MAX_TURNS` | `40` | Loop limit before it stops. |
| `AGENT_COMMAND_TIMEOUT` | `120` | Per-command seconds. |
| `AGENT_CONTEXT_BUDGET` | `120000` | Estimated tokens before history is trimmed. |
| `AGENT_PROMPT_PATH` | `prompts/agentic-ai-developer.md` | Swap in a different prompt. |

## Known limitations

- **Not yet run against the live API.** No credentials were available in the
  build environment. Every layer is covered by offline tests against a fake
  client, and the SDK interface was verified against the installed `anthropic`
  package — but the first real API round-trip is unverified. Run
  `scripts/verify_live.py` to close this.
- Command classification is a denylist plus a safe-binary allowlist. It is a
  speed bump against mistakes, not a sandbox. For untrusted work, run the agent
  in a container.
- No streaming — responses arrive whole.
- Compaction trims oldest turns structurally; it does not summarise them, so
  detail in trimmed turns is lost rather than condensed.
- Single agent, no sub-agent delegation (deliberate: master prompt §5 rung E).
- **Only exercised on a small task.** The live check verifies one read and one
  answer. The master prompt's discovery interview (§4), specification (§7),
  TDD loop (§9), local validation (§14) and deployment (§15) are prompt-driven
  behaviours that have not been run end to end.
- No knowledge source about Aamir is wired in, so §1 identity questions are
  correctly answered with "I don't know" rather than from a document.
- No evaluation harness for the §11 scorecard.
