#!/usr/bin/env python3
"""Resume Generator — cca-loop hardening: auto-generate SESSION_RESUME.md.

Prevents stale handoff prompts from degrading loop sessions.
When SESSION_RESUME.md is stale or missing, generates a fresh next-chat
handoff from SESSION_STATE.md, PROJECT_INDEX.md, TODAYS_TASKS.md, and the
latest coordination channels.

Usage:
  python3 resume_generator.py --print      Print the generated resume prompt
  python3 resume_generator.py --check      Exit 0=fresh, 1=stale
  python3 resume_generator.py --update     Update SESSION_RESUME.md if stale
  python3 resume_generator.py --force      Always update SESSION_RESUME.md
"""

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_CCA_ROOT = os.path.expanduser("~/Projects/ClaudeCodeAdvancements")
DEFAULT_MAX_AGE_HOURS = 6
DEFAULT_CLAUDE_TO_CODEX = os.path.join(DEFAULT_CCA_ROOT, "CLAUDE_TO_CODEX.md")
DEFAULT_CODEX_TO_CLAUDE = os.path.join(DEFAULT_CCA_ROOT, "CODEX_TO_CLAUDE.md")
DEFAULT_CCA_TO_POLYBOT = os.path.expanduser("~/.claude/cross-chat/CCA_TO_POLYBOT.md")
DEFAULT_POLYBOT_TO_CCA = os.path.expanduser("~/.claude/cross-chat/POLYBOT_TO_CCA.md")


def is_stale(path: str, max_age_hours: float = DEFAULT_MAX_AGE_HOURS) -> bool:
    """Return True if the file is older than max_age_hours, or doesn't exist."""
    if not os.path.exists(path):
        return True
    mtime = os.path.getmtime(path)
    age_hours = (time.time() - mtime) / 3600
    return age_hours > max_age_hours


def _extract_session_number(content: str) -> Optional[str]:
    """Extract session number from SESSION_STATE.md content."""
    m = re.search(r"Session\s+(\d+)", content)
    return m.group(1) if m else None


def _extract_what_done(content: str) -> Optional[str]:
    """Extract a brief summary of what was done from SESSION_STATE.md."""
    # Look for "Phase:" line
    m = re.search(r"\*\*Phase:\*\*\s*(.+?)(?:\n|$)", content)
    if m:
        return m.group(1).strip()
    return None


def _extract_session_date(content: str) -> Optional[str]:
    """Extract session date from SESSION_STATE.md header."""
    m = re.search(r"Session\s+\d+\s*(?:—|-)\s*(\d{4}-\d{2}-\d{2})", content)
    if m:
        return m.group(1)
    return None


def _extract_next_items(content: str) -> list[str]:
    """Extract prioritized next items from SESSION_STATE.md."""
    m = re.search(r"\*\*Next(?:\s*\(.*?\))?:\*\*\s*(.+?)(?:\n\*\*|\n---|\Z)", content, re.DOTALL)
    if not m:
        return []

    block = m.group(1).strip()
    items = []
    for line in block.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            items.append(re.sub(r"^\d+\.\s*", "", stripped))
            continue
        if not items and stripped:
            inline_items = re.findall(r"\(\d+\)\s*([^()]+?)(?=(?:\s+\(\d+\)|$))", stripped)
            if inline_items:
                items.extend(item.strip().rstrip(".") for item in inline_items if item.strip())
            elif stripped:
                items.append(stripped)

    return [item for item in items if item]


def _extract_test_count(content: str) -> Optional[str]:
    """Extract total test count from PROJECT_INDEX.md content."""
    m = re.search(r"\*\*Total:\s*(\d+)\s*tests.*?\*\*", content)
    return m.group(1) if m else None


def _extract_todays_tasks(content: str) -> list[str]:
    """Extract remaining TODO items from TODAYS_TASKS.md."""
    todos = []
    for raw_line in content.splitlines():
        if "[TODO]" not in raw_line:
            continue
        cleaned = raw_line.strip().lstrip("#").strip()
        cleaned = cleaned.replace("[TODO]", "").strip()
        if cleaned:
            todos.append(cleaned)
    return todos


def _extract_headings(content: str, max_items: int = 2) -> list[str]:
    """Extract recent markdown H2 headings for concise coordination context."""
    headings = [line.strip().lstrip("#").strip() for line in content.splitlines() if line.startswith("## ")]
    if not headings:
        return []
    return headings[-max_items:]


