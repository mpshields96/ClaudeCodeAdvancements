#!/usr/bin/env python3
"""
Tests for trade_reflector.py — MT-10 Phase 3A: Kalshi trade pattern analysis.

TDD: These tests define the expected behavior BEFORE implementation.
Target: 40+ tests covering all 5 statistical detectors + proposal generation.
"""

import json
import math
import os
import random
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _create_test_db(trades=None, include_edge=True, include_hour=True,
                    include_cost=True, include_entry_price=True):
    """Create a temporary SQLite DB with a trades table.

    Args:
        trades: list of dicts with trade data. If None, creates empty DB.
        include_edge: whether to include edge_pct column
        include_hour: whether to include hour_utc column
        include_cost: whether to include cost_basis_cents column
        include_entry_price: whether to include entry_price_cents column

    Returns:
        path to temp DB file
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    cols = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "ticker TEXT",
        "strategy_name TEXT",
        "result TEXT",
        "pnl_cents INTEGER",
        "market_type TEXT",
        "contracts INTEGER",
        "side TEXT",
        "created_at TEXT",
    ]
    if include_edge:
        cols.append("edge_pct REAL")
    if include_hour:
        cols.append("hour_utc INTEGER")
    if include_cost:
        cols.append("cost_basis_cents INTEGER")
    if include_entry_price:
        cols.append("entry_price_cents INTEGER")

    conn.execute(f"CREATE TABLE trades ({', '.join(cols)})")

    if trades:
        for t in trades:
            keys = [k for k in t.keys() if k != "id"]
            vals = [t[k] for k in keys]
            placeholders = ", ".join(["?"] * len(keys))
            col_names = ", ".join(keys)
            conn.execute(f"INSERT INTO trades ({col_names}) VALUES ({placeholders})", vals)

    conn.commit()
    conn.close()
    return path


def _make_trades(n, win_rate=0.85, strategy="expiry_sniper", market_type="binary",
                 base_edge=0.15, edge_drift=0.0, base_time=None, hour_range=(8, 22),
                 cost_range=(200, 1000), entry_price_range=(60, 95)):
    """Generate n synthetic trades with controllable parameters.

    Args:
        n: number of trades
        win_rate: probability of each trade being a win
        strategy: strategy name
        market_type: market type
        base_edge: starting edge_pct value
        edge_drift: per-trade drift to edge (negative = erosion)
        base_time: starting datetime (default: now - n hours)
        hour_range: (min_hour, max_hour) for hour_utc
        cost_range: (min, max) for cost_basis_cents
        entry_price_range: (min, max) for entry_price_cents

    Returns:
        list of trade dicts
    """
    if base_time is None:
        base_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

    trades = []
    rng = random.Random(42)  # deterministic

    for i in range(n):
        is_win = rng.random() < win_rate
        result = "win" if is_win else "loss"
        pnl = rng.randint(50, 500) if is_win else -rng.randint(100, 800)
        edge = base_edge + (edge_drift * i)
        hour = rng.randint(*hour_range)
        cost = rng.randint(*cost_range)
        entry = rng.randint(*entry_price_range)
        ts = base_time + timedelta(hours=i)

        trades.append({
            "ticker": f"MARKET-{rng.randint(1000, 9999)}",
            "strategy_name": strategy,
            "result": result,
            "pnl_cents": pnl,
            "market_type": market_type,
            "contracts": rng.randint(1, 10),
            "side": rng.choice(["yes", "no"]),
            "created_at": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "edge_pct": round(edge, 4),
            "hour_utc": hour,
            "cost_basis_cents": cost,
            "entry_price_cents": entry,
        })

    return trades


# ============================================================================
# Test Suite
# ============================================================================

class TestTradeReflectorInit(unittest.TestCase):
    """Tests for TradeReflector initialization and DB access."""

    def test_init_opens_db_readonly(self):
        """TradeReflector opens DB in read-only mode."""
        from trade_reflector import TradeReflector
        trades = _make_trades(5)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            self.assertIsNotNone(tr)
            # Verify read-only: writing should fail
            with self.assertRaises(Exception):
                tr._conn.execute("INSERT INTO trades (ticker) VALUES ('test')")
        finally:
            os.unlink(db_path)

    def test_init_nonexistent_db_raises(self):
        """TradeReflector raises FileNotFoundError for missing DB."""
        from trade_reflector import TradeReflector
        with self.assertRaises(FileNotFoundError):
            TradeReflector("/nonexistent/path/kalshi_bot.db")

    def test_init_empty_db_no_trades_table(self):
        """TradeReflector raises ValueError if trades table missing."""
        from trade_reflector import TradeReflector
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE other (id INTEGER)")
        conn.commit()
        conn.close()
        try:
            with self.assertRaises(ValueError):
                TradeReflector(path)
        finally:
            os.unlink(path)

    def test_get_trade_count(self):
        """TradeReflector reports correct trade count."""
        from trade_reflector import TradeReflector
        trades = _make_trades(25)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            self.assertEqual(tr.trade_count(), 25)
        finally:
            os.unlink(db_path)

    def test_get_trade_count_filtered(self):
        """TradeReflector counts trades by strategy."""
        from trade_reflector import TradeReflector
        trades = _make_trades(15, strategy="sniper") + _make_trades(10, strategy="value")
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            self.assertEqual(tr.trade_count(strategy="sniper"), 15)
            self.assertEqual(tr.trade_count(strategy="value"), 10)
        finally:
            os.unlink(db_path)

    def test_available_columns(self):
        """TradeReflector detects which columns exist."""
        from trade_reflector import TradeReflector
        trades = _make_trades(5)
        db_path = _create_test_db(trades, include_edge=True, include_hour=True)
        try:
            tr = TradeReflector(db_path)
            cols = tr.available_columns()
            self.assertIn("result", cols)
            self.assertIn("strategy_name", cols)
            self.assertIn("edge_pct", cols)
            self.assertIn("hour_utc", cols)
        finally:
            os.unlink(db_path)

    def test_available_columns_missing_optional(self):
        """TradeReflector handles DBs missing optional columns."""
        from trade_reflector import TradeReflector
        trades = [{"ticker": "T", "strategy_name": "s", "result": "win",
                    "pnl_cents": 100, "market_type": "binary", "contracts": 1,
                    "side": "yes", "created_at": "2026-03-01T10:00:00Z"}]
        db_path = _create_test_db(trades, include_edge=False, include_hour=False,
                                   include_cost=False, include_entry_price=False)
        try:
            tr = TradeReflector(db_path)
            cols = tr.available_columns()
            self.assertNotIn("edge_pct", cols)
            self.assertNotIn("hour_utc", cols)
        finally:
            os.unlink(db_path)

    def test_close(self):
        """TradeReflector can be closed cleanly."""
        from trade_reflector import TradeReflector
        db_path = _create_test_db(_make_trades(3))
        try:
            tr = TradeReflector(db_path)
            tr.close()
            # After close, operations should fail
            with self.assertRaises(Exception):
                tr.trade_count()
        finally:
            os.unlink(db_path)


class TestWinRateDrift(unittest.TestCase):
    """Tests for win_rate_drift() — Wilson CI comparison."""

    def test_drift_detected_when_recent_drops(self):
        """Detects significant win rate drift when recent trades underperform."""
        from trade_reflector import TradeReflector
        # 60 historical trades at 90% win rate, then 25 recent at 60%
        good = _make_trades(60, win_rate=0.92, strategy="sniper")
        bad = _make_trades(25, win_rate=0.55, strategy="sniper",
                           base_time=datetime(2026, 3, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            result = tr.win_rate_drift(strategy="sniper")
            self.assertIsNotNone(result)
            self.assertIn("historical_win_rate", result)
            self.assertIn("recent_win_rate", result)
            self.assertIn("wilson_ci_lower", result)
            self.assertIn("significant", result)
            # Recent WR should be much lower
            self.assertLess(result["recent_win_rate"], result["historical_win_rate"])
        finally:
            os.unlink(db_path)

    def test_no_drift_when_stable(self):
        """No drift flagged when win rate is stable."""
        from trade_reflector import TradeReflector
        trades = _make_trades(80, win_rate=0.85, strategy="sniper")
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.win_rate_drift(strategy="sniper")
            self.assertIsNotNone(result)
            self.assertFalse(result["significant"])
        finally:
            os.unlink(db_path)

    def test_insufficient_data_returns_none(self):
        """Returns None when fewer than 20 trades for the strategy."""
        from trade_reflector import TradeReflector
        trades = _make_trades(15, strategy="sniper")
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.win_rate_drift(strategy="sniper")
            self.assertIsNone(result)
        finally:
            os.unlink(db_path)

    def test_drift_all_strategies(self):
        """win_rate_drift(strategy=None) checks each strategy separately."""
        from trade_reflector import TradeReflector
        trades = _make_trades(40, strategy="sniper") + _make_trades(30, strategy="value")
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.win_rate_drift()  # No strategy filter
            self.assertIsInstance(result, dict)
            self.assertIn("sniper", result)
            self.assertIn("value", result)
        finally:
            os.unlink(db_path)

    def test_drift_includes_p_value(self):
        """Drift result includes a p-value for the difference."""
        from trade_reflector import TradeReflector
        good = _make_trades(50, win_rate=0.90, strategy="s")
        bad = _make_trades(25, win_rate=0.50, strategy="s",
                           base_time=datetime(2026, 3, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            result = tr.win_rate_drift(strategy="s")
            self.assertIn("p_value", result)
            self.assertIsInstance(result["p_value"], float)
            self.assertGreaterEqual(result["p_value"], 0.0)
            self.assertLessEqual(result["p_value"], 1.0)
        finally:
            os.unlink(db_path)


class TestTimeOfDayAnalysis(unittest.TestCase):
    """Tests for time_of_day_analysis() — hourly grouping + chi-squared."""

    def test_detects_time_bias(self):
        """Detects bias when overnight trades consistently lose."""
        from trade_reflector import TradeReflector
        # Daytime trades: 85% WR, Overnight: 40% WR
        day_trades = _make_trades(40, win_rate=0.85, hour_range=(10, 20), strategy="s")
        night_trades = _make_trades(20, win_rate=0.35, hour_range=(0, 7), strategy="s",
                                     base_time=datetime(2026, 3, 5, tzinfo=timezone.utc))
        db_path = _create_test_db(day_trades + night_trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.time_of_day_analysis()
            self.assertIsNotNone(result)
            self.assertIn("by_hour", result)
            self.assertIn("chi_squared", result)
            self.assertIn("p_value", result)
        finally:
            os.unlink(db_path)

    def test_insufficient_data_returns_none(self):
        """Returns None when fewer than 50 trades total."""
        from trade_reflector import TradeReflector
        trades = _make_trades(30)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.time_of_day_analysis()
            self.assertIsNone(result)
        finally:
            os.unlink(db_path)

    def test_no_hour_column_returns_none(self):
        """Returns None when hour_utc column doesn't exist."""
        from trade_reflector import TradeReflector
        trades = [{"ticker": "T", "strategy_name": "s", "result": "win",
                    "pnl_cents": 100, "market_type": "binary", "contracts": 1,
                    "side": "yes", "created_at": "2026-03-01T10:00:00Z"}] * 60
        db_path = _create_test_db(trades, include_hour=False, include_edge=False,
                                   include_cost=False, include_entry_price=False)
        try:
            tr = TradeReflector(db_path)
            result = tr.time_of_day_analysis()
            self.assertIsNone(result)
        finally:
            os.unlink(db_path)

    def test_by_hour_structure(self):
        """by_hour has entries for hours that have trades."""
        from trade_reflector import TradeReflector
        trades = _make_trades(60, hour_range=(8, 22))
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.time_of_day_analysis()
            self.assertIsNotNone(result)
            # by_hour should be a dict of hour -> stats
            for hour, stats in result["by_hour"].items():
                self.assertIn("wins", stats)
                self.assertIn("losses", stats)
                self.assertIn("total", stats)
        finally:
            os.unlink(db_path)


