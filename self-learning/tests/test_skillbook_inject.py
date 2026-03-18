#!/usr/bin/env python3
"""
Tests for skillbook_inject.py — UserPromptSubmit hook for Skillbook injection.

TDD: Tests written alongside implementation for Session 35.
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR.parent / "hooks"))
sys.path.insert(0, str(_THIS_DIR.parent))


SAMPLE_SKILLBOOK = """# CCA Skillbook — Distilled Strategies

---

## Active Strategies (Confidence >= 50)

### S1: Deep-read BUILD/ADAPT candidates only — Confidence: 90
**Directive:** "When scanning, triage by title first. Only deep-read posts scoring >200pts."
- Source: Sessions 14, 23

### S2: Parallel review agents for batch URLs — Confidence: 85
**Directive:** "Launch up to 5 review agents simultaneously for batch URL processing."
- Source: Sessions 32-33

### S3: Classifier needs per-sub keyword tuning — Confidence: 80
**Directive:** "If a subreddit scan returns >80% NEEDLE, the profile keywords are too generic."
- Source: Sessions 32-33

---

## Emerging Strategies (Confidence 30-49)

### S9: Time-weighted memory decay complements TTL — Confidence: 40
**Directive:** "Consider dual decay: TTL-by-confidence for deletion."
- Source: Session 33

### S10: Low confidence strategy — Confidence: 15
**Directive:** "This should be archived not injected."
- Source: Session 33
"""


class TestExtractStrategies(unittest.TestCase):
    """Tests for strategy extraction from SKILLBOOK.md content."""

    def test_import(self):
        from skillbook_inject import extract_strategies
        self.assertTrue(callable(extract_strategies))

    def test_extract_from_sample(self):
        from skillbook_inject import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=50)
        self.assertGreater(len(strategies), 0)

    def test_respects_min_confidence(self):
        """Should only return strategies with confidence >= min_confidence."""
        from skillbook_inject import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=50)
        for s in strategies:
            self.assertGreaterEqual(s["confidence"], 50)

    def test_excludes_low_confidence(self):
        """Should exclude strategies below min_confidence."""
        from skillbook_inject import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=50)
        ids = {s["id"] for s in strategies}
        self.assertNotIn("S9", ids)  # confidence 40
        self.assertNotIn("S10", ids)  # confidence 15

    def test_includes_high_confidence(self):
        """Should include S1 (confidence 90)."""
        from skillbook_inject import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=50)
        ids = {s["id"] for s in strategies}
        self.assertIn("S1", ids)
        self.assertIn("S2", ids)
        self.assertIn("S3", ids)

    def test_sorted_by_confidence_desc(self):
        """Strategies should be sorted by confidence descending."""
        from skillbook_inject import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=30)
        confidences = [s["confidence"] for s in strategies]
        self.assertEqual(confidences, sorted(confidences, reverse=True))

    def test_max_count_respected(self):
        """Should respect max_count parameter."""
        from skillbook_inject import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=30, max_count=2)
        self.assertLessEqual(len(strategies), 2)

    def test_strategy_has_required_fields(self):
        """Each strategy should have id, name, confidence, directive."""
        from skillbook_inject import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=50)
        for s in strategies:
            self.assertIn("id", s)
            self.assertIn("name", s)
            self.assertIn("confidence", s)
            self.assertIn("directive", s)
            self.assertIsInstance(s["confidence"], int)
            self.assertIsInstance(s["directive"], str)
            self.assertGreater(len(s["directive"]), 0)

    def test_empty_content(self):
        """Empty content should return empty list."""
        from skillbook_inject import extract_strategies
        strategies = extract_strategies("", min_confidence=50)
        self.assertEqual(strategies, [])

    def test_no_matching_strategies(self):
        """Content without strategies should return empty list."""
        from skillbook_inject import extract_strategies
        strategies = extract_strategies("# Just a heading\nSome text.", min_confidence=50)
        self.assertEqual(strategies, [])


class TestFormatInjection(unittest.TestCase):
    """Tests for formatting strategies into context injection text."""

    def test_import(self):
        from skillbook_inject import format_injection
        self.assertTrue(callable(format_injection))

    def test_format_with_strategies(self):
        from skillbook_inject import format_injection
        strategies = [
            {"id": "S1", "name": "Test", "confidence": 90, "directive": "Do the thing."},
            {"id": "S2", "name": "Test2", "confidence": 85, "directive": "Do another thing."},
        ]
        result = format_injection(strategies)
        self.assertIn("Skillbook", result)
        self.assertIn("S1", result)
        self.assertIn("Do the thing", result)
        self.assertIn("c=90", result)

    def test_format_empty_returns_empty(self):
        from skillbook_inject import format_injection
        result = format_injection([])
        self.assertEqual(result, "")

    def test_format_has_bookends(self):
        """Injection should have start and end markers."""
        from skillbook_inject import format_injection
        strategies = [{"id": "S1", "name": "T", "confidence": 90, "directive": "Test."}]
        result = format_injection(strategies)
        self.assertIn("[CCA Skillbook", result)
        self.assertIn("[End Skillbook]", result)


class TestReadSkillbook(unittest.TestCase):
    """Tests for reading SKILLBOOK.md."""

    def test_import(self):
        from skillbook_inject import read_skillbook
        self.assertTrue(callable(read_skillbook))

    def test_returns_string(self):
        from skillbook_inject import read_skillbook
        result = read_skillbook()
        self.assertIsInstance(result, str)

    def test_handles_missing_file(self):
        """Should return empty string if SKILLBOOK.md doesn't exist."""
        from skillbook_inject import read_skillbook
        with patch("skillbook_inject._SKILLBOOK_PATH", Path("/nonexistent/path/SKILLBOOK.md")):
            result = read_skillbook()
            self.assertEqual(result, "")


