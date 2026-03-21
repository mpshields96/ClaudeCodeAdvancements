#!/usr/bin/env python3
"""
Tests for dynamic_kelly.py — MT-26 Tier 2: Dynamic Kelly with Bayesian Updating

Tests Kelly fraction computation, Bayesian belief updating from new price
observations, time-decay adjustments, and optimal bet sizing.
"""

import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dynamic_kelly import (
    DynamicKelly,
    BetSizing,
    BeliefState,
)


class TestBeliefState(unittest.TestCase):
    """BeliefState dataclass."""

    def test_creation(self):
        bs = BeliefState(
            prior_prob=0.60,
            posterior_prob=0.65,
            n_updates=3,
            confidence=0.80,
        )
        self.assertEqual(bs.prior_prob, 0.60)
        self.assertEqual(bs.posterior_prob, 0.65)
        self.assertEqual(bs.n_updates, 3)

    def test_to_dict(self):
        bs = BeliefState(prior_prob=0.6, posterior_prob=0.65, n_updates=3, confidence=0.8)
        d = bs.to_dict()
        self.assertIn("prior_prob", d)
        self.assertIn("posterior_prob", d)


class TestBetSizing(unittest.TestCase):
    """BetSizing dataclass."""

    def test_creation(self):
        sizing = BetSizing(
            kelly_fraction=0.12,
            bet_amount_cents=500,
            edge=0.08,
            market_price=0.55,
            true_prob=0.63,
            confidence=0.85,
        )
        self.assertEqual(sizing.kelly_fraction, 0.12)
        self.assertEqual(sizing.bet_amount_cents, 500)

    def test_to_dict(self):
        sizing = BetSizing(
            kelly_fraction=0.12,
            bet_amount_cents=500,
            edge=0.08,
            market_price=0.55,
            true_prob=0.63,
            confidence=0.85,
        )
        d = sizing.to_dict()
        self.assertIn("kelly_fraction", d)
        self.assertIn("edge", d)


class TestDynamicKellyInit(unittest.TestCase):
    """Initialization."""

    def test_default_init(self):
        dk = DynamicKelly()
        self.assertGreater(dk.max_fraction, 0)
        self.assertGreater(dk.bankroll_cents, 0)

    def test_custom_params(self):
        dk = DynamicKelly(bankroll_cents=10000, max_fraction=0.10)
        self.assertEqual(dk.bankroll_cents, 10000)
        self.assertEqual(dk.max_fraction, 0.10)

    def test_invalid_bankroll(self):
        with self.assertRaises(ValueError):
            DynamicKelly(bankroll_cents=0)

    def test_invalid_max_fraction(self):
        with self.assertRaises(ValueError):
            DynamicKelly(max_fraction=0)
        with self.assertRaises(ValueError):
            DynamicKelly(max_fraction=1.5)


class TestClassicKelly(unittest.TestCase):
    """Classic Kelly criterion computation."""

    def setUp(self):
        self.dk = DynamicKelly(bankroll_cents=10000, max_fraction=0.25)

    def test_positive_edge(self):
        # If true prob = 0.60, market price = 0.50 (even odds)
        # Edge = 0.10, Kelly = edge / (1 - market_price) = 0.10 / 0.50 = 0.20
        f = self.dk.kelly_fraction(true_prob=0.60, market_price=0.50)
        self.assertGreater(f, 0)
        self.assertAlmostEqual(f, 0.20, places=2)

    def test_no_edge_returns_zero(self):
        f = self.dk.kelly_fraction(true_prob=0.50, market_price=0.50)
        self.assertEqual(f, 0)

    def test_negative_edge_returns_zero(self):
        f = self.dk.kelly_fraction(true_prob=0.40, market_price=0.50)
        self.assertEqual(f, 0)

    def test_capped_at_max_fraction(self):
        # Very high edge should still be capped
        f = self.dk.kelly_fraction(true_prob=0.95, market_price=0.30)
        self.assertLessEqual(f, self.dk.max_fraction)

    def test_edge_at_extremes(self):
        # Near 0 market price
        f = self.dk.kelly_fraction(true_prob=0.10, market_price=0.05)
        self.assertGreaterEqual(f, 0)
        # Near 1 market price
        f = self.dk.kelly_fraction(true_prob=0.99, market_price=0.95)
        self.assertGreaterEqual(f, 0)

    def test_fractional_kelly(self):
        # Half-Kelly should be half of full Kelly (use small edge to avoid cap)
        dk_full = DynamicKelly(bankroll_cents=10000, max_fraction=0.50, kelly_multiplier=1.0)
        dk_half = DynamicKelly(bankroll_cents=10000, max_fraction=0.50, kelly_multiplier=0.5)
        f_full = dk_full.kelly_fraction(true_prob=0.60, market_price=0.50)
        f_half = dk_half.kelly_fraction(true_prob=0.60, market_price=0.50)
        self.assertAlmostEqual(f_half, f_full * 0.5, places=4)


