"""Web dashboard for the Agentic AI Developer.

    python -m agentic_dev.server --workspace ./my-project

The agent loop is synchronous and blocking, so it runs in a worker thread while
the event loop keeps the socket alive. Two things cross that boundary: progress
events pushed out to the browser, and approval answers coming back in. Both go
through Bridge, which is the only place the threading rules matter.
"""

from __future__ import annotations

import argparse
import asyncio
import queue
import threading
import webbrowser
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .config import Settings, load_system_prompt, require_api_key
from .loop import AgenticDeveloper
from .tools import ToolContext

DASHBOARD = Path(__file__).parent / "dashboard.html"

# How long a pending approval waits for a human before defaulting to refusal.
APPROVAL_TIMEOUT_SECONDS = 600

app = FastAPI(title="Agentic AI Developer")
settings = Settings.from_env()


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD)


@app.get("/api/config")
def config() -> dict[str, Any]:
    """What the browser needs to render its header. No secrets."""
    return {
        "model": settings.model,
        "workspace": str(settings.workspace),
        "max_turns": settings.max_turns,
    }


class Bridge:
    """Carries events out to the browser and approval answers back in.

    Every method here is called from the agent's worker thread except
    :meth:`answer_approval`, which is called from the event loop.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, websocket: WebSocket) -> None:
        self._loop = loop
        self._ws = websocket
        self._approvals: queue.Queue[bool] = queue.Queue()
        self.closed = threading.Event()

    def send(self, payload: dict[str, Any]) -> None:
        """Push one message to the browser from the worker thread."""
        if self.closed.is_set():
            return
        future = asyncio.run_coroutine_threadsafe(self._ws.send_json(payload), self._loop)
        try:
            future.result(timeout=10)
        except Exception:
            self.closed.set()

    def on_event(self, event: str, detail: str) -> None:
        self.send({"type": "event", "event": event, "detail": detail})

    def approve(self, action: str, detail: str) -> bool:
        """Ask the browser and block this thread until it answers.

        A closed socket or a silent human both mean refusal — the safe default
        is never to act.
        """
        if self.closed.is_set():
            return False
        self.send({"type": "approval_request", "action": action, "detail": detail})
        try:
            return self._approvals.get(timeout=APPROVAL_TIMEOUT_SECONDS)
        except queue.Empty:
            self.send({"type": "event", "event": "limit", "detail": "approval timed out; refused"})
            return False

    def answer_approval(self, allow: bool) -> None:
        """Deliver the human's answer. Called from the event loop."""
        self._approvals.put(allow)


def build_agent(bridge: Bridge) -> AgenticDeveloper:
    import anthropic

    return AgenticDeveloper(
        client=anthropic.Anthropic(api_key=require_api_key()),
        system_prompt=load_system_prompt(settings.prompt_path),
        tool_context=ToolContext(
            workspace=settings.workspace,
            approve=bridge.approve,
            command_timeout=settings.command_timeout,
        ),
        model=settings.model,
        max_tokens=settings.max_tokens,
        max_turns=settings.max_turns,
        context_budget=settings.context_budget,
        on_event=bridge.on_event,
    )


@app.websocket("/ws")
async def agent_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    loop = asyncio.get_running_loop()
    bridge = Bridge(loop, websocket)

    try:
        agent = build_agent(bridge)
    except (RuntimeError, FileNotFoundError) as exc:
        await websocket.send_json({"type": "fatal", "detail": str(exc)})
        await websocket.close()
        return

    running: asyncio.Future[Any] | None = None

    try:
        while True:
            message = await websocket.receive_json()
            kind = message.get("type")

            if kind == "approval":
                # Answers arrive while a task is mid-flight; hand them to the
                # blocked worker thread rather than treating them as new work.
                bridge.answer_approval(bool(message.get("allow")))
                continue

            if kind != "task":
                continue
            if running is not None and not running.done():
                await websocket.send_json(
                    {"type": "event", "event": "limit", "detail": "a task is already running"}
                )
                continue

            text = (message.get("text") or "").strip()
            if not text:
                continue

            await websocket.send_json({"type": "started"})
            running = loop.run_in_executor(None, agent.run, text)
            running.add_done_callback(
                lambda fut: asyncio.run_coroutine_threadsafe(_finish(websocket, fut), loop)
            )
    except WebSocketDisconnect:
        bridge.closed.set()
        # Release a worker thread parked on an approval that will never come.
        bridge.answer_approval(False)


async def _finish(websocket: WebSocket, future: Any) -> None:
    """Report a completed run, or the exception that ended it."""
    try:
        result = future.result()
    except Exception as exc:
        payload = {"type": "error", "detail": f"{type(exc).__name__}: {exc}"}
    else:
        payload = {
            "type": "done",
            "text": result.text,
            "turns": result.turns,
            "tool_calls": result.tool_calls,
            "stopped_early": result.stopped_early,
        }
    try:
        await websocket.send_json(payload)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Agentic AI Developer dashboard.")
    parser.add_argument("--workspace", type=Path, default=None, help="Directory the agent may touch.")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--model", default=None, help="Override the model id.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser.")
    args = parser.parse_args(argv)

    global settings
    settings = Settings.from_env(workspace=args.workspace)
    if args.model:
        settings.model = args.model

    import uvicorn

    url = f"http://127.0.0.1:{args.port}"
    print(f"Agentic AI Developer  ·  {settings.model}")
    print(f"Workspace: {settings.workspace}")
    print(f"Dashboard: {url}\n")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
