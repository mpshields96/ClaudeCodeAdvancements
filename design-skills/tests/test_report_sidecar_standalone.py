"""Tests for standalone report_sidecar.py (MT-33 Phase 5).

Tests the extract/save/load/find_latest API of the standalone ReportSidecar
module (design-skills/report_sidecar.py), NOT the legacy one in report_generator.py.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from report_sidecar import ReportSidecar


def _sample_data(**overrides):
    """Build a sample report data dict with sensible defaults."""
    data = {
        "session": 134,
        "date": "2026-03-23",
        "summary": {
            "total_tests": 8406,
            "test_suites": 208,
            "total_loc": 45000,
            "source_loc": 28000,
            "test_loc": 17000,
            "source_files": 95,
            "test_files": 65,
            "git_commits": 600,
            "live_hooks": 16,
            "total_delivered": 180,
        },
        "intelligence": {"findings_total": 220},
        "self_learning": {"papers": 18},
        "modules": [
            {"name": "Memory System", "tests": 340, "loc": 1200},
            {"name": "Agent Guard", "tests": 1073, "loc": 5000},
            {"name": "Self-Learning", "tests": 1859, "loc": 8000},
        ],
        "master_tasks_complete": [
            {"id": "MT-9", "name": "Autonomous Scanner"},
            {"id": "MT-14", "name": "Nuclear Deep-Dive"},
        ],
        "master_tasks_active": [
            {"id": "MT-33", "name": "Strategic Report"},
        ],
        "master_tasks_pending": [
            {"id": "MT-35", "name": "Future Task"},
        ],
        "kalshi_analytics": {
            "available": True,
            "summary": {
                "total_trades": 150,
                "settled_trades": 140,
                "win_rate_pct": 63.5,
                "total_pnl_usd": 52.30,
                "avg_pnl_usd": 0.37,
                "best_strategy": "sniper_drift",
            },
            "strategies": [
                {
                    "strategy": "sniper_drift",
                    "trade_count": 100,
                    "win_rate_pct": 65.0,
                    "total_pnl_usd": 40.0,
                },
                {
                    "strategy": "value_fade",
                    "trade_count": 40,
                    "win_rate_pct": 55.0,
                    "total_pnl_usd": 12.30,
                },
            ],
        },
        "learning_intelligence": {
            "available": True,
            "journal": {
                "total_entries": 400,
                "event_counts": {"win": 80, "loss": 30, "insight": 50},
                "domain_counts": {"trading": 100, "cca": 60},
            },
            "apf": {"current_apf": 28.5, "target": 40.0},
        },
    }
    data.update(overrides)
    return data


class TestReportSidecarExtract(unittest.TestCase):
    """Tests for extract() method."""

    def setUp(self):
        self.sidecar = ReportSidecar()

    def test_extract_returns_dict(self):
        result = self.sidecar.extract(_sample_data())
        self.assertIsInstance(result, dict)

    def test_extract_includes_version(self):
        result = self.sidecar.extract(_sample_data())
        self.assertEqual(result["sidecar_version"], 1)

    def test_extract_includes_generated_at(self):
        result = self.sidecar.extract(_sample_data())
        self.assertIn("generated_at", result)
        # Should be parseable ISO timestamp
        datetime.fromisoformat(result["generated_at"])

    def test_extract_preserves_session_and_date(self):
        result = self.sidecar.extract(_sample_data())
        self.assertEqual(result["session"], 134)
        self.assertEqual(result["date"], "2026-03-23")

    def test_extract_summary_fields(self):
        result = self.sidecar.extract(_sample_data())
        s = result["summary"]
        self.assertEqual(s["total_tests"], 8406)
        self.assertEqual(s["test_suites"], 208)
        self.assertEqual(s["total_loc"], 45000)
        self.assertEqual(s["source_loc"], 28000)
        self.assertEqual(s["test_loc"], 17000)
        self.assertEqual(s["source_files"], 95)
        self.assertEqual(s["test_files"], 65)
        self.assertEqual(s["git_commits"], 600)
        self.assertEqual(s["live_hooks"], 16)
        self.assertEqual(s["total_delivered"], 180)

    def test_extract_summary_findings_from_intelligence(self):
        result = self.sidecar.extract(_sample_data())
        self.assertEqual(result["summary"]["total_findings"], 220)

    def test_extract_summary_papers_from_self_learning(self):
        result = self.sidecar.extract(_sample_data())
        self.assertEqual(result["summary"]["total_papers"], 18)

    def test_extract_summary_task_counts(self):
        result = self.sidecar.extract(_sample_data())
        self.assertEqual(result["summary"]["completed_tasks"], 2)
        self.assertEqual(result["summary"]["in_progress_tasks"], 1)

    def test_extract_modules_list(self):
        result = self.sidecar.extract(_sample_data())
        self.assertEqual(len(result["modules"]), 3)
        self.assertEqual(result["modules"][0]["name"], "Memory System")
        self.assertEqual(result["modules"][0]["tests"], 340)
        self.assertEqual(result["modules"][0]["loc"], 1200)

    def test_extract_master_tasks_complete(self):
        result = self.sidecar.extract(_sample_data())
        self.assertEqual(len(result["master_tasks_complete"]), 2)
        self.assertEqual(result["master_tasks_complete"][0]["id"], "MT-9")

    def test_extract_master_tasks_active(self):
        result = self.sidecar.extract(_sample_data())
        self.assertEqual(len(result["master_tasks_active"]), 1)
        self.assertEqual(result["master_tasks_active"][0]["id"], "MT-33")

    def test_extract_master_tasks_pending(self):
        result = self.sidecar.extract(_sample_data())
        self.assertEqual(len(result["master_tasks_pending"]), 1)

    def test_extract_empty_data(self):
        """Extract handles completely empty data dict."""
        result = self.sidecar.extract({})
        self.assertEqual(result["sidecar_version"], 1)
        self.assertIsNone(result["session"])
        self.assertIsNone(result["date"])
        self.assertEqual(result["summary"]["total_tests"], 0)
        self.assertEqual(result["modules"], [])
        self.assertEqual(result["master_tasks_complete"], [])

    def test_extract_partial_summary(self):
        """Extract handles summary with some fields missing."""
        data = _sample_data()
        data["summary"] = {"total_tests": 100}
        result = self.sidecar.extract(data)
        self.assertEqual(result["summary"]["total_tests"], 100)
        self.assertEqual(result["summary"]["test_suites"], 0)
        self.assertEqual(result["summary"]["total_loc"], 0)

    def test_extract_no_modules(self):
        """Extract with empty modules list."""
        data = _sample_data(modules=[])
        result = self.sidecar.extract(data)
        self.assertEqual(result["modules"], [])

    def test_extract_module_missing_fields(self):
        """Modules with missing fields get defaults."""
        data = _sample_data(modules=[{"name": "Bare Module"}])
        result = self.sidecar.extract(data)
        self.assertEqual(result["modules"][0]["name"], "Bare Module")
        self.assertEqual(result["modules"][0]["tests"], 0)
        self.assertEqual(result["modules"][0]["loc"], 0)


class TestReportSidecarKalshiExtract(unittest.TestCase):
    """Tests for Kalshi analytics extraction."""

    def setUp(self):
        self.sidecar = ReportSidecar()

    def test_kalshi_available(self):
        result = self.sidecar.extract(_sample_data())
        k = result["kalshi_analytics"]
        self.assertTrue(k["available"])
        self.assertEqual(k["total_trades"], 150)
        self.assertEqual(k["settled_trades"], 140)
        self.assertEqual(k["win_rate_pct"], 63.5)
        self.assertEqual(k["total_pnl_usd"], 52.30)
        self.assertEqual(k["avg_pnl_usd"], 0.37)
        self.assertEqual(k["best_strategy"], "sniper_drift")

    def test_kalshi_strategies(self):
        result = self.sidecar.extract(_sample_data())
        strats = result["kalshi_analytics"]["strategies"]
        self.assertEqual(len(strats), 2)
        self.assertEqual(strats[0]["name"], "sniper_drift")
        self.assertEqual(strats[0]["trades"], 100)
        self.assertEqual(strats[0]["win_rate"], 65.0)
        self.assertEqual(strats[0]["pnl"], 40.0)

    def test_kalshi_unavailable(self):
        data = _sample_data(kalshi_analytics={"available": False})
        result = self.sidecar.extract(data)
        self.assertFalse(result["kalshi_analytics"]["available"])

    def test_kalshi_empty_summary(self):
        data = _sample_data(kalshi_analytics={"available": True, "summary": {}})
        result = self.sidecar.extract(data)
        k = result["kalshi_analytics"]
        self.assertTrue(k["available"])
        self.assertEqual(k["total_trades"], 0)
        self.assertIsNone(k["win_rate_pct"])

    def test_kalshi_no_strategies(self):
        data = _sample_data(
            kalshi_analytics={"available": True, "summary": {"total_trades": 5}}
        )
        result = self.sidecar.extract(data)
        self.assertEqual(result["kalshi_analytics"]["strategies"], [])

    def test_kalshi_missing_entirely(self):
        """No kalshi_analytics key at all."""
        data = _sample_data()
        del data["kalshi_analytics"]
        result = self.sidecar.extract(data)
        self.assertFalse(result["kalshi_analytics"]["available"])


class TestReportSidecarLearningExtract(unittest.TestCase):
    """Tests for self-learning intelligence extraction."""

    def setUp(self):
        self.sidecar = ReportSidecar()

    def test_learning_available(self):
        result = self.sidecar.extract(_sample_data())
        li = result["learning_intelligence"]
        self.assertTrue(li["available"])
        self.assertEqual(li["total_entries"], 400)
        self.assertEqual(li["event_counts"]["win"], 80)
        self.assertEqual(li["domain_counts"]["trading"], 100)
        self.assertEqual(li["current_apf"], 28.5)
        self.assertEqual(li["apf_target"], 40.0)

    def test_learning_unavailable(self):
        data = _sample_data(learning_intelligence={"available": False})
        result = self.sidecar.extract(data)
        self.assertFalse(result["learning_intelligence"]["available"])

    def test_learning_empty_journal(self):
        data = _sample_data(
            learning_intelligence={
                "available": True,
                "journal": {},
                "apf": {"current_apf": 15.0},
            }
        )
        result = self.sidecar.extract(data)
        li = result["learning_intelligence"]
        self.assertEqual(li["total_entries"], 0)
        self.assertEqual(li["event_counts"], {})
        self.assertEqual(li["current_apf"], 15.0)

    def test_learning_no_apf(self):
        data = _sample_data(
            learning_intelligence={
                "available": True,
                "journal": {"total_entries": 50},
                "apf": {},
            }
        )
        result = self.sidecar.extract(data)
        self.assertIsNone(result["learning_intelligence"]["current_apf"])
        self.assertEqual(result["learning_intelligence"]["apf_target"], 40.0)

    def test_learning_missing_entirely(self):
        data = _sample_data()
        del data["learning_intelligence"]
        result = self.sidecar.extract(data)
        self.assertFalse(result["learning_intelligence"]["available"])


class TestReportSidecarSave(unittest.TestCase):
    """Tests for save() method."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sidecar = ReportSidecar()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_creates_file(self):
        pdf = os.path.join(self.tmpdir, "report.pdf")
        result = self.sidecar.save(_sample_data(), pdf)
        self.assertTrue(os.path.exists(result))

    def test_save_returns_sidecar_path(self):
        pdf = os.path.join(self.tmpdir, "report.pdf")
        result = self.sidecar.save(_sample_data(), pdf)
        self.assertEqual(result, os.path.join(self.tmpdir, "report.sidecar.json"))

    def test_save_valid_json(self):
        pdf = os.path.join(self.tmpdir, "report.pdf")
        result = self.sidecar.save(_sample_data(), pdf)
        with open(result) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["session"], 134)
        self.assertEqual(loaded["sidecar_version"], 1)

    def test_save_indented_json(self):
        pdf = os.path.join(self.tmpdir, "report.pdf")
        result = self.sidecar.save(_sample_data(), pdf)
        with open(result) as f:
            content = f.read()
        # Indented JSON has newlines
        self.assertIn("\n", content)

    def test_save_creates_parent_dir(self):
        pdf = os.path.join(self.tmpdir, "subdir", "report.pdf")
        result = self.sidecar.save(_sample_data(), pdf)
        self.assertTrue(os.path.exists(result))

    def test_save_overwrites_existing(self):
        pdf = os.path.join(self.tmpdir, "report.pdf")
        self.sidecar.save(_sample_data(session=100), pdf)
        self.sidecar.save(_sample_data(session=200), pdf)
        with open(os.path.join(self.tmpdir, "report.sidecar.json")) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["session"], 200)

    def test_save_uppercase_pdf_extension(self):
        pdf = os.path.join(self.tmpdir, "REPORT.PDF")
        result = self.sidecar.save(_sample_data(), pdf)
        self.assertEqual(result, os.path.join(self.tmpdir, "REPORT.sidecar.json"))

    def test_save_no_extension(self):
        path = os.path.join(self.tmpdir, "report")
        result = self.sidecar.save(_sample_data(), path)
        self.assertEqual(result, os.path.join(self.tmpdir, "report.sidecar.json"))


