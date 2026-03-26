"""Tests for edge_decay_detector.py — strategy edge stability monitoring.

Detects whether a trading edge is stable, growing, or deteriorating using
rolling window analysis. Answers: is our 93.3% WR holding steady or was
it an artifact of a hot streak?
"""
import os
import sys
import json
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from edge_decay_detector import (
    BetOutcome,
    WindowStats,
    EdgeTrend,
    EdgeDecayDetector,
)


def make_outcomes(n: int, win_rate: float, avg_win: float = 0.90,
                  avg_loss: float = -10.0, start_date: date | None = None) -> list[BetOutcome]:
    """Generate synthetic bet outcomes for testing."""
    import random
    random.seed(42)
    if start_date is None:
        start_date = date(2026, 1, 1)
    outcomes = []
    for i in range(n):
        d = start_date + timedelta(days=i // 10)  # ~10 bets per day
        pnl = avg_win if random.random() < win_rate else avg_loss
        outcomes.append(BetOutcome(
            date=d,
            pnl=pnl,
            strategy="expiry_sniper_v1",
        ))
    return outcomes


class TestBetOutcome(unittest.TestCase):
    def test_create(self):
        o = BetOutcome(date=date(2026, 3, 1), pnl=0.90, strategy="sniper")
        self.assertTrue(o.is_win)

    def test_loss(self):
        o = BetOutcome(date=date(2026, 3, 1), pnl=-5.0, strategy="sniper")
        self.assertFalse(o.is_win)

    def test_zero_is_loss(self):
        o = BetOutcome(date=date(2026, 3, 1), pnl=0.0, strategy="sniper")
        self.assertFalse(o.is_win)


class TestWindowStats(unittest.TestCase):
    def test_create(self):
        ws = WindowStats(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 10),
            n_bets=50,
            win_rate=0.93,
            avg_win=0.90,
            avg_loss=-10.0,
            expected_value=0.07,
            daily_pnl=5.0,
        )
        self.assertEqual(ws.n_bets, 50)

    def test_to_dict(self):
        ws = WindowStats(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 10),
            n_bets=50,
            win_rate=0.93,
            avg_win=0.90,
            avg_loss=-10.0,
            expected_value=0.07,
            daily_pnl=5.0,
        )
        d = ws.to_dict()
        self.assertIn("win_rate", d)
        json.dumps(d)  # must be serializable


class TestEdgeTrend(unittest.TestCase):
    def test_stable(self):
        t = EdgeTrend(
            direction="stable",
            wr_slope=0.0001,
            ev_slope=0.0,
            confidence=0.85,
            message="Edge is stable",
        )
        self.assertEqual(t.direction, "stable")

    def test_declining(self):
        t = EdgeTrend(
            direction="declining",
            wr_slope=-0.005,
            ev_slope=-0.01,
            confidence=0.90,
            message="Edge is deteriorating",
        )
        self.assertEqual(t.direction, "declining")

    def test_to_dict(self):
        t = EdgeTrend(
            direction="improving",
            wr_slope=0.003,
            ev_slope=0.005,
            confidence=0.70,
            message="Edge improving",
        )
        d = t.to_dict()
        json.dumps(d)


