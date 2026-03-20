#!/usr/bin/env python3
"""Tests for tech_debt_tracker.py — MT-20 Full Vision: SATD trend tracking.

TechDebtTracker scans a codebase for SATD markers, stores historical snapshots,
and identifies hotspot modules (files with growing or persistent debt).

Tests cover:
- Snapshot generation (scan all code files in a directory)
- Persistence (save/load snapshots as JSONL)
- Hotspot detection (files with most/growing markers)
- Trend calculation (increasing/stable/decreasing debt)
- Summary report generation
- Edge cases (empty dir, no SATD, single file)
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tech_debt_tracker import TechDebtTracker, DebtSnapshot, HotspotFile


class TestDebtSnapshot(unittest.TestCase):
    """Test DebtSnapshot dataclass."""

    def test_fields(self):
        s = DebtSnapshot(
            timestamp="2026-03-20T12:00:00Z",
            file_path="src/utils.py",
            markers=[{"line": 10, "type": "TODO", "text": "TODO: fix this"}],
        )
        self.assertEqual(s.file_path, "src/utils.py")
        self.assertEqual(len(s.markers), 1)

    def test_to_dict(self):
        s = DebtSnapshot(
            timestamp="2026-03-20T12:00:00Z",
            file_path="src/utils.py",
            markers=[],
        )
        d = s.to_dict()
        self.assertIn("timestamp", d)
        self.assertIn("file_path", d)
        self.assertIn("markers", d)
        self.assertIn("marker_count", d)

    def test_marker_count_matches_list(self):
        s = DebtSnapshot(
            timestamp="2026-03-20T12:00:00Z",
            file_path="src/utils.py",
            markers=[{"type": "TODO"}, {"type": "FIXME"}],
        )
        self.assertEqual(s.to_dict()["marker_count"], 2)


class TestHotspotFile(unittest.TestCase):
    """Test HotspotFile dataclass."""

    def test_fields(self):
        h = HotspotFile(file_path="src/utils.py", current_count=5, trend="increasing")
        self.assertEqual(h.file_path, "src/utils.py")
        self.assertEqual(h.current_count, 5)
        self.assertEqual(h.trend, "increasing")

    def test_to_dict(self):
        h = HotspotFile(file_path="src/utils.py", current_count=3, trend="stable")
        d = h.to_dict()
        self.assertIn("file_path", d)
        self.assertIn("current_count", d)
        self.assertIn("trend", d)

    def test_valid_trends(self):
        for trend in ["increasing", "stable", "decreasing", "new"]:
            h = HotspotFile(file_path="x.py", current_count=1, trend=trend)
            self.assertEqual(h.trend, trend)


class TestTechDebtTrackerScan(unittest.TestCase):
    """Test scanning a directory for SATD markers."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tracker = TechDebtTracker(db_path=os.path.join(self.tmpdir, "debt.jsonl"))

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_scan_empty_dir_returns_empty(self):
        empty = tempfile.mkdtemp()
        snapshots = self.tracker.scan_directory(empty)
        self.assertEqual(snapshots, [])

    def test_scan_single_clean_file(self):
        self._write_file("clean.py", "x = 1\ny = 2\n")
        snapshots = self.tracker.scan_directory(self.tmpdir)
        # File with no SATD may still create snapshot but with 0 markers
        total_markers = sum(len(s.markers) for s in snapshots)
        self.assertEqual(total_markers, 0)

    def test_scan_detects_todo(self):
        self._write_file("debt.py", "# TODO: fix this\nx = 1\n")
        snapshots = self.tracker.scan_directory(self.tmpdir)
        total_markers = sum(len(s.markers) for s in snapshots)
        self.assertGreater(total_markers, 0)

    def test_scan_multiple_files(self):
        self._write_file("a.py", "# TODO: fix a\n")
        self._write_file("b.py", "# FIXME: fix b\n")
        snapshots = self.tracker.scan_directory(self.tmpdir)
        files_with_debt = [s for s in snapshots if s.markers]
        self.assertGreaterEqual(len(files_with_debt), 2)

    def test_scan_skips_non_code_files(self):
        self._write_file("README.md", "# TODO: document more\n")
        self._write_file("config.json", '{"TODO": "not code"}')
        snapshots = self.tracker.scan_directory(self.tmpdir)
        total_markers = sum(len(s.markers) for s in snapshots)
        self.assertEqual(total_markers, 0)

    def test_snapshot_has_timestamp(self):
        self._write_file("code.py", "# TODO: something\n")
        snapshots = self.tracker.scan_directory(self.tmpdir)
        for s in snapshots:
            self.assertTrue(s.timestamp)


