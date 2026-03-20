#!/usr/bin/env python3
"""Tests for senior_chat.py — MT-20 Phase 8: Interactive senior dev CLI chat.

Tests cover:
- ReviewContext building from senior_review results
- Prompt formatting with review data
- Response generation (structured output from review context)
- CLI argument parsing
- Non-interactive mode (single question, no REPL)
"""

import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from senior_chat import (
    ReviewContext,
    build_review_context,
    format_initial_review,
    format_followup_prompt,
    parse_args,
)


class TestReviewContext(unittest.TestCase):
    """Test ReviewContext dataclass."""

    def test_context_creation(self):
        ctx = ReviewContext(
            file_path="test.py",
            content="x = 1\n",
            review_result={"verdict": "approve", "concerns": [], "suggestions": [], "metrics": {"loc": 1}},
        )
        self.assertEqual(ctx.file_path, "test.py")
        self.assertEqual(ctx.review_result["verdict"], "approve")

    def test_context_has_content(self):
        ctx = ReviewContext(
            file_path="test.py",
            content="def foo():\n    pass\n",
            review_result={"verdict": "approve", "concerns": [], "suggestions": [], "metrics": {}},
        )
        self.assertIn("def foo", ctx.content)


class TestBuildReviewContext(unittest.TestCase):
    """Test building review context from a file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_builds_context_from_file(self):
        path = self._write_file("mod.py", '"""Module."""\ndef run():\n    pass\n')
        ctx = build_review_context(path, project_root=self.tmpdir)
        self.assertIsInstance(ctx, ReviewContext)
        self.assertEqual(ctx.file_path, path)
        self.assertIn("verdict", ctx.review_result)

    def test_missing_file_returns_error_context(self):
        ctx = build_review_context("/nonexistent/file.py")
        self.assertEqual(ctx.review_result["verdict"], "error")

    def test_context_includes_content(self):
        path = self._write_file("code.py", 'x = 42\ny = 99\n')
        ctx = build_review_context(path, project_root=self.tmpdir)
        self.assertIn("x = 42", ctx.content)


class TestFormatInitialReview(unittest.TestCase):
    """Test formatting the initial review output for display."""

    def test_approve_format(self):
        ctx = ReviewContext(
            file_path="good.py",
            content="x = 1\n",
            review_result={
                "verdict": "approve",
                "concerns": [],
                "suggestions": [],
                "metrics": {"loc": 1, "quality_score": 95.0, "quality_grade": "A"},
            },
        )
        output = format_initial_review(ctx)
        self.assertIn("APPROVE", output.upper())
        self.assertIn("good.py", output)

    def test_conditional_shows_concerns(self):
        ctx = ReviewContext(
            file_path="messy.py",
            content="x = 1\n",
            review_result={
                "verdict": "conditional",
                "concerns": ["High complexity", "Missing tests"],
                "suggestions": ["Add docstrings"],
                "metrics": {"loc": 200, "quality_score": 55.0, "quality_grade": "D"},
            },
        )
        output = format_initial_review(ctx)
        self.assertIn("CONDITIONAL", output.upper())
        self.assertIn("High complexity", output)

    def test_rethink_shows_concerns(self):
        ctx = ReviewContext(
            file_path="bad.py",
            content="x = 1\n",
            review_result={
                "verdict": "rethink",
                "concerns": ["Structural problems"],
                "suggestions": [],
                "metrics": {"loc": 1200, "quality_score": 30.0, "quality_grade": "F"},
            },
        )
        output = format_initial_review(ctx)
        self.assertIn("RETHINK", output.upper())

    def test_metrics_displayed(self):
        ctx = ReviewContext(
            file_path="mod.py",
            content="x = 1\n",
            review_result={
                "verdict": "approve",
                "concerns": [],
                "suggestions": [],
                "metrics": {"loc": 50, "quality_score": 88.0, "quality_grade": "B",
                            "blast_radius": 3, "satd_total": 2},
            },
        )
        output = format_initial_review(ctx)
        self.assertIn("50", output)  # LOC shown


class TestFormatFollowupPrompt(unittest.TestCase):
    """Test follow-up prompt formatting for the LLM."""

    def test_includes_file_content(self):
        ctx = ReviewContext(
            file_path="mod.py",
            content="def foo():\n    return 42\n",
            review_result={"verdict": "approve", "concerns": [], "suggestions": [], "metrics": {}},
        )
        prompt = format_followup_prompt(ctx, "What does foo do?")
        self.assertIn("def foo", prompt)
        self.assertIn("What does foo do?", prompt)

    def test_includes_review_context(self):
        ctx = ReviewContext(
            file_path="mod.py",
            content="x = 1\n",
            review_result={
                "verdict": "conditional",
                "concerns": ["Too complex"],
                "suggestions": ["Simplify"],
                "metrics": {"loc": 100},
            },
        )
        prompt = format_followup_prompt(ctx, "How to simplify?")
        self.assertIn("conditional", prompt.lower())
        self.assertIn("How to simplify?", prompt)


class TestParseArgs(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_file_path_required(self):
        args = parse_args(["test.py"])
        self.assertEqual(args.file_path, "test.py")

    def test_project_root_default_empty(self):
        args = parse_args(["test.py"])
        self.assertEqual(args.project_root, "")

    def test_project_root_flag(self):
        args = parse_args(["test.py", "--project-root", "/tmp/proj"])
        self.assertEqual(args.project_root, "/tmp/proj")

    def test_question_flag(self):
        args = parse_args(["test.py", "--question", "What is this?"])
        self.assertEqual(args.question, "What is this?")

    def test_no_question_means_interactive(self):
        args = parse_args(["test.py"])
        self.assertIsNone(args.question)


if __name__ == "__main__":
    unittest.main()
