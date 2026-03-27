"""Pokemon Crystal navigation system.

A* pathfinding on tile grids with multi-map support via warps and
connections. Zero external dependencies — stdlib only.

Usage:
    from navigation import Navigator, MapData, TileType, Warp
    from game_state import MapPosition

    nav = Navigator()
    map_data = MapData(map_id=1, name="New Bark Town", width=10, height=9)
    # populate tiles...
    nav.add_map(map_data)

    path = nav.find_path(
        MapPosition(map_id=1, x=3, y=4),
        MapPosition(map_id=1, x=8, y=2),
    )
    directions = Navigator.path_to_directions(path)
    # ["right", "right", "up", "right", "right", "up", "right"]

Stdlib only. No external dependencies.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from game_state import MapPosition


# ── Tile types ───────────────────────────────────────────────────────────────

class TileType(Enum):
    """Types of map tiles with walkability properties."""
    FLOOR = "floor"
    GRASS = "grass"
    WALL = "wall"
    WATER = "water"
    DOOR = "door"
    LEDGE_DOWN = "ledge_down"     # one-way jump (can walk off, can't climb up)
    LEDGE_LEFT = "ledge_left"
    LEDGE_RIGHT = "ledge_right"
    STAIR = "stair"
    COUNTER = "counter"           # NPC counters in shops/centers
    TREE = "tree"                 # cuttable with HM01
    ROCK = "rock"                 # smashable with Rock Smash
    WHIRLPOOL = "whirlpool"       # passable with Whirlpool HM
    WATERFALL = "waterfall"       # climbable with Waterfall HM
    ICE = "ice"                   # sliding ice puzzles

    def is_walkable(self) -> bool:
        """Can the player walk on this tile normally?"""
        return self in (
            TileType.FLOOR, TileType.GRASS, TileType.DOOR,
            TileType.STAIR, TileType.ICE,
        )

    def needs_surf(self) -> bool:
        return self in (TileType.WATER, TileType.WHIRLPOOL, TileType.WATERFALL)

    def has_encounters(self) -> bool:
        return self == TileType.GRASS

    def is_hm_passable(self) -> bool:
        """Passable with the right HM."""
        return self in (
            TileType.TREE, TileType.ROCK, TileType.WATER,
            TileType.WHIRLPOOL, TileType.WATERFALL,
        )

    def movement_cost(self, avoid_encounters: bool = False) -> float:
        """Cost multiplier for pathfinding. Higher = less preferred."""
        if self == TileType.GRASS and avoid_encounters:
            return 3.0  # penalize grass to avoid wild encounters
        if self == TileType.ICE:
            return 2.0  # ice is tricky
        return 1.0


# ── Map data ─────────────────────────────────────────────────────────────────

@dataclass
class MapTile:
    """A single map tile with position and type."""
    x: int
    y: int
    tile_type: TileType = TileType.FLOOR


@dataclass
class MapData:
    """Tile grid for a single map."""
    map_id: int
    name: str
    width: int
    height: int
    tiles: Dict[Tuple[int, int], TileType] = field(default_factory=dict)

    def set_tile(self, x: int, y: int, tile_type: TileType) -> None:
        self.tiles[(x, y)] = tile_type

    def get_tile(self, x: int, y: int) -> TileType:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return TileType.WALL
        return self.tiles.get((x, y), TileType.WALL)

    def is_walkable(self, x: int, y: int) -> bool:
        return self.get_tile(x, y).is_walkable()

    def walkable_neighbors(self, x: int, y: int) -> List[MapTile]:
        """Get walkable neighbors in cardinal directions."""
        result = []
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny):
                result.append(MapTile(nx, ny, self.get_tile(nx, ny)))
        return result


# ── Warps and connections ────────────────────────────────────────────────────

@dataclass
class Warp:
    """A warp point (door, staircase, cave entrance) that teleports between maps."""
    source_map: int
    source_x: int
    source_y: int
    dest_map: int
    dest_x: int
    dest_y: int

    def matches(self, map_id: int, x: int, y: int) -> bool:
        return self.source_map == map_id and self.source_x == x and self.source_y == y


@dataclass
class Connection:
    """Edge connection between adjacent maps (walking off the map edge)."""
    direction: str   # north, south, east, west
    source_map: int
    dest_map: int
    offset: int = 0  # x/y offset when transitioning


class NavigationError(Exception):
    """Raised when navigation fails."""
    pass


# ── Path step ────────────────────────────────────────────────────────────────

@dataclass
class PathStep:
    """One step in a navigation path."""
    direction: str   # up, down, left, right, warp
    map_id: int
    x: int
    y: int
    is_warp: bool = False

    def target_position(self) -> MapPosition:
        return MapPosition(map_id=self.map_id, x=self.x, y=self.y)


# ── A* node for priority queue ───────────────────────────────────────────────

@dataclass(order=True)
class _AStarNode:
    f_score: float
    g_score: float = field(compare=False)
    map_id: int = field(compare=False)
    x: int = field(compare=False)
    y: int = field(compare=False)
    parent: Optional[_AStarNode] = field(compare=False, default=None)
    direction: str = field(compare=False, default="")
    is_warp: bool = field(compare=False, default=False)


# ── Navigator ────────────────────────────────────────────────────────────────

# Direction deltas: direction -> (dx, dy)
_DIR_DELTA = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

# Reverse: (dx, dy) -> direction
_DELTA_DIR = {v: k for k, v in _DIR_DELTA.items()}


class Navigator:
    """A* pathfinder with multi-map support via warps and connections."""

    def __init__(self) -> None:
        self._maps: Dict[int, MapData] = {}
        self._warps: List[Warp] = []
        self._connections: List[Connection] = []
        # Pre-built index: (map_id, x, y) -> list of warps at that tile
        self._warp_index: Dict[Tuple[int, int, int], List[Warp]] = {}
        # Pre-built index: (direction, source_map) -> connection
        self._conn_index: Dict[Tuple[str, int], Connection] = {}

    def add_map(self, map_data: MapData) -> None:
        self._maps[map_data.map_id] = map_data

    def add_warp(self, warp: Warp) -> None:
        self._warps.append(warp)
        key = (warp.source_map, warp.source_x, warp.source_y)
        self._warp_index.setdefault(key, []).append(warp)

    def add_connection(self, conn: Connection) -> None:
        self._connections.append(conn)
        self._conn_index[(conn.direction, conn.source_map)] = conn

    def has_map(self, map_id: int) -> bool:
        return map_id in self._maps

    def get_map(self, map_id: int) -> Optional[MapData]:
        return self._maps.get(map_id)

    @staticmethod
    def manhattan(x1: int, y1: int, x2: int, y2: int) -> int:
        return abs(x1 - x2) + abs(y1 - y2)

    @staticmethod
    def path_to_directions(path: Optional[List[PathStep]]) -> List[str]:
        if path is None:
            return []
        return [s.direction for s in path]

    def find_path(
        self,
        start: MapPosition,
        goal: MapPosition,
        avoid_encounters: bool = False,
        max_iterations: int = 50000,
    ) -> Optional[List[PathStep]]:
        """A* pathfinding from start to goal, optionally crossing maps.

        Returns list of PathStep or None if no path exists.
        Empty list if already at goal.
        """
        # No map data
        if start.map_id not in self._maps:
            return None

        # Already there
        if (start.map_id == goal.map_id and start.x == goal.x
                and start.y == goal.y):
            return []

        # Destination on unwalkable tile
        if goal.map_id in self._maps:
            dest_map = self._maps[goal.map_id]
            if not dest_map.is_walkable(goal.x, goal.y):
                return None

        # Same map: single-map A*
        if start.map_id == goal.map_id and not self._has_cross_map_path(start.map_id, goal.map_id):
            return self._astar_single(start, goal, avoid_encounters, max_iterations)

        # Cross-map: multi-map A*
        return self._astar_multi(start, goal, avoid_encounters, max_iterations)

    def _has_cross_map_path(self, src: int, dst: int) -> bool:
        """Check if we might need to cross maps (different map IDs)."""
        return src != dst

    def _astar_single(
        self,
        start: MapPosition,
        goal: MapPosition,
        avoid_encounters: bool,
        max_iter: int,
    ) -> Optional[List[PathStep]]:
        """A* on a single map."""
        map_data = self._maps[start.map_id]
        h = self.manhattan(start.x, start.y, goal.x, goal.y)

        start_node = _AStarNode(
            f_score=h, g_score=0,
            map_id=start.map_id, x=start.x, y=start.y,
        )

        open_set: List[_AStarNode] = [start_node]
        closed: Set[Tuple[int, int]] = set()
        g_scores: Dict[Tuple[int, int], float] = {(start.x, start.y): 0}

        iterations = 0
        while open_set and iterations < max_iter:
            iterations += 1
            current = heapq.heappop(open_set)

            if current.x == goal.x and current.y == goal.y:
                return self._reconstruct(current)

            pos_key = (current.x, current.y)
            if pos_key in closed:
                continue
            closed.add(pos_key)

            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = current.x + dx, current.y + dy
                nkey = (nx, ny)

                if nkey in closed:
                    continue

                tile = map_data.get_tile(nx, ny)
                # Start position is always walkable (player is already there)
                if not tile.is_walkable() and not (nx == start.x and ny == start.y):
                    continue

                cost = tile.movement_cost(avoid_encounters)
                tentative_g = current.g_score + cost

                if tentative_g < g_scores.get(nkey, float("inf")):
                    g_scores[nkey] = tentative_g
                    h = self.manhattan(nx, ny, goal.x, goal.y)
                    direction = _DELTA_DIR.get((dx, dy), "")
                    node = _AStarNode(
                        f_score=tentative_g + h,
                        g_score=tentative_g,
                        map_id=start.map_id,
                        x=nx, y=ny,
                        parent=current,
                        direction=direction,
                    )
                    heapq.heappush(open_set, node)

        return None  # No path found

    def _astar_multi(
        self,
        start: MapPosition,
        goal: MapPosition,
        avoid_encounters: bool,
        max_iter: int,
    ) -> Optional[List[PathStep]]:
        """A* across multiple maps using warps and connections."""
        h = 0 if start.map_id == goal.map_id else 10  # cross-map heuristic boost

        start_node = _AStarNode(
            f_score=h + self.manhattan(start.x, start.y, goal.x, goal.y)
            if start.map_id == goal.map_id else h,
            g_score=0,
            map_id=start.map_id, x=start.x, y=start.y,
        )

        open_set: List[_AStarNode] = [start_node]
        closed: Set[Tuple[int, int, int]] = set()  # (map_id, x, y)
        g_scores: Dict[Tuple[int, int, int], float] = {
            (start.map_id, start.x, start.y): 0
        }

        iterations = 0
        while open_set and iterations < max_iter:
            iterations += 1
            current = heapq.heappop(open_set)

            if (current.map_id == goal.map_id and current.x == goal.x
                    and current.y == goal.y):
                return self._reconstruct(current)

            pos_key = (current.map_id, current.x, current.y)
            if pos_key in closed:
                continue
            closed.add(pos_key)

            cur_map = self._maps.get(current.map_id)
            if cur_map is None:
                continue

            # Normal walking neighbors
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = current.x + dx, current.y + dy
                nkey = (current.map_id, nx, ny)

                if nkey in closed:
                    continue

                tile = cur_map.get_tile(nx, ny)
                if not tile.is_walkable():
                    continue

                cost = tile.movement_cost(avoid_encounters)
                tentative_g = current.g_score + cost

                if tentative_g < g_scores.get(nkey, float("inf")):
                    g_scores[nkey] = tentative_g
                    if current.map_id == goal.map_id:
                        h_val = self.manhattan(nx, ny, goal.x, goal.y)
                    else:
                        h_val = 10  # heuristic for cross-map
                    direction = _DELTA_DIR.get((dx, dy), "")
                    node = _AStarNode(
                        f_score=tentative_g + h_val,
                        g_score=tentative_g,
                        map_id=current.map_id, x=nx, y=ny,
                        parent=current,
                        direction=direction,
                    )
                    heapq.heappush(open_set, node)

            # Warp transitions
            warp_key = (current.map_id, current.x, current.y)
            for warp in self._warp_index.get(warp_key, []):
                dest_key = (warp.dest_map, warp.dest_x, warp.dest_y)
                if dest_key in closed:
                    continue

                # Warp cost is 1 (one step through door)
                tentative_g = current.g_score + 1.0

                if tentative_g < g_scores.get(dest_key, float("inf")):
                    g_scores[dest_key] = tentative_g
                    if warp.dest_map == goal.map_id:
                        h_val = self.manhattan(warp.dest_x, warp.dest_y, goal.x, goal.y)
                    else:
                        h_val = 10
                    node = _AStarNode(
                        f_score=tentative_g + h_val,
                        g_score=tentative_g,
                        map_id=warp.dest_map,
                        x=warp.dest_x, y=warp.dest_y,
                        parent=current,
                        direction="warp",
                        is_warp=True,
                    )
                    heapq.heappush(open_set, node)

            # Connection transitions (map edge)
            self._expand_connections(current, cur_map, goal, open_set, closed, g_scores)

        return None

    def _expand_connections(
        self,
        current: _AStarNode,
        cur_map: MapData,
        goal: MapPosition,
        open_set: List[_AStarNode],
        closed: Set[Tuple[int, int, int]],
        g_scores: Dict[Tuple[int, int, int], float],
    ) -> None:
        """Expand map edge connections."""
        # Check if current position is at a map edge
        edges = []
        if current.y == 0:
            edges.append("north")
        if current.y == cur_map.height - 1:
            edges.append("south")
        if current.x == 0:
            edges.append("west")
        if current.x == cur_map.width - 1:
            edges.append("east")

        for direction in edges:
            conn = self._conn_index.get((direction, current.map_id))
            if conn is None:
                continue

            dest_map = self._maps.get(conn.dest_map)
            if dest_map is None:
                continue

            # Calculate destination position on the connected map
            if direction == "north":
                dest_x = current.x + conn.offset
                dest_y = dest_map.height - 1
            elif direction == "south":
                dest_x = current.x + conn.offset
                dest_y = 0
            elif direction == "west":
                dest_x = dest_map.width - 1
                dest_y = current.y + conn.offset
            else:  # east
                dest_x = 0
                dest_y = current.y + conn.offset

            dest_key = (conn.dest_map, dest_x, dest_y)
            if dest_key in closed:
                continue

            if not dest_map.is_walkable(dest_x, dest_y):
                continue

            tentative_g = current.g_score + 1.0
            if tentative_g < g_scores.get(dest_key, float("inf")):
                g_scores[dest_key] = tentative_g
                if conn.dest_map == goal.map_id:
                    h_val = self.manhattan(dest_x, dest_y, goal.x, goal.y)
                else:
                    h_val = 10
                # Direction of movement to cross the edge
                dir_name = {
                    "north": "up", "south": "down",
                    "west": "left", "east": "right",
                }[direction]
                node = _AStarNode(
                    f_score=tentative_g + h_val,
                    g_score=tentative_g,
                    map_id=conn.dest_map,
                    x=dest_x, y=dest_y,
                    parent=current,
                    direction=dir_name,
                    is_warp=False,
                )
                heapq.heappush(open_set, node)

    def _reconstruct(self, node: _AStarNode) -> List[PathStep]:
        """Reconstruct path from goal node back to start."""
        steps: List[PathStep] = []
        current = node
        while current.parent is not None:
            steps.append(PathStep(
                direction=current.direction,
                map_id=current.map_id,
                x=current.x,
                y=current.y,
                is_warp=current.is_warp,
            ))
            current = current.parent
        steps.reverse()
        return steps