def build_handoff_snapshot(
    cca_root: str = DEFAULT_CCA_ROOT,
    claude_to_codex_path: str = DEFAULT_CLAUDE_TO_CODEX,
    codex_to_claude_path: str = DEFAULT_CODEX_TO_CLAUDE,
    cca_to_polybot_path: str = DEFAULT_CCA_TO_POLYBOT,
    polybot_to_cca_path: str = DEFAULT_POLYBOT_TO_CCA,
) -> dict:
    """Collect the structured data used for next-chat handoff generation."""
    root = Path(cca_root)
    session_state_path = root / "SESSION_STATE.md"
    project_index_path = root / "PROJECT_INDEX.md"
    todays_tasks_path = root / "TODAYS_TASKS.md"

    session_state = session_state_path.read_text(encoding="utf-8", errors="ignore") if session_state_path.exists() else ""
    project_index = project_index_path.read_text(encoding="utf-8", errors="ignore") if project_index_path.exists() else ""
    todays_tasks = todays_tasks_path.read_text(encoding="utf-8", errors="ignore") if todays_tasks_path.exists() else ""

    session_num = _extract_session_number(session_state)
    session_date = _extract_session_date(session_state) or datetime.now().strftime("%Y-%m-%d")
    phase = _extract_what_done(session_state) or "No phase summary found."
    next_items = _extract_next_items(session_state)
    test_count = _extract_test_count(project_index)
    todos = _extract_todays_tasks(todays_tasks)

    claude_to_codex = ""
    if claude_to_codex_path and os.path.exists(claude_to_codex_path):
        with open(claude_to_codex_path, encoding="utf-8", errors="ignore") as handle:
            claude_to_codex = handle.read()

    codex_to_claude = ""
    if codex_to_claude_path and os.path.exists(codex_to_claude_path):
        with open(codex_to_claude_path, encoding="utf-8", errors="ignore") as handle:
            codex_to_claude = handle.read()

    cca_to_polybot = ""
    if cca_to_polybot_path and os.path.exists(cca_to_polybot_path):
        with open(cca_to_polybot_path, encoding="utf-8", errors="ignore") as handle:
            cca_to_polybot = handle.read()

    polybot_to_cca = ""
    if polybot_to_cca_path and os.path.exists(polybot_to_cca_path):
        with open(polybot_to_cca_path, encoding="utf-8", errors="ignore") as handle:
            polybot_to_cca = handle.read()

    return {
        "cca_root": os.path.abspath(cca_root),
        "session_num": session_num,
        "session_date": session_date,
        "phase": phase,
        "next_items": next_items,
        "test_count": test_count,
        "todays_tasks": todos,
        "claude_to_codex": _extract_headings(claude_to_codex, max_items=2),
        "codex_to_claude": _extract_headings(codex_to_claude, max_items=2),
        "cca_to_polybot": _extract_headings(cca_to_polybot, max_items=2),
        "polybot_to_cca": _extract_headings(polybot_to_cca, max_items=2),
    }


def summarize_snapshot_for_init(snapshot: dict, max_priorities: int = 3, max_coordination: int = 2) -> dict:
    """Create a compact init-friendly summary from a handoff snapshot."""
    priorities = snapshot.get("todays_tasks") or snapshot.get("next_items") or []
    coordination = []

    for item in snapshot.get("claude_to_codex", []):
        coordination.append(f"Claude->Codex: {item}")
    for item in snapshot.get("codex_to_claude", []):
        coordination.append(f"Codex->CCA: {item}")
    for item in snapshot.get("cca_to_polybot", []):
        coordination.append(f"CCA->Kalshi: {item}")
    for item in snapshot.get("polybot_to_cca", []):
        coordination.append(f"Kalshi->CCA: {item}")

    return {
        "top_priorities": priorities[:max_priorities],
        "coordination": coordination[:max_coordination],
        "autonomous_hint": "Run /cca-auto after init only if you want autonomous continuation.",
    }


