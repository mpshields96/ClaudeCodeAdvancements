"""Tests for movement validation — blocked direction tracking.

Mewtoo pattern: track failed movement per direction, mark blocked after 3 failures,
suggest perpendicular alternatives. Prevents the agent from repeatedly walking into walls.
"""
import unittest
from game_state import MapPosition
from movement_validator import MovementValidator


class TestMovementValidator(unittest.TestCase):
    """Core movement validation tests."""

    def setUp(self):
        self.mv = MovementValidator()

    # ── Basic tracking ──

    def test_no_failures_initially(self):
        """Fresh validator has no blocked directions."""
        pos = MapPosition(map_id=1, x=5, y=5)
        self.assertEqual(self.mv.get_blocked(pos), set())

    def test_single_failure_not_blocked(self):
        """One failure in a direction doesn't mark it blocked."""
        pos = MapPosition(map_id=1, x=5, y=5)
        self.mv.record_failure(pos, "up")
        self.assertNotIn("up", self.mv.get_blocked(pos))

    def test_two_failures_not_blocked(self):
        """Two failures still not blocked (threshold is 3)."""
        pos = MapPosition(map_id=1, x=5, y=5)
        self.mv.record_failure(pos, "up")
        self.mv.record_failure(pos, "up")
        self.assertNotIn("up", self.mv.get_blocked(pos))

    def test_three_failures_blocked(self):
        """Three failures in same direction marks it blocked."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        self.assertIn("up", self.mv.get_blocked(pos))

    def test_different_directions_tracked_independently(self):
        """Failures in different directions don't cross-contaminate."""
        pos = MapPosition(map_id=1, x=5, y=5)
        self.mv.record_failure(pos, "up")
        self.mv.record_failure(pos, "up")
        self.mv.record_failure(pos, "left")
        self.assertNotIn("up", self.mv.get_blocked(pos))
        self.assertNotIn("left", self.mv.get_blocked(pos))

    def test_different_positions_independent(self):
        """Failures at different positions are tracked independently."""
        pos1 = MapPosition(map_id=1, x=5, y=5)
        pos2 = MapPosition(map_id=1, x=6, y=5)
        for _ in range(3):
            self.mv.record_failure(pos1, "up")
        self.assertIn("up", self.mv.get_blocked(pos1))
        self.assertEqual(self.mv.get_blocked(pos2), set())

    def test_different_maps_independent(self):
        """Same coordinates on different maps are independent."""
        pos1 = MapPosition(map_id=1, x=5, y=5)
        pos2 = MapPosition(map_id=2, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos1, "up")
        self.assertIn("up", self.mv.get_blocked(pos1))
        self.assertEqual(self.mv.get_blocked(pos2), set())

    def test_multiple_directions_blocked(self):
        """Can block multiple directions at the same position."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
            self.mv.record_failure(pos, "left")
        blocked = self.mv.get_blocked(pos)
        self.assertIn("up", blocked)
        self.assertIn("left", blocked)
        self.assertNotIn("down", blocked)
        self.assertNotIn("right", blocked)

    # ── Success resets ──

    def test_success_resets_failure_count(self):
        """Successfully moving in a direction resets its failure count."""
        pos = MapPosition(map_id=1, x=5, y=5)
        self.mv.record_failure(pos, "up")
        self.mv.record_failure(pos, "up")
        self.mv.record_success(pos, "up")
        self.mv.record_failure(pos, "up")  # Only 1 failure now, not 3
        self.assertNotIn("up", self.mv.get_blocked(pos))

    def test_success_clears_blocked(self):
        """A success in a previously blocked direction unblocks it."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        self.assertIn("up", self.mv.get_blocked(pos))
        self.mv.record_success(pos, "up")
        self.assertNotIn("up", self.mv.get_blocked(pos))

    def test_success_doesnt_affect_other_directions(self):
        """Success in one direction doesn't clear other blocked directions."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
            self.mv.record_failure(pos, "left")
        self.mv.record_success(pos, "up")
        self.assertNotIn("up", self.mv.get_blocked(pos))
        self.assertIn("left", self.mv.get_blocked(pos))

    # ── Alternative suggestions ──

    def test_suggest_alternatives_perpendicular(self):
        """Blocked up -> suggests left, right as alternatives."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        alts = self.mv.suggest_alternatives(pos, "up")
        self.assertIn("left", alts)
        self.assertIn("right", alts)
        self.assertNotIn("up", alts)

    def test_suggest_alternatives_excludes_blocked(self):
        """Alternatives don't include other blocked directions."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
            self.mv.record_failure(pos, "left")
        alts = self.mv.suggest_alternatives(pos, "up")
        self.assertNotIn("up", alts)
        self.assertNotIn("left", alts)
        self.assertIn("right", alts)
        self.assertIn("down", alts)

    def test_suggest_alternatives_all_blocked(self):
        """If all directions blocked, return empty list."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for d in ("up", "down", "left", "right"):
            for _ in range(3):
                self.mv.record_failure(pos, d)
        alts = self.mv.suggest_alternatives(pos, "up")
        self.assertEqual(alts, [])

    def test_suggest_alternatives_unblocked_direction(self):
        """Suggesting alternatives for an unblocked direction returns all others."""
        pos = MapPosition(map_id=1, x=5, y=5)
        alts = self.mv.suggest_alternatives(pos, "up")
        self.assertEqual(sorted(alts), ["down", "left", "right"])

    # ── is_blocked convenience ──

    def test_is_blocked_single_direction(self):
        """is_blocked checks a specific direction at a position."""
        pos = MapPosition(map_id=1, x=5, y=5)
        self.assertFalse(self.mv.is_blocked(pos, "up"))
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        self.assertTrue(self.mv.is_blocked(pos, "up"))
        self.assertFalse(self.mv.is_blocked(pos, "down"))

    # ── Custom threshold ──

    def test_custom_threshold(self):
        """Can configure failure threshold."""
        mv = MovementValidator(failure_threshold=5)
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(4):
            mv.record_failure(pos, "up")
        self.assertNotIn("up", mv.get_blocked(pos))
        mv.record_failure(pos, "up")
        self.assertIn("up", mv.get_blocked(pos))

    # ── Clear / reset ──

    def test_clear_position(self):
        """Can clear all tracking data for a position."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        self.mv.clear_position(pos)
        self.assertEqual(self.mv.get_blocked(pos), set())

    def test_clear_all(self):
        """Can clear all tracking data."""
        pos1 = MapPosition(map_id=1, x=5, y=5)
        pos2 = MapPosition(map_id=1, x=6, y=5)
        for _ in range(3):
            self.mv.record_failure(pos1, "up")
            self.mv.record_failure(pos2, "down")
        self.mv.clear_all()
        self.assertEqual(self.mv.get_blocked(pos1), set())
        self.assertEqual(self.mv.get_blocked(pos2), set())

    # ── Map change auto-clear ──

    def test_on_map_change_clears_old_data(self):
        """Changing maps should clear position tracking (different tile layout)."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        self.mv.on_map_change(old_map=1, new_map=2)
        self.assertEqual(self.mv.get_blocked(pos), set())

    def test_on_map_change_same_map_noop(self):
        """on_map_change with same map ID is a no-op."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        self.mv.on_map_change(old_map=1, new_map=1)
        self.assertIn("up", self.mv.get_blocked(pos))

    # ── Stats / debugging ──

    def test_stats(self):
        """Stats returns tracked position count and total failures."""
        pos = MapPosition(map_id=1, x=5, y=5)
        self.mv.record_failure(pos, "up")
        self.mv.record_failure(pos, "up")
        self.mv.record_failure(pos, "left")
        stats = self.mv.stats()
        self.assertEqual(stats["positions_tracked"], 1)
        self.assertEqual(stats["total_failures"], 3)
        self.assertEqual(stats["blocked_directions"], 0)

    def test_stats_with_blocked(self):
        """Stats counts blocked directions."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        stats = self.mv.stats()
        self.assertEqual(stats["blocked_directions"], 1)

    # ── Integration with verify_movement ──

    def test_verify_movement_success(self):
        """verify_movement records success when position changes in pressed direction."""
        pos_before = MapPosition(map_id=1, x=5, y=5)
        pos_after = MapPosition(map_id=1, x=5, y=4)
        self.mv.verify_movement(pos_before, pos_after, "up")
        # Should not be blocked since movement succeeded
        self.assertFalse(self.mv.is_blocked(pos_before, "up"))

    def test_verify_movement_failure(self):
        """verify_movement records failure when position doesn't change."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.verify_movement(pos, pos, "up")
        self.assertTrue(self.mv.is_blocked(pos, "up"))

    def test_verify_movement_different_map(self):
        """verify_movement with map change counts as success (warp/transition)."""
        pos_before = MapPosition(map_id=1, x=5, y=5)
        pos_after = MapPosition(map_id=2, x=0, y=0)
        self.mv.verify_movement(pos_before, pos_after, "up")
        self.assertFalse(self.mv.is_blocked(pos_before, "up"))

    # ── Format for prompt ──

    def test_format_for_prompt_empty(self):
        """No blocked directions returns empty string."""
        pos = MapPosition(map_id=1, x=5, y=5)
        self.assertEqual(self.mv.format_for_prompt(pos), "")

    def test_format_for_prompt_blocked(self):
        """Blocked directions are formatted for LLM prompt inclusion."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        prompt = self.mv.format_for_prompt(pos)
        self.assertIn("BLOCKED", prompt)
        self.assertIn("up", prompt)

    def test_format_for_prompt_with_alternatives(self):
        """Format includes alternative directions."""
        pos = MapPosition(map_id=1, x=5, y=5)
        for _ in range(3):
            self.mv.record_failure(pos, "up")
        prompt = self.mv.format_for_prompt(pos)
        self.assertIn("left", prompt.lower())
        self.assertIn("right", prompt.lower())


if __name__ == "__main__":
    unittest.main()
