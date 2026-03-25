#!/usr/bin/env python3
"""Tests for scan_executor.py — MT-40 Phase 4: Automated scan pipeline.

Tests the orchestrator that ties scan_scheduler, nuclear_fetcher, and
mt_originator into a single automated pipeline for /cca-auto.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scan_executor import (
    ScanResult,
    ScanExecutor,
    should_scan_now,
    run_auto_scan,
)


class TestScanResult(unittest.TestCase):
    """Tests for ScanResult data class."""

    def test_create_scan_result(self):
        r = ScanResult(
            slug="claudecode",
            posts_fetched=25,
            new_findings=3,
            mt_proposals=1,
            scan_command="python3 nuclear_fetcher.py claudecode 25 week",
        )
        self.assertEqual(r.slug, "claudecode")
        self.assertEqual(r.posts_fetched, 25)
        self.assertEqual(r.new_findings, 3)
        self.assertEqual(r.mt_proposals, 1)

    def test_to_dict(self):
        r = ScanResult(slug="claudeai", posts_fetched=10, new_findings=0, mt_proposals=0)
        d = r.to_dict()
        self.assertEqual(d["slug"], "claudeai")
        self.assertIn("posts_fetched", d)

    def test_scan_result_defaults(self):
        r = ScanResult(slug="test")
        self.assertEqual(r.posts_fetched, 0)
        self.assertEqual(r.new_findings, 0)
        self.assertEqual(r.mt_proposals, 0)
        self.assertIsNone(r.scan_command)
        self.assertIsNone(r.error)


class TestScanExecutor(unittest.TestCase):
    """Tests for ScanExecutor orchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.findings_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.unlink(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _write_registry(self, data):
        with open(self.registry_path, "w") as f:
            json.dump(data, f)

    def _read_registry(self):
        with open(self.registry_path) as f:
            return json.load(f)

    def test_init(self):
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        self.assertIsNotNone(ex)

    def test_check_staleness_all_fresh(self):
        now = datetime.now(timezone.utc).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": now},
            "claudeai": {"last_scan": now},
            "vibecoding": {"last_scan": now},
        })
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        result = ex.check_staleness()
        self.assertFalse(result["should_scan"])
        self.assertEqual(result["stale_count"], 0)

    def test_check_staleness_with_stale_subs(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": old_date},
        })
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        result = ex.check_staleness()
        self.assertTrue(result["should_scan"])
        self.assertGreater(result["stale_count"], 0)

    def test_check_staleness_no_registry(self):
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        result = ex.check_staleness()
        self.assertTrue(result["should_scan"])

    def test_update_registry_creates_file(self):
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        ex.update_registry("claudecode", posts_fetched=25)
        self.assertTrue(os.path.exists(self.registry_path))
        data = self._read_registry()
        self.assertIn("claudecode", data)
        self.assertIn("last_scan", data["claudecode"])
        self.assertEqual(data["claudecode"]["posts_fetched"], 25)

    def test_update_registry_preserves_existing(self):
        now = datetime.now(timezone.utc).isoformat()
        self._write_registry({"claudeai": {"last_scan": now, "posts_fetched": 15}})
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        ex.update_registry("claudecode", posts_fetched=25)
        data = self._read_registry()
        self.assertIn("claudeai", data)
        self.assertIn("claudecode", data)

    def test_generate_scan_commands(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": old_date},
            "claudeai": {"last_scan": now},
            "vibecoding": {"last_scan": now},
        })
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        commands = ex.generate_scan_commands()
        self.assertGreater(len(commands), 0)
        slugs = [c["slug"] for c in commands]
        self.assertIn("claudecode", slugs)
        self.assertIn("nuclear_fetcher.py", commands[0]["command"])

    def test_generate_scan_commands_empty_when_fresh(self):
        now = datetime.now(timezone.utc).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": now},
            "claudeai": {"last_scan": now},
            "vibecoding": {"last_scan": now},
        })
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        commands = ex.generate_scan_commands()
        self.assertEqual(len(commands), 0)

    def test_generate_scan_commands_limit(self):
        """Should limit to max_scans_per_run."""
        ex = ScanExecutor(
            registry_path=self.registry_path,
            findings_path=self.findings_path,
            max_scans_per_run=1,
        )
        commands = ex.generate_scan_commands()
        self.assertLessEqual(len(commands), 1)

    def test_format_scan_brief(self):
        results = [
            ScanResult(slug="claudecode", posts_fetched=25, new_findings=3, mt_proposals=1),
            ScanResult(slug="claudeai", posts_fetched=15, new_findings=1, mt_proposals=0),
        ]
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        brief = ex.format_brief(results)
        self.assertIn("claudecode", brief)
        self.assertIn("25 posts", brief)
        self.assertIn("3 findings", brief)

    def test_format_scan_brief_empty(self):
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        brief = ex.format_brief([])
        self.assertIn("No scans", brief)

    def test_format_scan_brief_with_error(self):
        results = [
            ScanResult(slug="claudecode", error="Network timeout"),
        ]
        ex = ScanExecutor(registry_path=self.registry_path, findings_path=self.findings_path)
        brief = ex.format_brief(results)
        self.assertIn("ERROR", brief)


class TestConvenienceFunctions(unittest.TestCase):
    """Tests for module-level convenience functions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")

    def tearDown(self):
        for f in os.listdir(self.tmpdir):
            os.unlink(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_should_scan_now_true(self):
        result = should_scan_now(registry_path=self.registry_path)
        self.assertTrue(result)  # No registry = all stale

    def test_should_scan_now_false(self):
        now = datetime.now(timezone.utc).isoformat()
        with open(self.registry_path, "w") as f:
            json.dump({
                "claudecode": {"last_scan": now},
                "claudeai": {"last_scan": now},
                "vibecoding": {"last_scan": now},
            }, f)
        result = should_scan_now(registry_path=self.registry_path)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
