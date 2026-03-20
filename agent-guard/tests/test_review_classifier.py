#!/usr/bin/env python3
"""Tests for review_classifier.py — MT-20 Senior Dev Agent: CRScore-style classifier.

ReviewClassifier maps SATD/finding text to review categories with priority scores.
Categories and scores from CRScore (NAACL 2025, arXiv:2409.19801):
  bugfix: 8.53, refactoring: 7.1, testing: 6.8, logging: 6.1,
  documentation: 5.9, style: 5.0

Tests cover:
- Category classification for each type
- Priority score for each category
- Default/fallback for unclassified text
- Sort order (highest priority first)
- Classify list of findings
- Edge cases (empty text, None-like)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from review_classifier import ReviewClassifier, ReviewCategory, CATEGORY_SCORES


class TestCategoryScores(unittest.TestCase):
    """Test that CATEGORY_SCORES constants match CRScore research values."""

    def test_bugfix_highest_priority(self):
        self.assertAlmostEqual(CATEGORY_SCORES["bugfix"], 8.53, places=1)

    def test_refactoring_score(self):
        self.assertAlmostEqual(CATEGORY_SCORES["refactoring"], 7.1, places=1)

    def test_testing_score(self):
        self.assertAlmostEqual(CATEGORY_SCORES["testing"], 6.8, places=1)

    def test_logging_score(self):
        self.assertAlmostEqual(CATEGORY_SCORES["logging"], 6.1, places=1)

    def test_documentation_score(self):
        self.assertAlmostEqual(CATEGORY_SCORES["documentation"], 5.9, places=1)

    def test_style_lowest_priority(self):
        self.assertAlmostEqual(CATEGORY_SCORES["style"], 5.0, places=1)

    def test_all_six_categories_present(self):
        expected = {"bugfix", "refactoring", "testing", "logging", "documentation", "style"}
        self.assertEqual(set(CATEGORY_SCORES.keys()), expected)

    def test_bugfix_greater_than_all_others(self):
        bugfix = CATEGORY_SCORES["bugfix"]
        for key, val in CATEGORY_SCORES.items():
            if key != "bugfix":
                self.assertGreater(bugfix, val)


class TestReviewCategory(unittest.TestCase):
    """Test ReviewCategory dataclass."""

    def test_fields(self):
        rc = ReviewCategory(name="bugfix", score=8.53)
        self.assertEqual(rc.name, "bugfix")
        self.assertAlmostEqual(rc.score, 8.53, places=2)

    def test_to_dict(self):
        rc = ReviewCategory(name="style", score=5.0)
        d = rc.to_dict()
        self.assertIn("name", d)
        self.assertIn("score", d)


class TestClassifyBugfix(unittest.TestCase):
    """Test that bugfix-related text maps to bugfix category."""

    def setUp(self):
        self.c = ReviewClassifier()

    def test_fix_keyword(self):
        result = self.c.classify("FIXME: this crashes when input is None")
        self.assertEqual(result.name, "bugfix")

    def test_bug_keyword(self):
        result = self.c.classify("TODO: fix this bug in the auth flow")
        self.assertEqual(result.name, "bugfix")

    def test_error_keyword(self):
        result = self.c.classify("HACK: error handling here is broken")
        self.assertEqual(result.name, "bugfix")

    def test_null_keyword(self):
        result = self.c.classify("TODO: handle null pointer exception here")
        self.assertEqual(result.name, "bugfix")

    def test_crash_keyword(self):
        result = self.c.classify("FIXME: this will crash on empty list")
        self.assertEqual(result.name, "bugfix")


class TestClassifyRefactoring(unittest.TestCase):
    """Test that refactoring text maps to refactoring category."""

    def setUp(self):
        self.c = ReviewClassifier()

    def test_refactor_keyword(self):
        result = self.c.classify("TODO: refactor this into smaller functions")
        self.assertEqual(result.name, "refactoring")

    def test_extract_keyword(self):
        result = self.c.classify("TODO: extract this logic into a helper")
        self.assertEqual(result.name, "refactoring")

    def test_simplify_keyword(self):
        result = self.c.classify("TODO: simplify this complex logic")
        self.assertEqual(result.name, "refactoring")

    def test_duplicate_keyword(self):
        result = self.c.classify("HACK: duplicate code, needs to be de-duped")
        self.assertEqual(result.name, "refactoring")


class TestClassifyTesting(unittest.TestCase):
    """Test that testing text maps to testing category."""

    def setUp(self):
        self.c = ReviewClassifier()

    def test_test_keyword(self):
        result = self.c.classify("TODO: add test for this edge case")
        self.assertEqual(result.name, "testing")

    def test_coverage_keyword(self):
        result = self.c.classify("TODO: add coverage for error paths")
        self.assertEqual(result.name, "testing")

    def test_mock_keyword(self):
        result = self.c.classify("TODO: mock the database call here")
        self.assertEqual(result.name, "testing")


class TestClassifyLogging(unittest.TestCase):
    """Test that logging text maps to logging category."""

    def setUp(self):
        self.c = ReviewClassifier()

    def test_log_keyword(self):
        result = self.c.classify("TODO: add logging for this operation")
        self.assertEqual(result.name, "logging")

    def test_debug_keyword(self):
        result = self.c.classify("TODO: add debug output here")
        self.assertEqual(result.name, "logging")


class TestClassifyDocumentation(unittest.TestCase):
    """Test that documentation text maps to documentation category."""

    def setUp(self):
        self.c = ReviewClassifier()

    def test_doc_keyword(self):
        result = self.c.classify("TODO: add docstring to this function")
        self.assertEqual(result.name, "documentation")

    def test_comment_keyword(self):
        result = self.c.classify("TODO: add comment explaining this algorithm")
        self.assertEqual(result.name, "documentation")

    def test_explain_keyword(self):
        result = self.c.classify("TODO: explain why this timeout is 30 seconds")
        self.assertEqual(result.name, "documentation")


class TestClassifyStyle(unittest.TestCase):
    """Test that style text maps to style category."""

    def setUp(self):
        self.c = ReviewClassifier()

    def test_style_keyword(self):
        result = self.c.classify("TODO: fix style here")
        self.assertEqual(result.name, "style")

    def test_format_keyword(self):
        result = self.c.classify("TODO: reformat this block")
        self.assertEqual(result.name, "style")

    def test_lint_keyword(self):
        result = self.c.classify("TODO: fix lint warnings")
        self.assertEqual(result.name, "style")


class TestClassifyFallback(unittest.TestCase):
    """Test fallback/default for unclassified text."""

    def setUp(self):
        self.c = ReviewClassifier()

    def test_unknown_text_returns_category(self):
        result = self.c.classify("TODO: something unclassifiable xyzzy123")
        self.assertIsInstance(result, ReviewCategory)
        self.assertIn(result.name, CATEGORY_SCORES)

    def test_empty_text_returns_category(self):
        result = self.c.classify("")
        self.assertIsInstance(result, ReviewCategory)

    def test_none_like_text_returns_category(self):
        result = self.c.classify(None)
        self.assertIsInstance(result, ReviewCategory)

    def test_all_results_have_valid_score(self):
        for text in ["TODO: fix bug", "TODO: add test", "TODO: xyzzy", ""]:
            result = self.c.classify(text)
            self.assertGreater(result.score, 0)


class TestClassifyFindings(unittest.TestCase):
    """Test classify_findings — classify a list of findings."""

    def setUp(self):
        self.c = ReviewClassifier()

    def test_empty_returns_empty(self):
        result = self.c.classify_findings([])
        self.assertEqual(result, [])

    def test_findings_sorted_by_score_descending(self):
        findings = [
            {"severity": "LOW", "message": "TODO: fix style"},
            {"severity": "HIGH", "message": "FIXME: crash on null"},
        ]
        result = self.c.classify_findings(findings)
        # bugfix (8.53) should come before style (5.0)
        self.assertGreaterEqual(result[0]["category_score"], result[-1]["category_score"])

    def test_finding_gets_category_field(self):
        findings = [{"severity": "HIGH", "message": "FIXME: crash"}]
        result = self.c.classify_findings(findings)
        self.assertIn("category", result[0])
        self.assertIn("category_score", result[0])

    def test_original_fields_preserved(self):
        findings = [{"severity": "HIGH", "message": "FIXME: crash", "source": "satd"}]
        result = self.c.classify_findings(findings)
        self.assertEqual(result[0]["source"], "satd")
        self.assertEqual(result[0]["severity"], "HIGH")

    def test_returns_list(self):
        result = self.c.classify_findings([])
        self.assertIsInstance(result, list)


class TestPriorityScore(unittest.TestCase):
    """Test priority_score convenience method."""

    def setUp(self):
        self.c = ReviewClassifier()

    def test_bugfix_returns_highest(self):
        self.assertAlmostEqual(self.c.priority_score("bugfix"), 8.53, places=1)

    def test_style_returns_lowest(self):
        self.assertAlmostEqual(self.c.priority_score("style"), 5.0, places=1)

    def test_unknown_category_returns_zero(self):
        self.assertEqual(self.c.priority_score("unknown_category"), 0.0)

    def test_all_categories_valid(self):
        for cat in CATEGORY_SCORES:
            score = self.c.priority_score(cat)
            self.assertGreater(score, 0)


if __name__ == "__main__":
    unittest.main()
