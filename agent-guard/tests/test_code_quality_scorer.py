#!/usr/bin/env python3
"""Tests for code_quality_scorer.py — MT-20 Senior Dev Agent: aggregate quality scoring.

Tests cover:
- Overall score calculation (0-100)
- Grade mapping (A-F)
- Individual dimension scoring (debt, complexity, size, documentation, naming)
- File type filtering
- Edge cases (empty content, very large files)
- Report serialization
- Summary output format
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from code_quality_scorer import (
    CodeQualityScorer,
    CodeQualityReport,
    DimensionScore,
    score_file,
    _score_to_grade,
    SKIP_EXTENSIONS,
)


class TestScoreToGrade(unittest.TestCase):
    """Test grade mapping from numeric score."""

    def test_a_grade(self):
        self.assertEqual(_score_to_grade(95), "A")
        self.assertEqual(_score_to_grade(90), "A")

    def test_b_grade(self):
        self.assertEqual(_score_to_grade(85), "B")
        self.assertEqual(_score_to_grade(80), "B")

    def test_c_grade(self):
        self.assertEqual(_score_to_grade(75), "C")
        self.assertEqual(_score_to_grade(70), "C")

    def test_d_grade(self):
        self.assertEqual(_score_to_grade(65), "D")
        self.assertEqual(_score_to_grade(60), "D")

    def test_f_grade(self):
        self.assertEqual(_score_to_grade(55), "F")
        self.assertEqual(_score_to_grade(0), "F")

    def test_boundary_values(self):
        self.assertEqual(_score_to_grade(89.9), "B")
        self.assertEqual(_score_to_grade(90.0), "A")


class TestDimensionScore(unittest.TestCase):
    """Test DimensionScore dataclass."""

    def test_fields(self):
        d = DimensionScore(name="test", score=85.0, weight=0.25, detail="test detail")
        self.assertEqual(d.name, "test")
        self.assertEqual(d.score, 85.0)
        self.assertEqual(d.weight, 0.25)

    def test_to_dict(self):
        d = DimensionScore(name="test", score=85.5, weight=0.25, detail="detail")
        result = d.to_dict()
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["score"], 85.5)
        self.assertIn("weight", result)
        self.assertIn("detail", result)


class TestCodeQualityReport(unittest.TestCase):
    """Test CodeQualityReport dataclass."""

    def test_fields(self):
        r = CodeQualityReport(overall_score=85.0, grade="B", loc=100)
        self.assertEqual(r.overall_score, 85.0)
        self.assertEqual(r.grade, "B")
        self.assertEqual(r.loc, 100)

    def test_to_dict(self):
        r = CodeQualityReport(overall_score=85.0, grade="B", loc=100, file_path="test.py")
        d = r.to_dict()
        self.assertIn("overall_score", d)
        self.assertIn("grade", d)
        self.assertIn("loc", d)
        self.assertIn("file_path", d)
        self.assertIn("dimensions", d)

    def test_summary(self):
        r = CodeQualityReport(overall_score=85.0, grade="B", loc=100)
        summary = r.summary()
        self.assertIn("B", summary)
        self.assertIn("85", summary)
        self.assertIn("100 LOC", summary)

    def test_to_dict_is_json_serializable(self):
        r = CodeQualityReport(
            overall_score=85.0, grade="B", loc=100,
            dimensions=[DimensionScore(name="test", score=85.0, weight=0.25, detail="d")],
        )
        json_str = json.dumps(r.to_dict())
        self.assertIsInstance(json_str, str)


class TestScorerEmptyContent(unittest.TestCase):
    """Test behavior with empty/minimal content."""

    def setUp(self):
        self.scorer = CodeQualityScorer()

    def test_empty_string_perfect_score(self):
        report = self.scorer.score("")
        self.assertEqual(report.overall_score, 100.0)
        self.assertEqual(report.grade, "A")
        self.assertEqual(report.loc, 0)

    def test_whitespace_only_perfect_score(self):
        report = self.scorer.score("   \n  \n  ")
        self.assertEqual(report.overall_score, 100.0)

    def test_single_line(self):
        report = self.scorer.score("x = 1")
        self.assertGreaterEqual(report.overall_score, 0)
        self.assertLessEqual(report.overall_score, 100)
        self.assertEqual(report.loc, 1)


class TestScorerFileTypes(unittest.TestCase):
    """Test file type filtering."""

    def setUp(self):
        self.scorer = CodeQualityScorer()

    def test_markdown_skipped(self):
        report = self.scorer.score("# HACK: bad\nif True:\n    pass", file_path="README.md")
        self.assertEqual(report.overall_score, 100.0)
        self.assertEqual(report.loc, 0)

    def test_json_skipped(self):
        report = self.scorer.score('{"key": "value"}', file_path="config.json")
        self.assertEqual(report.overall_score, 100.0)

    def test_python_analyzed(self):
        content = "# HACK: bad code\ndef foo():\n    if True:\n        pass"
        report = self.scorer.score(content, file_path="module.py")
        # Should actually analyze, score will be < 100 due to HACK marker
        self.assertIsNotNone(report.dimensions)

    def test_no_extension_analyzed(self):
        content = "# TODO: fix\ndef foo():\n    pass"
        report = self.scorer.score(content, file_path="Makefile")
        self.assertGreater(len(report.dimensions), 0)


class TestScorerDebtDensity(unittest.TestCase):
    """Test SATD debt density scoring."""

    def setUp(self):
        self.scorer = CodeQualityScorer()

    def test_clean_code_high_debt_score(self):
        content = "\n".join(["x = 1"] * 50)
        report = self.scorer.score(content, file_path="clean.py")
        debt_dim = next((d for d in report.dimensions if d.name == "debt_density"), None)
        self.assertIsNotNone(debt_dim)
        self.assertGreaterEqual(debt_dim.score, 90)

    def test_debt_laden_code_low_score(self):
        lines = [f"# HACK: fix {i}" for i in range(10)]
        lines.extend(["x = 1"] * 10)
        content = "\n".join(lines)
        report = self.scorer.score(content, file_path="debt.py")
        debt_dim = next((d for d in report.dimensions if d.name == "debt_density"), None)
        self.assertIsNotNone(debt_dim)
        self.assertLess(debt_dim.score, 80)


class TestScorerComplexity(unittest.TestCase):
    """Test complexity density scoring."""

    def setUp(self):
        self.scorer = CodeQualityScorer()

    def test_simple_code_high_score(self):
        content = "\n".join(["x = 1"] * 50)
        report = self.scorer.score(content, file_path="simple.py")
        cx_dim = next((d for d in report.dimensions if d.name == "complexity"), None)
        self.assertIsNotNone(cx_dim)
        self.assertGreaterEqual(cx_dim.score, 90)

    def test_complex_code_lower_score(self):
        content = "\n".join([
            f"def func_{i}():\n    if True:\n        for j in range(10):\n            while j > 0:\n                try:\n                    pass\n                except:\n                    pass"
            for i in range(10)
        ])
        report = self.scorer.score(content, file_path="complex.py")
        cx_dim = next((d for d in report.dimensions if d.name == "complexity"), None)
        self.assertIsNotNone(cx_dim)
        self.assertLess(cx_dim.score, 80)


class TestScorerSize(unittest.TestCase):
    """Test size scoring based on Atlassian thresholds."""

    def setUp(self):
        self.scorer = CodeQualityScorer()

    def test_small_file_perfect(self):
        content = "\n".join(["x = 1"] * 50)
        report = self.scorer.score(content, file_path="small.py")
        size_dim = next((d for d in report.dimensions if d.name == "size"), None)
        self.assertIsNotNone(size_dim)
        self.assertEqual(size_dim.score, 100.0)

    def test_large_file_penalized(self):
        content = "\n".join(["x = 1"] * 800)
        report = self.scorer.score(content, file_path="large.py")
        size_dim = next((d for d in report.dimensions if d.name == "size"), None)
        self.assertIsNotNone(size_dim)
        self.assertLess(size_dim.score, 60)

    def test_very_large_file(self):
        content = "\n".join(["x = 1"] * 1500)
        report = self.scorer.score(content, file_path="huge.py")
        size_dim = next((d for d in report.dimensions if d.name == "size"), None)
        self.assertIsNotNone(size_dim)
        self.assertLessEqual(size_dim.score, 20)


class TestScorerDocumentation(unittest.TestCase):
    """Test documentation ratio scoring."""

    def setUp(self):
        self.scorer = CodeQualityScorer()

    def test_well_documented(self):
        lines = ['"""Module docstring."""', "# Comment line"] + ["x = 1"] * 8
        content = "\n".join(lines)
        report = self.scorer.score(content, file_path="documented.py")
        doc_dim = next((d for d in report.dimensions if d.name == "documentation"), None)
        self.assertIsNotNone(doc_dim)
        self.assertGreaterEqual(doc_dim.score, 60)

    def test_undocumented(self):
        content = "\n".join(["x = 1"] * 50)
        report = self.scorer.score(content, file_path="nodocs.py")
        doc_dim = next((d for d in report.dimensions if d.name == "documentation"), None)
        self.assertIsNotNone(doc_dim)
        self.assertLessEqual(doc_dim.score, 80)


class TestScorerNaming(unittest.TestCase):
    """Test naming quality scoring."""

    def setUp(self):
        self.scorer = CodeQualityScorer()

    def test_good_names(self):
        content = "user_count = 10\ntotal_price = 99.99\ndef calculate_total():\n    pass"
        report = self.scorer.score(content, file_path="good_names.py")
        naming_dim = next((d for d in report.dimensions if d.name == "naming"), None)
        self.assertIsNotNone(naming_dim)
        self.assertGreaterEqual(naming_dim.score, 70)

    def test_naming_dimension_exists(self):
        report = self.scorer.score("x = 1", file_path="test.py")
        naming_dim = next((d for d in report.dimensions if d.name == "naming"), None)
        self.assertIsNotNone(naming_dim)


class TestScorerOverall(unittest.TestCase):
    """Test overall score aggregation."""

    def setUp(self):
        self.scorer = CodeQualityScorer()

    def test_score_in_range(self):
        report = self.scorer.score("x = 1\ny = 2", file_path="test.py")
        self.assertGreaterEqual(report.overall_score, 0)
        self.assertLessEqual(report.overall_score, 100)

    def test_grade_matches_score(self):
        report = self.scorer.score("x = 1", file_path="test.py")
        expected_grade = _score_to_grade(report.overall_score)
        self.assertEqual(report.grade, expected_grade)

    def test_five_dimensions(self):
        report = self.scorer.score("x = 1\ndef foo():\n    pass", file_path="test.py")
        self.assertEqual(len(report.dimensions), 5)

    def test_dimension_names(self):
        report = self.scorer.score("x = 1", file_path="test.py")
        names = {d.name for d in report.dimensions}
        self.assertIn("debt_density", names)
        self.assertIn("complexity", names)
        self.assertIn("size", names)
        self.assertIn("documentation", names)
        self.assertIn("naming", names)

    def test_weights_sum_to_one(self):
        report = self.scorer.score("x = 1", file_path="test.py")
        total_weight = sum(d.weight for d in report.dimensions)
        self.assertAlmostEqual(total_weight, 1.0, places=2)


class TestTopLevelFunction(unittest.TestCase):
    """Test score_file() convenience function."""

    def test_returns_report(self):
        report = score_file("x = 1")
        self.assertIsInstance(report, CodeQualityReport)

    def test_with_file_path(self):
        report = score_file("def foo():\n    pass", file_path="module.py")
        self.assertGreaterEqual(report.overall_score, 0)
        self.assertLessEqual(report.overall_score, 100)


class TestSkipExtensions(unittest.TestCase):
    """Verify skip extensions are correct."""

    def test_common_non_code_skipped(self):
        for ext in [".md", ".json", ".yaml", ".yml", ".txt", ".toml"]:
            self.assertIn(ext, SKIP_EXTENSIONS, f"{ext} should be skipped")


if __name__ == "__main__":
    unittest.main()
