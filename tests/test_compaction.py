"""Compaction tests. The critical property: never orphan a tool_result."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentic_dev.compaction import compact, estimate_tokens  # noqa: E402


def user(text: str) -> dict[str, Any]:
    return {"role": "user", "content": text}


def assistant_text(text: str) -> dict[str, Any]:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def assistant_tool(call_id: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": call_id, "name": "read_file", "input": {}}],
    }


def tool_result(call_id: str, text: str = "x" * 500) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": call_id, "content": text}],
    }


def conversation(pairs: int) -> list[dict[str, Any]]:
    """Original task, then *pairs* of (assistant tool_use, user tool_result)."""
    messages = [user("original task: " + "t" * 200)]
    for i in range(pairs):
        messages.append(assistant_tool(f"t{i}"))
        messages.append(tool_result(f"t{i}"))
    return messages


class TestEstimate(unittest.TestCase):
    def test_grows_with_content(self) -> None:
        small = estimate_tokens([user("hi")])
        large = estimate_tokens([user("hi" * 1000)])
        self.assertGreater(large, small)

    def test_handles_block_content(self) -> None:
        self.assertGreater(estimate_tokens([tool_result("t1")]), 0)


class TestNoCompactionNeeded(unittest.TestCase):
    def test_short_history_untouched(self) -> None:
        messages = conversation(2)
        out, trimmed = compact(messages, max_tokens=100_000)
        self.assertEqual(trimmed, 0)
        self.assertEqual(out, messages)

    def test_below_keep_recent_untouched(self) -> None:
        messages = conversation(2)
        out, trimmed = compact(messages, max_tokens=1, keep_recent=8)
        self.assertEqual(trimmed, 0)
        self.assertEqual(out, messages)


class TestCompaction(unittest.TestCase):
    def setUp(self) -> None:
        self.messages = conversation(20)
        self.out, self.trimmed = compact(self.messages, max_tokens=200, keep_recent=8)

    def test_actually_trims(self) -> None:
        self.assertGreater(self.trimmed, 0)
        self.assertLess(len(self.out), len(self.messages))

    def test_keeps_original_task(self) -> None:
        self.assertTrue(self.out[0]["content"].startswith("original task:"))

    def test_notes_the_trim_in_the_first_message(self) -> None:
        self.assertIn("were trimmed", self.out[0]["content"])

    def test_window_starts_on_assistant_so_roles_alternate(self) -> None:
        self.assertEqual(self.out[1]["role"], "assistant")
        for earlier, later in zip(self.out, self.out[1:]):
            self.assertNotEqual(earlier["role"], later["role"], f"{earlier['role']} repeated")

    def test_no_orphaned_tool_result(self) -> None:
        """Every tool_result must have its tool_use still present."""
        offered: set[str] = set()
        for message in self.out:
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "tool_use":
                    offered.add(block["id"])
                elif block.get("type") == "tool_result":
                    self.assertIn(
                        block["tool_use_id"], offered,
                        f"orphaned tool_result {block['tool_use_id']}",
                    )

    def test_keeps_the_most_recent_exchange(self) -> None:
        self.assertEqual(self.out[-1], self.messages[-1])


class TestEdgeCases(unittest.TestCase):
    def test_no_assistant_message_returns_unchanged(self) -> None:
        messages = [user("a"), user("b"), user("c"), user("d")]
        out, trimmed = compact(messages, max_tokens=1, keep_recent=1)
        self.assertEqual(trimmed, 0)
        self.assertEqual(out, messages)

    def test_repeated_compaction_is_stable(self) -> None:
        messages = conversation(20)
        first, _ = compact(messages, max_tokens=200, keep_recent=8)
        second, trimmed = compact(first, max_tokens=200, keep_recent=8)
        # Already at the floor: compacting again must not corrupt or loop.
        self.assertEqual(second[0]["role"], "user")
        self.assertEqual(second[-1], messages[-1])
        self.assertGreaterEqual(trimmed, 0)

    def test_trailing_text_answer_is_preserved(self) -> None:
        messages = conversation(20) + [assistant_text("final answer")]
        out, _ = compact(messages, max_tokens=200, keep_recent=8)
        self.assertEqual(out[-1]["content"][0]["text"], "final answer")


if __name__ == "__main__":
    unittest.main()
