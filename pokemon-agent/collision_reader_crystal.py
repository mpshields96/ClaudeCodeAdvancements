"""Pokemon Crystal collision map reader — walkability data for intro maps.

Provides accurate tile-level walkability for the 4 intro maps (New Bark Town
area) using static collision grids sourced from pret/pokecrystal map data,
plus a runtime RAM-based fallback for maps outside the static set.

Static grids supersede the all-FLOOR approximation in warp_data_crystal.py,
enabling the navigator to route around interior walls (beds, counters, tables).

Crystal map coordinates use 2x2-tile blocks. Dimensions come from .blk files:
  PlayerHouse2F : 5 blocks x 4 tall  = 10 tiles x  8 tiles
  PlayerHouse1F : 6 blocks x 4 tall  = 12 tiles x  8 tiles
  NewBarkTown   : 10 blocks x 9 tall = 20 tiles x 18 tiles
  ElmsLab       : 6 blocks x 4 tall  = 12 tiles x  8 tiles

RAM addresses for runtime fallback from pret/pokecrystal wram.asm:
  0xDCB7 wPlayerY        — player Y tile position
  0xDCB8 wPlayerX        — player X tile position
  0xDCB5 wCurMapGroup    — current map group
  0xDCB6 wCurMapNumber   — current map number
  0xD6E0 wCurMapHeight   — map height in blocks (multiply x2 for tiles)
  0xD6E1 wCurMapWidth    — map width in blocks (multiply x2 for tiles)

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from navigation import MapData, TileType
from warp_data_crystal import (
    MAP_PLAYERS_HOUSE_2F,
    MAP_PLAYERS_HOUSE_1F,
    MAP_NEW_BARK_TOWN,
    MAP_ELMS_LAB,
    MAP_DIMENSIONS,
    MAP_NAMES,
    WARP_TABLE,
    crystal_map_id,
)

# ── Crystal RAM addresses ────────────────────────────────────────────────────
# Source: pret/pokecrystal wram.asm (verified against known player position reads)

PLAYER_Y        = 0xDCB7
PLAYER_X        = 0xDCB8
MAP_GROUP_ADDR  = 0xDCB5
MAP_NUM_ADDR    = 0xDCB6
CUR_MAP_HEIGHT  = 0xD6E0   # height in 2-tile blocks
CUR_MAP_WIDTH   = 0xD6E1   # width in 2-tile blocks

# ── Static collision grids ───────────────────────────────────────────────────
# W = wall (impassable), F = floor (walkable), D = door/warp, G = grass

# Legend shorthand
W = TileType.WALL
F = TileType.FLOOR
D = TileType.DOOR
G = TileType.GRASS

# Player's House 2F — 10 tiles wide x 8 tiles tall
# Small upstairs bedroom. Bed at top-left area, stairs at col 7 row 0.
# Source: pret/pokecrystal maps/NewBark/PlayerHouse2F.blk visual inspection.
_HOUSE_2F_GRID = [
    # x: 0  1  2  3  4  5  6  7  8  9
    [    W, W, W, W, W, W, W, D, W, W ],  # y=0  (stairs at 7,0)
    [    W, F, F, F, F, F, F, F, F, W ],  # y=1
    [    W, W, W, F, F, F, F, F, F, W ],  # y=2  (bed/furniture left side)
    [    W, W, W, F, F, F, F, F, F, W ],  # y=3
    [    W, F, F, F, F, F, F, F, F, W ],  # y=4
    [    W, F, F, F, F, F, F, F, F, W ],  # y=5
    [    W, F, F, F, F, F, F, F, F, W ],  # y=6
    [    W, W, W, W, W, W, W, W, W, W ],  # y=7
]

# Player's House 1F — 12 tiles wide x 8 tiles tall
# Ground floor. Stairs at col 9 row 0. Door exit at south (cols 5-6 row 7).
# TV/furniture on the right side, PC on left.
_HOUSE_1F_GRID = [
    # x: 0  1  2  3  4  5  6  7  8  9 10 11
    [    W, W, W, W, W, W, W, W, W, D, W, W ],  # y=0  (stairs at 9,0)
    [    W, F, F, F, F, F, F, F, F, F, W, W ],  # y=1
    [    W, W, F, F, F, F, F, F, F, F, W, W ],  # y=2  (furniture left)
    [    W, W, F, F, F, F, F, F, F, W, W, W ],  # y=3  (table right)
    [    W, F, F, F, F, F, F, F, F, F, F, W ],  # y=4
    [    W, F, F, F, F, F, F, F, F, F, F, W ],  # y=5
    [    W, F, F, F, F, F, F, F, F, F, F, W ],  # y=6
    [    W, W, W, W, W, W, D, D, W, W, W, W ],  # y=7  (door at 6,7 and 7,7)
]

# New Bark Town — 20 tiles wide x 18 tiles tall
# Outdoor area. Buildings block certain tiles. Grass patches.
# Player house at top-left area, Elm's Lab in centre-right.
# Source: visual map from pokecrystal/maps/NewBark/NewBarkTown.blk
_NEW_BARK_GRID = [
    # x:  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19
    [     W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W ],  # y=0
    [     W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=1
    [     W, F, W, W, W, W, F, F, F, F, F, F, F, W, W, W, W, F, F, W ],  # y=2 (house roofs)
    [     W, F, W, W, W, W, F, F, F, F, F, F, F, W, W, W, W, F, F, W ],  # y=3
    [     W, F, W, W, W, W, F, F, F, F, F, F, F, W, W, W, W, F, F, W ],  # y=4
    [     W, F, D, F, F, D, F, F, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=5 (house exits, player house door at 2,5; neighbour at 5,5)
    [     W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=6
    [     W, G, G, G, G, G, G, G, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=7 (grass left side)
    [     W, G, G, G, G, G, G, G, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=8
    [     W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W, W, W, F, W ],  # y=9  (Elm's Lab roof top)
    [     W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W, W, W, F, W ],  # y=10
    [     W, F, F, F, F, F, F, F, F, F, F, D, D, F, F, W, W, W, F, W ],  # y=11 (Elm's lab door at 11,11 and 12,11)
    [     W, G, G, G, G, G, G, G, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=12
    [     W, G, G, G, G, G, G, G, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=13
    [     W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=14
    [     W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=15
    [     W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W ],  # y=16
    [     W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W ],  # y=17
]

# Elm's Lab — 12 tiles wide x 8 tiles tall
# Interior lab with counters/tables. Exit door at bottom (cols 5-6 row 7).
# Pokeballs on counters, PC, lab equipment block movement.
_ELMS_LAB_GRID = [
    # x: 0  1  2  3  4  5  6  7  8  9 10 11
    [    W, W, W, W, W, W, W, W, W, W, W, W ],  # y=0
    [    W, W, W, F, F, F, F, F, F, W, W, W ],  # y=1 (counter/bench top)
    [    W, W, W, F, F, F, F, F, F, W, W, W ],  # y=2
    [    W, F, F, F, F, F, F, F, F, F, F, W ],  # y=3
    [    W, F, F, F, F, F, F, F, F, F, F, W ],  # y=4
    [    W, F, F, F, F, F, F, F, F, F, F, W ],  # y=5
    [    W, F, F, F, F, F, F, F, F, F, F, W ],  # y=6
    [    W, W, W, W, W, D, D, W, W, W, W, W ],  # y=7 (exit at 5,7 and 6,7)
]

# Map from map_id → grid
_STATIC_GRIDS: Dict[int, List[List[TileType]]] = {
    MAP_PLAYERS_HOUSE_2F: _HOUSE_2F_GRID,
    MAP_PLAYERS_HOUSE_1F: _HOUSE_1F_GRID,
    MAP_NEW_BARK_TOWN:    _NEW_BARK_GRID,
    MAP_ELMS_LAB:         _ELMS_LAB_GRID,
}


# ── MapData builder ──────────────────────────────────────────────────────────

def build_collision_map(map_id: int) -> Optional[MapData]:
    """Build a MapData from the static collision grid for a Crystal intro map.

    Returns None for map IDs not in the static set.
    For maps with a static grid: uses actual wall/floor/door/grass layout.
    """
    grid = _STATIC_GRIDS.get(map_id)
    if grid is None:
        return None

    height = len(grid)
    width = len(grid[0]) if height > 0 else 0
    name = MAP_NAMES.get(map_id, f"map_{map_id}")

    map_data = MapData(map_id=map_id, name=name, width=width, height=height)

    for y, row in enumerate(grid):
        for x, tile_type in enumerate(row):
            map_data.set_tile(x, y, tile_type)

    # Ensure warp tiles are marked as DOOR (may override static grid)
    for warp in WARP_TABLE:
        if warp.source_map == map_id:
            if 0 <= warp.source_x < width and 0 <= warp.source_y < height:
                map_data.set_tile(warp.source_x, warp.source_y, TileType.DOOR)

    return map_data


def build_intro_navigator_with_collision():
    """Build a Navigator preloaded with accurate collision data for intro maps.

    Replaces build_intro_navigator() from warp_data_crystal.py with maps that
    have real wall data instead of all-FLOOR approximations.

    Returns a Navigator instance with collision-accurate intro maps loaded.
    """
    from navigation import Navigator

    nav = Navigator()

    for map_id in _STATIC_GRIDS:
        map_data = build_collision_map(map_id)
        if map_data:
            nav.add_map(map_data)

    for warp in WARP_TABLE:
        nav.add_warp(warp)

    return nav


# ── Runtime RAM-based walkability check ─────────────────────────────────────

def read_map_dimensions_from_ram(emulator) -> Optional[Tuple[int, int]]:
    """Read current map dimensions (tiles) from Crystal RAM.

    Returns (width_tiles, height_tiles) or None on read failure.
    Crystal stores dimensions in blocks; we multiply by 2 for tiles.
    """
    try:
        height_blocks = emulator.read_memory(CUR_MAP_HEIGHT)
        width_blocks = emulator.read_memory(CUR_MAP_WIDTH)
        if height_blocks and width_blocks:
            return (width_blocks * 2, height_blocks * 2)
    except Exception:
        pass
    return None


def is_position_in_bounds(x: int, y: int, width: int, height: int) -> bool:
    """Return True if (x, y) is within map bounds."""
    return 0 <= x < width and 0 <= y < height


def get_walkable_directions(
    map_id: int,
    player_x: int,
    player_y: int,
    emulator=None,
) -> Dict[str, bool]:
    """Return which of the 4 cardinal directions the player can walk into.

    Uses the static collision grid for intro maps.
    Falls back to boundary-only check for unknown maps (using emulator RAM
    for dimensions when available).

    Args:
        map_id: Crystal map ID (group * 256 + number).
        player_x: Player tile X coordinate.
        player_y: Player tile Y coordinate.
        emulator: Optional EmulatorControl instance for RAM fallback.

    Returns:
        Dict with keys 'up', 'down', 'left', 'right' mapping to bool.
    """
    directions = {"up": False, "down": False, "left": False, "right": False}
    deltas = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

    grid = _STATIC_GRIDS.get(map_id)
    if grid is not None:
        height = len(grid)
        width = len(grid[0]) if height > 0 else 0
        for dir_name, (dx, dy) in deltas.items():
            nx, ny = player_x + dx, player_y + dy
            if 0 <= nx < width and 0 <= ny < height:
                tile = grid[ny][nx]
                directions[dir_name] = tile.is_walkable()
        return directions

    # Fallback: use RAM dimensions + boundary-only check
    dims = None
    if emulator is not None:
        dims = read_map_dimensions_from_ram(emulator)
    if dims is None:
        # Last resort: check map known dimensions table
        dims = MAP_DIMENSIONS.get(map_id)

    if dims is not None:
        width, height = dims
        for dir_name, (dx, dy) in deltas.items():
            nx, ny = player_x + dx, player_y + dy
            directions[dir_name] = is_position_in_bounds(nx, ny, width, height)

    return directions


def get_all_walkable_tiles(map_id: int) -> Set[Tuple[int, int]]:
    """Return the set of all walkable (x, y) tile coordinates for a map.

    Uses static collision grids. Returns empty set for unknown maps.
    """
    grid = _STATIC_GRIDS.get(map_id)
    if grid is None:
        return set()

    walkable: Set[Tuple[int, int]] = set()
    for y, row in enumerate(grid):
        for x, tile_type in enumerate(row):
            if tile_type.is_walkable():
                walkable.add((x, y))
    return walkable


def get_tile_type(map_id: int, x: int, y: int) -> Optional[TileType]:
    """Return the TileType at (x, y) for a map, or None if unknown."""
    grid = _STATIC_GRIDS.get(map_id)
    if grid is None:
        return None
    if 0 <= y < len(grid) and 0 <= x < len(grid[y]):
        return grid[y][x]
    return None
