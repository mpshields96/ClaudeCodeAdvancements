#!/usr/bin/env python3
"""Tests for design_linter.py — MT-32 Phase 3: Design system lint rules."""

import os
import sys
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from design_linter import (
    CCA_PALETTE,
    ANTI_SLOP_COLORS,
    lint_colors,
    lint_fonts,
    lint_spacing,
    lint_anti_slop,
    lint_all,
    Violation,
)


class TestCCAPalette(unittest.TestCase):

    def test_palette_has_required_colors(self):
        required = ["primary", "accent", "highlight", "success", "warning",
                     "muted", "bg", "surface", "border"]
        for name in required:
            self.assertIn(name, CCA_PALETTE, f"Missing palette color: {name}")

    def test_palette_values_are_hex(self):
        for name, value in CCA_PALETTE.items():
            self.assertTrue(value.startswith("#"), f"{name} not hex: {value}")
            self.assertEqual(len(value), 7, f"{name} not 6-digit hex: {value}")


class TestLintColors(unittest.TestCase):

    def test_clean_html_no_violations(self):
        html = '<div style="color: #1a1a2e; background: #f8f9fa;">OK</div>'
        violations = lint_colors(html)
        self.assertEqual(violations, [])

    def test_orphan_hex_detected(self):
        html = '<div style="color: #ff00ff;">Purple text</div>'
        violations = lint_colors(html)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("#ff00ff" in v.detail for v in violations))

    def test_svg_fill_checked(self):
        svg = '<rect fill="#abc123" />'
        violations = lint_colors(svg)
        self.assertGreater(len(violations), 0)

    def test_series_colors_allowed(self):
        svg = '<rect fill="#8b5cf6" />'  # Series 6 (violet)
        violations = lint_colors(svg)
        self.assertEqual(violations, [])

    def test_common_safe_colors_allowed(self):
        html = '<div style="color: #000000; background: #ffffff;">BW</div>'
        violations = lint_colors(html)
        self.assertEqual(violations, [])

    def test_case_insensitive(self):
        html = '<div style="color: #1A1A2E;">OK</div>'
        violations = lint_colors(html)
        self.assertEqual(violations, [])

    def test_multiple_violations(self):
        html = '<div style="color: #ff00ff; background: #00ff00;">Bad</div>'
        violations = lint_colors(html)
        self.assertGreaterEqual(len(violations), 2)


class TestLintFonts(unittest.TestCase):

    def test_approved_font_passes(self):
        html = '<p style="font-family: Source Sans 3, sans-serif;">OK</p>'
        violations = lint_fonts(html)
        self.assertEqual(violations, [])

    def test_unapproved_font_detected(self):
        html = '<p style="font-family: Comic Sans MS;">Bad</p>'
        violations = lint_fonts(html)
        self.assertGreater(len(violations), 0)

    def test_code_font_allowed(self):
        html = '<code style="font-family: Source Code Pro;">code</code>'
        violations = lint_fonts(html)
        self.assertEqual(violations, [])

    def test_fallback_fonts_allowed(self):
        html = '<p style="font-family: Helvetica Neue, Arial, sans-serif;">OK</p>'
        violations = lint_fonts(html)
        self.assertEqual(violations, [])

    def test_no_font_declarations_passes(self):
        html = '<p>No font specified</p>'
        violations = lint_fonts(html)
        self.assertEqual(violations, [])


class TestLintSpacing(unittest.TestCase):

    def test_grid_aligned_passes(self):
        html = '<div style="padding: 8px; margin: 16px;">OK</div>'
        violations = lint_spacing(html)
        self.assertEqual(violations, [])

    def test_off_grid_detected(self):
        html = '<div style="padding: 13px;">Off grid</div>'
        violations = lint_spacing(html)
        self.assertGreater(len(violations), 0)

    def test_4px_base_allowed(self):
        html = '<div style="margin: 4px;">Fine</div>'
        violations = lint_spacing(html)
        self.assertEqual(violations, [])

    def test_zero_allowed(self):
        html = '<div style="padding: 0px;">Zero</div>'
        violations = lint_spacing(html)
        self.assertEqual(violations, [])

    def test_1px_border_allowed(self):
        """1px borders are common and should not trigger spacing violations."""
        html = '<div style="border: 1px solid #e5e7eb;">OK</div>'
        violations = lint_spacing(html)
        self.assertEqual(violations, [])

    def test_2px_allowed(self):
        html = '<div style="border-width: 2px;">OK</div>'
        violations = lint_spacing(html)
        self.assertEqual(violations, [])


class TestLintAntiSlop(unittest.TestCase):

    def test_purple_primary_detected(self):
        html = '<div style="background: #6c5ce7;">Purple slop</div>'
        violations = lint_anti_slop(html)
        self.assertGreater(len(violations), 0)

    def test_indigo_detected(self):
        html = '<div style="color: #4f46e5;">Indigo slop</div>'
        violations = lint_anti_slop(html)
        self.assertGreater(len(violations), 0)

    def test_tailwind_class_detected(self):
        html = '<div class="bg-indigo-600 text-gray-500">Tailwind defaults</div>'
        violations = lint_anti_slop(html)
        self.assertGreater(len(violations), 0)

    def test_rounded_full_detected(self):
        html = '<div class="rounded-full">Pill shape</div>'
        violations = lint_anti_slop(html)
        self.assertGreater(len(violations), 0)

    def test_clean_html_passes(self):
        html = '<div style="color: #1a1a2e; border-radius: 4px;">Clean</div>'
        violations = lint_anti_slop(html)
        self.assertEqual(violations, [])

    def test_series_violet_not_flagged_as_slop(self):
        """Series 6 violet (#8b5cf6) is approved, shouldn't trigger anti-slop."""
        svg = '<rect fill="#8b5cf6" />'
        violations = lint_anti_slop(svg)
        self.assertEqual(violations, [])


class TestLintAll(unittest.TestCase):

    def test_clean_returns_pass(self):
        html = '<div style="color: #1a1a2e; font-family: Source Sans 3; padding: 8px;">OK</div>'
        result = lint_all(html)
        self.assertTrue(result["passed"])
        self.assertEqual(result["violation_count"], 0)

    def test_dirty_returns_fail(self):
        html = '<div style="color: #ff00ff; font-family: Comic Sans MS; padding: 13px;" class="bg-indigo-600">Bad</div>'
        result = lint_all(html)
        self.assertFalse(result["passed"])
        self.assertGreater(result["violation_count"], 0)

    def test_result_has_categories(self):
        html = '<div>anything</div>'
        result = lint_all(html)
        self.assertIn("violations", result)
        self.assertIn("passed", result)
        self.assertIn("violation_count", result)

    def test_violations_have_required_fields(self):
        html = '<div style="color: #ff00ff;">Bad</div>'
        result = lint_all(html)
        for v in result["violations"]:
            self.assertIsInstance(v, dict)
            self.assertIn("category", v)
            self.assertIn("severity", v)
            self.assertIn("detail", v)

    def test_empty_input(self):
        result = lint_all("")
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()
