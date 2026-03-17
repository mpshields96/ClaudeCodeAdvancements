#!/usr/bin/env python3
"""Tests for improver.py — MT-10: YoYo self-learning improvement loop.

Tests the improvement proposal generation, risk classification,
lifecycle tracking, and safety guards.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)

import improver


class TestImprovementProposal(unittest.TestCase):
    """Test ImprovementProposal data structure."""

    def test_create_proposal_basic(self):
        p = improver.ImprovementProposal(
            pattern_type="retry_loop",
            pattern_data={"file": "test.py", "count": 5},
            source="trace_analysis",
            proposed_fix="Add pre-read guard before Edit",
            expected_improvement="Reduce Edit retries by 50%",
            test_plan="Compare retry count over 3 sessions",
            risk_level="LOW",
            target_module="self-learning",
        )
        self.assertEqual(p.pattern_type, "retry_loop")
        self.assertEqual(p.risk_level, "LOW")
        self.assertEqual(p.status, "proposed")
        self.assertIsNotNone(p.id)
        self.assertTrue(p.id.startswith("imp_"))
        self.assertIsNotNone(p.timestamp)

    def test_proposal_id_has_8_char_suffix(self):
        p = improver.ImprovementProposal(
            pattern_type="waste",
            pattern_data={},
            source="trace_analysis",
            proposed_fix="x",
            expected_improvement="x",
            test_plan="x",
            risk_level="LOW",
            target_module="self-learning",
        )
        # imp_YYYYMMDD_HHMMSS_8hexchars
        parts = p.id.split("_")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "imp")
        self.assertEqual(len(parts[3]), 8)

    def test_proposal_to_dict(self):
        p = improver.ImprovementProposal(
            pattern_type="retry_loop",
            pattern_data={"file": "x.py"},
            source="trace_analysis",
            proposed_fix="fix it",
            expected_improvement="better",
            test_plan="check it",
            risk_level="MEDIUM",
            target_module="agent-guard",
            target_file="agent-guard/hooks/mobile_approver.py",
            session_id=28,
        )
        d = p.to_dict()
        self.assertEqual(d["pattern_type"], "retry_loop")
        self.assertEqual(d["risk_level"], "MEDIUM")
        self.assertEqual(d["status"], "proposed")
        self.assertEqual(d["target_file"], "agent-guard/hooks/mobile_approver.py")
        self.assertEqual(d["session_id"], 28)
        self.assertIsNone(d["outcome"])

    def test_proposal_from_dict(self):
        d = {
            "id": "imp_20260317_120000_abcdef12",
            "timestamp": "2026-03-17T12:00:00Z",
            "status": "validated",
            "pattern_type": "waste",
            "pattern_data": {},
            "source": "reflect_pattern",
            "proposed_fix": "foo",
            "expected_improvement": "bar",
            "test_plan": "baz",
            "risk_level": "HIGH",
            "target_module": "context-monitor",
            "target_file": None,
            "outcome": {"improved": True, "metric_before": 0.5, "metric_after": 0.2},
            "session_id": 27,
        }
        p = improver.ImprovementProposal.from_dict(d)
        self.assertEqual(p.id, "imp_20260317_120000_abcdef12")
        self.assertEqual(p.status, "validated")
        self.assertEqual(p.outcome["improved"], True)

    def test_valid_risk_levels(self):
        for level in ("LOW", "MEDIUM", "HIGH"):
            p = improver.ImprovementProposal(
                pattern_type="x", pattern_data={}, source="manual",
                proposed_fix="x", expected_improvement="x", test_plan="x",
                risk_level=level, target_module="self-learning",
            )
            self.assertEqual(p.risk_level, level)

    def test_invalid_risk_level_rejected(self):
        with self.assertRaises(ValueError):
            improver.ImprovementProposal(
                pattern_type="x", pattern_data={}, source="manual",
                proposed_fix="x", expected_improvement="x", test_plan="x",
                risk_level="EXTREME", target_module="self-learning",
            )

    def test_valid_statuses(self):
        p = improver.ImprovementProposal(
            pattern_type="x", pattern_data={}, source="manual",
            proposed_fix="x", expected_improvement="x", test_plan="x",
            risk_level="LOW", target_module="self-learning",
        )
        for status in ("proposed", "approved", "building", "validated", "committed", "rejected", "superseded"):
            p.status = status  # Should not raise

    def test_valid_sources(self):
        for source in ("trace_analysis", "reflect_pattern", "manual"):
            p = improver.ImprovementProposal(
                pattern_type="x", pattern_data={}, source=source,
                proposed_fix="x", expected_improvement="x", test_plan="x",
                risk_level="LOW", target_module="self-learning",
            )
            self.assertEqual(p.source, source)


class TestImprovementStore(unittest.TestCase):
    """Test the JSONL improvement log persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "improvements.jsonl")
        self.store = improver.ImprovementStore(self.store_path)

    def test_empty_store(self):
        self.assertEqual(self.store.load_all(), [])

    def test_append_and_load(self):
        p = improver.ImprovementProposal(
            pattern_type="retry_loop", pattern_data={"count": 5},
            source="trace_analysis", proposed_fix="fix",
            expected_improvement="better", test_plan="check",
            risk_level="LOW", target_module="self-learning",
        )
        self.store.append(p)
        loaded = self.store.load_all()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].pattern_type, "retry_loop")

    def test_append_multiple(self):
        for i in range(5):
            p = improver.ImprovementProposal(
                pattern_type=f"type_{i}", pattern_data={},
                source="manual", proposed_fix=f"fix_{i}",
                expected_improvement="x", test_plan="x",
                risk_level="LOW", target_module="self-learning",
            )
            self.store.append(p)
        self.assertEqual(len(self.store.load_all()), 5)

    def test_update_status(self):
        p = improver.ImprovementProposal(
            pattern_type="waste", pattern_data={},
            source="trace_analysis", proposed_fix="fix",
            expected_improvement="better", test_plan="check",
            risk_level="LOW", target_module="self-learning",
        )
        self.store.append(p)
        self.store.update_status(p.id, "approved")
        loaded = self.store.load_all()
        self.assertEqual(loaded[0].status, "approved")

    def test_update_outcome(self):
        p = improver.ImprovementProposal(
            pattern_type="waste", pattern_data={},
            source="trace_analysis", proposed_fix="fix",
            expected_improvement="better", test_plan="check",
            risk_level="LOW", target_module="self-learning",
        )
        self.store.append(p)
        outcome = {"improved": True, "metric_before": 0.5, "metric_after": 0.2}
        self.store.update_outcome(p.id, outcome)
        loaded = self.store.load_all()
        self.assertEqual(loaded[0].outcome, outcome)

    def test_update_nonexistent_id_no_error(self):
        # Should not raise — just does nothing
        self.store.update_status("imp_nonexistent_00000000", "approved")

    def test_get_pending(self):
        for i, status in enumerate(["proposed", "approved", "committed", "proposed"]):
            p = improver.ImprovementProposal(
                pattern_type=f"t{i}", pattern_data={},
                source="manual", proposed_fix="x",
                expected_improvement="x", test_plan="x",
                risk_level="LOW", target_module="self-learning",
            )
            p.status = status
            self.store.append(p)
        pending = self.store.get_pending()
        self.assertEqual(len(pending), 2)
        for p in pending:
            self.assertEqual(p.status, "proposed")

    def test_get_by_status(self):
        for i, status in enumerate(["proposed", "approved", "committed", "rejected"]):
            p = improver.ImprovementProposal(
                pattern_type=f"t{i}", pattern_data={},
                source="manual", proposed_fix="x",
                expected_improvement="x", test_plan="x",
                risk_level="LOW", target_module="self-learning",
            )
            p.status = status
            self.store.append(p)
        self.assertEqual(len(self.store.get_by_status("committed")), 1)
        self.assertEqual(len(self.store.get_by_status("rejected")), 1)

    def test_corrupted_line_skipped(self):
        # Write a corrupted line then a valid one
        with open(self.store_path, "w") as f:
            f.write("NOT VALID JSON\n")
            p = improver.ImprovementProposal(
                pattern_type="ok", pattern_data={},
                source="manual", proposed_fix="x",
                expected_improvement="x", test_plan="x",
                risk_level="LOW", target_module="self-learning",
            )
            f.write(json.dumps(p.to_dict()) + "\n")
        loaded = self.store.load_all()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].pattern_type, "ok")


