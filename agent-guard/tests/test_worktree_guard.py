"""
Tests for worktree isolation guard (AG-10).

Detects Agent Teams / worktree contexts and validates isolation:
- Worktree detection (git worktree list parsing)
- Scope restriction (prevent cross-worktree writes)
- Main-worktree protection (prevent delegates from modifying shared state)
- Safety classification (stricter rules for delegated agents)
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from worktree_guard import (
    WorktreeInfo,
    WorktreeGuard,
    parse_worktree_list,
    detect_worktree_context,
    is_shared_state_file,
    SHARED_STATE_PATTERNS,
)


class TestParseWorktreeList(unittest.TestCase):
    """Parse `git worktree list --porcelain` output."""

    def test_single_worktree(self):
        output = (
            "worktree /Users/dev/project\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
        )
        result = parse_worktree_list(output)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].path, "/Users/dev/project")
        self.assertEqual(result[0].branch, "main")
        self.assertTrue(result[0].is_main)

    def test_multiple_worktrees(self):
        output = (
            "worktree /Users/dev/project\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /Users/dev/project/.claude/worktrees/feature-a\n"
            "HEAD def456\n"
            "branch refs/heads/feature-a\n"
            "\n"
            "worktree /Users/dev/project/.claude/worktrees/feature-b\n"
            "HEAD ghi789\n"
            "branch refs/heads/feature-b\n"
            "\n"
        )
        result = parse_worktree_list(output)
        self.assertEqual(len(result), 3)
        self.assertTrue(result[0].is_main)
        self.assertFalse(result[1].is_main)
        self.assertFalse(result[2].is_main)

    def test_empty_output(self):
        result = parse_worktree_list("")
        self.assertEqual(result, [])

    def test_bare_worktree(self):
        """Bare worktrees have no branch line."""
        output = (
            "worktree /Users/dev/project\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /tmp/worktree-1\n"
            "HEAD def456\n"
            "detached\n"
            "\n"
        )
        result = parse_worktree_list(output)
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[1].branch)
        self.assertTrue(result[1].is_detached)


class TestDetectWorktreeContext(unittest.TestCase):
    """Detect if current CWD is inside a worktree."""

    def test_main_worktree(self):
        info = detect_worktree_context(
            cwd="/Users/dev/project",
            main_worktree="/Users/dev/project",
        )
        self.assertTrue(info.is_main)
        self.assertFalse(info.is_delegate)

    def test_delegate_worktree(self):
        info = detect_worktree_context(
            cwd="/Users/dev/project/.claude/worktrees/feature-a",
            main_worktree="/Users/dev/project",
        )
        self.assertFalse(info.is_main)
        self.assertTrue(info.is_delegate)

    def test_claude_worktree_path_pattern(self):
        info = detect_worktree_context(
            cwd="/Users/dev/project/.claude/worktrees/fix-bug-123/src",
            main_worktree="/Users/dev/project",
        )
        self.assertTrue(info.is_delegate)
        self.assertEqual(info.worktree_name, "fix-bug-123")


class TestSharedStateFiles(unittest.TestCase):
    """Shared state files that delegates should not modify."""

    def test_session_state_is_shared(self):
        self.assertTrue(is_shared_state_file("SESSION_STATE.md"))

    def test_project_index_is_shared(self):
        self.assertTrue(is_shared_state_file("PROJECT_INDEX.md"))

    def test_changelog_is_shared(self):
        self.assertTrue(is_shared_state_file("CHANGELOG.md"))

    def test_claude_md_is_shared(self):
        self.assertTrue(is_shared_state_file("CLAUDE.md"))

    def test_regular_code_not_shared(self):
        self.assertFalse(is_shared_state_file("src/main.py"))

    def test_test_file_not_shared(self):
        self.assertFalse(is_shared_state_file("tests/test_foo.py"))

    def test_settings_is_shared(self):
        self.assertTrue(is_shared_state_file(".claude/settings.local.json"))

    def test_lock_files_are_shared(self):
        self.assertTrue(is_shared_state_file(".agent-manifest.json"))

    def test_git_config_is_shared(self):
        self.assertTrue(is_shared_state_file(".git/config"))


class TestWorktreeGuard(unittest.TestCase):
    """WorktreeGuard validates file operations in worktree context."""

    def _make_guard(self, is_delegate=True, worktree_name="feature-a",
                    worktree_path="/project/.claude/worktrees/feature-a",
                    main_path="/project"):
        return WorktreeGuard(
            is_delegate=is_delegate,
            worktree_name=worktree_name,
            worktree_path=worktree_path,
            main_worktree_path=main_path,
        )

    def test_delegate_can_write_own_worktree(self):
        guard = self._make_guard()
        result = guard.check_write("/project/.claude/worktrees/feature-a/src/main.py")
        self.assertEqual(result.decision, "allow")

    def test_delegate_blocked_from_main_worktree(self):
        guard = self._make_guard()
        result = guard.check_write("/project/src/main.py")
        self.assertEqual(result.decision, "block")
        self.assertIn("main worktree", result.reason.lower())

    def test_delegate_blocked_from_shared_state(self):
        guard = self._make_guard()
        result = guard.check_write("/project/.claude/worktrees/feature-a/SESSION_STATE.md")
        self.assertEqual(result.decision, "warn")
        self.assertIn("shared state", result.reason.lower())

    def test_main_worktree_unrestricted(self):
        guard = self._make_guard(is_delegate=False)
        result = guard.check_write("/project/SESSION_STATE.md")
        self.assertEqual(result.decision, "allow")

    def test_delegate_can_read_anything(self):
        """Read operations are never blocked."""
        guard = self._make_guard()
        result = guard.check_read("/project/src/main.py")
        self.assertEqual(result.decision, "allow")

    def test_delegate_blocked_from_other_worktree(self):
        guard = self._make_guard(worktree_name="feature-a")
        result = guard.check_write("/project/.claude/worktrees/feature-b/src/main.py")
        self.assertEqual(result.decision, "block")
        self.assertIn("other worktree", result.reason.lower())

    def test_guard_disabled_when_not_delegate(self):
        """When not in a delegate worktree, all writes allowed."""
        guard = self._make_guard(is_delegate=False)
        result = guard.check_write("/anywhere/file.py")
        self.assertEqual(result.decision, "allow")

    def test_delegate_git_push_to_main_blocked(self):
        guard = self._make_guard()
        result = guard.check_bash("git push origin main")
        self.assertEqual(result.decision, "block")
        self.assertIn("destructive git command", result.reason.lower())

    def test_delegate_git_push_to_own_branch_allowed(self):
        guard = self._make_guard(worktree_name="feature-a")
        result = guard.check_bash("git push origin feature-a")
        self.assertEqual(result.decision, "allow")

    def test_delegate_destructive_git_blocked(self):
        guard = self._make_guard()
        result = guard.check_bash("git reset --hard HEAD~3")
        self.assertEqual(result.decision, "block")

    def test_summary(self):
        guard = self._make_guard()
        s = guard.summary()
        self.assertIn("feature-a", s)
        self.assertIn("delegate", s.lower())


class TestWorktreeGuardCheckResult(unittest.TestCase):
    """CheckResult dataclass behavior."""

    def test_allow_result(self):
        guard = self._make_guard(is_delegate=False)
        result = guard.check_write("/any/file.py")
        self.assertEqual(result.decision, "allow")
        self.assertEqual(result.reason, "")

    def test_block_result_has_reason(self):
        guard = self._make_guard()
        result = guard.check_write("/project/src/main.py")
        self.assertNotEqual(result.reason, "")

    def _make_guard(self, **kwargs):
        defaults = dict(
            is_delegate=True, worktree_name="feat",
            worktree_path="/project/.claude/worktrees/feat",
            main_worktree_path="/project",
        )
        defaults.update(kwargs)
        return WorktreeGuard(**defaults)


if __name__ == "__main__":
    unittest.main()
