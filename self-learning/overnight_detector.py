#!/usr/bin/env python3
"""
overnight_detector.py — Objective Signal Detection for Time-Stratified Trading

Core principle: Build off objective signaling, not trauma. Every alert requires
statistical evidence — Wilson CI, CUSUM, or minimum sample sizes. No knee-jerk
reactions to recent losses.

This module:
1. Analyzes existing journal data for time-of-day patterns
2. Provides SQL templates for Kalshi bot DB queries
3. Runs Wilson CI significance tests on time windows
4. Generates CUSUM signals for per-window WR drift
5. Audits whether ALL necessary data fields are being logged

Usage:
    python3 overnight_detector.py analyze        # Analyze journal for time patterns
    python3 overnight_detector.py audit          # Audit data tracking completeness
    python3 overnight_detector.py sql-templates  # Print SQL templates for Kalshi bot
    python3 overnight_detector.py recommend      # Generate objective recommendations
"""

import sys
import os
import json
import math
import argparse
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import journal


# --- Statistical Tools ---

def wilson_ci(n, k, z=1.96):
    """Wilson score confidence interval for win rate.

    Wilson (1927), validated by Brown/Cai/DasGupta (2001).
    Returns (lower, upper) bounds at 95% confidence by default.
    """
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, round(center - margin, 4)), min(1.0, round(center + margin, 4)))


def cusum_signal(outcomes, mu_0, mu_1, h=5.0):
    """Page's CUSUM for detecting downward shift from mu_0 toward mu_1.

    Page (1954). Returns (signaled: bool, max_S: float, trigger_index: int or None).
    """
    k = (mu_0 - mu_1) / 2
    S = 0.0
    max_S = 0.0
    trigger_idx = None
    for i, x in enumerate(outcomes):
        S = max(0, S + (mu_0 - x - k))
        if S > max_S:
            max_S = S
        if S >= h and trigger_idx is None:
            trigger_idx = i
    return (trigger_idx is not None, round(max_S, 4), trigger_idx)


def cis_overlap(ci_a, ci_b):
    """Check if two confidence intervals overlap. Non-overlap = significant difference."""
    return ci_a[1] >= ci_b[0] and ci_b[1] >= ci_a[0]


# --- Analysis Functions ---

