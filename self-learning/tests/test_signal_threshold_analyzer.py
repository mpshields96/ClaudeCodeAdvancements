"""Tests for signal_threshold_analyzer.py — drift threshold sensitivity analysis.

Models how bet frequency and WR change at various drift thresholds.
Answers: if we loosen from 0.1% to 0.05%, how many more bets fire?
What's the WR/frequency tradeoff curve?
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from signal_threshold_analyzer import (
    ThresholdPoint,
    SignalThresholdAnalyzer,
    ThresholdReport,
)


class TestThresholdPoint(unittest.TestCase):
    """Test threshold data point."""

    def test_basic_creation(self):
        p = ThresholdPoint(
            threshold_pct=0.10, bets_per_day=64, win_rate=0.933,
            avg_win=0.90, avg_loss=8.0,
        )
        self.assertAlmostEqual(p.threshold_pct, 0.10)

    def test_expected_daily_pnl(self):
        p = ThresholdPoint(
            threshold_pct=0.10, bets_per_day=64, win_rate=0.933,
            avg_win=0.90, avg_loss=8.0,
        )
        # EV/bet = 0.933*0.90 - 0.067*8.0 = 0.8397 - 0.536 = 0.3037
        # Daily = 64 * 0.3037 = 19.44
        self.assertAlmostEqual(p.expected_daily_pnl(), 64 * 0.3037, places=1)

    def test_negative_ev(self):
        p = ThresholdPoint(
            threshold_pct=0.01, bets_per_day=200, win_rate=0.85,
            avg_win=0.90, avg_loss=8.0,
        )
        # EV/bet = 0.85*0.90 - 0.15*8.0 = 0.765 - 1.2 = -0.435
        self.assertLess(p.expected_daily_pnl(), 0)

    def test_edge_per_bet(self):
        p = ThresholdPoint(
            threshold_pct=0.10, bets_per_day=64, win_rate=0.933,
            avg_win=0.90, avg_loss=8.0,
        )
        self.assertAlmostEqual(p.edge_per_bet(), 0.3037, places=3)


class TestSignalThresholdAnalyzer(unittest.TestCase):
    """Test the analyzer with calibration data."""

    def _default_analyzer(self):
        # Calibration: observed data at 0.10% threshold
        calibration = [
            ThresholdPoint(threshold_pct=0.10, bets_per_day=64, win_rate=0.933,
                           avg_win=0.90, avg_loss=8.0),
        ]
        return SignalThresholdAnalyzer(calibration)

    def test_creation(self):
        a = self._default_analyzer()
        self.assertEqual(len(a.calibration), 1)

    def test_sweep_returns_points(self):
        a = self._default_analyzer()
        report = a.sweep()
        self.assertGreater(len(report.points), 0)

    def test_sweep_includes_calibrated_threshold(self):
        a = self._default_analyzer()
        report = a.sweep()
        thresholds = [p.threshold_pct for p in report.points]
        self.assertIn(0.10, thresholds)

    def test_lower_threshold_more_bets(self):
        a = self._default_analyzer()
        report = a.sweep()
        pts = {round(p.threshold_pct, 3): p for p in report.points}
        if 0.05 in pts and 0.10 in pts:
            self.assertGreater(pts[0.05].bets_per_day, pts[0.10].bets_per_day)

    def test_lower_threshold_lower_wr(self):
        a = self._default_analyzer()
        report = a.sweep()
        pts = {round(p.threshold_pct, 3): p for p in report.points}
        if 0.05 in pts and 0.10 in pts:
            self.assertLess(pts[0.05].win_rate, pts[0.10].win_rate)

    def test_optimal_threshold_exists(self):
        a = self._default_analyzer()
        report = a.sweep()
        self.assertIsNotNone(report.optimal_threshold)
        self.assertGreater(report.optimal_daily_pnl, 0)

    def test_report_has_recommendation(self):
        a = self._default_analyzer()
        report = a.sweep()
        self.assertIsInstance(report.recommendation, str)
        self.assertGreater(len(report.recommendation), 0)

    def test_multiple_calibration_points(self):
        calibration = [
            ThresholdPoint(threshold_pct=0.10, bets_per_day=64, win_rate=0.933,
                           avg_win=0.90, avg_loss=8.0),
            ThresholdPoint(threshold_pct=0.15, bets_per_day=45, win_rate=0.950,
                           avg_win=0.90, avg_loss=8.0),
        ]
        a = SignalThresholdAnalyzer(calibration)
        report = a.sweep()
        self.assertGreater(len(report.points), 2)


class TestSignalThresholdAnalyzerJSON(unittest.TestCase):
    """Test JSON export."""

    def test_to_dict(self):
        calibration = [
            ThresholdPoint(threshold_pct=0.10, bets_per_day=64, win_rate=0.933,
                           avg_win=0.90, avg_loss=8.0),
        ]
        a = SignalThresholdAnalyzer(calibration)
        d = a.to_dict()
        self.assertIn("calibration", d)
        self.assertIn("sweep", d)
        self.assertIn("optimal", d)

    def test_summary_text(self):
        calibration = [
            ThresholdPoint(threshold_pct=0.10, bets_per_day=64, win_rate=0.933,
                           avg_win=0.90, avg_loss=8.0),
        ]
        a = SignalThresholdAnalyzer(calibration)
        text = a.summary_text()
        self.assertIn("THRESHOLD", text)
        self.assertIn("0.10", text)


if __name__ == "__main__":
    unittest.main()
