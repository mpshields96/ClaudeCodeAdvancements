"""Tests for kalshi_data_collector.py — MT-33 Phase 2: Kalshi financial data extraction.

Uses in-memory SQLite with the real polybot.db schema. No external DB needed.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kalshi_data_collector import KalshiDataCollector


def _create_test_db(path):
    """Create a test DB with the real polybot.db schema."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            ticker TEXT NOT NULL,
            side TEXT NOT NULL,
            action TEXT NOT NULL,
            price_cents INTEGER NOT NULL,
            count INTEGER NOT NULL,
            cost_usd REAL NOT NULL,
            strategy TEXT DEFAULT 'btc_lag',
            edge_pct REAL,
            win_prob REAL,
            is_paper INTEGER NOT NULL DEFAULT 1,
            client_order_id TEXT,
            server_order_id TEXT,
            result TEXT,
            pnl_cents INTEGER,
            settled_at REAL,
            created_at REAL,
            signal_price_cents INTEGER,
            exit_price_cents INTEGER,
            kalshi_fee_cents INTEGER,
            gross_profit_cents INTEGER,
            tax_basis_usd REAL,
            signal_features TEXT
        );
        CREATE TABLE daily_pnl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            starting_bankroll REAL,
            realized_pnl_usd REAL DEFAULT 0.0,
            fees_usd REAL DEFAULT 0.0,
            num_trades INTEGER DEFAULT 0,
            num_wins INTEGER DEFAULT 0,
            is_paper INTEGER DEFAULT 1,
            created_at REAL,
            updated_at REAL
        );
        CREATE TABLE bankroll_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            balance_usd REAL NOT NULL,
            source TEXT DEFAULT 'api',
            created_at REAL
        );
        CREATE TABLE kill_switch_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            trigger_type TEXT NOT NULL,
            reason TEXT NOT NULL,
            bankroll_at_trigger REAL,
            created_at REAL
        );
    """)
    conn.close()


def _ts(date_str):
    """Convert 'YYYY-MM-DD' to unix timestamp."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    ).timestamp()


def _insert_trade(conn, ts, ticker, strategy, is_paper, price_cents, count,
                  result=None, pnl_cents=None, side="yes", action="buy",
                  edge_pct=None, win_prob=None):
    """Insert a trade row."""
    cost = price_cents / 100.0 * count
    conn.execute(
        """INSERT INTO trades (timestamp, ticker, side, action, price_cents,
           count, cost_usd, strategy, edge_pct, win_prob, is_paper, result,
           pnl_cents, settled_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts, ticker, side, action, price_cents, count, cost, strategy,
         edge_pct, win_prob, is_paper, result, pnl_cents,
         ts + 3600 if result else None, ts)
    )


def _insert_bankroll(conn, ts, balance, source="api"):
    """Insert a bankroll history row."""
    conn.execute(
        "INSERT INTO bankroll_history (timestamp, balance_usd, source, created_at) VALUES (?, ?, ?, ?)",
        (ts, balance, source, ts)
    )


class TestKalshiDataCollectorInit(unittest.TestCase):
    """Test initialization and DB detection."""

    def test_init_with_valid_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            _create_test_db(f.name)
            try:
                c = KalshiDataCollector(f.name)
                self.assertEqual(c.db_path, f.name)
                self.assertTrue(c.is_available())
            finally:
                os.unlink(f.name)

    def test_init_with_missing_db(self):
        c = KalshiDataCollector("/nonexistent/path.db")
        self.assertFalse(c.is_available())

    def test_init_with_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            pass  # 0-byte file
        try:
            c = KalshiDataCollector(f.name)
            self.assertFalse(c.is_available())
        finally:
            os.unlink(f.name)

    def test_default_db_path(self):
        c = KalshiDataCollector()
        # Should use default path
        self.assertIn("polybot.db", c.db_path)


class TestTradeStats(unittest.TestCase):
    """Test trade statistics extraction."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        _create_test_db(self.tmpfile.name)
        self.conn = sqlite3.connect(self.tmpfile.name)
        # Insert test trades
        _insert_trade(self.conn, _ts("2026-03-10"), "BTC-1", "sniper_v1", 0, 20, 5, "yes", 400)
        _insert_trade(self.conn, _ts("2026-03-10"), "BTC-2", "sniper_v1", 0, 25, 3, "yes", 225)
        _insert_trade(self.conn, _ts("2026-03-11"), "BTC-3", "sniper_v1", 0, 30, 4, "no", -120)
        _insert_trade(self.conn, _ts("2026-03-11"), "ETH-1", "drift_v1", 0, 45, 2, "yes", 110)
        _insert_trade(self.conn, _ts("2026-03-12"), "ETH-2", "drift_v1", 0, 50, 3, "no", -150)
        _insert_trade(self.conn, _ts("2026-03-12"), "SOL-1", "drift_v1", 0, 40, 2)  # unsettled
        # Paper trades (should be excluded from live stats)
        _insert_trade(self.conn, _ts("2026-03-10"), "PAPER-1", "sniper_v1", 1, 20, 5, "yes", 500)
        self.conn.commit()
        self.collector = KalshiDataCollector(self.tmpfile.name)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmpfile.name)

    def test_total_trades(self):
        stats = self.collector.get_trade_summary()
        self.assertEqual(stats["total_live_trades"], 6)
        self.assertEqual(stats["total_paper_trades"], 1)

    def test_settled_count(self):
        stats = self.collector.get_trade_summary()
        self.assertEqual(stats["settled_trades"], 5)
        self.assertEqual(stats["unsettled_trades"], 1)

    def test_win_loss(self):
        stats = self.collector.get_trade_summary()
        self.assertEqual(stats["wins"], 3)
        self.assertEqual(stats["losses"], 2)

    def test_total_pnl(self):
        stats = self.collector.get_trade_summary()
        # 400 + 225 - 120 + 110 - 150 = 465 cents = $4.65
        self.assertAlmostEqual(stats["total_pnl_usd"], 4.65)

    def test_win_rate(self):
        stats = self.collector.get_trade_summary()
        # 3 wins / 5 settled = 60%
        self.assertAlmostEqual(stats["win_rate_pct"], 60.0)

    def test_date_range(self):
        stats = self.collector.get_trade_summary()
        self.assertIn("2026-03-10", stats["first_trade_date"])
        self.assertIn("2026-03-12", stats["last_trade_date"])


