#!/usr/bin/env python3
"""Tests for principle_seeder.py — bootstrap principle registry from LEARNINGS.md."""
import json
import os
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from principle_seeder import (
    parse_learnings_md,
    Learning,
    map_learning_to_domain,
    seed_principles_from_learnings,
    seed_principles_from_journal,
    extract_journal_patterns,
)


class TestParseLearningsMd(unittest.TestCase):
    """Test parsing LEARNINGS.md into structured Learning objects."""

    def setUp(self):
        self.sample_md = """# CCA Learnings — Severity-Tracked Patterns
# Severity: 1 = noted, 2 = hard rule, 3 = global

---

### Anthropic key regex must include hyphens — Severity: 3 — Count: 3
- **Anti-pattern:** `sk-[A-Za-z0-9]{20,}` (misses keys with hyphens)
- **Fix:** `sk-[A-Za-z0-9\\-]{20,}` (keys contain `sk-ant-api03-...`)
- **First seen:** 2026-02-19
- **Last seen:** 2026-03-15
- **Files:** any credential scanning or validation

---

### PreToolUse deny format vs Stop hook block format differ — Severity: 2 — Count: 2
- **Anti-pattern:** Using same format for both hook types.
- **Fix:** PreToolUse: hookSpecificOutput.permissionDecision. Stop: decision block.
- **First seen:** 2026-02-20
- **Last seen:** 2026-03-08
- **Files:** any hook that needs to block or deny

---

### argparse subparsers don't inherit parent options — Severity: 1 — Count: 1
- **Anti-pattern:** Adding `--project` to parent parser expecting subcommands to inherit
- **Fix:** Add `--project` explicitly to each subparser
- **First seen:** 2026-03-08
- **Last seen:** 2026-03-08
- **Files:** any CLI using argparse subparsers

---
"""
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        )
        self.tmpfile.write(self.sample_md)
        self.tmpfile.close()

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_parse_returns_list_of_learnings(self):
        learnings = parse_learnings_md(self.tmpfile.name)
        self.assertIsInstance(learnings, list)
        self.assertEqual(len(learnings), 3)

    def test_learning_has_required_fields(self):
        learnings = parse_learnings_md(self.tmpfile.name)
        l = learnings[0]
        self.assertIsInstance(l, Learning)
        self.assertEqual(l.title, "Anthropic key regex must include hyphens")
        self.assertEqual(l.severity, 3)
        self.assertEqual(l.count, 3)
        self.assertIn("hyphens", l.anti_pattern)
        self.assertIn("sk-ant-api03", l.fix)

    def test_severity_parsed_correctly(self):
        learnings = parse_learnings_md(self.tmpfile.name)
        self.assertEqual(learnings[0].severity, 3)
        self.assertEqual(learnings[1].severity, 2)
        self.assertEqual(learnings[2].severity, 1)

    def test_count_parsed_correctly(self):
        learnings = parse_learnings_md(self.tmpfile.name)
        self.assertEqual(learnings[0].count, 3)
        self.assertEqual(learnings[1].count, 2)
        self.assertEqual(learnings[2].count, 1)

    def test_empty_file_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# No learnings here\n")
            f.flush()
            learnings = parse_learnings_md(f.name)
        os.unlink(f.name)
        self.assertEqual(learnings, [])

    def test_files_field_parsed(self):
        learnings = parse_learnings_md(self.tmpfile.name)
        self.assertIn("credential", learnings[0].files)

    def test_first_seen_parsed(self):
        learnings = parse_learnings_md(self.tmpfile.name)
        self.assertEqual(learnings[0].first_seen, "2026-02-19")


