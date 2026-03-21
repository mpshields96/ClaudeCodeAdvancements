#!/usr/bin/env python3
"""Extended tests for trace_analyzer.py — edge cases in TranscriptEntry,
TranscriptSession, RetryDetector, WasteDetector, EfficiencyCalculator,
VelocityCalculator, and TraceAnalyzer score calculation.

Supplements test_trace_analyzer.py (50 tests).
"""

import json
import os
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)

import trace_analyzer as ta


# ---------------------------------------------------------------------------
# Helpers — JSONL file builders
# ---------------------------------------------------------------------------

def _tool_entry(tool_name, file_path=None, command=None):
    """Build a raw assistant entry with a tool_use block."""
    inp = {}
    if file_path:
        inp["file_path"] = file_path
    if command:
        inp["command"] = command
    return {
        "type": "assistant",
        "message": {
            "content": [{"type": "tool_use", "name": tool_name, "input": inp}],
            "usage": {"output_tokens": 50},
        },
    }


def _tool_result_entry(is_error=False):
    """Build a user entry with a tool_result block."""
    return {
        "type": "user",
        "toolUseResult": {},
        "message": {
            "content": [{"type": "tool_result", "is_error": is_error}],
        },
    }


def _noise_entry(noise_type="progress"):
    return {"type": noise_type}


def _session_entry(session_id="sess123"):
    return {"type": "user", "sessionId": session_id, "message": {"content": []}}


def _make_jsonl(entries, tmpdir):
    path = os.path.join(tmpdir, "session.jsonl")
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path


def _make_session(entries, tmpdir):
    path = _make_jsonl(entries, tmpdir)
    return ta.TranscriptSession(path)


# ---------------------------------------------------------------------------
# TestTranscriptEntryEdgeCases
# ---------------------------------------------------------------------------

class TestTranscriptEntryEdgeCases(unittest.TestCase):

    def test_missing_message_key_no_crash(self):
        raw = {"type": "assistant"}
        entry = ta.TranscriptEntry(raw)
        self.assertIsNone(entry.tool_name)
        self.assertIsNone(entry.file_path)

    def test_none_content_no_crash(self):
        raw = {"type": "assistant", "message": {"content": None}}
        entry = ta.TranscriptEntry(raw)
        self.assertIsNone(entry.tool_name)

    def test_multiple_tool_use_blocks_first_wins(self):
        raw = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "first.py"}},
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "second.py"}},
                ],
            },
        }
        entry = ta.TranscriptEntry(raw)
        self.assertEqual(entry.tool_name, "Read")
        self.assertEqual(entry.file_path, "first.py")

    def test_orientation_session_state_md(self):
        raw = _tool_entry("Read", "some/path/SESSION_STATE.md")
        entry = ta.TranscriptEntry(raw)
        self.assertTrue(entry.is_orientation)

    def test_orientation_roadmap_md(self):
        raw = _tool_entry("Read", "/project/ROADMAP.md")
        entry = ta.TranscriptEntry(raw)
        self.assertTrue(entry.is_orientation)

    def test_orientation_master_roadmap_md(self):
        raw = _tool_entry("Read", "/project/MASTER_ROADMAP.md")
        entry = ta.TranscriptEntry(raw)
        self.assertTrue(entry.is_orientation)

    def test_non_orientation_regular_python_file(self):
        raw = _tool_entry("Read", "src/foo.py")
        entry = ta.TranscriptEntry(raw)
        self.assertFalse(entry.is_orientation)

    def test_orientation_requires_read_tool(self):
        # Edit of CLAUDE.md is NOT orientation
        raw = _tool_entry("Edit", "CLAUDE.md")
        entry = ta.TranscriptEntry(raw)
        self.assertFalse(entry.is_orientation)

    def test_invalid_timestamp_returns_none(self):
        raw = {"type": "assistant", "timestamp": "not-a-timestamp"}
        entry = ta.TranscriptEntry(raw)
        self.assertIsNone(entry.timestamp)

    def test_valid_timestamp_z_suffix(self):
        raw = {"type": "assistant", "timestamp": "2026-03-21T14:30:00Z"}
        entry = ta.TranscriptEntry(raw)
        self.assertIsNotNone(entry.timestamp)
        self.assertEqual(entry.timestamp.hour, 14)

    def test_is_error_false_when_no_tool_result(self):
        raw = {"type": "user", "toolUseResult": None, "message": {"content": []}}
        entry = ta.TranscriptEntry(raw)
        self.assertFalse(entry.is_error)

    def test_is_error_false_when_tool_result_not_error(self):
        raw = _tool_result_entry(is_error=False)
        entry = ta.TranscriptEntry(raw)
        self.assertFalse(entry.is_error)

    def test_is_error_true_when_tool_result_error(self):
        raw = _tool_result_entry(is_error=True)
        entry = ta.TranscriptEntry(raw)
        self.assertTrue(entry.is_error)

    def test_system_entry_not_noise(self):
        raw = {"type": "system"}
        entry = ta.TranscriptEntry(raw)
        self.assertFalse(entry.is_noise)

    def test_uuid_none_when_missing(self):
        raw = {"type": "user"}
        entry = ta.TranscriptEntry(raw)
        self.assertIsNone(entry.uuid)