class TestProposalGenerator(unittest.TestCase):
    """Test generation of improvement proposals from patterns."""

    def test_retry_loop_generates_proposal(self):
        trace_report = {
            "retries": {
                "retries": [
                    {"file": "foo.py", "tool": "Edit", "count": 5, "severity": "major", "error_confirmed": True}
                ],
                "total_retries": 1,
            },
            "waste": {"wasted_reads": [], "total_reads": 10, "waste_rate": 0.1},
            "efficiency": {"ratio": 0.3, "rating": "good", "unique_files": 10, "total_calls": 30},
            "velocity": {"commits": 3, "file_creates": 2, "deliverables": 5, "total_calls": 30, "velocity_pct": 16.7},
            "score": 70,
        }
        proposals = improver.ProposalGenerator.from_trace_report(trace_report)
        retry_props = [p for p in proposals if p.pattern_type == "retry_loop"]
        self.assertGreaterEqual(len(retry_props), 1)
        self.assertEqual(retry_props[0].source, "trace_analysis")
        self.assertIn("foo.py", retry_props[0].proposed_fix)

    def test_high_waste_generates_proposal(self):
        trace_report = {
            "retries": {"retries": [], "total_retries": 0},
            "waste": {
                "wasted_reads": [{"file": "a.py", "position": 5}, {"file": "b.py", "position": 10}],
                "total_reads": 4,
                "waste_rate": 0.5,
            },
            "efficiency": {"ratio": 0.3, "rating": "good", "unique_files": 10, "total_calls": 30},
            "velocity": {"commits": 2, "file_creates": 1, "deliverables": 3, "total_calls": 30, "velocity_pct": 10.0},
            "score": 60,
        }
        proposals = improver.ProposalGenerator.from_trace_report(trace_report)
        waste_props = [p for p in proposals if p.pattern_type == "high_waste"]
        self.assertGreaterEqual(len(waste_props), 1)

    def test_low_efficiency_generates_proposal(self):
        trace_report = {
            "retries": {"retries": [], "total_retries": 0},
            "waste": {"wasted_reads": [], "total_reads": 10, "waste_rate": 0.1},
            "efficiency": {"ratio": 0.05, "rating": "poor", "unique_files": 2, "total_calls": 40},
            "velocity": {"commits": 1, "file_creates": 0, "deliverables": 1, "total_calls": 40, "velocity_pct": 2.5},
            "score": 55,
        }
        proposals = improver.ProposalGenerator.from_trace_report(trace_report)
        eff_props = [p for p in proposals if p.pattern_type == "low_efficiency"]
        self.assertGreaterEqual(len(eff_props), 1)

    def test_no_deliverables_generates_proposal(self):
        trace_report = {
            "retries": {"retries": [], "total_retries": 0},
            "waste": {"wasted_reads": [], "total_reads": 5, "waste_rate": 0.0},
            "efficiency": {"ratio": 0.3, "rating": "good", "unique_files": 10, "total_calls": 30},
            "velocity": {"commits": 0, "file_creates": 0, "deliverables": 0, "total_calls": 30, "velocity_pct": 0.0},
            "score": 70,
        }
        proposals = improver.ProposalGenerator.from_trace_report(trace_report)
        vel_props = [p for p in proposals if p.pattern_type == "no_deliverables"]
        self.assertGreaterEqual(len(vel_props), 1)

    def test_clean_trace_no_proposals(self):
        trace_report = {
            "retries": {"retries": [], "total_retries": 0},
            "waste": {"wasted_reads": [], "total_reads": 10, "waste_rate": 0.1},
            "efficiency": {"ratio": 0.4, "rating": "good", "unique_files": 12, "total_calls": 30},
            "velocity": {"commits": 3, "file_creates": 2, "deliverables": 5, "total_calls": 30, "velocity_pct": 16.7},
            "score": 95,
        }
        proposals = improver.ProposalGenerator.from_trace_report(trace_report)
        self.assertEqual(len(proposals), 0)

    def test_from_reflect_patterns(self):
        patterns = [
            {
                "type": "high_skip_rate",
                "severity": "info",
                "message": "Skip rate is 65%",
                "data": {"skip_rate": 0.65, "build_rate": 0.03},
                "suggestion": {"nuclear_scan.min_score_threshold": 50},
            },
        ]
        proposals = improver.ProposalGenerator.from_reflect_patterns(patterns)
        self.assertGreaterEqual(len(proposals), 1)
        self.assertEqual(proposals[0].pattern_type, "high_skip_rate")
        self.assertEqual(proposals[0].source, "reflect_pattern")

    def test_losing_strategy_generates_high_risk(self):
        patterns = [
            {
                "type": "losing_strategy",
                "severity": "warning",
                "message": "Strategy 'momentum' has 30% win rate",
                "data": {"strategy": "momentum", "win_rate": 0.3, "bets": 25, "pnl_cents": -500},
            },
        ]
        proposals = improver.ProposalGenerator.from_reflect_patterns(patterns)
        strat_props = [p for p in proposals if p.pattern_type == "losing_strategy"]
        self.assertGreaterEqual(len(strat_props), 1)
        # Trading strategies should be HIGH risk (never auto-adjust)
        self.assertEqual(strat_props[0].risk_level, "HIGH")

    def test_stale_strategy_generates_low_risk(self):
        patterns = [
            {
                "type": "stale_strategy",
                "severity": "info",
                "message": "Strategy config is 20 days old",
                "data": {"days_old": 20, "entries_since": 50},
            },
        ]
        proposals = improver.ProposalGenerator.from_reflect_patterns(patterns)
        stale_props = [p for p in proposals if p.pattern_type == "stale_strategy"]
        self.assertGreaterEqual(len(stale_props), 1)
        self.assertEqual(stale_props[0].risk_level, "LOW")

    def test_duplicate_pattern_deduped(self):
        """Same pattern type + same file should not produce multiple proposals."""
        trace_report = {
            "retries": {
                "retries": [
                    {"file": "foo.py", "tool": "Edit", "count": 3, "severity": "minor", "error_confirmed": False},
                    {"file": "foo.py", "tool": "Edit", "count": 4, "severity": "minor", "error_confirmed": True},
                ],
                "total_retries": 2,
            },
            "waste": {"wasted_reads": [], "total_reads": 5, "waste_rate": 0.0},
            "efficiency": {"ratio": 0.3, "rating": "good", "unique_files": 10, "total_calls": 30},
            "velocity": {"commits": 2, "file_creates": 1, "deliverables": 3, "total_calls": 30, "velocity_pct": 10.0},
            "score": 80,
        }
        proposals = improver.ProposalGenerator.from_trace_report(trace_report)
        retry_props = [p for p in proposals if p.pattern_type == "retry_loop"]
        # Should dedupe retries on same file
        files = [p.pattern_data.get("file") for p in retry_props]
        self.assertEqual(len(set(files)), len(files))


