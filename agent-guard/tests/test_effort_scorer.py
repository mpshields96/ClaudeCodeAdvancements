#!/usr/bin/env python3
"""Tests for effort_scorer.py — MT-20 Senior Dev Agent: PR effort scoring.

Scoring mirrors PR-Agent's 1-5 scale, grounded in Atlassian's empirical research:
- 200-400 LOC is the empirically validated review limit (Cisco research)
- Complexity markers (if/for/while/def/class) increase cognitive load
- File count increases review surface area

Tests cover:
- LOC-based scoring at key thresholds
- Complexity marker counting
- Score normalization (always 1-5)
- Hook I/O format
- Edge cases (empty content, non-code files, very large files)
- Score labels match levels
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from effort_scorer import EffortScorer, EffortScore, score_content


class TestEffortScore(unittest.TestCase):
    """Test EffortScore dataclass."""

    def test_score_fields(self):
        s = EffortScore(score=3, label="Moderate", loc=120, complexity=8, breakdown={"loc_points": 2, "complexity_points": 1})
        self.assertEqual(s.score, 3)
        self.assertEqual(s.label, "Moderate")
        self.assertEqual(s.loc, 120)
        self.assertEqual(s.complexity, 8)

    def test_to_dict(self):
        s = EffortScore(score=2, label="Simple", loc=30, complexity=3, breakdown={})
        d = s.to_dict()
        self.assertIn("score", d)
        self.assertIn("label", d)
        self.assertIn("loc", d)
        self.assertIn("complexity", d)
        self.assertIn("breakdown", d)

    def test_score_in_range(self):
        for score in [1, 2, 3, 4, 5]:
            s = EffortScore(score=score, label="X", loc=0, complexity=0, breakdown={})
            self.assertGreaterEqual(s.score, 1)
            self.assertLessEqual(s.score, 5)


class TestEffortScorerLOC(unittest.TestCase):
    """Test LOC-based scoring thresholds from Atlassian/Cisco research."""

    def setUp(self):
        self.scorer = EffortScorer()

    def test_empty_content_trivial(self):
        result = self.scorer.score_content("")
        self.assertEqual(result.score, 1)
        self.assertEqual(result.label, "Trivial")
        self.assertEqual(result.loc, 0)

    def test_1_line_trivial(self):
        result = self.scorer.score_content("x = 1")
        self.assertEqual(result.score, 1)

    def test_10_lines_trivial(self):
        content = "\n".join(["x = 1"] * 10)
        result = self.scorer.score_content(content)
        self.assertEqual(result.score, 1)

    def test_30_lines_simple(self):
        content = "\n".join(["x = 1"] * 30)
        result = self.scorer.score_content(content)
        self.assertIn(result.score, [1, 2])  # 30 lines is borderline

    def test_60_lines_simple_or_moderate(self):
        content = "\n".join(["x = 1"] * 60)
        result = self.scorer.score_content(content)
        self.assertIn(result.score, [2, 3])

    def test_160_lines_moderate(self):
        content = "\n".join(["x = 1"] * 160)
        result = self.scorer.score_content(content)
        self.assertGreaterEqual(result.score, 3)

    def test_250_lines_complex(self):
        content = "\n".join(["x = 1"] * 250)
        result = self.scorer.score_content(content)
        self.assertGreaterEqual(result.score, 3)

    def test_500_lines_very_complex(self):
        content = "\n".join(["x = 1"] * 500)
        result = self.scorer.score_content(content)
        self.assertGreaterEqual(result.score, 4)

    def test_1000_lines_max_score(self):
        content = "\n".join(["x = 1"] * 1000)
        result = self.scorer.score_content(content)
        self.assertEqual(result.score, 5)

    def test_score_always_1_to_5(self):
        for n in [0, 1, 5, 10, 50, 100, 200, 400, 800, 2000]:
            content = "\n".join(["x = 1"] * n)
            result = self.scorer.score_content(content)
            self.assertGreaterEqual(result.score, 1, f"score < 1 for {n} lines")
            self.assertLessEqual(result.score, 5, f"score > 5 for {n} lines")


class TestEffortScorerComplexity(unittest.TestCase):
    """Test complexity marker detection."""

    def setUp(self):
        self.scorer = EffortScorer()

    def test_no_complexity_markers(self):
        content = "x = 1\ny = 2\nz = x + y"
        result = self.scorer.score_content(content)
        self.assertEqual(result.complexity, 0)

    def test_if_statement_counted(self):
        content = "if x > 0:\n    y = 1"
        result = self.scorer.score_content(content)
        self.assertGreaterEqual(result.complexity, 1)

    def test_for_loop_counted(self):
        content = "for i in range(10):\n    print(i)"
        result = self.scorer.score_content(content)
        self.assertGreaterEqual(result.complexity, 1)

    def test_while_loop_counted(self):
        content = "while True:\n    break"
        result = self.scorer.score_content(content)
        self.assertGreaterEqual(result.complexity, 1)

    def test_def_counted(self):
        content = "def my_func():\n    pass"
        result = self.scorer.score_content(content)
        self.assertGreaterEqual(result.complexity, 1)

    def test_class_counted(self):
        content = "class MyClass:\n    pass"
        result = self.scorer.score_content(content)
        self.assertGreaterEqual(result.complexity, 1)

    def test_try_except_counted(self):
        content = "try:\n    x = 1\nexcept Exception:\n    pass"
        result = self.scorer.score_content(content)
        self.assertGreaterEqual(result.complexity, 1)

    def test_high_complexity_raises_score(self):
        # 10 functions in a tiny file = complexity raises score
        content = "\n".join([f"def func_{i}():\n    if x:\n        for j in range(10):\n            pass" for i in range(5)])
        result_plain = self.scorer.score_content("x = 1\ny = 2")
        result_complex = self.scorer.score_content(content)
        self.assertGreaterEqual(result_complex.score, result_plain.score)

    def test_complexity_in_breakdown(self):
        content = "if x:\n    for i in range(10):\n        pass"
        result = self.scorer.score_content(content)
        self.assertIn("complexity_points", result.breakdown)


class TestEffortScorerLabels(unittest.TestCase):
    """Test score labels are consistent with numeric scores."""

    def setUp(self):
        self.scorer = EffortScorer()

    def test_score_1_label_trivial(self):
        result = self.scorer.score_content("")
        self.assertEqual(result.score, 1)
        self.assertEqual(result.label, "Trivial")

    def test_all_labels_are_strings(self):
        for content_size in [0, 30, 100, 300, 600]:
            content = "\n".join(["x = 1"] * content_size)
            result = self.scorer.score_content(content)
            self.assertIsInstance(result.label, str)
            self.assertTrue(len(result.label) > 0)

    def test_label_matches_score(self):
        label_map = {1: "Trivial", 2: "Simple", 3: "Moderate", 4: "Complex", 5: "Very Complex"}
        for content_size in [0, 5, 80, 220, 600]:
            content = "\n".join(["x = 1"] * content_size)
            result = self.scorer.score_content(content)
            self.assertEqual(result.label, label_map[result.score])


class TestEffortScorerFileTypes(unittest.TestCase):
    """Test file-type-aware scoring."""

    def setUp(self):
        self.scorer = EffortScorer()

    def test_python_file_scores_complexity(self):
        content = "\n".join([f"def func_{i}():\n    if True:\n        pass" for i in range(10)])
        result = self.scorer.score_content(content, file_path="mymodule.py")
        self.assertGreater(result.complexity, 0)

    def test_markdown_file_skips_complexity(self):
        content = "## Header\n\nif you do this, for example:\n\nwhile True:\n    class Foo: pass"
        result = self.scorer.score_content(content, file_path="README.md")
        # Markdown should skip complexity counting — no code markers
        self.assertEqual(result.complexity, 0)

    def test_json_file_skips_complexity(self):
        content = '{"if": true, "for": "each", "while": 1}'
        result = self.scorer.score_content(content, file_path="config.json")
        self.assertEqual(result.complexity, 0)

    def test_yaml_file_skips_complexity(self):
        content = "if: true\nfor: each\nwhile: loop"
        result = self.scorer.score_content(content, file_path="config.yaml")
        self.assertEqual(result.complexity, 0)


class TestEffortScorerHookOutput(unittest.TestCase):
    """Test PostToolUse hook I/O format."""

    def setUp(self):
        self.scorer = EffortScorer()

    def test_trivial_no_context(self):
        """Trivial score (1) should not emit additionalContext — no noise."""
        payload = {"tool_name": "Write", "tool_input": {"content": "x = 1", "file_path": "test.py"}}
        output = self.scorer.hook_output(payload)
        # Trivial writes should not clutter context
        self.assertNotIn("additionalContext", output)

    def test_complex_emits_context(self):
        """Scores >= 3 should emit additionalContext."""
        content = "\n".join([f"def func_{i}():\n    if True:\n        for j in range(10):\n            pass" for i in range(20)])
        payload = {"tool_name": "Write", "tool_input": {"content": content, "file_path": "big_module.py"}}
        output = self.scorer.hook_output(payload)
        self.assertIn("additionalContext", output)

    def test_context_mentions_score(self):
        content = "\n".join([f"def func_{i}():\n    if True:\n        for j in range(10):\n            pass" for i in range(20)])
        payload = {"tool_name": "Write", "tool_input": {"content": content, "file_path": "big_module.py"}}
        output = self.scorer.hook_output(payload)
        if "additionalContext" in output:
            self.assertIn("effort", output["additionalContext"].lower())

    def test_edit_tool_scans_new_string(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "x = 1",
                "new_string": "\n".join([f"def func_{i}():\n    if True:\n        pass" for i in range(20)]),
            }
        }
        output = self.scorer.hook_output(payload)
        # Should produce some output given large new_string
        self.assertIsInstance(output, dict)

    def test_unknown_tool_returns_empty(self):
        payload = {"tool_name": "Read", "tool_input": {"file_path": "foo.py"}}
        output = self.scorer.hook_output(payload)
        self.assertEqual(output, {})

    def test_empty_payload_returns_empty(self):
        output = self.scorer.hook_output({})
        self.assertEqual(output, {})

    def test_context_length_bounded(self):
        """additionalContext should not exceed 500 chars."""
        content = "\n".join([f"def func_{i}():\n    for j in range(100):\n        if j > 50:\n            pass" for i in range(100)])
        payload = {"tool_name": "Write", "tool_input": {"content": content, "file_path": "huge.py"}}
        output = self.scorer.hook_output(payload)
        if "additionalContext" in output:
            self.assertLessEqual(len(output["additionalContext"]), 500)

    def test_returns_dict(self):
        payload = {"tool_name": "Write", "tool_input": {"content": "x=1", "file_path": "f.py"}}
        self.assertIsInstance(self.scorer.hook_output(payload), dict)


class TestScoreContentTopLevel(unittest.TestCase):
    """Test the module-level score_content() convenience function."""

    def test_top_level_function_exists(self):
        result = score_content("x = 1")
        self.assertIsInstance(result, EffortScore)

    def test_top_level_with_file_path(self):
        result = score_content("def foo():\n    pass\n" * 50, file_path="module.py")
        self.assertGreaterEqual(result.score, 1)
        self.assertLessEqual(result.score, 5)


class TestHookStdin(unittest.TestCase):
    """Test hook as a subprocess (stdin/stdout interface)."""

    def _script(self):
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "effort_scorer.py")

    def _run_hook(self, payload: dict) -> dict:
        result = subprocess.run(
            [sys.executable, self._script()],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        return json.loads(result.stdout.strip())

    def test_empty_stdin_returns_empty(self):
        result = subprocess.run(
            [sys.executable, self._script()],
            input="",
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self.assertEqual(json.loads(result.stdout.strip()), {})

    def test_invalid_json_returns_empty(self):
        result = subprocess.run(
            [sys.executable, self._script()],
            input="not json",
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        self.assertEqual(json.loads(result.stdout.strip()), {})

    def test_write_tool_processed(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "content": "\n".join([f"def func_{i}():\n    if True:\n        for j in range(10):\n            pass" for i in range(30)]),
                "file_path": "big_module.py",
            }
        }
        output = self._run_hook(payload)
        self.assertIsInstance(output, dict)


if __name__ == "__main__":
    unittest.main()
