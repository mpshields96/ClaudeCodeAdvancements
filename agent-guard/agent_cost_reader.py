#!/usr/bin/env python3
"""
agent_cost_reader.py — Aggregate spawn budget data by agent type.

Reads ~/.claude-spawn-budget.json (written by hooks/spawn_budget_hook.py)
and produces a per-agent breakdown of invocation counts, estimated token
usage, and estimated USD cost.

Cost model (input + output combined rough estimate, per 1M tokens):
  haiku    → $0.40/MTok  (input $0.25 + output $1.25, ~75% input)
  sonnet   → $4.50/MTok  (input $3 + output $15, ~70% input)
  opus     → $21/MTok    (input $15 + output $75, ~70% input)
  inherited → uses sonnet pricing as conservative default

Usage:
  python3 agent_cost_reader.py summary     # ASCII table by agent type
  python3 agent_cost_reader.py json        # JSON output
  python3 agent_cost_reader.py briefing    # One-line for /cca-init
  python3 agent_cost_reader.py top [N]     # Top N most expensive agents (default 5)

Env vars:
  CCA_SPAWN_BUDGET_FILE  — Override default ~/.claude-spawn-budget.json
"""

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

BUDGET_FILE = Path.home() / ".claude-spawn-budget.json"

# Cost per million tokens (blended input+output estimate)
COST_PER_MTOK: Dict[str, float] = {
    "haiku": 0.40,
    "sonnet": 4.50,
    "opus": 21.00,
    "inherited": 4.50,   # conservative: assume sonnet
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AgentCostEntry:
    agent_type: str
    invocations: int
    total_tokens: int
    estimated_usd: float
    models_seen: List[str]       # unique models observed for this type

    @property
    def avg_tokens(self) -> int:
        return self.total_tokens // self.invocations if self.invocations else 0


@dataclass
class BudgetSummary:
    date: str                    # "YYYY-MM-DD" or "" if no data
    total_invocations: int
    total_tokens: int
    total_estimated_usd: float
    by_agent: List[AgentCostEntry]   # sorted by total_tokens desc


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_budget(budget_file: Optional[Path] = None) -> Optional[dict]:
    """
    Load raw spawn budget JSON. Returns None if file missing or unreadable.
    """
    if budget_file is None:
        env_path = os.environ.get("CCA_SPAWN_BUDGET_FILE", "")
        budget_file = Path(env_path) if env_path else BUDGET_FILE

    if not budget_file.exists():
        return None

    try:
        return json.loads(budget_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _cost_for_tokens(tokens: int, model: str) -> float:
    """Estimate USD cost for a given token count and model."""
    model_lower = model.lower()
    rate = COST_PER_MTOK.get("inherited")  # default
    for key, cost in COST_PER_MTOK.items():
        if key in model_lower:
            rate = cost
            break
    return tokens / 1_000_000 * rate


def aggregate(raw: dict) -> BudgetSummary:
    """
    Aggregate raw spawn budget data into per-agent cost entries.
    """
    spawns = raw.get("spawns", [])

    # Group by agent type
    groups: Dict[str, List[dict]] = {}
    for spawn in spawns:
        agent_type = spawn.get("type", "unknown")
        groups.setdefault(agent_type, []).append(spawn)

    entries: List[AgentCostEntry] = []
    for agent_type, agent_spawns in groups.items():
        total_tokens = sum(s.get("estimated_tokens", 0) for s in agent_spawns)
        models_seen = sorted(set(s.get("model", "inherited") for s in agent_spawns))
        # Use blended cost: each spawn has its own token estimate based on model
        estimated_usd = sum(
            _cost_for_tokens(s.get("estimated_tokens", 0), s.get("model", "inherited"))
            for s in agent_spawns
        )
        entries.append(AgentCostEntry(
            agent_type=agent_type,
            invocations=len(agent_spawns),
            total_tokens=total_tokens,
            estimated_usd=estimated_usd,
            models_seen=models_seen,
        ))

    entries.sort(key=lambda e: e.total_tokens, reverse=True)

    return BudgetSummary(
        date=raw.get("date", ""),
        total_invocations=raw.get("total_count", 0),
        total_tokens=raw.get("total_estimated_tokens", 0),
        total_estimated_usd=sum(e.estimated_usd for e in entries),
        by_agent=entries,
    )


def read_summary(budget_file: Optional[Path] = None) -> Optional[BudgetSummary]:
    """Load and aggregate budget data. Returns None if no data."""
    raw = load_budget(budget_file)
    if raw is None or not raw.get("spawns"):
        return None
    return aggregate(raw)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_table(summary: BudgetSummary) -> str:
    """Render per-agent cost breakdown as an ASCII table."""
    if not summary.by_agent:
        return f"No spawn data for {summary.date or 'today'}."

    W_TYPE = max(len("AGENT TYPE"), max(len(e.agent_type) for e in summary.by_agent))
    W_INV = max(len("CALLS"), 5)
    W_TOK = max(len("TOKENS"), 12)
    W_USD = max(len("EST. COST"), 9)

    header = (
        f"{'AGENT TYPE':<{W_TYPE}}  {'CALLS':>{W_INV}}  "
        f"{'TOKENS':>{W_TOK}}  {'EST. COST':>{W_USD}}"
    )
    sep = "-" * len(header)

    rows = [f"Spawn budget — {summary.date}", "", header, sep]
    for e in summary.by_agent:
        cost_str = f"${e.estimated_usd:.4f}"
        rows.append(
            f"{e.agent_type:<{W_TYPE}}  {e.invocations:>{W_INV}}  "
            f"{e.total_tokens:>{W_TOK},}  {cost_str:>{W_USD}}"
        )

    rows.append(sep)
    total_cost_str = f"${summary.total_estimated_usd:.4f}"
    rows.append(
        f"{'TOTAL':<{W_TYPE}}  {summary.total_invocations:>{W_INV}}  "
        f"{summary.total_tokens:>{W_TOK},}  {total_cost_str:>{W_USD}}"
    )
    rows.append("")
    rows.append(f"Cost model: inherited/sonnet=${COST_PER_MTOK['sonnet']}/MTok, "
                f"haiku=${COST_PER_MTOK['haiku']}/MTok, opus=${COST_PER_MTOK['opus']}/MTok")
    return "\n".join(rows)


def format_json(summary: BudgetSummary) -> str:
    """Render summary as JSON."""
    data = {
        "date": summary.date,
        "total_invocations": summary.total_invocations,
        "total_tokens": summary.total_tokens,
        "total_estimated_usd": round(summary.total_estimated_usd, 4),
        "by_agent": [
            {
                "agent_type": e.agent_type,
                "invocations": e.invocations,
                "total_tokens": e.total_tokens,
                "avg_tokens": e.avg_tokens,
                "estimated_usd": round(e.estimated_usd, 4),
                "models_seen": e.models_seen,
            }
            for e in summary.by_agent
        ],
    }
    return json.dumps(data, indent=2)


def format_briefing(summary: Optional[BudgetSummary]) -> str:
    """
    One-line summary for /cca-init briefing.
    E.g.: "Spawns today: 11 (~440K tokens, ~$1.98) | top: cca-reviewer×8, general-purpose×3"
    """
    if summary is None:
        return "Spawns today: none"

    top = summary.by_agent[:3]
    top_str = ", ".join(f"{e.agent_type}×{e.invocations}" for e in top)
    cost_str = f"~${summary.total_estimated_usd:.2f}"
    tok_str = f"~{summary.total_tokens // 1000}K tokens"
    return (
        f"Spawns today: {summary.total_invocations} ({tok_str}, {cost_str}) | "
        f"top: {top_str}"
    )


def format_top(summary: BudgetSummary, n: int = 5) -> str:
    """Show top N most-spawned agent types."""
    if not summary.by_agent:
        return "No spawn data."
    top = summary.by_agent[:n]
    lines = [f"Top {min(n, len(top))} agents by token cost — {summary.date}:"]
    for i, e in enumerate(top, 1):
        lines.append(
            f"  {i}. {e.agent_type}: {e.invocations} calls, "
            f"{e.total_tokens:,} tokens, ${e.estimated_usd:.4f}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Alert check (for /cca-init)
# ---------------------------------------------------------------------------

def check_expensive_agents(
    summary: Optional[BudgetSummary],
    warn_threshold_usd: float = 1.0,
) -> Optional[str]:
    """
    Return a warning string if any agent type has exceeded warn_threshold_usd,
    or None if costs are within budget.
    Used by /cca-init to surface unexpected spending.
    """
    if summary is None:
        return None
    expensive = [e for e in summary.by_agent if e.estimated_usd >= warn_threshold_usd]
    if not expensive:
        return None
    names = ", ".join(f"{e.agent_type}(${e.estimated_usd:.2f})" for e in expensive)
    return f"AGENT COST WARNING: {names} exceeded ${warn_threshold_usd:.2f} threshold today"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "summary"

    summary = read_summary()

    if cmd in ("summary", "today"):
        if summary is None:
            print(f"No spawn data found in {BUDGET_FILE}")
        else:
            print(format_table(summary))

    elif cmd == "json":
        if summary is None:
            print(json.dumps({"spawns": [], "total_invocations": 0}))
        else:
            print(format_json(summary))

    elif cmd == "briefing":
        print(format_briefing(summary))

    elif cmd == "top":
        n = int(args[1]) if len(args) > 1 else 5
        if summary is None:
            print("No spawn data.")
        else:
            print(format_top(summary, n))

    elif cmd == "alert":
        threshold = float(args[1]) if len(args) > 1 else 1.0
        msg = check_expensive_agents(summary, threshold)
        if msg:
            print(msg)
            sys.exit(1)
        else:
            print("OK — no agents over cost threshold")

    else:
        print(
            f"Unknown command: {cmd}. "
            "Use: summary, json, briefing, top [N], alert [threshold_usd]",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