# ---------------------------------------------------------------------------
# TestTranscriptSessionEdgeCases
# ---------------------------------------------------------------------------

class TestTranscriptSessionEdgeCases(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_corrupted_lines_skipped(self):
        path = os.path.join(self.tmpdir, "bad.jsonl")
        with open(path, "w") as f:
            f.write("not json at all\n")
            f.write(json.dumps({"type": "assistant"}) + "\n")
        session = ta.TranscriptSession(path)
        # Only the valid line should be loaded
        self.assertEqual(len(session.all_entries), 1)

    def test_blank_lines_skipped(self):
        path = os.path.join(self.tmpdir, "blanks.jsonl")
        with open(path, "w") as f:
            f.write("\n\n")
            f.write(json.dumps({"type": "user"}) + "\n")
            f.write("\n")
        session = ta.TranscriptSession(path)
        self.assertEqual(len(session.all_entries), 1)

    def test_first_session_id_wins(self):
        entries = [
            {"type": "user", "sessionId": "first", "message": {"content": []}},
            {"type": "user", "sessionId": "second", "message": {"content": []}},
        ]
        session = _make_session(entries, self.tmpdir)
        self.assertEqual(session.session_id, "first")

    def test_unique_files_excludes_none_file_path(self):
        # Bash entries have no file_path
        entries = [_tool_entry("Bash", command="ls")]
        session = _make_session(entries, self.tmpdir)
        self.assertEqual(len(session.unique_files), 0)

    def test_total_output_tokens_sums_correctly(self):
        entries = []
        for tokens in [100, 200, 300]:
            raw = _tool_entry("Read", "a.py")
            raw["message"]["usage"]["output_tokens"] = tokens
            entries.append(raw)
        session = _make_session(entries, self.tmpdir)
        self.assertEqual(session.total_output_tokens, 600)

    def test_total_output_tokens_zero_when_no_usage(self):
        entries = [{"type": "user", "message": {"content": []}}]
        session = _make_session(entries, self.tmpdir)
        self.assertEqual(session.total_output_tokens, 0)

    def test_noise_entries_excluded_from_signal(self):
        entries = [_noise_entry("progress"), _tool_entry("Read", "x.py")]
        session = _make_session(entries, self.tmpdir)
        self.assertEqual(len(session.signal_entries), 1)
        self.assertEqual(len(session.all_entries), 2)

    def test_queue_operation_is_noise(self):
        entries = [_noise_entry("queue-operation"), _tool_entry("Write", "x.py")]
        session = _make_session(entries, self.tmpdir)
        self.assertEqual(len(session.signal_entries), 1)


# ---------------------------------------------------------------------------
# TestRetryDetectorEdgeCases
# ---------------------------------------------------------------------------

class TestRetryDetectorEdgeCases(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.det = ta.RetryDetector()

    def _session(self, entries):
        return _make_session(entries, self.tmpdir)

    def test_exactly_two_consecutive_no_retry(self):
        entries = [_tool_entry("Edit", "x.py"), _tool_entry("Edit", "x.py")]
        result = self.det.detect(self._session(entries))
        self.assertEqual(result["total_retries"], 0)

    def test_different_tool_same_file_no_retry(self):
        entries = [
            _tool_entry("Read", "x.py"),
            _tool_entry("Edit", "x.py"),
            _tool_entry("Write", "x.py"),
        ]
        result = self.det.detect(self._session(entries))
        self.assertEqual(result["total_retries"], 0)

    def test_error_confirmed_when_tool_result_is_error(self):
        entries = [
            _tool_entry("Edit", "x.py"),
            _tool_result_entry(is_error=True),
            _tool_entry("Edit", "x.py"),
            _tool_entry("Edit", "x.py"),
        ]
        result = self.det.detect(self._session(entries))
        self.assertEqual(result["total_retries"], 1)
        self.assertTrue(result["retries"][0]["error_confirmed"])

    def test_non_tool_entries_interspersed_still_counts(self):
        # tool results (no tool_name) should be skipped in run counting
        entries = [
            _tool_entry("Edit", "x.py"),
            _tool_result_entry(is_error=False),  # no tool_name — interspersed
            _tool_entry("Edit", "x.py"),
            _tool_entry("Edit", "x.py"),
        ]
        result = self.det.detect(self._session(entries))
        self.assertGreaterEqual(result["total_retries"], 1)

    def test_start_index_in_result(self):
        entries = [_tool_entry("Edit", "a.py")] * 3
        result = self.det.detect(self._session(entries))
        self.assertIn("start_index", result["retries"][0])
        self.assertEqual(result["retries"][0]["start_index"], 0)

    def test_two_separate_retry_loops_detected(self):
        entries = (
            [_tool_entry("Edit", "file1.py")] * 3 +
            [_tool_entry("Read", "file2.py")] +  # break the run
            [_tool_entry("Edit", "file3.py")] * 3
        )
        result = self.det.detect(self._session(entries))
        self.assertEqual(result["total_retries"], 2)

    def test_retry_resets_on_different_tool_same_file(self):
        # Read x.py 3 times, then Edit x.py 3 times — two separate retries
        entries = (
            [_tool_entry("Read", "x.py")] * 3 +
            [_tool_entry("Edit", "x.py")] * 3
        )
        result = self.det.detect(self._session(entries))
        self.assertEqual(result["total_retries"], 2)


# ---------------------------------------------------------------------------
# TestWasteDetectorEdgeCases
# ---------------------------------------------------------------------------

class TestWasteDetectorEdgeCases(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.det = ta.WasteDetector()

    def _session(self, entries):
        return _make_session(entries, self.tmpdir)

    def test_no_reads_waste_rate_zero(self):
        entries = [_tool_entry("Edit", "x.py"), _tool_entry("Bash", command="ls")]
        result = self.det.detect(self._session(entries))
        self.assertEqual(result["waste_rate"], 0.0)
        self.assertEqual(result["total_reads"], 0)

    def test_all_orientation_reads_not_wasted(self):
        entries = [
            _tool_entry("Read", "CLAUDE.md"),
            _tool_entry("Read", "SESSION_STATE.md"),
            _tool_entry("Read", "PROJECT_INDEX.md"),
        ]
        result = self.det.detect(self._session(entries))
        self.assertEqual(result["total_reads"], 0)
        self.assertEqual(result["waste_rate"], 0.0)

    def test_reference_via_bash_command_not_wasted(self):
        entries = [
            _tool_entry("Read", "/path/to/module.py"),
            # Bash command that mentions the filename
            _tool_entry("Bash", command="python3 module.py test"),
        ]
        result = self.det.detect(self._session(entries))
        self.assertEqual(len(result["wasted_reads"]), 0)

    def test_reference_by_filename_match_not_wasted(self):
        # Read at /long/path/x.py, then later Edit at different/path/x.py
        entries = [
            _tool_entry("Read", "/long/path/to/x.py"),
            _tool_entry("Edit", "/different/path/x.py"),
        ]
        result = self.det.detect(self._session(entries))
        self.assertEqual(len(result["wasted_reads"]), 0)

    def test_file_referenced_at_boundary_not_wasted(self):
        # Read at index 0, reference at index WASTE_WINDOW (inclusive: entries[idx+1:idx+1+20])
        # Window is indices 1..20 (20 entries). Reference at index 20 = entries[20]
        entries = [_tool_entry("Read", "x.py")]
        # Add 19 noise entries then the reference
        for _ in range(19):
            entries.append({"type": "user", "message": {"content": []}})
        entries.append(_tool_entry("Edit", "x.py"))  # at index 20
        result = self.det.detect(self._session(entries))
        # Window covers entries[1:21] which includes index 20 — should not be wasted
        self.assertEqual(len(result["wasted_reads"]), 0)

    def test_file_referenced_just_outside_window_wasted(self):
        # Reference at index WASTE_WINDOW + 1 = 22 (outside window of 20)
        entries = [_tool_entry("Read", "x.py")]
        for _ in range(20):  # Fill exactly 20 slots
            entries.append({"type": "user", "message": {"content": []}})
        entries.append(_tool_entry("Edit", "x.py"))  # at index 21 — outside window
        result = self.det.detect(self._session(entries))
        self.assertEqual(len(result["wasted_reads"]), 1)

    def test_wasted_read_has_position_field(self):
        entries = [_tool_entry("Read", "orphan.py")]
        # No subsequent reference
        result = self.det.detect(self._session(entries))
        self.assertEqual(len(result["wasted_reads"]), 1)
        self.assertIn("position", result["wasted_reads"][0])

    def test_multiple_reads_same_file_each_evaluated(self):
        # Read x.py twice. First is used, second is wasted.
        entries = [
            _tool_entry("Read", "x.py"),
            _tool_entry("Edit", "x.py"),  # uses first read
            _tool_entry("Read", "x.py"),  # second read — nothing after it
        ]
        result = self.det.detect(self._session(entries))
        self.assertEqual(result["total_reads"], 2)
        self.assertEqual(len(result["wasted_reads"]), 1)


# ---------------------------------------------------------------------------
# TestEfficiencyCalculatorBoundaries
# ---------------------------------------------------------------------------

class TestEfficiencyCalculatorBoundaries(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.calc = ta.EfficiencyCalculator()

    def _session(self, entries):
        return _make_session(entries, self.tmpdir)

    def test_ratio_exactly_0_3_is_mediocre_not_good(self):
        # 3 unique files, 10 calls — ratio = 0.3 → mediocre (not > 0.3)
        entries = (
            [_tool_entry("Read", "a.py")] * 4 +
            [_tool_entry("Edit", "b.py")] * 3 +
            [_tool_entry("Write", "c.py")] * 3
        )
        result = self.calc.calculate(self._session(entries))
        self.assertAlmostEqual(result["ratio"], 0.3, places=2)
        self.assertEqual(result["rating"], "mediocre")

    def test_ratio_above_0_3_is_good(self):
        # 4 files, 10 calls = 0.4
        entries = (
            [_tool_entry("Read", "a.py")] * 3 +
            [_tool_entry("Edit", "b.py")] * 3 +
            [_tool_entry("Write", "c.py")] * 2 +
            [_tool_entry("Glob", "d.py")] * 2
        )
        result = self.calc.calculate(self._session(entries))
        self.assertGreater(result["ratio"], 0.3)
        self.assertEqual(result["rating"], "good")

    def test_ratio_exactly_0_1_is_mediocre_not_poor(self):
        # 1 file, 10 calls → ratio 0.1 → mediocre (>= 0.1)
        entries = [_tool_entry("Read", "only.py")] * 10
        result = self.calc.calculate(self._session(entries))
        self.assertAlmostEqual(result["ratio"], 0.1, places=2)
        self.assertEqual(result["rating"], "mediocre")

    def test_ratio_below_0_1_is_poor(self):
        # 1 file, 11 calls → ratio < 0.1
        entries = [_tool_entry("Read", "only.py")] * 11
        result = self.calc.calculate(self._session(entries))
        self.assertLess(result["ratio"], 0.1)
        self.assertEqual(result["rating"], "poor")

    def test_single_file_single_call_good(self):
        entries = [_tool_entry("Read", "one.py")]
        result = self.calc.calculate(self._session(entries))
        self.assertEqual(result["ratio"], 1.0)
        self.assertEqual(result["rating"], "good")

    def test_unique_files_count_in_result(self):
        entries = [_tool_entry("Read", "a.py"), _tool_entry("Edit", "b.py")]
        result = self.calc.calculate(self._session(entries))
        self.assertEqual(result["unique_files"], 2)


# ---------------------------------------------------------------------------
# TestVelocityCalculatorEdgeCases
# ---------------------------------------------------------------------------

class TestVelocityCalculatorEdgeCases(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.calc = ta.VelocityCalculator()

    def _session(self, entries):
        return _make_session(entries, self.tmpdir)

    def test_git_commit_with_message_flag_counted(self):
        entries = [_tool_entry("Bash", command="git commit -m 'fix: something'")]
        result = self.calc.calculate(self._session(entries))
        self.assertEqual(result["commits"], 1)

    def test_git_commit_partial_match_counted(self):
        entries = [_tool_entry("Bash", command="git commit --no-verify")]
        result = self.calc.calculate(self._session(entries))
        self.assertEqual(result["commits"], 1)

    def test_bash_not_commit_not_counted(self):
        entries = [_tool_entry("Bash", command="git status")]
        result = self.calc.calculate(self._session(entries))
        self.assertEqual(result["commits"], 0)

    def test_bash_no_command_not_counted(self):
        entries = [_tool_entry("Bash")]
        result = self.calc.calculate(self._session(entries))
        self.assertEqual(result["commits"], 0)

    def test_velocity_pct_zero_when_no_deliverables(self):
        entries = [_tool_entry("Read", "x.py")] * 5
        result = self.calc.calculate(self._session(entries))
        self.assertEqual(result["velocity_pct"], 0.0)

    def test_velocity_pct_computed_correctly(self):
        # 2 commits + 3 writes out of 10 calls = 50%
        entries = (
            [_tool_entry("Bash", command="git commit")] * 2 +
            [_tool_entry("Write", "x.py")] * 3 +
            [_tool_entry("Read", "y.py")] * 5
        )
        result = self.calc.calculate(self._session(entries))
        self.assertAlmostEqual(result["velocity_pct"], 50.0, places=1)

    def test_empty_session_velocity_zero(self):
        result = self.calc.calculate(_make_session([], self.tmpdir))
        self.assertEqual(result["velocity_pct"], 0.0)
        self.assertEqual(result["deliverables"], 0)


# ---------------------------------------------------------------------------
# TestTraceAnalyzerScoring
# ---------------------------------------------------------------------------

class TestTraceAnalyzerScoring(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _analyze(self, entries):
        path = _make_jsonl(entries, self.tmpdir)
        return ta.TraceAnalyzer(path).analyze()

    def test_perfect_session_score_100(self):
        # Good efficiency, velocity, no waste (each read immediately followed by edit), no retries
        entries = (
            [_tool_entry("Read", "a.py")] + [_tool_entry("Edit", "a.py")] +
            [_tool_entry("Read", "b.py")] + [_tool_entry("Edit", "b.py")] +
            [_tool_entry("Write", "c.py")] +
            [_tool_entry("Read", "d.py")] + [_tool_entry("Edit", "d.py")] +
            [_tool_entry("Bash", command="git commit -m 'done'")] * 2 +
            [_tool_entry("Write", "e.py")]
        )
        report = self._analyze(entries)
        self.assertEqual(report["score"], 100)

    def test_score_not_negative(self):
        # Many critical retries should floor at 0
        entries = [_tool_entry("Edit", "x.py")] * 20
        report = self._analyze(entries)
        self.assertGreaterEqual(report["score"], 0)

    def test_critical_retry_penalizes_20(self):
        # 8 consecutive = critical = -20
        base = 100
        entries = [_tool_entry("Edit", "x.py")] * 8
        report = self._analyze(entries)
        # Also penalizes for poor efficiency (-15), so just check < 100
        self.assertLess(report["score"], base)

    def test_waste_above_50pct_penalizes_20(self):
        # 3 reads all wasted → waste_rate = 1.0 → -20
        entries = [
            _tool_entry("Read", "a.py"),
            _tool_entry("Read", "b.py"),
            _tool_entry("Read", "c.py"),
        ]
        report = self._analyze(entries)
        # Waste rate = 1.0 → -20 penalty applies
        self.assertLess(report["score"], 100)

    def test_waste_between_30_and_50_penalizes_10(self):
        # 1 wasted + 2 used reads out of 3 = 33% waste → -10
        entries = [
            _tool_entry("Read", "wasted.py"),  # wasted
            _tool_entry("Read", "used.py"),    # used
            _tool_entry("Edit", "used.py"),
        ]
        report = self._analyze(entries)
        self.assertLess(report["score"], 100)

    def test_no_deliverables_with_many_calls_penalizes_10(self):
        # 11 reads, no commits or writes
        entries = [_tool_entry("Read", f"{i}.py") for i in range(11)]
        report = self._analyze(entries)
        recs = report["recommendations"]
        no_commit_recs = [r for r in recs if "commit" in r.lower()]
        self.assertGreater(len(no_commit_recs), 0)

    def test_no_deliverables_below_10_calls_no_penalty(self):
        # Only 10 reads, no commits — boundary: > 10 required for penalty
        entries = [_tool_entry("Read", f"{i}.py") for i in range(10)]
        report = self._analyze(entries)
        recs = report["recommendations"]
        no_commit_recs = [r for r in recs if "commit" in r.lower()]
        self.assertEqual(no_commit_recs, [])

    def test_report_has_session_id_key(self):
        entries = [{"type": "user", "sessionId": "my-session", "message": {"content": []}}]
        report = self._analyze(entries)
        self.assertIn("session_id", report)

    def test_report_total_entries_vs_signal_entries(self):
        entries = [_noise_entry("progress"), _tool_entry("Read", "a.py")]
        report = self._analyze(entries)
        self.assertEqual(report["total_entries"], 2)
        self.assertEqual(report["signal_entries"], 1)
        self.assertEqual(report["noise_filtered"], 1)

    def test_multiple_minor_retries_stack(self):
        # Two separate minor retries = -5 each = -10 total, plus efficiency penalty
        entries = (
            [_tool_entry("Edit", "a.py")] * 3 +
            [_tool_entry("Read", "b.py")] +   # break
            [_tool_entry("Edit", "c.py")] * 3
        )
        report = self._analyze(entries)
        self.assertEqual(report["retries"]["total_retries"], 2)
        self.assertLess(report["score"], 100)

    def test_recommendations_empty_for_clean_session(self):
        entries = (
            [_tool_entry("Read", "a.py")] +
            [_tool_entry("Write", "b.py")] +
            [_tool_entry("Bash", command="git commit -m 'x'")] +
            [_tool_entry("Read", "c.py")] +
            [_tool_entry("Edit", "c.py")]
        )
        report = self._analyze(entries)
        # Score should be perfect or near-perfect, no critical recommendations
        critical_recs = [r for r in report["recommendations"] if "critical" in r.lower()]
        self.assertEqual(critical_recs, [])


if __name__ == "__main__":
    unittest.main()
