#!/usr/bin/env python3
"""Tests for agent-guard/agent_cost_reader.py"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent_cost_reader import (
    AgentCostEntry,
    BudgetSummary,
    aggregate,
    check_expensive_agents,
    format_briefing,
    format_json,
    format_table,
    format_top,
    load_budget,
    read_summary,
    _cost_for_tokens,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_budget(spawns=None, date="2026-04-02", total_count=None, total_tokens=None):
    """Build a raw budget dict like spawn_budget_hook writes."""
    if spawns is None:
        spawns = []
    tc = total_count if total_count is not None else len(spawns)
    tt = total_tokens if total_tokens is not None else sum(s.get("estimated_tokens", 0) for s in spawns)
    return {
        "date": date,
        "spawns": spawns,
        "total_count": tc,
        "total_estimated_tokens": tt,
    }


def _spawn(agent_type="cca-reviewer", model="inherited", tokens=40000, time="10:00:00", desc="task"):
    return {"type": agent_type, "model": model, "estimated_tokens": tokens,
            "time": time, "description": desc}


def _write_budget(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# Tests: _cost_for_tokens
# ---------------------------------------------------------------------------

class TestCostForTokens(unittest.TestCase):

    def test_sonnet_rate(self):
        cost = _cost_for_tokens(1_000_000, "sonnet")
        self.assertAlmostEqual(cost, 4.50, places=2)

    def test_haiku_rate(self):
        cost = _cost_for_tokens(1_000_000, "haiku")
        self.assertAlmostEqual(cost, 0.40, places=2)

    def test_opus_rate(self):
        cost = _cost_for_tokens(1_000_000, "opus")
        self.assertAlmostEqual(cost, 21.00, places=2)

    def test_inherited_uses_sonnet_rate(self):
        cost_inherited = _cost_for_tokens(40_000, "inherited")
        cost_sonnet = _cost_for_tokens(40_000, "sonnet")
        self.assertAlmostEqual(cost_inherited, cost_sonnet, places=6)

    def test_unknown_model_uses_sonnet_rate(self):
        cost = _cost_for_tokens(40_000, "gpt-4")
        cost_sonnet = _cost_for_tokens(40_000, "sonnet")
        self.assertAlmostEqual(cost, cost_sonnet, places=6)

    def test_model_with_version_suffix(self):
        # "claude-sonnet-4-6" contains "sonnet" → sonnet rate
        cost = _cost_for_tokens(1_000_000, "claude-sonnet-4-6")
        self.assertAlmostEqual(cost, 4.50, places=2)

    def test_zero_tokens(self):
        self.assertEqual(_cost_for_tokens(0, "sonnet"), 0.0)


# ---------------------------------------------------------------------------
# Tests: load_budget
# ---------------------------------------------------------------------------

class TestLoadBudget(unittest.TestCase):

    def test_loads_valid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"date": "2026-04-02", "spawns": [], "total_count": 0}, f)
            path = Path(f.name)
        try:
            result = load_budget(path)
            self.assertIsNotNone(result)
            self.assertEqual(result["date"], "2026-04-02")
        finally:
            path.unlink()

    def test_missing_file_returns_none(self):
        result = load_budget(Path("/nonexistent/spawn_budget.json"))
        self.assertIsNone(result)

    def test_malformed_json_returns_none(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("not json {{{{")
            path = Path(f.name)
        try:
            result = load_budget(path)
            self.assertIsNone(result)
        finally:
            path.unlink()

    def test_env_var_overrides_path(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"date": "2026-04-02", "spawns": [], "total_count": 99,
                       "total_estimated_tokens": 0}, f)
            path = Path(f.name)
        try:
            with unittest.mock.patch.dict(os.environ, {"CCA_SPAWN_BUDGET_FILE": str(path)}):
                result = load_budget()
                self.assertIsNotNone(result)
                self.assertEqual(result["total_count"], 99)
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# Tests: aggregate
# ---------------------------------------------------------------------------

class TestAggregate(unittest.TestCase):

    def test_single_agent_type(self):
        raw = _make_budget([_spawn("cca-reviewer", tokens=40000)] * 3)
        summary = aggregate(raw)
        self.assertEqual(len(summary.by_agent), 1)
        entry = summary.by_agent[0]
        self.assertEqual(entry.agent_type, "cca-reviewer")
        self.assertEqual(entry.invocations, 3)
        self.assertEqual(entry.total_tokens, 120_000)

    def test_multiple_agent_types(self):
        spawns = [_spawn("cca-reviewer")] * 4 + [_spawn("general-purpose")] * 2
        raw = _make_budget(spawns)
        summary = aggregate(raw)
        self.assertEqual(len(summary.by_agent), 2)
        types = [e.agent_type for e in summary.by_agent]
        self.assertIn("cca-reviewer", types)
        self.assertIn("general-purpose", types)

    def test_sorted_by_tokens_descending(self):
        spawns = (
            [_spawn("cheap-agent", tokens=10_000)] * 2 +
            [_spawn("expensive-agent", tokens=100_000)] * 1
        )
        raw = _make_budget(spawns)
        summary = aggregate(raw)
        self.assertEqual(summary.by_agent[0].agent_type, "expensive-agent")
        self.assertEqual(summary.by_agent[1].agent_type, "cheap-agent")

    def test_avg_tokens(self):
        raw = _make_budget([_spawn("alpha", tokens=60_000)] * 3)
        summary = aggregate(raw)
        self.assertEqual(summary.by_agent[0].avg_tokens, 60_000)

    def test_models_seen_unique(self):
        spawns = [
            _spawn("alpha", model="sonnet"),
            _spawn("alpha", model="haiku"),
            _spawn("alpha", model="sonnet"),
        ]
        raw = _make_budget(spawns)
        summary = aggregate(raw)
        self.assertEqual(sorted(summary.by_agent[0].models_seen), ["haiku", "sonnet"])

    def test_total_tokens_matches_raw(self):
        spawns = [_spawn(tokens=40_000)] * 5
        raw = _make_budget(spawns, total_tokens=200_000)
        summary = aggregate(raw)
        self.assertEqual(summary.total_tokens, 200_000)

    def test_total_invocations_matches_raw(self):
        spawns = [_spawn()] * 7
        raw = _make_budget(spawns, total_count=7)
        summary = aggregate(raw)
        self.assertEqual(summary.total_invocations, 7)

    def test_estimated_usd_positive(self):
        raw = _make_budget([_spawn(tokens=40_000)])
        summary = aggregate(raw)
        self.assertGreater(summary.total_estimated_usd, 0)

    def test_empty_spawns(self):
        raw = _make_budget([])
        summary = aggregate(raw)
        self.assertEqual(summary.by_agent, [])
        self.assertEqual(summary.total_invocations, 0)


# ---------------------------------------------------------------------------
# Tests: read_summary
# ---------------------------------------------------------------------------

class TestReadSummary(unittest.TestCase):

    def test_returns_none_for_missing_file(self):
        result = read_summary(Path("/nonexistent/path.json"))
        self.assertIsNone(result)

    def test_returns_summary_for_valid_file(self):
        raw = _make_budget([_spawn()])
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(raw, f)
            path = Path(f.name)
        try:
            result = read_summary(path)
            self.assertIsNotNone(result)
            self.assertIsInstance(result, BudgetSummary)
        finally:
            path.unlink()

    def test_returns_none_for_empty_spawns(self):
        raw = _make_budget([])
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(raw, f)
            path = Path(f.name)
        try:
            result = read_summary(path)
            self.assertIsNone(result)
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# Tests: format_table
# ---------------------------------------------------------------------------

class TestFormatTable(unittest.TestCase):

    def _make_summary(self, n_reviewer=4, n_general=2):
        spawns = [_spawn("cca-reviewer")] * n_reviewer + [_spawn("general-purpose")] * n_general
        return aggregate(_make_budget(spawns, total_count=n_reviewer + n_general,
                                      total_tokens=(n_reviewer + n_general) * 40_000))

    def test_returns_string(self):
        self.assertIsInstance(format_table(self._make_summary()), str)

    def test_contains_agent_names(self):
        result = format_table(self._make_summary(4, 2))
        self.assertIn("cca-reviewer", result)
        self.assertIn("general-purpose", result)

    def test_contains_total_row(self):
        result = format_table(self._make_summary())
        self.assertIn("TOTAL", result)

    def test_empty_summary_returns_message(self):
        empty = BudgetSummary(date="2026-04-02", total_invocations=0,
                              total_tokens=0, total_estimated_usd=0.0, by_agent=[])
        result = format_table(empty)
        self.assertIn("No spawn data", result)

    def test_contains_cost_model_note(self):
        result = format_table(self._make_summary())
        self.assertIn("Cost model", result)


# ---------------------------------------------------------------------------
# Tests: format_briefing
# ---------------------------------------------------------------------------

class TestFormatBriefing(unittest.TestCase):

    def test_none_returns_none_message(self):
        result = format_briefing(None)
        self.assertIn("none", result)

    def test_contains_invocation_count(self):
        raw = _make_budget([_spawn()] * 5, total_count=5)
        summary = aggregate(raw)
        result = format_briefing(summary)
        self.assertIn("5", result)

    def test_contains_top_agent(self):
        raw = _make_budget([_spawn("cca-reviewer")] * 3)
        summary = aggregate(raw)
        result = format_briefing(summary)
        self.assertIn("cca-reviewer", result)

    def test_contains_cost(self):
        raw = _make_budget([_spawn(tokens=40_000)])
        summary = aggregate(raw)
        result = format_briefing(summary)
        self.assertIn("$", result)


# ---------------------------------------------------------------------------
# Tests: format_top
# ---------------------------------------------------------------------------

class TestFormatTop(unittest.TestCase):

    def test_limits_to_n(self):
        spawns = (
            [_spawn("alpha")] * 3 + [_spawn("beta")] * 2 +
            [_spawn("gamma")] * 1 + [_spawn("delta")] * 4
        )
        summary = aggregate(_make_budget(spawns))
        result = format_top(summary, n=2)
        # Should show exactly 2 agents
        self.assertIn("Top 2", result)
        self.assertNotIn("gamma", result)

    def test_empty_returns_message(self):
        empty = BudgetSummary(date="", total_invocations=0, total_tokens=0,
                              total_estimated_usd=0.0, by_agent=[])
        result = format_top(empty)
        self.assertIn("No spawn data", result)


# ---------------------------------------------------------------------------
# Tests: check_expensive_agents
# ---------------------------------------------------------------------------

class TestCheckExpensiveAgents(unittest.TestCase):

    def test_none_summary_returns_none(self):
        self.assertIsNone(check_expensive_agents(None))

    def test_under_threshold_returns_none(self):
        raw = _make_budget([_spawn("cheap", tokens=100)])
        summary = aggregate(raw)
        result = check_expensive_agents(summary, warn_threshold_usd=100.0)
        self.assertIsNone(result)

    def test_over_threshold_returns_warning(self):
        # cca-reviewer with 1M tokens → $4.50 USD at sonnet rate
        raw = _make_budget([_spawn("cca-reviewer", tokens=1_000_000)])
        summary = aggregate(raw)
        result = check_expensive_agents(summary, warn_threshold_usd=1.0)
        self.assertIsNotNone(result)
        self.assertIn("cca-reviewer", result)
        self.assertIn("WARNING", result)

    def test_multiple_expensive_agents_all_named(self):
        spawns = [
            _spawn("alpha", tokens=500_000),
            _spawn("beta", tokens=500_000),
        ]
        summary = aggregate(_make_budget(spawns))
        result = check_expensive_agents(summary, warn_threshold_usd=1.0)
        self.assertIn("alpha", result)
        self.assertIn("beta", result)


# ---------------------------------------------------------------------------
# Tests: format_json
# ---------------------------------------------------------------------------

class TestFormatJson(unittest.TestCase):

    def test_produces_valid_json(self):
        raw = _make_budget([_spawn("cca-reviewer")] * 3, total_count=3)
        summary = aggregate(raw)
        result = json.loads(format_json(summary))
        self.assertIsInstance(result, dict)

    def test_all_top_level_fields_present(self):
        raw = _make_budget([_spawn()])
        summary = aggregate(raw)
        result = json.loads(format_json(summary))
        for key in ["date", "total_invocations", "total_tokens",
                    "total_estimated_usd", "by_agent"]:
            self.assertIn(key, result)

    def test_by_agent_entry_fields(self):
        raw = _make_budget([_spawn("cca-reviewer")])
        summary = aggregate(raw)
        result = json.loads(format_json(summary))
        entry = result["by_agent"][0]
        for key in ["agent_type", "invocations", "total_tokens",
                    "avg_tokens", "estimated_usd", "models_seen"]:
            self.assertIn(key, entry)


import unittest.mock  # noqa: E402 — needed for TestLoadBudget.test_env_var_overrides_path


if __name__ == "__main__":
    unittest.main()
