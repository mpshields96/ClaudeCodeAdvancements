"""risk_dashboard_runner.py — Unified risk analysis dashboard.

Runs all 6 Kalshi analytical tools in sequence and produces a single
JSON report. One command, complete picture.

Modules integrated:
1. edge_decay_detector — trend monitoring
2. volatility_regime_classifier — regime detection + parameter recs
3. bankroll_growth_planner — trajectory projection
4. wr_cliff_analyzer — safety margin analysis
5. loss_reduction_simulator — what-if loss reduction modeling
6. strategy_allocator — capital allocation (if multiple strategies)

Usage:
    from risk_dashboard_runner import RiskDashboard, RiskDashboardConfig
    from edge_decay_detector import BetOutcome

    outcomes = [BetOutcome(date=d, pnl=p, strategy="sniper") for d, p in data]
    config = RiskDashboardConfig(bankroll=178.05)
    report = RiskDashboard(outcomes, config).run()
    print(json.dumps(report, indent=2))
"""
import statistics
from dataclasses import dataclass

from bankroll_growth_planner import GrowthParams, BankrollGrowthPlanner
from edge_decay_detector import BetOutcome, EdgeDecayDetector
from loss_reduction_simulator import LossReductionSimulator
from monte_carlo_simulator import BetDistribution
from volatility_regime_classifier import VolatilityRegimeClassifier
from wr_cliff_analyzer import WRCliffAnalyzer


@dataclass
class RiskDashboardConfig:
    """Configuration for the risk dashboard."""

    bankroll: float = 178.05
    target: float = 250.0
    n_days: int = 60
    n_sims: int = 1000
    seed: int | None = None
    edge_window_size: int = 20
    vol_window_size: int = 50


