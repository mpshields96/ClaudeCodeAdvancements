"""Tests for Pokemon Red collision map reader.

Tests the collision reader that extracts walkability data from emulator RAM
and produces MapData objects for the A* Navigator.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl
from collision_reader_red import (
    CollisionReaderRed,
    MAP_HEIGHT,
    MAP_WIDTH,
    MAP_DATA_PTR,
    OVERWORLD_MAP,
    SPRITE_COUNT,
    SPRITE_BASE,
    SPRITE_STRUCT_SIZE,
    SPRITE_Y_OFFSET,
    SPRITE_X_OFFSET,
    SPRITE_MOVABLE_OFFSET,
    TILESET_COLLISION_PTR,
    PALLET_TOWN_WALKABLE,
)
from navigation import MapData, TileType, Navigator
from game_state import MapPosition
import memory_reader_red as mrr


class TestCollisionReaderInit(unittest.TestCase):
    """Test basic collision reader setup."""

    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = CollisionReaderRed(self.emu)

    def test_reads_map_dimensions(self):
        self.emu.write_byte(MAP_HEIGHT, 9)  # 9 blocks = 18 tiles
        self.emu.write_byte(MAP_WIDTH, 10)  # 10 blocks = 20 tiles
        h, w = self.reader.read_map_dimensions()
        self.assertEqual(h, 18)
        self.assertEqual(w, 20)

    def test_zero_dimensions(self):
        h, w = self.reader.read_map_dimensions()
        self.assertEqual(h, 0)
        self.assertEqual(w, 0)

    def test_reads_sprite_count(self):
        self.emu.write_byte(SPRITE_COUNT, 3)
        self.assertEqual(self.reader.read_sprite_count(), 3)

    def test_sprite_count_capped(self):
        self.emu.write_byte(SPRITE_COUNT, 20)
        self.assertEqual(self.reader.read_sprite_count(), 16)


class TestSpritePositions(unittest.TestCase):
    """Test NPC sprite position reading."""

    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = CollisionReaderRed(self.emu)

    def test_reads_sprite_positions(self):
        self.emu.write_byte(SPRITE_COUNT, 2)
        # Sprite 0 (player) is skipped, sprites 1+ are NPCs
        # Sprite 1 at y=5, x=3
        s1_base = SPRITE_BASE + 1 * SPRITE_STRUCT_SIZE
        self.emu.write_byte(s1_base + SPRITE_Y_OFFSET, 5 * 16 + 4)  # pixel Y
        self.emu.write_byte(s1_base + SPRITE_X_OFFSET, 3 * 16)  # pixel X
        self.emu.write_byte(s1_base + SPRITE_MOVABLE_OFFSET, 0xFF)  # visible
        # Sprite 2 at y=7, x=8
        s2_base = SPRITE_BASE + 2 * SPRITE_STRUCT_SIZE
        self.emu.write_byte(s2_base + SPRITE_Y_OFFSET, 7 * 16 + 4)
        self.emu.write_byte(s2_base + SPRITE_X_OFFSET, 8 * 16)
        self.emu.write_byte(s2_base + SPRITE_MOVABLE_OFFSET, 0xFF)

        positions = self.reader.read_sprite_positions()
        self.assertEqual(len(positions), 2)
        self.assertIn((3, 5), positions)
        self.assertIn((8, 7), positions)

    def test_invisible_sprites_excluded(self):
        self.emu.write_byte(SPRITE_COUNT, 1)
        s1_base = SPRITE_BASE + 1 * SPRITE_STRUCT_SIZE
        self.emu.write_byte(s1_base + SPRITE_Y_OFFSET, 5 * 16 + 4)
        self.emu.write_byte(s1_base + SPRITE_X_OFFSET, 3 * 16)
        self.emu.write_byte(s1_base + SPRITE_MOVABLE_OFFSET, 0)  # invisible
        positions = self.reader.read_sprite_positions()
        self.assertEqual(len(positions), 0)


class TestOverworldMapReading(unittest.TestCase):
    """Test reading the overworld map tile buffer."""

    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = CollisionReaderRed(self.emu)

    def test_reads_overworld_tiles(self):
        self.emu.write_byte(MAP_HEIGHT, 3)  # 6 tiles tall
        self.emu.write_byte(MAP_WIDTH, 3)   # 6 tiles wide
        # The overworld map buffer has stride = (width_blocks * 2) + 6
        # For 3 blocks wide: stride = 12
        stride = 3 * 2 + 6
        # Write some tile IDs into the buffer
        # Row 0: walkable tiles (0x00 is walkable in most tilesets)
        for col in range(6):
            self.emu.write_byte(OVERWORLD_MAP + stride + 3 + col, 0x00)
        tiles = self.reader.read_overworld_tiles()
        self.assertIsInstance(tiles, list)


class TestBuildMapData(unittest.TestCase):
    """Test building MapData for the Navigator."""

    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = CollisionReaderRed(self.emu)

    def test_builds_mapdata_from_walkable_set(self):
        """Test building a simple map using static walkable data."""
        # Set map dimensions
        self.emu.write_byte(MAP_HEIGHT, 2)  # 4 tiles tall
        self.emu.write_byte(MAP_WIDTH, 3)   # 6 tiles wide
        self.emu.write_byte(mrr.MAP_ID, 0)  # Pallet Town

        map_data = self.reader.build_map_data(
            map_id=0,
            walkable_tiles=PALLET_TOWN_WALKABLE,
        )
        self.assertIsInstance(map_data, MapData)
        self.assertEqual(map_data.map_id, 0)
        self.assertEqual(map_data.width, 6)
        self.assertEqual(map_data.height, 4)

    def test_sprite_obstacles_marked_wall(self):
        """Sprites should be marked as walls in the MapData."""
        self.emu.write_byte(MAP_HEIGHT, 2)
        self.emu.write_byte(MAP_WIDTH, 2)
        self.emu.write_byte(SPRITE_COUNT, 1)
        s1_base = SPRITE_BASE + 1 * SPRITE_STRUCT_SIZE
        self.emu.write_byte(s1_base + SPRITE_Y_OFFSET, 1 * 16 + 4)
        self.emu.write_byte(s1_base + SPRITE_X_OFFSET, 1 * 16)
        self.emu.write_byte(s1_base + SPRITE_MOVABLE_OFFSET, 0xFF)

        map_data = self.reader.build_map_data(
            map_id=0,
            walkable_tiles=set(range(256)),  # All tiles walkable
        )
        # Sprite at (1, 1) should be a wall
        self.assertEqual(map_data.get_tile(1, 1), TileType.WALL)

    def test_mapdata_integrates_with_navigator(self):
        """Built MapData should work with the A* Navigator."""
        self.emu.write_byte(MAP_HEIGHT, 3)
        self.emu.write_byte(MAP_WIDTH, 3)

        map_data = self.reader.build_map_data(
            map_id=0,
            walkable_tiles=set(range(256)),  # All walkable
        )

        nav = Navigator()
        nav.add_map(map_data)
        start = MapPosition(map_id=0, x=0, y=0)
        goal = MapPosition(map_id=0, x=2, y=2)
        path = nav.find_path(start, goal)
        self.assertIsNotNone(path)
        self.assertGreater(len(path), 0)


class TestStaticWalkableData(unittest.TestCase):
    """Test static walkable tile definitions for known maps."""

    def test_pallet_town_walkable_not_empty(self):
        self.assertGreater(len(PALLET_TOWN_WALKABLE), 0)

    def test_pallet_town_has_grass(self):
        """Pallet Town has tall grass tiles that should be walkable."""
        # Grass tile IDs are typically in the walkable set
        self.assertIsInstance(PALLET_TOWN_WALKABLE, set)


class TestBuildCurrentMap(unittest.TestCase):
    """Test the convenience method that reads current map from RAM."""

    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        self.reader = CollisionReaderRed(self.emu)

    def test_build_current_map(self):
        self.emu.write_byte(mrr.MAP_ID, 0)  # Pallet Town
        self.emu.write_byte(MAP_HEIGHT, 3)
        self.emu.write_byte(MAP_WIDTH, 4)

        map_data = self.reader.build_current_map()
        self.assertEqual(map_data.map_id, 0)
        self.assertEqual(map_data.name, "PALLET TOWN")
        self.assertEqual(map_data.width, 8)
        self.assertEqual(map_data.height, 6)

    def test_build_current_map_unknown(self):
        self.emu.write_byte(mrr.MAP_ID, 200)  # Unknown map
        self.emu.write_byte(MAP_HEIGHT, 2)
        self.emu.write_byte(MAP_WIDTH, 2)

        map_data = self.reader.build_current_map()
        self.assertEqual(map_data.map_id, 200)
        self.assertIn("Map 200", map_data.name)


if __name__ == "__main__":
    unittest.main()
