#!/usr/bin/env python3
"""Tests for sentinel_bridge.py — MT-28 Phase 6."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sentinel_bridge import (
    SentinelBridge, BridgeCycleReport, MODULE_TO_DOMAIN,
)
from improver import ImprovementProposal
from principle_registry import _load_principles, _generate_id


def _make_proposal(pattern_type="retry_loop", status="proposed",
                   risk_level="LOW", target_module="self-learning",
                   outcome=None, pattern_data=None, proposed_fix="fix it",
                   source="trace_analysis"):
    p = ImprovementProposal(
        pattern_type=pattern_type,
        pattern_data=pattern_data or {"file": "test.py"},
        source=source,
        proposed_fix=proposed_fix,
        expected_improvement="improve",
        test_plan="test it",
        risk_level=risk_level,
        target_module=target_module,
    )
    p.status = status
    p.outcome = outcome
    return p


class TestModuleToDomain(unittest.TestCase):
    """Test module-to-domain mapping."""

    def test_known_modules(self):
        self.assertEqual(MODULE_TO_DOMAIN["self-learning"], "cca_operations")
        self.assertEqual(MODULE_TO_DOMAIN["context-monitor"], "session_management")
        self.assertEqual(MODULE_TO_DOMAIN["agent-guard"], "code_quality")
        self.assertEqual(MODULE_TO_DOMAIN["trading"], "trading_execution")

    def test_bridge_maps_unknown_to_general(self):
        bridge = SentinelBridge()
        p = _make_proposal(target_module="unknown-module")
        domain = bridge._proposal_to_domain(p)
        self.assertEqual(domain, "general")


class TestPrincipleCreation(unittest.TestCase):
    """Test creating principles from validated proposals."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.bridge = SentinelBridge(principles_path=self.principles_path)

    def tearDown(self):
        if os.path.exists(self.principles_path):
            os.unlink(self.principles_path)
        os.rmdir(self.tmpdir)

    def test_validated_creates_principle(self):
        p = _make_proposal(
            status="validated",
            proposed_fix="Always read before editing structured files",
            target_module="self-learning",
            outcome={"improved": True, "metric_before": 0.5, "metric_after": 0.2},
        )
        pid = self.bridge.create_principle_from_proposal(p, current_session=111)
        self.assertIsNotNone(pid)

        principles = _load_principles(self.principles_path)
        self.assertIn(pid, principles)
        self.assertEqual(principles[pid].success_count, 1)
        self.assertEqual(principles[pid].source_domain, "cca_operations")

    def test_proposed_skipped(self):
        p = _make_proposal(status="proposed")
        pid = self.bridge.create_principle_from_proposal(p)
        self.assertIsNone(pid)

    def test_rejected_skipped(self):
        p = _make_proposal(status="rejected")
        pid = self.bridge.create_principle_from_proposal(p)
        self.assertIsNone(pid)

    def test_duplicate_not_created(self):
        p = _make_proposal(
            status="validated",
            proposed_fix="Same fix twice",
            target_module="self-learning",
            outcome={"improved": True},
        )
        pid1 = self.bridge.create_principle_from_proposal(p, current_session=111)
        pid2 = self.bridge.create_principle_from_proposal(p, current_session=112)
        self.assertIsNotNone(pid1)
        self.assertIsNone(pid2)  # Already exists

    def test_empty_fix_skipped(self):
        p = _make_proposal(status="validated", proposed_fix="")
        pid = self.bridge.create_principle_from_proposal(p)
        self.assertIsNone(pid)

    def test_committed_creates_principle(self):
        p = _make_proposal(
            status="committed",
            proposed_fix="Use atomic writes for state files",
            outcome={"improved": True},
        )
        pid = self.bridge.create_principle_from_proposal(p, current_session=111)
        self.assertIsNotNone(pid)

    def test_long_fix_truncated(self):
        long_fix = "A" * 300
        p = _make_proposal(status="validated", proposed_fix=long_fix,
                           outcome={"improved": True})
        pid = self.bridge.create_principle_from_proposal(p, current_session=111)
        self.assertIsNotNone(pid)
        principles = _load_principles(self.principles_path)
        self.assertLessEqual(len(principles[pid].text), 200)


