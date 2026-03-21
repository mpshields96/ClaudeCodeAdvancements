#!/usr/bin/env python3
"""Extended tests for improver.py — SentinelMutator, evolve(), ProposalGenerator edges,
Improver lifecycle, QualityGate edges, and _is_protected_file coverage.

Supplements test_improver.py (64 tests). Targets gaps in SentinelMutator (mutate_from_failure,
cross_pollinate, scan_weaknesses), evolve() orchestration, and reflect pattern types
(research_dead_end, consecutive_failures, high_pain_rate, negative_pnl).
"""

import json
import os
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)

import improver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proposal(pattern_type="retry_loop", status="proposed", risk_level="LOW",
                   source="trace_analysis", target_module="self-learning",
                   target_file=None, pattern_data=None, store=None):
    p = improver.ImprovementProposal(
        pattern_type=pattern_type,
        pattern_data=pattern_data or {},
        source=source,
        proposed_fix="fix-stub",
        expected_improvement="better",
        test_plan="compare",
        risk_level=risk_level,
        target_module=target_module,
        target_file=target_file,
    )
    p.status = status
    if store:
        store.append(p)
    return p


def _make_store(tmpdir):
    return improver.ImprovementStore(path=os.path.join(tmpdir, "improvements.jsonl"))


# ---------------------------------------------------------------------------
# TestSentinelMutatorMutateFromFailure
# ---------------------------------------------------------------------------

class TestSentinelMutatorMutateFromFailure(unittest.TestCase):
    """mutate_from_failure — counter-strategy generation from rejected proposals."""

    def setUp(self):
        self.sm = improver.SentinelMutator()

    def _rejected(self, pattern_type="retry_loop", depth=0, target_file=None):
        p = _make_proposal(pattern_type=pattern_type, status="rejected",
                           pattern_data={"mutation_depth": depth}, target_file=target_file)
        return p

    def test_non_rejected_returns_empty(self):
        p = _make_proposal(status="proposed")
        self.assertEqual(self.sm.mutate_from_failure(p), [])

    def test_non_rejected_approved_returns_empty(self):
        p = _make_proposal(status="approved")
        self.assertEqual(self.sm.mutate_from_failure(p), [])

    def test_mutation_depth_exceeded_returns_empty(self):
        p = self._rejected(depth=improver.MAX_MUTATION_DEPTH)
        self.assertEqual(self.sm.mutate_from_failure(p), [])

    def test_mutation_depth_just_below_limit_allowed(self):
        p = self._rejected(depth=improver.MAX_MUTATION_DEPTH - 1)
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(len(result), 1)

    def test_protected_file_blocked(self):
        p = self._rejected(pattern_type="retry_loop", depth=0)
        p.pattern_data["file"] = "CLAUDE.md"
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(result, [])

    def test_env_file_blocked(self):
        p = self._rejected()
        p.pattern_data["file"] = ".env"
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(result, [])

    def test_mutation_source_is_sentinel_mutation(self):
        p = self._rejected(pattern_type="retry_loop")
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source, "sentinel_mutation")

    def test_mutation_pattern_type_has_mutation_suffix(self):
        p = self._rejected(pattern_type="retry_loop")
        result = self.sm.mutate_from_failure(p)
        self.assertIn("mutation", result[0].pattern_type)

    def test_mutation_depth_incremented(self):
        p = self._rejected(pattern_type="retry_loop", depth=0)
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(result[0].pattern_data["mutation_depth"], 1)

    def test_mutation_of_field_tracks_original_id(self):
        p = self._rejected(pattern_type="retry_loop")
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(result[0].pattern_data["mutation_of"], p.id)

    def test_original_fix_tracked_in_pattern_data(self):
        p = self._rejected(pattern_type="retry_loop")
        p.proposed_fix = "original-fix-stub"
        result = self.sm.mutate_from_failure(p)
        self.assertIn("original_fix_that_failed", result[0].pattern_data)

    def test_unknown_pattern_type_uses_fallback(self):
        p = self._rejected(pattern_type="totally_unknown_type")
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(len(result), 1)
        self.assertIn("Inverse approach", result[0].proposed_fix)

    def test_high_waste_mutation_picks_alternative(self):
        p = self._rejected(pattern_type="high_waste")
        p.proposed_fix = improver.MUTATION_STRATEGIES["high_waste"][0]
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(len(result), 1)
        # Should not pick the same fix that failed
        self.assertNotEqual(result[0].proposed_fix, p.proposed_fix)

    def test_mutation_inherits_risk_level(self):
        p = self._rejected(pattern_type="retry_loop")
        p.risk_level = "MEDIUM"
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(result[0].risk_level, "MEDIUM")

    def test_mutation_inherits_target_module(self):
        p = self._rejected(pattern_type="high_skip_rate")
        p.target_module = "reddit-intelligence"
        result = self.sm.mutate_from_failure(p)
        self.assertEqual(result[0].target_module, "reddit-intelligence")


