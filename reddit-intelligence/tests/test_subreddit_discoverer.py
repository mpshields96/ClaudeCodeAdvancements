#!/usr/bin/env python3
"""Tests for subreddit_discoverer.py."""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from subreddit_discoverer import (
    SubredditCandidate,
    DOMAIN_QUERIES,
    _already_tracked_slugs,
    _score_relevance,
    discover_subreddits,
)


class TestDomainQueries(unittest.TestCase):
    """Test domain configuration."""

    def test_all_domains_have_required_keys(self):
        for domain, config in DOMAIN_QUERIES.items():
            self.assertIn("description", config, f"{domain} missing description")
            self.assertIn("search_terms", config, f"{domain} missing search_terms")
            self.assertIn("relevance_keywords", config, f"{domain} missing relevance_keywords")

    def test_all_domains_have_search_terms(self):
        for domain, config in DOMAIN_QUERIES.items():
            self.assertGreater(len(config["search_terms"]), 0, f"{domain} has no search terms")

    def test_all_domains_have_keywords(self):
        for domain, config in DOMAIN_QUERIES.items():
            self.assertGreater(len(config["relevance_keywords"]), 0, f"{domain} has no keywords")

    def test_expected_domains_exist(self):
        self.assertIn("claude", DOMAIN_QUERIES)
        self.assertIn("trading", DOMAIN_QUERIES)
        self.assertIn("research", DOMAIN_QUERIES)
        self.assertIn("dev", DOMAIN_QUERIES)


class TestAlreadyTrackedSlugs(unittest.TestCase):
    """Test tracked subreddit detection."""

    def test_returns_set(self):
        result = _already_tracked_slugs()
        self.assertIsInstance(result, set)

    def test_includes_known_profiles(self):
        result = _already_tracked_slugs()
        self.assertIn("claudecode", result)
        self.assertIn("claudeai", result)
        self.assertIn("algotrading", result)

    def test_nonempty(self):
        result = _already_tracked_slugs()
        self.assertGreater(len(result), 5)


class TestScoreRelevance(unittest.TestCase):
    """Test relevance scoring."""

    def test_high_relevance_sub(self):
        sub_data = {
            "public_description": "A community for Claude Code AI agent development and automation",
            "description": "Tools, hooks, MCP servers, and workflows for Claude",
            "display_name": "ClaudeCodeTools",
            "title": "Claude Code Tools",
            "subscribers": 50000,
            "accounts_active": 500,
            "created_utc": datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp(),
        }
        score = _score_relevance(sub_data, DOMAIN_QUERIES["claude"]["relevance_keywords"])
        self.assertGreater(score, 40)

    def test_low_relevance_sub(self):
        sub_data = {
            "public_description": "Pictures of cats",
            "description": "Cute cat photos only",
            "display_name": "CatPhotos",
            "title": "Cat Photos",
            "subscribers": 1000000,
            "accounts_active": 5000,
            "created_utc": datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp(),
        }
        score = _score_relevance(sub_data, DOMAIN_QUERIES["claude"]["relevance_keywords"])
        self.assertLess(score, 55)  # Some score from subs/activity but low keyword match

    def test_zero_subscribers(self):
        sub_data = {
            "public_description": "", "description": "",
            "display_name": "Empty", "title": "",
            "subscribers": 0, "accounts_active": 0, "created_utc": 0,
        }
        score = _score_relevance(sub_data, ["test"])
        self.assertGreaterEqual(score, 0)

    def test_keyword_matching_case_insensitive(self):
        sub_data = {
            "public_description": "CLAUDE AGENT AUTOMATION WORKFLOW",
            "description": "", "display_name": "Test", "title": "",
            "subscribers": 10000, "accounts_active": 100, "created_utc": 0,
        }
        score = _score_relevance(sub_data, ["claude", "agent", "automation"])
        self.assertGreater(score, 30)


class TestSubredditCandidate(unittest.TestCase):
    """Test SubredditCandidate dataclass."""

    def _make_candidate(self, **kwargs):
        defaults = dict(
            name="test", display_name="Test", subscribers=10000,
            description="desc", public_description="pub desc",
            active_accounts=100, created_utc=datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp(),
            url="https://www.reddit.com/r/Test/", over18=False,
            domain="claude", relevance_score=75.0, already_tracked=False,
        )
        defaults.update(kwargs)
        return SubredditCandidate(**defaults)

    def test_to_dict(self):
        c = self._make_candidate()
        d = c.to_dict()
        self.assertIn("name", d)
        self.assertIn("relevance_score", d)
        self.assertIn("age_days", d)

    def test_age_days(self):
        c = self._make_candidate()
        self.assertGreater(c.age_days(), 0)

    def test_age_days_zero_created(self):
        c = self._make_candidate(created_utc=0)
        self.assertEqual(c.age_days(), 0)

    def test_profile_proposal(self):
        c = self._make_candidate(display_name="AIAgents", subscribers=50000)
        proposal = c.profile_proposal()
        self.assertIn("aiagents", proposal)
        self.assertIn("SubredditProfile", proposal)
        self.assertIn("claude", proposal)  # domain

    def test_profile_proposal_scaling(self):
        # Small sub = lower min_score
        small = self._make_candidate(subscribers=5000)
        large = self._make_candidate(subscribers=500000)
        self.assertIn("min_score=20", small.profile_proposal())
        self.assertIn("min_score=50", large.profile_proposal())


