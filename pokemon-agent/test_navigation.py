"""Tests for Pokemon Crystal navigation system.

Tests pathfinding, map transitions, and route planning.
Uses mock emulator backend — no ROM needed.
"""
import sys
import unittest

sys.path.insert(0, ".")

from navigation import (
    TileType,
    MapTile,
    MapData,
    Warp,
    Connection,
    Navigator,
    NavigationError,
    PathStep,
)
from game_state import MapPosition


class TestTileType(unittest.TestCase):
    """Test tile type classification."""

    def test_walkable_types(self):
        self.assertTrue(TileType.FLOOR.is_walkable())
        self.assertTrue(TileType.GRASS.is_walkable())
        self.assertTrue(TileType.DOOR.is_walkable())

    def test_unwalkable_types(self):
        self.assertFalse(TileType.WALL.is_walkable())
        self.assertFalse(TileType.WATER.is_walkable())
        self.assertFalse(TileType.LEDGE_DOWN.is_walkable())

    def test_surf_types(self):
        self.assertTrue(TileType.WATER.needs_surf())
        self.assertFalse(TileType.FLOOR.needs_surf())

    def test_encounter_types(self):
        self.assertTrue(TileType.GRASS.has_encounters())
        self.assertFalse(TileType.FLOOR.has_encounters())


class TestMapData(unittest.TestCase):
    """Test map data representation."""

    def setUp(self):
        """Create a simple 5x5 test map."""
        self.map_data = MapData(
            map_id=1,
            name="Test Town",
            width=5,
            height=5,
        )
        # Default all tiles walkable
        for y in range(5):
            for x in range(5):
                self.map_data.set_tile(x, y, TileType.FLOOR)
        # Add walls
        self.map_data.set_tile(2, 1, TileType.WALL)
        self.map_data.set_tile(2, 2, TileType.WALL)
        self.map_data.set_tile(2, 3, TileType.WALL)

    def test_tile_access(self):
        self.assertEqual(self.map_data.get_tile(0, 0), TileType.FLOOR)
        self.assertEqual(self.map_data.get_tile(2, 1), TileType.WALL)

    def test_out_of_bounds(self):
        self.assertEqual(self.map_data.get_tile(-1, 0), TileType.WALL)
        self.assertEqual(self.map_data.get_tile(5, 0), TileType.WALL)
        self.assertEqual(self.map_data.get_tile(0, 5), TileType.WALL)

    def test_is_walkable(self):
        self.assertTrue(self.map_data.is_walkable(0, 0))
        self.assertFalse(self.map_data.is_walkable(2, 2))
        self.assertFalse(self.map_data.is_walkable(-1, 0))

    def test_dimensions(self):
        self.assertEqual(self.map_data.width, 5)
        self.assertEqual(self.map_data.height, 5)

    def test_walkable_neighbors(self):
        """Neighbors of (1,2) should exclude wall at (2,2)."""
        neighbors = self.map_data.walkable_neighbors(1, 2)
        coords = [(n.x, n.y) for n in neighbors]
        self.assertIn((0, 2), coords)
        self.assertIn((1, 1), coords)
        self.assertIn((1, 3), coords)
        self.assertNotIn((2, 2), coords)


class TestWarp(unittest.TestCase):
    """Test warp (door/stair) data."""

    def test_warp_creation(self):
        warp = Warp(
            source_map=1, source_x=3, source_y=0,
            dest_map=2, dest_x=5, dest_y=9,
        )
        self.assertEqual(warp.source_map, 1)
        self.assertEqual(warp.dest_map, 2)

    def test_warp_matches_position(self):
        warp = Warp(source_map=1, source_x=3, source_y=0,
                    dest_map=2, dest_x=5, dest_y=9)
        self.assertTrue(warp.matches(1, 3, 0))
        self.assertFalse(warp.matches(1, 4, 0))
        self.assertFalse(warp.matches(2, 3, 0))


class TestConnection(unittest.TestCase):
    """Test map connections (north/south/east/west edges)."""

    def test_connection_creation(self):
        conn = Connection(
            direction="north",
            source_map=1,
            dest_map=3,
            offset=0,
        )
        self.assertEqual(conn.direction, "north")
        self.assertEqual(conn.dest_map, 3)


