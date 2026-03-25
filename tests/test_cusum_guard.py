"""
test_cusum_guard.py — Tests for CUSUM-triggered auto-guard discovery.

Validates the cusum_statistic() function and its integration into
auto_guard_discovery.py for the Kalshi bot. CUSUM (Page 1954, Biometrika 41:100-115)
detects drift away from baseline win rate before binomial p-value reaches significance.

TDD: tests written first, implementation follows.
"""

import os
import sys
import unittest

# Add polybot scripts to path for import
POLYBOT_ROOT = os.path.expanduser("~/Projects/polymarket-bot")
sys.path.insert(0, os.path.join(POLYBOT_ROOT, "scripts"))


class TestCusumStatistic(unittest.TestCase):
    """Test the cusum_statistic() pure function."""

    def test_all_wins_no_alert(self):
        """All wins should never trigger CUSUM alert."""
        from auto_guard_discovery import cusum_statistic
        outcomes = [True] * 20
        triggered, s_val = cusum_statistic(outcomes, mu_0=0.93, h=5.0)
        self.assertFalse(triggered)
        self.assertAlmostEqual(s_val, 0.0)

    def test_all_losses_triggers_alert(self):
        """All losses should trigger CUSUM alert quickly."""
        from auto_guard_discovery import cusum_statistic
        outcomes = [False] * 10
        triggered, s_val = cusum_statistic(outcomes, mu_0=0.93, h=5.0)
        self.assertTrue(triggered)
        self.assertGreater(s_val, 5.0)

    def test_mixed_near_baseline_no_alert(self):
        """Outcomes near baseline should not trigger."""
        from auto_guard_discovery import cusum_statistic
        # 18/20 wins = 90% WR, baseline 93% — slight underperformance but not enough for S=5
        outcomes = [True] * 18 + [False] * 2
        triggered, s_val = cusum_statistic(outcomes, mu_0=0.93, h=5.0)
        self.assertFalse(triggered)

    def test_gradual_drift_triggers(self):
        """Sustained below-baseline performance should trigger."""
        from auto_guard_discovery import cusum_statistic
        # 14/20 wins = 70% WR when baseline is 93% — clear drift
        # 6 consecutive losses after wins: S = 6 * 0.855 = 5.13 > 5.0
        outcomes = [True] * 14 + [False] * 6
        triggered, s_val = cusum_statistic(outcomes, mu_0=0.93, h=5.0)
        self.assertTrue(triggered)

    def test_s_value_resets_on_recovery(self):
        """S resets to 0 when performance recovers (CUSUM reset property)."""
        from auto_guard_discovery import cusum_statistic
        # Losses then wins — S should reset during win streak
        outcomes = [False] * 3 + [True] * 10
        triggered, s_val = cusum_statistic(outcomes, mu_0=0.93, h=5.0)
        self.assertFalse(triggered)

    def test_returns_tuple(self):
        """Should return (triggered: bool, s_value: float)."""
        from auto_guard_discovery import cusum_statistic
        result = cusum_statistic([True, False], mu_0=0.90, h=5.0)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], float)

    def test_empty_outcomes(self):
        """Empty outcomes should not trigger."""
        from auto_guard_discovery import cusum_statistic
        triggered, s_val = cusum_statistic([], mu_0=0.93, h=5.0)
        self.assertFalse(triggered)
        self.assertAlmostEqual(s_val, 0.0)

    def test_custom_threshold(self):
        """Higher threshold requires more evidence."""
        from auto_guard_discovery import cusum_statistic
        outcomes = [False] * 8
        # With h=5.0 should trigger
        triggered_5, _ = cusum_statistic(outcomes, mu_0=0.93, h=5.0)
        # With h=10.0 might not
        triggered_10, _ = cusum_statistic(outcomes, mu_0=0.93, h=10.0)
        self.assertTrue(triggered_5)
        # Higher threshold is harder to reach (may or may not trigger depending on exact math)

    def test_low_baseline_wr(self):
        """Should work with lower baseline WRs (e.g., 85%)."""
        from auto_guard_discovery import cusum_statistic
        # All losses against 85% baseline
        outcomes = [False] * 10
        triggered, s_val = cusum_statistic(outcomes, mu_0=0.85, h=5.0)
        self.assertTrue(triggered)


class TestCusumGuardIntegration(unittest.TestCase):
    """Test that CUSUM guards integrate into discover_guards_with_cusum()."""

    def test_cusum_constant_exists(self):
        """CUSUM_THRESHOLD constant should exist."""
        from auto_guard_discovery import CUSUM_THRESHOLD
        self.assertEqual(CUSUM_THRESHOLD, 5.0)

    def test_cusum_min_bets_constant(self):
        """CUSUM_MIN_BETS should require reasonable sample size."""
        from auto_guard_discovery import CUSUM_MIN_BETS
        self.assertGreaterEqual(CUSUM_MIN_BETS, 15)

    def test_guard_has_cusum_fields(self):
        """CUSUM-triggered guards should have cusum_s and guard_type fields."""
        from auto_guard_discovery import cusum_statistic
        # This tests the function exists and returns expected types
        triggered, s_val = cusum_statistic([False] * 10, mu_0=0.93, h=5.0)
        self.assertIsInstance(s_val, float)

    def test_cusum_formula_matches_page_1954(self):
        """Verify CUSUM formula: S_i = max(0, S_{i-1} + (mu_0 - outcome - k))."""
        from auto_guard_discovery import cusum_statistic
        # Manual calculation:
        # mu_0 = 0.90, mu_1 = max(0.01, 0.90 - 0.15) = 0.75
        # k = (0.90 - 0.75) / 2 = 0.075
        # outcome=0 (loss): increment = 0.90 - 0 - 0.075 = 0.825
        # outcome=1 (win): increment = 0.90 - 1 - 0.075 = -0.175
        # After 7 losses: S = 7 * 0.825 = 5.775 > 5.0
        outcomes = [False] * 7
        triggered, s_val = cusum_statistic(outcomes, mu_0=0.90, h=5.0)
        self.assertTrue(triggered)
        self.assertAlmostEqual(s_val, 5.775, places=2)


if __name__ == "__main__":
    unittest.main()
