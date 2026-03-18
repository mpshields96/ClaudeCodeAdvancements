#!/usr/bin/env python3
"""Tests for nuclear_fetcher.py — the batch Reddit post fetcher and classifier."""

import unittest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nuclear_fetcher import (
    classify_post, load_findings_urls, subreddit_slug,
    _parse_posts, _paginate_listing, fetch_hot_posts, fetch_rising_posts,
)


class TestClassifyPost(unittest.TestCase):
    """Test the NEEDLE/MAYBE/HAY triage classifier."""

    def _post(self, title="Test Post", score=200, comments=50, flair="",
              is_self=True, body_len=1000):
        return {
            "id": "abc123",
            "title": title,
            "author": "testuser",
            "score": score,
            "upvote_ratio": 0.95,
            "num_comments": comments,
            "flair": flair,
            "is_self": is_self,
            "selftext_length": body_len,
            "url": "https://reddit.com/r/ClaudeCode/comments/abc123/",
            "permalink": "https://reddit.com/r/ClaudeCode/comments/abc123/",
        }

    # --- HAY tests ---

    def test_humor_flair_is_hay(self):
        p = self._post(title="When Claude writes tests", flair="humor")
        self.assertEqual(classify_post(p), "HAY")

    def test_meme_flair_is_hay(self):
        p = self._post(title="Average vibe coder", flair="meme")
        self.assertEqual(classify_post(p), "HAY")

    def test_humor_keyword_in_title(self):
        p = self._post(title="This is so funny lmao")
        self.assertEqual(classify_post(p), "HAY")

    def test_rant_flair_is_hay(self):
        p = self._post(title="Tired of Claude", flair="rant")
        self.assertEqual(classify_post(p), "HAY")

    def test_gpt_vs_claude_is_hay(self):
        p = self._post(title="GPT vs Claude: which is better for coding?")
        self.assertEqual(classify_post(p), "HAY")

    def test_switching_is_hay(self):
        p = self._post(title="Switching to Cursor, goodbye Claude")
        self.assertEqual(classify_post(p), "HAY")

    def test_jailbreak_is_hay(self):
        p = self._post(title="New jailbreak technique for Claude 4")
        self.assertEqual(classify_post(p), "HAY")

    def test_link_post_no_body_low_score_is_hay(self):
        p = self._post(title="Check this out", score=50, is_self=False, body_len=0)
        self.assertEqual(classify_post(p), "HAY")

    def test_first_time_using_is_hay(self):
        p = self._post(title="First time using Claude Code — WOW")
        self.assertEqual(classify_post(p), "HAY")

    def test_pricing_is_hay(self):
        p = self._post(title="How much do you spend on Claude monthly?")
        self.assertEqual(classify_post(p), "HAY")

    def test_cancelling_is_hay(self):
        p = self._post(title="I'm cancelling my subscription")
        self.assertEqual(classify_post(p), "HAY")

    # --- NEEDLE tests ---

    def test_claude_md_keyword_is_needle(self):
        p = self._post(title="How I organized my CLAUDE.md for maximum effect")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_hook_keyword_is_needle(self):
        p = self._post(title="Built a PreToolUse hook for credential guard")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_mcp_server_is_needle(self):
        p = self._post(title="My custom MCP server for project memory")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_context_window_is_needle(self):
        p = self._post(title="How to manage context window in long sessions")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_multi_agent_is_needle(self):
        p = self._post(title="Running parallel agents without file conflicts")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_showcase_flair_high_score(self):
        p = self._post(title="Something I built", flair="showcase", score=150)
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_tutorial_flair_high_score(self):
        p = self._post(title="How to do X", flair="tutorial / guide", score=200)
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_substantive_self_post(self):
        p = self._post(title="My complete setup for X", score=300, body_len=2000)
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_high_engagement(self):
        p = self._post(title="Something interesting", score=200, comments=80)
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_built_keyword_is_needle(self):
        p = self._post(title="I built a tool for tracking Claude token usage")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_tips_keyword_is_needle(self):
        p = self._post(title="My best tips after 6 months with Claude Code")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_tmux_keyword_is_needle(self):
        p = self._post(title="tmux setup for managing multiple Claude sessions")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_self_learning_is_needle(self):
        p = self._post(title="Self-learning agent architecture for autonomous coding")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_workflow_keyword_is_needle(self):
        p = self._post(title="My automation workflow for Claude Code development")
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_dashboard_is_needle(self):
        p = self._post(title="Built a dashboard to monitor Claude sessions")
        self.assertEqual(classify_post(p), "NEEDLE")

    # --- MAYBE tests ---

    def test_generic_discussion_is_maybe(self):
        p = self._post(title="Thoughts on the latest update?", score=80,
                        comments=20, flair="", body_len=200)
        self.assertEqual(classify_post(p), "MAYBE")

    def test_low_score_no_keywords(self):
        p = self._post(title="Has anyone tried this approach?", score=40,
                        comments=10, body_len=300)
        self.assertEqual(classify_post(p), "MAYBE")