class TestStrategyBreakdown(unittest.TestCase):
    """Test per-strategy analytics."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        _create_test_db(self.tmpfile.name)
        self.conn = sqlite3.connect(self.tmpfile.name)
        # sniper: 3 wins, 1 loss
        for i in range(3):
            _insert_trade(self.conn, _ts("2026-03-10") + i, f"S-{i}", "sniper_v1", 0, 20, 5, "yes", 400)
        _insert_trade(self.conn, _ts("2026-03-11"), "S-3", "sniper_v1", 0, 30, 4, "no", -120)
        # drift: 1 win, 2 losses
        _insert_trade(self.conn, _ts("2026-03-11"), "D-1", "drift_v1", 0, 45, 2, "yes", 110)
        for i in range(2):
            _insert_trade(self.conn, _ts("2026-03-12") + i, f"D-{i+2}", "drift_v1", 0, 50, 3, "no", -150)
        self.conn.commit()
        self.collector = KalshiDataCollector(self.tmpfile.name)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmpfile.name)

    def test_strategy_count(self):
        breakdown = self.collector.get_strategy_breakdown()
        self.assertEqual(len(breakdown), 2)

    def test_strategy_win_rate(self):
        breakdown = self.collector.get_strategy_breakdown()
        by_name = {s["strategy"]: s for s in breakdown}
        self.assertAlmostEqual(by_name["sniper_v1"]["win_rate_pct"], 75.0)
        self.assertAlmostEqual(by_name["drift_v1"]["win_rate_pct"], 33.3, places=1)

    def test_strategy_pnl(self):
        breakdown = self.collector.get_strategy_breakdown()
        by_name = {s["strategy"]: s for s in breakdown}
        # sniper: 400*3 - 120 = 1080 cents = $10.80
        self.assertAlmostEqual(by_name["sniper_v1"]["total_pnl_usd"], 10.80)
        # drift: 110 - 150*2 = -190 cents = -$1.90
        self.assertAlmostEqual(by_name["drift_v1"]["total_pnl_usd"], -1.90)

    def test_strategy_sorted_by_pnl(self):
        breakdown = self.collector.get_strategy_breakdown()
        pnls = [s["total_pnl_usd"] for s in breakdown]
        self.assertEqual(pnls, sorted(pnls, reverse=True))

    def test_strategy_trade_count(self):
        breakdown = self.collector.get_strategy_breakdown()
        by_name = {s["strategy"]: s for s in breakdown}
        self.assertEqual(by_name["sniper_v1"]["trade_count"], 4)
        self.assertEqual(by_name["drift_v1"]["trade_count"], 3)


class TestDailyPnL(unittest.TestCase):
    """Test daily P&L aggregation."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        _create_test_db(self.tmpfile.name)
        self.conn = sqlite3.connect(self.tmpfile.name)
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "s", 0, 20, 5, "yes", 400)
        _insert_trade(self.conn, _ts("2026-03-10") + 1, "B", "s", 0, 25, 3, "no", -100)
        _insert_trade(self.conn, _ts("2026-03-11"), "C", "s", 0, 30, 4, "yes", 200)
        self.conn.commit()
        self.collector = KalshiDataCollector(self.tmpfile.name)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmpfile.name)

    def test_daily_pnl_count(self):
        daily = self.collector.get_daily_pnl()
        self.assertEqual(len(daily), 2)

    def test_daily_pnl_values(self):
        daily = self.collector.get_daily_pnl()
        by_date = {d["date"]: d for d in daily}
        # Day 1: 400 - 100 = 300 cents = $3.00
        self.assertAlmostEqual(by_date["2026-03-10"]["pnl_usd"], 3.00)
        # Day 2: 200 cents = $2.00
        self.assertAlmostEqual(by_date["2026-03-11"]["pnl_usd"], 2.00)

    def test_daily_cumulative(self):
        daily = self.collector.get_daily_pnl()
        self.assertAlmostEqual(daily[0]["cumulative_pnl_usd"], 3.00)
        self.assertAlmostEqual(daily[1]["cumulative_pnl_usd"], 5.00)

    def test_daily_trade_count(self):
        daily = self.collector.get_daily_pnl()
        by_date = {d["date"]: d for d in daily}
        self.assertEqual(by_date["2026-03-10"]["trade_count"], 2)
        self.assertEqual(by_date["2026-03-11"]["trade_count"], 1)


