#!/usr/bin/env python3
"""Tests for reflect.py principle_registry integration (MT-28).

The reflect() function imports principle_registry at lines 489-502.
This integration path had zero test coverage before S107.

Tests cover:
- Principles section appears when active principles exist
- Principles section skipped when no active principles
- Principles section skipped when principle_registry import fails
- Domain filtering passes through to get_top_principles
- Reinforced status displays correctly
- Prunable count displays correctly
- Score formatting
- Text truncation at 70 chars
"""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)

import reflect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class FakePrinciple:
    """Minimal Principle-like object for testing."""
    text: str
    score: float
    is_reinforced: bool = False
    id: str = "p_test_12345678"
    source_domain: str = "cca_operations"
    usage_count: int = 5
    success_count: int = 3


def _make_journal_entries(n=5):
    """Create minimal journal entries so reflect() doesn't exit early."""
    return [
        {"event_type": "session_outcome", "domain": "self_learning",
         "outcome": "success", "timestamp": f"2026-03-{10+i:02d}T10:00:00Z"}
        for i in range(n)
    ]


def _make_principle_stats(active=3, reinforced=1, prunable=0):
    return {
        "total": active,
        "active": active,
        "pruned": 0,
        "reinforced": reinforced,
        "avg_score": 0.65,
        "domain_counts": {"cca_operations": active},
        "prunable": prunable,
    }


# ---------------------------------------------------------------------------
# Tests: Principles section in reflect() report
# ---------------------------------------------------------------------------

