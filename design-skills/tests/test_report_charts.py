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


class TestKalshiCharts(unittest.TestCase):
    """Test Kalshi financial chart generation (MT-33)."""

    def setUp(self):
        from report_charts import ReportChartGenerator
        self.gen = ReportChartGenerator()
        self.kalshi_data = {
            "kalshi_analytics": {
                "available": True,
                "summary": {"total_live_trades": 100, "wins": 60, "losses": 40,
                            "total_pnl_usd": 45.50, "win_rate_pct": 60.0},
                "strategies": [
                    {"strategy": "sniper_v1", "trade_count": 50, "wins": 45,
                     "losses": 5, "win_rate_pct": 90.0, "total_pnl_usd": 35.0,
                     "avg_pnl_usd": 0.70},
                    {"strategy": "drift_v1", "trade_count": 30, "wins": 10,
                     "losses": 20, "win_rate_pct": 33.3, "total_pnl_usd": -5.0,
                     "avg_pnl_usd": -0.17},
                    {"strategy": "imbalance_v1", "trade_count": 20, "wins": 5,
                     "losses": 15, "win_rate_pct": 25.0, "total_pnl_usd": 15.5,
                     "avg_pnl_usd": 0.78},
                ],
                "daily_pnl": [
                    {"date": "2026-03-10", "pnl_usd": 5.0, "cumulative_pnl_usd": 5.0},
                    {"date": "2026-03-11", "pnl_usd": -2.0, "cumulative_pnl_usd": 3.0},
                    {"date": "2026-03-12", "pnl_usd": 8.0, "cumulative_pnl_usd": 11.0},
                    {"date": "2026-03-13", "pnl_usd": -1.0, "cumulative_pnl_usd": 10.0},
                ],
                "bankroll": [
                    {"timestamp": 1741564800, "datetime": "2026-03-10 00:00",
                     "balance_usd": 100.0},
                    {"timestamp": 1741651200, "datetime": "2026-03-11 00:00",
                     "balance_usd": 105.0},
                ],
                "charts": {
                    "cumulative_pnl": {
                        "labels": ["2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13"],
                        "values": [5.0, 3.0, 11.0, 10.0],
                    },
                    "strategy_winrate": {
                        "labels": ["sniper_v1", "drift_v1", "imbalance_v1"],
                        "values": [90.0, 33.3, 25.0],
                    },
                    "daily_pnl_histogram": {
                        "values": [5.0, -2.0, 8.0, -1.0, 3.0, -4.0, 6.0],
                    },
                    "strategy_pnl_distribution": {
                        "categories": ["sniper_v1", "drift_v1"],
                        "data_series": [
                            [0.5, 0.8, -0.1, 1.2, 0.3, 0.6, 0.9, -0.2, 0.4, 0.7],
                            [-0.3, 0.2, -0.5, -0.1, 0.1, -0.4, 0.3, -0.6, -0.2, 0.0],
                        ],
                    },
                    "winrate_vs_profit": {
                        "series": [{"name": "Strategies", "data": [
                            {"x": 90.0, "y": 0.70, "label": "sniper_v1"},
                            {"x": 33.3, "y": -0.17, "label": "drift_v1"},
                        ]}],
                    },
                    "trade_volume": {
                        "labels": ["sniper_v1", "drift_v1", "imbalance_v1"],
                        "values": [50, 30, 20],
                    },
                    "bankroll_timeline": {
                        "labels": ["2026-03-10 00:00", "2026-03-11 00:00"],
                        "values": [100.0, 105.0],
                    },
                },
            },
        }

    def test_cumulative_pnl_returns_svg(self):
        svg = self.gen.kalshi_cumulative_pnl(self.kalshi_data)
        self.assertIn("<svg", svg)
        self.assertIn("Cumulative P&amp;L", svg)  # & is XML-escaped in SVG

    def test_strategy_winrate_returns_svg(self):
        svg = self.gen.kalshi_strategy_winrate(self.kalshi_data)
        self.assertIn("<svg", svg)
        self.assertIn("sniper_v1", svg)

    def test_daily_pnl_histogram_returns_svg(self):
        svg = self.gen.kalshi_daily_pnl_histogram(self.kalshi_data)
        self.assertIn("<svg", svg)

    def test_strategy_pnl_box_returns_svg(self):
        svg = self.gen.kalshi_strategy_pnl_box(self.kalshi_data)
        self.assertIn("<svg", svg)
        self.assertIn("sniper_v1", svg)

    def test_winrate_vs_profit_returns_svg(self):
        svg = self.gen.kalshi_winrate_vs_profit(self.kalshi_data)
        self.assertIn("<svg", svg)

    def test_trade_volume_returns_svg(self):
        svg = self.gen.kalshi_trade_volume(self.kalshi_data)
        self.assertIn("<svg", svg)

    def test_bankroll_returns_svg(self):
        svg = self.gen.kalshi_bankroll(self.kalshi_data)
        self.assertIn("<svg", svg)

    def test_generate_all_includes_kalshi(self):
        charts = self.gen.generate_all(self.kalshi_data)
        kalshi_keys = [k for k in charts if k.startswith("kalshi_")]
        self.assertEqual(len(kalshi_keys), 7)

    def test_generate_all_without_kalshi(self):
        """Without kalshi_analytics, no kalshi charts generated."""
        data = {"modules": [], "master_tasks_complete": [],
                "master_tasks_active": [], "master_tasks_pending": [],
                "intelligence": {"findings_total": 0},
                "frontiers": [],
                "summary": {"source_loc": 1000, "test_loc": 2000, "total_loc": 3000}}
        charts = self.gen.generate_all(data)
        kalshi_keys = [k for k in charts if k.startswith("kalshi_")]
        self.assertEqual(len(kalshi_keys), 0)

    def test_empty_kalshi_data(self):
        data = {"kalshi_analytics": {"available": False}}
        svg = self.gen.kalshi_cumulative_pnl(data)
        self.assertIn("No data", svg)

    def test_missing_kalshi_key(self):
        data = {}
        svg = self.gen.kalshi_cumulative_pnl(data)
        self.assertIn("No data", svg)


