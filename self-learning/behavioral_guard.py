#!/usr/bin/env python3
"""behavioral_guard.py — MT-37 Layer 5: Behavioral bias detection.

Detects common investor behavioral biases and generates evidence-based
counter-recommendations. Runs on every portfolio action to flag when
the user's behavior contradicts academic evidence.

Biases detected:
1. Disposition effect — selling winners, holding losers (Shefrin & Statman 1985)
2. Loss aversion — overreacting to losses (Kahneman & Tversky 1979)
3. Recency bias — chasing recent performance (Tversky & Kahneman 1973)
4. Home bias — over-weighting domestic assets (French & Poterba 1991)
5. Overconfidence — excessive trading frequency (Barber & Odean 2000)

Academic basis:
- Kahneman & Tversky (1979): Prospect theory — losses hurt ~2x gains
- Shefrin & Statman (1985): Disposition effect in individual investors
- Barber & Odean (2000): Trading is hazardous to your wealth
- French & Poterba (1991): Investor diversification and intl equity markets
- Benartzi & Thaler (1995): Myopic loss aversion and equity premium puzzle

Usage:
    from behavioral_guard import BehavioralGuard

    guard = BehavioralGuard()
    alerts = guard.scan({
        "trades": [{"ticker": "AAPL", "action": "SELL", "gain_pct": 0.20}],
        "holdings_with_losses": [{"ticker": "META", "unrealized_gain_pct": -0.30}],
        "recent_loss_pct": -0.15,
        "proposed_action": "reduce_equity",
        "weights": {"VTI": 0.85, "VXUS": 0.10, "BND": 0.05},
        "domestic_tickers": {"VTI", "BND"},
        "trades_per_month": 12,
    })
    for alert in alerts:
        print(f"[{alert.severity.value}] {alert.bias.value}: {alert.message}")

Stdlib only. No external dependencies.
"""
import json
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set


class Bias(Enum):
    DISPOSITION_EFFECT = "DISPOSITION_EFFECT"
    LOSS_AVERSION = "LOSS_AVERSION"
    RECENCY_BIAS = "RECENCY_BIAS"
    HOME_BIAS = "HOME_BIAS"
    OVERCONFIDENCE = "OVERCONFIDENCE"


class BiasSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class BiasAlert:
    """A detected behavioral bias with recommendation."""
    bias: Bias
    severity: BiasSeverity
    message: str
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "bias": self.bias.value,
            "severity": self.severity.value,
            "message": self.message,
            "recommendation": self.recommendation,
        }


# ── Individual Detectors ────────────────────────────────────────────────────


def detect_disposition_effect(
    trades: List[dict],
    holdings_with_losses: List[dict],
) -> Optional[BiasAlert]:
    """Detect disposition effect: selling winners while holding losers.

    Shefrin & Statman (1985): investors are 1.5x more likely to sell
    a winning stock than a losing one. This locks in gains too early
    and lets losses compound.
    """
    # Check for sells of winning positions
    winning_sells = [
        t for t in trades
        if t.get("action") == "SELL" and t.get("gain_pct", 0) > 0
    ]

    if not winning_sells or not holdings_with_losses:
        return None

    worst_holding = min(
        holdings_with_losses,
        key=lambda h: h.get("unrealized_gain_pct", 0),
    )
    worst_loss = worst_holding.get("unrealized_gain_pct", 0)

    if worst_loss >= 0:
        return None

    severity = BiasSeverity.HIGH if worst_loss < -0.20 else BiasSeverity.MEDIUM

    return BiasAlert(
        bias=Bias.DISPOSITION_EFFECT,
        severity=severity,
        message=(
            f"Selling winner(s) while holding {worst_holding['ticker']} "
            f"at {worst_loss:.0%} unrealized loss."
        ),
        recommendation=(
            "Consider whether the losing position still has a valid thesis. "
            "Selling winners and holding losers reduces after-tax returns "
            "(Shefrin & Statman 1985). Evaluate each position on its forward "
            "merit, not its purchase price."
        ),
    )


