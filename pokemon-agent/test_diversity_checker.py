"""Tests for action diversity checking.

Mewtoo pattern: if one action exceeds 60% of the last 15 actions,
flag it and suggest alternatives. Complements stuck detection with
a different signal — you might be moving but doing the same thing.
"""
import unittest
from diversity_checker import DiversityChecker


class TestDiversityChecker(unittest.TestCase):
    """Core diversity checking tests."""

    def setUp(self):
        self.dc = DiversityChecker()

    # ── Basic recording ──

    def test_empty_history(self):
        """No actions recorded = no dominant action."""
        self.assertIsNone(self.dc.dominant_action())

    def test_single_action(self):
        """Single action can't be dominant (need enough history)."""
        self.dc.record("a")
        self.assertIsNone(self.dc.dominant_action())

    def test_varied_actions_no_dominant(self):
        """Varied actions don't trigger dominance."""
        for button in ["a", "b", "up", "down", "left", "right", "a", "b",
                        "up", "down", "left", "right", "a", "start", "select"]:
            self.dc.record(button)
        self.assertIsNone(self.dc.dominant_action())

    def test_dominant_action_detected(self):
        """One action > 60% of last 15 = dominant."""
        # 10 "a" presses out of 15 = 66%
        for _ in range(10):
            self.dc.record("a")
        for _ in range(5):
            self.dc.record("b")
        self.assertEqual(self.dc.dominant_action(), "a")

    def test_exactly_60_percent_not_dominant(self):
        """Exactly 60% is not dominant (must exceed 60%)."""
        # 9 "a" out of 15 = 60%
        for _ in range(9):
            self.dc.record("a")
        for _ in range(6):
            self.dc.record("b")
        self.assertIsNone(self.dc.dominant_action())

    def test_sliding_window(self):
        """Only the last 15 actions matter."""
        # First 15 are all "a" — dominant
        for _ in range(15):
            self.dc.record("a")
        self.assertEqual(self.dc.dominant_action(), "a")
        # Now add 15 varied actions — "a" dominance should clear
        for button in ["b", "up", "down", "left", "right"] * 3:
            self.dc.record(button)
        self.assertIsNone(self.dc.dominant_action())

    # ── Suggestions ──

    def test_suggest_alternatives(self):
        """When dominant, suggest other directions/buttons."""
        for _ in range(12):
            self.dc.record("right")
        for _ in range(3):
            self.dc.record("a")
        alts = self.dc.suggest_alternatives()
        self.assertNotIn("right", alts)
        self.assertIn("left", alts)
        self.assertIn("up", alts)
        self.assertIn("down", alts)

    def test_suggest_alternatives_no_dominant(self):
        """No dominant = no suggestions."""
        self.dc.record("a")
        self.assertEqual(self.dc.suggest_alternatives(), [])

    # ── Format for prompt ──

    def test_format_no_dominant(self):
        """No dominant action = empty string."""
        self.assertEqual(self.dc.format_for_prompt(), "")

    def test_format_with_dominant(self):
        """Dominant action produces a warning string."""
        for _ in range(12):
            self.dc.record("a")
        for _ in range(3):
            self.dc.record("b")
        prompt = self.dc.format_for_prompt()
        self.assertIn("a", prompt)
        self.assertIn("repetitive", prompt.lower())

    # ── Custom config ──

    def test_custom_window_and_threshold(self):
        """Can configure window size and threshold."""
        dc = DiversityChecker(window_size=10, threshold=0.5)
        for _ in range(6):
            dc.record("a")
        for _ in range(4):
            dc.record("b")
        self.assertEqual(dc.dominant_action(), "a")

    # ── Stats ──

    def test_stats(self):
        """Stats returns action distribution."""
        for _ in range(5):
            self.dc.record("a")
        for _ in range(3):
            self.dc.record("b")
        stats = self.dc.stats()
        self.assertEqual(stats["total_recorded"], 8)
        self.assertEqual(stats["window_size"], 8)  # < 15, so actual size
        self.assertEqual(stats["distribution"]["a"], 5)
        self.assertEqual(stats["distribution"]["b"], 3)

    # ── Clear ──

    def test_clear(self):
        """Clear resets all history."""
        for _ in range(10):
            self.dc.record("a")
        self.dc.clear()
        self.assertIsNone(self.dc.dominant_action())
        self.assertEqual(self.dc.stats()["total_recorded"], 0)


if __name__ == "__main__":
    unittest.main()
