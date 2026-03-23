#!/usr/bin/env python3
"""
calibration_bias.py — MT-26 Phase 1: Calibration Bias Exploiter

Identifies systematic mispricing in prediction market contracts by computing
calibration curves, detecting bias direction per domain, and providing
bias-adjusted probability estimates.

Based on Le (2026) arXiv:2602.19520 — calibration decomposes into 4 components
explaining 87.3% of variance. Crypto contracts may have different bias direction
than political ones. The Favorite-Longshot Bias (FLB) is a known mispricing
pattern where low-priced contracts lose 60%+ (per "Makers and Takers" UCD paper).

Usage:
    from calibration_bias import CalibrationBias

    cb = CalibrationBias(n_bins=10)
    cb.add_batch(historical_contracts)
    result = cb.analyze(domain="crypto")
    # result.bias_direction, result.mispricing_zones, result.calibration_curve

    adjusted = cb.adjust_probability(0.65, domain="crypto")
    # Returns bias-corrected probability

Zero external dependencies. Stdlib only.
"""

import json
import math
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metric_config import get_metric


class BiasDirection(Enum):
    """Direction of systematic calibration bias."""
    OVERCONFIDENT = "overconfident"   # Market price > true probability
    UNDERCONFIDENT = "underconfident"  # Market price < true probability
    MIXED = "mixed"                   # Different bias at different price levels
    NONE = "none"                     # Insufficient data or no significant bias


@dataclass
class MispricingZone:
    """A price range where systematic mispricing exists."""
    price_range: Tuple[float, float]  # (low, high) of the bin
    bias: float                        # mean_predicted - actual_freq (positive = overconfident)
    direction: BiasDirection
    confidence: float                  # Statistical confidence (0-1)
    n_samples: int
    exploitable: bool                  # True if bias > threshold and confidence > 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "price_range": list(self.price_range),
            "bias": round(self.bias, 4),
            "direction": self.direction.value,
            "confidence": round(self.confidence, 4),
            "n_samples": self.n_samples,
            "exploitable": self.exploitable,
        }


@dataclass
class CalibrationResult:
    """Full calibration analysis result for a domain."""
    domain: str
    bias_direction: BiasDirection
    mean_bias: float                           # Average (predicted - actual) across bins
    max_bias: float                            # Maximum absolute bias in any bin
    n_contracts: int
    calibration_curve: List[Dict[str, Any]]
    mispricing_zones: List[MispricingZone]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "bias_direction": self.bias_direction.value,
            "mean_bias": round(self.mean_bias, 4),
            "max_bias": round(self.max_bias, 4),
            "n_contracts": self.n_contracts,
            "calibration_curve": self.calibration_curve,
            "mispricing_zones": [z.to_dict() for z in self.mispricing_zones],
        }


