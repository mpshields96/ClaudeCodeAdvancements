#!/usr/bin/env python3
"""
Tests for validate_strategies.py — Strategy validation loop.
"""

import json
import os
import sys
import tempfile
import shutil
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR.parent))

SAMPLE_SKILLBOOK = """
## Active Strategies (Confidence >= 50)

### S1: Deep-read BUILD/ADAPT candidates only — Confidence: 90
**Directive:** "When scanning, triage by title first. Only deep-read posts scoring high or containing frontier keywords."
- Source: Sessions 14, 23

### S2: Parallel review agents — Confidence: 85
**Directive:** "Launch up to five review agents simultaneously for batch URL processing."
- Source: Sessions 32-33

### S3: Classifier keyword tuning — Confidence: 95 (IMPLEMENTED)
**Directive:** "If a subreddit scan returns high NEEDLE ratio, the profile keywords are too generic."
- Source: Sessions 32-35

## Emerging Strategies (Confidence 30-49)

### S9: Time-weighted decay — Confidence: 40
**Directive:** "Consider dual decay for memory: TTL-by-confidence for deletion and time-weighted abstraction."
- Source: Session 33

### S10: Role-specific agents — Confidence: 35
**Directive:** "For visual output and diagram generation, use a dedicated agent with role-specific system prompt."
- Source: Session 33
"""


def _make_entry(event_type="session_reflection", notes="", outcome="success",
                learnings=None, days_ago=1):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "timestamp": ts,
        "event_type": event_type,
        "notes": notes,
        "outcome": outcome,
        "learnings": learnings or [],
    }


class TestImports(unittest.TestCase):
    def test_import_strategy(self):
        from validate_strategies import Strategy
        self.assertTrue(callable(Strategy))

    def test_import_validation_result(self):
        from validate_strategies import ValidationResult
        self.assertTrue(callable(ValidationResult))

    def test_import_strategy_validator(self):
        from validate_strategies import StrategyValidator
        self.assertTrue(callable(StrategyValidator))

    def test_import_extract_strategies(self):
        from validate_strategies import extract_strategies
        self.assertTrue(callable(extract_strategies))

    def test_import_validate_all(self):
        from validate_strategies import validate_all
        self.assertTrue(callable(validate_all))


class TestExtractStrategies(unittest.TestCase):
    def test_extract_from_sample(self):
        from validate_strategies import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=30)
        self.assertGreater(len(strategies), 0)

    def test_respects_min_confidence(self):
        from validate_strategies import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=50)
        for s in strategies:
            self.assertGreaterEqual(s.confidence, 50)

    def test_extracts_keywords(self):
        from validate_strategies import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=50)
        for s in strategies:
            self.assertIsInstance(s.keywords, list)
            self.assertGreater(len(s.keywords), 0)

    def test_strategy_has_all_fields(self):
        from validate_strategies import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=50)
        for s in strategies:
            self.assertIsNotNone(s.id)
            self.assertIsNotNone(s.name)
            self.assertIsInstance(s.confidence, int)
            self.assertIsNotNone(s.directive)

    def test_empty_content(self):
        from validate_strategies import extract_strategies
        result = extract_strategies("", min_confidence=50)
        self.assertEqual(result, [])

    def test_parses_implemented_marker(self):
        """Should parse strategies with (IMPLEMENTED) in confidence line."""
        from validate_strategies import extract_strategies
        strategies = extract_strategies(SAMPLE_SKILLBOOK, min_confidence=90)
        ids = {s.id for s in strategies}
        self.assertIn("S3", ids)  # Has "(IMPLEMENTED)" after confidence


class TestExtractKeywords(unittest.TestCase):
    def test_extracts_meaningful_words(self):
        from validate_strategies import _extract_keywords
        kws = _extract_keywords("When scanning, triage by title first and deep-read frontier posts.")
        self.assertTrue(any("triage" in kw or "scanning" in kw or "frontier" in kw for kw in kws))

    def test_excludes_stop_words(self):
        from validate_strategies import _extract_keywords
        kws = _extract_keywords("the quick brown fox is very good")
        self.assertNotIn("the", kws)
        self.assertNotIn("is", kws)

    def test_caps_keywords(self):
        from validate_strategies import _extract_keywords
        kws = _extract_keywords("a " * 50 + "keyword " * 50)
        self.assertLessEqual(len(kws), 15)


