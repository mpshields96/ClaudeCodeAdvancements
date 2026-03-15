"""
Tests for reddit_reader.py — parse_input, flatten_comments, normalize_url.
Network calls are mocked; no live Reddit requests in tests.
"""
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO

sys.path.insert(0, "/Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence")
import reddit_reader as rr


class TestParseInput(unittest.TestCase):
    def test_bare_subreddit_name(self):
        kind, sub, extra = rr.parse_input("ClaudeAI")
        self.assertEqual(kind, "subreddit")
        self.assertEqual(sub, "ClaudeAI")
        self.assertEqual(extra, "hot")

    def test_r_slash_subreddit(self):
        kind, sub, extra = rr.parse_input("r/ClaudeCode")
        self.assertEqual(kind, "subreddit")
        self.assertEqual(sub, "ClaudeCode")

    def test_slash_r_slash_subreddit(self):
        kind, sub, extra = rr.parse_input("/r/vibecoding")
        self.assertEqual(kind, "subreddit")
        self.assertEqual(sub, "vibecoding")

    def test_www_reddit_subreddit_url(self):
        kind, sub, extra = rr.parse_input("https://www.reddit.com/r/AI_agents/")
        self.assertEqual(kind, "subreddit")
        self.assertEqual(sub, "AI_agents")

    def test_old_reddit_normalized(self):
        kind, sub, extra = rr.parse_input("https://old.reddit.com/r/ClaudeAI/")
        self.assertEqual(kind, "subreddit")
        self.assertEqual(sub, "ClaudeAI")

    def test_subreddit_url_with_hot_sort(self):
        kind, sub, extra = rr.parse_input("https://www.reddit.com/r/algotrading/hot/")
        self.assertEqual(kind, "subreddit")
        self.assertEqual(sub, "algotrading")
        self.assertEqual(extra, "hot")

    def test_subreddit_url_with_new_sort(self):
        kind, sub, extra = rr.parse_input("https://www.reddit.com/r/algobetting/new/")
        self.assertEqual(kind, "subreddit")
        self.assertEqual(sub, "algobetting")
        self.assertEqual(extra, "new")

    def test_subreddit_url_with_top_sort(self):
        kind, sub, extra = rr.parse_input("https://www.reddit.com/r/Kalshi/top/")
        self.assertEqual(kind, "subreddit")
        self.assertEqual(sub, "Kalshi")
        self.assertEqual(extra, "top")

    def test_subreddit_url_with_rising_sort(self):
        kind, sub, extra = rr.parse_input("https://www.reddit.com/r/polymarket_bets/rising/")
        self.assertEqual(kind, "subreddit")
        self.assertEqual(sub, "polymarket_bets")
        self.assertEqual(extra, "rising")

    def test_post_url_www(self):
        url = "https://www.reddit.com/r/ClaudeAI/comments/abc123/some_title/"
        kind, sub, extra = rr.parse_input(url)
        self.assertEqual(kind, "post")
        self.assertEqual(sub, "ClaudeAI")
        self.assertEqual(extra, "abc123")

    def test_post_url_old_reddit(self):
        url = "https://old.reddit.com/r/Claude/comments/xyz789/title_here/"
        kind, sub, extra = rr.parse_input(url)
        self.assertEqual(kind, "post")
        self.assertEqual(sub, "Claude")
        self.assertEqual(extra, "xyz789")

    def test_post_url_no_trailing_slash(self):
        url = "https://www.reddit.com/r/PredictionMarkets/comments/def456/post_title"
        kind, sub, extra = rr.parse_input(url)
        self.assertEqual(kind, "post")
        self.assertEqual(sub, "PredictionMarkets")
        self.assertEqual(extra, "def456")

    def test_strips_whitespace(self):
        kind, sub, extra = rr.parse_input("  r/ClaudeAI  ")
        self.assertEqual(sub, "ClaudeAI")

    def test_invalid_input_raises(self):
        with self.assertRaises(ValueError):
            rr.parse_input("https://github.com/some/repo")

    def test_all_target_subreddits_parse(self):
        targets = [
            "r/ClaudeCode", "r/ClaudeAI", "r/Claude", "r/algobetting",
            "r/algotrading", "r/vibecoding", "r/AI_agents",
            "r/Kalshi", "r/polymarket_bets", "r/PredictionMarkets"
        ]
        for t in targets:
            kind, sub, extra = rr.parse_input(t)
            self.assertEqual(kind, "subreddit", f"Failed for {t}")


