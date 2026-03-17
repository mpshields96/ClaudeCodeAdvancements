#!/usr/bin/env python3
"""
session_guard.py — Fresh-session anti-contamination guard.

Detects two kinds of quality degradation:
1. Session contamination: too many self-approved commits in one session
   (model approves its own changes, quality drifts). Warns to start fresh.
2. Slop patterns: over-documentation, redundant type comments, backwards-compat
   shims, emojis in code, removed-code comments, over-engineered try/except.

Inspired by: Desloppify (r/ClaudeCode, 98pts) — "spin up fresh session
every N commits to avoid context contamination."

Usage as PreToolUse hook:
  Reads JSON from stdin (tool_name, tool_input, session_id)
  Writes JSON to stdout with allow/warn decision

Usage as library:
  from session_guard import SlopDetector, SessionCommitTracker

Stdlib only. No external dependencies.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ── SlopResult ────────────────────────────────────────────────────────────────


@dataclass
class SlopResult:
    """Result of scanning code for slop patterns."""
    has_slop: bool = False
    slop_score: float = 0.0
    warnings: list = field(default_factory=list)

    def add(self, warning: str, score: float):
        self.warnings.append(warning)
        self.slop_score += score
        if self.slop_score > 0:
            self.has_slop = True


# ── SlopDetector ──────────────────────────────────────────────────────────────


# Emoji ranges (common ones that appear in code comments)
_EMOJI_PATTERN = re.compile(
    "[\U0001f300-\U0001f9ff\u2600-\u26ff\u2700-\u27bf\u2705\u274c\u2b50\u2728\U0001f389\U0001f680]"
)

# Backwards-compat shim patterns
_COMPAT_PATTERNS = [
    re.compile(r"^_\w+\s*=\s*None\s*#.*(?:backwards?|compat|legacy|deprecated|removed|kept for)", re.IGNORECASE),
]

# Removed-code comment patterns
_REMOVED_PATTERNS = [
    re.compile(r"#\s*(?:removed|deleted|was:|old_\w+|previous\s+implementation)", re.IGNORECASE),
]

# Redundant type comment pattern
_TYPE_COMMENT_PATTERN = re.compile(r"#\s*type:\s*(?:int|str|float|bool|list|dict|set|tuple)\s*$")


class SlopDetector:
    """
    Scans code content for slop patterns.

    Slop categories:
    1. Excessive documentation (>50% lines are comments/docstrings)
    2. Redundant type comments (# type: int on obvious assignments)
    3. Over-engineered try/except on simple operations
    4. Removed-code comments (# removed old logic)
    5. Backwards-compatibility shims (_old_var = None # compat)
    6. Emojis in code (not in string literals)
    """

    # Minimum lines to trigger detection (short snippets get a pass)
    MIN_LINES = 5

    def scan(self, code: str) -> SlopResult:
        result = SlopResult()

        if not code or not code.strip():
            return result

        lines = code.split("\n")
        if len(lines) < self.MIN_LINES:
            return result

        self._check_excessive_docs(lines, result)
        self._check_type_comments(lines, result)
        self._check_over_engineering(code, result)
        self._check_removed_comments(lines, result)
        self._check_compat_shims(lines, result)
        self._check_emojis(lines, result)

        return result

    def _check_excessive_docs(self, lines: list, result: SlopResult):
        """Flag code where >50% of non-empty lines are comments or docstrings."""
        non_empty = [l for l in lines if l.strip()]
        if len(non_empty) < self.MIN_LINES:
            return

        doc_lines = 0
        in_docstring = False
        for line in non_empty:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # Toggle docstring state
                if in_docstring:
                    in_docstring = False
                    doc_lines += 1
                elif stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                    doc_lines += 1  # Single-line docstring
                else:
                    in_docstring = True
                    doc_lines += 1
            elif in_docstring:
                doc_lines += 1
            elif stripped.startswith("#"):
                doc_lines += 1

        ratio = doc_lines / len(non_empty)
        if ratio > 0.5:
            result.add(
                f"Excessive docstrings/comments: {doc_lines}/{len(non_empty)} lines ({ratio:.0%})",
                30.0,
            )

    def _check_type_comments(self, lines: list, result: SlopResult):
        """Flag redundant # type: int style comments."""
        count = sum(1 for l in lines if _TYPE_COMMENT_PATTERN.search(l))
        if count >= 3:
            result.add(f"Redundant type comments: {count} occurrences", 15.0)

    def _check_over_engineering(self, code: str, result: SlopResult):
        """Flag excessive try/except blocks on simple operations."""
        # Count try blocks
        try_count = len(re.findall(r"^\s*try:\s*$", code, re.MULTILINE))
        # Simple heuristic: if there are 3+ try blocks in a short piece of code
        lines = code.split("\n")
        if try_count >= 3 and len(lines) < 50:
            result.add(f"Over-engineered try/except: {try_count} blocks in {len(lines)} lines", 20.0)

    def _check_removed_comments(self, lines: list, result: SlopResult):
        """Flag comments indicating removed code (should just delete, not comment)."""
        count = sum(1 for l in lines if any(p.search(l) for p in _REMOVED_PATTERNS))
        if count >= 2:
            result.add(f"Removed-code comments: {count} (just delete, don't comment out)", 15.0)

    def _check_compat_shims(self, lines: list, result: SlopResult):
        """Flag backwards-compatibility shims (unused vars kept for compat)."""
        count = sum(1 for l in lines if any(p.search(l.strip()) for p in _COMPAT_PATTERNS))
        if count >= 2:
            result.add(f"Backwards-compat shims: {count} (delete unused code entirely)", 20.0)

    def _check_emojis(self, lines: list, result: SlopResult):
        """Flag emojis in code (not in string literals)."""
        emoji_lines = 0
        for line in lines:
            stripped = line.strip()
            # Skip string-only lines
            if stripped.startswith(("'", '"', "print(", "return ")):
                continue
            if _EMOJI_PATTERN.search(stripped):
                emoji_lines += 1
        if emoji_lines >= 2:
            result.add(f"Emojis in code: {emoji_lines} lines (not in strings)", 10.0)


# ── SessionCommitTracker ─────────────────────────────────────────────────────


class SessionCommitTracker:
    """
    Tracks commits within a session to detect self-approval contamination.

    After N commits in one session, warns that a fresh session would produce
    better quality code (model approves its own changes, quality drifts).
    """

    def __init__(
        self,
        state_path: str = None,
        warn_threshold: int = 10,
        session_id: str = None,
    ):
        self.state_path = state_path or os.path.expanduser("~/.cca-session-guard.json")
        self.warn_threshold = warn_threshold
        self.session_id = session_id or os.environ.get("CLAUDE_SESSION_ID", "default")

        self.commit_count = 0
        self.commits = []
        self.files_touched = set()
        self._load()

    def _load(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path) as f:
                    data = json.load(f)
                session_data = data.get(self.session_id, {})
                self.commit_count = session_data.get("commit_count", 0)
                self.commits = session_data.get("commits", [])
                self.files_touched = set(session_data.get("files_touched", []))
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        # Load existing data for other sessions
        all_data = {}
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path) as f:
                    all_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        all_data[self.session_id] = {
            "commit_count": self.commit_count,
            "commits": self.commits,
            "files_touched": sorted(self.files_touched),
        }

        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(all_data, f, indent=2)
        os.replace(tmp, self.state_path)

    def record_commit(self, commit_hash: str, files_changed: list = None):
        self.commit_count += 1
        self.commits.append(commit_hash)
        if files_changed:
            self.files_touched.update(files_changed)
        self._save()

    @property
    def total_files_touched(self) -> int:
        return len(self.files_touched)

    def should_warn(self) -> bool:
        return self.commit_count >= self.warn_threshold

    def warning_message(self) -> str:
        return (
            f"Session has {self.commit_count} commits ({self.total_files_touched} files touched). "
            f"Consider starting a fresh session to avoid context contamination — "
            f"the model tends to approve its own changes, causing quality drift. "
            f"A fresh session brings fresh perspective."
        )

    def reset(self):
        self.commit_count = 0
        self.commits = []
        self.files_touched = set()
        self._save()


# ── Hook Integration ──────────────────────────────────────────────────────────

_CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java", ".c", ".cpp", ".h"}
_detector = SlopDetector()


def check_write_for_slop(tool_name: str, tool_input: dict) -> dict:
    """
    Check a Write/Edit tool call for slop patterns.
    Returns {"allow": bool, "reason": str}.
    """
    # Only check Write and Edit
    if tool_name not in ("Write", "Edit"):
        return {"allow": True, "reason": ""}

    # Get the content being written
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    if not content:
        return {"allow": True, "reason": ""}

    # Only check code files
    file_path = tool_input.get("file_path", "")
    if file_path:
        ext = os.path.splitext(file_path)[1].lower()
        if ext and ext not in _CODE_EXTENSIONS:
            return {"allow": True, "reason": ""}

    result = _detector.scan(content)
    if result.has_slop:
        warnings_str = "; ".join(result.warnings)
        return {
            "allow": False,
            "reason": f"Slop detected (score: {result.slop_score:.0f}): {warnings_str}",
        }

    return {"allow": True, "reason": ""}


# ── Main (PreToolUse hook) ────────────────────────────────────────────────────


def main():
    """PreToolUse hook entry point."""
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        # Can't parse input — allow by default (fail open)
        print(json.dumps({}))
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    result = check_write_for_slop(tool_name, tool_input)

    if not result["allow"]:
        # Warn via additionalContext (not block — slop is a warning, not a security issue)
        output = {
            "additionalContext": (
                f"SESSION GUARD WARNING: {result['reason']}. "
                "Consider reviewing this code for unnecessary complexity before committing."
            )
        }
        print(json.dumps(output))
    else:
        print(json.dumps({}))


if __name__ == "__main__":
    main()