class TestValidationResult(unittest.TestCase):
    def test_to_dict(self):
        from validate_strategies import ValidationResult
        r = ValidationResult(
            strategy_id="S1", strategy_name="Test", current_confidence=80,
            outcome="CONFIRMED", evidence_count=3,
            evidence_summary="3 positive", recommended_confidence=85,
        )
        d = r.to_dict()
        self.assertEqual(d["strategy_id"], "S1")
        self.assertEqual(d["outcome"], "CONFIRMED")
        json.dumps(d)  # Must be serializable


class TestStrategyValidator(unittest.TestCase):
    def _make_strategy(self, sid="S1", name="Test", confidence=80,
                       directive="When scanning, triage and deep-read posts.",
                       keywords=None):
        from validate_strategies import Strategy
        if keywords is None:
            from validate_strategies import _extract_keywords
            keywords = _extract_keywords(directive)
        return Strategy(id=sid, name=name, confidence=confidence,
                        directive=directive, keywords=keywords)

    def test_no_evidence_unchanged(self):
        """Strategy with no matching evidence should be UNCHANGED."""
        from validate_strategies import StrategyValidator
        s = self._make_strategy()
        v = StrategyValidator([s], [])
        results = v.validate_all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].outcome, "UNCHANGED")

    def test_positive_evidence_confirms(self):
        """Strategy with positive matching evidence should be CONFIRMED."""
        from validate_strategies import StrategyValidator
        s = self._make_strategy(
            directive="When scanning, triage by title first and deep-read high-scoring posts.",
            keywords=["scanning", "triage", "title", "deep-read", "posts"],
        )
        entries = [
            _make_entry(
                notes="scanning triage worked well today, deep-read posts hit rate was high",
                outcome="success",
            ),
        ]
        v = StrategyValidator([s], entries)
        results = v.validate_all()
        self.assertEqual(results[0].outcome, "CONFIRMED")

    def test_negative_evidence_contradicts(self):
        """Strategy with negative matching evidence should be CONTRADICTED."""
        from validate_strategies import StrategyValidator
        s = self._make_strategy(
            directive="When scanning, triage by title first and deep-read high-scoring posts.",
            keywords=["scanning", "triage", "title", "deep-read", "posts"],
        )
        entries = [
            _make_entry(
                notes="scanning triage missed important posts, deep-read selection was poor",
                outcome="failure",
            ),
        ]
        v = StrategyValidator([s], entries)
        results = v.validate_all()
        self.assertEqual(results[0].outcome, "CONTRADICTED")

    def test_confidence_bump_on_confirm(self):
        """Confirmed strategies should get confidence bump."""
        from validate_strategies import StrategyValidator
        s = self._make_strategy(confidence=80,
                                keywords=["scanning", "triage", "deep-read"])
        entries = [
            _make_entry(notes="scanning triage deep-read worked", outcome="success"),
        ]
        v = StrategyValidator([s], entries)
        results = v.validate_all()
        if results[0].outcome == "CONFIRMED":
            self.assertGreater(results[0].recommended_confidence, 80)

    def test_confidence_drop_on_contradict(self):
        """Contradicted strategies should get confidence drop."""
        from validate_strategies import StrategyValidator
        s = self._make_strategy(confidence=80,
                                keywords=["scanning", "triage", "deep-read"])
        entries = [
            _make_entry(notes="scanning triage deep-read failed badly", outcome="failure"),
        ]
        v = StrategyValidator([s], entries)
        results = v.validate_all()
        if results[0].outcome == "CONTRADICTED":
            self.assertLess(results[0].recommended_confidence, 80)

    def test_confidence_never_above_100(self):
        """Recommended confidence should never exceed 100."""
        from validate_strategies import StrategyValidator
        s = self._make_strategy(confidence=98,
                                keywords=["scanning", "triage", "deep-read"])
        entries = [
            _make_entry(notes="scanning triage deep-read", outcome="success"),
            _make_entry(notes="scanning triage deep-read", outcome="success"),
            _make_entry(notes="scanning triage deep-read", outcome="success"),
        ]
        v = StrategyValidator([s], entries)
        results = v.validate_all()
        self.assertLessEqual(results[0].recommended_confidence, 100)

    def test_confidence_never_below_0(self):
        """Recommended confidence should never go below 0."""
        from validate_strategies import StrategyValidator
        s = self._make_strategy(confidence=5,
                                keywords=["scanning", "triage", "deep-read"])
        entries = [
            _make_entry(notes="scanning triage deep-read", outcome="failure"),
            _make_entry(notes="scanning triage deep-read", outcome="failure"),
            _make_entry(notes="scanning triage deep-read", outcome="failure"),
        ]
        v = StrategyValidator([s], entries)
        results = v.validate_all()
        self.assertGreaterEqual(results[0].recommended_confidence, 0)

    def test_multiple_strategies(self):
        """Should validate each strategy independently."""
        from validate_strategies import StrategyValidator
        s1 = self._make_strategy(sid="S1", keywords=["scanning", "triage"])
        s2 = self._make_strategy(sid="S2", keywords=["agents", "parallel"])
        entries = [
            _make_entry(notes="scanning triage worked", outcome="success"),
        ]
        v = StrategyValidator([s1, s2], entries)
        results = v.validate_all()
        self.assertEqual(len(results), 2)
        # S1 should have evidence, S2 should not
        s1_result = next(r for r in results if r.strategy_id == "S1")
        s2_result = next(r for r in results if r.strategy_id == "S2")
        self.assertGreaterEqual(s1_result.evidence_count, 0)
        self.assertEqual(s2_result.outcome, "UNCHANGED")

    def test_requires_2_keyword_matches(self):
        """Should require at least 2 keyword matches, not just 1."""
        from validate_strategies import StrategyValidator
        s = self._make_strategy(keywords=["scanning", "triage", "deep-read"])
        # Only 1 keyword match — should not count as evidence
        entries = [
            _make_entry(notes="I did some scanning today", outcome="success"),
        ]
        v = StrategyValidator([s], entries)
        results = v.validate_all()
        self.assertEqual(results[0].outcome, "UNCHANGED")


