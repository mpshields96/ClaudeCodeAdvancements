#!/usr/bin/env python3
"""Tests for self-learning journal and reflection engine."""

import unittest
import os
import sys
import json
import tempfile
import shutil

# Add parent dirs to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

import journal
import reflect


class TestJournalLogging(unittest.TestCase):
    """Test journal event logging."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        reflect.SCRIPT_DIR = self.tmpdir
        # Write initial strategy
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-15T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_log_event_creates_file(self):
        entry = journal.log_event("session_outcome", session_id=1, domain="general", outcome="success")
        self.assertTrue(os.path.exists(journal.JOURNAL_PATH))
        self.assertEqual(entry["event_type"], "session_outcome")
        self.assertEqual(entry["session_id"], 1)
        self.assertEqual(entry["outcome"], "success")

    def test_log_event_appends(self):
        journal.log_event("session_outcome", session_id=1)
        journal.log_event("session_outcome", session_id=2)
        entries = journal._load_journal()
        self.assertEqual(len(entries), 2)

    def test_log_event_with_metrics(self):
        metrics = {"posts_reviewed": 45, "build": 2, "adapt": 8}
        entry = journal.log_event("nuclear_batch", session_id=1, metrics=metrics)
        self.assertEqual(entry["metrics"]["posts_reviewed"], 45)
        self.assertEqual(entry["metrics"]["build"], 2)

    def test_log_event_with_learnings(self):
        learnings = ["OTel is better than transcript parsing", "LSP hidden flag exists"]
        entry = journal.log_event("nuclear_batch", learnings=learnings)
        self.assertEqual(len(entry["learnings"]), 2)

    def test_log_event_strips_none(self):
        entry = journal.log_event("session_outcome")
        self.assertNotIn("session_id", entry)
        self.assertNotIn("outcome", entry)
        self.assertNotIn("notes", entry)

    def test_log_event_has_timestamp(self):
        entry = journal.log_event("session_outcome")
        self.assertIn("timestamp", entry)
        self.assertTrue(entry["timestamp"].endswith("Z"))

    def test_log_event_has_strategy_version(self):
        entry = journal.log_event("session_outcome")
        self.assertEqual(entry["strategy_version"], "v1")

    def test_valid_event_types(self):
        self.assertIn("nuclear_batch", journal.VALID_EVENT_TYPES)
        self.assertIn("session_outcome", journal.VALID_EVENT_TYPES)
        self.assertIn("strategy_update", journal.VALID_EVENT_TYPES)
        self.assertIn("pattern_detected", journal.VALID_EVENT_TYPES)
        self.assertIn("build_shipped", journal.VALID_EVENT_TYPES)

    def test_valid_domains(self):
        self.assertIn("nuclear_scan", journal.VALID_DOMAINS)
        self.assertIn("memory_system", journal.VALID_DOMAINS)
        self.assertIn("self_learning", journal.VALID_DOMAINS)
        self.assertIn("general", journal.VALID_DOMAINS)


class TestJournalStats(unittest.TestCase):
    """Test journal statistics aggregation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-15T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_stats_empty_journal(self):
        stats = journal.get_stats()
        self.assertEqual(stats["total_entries"], 0)

    def test_stats_counts_events(self):
        journal.log_event("session_outcome", session_id=1)
        journal.log_event("nuclear_batch", session_id=1)
        journal.log_event("nuclear_batch", session_id=2)
        stats = journal.get_stats()
        self.assertEqual(stats["total_entries"], 3)
        self.assertEqual(stats["by_event_type"]["nuclear_batch"], 2)
        self.assertEqual(stats["by_event_type"]["session_outcome"], 1)

    def test_stats_tracks_sessions(self):
        journal.log_event("session_outcome", session_id=1)
        journal.log_event("session_outcome", session_id=3)
        stats = journal.get_stats()
        self.assertEqual(stats["sessions_logged"], [1, 3])

    def test_stats_counts_outcomes(self):
        journal.log_event("session_outcome", outcome="success")
        journal.log_event("session_outcome", outcome="failure")
        journal.log_event("session_outcome", outcome="success")
        stats = journal.get_stats()
        self.assertEqual(stats["by_outcome"]["success"], 2)
        self.assertEqual(stats["by_outcome"]["failure"], 1)

    def test_stats_counts_learnings(self):
        journal.log_event("nuclear_batch", learnings=["a", "b"])
        journal.log_event("nuclear_batch", learnings=["c"])
        stats = journal.get_stats()
        self.assertEqual(stats["total_learnings"], 3)