def analyze_journal_time_patterns():
    """Analyze journal data for time-of-day trading patterns.

    Returns structured analysis with objective signals only.
    Requires N>=10 per window before making any claims.
    """
    ts = journal.get_time_stratified_trading_metrics()
    if ts is None:
        return {"status": "no_data", "message": "No trading data in journal"}

    analysis = {
        "status": "analyzed",
        "total_bets": ts["total_bets_analyzed"],
        "by_bucket": {},
        "signals": [],
        "recommendations": [],
    }

    # Analyze each bucket
    for label, data in ts["by_time_bucket"].items():
        decided = data["wins"] + data["losses"]
        bucket_analysis = {
            "bets": data["bets"],
            "decided": decided,
            "wins": data["wins"],
            "losses": data["losses"],
            "pnl_cents": data["pnl_cents"],
            "win_rate": data["win_rate"],
        }
        if decided >= 10:
            ci = wilson_ci(decided, data["wins"])
            bucket_analysis["wilson_ci_95"] = ci
            # CUSUM check for WR degradation (detecting drop from 0.90 to 0.70)
            outcomes = []
            for e in journal._load_journal():
                if e.get("event_type") != "bet_outcome":
                    continue
                ts_str = e.get("timestamp", "")
                try:
                    hour = int(ts_str[11:13])
                except (ValueError, IndexError):
                    continue
                # Check if this hour falls in the current bucket
                for bl, bs, be in [("overnight", 0, 8), ("morning", 8, 14),
                                    ("afternoon", 14, 20), ("evening", 20, 24)]:
                    if bl == label and bs <= hour < be:
                        r = e.get("metrics", {}).get("result")
                        if r == "win":
                            outcomes.append(1)
                        elif r == "loss":
                            outcomes.append(0)
            if len(outcomes) >= 10:
                signaled, max_s, idx = cusum_signal(outcomes, 0.90, 0.70, h=5.0)
                bucket_analysis["cusum"] = {
                    "signaled": signaled,
                    "max_S": max_s,
                    "trigger_at_bet": idx,
                }
                if signaled:
                    analysis["signals"].append({
                        "type": "cusum_wr_drop",
                        "bucket": label,
                        "severity": "warning",
                        "detail": f"CUSUM detected WR shift in {label} window at bet #{idx}",
                    })
        else:
            bucket_analysis["note"] = f"Insufficient sample ({decided} decided, need 10+)"

        analysis["by_bucket"][label] = bucket_analysis

    # Overnight vs daytime significance test
    ovd = ts["overnight_vs_daytime"]
    if ovd["significant"]:
        analysis["signals"].append({
            "type": "overnight_degradation",
            "severity": "actionable",
            "detail": (f"Statistically significant difference: "
                      f"overnight WR={ovd['overnight']['win_rate']:.1%}, "
                      f"daytime WR={ovd['daytime']['win_rate']:.1%}, "
                      f"delta={ovd['delta_wr']:.1%}"),
            "evidence": "Wilson CI 95% intervals do not overlap",
        })
        analysis["recommendations"].append(
            "Overnight WR is statistically worse. Investigate: "
            "is it liquidity (wider spreads), strategy (different contract types), "
            "or market regime (overnight news events)? "
            "Run SQL time-stratified query on bot DB for root cause."
        )
    elif ovd["delta_wr"] is not None and ovd["delta_wr"] > 0.05:
        analysis["signals"].append({
            "type": "overnight_trend",
            "severity": "monitor",
            "detail": (f"Trending but not yet significant: "
                      f"overnight WR={ovd['overnight']['win_rate']:.1%}, "
                      f"daytime WR={ovd['daytime']['win_rate']:.1%}"),
            "evidence": "Delta >5% but CIs still overlap — need more data",
        })

    # Worst hours analysis
    for hour, wr, pnl, n in ts["worst_hours"]:
        if pnl < 0 and n >= 5:
            analysis["signals"].append({
                "type": "negative_pnl_hour",
                "severity": "warning" if n >= 10 else "monitor",
                "detail": f"Hour {hour}:00 UTC: {n} bets, WR={wr:.1%}, PnL={pnl/100:.2f} USD",
            })

    return analysis


# --- Data Tracking Audit ---

# All fields that SHOULD be tracked per bet for optimal analysis
OPTIMAL_BET_FIELDS = {
    # Core fields (must have)
    "result": "win/loss/void — the outcome",
    "pnl_cents": "Profit/loss in cents",
    "strategy_name": "Which strategy placed this bet",
    "market_type": "Domain: crypto_15m, politics, weather, etc.",
    # Time fields (for overnight detection)
    "hour_utc": "Hour of bet placement (0-23 UTC)",
    "is_overnight": "Boolean: placed during 00-08 UTC",
    "minutes_to_expiry": "How close to contract expiry",
    # Price fields (for calibration analysis)
    "entry_price_cents": "What we paid per contract",
    "exit_price_cents": "Settlement or exit price",
    "contracts": "Number of contracts",
    "side": "yes/no — which side we bought",
    # Market state fields (for liquidity/regime analysis)
    "bid_ask_spread_cents": "Spread at time of purchase",
    "order_book_depth": "How many contracts available near our price",
    "volume_24h": "24-hour volume on this market",
    # Signal fields (for meta-labeling)
    "signal_strength": "The model's confidence in this bet",
    "guard_overrides": "Which guards were active but didn't block",
    "kelly_fraction": "What Kelly sizing recommended",
    "recalibrated_prob": "Le (2026) recalibrated true probability",
    # Context fields (for pattern detection)
    "ticker": "Contract ticker",
    "session_id": "Which Claude session placed this",
    "session_type": "overnight/daytime — the session classification",
    # Supervision fields (for supervised vs unsupervised analysis)
    "supervised": "Boolean: was Matthew available during this session?",
    "contract_expiry_type": "15min/hourly/daily — affects sniper timing window",
}

# Fields the current journal.py actually captures
CURRENT_BET_FIELDS = {
    "result", "pnl_cents", "strategy_name", "market_type",
    "ticker", "side", "price_cents", "contracts",
}


