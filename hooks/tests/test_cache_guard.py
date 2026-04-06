"""Tests for stop_hook_idle_writer and user_prompt_submit_cache_guard."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

# Add hooks dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_state(idle_secs_ago: float | None = None, extra: dict | None = None) -> dict:
    state = {"pct": 50.0, "zone": "green", "tokens": 100000, "window": 200000}
    if extra:
        state.update(extra)
    if idle_secs_ago is not None:
        ts = datetime.now(timezone.utc) - timedelta(seconds=idle_secs_ago)
        state["idle_since"] = ts.isoformat()
    return state


# ── stop_hook_idle_writer ─────────────────────────────────────────────────────

class TestIdleWriter:
    def test_writes_idle_since_to_state_file(self, tmp_path):
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"pct": 50.0}))

        import stop_hook_idle_writer as m
        with mock.patch.dict(os.environ, {"CLAUDE_CONTEXT_STATE_FILE": str(state_file)}):
            # Reload module-level constant
            m.STATE_FILE = state_file
            m.main()

        result = json.loads(state_file.read_text())
        assert "idle_since" in result
        # Should be recent (within 5 seconds)
        ts = datetime.fromisoformat(result["idle_since"])
        assert (datetime.now(timezone.utc) - ts).total_seconds() < 5

    def test_creates_state_file_if_missing(self, tmp_path):
        state_file = tmp_path / "health.json"
        import stop_hook_idle_writer as m
        m.STATE_FILE = state_file
        m.main()
        assert state_file.exists()
        result = json.loads(state_file.read_text())
        assert "idle_since" in result

    def test_preserves_existing_fields(self, tmp_path):
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps({"pct": 72.5, "zone": "red", "tokens": 145000}))
        import stop_hook_idle_writer as m
        m.STATE_FILE = state_file
        m.main()
        result = json.loads(state_file.read_text())
        assert result["pct"] == 72.5
        assert result["zone"] == "red"
        assert result["tokens"] == 145000

    def test_disabled_env_var(self, tmp_path):
        state_file = tmp_path / "health.json"
        import stop_hook_idle_writer as m
        m.STATE_FILE = state_file
        with mock.patch.dict(os.environ, {"CCA_IDLE_WRITER_DISABLED": "1"}):
            m.main()
        assert not state_file.exists()


# ── user_prompt_submit_cache_guard ────────────────────────────────────────────

class TestCacheGuard:
    def _run_guard(self, state: dict, tmp_path: Path, plan: str = "pro") -> tuple[str, dict]:
        """Run guard, return (stdout, updated_state)."""
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps(state))

        import user_prompt_submit_cache_guard as m
        m.STATE_FILE = state_file

        captured = []
        with mock.patch.dict(os.environ, {"CCA_CLAUDE_PLAN": plan}):
            with mock.patch("builtins.print", side_effect=lambda x: captured.append(x)):
                m.main()

        stdout = captured[0] if captured else ""
        updated = json.loads(state_file.read_text()) if state_file.exists() else {}
        return stdout, updated

    def test_no_warning_when_cache_warm_pro(self, tmp_path):
        state = make_state(idle_secs_ago=60)  # 1 min, under 5 min TTL
        stdout, _ = self._run_guard(state, tmp_path, plan="pro")
        assert stdout == ""

    def test_warning_when_cache_cold_pro(self, tmp_path, capsys):
        state = make_state(idle_secs_ago=400)  # 6+ min, over 5 min TTL
        stdout, updated = self._run_guard(state, tmp_path, plan="pro")
        assert stdout != ""
        msg = json.loads(stdout)
        assert "cache-guard" in msg["message"]
        assert "PRO" in msg["message"]
        # idle_since cleared after warning
        assert "idle_since" not in updated

    def test_warning_when_cache_cold_max(self, tmp_path):
        state = make_state(idle_secs_ago=3700)  # 61+ min, over 60 min TTL
        stdout, updated = self._run_guard(state, tmp_path, plan="max")
        assert stdout != ""
        msg = json.loads(stdout)
        assert "MAX" in msg["message"]

    def test_no_warning_max_under_ttl(self, tmp_path):
        state = make_state(idle_secs_ago=400)  # 6 min — cold for Pro, warm for Max
        stdout, _ = self._run_guard(state, tmp_path, plan="max")
        assert stdout == ""

    def test_no_idle_since_no_warning(self, tmp_path):
        state = {"pct": 50.0, "zone": "green"}  # no idle_since
        stdout, _ = self._run_guard(state, tmp_path)
        assert stdout == ""

    def test_state_file_missing_no_crash(self, tmp_path):
        import user_prompt_submit_cache_guard as m
        m.STATE_FILE = tmp_path / "nonexistent.json"
        m.main()  # should not raise

    def test_disabled_env_var(self, tmp_path):
        state = make_state(idle_secs_ago=999)
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps(state))
        import user_prompt_submit_cache_guard as m
        m.STATE_FILE = state_file
        captured = []
        with mock.patch.dict(os.environ, {"CCA_CACHE_GUARD_DISABLED": "1"}):
            with mock.patch("builtins.print", side_effect=lambda x: captured.append(x)):
                m.main()
        assert captured == []

    def test_warning_fires_only_once(self, tmp_path):
        """Second call after cold idle should not warn (idle_since cleared)."""
        state = make_state(idle_secs_ago=400)
        state_file = tmp_path / "health.json"
        state_file.write_text(json.dumps(state))

        import user_prompt_submit_cache_guard as m
        m.STATE_FILE = state_file

        captured = []
        with mock.patch.dict(os.environ, {"CCA_CLAUDE_PLAN": "pro"}):
            with mock.patch("builtins.print", side_effect=lambda x: captured.append(x)):
                m.main()  # first call — should warn
                m.main()  # second call — idle_since cleared, no warn

        assert len(captured) == 1