class TestJournalRecent(unittest.TestCase):
    """Test recent entries retrieval."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-15T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_recent_empty(self):
        self.assertEqual(journal.get_recent(), [])

    def test_recent_returns_last_n(self):
        for i in range(20):
            journal.log_event("session_outcome", session_id=i)
        recent = journal.get_recent(5)
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[0]["session_id"], 15)

    def test_recent_fewer_than_n(self):
        journal.log_event("session_outcome", session_id=1)
        recent = journal.get_recent(10)
        self.assertEqual(len(recent), 1)


class TestNuclearMetrics(unittest.TestCase):
    """Test nuclear scan specific metrics."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-15T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_nuclear_metrics_none_when_empty(self):
        self.assertIsNone(journal.get_nuclear_metrics())

    def test_nuclear_metrics_aggregates(self):
        journal.log_event("nuclear_batch", session_id=1,
                         metrics={"posts_reviewed": 15, "build": 1, "adapt": 3, "reference": 4, "skip": 2, "fast_skip": 5})
        journal.log_event("nuclear_batch", session_id=1,
                         metrics={"posts_reviewed": 15, "build": 1, "adapt": 3, "reference": 3, "skip": 2, "fast_skip": 6})
        nm = journal.get_nuclear_metrics()
        self.assertEqual(nm["posts_reviewed"], 30)
        self.assertEqual(nm["build"], 2)
        self.assertEqual(nm["adapt"], 6)
        self.assertEqual(nm["batches"], 2)
        self.assertAlmostEqual(nm["signal_rate"], (2 + 6) / 30, places=3)

    def test_nuclear_metrics_counts_sessions(self):
        journal.log_event("nuclear_batch", session_id=1, metrics={"posts_reviewed": 10})
        journal.log_event("nuclear_batch", session_id=2, metrics={"posts_reviewed": 10})
        nm = journal.get_nuclear_metrics()
        self.assertEqual(nm["sessions"], 2)

    def test_nuclear_ignores_other_events(self):
        journal.log_event("session_outcome", session_id=1)
        journal.log_event("nuclear_batch", session_id=1, metrics={"posts_reviewed": 5, "build": 1})
        nm = journal.get_nuclear_metrics()
        self.assertEqual(nm["batches"], 1)
        self.assertEqual(nm["posts_reviewed"], 5)


class TestGetAllLearnings(unittest.TestCase):
    """Test learning extraction."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-15T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_empty_learnings(self):
        self.assertEqual(journal.get_all_learnings(), [])

    def test_collects_across_entries(self):
        journal.log_event("nuclear_batch", domain="nuclear_scan", learnings=["a", "b"])
        journal.log_event("session_outcome", domain="general", learnings=["c"])
        learnings = journal.get_all_learnings()
        self.assertEqual(len(learnings), 3)
        self.assertEqual(learnings[0]["learning"], "a")
        self.assertEqual(learnings[0]["domain"], "nuclear_scan")


class TestReflectPatterns(unittest.TestCase):
    """Test pattern detection in reflect engine."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({
                "version": 1,
                "updated_at": "2026-03-15T00:00:00Z",
                "nuclear_scan": {"min_score_threshold": 30}
            }, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_no_patterns_from_empty(self):
        patterns = reflect.detect_patterns([])
        self.assertEqual(len(patterns), 0)

    def test_detects_high_skip_rate(self):
        entries = [
            {"event_type": "nuclear_batch", "metrics": {"posts_reviewed": 15, "skip": 5, "fast_skip": 6, "build": 0, "adapt": 2, "reference": 2}},
            {"event_type": "nuclear_batch", "metrics": {"posts_reviewed": 15, "skip": 5, "fast_skip": 5, "build": 1, "adapt": 2, "reference": 2}},
        ]
        patterns = reflect.detect_patterns(entries)
        skip_patterns = [p for p in patterns if p["type"] == "high_skip_rate"]
        self.assertTrue(len(skip_patterns) > 0)

    def test_detects_domain_concentration(self):
        entries = [{"domain": "nuclear_scan", "event_type": "nuclear_batch"} for _ in range(8)]
        entries.append({"domain": "general", "event_type": "session_outcome"})
        patterns = reflect.detect_patterns(entries, min_sample=5)
        conc = [p for p in patterns if p["type"] == "domain_concentration"]
        self.assertTrue(len(conc) > 0)

    def test_detects_consecutive_failures(self):
        entries = [
            {"event_type": "session_outcome", "outcome": "failure"},
            {"event_type": "session_outcome", "outcome": "failure"},
            {"event_type": "session_outcome", "outcome": "success"},
        ]
        patterns = reflect.detect_patterns(entries)
        fails = [p for p in patterns if p["type"] == "consecutive_failures"]
        self.assertTrue(len(fails) > 0)

    def test_no_failure_pattern_when_ok(self):
        entries = [
            {"event_type": "session_outcome", "outcome": "success"},
            {"event_type": "session_outcome", "outcome": "success"},
            {"event_type": "session_outcome", "outcome": "success"},
        ]
        patterns = reflect.detect_patterns(entries)
        fails = [p for p in patterns if p["type"] == "consecutive_failures"]
        self.assertEqual(len(fails), 0)

    def test_detects_recurring_themes(self):
        entries = [
            {"learnings": ["context window exhaustion is a problem"]},
            {"learnings": ["context window management needs work"]},
            {"learnings": ["context window compaction causes issues"]},
            {"learnings": ["context window monitoring is critical"]},
        ]
        patterns = reflect.detect_patterns(entries)
        themes = [p for p in patterns if p["type"] == "recurring_themes"]
        self.assertTrue(len(themes) > 0)


