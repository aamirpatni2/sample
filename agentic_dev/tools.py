"""Tool definitions and dispatch for the Agentic AI Developer.

Every tool runs behind the guardrails in :mod:`agentic_dev.guardrails`:
paths are confined to the workspace, commands are classified before they
run, and all output is redacted before it reaches the model or a log.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .guardrails import (
    GuardrailError,
    Risk,
    classify_command,
    redact,
    resolve_in_workspace,
)

# Approval callback: (action, detail) -> approved?
ApprovalFn = Callable[[str, str], bool]


@dataclass
class ToolContext:
    """Everything a tool needs to run, injected rather than imported."""

    workspace: Path
    approve: ApprovalFn
    command_timeout: int = 120
    max_output_chars: int = 20_000


@dataclass
class ToolResult:
    """Outcome of one tool call."""

    content: str
    is_error: bool = False


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file from the workspace. Returns the file with 1-indexed line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the workspace root."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write a UTF-8 text file in the workspace, creating parent directories as needed. "
            "Overwriting an existing file requires human approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the workspace root."},
                "content": {"type": "string", "description": "Full file content to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Replace an exact piece of text in an existing file. Prefer this over "
            "write_file for changes to a file that already exists: it touches only "
            "the named text, so the rest of the file cannot be lost. old_string must "
            "appear exactly once, and must include enough surrounding context to be "
            "unique."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the workspace root."},
                "old_string": {"type": "string", "description": "Exact text to replace, including indentation."},
                "new_string": {"type": "string", "description": "Replacement text. Empty string deletes."},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories under a workspace path, up to a depth of 3.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the workspace root. Defaults to the root."},
            },
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a shell command in the workspace. Read-only commands run immediately; "
            "commands that change state require human approval; destructive commands are refused."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."},
                "purpose": {"type": "string", "description": "One line on why this command is needed."},
            },
            "required": ["command"],
        },
    },
]


def dispatch(name: str, tool_input: dict[str, Any], ctx: ToolContext) -> ToolResult:
    """Route a tool call to its implementation and normalise failures.

    Guardrail violations and runtime errors both come back as ToolResult with
    ``is_error=True`` so the model can see and recover from them, rather than
    crashing the loop.
    """
    handler = _HANDLERS.get(name)
    if handler is None:
        return ToolResult(f"Unknown tool: {name!r}", is_error=True)
    try:
        return handler(tool_input, ctx)
    except GuardrailError as exc:
        return ToolResult(f"Refused by guardrail: {exc}", is_error=True)
    except Exception as exc:  # surfaced to the model, never swallowed
        return ToolResult(f"{type(exc).__name__}: {redact(str(exc))}", is_error=True)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, {len(text) - limit} more characters]"


def _read_file(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    path = resolve_in_workspace(ctx.workspace, args["path"])
    if not path.is_file():
        return ToolResult(f"Not a file: {args['path']}", is_error=True)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    numbered = "\n".join(f"{i:>5}\t{line}" for i, line in enumerate(lines, 1))
    return ToolResult(_truncate(redact(numbered), ctx.max_output_chars))


def _write_file(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    path = resolve_in_workspace(ctx.workspace, args["path"])
    content = args["content"]

    if path.exists():
        if not ctx.approve("overwrite file", str(path.relative_to(ctx.workspace.resolve()))):
            return ToolResult("Human declined the overwrite. File unchanged.", is_error=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return ToolResult(f"Wrote {len(content)} characters to {args['path']}")


def _edit_file(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    path = resolve_in_workspace(ctx.workspace, args["path"])
    old, new = args["old_string"], args["new_string"]

    if not path.is_file():
        return ToolResult(f"Not a file: {args['path']}", is_error=True)
    if old == new:
        return ToolResult("old_string and new_string are identical.", is_error=True)
    if not old:
        return ToolResult("old_string is empty; use write_file to create a file.", is_error=True)

    content = path.read_text(encoding="utf-8")
    occurrences = content.count(old)
    if occurrences == 0:
        return ToolResult(
            "old_string not found. It must match the file exactly, including "
            "whitespace and indentation. Read the file again before retrying.",
            is_error=True,
        )
    if occurrences > 1:
        # Editing the wrong one of several matches corrupts working code
        # silently, so ambiguity is refused rather than guessed at.
        return ToolResult(
            f"old_string appears {occurrences} times. Include more surrounding "
            "context so it matches exactly one place.",
            is_error=True,
        )

    path.write_text(content.replace(old, new), encoding="utf-8")
    delta = len(new) - len(old)
    return ToolResult(
        f"Edited {args['path']} ({delta:+d} characters). "
        "Re-read the file if you need updated line numbers."
    )


def _list_files(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    root = resolve_in_workspace(ctx.workspace, args.get("path") or ".")
    if not root.is_dir():
        return ToolResult(f"Not a directory: {args.get('path', '.')}", is_error=True)

    base_depth = len(root.parts)
    entries: list[str] = []
    for item in sorted(root.rglob("*")):
        if any(part.startswith(".") or part == "__pycache__" for part in item.parts[base_depth:]):
            continue
        depth = len(item.parts) - base_depth
        if depth > 3:
            continue
        rel = item.relative_to(root)
        entries.append(f"{'  ' * (depth - 1)}{rel.name}{'/' if item.is_dir() else ''}")

    listing = "\n".join(entries) or "(empty)"
    return ToolResult(_truncate(listing, ctx.max_output_chars))


def _run_command(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    command = args["command"]
    purpose = args.get("purpose", "")
    verdict = classify_command(command)

    if verdict.risk is Risk.BLOCKED:
        return ToolResult(
            f"Refused: {verdict.reason}. This command is blocked and cannot be approved.",
            is_error=True,
        )

    if verdict.risk is Risk.NEEDS_APPROVAL:
        detail = f"{command}\n  reason: {verdict.reason}"
        if purpose:
            detail += f"\n  purpose: {purpose}"
        if not ctx.approve("run command", detail):
            return ToolResult("Human declined this command. Not run.", is_error=True)

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=ctx.workspace,
            capture_output=True,
            text=True,
            timeout=ctx.command_timeout,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(f"Command timed out after {ctx.command_timeout}s.", is_error=True)

    body = f"exit code: {completed.returncode}\n"
    if completed.stdout:
        body += f"--- stdout ---\n{completed.stdout}"
    if completed.stderr:
        body += f"--- stderr ---\n{completed.stderr}"
    return ToolResult(
        _truncate(redact(body), ctx.max_output_chars),
        is_error=completed.returncode != 0,
    )


_HANDLERS: dict[str, Callable[[dict[str, Any], ToolContext], ToolResult]] = {
    "read_file": _read_file,
    "write_file": _write_file,
    "edit_file": _edit_file,
    "list_files": _list_files,
    "run_command": _run_command,
}
