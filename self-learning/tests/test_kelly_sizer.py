#!/usr/bin/env python3
"""Tests for kelly_sizer.py — MT-37 Phase 3 Layer 3: Portfolio position sizing.

Fractional Kelly criterion with confidence scaling for long-term portfolios.
Based on Thorp 2006, Kelly 1956, MacLean et al. 2011.
"""
import os
import sys
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from kelly_sizer import (
    kelly_fraction,
    fractional_kelly,
    confidence_scaled_kelly,
    portfolio_kelly_sizes,
    SizingResult,
)


class TestKellyFraction(unittest.TestCase):
    """Test full Kelly criterion computation."""

    def test_positive_edge(self):
        # 60% win rate, 1:1 odds → Kelly = 0.20
        f = kelly_fraction(win_prob=0.60, win_return=1.0, loss_return=1.0)
        self.assertAlmostEqual(f, 0.20, places=2)

    def test_no_edge(self):
        # 50% win rate, 1:1 odds → Kelly = 0
        f = kelly_fraction(win_prob=0.50, win_return=1.0, loss_return=1.0)
        self.assertAlmostEqual(f, 0.0, places=2)

    def test_negative_edge_returns_zero(self):
        # 40% win rate, 1:1 → negative edge, should return 0 (no bet)
        f = kelly_fraction(win_prob=0.40, win_return=1.0, loss_return=1.0)
        self.assertEqual(f, 0.0)

    def test_high_edge(self):
        # 80% win rate, 1:1 → Kelly = 0.60
        f = kelly_fraction(win_prob=0.80, win_return=1.0, loss_return=1.0)
        self.assertAlmostEqual(f, 0.60, places=2)

    def test_asymmetric_payoff(self):
        # 50% win rate, 2:1 payoff → Kelly = 0.25
        f = kelly_fraction(win_prob=0.50, win_return=2.0, loss_return=1.0)
        self.assertAlmostEqual(f, 0.25, places=2)

    def test_certain_win(self):
        f = kelly_fraction(win_prob=1.0, win_return=1.0, loss_return=1.0)
        self.assertAlmostEqual(f, 1.0, places=2)


class TestFractionalKelly(unittest.TestCase):
    """Test fractional Kelly (risk-adjusted half/quarter Kelly)."""

    def test_half_kelly(self):
        full = kelly_fraction(win_prob=0.60, win_return=1.0, loss_return=1.0)
        half = fractional_kelly(win_prob=0.60, win_return=1.0, loss_return=1.0, fraction=0.5)
        self.assertAlmostEqual(half, full * 0.5)

    def test_quarter_kelly(self):
        full = kelly_fraction(win_prob=0.60, win_return=1.0, loss_return=1.0)
        quarter = fractional_kelly(win_prob=0.60, win_return=1.0, loss_return=1.0, fraction=0.25)
        self.assertAlmostEqual(quarter, full * 0.25)

    def test_fraction_clamps_to_zero(self):
        result = fractional_kelly(win_prob=0.40, win_return=1.0, loss_return=1.0, fraction=0.5)
        self.assertEqual(result, 0.0)

    def test_default_fraction_is_half(self):
        half = fractional_kelly(win_prob=0.60, win_return=1.0, loss_return=1.0)
        full = kelly_fraction(win_prob=0.60, win_return=1.0, loss_return=1.0)
        self.assertAlmostEqual(half, full * 0.5)