class RiskDashboard:
    """Unified risk analysis dashboard."""

    def __init__(self, outcomes: list[BetOutcome], config: RiskDashboardConfig | None = None):
        self.outcomes = outcomes
        self.config = config or RiskDashboardConfig()
        self._pnl_values = [o.pnl for o in outcomes]

    def _compute_base_stats(self) -> dict:
        """Compute basic statistics from outcomes."""
        if not self._pnl_values:
            return {
                "n_bets": 0, "win_rate": 0.0, "avg_win": 0.0,
                "avg_loss": 0.0, "daily_volume": 0,
            }

        wins = [p for p in self._pnl_values if p > 0]
        losses = [p for p in self._pnl_values if p <= 0]
        wr = len(wins) / len(self._pnl_values) if self._pnl_values else 0.0
        avg_w = statistics.mean(wins) if wins else 0.0
        avg_l = statistics.mean(losses) if losses else 0.0

        # Estimate daily volume from date spread
        if self.outcomes:
            dates = sorted(set(o.date for o in self.outcomes))
            n_days = max(1, (dates[-1] - dates[0]).days) if len(dates) > 1 else 1
            daily_vol = len(self.outcomes) // n_days
        else:
            daily_vol = 0

        return {
            "n_bets": len(self._pnl_values),
            "win_rate": wr,
            "avg_win": avg_w,
            "avg_loss": avg_l,
            "daily_volume": max(1, daily_vol),
        }

    def run(self) -> dict:
        """Run all 6 analyses and produce unified report."""
        stats = self._compute_base_stats()

        # Handle empty/insufficient data
        if stats["n_bets"] < 3:
            return self._empty_report(stats)

        # 1. Edge trend
        edge_detector = EdgeDecayDetector(window_size=self.config.edge_window_size)
        edge_trend = edge_detector.detect(self.outcomes)

        # 2. Volatility regime
        vol_classifier = VolatilityRegimeClassifier(window_size=self.config.vol_window_size)
        vol_result = vol_classifier.classify(self._pnl_values)
        vol_params = vol_classifier.recommend_params(vol_result.regime)

        # 3. Growth projection
        daily_pnl = stats["win_rate"] * stats["avg_win"] + (1 - stats["win_rate"]) * stats["avg_loss"]
        daily_pnl *= stats["daily_volume"]
        growth_params = GrowthParams(
            starting_bankroll=self.config.bankroll,
            daily_pnl=daily_pnl,
            daily_volume=stats["daily_volume"],
            win_rate=stats["win_rate"],
            avg_win=stats["avg_win"],
            avg_loss=stats["avg_loss"],
        )
        planner = BankrollGrowthPlanner(growth_params)
        milestones = planner.milestones(n_days=self.config.n_days)

        # 4. WR cliff analysis
        cliff_analyzer = WRCliffAnalyzer(
            current_wr=stats["win_rate"],
            avg_win=stats["avg_win"],
            daily_volume=stats["daily_volume"],
            bankroll=self.config.bankroll,
            target=self.config.target,
            n_days=self.config.n_days,
        )
        cliff_report = cliff_analyzer.full_report(
            loss_levels=[stats["avg_loss"], -10.0, -8.0, -6.0],
            n_sims=self.config.n_sims,
            seed=self.config.seed,
        )

        # 5. Loss reduction sweep
        base_dist = BetDistribution(
            win_rate=stats["win_rate"],
            avg_win=stats["avg_win"],
            avg_loss=stats["avg_loss"],
            daily_volume=stats["daily_volume"],
            total_bets=stats["n_bets"],
        )
        loss_sim = LossReductionSimulator(base_dist)
        loss_sweep = loss_sim.sweep_avg_loss(
            start=round(stats["avg_loss"]),
            end=-5.0,
            step=1.0,
            bankroll=self.config.bankroll,
            target=self.config.target,
            n_days=self.config.n_days,
            n_sims=self.config.n_sims,
            seed=self.config.seed,
        )

        # 6. Overall status synthesis
        safety_margin = cliff_report.get("safety_margin", 0.0)
        health = self._assess_health(edge_trend, vol_result, safety_margin)

        return {
            "base_stats": {k: round(v, 4) if isinstance(v, float) else v for k, v in stats.items()},
            "edge_trend": edge_trend.to_dict(),
            "volatility_regime": vol_result.to_dict(),
            "regime_recommendations": vol_params,
            "growth_projection": milestones,
            "cliff_analysis": cliff_report,
            "loss_reduction": loss_sweep.to_dict(),
            "overall_status": health,
        }

    def _assess_health(self, edge_trend, vol_result, safety_margin: float) -> dict:
        """Synthesize overall health assessment from all analyses."""
        issues = []

        if safety_margin < 0:
            issues.append("CRITICAL: WR below ruin cliff")
        elif safety_margin < 0.02:
            issues.append("WARNING: narrow safety margin")

        if edge_trend.direction == "declining":
            issues.append("Edge declining")
        if edge_trend.should_alert:
            issues.append("Edge decay alert triggered")

        if vol_result.regime.value == "high":
            issues.append("High volatility regime")

        if not issues:
            health = "HEALTHY"
            summary = "All systems nominal. Edge stable, safety margin adequate."
        elif any("CRITICAL" in i for i in issues):
            health = "CRITICAL"
            summary = "Immediate action required. " + "; ".join(issues)
        else:
            health = "WARNING"
            summary = "Monitor closely. " + "; ".join(issues)

        # Recommend max_loss based on vol regime
        from volatility_regime_classifier import VolatilityRegimeClassifier
        rec = VolatilityRegimeClassifier().recommend_params(vol_result.regime)

        return {
            "health": health,
            "safety_margin": round(safety_margin, 4),
            "recommended_max_loss": rec["max_loss"],
            "issues": issues,
            "summary": summary,
        }

    def _empty_report(self, stats: dict) -> dict:
        """Report for insufficient data."""
        return {
            "base_stats": stats,
            "edge_trend": {"direction": "unknown", "message": "Insufficient data"},
            "volatility_regime": {"regime": "normal", "message": "Insufficient data"},
            "regime_recommendations": {"max_loss": 8.0, "volume_adjustment": 1.0, "rationale": "Default"},
            "growth_projection": {},
            "cliff_analysis": {},
            "loss_reduction": {},
            "overall_status": {
                "health": "UNKNOWN",
                "safety_margin": 0.0,
                "recommended_max_loss": 8.0,
                "issues": ["Insufficient data for analysis"],
                "summary": "Need more bet outcomes to assess risk.",
            },
        }

    def summary_text(self, report: dict) -> str:
        """Human-readable summary from report dict."""
        status = report["overall_status"]
        stats = report["base_stats"]
        lines = [
            f"=== RISK DASHBOARD ===",
            f"Health: {status['health']}",
            f"Safety margin: {status['safety_margin']:+.1%}",
            f"Recommended max_loss: ${status['recommended_max_loss']:.2f}",
            f"",
            f"Base: {stats['n_bets']} bets, WR {stats['win_rate']:.1%},"
            f" avg_win ${stats['avg_win']:.2f}, avg_loss ${stats['avg_loss']:.2f}",
            f"Edge: {report['edge_trend'].get('direction', 'unknown')}",
            f"Regime: {report['volatility_regime'].get('regime', 'unknown')}",
            f"",
        ]
        if status["issues"]:
            lines.append("Issues:")
            for issue in status["issues"]:
                lines.append(f"  - {issue}")
        lines.append(f"\n{status['summary']}")
        return "\n".join(lines)
