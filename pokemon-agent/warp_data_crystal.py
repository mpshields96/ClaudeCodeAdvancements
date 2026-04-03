"""Pokemon Crystal warp and connection data for cross-map A* pathfinding.

Static warp tables and simplified map grids for the intro sequence maps
(New Bark Town area), plus a Crystal-aware navigator builder.

Warp data sourced from pret/pokecrystal map header files (verified S221).
Map IDs use Crystal's group:number encoding: map_id = group * 256 + number.
All intro maps are in MapGroup_NewBark (group 24).

Map dimensions from pret/pokecrystal .blk files (in 2x2-tile blocks):
  PlayerHouse2F  : 5 blocks wide x 4 tall = 10 tiles x  8 tiles
  PlayerHouse1F  : 6 blocks wide x 4 tall = 12 tiles x  8 tiles
  NewBarkTown    : 10 blocks wide x 9 tall = 20 tiles x 18 tiles
  ElmsLab        : 6 blocks wide x 4 tall = 12 tiles x  8 tiles

Tile grids are simplified (FLOOR everywhere) because Crystal's block-based
collision system requires decoding runtime tileset data to get exact walls.
For the intro maps this is acceptable: the bot's main navigation need is
warp-transition awareness, not wall-precise pathfinding.

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from navigation import Connection, MapData, TileType, Warp

# ── Map ID encoding ──────────────────────────────────────────────────────────

def crystal_map_id(group: int, number: int) -> int:
    """Encode Crystal map group:number as single int.

    Matches MemoryReader.read_position() encoding: group * 256 + number.
    """
    return group * 256 + number


# ── Intro map IDs ────────────────────────────────────────────────────────────
# Source: pret/pokecrystal maps.asm, MapGroup_NewBark = 24 (verified S221)

MAP_PLAYERS_HOUSE_2F = crystal_map_id(24, 7)   # 6151
MAP_PLAYERS_HOUSE_1F = crystal_map_id(24, 6)   # 6150
MAP_NEW_BARK_TOWN    = crystal_map_id(24, 4)   # 6148
MAP_ELMS_LAB         = crystal_map_id(24, 5)   # 6149

# ── Map dimensions (tiles) ───────────────────────────────────────────────────
# Derived from pret/pokecrystal .blk file dimensions × 2 (blocks to tiles).

MAP_DIMENSIONS: Dict[int, tuple] = {
    MAP_PLAYERS_HOUSE_2F: (10, 8),   # width, height in tiles
    MAP_PLAYERS_HOUSE_1F: (12, 8),
    MAP_NEW_BARK_TOWN:    (20, 18),
    MAP_ELMS_LAB:         (12, 8),
}

MAP_NAMES: Dict[int, str] = {
    MAP_PLAYERS_HOUSE_2F: "Player's House 2F",
    MAP_PLAYERS_HOUSE_1F: "Player's House 1F",
    MAP_NEW_BARK_TOWN:    "New Bark Town",
    MAP_ELMS_LAB:         "Elm's Lab",
}

# ── Static warp table ────────────────────────────────────────────────────────
# Source: pret/pokecrystal map header files, verified S221 via RAM reads.
# Format: Warp(source_map, source_x, source_y, dest_map, dest_x, dest_y)
#
# Crystal warp semantics: stepping ON the warp tile triggers the transition.
# Arrival position = the warp exit tile on the destination map.

WARP_TABLE: List[Warp] = [
    # Player's House 2F → 1F (stairs down at tile 7,0)
    Warp(
        source_map=MAP_PLAYERS_HOUSE_2F, source_x=7, source_y=0,
        dest_map=MAP_PLAYERS_HOUSE_1F, dest_x=9, dest_y=0,
    ),
    # Player's House 1F → 2F (stairs up at tile 9,0)
    Warp(
        source_map=MAP_PLAYERS_HOUSE_1F, source_x=9, source_y=0,
        dest_map=MAP_PLAYERS_HOUSE_2F, dest_x=7, dest_y=0,
    ),
    # Player's House 1F → New Bark Town (door at 6,7)
    Warp(
        source_map=MAP_PLAYERS_HOUSE_1F, source_x=6, source_y=7,
        dest_map=MAP_NEW_BARK_TOWN, dest_x=7, dest_y=10,
    ),
    # Player's House 1F → New Bark Town (door at 7,7 — double-tile door)
    Warp(
        source_map=MAP_PLAYERS_HOUSE_1F, source_x=7, source_y=7,
        dest_map=MAP_NEW_BARK_TOWN, dest_x=8, dest_y=10,
    ),
    # New Bark Town → Player's House 1F (enter door)
    Warp(
        source_map=MAP_NEW_BARK_TOWN, source_x=7, source_y=9,
        dest_map=MAP_PLAYERS_HOUSE_1F, dest_x=6, dest_y=6,
    ),
    Warp(
        source_map=MAP_NEW_BARK_TOWN, source_x=8, source_y=9,
        dest_map=MAP_PLAYERS_HOUSE_1F, dest_x=7, dest_y=6,
    ),
    # New Bark Town → Elm's Lab (enter door)
    Warp(
        source_map=MAP_NEW_BARK_TOWN, source_x=11, source_y=9,
        dest_map=MAP_ELMS_LAB, dest_x=5, dest_y=6,
    ),
    Warp(
        source_map=MAP_NEW_BARK_TOWN, source_x=12, source_y=9,
        dest_map=MAP_ELMS_LAB, dest_x=6, dest_y=6,
    ),
    # Elm's Lab → New Bark Town (exit door)
    Warp(
        source_map=MAP_ELMS_LAB, source_x=5, source_y=7,
        dest_map=MAP_NEW_BARK_TOWN, dest_x=11, dest_y=10,
    ),
    Warp(
        source_map=MAP_ELMS_LAB, source_x=6, source_y=7,
        dest_map=MAP_NEW_BARK_TOWN, dest_x=12, dest_y=10,
    ),
]

# ── Map grid builder ─────────────────────────────────────────────────────────

def build_floor_map(map_id: int) -> Optional[MapData]:
    """Build a simplified MapData for a Crystal intro map.

    All tiles are FLOOR (walkable) except the outer boundary (WALL).
    Warp tiles are marked as DOOR.

    Crystal's block-based collision requires runtime tileset decoding to get
    exact walls. Floor-everywhere is a safe approximation for intro maps
    where the bot's main need is warp-transition tracking.

    Returns None if map_id is not in the intro set.
    """
    if map_id not in MAP_DIMENSIONS:
        return None

    width, height = MAP_DIMENSIONS[map_id]
    name = MAP_NAMES[map_id]

    map_data = MapData(map_id=map_id, name=name, width=width, height=height)

    # Fill interior with FLOOR, boundary with WALL
    for y in range(height):
        for x in range(width):
            if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                map_data.set_tile(x, y, TileType.WALL)
            else:
                map_data.set_tile(x, y, TileType.FLOOR)

    # Mark warp tiles as DOOR (walkable + signals transition)
    for warp in WARP_TABLE:
        if warp.source_map == map_id:
            if 0 <= warp.source_x < width and 0 <= warp.source_y < height:
                map_data.set_tile(warp.source_x, warp.source_y, TileType.DOOR)

    return map_data


def build_intro_navigator():
    """Build a Navigator preloaded with Crystal intro map data.

    Loads simplified tile grids and warp tables for the New Bark Town area.
    Suitable for main.py's CrystalAgent to enable navigate_to during the
    post-boot intro sequence.

    Returns a Navigator instance ready for find_path() calls.
    """
    from navigation import Navigator
    nav = Navigator()

    # Load simplified map grids
    for map_id in MAP_DIMENSIONS:
        map_data = build_floor_map(map_id)
        if map_data:
            nav.add_map(map_data)

    # Load warp transitions
    for warp in WARP_TABLE:
        nav.add_warp(warp)

    return nav


def get_warps_for_map(map_id: int) -> List[Warp]:
    """Return all warps where source_map matches map_id."""
    return [w for w in WARP_TABLE if w.source_map == map_id]