class TestBankrollHistory(unittest.TestCase):
    """Test bankroll timeline extraction."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        _create_test_db(self.tmpfile.name)
        self.conn = sqlite3.connect(self.tmpfile.name)
        base = _ts("2026-03-10")
        for i in range(100):
            _insert_bankroll(self.conn, base + i * 60, 100.0 + i * 0.5)
        self.conn.commit()
        self.collector = KalshiDataCollector(self.tmpfile.name)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmpfile.name)

    def test_bankroll_returns_data(self):
        data = self.collector.get_bankroll_history(max_points=50)
        self.assertGreater(len(data), 0)
        self.assertLessEqual(len(data), 50)

    def test_bankroll_downsampled(self):
        data = self.collector.get_bankroll_history(max_points=10)
        self.assertLessEqual(len(data), 10)

    def test_bankroll_has_fields(self):
        data = self.collector.get_bankroll_history()
        entry = data[0]
        self.assertIn("timestamp", entry)
        self.assertIn("balance_usd", entry)

    def test_bankroll_sorted(self):
        data = self.collector.get_bankroll_history()
        timestamps = [d["timestamp"] for d in data]
        self.assertEqual(timestamps, sorted(timestamps))


class TestChartData(unittest.TestCase):
    """Test chart-ready data generation methods."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        _create_test_db(self.tmpfile.name)
        self.conn = sqlite3.connect(self.tmpfile.name)
        strategies = ["sniper_v1", "drift_v1", "orderbook_v1"]
        for i, s in enumerate(strategies):
            for j in range(5):
                pnl = 200 if j < 3 else -100
                result = "yes" if j < 3 else "no"
                _insert_trade(self.conn, _ts("2026-03-10") + i * 1000 + j,
                              f"T-{i}-{j}", s, 0, 20 + i * 5, 3, result, pnl)
        self.conn.commit()
        self.collector = KalshiDataCollector(self.tmpfile.name)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmpfile.name)

    def test_cumulative_pnl_chart_data(self):
        data = self.collector.chart_cumulative_pnl()
        self.assertIn("labels", data)
        self.assertIn("values", data)
        self.assertEqual(len(data["labels"]), len(data["values"]))
        # Should be monotonically computed
        self.assertIsInstance(data["values"][-1], float)

    def test_strategy_winrate_chart_data(self):
        data = self.collector.chart_strategy_winrate()
        self.assertIn("labels", data)
        self.assertIn("values", data)
        self.assertEqual(len(data["labels"]), 3)
        for v in data["values"]:
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 100)

    def test_daily_pnl_histogram_data(self):
        data = self.collector.chart_daily_pnl_values()
        self.assertIn("values", data)
        self.assertGreater(len(data["values"]), 0)

    def test_strategy_pnl_box_data(self):
        data = self.collector.chart_strategy_pnl_distribution()
        self.assertIn("categories", data)
        self.assertIn("data_series", data)
        self.assertEqual(len(data["categories"]), len(data["data_series"]))

    def test_winrate_vs_profit_scatter(self):
        data = self.collector.chart_winrate_vs_profit()
        self.assertIn("series", data)
        self.assertEqual(len(data["series"]), 1)  # one series
        points = data["series"][0]["data"]
        self.assertGreater(len(points), 0)
        for p in points:
            self.assertIn("x", p)
            self.assertIn("y", p)
            self.assertIn("label", p)

    def test_trade_volume_donut(self):
        data = self.collector.chart_trade_volume()
        self.assertIn("labels", data)
        self.assertIn("values", data)
        self.assertEqual(sum(data["values"]), 15)  # 3 strategies * 5 trades

    def test_bankroll_area_chart(self):
        base = _ts("2026-03-10")
        for i in range(20):
            _insert_bankroll(self.conn, base + i * 3600, 100.0 + i)
        self.conn.commit()
        data = self.collector.chart_bankroll_timeline()
        self.assertIn("labels", data)
        self.assertIn("values", data)
        self.assertGreater(len(data["values"]), 0)


