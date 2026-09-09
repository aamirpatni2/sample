"""Guardrails for the Agentic AI Developer.

Enforced in code, never by prompting alone. Covers the three control surfaces
from the master prompt (section 10): filesystem scope, command permissions,
and secret leakage.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class GuardrailError(Exception):
    """Raised when an action violates a guardrail and must not proceed."""


class Risk(str, Enum):
    """How a command may be executed."""

    SAFE = "safe"                    # read-only, run without asking
    NEEDS_APPROVAL = "needs_approval"  # mutates state, ask the human first
    BLOCKED = "blocked"             # never run, no approval available


# ── Filesystem scope ───────────────────────────────────────────────────────

def resolve_in_workspace(workspace: Path, candidate: str) -> Path:
    """Resolve *candidate* inside *workspace*, or raise GuardrailError.

    Blocks absolute paths outside the workspace, ``..`` traversal, and
    symlinks pointing out of the tree. Resolution is done on the fully
    resolved real path so a symlink cannot be used to escape.
    """
    root = workspace.resolve()
    target = (root / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate).resolve()

    if target != root and root not in target.parents:
        raise GuardrailError(
            f"path escapes workspace: {candidate!r} resolves outside {root}"
        )
    return target


# ── Command permissions ────────────────────────────────────────────────────

# Read-only binaries safe to run unattended.
_SAFE_BINARIES = frozenset({
    "ls", "cat", "head", "tail", "wc", "grep", "rg", "find", "file", "stat",
    "pwd", "echo", "which", "tree", "diff", "sort", "uniq", "cut", "sed",
    "awk", "date", "env", "python3", "python", "pytest", "node",
})

# Read-only git subcommands. Anything else under git needs approval.
_SAFE_GIT = frozenset({"status", "diff", "log", "show", "branch", "remote", "ls-files"})

# Patterns that are never run, with or without approval.
_BLOCKED_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brm\s+(-\w+\s+)*-\w*[rf]\w*\s+/(\s|$)"), "recursive delete of /"),
    (re.compile(r"\b(mkfs|fdisk|dd)\b"), "disk-level operation"),
    (re.compile(r"\bcurl\b.*\|\s*(ba)?sh\b"), "piping a download into a shell"),
    (re.compile(r"\bwget\b.*\|\s*(ba)?sh\b"), "piping a download into a shell"),
    (re.compile(r"\bsudo\b"), "privilege escalation"),
    (re.compile(r"\bchmod\s+(-\w+\s+)*777\b"), "world-writable permissions"),
    (re.compile(r"\bgit\s+push\b.*--force(?!-with-lease)"), "force push"),
    (re.compile(r":\(\)\s*\{.*\}\s*;?\s*:"), "fork bomb"),
    (re.compile(r"\b(history|cat)\b.*\.(env|aws/credentials|ssh/id_)"), "reading a secret store"),
)

# Shell metacharacters that split a command line into several commands.
_CHAIN_SPLIT = re.compile(r"&&|\|\||[;|]")


@dataclass(frozen=True)
class CommandVerdict:
    """Result of classifying a shell command."""

    risk: Risk
    reason: str


def classify_command(command: str) -> CommandVerdict:
    """Classify a shell command as SAFE, NEEDS_APPROVAL, or BLOCKED.

    Chained commands take the risk of their most dangerous segment, so
    ``ls && rm -rf /`` is BLOCKED rather than SAFE. Anything unrecognised
    defaults to NEEDS_APPROVAL — the safe default is to ask.
    """
    text = command.strip()
    if not text:
        return CommandVerdict(Risk.BLOCKED, "empty command")

    for pattern, reason in _BLOCKED_PATTERNS:
        if pattern.search(text):
            return CommandVerdict(Risk.BLOCKED, reason)

    if "`" in text or "$(" in text:
        return CommandVerdict(Risk.NEEDS_APPROVAL, "command substitution")

    worst = Risk.SAFE
    reasons: list[str] = []
    for segment in _CHAIN_SPLIT.split(text):
        verdict = _classify_segment(segment)
        if verdict.risk is Risk.BLOCKED:
            return verdict
        if verdict.risk is Risk.NEEDS_APPROVAL:
            worst = Risk.NEEDS_APPROVAL
            reasons.append(verdict.reason)

    if worst is Risk.SAFE:
        return CommandVerdict(Risk.SAFE, "read-only command")
    return CommandVerdict(Risk.NEEDS_APPROVAL, "; ".join(dict.fromkeys(reasons)))


def _classify_segment(segment: str) -> CommandVerdict:
    """Classify one command in a chain."""
    segment = segment.strip()
    if not segment:
        return CommandVerdict(Risk.SAFE, "empty segment")

    try:
        parts = shlex.split(segment)
    except ValueError as exc:  # unbalanced quotes
        return CommandVerdict(Risk.NEEDS_APPROVAL, f"unparseable command ({exc})")
    if not parts:
        return CommandVerdict(Risk.SAFE, "empty segment")

    binary = Path(parts[0]).name

    if binary == "git":
        sub = parts[1] if len(parts) > 1 else ""
        if sub in _SAFE_GIT:
            return CommandVerdict(Risk.SAFE, "read-only git")
        return CommandVerdict(Risk.NEEDS_APPROVAL, f"git {sub} changes repository state")

    if binary in {"pip", "pip3", "npm", "yarn", "apt", "apt-get", "brew"}:
        return CommandVerdict(Risk.NEEDS_APPROVAL, f"{binary} installs software")

    if binary in {"rm", "mv", "cp", "mkdir", "touch", "chmod", "chown", "ln"}:
        return CommandVerdict(Risk.NEEDS_APPROVAL, f"{binary} modifies the filesystem")

    if binary in {"curl", "wget", "ssh", "scp", "rsync", "nc"}:
        return CommandVerdict(Risk.NEEDS_APPROVAL, f"{binary} touches the network")

    if binary in _SAFE_BINARIES:
        return CommandVerdict(Risk.SAFE, "read-only command")

    return CommandVerdict(Risk.NEEDS_APPROVAL, f"unrecognised command {binary!r}")


# ── Secret redaction ───────────────────────────────────────────────────────

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAAAAAAAAA[A-Za-z0-9%\-_]{20,}"),  # X/Twitter bearer
    re.compile(r"(?i)\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)\s*[=:]\s*\S+"),
)

REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    """Strip credential-shaped strings from text before it is logged or returned."""
    out = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            out = pattern.sub(lambda m: f"{m.group(1)}={REDACTED}", out)
        else:
            out = pattern.sub(REDACTED, out)
    return out
