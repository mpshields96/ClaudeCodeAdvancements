"""Tests for agent-guard/blast_radius.py.

Verifies: known import graph → correct values, high_risk fires at threshold,
zero-dep = 0, CLI modes, edge cases.

Run: python3 -m pytest agent-guard/tests/test_blast_radius.py -v
  or: python3 -m unittest agent-guard.tests.test_blast_radius
"""
from __future__ import annotations

import textwrap
import tempfile
import os
import sys
import unittest
from pathlib import Path

# Add project root to path so we can import blast_radius directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from blast_radius import (
    build_import_graph,
    build_reverse_deps,
    blast_radius,
    is_high_risk,
    high_risk_files,
    HIGH_RISK_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(dir_path: Path, rel: str, src: str) -> Path:
    """Write src to dir_path/rel, creating parent dirs."""
    target = dir_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(src))
    return target


# ---------------------------------------------------------------------------
# Unit tests: pure functions (no disk I/O)
# ---------------------------------------------------------------------------

class TestBlastRadius(unittest.TestCase):

    def _make_reverse(self, data: dict) -> dict:
        return {k: set(v) for k, v in data.items()}

    def test_zero_dep_returns_zero(self):
        # main imports util → reverse map has util: [main], main: []
        reverse = self._make_reverse({"util.py": ["main.py"], "main.py": []})
        self.assertEqual(blast_radius("main.py", reverse), 0)

    def test_single_importer(self):
        reverse = self._make_reverse({"util.py": ["main.py"], "main.py": []})
        self.assertEqual(blast_radius("util.py", reverse), 1)

    def test_multiple_importers(self):
        reverse = self._make_reverse({
            "base.py": ["a.py", "b.py", "c.py"],
            "a.py": [], "b.py": [], "c.py": [],
        })
        self.assertEqual(blast_radius("base.py", reverse), 3)

    def test_unknown_file_returns_zero(self):
        reverse = self._make_reverse({"a.py": []})
        self.assertEqual(blast_radius("nonexistent.py", reverse), 0)


class TestIsHighRisk(unittest.TestCase):

    def _make_reverse(self, data: dict) -> dict:
        return {k: set(v) for k, v in data.items()}

    def test_below_threshold_not_high_risk(self):
        importers = [f"f{i}.py" for i in range(HIGH_RISK_THRESHOLD)]
        reverse = {"core.py": set(importers)}
        self.assertFalse(is_high_risk("core.py", reverse))

    def test_at_threshold_not_high_risk(self):
        # exactly threshold is NOT high risk (must be > threshold)
        importers = [f"f{i}.py" for i in range(HIGH_RISK_THRESHOLD)]
        reverse = {"core.py": set(importers)}
        self.assertFalse(is_high_risk("core.py", reverse, threshold=HIGH_RISK_THRESHOLD))

    def test_above_threshold_is_high_risk(self):
        importers = [f"f{i}.py" for i in range(HIGH_RISK_THRESHOLD + 1)]
        reverse = {"core.py": set(importers)}
        self.assertTrue(is_high_risk("core.py", reverse))

    def test_custom_threshold(self):
        reverse = {"base.py": {"a.py", "b.py", "c.py"}}
        self.assertTrue(is_high_risk("base.py", reverse, threshold=2))
        self.assertFalse(is_high_risk("base.py", reverse, threshold=3))

    def test_zero_dep_never_high_risk(self):
        reverse = {"isolated.py": set()}
        self.assertFalse(is_high_risk("isolated.py", reverse))

    def test_high_risk_fires_at_six(self):
        """Canonical: default threshold is 5, so 6 importers → high risk."""
        importers = {f"importer_{i}.py" for i in range(6)}
        reverse = {"shared.py": importers}
        self.assertTrue(is_high_risk("shared.py", reverse))


class TestHighRiskFiles(unittest.TestCase):

    def test_returns_sorted_descending(self):
        reverse = {
            "a.py": {f"x{i}.py" for i in range(3)},
            "b.py": {f"x{i}.py" for i in range(7)},
            "c.py": {f"x{i}.py" for i in range(6)},
            "d.py": set(),
        }
        result = high_risk_files(reverse, threshold=5)
        radii = [r for _, r in result]
        self.assertEqual(radii, sorted(radii, reverse=True))
        files = [f for f, _ in result]
        self.assertIn("b.py", files)
        self.assertIn("c.py", files)
        self.assertNotIn("a.py", files)
        self.assertNotIn("d.py", files)

    def test_empty_graph_returns_empty(self):
        self.assertEqual(high_risk_files({}, threshold=5), [])


