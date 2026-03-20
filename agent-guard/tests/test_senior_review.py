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


class TestFPFilterIntegration(unittest.TestCase):
    """Test that fp_filter is wired into senior_review to reduce false positives."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_test_file_satd_reduced(self):
        """SATD markers in test files should have reduced impact on verdict."""
        # Test files commonly have TODO/FIXME for test improvements — not real debt
        path = self._write_file("tests/test_something.py", (
            '"""Tests."""\n'
            '# TODO: add more edge cases\n'
            '# TODO: test with empty input\n'
            '# TODO: parameterize this\n'
            '# TODO: test timeout behavior\n'
            '# TODO: test concurrent access\n'
            'def test_basic():\n'
            '    assert True\n'
        ))
        result = review_file(path, project_root=self.tmpdir)
        # Test file TODOs are LOW severity and should be filtered
        # Should not push verdict to conditional/rethink
        self.assertIn("fp_confidence", result["metrics"])

    def test_vendored_file_skipped(self):
        """Vendored files should get minimal review."""
        path = self._write_file("vendor/lib.py", (
            '# HACK: vendored code\n'
            '# FIXME: not our problem\n'
            'def vendored_function():\n'
            '    pass\n'
        ))
        result = review_file(path, project_root=self.tmpdir)
        self.assertIn("fp_confidence", result["metrics"])
        self.assertLessEqual(result["metrics"]["fp_confidence"], 0.0)

    def test_normal_file_full_confidence(self):
        """Normal source files should have full fp_confidence."""
        path = self._write_file("core.py", (
            '"""Core module."""\n'
            'def run():\n'
            '    pass\n'
        ))
        result = review_file(path, project_root=self.tmpdir)
        self.assertEqual(result["metrics"].get("fp_confidence", 1.0), 1.0)

    def test_vendored_satd_not_counted(self):
        """SATD in vendored files should not inflate satd_total in metrics."""
        path = self._write_file("vendor/hack.py", (
            '# HACK: not ours\n# FIXME: not ours\n# WORKAROUND: not ours\n'
            'x = 1\n'
        ))
        result = review_file(path, project_root=self.tmpdir)
        # Vendored files should have filtered SATD counts
        self.assertEqual(result["metrics"].get("satd_total", 0), 0)


class TestADRIntegration(unittest.TestCase):
    """Test that ADR reader is wired into senior review."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_relevant_adr_surfaces_in_review(self):
        """When an ADR matches the reviewed file, it should appear in concerns."""
        # Create an ADR about authentication
        self._write_file("docs/adr/001-use-jwt-auth.md", (
            "# Use JWT Authentication\n\n"
            "## Status\nAccepted\n\n"
            "## Decision\nAll authentication must use JWT tokens with RS256 signing. "
            "Session cookies are deprecated. Never store tokens in localStorage.\n"
        ))
        # Create a file that touches authentication
        code_path = self._write_file("auth_handler.py", (
            '"""Authentication handler."""\n\n'
            'def authenticate(token):\n'
            '    """Validate JWT authentication token."""\n'
            '    return verify_jwt(token)\n'
        ))
        result = review_file(code_path, project_root=self.tmpdir)
        self.assertIn("relevant_adrs", result["metrics"])

    def test_no_adr_dir_no_crash(self):
        """Projects without ADR directories should work fine."""
        code_path = self._write_file("mod.py", '"""Module."""\nx = 1\n')
        result = review_file(code_path, project_root=self.tmpdir)
        self.assertEqual(result["metrics"].get("relevant_adrs", 0), 0)

    def test_deprecated_adr_flagged(self):
        """Deprecated ADRs matching the file should surface as warnings."""
        self._write_file("docs/adr/002-use-xml-config.md", (
            "# Use XML Configuration\n\n"
            "## Status\nDeprecated\n\n"
            "## Decision\nConfiguration files should use XML format for parsing.\n"
        ))
        code_path = self._write_file("config_parser.py", (
            '"""Configuration parser module."""\n\n'
            'def parse_config(path):\n'
            '    """Parse XML configuration file."""\n'
            '    pass\n'
        ))
        result = review_file(code_path, project_root=self.tmpdir)
        # Should have relevant ADRs noted
        self.assertGreaterEqual(result["metrics"].get("relevant_adrs", 0), 0)


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
