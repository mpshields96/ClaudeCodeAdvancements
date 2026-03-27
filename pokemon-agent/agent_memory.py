"""Persistent agent memory — notepad, markers, and objectives.

Stolen from GPT Plays Pokemon FireRed architecture (clad3815).
The AI agent uses these to persist knowledge across turns:
- Memory: strategic notes, tips, boss dossiers
- Markers: map annotations (doors, NPCs, shops, connections)
- Objectives: quest log with WHY/HOW/WHAT rationale

All data persists as JSON files in bridge_io/ so the agent can
read them back on every turn. This is what separates a good
Pokemon bot from one that walks in circles.

Stdlib only.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

BRIDGE_DIR = os.path.join(os.path.dirname(__file__), "bridge_io")
MEMORY_FILE = os.path.join(BRIDGE_DIR, "memory.json")
MARKERS_FILE = os.path.join(BRIDGE_DIR, "markers.json")
OBJECTIVES_FILE = os.path.join(BRIDGE_DIR, "objectives.json")
HISTORY_FILE = os.path.join(BRIDGE_DIR, "history.json")


def _load_json(path: str, default: Any = None) -> Any:
    """Load JSON file, returning default if missing/corrupt."""
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default if default is not None else {}


def _save_json(path: str, data: Any) -> None:
    """Atomically save JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


# ── Agent Memory (persistent strategic notes) ────────────────────────────

class AgentMemory:
    """Persistent key-value memory for the AI agent.

    Stolen from GPT FireRed harness. The agent writes strategic notes
    that persist across turns: tips from mistakes, puzzle solutions,
    boss dossiers, PC Pokemon, important observations.

    NOT for raw RAM data (that comes from state.json). This is for
    learned knowledge that the game state doesn't track.
    """

    def __init__(self, path: str = MEMORY_FILE):
        self.path = path
        self.data: Dict[str, str] = _load_json(path, {})

    def write(self, key: str, value: str) -> str:
        """Write a memory entry. Returns confirmation message."""
        self.data[key] = value
        _save_json(self.path, self.data)
        return f"Memory saved: {key}"

    def delete(self, key: str) -> str:
        """Delete a memory entry. Returns confirmation message."""
        if key in self.data:
            del self.data[key]
            _save_json(self.path, self.data)
            return f"Memory deleted: {key}"
        return f"Memory key not found: {key}"

    def read_all(self) -> Dict[str, str]:
        """Read all memory entries."""
        return dict(self.data)

    def format_for_prompt(self) -> str:
        """Format all memories for inclusion in the AI prompt."""
        if not self.data:
            return "No memories stored yet."
        lines = []
        for key, value in self.data.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def count(self) -> int:
        return len(self.data)


# ── Map Markers (annotations on the game map) ────────────────────────────

class MapMarkers:
    """Persistent map annotations for navigation.

    Stolen from GPT FireRed harness. The agent places markers on maps
    to remember: doors and where they lead, important NPCs, shops,
    Pokemon Centers, route connections, items, etc.

    Markers are organized by map_id so only relevant ones are shown.
    """

    def __init__(self, path: str = MARKERS_FILE):
        self.path = path
        # Structure: { "map_id": { "x_y": { "label": str, "type": str } } }
        self.data: Dict[str, Dict[str, Dict[str, str]]] = _load_json(path, {})

    def add(self, map_id: int, x: int, y: int, label: str,
            marker_type: str = "poi") -> str:
        """Add a marker to a map location."""
        map_key = str(map_id)
        pos_key = f"{x}_{y}"

        if map_key not in self.data:
            self.data[map_key] = {}

        self.data[map_key][pos_key] = {
            "label": label,
            "type": marker_type,
            "x": x,
            "y": y,
        }
        _save_json(self.path, self.data)
        return f"Marker added at ({x},{y}) on map {map_id}: {label}"

    def delete(self, map_id: int, x: int, y: int) -> str:
        """Delete a marker from a map location."""
        map_key = str(map_id)
        pos_key = f"{x}_{y}"

        if map_key in self.data and pos_key in self.data[map_key]:
            del self.data[map_key][pos_key]
            if not self.data[map_key]:
                del self.data[map_key]
            _save_json(self.path, self.data)
            return f"Marker deleted at ({x},{y}) on map {map_id}"
        return f"No marker at ({x},{y}) on map {map_id}"

    def get_for_map(self, map_id: int) -> Dict[str, Dict[str, str]]:
        """Get all markers for a specific map."""
        return self.data.get(str(map_id), {})

    def format_for_prompt(self, map_id: int) -> str:
        """Format markers for the current map for inclusion in prompt."""
        markers = self.get_for_map(map_id)
        if not markers:
            return "No markers on this map."
        lines = []
        for pos_key, info in markers.items():
            x, y = info.get("x", "?"), info.get("y", "?")
            label = info.get("label", "?")
            mtype = info.get("type", "poi")
            lines.append(f"- ({x},{y}) [{mtype}]: {label}")
        return "\n".join(lines)

    def count(self) -> int:
        return sum(len(m) for m in self.data.values())