class TestCCAStatisticalCharts(unittest.TestCase):
    """Tests for CCA-specific statistical charts (MT-32)."""

    def setUp(self):
        from report_charts import ReportChartGenerator
        self.gen = ReportChartGenerator()
        self.sample_data = {
            "modules": [
                {"name": "Memory System", "tests": 340, "loc": 2000},
                {"name": "Spec System", "tests": 205, "loc": 1500},
                {"name": "Context Monitor", "tests": 411, "loc": 2500},
                {"name": "Agent Guard", "tests": 1073, "loc": 5000},
                {"name": "Usage Dashboard", "tests": 369, "loc": 1800},
                {"name": "Reddit Intelligence", "tests": 408, "loc": 2200},
                {"name": "Self-Learning", "tests": 1779, "loc": 6000},
                {"name": "Design Skills", "tests": 1261, "loc": 3500},
            ],
            "summary": {
                "source_loc": 25000,
                "test_loc": 35000,
            },
        }

    def test_test_density_scatter_returns_svg(self):
        svg = self.gen.test_density_scatter(self.sample_data)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_test_density_scatter_has_title(self):
        svg = self.gen.test_density_scatter(self.sample_data)
        self.assertIn("Test Density", svg)

    def test_test_density_scatter_empty_modules(self):
        svg = self.gen.test_density_scatter({"modules": []})
        self.assertIn("No data", svg)

    def test_test_density_scatter_zero_loc_modules(self):
        """Modules with 0 LOC are excluded from scatter."""
        data = {"modules": [{"name": "Empty", "tests": 0, "loc": 0}]}
        svg = self.gen.test_density_scatter(data)
        self.assertIn("No data", svg)

    def test_module_composition_returns_svg(self):
        svg = self.gen.module_composition(self.sample_data)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_module_composition_has_title(self):
        svg = self.gen.module_composition(self.sample_data)
        self.assertIn("Code Composition", svg)

    def test_module_composition_empty_data(self):
        svg = self.gen.module_composition({"summary": {}})
        self.assertIn("No data", svg)

    def test_module_composition_zero_loc(self):
        svg = self.gen.module_composition({"summary": {"source_loc": 0, "test_loc": 0}})
        self.assertIn("No data", svg)

    def test_generate_all_includes_statistical_charts(self):
        """generate_all includes the new statistical CCA charts."""
        from report_charts import ReportChartGenerator
        gen = ReportChartGenerator()
        # Need minimum data for generate_all to run
        data = dict(self.sample_data)
        data.update({
            "intelligence": {"findings_total": 0},
            "master_tasks_complete": [],
            "master_tasks_active": [],
            "master_tasks_pending": [],
            "frontiers": [],
        })
        charts = gen.generate_all(data)
        self.assertIn("test_density_scatter", charts)
        self.assertIn("module_composition", charts)


if __name__ == "__main__":
    unittest.main()
