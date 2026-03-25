"""
test_consistency_checker.py — Tests for MT-32 Phase 4 cross-format consistency checker.

Tests audit_colors, audit_token_sharing, audit_font_consistency, and run_audit.
S164 — TDD for consistency_checker.py.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestAuditColors(unittest.TestCase):
    """Test orphan color detection in source code."""

    def test_approved_color_passes(self):
        from consistency_checker import audit_colors
        content = '''html = f'<div style="color: #1a1a2e">hello</div>'\n'''
        issues = audit_colors(Path("test.py"), content)
        self.assertEqual(len(issues), 0)

    def test_unapproved_color_flagged(self):
        from consistency_checker import audit_colors
        content = '''html = f'<div style="color: #ff00ff">hello</div>'\n'''
        issues = audit_colors(Path("test.py"), content)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, "orphan_color")
        self.assertIn("#ff00ff", issues[0].detail)

    def test_safe_colors_pass(self):
        from consistency_checker import audit_colors
        content = '''html = f'<div style="color: #000000; bg: #ffffff">'\n'''
        issues = audit_colors(Path("test.py"), content)
        self.assertEqual(len(issues), 0)

    def test_series_colors_pass(self):
        from consistency_checker import audit_colors
        content = '''fill = "#0f3460"\nstroke = "#e94560"\n'''
        issues = audit_colors(Path("test.py"), content)
        # These are in token definitions, should be skipped
        self.assertEqual(len(issues), 0)

    def test_token_definition_skipped(self):
        from consistency_checker import audit_colors
        content = '''COLORS = {\n    "primary": "#abcdef",\n}\n'''
        issues = audit_colors(Path("test.py"), content)
        self.assertEqual(len(issues), 0)

    def test_comment_lines_skipped(self):
        from consistency_checker import audit_colors
        content = '''# Color: #abcdef is for testing\n'''
        issues = audit_colors(Path("test.py"), content)
        self.assertEqual(len(issues), 0)

    def test_multiple_unapproved(self):
        from consistency_checker import audit_colors
        content = '''a = f"color: #aabbcc"\nb = f"bg: #ddeeff"\n'''
        issues = audit_colors(Path("test.py"), content)
        self.assertEqual(len(issues), 2)


class TestAuditTokenSharing(unittest.TestCase):
    """Test detection of local color dicts without design_linter import."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_local_colors_without_import_flagged(self):
        from consistency_checker import audit_token_sharing, PROJECT_ROOT
        fp = Path(self.tmpdir) / "gen.py"
        fp.write_text('COLORS = {\n    "primary": "#1a1a2e",\n}\n')
        with patch.object(Path, 'relative_to', return_value=Path("gen.py")):
            issues = audit_token_sharing([fp])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, "shared_token")

    def test_local_colors_with_import_passes(self):
        from consistency_checker import audit_token_sharing
        fp = Path(self.tmpdir) / "gen.py"
        fp.write_text('from design_linter import CCA_PALETTE\nCOLORS = {\n    "primary": "#1a1a2e",\n}\n')
        issues = audit_token_sharing([fp])
        self.assertEqual(len(issues), 0)

    def test_design_linter_itself_skipped(self):
        from consistency_checker import audit_token_sharing
        fp = Path(self.tmpdir) / "design_linter.py"
        fp.write_text('COLORS = {\n    "primary": "#1a1a2e",\n}\n')
        issues = audit_token_sharing([fp])
        self.assertEqual(len(issues), 0)

    def test_no_colors_dict_passes(self):
        from consistency_checker import audit_token_sharing
        fp = Path(self.tmpdir) / "gen.py"
        fp.write_text('def generate():\n    return "<html>"\n')
        issues = audit_token_sharing([fp])
        self.assertEqual(len(issues), 0)


