#!/usr/bin/env python3
"""Tests for signal_pipeline.py — MT-26 Pipeline Orchestrator.

Chains the 6 MT-26 modules into a composable pipeline:
regime_detector -> calibration_bias -> cross_platform_signal ->
macro_regime -> fear_greed_filter -> dynamic_kelly

Each stage can be enabled/disabled independently. The pipeline produces
a combined SignalDecision with final bet sizing recommendation.
"""

import json
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from signal_pipeline import (
    SignalPipeline,
    PipelineInput,
    SignalDecision,
    StageResult,
)


class TestPipelineInput(unittest.TestCase):
    """Test PipelineInput data structure."""

    def test_create_minimal_input(self):
        inp = PipelineInput(
            true_prob=0.65,
            market_price=0.50,
        )
        self.assertEqual(inp.true_prob, 0.65)
        self.assertEqual(inp.market_price, 0.50)

    def test_create_full_input(self):
        inp = PipelineInput(
            true_prob=0.65,
            market_price=0.50,
            price_history=[100, 101, 102, 103, 104,
                           105, 106, 107, 108, 109, 110],
            bankroll_cents=10000,
            fear_greed_value=25,
            polymarket_price=0.60,
            contract_id="BTC-UP-100K",
            now=datetime(2026, 3, 21, 10, 0),
        )
        self.assertEqual(inp.fear_greed_value, 25)
        self.assertEqual(inp.polymarket_price, 0.60)

    def test_input_to_dict(self):
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        d = inp.to_dict()
        self.assertEqual(d["true_prob"], 0.65)
        self.assertEqual(d["market_price"], 0.50)


class TestStageResult(unittest.TestCase):
    """Test StageResult structure."""

    def test_create_result(self):
        sr = StageResult(
            stage="regime_detector",
            enabled=True,
            ran=True,
            output={"regime": "TRENDING", "confidence": 0.8},
            modifier=1.0,
        )
        self.assertEqual(sr.stage, "regime_detector")
        self.assertTrue(sr.ran)

    def test_skipped_result(self):
        sr = StageResult(
            stage="cross_platform",
            enabled=True,
            ran=False,
            output=None,
            modifier=1.0,
            skip_reason="No polymarket price provided",
        )
        self.assertFalse(sr.ran)
        self.assertIsNotNone(sr.skip_reason)

    def test_disabled_result(self):
        sr = StageResult(
            stage="fear_greed",
            enabled=False,
            ran=False,
            output=None,
            modifier=1.0,
        )
        self.assertFalse(sr.enabled)


class TestSignalDecision(unittest.TestCase):
    """Test SignalDecision output."""

    def test_decision_to_dict(self):
        dec = SignalDecision(
            action="BET",
            kelly_fraction=0.08,
            bet_amount_cents=800,
            edge=0.15,
            confidence=0.72,
            sizing_modifier=0.85,
            stages=[],
            advice="Trade with reduced sizing.",
        )
        d = dec.to_dict()
        self.assertEqual(d["action"], "BET")
        self.assertEqual(d["kelly_fraction"], 0.08)
        self.assertIn("stages", d)

    def test_decision_json_serializable(self):
        dec = SignalDecision(
            action="SKIP",
            kelly_fraction=0.0,
            bet_amount_cents=0,
            edge=0.02,
            confidence=0.3,
            sizing_modifier=0.0,
            stages=[],
            advice="Edge too thin.",
        )
        json_str = json.dumps(dec.to_dict())
        self.assertIsInstance(json_str, str)