class TestBuildReverseDeps(unittest.TestCase):

    def test_inversion_simple(self):
        forward = {
            "main.py": {"util.py"},
            "util.py": set(),
        }
        reverse = build_reverse_deps(forward)
        self.assertIn("main.py", reverse["util.py"])
        self.assertEqual(reverse["main.py"], set())

    def test_all_nodes_present(self):
        forward = {"a.py": {"b.py"}, "b.py": {"c.py"}, "c.py": set()}
        reverse = build_reverse_deps(forward)
        for key in ("a.py", "b.py", "c.py"):
            self.assertIn(key, reverse)

    def test_diamond_dependency(self):
        # a → b, a → c, b → d, c → d  ⟹  d has 2 reverse deps
        forward = {
            "a.py": {"b.py", "c.py"},
            "b.py": {"d.py"},
            "c.py": {"d.py"},
            "d.py": set(),
        }
        reverse = build_reverse_deps(forward)
        self.assertEqual(blast_radius("d.py", reverse), 2)
        self.assertEqual(blast_radius("a.py", reverse), 0)


# ---------------------------------------------------------------------------
# Integration tests: actual disk I/O with tmp dirs
# ---------------------------------------------------------------------------

class TestBuildImportGraph(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_absolute_import(self):
        _write(self.root, "util.py", "x = 1\n")
        _write(self.root, "main.py", "import util\n")
        forward = build_import_graph(self.root)
        self.assertIn("util.py", forward["main.py"])

    def test_from_import(self):
        _write(self.root, "helpers.py", "def f(): pass\n")
        _write(self.root, "app.py", "from helpers import f\n")
        forward = build_import_graph(self.root)
        self.assertIn("helpers.py", forward["app.py"])

    def test_external_import_excluded(self):
        _write(self.root, "app.py", "import os\nimport json\nimport requests\n")
        forward = build_import_graph(self.root)
        # os, json, requests are not .py files in root — should not appear
        self.assertEqual(forward["app.py"], set())

    def test_syntax_error_file_included_empty_deps(self):
        _write(self.root, "broken.py", "def oops(\n")
        forward = build_import_graph(self.root)
        self.assertIn("broken.py", forward)
        self.assertEqual(forward["broken.py"], set())

    def test_zero_dep_file(self):
        _write(self.root, "standalone.py", "ANSWER = 42\n")
        forward = build_import_graph(self.root)
        reverse = build_reverse_deps(forward)
        self.assertEqual(blast_radius("standalone.py", reverse), 0)

    def test_known_import_graph_correct_values(self):
        """Canonical integration test: 3-file chain, verify blast radii."""
        _write(self.root, "base.py", "VALUE = 1\n")
        _write(self.root, "mid.py", "from base import VALUE\n")
        _write(self.root, "top.py", "import mid\n")
        forward = build_import_graph(self.root)
        reverse = build_reverse_deps(forward)
        # base is imported by mid → radius 1
        self.assertEqual(blast_radius("base.py", reverse), 1)
        # mid is imported by top → radius 1
        self.assertEqual(blast_radius("mid.py", reverse), 1)
        # top is imported by nobody → radius 0
        self.assertEqual(blast_radius("top.py", reverse), 0)

    def test_high_risk_fires_at_threshold(self):
        """6 files import shared.py → high_risk."""
        _write(self.root, "shared.py", "CONSTANT = True\n")
        for i in range(6):
            _write(self.root, f"consumer_{i}.py", "from shared import CONSTANT\n")
        forward = build_import_graph(self.root)
        reverse = build_reverse_deps(forward)
        self.assertTrue(is_high_risk("shared.py", reverse))
        self.assertEqual(blast_radius("shared.py", reverse), 6)

    def test_high_risk_not_triggered_at_five(self):
        """5 files import shared.py → NOT high_risk (must be strictly >5)."""
        _write(self.root, "shared.py", "CONSTANT = True\n")
        for i in range(5):
            _write(self.root, f"consumer_{i}.py", "from shared import CONSTANT\n")
        forward = build_import_graph(self.root)
        reverse = build_reverse_deps(forward)
        self.assertFalse(is_high_risk("shared.py", reverse))

    def test_relative_import(self):
        pkg = self.root / "mypkg"
        pkg.mkdir()
        _write(self.root, "mypkg/__init__.py", "")
        _write(self.root, "mypkg/utils.py", "def helper(): pass\n")
        _write(self.root, "mypkg/main.py", "from . import utils\n")
        forward = build_import_graph(self.root)
        self.assertIn("mypkg/utils.py", forward.get("mypkg/main.py", set()))


if __name__ == "__main__":
    unittest.main()
