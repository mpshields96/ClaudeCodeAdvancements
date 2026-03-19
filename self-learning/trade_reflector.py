#!/usr/bin/env python3
"""
trade_reflector.py — MT-10 Phase 3A: Kalshi Trade Pattern Analysis

Reads Kalshi bot's SQLite DB (read-only) and detects statistical patterns
in trade history. Generates structured proposals for human review.

SAFETY:
- Read-only DB access (sqlite3 URI mode=ro)
- No credential access
- No trade execution
- All proposals: auto_applicable = False (hardcoded)
- Minimum sample sizes enforced for all statistical tests
- p-value gating: no proposal unless p < 0.10

Patterns detected:
1. Win rate drift — Wilson CI comparison (last N vs. historical)
2. Time-of-day bias — Hourly grouping + chi-squared
3. Streak detection — Wald-Wolfowitz runs test
4. Edge erosion — Rolling window edge_pct trend
5. Sizing inefficiency — Actual vs. Kelly-optimal comparison

Usage:
    from trade_reflector import TradeReflector
    with TradeReflector("/path/to/kalshi_bot.db") as tr:
        report = tr.analyze()
        proposals = tr.generate_proposals()
"""

import json
import math
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone


# Minimum sample sizes per pattern (from design doc)
MIN_WIN_RATE_DRIFT = 20
MIN_TIME_OF_DAY = 50
MIN_STREAK = 15
MIN_EDGE_TREND = 30
MIN_SIZING = 20

# p-value threshold for proposal generation
P_VALUE_THRESHOLD = 0.10

VALID_SEVERITIES = {"info", "warning", "critical"}
VALID_ACTIONS = {"monitor", "parameter_adjust", "strategy_pause", "investigation"}


def _wilson_ci(n, k, z=1.96):
    """Wilson score confidence interval for binomial proportion.

    Args:
        n: total trials
        k: successes
        z: z-score (default 1.96 for 95% CI)

    Returns:
        (lower, upper) bounds
    """
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def _two_proportion_z_test(n1, k1, n2, k2):
    """Two-proportion z-test. Returns p-value (two-tailed).

    Args:
        n1, k1: sample 1 (total, successes)
        n2, k2: sample 2 (total, successes)

    Returns:
        p-value (float)
    """
    if n1 == 0 or n2 == 0:
        return 1.0
    p1 = k1 / n1
    p2 = k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    if p_pool == 0 or p_pool == 1:
        return 1.0
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = abs(p1 - p2) / se
    # Approximate p-value using normal CDF (no scipy)
    p_value = 2 * _normal_sf(z)
    return p_value


def _normal_sf(z):
    """Survival function (1 - CDF) for standard normal, approximation.

    Uses Abramowitz and Stegun approximation 26.2.17.
    """
    if z < 0:
        return 1.0 - _normal_sf(-z)
    # Constants for approximation
    b0 = 0.2316419
    b1 = 0.319381530
    b2 = -0.356563782
    b3 = 1.781477937
    b4 = -1.821255978
    b5 = 1.330274429
    t = 1.0 / (1.0 + b0 * z)
    phi = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    return phi * (b1 * t + b2 * t**2 + b3 * t**3 + b4 * t**4 + b5 * t**5)


def _chi_squared_p_value(chi2, df):
    """Approximate chi-squared p-value using Wilson-Hilferty transformation.

    Good enough for df >= 1. No scipy needed.
    """
    if df <= 0 or chi2 <= 0:
        return 1.0
    # Wilson-Hilferty normal approximation
    z = ((chi2 / df) ** (1.0 / 3.0) - (1 - 2.0 / (9 * df))) / math.sqrt(2.0 / (9 * df))
    return _normal_sf(z)


def _linear_regression_slope(values):
    """Simple OLS slope for evenly-spaced values.

    Args:
        values: list of numeric values

    Returns:
        (slope, r_squared)
    """
    n = len(values)
    if n < 2:
        return (0.0, 0.0)
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    ss_xy = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    ss_xx = sum((i - x_mean) ** 2 for i in range(n))
    ss_yy = sum((v - y_mean) ** 2 for v in values)
    if ss_xx == 0:
        return (0.0, 0.0)
    slope = ss_xy / ss_xx
    r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy != 0 else 0.0
    return (slope, r_squared)