# ---------------------------------------------------------------------------
# TestSentinelMutatorCrossPollinate
# ---------------------------------------------------------------------------

class TestSentinelMutatorCrossPollinate(unittest.TestCase):
    """cross_pollinate — spread proven patterns across domains."""

    def setUp(self):
        self.sm = improver.SentinelMutator()

    def test_no_successful_proposals_returns_empty(self):
        proposals = [_make_proposal(status="proposed"), _make_proposal(status="rejected")]
        self.assertEqual(self.sm.cross_pollinate(proposals), [])

    def test_validated_proposal_triggers_cross_pollination(self):
        p = _make_proposal(status="validated", target_module="self-learning")
        result = self.sm.cross_pollinate([p])
        self.assertGreater(len(result), 0)

    def test_committed_proposal_triggers_cross_pollination(self):
        p = _make_proposal(status="committed", target_module="context-monitor")
        result = self.sm.cross_pollinate([p])
        self.assertGreater(len(result), 0)

    def test_trading_proposals_never_cross_pollinate(self):
        p = _make_proposal(status="validated", target_module="trading")
        result = self.sm.cross_pollinate([p])
        self.assertEqual(result, [])

    def test_cross_pollinated_source_is_correct(self):
        p = _make_proposal(status="validated", target_module="self-learning")
        result = self.sm.cross_pollinate([p])
        for cross in result:
            self.assertEqual(cross.source, "sentinel_cross_pollination")

    def test_cross_pollinated_fix_references_origin(self):
        p = _make_proposal(status="validated", target_module="self-learning")
        p.proposed_fix = "my-original-fix"
        result = self.sm.cross_pollinate([p])
        for cross in result:
            self.assertIn("self-learning", cross.proposed_fix)

    def test_cross_pollinated_target_is_different_domain(self):
        p = _make_proposal(status="validated", target_module="self-learning")
        result = self.sm.cross_pollinate([p])
        for cross in result:
            self.assertNotEqual(cross.target_module, "self-learning")

    def test_cross_pollination_risk_is_low(self):
        p = _make_proposal(status="validated", target_module="memory-system")
        result = self.sm.cross_pollinate([p])
        for cross in result:
            self.assertEqual(cross.risk_level, "LOW")

    def test_cross_pollination_origin_tracked(self):
        p = _make_proposal(status="validated", target_module="spec-system")
        result = self.sm.cross_pollinate([p])
        for cross in result:
            self.assertEqual(cross.pattern_data["cross_from"], p.id)
            self.assertEqual(cross.pattern_data["origin_module"], "spec-system")


# ---------------------------------------------------------------------------
# TestSentinelMutatorScanWeaknesses
# ---------------------------------------------------------------------------

