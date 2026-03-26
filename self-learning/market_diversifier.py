#!/usr/bin/env python3
"""market_diversifier.py — REQ-055: Cross-market diversification analysis.

Analyzes a portfolio of prediction market positions across asset classes
(crypto, sports, politics, weather, economics) and quantifies concentration
risk using the Herfindahl-Hirschman Index (HHI).

Key insight: Kalshi positions across different asset classes are structurally
uncorrelated (BTC price is independent of Lakers winning). Diversifying across
classes reduces portfolio variance without sacrificing expected edge.

This module:
1. Classifies positions by asset class
2. Computes HHI (concentration metric: 0 = perfectly diversified, 1 = fully concentrated)
3. Calculates effective number of markets (1/HHI)
4. Recommends diversification actions when concentrated

Usage:
    from market_diversifier import DiversificationAdvisor, MarketPosition, AssetClass

    positions = [
        MarketPosition("btc-100k", AssetClass.CRYPTO, 20.0, "BTC"),
        MarketPosition("lakers-win", AssetClass.SPORTS, 10.0),
    ]
    advisor = DiversificationAdvisor()
    result = advisor.analyze(positions)
    print(result.summary_text())

Stdlib only. No external dependencies.
"""
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class AssetClass(Enum):
    """Asset classes for prediction market positions."""
    CRYPTO = "CRYPTO"
    SPORTS = "SPORTS"
    POLITICS = "POLITICS"
    WEATHER = "WEATHER"
    ECONOMICS = "ECONOMICS"
    OTHER = "OTHER"


@dataclass
class MarketPosition:
    """A single prediction market position."""
    market_id: str
    asset_class: AssetClass
    amount: float  # Dollar amount at risk
    ticker: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "market_id": self.market_id,
            "asset_class": self.asset_class.value,
            "amount": round(self.amount, 2),
            "ticker": self.ticker,
        }


@dataclass
class ConcentrationResult:
    """Result of diversification analysis."""
    hhi: float  # Herfindahl-Hirschman Index (0-1)
    effective_markets_count: float  # 1/HHI
    risk_level: str  # HIGH / MODERATE / LOW
    class_weights: Dict[AssetClass, float]
    total_exposure: float
    max_class_exposure: float
    recommendations: List[str]

    def to_dict(self) -> dict:
        return {
            "hhi": round(self.hhi, 4),
            "effective_markets": round(self.effective_markets_count, 2),
            "risk_level": self.risk_level,
            "class_weights": {k.value: round(v, 4) for k, v in self.class_weights.items()},
            "total_exposure": round(self.total_exposure, 2),
            "max_class_exposure": round(self.max_class_exposure, 4),
            "recommendations": self.recommendations,
        }

    def summary_text(self) -> str:
        lines = [
            "Diversification Analysis",
            "=" * 40,
            f"Total exposure: ${self.total_exposure:,.0f}",
            f"HHI: {self.hhi:.3f} (1.0 = fully concentrated)",
            f"Effective markets: {self.effective_markets_count:.1f}",
            f"Risk level: {self.risk_level}",
            f"Max single-class exposure: {self.max_class_exposure:.1%}",
            "",
            "Class breakdown:",
        ]
        for cls, weight in sorted(self.class_weights.items(), key=lambda x: -x[1]):
            lines.append(f"  {cls.value}: {weight:.1%}")

        if self.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for rec in self.recommendations:
                lines.append(f"  - {rec}")

        return "\n".join(lines)


def herfindahl_index(weights: Dict[str, float]) -> float:
    """Compute Herfindahl-Hirschman Index from weight dictionary.

    HHI = sum(w_i^2) where w_i are portfolio weights.
    Range: 1/N (perfectly diversified) to 1.0 (fully concentrated).
    """
    if not weights:
        return 0.0
    return sum(w ** 2 for w in weights.values())


def effective_markets(weights: Dict[str, float]) -> float:
    """Effective number of markets = 1 / HHI.

    Represents how many equally-weighted markets would produce the same HHI.
    """
    hhi = herfindahl_index(weights)
    if hhi == 0:
        return 0.0
    return 1.0 / hhi