# ── Objectives (quest log) ───────────────────────────────────────────────

class Objectives:
    """Quest log for the AI agent.

    Stolen from GPT FireRed harness. Tracks medium/long-term goals
    with rationale (WHY/HOW/WHAT). Not for micro-actions like
    "walk 3 tiles up" — those are just button presses.

    Each objective has:
    - description: what to do
    - rationale: why it matters
    - status: active/completed/abandoned
    """

    def __init__(self, path: str = OBJECTIVES_FILE):
        self.path = path
        # List of { "description": str, "rationale": str, "status": str }
        self.data: List[Dict[str, str]] = _load_json(path, [])

    def update(self, objectives: List[Dict[str, str]]) -> str:
        """Replace all objectives with a new list."""
        self.data = objectives
        _save_json(self.path, self.data)
        return f"Objectives updated: {len(objectives)} total"

    def add(self, description: str, rationale: str = "") -> str:
        """Add a new objective."""
        self.data.append({
            "description": description,
            "rationale": rationale,
            "status": "active",
            "added": time.strftime("%Y-%m-%d %H:%M"),
        })
        _save_json(self.path, self.data)
        return f"Objective added: {description}"

    def complete(self, index: int) -> str:
        """Mark an objective as completed."""
        if 0 <= index < len(self.data):
            self.data[index]["status"] = "completed"
            _save_json(self.path, self.data)
            return f"Objective completed: {self.data[index]['description']}"
        return f"Invalid objective index: {index}"

    def abandon(self, index: int) -> str:
        """Mark an objective as abandoned."""
        if 0 <= index < len(self.data):
            self.data[index]["status"] = "abandoned"
            _save_json(self.path, self.data)
            return f"Objective abandoned: {self.data[index]['description']}"
        return f"Invalid objective index: {index}"

    def active(self) -> List[Dict[str, str]]:
        """Get only active objectives."""
        return [o for o in self.data if o.get("status") == "active"]

    def format_for_prompt(self) -> str:
        """Format objectives for inclusion in the AI prompt."""
        active = self.active()
        if not active:
            return "No active objectives."
        lines = []
        for i, obj in enumerate(active):
            desc = obj.get("description", "?")
            rationale = obj.get("rationale", "")
            line = f"{i+1}. {desc}"
            if rationale:
                line += f" — WHY: {rationale}"
            lines.append(line)
        return "\n".join(lines)

    def count_active(self) -> int:
        return len(self.active())


# ── Action History (for context window management) ────────────────────────

class ActionHistory:
    """Recent action history for the AI agent.

    Keeps a rolling window of recent actions + results so the agent
    has short-term memory of what it just did. Prevents loops.

    Stolen from GPT FireRed harness history management.
    """

    def __init__(self, path: str = HISTORY_FILE, max_entries: int = 50):
        self.path = path
        self.max_entries = max_entries
        self.data: List[Dict[str, Any]] = _load_json(path, [])

    def add(self, action: Dict[str, Any], result: Dict[str, Any],
            position: Optional[Dict[str, Any]] = None) -> None:
        """Add an action to history."""
        entry = {
            "action": action,
            "result": result,
            "position": position,
            "timestamp": time.time(),
        }
        self.data.append(entry)
        # Trim to max
        if len(self.data) > self.max_entries:
            self.data = self.data[-self.max_entries:]
        _save_json(self.path, self.data)

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get the N most recent actions."""
        return self.data[-n:]

    def format_for_prompt(self, n: int = 10) -> str:
        """Format recent history for inclusion in prompt."""
        recent = self.recent(n)
        if not recent:
            return "No actions taken yet."
        lines = []
        for entry in recent:
            action = entry.get("action", {})
            pos = entry.get("position", {})
            atype = action.get("type", "?")
            buttons = action.get("buttons", [])
            pos_str = f"({pos.get('x','?')},{pos.get('y','?')})" if pos else ""
            if buttons:
                lines.append(f"- {atype}: {buttons} {pos_str}")
            else:
                lines.append(f"- {atype} {pos_str}")
        return "\n".join(lines)

    def detect_loop(self, window: int = 8) -> bool:
        """Detect if the agent is in a movement loop.

        Checks if the last `window` positions repeat a pattern.
        """
        if len(self.data) < window:
            return False
        recent_positions = []
        for entry in self.data[-window:]:
            pos = entry.get("position", {})
            if pos:
                recent_positions.append((pos.get("x"), pos.get("y")))
        if len(recent_positions) < window:
            return False
        # Check if positions cycle with period <= window/2
        half = window // 2
        first_half = recent_positions[:half]
        second_half = recent_positions[half:half*2]
        return first_half == second_half

    def count(self) -> int:
        return len(self.data)