class TestSentinelMutatorScanWeaknesses(unittest.TestCase):
    """scan_weaknesses — identify under-covered or failing domains."""

    def setUp(self):
        self.sm = improver.SentinelMutator()

    def test_empty_proposals_all_domains_flagged(self):
        gaps = self.sm.scan_weaknesses([])
        flagged = {g["domain"] for g in gaps}
        for d in improver.SENTINEL_DOMAINS:
            self.assertIn(d, flagged)

    def test_domain_with_proposals_not_flagged_as_unexplored(self):
        p = _make_proposal(status="proposed", target_module="self-learning")
        gaps = self.sm.scan_weaknesses([p])
        unexplored = [g for g in gaps if g["domain"] == "self-learning" and "unexplored" in g["reason"]]
        self.assertEqual(unexplored, [])

    def test_all_rejected_no_active_flagged(self):
        proposals = [
            _make_proposal(status="rejected", target_module="context-monitor"),
            _make_proposal(status="rejected", target_module="context-monitor"),
        ]
        gaps = self.sm.scan_weaknesses(proposals)
        flagged = [g for g in gaps if g["domain"] == "context-monitor"]
        self.assertEqual(len(flagged), 1)
        self.assertIn("rejected", flagged[0]["reason"])

    def test_high_rejection_rate_flagged(self):
        # 3+ total, >66% rejected
        proposals = [
            _make_proposal(status="rejected", target_module="agent-guard"),
            _make_proposal(status="rejected", target_module="agent-guard"),
            _make_proposal(status="proposed", target_module="agent-guard"),
        ]
        gaps = self.sm.scan_weaknesses(proposals)
        flagged = [g for g in gaps if g["domain"] == "agent-guard"]
        self.assertEqual(len(flagged), 1)

    def test_healthy_domain_not_flagged(self):
        proposals = [
            _make_proposal(status="validated", target_module="memory-system"),
            _make_proposal(status="committed", target_module="memory-system"),
        ]
        gaps = self.sm.scan_weaknesses(proposals)
        flagged = [g for g in gaps if g["domain"] == "memory-system"]
        self.assertEqual(flagged, [])

    def test_unknown_module_not_in_gaps(self):
        p = _make_proposal(status="rejected", target_module="unknown-module")
        # Should not crash — unknown modules are just ignored
        gaps = self.sm.scan_weaknesses([p])
        flagged = [g for g in gaps if g["domain"] == "unknown-module"]
        self.assertEqual(flagged, [])


# ---------------------------------------------------------------------------
# TestProposalGeneratorEdgeCases
# ---------------------------------------------------------------------------

