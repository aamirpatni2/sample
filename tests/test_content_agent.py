"""Content agent tests: parsing and prompt assembly. No API key needed.

The Anthropic client is constructed at import time, so a dummy key is set
before importing the module.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import agent  # noqa: E402


class TestSplitVariations(unittest.TestCase):
    def test_splits_clean_output(self) -> None:
        raw = "First post\n---POST---\nSecond post\n---POST---\nThird post"
        self.assertEqual(
            agent.split_variations(raw, "---POST---", 3),
            ["First post", "Second post", "Third post"],
        )

    def test_strips_chatty_preamble(self) -> None:
        """The old parser turned this preamble into post #1."""
        raw = "Here are 3 Facebook posts:\nReal first post\n---POST---\nSecond post"
        parts = agent.split_variations(raw, "---POST---", 3)
        self.assertEqual(parts[0], "Real first post")
        self.assertNotIn("Here are", " ".join(parts))

    def test_strips_numbering_the_model_was_told_to_omit(self) -> None:
        raw = "1. First post\n---POST---\nPost 2: Second post\n---POST---\n3) Third"
        parts = agent.split_variations(raw, "---POST---", 3)
        self.assertEqual(parts, ["First post", "Second post", "Third"])

    def test_drops_empty_chunks_from_leading_delimiter(self) -> None:
        raw = "---POST---\nOnly post"
        self.assertEqual(agent.split_variations(raw, "---POST---", 3), ["Only post"])

    def test_caps_at_requested_count(self) -> None:
        raw = "---POST---".join(f"Post {i}" for i in range(10))
        self.assertEqual(len(agent.split_variations(raw, "---POST---", 3)), 3)

    def test_single_line_preamble_is_kept_as_content(self) -> None:
        """A one-line post must not be eaten by preamble stripping."""
        raw = "Here is why AI matters"
        self.assertEqual(agent.split_variations(raw, "---POST---", 3), ["Here is why AI matters"])

    def test_handles_missing_delimiter(self) -> None:
        raw = "The model ignored the delimiter entirely."
        self.assertEqual(agent.split_variations(raw, "---POST---", 3), [raw])

    def test_thread_returns_six(self) -> None:
        raw = "---TWEET---".join(f"{i}/ tweet body" for i in range(1, 9))
        self.assertEqual(len(agent.split_variations(raw, "---TWEET---", 6)), 6)


class TestBrandAndLanguage(unittest.TestCase):
    def test_brand_block_has_no_language_contradiction(self) -> None:
        """The v1 bug: 'write in English' plus a mandatory Roman-Urdu template."""
        self.assertIn("LANGUAGE", agent.BRAND)
        self.assertEqual(agent.BRAND.count("LANGUAGE"), 1)

    def test_banned_phrases_are_declared(self) -> None:
        for phrase in ("game changer", "dive in", "revolutionary"):
            self.assertIn(phrase, agent.BRAND)

    def test_every_platform_inherits_the_brand(self) -> None:
        for name in agent.PLATFORMS:
            system = f"{agent.BRAND}\n\n{agent.PLATFORMS[name].rules}"
            self.assertIn("AUDIENCE", system, f"{name} missing brand context")
            self.assertIn("NEVER WRITE", system, f"{name} missing anti-slop rules")