class TestLoadFindingsUrls(unittest.TestCase):
    """Test deduplication against FINDINGS_LOG."""

    def test_extracts_post_ids(self):
        content = (
            "[2026-03-15] [BUILD] test — https://www.reddit.com/r/ClaudeCode/comments/abc123/\n"
            "[2026-03-15] [SKIP] test — https://www.reddit.com/r/ClaudeAI/comments/xyz789/\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            ids = load_findings_urls(f.name)
        os.unlink(f.name)
        self.assertIn("abc123", ids)
        self.assertIn("xyz789", ids)

    def test_missing_file_returns_empty(self):
        ids = load_findings_urls("/nonexistent/path.md")
        self.assertEqual(ids, set())

    def test_empty_file_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("")
            f.flush()
            ids = load_findings_urls(f.name)
        os.unlink(f.name)
        self.assertEqual(ids, set())

    def test_no_reddit_urls_returns_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("[2026-03-15] [BUILD] test — https://github.com/foo/bar\n")
            f.flush()
            ids = load_findings_urls(f.name)
        os.unlink(f.name)
        self.assertEqual(ids, set())


class TestClassifyEdgeCases(unittest.TestCase):
    """Edge cases for the classifier."""

    def _post(self, **kwargs):
        base = {
            "id": "test", "title": "Test", "author": "u", "score": 100,
            "upvote_ratio": 0.9, "num_comments": 30, "flair": "",
            "is_self": True, "selftext_length": 500, "url": "", "permalink": "",
        }
        base.update(kwargs)
        return base

    def test_hay_keyword_overrides_high_score(self):
        """Even 5000pts humor is still hay."""
        p = self._post(title="This is so funny lmao", score=5000)
        self.assertEqual(classify_post(p), "HAY")

    def test_needle_keyword_with_low_score(self):
        """Needle keywords work even at lower scores."""
        p = self._post(title="My CLAUDE.md organization", score=30)
        self.assertEqual(classify_post(p), "NEEDLE")

    def test_empty_flair_doesnt_crash(self):
        p = self._post(flair="")
        result = classify_post(p)
        self.assertIn(result, ("NEEDLE", "MAYBE", "HAY"))

    def test_none_flair_doesnt_crash(self):
        p = self._post(flair=None)
        result = classify_post(p)
        self.assertIn(result, ("NEEDLE", "MAYBE", "HAY"))


class TestSubredditSlug(unittest.TestCase):
    """Test subreddit name to filesystem slug conversion."""

    def test_r_prefix_stripped(self):
        self.assertEqual(subreddit_slug("r/ClaudeCode"), "claudecode")

    def test_slash_r_prefix_stripped(self):
        self.assertEqual(subreddit_slug("/r/ClaudeCode"), "claudecode")

    def test_no_prefix(self):
        self.assertEqual(subreddit_slug("ClaudeAI"), "claudeai")

    def test_lowercase(self):
        self.assertEqual(subreddit_slug("r/LocalLLaMA"), "localllama")

    def test_underscores_stripped(self):
        self.assertEqual(subreddit_slug("r/Machine_Learning"), "machinelearning")

    def test_whitespace_stripped(self):
        self.assertEqual(subreddit_slug("  r/ClaudeCode  "), "claudecode")

    def test_hyphens_stripped(self):
        self.assertEqual(subreddit_slug("r/vibe-coding"), "vibecoding")

    def test_default_claudecode(self):
        """The most common case."""
        self.assertEqual(subreddit_slug("r/ClaudeCode"), "claudecode")


class TestParsePosts(unittest.TestCase):
    """Test the _parse_posts helper."""

    def test_parses_standard_children(self):
        children = [
            {"data": {
                "id": "abc", "title": "Test", "author": "user1",
                "score": 100, "upvote_ratio": 0.9, "num_comments": 10,
                "created_utc": 1710000000, "link_flair_text": "Discussion",
                "is_self": True, "url": "https://reddit.com/r/test/abc",
                "permalink": "/r/test/comments/abc/test/",
                "selftext": "body text",
            }},
        ]
        result = _parse_posts(children, "test")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "abc")
        self.assertEqual(result[0]["score"], 100)
        self.assertEqual(result[0]["flair"], "Discussion")
        self.assertEqual(result[0]["selftext_length"], len("body text"))

    def test_empty_children(self):
        self.assertEqual(_parse_posts([], "test"), [])

    def test_deleted_author_becomes_deleted(self):
        children = [{"data": {"id": "x", "title": "t", "author": None,
                               "score": 1, "upvote_ratio": 0.5, "num_comments": 0,
                               "created_utc": 0, "is_self": True, "url": "", "permalink": ""}}]
        result = _parse_posts(children, "test")
        self.assertEqual(result[0]["author"], "[deleted]")

    def test_missing_flair_becomes_empty_string(self):
        children = [{"data": {"id": "x", "title": "t", "author": "u",
                               "score": 1, "upvote_ratio": 0.5, "num_comments": 0,
                               "created_utc": 0, "is_self": True, "url": "", "permalink": "",
                               "link_flair_text": None}}]
        result = _parse_posts(children, "test")
        self.assertEqual(result[0]["flair"], "")

    def test_permalink_gets_base_url(self):
        children = [{"data": {"id": "x", "title": "t", "author": "u",
                               "score": 1, "upvote_ratio": 0.5, "num_comments": 0,
                               "created_utc": 0, "is_self": True, "url": "",
                               "permalink": "/r/test/comments/x/title/"}}]
        result = _parse_posts(children, "test")
        self.assertTrue(result[0]["permalink"].startswith("https://www.reddit.com"))


class TestFetchHotRisingSignatures(unittest.TestCase):
    """Test that fetch_hot_posts and fetch_rising_posts have correct signatures."""

    def test_fetch_hot_posts_callable(self):
        self.assertTrue(callable(fetch_hot_posts))

    def test_fetch_rising_posts_callable(self):
        self.assertTrue(callable(fetch_rising_posts))

    def test_fetch_hot_accepts_limit(self):
        import inspect
        sig = inspect.signature(fetch_hot_posts)
        self.assertIn("limit", sig.parameters)

    def test_fetch_rising_accepts_limit(self):
        import inspect
        sig = inspect.signature(fetch_rising_posts)
        self.assertIn("limit", sig.parameters)

    def test_fetch_hot_default_limit(self):
        import inspect
        sig = inspect.signature(fetch_hot_posts)
        self.assertEqual(sig.parameters["limit"].default, 50)

    def test_fetch_rising_default_limit(self):
        import inspect
        sig = inspect.signature(fetch_rising_posts)
        self.assertEqual(sig.parameters["limit"].default, 25)


if __name__ == "__main__":
    unittest.main()