class TestImprover(unittest.TestCase):
    """Test the Improver orchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "improvements.jsonl")

    def test_generate_and_store_from_trace(self):
        trace_report = {
            "retries": {
                "retries": [
                    {"file": "x.py", "tool": "Edit", "count": 6, "severity": "major", "error_confirmed": True}
                ],
                "total_retries": 1,
            },
            "waste": {"wasted_reads": [{"file": "a.py", "position": 5}], "total_reads": 3, "waste_rate": 0.33},
            "efficiency": {"ratio": 0.2, "rating": "mediocre", "unique_files": 6, "total_calls": 30},
            "velocity": {"commits": 1, "file_creates": 1, "deliverables": 2, "total_calls": 30, "velocity_pct": 6.7},
            "score": 55,
        }
        imp = improver.Improver(store_path=self.store_path)
        proposals = imp.generate_from_trace(trace_report, session_id=28)
        self.assertGreater(len(proposals), 0)
        # Should be persisted
        stored = imp.store.load_all()
        self.assertEqual(len(stored), len(proposals))

    def test_generate_from_reflect(self):
        patterns = [
            {
                "type": "high_skip_rate",
                "severity": "info",
                "message": "Skip rate is 65%",
                "data": {"skip_rate": 0.65},
                "suggestion": {"nuclear_scan.min_score_threshold": 50},
            },
        ]
        imp = improver.Improver(store_path=self.store_path)
        proposals = imp.generate_from_reflect(patterns, session_id=28)
        self.assertGreater(len(proposals), 0)

    def test_max_proposals_per_session_guard(self):
        """Guard: max proposals per session (default 5)."""
        trace_report = {
            "retries": {
                "retries": [
                    {"file": f"f{i}.py", "tool": "Edit", "count": 5, "severity": "major", "error_confirmed": True}
                    for i in range(10)
                ],
                "total_retries": 10,
            },
            "waste": {
                "wasted_reads": [{"file": f"w{i}.py", "position": i} for i in range(10)],
                "total_reads": 15,
                "waste_rate": 0.67,
            },
            "efficiency": {"ratio": 0.05, "rating": "poor", "unique_files": 2, "total_calls": 40},
            "velocity": {"commits": 0, "file_creates": 0, "deliverables": 0, "total_calls": 40, "velocity_pct": 0.0},
            "score": 10,
        }
        imp = improver.Improver(store_path=self.store_path, max_proposals_per_session=5)
        proposals = imp.generate_from_trace(trace_report, session_id=28)
        self.assertLessEqual(len(proposals), 5)

    def test_auto_approve_low_risk(self):
        """LOW risk proposals auto-approve."""
        trace_report = {
            "retries": {
                "retries": [
                    {"file": "x.py", "tool": "Edit", "count": 8, "severity": "critical", "error_confirmed": True}
                ],
                "total_retries": 1,
            },
            "waste": {"wasted_reads": [], "total_reads": 5, "waste_rate": 0.0},
            "efficiency": {"ratio": 0.3, "rating": "good", "unique_files": 10, "total_calls": 30},
            "velocity": {"commits": 2, "file_creates": 1, "deliverables": 3, "total_calls": 30, "velocity_pct": 10.0},
            "score": 60,
        }
        imp = improver.Improver(store_path=self.store_path, auto_approve_low=True)
        proposals = imp.generate_from_trace(trace_report, session_id=28)
        low_risk = [p for p in proposals if p.risk_level == "LOW"]
        for p in low_risk:
            self.assertEqual(p.status, "approved")

    def test_no_auto_approve_medium_high(self):
        """MEDIUM and HIGH risk proposals stay as proposed."""
        patterns = [
            {
                "type": "losing_strategy",
                "severity": "warning",
                "message": "Strategy 'momentum' losing",
                "data": {"strategy": "momentum", "win_rate": 0.3, "bets": 25, "pnl_cents": -500},
            },
        ]
        imp = improver.Improver(store_path=self.store_path, auto_approve_low=True)
        proposals = imp.generate_from_reflect(patterns, session_id=28)
        high_risk = [p for p in proposals if p.risk_level == "HIGH"]
        for p in high_risk:
            self.assertEqual(p.status, "proposed")

    def test_get_actionable_proposals(self):
        """get_actionable returns approved proposals only."""
        imp = improver.Improver(store_path=self.store_path)
        # Add proposals with different statuses
        for i, status in enumerate(["proposed", "approved", "approved", "committed", "rejected"]):
            p = improver.ImprovementProposal(
                pattern_type=f"t{i}", pattern_data={},
                source="manual", proposed_fix=f"fix_{i}",
                expected_improvement="x", test_plan="x",
                risk_level="LOW", target_module="self-learning",
            )
            p.status = status
            imp.store.append(p)
        actionable = imp.get_actionable()
        self.assertEqual(len(actionable), 2)
        for p in actionable:
            self.assertEqual(p.status, "approved")

    def test_record_outcome_success(self):
        imp = improver.Improver(store_path=self.store_path)
        p = improver.ImprovementProposal(
            pattern_type="retry_loop", pattern_data={},
            source="trace_analysis", proposed_fix="fix",
            expected_improvement="better", test_plan="check",
            risk_level="LOW", target_module="self-learning",
        )
        imp.store.append(p)
        imp.record_outcome(p.id, improved=True, metric_before=0.5, metric_after=0.2)
        loaded = imp.store.load_all()
        self.assertEqual(loaded[0].status, "validated")
        self.assertEqual(loaded[0].outcome["improved"], True)

    def test_record_outcome_failure(self):
        imp = improver.Improver(store_path=self.store_path)
        p = improver.ImprovementProposal(
            pattern_type="waste", pattern_data={},
            source="trace_analysis", proposed_fix="fix",
            expected_improvement="better", test_plan="check",
            risk_level="LOW", target_module="self-learning",
        )
        imp.store.append(p)
        imp.record_outcome(p.id, improved=False, metric_before=0.5, metric_after=0.5)
        loaded = imp.store.load_all()
        self.assertEqual(loaded[0].status, "rejected")

    def test_get_stats(self):
        imp = improver.Improver(store_path=self.store_path)
        for i, status in enumerate(["proposed", "approved", "committed", "committed", "rejected"]):
            p = improver.ImprovementProposal(
                pattern_type=f"t{i}", pattern_data={},
                source="manual", proposed_fix=f"fix_{i}",
                expected_improvement="x", test_plan="x",
                risk_level="LOW", target_module="self-learning",
            )
            p.status = status
            if status == "committed":
                p.outcome = {"improved": True, "metric_before": 0.5, "metric_after": 0.3}
            elif status == "rejected":
                p.outcome = {"improved": False, "metric_before": 0.5, "metric_after": 0.5}
            imp.store.append(p)
        stats = imp.get_stats()
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["by_status"]["proposed"], 1)
        self.assertEqual(stats["by_status"]["committed"], 2)
        self.assertEqual(stats["success_rate"], 2/3)  # 2 committed / (2 committed + 1 rejected)

    def test_dedup_across_sessions(self):
        """Proposals for the same pattern on the same file should be deduped across sessions."""
        imp = improver.Improver(store_path=self.store_path)
        # First session generates a retry proposal for foo.py
        p1 = improver.ImprovementProposal(
            pattern_type="retry_loop", pattern_data={"file": "foo.py"},
            source="trace_analysis", proposed_fix="fix",
            expected_improvement="better", test_plan="check",
            risk_level="LOW", target_module="self-learning",
        )
        imp.store.append(p1)

        # Second trace report also has retry on foo.py
        trace_report = {
            "retries": {
                "retries": [
                    {"file": "foo.py", "tool": "Edit", "count": 5, "severity": "major", "error_confirmed": True}
                ],
                "total_retries": 1,
            },
            "waste": {"wasted_reads": [], "total_reads": 5, "waste_rate": 0.0},
            "efficiency": {"ratio": 0.3, "rating": "good", "unique_files": 10, "total_calls": 30},
            "velocity": {"commits": 2, "file_creates": 1, "deliverables": 3, "total_calls": 30, "velocity_pct": 10.0},
            "score": 70,
        }
        proposals = imp.generate_from_trace(trace_report, session_id=29)
        retry_on_foo = [p for p in proposals if p.pattern_type == "retry_loop" and p.pattern_data.get("file") == "foo.py"]
        self.assertEqual(len(retry_on_foo), 0)  # Already proposed

    def test_superseded_proposal_allows_new(self):
        """If an existing proposal is superseded, a new one for same pattern is allowed."""
        imp = improver.Improver(store_path=self.store_path)
        p1 = improver.ImprovementProposal(
            pattern_type="retry_loop", pattern_data={"file": "foo.py"},
            source="trace_analysis", proposed_fix="fix v1",
            expected_improvement="better", test_plan="check",
            risk_level="LOW", target_module="self-learning",
        )
        p1.status = "superseded"
        imp.store.append(p1)

        trace_report = {
            "retries": {
                "retries": [
                    {"file": "foo.py", "tool": "Edit", "count": 5, "severity": "major", "error_confirmed": True}
                ],
                "total_retries": 1,
            },
            "waste": {"wasted_reads": [], "total_reads": 5, "waste_rate": 0.0},
            "efficiency": {"ratio": 0.3, "rating": "good", "unique_files": 10, "total_calls": 30},
            "velocity": {"commits": 2, "file_creates": 1, "deliverables": 3, "total_calls": 30, "velocity_pct": 10.0},
            "score": 70,
        }
        proposals = imp.generate_from_trace(trace_report, session_id=29)
        retry_on_foo = [p for p in proposals if p.pattern_type == "retry_loop" and p.pattern_data.get("file") == "foo.py"]
        self.assertGreaterEqual(len(retry_on_foo), 1)


class TestRiskClassification(unittest.TestCase):
    """Test risk level classification logic."""

    def test_new_utility_file_is_low(self):
        level = improver.classify_risk(target_file=None, target_module="self-learning", modifies_hook=False)
        self.assertEqual(level, "LOW")

    def test_new_hook_is_medium(self):
        level = improver.classify_risk(target_file=None, target_module="agent-guard", modifies_hook=True)
        self.assertEqual(level, "MEDIUM")

    def test_modify_existing_hook_is_high(self):
        level = improver.classify_risk(
            target_file="context-monitor/hooks/meter.py",
            target_module="context-monitor",
            modifies_hook=True,
        )
        self.assertEqual(level, "HIGH")

    def test_modify_existing_non_hook_is_medium(self):
        level = improver.classify_risk(
            target_file="self-learning/journal.py",
            target_module="self-learning",
            modifies_hook=False,
        )
        self.assertEqual(level, "MEDIUM")

    def test_trading_always_high(self):
        level = improver.classify_risk(
            target_file=None, target_module="trading", modifies_hook=False,
        )
        self.assertEqual(level, "HIGH")


class TestSafetyGuards(unittest.TestCase):
    """Test safety constraints on the improvement system."""

    def test_never_propose_credential_changes(self):
        """Proposals must never target credential files."""
        trace_report = {
            "retries": {
                "retries": [
                    {"file": ".env", "tool": "Read", "count": 3, "severity": "minor", "error_confirmed": False}
                ],
                "total_retries": 1,
            },
            "waste": {"wasted_reads": [], "total_reads": 5, "waste_rate": 0.0},
            "efficiency": {"ratio": 0.3, "rating": "good", "unique_files": 10, "total_calls": 30},
            "velocity": {"commits": 2, "file_creates": 1, "deliverables": 3, "total_calls": 30, "velocity_pct": 10.0},
            "score": 80,
        }
        proposals = improver.ProposalGenerator.from_trace_report(trace_report)
        for p in proposals:
            self.assertNotIn(".env", p.proposed_fix.lower())
            if p.pattern_data.get("file"):
                self.assertNotEqual(p.pattern_data["file"], ".env")

    def test_never_modify_claude_md(self):
        """Should never propose modifying CLAUDE.md files."""
        trace_report = {
            "retries": {
                "retries": [
                    {"file": "CLAUDE.md", "tool": "Edit", "count": 5, "severity": "major", "error_confirmed": True}
                ],
                "total_retries": 1,
            },
            "waste": {"wasted_reads": [], "total_reads": 5, "waste_rate": 0.0},
            "efficiency": {"ratio": 0.3, "rating": "good", "unique_files": 10, "total_calls": 30},
            "velocity": {"commits": 2, "file_creates": 1, "deliverables": 3, "total_calls": 30, "velocity_pct": 10.0},
            "score": 70,
        }
        proposals = improver.ProposalGenerator.from_trace_report(trace_report)
        for p in proposals:
            if p.target_file:
                self.assertNotIn("CLAUDE.md", p.target_file)


class TestQualityGate(unittest.TestCase):
    """Test geometric mean quality gate for MT-10 self-improvement loop.

    The geometric mean prevents Goodhart's Law gaming: you can't sacrifice
    one metric to boost another, because a zero in any dimension tanks the
    composite score. Inspired by Nash bargaining (1950) / sentrux pattern.
    """

    def test_geometric_mean_basic(self):
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"a": 0.8, "b": 0.8})
        self.assertAlmostEqual(result["geometric_mean"], 0.8, places=5)

    def test_geometric_mean_three_metrics(self):
        gate = improver.QualityGate(threshold=0.5)
        # (0.5 * 0.5 * 0.5)^(1/3) = 0.5
        result = gate.evaluate({"a": 0.5, "b": 0.5, "c": 0.5})
        self.assertAlmostEqual(result["geometric_mean"], 0.5, places=5)

    def test_all_ones_pass(self):
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"a": 1.0, "b": 1.0, "c": 1.0})
        self.assertTrue(result["passed"])
        self.assertAlmostEqual(result["geometric_mean"], 1.0, places=5)

    def test_one_zero_fails(self):
        """Core anti-gaming property: any zero metric tanks the entire score."""
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"a": 1.0, "b": 0.0, "c": 1.0})
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["geometric_mean"], 0.0, places=5)

    def test_anti_gaming_unbalanced(self):
        """High in one, low in another → geometric mean punishes imbalance."""
        gate = improver.QualityGate(threshold=0.5)
        # (0.99 * 0.01)^(1/2) ≈ 0.0995 — well below threshold
        result = gate.evaluate({"a": 0.99, "b": 0.01})
        self.assertFalse(result["passed"])
        self.assertLess(result["geometric_mean"], 0.2)

    def test_balanced_moderate_passes(self):
        """Balanced moderate scores pass where unbalanced extreme fails."""
        gate = improver.QualityGate(threshold=0.5)
        # (0.6 * 0.6)^(1/2) = 0.6 — passes
        result = gate.evaluate({"a": 0.6, "b": 0.6})
        self.assertTrue(result["passed"])

    def test_threshold_customizable(self):
        gate = improver.QualityGate(threshold=0.8)
        result = gate.evaluate({"a": 0.7, "b": 0.7})
        self.assertFalse(result["passed"])  # 0.7 < 0.8

    def test_minimum_two_metrics_required(self):
        """Quality gate needs at least 2 metrics to prevent single-metric gaming."""
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"a": 1.0})
        self.assertFalse(result["passed"])
        self.assertIn("error", result)

    def test_empty_metrics_rejected(self):
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({})
        self.assertFalse(result["passed"])
        self.assertIn("error", result)

    def test_negative_values_clamped_to_zero(self):
        """Negative metric values should be treated as 0."""
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"a": 0.8, "b": -0.5})
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["geometric_mean"], 0.0, places=5)

    def test_values_above_one_clamped(self):
        """Metric values > 1.0 should be clamped to 1.0."""
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"a": 1.5, "b": 0.8})
        # (1.0 * 0.8)^(1/2) ≈ 0.894
        self.assertAlmostEqual(result["geometric_mean"], (1.0 * 0.8) ** 0.5, places=5)

    def test_result_includes_per_metric_scores(self):
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"test_pass": 0.9, "retry_reduction": 0.7})
        self.assertIn("metrics", result)
        self.assertEqual(result["metrics"]["test_pass"], 0.9)
        self.assertEqual(result["metrics"]["retry_reduction"], 0.7)

    def test_result_includes_threshold(self):
        gate = improver.QualityGate(threshold=0.6)
        result = gate.evaluate({"a": 0.8, "b": 0.8})
        self.assertEqual(result["threshold"], 0.6)

    def test_exactly_at_threshold_passes(self):
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"a": 0.5, "b": 0.5})
        self.assertTrue(result["passed"])

    def test_just_below_threshold_fails(self):
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"a": 0.49, "b": 0.5})
        self.assertFalse(result["passed"])

    def test_four_metrics_geometric_mean(self):
        gate = improver.QualityGate(threshold=0.5)
        # (0.8 * 0.6 * 0.7 * 0.9)^(1/4) ≈ 0.7418
        expected = (0.8 * 0.6 * 0.7 * 0.9) ** 0.25
        result = gate.evaluate({"a": 0.8, "b": 0.6, "c": 0.7, "d": 0.9})
        self.assertAlmostEqual(result["geometric_mean"], expected, places=4)
        self.assertTrue(result["passed"])

    def test_weakest_metric_identified(self):
        """Result should identify the weakest metric for targeted improvement."""
        gate = improver.QualityGate(threshold=0.5)
        result = gate.evaluate({"test_pass": 0.9, "waste_reduction": 0.3, "efficiency": 0.8})
        self.assertEqual(result["weakest_metric"], "waste_reduction")

    def test_default_threshold(self):
        """Default threshold should be 0.5."""
        gate = improver.QualityGate()
        self.assertEqual(gate.threshold, 0.5)


class TestImproverQualityGateIntegration(unittest.TestCase):
    """Test QualityGate integration with Improver.record_outcome."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "improvements.jsonl")

    def test_record_outcome_with_quality_gate(self):
        """record_outcome can use quality gate for multi-metric evaluation."""
        imp = improver.Improver(store_path=self.store_path)
        p = improver.ImprovementProposal(
            pattern_type="retry_loop", pattern_data={"file": "x.py"},
            source="trace_analysis", proposed_fix="fix retries",
            expected_improvement="fewer retries", test_plan="check",
            risk_level="LOW", target_module="self-learning",
        )
        imp.store.append(p)
        gate = improver.QualityGate(threshold=0.5)
        metrics = {"test_pass": 0.9, "retry_reduction": 0.8, "efficiency": 0.7}
        result = gate.evaluate(metrics)
        imp.record_outcome(p.id, improved=result["passed"],
                          metric_before=None, metric_after=result["geometric_mean"])
        loaded = imp.store.load_all()
        self.assertEqual(loaded[0].status, "validated")

    def test_quality_gate_rejects_unbalanced_improvement(self):
        """Quality gate prevents accepting improvements that game one metric."""
        imp = improver.Improver(store_path=self.store_path)
        p = improver.ImprovementProposal(
            pattern_type="high_waste", pattern_data={},
            source="trace_analysis", proposed_fix="fix waste",
            expected_improvement="less waste", test_plan="check",
            risk_level="LOW", target_module="self-learning",
        )
        imp.store.append(p)
        gate = improver.QualityGate(threshold=0.5)
        # Waste improved massively but tests broke
        metrics = {"test_pass": 0.1, "waste_reduction": 0.99}
        result = gate.evaluate(metrics)
        imp.record_outcome(p.id, improved=result["passed"],
                          metric_before=None, metric_after=result["geometric_mean"])
        loaded = imp.store.load_all()
        self.assertEqual(loaded[0].status, "rejected")  # Gate caught the gaming


if __name__ == "__main__":
    unittest.main()
