"""Tests for trace_analyzer.py — MT-7 transcript pattern analysis.

Tests written first (TDD). Run with: python3 test_trace_analyzer.py
"""
import json
import tempfile
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from trace_analyzer import (
    TranscriptEntry,
    TranscriptSession,
    RetryDetector,
    WasteDetector,
    EfficiencyCalculator,
    VelocityCalculator,
    TraceAnalyzer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(offset_seconds=0):
    """ISO 8601 timestamp with optional offset from a base time."""
    base = datetime(2026, 3, 16, 10, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).isoformat()


def _tool_use_entry(tool_name, file_path=None, command=None, offset=0):
    content = {
        "type": "tool_use",
        "id": f"tool_{offset}",
        "name": tool_name,
        "input": {},
    }
    if file_path:
        content["input"]["file_path"] = file_path
    if command:
        content["input"]["command"] = command
    return {
        "type": "assistant",
        "uuid": f"uuid_asst_{offset}",
        "timestamp": _ts(offset),
        "sessionId": "sess1",
        "parentUuid": None,
        "isSidechain": False,
        "message": {
            "role": "assistant",
            "content": [content],
            "usage": {
                "input_tokens": 10,
                "cache_read_input_tokens": 50000,
                "cache_creation_input_tokens": 0,
                "output_tokens": 20,
                "stop_reason": "tool_use",
            },
        },
    }


def _tool_result_entry(tool_use_id, is_error=False, offset=0):
    return {
        "type": "user",
        "uuid": f"uuid_result_{offset}",
        "timestamp": _ts(offset),
        "sessionId": "sess1",
        "parentUuid": f"uuid_asst_{offset - 1}",
        "isSidechain": False,
        "toolUseResult": {"type": "text"},
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "is_error": is_error,
                    "content": "error output" if is_error else "ok",
                }
            ],
        },
    }


def _progress_entry(offset=0):
    return {
        "type": "progress",
        "uuid": f"uuid_prog_{offset}",
        "timestamp": _ts(offset),
        "sessionId": "sess1",
        "parentUuid": None,
        "isSidechain": False,
        "message": {"type": "progress", "content": "doing stuff"},
    }


def _queue_entry(offset=0):
    return {
        "type": "queue-operation",
        "uuid": f"uuid_q_{offset}",
        "timestamp": _ts(offset),
        "sessionId": "sess1",
    }


def _user_message_entry(text="hello", offset=0):
    return {
        "type": "user",
        "uuid": f"uuid_user_{offset}",
        "timestamp": _ts(offset),
        "sessionId": "sess1",
        "parentUuid": None,
        "isSidechain": False,
        "permissionMode": "default",
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": text}],
        },
    }


def _bash_commit_entry(offset=0):
    return _tool_use_entry("Bash", command="git commit -m 'test'", offset=offset)


def _write_file_entry(file_path, offset=0):
    return _tool_use_entry("Write", file_path=file_path, offset=offset)


def _make_jsonl(entries):
    """Write entries to a temp file and return path."""
    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for e in entries:
        tf.write(json.dumps(e) + "\n")
    tf.close()
    return tf.name


# ---------------------------------------------------------------------------
# TranscriptEntry tests
# ---------------------------------------------------------------------------

