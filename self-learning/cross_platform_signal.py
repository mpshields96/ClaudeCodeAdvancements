#!/usr/bin/env python3
"""
cross_platform_signal.py — MT-26 Phase 1: Cross-Platform Signal

Detects price divergences between prediction market platforms (Kalshi and
Polymarket) and generates signals for the Kalshi bot. Based on SSRN:5331995
finding that Polymarket leads Kalshi in price discovery — when Polymarket
moves first on correlated contracts, that's a free leading indicator.

Key concepts:
- Price divergence: |kalshi_price - polymarket_price| for same contract
- Lag analysis: Which platform moves first (leader vs follower)
- Actionable signal: Divergence above threshold with sufficient confidence

The bot can use this to:
- Buy on Kalshi when Polymarket price is significantly higher (Kalshi will catch up)
- Sell on Kalshi when Polymarket price is significantly lower
- Time entries using Polymarket as a leading indicator

Usage:
    from cross_platform_signal import CrossPlatformSignal

    cps = CrossPlatformSignal(min_divergence=0.03)
    cps.add_observation("kalshi", "BTC-UP-100K", 0.55, "2026-03-21T10:00:00Z")
    cps.add_observation("polymarket", "BTC-UP-100K", 0.65, "2026-03-21T10:00:00Z")
    signals = cps.get_actionable_signals()
    # [DivergenceSignal(divergence=0.10, direction=POLYMARKET_HIGHER, ...)]

Zero external dependencies. Stdlib only.
"""

import json
import math
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


VALID_PLATFORMS = ("kalshi", "polymarket")


class SignalDirection(Enum):
    """Which platform has the higher price."""
    KALSHI_HIGHER = "kalshi_higher"
    POLYMARKET_HIGHER = "polymarket_higher"
    CONVERGED = "converged"


@dataclass
class PriceObservation:
    """A single price observation from a platform."""
    platform: str
    contract_id: str
    price: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "contract_id": self.contract_id,
            "price": round(self.price, 4),
            "timestamp": self.timestamp,
        }


@dataclass
class DivergenceSignal:
    """A detected price divergence between platforms."""
    contract_id: str
    kalshi_price: float
    polymarket_price: float
    divergence: float             # |kalshi - polymarket|
    direction: SignalDirection
    confidence: float             # 0-1, based on consistency of divergence
    timestamp: str
    actionable: bool              # True if divergence > threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "kalshi_price": round(self.kalshi_price, 4),
            "polymarket_price": round(self.polymarket_price, 4),
            "divergence": round(self.divergence, 4),
            "direction": self.direction.value,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp,
            "actionable": self.actionable,
        }