def render_handoff(snapshot: dict) -> str:
    """Render a full next-chat handoff markdown document."""
    summary = summarize_snapshot_for_init(snapshot, max_priorities=3, max_coordination=6)
    session_label = f"S{snapshot['session_num']}" if snapshot.get("session_num") else "Unknown session"
    lines = [
        "# NEXT CHAT HANDOFF",
        "",
        "## Start Here",
        "Run /cca-init.",
        "This file is the full next-chat handoff written by /cca-wrap, so a fresh chat should not need Matthew to restate context.",
        summary["autonomous_hint"],
        "",
        "## Repo State",
        f"- Repo: {snapshot.get('cca_root', DEFAULT_CCA_ROOT)}",
        f"- Last wrapped session: {session_label} ({snapshot.get('session_date', 'unknown date')})",
        f"- Phase: {snapshot.get('phase', 'No phase summary found.')}",
    ]

    if snapshot.get("test_count"):
        lines.append(f"- Cached tests: {snapshot['test_count']} passing")

    lines.extend(["", "## Immediate Priorities"])
    priorities = summary["top_priorities"]
    if priorities:
        for idx, item in enumerate(priorities, 1):
            lines.append(f"{idx}. {item}")
    else:
        lines.append("1. Read TODAYS_TASKS.md and SESSION_STATE.md, then pick the next narrow deliverable.")

    lines.extend(["", "## Today's Tasks"])
    if snapshot.get("todays_tasks"):
        for item in snapshot["todays_tasks"][:5]:
            lines.append(f"- {item}")
    else:
        lines.append("- No remaining [TODO] items found in TODAYS_TASKS.md.")

    lines.extend(["", "## Coordination"])
    coordination = summary["coordination"]
    if coordination:
        lines.extend(f"- {item}" for item in coordination)
    else:
        lines.append("- No fresh Codex or Kalshi coordination notes were found.")
    lines.append("- Check `python3 cca_comm.py inbox` if this session is part of CCA hivemind work.")

    lines.extend([
        "",
        "## Fresh-Chat Rule",
        "Typing only /cca-init in a new chat should be enough. Use this handoff as the authoritative continuation context after init.",
    ])
    return "\n".join(lines).strip() + "\n"


class ResumeGenerator:
    def __init__(
        self,
        cca_root: str = DEFAULT_CCA_ROOT,
        claude_to_codex_path: str = DEFAULT_CLAUDE_TO_CODEX,
        codex_to_claude_path: str = DEFAULT_CODEX_TO_CLAUDE,
        cca_to_polybot_path: str = DEFAULT_CCA_TO_POLYBOT,
        polybot_to_cca_path: str = DEFAULT_POLYBOT_TO_CCA,
    ):
        self.cca_root = cca_root
        self.claude_to_codex_path = claude_to_codex_path
        self.codex_to_claude_path = codex_to_claude_path
        self.cca_to_polybot_path = cca_to_polybot_path
        self.polybot_to_cca_path = polybot_to_cca_path

    def _read(self, filename: str) -> Optional[str]:
        path = os.path.join(self.cca_root, filename)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    def generate(self) -> str:
        """Generate a fresh next-chat handoff string."""
        snapshot = build_handoff_snapshot(
            cca_root=self.cca_root,
            claude_to_codex_path=self.claude_to_codex_path,
            codex_to_claude_path=self.codex_to_claude_path,
            cca_to_polybot_path=self.cca_to_polybot_path,
            polybot_to_cca_path=self.polybot_to_cca_path,
        )
        return render_handoff(snapshot)

    def update(self, force: bool = False, max_age_hours: float = DEFAULT_MAX_AGE_HOURS) -> bool:
        """
        Update SESSION_RESUME.md if stale.
        Returns True if file was updated, False if it was fresh.
        """
        resume_path = os.path.join(self.cca_root, "SESSION_RESUME.md")
        if not force and not is_stale(resume_path, max_age_hours=max_age_hours):
            return False

        content = self.generate()
        with open(resume_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")
        return True


def generate_resume(cca_root: str = DEFAULT_CCA_ROOT) -> str:
    """Module-level convenience function."""
    return ResumeGenerator(cca_root=cca_root).generate()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate SESSION_RESUME.md for cca-loop")
    parser.add_argument("--print", action="store_true", help="Print the generated resume prompt")
    parser.add_argument("--check", action="store_true", help="Exit 0=fresh, 1=stale")
    parser.add_argument("--update", action="store_true", help="Update if stale")
    parser.add_argument("--force", action="store_true", help="Always update")
    parser.add_argument("--root", default=DEFAULT_CCA_ROOT, help="CCA root directory")
    parser.add_argument("--max-age", type=float, default=DEFAULT_MAX_AGE_HOURS,
                        help="Max age in hours before file is considered stale")
    args = parser.parse_args()

    gen = ResumeGenerator(cca_root=args.root)
    resume_path = os.path.join(args.root, "SESSION_RESUME.md")

    if args.check:
        if is_stale(resume_path, max_age_hours=args.max_age):
            print("STALE")
            sys.exit(1)
        else:
            print("FRESH")
            sys.exit(0)

    if args.print:
        print(gen.generate())
        sys.exit(0)

    if args.update or args.force:
        updated = gen.update(force=args.force, max_age_hours=args.max_age)
        if updated:
            print(f"Updated: {resume_path}")
        else:
            print(f"Skipped (fresh): {resume_path}")
        sys.exit(0)

    # Default: print
    print(gen.generate())


if __name__ == "__main__":
    main()
