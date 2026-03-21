#!/usr/bin/env python3
"""
trading_analysis_runner.py — MT-10 Phase 3A: Automated Kalshi Analysis Pipeline

Runs trade_reflector + journal trading metrics against polybot.db (read-only),
generates a structured report, and optionally appends to KALSHI_INTEL.md.

This is the "last mile" that makes CCA's self-learning system consumable
by Kalshi research/main chats. One command, fresh analysis.

SAFETY:
- Read-only DB access (sqlite3 URI mode=ro)
- No credential access, no trade execution
- All proposals: advisory only
- Writes only to CCA project files (KALSHI_INTEL.md)

Usage:
    python3 self-learning/trading_analysis_runner.py                    # Full analysis
    python3 self-learning/trading_analysis_runner.py --db /path/to/db   # Explicit DB
    python3 self-learning/trading_analysis_runner.py --json              # JSON output
    python3 self-learning/trading_analysis_runner.py --append-intel      # Append to KALSHI_INTEL.md
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Known locations for polybot.db
DEFAULT_DB_PATHS = [
    os.path.expanduser("~/Projects/polymarket-bot/polybot.db"),
    os.path.expanduser("~/Projects/polymarket-bot/data/polybot.db"),
]

INTEL_PATH = os.path.join(PROJECT_ROOT, "KALSHI_INTEL.md")


# ── DB Discovery ─────────────────────────────────────────────────────────────

def discover_db(explicit_path: str | None = None) -> str | None:
    """Find polybot.db at known locations.

    Priority:
    1. Explicit path argument
    2. POLYBOT_DB_PATH env var
    3. Default known locations

    Returns path if found, None otherwise.
    """
    if explicit_path:
        if os.path.isfile(explicit_path):
            return explicit_path
        return None

    env_path = os.environ.get("POLYBOT_DB_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    for p in DEFAULT_DB_PATHS:
        if os.path.isfile(p):
            return p

    return None


# ── Analysis ─────────────────────────────────────────────────────────────────

def _read_trades(db_path: str) -> list[dict]:
    """Read all trades from polybot.db (read-only)."""
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        # Fallback for test DBs that don't support URI mode
        conn = sqlite3.connect(db_path)

    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT strategy, result, timestamp, price_cents, cost_usd, "
            "payout_usd, market_id, edge_pct FROM trades ORDER BY timestamp"
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _compute_strategy_breakdown(trades: list[dict]) -> dict:
    """Compute per-strategy stats."""
    breakdown = {}
    for t in trades:
        strat = t.get("strategy", "unknown")
        if strat not in breakdown:
            breakdown[strat] = {"count": 0, "wins": 0, "pnl_usd": 0.0}
        breakdown[strat]["count"] += 1
        if t.get("result") == "yes":
            breakdown[strat]["wins"] += 1
        payout = t.get("payout_usd", 0) or 0
        cost = t.get("cost_usd", 0) or 0
        breakdown[strat]["pnl_usd"] += payout - cost

    # Compute win rates
    for strat, data in breakdown.items():
        data["win_rate"] = round(data["wins"] / data["count"], 4) if data["count"] > 0 else 0.0
        data["pnl_usd"] = round(data["pnl_usd"], 2)

    return breakdown


def _run_trade_reflector(db_path: str) -> list[dict]:
    """Run trade_reflector if available, return proposals."""
    try:
        sys.path.insert(0, SCRIPT_DIR)
        from trade_reflector import TradeReflector
        with TradeReflector(db_path) as tr:
            return tr.generate_proposals()
    except Exception:
        return []


def run_analysis(db_path: str) -> dict:
    """Run full analysis pipeline on polybot.db.

    Returns structured report dict.
    """
    trades = _read_trades(db_path)
    n = len(trades)

    if n == 0:
        return {
            "db_path": db_path,
            "trade_count": 0,
            "win_rate": 0.0,
            "pnl_usd": 0.0,
            "proposals": [],
            "strategy_breakdown": {},
            "summary": "No trades found in database.",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    wins = sum(1 for t in trades if t.get("result") == "yes")
    win_rate = round(wins / n, 4)

    total_pnl = sum(
        (t.get("payout_usd", 0) or 0) - (t.get("cost_usd", 0) or 0)
        for t in trades
    )

    breakdown = _compute_strategy_breakdown(trades)
    proposals = _run_trade_reflector(db_path)

    # Build summary
    top_strat = max(breakdown.items(), key=lambda x: x[1]["count"])[0] if breakdown else "none"
    summary = (
        f"{n} trades, {win_rate:.0%} win rate, ${total_pnl:.2f} PnL. "
        f"Top strategy: {top_strat}. {len(proposals)} proposals."
    )

    return {
        "db_path": db_path,
        "trade_count": n,
        "win_rate": win_rate,
        "pnl_usd": round(total_pnl, 2),
        "proposals": proposals,
        "strategy_breakdown": breakdown,
        "summary": summary,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Formatting ───────────────────────────────────────────────────────────────

def format_report(report: dict) -> str:
    """Format analysis report as human-readable markdown."""
    lines = [
        "## Trading Analysis Report",
        "",
        f"**Analyzed:** {report.get('analyzed_at', 'unknown')}",
        f"**Trades:** {report['trade_count']}",
        f"**Win Rate:** {report['win_rate']:.0%}",
        f"**PnL:** ${report['pnl_usd']:.2f}",
        "",
    ]

    # Strategy breakdown
    breakdown = report.get("strategy_breakdown", {})
    if breakdown:
        lines.append("### Strategy Breakdown")
        lines.append("")
        lines.append("| Strategy | Trades | Win Rate | PnL |")
        lines.append("|----------|--------|----------|-----|")
        for strat, data in sorted(breakdown.items()):
            lines.append(
                f"| {strat} | {data['count']} | {data['win_rate']:.0%} | "
                f"${data.get('pnl_usd', 0):.2f} |"
            )
        lines.append("")

    # Proposals
    proposals = report.get("proposals", [])
    if proposals:
        lines.append("### Actionable Proposals")
        lines.append("")
        for p in proposals:
            sev = p.get("severity", "info")
            pattern = p.get("pattern", "unknown")
            rec = p.get("recommendation", "")
            lines.append(f"- **[{sev}]** {pattern}: {rec}")
        lines.append("")
    else:
        lines.append("No actionable proposals at this time.")
        lines.append("")

    lines.append(f"*Summary: {report['summary']}*")
    return "\n".join(lines)


# ── Intel Bridge ─────────────────────────────────────────────────────────────

def append_to_intel(intel_path: str, report: dict) -> None:
    """Append analysis snapshot to KALSHI_INTEL.md.

    Each analysis is a point-in-time snapshot. Multiple entries are fine.
    """
    entry = [
        "",
        f"### Self-Learning Analysis ({report.get('analyzed_at', 'unknown')[:10]})",
        "",
        f"- **Trades:** {report['trade_count']} | **WR:** {report['win_rate']:.0%} | **PnL:** ${report['pnl_usd']:.2f}",
    ]

    breakdown = report.get("strategy_breakdown", {})
    if breakdown:
        for strat, data in sorted(breakdown.items()):
            entry.append(f"- {strat}: {data['count']} trades, {data['win_rate']:.0%} WR")

    proposals = report.get("proposals", [])
    if proposals:
        entry.append(f"- **{len(proposals)} proposals** — see full analysis")
        for p in proposals[:3]:  # Top 3 only
            entry.append(f"  - [{p.get('severity', 'info')}] {p.get('pattern', '')}")

    entry.append(f"- Summary: {report.get('summary', '')}")
    entry.append("")

    path = Path(intel_path)
    if path.exists():
        content = path.read_text()
    else:
        content = "# Kalshi/Trading Intelligence\n\n"

    content += "\n".join(entry)

    # Atomic write
    tmp_path = str(path) + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(content)
    os.replace(tmp_path, str(path))


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run automated Kalshi trading analysis"
    )
    parser.add_argument("--db", help="Explicit path to polybot.db")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--append-intel", action="store_true",
        help="Append results to KALSHI_INTEL.md"
    )
    parser.add_argument(
        "--intel-path", default=INTEL_PATH,
        help="Path to KALSHI_INTEL.md"
    )

    args = parser.parse_args()

    db_path = discover_db(args.db)
    if db_path is None:
        print("ERROR: polybot.db not found.", file=sys.stderr)
        print("Checked:", file=sys.stderr)
        for p in DEFAULT_DB_PATHS:
            print(f"  {p}", file=sys.stderr)
        print("\nSet POLYBOT_DB_PATH or use --db /path/to/polybot.db", file=sys.stderr)
        sys.exit(1)

    report = run_analysis(db_path)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))

    if args.append_intel:
        append_to_intel(args.intel_path, report)
        print(f"\nAppended to {args.intel_path}")


if __name__ == "__main__":
    main()
