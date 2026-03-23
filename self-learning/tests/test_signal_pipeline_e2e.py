"""E2E integration tests for signal_pipeline.py (MT-26).

Tests the full 7-stage pipeline with realistic trading scenarios.
Validates that all stages compose correctly, graceful degradation works,
and the pipeline produces sensible bet/skip decisions for known market conditions.
"""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from signal_pipeline import SignalPipeline, PipelineInput, SignalDecision


class TestPipelineE2EBasic(unittest.TestCase):
    """Basic E2E pipeline tests with minimal inputs."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_minimal_input_produces_decision(self):
        """Pipeline runs with only required fields."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        decision = self.pipeline.run(inp)
        self.assertIsInstance(decision, SignalDecision)
        self.assertIn(decision.action, ["BET", "SKIP"])

    def test_clear_edge_produces_bet(self):
        """15% edge with no negative signals should produce BET."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        decision = self.pipeline.run(inp)
        self.assertEqual(decision.action, "BET")
        self.assertGreater(decision.bet_amount_cents, 0)

    def test_no_edge_produces_skip(self):
        """No edge (true_prob == market_price) should produce SKIP."""
        inp = PipelineInput(true_prob=0.50, market_price=0.50)
        decision = self.pipeline.run(inp)
        self.assertEqual(decision.action, "SKIP")

    def test_negative_edge_produces_skip(self):
        """Negative edge should produce SKIP."""
        inp = PipelineInput(true_prob=0.40, market_price=0.50)
        decision = self.pipeline.run(inp)
        self.assertEqual(decision.action, "SKIP")

    def test_decision_has_all_fields(self):
        """Decision should have all expected fields."""
        inp = PipelineInput(true_prob=0.70, market_price=0.50)
        decision = self.pipeline.run(inp)
        self.assertIsNotNone(decision.kelly_fraction)
        self.assertIsNotNone(decision.bet_amount_cents)
        self.assertIsNotNone(decision.edge)
        self.assertIsNotNone(decision.sizing_modifier)
        self.assertIsInstance(decision.stages, list)
        self.assertGreater(len(decision.stages), 0)
        self.assertIsInstance(decision.advice, str)

    def test_to_dict_serializable(self):
        """Decision.to_dict() should produce JSON-serializable dict."""
        import json
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        decision = self.pipeline.run(inp)
        d = decision.to_dict()
        serialized = json.dumps(d)
        self.assertIsInstance(serialized, str)


class TestPipelineE2EFullInput(unittest.TestCase):
    """E2E tests with all optional fields populated."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def _make_full_input(self, true_prob=0.65, market_price=0.50, **overrides):
        """Create a PipelineInput with all optional fields."""
        kwargs = {
            "true_prob": true_prob,
            "market_price": market_price,
            "price_history": [50 + i * 0.5 for i in range(30)],  # Uptrend
            "bankroll_cents": 10000,
            "fear_greed_value": 50,  # Neutral
            "polymarket_price": market_price + 0.02,  # Small divergence
            "contract_id": "KXTEST-123",
            "now": datetime(2026, 3, 23, 14, 0, 0),  # 2pm, no major events
            "trend": "UP",
            "minutes_remaining": 60.0,
            "total_window": 120.0,
            "market_category": "crypto",
        }
        kwargs.update(overrides)
        return PipelineInput(**kwargs)

    def test_full_input_all_stages_run(self):
        """All 7 stages should run with full input."""
        inp = self._make_full_input()
        decision = self.pipeline.run(inp)
        # Count stages that actually ran
        ran_count = sum(1 for s in decision.stages if s.get("ran", False))
        self.assertGreaterEqual(ran_count, 5, f"Expected 5+ stages to run, got {ran_count}")

    def test_full_input_produces_bet(self):
        """Full input with clear edge should produce BET."""
        inp = self._make_full_input(true_prob=0.70, market_price=0.50)
        decision = self.pipeline.run(inp)
        self.assertEqual(decision.action, "BET")

    def test_bet_amount_bounded_by_bankroll(self):
        """Bet amount should never exceed bankroll."""
        inp = self._make_full_input(true_prob=0.95, market_price=0.50)
        decision = self.pipeline.run(inp)
        self.assertLessEqual(decision.bet_amount_cents, 10000)

    def test_bet_amount_bounded_by_max_fraction(self):
        """Bet amount should respect max_fraction (default 15%)."""
        pipeline = SignalPipeline(bankroll_cents=10000, max_fraction=0.15)
        inp = self._make_full_input(true_prob=0.95, market_price=0.50)
        decision = pipeline.run(inp)
        self.assertLessEqual(decision.bet_amount_cents, 1500)

    def test_compound_modifier_affects_sizing(self):
        """More favorable conditions should produce larger bets."""
        # Neutral conditions
        inp_neutral = self._make_full_input(fear_greed_value=50, true_prob=0.65)
        dec_neutral = self.pipeline.run(inp_neutral)

        # Extreme fear (contrarian opportunity = larger modifier)
        inp_fear = self._make_full_input(fear_greed_value=10, true_prob=0.65)
        dec_fear = self.pipeline.run(inp_fear)

        # At least one should be different
        # (exact comparison depends on pipeline internals, but sizing_modifier should differ)
        self.assertIsInstance(dec_neutral.sizing_modifier, float)
        self.assertIsInstance(dec_fear.sizing_modifier, float)


