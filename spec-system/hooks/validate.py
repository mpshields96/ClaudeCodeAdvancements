#!/usr/bin/env python3
"""
SPEC-5: Spec Validation Hook
PreToolUse hook — fires before Write and Edit tool calls.
Warns (or blocks, if configured) when code is being written without an approved spec.

Behavior:
  - WARN mode (default): injects a context message, does not block
  - BLOCK mode (opt-in): denies the Write/Edit and explains why

Configuration:
  Set environment variable SPEC_GUARD_MODE=block to enable blocking.
  Default is warn-only.

Usage (hooks config):
  PreToolUse: python3 /path/to/validate.py
"""

import json
import os
import sys
from pathlib import Path


# ── Configuration ─────────────────────────────────────────────────────────────

# File extensions that indicate a code file (not docs/config)
_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb", ".java",
    ".c", ".cpp", ".h", ".cs", ".php", ".swift", ".kt", ".sh", ".bash",
}

# File names that are always allowed (spec outputs, docs, config)
_ALWAYS_ALLOWED_NAMES = {
    "requirements.md", "design.md", "tasks.md", "CLAUDE.md",
    "README.md", "SESSION_STATE.md", "PROJECT_INDEX.md", "ROADMAP.md",
    "schema.md", "EVIDENCE.md", "HANDOFF.md",
}

# Tool names that write files
_WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}


# ── Spec Detection ────────────────────────────────────────────────────────────

def _find_spec_file(start_dir: str, filename: str) -> Path | None:
    """
    Walk up from start_dir looking for filename.
    Returns the path if found, None otherwise.
    """
    current = Path(start_dir).resolve()
    for _ in range(10):  # Max 10 levels up — prevents infinite loop
        candidate = current / filename
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _is_approved(spec_path: Path) -> bool:
    """Return True if the spec file contains 'Status: APPROVED'."""
    try:
        content = spec_path.read_text(encoding="utf-8")
        return "Status: APPROVED" in content
    except OSError:
        return False


def _spec_status(cwd: str) -> dict:
    """
    Check the spec state for the current working directory.
    Returns a dict with keys: has_requirements, requirements_approved,
    has_design, design_approved, has_tasks, tasks_approved.
    """
    status = {
        "has_requirements": False,
        "requirements_approved": False,
        "has_design": False,
        "design_approved": False,
        "has_tasks": False,
        "tasks_approved": False,
    }

    req_path = _find_spec_file(cwd, "requirements.md")
    if req_path:
        status["has_requirements"] = True
        status["requirements_approved"] = _is_approved(req_path)

    design_path = _find_spec_file(cwd, "design.md")
    if design_path:
        status["has_design"] = True
        status["design_approved"] = _is_approved(design_path)

    tasks_path = _find_spec_file(cwd, "tasks.md")
    if tasks_path:
        status["has_tasks"] = True
        status["tasks_approved"] = _is_approved(tasks_path)

    return status


# ── Decision Logic ────────────────────────────────────────────────────────────

def _should_check(tool_name: str, file_path: str) -> bool:
    """Return True if this Write/Edit call warrants a spec check."""
    if tool_name not in _WRITE_TOOLS:
        return False

    path = Path(file_path)

    # Always allow spec documents themselves
    if path.name in _ALWAYS_ALLOWED_NAMES:
        return False

    # Check file extension — only flag code files
    if path.suffix.lower() not in _CODE_EXTENSIONS:
        return False

    # Allow test files to be written (they're evidence of spec compliance)
    if "test_" in path.name or path.name.endswith("_test.py"):
        return False

    return True


def _build_warning(spec_status: dict, file_path: str, mode: str) -> str:
    """Build a human-readable warning message based on spec state."""
    missing = []
    if not spec_status["has_requirements"]:
        missing.append("requirements.md (run /spec:requirements)")
    elif not spec_status["requirements_approved"]:
        missing.append("requirements.md approval (say 'approved' after reviewing)")

    if not spec_status["has_design"] and spec_status["requirements_approved"]:
        missing.append("design.md (run /spec:design)")
    elif spec_status["has_design"] and not spec_status["design_approved"]:
        missing.append("design.md approval (say 'approved' after reviewing)")

    if not missing:
        return ""  # Spec is in order — no warning needed

    warning_parts = [
        f"[spec-guard] Writing {Path(file_path).name} without an approved spec.",
        f"Missing: {', '.join(missing)}.",
    ]

    if mode == "block":
        warning_parts.append(
            "BLOCKED. Complete the spec process first, or set SPEC_GUARD_MODE=warn to switch to warning-only mode."
        )
    else:
        warning_parts.append(
            "Proceeding in warn-only mode. Run /spec:requirements to start the spec process."
        )

    return " ".join(warning_parts)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        hook_input = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    # Only act on PreToolUse
    if hook_input.get("hook_event_name") != "PreToolUse":
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    cwd = hook_input.get("cwd", "")
    file_path = tool_input.get("file_path", "")

    if not _should_check(tool_name, file_path):
        sys.exit(0)

    status = _spec_status(cwd)

    # If tasks are approved, we're in implementation mode — no warning needed
    if status["tasks_approved"]:
        sys.exit(0)

    mode = os.environ.get("SPEC_GUARD_MODE", "warn").lower()
    warning = _build_warning(status, file_path, mode)

    if not warning:
        sys.exit(0)

    if mode == "block":
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": warning,
            }
        }
    else:
        # Warn-only: allow but inject context
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": warning,
            }
        }

    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
