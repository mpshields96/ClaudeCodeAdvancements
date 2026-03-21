#!/usr/bin/env python3
"""
Tests for generate_report_pdf.py — Apple-style PDF builder.

Testable surface (no real file I/O required for most):
  - san(): Unicode sanitization for latin-1 output
  - ApplePDF: FPDF subclass instantiation + primitive methods (render to BytesIO)
  - build_pdf(): text parsing logic via a temp input file
  - Line classification regexes (section, subsection, bullet, kv, mono, body)
"""

import io
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_report_pdf import ApplePDF, san, build_pdf


# ---------------------------------------------------------------------------
# san() — Unicode sanitization
# ---------------------------------------------------------------------------


class TestSan(unittest.TestCase):
    """san() replaces smart punctuation and encodes to latin-1."""

    def test_em_dash_replaced(self):
        self.assertEqual(san('\u2014'), ' -- ')

    def test_en_dash_replaced(self):
        self.assertEqual(san('\u2013'), '-')

    def test_left_single_quote_replaced(self):
        self.assertEqual(san('\u2018'), "'")

    def test_right_single_quote_replaced(self):
        self.assertEqual(san('\u2019'), "'")

    def test_left_double_quote_replaced(self):
        self.assertEqual(san('\u201c'), '"')

    def test_right_double_quote_replaced(self):
        self.assertEqual(san('\u201d'), '"')

    def test_bullet_replaced(self):
        self.assertEqual(san('\u2022'), '-')

    def test_ellipsis_replaced(self):
        self.assertEqual(san('\u2026'), '...')

    def test_arrow_replaced(self):
        self.assertEqual(san('\u2192'), '->')

    def test_nbsp_replaced(self):
        self.assertEqual(san('\u00a0'), ' ')

    def test_non_breaking_hyphen_replaced(self):
        self.assertEqual(san('\u2011'), '-')

    def test_minus_sign_replaced(self):
        self.assertEqual(san('\u2212'), '-')

    def test_plain_ascii_unchanged(self):
        self.assertEqual(san('hello world'), 'hello world')

    def test_empty_string(self):
        self.assertEqual(san(''), '')

    def test_multiple_replacements_in_one_string(self):
        result = san('\u2018hello\u2019 \u2014 world')
        # \u2014 -> ' -- ' (with surrounding spaces), \u2018/\u2019 -> '
        # Input space + ' -- ' = two spaces before '--'
        self.assertEqual(result, "'hello'  --  world")

    def test_latin1_unencodable_chars_replaced(self):
        """Characters outside latin-1 that aren't in our map become '?'."""
        result = san('\u4e2d\u6587')  # Chinese chars
        self.assertNotIn('\u4e2d', result)

    def test_result_is_string(self):
        self.assertIsInstance(san('test'), str)


# ---------------------------------------------------------------------------
# ApplePDF — class-level and primitive method smoke tests
# ---------------------------------------------------------------------------


class TestApplePDFInit(unittest.TestCase):
    """ApplePDF can be instantiated without crashing."""

    def test_instantiation(self):
        pdf = ApplePDF()
        self.assertIsNotNone(pdf)

    def test_is_fpdf_subclass(self):
        from fpdf import FPDF
        pdf = ApplePDF()
        self.assertIsInstance(pdf, FPDF)


class TestApplePDFPrimitives(unittest.TestCase):
    """Primitive rendering methods execute without raising exceptions."""

    def setUp(self):
        self.pdf = ApplePDF()
        self.pdf.add_page()

    def test_body_renders(self):
        self.pdf.body("This is a body paragraph.")

    def test_body_with_unicode(self):
        """Body with smart quotes should not crash (san() handles them)."""
        self.pdf.body("He said \u2018hello\u2019 \u2014 and smiled.")

    def test_mono_renders(self):
        self.pdf.mono("def foo():\n    return 42")

    def test_mono_empty_string(self):
        self.pdf.mono("")

    def test_bullet_renders(self):
        self.pdf.bullet("An important point here")

    def test_bullet_with_unicode(self):
        self.pdf.bullet("Point with arrow \u2192 next step")

    def test_kv_renders(self):
        self.pdf.kv("Module", "memory-system")

    def test_kv_with_highlight(self):
        self.pdf.kv("Status", "COMPLETE", highlight=True)

    def test_kv_long_value(self):
        """Long values trigger multi_cell path in kv()."""
        self.pdf.kv("Key", "A" * 200)

    def test_section_renders(self):
        self.pdf.section(1, "Executive Summary")

    def test_subsection_renders(self):
        self.pdf.subsection("Memory System")

    def test_toc_renders(self):
        items = ["Executive Summary", "Module Deep-Dive", "Next Steps"]
        self.pdf.toc(items)

    def test_cover_renders(self):
        """cover() adds a page — call on fresh PDF."""
        pdf = ApplePDF()
        pdf.cover()
        self.assertGreater(pdf.page, 0)

    def test_closing_page_renders(self):
        self.pdf.closing_page()


class TestApplePDFOutput(unittest.TestCase):
    """ApplePDF generates valid PDF bytes via output()."""

    def test_output_produces_bytes(self):
        pdf = ApplePDF()
        pdf.add_page()
        pdf.body("Hello PDF")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            fname = f.name
        try:
            pdf.output(fname)
            with open(fname, 'rb') as fh:
                data = fh.read()
            self.assertTrue(data.startswith(b'%PDF'))
        finally:
            os.unlink(fname)


# ---------------------------------------------------------------------------
# build_pdf() — integration: parses text, generates PDF file
# ---------------------------------------------------------------------------


