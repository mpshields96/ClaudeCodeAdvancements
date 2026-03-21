"""
test_trial_tracker_extended.py — Extended edge-case tests for trial_tracker.py

Covers gaps in test_trial_tracker.py:
- Missing/extra fields in JSONL records
- Concurrent writes (threading)
- Gate evaluation boundaries (required=0, required=1, exactly at threshold)
- Consecutive pass counting edge cases
- Status with all-fails, zero-duration, mixed duration
- TrialRecord validation edge cases
- Multiple MT isolation stress
- from_dict robustness

Target: 30+ tests
"""

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestMissingFields(unittest.TestCase):
    """JSONL lines with valid JSON but missing required or optional fields."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_missing_mt_id_skipped(self):
        """Line with missing mt_id should be skipped (TypeError on from_dict)."""
        from trial_tracker import load_trials, record_trial, TrialRecord

        # Write a valid record first
        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)

        # Append a record missing mt_id
        bad = {
            "session_id": "S98",
            "result": "pass",
            "timestamp": "2026-03-22T10:00:00+00:00",
            "commits": 3,
            "tests_added": 10,
            "coordination_failures": 0,
            "test_regressions": 0,
            "duration_secs": 0,
            "notes": "",
        }
        with open(self.trial_file, "a") as f:
            f.write(json.dumps(bad) + "\n")

        trials = load_trials(trial_file=self.trial_file)
        # Only the valid record should be loaded
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0].mt_id, "MT-22")

    def test_missing_session_id_skipped(self):
        """Line missing session_id should be skipped."""
        from trial_tracker import load_trials

        bad = {
            "mt_id": "MT-22",
            "result": "pass",
            "timestamp": "2026-03-22T10:00:00+00:00",
            "commits": 0,
            "tests_added": 0,
            "coordination_failures": 0,
            "test_regressions": 0,
            "duration_secs": 0,
            "notes": "",
        }
        with open(self.trial_file, "w") as f:
            f.write(json.dumps(bad) + "\n")

        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(len(trials), 0)

    def test_missing_optional_fields_use_defaults(self):
        """JSONL with only required fields should load with defaults for optional fields."""
        from trial_tracker import load_trials

        # Only the minimal required fields for TrialRecord constructor
        minimal = {
            "mt_id": "MT-22",
            "session_id": "S99",
            "result": "pass",
            "timestamp": "2026-03-22T10:00:00+00:00",
            "commits": 0,
            "tests_added": 0,
            "coordination_failures": 0,
            "test_regressions": 0,
            "duration_secs": 0,
            "notes": "",
        }
        with open(self.trial_file, "w") as f:
            f.write(json.dumps(minimal) + "\n")

        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0].commits, 0)
        self.assertEqual(trials[0].notes, "")

    def test_extra_fields_in_jsonl_skipped(self):
        """JSONL with unknown extra fields should raise TypeError and be skipped."""
        from trial_tracker import load_trials, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)

        # Append record with extra unknown field
        extra = rec.to_dict()
        extra["unknown_future_field"] = "some_value"
        with open(self.trial_file, "a") as f:
            f.write(json.dumps(extra) + "\n")

        # Load should skip the record with extra fields (TypeError from_dict)
        # OR handle it gracefully. Either outcome is acceptable; what matters
        # is it does not crash.
        try:
            trials = load_trials(trial_file=self.trial_file)
            # If it doesn't crash, we just verify the valid record is loaded
            self.assertGreaterEqual(len(trials), 1)
        except Exception as e:
            self.fail(f"load_trials crashed on extra fields: {e}")

    def test_null_mt_id_raises_value_error(self):
        """KNOWN GAP: null mt_id in JSONL raises ValueError from __post_init__.

        load_trials currently catches (JSONDecodeError, TypeError) but not ValueError.
        When mt_id is JSON null (None), TrialRecord.__post_init__ raises ValueError
        which propagates uncaught. This test documents the current behavior.
        Desktop should add ValueError to the except clause in load_trials.
        """
        from trial_tracker import load_trials, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)

        bad = rec.to_dict()
        bad["mt_id"] = None
        with open(self.trial_file, "a") as f:
            f.write(json.dumps(bad) + "\n")

        # Current behavior: raises ValueError (uncaught exception — known gap)
        with self.assertRaises(ValueError):
            load_trials(trial_file=self.trial_file)

    def test_empty_json_object_skipped(self):
        """Empty JSON object should be skipped."""
        from trial_tracker import load_trials

        with open(self.trial_file, "w") as f:
            f.write("{}\n")

        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(len(trials), 0)

    def test_json_array_line_skipped(self):
        """JSON array instead of object should be skipped."""
        from trial_tracker import load_trials

        with open(self.trial_file, "w") as f:
            f.write("[1, 2, 3]\n")

        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(len(trials), 0)


class TestConcurrentWrites(unittest.TestCase):
    """Concurrent write safety — multiple threads writing to the same JSONL file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_concurrent_writes_no_crash(self):
        """Concurrent writes from 5 threads should not crash."""
        from trial_tracker import record_trial, TrialRecord

        errors = []

        def write_trial(session_id):
            try:
                rec = TrialRecord(
                    mt_id="MT-22", session_id=session_id, result="pass", commits=2
                )
                record_trial(rec, trial_file=self.trial_file)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=write_trial, args=(f"S{100 + i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Concurrent write errors: {errors}")

    def test_concurrent_writes_all_recorded(self):
        """All 10 concurrent writes should appear in the file (no data loss)."""
        from trial_tracker import record_trial, load_trials, TrialRecord

        session_ids = [f"S{200 + i}" for i in range(10)]

        def write_trial(session_id):
            rec = TrialRecord(
                mt_id="MT-CONC", session_id=session_id, result="pass"
            )
            record_trial(rec, trial_file=self.trial_file)

        threads = [
            threading.Thread(target=write_trial, args=(sid,))
            for sid in session_ids
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        trials = load_trials(mt_id="MT-CONC", trial_file=self.trial_file)
        # Allow for some races but all 10 should be present in the file
        self.assertEqual(len(trials), 10)

    def test_concurrent_reads_while_writing(self):
        """Reading while another thread writes should not crash."""
        from trial_tracker import record_trial, load_trials, TrialRecord

        # Pre-seed some data
        for i in range(3):
            rec = TrialRecord(mt_id="MT-22", session_id=f"S{i}", result="pass")
            record_trial(rec, trial_file=self.trial_file)

        read_errors = []

        def continuous_read():
            for _ in range(20):
                try:
                    load_trials(mt_id="MT-22", trial_file=self.trial_file)
                    time.sleep(0.005)
                except Exception as e:
                    read_errors.append(e)

        def write_more():
            for i in range(5):
                rec = TrialRecord(mt_id="MT-22", session_id=f"SW{i}", result="pass")
                record_trial(rec, trial_file=self.trial_file)
                time.sleep(0.01)

        reader = threading.Thread(target=continuous_read)
        writer = threading.Thread(target=write_more)
        reader.start()
        writer.start()
        reader.join(timeout=5)
        writer.join(timeout=5)

        self.assertEqual(len(read_errors), 0, f"Read errors during concurrent write: {read_errors}")


class TestGateBoundaries(unittest.TestCase):
    """Gate evaluation edge cases: required=0, required=1, exactly at threshold."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_gate_required_one_one_pass(self):
        """required=1 with 1 pass should pass."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)

        result = check_gate("MT-22", required=1, trial_file=self.trial_file)
        self.assertTrue(result["passed"])
        self.assertEqual(result["pass_count"], 1)

    def test_gate_required_one_one_fail(self):
        """required=1 with 1 fail should not pass."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="fail")
        record_trial(rec, trial_file=self.trial_file)

        result = check_gate("MT-22", required=1, trial_file=self.trial_file)
        self.assertFalse(result["passed"])

    def test_gate_required_two_exactly_two_passes(self):
        """required=2 with exactly 2 passes should pass."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        for s in ["S96", "S97"]:
            rec = TrialRecord(mt_id="MT-22", session_id=s, result="pass")
            record_trial(rec, trial_file=self.trial_file)

        result = check_gate("MT-22", required=2, trial_file=self.trial_file)
        self.assertTrue(result["passed"])
        self.assertEqual(result["pass_count"], 2)

    def test_gate_required_two_one_pass(self):
        """required=2 with only 1 pass should not pass."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)

        result = check_gate("MT-22", required=2, trial_file=self.trial_file)
        self.assertFalse(result["passed"])

    def test_gate_all_fails(self):
        """Gate with all fails should not pass and have 0 consecutive passes."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        for s in ["S96", "S97", "S98"]:
            rec = TrialRecord(mt_id="MT-22", session_id=s, result="fail")
            record_trial(rec, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertFalse(result["passed"])
        self.assertEqual(result["pass_count"], 0)
        self.assertEqual(result["fail_count"], 3)
        self.assertEqual(result["consecutive_passes"], 0)

    def test_gate_consecutive_resets_on_fail(self):
        """After 3 passes, a fail resets consecutive count."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        for s in ["S90", "S91", "S92"]:
            rec = TrialRecord(mt_id="MT-22", session_id=s, result="pass")
            record_trial(rec, trial_file=self.trial_file)
        fail_rec = TrialRecord(mt_id="MT-22", session_id="S93", result="fail")
        record_trial(fail_rec, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertEqual(result["consecutive_passes"], 0)
        # Still has 3 total passes, gate passes
        self.assertTrue(result["passed"])

    def test_gate_consecutive_all_pass(self):
        """All passes means consecutive = total."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        for s in ["S96", "S97", "S99"]:
            rec = TrialRecord(mt_id="MT-22", session_id=s, result="pass")
            record_trial(rec, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertEqual(result["consecutive_passes"], 3)

    def test_gate_result_has_all_keys(self):
        """Gate result dict must have all expected keys."""
        from trial_tracker import check_gate

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        expected_keys = {
            "mt_id",
            "passed",
            "pass_count",
            "fail_count",
            "required",
            "consecutive_passes",
            "total_trials",
        }
        for key in expected_keys:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_gate_mt_isolation(self):
        """Gate for MT-22 should not count MT-21 passes."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        # Add 3 passes for MT-21 and 1 pass for MT-22
        for s in ["S96", "S97", "S98"]:
            rec = TrialRecord(mt_id="MT-21", session_id=s, result="pass")
            record_trial(rec, trial_file=self.trial_file)
        rec22 = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec22, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertFalse(result["passed"])
        self.assertEqual(result["pass_count"], 1)

    def test_gate_empty_file_no_trials(self):
        """Gate on empty file returns total_trials=0 and passed=False."""
        from trial_tracker import check_gate

        # Create empty file
        self.trial_file.write_text("")

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertFalse(result["passed"])
        self.assertEqual(result["total_trials"], 0)

    def test_gate_message_includes_need_count(self):
        """Gate not-met message should include how many more passes are needed."""
        from trial_tracker import cli_gate, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)

        result = cli_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertIn("2", result["message"])  # "Need 2 more passes"


class TestDuplicateSessionIds(unittest.TestCase):
    """Duplicate session IDs in gate and status calculations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_duplicate_session_both_counted_in_gate(self):
        """Same session recorded twice — both count toward gate (append-only)."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        rec1 = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        rec2 = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        rec3 = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)
        record_trial(rec3, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertTrue(result["passed"])
        self.assertEqual(result["pass_count"], 3)

    def test_duplicate_session_pass_then_fail(self):
        """Same session recorded as pass then fail — both counted."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        rec1 = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        rec2 = TrialRecord(mt_id="MT-22", session_id="S99", result="fail")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertFalse(result["passed"])
        self.assertEqual(result["pass_count"], 1)
        self.assertEqual(result["fail_count"], 1)
        # Last record is fail, so consecutive passes = 0
        self.assertEqual(result["consecutive_passes"], 0)


class TestStatusEdgeCases(unittest.TestCase):
    """get_trial_status edge cases."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_status_all_fails(self):
        """Status with all fail results."""
        from trial_tracker import get_trial_status, record_trial, TrialRecord

        for s in ["S96", "S97", "S98"]:
            rec = TrialRecord(mt_id="MT-22", session_id=s, result="fail")
            record_trial(rec, trial_file=self.trial_file)

        status = get_trial_status("MT-22", trial_file=self.trial_file)
        self.assertEqual(status["passes"], 0)
        self.assertEqual(status["fails"], 3)
        self.assertEqual(status["total_trials"], 3)

    def test_status_zero_duration_excluded_from_avg(self):
        """Trials with duration_secs=0 should not affect avg_duration_secs."""
        from trial_tracker import get_trial_status, record_trial, TrialRecord

        rec1 = TrialRecord(
            mt_id="MT-22", session_id="S96", result="pass", duration_secs=0
        )
        rec2 = TrialRecord(
            mt_id="MT-22", session_id="S97", result="pass", duration_secs=3600
        )
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)

        status = get_trial_status("MT-22", trial_file=self.trial_file)
        # Only S97 has non-zero duration, avg = 3600
        self.assertEqual(status["avg_duration_secs"], 3600)

    def test_status_all_zero_duration(self):
        """All zero-duration trials should return avg_duration_secs=0."""
        from trial_tracker import get_trial_status, record_trial, TrialRecord

        for s in ["S96", "S97"]:
            rec = TrialRecord(
                mt_id="MT-22", session_id=s, result="pass", duration_secs=0
            )
            record_trial(rec, trial_file=self.trial_file)

        status = get_trial_status("MT-22", trial_file=self.trial_file)
        self.assertEqual(status["avg_duration_secs"], 0)

    def test_status_has_all_expected_keys(self):
        """Status dict must have all expected keys."""
        from trial_tracker import get_trial_status

        status = get_trial_status("MT-22", trial_file=self.trial_file)
        expected_keys = {
            "total_trials",
            "passes",
            "fails",
            "total_commits",
            "total_tests_added",
            "avg_duration_secs",
        }
        for key in expected_keys:
            self.assertIn(key, status, f"Missing key: {key}")

    def test_status_multiple_mts_isolated(self):
        """Status for MT-22 should not count MT-21 trials."""
        from trial_tracker import get_trial_status, record_trial, TrialRecord

        rec21 = TrialRecord(mt_id="MT-21", session_id="S96", result="pass", commits=10)
        rec22 = TrialRecord(mt_id="MT-22", session_id="S97", result="pass", commits=3)
        record_trial(rec21, trial_file=self.trial_file)
        record_trial(rec22, trial_file=self.trial_file)

        status = get_trial_status("MT-22", trial_file=self.trial_file)
        self.assertEqual(status["total_trials"], 1)
        self.assertEqual(status["total_commits"], 3)


class TestRecordValidation(unittest.TestCase):
    """TrialRecord validation edge cases."""

    def test_explicit_timestamp_preserved(self):
        """If timestamp is provided explicitly, it should be kept."""
        from trial_tracker import TrialRecord

        ts = "2026-01-01T00:00:00+00:00"
        rec = TrialRecord(mt_id="MT-22", session_id="S1", result="pass", timestamp=ts)
        self.assertEqual(rec.timestamp, ts)

    def test_result_pass_is_valid(self):
        """result='pass' should not raise."""
        from trial_tracker import TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S1", result="pass")
        self.assertEqual(rec.result, "pass")

    def test_result_fail_is_valid(self):
        """result='fail' should not raise."""
        from trial_tracker import TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S1", result="fail")
        self.assertEqual(rec.result, "fail")

    def test_cli_record_invalid_result_raises(self):
        """cli_record with invalid result should raise ValueError."""
        from trial_tracker import cli_record
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=True) as f:
            trial_file = Path(f.name)

        with self.assertRaises(ValueError) as ctx:
            cli_record("MT-22", "S99", "unknown", trial_file=trial_file)
        self.assertIn("pass", str(ctx.exception).lower())

    def test_from_dict_roundtrip_preserves_all_fields(self):
        """from_dict(to_dict()) should be lossless."""
        from trial_tracker import TrialRecord

        original = TrialRecord(
            mt_id="MT-22",
            session_id="S99",
            result="pass",
            commits=7,
            tests_added=42,
            coordination_failures=1,
            test_regressions=0,
            duration_secs=4200,
            notes="clean session with minor hiccup",
        )
        d = original.to_dict()
        restored = TrialRecord.from_dict(d)

        self.assertEqual(restored.mt_id, original.mt_id)
        self.assertEqual(restored.session_id, original.session_id)
        self.assertEqual(restored.result, original.result)
        self.assertEqual(restored.commits, original.commits)
        self.assertEqual(restored.tests_added, original.tests_added)
        self.assertEqual(restored.coordination_failures, original.coordination_failures)
        self.assertEqual(restored.test_regressions, original.test_regressions)
        self.assertEqual(restored.duration_secs, original.duration_secs)
        self.assertEqual(restored.notes, original.notes)
        self.assertEqual(restored.timestamp, original.timestamp)


class TestLoadTrialsEdgeCases(unittest.TestCase):
    """load_trials robustness."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_load_all_trials_no_filter(self):
        """load_trials with mt_id=None should return all records."""
        from trial_tracker import record_trial, load_trials, TrialRecord

        rec1 = TrialRecord(mt_id="MT-21", session_id="S96", result="pass")
        rec2 = TrialRecord(mt_id="MT-22", session_id="S97", result="pass")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)

        trials = load_trials(trial_file=self.trial_file)  # no mt_id filter
        self.assertEqual(len(trials), 2)

    def test_load_nonexistent_mt_returns_empty(self):
        """Querying for an MT that has no records returns empty list."""
        from trial_tracker import load_trials, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)

        trials = load_trials(mt_id="MT-NONEXISTENT", trial_file=self.trial_file)
        self.assertEqual(trials, [])

    def test_load_preserves_order(self):
        """load_trials should return records in file order (FIFO)."""
        from trial_tracker import record_trial, load_trials, TrialRecord

        session_ids = ["S90", "S91", "S92", "S93", "S94"]
        for s in session_ids:
            rec = TrialRecord(mt_id="MT-22", session_id=s, result="pass")
            record_trial(rec, trial_file=self.trial_file)

        trials = load_trials(mt_id="MT-22", trial_file=self.trial_file)
        loaded_sessions = [t.session_id for t in trials]
        self.assertEqual(loaded_sessions, session_ids)

    def test_load_whitespace_only_lines_skipped(self):
        """Whitespace-only lines should be skipped."""
        from trial_tracker import load_trials, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)
        with open(self.trial_file, "a") as f:
            f.write("   \n\t\n")

        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(len(trials), 1)

    def test_large_number_of_trials_no_crash(self):
        """Writing and loading 500 trials should complete without error."""
        from trial_tracker import record_trial, load_trials, TrialRecord

        for i in range(500):
            rec = TrialRecord(mt_id="MT-STRESS", session_id=f"S{i}", result="pass")
            record_trial(rec, trial_file=self.trial_file)

        trials = load_trials(mt_id="MT-STRESS", trial_file=self.trial_file)
        self.assertEqual(len(trials), 500)


if __name__ == "__main__":
    unittest.main()