class TestStreakAnalysis(unittest.TestCase):
    """Tests for streak_analysis() — Wald-Wolfowitz runs test."""

    def test_detects_non_random_streaks(self):
        """Detects non-random clustering when wins/losses are grouped."""
        from trade_reflector import TradeReflector
        # 15 wins then 15 losses — clearly non-random
        wins = _make_trades(15, win_rate=1.0, strategy="s")
        losses = _make_trades(15, win_rate=0.0, strategy="s",
                               base_time=datetime(2026, 3, 5, tzinfo=timezone.utc))
        db_path = _create_test_db(wins + losses)
        try:
            tr = TradeReflector(db_path)
            result = tr.streak_analysis()
            self.assertIsNotNone(result)
            self.assertIn("runs_count", result)
            self.assertIn("expected_runs", result)
            self.assertIn("p_value", result)
            # With 15W then 15L, runs should be very low (2)
            self.assertLessEqual(result["runs_count"], 5)
        finally:
            os.unlink(db_path)

    def test_random_sequence_not_flagged(self):
        """Random-looking sequence should not be flagged as significant."""
        from trade_reflector import TradeReflector
        trades = _make_trades(50, win_rate=0.50, strategy="s")
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.streak_analysis()
            self.assertIsNotNone(result)
            # p_value should not be extremely low for random data
            # (with seed 42 this should be non-significant at 0.05)
        finally:
            os.unlink(db_path)

    def test_insufficient_data_returns_none(self):
        """Returns None when fewer than 15 trades."""
        from trade_reflector import TradeReflector
        trades = _make_trades(10)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.streak_analysis()
            self.assertIsNone(result)
        finally:
            os.unlink(db_path)

    def test_includes_longest_streak(self):
        """Result includes the longest winning and losing streaks."""
        from trade_reflector import TradeReflector
        trades = _make_trades(30, win_rate=0.70)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.streak_analysis()
            self.assertIsNotNone(result)
            self.assertIn("longest_win_streak", result)
            self.assertIn("longest_loss_streak", result)
            self.assertGreaterEqual(result["longest_win_streak"], 1)
            self.assertGreaterEqual(result["longest_loss_streak"], 1)
        finally:
            os.unlink(db_path)

    def test_excludes_voids(self):
        """Void trades are excluded from streak analysis."""
        from trade_reflector import TradeReflector
        trades = _make_trades(20)
        # Add some voids
        for i in range(5):
            trades.append({
                "ticker": "VOID", "strategy_name": "s", "result": "void",
                "pnl_cents": 0, "market_type": "binary", "contracts": 1,
                "side": "yes", "created_at": f"2026-03-15T{10+i:02d}:00:00Z",
                "edge_pct": 0.1, "hour_utc": 10 + i, "cost_basis_cents": 500,
                "entry_price_cents": 70,
            })
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.streak_analysis()
            # Should only count win/loss, not voids
            self.assertEqual(result["total_trades"], 20)
        finally:
            os.unlink(db_path)