class TestPrincipleScoring(unittest.TestCase):
    """Test scoring existing principles from outcomes."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.bridge = SentinelBridge(principles_path=self.principles_path)

    def tearDown(self):
        if os.path.exists(self.principles_path):
            os.unlink(self.principles_path)
        os.rmdir(self.tmpdir)

    def test_score_success(self):
        # First create the principle
        p1 = _make_proposal(
            status="validated",
            proposed_fix="Check before writing",
            outcome={"improved": True},
        )
        pid = self.bridge.create_principle_from_proposal(p1, current_session=110)

        # Score it with another success
        p2 = _make_proposal(
            status="validated",
            proposed_fix="Check before writing",
            outcome={"improved": True},
        )
        scored = self.bridge.score_principle_from_outcome(p2, current_session=111)
        self.assertEqual(scored, pid)

        principles = _load_principles(self.principles_path)
        self.assertEqual(principles[pid].success_count, 2)
        self.assertEqual(principles[pid].usage_count, 2)

    def test_score_failure(self):
        p1 = _make_proposal(
            status="validated",
            proposed_fix="Try this approach",
            outcome={"improved": True},
        )
        pid = self.bridge.create_principle_from_proposal(p1, current_session=110)

        p2 = _make_proposal(
            status="validated",
            proposed_fix="Try this approach",
            outcome={"improved": False},
        )
        self.bridge.score_principle_from_outcome(p2, current_session=111)

        principles = _load_principles(self.principles_path)
        # success_count should stay at 1 (only the creation), usage goes up
        self.assertEqual(principles[pid].success_count, 1)
        self.assertEqual(principles[pid].usage_count, 2)

    def test_score_nonexistent_returns_none(self):
        p = _make_proposal(proposed_fix="No matching principle")
        result = self.bridge.score_principle_from_outcome(p)
        self.assertIsNone(result)


class TestCounterPrinciples(unittest.TestCase):
    """Test counter-principle creation from rejected proposals."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.bridge = SentinelBridge(principles_path=self.principles_path)

    def tearDown(self):
        if os.path.exists(self.principles_path):
            os.unlink(self.principles_path)
        os.rmdir(self.tmpdir)

    def test_rejected_creates_counter(self):
        p = _make_proposal(
            status="rejected",
            proposed_fix="Rush shipping without tests",
            outcome={"improved": False},
        )
        cpid = self.bridge.create_counter_principle(p, current_session=111)
        self.assertIsNotNone(cpid)

        principles = _load_principles(self.principles_path)
        self.assertIn(cpid, principles)
        self.assertTrue(principles[cpid].text.startswith("Avoid:"))

    def test_non_rejected_skipped(self):
        p = _make_proposal(status="proposed")
        cpid = self.bridge.create_counter_principle(p)
        self.assertIsNone(cpid)

    def test_duplicate_counter_scores_existing(self):
        p = _make_proposal(
            status="rejected",
            proposed_fix="Bad approach",
            outcome={"improved": False},
        )
        cpid1 = self.bridge.create_counter_principle(p, current_session=110)
        cpid2 = self.bridge.create_counter_principle(p, current_session=111)
        self.assertEqual(cpid1, cpid2)

        principles = _load_principles(self.principles_path)
        # Second call should increment counts
        self.assertEqual(principles[cpid1].success_count, 2)
        self.assertEqual(principles[cpid1].usage_count, 2)

    def test_empty_fix_skipped(self):
        p = _make_proposal(status="rejected", proposed_fix="")
        cpid = self.bridge.create_counter_principle(p)
        self.assertIsNone(cpid)