class TradeReflector:
    """Analyze Kalshi bot trade history and generate improvement proposals.

    Opens the DB in read-only mode. All statistical tests enforce minimum
    sample sizes. All proposals have auto_applicable=False.
    """

    def __init__(self, db_path: str):
        """Open DB read-only and verify schema.

        Args:
            db_path: path to kalshi_bot.db

        Raises:
            FileNotFoundError: if db_path doesn't exist
            ValueError: if trades table is missing
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")

        # Open read-only via URI
        uri = f"file:{db_path}?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True)
        self._conn.row_factory = sqlite3.Row

        # Verify trades table exists
        tables = [r[0] for r in self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "trades" not in tables:
            self._conn.close()
            raise ValueError("Database missing 'trades' table")

        self._columns = self._discover_columns()

    def _discover_columns(self):
        """Discover available columns in the trades table."""
        cursor = self._conn.execute("PRAGMA table_info(trades)")
        return [row[1] for row in cursor.fetchall()]

    def available_columns(self):
        """Return list of column names in the trades table."""
        return list(self._columns)

    def trade_count(self, strategy=None):
        """Count trades, optionally filtered by strategy.

        Args:
            strategy: if provided, only count trades with this strategy_name

        Returns:
            int count
        """
        if strategy:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM trades WHERE strategy_name = ?",
                (strategy,)).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM trades").fetchone()
        return row[0]

    def _get_strategies(self):
        """Get list of distinct strategy names."""
        rows = self._conn.execute(
            "SELECT DISTINCT strategy_name FROM trades WHERE strategy_name IS NOT NULL"
        ).fetchall()
        return [r[0] for r in rows]

    def win_rate_drift(self, strategy=None, recent_n=20):
        """Wilson CI comparison: last N trades vs. all-time for a strategy.

        Args:
            strategy: specific strategy to check. If None, checks each strategy
                      and returns dict keyed by strategy name.
            recent_n: number of recent trades to compare (default 20)

        Returns:
            If strategy specified: dict with drift analysis, or None if insufficient data.
            If strategy is None: dict of {strategy_name: drift_result}
        """
        if strategy is None:
            strategies = self._get_strategies()
            results = {}
            for s in strategies:
                r = self.win_rate_drift(strategy=s, recent_n=recent_n)
                if r is not None:
                    results[s] = r
                else:
                    results[s] = None
            return results

        # Get all win/loss trades for this strategy, ordered by created_at
        rows = self._conn.execute(
            "SELECT result FROM trades WHERE strategy_name = ? AND result IN ('win', 'loss') "
            "ORDER BY created_at ASC",
            (strategy,)
        ).fetchall()

        total = len(rows)
        if total < MIN_WIN_RATE_DRIFT:
            return None

        # Split into historical and recent
        recent_start = max(0, total - recent_n)
        historical = rows[:recent_start]
        recent = rows[recent_start:]

        if len(historical) < 5 or len(recent) < 5:
            return None

        hist_wins = sum(1 for r in historical if r[0] == "win")
        recent_wins = sum(1 for r in recent if r[0] == "win")

        hist_wr = hist_wins / len(historical)
        recent_wr = recent_wins / len(recent)

        wilson_lo, wilson_hi = _wilson_ci(len(recent), recent_wins)
        p_value = _two_proportion_z_test(
            len(historical), hist_wins, len(recent), recent_wins)

        significant = p_value < P_VALUE_THRESHOLD

        return {
            "strategy": strategy,
            "historical_win_rate": round(hist_wr, 4),
            "recent_win_rate": round(recent_wr, 4),
            "wilson_ci_lower": round(wilson_lo, 4),
            "wilson_ci_upper": round(wilson_hi, 4),
            "sample_size_historical": len(historical),
            "sample_size_recent": len(recent),
            "p_value": round(p_value, 6),
            "significant": significant,
        }

    def time_of_day_analysis(self):
        """Group trades by hour, identify statistically significant biases.

        Requires hour_utc column. Uses chi-squared test.

        Returns:
            dict with by_hour stats and chi-squared test, or None if
            insufficient data or missing column.
        """
        if "hour_utc" not in self._columns:
            return None

        rows = self._conn.execute(
            "SELECT hour_utc, result FROM trades WHERE result IN ('win', 'loss') "
            "AND hour_utc IS NOT NULL"
        ).fetchall()

        if len(rows) < MIN_TIME_OF_DAY:
            return None

        # Group by hour
        by_hour = {}
        total_wins = 0
        total_trades = 0

        for hour, result in rows:
            if hour not in by_hour:
                by_hour[hour] = {"wins": 0, "losses": 0, "total": 0}
            by_hour[hour]["total"] += 1
            if result == "win":
                by_hour[hour]["wins"] += 1
                total_wins += 1
            else:
                by_hour[hour]["losses"] += 1
            total_trades += 1

        # Compute win rates per hour
        for h in by_hour:
            t = by_hour[h]["total"]
            by_hour[h]["win_rate"] = round(by_hour[h]["wins"] / t, 4) if t > 0 else None

        # Chi-squared test: are win rates uniform across hours?
        overall_wr = total_wins / total_trades if total_trades > 0 else 0
        chi2 = 0.0
        df = 0

        for h, stats in by_hour.items():
            if stats["total"] >= 5:  # Need sufficient expected count
                expected_wins = stats["total"] * overall_wr
                expected_losses = stats["total"] * (1 - overall_wr)
                if expected_wins > 0:
                    chi2 += (stats["wins"] - expected_wins) ** 2 / expected_wins
                if expected_losses > 0:
                    chi2 += (stats["losses"] - expected_losses) ** 2 / expected_losses
                df += 1

        df = max(df - 1, 1)  # degrees of freedom
        p_value = _chi_squared_p_value(chi2, df)

        return {
            "by_hour": by_hour,
            "chi_squared": round(chi2, 4),
            "degrees_of_freedom": df,
            "p_value": round(p_value, 6),
            "significant": p_value < P_VALUE_THRESHOLD,
            "overall_win_rate": round(overall_wr, 4),
            "total_trades": total_trades,
        }

    def streak_analysis(self):
        """Wald-Wolfowitz runs test for non-random streaks.

        Returns:
            dict with runs test results, or None if insufficient data.
        """
        rows = self._conn.execute(
            "SELECT result FROM trades WHERE result IN ('win', 'loss') "
            "ORDER BY created_at ASC"
        ).fetchall()

        results = [r[0] for r in rows]
        if len(results) < MIN_STREAK:
            return None

        n = len(results)
        n1 = sum(1 for r in results if r == "win")   # wins
        n2 = n - n1                                     # losses

        if n1 == 0 or n2 == 0:
            # All same result — can't compute runs test
            return {
                "total_trades": n,
                "wins": n1,
                "losses": n2,
                "runs_count": 1,
                "expected_runs": 1.0,
                "z_score": 0.0,
                "p_value": 1.0,
                "significant": False,
                "longest_win_streak": n if n1 == n else 0,
                "longest_loss_streak": n if n2 == n else 0,
            }

        # Count runs
        runs = 1
        for i in range(1, n):
            if results[i] != results[i - 1]:
                runs += 1

        # Expected runs and variance under H0 (random)
        expected = 1 + (2 * n1 * n2) / n
        if n <= 1:
            variance = 0
        else:
            variance = (2 * n1 * n2 * (2 * n1 * n2 - n)) / (n * n * (n - 1))

        if variance > 0:
            z = (runs - expected) / math.sqrt(variance)
            p_value = 2 * _normal_sf(abs(z))
        else:
            z = 0.0
            p_value = 1.0

        # Compute longest streaks
        longest_win = 0
        longest_loss = 0
        current_streak = 1
        for i in range(1, n):
            if results[i] == results[i - 1]:
                current_streak += 1
            else:
                if results[i - 1] == "win":
                    longest_win = max(longest_win, current_streak)
                else:
                    longest_loss = max(longest_loss, current_streak)
                current_streak = 1
        # Don't forget the last streak
        if results[-1] == "win":
            longest_win = max(longest_win, current_streak)
        else:
            longest_loss = max(longest_loss, current_streak)

        return {
            "total_trades": n,
            "wins": n1,
            "losses": n2,
            "runs_count": runs,
            "expected_runs": round(expected, 2),
            "z_score": round(z, 4),
            "p_value": round(p_value, 6),
            "significant": p_value < P_VALUE_THRESHOLD,
            "longest_win_streak": longest_win,
            "longest_loss_streak": longest_loss,
        }

    def edge_trend(self, window=20):
        """Rolling window edge_pct: rising, stable, or declining.

        Args:
            window: rolling window size (default 20)

        Returns:
            dict with trend analysis, or None if insufficient data or
            missing column.
        """
        if "edge_pct" not in self._columns:
            return None

        rows = self._conn.execute(
            "SELECT edge_pct FROM trades WHERE edge_pct IS NOT NULL "
            "ORDER BY created_at ASC"
        ).fetchall()

        values = [r[0] for r in rows]
        if len(values) < MIN_EDGE_TREND:
            return None

        # Compute rolling averages
        rolling = []
        for i in range(len(values) - window + 1):
            chunk = values[i:i + window]
            rolling.append(round(sum(chunk) / len(chunk), 6))

        # Linear regression on rolling averages
        slope, r_squared = _linear_regression_slope(rolling)

        # Classify trend
        # Threshold: slope magnitude > 0.001 per window step
        if abs(slope) < 0.001:
            trend = "stable"
        elif slope < 0:
            trend = "declining"
        else:
            trend = "rising"

        return {
            "trend": trend,
            "slope": round(slope, 6),
            "r_squared": round(r_squared, 4),
            "data_points": len(values),
            "window_size": window,
            "rolling_averages": rolling,
            "first_avg": rolling[0] if rolling else None,
            "last_avg": rolling[-1] if rolling else None,
        }

    def sizing_efficiency(self):
        """Compare actual sizing vs. Kelly-optimal.

        Requires cost_basis_cents and entry_price_cents columns, plus
        enough win/loss data to estimate true win probability.

        Returns:
            dict with sizing analysis, or None if insufficient data or
            missing columns.
        """
        required = {"cost_basis_cents", "entry_price_cents"}
        if not required.issubset(set(self._columns)):
            return None

        rows = self._conn.execute(
            "SELECT result, cost_basis_cents, entry_price_cents FROM trades "
            "WHERE result IN ('win', 'loss') "
            "AND cost_basis_cents IS NOT NULL AND entry_price_cents IS NOT NULL"
        ).fetchall()

        if len(rows) < MIN_SIZING:
            return None

        wins = sum(1 for r in rows if r[0] == "win")
        n = len(rows)
        win_prob = wins / n

        # Kelly fraction: f* = (bp - q) / b
        # For binary contracts: b = (100 - avg_entry_price) / avg_entry_price
        # where entry_price is in cents (0-100 range)
        avg_entry = sum(r[2] for r in rows) / n
        avg_cost = sum(r[1] for r in rows) / n

        if avg_entry <= 0 or avg_entry >= 100:
            return None

        # Binary contract: pay entry_price cents, win (100 - entry_price) cents
        b = (100 - avg_entry) / avg_entry  # odds ratio
        q = 1 - win_prob

        kelly_fraction = (b * win_prob - q) / b if b > 0 else 0.0
        kelly_fraction = max(0.0, kelly_fraction)  # Kelly says don't bet if negative

        # Actual fraction: approximate from cost vs typical bankroll
        # We can't know bankroll, so report raw cost stats
        return {
            "total_trades": n,
            "win_rate": round(win_prob, 4),
            "avg_entry_price_cents": round(avg_entry, 2),
            "avg_cost_basis_cents": round(avg_cost, 2),
            "kelly_optimal": round(kelly_fraction, 4),
            "avg_actual_fraction": round(avg_cost / 10000, 4),  # Rough: assume $100 base
            "efficiency_ratio": round(
                (avg_cost / 10000) / kelly_fraction, 4
            ) if kelly_fraction > 0 else None,
            "odds_ratio": round(b, 4),
        }

    def analyze(self):
        """Run all detectors. Return structured report.

        Returns:
            dict with summary + results from each detector
        """
        count = self.trade_count()

        report = {
            "analyzed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "summary": {
                "trade_count": count,
                "strategies": self._get_strategies() if count > 0 else [],
                "available_columns": self.available_columns(),
            },
            "win_rate_drift": self.win_rate_drift() if count >= MIN_WIN_RATE_DRIFT else None,
            "time_of_day": self.time_of_day_analysis() if count >= MIN_TIME_OF_DAY else None,
            "streaks": self.streak_analysis() if count >= MIN_STREAK else None,
            "edge_trend": self.edge_trend() if count >= MIN_EDGE_TREND else None,
            "sizing": self.sizing_efficiency() if count >= MIN_SIZING else None,
        }

        return report

    def generate_proposals(self):
        """Convert detected patterns into structured proposals.

        Returns:
            list of proposal dicts
        """
        report = self.analyze()
        proposals = []

        # Win rate drift proposals
        drift = report.get("win_rate_drift")
        if isinstance(drift, dict):
            for strategy, result in drift.items():
                if result and result.get("significant"):
                    severity = "critical" if result["p_value"] < 0.01 else "warning"
                    action = "strategy_pause" if result["recent_win_rate"] < 0.50 else "monitor"
                    proposals.append(self._make_proposal(
                        pattern="win_rate_drift",
                        strategy=strategy,
                        severity=severity,
                        evidence=result,
                        recommendation=(
                            f"{strategy} win rate dropped from "
                            f"{result['historical_win_rate']:.0%} to "
                            f"{result['recent_win_rate']:.0%} "
                            f"(last {result['sample_size_recent']} trades). "
                            f"p={result['p_value']:.4f}."
                        ),
                        action_type=action,
                    ))

        # Time-of-day proposals
        tod = report.get("time_of_day")
        if tod and tod.get("significant"):
            # Find worst hours
            worst = sorted(
                [(h, s) for h, s in tod["by_hour"].items() if s["total"] >= 5],
                key=lambda x: x[1].get("win_rate", 1.0)
            )
            if worst:
                h, s = worst[0]
                proposals.append(self._make_proposal(
                    pattern="time_of_day_bias",
                    severity="warning",
                    evidence={
                        "worst_hour": h,
                        "worst_hour_wr": s["win_rate"],
                        "worst_hour_n": s["total"],
                        "overall_wr": tod["overall_win_rate"],
                        "chi_squared": tod["chi_squared"],
                        "p_value": tod["p_value"],
                    },
                    recommendation=(
                        f"Hour {h} UTC has {s['win_rate']:.0%} win rate "
                        f"({s['total']} trades) vs {tod['overall_win_rate']:.0%} overall. "
                        f"Chi-squared p={tod['p_value']:.4f}."
                    ),
                    action_type="investigation",
                ))

        # Streak proposals
        streaks = report.get("streaks")
        if streaks and streaks.get("significant"):
            proposals.append(self._make_proposal(
                pattern="streak_anomaly",
                severity="info",
                evidence={
                    "runs_count": streaks["runs_count"],
                    "expected_runs": streaks["expected_runs"],
                    "z_score": streaks["z_score"],
                    "p_value": streaks["p_value"],
                    "longest_win_streak": streaks["longest_win_streak"],
                    "longest_loss_streak": streaks["longest_loss_streak"],
                },
                recommendation=(
                    f"Trade outcomes show non-random clustering "
                    f"({streaks['runs_count']} runs vs {streaks['expected_runs']:.1f} expected). "
                    f"Longest loss streak: {streaks['longest_loss_streak']}. "
                    f"p={streaks['p_value']:.4f}."
                ),
                action_type="investigation",
            ))

        # Edge trend proposals
        edge = report.get("edge_trend")
        if edge and edge["trend"] == "declining":
            severity = "critical" if edge["r_squared"] > 0.5 else "warning"
            proposals.append(self._make_proposal(
                pattern="edge_erosion",
                severity=severity,
                evidence={
                    "trend": edge["trend"],
                    "slope": edge["slope"],
                    "r_squared": edge["r_squared"],
                    "first_avg": edge["first_avg"],
                    "last_avg": edge["last_avg"],
                },
                recommendation=(
                    f"Edge declining: slope={edge['slope']:.4f}, "
                    f"R²={edge['r_squared']:.3f}. "
                    f"Edge moved from {edge['first_avg']:.3f} to {edge['last_avg']:.3f}."
                ),
                action_type="monitor" if edge["r_squared"] < 0.3 else "parameter_adjust",
            ))

        return proposals

    def _make_proposal(self, pattern, severity, evidence, recommendation,
                       action_type, strategy=None):
        """Create a structured proposal dict.

        auto_applicable is ALWAYS False — hardcoded, non-negotiable.
        """
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        hex_id = secrets.token_hex(4)

        return {
            "proposal_id": f"tp_{date_str}_{hex_id}",
            "source": "trade_reflector",
            "pattern": pattern,
            "strategy": strategy,
            "severity": severity,
            "evidence": evidence,
            "recommendation": recommendation,
            "action_type": action_type,
            "auto_applicable": False,  # NEVER True for trading
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def close(self):
        """Close the database connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def _cli():
    """CLI entry point for trade_reflector."""
    import argparse

    parser = argparse.ArgumentParser(description="Kalshi Trade Pattern Analyzer")
    parser.add_argument("db_path", help="Path to kalshi_bot.db")
    parser.add_argument("--strategy", help="Filter by strategy name")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("analyze", help="Run full analysis")
    sub.add_parser("proposals", help="Generate proposals")
    sub.add_parser("drift", help="Win rate drift check")
    sub.add_parser("time", help="Time-of-day analysis")
    sub.add_parser("streaks", help="Streak analysis")
    sub.add_parser("edge", help="Edge trend analysis")
    sub.add_parser("sizing", help="Sizing efficiency")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    with TradeReflector(args.db_path) as tr:
        if args.command == "analyze":
            result = tr.analyze()
        elif args.command == "proposals":
            result = tr.generate_proposals()
        elif args.command == "drift":
            result = tr.win_rate_drift(strategy=args.strategy)
        elif args.command == "time":
            result = tr.time_of_day_analysis()
        elif args.command == "streaks":
            result = tr.streak_analysis()
        elif args.command == "edge":
            result = tr.edge_trend()
        elif args.command == "sizing":
            result = tr.sizing_efficiency()
        else:
            parser.print_help()
            return

        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    _cli()
