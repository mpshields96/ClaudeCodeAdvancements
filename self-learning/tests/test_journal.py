#!/usr/bin/env python3
"""
test_journal.py — Dedicated test suite for self-learning/journal.py

Tests the full public API of journal.py:
- log_event: JSONL format, field validation, None stripping, strategy version
- get_stats: aggregation across event types, domains, outcomes, sessions, learnings
- get_recent: order and count
- get_entries_by_domain: filtering
- get_all_learnings: cross-entry extraction
- get_nuclear_metrics: aggregation + rate computation
- get_trading_metrics: win/loss/pnl, market type, strategy, research effectiveness
- get_time_stratified_trading_metrics: hourly bucketing, overnight vs daytime
- get_pain_win_summary: ratio + domain counters
- Edge cases: empty journal, corrupt lines, unknown event types
"""

import json
import os
import sys
import tempfile
import unittest

# Add parent directory so `import journal` works
SELF_LEARNING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SELF_LEARNING_DIR)
import journal as J


class JournalTestBase(unittest.TestCase):
    """Redirect journal reads/writes to a temp file for test isolation."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self._orig_journal = J.JOURNAL_PATH
        self._orig_strategy = J.STRATEGY_PATH
        J.JOURNAL_PATH = self.tmp.name
        # Use a strategy path that doesn't exist → empty strategy (version 0)
        self.strategy_tmp = self.tmp.name + ".strategy.json"
        J.STRATEGY_PATH = self.strategy_tmp

    def tearDown(self):
        J.JOURNAL_PATH = self._orig_journal
        J.STRATEGY_PATH = self._orig_strategy
        os.unlink(self.tmp.name)
        if os.path.exists(self.strategy_tmp):
            os.unlink(self.strategy_tmp)

    def _write_raw(self, obj):
        """Write a raw JSON object directly to the journal file."""
        with open(J.JOURNAL_PATH, "a") as f:
            f.write(json.dumps(obj) + "\n")


# ---------------------------------------------------------------------------
# log_event
# ---------------------------------------------------------------------------

class TestLogEvent(JournalTestBase):

    def test_creates_jsonl_file(self):
        """log_event appends to the journal file and produces valid JSON."""
        J.log_event("session_outcome", session_id=1, domain="general")
        with open(J.JOURNAL_PATH) as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["event_type"], "session_outcome")

    def test_appends_multiple_entries(self):
        """Each log_event call appends a new line (append-only)."""
        J.log_event("session_outcome", session_id=1)
        J.log_event("session_outcome", session_id=2)
        J.log_event("nuclear_batch", session_id=3)
        with open(J.JOURNAL_PATH) as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 3)

    def test_returns_entry_dict(self):
        """log_event returns the entry dict that was written."""
        entry = J.log_event("win", domain="agent_guard", notes="Bash guard caught evasion")
        self.assertIsInstance(entry, dict)
        self.assertEqual(entry["event_type"], "win")
        self.assertEqual(entry["domain"], "agent_guard")

    def test_strips_none_values(self):
        """None-valued fields are stripped from the stored entry."""
        entry = J.log_event("error", session_id=None, outcome=None)
        self.assertNotIn("session_id", entry)
        self.assertNotIn("outcome", entry)

    def test_has_utc_timestamp(self):
        """Entries always have a UTC ISO 8601 timestamp."""
        entry = J.log_event("session_outcome")
        self.assertIn("timestamp", entry)
        ts = entry["timestamp"]
        self.assertTrue(ts.endswith("Z"), f"Expected UTC timestamp, got: {ts}")
        self.assertRegex(ts, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

    def test_strategy_version_default(self):
        """strategy_version defaults to 'v0' when no strategy file exists."""
        entry = J.log_event("session_outcome")
        self.assertEqual(entry["strategy_version"], "v0")

    def test_metrics_default_empty_dict(self):
        """metrics defaults to {} when not provided."""
        entry = J.log_event("session_outcome")
        self.assertEqual(entry["metrics"], {})

    def test_learnings_default_empty_list(self):
        """learnings defaults to [] when not provided."""
        entry = J.log_event("session_outcome")
        self.assertEqual(entry["learnings"], [])

    def test_unknown_event_type_still_logged(self):
        """Unknown event types produce a warning but are still written."""
        import io
        buf = io.StringIO()
        # Capture stderr without suppressing it in test output
        old_stderr = sys.stderr
        sys.stderr = buf
        try:
            entry = J.log_event("totally_unknown_type")
        finally:
            sys.stderr = old_stderr
        self.assertEqual(entry["event_type"], "totally_unknown_type")
        self.assertIn("unknown event_type", buf.getvalue())

    def test_compact_json_format(self):
        """Stored JSON uses compact separators (no extra whitespace) for size efficiency."""
        J.log_event("session_outcome")
        with open(J.JOURNAL_PATH) as f:
            raw_line = f.readline().strip()
        # Compact format has no ': ' or ', ' spacing
        self.assertNotIn(": ", raw_line)
        self.assertNotIn(", ", raw_line)


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats(JournalTestBase):

    def test_empty_journal(self):
        """get_stats on an empty journal returns total_entries=0."""
        stats = J.get_stats()
        self.assertEqual(stats["total_entries"], 0)

    def test_counts_entries_by_event_type(self):
        J.log_event("session_outcome")
        J.log_event("session_outcome")
        J.log_event("nuclear_batch")
        stats = J.get_stats()
        self.assertEqual(stats["total_entries"], 3)
        self.assertEqual(stats["by_event_type"]["session_outcome"], 2)
        self.assertEqual(stats["by_event_type"]["nuclear_batch"], 1)

    def test_counts_entries_by_domain(self):
        J.log_event("session_outcome", domain="general")
        J.log_event("win", domain="agent_guard")
        J.log_event("win", domain="agent_guard")
        stats = J.get_stats()
        self.assertEqual(stats["by_domain"]["general"], 1)
        self.assertEqual(stats["by_domain"]["agent_guard"], 2)

    def test_counts_outcomes(self):
        J.log_event("session_outcome", outcome="success")
        J.log_event("session_outcome", outcome="partial")
        J.log_event("session_outcome", outcome="success")
        stats = J.get_stats()
        self.assertEqual(stats["by_outcome"]["success"], 2)
        self.assertEqual(stats["by_outcome"]["partial"], 1)

    def test_tracks_unique_sessions(self):
        J.log_event("session_outcome", session_id=10)
        J.log_event("session_outcome", session_id=10)
        J.log_event("session_outcome", session_id=11)
        stats = J.get_stats()
        self.assertIn(10, stats["sessions_logged"])
        self.assertIn(11, stats["sessions_logged"])
        self.assertEqual(len(stats["sessions_logged"]), 2)

    def test_counts_total_learnings(self):
        J.log_event("nuclear_batch", learnings=["L1", "L2"])
        J.log_event("nuclear_batch", learnings=["L3"])
        stats = J.get_stats()
        self.assertEqual(stats["total_learnings"], 3)

    def test_skips_corrupt_lines(self):
        """Corrupt JSONL lines are silently skipped; valid lines still counted."""
        with open(J.JOURNAL_PATH, "a") as f:
            f.write("THIS IS NOT JSON\n")
        J.log_event("session_outcome")
        stats = J.get_stats()
        self.assertEqual(stats["total_entries"], 1)


# ---------------------------------------------------------------------------
# get_recent / get_entries_by_domain / get_all_learnings
# ---------------------------------------------------------------------------

class TestQueryFunctions(JournalTestBase):

    def test_get_recent_returns_last_n(self):
        for i in range(5):
            J.log_event("session_outcome", session_id=i)
        recent = J.get_recent(3)
        self.assertEqual(len(recent), 3)
        # Should be the last 3 (session_ids 2, 3, 4)
        ids = [e.get("session_id") for e in recent]
        self.assertEqual(ids, [2, 3, 4])

    def test_get_entries_by_domain(self):
        J.log_event("win", domain="agent_guard")
        J.log_event("pain", domain="memory_system")
        J.log_event("win", domain="agent_guard")
        entries = J.get_entries_by_domain("agent_guard")
        self.assertEqual(len(entries), 2)
        for e in entries:
            self.assertEqual(e["domain"], "agent_guard")

    def test_get_all_learnings(self):
        J.log_event("nuclear_batch", session_id=5, domain="nuclear_scan",
                    learnings=["Use OTel", "LSP flag exists"])
        J.log_event("session_outcome", session_id=6, domain="general",
                    learnings=["TDD saves time"])
        learnings = J.get_all_learnings()
        self.assertEqual(len(learnings), 3)
        texts = [l["learning"] for l in learnings]
        self.assertIn("Use OTel", texts)
        self.assertIn("TDD saves time", texts)
        # Each learning includes session + domain context
        self.assertEqual(learnings[0]["session"], 5)
        self.assertEqual(learnings[0]["domain"], "nuclear_scan")


# ---------------------------------------------------------------------------
# get_nuclear_metrics
# ---------------------------------------------------------------------------

class TestNuclearMetrics(JournalTestBase):

    def test_returns_none_with_no_data(self):
        J.log_event("session_outcome")
        self.assertIsNone(J.get_nuclear_metrics())

    def test_aggregates_nuclear_batch_metrics(self):
        J.log_event("nuclear_batch", session_id=1, metrics={
            "posts_reviewed": 30, "build": 3, "adapt": 7, "skip": 20
        })
        J.log_event("nuclear_batch", session_id=2, metrics={
            "posts_reviewed": 20, "build": 1, "adapt": 3, "skip": 16
        })
        nm = J.get_nuclear_metrics()
        self.assertEqual(nm["batches"], 2)
        self.assertEqual(nm["posts_reviewed"], 50)
        self.assertEqual(nm["build"], 4)
        self.assertEqual(nm["adapt"], 10)
        self.assertAlmostEqual(nm["build_rate"], 4 / 50, places=3)
        self.assertAlmostEqual(nm["signal_rate"], 14 / 50, places=3)

    def test_counts_unique_sessions(self):
        J.log_event("nuclear_batch", session_id=10, metrics={"posts_reviewed": 5})
        J.log_event("nuclear_batch", session_id=10, metrics={"posts_reviewed": 5})
        nm = J.get_nuclear_metrics()
        self.assertEqual(nm["sessions"], 1)
        self.assertEqual(nm["posts_reviewed"], 10)


# ---------------------------------------------------------------------------
# get_trading_metrics
# ---------------------------------------------------------------------------

class TestTradingMetrics(JournalTestBase):

    def test_returns_none_with_no_trading_data(self):
        J.log_event("session_outcome")
        self.assertIsNone(J.get_trading_metrics())

    def test_win_loss_pnl_aggregation(self):
        J.log_event("bet_outcome", metrics={"result": "win", "pnl_cents": 50,
                                             "market_type": "binary", "strategy_name": "sniper"})
        J.log_event("bet_outcome", metrics={"result": "loss", "pnl_cents": -25,
                                             "market_type": "binary", "strategy_name": "sniper"})
        J.log_event("bet_outcome", metrics={"result": "void", "pnl_cents": 0,
                                             "market_type": "binary", "strategy_name": "sniper"})
        tm = J.get_trading_metrics()
        self.assertEqual(tm["total_bets"], 3)
        self.assertEqual(tm["wins"], 1)
        self.assertEqual(tm["losses"], 1)
        self.assertEqual(tm["voids"], 1)
        self.assertEqual(tm["total_pnl_cents"], 25)
        # Win rate excludes voids: 1 win / 2 decided
        self.assertAlmostEqual(tm["win_rate"], 0.5, places=3)

    def test_by_market_type(self):
        J.log_event("bet_outcome", metrics={"result": "win", "pnl_cents": 100,
                                             "market_type": "binary", "strategy_name": "X"})
        J.log_event("bet_outcome", metrics={"result": "loss", "pnl_cents": -50,
                                             "market_type": "spread", "strategy_name": "X"})
        tm = J.get_trading_metrics()
        self.assertIn("binary", tm["by_market_type"])
        self.assertIn("spread", tm["by_market_type"])
        self.assertEqual(tm["by_market_type"]["binary"]["wins"], 1)
        self.assertEqual(tm["by_market_type"]["spread"]["losses"], 1)

    def test_research_effectiveness(self):
        J.log_event("market_research", metrics={"actionable": True})
        J.log_event("market_research", metrics={"actionable": False})
        J.log_event("edge_discovered")
        J.log_event("edge_rejected")
        tm = J.get_trading_metrics()
        r = tm["research"]
        self.assertEqual(r["total_sessions"], 2)
        self.assertEqual(r["actionable"], 1)
        self.assertAlmostEqual(r["actionable_rate"], 0.5, places=3)
        self.assertEqual(r["edges_discovered"], 1)
        self.assertEqual(r["edges_rejected"], 1)


# ---------------------------------------------------------------------------
# get_time_stratified_trading_metrics
# ---------------------------------------------------------------------------

class TestTimeStratifiedMetrics(JournalTestBase):

    def test_returns_none_with_no_bet_outcomes(self):
        J.log_event("session_outcome")
        self.assertIsNone(J.get_time_stratified_trading_metrics())

    def test_buckets_by_hour(self):
        # Hour 02 → overnight (0-8), hour 15 → afternoon (14-20)
        self._write_raw({
            "event_type": "bet_outcome",
            "timestamp": "2026-03-20T02:30:00Z",
            "metrics": {"result": "loss", "pnl_cents": -100},
        })
        self._write_raw({
            "event_type": "bet_outcome",
            "timestamp": "2026-03-20T15:00:00Z",
            "metrics": {"result": "win", "pnl_cents": 200},
        })
        ts = J.get_time_stratified_trading_metrics()
        self.assertEqual(ts["total_bets_analyzed"], 2)
        overnight = ts["by_time_bucket"]["overnight"]
        afternoon = ts["by_time_bucket"]["afternoon"]
        self.assertEqual(overnight["losses"], 1)
        self.assertEqual(afternoon["wins"], 1)

    def test_overnight_vs_daytime_keys_present(self):
        self._write_raw({
            "event_type": "bet_outcome",
            "timestamp": "2026-03-20T10:00:00Z",
            "metrics": {"result": "win", "pnl_cents": 50},
        })
        ts = J.get_time_stratified_trading_metrics()
        ovd = ts["overnight_vs_daytime"]
        self.assertIn("overnight", ovd)
        self.assertIn("daytime", ovd)
        self.assertIn("delta_wr", ovd)
        self.assertIn("significant", ovd)

    def test_worst_hours_sorted_by_pnl(self):
        # Write 3 bet outcomes at different hours with varying PnL
        for hour, pnl, result in [(3, -200, "loss"), (10, 100, "win"), (20, -50, "loss")]:
            self._write_raw({
                "event_type": "bet_outcome",
                "timestamp": f"2026-03-20T{hour:02d}:00:00Z",
                "metrics": {"result": result, "pnl_cents": pnl},
            })
        ts = J.get_time_stratified_trading_metrics()
        worst = ts["worst_hours"]
        # First entry should have the lowest PnL (-200)
        self.assertEqual(worst[0][2], -200)


# ---------------------------------------------------------------------------
# get_pain_win_summary
# ---------------------------------------------------------------------------

class TestPainWinSummary(JournalTestBase):

    def test_empty_returns_zero_counts(self):
        J.log_event("session_outcome")
        pw = J.get_pain_win_summary()
        self.assertEqual(pw["pain_count"], 0)
        self.assertEqual(pw["win_count"], 0)
        self.assertIsNone(pw["ratio"])

    def test_counts_pains_and_wins(self):
        J.log_event("pain", domain="general")
        J.log_event("pain", domain="agent_guard")
        J.log_event("win", domain="agent_guard")
        pw = J.get_pain_win_summary()
        self.assertEqual(pw["pain_count"], 2)
        self.assertEqual(pw["win_count"], 1)
        self.assertAlmostEqual(pw["ratio"], 1 / 3, places=3)

    def test_domain_counters(self):
        J.log_event("win", domain="memory_system")
        J.log_event("win", domain="memory_system")
        J.log_event("pain", domain="spec_system")
        pw = J.get_pain_win_summary()
        self.assertEqual(pw["win_domains"]["memory_system"], 2)
        self.assertEqual(pw["pain_domains"]["spec_system"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
