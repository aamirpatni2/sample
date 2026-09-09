"""Tool dispatch tests. No API key or network required."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentic_dev.tools import ToolContext, dispatch  # noqa: E402


def always_approve(action: str, detail: str) -> bool:
    return True


def never_approve(action: str, detail: str) -> bool:
    return False


class ToolTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("print('hi')\n")
        self.ctx = ToolContext(workspace=self.root, approve=always_approve, command_timeout=10)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestReadFile(ToolTestCase):
    def test_reads_with_line_numbers(self) -> None:
        result = dispatch("read_file", {"path": "src/app.py"}, self.ctx)
        self.assertFalse(result.is_error)
        self.assertIn("print('hi')", result.content)
        self.assertIn("1\t", result.content)

    def test_missing_file_is_an_error_not_a_crash(self) -> None:
        result = dispatch("read_file", {"path": "nope.py"}, self.ctx)
        self.assertTrue(result.is_error)

    def test_escape_is_refused(self) -> None:
        result = dispatch("read_file", {"path": "../../etc/passwd"}, self.ctx)
        self.assertTrue(result.is_error)
        self.assertIn("guardrail", result.content.lower())

    def test_secrets_in_file_are_redacted(self) -> None:
        (self.root / ".env.local").write_text("ANTHROPIC_API_KEY=sk-ant-api03-realsecret12345678\n")
        result = dispatch("read_file", {"path": ".env.local"}, self.ctx)
        self.assertNotIn("realsecret12345678", result.content)


class TestWriteFile(ToolTestCase):
    def test_creates_new_file_without_approval(self) -> None:
        ctx = ToolContext(workspace=self.root, approve=never_approve)
        result = dispatch("write_file", {"path": "new/thing.py", "content": "x = 1\n"}, ctx)
        self.assertFalse(result.is_error)
        self.assertEqual((self.root / "new" / "thing.py").read_text(), "x = 1\n")

    def test_overwrite_requires_approval(self) -> None:
        ctx = ToolContext(workspace=self.root, approve=never_approve)
        result = dispatch("write_file", {"path": "src/app.py", "content": "wiped"}, ctx)
        self.assertTrue(result.is_error)
        self.assertEqual((self.root / "src" / "app.py").read_text(), "print('hi')\n")

    def test_overwrite_proceeds_when_approved(self) -> None:
        result = dispatch("write_file", {"path": "src/app.py", "content": "new\n"}, self.ctx)
        self.assertFalse(result.is_error)
        self.assertEqual((self.root / "src" / "app.py").read_text(), "new\n")

    def test_write_outside_workspace_is_refused(self) -> None:
        result = dispatch("write_file", {"path": "/tmp/evil.py", "content": "x"}, self.ctx)
        self.assertTrue(result.is_error)
        self.assertFalse(Path("/tmp/evil.py").exists())


class TestEditFile(ToolTestCase):
    """Targeted edits, so a one-line change cannot lose the rest of a file."""

    def setUp(self) -> None:
        super().setUp()
        (self.root / "calc.py").write_text(
            "def add(a, b):\n"
            "    return a - b\n"
            "\n"
            "def sub(a, b):\n"
            "    return a - b\n"
        )

    def test_replaces_the_named_text_only(self) -> None:
        result = dispatch(
            "edit_file",
            {"path": "calc.py", "old_string": "def add(a, b):\n    return a - b",
             "new_string": "def add(a, b):\n    return a + b"},
            self.ctx,
        )
        self.assertFalse(result.is_error, result.content)
        text = (self.root / "calc.py").read_text()
        self.assertIn("return a + b", text)
        self.assertIn("def sub(a, b):", text)  # rest of the file survives

    def test_ambiguous_match_is_refused(self) -> None:
        """Editing the wrong one of several matches corrupts code silently."""
        result = dispatch(
            "edit_file",
            {"path": "calc.py", "old_string": "return a - b", "new_string": "return a + b"},
            self.ctx,
        )
        self.assertTrue(result.is_error)
        self.assertIn("appears 2 times", result.content)
        self.assertEqual((self.root / "calc.py").read_text().count("return a - b"), 2)

    def test_missing_text_is_reported_not_guessed(self) -> None:
        result = dispatch(
            "edit_file",
            {"path": "calc.py", "old_string": "def multiply", "new_string": "x"},
            self.ctx,
        )
        self.assertTrue(result.is_error)
        self.assertIn("not found", result.content)

    def test_deletion_via_empty_new_string(self) -> None:
        result = dispatch(
            "edit_file",
            {"path": "calc.py", "old_string": "\ndef sub(a, b):\n    return a - b\n",
             "new_string": ""},
            self.ctx,
        )
        self.assertFalse(result.is_error, result.content)
        self.assertNotIn("def sub", (self.root / "calc.py").read_text())

    def test_empty_old_string_is_refused(self) -> None:
        result = dispatch(
            "edit_file",
            {"path": "calc.py", "old_string": "", "new_string": "x"},
            self.ctx,
        )
        self.assertTrue(result.is_error)

    def test_identical_strings_are_refused(self) -> None:
        result = dispatch(
            "edit_file",
            {"path": "calc.py", "old_string": "return a - b", "new_string": "return a - b"},
            self.ctx,
        )
        self.assertTrue(result.is_error)

    def test_missing_file_is_an_error(self) -> None:
        result = dispatch(
            "edit_file", {"path": "nope.py", "old_string": "a", "new_string": "b"}, self.ctx
        )
        self.assertTrue(result.is_error)

    def test_workspace_escape_is_refused(self) -> None:
        result = dispatch(
            "edit_file",
            {"path": "../../etc/hosts", "old_string": "localhost", "new_string": "evil"},
            self.ctx,
        )
        self.assertTrue(result.is_error)
        self.assertIn("guardrail", result.content.lower())

    def test_edit_needs_no_approval(self) -> None:
        """Editing inside the workspace is the agent's job; overwriting is not."""
        ctx = ToolContext(workspace=self.root, approve=never_approve)
        result = dispatch(
            "edit_file",
            {"path": "calc.py", "old_string": "def add(a, b):", "new_string": "def plus(a, b):"},
            ctx,
        )
        self.assertFalse(result.is_error, result.content)


