#!/usr/bin/env python3
"""
sizing_optimizer.py — Portfolio-level bet sizing optimizer.

Given trade data across multiple assets (win rate, avg price, n_bets) and a
bankroll, computes optimal per-asset max_loss sizing to hit a daily P&L target.

Uses Kelly criterion math (Thorp 2006, MacLean et al 2011) to find the sweet
spot between conservative (current 1/16 Kelly) and aggressive (full Kelly).

Features:
1. Per-asset Kelly fraction computation
2. Daily EV/SD projection at any bet size
3. P(daily >= target) and P(5-day avg >= target) normal approximation
4. Optimal max_loss finder for a given daily target
5. Asset-weighted sizing (proportional to Kelly fraction)
6. Full JSON report generation + CLI

Usage:
    from sizing_optimizer import AssetProfile, SizingOptimizer

    profiles = [
        AssetProfile("KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915),
        AssetProfile("KXETH", n_bets=134, win_rate=0.963, avg_price=0.915),
    ]
    opt = SizingOptimizer(profiles, bankroll_usd=190.0, bets_per_day=31.5)
    report = opt.generate_report(daily_target=15.0)
    print(report.summary())

CLI:
    python3 sizing_optimizer.py --bankroll 190 --target 15
    python3 sizing_optimizer.py --bankroll 190 --target 15 --json
    python3 sizing_optimizer.py --bankroll 190 --target 15 --assets KXBTC:181:0.967:0.915

Zero external dependencies. Stdlib only.
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AssetProfile:
    """Trade profile for a single asset."""

    ticker: str
    n_bets: int
    win_rate: float
    avg_price: float  # e.g. 0.915 for 91.5c

    @property
    def net_odds(self) -> float:
        """Win/loss ratio per contract: b = (1-p)/p."""
        return (1 - self.avg_price) / self.avg_price

    @property
    def kelly_fraction(self) -> float:
        """Full Kelly fraction: f* = (W*b - L) / b."""
        b = self.net_odds
        q = 1 - self.win_rate
        return (self.win_rate * b - q) / b

    @property
    def ev_per_contract(self) -> float:
        """Expected value per contract in dollars."""
        return self.win_rate * (1 - self.avg_price) - (1 - self.win_rate) * self.avg_price

    @property
    def sd_per_contract(self) -> float:
        """Standard deviation per contract in dollars."""
        ev = self.ev_per_contract
        win_amt = 1 - self.avg_price
        loss_amt = -self.avg_price
        var = (
            self.win_rate * (win_amt - ev) ** 2
            + (1 - self.win_rate) * (loss_amt - ev) ** 2
        )
        return math.sqrt(var)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "n_bets": self.n_bets,
            "win_rate": round(self.win_rate, 4),
            "avg_price": round(self.avg_price, 4),
            "net_odds": round(self.net_odds, 4),
            "kelly_fraction": round(self.kelly_fraction, 4),
            "ev_per_contract": round(self.ev_per_contract, 4),
            "sd_per_contract": round(self.sd_per_contract, 4),
        }


@dataclass
class DailyProjection:
    """Daily P&L projection at a given bet size."""

    max_loss_usd: float
    contracts_per_bet: int
    daily_ev: float
    daily_sd: float
    p_daily_target: float
    p_5day_target: float
    kelly_multiple: float
    bankroll_usd: float

    @property
    def worst_3loss_day(self) -> float:
        """Dollar loss on a 3-loss day."""
        return self.max_loss_usd * 3

    @property
    def worst_3loss_pct(self) -> float:
        """3-loss day as percentage of bankroll."""
        if self.bankroll_usd <= 0:
            return 0.0
        return self.worst_3loss_day / self.bankroll_usd * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_loss_usd": round(self.max_loss_usd, 2),
            "contracts_per_bet": self.contracts_per_bet,
            "daily_ev": round(self.daily_ev, 2),
            "daily_sd": round(self.daily_sd, 2),
            "p_daily_target": round(self.p_daily_target, 4),
            "p_5day_target": round(self.p_5day_target, 4),
            "kelly_multiple": round(self.kelly_multiple, 4),
            "worst_3loss_day": round(self.worst_3loss_day, 2),
            "worst_3loss_pct": round(self.worst_3loss_pct, 1),
        }


@dataclass
class VarianceAnalysis:
    """Variance analysis across a range of bet sizes."""

    projections: List[DailyProjection]

    def to_dict(self) -> Dict[str, Any]:
        return {"projections": [p.to_dict() for p in self.projections]}


@dataclass
class SizingReport:
    """Full sizing optimization report."""

    asset_profiles: List[AssetProfile]
    variance_analysis: VarianceAnalysis
    recommended_max_loss: float
    recommended_per_asset: Dict[str, float]
    daily_target: float
    bankroll_usd: float
    bets_per_day: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_profiles": [p.to_dict() for p in self.asset_profiles],
            "variance_analysis": self.variance_analysis.to_dict(),
            "recommended_max_loss": round(self.recommended_max_loss, 2),
            "recommended_per_asset": {
                k: round(v, 2) for k, v in self.recommended_per_asset.items()
            },
            "daily_target": self.daily_target,
            "bankroll_usd": self.bankroll_usd,
            "bets_per_day": self.bets_per_day,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def summary(self) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("SIZING OPTIMIZER REPORT")
        lines.append(f"Bankroll: ${self.bankroll_usd:.2f} | Target: ${self.daily_target:.2f}/day | Bets/day: {self.bets_per_day:.1f}")
        lines.append("=" * 60)

        lines.append("\nASSET PROFILES:")
        for ap in self.asset_profiles:
            lines.append(
                f"  {ap.ticker}: WR={ap.win_rate*100:.1f}%, Kelly={ap.kelly_fraction*100:.1f}%, "
                f"EV/contract=${ap.ev_per_contract:.4f}"
            )

        lines.append("\nVARIANCE ANALYSIS:")
        lines.append(f"  {'Max Loss':>10} {'Daily EV':>10} {'Daily SD':>10} {'P(5d>=tgt)':>12} {'3-Loss Day':>12}")
        for p in self.variance_analysis.projections:
            lines.append(
                f"  ${p.max_loss_usd:>8.2f} ${p.daily_ev:>8.2f} ${p.daily_sd:>8.2f} "
                f"{p.p_5day_target*100:>10.1f}% ${p.worst_3loss_day:>9.2f}"
            )

        lines.append(f"\nRECOMMENDED: Uniform max_loss = ${self.recommended_max_loss:.2f}")
        if self.recommended_per_asset:
            lines.append("RECOMMENDED per-asset:")
            for ticker, size in sorted(self.recommended_per_asset.items()):
                lines.append(f"  {ticker}: ${size:.2f}")

        return "\n".join(lines)


def _normal_cdf(x: float) -> float:
    """Standard normal CDF using erf."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


