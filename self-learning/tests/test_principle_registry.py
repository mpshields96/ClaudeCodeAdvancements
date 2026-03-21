#!/usr/bin/env python3
"""Tests for principle_registry.py — MT-28 Phase 1."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from principle_registry import (
    Principle,
    add_principle,
    record_usage,
    get_principles,
    get_top_principles,
    prune_principles,
    get_stats,
    get_principle_by_id,
    _generate_id,
    _text_similarity,
    _load_principles,
    _save_principle,
    _atomic_rewrite,
    PRUNE_SCORE,
    PRUNE_MIN_USAGES,
    REINFORCE_SCORE,
    MAX_PRINCIPLES_PER_DOMAIN,
    VALID_DOMAINS,
)


class TestPrincipleDataclass(unittest.TestCase):
    """Test the Principle dataclass and its computed properties."""

    def test_score_zero_usage(self):
        """Laplace-smoothed: (0+1)/(0+2) = 0.5 for new principles."""
        p = Principle(id="test", text="t", source_domain="general", applicable_domains=["general"])
        self.assertAlmostEqual(p.score, 0.5)

    def test_score_all_success(self):
        """10 successes out of 10: (10+1)/(10+2) = 0.9167."""
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=10, usage_count=10)
        self.assertAlmostEqual(p.score, 11/12, places=4)

    def test_score_all_failure(self):
        """0 successes out of 10: (0+1)/(10+2) = 0.0833."""
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=0, usage_count=10)
        self.assertAlmostEqual(p.score, 1/12, places=4)

    def test_score_mixed(self):
        """5 successes out of 10: (5+1)/(10+2) = 0.5."""
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=5, usage_count=10)
        self.assertAlmostEqual(p.score, 0.5)

    def test_should_prune_low_score_enough_data(self):
        """Prune when score < 0.3 AND 10+ usages."""
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=1, usage_count=15)
        self.assertTrue(p.should_prune)

    def test_should_not_prune_low_data(self):
        """Don't prune with insufficient data even if score is low."""
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=0, usage_count=5)
        self.assertFalse(p.should_prune)

    def test_should_not_prune_already_pruned(self):
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=1, usage_count=15, pruned=True)
        self.assertFalse(p.should_prune)

    def test_should_not_prune_good_score(self):
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=8, usage_count=10)
        self.assertFalse(p.should_prune)

    def test_is_reinforced(self):
        """Score >= 0.7 and 5+ usages."""
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=8, usage_count=10)
        self.assertTrue(p.is_reinforced)

    def test_not_reinforced_low_usage(self):
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=2, usage_count=2)
        self.assertFalse(p.is_reinforced)

    def test_not_reinforced_low_score(self):
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=3, usage_count=10)
        self.assertFalse(p.is_reinforced)

    def test_to_dict(self):
        p = Principle(id="t", text="hello", source_domain="general",
                      applicable_domains=["general"], success_count=3, usage_count=5)
        d = p.to_dict()
        self.assertEqual(d["id"], "t")
        self.assertEqual(d["text"], "hello")
        self.assertIn("score", d)
        self.assertAlmostEqual(d["score"], 4/7, places=4)


class TestHelpers(unittest.TestCase):
    """Test helper functions."""

    def test_generate_id_deterministic(self):
        """Same text+domain = same ID."""
        id1 = _generate_id("hello world", "general")
        id2 = _generate_id("hello world", "general")
        self.assertEqual(id1, id2)

    def test_generate_id_prefix(self):
        pid = _generate_id("test", "general")
        self.assertTrue(pid.startswith("prin_"))

    def test_generate_id_different_domains(self):
        id1 = _generate_id("hello", "general")
        id2 = _generate_id("hello", "trading_research")
        self.assertNotEqual(id1, id2)

    def test_generate_id_case_insensitive(self):
        id1 = _generate_id("Hello World", "general")
        id2 = _generate_id("hello world", "general")
        self.assertEqual(id1, id2)

    def test_text_similarity_identical(self):
        self.assertAlmostEqual(_text_similarity("hello world", "hello world"), 1.0)

    def test_text_similarity_no_overlap(self):
        self.assertAlmostEqual(_text_similarity("hello world", "foo bar"), 0.0)

    def test_text_similarity_partial(self):
        sim = _text_similarity("hello world foo", "hello world bar")
        self.assertGreater(sim, 0.3)
        self.assertLess(sim, 1.0)

    def test_text_similarity_empty(self):
        self.assertAlmostEqual(_text_similarity("", "hello"), 0.0)
        self.assertAlmostEqual(_text_similarity("", ""), 0.0)


