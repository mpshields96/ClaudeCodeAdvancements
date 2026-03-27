"""Tool definitions for the Crystal agent.

Minimal tool surface — 2 core tools + 1 utility. Let Opus 4.6 reason
through menus and battles via button presses rather than building
elaborate tool chains.

These are Anthropic API tool definitions (JSON Schema format).
"""

# ── Tool definitions for Claude API ──────────────────────────────────────────

PRESS_BUTTONS = {
    "name": "press_buttons",
    "description": (
        "Press Game Boy buttons in sequence. Each button is pressed and released "
        "with appropriate timing. Use this for all direct input: movement, menus, "
        "battles, text advancement, and dialog choices."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "buttons": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["a", "b", "start", "select",
                             "up", "down", "left", "right"],
                },
                "description": (
                    "Buttons to press in order. Examples: "
                    '["a"] to confirm, ["b"] to cancel, '
                    '["up", "up", "a"] to select a menu item, '
                    '["right", "right", "right"] to walk 3 tiles right.'
                ),
            },
            "wait_frames": {
                "type": "integer",
                "description": (
                    "Extra frames to wait after the sequence completes. "
                    "Use 60 (~1 second) for animations, 30 for menus. "
                    "Default: 0 (no extra wait)."
                ),
                "default": 0,
            },
        },
        "required": ["buttons"],
    },
}

NAVIGATE_TO = {
    "name": "navigate_to",
    "description": (
        "Navigate to specific grid coordinates using A* pathfinding. "
        "The agent will automatically find and walk the shortest path, "
        "avoiding walls and obstacles. Only works on the current map — "
        "use press_buttons to enter doors or change maps. "
        "Coordinates are in the current map's tile grid (from RAM state)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "x": {
                "type": "integer",
                "description": "Target X coordinate (tile column).",
            },
            "y": {
                "type": "integer",
                "description": "Target Y coordinate (tile row).",
            },
        },
        "required": ["x", "y"],
    },
}

WAIT = {
    "name": "wait",
    "description": (
        "Wait without pressing any buttons. Useful for: waiting for "
        "animations to finish, letting an NPC move, or pausing to observe "
        "the game state. Advances the emulator by the specified number of frames."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "frames": {
                "type": "integer",
                "description": (
                    "Number of frames to wait. 60 frames = ~1 second. "
                    "Common values: 30 (half second), 60 (one second), "
                    "120 (two seconds for long animations)."
                ),
                "default": 60,
            },
        },
        "required": [],
    },
}


RELOAD_CHECKPOINT = {
    "name": "reload_checkpoint",
    "description": (
        "Reload the most recent save-state checkpoint. Use this when: "
        "your entire party has fainted, you lost a gym leader battle and "
        "want to retry, or you're in an unrecoverable situation. "
        "The game will rewind to the last auto-saved checkpoint."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why you're reloading (for logging).",
            },
        },
        "required": ["reason"],
    },
}


# ── Tool list for Claude API ─────────────────────────────────────────────────

TOOLS = [PRESS_BUTTONS, NAVIGATE_TO, WAIT, RELOAD_CHECKPOINT]

# Tool name -> definition lookup
TOOL_INDEX = {t["name"]: t for t in TOOLS}

# Valid tool names (for routing)
TOOL_NAMES = frozenset(TOOL_INDEX.keys())


def validate_tool_call(name: str, input_data: dict) -> tuple:
    """Validate a tool call from Claude's response.

    Returns (is_valid, error_message).
    """
    if name not in TOOL_NAMES:
        return False, f"Unknown tool: {name}"

    schema = TOOL_INDEX[name]["input_schema"]
    required = schema.get("required", [])

    for field in required:
        if field not in input_data:
            return False, f"Missing required field: {field}"

    # Validate button names
    if name == "press_buttons":
        buttons = input_data.get("buttons", [])
        if not isinstance(buttons, list):
            return False, "buttons must be a list"
        if len(buttons) == 0:
            return False, "buttons list cannot be empty"
        valid_buttons = {"a", "b", "start", "select", "up", "down", "left", "right"}
        for b in buttons:
            if b not in valid_buttons:
                return False, f"Invalid button: {b}"

    # Validate coordinates
    if name == "navigate_to":
        for coord in ("x", "y"):
            val = input_data.get(coord)
            if not isinstance(val, int):
                return False, f"{coord} must be an integer"

    # Validate frames
    if name == "wait":
        frames = input_data.get("frames", 60)
        if not isinstance(frames, int) or frames < 0:
            return False, "frames must be a non-negative integer"

    return True, ""
