"""Tests for tools.py — Crystal agent tool definitions."""
import unittest

from tools import (
    TOOLS, TOOL_INDEX, TOOL_NAMES,
    PRESS_BUTTONS, NAVIGATE_TO, WAIT,
    validate_tool_call,
)


class TestToolDefinitions(unittest.TestCase):
    """Validate tool schema structure for Claude API."""

    def test_tools_list_has_10_tools(self):
        self.assertEqual(len(TOOLS), 10)

    def test_all_tools_have_name(self):
        for tool in TOOLS:
            self.assertIn("name", tool)
            self.assertIsInstance(tool["name"], str)

    def test_all_tools_have_description(self):
        for tool in TOOLS:
            self.assertIn("description", tool)
            self.assertIsInstance(tool["description"], str)
            self.assertGreater(len(tool["description"]), 10)

    def test_all_tools_have_input_schema(self):
        for tool in TOOLS:
            self.assertIn("input_schema", tool)
            schema = tool["input_schema"]
            self.assertEqual(schema["type"], "object")
            self.assertIn("properties", schema)

    def test_tool_names_match_index(self):
        expected = frozenset([
            "press_buttons", "mash_a", "navigate_to",
            "write_memory", "delete_memory",
            "add_marker", "delete_marker",
            "update_objectives", "wait", "reload_checkpoint",
        ])
        self.assertEqual(TOOL_NAMES, expected)
        self.assertEqual(set(TOOL_INDEX.keys()), set(TOOL_NAMES))

    def test_press_buttons_schema(self):
        schema = PRESS_BUTTONS["input_schema"]
        self.assertIn("buttons", schema["properties"])
        self.assertEqual(schema["properties"]["buttons"]["type"], "array")
        self.assertEqual(schema["required"], ["buttons"])

    def test_press_buttons_valid_enum(self):
        enum = PRESS_BUTTONS["input_schema"]["properties"]["buttons"]["items"]["enum"]
        expected = ["a", "b", "start", "select", "up", "down", "left", "right"]
        self.assertEqual(sorted(enum), sorted(expected))

    def test_navigate_to_schema(self):
        schema = NAVIGATE_TO["input_schema"]
        self.assertIn("x", schema["properties"])
        self.assertIn("y", schema["properties"])
        self.assertEqual(schema["required"], ["x", "y"])

    def test_wait_schema(self):
        schema = WAIT["input_schema"]
        self.assertIn("frames", schema["properties"])


class TestValidateToolCall(unittest.TestCase):
    """Validate tool call validation logic."""

    def test_valid_press_buttons(self):
        ok, err = validate_tool_call("press_buttons", {"buttons": ["a", "b"]})
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_valid_single_button(self):
        ok, err = validate_tool_call("press_buttons", {"buttons": ["start"]})
        self.assertTrue(ok)

    def test_valid_navigate_to(self):
        ok, err = validate_tool_call("navigate_to", {"x": 5, "y": 3})
        self.assertTrue(ok)

    def test_valid_wait_default(self):
        ok, err = validate_tool_call("wait", {})
        self.assertTrue(ok)

    def test_valid_wait_with_frames(self):
        ok, err = validate_tool_call("wait", {"frames": 120})
        self.assertTrue(ok)

    def test_unknown_tool(self):
        ok, err = validate_tool_call("fly_to_moon", {})
        self.assertFalse(ok)
        self.assertIn("Unknown tool", err)

    def test_missing_required_buttons(self):
        ok, err = validate_tool_call("press_buttons", {})
        self.assertFalse(ok)
        self.assertIn("Missing required", err)

    def test_empty_buttons_list(self):
        ok, err = validate_tool_call("press_buttons", {"buttons": []})
        self.assertFalse(ok)
        self.assertIn("empty", err)

    def test_invalid_button_name(self):
        ok, err = validate_tool_call("press_buttons", {"buttons": ["turbo"]})
        self.assertFalse(ok)
        self.assertIn("Invalid button", err)

    def test_buttons_not_list(self):
        ok, err = validate_tool_call("press_buttons", {"buttons": "a"})
        self.assertFalse(ok)
        self.assertIn("must be a list", err)

    def test_missing_navigate_x(self):
        ok, err = validate_tool_call("navigate_to", {"y": 3})
        self.assertFalse(ok)
        self.assertIn("Missing required", err)

    def test_navigate_x_not_int(self):
        ok, err = validate_tool_call("navigate_to", {"x": "five", "y": 3})
        self.assertFalse(ok)
        self.assertIn("must be an integer", err)

    def test_wait_negative_frames(self):
        ok, err = validate_tool_call("wait", {"frames": -10})
        self.assertFalse(ok)
        self.assertIn("non-negative", err)

    def test_all_8_buttons_valid(self):
        for btn in ["a", "b", "start", "select", "up", "down", "left", "right"]:
            ok, err = validate_tool_call("press_buttons", {"buttons": [btn]})
            self.assertTrue(ok, f"Button {btn} should be valid: {err}")

    def test_long_button_sequence(self):
        ok, err = validate_tool_call("press_buttons", {
            "buttons": ["up"] * 20 + ["a"]
        })
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
