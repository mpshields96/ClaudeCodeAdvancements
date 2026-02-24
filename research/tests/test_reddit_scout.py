#!/usr/bin/env python3
"""
Tests for research/reddit_scout.py
Tests scoring, filtering, and output logic only — no live Reddit calls.
Run: python3 research/tests/test_reddit_scout.py
"""

import json
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from reddit_scout import (
    relevance_score,
    is_rat_poison,
    extract_idea,
    map_to_frontier,
    run_scout,
    save_findings,
    format_summary,
    RELEVANCE_KEYWORDS,
    RAT_POISON_KEYWORDS,
)


def make_post(title="", selftext="", score=100, num_comments=10, permalink="/r/test/comments/abc"):
    return {
        "title": title,
        "selftext": selftext,
        "score": score,
        "num_comments": num_comments,
        "permalink": permalink,
    }


class TestRelevanceScore(unittest.TestCase):
    def test_zero_for_unrelated_post(self):
        post = make_post(title="I love cooking pasta", selftext="Here is a recipe")
        self.assertEqual(relevance_score(post), 0)

    def test_nonzero_for_memory_post(self):
        post = make_post(title="How do I make Claude remember things across sessions?")
        self.assertGreater(relevance_score(post), 0)

    def test_nonzero_for_context_post(self):
        post = make_post(title="Claude Code context window keeps hitting limit")
        self.assertGreater(relevance_score(post), 0)

    def test_counts_multiple_keywords(self):
        post = make_post(title="Claude Code memory and token cost and context limit")
        score = relevance_score(post)
        self.assertGreater(score, 2)

    def test_case_insensitive(self):
        post = make_post(title="MEMORY and SESSION issues with Claude")
        self.assertGreater(relevance_score(post), 0)

    def test_selftext_also_checked(self):
        post = make_post(title="Question", selftext="I have a context window problem")
        self.assertGreater(relevance_score(post), 0)


class TestRatPoison(unittest.TestCase):
    def test_install_flagged(self):
        post = make_post(title="pip install this amazing memory tool")
        self.assertTrue(is_rat_poison(post))

    def test_credentials_flagged(self):
        post = make_post(selftext="paste your api key here to get started")
        self.assertTrue(is_rat_poison(post))

    def test_clean_post_not_flagged(self):
        post = make_post(title="How to use Claude Code memory patterns effectively")
        self.assertFalse(is_rat_poison(post))

    def test_jailbreak_flagged(self):
        post = make_post(title="How to jailbreak Claude for unlimited context")
        self.assertTrue(is_rat_poison(post))

    def test_clone_flagged(self):
        post = make_post(selftext="just clone this repo and run it")
        self.assertTrue(is_rat_poison(post))


class TestExtractIdea(unittest.TestCase):
    def test_contains_title(self):
        post = make_post(title="Persistent memory across Claude sessions", score=500)
        idea = extract_idea(post)
        self.assertIn("Persistent memory across Claude sessions", idea)

    def test_contains_upvotes(self):
        post = make_post(title="Test", score=234)
        idea = extract_idea(post)
        self.assertIn("234", idea)

    def test_contains_reddit_url(self):
        post = make_post(title="Test", permalink="/r/ClaudeAI/comments/xyz/test/")
        idea = extract_idea(post)
        self.assertIn("reddit.com", idea)


class TestMapToFrontier(unittest.TestCase):
    def test_memory_post(self):
        post = make_post(title="Claude always forgets everything between sessions, memory issue")
        self.assertEqual(map_to_frontier(post), "memory-system")

    def test_context_post(self):
        post = make_post(title="hitting context window limit constantly, compaction problem")
        self.assertEqual(map_to_frontier(post), "context-monitor")

    def test_cost_post(self):
        post = make_post(title="Claude Code billing and token usage is out of control")
        self.assertEqual(map_to_frontier(post), "usage-dashboard")

    def test_agent_post(self):
        post = make_post(title="running parallel multi-agent Claude worktree sessions")
        self.assertEqual(map_to_frontier(post), "agent-guard")

    def test_unrelated_returns_general(self):
        post = make_post(title="hello world")
        self.assertEqual(map_to_frontier(post), "general")


