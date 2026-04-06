"""Tests for collision_reader_crystal.py — Crystal walkability data.

Run: python3 -m unittest pokemon-agent.test_collision_reader_crystal
"""
from __future__ import annotations

import unittest
from navigation import TileType
from warp_data_crystal import (
    MAP_PLAYERS_HOUSE_2F,
    MAP_PLAYERS_HOUSE_1F,
    MAP_NEW_BARK_TOWN,
    MAP_ELMS_LAB,
    WARP_TABLE,
    MAP_DIMENSIONS,
)
from collision_reader_crystal import (
    build_collision_map,
    build_intro_navigator_with_collision,
    get_walkable_directions,
    get_all_walkable_tiles,
    get_tile_type,
    _STATIC_GRIDS,
)


class TestStaticGridIntegrity(unittest.TestCase):
    """Verify static grids have correct dimensions and type consistency."""

    def test_all_intro_maps_have_grids(self):
        for map_id in [MAP_PLAYERS_HOUSE_2F, MAP_PLAYERS_HOUSE_1F,
                       MAP_NEW_BARK_TOWN, MAP_ELMS_LAB]:
            self.assertIn(map_id, _STATIC_GRIDS, f"Missing grid for map {map_id}")

    def test_grid_dimensions_match_map_dimensions(self):
        for map_id, grid in _STATIC_GRIDS.items():
            expected_w, expected_h = MAP_DIMENSIONS[map_id]
            self.assertEqual(len(grid), expected_h,
                             f"map {map_id}: height {len(grid)} != {expected_h}")
            for y, row in enumerate(grid):
                self.assertEqual(len(row), expected_w,
                                 f"map {map_id} row {y}: width {len(row)} != {expected_w}")

    def test_all_cells_are_tiletype(self):
        for map_id, grid in _STATIC_GRIDS.items():
            for y, row in enumerate(grid):
                for x, cell in enumerate(row):
                    self.assertIsInstance(cell, TileType,
                                         f"map {map_id} ({x},{y}): {cell!r} not TileType")

    def test_boundaries_are_walls_or_doors(self):
        """All 4 intro maps should have no walkable tiles on the outer edge
        except for warp/door tiles."""
        warp_positions = {}
        for warp in WARP_TABLE:
            warp_positions.setdefault(warp.source_map, set()).add(
                (warp.source_x, warp.source_y)
            )

        for map_id, grid in _STATIC_GRIDS.items():
            h = len(grid)
            w = len(grid[0])
            warps = warp_positions.get(map_id, set())

            for x in range(w):
                for y in [0, h - 1]:
                    tile = grid[y][x]
                    if (x, y) not in warps:
                        self.assertFalse(
                            tile.is_walkable() and tile != TileType.DOOR,
                            f"map {map_id} boundary ({x},{y}) should be wall, got {tile}"
                        )
            for y in range(h):
                for x in [0, w - 1]:
                    tile = grid[y][x]
                    if (x, y) not in warps:
                        self.assertFalse(
                            tile.is_walkable() and tile != TileType.DOOR,
                            f"map {map_id} boundary ({x},{y}) should be wall, got {tile}"
                        )

    def test_has_walkable_interior_tiles(self):
        """Every map must have at least some walkable tiles (sanity check)."""
        for map_id in _STATIC_GRIDS:
            walkable = get_all_walkable_tiles(map_id)
            self.assertGreater(len(walkable), 0,
                               f"map {map_id} has no walkable tiles")


class TestWarpTilesAreDoors(unittest.TestCase):
    """Warp source positions must be walkable (DOOR type) in every map."""

    def test_all_warp_tiles_are_walkable(self):
        for warp in WARP_TABLE:
            map_id = warp.source_map
            grid = _STATIC_GRIDS.get(map_id)
            if grid is None:
                continue
            w = len(grid[0])
            h = len(grid)
            self.assertTrue(0 <= warp.source_x < w and 0 <= warp.source_y < h,
                            f"Warp ({warp.source_x},{warp.source_y}) OOB on map {map_id}")
            tile = grid[warp.source_y][warp.source_x]
            self.assertTrue(tile.is_walkable(),
                            f"Warp at ({warp.source_x},{warp.source_y}) on map {map_id} "
                            f"is not walkable: {tile}")


class TestBuildCollisionMap(unittest.TestCase):

    def test_returns_none_for_unknown_map(self):
        self.assertIsNone(build_collision_map(9999))

    def test_returns_map_data_for_intro_maps(self):
        for map_id in [MAP_PLAYERS_HOUSE_2F, MAP_PLAYERS_HOUSE_1F,
                       MAP_NEW_BARK_TOWN, MAP_ELMS_LAB]:
            result = build_collision_map(map_id)
            self.assertIsNotNone(result, f"build_collision_map({map_id}) returned None")
            self.assertEqual(result.map_id, map_id)

    def test_map_data_dimensions_correct(self):
        for map_id, (exp_w, exp_h) in MAP_DIMENSIONS.items():
            if map_id not in _STATIC_GRIDS:
                continue
            md = build_collision_map(map_id)
            self.assertEqual(md.width, exp_w)
            self.assertEqual(md.height, exp_h)

    def test_warp_tiles_marked_as_door(self):
        for warp in WARP_TABLE:
            md = build_collision_map(warp.source_map)
            if md is None:
                continue
            tile = md.get_tile(warp.source_x, warp.source_y)
            self.assertEqual(tile, TileType.DOOR,
                             f"Expected DOOR at ({warp.source_x},{warp.source_y}) "
                             f"on map {warp.source_map}, got {tile}")