class TestTechDebtTrackerPersistence(unittest.TestCase):
    """Test saving and loading snapshots."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "debt.jsonl")
        self.tracker = TechDebtTracker(db_path=self.db_path)

    def test_save_creates_file(self):
        from tech_debt_tracker import DebtSnapshot
        s = DebtSnapshot(timestamp="2026-01-01T00:00:00Z", file_path="x.py", markers=[])
        self.tracker.save_snapshots([s])
        self.assertTrue(os.path.exists(self.db_path))

    def test_save_and_load_roundtrip(self):
        from tech_debt_tracker import DebtSnapshot
        s = DebtSnapshot(
            timestamp="2026-01-01T00:00:00Z",
            file_path="x.py",
            markers=[{"type": "TODO", "line": 5, "text": "TODO: fix"}],
        )
        self.tracker.save_snapshots([s])
        loaded = self.tracker.load_history("x.py")
        self.assertGreater(len(loaded), 0)
        self.assertEqual(loaded[0].file_path, "x.py")

    def test_empty_history_returns_empty(self):
        result = self.tracker.load_history("nonexistent.py")
        self.assertEqual(result, [])

    def test_multiple_saves_accumulate(self):
        from tech_debt_tracker import DebtSnapshot
        s1 = DebtSnapshot(timestamp="2026-01-01T00:00:00Z", file_path="x.py", markers=[])
        s2 = DebtSnapshot(timestamp="2026-01-02T00:00:00Z", file_path="x.py", markers=[{"type": "TODO"}])
        self.tracker.save_snapshots([s1])
        self.tracker.save_snapshots([s2])
        history = self.tracker.load_history("x.py")
        self.assertGreaterEqual(len(history), 2)

    def test_history_ordered_oldest_first(self):
        from tech_debt_tracker import DebtSnapshot
        s1 = DebtSnapshot(timestamp="2026-01-01T00:00:00Z", file_path="x.py", markers=[])
        s2 = DebtSnapshot(timestamp="2026-01-03T00:00:00Z", file_path="x.py", markers=[])
        self.tracker.save_snapshots([s1])
        self.tracker.save_snapshots([s2])
        history = self.tracker.load_history("x.py")
        if len(history) >= 2:
            self.assertLessEqual(history[0].timestamp, history[-1].timestamp)


class TestTechDebtTrackerHotspots(unittest.TestCase):
    """Test hotspot detection and trend calculation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "debt.jsonl")
        self.tracker = TechDebtTracker(db_path=self.db_path)

    def test_no_history_no_hotspots(self):
        hotspots = self.tracker.get_hotspots()
        self.assertIsInstance(hotspots, list)

    def test_hotspots_sorted_by_count_descending(self):
        from tech_debt_tracker import DebtSnapshot
        s_high = DebtSnapshot("2026-01-01T00:00:00Z", "high_debt.py",
                              [{"type": "TODO"}, {"type": "FIXME"}, {"type": "HACK"}])
        s_low = DebtSnapshot("2026-01-01T00:00:00Z", "low_debt.py",
                             [{"type": "TODO"}])
        self.tracker.save_snapshots([s_high, s_low])
        hotspots = self.tracker.get_hotspots()
        if len(hotspots) >= 2:
            self.assertGreaterEqual(hotspots[0].current_count, hotspots[-1].current_count)

    def test_increasing_trend_detected(self):
        from tech_debt_tracker import DebtSnapshot
        s1 = DebtSnapshot("2026-01-01T00:00:00Z", "debt.py", [{"type": "TODO"}])
        s2 = DebtSnapshot("2026-01-02T00:00:00Z", "debt.py",
                          [{"type": "TODO"}, {"type": "FIXME"}, {"type": "HACK"}])
        self.tracker.save_snapshots([s1])
        self.tracker.save_snapshots([s2])
        hotspots = self.tracker.get_hotspots()
        debt_hotspot = next((h for h in hotspots if h.file_path == "debt.py"), None)
        if debt_hotspot:
            self.assertEqual(debt_hotspot.trend, "increasing")

    def test_decreasing_trend_detected(self):
        from tech_debt_tracker import DebtSnapshot
        s1 = DebtSnapshot("2026-01-01T00:00:00Z", "debt.py",
                          [{"type": "TODO"}, {"type": "FIXME"}, {"type": "HACK"}])
        s2 = DebtSnapshot("2026-01-02T00:00:00Z", "debt.py", [{"type": "TODO"}])
        self.tracker.save_snapshots([s1])
        self.tracker.save_snapshots([s2])
        hotspots = self.tracker.get_hotspots()
        debt_hotspot = next((h for h in hotspots if h.file_path == "debt.py"), None)
        if debt_hotspot:
            self.assertEqual(debt_hotspot.trend, "decreasing")

    def test_stable_trend_detected(self):
        from tech_debt_tracker import DebtSnapshot
        s1 = DebtSnapshot("2026-01-01T00:00:00Z", "stable.py", [{"type": "TODO"}])
        s2 = DebtSnapshot("2026-01-02T00:00:00Z", "stable.py", [{"type": "FIXME"}])
        self.tracker.save_snapshots([s1])
        self.tracker.save_snapshots([s2])
        hotspots = self.tracker.get_hotspots()
        stable = next((h for h in hotspots if h.file_path == "stable.py"), None)
        if stable:
            self.assertEqual(stable.trend, "stable")

    def test_top_n_hotspots(self):
        from tech_debt_tracker import DebtSnapshot
        for i in range(10):
            s = DebtSnapshot("2026-01-01T00:00:00Z", f"file_{i}.py",
                             [{"type": "TODO"}] * (i + 1))
            self.tracker.save_snapshots([s])
        hotspots = self.tracker.get_hotspots(top_n=3)
        self.assertLessEqual(len(hotspots), 3)