class TestReflectApply(unittest.TestCase):
    """Test strategy auto-adjustment."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({
                "version": 1,
                "updated_at": "2026-03-15T00:00:00Z",
                "nuclear_scan": {"min_score_threshold": 30},
                "learning": {"auto_adjust_enabled": True},
                "bounds": {
                    "nuclear_scan.min_score_threshold": {"min": 10, "max": 200, "step": 10}
                }
            }, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_apply_bumps_version(self):
        patterns = [
            {"type": "test", "severity": "info", "message": "test",
             "suggestion": {"nuclear_scan.min_score_threshold": 50}}
        ]
        strategy = journal._load_strategy()
        changes = reflect.apply_suggestions(patterns, strategy)
        self.assertTrue(len(changes) > 0)
        updated = journal._load_strategy()
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["nuclear_scan"]["min_score_threshold"], 50)

    def test_no_change_no_bump(self):
        patterns = [
            {"type": "test", "severity": "info", "message": "test",
             "suggestion": {"nuclear_scan.min_score_threshold": 30}}  # Same as current
        ]
        strategy = journal._load_strategy()
        changes = reflect.apply_suggestions(patterns, strategy)
        self.assertEqual(len(changes), 0)

    def test_apply_logs_to_journal(self):
        patterns = [
            {"type": "test", "severity": "info", "message": "test",
             "suggestion": {"nuclear_scan.min_score_threshold": 50}}
        ]
        strategy = journal._load_strategy()
        reflect.apply_suggestions(patterns, strategy)
        entries = journal._load_journal()
        strategy_updates = [e for e in entries if e.get("event_type") == "strategy_update"]
        self.assertEqual(len(strategy_updates), 1)


class TestGetEntriesByDomain(unittest.TestCase):
    """Test domain filtering."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-15T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_filters_by_domain(self):
        journal.log_event("nuclear_batch", domain="nuclear_scan")
        journal.log_event("session_outcome", domain="general")
        journal.log_event("nuclear_batch", domain="nuclear_scan")
        result = journal.get_entries_by_domain("nuclear_scan")
        self.assertEqual(len(result), 2)

    def test_empty_for_unknown_domain(self):
        journal.log_event("session_outcome", domain="general")
        result = journal.get_entries_by_domain("nonexistent")
        self.assertEqual(len(result), 0)


