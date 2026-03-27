"""Kelly criterion bet sizing optimizer.

Computes full, half, and quarter Kelly fractions for binary outcome bets.
Integrates with stage-based bankroll limits. Answers: what is the
theoretically justified max bet given current WR, payoffs, and bankroll?

The Kelly criterion maximizes long-run log-wealth growth. In practice,
fractional Kelly (0.25x-0.5x) is used to reduce variance at the cost
of slightly slower growth.

For binary bets at ceiling c (e.g. 93c):
  - Win amount = (1 - c) per contract = $0.07 at 93c
  - Loss amount = c per contract = $0.93 at 93c
  - But with max_loss cap, effective loss = min(c * contracts, max_loss)

Usage:
    from kelly_optimizer import KellyOptimizer, KellyParams
    params = KellyParams(win_rate=0.933, avg_win=0.90, avg_loss=8.0, bankroll=213.80)
    opt = KellyOptimizer(params)
    print(opt.summary_text())
"""
import math
from dataclasses import dataclass


@dataclass
class KellyParams:
    """Input parameters for Kelly computation."""

    win_rate: float  # p, probability of winning (0-1)
    avg_win: float  # average win amount in USD
    avg_loss: float  # average loss amount in USD (positive number)
    bankroll: float  # current bankroll in USD

    def edge(self) -> float:
        """Expected value per bet = p*avg_win - q*avg_loss."""
        q = 1.0 - self.win_rate
        return self.win_rate * self.avg_win - q * self.avg_loss


@dataclass
class KellyResult:
    """Kelly computation output."""

    full_kelly_fraction: float  # optimal fraction of bankroll per bet
    half_kelly_fraction: float
    quarter_kelly_fraction: float
    full_kelly_bet: float  # dollar amount at full Kelly
    half_kelly_bet: float
    quarter_kelly_bet: float
    expected_growth_rate: float  # log growth rate at full Kelly
    ruin_at_quarter_kelly: float  # approximate ruin probability
    recommended_bet: float  # stage-capped recommended bet
    edge_per_bet: float


@dataclass
class StageLimits:
    """Stage-based bet sizing constraints from polybot."""

    stage: int
    max_bet: float
    bankroll_floor: float
    bankroll_ceiling: float

    @classmethod
    def for_bankroll(cls, bankroll: float) -> "StageLimits":
        """Determine stage from bankroll level."""
        if bankroll >= 500:
            return cls(stage=3, max_bet=25.0, bankroll_floor=500.0, bankroll_ceiling=float("inf"))
        if bankroll >= 200:
            return cls(stage=2, max_bet=10.0, bankroll_floor=200.0, bankroll_ceiling=500.0)
        return cls(stage=1, max_bet=5.0, bankroll_floor=0.0, bankroll_ceiling=200.0)


