"""Pokemon Red collision map reader — extracts walkability from emulator RAM.

Reads the current map's dimensions, tile layout, and NPC positions from RAM
to build MapData objects for the A* Navigator. This is the bridge between
the emulator's live state and the pathfinding system.

Pokemon Red stores maps as 2x2 tile blocks. Each block contains 4 tiles.
Map dimensions in RAM are in blocks — multiply by 2 for tile coordinates.
The overworld map buffer at 0xC6E8 contains tile IDs for the visible area.
Tileset collision data determines which tile IDs are walkable.

For maps we don't have collision data for, we fall back to a heuristic:
all tiles except known wall/water IDs are assumed walkable.

RAM addresses from pret/pokered wram.asm.

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from emulator_control import EmulatorControl
from navigation import MapData, TileType
import memory_reader_red as mrr

# ── RAM addresses ───────────────────────────────────────────────────────────

MAP_HEIGHT = 0xD524          # Current map height in 2-tile blocks
MAP_WIDTH = 0xD525           # Current map width in 2-tile blocks
MAP_DATA_PTR = 0xD36A        # Pointer to map data (2 bytes, little-endian)
OVERWORLD_MAP = 0xC6E8       # Overworld tile buffer (movement permissions)
TILESET_COLLISION_PTR = 0xD530  # Pointer to tileset collision data (2 bytes)

# Sprites / NPCs
SPRITE_COUNT = 0xD4E1        # Number of sprites on current map
SPRITE_BASE = 0xC100         # Start of sprite data (OAM-like)
SPRITE_STRUCT_SIZE = 0x10    # 16 bytes per sprite
SPRITE_Y_OFFSET = 0x04       # Sprite Y position (pixels)
SPRITE_X_OFFSET = 0x06       # Sprite X position (pixels)
SPRITE_MOVABLE_OFFSET = 0x02 # Non-zero if sprite is visible/active

# Max sprites the game supports
MAX_SPRITES = 16

# ── Static walkable tile sets per tileset ──────────────────────────────────
# Source: pokered tileset definitions. Tile IDs that are walkable (no collision).
# These are the movement permission values from the overworld map buffer.
# In Pokemon Red, 0x00 = walkable, other values have special meaning.

# Overworld tileset (used by Pallet Town, routes, etc.)
# Walkable tile permission bytes from the overworld tileset
OVERWORLD_WALKABLE = {
    0x00,  # Plain ground
    0x04,  # Grass (tall grass, walkable but encounters)
    0x0C,  # Doorway
    0x10,  # Stair
    0x14,  # Sand/path
    0x18,  # Bridge
    0x24,  # Indoor floor
}

# Pallet Town uses the overworld tileset
PALLET_TOWN_WALKABLE = OVERWORLD_WALKABLE.copy()

# Route tileset — same as overworld for basic routes
ROUTE_WALKABLE = OVERWORLD_WALKABLE.copy()

# Indoor tileset (Pokemon Centers, houses, etc.)
INDOOR_WALKABLE = {
    0x00,  # Floor
    0x04,  # Carpet
    0x0C,  # Door mat
    0x10,  # Stair
    0x14,  # Rug
    0x24,  # Tile floor
}

# Map ID → walkable tile set
MAP_WALKABLE: Dict[int, Set[int]] = {}

# Outdoor maps: Pallet Town, Viridian City, Pewter City, routes
for mid in range(0, 37):  # Maps 0-36 are towns and routes
    MAP_WALKABLE[mid] = OVERWORLD_WALKABLE

# Red's House 1F, 2F, Blue's House, Oak's Lab
for mid in range(37, 41):
    MAP_WALKABLE[mid] = INDOOR_WALKABLE

# Gyms, Pokemon Centers, Marts — indoor tileset
for mid in [41, 42, 43, 44, 52, 53, 54, 58, 59, 60, 61]:
    MAP_WALKABLE[mid] = INDOOR_WALKABLE

# Default fallback: treat 0x00 as walkable
DEFAULT_WALKABLE = {0x00, 0x04, 0x0C, 0x10, 0x14, 0x24}


class CollisionReaderRed:
    """Reads collision/walkability data from Pokemon Red emulator RAM.

    Produces MapData objects that the Navigator can use for A* pathfinding.
    """

    def __init__(self, emu: EmulatorControl):
        self._emu = emu

    def read_map_dimensions(self) -> Tuple[int, int]:
        """Read current map dimensions in tiles.

        Returns (height_tiles, width_tiles). Blocks are 2x2 tiles.
        """
        height_blocks = self._emu.read_byte(MAP_HEIGHT)
        width_blocks = self._emu.read_byte(MAP_WIDTH)
        return (height_blocks * 2, width_blocks * 2)

    def read_sprite_count(self) -> int:
        """Read number of sprites on current map (capped at 16)."""
        count = self._emu.read_byte(SPRITE_COUNT)
        return min(count, MAX_SPRITES)

    def read_sprite_positions(self) -> List[Tuple[int, int]]:
        """Read NPC sprite positions as (x, y) tile coordinates.

        Sprite 0 is the player — skipped. Returns positions of NPCs only.
        Invisible sprites (movable byte == 0) are excluded.
        """
        count = self.read_sprite_count()
        positions = []

        for i in range(1, count + 1):
            base = SPRITE_BASE + i * SPRITE_STRUCT_SIZE
            movable = self._emu.read_byte(base + SPRITE_MOVABLE_OFFSET)
            if movable == 0:
                continue  # Invisible/inactive sprite

            pixel_y = self._emu.read_byte(base + SPRITE_Y_OFFSET)
            pixel_x = self._emu.read_byte(base + SPRITE_X_OFFSET)

            # Convert pixel coordinates to tile coordinates
            # Sprites are offset by 4 pixels vertically in Pokemon Red
            tile_y = (pixel_y - 4) // 16 if pixel_y >= 4 else pixel_y // 16
            tile_x = pixel_x // 16

            positions.append((tile_x, tile_y))

        return positions

    def read_overworld_tiles(self) -> List[List[int]]:
        """Read tile IDs from the overworld map buffer.

        The buffer has a stride of (width_blocks * 2 + 6) and is offset
        by 3 columns and 1 row of border tiles. Returns a 2D list of
        tile IDs [row][col].
        """
        height_tiles, width_tiles = self.read_map_dimensions()
        if height_tiles == 0 or width_tiles == 0:
            return []

        # Buffer stride includes 6 border columns (3 on each side)
        stride = width_tiles + 6
        # Skip first row of border + 3 border columns
        offset = stride + 3

        tiles = []
        for row in range(height_tiles):
            row_tiles = []
            for col in range(width_tiles):
                addr = OVERWORLD_MAP + offset + row * stride + col
                if addr < 0x10000:  # Stay in RAM bounds
                    row_tiles.append(self._emu.read_byte(addr))
                else:
                    row_tiles.append(0xFF)  # Out of bounds = wall
            tiles.append(row_tiles)

        return tiles

    def build_map_data(
        self,
        map_id: int,
        walkable_tiles: Optional[Set[int]] = None,
    ) -> MapData:
        """Build a MapData object from current RAM state.

        Args:
            map_id: The map ID to assign.
            walkable_tiles: Set of tile IDs that are walkable. If None,
                uses the static lookup table or default heuristic.

        Returns:
            MapData populated with tile types and NPC obstacles.
        """
        height_tiles, width_tiles = self.read_map_dimensions()
        map_name = mrr.MAP_NAMES.get(map_id, f"Map {map_id}")

        if walkable_tiles is None:
            walkable_tiles = MAP_WALKABLE.get(map_id, DEFAULT_WALKABLE)

        map_data = MapData(
            map_id=map_id,
            name=map_name,
            width=width_tiles,
            height=height_tiles,
        )

        # Read tile data from overworld buffer
        tile_grid = self.read_overworld_tiles()
        for row_idx, row in enumerate(tile_grid):
            for col_idx, tile_id in enumerate(row):
                if tile_id in walkable_tiles:
                    if tile_id == 0x04:
                        map_data.set_tile(col_idx, row_idx, TileType.GRASS)
                    elif tile_id in (0x0C, 0x10):
                        map_data.set_tile(col_idx, row_idx, TileType.DOOR)
                    else:
                        map_data.set_tile(col_idx, row_idx, TileType.FLOOR)
                else:
                    map_data.set_tile(col_idx, row_idx, TileType.WALL)

        # Mark NPC positions as walls (non-walkable obstacles)
        sprites = self.read_sprite_positions()
        for sx, sy in sprites:
            if 0 <= sx < width_tiles and 0 <= sy < height_tiles:
                map_data.set_tile(sx, sy, TileType.WALL)

        return map_data

    def build_current_map(self) -> MapData:
        """Build MapData for the map currently loaded in RAM.

        Reads map ID from RAM, looks up walkable tiles, and builds
        the collision grid. Convenience method for the bridge loop.
        """
        map_id = self._emu.read_byte(mrr.MAP_ID)
        walkable_tiles = MAP_WALKABLE.get(map_id, DEFAULT_WALKABLE)
        return self.build_map_data(map_id, walkable_tiles)
