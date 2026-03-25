"""Maker sniper fill rate simulator (REQ-042).

Monte Carlo simulation of limit order fill rates for the maker_sniper strategy.
Models: spread distribution, price movement volatility, offset/expiry parameters.

Answers: given a maker order at (ask - offset_cents), what percentage fill within
expiry_seconds? How does fill rate change across parameter combinations?

Usage:
    from fill_rate_simulator import FillRateSimulator, SpreadModel

    sim = FillRateSimulator(SpreadModel.parametric(3.0, 1.0), price_vol_per_second=0.005)
    result = sim.simulate(base_price_cents=93, offset_cents=1, expiry_seconds=300,
                          min_spread_cents=2, n_simulations=5000)
    print(result.summary())

CLI:
    python3 fill_rate_simulator.py --price 93 --offset 1 --expiry 300 --sims 5000
    python3 fill_rate_simulator.py --sweep  # parameter sweep across offsets and expiries
    python3 fill_rate_simulator.py --from-db  # calibrate from polybot.db
"""
import argparse
import json
import math
import os
import random
import sqlite3
import statistics
from dataclasses import dataclass, field
from typing import Optional


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class MarketSnapshot:
    """A single orderbook snapshot for simulation."""

    ask_cents: int
    bid_cents: int
    price_cents: int  # mid or last trade price
    seconds_to_expiry: int

    @property
    def spread_cents(self) -> int:
        return self.ask_cents - self.bid_cents

    def maker_price(self, offset_cents: int) -> int:
        """Compute maker limit price, clamped to bid."""
        return max(self.ask_cents - offset_cents, self.bid_cents)

    def fill_possible(self, offset_cents: int, min_spread_cents: int) -> bool:
        """Check if spread is wide enough for a maker order."""
        return self.spread_cents >= min_spread_cents


@dataclass
class FillRateResult:
    """Result of a fill rate simulation run."""

    fill_rate: float
    n_simulations: int
    n_filled: int
    n_skipped_narrow_spread: int
    mean_time_to_fill: float
    median_time_to_fill: float
    effective_edge_cents: float
    offset_cents: int
    expiry_seconds: int
    base_price_cents: int

    def summary(self) -> str:
        lines = [
            f"Fill Rate: {self.fill_rate * 100:.1f}% ({self.n_filled}/{self.n_simulations})",
            f"Skipped (narrow spread): {self.n_skipped_narrow_spread}",
            f"Mean time to fill: {self.mean_time_to_fill:.1f}s",
            f"Median time to fill: {self.median_time_to_fill:.1f}s",
            f"Effective edge: {self.effective_edge_cents:.2f}c",
            f"Params: price={self.base_price_cents}c offset={self.offset_cents}c expiry={self.expiry_seconds}s",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "fill_rate": self.fill_rate,
            "n_simulations": self.n_simulations,
            "n_filled": self.n_filled,
            "n_skipped_narrow_spread": self.n_skipped_narrow_spread,
            "mean_time_to_fill": self.mean_time_to_fill,
            "median_time_to_fill": self.median_time_to_fill,
            "effective_edge_cents": self.effective_edge_cents,
            "offset_cents": self.offset_cents,
            "expiry_seconds": self.expiry_seconds,
            "base_price_cents": self.base_price_cents,
        }


# ── Spread model ─────────────────────────────────────────────────────────────


class SpreadModel:
    """Model of bid-ask spread distribution.

    Parametric: Gaussian with floor at 1c.
    Empirical: from observed spread data.
    """

    def __init__(self, mean_spread: float, std_spread: float):
        self.mean_spread = mean_spread
        self.std_spread = std_spread

    @classmethod
    def parametric(cls, mean_spread: float, std_spread: float) -> "SpreadModel":
        return cls(mean_spread=mean_spread, std_spread=std_spread)

    @classmethod
    def from_empirical(cls, spreads: list[int]) -> "SpreadModel":
        if not spreads:
            return cls(mean_spread=3.0, std_spread=1.0)
        mean = statistics.mean(spreads)
        std = statistics.stdev(spreads) if len(spreads) > 1 else 1.0
        return cls(mean_spread=mean, std_spread=std)

    def sample_spread(self) -> int:
        """Sample a spread value (integer cents, minimum 1)."""
        raw = random.gauss(self.mean_spread, self.std_spread)
        return max(1, round(raw))


# ── Fill rate simulator ──────────────────────────────────────────────────────


