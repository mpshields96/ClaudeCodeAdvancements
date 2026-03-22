#!/usr/bin/env python3
"""Tests for apf_session_tracker.py — MT-27 Phase 5: APF trend tracking per session."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add parent dirs to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestRecordSnapshot(unittest.TestCase):
    """Test record_snapshot() — appending APF snapshots per session."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.snapshot_path = Path(self.tmpdir) / "apf_snapshots.jsonl"
        self.findings_path = Path(self.tmpdir) / "FINDINGS_LOG.md"

    def _write_findings(self, entries):
        """Write mock findings log entries."""
        lines = []
        for e in entries:
            date = e.get("date", "2026-03-21")
            verdict = e.get("verdict", "SKIP")
            frontier = e.get("frontier", "Frontier 1: Memory")
            title = e.get("title", "Test finding")
            score = e.get("score", 10)
            lines.append(
                f'[{date}] [{verdict}] [{frontier}] "{title}" ({score}pts, 5c, r/ClaudeCode)'
            )
        self.findings_path.write_text("\n".join(lines))

    def test_creates_snapshot_file(self):
        from apf_session_tracker import record_snapshot

        self._write_findings([{"verdict": "BUILD"}, {"verdict": "SKIP"}])
        record_snapshot("S115", self.findings_path, self.snapshot_path)
        self.assertTrue(self.snapshot_path.exists())

    def test_snapshot_content(self):
        from apf_session_tracker import record_snapshot

        self._write_findings([
            {"verdict": "BUILD"},
            {"verdict": "ADAPT"},
            {"verdict": "SKIP"},
            {"verdict": "SKIP"},
        ])
        record_snapshot("S115", self.findings_path, self.snapshot_path)

        lines = self.snapshot_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 1)
        snap = json.loads(lines[0])
        self.assertEqual(snap["session"], "S115")
        self.assertEqual(snap["total"], 4)
        self.assertEqual(snap["apf"], 50.0)
        self.assertEqual(snap["build"], 1)
        self.assertEqual(snap["adapt"], 1)
        self.assertIn("timestamp", snap)

    def test_appends_multiple_sessions(self):
        from apf_session_tracker import record_snapshot

        self._write_findings([{"verdict": "BUILD"}, {"verdict": "SKIP"}])
        record_snapshot("S114", self.findings_path, self.snapshot_path)

        # Add more findings
        self._write_findings([
            {"verdict": "BUILD"},
            {"verdict": "SKIP"},
            {"verdict": "BUILD"},
        ])
        record_snapshot("S115", self.findings_path, self.snapshot_path)

        lines = self.snapshot_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)
        s1 = json.loads(lines[0])
        s2 = json.loads(lines[1])
        self.assertEqual(s1["session"], "S114")
        self.assertEqual(s2["session"], "S115")

    def test_empty_findings(self):
        from apf_session_tracker import record_snapshot

        self.findings_path.write_text("")
        record_snapshot("S115", self.findings_path, self.snapshot_path)

        lines = self.snapshot_path.read_text().strip().split("\n")
        snap = json.loads(lines[0])
        self.assertEqual(snap["total"], 0)
        self.assertEqual(snap["apf"], 0.0)

    def test_missing_findings_file(self):
        from apf_session_tracker import record_snapshot

        # Don't create findings file
        record_snapshot("S115", Path(self.tmpdir) / "nonexistent.md", self.snapshot_path)

        lines = self.snapshot_path.read_text().strip().split("\n")
        snap = json.loads(lines[0])
        self.assertEqual(snap["total"], 0)

    def test_snapshot_includes_by_frontier(self):
        from apf_session_tracker import record_snapshot

        self._write_findings([
            {"verdict": "BUILD", "frontier": "Frontier 1: Memory"},
            {"verdict": "BUILD", "frontier": "Frontier 2: Spec"},
            {"verdict": "SKIP", "frontier": "Frontier 3: Context"},
        ])
        record_snapshot("S115", self.findings_path, self.snapshot_path)

        snap = json.loads(self.snapshot_path.read_text().strip())
        self.assertIn("by_frontier", snap)
        self.assertIsInstance(snap["by_frontier"], dict)

    def test_duplicate_session_appends(self):
        """Recording same session twice just appends another line (append-only)."""
        from apf_session_tracker import record_snapshot

        self._write_findings([{"verdict": "BUILD"}])
        record_snapshot("S115", self.findings_path, self.snapshot_path)
        record_snapshot("S115", self.findings_path, self.snapshot_path)

        lines = self.snapshot_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)


