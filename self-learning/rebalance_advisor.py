#!/usr/bin/env python3
"""rebalance_advisor.py — MT-37 Layer 5: Rebalancing recommendations.

Implements a hybrid threshold + calendar rebalancing strategy.
Detects portfolio drift from target allocation and generates
actionable BUY/SELL recommendations.

Academic basis:
- DeMiguel et al. (2009): 1/N baseline; threshold rebalancing outperforms
  calendar-only for transaction cost reduction
- Daryanani (2008): 5% absolute threshold is the practical sweet spot
  (balances tracking error vs transaction costs)
- Jaconetti et al. (2010, Vanguard): hybrid threshold+calendar dominates
  pure calendar — fewer trades, lower costs, tighter tracking

The advisor checks two triggers:
1. Threshold: any asset drifts >= threshold from target (default 5%)
2. Calendar: days since last rebalance >= interval (default 90 days)

If either fires, it generates per-asset BUY/SELL actions to restore
target allocation.

Usage:
    from rebalance_advisor import RebalanceAdvisor

    advisor = RebalanceAdvisor(drift_threshold=0.05, calendar_interval_days=90)
    rec = advisor.analyze(
        current={"VTI": 0.70, "VXUS": 0.20, "BND": 0.10},
        target={"VTI": 0.60, "VXUS": 0.30, "BND": 0.10},
        days_since_last=45,
        bankroll=100000,
    )
    if rec.should_rebalance:
        for action in rec.actions:
            print(action.summary_text())

Stdlib only. No external dependencies.
"""
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RebalanceTrigger(Enum):
    THRESHOLD = "THRESHOLD"
    CALENDAR = "CALENDAR"


@dataclass
class DriftResult:
    """Per-asset drift from target allocation."""
    drifts: Dict[str, float]  # ticker -> signed drift (positive = overweight)
    max_drift: float          # Absolute max drift across all assets
    total_drift: float        # Sum of absolute drifts

    def to_dict(self) -> dict:
        return {
            "drifts": {k: round(v, 4) for k, v in self.drifts.items()},
            "max_drift": round(self.max_drift, 4),
            "total_drift": round(self.total_drift, 4),
        }


@dataclass
class RebalanceAction:
    """A single rebalancing trade recommendation."""
    ticker: str
    direction: str       # "BUY" or "SELL"
    amount_pct: float    # Absolute percentage of portfolio to trade
    dollar_amount: float = 0.0  # Dollar amount if bankroll provided

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "direction": self.direction,
            "amount_pct": round(self.amount_pct, 4),
            "dollar_amount": round(self.dollar_amount, 2),
        }

    def summary_text(self) -> str:
        if self.dollar_amount > 0:
            return f"{self.direction} {self.ticker}: {self.amount_pct:.1%} (${self.dollar_amount:,.0f})"
        return f"{self.direction} {self.ticker}: {self.amount_pct:.1%}"


@dataclass
class RebalanceRecommendation:
    """Full rebalancing recommendation."""
    should_rebalance: bool
    triggers: List[RebalanceTrigger]
    actions: List[RebalanceAction]
    drift: DriftResult

    def to_dict(self) -> dict:
        return {
            "should_rebalance": self.should_rebalance,
            "triggers": [t.value for t in self.triggers],
            "actions": [a.to_dict() for a in self.actions],
            "drift": self.drift.to_dict(),
        }

    def summary_text(self) -> str:
        if not self.should_rebalance:
            return "No rebalancing needed — portfolio within tolerance."
        lines = ["Rebalancing recommended:"]
        lines.append(f"  Triggers: {', '.join(t.value for t in self.triggers)}")
        lines.append(f"  Max drift: {self.drift.max_drift:.1%}")
        for a in self.actions:
            lines.append(f"  {a.summary_text()}")
        return "\n".join(lines)


def drift_analysis(
    current: Dict[str, float],
    target: Dict[str, float],
) -> DriftResult:
    """Compute per-asset drift between current and target allocations.

    Both dicts map ticker -> weight (0-1 scale).
    Missing tickers in either dict are treated as 0.
    """
    all_tickers = set(current) | set(target)
    drifts = {}
    for ticker in all_tickers:
        c = current.get(ticker, 0.0)
        t = target.get(ticker, 0.0)
        drifts[ticker] = round(c - t, 10)  # Avoid float noise

    abs_drifts = [abs(d) for d in drifts.values()]
    max_drift = max(abs_drifts) if abs_drifts else 0.0
    total_drift = sum(abs_drifts)

    return DriftResult(drifts=drifts, max_drift=max_drift, total_drift=total_drift)


def threshold_trigger(
    current: Dict[str, float],
    target: Dict[str, float],
    threshold: float = 0.05,
) -> bool:
    """Check if any asset has drifted >= threshold from target."""
    result = drift_analysis(current, target)
    return result.max_drift >= threshold


def calendar_trigger(days_since_last: int, interval_days: int = 90) -> bool:
    """Check if enough time has passed since last rebalance."""
    return days_since_last >= interval_days


class RebalanceAdvisor:
    """Hybrid threshold + calendar rebalancing advisor.

    Checks both drift threshold and calendar interval. If either
    triggers, generates per-asset BUY/SELL actions to restore target.
    """

    def __init__(
        self,
        drift_threshold: float = 0.05,
        calendar_interval_days: int = 90,
    ):
        self.drift_threshold = drift_threshold
        self.calendar_interval_days = calendar_interval_days

    def analyze(
        self,
        current: Dict[str, float],
        target: Dict[str, float],
        days_since_last: int = 0,
        bankroll: float = 0.0,
    ) -> RebalanceRecommendation:
        """Analyze portfolio and generate rebalancing recommendation."""
        drift = drift_analysis(current, target)
        triggers: List[RebalanceTrigger] = []

        if threshold_trigger(current, target, self.drift_threshold):
            triggers.append(RebalanceTrigger.THRESHOLD)

        if calendar_trigger(days_since_last, self.calendar_interval_days):
            triggers.append(RebalanceTrigger.CALENDAR)

        should_rebalance = len(triggers) > 0

        actions: List[RebalanceAction] = []
        if should_rebalance:
            for ticker, d in sorted(drift.drifts.items()):
                if abs(d) < 1e-9:
                    continue
                direction = "SELL" if d > 0 else "BUY"
                amount_pct = abs(d)
                dollar_amount = amount_pct * bankroll if bankroll > 0 else 0.0
                actions.append(RebalanceAction(
                    ticker=ticker,
                    direction=direction,
                    amount_pct=amount_pct,
                    dollar_amount=dollar_amount,
                ))

        return RebalanceRecommendation(
            should_rebalance=should_rebalance,
            triggers=triggers,
            actions=actions,
            drift=drift,
        )


def main():
    """CLI: example rebalancing analysis."""
    current = {
        "VTI": 0.68, "VXUS": 0.18, "BND": 0.08, "VTIP": 0.06,
    }
    target = {
        "VTI": 0.55, "VXUS": 0.25, "BND": 0.15, "VTIP": 0.05,
    }

    advisor = RebalanceAdvisor(drift_threshold=0.05, calendar_interval_days=90)
    rec = advisor.analyze(current, target, days_since_last=45, bankroll=500000)

    print("Portfolio Rebalancing Advisor")
    print("=" * 50)
    print(rec.summary_text())

    if "--json" in sys.argv:
        print(json.dumps(rec.to_dict(), indent=2))


if __name__ == "__main__":
    main()
