#!/usr/bin/env python3
"""Tests for fp_filter.py — MT-20 Senior Dev Agent: false positive filter.

FPFilter reduces noise from SATD and effort scoring by:
- Identifying test files (test_*.py, *_test.py, tests/ dir) — lower priority
- Identifying vendored files (vendor/, node_modules/, .venv/) — skip
- Scoring confidence that a finding is NOT a false positive (0.0-1.0)
- Filtering a list of findings to only high-confidence ones

Tests cover:
- Test file detection
- Vendored file detection
- Confidence scoring rules
- Filter with threshold
- Edge cases (no path, empty path, no findings)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fp_filter import FPFilter


class TestTestFileDetection(unittest.TestCase):
    """Test detection of test files."""

    def setUp(self):
        self.f = FPFilter()

    def test_test_prefix_detected(self):
        self.assertTrue(self.f.is_test_file("test_utils.py"))

    def test_test_suffix_detected(self):
        self.assertTrue(self.f.is_test_file("utils_test.py"))

    def test_tests_directory_detected(self):
        self.assertTrue(self.f.is_test_file("tests/test_utils.py"))
        self.assertTrue(self.f.is_test_file("mymodule/tests/something.py"))

    def test_tests_directory_nested(self):
        self.assertTrue(self.f.is_test_file("agent-guard/tests/test_foo.py"))

    def test_dunder_tests_directory(self):
        self.assertTrue(self.f.is_test_file("__tests__/utils.test.js"))

    def test_spec_file_detected(self):
        self.assertTrue(self.f.is_test_file("utils.spec.ts"))
        self.assertTrue(self.f.is_test_file("utils.test.js"))

    def test_normal_file_not_test(self):
        self.assertFalse(self.f.is_test_file("utils.py"))
        self.assertFalse(self.f.is_test_file("mymodule.py"))
        self.assertFalse(self.f.is_test_file("testing_framework.py"))  # "testing" but not a test file

    def test_empty_path_not_test(self):
        self.assertFalse(self.f.is_test_file(""))

    def test_none_like_not_test(self):
        self.assertFalse(self.f.is_test_file(None))


class TestVendoredFileDetection(unittest.TestCase):
    """Test detection of vendored/third-party files."""

    def setUp(self):
        self.f = FPFilter()

    def test_vendor_directory(self):
        self.assertTrue(self.f.is_vendored("vendor/lodash.js"))
        self.assertTrue(self.f.is_vendored("src/vendor/utils.py"))

    def test_node_modules(self):
        self.assertTrue(self.f.is_vendored("node_modules/lodash/index.js"))

    def test_venv(self):
        self.assertTrue(self.f.is_vendored(".venv/lib/python3.10/site-packages/foo.py"))
        self.assertTrue(self.f.is_vendored("venv/lib/foo.py"))

    def test_site_packages(self):
        self.assertTrue(self.f.is_vendored("site-packages/requests/api.py"))

    def test_third_party(self):
        self.assertTrue(self.f.is_vendored("third_party/protobuf/descriptor.py"))

    def test_generated_pb(self):
        self.assertTrue(self.f.is_vendored("proto/generated/foo_pb2.py"))

    def test_normal_file_not_vendored(self):
        self.assertFalse(self.f.is_vendored("src/utils.py"))
        self.assertFalse(self.f.is_vendored("mymodule.py"))

    def test_empty_path_not_vendored(self):
        self.assertFalse(self.f.is_vendored(""))


class TestShouldSkip(unittest.TestCase):
    """Test should_skip — combined skip decision."""

    def setUp(self):
        self.f = FPFilter()

    def test_vendored_should_skip(self):
        self.assertTrue(self.f.should_skip("vendor/utils.py"))
        self.assertTrue(self.f.should_skip("node_modules/lodash.js"))

    def test_test_file_not_skipped(self):
        # Test files are filtered, not skipped — they still produce findings at lower confidence
        self.assertFalse(self.f.should_skip("test_utils.py"))

    def test_normal_file_not_skipped(self):
        self.assertFalse(self.f.should_skip("src/utils.py"))

    def test_no_path_not_skipped(self):
        self.assertFalse(self.f.should_skip(""))


class TestConfidenceScoring(unittest.TestCase):
    """Test confidence scoring — how likely is a finding to be real (not FP)?"""

    def setUp(self):
        self.f = FPFilter()

    def test_normal_file_full_confidence(self):
        c = self.f.confidence("src/utils.py", "TODO: fix this edge case with None values")
        self.assertEqual(c, 1.0)

    def test_test_file_reduced_confidence(self):
        c = self.f.confidence("tests/test_utils.py", "TODO: fix this edge case")
        self.assertLess(c, 1.0)
        self.assertGreater(c, 0.0)

    def test_vendored_file_zero_confidence(self):
        c = self.f.confidence("vendor/lodash.js", "TODO: upstream fix needed")
        self.assertEqual(c, 0.0)

    def test_no_path_full_confidence(self):
        c = self.f.confidence("", "TODO: fix this")
        self.assertEqual(c, 1.0)

    def test_high_confidence_for_fixme(self):
        c = self.f.confidence("src/auth.py", "FIXME: security issue here")
        self.assertEqual(c, 1.0)

    def test_confidence_in_range(self):
        for path in ["src/foo.py", "test_bar.py", "vendor/baz.py", ""]:
            c = self.f.confidence(path, "TODO: something")
            self.assertGreaterEqual(c, 0.0)
            self.assertLessEqual(c, 1.0)


class TestFilterFindings(unittest.TestCase):
    """Test filter_findings — apply FP filter to a list of findings."""

    def setUp(self):
        self.f = FPFilter()

    def test_empty_findings_returns_empty(self):
        result = self.f.filter_findings([], "src/utils.py")
        self.assertEqual(result, [])

    def test_normal_file_passes_all(self):
        findings = [
            {"severity": "HIGH", "message": "FIXME: broken"},
            {"severity": "MEDIUM", "message": "TODO: refactor"},
        ]
        result = self.f.filter_findings(findings, "src/utils.py")
        self.assertEqual(len(result), 2)

    def test_vendored_file_returns_empty(self):
        findings = [{"severity": "HIGH", "message": "FIXME: something"}]
        result = self.f.filter_findings(findings, "vendor/lodash.js")
        self.assertEqual(result, [])

    def test_test_file_passes_high_severity(self):
        findings = [
            {"severity": "HIGH", "message": "FIXME: actual bug"},
            {"severity": "LOW", "message": "NOTE: style thing"},
        ]
        result = self.f.filter_findings(findings, "tests/test_utils.py")
        # HIGH should still pass for test files, LOW might be filtered
        high = [r for r in result if r["severity"] == "HIGH"]
        self.assertGreater(len(high), 0)

    def test_no_path_passes_all(self):
        findings = [{"severity": "MEDIUM", "message": "TODO: something"}]
        result = self.f.filter_findings(findings, "")
        self.assertEqual(len(result), 1)

    def test_findings_unchanged_for_normal_file(self):
        findings = [{"severity": "HIGH", "message": "FIXME: broken", "extra": 42}]
        result = self.f.filter_findings(findings, "src/module.py")
        self.assertEqual(result[0]["extra"], 42)

    def test_returns_list(self):
        result = self.f.filter_findings([], "")
        self.assertIsInstance(result, list)


class TestFPFilterEdgeCases(unittest.TestCase):
    """Test edge cases."""

    def setUp(self):
        self.f = FPFilter()

    def test_deeply_nested_test_file(self):
        self.assertTrue(self.f.is_test_file("a/b/c/d/tests/test_something.py"))

    def test_deeply_nested_vendor_file(self):
        self.assertTrue(self.f.is_vendored("a/b/node_modules/lodash.js"))

    def test_path_with_spaces(self):
        self.assertFalse(self.f.is_test_file("my module/utils.py"))
        self.assertFalse(self.f.is_vendored("my module/utils.py"))

    def test_windows_style_path(self):
        # Should handle forward slashes
        self.assertTrue(self.f.is_test_file("tests/test_foo.py"))

    def test_javascript_test_file(self):
        self.assertTrue(self.f.is_test_file("src/utils.test.js"))
        self.assertTrue(self.f.is_test_file("src/utils.spec.js"))

    def test_go_test_file(self):
        self.assertTrue(self.f.is_test_file("pkg/utils_test.go"))


if __name__ == "__main__":
    unittest.main()
