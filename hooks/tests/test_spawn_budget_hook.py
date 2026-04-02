"""Tests for spawn_budget_hook.py — agent spawn budget tracking."""

import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spawn_budget_hook import load_budget, save_budget, main, BUDGET_FILE


class TestLoadBudget(unittest.TestCase):
    def test_fresh_budget(self):
        with patch("spawn_budget_hook.BUDGET_FILE", Path(tempfile.mktemp())):
            b = load_budget()
            self.assertEqual(b["total_count"], 0)
            self.assertEqual(b["total_estimated_tokens"], 0)

    def test_stale_date_resets(self):
        tmp = Path(tempfile.mktemp())
        tmp.write_text(json.dumps({"date": "2020-01-01", "total_count": 5, "total_estimated_tokens": 200000, "spawns": []}))
        with patch("spawn_budget_hook.BUDGET_FILE", tmp):
            b = load_budget()
            self.assertEqual(b["total_count"], 0)  # Reset because old date


class TestMainHook(unittest.TestCase):
    def _run_hook(self, tool_name="Agent", subagent_type="cca-reviewer", model="sonnet", env_overrides=None):
        hook_input = json.dumps({
            "tool_name": tool_name,
            "tool_input": {"subagent_type": subagent_type, "description": "test", "model": model}
        })
        tmp = Path(tempfile.mktemp())
        env = env_overrides or {}
        with patch("spawn_budget_hook.BUDGET_FILE", tmp):
            with patch.dict(os.environ, env, clear=False):
                with patch("sys.stdin", StringIO(hook_input)):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        main()
                        return mock_out.getvalue().strip(), tmp

    def test_tracks_agent_spawn(self):
        _, tmp = self._run_hook()
        data = json.loads(tmp.read_text())
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(len(data["spawns"]), 1)
        self.assertEqual(data["spawns"][0]["type"], "cca-reviewer")

    def test_ignores_non_agent_tools(self):
        output, tmp = self._run_hook(tool_name="Read")
        self.assertEqual(output, "")
        self.assertFalse(tmp.exists())

    def test_silent_under_threshold(self):
        output, _ = self._run_hook()
        self.assertEqual(output, "")  # 40K << 200K threshold

    def test_warns_at_threshold(self):
        # Set threshold very low so one spawn triggers it
        output, _ = self._run_hook(env_overrides={"CCA_SPAWN_BUDGET_THRESHOLD": "10000"})
        self.assertIn("WARNING", output)

    def test_soft_warn_at_75pct(self):
        # 40K sonnet spawn vs 50K threshold = 80% → soft warn
        output, _ = self._run_hook(env_overrides={"CCA_SPAWN_BUDGET_THRESHOLD": "50000"})
        self.assertIn("Approaching", output)

    def test_haiku_lower_cost(self):
        _, tmp = self._run_hook(model="haiku")
        data = json.loads(tmp.read_text())
        self.assertEqual(data["spawns"][0]["estimated_tokens"], 12000)  # 40K * 0.3

    def test_opus_higher_cost(self):
        _, tmp = self._run_hook(model="opus")
        data = json.loads(tmp.read_text())
        self.assertEqual(data["spawns"][0]["estimated_tokens"], 100000)  # 40K * 2.5

    def test_disabled(self):
        output, tmp = self._run_hook(env_overrides={"CCA_SPAWN_BUDGET_DISABLED": "1"})
        self.assertEqual(output, "")
        self.assertFalse(tmp.exists())

    def test_empty_stdin(self):
        with patch("spawn_budget_hook.BUDGET_FILE", Path(tempfile.mktemp())):
            with patch("sys.stdin", StringIO("")):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()  # Should not raise


if __name__ == "__main__":
    unittest.main()
