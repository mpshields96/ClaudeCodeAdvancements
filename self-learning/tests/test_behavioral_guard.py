#!/usr/bin/env python3
"""Tests for behavioral_guard.py — MT-37 Layer 5: Behavioral bias detection."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from behavioral_guard import (
    Bias,
    BiasAlert,
    BiasSeverity,
    BehavioralGuard,
    detect_disposition_effect,
    detect_loss_aversion,
    detect_recency_bias,
    detect_home_bias,
    detect_overconfidence,
)


class TestDispositionEffect(unittest.TestCase):
    """Test disposition effect detection (selling winners, holding losers)."""

    def test_classic_disposition(self):
        # Selling a winner while holding a larger loser
        trades = [
            {"ticker": "AAPL", "action": "SELL", "gain_pct": 0.20},
        ]
        holdings_with_losses = [
            {"ticker": "META", "unrealized_gain_pct": -0.30},
        ]
        alert = detect_disposition_effect(trades, holdings_with_losses)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.bias, Bias.DISPOSITION_EFFECT)

    def test_no_disposition_when_selling_loser(self):
        trades = [
            {"ticker": "META", "action": "SELL", "gain_pct": -0.10},
        ]
        holdings_with_losses = []
        alert = detect_disposition_effect(trades, holdings_with_losses)
        self.assertIsNone(alert)

    def test_no_disposition_when_no_unrealized_losses(self):
        trades = [
            {"ticker": "AAPL", "action": "SELL", "gain_pct": 0.20},
        ]
        holdings_with_losses = []
        alert = detect_disposition_effect(trades, holdings_with_losses)
        self.assertIsNone(alert)

    def test_buy_action_ignored(self):
        trades = [
            {"ticker": "AAPL", "action": "BUY", "gain_pct": 0.0},
        ]
        holdings_with_losses = [
            {"ticker": "META", "unrealized_gain_pct": -0.30},
        ]
        alert = detect_disposition_effect(trades, holdings_with_losses)
        self.assertIsNone(alert)


class TestLossAversion(unittest.TestCase):
    """Test loss aversion detection (Kahneman & Tversky 1979)."""

    def test_loss_aversion_detected(self):
        # Recent large loss followed by risk-averse behavior
        recent_loss_pct = -0.15
        proposed_action = "reduce_equity"
        alert = detect_loss_aversion(recent_loss_pct, proposed_action)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.bias, Bias.LOSS_AVERSION)

    def test_no_loss_aversion_without_recent_loss(self):
        alert = detect_loss_aversion(0.05, "reduce_equity")
        self.assertIsNone(alert)

    def test_no_loss_aversion_without_risk_reduction(self):
        alert = detect_loss_aversion(-0.15, "hold")
        self.assertIsNone(alert)

    def test_small_loss_no_trigger(self):
        alert = detect_loss_aversion(-0.02, "reduce_equity")
        self.assertIsNone(alert)


class TestRecencyBias(unittest.TestCase):
    """Test recency bias detection."""

    def test_recency_bias_chasing_returns(self):
        # Buying into recent top performer
        recent_top = {"ticker": "NVDA", "return_3m": 0.40}
        proposed_buy = "NVDA"
        alert = detect_recency_bias(recent_top, proposed_buy)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.bias, Bias.RECENCY_BIAS)

    def test_no_bias_different_ticker(self):
        recent_top = {"ticker": "NVDA", "return_3m": 0.40}
        proposed_buy = "VTI"
        alert = detect_recency_bias(recent_top, proposed_buy)
        self.assertIsNone(alert)

    def test_no_bias_modest_returns(self):
        recent_top = {"ticker": "VTI", "return_3m": 0.05}
        proposed_buy = "VTI"
        alert = detect_recency_bias(recent_top, proposed_buy)
        self.assertIsNone(alert)


class TestHomeBias(unittest.TestCase):
    """Test home country bias detection."""

    def test_home_bias_detected(self):
        weights = {"VTI": 0.85, "VXUS": 0.10, "BND": 0.05}
        domestic_tickers = {"VTI", "BND"}
        alert = detect_home_bias(weights, domestic_tickers, threshold=0.70)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.bias, Bias.HOME_BIAS)

    def test_no_home_bias_when_diversified(self):
        weights = {"VTI": 0.50, "VXUS": 0.30, "BND": 0.20}
        domestic_tickers = {"VTI", "BND"}
        alert = detect_home_bias(weights, domestic_tickers, threshold=0.80)
        self.assertIsNone(alert)

    def test_edge_case_all_domestic(self):
        weights = {"VTI": 0.60, "BND": 0.40}
        domestic_tickers = {"VTI", "BND"}
        alert = detect_home_bias(weights, domestic_tickers, threshold=0.70)
        self.assertIsNotNone(alert)


class TestOverconfidence(unittest.TestCase):
    """Test overconfidence detection (excessive trading)."""

    def test_overconfidence_high_turnover(self):
        alert = detect_overconfidence(trades_per_month=15, threshold=10)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.bias, Bias.OVERCONFIDENCE)

    def test_no_overconfidence_normal_trading(self):
        alert = detect_overconfidence(trades_per_month=3, threshold=10)
        self.assertIsNone(alert)

    def test_threshold_exact(self):
        alert = detect_overconfidence(trades_per_month=10, threshold=10)
        self.assertIsNotNone(alert)


class TestBehavioralGuard(unittest.TestCase):
    """Test the full behavioral guard orchestrator."""

    def test_guard_runs_all_checks(self):
        guard = BehavioralGuard()
        context = {
            "trades": [
                {"ticker": "AAPL", "action": "SELL", "gain_pct": 0.25},
            ],
            "holdings_with_losses": [
                {"ticker": "META", "unrealized_gain_pct": -0.35},
            ],
            "recent_loss_pct": -0.18,
            "proposed_action": "reduce_equity",
            "weights": {"VTI": 0.90, "VXUS": 0.10},
            "domestic_tickers": {"VTI"},
            "trades_per_month": 20,
        }
        alerts = guard.scan(context)
        bias_types = {a.bias for a in alerts}
        # Should detect multiple biases
        self.assertGreater(len(alerts), 0)

    def test_guard_no_alerts_clean_context(self):
        guard = BehavioralGuard()
        context = {
            "trades": [],
            "holdings_with_losses": [],
            "recent_loss_pct": 0.0,
            "proposed_action": "hold",
            "weights": {"VTI": 0.50, "VXUS": 0.30, "BND": 0.20},
            "domestic_tickers": {"VTI", "BND"},
            "trades_per_month": 1,
        }
        alerts = guard.scan(context)
        self.assertEqual(len(alerts), 0)

    def test_guard_summary_text(self):
        guard = BehavioralGuard()
        context = {
            "trades": [{"ticker": "AAPL", "action": "SELL", "gain_pct": 0.25}],
            "holdings_with_losses": [{"ticker": "META", "unrealized_gain_pct": -0.35}],
            "recent_loss_pct": 0.0,
            "proposed_action": "hold",
            "weights": {},
            "domestic_tickers": set(),
            "trades_per_month": 0,
        }
        alerts = guard.scan(context)
        text = guard.summary_text(alerts)
        self.assertIsInstance(text, str)

    def test_guard_to_dict(self):
        guard = BehavioralGuard()
        context = {
            "trades": [],
            "holdings_with_losses": [],
            "recent_loss_pct": -0.20,
            "proposed_action": "reduce_equity",
            "weights": {},
            "domestic_tickers": set(),
            "trades_per_month": 0,
        }
        alerts = guard.scan(context)
        dicts = guard.to_dict(alerts)
        self.assertIsInstance(dicts, list)
        if dicts:
            self.assertIn("bias", dicts[0])
            self.assertIn("severity", dicts[0])
            self.assertIn("recommendation", dicts[0])

    def test_alert_severity_levels(self):
        alert = BiasAlert(
            bias=Bias.LOSS_AVERSION,
            severity=BiasSeverity.HIGH,
            message="Test",
            recommendation="Test rec",
        )
        self.assertEqual(alert.severity, BiasSeverity.HIGH)


if __name__ == "__main__":
    unittest.main()
