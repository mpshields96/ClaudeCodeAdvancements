"""Tests for main.py — entry point and arg parsing."""
import unittest
import os
import sys

from main import parse_args


class TestParseArgs(unittest.TestCase):
    """Test command-line argument parsing."""

    def test_defaults(self):
        args = parse_args([])
        self.assertEqual(args.rom, "pokemon_crystal.gbc")
        self.assertEqual(args.steps, 1000)
        self.assertFalse(args.headless)
        self.assertEqual(args.speed, 0)
        self.assertIsNone(args.load_state)
        self.assertFalse(args.verbose)
        self.assertFalse(args.offline)

    def test_custom_rom(self):
        args = parse_args(["--rom", "my_crystal.gbc"])
        self.assertEqual(args.rom, "my_crystal.gbc")

    def test_custom_steps(self):
        args = parse_args(["--steps", "500"])
        self.assertEqual(args.steps, 500)

    def test_headless(self):
        args = parse_args(["--headless"])
        self.assertTrue(args.headless)

    def test_speed(self):
        args = parse_args(["--speed", "2"])
        self.assertEqual(args.speed, 2)

    def test_load_state(self):
        args = parse_args(["--load-state", "states/gym1.state"])
        self.assertEqual(args.load_state, "states/gym1.state")

    def test_verbose(self):
        args = parse_args(["-v"])
        self.assertTrue(args.verbose)

    def test_offline(self):
        args = parse_args(["--offline"])
        self.assertTrue(args.offline)

    def test_all_flags(self):
        args = parse_args([
            "--rom", "crystal.gbc",
            "--steps", "100",
            "--headless",
            "--speed", "3",
            "--load-state", "s.state",
            "--verbose",
            "--offline",
        ])
        self.assertEqual(args.rom, "crystal.gbc")
        self.assertEqual(args.steps, 100)
        self.assertTrue(args.headless)
        self.assertEqual(args.speed, 3)
        self.assertEqual(args.load_state, "s.state")
        self.assertTrue(args.verbose)
        self.assertTrue(args.offline)


if __name__ == "__main__":
    unittest.main()