class TestProcessCycle(unittest.TestCase):
    """Test full cycle processing."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.bridge = SentinelBridge(principles_path=self.principles_path)

    def tearDown(self):
        if os.path.exists(self.principles_path):
            os.unlink(self.principles_path)
        os.rmdir(self.tmpdir)

    def test_empty_proposals(self):
        report = self.bridge.process_cycle([], current_session=111)
        self.assertEqual(report.principles_created, 0)
        self.assertEqual(report.principles_scored, 0)
        self.assertEqual(report.counter_principles, 0)

    def test_mixed_proposals(self):
        proposals = [
            _make_proposal(
                status="validated",
                proposed_fix="Always run tests first",
                target_module="self-learning",
                outcome={"improved": True},
            ),
            _make_proposal(
                status="rejected",
                proposed_fix="Skip validation",
                target_module="agent-guard",
                outcome={"improved": False},
                pattern_data={"file": "test.py"},
            ),
        ]
        report = self.bridge.process_cycle(proposals, current_session=111)
        self.assertGreater(report.principles_created, 0)
        self.assertGreater(report.counter_principles, 0)

    def test_cycle_report_is_correct_type(self):
        report = self.bridge.process_cycle([], current_session=111)
        self.assertIsInstance(report, BridgeCycleReport)

    def test_cycle_handles_errors_gracefully(self):
        # A proposal with None pattern_data might cause issues
        p = _make_proposal(status="validated", proposed_fix="test")
        p.pattern_data = None
        report = self.bridge.process_cycle([p], current_session=111)
        # Should not crash — errors captured in report
        self.assertIsInstance(report, BridgeCycleReport)

    def test_cross_pollination_in_cycle(self):
        proposals = [
            _make_proposal(
                status="validated",
                proposed_fix="Track file references to avoid reads",
                target_module="reddit-intelligence",
                outcome={"improved": True, "metric_before": 0.4, "metric_after": 0.15},
            ),
        ]
        report = self.bridge.process_cycle(proposals, current_session=111)
        # Cross-pollination may or may not generate transfers depending on sentinel
        # At minimum, a principle should be created
        self.assertGreaterEqual(report.principles_created, 1)


class TestBridgeCycleReport(unittest.TestCase):
    """Test report data class."""

    def test_to_dict(self):
        report = BridgeCycleReport(
            principles_created=3,
            principles_scored=2,
            counter_principles=1,
            transfers_suggested=1,
        )
        d = report.to_dict()
        self.assertEqual(d["principles_created"], 3)
        self.assertEqual(d["counter_principles"], 1)

    def test_summary_output(self):
        report = BridgeCycleReport(principles_created=2, errors=["test error"])
        summary = report.summary()
        self.assertIn("Principles created: 2", summary)
        self.assertIn("Errors: 1", summary)
        self.assertIn("test error", summary)

    def test_empty_report(self):
        report = BridgeCycleReport()
        summary = report.summary()
        self.assertIn("Principles created: 0", summary)


class TestGetStats(unittest.TestCase):
    """Test bridge statistics."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.bridge = SentinelBridge(principles_path=self.principles_path)

    def tearDown(self):
        if os.path.exists(self.principles_path):
            os.unlink(self.principles_path)
        os.rmdir(self.tmpdir)

    def test_stats_empty(self):
        stats = self.bridge.get_stats()
        self.assertEqual(stats["total_principles"], 0)
        self.assertEqual(stats["counter_principles"], 0)

    def test_stats_after_cycle(self):
        proposals = [
            _make_proposal(
                status="validated",
                proposed_fix="Good approach",
                outcome={"improved": True},
            ),
            _make_proposal(
                status="rejected",
                proposed_fix="Bad approach",
                outcome={"improved": False},
                pattern_data={"file": "x.py"},
            ),
        ]
        self.bridge.process_cycle(proposals, current_session=111)
        stats = self.bridge.get_stats()
        self.assertGreater(stats["total_principles"], 0)
        self.assertGreater(stats["counter_principles"], 0)
        self.assertGreater(stats["sentinel_sourced"], 0)


class TestExtractPrincipleText(unittest.TestCase):
    """Test text extraction from proposals."""

    def setUp(self):
        self.bridge = SentinelBridge()

    def test_plain_text(self):
        p = _make_proposal(proposed_fix="Simple fix")
        text = self.bridge._extract_principle_text(p)
        self.assertEqual(text, "Simple fix")

    def test_cross_pollinated_prefix_stripped(self):
        p = _make_proposal(proposed_fix="[Cross-pollinated from trading] Use caching")
        text = self.bridge._extract_principle_text(p)
        self.assertEqual(text, "Use caching")

    def test_counter_prefix_stripped(self):
        p = _make_proposal(proposed_fix="[COUNTER] Skip tests")
        text = self.bridge._extract_principle_text(p)
        self.assertEqual(text, "Skip tests")

    def test_truncation(self):
        long_text = "X" * 300
        p = _make_proposal(proposed_fix=long_text)
        text = self.bridge._extract_principle_text(p)
        self.assertLessEqual(len(text), 200)
        self.assertTrue(text.endswith("..."))


if __name__ == "__main__":
    unittest.main()
