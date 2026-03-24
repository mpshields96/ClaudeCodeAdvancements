#!/usr/bin/env python3
"""
test_dashboard_v2.py — Tests for Dashboard v2 interactive features.

Covers: dark mode toggle, sortable tables, module search filter,
collapsible sections, theme CLI flag, CSS custom properties.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_generator import (
    DashboardRenderer,
    DashboardData,
    ModuleCard,
    MasterTaskRow,
    MetricCard,
    _e,
    cli_main,
)


def _sample_data() -> DashboardData:
    """Build a full sample dashboard for v2 tests."""
    data = DashboardData(title="Test Dashboard v2", session_number=148)
    data.metrics = [
        MetricCard(label="Tests", value="8733", status="success"),
        MetricCard(label="Modules", value="9", status="info"),
    ]
    data.modules = [
        ModuleCard(name="Memory System", path="memory-system/", status="COMPLETE", tests=340, items="MEM-1-5"),
        ModuleCard(name="Agent Guard", path="agent-guard/", status="ACTIVE", tests=1073, items="AG-1-9"),
        ModuleCard(name="Self-Learning", path="self-learning/", status="ACTIVE", tests=1885, items="MT-7,10"),
        ModuleCard(name="Context Monitor", path="context-monitor/", status="COMPLETE", tests=411, items="CTX-1-7"),
    ]
    data.master_tasks = [
        MasterTaskRow(id="MT-32", name="Visual Excellence", score=10.0, status="Phase 5"),
        MasterTaskRow(id="MT-22", name="Desktop Electron", score=2.0, status="Phase 4"),
        MasterTaskRow(id="MT-36", name="Session Efficiency", score=1.0, status="Phase 4"),
    ]
    return data


class TestDarkModeToggle(unittest.TestCase):
    """Dashboard v2 must include a dark mode toggle."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_theme_toggle_button_present(self):
        """HTML output must include a theme toggle button."""
        self.assertIn('id="theme-toggle"', self.html)

    def test_css_custom_properties_defined(self):
        """CSS must use custom properties (--var) for theming."""
        self.assertIn("--bg-primary", self.html)
        self.assertIn("--text-primary", self.html)
        self.assertIn("--surface", self.html)

    def test_dark_theme_class_in_css(self):
        """CSS must define [data-theme='dark'] overrides."""
        self.assertIn("data-theme", self.html)
        self.assertIn("dark", self.html)

    def test_toggle_js_present(self):
        """JavaScript for toggling theme must be present."""
        self.assertIn("toggleTheme", self.html)

    def test_theme_persistence_localstorage(self):
        """JS must save theme preference to localStorage."""
        self.assertIn("localStorage", self.html)


class TestSortableTable(unittest.TestCase):
    """Task table must be sortable by clicking column headers."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_sortable_class_on_table(self):
        """Task table must have sortable class."""
        self.assertIn("sortable", self.html)

    def test_sort_js_function_present(self):
        """JavaScript sortTable function must exist."""
        self.assertIn("sortTable", self.html)

    def test_th_onclick_or_cursor(self):
        """Table headers must be clickable (cursor pointer or onclick)."""
        self.assertIn("cursor:pointer", self.html.replace(" ", ""))

    def test_sort_indicators_in_headers(self):
        """Column headers must have sort indicator spans."""
        self.assertIn("sort-indicator", self.html)


class TestModuleSearch(unittest.TestCase):
    """Module grid must have a search/filter input."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_search_input_present(self):
        """A search input for filtering modules must exist."""
        self.assertIn('id="module-search"', self.html)

    def test_filter_js_present(self):
        """JavaScript filterModules function must exist."""
        self.assertIn("filterModules", self.html)

    def test_search_placeholder(self):
        """Search input must have a placeholder."""
        self.assertIn("placeholder=", self.html)
        # Should mention filtering or searching
        lower = self.html.lower()
        self.assertTrue("filter" in lower or "search" in lower)

    def test_module_cards_have_data_name(self):
        """Each module card must have data-name attribute for JS filtering."""
        self.assertIn("data-name=", self.html)


