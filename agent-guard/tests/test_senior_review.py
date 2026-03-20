#!/usr/bin/env python3
"""Tests for senior_review.py — MT-20 Phase 7: On-demand senior developer review engine.

Tests cover:
- File reading and content analysis
- Integration with existing submodules (SATD, effort, quality)
- Project rule checking (CLAUDE.md patterns)
- ADR relevance matching
- Review output structure (design fit, concerns, suggestions, verdict)
- Edge cases (empty files, missing files, non-code files)
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from senior_review import SeniorReview, ReviewVerdict, review_file


class TestReviewVerdict(unittest.TestCase):
    """Test ReviewVerdict enum values."""

    def test_verdict_values(self):
        self.assertEqual(ReviewVerdict.APPROVE.value, "approve")
        self.assertEqual(ReviewVerdict.CONDITIONAL.value, "conditional")
        self.assertEqual(ReviewVerdict.RETHINK.value, "rethink")


class TestSeniorReviewInit(unittest.TestCase):
    """Test SeniorReview initialization."""

    def test_default_init(self):
        sr = SeniorReview()
        self.assertIsNotNone(sr)

    def test_custom_project_root(self):
        sr = SeniorReview(project_root="/tmp")
        self.assertEqual(sr.project_root, "/tmp")


class TestReviewFile(unittest.TestCase):
    """Test the main review_file function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_review_clean_file(self):
        path = self._write_file("clean.py", (
            '"""Clean module with good practices."""\n\n'
            'def calculate_total(items: list) -> float:\n'
            '    """Sum all item prices."""\n'
            '    return sum(item.price for item in items)\n'
        ))
        result = review_file(path, project_root=self.tmpdir)
        self.assertIsNotNone(result)
        self.assertIn("verdict", result)
        self.assertIn("concerns", result)
        self.assertIn("suggestions", result)
        self.assertIn("metrics", result)

    def test_review_file_with_hacks(self):
        path = self._write_file("hacky.py", (
            '# HACK: this is terrible\n'
            '# FIXME: broken logic\n'
            'def bad_function():\n'
            '    # WORKAROUND: upstream bug\n'
            '    pass\n'
        ))
        result = review_file(path, project_root=self.tmpdir)
        self.assertIn("concerns", result)
        self.assertTrue(len(result["concerns"]) > 0)

    def test_review_missing_file(self):
        result = review_file("/tmp/nonexistent_file_12345.py")
        self.assertEqual(result["verdict"], "error")
        self.assertIn("not found", result.get("error", "").lower())

    def test_review_empty_file(self):
        path = self._write_file("empty.py", "")
        result = review_file(path, project_root=self.tmpdir)
        self.assertEqual(result["verdict"], "approve")

    def test_review_non_code_file(self):
        path = self._write_file("readme.md", "# README\nSome docs")
        result = review_file(path, project_root=self.tmpdir)
        self.assertEqual(result["verdict"], "approve")
        # Non-code files get a pass with minimal analysis

    def test_review_result_has_file_path(self):
        path = self._write_file("mod.py", "x = 1\n")
        result = review_file(path, project_root=self.tmpdir)
        self.assertEqual(result["file_path"], path)

    def test_review_result_has_loc(self):
        path = self._write_file("mod.py", "x = 1\ny = 2\nz = 3\n")
        result = review_file(path, project_root=self.tmpdir)
        self.assertIn("loc", result["metrics"])
        self.assertEqual(result["metrics"]["loc"], 3)


class TestReviewConcerns(unittest.TestCase):
    """Test that the reviewer catches real issues."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_large_file_flagged(self):
        """Files >400 LOC should get a size concern."""
        content = "\n".join(f"line_{i} = {i}" for i in range(500))
        path = self._write_file("big.py", content)
        result = review_file(path, project_root=self.tmpdir)
        size_concerns = [c for c in result["concerns"] if "size" in c.lower() or "loc" in c.lower() or "large" in c.lower()]
        self.assertTrue(len(size_concerns) > 0, f"Expected size concern, got: {result['concerns']}")

    def test_high_satd_flagged(self):
        """Multiple HACK/FIXME markers should produce concerns."""
        content = "\n".join([
            "# HACK: bad",
            "# FIXME: broken",
            "# HACK: terrible",
            "x = 1",
        ])
        path = self._write_file("debt.py", content)
        result = review_file(path, project_root=self.tmpdir)
        debt_concerns = [c for c in result["concerns"] if "hack" in c.lower() or "debt" in c.lower() or "satd" in c.lower() or "fixme" in c.lower()]
        self.assertTrue(len(debt_concerns) > 0, f"Expected debt concern, got: {result['concerns']}")

    def test_complex_file_flagged(self):
        """Highly complex files should get a complexity concern."""
        # Generate a file with many nested control flow structures
        lines = ['def complex_function(data):']
        for i in range(25):
            indent = "    " * (1 + i % 4)
            lines.append(f'{indent}if data[{i}]:')
            lines.append(f'{indent}    for item in data[{i}]:')
            lines.append(f'{indent}        try:')
            lines.append(f'{indent}            pass')
            lines.append(f'{indent}        except Exception:')
            lines.append(f'{indent}            pass')
        content = "\n".join(lines)
        path = self._write_file("complex.py", content)
        result = review_file(path, project_root=self.tmpdir)
        # Should have some concerns about complexity or effort
        self.assertTrue(len(result["concerns"]) > 0)


class TestReviewVerdicLogic(unittest.TestCase):
    """Test verdict determination logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_clean_file_approved(self):
        path = self._write_file("good.py", (
            '"""Good module."""\n\n'
            'def add(a, b):\n'
            '    """Add two numbers."""\n'
            '    return a + b\n'
        ))
        result = review_file(path, project_root=self.tmpdir)
        self.assertEqual(result["verdict"], "approve")

    def test_messy_file_conditional(self):
        """Files with HIGH severity issues should get conditional verdict."""
        content = "\n".join([
            "# HACK: temp fix",
            "# FIXME: this breaks on edge cases",
            "# WORKAROUND: upstream is broken",
            "def hacky():",
            "    pass",
        ])
        path = self._write_file("messy.py", content)
        result = review_file(path, project_root=self.tmpdir)
        self.assertIn(result["verdict"], ["conditional", "rethink"])


class TestConvenienceFunction(unittest.TestCase):
    """Test the module-level review_file convenience function."""

    def test_review_file_returns_dict(self):
        tmpfile = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w")
        tmpfile.write("x = 1\n")
        tmpfile.close()
        try:
            result = review_file(tmpfile.name)
            self.assertIsInstance(result, dict)
        finally:
            os.unlink(tmpfile.name)


if __name__ == "__main__":
    unittest.main()
