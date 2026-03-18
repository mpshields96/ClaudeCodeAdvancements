#!/usr/bin/env python3
"""Tests for profiles.py — subreddit profiles, scan registry, and quick-scan mode."""

import unittest
import sys
import os
import json
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from profiles import (
    SubredditProfile,
    ScanRegistry,
    BUILTIN_PROFILES,
    get_profile,
    quick_scan_triage,
    merge_scout_nuclear,
)


class TestSubredditProfile(unittest.TestCase):
    """Test SubredditProfile dataclass and defaults."""

    def test_builtin_claudecode_exists(self):
        p = BUILTIN_PROFILES["claudecode"]
        self.assertEqual(p.subreddit, "ClaudeCode")
        self.assertGreater(p.min_score, 0)

    def test_builtin_claudeai_exists(self):
        p = BUILTIN_PROFILES["claudeai"]
        self.assertEqual(p.subreddit, "ClaudeAI")

    def test_builtin_algotrading_exists(self):
        p = BUILTIN_PROFILES["algotrading"]
        self.assertEqual(p.subreddit, "algotrading")

    def test_builtin_vibecoding_exists(self):
        p = BUILTIN_PROFILES["vibecoding"]
        self.assertEqual(p.subreddit, "vibecoding")

    def test_builtin_localllama_exists(self):
        p = BUILTIN_PROFILES["localllama"]
        self.assertEqual(p.subreddit, "LocalLLaMA")

    def test_builtin_machinelearning_exists(self):
        p = BUILTIN_PROFILES["machinelearning"]
        self.assertEqual(p.subreddit, "MachineLearning")

    def test_profile_has_required_fields(self):
        p = BUILTIN_PROFILES["claudecode"]
        self.assertIsInstance(p.subreddit, str)
        self.assertIsInstance(p.min_score, int)
        self.assertIsInstance(p.timeframe, str)
        self.assertIsInstance(p.limit, int)
        self.assertIsInstance(p.extra_needle_keywords, list)
        self.assertIsInstance(p.domain, str)

    def test_profile_timeframe_valid(self):
        valid = {"hour", "day", "week", "month", "year", "all"}
        for name, p in BUILTIN_PROFILES.items():
            self.assertIn(p.timeframe, valid, f"{name} has invalid timeframe")

    def test_profile_limit_reasonable(self):
        for name, p in BUILTIN_PROFILES.items():
            self.assertGreater(p.limit, 0, f"{name} limit must be > 0")
            self.assertLessEqual(p.limit, 200, f"{name} limit too high")

    def test_profile_domain_set(self):
        """Every profile must declare a domain for categorization."""
        for name, p in BUILTIN_PROFILES.items():
            self.assertIn(p.domain, ("claude", "trading", "dev", "research"),
                          f"{name} has unknown domain")


class TestGetProfile(unittest.TestCase):
    """Test profile lookup and auto-generation for unknown subs."""

    def test_known_sub_returns_builtin(self):
        p = get_profile("r/ClaudeCode")
        self.assertEqual(p.subreddit, "ClaudeCode")

    def test_known_sub_case_insensitive(self):
        p = get_profile("r/claudecode")
        self.assertEqual(p.subreddit, "ClaudeCode")

    def test_known_sub_without_prefix(self):
        p = get_profile("ClaudeCode")
        self.assertEqual(p.subreddit, "ClaudeCode")

    def test_unknown_sub_returns_default_profile(self):
        p = get_profile("r/SomeRandomSub")
        self.assertEqual(p.subreddit, "SomeRandomSub")
        self.assertIsInstance(p.min_score, int)
        self.assertIsInstance(p.timeframe, str)

    def test_unknown_sub_gets_conservative_defaults(self):
        p = get_profile("r/NeverHeardOfThis")
        self.assertGreaterEqual(p.min_score, 20)
        self.assertEqual(p.limit, 50)
        self.assertEqual(p.domain, "unknown")

    def test_slug_lookup_works(self):
        """Can look up by slug directly."""
        p = get_profile("localllama")
        self.assertEqual(p.subreddit, "LocalLLaMA")


