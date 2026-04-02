#!/usr/bin/env python3
"""Tests for agent-guard/agent_registry.py"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent_registry import (
    AgentEntry,
    _cost_tier,
    _parse_frontmatter,
    _parse_list_field,
    briefing_summary,
    discover_agents,
    format_detail,
    format_json,
    format_table,
)


def _write_agent(dir_path: Path, filename: str, content: str) -> Path:
    p = dir_path / filename
    p.write_text(content)
    return p


FULL_AGENT_MD = """\
---
name: test-agent
description: A test agent for unit testing.
model: sonnet
maxTurns: 25
disallowedTools: Edit, Write
tools: Read, Bash, Grep
effort: high
color: cyan
---

# Test Agent

You are a test agent.
"""

MINIMAL_AGENT_MD = """\
---
name: minimal-agent
---

Just the name, nothing else.
"""

NO_NAME_MD = """\
---
description: No name field here
model: haiku
---

Content.
"""

NO_FRONTMATTER_MD = """\
# Just a markdown file

No frontmatter at all.
"""


class TestParseFrontmatter(unittest.TestCase):

    def test_parses_all_fields(self):
        fm = _parse_frontmatter(FULL_AGENT_MD)
        self.assertEqual(fm["name"], "test-agent")
        self.assertEqual(fm["model"], "sonnet")
        self.assertEqual(fm["maxTurns"], "25")
        self.assertEqual(fm["disallowedTools"], "Edit, Write")
        self.assertEqual(fm["tools"], "Read, Bash, Grep")
        self.assertEqual(fm["effort"], "high")
        self.assertEqual(fm["color"], "cyan")

    def test_minimal_frontmatter(self):
        fm = _parse_frontmatter(MINIMAL_AGENT_MD)
        self.assertEqual(fm["name"], "minimal-agent")
        self.assertNotIn("model", fm)

    def test_no_frontmatter_returns_empty(self):
        fm = _parse_frontmatter(NO_FRONTMATTER_MD)
        self.assertEqual(fm, {})

    def test_missing_key_not_in_result(self):
        fm = _parse_frontmatter(MINIMAL_AGENT_MD)
        self.assertNotIn("maxTurns", fm)
        self.assertNotIn("disallowedTools", fm)

    def test_empty_string_returns_empty(self):
        fm = _parse_frontmatter("")
        self.assertEqual(fm, {})


class TestParseListField(unittest.TestCase):

    def test_comma_separated(self):
        result = _parse_list_field("Edit, Write, Agent")
        self.assertEqual(result, ["Edit", "Write", "Agent"])

    def test_single_item(self):
        result = _parse_list_field("Read")
        self.assertEqual(result, ["Read"])

    def test_empty_string(self):
        result = _parse_list_field("")
        self.assertEqual(result, [])

    def test_strips_whitespace(self):
        result = _parse_list_field("  Edit ,  Write  ")
        self.assertEqual(result, ["Edit", "Write"])


class TestCostTier(unittest.TestCase):

    def test_haiku_is_low(self):
        self.assertEqual(_cost_tier("haiku"), "LOW")

    def test_sonnet_is_med(self):
        self.assertEqual(_cost_tier("sonnet"), "MED")

    def test_opus_is_high(self):
        self.assertEqual(_cost_tier("opus"), "HIGH")

    def test_unknown_model_is_question(self):
        self.assertEqual(_cost_tier("gpt-4"), "?")

    def test_empty_model_is_question(self):
        self.assertEqual(_cost_tier(""), "?")

    def test_model_with_version_suffix(self):
        self.assertEqual(_cost_tier("claude-sonnet-4-6"), "MED")
        self.assertEqual(_cost_tier("claude-haiku-4-5"), "LOW")
        self.assertEqual(_cost_tier("claude-opus-4-6"), "HIGH")


class TestDiscoverAgents(unittest.TestCase):

    def test_discovers_agents_from_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_agent(d, "agent-a.md", FULL_AGENT_MD)
            _write_agent(d, "agent-b.md", MINIMAL_AGENT_MD)
            agents = discover_agents(d)
            self.assertEqual(len(agents), 2)

    def test_skips_files_without_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_agent(d, "named.md", FULL_AGENT_MD)
            _write_agent(d, "noname.md", NO_NAME_MD)
            _write_agent(d, "nofm.md", NO_FRONTMATTER_MD)
            agents = discover_agents(d)
            self.assertEqual(len(agents), 1)
            self.assertEqual(agents[0].name, "test-agent")

    def test_sorted_by_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_agent(d, "z-agent.md", "---\nname: z-agent\n---\n")
            _write_agent(d, "a-agent.md", "---\nname: a-agent\n---\n")
            _write_agent(d, "m-agent.md", "---\nname: m-agent\n---\n")
            agents = discover_agents(d)
            names = [a.name for a in agents]
            self.assertEqual(names, sorted(names))

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents = discover_agents(Path(tmpdir))
            self.assertEqual(agents, [])

    def test_nonexistent_dir_returns_empty(self):
        agents = discover_agents(Path("/nonexistent/path/that/does/not/exist"))
        self.assertEqual(agents, [])

    def test_full_agent_parsed_correctly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_agent(d, "full.md", FULL_AGENT_MD)
            agents = discover_agents(d)
            self.assertEqual(len(agents), 1)
            a = agents[0]
            self.assertEqual(a.name, "test-agent")
            self.assertEqual(a.model, "sonnet")
            self.assertEqual(a.max_turns, 25)
            self.assertEqual(a.disallowed_tools, ["Edit", "Write"])
            self.assertEqual(a.tools, ["Read", "Bash", "Grep"])
            self.assertEqual(a.cost_tier, "MED")
            self.assertEqual(a.effort, "high")
            self.assertEqual(a.color, "cyan")

    def test_minimal_agent_has_safe_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_agent(d, "minimal.md", MINIMAL_AGENT_MD)
            agents = discover_agents(d)
            a = agents[0]
            self.assertEqual(a.name, "minimal-agent")
            self.assertEqual(a.model, "")
            self.assertEqual(a.max_turns, 0)
            self.assertEqual(a.disallowed_tools, [])
            self.assertEqual(a.cost_tier, "?")

    def test_env_var_overrides_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_agent(d, "env-agent.md", "---\nname: env-agent\n---\n")
            with unittest.mock.patch.dict(os.environ, {"CLAUDE_AGENTS_DIR": str(d)}):
                agents = discover_agents()
                names = [a.name for a in agents]
                self.assertIn("env-agent", names)


class TestFormatTable(unittest.TestCase):

    def _make_agent(self, name: str, model: str = "sonnet", max_turns: int = 20) -> AgentEntry:
        return AgentEntry(
            name=name, model=model, max_turns=max_turns,
            disallowed_tools=["Edit"], description="desc", cost_tier=_cost_tier(model),
            source_file=f"{name}.md", tools=[], effort="", color="",
        )

    def test_returns_string(self):
        agents = [self._make_agent("alpha"), self._make_agent("beta")]
        result = format_table(agents)
        self.assertIsInstance(result, str)

    def test_contains_all_names(self):
        agents = [self._make_agent("alpha"), self._make_agent("beta", "haiku")]
        result = format_table(agents)
        self.assertIn("alpha", result)
        self.assertIn("beta", result)

    def test_shows_total_count(self):
        agents = [self._make_agent("a"), self._make_agent("b"), self._make_agent("c")]
        result = format_table(agents)
        self.assertIn("Total: 3", result)

    def test_empty_agents_returns_message(self):
        result = format_table([])
        self.assertIn("No agents", result)

    def test_inherited_model_displayed(self):
        agent = AgentEntry(
            name="gsd-test", model="", max_turns=0,
            disallowed_tools=[], description="", cost_tier="?",
            source_file="gsd-test.md", tools=[], effort="", color="",
        )
        result = format_table([agent])
        self.assertIn("inherited", result)


class TestFormatJson(unittest.TestCase):

    def test_produces_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent(Path(tmpdir), "a.md", FULL_AGENT_MD)
            agents = discover_agents(Path(tmpdir))
            result = format_json(agents)
            parsed = json.loads(result)
            self.assertIsInstance(parsed, list)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0]["name"], "test-agent")

    def test_all_fields_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_agent(Path(tmpdir), "a.md", FULL_AGENT_MD)
            agents = discover_agents(Path(tmpdir))
            parsed = json.loads(format_json(agents))
            entry = parsed[0]
            for key in ["name", "model", "max_turns", "disallowed_tools", "cost_tier", "source_file"]:
                self.assertIn(key, entry)


class TestBriefingSummary(unittest.TestCase):

    def test_empty_returns_message(self):
        result = briefing_summary([])
        self.assertIn("none", result)

    def test_counts_agents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_agent(d, "cca-a.md", "---\nname: cca-a\nmodel: sonnet\n---\n")
            _write_agent(d, "gsd-b.md", "---\nname: gsd-b\n---\n")
            agents = discover_agents(d)
            result = briefing_summary(agents)
            self.assertIn("2 installed", result)
            self.assertIn("1 CCA", result)
            self.assertIn("1 GSD", result)

    def test_shows_cost_tiers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_agent(d, "a.md", "---\nname: alpha\nmodel: haiku\n---\n")
            _write_agent(d, "b.md", "---\nname: beta\nmodel: opus\n---\n")
            agents = discover_agents(d)
            result = briefing_summary(agents)
            self.assertIn("LOW:1", result)
            self.assertIn("HIGH:1", result)


import unittest.mock  # noqa: E402 — needed for TestDiscoverAgents.test_env_var_overrides_dir


if __name__ == "__main__":
    unittest.main()