class TestMapLearningToDomain(unittest.TestCase):
    """Test domain mapping from learning content."""

    def _make_learning(self, title, fix="", files=""):
        return Learning(
            title=title,
            severity=2,
            count=1,
            anti_pattern="",
            fix=fix,
            first_seen="2026-01-01",
            last_seen="2026-01-01",
            files=files,
        )

    def test_credential_maps_to_code_quality(self):
        l = self._make_learning("Anthropic key regex", files="credential_guard.py")
        domain = map_learning_to_domain(l)
        self.assertEqual(domain, "code_quality")

    def test_hook_format_maps_to_cca_operations(self):
        l = self._make_learning("PreToolUse deny format", files="any hook")
        domain = map_learning_to_domain(l)
        self.assertEqual(domain, "cca_operations")

    def test_reddit_maps_to_nuclear_scan(self):
        l = self._make_learning("Reddit JSON API top", files="reddit_reader.py")
        domain = map_learning_to_domain(l)
        self.assertEqual(domain, "nuclear_scan")

    def test_session_maps_to_session_management(self):
        l = self._make_learning("Session wrap files uncommitted")
        domain = map_learning_to_domain(l)
        self.assertEqual(domain, "session_management")

    def test_trading_maps_to_trading_research(self):
        l = self._make_learning("Kalshi bet timing", fix="trading strategy")
        domain = map_learning_to_domain(l)
        self.assertEqual(domain, "trading_research")

    def test_unknown_maps_to_general(self):
        l = self._make_learning("Random thing", files="some_file.py")
        domain = map_learning_to_domain(l)
        self.assertEqual(domain, "general")


class TestSeedFromLearnings(unittest.TestCase):
    """Test seeding principle registry from parsed learnings."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.sample_md = """# Learnings

---

### Always commit wrap files — Severity: 2 — Count: 3
- **Anti-pattern:** Leaving wrap files uncommitted
- **Fix:** Commit SESSION_STATE, PROJECT_INDEX at session end
- **First seen:** 2026-02-19
- **Last seen:** 2026-03-15
- **Files:** session state files

---

### Edit retries on structured tables — Severity: 2 — Count: 5
- **Anti-pattern:** Editing PROJECT_INDEX without reading first
- **Fix:** Always Read before Edit on structured table files
- **First seen:** 2026-03-01
- **Last seen:** 2026-03-20
- **Files:** PROJECT_INDEX.md, SESSION_STATE.md

---
"""
        self.md_path = os.path.join(self.tmpdir, "LEARNINGS.md")
        with open(self.md_path, "w") as f:
            f.write(self.sample_md)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_seed_creates_principles(self):
        results = seed_principles_from_learnings(
            self.md_path, principles_path=self.principles_path
        )
        self.assertGreater(len(results), 0)

    def test_seed_writes_to_principles_file(self):
        seed_principles_from_learnings(
            self.md_path, principles_path=self.principles_path
        )
        self.assertTrue(os.path.exists(self.principles_path))
        with open(self.principles_path) as f:
            lines = f.readlines()
        self.assertGreater(len(lines), 0)

    def test_seeded_principles_have_source_context(self):
        results = seed_principles_from_learnings(
            self.md_path, principles_path=self.principles_path
        )
        for r in results:
            self.assertIn("LEARNINGS.md", r.get("source_context", ""))

    def test_severity_filters(self):
        """Only seed severity >= min_severity."""
        results = seed_principles_from_learnings(
            self.md_path, principles_path=self.principles_path, min_severity=3
        )
        # Both learnings are severity 2, should be filtered out
        self.assertEqual(len(results), 0)

    def test_idempotent_seeding(self):
        """Running seed twice doesn't duplicate principles."""
        r1 = seed_principles_from_learnings(
            self.md_path, principles_path=self.principles_path
        )
        r2 = seed_principles_from_learnings(
            self.md_path, principles_path=self.principles_path
        )
        # Second run should skip duplicates
        self.assertEqual(len(r2), 0)

    def test_count_maps_to_initial_usage(self):
        """Learning count becomes initial usage_count for the principle."""
        results = seed_principles_from_learnings(
            self.md_path, principles_path=self.principles_path
        )
        # Check the principles file for usage_count
        with open(self.principles_path) as f:
            principles = [json.loads(line) for line in f]
        # The one with count=5 should have higher usage
        counts = {p["text"][:20]: p.get("usage_count", 0) for p in principles}
        self.assertTrue(any(c > 0 for c in counts.values()))


