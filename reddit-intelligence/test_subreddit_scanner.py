#!/usr/bin/env python3
"""Tests for subreddit_scanner.py — full subreddit absorption tool."""

import unittest
import json
import os
import sys
import tempfile

# Add parent dir so we can import
sys.path.insert(0, os.path.dirname(__file__))

from subreddit_scanner import (
    build_listing_url,
    parse_listing_response,
    PostSummary,
    filter_posts,
    format_post_table,
    ScanResult,
)


class TestBuildListingUrl(unittest.TestCase):
    """Test URL construction for Reddit JSON API."""

    def test_basic_new(self):
        url = build_listing_url("ClaudePlaysPokemon", sort="new")
        self.assertIn("/r/ClaudePlaysPokemon/new.json", url)
        self.assertIn("limit=100", url)
        self.assertIn("raw_json=1", url)

    def test_top_with_timeframe(self):
        url = build_listing_url("ClaudePlaysPokemon", sort="top", timeframe="all")
        self.assertIn("t=all", url)

    def test_pagination_token(self):
        url = build_listing_url("test", after="t3_abc123")
        self.assertIn("after=t3_abc123", url)

    def test_hot_default(self):
        url = build_listing_url("test")
        self.assertIn("/hot.json", url)

    def test_limit_capped_at_100(self):
        url = build_listing_url("test", limit=200)
        self.assertIn("limit=100", url)


class TestParseListingResponse(unittest.TestCase):
    """Test parsing of Reddit JSON listing responses."""

    def _make_response(self, posts, after=None):
        """Build a minimal Reddit listing response."""
        children = []
        for p in posts:
            children.append({
                "kind": "t3",
                "data": {
                    "id": p.get("id", "abc123"),
                    "title": p.get("title", "Test Post"),
                    "author": p.get("author", "testuser"),
                    "score": p.get("score", 10),
                    "num_comments": p.get("num_comments", 5),
                    "created_utc": p.get("created_utc", 1700000000),
                    "permalink": p.get("permalink", "/r/test/comments/abc123/test/"),
                    "subreddit": p.get("subreddit", "test"),
                    "is_self": p.get("is_self", True),
                    "selftext": p.get("selftext", ""),
                    "url": p.get("url", ""),
                    "link_flair_text": p.get("flair", None),
                    "upvote_ratio": p.get("upvote_ratio", 0.95),
                }
            })
        return {
            "data": {
                "children": children,
                "after": after,
                "before": None,
            }
        }

    def test_basic_parse(self):
        resp = self._make_response([
            {"id": "a1", "title": "Post 1", "score": 50, "num_comments": 10},
            {"id": "a2", "title": "Post 2", "score": 30, "num_comments": 5},
        ], after="t3_a2")
        posts, after_token = parse_listing_response(resp)
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].id, "a1")
        self.assertEqual(posts[0].title, "Post 1")
        self.assertEqual(posts[0].score, 50)
        self.assertEqual(after_token, "t3_a2")

    def test_empty_response(self):
        resp = self._make_response([], after=None)
        posts, after_token = parse_listing_response(resp)
        self.assertEqual(len(posts), 0)
        self.assertIsNone(after_token)

    def test_no_after_token(self):
        resp = self._make_response([{"id": "x1"}], after=None)
        _, after_token = parse_listing_response(resp)
        self.assertIsNone(after_token)

    def test_post_summary_fields(self):
        resp = self._make_response([{
            "id": "xyz",
            "title": "Technical Post",
            "author": "dev123",
            "score": 85,
            "num_comments": 18,
            "flair": "Discussion",
            "is_self": False,
            "url": "https://github.com/example",
        }])
        posts, _ = parse_listing_response(resp)
        p = posts[0]
        self.assertEqual(p.id, "xyz")
        self.assertEqual(p.title, "Technical Post")
        self.assertEqual(p.author, "dev123")
        self.assertEqual(p.score, 85)
        self.assertEqual(p.num_comments, 18)
        self.assertEqual(p.flair, "Discussion")
        self.assertFalse(p.is_self)
        self.assertEqual(p.url, "https://github.com/example")


