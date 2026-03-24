#!/usr/bin/env python3
"""Tests for batch_wrap_learning.py — MT-36 Phase 3.

Consolidates 11 self-learning wrap subprocess calls into a single batch.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from batch_wrap_learning import (
    WrapBatch,
    BatchResult,
    run_batch,
)


class TestWrapBatch(unittest.TestCase):
    """Test WrapBatch data structure."""

    def test_create(self):
        batch = WrapBatch(
            session_id=147,
            grade="B",
            wins=["Built efficiency analyzer"],
            losses=["Priority picker stale data"],
            outcome="success",
            summary="MT-36 Phase 2 complete",
            domain="general",
            tests_added=32,
            tests_total=8715,
            tips=["Wire session_timer into wrap steps"],
        )
        self.assertEqual(batch.session_id, 147)
        self.assertEqual(batch.grade, "B")
        self.assertEqual(len(batch.wins), 1)

    def test_validate_grade(self):
        batch = WrapBatch(session_id=1, grade="A", wins=[], losses=[],
                          outcome="success", summary="ok", domain="general",
                          tests_added=0, tests_total=100, tips=[])
        self.assertTrue(batch.is_valid())

    def test_invalid_grade(self):
        batch = WrapBatch(session_id=1, grade="X", wins=[], losses=[],
                          outcome="success", summary="ok", domain="general",
                          tests_added=0, tests_total=100, tips=[])
        self.assertFalse(batch.is_valid())

    def test_invalid_outcome(self):
        batch = WrapBatch(session_id=1, grade="A", wins=[], losses=[],
                          outcome="amazing", summary="ok", domain="general",
                          tests_added=0, tests_total=100, tips=[])
        self.assertFalse(batch.is_valid())

    def test_outcome_from_grade(self):
        self.assertEqual(WrapBatch.grade_to_outcome("A"), "success")
        self.assertEqual(WrapBatch.grade_to_outcome("B"), "success")
        self.assertEqual(WrapBatch.grade_to_outcome("C"), "partial")
        self.assertEqual(WrapBatch.grade_to_outcome("D"), "failure")


class TestBatchResult(unittest.TestCase):
    """Test BatchResult tracking."""

    def test_create(self):
        result = BatchResult()
        self.assertEqual(result.steps_run, 0)
        self.assertEqual(result.steps_failed, 0)
        self.assertEqual(len(result.errors), 0)

    def test_record_success(self):
        result = BatchResult()
        result.record("journal_log", True)
        self.assertEqual(result.steps_run, 1)
        self.assertEqual(result.steps_failed, 0)

    def test_record_failure(self):
        result = BatchResult()
        result.record("journal_log", False, "file not found")
        self.assertEqual(result.steps_run, 1)
        self.assertEqual(result.steps_failed, 1)
        self.assertEqual(result.errors[0], "journal_log: file not found")

    def test_summary(self):
        result = BatchResult()
        result.record("step1", True)
        result.record("step2", False, "err")
        result.record("step3", True)
        summary = result.summary()
        self.assertIn("3 steps", summary)
        self.assertIn("1 failed", summary)

    def test_all_ok(self):
        result = BatchResult()
        result.record("step1", True)
        result.record("step2", True)
        self.assertTrue(result.all_ok)

    def test_not_all_ok(self):
        result = BatchResult()
        result.record("step1", True)
        result.record("step2", False, "err")
        self.assertFalse(result.all_ok)


class TestRunBatch(unittest.TestCase):
    """Test the batch execution with temp directories."""

    def test_batch_writes_journal(self):
        """Batch should write session_outcome to journal JSONL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = os.path.join(tmpdir, "journal.jsonl")
            batch = WrapBatch(
                session_id=147, grade="B",
                wins=["Built analyzer"], losses=["Stale data"],
                outcome="success", summary="MT-36 done",
                domain="general", tests_added=32, tests_total=8715,
                tips=["Wire timer"],
            )
            result = run_batch(batch, journal_path=journal_path,
                             wrap_path=os.path.join(tmpdir, "wrap.jsonl"),
                             tip_path=os.path.join(tmpdir, "tips.jsonl"),
                             outcome_path=os.path.join(tmpdir, "outcomes.jsonl"))
            self.assertTrue(os.path.exists(journal_path))
            with open(journal_path) as f:
                lines = f.readlines()
            self.assertGreaterEqual(len(lines), 1)  # At least session_outcome
            entry = json.loads(lines[0])
            self.assertEqual(entry["event_type"], "session_outcome")
            self.assertEqual(entry["session"], 147)

    def test_batch_writes_wins_and_losses(self):
        """Each win/loss should be a separate journal entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = os.path.join(tmpdir, "journal.jsonl")
            batch = WrapBatch(
                session_id=100, grade="A",
                wins=["Win 1", "Win 2"], losses=["Loss 1"],
                outcome="success", summary="good",
                domain="general", tests_added=10, tests_total=500,
                tips=[],
            )
            result = run_batch(batch, journal_path=journal_path,
                             wrap_path=os.path.join(tmpdir, "wrap.jsonl"),
                             tip_path=os.path.join(tmpdir, "tips.jsonl"),
                             outcome_path=os.path.join(tmpdir, "outcomes.jsonl"))
            with open(journal_path) as f:
                lines = f.readlines()
            # 1 session_outcome + 2 wins + 1 loss = 4 entries
            self.assertEqual(len(lines), 4)
            types = [json.loads(l)["event_type"] for l in lines]
            self.assertEqual(types.count("win"), 2)
            self.assertEqual(types.count("pain"), 1)

    def test_batch_writes_wrap_assessment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wrap_path = os.path.join(tmpdir, "wrap.jsonl")
            batch = WrapBatch(
                session_id=100, grade="B",
                wins=["Win"], losses=[],
                outcome="success", summary="good",
                domain="general", tests_added=5, tests_total=500,
                tips=[],
            )
            result = run_batch(batch, journal_path=os.path.join(tmpdir, "j.jsonl"),
                             wrap_path=wrap_path,
                             tip_path=os.path.join(tmpdir, "tips.jsonl"),
                             outcome_path=os.path.join(tmpdir, "outcomes.jsonl"))
            self.assertTrue(os.path.exists(wrap_path))
            with open(wrap_path) as f:
                entry = json.loads(f.readline())
            self.assertEqual(entry["session"], 100)
            self.assertEqual(entry["grade"], "B")

    def test_batch_writes_tips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tip_path = os.path.join(tmpdir, "tips.jsonl")
            batch = WrapBatch(
                session_id=100, grade="A",
                wins=[], losses=[],
                outcome="success", summary="good",
                domain="general", tests_added=0, tests_total=500,
                tips=["Tip one", "Tip two"],
            )
            result = run_batch(batch, journal_path=os.path.join(tmpdir, "j.jsonl"),
                             wrap_path=os.path.join(tmpdir, "wrap.jsonl"),
                             tip_path=tip_path,
                             outcome_path=os.path.join(tmpdir, "outcomes.jsonl"))
            with open(tip_path) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 2)

    def test_batch_writes_outcome(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outcome_path = os.path.join(tmpdir, "outcomes.jsonl")
            batch = WrapBatch(
                session_id=100, grade="A",
                wins=["Win"], losses=[],
                outcome="success", summary="good",
                domain="general", tests_added=10, tests_total=500,
                tips=[],
            )
            result = run_batch(batch, journal_path=os.path.join(tmpdir, "j.jsonl"),
                             wrap_path=os.path.join(tmpdir, "wrap.jsonl"),
                             tip_path=os.path.join(tmpdir, "tips.jsonl"),
                             outcome_path=outcome_path)
            self.assertTrue(os.path.exists(outcome_path))
            with open(outcome_path) as f:
                entry = json.loads(f.readline())
            self.assertEqual(entry["session"], 100)
            self.assertEqual(entry["tests_added"], 10)

    def test_batch_result_reports_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            batch = WrapBatch(
                session_id=100, grade="A",
                wins=[], losses=[],
                outcome="success", summary="good",
                domain="general", tests_added=0, tests_total=500,
                tips=[],
            )
            result = run_batch(batch, journal_path=os.path.join(tmpdir, "j.jsonl"),
                             wrap_path=os.path.join(tmpdir, "wrap.jsonl"),
                             tip_path=os.path.join(tmpdir, "tips.jsonl"),
                             outcome_path=os.path.join(tmpdir, "outcomes.jsonl"))
            self.assertTrue(result.all_ok)
            self.assertGreater(result.steps_run, 0)

    def test_batch_empty_wins_losses_tips(self):
        """Batch with no wins, losses, or tips still writes session_outcome."""
        with tempfile.TemporaryDirectory() as tmpdir:
            journal_path = os.path.join(tmpdir, "journal.jsonl")
            batch = WrapBatch(
                session_id=100, grade="C",
                wins=[], losses=[],
                outcome="partial", summary="meh",
                domain="general", tests_added=0, tests_total=500,
                tips=[],
            )
            result = run_batch(batch, journal_path=journal_path,
                             wrap_path=os.path.join(tmpdir, "wrap.jsonl"),
                             tip_path=os.path.join(tmpdir, "tips.jsonl"),
                             outcome_path=os.path.join(tmpdir, "outcomes.jsonl"))
            with open(journal_path) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)  # Just session_outcome


if __name__ == "__main__":
    unittest.main()
