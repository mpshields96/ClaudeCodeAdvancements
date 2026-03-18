"""Tests for slide_generator.py — MT-17 Phase 2: Slide templates."""
import json
import os
import sys
import tempfile
import unittest

# Add parent dir to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from slide_generator import SlideDataCollector, SlideGenerator


class TestSlideDataCollector(unittest.TestCase):
    """Test data collection for slide generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.collector = SlideDataCollector(project_root=self.tmpdir)

    def test_collector_creates_with_project_root(self):
        c = SlideDataCollector(project_root="/tmp/test")
        self.assertEqual(c.project_root, "/tmp/test")

    def test_collect_basic_metadata(self):
        data = self.collector.collect_metadata(
            title="CCA Update",
            subtitle="Session 46 Overview",
            author="Matthew Shields",
            session=46,
        )
        self.assertEqual(data["title"], "CCA Update")
        self.assertEqual(data["subtitle"], "Session 46 Overview")
        self.assertEqual(data["author"], "Matthew Shields")
        self.assertEqual(data["session"], 46)
        self.assertIn("date", data)

    def test_collect_metadata_defaults(self):
        data = self.collector.collect_metadata()
        self.assertEqual(data["title"], "ClaudeCodeAdvancements")
        self.assertEqual(data["subtitle"], "Project Update")
        self.assertEqual(data["author"], "")
        self.assertIsNone(data["session"])

    def test_build_summary_slide(self):
        slide = self.collector.build_summary_slide(
            total_tests=1593,
            passing_tests=1593,
            test_suites=39,
            total_modules=9,
            total_findings=283,
        )
        self.assertEqual(slide["type"], "summary")
        self.assertEqual(slide["metrics"]["total_tests"], 1593)
        self.assertEqual(slide["metrics"]["passing_tests"], 1593)
        self.assertEqual(slide["metrics"]["test_suites"], 39)
        self.assertEqual(slide["metrics"]["total_modules"], 9)
        self.assertEqual(slide["metrics"]["total_findings"], 283)

    def test_build_module_slide(self):
        modules = [
            {"name": "Memory System", "status": "COMPLETE", "tests": 94},
            {"name": "Spec System", "status": "COMPLETE", "tests": 90},
        ]
        slide = self.collector.build_module_slide(modules)
        self.assertEqual(slide["type"], "modules")
        self.assertEqual(len(slide["modules"]), 2)
        self.assertEqual(slide["modules"][0]["name"], "Memory System")

    def test_build_bullet_slide(self):
        slide = self.collector.build_bullet_slide(
            title="What's Next",
            bullets=["MT-14 scanning", "MT-17 slides", "Bridge sync"],
        )
        self.assertEqual(slide["type"], "bullets")
        self.assertEqual(slide["title"], "What's Next")
        self.assertEqual(len(slide["bullets"]), 3)

    def test_build_metric_slide(self):
        metrics = [
            {"label": "Tests", "value": "1593", "sublabel": "all passing"},
            {"label": "Modules", "value": "9", "sublabel": "5 frontiers complete"},
            {"label": "Findings", "value": "283", "sublabel": "32% APF"},
        ]
        slide = self.collector.build_metric_slide(
            title="Key Metrics",
            metrics=metrics,
        )
        self.assertEqual(slide["type"], "metrics")
        self.assertEqual(len(slide["metrics"]), 3)
        self.assertEqual(slide["metrics"][0]["label"], "Tests")

    def test_build_section_slide(self):
        slide = self.collector.build_section_slide("Deep Dive: Memory System")
        self.assertEqual(slide["type"], "section")
        self.assertEqual(slide["title"], "Deep Dive: Memory System")

    def test_assemble_deck(self):
        metadata = self.collector.collect_metadata(title="Test Deck")
        slides = [
            self.collector.build_section_slide("Intro"),
            self.collector.build_bullet_slide("Topics", ["A", "B"]),
        ]
        deck = self.collector.assemble_deck(metadata, slides)
        self.assertEqual(deck["title"], "Test Deck")
        self.assertEqual(len(deck["slides"]), 2)
        self.assertEqual(deck["slides"][0]["type"], "section")

    def test_assemble_deck_empty_slides(self):
        metadata = self.collector.collect_metadata()
        deck = self.collector.assemble_deck(metadata, [])
        self.assertEqual(len(deck["slides"]), 0)


class TestSlideGenerator(unittest.TestCase):
    """Test slide generation and Typst compilation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.generator = SlideGenerator()

    def test_generator_finds_template(self):
        template_path = self.generator.template_path
        self.assertTrue(template_path.endswith("cca-slides.typ"))

    def test_write_data_json(self):
        data = {"title": "Test", "slides": []}
        path = os.path.join(self.tmpdir, "data.json")
        self.generator.write_data_json(data, path)
        with open(path) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["title"], "Test")

    def test_write_data_json_serializable(self):
        """All slide data must be JSON-serializable."""
        collector = SlideDataCollector(project_root=self.tmpdir)
        metadata = collector.collect_metadata(title="Serialize Test", session=1)
        slides = [
            collector.build_section_slide("Intro"),
            collector.build_summary_slide(100, 100, 5, 3, 50),
            collector.build_bullet_slide("Items", ["a", "b", "c"]),
            collector.build_metric_slide("KPIs", [
                {"label": "X", "value": "1", "sublabel": "y"},
            ]),
            collector.build_module_slide([
                {"name": "Mod1", "status": "COMPLETE", "tests": 10},
            ]),
        ]
        deck = collector.assemble_deck(metadata, slides)
        # Should not raise
        path = os.path.join(self.tmpdir, "test.json")
        self.generator.write_data_json(deck, path)
        with open(path) as f:
            loaded = json.load(f)
        self.assertEqual(len(loaded["slides"]), 5)

    def test_build_compile_command(self):
        cmd = self.generator.build_compile_command(
            data_path="/tmp/data.json",
            output_path="/tmp/slides.pdf",
        )
        self.assertIn("typst", cmd[0])
        self.assertIn("compile", cmd[1])
        # Should have --root and --input flags
        self.assertIn("--root", cmd)
        self.assertIn("--input", cmd)

    def test_build_compile_command_contains_data_input(self):
        cmd = self.generator.build_compile_command(
            data_path="/tmp/data.json",
            output_path="/tmp/slides.pdf",
        )
        # Find the --input arg
        input_idx = cmd.index("--input")
        input_val = cmd[input_idx + 1]
        self.assertTrue(input_val.startswith("data="))
        self.assertIn("/tmp/data.json", input_val)