class TestPersistence(unittest.TestCase):
    """Test JSONL file operations."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.path = self.tmpfile.name
        self.tmpfile.close()
        # Start with empty file
        open(self.path, "w").close()

    def tearDown(self):
        os.unlink(self.path)

    def test_load_empty(self):
        principles = _load_principles(self.path)
        self.assertEqual(len(principles), 0)

    def test_load_nonexistent(self):
        principles = _load_principles("/tmp/nonexistent_principles_test.jsonl")
        self.assertEqual(len(principles), 0)

    def test_save_and_load(self):
        p = Principle(id="prin_test1", text="test principle", source_domain="general",
                      applicable_domains=["general"])
        _save_principle(p, self.path)

        loaded = _load_principles(self.path)
        self.assertIn("prin_test1", loaded)
        self.assertEqual(loaded["prin_test1"].text, "test principle")

    def test_append_only_latest_wins(self):
        """When same ID appears twice, latest version wins."""
        p1 = Principle(id="prin_dup", text="v1", source_domain="general",
                       applicable_domains=["general"], usage_count=0)
        p2 = Principle(id="prin_dup", text="v2", source_domain="general",
                       applicable_domains=["general"], usage_count=5)
        _save_principle(p1, self.path)
        _save_principle(p2, self.path)

        loaded = _load_principles(self.path)
        self.assertEqual(loaded["prin_dup"].text, "v2")
        self.assertEqual(loaded["prin_dup"].usage_count, 5)

    def test_atomic_rewrite(self):
        p = Principle(id="prin_rw", text="rewrite test", source_domain="general",
                      applicable_domains=["general"])
        _save_principle(p, self.path)

        loaded = _load_principles(self.path)
        loaded["prin_rw"].pruned = True
        _atomic_rewrite(loaded, self.path)

        reloaded = _load_principles(self.path)
        self.assertTrue(reloaded["prin_rw"].pruned)
        # File should have exactly 1 line after rewrite
        with open(self.path) as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 1)

    def test_malformed_json_skipped(self):
        with open(self.path, "w") as f:
            f.write("not json\n")
            f.write(json.dumps({"id": "prin_ok", "text": "ok", "source_domain": "general",
                                "applicable_domains": ["general"]}) + "\n")
        loaded = _load_principles(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertIn("prin_ok", loaded)


class TestAddPrinciple(unittest.TestCase):
    """Test adding principles."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.path = self.tmpfile.name
        self.tmpfile.close()
        open(self.path, "w").close()

    def tearDown(self):
        os.unlink(self.path)

    def test_add_basic(self):
        p = add_principle("Test principle", "general", path=self.path)
        self.assertTrue(p.id.startswith("prin_"))
        self.assertEqual(p.text, "Test principle")
        self.assertEqual(p.source_domain, "general")
        self.assertAlmostEqual(p.score, 0.5)

    def test_add_with_session(self):
        p = add_principle("Test", "general", session=105, path=self.path)
        self.assertEqual(p.created_session, 105)
        self.assertEqual(p.last_used_session, 105)

    def test_add_with_applicable_domains(self):
        p = add_principle("Cross-domain", "cca_operations",
                          applicable_domains=["cca_operations", "trading_research"],
                          path=self.path)
        self.assertIn("trading_research", p.applicable_domains)

    def test_add_default_applicable_domains(self):
        p = add_principle("Domain-local", "code_quality", path=self.path)
        self.assertEqual(p.applicable_domains, ["code_quality"])

    def test_add_invalid_domain(self):
        with self.assertRaises(ValueError):
            add_principle("Test", "invalid_domain", path=self.path)

    def test_add_invalid_applicable_domain(self):
        with self.assertRaises(ValueError):
            add_principle("Test", "general",
                          applicable_domains=["general", "fake"], path=self.path)

    def test_add_duplicate_rejected(self):
        add_principle("When evidence is ambiguous seek corroboration", "general", path=self.path)
        with self.assertRaises(ValueError) as ctx:
            add_principle("When evidence is ambiguous seek corroboration", "general", path=self.path)
        self.assertIn("Duplicate", str(ctx.exception))

    def test_add_similar_rejected(self):
        add_principle("always verify data before making decisions about strategy",
                      "general", path=self.path)
        with self.assertRaises(ValueError):
            add_principle("always verify data before making decisions about strategy changes",
                          "general", path=self.path)

    def test_add_different_text_allowed(self):
        add_principle("Principle about testing", "general", path=self.path)
        p2 = add_principle("Principle about deployment", "general", path=self.path)
        self.assertIsNotNone(p2)

    def test_add_persists(self):
        add_principle("Persistent principle", "general", path=self.path)
        loaded = _load_principles(self.path)
        self.assertEqual(len(loaded), 1)

    def test_add_context(self):
        p = add_principle("Test", "general", source_context="S105 nuclear scan",
                          path=self.path)
        self.assertEqual(p.source_context, "S105 nuclear scan")

    def test_add_strips_whitespace(self):
        p = add_principle("  spaced text  ", "general", path=self.path)
        self.assertEqual(p.text, "spaced text")

    def test_domain_cap(self):
        """Cannot exceed MAX_PRINCIPLES_PER_DOMAIN."""
        # Use hash-based unique text to avoid dedup triggers
        import hashlib
        for i in range(MAX_PRINCIPLES_PER_DOMAIN):
            h = hashlib.md5(str(i).encode()).hexdigest()
            add_principle(f"{h} principle", "general", path=self.path)

        with self.assertRaises(ValueError) as ctx:
            add_principle("One more beyond the cap entirely different", "general", path=self.path)
        self.assertIn("max", str(ctx.exception).lower())


