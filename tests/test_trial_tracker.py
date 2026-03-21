"""
test_trial_tracker.py — Tests for trial_tracker.py

MT-22 needs supervised trial tracking. This module records trial results
for any MT that requires validation gates (e.g., 3/3 supervised passes).

TDD: tests written first, implementation follows.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestTrialRecord(unittest.TestCase):
    """Test the TrialRecord dataclass."""

    def test_create_record_minimal(self):
        from trial_tracker import TrialRecord

        rec = TrialRecord(
            mt_id="MT-22",
            session_id="S99",
            result="pass",
        )
        self.assertEqual(rec.mt_id, "MT-22")
        self.assertEqual(rec.session_id, "S99")
        self.assertEqual(rec.result, "pass")
        self.assertEqual(rec.commits, 0)
        self.assertEqual(rec.tests_added, 0)
        self.assertEqual(rec.coordination_failures, 0)
        self.assertEqual(rec.test_regressions, 0)
        self.assertEqual(rec.notes, "")

    def test_create_record_full(self):
        from trial_tracker import TrialRecord

        rec = TrialRecord(
            mt_id="MT-22",
            session_id="S99",
            result="pass",
            commits=5,
            tests_added=47,
            coordination_failures=0,
            test_regressions=0,
            duration_secs=3600,
            notes="Trial #3 clean",
        )
        self.assertEqual(rec.commits, 5)
        self.assertEqual(rec.tests_added, 47)
        self.assertEqual(rec.duration_secs, 3600)

    def test_create_record_fail(self):
        from trial_tracker import TrialRecord

        rec = TrialRecord(
            mt_id="MT-22",
            session_id="S96",
            result="fail",
            coordination_failures=2,
            notes="Worker crashed mid-task",
        )
        self.assertEqual(rec.result, "fail")
        self.assertEqual(rec.coordination_failures, 2)

    def test_record_has_timestamp(self):
        from trial_tracker import TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        # Should have a non-empty timestamp
        self.assertTrue(len(rec.timestamp) > 0)
        # Should be parseable as ISO format
        datetime.fromisoformat(rec.timestamp)

    def test_record_to_dict(self):
        from trial_tracker import TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass", commits=3)
        d = rec.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["mt_id"], "MT-22")
        self.assertEqual(d["commits"], 3)
        self.assertIn("timestamp", d)

    def test_record_from_dict(self):
        from trial_tracker import TrialRecord

        d = {
            "mt_id": "MT-22",
            "session_id": "S99",
            "result": "pass",
            "timestamp": "2026-03-22T10:00:00+00:00",
            "commits": 5,
            "tests_added": 20,
            "coordination_failures": 0,
            "test_regressions": 0,
            "duration_secs": 3600,
            "notes": "clean",
        }
        rec = TrialRecord.from_dict(d)
        self.assertEqual(rec.mt_id, "MT-22")
        self.assertEqual(rec.commits, 5)
        self.assertEqual(rec.timestamp, "2026-03-22T10:00:00+00:00")


class TestTrialStorage(unittest.TestCase):
    """Test recording and loading trials from JSONL storage."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_record_trial_creates_file(self):
        from trial_tracker import record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)
        self.assertTrue(self.trial_file.exists())

    def test_record_trial_appends(self):
        from trial_tracker import record_trial, TrialRecord

        rec1 = TrialRecord(mt_id="MT-22", session_id="S96", result="pass")
        rec2 = TrialRecord(mt_id="MT-22", session_id="S97", result="pass")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)

        lines = self.trial_file.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)

    def test_load_trials_empty(self):
        from trial_tracker import load_trials

        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(trials, [])

    def test_load_trials_roundtrip(self):
        from trial_tracker import record_trial, load_trials, TrialRecord

        rec = TrialRecord(
            mt_id="MT-22", session_id="S99", result="pass", commits=5, tests_added=30
        )
        record_trial(rec, trial_file=self.trial_file)

        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0].mt_id, "MT-22")
        self.assertEqual(trials[0].commits, 5)

    def test_load_trials_by_mt(self):
        from trial_tracker import record_trial, load_trials, TrialRecord

        rec1 = TrialRecord(mt_id="MT-22", session_id="S96", result="pass")
        rec2 = TrialRecord(mt_id="MT-21", session_id="S97", result="pass")
        rec3 = TrialRecord(mt_id="MT-22", session_id="S97", result="pass")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)
        record_trial(rec3, trial_file=self.trial_file)

        mt22 = load_trials(mt_id="MT-22", trial_file=self.trial_file)
        self.assertEqual(len(mt22), 2)
        self.assertTrue(all(t.mt_id == "MT-22" for t in mt22))

    def test_load_trials_skips_blank_lines(self):
        from trial_tracker import load_trials, TrialRecord, record_trial

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=self.trial_file)
        # Append blank line
        with open(self.trial_file, "a") as f:
            f.write("\n\n")
        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(len(trials), 1)


