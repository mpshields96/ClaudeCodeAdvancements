#!/usr/bin/env python3
"""
Tests for trade_reflector.py — MT-10 Phase 3A: Kalshi trade pattern analysis.

Schema matches real polybot.db:
- strategy (not strategy_name)
- result: 'yes' (win) / 'no' (loss)
- timestamp: REAL epoch
- price_cents: entry price 1-99
- cost_usd: cost in dollars
- edge_pct: REAL
- created_at: REAL epoch
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _create_test_db(trades=None, include_edge=True, include_timestamp=True,
                    include_cost=True, include_price=True):
    """Create a temporary SQLite DB matching real polybot.db schema.

    Args:
        trades: list of dicts with trade data. If None, creates empty DB.
        include_edge: whether to include edge_pct column
        include_timestamp: whether to include timestamp column
        include_cost: whether to include cost_usd column
        include_price: whether to include price_cents column

    Returns:
        path to temp DB file
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    cols = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "ticker TEXT",
        "strategy TEXT",
        "side TEXT",
        "action TEXT",
        "count INTEGER",
        "result TEXT",
        "pnl_cents INTEGER",
        "is_paper INTEGER DEFAULT 1",
        "created_at REAL",
    ]
    if include_timestamp:
        cols.append("timestamp REAL")
    if include_edge:
        cols.append("edge_pct REAL")
    if include_cost:
        cols.append("cost_usd REAL")
    if include_price:
        cols.append("price_cents INTEGER")

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