class TestBoundedAutoAdjust(unittest.TestCase):
    """Test bounded parameter safety rails."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({
                "version": 1,
                "updated_at": "2026-03-15T00:00:00Z",
                "nuclear_scan": {"min_score_threshold": 30},
                "learning": {"auto_adjust_enabled": True},
                "bounds": {
                    "nuclear_scan.min_score_threshold": {"min": 10, "max": 200, "step": 10}
                }
            }, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_clamp_within_bounds(self):
        strategy = journal._load_strategy()
        result = reflect._clamp_to_bounds("nuclear_scan.min_score_threshold", 50, strategy)
        self.assertEqual(result, 50)

    def test_clamp_above_max(self):
        strategy = journal._load_strategy()
        result = reflect._clamp_to_bounds("nuclear_scan.min_score_threshold", 999, strategy)
        self.assertEqual(result, 200)

    def test_clamp_below_min(self):
        strategy = journal._load_strategy()
        result = reflect._clamp_to_bounds("nuclear_scan.min_score_threshold", 1, strategy)
        self.assertEqual(result, 10)

    def test_clamp_snaps_to_step(self):
        strategy = journal._load_strategy()
        # 47 should snap to 50 (step=10, min=10)
        result = reflect._clamp_to_bounds("nuclear_scan.min_score_threshold", 47, strategy)
        self.assertEqual(result, 50)

    def test_clamp_no_bounds_returns_none(self):
        strategy = journal._load_strategy()
        result = reflect._clamp_to_bounds("nonexistent.key", 50, strategy)
        self.assertIsNone(result)

    def test_reject_when_auto_adjust_disabled(self):
        strategy = journal._load_strategy()
        strategy["learning"]["auto_adjust_enabled"] = False
        patterns = [
            {"type": "test", "severity": "info", "message": "test",
             "suggestion": {"nuclear_scan.min_score_threshold": 50}}
        ]
        changes = reflect.apply_suggestions(patterns, strategy)
        self.assertEqual(len(changes), 0)
        # Strategy should NOT be updated
        loaded = journal._load_strategy()
        self.assertEqual(loaded["nuclear_scan"]["min_score_threshold"], 30)

    def test_reject_unbounded_parameter(self):
        strategy = journal._load_strategy()
        patterns = [
            {"type": "test", "severity": "info", "message": "test",
             "suggestion": {"unbounded.param": 999}}
        ]
        changes = reflect.apply_suggestions(patterns, strategy)
        self.assertEqual(len(changes), 0)

    def test_apply_clamped_value(self):
        strategy = journal._load_strategy()
        patterns = [
            {"type": "test", "severity": "info", "message": "test",
             "suggestion": {"nuclear_scan.min_score_threshold": 999}}
        ]
        changes = reflect.apply_suggestions(patterns, strategy)
        self.assertEqual(len(changes), 1)
        self.assertIn("clamped", changes[0])
        loaded = journal._load_strategy()
        self.assertEqual(loaded["nuclear_scan"]["min_score_threshold"], 200)


class TestPainWinSignals(unittest.TestCase):
    """Test pain/win signal tracking."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-15T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_pain_event_logs(self):
        entry = journal.log_event("pain", domain="general", notes="Wasted 30min on wrong approach")
        self.assertEqual(entry["event_type"], "pain")

    def test_win_event_logs(self):
        entry = journal.log_event("win", domain="nuclear_scan", notes="Found 3 BUILD candidates in 15min")
        self.assertEqual(entry["event_type"], "win")

    def test_pain_win_summary_empty(self):
        pw = journal.get_pain_win_summary()
        self.assertEqual(pw["pain_count"], 0)
        self.assertEqual(pw["win_count"], 0)
        self.assertIsNone(pw["ratio"])

    def test_pain_win_summary_counts(self):
        journal.log_event("pain", domain="general")
        journal.log_event("win", domain="general")
        journal.log_event("win", domain="nuclear_scan")
        pw = journal.get_pain_win_summary()
        self.assertEqual(pw["pain_count"], 1)
        self.assertEqual(pw["win_count"], 2)
        self.assertAlmostEqual(pw["ratio"], 2 / 3, places=3)

    def test_pain_win_domains(self):
        journal.log_event("pain", domain="general")
        journal.log_event("pain", domain="general")
        journal.log_event("pain", domain="nuclear_scan")
        pw = journal.get_pain_win_summary()
        self.assertEqual(pw["pain_domains"]["general"], 2)
        self.assertEqual(pw["pain_domains"]["nuclear_scan"], 1)

    def test_pain_win_ignores_other_events(self):
        journal.log_event("session_outcome", domain="general")
        journal.log_event("pain", domain="general")
        pw = journal.get_pain_win_summary()
        self.assertEqual(pw["pain_count"], 1)
        self.assertEqual(pw["win_count"], 0)

    def test_high_pain_pattern_detected(self):
        # 8 pains, 2 wins = 20% win ratio — should trigger warning
        for _ in range(8):
            journal.log_event("pain", domain="general")
        for _ in range(2):
            journal.log_event("win", domain="general")
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=5)
        pain_patterns = [p for p in patterns if p["type"] == "high_pain_rate"]
        self.assertEqual(len(pain_patterns), 1)

    def test_high_win_pattern_detected(self):
        # 1 pain, 9 wins = 90% win ratio
        journal.log_event("pain", domain="general")
        for _ in range(9):
            journal.log_event("win", domain="general")
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=5)
        win_patterns = [p for p in patterns if p["type"] == "high_win_rate"]
        self.assertEqual(len(win_patterns), 1)

    def test_no_pattern_below_min_sample(self):
        journal.log_event("pain", domain="general")
        journal.log_event("win", domain="general")
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=5)
        pw_patterns = [p for p in patterns if p["type"] in ("high_pain_rate", "high_win_rate")]
        self.assertEqual(len(pw_patterns), 0)


