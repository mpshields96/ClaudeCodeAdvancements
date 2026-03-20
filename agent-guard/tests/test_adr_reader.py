#!/usr/bin/env python3
"""Tests for adr_reader.py — MT-20 Senior Dev Agent Full Vision: ADR awareness.

ADRReader discovers Architectural Decision Records in a project and surfaces
relevant decisions when code is written or edited. Prevents accidental
violations of recorded architectural choices.

ADR formats supported:
- MADR (Markdown Architectural Decision Records): Status: field in body
- Nygard format: ## Status section
- Simple frontmatter: status: accepted

Tests cover:
- ADR file discovery (multiple directory conventions)
- Status parsing (accepted/proposed/deprecated/superseded)
- Title extraction
- Summary extraction (first decision paragraph)
- Relevance matching (file path and keyword overlap)
- Hook I/O format
- Graceful degradation (no ADR directory found)
- Edge cases
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from adr_reader import ADRReader, ADR, parse_adr_file


class TestADRDataclass(unittest.TestCase):
    """Test ADR dataclass."""

    def test_fields(self):
        a = ADR(path="docs/adr/0001-use-sqlite.md", title="Use SQLite", status="accepted", summary="We decided to use SQLite for local storage.")
        self.assertEqual(a.title, "Use SQLite")
        self.assertEqual(a.status, "accepted")

    def test_to_dict(self):
        a = ADR(path="docs/adr/0001.md", title="Test", status="accepted", summary="Summary")
        d = a.to_dict()
        self.assertIn("path", d)
        self.assertIn("title", d)
        self.assertIn("status", d)
        self.assertIn("summary", d)


class TestParseADRFile(unittest.TestCase):
    """Test standalone parse_adr_file() function."""

    def test_madr_format(self):
        content = """# Use SQLite for Local Storage

## Status

Accepted

## Context

We need local storage.

## Decision

We will use SQLite.
"""
        adr = parse_adr_file("0001-use-sqlite.md", content)
        self.assertEqual(adr.title, "Use SQLite for Local Storage")
        self.assertEqual(adr.status, "accepted")

    def test_inline_status_field(self):
        content = """# Use Redis for Caching

Status: Proposed

We decided to use Redis.
"""
        adr = parse_adr_file("0002-redis.md", content)
        self.assertEqual(adr.status, "proposed")
        self.assertEqual(adr.title, "Use Redis for Caching")

    def test_deprecated_status(self):
        content = """# Old Auth Method

## Status

Deprecated

Old decision.
"""
        adr = parse_adr_file("0003-old-auth.md", content)
        self.assertEqual(adr.status, "deprecated")

    def test_superseded_status(self):
        content = """# Original DB Choice

Status: Superseded by 0005-postgresql.md

We originally used MySQL.
"""
        adr = parse_adr_file("0004-mysql.md", content)
        self.assertEqual(adr.status, "superseded")

    def test_unknown_status_defaults(self):
        content = """# Some Decision

No status line here.
"""
        adr = parse_adr_file("0005.md", content)
        self.assertIn(adr.status, ("unknown", "proposed", "accepted"))

    def test_summary_extracted(self):
        content = """# Use JSONL for logging

## Status

Accepted

## Decision

