#!/usr/bin/env python3
"""Tests for learning_loop.py — Cross-chat learning feedback loop.

Tests the automated outcome reporting + research prioritization pipeline
that connects Kalshi trading results back to CCA research decisions.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from learning_loop import (
    OutcomeReport,
    ResearchPriority,
    LearningLoop,
    process_outcome_reports,
    compute_research_priorities,
    generate_priority_message,
)


class TestOutcomeReport(unittest.TestCase):
    """Tests for OutcomeReport data class."""

    def test_create_from_queue_message(self):
        msg = {
            "id": "msg_001",
            "sender": "km",
            "target": "cca",
            "subject": "Outcome: FLB sniper edge",
            "body": json.dumps({
                "delivery_id": "del_abc123",
                "status": "profitable",
                "profit_cents": 1450,
                "bet_count": 23,
                "notes": "Confirmed +$14.50 over 23 bets",
            }),
            "category": "outcome_report",
        }
        report = OutcomeReport.from_queue_message(msg)
        self.assertEqual(report.delivery_id, "del_abc123")
        self.assertEqual(report.status, "profitable")
        self.assertEqual(report.profit_cents, 1450)
        self.assertEqual(report.bet_count, 23)
        self.assertEqual(report.source_msg_id, "msg_001")

    def test_create_from_queue_message_minimal(self):
        msg = {
            "id": "msg_002",
            "sender": "km",
            "target": "cca",
            "subject": "Outcome: regime detector",
            "body": json.dumps({
                "delivery_id": "del_xyz789",
                "status": "unprofitable",
            }),
            "category": "outcome_report",
        }
        report = OutcomeReport.from_queue_message(msg)
        self.assertEqual(report.delivery_id, "del_xyz789")
        self.assertEqual(report.status, "unprofitable")
        self.assertIsNone(report.profit_cents)
        self.assertIsNone(report.bet_count)

    def test_create_from_invalid_body_raises(self):
        msg = {
            "id": "msg_003",
            "sender": "km",
            "target": "cca",
            "subject": "Bad outcome",
            "body": "not json",
            "category": "outcome_report",
        }
        with self.assertRaises(ValueError):
            OutcomeReport.from_queue_message(msg)

    def test_create_missing_delivery_id_raises(self):
        msg = {
            "id": "msg_004",
            "sender": "km",
            "target": "cca",
            "subject": "No delivery ID",
            "body": json.dumps({"status": "profitable"}),
            "category": "outcome_report",
        }
        with self.assertRaises(ValueError):
            OutcomeReport.from_queue_message(msg)

    def test_create_missing_status_raises(self):
        msg = {
            "id": "msg_005",
            "sender": "km",
            "target": "cca",
            "subject": "No status",
            "body": json.dumps({"delivery_id": "del_001"}),
            "category": "outcome_report",
        }
        with self.assertRaises(ValueError):
            OutcomeReport.from_queue_message(msg)

    def test_to_dict(self):
        report = OutcomeReport(
            delivery_id="del_001",
            status="profitable",
            profit_cents=500,
            bet_count=10,
            notes="Good edge",
            source_msg_id="msg_001",
        )
        d = report.to_dict()
        self.assertEqual(d["delivery_id"], "del_001")
        self.assertEqual(d["status"], "profitable")
        self.assertEqual(d["profit_cents"], 500)
        self.assertEqual(d["bet_count"], 10)


class TestResearchPriority(unittest.TestCase):
    """Tests for ResearchPriority data class."""

    def test_create_priority(self):
        p = ResearchPriority(
            category="academic_paper",
            score=85.5,
            total_deliveries=10,
            profitable_count=7,
            total_profit_cents=3200,
            recommendation="HIGH — papers have 70% hit rate, +$32 total",
        )
        self.assertEqual(p.category, "academic_paper")
        self.assertAlmostEqual(p.score, 85.5)
        self.assertEqual(p.profitable_count, 7)

    def test_to_dict(self):
        p = ResearchPriority(
            category="signal",
            score=20.0,
            total_deliveries=5,
            profitable_count=1,
            total_profit_cents=-800,
            recommendation="LOW — signals have 20% hit rate, -$8 total",
        )
        d = p.to_dict()
        self.assertEqual(d["category"], "signal")
        self.assertEqual(d["score"], 20.0)
        self.assertEqual(d["total_profit_cents"], -800)


class TestLearningLoop(unittest.TestCase):
    """Tests for LearningLoop core logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")
        self.outcomes_path = os.path.join(self.tmpdir, "outcomes.jsonl")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.unlink(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _write_queue(self, messages):
        with open(self.queue_path, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

    def _write_outcomes(self, outcomes):
        with open(self.outcomes_path, "w") as f:
            for o in outcomes:
                f.write(json.dumps(o) + "\n")

    def _read_outcomes(self):
        if not os.path.exists(self.outcomes_path):
            return []
        results = []
        with open(self.outcomes_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        return results

    def test_init(self):
        loop = LearningLoop(
            queue_path=self.queue_path,
            outcomes_path=self.outcomes_path,
        )
        self.assertIsNotNone(loop)

    def test_extract_outcome_reports_from_queue(self):
        self._write_queue([
            {
                "id": "msg_001", "sender": "km", "target": "cca",
                "subject": "Outcome: FLB", "category": "outcome_report",
                "status": "unread",
                "body": json.dumps({"delivery_id": "del_001", "status": "profitable", "profit_cents": 500}),
            },
            {
                "id": "msg_002", "sender": "cca", "target": "km",
                "subject": "New research", "category": "research_finding",
                "status": "unread",
                "body": "Some finding",
            },
            {
                "id": "msg_003", "sender": "kr", "target": "cca",
                "subject": "Outcome: regime", "category": "outcome_report",
                "status": "unread",
                "body": json.dumps({"delivery_id": "del_002", "status": "unprofitable", "profit_cents": -200}),
            },
        ])
        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        reports = loop.extract_outcome_reports()
        self.assertEqual(len(reports), 2)
        self.assertEqual(reports[0].delivery_id, "del_001")
        self.assertEqual(reports[1].delivery_id, "del_002")

    def test_extract_skips_read_messages(self):
        self._write_queue([
            {
                "id": "msg_001", "sender": "km", "target": "cca",
                "subject": "Outcome: old", "category": "outcome_report",
                "status": "read",
                "body": json.dumps({"delivery_id": "del_old", "status": "profitable"}),
            },
        ])
        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        reports = loop.extract_outcome_reports()
        self.assertEqual(len(reports), 0)

    def test_apply_outcomes_updates_research_db(self):
        # Pre-existing delivery in outcomes DB
        self._write_outcomes([
            {
                "delivery_id": "del_001", "session": 100, "title": "FLB paper",
                "category": "academic_paper", "description": "FLB edge",
                "target_chat": "km", "status": "implemented",
                "created_at": "2026-03-20T00:00:00Z",
            },
        ])
        reports = [
            OutcomeReport(
                delivery_id="del_001", status="profitable",
                profit_cents=1450, bet_count=23,
                notes="Confirmed profitable", source_msg_id="msg_001",
            ),
        ]
        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        applied = loop.apply_outcomes(reports)
        self.assertEqual(applied, 1)

        # Verify the outcome was updated
        outcomes = self._read_outcomes()
        updated = [o for o in outcomes if o["delivery_id"] == "del_001"]
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["status"], "profitable")
        self.assertEqual(updated[0]["profit_impact_cents"], 1450)

    def test_apply_outcomes_skips_unknown_delivery(self):
        self._write_outcomes([])
        reports = [
            OutcomeReport(
                delivery_id="del_unknown", status="profitable",
                profit_cents=100, source_msg_id="msg_001",
            ),
        ]
        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        applied = loop.apply_outcomes(reports)
        self.assertEqual(applied, 0)

    def test_compute_priorities_from_outcomes(self):
        self._write_outcomes([
            {"delivery_id": "d1", "category": "academic_paper", "status": "profitable", "profit_impact_cents": 500},
            {"delivery_id": "d2", "category": "academic_paper", "status": "profitable", "profit_impact_cents": 300},
            {"delivery_id": "d3", "category": "academic_paper", "status": "unprofitable", "profit_impact_cents": -100},
            {"delivery_id": "d4", "category": "signal", "status": "unprofitable", "profit_impact_cents": -200},
            {"delivery_id": "d5", "category": "signal", "status": "unprofitable", "profit_impact_cents": -300},
            {"delivery_id": "d6", "category": "tool", "status": "delivered"},
        ])
        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        priorities = loop.compute_priorities()

        # academic_paper: 2/3 profitable, +700 total → high score
        # signal: 0/2 profitable, -500 total → low score
        # tool: no outcome data → neutral
        paper_p = next(p for p in priorities if p.category == "academic_paper")
        signal_p = next(p for p in priorities if p.category == "signal")

        self.assertGreater(paper_p.score, signal_p.score)
        self.assertEqual(paper_p.profitable_count, 2)
        self.assertEqual(paper_p.total_deliveries, 3)
        self.assertEqual(signal_p.profitable_count, 0)
        self.assertEqual(signal_p.total_deliveries, 2)

    def test_compute_priorities_empty_db(self):
        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        priorities = loop.compute_priorities()
        self.assertEqual(len(priorities), 0)

    def test_generate_priority_message(self):
        priorities = [
            ResearchPriority(
                category="academic_paper", score=85.0,
                total_deliveries=10, profitable_count=7,
                total_profit_cents=3200,
                recommendation="HIGH — academic_paper: 70% hit, +$32",
            ),
            ResearchPriority(
                category="signal", score=15.0,
                total_deliveries=5, profitable_count=1,
                total_profit_cents=-800,
                recommendation="LOW — signal: 20% hit, -$8",
            ),
        ]
        msg = generate_priority_message(priorities)
        self.assertIn("academic_paper", msg)
        self.assertIn("signal", msg)
        self.assertIn("HIGH", msg)
        self.assertIn("LOW", msg)

    def test_run_full_cycle(self):
        """End-to-end: queue has outcome reports, outcomes DB has deliveries, run cycle."""
        self._write_outcomes([
            {
                "delivery_id": "del_001", "session": 100, "title": "FLB paper",
                "category": "academic_paper", "description": "FLB edge",
                "target_chat": "km", "status": "implemented",
                "created_at": "2026-03-20T00:00:00Z",
            },
            {
                "delivery_id": "del_002", "session": 105, "title": "Regime detector",
                "category": "framework", "description": "Market regime",
                "target_chat": "km", "status": "implemented",
                "created_at": "2026-03-21T00:00:00Z",
            },
        ])
        self._write_queue([
            {
                "id": "msg_001", "sender": "km", "target": "cca",
                "subject": "Outcome: FLB", "category": "outcome_report",
                "status": "unread",
                "body": json.dumps({
                    "delivery_id": "del_001", "status": "profitable",
                    "profit_cents": 1450, "bet_count": 23,
                }),
            },
            {
                "id": "msg_002", "sender": "km", "target": "cca",
                "subject": "Outcome: regime", "category": "outcome_report",
                "status": "unread",
                "body": json.dumps({
                    "delivery_id": "del_002", "status": "unprofitable",
                    "profit_cents": -300, "bet_count": 8,
                }),
            },
        ])

        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        result = loop.run_cycle()

        self.assertEqual(result["reports_processed"], 2)
        self.assertEqual(result["outcomes_applied"], 2)
        self.assertGreater(len(result["priorities"]), 0)

        # Verify outcomes DB was updated
        outcomes = self._read_outcomes()
        d1 = next(o for o in outcomes if o["delivery_id"] == "del_001")
        d2 = next(o for o in outcomes if o["delivery_id"] == "del_002")
        self.assertEqual(d1["status"], "profitable")
        self.assertEqual(d2["status"], "unprofitable")

    def test_run_cycle_no_reports(self):
        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        result = loop.run_cycle()
        self.assertEqual(result["reports_processed"], 0)
        self.assertEqual(result["outcomes_applied"], 0)

    def test_priority_score_calculation(self):
        """Verify the score formula: win_rate * 50 + profit_factor * 50."""
        self._write_outcomes([
            {"delivery_id": "d1", "category": "academic_paper", "status": "profitable", "profit_impact_cents": 1000},
            {"delivery_id": "d2", "category": "academic_paper", "status": "profitable", "profit_impact_cents": 500},
            {"delivery_id": "d3", "category": "academic_paper", "status": "unprofitable", "profit_impact_cents": -200},
        ])
        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        priorities = loop.compute_priorities()
        paper = next(p for p in priorities if p.category == "academic_paper")
        # win_rate = 2/3 = 0.667 → 33.3 points
        # profit = 1300 cents → capped contribution
        self.assertGreater(paper.score, 50.0)

    def test_only_resolved_deliveries_count(self):
        """Deliveries still in 'delivered' or 'acknowledged' status shouldn't affect scoring."""
        self._write_outcomes([
            {"delivery_id": "d1", "category": "academic_paper", "status": "delivered"},
            {"delivery_id": "d2", "category": "academic_paper", "status": "acknowledged"},
            {"delivery_id": "d3", "category": "academic_paper", "status": "profitable", "profit_impact_cents": 500},
        ])
        loop = LearningLoop(queue_path=self.queue_path, outcomes_path=self.outcomes_path)
        priorities = loop.compute_priorities()
        paper = next(p for p in priorities if p.category == "academic_paper")
        # Only d3 counts as resolved
        self.assertEqual(paper.total_deliveries, 1)
        self.assertEqual(paper.profitable_count, 1)

    def test_format_priority_message_empty(self):
        msg = generate_priority_message([])
        self.assertIn("No outcome data", msg)


class TestProcessOutcomeReports(unittest.TestCase):
    """Tests for the convenience function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")
        self.outcomes_path = os.path.join(self.tmpdir, "outcomes.jsonl")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.unlink(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_process_returns_count(self):
        with open(self.outcomes_path, "w") as f:
            f.write(json.dumps({
                "delivery_id": "del_001", "category": "academic_paper",
                "status": "implemented",
            }) + "\n")
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "id": "msg_001", "sender": "km", "target": "cca",
                "subject": "Outcome: test", "category": "outcome_report",
                "status": "unread",
                "body": json.dumps({"delivery_id": "del_001", "status": "profitable", "profit_cents": 100}),
            }) + "\n")

        count = process_outcome_reports(
            queue_path=self.queue_path,
            outcomes_path=self.outcomes_path,
        )
        self.assertEqual(count, 1)


class TestComputeResearchPriorities(unittest.TestCase):
    """Tests for the convenience function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.outcomes_path = os.path.join(self.tmpdir, "outcomes.jsonl")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.unlink(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_compute_returns_sorted_list(self):
        with open(self.outcomes_path, "w") as f:
            f.write(json.dumps({"delivery_id": "d1", "category": "academic_paper", "status": "profitable", "profit_impact_cents": 1000}) + "\n")
            f.write(json.dumps({"delivery_id": "d2", "category": "signal", "status": "unprofitable", "profit_impact_cents": -500}) + "\n")

        priorities = compute_research_priorities(outcomes_path=self.outcomes_path)
        self.assertEqual(len(priorities), 2)
        # First should be highest score
        self.assertGreaterEqual(priorities[0].score, priorities[1].score)


if __name__ == "__main__":
    unittest.main()
