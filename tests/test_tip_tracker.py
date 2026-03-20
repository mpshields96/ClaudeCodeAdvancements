#!/usr/bin/env python3
"""
test_tip_tracker.py — Tests for advancement tip tracker.

S89: Matthew explicit S86 request — tips must persist across all chats.

Run: python3 tests/test_tip_tracker.py
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTipStorage(unittest.TestCase):
    """Test tip persistence (JSONL file)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_add_tip(self):
        from tip_tracker import add_tip
        tip = add_tip("Use pytest -x for fast failure", source="cca-desktop",
                      session="S89", path=self.path)
        self.assertIn("id", tip)
        self.assertEqual(tip["text"], "Use pytest -x for fast failure")
        self.assertEqual(tip["source"], "cca-desktop")
        self.assertEqual(tip["session"], "S89")
        self.assertEqual(tip["status"], "pending")

    def test_tip_persists_to_file(self):
        from tip_tracker import add_tip, load_tips
        add_tip("Tip 1", source="cca", path=self.path)
        tips = load_tips(self.path)
        self.assertEqual(len(tips), 1)
        self.assertEqual(tips[0]["text"], "Tip 1")

    def test_multiple_tips_appended(self):
        from tip_tracker import add_tip, load_tips
        add_tip("Tip 1", source="cca", path=self.path)
        add_tip("Tip 2", source="kalshi", path=self.path)
        add_tip("Tip 3", source="cli1", path=self.path)
        tips = load_tips(self.path)
        self.assertEqual(len(tips), 3)

    def test_tip_has_timestamp(self):
        from tip_tracker import add_tip
        tip = add_tip("Test", source="cca", path=self.path)
        self.assertIn("created_at", tip)
        self.assertIn("T", tip["created_at"])

    def test_tip_has_unique_id(self):
        from tip_tracker import add_tip
        t1 = add_tip("Tip A", source="cca", path=self.path)
        t2 = add_tip("Tip B", source="cca", path=self.path)
        self.assertNotEqual(t1["id"], t2["id"])

    def test_load_empty_file(self):
        from tip_tracker import load_tips
        tips = load_tips(self.path)
        self.assertEqual(tips, [])

    def test_load_nonexistent_file(self):
        from tip_tracker import load_tips
        tips = load_tips("/nonexistent/tips.jsonl")
        self.assertEqual(tips, [])

    def test_load_skips_malformed_lines(self):
        from tip_tracker import load_tips
        with open(self.path, "w") as f:
            f.write('{"text": "valid", "id": "1", "status": "pending"}\n')
            f.write("not json\n")
            f.write('{"text": "also valid", "id": "2", "status": "pending"}\n')
        tips = load_tips(self.path)
        self.assertEqual(len(tips), 2)


class TestTipStatusUpdate(unittest.TestCase):
    """Test updating tip status (pending -> implemented/skipped)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_mark_implemented(self):
        from tip_tracker import add_tip, update_status, load_tips
        tip = add_tip("Do X", source="cca", path=self.path)
        result = update_status(tip["id"], "implemented", path=self.path)
        self.assertTrue(result)
        tips = load_tips(self.path)
        self.assertEqual(tips[0]["status"], "implemented")

    def test_mark_skipped(self):
        from tip_tracker import add_tip, update_status, load_tips
        tip = add_tip("Do Y", source="cca", path=self.path)
        result = update_status(tip["id"], "skipped", path=self.path)
        self.assertTrue(result)
        tips = load_tips(self.path)
        self.assertEqual(tips[0]["status"], "skipped")

    def test_update_nonexistent_returns_false(self):
        from tip_tracker import update_status
        result = update_status("nonexistent_id", "implemented", path=self.path)
        self.assertFalse(result)

    def test_update_preserves_other_tips(self):
        from tip_tracker import add_tip, update_status, load_tips
        t1 = add_tip("Tip 1", source="cca", path=self.path)
        t2 = add_tip("Tip 2", source="cca", path=self.path)
        update_status(t1["id"], "implemented", path=self.path)
        tips = load_tips(self.path)
        self.assertEqual(tips[0]["status"], "implemented")
        self.assertEqual(tips[1]["status"], "pending")

    def test_invalid_status_raises(self):
        from tip_tracker import add_tip, update_status
        tip = add_tip("Test", source="cca", path=self.path)
        with self.assertRaises(ValueError):
            update_status(tip["id"], "bogus", path=self.path)


class TestTipFiltering(unittest.TestCase):
    """Test filtering tips by status/source."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_get_pending(self):
        from tip_tracker import add_tip, update_status, get_pending
        add_tip("Pending 1", source="cca", path=self.path)
        t2 = add_tip("Done 1", source="cca", path=self.path)
        add_tip("Pending 2", source="kalshi", path=self.path)
        update_status(t2["id"], "implemented", path=self.path)
        pending = get_pending(self.path)
        self.assertEqual(len(pending), 2)

    def test_get_pending_empty(self):
        from tip_tracker import get_pending
        pending = get_pending(self.path)
        self.assertEqual(pending, [])

    def test_get_by_source(self):
        from tip_tracker import add_tip, get_by_source
        add_tip("CCA tip", source="cca-desktop", path=self.path)
        add_tip("Kalshi tip", source="kalshi-main", path=self.path)
        add_tip("CLI tip", source="cca-cli1", path=self.path)
        cca_tips = get_by_source("cca-desktop", self.path)
        self.assertEqual(len(cca_tips), 1)
        self.assertEqual(cca_tips[0]["text"], "CCA tip")

    def test_get_stats(self):
        from tip_tracker import add_tip, update_status, get_stats
        add_tip("A", source="cca", path=self.path)
        t2 = add_tip("B", source="cca", path=self.path)
        t3 = add_tip("C", source="kalshi", path=self.path)
        update_status(t2["id"], "implemented", path=self.path)
        update_status(t3["id"], "skipped", path=self.path)
        stats = get_stats(self.path)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["implemented"], 1)
        self.assertEqual(stats["skipped"], 1)


