#!/usr/bin/env python3
"""Tests for sizing_optimizer.py — Portfolio-level bet sizing optimizer."""

import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sizing_optimizer import (
    AssetProfile,
    DailyProjection,
    SizingOptimizer,
    SizingReport,
    VarianceAnalysis,
)


class TestAssetProfile(unittest.TestCase):
    """Test AssetProfile dataclass and computed properties."""

    def test_basic_creation(self):
        ap = AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915)
        self.assertEqual(ap.ticker, "KXBTC")
        self.assertEqual(ap.n_bets, 181)
        self.assertAlmostEqual(ap.win_rate, 0.967)
        self.assertAlmostEqual(ap.avg_price, 0.915)

    def test_net_odds(self):
        ap = AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915)
        # b = (1 - 0.915) / 0.915 = 0.085 / 0.915
        expected = 0.085 / 0.915
        self.assertAlmostEqual(ap.net_odds, expected, places=4)

    def test_kelly_fraction(self):
        ap = AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915)
        b = 0.085 / 0.915
        expected = (0.967 * b - 0.033) / b
        self.assertAlmostEqual(ap.kelly_fraction, expected, places=4)

    def test_ev_per_contract(self):
        ap = AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915)
        expected = 0.967 * 0.085 - 0.033 * 0.915
        self.assertAlmostEqual(ap.ev_per_contract, expected, places=4)

    def test_sd_per_contract(self):
        ap = AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915)
        ev = ap.ev_per_contract
        var = 0.967 * (0.085 - ev) ** 2 + 0.033 * (-0.915 - ev) ** 2
        self.assertAlmostEqual(ap.sd_per_contract, math.sqrt(var), places=4)

    def test_kelly_fraction_positive_edge(self):
        """Kelly fraction should be positive when WR > break-even."""
        ap = AssetProfile(ticker="TEST", n_bets=100, win_rate=0.96, avg_price=0.90)
        self.assertGreater(ap.kelly_fraction, 0)

    def test_kelly_fraction_no_edge(self):
        """Kelly fraction should be near zero or negative when WR is at break-even."""
        # At 90c, break-even WR = 0.90
        ap = AssetProfile(ticker="TEST", n_bets=100, win_rate=0.90, avg_price=0.90)
        self.assertAlmostEqual(ap.kelly_fraction, 0.0, places=2)

    def test_to_dict(self):
        ap = AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915)
        d = ap.to_dict()
        self.assertEqual(d["ticker"], "KXBTC")
        self.assertIn("kelly_fraction", d)
        self.assertIn("ev_per_contract", d)
        self.assertIn("sd_per_contract", d)


class TestSizingOptimizer(unittest.TestCase):
    """Test the core optimizer."""

    def setUp(self):
        self.profiles = [
            AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915),
            AssetProfile(ticker="KXETH", n_bets=134, win_rate=0.963, avg_price=0.915),
            AssetProfile(ticker="KXSOL", n_bets=126, win_rate=0.952, avg_price=0.915),
        ]
        self.optimizer = SizingOptimizer(
            profiles=self.profiles,
            bankroll_usd=190.0,
            bets_per_day=31.5,
        )

    def test_creation(self):
        self.assertEqual(len(self.optimizer.profiles), 3)
        self.assertAlmostEqual(self.optimizer.bankroll_usd, 190.0)
        self.assertAlmostEqual(self.optimizer.bets_per_day, 31.5)

    def test_compute_daily_projection(self):
        proj = self.optimizer.compute_daily_projection(max_loss_usd=7.50)
        self.assertIsInstance(proj, DailyProjection)
        self.assertGreater(proj.daily_ev, 0)
        self.assertGreater(proj.daily_sd, 0)
        self.assertAlmostEqual(proj.max_loss_usd, 7.50)

    def test_daily_projection_scales_with_bet_size(self):
        proj_small = self.optimizer.compute_daily_projection(max_loss_usd=5.0)
        proj_large = self.optimizer.compute_daily_projection(max_loss_usd=15.0)
        self.assertGreater(proj_large.daily_ev, proj_small.daily_ev)

    def test_daily_projection_probability(self):
        proj = self.optimizer.compute_daily_projection(max_loss_usd=7.50)
        # P(5-day avg >= $15) should be between 0 and 1
        self.assertGreater(proj.p_5day_target, 0)
        self.assertLess(proj.p_5day_target, 1)

    def test_variance_analysis(self):
        va = self.optimizer.variance_analysis(
            max_loss_range=[5.0, 7.5, 10.0, 12.5, 15.0]
        )
        self.assertIsInstance(va, VarianceAnalysis)
        self.assertEqual(len(va.projections), 5)

    def test_variance_analysis_monotonic_ev(self):
        """Daily EV should increase with bet size."""
        va = self.optimizer.variance_analysis(
            max_loss_range=[5.0, 7.5, 10.0, 12.5, 15.0]
        )
        evs = [p.daily_ev for p in va.projections]
        for i in range(len(evs) - 1):
            self.assertLessEqual(evs[i], evs[i + 1])

    def test_asset_weighted_sizing(self):
        """Assets with higher Kelly fraction should get larger sizes."""
        sizing = self.optimizer.asset_weighted_sizing(total_budget_usd=30.0)
        self.assertEqual(len(sizing), 3)
        # BTC has highest Kelly, should get largest allocation
        btc_size = sizing["KXBTC"]
        sol_size = sizing["KXSOL"]
        self.assertGreater(btc_size, sol_size)

    def test_asset_weighted_sizing_averages_correctly(self):
        """Weighted average of per-asset sizes should approximate the budget."""
        sizing = self.optimizer.asset_weighted_sizing(total_budget_usd=10.0)
        # BTC gets more than 10, SOL gets less than 10
        self.assertGreater(sizing["KXBTC"], 10.0)
        self.assertLess(sizing["KXSOL"], 10.0)

    def test_optimal_max_loss(self):
        """Find optimal max_loss to hit a daily target."""
        result = self.optimizer.optimal_max_loss(daily_target=15.0)
        self.assertGreater(result, 0)
        # Should be higher than current $7.50 since that can't hit $15/day
        self.assertGreater(result, 7.0)

    def test_optimal_max_loss_unreachable_target(self):
        """Very high target should return max allowed."""
        result = self.optimizer.optimal_max_loss(
            daily_target=500.0, max_allowed=50.0
        )
        self.assertAlmostEqual(result, 50.0)

    def test_kelly_multiple(self):
        """Check Kelly multiple computation."""
        proj = self.optimizer.compute_daily_projection(max_loss_usd=7.50)
        # Should be very small fraction of Kelly (1/10 to 1/20)
        self.assertGreater(proj.kelly_multiple, 0)
        self.assertLess(proj.kelly_multiple, 0.2)