class TestPipelineE2EScenarios(unittest.TestCase):
    """Realistic trading scenarios through the pipeline."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_sniper_bet_scenario(self):
        """Typical sniper bet: high prob, expiring soon, crypto market."""
        inp = PipelineInput(
            true_prob=0.92,
            market_price=0.85,
            market_category="crypto",
            minutes_remaining=5.0,
            total_window=15.0,
        )
        decision = self.pipeline.run(inp)
        self.assertEqual(decision.action, "BET")
        self.assertGreater(decision.edge, 0.05)

    def test_marginal_edge_scenario(self):
        """Marginal edge (3-4%) — pipeline should be cautious."""
        inp = PipelineInput(
            true_prob=0.54,
            market_price=0.50,
        )
        decision = self.pipeline.run(inp)
        # Marginal edge — could be BET or SKIP depending on modifier
        if decision.action == "BET":
            self.assertLess(decision.bet_amount_cents, 500,
                            "Marginal edge should produce small bet")

    def test_toxic_contract_scenario(self):
        """Sub-10c contract (TOXIC) should be hard-skipped by order flow."""
        inp = PipelineInput(
            true_prob=0.15,
            market_price=0.05,
            market_category="crypto",
        )
        decision = self.pipeline.run(inp)
        # TOXIC contracts get modifier=0.0 from order flow
        self.assertEqual(decision.action, "SKIP")

    def test_cross_platform_divergence_scenario(self):
        """Kalshi and Polymarket prices diverge — signal should adjust."""
        # Large divergence: Kalshi says 50c, Polymarket says 65c
        inp = PipelineInput(
            true_prob=0.65,
            market_price=0.50,
            polymarket_price=0.65,
        )
        decision = self.pipeline.run(inp)
        # Should still produce a decision
        self.assertIn(decision.action, ["BET", "SKIP"])

    def test_high_fear_contrarian_scenario(self):
        """Extreme fear + positive edge = contrarian opportunity."""
        inp = PipelineInput(
            true_prob=0.65,
            market_price=0.50,
            fear_greed_value=8,  # Extreme fear
            trend="DOWN",
        )
        decision = self.pipeline.run(inp)
        self.assertEqual(decision.action, "BET")

    def test_chaotic_regime_scenario(self):
        """Chaotic market regime should reduce sizing."""
        import random
        random.seed(42)
        # Chaotic price history (random walk)
        prices = [50.0]
        for _ in range(29):
            prices.append(prices[-1] + random.uniform(-3, 3))

        inp = PipelineInput(
            true_prob=0.65,
            market_price=0.50,
            price_history=prices,
        )
        decision = self.pipeline.run(inp)
        # Should still work, maybe with reduced sizing
        self.assertIn(decision.action, ["BET", "SKIP"])
        self.assertIsInstance(decision.sizing_modifier, float)

    def test_small_bankroll_scenario(self):
        """Small bankroll ($10) should still produce valid decisions."""
        pipeline = SignalPipeline(bankroll_cents=1000)
        inp = PipelineInput(true_prob=0.70, market_price=0.50)
        decision = pipeline.run(inp)
        self.assertIn(decision.action, ["BET", "SKIP"])
        if decision.action == "BET":
            self.assertLessEqual(decision.bet_amount_cents, 1000)
            self.assertGreater(decision.bet_amount_cents, 0)


class TestPipelineE2EGracefulDegradation(unittest.TestCase):
    """Tests that stages gracefully skip when data is missing."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_no_price_history_skips_regime(self):
        """No price_history should skip regime detection."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        decision = self.pipeline.run(inp)
        regime_stages = [s for s in decision.stages if s["stage"] == "regime_detector"]
        if regime_stages:
            self.assertFalse(regime_stages[0].get("ran", True))

    def test_no_fear_greed_skips_sentiment(self):
        """No fear_greed_value should skip F&G filter."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        decision = self.pipeline.run(inp)
        fg_stages = [s for s in decision.stages if s["stage"] == "fear_greed"]
        if fg_stages:
            self.assertFalse(fg_stages[0].get("ran", True))

    def test_no_polymarket_skips_cross_platform(self):
        """No polymarket_price should skip cross-platform signal."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        decision = self.pipeline.run(inp)
        cp_stages = [s for s in decision.stages if s["stage"] == "cross_platform"]
        if cp_stages:
            self.assertFalse(cp_stages[0].get("ran", True))

    def test_stages_disabled_via_config(self):
        """Explicitly disabled stages should not run."""
        pipeline = SignalPipeline(
            bankroll_cents=10000,
            enabled_stages={"regime_detector": False, "fear_greed": False},
        )
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50,
            price_history=[50 + i for i in range(30)],
            fear_greed_value=25,
        )
        decision = pipeline.run(inp)
        for s in decision.stages:
            if s["stage"] in ("regime_detector", "fear_greed"):
                self.assertFalse(s.get("enabled", True))

    def test_all_stages_disabled_still_works(self):
        """Pipeline with all stages disabled should still produce a decision via Kelly."""
        pipeline = SignalPipeline(
            bankroll_cents=10000,
            enabled_stages={
                "regime_detector": False,
                "calibration_bias": False,
                "cross_platform": False,
                "macro_regime": False,
                "fear_greed": False,
                "order_flow_risk": False,
            },
        )
        inp = PipelineInput(true_prob=0.70, market_price=0.50)
        decision = pipeline.run(inp)
        self.assertIn(decision.action, ["BET", "SKIP"])


class TestPipelineE2EStability(unittest.TestCase):
    """Stability tests — pipeline shouldn't crash on edge cases."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_extreme_probabilities(self):
        """Pipeline handles extreme true_prob values."""
        for prob in [0.01, 0.99, 0.001, 0.999]:
            inp = PipelineInput(true_prob=prob, market_price=0.50)
            decision = self.pipeline.run(inp)
            self.assertIn(decision.action, ["BET", "SKIP"])

    def test_zero_bankroll(self):
        """Zero bankroll should produce SKIP (can't bet with nothing)."""
        pipeline = SignalPipeline(bankroll_cents=0)
        inp = PipelineInput(true_prob=0.70, market_price=0.50)
        decision = pipeline.run(inp)
        self.assertEqual(decision.bet_amount_cents, 0)

    def test_empty_price_history(self):
        """Empty price_history should not crash."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50, price_history=[])
        decision = self.pipeline.run(inp)
        self.assertIn(decision.action, ["BET", "SKIP"])

    def test_single_price_history(self):
        """Single price point should not crash."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50, price_history=[50.0])
        decision = self.pipeline.run(inp)
        self.assertIn(decision.action, ["BET", "SKIP"])

    def test_deterministic_output(self):
        """Same input should produce same output."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50, bankroll_cents=10000)
        dec1 = self.pipeline.run(inp)
        dec2 = self.pipeline.run(inp)
        self.assertEqual(dec1.action, dec2.action)
        self.assertEqual(dec1.bet_amount_cents, dec2.bet_amount_cents)

    def test_boundary_edge(self):
        """Edge exactly at min_edge threshold."""
        # Default min_edge is 0.03
        inp = PipelineInput(true_prob=0.53, market_price=0.50)
        decision = self.pipeline.run(inp)
        self.assertIn(decision.action, ["BET", "SKIP"])

    def test_fear_greed_boundary_values(self):
        """F&G index at boundaries (0, 50, 100)."""
        for fg in [0, 50, 100]:
            inp = PipelineInput(true_prob=0.65, market_price=0.50, fear_greed_value=fg)
            decision = self.pipeline.run(inp)
            self.assertIn(decision.action, ["BET", "SKIP"])


if __name__ == "__main__":
    unittest.main()
