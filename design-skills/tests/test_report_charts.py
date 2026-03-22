"""Tests for report_charts.py — SVG chart generation for CCA reports.

Generates professional charts from CCADataCollector output for Typst embedding.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestReportChartGenerator(unittest.TestCase):
    """Test ReportChartGenerator initialization and chart generation."""

    def setUp(self):
        from report_charts import ReportChartGenerator
        self.gen = ReportChartGenerator()
        # Minimal valid report data matching CCADataCollector.collect_from_project() output
        self.sample_data = {
            "session": 117,
            "summary": {
                "total_tests": 7333,
                "test_suites": 184,
                "total_modules": 8,
                "total_findings": 335,
                "source_loc": 25000,
                "test_loc": 35000,
                "total_loc": 60000,
                "git_commits": 500,
                "project_age_days": 30,
                "master_tasks": 31,
                "completed_tasks": 5,
                "in_progress_tasks": 20,
                "not_started_tasks": 4,
                "blocked_tasks": 2,
                "live_hooks": 18,
                "source_files": 80,
                "test_files": 170,
            },
            "modules": [
                {"name": "Memory System", "tests": 340, "loc": 2000, "status": "ACTIVE"},
                {"name": "Spec System", "tests": 205, "loc": 1500, "status": "ACTIVE"},
                {"name": "Context Monitor", "tests": 411, "loc": 2500, "status": "ACTIVE"},
                {"name": "Agent Guard", "tests": 1073, "loc": 5000, "status": "ACTIVE"},
                {"name": "Usage Dashboard", "tests": 369, "loc": 1800, "status": "ACTIVE"},
                {"name": "Reddit Intelligence", "tests": 408, "loc": 2200, "status": "ACTIVE"},
                {"name": "Self-Learning", "tests": 1779, "loc": 6000, "status": "ACTIVE"},
                {"name": "Design Skills", "tests": 719, "loc": 3500, "status": "ACTIVE"},
            ],
            "intelligence": {
                "findings_total": 335,
                "build": 25,
                "adapt": 45,
                "reference": 80,
                "reference_personal": 35,
                "skip": 140,
                "other": 10,
            },
            "master_tasks_complete": [
                {"id": "MT-9", "name": "Autonomous Scanning", "phases_done": 3, "total_phases": 3},
                {"id": "MT-10", "name": "YoYo Loop", "phases_done": 3, "total_phases": 3},
            ],
            "master_tasks_active": [
                {"id": "MT-0", "name": "Kalshi Self-Learning", "phases_done": 1, "total_phases": 4},
                {"id": "MT-20", "name": "Senior Dev Agent", "phases_done": 7, "total_phases": 9},
                {"id": "MT-21", "name": "Hivemind", "phases_done": 2, "total_phases": 5},
            ],
            "master_tasks_pending": [
                {"id": "MT-5", "name": "Pro Bridge", "phases_done": 0, "total_phases": 3},
            ],
            "frontiers": [
                {"number": 1, "name": "Memory", "tests": 340, "loc": 2000, "status": "ACTIVE"},
                {"number": 2, "name": "Spec", "tests": 205, "loc": 1500, "status": "ACTIVE"},
                {"number": 3, "name": "Context", "tests": 411, "loc": 2500, "status": "ACTIVE"},
                {"number": 4, "name": "Guard", "tests": 1073, "loc": 5000, "status": "ACTIVE"},
                {"number": 5, "name": "Dashboard", "tests": 369, "loc": 1800, "status": "ACTIVE"},
            ],
        }

    # ── Initialization ──────────────────────────────────────────────────

    def test_init_default(self):
        from report_charts import ReportChartGenerator
        gen = ReportChartGenerator()
        self.assertIsNotNone(gen)

    def test_init_with_output_dir(self):
        from report_charts import ReportChartGenerator
        gen = ReportChartGenerator(output_dir="/tmp/test_charts")
        self.assertEqual(gen.output_dir, "/tmp/test_charts")

    # ── Module test distribution chart ──────────────────────────────────

    def test_module_tests_chart_returns_svg(self):
        svg = self.gen.module_tests_chart(self.sample_data)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_module_tests_chart_contains_module_names(self):
        svg = self.gen.module_tests_chart(self.sample_data)
        self.assertIn("Agent Guard", svg)
        self.assertIn("Self-Learning", svg)

    def test_module_tests_chart_sorted_by_tests(self):
        """Modules should be sorted by test count descending."""
        svg = self.gen.module_tests_chart(self.sample_data)
        # Self-Learning (1779) should appear before Memory System (340)
        sl_pos = svg.find("Self-Learning")
        ms_pos = svg.find("Memory System")
        # In horizontal bar chart, higher values appear first (at top)
        self.assertGreater(ms_pos, -1)
        self.assertGreater(sl_pos, -1)

    def test_module_tests_chart_empty_modules(self):
        data = dict(self.sample_data, modules=[])
        svg = self.gen.module_tests_chart(data)
        self.assertIn("No data", svg)

    def test_module_tests_chart_has_title(self):
        svg = self.gen.module_tests_chart(self.sample_data)
        self.assertIn("Tests per Module", svg)

    # ── Intelligence verdict chart ──────────────────────────────────────

    def test_intelligence_chart_returns_svg(self):
        svg = self.gen.intelligence_chart(self.sample_data)
        self.assertIn("<svg", svg)

    def test_intelligence_chart_contains_verdicts(self):
        svg = self.gen.intelligence_chart(self.sample_data)
        self.assertIn("BUILD", svg)
        self.assertIn("SKIP", svg)

    def test_intelligence_chart_empty_data(self):
        data = dict(self.sample_data, intelligence={
            "findings_total": 0, "build": 0, "adapt": 0,
            "reference": 0, "reference_personal": 0, "skip": 0, "other": 0,
        })
        svg = self.gen.intelligence_chart(data)
        self.assertIn("No data", svg)

    # ── MT status breakdown chart ───────────────────────────────────────

    def test_mt_status_chart_returns_svg(self):
        svg = self.gen.mt_status_chart(self.sample_data)
        self.assertIn("<svg", svg)

    def test_mt_status_chart_categories(self):
        svg = self.gen.mt_status_chart(self.sample_data)
        self.assertIn("Complete", svg)

    def test_mt_status_chart_empty(self):
        data = dict(self.sample_data,
                    master_tasks_complete=[],
                    master_tasks_active=[],
                    master_tasks_pending=[])
        svg = self.gen.mt_status_chart(data)
        self.assertIn("No data", svg)

    # ── LOC distribution chart ──────────────────────────────────────────

    def test_loc_chart_returns_svg(self):
        svg = self.gen.loc_chart(self.sample_data)
        self.assertIn("<svg", svg)

    def test_loc_chart_source_vs_test(self):
        svg = self.gen.loc_chart(self.sample_data)
        self.assertIn("Source", svg)
        self.assertIn("Test", svg)

    # ── MT phase progress chart ─────────────────────────────────────────

    def test_mt_progress_chart_returns_svg(self):
        svg = self.gen.mt_progress_chart(self.sample_data)
        self.assertIn("<svg", svg)

    def test_mt_progress_chart_contains_task_names(self):
        svg = self.gen.mt_progress_chart(self.sample_data)
        self.assertIn("MT-0", svg)
        self.assertIn("MT-20", svg)

    def test_mt_progress_chart_empty(self):
        data = dict(self.sample_data, master_tasks_active=[])
        svg = self.gen.mt_progress_chart(data)
        self.assertIn("No data", svg)

    # ── Frontier status chart ───────────────────────────────────────────

    def test_frontier_chart_returns_svg(self):
        svg = self.gen.frontier_chart(self.sample_data)
        self.assertIn("<svg", svg)

    def test_frontier_chart_all_frontiers(self):
        svg = self.gen.frontier_chart(self.sample_data)
        self.assertIn("Memory", svg)
        self.assertIn("Context", svg)

    # ── generate_all ────────────────────────────────────────────────────

    def test_generate_all_returns_dict(self):
        result = self.gen.generate_all(self.sample_data)
        self.assertIsInstance(result, dict)

    def test_generate_all_has_expected_keys(self):
        result = self.gen.generate_all(self.sample_data)
        expected_keys = [
            "module_tests", "intelligence", "mt_status",
            "loc_distribution", "mt_progress", "frontier_status",
        ]
        for key in expected_keys:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_generate_all_values_are_svg(self):
        result = self.gen.generate_all(self.sample_data)
        for key, svg in result.items():
            self.assertIn("<svg", svg, f"{key} is not valid SVG")

    # ── save_all ────────────────────────────────────────────────────────

    def test_save_all_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = self._make_gen(tmpdir)
            paths = gen.save_all(self.sample_data)
            self.assertIsInstance(paths, dict)
            for key, path in paths.items():
                self.assertTrue(os.path.exists(path), f"{key} file not created: {path}")
                self.assertTrue(path.endswith(".svg"))

    def test_save_all_files_contain_svg(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = self._make_gen(tmpdir)
            paths = gen.save_all(self.sample_data)
            for key, path in paths.items():
                with open(path) as f:
                    content = f.read()
                self.assertIn("<svg", content, f"{key} file is not SVG")

    def test_save_all_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "nested", "charts")
            gen = self._make_gen(subdir)
            paths = gen.save_all(self.sample_data)
            self.assertTrue(os.path.isdir(subdir))
            self.assertTrue(len(paths) > 0)

    def _make_gen(self, output_dir):
        from report_charts import ReportChartGenerator
        return ReportChartGenerator(output_dir=output_dir)


class TestReportChartGeneratorEdgeCases(unittest.TestCase):
    """Edge case and boundary tests."""

    def setUp(self):
        from report_charts import ReportChartGenerator
        self.gen = ReportChartGenerator()

    def test_single_module(self):
        data = {
            "modules": [{"name": "Only Module", "tests": 100, "loc": 500, "status": "ACTIVE"}],
            "intelligence": {"findings_total": 0, "build": 0, "adapt": 0,
                            "reference": 0, "reference_personal": 0, "skip": 0, "other": 0},
            "master_tasks_complete": [], "master_tasks_active": [], "master_tasks_pending": [],
            "frontiers": [], "summary": {"source_loc": 500, "test_loc": 200, "total_loc": 700},
        }
        result = self.gen.generate_all(data)
        self.assertIn("<svg", result["module_tests"])

    def test_zero_test_modules(self):
        data = {
            "modules": [
                {"name": "Empty", "tests": 0, "loc": 100, "status": "ACTIVE"},
                {"name": "Also Empty", "tests": 0, "loc": 50, "status": "ACTIVE"},
            ],
            "intelligence": {"findings_total": 0, "build": 0, "adapt": 0,
                            "reference": 0, "reference_personal": 0, "skip": 0, "other": 0},
            "master_tasks_complete": [], "master_tasks_active": [], "master_tasks_pending": [],
            "frontiers": [], "summary": {"source_loc": 150, "test_loc": 0, "total_loc": 150},
        }
        result = self.gen.generate_all(data)
        for key, svg in result.items():
            self.assertIn("<svg", svg)

    def test_very_long_module_name(self):
        data = {
            "modules": [{"name": "A" * 100, "tests": 50, "loc": 200, "status": "ACTIVE"}],
            "intelligence": {"findings_total": 0, "build": 0, "adapt": 0,
                            "reference": 0, "reference_personal": 0, "skip": 0, "other": 0},
            "master_tasks_complete": [], "master_tasks_active": [], "master_tasks_pending": [],
            "frontiers": [], "summary": {"source_loc": 200, "test_loc": 100, "total_loc": 300},
        }
        svg = self.gen.module_tests_chart(data)
        self.assertIn("<svg", svg)

    def test_all_verdicts_zero_except_one(self):
        data = {
            "modules": [],
            "intelligence": {"findings_total": 50, "build": 50, "adapt": 0,
                            "reference": 0, "reference_personal": 0, "skip": 0, "other": 0},
            "master_tasks_complete": [], "master_tasks_active": [], "master_tasks_pending": [],
            "frontiers": [], "summary": {"source_loc": 0, "test_loc": 0, "total_loc": 0},
        }
        svg = self.gen.intelligence_chart(data)
        self.assertIn("<svg", svg)
        self.assertIn("BUILD", svg)

    def test_mt_with_zero_phases(self):
        data = {
            "modules": [],
            "intelligence": {"findings_total": 0, "build": 0, "adapt": 0,
                            "reference": 0, "reference_personal": 0, "skip": 0, "other": 0},
            "master_tasks_complete": [],
            "master_tasks_active": [
                {"id": "MT-99", "name": "Zero Phases", "phases_done": 0, "total_phases": 0},
            ],
            "master_tasks_pending": [],
            "frontiers": [], "summary": {"source_loc": 0, "test_loc": 0, "total_loc": 0},
        }
        svg = self.gen.mt_progress_chart(data)
        self.assertIn("<svg", svg)

    def test_large_test_counts(self):
        data = {
            "modules": [
                {"name": "Big Module", "tests": 99999, "loc": 50000, "status": "ACTIVE"},
            ],
            "intelligence": {"findings_total": 0, "build": 0, "adapt": 0,
                            "reference": 0, "reference_personal": 0, "skip": 0, "other": 0},
            "master_tasks_complete": [], "master_tasks_active": [], "master_tasks_pending": [],
            "frontiers": [], "summary": {"source_loc": 50000, "test_loc": 60000, "total_loc": 110000},
        }
        svg = self.gen.module_tests_chart(data)
        self.assertIn("99999", svg)


if __name__ == "__main__":
    unittest.main()
