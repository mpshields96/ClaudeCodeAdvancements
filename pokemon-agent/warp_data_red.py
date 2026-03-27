"""Pokemon Red warp and connection data for cross-map A* pathfinding.

Static warp tables for early-game maps (Pallet Town through Viridian City)
plus a RAM reader for dynamic warp discovery. Together these enable the
Navigator to find paths across map boundaries.

Warp data sourced from pret/pokered disassembly (wram.asm, map headers).
RAM layout per warp entry (4 bytes):
  byte 0: source Y (tile row on current map)
  byte 1: source X (tile col on current map)
  byte 2: destination warp index (which warp on dest map you appear at)
  byte 3: destination map ID

Stdlib only. No external dependencies beyond project modules.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from emulator_control import EmulatorControl
from navigation import Warp, Connection

# ── RAM addresses ────────────────────────────────────────────────────────────

WARP_COUNT_ADDR = 0xD3AE     # Number of warps on current map
WARP_DATA_ADDR = 0xD3AF      # Start of warp entries (4 bytes each)
WARP_ENTRY_SIZE = 4           # Bytes per warp entry
MAX_WARPS = 32                # Safety cap

# ── Static warp table ────────────────────────────────────────────────────────
# Early-game maps: Pallet Town, Red's House, Blue's House, Oak's Lab,
# Route 1, Viridian City, Viridian buildings.
#
# Coordinates from pret/pokered map header files.
# Format: Warp(source_map, source_x, source_y, dest_map, dest_x, dest_y)

WARP_TABLE: List[Warp] = [
    # ── Pallet Town (Map 0) ──────────────────────────────────────────────
    # Door to Red's House 1F
    Warp(source_map=0, source_x=5, source_y=5, dest_map=37, dest_x=2, dest_y=7),
    # Door to Blue's House
    Warp(source_map=0, source_x=13, source_y=5, dest_map=39, dest_x=2, dest_y=7),
    # Door to Oak's Lab
    Warp(source_map=0, source_x=12, source_y=11, dest_map=40, dest_x=4, dest_y=11),

    # ── Red's House 1F (Map 37) ─────────────────────────────────────────
    # Front door back to Pallet Town
    Warp(source_map=37, source_x=2, source_y=7, dest_map=0, dest_x=5, dest_y=6),
    Warp(source_map=37, source_x=3, source_y=7, dest_map=0, dest_x=5, dest_y=6),
    # Stairs to Red's House 2F
    Warp(source_map=37, source_x=7, source_y=1, dest_map=38, dest_x=7, dest_y=1),

    # ── Red's House 2F (Map 38) ─────────────────────────────────────────
    # Stairs back to 1F
    Warp(source_map=38, source_x=7, source_y=1, dest_map=37, dest_x=7, dest_y=1),

    # ── Blue's House (Map 39) ───────────────────────────────────────────
    # Front door back to Pallet Town
    Warp(source_map=39, source_x=2, source_y=7, dest_map=0, dest_x=13, dest_y=6),
    Warp(source_map=39, source_x=3, source_y=7, dest_map=0, dest_x=13, dest_y=6),

    # ── Oak's Lab (Map 40) ──────────────────────────────────────────────
    # Front door back to Pallet Town
    Warp(source_map=40, source_x=4, source_y=11, dest_map=0, dest_x=12, dest_y=12),
    Warp(source_map=40, source_x=5, source_y=11, dest_map=0, dest_x=12, dest_y=12),

    # ── Viridian City (Map 1) ───────────────────────────────────────────
    # Pokemon Center door
    Warp(source_map=1, source_x=13, source_y=13, dest_map=41, dest_x=3, dest_y=7),
    # Mart door
    Warp(source_map=1, source_x=17, source_y=11, dest_map=42, dest_x=2, dest_y=7),
    # School door
    Warp(source_map=1, source_x=9, source_y=11, dest_map=43, dest_x=2, dest_y=7),
    # Gym door (locked until later)
    Warp(source_map=1, source_x=17, source_y=17, dest_map=44, dest_x=2, dest_y=17),

    # ── Viridian Pokemon Center (Map 41) ────────────────────────────────
    Warp(source_map=41, source_x=3, source_y=7, dest_map=1, dest_x=13, dest_y=14),
    Warp(source_map=41, source_x=4, source_y=7, dest_map=1, dest_x=13, dest_y=14),

    # ── Viridian Mart (Map 42) ──────────────────────────────────────────
    Warp(source_map=42, source_x=2, source_y=7, dest_map=1, dest_x=17, dest_y=12),
    Warp(source_map=42, source_x=3, source_y=7, dest_map=1, dest_x=17, dest_y=12),

    # ── Viridian School (Map 43) ────────────────────────────────────────
    Warp(source_map=43, source_x=2, source_y=7, dest_map=1, dest_x=9, dest_y=12),
    Warp(source_map=43, source_x=3, source_y=7, dest_map=1, dest_x=9, dest_y=12),

    # ── Viridian Gym (Map 44) ───────────────────────────────────────────
    Warp(source_map=44, source_x=2, source_y=17, dest_map=1, dest_x=17, dest_y=18),
    Warp(source_map=44, source_x=3, source_y=17, dest_map=1, dest_x=17, dest_y=18),

    # ── Viridian Forest Entrance (Map 46) ───────────────────────────────
    Warp(source_map=46, source_x=4, source_y=7, dest_map=13, dest_x=3, dest_y=11),
    Warp(source_map=46, source_x=5, source_y=7, dest_map=13, dest_x=3, dest_y=11),

    # ── Route 2 (Map 13) — doors to forest gates ────────────────────────
    # South gate (Viridian Forest Entrance)
    Warp(source_map=13, source_x=3, source_y=11, dest_map=46, dest_x=4, dest_y=7),
    # North gate (Route 2 Gate)
    Warp(source_map=13, source_x=3, source_y=17, dest_map=47, dest_x=4, dest_y=0),

    # ── Route 2 Gate (Map 47) ───────────────────────────────────────────
    Warp(source_map=47, source_x=4, source_y=0, dest_map=13, dest_x=3, dest_y=17),
    Warp(source_map=47, source_x=5, source_y=0, dest_map=13, dest_x=3, dest_y=17),

    # ── Viridian Forest Exit (Map 48) ───────────────────────────────────
    Warp(source_map=48, source_x=4, source_y=0, dest_map=51, dest_x=17, dest_y=35),

    # ── Pewter Museum 2F (Map 51) — return from forest exit ─────────────
    Warp(source_map=51, source_x=17, source_y=35, dest_map=48, dest_x=4, dest_y=0),
]

# ── Static connection table ──────────────────────────────────────────────────
# Map edge connections for adjacent outdoor maps.
# Pokemon Red maps connect at edges — walking off the north edge of
# Pallet Town puts you on the south edge of Route 1.

CONNECTION_TABLE: List[Connection] = [
    # Pallet Town <-> Route 1
    Connection(direction="north", source_map=0, dest_map=12, offset=0),
    Connection(direction="south", source_map=12, dest_map=0, offset=0),

    # Route 1 <-> Viridian City
    Connection(direction="north", source_map=12, dest_map=1, offset=0),
    Connection(direction="south", source_map=1, dest_map=12, offset=0),

    # Viridian City <-> Route 2
    Connection(direction="north", source_map=1, dest_map=13, offset=0),
    Connection(direction="south", source_map=13, dest_map=1, offset=0),

    # Route 2 <-> Pewter City
    Connection(direction="north", source_map=13, dest_map=2, offset=0),
    Connection(direction="south", source_map=2, dest_map=13, offset=0),

    # Pallet Town <-> Route 21 (south, water route)
    Connection(direction="south", source_map=0, dest_map=32, offset=0),
    Connection(direction="north", source_map=32, dest_map=0, offset=0),

    # Viridian City <-> Route 22 (west)
    Connection(direction="west", source_map=1, dest_map=33, offset=0),
    Connection(direction="east", source_map=33, dest_map=1, offset=0),
]

# ── Index caches ─────────────────────────────────────────────────────────────

_WARP_BY_MAP: Dict[int, List[Warp]] = {}
_CONN_BY_MAP: Dict[int, List[Connection]] = {}


def _build_indices() -> None:
    """Build lookup indices for warps and connections by source map."""
    _WARP_BY_MAP.clear()
    _CONN_BY_MAP.clear()
    for w in WARP_TABLE:
        _WARP_BY_MAP.setdefault(w.source_map, []).append(w)
    for c in CONNECTION_TABLE:
        _CONN_BY_MAP.setdefault(c.source_map, []).append(c)


_build_indices()


def get_warps_for_map(map_id: int) -> List[Warp]:
    """Get all static warps where source_map == map_id."""
    return _WARP_BY_MAP.get(map_id, [])


def get_connections_for_map(map_id: int) -> List[Connection]:
    """Get all static connections where source_map == map_id."""
    return _CONN_BY_MAP.get(map_id, [])


# ── RAM warp reader ──────────────────────────────────────────────────────────

class WarpReaderRed:
    """Reads warp data from Pokemon Red emulator RAM.

    Reads the current map's warp entries from RAM at runtime.
    Each entry is 4 bytes: src_y, src_x, dest_warp_id, dest_map_id.
    """

    def __init__(self, emu: EmulatorControl):
        self._emu = emu

    def read_warp_count(self) -> int:
        """Number of warps on the current map (capped at MAX_WARPS)."""
        count = self._emu.read_byte(WARP_COUNT_ADDR)
        return min(count, MAX_WARPS)

    def read_warp_positions(self) -> List[Tuple[int, int]]:
        """Read source positions of all warps as (x, y) tuples.

        These are the tiles on the current map that are warp points.
        """
        count = self.read_warp_count()
        positions = []
        for i in range(count):
            base = WARP_DATA_ADDR + i * WARP_ENTRY_SIZE
            src_y = self._emu.read_byte(base + 0)
            src_x = self._emu.read_byte(base + 1)
            positions.append((src_x, src_y))
        return positions

    def read_warp_entries(self) -> List[Dict]:
        """Read full warp entries including destination info.

        Returns list of dicts with keys: src_x, src_y, dest_warp_id, dest_map.
        """
        count = self.read_warp_count()
        entries = []
        for i in range(count):
            base = WARP_DATA_ADDR + i * WARP_ENTRY_SIZE
            entries.append({
                "src_y": self._emu.read_byte(base + 0),
                "src_x": self._emu.read_byte(base + 1),
                "dest_warp_id": self._emu.read_byte(base + 2),
                "dest_map": self._emu.read_byte(base + 3),
            })
        return entries


# Type annotation for the Dict import
from typing import Dict as Dict  # noqa: F811 — already imported, just for clarity
