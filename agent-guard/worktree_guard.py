"""
Worktree Isolation Guard (AG-10) — Agent Teams awareness for agent-guard.

JOB: Detect when running inside a Claude Agent Teams worktree and enforce
     isolation rules to prevent cross-worktree file conflicts.

CONTEXT:
    Claude Agent Teams (Opus 4.6 research preview) spawns delegate agents,
    each in its own git worktree at .claude/worktrees/<name>/. The lead agent
    coordinates via SendMessage/TeammateTool. Each delegate has its own context
    window and branch.

RULES:
    - Delegates can write files ONLY within their own worktree
    - Delegates cannot write to the main worktree (lead agent's territory)
    - Delegates cannot write to other delegates' worktrees
    - Shared state files (SESSION_STATE.md, CLAUDE.md, etc.) get a WARN even
      within own worktree (they should only be modified by the lead)
    - Read operations are never restricted
    - Git push to main/master is blocked for delegates
    - When not in a worktree context, all operations are allowed (no-op)

USAGE:
    guard = WorktreeGuard.from_environment()
    result = guard.check_write("/path/to/file.py")
    if result.decision == "block":
        # Deny the operation
    elif result.decision == "warn":
        # Allow but log warning
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# Files that should only be modified by the lead agent / main worktree.
# Delegates get a WARN (not block) when writing these in their own worktree.
SHARED_STATE_PATTERNS = {
    "SESSION_STATE.md",
    "PROJECT_INDEX.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "ROADMAP.md",
    "MASTER_TASKS.md",
    "LEARNINGS.md",
    "TODAYS_TASKS.md",
    ".agent-manifest.json",
}

# Path prefixes that are always shared state
SHARED_STATE_PREFIXES = (
    ".claude/",
    ".git/",
)

# Dangerous git commands for delegates
_DANGEROUS_GIT_PATTERNS = [
    re.compile(r"git\s+push\s+\S+\s+(main|master)\b"),
    re.compile(r"git\s+reset\s+--hard"),
    re.compile(r"git\s+checkout\s+--\s"),
    re.compile(r"git\s+clean\s+-[fd]"),
    re.compile(r"git\s+branch\s+-[dD]\s"),
]


@dataclass
class CheckResult:
    """Result of a worktree guard check."""
    decision: str  # "allow", "warn", "block"
    reason: str = ""


@dataclass
class WorktreeInfo:
    """Parsed info about a single git worktree."""
    path: str
    head: str = ""
    branch: Optional[str] = None
    is_main: bool = False
    is_detached: bool = False

    @property
    def name(self) -> str:
        """Extract worktree name from path."""
        return Path(self.path).name


def parse_worktree_list(output: str) -> List[WorktreeInfo]:
    """Parse `git worktree list --porcelain` output into WorktreeInfo objects."""
    if not output.strip():
        return []

    worktrees = []
    current: Optional[dict] = None

    for line in output.splitlines():
        if line.startswith("worktree "):
            if current is not None:
                worktrees.append(_dict_to_info(current, is_first=len(worktrees) == 0))
            current = {"path": line[len("worktree "):].strip()}
        elif line.startswith("HEAD ") and current is not None:
            current["head"] = line[len("HEAD "):].strip()
        elif line.startswith("branch ") and current is not None:
            branch_ref = line[len("branch "):].strip()
            # refs/heads/main -> main
            current["branch"] = branch_ref.split("/")[-1] if "/" in branch_ref else branch_ref
        elif line.strip() == "detached" and current is not None:
            current["detached"] = True

    if current is not None:
        worktrees.append(_dict_to_info(current, is_first=len(worktrees) == 0))

    return worktrees


def _dict_to_info(d: dict, is_first: bool) -> WorktreeInfo:
    return WorktreeInfo(
        path=d.get("path", ""),
        head=d.get("head", ""),
        branch=d.get("branch"),
        is_main=is_first,  # First worktree in list is always the main one
        is_detached=d.get("detached", False),
    )


@dataclass
class WorktreeContext:
    """Context about current worktree environment."""
    is_main: bool
    is_delegate: bool
    worktree_name: Optional[str] = None


def detect_worktree_context(
    cwd: str,
    main_worktree: str,
) -> WorktreeContext:
    """Detect if cwd is inside a delegate worktree."""
    cwd_path = Path(cwd).resolve()
    main_path = Path(main_worktree).resolve()

    # Check if cwd is inside .claude/worktrees/
    worktrees_dir = main_path / ".claude" / "worktrees"
    try:
        rel = cwd_path.relative_to(worktrees_dir)
        # First component is the worktree name
        parts = rel.parts
        worktree_name = parts[0] if parts else None
        return WorktreeContext(
            is_main=False,
            is_delegate=True,
            worktree_name=worktree_name,
        )
    except ValueError:
        pass

    # Check if cwd is the main worktree (or inside it)
    try:
        cwd_path.relative_to(main_path)
        return WorktreeContext(is_main=True, is_delegate=False)
    except ValueError:
        # Outside both — treat as main (no restrictions)
        return WorktreeContext(is_main=True, is_delegate=False)


def is_shared_state_file(filepath: str) -> bool:
    """Check if a file is a shared state file that delegates should not modify."""
    name = Path(filepath).name
    if name in SHARED_STATE_PATTERNS:
        return True

    # Check path prefixes
    normalized = filepath.replace("\\", "/")
    for prefix in SHARED_STATE_PREFIXES:
        if prefix in normalized:
            return True

    return False


@dataclass
class WorktreeGuard:
    """
    Validates file operations in worktree context.

    When is_delegate=True, enforces isolation:
    - Writes restricted to own worktree
    - Shared state files get warnings
    - Destructive git commands blocked
    """
    is_delegate: bool
    worktree_name: str
    worktree_path: str
    main_worktree_path: str

    def check_write(self, filepath: str) -> CheckResult:
        """Check if a write operation is allowed."""
        if not self.is_delegate:
            return CheckResult(decision="allow")

        abs_path = Path(filepath).resolve() if not Path(filepath).is_absolute() else Path(filepath)
        wt_path = Path(self.worktree_path).resolve()
        main_path = Path(self.main_worktree_path).resolve()

        # Check if writing to own worktree
        try:
            rel = abs_path.relative_to(wt_path)
            # Within own worktree — check if shared state file
            if is_shared_state_file(str(rel)):
                return CheckResult(
                    decision="warn",
                    reason=f"Shared state file '{rel}' — should be modified by lead agent only",
                )
            return CheckResult(decision="allow")
        except ValueError:
            pass

        # Check if writing to another worktree
        worktrees_dir = main_path / ".claude" / "worktrees"
        try:
            rel = abs_path.relative_to(worktrees_dir)
            return CheckResult(
                decision="block",
                reason=f"Cannot write to other worktree: {rel.parts[0] if rel.parts else 'unknown'}",
            )
        except ValueError:
            pass

        # Writing to main worktree
        try:
            abs_path.relative_to(main_path)
            return CheckResult(
                decision="block",
                reason=f"Delegate '{self.worktree_name}' cannot write to main worktree",
            )
        except ValueError:
            pass

        # Outside all worktrees — block
        return CheckResult(
            decision="block",
            reason=f"Delegate '{self.worktree_name}' cannot write outside project",
        )

    def check_read(self, filepath: str) -> CheckResult:
        """Read operations are never blocked."""
        return CheckResult(decision="allow")

    def check_bash(self, command: str) -> CheckResult:
        """Check if a bash command is safe for a delegate."""
        if not self.is_delegate:
            return CheckResult(decision="allow")

        for pattern in _DANGEROUS_GIT_PATTERNS:
            if pattern.search(command):
                # Allow push to own branch
                push_match = re.search(r"git\s+push\s+\S+\s+(\S+)", command)
                if push_match and push_match.group(1) == self.worktree_name:
                    return CheckResult(decision="allow")
                return CheckResult(
                    decision="block",
                    reason=f"Delegate cannot run destructive git command: {command.strip()[:80]}",
                )

        return CheckResult(decision="allow")

    def summary(self) -> str:
        """One-line summary for logging."""
        if self.is_delegate:
            return f"Delegate worktree '{self.worktree_name}' at {self.worktree_path}"
        return f"Main worktree at {self.main_worktree_path}"

    @classmethod
    def from_environment(cls, cwd: Optional[str] = None) -> "WorktreeGuard":
        """Create guard from current environment."""
        if cwd is None:
            cwd = os.getcwd()

        # Try to find main worktree via git
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5,
            )
            git_root = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            git_root = cwd

        # Detect context
        # For Agent Teams, worktrees are at .claude/worktrees/<name>/
        # The main worktree is the one NOT inside .claude/worktrees/
        ctx = detect_worktree_context(cwd, git_root)

        return cls(
            is_delegate=ctx.is_delegate,
            worktree_name=ctx.worktree_name or "",
            worktree_path=cwd,
            main_worktree_path=git_root,
        )
