#!/usr/bin/env python3
"""Tests for leagues_project_doc_pack.py."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leagues_project_doc_pack import init_pack


class TestInitPack(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_creates_minimal_four_doc_pack(self):
        result = init_pack(self.root)
        self.assertEqual(len(result.created), 4)
        self.assertTrue((self.root / "01_OVERVIEW.md").exists())
        self.assertFalse((self.root / "05_PLANNER_ROUTE_NOTES.md").exists())

    def test_creates_five_doc_pack_with_planner(self):
        result = init_pack(self.root, with_planner=True)
        self.assertEqual(len(result.created), 5)
        self.assertTrue((self.root / "05_PLANNER_ROUTE_NOTES.md").exists())

    def test_skips_existing_without_overwrite(self):
        target = self.root / "01_OVERVIEW.md"
        target.write_text("custom", encoding="utf-8")
        result = init_pack(self.root)
        self.assertIn("01_OVERVIEW.md", result.skipped)
        self.assertEqual(target.read_text(encoding="utf-8"), "custom")

    def test_overwrite_replaces_existing(self):
        target = self.root / "01_OVERVIEW.md"
        target.write_text("custom", encoding="utf-8")
        init_pack(self.root, overwrite=True)
        self.assertNotEqual(target.read_text(encoding="utf-8"), "custom")
        self.assertIn("# Leagues 6 Planner", target.read_text(encoding="utf-8"))


class TestCLI(unittest.TestCase):
    def test_cli_json_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(__file__).resolve().parent.parent / "leagues_project_doc_pack.py"
            proc = subprocess.run(
                [sys.executable, str(script), "init", tmpdir, "--with-planner", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            payload = json.loads(proc.stdout)
            self.assertEqual(len(payload["created"]), 5)


if __name__ == "__main__":
    unittest.main()
