#!/usr/bin/env python3
"""Tests for design_tokens.py — MT-32 Phase 6: canonical design token module.

TDD: Tests written BEFORE implementation (S230).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import design_tokens


class TestColorTokens(unittest.TestCase):
    """Verify canonical CCA color palette."""

    def test_palette_has_required_keys(self):
        required = {"primary", "accent", "highlight", "success", "warning",
                     "muted", "bg", "surface", "border"}
        self.assertTrue(required.issubset(set(design_tokens.CCA_PALETTE.keys())))

    def test_palette_values_are_hex(self):
        import re
        hex_re = re.compile(r'^#[0-9a-fA-F]{6}$')
        for name, val in design_tokens.CCA_PALETTE.items():
            self.assertRegex(val, hex_re, f"{name} is not valid hex: {val}")

    def test_series_colors_length(self):
        self.assertEqual(len(design_tokens.SERIES_COLORS), 8)

    def test_dark_palette_keys(self):
        required = {"dark_bg", "dark_text", "dark_surface", "dark_border"}
        self.assertTrue(required.issubset(set(design_tokens.DARK_PALETTE.keys())))

    def test_all_approved_includes_palette_and_series(self):
        for color in design_tokens.CCA_PALETTE.values():
            self.assertIn(color.lower(), {c.lower() for c in design_tokens.ALL_APPROVED_COLORS})
        for color in design_tokens.SERIES_COLORS:
            self.assertIn(color.lower(), {c.lower() for c in design_tokens.ALL_APPROVED_COLORS})


class TestFontTokens(unittest.TestCase):
    """Verify approved font families."""

    def test_source_sans_in_approved(self):
        self.assertIn("source sans 3", design_tokens.APPROVED_FONTS)

    def test_source_code_pro_in_approved(self):
        self.assertIn("source code pro", design_tokens.APPROVED_FONTS)

    def test_fallbacks_in_approved(self):
        for font in ["helvetica neue", "arial", "sans-serif"]:
            self.assertIn(font, design_tokens.APPROVED_FONTS)


class TestSpacingTokens(unittest.TestCase):
    """Verify spacing scale."""

    def test_base_grid_values(self):
        for val in [0, 4, 8, 16, 24, 32, 48, 64]:
            self.assertIn(val, design_tokens.VALID_SPACING)

    def test_no_odd_values(self):
        for val in design_tokens.VALID_SPACING:
            if val > 3:
                self.assertEqual(val % 2, 0, f"{val}px is odd — not on the grid")


class TestTypographyTokens(unittest.TestCase):
    """Verify typography scale."""

    def test_has_required_roles(self):
        required = {"display", "h1", "h2", "h3", "body", "caption", "metric", "code"}
        self.assertTrue(required.issubset(set(design_tokens.TYPOGRAPHY.keys())))

    def test_sizes_descend(self):
        t = design_tokens.TYPOGRAPHY
        self.assertGreater(t["display"]["size_pt"], t["h1"]["size_pt"])
        self.assertGreater(t["h1"]["size_pt"], t["h2"]["size_pt"])
        self.assertGreater(t["h2"]["size_pt"], t["body"]["size_pt"])

    def test_each_has_required_fields(self):
        for role, spec in design_tokens.TYPOGRAPHY.items():
            self.assertIn("size_pt", spec, f"{role} missing size_pt")
            self.assertIn("weight", spec, f"{role} missing weight")
            self.assertIn("line_height", spec, f"{role} missing line_height")


class TestAntiSlopColors(unittest.TestCase):
    """Verify anti-slop detection list."""

    def test_anti_slop_has_purples(self):
        has_purple = any("#6c5ce7" in c.lower() or "#4f46e5" in c.lower()
                         for c in design_tokens.ANTI_SLOP_COLORS)
        self.assertTrue(has_purple, "Anti-slop list should include common AI purples")

    def test_series_6_not_in_anti_slop(self):
        self.assertNotIn("#8b5cf6", design_tokens.ANTI_SLOP_COLORS,
                         "Series 6 violet is approved — should not be in anti-slop")


class TestCSSExport(unittest.TestCase):
    """Test CSS custom property export."""

    def test_generates_css_vars(self):
        css = design_tokens.to_css_vars()
        self.assertIn("--cca-primary:", css)
        self.assertIn("--cca-accent:", css)
        self.assertIn("#1a1a2e", css)

    def test_includes_spacing(self):
        css = design_tokens.to_css_vars()
        self.assertIn("--space-sm:", css)
        self.assertIn("--space-lg:", css)

    def test_includes_typography(self):
        css = design_tokens.to_css_vars()
        self.assertIn("--type-body", css)

    def test_wraps_in_root(self):
        css = design_tokens.to_css_vars()
        self.assertIn(":root", css)


class TestTypstExport(unittest.TestCase):
    """Test Typst variable export."""

    def test_generates_typst_vars(self):
        typst = design_tokens.to_typst_vars()
        self.assertIn("#let cca-primary", typst)
        self.assertIn('rgb("#1a1a2e")', typst)

    def test_includes_spacing(self):
        typst = design_tokens.to_typst_vars()
        self.assertIn("space-sm", typst)

    def test_includes_font(self):
        typst = design_tokens.to_typst_vars()
        self.assertIn("Source Sans 3", typst)


class TestPythonExport(unittest.TestCase):
    """Test Python dict export for use in generators."""

    def test_returns_dict(self):
        tokens = design_tokens.to_python_dict()
        self.assertIsInstance(tokens, dict)

    def test_has_all_sections(self):
        tokens = design_tokens.to_python_dict()
        self.assertIn("colors", tokens)
        self.assertIn("spacing", tokens)
        self.assertIn("typography", tokens)
        self.assertIn("fonts", tokens)

    def test_colors_includes_palette_and_series(self):
        tokens = design_tokens.to_python_dict()
        self.assertIn("primary", tokens["colors"])
        self.assertIn("series", tokens["colors"])


if __name__ == "__main__":
    unittest.main()
