#!/usr/bin/env python3
"""correlated_loss_analyzer.py — REQ-054: Cross-asset loss correlation detection.

Detects when losses in multiple crypto assets (BTC, ETH, SOL) cluster within
short time windows, indicating correlated exposure. Quantifies the coincidence
rate vs independent baseline, and recommends mitigation strategies.

Key insight: Crypto assets are highly correlated during market stress (correlation
approaches 1.0 in crashes). If the Kalshi bot holds positions in BTC AND ETH
simultaneously, a market-wide drop produces correlated losses that compound.

This module:
1. Clusters loss events by time window (default 30 min)
2. Computes observed coincidence rate (what fraction of losses co-occur)
3. Compares to expected rate under independence assumption
4. Recommends staggering, exposure caps, or diversification if correlated

Usage:
    from correlated_loss_analyzer import WindowAnalyzer, LossEvent
    from datetime import datetime

    events = [
        LossEvent("BTC", -5.0, datetime(2026, 3, 25, 14, 0)),
        LossEvent("ETH", -3.0, datetime(2026, 3, 25, 14, 10)),
    ]
    analyzer = WindowAnalyzer(window_minutes=30)
    result = analyzer.analyze(events)
    print(result.summary_text())

Stdlib only. No external dependencies.
"""
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set


@dataclass
class LossEvent:
    """A single loss event on a specific asset."""
    ticker: str
    amount: float        # Negative = loss
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "amount": round(self.amount, 2),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class LossCluster:
    """A cluster of loss events within a time window."""
    events: List[LossEvent]
    window_start: datetime
    window_end: datetime

    @property
    def total_loss(self) -> float:
        return sum(e.amount for e in self.events)

    @property
    def asset_count(self) -> int:
        return len({e.ticker for e in self.events})

    @property
    def tickers(self) -> Set[str]:
        return {e.ticker for e in self.events}

    @property
    def is_multi_asset(self) -> bool:
        return self.asset_count > 1

    def to_dict(self) -> dict:
        return {
            "events": [e.to_dict() for e in self.events],
            "total_loss": round(self.total_loss, 2),
            "asset_count": self.asset_count,
            "tickers": sorted(self.tickers),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
        }


@dataclass
class CorrelationResult:
    """Result of correlated loss analysis."""
    coincidence_rate: float    # Fraction of losses that co-occur
    expected_rate: float       # Expected rate under independence
    excess_correlation: float  # Observed - expected
    clusters: List[LossCluster]
    multi_asset_clusters: int
    total_events: int
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "coincidence_rate": round(self.coincidence_rate, 4),
            "expected_rate": round(self.expected_rate, 4),
            "excess_correlation": round(self.excess_correlation, 4),
            "multi_asset_clusters": self.multi_asset_clusters,
            "total_events": self.total_events,
            "clusters": [c.to_dict() for c in self.clusters],
            "recommendation": self.recommendation,
        }

    def summary_text(self) -> str:
        lines = [
            "Correlated Loss Analysis",
            "=" * 40,
            f"Total loss events: {self.total_events}",
            f"Loss clusters: {len(self.clusters)}",
            f"Multi-asset clusters: {self.multi_asset_clusters}",
            f"Coincidence rate: {self.coincidence_rate:.1%}",
            f"Expected (independent): {self.expected_rate:.1%}",
            f"Excess correlation: {self.excess_correlation:+.1%}",
            "",
            f"Recommendation: {self.recommendation}",
        ]
        return "\n".join(lines)


def coincidence_rate(
    btc_times: List[datetime],
    eth_times: List[datetime],
    window_minutes: int = 30,
) -> float:
    """Compute what fraction of BTC loss times have an ETH loss within the window.

    Returns 0-1 fraction. Symmetric: checks from BTC→ETH perspective.
    """
    if not btc_times or not eth_times:
        return 0.0

    window = timedelta(minutes=window_minutes)
    matches = 0

    for bt in btc_times:
        for et in eth_times:
            if abs(bt - et) <= window:
                matches += 1
                break  # Count each BTC event at most once

    return matches / len(btc_times)


def expected_coincidence(
    btc_loss_rate: float,
    eth_loss_rate: float,
) -> float:
    """Expected coincidence rate if losses are independent.

    P(both lose) = P(BTC loses) * P(ETH loses) under independence.
    """
    return btc_loss_rate * eth_loss_rate