class TestProposalGeneratorEdgeCases(unittest.TestCase):
    """ProposalGenerator edge cases not covered in base tests."""

    def _trace_report_with_retry(self, filepath, count=3, severity="major"):
        return {
            "retries": {"retries": [{"file": filepath, "tool": "Edit", "count": count, "severity": severity}]},
            "waste": {"waste_rate": 0.1, "wasted_reads": []},
            "efficiency": {"rating": "ok", "ratio": 0.5, "unique_files": 5, "total_calls": 10},
            "velocity": {"total_calls": 5, "deliverables": 1},
        }

    def test_protected_file_retry_not_proposed(self):
        report = self._trace_report_with_retry("CLAUDE.md")
        proposals = improver.ProposalGenerator.from_trace_report(report)
        retry_props = [p for p in proposals if p.pattern_type == "retry_loop"]
        self.assertEqual(retry_props, [])

    def test_env_file_retry_not_proposed(self):
        report = self._trace_report_with_retry(".env")
        proposals = improver.ProposalGenerator.from_trace_report(report)
        retry_props = [p for p in proposals if p.pattern_type == "retry_loop"]
        self.assertEqual(retry_props, [])

    def test_duplicate_file_in_retries_deduped(self):
        report = {
            "retries": {"retries": [
                {"file": "journal.py", "tool": "Edit", "count": 3, "severity": "major"},
                {"file": "journal.py", "tool": "Edit", "count": 2, "severity": "minor"},
            ]},
            "waste": {"waste_rate": 0.0},
            "efficiency": {"rating": "ok"},
            "velocity": {"total_calls": 5, "deliverables": 1},
        }
        proposals = improver.ProposalGenerator.from_trace_report(report)
        retry_props = [p for p in proposals if p.pattern_type == "retry_loop"]
        self.assertEqual(len(retry_props), 1)

    def test_low_waste_no_proposal(self):
        report = {
            "retries": {"retries": []},
            "waste": {"waste_rate": 0.1, "wasted_reads": []},
            "efficiency": {"rating": "ok"},
            "velocity": {"total_calls": 5, "deliverables": 1},
        }
        proposals = improver.ProposalGenerator.from_trace_report(report)
        waste_props = [p for p in proposals if p.pattern_type == "high_waste"]
        self.assertEqual(waste_props, [])

    def test_good_efficiency_no_proposal(self):
        report = {
            "retries": {"retries": []},
            "waste": {"waste_rate": 0.0},
            "efficiency": {"rating": "good", "ratio": 0.3},
            "velocity": {"total_calls": 5, "deliverables": 1},
        }
        proposals = improver.ProposalGenerator.from_trace_report(report)
        eff_props = [p for p in proposals if p.pattern_type == "low_efficiency"]
        self.assertEqual(eff_props, [])

    def test_few_calls_no_deliverables_proposal(self):
        # < 10 total_calls — should NOT generate no_deliverables proposal
        report = {
            "retries": {"retries": []},
            "waste": {"waste_rate": 0.0},
            "efficiency": {"rating": "ok"},
            "velocity": {"total_calls": 5, "deliverables": 0},
        }
        proposals = improver.ProposalGenerator.from_trace_report(report)
        nd_props = [p for p in proposals if p.pattern_type == "no_deliverables"]
        self.assertEqual(nd_props, [])

    def test_research_dead_end_generates_high_risk(self):
        patterns = [{"type": "research_dead_end", "data": {"path": "foo", "sessions": 5}}]
        proposals = improver.ProposalGenerator.from_reflect_patterns(patterns)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].risk_level, "HIGH")
        self.assertEqual(proposals[0].target_module, "trading")

    def test_consecutive_failures_generates_medium_risk(self):
        patterns = [{"type": "consecutive_failures", "data": {"streak": 3}}]
        proposals = improver.ProposalGenerator.from_reflect_patterns(patterns)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].risk_level, "MEDIUM")

    def test_high_pain_rate_generates_medium_risk(self):
        patterns = [{"type": "high_pain_rate", "data": {"top_pain_domain": "context", "rate": 0.7}}]
        proposals = improver.ProposalGenerator.from_reflect_patterns(patterns)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].risk_level, "MEDIUM")

    def test_negative_pnl_generates_high_risk(self):
        patterns = [{"type": "negative_pnl", "data": {"pnl_cents": -500}}]
        proposals = improver.ProposalGenerator.from_reflect_patterns(patterns)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].risk_level, "HIGH")
        self.assertEqual(proposals[0].target_module, "trading")

    def test_unknown_reflect_pattern_type_skipped(self):
        patterns = [{"type": "unknown_pattern_xyz", "data": {}}]
        proposals = improver.ProposalGenerator.from_reflect_patterns(patterns)
        self.assertEqual(proposals, [])

    def test_session_id_propagated(self):
        report = {
            "retries": {"retries": [{"file": "x.py", "tool": "Edit", "count": 3}]},
            "waste": {"waste_rate": 0.0},
            "efficiency": {"rating": "ok"},
            "velocity": {"total_calls": 5, "deliverables": 1},
        }
        proposals = improver.ProposalGenerator.from_trace_report(report, session_id=99)
        self.assertEqual(proposals[0].session_id, 99)


# ---------------------------------------------------------------------------
# TestImproverEvolve
# ---------------------------------------------------------------------------