class TestSignalPipelineFull(unittest.TestCase):
    """Test full pipeline execution."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_minimal_input_runs(self):
        """Pipeline should work with just true_prob and market_price."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        dec = self.pipeline.run(inp)
        self.assertIsInstance(dec, SignalDecision)
        self.assertIn(dec.action, ["BET", "SKIP"])

    def test_positive_edge_produces_bet(self):
        inp = PipelineInput(true_prob=0.70, market_price=0.50)
        dec = self.pipeline.run(inp)
        self.assertEqual(dec.action, "BET")
        self.assertGreater(dec.kelly_fraction, 0)
        self.assertGreater(dec.bet_amount_cents, 0)

    def test_no_edge_produces_skip(self):
        inp = PipelineInput(true_prob=0.50, market_price=0.55)
        dec = self.pipeline.run(inp)
        self.assertEqual(dec.action, "SKIP")
        self.assertEqual(dec.bet_amount_cents, 0)

    def test_thin_edge_produces_skip(self):
        """Edge below minimum threshold should be skipped."""
        inp = PipelineInput(true_prob=0.52, market_price=0.50)
        dec = self.pipeline.run(inp)
        self.assertEqual(dec.action, "SKIP")

    def test_stages_recorded(self):
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        dec = self.pipeline.run(inp)
        self.assertGreater(len(dec.stages), 0)
        stage_names = [s["stage"] for s in dec.stages]
        self.assertIn("dynamic_kelly", stage_names)

    def test_all_stages_in_output(self):
        """All 6 pipeline stages should be represented in output."""
        inp = PipelineInput(
            true_prob=0.65,
            market_price=0.50,
            price_history=[100 + i for i in range(15)],
            fear_greed_value=25,
            polymarket_price=0.60,
            contract_id="BTC-UP",
            now=datetime(2026, 3, 21, 10, 0),
        )
        dec = self.pipeline.run(inp)
        stage_names = [s["stage"] for s in dec.stages]
        self.assertIn("regime_detector", stage_names)
        self.assertIn("calibration_bias", stage_names)
        self.assertIn("cross_platform", stage_names)
        self.assertIn("macro_regime", stage_names)
        self.assertIn("fear_greed", stage_names)
        self.assertIn("dynamic_kelly", stage_names)


class TestPipelineWithRegime(unittest.TestCase):
    """Test regime detector integration."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_trending_regime_no_reduction(self):
        # Linear uptrend
        prices = [100 + i * 2 for i in range(15)]
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50, price_history=prices)
        dec = self.pipeline.run(inp)
        regime_stage = next(
            s for s in dec.stages if s["stage"] == "regime_detector")
        if regime_stage["ran"]:
            self.assertGreaterEqual(regime_stage["modifier"], 0.8)

    def test_no_price_history_skips_regime(self):
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        dec = self.pipeline.run(inp)
        regime_stage = next(
            s for s in dec.stages if s["stage"] == "regime_detector")
        self.assertFalse(regime_stage["ran"])


class TestPipelineWithFearGreed(unittest.TestCase):
    """Test fear & greed filter integration."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_extreme_fear_boosts_sizing(self):
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50, fear_greed_value=10)
        dec = self.pipeline.run(inp)
        fg_stage = next(s for s in dec.stages if s["stage"] == "fear_greed")
        self.assertTrue(fg_stage["ran"])
        self.assertGreaterEqual(fg_stage["modifier"], 1.0)

    def test_extreme_greed_reduces_sizing(self):
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50, fear_greed_value=92)
        dec = self.pipeline.run(inp)
        fg_stage = next(s for s in dec.stages if s["stage"] == "fear_greed")
        self.assertTrue(fg_stage["ran"])
        self.assertLessEqual(fg_stage["modifier"], 1.0)

    def test_no_fg_value_skips(self):
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        dec = self.pipeline.run(inp)
        fg_stage = next(s for s in dec.stages if s["stage"] == "fear_greed")
        self.assertFalse(fg_stage["ran"])


class TestPipelineWithMacro(unittest.TestCase):
    """Test macro regime context integration."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_macro_runs_with_now(self):
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50,
            now=datetime(2026, 3, 21, 10, 0))
        dec = self.pipeline.run(inp)
        macro_stage = next(
            s for s in dec.stages if s["stage"] == "macro_regime")
        self.assertTrue(macro_stage["ran"])

    def test_near_fomc_reduces_sizing(self):
        # March 18 FOMC at 14:00 — 30 min before
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50,
            now=datetime(2026, 3, 18, 13, 30))
        dec = self.pipeline.run(inp)
        macro_stage = next(
            s for s in dec.stages if s["stage"] == "macro_regime")
        self.assertTrue(macro_stage["ran"])
        self.assertLess(macro_stage["modifier"], 1.0)


class TestPipelineWithCrossPlatform(unittest.TestCase):
    """Test cross-platform signal integration."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_divergence_detected(self):
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50,
            polymarket_price=0.62, contract_id="BTC-UP")
        dec = self.pipeline.run(inp)
        cp_stage = next(
            s for s in dec.stages if s["stage"] == "cross_platform")
        self.assertTrue(cp_stage["ran"])

    def test_no_polymarket_skips(self):
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        dec = self.pipeline.run(inp)
        cp_stage = next(
            s for s in dec.stages if s["stage"] == "cross_platform")
        self.assertFalse(cp_stage["ran"])


