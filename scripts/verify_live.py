#!/usr/bin/env python3
"""Live verification against the real Claude API.

Everything else in this repo is tested offline against fakes. This is the one
script that spends money, and it exists to fill in the rows the offline tests
cannot: does the content actually meet its contract, and does the agent loop
actually complete a real tool round-trip.

    python3 scripts/verify_live.py              # both suites
    python3 scripts/verify_live.py --content    # content agent only
    python3 scripts/verify_live.py --agent      # agentic developer only

Costs roughly a cent. Exits non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)

HEADLINE = "OpenAI releases a free tier for its agent-building API"
SUMMARY = (
    "The company announced that developers can now build and deploy autonomous "
    "agents without an upfront subscription, with usage-based pricing after a "
    "monthly free allowance."
)

BANNED = ["game changer", "game-changer", "dive in", "revolutionary", "unlock the power"]


class Results:
    """Collects pass/fail checks and prints a scorecard."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> bool:
        self.rows.append((name, passed, detail))
        mark = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {mark}  {name}" + (f" {DIM}— {detail}{RESET}" if detail else ""))
        return passed

    @property
    def failed(self) -> int:
        return sum(1 for _, ok, _ in self.rows if not ok)

    def summary(self) -> None:
        passed = len(self.rows) - self.failed
        colour = GREEN if self.failed == 0 else RED
        print(f"\n{BOLD}{colour}{passed}/{len(self.rows)} checks passed{RESET}")
        for name, ok, detail in self.rows:
            if not ok:
                print(f"  {RED}✗{RESET} {name}: {detail}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


# ── Content agent ──────────────────────────────────────────────────────────

def verify_content(results: Results) -> None:
    import agent

    section(f"Content agent  ({agent.MODEL}, language={agent.LANGUAGE})")

    # Facebook: the platform whose contract was most broken before.
    start = time.time()
    posts = agent.generate_posts(HEADLINE, SUMMARY, "informative")
    elapsed = time.time() - start

    results.check("facebook returns 3 variations", len(posts) == 3, f"got {len(posts)}")
    if posts:
        for i, post in enumerate(posts, 1):
            words = len(post.split())
            results.check(
                f"facebook #{i} length is postable",
                25 <= words <= 130,
                f"{words} words",
            )
            results.check(
                f"facebook #{i} has 5 hashtags",
                post.count("#") == 5,
                f"{post.count('#')} found",
            )
            results.check(
                f"facebook #{i} keeps the PROMPT CTA",
                "PROMPT" in post,
            )
        hooks = {p.splitlines()[0][:45].lower() for p in posts if p.strip()}
        results.check(
            "facebook variations have distinct hooks",
            len(hooks) == len(posts),
            f"{len(hooks)} unique of {len(posts)}",
        )
        joined = " ".join(posts).lower()
        hits = [phrase for phrase in BANNED if phrase in joined]
        results.check("no banned filler phrases", not hits, ", ".join(hits))

        # The check the first version of this script was missing: does the
        # CONTENT_LANGUAGE setting actually control the output language?
        for i, post in enumerate(posts, 1):
            score = agent.roman_urdu_score(post)
            if agent.LANGUAGE == "english":
                results.check(
                    f"facebook #{i} body is English",
                    score <= 2,
                    f"{score} Roman Urdu markers outside the fixed CTA lines",
                )
            else:
                results.check(
                    f"facebook #{i} body is Hinglish",
                    score >= 3,
                    f"only {score} Roman Urdu markers",
                )
    print(f"  {DIM}{elapsed:.1f}s{RESET}")

    # Tweets: the hard character ceiling.
    tweets = agent.generate_tweet(HEADLINE, SUMMARY, "breaking")
    results.check("tweet returns 3 variations", len(tweets) == 3, f"got {len(tweets)}")
    for i, tweet in enumerate(tweets, 1):
        results.check(f"tweet #{i} under 280 chars", len(tweet) <= 280, f"{len(tweet)} chars")

    # Thread: exactly six parts, each a valid tweet.
    thread = agent.generate_thread(HEADLINE, SUMMARY, "thought")
    results.check("thread returns 6 tweets", len(thread) == 6, f"got {len(thread)}")
    over = [i for i, t in enumerate(thread, 1) if len(t) > 280]
    results.check("every thread tweet under 280 chars", not over, f"over: {over}")

    print(f"\n{DIM}sample facebook post:{RESET}")
    if posts:
        for line in posts[0].splitlines():
            print(f"  {DIM}│{RESET} {line}")


# ── Agentic developer ──────────────────────────────────────────────────────

def verify_agent(results: Results) -> None:
    import anthropic

    from agentic_dev.config import Settings, load_system_prompt
    from agentic_dev.loop import AgenticDeveloper
    from agentic_dev.tools import ToolContext

    settings = Settings.from_env()
    section(f"Agentic developer  ({settings.model})")

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        (workspace / "totals.py").write_text(
            "def add(a, b):\n"
            "    return a - b  # deliberate bug for the agent to find\n"
        )

        events: list[tuple[str, str]] = []
        agent_obj = AgenticDeveloper(
            client=anthropic.Anthropic(),
            system_prompt=load_system_prompt(settings.prompt_path),
            tool_context=ToolContext(
                workspace=workspace,
                approve=lambda action, detail: False,  # deny everything
            ),
            model=settings.model,
            max_tokens=2000,
            max_turns=8,
            on_event=lambda e, d: events.append((e, d)),
        )

        start = time.time()
        result = agent_obj.run(
            "Read totals.py and tell me in one sentence whether add() is correct. "
            "Do not change any files."
        )
        elapsed = time.time() - start

    tool_events = [d for e, d in events if e == "tool"]
    results.check("agent used at least one tool", bool(tool_events), f"{len(tool_events)} calls")
    results.check("agent read the file", any("read_file" in d for d in tool_events))
    results.check("agent finished within the turn limit", not result.stopped_early,
                  f"{result.turns} turns")
    results.check("agent produced an answer", bool(result.text.strip()))
    results.check(
        "agent spotted the bug",
        any(word in result.text.lower() for word in ("incorrect", "bug", "subtract", "wrong", "not correct")),
        result.text[:90],
    )
    print(f"  {DIM}{elapsed:.1f}s, {result.turns} turns, {result.tool_calls} tool calls{RESET}")
    print(f"\n{DIM}agent said:{RESET}\n  {DIM}│{RESET} {result.text[:300]}")


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", action="store_true", help="Content agent only.")
    parser.add_argument("--agent", action="store_true", help="Agentic developer only.")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        print(f"{RED}ANTHROPIC_API_KEY is not set.{RESET}", file=sys.stderr)
        print("Set it in your environment, then re-run.", file=sys.stderr)
        return 1

    run_content = args.content or not args.agent
    run_agent = args.agent or not args.content

    print(f"{BOLD}Live verification{RESET} {DIM}— this spends real tokens{RESET}")
    results = Results()

    if run_content:
        try:
            verify_content(results)
        except Exception as exc:
            results.check("content agent ran without raising", False, f"{type(exc).__name__}: {exc}")

    if run_agent:
        try:
            verify_agent(results)
        except Exception as exc:
            results.check("agentic developer ran without raising", False, f"{type(exc).__name__}: {exc}")

    results.summary()

    if run_content:
        try:
            import agent as content_agent
            usage = content_agent.usage_summary()
            print(
                f"\n{DIM}content agent spend: {usage['calls']} calls, "
                f"{usage['input_tokens']} in / {usage['output_tokens']} out, "
                f"${usage['cost_usd']:.4f}{RESET}"
            )
        except Exception:
            pass

    return 1 if results.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
