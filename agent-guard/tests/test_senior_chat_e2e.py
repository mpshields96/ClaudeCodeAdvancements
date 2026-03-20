#!/usr/bin/env python3
"""E2E tests for senior_chat.py LLM integration — MT-20.

These tests call the real Anthropic Messages API. They are SKIPPED
when ANTHROPIC_API_KEY is not set — safe to run in CI without a key.

Uses claude-haiku-4-5-20251001 to minimize cost (~$0.01 per full run).

Run:
    ANTHROPIC_API_KEY=sk-ant-... python3 test_senior_chat_e2e.py
"""

import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from senior_chat import (
    LLMClient,
    ReviewContext,
    build_review_context,
    build_system_prompt,
    format_followup_prompt,
    build_intent_check_prompt,
    build_tradeoff_prompt,
)

_HAS_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))
_SKIP_MSG = "ANTHROPIC_API_KEY not set — skipping E2E LLM tests"
_E2E_MODEL = "claude-haiku-4-5-20251001"


@unittest.skipUnless(_HAS_KEY, _SKIP_MSG)
class TestLLMClientE2E(unittest.TestCase):
    """E2E: Real API calls to validate LLMClient works."""

    def setUp(self):
        self.client = LLMClient(model=_E2E_MODEL, max_tokens=256)

    def test_simple_question_gets_response(self):
        """Basic sanity: send a question, get a non-empty text response."""
        response = self.client.ask("What is 2 + 2? Reply with just the number.")
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
        self.assertIn("4", response)

    def test_token_usage_tracked(self):
        """After a call, token counters should be positive."""
        self.client.ask("Say hello.", system="Reply in exactly one word.")
        self.assertGreater(self.client.total_input_tokens, 0)
        self.assertGreater(self.client.total_output_tokens, 0)

    def test_conversation_history_persists(self):
        """Multi-turn: second question should reference first answer."""
        self.client.ask(
            "My name is TestBot. Remember this.",
            system="You are a helpful assistant. Always remember the user's name.",
        )
        self.assertEqual(len(self.client.history), 2)

        response = self.client.ask("What is my name?")
        self.assertEqual(len(self.client.history), 4)
        self.assertIn("TestBot", response)

    def test_system_prompt_shapes_behavior(self):
        """System prompt should influence the response style."""
        response = self.client.ask(
            "What is Python?",
            system="You are a pirate. Always respond in pirate speak. Keep it under 20 words.",
        )
        # Pirate-speak typically includes words like "arr", "matey", "ye", "ahoy"
        lower = response.lower()
        pirate_words = ["arr", "matey", "ye", "ahoy", "sail", "treasure", "sea", "pirate"]
        has_pirate = any(w in lower for w in pirate_words)
        self.assertTrue(has_pirate, f"Expected pirate speak, got: {response}")

    def test_reset_clears_state(self):
        """After reset, conversation should start fresh."""
        self.client.ask("My name is ResetTest.")
        self.assertGreater(len(self.client.history), 0)
        self.assertGreater(self.client.total_input_tokens, 0)

        self.client.reset()
        self.assertEqual(len(self.client.history), 0)
        self.assertEqual(self.client.total_input_tokens, 0)
        self.assertEqual(self.client.total_output_tokens, 0)