class TestTranscriptEntry(unittest.TestCase):

    def test_assistant_tool_use_entry(self):
        raw = _tool_use_entry("Read", file_path="foo.py", offset=0)
        entry = TranscriptEntry(raw)
        self.assertEqual(entry.type, "assistant")
        self.assertEqual(entry.tool_name, "Read")
        self.assertEqual(entry.file_path, "foo.py")
        self.assertFalse(entry.is_error)

    def test_tool_result_is_error(self):
        raw = _tool_result_entry("tool_0", is_error=True, offset=1)
        entry = TranscriptEntry(raw)
        self.assertEqual(entry.type, "user")
        self.assertTrue(entry.is_error)

    def test_tool_result_not_error(self):
        raw = _tool_result_entry("tool_0", is_error=False, offset=1)
        entry = TranscriptEntry(raw)
        self.assertFalse(entry.is_error)

    def test_progress_entry(self):
        raw = _progress_entry()
        entry = TranscriptEntry(raw)
        self.assertEqual(entry.type, "progress")
        self.assertTrue(entry.is_noise)

    def test_queue_entry_is_noise(self):
        raw = _queue_entry()
        entry = TranscriptEntry(raw)
        self.assertTrue(entry.is_noise)

    def test_usage_extraction(self):
        raw = _tool_use_entry("Bash", offset=0)
        entry = TranscriptEntry(raw)
        self.assertEqual(entry.usage["output_tokens"], 20)
        self.assertEqual(entry.usage["input_tokens"], 10)

    def test_no_usage_on_user_entry(self):
        raw = _user_message_entry()
        entry = TranscriptEntry(raw)
        self.assertIsNone(entry.usage)

    def test_bash_command_extraction(self):
        raw = _tool_use_entry("Bash", command="ls -la", offset=0)
        entry = TranscriptEntry(raw)
        self.assertEqual(entry.tool_name, "Bash")
        self.assertEqual(entry.command, "ls -la")

    def test_timestamp_parsed(self):
        raw = _tool_use_entry("Read", offset=0)
        entry = TranscriptEntry(raw)
        self.assertIsNotNone(entry.timestamp)

    def test_uuid_exposed(self):
        raw = _tool_use_entry("Read", offset=5)
        entry = TranscriptEntry(raw)
        self.assertEqual(entry.uuid, "uuid_asst_5")

    def test_assistant_text_not_tool(self):
        raw = {
            "type": "assistant",
            "uuid": "u1",
            "timestamp": _ts(),
            "sessionId": "s1",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "hello"}],
            },
        }
        entry = TranscriptEntry(raw)
        self.assertIsNone(entry.tool_name)

    def test_is_orientation_read(self):
        raw = _tool_use_entry("Read", file_path="CLAUDE.md", offset=5)
        entry = TranscriptEntry(raw)
        self.assertTrue(entry.is_orientation)

    def test_non_orientation_read(self):
        raw = _tool_use_entry("Read", file_path="foo.py", offset=5)
        entry = TranscriptEntry(raw)
        self.assertFalse(entry.is_orientation)


# ---------------------------------------------------------------------------
# TranscriptSession tests
# ---------------------------------------------------------------------------

class TestTranscriptSession(unittest.TestCase):

    def _make_session(self, entries):
        path = _make_jsonl(entries)
        try:
            return TranscriptSession(path)
        finally:
            os.unlink(path)

    def test_loads_file(self):
        entries = [_tool_use_entry("Read", file_path="foo.py", offset=i) for i in range(3)]
        path = _make_jsonl(entries)
        sess = TranscriptSession(path)
        os.unlink(path)
        self.assertEqual(len(sess.all_entries), 3)

    def test_filters_noise(self):
        entries = [
            _tool_use_entry("Read", file_path="foo.py", offset=0),
            _progress_entry(offset=1),
            _queue_entry(offset=2),
            _tool_use_entry("Write", file_path="bar.py", offset=3),
        ]
        sess = self._make_session(entries)
        self.assertEqual(len(sess.signal_entries), 2)

    def test_all_entries_includes_noise(self):
        entries = [_progress_entry(), _tool_use_entry("Read")]
        sess = self._make_session(entries)
        self.assertEqual(len(sess.all_entries), 2)

    def test_tool_calls_only_assistant(self):
        entries = [
            _tool_use_entry("Read", offset=0),
            _tool_result_entry("tool_0", offset=1),
            _user_message_entry(offset=2),
        ]
        sess = self._make_session(entries)
        tool_calls = sess.tool_calls
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].tool_name, "Read")

    def test_total_output_tokens(self):
        entries = [
            _tool_use_entry("Read", offset=0),
            _tool_use_entry("Write", offset=1),
        ]
        sess = self._make_session(entries)
        self.assertEqual(sess.total_output_tokens, 40)

    def test_session_id(self):
        entries = [_tool_use_entry("Read")]
        sess = self._make_session(entries)
        self.assertEqual(sess.session_id, "sess1")

    def test_unique_files_touched(self):
        entries = [
            _tool_use_entry("Read", file_path="a.py", offset=0),
            _tool_use_entry("Edit", file_path="a.py", offset=1),
            _tool_use_entry("Read", file_path="b.py", offset=2),
        ]
        sess = self._make_session(entries)
        self.assertEqual(len(sess.unique_files), 2)

    def test_empty_file(self):
        path = _make_jsonl([])
        sess = TranscriptSession(path)
        os.unlink(path)
        self.assertEqual(len(sess.all_entries), 0)


# ---------------------------------------------------------------------------
# RetryDetector tests
# ---------------------------------------------------------------------------