class TestSizingReport(unittest.TestCase):
    """Test full report generation."""

    def setUp(self):
        self.profiles = [
            AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915),
            AssetProfile(ticker="KXETH", n_bets=134, win_rate=0.963, avg_price=0.915),
            AssetProfile(ticker="KXSOL", n_bets=126, win_rate=0.952, avg_price=0.915),
        ]
        self.optimizer = SizingOptimizer(
            profiles=self.profiles,
            bankroll_usd=190.0,
            bets_per_day=31.5,
        )

    def test_generate_report(self):
        report = self.optimizer.generate_report(daily_target=15.0)
        self.assertIsInstance(report, SizingReport)
        self.assertGreater(len(report.asset_profiles), 0)
        self.assertIsNotNone(report.variance_analysis)
        self.assertIsNotNone(report.recommended_max_loss)

    def test_report_to_dict(self):
        report = self.optimizer.generate_report(daily_target=15.0)
        d = report.to_dict()
        self.assertIn("asset_profiles", d)
        self.assertIn("variance_analysis", d)
        self.assertIn("recommended_max_loss", d)
        self.assertIn("daily_target", d)

    def test_report_to_json(self):
        report = self.optimizer.generate_report(daily_target=15.0)
        j = json.loads(report.to_json())
        self.assertIn("asset_profiles", j)

    def test_report_summary_text(self):
        report = self.optimizer.generate_report(daily_target=15.0)
        text = report.summary()
        self.assertIn("KXBTC", text)
        self.assertIn("recommended", text.lower())


class TestDailyProjection(unittest.TestCase):
    """Test DailyProjection computed fields."""

    def test_worst_day_risk(self):
        proj = DailyProjection(
            max_loss_usd=10.0,
            contracts_per_bet=10,
            daily_ev=14.65,
            daily_sd=10.80,
            p_daily_target=0.47,
            p_5day_target=0.47,
            kelly_multiple=0.08,
            bankroll_usd=190.0,
        )
        # 3 losses at $10 = $30
        self.assertAlmostEqual(proj.worst_3loss_day, 30.0)
        # As % of bankroll
        self.assertAlmostEqual(proj.worst_3loss_pct, 30.0 / 190.0 * 100, places=1)


class TestEdgeCases(unittest.TestCase):
    """Edge case handling."""

    def test_single_asset(self):
        profiles = [
            AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915),
        ]
        opt = SizingOptimizer(profiles=profiles, bankroll_usd=190.0, bets_per_day=31.5)
        report = opt.generate_report(daily_target=15.0)
        self.assertEqual(len(report.asset_profiles), 1)

    def test_zero_bets_per_day(self):
        profiles = [
            AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915),
        ]
        with self.assertRaises(ValueError):
            SizingOptimizer(profiles=profiles, bankroll_usd=190.0, bets_per_day=0)

    def test_negative_bankroll(self):
        profiles = [
            AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915),
        ]
        with self.assertRaises(ValueError):
            SizingOptimizer(profiles=profiles, bankroll_usd=-100.0, bets_per_day=31.5)

    def test_very_high_price(self):
        """At 99c, edge should be very small but computation shouldn't break."""
        ap = AssetProfile(ticker="TEST", n_bets=100, win_rate=0.999, avg_price=0.99)
        self.assertGreater(ap.ev_per_contract, 0)
        self.assertGreater(ap.kelly_fraction, 0)

    def test_custom_daily_target(self):
        profiles = [
            AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915),
        ]
        opt = SizingOptimizer(profiles=profiles, bankroll_usd=190.0, bets_per_day=31.5)
        report_15 = opt.generate_report(daily_target=15.0)
        report_25 = opt.generate_report(daily_target=25.0)
        # Higher target should recommend larger bet size
        self.assertGreaterEqual(
            report_25.recommended_max_loss, report_15.recommended_max_loss
        )


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_cli_json_output(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "sizing_optimizer.py"),
                "--bankroll", "190",
                "--target", "15",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("recommended_max_loss", data)

    def test_cli_text_output(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "sizing_optimizer.py"),
                "--bankroll", "190",
                "--target", "15",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("KXBTC", result.stdout)

    def test_cli_custom_assets(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "sizing_optimizer.py"),
                "--bankroll", "190",
                "--target", "15",
                "--assets", "KXBTC:181:0.967:0.915",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["asset_profiles"]), 1)


if __name__ == "__main__":
    unittest.main()