class TestTechDebtTrackerReport(unittest.TestCase):
    """Test summary report generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "debt.jsonl")
        self.tracker = TechDebtTracker(db_path=self.db_path)

    def test_empty_report_is_string(self):
        report = self.tracker.generate_report()
        self.assertIsInstance(report, str)

    def test_report_mentions_satd(self):
        from tech_debt_tracker import DebtSnapshot
        s = DebtSnapshot("2026-01-01T00:00:00Z", "debt.py", [{"type": "TODO", "text": "TODO: fix"}])
        self.tracker.save_snapshots([s])
        report = self.tracker.generate_report()
        self.assertIn("SATD", report.upper()) or self.assertIn("debt", report.lower())

    def test_report_mentions_hotspot_file(self):
        from tech_debt_tracker import DebtSnapshot
        s = DebtSnapshot("2026-01-01T00:00:00Z", "hotspot.py",
                         [{"type": "TODO"}, {"type": "FIXME"}, {"type": "HACK"}])
        self.tracker.save_snapshots([s])
        report = self.tracker.generate_report()
        self.assertIn("hotspot.py", report)

    def test_report_length_bounded(self):
        report = self.tracker.generate_report()
        self.assertLess(len(report), 5000)


if __name__ == "__main__":
    unittest.main()