class TestReflectPrincipleIntegration(unittest.TestCase):
    """Test the principle_registry integration in reflect()."""

    def setUp(self):
        """Create a temp journal with some entries."""
        self.tmpdir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")
        self.strategy_path = os.path.join(self.tmpdir, "strategy.json")

        # Write minimal journal
        with open(self.journal_path, "w") as f:
            for entry in _make_journal_entries(5):
                f.write(json.dumps(entry) + "\n")

        # Write minimal strategy
        with open(self.strategy_path, "w") as f:
            json.dump({"version": 1}, f)

    def _capture_reflect(self, domain=None):
        """Run reflect() and capture stdout."""
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            with patch.object(reflect, '_load_journal', return_value=_make_journal_entries(5)):
                with patch.object(reflect, '_load_strategy', return_value={"version": 1}):
                    reflect.reflect(domain=domain, brief=False)
        finally:
            sys.stdout = old_stdout
        return captured.getvalue()

    def test_principles_section_shown_when_active(self):
        """When principles exist, the section should appear in report."""
        fake_stats = _make_principle_stats(active=3, reinforced=1)
        fake_principles = [
            FakePrinciple(text="Test principle one", score=0.75, is_reinforced=True),
            FakePrinciple(text="Test principle two", score=0.60),
        ]

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=MagicMock(return_value=fake_principles),
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        self.assertIn("Strategic Principles", output)
        self.assertIn("3 active", output)
        self.assertIn("1 reinforced", output)

    def test_principles_section_hidden_when_no_active(self):
        """When no active principles, section should not appear."""
        fake_stats = _make_principle_stats(active=0, reinforced=0)

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        self.assertNotIn("Strategic Principles", output)

    def test_principles_section_hidden_on_import_error(self):
        """When principle_registry is not importable, section gracefully skips."""
        # Remove principle_registry from sys.modules if it's cached
        with patch.dict('sys.modules', {'principle_registry': None}):
            # The try/except ImportError in reflect.py should catch this
            output = self._capture_reflect()

        self.assertNotIn("Strategic Principles", output)
        # Report should still render without error
        self.assertIn("CCA SELF-LEARNING REFLECTION REPORT", output)

    def test_principle_score_formatting(self):
        """Scores should be formatted to 2 decimal places."""
        fake_stats = _make_principle_stats(active=1)
        fake_principles = [
            FakePrinciple(text="A principle", score=0.6667),
        ]

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=MagicMock(return_value=fake_principles),
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        self.assertIn("[0.67]", output)

    def test_reinforced_flag_displayed(self):
        """Reinforced principles should show [REINFORCED] tag."""
        fake_stats = _make_principle_stats(active=1, reinforced=1)
        fake_principles = [
            FakePrinciple(text="A reinforced principle", score=0.80, is_reinforced=True),
        ]

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=MagicMock(return_value=fake_principles),
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        self.assertIn("[REINFORCED]", output)

    def test_non_reinforced_no_tag(self):
        """Non-reinforced principles should NOT show [REINFORCED] tag."""
        fake_stats = _make_principle_stats(active=1, reinforced=0)
        fake_principles = [
            FakePrinciple(text="A normal principle", score=0.50, is_reinforced=False),
        ]

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=MagicMock(return_value=fake_principles),
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        self.assertNotIn("[REINFORCED]", output)

    def test_prunable_count_shown(self):
        """When prunable principles exist, count should be shown."""
        fake_stats = _make_principle_stats(active=5, prunable=2)
        fake_principles = [
            FakePrinciple(text="Principle", score=0.50),
        ]

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=MagicMock(return_value=fake_principles),
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        self.assertIn("2 principles eligible for pruning", output)

    def test_prunable_count_hidden_when_zero(self):
        """When no prunable principles, the prunable line should not appear."""
        fake_stats = _make_principle_stats(active=3, prunable=0)
        fake_principles = [
            FakePrinciple(text="Principle", score=0.50),
        ]

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=MagicMock(return_value=fake_principles),
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        self.assertNotIn("eligible for pruning", output)

    def test_text_truncation_at_70_chars(self):
        """Principle text should be truncated at 70 characters."""
        long_text = "A" * 100  # 100 chars
        fake_stats = _make_principle_stats(active=1)
        fake_principles = [
            FakePrinciple(text=long_text, score=0.50),
        ]

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=MagicMock(return_value=fake_principles),
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        # The full 100-char text should NOT appear
        self.assertNotIn("A" * 100, output)
        # But the first 70 chars should
        self.assertIn("A" * 70, output)

    def test_domain_filter_passed_through(self):
        """Domain filter should be passed to get_top_principles."""
        fake_stats = _make_principle_stats(active=1)
        mock_get_top = MagicMock(return_value=[
            FakePrinciple(text="Domain-specific", score=0.50),
        ])

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=mock_get_top,
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            self._capture_reflect(domain="trading_research")

        # Verify domain was passed through
        mock_get_top.assert_called_once_with(n=5, domain="trading_research")

    def test_multiple_principles_numbered(self):
        """Multiple principles should be numbered sequentially."""
        fake_stats = _make_principle_stats(active=3)
        fake_principles = [
            FakePrinciple(text="First principle", score=0.80),
            FakePrinciple(text="Second principle", score=0.70),
            FakePrinciple(text="Third principle", score=0.60),
        ]

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=MagicMock(return_value=fake_principles),
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        self.assertIn("1.", output)
        self.assertIn("2.", output)
        self.assertIn("3.", output)
        self.assertIn("First principle", output)
        self.assertIn("Third principle", output)

    def test_empty_principles_list_no_crash(self):
        """If get_top_principles returns empty list, no crash."""
        fake_stats = _make_principle_stats(active=1)  # active but no top results

        with patch.dict('sys.modules', {
            'principle_registry': MagicMock(
                get_top_principles=MagicMock(return_value=[]),
                get_stats=MagicMock(return_value=fake_stats),
            )
        }):
            output = self._capture_reflect()

        # Header shows but no numbered items
        self.assertIn("Strategic Principles", output)

    def test_brief_mode_skips_principles(self):
        """In brief mode, principles section should not appear."""
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            with patch.object(reflect, '_load_journal', return_value=_make_journal_entries(5)):
                with patch.object(reflect, '_load_strategy', return_value={"version": 1}):
                    reflect.reflect(brief=True)
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()

        self.assertNotIn("Strategic Principles", output)


if __name__ == "__main__":
    unittest.main()
