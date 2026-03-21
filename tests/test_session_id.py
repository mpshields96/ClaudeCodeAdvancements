#!/usr/bin/env python3
"""Tests for session_id.py — MT-20 Gap 3: Session ID normalization.

Canonical format: "S{number}" string (e.g., "S99", "S100").
All modules should use this format for cross-module correlation.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from session_id import normalize, validate, extract_number, SessionIdError


class TestNormalize(unittest.TestCase):
    """Test session ID normalization to canonical 'S{number}' format."""

    def test_int_input(self):
        self.assertEqual(normalize(99), "S99")

    def test_int_zero(self):
        self.assertEqual(normalize(0), "S0")

    def test_int_large(self):
        self.assertEqual(normalize(1000), "S1000")

    def test_string_with_prefix(self):
        self.assertEqual(normalize("S99"), "S99")

    def test_string_lowercase_prefix(self):
        self.assertEqual(normalize("s99"), "S99")

    def test_string_bare_number(self):
        self.assertEqual(normalize("99"), "S99")

    def test_string_with_suffix(self):
        # "S99a" -> "S99" (strip letter suffixes for normalization)
        self.assertEqual(normalize("S99a"), "S99")

    def test_string_with_suffix_b(self):
        self.assertEqual(normalize("S99b"), "S99")

    def test_none_raises(self):
        with self.assertRaises(SessionIdError):
            normalize(None)

    def test_empty_string_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("")

    def test_non_numeric_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("abc")

    def test_negative_raises(self):
        with self.assertRaises(SessionIdError):
            normalize(-1)

    def test_float_truncates(self):
        self.assertEqual(normalize(99.5), "S99")

    def test_whitespace_stripped(self):
        self.assertEqual(normalize("  S99  "), "S99")


class TestValidate(unittest.TestCase):
    """Test session ID validation."""

    def test_valid_canonical(self):
        self.assertTrue(validate("S99"))

    def test_valid_large(self):
        self.assertTrue(validate("S1000"))

    def test_valid_zero(self):
        self.assertTrue(validate("S0"))

    def test_invalid_no_prefix(self):
        self.assertFalse(validate("99"))

    def test_invalid_lowercase(self):
        self.assertFalse(validate("s99"))

    def test_invalid_suffix(self):
        self.assertFalse(validate("S99a"))

    def test_invalid_empty(self):
        self.assertFalse(validate(""))

    def test_invalid_none(self):
        self.assertFalse(validate(None))

    def test_invalid_int(self):
        self.assertFalse(validate(99))

    def test_invalid_just_s(self):
        self.assertFalse(validate("S"))


class TestExtractNumber(unittest.TestCase):
    """Test extracting the integer from a session ID."""

    def test_canonical(self):
        self.assertEqual(extract_number("S99"), 99)

    def test_int_passthrough(self):
        self.assertEqual(extract_number(99), 99)

    def test_string_number(self):
        self.assertEqual(extract_number("99"), 99)

    def test_with_suffix(self):
        self.assertEqual(extract_number("S99a"), 99)

    def test_lowercase(self):
        self.assertEqual(extract_number("s100"), 100)

    def test_none_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number(None)

    def test_non_numeric_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number("hello")

    def test_zero(self):
        self.assertEqual(extract_number("S0"), 0)


if __name__ == "__main__":
    unittest.main()