class TestGetTrend(unittest.TestCase):
    """Test get_trend() — reading snapshots and returning trend data."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.snapshot_path = Path(self.tmpdir) / "apf_snapshots.jsonl"

    def _write_snapshots(self, snapshots):
        lines = [json.dumps(s) for s in snapshots]
        self.snapshot_path.write_text("\n".join(lines))

    def test_empty_file(self):
        from apf_session_tracker import get_trend

        self.snapshot_path.write_text("")
        trend = get_trend(self.snapshot_path)
        self.assertEqual(trend, [])

    def test_missing_file(self):
        from apf_session_tracker import get_trend

        trend = get_trend(Path(self.tmpdir) / "nonexistent.jsonl")
        self.assertEqual(trend, [])

    def test_single_snapshot(self):
        from apf_session_tracker import get_trend

        self._write_snapshots([{
            "session": "S114",
            "total": 335,
            "apf": 22.7,
            "build": 30,
            "adapt": 46,
            "timestamp": "2026-03-21T10:00:00",
        }])
        trend = get_trend(self.snapshot_path)
        self.assertEqual(len(trend), 1)
        self.assertEqual(trend[0]["session"], "S114")
        self.assertEqual(trend[0]["apf"], 22.7)

    def test_multiple_snapshots_with_delta(self):
        from apf_session_tracker import get_trend

        self._write_snapshots([
            {"session": "S113", "total": 330, "apf": 21.0, "build": 28, "adapt": 41, "timestamp": "2026-03-21T08:00:00"},
            {"session": "S114", "total": 335, "apf": 22.7, "build": 30, "adapt": 46, "timestamp": "2026-03-21T10:00:00"},
            {"session": "S115", "total": 340, "apf": 24.1, "build": 33, "adapt": 49, "timestamp": "2026-03-21T12:00:00"},
        ])
        trend = get_trend(self.snapshot_path)
        self.assertEqual(len(trend), 3)
        # First has no delta
        self.assertIsNone(trend[0].get("apf_delta"))
        # Second has delta
        self.assertAlmostEqual(trend[1]["apf_delta"], 1.7, places=1)
        # Third has delta
        self.assertAlmostEqual(trend[2]["apf_delta"], 1.4, places=1)

    def test_corrupt_line_skipped(self):
        from apf_session_tracker import get_trend

        self.snapshot_path.write_text(
            '{"session":"S113","total":330,"apf":21.0}\n'
            'not valid json\n'
            '{"session":"S114","total":335,"apf":22.7}\n'
        )
        trend = get_trend(self.snapshot_path)
        self.assertEqual(len(trend), 2)
        self.assertEqual(trend[0]["session"], "S113")
        self.assertEqual(trend[1]["session"], "S114")


class TestFormatTrend(unittest.TestCase):
    """Test format_trend() — pretty-printing the trend."""

    def test_empty_trend(self):
        from apf_session_tracker import format_trend

        result = format_trend([])
        self.assertIn("No APF snapshots", result)

    def test_single_entry(self):
        from apf_session_tracker import format_trend

        trend = [{"session": "S115", "apf": 22.7, "total": 335}]
        result = format_trend(trend)
        self.assertIn("S115", result)
        self.assertIn("22.7", result)

    def test_delta_shown(self):
        from apf_session_tracker import format_trend

        trend = [
            {"session": "S114", "apf": 21.0, "total": 330},
            {"session": "S115", "apf": 22.7, "total": 335, "apf_delta": 1.7},
        ]
        result = format_trend(trend)
        self.assertIn("+1.7", result)

    def test_negative_delta(self):
        from apf_session_tracker import format_trend

        trend = [
            {"session": "S114", "apf": 22.7, "total": 335},
            {"session": "S115", "apf": 20.0, "total": 340, "apf_delta": -2.7},
        ]
        result = format_trend(trend)
        self.assertIn("-2.7", result)

    def test_bar_chart(self):
        from apf_session_tracker import format_trend

        trend = [{"session": "S115", "apf": 25.0, "total": 335}]
        result = format_trend(trend)
        # Should have some visual indicator
        self.assertIn("#", result)


class TestLatestSnapshot(unittest.TestCase):
    """Test get_latest_snapshot() — returning the most recent snapshot."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.snapshot_path = Path(self.tmpdir) / "apf_snapshots.jsonl"

    def test_empty_file(self):
        from apf_session_tracker import get_latest_snapshot

        self.snapshot_path.write_text("")
        result = get_latest_snapshot(self.snapshot_path)
        self.assertIsNone(result)

    def test_returns_last_entry(self):
        from apf_session_tracker import get_latest_snapshot

        self.snapshot_path.write_text(
            '{"session":"S113","apf":21.0}\n'
            '{"session":"S114","apf":22.7}\n'
        )
        result = get_latest_snapshot(self.snapshot_path)
        self.assertEqual(result["session"], "S114")
        self.assertEqual(result["apf"], 22.7)


