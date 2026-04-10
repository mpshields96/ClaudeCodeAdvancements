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

from leagues_project_doc_pack import init_pack, materialize_pack


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


class TestMaterializePack(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.context_path = self.root / "context.json"
        self.context = {
            "source_paths": ["data/wiki_data.json", "data/community_meta.json"],
            "overview": {
                "snapshot": {
                    "league_dates": "April 15 - June 10, 2026",
                    "key_reveal_dates": "April 10 echo item stats",
                    "always_unlocked_context": "Varlamore and Karamja",
                    "current_planner_runtime_note": "Planner.py live sheet advisor active",
                },
                "region_point_snapshot": [
                    {"region": "Desert", "points": "1410", "notes": "Strong mage value"},
                    {"region": "Asgarnia", "points": "1170", "notes": "Strong melee utility"},
                ],
                "current_high_confidence_consensus": ["Kandarin + Desert is core for mage."],
                "known_uncertainties": ["Reveal data may change optimal route."],
            },
            "regions_relics_tasks": {
                "regions": [
                    {
                        "name": "Desert",
                        "points": "1410",
                        "identity": "Magic and ancients power spike",
                        "reasons": ["Ancients access", "High mage task value"],
                        "notes": ["Pairs well with Kandarin"],
                        "best_fit": ["Magic"],
                    }
                ],
                "relic_tiers": [
                    {
                        "tier": "6",
                        "relics": [
                            {
                                "name": "Grimoire",
                                "description": "Spellbook flexibility",
                                "best_use_case": "Mage",
                                "notes": "Core late-game mage relic",
                            }
                        ],
                    }
                ],
                "task_themes": {
                    "Magic": [{"task": "Cast barrage", "region": "Desert", "points": "200", "note": "Ancients route"}],
                },
                "important_build_constraints": ["Need enough total points for T6."],
            },
            "community_meta": {
                "trios": [{"trio": "Kandarin+Desert+Zeah", "goal": "Magic", "confidence": "High", "summary": "Most repeated mage trio"}],
                "agreements": ["Ancients are core for most mage builds."],
                "splits": [{"question": "Zeah vs Asgarnia", "side_a": "Zeah for raids", "side_b": "Asgarnia for utility"}],
                "lazy_recommendations": ["Dad-style routes favor simpler unlock paths."],
            },
            "query_examples": {
                "fact_queries": ["What magic tasks give the most points in Desert? Cite the doc."],
                "build_queries": ["Recommend 3 regions for a lazy magic build."],
                "route_queries": ["What is the safest early route for mage?"],
                "validation_queries": ["Separate facts from community opinions."],
                "planner_support_queries": ["What are the tradeoffs of this trio?"],
            },
            "planner_route_notes": {
                "current_focus_build": {
                    "build_label": "Magic route",
                    "target_style": "magic",
                    "core_regions": "Kandarin, Desert, Zeah",
                    "core_relic_direction": "Grimoire",
                    "main_goal": "T6 mage spike",
                },
                "recommended_route_notes": ["Reach Grimoire quickly."],
                "planner_outputs": ["Wilderness is the 4th-region candidate for point gap closure."],
                "tradeoffs_and_warnings": ["Late reveal data may change route quality."],
                "open_questions": ["Need final echo stats refresh."],
            },
        }
        self.context_path.write_text(json.dumps(self.context), encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_materialize_writes_docs_and_manifest(self):
        result = materialize_pack(self.root / "out", self.context, context_path=str(self.context_path), with_planner=True)
        self.assertEqual(len(result.created), 5)
        overview = (self.root / "out" / "01_OVERVIEW.md").read_text(encoding="utf-8")
        self.assertIn("April 15 - June 10, 2026", overview)
        planner = (self.root / "out" / "05_PLANNER_ROUTE_NOTES.md").read_text(encoding="utf-8")
        self.assertIn("Magic route", planner)
        manifest = json.loads((self.root / "out" / "leagues_project_pack.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["doc_count"], 5)
        self.assertEqual(manifest["context_path"], str(self.context_path))

    def test_materialize_cli_json_output(self):
        script = Path(__file__).resolve().parent.parent / "leagues_project_doc_pack.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "materialize",
                str(self.root / "rendered"),
                str(self.context_path),
                "--with-planner",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(len(payload["created"]), 5)
        self.assertTrue(payload["manifest_path"].endswith("leagues_project_pack.json"))


if __name__ == "__main__":
    unittest.main()