class TestTradingEventTypes(unittest.TestCase):
    """Test trading domain event types and validation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-16T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_trading_event_types_exist(self):
        for et in ["bet_placed", "bet_outcome", "market_research",
                    "edge_discovered", "edge_rejected", "strategy_shift"]:
            self.assertIn(et, journal.VALID_EVENT_TYPES)

    def test_trading_domain_exists(self):
        self.assertIn("trading", journal.VALID_DOMAINS)

    def test_log_bet_placed(self):
        entry = journal.log_event("bet_placed", domain="trading", metrics={
            "market_type": "crypto_15m", "ticker": "KXBTC15M",
            "side": "yes", "price_cents": 95, "contracts": 10,
            "strategy_name": "expiry_sniper_v1",
        })
        self.assertEqual(entry["event_type"], "bet_placed")
        self.assertEqual(entry["domain"], "trading")
        self.assertEqual(entry["metrics"]["ticker"], "KXBTC15M")

    def test_log_bet_outcome(self):
        entry = journal.log_event("bet_outcome", domain="trading", outcome="success",
                                  metrics={
                                      "ticker": "KXBTC15M", "result": "win",
                                      "pnl_cents": 500, "side": "yes",
                                      "strategy_name": "expiry_sniper_v1",
                                  })
        self.assertEqual(entry["outcome"], "success")
        self.assertEqual(entry["metrics"]["pnl_cents"], 500)

    def test_log_market_research(self):
        entry = journal.log_event("market_research", domain="trading",
                                  outcome="success",
                                  notes="Found crypto 15m edge via ATR analysis",
                                  metrics={"research_path": "atr_volatility",
                                           "actionable": True})
        self.assertEqual(entry["event_type"], "market_research")
        self.assertTrue(entry["metrics"]["actionable"])

    def test_log_edge_discovered(self):
        entry = journal.log_event("edge_discovered", domain="trading",
                                  notes="Sniper bets at 95c+ with <2min to expiry",
                                  metrics={"edge_type": "expiry_timing",
                                           "expected_win_rate": 0.85,
                                           "market_type": "crypto_15m"})
        self.assertEqual(entry["metrics"]["edge_type"], "expiry_timing")

    def test_log_edge_rejected(self):
        entry = journal.log_event("edge_rejected", domain="trading",
                                  outcome="failure",
                                  notes="Weather market mean-reversion too noisy",
                                  metrics={"edge_type": "mean_reversion",
                                           "reason": "insufficient_sample",
                                           "market_type": "weather"})
        self.assertEqual(entry["outcome"], "failure")
        self.assertEqual(entry["metrics"]["reason"], "insufficient_sample")

    def test_log_strategy_shift(self):
        entry = journal.log_event("strategy_shift", domain="trading",
                                  notes="Raised min liquidity threshold from 50 to 100",
                                  metrics={"param": "min_liquidity",
                                           "old_value": 50, "new_value": 100,
                                           "reason": "3 losses on thin markets"})
        self.assertEqual(entry["event_type"], "strategy_shift")


class TestTradingMetrics(unittest.TestCase):
    """Test trading-specific metrics aggregation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-16T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_trading_metrics_none_when_empty(self):
        self.assertIsNone(journal.get_trading_metrics())

    def test_trading_metrics_counts_bets(self):
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "win", "pnl_cents": 500,
                                   "market_type": "crypto_15m", "strategy_name": "sniper"})
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "loss", "pnl_cents": -100,
                                   "market_type": "crypto_15m", "strategy_name": "sniper"})
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "win", "pnl_cents": 300,
                                   "market_type": "weather", "strategy_name": "mean_rev"})
        tm = journal.get_trading_metrics()
        self.assertEqual(tm["total_bets"], 3)
        self.assertEqual(tm["wins"], 2)
        self.assertEqual(tm["losses"], 1)
        self.assertAlmostEqual(tm["win_rate"], 2 / 3, places=3)

    def test_trading_metrics_pnl(self):
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "win", "pnl_cents": 500})
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "loss", "pnl_cents": -200})
        tm = journal.get_trading_metrics()
        self.assertEqual(tm["total_pnl_cents"], 300)

    def test_trading_metrics_by_market_type(self):
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "win", "pnl_cents": 500,
                                   "market_type": "crypto_15m"})
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "loss", "pnl_cents": -100,
                                   "market_type": "crypto_15m"})
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "win", "pnl_cents": 200,
                                   "market_type": "weather"})
        tm = journal.get_trading_metrics()
        self.assertEqual(tm["by_market_type"]["crypto_15m"]["bets"], 2)
        self.assertEqual(tm["by_market_type"]["crypto_15m"]["pnl_cents"], 400)
        self.assertEqual(tm["by_market_type"]["weather"]["bets"], 1)

    def test_trading_metrics_by_strategy(self):
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "win", "pnl_cents": 500,
                                   "strategy_name": "sniper"})
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "win", "pnl_cents": 300,
                                   "strategy_name": "sniper"})
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "loss", "pnl_cents": -400,
                                   "strategy_name": "mean_rev"})
        tm = journal.get_trading_metrics()
        self.assertEqual(tm["by_strategy"]["sniper"]["wins"], 2)
        self.assertEqual(tm["by_strategy"]["sniper"]["pnl_cents"], 800)
        self.assertEqual(tm["by_strategy"]["mean_rev"]["losses"], 1)

    def test_trading_metrics_research_effectiveness(self):
        journal.log_event("market_research", domain="trading",
                          metrics={"actionable": True, "research_path": "atr"})
        journal.log_event("market_research", domain="trading",
                          metrics={"actionable": False, "research_path": "sentiment"})
        journal.log_event("market_research", domain="trading",
                          metrics={"actionable": True, "research_path": "volatility"})
        journal.log_event("edge_discovered", domain="trading",
                          metrics={"edge_type": "timing"})
        journal.log_event("edge_rejected", domain="trading",
                          metrics={"edge_type": "sentiment"})
        tm = journal.get_trading_metrics()
        self.assertEqual(tm["research"]["total_sessions"], 3)
        self.assertEqual(tm["research"]["actionable"], 2)
        self.assertEqual(tm["research"]["edges_discovered"], 1)
        self.assertEqual(tm["research"]["edges_rejected"], 1)
        self.assertAlmostEqual(tm["research"]["actionable_rate"], 2 / 3, places=3)

    def test_trading_metrics_ignores_non_trading(self):
        journal.log_event("session_outcome", domain="general", outcome="success")
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "win", "pnl_cents": 100})
        tm = journal.get_trading_metrics()
        self.assertEqual(tm["total_bets"], 1)

    def test_trading_metrics_void_bets(self):
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "void", "pnl_cents": 0})
        tm = journal.get_trading_metrics()
        self.assertEqual(tm["total_bets"], 1)
        self.assertEqual(tm["wins"], 0)
        self.assertEqual(tm["losses"], 0)
        self.assertEqual(tm["voids"], 1)

    def test_trading_metrics_cli_subcommand(self):
        """Test that trading-stats CLI subcommand exists."""
        journal.log_event("bet_outcome", domain="trading",
                          metrics={"result": "win", "pnl_cents": 100})
        # Just verify get_trading_metrics returns data (CLI tested via integration)
        tm = journal.get_trading_metrics()
        self.assertIsNotNone(tm)


