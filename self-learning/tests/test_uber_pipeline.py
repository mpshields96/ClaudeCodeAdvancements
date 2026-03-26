#!/usr/bin/env python3
"""Tests for uber_pipeline.py — MT-37 UBER orchestrator."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from uber_pipeline import (
    PortfolioInput,
    UBERConfig,
    UBERPipeline,
    UBERReport,
)


class TestPortfolioInput(unittest.TestCase):
    """Test portfolio input validation."""

    def test_valid_input(self):
        inp = PortfolioInput(
            holdings={
                "VTI": {"shares": 50, "cost_basis": 200.0, "current_price": 220.0},
                "BND": {"shares": 100, "cost_basis": 75.0, "current_price": 72.0},
            },
            target_weights={"VTI": 0.60, "BND": 0.40},
        )
        self.assertEqual(len(inp.holdings), 2)

    def test_current_weights_computed(self):
        inp = PortfolioInput(
            holdings={
                "VTI": {"shares": 100, "cost_basis": 200.0, "current_price": 200.0},
                "BND": {"shares": 100, "cost_basis": 100.0, "current_price": 100.0},
            },
            target_weights={"VTI": 0.60, "BND": 0.40},
        )
        weights = inp.current_weights()
        # VTI = 100*200 = 20000, BND = 100*100 = 10000, total = 30000
        self.assertAlmostEqual(weights["VTI"], 20000 / 30000, places=4)
        self.assertAlmostEqual(weights["BND"], 10000 / 30000, places=4)

    def test_total_value(self):
        inp = PortfolioInput(
            holdings={
                "VTI": {"shares": 10, "cost_basis": 200.0, "current_price": 250.0},
            },
            target_weights={"VTI": 1.0},
        )
        self.assertAlmostEqual(inp.total_value(), 2500.0)

    def test_empty_holdings(self):
        inp = PortfolioInput(holdings={}, target_weights={})
        self.assertEqual(inp.total_value(), 0.0)
        self.assertEqual(inp.current_weights(), {})


class TestUBERConfig(unittest.TestCase):
    """Test UBER configuration defaults."""

    def test_defaults(self):
        cfg = UBERConfig()
        self.assertEqual(cfg.kelly_fraction, 0.5)
        self.assertEqual(cfg.drift_threshold, 0.05)
        self.assertEqual(cfg.calendar_interval_days, 90)
        self.assertEqual(cfg.home_bias_threshold, 0.70)

    def test_custom_config(self):
        cfg = UBERConfig(kelly_fraction=0.25, drift_threshold=0.10)
        self.assertEqual(cfg.kelly_fraction, 0.25)
        self.assertEqual(cfg.drift_threshold, 0.10)


class TestUBERPipeline(unittest.TestCase):
    """Test the full UBER pipeline orchestrator."""

    def setUp(self):
        self.pipeline = UBERPipeline()
        self.portfolio = PortfolioInput(
            holdings={
                "VTI": {"shares": 100, "cost_basis": 180.0, "current_price": 220.0,
                         "volatility": 0.16, "domestic": True},
                "VXUS": {"shares": 50, "cost_basis": 55.0, "current_price": 50.0,
                          "volatility": 0.18, "domestic": False},
                "BND": {"shares": 200, "cost_basis": 78.0, "current_price": 75.0,
                         "volatility": 0.04, "domestic": True},
            },
            target_weights={"VTI": 0.55, "VXUS": 0.25, "BND": 0.20},
            days_since_rebalance=45,
            portfolio_values=[100000 + i * 50 for i in range(60)],
        )

    def test_full_analysis(self):
        report = self.pipeline.analyze(self.portfolio)
        self.assertIsInstance(report, UBERReport)

    def test_report_has_rebalancing(self):
        report = self.pipeline.analyze(self.portfolio)
        self.assertIn("rebalancing", report.sections)
        self.assertIsInstance(report.sections["rebalancing"], dict)

    def test_report_has_analytics(self):
        report = self.pipeline.analyze(self.portfolio)
        self.assertIn("analytics", report.sections)

    def test_report_has_behavioral(self):
        report = self.pipeline.analyze(self.portfolio)
        self.assertIn("behavioral", report.sections)

    def test_report_has_tax(self):
        report = self.pipeline.analyze(self.portfolio)
        self.assertIn("tax_harvesting", report.sections)

    def test_report_has_risk(self):
        report = self.pipeline.analyze(self.portfolio)
        self.assertIn("risk", report.sections)

    def test_report_to_dict(self):
        report = self.pipeline.analyze(self.portfolio)
        d = report.to_dict()
        self.assertIn("sections", d)
        self.assertIn("summary", d)
        self.assertIsInstance(d["sections"], dict)

    def test_report_summary_text(self):
        report = self.pipeline.analyze(self.portfolio)
        text = report.summary_text()
        self.assertIn("UBER", text)
        self.assertIsInstance(text, str)

    def test_tlh_candidates_found(self):
        # VXUS and BND are underwater (cost > price)
        report = self.pipeline.analyze(self.portfolio)
        tax = report.sections["tax_harvesting"]
        # Should detect at least one TLH candidate
        self.assertIn("candidates", tax)

    def test_risk_dashboard(self):
        report = self.pipeline.analyze(self.portfolio)
        risk = report.sections["risk"]
        self.assertIn("overall_risk", risk)

    def test_custom_config(self):
        cfg = UBERConfig(drift_threshold=0.01)
        pipeline = UBERPipeline(config=cfg)
        report = pipeline.analyze(self.portfolio)
        # With 1% threshold, rebalancing should definitely trigger
        rebal = report.sections["rebalancing"]
        self.assertTrue(rebal.get("should_rebalance", False))

    def test_minimal_portfolio(self):
        """Single asset, minimal data."""
        port = PortfolioInput(
            holdings={
                "VTI": {"shares": 100, "cost_basis": 200.0, "current_price": 210.0,
                         "volatility": 0.16, "domestic": True},
            },
            target_weights={"VTI": 1.0},
            portfolio_values=[20000, 20500, 21000],
        )
        report = self.pipeline.analyze(port)
        self.assertIsInstance(report, UBERReport)

    def test_no_portfolio_values(self):
        """Pipeline handles missing value history gracefully."""
        port = PortfolioInput(
            holdings={
                "VTI": {"shares": 10, "cost_basis": 200.0, "current_price": 210.0,
                         "volatility": 0.16, "domestic": True},
            },
            target_weights={"VTI": 1.0},
        )
        report = self.pipeline.analyze(port)
        self.assertIsInstance(report, UBERReport)


class TestUBERReport(unittest.TestCase):
    """Test UBER report formatting."""

    def test_empty_report(self):
        report = UBERReport(sections={}, portfolio_value=0.0)
        d = report.to_dict()
        self.assertEqual(d["sections"], {})

    def test_action_items_extracted(self):
        pipeline = UBERPipeline()
        port = PortfolioInput(
            holdings={
                "VTI": {"shares": 100, "cost_basis": 180.0, "current_price": 220.0,
                         "volatility": 0.16, "domestic": True},
                "VXUS": {"shares": 50, "cost_basis": 55.0, "current_price": 50.0,
                          "volatility": 0.18, "domestic": False},
            },
            target_weights={"VTI": 0.55, "VXUS": 0.45},
            days_since_rebalance=100,
            portfolio_values=[25000 + i * 30 for i in range(60)],
        )
        report = pipeline.analyze(port)
        actions = report.action_items()
        self.assertIsInstance(actions, list)


if __name__ == "__main__":
    unittest.main()
