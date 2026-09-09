"""Dashboard server tests. No API key or network required."""

from __future__ import annotations

import asyncio
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from fastapi.testclient import TestClient

    from agentic_dev import server
except ImportError as exc:
    raise unittest.SkipTest(f"web dependencies not installed ({exc}); "
                            "run: pip install fastapi uvicorn httpx") from exc


class TestPages(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(server.app)

    def test_dashboard_is_served(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Agentic AI Developer", response.text)

    def test_config_exposes_no_secrets(self) -> None:
        body = self.client.get("/api/config").json()
        self.assertIn("model", body)
        self.assertIn("workspace", body)
        joined = " ".join(str(v) for v in body.values()).lower()
        for leaked in ("sk-ant", "api_key", "token"):
            self.assertNotIn(leaked, joined)


class TestBridge(unittest.TestCase):
    """The thread boundary is the only tricky part of this server."""

    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.sent: list[dict] = []

        class FakeSocket:
            async def send_json(inner, payload: dict) -> None:
                self.sent.append(payload)

        self.bridge = server.Bridge(self.loop, FakeSocket())
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)
        self.loop.close()

    def test_events_reach_the_browser(self) -> None:
        self.bridge.on_event("tool", "read_file app.py")
        self.assertEqual(self.sent[-1]["event"], "tool")
        self.assertEqual(self.sent[-1]["detail"], "read_file app.py")

    def test_approval_blocks_until_answered(self) -> None:
        """The worker thread must wait for the human, not race past them."""
        outcome: list[bool] = []

        worker = threading.Thread(
            target=lambda: outcome.append(self.bridge.approve("run command", "rm old.py"))
        )
        worker.start()
        worker.join(timeout=0.3)
        self.assertTrue(worker.is_alive(), "approve() returned without an answer")
        self.assertEqual(self.sent[-1]["type"], "approval_request")

        self.bridge.answer_approval(True)
        worker.join(timeout=3)
        self.assertEqual(outcome, [True])

    def test_denial_is_delivered(self) -> None:
        outcome: list[bool] = []
        worker = threading.Thread(
            target=lambda: outcome.append(self.bridge.approve("run command", "rm -rf build"))
        )
        worker.start()
        self.bridge.answer_approval(False)
        worker.join(timeout=3)
        self.assertEqual(outcome, [False])

    def test_closed_socket_refuses_rather_than_hanging(self) -> None:
        """A disconnected browser must not leave a thread parked forever."""
        self.bridge.closed.set()
        self.assertFalse(self.bridge.approve("run command", "anything"))

    def test_approval_timeout_defaults_to_refusal(self) -> None:
        original = server.APPROVAL_TIMEOUT_SECONDS
        server.APPROVAL_TIMEOUT_SECONDS = 0.2
        try:
            self.assertFalse(self.bridge.approve("run command", "silent human"))
        finally:
            server.APPROVAL_TIMEOUT_SECONDS = original
        self.assertEqual(self.sent[-1]["event"], "limit")


if __name__ == "__main__":
    unittest.main()