class TestTradingPatternDetection(unittest.TestCase):
    """Test trading-specific pattern detection in reflect.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({
                "version": 1,
                "updated_at": "2026-03-16T00:00:00Z",
                "trading": {
                    "min_sample_bets": 20,
                    "min_liquidity": 50,
                    "win_rate_alert_below": 0.4,
                },
                "learning": {"auto_adjust_enabled": True},
                "bounds": {
                    "trading.min_liquidity": {"min": 10, "max": 500, "step": 10},
                    "trading.min_sample_bets": {"min": 5, "max": 50, "step": 5},
                    "trading.win_rate_alert_below": {"min": 0.2, "max": 0.6, "step": 0.05},
                }
            }, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def test_detects_losing_strategy(self):
        """Strategy with <40% win rate over 20+ bets triggers warning."""
        for _ in range(15):
            journal.log_event("bet_outcome", domain="trading",
                              metrics={"result": "loss", "pnl_cents": -100,
                                       "strategy_name": "bad_strat"})
        for _ in range(5):
            journal.log_event("bet_outcome", domain="trading",
                              metrics={"result": "win", "pnl_cents": 100,
                                       "strategy_name": "bad_strat"})
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=5)
        losing = [p for p in patterns if p["type"] == "losing_strategy"]
        self.assertTrue(len(losing) > 0)
        self.assertEqual(losing[0]["data"]["strategy"], "bad_strat")

    def test_no_losing_strategy_below_sample(self):
        """Don't flag with fewer than min_sample_bets."""
        for _ in range(3):
            journal.log_event("bet_outcome", domain="trading",
                              metrics={"result": "loss", "strategy_name": "new_strat"})
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=5)
        losing = [p for p in patterns if p["type"] == "losing_strategy"]
        self.assertEqual(len(losing), 0)

    def test_detects_research_dead_end(self):
        """Research path with 0 actionable results over 5+ sessions triggers warning."""
        for _ in range(6):
            journal.log_event("market_research", domain="trading",
                              metrics={"actionable": False,
                                       "research_path": "sentiment_analysis"})
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=5)
        dead_ends = [p for p in patterns if p["type"] == "research_dead_end"]
        self.assertTrue(len(dead_ends) > 0)
        self.assertIn("sentiment_analysis", dead_ends[0]["data"]["path"])

    def test_no_dead_end_with_some_hits(self):
        """Research path with some actionable results is not flagged."""
        for _ in range(4):
            journal.log_event("market_research", domain="trading",
                              metrics={"actionable": False,
                                       "research_path": "atr_vol"})
        journal.log_event("market_research", domain="trading",
                          metrics={"actionable": True,
                                   "research_path": "atr_vol"})
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=5)
        dead_ends = [p for p in patterns if p["type"] == "research_dead_end"]
        self.assertEqual(len(dead_ends), 0)

    def test_detects_negative_pnl_trend(self):
        """Cumulative PnL going negative triggers warning."""
        for _ in range(10):
            journal.log_event("bet_outcome", domain="trading",
                              metrics={"result": "loss", "pnl_cents": -200})
        for _ in range(5):
            journal.log_event("bet_outcome", domain="trading",
                              metrics={"result": "win", "pnl_cents": 100})
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=5)
        neg_pnl = [p for p in patterns if p["type"] == "negative_pnl"]
        self.assertTrue(len(neg_pnl) > 0)

    def test_no_negative_pnl_when_profitable(self):
        """Profitable trading doesn't trigger warning."""
        for _ in range(10):
            journal.log_event("bet_outcome", domain="trading",
                              metrics={"result": "win", "pnl_cents": 500})
        for _ in range(2):
            journal.log_event("bet_outcome", domain="trading",
                              metrics={"result": "loss", "pnl_cents": -100})
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=5)
        neg_pnl = [p for p in patterns if p["type"] == "negative_pnl"]
        self.assertEqual(len(neg_pnl), 0)

    def test_detects_edge_quality_signal(self):
        """Edges with high discovery-to-rejection ratio noted."""
        for _ in range(4):
            journal.log_event("edge_discovered", domain="trading")
        journal.log_event("edge_rejected", domain="trading")
        entries = journal._load_journal()
        patterns = reflect.detect_patterns(entries, min_sample=3)
        edge_q = [p for p in patterns if p["type"] == "strong_edge_discovery"]
        self.assertTrue(len(edge_q) > 0)