def detect_loss_aversion(
    recent_loss_pct: float,
    proposed_action: str,
    loss_threshold: float = -0.05,
) -> Optional[BiasAlert]:
    """Detect loss aversion: overreacting to recent portfolio losses.

    Kahneman & Tversky (1979): losses are felt ~2x as strongly as
    equivalent gains. After a drawdown, investors often flee to cash
    precisely when expected returns are highest.
    """
    if recent_loss_pct >= loss_threshold:
        return None

    risk_reducing_actions = {"reduce_equity", "sell_all", "move_to_cash", "go_defensive"}
    if proposed_action not in risk_reducing_actions:
        return None

    severity = BiasSeverity.HIGH if recent_loss_pct < -0.15 else BiasSeverity.MEDIUM

    return BiasAlert(
        bias=Bias.LOSS_AVERSION,
        severity=severity,
        message=(
            f"Portfolio down {recent_loss_pct:.0%} recently. "
            f"Proposed action '{proposed_action}' may be loss-aversion driven."
        ),
        recommendation=(
            "After significant losses, expected future returns are typically "
            "higher, not lower. Selling after a drawdown locks in losses and "
            "misses recovery (Benartzi & Thaler 1995). If your risk tolerance "
            "and time horizon haven't changed, stay the course."
        ),
    )


def detect_recency_bias(
    recent_top: dict,
    proposed_buy: str,
    return_threshold: float = 0.15,
) -> Optional[BiasAlert]:
    """Detect recency bias: chasing recent top performers.

    Tversky & Kahneman (1973): availability heuristic causes
    overweighting of recent, salient information. Past 3-month
    returns don't predict future returns.
    """
    if recent_top.get("ticker") != proposed_buy:
        return None

    if recent_top.get("return_3m", 0) < return_threshold:
        return None

    ret = recent_top["return_3m"]
    severity = BiasSeverity.HIGH if ret > 0.30 else BiasSeverity.MEDIUM

    return BiasAlert(
        bias=Bias.RECENCY_BIAS,
        severity=severity,
        message=(
            f"Buying {proposed_buy} which returned {ret:.0%} in the last 3 months. "
            f"Recent performance does not predict future returns."
        ),
        recommendation=(
            "Short-term outperformance often mean-reverts. Chasing hot stocks "
            "is the #1 return-destroying behavior for individual investors "
            "(Barber & Odean 2000). Buy based on valuation and allocation "
            "targets, not recent momentum."
        ),
    )


def detect_home_bias(
    weights: Dict[str, float],
    domestic_tickers: Set[str],
    threshold: float = 0.70,
) -> Optional[BiasAlert]:
    """Detect home country bias: over-weighting domestic assets.

    French & Poterba (1991): US investors hold ~80% domestic despite
    US being ~60% of world market cap. International diversification
    improves risk-adjusted returns.
    """
    if not weights:
        return None

    domestic_weight = sum(
        w for t, w in weights.items() if t in domestic_tickers
    )

    if domestic_weight <= threshold:
        return None

    severity = BiasSeverity.MEDIUM if domestic_weight < 0.90 else BiasSeverity.HIGH

    return BiasAlert(
        bias=Bias.HOME_BIAS,
        severity=severity,
        message=(
            f"Domestic allocation is {domestic_weight:.0%}, above {threshold:.0%} threshold. "
            f"US is ~60% of global market cap."
        ),
        recommendation=(
            "International diversification reduces portfolio risk without "
            "sacrificing expected returns (French & Poterba 1991). Consider "
            "allocating 30-40% to international equities (VXUS, IXUS) to "
            "match global market weights."
        ),
    )


def detect_overconfidence(
    trades_per_month: float,
    threshold: float = 10,
) -> Optional[BiasAlert]:
    """Detect overconfidence via excessive trading frequency.

    Barber & Odean (2000): the most active traders underperform by
    6.5% annually due to transaction costs and poor timing. Trading
    frequency is a reliable proxy for overconfidence.
    """
    if trades_per_month < threshold:
        return None

    severity = BiasSeverity.HIGH if trades_per_month > 20 else BiasSeverity.MEDIUM

    return BiasAlert(
        bias=Bias.OVERCONFIDENCE,
        severity=severity,
        message=(
            f"Trading frequency: {trades_per_month:.0f} trades/month "
            f"(threshold: {threshold:.0f})."
        ),
        recommendation=(
            "High trading frequency strongly predicts underperformance. "
            "Barber & Odean (2000) showed the most active quintile of "
            "traders earned 6.5% less annually than the least active. "
            "Reduce trading and let compounding work."
        ),
    )


