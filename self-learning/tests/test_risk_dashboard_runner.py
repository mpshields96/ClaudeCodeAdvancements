"""Tests for risk_dashboard_runner.py — unified risk analysis runner.

Runs all 6 Kalshi analytical tools in sequence and produces a single
JSON report. One command, complete picture.
"""
import json
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from risk_dashboard_runner import (
    RiskDashboardConfig,
    RiskDashboard,
)
from edge_decay_detector import BetOutcome


def make_bet_outcomes(n: int, wr: float = 0.933, avg_win: float = 0.90,
                      avg_loss: float = -11.39) -> list[BetOutcome]:
    import random
    random.seed(42)
    outcomes = []
    d = date(2026, 3, 1)
    for i in range(n):
        pnl = avg_win if random.random() < wr else avg_loss
        outcomes.append(BetOutcome(
            date=d + timedelta(days=i // 10),
            pnl=pnl,
            strategy="expiry_sniper_v1",
        ))
    return outcomes


class TestRiskDashboardConfig(unittest.TestCase):
    def test_defaults(self):
        c = RiskDashboardConfig()
        self.assertAlmostEqual(c.bankroll, 178.05)
        self.assertAlmostEqual(c.target, 250.0)

    def test_custom(self):
        c = RiskDashboardConfig(bankroll=200.0, n_sims=500)
        self.assertAlmostEqual(c.bankroll, 200.0)
        self.assertEqual(c.n_sims, 500)


class TestRiskDashboard(unittest.TestCase):
    def setUp(self):
        self.outcomes = make_bet_outcomes(200)
        self.config = RiskDashboardConfig(n_sims=100, seed=42)

    def test_create(self):
        dash = RiskDashboard(self.outcomes, self.config)
        self.assertIsNotNone(dash)

    def test_run_produces_report(self):
        dash = RiskDashboard(self.outcomes, self.config)
        report = dash.run()
        self.assertIsInstance(report, dict)

    def test_report_has_all_sections(self):
        dash = RiskDashboard(self.outcomes, self.config)
        report = dash.run()
        self.assertIn("edge_trend", report)
        self.assertIn("volatility_regime", report)
        self.assertIn("growth_projection", report)
        self.assertIn("cliff_analysis", report)
        self.assertIn("loss_reduction", report)
        self.assertIn("overall_status", report)

    def test_report_json_serializable(self):
        dash = RiskDashboard(self.outcomes, self.config)
        report = dash.run()
        json_str = json.dumps(report)
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertIn("edge_trend", parsed)

    def test_overall_status_present(self):
        dash = RiskDashboard(self.outcomes, self.config)
        report = dash.run()
        status = report["overall_status"]
        self.assertIn("health", status)
        self.assertIn("safety_margin", status)
        self.assertIn("recommended_max_loss", status)
        self.assertIn("summary", status)

    def test_summary_text(self):
        dash = RiskDashboard(self.outcomes, self.config)
        report = dash.run()
        text = dash.summary_text(report)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 50)

    def test_with_few_outcomes(self):
        """Should handle small datasets gracefully."""
        outcomes = make_bet_outcomes(10)
        dash = RiskDashboard(outcomes, self.config)
        report = dash.run()
        self.assertIn("overall_status", report)

    def test_empty_outcomes(self):
        """Should handle empty data without crashing."""
        dash = RiskDashboard([], self.config)
        report = dash.run()
        self.assertIn("overall_status", report)


if __name__ == "__main__":
    unittest.main()
