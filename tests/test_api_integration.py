"""End-to-end API tests against the real FastAPI app.

agent.py was rewritten underneath main.py and the frontend. These tests
exercise every endpoint the browser actually calls and assert the exact JSON
keys frontend/index.html reads, so a backend rewrite cannot silently break
the dashboard.

The Anthropic client is stubbed, so no API key or network is needed.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from typing import Any

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

try:
    from fastapi.testclient import TestClient

    import agent
    import main
except ImportError as exc:  # the web stack is optional for content-only work
    raise unittest.SkipTest(f"web dependencies not installed ({exc}); "
                            "run: pip install fastapi httpx feedparser") from exc


class FakeBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeUsage:
    input_tokens = 100
    output_tokens = 50


class FakeMessage:
    def __init__(self, text: str) -> None:
        self.content = [FakeBlock(text)]
        self.usage = FakeUsage()


class FakeMessages:
    """Returns a canned response shaped for whichever delimiter was asked for."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeMessage:
        self.calls.append(kwargs)
        user = kwargs["messages"][0]["content"]

        if "---XTWEET---" in kwargs.get("system", ""):
            return FakeMessage(
                "HOOK: Result first\nHASHTAGS: #AI\nCTA: Comment\nSTYLE: Punchy\n"
                "---XTWEET---\nThe rewritten tweet.\n"
                "---FACEBOOK---\nThe rewritten Facebook post."
            )
        for delimiter in ("---SCRIPT---", "---VIDEO---", "---IDEA---", "---TWEET---", "---POST---"):
            if delimiter in user:
                return FakeMessage(f"\n{delimiter}\n".join(f"Generated part {i}" for i in range(1, 8)))
        return FakeMessage("A single generated tweet.")


class FakeClient:
    def __init__(self) -> None:
        self.messages = FakeMessages()


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._real_client = agent.client
        agent.client = FakeClient()
        agent.USAGE_LOG.clear()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        agent.client = self._real_client


GENERATE_ENDPOINTS = [
    "/generate", "/generate/tweet", "/generate/thread", "/generate/linkedin",
    "/generate/instagram", "/generate/tiktok", "/generate/youtube",
    "/generate/youtube-video", "/generate/reel-script",
]


class TestGenerateEndpoints(ApiTestCase):
    def test_every_endpoint_returns_a_posts_list(self) -> None:
        """The frontend reads `.posts` on all nine — this is the contract."""
        for endpoint in GENERATE_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    endpoint,
                    json={"headline": "A headline", "summary": "A summary", "tone": "informative"},
                )
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertIn("posts", body)
                self.assertIsInstance(body["posts"], list)
                self.assertTrue(body["posts"], "empty posts list would render a blank UI")
                for post in body["posts"]:
                    self.assertIsInstance(post, str)

    def test_thread_returns_six_parts(self) -> None:
        response = self.client.post("/generate/thread", json={"headline": "H", "summary": "S"})
        self.assertEqual(len(response.json()["posts"]), 6)

    def test_facebook_returns_three_variations(self) -> None:
        response = self.client.post("/generate", json={"headline": "H", "summary": "S"})
        self.assertEqual(len(response.json()["posts"]), 3)

    def test_missing_headline_is_rejected(self) -> None:
        response = self.client.post("/generate", json={"headline": "  "})
        self.assertEqual(response.status_code, 400)

    def test_invalid_tone_is_rejected(self) -> None:
        response = self.client.post("/generate", json={"headline": "H", "tone": "sarcastic"})
        self.assertEqual(response.status_code, 400)

    def test_summary_is_optional(self) -> None:
        response = self.client.post("/generate", json={"headline": "H"})
        self.assertEqual(response.status_code, 200)


class TestRewriteEndpoint(ApiTestCase):
    def test_returns_the_three_keys_the_frontend_reads(self) -> None:
        response = self.client.post(
            "/rewrite",
            json={"text": "A viral post.", "author": "someone", "likes": 900, "reposts": 120},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        for key in ("analysis", "x_tweet", "facebook"):
            self.assertIn(key, body)
        self.assertEqual(body["x_tweet"], "The rewritten tweet.")
        self.assertEqual(body["facebook"], "The rewritten Facebook post.")

    def test_analysis_carries_all_four_fields(self) -> None:
        response = self.client.post("/rewrite", json={"text": "A viral post."})
        analysis = response.json()["analysis"]
        for field in ("hook", "hashtags", "cta", "style"):
            self.assertIn(field, analysis)

    def test_empty_text_is_rejected(self) -> None:
        self.assertEqual(self.client.post("/rewrite", json={"text": "   "}).status_code, 400)


class TestUsageTracking(ApiTestCase):
    def test_generation_records_spend(self) -> None:
        self.client.post("/generate", json={"headline": "H", "summary": "S"})
        summary = agent.usage_summary()
        self.assertGreater(summary["calls"], 0)
        self.assertGreater(summary["input_tokens"], 0)


class TestStaticFrontend(ApiTestCase):
    def test_dashboard_is_served_at_root(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