class TestRetryDetector(unittest.TestCase):

    def _make_session(self, entries):
        path = _make_jsonl(entries)
        try:
            return TranscriptSession(path)
        finally:
            os.unlink(path)

    def test_no_retries(self):
        entries = [
            _tool_use_entry("Read", file_path="a.py", offset=0),
            _tool_use_entry("Edit", file_path="b.py", offset=1),
        ]
        sess = self._make_session(entries)
        det = RetryDetector()
        result = det.detect(sess)
        self.assertEqual(result["retries"], [])

    def test_minor_retry_3_consecutive(self):
        entries = [
            _tool_use_entry("Edit", file_path="foo.py", offset=0),
            _tool_use_entry("Edit", file_path="foo.py", offset=1),
            _tool_use_entry("Edit", file_path="foo.py", offset=2),
        ]
        sess = self._make_session(entries)
        det = RetryDetector()
        result = det.detect(sess)
        self.assertEqual(len(result["retries"]), 1)
        self.assertEqual(result["retries"][0]["severity"], "minor")
        self.assertEqual(result["retries"][0]["file"], "foo.py")

    def test_major_retry_5_consecutive(self):
        entries = [_tool_use_entry("Edit", file_path="foo.py", offset=i) for i in range(5)]
        sess = self._make_session(entries)
        det = RetryDetector()
        result = det.detect(sess)
        self.assertEqual(result["retries"][0]["severity"], "major")

    def test_critical_retry_8_consecutive(self):
        entries = [_tool_use_entry("Edit", file_path="foo.py", offset=i) for i in range(8)]
        sess = self._make_session(entries)
        det = RetryDetector()
        result = det.detect(sess)
        self.assertEqual(result["retries"][0]["severity"], "critical")

    def test_retry_resets_on_different_file(self):
        entries = [
            _tool_use_entry("Edit", file_path="foo.py", offset=0),
            _tool_use_entry("Edit", file_path="foo.py", offset=1),
            _tool_use_entry("Edit", file_path="bar.py", offset=2),
            _tool_use_entry("Edit", file_path="foo.py", offset=3),
        ]
        sess = self._make_session(entries)
        det = RetryDetector()
        result = det.detect(sess)
        self.assertEqual(result["retries"], [])

    def test_error_weighted_retry(self):
        entries = [
            _tool_use_entry("Edit", file_path="foo.py", offset=0),
            _tool_result_entry("tool_0", is_error=True, offset=1),
            _tool_use_entry("Edit", file_path="foo.py", offset=2),
            _tool_result_entry("tool_2", is_error=True, offset=3),
            _tool_use_entry("Edit", file_path="foo.py", offset=4),
        ]
        sess = self._make_session(entries)
        det = RetryDetector()
        result = det.detect(sess)
        self.assertTrue(result["retries"][0]["error_confirmed"])

    def test_count_in_result(self):
        entries = [_tool_use_entry("Edit", file_path="foo.py", offset=i) for i in range(5)]
        sess = self._make_session(entries)
        det = RetryDetector()
        result = det.detect(sess)
        self.assertEqual(result["retries"][0]["count"], 5)


# ---------------------------------------------------------------------------
# WasteDetector tests
# ---------------------------------------------------------------------------