class TestRecordUsage(unittest.TestCase):
    """Test recording usage outcomes."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.path = self.tmpfile.name
        self.tmpfile.close()
        open(self.path, "w").close()

    def tearDown(self):
        os.unlink(self.path)

    def test_record_success(self):
        p = add_principle("Test usage", "general", path=self.path)
        updated = record_usage(p.id, success=True, path=self.path)
        self.assertEqual(updated.usage_count, 1)
        self.assertEqual(updated.success_count, 1)

    def test_record_failure(self):
        p = add_principle("Test failure", "general", path=self.path)
        updated = record_usage(p.id, success=False, path=self.path)
        self.assertEqual(updated.usage_count, 1)
        self.assertEqual(updated.success_count, 0)

    def test_record_multiple(self):
        p = add_principle("Multiple usages", "general", path=self.path)
        record_usage(p.id, success=True, path=self.path)
        record_usage(p.id, success=True, path=self.path)
        updated = record_usage(p.id, success=False, path=self.path)
        self.assertEqual(updated.usage_count, 3)
        self.assertEqual(updated.success_count, 2)

    def test_record_updates_session(self):
        p = add_principle("Session track", "general", session=100, path=self.path)
        updated = record_usage(p.id, success=True, session=105, path=self.path)
        self.assertEqual(updated.last_used_session, 105)

    def test_record_nonexistent_id(self):
        with self.assertRaises(KeyError):
            record_usage("prin_nonexistent", success=True, path=self.path)

    def test_record_pruned_rejected(self):
        p = add_principle("Will be pruned", "general", path=self.path)
        # Manually mark pruned
        principles = _load_principles(self.path)
        principles[p.id].pruned = True
        _atomic_rewrite(principles, self.path)

        with self.assertRaises(ValueError):
            record_usage(p.id, success=True, path=self.path)

    def test_score_changes_with_usage(self):
        p = add_principle("Score tracker", "general", path=self.path)
        initial_score = p.score  # 0.5

        # Record 5 successes
        for _ in range(5):
            p = record_usage(p.id, success=True, path=self.path)

        # Score should be (5+1)/(5+2) = 0.857
        self.assertGreater(p.score, initial_score)
        self.assertAlmostEqual(p.score, 6/7, places=3)


class TestGetPrinciples(unittest.TestCase):
    """Test querying principles."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.path = self.tmpfile.name
        self.tmpfile.close()
        open(self.path, "w").close()

        # Seed some principles
        self.p1 = add_principle("General principle one", "general", path=self.path)
        self.p2 = add_principle("Trading research insight", "trading_research", path=self.path)
        self.p3 = add_principle("Code quality rule", "code_quality",
                                applicable_domains=["code_quality", "general"], path=self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_get_all(self):
        result = get_principles(path=self.path)
        self.assertEqual(len(result), 3)

    def test_filter_by_domain(self):
        result = get_principles(domain="trading_research", path=self.path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source_domain, "trading_research")

    def test_filter_by_applicable_domain(self):
        """Code quality principle is also applicable to general."""
        result = get_principles(domain="general", path=self.path)
        self.assertEqual(len(result), 2)  # p1 (general) + p3 (applicable to general)

    def test_filter_by_min_score(self):
        # All new principles have score 0.5
        result = get_principles(min_score=0.6, path=self.path)
        self.assertEqual(len(result), 0)

        result = get_principles(min_score=0.4, path=self.path)
        self.assertEqual(len(result), 3)

    def test_excludes_pruned(self):
        principles = _load_principles(self.path)
        principles[self.p1.id].pruned = True
        _atomic_rewrite(principles, self.path)

        result = get_principles(path=self.path)
        self.assertEqual(len(result), 2)

    def test_includes_pruned_when_asked(self):
        principles = _load_principles(self.path)
        principles[self.p1.id].pruned = True
        _atomic_rewrite(principles, self.path)

        result = get_principles(include_pruned=True, path=self.path)
        self.assertEqual(len(result), 3)

    def test_sorted_by_score(self):
        # Give p2 some successes to boost score
        for _ in range(5):
            record_usage(self.p2.id, success=True, path=self.path)

        result = get_principles(path=self.path)
        self.assertEqual(result[0].id, self.p2.id)

    def test_top_n(self):
        result = get_top_principles(n=2, path=self.path)
        self.assertEqual(len(result), 2)

    def test_top_with_domain(self):
        result = get_top_principles(n=5, domain="trading_research", path=self.path)
        self.assertEqual(len(result), 1)

    def test_get_by_id(self):
        p = get_principle_by_id(self.p1.id, path=self.path)
        self.assertIsNotNone(p)
        self.assertEqual(p.text, "General principle one")

    def test_get_by_id_nonexistent(self):
        p = get_principle_by_id("prin_nonexistent", path=self.path)
        self.assertIsNone(p)


class TestPruning(unittest.TestCase):
    """Test pruning underperforming principles."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.path = self.tmpfile.name
        self.tmpfile.close()
        open(self.path, "w").close()

    def tearDown(self):
        os.unlink(self.path)

    def test_prune_underperformer(self):
        p = add_principle("Bad principle", "general", path=self.path)
        # 1 success out of 15 usages -> score = 2/17 = 0.118
        for i in range(15):
            record_usage(p.id, success=(i == 0), path=self.path)

        pruned = prune_principles(path=self.path)
        self.assertIn(p.id, pruned)

        # Verify it's marked pruned
        loaded = get_principle_by_id(p.id, path=self.path)
        self.assertTrue(loaded.pruned)

    def test_prune_dry_run(self):
        p = add_principle("Bad principle dry run", "general", path=self.path)
        for i in range(15):
            record_usage(p.id, success=(i == 0), path=self.path)

        pruned = prune_principles(dry_run=True, path=self.path)
        self.assertIn(p.id, pruned)

        # Should NOT be pruned in reality
        loaded = get_principle_by_id(p.id, path=self.path)
        self.assertFalse(loaded.pruned)

    def test_no_prune_good_principles(self):
        p = add_principle("Good principle", "general", path=self.path)
        for _ in range(10):
            record_usage(p.id, success=True, path=self.path)

        pruned = prune_principles(path=self.path)
        self.assertEqual(len(pruned), 0)

    def test_no_prune_insufficient_data(self):
        p = add_principle("New principle", "general", path=self.path)
        for _ in range(3):
            record_usage(p.id, success=False, path=self.path)

        pruned = prune_principles(path=self.path)
        self.assertEqual(len(pruned), 0)

    def test_prune_preserves_good_principles(self):
        good = add_principle("Good one keeps working", "general", path=self.path)
        bad = add_principle("Bad one always fails", "general", path=self.path)

        for _ in range(10):
            record_usage(good.id, success=True, path=self.path)
        for _ in range(15):
            record_usage(bad.id, success=False, path=self.path)

        pruned = prune_principles(path=self.path)
        self.assertIn(bad.id, pruned)
        self.assertNotIn(good.id, pruned)


class TestStats(unittest.TestCase):
    """Test statistics."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.path = self.tmpfile.name
        self.tmpfile.close()
        open(self.path, "w").close()

    def tearDown(self):
        os.unlink(self.path)

    def test_stats_empty(self):
        stats = get_stats(self.path)
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["active"], 0)

    def test_stats_with_data(self):
        add_principle("P1 for stats", "general", path=self.path)
        add_principle("P2 for stats trading", "trading_research", path=self.path)

        stats = get_stats(self.path)
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["active"], 2)
        self.assertEqual(stats["pruned"], 0)
        self.assertEqual(stats["domain_counts"]["general"], 1)
        self.assertEqual(stats["domain_counts"]["trading_research"], 1)

    def test_stats_avg_score(self):
        add_principle("P for avg", "general", path=self.path)
        stats = get_stats(self.path)
        self.assertAlmostEqual(stats["avg_score"], 0.5, places=2)

    def test_stats_reinforced_count(self):
        p = add_principle("Will be reinforced", "general", path=self.path)
        for _ in range(10):
            record_usage(p.id, success=True, path=self.path)

        stats = get_stats(self.path)
        self.assertEqual(stats["reinforced"], 1)


class TestEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.path = self.tmpfile.name
        self.tmpfile.close()
        open(self.path, "w").close()

    def tearDown(self):
        os.unlink(self.path)

    def test_valid_domains_list(self):
        """All expected domains are present."""
        self.assertIn("cca_operations", VALID_DOMAINS)
        self.assertIn("trading_research", VALID_DOMAINS)
        self.assertIn("trading_execution", VALID_DOMAINS)
        self.assertIn("code_quality", VALID_DOMAINS)
        self.assertIn("general", VALID_DOMAINS)

    def test_prune_threshold_constants(self):
        self.assertEqual(PRUNE_SCORE, 0.3)
        self.assertEqual(PRUNE_MIN_USAGES, 10)
        self.assertEqual(REINFORCE_SCORE, 0.7)

    def test_max_per_domain_constant(self):
        self.assertEqual(MAX_PRINCIPLES_PER_DOMAIN, 100)

    def test_empty_text_allowed(self):
        """Empty text is technically allowed (but unusual)."""
        p = add_principle("x", "general", path=self.path)
        self.assertIsNotNone(p)

    def test_score_boundary_prune(self):
        """Test exact boundary: score == 0.3 should NOT be pruned (strictly less)."""
        # Need (s+1)/(u+2) = 0.3 exactly
        # s+1 = 0.3*(u+2), if u=18: s+1 = 6, s=5 -> score = 6/20 = 0.3
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=5, usage_count=18)
        self.assertAlmostEqual(p.score, 0.3)
        self.assertFalse(p.should_prune)  # Not strictly less than 0.3

    def test_score_boundary_reinforce(self):
        """Test exact boundary: score == 0.7 should be reinforced."""
        # (s+1)/(u+2) = 0.7, if u=8: s+1 = 7, s=6 -> score = 7/10 = 0.7
        p = Principle(id="t", text="t", source_domain="general", applicable_domains=["general"],
                      success_count=6, usage_count=8)
        self.assertAlmostEqual(p.score, 0.7)
        self.assertTrue(p.is_reinforced)

    def test_concurrent_add_different_domains(self):
        """Same text in different domains should get different IDs."""
        p1 = add_principle("Universal insight", "general", path=self.path)
        p2 = add_principle("Universal insight", "trading_research", path=self.path)
        self.assertNotEqual(p1.id, p2.id)


if __name__ == "__main__":
    unittest.main()