def _make_trades(n, win_rate=0.85, strategy="expiry_sniper",
                 base_edge=0.15, edge_drift=0.0, base_time=None,
                 hour_range=(8, 22), cost_range=(2.0, 10.0),
                 price_range=(60, 95)):
    """Generate n synthetic trades matching real polybot.db schema.

    Args:
        n: number of trades
        win_rate: probability of each trade being a win (result='yes')
        strategy: strategy name
        base_edge: starting edge_pct value
        edge_drift: per-trade drift to edge (negative = erosion)
        base_time: starting datetime (default: 2026-03-01 10:00 UTC)
        hour_range: (min_hour, max_hour) for trade hour (sets timestamp accordingly)
        cost_range: (min, max) for cost_usd in dollars
        price_range: (min, max) for price_cents (1-99 range)

    Returns:
        list of trade dicts
    """
    if base_time is None:
        base_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

    trades = []
    rng = random.Random(42)

    for i in range(n):
        is_win = rng.random() < win_rate
        result = "yes" if is_win else "no"
        pnl = rng.randint(50, 500) if is_win else -rng.randint(100, 800)
        edge = base_edge + (edge_drift * i)
        hour = rng.randint(*hour_range)
        cost = round(rng.uniform(*cost_range), 2)
        price = rng.randint(*price_range)

        # Set timestamp with the random hour
        ts_dt = base_time.replace(hour=min(hour, 23)) + timedelta(days=i)
        ts_epoch = ts_dt.timestamp()

        trades.append({
            "ticker": f"KXBTC15M-{rng.randint(1000, 9999)}",
            "strategy": strategy,
            "side": rng.choice(["yes", "no"]),
            "action": "buy",
            "count": rng.randint(1, 10),
            "result": result,
            "pnl_cents": pnl,
            "is_paper": 1,
            "created_at": ts_epoch,
            "timestamp": ts_epoch,
            "edge_pct": round(edge, 4),
            "cost_usd": cost,
            "price_cents": price,
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
        db_path = _create_test_db(trades, include_edge=True)
        try:
            tr = TradeReflector(db_path)
            cols = tr.available_columns()
            self.assertIn("result", cols)
            self.assertIn("strategy", cols)
            self.assertIn("edge_pct", cols)
            self.assertIn("timestamp", cols)
            self.assertIn("price_cents", cols)
            self.assertIn("cost_usd", cols)
        finally:
            os.unlink(db_path)

    def test_available_columns_missing_optional(self):
        """TradeReflector handles DBs missing optional columns."""
        from trade_reflector import TradeReflector
        trades = [{"ticker": "T", "strategy": "s", "result": "yes",
                   "pnl_cents": 100, "side": "yes", "action": "buy",
                   "count": 1, "created_at": 1709290800.0}]
        db_path = _create_test_db(trades, include_edge=False, include_timestamp=False,
                                  include_cost=False, include_price=False)
        try:
            tr = TradeReflector(db_path)
            cols = tr.available_columns()
            self.assertNotIn("edge_pct", cols)
            self.assertNotIn("timestamp", cols)
        finally:
            os.unlink(db_path)

    def test_close(self):
        """TradeReflector can be closed cleanly."""
        from trade_reflector import TradeReflector
        db_path = _create_test_db(_make_trades(3))
        try:
            tr = TradeReflector(db_path)
            tr.close()
            with self.assertRaises(Exception):
                tr.trade_count()
        finally:
            os.unlink(db_path)


class TestWinRateDrift(unittest.TestCase):
    """Tests for win_rate_drift() — Wilson CI comparison."""

    def test_drift_detected_when_recent_drops(self):
        """Detects significant win rate drift when recent trades underperform."""
        from trade_reflector import TradeReflector
        good = _make_trades(60, win_rate=0.92, strategy="sniper")
        bad = _make_trades(25, win_rate=0.55, strategy="sniper",
                           base_time=datetime(2026, 5, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            result = tr.win_rate_drift(strategy="sniper")
            self.assertIsNotNone(result)
            self.assertIn("historical_win_rate", result)
            self.assertIn("recent_win_rate", result)
            self.assertIn("wilson_ci_lower", result)
            self.assertIn("significant", result)
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
            result = tr.win_rate_drift()
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
                           base_time=datetime(2026, 5, 10, tzinfo=timezone.utc))
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

    def test_no_timestamp_column_returns_none(self):
        """Returns None when timestamp column doesn't exist."""
        from trade_reflector import TradeReflector
        trades = [{"ticker": "T", "strategy": "s", "result": "yes",
                   "pnl_cents": 100, "side": "yes", "action": "buy",
                   "count": 1, "created_at": 1709290800.0 + i * 3600}
                  for i in range(60)]
        db_path = _create_test_db(trades, include_timestamp=False, include_edge=False,
                                  include_cost=False, include_price=False)
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
        wins = _make_trades(15, win_rate=1.0, strategy="s")
        losses = _make_trades(15, win_rate=0.0, strategy="s",
                              base_time=datetime(2026, 4, 5, tzinfo=timezone.utc))
        db_path = _create_test_db(wins + losses)
        try:
            tr = TradeReflector(db_path)
            result = tr.streak_analysis()
            self.assertIsNotNone(result)
            self.assertIn("runs_count", result)
            self.assertIn("expected_runs", result)
            self.assertIn("p_value", result)
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

    def test_excludes_unsettled(self):
        """Unsettled trades (result=NULL) are excluded from streak analysis."""
        from trade_reflector import TradeReflector
        trades = _make_trades(20)
        # Add some unsettled trades
        for i in range(5):
            ts = datetime(2026, 3, 15, 10 + i, tzinfo=timezone.utc).timestamp()
            trades.append({
                "ticker": "UNSETTLED", "strategy": "s", "result": None,
                "pnl_cents": None, "side": "yes", "action": "buy",
                "count": 1, "created_at": ts, "timestamp": ts,
                "edge_pct": 0.1, "cost_usd": 5.0, "price_cents": 70,
            })
        db_path = _create_test_db(trades)
        try:
            tr = TradeReflector(db_path)
            result = tr.streak_analysis()
            # Should only count yes/no results, not NULLs
            self.assertEqual(result["total_trades"], 20)
        finally:
            os.unlink(db_path)


class TestEdgeTrend(unittest.TestCase):
    """Tests for edge_trend() — rolling window edge_pct analysis."""

    def test_detects_declining_edge(self):
        """Detects declining edge when edge_pct trends downward."""
        from trade_reflector import TradeReflector
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
        ts_base = datetime(2026, 3, 1, 10, tzinfo=timezone.utc).timestamp()
        trades = [{"ticker": "T", "strategy": "s", "result": "yes",
                   "pnl_cents": 100, "side": "yes", "action": "buy",
                   "count": 1, "created_at": ts_base + i * 3600,
                   "timestamp": ts_base + i * 3600,
                   "cost_usd": 5.0, "price_cents": 70}
                  for i in range(35)]
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
        trades = _make_trades(30, win_rate=0.60, cost_range=(8.0, 12.0),
                              price_range=(50, 60))
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
        """Returns None when cost/price columns don't exist."""
        from trade_reflector import TradeReflector
        ts_base = datetime(2026, 3, 1, 10, tzinfo=timezone.utc).timestamp()
        trades = [{"ticker": "T", "strategy": "s", "result": "yes",
                   "pnl_cents": 100, "side": "yes", "action": "buy",
                   "count": 1, "created_at": ts_base + i * 3600,
                   "timestamp": ts_base + i * 3600,
                   "edge_pct": 0.1}
                  for i in range(25)]
        db_path = _create_test_db(trades, include_cost=False, include_price=False)
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
        ts_base = datetime(2026, 3, 1, 10, tzinfo=timezone.utc).timestamp()
        trades = [{"ticker": "T", "strategy": "s", "result": "yes",
                   "pnl_cents": 100, "side": "yes", "action": "buy",
                   "count": 1, "created_at": ts_base + i * 3600}
                  for i in range(60)]
        db_path = _create_test_db(trades, include_edge=False, include_timestamp=False,
                                  include_cost=False, include_price=False)
        try:
            tr = TradeReflector(db_path)
            report = tr.analyze()
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
                           base_time=datetime(2026, 5, 10, tzinfo=timezone.utc))
        db_path = _create_test_db(good + bad)
        try:
            tr = TradeReflector(db_path)
            proposals = tr.generate_proposals()
            self.assertIsInstance(proposals, list)
            drift_proposals = [p for p in proposals if p["pattern"] == "win_rate_drift"]
            self.assertGreater(len(drift_proposals), 0)
        finally:
            os.unlink(db_path)

    def test_proposal_format(self):
        """Each proposal has the required fields."""
        from trade_reflector import TradeReflector
        good = _make_trades(50, win_rate=0.90, strategy="s")
        bad = _make_trades(25, win_rate=0.40, strategy="s",
                           base_time=datetime(2026, 5, 10, tzinfo=timezone.utc))
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
                           base_time=datetime(2026, 5, 10, tzinfo=timezone.utc))
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
                           base_time=datetime(2026, 5, 10, tzinfo=timezone.utc))
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
                           base_time=datetime(2026, 5, 10, tzinfo=timezone.utc))
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
                           base_time=datetime(2026, 5, 10, tzinfo=timezone.utc))
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
