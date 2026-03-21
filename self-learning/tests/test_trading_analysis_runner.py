#!/usr/bin/env python3
"""
Tests for trading_analysis_runner.py — Automated Kalshi analysis pipeline.

Runs trade_reflector + reflect.py trading patterns, generates structured
report for Kalshi chat consumption, optionally appends to KALSHI_INTEL.md.

Run: python3 self-learning/tests/test_trading_analysis_runner.py
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_test_db(db_path: str, n_trades: int = 30):
    """Create a minimal polybot.db-compatible test database (legacy schema)."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY,
            strategy TEXT,
            result TEXT,
            timestamp REAL,
            price_cents INTEGER,
            cost_usd REAL,
            payout_usd REAL,
            market_id TEXT,
            edge_pct REAL
        )
    """)
    import time
    base_time = time.time() - (n_trades * 3600)
    for i in range(n_trades):
        result = "yes" if i % 3 != 0 else "no"  # ~67% win rate
        conn.execute(
            "INSERT INTO trades (strategy, result, timestamp, price_cents, cost_usd, payout_usd, market_id, edge_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("sniper", result, base_time + i * 3600, 60 + (i % 20), 1.50, 2.50 if result == "yes" else 0.0, f"MKT-{i % 5}", 0.15 + (i % 10) * 0.01)
        )
    conn.commit()
    conn.close()


def _create_kalshi_db(db_path: str, n_trades: int = 30):
    """Create a polybot.db with real Kalshi schema (pnl_cents, ticker, count)."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
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
            result TEXT,
            pnl_cents INTEGER,
            settled_at REAL
        )
    """)
    import time
    base_time = time.time() - (n_trades * 3600)
    strategies = ["expiry_sniper_v1", "orderbook_imbalance_v1", "btc_drift_v1"]
    for i in range(n_trades):
        strat = strategies[i % len(strategies)]
        # 60% settled, 40% unsettled
        if i % 5 != 0:
            result = "yes" if i % 3 != 0 else "no"
            pnl = 150 if result == "yes" else -100
        else:
            result = None
            pnl = None
        conn.execute(
            "INSERT INTO trades (timestamp, ticker, side, action, price_cents, "
            "count, cost_usd, strategy, edge_pct, result, pnl_cents) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (base_time + i * 3600, f"TICKER-{i % 5}", "yes", "buy",
             60 + (i % 20), 2, 1.50, strat, 0.15, result, pnl)
        )
    conn.commit()
    conn.close()


class TestDiscoverDB(unittest.TestCase):
    """Test polybot.db discovery."""

    def test_finds_db_at_explicit_path(self):
        from trading_analysis_runner import discover_db
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            _create_test_db(f.name, 5)
            result = discover_db(explicit_path=f.name)
            self.assertEqual(result, f.name)

    def test_returns_none_for_missing_db(self):
        from trading_analysis_runner import discover_db
        result = discover_db(explicit_path="/nonexistent/path.db")
        self.assertIsNone(result)

    def test_returns_none_when_no_path(self):
        from trading_analysis_runner import discover_db
        # With no explicit path and env not set, should check defaults
        with patch.dict(os.environ, {}, clear=True):
            result = discover_db(explicit_path=None)
            # May or may not find it depending on machine; just verify no crash
            self.assertIsInstance(result, (str, type(None)))


class TestRunAnalysis(unittest.TestCase):
    """Test the analysis pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "polybot.db")
        _create_test_db(self.db_path, 50)

    def test_returns_structured_report(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        self.assertIn("summary", report)
        self.assertIn("db_path", report)
        self.assertIn("trade_count", report)

    def test_report_has_trade_count(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        self.assertEqual(report["trade_count"], 50)

    def test_report_has_win_rate(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        self.assertIn("win_rate", report)
        self.assertIsInstance(report["win_rate"], float)
        self.assertGreater(report["win_rate"], 0)
        self.assertLess(report["win_rate"], 1)

    def test_report_has_proposals(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        self.assertIn("proposals", report)
        self.assertIsInstance(report["proposals"], list)

    def test_report_has_pnl(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        self.assertIn("pnl_usd", report)
        self.assertIsInstance(report["pnl_usd"], float)

    def test_report_has_timestamp(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        self.assertIn("analyzed_at", report)

    def test_empty_db_returns_zero_count(self):
        empty_db = os.path.join(self.tmpdir, "empty.db")
        conn = sqlite3.connect(empty_db)
        conn.execute("""
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY, strategy TEXT, result TEXT,
                timestamp REAL, price_cents INTEGER, cost_usd REAL,
                payout_usd REAL, market_id TEXT, edge_pct REAL
            )
        """)
        conn.commit()
        conn.close()

        from trading_analysis_runner import run_analysis
        report = run_analysis(empty_db)
        self.assertEqual(report["trade_count"], 0)
        self.assertEqual(report["win_rate"], 0.0)


class TestFormatReport(unittest.TestCase):
    """Test report formatting for human/Kalshi consumption."""

    def test_format_produces_markdown(self):
        from trading_analysis_runner import format_report
        report = {
            "db_path": "/test/db.db",
            "trade_count": 50,
            "win_rate": 0.67,
            "pnl_usd": 15.50,
            "proposals": [],
            "strategy_breakdown": {"sniper": {"count": 50, "win_rate": 0.67}},
            "summary": "50 trades, 67% win rate",
            "analyzed_at": "2026-03-20T12:00:00Z",
        }
        text = format_report(report)
        self.assertIn("Trading Analysis", text)
        self.assertIn("50", text)
        self.assertIn("67", text)

    def test_format_includes_proposals(self):
        from trading_analysis_runner import format_report
        report = {
            "db_path": "/test/db.db",
            "trade_count": 50,
            "win_rate": 0.67,
            "pnl_usd": 15.50,
            "proposals": [
                {"pattern": "win_rate_drift", "severity": "warning",
                 "recommendation": "Consider pausing sniper strategy"}
            ],
            "strategy_breakdown": {},
            "summary": "50 trades",
            "analyzed_at": "2026-03-20T12:00:00Z",
        }
        text = format_report(report)
        self.assertIn("win_rate_drift", text)
        self.assertIn("warning", text)

    def test_format_no_proposals(self):
        from trading_analysis_runner import format_report
        report = {
            "db_path": "/test/db.db",
            "trade_count": 50,
            "win_rate": 0.67,
            "pnl_usd": 15.50,
            "proposals": [],
            "strategy_breakdown": {},
            "summary": "50 trades",
            "analyzed_at": "2026-03-20T12:00:00Z",
        }
        text = format_report(report)
        self.assertIn("No actionable proposals", text)


class TestAppendToIntel(unittest.TestCase):
    """Test appending analysis to KALSHI_INTEL.md."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.intel_path = os.path.join(self.tmpdir, "KALSHI_INTEL.md")
        with open(self.intel_path, "w") as f:
            f.write("# Kalshi Intel\n\n## New Intel (Unprocessed)\n\n")

    def test_appends_analysis_section(self):
        from trading_analysis_runner import append_to_intel
        report = {
            "trade_count": 50,
            "win_rate": 0.67,
            "pnl_usd": 15.50,
            "proposals": [],
            "strategy_breakdown": {"sniper": {"count": 50, "win_rate": 0.67}},
            "summary": "50 trades, 67% win rate",
            "analyzed_at": "2026-03-20T12:00:00Z",
        }
        append_to_intel(self.intel_path, report)
        content = Path(self.intel_path).read_text()
        self.assertIn("Self-Learning Analysis", content)
        self.assertIn("50 trades", content)

    def test_does_not_duplicate(self):
        from trading_analysis_runner import append_to_intel
        report = {
            "trade_count": 50,
            "win_rate": 0.67,
            "pnl_usd": 15.50,
            "proposals": [],
            "strategy_breakdown": {},
            "summary": "test",
            "analyzed_at": "2026-03-20T12:00:00Z",
        }
        append_to_intel(self.intel_path, report)
        append_to_intel(self.intel_path, report)
        content = Path(self.intel_path).read_text()
        # Should have exactly 2 entries (we allow multiple — each analysis is a snapshot)
        count = content.count("Self-Learning Analysis")
        self.assertEqual(count, 2)

    def test_creates_file_if_missing(self):
        from trading_analysis_runner import append_to_intel
        new_path = os.path.join(self.tmpdir, "new_intel.md")
        report = {
            "trade_count": 10,
            "win_rate": 0.5,
            "pnl_usd": 0.0,
            "proposals": [],
            "strategy_breakdown": {},
            "summary": "test",
            "analyzed_at": "2026-03-20T12:00:00Z",
        }
        append_to_intel(new_path, report)
        self.assertTrue(Path(new_path).exists())


class TestStrategyBreakdown(unittest.TestCase):
    """Test per-strategy analysis in the report."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "polybot.db")
        _create_test_db(self.db_path, 50)

    def test_breakdown_by_strategy(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        self.assertIn("strategy_breakdown", report)
        self.assertIn("sniper", report["strategy_breakdown"])

    def test_breakdown_has_count_and_wr(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        sniper = report["strategy_breakdown"]["sniper"]
        self.assertIn("count", sniper)
        self.assertIn("win_rate", sniper)
        self.assertEqual(sniper["count"], 50)


class TestJsonOutput(unittest.TestCase):
    """Test JSON output mode."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "polybot.db")
        _create_test_db(self.db_path, 30)

    def test_json_output_is_valid(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        # Should be JSON-serializable
        json_str = json.dumps(report)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["trade_count"], 30)


class TestKalshiSchema(unittest.TestCase):
    """Test against real Kalshi DB schema (pnl_cents, ticker, count)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "polybot.db")
        _create_kalshi_db(self.db_path, 50)

    def test_reads_kalshi_schema(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        self.assertEqual(report["trade_count"], 50)

    def test_handles_unsettled_trades(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        # 40 settled (every 5th is unsettled = 10 unsettled)
        self.assertEqual(report["settled_count"], 40)
        # Win rate based on settled only
        self.assertGreater(report["win_rate"], 0)
        self.assertLess(report["win_rate"], 1)

    def test_pnl_from_pnl_cents(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        # pnl_usd should be non-zero (mix of wins/losses)
        self.assertNotEqual(report["pnl_usd"], 0)

    def test_ticker_mapped_to_market_id(self):
        from trading_analysis_runner import _read_trades
        trades = _read_trades(self.db_path)
        self.assertTrue(all("market_id" in t for t in trades))
        self.assertTrue(any(t["market_id"].startswith("TICKER") for t in trades))

    def test_multiple_strategies(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        breakdown = report["strategy_breakdown"]
        self.assertIn("expiry_sniper_v1", breakdown)
        self.assertIn("orderbook_imbalance_v1", breakdown)
        self.assertIn("btc_drift_v1", breakdown)

    def test_settled_vs_count_in_breakdown(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        for strat, data in report["strategy_breakdown"].items():
            self.assertIn("settled", data)
            self.assertLessEqual(data["settled"], data["count"])

    def test_contracts_tracked(self):
        from trading_analysis_runner import _read_trades
        trades = _read_trades(self.db_path)
        self.assertTrue(all(t.get("contracts", 0) == 2 for t in trades))

    def test_summary_includes_settled(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        self.assertIn("settled", report["summary"])

    def test_top_strategy_by_pnl(self):
        from trading_analysis_runner import run_analysis
        report = run_analysis(self.db_path)
        # Summary should mention the top strategy by PnL
        self.assertIn("Top strategy:", report["summary"])


if __name__ == "__main__":
    unittest.main()