class TestTrialGate(unittest.TestCase):
    """Test the gate check — are N/N trials passing?"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_gate_no_trials(self):
        from trial_tracker import check_gate

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertFalse(result["passed"])
        self.assertEqual(result["pass_count"], 0)
        self.assertEqual(result["required"], 3)

    def test_gate_partial(self):
        from trial_tracker import check_gate, record_trial, TrialRecord

        rec1 = TrialRecord(mt_id="MT-22", session_id="S96", result="pass")
        rec2 = TrialRecord(mt_id="MT-22", session_id="S97", result="pass")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertFalse(result["passed"])
        self.assertEqual(result["pass_count"], 2)

    def test_gate_exactly_met(self):
        from trial_tracker import check_gate, record_trial, TrialRecord

        for s in ["S96", "S97", "S99"]:
            rec = TrialRecord(mt_id="MT-22", session_id=s, result="pass")
            record_trial(rec, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertTrue(result["passed"])
        self.assertEqual(result["pass_count"], 3)

    def test_gate_exceeds_required(self):
        from trial_tracker import check_gate, record_trial, TrialRecord

        for s in ["S96", "S97", "S98", "S99"]:
            rec = TrialRecord(mt_id="MT-22", session_id=s, result="pass")
            record_trial(rec, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertTrue(result["passed"])
        self.assertEqual(result["pass_count"], 4)

    def test_gate_fails_not_count(self):
        from trial_tracker import check_gate, record_trial, TrialRecord

        rec1 = TrialRecord(mt_id="MT-22", session_id="S96", result="pass")
        rec2 = TrialRecord(mt_id="MT-22", session_id="S97", result="fail")
        rec3 = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)
        record_trial(rec3, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertFalse(result["passed"])
        self.assertEqual(result["pass_count"], 2)
        self.assertEqual(result["fail_count"], 1)

    def test_gate_different_mt_not_counted(self):
        from trial_tracker import check_gate, record_trial, TrialRecord

        rec1 = TrialRecord(mt_id="MT-22", session_id="S96", result="pass")
        rec2 = TrialRecord(mt_id="MT-21", session_id="S97", result="pass")
        rec3 = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)
        record_trial(rec3, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertFalse(result["passed"])
        self.assertEqual(result["pass_count"], 2)

    def test_gate_consecutive_pass_count(self):
        """Gate should report consecutive passes (useful for streaks)."""
        from trial_tracker import check_gate, record_trial, TrialRecord

        rec1 = TrialRecord(mt_id="MT-22", session_id="S96", result="fail")
        rec2 = TrialRecord(mt_id="MT-22", session_id="S97", result="pass")
        rec3 = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)
        record_trial(rec3, trial_file=self.trial_file)

        result = check_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertEqual(result["consecutive_passes"], 2)


class TestTrialStatus(unittest.TestCase):
    """Test the status summary function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_status_no_trials(self):
        from trial_tracker import get_trial_status

        status = get_trial_status("MT-22", trial_file=self.trial_file)
        self.assertEqual(status["total_trials"], 0)
        self.assertEqual(status["passes"], 0)
        self.assertEqual(status["fails"], 0)

    def test_status_with_trials(self):
        from trial_tracker import get_trial_status, record_trial, TrialRecord

        rec1 = TrialRecord(
            mt_id="MT-22", session_id="S96", result="pass", commits=4, tests_added=30
        )
        rec2 = TrialRecord(
            mt_id="MT-22", session_id="S97", result="pass", commits=6, tests_added=50
        )
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)

        status = get_trial_status("MT-22", trial_file=self.trial_file)
        self.assertEqual(status["total_trials"], 2)
        self.assertEqual(status["passes"], 2)
        self.assertEqual(status["fails"], 0)
        self.assertEqual(status["total_commits"], 10)
        self.assertEqual(status["total_tests_added"], 80)

    def test_status_avg_duration(self):
        from trial_tracker import get_trial_status, record_trial, TrialRecord

        rec1 = TrialRecord(
            mt_id="MT-22", session_id="S96", result="pass", duration_secs=3000
        )
        rec2 = TrialRecord(
            mt_id="MT-22", session_id="S97", result="pass", duration_secs=3600
        )
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)

        status = get_trial_status("MT-22", trial_file=self.trial_file)
        self.assertEqual(status["avg_duration_secs"], 3300)


