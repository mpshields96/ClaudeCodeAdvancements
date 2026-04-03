"""Tests for crystal_intro_navigation.py."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from crystal_intro_navigation import (
    MAP_ID_ELMS_LAB,
    MAP_ID_NEW_BARK_TOWN,
    MAP_ID_PLAYERS_HOUSE_1F,
    MAP_ID_PLAYERS_HOUSE_2F,
    build_crystal_intro_navigator,
)
from game_state import MapPosition
from navigation import Navigator


class TestCrystalIntroNavigator(unittest.TestCase):
    def setUp(self):
        self.navigator = build_crystal_intro_navigator()

    def test_intro_maps_are_loaded(self):
        self.assertTrue(self.navigator.has_map(MAP_ID_PLAYERS_HOUSE_2F))
        self.assertTrue(self.navigator.has_map(MAP_ID_PLAYERS_HOUSE_1F))
        self.assertTrue(self.navigator.has_map(MAP_ID_NEW_BARK_TOWN))
        self.assertTrue(self.navigator.has_map(MAP_ID_ELMS_LAB))

    def test_house_2f_path_to_stairs_exists(self):
        path = self.navigator.find_path(
            MapPosition(map_id=MAP_ID_PLAYERS_HOUSE_2F, x=4, y=4),
            MapPosition(map_id=MAP_ID_PLAYERS_HOUSE_2F, x=7, y=1),
        )
        self.assertIsNotNone(path)
        self.assertGreater(len(path), 0)

    def test_new_bark_path_to_lab_approach_exists(self):
        path = self.navigator.find_path(
            MapPosition(map_id=MAP_ID_NEW_BARK_TOWN, x=13, y=5),
            MapPosition(map_id=MAP_ID_NEW_BARK_TOWN, x=6, y=4),
        )
        self.assertIsNotNone(path)
        self.assertGreater(len(path), 0)

    def test_cross_map_path_uses_warps(self):
        path = self.navigator.find_path(
            MapPosition(map_id=MAP_ID_PLAYERS_HOUSE_2F, x=4, y=4),
            MapPosition(map_id=MAP_ID_NEW_BARK_TOWN, x=13, y=5),
        )
        self.assertIsNotNone(path)
        directions = Navigator.path_to_directions(path)
        self.assertIn("warp", directions)


if __name__ == "__main__":
    unittest.main()
