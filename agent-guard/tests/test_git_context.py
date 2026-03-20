#!/usr/bin/env python3
"""Tests for git_context.py — MT-20: Git history awareness for senior reviews.

Tests cover:
- File commit history extraction (git log)
- Blame summary (who owns what percentage of a file)
- Recent change detection (changed in last N days)
- Churn detection (files changed frequently)
- Graceful handling of non-git repos and missing files
- Output formatting for review context
"""

import os
import subprocess
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from git_context import (
    GitContext,
    FileHistory,
    CommitInfo,
    BlameOwnership,
)


class TestGitContextInit(unittest.TestCase):
    """Test GitContext initialization and git detection."""

    def test_init_with_valid_repo(self):
        """Should detect CCA as a valid git repo."""
        cca_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        gc = GitContext(cca_root)
        self.assertTrue(gc.is_git_repo)

    def test_init_with_non_repo(self):
        tmpdir = tempfile.mkdtemp()
        try:
            gc = GitContext(tmpdir)
            self.assertFalse(gc.is_git_repo)
        finally:
            shutil.rmtree(tmpdir)

    def test_init_stores_repo_root(self):
        cca_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        gc = GitContext(cca_root)
        self.assertEqual(gc.repo_root, cca_root)


class TestCommitInfo(unittest.TestCase):
    """Test CommitInfo dataclass."""

    def test_creation(self):
        ci = CommitInfo(sha="abc1234", author="Alice", date="2026-03-20", message="Fix bug")
        self.assertEqual(ci.sha, "abc1234")
        self.assertEqual(ci.author, "Alice")

    def test_summary_truncates_long_messages(self):
        ci = CommitInfo(sha="abc1234", author="Alice", date="2026-03-20",
                        message="A" * 200)
        self.assertLessEqual(len(ci.summary), 100)


class TestFileHistory(unittest.TestCase):
    """Test file history extraction using a real git repo."""

    @classmethod
    def setUpClass(cls):
        cls.cca_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.gc = GitContext(cls.cca_root)

    def test_file_history_returns_commits(self):
        """CLAUDE.md should have multiple commits."""
        history = self.gc.file_history("CLAUDE.md")
        self.assertIsInstance(history, FileHistory)
        self.assertGreater(len(history.commits), 0)

    def test_file_history_commits_have_fields(self):
        history = self.gc.file_history("CLAUDE.md")
        if history.commits:
            c = history.commits[0]
            self.assertIsInstance(c, CommitInfo)
            self.assertTrue(c.sha)
            self.assertTrue(c.author)
            self.assertTrue(c.date)
            self.assertTrue(c.message)

    def test_file_history_max_commits(self):
        history = self.gc.file_history("CLAUDE.md", max_commits=3)
        self.assertLessEqual(len(history.commits), 3)

    def test_file_history_nonexistent_file(self):
        history = self.gc.file_history("does_not_exist_ever.py")
        self.assertEqual(len(history.commits), 0)

    def test_file_history_total_commits(self):
        history = self.gc.file_history("CLAUDE.md")
        self.assertGreaterEqual(history.total_commits, len(history.commits))

    def test_file_history_relative_path(self):
        """Should work with paths relative to repo root."""
        history = self.gc.file_history("agent-guard/senior_chat.py")
        self.assertGreater(len(history.commits), 0)


class TestBlameOwnership(unittest.TestCase):
    """Test blame ownership extraction."""

    @classmethod
    def setUpClass(cls):
        cls.cca_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.gc = GitContext(cls.cca_root)

    def test_blame_returns_ownership(self):
        owners = self.gc.blame_summary("CLAUDE.md")
        self.assertIsInstance(owners, list)
        self.assertGreater(len(owners), 0)

    def test_blame_ownership_fields(self):
        owners = self.gc.blame_summary("CLAUDE.md")
        if owners:
            o = owners[0]
            self.assertIsInstance(o, BlameOwnership)
            self.assertTrue(o.author)
            self.assertGreater(o.lines, 0)
            self.assertGreater(o.percentage, 0)

    def test_blame_percentages_sum_to_100(self):
        owners = self.gc.blame_summary("CLAUDE.md")
        total = sum(o.percentage for o in owners)
        self.assertAlmostEqual(total, 100.0, delta=1.0)

    def test_blame_nonexistent_file(self):
        owners = self.gc.blame_summary("does_not_exist_ever.py")
        self.assertEqual(owners, [])


class TestChurnDetection(unittest.TestCase):
    """Test file churn (change frequency) detection."""

    @classmethod
    def setUpClass(cls):
        cls.cca_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.gc = GitContext(cls.cca_root)

    def test_commit_count(self):
        count = self.gc.commit_count("CLAUDE.md")
        self.assertGreater(count, 0)

    def test_commit_count_nonexistent(self):
        count = self.gc.commit_count("does_not_exist.py")
        self.assertEqual(count, 0)

    def test_is_high_churn(self):
        """CLAUDE.md is edited almost every session — should be high churn."""
        self.assertTrue(self.gc.is_high_churn("CLAUDE.md", threshold=5))

    def test_not_high_churn_with_high_threshold(self):
        """With impossibly high threshold, nothing is high churn."""
        self.assertFalse(self.gc.is_high_churn("CLAUDE.md", threshold=99999))


class TestFormatForReview(unittest.TestCase):
    """Test formatting git context for inclusion in reviews."""

    @classmethod
    def setUpClass(cls):
        cls.cca_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.gc = GitContext(cls.cca_root)

    def test_format_returns_string(self):
        result = self.gc.format_for_review("CLAUDE.md")
        self.assertIsInstance(result, str)

    def test_format_includes_history(self):
        result = self.gc.format_for_review("CLAUDE.md")
        self.assertIn("commit", result.lower())

    def test_format_nonexistent_file(self):
        result = self.gc.format_for_review("does_not_exist.py")
        self.assertIn("No git history", result)

    def test_format_non_git_repo(self):
        tmpdir = tempfile.mkdtemp()
        try:
            gc = GitContext(tmpdir)
            result = gc.format_for_review("anything.py")
            self.assertIn("Not a git repository", result)
        finally:
            shutil.rmtree(tmpdir)


class TestNonGitRepo(unittest.TestCase):
    """Test graceful handling when not in a git repo."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gc = GitContext(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_file_history_empty(self):
        history = self.gc.file_history("any.py")
        self.assertEqual(len(history.commits), 0)

    def test_blame_empty(self):
        owners = self.gc.blame_summary("any.py")
        self.assertEqual(owners, [])

    def test_commit_count_zero(self):
        count = self.gc.commit_count("any.py")
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
