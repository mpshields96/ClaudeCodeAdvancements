#!/usr/bin/env python3
"""
test_dashboard_generator_extended.py — Extended edge-case tests for dashboard_generator.py

Covers: XSS escaping edge cases, score_bar_width boundaries, status_color fallback,
DashboardData.to_dict round-trips, _render_daily_diff all branches, _render_charts
with/without data, cli_main missing-output and unknown-cmd, _demo_data structure,
session_number display, render_to_file atomic write, MetricCard unknown status,
and DashboardData with daily_diff.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_generator import (
    DashboardRenderer,
    DashboardData,
    ModuleCard,
    MasterTaskRow,
    MetricCard,
    _e,
    COLORS,
    _demo_data,
    cli_main,
)


# ===== XSS / HTML escaping =====

class TestEscapeFunction(unittest.TestCase):
    """Edge cases for the _e() HTML escape helper."""

    def test_ampersand_escaped(self):
        self.assertEqual(_e("a & b"), "a &amp; b")

    def test_less_than_escaped(self):
        self.assertEqual(_e("<script>"), "&lt;script&gt;")

    def test_quote_escaped(self):
        self.assertIn("&quot;", _e('"hello"'))

    def test_plain_text_unchanged(self):
        self.assertEqual(_e("hello world"), "hello world")

    def test_int_input_converts(self):
        """_e() calls str() on non-string input."""
        self.assertEqual(_e(42), "42")

    def test_empty_string(self):
        self.assertEqual(_e(""), "")

    def test_only_special_chars(self):
        result = _e("<>&\"'")
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertNotIn("&\"", result)


# ===== ModuleCard extended =====

class TestModuleCardExtended(unittest.TestCase):
    """Extended edge cases for ModuleCard."""

    def test_status_color_unknown_defaults_to_accent(self):
        """Status not COMPLETE or FAILING falls through to accent color."""
        m = ModuleCard(name="X", path="x/", status="PENDING", tests=5, items="")
        self.assertEqual(m.status_color(), COLORS["accent"])

    def test_status_case_sensitive_complete(self):
        """'complete' (lowercase) does NOT match COMPLETE — returns accent."""
        m = ModuleCard(name="X", path="x/", status="complete", tests=5, items="")
        # Not COMPLETE uppercase, not FAILING — falls through to accent
        self.assertEqual(m.status_color(), COLORS["accent"])

    def test_to_dict_has_all_fields(self):
        m = ModuleCard(name="Agent Guard", path="agent-guard/", status="COMPLETE", tests=264, items="AG-1-7")
        d = m.to_dict()
        for key in ("name", "path", "status", "tests", "items"):
            self.assertIn(key, d)

    def test_to_dict_values_correct(self):
        m = ModuleCard(name="M", path="p/", status="FAILING", tests=0, items="x")
        d = m.to_dict()
        self.assertEqual(d["name"], "M")
        self.assertEqual(d["tests"], 0)
        self.assertEqual(d["status"], "FAILING")

    def test_zero_tests(self):
        m = ModuleCard(name="X", path="x/", status="ACTIVE", tests=0, items="")
        self.assertEqual(m.tests, 0)


# ===== MasterTaskRow extended =====

class TestMasterTaskRowExtended(unittest.TestCase):
    """Extended edge cases for MasterTaskRow.score_bar_width."""

    def test_score_zero_gives_zero_width(self):
        t = MasterTaskRow(id="MT-1", name="X", score=0.0, status="Pending")
        self.assertEqual(t.score_bar_width(), 0.0)

    def test_score_exactly_20_gives_100(self):
        t = MasterTaskRow(id="MT-1", name="X", score=20.0, status="Active")
        self.assertEqual(t.score_bar_width(), 100.0)

    def test_score_above_20_capped_at_100(self):
        t = MasterTaskRow(id="MT-1", name="X", score=30.0, status="Active")
        self.assertEqual(t.score_bar_width(), 100.0)

    def test_score_10_is_50_percent(self):
        t = MasterTaskRow(id="MT-1", name="X", score=10.0, status="Active")
        self.assertAlmostEqual(t.score_bar_width(), 50.0)

    def test_score_1_is_5_percent(self):
        t = MasterTaskRow(id="MT-1", name="X", score=1.0, status="Active")
        self.assertAlmostEqual(t.score_bar_width(), 5.0)

    def test_to_dict_includes_score_bar_width(self):
        t = MasterTaskRow(id="MT-5", name="Y", score=10.0, status="In Progress")
        d = t.to_dict()
        self.assertIn("score_bar_width", d)
        self.assertAlmostEqual(d["score_bar_width"], 50.0)

    def test_to_dict_all_fields(self):
        t = MasterTaskRow(id="MT-5", name="Y", score=10.0, status="In Progress")
        d = t.to_dict()
        for key in ("id", "name", "score", "status"):
            self.assertIn(key, d)


# ===== MetricCard extended =====

class TestMetricCardExtended(unittest.TestCase):
    """Extended edge cases for MetricCard."""

    def test_unknown_status_returns_accent(self):
        m = MetricCard(label="X", value="0", status="unknown_status")
        self.assertEqual(m.status_color(), COLORS["accent"])

    def test_empty_status_returns_accent(self):
        m = MetricCard(label="X", value="0", status="")
        self.assertEqual(m.status_color(), COLORS["accent"])

    def test_to_dict_fields(self):
        m = MetricCard(label="Total Tests", value="500", status="success")
        d = m.to_dict()
        self.assertEqual(d["label"], "Total Tests")
        self.assertEqual(d["value"], "500")
        self.assertEqual(d["status"], "success")

    def test_default_status_is_info(self):
        m = MetricCard(label="X", value="0")
        self.assertEqual(m.status, "info")


# ===== DashboardData extended =====

class TestDashboardDataExtended(unittest.TestCase):
    """Extended edge cases for DashboardData.to_dict."""

    def test_to_dict_with_daily_diff(self):
        """daily_diff is included in to_dict output."""
        d = DashboardData()
        d.daily_diff = {"date_range": {"from": "2026-03-20", "to": "2026-03-21"}}
        result = d.to_dict()
        self.assertIn("daily_diff", result)
        self.assertIsNotNone(result["daily_diff"])

    def test_to_dict_without_daily_diff(self):
        d = DashboardData()
        result = d.to_dict()
        self.assertIsNone(result["daily_diff"])

    def test_to_dict_session_number(self):
        d = DashboardData(session_number=42)
        result = d.to_dict()
        self.assertEqual(result["session_number"], 42)

    def test_to_dict_includes_metrics_list(self):
        d = DashboardData()
        d.metrics = [MetricCard("X", "1", "success"), MetricCard("Y", "2", "info")]
        result = d.to_dict()
        self.assertEqual(len(result["metrics"]), 2)

    def test_generated_date_is_today(self):
        """generated_date defaults to today in ISO format."""
        from datetime import date
        d = DashboardData()
        self.assertEqual(d.generated_date, date.today().isoformat())


# ===== DashboardRenderer render edges =====

class TestDashboardRendererExtended(unittest.TestCase):
    """Extended rendering edge cases."""

    def setUp(self):
        self.renderer = DashboardRenderer()

    def test_xss_in_title_escaped(self):
        """HTML in dashboard title must be escaped."""
        data = DashboardData(title="<script>alert(1)</script>")
        html = self.renderer.render(data)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_xss_in_metric_value(self):
        """HTML in metric value must be escaped."""
        data = DashboardData()
        data.metrics = [MetricCard(label="X", value="<b>bold</b>", status="info")]
        html = self.renderer.render(data)
        self.assertNotIn("<b>bold</b>", html)

    def test_xss_in_module_path(self):
        """HTML in module path is escaped."""
        data = DashboardData()
        data.modules = [ModuleCard(
            name="M", path="path/<evil>", status="ACTIVE", tests=1, items=""
        )]
        html = self.renderer.render(data)
        self.assertNotIn("path/<evil>", html)

    def test_session_number_shown_when_nonzero(self):
        """Session number appears in subtitle when > 0."""
        data = DashboardData(session_number=99)
        html = self.renderer.render(data)
        self.assertIn("Session 99", html)

    def test_session_number_hidden_when_zero(self):
        """Session number NOT shown when 0."""
        data = DashboardData(session_number=0)
        html = self.renderer.render(data)
        self.assertNotIn("Session 0", html)

    def test_empty_metrics_no_metrics_div(self):
        """No metrics = no metric-card elements rendered."""
        data = DashboardData()
        html = self.renderer.render(data)
        # CSS defines .metric-card but no <div class="metric-card"> should appear
        self.assertNotIn('<div class="metric-card"', html)

    def test_empty_modules_no_modules_section(self):
        """No modules = no Modules section header."""
        data = DashboardData()
        html = self.renderer.render(data)
        self.assertNotIn(">Modules<", html)

    def test_empty_master_tasks_no_tasks_table(self):
        """No master tasks = no tasks table element rendered."""
        data = DashboardData()
        html = self.renderer.render(data)
        # CSS defines .tasks-table but no <table class="tasks-table"> should appear
        self.assertNotIn('<table class="tasks-table"', html)

    def test_failing_module_uses_highlight_color(self):
        """FAILING module uses highlight (red) color."""
        data = DashboardData()
        data.modules = [ModuleCard(
            name="Broken", path="x/", status="FAILING", tests=0, items=""
        )]
        html = self.renderer.render(data)
        self.assertIn(COLORS["highlight"], html)

    def test_complete_module_uses_success_color(self):
        """COMPLETE module uses success (green) color."""
        data = DashboardData()
        data.modules = [ModuleCard(
            name="Done", path="x/", status="COMPLETE", tests=10, items=""
        )]
        html = self.renderer.render(data)
        self.assertIn(COLORS["success"], html)

    def test_multiple_tasks_all_appear(self):
        """Multiple master task rows are all rendered."""
        data = DashboardData()
        data.master_tasks = [
            MasterTaskRow(id="MT-1", name="Alpha", score=5.0, status="Active"),
            MasterTaskRow(id="MT-2", name="Beta", score=8.0, status="Active"),
            MasterTaskRow(id="MT-3", name="Gamma", score=12.0, status="Complete"),
        ]
        html = self.renderer.render(data)
        self.assertIn("MT-1", html)
        self.assertIn("MT-2", html)
        self.assertIn("MT-3", html)
        self.assertIn("Alpha", html)
        self.assertIn("Gamma", html)

    def test_render_to_file_creates_file(self):
        """render_to_file writes to the specified path."""
        data = DashboardData(title="File Test")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.html")
            self.renderer.render_to_file(data, path)
            self.assertTrue(os.path.exists(path))

    def test_render_to_file_content_correct(self):
        """render_to_file content matches render() output."""
        data = DashboardData(title="Check Content")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.html")
            self.renderer.render_to_file(data, path)
            with open(path) as f:
                content = f.read()
            self.assertIn("Check Content", content)

    def test_render_to_file_no_tmp_leftover(self):
        """Atomic write — .tmp file should not exist after render_to_file."""
        data = DashboardData()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.html")
            self.renderer.render_to_file(data, path)
            self.assertFalse(os.path.exists(path + ".tmp"))

    def test_html_has_lang_attribute(self):
        """HTML tag includes lang='en' for accessibility."""
        html = self.renderer.render(DashboardData())
        self.assertIn('lang="en"', html)

    def test_html_has_charset_meta(self):
        """<meta charset> is present."""
        html = self.renderer.render(DashboardData())
        self.assertIn("utf-8", html.lower())


# ===== _render_daily_diff branch coverage =====

class TestRenderDailyDiff(unittest.TestCase):
    """Branch coverage for _render_daily_diff."""

    def setUp(self):
        self.renderer = DashboardRenderer()

    def _render_with_diff(self, diff):
        data = DashboardData()
        data.daily_diff = diff
        html = self.renderer.render(data)
        return html

    def test_none_diff_no_daily_section(self):
        """No diff = no daily-diff div rendered."""
        html = self._render_with_diff(None)
        # CSS defines .daily-diff but no <div class="daily-diff"> should appear
        self.assertNotIn('<div class="daily-diff"', html)

    def test_positive_deltas_show_plus(self):
        diff = {
            "date_range": {"from": "2026-03-20", "to": "2026-03-21"},
            "totals_delta": {
                "tests": {"delta": 50},
                "suites": {"delta": 2},
                "loc": {"delta": 300},
                "py_files": {"delta": 5},
            },
            "module_deltas": [],
        }
        html = self._render_with_diff(diff)
        self.assertIn("+50", html)
        self.assertIn("positive", html)

    def test_negative_deltas_show_negative_class(self):
        diff = {
            "date_range": {"from": "2026-03-20", "to": "2026-03-21"},
            "totals_delta": {"tests": {"delta": -10}, "suites": {"delta": 0}},
            "module_deltas": [],
        }
        html = self._render_with_diff(diff)
        self.assertIn("negative", html)
        self.assertIn("-10", html)

    def test_zero_deltas_show_zero_class(self):
        """All zero deltas shows the 'zero' placeholder."""
        diff = {
            "date_range": {"from": "2026-03-20", "to": "2026-03-21"},
            "totals_delta": {},
            "module_deltas": [],
        }
        html = self._render_with_diff(diff)
        self.assertIn("zero", html)
        self.assertIn("No changes", html)

    def test_module_deltas_shown(self):
        """Module-level changes are listed in diff output."""
        diff = {
            "date_range": {"from": "2026-03-20", "to": "2026-03-21"},
            "totals_delta": {},
            "module_deltas": [
                {"name": "Memory System", "tests_delta": 5, "loc_delta": 50},
            ],
        }
        html = self._render_with_diff(diff)
        self.assertIn("Memory System", html)
        self.assertIn("+5 tests", html)

    def test_module_with_zero_deltas_not_shown(self):
        """Module with all-zero deltas is not listed in diff modules."""
        diff = {
            "date_range": {"from": "2026-03-20", "to": "2026-03-21"},
            "totals_delta": {},
            "module_deltas": [
                {"name": "No Change Module", "tests_delta": 0, "loc_delta": 0},
            ],
        }
        html = self._render_with_diff(diff)
        self.assertNotIn("No Change Module", html)

    def test_date_range_shown(self):
        """Date range appears in diff header."""
        diff = {
            "date_range": {"from": "2026-03-01", "to": "2026-03-21"},
            "totals_delta": {},
            "module_deltas": [],
        }
        html = self._render_with_diff(diff)
        self.assertIn("2026-03-01", html)
        self.assertIn("2026-03-21", html)

    def test_missing_date_range_shows_question_marks(self):
        """Missing date_range values show '?' fallbacks."""
        diff = {"date_range": {}, "totals_delta": {}, "module_deltas": []}
        html = self._render_with_diff(diff)
        self.assertIn("?", html)


# ===== CLI extended =====

class TestCliMainExtended(unittest.TestCase):
    """Extended CLI edge cases."""

    def _capture(self, args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli_main(args)
        return buf.getvalue()

    def test_missing_output_flag_prints_error(self):
        """generate without --output prints an error."""
        out = self._capture(["generate"])
        self.assertIn("Error", out)

    def test_unknown_command_prints_message(self):
        out = self._capture(["foobar"])
        self.assertIn("Unknown", out)

    def test_generate_demo_writes_file(self):
        """--demo writes a real HTML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "demo.html")
            out = self._capture(["generate", "--output", path, "--demo"])
            self.assertTrue(os.path.exists(path))
            self.assertIn(path, out)

    def test_generate_demo_file_has_doctype(self):
        """Demo HTML file contains <!DOCTYPE html>."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "demo.html")
            self._capture(["generate", "--output", path, "--demo"])
            with open(path) as f:
                content = f.read()
            self.assertIn("<!DOCTYPE html>", content)

    def test_no_args_shows_usage(self):
        out = self._capture([])
        self.assertIn("Usage", out)
        self.assertIn("--output", out)


# ===== _demo_data =====

class TestDemoData(unittest.TestCase):
    """Verify _demo_data() returns a well-formed DashboardData."""

    def setUp(self):
        self.data = _demo_data()

    def test_returns_dashboard_data(self):
        self.assertIsInstance(self.data, DashboardData)

    def test_has_modules(self):
        self.assertGreater(len(self.data.modules), 0)

    def test_has_metrics(self):
        self.assertGreater(len(self.data.metrics), 0)

    def test_has_master_tasks(self):
        self.assertGreater(len(self.data.master_tasks), 0)

    def test_title_set(self):
        self.assertIsInstance(self.data.title, str)
        self.assertTrue(self.data.title)

    def test_session_number_positive(self):
        self.assertGreater(self.data.session_number, 0)

    def test_all_modules_have_valid_status(self):
        valid = {"COMPLETE", "ACTIVE", "FAILING"}
        for m in self.data.modules:
            self.assertIn(m.status, valid, f"{m.name} has invalid status {m.status}")

    def test_all_tasks_have_non_negative_score(self):
        for t in self.data.master_tasks:
            self.assertGreaterEqual(t.score, 0.0)

    def test_renders_without_error(self):
        """Demo data must render to valid HTML without exceptions."""
        renderer = DashboardRenderer()
        html = renderer.render(self.data)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn(self.data.title, html)


if __name__ == "__main__":
    unittest.main()