class TestWasteDetector(unittest.TestCase):

    def _make_session(self, entries):
        path = _make_jsonl(entries)
        try:
            return TranscriptSession(path)
        finally:
            os.unlink(path)

    def test_no_waste_when_file_used(self):
        entries = [
            _tool_use_entry("Read", file_path="foo.py", offset=0),
            _tool_use_entry("Edit", file_path="foo.py", offset=1),
        ]
        sess = self._make_session(entries)
        det = WasteDetector()
        result = det.detect(sess)
        self.assertEqual(result["wasted_reads"], [])

    def test_waste_when_file_not_used(self):
        entries = [
            _tool_use_entry("Read", file_path="foo.py", offset=0),
            _tool_use_entry("Read", file_path="bar.py", offset=1),
            _tool_use_entry("Edit", file_path="other.py", offset=2),
        ]
        sess = self._make_session(entries)
        det = WasteDetector()
        result = det.detect(sess)
        paths = [w["file"] for w in result["wasted_reads"]]
        self.assertIn("foo.py", paths)

    def test_orientation_reads_not_flagged(self):
        entries = [
            _tool_use_entry("Read", file_path="CLAUDE.md", offset=0),
            _tool_use_entry("Read", file_path="SESSION_STATE.md", offset=1),
            _tool_use_entry("Bash", command="echo done", offset=2),
        ]
        sess = self._make_session(entries)
        det = WasteDetector()
        result = det.detect(sess)
        self.assertEqual(result["wasted_reads"], [])

    def test_window_is_20_entries(self):
        # Read at 0, no reference in entries 1-20, but reference at 21
        entries = [_tool_use_entry("Read", file_path="foo.py", offset=0)]
        for i in range(1, 21):
            entries.append(_tool_use_entry("Bash", command="echo x", offset=i))
        entries.append(_tool_use_entry("Edit", file_path="foo.py", offset=21))
        sess = self._make_session(entries)
        det = WasteDetector()
        result = det.detect(sess)
        # Read at position 0, reference at position 21 — outside 20-entry window
        self.assertEqual(len(result["wasted_reads"]), 1)

    def test_within_window_not_wasted(self):
        entries = [_tool_use_entry("Read", file_path="foo.py", offset=0)]
        for i in range(1, 10):
            entries.append(_tool_use_entry("Bash", command="echo x", offset=i))
        entries.append(_tool_use_entry("Edit", file_path="foo.py", offset=10))
        sess = self._make_session(entries)
        det = WasteDetector()
        result = det.detect(sess)
        self.assertEqual(result["wasted_reads"], [])

    def test_waste_rate_calculation(self):
        entries = [
            _tool_use_entry("Read", file_path="foo.py", offset=0),
            _tool_use_entry("Read", file_path="bar.py", offset=1),
            _tool_use_entry("Edit", file_path="foo.py", offset=2),
        ]
        sess = self._make_session(entries)
        det = WasteDetector()
        result = det.detect(sess)
        # 1 read used (foo.py), 1 wasted (bar.py) → 50%
        self.assertAlmostEqual(result["waste_rate"], 0.5)


# ---------------------------------------------------------------------------
# EfficiencyCalculator tests
# ---------------------------------------------------------------------------

class TestEfficiencyCalculator(unittest.TestCase):

    def _make_session(self, entries):
        path = _make_jsonl(entries)
        try:
            return TranscriptSession(path)
        finally:
            os.unlink(path)

    def test_good_efficiency(self):
        entries = [_tool_use_entry("Edit", file_path=f"file{i}.py", offset=i) for i in range(4)]
        sess = self._make_session(entries)
        calc = EfficiencyCalculator()
        result = calc.calculate(sess)
        self.assertEqual(result["rating"], "good")

    def test_poor_efficiency(self):
        # 1 unique file, 20 tool calls
        entries = [_tool_use_entry("Edit", file_path="foo.py", offset=i) for i in range(20)]
        sess = self._make_session(entries)
        calc = EfficiencyCalculator()
        result = calc.calculate(sess)
        self.assertEqual(result["rating"], "poor")

    def test_mediocre_efficiency(self):
        # 2 unique files, 15 tool calls → 0.13
        entries = []
        for i in range(15):
            fp = "a.py" if i < 8 else "b.py"
            entries.append(_tool_use_entry("Edit", file_path=fp, offset=i))
        sess = self._make_session(entries)
        calc = EfficiencyCalculator()
        result = calc.calculate(sess)
        self.assertEqual(result["rating"], "mediocre")

    def test_ratio_in_result(self):
        entries = [_tool_use_entry("Edit", file_path=f"f{i}.py", offset=i) for i in range(5)]
        sess = self._make_session(entries)
        calc = EfficiencyCalculator()
        result = calc.calculate(sess)
        self.assertAlmostEqual(result["ratio"], 1.0)

    def test_empty_session(self):
        path = _make_jsonl([])
        sess = TranscriptSession(path)
        os.unlink(path)
        calc = EfficiencyCalculator()
        result = calc.calculate(sess)
        self.assertIsNone(result["ratio"])
        self.assertEqual(result["rating"], "unknown")


# ---------------------------------------------------------------------------
# VelocityCalculator tests
# ---------------------------------------------------------------------------