class TestDiscoverSubreddits(unittest.TestCase):
    """Test discovery with mocked API calls."""

    def _mock_response(self, subreddits):
        """Create a mock Reddit API response."""
        children = []
        for sub in subreddits:
            children.append({
                "data": {
                    "display_name": sub["name"],
                    "subscribers": sub.get("subs", 10000),
                    "public_description": sub.get("desc", ""),
                    "description": sub.get("desc", ""),
                    "title": sub.get("name", ""),
                    "accounts_active": sub.get("active", 100),
                    "created_utc": datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp(),
                    "over18": sub.get("nsfw", False),
                }
            })
        return {"data": {"children": children}}

    @patch("subreddit_discoverer._fetch_json")
    @patch("subreddit_discoverer.time.sleep")  # Don't actually sleep in tests
    def test_basic_discovery(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = self._mock_response([
            {"name": "NewAISub", "subs": 50000, "desc": "AI agent tools and Claude code"},
        ])
        results = discover_subreddits(domains=["claude"], top_n=5)
        self.assertGreater(len(results), 0)
        self.assertIsInstance(results[0], SubredditCandidate)

    @patch("subreddit_discoverer._fetch_json")
    @patch("subreddit_discoverer.time.sleep")
    def test_filters_nsfw(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = self._mock_response([
            {"name": "NSFWSub", "subs": 50000, "desc": "test", "nsfw": True},
        ])
        results = discover_subreddits(domains=["claude"], top_n=5)
        nsfw = [r for r in results if r.display_name == "NSFWSub"]
        self.assertEqual(len(nsfw), 0)

    @patch("subreddit_discoverer._fetch_json")
    @patch("subreddit_discoverer.time.sleep")
    def test_filters_tiny_subs(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = self._mock_response([
            {"name": "TinySub", "subs": 50, "desc": "too small"},
        ])
        results = discover_subreddits(domains=["claude"], top_n=5, min_subscribers=1000)
        tiny = [r for r in results if r.display_name == "TinySub"]
        self.assertEqual(len(tiny), 0)

    @patch("subreddit_discoverer._fetch_json")
    @patch("subreddit_discoverer.time.sleep")
    def test_deduplicates(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = self._mock_response([
            {"name": "DupeSub", "subs": 50000, "desc": "test"},
            {"name": "DupeSub", "subs": 50000, "desc": "test"},
        ])
        results = discover_subreddits(domains=["claude"], top_n=10)
        dupe_count = sum(1 for r in results if r.display_name == "DupeSub")
        self.assertLessEqual(dupe_count, 1)

    @patch("subreddit_discoverer._fetch_json")
    @patch("subreddit_discoverer.time.sleep")
    def test_marks_tracked_subs(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = self._mock_response([
            {"name": "ClaudeCode", "subs": 100000, "desc": "Claude Code"},
        ])
        results = discover_subreddits(domains=["claude"], top_n=5)
        tracked = [r for r in results if r.display_name == "ClaudeCode"]
        if tracked:
            self.assertTrue(tracked[0].already_tracked)

    @patch("subreddit_discoverer._fetch_json")
    @patch("subreddit_discoverer.time.sleep")
    def test_sorted_by_relevance(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = self._mock_response([
            {"name": "LowRel", "subs": 5000, "desc": "cats"},
            {"name": "HighRel", "subs": 100000, "desc": "Claude AI agent automation workflow MCP hook"},
        ])
        results = discover_subreddits(domains=["claude"], top_n=10)
        if len(results) >= 2:
            self.assertGreaterEqual(results[0].relevance_score, results[1].relevance_score)

    @patch("subreddit_discoverer._fetch_json")
    @patch("subreddit_discoverer.time.sleep")
    def test_respects_top_n(self, mock_sleep, mock_fetch):
        subs = [{"name": f"Sub{i}", "subs": 10000, "desc": "test"} for i in range(20)]
        mock_fetch.return_value = self._mock_response(subs)
        results = discover_subreddits(domains=["claude"], top_n=3)
        self.assertLessEqual(len(results), 3)

    @patch("subreddit_discoverer._fetch_json")
    @patch("subreddit_discoverer.time.sleep")
    def test_handles_api_failure(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = None
        results = discover_subreddits(domains=["claude"], top_n=5)
        self.assertEqual(len(results), 0)

    def test_invalid_domain_ignored(self):
        # Should not crash on unknown domain
        with patch("subreddit_discoverer._fetch_json") as mock_fetch, \
             patch("subreddit_discoverer.time.sleep"):
            mock_fetch.return_value = None
            results = discover_subreddits(domains=["nonexistent"], top_n=5)
            self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