class KellyOptimizer:
    """Computes Kelly-optimal bet sizing with stage constraints."""

    def __init__(self, params: KellyParams) -> None:
        self.params = params
        self._result = None

    def compute(self) -> KellyResult:
        """Compute Kelly fractions and dollar amounts."""
        if self._result is not None:
            return self._result

        p = self.params
        edge = p.edge()

        # Kelly fraction for unequal payoffs: f* = edge / avg_loss
        # This is the simplified form for binary outcomes where
        # f* = (p * b - q) / b, with b = avg_win / avg_loss (odds ratio)
        if edge <= 0 or p.avg_loss <= 0:
            self._result = KellyResult(
                full_kelly_fraction=0.0,
                half_kelly_fraction=0.0,
                quarter_kelly_fraction=0.0,
                full_kelly_bet=0.0,
                half_kelly_bet=0.0,
                quarter_kelly_bet=0.0,
                expected_growth_rate=0.0,
                ruin_at_quarter_kelly=1.0,
                recommended_bet=0.0,
                edge_per_bet=edge,
            )
            return self._result

        full_f = edge / p.avg_loss
        half_f = full_f / 2.0
        quarter_f = full_f / 4.0

        full_bet = full_f * p.bankroll
        half_bet = half_f * p.bankroll
        quarter_bet = quarter_f * p.bankroll

        # Expected log growth rate at full Kelly
        # G = p * ln(1 + f*b) + q * ln(1 - f)
        # where b = avg_win / avg_loss, f = full_f
        q = 1.0 - p.win_rate
        b = p.avg_win / p.avg_loss
        win_term = 1.0 + full_f * b
        loss_term = 1.0 - full_f
        if win_term > 0 and loss_term > 0:
            growth = p.win_rate * math.log(win_term) + q * math.log(loss_term)
        else:
            growth = 0.0

        # Approximate ruin probability at quarter Kelly
        # P(ruin) ≈ (q/p)^(bankroll / avg_loss) for favorable games
        # This is a rough lower bound
        if p.win_rate > 0.5 and p.bankroll > 0:
            ruin_base = q / p.win_rate
            exponent = p.bankroll / (quarter_bet if quarter_bet > 0 else p.avg_loss)
            ruin = ruin_base ** min(exponent, 100)  # cap to avoid underflow
        else:
            ruin = 1.0

        # Stage-capped recommendation
        stage = StageLimits.for_bankroll(p.bankroll)
        recommended = min(quarter_bet, stage.max_bet)
        recommended = max(recommended, 0.0)

        self._result = KellyResult(
            full_kelly_fraction=full_f,
            half_kelly_fraction=half_f,
            quarter_kelly_fraction=quarter_f,
            full_kelly_bet=round(full_bet, 2),
            half_kelly_bet=round(half_bet, 2),
            quarter_kelly_bet=round(quarter_bet, 2),
            expected_growth_rate=growth,
            ruin_at_quarter_kelly=ruin,
            recommended_bet=round(recommended, 2),
            edge_per_bet=round(edge, 4),
        )
        return self._result

    def to_dict(self) -> dict:
        """Export as JSON-serializable dict."""
        r = self.compute()
        p = self.params
        stage = StageLimits.for_bankroll(p.bankroll)
        return {
            "params": {
                "win_rate": p.win_rate,
                "avg_win": p.avg_win,
                "avg_loss": p.avg_loss,
                "bankroll": p.bankroll,
                "edge_per_bet": r.edge_per_bet,
            },
            "kelly": {
                "full_kelly_fraction": round(r.full_kelly_fraction, 6),
                "half_kelly_fraction": round(r.half_kelly_fraction, 6),
                "quarter_kelly_fraction": round(r.quarter_kelly_fraction, 6),
                "full_kelly_bet": r.full_kelly_bet,
                "half_kelly_bet": r.half_kelly_bet,
                "quarter_kelly_bet": r.quarter_kelly_bet,
                "expected_growth_rate": round(r.expected_growth_rate, 6),
                "ruin_at_quarter_kelly": round(r.ruin_at_quarter_kelly, 6),
                "recommended_bet": r.recommended_bet,
            },
            "stage": {
                "stage": stage.stage,
                "max_bet": stage.max_bet,
            },
        }

    def summary_text(self) -> str:
        """Human-readable Kelly analysis."""
        r = self.compute()
        p = self.params
        stage = StageLimits.for_bankroll(p.bankroll)

        lines = [
            f"=== KELLY OPTIMIZER ===",
            f"Bankroll: ${p.bankroll:.2f} | Stage {stage.stage} (max ${stage.max_bet:.0f}/bet)",
            f"WR: {p.win_rate:.1%} | Avg win: ${p.avg_win:.2f} | Avg loss: ${p.avg_loss:.2f}",
            f"Edge per bet: ${r.edge_per_bet:.4f}",
            f"",
            f"Kelly fractions:",
            f"  Full Kelly:    {r.full_kelly_fraction:.4f} = ${r.full_kelly_bet:.2f}/bet",
            f"  Half Kelly:    {r.half_kelly_fraction:.4f} = ${r.half_kelly_bet:.2f}/bet",
            f"  Quarter Kelly: {r.quarter_kelly_fraction:.4f} = ${r.quarter_kelly_bet:.2f}/bet",
            f"",
            f"Growth rate (full Kelly): {r.expected_growth_rate:.6f}",
            f"Ruin probability (quarter Kelly): {r.ruin_at_quarter_kelly:.6f}",
            f"",
            f"RECOMMENDED BET: ${r.recommended_bet:.2f} (quarter Kelly, stage-capped)",
        ]
        return "\n".join(lines)
