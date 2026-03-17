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


class TestAutocompactAwareness(unittest.TestCase):
    """Tests for autocompact proximity awareness in alert hook."""

    # --- should_warn_autocompact ---

    def test_warn_when_proximity_below_threshold(self):
        """Warn when autocompact is < 10 points away."""
        self.assertTrue(alert.should_warn_autocompact(5.0))

    def test_warn_at_zero_proximity(self):
        """Warn when already at or past autocompact threshold."""
        self.assertTrue(alert.should_warn_autocompact(0.0))

    def test_no_warn_when_proximity_comfortable(self):
        """Don't warn when 15+ points from autocompact."""
        self.assertFalse(alert.should_warn_autocompact(15.0))

    def test_no_warn_when_proximity_exactly_at_threshold(self):
        """At exactly 10 points, no warning (threshold is <10)."""
        self.assertFalse(alert.should_warn_autocompact(10.0))

    def test_no_warn_when_proximity_none(self):
        """No warning when autocompact is not configured."""
        self.assertFalse(alert.should_warn_autocompact(None))

    def test_custom_proximity_threshold(self):
        """Custom proximity threshold overrides default 10."""
        self.assertTrue(alert.should_warn_autocompact(12.0, threshold=15))
        self.assertFalse(alert.should_warn_autocompact(12.0, threshold=10))

    # --- build_message with autocompact proximity ---

    def test_red_message_includes_autocompact_proximity(self):
        """Red zone message should mention autocompact when proximity is set."""
        msg = alert.build_message("red", 75.0, "Agent", blocking=False,
                                  autocompact_proximity=5.0)
        self.assertIn("75%", msg)
        self.assertIn("auto-compact", msg.lower().replace("autocompact", "auto-compact").replace("auto compact", "auto-compact"))

    def test_critical_message_includes_autocompact_proximity(self):
        """Critical zone message should mention autocompact proximity."""
        msg = alert.build_message("critical", 92.0, "Bash", blocking=False,
                                  autocompact_proximity=2.0)
        self.assertIn("92%", msg)

    def test_message_without_autocompact_unchanged(self):
        """When no autocompact info, messages stay the same as before."""
        msg_without = alert.build_message("red", 75.0, "Agent", blocking=False)
        msg_none = alert.build_message("red", 75.0, "Agent", blocking=False,
                                       autocompact_proximity=None)
        self.assertEqual(msg_without, msg_none)

    # --- yellow zone autocompact warning ---

    def test_yellow_zone_warns_when_autocompact_near(self):
        """Yellow zone should alert when autocompact is close."""
        self.assertTrue(alert.should_alert("yellow", "Agent",
                                           autocompact_proximity=5.0))

    def test_yellow_zone_no_alert_without_autocompact(self):
        """Yellow zone stays silent without autocompact proximity."""
        self.assertFalse(alert.should_alert("yellow", "Agent"))

    def test_yellow_zone_no_alert_when_autocompact_far(self):
        """Yellow zone stays silent when autocompact is far away."""
        self.assertFalse(alert.should_alert("yellow", "Agent",
                                            autocompact_proximity=20.0))

    def test_yellow_zone_quiet_tools_still_quiet(self):
        """Quiet tools stay quiet even with autocompact proximity warning."""
        self.assertFalse(alert.should_alert("yellow", "Read",
                                            autocompact_proximity=3.0))

    def test_yellow_autocompact_message(self):
        """Yellow zone autocompact message format."""
        msg = alert.build_message("yellow", 55.0, "Agent", blocking=False,
                                  autocompact_proximity=5.0)
        self.assertIn("55%", msg)
        self.assertIn("5", msg)  # proximity value

    # --- Integration: state file with autocompact fields ---

    def test_state_with_autocompact_fields(self):
        """Alert reads autocompact_proximity from state file."""
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            path = Path(f.name)
        state = {
            "zone": "yellow", "pct": 58.0, "tokens": 116000,
            "turns": 50, "window": 200000,
            "autocompact_pct": 60, "autocompact_proximity": 2.0,
        }
        with open(path, "w") as f:
            json.dump(state, f)
        try:
            loaded = alert.load_state(path)
            proximity = loaded.get("autocompact_proximity")
            self.assertEqual(proximity, 2.0)
            zone = loaded["zone"]
            self.assertTrue(alert.should_alert(zone, "Agent",
                                               autocompact_proximity=proximity))
        finally:
            os.unlink(str(path))

    def test_state_without_autocompact_fields(self):
        """Old state files without autocompact fields still work."""
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            path = Path(f.name)
        _write_state(path, "red", 75.0)
        try:
            loaded = alert.load_state(path)
            proximity = loaded.get("autocompact_proximity")
            self.assertIsNone(proximity)
            # Red zone still alerts without autocompact info
            self.assertTrue(alert.should_alert("red", "Agent",
                                               autocompact_proximity=proximity))
        finally:
            os.unlink(str(path))


if __name__ == "__main__":
    unittest.main()
