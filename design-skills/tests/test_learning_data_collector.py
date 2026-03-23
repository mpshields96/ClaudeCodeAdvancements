"""Tests for learning_data_collector.py — MT-33 Phase 5: Self-learning intelligence data.

Extracts journal events, APF snapshots, and wrap assessments for report integration.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from learning_data_collector import LearningDataCollector


def _write_journal(path, entries):
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _write_apf(path, snapshots):
    with open(path, "w") as f:
        for s in snapshots:
            f.write(json.dumps(s) + "\n")


class TestLearningDataCollectorInit(unittest.TestCase):

    def test_init_with_paths(self):
        c = LearningDataCollector(journal_path="/tmp/j.jsonl", apf_path="/tmp/a.jsonl")
        self.assertEqual(c.journal_path, "/tmp/j.jsonl")

    def test_is_available_with_journal(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write('{"event_type": "test"}\n')
        try:
            c = LearningDataCollector(journal_path=f.name, apf_path="/nonexistent")
            self.assertTrue(c.is_available())
        finally:
            os.unlink(f.name)

    def test_not_available_missing_files(self):
        c = LearningDataCollector(journal_path="/nonexistent", apf_path="/nonexistent")
        self.assertFalse(c.is_available())


class TestJournalStats(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False)
        entries = [
            {"event_type": "session_outcome", "timestamp": "2026-03-10T00:00:00Z",
             "metrics": {"grade": "A"}, "domain": "cca"},
            {"event_type": "session_outcome", "timestamp": "2026-03-11T00:00:00Z",
             "metrics": {"grade": "B+"}, "domain": "cca"},
            {"event_type": "win", "timestamp": "2026-03-10T01:00:00Z",
             "metrics": {}, "domain": "memory"},
            {"event_type": "win", "timestamp": "2026-03-11T01:00:00Z",
             "metrics": {}, "domain": "context"},
            {"event_type": "win", "timestamp": "2026-03-12T01:00:00Z",
             "metrics": {}, "domain": "memory"},
            {"event_type": "pain", "timestamp": "2026-03-10T02:00:00Z",
             "metrics": {}, "domain": "spec"},
            {"event_type": "pain", "timestamp": "2026-03-11T02:00:00Z",
             "metrics": {}, "domain": "spec"},
            {"event_type": "nuclear_batch", "timestamp": "2026-03-12T00:00:00Z",
             "metrics": {"posts_reviewed": 45, "build": 2, "adapt": 8}, "domain": "nuclear_scan"},
            {"event_type": "unknown", "timestamp": "2026-03-10T03:00:00Z"},
        ]
        _write_journal(self.tmpfile.name, entries)
        self.collector = LearningDataCollector(
            journal_path=self.tmpfile.name, apf_path="/nonexistent"
        )

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_total_entries(self):
        stats = self.collector.get_journal_stats()
        self.assertEqual(stats["total_entries"], 9)

    def test_event_type_counts(self):
        stats = self.collector.get_journal_stats()
        self.assertEqual(stats["event_counts"]["win"], 3)
        self.assertEqual(stats["event_counts"]["pain"], 2)
        self.assertEqual(stats["event_counts"]["session_outcome"], 2)

    def test_domain_counts(self):
        stats = self.collector.get_journal_stats()
        self.assertEqual(stats["domain_counts"]["memory"], 2)
        self.assertEqual(stats["domain_counts"]["spec"], 2)

    def test_date_range(self):
        stats = self.collector.get_journal_stats()
        self.assertIn("2026-03-10", stats["first_entry"])
        self.assertIn("2026-03-12", stats["last_entry"])

    def test_win_pain_ratio(self):
        stats = self.collector.get_journal_stats()
        self.assertAlmostEqual(stats["win_pain_ratio"], 1.5)  # 3 wins / 2 pains


class TestAPFStats(unittest.TestCase):

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False)
        snapshots = [
            {"session": "S100", "timestamp": "2026-03-10T00:00:00Z",
             "total": 200, "apf": 20.0, "build": 10, "adapt": 30, "skip": 20,
             "signal": 40, "by_frontier": {}},
            {"session": "S110", "timestamp": "2026-03-15T00:00:00Z",
             "total": 300, "apf": 25.0, "build": 20, "adapt": 55, "skip": 30,
             "signal": 75, "by_frontier": {
                 "Frontier 1: Memory": {"apf": 23.5, "total": 50},
                 "Frontier 2: Spec": {"apf": 44.2, "total": 40},
             }},
        ]
        _write_apf(self.tmpfile.name, snapshots)
        self.collector = LearningDataCollector(
            journal_path="/nonexistent", apf_path=self.tmpfile.name
        )

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_apf_latest(self):
        stats = self.collector.get_apf_stats()
        self.assertAlmostEqual(stats["current_apf"], 25.0)
        self.assertEqual(stats["latest_session"], "S110")

    def test_apf_trend(self):
        stats = self.collector.get_apf_stats()
        self.assertEqual(len(stats["trend"]), 2)
        self.assertAlmostEqual(stats["trend"][0]["apf"], 20.0)
        self.assertAlmostEqual(stats["trend"][1]["apf"], 25.0)

    def test_apf_change(self):
        stats = self.collector.get_apf_stats()
        self.assertAlmostEqual(stats["apf_change"], 5.0)

    def test_frontier_breakdown(self):
        stats = self.collector.get_apf_stats()
        fb = stats["frontier_breakdown"]
        self.assertGreater(len(fb), 0)


class TestChartData(unittest.TestCase):

    def setUp(self):
        self.journal_file = tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False)
        entries = [
            {"event_type": "win", "timestamp": f"2026-03-{10+i}T00:00:00Z",
             "domain": "memory"} for i in range(5)
        ] + [
            {"event_type": "pain", "timestamp": f"2026-03-{10+i}T00:00:00Z",
             "domain": "spec"} for i in range(3)
        ] + [
            {"event_type": "session_outcome", "timestamp": f"2026-03-{10+i}T00:00:00Z",
             "domain": "cca", "metrics": {"grade": "A"}} for i in range(2)
        ]
        _write_journal(self.journal_file.name, entries)

        self.apf_file = tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False)
        _write_apf(self.apf_file.name, [
            {"session": f"S{100+i}", "timestamp": f"2026-03-{10+i}T00:00:00Z",
             "apf": 20 + i * 2, "total": 200 + i * 10, "build": 10 + i,
             "adapt": 30 + i, "skip": 20, "signal": 40 + i,
             "by_frontier": {}} for i in range(5)
        ])

        self.collector = LearningDataCollector(
            journal_path=self.journal_file.name, apf_path=self.apf_file.name
        )

    def tearDown(self):
        os.unlink(self.journal_file.name)
        os.unlink(self.apf_file.name)

    def test_event_type_bar_chart(self):
        data = self.collector.chart_event_types()
        self.assertIn("labels", data)
        self.assertIn("values", data)
        self.assertGreater(len(data["labels"]), 0)

    def test_apf_trend_sparkline(self):
        data = self.collector.chart_apf_trend()
        self.assertIn("labels", data)
        self.assertIn("values", data)
        self.assertEqual(len(data["values"]), 5)

    def test_domain_distribution(self):
        data = self.collector.chart_domain_distribution()
        self.assertIn("labels", data)
        self.assertIn("values", data)
        self.assertIn("memory", data["labels"])


class TestCollectAll(unittest.TestCase):

    def test_collect_all_with_data(self):
        journal_file = tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False)
        _write_journal(journal_file.name, [
            {"event_type": "win", "timestamp": "2026-03-10T00:00:00Z", "domain": "cca"}
        ])
        try:
            c = LearningDataCollector(
                journal_path=journal_file.name, apf_path="/nonexistent"
            )
            data = c.collect_all()
            self.assertTrue(data["available"])
            self.assertIn("journal", data)
            self.assertIn("apf", data)
            self.assertIn("charts", data)
            # JSON serializable
            json.dumps(data)
        finally:
            os.unlink(journal_file.name)

    def test_collect_all_unavailable(self):
        c = LearningDataCollector(journal_path="/nonexistent", apf_path="/nonexistent")
        data = c.collect_all()
        self.assertFalse(data["available"])

    def test_collect_all_chart_keys(self):
        journal_file = tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False)
        _write_journal(journal_file.name, [
            {"event_type": "win", "timestamp": "2026-03-10T00:00:00Z", "domain": "cca"}
        ])
        try:
            c = LearningDataCollector(journal_path=journal_file.name, apf_path="/nonexistent")
            data = c.collect_all()
            self.assertIn("event_types", data["charts"])
            self.assertIn("apf_trend", data["charts"])
            self.assertIn("domain_distribution", data["charts"])
        finally:
            os.unlink(journal_file.name)


if __name__ == "__main__":
    unittest.main()