class TestPathfinding(unittest.TestCase):
    """Test A* pathfinding on a single map."""

    def setUp(self):
        """Create navigator with a simple map."""
        self.map_data = MapData(map_id=1, name="Test", width=8, height=8)
        for y in range(8):
            for x in range(8):
                self.map_data.set_tile(x, y, TileType.FLOOR)

        self.navigator = Navigator()
        self.navigator.add_map(self.map_data)

    def test_straight_path(self):
        """Path from (0,0) to (4,0) is a straight line."""
        path = self.navigator.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=4, y=0),
        )
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 4)  # 4 steps east
        self.assertTrue(all(s.direction == "right" for s in path))

    def test_path_around_wall(self):
        """Path must go around a vertical wall."""
        # Wall from (3,0) to (3,5)
        for y in range(6):
            self.map_data.set_tile(3, y, TileType.WALL)

        path = self.navigator.find_path(
            MapPosition(map_id=1, x=1, y=3),
            MapPosition(map_id=1, x=5, y=3),
        )
        self.assertIsNotNone(path)
        # Path must go around wall (through y=6 or y=7)
        self.assertTrue(len(path) > 4)  # Direct would be 4, must be longer

    def test_no_path_enclosed(self):
        """No path if destination is walled off."""
        # Enclose (6,6) completely
        for x in range(5, 8):
            self.map_data.set_tile(x, 5, TileType.WALL)
        for y in range(5, 8):
            self.map_data.set_tile(5, y, TileType.WALL)

        path = self.navigator.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=7, y=7),
        )
        self.assertIsNone(path)

    def test_already_at_destination(self):
        """Path from a position to itself is empty."""
        path = self.navigator.find_path(
            MapPosition(map_id=1, x=3, y=3),
            MapPosition(map_id=1, x=3, y=3),
        )
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 0)

    def test_path_steps_are_cardinal(self):
        """All path steps must be cardinal directions."""
        path = self.navigator.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=3, y=3),
        )
        self.assertIsNotNone(path)
        for step in path:
            self.assertIn(step.direction, ("up", "down", "left", "right"))

    def test_path_length_manhattan(self):
        """On open map, path length = Manhattan distance."""
        path = self.navigator.find_path(
            MapPosition(map_id=1, x=1, y=1),
            MapPosition(map_id=1, x=5, y=4),
        )
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 7)  # |5-1| + |4-1| = 7

    def test_grass_avoidance_preference(self):
        """Navigator should prefer non-grass tiles to avoid encounters."""
        # Row of grass at y=2
        for x in range(8):
            self.map_data.set_tile(x, 2, TileType.GRASS)

        path = self.navigator.find_path(
            MapPosition(map_id=1, x=3, y=0),
            MapPosition(map_id=1, x=3, y=4),
            avoid_encounters=True,
        )
        self.assertIsNotNone(path)
        # With avoidance, path might be longer but should still work
        # (Can't always avoid grass but should try)


class TestMultiMapNavigation(unittest.TestCase):
    """Test navigation between connected maps."""

    def setUp(self):
        """Create two connected maps."""
        self.map_a = MapData(map_id=1, name="Town A", width=5, height=5)
        self.map_b = MapData(map_id=2, name="Route 1", width=5, height=5)
        for m in (self.map_a, self.map_b):
            for y in range(5):
                for x in range(5):
                    m.set_tile(x, y, TileType.FLOOR)

        self.navigator = Navigator()
        self.navigator.add_map(self.map_a)
        self.navigator.add_map(self.map_b)

    def test_warp_navigation(self):
        """Navigate through a warp (door) between maps."""
        # Door at A(2,0) → B(2,4)
        self.navigator.add_warp(Warp(
            source_map=1, source_x=2, source_y=0,
            dest_map=2, dest_x=2, dest_y=4,
        ))
        self.navigator.add_warp(Warp(
            source_map=2, source_x=2, source_y=4,
            dest_map=1, dest_x=2, dest_y=0,
        ))

        path = self.navigator.find_path(
            MapPosition(map_id=1, x=2, y=2),
            MapPosition(map_id=2, x=2, y=2),
        )
        self.assertIsNotNone(path)
        # Should walk to warp, take warp, walk to destination
        has_warp_step = any(s.is_warp for s in path)
        self.assertTrue(has_warp_step)

    def test_connection_navigation(self):
        """Navigate through a map connection (edge transition)."""
        # A's north edge connects to B's south edge
        self.navigator.add_connection(Connection(
            direction="north", source_map=1, dest_map=2, offset=0,
        ))
        self.navigator.add_connection(Connection(
            direction="south", source_map=2, dest_map=1, offset=0,
        ))

        path = self.navigator.find_path(
            MapPosition(map_id=1, x=2, y=2),
            MapPosition(map_id=2, x=2, y=2),
        )
        self.assertIsNotNone(path)

    def test_no_path_disconnected_maps(self):
        """No path between maps with no connections or warps."""
        path = self.navigator.find_path(
            MapPosition(map_id=1, x=2, y=2),
            MapPosition(map_id=2, x=2, y=2),
        )
        self.assertIsNone(path)