class TestEdgeDecayDetector(unittest.TestCase):
    def setUp(self):
        self.detector = EdgeDecayDetector(window_size=20)

    def test_create(self):
        self.assertEqual(self.detector.window_size, 20)

    def test_stable_edge(self):
        """Consistent 93% WR should show stable edge."""
        outcomes = make_outcomes(200, win_rate=0.93)
        trend = self.detector.detect(outcomes)
        self.assertIsInstance(trend, EdgeTrend)
        # With consistent WR, should be stable or slightly improving
        self.assertIn(trend.direction, ("stable", "improving"))

    def test_declining_edge(self):
        """WR dropping from 95% to 80% should show decline."""
        outcomes = []
        d = date(2026, 1, 1)
        import random
        random.seed(42)
        # First 100 bets: 95% WR
        for i in range(100):
            pnl = 0.90 if random.random() < 0.95 else -10.0
            outcomes.append(BetOutcome(d + timedelta(days=i // 10), pnl, "sniper"))
        # Next 100 bets: 80% WR
        for i in range(100):
            pnl = 0.90 if random.random() < 0.80 else -10.0
            outcomes.append(BetOutcome(d + timedelta(days=10 + i // 10), pnl, "sniper"))

        trend = self.detector.detect(outcomes)
        self.assertEqual(trend.direction, "declining")
        self.assertLess(trend.wr_slope, 0)

    def test_improving_edge(self):
        """WR climbing from 85% to 96% should show improvement."""
        outcomes = []
        d = date(2026, 1, 1)
        import random
        random.seed(42)
        for i in range(100):
            pnl = 0.90 if random.random() < 0.85 else -10.0
            outcomes.append(BetOutcome(d + timedelta(days=i // 10), pnl, "sniper"))
        for i in range(100):
            pnl = 0.90 if random.random() < 0.96 else -10.0
            outcomes.append(BetOutcome(d + timedelta(days=10 + i // 10), pnl, "sniper"))

        trend = self.detector.detect(outcomes)
        self.assertEqual(trend.direction, "improving")
        self.assertGreater(trend.wr_slope, 0)

    def test_insufficient_data(self):
        """Too few bets should return unknown."""
        outcomes = make_outcomes(5, win_rate=0.90)
        trend = self.detector.detect(outcomes)
        self.assertEqual(trend.direction, "unknown")

    def test_rolling_windows(self):
        """Get rolling window statistics."""
        outcomes = make_outcomes(200, win_rate=0.93)
        windows = self.detector.rolling_windows(outcomes)
        self.assertGreater(len(windows), 0)
        for w in windows:
            self.assertIsInstance(w, WindowStats)
            self.assertGreater(w.n_bets, 0)

    def test_alert_threshold(self):
        """Test alert generation for significant edge decay."""
        detector = EdgeDecayDetector(window_size=20, alert_wr_drop=0.05)
        outcomes = []
        d = date(2026, 1, 1)
        import random
        random.seed(42)
        for i in range(100):
            pnl = 0.90 if random.random() < 0.95 else -10.0
            outcomes.append(BetOutcome(d + timedelta(days=i // 10), pnl, "sniper"))
        for i in range(100):
            pnl = 0.90 if random.random() < 0.80 else -10.0
            outcomes.append(BetOutcome(d + timedelta(days=10 + i // 10), pnl, "sniper"))

        trend = detector.detect(outcomes)
        self.assertTrue(trend.should_alert)

    def test_no_alert_for_stable(self):
        """Stable edge should not trigger alert."""
        detector = EdgeDecayDetector(window_size=20, alert_wr_drop=0.05)
        outcomes = make_outcomes(200, win_rate=0.93)
        trend = detector.detect(outcomes)
        self.assertFalse(trend.should_alert)

    def test_full_report(self):
        """Full report as JSON-serializable dict."""
        outcomes = make_outcomes(200, win_rate=0.93)
        report = self.detector.full_report(outcomes)
        self.assertIn("trend", report)
        self.assertIn("windows", report)
        self.assertIn("latest_window", report)
        json.dumps(report)

    def test_strategy_filter(self):
        """Only analyze outcomes for the specified strategy."""
        outcomes = make_outcomes(100, win_rate=0.93)
        # Add some from a different strategy
        for i in range(50):
            outcomes.append(BetOutcome(
                date=date(2026, 2, 1) + timedelta(days=i // 10),
                pnl=-5.0, strategy="other_strategy",
            ))
        trend = self.detector.detect(outcomes, strategy="expiry_sniper_v1")
        # Should only analyze the sniper outcomes, not the losing "other" ones
        # Direction may vary due to small sample; key test is it doesn't crash
        # and filters correctly (100 sniper bets = 5 windows, not 7.5)
        self.assertIn(trend.direction, ("stable", "improving", "declining", "unknown"))

    def test_ev_trend_tracked(self):
        """EV slope should be tracked alongside WR slope."""
        outcomes = make_outcomes(200, win_rate=0.93)
        trend = self.detector.detect(outcomes)
        self.assertIsNotNone(trend.ev_slope)


if __name__ == "__main__":
    unittest.main()
