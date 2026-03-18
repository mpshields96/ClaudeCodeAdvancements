#!/usr/bin/env python3
"""Tests for SentinelMutator — adaptive mutation in self-learning loop.

Sentinel concept: like the X-Men Sentinels, the system analyzes failures,
generates counter-strategies, cross-pollinates across domains, and
proactively scans for weaknesses.
"""

import json
import os
import sys
import tempfile
import unittest

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from improver import (
    ImprovementProposal, ImprovementStore, Improver, QualityGate,
)


# ---------------------------------------------------------------------------
# Helper: create proposals for testing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# SentinelMutator tests
# ---------------------------------------------------------------------------

class TestSentinelMutatorImport(unittest.TestCase):
    """Test that SentinelMutator can be imported."""

    def test_import(self):
        from improver import SentinelMutator
        self.assertTrue(hasattr(SentinelMutator, 'mutate_from_failure'))
        self.assertTrue(hasattr(SentinelMutator, 'cross_pollinate'))
        self.assertTrue(hasattr(SentinelMutator, 'scan_weaknesses'))


class TestMutateFromFailure(unittest.TestCase):
    """Test failure analysis → counter-strategy generation."""

    def setUp(self):
        from improver import SentinelMutator
        self.mutator = SentinelMutator()

    def test_rejected_proposal_generates_mutation(self):
        """A rejected proposal should spawn a mutated counter-strategy."""
        rejected = _make_proposal(
            pattern_type="retry_loop",
            status="rejected",
            outcome={"improved": False, "metric_before": 0.4, "metric_after": 0.5},
            pattern_data={"file": "hooks/meter.py", "count": 5},
            proposed_fix="Add pre-read guard before Edit on hooks/meter.py",
        )
        mutations = self.mutator.mutate_from_failure(rejected)
        self.assertGreater(len(mutations), 0)
        # Mutations should reference the original
        for m in mutations:
            self.assertEqual(m.source, "sentinel_mutation")
            self.assertIn("mutation_of", m.pattern_data)

    def test_non_rejected_proposal_no_mutation(self):
        """Only rejected proposals should generate mutations."""
        proposed = _make_proposal(status="proposed")
        mutations = self.mutator.mutate_from_failure(proposed)
        self.assertEqual(len(mutations), 0)

    def test_mutation_changes_approach(self):
        """The mutated proposal should have a different fix than the original."""
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            proposed_fix="Add pre-read guard before Edit",
            pattern_type="retry_loop",
        )
        mutations = self.mutator.mutate_from_failure(rejected)
        if mutations:
            self.assertNotEqual(mutations[0].proposed_fix, rejected.proposed_fix)

    def test_mutation_inherits_pattern_type(self):
        """Mutations should preserve the pattern type they're addressing."""
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            pattern_type="high_waste",
            pattern_data={"waste_rate": 0.5},
        )
        mutations = self.mutator.mutate_from_failure(rejected)
        if mutations:
            self.assertEqual(mutations[0].pattern_type, "high_waste_mutation")

    def test_mutation_risk_not_lower_than_original(self):
        """Mutations should be at least as risky as the original."""
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            risk_level="MEDIUM",
        )
        mutations = self.mutator.mutate_from_failure(rejected)
        risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        for m in mutations:
            self.assertGreaterEqual(
                risk_order[m.risk_level], risk_order[rejected.risk_level]
            )

    def test_protected_file_blocks_mutation(self):
        """Mutations targeting protected files should be blocked."""
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            pattern_data={"file": ".env"},
        )
        mutations = self.mutator.mutate_from_failure(rejected)
        for m in mutations:
            self.assertNotIn(".env", str(m.target_file or ""))

    def test_max_mutation_depth(self):
        """Mutations of mutations should be capped at depth 2."""
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            pattern_data={"file": "test.py", "mutation_of": "imp_1", "mutation_depth": 2},
        )
        mutations = self.mutator.mutate_from_failure(rejected)
        self.assertEqual(len(mutations), 0, "Should not mutate beyond depth 2")