class SizingOptimizer:
    """Portfolio-level bet sizing optimizer."""

    # Default assets matching current Kalshi sniper config
    DEFAULT_PROFILES = [
        AssetProfile(ticker="KXBTC", n_bets=181, win_rate=0.967, avg_price=0.915),
        AssetProfile(ticker="KXETH", n_bets=134, win_rate=0.963, avg_price=0.915),
        AssetProfile(ticker="KXSOL", n_bets=126, win_rate=0.952, avg_price=0.915),
    ]

    def __init__(
        self,
        profiles: Optional[List[AssetProfile]] = None,
        bankroll_usd: float = 190.0,
        bets_per_day: float = 31.5,
    ):
        if bankroll_usd <= 0:
            raise ValueError(f"bankroll_usd must be > 0, got {bankroll_usd}")
        if bets_per_day <= 0:
            raise ValueError(f"bets_per_day must be > 0, got {bets_per_day}")

        self.profiles = profiles or self.DEFAULT_PROFILES
        self.bankroll_usd = bankroll_usd
        self.bets_per_day = bets_per_day

    def _weighted_ev_sd(self) -> tuple:
        """Compute bet-count-weighted average EV and SD per contract."""
        total_n = sum(p.n_bets for p in self.profiles)
        if total_n == 0:
            return 0.0, 0.0

        avg_ev = sum(p.ev_per_contract * p.n_bets for p in self.profiles) / total_n
        avg_sd = sum(p.sd_per_contract * p.n_bets for p in self.profiles) / total_n
        return avg_ev, avg_sd

    def _weighted_kelly(self) -> float:
        """Bet-count-weighted average Kelly fraction."""
        total_n = sum(p.n_bets for p in self.profiles)
        if total_n == 0:
            return 0.0
        return sum(p.kelly_fraction * p.n_bets for p in self.profiles) / total_n

    def _avg_price(self) -> float:
        """Bet-count-weighted average price."""
        total_n = sum(p.n_bets for p in self.profiles)
        if total_n == 0:
            return 0.90
        return sum(p.avg_price * p.n_bets for p in self.profiles) / total_n

    def compute_daily_projection(
        self,
        max_loss_usd: float,
        daily_target: float = 15.0,
    ) -> DailyProjection:
        """Compute daily EV, SD, and target probabilities for a given max_loss."""
        avg_price = self._avg_price()
        contracts = int(max_loss_usd / avg_price) if avg_price > 0 else 0
        contracts = max(contracts, 1)

        avg_ev, avg_sd = self._weighted_ev_sd()
        ev_per_bet = contracts * avg_ev
        sd_per_bet = contracts * avg_sd

        daily_ev = self.bets_per_day * ev_per_bet
        daily_sd = math.sqrt(self.bets_per_day) * sd_per_bet if sd_per_bet > 0 else 0

        # P(daily >= target)
        if daily_sd > 0:
            z_daily = (daily_target - daily_ev) / daily_sd
            p_daily = 1 - _normal_cdf(z_daily)
        else:
            p_daily = 1.0 if daily_ev >= daily_target else 0.0

        # P(5-day avg >= target)
        avg_5day_sd = daily_sd / math.sqrt(5) if daily_sd > 0 else 0
        if avg_5day_sd > 0:
            z_5day = (daily_target - daily_ev) / avg_5day_sd
            p_5day = 1 - _normal_cdf(z_5day)
        else:
            p_5day = 1.0 if daily_ev >= daily_target else 0.0

        # Kelly multiple
        avg_kelly = self._weighted_kelly()
        kelly_bet = avg_kelly * self.bankroll_usd if avg_kelly > 0 else 1.0
        kelly_multiple = max_loss_usd / kelly_bet if kelly_bet > 0 else 0.0

        return DailyProjection(
            max_loss_usd=max_loss_usd,
            contracts_per_bet=contracts,
            daily_ev=daily_ev,
            daily_sd=daily_sd,
            p_daily_target=p_daily,
            p_5day_target=p_5day,
            kelly_multiple=kelly_multiple,
            bankroll_usd=self.bankroll_usd,
        )

    def variance_analysis(
        self,
        max_loss_range: Optional[List[float]] = None,
        daily_target: float = 15.0,
    ) -> VarianceAnalysis:
        """Run projections across a range of bet sizes."""
        if max_loss_range is None:
            max_loss_range = [5.0, 7.5, 10.0, 12.5, 15.0, 20.0]

        projections = [
            self.compute_daily_projection(ml, daily_target=daily_target)
            for ml in max_loss_range
        ]
        return VarianceAnalysis(projections=projections)

    def asset_weighted_sizing(self, total_budget_usd: float) -> Dict[str, float]:
        """Scale per-bet max_loss per asset proportional to Kelly fraction.

        Assets with higher Kelly fraction get larger per-bet sizing.
        The weighted average across assets equals total_budget_usd.
        """
        kellys = {p.ticker: max(p.kelly_fraction, 0.01) for p in self.profiles}
        weights = {p.ticker: p.n_bets for p in self.profiles}
        total_n = sum(weights.values())
        if total_n == 0:
            return {p.ticker: total_budget_usd for p in self.profiles}

        # Weighted average Kelly
        avg_kelly = sum(kellys[t] * weights[t] for t in kellys) / total_n
        if avg_kelly <= 0:
            return {p.ticker: total_budget_usd for p in self.profiles}

        # Scale each asset's max_loss by its Kelly ratio to the average
        return {
            ticker: round(total_budget_usd * k / avg_kelly, 2)
            for ticker, k in kellys.items()
        }

    def optimal_max_loss(
        self,
        daily_target: float = 15.0,
        p_threshold: float = 0.50,
        max_allowed: float = 50.0,
        step: float = 0.50,
    ) -> float:
        """Find minimum max_loss where P(5-day avg >= target) >= p_threshold."""
        current = step
        while current <= max_allowed:
            proj = self.compute_daily_projection(current, daily_target=daily_target)
            if proj.p_5day_target >= p_threshold:
                return round(current, 2)
            current += step
        return max_allowed

    def generate_report(self, daily_target: float = 15.0) -> SizingReport:
        """Generate full sizing optimization report."""
        va = self.variance_analysis(daily_target=daily_target)
        opt_loss = self.optimal_max_loss(daily_target=daily_target)
        per_asset = self.asset_weighted_sizing(opt_loss)

        return SizingReport(
            asset_profiles=self.profiles,
            variance_analysis=va,
            recommended_max_loss=opt_loss,
            recommended_per_asset=per_asset,
            daily_target=daily_target,
            bankroll_usd=self.bankroll_usd,
            bets_per_day=self.bets_per_day,
        )


