"""
Tests for CTX-3: context alert hook.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

import alert


def _write_state(path: Path, zone: str, pct: float):
    state = {"zone": zone, "pct": pct, "tokens": 0, "turns": 0, "window": 200000}
    with open(path, "w") as f:
        json.dump(state, f)


class TestShouldAlert(unittest.TestCase):

    def test_no_alert_in_green(self):
        self.assertFalse(alert.should_alert("green", "Agent"))

    def test_no_alert_in_yellow(self):
        self.assertFalse(alert.should_alert("yellow", "WebSearch"))

    def test_alert_in_red(self):
        self.assertTrue(alert.should_alert("red", "Agent"))

    def test_alert_in_critical(self):
        self.assertTrue(alert.should_alert("critical", "Bash"))

    def test_no_alert_for_quiet_tools_in_red(self):
        self.assertFalse(alert.should_alert("red", "Read"))
        self.assertFalse(alert.should_alert("red", "Glob"))
        self.assertFalse(alert.should_alert("red", "Grep"))
        self.assertFalse(alert.should_alert("red", "TodoWrite"))

    def test_no_alert_for_quiet_tools_in_critical(self):
        self.assertFalse(alert.should_alert("critical", "Read"))
        self.assertFalse(alert.should_alert("critical", "Glob"))

    def test_alert_for_expensive_tools_in_red(self):
        for tool in ("Agent", "WebSearch", "WebFetch", "Write", "Edit", "Bash"):
            with self.subTest(tool=tool):
                self.assertTrue(alert.should_alert("red", tool))

    def test_no_alert_for_unknown_zone(self):
        self.assertFalse(alert.should_alert("unknown", "Agent"))

    def test_no_alert_when_zone_missing(self):
        self.assertFalse(alert.should_alert("", "Agent"))


class TestBuildMessage(unittest.TestCase):

    def test_red_message_contains_percentage(self):
        msg = alert.build_message("red", 75.0, "Agent", blocking=False)
        self.assertIn("75%", msg)
        self.assertIn("red", msg)

    def test_critical_message_contains_percentage(self):
        msg = alert.build_message("critical", 91.0, "Bash", blocking=False)
        self.assertIn("91%", msg)
        self.assertIn("CRITICAL", msg)

    def test_critical_blocking_includes_blocking_msg(self):
        msg = alert.build_message("critical", 90.0, "Bash", blocking=True)
        self.assertIn("Blocking", msg)

    def test_critical_non_blocking_says_continuing(self):
        msg = alert.build_message("critical", 90.0, "Bash", blocking=False)
        self.assertIn("Continuing", msg)

    def test_empty_for_green(self):
        msg = alert.build_message("green", 30.0, "Agent", blocking=False)
        self.assertEqual(msg, "")

    def test_empty_for_yellow(self):
        msg = alert.build_message("yellow", 60.0, "Write", blocking=False)
        self.assertEqual(msg, "")


class TestLoadState(unittest.TestCase):

    def test_loads_existing_state(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"zone": "red", "pct": 78.5}, f)
            path = Path(f.name)
        try:
            state = alert.load_state(path)
            self.assertEqual(state["zone"], "red")
            self.assertAlmostEqual(state["pct"], 78.5)
        finally:
            os.unlink(str(path))

    def test_returns_empty_dict_for_missing_file(self):
        state = alert.load_state(Path("/tmp/does_not_exist_alert_test.json"))
        self.assertEqual(state, {})

    def test_returns_empty_dict_for_malformed_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("not json")
            path = Path(f.name)
        try:
            state = alert.load_state(path)
            self.assertEqual(state, {})
        finally:
            os.unlink(str(path))


class TestResponseFormats(unittest.TestCase):

    def test_allow_response_is_empty_dict(self):
        resp = alert._allow_response()
        self.assertEqual(resp, {})

    def test_warn_response_allows(self):
        resp = alert._warn_response("Watch out!")
        decision = resp["hookSpecificOutput"]["permissionDecision"]
        self.assertEqual(decision, "allow")

    def test_block_response_denies(self):
        resp = alert._block_response("Blocked!")
        decision = resp["hookSpecificOutput"]["permissionDecision"]
        self.assertEqual(decision, "deny")
        self.assertIn("denyReason", resp["hookSpecificOutput"])


class TestAlertIntegration(unittest.TestCase):
    """Test full alert logic via load_state + should_alert + build_message."""

    def test_green_zone_no_alert_emitted(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_state(path, "green", 30.0)
        try:
            state = alert.load_state(path)
            zone = state.get("zone", "unknown")
            self.assertFalse(alert.should_alert(zone, "Agent"))
        finally:
            os.unlink(str(path))

    def test_red_zone_expensive_tool_triggers_alert(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_state(path, "red", 74.0)
        try:
            state = alert.load_state(path)
            zone = state.get("zone")
            pct = float(state.get("pct", 0))
            self.assertTrue(alert.should_alert(zone, "WebSearch"))
            msg = alert.build_message(zone, pct, "WebSearch", blocking=False)
            self.assertIn("74%", msg)
            self.assertIn("Continuing", msg)
        finally:
            os.unlink(str(path))

    def test_critical_zone_blocking_mode(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_state(path, "critical", 91.0)
        try:
            state = alert.load_state(path)
            zone = state.get("zone")
            pct = float(state.get("pct", 0))
            msg = alert.build_message(zone, pct, "Agent", blocking=True)
            self.assertIn("Blocking", msg)
            resp = alert._block_response(msg)
            self.assertEqual(resp["hookSpecificOutput"]["permissionDecision"], "deny")
        finally:
            os.unlink(str(path))


if __name__ == "__main__":
    unittest.main()
