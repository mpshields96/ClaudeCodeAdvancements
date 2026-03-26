"""strategy_allocator.py — Multi-strategy capital allocation optimizer.

Given N trading strategies with known performance profiles, find the optimal
capital allocation that maximizes expected daily P&L while respecting
risk constraints (ruin probability, per-strategy caps).

Uses Kelly-criterion-inspired allocation: strategies with higher edge ratio
(EV / |avg_loss|) receive proportionally more capital. Negative-EV or
insufficient-data strategies receive zero.

Usage:
    from strategy_allocator import StrategyProfile, StrategyAllocator

    sniper = StrategyProfile("sniper", win_rate=0.933, avg_win=0.90,
                              avg_loss=-11.39, daily_volume=78, n_bets=100)
    sports = StrategyProfile("sports", win_rate=0.85, avg_win=1.20,
                              avg_loss=-5.0, daily_volume=20, n_bets=30)
    alloc = StrategyAllocator([sniper, sports])
    result = alloc.allocate(bankroll=178.05)
    print(result.summary())
"""
import math
from dataclasses import dataclass, field


@dataclass
class StrategyProfile:
    """Performance profile of a single trading strategy."""

    name: str
    win_rate: float
    avg_win: float
    avg_loss: float  # negative
    daily_volume: int
    n_bets: int
    is_paper: bool = False

    def expected_value(self) -> float:
        """Expected value of a single bet."""
        return self.win_rate * self.avg_win + (1 - self.win_rate) * self.avg_loss

    def daily_expected_pnl(self) -> float:
        """Expected daily P&L = EV * daily_volume."""
        return self.expected_value() * self.daily_volume

    def variance(self) -> float:
        """Variance of a single bet outcome."""
        ev = self.expected_value()
        return (
            self.win_rate * (self.avg_win - ev) ** 2
            + (1 - self.win_rate) * (self.avg_loss - ev) ** 2
        )

    def edge_ratio(self) -> float:
        """Edge ratio = EV / |avg_loss|. Higher = more efficient per dollar risked."""
        if self.avg_loss == 0:
            return 0.0
        return self.expected_value() / abs(self.avg_loss)

    def kelly_fraction(self) -> float:
        """Kelly fraction: f* = p/a - q/b where p=WR, a=|avg_loss|, b=avg_win."""
        if self.avg_loss == 0 or self.avg_win == 0:
            return 0.0
        p = self.win_rate
        q = 1 - p
        b = self.avg_win
        a = abs(self.avg_loss)
        f = p / a - q / b
        return max(0.0, f)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "win_rate": round(self.win_rate, 4),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "daily_volume": self.daily_volume,
            "n_bets": self.n_bets,
            "is_paper": self.is_paper,
            "expected_value": round(self.expected_value(), 4),
            "daily_expected_pnl": round(self.daily_expected_pnl(), 2),
            "edge_ratio": round(self.edge_ratio(), 4),
            "kelly_fraction": round(self.kelly_fraction(), 4),
            "variance": round(self.variance(), 4),
        }


@dataclass
class AllocationConstraints:
    """Constraints on the allocation optimizer."""

    max_ruin_probability: float = 0.05
    min_allocation: float = 0.0  # minimum per-strategy allocation
    max_allocation: float = 1.0  # maximum per-strategy allocation
    require_min_bets: int = 0  # minimum historical bets to be eligible

    def to_dict(self) -> dict:
        return {
            "max_ruin_probability": self.max_ruin_probability,
            "min_allocation": self.min_allocation,
            "max_allocation": self.max_allocation,
            "require_min_bets": self.require_min_bets,
        }


