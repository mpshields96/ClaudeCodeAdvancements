"""Tests for design-skills/report_generator.py — CCA Report Generator."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent dirs to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestDataCollector(unittest.TestCase):
    """Tests for CCADataCollector — gathers project data for reports."""

    def test_read_file_missing(self):
        """Returns empty string for missing files."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake_nonexistent")
        result = collector._read_file("nonexistent.md")
        self.assertEqual(result, "")

    def test_count_lines(self):
        """Counts lines in a file."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            f.flush()
            count = collector._count_lines(f.name)
            self.assertEqual(count, 3)
        os.unlink(f.name)

    def test_count_lines_missing_file(self):
        """Returns 0 for missing files."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        count = collector._count_lines("/tmp/totally_nonexistent_file.py")
        self.assertEqual(count, 0)

    def test_module_definitions_present(self):
        """All 9 modules have definitions."""
        from report_generator import CCADataCollector
        self.assertEqual(len(CCADataCollector.MODULE_DEFINITIONS), 9)

    def test_module_definitions_have_required_fields(self):
        """Each module definition has name, path, description, components."""
        from report_generator import CCADataCollector
        for mod in CCADataCollector.MODULE_DEFINITIONS:
            self.assertIn("name", mod)
            self.assertIn("path", mod)
            self.assertIn("description", mod)
            self.assertIn("components", mod)
            self.assertIsInstance(mod["components"], list)
            self.assertGreater(len(mod["components"]), 0)

    def test_hooks_defined(self):
        """All 18 hooks are defined."""
        from report_generator import CCADataCollector
        self.assertEqual(len(CCADataCollector.HOOKS), 18)

    def test_hooks_have_required_fields(self):
        """Each hook has event, matcher, file, purpose."""
        from report_generator import CCADataCollector
        for hook in CCADataCollector.HOOKS:
            self.assertIn("event", hook)
            self.assertIn("matcher", hook)
            self.assertIn("file", hook)
            self.assertIn("purpose", hook)

    def test_architecture_decisions_defined(self):
        """Architecture decisions are defined."""
        from report_generator import CCADataCollector
        self.assertGreater(len(CCADataCollector.ARCHITECTURE_DECISIONS), 5)

    def test_collect_intelligence_empty(self):
        """Returns zero counts when FINDINGS_LOG.md is missing."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake_nonexistent")
        intel = collector.collect_intelligence()
        self.assertEqual(intel["findings_total"], 0)
        self.assertEqual(intel["build"], 0)

    def test_collect_self_learning(self):
        """Returns self-learning metrics."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake_nonexistent")
        sl = collector.collect_self_learning()
        self.assertIn("strategies_total", sl)
        self.assertIn("papers_logged", sl)
        self.assertIn("sentinel_rate", sl)

    def test_collect_risks(self):
        """Returns risk items."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake_nonexistent")
        risks = collector.collect_risks()
        self.assertIsInstance(risks, list)
        for risk in risks:
            self.assertIn("title", risk)
            self.assertIn("severity", risk)
            self.assertIn("description", risk)

    def test_collect_priorities_empty(self):
        """Returns fallback when SESSION_STATE.md is missing."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake_nonexistent")
        priorities = collector.collect_priorities()
        self.assertIsInstance(priorities, list)
        self.assertGreater(len(priorities), 0)

    def test_build_executive_summary(self):
        """Generates executive summary text."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        modules = [{"tests": 100, "status": "COMPLETE"}, {"tests": 50, "status": "ACTIVE"}]
        summary = collector.build_executive_summary(52, modules, [1], [2, 3], [4])
        self.assertIn("ClaudeCodeAdvancements", summary)
        self.assertIn("52", summary)
        self.assertIn("150", summary)  # total tests


class TestReportRenderer(unittest.TestCase):
    """Tests for ReportRenderer — calls Typst to generate PDF."""

    def test_render_returns_path(self):
        """render() returns the output PDF path."""
        from report_generator import ReportRenderer
        renderer = ReportRenderer()
        with patch("report_generator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with tempfile.TemporaryDirectory() as tmpdir:
                data = {"title": "Test", "session": 1}
                data_path = os.path.join(tmpdir, "data.json")
                with open(data_path, "w") as f:
                    json.dump(data, f)
                output = os.path.join(tmpdir, "report.pdf")
                result = renderer.render(
                    template="cca-report",
                    data_path=data_path,
                    output_path=output,
                )
                self.assertEqual(result, output)
                mock_run.assert_called_once()

    def test_render_typst_not_found(self):
        """Raises RuntimeError if Typst not installed."""
        from report_generator import ReportRenderer
        renderer = ReportRenderer()
        with patch("report_generator.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                renderer.render("cca-report", "/tmp/data.json", "/tmp/out.pdf")
            self.assertIn("Typst", str(ctx.exception))

    def test_render_typst_fails(self):
        """Raises RuntimeError if Typst compilation fails."""
        from report_generator import ReportRenderer
        renderer = ReportRenderer()
        with patch("report_generator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error: something broke")
            with patch("report_generator.shutil.which", return_value="/usr/bin/typst"):
                with self.assertRaises(RuntimeError) as ctx:
                    renderer.render("cca-report", "/tmp/data.json", "/tmp/out.pdf")
                self.assertIn("Typst compilation failed", str(ctx.exception))

    def test_template_path_resolution(self):
        """Resolves template name to .typ file path."""
        from report_generator import ReportRenderer
        renderer = ReportRenderer()
        path = renderer.template_path("cca-report")
        self.assertTrue(path.endswith("cca-report.typ"))
        self.assertIn("templates", path)

    def test_available_templates(self):
        """Lists available templates."""
        from report_generator import ReportRenderer
        renderer = ReportRenderer()
        templates = renderer.available_templates()
        self.assertIsInstance(templates, list)
        self.assertIn("cca-report", templates)


class TestCLI(unittest.TestCase):
    """Tests for CLI interface."""

    def test_cli_generate_requires_output(self):
        """CLI generate command requires --output."""
        from report_generator import parse_args
        with self.assertRaises(SystemExit):
            parse_args(["generate"])

    def test_cli_generate_parses_args(self):
        """CLI generate command parses arguments."""
        from report_generator import parse_args
        args = parse_args(["generate", "--output", "/tmp/report.pdf"])
        self.assertEqual(args.command, "generate")
        self.assertEqual(args.output, "/tmp/report.pdf")

    def test_cli_templates_command(self):
        """CLI templates command exists."""
        from report_generator import parse_args
        args = parse_args(["templates"])
        self.assertEqual(args.command, "templates")

    def test_cli_generate_with_session(self):
        """CLI generate accepts --session."""
        from report_generator import parse_args
        args = parse_args(["generate", "--output", "/tmp/report.pdf", "--session", "41"])
        self.assertEqual(args.session, 41)

    def test_cli_generate_with_template(self):
        """CLI generate accepts --template."""
        from report_generator import parse_args
        args = parse_args(["generate", "--output", "/tmp/report.pdf", "--template", "cca-report"])
        self.assertEqual(args.template, "cca-report")


class TestIntegration(unittest.TestCase):
    """Integration tests — only run if Typst is installed."""

    def setUp(self):
        """Skip if Typst not available."""
        import shutil
        if not shutil.which("typst"):
            self.skipTest("Typst not installed")

    def test_full_pipeline_from_real_project(self):
        """Full pipeline: real project data -> JSON -> Typst -> PDF."""
        from report_generator import CCADataCollector, ReportRenderer
        project_root = str(Path(__file__).parent.parent.parent)
        collector = CCADataCollector(project_root=project_root)
        data = collector.collect_from_project(session=52)

        # Verify data structure
        self.assertIn("summary", data)
        self.assertIn("modules", data)
        self.assertIn("master_tasks_complete", data)
        self.assertIn("master_tasks_active", data)
        self.assertIn("master_tasks_pending", data)
        self.assertIn("hooks", data)
        self.assertIn("intelligence", data)
        self.assertIn("self_learning", data)
        self.assertIn("risks", data)
        self.assertIn("next_priorities", data)
        self.assertIn("architecture_decisions", data)

        # Verify module data
        self.assertGreater(len(data["modules"]), 5)
        for mod in data["modules"]:
            self.assertIn("name", mod)
            self.assertIn("tests", mod)
            self.assertIn("loc", mod)
            self.assertIn("description", mod)
            self.assertIn("components", mod)

        # Generate PDF
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            with open(data_path, "w") as f:
                json.dump(data, f)

            output_path = os.path.join(tmpdir, "report.pdf")
            renderer = ReportRenderer()
            result = renderer.render("cca-report", data_path, output_path)
            self.assertTrue(os.path.exists(result))
            self.assertGreater(os.path.getsize(result), 10000)  # Should be substantial PDF

    def test_full_pipeline_with_charts(self):
        """Full pipeline with chart generation: data -> charts -> JSON -> Typst -> PDF."""
        from report_generator import CCADataCollector, ReportRenderer, ReportChartGenerator
        project_root = str(Path(__file__).parent.parent.parent)
        collector = CCADataCollector(project_root=project_root)
        data = collector.collect_from_project(session=118)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Generate charts
            chart_dir = os.path.join(tmpdir, "charts")
            chart_gen = ReportChartGenerator(output_dir=chart_dir)
            chart_paths = chart_gen.save_all(data)

            self.assertGreaterEqual(len(chart_paths), 7)  # 7 base + up to 7 Kalshi charts
            for name, path in chart_paths.items():
                self.assertTrue(os.path.exists(path), f"Chart {name} not found at {path}")
                self.assertTrue(path.endswith(".svg"))
                size = os.path.getsize(path)
                self.assertGreater(size, 50, f"Chart {name} is too small ({size} bytes)")

            # Generate PDF with charts
            data_path = os.path.join(tmpdir, "data.json")
            with open(data_path, "w") as f:
                json.dump(data, f)

            output_path = os.path.join(tmpdir, "report_with_charts.pdf")
            renderer = ReportRenderer()
            result = renderer.render("cca-report", data_path, output_path, chart_dir=chart_dir)
            self.assertTrue(os.path.exists(result))
            self.assertGreater(os.path.getsize(result), 10000)


class TestChartIntegration(unittest.TestCase):
    """Tests for chart generation in the report pipeline."""

    def test_render_passes_chart_dir_to_typst(self):
        """render() passes chart_dir as --input to Typst."""
        from report_generator import ReportRenderer
        renderer = ReportRenderer()
        with patch("report_generator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with tempfile.TemporaryDirectory() as tmpdir:
                data_path = os.path.join(tmpdir, "data.json")
                with open(data_path, "w") as f:
                    json.dump({"title": "Test"}, f)
                chart_dir = os.path.join(tmpdir, "charts")
                os.makedirs(chart_dir)

                renderer.render("cca-report", data_path, "/tmp/out.pdf", chart_dir=chart_dir)
                call_args = mock_run.call_args[0][0]
                self.assertIn("--input", call_args)
                # Find the chart_dir input
                found = False
                for i, arg in enumerate(call_args):
                    if arg.startswith("chart_dir="):
                        found = True
                        self.assertIn(chart_dir, arg)
                self.assertTrue(found, "chart_dir not passed to Typst")

    def test_render_without_chart_dir(self):
        """render() works without chart_dir (backwards compatible)."""
        from report_generator import ReportRenderer
        renderer = ReportRenderer()
        with patch("report_generator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with tempfile.TemporaryDirectory() as tmpdir:
                data_path = os.path.join(tmpdir, "data.json")
                with open(data_path, "w") as f:
                    json.dump({"title": "Test"}, f)

                renderer.render("cca-report", data_path, "/tmp/out.pdf")
                call_args = mock_run.call_args[0][0]
                # Should NOT have chart_dir input
                chart_inputs = [a for a in call_args if "chart_dir" in str(a)]
                self.assertEqual(len(chart_inputs), 0)

    def test_chart_generator_produces_six_charts(self):
        """ReportChartGenerator.generate_all produces 6 named charts."""
        from report_charts import ReportChartGenerator
        gen = ReportChartGenerator()
        data = {
            "modules": [{"name": "Test", "tests": 100}],
            "intelligence": {"findings_total": 10, "build": 3, "adapt": 2, "reference": 3, "reference_personal": 1, "skip": 1, "other": 0},
            "master_tasks_complete": [{"id": "MT-1"}],
            "master_tasks_active": [{"id": "MT-2", "phases_done": 3, "total_phases": 5}],
            "master_tasks_pending": [],
            "summary": {"source_loc": 5000, "test_loc": 4000},
            "frontiers": [{"name": "Memory", "tests": 340}],
        }
        charts = gen.generate_all(data)
        self.assertEqual(len(charts), 10)
        expected = {"module_tests", "intelligence", "mt_status", "loc_distribution", "mt_progress", "frontier_status", "module_loc_treemap", "test_density_scatter", "module_composition", "coverage_ratio"}
        self.assertEqual(set(charts.keys()), expected)
        for name, svg in charts.items():
            self.assertIn("<svg", svg, f"Chart {name} is not valid SVG")

    def test_chart_save_all_creates_files(self):
        """save_all creates SVG files in output directory."""
        from report_charts import ReportChartGenerator
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportChartGenerator(output_dir=tmpdir)
            data = {
                "modules": [{"name": "Mod", "tests": 50}],
                "intelligence": {"findings_total": 5, "build": 1, "adapt": 1, "reference": 1, "reference_personal": 1, "skip": 1, "other": 0},
                "master_tasks_complete": [], "master_tasks_active": [], "master_tasks_pending": [{"id": "MT-1"}],
                "summary": {"source_loc": 1000, "test_loc": 800},
                "frontiers": [{"name": "F1", "tests": 100}],
            }
            paths = gen.save_all(data)
            self.assertEqual(len(paths), 10)
            for name, path in paths.items():
                self.assertTrue(os.path.exists(path))
                with open(path) as f:
                    content = f.read()
                self.assertIn("<svg", content)


if __name__ == "__main__":
    unittest.main()