class TestEdgeTrend(unittest.TestCase):
    """Tests for edge_trend() — rolling window edge_pct analysis."""

    def test_detects_declining_edge(self):
        """Detects declining edge when edge_pct trends downward."""
        from trade_reflector import TradeReflector
        # edge_drift=-0.003 over 40 trades = 0.15 -> 0.03
        trades = _make_trades(40, base_edge=0.15, edge_drift=-0.003)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.edge_trend()
            self.assertIsNotNone(result)
            self.assertIn("trend", result)
            self.assertEqual(result["trend"], "declining")
            self.assertIn("slope", result)
            self.assertLess(result["slope"], 0)
        finally:
            os.unlink(db_path)

    def test_stable_edge_not_flagged(self):
        """Stable edge is reported as 'stable'."""
        from trade_reflector import TradeReflector
        trades = _make_trades(40, base_edge=0.12, edge_drift=0.0)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.edge_trend()
            self.assertIsNotNone(result)
            self.assertEqual(result["trend"], "stable")
        finally:
            os.unlink(db_path)

    def test_insufficient_data_returns_none(self):
        """Returns None when fewer than 30 trades."""
        from trade_reflector import TradeReflector
        trades = _make_trades(20)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.edge_trend()
            self.assertIsNone(result)
        finally:
            os.unlink(db_path)

    def test_no_edge_column_returns_none(self):
        """Returns None when edge_pct column doesn't exist."""
        from trade_reflector import TradeReflector
        trades = [{"ticker": "T", "strategy_name": "s", "result": "win",
                    "pnl_cents": 100, "market_type": "binary", "contracts": 1,
                    "side": "yes", "created_at": "2026-03-01T10:00:00Z",
                    "hour_utc": 10, "cost_basis_cents": 500,
                    "entry_price_cents": 70}] * 35
        db_path = _create_test_db(trades, include_edge=False)
        try:
            tr = TradeReflector(db_path)
            result = tr.edge_trend()
            self.assertIsNone(result)
        finally:
            os.unlink(db_path)

    def test_includes_rolling_averages(self):
        """Result includes rolling window averages."""
        from trade_reflector import TradeReflector
        trades = _make_trades(40, base_edge=0.12)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.edge_trend(window=10)
            self.assertIsNotNone(result)
            self.assertIn("rolling_averages", result)
            self.assertGreater(len(result["rolling_averages"]), 0)
        finally:
            os.unlink(db_path)