@dataclass
class AllocationResult:
    """Result of the allocation optimization."""

    allocations: dict[str, float]  # strategy_name -> fraction [0, 1]
    expected_daily_pnl: float
    combined_ruin_probability: float
    strategy_contributions: dict[str, float]  # strategy_name -> daily P&L contribution

    def summary(self) -> str:
        lines = ["Strategy Allocation:"]
        for name, frac in sorted(self.allocations.items(), key=lambda x: -x[1]):
            contrib = self.strategy_contributions.get(name, 0.0)
            lines.append(f"  {name}: {frac:.1%} (${contrib:.2f}/day)")
        lines.append(f"  Total expected daily P&L: ${self.expected_daily_pnl:.2f}")
        lines.append(f"  Combined ruin probability: {self.combined_ruin_probability:.2%}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "allocations": {k: round(v, 4) for k, v in self.allocations.items()},
            "expected_daily_pnl": round(self.expected_daily_pnl, 2),
            "combined_ruin_probability": round(self.combined_ruin_probability, 4),
            "strategy_contributions": {
                k: round(v, 2) for k, v in self.strategy_contributions.items()
            },
        }


class StrategyAllocator:
    """Multi-strategy capital allocation optimizer.

    Uses Kelly-criterion-inspired proportional allocation:
    1. Filter out negative-EV and insufficient-data strategies
    2. Compute Kelly fraction for each eligible strategy
    3. Normalize to sum to 1.0 (with half-Kelly for safety)
    4. Apply constraints (max per-strategy, min bets)
    """

    def __init__(self, strategies: list[StrategyProfile]):
        self.strategies = strategies

    def _filter_eligible(
        self, constraints: AllocationConstraints | None = None
    ) -> list[StrategyProfile]:
        """Filter to strategies eligible for capital allocation."""
        eligible = []
        min_bets = constraints.require_min_bets if constraints else 0

        for s in self.strategies:
            # Skip negative EV
            if s.expected_value() <= 0:
                continue
            # Skip paper mode if min bets required
            if s.is_paper and min_bets > 0:
                continue
            # Skip insufficient data
            if s.n_bets < min_bets:
                continue
            eligible.append(s)

        return eligible

    def allocate(
        self,
        bankroll: float = 178.05,
        constraints: AllocationConstraints | None = None,
    ) -> AllocationResult:
        """Find optimal allocation across strategies.

        Algorithm:
        1. Filter eligible strategies (positive EV, sufficient data)
        2. Compute half-Kelly fraction for each
        3. Normalize proportions to sum to 1.0
        4. Apply max_allocation cap and redistribute excess
        5. Compute expected daily P&L and ruin estimate
        """
        if constraints is None:
            constraints = AllocationConstraints()

        eligible = self._filter_eligible(constraints)

        if not eligible:
            # No eligible strategies — all to the single best one or empty
            allocations = {s.name: 0.0 for s in self.strategies}
            return AllocationResult(
                allocations=allocations,
                expected_daily_pnl=0.0,
                combined_ruin_probability=1.0,
                strategy_contributions={s.name: 0.0 for s in self.strategies},
            )

        # Compute Kelly fractions (half-Kelly for safety)
        kelly_fracs = {}
        for s in eligible:
            kf = s.kelly_fraction() * 0.5  # half-Kelly
            kelly_fracs[s.name] = max(kf, 0.001)  # small floor for diversification

        # Normalize to sum to 1.0
        total_kelly = sum(kelly_fracs.values())
        if total_kelly == 0:
            # Equal weight fallback
            n = len(eligible)
            raw_alloc = {s.name: 1.0 / n for s in eligible}
        else:
            raw_alloc = {name: kf / total_kelly for name, kf in kelly_fracs.items()}

        # Apply max_allocation cap
        capped = {}
        excess = 0.0
        uncapped_names = []

        for name, frac in raw_alloc.items():
            if frac > constraints.max_allocation:
                capped[name] = constraints.max_allocation
                excess += frac - constraints.max_allocation
            else:
                capped[name] = frac
                uncapped_names.append(name)

        # Redistribute excess to uncapped strategies
        if excess > 0 and uncapped_names:
            uncapped_total = sum(capped[n] for n in uncapped_names)
            if uncapped_total > 0:
                for name in uncapped_names:
                    share = capped[name] / uncapped_total
                    capped[name] += excess * share
                    capped[name] = min(capped[name], constraints.max_allocation)

        # Renormalize
        total = sum(capped.values())
        if total > 0:
            allocations = {name: frac / total for name, frac in capped.items()}
        else:
            allocations = capped

        # Add zero allocation for excluded strategies
        for s in self.strategies:
            if s.name not in allocations:
                allocations[s.name] = 0.0

        # Compute contributions and combined metrics
        contributions = {}
        total_daily = 0.0
        for s in self.strategies:
            frac = allocations.get(s.name, 0.0)
            # P&L contribution is proportional to allocation (affects volume, not EV per bet)
            daily = s.daily_expected_pnl() * frac
            contributions[s.name] = daily
            total_daily += daily

        # Rough ruin estimate: weighted average of per-strategy ruin approximations
        # Using Gambler's ruin approximation: P(ruin) ≈ (q/p)^(B/avg_loss)
        combined_ruin = self._estimate_combined_ruin(
            eligible, allocations, bankroll
        )

        return AllocationResult(
            allocations=allocations,
            expected_daily_pnl=total_daily,
            combined_ruin_probability=combined_ruin,
            strategy_contributions=contributions,
        )

    def _estimate_combined_ruin(
        self,
        eligible: list[StrategyProfile],
        allocations: dict[str, float],
        bankroll: float,
    ) -> float:
        """Rough ruin probability estimate using exponential approximation.

        For each strategy: P(ruin) ≈ exp(-2 * EV * B_alloc / var)
        Combined: product of survival probabilities.
        """
        survival = 1.0
        for s in eligible:
            frac = allocations.get(s.name, 0.0)
            if frac <= 0:
                continue
            alloc_bankroll = bankroll * frac
            ev = s.expected_value()
            var = s.variance()
            if var <= 0 or ev <= 0:
                continue
            # Exponential ruin bound: P(ruin) ≈ exp(-2 * EV * B / Var)
            daily_ev = ev * s.daily_volume
            daily_var = var * s.daily_volume
            if daily_var > 0:
                ruin_est = math.exp(-2 * daily_ev * alloc_bankroll / daily_var)
                ruin_est = min(ruin_est, 1.0)
                survival *= (1 - ruin_est)

        return 1 - survival

    def scenario_analysis(
        self,
        bankrolls: list[float] | None = None,
        constraints: AllocationConstraints | None = None,
    ) -> list[dict]:
        """Run allocation at multiple bankroll levels."""
        if bankrolls is None:
            bankrolls = [100.0, 178.05, 250.0, 500.0, 1000.0]

        scenarios = []
        for b in bankrolls:
            result = self.allocate(bankroll=b, constraints=constraints)
            scenarios.append({
                "bankroll": b,
                "allocation": result.to_dict(),
                "expected_daily_pnl": result.expected_daily_pnl,
                "monthly_pnl": round(result.expected_daily_pnl * 30, 2),
            })
        return scenarios

    def full_report(
        self,
        bankroll: float = 178.05,
        constraints: AllocationConstraints | None = None,
    ) -> dict:
        """Generate complete allocation analysis report."""
        result = self.allocate(bankroll=bankroll, constraints=constraints)
        scenarios = self.scenario_analysis(constraints=constraints)

        return {
            "optimal_allocation": result.to_dict(),
            "strategy_profiles": [s.to_dict() for s in self.strategies],
            "scenarios": scenarios,
            "bankroll": bankroll,
            "self_sustaining_daily": round(250.0 / 30.0, 2),
            "current_vs_target": {
                "current_daily": round(result.expected_daily_pnl, 2),
                "target_daily": round(250.0 / 30.0, 2),
                "gap_pct": round(
                    (1 - result.expected_daily_pnl / (250.0 / 30.0)) * 100, 1
                )
                if result.expected_daily_pnl < 250.0 / 30.0
                else 0.0,
            },
        }