class TestCrossPollinate(unittest.TestCase):
    """Test cross-domain adaptation of successful strategies."""

    def setUp(self):
        from improver import SentinelMutator
        self.mutator = SentinelMutator()

    def test_successful_strategy_generates_cross_domain(self):
        """A validated strategy in one domain should spawn proposals for others."""
        validated = _make_proposal(
            pattern_type="high_waste",
            status="validated",
            target_module="self-learning",
            outcome={"improved": True, "metric_before": 0.4, "metric_after": 0.15},
            proposed_fix="Track file references to avoid speculative reads",
        )
        proposals = self.mutator.cross_pollinate([validated])
        # Should generate at least one cross-domain proposal
        if proposals:
            self.assertNotEqual(proposals[0].target_module, "self-learning")
            self.assertEqual(proposals[0].source, "sentinel_cross_pollination")

    def test_non_validated_skipped(self):
        """Only validated/committed proposals should be cross-pollinated."""
        proposed = _make_proposal(status="proposed")
        rejected = _make_proposal(status="rejected")
        proposals = self.mutator.cross_pollinate([proposed, rejected])
        self.assertEqual(len(proposals), 0)

    def test_trading_never_cross_pollinated_from(self):
        """Trading strategies should never be applied to other domains."""
        validated = _make_proposal(
            status="validated",
            target_module="trading",
            outcome={"improved": True},
        )
        proposals = self.mutator.cross_pollinate([validated])
        # Should not generate cross-domain from trading
        for p in proposals:
            self.assertNotEqual(p.target_module, "trading")

    def test_cross_pollination_marks_origin(self):
        """Cross-pollinated proposals should reference their origin."""
        validated = _make_proposal(
            status="validated",
            target_module="reddit-intelligence",
            outcome={"improved": True},
            proposed_fix="Raise min_score_threshold",
        )
        proposals = self.mutator.cross_pollinate([validated])
        for p in proposals:
            self.assertIn("cross_from", p.pattern_data)
            self.assertIn("origin_module", p.pattern_data)

    def test_no_duplicate_domain_proposals(self):
        """Should not generate multiple proposals for the same target domain."""
        validated = _make_proposal(
            status="validated",
            target_module="self-learning",
            outcome={"improved": True},
        )
        proposals = self.mutator.cross_pollinate([validated])
        domains = [p.target_module for p in proposals]
        self.assertEqual(len(domains), len(set(domains)), "Duplicate domain proposals")


class TestScanWeaknesses(unittest.TestCase):
    """Test proactive weakness scanning."""

    def setUp(self):
        from improver import SentinelMutator
        self.mutator = SentinelMutator()

    def test_no_proposals_detects_gap(self):
        """An empty proposal history should flag all domains as gaps."""
        gaps = self.mutator.scan_weaknesses([])
        self.assertGreater(len(gaps), 0)

    def test_covered_domain_not_flagged(self):
        """Domains with active proposals should not be flagged."""
        active = _make_proposal(
            status="proposed",
            target_module="self-learning",
        )
        gaps = self.mutator.scan_weaknesses([active])
        gap_modules = [g.get("domain") for g in gaps]
        self.assertNotIn("self-learning", gap_modules)

    def test_all_rejected_flags_domain(self):
        """A domain where all proposals were rejected needs attention."""
        r1 = _make_proposal(status="rejected", target_module="reddit-intelligence")
        r2 = _make_proposal(status="rejected", target_module="reddit-intelligence",
                           pattern_type="low_build_rate")
        gaps = self.mutator.scan_weaknesses([r1, r2])
        gap_modules = [g.get("domain") for g in gaps]
        self.assertIn("reddit-intelligence", gap_modules)

    def test_high_rejection_rate_flagged(self):
        """A domain with >66% rejection rate should be flagged."""
        r1 = _make_proposal(status="rejected", target_module="context-monitor")
        r2 = _make_proposal(status="rejected", target_module="context-monitor",
                           pattern_type="low_efficiency")
        v1 = _make_proposal(status="validated", target_module="context-monitor",
                           pattern_type="high_waste")
        gaps = self.mutator.scan_weaknesses([r1, r2, v1])
        gap_modules = [g.get("domain") for g in gaps]
        self.assertIn("context-monitor", gap_modules)

    def test_gap_report_includes_reason(self):
        """Gap reports should include why the domain is weak."""
        gaps = self.mutator.scan_weaknesses([])
        for g in gaps:
            self.assertIn("reason", g)
            self.assertIn("domain", g)


