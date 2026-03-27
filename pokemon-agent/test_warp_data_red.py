"""Tests for Pokemon Red warp data — static tables and RAM reader.

Tests the warp/connection data that enables cross-map A* pathfinding.
Covers: static warp table lookup, RAM warp reading, connection tables,
and integration with Navigator.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from emulator_control import EmulatorControl
from navigation import Navigator, MapData, TileType, Warp, Connection
from game_state import MapPosition


# ── Static warp table tests ──────────────────────────────────────────────────

class TestStaticWarpTable(unittest.TestCase):
    """Test the hardcoded warp definitions for early-game maps."""

    def setUp(self):
        from warp_data_red import WARP_TABLE, CONNECTION_TABLE
        self.warps = WARP_TABLE
        self.connections = CONNECTION_TABLE

    def test_warp_table_not_empty(self):
        self.assertGreater(len(self.warps), 0)

    def test_pallet_town_has_warps(self):
        """Pallet Town should have door warps to Red's House, Blue's House, Oak's Lab."""
        pallet_warps = [w for w in self.warps if w.source_map == 0]
        self.assertGreaterEqual(len(pallet_warps), 3, "Pallet Town needs at least 3 warps")

    def test_reds_house_1f_exits_to_pallet(self):
        """Red's House 1F door should warp back to Pallet Town."""
        reds_house_warps = [w for w in self.warps if w.source_map == 37]
        pallet_exits = [w for w in reds_house_warps if w.dest_map == 0]
        self.assertGreaterEqual(len(pallet_exits), 1)

    def test_reds_house_stairs(self):
        """Red's House 1F should have stairs to 2F and vice versa."""
        to_2f = [w for w in self.warps if w.source_map == 37 and w.dest_map == 38]
        to_1f = [w for w in self.warps if w.source_map == 38 and w.dest_map == 37]
        self.assertGreaterEqual(len(to_2f), 1, "Need stairs from 1F to 2F")
        self.assertGreaterEqual(len(to_1f), 1, "Need stairs from 2F to 1F")

    def test_oaks_lab_exits_to_pallet(self):
        """Oak's Lab should exit back to Pallet Town."""
        lab_warps = [w for w in self.warps if w.source_map == 40 and w.dest_map == 0]
        self.assertGreaterEqual(len(lab_warps), 1)

    def test_warps_are_bidirectional(self):
        """For every warp A->B, there should be a return warp B->A."""
        pairs = set()
        for w in self.warps:
            pairs.add((w.source_map, w.dest_map))
        for w in self.warps:
            reverse = (w.dest_map, w.source_map)
            self.assertIn(reverse, pairs,
                          f"Warp {w.source_map}->{w.dest_map} has no return warp")

    def test_warp_coordinates_non_negative(self):
        for w in self.warps:
            self.assertGreaterEqual(w.source_x, 0)
            self.assertGreaterEqual(w.source_y, 0)
            self.assertGreaterEqual(w.dest_x, 0)
            self.assertGreaterEqual(w.dest_y, 0)

    def test_warp_objects_match_navigation_type(self):
        """Warps should be navigation.Warp instances."""
        for w in self.warps:
            self.assertIsInstance(w, Warp)