class TestListFiles(ToolTestCase):
    def test_lists_workspace(self) -> None:
        result = dispatch("list_files", {}, self.ctx)
        self.assertFalse(result.is_error)
        self.assertIn("app.py", result.content)

    def test_skips_hidden_and_pycache(self) -> None:
        (self.root / "__pycache__").mkdir()
        (self.root / "__pycache__" / "junk.pyc").write_text("x")
        (self.root / ".secret").write_text("x")
        result = dispatch("list_files", {}, self.ctx)
        self.assertNotIn("junk.pyc", result.content)
        self.assertNotIn(".secret", result.content)


class TestRunCommand(ToolTestCase):
    def test_safe_command_runs_without_approval(self) -> None:
        ctx = ToolContext(workspace=self.root, approve=never_approve)
        result = dispatch("run_command", {"command": "ls"}, ctx)
        self.assertFalse(result.is_error)
        self.assertIn("src", result.content)

    def test_blocked_command_is_never_run_even_if_approved(self) -> None:
        result = dispatch("run_command", {"command": "sudo rm -rf /"}, self.ctx)
        self.assertTrue(result.is_error)
        self.assertIn("blocked", result.content.lower())

    def test_state_changing_command_respects_denial(self) -> None:
        ctx = ToolContext(workspace=self.root, approve=never_approve)
        result = dispatch("run_command", {"command": "touch created.txt"}, ctx)
        self.assertTrue(result.is_error)
        self.assertFalse((self.root / "created.txt").exists())

    def test_nonzero_exit_is_reported_as_error(self) -> None:
        result = dispatch("run_command", {"command": "ls /definitely/not/here"}, self.ctx)
        self.assertTrue(result.is_error)
        self.assertIn("exit code:", result.content)

    def test_timeout_is_handled(self) -> None:
        ctx = ToolContext(workspace=self.root, approve=always_approve, command_timeout=1)
        result = dispatch("run_command", {"command": "python3 -c 'import time; time.sleep(5)'"}, ctx)
        self.assertTrue(result.is_error)
        self.assertIn("timed out", result.content.lower())


class TestDispatch(ToolTestCase):
    def test_unknown_tool_is_an_error(self) -> None:
        result = dispatch("launch_missiles", {}, self.ctx)
        self.assertTrue(result.is_error)
        self.assertIn("Unknown tool", result.content)

    def test_missing_required_arg_does_not_crash(self) -> None:
        result = dispatch("read_file", {}, self.ctx)
        self.assertTrue(result.is_error)


if __name__ == "__main__":
    unittest.main()