class TestCompactStatus(unittest.TestCase):
    """Test compact_status() — one-liner for wrap reports."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.snapshot_path = Path(self.tmpdir) / "apf_snapshots.jsonl"

    def test_no_snapshots(self):
        from apf_session_tracker import compact_status

        self.snapshot_path.write_text("")
        result = compact_status(self.snapshot_path)
        self.assertIn("No snapshots", result)

    def test_single_snapshot(self):
        from apf_session_tracker import compact_status

        self.snapshot_path.write_text('{"session":"S115","apf":22.7,"total":335}\n')
        result = compact_status(self.snapshot_path)
        self.assertIn("22.7%", result)
        self.assertIn("S115", result)

    def test_with_delta(self):
        from apf_session_tracker import compact_status

        self.snapshot_path.write_text(
            '{"session":"S114","apf":21.0,"total":330}\n'
            '{"session":"S115","apf":22.7,"total":335}\n'
        )
        result = compact_status(self.snapshot_path)
        self.assertIn("+1.7", result)

    def test_negative_delta(self):
        from apf_session_tracker import compact_status

        self.snapshot_path.write_text(
            '{"session":"S114","apf":22.7,"total":335}\n'
            '{"session":"S115","apf":20.0,"total":340}\n'
        )
        result = compact_status(self.snapshot_path)
        self.assertIn("-2.7", result)


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.snapshot_path = Path(self.tmpdir) / "apf_snapshots.jsonl"
        self.findings_path = Path(self.tmpdir) / "FINDINGS_LOG.md"
        self.findings_path.write_text(
            '[2026-03-21] [BUILD] [Frontier 1: Memory] "Test" (10pts, 5c, r/ClaudeCode)\n'
            '[2026-03-21] [SKIP] [Frontier 2: Spec] "Other" (5pts, 2c, r/ClaudeCode)\n'
        )

    def test_snapshot_command(self):
        from apf_session_tracker import record_snapshot

        # Test record_snapshot directly with explicit paths (CLI patches are fragile)
        snap = record_snapshot("S115", self.findings_path, self.snapshot_path)
        self.assertTrue(self.snapshot_path.exists())
        self.assertEqual(snap["session"], "S115")
        self.assertEqual(snap["apf"], 50.0)

    def test_trend_command_empty(self):
        from apf_session_tracker import main

        self.snapshot_path.write_text("")
        with patch("sys.argv", ["prog", "trend"]):
            with patch("apf_session_tracker.DEFAULT_SNAPSHOT_PATH", self.snapshot_path):
                main()  # Should not raise

    def test_status_command(self):
        from apf_session_tracker import main

        self.snapshot_path.write_text('{"session":"S115","apf":22.7,"total":335}\n')
        with patch("sys.argv", ["prog", "status"]):
            with patch("apf_session_tracker.DEFAULT_SNAPSHOT_PATH", self.snapshot_path):
                main()  # Should not raise

    def test_unknown_command(self):
        from apf_session_tracker import main

        with patch("sys.argv", ["prog", "bogus"]):
            with self.assertRaises(SystemExit):
                main()


if __name__ == "__main__":
    unittest.main()
