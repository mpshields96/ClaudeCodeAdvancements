#!/usr/bin/env python3
"""Tests for portfolio_report.py — MT-37 Layer 5: Portfolio analytics."""
import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from portfolio_report import (
    AssetReport,
    PortfolioReport,
    RiskAttribution,
    annualized_return,
    compute_sharpe,
    max_drawdown,
    portfolio_analytics,
    risk_attribution,
    sortino_ratio,
)


class TestAnnualizedReturn(unittest.TestCase):
    """Test annualized return calculation."""

    def test_simple_return(self):
        # 10% over 1 year
        result = annualized_return([100, 110], periods_per_year=1)
        self.assertAlmostEqual(result, 0.10, places=2)

    def test_multi_period(self):
        # 252 daily values, ~10% total
        values = [100 + i * (10 / 251) for i in range(252)]
        result = annualized_return(values, periods_per_year=252)
        self.assertGreater(result, 0)

    def test_negative_return(self):
        result = annualized_return([100, 90], periods_per_year=1)
        self.assertAlmostEqual(result, -0.10, places=2)

    def test_insufficient_data(self):
        result = annualized_return([100], periods_per_year=252)
        self.assertEqual(result, 0.0)

    def test_empty_data(self):
        result = annualized_return([], periods_per_year=252)
        self.assertEqual(result, 0.0)


class TestSharpeRatio(unittest.TestCase):
    """Test Sharpe ratio calculation."""

    def test_positive_sharpe(self):
        # Steadily increasing portfolio
        returns = [0.01] * 50  # 1% daily
        sharpe = compute_sharpe(returns, risk_free_annual=0.05)
        self.assertGreater(sharpe, 0)

    def test_zero_volatility(self):
        # All same return -> infinite sharpe, capped
        returns = [0.01] * 10
        sharpe = compute_sharpe(returns, risk_free_annual=0.0)
        # With zero vol, returns inf or capped
        self.assertGreater(sharpe, 0)

    def test_negative_excess_return(self):
        returns = [0.0001] * 50  # Tiny returns
        sharpe = compute_sharpe(returns, risk_free_annual=0.10)
        self.assertLess(sharpe, 0)

    def test_insufficient_data(self):
        sharpe = compute_sharpe([0.01], risk_free_annual=0.05)
        self.assertEqual(sharpe, 0.0)


class TestSortinoRatio(unittest.TestCase):
    """Test Sortino ratio calculation."""

    def test_no_downside(self):
        returns = [0.01, 0.02, 0.015, 0.01, 0.025]
        ratio = sortino_ratio(returns, risk_free_annual=0.0)
        # No downside -> high ratio
        self.assertGreater(ratio, 0)

    def test_with_downside(self):
        returns = [0.02, -0.03, 0.01, -0.02, 0.03]
        ratio = sortino_ratio(returns, risk_free_annual=0.0)
        self.assertIsInstance(ratio, float)

    def test_insufficient_data(self):
        ratio = sortino_ratio([], risk_free_annual=0.0)
        self.assertEqual(ratio, 0.0)


class TestMaxDrawdown(unittest.TestCase):
    """Test max drawdown calculation."""

    def test_no_drawdown(self):
        values = [100, 101, 102, 103, 104]
        self.assertAlmostEqual(max_drawdown(values), 0.0)

    def test_simple_drawdown(self):
        values = [100, 110, 90, 95]
        # Peak 110, trough 90 -> 18.18%
        dd = max_drawdown(values)
        self.assertAlmostEqual(dd, (110 - 90) / 110, places=4)

    def test_multiple_drawdowns_returns_max(self):
        values = [100, 110, 100, 120, 90, 115]
        dd = max_drawdown(values)
        # Peak 120, trough 90 -> 25%
        self.assertAlmostEqual(dd, 30 / 120, places=4)

    def test_empty_input(self):
        self.assertEqual(max_drawdown([]), 0.0)


class TestRiskAttribution(unittest.TestCase):
    """Test risk attribution / decomposition."""

    def test_basic_attribution(self):
        weights = {"VTI": 0.60, "BND": 0.40}
        vols = {"VTI": 0.16, "BND": 0.04}
        attr = risk_attribution(weights, vols)
        self.assertIn("VTI", attr.contributions)
        self.assertIn("BND", attr.contributions)
        # VTI should contribute more risk
        self.assertGreater(attr.contributions["VTI"], attr.contributions["BND"])

    def test_contributions_sum_to_one(self):
        weights = {"A": 0.50, "B": 0.30, "C": 0.20}
        vols = {"A": 0.20, "B": 0.15, "C": 0.10}
        attr = risk_attribution(weights, vols)
        total = sum(attr.contributions.values())
        self.assertAlmostEqual(total, 1.0, places=4)

    def test_single_asset(self):
        attr = risk_attribution({"VTI": 1.0}, {"VTI": 0.16})
        self.assertAlmostEqual(attr.contributions["VTI"], 1.0)

    def test_to_dict(self):
        weights = {"A": 0.60, "B": 0.40}
        vols = {"A": 0.20, "B": 0.05}
        attr = risk_attribution(weights, vols)
        d = attr.to_dict()
        self.assertIn("contributions", d)
        self.assertIn("portfolio_vol", d)


class TestPortfolioAnalytics(unittest.TestCase):
    """Test the full portfolio analytics pipeline."""

    def test_basic_report(self):
        holdings = {
            "VTI": {"weight": 0.60, "volatility": 0.16},
            "BND": {"weight": 0.40, "volatility": 0.04},
        }
        # Simulate 100 daily values
        values = [100000 + i * 50 for i in range(100)]
        report = portfolio_analytics(holdings, values, risk_free_annual=0.05)
        self.assertIsInstance(report, PortfolioReport)
        self.assertGreater(report.annualized_return, 0)
        self.assertIsInstance(report.sharpe, float)
        self.assertIsInstance(report.sortino, float)

    def test_report_to_dict(self):
        holdings = {"VTI": {"weight": 1.0, "volatility": 0.16}}
        values = [100000, 101000, 102000, 100500, 103000]
        report = portfolio_analytics(holdings, values)
        d = report.to_dict()
        self.assertIn("annualized_return", d)
        self.assertIn("sharpe", d)
        self.assertIn("sortino", d)
        self.assertIn("max_drawdown", d)
        self.assertIn("risk_attribution", d)

    def test_report_summary_text(self):
        holdings = {"VTI": {"weight": 1.0, "volatility": 0.16}}
        values = [100000 + i * 100 for i in range(50)]
        report = portfolio_analytics(holdings, values)
        text = report.summary_text()
        self.assertIn("Sharpe", text)
        self.assertIn("Return", text)

    def test_asset_reports(self):
        holdings = {
            "VTI": {"weight": 0.60, "volatility": 0.16},
            "BND": {"weight": 0.40, "volatility": 0.04},
        }
        values = [100000 + i * 50 for i in range(100)]
        report = portfolio_analytics(holdings, values)
        self.assertEqual(len(report.assets), 2)
        self.assertIsInstance(report.assets[0], AssetReport)


if __name__ == "__main__":
    unittest.main()
