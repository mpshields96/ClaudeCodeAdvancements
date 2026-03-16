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
                "nuclear_scan": {"min_score_threshold": 30}
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


if __name__ == "__main__":
    unittest.main()