class FillRateSimulator:
    """Monte Carlo fill rate simulation for maker limit orders.

    Model: at each second within the expiry window, the ask price does a
    random walk. A fill occurs when the ask reaches or crosses the maker price.
    The walk uses price_vol_per_second as the standard deviation of per-second
    price changes (in cents).

    Args:
        spread_model: Model for sampling bid-ask spreads.
        price_vol_per_second: Std dev of per-second ask price movement in cents.
            Calibration: 15-min crypto binary at 90-94c typically sees 2-5c
            total movement, so ~0.015-0.03 per second (sqrt scaling).
    """

    def __init__(self, spread_model: SpreadModel, price_vol_per_second: float = 0.02):
        self.spread_model = spread_model
        self.price_vol_per_second = price_vol_per_second

    @classmethod
    def from_db(
        cls,
        db_path: str = "",
        strategy: str = "expiry_sniper_v1",
    ) -> "FillRateSimulator":
        """Calibrate simulator from polybot.db trade history.

        Uses expiry_sniper price distribution to estimate spread and volatility.
        """
        if not db_path:
            db_path = os.path.expanduser(
                "~/Projects/polymarket-bot/data/polybot.db"
            )
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"DB not found: {db_path}")

        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT price_cents FROM trades WHERE strategy = ? AND is_paper = 0 AND price_cents BETWEEN 85 AND 99",
                (strategy,),
            ).fetchall()
        finally:
            conn.close()

        prices = [r[0] for r in rows]

        if not prices:
            # No data — use conservative defaults
            return cls(
                spread_model=SpreadModel.parametric(3.0, 1.0),
                price_vol_per_second=0.02,
            )

        # Estimate spread from price distribution:
        # At 90-94c range, typical Kalshi 15-min spread is ~2-4c.
        # Use price variance as a proxy for spread + vol.
        mean_price = statistics.mean(prices)
        price_std = statistics.stdev(prices) if len(prices) > 1 else 2.0

        # Spread estimate: at 90-94c, spread is roughly 100 - mean_price scaled
        # Empirical: spread widens as price moves away from extremes
        estimated_spread = max(2.0, min(5.0, (100 - mean_price) * 0.3))
        spread_std = max(0.5, price_std * 0.3)

        # Vol estimate: price_std across trades gives session-level vol
        # Per-second vol = session_std / sqrt(avg_seconds_in_window)
        # 15-min window = 900s, trades span last ~14min = ~840s
        vol_per_second = max(0.005, price_std / math.sqrt(840))

        return cls(
            spread_model=SpreadModel.parametric(estimated_spread, spread_std),
            price_vol_per_second=vol_per_second,
        )

    def simulate(
        self,
        base_price_cents: int,
        offset_cents: int,
        expiry_seconds: int,
        min_spread_cents: int,
        n_simulations: int,
    ) -> FillRateResult:
        """Run Monte Carlo fill rate simulation.

        For each simulation:
        1. Sample a spread from the spread model
        2. Check if spread >= min_spread_cents (skip if not)
        3. Compute maker_price = ask - offset
        4. Random walk the ask price for expiry_seconds
        5. Record if/when price reaches maker_price (fill)

        Args:
            base_price_cents: Typical ask price (e.g., 93c)
            offset_cents: How far below ask to place the maker order
            expiry_seconds: How long the order stays open
            min_spread_cents: Minimum spread to place order
            n_simulations: Number of Monte Carlo runs
        """
        n_filled = 0
        n_skipped = 0
        fill_times: list[float] = []

        for _ in range(n_simulations):
            spread = self.spread_model.sample_spread()

            # Check spread threshold
            if spread < min_spread_cents:
                n_skipped += 1
                continue

            # Maker price
            ask = base_price_cents
            bid = ask - spread
            maker_price = max(ask - offset_cents, bid)

            # If offset is 0, fill is immediate
            if offset_cents == 0 or maker_price >= ask:
                n_filled += 1
                fill_times.append(0.0)
                continue

            # Random walk: simulate ask price movement
            # The ask can move up or down. Fill occurs when ask drops to maker_price.
            current_ask = float(ask)
            filled = False
            # Step in 5-second increments for speed
            step_size = 5
            vol_per_step = self.price_vol_per_second * math.sqrt(step_size)

            for t in range(0, expiry_seconds, step_size):
                # Random walk step
                current_ask += random.gauss(0, vol_per_step)

                # Fill check: if ask dropped to maker_price level
                if current_ask <= maker_price:
                    filled = True
                    n_filled += 1
                    fill_times.append(float(t + step_size))
                    break

            # Not filled within expiry — order expires

        eligible = n_simulations - n_skipped
        fill_rate = n_filled / eligible if eligible > 0 else 0.0

        mean_ttf = statistics.mean(fill_times) if fill_times else 0.0
        median_ttf = statistics.median(fill_times) if fill_times else 0.0
        effective_edge = offset_cents * fill_rate

        return FillRateResult(
            fill_rate=fill_rate,
            n_simulations=n_simulations,
            n_filled=n_filled,
            n_skipped_narrow_spread=n_skipped,
            mean_time_to_fill=mean_ttf,
            median_time_to_fill=median_ttf,
            effective_edge_cents=effective_edge,
            offset_cents=offset_cents,
            expiry_seconds=expiry_seconds,
            base_price_cents=base_price_cents,
        )


