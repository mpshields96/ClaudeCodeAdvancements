#!/usr/bin/env python3
"""Tests for batch_report.py — aggregate trace analysis across sessions."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def _write_session_jsonl(tmpdir, session_id, entries):
    """Write a fake JSONL transcript for testing."""
    path = os.path.join(tmpdir, f"{session_id}.jsonl")
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path


def _make_assistant_entry(tool_name=None, file_path=None, is_error=False, output_tokens=100):
    """Create a minimal assistant entry."""
    entry = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "usage": {"output_tokens": output_tokens},
        },
        "sessionId": "test-session",
    }
    if tool_name:
        entry["message"]["content"] = [
            {
                "type": "tool_use",
                "name": tool_name,
                "input": {"file_path": file_path} if file_path else {},
            }
        ]
    return entry


def _make_result_entry(is_error=False):
    """Create a tool_result entry."""
    return {
        "type": "tool_result",
        "tool_result": {"is_error": is_error},
    }


class TestBatchReport(unittest.TestCase):
    """Test the BatchReport aggregation."""

    def test_import(self):
        """Module can be imported."""
        from batch_report import BatchReport
        self.assertTrue(callable(BatchReport))

    def test_empty_directory(self):
        """Empty directory returns empty report."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            report = BatchReport(tmpdir)
            result = report.analyze()
            self.assertEqual(result["sessions_analyzed"], 0)

    def test_single_session(self):
        """Single session produces valid aggregate."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [
                _make_assistant_entry("Read", "/foo/bar.py"),
                _make_result_entry(),
                _make_assistant_entry("Edit", "/foo/bar.py"),
                _make_result_entry(),
            ]
            _write_session_jsonl(tmpdir, "session-1", entries)
            report = BatchReport(tmpdir)
            result = report.analyze()
            self.assertEqual(result["sessions_analyzed"], 1)
            self.assertIn("score_avg", result)
            self.assertIn("score_min", result)
            self.assertIn("score_max", result)

    def test_multiple_sessions(self):
        """Multiple sessions are aggregated."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                entries = [
                    _make_assistant_entry("Read", f"/foo/file{i}.py"),
                    _make_result_entry(),
                ]
                _write_session_jsonl(tmpdir, f"session-{i}", entries)
            report = BatchReport(tmpdir)
            result = report.analyze()
            self.assertEqual(result["sessions_analyzed"], 3)

    def test_retry_hotspots(self):
        """Retry hotspots are tracked across sessions."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            # Session with retries on same file
            entries = []
            for _ in range(5):
                entries.append(_make_assistant_entry("Edit", "/foo/INDEX.md"))
                entries.append(_make_result_entry())
            _write_session_jsonl(tmpdir, "session-retries", entries)
            report = BatchReport(tmpdir)
            result = report.analyze()
            hotspots = result.get("retry_hotspots", [])
            # Should detect the retry hotspot
            self.assertIsInstance(hotspots, list)

    def test_waste_stats(self):
        """Waste statistics are aggregated."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [
                _make_assistant_entry("Read", "/foo/a.py"),
                _make_result_entry(),
                _make_assistant_entry("Read", "/foo/b.py"),
                _make_result_entry(),
                # No reference to a.py or b.py after reading
            ]
            _write_session_jsonl(tmpdir, "session-waste", entries)
            report = BatchReport(tmpdir)
            result = report.analyze()
            self.assertIn("waste_avg", result)

    def test_score_distribution(self):
        """Score distribution buckets are correct."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(5):
                entries = [
                    _make_assistant_entry("Read", f"/foo/{i}.py"),
                    _make_result_entry(),
                ]
                _write_session_jsonl(tmpdir, f"s{i}", entries)
            report = BatchReport(tmpdir)
            result = report.analyze()
            dist = result.get("score_distribution", {})
            self.assertIn("excellent", dist)  # 80+
            self.assertIn("good", dist)       # 60-79
            self.assertIn("poor", dist)       # 40-59
            self.assertIn("critical", dist)   # <40

    def test_skips_non_jsonl(self):
        """Non-JSONL files are ignored."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a non-JSONL file
            with open(os.path.join(tmpdir, "notes.txt"), "w") as f:
                f.write("not a transcript\n")
            entries = [_make_assistant_entry("Read", "/foo/a.py"), _make_result_entry()]
            _write_session_jsonl(tmpdir, "real-session", entries)
            report = BatchReport(tmpdir)
            result = report.analyze()
            self.assertEqual(result["sessions_analyzed"], 1)

    def test_skips_subagent_dirs(self):
        """Subagent directories are not traversed."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            # Main session
            entries = [_make_assistant_entry("Read", "/foo/a.py"), _make_result_entry()]
            _write_session_jsonl(tmpdir, "main-session", entries)
            # Subagent dir (should be skipped)
            sub_dir = os.path.join(tmpdir, "main-session", "subagents")
            os.makedirs(sub_dir, exist_ok=True)
            _write_session_jsonl(sub_dir, "agent-sub", entries)
            report = BatchReport(tmpdir)
            result = report.analyze()
            self.assertEqual(result["sessions_analyzed"], 1)

    def test_text_report(self):
        """Text report is a non-empty string."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [_make_assistant_entry("Read", "/foo/a.py"), _make_result_entry()]
            _write_session_jsonl(tmpdir, "s1", entries)
            report = BatchReport(tmpdir)
            report.analyze()
            text = report.text_report()
            self.assertIsInstance(text, str)
            self.assertGreater(len(text), 50)

    def test_json_output(self):
        """JSON output is valid JSON."""
        from batch_report import BatchReport
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [_make_assistant_entry("Read", "/foo/a.py"), _make_result_entry()]
            _write_session_jsonl(tmpdir, "s1", entries)
            report = BatchReport(tmpdir)
            result = report.analyze()
            # Should be JSON-serializable
            json_str = json.dumps(result)
            self.assertIsInstance(json.loads(json_str), dict)


class TestBatchReportCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_cli_help(self):
        """CLI accepts --help."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "batch_report.py"), "--help"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)

    def test_cli_with_dir(self):
        """CLI accepts a directory argument."""
        import subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [_make_assistant_entry("Read", "/foo/a.py"), _make_result_entry()]
            _write_session_jsonl(tmpdir, "s1", entries)
            result = subprocess.run(
                [sys.executable, str(Path(__file__).parent.parent / "batch_report.py"), tmpdir],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("sessions", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
