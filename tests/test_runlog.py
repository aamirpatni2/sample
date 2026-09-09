"""Run log tests. No API key or network required."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentic_dev.runlog import JsonlRunLog, tee  # noqa: E402


class TestJsonlRunLog(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "logs" / "run.jsonl"
        self.log = JsonlRunLog(self.path, run_id="test-run")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def records(self) -> list[dict]:
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_creates_parent_directory(self) -> None:
        self.assertTrue(self.path.parent.is_dir())

    def test_appends_one_line_per_event(self) -> None:
        self.log("text", "hello")
        self.log("tool", "read_file")
        records = self.records()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["event"], "text")
        self.assertEqual(records[1]["detail"], "read_file")
        self.assertEqual(records[0]["run_id"], "test-run")

    def test_redacts_secrets_before_writing(self) -> None:
        self.log("text", "key sk-ant-api03-leakedvalue1234567")
        raw = self.path.read_text()
        self.assertNotIn("leakedvalue1234567", raw)
        self.assertIn("[REDACTED]", raw)

    def test_redacts_extra_fields(self) -> None:
        self.log.write("tool", "ok", command="export TOKEN=hunter2secretvalue")
        self.assertNotIn("hunter2secretvalue", self.path.read_text())

    def test_write_failure_does_not_raise(self) -> None:
        log = JsonlRunLog(self.path)
        log.path = Path("/proc/definitely/not/writable.jsonl")
        log("text", "should not crash the run")
        self.assertTrue(log.write_errors)

    def test_lines_are_valid_json(self) -> None:
        self.log("text", 'quotes " and \\ backslashes and \n newlines')
        self.assertEqual(len(self.records()), 1)


class TestTee(unittest.TestCase):
    def test_fans_out_to_all_handlers(self) -> None:
        a: list[tuple[str, str]] = []
        b: list[tuple[str, str]] = []
        emit = tee(lambda e, d: a.append((e, d)), lambda e, d: b.append((e, d)), None)
        emit("text", "hi")
        self.assertEqual(a, [("text", "hi")])
        self.assertEqual(b, [("text", "hi")])


if __name__ == "__main__":
    unittest.main()
