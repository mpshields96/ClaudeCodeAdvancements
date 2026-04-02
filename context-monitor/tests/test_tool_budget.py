"""Tests for CTX-6 tool_budget.py — PreToolUse tool-call budget hook."""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
from tool_budget import (
    BASH_SHORT_THRESHOLD,
    DEFAULT_BLOCK,
    DEFAULT_WARN,
    build_block_output,
    build_warn_output,
    check_budget,
    is_exempt,
    load_state,
    save_state,
)


# ---------------------------------------------------------------------------
# is_exempt
# ---------------------------------------------------------------------------

class TestIsExempt:
    def test_read_exempt(self):
        assert is_exempt("Read", {}) is True

    def test_glob_exempt(self):
        assert is_exempt("Glob", {}) is True

    def test_grep_exempt(self):
        assert is_exempt("Grep", {}) is True

    def test_todo_read_exempt(self):
        assert is_exempt("TodoRead", {}) is True

    def test_todo_write_exempt(self):
        assert is_exempt("TodoWrite", {}) is True

    def test_ls_exempt(self):
        assert is_exempt("LS", {}) is True

    def test_bash_short_command_exempt(self):
        short_cmd = "git status"
        assert len(short_cmd) < BASH_SHORT_THRESHOLD
        assert is_exempt("Bash", {"command": short_cmd}) is True

    def test_bash_long_command_not_exempt(self):
        long_cmd = "python3 " + "x" * BASH_SHORT_THRESHOLD
        assert is_exempt("Bash", {"command": long_cmd}) is False

    def test_bash_at_threshold_not_exempt(self):
        cmd = "x" * BASH_SHORT_THRESHOLD
        assert is_exempt("Bash", {"command": cmd}) is False

    def test_bash_just_under_threshold_exempt(self):
        cmd = "x" * (BASH_SHORT_THRESHOLD - 1)
        assert is_exempt("Bash", {"command": cmd}) is True

    def test_agent_not_exempt(self):
        assert is_exempt("Agent", {}) is False

    def test_write_not_exempt(self):
        assert is_exempt("Write", {"file_path": "/tmp/foo"}) is False

    def test_edit_not_exempt(self):
        assert is_exempt("Edit", {"file_path": "/tmp/foo"}) is False

    def test_web_fetch_not_exempt(self):
        assert is_exempt("WebFetch", {"url": "https://example.com"}) is False

    def test_bash_missing_command_key_short(self):
        # Empty string (missing key) < threshold → exempt
        assert is_exempt("Bash", {}) is True


# ---------------------------------------------------------------------------
# load_state / save_state
# ---------------------------------------------------------------------------

