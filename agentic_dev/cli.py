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
from .tools import ToolContext

DIM = "\033[2m"
BOLD = "\033[1m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def prompt_for_approval(action: str, detail: str) -> bool:
    """Ask the human before a state-changing action. Default is no."""
    print(f"\n{YELLOW}{BOLD}Approval needed:{RESET} {action}")
    for line in detail.splitlines():
        print(f"  {line}")
    try:
        answer = input(f"{YELLOW}Allow? [y/N] {RESET}").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
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


def build_agent(settings: Settings) -> AgenticDeveloper:
    """Wire up the agent from settings. Requires the API key to be set."""
    import anthropic  # imported here so --help works without the SDK installed

    client = anthropic.Anthropic(api_key=require_api_key())
    context = ToolContext(
        workspace=settings.workspace,
        approve=prompt_for_approval,
        command_timeout=settings.command_timeout,
    )
    return AgenticDeveloper(
        client=client,
        system_prompt=load_system_prompt(settings.prompt_path),
        tool_context=context,
        model=settings.model,
        max_tokens=settings.max_tokens,
        max_turns=settings.max_turns,
        on_event=print_event,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentic_dev", description=__doc__)
    parser.add_argument("task", nargs="*", help="Task to run. Omit for an interactive session.")
    parser.add_argument("--workspace", type=Path, default=None, help="Directory the agent may touch.")
    parser.add_argument("--model", default=None, help="Override the model id.")
    args = parser.parse_args(argv)

    settings = Settings.from_env(workspace=args.workspace)
    if args.model:
        settings.model = args.model

    try:
        agent = build_agent(settings)
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
