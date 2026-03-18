#!/usr/bin/env python3
"""Tests for dashboard_generator.py — HTML dashboard for CCA project data."""

import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_generator import (
    DashboardRenderer,
    DashboardData,
    ModuleCard,
    MasterTaskRow,
    MetricCard,
)


class TestDashboardData(unittest.TestCase):
    """Test DashboardData construction."""

    def test_defaults(self):
        d = DashboardData()
        self.assertEqual(d.title, "CCA Project Dashboard")
        self.assertIsNotNone(d.generated_date)
        self.assertEqual(d.modules, [])
        self.assertEqual(d.master_tasks, [])
        self.assertEqual(d.metrics, [])

    def test_custom_title(self):
        d = DashboardData(title="Custom Dashboard")
        self.assertEqual(d.title, "Custom Dashboard")

    def test_add_module(self):
        d = DashboardData()
        d.modules.append(ModuleCard(
            name="Memory System",
            path="memory-system/",
            status="COMPLETE",
            tests=94,
            items="MEM-1-5 COMPLETE",
        ))
        self.assertEqual(len(d.modules), 1)
        self.assertEqual(d.modules[0].name, "Memory System")

    def test_add_metric(self):
        d = DashboardData()
        d.metrics.append(MetricCard(
            label="Total Tests",
            value="1653",
            status="success",
        ))
        self.assertEqual(len(d.metrics), 1)

    def test_to_dict(self):
        d = DashboardData(title="Test")
        d.modules.append(ModuleCard(
            name="Test Module", path="test/", status="ACTIVE", tests=10, items="TST-1"
        ))
        result = d.to_dict()
        self.assertEqual(result["title"], "Test")
        self.assertEqual(len(result["modules"]), 1)


class TestModuleCard(unittest.TestCase):
    """Test ModuleCard data class."""

    def test_creation(self):
        m = ModuleCard(
            name="Agent Guard",
            path="agent-guard/",
            status="COMPLETE",
            tests=264,
            items="AG-1-7 COMPLETE",
        )
        self.assertEqual(m.name, "Agent Guard")
        self.assertEqual(m.tests, 264)
        self.assertEqual(m.status, "COMPLETE")

    def test_status_color_complete(self):
        m = ModuleCard(name="X", path="x/", status="COMPLETE", tests=1, items="")
        self.assertEqual(m.status_color(), "#16c79a")

    def test_status_color_active(self):
        m = ModuleCard(name="X", path="x/", status="ACTIVE", tests=1, items="")
        self.assertEqual(m.status_color(), "#0f3460")

    def test_status_color_failing(self):
        m = ModuleCard(name="X", path="x/", status="FAILING", tests=0, items="")
        self.assertEqual(m.status_color(), "#e94560")


class TestMasterTaskRow(unittest.TestCase):
    """Test MasterTaskRow data class."""

    def test_creation(self):
        t = MasterTaskRow(
            id="MT-7",
            name="Trace Analyzer",
            score=9.0,
            status="Phase 2 COMPLETE",
        )
        self.assertEqual(t.id, "MT-7")
        self.assertEqual(t.score, 9.0)

    def test_score_bar_width(self):
        t = MasterTaskRow(id="MT-7", name="X", score=7.5, status="Active")
        # Score is out of 20 (max possible), so 7.5/20 = 37.5%
        self.assertEqual(t.score_bar_width(), 37.5)

    def test_score_bar_width_capped(self):
        t = MasterTaskRow(id="MT-7", name="X", score=25.0, status="Active")
        self.assertEqual(t.score_bar_width(), 100.0)


class TestMetricCard(unittest.TestCase):
    """Test MetricCard data class."""

    def test_creation(self):
        m = MetricCard(label="Total Tests", value="1653", status="success")
        self.assertEqual(m.label, "Total Tests")
        self.assertEqual(m.value, "1653")

    def test_status_color_success(self):
        m = MetricCard(label="X", value="0", status="success")
        self.assertEqual(m.status_color(), "#16c79a")

    def test_status_color_warning(self):
        m = MetricCard(label="X", value="0", status="warning")
        self.assertEqual(m.status_color(), "#f59e0b")

    def test_status_color_critical(self):
        m = MetricCard(label="X", value="0", status="critical")
        self.assertEqual(m.status_color(), "#e94560")

    def test_status_color_default(self):
        m = MetricCard(label="X", value="0", status="info")
        self.assertEqual(m.status_color(), "#0f3460")


