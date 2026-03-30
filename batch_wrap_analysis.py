#!/usr/bin/env python3
"""batch_wrap_analysis.py — Consolidate wrap Steps 6b-6h into one call.

Replaces 7 separate bash blocks in cca-wrap with a single subprocess call.
Runs: reflect --brief, auto-escalate check, reflect --apply, recurring
anti-pattern scan, skillbook evolution, sentinel adaptation, strategy validation.

Savings: ~5,000 tokens per wrap (7 bash blocks + context overhead → 1).

Usage:
    python3 batch_wrap_analysis.py --session 240 --grade B \
        --wins "Built analyzer" --losses "Stale data"
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SELF_LEARNING = SCRIPT_DIR / "self-learning"
LEARNINGS_PATH = SCRIPT_DIR / "LEARNINGS.md"
CHANGELOG_PATH = SCRIPT_DIR / "CHANGELOG.md"
SKILLBOOK_PATH = SELF_LEARNING / "SKILLBOOK.md"
RULES_DIR = SCRIPT_DIR / ".claude" / "rules"


def _run_script(args: list[str], label: str) -> tuple[bool, str]:
    """Run a Python script and capture output."""
    try:
        result = subprocess.run(
            [sys.executable] + args,
            capture_output=True, text=True, timeout=30,
            cwd=str(SCRIPT_DIR),
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"{label}: timed out (30s)"
    except Exception as e:
        return False, f"{label}: {e}"


def step_6b_reflect_brief() -> dict:
    """6b: Run reflect.py --brief to detect patterns."""
    ok, output = _run_script(
        [str(SELF_LEARNING / "reflect.py"), "--brief"],
        "reflect --brief",
    )
    return {"step": "6b_reflect", "ok": ok, "output": output}


def step_6c_escalate_check() -> dict:
    """6c: Scan LEARNINGS.md for severity 3 / count 3+ needing rule promotion."""
    if not LEARNINGS_PATH.exists():
        return {"step": "6c_escalate", "ok": True, "output": "No LEARNINGS.md found"}

    text = LEARNINGS_PATH.read_text(encoding="utf-8")
    candidates = []
    existing_rules = set()
    if RULES_DIR.exists():
        existing_rules = {f.stem for f in RULES_DIR.iterdir() if f.suffix == ".md"}

    # Find entries with Severity: 3 and Count: 3+
    blocks = re.split(r"\n### ", text)
    for block in blocks:
        sev_match = re.search(r"Severity:\s*(\d+)", block)
        count_match = re.search(r"Count:\s*(\d+)", block)
        promoted = "Promoted:" in block
        if sev_match and count_match and not promoted:
            severity = int(sev_match.group(1))
            count = int(count_match.group(1))
            title_line = block.split("\n")[0].strip()
            # Severity 3, Count >= 3: needs rule file
            if severity >= 3 and count >= 3:
                slug = re.sub(r"[^a-z0-9]+", "-", title_line.lower()).strip("-")[:40]
                if slug not in existing_rules:
                    candidates.append(f"PROMOTE TO RULE: {title_line} (sev={severity}, count={count})")
            # Severity 2, Count >= 2: needs CLAUDE.md gotcha
            elif severity >= 2 and count >= 2:
                candidates.append(f"GOTCHA CANDIDATE: {title_line} (sev={severity}, count={count})")

    if candidates:
        output = "\n".join(candidates)
    else:
        output = "No learnings qualify for promotion"
    return {"step": "6c_escalate", "ok": True, "output": output}


def step_6d_reflect_apply() -> dict:
    """6d: Apply strategy changes from detected patterns."""
    ok, output = _run_script(
        [str(SELF_LEARNING / "reflect.py"), "--apply"],
        "reflect --apply",
    )
    return {"step": "6d_apply", "ok": ok, "output": output}


def step_6e_recurring_antipatterns(session: int) -> dict:
    """6e: Check last 3 session entries in CHANGELOG for recurring patterns."""
    if not CHANGELOG_PATH.exists():
        return {"step": "6e_antipatterns", "ok": True, "output": "No CHANGELOG.md found"}

    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    # Extract recent session blocks (## S### format)
    session_blocks = re.findall(
        r"## S\d+.*?(?=\n## S\d+|\Z)", text, re.DOTALL
    )[:3]

    if len(session_blocks) < 2:
        return {"step": "6e_antipatterns", "ok": True, "output": "Not enough sessions to compare"}

    # Look for repeated loss/issue keywords across sessions
    loss_keywords = []
    for block in session_blocks:
        losses = re.findall(r"(?:LOSS|loss|Loss|issue|bug|broke|failed|wasted).*", block, re.IGNORECASE)
        for loss in losses:
            words = set(re.findall(r"\b[a-z]{4,}\b", loss.lower()))
            loss_keywords.append(words)

    if len(loss_keywords) >= 2:
        overlap = loss_keywords[0]
        for kw_set in loss_keywords[1:]:
            overlap = overlap & kw_set
        if overlap:
            return {
                "step": "6e_antipatterns",
                "ok": True,
                "output": f"RECURRING PATTERN: shared loss keywords across sessions: {', '.join(sorted(overlap)[:5])}",
            }

    return {"step": "6e_antipatterns", "ok": True, "output": "No recurring anti-patterns detected"}


def step_6f_skillbook_evolution(session: int, grade: str, wins: list[str], losses: list[str]) -> dict:
    """6f: Update Skillbook strategy confidence based on session evidence."""
    if not SKILLBOOK_PATH.exists():
        return {"step": "6f_skillbook", "ok": True, "output": "No SKILLBOOK.md found"}

    text = SKILLBOOK_PATH.read_text(encoding="utf-8")
    updates = []

    # Extract strategies with confidence scores
    strategies = re.findall(
        r"\*\*([A-Z]\d+)\*\*.*?Confidence:\s*(\d+).*?\n(.*?)(?=\n\*\*[A-Z]\d+|## Archived|\Z)",
        text, re.DOTALL
    )

    session_text = " ".join(wins + losses).lower()
    for sid, conf, body in strategies:
        conf = int(conf)
        keywords = re.findall(r"\b[a-z]{4,}\b", body.lower())[:10]
        matches = sum(1 for kw in keywords if kw in session_text)
        if matches >= 2:
            if grade in ("A", "B"):
                new_conf = min(100, conf + 5)
                updates.append(f"{sid}: confidence {conf} -> {new_conf} (validated by session wins)")
            elif grade in ("C", "D"):
                new_conf = max(0, conf - 10)
                updates.append(f"{sid}: confidence {conf} -> {new_conf} (contradicted by session losses)")

    if updates:
        output = "\n".join(updates)
    else:
        output = "No strategies matched session evidence"
    return {"step": "6f_skillbook", "ok": True, "output": output}


def step_6g5_sentinel() -> dict:
    """6g.5: Run sentinel adaptation cycle (improver.py evolve)."""
    ok, output = _run_script(
        [str(SELF_LEARNING / "improver.py"), "evolve"],
        "improver evolve",
    )
    return {"step": "6g5_sentinel", "ok": ok, "output": output}


def step_6h_validate() -> dict:
    """6h: Validate Skillbook strategies against journal evidence."""
    ok, output = _run_script(
        [str(SELF_LEARNING / "validate_strategies.py"), "--brief"],
        "validate_strategies --brief",
    )
    return {"step": "6h_validate", "ok": ok, "output": output}


def run_all(session: int, grade: str, wins: list[str], losses: list[str]) -> list[dict]:
    """Run all analysis steps and return results."""
    results = []
    results.append(step_6b_reflect_brief())
    results.append(step_6c_escalate_check())
    results.append(step_6d_reflect_apply())
    results.append(step_6e_recurring_antipatterns(session))
    results.append(step_6f_skillbook_evolution(session, grade, wins, losses))
    results.append(step_6g5_sentinel())
    results.append(step_6h_validate())
    return results


def format_summary(results: list[dict]) -> str:
    """Format results into the SESSION LEARNING block expected by cca-wrap."""
    lines = ["SESSION LEARNING (batch_wrap_analysis):"]
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        # Truncate long output to keep wrap concise
        output = r["output"][:200] if r["output"] else "(no output)"
        lines.append(f"  [{status}] {r['step']}: {output}")

    ok_count = sum(1 for r in results if r["ok"])
    fail_count = sum(1 for r in results if not r["ok"])
    lines.append(f"  Total: {ok_count} OK, {fail_count} failed out of {len(results)} steps")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Batch wrap analysis — Steps 6b-6h consolidated"
    )
    parser.add_argument("--session", type=int, required=True)
    parser.add_argument("--grade", required=True, choices=["A", "B", "C", "D"])
    parser.add_argument("--wins", nargs="*", default=[])
    parser.add_argument("--losses", nargs="*", default=[])
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    results = run_all(args.session, args.grade, args.wins, args.losses)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(format_summary(results))


if __name__ == "__main__":
    main()