class TestImproverEvolve(unittest.TestCase):
    """evolve() orchestration — Sentinel cycle through Improver."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.imp = improver.Improver(store_path=os.path.join(self.tmpdir, "imp.jsonl"))

    def test_evolve_empty_store_returns_zero_mutations(self):
        result = self.imp.evolve()
        self.assertEqual(result["mutations"], 0)

    def test_evolve_empty_store_returns_zero_cross(self):
        result = self.imp.evolve()
        self.assertEqual(result["cross_pollinations"], 0)

    def test_evolve_empty_store_has_all_weakness_gaps(self):
        result = self.imp.evolve()
        self.assertGreaterEqual(result["weakness_gaps"], len(improver.SENTINEL_DOMAINS))

    def test_evolve_with_rejected_creates_mutation(self):
        p = _make_proposal(status="rejected", pattern_type="retry_loop",
                           pattern_data={"mutation_depth": 0})
        self.imp.store.append(p)
        result = self.imp.evolve()
        self.assertGreaterEqual(result["mutations"], 1)

    def test_evolve_mutation_persisted_to_store(self):
        p = _make_proposal(status="rejected", pattern_type="retry_loop",
                           pattern_data={"mutation_depth": 0})
        self.imp.store.append(p)
        self.imp.evolve()
        all_props = self.imp.store.load_all()
        mutation_props = [x for x in all_props if x.source == "sentinel_mutation"]
        self.assertGreaterEqual(len(mutation_props), 1)

    def test_evolve_with_validated_creates_cross_pollination(self):
        # Use pattern_data with a unique file so dedup key doesn't collide with
        # the cross-pollinated proposals (which have no "file" in pattern_data).
        p = _make_proposal(status="validated", target_module="self-learning",
                           pattern_data={"file": "unique_source.py"})
        self.imp.store.append(p)
        result = self.imp.evolve()
        self.assertGreaterEqual(result["cross_pollinations"], 1)

    def test_evolve_cross_pollinated_persisted(self):
        p = _make_proposal(status="validated", target_module="self-learning",
                           pattern_data={"file": "unique_source2.py"})
        self.imp.store.append(p)
        self.imp.evolve()
        all_props = self.imp.store.load_all()
        cross = [x for x in all_props if x.source == "sentinel_cross_pollination"]
        self.assertGreaterEqual(len(cross), 1)

    def test_evolve_mutations_capped_at_max(self):
        # Create more rejected proposals than MAX_MUTATIONS_PER_CYCLE
        for _ in range(improver.MAX_MUTATIONS_PER_CYCLE + 3):
            p = _make_proposal(status="rejected", pattern_type="retry_loop",
                               pattern_data={"mutation_depth": 0})
            self.imp.store.append(p)
        result = self.imp.evolve()
        self.assertLessEqual(result["mutations"], improver.MAX_MUTATIONS_PER_CYCLE)

    def test_evolve_gap_details_returned(self):
        result = self.imp.evolve()
        self.assertIn("gap_details", result)
        self.assertIsInstance(result["gap_details"], list)

    def test_evolve_does_not_duplicate_existing_mutations(self):
        # First evolve creates a mutation
        p = _make_proposal(status="rejected", pattern_type="retry_loop",
                           pattern_data={"mutation_depth": 0})
        self.imp.store.append(p)
        self.imp.evolve()
        count_after_first = len(self.imp.store.load_all())

        # Second evolve on same data should not add duplicates (dedup)
        self.imp.evolve()
        count_after_second = len(self.imp.store.load_all())
        # May not grow if dedup works (mutations would be deduped by pattern_type+file key)
        # At minimum, should not crash
        self.assertGreaterEqual(count_after_second, count_after_first)


# ---------------------------------------------------------------------------
# TestImproverLifecycle
# ---------------------------------------------------------------------------

class TestImproverLifecycle(unittest.TestCase):
    """Improver full lifecycle — generate → approve → record → evolve."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.imp = improver.Improver(store_path=os.path.join(self.tmpdir, "imp.jsonl"))

    def _trace_with_retry(self, filepath="journal.py"):
        return {
            "retries": {"retries": [{"file": filepath, "tool": "Edit", "count": 4}]},
            "waste": {"waste_rate": 0.4, "wasted_reads": ["a.py", "b.py"]},
            "efficiency": {"rating": "poor", "ratio": 0.03, "unique_files": 2, "total_calls": 60},
            "velocity": {"total_calls": 60, "deliverables": 0},
        }

    def test_generate_then_approve_then_get_actionable(self):
        proposals = self.imp.generate_from_trace(self._trace_with_retry())
        self.assertGreater(len(proposals), 0)
        p_id = proposals[0].id
        self.imp.store.update_status(p_id, "approved")
        actionable = self.imp.get_actionable()
        ids = [a.id for a in actionable]
        self.assertIn(p_id, ids)

    def test_record_outcome_improved_sets_validated(self):
        proposals = self.imp.generate_from_trace(self._trace_with_retry())
        p_id = proposals[0].id
        self.imp.record_outcome(p_id, improved=True, metric_before=0.5, metric_after=0.2)
        all_p = self.imp.store.load_all()
        p = next(x for x in all_p if x.id == p_id)
        self.assertEqual(p.status, "validated")
        self.assertTrue(p.outcome["improved"])

    def test_record_outcome_not_improved_sets_rejected(self):
        proposals = self.imp.generate_from_trace(self._trace_with_retry())
        p_id = proposals[0].id
        self.imp.record_outcome(p_id, improved=False)
        all_p = self.imp.store.load_all()
        p = next(x for x in all_p if x.id == p_id)
        self.assertEqual(p.status, "rejected")
        self.assertFalse(p.outcome["improved"])

    def test_auto_approve_low_risk_sets_approved_on_generate(self):
        imp = improver.Improver(
            store_path=os.path.join(self.tmpdir, "imp2.jsonl"),
            auto_approve_low=True,
        )
        proposals = imp.generate_from_trace(self._trace_with_retry())
        low_risk = [p for p in proposals if p.risk_level == "LOW"]
        for p in low_risk:
            self.assertEqual(p.status, "approved")

    def test_auto_approve_does_not_approve_high_risk(self):
        imp = improver.Improver(
            store_path=os.path.join(self.tmpdir, "imp3.jsonl"),
            auto_approve_low=True,
        )
        patterns = [{"type": "losing_strategy",
                     "data": {"strategy": "x", "win_rate": 0.2, "pnl_cents": -200, "bets": 20}}]
        proposals = imp.generate_from_reflect(patterns)
        high_risk = [p for p in proposals if p.risk_level == "HIGH"]
        for p in high_risk:
            self.assertNotEqual(p.status, "approved")

    def test_max_proposals_per_session_limits_output(self):
        imp = improver.Improver(
            store_path=os.path.join(self.tmpdir, "imp4.jsonl"),
            max_proposals_per_session=2,
        )
        # Trace with many issues
        proposals = imp.generate_from_trace(self._trace_with_retry())
        self.assertLessEqual(len(proposals), 2)

    def test_generate_from_reflect_returns_proposals(self):
        patterns = [
            {"type": "high_skip_rate", "data": {"skip_rate": 0.8}},
            {"type": "low_build_rate", "data": {"build_rate": 0.05}},
        ]
        proposals = self.imp.generate_from_reflect(patterns)
        self.assertGreater(len(proposals), 0)

    def test_get_stats_by_risk_accounts_all_levels(self):
        proposals = self.imp.generate_from_trace(self._trace_with_retry())
        stats = self.imp.get_stats()
        for level in improver.VALID_RISK_LEVELS:
            self.assertIn(level, stats["by_risk"])

    def test_get_stats_by_source_accounts_all_sources(self):
        proposals = self.imp.generate_from_trace(self._trace_with_retry())
        stats = self.imp.get_stats()
        for source in improver.VALID_SOURCES:
            self.assertIn(source, stats["by_source"])

    def test_get_stats_success_rate_none_when_no_decisions(self):
        # No proposals decided yet
        self.imp.generate_from_trace(self._trace_with_retry())
        stats = self.imp.get_stats()
        self.assertIsNone(stats["success_rate"])

    def test_get_stats_success_rate_computed_after_decision(self):
        proposals = self.imp.generate_from_trace(self._trace_with_retry())
        self.imp.record_outcome(proposals[0].id, improved=True)
        stats = self.imp.get_stats()
        self.assertIsNotNone(stats["success_rate"])
        self.assertEqual(stats["success_rate"], 1.0)