class TestConfidenceScaledKelly(unittest.TestCase):
    """Test confidence-scaled Kelly sizing."""

    def test_full_confidence_equals_fractional(self):
        base = fractional_kelly(win_prob=0.60, win_return=1.0, loss_return=1.0, fraction=0.5)
        scaled = confidence_scaled_kelly(
            win_prob=0.60, win_return=1.0, loss_return=1.0,
            fraction=0.5, confidence=1.0,
        )
        self.assertAlmostEqual(scaled, base)

    def test_zero_confidence_returns_zero(self):
        scaled = confidence_scaled_kelly(
            win_prob=0.60, win_return=1.0, loss_return=1.0,
            fraction=0.5, confidence=0.0,
        )
        self.assertEqual(scaled, 0.0)

    def test_half_confidence_halves_size(self):
        base = fractional_kelly(win_prob=0.60, win_return=1.0, loss_return=1.0, fraction=0.5)
        scaled = confidence_scaled_kelly(
            win_prob=0.60, win_return=1.0, loss_return=1.0,
            fraction=0.5, confidence=0.5,
        )
        self.assertAlmostEqual(scaled, base * 0.5)

    def test_confidence_above_one_clamps(self):
        base = fractional_kelly(win_prob=0.60, win_return=1.0, loss_return=1.0, fraction=0.5)
        scaled = confidence_scaled_kelly(
            win_prob=0.60, win_return=1.0, loss_return=1.0,
            fraction=0.5, confidence=1.5,
        )
        # Should clamp confidence to 1.0
        self.assertAlmostEqual(scaled, base)


class TestPortfolioKellySizes(unittest.TestCase):
    """Test portfolio-level Kelly sizing across multiple assets."""

    def test_two_assets_independent(self):
        assets = [
            {"ticker": "VTI", "win_prob": 0.55, "win_return": 0.10, "loss_return": 0.08, "confidence": 0.7},
            {"ticker": "BND", "win_prob": 0.60, "win_return": 0.04, "loss_return": 0.02, "confidence": 0.9},
        ]
        result = portfolio_kelly_sizes(assets, fraction=0.5, bankroll=100000)
        self.assertEqual(len(result), 2)
        self.assertIn("VTI", [r.ticker for r in result])
        self.assertIn("BND", [r.ticker for r in result])

    def test_all_results_have_dollar_amount(self):
        assets = [
            {"ticker": "VTI", "win_prob": 0.55, "win_return": 0.10, "loss_return": 0.08, "confidence": 0.8},
        ]
        result = portfolio_kelly_sizes(assets, fraction=0.5, bankroll=50000)
        self.assertGreater(result[0].dollar_amount, 0)
        self.assertLessEqual(result[0].dollar_amount, 50000)

    def test_negative_edge_gets_zero_allocation(self):
        assets = [
            {"ticker": "BAD", "win_prob": 0.40, "win_return": 0.05, "loss_return": 0.10, "confidence": 0.9},
        ]
        result = portfolio_kelly_sizes(assets, fraction=0.5, bankroll=100000)
        self.assertEqual(result[0].dollar_amount, 0.0)
        self.assertEqual(result[0].kelly_pct, 0.0)

    def test_total_allocation_capped_at_bankroll(self):
        # Even with very high edges, total shouldn't exceed bankroll
        assets = [
            {"ticker": "A", "win_prob": 0.90, "win_return": 2.0, "loss_return": 0.5, "confidence": 1.0},
            {"ticker": "B", "win_prob": 0.85, "win_return": 1.5, "loss_return": 0.5, "confidence": 1.0},
            {"ticker": "C", "win_prob": 0.80, "win_return": 1.0, "loss_return": 0.5, "confidence": 1.0},
        ]
        result = portfolio_kelly_sizes(assets, fraction=0.5, bankroll=100000)
        total = sum(r.dollar_amount for r in result)
        self.assertLessEqual(total, 100000)


class TestSizingResult(unittest.TestCase):
    """Test SizingResult data class."""

    def test_to_dict(self):
        sr = SizingResult(
            ticker="VTI",
            kelly_pct=0.10,
            dollar_amount=10000.0,
            confidence=0.8,
        )
        d = sr.to_dict()
        self.assertEqual(d["ticker"], "VTI")
        self.assertAlmostEqual(d["kelly_pct"], 0.10)
        self.assertAlmostEqual(d["dollar_amount"], 10000.0)

    def test_summary_text(self):
        sr = SizingResult(
            ticker="VTI",
            kelly_pct=0.10,
            dollar_amount=10000.0,
            confidence=0.8,
        )
        text = sr.summary_text()
        self.assertIn("VTI", text)
        self.assertIn("10.0%", text)


if __name__ == "__main__":
    unittest.main()
