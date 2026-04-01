"""Tests for verdict_parser.py — cca-reviewer agent output parsing."""

import sys
import unittest

sys.path.insert(0, "reddit-intelligence")
from verdict_parser import ReviewVerdict, parse_verdict, parse_multiple


class TestParseVerdict(unittest.TestCase):
    """Test extraction of structured fields from agent output."""

    SAMPLE = """REVIEW: Follow-up: Claude Code's source confirms the system prompt problem
Source: https://www.reddit.com/r/ClaudeCode/comments/1s99j2t/
Score: 241 pts | 83% upvoted | 43 comments

FRONTIER: Frontier 1: Memory + Frontier 4: Agent Guard
RAT POISON: CLEAN

WHAT IT IS:
Technical deep-dive confirming CC's internal system prompt hierarchy.

WHAT WE CAN STEAL:
Use <important> XML wrappers for critical CLAUDE.md directives.

IMPLEMENTATION:
- Delivery: CLAUDE.md template change
- Effort: 1 hour
- Dependencies: none

VERDICT: ADAPT
WHY: Confirms system prompt subordination. Actionable XML wrapper pattern."""

    def test_title(self):
        v = parse_verdict(self.SAMPLE)
        self.assertEqual(
            v.title,
            "Follow-up: Claude Code's source confirms the system prompt problem",
        )

    def test_url(self):
        v = parse_verdict(self.SAMPLE)
        self.assertEqual(
            v.url, "https://www.reddit.com/r/ClaudeCode/comments/1s99j2t/"
        )

    def test_score(self):
        v = parse_verdict(self.SAMPLE)
        self.assertEqual(v.score_pts, 241)
        self.assertEqual(v.upvote_pct, 83)
        self.assertEqual(v.comment_count, 43)

    def test_frontier(self):
        v = parse_verdict(self.SAMPLE)
        self.assertIn("Frontier 1", v.frontier)
        self.assertIn("Frontier 4", v.frontier)

    def test_rat_poison(self):
        v = parse_verdict(self.SAMPLE)
        self.assertEqual(v.rat_poison, "CLEAN")

    def test_verdict(self):
        v = parse_verdict(self.SAMPLE)
        self.assertEqual(v.verdict, "ADAPT")

    def test_why(self):
        v = parse_verdict(self.SAMPLE)
        self.assertIn("system prompt", v.why)

    def test_what_to_steal(self):
        v = parse_verdict(self.SAMPLE)
        self.assertIn("XML", v.what_to_steal)


class TestVerdictTypes(unittest.TestCase):
    """Test all verdict types parse correctly."""

    def test_build(self):
        text = "REVIEW: Test\nSource: https://x.com\nScore: 100 pts\nFRONTIER: F1\nRAT POISON: CLEAN\nWHAT IT IS:\nA thing.\nWHAT WE CAN STEAL:\nEverything.\nVERDICT: BUILD\nWHY: Critical."
        v = parse_verdict(text)
        self.assertEqual(v.verdict, "BUILD")

    def test_skip(self):
        text = "REVIEW: Meme post\nSource: https://x.com\nScore: 5 pts\nFRONTIER: OFF-SCOPE\nRAT POISON: CONTAMINATED — pure hype\nVERDICT: SKIP\nWHY: Not actionable."
        v = parse_verdict(text)
        self.assertEqual(v.verdict, "SKIP")
        self.assertIn("CONTAMINATED", v.rat_poison)

    def test_reference_personal(self):
        text = "REVIEW: Trading tool\nSource: https://x.com\nScore: 50 pts\nFRONTIER: OFF-SCOPE\nVERDICT: REFERENCE-PERSONAL\nWHY: Useful for Kalshi."
        v = parse_verdict(text)
        self.assertEqual(v.verdict, "REFERENCE-PERSONAL")

    def test_reference(self):
        text = "REVIEW: Interesting thing\nSource: https://x.com\nScore: 30 pts\nFRONTIER: General\nVERDICT: REFERENCE\nWHY: Worth noting."
        v = parse_verdict(text)
        self.assertEqual(v.verdict, "REFERENCE")