class TestStaticConnectionTable(unittest.TestCase):
    """Test map edge connections for early-game routes."""

    def setUp(self):
        from warp_data_red import CONNECTION_TABLE
        self.connections = CONNECTION_TABLE

    def test_connection_table_not_empty(self):
        self.assertGreater(len(self.connections), 0)

    def test_pallet_connects_north_to_route_1(self):
        """Pallet Town north edge should connect to Route 1."""
        pallet_north = [c for c in self.connections
                        if c.source_map == 0 and c.direction == "north"]
        self.assertEqual(len(pallet_north), 1)
        self.assertEqual(pallet_north[0].dest_map, 12)  # Route 1

    def test_route_1_connects_south_to_pallet(self):
        """Route 1 south edge should connect back to Pallet Town."""
        r1_south = [c for c in self.connections
                    if c.source_map == 12 and c.direction == "south"]
        self.assertEqual(len(r1_south), 1)
        self.assertEqual(r1_south[0].dest_map, 0)  # Pallet Town

    def test_route_1_connects_north_to_viridian(self):
        """Route 1 north should connect to Viridian City."""
        r1_north = [c for c in self.connections
                    if c.source_map == 12 and c.direction == "north"]
        self.assertEqual(len(r1_north), 1)
        self.assertEqual(r1_north[0].dest_map, 1)  # Viridian City

    def test_connections_are_navigation_type(self):
        for c in self.connections:
            self.assertIsInstance(c, Connection)

    def test_connections_have_valid_directions(self):
        valid = {"north", "south", "east", "west"}
        for c in self.connections:
            self.assertIn(c.direction, valid)


# ── RAM warp reader tests ───────────────────────────────────────────────────

class TestRAMWarpReader(unittest.TestCase):
    """Test reading warp data from emulator RAM."""

    def setUp(self):
        self.emu = EmulatorControl.mock(ram_size=0x10000)
        from warp_data_red import WarpReaderRed, WARP_COUNT_ADDR, WARP_DATA_ADDR
        self.reader = WarpReaderRed(self.emu)
        self.WARP_COUNT = WARP_COUNT_ADDR
        self.WARP_DATA = WARP_DATA_ADDR

    def test_reads_zero_warps(self):
        self.emu.write_byte(self.WARP_COUNT, 0)
        warps = self.reader.read_warp_positions()
        self.assertEqual(len(warps), 0)

    def test_reads_warp_positions(self):
        """Read source positions of warps on current map."""
        self.emu.write_byte(self.WARP_COUNT, 2)
        # Warp 0: src_y=5, src_x=3, dest_warp=0, dest_map=37
        self.emu.write_byte(self.WARP_DATA + 0, 5)   # src_y
        self.emu.write_byte(self.WARP_DATA + 1, 3)   # src_x
        self.emu.write_byte(self.WARP_DATA + 2, 0)   # dest_warp_id
        self.emu.write_byte(self.WARP_DATA + 3, 37)  # dest_map
        # Warp 1: src_y=5, src_x=13, dest_warp=0, dest_map=39
        self.emu.write_byte(self.WARP_DATA + 4, 5)
        self.emu.write_byte(self.WARP_DATA + 5, 13)
        self.emu.write_byte(self.WARP_DATA + 6, 0)
        self.emu.write_byte(self.WARP_DATA + 7, 39)

        positions = self.reader.read_warp_positions()
        self.assertEqual(len(positions), 2)
        self.assertEqual(positions[0], (3, 5))   # (x, y)
        self.assertEqual(positions[1], (13, 5))

    def test_reads_warp_destinations(self):
        """Read full warp data including destination map and warp ID."""
        self.emu.write_byte(self.WARP_COUNT, 1)
        self.emu.write_byte(self.WARP_DATA + 0, 5)   # src_y
        self.emu.write_byte(self.WARP_DATA + 1, 3)   # src_x
        self.emu.write_byte(self.WARP_DATA + 2, 0)   # dest_warp_id
        self.emu.write_byte(self.WARP_DATA + 3, 37)  # dest_map

        entries = self.reader.read_warp_entries()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["src_x"], 3)
        self.assertEqual(entry["src_y"], 5)
        self.assertEqual(entry["dest_map"], 37)
        self.assertEqual(entry["dest_warp_id"], 0)

    def test_warp_count_capped(self):
        """Warp count should be capped to prevent OOB reads."""
        self.emu.write_byte(self.WARP_COUNT, 100)
        positions = self.reader.read_warp_positions()
        self.assertLessEqual(len(positions), 32)


# ── Integration: warps + navigator ──────────────────────────────────────────

