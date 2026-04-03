"""Static Crystal intro navigation bootstrap.

Provides a minimal `Navigator` for the four verified New Bark intro maps:
- Player's House 2F
- Player's House 1F
- New Bark Town
- Elm's Lab

This is intentionally not a full Crystal collision reader. It is a narrow
static bootstrap so the runtime can offer `navigate_to` on the intro maps
without pretending the whole game is mapped already.
"""
from __future__ import annotations

from navigation import MapData, Navigator, TileType, Warp
from boot_sequence_crystal import (
    MAP_ELMS_LAB,
    MAP_NEW_BARK_TOWN,
    MAP_PLAYERS_HOUSE_1F,
    MAP_PLAYERS_HOUSE_2F,
)
from crystal_data import get_map_name


def _encode_map(group: int, number: int) -> int:
    return group * 256 + number


MAP_ID_PLAYERS_HOUSE_2F = _encode_map(*MAP_PLAYERS_HOUSE_2F)
MAP_ID_PLAYERS_HOUSE_1F = _encode_map(*MAP_PLAYERS_HOUSE_1F)
MAP_ID_NEW_BARK_TOWN = _encode_map(*MAP_NEW_BARK_TOWN)
MAP_ID_ELMS_LAB = _encode_map(*MAP_ELMS_LAB)


def _fill_rect(map_data: MapData, width: int, height: int, tile_type: TileType) -> None:
    for y in range(height):
        for x in range(width):
            map_data.set_tile(x, y, tile_type)


def _players_house_2f() -> MapData:
    map_data = MapData(
        map_id=MAP_ID_PLAYERS_HOUSE_2F,
        name=get_map_name(*MAP_PLAYERS_HOUSE_2F),
        width=10,
        height=8,
    )
    _fill_rect(map_data, map_data.width, map_data.height, TileType.FLOOR)
    map_data.set_tile(7, 0, TileType.STAIR)
    return map_data


def _players_house_1f() -> MapData:
    map_data = MapData(
        map_id=MAP_ID_PLAYERS_HOUSE_1F,
        name=get_map_name(*MAP_PLAYERS_HOUSE_1F),
        width=10,
        height=8,
    )
    _fill_rect(map_data, map_data.width, map_data.height, TileType.FLOOR)
    map_data.set_tile(9, 0, TileType.STAIR)
    map_data.set_tile(6, 7, TileType.DOOR)
    map_data.set_tile(7, 7, TileType.DOOR)
    return map_data


def _new_bark_town() -> MapData:
    map_data = MapData(
        map_id=MAP_ID_NEW_BARK_TOWN,
        name=get_map_name(*MAP_NEW_BARK_TOWN),
        width=20,
        height=10,
    )
    _fill_rect(map_data, map_data.width, map_data.height, TileType.FLOOR)
    map_data.set_tile(13, 5, TileType.DOOR)  # Player's House exit
    map_data.set_tile(6, 3, TileType.DOOR)   # Elm's Lab entrance
    return map_data


def _elms_lab() -> MapData:
    map_data = MapData(
        map_id=MAP_ID_ELMS_LAB,
        name=get_map_name(*MAP_ELMS_LAB),
        width=10,
        height=8,
    )
    _fill_rect(map_data, map_data.width, map_data.height, TileType.FLOOR)
    map_data.set_tile(4, 7, TileType.DOOR)
    return map_data


def build_crystal_intro_navigator() -> Navigator:
    """Return a Navigator preloaded with the Crystal intro maps and warps."""
    navigator = Navigator()

    for map_data in (
        _players_house_2f(),
        _players_house_1f(),
        _new_bark_town(),
        _elms_lab(),
    ):
        navigator.add_map(map_data)

    for warp in (
        Warp(
            source_map=MAP_ID_PLAYERS_HOUSE_2F,
            source_x=7,
            source_y=0,
            dest_map=MAP_ID_PLAYERS_HOUSE_1F,
            dest_x=9,
            dest_y=0,
        ),
        Warp(
            source_map=MAP_ID_PLAYERS_HOUSE_1F,
            source_x=9,
            source_y=0,
            dest_map=MAP_ID_PLAYERS_HOUSE_2F,
            dest_x=7,
            dest_y=1,
        ),
        Warp(
            source_map=MAP_ID_PLAYERS_HOUSE_1F,
            source_x=6,
            source_y=7,
            dest_map=MAP_ID_NEW_BARK_TOWN,
            dest_x=13,
            dest_y=5,
        ),
        Warp(
            source_map=MAP_ID_PLAYERS_HOUSE_1F,
            source_x=7,
            source_y=7,
            dest_map=MAP_ID_NEW_BARK_TOWN,
            dest_x=13,
            dest_y=5,
        ),
        Warp(
            source_map=MAP_ID_NEW_BARK_TOWN,
            source_x=13,
            source_y=5,
            dest_map=MAP_ID_PLAYERS_HOUSE_1F,
            dest_x=6,
            dest_y=6,
        ),
        Warp(
            source_map=MAP_ID_NEW_BARK_TOWN,
            source_x=6,
            source_y=3,
            dest_map=MAP_ID_ELMS_LAB,
            dest_x=4,
            dest_y=7,
        ),
        Warp(
            source_map=MAP_ID_ELMS_LAB,
            source_x=4,
            source_y=7,
            dest_map=MAP_ID_NEW_BARK_TOWN,
            dest_x=6,
            dest_y=4,
        ),
    ):
        navigator.add_warp(warp)

    return navigator
