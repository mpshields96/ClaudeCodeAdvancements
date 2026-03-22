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
        """All 7 pipeline stages should be represented in output."""
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
        self.assertIn("order_flow_risk", stage_names)
        self.assertIn("dynamic_kelly", stage_names)
        self.assertEqual(len(dec.stages), 7)


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
                "order_flow_risk": False,
            })
        inp = PipelineInput(true_prob=0.70, market_price=0.50)
        dec = pipeline.run(inp)
        # Should still produce a bet from Kelly alone
        self.assertEqual(dec.action, "BET")
        self.assertGreater(dec.bet_amount_cents, 0)

    def test_disable_order_flow_risk(self):
        pipeline = SignalPipeline(
            bankroll_cents=10000,
            enabled_stages={"order_flow_risk": False})
        inp = PipelineInput(
            true_prob=0.65, market_price=0.05,
            market_category="crypto")
        dec = pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        self.assertFalse(ofr_stage["enabled"])
        self.assertFalse(ofr_stage["ran"])


class TestPipelineWithOrderFlowRisk(unittest.TestCase):
    """Test order flow risk (Tier 3) integration in pipeline."""

    def setUp(self):
        self.pipeline = SignalPipeline(bankroll_cents=10000)

    def test_order_flow_stage_runs(self):
        """Order flow risk should run by default."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        self.assertTrue(ofr_stage["ran"])

    def test_toxic_contract_forces_skip(self):
        """Sub-10c contracts should be classified TOXIC and get modifier=0.0."""
        inp = PipelineInput(
            true_prob=0.65, market_price=0.05,
            market_category="crypto")
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        self.assertTrue(ofr_stage["ran"])
        self.assertEqual(ofr_stage["output"]["risk"], "TOXIC")
        self.assertEqual(ofr_stage["modifier"], 0.0)
        # TOXIC modifier=0.0 should force SKIP regardless of edge
        self.assertEqual(dec.action, "SKIP")
        self.assertEqual(dec.bet_amount_cents, 0)

    def test_favorable_contract_no_reduction(self):
        """Mid-range contracts should get FAVORABLE with modifier=1.0."""
        inp = PipelineInput(
            true_prob=0.70, market_price=0.50,
            market_category="financials")
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        self.assertTrue(ofr_stage["ran"])
        self.assertEqual(ofr_stage["modifier"], 1.0)

    def test_unfavorable_halves_sizing(self):
        """Low-price but not toxic contracts get modifier=0.5."""
        inp = PipelineInput(
            true_prob=0.70, market_price=0.12,
            market_category="all")
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        self.assertTrue(ofr_stage["ran"])
        risk = ofr_stage["output"]["risk"]
        if risk == "UNFAVORABLE":
            self.assertEqual(ofr_stage["modifier"], 0.5)

    def test_market_category_passed_through(self):
        """market_category from PipelineInput reaches order flow stage."""
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50,
            market_category="crypto")
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        self.assertEqual(ofr_stage["output"]["category"], "crypto")

    def test_default_category_is_all(self):
        """Without market_category, default should be 'all'."""
        inp = PipelineInput(true_prob=0.65, market_price=0.50)
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        self.assertEqual(ofr_stage["output"]["category"], "all")

    def test_toxic_overrides_positive_filters(self):
        """TOXIC should force SKIP even when other filters are positive."""
        inp = PipelineInput(
            true_prob=0.90, market_price=0.05,
            fear_greed_value=10,  # extreme fear = bullish
            market_category="crypto")
        dec = self.pipeline.run(inp)
        # Despite huge edge (0.85) and bullish F&G, TOXIC should force SKIP
        self.assertEqual(dec.action, "SKIP")

    def test_order_flow_compounds_with_other_stages(self):
        """Order flow modifier should compound with other stage modifiers."""
        inp = PipelineInput(
            true_prob=0.65, market_price=0.30,
            fear_greed_value=90,  # extreme greed = reduce
            market_category="all")
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        fg_stage = next(
            s for s in dec.stages if s["stage"] == "fear_greed")
        if ofr_stage["ran"] and fg_stage["ran"]:
            expected_compound = ofr_stage["modifier"] * fg_stage["modifier"]
            # Compound modifier should be <= each individual modifier
            self.assertLessEqual(
                dec.sizing_modifier,
                max(ofr_stage["modifier"], 1.0) * max(fg_stage["modifier"], 1.0) + 0.01)

    def test_order_flow_has_confidence(self):
        """Stage output should include confidence for overall calculation."""
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50,
            market_category="financials")
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        self.assertIn("confidence", ofr_stage["output"])
        self.assertGreater(ofr_stage["output"]["confidence"], 0)

    def test_order_flow_has_expected_return(self):
        """Stage output should include expected_return."""
        inp = PipelineInput(
            true_prob=0.65, market_price=0.50)
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        self.assertIn("expected_return", ofr_stage["output"])

    def test_neutral_slight_reduction(self):
        """NEUTRAL risk should get modifier=0.9."""
        # Price range that typically maps to NEUTRAL
        inp = PipelineInput(
            true_prob=0.65, market_price=0.20,
            market_category="all")
        dec = self.pipeline.run(inp)
        ofr_stage = next(
            s for s in dec.stages if s["stage"] == "order_flow_risk")
        if ofr_stage["output"]["risk"] == "NEUTRAL":
            self.assertEqual(ofr_stage["modifier"], 0.9)


class TestPipelineWithBeliefVol(unittest.TestCase):
    """Test belief_vol_surface modules alongside pipeline inputs.

    belief_vol_surface is not a pipeline stage yet, but its outputs
    (realized vol, Greeks) should be compatible with pipeline data.
    """

    def test_realized_vol_from_pipeline_prices(self):
        """RealizedVolEstimator should work with price_history format."""
        from belief_vol_surface import RealizedVolEstimator

        prices = [0.50 + 0.01 * i for i in range(20)]
        timestamps = list(range(len(prices)))
        est = RealizedVolEstimator()
        vol = est.estimate(prices, timestamps)
        self.assertIsInstance(vol, float)
        self.assertGreater(vol, 0)

    def test_greeks_at_pipeline_price(self):
        """BeliefGreeks should compute for typical pipeline market_price."""
        from belief_vol_surface import BeliefGreeks

        bg = BeliefGreeks()
        price = 0.50
        greeks = bg.all_greeks(p=price, sigma_b=0.5, tau=1.0)
        self.assertIn("delta_x", greeks)
        self.assertIn("gamma_x", greeks)
        self.assertIn("belief_vega", greeks)
        self.assertGreater(greeks["delta_x"], 0)

    def test_logit_roundtrip(self):
        """logit(sigmoid(x)) == x for pipeline-relevant values."""
        from belief_vol_surface import LogitTransform

        for p in [0.10, 0.25, 0.50, 0.75, 0.90]:
            x = LogitTransform.logit(p)
            p_back = LogitTransform.sigmoid(x)
            self.assertAlmostEqual(p, p_back, places=10)

    def test_vol_with_volatile_prices(self):
        """High-volatility prices should produce higher realized vol."""
        from belief_vol_surface import RealizedVolEstimator
        import math as _math

        # Calm market
        calm_prices = [0.50 + 0.001 * i for i in range(20)]
        calm_ts = list(range(len(calm_prices)))

        # Volatile market
        volatile_prices = [
            max(0.01, min(0.99, 0.50 + 0.05 * _math.sin(i)))
            for i in range(20)]
        vol_ts = list(range(len(volatile_prices)))

        est = RealizedVolEstimator()
        calm_vol = est.estimate(calm_prices, calm_ts)
        vol_vol = est.estimate(volatile_prices, vol_ts)
        self.assertGreater(vol_vol, calm_vol)

    def test_greeks_at_extreme_prices(self):
        """Greeks should be computable at extreme but valid prices."""
        from belief_vol_surface import BeliefGreeks

        bg = BeliefGreeks()
        for p in [0.05, 0.95]:
            greeks = bg.all_greeks(p=p, sigma_b=0.5, tau=1.0)
            self.assertIn("delta_x", greeks)
            self.assertIsInstance(greeks["delta_x"], float)


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