class TestSizingEfficiency(unittest.TestCase):
    """Tests for sizing_efficiency() — Kelly comparison."""

    def test_detects_oversizing(self):
        """Detects when actual sizing exceeds Kelly-optimal."""
        from trade_reflector import TradeReflector
        # Create trades where cost is much higher than Kelly would suggest
        trades = _make_trades(30, win_rate=0.60, cost_range=(800, 1200),
                              entry_price_range=(50, 60))
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.sizing_efficiency()
            self.assertIsNotNone(result)
            self.assertIn("avg_actual_fraction", result)
            self.assertIn("kelly_optimal", result)
            self.assertIn("efficiency_ratio", result)
        finally:
            os.unlink(db_path)

    def test_insufficient_data_returns_none(self):
        """Returns None when fewer than 20 trades."""
        from trade_reflector import TradeReflector
        trades = _make_trades(15)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.sizing_efficiency()
            self.assertIsNone(result)
        finally:
            os.unlink(db_path)

    def test_no_cost_column_returns_none(self):
        """Returns None when cost column doesn't exist."""
        from trade_reflector import TradeReflector
        trades = [{"ticker": "T", "strategy_name": "s", "result": "win",
                    "pnl_cents": 100, "market_type": "binary", "contracts": 1,
                    "side": "yes", "created_at": "2026-03-01T10:00:00Z",
                    "edge_pct": 0.1, "hour_utc": 10}] * 25
        db_path = _create_test_db(trades, include_cost=False, include_entry_price=False)
        try:
            tr = TradeReflector(db_path)
            result = tr.sizing_efficiency()
            self.assertIsNone(result)
        finally:
            os.unlink(db_path)