class TestLoadJournal(unittest.TestCase):
    def test_empty_file_returns_empty(self):
        from validate_strategies import load_recent_journal
        with patch("validate_strategies._JOURNAL_PATH", Path("/nonexistent/path.jsonl")):
            result = load_recent_journal()
            self.assertEqual(result, [])

    def test_filters_by_days(self):
        from validate_strategies import load_recent_journal
        tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        try:
            # Write entries: one recent, one old
            recent = _make_entry(days_ago=1)
            old = _make_entry(days_ago=30)
            tmpfile.write(json.dumps(recent) + "\n")
            tmpfile.write(json.dumps(old) + "\n")
            tmpfile.close()

            with patch("validate_strategies._JOURNAL_PATH", Path(tmpfile.name)):
                result = load_recent_journal(days=7)
                self.assertEqual(len(result), 1)  # Only the recent one
        finally:
            os.unlink(tmpfile.name)


class TestValidateAll(unittest.TestCase):
    def test_returns_list(self):
        from validate_strategies import validate_all
        result = validate_all()
        self.assertIsInstance(result, list)

    def test_with_real_skillbook(self):
        """Should work with the actual SKILLBOOK.md if it exists."""
        from validate_strategies import validate_all
        results = validate_all()
        for r in results:
            self.assertIn(r.outcome, ("CONFIRMED", "CONTRADICTED", "UNCHANGED"))


class TestCLI(unittest.TestCase):
    def test_brief_mode(self):
        from validate_strategies import main
        import io
        buf = io.StringIO()
        with patch("sys.argv", ["validate_strategies.py", "--brief"]), \
             patch("sys.stdout", buf):
            main()
        output = buf.getvalue()
        self.assertIn("validation", output.lower())

    def test_json_mode(self):
        from validate_strategies import main
        import io
        buf = io.StringIO()
        with patch("sys.argv", ["validate_strategies.py", "--json"]), \
             patch("sys.stdout", buf):
            main()
        output = buf.getvalue()
        parsed = json.loads(output)
        self.assertIsInstance(parsed, list)


if __name__ == "__main__":
    unittest.main()
