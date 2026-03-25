#!/usr/bin/env python3
"""Tests for github_scanner.py discover functionality (RepoDiscoverer + RepoCandidate)."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from github_scanner import (
    RepoCandidate,
    RepoDiscoverer,
    RepoMetadata,
    EvaluationResult,
    DISCOVERY_QUERIES,
    FRONTIER_KEYWORDS,
    cli_main,
)


class TestDiscoveryQueries(unittest.TestCase):
    """Test domain query configuration."""

    def test_all_domains_have_required_keys(self):
        for domain, config in DISCOVERY_QUERIES.items():
            self.assertIn("description", config, f"{domain} missing description")
            self.assertIn("queries", config, f"{domain} missing queries")

    def test_all_domains_have_queries(self):
        for domain, config in DISCOVERY_QUERIES.items():
            self.assertGreater(len(config["queries"]), 0, f"{domain} has no queries")

    def test_expected_domains_exist(self):
        self.assertIn("claude", DISCOVERY_QUERIES)
        self.assertIn("trading", DISCOVERY_QUERIES)
        self.assertIn("research", DISCOVERY_QUERIES)
        self.assertIn("dev", DISCOVERY_QUERIES)

    def test_min_stars_is_reasonable(self):
        for domain, config in DISCOVERY_QUERIES.items():
            min_stars = config.get("min_stars", 5)
            self.assertGreaterEqual(min_stars, 1)
            self.assertLessEqual(min_stars, 100)


class TestRepoCandidate(unittest.TestCase):
    """Test RepoCandidate dataclass."""

    def _make_candidate(self, **kwargs):
        defaults = dict(
            full_name="owner/repo",
            description="A test repo",
            stars=100,
            language="Python",
            license_id="MIT",
            days_since_push=5.0,
            topics=["ai", "claude"],
            url="https://github.com/owner/repo",
            domain="claude",
            eval_score=75.0,
            eval_verdict="EVALUATE",
            warnings=[],
        )
        defaults.update(kwargs)
        return RepoCandidate(**defaults)

    def test_to_dict(self):
        c = self._make_candidate()
        d = c.to_dict()
        self.assertIn("full_name", d)
        self.assertIn("eval_score", d)
        self.assertIn("domain", d)
        self.assertEqual(d["full_name"], "owner/repo")

    def test_to_dict_json_serializable(self):
        c = self._make_candidate()
        # Should not raise
        json.dumps(c.to_dict())

    def test_fields(self):
        c = self._make_candidate(stars=500, domain="trading")
        self.assertEqual(c.stars, 500)
        self.assertEqual(c.domain, "trading")


class TestRepoDiscoverer(unittest.TestCase):
    """Test RepoDiscoverer with mocked API."""

    def _make_meta(self, name="owner/repo", stars=100, desc="test", lang="Python", topics=None):
        return RepoMetadata(
            full_name=name,
            description=desc,
            stars=stars,
            forks=10,
            open_issues=5,
            language=lang,
            license_id="MIT",
            age_days=365.0,
            days_since_push=3.0,
            topics=topics or [],
            url=f"https://github.com/{name}",
            default_branch="main",
        )

    def _make_eval_result(self, score=70.0, verdict="EVALUATE"):
        return EvaluationResult(
            total=score,
            components={"stars": 20, "activity": 25, "license": 15, "relevance": 5, "age": 5},
            warnings=[],
            blocked=False,
            block_reason="",
            verdict=verdict,
        )

    @patch("github_scanner.search_repos")
    def test_basic_discovery(self, mock_search):
        meta = self._make_meta(name="test/claude-tools", stars=200, desc="Claude MCP tools")
        mock_search.return_value = [meta]

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        try:
            discoverer = RepoDiscoverer(eval_log_path=log_path)
            results = discoverer.discover(domains=["claude"], top_n=5, limit_per_query=3)
            self.assertGreater(len(results), 0)
            self.assertIsInstance(results[0], RepoCandidate)
        finally:
            os.unlink(log_path)

    @patch("github_scanner.search_repos")
    def test_deduplicates_repos(self, mock_search):
        meta = self._make_meta(name="owner/dupe-repo")
        mock_search.return_value = [meta, meta]  # Same repo returned twice

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        try:
            discoverer = RepoDiscoverer(eval_log_path=log_path)
            results = discoverer.discover(domains=["claude"], top_n=10, limit_per_query=5)
            names = [r.full_name for r in results]
            self.assertEqual(len(set(names)), len(names), "Duplicates found")
        finally:
            os.unlink(log_path)

    @patch("github_scanner.search_repos")
    def test_sorted_by_score(self, mock_search):
        meta1 = self._make_meta(name="owner/low", stars=5, desc="minimal")
        meta2 = self._make_meta(name="owner/high", stars=5000, desc="Claude AI agent MCP tools")
        mock_search.return_value = [meta1, meta2]

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        try:
            discoverer = RepoDiscoverer(eval_log_path=log_path)
            results = discoverer.discover(domains=["claude"], top_n=10, limit_per_query=5)
            if len(results) >= 2:
                self.assertGreaterEqual(results[0].eval_score, results[1].eval_score)
        finally:
            os.unlink(log_path)

    @patch("github_scanner.search_repos")
    def test_respects_top_n(self, mock_search):
        metas = [self._make_meta(name=f"owner/repo{i}") for i in range(15)]
        mock_search.return_value = metas

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        try:
            discoverer = RepoDiscoverer(eval_log_path=log_path)
            results = discoverer.discover(domains=["claude"], top_n=3, limit_per_query=10)
            self.assertLessEqual(len(results), 3)
        finally:
            os.unlink(log_path)

    @patch("github_scanner.search_repos")
    def test_handles_empty_results(self, mock_search):
        mock_search.return_value = []

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        try:
            discoverer = RepoDiscoverer(eval_log_path=log_path)
            results = discoverer.discover(domains=["claude"], top_n=5)
            self.assertEqual(len(results), 0)
        finally:
            os.unlink(log_path)

    def test_invalid_domain_ignored(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name
        try:
            discoverer = RepoDiscoverer(eval_log_path=log_path)
            with patch("github_scanner.search_repos", return_value=[]):
                results = discoverer.discover(domains=["nonexistent"], top_n=5)
                self.assertEqual(len(results), 0)
        finally:
            os.unlink(log_path)

    @patch("github_scanner.search_repos")
    def test_multi_domain_discovery(self, mock_search):
        meta1 = self._make_meta(name="owner/claude-tool", desc="Claude MCP")
        meta2 = self._make_meta(name="owner/trade-bot", desc="Trading bot")
        mock_search.side_effect = lambda q, **kw: [meta1] if "claude" in q else [meta2]

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name

        try:
            discoverer = RepoDiscoverer(eval_log_path=log_path)
            results = discoverer.discover(domains=["claude", "trading"], top_n=10, limit_per_query=3)
            domains_found = {r.domain for r in results}
            # Should have results from at least one domain
            self.assertGreater(len(results), 0)
        finally:
            os.unlink(log_path)


class TestDiscoverCLI(unittest.TestCase):
    """Test the discover CLI command."""

    @patch("github_scanner.search_repos")
    def test_cli_discover_help(self, mock_search):
        # Should not crash
        cli_main(["discover", "--help"])

    @patch("github_scanner.search_repos")
    def test_cli_discover_no_results(self, mock_search):
        mock_search.return_value = []
        cli_main(["discover", "--domain", "claude", "--top", "5"])


if __name__ == "__main__":
    unittest.main()