class TestTipExtraction(unittest.TestCase):
    """Test extracting tips from assistant messages."""

    def test_extract_from_standard_format(self):
        from tip_tracker import extract_tip
        text = "Here is the code.\n\nAdvancement tip: Use pytest -x for fast failure on first error."
        tip = extract_tip(text)
        self.assertEqual(tip, "Use pytest -x for fast failure on first error.")

    def test_extract_case_insensitive(self):
        from tip_tracker import extract_tip
        text = "Done.\n\nadvancement tip: Always read before editing."
        tip = extract_tip(text)
        self.assertEqual(tip, "Always read before editing.")

    def test_no_tip_returns_none(self):
        from tip_tracker import extract_tip
        text = "Here is the code. All tests pass."
        tip = extract_tip(text)
        self.assertIsNone(tip)

    def test_extract_with_colon_in_tip(self):
        from tip_tracker import extract_tip
        text = "Advancement tip: The memory system now supports: search, list, and stats."
        tip = extract_tip(text)
        self.assertEqual(tip, "The memory system now supports: search, list, and stats.")

    def test_extract_multiline_tip(self):
        from tip_tracker import extract_tip
        text = "Done.\n\nAdvancement tip: Consider using TDD for all new features."
        tip = extract_tip(text)
        self.assertEqual(tip, "Consider using TDD for all new features.")

    def test_extract_with_backticks(self):
        from tip_tracker import extract_tip
        text = "Advancement tip: The `--verbose` flag in pytest shows detailed output."
        tip = extract_tip(text)
        self.assertEqual(tip, "The `--verbose` flag in pytest shows detailed output.")


class TestTipFormatting(unittest.TestCase):
    """Test formatting tips for display."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_format_for_init(self):
        """Format pending tips for /cca-init briefing."""
        from tip_tracker import add_tip, format_for_init
        add_tip("Tip A", source="cca-desktop", session="S88", path=self.path)
        add_tip("Tip B", source="kalshi-main", session="S104", path=self.path)
        output = format_for_init(self.path)
        self.assertIn("2 pending", output)
        self.assertIn("Tip A", output)
        self.assertIn("Tip B", output)

    def test_format_for_init_empty(self):
        from tip_tracker import format_for_init
        output = format_for_init(self.path)
        self.assertEqual(output, "")

    def test_format_for_init_caps_at_5(self):
        """Show at most 5 tips in init briefing to avoid clutter."""
        from tip_tracker import add_tip, format_for_init
        for i in range(10):
            add_tip(f"Tip {i}", source="cca", path=self.path)
        output = format_for_init(self.path)
        self.assertIn("10 pending", output)
        # Should show at most 5 tip texts
        tip_count = output.count("Tip ")
        self.assertLessEqual(tip_count, 7)  # "10 pending tips" + up to 5 listed + "...5 more"


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