class TestBayesianUpdate(unittest.TestCase):
    """Bayesian belief updating from new price observations."""

    def setUp(self):
        self.dk = DynamicKelly(bankroll_cents=10000)

    def test_update_with_confirming_evidence(self):
        # Initial belief: 60% yes. New price observation also shows 65%.
        state = self.dk.update_belief(
            prior_prob=0.60,
            new_observation=0.65,
            observation_weight=1.0,
        )
        self.assertIsInstance(state, BeliefState)
        # Posterior should move toward the observation
        self.assertGreater(state.posterior_prob, 0.60)

    def test_update_with_contradicting_evidence(self):
        # Initial belief: 60% yes. New observation shows 40%.
        state = self.dk.update_belief(
            prior_prob=0.60,
            new_observation=0.40,
            observation_weight=1.0,
        )
        # Posterior should move toward the observation (down)
        self.assertLess(state.posterior_prob, 0.60)

    def test_posterior_in_valid_range(self):
        for prior in [0.1, 0.3, 0.5, 0.7, 0.9]:
            for obs in [0.1, 0.3, 0.5, 0.7, 0.9]:
                state = self.dk.update_belief(prior, obs, 1.0)
                self.assertGreater(state.posterior_prob, 0.0)
                self.assertLess(state.posterior_prob, 1.0)

    def test_weight_affects_strength(self):
        state_low = self.dk.update_belief(0.50, 0.70, observation_weight=0.3)
        state_high = self.dk.update_belief(0.50, 0.70, observation_weight=1.0)
        # Higher weight should move posterior more
        self.assertGreater(
            abs(state_high.posterior_prob - 0.50),
            abs(state_low.posterior_prob - 0.50),
        )

    def test_multiple_updates(self):
        state = self.dk.update_belief(0.50, 0.65, 1.0)
        state2 = self.dk.update_belief(state.posterior_prob, 0.70, 1.0)
        # Should continue moving toward 0.70
        self.assertGreater(state2.posterior_prob, state.posterior_prob)
        self.assertEqual(state2.n_updates, 1)

    def test_extreme_observation_clamped(self):
        # Even with extreme observation, posterior should stay reasonable
        state = self.dk.update_belief(0.50, 0.99, 1.0)
        self.assertLess(state.posterior_prob, 0.99)


class TestTimeDecay(unittest.TestCase):
    """Time decay for Kelly fraction as expiry approaches."""

    def setUp(self):
        self.dk = DynamicKelly(bankroll_cents=10000, max_fraction=0.25)

    def test_full_time_remaining_no_decay(self):
        factor = self.dk.time_decay_factor(minutes_remaining=15, total_window=15)
        self.assertAlmostEqual(factor, 1.0, places=2)

    def test_near_expiry_reduces_fraction(self):
        factor = self.dk.time_decay_factor(minutes_remaining=1, total_window=15)
        self.assertLess(factor, 1.0)

    def test_zero_remaining_returns_min(self):
        factor = self.dk.time_decay_factor(minutes_remaining=0, total_window=15)
        self.assertGreaterEqual(factor, 0)
        self.assertLessEqual(factor, 0.5)

    def test_factor_monotonically_decreasing(self):
        factors = [
            self.dk.time_decay_factor(m, 15) for m in [15, 10, 5, 2, 1, 0]
        ]
        for i in range(len(factors) - 1):
            self.assertGreaterEqual(factors[i], factors[i + 1])

    def test_factor_in_valid_range(self):
        for m in range(0, 16):
            factor = self.dk.time_decay_factor(m, 15)
            self.assertGreaterEqual(factor, 0)
            self.assertLessEqual(factor, 1.0)


class TestComputeBetSizing(unittest.TestCase):
    """Full bet sizing computation."""

    def setUp(self):
        self.dk = DynamicKelly(bankroll_cents=10000, max_fraction=0.25)

    def test_returns_bet_sizing(self):
        sizing = self.dk.compute_bet_sizing(
            true_prob=0.65,
            market_price=0.50,
            minutes_remaining=10,
            total_window=15,
        )
        self.assertIsInstance(sizing, BetSizing)

    def test_bet_amount_positive_with_edge(self):
        sizing = self.dk.compute_bet_sizing(
            true_prob=0.65,
            market_price=0.50,
        )
        self.assertGreater(sizing.bet_amount_cents, 0)

    def test_bet_amount_zero_without_edge(self):
        sizing = self.dk.compute_bet_sizing(
            true_prob=0.50,
            market_price=0.50,
        )
        self.assertEqual(sizing.bet_amount_cents, 0)

    def test_bet_not_exceed_bankroll(self):
        sizing = self.dk.compute_bet_sizing(
            true_prob=0.95,
            market_price=0.30,
        )
        self.assertLessEqual(sizing.bet_amount_cents, self.dk.bankroll_cents)

    def test_time_decay_reduces_bet(self):
        sizing_full = self.dk.compute_bet_sizing(
            true_prob=0.65,
            market_price=0.50,
            minutes_remaining=15,
            total_window=15,
        )
        sizing_late = self.dk.compute_bet_sizing(
            true_prob=0.65,
            market_price=0.50,
            minutes_remaining=2,
            total_window=15,
        )
        self.assertGreater(sizing_full.bet_amount_cents, sizing_late.bet_amount_cents)

    def test_edge_computed_correctly(self):
        sizing = self.dk.compute_bet_sizing(
            true_prob=0.65,
            market_price=0.50,
        )
        self.assertAlmostEqual(sizing.edge, 0.15, places=2)

    def test_confidence_in_sizing(self):
        sizing = self.dk.compute_bet_sizing(
            true_prob=0.65,
            market_price=0.50,
        )
        self.assertGreaterEqual(sizing.confidence, 0)
        self.assertLessEqual(sizing.confidence, 1)


if __name__ == "__main__":
    unittest.main()