MINIMAL_REPORT = """\
ClaudeCodeAdvancements Status Report
=====================================

1. EXECUTIVE SUMMARY
Some body text here. This is a paragraph.

2. MODULE STATS
------------------
Memory System
------------------
  Module           memory-system
  Status           COMPLETE
  - Tests pass
  - All hooks wired

    deeply indented code line
    another code line

3. NEXT STEPS
More body text.
"""


class TestBuildPdf(unittest.TestCase):
    """build_pdf() parses input text and writes a valid PDF."""

    def test_produces_pdf_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tf:
            tf.write(MINIMAL_REPORT)
            txt_path = tf.name
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as of:
            out_path = of.name
        try:
            result = build_pdf(txt_path, out_path)
            self.assertEqual(result, out_path)
            with open(out_path, 'rb') as fh:
                data = fh.read()
            self.assertTrue(data.startswith(b'%PDF'))
        finally:
            os.unlink(txt_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_returns_output_path(self):
        """build_pdf returns the output path string."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tf:
            tf.write(MINIMAL_REPORT)
            txt_path = tf.name
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as of:
            out_path = of.name
        try:
            result = build_pdf(txt_path, out_path)
            self.assertIsInstance(result, str)
            self.assertTrue(result.endswith('.pdf'))
        finally:
            os.unlink(txt_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_handles_empty_content(self):
        """build_pdf with an empty file should not crash."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tf:
            tf.write("")
            txt_path = tf.name
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as of:
            out_path = of.name
        try:
            build_pdf(txt_path, out_path)
            self.assertTrue(os.path.exists(out_path))
        finally:
            os.unlink(txt_path)
            if os.path.exists(out_path):
                os.unlink(out_path)

    def test_handles_unicode_content(self):
        """build_pdf with smart quotes in input does not crash."""
        content = "1. SUMMARY\nHe said \u2018hello\u2019 \u2014 world.\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tf:
            tf.write(content)
            txt_path = tf.name
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as of:
            out_path = of.name
        try:
            build_pdf(txt_path, out_path)
            with open(out_path, 'rb') as fh:
                data = fh.read()
            self.assertTrue(data.startswith(b'%PDF'))
        finally:
            os.unlink(txt_path)
            if os.path.exists(out_path):
                os.unlink(out_path)


# ---------------------------------------------------------------------------
# Line classification regexes — unit test the patterns used in build_pdf()
# ---------------------------------------------------------------------------


class TestLineClassificationPatterns(unittest.TestCase):
    """The regex patterns in build_pdf() correctly classify line types."""

    def test_section_header_pattern(self):
        """Lines like '1. EXECUTIVE SUMMARY' match section header regex."""
        pattern = re.compile(r'^(\d+)\.\s+(.+)$')
        m = pattern.match('1. EXECUTIVE SUMMARY')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), '1')
        self.assertEqual(m.group(2), 'EXECUTIVE SUMMARY')

    def test_section_header_double_digit(self):
        m = re.match(r'^(\d+)\.\s+(.+)$', '15. FINAL SECTION')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), '15')

    def test_equals_separator_pattern(self):
        """20+ equals signs are recognized as decorative separators."""
        self.assertIsNotNone(re.match(r'^={20,}$', '=' * 25))
        self.assertIsNone(re.match(r'^={20,}$', '=' * 10))

    def test_dash_separator_pattern(self):
        """10+ dashes are recognized as subsection borders."""
        self.assertIsNotNone(re.match(r'^-{10,}$', '-' * 20))
        self.assertIsNone(re.match(r'^-{10,}$', '---'))

    def test_titled_dash_header_pattern(self):
        """Lines like '---- COMPLETED (6/17) ----' match the titled pattern."""
        pattern = re.compile(r'^-{5,}\s+(.+?)\s+-{5,}$')
        m = pattern.match('---------- COMPLETED (6/17) ----------')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), 'COMPLETED (6/17)')

    def test_bullet_pattern(self):
        """'  - item text' matches bullet pattern."""
        pattern = re.compile(r'^\s{2,}-\s+(.+)$')
        m = pattern.match('  - This is a bullet point')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), 'This is a bullet point')

    def test_bullet_not_dashes(self):
        """Long dash lines don't match as bullets."""
        pattern = re.compile(r'^\s{2,}-\s+(.+)$')
        self.assertIsNone(pattern.match('  ----------'))

    def test_kv_label_value_pattern(self):
        """'  Label: Value' matches label-value pattern."""
        pattern = re.compile(r'^\s{2}(\w[\w\s]*?):\s+(.+)$')
        m = pattern.match('  Module: memory-system')
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), 'Module')
        self.assertEqual(m.group(2), 'memory-system')

    def test_deeply_indented_line(self):
        """4+ spaces of indent marks a mono block line."""
        self.assertIsNotNone(re.match(r'^\s{4,}\S', '    code_here'))
        self.assertIsNone(re.match(r'^\s{4,}\S', '  normal indent'))

    def test_kv_aligned_pattern(self):
        """Lines with 3+ spaces between key and value match kv-aligned regex."""
        pattern = re.compile(r'^\s{2,}\S.*\s{3,}\S')
        self.assertIsNotNone(pattern.match('  Tests Passing        1,525'))
        self.assertIsNone(pattern.match('  short  x'))

    def test_table_separator_pattern(self):
        """Table separator lines with +----- are recognized."""
        line = '+------+------+'
        self.assertTrue(bool(re.match(r'^.*[-+]{5,}.*$', line) and ('+-' in line or '-+' in line)))


if __name__ == '__main__':
    unittest.main()