class TestGetWalkableDirections(unittest.TestCase):

    def test_centre_of_new_bark_all_directions(self):
        # Centre of New Bark Town should have all 4 directions walkable
        dirs = get_walkable_directions(MAP_NEW_BARK_TOWN, 10, 9)
        self.assertTrue(any(dirs.values()), "At least one direction should be walkable")

    def test_wall_position_blocks_toward_boundary(self):
        # From (1,1) in Player House 2F: can't go up (y=0 is wall) or left (x=0 is wall)
        dirs = get_walkable_directions(MAP_PLAYERS_HOUSE_2F, 1, 1)
        self.assertFalse(dirs["up"], "Should not be able to walk up into top wall")
        self.assertFalse(dirs["left"], "Should not be able to walk left into left wall")

    def test_warp_tile_is_reachable(self):
        # Stairs in House 2F at (7,0) — standing at (7,1) should be able to walk up
        dirs = get_walkable_directions(MAP_PLAYERS_HOUSE_2F, 7, 1)
        self.assertTrue(dirs["up"], "Should be able to walk up to stair warp tile")

    def test_unknown_map_returns_false(self):
        dirs = get_walkable_directions(9999, 5, 5)
        self.assertFalse(all(dirs.values()), "Unknown map should not report all walkable")

    def test_out_of_bounds_position_not_walkable(self):
        # Standing at edge, trying to walk out of bounds
        dirs = get_walkable_directions(MAP_PLAYERS_HOUSE_2F, 0, 0)
        self.assertFalse(dirs["up"])
        self.assertFalse(dirs["left"])


class TestGetAllWalkableTiles(unittest.TestCase):

    def test_returns_empty_for_unknown_map(self):
        self.assertEqual(get_all_walkable_tiles(9999), set())

    def test_all_maps_return_nonempty_sets(self):
        for map_id in _STATIC_GRIDS:
            tiles = get_all_walkable_tiles(map_id)
            self.assertGreater(len(tiles), 0)

    def test_warp_positions_in_walkable_set(self):
        for warp in WARP_TABLE:
            if warp.source_map not in _STATIC_GRIDS:
                continue
            tiles = get_all_walkable_tiles(warp.source_map)
            self.assertIn((warp.source_x, warp.source_y), tiles,
                          f"Warp ({warp.source_x},{warp.source_y}) not in walkable tiles "
                          f"for map {warp.source_map}")

    def test_boundary_tiles_not_in_walkable_set(self):
        # Corner tiles (0,0) are walls and should not be walkable
        for map_id in _STATIC_GRIDS:
            tiles = get_all_walkable_tiles(map_id)
            self.assertNotIn((0, 0), tiles,
                             f"map {map_id}: (0,0) corner should be wall")


class TestGetTileType(unittest.TestCase):

    def test_returns_none_for_unknown_map(self):
        self.assertIsNone(get_tile_type(9999, 1, 1))

    def test_returns_none_for_oob_coordinates(self):
        self.assertIsNone(get_tile_type(MAP_PLAYERS_HOUSE_2F, 100, 100))

    def test_corner_is_wall(self):
        result = get_tile_type(MAP_PLAYERS_HOUSE_2F, 0, 0)
        self.assertEqual(result, TileType.WALL)

    def test_stair_is_door(self):
        # Stairs at (7,0) in Player's House 2F
        result = get_tile_type(MAP_PLAYERS_HOUSE_2F, 7, 0)
        self.assertEqual(result, TileType.DOOR)

    def test_elm_lab_exit_is_door(self):
        # Elm's Lab exit at (5,7) and (6,7)
        self.assertEqual(get_tile_type(MAP_ELMS_LAB, 5, 7), TileType.DOOR)
        self.assertEqual(get_tile_type(MAP_ELMS_LAB, 6, 7), TileType.DOOR)


class TestBuildIntroNavigatorWithCollision(unittest.TestCase):

    def test_navigator_loads_all_intro_maps(self):
        nav = build_intro_navigator_with_collision()
        for map_id in _STATIC_GRIDS:
            # Navigator should have the map loaded (no KeyError)
            md = nav._maps.get(map_id)
            self.assertIsNotNone(md, f"Navigator missing map {map_id}")

    def test_navigator_finds_path_in_house_2f(self):
        from game_state import MapPosition
        nav = build_intro_navigator_with_collision()
        # Path from interior to near the stairs tile should succeed
        start = MapPosition(map_id=MAP_PLAYERS_HOUSE_2F, x=5, y=4)
        goal = MapPosition(map_id=MAP_PLAYERS_HOUSE_2F, x=7, y=1)
        path = nav.find_path(start=start, goal=goal)
        self.assertIsNotNone(path, "Navigator should find path to near stairs")

    def test_navigator_has_warps_loaded(self):
        nav = build_intro_navigator_with_collision()
        self.assertGreater(len(nav._warps), 0, "Navigator should have warps loaded")


if __name__ == "__main__":
    unittest.main()
