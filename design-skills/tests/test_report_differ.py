"""Tests for report differ — compares two JSON sidecar reports (MT-33 Phase 6).

The differ takes two report data dicts (or JSON paths) and produces a structured
diff highlighting what changed: test growth, new MTs, P&L changes, APF movement, etc.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from report_differ import ReportDiffer


class TestReportDiffer(unittest.TestCase):
    """Tests for ReportDiffer class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.old_report = {
            "date": "2026-03-20",
            "session": 120,
            "summary": {
                "total_tests": 7500,
                "test_suites": 190,
                "total_loc": 38000,
                "source_loc": 23000,
                "test_loc": 15000,
                "git_commits": 480,
                "total_modules": 8,
                "master_tasks": 34,
                "completed_tasks": 10,
                "in_progress_tasks": 9,
                "source_files": 85,
                "test_files": 55,
                "total_findings": 180,
                "total_papers": 12,
                "not_started_tasks": 10,
                "blocked_tasks": 5,
                "project_age_days": 29,
                "live_hooks": 15,
                "total_delivered": 130,
                "passing_tests": 7500,
            },
            "modules": [
                {"name": "Memory System", "tests": 340, "loc": 1200},
                {"name": "Agent Guard", "tests": 1000, "loc": 4800},
                {"name": "Design Skills", "tests": 900, "loc": 3000},
            ],
            "master_tasks_complete": [
                {"id": "MT-9", "name": "Autonomous Scanner"},
            ],
            "master_tasks_active": [
                {"id": "MT-20", "name": "Senior Dev"},
                {"id": "MT-21", "name": "Hivemind"},
            ],
            "master_tasks_pending": [
                {"id": "MT-33", "name": "Strategic Report"},
            ],
            "kalshi_analytics": {
                "available": True,
                "summary": {"total_pnl_usd": 30.00, "win_rate_pct": 58.0, "settled_trades": 100},
            },
            "learning_intelligence": {
                "available": True,
                "journal": {"total_entries": 300, "win_pain_ratio": 1.8},
                "apf": {"current_apf": 20.5},
            },
        }
        self.new_report = {
            "date": "2026-03-22",
            "session": 122,
            "summary": {
                "total_tests": 7870,
                "test_suites": 199,
                "total_loc": 40000,
                "source_loc": 25000,
                "test_loc": 15000,
                "git_commits": 500,
                "total_modules": 8,
                "master_tasks": 35,
                "completed_tasks": 12,
                "in_progress_tasks": 8,
                "source_files": 90,
                "test_files": 60,
                "total_findings": 200,
                "total_papers": 15,
                "not_started_tasks": 10,
                "blocked_tasks": 5,
                "project_age_days": 31,
                "live_hooks": 15,
                "total_delivered": 150,
                "passing_tests": 7870,
            },
            "modules": [
                {"name": "Memory System", "tests": 340, "loc": 1200},
                {"name": "Agent Guard", "tests": 1073, "loc": 5000},
                {"name": "Design Skills", "tests": 1082, "loc": 3500},
            ],
            "master_tasks_complete": [
                {"id": "MT-9", "name": "Autonomous Scanner"},
                {"id": "MT-10", "name": "YoYo Loop"},
            ],
            "master_tasks_active": [
                {"id": "MT-20", "name": "Senior Dev"},
                {"id": "MT-33", "name": "Strategic Report"},
            ],
            "master_tasks_pending": [
                {"id": "MT-21", "name": "Hivemind"},
            ],
            "kalshi_analytics": {
                "available": True,
                "summary": {"total_pnl_usd": 45.50, "win_rate_pct": 62.5, "settled_trades": 120},
            },
            "learning_intelligence": {
                "available": True,
                "journal": {"total_entries": 335, "win_pain_ratio": 2.1},
                "apf": {"current_apf": 22.7},
            },
        }

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ── diff_reports ──────────────────────────────────────────────────

    def test_diff_returns_structured_result(self):
        """Diff result has expected top-level keys."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        self.assertIn("sessions", result)
        self.assertIn("summary_changes", result)
        self.assertIn("module_changes", result)
        self.assertIn("mt_changes", result)
        self.assertIn("kalshi_changes", result)
        self.assertIn("learning_changes", result)

    def test_diff_sessions_metadata(self):
        """Sessions metadata shows old and new session info."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        self.assertEqual(result["sessions"]["old"], 120)
        self.assertEqual(result["sessions"]["new"], 122)
        self.assertEqual(result["sessions"]["old_date"], "2026-03-20")
        self.assertEqual(result["sessions"]["new_date"], "2026-03-22")

    # ── summary_changes ───────────────────────────────────────────────

    def test_diff_test_growth(self):
        """Detects test count increase."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        changes = result["summary_changes"]
        self.assertEqual(changes["total_tests"]["old"], 7500)
        self.assertEqual(changes["total_tests"]["new"], 7870)
        self.assertEqual(changes["total_tests"]["delta"], 370)

    def test_diff_loc_growth(self):
        """Detects LOC increase."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        changes = result["summary_changes"]
        self.assertEqual(changes["total_loc"]["delta"], 2000)

    def test_diff_commit_growth(self):
        """Detects commit count increase."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        self.assertEqual(result["summary_changes"]["git_commits"]["delta"], 20)

    # ── module_changes ────────────────────────────────────────────────

    def test_diff_module_test_changes(self):
        """Detects per-module test count changes."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        changes = result["module_changes"]
        # Memory System unchanged
        mem = next((c for c in changes if c["name"] == "Memory System"), None)
        self.assertIsNotNone(mem)
        self.assertEqual(mem["tests_delta"], 0)
        # Agent Guard grew
        ag = next((c for c in changes if c["name"] == "Agent Guard"), None)
        self.assertEqual(ag["tests_delta"], 73)
        # Design Skills grew
        ds = next((c for c in changes if c["name"] == "Design Skills"), None)
        self.assertEqual(ds["tests_delta"], 182)

    def test_diff_module_loc_changes(self):
        """Detects per-module LOC changes."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        ag = next((c for c in result["module_changes"] if c["name"] == "Agent Guard"), None)
        self.assertEqual(ag["loc_delta"], 200)

    def test_diff_new_module(self):
        """Handles modules that appear only in new report."""
        new = dict(self.new_report)
        new["modules"] = self.new_report["modules"] + [
            {"name": "New Module", "tests": 50, "loc": 300}
        ]
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, new)
        nm = next((c for c in result["module_changes"] if c["name"] == "New Module"), None)
        self.assertIsNotNone(nm)
        self.assertEqual(nm["tests_delta"], 50)
        self.assertTrue(nm["is_new"])

    # ── mt_changes ────────────────────────────────────────────────────

    def test_diff_newly_completed_mts(self):
        """Detects MTs that moved to completed."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        newly_completed = result["mt_changes"]["newly_completed"]
        ids = [mt["id"] for mt in newly_completed]
        self.assertIn("MT-10", ids)

    def test_diff_newly_active_mts(self):
        """Detects MTs that became active."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        newly_active = result["mt_changes"]["newly_active"]
        ids = [mt["id"] for mt in newly_active]
        self.assertIn("MT-33", ids)

    def test_diff_mt_counts(self):
        """Reports overall MT count changes."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        self.assertEqual(result["mt_changes"]["completed_delta"], 2)

    # ── kalshi_changes ────────────────────────────────────────────────

    def test_diff_kalshi_pnl(self):
        """Detects Kalshi P&L change."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        k = result["kalshi_changes"]
        self.assertEqual(k["pnl_delta"], 15.50)
        self.assertAlmostEqual(k["win_rate_delta"], 4.5)

    def test_diff_kalshi_not_available(self):
        """Handles Kalshi data being unavailable in one or both reports."""
        old = dict(self.old_report)
        old["kalshi_analytics"] = {"available": False, "summary": {}}
        differ = ReportDiffer()
        result = differ.diff_reports(old, self.new_report)
        k = result["kalshi_changes"]
        self.assertIsNone(k["pnl_delta"])
        self.assertTrue(k["became_available"])

    # ── learning_changes ──────────────────────────────────────────────

    def test_diff_apf_change(self):
        """Detects APF score change."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        lc = result["learning_changes"]
        self.assertAlmostEqual(lc["apf_delta"], 2.2)

    def test_diff_journal_growth(self):
        """Detects journal entry growth."""
        differ = ReportDiffer()
        result = differ.diff_reports(self.old_report, self.new_report)
        lc = result["learning_changes"]
        self.assertEqual(lc["journal_delta"], 35)

    def test_diff_learning_not_available(self):
        """Handles learning data being unavailable."""
        old = dict(self.old_report)
        old["learning_intelligence"] = {"available": False, "journal": {}, "apf": {}}
        differ = ReportDiffer()
        result = differ.diff_reports(old, self.new_report)
        lc = result["learning_changes"]
        self.assertIsNone(lc["apf_delta"])

    # ── diff_from_files ───────────────────────────────────────────────

    def test_diff_from_files(self):
        """Can diff from file paths."""
        old_path = os.path.join(self.tmpdir, "old.json")
        new_path = os.path.join(self.tmpdir, "new.json")
        with open(old_path, "w") as f:
            json.dump(self.old_report, f)
        with open(new_path, "w") as f:
            json.dump(self.new_report, f)

        differ = ReportDiffer()
        result = differ.diff_from_files(old_path, new_path)
        self.assertEqual(result["sessions"]["old"], 120)
        self.assertEqual(result["sessions"]["new"], 122)

    def test_diff_from_files_missing(self):
        """Returns None if a file is missing."""
        differ = ReportDiffer()
        result = differ.diff_from_files("/nope/old.json", "/nope/new.json")
        self.assertIsNone(result)

    # ── format_summary ────────────────────────────────────────────────

    def test_format_summary_text(self):
        """Produces human-readable summary text."""
        differ = ReportDiffer()
        diff = differ.diff_reports(self.old_report, self.new_report)
        text = differ.format_summary(diff)
        self.assertIn("S120", text)
        self.assertIn("S122", text)
        self.assertIn("+370", text)  # test growth
        self.assertIn("MT-10", text)  # newly completed

    def test_format_summary_no_changes(self):
        """Handles case where reports are identical."""
        differ = ReportDiffer()
        diff = differ.diff_reports(self.old_report, self.old_report)
        text = differ.format_summary(diff)
        self.assertIn("No changes", text)


if __name__ == "__main__":
    unittest.main()
