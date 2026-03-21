#!/usr/bin/env python3
"""
Tests for resurfacer_hook.py — UserPromptSubmit hook that auto-surfaces
relevant FINDINGS_LOG entries based on detected module/frontier/MT context.

Run: python3 self-learning/tests/test_resurfacer_hook.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── Sample data ──────────────────────────────────────────────────────────────

SAMPLE_LOG = """[2026-03-17] [BUILD] [Frontier 5: Usage Dashboard + Frontier 3: Context Health] CShip — Rust statusline for Claude Code with cost, context bar, usage limits — https://reddit.com/r/ClaudeCode/1
[2026-03-17] [ADAPT] [Frontier 2: Spec-Driven Dev] Autoresearch — Karpathy-inspired autonomous iteration loop — https://reddit.com/r/ClaudeCode/2
[2026-03-17] [REFERENCE] [Frontier 1: Memory] traul — CLI syncing all comms into local SQLite + FTS5 — https://reddit.com/r/ClaudeCode/3
[2026-03-15] [REFERENCE-PERSONAL] [Trading/Kalshi] VEI volatility expansion signal — https://reddit.com/r/algotrading/1
[2026-03-18] [BUILD] [Frontier 4: Agent Guard] SafeAgent — multi-agent conflict prevention framework — https://github.com/example/safeagent
[2026-03-18] [ADAPT] [MT-17: Design] Design Studio v4 — 26 roles, massive overengineering — https://reddit.com/r/ClaudeCode/5
[2026-03-19] [BUILD] [Frontier 3: Context Health] ContextGuard — compaction recovery tool — https://github.com/example/contextguard
"""


class TestDetectContext(unittest.TestCase):
    """Test prompt context detection."""

    def test_detects_module_name(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("I'm working on context-monitor hooks today")
        self.assertIn("context-monitor", ctx["modules"])

    def test_detects_multiple_modules(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("fixing agent-guard and memory-system integration")
        self.assertIn("agent-guard", ctx["modules"])
        self.assertIn("memory-system", ctx["modules"])

    def test_detects_frontier_number(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("working on Frontier 3 compaction issues")
        self.assertIn(3, ctx["frontiers"])

    def test_detects_mt_task(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("continuing MT-17 design work")
        self.assertIn("MT-17", ctx["mt_tasks"])

    def test_detects_multiple_mt_tasks(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("MT-10 and MT-12 both need attention")
        self.assertIn("MT-10", ctx["mt_tasks"])
        self.assertIn("MT-12", ctx["mt_tasks"])

    def test_no_context_returns_empty(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("hello how are you")
        self.assertEqual(ctx["modules"], [])
        self.assertEqual(ctx["frontiers"], [])
        self.assertEqual(ctx["mt_tasks"], [])

    def test_detects_keyword_trading(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("let's look at the Kalshi trading patterns")
        self.assertIn("trading", ctx["keywords"])

    def test_detects_keyword_memory(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("improving the memory capture hook")
        self.assertIn("memory-system", ctx["modules"])

    def test_case_insensitive_module(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("the SPEC-SYSTEM needs a fix")
        self.assertIn("spec-system", ctx["modules"])

    def test_detects_frontier_word_context(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("context health monitoring is broken")
        self.assertIn(3, ctx["frontiers"])

    def test_detects_frontier_word_usage(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("token usage dashboard needs updating")
        self.assertIn(5, ctx["frontiers"])

    def test_detects_frontier_word_spec(self):
        from resurfacer_hook import detect_context
        ctx = detect_context("spec-driven development workflow")
        self.assertIn(2, ctx["frontiers"])


class TestBuildResurfaceQuery(unittest.TestCase):
    """Test query building from detected context."""

    def test_module_maps_to_frontier(self):
        from resurfacer_hook import build_resurface_queries
        ctx = {"modules": ["context-monitor"], "frontiers": [], "mt_tasks": [], "keywords": []}
        queries = build_resurface_queries(ctx)
        self.assertTrue(any(q.get("frontier") == 3 for q in queries))

    def test_mt_task_generates_query(self):
        from resurfacer_hook import build_resurface_queries
        ctx = {"modules": [], "frontiers": [], "mt_tasks": ["MT-17"], "keywords": []}
        queries = build_resurface_queries(ctx)
        self.assertTrue(any(q.get("mt_task") == "MT-17" for q in queries))

    def test_keywords_generate_query(self):
        from resurfacer_hook import build_resurface_queries
        ctx = {"modules": [], "frontiers": [], "mt_tasks": [], "keywords": ["trading"]}
        queries = build_resurface_queries(ctx)
        self.assertTrue(any(q.get("keywords") == ["trading"] for q in queries))

    def test_empty_context_no_queries(self):
        from resurfacer_hook import build_resurface_queries
        ctx = {"modules": [], "frontiers": [], "mt_tasks": [], "keywords": []}
        queries = build_resurface_queries(ctx)
        self.assertEqual(queries, [])

    def test_dedup_frontier_from_module(self):
        from resurfacer_hook import build_resurface_queries
        # If both module=context-monitor and frontier=3 detected, don't double-query
        ctx = {"modules": ["context-monitor"], "frontiers": [3], "mt_tasks": [], "keywords": []}
        queries = build_resurface_queries(ctx)
        frontier_queries = [q for q in queries if q.get("frontier") == 3]
        self.assertEqual(len(frontier_queries), 1)


class TestHookHandler(unittest.TestCase):
    """Test the full hook handler end-to-end."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        with open(self.log_path, "w") as f:
            f.write(SAMPLE_LOG)

    def test_returns_none_for_no_context(self):
        from resurfacer_hook import handle_prompt
        result = handle_prompt("hello there", self.log_path)
        self.assertIsNone(result)

    def test_returns_findings_for_module(self):
        from resurfacer_hook import handle_prompt
        result = handle_prompt("working on context-monitor", self.log_path)
        self.assertIsNotNone(result)
        self.assertIn("Relevant Past Findings", result)
        self.assertIn("CShip", result)  # Frontier 3+5 finding
        self.assertIn("ContextGuard", result)  # Frontier 3 finding

    def test_returns_findings_for_mt_task(self):
        from resurfacer_hook import handle_prompt
        result = handle_prompt("continuing MT-17 design work", self.log_path)
        self.assertIsNotNone(result)
        self.assertIn("Design Studio", result)

    def test_returns_findings_for_frontier(self):
        from resurfacer_hook import handle_prompt
        result = handle_prompt("Frontier 4 agent guard improvements", self.log_path)
        self.assertIsNotNone(result)
        self.assertIn("SafeAgent", result)

    def test_returns_none_for_missing_log(self):
        from resurfacer_hook import handle_prompt
        result = handle_prompt("working on context-monitor", "/nonexistent/path.md")
        self.assertIsNone(result)

    def test_limits_output_length(self):
        from resurfacer_hook import handle_prompt
        result = handle_prompt("working on context-monitor", self.log_path, max_findings=1)
        self.assertIsNotNone(result)
        # Should only have 1 finding entry
        lines = [l for l in result.strip().splitlines() if l.startswith("- [")]
        self.assertEqual(len(lines), 1)

    def test_combines_multiple_context_hits(self):
        from resurfacer_hook import handle_prompt
        result = handle_prompt("Frontier 1 memory and MT-17 design", self.log_path)
        self.assertIsNotNone(result)
        # Should find memory finding AND MT-17 finding
        self.assertIn("traul", result)  # Frontier 1
        self.assertIn("Design Studio", result)  # MT-17