class TestVelocityCalculator(unittest.TestCase):

    def _make_session(self, entries):
        path = _make_jsonl(entries)
        try:
            return TranscriptSession(path)
        finally:
            os.unlink(path)

    def test_commit_count(self):
        entries = [
            _bash_commit_entry(offset=0),
            _bash_commit_entry(offset=60),
            _tool_use_entry("Read", file_path="x.py", offset=120),
        ]
        sess = self._make_session(entries)
        calc = VelocityCalculator()
        result = calc.calculate(sess)
        self.assertEqual(result["commits"], 2)

    def test_file_creates_count(self):
        entries = [
            _write_file_entry("new_module.py", offset=0),
            _write_file_entry("another.py", offset=1),
        ]
        sess = self._make_session(entries)
        calc = VelocityCalculator()
        result = calc.calculate(sess)
        self.assertEqual(result["file_creates"], 2)

    def test_deliverables_total(self):
        entries = [
            _bash_commit_entry(offset=0),
            _write_file_entry("new.py", offset=1),
        ]
        sess = self._make_session(entries)
        calc = VelocityCalculator()
        result = calc.calculate(sess)
        self.assertEqual(result["deliverables"], 2)

    def test_velocity_per_100_calls(self):
        # 2 commits, 20 tool calls → 10%
        entries = [_tool_use_entry("Read", file_path="x.py", offset=i) for i in range(18)]
        entries.append(_bash_commit_entry(offset=18))
        entries.append(_bash_commit_entry(offset=19))
        sess = self._make_session(entries)
        calc = VelocityCalculator()
        result = calc.calculate(sess)
        self.assertAlmostEqual(result["velocity_pct"], 10.0)

    def test_no_deliverables(self):
        entries = [_tool_use_entry("Read", file_path="x.py", offset=i) for i in range(5)]
        sess = self._make_session(entries)
        calc = VelocityCalculator()
        result = calc.calculate(sess)
        self.assertEqual(result["deliverables"], 0)
        self.assertAlmostEqual(result["velocity_pct"], 0.0)


# ---------------------------------------------------------------------------
# TraceAnalyzer integration tests
# ---------------------------------------------------------------------------

class TestTraceAnalyzer(unittest.TestCase):

    def _make_session_file(self, entries):
        return _make_jsonl(entries)

    def test_analyze_returns_report(self):
        entries = [
            _tool_use_entry("Read", file_path="a.py", offset=0),
            _tool_use_entry("Edit", file_path="a.py", offset=1),
            _bash_commit_entry(offset=2),
        ]
        path = self._make_session_file(entries)
        try:
            analyzer = TraceAnalyzer(path)
            report = analyzer.analyze()
        finally:
            os.unlink(path)
        self.assertIn("efficiency", report)
        self.assertIn("retries", report)
        self.assertIn("waste", report)
        self.assertIn("velocity", report)
        self.assertIn("session_id", report)

    def test_report_has_summary_score(self):
        entries = [
            _tool_use_entry("Edit", file_path=f"f{i}.py", offset=i) for i in range(5)
        ]
        entries.append(_bash_commit_entry(offset=5))
        path = self._make_session_file(entries)
        try:
            report = TraceAnalyzer(path).analyze()
        finally:
            os.unlink(path)
        self.assertIn("score", report)
        self.assertIsInstance(report["score"], (int, float))

    def test_report_has_recommendations(self):
        # Trigger waste: Read foo.py but never use it
        entries = [
            _tool_use_entry("Read", file_path="foo.py", offset=0),
            _tool_use_entry("Edit", file_path="bar.py", offset=1),
        ]
        path = self._make_session_file(entries)
        try:
            report = TraceAnalyzer(path).analyze()
        finally:
            os.unlink(path)
        self.assertIn("recommendations", report)

    def test_report_is_json_serializable(self):
        entries = [_tool_use_entry("Read", file_path="x.py")]
        path = self._make_session_file(entries)
        try:
            report = TraceAnalyzer(path).analyze()
        finally:
            os.unlink(path)
        # Should not raise
        json.dumps(report)

    def test_analyze_empty_session(self):
        path = _make_jsonl([])
        try:
            report = TraceAnalyzer(path).analyze()
        finally:
            os.unlink(path)
        self.assertIsNotNone(report)
        self.assertIn("efficiency", report)

    def test_high_retry_lowers_score(self):
        # 8 retries = critical
        entries = [_tool_use_entry("Edit", file_path="foo.py", offset=i) for i in range(8)]
        path = self._make_session_file(entries)
        try:
            bad_report = TraceAnalyzer(path).analyze()
        finally:
            os.unlink(path)

        entries2 = [_tool_use_entry("Edit", file_path=f"f{i}.py", offset=i) for i in range(8)]
        path2 = self._make_session_file(entries2)
        try:
            good_report = TraceAnalyzer(path2).analyze()
        finally:
            os.unlink(path2)

        self.assertLess(bad_report["score"], good_report["score"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
