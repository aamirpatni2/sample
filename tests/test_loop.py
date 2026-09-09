"""Agent loop tests driven by a fake client. No API key or network required."""

from __future__ import annotations

import sys
import copy
import tempfile
import unittest
import unittest.mock
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentic_dev.loop import AgenticDeveloper  # noqa: E402
from agentic_dev.tools import ToolContext  # noqa: E402


# ── Fakes ──────────────────────────────────────────────────────────────────

@dataclass
class FakeText:
    text: str
    type: str = "text"


@dataclass
class FakeToolUse:
    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class FakeResponse:
    content: list[Any]
    stop_reason: str


class FakeMessages:
    """Replays a scripted list of responses and records every request."""

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        # Snapshot the payload: the loop mutates its message list in place,
        # and the real SDK serialises at call time.
        self.requests.append(copy.deepcopy(kwargs))
        if not self._script:
            raise AssertionError("fake client ran out of scripted responses")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, script: list[Any]) -> None:
        self.messages = FakeMessages(script)


class TransientError(Exception):
    status_code = 429


class FatalError(Exception):
    status_code = 400


# ── Tests ──────────────────────────────────────────────────────────────────

class LoopTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "app.py").write_text("print('hi')\n")
        self.ctx = ToolContext(workspace=self.root, approve=lambda a, d: True, command_timeout=10)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def build(self, script: list[Any], **kw: Any) -> AgenticDeveloper:
        self.client = FakeClient(script)
        return AgenticDeveloper(
            client=self.client,
            system_prompt="test prompt",
            tool_context=self.ctx,
            model="test-model",
            **kw,
        )


class TestPlainReply(LoopTestCase):
    def test_returns_text_without_tools(self) -> None:
        agent = self.build([FakeResponse([FakeText("Hello.")], "end_turn")])
        result = agent.run("hi")
        self.assertEqual(result.text, "Hello.")
        self.assertEqual(result.turns, 1)
        self.assertEqual(result.tool_calls, 0)
        self.assertFalse(result.stopped_early)

    def test_sends_system_prompt_and_tools(self) -> None:
        agent = self.build([FakeResponse([FakeText("ok")], "end_turn")])
        agent.run("hi")
        request = self.client.messages.requests[0]
        self.assertEqual(request["system"], "test prompt")
        self.assertTrue(any(t["name"] == "read_file" for t in request["tools"]))


class TestToolUse(LoopTestCase):
    def test_executes_tool_then_returns_final_text(self) -> None:
        agent = self.build([
            FakeResponse([FakeToolUse("t1", "read_file", {"path": "app.py"})], "tool_use"),
            FakeResponse([FakeText("The file prints hi.")], "end_turn"),
        ])
        result = agent.run("what does app.py do?")
        self.assertEqual(result.text, "The file prints hi.")
        self.assertEqual(result.tool_calls, 1)

        # The tool result must be fed back as a user turn the model can read.
        second_request = self.client.messages.requests[1]
        tool_result = second_request["messages"][-1]["content"][0]
        self.assertEqual(tool_result["type"], "tool_result")
        self.assertEqual(tool_result["tool_use_id"], "t1")
        self.assertIn("print('hi')", tool_result["content"])
        self.assertFalse(tool_result["is_error"])

    def test_tool_failure_is_reported_not_raised(self) -> None:
        agent = self.build([
            FakeResponse([FakeToolUse("t1", "read_file", {"path": "../../etc/passwd"})], "tool_use"),
            FakeResponse([FakeText("I cannot read outside the workspace.")], "end_turn"),
        ])
        result = agent.run("read /etc/passwd")
        tool_result = self.client.messages.requests[1]["messages"][-1]["content"][0]
        self.assertTrue(tool_result["is_error"])
        self.assertIn("guardrail", tool_result["content"].lower())
        self.assertIn("cannot read", result.text)

    def test_handles_several_tool_calls_in_one_turn(self) -> None:
        agent = self.build([
            FakeResponse(
                [
                    FakeToolUse("t1", "read_file", {"path": "app.py"}),
                    FakeToolUse("t2", "list_files", {}),
                ],
                "tool_use",
            ),
            FakeResponse([FakeText("done")], "end_turn"),
        ])
        result = agent.run("look around")
        self.assertEqual(result.tool_calls, 2)
        self.assertEqual(len(self.client.messages.requests[1]["messages"][-1]["content"]), 2)


class TestLimitsAndErrors(LoopTestCase):
    def test_stops_at_max_turns(self) -> None:
        looping = [
            FakeResponse([FakeToolUse(f"t{i}", "list_files", {})], "tool_use")
            for i in range(10)
        ]
        agent = self.build(looping, max_turns=3)
        result = agent.run("loop forever")
        self.assertTrue(result.stopped_early)
        self.assertEqual(result.turns, 3)

    def test_retries_transient_error(self) -> None:
        agent = self.build([
            TransientError("rate limited"),
            FakeResponse([FakeText("recovered")], "end_turn"),
        ])
        with unittest.mock.patch("agentic_dev.loop.time.sleep"):
            result = agent.run("hi")
        self.assertEqual(result.text, "recovered")
        self.assertEqual(len(self.client.messages.requests), 2)

    def test_does_not_retry_fatal_error(self) -> None:
        agent = self.build([FatalError("bad request")])
        with self.assertRaises(FatalError):
            agent.run("hi")
        self.assertEqual(len(self.client.messages.requests), 1)


class TestConversationState(LoopTestCase):
    def test_second_run_keeps_history(self) -> None:
        agent = self.build([
            FakeResponse([FakeText("first")], "end_turn"),
            FakeResponse([FakeText("second")], "end_turn"),
        ])
        agent.run("one")
        agent.run("two")
        sent = self.client.messages.requests[1]["messages"]
        self.assertEqual(sent[0]["content"], "one")
        self.assertEqual(sent[-1]["content"], "two")


class TestCompactionInLoop(LoopTestCase):
    def test_long_history_is_compacted_before_the_call(self) -> None:
        agent = self.build(
            [FakeResponse([FakeText("ok")], "end_turn")],
            context_budget=50,
            keep_recent=2,
        )
        agent.messages = [
            {"role": "user", "content": "original task " + "x" * 4000},
            {"role": "assistant", "content": [{"type": "text", "text": "y" * 4000}]},
            {"role": "user", "content": "z" * 4000},
            {"role": "assistant", "content": [{"type": "text", "text": "w" * 4000}]},
        ]
        events: list[str] = []
        agent.on_event = lambda e, d: events.append(e)
        agent.run("next")
        sent = self.client.messages.requests[0]["messages"]
        self.assertIn("compact", events)
        self.assertLess(len(sent), 5)
        self.assertTrue(sent[0]["content"].startswith("original task"))


class TestEvents(LoopTestCase):
    def test_events_are_redacted(self) -> None:
        seen: list[tuple[str, str]] = []
        agent = self.build(
            [FakeResponse([FakeText("key is sk-ant-api03-supersecretvalue99")], "end_turn")],
            on_event=lambda e, d: seen.append((e, d)),
        )
        agent.run("hi")
        joined = " ".join(d for _, d in seen)
        self.assertNotIn("supersecretvalue99", joined)


if __name__ == "__main__":
    unittest.main()