# ── Parameter sweep ──────────────────────────────────────────────────────────


class ParameterSweep:
    """Sweep across offset and expiry combinations."""

    def __init__(self, simulator: FillRateSimulator):
        self.simulator = simulator

    def run(
        self,
        base_price_cents: int,
        offsets: list[int],
        expiries: list[int],
        min_spread_cents: int,
        n_simulations: int,
    ) -> list[FillRateResult]:
        """Run simulation for all offset x expiry combinations."""
        results = []
        for offset in offsets:
            for expiry in expiries:
                result = self.simulator.simulate(
                    base_price_cents=base_price_cents,
                    offset_cents=offset,
                    expiry_seconds=expiry,
                    min_spread_cents=min_spread_cents,
                    n_simulations=n_simulations,
                )
                results.append(result)
        return results

    def to_table(self, results: list[FillRateResult]) -> str:
        """Format sweep results as an ASCII table."""
        lines = [
            f"{'Offset':>8} {'Expiry':>8} {'Fill Rate':>10} {'Filled':>8} {'Skipped':>8} {'Mean TTF':>10} {'Eff Edge':>10}",
            "-" * 72,
        ]
        for r in results:
            lines.append(
                f"{r.offset_cents:>7}c {r.expiry_seconds:>7}s {r.fill_rate * 100:>9.1f}% "
                f"{r.n_filled:>8} {r.n_skipped_narrow_spread:>8} "
                f"{r.mean_time_to_fill:>9.1f}s {r.effective_edge_cents:>9.2f}c"
            )
        return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Maker sniper fill rate simulator (REQ-042)")
    parser.add_argument("--price", type=int, default=93, help="Base ask price in cents")
    parser.add_argument("--offset", type=int, default=1, help="Offset below ask in cents")
    parser.add_argument("--expiry", type=int, default=300, help="Order expiry in seconds")
    parser.add_argument("--min-spread", type=int, default=2, help="Minimum spread to place order")
    parser.add_argument("--sims", type=int, default=5000, help="Number of simulations")
    parser.add_argument("--spread-mean", type=float, default=3.0, help="Mean spread in cents")
    parser.add_argument("--spread-std", type=float, default=1.0, help="Spread std dev")
    parser.add_argument("--vol", type=float, default=0.02, help="Price vol per second (cents)")
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep")
    parser.add_argument("--from-db", action="store_true", help="Calibrate from polybot.db")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if args.from_db:
        sim = FillRateSimulator.from_db()
        print(f"Calibrated from DB: spread={sim.spread_model.mean_spread:.1f}c +/- {sim.spread_model.std_spread:.1f}c, vol={sim.price_vol_per_second:.4f}c/s")
    else:
        spread = SpreadModel.parametric(args.spread_mean, args.spread_std)
        sim = FillRateSimulator(spread, args.vol)

    if args.sweep:
        sweep = ParameterSweep(sim)
        results = sweep.run(
            base_price_cents=args.price,
            offsets=[0, 1, 2, 3],
            expiries=[30, 60, 120, 300, 600],
            min_spread_cents=args.min_spread,
            n_simulations=args.sims,
        )
        if args.json:
            print(json.dumps([r.to_dict() for r in results], indent=2))
        else:
            print(sweep.to_table(results))
    else:
        result = sim.simulate(
            base_price_cents=args.price,
            offset_cents=args.offset,
            expiry_seconds=args.expiry,
            min_spread_cents=args.min_spread,
            n_simulations=args.sims,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())


if __name__ == "__main__":
    main()