class TestReportSidecarLoad(unittest.TestCase):
    """Tests for load() method."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sidecar = ReportSidecar()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_existing_file(self):
        path = os.path.join(self.tmpdir, "test.sidecar.json")
        with open(path, "w") as f:
            json.dump({"session": 99, "sidecar_version": 1}, f)
        result = self.sidecar.load(path)
        self.assertEqual(result["session"], 99)

    def test_load_missing_file(self):
        result = self.sidecar.load("/nonexistent/path.json")
        self.assertIsNone(result)

    def test_load_corrupt_json(self):
        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w") as f:
            f.write("{not valid json")
        result = self.sidecar.load(path)
        self.assertIsNone(result)

    def test_load_empty_file(self):
        path = os.path.join(self.tmpdir, "empty.json")
        with open(path, "w") as f:
            f.write("")
        result = self.sidecar.load(path)
        self.assertIsNone(result)

    def test_load_roundtrip(self):
        """Save then load gives back the same data."""
        pdf = os.path.join(self.tmpdir, "report.pdf")
        saved_path = self.sidecar.save(_sample_data(), pdf)
        loaded = self.sidecar.load(saved_path)
        self.assertEqual(loaded["session"], 134)
        self.assertEqual(loaded["summary"]["total_tests"], 8406)
        self.assertEqual(loaded["kalshi_analytics"]["total_pnl_usd"], 52.30)


class TestReportSidecarFindLatest(unittest.TestCase):
    """Tests for find_latest() method."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sidecar = ReportSidecar()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_find_latest_nonexistent_dir(self):
        path, data = self.sidecar.find_latest("/nonexistent/dir")
        self.assertIsNone(path)
        self.assertIsNone(data)

    def test_find_latest_empty_dir(self):
        path, data = self.sidecar.find_latest(self.tmpdir)
        self.assertIsNone(path)
        self.assertIsNone(data)

    def test_find_latest_single_file(self):
        sidecar_path = os.path.join(self.tmpdir, "2026-03-23_S134.sidecar.json")
        with open(sidecar_path, "w") as f:
            json.dump({"session": 134}, f)
        path, data = self.sidecar.find_latest(self.tmpdir)
        self.assertEqual(path, sidecar_path)
        self.assertEqual(data["session"], 134)

    def test_find_latest_multiple_files_returns_newest(self):
        """With multiple sidecar files, returns the one that sorts last (newest)."""
        for name in [
            "2026-03-20_S130.sidecar.json",
            "2026-03-22_S132.sidecar.json",
            "2026-03-23_S134.sidecar.json",
        ]:
            with open(os.path.join(self.tmpdir, name), "w") as f:
                json.dump({"session": int(name.split("S")[1].split(".")[0])}, f)
        path, data = self.sidecar.find_latest(self.tmpdir)
        self.assertIn("2026-03-23", path)
        self.assertEqual(data["session"], 134)

    def test_find_latest_ignores_non_sidecar_files(self):
        """Non-.sidecar.json files are ignored."""
        with open(os.path.join(self.tmpdir, "report.pdf"), "w") as f:
            f.write("pdf bytes")
        with open(os.path.join(self.tmpdir, "notes.json"), "w") as f:
            json.dump({"not": "sidecar"}, f)
        with open(os.path.join(self.tmpdir, "report.sidecar.json"), "w") as f:
            json.dump({"session": 100}, f)
        path, data = self.sidecar.find_latest(self.tmpdir)
        self.assertIn("report.sidecar.json", path)
        self.assertEqual(data["session"], 100)

    def test_find_latest_corrupt_file_returns_none(self):
        """If the latest sidecar is corrupt, returns None."""
        with open(os.path.join(self.tmpdir, "z_latest.sidecar.json"), "w") as f:
            f.write("corrupt{{{")
        path, data = self.sidecar.find_latest(self.tmpdir)
        self.assertIsNone(path)
        self.assertIsNone(data)

    def test_find_latest_skips_corrupt_finds_valid(self):
        """If latest is corrupt but an earlier one is valid, still returns None.

        find_latest only checks the first (sorted-last) file, not all of them.
        This is by design — it's a simple 'get the newest' function.
        """
        with open(os.path.join(self.tmpdir, "a_old.sidecar.json"), "w") as f:
            json.dump({"session": 100}, f)
        with open(os.path.join(self.tmpdir, "z_new.sidecar.json"), "w") as f:
            f.write("corrupt")
        path, data = self.sidecar.find_latest(self.tmpdir)
        # Only checks the first sorted match (z_new), which is corrupt
        self.assertIsNone(path)
        self.assertIsNone(data)