class TestEmptyDB(unittest.TestCase):
    """Test graceful handling of empty database."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        _create_test_db(self.tmpfile.name)
        self.collector = KalshiDataCollector(self.tmpfile.name)

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_empty_trade_summary(self):
        stats = self.collector.get_trade_summary()
        self.assertEqual(stats["total_live_trades"], 0)
        self.assertEqual(stats["wins"], 0)
        self.assertIsNone(stats["win_rate_pct"])

    def test_empty_strategy_breakdown(self):
        breakdown = self.collector.get_strategy_breakdown()
        self.assertEqual(len(breakdown), 0)

    def test_empty_daily_pnl(self):
        daily = self.collector.get_daily_pnl()
        self.assertEqual(len(daily), 0)

    def test_empty_bankroll(self):
        data = self.collector.get_bankroll_history()
        self.assertEqual(len(data), 0)

    def test_empty_chart_data(self):
        data = self.collector.chart_cumulative_pnl()
        self.assertEqual(len(data["labels"]), 0)


class TestCollectAll(unittest.TestCase):
    """Test the collect_all() aggregator for report integration."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        _create_test_db(self.tmpfile.name)
        self.conn = sqlite3.connect(self.tmpfile.name)
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "sniper", 0, 20, 5, "yes", 400)
        _insert_bankroll(self.conn, _ts("2026-03-10"), 100.0)
        self.conn.commit()
        self.collector = KalshiDataCollector(self.tmpfile.name)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmpfile.name)

    def test_collect_all_keys(self):
        data = self.collector.collect_all()
        self.assertIn("summary", data)
        self.assertIn("strategies", data)
        self.assertIn("daily_pnl", data)
        self.assertIn("bankroll", data)
        self.assertIn("charts", data)
        self.assertIn("available", data)
        self.assertTrue(data["available"])

    def test_collect_all_charts_keys(self):
        data = self.collector.collect_all()
        charts = data["charts"]
        self.assertIn("cumulative_pnl", charts)
        self.assertIn("strategy_winrate", charts)
        self.assertIn("daily_pnl_histogram", charts)
        self.assertIn("strategy_pnl_distribution", charts)
        self.assertIn("winrate_vs_profit", charts)
        self.assertIn("trade_volume", charts)
        self.assertIn("bankroll_timeline", charts)

    def test_collect_all_serializable(self):
        data = self.collector.collect_all()
        # Must be JSON-serializable for Typst pipeline
        json_str = json.dumps(data)
        self.assertIsInstance(json_str, str)


class TestUnavailableDB(unittest.TestCase):
    """Test collect_all when DB is not available."""

    def test_collect_all_unavailable(self):
        c = KalshiDataCollector("/nonexistent.db")
        data = c.collect_all()
        self.assertFalse(data["available"])
        self.assertEqual(data["summary"]["total_live_trades"], 0)