class TestPipelineDisableStages(unittest.TestCase):
    """Test disabling individual stages."""

    def test_disable_regime(self):
        pipeline = SignalPipeline(
            bankroll_cents=10000,
            enabled_stages={"regime_detector": False})
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50,
            price_history=[100 + i for i in range(15)])
        dec = pipeline.run(inp)
        regime_stage = next(
            s for s in dec.stages if s["stage"] == "regime_detector")
        self.assertFalse(regime_stage["enabled"])
        self.assertFalse(regime_stage["ran"])

    def test_disable_all_still_produces_kelly(self):
        pipeline = SignalPipeline(
            bankroll_cents=10000,
            enabled_stages={
                "regime_detector": False,
                "calibration_bias": False,
                "cross_platform": False,
                "macro_regime": False,
                "fear_greed": False,
            })
        inp = PipelineInput(true_prob=0.70, market_price=0.50)
        dec = pipeline.run(inp)
        # Should still produce a bet from Kelly alone
        self.assertEqual(dec.action, "BET")
        self.assertGreater(dec.bet_amount_cents, 0)


class TestPipelineModifierCompounding(unittest.TestCase):
    """Test that modifiers from all stages compound correctly."""

    def test_modifiers_compound_multiplicatively(self):
        """Final sizing = kelly * product(all modifiers)."""
        pipeline = SignalPipeline(bankroll_cents=10000)
        inp = PipelineInput(
            true_prob=0.70, market_price=0.50,
            price_history=[100 + i for i in range(15)],
            fear_greed_value=15,
            now=datetime(2026, 3, 21, 10, 0),
        )
        dec = pipeline.run(inp)
        # Verify compound modifier matches product of stage modifiers
        compound = 1.0
        for s in dec.stages:
            compound *= s["modifier"]
        self.assertAlmostEqual(dec.sizing_modifier, compound, places=3)

    def test_modifier_never_negative(self):
        pipeline = SignalPipeline(bankroll_cents=10000)
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50,
            fear_greed_value=95,
            now=datetime(2026, 3, 18, 13, 55),  # Near FOMC
        )
        dec = pipeline.run(inp)
        self.assertGreaterEqual(dec.sizing_modifier, 0.0)


class TestPipelineEdgeCases(unittest.TestCase):
    """Edge cases and robustness."""

    def test_zero_bankroll(self):
        pipeline = SignalPipeline(bankroll_cents=0)
        inp = PipelineInput(true_prob=0.70, market_price=0.50)
        dec = pipeline.run(inp)
        self.assertEqual(dec.bet_amount_cents, 0)

    def test_prob_equals_price(self):
        pipeline = SignalPipeline(bankroll_cents=10000)
        inp = PipelineInput(true_prob=0.50, market_price=0.50)
        dec = pipeline.run(inp)
        self.assertEqual(dec.action, "SKIP")

    def test_output_json_serializable(self):
        pipeline = SignalPipeline(bankroll_cents=10000)
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50,
            price_history=[100 + i for i in range(15)],
            fear_greed_value=25,
            now=datetime(2026, 3, 21, 10, 0),
        )
        dec = pipeline.run(inp)
        json_str = json.dumps(dec.to_dict())
        self.assertIsInstance(json_str, str)

    def test_very_small_edge(self):
        pipeline = SignalPipeline(bankroll_cents=10000, min_edge=0.05)
        inp = PipelineInput(true_prob=0.53, market_price=0.50)
        dec = pipeline.run(inp)
        self.assertEqual(dec.action, "SKIP")

    def test_cli_output(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(
                os.path.dirname(__file__), "..", "signal_pipeline.py"),
             "--true-prob", "0.65", "--market-price", "0.50",
             "--bankroll", "10000"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("action", data)
        self.assertIn("stages", data)


if __name__ == "__main__":
    unittest.main()