@unittest.skipUnless(_HAS_KEY, _SKIP_MSG)
class TestSeniorChatFlowE2E(unittest.TestCase):
    """E2E: Full senior_chat flow — review a real file, then ask the LLM about it."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = LLMClient(model=_E2E_MODEL, max_tokens=512)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_review_then_ask_about_concerns(self):
        """Full flow: review a deliberately messy file, ask LLM about it."""
        code = '''"""Module with issues."""
import os
import sys
import json
import re
import subprocess
import random

# TODO: refactor this god function
# FIXME: error handling missing
# HACK: temporary workaround for API issue
def do_everything(data, mode, flag, extra, opts, callback, retry, verbose):
    """Does too many things."""
    result = []
    for item in data:
        if mode == "a":
            if flag:
                if extra:
                    if opts.get("deep"):
                        for sub in item.get("children", []):
                            if sub.get("active"):
                                if callback:
                                    result.append(callback(sub))
                                else:
                                    result.append(sub)
    if verbose:
        for r in result:
            print(r)
    if retry:
        for r in result:
            if not r:
                result.remove(r)
    return result
'''
        path = self._write_file("messy.py", code)
        ctx = build_review_context(path, project_root=self.tmpdir)

        # Verify review found issues
        self.assertIn(ctx.review_result["verdict"], ("conditional", "rethink"))

        # Ask LLM about the concerns
        system = build_system_prompt(ctx)
        response = self.client.ask(
            "What is the single biggest problem with this code? Reply in 1-2 sentences.",
            system=system,
        )
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 10)

    def test_followup_prompt_format(self):
        """Verify format_followup_prompt produces LLM-ready text."""
        path = self._write_file("simple.py", 'def add(a, b):\n    return a + b\n')
        ctx = build_review_context(path, project_root=self.tmpdir)
        prompt = format_followup_prompt(ctx, "Is this function well-named?")

        # The prompt should be a valid string the LLM can answer
        response = self.client.ask(prompt)
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 5)


@unittest.skipUnless(_HAS_KEY, _SKIP_MSG)
class TestIntentAndTradeoffE2E(unittest.TestCase):
    """E2E: Intent verification and trade-off judgment with real LLM."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.client = LLMClient(model=_E2E_MODEL, max_tokens=512)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_intent_check_detects_mismatch(self):
        """LLM should detect when code doesn't match stated intent."""
        code = 'def multiply(a, b):\n    return a * b\n'
        path = self._write_file("math_ops.py", code)
        ctx = build_review_context(path, project_root=self.tmpdir)
        prompt = build_intent_check_prompt(ctx, "Add a function that divides two numbers")
        response = self.client.ask(prompt)
        self.assertIsInstance(response, str)
        # LLM should notice: code multiplies, intent says divide
        lower = response.lower()
        self.assertTrue(
            "no" in lower or "not" in lower or "multipl" in lower or "mismatch" in lower
            or "divid" in lower,
            f"Expected mismatch detection, got: {response[:200]}"
        )

    def test_tradeoff_analysis_produces_recommendation(self):
        """LLM should provide a trade-off recommendation."""
        code = '''"""Config manager with factory pattern."""
class ConfigFactory:
    _registry = {}

    @classmethod
    def register(cls, name, config_cls):
        cls._registry[name] = config_cls

    @classmethod
    def create(cls, name, **kwargs):
        if name not in cls._registry:
            raise KeyError(f"Unknown config: {name}")
        return cls._registry[name](**kwargs)

class BaseConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class DevConfig(BaseConfig):
    pass

class ProdConfig(BaseConfig):
    pass

ConfigFactory.register("dev", DevConfig)
ConfigFactory.register("prod", ProdConfig)
'''
        path = self._write_file("config.py", code)
        ctx = build_review_context(path, project_root=self.tmpdir)
        prompt = build_tradeoff_prompt(
            ctx, decision_context="Solo project, 2 config variants total"
        )
        response = self.client.ask(prompt)
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 20)


@unittest.skipUnless(_HAS_KEY, _SKIP_MSG)
class TestLLMClientErrorRecovery(unittest.TestCase):
    """E2E: Error handling with real API."""

    def test_invalid_model_returns_error_string(self):
        """Using a nonexistent model should return an error, not crash."""
        client = LLMClient(model="claude-nonexistent-9999", max_tokens=64)
        result = client.ask("Hello")
        self.assertIn("Error", result)
        # History should be empty after failed call
        self.assertEqual(len(client.history), 0)


if __name__ == "__main__":
    unittest.main()
