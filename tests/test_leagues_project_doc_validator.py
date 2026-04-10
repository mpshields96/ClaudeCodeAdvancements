#!/usr/bin/env python3
"""Tests for leagues_project_doc_validator.py.

Validates the Leagues Claude Project upload pack before mobile/web upload.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leagues_project_doc_validator import validate_pack


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestValidatePack(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_valid_four_doc_pack(self) -> None:
        _write(
            self.root / "01_OVERVIEW.md",
            "# Leagues 6 Planner\n\n## League Snapshot\n- League dates: April 15 - June 10, 2026\n\n"
            "## Current High-Confidence Consensus\n- Kandarin + Desert is strong for mage.\n",
        )
        _write(
            self.root / "02_REGIONS_RELICS_TASKS.md",
            "# Regions, Relics, and Tasks\n\n## Regions\n### Desert\n- Points: 1410\n\n"
            "## Relic Tiers\n### Tier 6\n| Relic | Short Description | Best Use Case | Notes |\n"
            "|------|-------------------|---------------|-------|\n| Grimoire | Magic unlocks | Mage | Strong |\n",
        )
        _write(
            self.root / "03_COMMUNITY_META.md",
            "# Community Meta\n\n## Strongest Repeated Region Trios\n"
            "| Trio | Combat Style / Goal | Confidence | Why People Like It |\n"
            "|------|----------------------|------------|--------------------|\n"
            "| Kandarin+Desert+Zeah | Magic | High | Strong mage path |\n",
        )
        _write(
            self.root / "04_QUERY_EXAMPLES.md",
            "# Query Examples\n\n## Fact Queries\n"
            "- What magic tasks give the most points in Desert? Cite which uploaded doc you used.\n",
        )

    def test_valid_four_doc_pack_passes(self):
        self._write_valid_four_doc_pack()
        result = validate_pack(self.root)
        self.assertTrue(result.ok)
        self.assertEqual(result.issue_count, 0)

    def test_require_planner_fails_without_fifth_doc(self):
        self._write_valid_four_doc_pack()
        result = validate_pack(self.root, require_planner=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("05_PLANNER_ROUTE_NOTES.md" in issue for issue in result.issues))

    def test_valid_five_doc_pack_passes(self):
        self._write_valid_four_doc_pack()
        _write(
            self.root / "05_PLANNER_ROUTE_NOTES.md",
            "# Planner and Route Notes\n\n## Current Focus Build\n- Build label: Magic route\n\n"
            "## Recommended Route Notes\n- Push toward Grimoire.\n",
        )
        result = validate_pack(self.root, require_planner=True)
        self.assertTrue(result.ok)

    def test_placeholder_tokens_fail_by_default(self):
        self._write_valid_four_doc_pack()
        _write(
            self.root / "05_PLANNER_ROUTE_NOTES.md",
            "# Planner and Route Notes\n\n## Current Focus Build\n- Build label: [fill in]\n\n"
            "## Recommended Route Notes\n- [step or priority note]\n",
        )
        result = validate_pack(self.root, require_planner=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("placeholder" in issue.lower() for issue in result.issues))

    def test_missing_required_heading_fails(self):
        self._write_valid_four_doc_pack()
        _write(
            self.root / "05_PLANNER_ROUTE_NOTES.md",
            "# Planner and Route Notes\n\n## Tradeoffs and Warnings\n- Wilderness tradeoff.\n",
        )
        result = validate_pack(self.root, require_planner=True)
        self.assertFalse(result.ok)
        self.assertTrue(any("Current Focus Build" in issue for issue in result.issues))


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_cli_json_success(self):
        _write(
            self.root / "01_OVERVIEW.md",
            "# Leagues 6 Planner\n\n## League Snapshot\n- League dates: April 15 - June 10, 2026\n\n"
            "## Current High-Confidence Consensus\n- Strong mage route.\n",
        )
        _write(
            self.root / "02_REGIONS_RELICS_TASKS.md",
            "# Regions, Relics, and Tasks\n\n## Regions\n### Desert\n- Points: 1410\n\n"
            "## Relic Tiers\n### Tier 6\n| Relic | Short Description | Best Use Case | Notes |\n"
            "|------|-------------------|---------------|-------|\n| Grimoire | Magic unlocks | Mage | Strong |\n",
        )
        _write(
            self.root / "03_COMMUNITY_META.md",
            "# Community Meta\n\n## Strongest Repeated Region Trios\n"
            "| Trio | Combat Style / Goal | Confidence | Why People Like It |\n"
            "|------|----------------------|------------|--------------------|\n"
            "| Kandarin+Desert+Zeah | Magic | High | Strong mage path |\n",
        )
        _write(
            self.root / "04_QUERY_EXAMPLES.md",
            "# Query Examples\n\n## Fact Queries\n"
            "- What magic tasks give the most points in Desert? Cite which uploaded doc you used.\n",
        )
        script = Path(__file__).resolve().parent.parent / "leagues_project_doc_validator.py"
        proc = subprocess.run(
            [sys.executable, str(script), "validate", str(self.root), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