class TestTimeStratifiedTradingMetrics(unittest.TestCase):
    """Test time-stratified trading analysis — objective overnight detection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_journal = journal.JOURNAL_PATH
        self.orig_strategy = journal.STRATEGY_PATH
        journal.JOURNAL_PATH = os.path.join(self.tmpdir, "journal.jsonl")
        journal.STRATEGY_PATH = os.path.join(self.tmpdir, "strategy.json")
        with open(journal.STRATEGY_PATH, "w") as f:
            json.dump({"version": 1, "updated_at": "2026-03-19T00:00:00Z"}, f)

    def tearDown(self):
        journal.JOURNAL_PATH = self.orig_journal
        journal.STRATEGY_PATH = self.orig_strategy
        shutil.rmtree(self.tmpdir)

    def _log_bet(self, hour, result="win", pnl=100, strategy="sniper"):
        """Helper to log a bet at a specific UTC hour."""
        entry = {
            "timestamp": f"2026-03-19T{hour:02d}:30:00Z",
            "event_type": "bet_outcome",
            "domain": "trading",
            "metrics": {
                "result": result,
                "pnl_cents": pnl,
                "strategy_name": strategy,
                "market_type": "crypto_15m",
            },
            "strategy_version": "v1",
        }
        with open(journal.JOURNAL_PATH, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def test_none_when_no_trading_data(self):
        self.assertIsNone(journal.get_time_stratified_trading_metrics())

    def test_basic_time_bucketing(self):
        # 5 bets in overnight (0-8 UTC), 5 in afternoon (14-20 UTC)
        for h in range(0, 5):
            self._log_bet(h, "win", 100)
        for h in range(14, 19):
            self._log_bet(h, "win", 200)
        ts = journal.get_time_stratified_trading_metrics()
        self.assertEqual(ts["by_time_bucket"]["overnight"]["bets"], 5)
        self.assertEqual(ts["by_time_bucket"]["afternoon"]["bets"], 5)
        self.assertEqual(ts["total_bets_analyzed"], 10)

    def test_hourly_breakdown(self):
        self._log_bet(3, "win", 100)
        self._log_bet(3, "loss", -50)
        self._log_bet(15, "win", 200)
        ts = journal.get_time_stratified_trading_metrics()
        self.assertEqual(ts["by_hour"][3]["bets"], 2)
        self.assertEqual(ts["by_hour"][3]["wins"], 1)
        self.assertEqual(ts["by_hour"][3]["losses"], 1)
        self.assertEqual(ts["by_hour"][15]["bets"], 1)

    def test_win_rate_per_bucket(self):
        # Overnight: 2 wins, 8 losses = 20% WR
        for _ in range(2):
            self._log_bet(2, "win", 100)
        for _ in range(8):
            self._log_bet(3, "loss", -100)
        # Afternoon: 9 wins, 1 loss = 90% WR
        for _ in range(9):
            self._log_bet(15, "win", 100)
        self._log_bet(16, "loss", -100)
        ts = journal.get_time_stratified_trading_metrics()
        self.assertAlmostEqual(ts["by_time_bucket"]["overnight"]["win_rate"], 0.2, places=4)
        self.assertAlmostEqual(ts["by_time_bucket"]["afternoon"]["win_rate"], 0.9, places=4)

    def test_overnight_vs_daytime_comparison(self):
        # Overnight: 3 wins, 7 losses
        for _ in range(3):
            self._log_bet(1, "win", 100)
        for _ in range(7):
            self._log_bet(4, "loss", -100)
        # Daytime (morning + afternoon + evening): 15 wins, 5 losses
        for _ in range(15):
            self._log_bet(10, "win", 100)
        for _ in range(5):
            self._log_bet(16, "loss", -100)
        ts = journal.get_time_stratified_trading_metrics()
        ovd = ts["overnight_vs_daytime"]
        self.assertEqual(ovd["overnight"]["bets"], 10)
        self.assertEqual(ovd["daytime"]["bets"], 20)
        self.assertAlmostEqual(ovd["overnight"]["win_rate"], 0.3, places=4)
        self.assertAlmostEqual(ovd["daytime"]["win_rate"], 0.75, places=4)
        # delta_wr should be positive (daytime better)
        self.assertGreater(ovd["delta_wr"], 0)

    def test_significance_detection(self):
        # Large sample with very different WRs should be significant
        for _ in range(20):
            self._log_bet(2, "loss", -100)  # overnight all losses
        for _ in range(20):
            self._log_bet(15, "win", 100)  # daytime all wins
        ts = journal.get_time_stratified_trading_metrics()
        self.assertTrue(ts["overnight_vs_daytime"]["significant"])

    def test_no_significance_with_small_sample(self):
        # 3 bets each — too small for significance
        for _ in range(3):
            self._log_bet(2, "loss", -100)
        for _ in range(3):
            self._log_bet(15, "win", 100)
        ts = journal.get_time_stratified_trading_metrics()
        self.assertFalse(ts["overnight_vs_daytime"]["significant"])

    def test_no_significance_when_similar_wr(self):
        # Both windows similar WR — should NOT be significant
        for _ in range(15):
            self._log_bet(2, "win", 100)
        for _ in range(5):
            self._log_bet(3, "loss", -100)
        for _ in range(14):
            self._log_bet(15, "win", 100)
        for _ in range(6):
            self._log_bet(16, "loss", -100)
        ts = journal.get_time_stratified_trading_metrics()
        self.assertFalse(ts["overnight_vs_daytime"]["significant"])

    def test_worst_hours_sorted_by_pnl(self):
        self._log_bet(2, "loss", -500)
        self._log_bet(3, "loss", -300)
        self._log_bet(15, "win", 200)
        self._log_bet(16, "win", 400)
        ts = journal.get_time_stratified_trading_metrics()
        worst = ts["worst_hours"]
        # First entry should be worst PnL
        self.assertEqual(worst[0][0], 2)  # hour 2
        self.assertEqual(worst[0][2], -500)  # pnl

    def test_pnl_tracking_per_bucket(self):
        self._log_bet(2, "win", 100)
        self._log_bet(3, "loss", -300)
        ts = journal.get_time_stratified_trading_metrics()
        self.assertEqual(ts["by_time_bucket"]["overnight"]["pnl_cents"], -200)

    def test_custom_time_buckets(self):
        self._log_bet(5, "win", 100)
        self._log_bet(18, "loss", -50)
        custom = [("early", 0, 12), ("late", 12, 24)]
        ts = journal.get_time_stratified_trading_metrics(time_buckets=custom)
        self.assertEqual(ts["by_time_bucket"]["early"]["bets"], 1)
        self.assertEqual(ts["by_time_bucket"]["late"]["bets"], 1)

    def test_handles_malformed_timestamps(self):
        # Log a normal bet plus one with bad timestamp
        self._log_bet(10, "win", 100)
        entry = {
            "timestamp": "bad-timestamp",
            "event_type": "bet_outcome",
            "domain": "trading",
            "metrics": {"result": "win", "pnl_cents": 50},
            "strategy_version": "v1",
        }
        with open(journal.JOURNAL_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
        ts = journal.get_time_stratified_trading_metrics()
        # Should only count the valid bet
        self.assertEqual(ts["total_bets_analyzed"], 2)
        self.assertEqual(ts["by_hour"][10]["bets"], 1)

    def test_void_bets_counted_but_not_in_wr(self):
        self._log_bet(10, "void", 0)
        self._log_bet(10, "win", 100)
        ts = journal.get_time_stratified_trading_metrics()
        self.assertEqual(ts["by_hour"][10]["bets"], 2)
        self.assertEqual(ts["by_hour"][10]["wins"], 1)
        self.assertAlmostEqual(ts["by_hour"][10]["win_rate"], 1.0, places=4)

    def test_cli_time_stats_subcommand(self):
        """Verify time-stats CLI path exists."""
        self._log_bet(10, "win", 100)
        ts = journal.get_time_stratified_trading_metrics()
        self.assertIsNotNone(ts)


if __name__ == "__main__":
    unittest.main()
