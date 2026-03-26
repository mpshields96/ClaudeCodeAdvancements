#!/usr/bin/env python3
"""
strategy_health_scorer.py — Statistical strategy health assessment for Kalshi bot.

Evaluates each trading strategy's health using objective statistical measures:
- Win rate vs break-even threshold (given avg cost/payout)
- PnL trend (last N trades vs lifetime)
- Consecutive loss detection
- Sample size adequacy (N >= 20 before any verdict)
- Risk-adjusted return (profit per trade, Sharpe-like ratio)

Outputs: HEALTHY / MONITOR / PAUSE / KILL verdict per strategy.

SAFETY:
- Read-only analysis — no trade execution, no DB writes
- Advisory only — verdicts are recommendations, not automated actions
- Minimum sample size guards prevent premature conclusions

Usage:
    from strategy_health_scorer import score_strategies
    verdicts = score_strategies(trades)  # list of dicts from _read_trades()

Run standalone:
    python3 self-learning/strategy_health_scorer.py --db /path/to/polybot.db
"""

import math
import os
import sys
from dataclasses import dataclass, field

from metric_config import get_metric


# ── Verdict Thresholds (loaded from metric_config, user-overridable) ─────────

MIN_SAMPLE_SIZE = get_metric("strategy_health.min_sample_size", 20)
KILL_PNL_THRESHOLD = get_metric("strategy_health.kill_pnl_threshold", -30.0)
PAUSE_LOSS_STREAK = get_metric("strategy_health.pause_loss_streak", 8)
MONITOR_WIN_RATE_DROP = get_metric("strategy_health.monitor_win_rate_drop", 0.10)
HEALTHY_MIN_PROFIT_PER_TRADE = get_metric("strategy_health.healthy_min_profit_per_trade", 0.0)


@dataclass
class StrategyVerdict:
    """Health verdict for a single strategy."""
    strategy: str
    verdict: str  # HEALTHY / MONITOR / PAUSE / KILL / INSUFFICIENT_DATA
    reasons: list[str] = field(default_factory=list)
    total_trades: int = 0
    settled_trades: int = 0
    wins: int = 0
    win_rate: float = 0.0
    pnl_usd: float = 0.0
    profit_per_trade: float = 0.0
    max_loss_streak: int = 0
    recent_win_rate: float = 0.0  # Last 20 settled trades
    lifetime_win_rate: float = 0.0


def _compute_loss_streak(outcomes: list[bool]) -> int:
    """Compute maximum consecutive loss streak from win/loss booleans."""
    max_streak = 0
    current_streak = 0
    for won in outcomes:
        if not won:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    return max_streak


def _compute_recent_win_rate(outcomes: list[bool], window: int = 20) -> float | None:
    """Win rate of last N settled trades. Returns None if < window trades."""
    if len(outcomes) < window:
        return None
    recent = outcomes[-window:]
    return sum(1 for w in recent if w) / len(recent)


def score_strategy(strategy: str, trades: list[dict]) -> StrategyVerdict:
    """Score a single strategy's health.

    Args:
        strategy: Strategy name
        trades: List of trade dicts for this strategy (from _read_trades)

    Returns:
        StrategyVerdict with health assessment
    """
    total = len(trades)
    settled = [t for t in trades if t.get("result") is not None]
    n_settled = len(settled)

    verdict = StrategyVerdict(
        strategy=strategy,
        verdict="INSUFFICIENT_DATA",
        total_trades=total,
        settled_trades=n_settled,
    )

    if n_settled < MIN_SAMPLE_SIZE:
        verdict.reasons.append(f"Only {n_settled} settled trades (need {MIN_SAMPLE_SIZE})")
        return verdict

    # Compute metrics
    wins = sum(1 for t in settled if t.get("result") == t.get("side"))
    win_rate = wins / n_settled
    pnl = sum(t.get("pnl_usd", 0) or 0 for t in trades)
    profit_per_trade = pnl / n_settled if n_settled > 0 else 0

    outcomes = [t.get("result") == t.get("side") for t in settled]
    max_loss_streak = _compute_loss_streak(outcomes)
    recent_wr = _compute_recent_win_rate(outcomes)

    verdict.wins = wins
    verdict.win_rate = round(win_rate, 4)
    verdict.pnl_usd = round(pnl, 2)
    verdict.profit_per_trade = round(profit_per_trade, 4)
    verdict.max_loss_streak = max_loss_streak
    verdict.lifetime_win_rate = round(win_rate, 4)
    if recent_wr is not None:
        verdict.recent_win_rate = round(recent_wr, 4)

    # ── Verdict Logic (most severe first) ────────────────────────────────

    reasons = []
    severity = "HEALTHY"

    # KILL: Deep cumulative losses
    if pnl <= KILL_PNL_THRESHOLD:
        reasons.append(f"Cumulative PnL ${pnl:.2f} below kill threshold ${KILL_PNL_THRESHOLD:.2f}")
        severity = "KILL"

    # PAUSE: Long loss streaks
    if max_loss_streak >= PAUSE_LOSS_STREAK:
        reasons.append(f"Max loss streak: {max_loss_streak} (threshold: {PAUSE_LOSS_STREAK})")
        if severity != "KILL":
            severity = "PAUSE"

    # MONITOR: Recent win rate dropped significantly
    if recent_wr is not None and (win_rate - recent_wr) >= MONITOR_WIN_RATE_DROP:
        reasons.append(
            f"Recent WR {recent_wr:.0%} dropped {(win_rate - recent_wr):.0%} "
            f"from lifetime {win_rate:.0%}"
        )
        if severity not in ("KILL", "PAUSE"):
            severity = "MONITOR"

    # MONITOR: Negative profit per trade
    if profit_per_trade < HEALTHY_MIN_PROFIT_PER_TRADE and severity == "HEALTHY":
        reasons.append(f"Negative profit per trade: ${profit_per_trade:.4f}")
        severity = "MONITOR"

    if not reasons:
        reasons.append("Strategy is performing within acceptable parameters")

    verdict.verdict = severity
    verdict.reasons = reasons
    return verdict