class TestScanRegistry(unittest.TestCase):
    """Test scan registry — tracks last-scan timestamps per subreddit."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.reg = ScanRegistry(self.registry_path)

    def tearDown(self):
        if os.path.exists(self.registry_path):
            os.unlink(self.registry_path)
        os.rmdir(self.tmpdir)

    def test_new_registry_is_empty(self):
        self.assertEqual(self.reg.list_scans(), {})

    def test_record_scan(self):
        self.reg.record_scan("claudecode", posts_scanned=150, builds=3, adapts=5)
        scans = self.reg.list_scans()
        self.assertIn("claudecode", scans)
        self.assertEqual(scans["claudecode"]["posts_scanned"], 150)
        self.assertEqual(scans["claudecode"]["builds"], 3)

    def test_record_scan_persists(self):
        self.reg.record_scan("claudecode", posts_scanned=100, builds=1, adapts=2)
        reg2 = ScanRegistry(self.registry_path)
        self.assertIn("claudecode", reg2.list_scans())

    def test_record_overwrites_previous(self):
        self.reg.record_scan("claudecode", posts_scanned=100, builds=1, adapts=2)
        self.reg.record_scan("claudecode", posts_scanned=200, builds=5, adapts=10)
        scans = self.reg.list_scans()
        self.assertEqual(scans["claudecode"]["posts_scanned"], 200)

    def test_multiple_subs(self):
        self.reg.record_scan("claudecode", posts_scanned=100, builds=1, adapts=2)
        self.reg.record_scan("algotrading", posts_scanned=50, builds=0, adapts=3)
        scans = self.reg.list_scans()
        self.assertEqual(len(scans), 2)
        self.assertIn("claudecode", scans)
        self.assertIn("algotrading", scans)

    def test_is_stale_new_sub(self):
        """A never-scanned sub is always stale."""
        self.assertTrue(self.reg.is_stale("claudecode", max_age_days=14))

    def test_is_stale_recent_scan(self):
        self.reg.record_scan("claudecode", posts_scanned=100, builds=1, adapts=0)
        self.assertFalse(self.reg.is_stale("claudecode", max_age_days=14))

    def test_is_stale_old_scan(self):
        self.reg.record_scan("claudecode", posts_scanned=100, builds=1, adapts=0)
        # Hack the timestamp to be 15 days ago
        self.reg._data["claudecode"]["last_scan"] = (
            datetime.now(timezone.utc) - timedelta(days=15)
        ).isoformat()
        self.reg._save()
        self.assertTrue(self.reg.is_stale("claudecode", max_age_days=14))

    def test_stale_subs_returns_list(self):
        self.reg.record_scan("claudecode", posts_scanned=100, builds=1, adapts=0)
        self.reg.record_scan("algotrading", posts_scanned=50, builds=0, adapts=0)
        # Make algotrading stale
        self.reg._data["algotrading"]["last_scan"] = (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).isoformat()
        self.reg._save()
        stale = self.reg.stale_subs(max_age_days=14)
        self.assertIn("algotrading", stale)
        self.assertNotIn("claudecode", stale)

    def test_scan_history_recorded(self):
        self.reg.record_scan("claudecode", posts_scanned=100, builds=1, adapts=2)
        entry = self.reg.list_scans()["claudecode"]
        self.assertIn("last_scan", entry)
        self.assertIn("posts_scanned", entry)
        self.assertIn("builds", entry)
        self.assertIn("adapts", entry)

    def test_atomic_save(self):
        """Save should be atomic (tmp + rename)."""
        self.reg.record_scan("test", posts_scanned=10, builds=0, adapts=0)
        self.assertTrue(os.path.exists(self.registry_path))
        # No .tmp file should remain
        self.assertFalse(os.path.exists(self.registry_path + ".tmp"))

    def test_corrupt_file_handled(self):
        """Corrupt JSON should result in empty registry, not crash."""
        with open(self.registry_path, "w") as f:
            f.write("NOT VALID JSON{{{")
        reg = ScanRegistry(self.registry_path)
        self.assertEqual(reg.list_scans(), {})

    def test_yield_score(self):
        """yield_score = builds + adapts per 100 posts scanned."""
        self.reg.record_scan("claudecode", posts_scanned=100, builds=3, adapts=7)
        score = self.reg.yield_score("claudecode")
        self.assertAlmostEqual(score, 10.0)

    def test_yield_score_zero_posts(self):
        self.reg.record_scan("empty", posts_scanned=0, builds=0, adapts=0)
        self.assertEqual(self.reg.yield_score("empty"), 0.0)

    def test_yield_score_unknown_sub(self):
        self.assertEqual(self.reg.yield_score("neverscanned"), 0.0)


class TestQuickScanTriage(unittest.TestCase):
    """Test quick-scan mode: title-first triage, pick top N for deep read."""

    def _posts(self, n=30):
        """Generate n fake posts with varying scores."""
        return [
            {
                "id": f"post_{i}",
                "title": f"Test post {i} about generic things and ideas",
                "score": 90 - i,
                "num_comments": 5 + i,
                "flair": "",
                "is_self": True,
                "selftext_length": 200,
                "url": f"https://reddit.com/r/test/comments/post_{i}/",
                "permalink": f"/r/test/comments/post_{i}/",
                "subreddit": "test",
            }
            for i in range(n)
        ]

    def test_returns_subset(self):
        posts = self._posts(30)
        deep, skipped = quick_scan_triage(posts, deep_read_count=10)
        self.assertEqual(len(deep), 10)
        self.assertEqual(len(skipped), 20)

    def test_deep_read_sorted_by_score(self):
        posts = self._posts(20)
        deep, _ = quick_scan_triage(posts, deep_read_count=5)
        scores = [p["score"] for p in deep]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_needles_prioritized(self):
        """Posts classified as NEEDLE should be in deep-read even if lower score."""
        posts = self._posts(20)
        # Make a low-score post a NEEDLE
        posts[15]["title"] = "Built a custom MCP server for memory"
        posts[15]["score"] = 50
        deep, _ = quick_scan_triage(posts, deep_read_count=5)
        deep_ids = {p["id"] for p in deep}
        self.assertIn("post_15", deep_ids)

    def test_hay_excluded_from_deep(self):
        """HAY posts should never be in deep-read."""
        posts = self._posts(10)
        posts[0]["title"] = "This is so funny lmao"
        posts[0]["score"] = 9999
        deep, skipped = quick_scan_triage(posts, deep_read_count=5)
        deep_ids = {p["id"] for p in deep}
        self.assertNotIn("post_0", deep_ids)

    def test_empty_input(self):
        deep, skipped = quick_scan_triage([], deep_read_count=5)
        self.assertEqual(deep, [])
        self.assertEqual(skipped, [])

    def test_fewer_posts_than_deep_count(self):
        posts = self._posts(3)
        deep, skipped = quick_scan_triage(posts, deep_read_count=10)
        self.assertLessEqual(len(deep), 3)

    def test_default_deep_count(self):
        posts = self._posts(30)
        deep, _ = quick_scan_triage(posts)
        self.assertEqual(len(deep), 10)  # default

    # ── needle_ratio_cap tests ──────────────────────────────────────────────

    def test_needle_ratio_cap_demotes_excess(self):
        """When NEEDLE ratio exceeds cap, lowest-score NEEDLEs become MAYBE."""
        # Create 20 posts, all of which are NEEDLEs (titles with MCP keyword)
        posts = []
        for i in range(20):
            posts.append({
                "id": f"post_{i}",
                "title": f"Built a custom MCP server for feature {i}",
                "score": 100 + i,
                "num_comments": 10,
                "flair": "",
                "is_self": True,
                "selftext_length": 600,
                "url": f"https://reddit.com/r/test/comments/post_{i}/",
                "permalink": f"/r/test/comments/post_{i}/",
                "subreddit": "test",
            })
        # With 40% cap on 20 posts, max 8 NEEDLEs allowed
        deep, skipped = quick_scan_triage(posts, deep_read_count=20, needle_ratio_cap=0.4)
        # Deep should still get 20 posts (8 NEEDLEs + 12 demoted MAYBEs)
        # but the demoted ones have lower scores
        self.assertEqual(len(deep), 20)

    def test_needle_ratio_cap_preserves_highest_score(self):
        """When capping, the highest-score NEEDLEs should survive."""
        posts = []
        for i in range(10):
            posts.append({
                "id": f"post_{i}",
                "title": "MCP server implementation guide",
                "score": 50 + i * 10,  # scores: 50, 60, 70, ..., 140
                "num_comments": 10,
                "flair": "",
                "is_self": True,
                "selftext_length": 600,
                "url": f"https://reddit.com/r/test/comments/post_{i}/",
                "permalink": f"/r/test/comments/post_{i}/",
                "subreddit": "test",
            })
        # Cap at 30% → max 3 NEEDLEs out of 10 posts
        deep, skipped = quick_scan_triage(posts, deep_read_count=3, needle_ratio_cap=0.3)
        # The top 3 by score should be in deep (posts 7, 8, 9 with scores 120, 130, 140)
        deep_ids = {p["id"] for p in deep}
        self.assertIn("post_9", deep_ids)  # score 140
        self.assertIn("post_8", deep_ids)  # score 130
        self.assertIn("post_7", deep_ids)  # score 120

    def test_needle_ratio_cap_1_means_no_limit(self):
        """Cap of 1.0 should not demote any NEEDLEs."""
        posts = []
        for i in range(10):
            posts.append({
                "id": f"post_{i}",
                "title": "MCP server build guide",
                "score": 100 + i,
                "num_comments": 10,
                "flair": "",
                "is_self": True,
                "selftext_length": 600,
                "url": f"https://reddit.com/r/test/comments/post_{i}/",
                "permalink": f"/r/test/comments/post_{i}/",
                "subreddit": "test",
            })
        deep, _ = quick_scan_triage(posts, deep_read_count=10, needle_ratio_cap=1.0)
        self.assertEqual(len(deep), 10)

    def test_needle_ratio_cap_default_profile_has_field(self):
        """All profiles should have needle_ratio_cap field."""
        for slug, profile in BUILTIN_PROFILES.items():
            self.assertTrue(hasattr(profile, "needle_ratio_cap"),
                            f"Profile {slug} missing needle_ratio_cap")
            self.assertGreater(profile.needle_ratio_cap, 0)
            self.assertLessEqual(profile.needle_ratio_cap, 1.0)

    def test_investing_profile_has_tight_cap(self):
        """r/investing should have a tight needle_ratio_cap (<0.5) per SKILLBOOK S3."""
        p = BUILTIN_PROFILES["investing"]
        self.assertLess(p.needle_ratio_cap, 0.5)

    def test_localllama_profile_has_tight_cap(self):
        """r/LocalLLaMA should have a tight needle_ratio_cap per SKILLBOOK S3."""
        p = BUILTIN_PROFILES["localllama"]
        self.assertLess(p.needle_ratio_cap, 0.5)


class TestMergeScoutNuclear(unittest.TestCase):
    """Test the merge function that combines scout discovery with nuclear depth."""

    def test_merge_returns_dict(self):
        result = merge_scout_nuclear(
            subreddit="ClaudeCode",
            mode="quick",
            profile=get_profile("ClaudeCode"),
        )
        self.assertIsInstance(result, dict)
        self.assertIn("subreddit", result)
        self.assertIn("mode", result)
        self.assertIn("profile_name", result)

    def test_quick_mode_params(self):
        result = merge_scout_nuclear(
            subreddit="ClaudeCode",
            mode="quick",
            profile=get_profile("ClaudeCode"),
        )
        self.assertEqual(result["mode"], "quick")
        self.assertLessEqual(result["fetch_limit"], 50)
        self.assertLessEqual(result["deep_read_count"], 10)

    def test_full_mode_params(self):
        result = merge_scout_nuclear(
            subreddit="ClaudeCode",
            mode="full",
            profile=get_profile("ClaudeCode"),
        )
        self.assertEqual(result["mode"], "full")
        self.assertGreater(result["fetch_limit"], 50)

    def test_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            merge_scout_nuclear(
                subreddit="ClaudeCode",
                mode="invalid",
                profile=get_profile("ClaudeCode"),
            )

    def test_profile_settings_applied(self):
        profile = get_profile("algotrading")
        result = merge_scout_nuclear(
            subreddit="algotrading",
            mode="full",
            profile=profile,
        )
        self.assertEqual(result["min_score"], profile.min_score)
        self.assertEqual(result["timeframe"], profile.timeframe)


if __name__ == "__main__":
    unittest.main()
