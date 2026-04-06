"""Tests for volatility_regime_classifier.py — market regime detection.

Classifies current market conditions into LOW/NORMAL/HIGH volatility
regimes based on recent bet outcome distribution. Informs strategy
parameter adjustment (tighter stops in high vol, wider in low vol).
"""
from __future__ import annotations
import json
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from volatility_regime_classifier import (
    Regime,
    RegimeClassification,
    OutcomeWindow,
    VolatilityRegimeClassifier,
)


def make_outcomes(n: int, avg_win: float = 0.90, avg_loss: float = -10.0,
                  win_rate: float = 0.93, start: date | None = None) -> list[float]:
    """Generate synthetic P&L values."""
    import random
    random.seed(42)
    if start is None:
        start = date(2026, 1, 1)
    return [avg_win if random.random() < win_rate else avg_loss for _ in range(n)]


class TestRegime(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Regime.LOW, "low")
        self.assertEqual(Regime.NORMAL, "normal")
        self.assertEqual(Regime.HIGH, "high")


class TestRegimeClassification(unittest.TestCase):
    def test_create(self):
        rc = RegimeClassification(
            regime=Regime.NORMAL,
            volatility=27.0,
            vol_percentile=0.50,
            loss_frequency=0.067,
            avg_loss_magnitude=11.39,
            confidence=0.85,
            message="Normal volatility regime",
        )
        self.assertEqual(rc.regime, Regime.NORMAL)

    def test_to_dict(self):
        rc = RegimeClassification(
            regime=Regime.HIGH, volatility=45.0, vol_percentile=0.90,
            loss_frequency=0.12, avg_loss_magnitude=15.0,
            confidence=0.90, message="High vol",
        )
        d = rc.to_dict()
        json.dumps(d)
        self.assertEqual(d["regime"], "high")

    def test_summary(self):
        rc = RegimeClassification(
            regime=Regime.LOW, volatility=15.0, vol_percentile=0.20,
            loss_frequency=0.04, avg_loss_magnitude=8.0,
            confidence=0.80, message="Low vol",
        )
        s = rc.summary()
        self.assertIn("LOW", s.upper())


class TestOutcomeWindow(unittest.TestCase):
    def test_from_pnl_values(self):
        pnls = make_outcomes(100)
        w = OutcomeWindow.from_pnl_values(pnls)
        self.assertEqual(w.n_bets, 100)
        self.assertGreater(w.volatility, 0)

    def test_empty(self):
        w = OutcomeWindow.from_pnl_values([])
        self.assertEqual(w.n_bets, 0)
        self.assertAlmostEqual(w.volatility, 0.0)

    def test_to_dict(self):
        pnls = make_outcomes(50)
        w = OutcomeWindow.from_pnl_values(pnls)
        d = w.to_dict()
        json.dumps(d)


class TestVolatilityRegimeClassifier(unittest.TestCase):
    def test_create(self):
        c = VolatilityRegimeClassifier()
        self.assertIsNotNone(c)

    def test_classify_normal(self):
        """Consistent WR should be normal regime."""
        pnls = make_outcomes(200, win_rate=0.93)
        c = VolatilityRegimeClassifier()
        result = c.classify(pnls)
        self.assertIsInstance(result, RegimeClassification)
        self.assertIn(result.regime, (Regime.LOW, Regime.NORMAL))

    def test_classify_high_vol(self):
        """Large losses mixed in should push toward high regime."""
        import random
        random.seed(42)
        pnls = []
        for _ in range(200):
            if random.random() < 0.80:  # lower WR
                pnls.append(0.90)
            else:
                pnls.append(-20.0)  # larger losses
        c = VolatilityRegimeClassifier()
        result = c.classify(pnls)
        self.assertEqual(result.regime, Regime.HIGH)

    def test_classify_low_vol(self):
        """All wins = low volatility."""
        pnls = [0.90] * 200
        c = VolatilityRegimeClassifier()
        result = c.classify(pnls)
        self.assertEqual(result.regime, Regime.LOW)

    def test_insufficient_data(self):
        """Too few outcomes should return NORMAL with low confidence."""
        pnls = [0.90, -10.0]
        c = VolatilityRegimeClassifier()
        result = c.classify(pnls)
        self.assertLess(result.confidence, 0.5)

    def test_rolling_regimes(self):
        """Classify regimes over rolling windows."""
        pnls = make_outcomes(300, win_rate=0.93)
        c = VolatilityRegimeClassifier(window_size=50)
        regimes = c.rolling_classify(pnls)
        self.assertGreater(len(regimes), 0)
        for r in regimes:
            self.assertIsInstance(r, RegimeClassification)

    def test_parameter_recommendations(self):
        """Get strategy parameter recommendations for each regime."""
        c = VolatilityRegimeClassifier()
        for regime in (Regime.LOW, Regime.NORMAL, Regime.HIGH):
            rec = c.recommend_params(regime)
            self.assertIn("max_loss", rec)
            self.assertIn("volume_adjustment", rec)
            self.assertIn("rationale", rec)

    def test_high_vol_recommends_tighter_stops(self):
        """High vol should recommend lower max_loss (tighter stops)."""
        c = VolatilityRegimeClassifier()
        low_rec = c.recommend_params(Regime.LOW)
        high_rec = c.recommend_params(Regime.HIGH)
        self.assertLess(high_rec["max_loss"], low_rec["max_loss"])

    def test_full_report(self):
        pnls = make_outcomes(200, win_rate=0.93)
        c = VolatilityRegimeClassifier()
        report = c.full_report(pnls)
        self.assertIn("current_regime", report)
        self.assertIn("recommendations", report)
        self.assertIn("window_stats", report)
        json.dumps(report)


if __name__ == "__main__":
    unittest.main()
