#!/usr/bin/env python3
"""
signal_pipeline.py — MT-26 Pipeline Orchestrator

Chains the 6 MT-26 financial intelligence modules into a composable pipeline:
1. regime_detector   — Market regime classification (TRENDING/MEAN_REVERTING/CHAOTIC)
2. calibration_bias  — Systematic mispricing detection + probability adjustment
3. cross_platform    — Kalshi/Polymarket divergence signals
4. macro_regime      — Economic event proximity filter
5. fear_greed        — Sentiment-based contrarian filter
6. dynamic_kelly     — Final bet sizing with Bayesian updating

Each stage produces a sizing modifier (0.0 to ~1.5). Modifiers compound
multiplicatively into a final sizing recommendation.

Stages gracefully degrade: if input data for a stage is missing, it's
skipped with modifier=1.0 (no effect). Stages can also be disabled via config.

Usage:
    from signal_pipeline import SignalPipeline, PipelineInput

    pipeline = SignalPipeline(bankroll_cents=10000)
    inp = PipelineInput(
        true_prob=0.65,
        market_price=0.50,
        price_history=[100, 101, ...],
        fear_greed_value=25,
        now=datetime.now(),
    )
    decision = pipeline.run(inp)
    # decision.action = "BET" or "SKIP"
    # decision.bet_amount_cents = 450
    # decision.stages = [...]  # per-stage breakdown

CLI:
    python3 signal_pipeline.py --true-prob 0.65 --market-price 0.50 --bankroll 10000

Zero external dependencies. Stdlib only.
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class PipelineInput:
    """Input data for the signal pipeline."""
    # Required
    true_prob: float          # Model's estimated true probability (0-1)
    market_price: float       # Current Kalshi market price (0-1)

    # Optional — stages skip gracefully if missing
    price_history: Optional[List[float]] = None     # Close prices for regime detection
    bankroll_cents: int = 10000                      # Bankroll in cents
    fear_greed_value: Optional[int] = None           # F&G index (0-100)
    polymarket_price: Optional[float] = None         # For cross-platform signal
    contract_id: Optional[str] = None                # Contract identifier
    now: Optional[datetime] = None                   # Current time for macro regime
    trend: Optional[str] = None                      # UP/DOWN/FLAT for F&G context
    minutes_remaining: Optional[float] = None        # For dynamic Kelly time decay
    total_window: Optional[float] = None             # Total bet window in minutes
    market_category: Optional[str] = None            # For order flow FLB (crypto/financials/etc)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "true_prob": self.true_prob,
            "market_price": self.market_price,
            "bankroll_cents": self.bankroll_cents,
        }
        if self.price_history is not None:
            d["price_history_len"] = len(self.price_history)
        if self.fear_greed_value is not None:
            d["fear_greed_value"] = self.fear_greed_value
        if self.polymarket_price is not None:
            d["polymarket_price"] = self.polymarket_price
        if self.contract_id is not None:
            d["contract_id"] = self.contract_id
        if self.now is not None:
            d["now"] = self.now.isoformat()
        return d


@dataclass
class StageResult:
    """Result from one pipeline stage."""
    stage: str
    enabled: bool
    ran: bool
    output: Optional[Dict[str, Any]]
    modifier: float  # Sizing modifier (1.0 = no change)
    skip_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "stage": self.stage,
            "enabled": self.enabled,
            "ran": self.ran,
            "modifier": round(self.modifier, 4),
        }
        if self.output is not None:
            d["output"] = self.output
        if self.skip_reason is not None:
            d["skip_reason"] = self.skip_reason
        return d


@dataclass
class SignalDecision:
    """Final pipeline output — the bet/skip decision."""
    action: str                 # BET or SKIP
    kelly_fraction: float       # Raw Kelly fraction
    bet_amount_cents: int       # Final bet size in cents
    edge: float                 # true_prob - market_price
    confidence: float           # Overall confidence (0-1)
    sizing_modifier: float      # Compound modifier from all stages
    stages: List[Dict[str, Any]]  # Per-stage breakdown
    advice: str                 # Human-readable recommendation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "kelly_fraction": round(self.kelly_fraction, 4),
            "bet_amount_cents": self.bet_amount_cents,
            "edge": round(self.edge, 4),
            "confidence": round(self.confidence, 3),
            "sizing_modifier": round(self.sizing_modifier, 4),
            "stages": self.stages,
            "advice": self.advice,
        }


class SignalPipeline:
    """Orchestrates the MT-26 signal intelligence pipeline.

    Runs each stage in order, collects modifiers, and produces
    a final bet sizing recommendation via Dynamic Kelly.
    """

    # Default minimum edge to consider betting
    DEFAULT_MIN_EDGE = 0.03

    def __init__(
        self,
        bankroll_cents: int = 10000,
        min_edge: float = DEFAULT_MIN_EDGE,
        kelly_multiplier: float = 0.5,  # Half-Kelly default (safer)
        max_fraction: float = 0.15,
        enabled_stages: Optional[Dict[str, bool]] = None,
    ):
        self.bankroll_cents = bankroll_cents
        self.min_edge = min_edge
        self.kelly_multiplier = kelly_multiplier
        self.max_fraction = max_fraction
        self.enabled_stages = enabled_stages or {}

    def _is_enabled(self, stage: str) -> bool:
        """Check if a stage is enabled (default: True)."""
        return self.enabled_stages.get(stage, True)

    def run(self, inp: PipelineInput) -> SignalDecision:
        """Run the full pipeline and produce a decision.

        Args:
            inp: PipelineInput with market data.

        Returns:
            SignalDecision with action, sizing, and per-stage breakdown.
        """
        stages = []
        compound_modifier = 1.0

        # Stage 1: Regime Detector
        stage1 = self._run_regime_detector(inp)
        stages.append(stage1.to_dict())
        compound_modifier *= stage1.modifier

        # Stage 2: Calibration Bias
        stage2 = self._run_calibration_bias(inp)
        stages.append(stage2.to_dict())
        compound_modifier *= stage2.modifier

        # Stage 3: Cross-Platform Signal
        stage3 = self._run_cross_platform(inp)
        stages.append(stage3.to_dict())
        compound_modifier *= stage3.modifier

        # Stage 4: Macro Regime Context
        stage4 = self._run_macro_regime(inp)
        stages.append(stage4.to_dict())
        compound_modifier *= stage4.modifier

        # Stage 5: Fear & Greed Filter
        stage5 = self._run_fear_greed(inp)
        stages.append(stage5.to_dict())
        compound_modifier *= stage5.modifier

        # Stage 6: Order Flow Risk (Tier 3)
        stage6 = self._run_order_flow_risk(inp)
        stages.append(stage6.to_dict())
        compound_modifier *= stage6.modifier

        # Stage 7: Dynamic Kelly (always runs — it's the final sizing engine)
        stage7 = self._run_dynamic_kelly(inp, compound_modifier)
        stages.append(stage7.to_dict())
        # Kelly modifier is already baked into the bet sizing

        # Compute final decision
        edge = inp.true_prob - inp.market_price
        kelly_frac = stage7.output.get("kelly_fraction", 0.0) if stage7.output else 0.0

        # Apply compound modifier to Kelly fraction
        adjusted_frac = kelly_frac * compound_modifier
        adjusted_frac = max(0.0, min(self.max_fraction, adjusted_frac))

        bet_cents = int(self.bankroll_cents * adjusted_frac)

        if edge < self.min_edge or adjusted_frac <= 0 or bet_cents <= 0:
            action = "SKIP"
            bet_cents = 0
            adjusted_frac = 0.0
            advice = self._skip_advice(edge, compound_modifier, stages)
        else:
            action = "BET"
            advice = self._bet_advice(
                edge, adjusted_frac, bet_cents, compound_modifier, stages)

        # Overall confidence: average of stage confidences that ran
        confidences = []
        for s in stages:
            if s["ran"] and s.get("output") and "confidence" in s["output"]:
                confidences.append(s["output"]["confidence"])
        confidence = sum(confidences) / len(confidences) if confidences else 0.5

        return SignalDecision(
            action=action,
            kelly_fraction=adjusted_frac,
            bet_amount_cents=bet_cents,
            edge=edge,
            confidence=confidence,
            sizing_modifier=compound_modifier,
            stages=stages,
            advice=advice,
        )

    # --- Stage runners ---

    def _run_regime_detector(self, inp: PipelineInput) -> StageResult:
        """Stage 1: Market regime classification."""
        if not self._is_enabled("regime_detector"):
            return StageResult("regime_detector", False, False, None, 1.0)

        if not inp.price_history or len(inp.price_history) < 10:
            return StageResult(
                "regime_detector", True, False, None, 1.0,
                skip_reason="No price history (need >= 10 prices)")

        from regime_detector import RegimeDetector
        detector = RegimeDetector()
        result = detector.classify_from_prices(inp.price_history)

        # Sizing modifier based on regime
        regime = result["regime"]
        if regime == "CHAOTIC":
            modifier = 0.3  # Severe reduction
        elif regime == "MEAN_REVERTING":
            modifier = 0.8  # Moderate reduction
        elif regime == "TRENDING":
            modifier = 1.0  # Full sizing
        else:
            modifier = 0.7  # Unknown — be cautious

        return StageResult(
            "regime_detector", True, True, result, modifier)

    def _run_calibration_bias(self, inp: PipelineInput) -> StageResult:
        """Stage 2: Calibration bias check.

        For now, reports the bias but doesn't adjust probability —
        the CalibrationBias module needs historical data loaded first.
        The modifier passes through at 1.0 unless configured.
        """
        if not self._is_enabled("calibration_bias"):
            return StageResult("calibration_bias", False, False, None, 1.0)

        # CalibrationBias requires batch historical data — skip if not available.
        # The bot should pre-load calibration data before calling the pipeline.
        return StageResult(
            "calibration_bias", True, False, None, 1.0,
            skip_reason="Calibration data not pre-loaded (bot must call cb.add_batch first)")

    def _run_cross_platform(self, inp: PipelineInput) -> StageResult:
        """Stage 3: Cross-platform divergence signal."""
        if not self._is_enabled("cross_platform"):
            return StageResult("cross_platform", False, False, None, 1.0)

        if inp.polymarket_price is None or inp.contract_id is None:
            return StageResult(
                "cross_platform", True, False, None, 1.0,
                skip_reason="No polymarket price or contract ID")

        from cross_platform_signal import CrossPlatformSignal
        cps = CrossPlatformSignal()
        now_str = (inp.now or datetime.now()).isoformat() + "Z"
        cps.add_observation("kalshi", inp.contract_id,
                            inp.market_price, now_str)
        cps.add_observation("polymarket", inp.contract_id,
                            inp.polymarket_price, now_str)

        signals = cps.get_actionable_signals()
        if signals:
            sig = signals[0]
            output = sig.to_dict()
            # If Polymarket is higher, Kalshi will catch up — bullish for buy
            # Modifier stays at 1.0 (cross-platform is informational, not a sizing filter)
            modifier = 1.0
        else:
            output = {"divergence": abs(inp.market_price - inp.polymarket_price),
                      "actionable": False}
            modifier = 1.0

        return StageResult("cross_platform", True, True, output, modifier)

    def _run_macro_regime(self, inp: PipelineInput) -> StageResult:
        """Stage 4: Macro regime context."""
        if not self._is_enabled("macro_regime"):
            return StageResult("macro_regime", False, False, None, 1.0)

        now = inp.now or datetime.now()

        from macro_regime import MacroRegimeContext
        ctx = MacroRegimeContext()
        result = ctx.classify(now=now)

        modifier = result["sizing_modifier"]

        return StageResult("macro_regime", True, True, result, modifier)

    def _run_fear_greed(self, inp: PipelineInput) -> StageResult:
        """Stage 5: Fear & greed contrarian filter."""
        if not self._is_enabled("fear_greed"):
            return StageResult("fear_greed", False, False, None, 1.0)

        if inp.fear_greed_value is None:
            return StageResult(
                "fear_greed", True, False, None, 1.0,
                skip_reason="No fear & greed value provided")

        from fear_greed_filter import FearGreedFilter
        fgf = FearGreedFilter()

        if inp.trend:
            signal = fgf.classify_with_trend(inp.fear_greed_value, inp.trend)
        else:
            signal = fgf.classify(inp.fear_greed_value)

        output = signal.to_dict()
        modifier = signal.sizing_modifier

        return StageResult("fear_greed", True, True, output, modifier)

    def _run_order_flow_risk(self, inp: PipelineInput) -> StageResult:
        """Stage 6: Order flow risk classification (Tier 3).

        Uses FLB research to flag toxic longshot contracts.
        Sub-10c contracts get modifier=0.0 (SKIP).
        """
        if not self._is_enabled("order_flow_risk"):
            return StageResult("order_flow_risk", False, False, None, 1.0)

        from order_flow_intel import RiskClassifier

        classifier = RiskClassifier()
        category = inp.market_category or "all"
        result = classifier.classify(inp.market_price, category=category)

        risk = result["risk"]
        if risk == "TOXIC":
            modifier = 0.0  # Hard skip — 60%+ loss expected
        elif risk == "UNFAVORABLE":
            modifier = 0.5  # Halve sizing
        elif risk == "NEUTRAL":
            modifier = 0.9  # Slight reduction
        else:  # FAVORABLE
            modifier = 1.0  # Full sizing

        output = {
            "risk": risk,
            "expected_return": round(result["expected_return"], 4),
            "category": category,
            "confidence": 0.85 if risk in ("TOXIC", "FAVORABLE") else 0.65,
        }

        return StageResult("order_flow_risk", True, True, output, modifier)

    def _run_dynamic_kelly(
        self, inp: PipelineInput, compound_modifier: float
    ) -> StageResult:
        """Stage 7: Dynamic Kelly bet sizing (always runs)."""
        from dynamic_kelly import DynamicKelly

        bankroll = max(1, self.bankroll_cents)
        dk = DynamicKelly(
            bankroll_cents=bankroll,
            max_fraction=self.max_fraction,
            kelly_multiplier=self.kelly_multiplier,
        )

        sizing = dk.compute_bet_sizing(
            true_prob=inp.true_prob,
            market_price=inp.market_price,
            minutes_remaining=inp.minutes_remaining,
            total_window=inp.total_window,
        )

        output = sizing.to_dict()

        return StageResult("dynamic_kelly", True, True, output, 1.0)

    # --- Advice generators ---

    def _bet_advice(
        self, edge, frac, cents, modifier, stages
    ) -> str:
        active_filters = [s["stage"] for s in stages
                          if s["ran"] and s["modifier"] < 1.0]
        filter_note = ""
        if active_filters:
            filter_note = f" Reduced by: {', '.join(active_filters)}."
        return (
            f"BET {cents} cents ({frac:.1%} of bankroll). "
            f"Edge: {edge:.1%}. Compound modifier: {modifier:.2f}.{filter_note}"
        )

    def _skip_advice(self, edge, modifier, stages) -> str:
        if edge < self.min_edge:
            return (
                f"SKIP — edge too thin ({edge:.1%} < {self.min_edge:.1%}). "
                f"Wait for better opportunity."
            )
        if modifier < 0.1:
            reducing = [s["stage"] for s in stages
                        if s["ran"] and s["modifier"] < 0.5]
            return (
                f"SKIP — sizing modifier too low ({modifier:.2f}). "
                f"Filters: {', '.join(reducing)}."
            )
        return f"SKIP — insufficient edge or sizing after all filters."


def _cli():
    """CLI interface."""
    import argparse
    parser = argparse.ArgumentParser(description="MT-26 Signal Pipeline")
    parser.add_argument("--true-prob", type=float, required=True)
    parser.add_argument("--market-price", type=float, required=True)
    parser.add_argument("--bankroll", type=int, default=10000)
    parser.add_argument("--fg-value", type=int, default=None)
    parser.add_argument("--poly-price", type=float, default=None)
    parser.add_argument("--contract", type=str, default=None)
    parser.add_argument("--kelly-mult", type=float, default=0.5)
    args = parser.parse_args()

    pipeline = SignalPipeline(
        bankroll_cents=args.bankroll,
        kelly_multiplier=args.kelly_mult,
    )

    inp = PipelineInput(
        true_prob=args.true_prob,
        market_price=args.market_price,
        bankroll_cents=args.bankroll,
        fear_greed_value=args.fg_value,
        polymarket_price=args.poly_price,
        contract_id=args.contract,
        now=datetime.now(),
    )

    decision = pipeline.run(inp)
    print(json.dumps(decision.to_dict(), indent=2))


if __name__ == "__main__":
    _cli()
