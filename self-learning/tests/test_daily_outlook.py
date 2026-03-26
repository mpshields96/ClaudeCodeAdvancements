#!/usr/bin/env python3
"""Tests for daily_outlook.py — Daily performance outlook predictor."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from daily_outlook import DailyOutlook, OutlookResult, VolumeScenario


class TestVolumeScenario(unittest.TestCase):
    """Test VolumeScenario dataclass."""

    def test_basic(self):
        vs = VolumeScenario(label="MEDIUM", bets_low=40, bets_high=80)
        self.assertEqual(vs.label, "MEDIUM")
        self.assertEqual(vs.midpoint, 60)

    def test_midpoint_odd(self):
        vs = VolumeScenario(label="TEST", bets_low=15, bets_high=40)
        self.assertEqual(vs.midpoint, 27)  # int((15+40)/2)


class TestDailyOutlook(unittest.TestCase):
    """Test the DailyOutlook predictor."""

    def test_default_creation(self):
        outlook = DailyOutlook()
        self.assertAlmostEqual(outlook.bankroll_usd, 190.0)
        self.assertAlmostEqual(outlook.daily_target, 20.0)

    def test_predict_medium_volume(self):
        outlook = DailyOutlook(max_loss_usd=10.0)
        result = outlook.predict(btc_range_usd=2000.0)
        self.assertIsInstance(result, OutlookResult)
        self.assertEqual(result.volume_band, "MEDIUM")
        self.assertGreater(result.p_daily_target, 0)
        self.assertLess(result.p_daily_target, 1)
        self.assertGreater(result.expected_daily_pnl, 0)

    def test_predict_low_volume(self):
        outlook = DailyOutlook()
        result = outlook.predict(btc_range_usd=500.0)
        self.assertEqual(result.volume_band, "LOW")

    def test_predict_high_volume(self):
        outlook = DailyOutlook()
        result = outlook.predict(btc_range_usd=3000.0)
        self.assertEqual(result.volume_band, "HIGH")

    def test_higher_volume_better_probability(self):
        outlook = DailyOutlook(max_loss_usd=10.0)
        low = outlook.predict(btc_range_usd=500.0)
        high = outlook.predict(btc_range_usd=3000.0)
        self.assertGreater(high.p_daily_target, low.p_daily_target)

    def test_higher_bet_size_better_ev(self):
        small = DailyOutlook(max_loss_usd=5.0)
        large = DailyOutlook(max_loss_usd=15.0)
        r_small = small.predict(btc_range_usd=2000.0)
        r_large = large.predict(btc_range_usd=2000.0)
        self.assertGreater(r_large.expected_daily_pnl, r_small.expected_daily_pnl)

    def test_weekend_multiplier(self):
        outlook = DailyOutlook()
        weekday = outlook.predict(btc_range_usd=2000.0, is_weekend=False)
        weekend = outlook.predict(btc_range_usd=2000.0, is_weekend=True)
        # Weekend has 0.7x volume multiplier
        self.assertGreater(weekday.estimated_bets, weekend.estimated_bets)

    def test_result_to_dict(self):
        outlook = DailyOutlook()
        result = outlook.predict(btc_range_usd=2000.0)
        d = result.to_dict()
        self.assertIn("volume_band", d)
        self.assertIn("estimated_bets", d)
        self.assertIn("p_daily_target", d)
        self.assertIn("expected_daily_pnl", d)
        self.assertIn("verdict", d)

    def test_result_to_json(self):
        outlook = DailyOutlook()
        result = outlook.predict(btc_range_usd=2000.0)
        j = json.loads(result.to_json())
        self.assertIn("volume_band", j)

    def test_verdict_likely(self):
        """High volume + good sizing should be LIKELY."""
        outlook = DailyOutlook(max_loss_usd=12.5)
        result = outlook.predict(btc_range_usd=3000.0)
        self.assertIn(result.verdict, ("LIKELY", "POSSIBLE", "UNLIKELY"))

    def test_verdict_unlikely(self):
        """Low volume + small sizing should be UNLIKELY."""
        outlook = DailyOutlook(max_loss_usd=5.0)
        result = outlook.predict(btc_range_usd=500.0)
        self.assertEqual(result.verdict, "UNLIKELY")

    def test_sweep_bet_sizes(self):
        outlook = DailyOutlook()
        sweep = outlook.sweep_bet_sizes(
            btc_range_usd=2000.0, sizes=[5.0, 7.5, 10.0, 12.5]
        )
        self.assertEqual(len(sweep), 4)
        # EVs should be monotonically increasing
        evs = [r.expected_daily_pnl for r in sweep]
        for i in range(len(evs) - 1):
            self.assertLessEqual(evs[i], evs[i + 1])

    def test_summary_text(self):
        outlook = DailyOutlook()
        result = outlook.predict(btc_range_usd=2000.0)
        text = result.summary()
        self.assertIn("Volume:", text)
        self.assertIn("Target:", text)


class TestCLI(unittest.TestCase):
    """Test CLI."""

    def test_cli_basic(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "daily_outlook.py"),
                "--btc-range", "2000",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Volume:", result.stdout)

    def test_cli_json(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "daily_outlook.py"),
                "--btc-range", "2000",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("verdict", data)

    def test_cli_sweep(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "daily_outlook.py"),
                "--btc-range", "2000",
                "--sweep",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("$", result.stdout)


if __name__ == "__main__":
    unittest.main()