class TestHookMain(unittest.TestCase):
    """Tests for the hook main() entry point."""

    def test_import(self):
        from skillbook_inject import main
        self.assertTrue(callable(main))

    def test_non_cca_project_no_injection(self):
        """Should not inject for non-CCA projects."""
        from skillbook_inject import main
        hook_input = json.dumps({"cwd": "/Users/matt/Projects/SomeOtherProject"})
        with patch("sys.stdin") as mock_stdin, \
             patch("sys.stdout") as mock_stdout, \
             patch.dict(os.environ, {}, clear=False):
            mock_stdin.read.return_value = hook_input
            mock_stdout.write = lambda x: None
            # Should output empty response
            import io
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                main()
            output = json.loads(buf.getvalue())
            self.assertNotIn("additionalContext", output)

    def test_cca_project_gets_injection(self):
        """Should inject for CCA project."""
        from skillbook_inject import main
        hook_input = json.dumps({
            "cwd": "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        })
        # Clear injection flag
        os.environ.pop("CCA_SKILLBOOK_INJECTED", None)
        with patch("skillbook_inject.read_skillbook", return_value=SAMPLE_SKILLBOOK):
            import io
            buf = io.StringIO()
            with patch("sys.stdin") as mock_stdin, patch("sys.stdout", buf):
                mock_stdin.read.return_value = hook_input
                main()
            output = json.loads(buf.getvalue())
            self.assertIn("additionalContext", output)
            self.assertIn("Skillbook", output["additionalContext"])
        # Clean up env
        os.environ.pop("CCA_SKILLBOOK_INJECTED", None)

    def test_second_call_no_injection(self):
        """Should only inject once per session (env flag)."""
        from skillbook_inject import main
        hook_input = json.dumps({
            "cwd": "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        })
        os.environ["CCA_SKILLBOOK_INJECTED"] = "1"
        try:
            import io
            buf = io.StringIO()
            with patch("sys.stdin") as mock_stdin, patch("sys.stdout", buf):
                mock_stdin.read.return_value = hook_input
                main()
            output = json.loads(buf.getvalue())
            self.assertNotIn("additionalContext", output)
        finally:
            os.environ.pop("CCA_SKILLBOOK_INJECTED", None)

    def test_empty_skillbook_no_injection(self):
        """Should not inject if SKILLBOOK.md is empty."""
        from skillbook_inject import main
        hook_input = json.dumps({
            "cwd": "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        })
        os.environ.pop("CCA_SKILLBOOK_INJECTED", None)
        with patch("skillbook_inject.read_skillbook", return_value=""):
            import io
            buf = io.StringIO()
            with patch("sys.stdin") as mock_stdin, patch("sys.stdout", buf):
                mock_stdin.read.return_value = hook_input
                main()
            output = json.loads(buf.getvalue())
            self.assertNotIn("additionalContext", output)


class TestSafetyAndEdgeCases(unittest.TestCase):
    """Safety and edge case tests."""

    def test_no_credentials_in_output(self):
        """Injection output must never contain API keys or tokens."""
        from skillbook_inject import format_injection
        strategies = [
            {"id": "S1", "name": "T", "confidence": 90,
             "directive": "Use API wisely."},
        ]
        result = format_injection(strategies)
        self.assertNotIn("sk-", result)
        self.assertNotIn("Bearer", result)

    def test_malformed_stdin_handled(self):
        """Should handle malformed JSON stdin gracefully."""
        from skillbook_inject import main
        import io
        buf = io.StringIO()
        with patch("sys.stdin") as mock_stdin, patch("sys.stdout", buf):
            mock_stdin.read.return_value = "not json {{"
            main()
        output = json.loads(buf.getvalue())
        self.assertIsInstance(output, dict)

    def test_confidence_boundary_exact_50(self):
        """Strategy with exactly min_confidence should be included."""
        from skillbook_inject import extract_strategies
        content = '### S99: Edge case strategy — Confidence: 50\n**Directive:** "Test boundary."'
        strategies = extract_strategies(content, min_confidence=50)
        self.assertEqual(len(strategies), 1)
        self.assertEqual(strategies[0]["confidence"], 50)

    def test_confidence_boundary_49_excluded(self):
        """Strategy with confidence 49 should be excluded at min=50."""
        from skillbook_inject import extract_strategies
        content = '### S99: Edge case — Confidence: 49\n**Directive:** "Test boundary."'
        strategies = extract_strategies(content, min_confidence=50)
        self.assertEqual(len(strategies), 0)


if __name__ == "__main__":
    unittest.main()