class TestLanguageControl(unittest.TestCase):
    """The setting must actually control the output, and be verifiable."""

    def test_language_rule_comes_last_in_the_system_prompt(self) -> None:
        """The Facebook template holds Roman Urdu CTA lines; a language rule
        placed before it loses to recency, which is how the live run produced
        a Roman Urdu body under language=english."""
        system = agent._system_prompt(agent.PLATFORMS["facebook"])
        self.assertGreater(
            system.rindex("LANGUAGE CHECK"),
            system.rindex(agent.CTA_PROMPT_LINE),
            "language rule must come after the template's Roman Urdu lines",
        )

    def test_every_platform_gets_the_language_rule_last(self) -> None:
        for name in agent.PLATFORMS:
            with self.subTest(platform=name):
                self.assertIn("LANGUAGE CHECK", agent._system_prompt(agent.PLATFORMS[name]))

    def test_detector_scores_roman_urdu_high(self) -> None:
        text = "Aapka pehla AI agent bilkul free bana sakte ho ab. Matlab ab nahi karna padta."
        self.assertGreaterEqual(agent.roman_urdu_score(text), 5)

    def test_detector_scores_english_zero(self) -> None:
        text = "Your first AI agent is now free to build. No subscription needed up front."
        self.assertEqual(agent.roman_urdu_score(text), 0)

    def test_fixed_cta_lines_do_not_count_against_english(self) -> None:
        """The brand signatures are Roman Urdu by design and must not trip it."""
        post = (
            "Build your first AI agent for free.\n"
            "OpenAI launched a free tier. No subscription required.\n"
            f"{agent.CAVEAT_LINE}\n{agent.CTA_PROMPT_LINE}\n{agent.CTA_FOLLOW_LINE}"
        )
        self.assertLessEqual(agent.roman_urdu_score(post), 2)


class TestUserPrompt(unittest.TestCase):
    def build(self, platform_name: str, summary: str = "A summary.") -> str:
        return agent._build_user_prompt(
            agent.PLATFORMS[platform_name], "A headline", summary, "informative"
        )

    def test_includes_todays_date(self) -> None:
        from datetime import date
        self.assertIn(date.today().isoformat(), self.build("facebook"))

    def test_guards_against_inventing_detail_when_summary_is_empty(self) -> None:
        self.assertIn("do not invent", self.build("facebook", summary=""))

    def test_asks_for_distinct_variations(self) -> None:
        self.assertIn("differ in hook AND angle", self.build("facebook"))

    def test_thread_is_one_artifact_not_variations(self) -> None:
        """A 6-tweet thread must not be told its tweets should differ in angle."""
        self.assertNotIn("differ in hook AND angle", self.build("thread"))

    def test_declares_the_delimiter(self) -> None:
        self.assertIn("---SCRIPT---", self.build("reel"))

    def test_unknown_tone_falls_back_safely(self) -> None:
        prompt = agent._build_user_prompt(
            agent.PLATFORMS["facebook"], "H", "S", "nonsense-tone"
        )
        self.assertIn(agent.TONE_INSTRUCTIONS["informative"], prompt)


class TestRewriteParsing(unittest.TestCase):
    def test_extracts_analysis_and_both_rewrites(self) -> None:
        raw = """HOOK: Result-first reveal
HASHTAGS: #AI #buildinpublic
CTA: Comment to get the prompt
STYLE: Punchy and direct
---XTWEET---
The tweet rewrite.
---FACEBOOK---
The Facebook rewrite."""
        analysis = {k.lower(): v.strip() for k, v in agent._FIELD.findall(raw)}
        self.assertEqual(analysis["hook"], "Result-first reveal")
        self.assertEqual(analysis["style"], "Punchy and direct")
        self.assertEqual(len(analysis), 4)

    def test_field_regex_ignores_mid_text_matches(self) -> None:
        """The old loop matched any line starting with the field name."""
        raw = "HOOK: real value\nSome prose that mentions CTA: not a field"
        found = dict(agent._FIELD.findall(raw))
        self.assertEqual(found.get("HOOK"), "real value")
        self.assertNotIn("CTA", found)


class TestPlatformRegistry(unittest.TestCase):
    def test_all_platforms_are_well_formed(self) -> None:
        for name, platform in agent.PLATFORMS.items():
            with self.subTest(platform=name):
                self.assertGreater(platform.count, 0)
                self.assertGreater(platform.max_tokens, 0)
                self.assertTrue(platform.delimiter.startswith("---"))
                self.assertTrue(platform.rules.strip())

    def test_public_functions_cover_every_platform(self) -> None:
        self.assertEqual(len(agent.PLATFORMS), 9)


if __name__ == "__main__":
    unittest.main()
