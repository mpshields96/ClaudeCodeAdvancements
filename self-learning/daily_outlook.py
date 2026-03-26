#!/usr/bin/env python3
"""
daily_outlook.py — Daily performance outlook predictor.

Chains volume_predictor (BTC range -> bet count) with sizing_optimizer
(bet count + size -> daily EV/SD -> P(target)) to give a single daily
outlook at session start.

Usage:
    from daily_outlook import DailyOutlook

    outlook = DailyOutlook(max_loss_usd=10.0, daily_target=20.0)
    result = outlook.predict(btc_range_usd=2400.0)
    print(result.summary())

CLI:
    python3 daily_outlook.py --btc-range 2400
    python3 daily_outlook.py --btc-range 2400 --max-loss 12.5 --target 20 --json
    python3 daily_outlook.py --btc-range 2400 --sweep

Zero external dependencies. Stdlib only.
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class VolumeScenario:
    """Volume band from BTC 24h range."""

    label: str  # LOW, MEDIUM, HIGH
    bets_low: int
    bets_high: int

    @property
    def midpoint(self) -> int:
        return int((self.bets_low + self.bets_high) / 2)


# Volume bands calibrated from volume_predictor.py
VOLUME_BANDS = [
    VolumeScenario(label="LOW", bets_low=15, bets_high=40),
    VolumeScenario(label="MEDIUM", bets_low=40, bets_high=80),
    VolumeScenario(label="HIGH", bets_low=80, bets_high=140),
]

# BTC range thresholds (from volume_predictor.py)
BTC_RANGE_LOW = 1000  # Below this = LOW volume
BTC_RANGE_HIGH = 2500  # Above this = HIGH volume


def _classify_volume(btc_range_usd: float, is_weekend: bool = False) -> VolumeScenario:
    """Map BTC 24h range to volume band."""
    if btc_range_usd < BTC_RANGE_LOW:
        band = VOLUME_BANDS[0]  # LOW
    elif btc_range_usd > BTC_RANGE_HIGH:
        band = VOLUME_BANDS[2]  # HIGH
    else:
        band = VOLUME_BANDS[1]  # MEDIUM

    if is_weekend:
        # 0.7x multiplier for weekends
        return VolumeScenario(
            label=band.label,
            bets_low=int(band.bets_low * 0.7),
            bets_high=int(band.bets_high * 0.7),
        )
    return band


def _normal_cdf(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


@dataclass
class OutlookResult:
    """Daily performance outlook."""

    volume_band: str
    estimated_bets: int
    max_loss_usd: float
    daily_target: float
    expected_daily_pnl: float
    daily_sd: float
    p_daily_target: float
    p_5day_target: float
    verdict: str  # LIKELY, POSSIBLE, UNLIKELY
    is_weekend: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "volume_band": self.volume_band,
            "estimated_bets": self.estimated_bets,
            "max_loss_usd": round(self.max_loss_usd, 2),
            "daily_target": round(self.daily_target, 2),
            "expected_daily_pnl": round(self.expected_daily_pnl, 2),
            "daily_sd": round(self.daily_sd, 2),
            "p_daily_target": round(self.p_daily_target, 4),
            "p_5day_target": round(self.p_5day_target, 4),
            "verdict": self.verdict,
            "is_weekend": self.is_weekend,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def summary(self) -> str:
        lines = [
            f"DAILY OUTLOOK — {self.verdict}",
            f"  Volume: {self.volume_band} (~{self.estimated_bets} bets{'  [weekend]' if self.is_weekend else ''})",
            f"  Bet size: ${self.max_loss_usd:.2f}/bet",
            f"  Expected: ${self.expected_daily_pnl:.2f}/day (SD: ${self.daily_sd:.2f})",
            f"  Target: ${self.daily_target:.2f}/day",
            f"  P(today >= target): {self.p_daily_target * 100:.1f}%",
            f"  P(5-day avg >= target): {self.p_5day_target * 100:.1f}%",
        ]
        return "\n".join(lines)


class DailyOutlook:
    """Predicts daily Kalshi P&L outlook from BTC range + bet sizing."""

    # Weighted average per-contract stats from 441 90-93c non-XRP trades
    # BTC: 0.967 WR, ETH: 0.963, SOL: 0.952 at avg 91.5c
    AVG_EV_PER_CONTRACT = 0.0465  # weighted avg EV in USD
    AVG_SD_PER_CONTRACT = 0.1927  # weighted avg SD in USD
    AVG_PRICE = 0.915

    def __init__(
        self,
        bankroll_usd: float = 190.0,
        max_loss_usd: float = 7.50,
        daily_target: float = 20.0,
    ):
        self.bankroll_usd = bankroll_usd
        self.max_loss_usd = max_loss_usd
        self.daily_target = daily_target

    def predict(
        self,
        btc_range_usd: float,
        is_weekend: bool = False,
        max_loss_usd: Optional[float] = None,
    ) -> OutlookResult:
        """Predict today's P&L outlook.

        Args:
            btc_range_usd: BTC 24h price range in USD
            is_weekend: Whether today is Saturday/Sunday
            max_loss_usd: Override bet size (uses instance default if None)
        """
        ml = max_loss_usd or self.max_loss_usd
        band = _classify_volume(btc_range_usd, is_weekend)
        bets = band.midpoint

        # Contracts per bet at avg price
        contracts = max(int(ml / self.AVG_PRICE), 1)

        ev_per_bet = contracts * self.AVG_EV_PER_CONTRACT
        sd_per_bet = contracts * self.AVG_SD_PER_CONTRACT

        daily_ev = bets * ev_per_bet
        daily_sd = math.sqrt(bets) * sd_per_bet if bets > 0 else 0

        # P(daily >= target)
        if daily_sd > 0:
            z = (self.daily_target - daily_ev) / daily_sd
            p_daily = 1 - _normal_cdf(z)
        else:
            p_daily = 1.0 if daily_ev >= self.daily_target else 0.0

        # P(5-day avg >= target)
        sd_5day = daily_sd / math.sqrt(5) if daily_sd > 0 else 0
        if sd_5day > 0:
            z5 = (self.daily_target - daily_ev) / sd_5day
            p_5day = 1 - _normal_cdf(z5)
        else:
            p_5day = 1.0 if daily_ev >= self.daily_target else 0.0

        # Verdict
        if p_daily >= 0.60:
            verdict = "LIKELY"
        elif p_daily >= 0.30:
            verdict = "POSSIBLE"
        else:
            verdict = "UNLIKELY"

        return OutlookResult(
            volume_band=band.label,
            estimated_bets=bets,
            max_loss_usd=ml,
            daily_target=self.daily_target,
            expected_daily_pnl=daily_ev,
            daily_sd=daily_sd,
            p_daily_target=p_daily,
            p_5day_target=p_5day,
            verdict=verdict,
            is_weekend=is_weekend,
        )

    def sweep_bet_sizes(
        self,
        btc_range_usd: float,
        sizes: Optional[List[float]] = None,
        is_weekend: bool = False,
    ) -> List[OutlookResult]:
        """Run outlook at multiple bet sizes."""
        if sizes is None:
            sizes = [5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
        return [
            self.predict(btc_range_usd, is_weekend=is_weekend, max_loss_usd=s)
            for s in sizes
        ]


def main():
    parser = argparse.ArgumentParser(description="Daily performance outlook predictor")
    parser.add_argument("--btc-range", type=float, required=True, help="BTC 24h range in USD")
    parser.add_argument("--max-loss", type=float, default=10.0, help="Max loss per bet in USD")
    parser.add_argument("--target", type=float, default=20.0, help="Daily target in USD")
    parser.add_argument("--bankroll", type=float, default=190.0, help="Bankroll in USD")
    parser.add_argument("--weekend", action="store_true", help="Apply weekend 0.7x multiplier")
    parser.add_argument("--sweep", action="store_true", help="Show analysis at multiple bet sizes")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    outlook = DailyOutlook(
        bankroll_usd=args.bankroll,
        max_loss_usd=args.max_loss,
        daily_target=args.target,
    )

    if args.sweep:
        results = outlook.sweep_bet_sizes(args.btc_range, is_weekend=args.weekend)
        if args.json:
            print(json.dumps([r.to_dict() for r in results], indent=2))
        else:
            print(f"DAILY OUTLOOK SWEEP — BTC range: ${args.btc_range:.0f}, Target: ${args.target:.2f}/day")
            print(f"{'Bet Size':>10} {'Bets':>6} {'Daily EV':>10} {'P(daily)':>10} {'P(5-day)':>10} {'Verdict':>10}")
            for r in results:
                print(
                    f"${r.max_loss_usd:>8.2f} {r.estimated_bets:>5} ${r.expected_daily_pnl:>8.2f} "
                    f"{r.p_daily_target * 100:>8.1f}% {r.p_5day_target * 100:>8.1f}% {r.verdict:>10}"
                )
    else:
        result = outlook.predict(args.btc_range, is_weekend=args.weekend)
        if args.json:
            print(result.to_json())
        else:
            print(result.summary())


if __name__ == "__main__":
    main()