class TestSlideTypes(unittest.TestCase):
    """Test that all slide types have correct structure."""

    def setUp(self):
        self.collector = SlideDataCollector(project_root="/tmp")

    def test_summary_slide_required_keys(self):
        slide = self.collector.build_summary_slide(100, 95, 5, 3, 20)
        self.assertIn("type", slide)
        self.assertIn("metrics", slide)
        for key in ["total_tests", "passing_tests", "test_suites",
                     "total_modules", "total_findings"]:
            self.assertIn(key, slide["metrics"])

    def test_bullet_slide_required_keys(self):
        slide = self.collector.build_bullet_slide("Title", ["a"])
        self.assertIn("type", slide)
        self.assertIn("title", slide)
        self.assertIn("bullets", slide)
        self.assertIsInstance(slide["bullets"], list)

    def test_metric_slide_required_keys(self):
        metrics = [{"label": "A", "value": "1", "sublabel": "x"}]
        slide = self.collector.build_metric_slide("KPIs", metrics)
        self.assertIn("type", slide)
        self.assertIn("title", slide)
        self.assertIn("metrics", slide)
        for m in slide["metrics"]:
            self.assertIn("label", m)
            self.assertIn("value", m)
            self.assertIn("sublabel", m)

    def test_section_slide_required_keys(self):
        slide = self.collector.build_section_slide("Section Title")
        self.assertIn("type", slide)
        self.assertIn("title", slide)

    def test_modules_slide_required_keys(self):
        mods = [{"name": "Foo", "status": "OK", "tests": 10}]
        slide = self.collector.build_module_slide(mods)
        self.assertIn("type", slide)
        self.assertIn("modules", slide)
        for m in slide["modules"]:
            self.assertIn("name", m)
            self.assertIn("status", m)
            self.assertIn("tests", m)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_bullets(self):
        c = SlideDataCollector(project_root="/tmp")
        slide = c.build_bullet_slide("Empty", [])
        self.assertEqual(slide["bullets"], [])

    def test_many_modules(self):
        c = SlideDataCollector(project_root="/tmp")
        mods = [{"name": f"Mod{i}", "status": "OK", "tests": i}
                for i in range(20)]
        slide = c.build_module_slide(mods)
        self.assertEqual(len(slide["modules"]), 20)

    def test_long_bullet_text(self):
        c = SlideDataCollector(project_root="/tmp")
        long_text = "A" * 500
        slide = c.build_bullet_slide("Long", [long_text])
        self.assertEqual(slide["bullets"][0], long_text)

    def test_metric_with_special_chars(self):
        c = SlideDataCollector(project_root="/tmp")
        metrics = [{"label": "Rate (%)", "value": "32.1%", "sublabel": "> target"}]
        slide = c.build_metric_slide("Special", metrics)
        self.assertEqual(slide["metrics"][0]["value"], "32.1%")

    def test_generator_template_path_exists(self):
        g = SlideGenerator()
        # Template may not exist yet (TDD — we create it after)
        # Just verify it points to the right location
        self.assertTrue(g.template_path.endswith("cca-slides.typ"))


if __name__ == "__main__":
    unittest.main()