class TestReportSidecarPath(unittest.TestCase):
    """Tests for _sidecar_path() static method."""

    def test_pdf_extension(self):
        result = ReportSidecar._sidecar_path("/path/to/report.pdf")
        self.assertEqual(result, "/path/to/report.sidecar.json")

    def test_uppercase_extension(self):
        result = ReportSidecar._sidecar_path("/path/to/REPORT.PDF")
        self.assertEqual(result, "/path/to/REPORT.sidecar.json")

    def test_no_extension(self):
        result = ReportSidecar._sidecar_path("/path/to/report")
        self.assertEqual(result, "/path/to/report.sidecar.json")

    def test_multiple_dots(self):
        result = ReportSidecar._sidecar_path("/path/to/cca.status.report.pdf")
        self.assertEqual(result, "/path/to/cca.status.report.sidecar.json")

    def test_just_filename(self):
        result = ReportSidecar._sidecar_path("report.pdf")
        self.assertEqual(result, "report.sidecar.json")


class TestReportSidecarJsonSerializable(unittest.TestCase):
    """Ensure extracted data is fully JSON-serializable."""

    def test_extract_is_json_serializable(self):
        sidecar = ReportSidecar()
        result = sidecar.extract(_sample_data())
        # This will raise if not serializable
        serialized = json.dumps(result)
        self.assertIsInstance(serialized, str)

    def test_extract_with_none_values(self):
        """None values in data shouldn't break serialization."""
        data = _sample_data()
        data["session"] = None
        data["date"] = None
        sidecar = ReportSidecar()
        result = sidecar.extract(data)
        serialized = json.dumps(result)
        self.assertIsInstance(serialized, str)


if __name__ == "__main__":
    unittest.main()