class TestStatePersistence:
    def test_load_nonexistent_returns_zeroed(self, tmp_path):
        state = load_state(tmp_path / "missing.json")
        assert state["call_count"] == 0
        assert state["warnings_issued"] == 0
        assert state["session_id"] == ""

    def test_save_then_load_roundtrip(self, tmp_path):
        path = tmp_path / "budget.json"
        original = {"session_id": "sess_abc", "call_count": 7, "warnings_issued": 2}
        save_state(path, original)
        loaded = load_state(path)
        assert loaded["session_id"] == "sess_abc"
        assert loaded["call_count"] == 7
        assert loaded["warnings_issued"] == 2

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "a" / "b" / "c" / "budget.json"
        save_state(path, {"session_id": "x", "call_count": 1, "warnings_issued": 0})
        assert path.exists()

    def test_load_corrupted_json_returns_zeroed(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{{")
        state = load_state(path)
        assert state["call_count"] == 0

    def test_save_writes_updated_at(self, tmp_path):
        path = tmp_path / "budget.json"
        save_state(path, {"session_id": "s1", "call_count": 3, "warnings_issued": 0})
        raw = json.loads(path.read_text())
        assert "updated_at" in raw


# ---------------------------------------------------------------------------
# check_budget
# ---------------------------------------------------------------------------

class TestCheckBudget:
    def _fresh_state(self, session_id="sess1"):
        return {"session_id": session_id, "call_count": 0, "warnings_issued": 0}

    def test_allow_below_warn(self):
        state = self._fresh_state()
        action, new_state = check_budget("sess1", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert action == "allow"
        assert new_state["call_count"] == 1

    def test_warn_at_warn_threshold(self):
        state = {"session_id": "sess1", "call_count": 14, "warnings_issued": 0}
        action, new_state = check_budget("sess1", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert action == "warn"
        assert new_state["call_count"] == 15

    def test_warn_above_warn_below_block(self):
        state = {"session_id": "sess1", "call_count": 20, "warnings_issued": 1}
        action, _ = check_budget("sess1", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert action == "warn"

    def test_block_at_block_threshold(self):
        state = {"session_id": "sess1", "call_count": 29, "warnings_issued": 5}
        action, new_state = check_budget("sess1", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert action == "block"
        assert new_state["call_count"] == 30

    def test_block_above_block_threshold(self):
        state = {"session_id": "sess1", "call_count": 50, "warnings_issued": 10}
        action, _ = check_budget("sess1", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert action == "block"

    def test_new_session_resets_counter(self):
        state = {"session_id": "old_sess", "call_count": 25, "warnings_issued": 5}
        action, new_state = check_budget("new_sess", "Write", {}, state, warn_threshold=15, block_threshold=30)
        # After reset, count is 1 (this call), which is below warn threshold
        assert action == "allow"
        assert new_state["call_count"] == 1
        assert new_state["session_id"] == "new_sess"

    def test_new_session_with_high_prior_count_does_not_block(self):
        # Old session had 40 calls, new session starts fresh
        state = {"session_id": "old", "call_count": 40, "warnings_issued": 15}
        action, new_state = check_budget("new", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert action == "allow"
        assert new_state["call_count"] == 1

    def test_exempt_tool_does_not_increment(self):
        state = {"session_id": "sess1", "call_count": 10, "warnings_issued": 0}
        action, new_state = check_budget("sess1", "Read", {}, state, warn_threshold=15, block_threshold=30)
        assert action == "allow"
        assert new_state["call_count"] == 10  # unchanged

    def test_custom_warn_threshold_via_lower_value(self):
        state = {"session_id": "sess1", "call_count": 4, "warnings_issued": 0}
        action, _ = check_budget("sess1", "Write", {}, state, warn_threshold=5, block_threshold=10)
        assert action == "warn"

    def test_custom_block_threshold_via_lower_value(self):
        state = {"session_id": "sess1", "call_count": 9, "warnings_issued": 0}
        action, _ = check_budget("sess1", "Write", {}, state, warn_threshold=5, block_threshold=10)
        assert action == "block"

    def test_missing_session_id_still_counts(self):
        state = {"session_id": "", "call_count": 14, "warnings_issued": 0}
        action, new_state = check_budget("", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert action == "warn"
        assert new_state["call_count"] == 15

    def test_empty_state_resets_on_new_session(self):
        state = load_state(Path("/nonexistent/path/budget.json"))  # returns zeroed
        action, new_state = check_budget("sess1", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert action == "allow"
        assert new_state["call_count"] == 1

    def test_warnings_issued_increments_on_warn(self):
        state = {"session_id": "sess1", "call_count": 14, "warnings_issued": 0}
        _, new_state = check_budget("sess1", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert new_state["warnings_issued"] == 1

    def test_warnings_issued_increments_on_block(self):
        state = {"session_id": "sess1", "call_count": 29, "warnings_issued": 5}
        _, new_state = check_budget("sess1", "Write", {}, state, warn_threshold=15, block_threshold=30)
        assert new_state["warnings_issued"] == 6


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------

class TestOutputBuilders:
    def test_warn_output_has_additional_context(self):
        out = build_warn_output(16, 30)
        assert "hookSpecificOutput" in out
        assert "additionalContext" in out["hookSpecificOutput"]
        assert "16/30" in out["hookSpecificOutput"]["additionalContext"]

    def test_block_output_has_permission_denied(self):
        out = build_block_output(30, 30)
        assert "hookSpecificOutput" in out
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "reason" in out["hookSpecificOutput"]
        assert "30/30" in out["hookSpecificOutput"]["reason"]

    def test_warn_output_is_valid_json_serializable(self):
        out = build_warn_output(20, 30)
        assert json.dumps(out)  # does not raise

    def test_block_output_is_valid_json_serializable(self):
        out = build_block_output(30, 30)
        assert json.dumps(out)  # does not raise