class TestRunScout(unittest.TestCase):
    def _fake_fetch(self, subreddit, dry_run=False):
        return [
            make_post(title="Claude memory keeps resetting every session", score=300),
            make_post(title="pip install claude-memory-tool for persistent memory", score=50),
            make_post(title="Best pasta recipe", score=1000),
        ]

    def test_relevant_posts_captured(self):
        with patch("reddit_scout.fetch_subreddit", self._fake_fetch):
            findings = run_scout(dry_run=True)
        ideas = [e["idea"] for e in findings["relevant"]]
        self.assertTrue(any("memory" in i.lower() for i in ideas))

    def test_rat_poison_separated(self):
        with patch("reddit_scout.fetch_subreddit", self._fake_fetch):
            findings = run_scout(dry_run=True)
        poison_ideas = [e["idea"] for e in findings["rat_poison_flagged"]]
        self.assertTrue(any("pip install" in i for i in poison_ideas))

    def test_unrelated_posts_excluded(self):
        with patch("reddit_scout.fetch_subreddit", self._fake_fetch):
            findings = run_scout(dry_run=True)
        all_ideas = [e["idea"] for e in findings["relevant"]]
        self.assertFalse(any("pasta" in i.lower() for i in all_ideas))

    def test_stats_present(self):
        with patch("reddit_scout.fetch_subreddit", self._fake_fetch):
            findings = run_scout(dry_run=True)
        self.assertIn("stats", findings)
        for sub in findings["subreddits_checked"]:
            self.assertIn(sub, findings["stats"])

    def test_relevant_sorted_by_upvotes(self):
        def fetch_ordered(sub, dry_run=False):
            return [
                make_post(title="Claude memory issue", score=100),
                make_post(title="Claude token cost problem", score=500),
            ]
        with patch("reddit_scout.fetch_subreddit", fetch_ordered):
            findings = run_scout(dry_run=True)
        if len(findings["relevant"]) >= 2:
            self.assertGreaterEqual(
                findings["relevant"][0]["upvotes"],
                findings["relevant"][1]["upvotes"]
            )


class TestSaveFindings(unittest.TestCase):
    def _make_findings(self):
        return {
            "generated_at": "2026-02-20T10:00:00Z",
            "subreddits_checked": ["ClaudeAI"],
            "relevant": [{"subreddit": "ClaudeAI", "frontier": "memory-system",
                          "relevance_score": 2, "idea": "test idea", "upvotes": 100,
                          "rat_poison": False}],
            "rat_poison_flagged": [],
            "stats": {"ClaudeAI": {"posts_checked": 25, "relevant": 1, "rat_poison_flagged": 0}}
        }

    def test_saves_to_dated_file(self):
        findings = self._make_findings()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("reddit_scout.FINDINGS_DIR", Path(tmpdir)):
                out = save_findings(findings)
            self.assertTrue(out.exists())
            saved = json.loads(out.read_text())
            self.assertEqual(len(saved["relevant"]), 1)

    def test_merges_with_existing_file(self):
        findings1 = self._make_findings()
        findings2 = self._make_findings()
        findings2["relevant"][0]["idea"] = "second idea"
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("reddit_scout.FINDINGS_DIR", Path(tmpdir)):
                save_findings(findings1)
                save_findings(findings2)
                files = list(Path(tmpdir).glob("*.json"))
                saved = json.loads(files[0].read_text())
        self.assertEqual(len(saved["relevant"]), 2)

    def test_no_duplicate_ideas_on_merge(self):
        findings = self._make_findings()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("reddit_scout.FINDINGS_DIR", Path(tmpdir)):
                save_findings(findings)
                save_findings(findings)  # same ideas
                files = list(Path(tmpdir).glob("*.json"))
                saved = json.loads(files[0].read_text())
        self.assertEqual(len(saved["relevant"]), 1)


class TestFormatSummary(unittest.TestCase):
    def test_contains_subreddit_names(self):
        findings = {
            "generated_at": "2026-02-20T10:00:00Z",
            "subreddits_checked": ["ClaudeAI", "ClaudeCode"],
            "relevant": [],
            "rat_poison_flagged": [],
            "stats": {
                "ClaudeAI": {"posts_checked": 25, "relevant": 0, "rat_poison_flagged": 0},
                "ClaudeCode": {"posts_checked": 25, "relevant": 0, "rat_poison_flagged": 0},
            }
        }
        summary = format_summary(findings)
        self.assertIn("ClaudeAI", summary)
        self.assertIn("ClaudeCode", summary)

    def test_rat_poison_section_shown_when_present(self):
        findings = {
            "generated_at": "2026-02-20T10:00:00Z",
            "subreddits_checked": ["ClaudeAI"],
            "relevant": [],
            "rat_poison_flagged": [
                {"subreddit": "ClaudeAI", "idea": "pip install bad thing", "upvotes": 5}
            ],
            "stats": {"ClaudeAI": {"posts_checked": 25, "relevant": 0, "rat_poison_flagged": 1}}
        }
        summary = format_summary(findings)
        self.assertIn("RAT POISON", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