class TestPathStep(unittest.TestCase):
    """Test path step representation."""

    def test_walk_step(self):
        step = PathStep(direction="right", map_id=1, x=3, y=2)
        self.assertEqual(step.direction, "right")
        self.assertFalse(step.is_warp)

    def test_warp_step(self):
        step = PathStep(direction="warp", map_id=2, x=5, y=9, is_warp=True)
        self.assertTrue(step.is_warp)

    def test_step_target_position(self):
        step = PathStep(direction="right", map_id=1, x=3, y=2)
        self.assertEqual(step.target_position(), MapPosition(map_id=1, x=3, y=2))


class TestNavigatorUtilities(unittest.TestCase):
    """Test navigator helper methods."""

    def setUp(self):
        self.map_data = MapData(map_id=1, name="Test", width=5, height=5)
        for y in range(5):
            for x in range(5):
                self.map_data.set_tile(x, y, TileType.FLOOR)
        self.navigator = Navigator()
        self.navigator.add_map(self.map_data)

    def test_directions_to_buttons(self):
        """Path directions should map to emulator buttons."""
        path = self.navigator.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=2, y=1),
        )
        buttons = [s.direction for s in path]
        self.assertTrue(all(b in ("up", "down", "left", "right", "warp") for b in buttons))

    def test_path_to_directions_list(self):
        """Convert path to a flat direction list for emulator input."""
        path = self.navigator.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=3, y=0),
        )
        dirs = Navigator.path_to_directions(path)
        self.assertEqual(dirs, ["right", "right", "right"])

    def test_manhattan_distance(self):
        self.assertEqual(Navigator.manhattan(0, 0, 3, 4), 7)
        self.assertEqual(Navigator.manhattan(2, 2, 2, 2), 0)

    def test_has_map(self):
        self.assertTrue(self.navigator.has_map(1))
        self.assertFalse(self.navigator.has_map(99))

    def test_get_map(self):
        m = self.navigator.get_map(1)
        self.assertIsNotNone(m)
        self.assertEqual(m.name, "Test")

    def test_get_missing_map(self):
        self.assertIsNone(self.navigator.get_map(99))


class TestEdgeCases(unittest.TestCase):
    """Edge cases and error handling."""

    def test_empty_navigator(self):
        nav = Navigator()
        path = nav.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=3, y=3),
        )
        self.assertIsNone(path)

    def test_start_on_wall(self):
        """If start position is on a wall, still try to find path (player is there)."""
        map_data = MapData(map_id=1, name="Test", width=5, height=5)
        for y in range(5):
            for x in range(5):
                map_data.set_tile(x, y, TileType.FLOOR)
        map_data.set_tile(0, 0, TileType.WALL)

        nav = Navigator()
        nav.add_map(map_data)
        # Player is at (0,0) which is "wall" but they're already there
        path = nav.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=3, y=3),
        )
        # Should still work — start is always walkable
        self.assertIsNotNone(path)

    def test_dest_on_wall(self):
        """If destination is on a wall, return None."""
        map_data = MapData(map_id=1, name="Test", width=5, height=5)
        for y in range(5):
            for x in range(5):
                map_data.set_tile(x, y, TileType.FLOOR)
        map_data.set_tile(4, 4, TileType.WALL)

        nav = Navigator()
        nav.add_map(map_data)
        path = nav.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=4, y=4),
        )
        self.assertIsNone(path)

    def test_1x1_map(self):
        """Tiny map — start = dest."""
        map_data = MapData(map_id=1, name="Tiny", width=1, height=1)
        map_data.set_tile(0, 0, TileType.FLOOR)
        nav = Navigator()
        nav.add_map(map_data)
        path = nav.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=0, y=0),
        )
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 0)

    def test_large_map_performance(self):
        """50x50 map should still pathfind quickly."""
        import time
        map_data = MapData(map_id=1, name="Large", width=50, height=50)
        for y in range(50):
            for x in range(50):
                map_data.set_tile(x, y, TileType.FLOOR)

        nav = Navigator()
        nav.add_map(map_data)

        start = time.time()
        path = nav.find_path(
            MapPosition(map_id=1, x=0, y=0),
            MapPosition(map_id=1, x=49, y=49),
        )
        elapsed = time.time() - start

        self.assertIsNotNone(path)
        self.assertEqual(len(path), 98)  # Manhattan distance
        self.assertLess(elapsed, 1.0)  # Should be well under 1 second


if __name__ == "__main__":
    unittest.main()