class TestSentinelIntegration(unittest.TestCase):
    """Test Sentinel integration with the Improver lifecycle."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.tmpfile.close()
        self.store_path = self.tmpfile.name

    def tearDown(self):
        os.unlink(self.store_path)

    def test_improver_has_sentinel(self):
        """Improver should have a sentinel attribute."""
        imp = Improver(store_path=self.store_path)
        self.assertTrue(hasattr(imp, 'sentinel'))

    def test_evolve_runs_all_sentinel_steps(self):
        """Improver.evolve() should run mutation, cross-pollination, and weakness scan."""
        imp = Improver(store_path=self.store_path)
        # Add a rejected and a validated proposal
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            pattern_data={"file": "test.py"},
        )
        validated = _make_proposal(
            status="validated",
            target_module="self-learning",
            outcome={"improved": True},
            pattern_type="high_waste",
        )
        imp.store.append(rejected)
        imp.store.append(validated)

        result = imp.evolve()
        self.assertIn("mutations", result)
        self.assertIn("cross_pollinations", result)
        self.assertIn("weakness_gaps", result)

    def test_evolve_appends_to_store(self):
        """Evolve should persist new proposals to the store."""
        imp = Improver(store_path=self.store_path)
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            pattern_data={"file": "test.py", "count": 5},
            pattern_type="retry_loop",
        )
        imp.store.append(rejected)
        result = imp.evolve()
        # Total proposals should be original + any new ones
        all_proposals = imp.store.load_all()
        total_new = result["mutations"] + result["cross_pollinations"]
        self.assertEqual(len(all_proposals), 1 + total_new)

    def test_evolve_respects_max_mutations(self):
        """Evolve should cap the number of mutations per cycle."""
        imp = Improver(store_path=self.store_path)
        # Add many rejected proposals
        for i in range(10):
            r = _make_proposal(
                status="rejected",
                outcome={"improved": False},
                pattern_data={"file": f"file_{i}.py", "count": 3},
                pattern_type="retry_loop",
            )
            imp.store.append(r)
        result = imp.evolve()
        self.assertLessEqual(result["mutations"], 2, "Should cap mutations at 2 per cycle")


class TestMutationStrategies(unittest.TestCase):
    """Test specific mutation strategies for different pattern types."""

    def setUp(self):
        from improver import SentinelMutator
        self.mutator = SentinelMutator()

    def test_retry_loop_mutation_alternatives(self):
        """Retry loop failures should try alternative approaches."""
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            pattern_type="retry_loop",
            pattern_data={"file": "hooks/meter.py", "count": 5, "tool": "Edit"},
            proposed_fix="Add pre-read guard before Edit on hooks/meter.py",
        )
        mutations = self.mutator.mutate_from_failure(rejected)
        self.assertGreater(len(mutations), 0)
        # The fix should suggest a different approach
        fix = mutations[0].proposed_fix
        self.assertNotEqual(fix, rejected.proposed_fix)

    def test_high_waste_mutation_alternatives(self):
        """High waste failures should try different reduction strategies."""
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            pattern_type="high_waste",
            pattern_data={"waste_rate": 0.5, "wasted_count": 10},
            proposed_fix="Track file references to avoid speculative reads",
        )
        mutations = self.mutator.mutate_from_failure(rejected)
        self.assertGreater(len(mutations), 0)

    def test_low_efficiency_mutation(self):
        """Low efficiency failures should suggest batching or caching."""
        rejected = _make_proposal(
            status="rejected",
            outcome={"improved": False},
            pattern_type="low_efficiency",
            pattern_data={"ratio": 0.05, "unique_files": 3, "total_calls": 60},
            proposed_fix="Reduce redundant tool calls",
        )
        mutations = self.mutator.mutate_from_failure(rejected)
        self.assertGreater(len(mutations), 0)


class TestSentinelCLI(unittest.TestCase):
    """Test the sentinel CLI subcommands."""

    def test_evolve_command_exists(self):
        """The 'evolve' CLI subcommand should exist."""
        # Just verify the import works — CLI is tested via integration
        from improver import Improver
        imp = Improver()
        self.assertTrue(hasattr(imp, 'evolve'))


if __name__ == "__main__":
    unittest.main()
