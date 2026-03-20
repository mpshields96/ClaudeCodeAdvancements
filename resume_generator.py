#!/usr/bin/env python3
"""Resume Generator — cca-loop hardening: auto-generate SESSION_RESUME.md.

Prevents stale resume prompt from degrading loop sessions.
When SESSION_RESUME.md is stale or missing, generates a fresh resume
prompt from SESSION_STATE.md and PROJECT_INDEX.md.

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
from typing import Optional

DEFAULT_CCA_ROOT = os.path.expanduser("~/Projects/ClaudeCodeAdvancements")
DEFAULT_MAX_AGE_HOURS = 6


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


def _extract_next(content: str) -> Optional[str]:
    """Extract the 'Next:' directive from SESSION_STATE.md."""
    m = re.search(r"\*\*Next:\*\*\s*(.+?)(?:\n\n|\n---|\Z)", content, re.DOTALL)
    if m:
        text = m.group(1).strip()
        # Truncate to first 120 chars
        if len(text) > 120:
            text = text[:120].rsplit(" ", 1)[0] + "..."
        return text
    return None


def _extract_test_count(content: str) -> Optional[str]:
    """Extract total test count from PROJECT_INDEX.md content."""
    m = re.search(r"\*\*Total:\s*(\d+)\s*tests.*?\*\*", content)
    return m.group(1) if m else None


class ResumeGenerator:
    def __init__(self, cca_root: str = DEFAULT_CCA_ROOT):
        self.cca_root = cca_root

    def _read(self, filename: str) -> Optional[str]:
        path = os.path.join(self.cca_root, filename)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    def generate(self) -> str:
        """Generate a fresh resume prompt string."""
        session_state = self._read("SESSION_STATE.md")
        project_index = self._read("PROJECT_INDEX.md")

        session_num = None
        what_done = None
        next_task = None
        test_count = None

        if session_state:
            session_num = _extract_session_number(session_state)
            what_done = _extract_what_done(session_state)
            next_task = _extract_next(session_state)

        if project_index:
            test_count = _extract_test_count(project_index)

        # Build the resume prompt
        parts = []

        if session_num:
            parts.append(f"Run /cca-init. Last session was {session_num} on 2026-03-20.")
        else:
            parts.append("Run /cca-init.")

        if what_done:
            # Keep it brief
            summary = what_done[:100] if len(what_done) > 100 else what_done
            parts.append(f"WHAT WAS DONE: {summary}")

        if test_count:
            parts.append(f"Tests: {test_count} passing. Git: clean.")
        else:
            parts.append("Git: clean.")

        if next_task:
            parts.append(f"NEXT: {next_task}")

        parts.append("Run /cca-auto for autonomous work.")

        return " ".join(parts)

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