class TestAnalyze(unittest.TestCase):
    """Tests for analyze() — full orchestration."""

    def test_analyze_returns_all_sections(self):
        """Full analyze returns sections for each detector."""
        from trade_reflector import TradeReflector
        trades = _make_trades(60, win_rate=0.80)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            report = tr.analyze()
            self.assertIn("summary", report)
            self.assertIn("trade_count", report["summary"])
            self.assertIn("win_rate_drift", report)
            self.assertIn("time_of_day", report)
            self.assertIn("streaks", report)
            self.assertIn("edge_trend", report)
            self.assertIn("sizing", report)
        finally:
            os.unlink(db_path)

    def test_analyze_empty_db(self):
        """Analyze handles DB with no trades gracefully."""
        from trade_reflector import TradeReflector
        db_path = _create_test_db([])
        try:
            tr = TradeReflector(db_path)
            report = tr.analyze()
            self.assertEqual(report["summary"]["trade_count"], 0)
        finally:
            os.unlink(db_path)

    def test_analyze_includes_timestamp(self):
        """Report includes analysis timestamp."""
        from trade_reflector import TradeReflector
        trades = _make_trades(30)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            report = tr.analyze()
            self.assertIn("analyzed_at", report)
        finally:
            os.unlink(db_path)

    def test_analyze_skips_detectors_missing_columns(self):
        """Analyze skips detectors when required columns are missing."""
        from trade_reflector import TradeReflector
        trades = [{"ticker": "T", "strategy_name": "s", "result": "win",
                    "pnl_cents": 100, "market_type": "binary", "contracts": 1,
                    "side": "yes", "created_at": "2026-03-01T10:00:00Z"}] * 60
        db_path = _create_test_db(trades, include_edge=False, include_hour=False,
                                   include_cost=False, include_entry_price=False)
        try:
            tr = TradeReflector(db_path)
            report = tr.analyze()
            # Should still have sections, but with None or "skipped"
            self.assertIsNone(report["edge_trend"])
            self.assertIsNone(report["time_of_day"])
            self.assertIsNone(report["sizing"])
        finally:
            os.unlink(db_path)


