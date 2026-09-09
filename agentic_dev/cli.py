"""Interactive CLI for the Agentic AI Developer.

Usage:
    python -m agentic_dev                     # interactive session in the cwd
    python -m agentic_dev --workspace ./proj  # scope the agent to a directory
    python -m agentic_dev "fix the failing test"   # one-shot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Settings, load_system_prompt, require_api_key
from .loop import AgenticDeveloper
from .runlog import JsonlRunLog, tee
from .tools import ToolContext

DIM = "\033[2m"
BOLD = "\033[1m"
YELLOW = "\033[33m"
RESET = "\033[0m"


class ApprovalPrompt:
    """Asks the human before a state-changing action. Default is no.

    Remembers "always" answers for the rest of the session, keyed on the exact
    command, so a repeated step (running the test suite) is approved once
    rather than every time.
    """

    def __init__(self) -> None:
        self.remembered: set[str] = set()

    def __call__(self, action: str, detail: str) -> bool:
        key = f"{action}:{detail.splitlines()[0] if detail else ''}"
        if key in self.remembered:
            print(f"{DIM}  (already approved this session){RESET}")
            return True

        print(f"\n{YELLOW}{BOLD}Approval needed:{RESET} {action}")
        for line in detail.splitlines():
            print(f"  {line}")
        try:
            answer = input(f"{YELLOW}Allow? [y]es / [a]lways / [N]o {RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False

        if answer in {"a", "always"}:
            self.remembered.add(key)
            return True
        return answer in {"y", "yes"}


def print_event(event: str, detail: str) -> None:
    """Render loop progress. Text blocks print in full; the rest is dimmed."""
    if event == "text":
        print(detail)
    elif event == "tool":
        print(f"{DIM}  → {detail[:200]}{RESET}")
    elif event == "tool_result":
        first = detail.splitlines()[0] if detail else ""
        print(f"{DIM}  ← {first[:200]}{RESET}")
    elif event in {"retry", "limit"}:
        print(f"{YELLOW}  ! {detail}{RESET}")


def build_agent(settings: Settings, log_path: Path | None = None) -> AgenticDeveloper:
    """Wire up the agent from settings. Requires the API key to be set."""
    import anthropic  # imported here so --help works without the SDK installed

    client = anthropic.Anthropic(api_key=require_api_key())
    handler = print_event
    if log_path is not None:
        handler = tee(print_event, JsonlRunLog(log_path))
    context = ToolContext(
        workspace=settings.workspace,
        approve=ApprovalPrompt(),
        command_timeout=settings.command_timeout,
    )
    return AgenticDeveloper(
        client=client,
        system_prompt=load_system_prompt(settings.prompt_path),
        tool_context=context,
        model=settings.model,
        max_tokens=settings.max_tokens,
        max_turns=settings.max_turns,
        context_budget=settings.context_budget,
        on_event=handler,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentic_dev", description=__doc__)
    parser.add_argument("task", nargs="*", help="Task to run. Omit for an interactive session.")
    parser.add_argument("--workspace", type=Path, default=None, help="Directory the agent may touch.")
    parser.add_argument("--model", default=None, help="Override the model id.")
    parser.add_argument("--log", type=Path, default=None, help="Write a JSONL run log to this path.")
    args = parser.parse_args(argv)

    settings = Settings.from_env(workspace=args.workspace)
    if args.model:
        settings.model = args.model

    try:
        agent = build_agent(settings, log_path=args.log)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        return 1

    print(f"{BOLD}Agentic AI Developer{RESET} {DIM}· {settings.model} · {settings.workspace}{RESET}")

    if args.task:
        agent.run(" ".join(args.task))
        return 0

    print(f"{DIM}Type a task, or Ctrl-D to exit.{RESET}")
    while True:
        try:
            message = input(f"\n{BOLD}you ›{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message:
            continue
        if message in {"exit", "quit"}:
            return 0
        try:
            agent.run(message)
        except Exception as exc:  # keep the session alive on API failures
            print(f"{YELLOW}Run failed: {type(exc).__name__}: {exc}{RESET}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