class TestDashboardRenderer(unittest.TestCase):
    """Test HTML rendering."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.data = DashboardData(title="Test Dashboard")
        self.data.metrics = [
            MetricCard(label="Tests", value="1653", status="success"),
            MetricCard(label="Modules", value="9", status="info"),
        ]
        self.data.modules = [
            ModuleCard(
                name="Memory System", path="memory-system/",
                status="COMPLETE", tests=94, items="MEM-1-5 COMPLETE",
            ),
            ModuleCard(
                name="Context Monitor", path="context-monitor/",
                status="ACTIVE", tests=197, items="CTX-1-6 + Pacer",
            ),
        ]
        self.data.master_tasks = [
            MasterTaskRow(id="MT-10", name="YoYo Self-Learning", score=9.0, status="Phase 2 COMPLETE"),
            MasterTaskRow(id="MT-9", name="Autonomous Scanning", score=8.0, status="Phase 2 COMPLETE"),
        ]

    def test_render_returns_string(self):
        html = self.renderer.render(self.data)
        self.assertIsInstance(html, str)

    def test_render_contains_title(self):
        html = self.renderer.render(self.data)
        self.assertIn("Test Dashboard", html)

    def test_render_contains_doctype(self):
        html = self.renderer.render(self.data)
        self.assertIn("<!DOCTYPE html>", html)

    def test_render_contains_module_names(self):
        html = self.renderer.render(self.data)
        self.assertIn("Memory System", html)
        self.assertIn("Context Monitor", html)

    def test_render_contains_metrics(self):
        html = self.renderer.render(self.data)
        self.assertIn("1653", html)
        self.assertIn("Tests", html)

    def test_render_contains_master_tasks(self):
        html = self.renderer.render(self.data)
        self.assertIn("MT-10", html)
        self.assertIn("YoYo Self-Learning", html)

    def test_render_contains_design_colors(self):
        """Must use colors from design-guide.md."""
        html = self.renderer.render(self.data)
        self.assertIn("#1a1a2e", html)  # Primary
        self.assertIn("#16c79a", html)  # Success

    def test_render_is_self_contained(self):
        """No external CSS/JS links — everything inline."""
        html = self.renderer.render(self.data)
        self.assertNotIn('rel="stylesheet"', html)
        self.assertNotIn('<script src=', html)
        self.assertIn("<style>", html)

    def test_render_responsive(self):
        """Should include viewport meta for mobile."""
        html = self.renderer.render(self.data)
        self.assertIn("viewport", html)

    def test_render_empty_data(self):
        """Should handle empty data gracefully."""
        html = self.renderer.render(DashboardData())
        self.assertIn("<!DOCTYPE html>", html)

    def test_render_special_characters(self):
        """Module names with special chars should be escaped."""
        data = DashboardData()
        data.modules.append(ModuleCard(
            name="Test <script>alert('xss')</script>",
            path="test/", status="ACTIVE", tests=1, items="",
        ))
        html = self.renderer.render(data)
        self.assertNotIn("<script>alert", html)

    def test_write_to_file(self):
        """Render and write to a file."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            self.renderer.render_to_file(self.data, path)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("Test Dashboard", content)
        finally:
            os.unlink(path)

    def test_render_has_generation_timestamp(self):
        html = self.renderer.render(self.data)
        self.assertIn("Generated", html)

    def test_render_has_status_indicators(self):
        """Status dots/indicators should appear for modules."""
        html = self.renderer.render(self.data)
        # COMPLETE module should show success color
        self.assertIn("#16c79a", html)


class TestDashboardRendererCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_cli_generate(self):
        from dashboard_generator import cli_main
        import io
        from contextlib import redirect_stdout

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            f_out = io.StringIO()
            with redirect_stdout(f_out):
                cli_main(["generate", "--output", path, "--demo"])
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                content = f.read()
            self.assertIn("<!DOCTYPE html>", content)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_cli_no_args(self):
        from dashboard_generator import cli_main
        import io
        from contextlib import redirect_stdout

        f_out = io.StringIO()
        with redirect_stdout(f_out):
            cli_main([])
        output = f_out.getvalue()
        self.assertIn("Usage", output)


if __name__ == "__main__":
    unittest.main()