def audit_data_tracking():
    """Audit whether the trading system logs all necessary fields.

    Returns structured report of what's tracked, what's missing,
    and what the impact of each gap is.
    """
    missing = {}
    present = {}

    for field, description in OPTIMAL_BET_FIELDS.items():
        if field in CURRENT_BET_FIELDS:
            present[field] = description
        else:
            missing[field] = description

    # Check actual journal entries for field usage
    entries = journal._load_journal()
    bet_entries = [e for e in entries if e.get("event_type") == "bet_outcome"]

    actual_fields_seen = set()
    for e in bet_entries:
        for k in e.get("metrics", {}):
            actual_fields_seen.add(k)

    # Fields in schema but never actually logged
    schema_only = CURRENT_BET_FIELDS - actual_fields_seen
    # Fields actually used beyond schema
    extra_fields = actual_fields_seen - CURRENT_BET_FIELDS

    report = {
        "total_optimal_fields": len(OPTIMAL_BET_FIELDS),
        "currently_tracked": len(present),
        "missing": len(missing),
        "coverage_pct": round(len(present) / len(OPTIMAL_BET_FIELDS) * 100, 1),
        "tracked_fields": present,
        "missing_fields": missing,
        "in_schema_never_used": sorted(schema_only),
        "extra_fields_seen": sorted(extra_fields),
        "total_bet_entries": len(bet_entries),
        "impact_assessment": {},
    }

    # Impact assessment for missing fields
    critical_missing = []
    high_missing = []
    medium_missing = []

    for field in missing:
        if field in ("hour_utc", "is_overnight", "minutes_to_expiry"):
            critical_missing.append(field)
        elif field in ("bid_ask_spread_cents", "entry_price_cents",
                       "signal_strength", "kelly_fraction", "recalibrated_prob"):
            high_missing.append(field)
        else:
            medium_missing.append(field)

    report["impact_assessment"] = {
        "critical": {
            "fields": critical_missing,
            "impact": "Cannot detect overnight degradation or expiry timing issues without these",
        },
        "high": {
            "fields": high_missing,
            "impact": "Cannot run calibration analysis, Kelly validation, or spread analysis",
        },
        "medium": {
            "fields": medium_missing,
            "impact": "Limits pattern detection but not core analysis",
        },
    }

    return report


# --- SQL Templates ---

SQL_TEMPLATES = {
    "time_stratified_pnl": """
-- Time-stratified PnL analysis
-- Run this on the Kalshi bot's SQLite database
-- Adjust table/column names to match your schema

SELECT
    CASE
        WHEN CAST(strftime('%H', created_at) AS INTEGER) BETWEEN 0 AND 7 THEN 'overnight'
        WHEN CAST(strftime('%H', created_at) AS INTEGER) BETWEEN 8 AND 13 THEN 'morning'
        WHEN CAST(strftime('%H', created_at) AS INTEGER) BETWEEN 14 AND 19 THEN 'afternoon'
        ELSE 'evening'
    END AS time_window,
    COUNT(*) AS total_bets,
    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
    ROUND(CAST(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS FLOAT)
        / NULLIF(SUM(CASE WHEN result IN ('win','loss') THEN 1 ELSE 0 END), 0), 4) AS win_rate,
    SUM(pnl_cents) AS total_pnl_cents,
    ROUND(SUM(pnl_cents) / 100.0, 2) AS total_pnl_usd,
    ROUND(AVG(pnl_cents) / 100.0, 2) AS avg_pnl_per_bet_usd
FROM trades
WHERE result IN ('win', 'loss')
GROUP BY time_window
ORDER BY total_pnl_cents ASC;
""",

    "hourly_breakdown": """
-- Hourly PnL breakdown (24 hours)
SELECT
    CAST(strftime('%H', created_at) AS INTEGER) AS hour_utc,
    COUNT(*) AS bets,
    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
    ROUND(CAST(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS FLOAT)
        / NULLIF(COUNT(*), 0), 4) AS win_rate,
    SUM(pnl_cents) AS pnl_cents,
    ROUND(SUM(pnl_cents) / 100.0, 2) AS pnl_usd
FROM trades
WHERE result IN ('win', 'loss')
GROUP BY hour_utc
ORDER BY pnl_cents ASC;
""",

    "strategy_by_time": """
-- Strategy performance by time window
SELECT
    strategy_name,
    CASE
        WHEN CAST(strftime('%H', created_at) AS INTEGER) BETWEEN 0 AND 7 THEN 'overnight'
        ELSE 'daytime'
    END AS period,
    COUNT(*) AS bets,
    ROUND(CAST(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS FLOAT)
        / NULLIF(COUNT(*), 0), 4) AS win_rate,
    SUM(pnl_cents) AS pnl_cents
FROM trades
WHERE result IN ('win', 'loss')
GROUP BY strategy_name, period
ORDER BY strategy_name, period;
""",

    "spread_by_time": """
-- Bid-ask spread by time of day (if spread data is logged)
-- This query will fail if spread columns don't exist — that's the gap we need to fix
SELECT
    CASE
        WHEN CAST(strftime('%H', created_at) AS INTEGER) BETWEEN 0 AND 7 THEN 'overnight'
        ELSE 'daytime'
    END AS period,
    ROUND(AVG(ask_price - bid_price), 2) AS avg_spread_cents,
    MIN(ask_price - bid_price) AS min_spread,
    MAX(ask_price - bid_price) AS max_spread,
    COUNT(*) AS observations
FROM order_snapshots  -- or whatever table captures orderbook state
GROUP BY period;
""",

    "daily_pnl_trend": """
-- Daily PnL trend to see if losses cluster on specific days
SELECT
    DATE(created_at) AS trade_date,
    COUNT(*) AS bets,
    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
    ROUND(CAST(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS FLOAT)
        / NULLIF(COUNT(*), 0), 4) AS win_rate,
    SUM(pnl_cents) AS pnl_cents,
    ROUND(SUM(pnl_cents) / 100.0, 2) AS pnl_usd
FROM trades
WHERE result IN ('win', 'loss')
GROUP BY trade_date
ORDER BY trade_date DESC
LIMIT 30;
""",
}