def _parse_asset(s: str) -> AssetProfile:
    """Parse asset string: TICKER:N:WR:PRICE."""
    parts = s.split(":")
    if len(parts) != 4:
        raise ValueError(f"Asset format must be TICKER:N:WR:PRICE, got: {s}")
    return AssetProfile(
        ticker=parts[0],
        n_bets=int(parts[1]),
        win_rate=float(parts[2]),
        avg_price=float(parts[3]),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Portfolio-level bet sizing optimizer"
    )
    parser.add_argument("--bankroll", type=float, default=190.0, help="Bankroll in USD")
    parser.add_argument("--target", type=float, default=15.0, help="Daily target in USD")
    parser.add_argument("--bets-per-day", type=float, default=31.5, help="Expected bets per day")
    parser.add_argument("--assets", nargs="+", help="Assets as TICKER:N:WR:PRICE")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    profiles = None
    if args.assets:
        profiles = [_parse_asset(a) for a in args.assets]

    opt = SizingOptimizer(
        profiles=profiles,
        bankroll_usd=args.bankroll,
        bets_per_day=args.bets_per_day,
    )
    report = opt.generate_report(daily_target=args.target)

    if args.json:
        print(report.to_json())
    else:
        print(report.summary())


if __name__ == "__main__":
    main()