class TestEdgeCases(unittest.TestCase):
    """Hardening tests for edge cases (MT-33 hardening)."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        _create_test_db(self.tmpfile.name)
        self.conn = sqlite3.connect(self.tmpfile.name)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmpfile.name)

    def test_paper_only_trades(self):
        """Summary shows 0 live trades when all trades are paper."""
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "sniper", 1, 20, 5, "yes", 400)
        _insert_trade(self.conn, _ts("2026-03-11"), "B", "sniper", 1, 30, 3, "no", -300)
        self.conn.commit()
        c = KalshiDataCollector(self.tmpfile.name)
        summary = c.get_trade_summary()
        self.assertEqual(summary["total_live_trades"], 0)
        self.assertEqual(summary["total_paper_trades"], 2)
        self.assertEqual(summary["total_pnl_usd"], 0.0)

    def test_all_unsettled_trades(self):
        """Win rate is None when no trades have settled."""
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "sniper", 0, 20, 5)
        _insert_trade(self.conn, _ts("2026-03-11"), "B", "sniper", 0, 30, 3)
        self.conn.commit()
        c = KalshiDataCollector(self.tmpfile.name)
        summary = c.get_trade_summary()
        self.assertEqual(summary["settled_trades"], 0)
        self.assertEqual(summary["unsettled_trades"], 2)
        self.assertIsNone(summary["win_rate_pct"])

    def test_single_trade_strategy_breakdown(self):
        """Strategy breakdown works with exactly one trade."""
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "sniper", 0, 20, 5, "yes", 400)
        self.conn.commit()
        c = KalshiDataCollector(self.tmpfile.name)
        strategies = c.get_strategy_breakdown()
        self.assertEqual(len(strategies), 1)
        self.assertEqual(strategies[0]["strategy"], "sniper")
        self.assertEqual(strategies[0]["wins"], 1)
        self.assertEqual(strategies[0]["win_rate_pct"], 100.0)

    def test_all_losses(self):
        """Win rate is 0% when all trades are losses."""
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "sniper", 0, 20, 5, "no", -500)
        _insert_trade(self.conn, _ts("2026-03-11"), "B", "sniper", 0, 30, 3, "no", -300)
        self.conn.commit()
        c = KalshiDataCollector(self.tmpfile.name)
        summary = c.get_trade_summary()
        self.assertEqual(summary["win_rate_pct"], 0.0)
        self.assertEqual(summary["wins"], 0)
        self.assertEqual(summary["losses"], 2)

    def test_zero_pnl_counted_as_loss(self):
        """Trade with pnl_cents=0 is counted as a loss (not a win)."""
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "sniper", 0, 20, 5, "yes", 0)
        self.conn.commit()
        c = KalshiDataCollector(self.tmpfile.name)
        summary = c.get_trade_summary()
        self.assertEqual(summary["wins"], 0)
        self.assertEqual(summary["losses"], 1)

    def test_bankroll_single_entry(self):
        """Bankroll with exactly one entry returns it."""
        _insert_bankroll(self.conn, _ts("2026-03-10"), 100.0)
        self.conn.commit()
        c = KalshiDataCollector(self.tmpfile.name)
        history = c.get_bankroll_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["balance_usd"], 100.0)

    def test_daily_pnl_single_day(self):
        """Daily P&L with all trades on same day."""
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "sniper", 0, 20, 5, "yes", 400)
        _insert_trade(self.conn, _ts("2026-03-10") + 3600, "B", "sniper", 0, 30, 3, "no", -300)
        self.conn.commit()
        c = KalshiDataCollector(self.tmpfile.name)
        daily = c.get_daily_pnl()
        self.assertEqual(len(daily), 1)
        self.assertAlmostEqual(daily[0]["pnl_usd"], 1.0)  # (400-300)/100
        self.assertAlmostEqual(daily[0]["cumulative_pnl_usd"], 1.0)

    def test_scatter_no_settled_strategies(self):
        """Scatter chart empty when no strategies have settled trades."""
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "sniper", 0, 20, 5)
        self.conn.commit()
        c = KalshiDataCollector(self.tmpfile.name)
        data = c.chart_winrate_vs_profit()
        # Strategy has 0 settled trades, win_rate_pct=0.0 (not None), so point exists
        self.assertIn("series", data)

    def test_collect_all_json_serializable_with_all_edge_cases(self):
        """collect_all is JSON-serializable even with edge-case data."""
        _insert_trade(self.conn, _ts("2026-03-10"), "A", "sniper", 0, 20, 5)  # unsettled
        _insert_trade(self.conn, _ts("2026-03-11"), "B", "bayesian", 1, 10, 2, "yes", 0)  # paper, zero pnl
        self.conn.commit()
        c = KalshiDataCollector(self.tmpfile.name)
        data = c.collect_all()
        json_str = json.dumps(data)
        self.assertIsInstance(json_str, str)


if __name__ == "__main__":
    unittest.main()
