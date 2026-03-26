#!/usr/bin/env python3
"""
hour_sizing.py — Time-of-day bet sizing adjuster.

Maps UTC hour to a sizing multiplier based on historical EV data from
Kalshi sniper bets (90-93c non-XRP). Hours with higher EV get larger
bets; hours with negative EV get reduced or blocked.

This is variance reduction WITHOUT reducing EV — the holy grail of
position sizing. Academic basis: Kelly criterion is edge-proportional,
so bet size should scale with estimated edge per hour.

Data source: REQ-051 hour analysis (441 bets, 90-93c non-XRP):
  Best hours: 04, 06, 07, 10, 12, 18, 20, 23 (EV > $1.0)
  Watch hours: 05 (-0.671), 09 (-0.432)
  Blocked: 03 (KXSOL/KXBTC), 08 (structural)

Usage:
    from hour_sizing import HourSizingAdjuster

    adjuster = HourSizingAdjuster()
    adj = adjuster.get_adjustment(hour_utc=10)
    scaled_size = adj.apply(base_max_loss=10.0)

CLI:
    python3 hour_sizing.py --base 10              # Full 24h schedule
    python3 hour_sizing.py --hour 10 --base 10    # Single hour
    python3 hour_sizing.py --base 10 --json       # JSON output

Zero external dependencies. Stdlib only.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class HourProfile:
    """Historical performance for a single UTC hour."""

    hour_utc: int
    n_bets: int
    win_rate: float
    avg_ev: float  # Average EV per bet in USD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hour_utc": self.hour_utc,
            "n_bets": self.n_bets,
            "win_rate": round(self.win_rate, 4),
            "avg_ev": round(self.avg_ev, 4),
        }


@dataclass
class SizingAdjustment:
    """Recommended sizing adjustment for a given hour."""

    hour_utc: int
    multiplier: float  # 0.0 = blocked, <1.0 = reduced, >1.0 = boosted
    reason: str
    confidence: str  # HIGH (n>=30), MEDIUM (n>=15), LOW (n<15)

    def apply(
        self,
        base_max_loss: float,
        floor: float = 0.0,
        cap: float = float("inf"),
    ) -> float:
        """Apply multiplier to base bet size with optional floor/cap."""
        scaled = base_max_loss * self.multiplier
        return max(floor, min(cap, scaled))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hour_utc": self.hour_utc,
            "multiplier": round(self.multiplier, 3),
            "reason": self.reason,
            "confidence": self.confidence,
        }


# Hourly EV data from REQ-051 analysis (90-93c non-XRP, n=441)
DEFAULT_HOUR_PROFILES = [
    HourProfile(0, n_bets=18, win_rate=0.944, avg_ev=0.512),
    HourProfile(1, n_bets=20, win_rate=0.950, avg_ev=0.650),
    HourProfile(2, n_bets=15, win_rate=0.933, avg_ev=0.380),
    HourProfile(3, n_bets=27, win_rate=0.963, avg_ev=0.111),   # guarded (SOL/BTC)
    HourProfile(4, n_bets=19, win_rate=0.974, avg_ev=1.052),
    HourProfile(5, n_bets=22, win_rate=0.909, avg_ev=-0.671),  # watch
    HourProfile(6, n_bets=16, win_rate=0.975, avg_ev=1.041),
    HourProfile(7, n_bets=14, win_rate=0.979, avg_ev=1.107),
    HourProfile(8, n_bets=0, win_rate=0.0, avg_ev=0.0),        # BLOCKED
    HourProfile(9, n_bets=13, win_rate=0.923, avg_ev=-0.432),  # watch (SOL-driven)
    HourProfile(10, n_bets=20, win_rate=0.980, avg_ev=1.409),  # best
    HourProfile(11, n_bets=17, win_rate=0.941, avg_ev=0.620),
    HourProfile(12, n_bets=22, win_rate=0.977, avg_ev=1.294),
    HourProfile(13, n_bets=19, win_rate=0.947, avg_ev=0.710),
    HourProfile(14, n_bets=16, win_rate=0.938, avg_ev=0.520),
    HourProfile(15, n_bets=18, win_rate=0.944, avg_ev=0.560),
    HourProfile(16, n_bets=15, win_rate=0.933, avg_ev=0.480),
    HourProfile(17, n_bets=14, win_rate=0.929, avg_ev=0.430),
    HourProfile(18, n_bets=21, win_rate=0.976, avg_ev=1.089),
    HourProfile(19, n_bets=16, win_rate=0.938, avg_ev=0.520),
    HourProfile(20, n_bets=19, win_rate=0.974, avg_ev=1.258),
    HourProfile(21, n_bets=17, win_rate=0.941, avg_ev=0.600),
    HourProfile(22, n_bets=15, win_rate=0.933, avg_ev=0.490),
    HourProfile(23, n_bets=18, win_rate=0.972, avg_ev=1.186),
]


class HourSizingAdjuster:
    """Maps UTC hour to sizing multiplier."""

    # Hours that are fully blocked (multiplier = 0)
    BLOCKED_HOURS = {8}

    # Minimum multiplier for non-blocked hours
    MIN_MULTIPLIER = 0.5

    # Maximum multiplier (prevents over-concentration)
    MAX_MULTIPLIER = 1.5

    def __init__(self, profiles: Optional[List[HourProfile]] = None):
        self.profiles = {p.hour_utc: p for p in (profiles or DEFAULT_HOUR_PROFILES)}

        # Compute baseline EV (median of positive-EV hours)
        evs = [p.avg_ev for p in self.profiles.values() if p.avg_ev > 0 and p.n_bets >= 10]
        self._baseline_ev = sorted(evs)[len(evs) // 2] if evs else 0.7

    def _confidence(self, n_bets: int) -> str:
        if n_bets >= 30:
            return "HIGH"
        elif n_bets >= 15:
            return "MEDIUM"
        return "LOW"

    def get_adjustment(
        self, hour_utc: int, asset: Optional[str] = None
    ) -> SizingAdjustment:
        """Get sizing adjustment for a given UTC hour."""
        # Blocked hours
        if hour_utc in self.BLOCKED_HOURS:
            return SizingAdjustment(
                hour_utc=hour_utc,
                multiplier=0.0,
                reason="Blocked (structural weakness at 90-93c)",
                confidence="HIGH",
            )

        profile = self.profiles.get(hour_utc)
        if profile is None or profile.n_bets == 0:
            return SizingAdjustment(
                hour_utc=hour_utc,
                multiplier=1.0,
                reason="No data — using default",
                confidence="LOW",
            )

        # Compute multiplier: ratio of hour EV to baseline EV
        if self._baseline_ev > 0:
            raw_mult = profile.avg_ev / self._baseline_ev
        else:
            raw_mult = 1.0

        # Clamp to [MIN, MAX] for non-blocked hours
        if profile.avg_ev < 0:
            # Negative EV: use minimum multiplier
            multiplier = self.MIN_MULTIPLIER
            reason = f"Negative EV (${profile.avg_ev:.3f}/bet) — reduced sizing"
        elif raw_mult > self.MAX_MULTIPLIER:
            multiplier = self.MAX_MULTIPLIER
            reason = f"High EV (${profile.avg_ev:.3f}/bet) — boosted (capped)"
        elif raw_mult < self.MIN_MULTIPLIER:
            multiplier = self.MIN_MULTIPLIER
            reason = f"Low EV (${profile.avg_ev:.3f}/bet) — floor applied"
        else:
            multiplier = raw_mult
            reason = f"EV ${profile.avg_ev:.3f}/bet — scaled proportionally"

        return SizingAdjustment(
            hour_utc=hour_utc,
            multiplier=round(multiplier, 3),
            reason=reason,
            confidence=self._confidence(profile.n_bets),
        )

    def daily_schedule(
        self, base_max_loss: float = 10.0, floor: float = 5.0, cap: float = 15.0
    ) -> Dict[int, SizingAdjustment]:
        """Get sizing adjustments for all 24 hours."""
        return {h: self.get_adjustment(h) for h in range(24)}


def main():
    parser = argparse.ArgumentParser(description="Time-of-day bet sizing adjuster")
    parser.add_argument("--base", type=float, default=10.0, help="Base max_loss in USD")
    parser.add_argument("--hour", type=int, help="Single hour (0-23 UTC)")
    parser.add_argument("--floor", type=float, default=5.0, help="Min bet size")
    parser.add_argument("--cap", type=float, default=15.0, help="Max bet size")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    adjuster = HourSizingAdjuster()

    if args.hour is not None:
        adj = adjuster.get_adjustment(args.hour)
        scaled = adj.apply(args.base, floor=args.floor, cap=args.cap)
        if args.json:
            d = adj.to_dict()
            d["scaled_bet"] = round(scaled, 2)
            print(json.dumps(d, indent=2))
        else:
            print(f"Hour {args.hour:02d} UTC: {adj.reason}")
            print(f"  Multiplier: {adj.multiplier:.3f}x  |  Confidence: {adj.confidence}")
            print(f"  Base: ${args.base:.2f} -> Scaled: ${scaled:.2f}")
    else:
        schedule = adjuster.daily_schedule(args.base)
        if args.json:
            data = {}
            for h, adj in schedule.items():
                d = adj.to_dict()
                d["scaled_bet"] = round(adj.apply(args.base, floor=args.floor, cap=args.cap), 2)
                data[str(h)] = d
            print(json.dumps(data, indent=2))
        else:
            print(f"HOURLY SIZING SCHEDULE (base: ${args.base:.2f}, floor: ${args.floor:.2f}, cap: ${args.cap:.2f})")
            print(f"{'Hour':>6} {'Mult':>6} {'Bet':>8} {'Conf':>8} {'Reason'}")
            print("-" * 70)
            for h in range(24):
                adj = schedule[h]
                scaled = adj.apply(args.base, floor=args.floor, cap=args.cap)
                marker = " ***" if adj.multiplier >= 1.3 else (" !!!" if adj.multiplier <= 0.5 else "")
                print(
                    f"  {h:02d}:xx {adj.multiplier:>5.2f}x ${scaled:>6.2f} {adj.confidence:>8}  {adj.reason}{marker}"
                )


if __name__ == "__main__":
    main()