# ── Orchestrator ────────────────────────────────────────────────────────────


class BehavioralGuard:
    """Orchestrates all behavioral bias checks on a portfolio context."""

    def __init__(
        self,
        home_bias_threshold: float = 0.70,
        overconfidence_threshold: float = 10,
    ):
        self.home_bias_threshold = home_bias_threshold
        self.overconfidence_threshold = overconfidence_threshold

    def scan(self, context: dict) -> List[BiasAlert]:
        """Run all bias detectors against the provided context.

        Context keys:
            trades: list of recent trade dicts
            holdings_with_losses: list of holdings with unrealized losses
            recent_loss_pct: float, recent portfolio loss (negative)
            proposed_action: str, what the user wants to do
            weights: dict of ticker -> weight
            domestic_tickers: set of domestic ticker symbols
            trades_per_month: float, recent trading frequency
            recent_top: dict with ticker + return_3m (optional)
            proposed_buy: str (optional)
        """
        alerts: List[BiasAlert] = []

        # 1. Disposition effect
        disposition = detect_disposition_effect(
            context.get("trades", []),
            context.get("holdings_with_losses", []),
        )
        if disposition:
            alerts.append(disposition)

        # 2. Loss aversion
        loss_av = detect_loss_aversion(
            context.get("recent_loss_pct", 0.0),
            context.get("proposed_action", "hold"),
        )
        if loss_av:
            alerts.append(loss_av)

        # 3. Recency bias
        if "recent_top" in context and "proposed_buy" in context:
            recency = detect_recency_bias(
                context["recent_top"],
                context["proposed_buy"],
            )
            if recency:
                alerts.append(recency)

        # 4. Home bias
        home = detect_home_bias(
            context.get("weights", {}),
            context.get("domestic_tickers", set()),
            self.home_bias_threshold,
        )
        if home:
            alerts.append(home)

        # 5. Overconfidence
        overconf = detect_overconfidence(
            context.get("trades_per_month", 0),
            self.overconfidence_threshold,
        )
        if overconf:
            alerts.append(overconf)

        return alerts

    def summary_text(self, alerts: List[BiasAlert]) -> str:
        """Generate human-readable summary of all alerts."""
        if not alerts:
            return "No behavioral biases detected."
        lines = [f"Behavioral Guard: {len(alerts)} alert(s) detected"]
        for a in alerts:
            lines.append(f"  [{a.severity.value}] {a.bias.value}: {a.message}")
            lines.append(f"    Recommendation: {a.recommendation}")
        return "\n".join(lines)

    def to_dict(self, alerts: List[BiasAlert]) -> list:
        """Serialize alerts to list of dicts."""
        return [a.to_dict() for a in alerts]


def main():
    """CLI: example behavioral guard scan."""
    context = {
        "trades": [
            {"ticker": "AAPL", "action": "SELL", "gain_pct": 0.25},
        ],
        "holdings_with_losses": [
            {"ticker": "META", "unrealized_gain_pct": -0.35},
            {"ticker": "BABA", "unrealized_gain_pct": -0.50},
        ],
        "recent_loss_pct": -0.12,
        "proposed_action": "reduce_equity",
        "weights": {"VTI": 0.85, "VXUS": 0.10, "BND": 0.05},
        "domestic_tickers": {"VTI", "BND"},
        "trades_per_month": 15,
    }

    guard = BehavioralGuard()
    alerts = guard.scan(context)

    print("Behavioral Guard Report")
    print("=" * 50)
    print(guard.summary_text(alerts))

    if "--json" in sys.argv:
        print(json.dumps(guard.to_dict(alerts), indent=2))


if __name__ == "__main__":
    main()