class CalibrationBias:
    """
    Calibration bias analysis for prediction market contracts.

    Computes calibration curves, detects systematic bias direction per domain,
    identifies exploitable mispricing zones, and provides bias-adjusted
    probability estimates.
    """

    # Thresholds loaded from metric_config (user-overridable via ~/.cca-metrics.json)
    EXPLOITABLE_BIAS_THRESHOLD = get_metric("calibration_bias.exploitable_bias_threshold", 0.03)
    EXPLOITABLE_CONFIDENCE_THRESHOLD = get_metric("calibration_bias.exploitable_confidence_threshold", 0.70)

    def __init__(self, n_bins: int = 10, min_samples_per_bin: int = 20):
        if n_bins <= 0:
            raise ValueError(f"n_bins must be positive, got {n_bins}")
        if min_samples_per_bin <= 0:
            raise ValueError(f"min_samples_per_bin must be positive, got {min_samples_per_bin}")
        self.n_bins = n_bins
        self.min_samples_per_bin = min_samples_per_bin
        self.contracts: List[Dict[str, Any]] = []
        self._results: Dict[str, CalibrationResult] = {}

    def add_contract(self, market_price: float, outcome: int, domain: str) -> None:
        """Add a single historical contract observation."""
        if not 0.0 <= market_price <= 1.0:
            raise ValueError(f"market_price must be in [0, 1], got {market_price}")
        if outcome not in (0, 1):
            raise ValueError(f"outcome must be 0 or 1, got {outcome}")
        self.contracts.append({
            "market_price": market_price,
            "outcome": outcome,
            "domain": domain,
        })

    def add_batch(self, contracts: List[Dict[str, Any]]) -> None:
        """Add multiple contracts at once."""
        for c in contracts:
            self.add_contract(
                market_price=c["market_price"],
                outcome=c["outcome"],
                domain=c["domain"],
            )

    def compute_calibration_curve(
        self, domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Compute binned calibration curve.

        Returns list of dicts with:
        - bin_center: center of the probability bin
        - mean_predicted: average market price in this bin
        - actual_freq: fraction of outcomes that were 1
        - count: number of contracts in this bin
        - bias: mean_predicted - actual_freq (positive = overconfident)
        """
        # Filter by domain
        if domain is not None:
            filtered = [c for c in self.contracts if c["domain"] == domain]
        else:
            filtered = self.contracts

        if not filtered:
            return []

        # Create bins
        bin_width = 1.0 / self.n_bins
        bins: Dict[int, List[Dict]] = {i: [] for i in range(self.n_bins)}

        for c in filtered:
            bin_idx = min(int(c["market_price"] / bin_width), self.n_bins - 1)
            bins[bin_idx].append(c)

        curve = []
        for i in range(self.n_bins):
            entries = bins[i]
            if len(entries) < self.min_samples_per_bin:
                continue

            bin_center = (i + 0.5) * bin_width
            mean_predicted = sum(e["market_price"] for e in entries) / len(entries)
            actual_freq = sum(e["outcome"] for e in entries) / len(entries)
            bias = mean_predicted - actual_freq

            curve.append({
                "bin_center": round(bin_center, 4),
                "mean_predicted": round(mean_predicted, 4),
                "actual_freq": round(actual_freq, 4),
                "count": len(entries),
                "bias": round(bias, 4),
            })

        return curve

    def _compute_confidence(self, p_hat: float, n: int) -> float:
        """
        Wilson score confidence that observed proportion differs from expected.

        Returns confidence in [0, 1] — higher means more certain the bias is real.
        """
        if n == 0:
            return 0.0
        # Standard error of proportion
        se = math.sqrt(p_hat * (1 - p_hat) / n) if 0 < p_hat < 1 else 1.0 / math.sqrt(n)
        if se == 0:
            return 1.0
        # z-score (how many SEs the bias is from zero)
        # We already have the bias, but for confidence we use the actual_freq vs bin_center
        # Simplification: confidence = 1 - 2 * P(z) where z = |bias| / se
        # Using approximation since we can't import scipy
        z = abs(p_hat) / se if se > 0 else 0
        # Approximate normal CDF for confidence
        confidence = min(1.0, z / 3.0)  # Linear approx, saturates at z=3
        return confidence

    def analyze(self, domain: str) -> CalibrationResult:
        """
        Full calibration analysis for a domain.

        Returns CalibrationResult with bias direction, mispricing zones,
        and calibration curve.
        """
        domain_contracts = [c for c in self.contracts if c["domain"] == domain]
        n_contracts = len(domain_contracts)

        curve = self.compute_calibration_curve(domain=domain)

        if not curve:
            result = CalibrationResult(
                domain=domain,
                bias_direction=BiasDirection.NONE,
                mean_bias=0.0,
                max_bias=0.0,
                n_contracts=n_contracts,
                calibration_curve=[],
                mispricing_zones=[],
            )
            self._results[domain] = result
            return result

        # Compute overall bias metrics
        biases = [e["bias"] for e in curve]
        mean_bias = sum(biases) / len(biases)
        max_bias = max(abs(b) for b in biases)

        # Determine bias direction
        positive_count = sum(1 for b in biases if b > 0.02)
        negative_count = sum(1 for b in biases if b < -0.02)

        if positive_count > len(biases) * 0.6:
            bias_direction = BiasDirection.OVERCONFIDENT
        elif negative_count > len(biases) * 0.6:
            bias_direction = BiasDirection.UNDERCONFIDENT
        elif positive_count > 0 and negative_count > 0:
            bias_direction = BiasDirection.MIXED
        else:
            bias_direction = BiasDirection.NONE

        # Find mispricing zones
        bin_width = 1.0 / self.n_bins
        mispricing_zones = []
        for entry in curve:
            bias = entry["bias"]
            abs_bias = abs(bias)
            n = entry["count"]
            actual_freq = entry["actual_freq"]

            confidence = self._compute_confidence(bias, n)

            if abs_bias > 0.01:  # Only report zones with meaningful bias
                zone_dir = BiasDirection.OVERCONFIDENT if bias > 0 else BiasDirection.UNDERCONFIDENT
                bin_center = entry["bin_center"]
                price_range = (
                    round(max(0, bin_center - bin_width / 2), 4),
                    round(min(1, bin_center + bin_width / 2), 4),
                )

                exploitable = (
                    abs_bias > self.EXPLOITABLE_BIAS_THRESHOLD
                    and confidence > self.EXPLOITABLE_CONFIDENCE_THRESHOLD
                )

                mispricing_zones.append(MispricingZone(
                    price_range=price_range,
                    bias=round(bias, 4),
                    direction=zone_dir,
                    confidence=round(confidence, 4),
                    n_samples=n,
                    exploitable=exploitable,
                ))

        result = CalibrationResult(
            domain=domain,
            bias_direction=bias_direction,
            mean_bias=round(mean_bias, 4),
            max_bias=round(max_bias, 4),
            n_contracts=n_contracts,
            calibration_curve=curve,
            mispricing_zones=mispricing_zones,
        )
        self._results[domain] = result
        return result

    def adjust_probability(self, market_price: float, domain: str) -> float:
        """
        Return bias-adjusted probability for a given market price.

        If no analysis has been run for this domain, returns the original price.
        Uses linear interpolation between calibration curve points.
        """
        if domain not in self._results:
            return market_price

        result = self._results[domain]
        curve = result.calibration_curve
        if not curve:
            return market_price

        # Find the two nearest calibration points and interpolate
        # Sort by bin_center
        sorted_curve = sorted(curve, key=lambda e: e["bin_center"])

        # If market_price is below all bins, use first bin's bias
        if market_price <= sorted_curve[0]["bin_center"]:
            adjusted = market_price - sorted_curve[0]["bias"]
        # If above all bins, use last bin's bias
        elif market_price >= sorted_curve[-1]["bin_center"]:
            adjusted = market_price - sorted_curve[-1]["bias"]
        else:
            # Linear interpolation between two nearest bins
            for i in range(len(sorted_curve) - 1):
                if sorted_curve[i]["bin_center"] <= market_price <= sorted_curve[i + 1]["bin_center"]:
                    # Interpolation factor
                    span = sorted_curve[i + 1]["bin_center"] - sorted_curve[i]["bin_center"]
                    if span == 0:
                        t = 0
                    else:
                        t = (market_price - sorted_curve[i]["bin_center"]) / span
                    bias = sorted_curve[i]["bias"] * (1 - t) + sorted_curve[i + 1]["bias"] * t
                    adjusted = market_price - bias
                    break
            else:
                adjusted = market_price

        # Clamp to [0, 1]
        return max(0.0, min(1.0, adjusted))

    def save(self, path: str) -> None:
        """Save calibration data to JSON file."""
        data = {
            "n_bins": self.n_bins,
            "min_samples_per_bin": self.min_samples_per_bin,
            "contracts": self.contracts,
            "results": {
                domain: result.to_dict()
                for domain, result in self._results.items()
            },
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "CalibrationBias":
        """Load calibration data from JSON file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"No calibration file at {path}")

        with open(path) as f:
            data = json.load(f)

        cb = cls(
            n_bins=data["n_bins"],
            min_samples_per_bin=data["min_samples_per_bin"],
        )
        cb.contracts = data["contracts"]

        # Re-run analysis to rebuild _results with proper dataclass instances
        domains = set(c["domain"] for c in cb.contracts)
        for domain in domains:
            cb.analyze(domain)

        return cb