class TestWarpNavigatorIntegration(unittest.TestCase):
    """Test that static warps enable cross-map A* pathfinding."""

    def test_cross_map_path_through_warp(self):
        """Navigator should find a path from Pallet Town into Red's House."""
        from warp_data_red import WARP_TABLE

        nav = Navigator()

        # Pallet Town: 20x18 tiles, all walkable
        pallet = MapData(map_id=0, name="Pallet Town", width=20, height=18)
        for y in range(18):
            for x in range(20):
                pallet.set_tile(x, y, TileType.FLOOR)
        nav.add_map(pallet)

        # Red's House 1F: 8x8 tiles, all walkable
        reds_house = MapData(map_id=37, name="Red's House 1F", width=8, height=8)
        for y in range(8):
            for x in range(8):
                reds_house.set_tile(x, y, TileType.FLOOR)
        nav.add_map(reds_house)

        # Add warps between Pallet Town and Red's House
        pallet_to_reds = [w for w in WARP_TABLE
                          if w.source_map == 0 and w.dest_map == 37]
        reds_to_pallet = [w for w in WARP_TABLE
                          if w.source_map == 37 and w.dest_map == 0]
        for w in pallet_to_reds + reds_to_pallet:
            nav.add_warp(w)

        # Should find a path from somewhere in Pallet to inside Red's House
        if pallet_to_reds:
            warp = pallet_to_reds[0]
            start = MapPosition(map_id=0, x=warp.source_x, y=max(0, warp.source_y - 1))
            goal = MapPosition(map_id=37, x=warp.dest_x, y=min(7, warp.dest_y + 1))
            path = nav.find_path(start, goal)
            self.assertIsNotNone(path, "Should find cross-map path through warp")
            # Path should include a warp step
            warp_steps = [s for s in path if s.is_warp]
            self.assertGreaterEqual(len(warp_steps), 1, "Path should use a warp")

    def test_cross_map_path_through_connection(self):
        """Navigator should find a path from Pallet Town to Route 1 via north edge."""
        from warp_data_red import CONNECTION_TABLE

        nav = Navigator()

        # Pallet Town: 20x18
        pallet = MapData(map_id=0, name="Pallet Town", width=20, height=18)
        for y in range(18):
            for x in range(20):
                pallet.set_tile(x, y, TileType.FLOOR)
        nav.add_map(pallet)

        # Route 1: 20x36
        route1 = MapData(map_id=12, name="Route 1", width=20, height=36)
        for y in range(36):
            for x in range(20):
                route1.set_tile(x, y, TileType.FLOOR)
        nav.add_map(route1)

        # Add connections
        pallet_north = [c for c in CONNECTION_TABLE
                        if c.source_map == 0 and c.direction == "north"]
        r1_south = [c for c in CONNECTION_TABLE
                    if c.source_map == 12 and c.direction == "south"]
        for c in pallet_north + r1_south:
            nav.add_connection(c)

        # Walk from middle of Pallet to north edge → should cross to Route 1
        start = MapPosition(map_id=0, x=10, y=2)
        goal = MapPosition(map_id=12, x=10, y=34)
        path = nav.find_path(start, goal)
        self.assertIsNotNone(path, "Should find path from Pallet to Route 1")


class TestGetWarpsForMap(unittest.TestCase):
    """Test the helper that filters warps by source map."""

    def test_get_warps_for_pallet(self):
        from warp_data_red import get_warps_for_map
        warps = get_warps_for_map(0)
        self.assertGreaterEqual(len(warps), 3)
        for w in warps:
            self.assertEqual(w.source_map, 0)

    def test_get_warps_for_unknown_map(self):
        from warp_data_red import get_warps_for_map
        warps = get_warps_for_map(255)
        self.assertEqual(len(warps), 0)

    def test_get_connections_for_map(self):
        from warp_data_red import get_connections_for_map
        conns = get_connections_for_map(0)
        self.assertGreaterEqual(len(conns), 1)
        for c in conns:
            self.assertEqual(c.source_map, 0)


if __name__ == "__main__":
    unittest.main()
