#!/usr/bin/env python3
"""Extended tests for session_id.py — MT-20 Gap 3: Session ID normalization.

Covers edge cases not in the base test suite:
- None and empty string inputs
- Unicode and special characters
- Numeric overflow (very large session numbers)
- Bulk normalization roundtrips
- extract_number with malformed inputs
- Boundary values at format transitions
- Float edge cases
- Whitespace variants
- Mixed-case prefix handling
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from session_id import normalize, validate, extract_number, SessionIdError


# ===== Extended Normalize Tests =====

class TestNormalizeEdgeCases(unittest.TestCase):
    """Edge cases for normalize()."""

    def test_none_raises(self):
        with self.assertRaises(SessionIdError):
            normalize(None)

    def test_none_raises_with_message(self):
        with self.assertRaises(SessionIdError) as ctx:
            normalize(None)
        self.assertIn("None", str(ctx.exception))

    def test_empty_string_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("   ")

    def test_tab_whitespace_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("\t")

    def test_newline_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("\n")

    def test_unicode_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("S①②")

    def test_unicode_digit_behavior(self):
        # Python's re \d matches Unicode digits (Arabic-Indic etc.)
        # and int() can parse them. Document that this either succeeds or raises.
        try:
            result = normalize("S\u0661\u0662\u0663")  # Arabic-Indic 1,2,3
            # If it parses, it should start with "S"
            self.assertTrue(result.startswith("S"))
        except SessionIdError:
            pass  # Also acceptable — implementation choice

    def test_emoji_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("S🔥")

    def test_special_chars_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("S99!")

    def test_double_s_raises(self):
        with self.assertRaises(SessionIdError):
            normalize("SS99")

    def test_list_raises(self):
        with self.assertRaises(SessionIdError):
            normalize([99])

    def test_dict_raises(self):
        with self.assertRaises(SessionIdError):
            normalize({"session": 99})

    def test_bool_true_behavior(self):
        # bool is a subclass of int in Python — isinstance(True, int) is True
        # The code does f"S{value}" where value=True, so it returns "STrue"
        # This documents actual behavior (not necessarily ideal)
        result = normalize(True)
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("S"))

    def test_bool_false_behavior(self):
        # Similar to True — isinstance(False, int) is True, f"S{False}" = "SFalse"
        result = normalize(False)
        self.assertIsInstance(result, str)
        self.assertTrue(result.startswith("S"))


class TestNormalizeNumericOverflow(unittest.TestCase):
    """Test very large session numbers."""

    def test_very_large_int(self):
        result = normalize(999999)
        self.assertEqual(result, "S999999")

    def test_million(self):
        result = normalize(1_000_000)
        self.assertEqual(result, "S1000000")

    def test_very_large_string(self):
        result = normalize("S999999")
        self.assertEqual(result, "S999999")

    def test_large_bare_number(self):
        result = normalize("999999")
        self.assertEqual(result, "S999999")

    def test_large_with_suffix(self):
        result = normalize("S999a")
        self.assertEqual(result, "S999")

    def test_zero_int(self):
        result = normalize(0)
        self.assertEqual(result, "S0")

    def test_one(self):
        result = normalize(1)
        self.assertEqual(result, "S1")

    def test_negative_int_raises(self):
        with self.assertRaises(SessionIdError):
            normalize(-1)

    def test_large_negative_raises(self):
        with self.assertRaises(SessionIdError):
            normalize(-999)


class TestNormalizeFloatEdgeCases(unittest.TestCase):
    """Float handling edge cases."""

    def test_float_truncates_down(self):
        self.assertEqual(normalize(99.9), "S99")

    def test_float_zero(self):
        self.assertEqual(normalize(0.7), "S0")

    def test_float_exact(self):
        self.assertEqual(normalize(50.0), "S50")

    def test_float_negative_raises(self):
        with self.assertRaises(SessionIdError):
            normalize(-1.5)


class TestNormalizeWhitespace(unittest.TestCase):
    """Whitespace stripping edge cases."""

    def test_leading_spaces(self):
        self.assertEqual(normalize("   S99"), "S99")

    def test_trailing_spaces(self):
        self.assertEqual(normalize("S99   "), "S99")

    def test_leading_and_trailing(self):
        self.assertEqual(normalize("  99  "), "S99")

    def test_tabs_stripped(self):
        self.assertEqual(normalize("\tS99\t"), "S99")


class TestNormalizeBulkRoundtrip(unittest.TestCase):
    """Bulk normalization roundtrips — canonical form survives normalize twice."""

    def test_already_canonical_is_idempotent(self):
        """normalize(normalize(x)) == normalize(x)"""
        for raw in [99, "S99", "s99", "99", "S99a", "  S99  "]:
            first = normalize(raw)
            second = normalize(first)
            self.assertEqual(first, second, f"Failed idempotency for {raw!r}")

    def test_bulk_ints(self):
        expected = [f"S{n}" for n in range(0, 20)]
        result = [normalize(n) for n in range(0, 20)]
        self.assertEqual(result, expected)

    def test_bulk_string_bare(self):
        for n in [0, 1, 50, 100, 500]:
            self.assertEqual(normalize(str(n)), f"S{n}")

    def test_bulk_prefixed_strings(self):
        for n in [1, 10, 100]:
            self.assertEqual(normalize(f"S{n}"), f"S{n}")
            self.assertEqual(normalize(f"s{n}"), f"S{n}")


# ===== Extended Validate Tests =====

class TestValidateEdgeCases(unittest.TestCase):
    """Edge cases for validate()."""

    def test_none_is_false(self):
        self.assertFalse(validate(None))

    def test_empty_string_false(self):
        self.assertFalse(validate(""))

    def test_whitespace_false(self):
        self.assertFalse(validate("  "))

    def test_s_only_false(self):
        self.assertFalse(validate("S"))

    def test_lowercase_s_false(self):
        self.assertFalse(validate("s99"))

    def test_with_suffix_false(self):
        self.assertFalse(validate("S99a"))

    def test_spaces_not_stripped(self):
        # validate() should NOT strip — canonical form is exact
        self.assertFalse(validate(" S99 "))

    def test_float_is_false(self):
        self.assertFalse(validate(99.0))

    def test_int_is_false(self):
        self.assertFalse(validate(99))

    def test_canonical_s0(self):
        self.assertTrue(validate("S0"))

    def test_canonical_large(self):
        self.assertTrue(validate("S999999"))

    def test_s_with_leading_zero(self):
        # "S099" — is this canonical? regex r"^S\d+$" would accept it
        self.assertTrue(validate("S099"))  # passes since it's S + digits

    def test_only_number_false(self):
        self.assertFalse(validate("99"))

    def test_dash_false(self):
        self.assertFalse(validate("S-99"))

    def test_dot_false(self):
        self.assertFalse(validate("S99.5"))


# ===== Extended ExtractNumber Tests =====

class TestExtractNumberEdgeCases(unittest.TestCase):
    """Edge cases for extract_number()."""

    def test_none_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number(None)

    def test_empty_string_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number("   ")

    def test_alpha_only_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number("hello")

    def test_special_chars_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number("S99!")

    def test_double_prefix_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number("SS99")

    def test_list_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number([99])

    def test_dict_raises(self):
        with self.assertRaises(SessionIdError):
            extract_number({"n": 99})

    def test_large_int_passthrough(self):
        self.assertEqual(extract_number(999999), 999999)

    def test_zero_int(self):
        self.assertEqual(extract_number(0), 0)

    def test_large_string(self):
        self.assertEqual(extract_number("S999999"), 999999)

    def test_leading_spaces_in_string(self):
        # Pattern match after strip
        result = extract_number("  S99  ")
        self.assertEqual(result, 99)

    def test_extract_from_bare_zero(self):
        self.assertEqual(extract_number("0"), 0)

    def test_extract_suffix_uppercase(self):
        self.assertEqual(extract_number("S100A"), 100)

    def test_extract_suffix_lowercase(self):
        self.assertEqual(extract_number("S100z"), 100)

    def test_roundtrip_with_normalize(self):
        """extract_number(normalize(x)) == extract_number(x) for valid inputs."""
        for raw in [99, "S99", "s99", "99", "S99a"]:
            self.assertEqual(
                extract_number(normalize(raw)),
                extract_number(raw) if not isinstance(raw, int) else raw
            )


class TestExtractNumberBoundaryValues(unittest.TestCase):
    """Boundary value tests for extract_number."""

    def test_session_1(self):
        self.assertEqual(extract_number("S1"), 1)

    def test_session_100(self):
        self.assertEqual(extract_number("S100"), 100)

    def test_session_0_from_string(self):
        self.assertEqual(extract_number("S0"), 0)

    def test_consecutive_sessions(self):
        for n in range(0, 10):
            self.assertEqual(extract_number(f"S{n}"), n)
            self.assertEqual(extract_number(f"s{n}"), n)
            self.assertEqual(extract_number(str(n)), n)


if __name__ == "__main__":
    unittest.main()