def main():
    """CLI interface for calibration bias analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Calibration Bias Exploiter")
    subparsers = parser.add_subparsers(dest="command")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze calibration bias")
    analyze_parser.add_argument("data_file", help="JSON file with contract data")
    analyze_parser.add_argument("--domain", required=True, help="Domain to analyze")
    analyze_parser.add_argument("--bins", type=int, default=10, help="Number of bins")

    # adjust command
    adjust_parser = subparsers.add_parser("adjust", help="Get adjusted probability")
    adjust_parser.add_argument("data_file", help="JSON file with contract data")
    adjust_parser.add_argument("--domain", required=True, help="Domain")
    adjust_parser.add_argument("--price", type=float, required=True, help="Market price to adjust")
    adjust_parser.add_argument("--bins", type=int, default=10, help="Number of bins")

    args = parser.parse_args()

    if args.command == "analyze":
        with open(args.data_file) as f:
            contracts = json.load(f)
        cb = CalibrationBias(n_bins=args.bins, min_samples_per_bin=5)
        cb.add_batch(contracts)
        result = cb.analyze(domain=args.domain)
        print(json.dumps(result.to_dict(), indent=2))

    elif args.command == "adjust":
        with open(args.data_file) as f:
            contracts = json.load(f)
        cb = CalibrationBias(n_bins=args.bins, min_samples_per_bin=5)
        cb.add_batch(contracts)
        cb.analyze(domain=args.domain)
        adjusted = cb.adjust_probability(args.price, domain=args.domain)
        print(json.dumps({
            "market_price": args.price,
            "adjusted_price": round(adjusted, 4),
            "domain": args.domain,
        }))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