class TestCondensedFormat(unittest.TestCase):
    """Test condensed output for /cca-nuclear."""

    def test_skip_condensed(self):
        v = ReviewVerdict(title="Meme post", score_pts=5, verdict="SKIP", why="Not relevant")
        c = v.to_condensed()
        self.assertTrue(c.startswith("SKIP:"))
        self.assertIn("5 pts", c)

    def test_ref_condensed(self):
        v = ReviewVerdict(
            title="Good ref", score_pts=100, verdict="REFERENCE",
            frontier="Frontier 3", why="Worth tracking"
        )
        c = v.to_condensed()
        self.assertTrue(c.startswith("REF:"))
        self.assertIn("Frontier 3", c)

    def test_build_condensed(self):
        v = ReviewVerdict(
            title="Build this", score_pts=200, verdict="BUILD",
            frontier="Frontier 1", what_to_steal="Memory consolidation pattern"
        )
        c = v.to_condensed()
        self.assertIn("BUILD:", c)
        self.assertIn("STEAL:", c)


class TestFindingsLogEntry(unittest.TestCase):
    """Test FINDINGS_LOG.md entry formatting."""

    def test_basic_entry(self):
        v = ReviewVerdict(
            title="Test Post", url="https://reddit.com/r/test/123",
            score_pts=50, upvote_pct=90, comment_count=10,
            verdict="ADAPT", frontier="Frontier 1",
            what_to_steal="Pattern X"
        )
        entry = v.to_findings_log_entry("2026-04-01")
        self.assertIn("[2026-04-01]", entry)
        self.assertIn("[ADAPT]", entry)
        self.assertIn("[Frontier 1]", entry)
        self.assertIn('"Test Post"', entry)
        self.assertIn("50pts", entry)
        self.assertIn("Pattern X", entry)
        self.assertIn("https://reddit.com/r/test/123", entry)

    def test_special_flags(self):
        v = ReviewVerdict(
            title="Agent post", url="https://x.com", score_pts=10,
            verdict="ADAPT", frontier="F4",
            special_flags=["POLYBOT-RELEVANT", "MAESTRO-RELEVANT"]
        )
        entry = v.to_findings_log_entry("2026-04-01")
        self.assertIn("[POLYBOT-RELEVANT]", entry)
        self.assertIn("[MAESTRO-RELEVANT]", entry)


class TestSpecialFlags(unittest.TestCase):
    """Test auto-detection of special flags from content."""

    def test_polybot_flag(self):
        text = "REVIEW: Self-learning agent\nSource: https://x.com\nScore: 10 pts\nVERDICT: ADAPT\nWHY: Has self-learning loop."
        v = parse_verdict(text)
        self.assertIn("POLYBOT-RELEVANT", v.special_flags)

    def test_maestro_flag(self):
        text = "REVIEW: Multi-session manager\nSource: https://x.com\nScore: 10 pts\nVERDICT: REF\nWHY: Workspace tool."
        v = parse_verdict(text)
        self.assertIn("MAESTRO-RELEVANT", v.special_flags)

    def test_usage_dashboard_flag(self):
        text = "REVIEW: Cost tracker\nSource: https://x.com\nScore: 10 pts\nVERDICT: REF\nWHY: Token usage dashboard."
        v = parse_verdict(text)
        self.assertIn("USAGE-DASHBOARD", v.special_flags)


class TestParseMultiple(unittest.TestCase):
    """Test parsing multiple REVIEW blocks from one output."""

    def test_two_blocks(self):
        text = """REVIEW: Post One
Source: https://x.com/1
Score: 100 pts
VERDICT: BUILD
WHY: Important.

REVIEW: Post Two
Source: https://x.com/2
Score: 50 pts
VERDICT: SKIP
WHY: Not relevant."""
        results = parse_multiple(text)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].verdict, "BUILD")
        self.assertEqual(results[1].verdict, "SKIP")

    def test_single_block(self):
        text = "REVIEW: Only one\nSource: https://x.com\nScore: 10 pts\nVERDICT: REFERENCE\nWHY: Ok."
        results = parse_multiple(text)
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
