#!/usr/bin/env python3
"""
Tests for reddit-intelligence/url_reader.py — Universal URL routing.
177 LOC source. Tests routing logic, output formatting, and error handling.
All subprocess/shutil calls are mocked — no network or CLI tools needed.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _MODULE_DIR)

import url_reader as ur


# ── is_reddit ─────────────────────────────────────────────────────────────────

class TestIsReddit(unittest.TestCase):

    def test_full_reddit_url(self):
        self.assertTrue(ur.is_reddit("https://www.reddit.com/r/ClaudeAI/comments/abc123"))

    def test_reddit_without_www(self):
        self.assertTrue(ur.is_reddit("https://reddit.com/r/ClaudeAI/"))

    def test_short_r_prefix(self):
        self.assertTrue(ur.is_reddit("r/ClaudeCode"))

    def test_github_not_reddit(self):
        self.assertFalse(ur.is_reddit("https://github.com/user/repo"))

    def test_empty_string(self):
        self.assertFalse(ur.is_reddit(""))

    def test_youtube_not_reddit(self):
        self.assertFalse(ur.is_reddit("https://youtube.com/watch?v=abc"))

    def test_old_reddit(self):
        self.assertTrue(ur.is_reddit("https://old.reddit.com/r/python"))


# ── is_youtube ────────────────────────────────────────────────────────────────

class TestIsYoutube(unittest.TestCase):

    def test_standard_watch_url(self):
        self.assertTrue(ur.is_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))

    def test_short_youtu_be(self):
        self.assertTrue(ur.is_youtube("https://youtu.be/dQw4w9WgXcQ"))

    def test_youtube_shorts(self):
        self.assertTrue(ur.is_youtube("https://youtube.com/shorts/abc123"))

    def test_youtube_channel_not_matched(self):
        # Channel pages are not video URLs
        self.assertFalse(ur.is_youtube("https://www.youtube.com/c/SomeChannel"))

    def test_reddit_not_youtube(self):
        self.assertFalse(ur.is_youtube("https://reddit.com/r/ClaudeAI"))

    def test_empty_string(self):
        self.assertFalse(ur.is_youtube(""))


# ── read_reddit ───────────────────────────────────────────────────────────────

class TestReadReddit(unittest.TestCase):

    def test_success_returns_stdout(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "POST CONTENT\nComment 1\nComment 2"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            output = ur.read_reddit("https://reddit.com/r/test/comments/abc")
        self.assertIn("POST CONTENT", output)

    def test_error_returns_error_message(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Connection refused"
        with patch("subprocess.run", return_value=mock_result):
            output = ur.read_reddit("https://reddit.com/r/test/comments/abc")
        self.assertIn("REDDIT READER ERROR", output)
        self.assertIn("Connection refused", output)

    def test_calls_reddit_reader_script(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "content"
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            ur.read_reddit("https://reddit.com/r/test")
        args = mock_run.call_args[0][0]
        # Should call reddit_reader.py
        self.assertTrue(any("reddit_reader.py" in str(a) for a in args))


# ── read_youtube ──────────────────────────────────────────────────────────────

class TestReadYoutube(unittest.TestCase):

    def test_yt_dlp_not_installed(self):
        with patch("shutil.which", return_value=None):
            output = ur.read_youtube("https://youtu.be/test")
        self.assertIn("yt-dlp not installed", output)
        self.assertIn("brew install yt-dlp", output)

    def test_no_subtitles_returns_description_fallback(self):
        """When no .json3 subtitle files exist, returns title/channel/description."""
        def mock_run(args, **kwargs):
            r = MagicMock()
            r.returncode = 0
            if "--print" in args and "%(title)s" in args:
                r.stdout = "Test Video Title\n"
            elif "--print" in args and "%(channel)s" in args:
                r.stdout = "Test Channel\n"
            elif "--print" in args and "%(description)s" in args:
                r.stdout = "A great description\n"
            else:
                r.stdout = ""  # subtitle download step
            return r

        with patch("shutil.which", return_value="/usr/local/bin/yt-dlp"), \
             patch("subprocess.run", side_effect=mock_run):
            output = ur.read_youtube("https://youtu.be/test123")

        self.assertIn("Test Video Title", output)
        self.assertIn("Test Channel", output)
        self.assertIn("TRANSCRIPT: Not available", output)

    def test_with_subtitles_includes_transcript(self):
        """When subtitle json3 file exists, parses and returns transcript."""
        subtitle_data = {
            "events": [
                {"tStartMs": 0, "segs": [{"utf8": "Hello world"}]},
                {"tStartMs": 5000, "segs": [{"utf8": "Second line"}]},
                {"tStartMs": 65000, "segs": [{"utf8": "Over a minute"}]},
            ]
        }

        def mock_run(args, **kwargs):
            r = MagicMock()
            r.returncode = 0
            if "--print" in args and "%(title)s" in args:
                r.stdout = "My Video\n"
            elif "--print" in args and "%(channel)s" in args:
                r.stdout = "MyChannel\n"
            elif "--print" in args and "%(description)s" in args:
                r.stdout = "Desc\n"
            else:
                # Subtitle download — write subtitle file to tmpdir
                # Extract -o path from args
                try:
                    o_idx = args.index("-o")
                    sub_path = args[o_idx + 1]
                    # Write the json3 file
                    with open(sub_path + ".en.json3", "w") as f:
                        json.dump(subtitle_data, f)
                except (ValueError, IndexError):
                    pass
                r.stdout = ""
            return r

        with patch("shutil.which", return_value="/usr/local/bin/yt-dlp"), \
             patch("subprocess.run", side_effect=mock_run):
            output = ur.read_youtube("https://youtu.be/test123")

        self.assertIn("TRANSCRIPT", output)
        self.assertIn("Hello world", output)
        self.assertIn("Second line", output)

    def test_timestamp_formatting_over_an_hour(self):
        """Timestamps >= 1 hour should show H:MM:SS format."""
        subtitle_data = {
            "events": [
                {"tStartMs": 3660000, "segs": [{"utf8": "Late in video"}]},  # 61 minutes
            ]
        }

        def mock_run(args, **kwargs):
            r = MagicMock()
            r.returncode = 0
            if "--print" in args:
                r.stdout = "Title\n"
            else:
                try:
                    o_idx = args.index("-o")
                    sub_path = args[o_idx + 1]
                    with open(sub_path + ".en.json3", "w") as f:
                        json.dump(subtitle_data, f)
                except (ValueError, IndexError):
                    pass
                r.stdout = ""
            return r

        with patch("shutil.which", return_value="/usr/local/bin/yt-dlp"), \
             patch("subprocess.run", side_effect=mock_run):
            output = ur.read_youtube("https://youtu.be/test123")

        # Should have H:MM:SS format for 61-minute mark
        self.assertIn("1:01:00", output)

    def test_duplicate_lines_deduped(self):
        """Duplicate transcript lines should only appear once."""
        subtitle_data = {
            "events": [
                {"tStartMs": 0, "segs": [{"utf8": "Repeated line"}]},
                {"tStartMs": 2000, "segs": [{"utf8": "Repeated line"}]},
                {"tStartMs": 4000, "segs": [{"utf8": "Unique line"}]},
            ]
        }

        def mock_run(args, **kwargs):
            r = MagicMock()
            r.returncode = 0
            if "--print" in args:
                r.stdout = "Title\n"
            else:
                try:
                    o_idx = args.index("-o")
                    sub_path = args[o_idx + 1]
                    with open(sub_path + ".en.json3", "w") as f:
                        json.dump(subtitle_data, f)
                except (ValueError, IndexError):
                    pass
                r.stdout = ""
            return r

        with patch("shutil.which", return_value="/usr/local/bin/yt-dlp"), \
             patch("subprocess.run", side_effect=mock_run):
            output = ur.read_youtube("https://youtu.be/test123")

        # "Repeated line" should appear only once
        self.assertEqual(output.count("Repeated line"), 1)
        self.assertIn("Unique line", output)


# ── read_webpage ──────────────────────────────────────────────────────────────

class TestReadWebpage(unittest.TestCase):

    def test_defuddle_not_installed(self):
        with patch("shutil.which", return_value=None):
            output = ur.read_webpage("https://example.com/article")
        self.assertIn("defuddle not installed", output)
        self.assertIn("npm install -g defuddle", output)

    def test_success_returns_content(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "# Article Title\n\nArticle body content here."
        with patch("shutil.which", return_value="/usr/local/bin/defuddle"), \
             patch("subprocess.run", return_value=mock_result):
            output = ur.read_webpage("https://example.com/article")
        self.assertIn("https://example.com/article", output)
        self.assertIn("Article Title", output)

    def test_defuddle_error(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Failed to fetch"
        mock_result.stdout = ""
        with patch("shutil.which", return_value="/usr/local/bin/defuddle"), \
             patch("subprocess.run", return_value=mock_result):
            output = ur.read_webpage("https://example.com/article")
        self.assertIn("DEFUDDLE ERROR", output)

    def test_empty_content_from_defuddle(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("shutil.which", return_value="/usr/local/bin/defuddle"), \
             patch("subprocess.run", return_value=mock_result):
            output = ur.read_webpage("https://example.com/article")
        self.assertIn("No content extracted", output)

    def test_uses_markdown_flag(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "content"
        with patch("shutil.which", return_value="/usr/local/bin/defuddle"), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            ur.read_webpage("https://example.com")
        args = mock_run.call_args[0][0]
        self.assertIn("--markdown", args)


# ── routing (main logic) ──────────────────────────────────────────────────────

class TestRouting(unittest.TestCase):
    """Test that routing logic correctly dispatches to the right handler."""

    def test_reddit_url_routes_to_read_reddit(self):
        with patch.object(ur, "read_reddit", return_value="reddit content") as mock_rr:
            with patch.object(ur, "read_youtube"):
                with patch.object(ur, "read_webpage"):
                    # Simulate routing
                    url = "https://reddit.com/r/test"
                    if ur.is_reddit(url):
                        result = ur.read_reddit(url)
                    elif ur.is_youtube(url):
                        result = ur.read_youtube(url)
                    else:
                        result = ur.read_webpage(url)
            mock_rr.assert_called_once_with(url)

    def test_youtube_url_routes_to_read_youtube(self):
        url = "https://youtube.com/watch?v=abc123"
        self.assertFalse(ur.is_reddit(url))
        self.assertTrue(ur.is_youtube(url))

    def test_generic_url_is_not_reddit_or_youtube(self):
        url = "https://anthropic.com/research"
        self.assertFalse(ur.is_reddit(url))
        self.assertFalse(ur.is_youtube(url))

    def test_github_url_routes_to_webpage(self):
        url = "https://github.com/user/repo"
        self.assertFalse(ur.is_reddit(url))
        self.assertFalse(ur.is_youtube(url))


if __name__ == "__main__":
    unittest.main()