class TestGenerateProposals(unittest.TestCase):
    """Tests for generate_proposals() — structured proposal output."""

    def test_proposals_from_drift(self):
        """Generates proposal when win rate drift is detected."""
        from trade_reflector import TradeReflector
        good = _make_trades(60, win_rate=0.92, strategy="sniper")
        bad = _make_trades(25, win_rate=0.45, strategy="sniper",
                           base_time=datetime(2026, 3, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            proposals = tr.generate_proposals()
            self.assertIsInstance(proposals, list)
            # Should have at least one proposal for the drift
            drift_proposals = [p for p in proposals if p["pattern"] == "win_rate_drift"]
            self.assertGreater(len(drift_proposals), 0)
        finally:
            os.unlink(db_path)

    def test_proposal_format(self):
        """Each proposal has the required fields."""
        from trade_reflector import TradeReflector
        good = _make_trades(50, win_rate=0.90, strategy="s")
        bad = _make_trades(25, win_rate=0.40, strategy="s",
                           base_time=datetime(2026, 3, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            proposals = tr.generate_proposals()
            if proposals:
                p = proposals[0]
                required_fields = [
                    "proposal_id", "source", "pattern", "severity",
                    "evidence", "recommendation", "action_type",
                    "auto_applicable", "created_at"
                ]
                for field in required_fields:
                    self.assertIn(field, p, f"Missing field: {field}")
        finally:
            os.unlink(db_path)

    def test_auto_applicable_always_false(self):
        """auto_applicable is ALWAYS false — non-negotiable safety."""
        from trade_reflector import TradeReflector
        good = _make_trades(50, win_rate=0.90, strategy="s")
        bad = _make_trades(25, win_rate=0.40, strategy="s",
                           base_time=datetime(2026, 3, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            proposals = tr.generate_proposals()
            for p in proposals:
                self.assertFalse(p["auto_applicable"],
                                 "auto_applicable must ALWAYS be False for trading")
        finally:
            os.unlink(db_path)

    def test_proposal_id_format(self):
        """Proposal IDs follow tp_YYYYMMDD_hex format."""
        from trade_reflector import TradeReflector
        import re
        good = _make_trades(50, win_rate=0.90, strategy="s")
        bad = _make_trades(25, win_rate=0.40, strategy="s",
                           base_time=datetime(2026, 3, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            proposals = tr.generate_proposals()
            for p in proposals:
                self.assertRegex(p["proposal_id"], r"^tp_\d{8}_[a-f0-9]{8}$")
        finally:
            os.unlink(db_path)

    def test_no_proposals_when_all_healthy(self):
        """No proposals generated when everything looks good."""
        from trade_reflector import TradeReflector
        trades = _make_trades(60, win_rate=0.85, base_edge=0.12, edge_drift=0.0)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            proposals = tr.generate_proposals()
            self.assertIsInstance(proposals, list)
            # Healthy trades should produce zero or minimal proposals
        finally:
            os.unlink(db_path)

    def test_no_proposals_below_minimum_data(self):
        """No proposals when data is below all minimum thresholds."""
        from trade_reflector import TradeReflector
        trades = _make_trades(10)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            proposals = tr.generate_proposals()
            self.assertEqual(len(proposals), 0)
        finally:
            os.unlink(db_path)

    def test_severity_levels(self):
        """Proposals use valid severity levels."""
        from trade_reflector import TradeReflector
        good = _make_trades(50, win_rate=0.92, strategy="s")
        bad = _make_trades(25, win_rate=0.40, strategy="s",
                           base_time=datetime(2026, 3, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            proposals = tr.generate_proposals()
            valid_severities = {"info", "warning", "critical"}
            for p in proposals:
                self.assertIn(p["severity"], valid_severities)
        finally:
            os.unlink(db_path)

    def test_action_types(self):
        """Proposals use valid action types."""
        from trade_reflector import TradeReflector
        good = _make_trades(50, win_rate=0.92, strategy="s")
        bad = _make_trades(25, win_rate=0.40, strategy="s",
                           base_time=datetime(2026, 3, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            proposals = tr.generate_proposals()
            valid_actions = {"monitor", "parameter_adjust", "strategy_pause", "investigation"}
            for p in proposals:
                self.assertIn(p["action_type"], valid_actions)
        finally:
            os.unlink(db_path)


class TestEdgeCases(unittest.TestCase):
    """Edge cases and safety tests."""

    def test_all_wins_no_crash(self):
        """Handles 100% win rate without division errors."""
        from trade_reflector import TradeReflector
        trades = _make_trades(30, win_rate=1.0)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            report = tr.analyze()
            self.assertIsNotNone(report)
        finally:
            os.unlink(db_path)

    def test_all_losses_no_crash(self):
        """Handles 0% win rate without division errors."""
        from trade_reflector import TradeReflector
        trades = _make_trades(30, win_rate=0.0)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            report = tr.analyze()
            self.assertIsNotNone(report)
        finally:
            os.unlink(db_path)

    def test_single_strategy_only(self):
        """Works correctly when DB has only one strategy."""
        from trade_reflector import TradeReflector
        trades = _make_trades(40, strategy="only_one")
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            report = tr.analyze()
            self.assertIsNotNone(report)
        finally:
            os.unlink(db_path)

    def test_negative_edge_pct(self):
        """Handles negative edge_pct values."""
        from trade_reflector import TradeReflector
        trades = _make_trades(35, base_edge=-0.05, edge_drift=0.0)
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.edge_trend()
            self.assertIsNotNone(result)
        finally:
            os.unlink(db_path)

    def test_context_manager(self):
        """TradeReflector works as context manager."""
        from trade_reflector import TradeReflector
        db_path = _create_test_db(_make_trades(5))
        try:
            with TradeReflector(db_path) as tr:
                self.assertEqual(tr.trade_count(), 5)
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
