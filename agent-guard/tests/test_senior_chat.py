#!/usr/bin/env python3
"""Tests for senior_chat.py — MT-20 Phase 8: Interactive senior dev CLI chat.

Tests cover:
- ReviewContext building from senior_review results
- Prompt formatting with review data
- Response generation (structured output from review context)
- CLI argument parsing
- Non-interactive mode (single question, no REPL)
- LLMClient: API integration, conversation history, error handling
"""

import json
import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from senior_chat import (
    ReviewContext,
    build_review_context,
    format_initial_review,
    format_followup_prompt,
    parse_args,
    LLMClient,
    build_system_prompt,
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


class TestBuildSystemPrompt(unittest.TestCase):
    """Test system prompt generation from review context."""

    def test_includes_verdict(self):
        ctx = ReviewContext(
            file_path="mod.py",
            content="x = 1\n",
            review_result={
                "verdict": "conditional",
                "concerns": ["High complexity"],
                "suggestions": ["Simplify"],
                "metrics": {"loc": 100, "quality_score": 55.0},
            },
        )
        prompt = build_system_prompt(ctx)
        self.assertIn("conditional", prompt.lower())
        self.assertIn("mod.py", prompt)

    def test_includes_file_content(self):
        ctx = ReviewContext(
            file_path="mod.py",
            content="def foo():\n    return 42\n",
            review_result={"verdict": "approve", "concerns": [], "suggestions": [], "metrics": {}},
        )
        prompt = build_system_prompt(ctx)
        self.assertIn("def foo", prompt)

    def test_includes_concerns_and_suggestions(self):
        ctx = ReviewContext(
            file_path="mod.py",
            content="x = 1\n",
            review_result={
                "verdict": "rethink",
                "concerns": ["No error handling", "God class"],
                "suggestions": ["Split into modules"],
                "metrics": {"loc": 800},
            },
        )
        prompt = build_system_prompt(ctx)
        self.assertIn("No error handling", prompt)
        self.assertIn("Split into modules", prompt)

    def test_truncates_large_files(self):
        ctx = ReviewContext(
            file_path="big.py",
            content="x = 1\n" * 5000,
            review_result={"verdict": "approve", "concerns": [], "suggestions": [], "metrics": {}},
        )
        prompt = build_system_prompt(ctx)
        self.assertIn("truncated", prompt.lower())
        self.assertLess(len(prompt), 15000)

    def test_includes_git_summary(self):
        ctx = ReviewContext(
            file_path="mod.py",
            content="x = 1\n",
            review_result={"verdict": "approve", "concerns": [], "suggestions": [], "metrics": {}},
            git_summary="Git history (5 total commits):\n  2026-03-20 Alice: Fix bug",
        )
        prompt = build_system_prompt(ctx)
        self.assertIn("Git history", prompt)
        self.assertIn("Alice", prompt)

    def test_no_git_summary_when_empty(self):
        ctx = ReviewContext(
            file_path="mod.py",
            content="x = 1\n",
            review_result={"verdict": "approve", "concerns": [], "suggestions": [], "metrics": {}},
            git_summary="",
        )
        prompt = build_system_prompt(ctx)
        self.assertNotIn("Git history", prompt)


class TestLLMClient(unittest.TestCase):
    """Test LLMClient — Anthropic API wrapper with conversation history."""

    def test_init_no_api_key_raises(self):
        """LLMClient should raise ValueError if no API key is available."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove ANTHROPIC_API_KEY if present
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ValueError):
                    LLMClient(api_key=None)

    def test_init_with_explicit_api_key(self):
        client = LLMClient(api_key="sk-ant-test-key-123")
        self.assertEqual(client.api_key, "sk-ant-test-key-123")

    def test_init_with_env_api_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-env-key-456"}):
            client = LLMClient()
            self.assertEqual(client.api_key, "sk-ant-env-key-456")

    def test_default_model(self):
        client = LLMClient(api_key="sk-ant-test-key-123")
        self.assertEqual(client.model, "claude-sonnet-4-20250514")

    def test_custom_model(self):
        client = LLMClient(api_key="sk-ant-test-key-123", model="claude-haiku-4-5-20251001")
        self.assertEqual(client.model, "claude-haiku-4-5-20251001")

    def test_conversation_history_starts_empty(self):
        client = LLMClient(api_key="sk-ant-test-key-123")
        self.assertEqual(client.history, [])

    def test_ask_appends_to_history(self):
        """After a successful ask(), both user and assistant messages are in history."""
        client = LLMClient(api_key="sk-ant-test-key-123")

        mock_response = {
            "content": [{"type": "text", "text": "The function returns 42."}],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
        with patch.object(client, "_call_api", return_value=mock_response):
            result = client.ask("What does foo do?", system="You are a senior dev.")
            self.assertEqual(result, "The function returns 42.")
            self.assertEqual(len(client.history), 2)
            self.assertEqual(client.history[0]["role"], "user")
            self.assertEqual(client.history[1]["role"], "assistant")

    def test_ask_tracks_token_usage(self):
        client = LLMClient(api_key="sk-ant-test-key-123")
        mock_response = {
            "content": [{"type": "text", "text": "Answer."}],
            "usage": {"input_tokens": 150, "output_tokens": 30},
        }
        with patch.object(client, "_call_api", return_value=mock_response):
            client.ask("Question?", system="System.")
            self.assertEqual(client.total_input_tokens, 150)
            self.assertEqual(client.total_output_tokens, 30)

    def test_ask_accumulates_tokens(self):
        client = LLMClient(api_key="sk-ant-test-key-123")
        mock_resp1 = {
            "content": [{"type": "text", "text": "A1."}],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
        mock_resp2 = {
            "content": [{"type": "text", "text": "A2."}],
            "usage": {"input_tokens": 200, "output_tokens": 40},
        }
        with patch.object(client, "_call_api", side_effect=[mock_resp1, mock_resp2]):
            client.ask("Q1", system="S")
            client.ask("Q2", system="S")
            self.assertEqual(client.total_input_tokens, 300)
            self.assertEqual(client.total_output_tokens, 60)

    def test_ask_handles_api_error(self):
        client = LLMClient(api_key="sk-ant-test-key-123")
        with patch.object(client, "_call_api", side_effect=Exception("Connection failed")):
            result = client.ask("Question?", system="System.")
            self.assertIn("Error", result)
            # History should NOT have the failed exchange
            self.assertEqual(len(client.history), 0)

    def test_reset_clears_history(self):
        client = LLMClient(api_key="sk-ant-test-key-123")
        client.history = [{"role": "user", "content": "test"}]
        client.total_input_tokens = 500
        client.reset()
        self.assertEqual(client.history, [])
        self.assertEqual(client.total_input_tokens, 0)
        self.assertEqual(client.total_output_tokens, 0)

    def test_call_api_builds_correct_request(self):
        """Verify _call_api sends properly formatted request to Anthropic."""
        client = LLMClient(api_key="sk-ant-test-key-123", model="claude-sonnet-4-20250514")

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "content": [{"type": "text", "text": "response"}],
            "usage": {"input_tokens": 50, "output_tokens": 10},
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        messages = [{"role": "user", "content": "Hello"}]
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = client._call_api(messages, system="You are helpful.")
            # Verify the request was made
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            self.assertEqual(req.get_header("X-api-key"), "sk-ant-test-key-123")
            self.assertIn("anthropic-version", {k.lower(): v for k, v in req.header_items()})
            body = json.loads(req.data)
            self.assertEqual(body["model"], "claude-sonnet-4-20250514")
            self.assertEqual(body["system"], "You are helpful.")

    def test_max_tokens_default(self):
        client = LLMClient(api_key="sk-ant-test-key-123")
        self.assertEqual(client.max_tokens, 4096)

    def test_max_tokens_custom(self):
        client = LLMClient(api_key="sk-ant-test-key-123", max_tokens=2048)
        self.assertEqual(client.max_tokens, 2048)


class TestParseArgsLLM(unittest.TestCase):
    """Test CLI args for LLM features."""

    def test_model_flag(self):
        args = parse_args(["test.py", "--model", "claude-haiku-4-5-20251001"])
        self.assertEqual(args.model, "claude-haiku-4-5-20251001")

    def test_model_default(self):
        args = parse_args(["test.py"])
        self.assertEqual(args.model, "claude-sonnet-4-20250514")

    def test_no_llm_flag(self):
        args = parse_args(["test.py", "--no-llm"])
        self.assertTrue(args.no_llm)

    def test_no_llm_default_false(self):
        args = parse_args(["test.py"])
        self.assertFalse(args.no_llm)


if __name__ == "__main__":
    unittest.main()