class CrossPlatformSignal:
    """
    Cross-platform price divergence detector and signal generator.

    Tracks prices from Kalshi and Polymarket, detects divergences,
    analyzes which platform leads, and generates actionable signals.
    """

    def __init__(
        self,
        min_divergence: float = 0.03,
        lookback_window: int = 30,  # minutes
        confidence_threshold: float = 0.5,
    ):
        if min_divergence < 0:
            raise ValueError(f"min_divergence must be >= 0, got {min_divergence}")
        if lookback_window <= 0:
            raise ValueError(f"lookback_window must be > 0, got {lookback_window}")

        self.min_divergence = min_divergence
        self.lookback_window = lookback_window
        self.confidence_threshold = confidence_threshold
        self.observations: List[PriceObservation] = []

    def add_observation(
        self,
        platform: str,
        contract_id: str,
        price: float,
        timestamp: str,
    ) -> None:
        """Add a price observation from a platform."""
        if platform not in VALID_PLATFORMS:
            raise ValueError(
                f"Invalid platform: {platform}. Must be one of {VALID_PLATFORMS}"
            )
        if not 0.0 <= price <= 1.0:
            raise ValueError(f"price must be in [0, 1], got {price}")

        self.observations.append(PriceObservation(
            platform=platform,
            contract_id=contract_id,
            price=price,
            timestamp=timestamp,
        ))

    def add_batch(self, observations: List[Dict[str, Any]]) -> None:
        """Add multiple observations at once."""
        for obs in observations:
            self.add_observation(
                platform=obs["platform"],
                contract_id=obs["contract_id"],
                price=obs["price"],
                timestamp=obs["timestamp"],
            )

    def _group_by_timestamp(
        self, contract_id: str
    ) -> Dict[str, Dict[str, float]]:
        """
        Group observations by timestamp, returning {timestamp: {platform: price}}.
        """
        groups: Dict[str, Dict[str, float]] = {}
        for obs in self.observations:
            if obs.contract_id != contract_id:
                continue
            if obs.timestamp not in groups:
                groups[obs.timestamp] = {}
            groups[obs.timestamp][obs.platform] = obs.price
        return groups

    def detect_divergences(
        self, contract_id: str
    ) -> List[DivergenceSignal]:
        """
        Detect price divergences for a specific contract.

        Pairs up observations by timestamp and computes divergence
        for each pair where both platforms have data.
        """
        groups = self._group_by_timestamp(contract_id)
        signals = []

        # Track divergences for confidence calculation
        divergence_history = []

        for timestamp in sorted(groups.keys()):
            prices = groups[timestamp]
            if "kalshi" not in prices or "polymarket" not in prices:
                continue

            kalshi_price = prices["kalshi"]
            poly_price = prices["polymarket"]
            divergence = abs(kalshi_price - poly_price)
            divergence_history.append(divergence)

            if poly_price > kalshi_price:
                direction = SignalDirection.POLYMARKET_HIGHER
            elif kalshi_price > poly_price:
                direction = SignalDirection.KALSHI_HIGHER
            else:
                direction = SignalDirection.CONVERGED

            # Confidence based on consistency: if divergence is consistent
            # across observations, confidence is higher
            if len(divergence_history) >= 2:
                mean_div = sum(divergence_history) / len(divergence_history)
                if mean_div > 0:
                    consistency = 1 - (
                        sum(abs(d - mean_div) for d in divergence_history)
                        / (len(divergence_history) * mean_div)
                    )
                    confidence = max(0, min(1, consistency))
                else:
                    confidence = 0
            else:
                confidence = 0.5  # Single observation — moderate confidence

            actionable = (
                divergence >= self.min_divergence
                and confidence >= self.confidence_threshold
            )

            signals.append(DivergenceSignal(
                contract_id=contract_id,
                kalshi_price=kalshi_price,
                polymarket_price=poly_price,
                divergence=round(divergence, 4),
                direction=direction,
                confidence=round(confidence, 4),
                timestamp=timestamp,
                actionable=actionable,
            ))

        return signals

    def analyze_lag(self, contract_id: str) -> Dict[str, Any]:
        """
        Analyze which platform leads in price discovery.

        Returns dict with:
        - leader: "polymarket", "kalshi", or "unknown"
        - avg_divergence: average |kalshi - polymarket|
        - n_observations: number of paired observations
        - lead_count: {platform: times_it_was_higher}
        """
        groups = self._group_by_timestamp(contract_id)
        paired = []

        for timestamp in sorted(groups.keys()):
            prices = groups[timestamp]
            if "kalshi" in prices and "polymarket" in prices:
                paired.append({
                    "timestamp": timestamp,
                    "kalshi": prices["kalshi"],
                    "polymarket": prices["polymarket"],
                })

        if not paired:
            return {
                "leader": "unknown",
                "avg_divergence": 0,
                "n_observations": 0,
                "lead_count": {"kalshi": 0, "polymarket": 0},
            }

        divergences = [abs(p["kalshi"] - p["polymarket"]) for p in paired]
        avg_div = sum(divergences) / len(divergences)

        # Count which platform moves higher more often
        # The platform with the higher price more often is likely leading
        # (since Polymarket leads, it should show the new price first)
        kalshi_leads = sum(1 for p in paired if p["kalshi"] > p["polymarket"])
        poly_leads = sum(1 for p in paired if p["polymarket"] > p["kalshi"])

        if poly_leads > kalshi_leads:
            leader = "polymarket"
        elif kalshi_leads > poly_leads:
            leader = "kalshi"
        else:
            leader = "unknown"

        return {
            "leader": leader,
            "avg_divergence": round(avg_div, 4),
            "n_observations": len(paired),
            "lead_count": {"kalshi": kalshi_leads, "polymarket": poly_leads},
        }

    def get_actionable_signals(self) -> List[DivergenceSignal]:
        """
        Get all actionable divergence signals across all contracts.

        Returns only signals where divergence > min_divergence
        and confidence > confidence_threshold.
        """
        # Get unique contract IDs
        contract_ids = set(obs.contract_id for obs in self.observations)
        all_signals = []

        for contract_id in contract_ids:
            signals = self.detect_divergences(contract_id)
            actionable = [s for s in signals if s.actionable]
            all_signals.extend(actionable)

        return all_signals

    def save(self, path: str) -> None:
        """Save observation data to JSON file."""
        data = {
            "min_divergence": self.min_divergence,
            "lookback_window": self.lookback_window,
            "confidence_threshold": self.confidence_threshold,
            "observations": [obs.to_dict() for obs in self.observations],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "CrossPlatformSignal":
        """Load observation data from JSON file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"No signal file at {path}")

        with open(path) as f:
            data = json.load(f)

        cps = cls(
            min_divergence=data["min_divergence"],
            lookback_window=data["lookback_window"],
            confidence_threshold=data.get("confidence_threshold", 0.5),
        )
        for obs_data in data["observations"]:
            cps.add_observation(
                platform=obs_data["platform"],
                contract_id=obs_data["contract_id"],
                price=obs_data["price"],
                timestamp=obs_data["timestamp"],
            )
        return cps


def main():
    """CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(description="Cross-Platform Signal Detector")
    sub = parser.add_subparsers(dest="command")

    # analyze
    analyze_p = sub.add_parser("analyze", help="Analyze price data file")
    analyze_p.add_argument("data_file", help="JSON file with observations")
    analyze_p.add_argument("--contract", help="Contract ID to analyze")

    # signals
    signals_p = sub.add_parser("signals", help="Get actionable signals")
    signals_p.add_argument("data_file", help="JSON file with observations")

    args = parser.parse_args()

    if args.command == "analyze":
        cps = CrossPlatformSignal.load(args.data_file)
        if args.contract:
            lag = cps.analyze_lag(args.contract)
            print(json.dumps(lag, indent=2))
        else:
            contracts = set(obs.contract_id for obs in cps.observations)
            for cid in sorted(contracts):
                lag = cps.analyze_lag(cid)
                print(f"{cid}: leader={lag['leader']}, "
                      f"avg_div={lag['avg_divergence']:.4f}, "
                      f"n={lag['n_observations']}")

    elif args.command == "signals":
        cps = CrossPlatformSignal.load(args.data_file)
        signals = cps.get_actionable_signals()
        if not signals:
            print("No actionable signals.")
        else:
            for s in signals:
                print(json.dumps(s.to_dict(), indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