def loss_clusters(
    events: List[LossEvent],
    window_minutes: int = 30,
) -> List[LossCluster]:
    """Cluster loss events by time proximity.

    Events within window_minutes of each other are grouped into the same cluster.
    Uses a simple greedy approach: sort by time, extend cluster if next event
    is within window of the cluster's last event.
    """
    if not events:
        return []

    sorted_events = sorted(events, key=lambda e: e.timestamp)
    window = timedelta(minutes=window_minutes)

    clusters: List[LossCluster] = []
    current_events = [sorted_events[0]]

    for ev in sorted_events[1:]:
        if ev.timestamp - current_events[-1].timestamp <= window:
            current_events.append(ev)
        else:
            clusters.append(LossCluster(
                events=current_events,
                window_start=current_events[0].timestamp,
                window_end=current_events[-1].timestamp,
            ))
            current_events = [ev]

    # Don't forget the last cluster
    clusters.append(LossCluster(
        events=current_events,
        window_start=current_events[0].timestamp,
        window_end=current_events[-1].timestamp,
    ))

    return clusters


class WindowAnalyzer:
    """Full correlated loss analysis engine."""

    def __init__(self, window_minutes: int = 30):
        self.window_minutes = window_minutes

    def analyze(self, events: List[LossEvent]) -> CorrelationResult:
        """Run full correlation analysis on a set of loss events."""
        if not events:
            return CorrelationResult(
                coincidence_rate=0.0,
                expected_rate=0.0,
                excess_correlation=0.0,
                clusters=[],
                multi_asset_clusters=0,
                total_events=0,
                recommendation="No loss events to analyze.",
            )

        # Cluster events
        clusters = loss_clusters(events, self.window_minutes)
        multi_asset = [c for c in clusters if c.is_multi_asset]

        # Compute coincidence rate
        btc_times = [e.timestamp for e in events if e.ticker == "BTC"]
        eth_times = [e.timestamp for e in events if e.ticker == "ETH"]
        observed = coincidence_rate(btc_times, eth_times, self.window_minutes)

        # Expected under independence
        total_events = len(events)
        btc_rate = len(btc_times) / total_events if total_events > 0 else 0
        eth_rate = len(eth_times) / total_events if total_events > 0 else 0
        expected = expected_coincidence(btc_rate, eth_rate)

        excess = observed - expected

        # Generate recommendation
        recommendation = self._recommend(observed, expected, len(multi_asset), len(clusters))

        return CorrelationResult(
            coincidence_rate=observed,
            expected_rate=expected,
            excess_correlation=excess,
            clusters=clusters,
            multi_asset_clusters=len(multi_asset),
            total_events=total_events,
            recommendation=recommendation,
        )

    def _recommend(
        self,
        observed: float,
        expected: float,
        multi_count: int,
        total_clusters: int,
    ) -> str:
        """Generate mitigation recommendation based on correlation level."""
        if observed == 0 or total_clusters == 0:
            return "No correlated losses detected. Current exposure is diversified."

        ratio = multi_count / total_clusters if total_clusters > 0 else 0

        if observed > 0.5 or ratio > 0.5:
            return (
                "HIGH correlation: stagger BTC and ETH entries by at least "
                f"{self.window_minutes} minutes. Consider a combined exposure "
                "cap (e.g., max $15 total across all crypto in any 30-min window). "
                "Adding non-crypto assets (sports sniper) reduces portfolio correlation."
            )
        elif observed > 0.2 or ratio > 0.25:
            return (
                "MODERATE correlation: consider time-staggering entries across "
                "crypto assets. Monitor combined exposure in same time window."
            )
        else:
            return (
                "LOW correlation: current loss patterns appear mostly independent. "
                "Continue monitoring."
            )


def main():
    """CLI: example correlated loss analysis."""
    # Simulated loss events from a trading day
    events = [
        LossEvent("BTC", -5.0, datetime(2026, 3, 25, 10, 0)),
        LossEvent("ETH", -3.5, datetime(2026, 3, 25, 10, 8)),
        LossEvent("BTC", -4.0, datetime(2026, 3, 25, 14, 0)),
        LossEvent("ETH", -2.0, datetime(2026, 3, 25, 14, 12)),
        LossEvent("SOL", -1.5, datetime(2026, 3, 25, 14, 15)),
        LossEvent("BTC", -6.0, datetime(2026, 3, 25, 20, 0)),
        LossEvent("BTC", -3.0, datetime(2026, 3, 25, 22, 30)),
        LossEvent("ETH", -2.5, datetime(2026, 3, 25, 22, 35)),
    ]

    analyzer = WindowAnalyzer(window_minutes=30)
    result = analyzer.analyze(events)
    print(result.summary_text())

    if "--json" in sys.argv:
        print(json.dumps(result.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()