class TestAuditFontConsistency(unittest.TestCase):
    """Test cross-file font consistency checking."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_single_font_passes(self):
        from consistency_checker import audit_font_consistency
        f1 = Path(self.tmpdir) / "a.py"
        f2 = Path(self.tmpdir) / "b.py"
        f1.write_text("css = 'font-family: Source Sans 3, Arial, sans-serif;'\n")
        f2.write_text("css = 'font-family: Source Sans 3, Helvetica, sans-serif;'\n")
        issues = audit_font_consistency([f1, f2])
        self.assertEqual(len(issues), 0)

    def test_different_primary_fonts_flagged(self):
        from consistency_checker import audit_font_consistency
        f1 = Path(self.tmpdir) / "a.py"
        f2 = Path(self.tmpdir) / "b.py"
        f1.write_text("css = 'font-family: Source Sans 3, sans-serif;'\n")
        f2.write_text("css = 'font-family: Inter, sans-serif;'\n")
        issues = audit_font_consistency([f1, f2])
        self.assertTrue(len(issues) >= 1)
        self.assertTrue(any(i.category == "font_mismatch" for i in issues))

    def test_fstring_artifacts_skipped(self):
        from consistency_checker import audit_font_consistency
        f1 = Path(self.tmpdir) / "a.py"
        f1.write_text("css = f'font-family: {font_var}, sans-serif;'\n")
        issues = audit_font_consistency([f1])
        self.assertEqual(len(issues), 0)

    def test_regex_lines_skipped(self):
        from consistency_checker import audit_font_consistency
        f1 = Path(self.tmpdir) / "a.py"
        f1.write_text("FONT_RE = re.compile(r'font-family:\\s*([^;]+)')\n")
        issues = audit_font_consistency([f1])
        self.assertEqual(len(issues), 0)


class TestRunAudit(unittest.TestCase):
    """Test the full audit pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_clean_file_passes(self):
        from consistency_checker import run_audit
        fp = Path(self.tmpdir) / "gen.py"
        fp.write_text('from design_linter import CCA_PALETTE\ndef gen():\n    return "<div>"\n')
        result = run_audit([fp])
        self.assertTrue(result["passed"])
        self.assertEqual(result["errors"], 0)

    def test_dirty_file_fails(self):
        from consistency_checker import run_audit
        fp = Path(self.tmpdir) / "gen.py"
        fp.write_text('html = f\'<div style="color: #ff00ff">bad</div>\'\n')
        result = run_audit([fp])
        self.assertFalse(result["passed"])
        self.assertGreater(result["errors"], 0)

    def test_result_structure(self):
        from consistency_checker import run_audit
        fp = Path(self.tmpdir) / "gen.py"
        fp.write_text('def gen():\n    return "ok"\n')
        result = run_audit([fp])
        self.assertIn("passed", result)
        self.assertIn("files_audited", result)
        self.assertIn("total_issues", result)
        self.assertIn("errors", result)
        self.assertIn("warnings", result)
        self.assertIn("issues", result)

    def test_nonexistent_file_skipped(self):
        from consistency_checker import run_audit
        fp = Path(self.tmpdir) / "nonexistent.py"
        result = run_audit([fp])
        self.assertEqual(result["files_audited"], 0)

    def test_json_output_format(self):
        from consistency_checker import run_audit
        fp = Path(self.tmpdir) / "gen.py"
        fp.write_text('x = 1\n')
        result = run_audit([fp])
        # Should be JSON-serializable
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["passed"], result["passed"])


class TestRealGenerators(unittest.TestCase):
    """Integration: run against actual CCA generator files."""

    def test_audit_finds_known_issues(self):
        """The dashboard dark mode palette is a known drift — audit should catch it."""
        from consistency_checker import run_audit, GENERATOR_FILES
        existing = [fp for fp in GENERATOR_FILES if fp.exists()]
        if not existing:
            self.skipTest("No generator files found")
        result = run_audit(existing)
        # We know dashboard_generator has dark mode colors not in palette
        self.assertGreater(result["total_issues"], 0)
        self.assertGreater(result["files_audited"], 0)

    def test_audit_returns_valid_structure(self):
        from consistency_checker import run_audit, GENERATOR_FILES
        existing = [fp for fp in GENERATOR_FILES if fp.exists()]
        if not existing:
            self.skipTest("No generator files found")
        result = run_audit(existing)
        self.assertIsInstance(result["issues"], list)
        for issue in result["issues"]:
            self.assertIn("category", issue)
            self.assertIn("severity", issue)
            self.assertIn("detail", issue)


if __name__ == "__main__":
    unittest.main()