class TestCollapsibleSections(unittest.TestCase):
    """Section headers must be collapsible."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_collapsible_class_present(self):
        """Section headers must have collapsible class or role."""
        self.assertIn("collapsible", self.html)

    def test_toggle_section_js(self):
        """JavaScript for toggling sections must exist."""
        self.assertIn("toggleSection", self.html)

    def test_chevron_indicator(self):
        """Collapsible headers must have a visual indicator (chevron)."""
        # Could be an SVG, unicode char, or CSS ::after
        self.assertIn("chevron", self.html.lower())


class TestThemeCLIFlag(unittest.TestCase):
    """CLI must accept --theme light|dark flag."""

    def test_cli_theme_flag_dark(self):
        """--theme dark should set initial theme."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            cli_main(["generate", "--output", path, "--demo", "--theme", "dark"])
            with open(path) as f:
                html = f.read()
            self.assertIn("data-theme=\"dark\"", html)
        finally:
            os.unlink(path)

    def test_cli_theme_flag_light(self):
        """--theme light should set initial theme (or default)."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            cli_main(["generate", "--output", path, "--demo", "--theme", "light"])
            with open(path) as f:
                html = f.read()
            # The <html> tag should have data-theme="light", not dark
            self.assertIn('<html lang="en" data-theme="light">', html)
        finally:
            os.unlink(path)

    def test_cli_no_theme_defaults_light(self):
        """No --theme flag defaults to light theme."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            cli_main(["generate", "--output", path, "--demo"])
            with open(path) as f:
                html = f.read()
            # Default is light
            self.assertIn('<html lang="en" data-theme="light">', html)
        finally:
            os.unlink(path)


class TestV2Rendering(unittest.TestCase):
    """General v2 rendering integrity."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.data = _sample_data()

    def test_render_still_produces_valid_html(self):
        """v2 changes must not break basic HTML structure."""
        html = self.renderer.render(self.data)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)
        self.assertIn("<body", html)
        self.assertIn("</body>", html)

    def test_render_includes_all_modules(self):
        """All module names must appear in output."""
        html = self.renderer.render(self.data)
        for m in self.data.modules:
            self.assertIn(m.name, html)

    def test_render_includes_all_tasks(self):
        """All task IDs must appear in output."""
        html = self.renderer.render(self.data)
        for t in self.data.master_tasks:
            self.assertIn(t.id, html)

    def test_render_with_empty_data(self):
        """v2 features must not crash with empty data."""
        html = self.renderer.render(DashboardData())
        self.assertIn("<!DOCTYPE html>", html)
        # Theme toggle should still be there
        self.assertIn('id="theme-toggle"', html)

    def test_render_xss_safety_preserved(self):
        """XSS escaping still works in v2."""
        data = DashboardData(title='<script>alert("xss")</script>')
        html = self.renderer.render(data)
        self.assertNotIn('<script>alert("xss")</script>', html)
        self.assertIn("&lt;script&gt;", html)

    def test_render_with_theme_param(self):
        """Renderer must accept theme parameter."""
        html = self.renderer.render(self.data, theme="dark")
        self.assertIn("data-theme=\"dark\"", html)

    def test_render_default_theme_light(self):
        """Default render produces light theme."""
        html = self.renderer.render(self.data)
        self.assertIn("data-theme=\"light\"", html)

    def test_script_tag_present(self):
        """v2 must include a <script> tag for interactivity."""
        html = self.renderer.render(self.data)
        self.assertIn("<script>", html)
        self.assertIn("</script>", html)


class TestV2FileOutput(unittest.TestCase):
    """File output with v2 features."""

    def test_render_to_file_with_theme(self):
        """render_to_file should pass theme through."""
        renderer = DashboardRenderer()
        data = _sample_data()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            renderer.render_to_file(data, path, theme="dark")
            with open(path) as f:
                html = f.read()
            self.assertIn("data-theme=\"dark\"", html)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
