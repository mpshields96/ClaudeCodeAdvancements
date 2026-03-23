"""Tests for JSON sidecar export alongside PDF reports (MT-33 Phase 6).

The sidecar is a machine-readable JSON file saved next to every PDF report,
enabling future sessions to diff reports and track trends without re-reading PDFs.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from report_generator import ReportSidecar


class TestReportSidecar(unittest.TestCase):
    """Tests for ReportSidecar class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sample_data = {
            "title": "ClaudeCodeAdvancements",
            "date": "2026-03-22",
            "session": 122,
            "summary": {
                "total_tests": 7870,
                "test_suites": 199,
                "total_modules": 8,
                "source_loc": 25000,
                "test_loc": 15000,
                "total_loc": 40000,
                "git_commits": 500,
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
                {"name": "Memory System", "tests": 340, "loc": 1200, "files": 5},
                {"name": "Agent Guard", "tests": 1073, "loc": 5000, "files": 15},
            ],
            "master_tasks_complete": [{"id": "MT-9", "name": "Autonomous Scanner"}],
            "master_tasks_active": [{"id": "MT-33", "name": "Strategic Report"}],
            "master_tasks_pending": [],
            "kalshi_analytics": {
                "available": True,
                "summary": {"total_pnl_usd": 45.50, "win_rate_pct": 62.5},
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

    # ── save_alongside_pdf ────────────────────────────────────────────

    def test_save_alongside_pdf_creates_json(self):
        """JSON sidecar is created next to the PDF."""
        pdf_path = os.path.join(self.tmpdir, "report.pdf")
        sidecar = ReportSidecar()
        result = sidecar.save_alongside_pdf(self.sample_data, pdf_path)
        expected = os.path.join(self.tmpdir, "report.json")
        self.assertEqual(result, expected)
        self.assertTrue(os.path.exists(expected))

    def test_save_alongside_pdf_valid_json(self):
        """Sidecar file contains valid, parseable JSON."""
        pdf_path = os.path.join(self.tmpdir, "report.pdf")
        sidecar = ReportSidecar()
        result = sidecar.save_alongside_pdf(self.sample_data, pdf_path)
        with open(result) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["session"], 122)

    def test_save_alongside_pdf_preserves_all_data(self):
        """All collected data is preserved in the sidecar."""
        pdf_path = os.path.join(self.tmpdir, "report.pdf")
        sidecar = ReportSidecar()
        result = sidecar.save_alongside_pdf(self.sample_data, pdf_path)
        with open(result) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["summary"]["total_tests"], 7870)
        self.assertEqual(loaded["kalshi_analytics"]["summary"]["total_pnl_usd"], 45.50)

    def test_save_alongside_pdf_custom_extension(self):
        """Works with PDF paths that have uppercase .PDF extension."""
        pdf_path = os.path.join(self.tmpdir, "REPORT.PDF")
        sidecar = ReportSidecar()
        result = sidecar.save_alongside_pdf(self.sample_data, pdf_path)
        expected = os.path.join(self.tmpdir, "REPORT.json")
        self.assertEqual(result, expected)

    def test_save_alongside_pdf_no_extension(self):
        """Works even if the output path has no extension."""
        pdf_path = os.path.join(self.tmpdir, "report")
        sidecar = ReportSidecar()
        result = sidecar.save_alongside_pdf(self.sample_data, pdf_path)
        expected = os.path.join(self.tmpdir, "report.json")
        self.assertEqual(result, expected)

    # ── save_to_archive ───────────────────────────────────────────────

    def test_save_to_archive_creates_directory(self):
        """Archive directory is created if it doesn't exist."""
        archive_dir = os.path.join(self.tmpdir, "archive")
        sidecar = ReportSidecar(archive_dir=archive_dir)
        result = sidecar.save_to_archive(self.sample_data)
        self.assertTrue(os.path.isdir(archive_dir))
        self.assertTrue(os.path.exists(result))

    def test_save_to_archive_date_named(self):
        """Archive file is named by date."""
        archive_dir = os.path.join(self.tmpdir, "archive")
        sidecar = ReportSidecar(archive_dir=archive_dir)
        result = sidecar.save_to_archive(self.sample_data)
        self.assertIn("2026-03-22", os.path.basename(result))

    def test_save_to_archive_includes_session(self):
        """Archive filename includes session number for uniqueness."""
        archive_dir = os.path.join(self.tmpdir, "archive")
        sidecar = ReportSidecar(archive_dir=archive_dir)
        result = sidecar.save_to_archive(self.sample_data)
        basename = os.path.basename(result)
        self.assertIn("S122", basename)

    def test_save_to_archive_valid_json(self):
        """Archived file is valid JSON."""
        archive_dir = os.path.join(self.tmpdir, "archive")
        sidecar = ReportSidecar(archive_dir=archive_dir)
        result = sidecar.save_to_archive(self.sample_data)
        with open(result) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["date"], "2026-03-22")

    def test_save_to_archive_overwrites_same_session(self):
        """Re-running for the same session overwrites the file (not duplicates)."""
        archive_dir = os.path.join(self.tmpdir, "archive")
        sidecar = ReportSidecar(archive_dir=archive_dir)
        sidecar.save_to_archive(self.sample_data)
        # Modify data and save again
        self.sample_data["summary"]["total_tests"] = 8000
        result = sidecar.save_to_archive(self.sample_data)
        with open(result) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["summary"]["total_tests"], 8000)
        # Only one file for this date+session
        files = os.listdir(archive_dir)
        matching = [f for f in files if "2026-03-22" in f and "S122" in f]
        self.assertEqual(len(matching), 1)

    # ── list_archived_reports ─────────────────────────────────────────

    def test_list_archived_empty(self):
        """Returns empty list when archive doesn't exist."""
        sidecar = ReportSidecar(archive_dir=os.path.join(self.tmpdir, "nope"))
        result = sidecar.list_archived_reports()
        self.assertEqual(result, [])

    def test_list_archived_returns_sorted(self):
        """Returns archived reports sorted by date descending (newest first)."""
        archive_dir = os.path.join(self.tmpdir, "archive")
        sidecar = ReportSidecar(archive_dir=archive_dir)

        # Save two reports with different dates
        data1 = dict(self.sample_data, date="2026-03-20", session=120)
        data2 = dict(self.sample_data, date="2026-03-22", session=122)
        sidecar.save_to_archive(data1)
        sidecar.save_to_archive(data2)

        result = sidecar.list_archived_reports()
        self.assertEqual(len(result), 2)
        # Newest first
        self.assertIn("2026-03-22", result[0])
        self.assertIn("2026-03-20", result[1])

    # ── load_report ───────────────────────────────────────────────────

    def test_load_report_from_path(self):
        """Can load a sidecar JSON by path."""
        archive_dir = os.path.join(self.tmpdir, "archive")
        sidecar = ReportSidecar(archive_dir=archive_dir)
        saved = sidecar.save_to_archive(self.sample_data)
        loaded = sidecar.load_report(saved)
        self.assertEqual(loaded["session"], 122)

    def test_load_report_missing_file(self):
        """Returns None for missing file."""
        sidecar = ReportSidecar()
        result = sidecar.load_report("/nonexistent/file.json")
        self.assertIsNone(result)

    def test_load_report_corrupt_json(self):
        """Returns None for corrupt JSON."""
        bad_path = os.path.join(self.tmpdir, "bad.json")
        with open(bad_path, "w") as f:
            f.write("not json{{{")
        sidecar = ReportSidecar()
        result = sidecar.load_report(bad_path)
        self.assertIsNone(result)

    # ── extract_summary_snapshot ──────────────────────────────────────

    def test_extract_summary_snapshot(self):
        """Extracts a compact summary for quick comparison."""
        sidecar = ReportSidecar()
        snap = sidecar.extract_summary_snapshot(self.sample_data)
        self.assertEqual(snap["session"], 122)
        self.assertEqual(snap["date"], "2026-03-22")
        self.assertEqual(snap["total_tests"], 7870)
        self.assertEqual(snap["total_loc"], 40000)
        self.assertEqual(snap["git_commits"], 500)
        self.assertEqual(snap["completed_mts"], 1)
        self.assertEqual(snap["active_mts"], 1)

    def test_extract_summary_snapshot_kalshi(self):
        """Snapshot includes Kalshi P&L if available."""
        sidecar = ReportSidecar()
        snap = sidecar.extract_summary_snapshot(self.sample_data)
        self.assertEqual(snap["kalshi_pnl_usd"], 45.50)
        self.assertEqual(snap["kalshi_win_rate"], 62.5)

    def test_extract_summary_snapshot_no_kalshi(self):
        """Snapshot handles missing Kalshi data gracefully."""
        data = dict(self.sample_data)
        data["kalshi_analytics"] = {"available": False, "summary": {}}
        sidecar = ReportSidecar()
        snap = sidecar.extract_summary_snapshot(data)
        self.assertIsNone(snap["kalshi_pnl_usd"])
        self.assertIsNone(snap["kalshi_win_rate"])

    def test_extract_summary_snapshot_learning(self):
        """Snapshot includes self-learning APF."""
        sidecar = ReportSidecar()
        snap = sidecar.extract_summary_snapshot(self.sample_data)
        self.assertEqual(snap["apf"], 22.7)
        self.assertEqual(snap["journal_entries"], 335)

    def test_extract_summary_snapshot_no_learning(self):
        """Snapshot handles missing learning data gracefully."""
        data = dict(self.sample_data)
        data["learning_intelligence"] = {"available": False, "journal": {}, "apf": {}}
        sidecar = ReportSidecar()
        snap = sidecar.extract_summary_snapshot(data)
        self.assertIsNone(snap["apf"])
        self.assertIsNone(snap["journal_entries"])


if __name__ == "__main__":
    unittest.main()