class TestHookJsonOutput(unittest.TestCase):
    """Test the hook produces valid JSON for Claude Code."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        with open(self.log_path, "w") as f:
            f.write(SAMPLE_LOG)

    def test_hook_output_is_valid_json(self):
        from resurfacer_hook import generate_hook_output
        result = generate_hook_output("working on context-monitor", self.log_path)
        if result is not None:
            parsed = json.loads(result)
            self.assertIn("additionalContext", parsed)

    def test_hook_output_empty_for_no_context(self):
        from resurfacer_hook import generate_hook_output
        result = generate_hook_output("hello", self.log_path)
        self.assertIsNone(result)

    def test_hook_output_has_prefix(self):
        from resurfacer_hook import generate_hook_output
        result = generate_hook_output("working on agent-guard", self.log_path)
        if result is not None:
            parsed = json.loads(result)
            ctx = parsed["additionalContext"]
            self.assertIn("Past findings", ctx)


class TestCooldown(unittest.TestCase):
    """Test that hook doesn't fire on every single prompt."""

    def test_cooldown_prevents_rapid_fire(self):
        from resurfacer_hook import ResurfacerState
        state = ResurfacerState()
        # First call should be allowed
        self.assertTrue(state.should_fire())
        state.mark_fired()
        # Immediate second call should be blocked
        self.assertFalse(state.should_fire())

    def test_cooldown_resets_after_interval(self):
        import time
        from resurfacer_hook import ResurfacerState
        state = ResurfacerState(cooldown_seconds=0.1)
        state.mark_fired()
        time.sleep(0.15)
        self.assertTrue(state.should_fire())

    def test_cooldown_resets_on_new_context(self):
        from resurfacer_hook import ResurfacerState
        state = ResurfacerState()
        state.mark_fired(context_key="context-monitor")
        # Different context should be allowed
        self.assertTrue(state.should_fire(context_key="agent-guard"))

    def test_same_context_blocked(self):
        from resurfacer_hook import ResurfacerState
        state = ResurfacerState()
        state.mark_fired(context_key="context-monitor")
        self.assertFalse(state.should_fire(context_key="context-monitor"))


if __name__ == "__main__":
    unittest.main()
