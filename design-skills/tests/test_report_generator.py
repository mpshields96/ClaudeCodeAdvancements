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

    def test_collect_test_counts(self):
        """Collects test suite counts from test runner output."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        # Mock test output
        output = "Ran 50 tests in 0.5s\nOK\nRan 30 tests in 0.2s\nOK"
        total, passing = collector.parse_test_output(output)
        self.assertEqual(total, 80)
        self.assertEqual(passing, 80)

    def test_collect_test_counts_with_failures(self):
        """Handles test output with failures."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        output = "Ran 50 tests in 0.5s\nOK\nRan 30 tests in 0.2s\nFAILED (failures=2)"
        total, passing = collector.parse_test_output(output)
        self.assertEqual(total, 80)
        self.assertEqual(passing, 78)

    def test_collect_test_counts_empty_output(self):
        """Handles empty test output gracefully."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        total, passing = collector.parse_test_output("")
        self.assertEqual(total, 0)
        self.assertEqual(passing, 0)

    def test_parse_module_status(self):
        """Parses PROJECT_INDEX.md for module status."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        index_content = """| Memory System | `memory-system/` | MEM-1-5 COMPLETE | 94 |
| Spec System | `spec-system/` | SPEC-1-6 COMPLETE | 90 |
| Agent Guard | `agent-guard/` | AG-1-7 COMPLETE | 264 |"""
        modules = collector.parse_module_table(index_content)
        self.assertEqual(len(modules), 3)
        self.assertEqual(modules[0]["name"], "Memory System")
        self.assertEqual(modules[0]["status"], "COMPLETE")
        self.assertEqual(modules[0]["tests"], 94)

    def test_parse_module_status_active(self):
        """Correctly identifies ACTIVE vs COMPLETE modules."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        index_content = """| Reddit Intelligence | `reddit-intelligence/` | MT-6,9,11,14,15 | 263 |"""
        modules = collector.parse_module_table(index_content)
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0]["status"], "ACTIVE")

    def test_parse_master_tasks(self):
        """Parses MASTER_TASKS.md for task status."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        content = """## MT-0: Kalshi Bot Self-Learning Integration (BIGGEST)
**Status:** Phase 1 COMPLETE (Session 21).

## MT-2: Mermaid Architecture Diagrams in Spec System
**Status:** COMPLETE (Session 19).

## MT-17: UI/Design Excellence and Professional Report Generation
**Status:** Not started."""
        tasks = collector.parse_master_tasks(content)
        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0]["id"], "MT-0")
        self.assertEqual(tasks[0]["name"], "Kalshi Bot Self-Learning Integration")
        self.assertEqual(tasks[0]["status"], "Phase 1 COMPLETE (Session 21).")
        self.assertEqual(tasks[1]["status"], "COMPLETE (Session 19).")

    def test_count_findings(self):
        """Counts entries in FINDINGS_LOG.md."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        content = """[2026-03-17] [REFERENCE] something
[2026-03-17] [BUILD] something else
[2026-03-18] [SKIP] another thing"""
        count = collector.count_findings(content)
        self.assertEqual(count, 3)

    def test_count_papers(self):
        """Counts papers in papers.jsonl."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        lines = ['{"title": "Paper 1"}\n', '{"title": "Paper 2"}\n', '{"title": "Paper 3"}\n']
        count = collector.count_papers(lines)
        self.assertEqual(count, 3)

    def test_build_report_data(self):
        """build_report_data returns correct structure."""
        from report_generator import CCADataCollector
        collector = CCADataCollector(project_root="/tmp/fake")
        data = collector.build_report_data(
            session=41,
            date="2026-03-18",
            total_tests=1525,
            passing_tests=1525,
            test_suites=37,
            modules=[{"name": "Test", "path": "test/", "status": "COMPLETE", "tests": 10, "items": "T-1"}],
            master_tasks=[{"id": "MT-0", "name": "Test Task", "status": "COMPLETE"}],
            findings_count=215,
            papers_count=21,
            next_priorities=["Do something"],
        )
        self.assertEqual(data["title"], "ClaudeCodeAdvancements")
        self.assertEqual(data["session"], 41)
        self.assertEqual(data["summary"]["total_tests"], 1525)
        self.assertEqual(len(data["modules"]), 1)
        self.assertEqual(data["summary"]["master_tasks"], 1)


class TestReportRenderer(unittest.TestCase):
    """Tests for ReportRenderer — calls Typst to generate PDF."""

    def test_render_returns_path(self):
        """render() returns the output PDF path."""
        from report_generator import ReportRenderer
        renderer = ReportRenderer()
        # Mock subprocess
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

    def test_full_pipeline_with_sample_data(self):
        """Full pipeline: sample data -> JSON -> Typst -> PDF."""
        from report_generator import CCADataCollector, ReportRenderer
        collector = CCADataCollector(project_root="/tmp/fake")
        data = collector.build_report_data(
            session=41,
            date="2026-03-18",
            total_tests=1525,
            passing_tests=1525,
            test_suites=37,
            modules=[
                {"name": "Memory System", "path": "memory-system/", "status": "COMPLETE", "tests": 94, "items": "MEM-1-5"},
            ],
            master_tasks=[
                {"id": "MT-0", "name": "Self-Learning", "status": "COMPLETE"},
            ],
            findings_count=215,
            papers_count=21,
            next_priorities=["Build MT-17"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "data.json")
            with open(data_path, "w") as f:
                json.dump(data, f)

            output_path = os.path.join(tmpdir, "report.pdf")
            renderer = ReportRenderer()
            result = renderer.render("cca-report", data_path, output_path)
            self.assertTrue(os.path.exists(result))
            self.assertGreater(os.path.getsize(result), 1000)  # Should be a real PDF

    def test_sample_template_compiles(self):
        """cca-report.typ compiles with embedded sample data."""
        from report_generator import ReportRenderer
        renderer = ReportRenderer()
        template_file = renderer.template_path("cca-report")
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "test.pdf")
            import subprocess
            result = subprocess.run(
                ["typst", "compile", template_file, output],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, f"Typst error: {result.stderr}")
            self.assertTrue(os.path.exists(output))


if __name__ == "__main__":
    unittest.main()