def concentration_risk(weights: Dict[str, float], high_threshold: float = 0.5, moderate_threshold: float = 0.3) -> str:
    """Classify concentration risk based on HHI thresholds.

    Default thresholds:
    - HIGH: HHI >= 0.5 (effectively 2 or fewer markets)
    - MODERATE: HHI >= 0.3
    - LOW: HHI < 0.3
    """
    hhi = herfindahl_index(weights)
    if hhi >= high_threshold:
        return "HIGH"
    elif hhi >= moderate_threshold:
        return "MODERATE"
    return "LOW"


class DiversificationAdvisor:
    """Full diversification analysis engine for prediction market portfolios."""

    def __init__(self, high_threshold: float = 0.5, moderate_threshold: float = 0.3):
        self.high_threshold = high_threshold
        self.moderate_threshold = moderate_threshold

    def analyze(self, positions: List[MarketPosition]) -> ConcentrationResult:
        """Run diversification analysis on a set of market positions."""
        if not positions:
            return ConcentrationResult(
                hhi=0.0,
                effective_markets_count=0.0,
                risk_level="LOW",
                class_weights={},
                total_exposure=0.0,
                max_class_exposure=0.0,
                recommendations=[],
            )

        # Aggregate by asset class
        class_totals: Dict[AssetClass, float] = defaultdict(float)
        for pos in positions:
            class_totals[pos.asset_class] += pos.amount

        total = sum(class_totals.values())
        if total <= 0:
            return ConcentrationResult(
                hhi=0.0,
                effective_markets_count=0.0,
                risk_level="LOW",
                class_weights={},
                total_exposure=0.0,
                max_class_exposure=0.0,
                recommendations=[],
            )

        # Compute weights
        class_weights = {cls: amt / total for cls, amt in class_totals.items()}
        weight_values = {cls.value: w for cls, w in class_weights.items()}

        # Compute metrics
        hhi = herfindahl_index(weight_values)
        eff = effective_markets(weight_values)
        risk = concentration_risk(weight_values, self.high_threshold, self.moderate_threshold)
        max_exposure = max(class_weights.values()) if class_weights else 0.0

        # Generate recommendations
        recommendations = self._recommend(class_weights, hhi, max_exposure)

        return ConcentrationResult(
            hhi=hhi,
            effective_markets_count=eff,
            risk_level=risk,
            class_weights=class_weights,
            total_exposure=total,
            max_class_exposure=max_exposure,
            recommendations=recommendations,
        )

    def _recommend(
        self,
        class_weights: Dict[AssetClass, float],
        hhi: float,
        max_exposure: float,
    ) -> List[str]:
        """Generate diversification recommendations."""
        recs = []

        if not class_weights:
            return recs

        # Find dominant class
        dominant = max(class_weights, key=class_weights.get)
        dominant_pct = class_weights[dominant]

        if dominant_pct > 0.70:
            recs.append(
                f"CRITICAL: {dominant.value} is {dominant_pct:.0%} of portfolio. "
                f"Cap at 50% and redistribute to uncorrelated classes."
            )

        if hhi >= self.high_threshold:
            # Find missing classes
            all_classes = set(AssetClass)
            present = set(class_weights.keys())
            missing = all_classes - present - {AssetClass.OTHER}
            if missing:
                missing_names = ", ".join(sorted(c.value for c in missing))
                recs.append(
                    f"Add positions in underrepresented classes: {missing_names}. "
                    f"Structural independence reduces portfolio variance."
                )

        if hhi >= self.moderate_threshold and len(class_weights) <= 2:
            recs.append(
                "Expand to 3+ asset classes. Two-class portfolios remain "
                "vulnerable to single-class drawdowns."
            )

        return recs


def main():
    """CLI: example diversification analysis."""
    positions = [
        MarketPosition("btc-above-100k", AssetClass.CRYPTO, 25.0, "BTC"),
        MarketPosition("eth-above-4k", AssetClass.CRYPTO, 15.0, "ETH"),
        MarketPosition("sol-above-200", AssetClass.CRYPTO, 10.0, "SOL"),
        MarketPosition("lakers-win-series", AssetClass.SPORTS, 5.0),
        MarketPosition("fed-rate-cut", AssetClass.ECONOMICS, 3.0),
    ]

    advisor = DiversificationAdvisor()
    result = advisor.analyze(positions)
    print(result.summary_text())

    if "--json" in sys.argv:
        print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