class TestFilterPosts(unittest.TestCase):
    """Test post filtering (memes, low-value, duplicates)."""

    def _make_posts(self, items):
        posts = []
        for i, item in enumerate(items):
            posts.append(PostSummary(
                id=f"post{i}",
                title=item.get("title", "Test"),
                author=item.get("author", "user"),
                score=item.get("score", 10),
                num_comments=item.get("num_comments", 1),
                created_utc=item.get("created_utc", 1700000000 + i),
                permalink=f"/r/test/comments/post{i}/",
                subreddit="test",
                is_self=True,
                selftext="",
                url="",
                flair=item.get("flair", None),
                upvote_ratio=0.95,
            ))
        return posts

    def test_filter_shitposts(self):
        posts = self._make_posts([
            {"title": "[shitpost] Claude's adventures", "score": 26},
            {"title": "Technical harness discussion", "score": 30},
        ])
        filtered = filter_posts(posts, exclude_flairs=["Meme"], exclude_title_patterns=["shitpost"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "Technical harness discussion")

    def test_filter_by_min_score(self):
        posts = self._make_posts([
            {"title": "High value", "score": 50},
            {"title": "Low value", "score": 3},
        ])
        filtered = filter_posts(posts, min_score=5)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "High value")

    def test_filter_songs_and_memes(self):
        posts = self._make_posts([
            {"title": "Elevator Shanty Song by Kurukkoo", "score": 11},
            {"title": "Technical architecture post", "score": 15},
            {"title": "Song about Pokemon", "score": 8},
        ])
        filtered = filter_posts(posts, exclude_title_patterns=["song", "shanty"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "Technical architecture post")

    def test_no_filters(self):
        posts = self._make_posts([
            {"title": "Post 1"},
            {"title": "Post 2"},
        ])
        filtered = filter_posts(posts)
        self.assertEqual(len(filtered), 2)

    def test_filter_by_flair(self):
        posts = self._make_posts([
            {"title": "Meme post", "flair": "Meme"},
            {"title": "Discussion post", "flair": "Discussion"},
        ])
        filtered = filter_posts(posts, exclude_flairs=["Meme"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "Discussion post")


class TestFormatPostTable(unittest.TestCase):
    """Test formatted output for post listings."""

    def test_basic_format(self):
        posts = [PostSummary(
            id="abc", title="Test Post", author="user1", score=42,
            num_comments=10, created_utc=1700000000,
            permalink="/r/test/comments/abc/", subreddit="test",
            is_self=True, selftext="", url="", flair="Discussion",
            upvote_ratio=0.95,
        )]
        output = format_post_table(posts, subreddit="test")
        self.assertIn("Test Post", output)
        self.assertIn("42", output)
        self.assertIn("10", output)
        self.assertIn("user1", output)

    def test_sorted_by_score(self):
        posts = [
            PostSummary(id="a", title="Low", author="u", score=5,
                       num_comments=1, created_utc=1700000000,
                       permalink="/r/t/comments/a/", subreddit="t",
                       is_self=True, selftext="", url="", flair=None,
                       upvote_ratio=0.9),
            PostSummary(id="b", title="High", author="u", score=100,
                       num_comments=20, created_utc=1700000001,
                       permalink="/r/t/comments/b/", subreddit="t",
                       is_self=True, selftext="", url="", flair=None,
                       upvote_ratio=0.95),
        ]
        output = format_post_table(posts, sort_by="score")
        lines = output.strip().split("\n")
        # High score should come first
        first_post_line = [l for l in lines if "High" in l or "Low" in l]
        self.assertTrue(first_post_line[0].index("High") < first_post_line[1].index("Low"))


class TestScanResult(unittest.TestCase):
    """Test ScanResult aggregation."""

    def test_basic_result(self):
        posts = [PostSummary(
            id="abc", title="Test", author="u", score=10,
            num_comments=5, created_utc=1700000000,
            permalink="/r/t/comments/abc/", subreddit="test",
            is_self=True, selftext="body text", url="", flair=None,
            upvote_ratio=0.9,
        )]
        result = ScanResult(subreddit="test", total_posts=1, posts=posts, pages_fetched=1)
        self.assertEqual(result.total_posts, 1)
        self.assertEqual(result.subreddit, "test")
        self.assertEqual(len(result.posts), 1)

    def test_save_and_load(self):
        posts = [PostSummary(
            id="x1", title="Saved Post", author="dev", score=50,
            num_comments=12, created_utc=1700000000,
            permalink="/r/t/comments/x1/", subreddit="test",
            is_self=True, selftext="content", url="", flair="Tech",
            upvote_ratio=0.95,
        )]
        result = ScanResult(subreddit="test", total_posts=1, posts=posts, pages_fetched=1)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            result.save(path)

        try:
            loaded = ScanResult.load(path)
            self.assertEqual(loaded.subreddit, "test")
            self.assertEqual(len(loaded.posts), 1)
            self.assertEqual(loaded.posts[0].title, "Saved Post")
            self.assertEqual(loaded.posts[0].score, 50)
        finally:
            os.unlink(path)

    def test_urls_list(self):
        posts = [
            PostSummary(id="a", title="P1", author="u", score=10,
                       num_comments=1, created_utc=1700000000,
                       permalink="/r/t/comments/a/test/", subreddit="t",
                       is_self=True, selftext="", url="", flair=None,
                       upvote_ratio=0.9),
            PostSummary(id="b", title="P2", author="u", score=20,
                       num_comments=2, created_utc=1700000001,
                       permalink="/r/t/comments/b/test/", subreddit="t",
                       is_self=True, selftext="", url="", flair=None,
                       upvote_ratio=0.95),
        ]
        result = ScanResult(subreddit="t", total_posts=2, posts=posts, pages_fetched=1)
        urls = result.post_urls()
        self.assertEqual(len(urls), 2)
        self.assertTrue(all(u.startswith("https://www.reddit.com") for u in urls))


class TestCLI(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_scan_mode_detection(self):
        """Verify that 'scan' subcommand is recognized."""
        from subreddit_scanner import parse_cli_args
        args = parse_cli_args(["scan", "r/ClaudePlaysPokemon"])
        self.assertEqual(args["mode"], "scan")
        self.assertEqual(args["subreddit"], "ClaudePlaysPokemon")

    def test_scan_with_options(self):
        from subreddit_scanner import parse_cli_args
        args = parse_cli_args(["scan", "r/test", "--sort", "top", "--min-score", "10",
                               "--exclude", "shitpost,song", "--output", "results.json"])
        self.assertEqual(args["sort"], "top")
        self.assertEqual(args["min_score"], 10)
        self.assertEqual(args["exclude_patterns"], ["shitpost", "song"])
        self.assertEqual(args["output"], "results.json")

    def test_read_mode(self):
        from subreddit_scanner import parse_cli_args
        args = parse_cli_args(["read", "r/test", "post123"])
        self.assertEqual(args["mode"], "read")

    def test_default_sort(self):
        from subreddit_scanner import parse_cli_args
        args = parse_cli_args(["scan", "r/test"])
        self.assertEqual(args["sort"], "new")  # new is best for full scan


if __name__ == "__main__":
    unittest.main()