We will use JSONL for all logging to allow streaming processing.
"""
        adr = parse_adr_file("0006.md", content)
        self.assertIsInstance(adr.summary, str)
        self.assertTrue(len(adr.summary) > 0)

    def test_empty_content(self):
        adr = parse_adr_file("empty.md", "")
        self.assertIsInstance(adr, ADR)

    def test_path_preserved(self):
        adr = parse_adr_file("docs/adr/0001.md", "# Title\nStatus: Accepted")
        self.assertEqual(adr.path, "docs/adr/0001.md")


class TestADRDiscovery(unittest.TestCase):
    """Test ADR directory discovery and file parsing."""

    def setUp(self):
        self.reader = ADRReader()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_adr(self, rel_path: str, content: str):
        full = os.path.join(self.tmpdir, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return full

    def test_discover_docs_adr(self):
        self._write_adr("docs/adr/0001-sqlite.md", "# Use SQLite\n\nStatus: Accepted\n")
        adrs = self.reader.discover(self.tmpdir)
        self.assertEqual(len(adrs), 1)
        self.assertEqual(adrs[0].title, "Use SQLite")

    def test_discover_adr_directory(self):
        self._write_adr("adr/0001-decision.md", "# Big Decision\n\nStatus: Accepted\n")
        adrs = self.reader.discover(self.tmpdir)
        self.assertEqual(len(adrs), 1)

    def test_discover_docs_decisions(self):
        self._write_adr("docs/decisions/001-arch.md", "# Architecture Choice\n\nStatus: Accepted\n")
        adrs = self.reader.discover(self.tmpdir)
        self.assertEqual(len(adrs), 1)

    def test_discover_multiple_adrs(self):
        self._write_adr("docs/adr/0001-a.md", "# Decision A\n\nStatus: Accepted\n")
        self._write_adr("docs/adr/0002-b.md", "# Decision B\n\nStatus: Deprecated\n")
        adrs = self.reader.discover(self.tmpdir)
        self.assertEqual(len(adrs), 2)

    def test_discover_no_adr_directory(self):
        adrs = self.reader.discover(self.tmpdir)
        self.assertEqual(adrs, [])

    def test_discover_nonexistent_root(self):
        adrs = self.reader.discover("/nonexistent/path/123xyz")
        self.assertEqual(adrs, [])

    def test_only_markdown_files(self):
        self._write_adr("docs/adr/0001-decision.md", "# Decision\n\nStatus: Accepted\n")
        self._write_adr("docs/adr/notes.txt", "not an adr")
        adrs = self.reader.discover(self.tmpdir)
        self.assertEqual(len(adrs), 1)


class TestADRRelevance(unittest.TestCase):
    """Test find_relevant — which ADRs are relevant to a file/content."""

    def setUp(self):
        self.reader = ADRReader()

    def _make_adr(self, title: str, status: str, summary: str, path: str = "docs/adr/0001.md") -> ADR:
        return ADR(path=path, title=title, status=status, summary=summary)

    def test_deprecated_adr_always_relevant(self):
        adr = self._make_adr("Old Auth", "deprecated", "We no longer use basic auth.")
        result = self.reader.find_relevant([adr], "src/auth.py", "def authenticate(): pass")
        self.assertIn(adr, result)

    def test_accepted_adr_relevant_by_keyword(self):
        adr = self._make_adr("Use SQLite", "accepted", "All persistence uses SQLite. No other DB allowed.")
        result = self.reader.find_relevant([adr], "src/storage.py", "import sqlite3")
        self.assertIn(adr, result)

    def test_accepted_adr_not_relevant_for_unrelated_file(self):
        adr = self._make_adr("Use Redis for Caching", "accepted", "Cache layer must use Redis.")
        result = self.reader.find_relevant([adr], "src/ui/button.py", "def render(): pass")
        # An unrelated file should not trigger Redis ADR
        self.assertNotIn(adr, result)

    def test_deprecated_adr_for_unrelated_file_irrelevant(self):
        adr = self._make_adr("Old Database", "deprecated", "We used MySQL. Don't use MySQL.")
        result = self.reader.find_relevant([adr], "src/ui/render.py", "def render(): pass")
        # Deprecated + no keyword match = not relevant
        self.assertNotIn(adr, result)

    def test_only_accepted_and_deprecated_surfaced(self):
        adrs = [
            self._make_adr("Proposed Decision", "proposed", "Still under discussion."),
            self._make_adr("Superseded Decision", "superseded", "Old approach."),
        ]
        result = self.reader.find_relevant(adrs, "src/anything.py", "proposed superseded content")
        # Proposed and superseded should not be surfaced (not actionable)
        self.assertEqual(result, [])

    def test_empty_adrs_returns_empty(self):
        result = self.reader.find_relevant([], "src/foo.py", "content")
        self.assertEqual(result, [])


class TestADRHookOutput(unittest.TestCase):
    """Test hook_output — PostToolUse hook integration."""

    def setUp(self):
        self.reader = ADRReader()

    def test_unknown_tool_returns_empty(self):
        payload = {"tool_name": "Read", "tool_input": {"file_path": "foo.py"}}
        result = self.reader.hook_output(payload, [])
        self.assertEqual(result, {})

    def test_no_relevant_adrs_returns_empty(self):
        payload = {"tool_name": "Write", "tool_input": {"content": "x = 1", "file_path": "foo.py"}}
        result = self.reader.hook_output(payload, [])
        self.assertEqual(result, {})

    def test_relevant_adr_emits_context(self):
        adrs = [ADR(path="docs/adr/0001.md", title="Use SQLite", status="accepted", summary="All DB must be SQLite.")]
        payload = {"tool_name": "Write", "tool_input": {"content": "import sqlite3", "file_path": "db.py"}}
        result = self.reader.hook_output(payload, adrs)
        self.assertIn("additionalContext", result)

    def test_context_mentions_adr(self):
        adrs = [ADR(path="docs/adr/0001.md", title="Use SQLite", status="accepted", summary="Use SQLite for DB.")]
        payload = {"tool_name": "Write", "tool_input": {"content": "import sqlite3", "file_path": "db.py"}}
        result = self.reader.hook_output(payload, adrs)
        if "additionalContext" in result:
            self.assertIn("ADR", result["additionalContext"])

    def test_context_bounded_at_500_chars(self):
        adrs = [
            ADR(path=f"docs/adr/{i:04d}.md", title=f"Decision {i}", status="accepted",
                summary="A" * 200)
            for i in range(10)
        ]
        payload = {"tool_name": "Write", "tool_input": {"content": "anything", "file_path": "file.py"}}
        result = self.reader.hook_output(payload, adrs)
        if "additionalContext" in result:
            self.assertLessEqual(len(result["additionalContext"]), 500)

    def test_returns_dict(self):
        payload = {"tool_name": "Write", "tool_input": {"content": "x=1", "file_path": "f.py"}}
        result = self.reader.hook_output(payload, [])
        self.assertIsInstance(result, dict)

    def test_edit_tool_processed(self):
        adrs = [ADR(path="docs/adr/0001.md", title="No Globals", status="accepted", summary="Avoid global state.")]
        payload = {"tool_name": "Edit", "tool_input": {"file_path": "module.py", "old_string": "x", "new_string": "GLOBAL = 1"}}
        result = self.reader.hook_output(payload, adrs)
        self.assertIsInstance(result, dict)

    def test_empty_payload_returns_empty(self):
        result = self.reader.hook_output({}, [])
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