class TestTrialCLI(unittest.TestCase):
    """Test the CLI interface."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_cli_record(self):
        from trial_tracker import cli_record

        cli_record(
            mt_id="MT-22",
            session_id="S99",
            result="pass",
            commits=5,
            tests_added=30,
            trial_file=self.trial_file,
        )

        from trial_tracker import load_trials

        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(len(trials), 1)
        self.assertEqual(trials[0].session_id, "S99")

    def test_cli_record_invalid_result(self):
        from trial_tracker import cli_record

        with self.assertRaises(ValueError):
            cli_record(
                mt_id="MT-22",
                session_id="S99",
                result="maybe",
                trial_file=self.trial_file,
            )

    def test_cli_gate_output(self):
        from trial_tracker import cli_gate, record_trial, TrialRecord

        for s in ["S96", "S97", "S99"]:
            rec = TrialRecord(mt_id="MT-22", session_id=s, result="pass")
            record_trial(rec, trial_file=self.trial_file)

        result = cli_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertTrue(result["passed"])
        self.assertIn("GATE PASSED", result["message"])

    def test_cli_gate_not_met(self):
        from trial_tracker import cli_gate, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S96", result="pass")
        record_trial(rec, trial_file=self.trial_file)

        result = cli_gate("MT-22", required=3, trial_file=self.trial_file)
        self.assertFalse(result["passed"])
        self.assertIn("GATE NOT MET", result["message"])


class TestEdgeCases(unittest.TestCase):
    """Edge cases and error handling."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.trial_file = Path(self.tmpdir) / "trials.jsonl"

    def tearDown(self):
        if self.trial_file.exists():
            self.trial_file.unlink()
        os.rmdir(self.tmpdir)

    def test_corrupt_json_line_skipped(self):
        """Corrupt JSONL lines should be skipped, not crash."""
        from trial_tracker import load_trials, record_trial, TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S96", result="pass")
        record_trial(rec, trial_file=self.trial_file)
        # Append corrupt line
        with open(self.trial_file, "a") as f:
            f.write("{corrupt json\n")
        rec2 = TrialRecord(mt_id="MT-22", session_id="S97", result="pass")
        record_trial(rec2, trial_file=self.trial_file)

        trials = load_trials(trial_file=self.trial_file)
        self.assertEqual(len(trials), 2)

    def test_duplicate_session_id(self):
        """Recording same session twice should work (append-only)."""
        from trial_tracker import record_trial, load_trials, TrialRecord

        rec1 = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        rec2 = TrialRecord(mt_id="MT-22", session_id="S99", result="fail")
        record_trial(rec1, trial_file=self.trial_file)
        record_trial(rec2, trial_file=self.trial_file)

        trials = load_trials(mt_id="MT-22", trial_file=self.trial_file)
        self.assertEqual(len(trials), 2)

    def test_empty_mt_id(self):
        from trial_tracker import TrialRecord

        with self.assertRaises(ValueError):
            TrialRecord(mt_id="", session_id="S99", result="pass")

    def test_empty_session_id(self):
        from trial_tracker import TrialRecord

        with self.assertRaises(ValueError):
            TrialRecord(mt_id="MT-22", session_id="", result="pass")

    def test_negative_commits(self):
        from trial_tracker import TrialRecord

        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass", commits=-1)
        # Should clamp or allow — we'll allow it (data integrity > validation)
        self.assertEqual(rec.commits, -1)

    def test_file_in_nonexistent_dir(self):
        """Should create parent directories."""
        from trial_tracker import record_trial, TrialRecord

        deep_file = Path(self.tmpdir) / "sub" / "deep" / "trials.jsonl"
        rec = TrialRecord(mt_id="MT-22", session_id="S99", result="pass")
        record_trial(rec, trial_file=deep_file)
        self.assertTrue(deep_file.exists())
        # Cleanup
        deep_file.unlink()
        deep_file.parent.rmdir()
        deep_file.parent.parent.rmdir()


if __name__ == "__main__":
    unittest.main()
