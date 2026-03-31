#!/usr/bin/env python3
"""
Tests for correction resurfacing (Prism mistake-learning pattern).

Tests the get_recent_corrections(), format_correction_warnings(),
and format_correction_briefing() functions added to resurfacer.py.

Run: python3 self-learning/tests/test_correction_resurfacer.py
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from resurfacer import (
    get_recent_corrections,
    format_correction_warnings,
    format_correction_briefing,
    _parse_timestamp,
    _load_journal_entries,
    JOURNAL_PATH,
    DEFAULT_LOOKBACK_DAYS,
    MAX_CORRECTION_WARNINGS,
)


def _make_correction_entry(
    error_pattern="old_string not found",
    error_tool="Edit",
    fix_tool="Edit",
    time_to_fix=15.0,
    resource="/tmp/test.py",
    timestamp=None,
):
    """Helper to create a correction_captured journal entry."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "timestamp": timestamp,
        "event_type": "correction_captured",
        "domain": "self_learning",
        "metrics": {
            "error_tool": error_tool,
            "fix_tool": fix_tool,
            "time_to_fix_seconds": time_to_fix,
            "error_pattern": error_pattern,
        },
        "notes": f"Error on {resource}: {error_pattern}. Fixed with {fix_tool} after {time_to_fix:.0f}s.",
        "strategy_version": "v0",
    }