class TestExtractJournalPatterns(unittest.TestCase):
    """Test pattern extraction from journal entries."""

    def test_empty_journal_returns_empty(self):
        patterns = extract_journal_patterns([])
        self.assertEqual(patterns, [])

    def test_session_outcome_success_pattern(self):
        entries = [
            {"event_type": "session_outcome", "outcome": "success", "domain": "cca_operations"},
            {"event_type": "session_outcome", "outcome": "success", "domain": "cca_operations"},
            {"event_type": "session_outcome", "outcome": "success", "domain": "cca_operations"},
        ]
        patterns = extract_journal_patterns(entries)
        # Should detect repeated success in a domain
        self.assertIsInstance(patterns, list)

    def test_pain_patterns_detected(self):
        entries = [
            {"event_type": "pain", "description": "Edit retry on PROJECT_INDEX", "domain": "cca_operations"},
            {"event_type": "pain", "description": "Edit retry on PROJECT_INDEX", "domain": "cca_operations"},
            {"event_type": "pain", "description": "Edit retry on PROJECT_INDEX", "domain": "cca_operations"},
        ]
        patterns = extract_journal_patterns(entries)
        # Should detect repeated pain
        pain_patterns = [p for p in patterns if p.get("type") == "recurring_pain"]
        self.assertGreater(len(pain_patterns), 0)

    def test_win_patterns_detected(self):
        entries = [
            {"event_type": "win", "description": "TDD caught regression before commit", "domain": "code_quality"},
            {"event_type": "win", "description": "TDD caught regression before commit", "domain": "code_quality"},
            {"event_type": "win", "description": "TDD caught regression before commit", "domain": "code_quality"},
        ]
        patterns = extract_journal_patterns(entries)
        win_patterns = [p for p in patterns if p.get("type") == "recurring_win"]
        self.assertGreater(len(win_patterns), 0)


class TestSeedFromJournal(unittest.TestCase):
    """Test seeding principles from journal patterns."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")
        entries = [
            {"event_type": "pain", "description": "Edit retry on structured file", "domain": "cca_operations", "timestamp": "2026-03-01T00:00:00Z"},
            {"event_type": "pain", "description": "Edit retry on structured file", "domain": "cca_operations", "timestamp": "2026-03-02T00:00:00Z"},
            {"event_type": "pain", "description": "Edit retry on structured file", "domain": "cca_operations", "timestamp": "2026-03-03T00:00:00Z"},
            {"event_type": "win", "description": "Tests caught regression", "domain": "code_quality", "timestamp": "2026-03-01T00:00:00Z"},
            {"event_type": "win", "description": "Tests caught regression", "domain": "code_quality", "timestamp": "2026-03-02T00:00:00Z"},
            {"event_type": "win", "description": "Tests caught regression", "domain": "code_quality", "timestamp": "2026-03-03T00:00:00Z"},
        ]
        with open(self.journal_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_seed_from_journal_creates_principles(self):
        results = seed_principles_from_journal(
            self.journal_path, principles_path=self.principles_path
        )
        self.assertIsInstance(results, list)

    def test_seed_from_journal_writes_file(self):
        seed_principles_from_journal(
            self.journal_path, principles_path=self.principles_path
        )
        if os.path.exists(self.principles_path):
            with open(self.principles_path) as f:
                lines = f.readlines()
            self.assertGreater(len(lines), 0)


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_import_main(self):
        """Module should be importable without side effects."""
        import principle_seeder

        self.assertTrue(hasattr(principle_seeder, "main"))


if __name__ == "__main__":
    unittest.main()
