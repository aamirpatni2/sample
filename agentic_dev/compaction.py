"""Context compaction.

Conversation history grows without bound; long sessions eventually exceed the
model's context window. This trims the oldest turns structurally — no model
call, no summarisation, fully deterministic.

The constraint that makes this non-trivial: a ``tool_result`` block is only
valid if the ``tool_use`` it answers is still in the history. Trimming that
splits a pair produces a request the API rejects, so the window boundary is
always moved to a safe position rather than cut where the budget happens to
land.
"""

from __future__ import annotations

from typing import Any

# Rough chars-per-token for English + code. Deliberately conservative: it is
# better to compact slightly early than to overflow the window.
CHARS_PER_TOKEN = 3.5

TRIM_NOTE = (
    "\n\n[Note: {count} earlier messages were trimmed to fit the context window. "
    "Re-read any file you need rather than relying on memory of it.]"
)


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Approximate the token cost of a message list.

    A heuristic, not a tokeniser — used only to decide *when* to compact.
    """
    total = 0
    for message in messages:
        content = message.get("content", "")
        total += len(content) if isinstance(content, str) else len(str(content))
    return int(total / CHARS_PER_TOKEN)


def compact(
    messages: list[dict[str, Any]],
    max_tokens: int,
    keep_recent: int = 8,
) -> tuple[list[dict[str, Any]], int]:
    """Trim history to fit *max_tokens*, returning (messages, trimmed_count).

    The original task (message 0) is always kept so the agent does not lose
    what it was asked to do. The retained window always begins on an assistant
    message, which guarantees two things: roles still alternate, and no
    ``tool_result`` is left without its ``tool_use``.

    Returns the input unchanged when it already fits or cannot be safely cut.
    """
    if estimate_tokens(messages) <= max_tokens or len(messages) <= keep_recent + 1:
        return messages, 0

    start = _safe_window_start(messages, len(messages) - keep_recent)
    if start is None:
        return messages, 0

    head = dict(messages[0])
    trimmed = start - 1
    if isinstance(head.get("content"), str):
        head["content"] = head["content"] + TRIM_NOTE.format(count=trimmed)

    return [head, *messages[start:]], trimmed


def _safe_window_start(messages: list[dict[str, Any]], desired: int) -> int | None:
    """Find the first index at or after *desired* that can safely start a window.

    A safe start is an assistant message after index 0. Searching forward
    rather than backward guarantees we never widen the window past the budget,
    and never begin on a user ``tool_result`` whose ``tool_use`` was dropped.
    """
    for index in range(max(desired, 1), len(messages)):
        if messages[index].get("role") == "assistant":
            return index
    return None
