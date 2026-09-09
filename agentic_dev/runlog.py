"""JSONL run logging.

One line per event, so a session can be replayed, diffed, or turned into
evaluation cases later. Every value passes through redaction first — a run log
is a file on disk and must never contain a credential.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .guardrails import redact


class JsonlRunLog:
    """Append-only event log. Plugs straight into ``AgenticDeveloper.on_event``.

    Logging is best-effort: a failure to write must never take down a run, so
    write errors are recorded on the instance rather than raised.
    """

    def __init__(self, path: Path, run_id: str | None = None) -> None:
        self.path = path
        self.run_id = run_id or time.strftime("%Y%m%dT%H%M%S")
        self.write_errors: list[str] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, event: str, detail: str) -> None:
        self.write(event, detail)

    def write(self, event: str, detail: str, **extra: Any) -> None:
        """Append one event. Never raises."""
        record = {
            "run_id": self.run_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "event": event,
            "detail": redact(detail),
            **{k: redact(v) if isinstance(v, str) else v for k, v in extra.items()},
        }
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            self.write_errors.append(str(exc))


def tee(*handlers: Any) -> Any:
    """Combine several event handlers into one, e.g. print plus log."""

    def emit(event: str, detail: str) -> None:
        for handler in handlers:
            if handler is not None:
                handler(event, detail)

    return emit
