#!/usr/bin/env python3
"""
agent_registry.py — Discover and catalogue all Claude Code agents.

Scans ~/.claude/agents/*.md, parses YAML frontmatter, and returns
a structured view of every installed agent with name, model, maxTurns,
disallowedTools, cost tier, and description.

Cost tier is derived from model:
  haiku  → LOW   (~$0.25/MTok input)
  sonnet → MED   (~$3/MTok input)
  opus   → HIGH  (~$15/MTok input)
  (none) → ?     (inherits from parent — unknown cost)

Usage:
  python3 agent_registry.py list          # ASCII table of all agents
  python3 agent_registry.py json          # JSON output
  python3 agent_registry.py count         # Number of installed agents
  python3 agent_registry.py check <name>  # Details for one agent

Env vars:
  CLAUDE_AGENTS_DIR  — Override default ~/.claude/agents/ path
"""

import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_AGENTS_DIR = Path.home() / ".claude" / "agents"

COST_TIER: Dict[str, str] = {
    "haiku": "LOW",
    "sonnet": "MED",
    "opus": "HIGH",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AgentEntry:
    name: str
    model: str            # "haiku", "sonnet", "opus", or "" (inherited)
    max_turns: int        # 0 = not set
    disallowed_tools: List[str]
    description: str
    cost_tier: str        # "LOW", "MED", "HIGH", "?"
    source_file: str      # filename only (not full path)
    tools: List[str]      # allowed tools (empty = all)
    effort: str           # "low", "medium", "high", "max", or ""
    color: str            # agent color tag or ""


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

def _parse_frontmatter(content: str) -> Dict[str, str]:
    """
    Extract key: value pairs from YAML frontmatter (between --- delimiters).

    Handles:
      - Simple string values: key: value
      - Omitted keys (returns empty string for missing)
      - No frontmatter (returns empty dict)

    Does NOT handle: nested YAML, multi-line values, quoted strings with colons.
    Those don't appear in Claude Code agent frontmatter.
    """
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    result = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


def _parse_list_field(value: str) -> List[str]:
    """Parse a comma-separated field value into a list. E.g. 'Edit, Write' → ['Edit', 'Write']."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _cost_tier(model: str) -> str:
    """Map model name to cost tier."""
    model_lower = model.lower()
    for key, tier in COST_TIER.items():
        if key in model_lower:
            return tier
    return "?" if not model else "?"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_agents(agents_dir: Optional[Path] = None) -> List[AgentEntry]:
    """
    Scan agents_dir for *.md files and parse each into an AgentEntry.

    Files without a `name:` frontmatter field are skipped.
    Returns agents sorted by name.
    """
    if agents_dir is None:
        env_dir = os.environ.get("CLAUDE_AGENTS_DIR", "")
        agents_dir = Path(env_dir) if env_dir else DEFAULT_AGENTS_DIR

    if not agents_dir.exists():
        return []

    entries = []
    for md_file in sorted(agents_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        fm = _parse_frontmatter(content)
        name = fm.get("name", "").strip()
        if not name:
            continue  # Skip files without a name field

        model = fm.get("model", "").strip()
        max_turns_str = fm.get("maxTurns", "0").strip()
        try:
            max_turns = int(max_turns_str)
        except ValueError:
            max_turns = 0

        entries.append(AgentEntry(
            name=name,
            model=model,
            max_turns=max_turns,
            disallowed_tools=_parse_list_field(fm.get("disallowedTools", "")),
            description=fm.get("description", "")[:120],  # Truncate long descriptions
            cost_tier=_cost_tier(model),
            source_file=md_file.name,
            tools=_parse_list_field(fm.get("tools", "")),
            effort=fm.get("effort", "").strip(),
            color=fm.get("color", "").strip(),
        ))

    return sorted(entries, key=lambda e: e.name)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_table(agents: List[AgentEntry]) -> str:
    """Render agents as a fixed-width ASCII table."""
    if not agents:
        return "No agents found in ~/.claude/agents/"

    # Column widths
    W_NAME = max(len("NAME"), max(len(a.name) for a in agents))
    W_MODEL = max(len("MODEL"), max(len(a.model) if a.model else len("inherited") for a in agents))
    W_TURNS = 6
    W_TIER = 4
    W_TOOLS = 20

    header = (
        f"{'NAME':<{W_NAME}}  {'MODEL':<{W_MODEL}}  {'TURNS':<{W_TURNS}}  "
        f"{'TIER':<{W_TIER}}  {'DISALLOWED':<{W_TOOLS}}"
    )
    sep = "-" * len(header)

    rows = [header, sep]
    for a in agents:
        model_str = a.model if a.model else "inherited"
        turns_str = str(a.max_turns) if a.max_turns else "-"
        disallowed = ", ".join(a.disallowed_tools) if a.disallowed_tools else "none"
        if len(disallowed) > W_TOOLS:
            disallowed = disallowed[:W_TOOLS - 2] + ".."
        rows.append(
            f"{a.name:<{W_NAME}}  {model_str:<{W_MODEL}}  {turns_str:<{W_TURNS}}  "
            f"{a.cost_tier:<{W_TIER}}  {disallowed:<{W_TOOLS}}"
        )

    rows.append(sep)
    rows.append(f"Total: {len(agents)} agents")
    return "\n".join(rows)


def format_json(agents: List[AgentEntry]) -> str:
    """Render agents as JSON."""
    return json.dumps([asdict(a) for a in agents], indent=2)


def format_detail(agent: AgentEntry) -> str:
    """Render a single agent's full details."""
    lines = [
        f"Agent: {agent.name}",
        f"  File:         {agent.source_file}",
        f"  Model:        {agent.model or 'inherited'}",
        f"  Cost tier:    {agent.cost_tier}",
        f"  Max turns:    {agent.max_turns or 'unlimited'}",
        f"  Effort:       {agent.effort or 'not set'}",
        f"  Color:        {agent.color or 'not set'}",
        f"  Tools:        {', '.join(agent.tools) if agent.tools else 'all'}",
        f"  Disallowed:   {', '.join(agent.disallowed_tools) if agent.disallowed_tools else 'none'}",
    ]
    if agent.description:
        lines.append(f"  Description:  {agent.description}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Briefing summary (for /cca-init integration)
# ---------------------------------------------------------------------------

def briefing_summary(agents: Optional[List[AgentEntry]] = None) -> str:
    """
    One-line summary for /cca-init briefing.
    E.g.: "Agents: 15 installed (4 CCA, 11 GSD) | HIGH: 2, MED: 6, LOW: 3, ?: 4"
    """
    if agents is None:
        agents = discover_agents()

    if not agents:
        return "Agents: none installed"

    cca = sum(1 for a in agents if a.name.startswith("cca-") or a.name == "senior-reviewer")
    gsd = sum(1 for a in agents if a.name.startswith("gsd-"))
    other = len(agents) - cca - gsd

    tiers: Dict[str, int] = {"HIGH": 0, "MED": 0, "LOW": 0, "?": 0}
    for a in agents:
        tiers[a.cost_tier] = tiers.get(a.cost_tier, 0) + 1

    tier_str = " | ".join(f"{k}:{v}" for k, v in tiers.items() if v > 0)
    parts = [f"{len(agents)} installed"]
    if cca:
        parts.append(f"{cca} CCA")
    if gsd:
        parts.append(f"{gsd} GSD")
    if other:
        parts.append(f"{other} other")

    return f"Agents: {', '.join(parts)} | Cost tiers: {tier_str}"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "list"

    agents = discover_agents()

    if cmd == "list":
        print(format_table(agents))

    elif cmd == "json":
        print(format_json(agents))

    elif cmd == "count":
        print(len(agents))

    elif cmd == "briefing":
        print(briefing_summary(agents))

    elif cmd == "check":
        if len(args) < 2:
            print("Usage: agent_registry.py check <name>", file=sys.stderr)
            sys.exit(1)
        target = args[1].lower()
        found = [a for a in agents if a.name.lower() == target]
        if not found:
            print(f"Agent not found: {target}", file=sys.stderr)
            sys.exit(1)
        print(format_detail(found[0]))

    else:
        print(f"Unknown command: {cmd}. Use: list, json, count, briefing, check <name>", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
