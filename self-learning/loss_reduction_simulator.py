"""Loss reduction simulator (REQ-057).

Models the impact of reducing average loss magnitude on ruin probability,
daily P&L, and target achievement. Answers key questions:
1. If avg_loss drops from -11.39 to -8.00, how does ruin probability change?
2. Which loss reduction strategies have the best risk/reward tradeoff?
3. At what avg_loss level does the bot become self-sustaining ($250/month)?

Uses MonteCarloSimulator as the simulation engine.

Usage:
    from loss_reduction_simulator import LossReductionSimulator
    from monte_carlo_simulator import BetDistribution

    dist = BetDistribution(win_rate=0.933, avg_win=0.90, avg_loss=-11.39,
                           daily_volume=78, total_bets=100)
    sim = LossReductionSimulator(dist)
    report = sim.full_report(bankroll=178.05, target=250.0, n_days=60, n_sims=10000)
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field

from monte_carlo_simulator import BetDistribution, MonteCarloSimulator


@dataclass
class LossReductionStrategy:
    """A specific strategy for reducing average loss magnitude.

    Each strategy may have side effects: WR change, volume change, avg_win change.
    """

    name: str
    description: str
    target_avg_loss: float  # new avg_loss if strategy is applied
    wr_impact: float = 0.0  # additive change to win rate (e.g. -0.005)
    volume_impact: float = 0.0  # fractional change to daily volume (e.g. -0.15 = 15% fewer)
    avg_win_impact: float = 0.0  # fractional change to avg_win (e.g. -0.10 = 10% smaller wins)


@dataclass
class SweepPoint:
    """One data point in an avg_loss sweep."""

    avg_loss: float
    win_rate: float
    ruin_probability: float
    target_probability: float
    expected_daily_pnl: float
    median_bankroll: float

    def to_dict(self) -> dict:
        return {
            "avg_loss": round(self.avg_loss, 2),
            "win_rate": round(self.win_rate, 4),
            "ruin_probability": round(self.ruin_probability, 4),
            "target_probability": round(self.target_probability, 4),
            "expected_daily_pnl": round(self.expected_daily_pnl, 4),
            "median_bankroll": round(self.median_bankroll, 2),
        }


@dataclass
class LossReductionSweep:
    """Results from sweeping avg_loss across a range."""

    baseline_avg_loss: float
    baseline_ruin: float
    points: list[SweepPoint]

    def find_ruin_threshold(self, max_ruin: float) -> SweepPoint | None:
        """Find the first point where ruin drops below max_ruin."""
        for p in self.points:
            if p.ruin_probability <= max_ruin:
                return p
        return None

    def summary(self) -> str:
        lines = [
            f"Loss Reduction Sweep (baseline avg_loss: ${self.baseline_avg_loss:.2f},"
            f" baseline ruin: {self.baseline_ruin:.1%})",
            f"{'avg_loss':>10} {'WR':>8} {'ruin':>8} {'target':>8} {'daily_pnl':>10} {'median':>10}",
            "-" * 60,
        ]
        for p in self.points:
            lines.append(
                f"${p.avg_loss:>8.2f} {p.win_rate:>8.1%} {p.ruin_probability:>8.1%}"
                f" {p.target_probability:>8.1%} ${p.expected_daily_pnl:>9.2f}"
                f" ${p.median_bankroll:>9.2f}"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "baseline_avg_loss": round(self.baseline_avg_loss, 2),
            "baseline_ruin": round(self.baseline_ruin, 4),
            "points": [p.to_dict() for p in self.points],
        }


@dataclass
class StrategyImpact:
    """Impact assessment of a specific loss reduction strategy."""

    strategy_name: str
    original_ruin: float
    new_ruin: float
    original_daily_pnl: float
    new_daily_pnl: float
    original_avg_loss: float
    new_avg_loss: float
    ruin_reduction: float  # original_ruin - new_ruin
    pnl_improvement: float  # new_daily_pnl - original_daily_pnl

    def summary(self) -> str:
        lines = [
            f"Strategy: {self.strategy_name}",
            f"  avg_loss: ${self.original_avg_loss:.2f} -> ${self.new_avg_loss:.2f}",
            f"  ruin:     {self.original_ruin:.1%} -> {self.new_ruin:.1%}"
            f"  (reduction: {self.ruin_reduction:.1%})",
            f"  daily PnL: ${self.original_daily_pnl:.2f} -> ${self.new_daily_pnl:.2f}"
            f"  (improvement: ${self.pnl_improvement:.2f})",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "strategy_name": self.strategy_name,
            "original_ruin": round(self.original_ruin, 4),
            "new_ruin": round(self.new_ruin, 4),
            "original_daily_pnl": round(self.original_daily_pnl, 4),
            "new_daily_pnl": round(self.new_daily_pnl, 4),
            "original_avg_loss": round(self.original_avg_loss, 2),
            "new_avg_loss": round(self.new_avg_loss, 2),
            "ruin_reduction": round(self.ruin_reduction, 4),
            "pnl_improvement": round(self.pnl_improvement, 4),
        }


class LossReductionSimulator:
    """Simulates impact of reducing average loss on bankroll outcomes."""

    # Default strategies to evaluate (based on REQ-57 analysis)
    DEFAULT_STRATEGIES = [
        LossReductionStrategy(
            name="early_exit_8c",
            description="Exit position when it moves 8c against us (cap loss at ~$8)",
            target_avg_loss=-8.0,
            wr_impact=-0.005,  # slight WR decrease: some early exits would have recovered
        ),
        LossReductionStrategy(
            name="early_exit_6c",
            description="Exit position when it moves 6c against us (cap loss at ~$6)",
            target_avg_loss=-6.0,
            wr_impact=-0.015,  # more aggressive exit = more false exits
        ),
        LossReductionStrategy(
            name="tighter_price_floors",
            description="Only enter at 93c+ (currently 90c+), reducing max possible loss",
            target_avg_loss=-6.5,
            wr_impact=-0.01,
            volume_impact=-0.15,  # 15% fewer qualifying trades
        ),
        LossReductionStrategy(
            name="reduced_sizing_low_conf",
            description="Half bet size on lower-confidence entries (price 90-92c)",
            target_avg_loss=-7.50,
            wr_impact=0.0,
            avg_win_impact=-0.10,  # 10% smaller avg win (blended effect)
        ),
        LossReductionStrategy(
            name="portfolio_kelly_sizing",
            description="Apply fractional Kelly to reduce per-bet exposure",
            target_avg_loss=-9.0,
            wr_impact=0.0,
            avg_win_impact=-0.15,  # Kelly reduces bet size = smaller wins AND losses
        ),
    ]

    def __init__(self, base_distribution: BetDistribution):
        self.base_distribution = base_distribution

    def recovery_ratio(self, avg_loss: float) -> float:
        """How many wins needed to recover from one loss at this avg_loss level."""
        if self.base_distribution.avg_win == 0:
            return float("inf")
        return abs(avg_loss) / self.base_distribution.avg_win

    def self_sustaining_daily_pnl(self, monthly_target: float = 250.0) -> float:
        """Minimum daily P&L to hit monthly target (assuming 30 days)."""
        return monthly_target / 30.0

    def _make_distribution(
        self,
        avg_loss: float,
        wr_delta: float = 0.0,
        volume_delta: float = 0.0,
        avg_win_delta: float = 0.0,
    ) -> BetDistribution:
        """Create a modified BetDistribution with adjusted parameters."""
        new_wr = max(0.0, min(1.0, self.base_distribution.win_rate + wr_delta))
        new_volume = max(1, round(self.base_distribution.daily_volume * (1 + volume_delta)))
        new_avg_win = self.base_distribution.avg_win * (1 + avg_win_delta)
        return BetDistribution(
            win_rate=new_wr,
            avg_win=new_avg_win,
            avg_loss=avg_loss,
            total_bets=self.base_distribution.total_bets,
            daily_volume=new_volume,
        )

    def _run_sim(
        self,
        dist: BetDistribution,
        bankroll: float,
        target: float,
        n_days: int,
        n_sims: int,
        seed: int | None = None,
    ):
        """Run Monte Carlo and return SimulationResult."""
        mc = MonteCarloSimulator(dist)
        return mc.run(
            starting_bankroll=bankroll,
            target_bankroll=target,
            n_days=n_days,
            n_simulations=n_sims,
            seed=seed,
        )

    def sweep_avg_loss(
        self,
        start: float,
        end: float,
        step: float,
        bankroll: float,
        target: float,
        n_days: int,
        n_sims: int,
        seed: int | None = None,
    ) -> LossReductionSweep:
        """Sweep avg_loss from start to end and measure ruin/target at each level."""
        # Compute baseline
        baseline_result = self._run_sim(
            self.base_distribution, bankroll, target, n_days, n_sims, seed
        )
        baseline_ruin = baseline_result.ruin_probability

        points = []
        # start is most negative (e.g. -11), end is least negative (e.g. -6)
        # We sweep from start toward end (ascending)
        current = start
        while current <= end + 0.001:
            dist = self._make_distribution(avg_loss=current)
            result = self._run_sim(dist, bankroll, target, n_days, n_sims, seed)
            points.append(
                SweepPoint(
                    avg_loss=current,
                    win_rate=dist.win_rate,
                    ruin_probability=result.ruin_probability,
                    target_probability=result.target_probability,
                    expected_daily_pnl=result.expected_daily_pnl(),
                    median_bankroll=result.median_bankroll,
                )
            )
            current += abs(step)

        return LossReductionSweep(
            baseline_avg_loss=self.base_distribution.avg_loss,
            baseline_ruin=baseline_ruin,
            points=points,
        )

    def evaluate_strategy(
        self,
        strategy: LossReductionStrategy,
        bankroll: float,
        target: float,
        n_days: int,
        n_sims: int,
        seed: int | None = None,
    ) -> StrategyImpact:
        """Evaluate a single loss reduction strategy against baseline."""
        # Baseline
        baseline_result = self._run_sim(
            self.base_distribution, bankroll, target, n_days, n_sims, seed
        )

        # Modified distribution
        modified_dist = self._make_distribution(
            avg_loss=strategy.target_avg_loss,
            wr_delta=strategy.wr_impact,
            volume_delta=strategy.volume_impact,
            avg_win_delta=strategy.avg_win_impact,
        )
        modified_result = self._run_sim(modified_dist, bankroll, target, n_days, n_sims, seed)

        return StrategyImpact(
            strategy_name=strategy.name,
            original_ruin=baseline_result.ruin_probability,
            new_ruin=modified_result.ruin_probability,
            original_daily_pnl=baseline_result.expected_daily_pnl(),
            new_daily_pnl=modified_result.expected_daily_pnl(),
            original_avg_loss=self.base_distribution.avg_loss,
            new_avg_loss=strategy.target_avg_loss,
            ruin_reduction=baseline_result.ruin_probability - modified_result.ruin_probability,
            pnl_improvement=modified_result.expected_daily_pnl() - baseline_result.expected_daily_pnl(),
        )

    def compare_strategies(
        self,
        strategies: list[LossReductionStrategy] | None = None,
        bankroll: float = 178.05,
        target: float = 250.0,
        n_days: int = 60,
        n_sims: int = 10000,
        seed: int | None = None,
    ) -> list[StrategyImpact]:
        """Compare multiple strategies, sorted by ruin reduction (best first)."""
        if strategies is None:
            strategies = self.DEFAULT_STRATEGIES

        results = []
        for s in strategies:
            impact = self.evaluate_strategy(s, bankroll, target, n_days, n_sims, seed)
            results.append(impact)

        results.sort(key=lambda r: r.ruin_reduction, reverse=True)
        return results

    def wr_sensitivity(
        self,
        avg_loss: float,
        wr_range: tuple[float, float] = (0.90, 0.96),
        wr_step: float = 0.01,
        bankroll: float = 178.05,
        target: float = 250.0,
        n_days: int = 60,
        n_sims: int = 10000,
        seed: int | None = None,
    ) -> list[SweepPoint]:
        """Sweep win rate at a fixed avg_loss to find the ruin cliff."""
        points = []
        wr = wr_range[0]
        while wr <= wr_range[1] + 0.0001:
            dist = BetDistribution(
                win_rate=wr,
                avg_win=self.base_distribution.avg_win,
                avg_loss=avg_loss,
                total_bets=self.base_distribution.total_bets,
                daily_volume=self.base_distribution.daily_volume,
            )
            result = self._run_sim(dist, bankroll, target, n_days, n_sims, seed)
            points.append(
                SweepPoint(
                    avg_loss=avg_loss,
                    win_rate=wr,
                    ruin_probability=result.ruin_probability,
                    target_probability=result.target_probability,
                    expected_daily_pnl=result.expected_daily_pnl(),
                    median_bankroll=result.median_bankroll,
                )
            )
            wr = round(wr + wr_step, 4)

        return points

    def full_report(
        self,
        bankroll: float = 178.05,
        target: float = 250.0,
        n_days: int = 60,
        n_sims: int = 10000,
        seed: int | None = None,
    ) -> dict:
        """Generate a complete loss reduction analysis report.

        Returns a JSON-serializable dict with:
        - sweep: avg_loss sweep from current to -5.0
        - strategies: ranked strategy comparison
        - wr_sensitivity: WR cliff analysis at reduced loss level
        - recovery_ratios: wins-to-recover at various loss levels
        - self_sustaining_daily: daily P&L needed for $250/month
        """
        # 1. Sweep avg_loss
        sweep = self.sweep_avg_loss(
            start=round(self.base_distribution.avg_loss),
            end=-5.0,
            step=1.0,
            bankroll=bankroll,
            target=target,
            n_days=n_days,
            n_sims=n_sims,
            seed=seed,
        )

        # 2. Evaluate default strategies
        strategy_impacts = self.compare_strategies(
            bankroll=bankroll,
            target=target,
            n_days=n_days,
            n_sims=n_sims,
            seed=seed,
        )

        # 3. WR sensitivity at -8.0 (the key target)
        wr_sens = self.wr_sensitivity(
            avg_loss=-8.0,
            bankroll=bankroll,
            target=target,
            n_days=n_days,
            n_sims=n_sims,
            seed=seed,
        )

        # 4. Recovery ratios
        loss_levels = [-11.39, -10.0, -9.0, -8.0, -7.5, -7.0, -6.0, -5.0]
        recovery_ratios = {
            f"${lvl:.2f}": round(self.recovery_ratio(lvl), 1)
            for lvl in loss_levels
        }

        # 5. Self-sustaining threshold
        daily_threshold = self.self_sustaining_daily_pnl(250.0)

        return {
            "sweep": sweep.to_dict(),
            "strategies": [s.to_dict() for s in strategy_impacts],
            "wr_sensitivity": [p.to_dict() for p in wr_sens],
            "recovery_ratios": recovery_ratios,
            "self_sustaining_daily": round(daily_threshold, 2),
            "summary": {
                "baseline_avg_loss": round(self.base_distribution.avg_loss, 2),
                "baseline_wr": round(self.base_distribution.win_rate, 4),
                "baseline_daily_volume": self.base_distribution.daily_volume,
                "bankroll": bankroll,
                "target": target,
                "n_days": n_days,
                "n_sims": n_sims,
            },
        }