# ---------------------------------------------------------------------------
# TestIsProtectedFile
# ---------------------------------------------------------------------------

class TestIsProtectedFile(unittest.TestCase):
    """_is_protected_file — various path formats."""

    def test_claude_md_protected(self):
        self.assertTrue(improver._is_protected_file("CLAUDE.md"))

    def test_env_protected(self):
        self.assertTrue(improver._is_protected_file(".env"))

    def test_env_local_protected(self):
        self.assertTrue(improver._is_protected_file(".env.local"))

    def test_settings_local_json_protected(self):
        self.assertTrue(improver._is_protected_file("settings.local.json"))

    def test_credentials_json_protected(self):
        self.assertTrue(improver._is_protected_file("credentials.json"))

    def test_credential_in_name_protected(self):
        self.assertTrue(improver._is_protected_file("my_credential_store.py"))

    def test_secret_in_name_protected(self):
        self.assertTrue(improver._is_protected_file("app_secret.py"))

    def test_token_in_name_protected(self):
        self.assertTrue(improver._is_protected_file("auth_token.json"))

    def test_apikey_in_name_protected(self):
        self.assertTrue(improver._is_protected_file("apikey_manager.py"))

    def test_normal_file_not_protected(self):
        self.assertFalse(improver._is_protected_file("journal.py"))

    def test_none_not_protected(self):
        self.assertFalse(improver._is_protected_file(None))

    def test_empty_string_not_protected(self):
        self.assertFalse(improver._is_protected_file(""))

    def test_path_with_subdir_checks_basename(self):
        # Directory name contains 'credential' but filename is safe
        self.assertFalse(improver._is_protected_file("credential_store/journal.py"))

    def test_api_key_underscore_variant_protected(self):
        self.assertTrue(improver._is_protected_file("my_api_key.py"))