def generate_recommendations(analysis, audit):
    """Generate objective, evidence-based recommendations.

    Only recommends actions backed by statistical evidence.
    """
    recs = []

    # From analysis signals
    for signal in analysis.get("signals", []):
        if signal["severity"] == "actionable":
            recs.append({
                "priority": "HIGH",
                "action": signal["detail"],
                "evidence": signal.get("evidence", "See analysis"),
                "type": "immediate",
            })
        elif signal["severity"] == "warning":
            recs.append({
                "priority": "MEDIUM",
                "action": f"Monitor: {signal['detail']}",
                "evidence": "Sample may be too small — continue collecting data",
                "type": "monitor",
            })

    # From audit gaps
    if audit["coverage_pct"] < 50:
        recs.append({
            "priority": "HIGH",
            "action": (f"Data tracking only covers {audit['coverage_pct']}% of optimal fields. "
                      f"Critical missing: {', '.join(audit['impact_assessment']['critical']['fields'])}"),
            "evidence": "Cannot run time-stratified analysis without hour_utc, is_overnight fields",
            "type": "infrastructure",
        })

    # General
    if analysis.get("total_bets", 0) < 50:
        recs.append({
            "priority": "LOW",
            "action": "Insufficient data for reliable time analysis. Need 50+ bets minimum.",
            "evidence": f"Currently only {analysis.get('total_bets', 0)} bets in journal",
            "type": "data_collection",
        })

    return recs


# --- CLI ---

def _cli():
    parser = argparse.ArgumentParser(
        description="Overnight Detector — Objective Signal Detection for Trading")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("analyze", help="Analyze journal for time-of-day patterns")
    sub.add_parser("audit", help="Audit data tracking completeness")
    sub.add_parser("sql-templates", help="Print SQL templates for Kalshi bot DB")
    sub.add_parser("recommend", help="Generate evidence-based recommendations")

    args = parser.parse_args()

    if args.command == "analyze":
        result = analyze_journal_time_patterns()
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "audit":
        result = audit_data_tracking()
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "sql-templates":
        for name, sql in SQL_TEMPLATES.items():
            print(f"=== {name} ===")
            print(sql)
            print()

    elif args.command == "recommend":
        analysis = analyze_journal_time_patterns()
        audit = audit_data_tracking()
        recs = generate_recommendations(analysis, audit)
        print(json.dumps(recs, indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