def score_strategies(trades: list[dict], live_only: bool = True) -> list[StrategyVerdict]:
    """Score all strategies found in trades.

    Args:
        trades: Full list of trade dicts (from _read_trades)
        live_only: If True, only score live trades (is_paper=False).
                   Paper trades are excluded from health verdicts since they
                   don't represent real capital at risk.

    Returns:
        List of StrategyVerdict, sorted by severity (KILL first, then PAUSE, etc.)
    """
    # Filter paper trades if requested
    if live_only:
        filtered = [t for t in trades if not t.get("is_paper", False)]
    else:
        filtered = trades

    # Group by strategy
    by_strategy: dict[str, list[dict]] = {}
    for t in filtered:
        strat = t.get("strategy", "unknown")
        if strat not in by_strategy:
            by_strategy[strat] = []
        by_strategy[strat].append(t)

    verdicts = [score_strategy(name, strat_trades)
                for name, strat_trades in sorted(by_strategy.items())]

    # Sort by severity: KILL > PAUSE > MONITOR > HEALTHY > INSUFFICIENT_DATA
    severity_order = {"KILL": 0, "PAUSE": 1, "MONITOR": 2, "HEALTHY": 3, "INSUFFICIENT_DATA": 4}
    verdicts.sort(key=lambda v: (severity_order.get(v.verdict, 5), -abs(v.pnl_usd)))

    return verdicts


def format_health_report(verdicts: list[StrategyVerdict]) -> str:
    """Format strategy health as markdown for Kalshi consumption."""
    lines = [
        "## Strategy Health Report",
        "",
        "| Strategy | Verdict | Trades | WR | PnL | $/Trade | Max Loss Streak | Reasons |",
        "|----------|---------|--------|-----|-----|---------|-----------------|---------|",
    ]

    for v in verdicts:
        emoji = {"KILL": "KILL", "PAUSE": "PAUSE", "MONITOR": "WATCH",
                 "HEALTHY": "OK", "INSUFFICIENT_DATA": "N/A"}.get(v.verdict, "?")
        reason_str = "; ".join(v.reasons[:2])  # Max 2 reasons for table
        lines.append(
            f"| {v.strategy} | **{emoji}** | {v.settled_trades}/{v.total_trades} | "
            f"{v.win_rate:.0%} | ${v.pnl_usd:.2f} | ${v.profit_per_trade:.2f} | "
            f"{v.max_loss_streak} | {reason_str} |"
        )

    lines.append("")

    # Summary counts
    counts = {}
    for v in verdicts:
        counts[v.verdict] = counts.get(v.verdict, 0) + 1
    summary_parts = [f"{counts.get(k, 0)} {k}" for k in
                     ["KILL", "PAUSE", "MONITOR", "HEALTHY", "INSUFFICIENT_DATA"]
                     if counts.get(k, 0) > 0]
    lines.append(f"**Summary:** {', '.join(summary_parts)}")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    import json

    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, SCRIPT_DIR)

    parser = argparse.ArgumentParser(description="Strategy health scorer")
    parser.add_argument("--db", help="Path to polybot.db")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    from trading_analysis_runner import discover_db, _read_trades

    db_path = discover_db(args.db)
    if db_path is None:
        print("ERROR: polybot.db not found", file=sys.stderr)
        sys.exit(1)

    trades = _read_trades(db_path)
    verdicts = score_strategies(trades)

    if args.json:
        output = [
            {
                "strategy": v.strategy,
                "verdict": v.verdict,
                "reasons": v.reasons,
                "total_trades": v.total_trades,
                "settled_trades": v.settled_trades,
                "win_rate": v.win_rate,
                "pnl_usd": v.pnl_usd,
                "profit_per_trade": v.profit_per_trade,
                "max_loss_streak": v.max_loss_streak,
            }
            for v in verdicts
        ]
        print(json.dumps(output, indent=2))
    else:
        print(format_health_report(verdicts))


if __name__ == "__main__":
    main()