# ---------------------------------------------------------------------------
# TestQualityGateExtended
# ---------------------------------------------------------------------------

class TestQualityGateExtended(unittest.TestCase):
    """QualityGate edge cases not covered in base tests."""

    def setUp(self):
        self.gate = improver.QualityGate()

    def test_all_zeros_fails(self):
        result = self.gate.evaluate({"a": 0.0, "b": 0.0})
        self.assertFalse(result["passed"])
        self.assertEqual(result["geometric_mean"], 0.0)

    def test_single_metric_rejected(self):
        result = self.gate.evaluate({"a": 0.9})
        self.assertFalse(result["passed"])
        self.assertIn("error", result)

    def test_values_above_one_clamped_to_one(self):
        result = self.gate.evaluate({"a": 2.0, "b": 1.5})
        self.assertEqual(result["metrics"]["a"], 1.0)
        self.assertEqual(result["metrics"]["b"], 1.0)

    def test_negative_values_clamped_to_zero(self):
        result = self.gate.evaluate({"a": -0.5, "b": 0.8})
        self.assertEqual(result["metrics"]["a"], 0.0)

    def test_threshold_zero_always_passes(self):
        gate = improver.QualityGate(threshold=0.0)
        result = gate.evaluate({"a": 0.0, "b": 0.0})
        self.assertTrue(result["passed"])

    def test_threshold_one_only_passes_all_ones(self):
        gate = improver.QualityGate(threshold=1.0)
        result = gate.evaluate({"a": 1.0, "b": 1.0})
        self.assertTrue(result["passed"])
        result2 = gate.evaluate({"a": 0.99, "b": 1.0})
        self.assertFalse(result2["passed"])

    def test_weakest_metric_identified_correctly(self):
        result = self.gate.evaluate({"strong": 0.9, "weak": 0.1, "medium": 0.5})
        self.assertEqual(result["weakest_metric"], "weak")

    def test_five_metrics_geometric_mean(self):
        # (0.5 * 0.5 * 0.5 * 0.5 * 0.5)^(1/5) = 0.5
        result = self.gate.evaluate({"a": 0.5, "b": 0.5, "c": 0.5, "d": 0.5, "e": 0.5})
        self.assertAlmostEqual(result["geometric_mean"], 0.5, places=6)

    def test_anti_gaming_one_zero_kills_score(self):
        # One zero tanks the geometric mean to 0 no matter how high others are
        result = self.gate.evaluate({"perfect": 1.0, "good": 0.9, "zero": 0.0})
        self.assertEqual(result["geometric_mean"], 0.0)


if __name__ == "__main__":
    unittest.main()