def _write_journal(entries, path):
    """Write entries to a JSONL file."""
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestParseTimestamp(unittest.TestCase):
    """Test _parse_timestamp helper."""

    def test_iso_with_z(self):
        dt = _parse_timestamp("2026-03-30T12:00:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.hour, 12)

    def test_iso_with_offset(self):
        dt = _parse_timestamp("2026-03-30T12:00:00+00:00")
        self.assertIsNotNone(dt)

    def test_none_input(self):
        self.assertIsNone(_parse_timestamp(None))

    def test_empty_string(self):
        self.assertIsNone(_parse_timestamp(""))

    def test_garbage(self):
        self.assertIsNone(_parse_timestamp("not a date"))


class TestGetRecentCorrections(unittest.TestCase):
    """Test get_recent_corrections() query logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        if os.path.exists(self.journal_path):
            os.unlink(self.journal_path)
        os.rmdir(self.tmpdir)

    def _patch_journal(self, entries):
        """Write entries and patch JOURNAL_PATH."""
        _write_journal(entries, self.journal_path)
        return patch("resurfacer.JOURNAL_PATH", self.journal_path)

    def test_empty_journal(self):
        with self._patch_journal([]):
            result = get_recent_corrections()
        self.assertEqual(result, [])

    def test_no_corrections(self):
        entries = [{
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event_type": "session_outcome",
            "domain": "general",
        }]
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertEqual(result, [])

    def test_single_correction(self):
        entries = [_make_correction_entry()]
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["error_pattern"], "old_string not found")
        self.assertEqual(result[0]["error_tool"], "Edit")
        self.assertEqual(result[0]["count"], 1)

    def test_grouped_corrections(self):
        """Same error pattern + tool should be grouped."""
        entries = [
            _make_correction_entry(error_pattern="No such file", error_tool="Read"),
            _make_correction_entry(error_pattern="No such file", error_tool="Read"),
            _make_correction_entry(error_pattern="No such file", error_tool="Read"),
        ]
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 3)

    def test_different_patterns_separate(self):
        """Different error patterns should be separate entries."""
        entries = [
            _make_correction_entry(error_pattern="old_string not found"),
            _make_correction_entry(error_pattern="No such file"),
        ]
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertEqual(len(result), 2)

    def test_different_tools_separate(self):
        """Same pattern but different tools should be separate."""
        entries = [
            _make_correction_entry(error_pattern="Error:", error_tool="Bash"),
            _make_correction_entry(error_pattern="Error:", error_tool="Edit"),
        ]
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertEqual(len(result), 2)

    def test_old_corrections_excluded(self):
        """Corrections older than lookback window should be excluded."""
        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        entries = [_make_correction_entry(timestamp=old_ts)]
        with self._patch_journal(entries):
            result = get_recent_corrections(days=7)
        self.assertEqual(result, [])

    def test_old_corrections_included_with_longer_window(self):
        """Extending the window should include older corrections."""
        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        entries = [_make_correction_entry(timestamp=old_ts)]
        with self._patch_journal(entries):
            result = get_recent_corrections(days=14)
        self.assertEqual(len(result), 1)

    def test_sorted_by_frequency(self):
        """Most frequent errors should come first."""
        entries = [
            _make_correction_entry(error_pattern="rare error"),
            _make_correction_entry(error_pattern="common error"),
            _make_correction_entry(error_pattern="common error"),
            _make_correction_entry(error_pattern="common error"),
        ]
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertEqual(result[0]["error_pattern"], "common error")
        self.assertEqual(result[0]["count"], 3)

    def test_time_to_fix_avg(self):
        """Average time to fix should be computed correctly."""
        entries = [
            _make_correction_entry(time_to_fix=10.0),
            _make_correction_entry(time_to_fix=20.0),
            _make_correction_entry(time_to_fix=30.0),
        ]
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertEqual(result[0]["time_to_fix_avg"], 20.0)

    def test_max_warnings_cap(self):
        """Should cap at MAX_CORRECTION_WARNINGS."""
        entries = []
        for i in range(15):
            entries.append(_make_correction_entry(error_pattern=f"error_{i}"))
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertLessEqual(len(result), MAX_CORRECTION_WARNINGS)

    def test_resource_extraction(self):
        """Resources should be extracted from notes."""
        entries = [
            _make_correction_entry(resource="/foo/bar.py"),
            _make_correction_entry(resource="/foo/bar.py"),
        ]
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertIn("/foo/bar.py", result[0]["resources"])

    def test_mixed_event_types(self):
        """Only correction_captured events should be returned."""
        entries = [
            _make_correction_entry(),
            {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event_type": "session_outcome",
                "domain": "general",
            },
            {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event_type": "pain",
                "domain": "general",
            },
        ]
        with self._patch_journal(entries):
            result = get_recent_corrections()
        self.assertEqual(len(result), 1)

    def test_missing_journal_file(self):
        """Should return empty list if journal doesn't exist."""
        with patch("resurfacer.JOURNAL_PATH", "/nonexistent/path/journal.jsonl"):
            result = get_recent_corrections()
        self.assertEqual(result, [])

    def test_malformed_entries_skipped(self):
        """Malformed JSON lines should be skipped gracefully."""
        with open(self.journal_path, "w") as f:
            f.write(json.dumps(_make_correction_entry()) + "\n")
            f.write("not valid json\n")
            f.write(json.dumps(_make_correction_entry(error_pattern="second")) + "\n")
        with patch("resurfacer.JOURNAL_PATH", self.journal_path):
            result = get_recent_corrections()
        self.assertEqual(len(result), 2)


class TestFormatCorrectionWarnings(unittest.TestCase):
    """Test format_correction_warnings() output formatting."""

    def test_empty_list(self):
        result = format_correction_warnings([])
        self.assertEqual(result, [])

    def test_single_correction(self):
        corrections = [{
            "error_pattern": "old_string not found",
            "error_tool": "Edit",
            "fix_tool": "Edit",
            "count": 1,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "time_to_fix_avg": 15.0,
            "resources": ["/tmp/test.py"],
        }]
        result = format_correction_warnings(corrections)
        self.assertEqual(len(result), 1)
        self.assertIn("Edit", result[0])
        self.assertIn("old_string not found", result[0])

    def test_count_shown_for_repeats(self):
        corrections = [{
            "error_pattern": "No such file",
            "error_tool": "Read",
            "fix_tool": "Read",
            "count": 5,
            "last_seen": None,
            "time_to_fix_avg": 8.0,
            "resources": [],
        }]
        result = format_correction_warnings(corrections)
        self.assertIn("(5x)", result[0])

    def test_count_not_shown_for_single(self):
        corrections = [{
            "error_pattern": "Error",
            "error_tool": "Bash",
            "fix_tool": "Bash",
            "count": 1,
            "last_seen": None,
            "time_to_fix_avg": None,
            "resources": [],
        }]
        result = format_correction_warnings(corrections)
        self.assertNotIn("(1x)", result[0])

    def test_time_ago_days(self):
        old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        corrections = [{
            "error_pattern": "Error",
            "error_tool": "Bash",
            "fix_tool": "Bash",
            "count": 1,
            "last_seen": old,
            "time_to_fix_avg": None,
            "resources": [],
        }]
        result = format_correction_warnings(corrections)
        self.assertIn("3d ago", result[0])

    def test_time_ago_hours(self):
        recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        corrections = [{
            "error_pattern": "Error",
            "error_tool": "Bash",
            "fix_tool": "Bash",
            "count": 1,
            "last_seen": recent,
            "time_to_fix_avg": None,
            "resources": [],
        }]
        result = format_correction_warnings(corrections)
        self.assertIn("2h ago", result[0])

    def test_avg_fix_time_shown(self):
        corrections = [{
            "error_pattern": "Error",
            "error_tool": "Bash",
            "fix_tool": "Bash",
            "count": 2,
            "last_seen": None,
            "time_to_fix_avg": 42.5,
            "resources": [],
        }]
        result = format_correction_warnings(corrections)
        self.assertIn("avg fix: 42s", result[0])


class TestFormatCorrectionBriefing(unittest.TestCase):
    """Test format_correction_briefing() session block."""

    def test_empty_returns_empty(self):
        result = format_correction_briefing([])
        self.assertEqual(result, "")

    def test_has_header(self):
        corrections = [{
            "error_pattern": "Error",
            "error_tool": "Bash",
            "fix_tool": "Bash",
            "count": 1,
            "last_seen": None,
            "time_to_fix_avg": None,
            "resources": [],
        }]
        result = format_correction_briefing(corrections)
        self.assertIn("Recent corrections", result)

    def test_custom_days_in_header(self):
        corrections = [{
            "error_pattern": "Error",
            "error_tool": "Bash",
            "fix_tool": "Bash",
            "count": 1,
            "last_seen": None,
            "time_to_fix_avg": None,
            "resources": [],
        }]
        result = format_correction_briefing(corrections, days=14)
        self.assertIn("14 days", result)

    def test_bullet_format(self):
        corrections = [{
            "error_pattern": "Error A",
            "error_tool": "Bash",
            "fix_tool": "Bash",
            "count": 1,
            "last_seen": None,
            "time_to_fix_avg": None,
            "resources": [],
        }, {
            "error_pattern": "Error B",
            "error_tool": "Edit",
            "fix_tool": "Edit",
            "count": 2,
            "last_seen": None,
            "time_to_fix_avg": None,
            "resources": [],
        }]
        result = format_correction_briefing(corrections)
        self.assertEqual(result.count("  - "), 2)


class TestCLICorrections(unittest.TestCase):
    """Test the CLI 'corrections' subcommand."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        if os.path.exists(self.journal_path):
            os.unlink(self.journal_path)
        os.rmdir(self.tmpdir)

    def test_cli_corrections_json(self):
        """CLI corrections --json should output valid JSON."""
        _write_journal([_make_correction_entry()], self.journal_path)
        with patch("resurfacer.JOURNAL_PATH", self.journal_path):
            from resurfacer import main
            import io
            from contextlib import redirect_stdout
            captured = io.StringIO()
            with redirect_stdout(captured):
                with patch("sys.argv", ["resurfacer.py", "corrections", "--json"]):
                    main()
            output = captured.getvalue()
        data = json.loads(output)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_cli_corrections_text(self):
        """CLI corrections should output formatted text."""
        _write_journal([_make_correction_entry()], self.journal_path)
        with patch("resurfacer.JOURNAL_PATH", self.journal_path):
            from resurfacer import main
            import io
            from contextlib import redirect_stdout
            captured = io.StringIO()
            with redirect_stdout(captured):
                with patch("sys.argv", ["resurfacer.py", "corrections"]):
                    main()
            output = captured.getvalue()
        self.assertIn("Recent corrections", output)

    def test_cli_corrections_empty(self):
        """CLI corrections with no data should say so."""
        _write_journal([], self.journal_path)
        with patch("resurfacer.JOURNAL_PATH", self.journal_path):
            from resurfacer import main
            import io
            from contextlib import redirect_stdout
            captured = io.StringIO()
            with redirect_stdout(captured):
                with patch("sys.argv", ["resurfacer.py", "corrections"]):
                    main()
            output = captured.getvalue()
        self.assertIn("No corrections", output)


if __name__ == "__main__":
    unittest.main()
