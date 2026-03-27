"""Movement validation — blocked direction tracking.

Mewtoo pattern: track failed movement per direction, mark blocked after N failures,
suggest perpendicular alternatives. Prevents the agent from repeatedly walking into walls.

Usage:
    from movement_validator import MovementValidator
    from game_state import MapPosition

    mv = MovementValidator()
    pos = MapPosition(map_id=1, x=5, y=5)
    mv.verify_movement(pos_before, pos_after, "up")  # auto-detect success/failure
    blocked = mv.get_blocked(pos)  # {"up"}
    alts = mv.suggest_alternatives(pos, "up")  # ["left", "right", "down"]

Stdlib only. No external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from game_state import MapPosition

ALL_DIRECTIONS = ("up", "down", "left", "right")
DEFAULT_FAILURE_THRESHOLD = 3


class MovementValidator:
    """Tracks failed movements per direction at each position.

    After `failure_threshold` consecutive failures in the same direction
    at the same position, that direction is marked blocked. A successful
    movement resets the counter and unblocks the direction.
    """

    def __init__(self, failure_threshold: int = DEFAULT_FAILURE_THRESHOLD):
        self.failure_threshold = failure_threshold
        # Key: (map_id, x, y, direction) -> failure count
        self._failures: Dict[Tuple[int, int, int, str], int] = {}

    def _key(self, pos: MapPosition, direction: str) -> Tuple[int, int, int, str]:
        return (pos.map_id, pos.x, pos.y, direction)

    def record_failure(self, pos: MapPosition, direction: str) -> None:
        """Record a failed movement attempt in the given direction."""
        key = self._key(pos, direction)
        self._failures[key] = self._failures.get(key, 0) + 1

    def record_success(self, pos: MapPosition, direction: str) -> None:
        """Record a successful movement, resetting the failure counter."""
        key = self._key(pos, direction)
        self._failures.pop(key, None)

    def is_blocked(self, pos: MapPosition, direction: str) -> bool:
        """Check if a direction is blocked at a position."""
        key = self._key(pos, direction)
        return self._failures.get(key, 0) >= self.failure_threshold

    def get_blocked(self, pos: MapPosition) -> Set[str]:
        """Get all blocked directions at a position."""
        blocked = set()
        for d in ALL_DIRECTIONS:
            if self.is_blocked(pos, d):
                blocked.add(d)
        return blocked

    def suggest_alternatives(self, pos: MapPosition, direction: str) -> List[str]:
        """Suggest alternative directions, excluding blocked ones."""
        blocked = self.get_blocked(pos)
        return [d for d in ALL_DIRECTIONS if d != direction and d not in blocked]

    def verify_movement(
        self, pos_before: MapPosition, pos_after: MapPosition, direction: str
    ) -> None:
        """Auto-detect success/failure based on position change.

        Map changes count as success (warp/transition).
        Same position = failure. Different position = success.
        """
        if pos_before.map_id != pos_after.map_id:
            self.record_success(pos_before, direction)
        elif pos_before.x == pos_after.x and pos_before.y == pos_after.y:
            self.record_failure(pos_before, direction)
        else:
            self.record_success(pos_before, direction)

    def clear_position(self, pos: MapPosition) -> None:
        """Clear all tracking data for a position."""
        keys_to_remove = [
            k for k in self._failures
            if k[0] == pos.map_id and k[1] == pos.x and k[2] == pos.y
        ]
        for k in keys_to_remove:
            del self._failures[k]

    def clear_all(self) -> None:
        """Clear all tracking data."""
        self._failures.clear()

    def on_map_change(self, old_map: int, new_map: int) -> None:
        """Clear tracking when changing maps (tiles may be different)."""
        if old_map == new_map:
            return
        keys_to_remove = [k for k in self._failures if k[0] == old_map]
        for k in keys_to_remove:
            del self._failures[k]

    def stats(self) -> dict:
        """Return tracking stats for debugging."""
        positions = set((k[0], k[1], k[2]) for k in self._failures)
        blocked_count = sum(
            1 for k, v in self._failures.items()
            if v >= self.failure_threshold
        )
        return {
            "positions_tracked": len(positions),
            "total_failures": sum(self._failures.values()),
            "blocked_directions": blocked_count,
        }

    def format_for_prompt(self, pos: MapPosition) -> str:
        """Format blocked directions for LLM prompt inclusion."""
        blocked = self.get_blocked(pos)
        if not blocked:
            return ""
        blocked_list = ", ".join(sorted(blocked))
        alts = self.suggest_alternatives(pos, list(blocked)[0])
        alt_list = ", ".join(sorted(alts)) if alts else "none"
        return (
            f"BLOCKED directions at ({pos.x},{pos.y}): {blocked_list}. "
            f"Try instead: {alt_list}."
        )
