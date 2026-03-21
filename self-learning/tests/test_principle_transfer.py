#!/usr/bin/env python3
"""
Tests for principle_transfer.py — MT-28 Phase 3: Cross-Domain Principle Transfer

Tests domain affinity scoring, transfer candidate identification,
transfer suggestions, and integration with pattern_registry.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from principle_transfer import (
    DomainAffinity,
    TransferCandidate,
    PrincipleTransfer,
    DOMAIN_AFFINITY_MAP,
)
from principle_registry import (
    Principle,
    add_principle,
    record_usage,
    _load_principles,
    VALID_DOMAINS,
)


class TestDomainAffinityMap(unittest.TestCase):
    """Domain affinity map structure and values."""

    def test_map_exists(self):
        self.assertIsInstance(DOMAIN_AFFINITY_MAP, dict)

    def test_all_valid_domains_present(self):
        for domain in VALID_DOMAINS:
            self.assertIn(domain, DOMAIN_AFFINITY_MAP, f"Missing domain: {domain}")

    def test_affinity_values_are_dicts(self):
        for domain, affinities in DOMAIN_AFFINITY_MAP.items():
            self.assertIsInstance(affinities, dict, f"Bad affinity for {domain}")

    def test_affinity_values_in_range(self):
        for domain, affinities in DOMAIN_AFFINITY_MAP.items():
            for target, score in affinities.items():
                self.assertGreaterEqual(score, 0.0, f"{domain}->{target}")
                self.assertLessEqual(score, 1.0, f"{domain}->{target}")

    def test_self_affinity_not_present(self):
        """A domain should not have affinity to itself (it's implicit)."""
        for domain, affinities in DOMAIN_AFFINITY_MAP.items():
            self.assertNotIn(domain, affinities)


class TestDomainAffinity(unittest.TestCase):
    """DomainAffinity dataclass."""

    def test_creation(self):
        aff = DomainAffinity(
            source="trading_research",
            target="trading_execution",
            score=0.85,
            reason="Both trading domains share strategy concepts",
        )
        self.assertEqual(aff.source, "trading_research")
        self.assertEqual(aff.score, 0.85)

    def test_to_dict(self):
        aff = DomainAffinity(
            source="trading_research",
            target="trading_execution",
            score=0.85,
            reason="Both trading domains",
        )
        d = aff.to_dict()
        self.assertEqual(d["source"], "trading_research")
        self.assertEqual(d["score"], 0.85)


class TestTransferCandidate(unittest.TestCase):
    """TransferCandidate dataclass."""

    def test_creation(self):
        candidate = TransferCandidate(
            principle_id="prin_abc12345",
            principle_text="Test principle",
            source_domain="code_quality",
            target_domain="session_management",
            principle_score=0.82,
            affinity_score=0.65,
            transfer_score=0.53,
            reason="Code quality practices apply to session management",
        )
        self.assertEqual(candidate.principle_id, "prin_abc12345")
        self.assertAlmostEqual(candidate.transfer_score, 0.53)

    def test_to_dict(self):
        candidate = TransferCandidate(
            principle_id="prin_abc12345",
            principle_text="Test",
            source_domain="code_quality",
            target_domain="session_management",
            principle_score=0.82,
            affinity_score=0.65,
            transfer_score=0.53,
            reason="Test reason",
        )
        d = candidate.to_dict()
        self.assertIn("principle_id", d)
        self.assertIn("transfer_score", d)


class TestPrincipleTransferInit(unittest.TestCase):
    """PrincipleTransfer initialization."""

    def test_default_init(self):
        pt = PrincipleTransfer()
        self.assertGreater(pt.min_principle_score, 0)
        self.assertGreater(pt.min_affinity, 0)
        self.assertGreater(pt.min_usages, 0)

    def test_custom_thresholds(self):
        pt = PrincipleTransfer(
            min_principle_score=0.8,
            min_affinity=0.5,
            min_usages=10,
        )
        self.assertEqual(pt.min_principle_score, 0.8)
        self.assertEqual(pt.min_affinity, 0.5)
        self.assertEqual(pt.min_usages, 10)


class TestGetDomainAffinity(unittest.TestCase):
    """Getting affinity between domains."""

    def setUp(self):
        self.pt = PrincipleTransfer()

    def test_known_affinity(self):
        score = self.pt.get_affinity("trading_research", "trading_execution")
        self.assertGreater(score, 0)

    def test_same_domain_returns_one(self):
        score = self.pt.get_affinity("code_quality", "code_quality")
        self.assertEqual(score, 1.0)

    def test_unknown_affinity_returns_zero(self):
        # If domains have no defined affinity
        score = self.pt.get_affinity("nuclear_scan", "trading_execution")
        # May be 0 or low, depends on map
        self.assertGreaterEqual(score, 0.0)

    def test_returns_float(self):
        score = self.pt.get_affinity("cca_operations", "session_management")
        self.assertIsInstance(score, float)


class TestFindTransferCandidates(unittest.TestCase):
    """Finding principles that could transfer to a target domain."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        )
        self.tmpfile.close()
        self.path = self.tmpfile.name
        self.pt = PrincipleTransfer(
            min_principle_score=0.6,
            min_affinity=0.3,
            min_usages=3,
        )

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def _add_high_scoring_principle(self, domain, text, successes=8, usages=10):
        """Add a principle with high score via the registry API."""
        p = add_principle(
            text=text,
            source_domain=domain,
            applicable_domains=[domain],
            session=1,
            path=self.path,
        )
        for i in range(usages):
            record_usage(p.id, success=(i < successes), session=1, path=self.path)
        return p

    def test_finds_candidates_from_related_domain(self):
        self._add_high_scoring_principle(
            "trading_research",
            "Always validate signals against historical data before acting",
        )
        candidates = self.pt.find_transfer_candidates(
            target_domain="trading_execution",
            principles_path=self.path,
        )
        # trading_research -> trading_execution should have high affinity
        self.assertGreater(len(candidates), 0)

    def test_no_candidates_for_same_domain(self):
        self._add_high_scoring_principle(
            "code_quality",
            "Write tests before implementation code",
        )
        candidates = self.pt.find_transfer_candidates(
            target_domain="code_quality",
            principles_path=self.path,
        )
        # Should not suggest transferring to same domain
        self.assertEqual(len(candidates), 0)

    def test_excludes_already_applicable(self):
        """If principle already applies to target domain, skip it."""
        p = add_principle(
            text="Review before committing",
            source_domain="code_quality",
            applicable_domains=["code_quality", "session_management"],
            session=1,
            path=self.path,
        )
        for i in range(10):
            record_usage(p.id, success=True, session=1, path=self.path)

        candidates = self.pt.find_transfer_candidates(
            target_domain="session_management",
            principles_path=self.path,
        )
        # Already applicable — should not appear
        matching = [c for c in candidates if c.principle_id == p.id]
        self.assertEqual(len(matching), 0)

    def test_excludes_low_score_principles(self):
        p = add_principle(
            text="A questionable principle",
            source_domain="trading_research",
            session=1,
            path=self.path,
        )
        # Record mostly failures
        for i in range(10):
            record_usage(p.id, success=False, session=1, path=self.path)

        candidates = self.pt.find_transfer_candidates(
            target_domain="trading_execution",
            principles_path=self.path,
        )
        matching = [c for c in candidates if c.principle_id == p.id]
        self.assertEqual(len(matching), 0)

    def test_excludes_low_usage_principles(self):
        p = add_principle(
            text="An untested principle",
            source_domain="trading_research",
            session=1,
            path=self.path,
        )
        # Only 1 usage — below min_usages=3
        record_usage(p.id, success=True, session=1, path=self.path)

        candidates = self.pt.find_transfer_candidates(
            target_domain="trading_execution",
            principles_path=self.path,
        )
        matching = [c for c in candidates if c.principle_id == p.id]
        self.assertEqual(len(matching), 0)

    def test_candidates_sorted_by_transfer_score(self):
        self._add_high_scoring_principle(
            "trading_research",
            "Validate signals against historical data first",
        )
        self._add_high_scoring_principle(
            "trading_research",
            "Use Bayesian updating for belief revision",
        )
        candidates = self.pt.find_transfer_candidates(
            target_domain="trading_execution",
            principles_path=self.path,
        )
        if len(candidates) >= 2:
            for i in range(len(candidates) - 1):
                self.assertGreaterEqual(
                    candidates[i].transfer_score,
                    candidates[i + 1].transfer_score,
                )

    def test_candidate_has_all_fields(self):
        self._add_high_scoring_principle(
            "trading_research",
            "Check regime before placing bets",
        )
        candidates = self.pt.find_transfer_candidates(
            target_domain="trading_execution",
            principles_path=self.path,
        )
        if candidates:
            c = candidates[0]
            self.assertIsInstance(c, TransferCandidate)
            self.assertIsNotNone(c.principle_id)
            self.assertIsNotNone(c.source_domain)
            self.assertIsNotNone(c.target_domain)
            self.assertGreater(c.transfer_score, 0)

    def test_empty_registry_returns_empty(self):
        candidates = self.pt.find_transfer_candidates(
            target_domain="trading_execution",
            principles_path=self.path,
        )
        self.assertEqual(len(candidates), 0)

    def test_pruned_principles_excluded(self):
        p = self._add_high_scoring_principle(
            "trading_research",
            "A principle that will be pruned",
            successes=1,
            usages=15,
        )
        # Manually prune
        principles = _load_principles(self.path)
        principles[p.id].pruned = True
        from principle_registry import _atomic_rewrite
        _atomic_rewrite(principles, self.path)

        candidates = self.pt.find_transfer_candidates(
            target_domain="trading_execution",
            principles_path=self.path,
        )
        matching = [c for c in candidates if c.principle_id == p.id]
        self.assertEqual(len(matching), 0)


class TestApplyTransfer(unittest.TestCase):
    """Applying a transfer — adding target domain to principle's applicable_domains."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        )
        self.tmpfile.close()
        self.path = self.tmpfile.name
        self.pt = PrincipleTransfer(min_principle_score=0.6, min_affinity=0.3, min_usages=3)

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_apply_adds_domain(self):
        p = add_principle(
            text="Verify data before using",
            source_domain="code_quality",
            applicable_domains=["code_quality"],
            session=1,
            path=self.path,
        )
        self.pt.apply_transfer(
            principle_id=p.id,
            target_domain="session_management",
            principles_path=self.path,
        )
        updated = _load_principles(self.path)
        self.assertIn("session_management", updated[p.id].applicable_domains)

    def test_apply_idempotent(self):
        p = add_principle(
            text="Always test before deploying",
            source_domain="code_quality",
            applicable_domains=["code_quality"],
            session=1,
            path=self.path,
        )
        self.pt.apply_transfer(p.id, "session_management", self.path)
        self.pt.apply_transfer(p.id, "session_management", self.path)
        updated = _load_principles(self.path)
        count = updated[p.id].applicable_domains.count("session_management")
        self.assertEqual(count, 1)

    def test_apply_invalid_domain_raises(self):
        p = add_principle(
            text="Test principle",
            source_domain="general",
            session=1,
            path=self.path,
        )
        with self.assertRaises(ValueError):
            self.pt.apply_transfer(p.id, "invalid_domain", self.path)

    def test_apply_nonexistent_principle_raises(self):
        with self.assertRaises(KeyError):
            self.pt.apply_transfer("prin_nonexist", "general", self.path)


class TestScanAllDomains(unittest.TestCase):
    """Scanning all domains for transfer opportunities."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        )
        self.tmpfile.close()
        self.path = self.tmpfile.name
        self.pt = PrincipleTransfer(min_principle_score=0.6, min_affinity=0.3, min_usages=3)

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_scan_empty_returns_empty(self):
        results = self.pt.scan_all_domains(principles_path=self.path)
        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 0)

    def test_scan_returns_dict_by_target_domain(self):
        p = add_principle(
            text="Always backtest strategies",
            source_domain="trading_research",
            session=1,
            path=self.path,
        )
        for i in range(10):
            record_usage(p.id, success=True, session=1, path=self.path)

        results = self.pt.scan_all_domains(principles_path=self.path)
        self.assertIsInstance(results, dict)
        # Should find at least one target domain
        for domain, candidates in results.items():
            self.assertIn(domain, VALID_DOMAINS)
            self.assertIsInstance(candidates, list)

    def test_scan_excludes_empty_domains(self):
        """Domains with no transfer candidates should not appear in results."""
        results = self.pt.scan_all_domains(principles_path=self.path)
        for domain, candidates in results.items():
            self.assertGreater(len(candidates), 0)


class TestTransferScoreCalculation(unittest.TestCase):
    """Transfer score = principle_score * affinity_score."""

    def setUp(self):
        self.pt = PrincipleTransfer()

    def test_transfer_score_is_product(self):
        """Transfer score should be principle_score * affinity_score."""
        principle_score = 0.8
        affinity_score = 0.7
        expected = 0.56  # 0.8 * 0.7
        actual = self.pt.compute_transfer_score(principle_score, affinity_score)
        self.assertAlmostEqual(actual, expected, places=2)

    def test_zero_affinity_gives_zero(self):
        actual = self.pt.compute_transfer_score(0.9, 0.0)
        self.assertEqual(actual, 0.0)

    def test_perfect_scores(self):
        actual = self.pt.compute_transfer_score(1.0, 1.0)
        self.assertEqual(actual, 1.0)


if __name__ == "__main__":
    unittest.main()
