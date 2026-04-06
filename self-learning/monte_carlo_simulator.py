"""Monte Carlo bankroll simulator (REQ-040).

Simulates bankroll trajectories using parameterized or empirical bet distributions.
Answers: given current bankroll + daily bet volume + win rate distribution,
what is the probability of reaching a target vs ruin?

Usage:
    from monte_carlo_simulator import BetDistribution, MonteCarloSimulator

    dist = BetDistribution(win_rate=0.957, avg_win=0.90, avg_loss=-10.0, daily_volume=30)
    sim = MonteCarloSimulator(dist)
    result = sim.run(starting_bankroll=100.0, target_bankroll=125.0, n_days=60, n_simulations=10000)
    print(result.summary())

CLI:
    python3 monte_carlo_simulator.py --bankroll 100 --target 125 --days 60 --sims 10000
    python3 monte_carlo_simulator.py --from-db  # use actual polybot.db bet history
"""
from __future__ import annotations
import argparse
import json
import math
import os
import random
import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BetDistribution:
    """Parameterized bet outcome distribution.

    Can be created from explicit parameters or from historical outcome data.
    Supports both parametric sampling (Bernoulli win/loss) and empirical
    bootstrap sampling from actual outcome values.
    """

    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_bets: int = 0
    daily_volume: int = 30
    win_values: list = field(default_factory=list)
    loss_values: list = field(default_factory=list)

    @classmethod
    def from_outcomes(cls, outcomes: list[float], daily_volume: int = 30) -> "BetDistribution":
        """Create distribution from a list of P&L values."""
        if not outcomes:
            return cls(total_bets=0, daily_volume=daily_volume)

        wins = [o for o in outcomes if o > 0]
        losses = [o for o in outcomes if o <= 0]
        total = len(outcomes)
        win_rate = len(wins) / total if total > 0 else 0.0
        avg_win = statistics.mean(wins) if wins else 0.0
        avg_loss = statistics.mean(losses) if losses else 0.0

        return cls(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_bets=total,
            daily_volume=daily_volume,
            win_values=wins,
            loss_values=losses,
        )

    @classmethod
    def from_db(
        cls,
        db_path: str | None = None,
        strategy: str | None = None,
        daily_volume: int | None = None,
    ) -> "BetDistribution":
        """Create distribution from actual polybot.db trade history.

        Args:
            db_path: Path to polybot.db. Defaults to ~/Projects/polymarket-bot/data/polybot.db
            strategy: Filter to specific strategy (e.g. 'expiry_sniper_v1'). None = all live.
            daily_volume: Override daily volume. None = estimate from data.
        """
        if db_path is None:
            db_path = os.path.expanduser("~/Projects/polymarket-bot/data/polybot.db")

        if not os.path.exists(db_path):
            raise FileNotFoundError(f"DB not found: {db_path}")

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            # Get settled live trade P&L values
            query = """
                SELECT pnl_cents FROM trades
                WHERE is_paper = 0 AND result IS NOT NULL AND pnl_cents IS NOT NULL
            """
            params = []
            if strategy:
                query += " AND strategy = ?"
                params.append(strategy)

            rows = conn.execute(query, params).fetchall()
            if not rows:
                return cls(total_bets=0)

            outcomes = [r[0] / 100.0 for r in rows]  # cents to USD

            # Estimate daily volume from data if not provided
            if daily_volume is None:
                date_query = """
                    SELECT COUNT(*) as n, date(timestamp, 'unixepoch') as d
                    FROM trades
                    WHERE is_paper = 0 AND result IS NOT NULL
                """
                if strategy:
                    date_query += " AND strategy = ?"
                date_query += " GROUP BY d HAVING n > 0"
                day_rows = conn.execute(date_query, params).fetchall()
                if day_rows:
                    daily_counts = [r[0] for r in day_rows]
                    daily_volume = round(statistics.mean(daily_counts))
                else:
                    daily_volume = 30  # fallback

            # Get current bankroll
            bankroll_row = conn.execute(
                "SELECT balance_usd FROM bankroll_history WHERE source = 'api' ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            current_bankroll = bankroll_row[0] if bankroll_row else None

            dist = cls.from_outcomes(outcomes, daily_volume)
            dist._current_bankroll = current_bankroll
            return dist
        finally:
            conn.close()

    def with_loss_cap(self, max_loss_usd: float) -> "BetDistribution":
        """Return a new BetDistribution with losses capped at -max_loss_usd.

        Pre-sizing historical data includes large losses (e.g. -$19).
        With DEFAULT_MAX_LOSS=$7.50, those can't happen anymore.
        This method creates a distribution reflecting bounded losses.
        """
        cap = -abs(max_loss_usd)
        capped_losses = [max(v, cap) for v in self.loss_values]
        avg_loss = statistics.mean(capped_losses) if capped_losses else 0.0
        return BetDistribution(
            win_rate=self.win_rate,
            avg_win=self.avg_win,
            avg_loss=avg_loss,
            total_bets=self.total_bets,
            daily_volume=self.daily_volume,
            win_values=list(self.win_values),
            loss_values=capped_losses,
        )

    def expected_value(self) -> float:
        """Expected value of a single bet."""
        return self.win_rate * self.avg_win + (1 - self.win_rate) * self.avg_loss

    def variance(self) -> float:
        """Variance of a single bet outcome."""
        ev = self.expected_value()
        return (
            self.win_rate * (self.avg_win - ev) ** 2
            + (1 - self.win_rate) * (self.avg_loss - ev) ** 2
        )

    def sample(self) -> float:
        """Sample a single bet outcome (parametric Bernoulli)."""
        if random.random() < self.win_rate:
            return self.avg_win
        return self.avg_loss

    def sample_empirical(self) -> float:
        """Sample from empirical distribution (bootstrap from actual values)."""
        if not self.win_values and not self.loss_values:
            return self.sample()
        if random.random() < self.win_rate:
            return random.choice(self.win_values) if self.win_values else self.avg_win
        return random.choice(self.loss_values) if self.loss_values else self.avg_loss

    def kelly_fraction(self) -> float:
        """Full Kelly fraction: f* = p/q - q/(b/a) where p=WR, q=1-WR, b=avg_win, a=|avg_loss|."""
        if self.avg_loss == 0 or self.avg_win == 0:
            return 0.0
        p = self.win_rate
        q = 1 - p
        b = self.avg_win
        a = abs(self.avg_loss)
        kelly = p / a - q / b
        # Clamp to [0, 1] — negative means don't bet
        return max(0.0, min(1.0, kelly * a))  # Scale back to fraction of bankroll


@dataclass
class SimulationResult:
    """Results from a Monte Carlo simulation run."""

    n_simulations: int
    n_days: int
    starting_bankroll: float
    target_bankroll: float
    final_bankrolls: list[float]
    ruin_count: int
    target_count: int
    paths: list[list[float]] = field(default_factory=list)

    @property
    def ruin_probability(self) -> float:
        return self.ruin_count / self.n_simulations if self.n_simulations > 0 else 0.0

    @property
    def target_probability(self) -> float:
        return self.target_count / self.n_simulations if self.n_simulations > 0 else 0.0

    @property
    def median_bankroll(self) -> float:
        if not self.final_bankrolls:
            return 0.0
        return statistics.median(self.final_bankrolls)

    def percentiles(self, p: float) -> float:
        """Get percentile of final bankrolls (0-100)."""
        if not self.final_bankrolls:
            return 0.0
        sorted_b = sorted(self.final_bankrolls)
        idx = int(p / 100.0 * (len(sorted_b) - 1))
        return sorted_b[idx]

    def expected_daily_pnl(self) -> float:
        """Average daily P&L across all simulations."""
        if not self.final_bankrolls or self.n_days == 0:
            return 0.0
        avg_final = statistics.mean(self.final_bankrolls)
        return (avg_final - self.starting_bankroll) / self.n_days

    def to_dict(self) -> dict:
        return {
            "n_simulations": self.n_simulations,
            "n_days": self.n_days,
            "starting_bankroll": self.starting_bankroll,
            "target_bankroll": self.target_bankroll,
            "ruin_probability": round(self.ruin_probability, 4),
            "target_probability": round(self.target_probability, 4),
            "median_bankroll": round(self.median_bankroll, 2),
            "percentile_5": round(self.percentiles(5), 2),
            "percentile_25": round(self.percentiles(25), 2),
            "percentile_75": round(self.percentiles(75), 2),
            "percentile_95": round(self.percentiles(95), 2),
            "expected_daily_pnl": round(self.expected_daily_pnl(), 4),
            "mean_bankroll": round(statistics.mean(self.final_bankrolls), 2) if self.final_bankrolls else 0.0,
        }

    def summary(self) -> str:
        """Human-readable summary."""
        d = self.to_dict()
        lines = [
            f"Monte Carlo Simulation ({d['n_simulations']} paths, {d['n_days']} days)",
            f"  Start: ${d['starting_bankroll']:.2f} -> Target: ${d['target_bankroll']:.2f}",
            f"  Ruin probability:   {d['ruin_probability']:.1%}",
            f"  Target probability: {d['target_probability']:.1%}",
            f"  Median bankroll:    ${d['median_bankroll']:.2f}",
            f"  5th/95th pct:       ${d['percentile_5']:.2f} / ${d['percentile_95']:.2f}",
            f"  Expected daily P&L: ${d['expected_daily_pnl']:.4f}",
        ]
        return "\n".join(lines)


class MonteCarloSimulator:
    """Monte Carlo bankroll simulation engine."""

    def __init__(self, distribution: BetDistribution):
        self.distribution = distribution

    def simulate_path(
        self,
        starting_bankroll: float,
        n_days: int,
        ruin_threshold: float = 0.0,
        use_empirical: bool = False,
    ) -> list[float]:
        """Simulate a single bankroll trajectory.

        Returns list of bankroll values [day0, day1, ..., dayN].
        Stops early if bankroll hits ruin threshold.
        """
        path = [starting_bankroll]
        bankroll = starting_bankroll

        if bankroll <= ruin_threshold:
            return [0.0] * (n_days + 1)

        sample_fn = self.distribution.sample_empirical if use_empirical else self.distribution.sample

        for day in range(n_days):
            daily_pnl = 0.0
            for _ in range(self.distribution.daily_volume):
                daily_pnl += sample_fn()

            bankroll += daily_pnl
            if bankroll <= ruin_threshold:
                bankroll = 0.0
                path.append(0.0)
                # Fill remaining days with 0
                path.extend([0.0] * (n_days - day - 1))
                return path

            path.append(bankroll)

        return path

    def run(
        self,
        starting_bankroll: float,
        target_bankroll: float,
        n_days: int,
        n_simulations: int,
        seed: int | None = None,
        ruin_threshold: float = 0.0,
        use_empirical: bool = False,
        store_paths: bool = False,
    ) -> SimulationResult:
        """Run full Monte Carlo simulation.

        Args:
            starting_bankroll: Starting bankroll in USD
            target_bankroll: Target bankroll in USD
            n_days: Number of days to simulate
            n_simulations: Number of paths to simulate
            seed: Random seed for reproducibility
            ruin_threshold: Bankroll level considered ruin (default 0)
            use_empirical: Use bootstrap sampling instead of parametric
            store_paths: Store all paths (memory-intensive, for charting)
        """
        if seed is not None:
            random.seed(seed)

        final_bankrolls = []
        ruin_count = 0
        target_count = 0
        paths = []

        for _ in range(n_simulations):
            path = self.simulate_path(
                starting_bankroll, n_days, ruin_threshold, use_empirical
            )
            final = path[-1]
            final_bankrolls.append(final)

            if final <= ruin_threshold:
                ruin_count += 1
            if final >= target_bankroll:
                target_count += 1

            if store_paths:
                paths.append(path)

        return SimulationResult(
            n_simulations=n_simulations,
            n_days=n_days,
            starting_bankroll=starting_bankroll,
            target_bankroll=target_bankroll,
            final_bankrolls=final_bankrolls,
            ruin_count=ruin_count,
            target_count=target_count,
            paths=paths,
        )

    def scenario_analysis(
        self,
        starting_bankroll: float,
        target_bankroll: float,
        n_days_options: list[int],
        n_simulations: int = 1000,
        seed: int | None = None,
        **kwargs,
    ) -> list[SimulationResult]:
        """Run simulations across multiple time horizons."""
        results = []
        for n_days in n_days_options:
            result = self.run(
                starting_bankroll, target_bankroll, n_days, n_simulations,
                seed=seed, **kwargs,
            )
            results.append(result)
        return results

    def sensitivity_analysis(
        self,
        starting_bankroll: float,
        target_bankroll: float,
        n_days: int,
        n_simulations: int = 1000,
        win_rate_range: tuple[float, float] = (0.90, 0.98),
        steps: int = 5,
        seed: int | None = None,
    ) -> list[dict]:
        """Sweep win rate to see sensitivity of outcomes."""
        wr_low, wr_high = win_rate_range
        step_size = (wr_high - wr_low) / (steps - 1) if steps > 1 else 0
        results = []

        for i in range(steps):
            wr = wr_low + i * step_size
            dist = BetDistribution(
                win_rate=wr,
                avg_win=self.distribution.avg_win,
                avg_loss=self.distribution.avg_loss,
                daily_volume=self.distribution.daily_volume,
            )
            sim = MonteCarloSimulator(dist)
            result = sim.run(
                starting_bankroll, target_bankroll, n_days, n_simulations, seed=seed
            )
            results.append({
                "win_rate": round(wr, 4),
                "ruin_probability": round(result.ruin_probability, 4),
                "target_probability": round(result.target_probability, 4),
                "median_bankroll": round(result.median_bankroll, 2),
            })

        return results


class SyntheticBetGenerator:
    """Generate synthetic bets from historical patterns.

    Supports multi-strategy generation where each strategy maintains
    its own outcome distribution and volume proportion.
    """

    def __init__(self, strategies: dict[str, BetDistribution], daily_volume: int = 30):
        self.strategies = strategies
        self.daily_volume = daily_volume
        # Calculate volume proportions from total_bets
        total = sum(d.total_bets for d in strategies.values())
        if total > 0:
            self._proportions = {
                name: d.total_bets / total for name, d in strategies.items()
            }
        else:
            n = len(strategies)
            self._proportions = {name: 1.0 / n for name in strategies} if n > 0 else {}

    @classmethod
    def from_trade_data(
        cls, trade_data: list[dict], daily_volume: int = 30
    ) -> "SyntheticBetGenerator":
        """Create from list of trade dicts with 'pnl_usd' and 'strategy' keys."""
        by_strategy: dict[str, list[float]] = {}
        for t in trade_data:
            strat = t.get("strategy", "unknown")
            pnl = t.get("pnl_usd", 0.0)
            by_strategy.setdefault(strat, []).append(pnl)

        strategies = {}
        for name, outcomes in by_strategy.items():
            strategies[name] = BetDistribution.from_outcomes(outcomes)

        return cls(strategies, daily_volume)

    @classmethod
    def from_outcomes(
        cls, outcomes: list[float], daily_volume: int = 30
    ) -> "SyntheticBetGenerator":
        """Create from flat list of outcomes (single strategy bootstrap)."""
        dist = BetDistribution.from_outcomes(outcomes)
        return cls({"default": dist}, daily_volume)

    def generate_day(self) -> list[dict]:
        """Generate one day of synthetic bets."""
        bets = []
        for name, proportion in self._proportions.items():
            count = round(self.daily_volume * proportion)
            dist = self.strategies[name]
            for _ in range(count):
                pnl = dist.sample_empirical() if dist.win_values or dist.loss_values else dist.sample()
                bets.append({"pnl": pnl, "strategy": name})

        # Adjust to exact daily_volume (rounding may under/overshoot)
        while len(bets) < self.daily_volume:
            name = random.choice(list(self.strategies.keys()))
            dist = self.strategies[name]
            pnl = dist.sample_empirical() if dist.win_values or dist.loss_values else dist.sample()
            bets.append({"pnl": pnl, "strategy": name})
        while len(bets) > self.daily_volume:
            bets.pop()

        random.shuffle(bets)
        return bets

    def generate_sequence(self, n_days: int) -> list[list[dict]]:
        """Generate N days of synthetic bets."""
        return [self.generate_day() for _ in range(n_days)]


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Monte Carlo bankroll simulator")
    parser.add_argument("--bankroll", type=float, default=100.0, help="Starting bankroll (USD)")
    parser.add_argument("--target", type=float, default=125.0, help="Target bankroll (USD)")
    parser.add_argument("--days", type=int, default=60, help="Days to simulate")
    parser.add_argument("--sims", type=int, default=10000, help="Number of simulations")
    parser.add_argument("--wr", type=float, default=0.957, help="Win rate")
    parser.add_argument("--win", type=float, default=0.90, help="Average win (USD)")
    parser.add_argument("--loss", type=float, default=-10.0, help="Average loss (USD)")
    parser.add_argument("--volume", type=int, default=30, help="Daily bet volume")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--sensitivity", action="store_true", help="Run WR sensitivity analysis")
    parser.add_argument("--scenarios", action="store_true", help="Run 30/60/90 day scenarios")
    parser.add_argument("--from-db", action="store_true", help="Use actual polybot.db bet history")
    parser.add_argument("--db-path", type=str, default=None, help="Custom DB path (with --from-db)")
    parser.add_argument("--strategy", type=str, default=None, help="Filter to strategy (with --from-db)")

    args = parser.parse_args()

    if args.from_db:
        try:
            dist = BetDistribution.from_db(
                db_path=args.db_path,
                strategy=args.strategy,
                daily_volume=args.volume if args.volume != 30 else None,
            )
            bankroll = args.bankroll
            if hasattr(dist, '_current_bankroll') and dist._current_bankroll and bankroll == 100.0:
                bankroll = dist._current_bankroll
                print(f"Using DB bankroll: ${bankroll:.2f}")
            print(f"From DB: {dist.total_bets} bets, WR={dist.win_rate:.1%}, "
                  f"avg_win=${dist.avg_win:.2f}, avg_loss=${dist.avg_loss:.2f}, "
                  f"volume={dist.daily_volume}/day")
            args.bankroll = bankroll
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return
    else:
        dist = BetDistribution(
            win_rate=args.wr,
            avg_win=args.win,
            avg_loss=args.loss,
            daily_volume=args.volume,
        )
    sim = MonteCarloSimulator(dist)

    if args.sensitivity:
        results = sim.sensitivity_analysis(
            args.bankroll, args.target, args.days, args.sims, seed=args.seed
        )
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Sensitivity Analysis (WR sweep, {args.days} days, {args.sims} sims)")
            print(f"{'WR':>8} {'Ruin%':>8} {'Target%':>8} {'Median$':>10}")
            print("-" * 38)
            for r in results:
                print(f"{r['win_rate']:>8.1%} {r['ruin_probability']:>8.1%} "
                      f"{r['target_probability']:>8.1%} ${r['median_bankroll']:>9.2f}")
        return

    if args.scenarios:
        results = sim.scenario_analysis(
            args.bankroll, args.target, [30, 60, 90], args.sims, seed=args.seed
        )
        if args.json:
            print(json.dumps([r.to_dict() for r in results], indent=2))
        else:
            for r in results:
                print(r.summary())
                print()
        return

    result = sim.run(
        args.bankroll, args.target, args.days, args.sims, seed=args.seed
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.summary())
        print(f"\n  EV per bet:   ${dist.expected_value():.4f}")
        print(f"  Kelly fraction: {dist.kelly_fraction():.4f}")


if __name__ == "__main__":
    main()
