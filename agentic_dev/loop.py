"""The agent loop: model call -> tool use -> tool result -> repeat.

The Anthropic client is injected rather than constructed here, so the loop
can be tested end to end with a fake client and no API key.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .guardrails import redact
from .tools import TOOL_SCHEMAS, ToolContext, dispatch

# Called with (event_name, detail) so a UI can show progress. Never required.
EventFn = Callable[[str, str], None]

TRANSIENT_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})


class MessagesClient(Protocol):
    """The slice of the Anthropic client this loop actually uses."""

    def create(self, **kwargs: Any) -> Any: ...


@dataclass
class RunResult:
    """Outcome of one :meth:`AgenticDeveloper.run` call."""

    text: str
    turns: int
    tool_calls: int
    stopped_early: bool = False


@dataclass
class AgenticDeveloper:
    """Runs the master prompt as a tool-using agent."""

    client: Any                # anything exposing .messages.create(**kwargs)
    system_prompt: str
    tool_context: ToolContext
    model: str
    max_tokens: int = 8_000
    max_turns: int = 40
    on_event: EventFn | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)

    def _emit(self, event: str, detail: str = "") -> None:
        if self.on_event is not None:
            self.on_event(event, redact(detail))

    def run(self, user_message: str) -> RunResult:
        """Send *user_message* and work until the model stops needing tools.

        Conversation state persists on the instance, so successive calls
        continue the same session.
        """
        self.messages.append({"role": "user", "content": user_message})

        tool_calls = 0
        for turn in range(1, self.max_turns + 1):
            response = self._create_with_retry()
            blocks = list(response.content)
            self.messages.append({"role": "assistant", "content": _to_params(blocks)})

            for block in blocks:
                if getattr(block, "type", None) == "text":
                    self._emit("text", block.text)

            if getattr(response, "stop_reason", None) != "tool_use":
                return RunResult(text=_text_of(blocks), turns=turn, tool_calls=tool_calls)

            results: list[dict[str, Any]] = []
            for block in blocks:
                if getattr(block, "type", None) != "tool_use":
                    continue
                tool_calls += 1
                self._emit("tool", f"{block.name} {block.input}")
                outcome = dispatch(block.name, dict(block.input), self.tool_context)
                self._emit("tool_result", outcome.content[:400])
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": outcome.content,
                    "is_error": outcome.is_error,
                })

            self.messages.append({"role": "user", "content": results})

        self._emit("limit", f"stopped after {self.max_turns} turns")
        return RunResult(
            text=f"Stopped after {self.max_turns} turns without finishing.",
            turns=self.max_turns,
            tool_calls=tool_calls,
            stopped_early=True,
        )

    def _create_with_retry(self, attempts: int = 3) -> Any:
        """Call the model, retrying transient failures with exponential backoff."""
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                return self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt,
                    tools=TOOL_SCHEMAS,
                    messages=self.messages,
                )
            except Exception as exc:
                if not _is_transient(exc) or attempt == attempts - 1:
                    raise
                last = exc
                delay = 2 ** attempt
                self._emit("retry", f"{type(exc).__name__}, retrying in {delay}s")
                time.sleep(delay)
        raise RuntimeError("unreachable") from last


def _is_transient(exc: Exception) -> bool:
    """True for errors worth retrying: rate limits, 5xx, connection drops."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status in TRANSIENT_STATUS
    return type(exc).__name__ in {"APIConnectionError", "APITimeoutError"}


def _to_params(blocks: list[Any]) -> list[dict[str, Any]]:
    """Convert response blocks to plain dicts for the next request."""
    params: list[dict[str, Any]] = []
    for block in blocks:
        kind = getattr(block, "type", None)
        if kind == "text":
            params.append({"type": "text", "text": block.text})
        elif kind == "tool_use":
            params.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": dict(block.input),
            })
    return params


def _text_of(blocks: list[Any]) -> str:
    """Join the text blocks of a response."""
    return "\n".join(b.text for b in blocks if getattr(b, "type", None) == "text").strip()