class TestNormalizeUrl(unittest.TestCase):
    def test_replaces_old_with_www(self):
        result = rr.normalize_url("https://old.reddit.com/r/ClaudeAI/")
        self.assertEqual(result, "https://www.reddit.com/r/ClaudeAI/")

    def test_www_unchanged(self):
        result = rr.normalize_url("https://www.reddit.com/r/ClaudeAI/")
        self.assertEqual(result, "https://www.reddit.com/r/ClaudeAI/")

    def test_no_reddit_unchanged(self):
        result = rr.normalize_url("https://example.com/page")
        self.assertEqual(result, "https://example.com/page")


class TestFlattenComments(unittest.TestCase):
    def _make_comment(self, author, body, score=10, replies=None, depth=0):
        data = {
            "author": author,
            "body": body,
            "score": score,
            "replies": replies or "",
        }
        return {"kind": "t1", "data": data}

    def test_single_comment(self):
        tree = [self._make_comment("alice", "Hello world")]
        result = rr.flatten_comments(tree)
        self.assertEqual(len(result), 1)
        self.assertIn("alice", result[0])
        self.assertIn("Hello world", result[0])

    def test_deleted_comment_excluded(self):
        tree = [self._make_comment("alice", "[deleted]")]
        result = rr.flatten_comments(tree)
        self.assertEqual(len(result), 0)

    def test_removed_comment_excluded(self):
        tree = [self._make_comment("bob", "[removed]")]
        result = rr.flatten_comments(tree)
        self.assertEqual(len(result), 0)

    def test_score_shown(self):
        tree = [self._make_comment("alice", "Great post", score=42)]
        result = rr.flatten_comments(tree)
        self.assertIn("42", result[0])

    def test_nested_replies(self):
        reply = self._make_comment("bob", "Nested reply", score=5)
        replies_data = {"data": {"children": [reply]}}
        parent = self._make_comment("alice", "Parent comment", replies=replies_data)
        tree = [parent]
        result = rr.flatten_comments(tree)
        self.assertEqual(len(result), 2)
        # Reply should be indented
        self.assertTrue(result[1].startswith("  "))

    def test_more_item_shows_count(self):
        more = {"kind": "more", "data": {"count": 15}}
        result = rr.flatten_comments([more])
        self.assertEqual(len(result), 1)
        self.assertIn("15", result[0])
        self.assertIn("more", result[0])

    def test_more_item_zero_count_excluded(self):
        more = {"kind": "more", "data": {"count": 0}}
        result = rr.flatten_comments([more])
        self.assertEqual(len(result), 0)

    def test_unknown_kind_excluded(self):
        item = {"kind": "t3", "data": {}}
        result = rr.flatten_comments([item])
        self.assertEqual(len(result), 0)

    def test_max_depth_respected(self):
        # Build deeply nested structure
        deepest = self._make_comment("deep", "Deep comment")
        for _ in range(12):
            replies_data = {"data": {"children": [deepest]}}
            deepest = self._make_comment("level", "comment", replies=replies_data)
        tree = [deepest]
        # Should not raise even with deep nesting
        result = rr.flatten_comments(tree, max_depth=5)
        # At max_depth, recursion stops
        self.assertIsInstance(result, list)

    def test_empty_body_excluded(self):
        item = {"kind": "t1", "data": {"author": "alice", "body": "", "score": 5, "replies": ""}}
        result = rr.flatten_comments([item])
        self.assertEqual(len(result), 0)

    def test_none_body_excluded(self):
        item = {"kind": "t1", "data": {"author": "alice", "body": None, "score": 5, "replies": ""}}
        result = rr.flatten_comments([item])
        self.assertEqual(len(result), 0)

    def test_multiline_body_indented(self):
        body = "Line one\nLine two\nLine three"
        reply = self._make_comment("bob", body, score=1)
        replies_data = {"data": {"children": [reply]}}
        parent = self._make_comment("alice", "Parent", replies=replies_data)
        result = rr.flatten_comments([parent])
        # The reply (depth=1) should have its lines indented
        reply_text = result[1]
        lines = reply_text.split("\n")
        for line in lines:
            if line.strip():
                self.assertTrue(line.startswith("  "), f"Line not indented: {line!r}")

    def test_empty_tree(self):
        result = rr.flatten_comments([])
        self.assertEqual(result, [])


