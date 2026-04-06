#!/usr/bin/env python3
"""
UserPromptSubmit hook: Auto-surface relevant FINDINGS_LOG entries.

Detects module, frontier, and MT-task context from the user's prompt,
then injects matched past findings as additionalContext so Claude has
awareness of previously reviewed tools and patterns.

Designed for lightweight, zero-API-call execution on every prompt.
Uses cooldown to avoid noise on rapid-fire prompts.

Hook type: UserPromptSubmit
Delivery: additionalContext (non-blocking, informational)

Usage as hook (settings.local.json):
    {
        "hooks": {
            "UserPromptSubmit": [{
                "type": "command",
                "command": "python3 /path/to/self-learning/resurfacer_hook.py"
            }]
        }
    }
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# Add parent dirs for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from resurfacer import resurface, format_resurface_report, MODULE_FRONTIER_MAP


# ── Constants ────────────────────────────────────────────────────────────────

# Module names to detect in prompts
MODULE_NAMES = list(MODULE_FRONTIER_MAP.keys())

# Shorthand aliases that map to module names
MODULE_ALIASES = {
    "memory": "memory-system",
    "spec": "spec-system",
    "context": "context-monitor",
    "agent guard": "agent-guard",
    "usage": "usage-dashboard",
}

# Frontier keyword mappings (detect frontier from natural language)
FRONTIER_KEYWORDS = {
    1: ["memory", "persistent memory", "cross-session"],
    2: ["spec-driven", "spec system", "requirements", "design doc"],
    3: ["context health", "context monitor", "compaction", "context rot"],
    4: ["agent guard", "multi-agent", "conflict guard", "bash guard"],
    5: ["usage dashboard", "token usage", "cost transparency"],
}

# Trading/Kalshi keywords
TRADING_KEYWORDS = ["trading", "kalshi", "polymarket", "sniper", "bet", "pnl"]

# Default findings log path (relative to CCA project root)
DEFAULT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "FINDINGS_LOG.md"
)

# Cooldown: don't fire more than once per 5 minutes per context
DEFAULT_COOLDOWN = 300


# ── Context Detection ────────────────────────────────────────────────────────

def detect_context(prompt: str) -> dict:
    """Detect module, frontier, and MT-task context from user prompt.

    Returns dict with:
        modules: list[str]   — detected module names
        frontiers: list[int] — detected frontier numbers
        mt_tasks: list[str]  — detected MT-N task IDs
        keywords: list[str]  — detected domain keywords
    """
    prompt_lower = prompt.lower()

    modules = []
    frontiers = []
    mt_tasks = []
    keywords = []

    # Detect module names (case-insensitive, full name or alias)
    for mod in MODULE_NAMES:
        if mod.lower() in prompt_lower:
            modules.append(mod)
    for alias, mod in MODULE_ALIASES.items():
        if alias.lower() in prompt_lower and mod not in modules:
            modules.append(mod)

    # Detect explicit "Frontier N" references
    for m in re.finditer(r'frontier\s+(\d+)', prompt_lower):
        num = int(m.group(1))
        if 1 <= num <= 5:
            frontiers.append(num)

    # Detect frontier from keyword context
    for frontier_num, kws in FRONTIER_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in prompt_lower and frontier_num not in frontiers:
                frontiers.append(frontier_num)
                break

    # Detect MT-N task references
    for m in re.finditer(r'mt-(\d+)', prompt_lower):
        mt_tasks.append(f"MT-{m.group(1)}")

    # Detect trading/Kalshi keywords
    for kw in TRADING_KEYWORDS:
        if kw.lower() in prompt_lower:
            keywords.append("trading")
            break

    return {
        "modules": modules,
        "frontiers": frontiers,
        "mt_tasks": mt_tasks,
        "keywords": keywords,
    }


# ── Query Building ───────────────────────────────────────────────────────────

def build_resurface_queries(ctx: dict) -> list[dict]:
    """Build resurface query dicts from detected context.

    Deduplicates: if a module maps to frontier N and frontier N was
    also explicitly detected, only one query for that frontier.

    Returns list of dicts with keys matching resurface() kwargs.
    """
    queries = []
    seen_frontiers = set()

    # Module → frontier queries
    for mod in ctx["modules"]:
        frontier = MODULE_FRONTIER_MAP.get(mod)
        if frontier and frontier not in seen_frontiers:
            queries.append({"frontier": frontier, "module": mod})
            seen_frontiers.add(frontier)

    # Explicit frontier queries (skip if already covered by module)
    for f in ctx["frontiers"]:
        if f not in seen_frontiers:
            queries.append({"frontier": f})
            seen_frontiers.add(f)

    # MT task queries
    for mt in ctx["mt_tasks"]:
        queries.append({"mt_task": mt})

    # Keyword queries
    if ctx["keywords"]:
        queries.append({"keywords": ctx["keywords"]})

    return queries


# ── Cooldown State ───────────────────────────────────────────────────────────

class ResurfacerState:
    """Tracks cooldown to prevent rapid-fire hook execution."""

    def __init__(self, cooldown_seconds: float = DEFAULT_COOLDOWN):
        self.cooldown_seconds = cooldown_seconds
        self._last_fired: dict[str, float] = {}  # context_key -> timestamp

    def should_fire(self, context_key: str = "__default__") -> bool:
        """Check if enough time has passed since last fire for this context."""
        last = self._last_fired.get(context_key)
        if last is None:
            return True
        return (time.time() - last) >= self.cooldown_seconds

    def mark_fired(self, context_key: str = "__default__") -> None:
        """Record that we just fired for this context."""
        self._last_fired[context_key] = time.time()


# ── Handler Functions ────────────────────────────────────────────────────────

def handle_prompt(
    prompt: str,
    log_path: str = DEFAULT_LOG_PATH,
    max_findings: int = 5,
) -> str | None:
    """Process a user prompt and return formatted findings if relevant.

    Returns None if no relevant context detected or no findings match.
    """
    ctx = detect_context(prompt)
    queries = build_resurface_queries(ctx)

    if not queries:
        return None

    # Collect all findings across queries, dedup by title
    all_findings = []
    seen_titles = set()

    for q in queries:
        results = resurface(log_path, **q, limit=max_findings)
        for f in results:
            if f.title not in seen_titles:
                all_findings.append(f)
                seen_titles.add(f.title)

    if not all_findings:
        return None

    # Limit total findings
    all_findings = all_findings[:max_findings]

    # Build context string
    context_parts = []
    if ctx["modules"]:
        context_parts.extend(ctx["modules"])
    if ctx["frontiers"]:
        context_parts.extend(f"Frontier {f}" for f in ctx["frontiers"])
    if ctx["mt_tasks"]:
        context_parts.extend(ctx["mt_tasks"])
    if ctx["keywords"]:
        context_parts.extend(ctx["keywords"])

    context_label = ", ".join(context_parts)
    return format_resurface_report(all_findings, context_label)


def generate_hook_output(
    prompt: str,
    log_path: str = DEFAULT_LOG_PATH,
    max_findings: int = 5,
) -> str | None:
    """Generate JSON hook output for Claude Code UserPromptSubmit.

    Returns JSON string with additionalContext, or None if no findings.
    """
    report = handle_prompt(prompt, log_path, max_findings)
    if report is None:
        return None

    output = {
        "additionalContext": f"Past findings relevant to your current work:\n{report}"
    }
    return json.dumps(output)


# ── Main (hook entry point) ──────────────────────────────────────────────────

def main():
    """UserPromptSubmit hook entry point.

    Reads hook input from stdin, detects context, surfaces findings.
    """
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, IOError):
        return

    # Extract user prompt from hook input
    prompt = hook_input.get("userMessage", "")
    if not prompt:
        return

    result = generate_hook_output(prompt)
    if result:
        print(result)


if __name__ == "__main__":
    main()
