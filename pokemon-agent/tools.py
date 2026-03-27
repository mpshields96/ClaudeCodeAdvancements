"""Tool definitions for the Pokemon agent.

Full tool surface stolen from GPT Plays Pokemon FireRed (clad3815) +
PokeAgent (sethkarten). Gives Claude the same capabilities:
- press_buttons: direct Game Boy input
- mash_a: spam A to clear dialog (a_until_end_of_dialog equivalent)
- navigate_to: A* pathfinding
- write_memory / delete_memory: persistent strategic notes
- add_marker / delete_marker: map annotations
- update_objectives: quest log management
- wait: advance emulator frames
- reload_checkpoint: reload save state

These are Anthropic API tool definitions (JSON Schema format).
"""

# ── Core input tools ─────────────────────────────────────────────────────

PRESS_BUTTONS = {
    "name": "press_buttons",
    "description": (
        "Press Game Boy buttons in sequence. Each button is pressed and released "
        "with appropriate timing. Use this for: movement (short distances), "
        "menu navigation, battle commands, and dialog choices. "
        "For clearing long dialog, use mash_a instead."
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

MASH_A = {
    "name": "mash_a",
    "description": (
        "Rapidly press A to advance through all current dialog and text. "
        "Equivalent to GPT harness 'a_until_end_of_dialog'. Use when: "
        "an NPC is talking, a sign is being read, battle text is scrolling, "
        "or any multi-line text box needs clearing. Presses A repeatedly "
        "until no more text is detected. Much faster than pressing A manually."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "max_presses": {
                "type": "integer",
                "description": "Maximum A presses before stopping. Default: 20.",
                "default": 20,
            },
        },
        "required": [],
    },
}

NAVIGATE_TO = {
    "name": "navigate_to",
    "description": (
        "Navigate to specific grid coordinates using A* pathfinding. "
        "The agent will automatically find and walk the shortest path, "
        "avoiding walls and obstacles. Only works on the current map — "
        "use press_buttons to enter doors or change maps. "
        "Use exact target coordinates (the position of the door/NPC/item), "
        "not a tile in front of it. For long distances or when you keep "
        "failing to reach a destination with press_buttons."
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

# ── Memory tools (from GPT FireRed harness) ──────────────────────────────

WRITE_MEMORY = {
    "name": "write_memory",
    "description": (
        "Save a persistent note for future reference. Use for strategic "
        "knowledge that the game state doesn't track: tips from mistakes "
        "(prefix with 'tips_'), puzzle solutions, boss dossiers (team, moves, "
        "weaknesses, winning strategy), PC Pokemon, route connections, "
        "shop inventories. Do NOT store raw game data (HP, money, etc.) — "
        "that comes from RAM automatically."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": (
                    "Memory key. Use descriptive prefixes: "
                    "'tips_' for lessons, 'boss_' for boss dossiers, "
                    "'pc_' for PC Pokemon, 'route_' for connections."
                ),
            },
            "value": {
                "type": "string",
                "description": "The information to remember.",
            },
        },
        "required": ["key", "value"],
    },
}

DELETE_MEMORY = {
    "name": "delete_memory",
    "description": (
        "Delete a memory entry that is no longer needed or is outdated."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The memory key to delete.",
            },
        },
        "required": ["key"],
    },
}

# ── Marker tools (from GPT FireRed harness) ──────────────────────────────

ADD_MARKER = {
    "name": "add_marker",
    "description": (
        "Place a marker on the current map for future reference. Use for: "
        "doors (and where they lead), ladders/stairs, important NPCs, "
        "shops, Pokemon Centers, items on the ground, route exits, "
        "and map connections. Markers help you navigate back to places."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "x": {
                "type": "integer",
                "description": "X coordinate to mark.",
            },
            "y": {
                "type": "integer",
                "description": "Y coordinate to mark.",
            },
            "label": {
                "type": "string",
                "description": (
                    "Description of what's here. Examples: "
                    "'Door to Route 1', 'Nurse Joy', 'Potion on ground', "
                    "'Gym Leader Brock', 'Exit to Viridian City'."
                ),
            },
            "marker_type": {
                "type": "string",
                "enum": ["door", "npc", "shop", "pokecenter", "gym",
                         "item", "exit", "stairs", "poi"],
                "description": "Type of marker. Default: poi (point of interest).",
                "default": "poi",
            },
        },
        "required": ["x", "y", "label"],
    },
}

DELETE_MARKER = {
    "name": "delete_marker",
    "description": "Remove a marker from the current map.",
    "input_schema": {
        "type": "object",
        "properties": {
            "x": {
                "type": "integer",
                "description": "X coordinate of marker to remove.",
            },
            "y": {
                "type": "integer",
                "description": "Y coordinate of marker to remove.",
            },
        },
        "required": ["x", "y"],
    },
}

# ── Objectives tool (from GPT FireRed harness) ──────────────────────────

UPDATE_OBJECTIVES = {
    "name": "update_objectives",
    "description": (
        "Update the quest log with current goals. Each objective should "
        "include WHY it matters and HOW you'll do it. Use for medium/long "
        "term goals like 'Defeat Brock' or 'Get to Cerulean City', not "
        "micro-actions like 'Walk 3 tiles up'. Call this when your goals "
        "change: after earning a badge, clearing a dungeon, or deciding "
        "on a new plan."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "objectives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "What to do.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Why it matters and how to do it.",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["active", "completed", "abandoned"],
                            "default": "active",
                        },
                    },
                    "required": ["description"],
                },
                "description": "Full list of current objectives (replaces previous).",
            },
        },
        "required": ["objectives"],
    },
}

# ── Utility tools ────────────────────────────────────────────────────────

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


# ── Tool list for Claude API ─────────────────────────────────────────────

TOOLS = [
    PRESS_BUTTONS,
    MASH_A,
    NAVIGATE_TO,
    WRITE_MEMORY,
    DELETE_MEMORY,
    ADD_MARKER,
    DELETE_MARKER,
    UPDATE_OBJECTIVES,
    WAIT,
    RELOAD_CHECKPOINT,
]

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
    if name in ("navigate_to", "add_marker", "delete_marker"):
        for coord in ("x", "y"):
            if coord in required or coord in input_data:
                val = input_data.get(coord)
                if val is not None and not isinstance(val, int):
                    return False, f"{coord} must be an integer"

    # Validate frames
    if name == "wait":
        frames = input_data.get("frames", 60)
        if not isinstance(frames, int) or frames < 0:
            return False, "frames must be a non-negative integer"

    # Validate memory key
    if name in ("write_memory", "delete_memory"):
        key = input_data.get("key", "")
        if not isinstance(key, str) or not key.strip():
            return False, "key must be a non-empty string"

    return True, ""