class TestReadSubredditMocked(unittest.TestCase):
    def _make_listing(self, posts):
        return {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "title": p["title"],
                            "author": p.get("author", "testuser"),
                            "score": p.get("score", 100),
                            "num_comments": p.get("num_comments", 10),
                            "id": p.get("id", "abc123"),
                            "subreddit": p.get("subreddit", "ClaudeAI"),
                            "is_self": True,
                            "url": "",
                            "link_flair_text": p.get("flair", None),
                        }
                    }
                    for p in posts
                ]
            }
        }

    @patch("reddit_reader.fetch_json")
    def test_returns_post_titles(self, mock_fetch):
        mock_fetch.return_value = self._make_listing([
            {"title": "First Post", "score": 50},
            {"title": "Second Post", "score": 30},
        ])
        result = rr.read_subreddit("ClaudeAI", "hot", 25)
        self.assertIn("First Post", result)
        self.assertIn("Second Post", result)

    @patch("reddit_reader.fetch_json")
    def test_header_shows_subreddit_and_sort(self, mock_fetch):
        mock_fetch.return_value = self._make_listing([{"title": "Post"}])
        result = rr.read_subreddit("vibecoding", "new", 10)
        self.assertIn("r/vibecoding", result)
        self.assertIn("NEW", result)

    @patch("reddit_reader.fetch_json")
    def test_shows_author_score_comments(self, mock_fetch):
        mock_fetch.return_value = self._make_listing([
            {"title": "A Post", "author": "alice", "score": 999, "num_comments": 42}
        ])
        result = rr.read_subreddit("ClaudeCode", "hot", 25)
        self.assertIn("alice", result)
        self.assertIn("999", result)
        self.assertIn("42", result)

    @patch("reddit_reader.fetch_json")
    def test_shows_permalink(self, mock_fetch):
        mock_fetch.return_value = self._make_listing([{"title": "Post", "id": "xyz789"}])
        result = rr.read_subreddit("Claude", "top", 5)
        self.assertIn("xyz789", result)
        self.assertIn("reddit.com", result)

    @patch("reddit_reader.fetch_json")
    def test_flair_shown_when_present(self, mock_fetch):
        mock_fetch.return_value = self._make_listing([
            {"title": "Post", "flair": "Discussion"}
        ])
        result = rr.read_subreddit("ClaudeAI", "hot", 5)
        self.assertIn("Discussion", result)


class TestReadPostMocked(unittest.TestCase):
    def _make_post_response(self, title="Test Post", body="Post body text",
                            author="testuser", score=100, num_comments=5):
        post_listing = {
            "data": {
                "children": [{
                    "kind": "t3",
                    "data": {
                        "title": title,
                        "author": author,
                        "score": score,
                        "upvote_ratio": 0.95,
                        "selftext": body,
                        "url": "https://www.reddit.com/r/ClaudeAI/comments/abc123/test_post/",
                        "num_comments": num_comments,
                        "link_flair_text": None,
                        "created_utc": 1700000000,
                        "permalink": "/r/ClaudeAI/comments/abc123/test_post/",
                        "is_self": True,
                    }
                }]
            }
        }
        comment_listing = {
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "author": "commenter1",
                            "body": "Great post!",
                            "score": 25,
                            "replies": "",
                        }
                    }
                ]
            }
        }
        return [post_listing, comment_listing]

    @patch("reddit_reader.fetch_json")
    def test_title_in_output(self, mock_fetch):
        mock_fetch.return_value = self._make_post_response(title="My Test Post")
        result = rr.read_post("ClaudeAI", "abc123")
        self.assertIn("My Test Post", result)

    @patch("reddit_reader.fetch_json")
    def test_body_in_output(self, mock_fetch):
        mock_fetch.return_value = self._make_post_response(body="Detailed post content here.")
        result = rr.read_post("ClaudeAI", "abc123")
        self.assertIn("Detailed post content here.", result)

    @patch("reddit_reader.fetch_json")
    def test_comment_in_output(self, mock_fetch):
        mock_fetch.return_value = self._make_post_response()
        result = rr.read_post("ClaudeAI", "abc123")
        self.assertIn("Great post!", result)
        self.assertIn("commenter1", result)

    @patch("reddit_reader.fetch_json")
    def test_score_shown(self, mock_fetch):
        mock_fetch.return_value = self._make_post_response(score=1234)
        result = rr.read_post("ClaudeAI", "abc123")
        self.assertIn("1234", result)

    @patch("reddit_reader.fetch_json")
    def test_upvote_ratio_shown(self, mock_fetch):
        mock_fetch.return_value = self._make_post_response()
        result = rr.read_post("ClaudeAI", "abc123")
        self.assertIn("95%", result)

    @patch("reddit_reader.fetch_json")
    def test_comment_count_shown(self, mock_fetch):
        mock_fetch.return_value = self._make_post_response(num_comments=99)
        result = rr.read_post("ClaudeAI", "abc123")
        self.assertIn("99", result)

    @patch("reddit_reader.fetch_json")
    def test_link_post_shows_url(self, mock_fetch):
        data = self._make_post_response(body="")
        data[0]["data"]["children"][0]["data"]["selftext"] = ""
        data[0]["data"]["children"][0]["data"]["url"] = "https://example.com/article"
        data[0]["data"]["children"][0]["data"]["is_self"] = False
        mock_fetch.return_value = data
        result = rr.read_post("ClaudeAI", "abc123")
        self.assertIn("https://example.com/article", result)


if __name__ == "__main__":
    unittest.main()
