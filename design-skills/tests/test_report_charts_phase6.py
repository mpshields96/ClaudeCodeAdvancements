#!/usr/bin/env python3
"""
test_report_charts_phase6.py — MT-33 Phase 6 hardening tests.

Covers: learning chart generation, combined Kalshi+learning pipeline,
save_all edge cases, empty/missing/partial data resilience.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from report_charts import ReportChartGenerator


def _full_data():
    """Sample data with both Kalshi and learning data available."""
    return {
        "modules": [
            {"name": "Memory System", "tests": 340, "loc": 2000},
            {"name": "Agent Guard", "tests": 1073, "loc": 5000},
        ],
        "summary": {"source_loc": 7000, "test_loc": 5000, "total_loc": 12000},
        "intelligence": {"findings_total": 42},
        "master_tasks_complete": [{"id": "MT-7", "name": "Trace"}],
        "master_tasks_active": [{"id": "MT-32", "name": "Visual", "score": 8.0}],
        "master_tasks_pending": [],
        "frontiers": [
            {"name": "Memory", "status": "COMPLETE"},
            {"name": "Spec", "status": "COMPLETE"},
        ],
        "kalshi_analytics": {
            "available": True,
            "summary": {"total_live_trades": 100, "wins": 90, "losses": 10,
                        "total_pnl_usd": 26.35, "win_rate_pct": 90.0},
            "strategies": [
                {"strategy": "sniper_v1", "trade_count": 80, "wins": 76,
                 "losses": 4, "win_rate_pct": 95.0, "total_pnl_usd": 30.0,
                 "avg_pnl_usd": 0.38},
            ],
            "daily_pnl": [
                {"date": "2026-03-20", "pnl_usd": 2.0, "cumulative_pnl_usd": 24.0},
                {"date": "2026-03-21", "pnl_usd": 1.5, "cumulative_pnl_usd": 25.5},
            ],
            "bankroll": [
                {"timestamp": 1741564800, "datetime": "2026-03-20 00:00", "balance_usd": 124.0},
            ],
            "charts": {
                "cumulative_pnl": {
                    "labels": ["2026-03-20", "2026-03-21"],
                    "values": [24.0, 25.5],
                },
                "strategy_winrate": {
                    "labels": ["sniper_v1"],
                    "values": [95.0],
                },
                "daily_pnl_histogram": {"values": [2.0, 1.5, -0.5, 3.0]},
                "strategy_pnl_distribution": {
                    "categories": ["sniper_v1"],
                    "data_series": [[0.3, 0.5, -0.1, 0.8, 0.4]],
                },
                "winrate_vs_profit": {
                    "series": [{"name": "Strategies", "data": [
                        {"x": 95.0, "y": 0.38, "label": "sniper_v1"},
                    ]}],
                },
                "trade_volume": {"labels": ["sniper_v1"], "values": [80]},
                "bankroll_timeline": {
                    "labels": ["2026-03-20 00:00"],
                    "values": [124.0],
                },
            },
        },
        "learning_intelligence": {
            "available": True,
            "journal": {"total_entries": 500, "recent_entries": 50},
            "apf": {"current_apf": 72.5, "trend": "improving"},
            "charts": {
                "event_types": {
                    "labels": ["session_start", "task_complete", "test_pass", "commit"],
                    "values": [165, 320, 890, 280],
                },
                "apf_trend": {
                    "labels": ["S160", "S161", "S162", "S163", "S164"],
                    "values": [71.0, 71.5, 72.0, 72.3, 72.5],
                },
                "domain_distribution": {
                    "labels": ["general", "trading", "research"],
                    "values": [200, 180, 120],
                },
            },
        },
    }


class TestLearningEventTypesChart(unittest.TestCase):
    """Test learning event types donut chart."""

    def setUp(self):
        self.gen = ReportChartGenerator()

    def test_returns_svg(self):
        svg = self.gen.learning_event_types(_full_data())
        self.assertIn("<svg", svg)

    def test_no_data_when_unavailable(self):
        svg = self.gen.learning_event_types({"learning_intelligence": {"available": False}})
        self.assertIn("No data", svg)

    def test_no_data_when_missing(self):
        svg = self.gen.learning_event_types({})
        self.assertIn("No data", svg)

    def test_empty_chart_data(self):
        data = {"learning_intelligence": {"available": True, "charts": {"event_types": {}}}}
        svg = self.gen.learning_event_types(data)
        self.assertIn("No data", svg)

    def test_no_labels(self):
        data = {"learning_intelligence": {"available": True, "charts": {"event_types": {"labels": [], "values": []}}}}
        svg = self.gen.learning_event_types(data)
        self.assertIn("No data", svg)


class TestLearningAPFTrendChart(unittest.TestCase):
    """Test learning APF trend line chart."""

    def setUp(self):
        self.gen = ReportChartGenerator()

    def test_returns_svg(self):
        svg = self.gen.learning_apf_trend(_full_data())
        self.assertIn("<svg", svg)

    def test_no_data_when_unavailable(self):
        svg = self.gen.learning_apf_trend({"learning_intelligence": {"available": False}})
        self.assertIn("No data", svg)

    def test_no_data_when_missing(self):
        svg = self.gen.learning_apf_trend({})
        self.assertIn("No data", svg)

    def test_single_point(self):
        data = {"learning_intelligence": {"available": True, "charts": {
            "apf_trend": {"labels": ["S164"], "values": [72.5]}}}}
        svg = self.gen.learning_apf_trend(data)
        self.assertIn("<svg", svg)


class TestLearningDomainChart(unittest.TestCase):
    """Test learning domain distribution donut chart."""

    def setUp(self):
        self.gen = ReportChartGenerator()

    def test_returns_svg(self):
        svg = self.gen.learning_domain_distribution(_full_data())
        self.assertIn("<svg", svg)

    def test_no_data_when_unavailable(self):
        svg = self.gen.learning_domain_distribution({"learning_intelligence": {"available": False}})
        self.assertIn("No data", svg)

    def test_no_data_when_missing(self):
        svg = self.gen.learning_domain_distribution({})
        self.assertIn("No data", svg)


class TestCombinedPipeline(unittest.TestCase):
    """Test generate_all and save_all with combined data."""

    def setUp(self):
        self.gen = ReportChartGenerator()

    def test_generate_all_includes_both_kalshi_and_learning(self):
        charts = self.gen.generate_all(_full_data())
        kalshi_keys = [k for k in charts if k.startswith("kalshi_")]
        learning_keys = [k for k in charts if k.startswith("learning_")]
        self.assertEqual(len(kalshi_keys), 10)
        self.assertEqual(len(learning_keys), 3)

    def test_generate_all_total_chart_count(self):
        """Full data should produce at least 18 charts (10 base + 7 kalshi + 3 learning)."""
        charts = self.gen.generate_all(_full_data())
        self.assertGreaterEqual(len(charts), 18)

    def test_generate_all_all_svgs_valid(self):
        """Every chart must be valid SVG (starts with <svg)."""
        charts = self.gen.generate_all(_full_data())
        for name, svg in charts.items():
            self.assertIn("<svg", svg, f"Chart {name} is not valid SVG")

    def test_generate_all_no_none_values(self):
        """No chart should be None."""
        charts = self.gen.generate_all(_full_data())
        for name, svg in charts.items():
            self.assertIsNotNone(svg, f"Chart {name} is None")

    def test_save_all_writes_files(self):
        """save_all should create SVG files on disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportChartGenerator(output_dir=tmpdir)
            paths = gen.save_all(_full_data())
            self.assertGreaterEqual(len(paths), 18)
            for name, path in paths.items():
                self.assertTrue(os.path.exists(path), f"Missing file: {path}")
                self.assertTrue(path.endswith(".svg"), f"Not SVG: {path}")
                with open(path) as f:
                    content = f.read()
                self.assertIn("<svg", content, f"File {name} not valid SVG")

    def test_save_all_creates_output_dir(self):
        """save_all should create the output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "charts_subdir")
            gen = ReportChartGenerator(output_dir=out)
            paths = gen.save_all(_full_data())
            self.assertTrue(os.path.isdir(out))
            self.assertGreater(len(paths), 0)


class TestEmptyDataResilience(unittest.TestCase):
    """Test that all charts handle completely empty data gracefully."""

    def setUp(self):
        self.gen = ReportChartGenerator()
        self.empty_data = {
            "modules": [],
            "summary": {"source_loc": 0, "test_loc": 0, "total_loc": 0},
            "intelligence": {"findings_total": 0},
            "master_tasks_complete": [],
            "master_tasks_active": [],
            "master_tasks_pending": [],
            "frontiers": [],
        }

    def test_generate_all_with_empty_data(self):
        """generate_all should not crash with empty data."""
        charts = self.gen.generate_all(self.empty_data)
        self.assertIsInstance(charts, dict)
        for name, svg in charts.items():
            self.assertIn("<svg", svg, f"Chart {name} missing svg tag")

    def test_no_kalshi_charts_without_data(self):
        charts = self.gen.generate_all(self.empty_data)
        kalshi_keys = [k for k in charts if k.startswith("kalshi_")]
        self.assertEqual(len(kalshi_keys), 0)

    def test_no_learning_charts_without_data(self):
        charts = self.gen.generate_all(self.empty_data)
        learning_keys = [k for k in charts if k.startswith("learning_")]
        self.assertEqual(len(learning_keys), 0)


class TestPartialDataResilience(unittest.TestCase):
    """Test with partially available data (Kalshi yes, learning no, or vice versa)."""

    def setUp(self):
        self.gen = ReportChartGenerator()

    def test_kalshi_only(self):
        data = _full_data()
        data["learning_intelligence"] = {"available": False}
        charts = self.gen.generate_all(data)
        kalshi_keys = [k for k in charts if k.startswith("kalshi_")]
        learning_keys = [k for k in charts if k.startswith("learning_")]
        self.assertEqual(len(kalshi_keys), 10)
        self.assertEqual(len(learning_keys), 0)

    def test_learning_only(self):
        data = _full_data()
        data["kalshi_analytics"] = {"available": False}
        charts = self.gen.generate_all(data)
        kalshi_keys = [k for k in charts if k.startswith("kalshi_")]
        learning_keys = [k for k in charts if k.startswith("learning_")]
        self.assertEqual(len(kalshi_keys), 0)
        self.assertEqual(len(learning_keys), 3)

    def test_kalshi_available_but_empty_charts(self):
        """Kalshi available=True but charts dict is empty."""
        data = _full_data()
        data["kalshi_analytics"]["charts"] = {}
        charts = self.gen.generate_all(data)
        # Should still generate 7 kalshi charts (all will be "No data")
        kalshi_keys = [k for k in charts if k.startswith("kalshi_")]
        self.assertEqual(len(kalshi_keys), 10)

    def test_learning_available_but_empty_charts(self):
        """Learning available=True but charts dict is empty."""
        data = _full_data()
        data["learning_intelligence"]["charts"] = {}
        charts = self.gen.generate_all(data)
        learning_keys = [k for k in charts if k.startswith("learning_")]
        self.assertEqual(len(learning_keys), 3)

    def test_missing_single_chart_data(self):
        """Missing one Kalshi chart's data shouldn't affect others."""
        data = _full_data()
        del data["kalshi_analytics"]["charts"]["cumulative_pnl"]
        charts = self.gen.generate_all(data)
        kalshi_keys = [k for k in charts if k.startswith("kalshi_")]
        self.assertEqual(len(kalshi_keys), 10)  # Still generates all 7


class TestChartNoDataReplacement(unittest.TestCase):
    """Test that 'No data' charts are replaced with invisible SVG in generate_all."""

    def setUp(self):
        self.gen = ReportChartGenerator()

    def test_no_data_charts_replaced(self):
        """Charts with 'No data' text should be replaced with invisible SVG."""
        data = _full_data()
        data["kalshi_analytics"]["charts"] = {}  # Force all Kalshi to "No data"
        charts = self.gen.generate_all(data)
        for name, svg in charts.items():
            if name.startswith("kalshi_"):
                self.assertNotIn("No data</text>", svg,
                                 f"Chart {name} should have been replaced with invisible SVG")
                self.assertIn("width=\"1\"", svg)


if __name__ == "__main__":
    unittest.main()
