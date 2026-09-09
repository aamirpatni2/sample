"""Regression tests for command-classifier bypasses.

Each case here was classified SAFE by the first version of the classifier.
They are grouped by the root cause they came from, not by symptom.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentic_dev.guardrails import Risk, classify_command  # noqa: E402


class BypassTestCase(unittest.TestCase):
    def assert_not_safe(self, command: str) -> None:
        verdict = classify_command(command)
        self.assertIsNot(
            verdict.risk, Risk.SAFE,
            f"{command!r} classified SAFE — bypass: {verdict.reason}",
        )

    def assert_safe(self, command: str) -> None:
        verdict = classify_command(command)
        self.assertIs(verdict.risk, Risk.SAFE, f"{command!r} -> {verdict}")


class TestRedirectionBypass(BypassTestCase):
    """Root cause 1: any read-only command plus > writes to an arbitrary path."""

    def test_output_redirect(self) -> None:
        self.assert_not_safe("echo pwned > /etc/passwd")

    def test_append_redirect(self) -> None:
        self.assert_not_safe("cat file.txt >> /etc/hosts")

    def test_input_redirect(self) -> None:
        self.assert_not_safe("cat < /etc/shadow")


class TestInterpreterBypass(BypassTestCase):
    """Root cause 2: a binary allowlist cannot express 'safe unless flag X'."""

    def test_python_script(self) -> None:
        self.assert_not_safe("python3 evil.py")

    def test_python_inline(self) -> None:
        self.assert_not_safe('python3 -c "import shutil; shutil.rmtree(\'/\')"')

    def test_node_inline(self) -> None:
        self.assert_not_safe("node -e \"require('fs').unlinkSync('x')\"")

    def test_awk_system_call(self) -> None:
        self.assert_not_safe("awk 'BEGIN{system(\"rm -rf /\")}'")

    def test_shell_invocation(self) -> None:
        self.assert_not_safe("bash script.sh")

    def test_sed_in_place_write(self) -> None:
        self.assert_not_safe("sed -i 's/a/b/' important.py")

    def test_find_delete(self) -> None:
        self.assert_not_safe("find . -name '*.py' -delete")

    def test_find_exec(self) -> None:
        self.assert_not_safe("find . -exec rm {} ;")

    def test_env_dumps_secrets(self) -> None:
        self.assert_not_safe("env")


class TestWorkspaceEscapeByRead(BypassTestCase):
    """Reading outside the workspace exfiltrates into the model's context."""

    def test_absolute_path_read(self) -> None:
        self.assert_not_safe("cat /etc/passwd")

    def test_recursive_grep_of_root(self) -> None:
        self.assert_not_safe("grep -r . / --include=*.env")

    def test_home_reference(self) -> None:
        self.assert_not_safe("ls ~/.aws")


class TestQuoteAwareness(BypassTestCase):
    """Separators inside quotes are data, not command separators."""

    def test_semicolon_in_quotes_is_not_a_chain(self) -> None:
        # Must be judged on the interpreter, not on an accidental mid-string split.
        verdict = classify_command("python3 -c 'import os; print(1)'")
        self.assertIsNot(verdict.risk, Risk.SAFE)
        self.assertIn("arbitrary code", verdict.reason)

    def test_command_substitution_still_caught(self) -> None:
        self.assert_not_safe("echo $(cat /etc/passwd)")

    def test_backticks_still_caught(self) -> None:
        self.assert_not_safe("echo `whoami`")


class TestOrdinaryWorkStillRuns(BypassTestCase):
    """The stricter rules must not make normal read-only work require approval."""

    def test_common_read_only_commands(self) -> None:
        for command in (
            "ls", "ls -la src", "cat README.md", "head -20 main.py",
            "grep -rn TODO src", "wc -l *.py", "git status", "git diff HEAD",
            "git log --oneline -10", "diff a.py b.py", "ls | grep test",
        ):
            with self.subTest(command=command):
                self.assert_safe(command)


if __name__ == "__main__":
    unittest.main()
