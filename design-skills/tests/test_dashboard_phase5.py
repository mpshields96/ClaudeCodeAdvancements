#!/usr/bin/env python3
"""
test_dashboard_phase5.py — Tests for MT-32 Phase 5 dashboard enhancements.

Covers: responsive tablet layout, auto-refresh, keyboard shortcuts,
print styles, embedded JSON data export, accessibility improvements.
"""

import json
import os
import re
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
    cli_main,
)


def _sample_data() -> DashboardData:
    """Build sample dashboard data for Phase 5 tests."""
    data = DashboardData(title="Phase 5 Test Dashboard", session_number=165)
    data.metrics = [
        MetricCard(label="Tests", value="9239", status="success"),
        MetricCard(label="Suites", value="234", status="info"),
        MetricCard(label="Modules", value="9", status="info"),
    ]
    data.modules = [
        ModuleCard(name="Memory System", path="memory-system/", status="COMPLETE", tests=340, items="MEM-1-5"),
        ModuleCard(name="Agent Guard", path="agent-guard/", status="ACTIVE", tests=1073, items="AG-1-9"),
        ModuleCard(name="Self-Learning", path="self-learning/", status="ACTIVE", tests=1885, items="MT-7,10"),
    ]
    data.master_tasks = [
        MasterTaskRow(id="MT-32", name="Visual Excellence", score=10.0, status="Phase 5"),
        MasterTaskRow(id="MT-33", name="Reporting Suite", score=8.0, status="Phase 4"),
    ]
    return data


class TestResponsiveTablet(unittest.TestCase):
    """Dashboard must have a tablet breakpoint (768px)."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_tablet_breakpoint_exists(self):
        """CSS must include a media query for ~768px (tablet)."""
        self.assertRegex(self.html, r"@media\s*\(max-width:\s*768px\)")

    def test_tablet_metrics_grid(self):
        """Metrics grid should adjust at tablet width."""
        # Should have a grid-template-columns rule inside the 768px query
        tablet_match = re.search(
            r"@media\s*\(max-width:\s*768px\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}",
            self.html, re.DOTALL,
        )
        self.assertIsNotNone(tablet_match)
        tablet_css = tablet_match.group(1)
        self.assertIn(".metrics", tablet_css)

    def test_mobile_breakpoint_still_exists(self):
        """Original 600px mobile breakpoint must still be present."""
        self.assertRegex(self.html, r"@media\s*\(max-width:\s*600px\)")

    def test_header_stacks_on_mobile(self):
        """Header flex should stack on small screens."""
        # The 600px or 768px query should affect the header layout
        self.assertIn("flex-direction", self.html)


class TestAutoRefresh(unittest.TestCase):
    """Dashboard must support auto-refresh via meta tag."""

    def setUp(self):
        self.renderer = DashboardRenderer()

    def test_no_refresh_by_default(self):
        """Without refresh_seconds, no meta refresh tag."""
        html = self.renderer.render(_sample_data())
        self.assertNotIn('http-equiv="refresh"', html)

    def test_refresh_meta_tag_present(self):
        """With refresh_seconds, meta refresh tag should appear."""
        html = self.renderer.render(_sample_data(), refresh_seconds=30)
        self.assertIn('http-equiv="refresh"', html)
        self.assertIn('content="30"', html)

    def test_refresh_zero_means_no_refresh(self):
        """refresh_seconds=0 should not add meta tag."""
        html = self.renderer.render(_sample_data(), refresh_seconds=0)
        self.assertNotIn('http-equiv="refresh"', html)

    def test_refresh_negative_means_no_refresh(self):
        """Negative refresh_seconds should not add meta tag."""
        html = self.renderer.render(_sample_data(), refresh_seconds=-5)
        self.assertNotIn('http-equiv="refresh"', html)

    def test_cli_refresh_flag(self):
        """CLI must accept --refresh N flag."""
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            cli_main(["generate", "--output", path, "--demo", "--refresh", "60"])
            with open(path) as f:
                html = f.read()
            self.assertIn('http-equiv="refresh"', html)
            self.assertIn('content="60"', html)
        finally:
            os.unlink(path)

    def test_refresh_timestamp_displayed(self):
        """When auto-refresh is on, show last-updated timestamp."""
        html = self.renderer.render(_sample_data(), refresh_seconds=30)
        self.assertIn("auto-refresh", html.lower())


class TestKeyboardShortcuts(unittest.TestCase):
    """Dashboard must support keyboard navigation."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_keyboard_event_listener(self):
        """JS must have a keydown or keyup event listener."""
        self.assertTrue(
            "addEventListener" in self.html and "key" in self.html.lower(),
            "Must have keyboard event listener",
        )

    def test_escape_clears_search(self):
        """Pressing Escape should clear the module search."""
        self.assertIn("Escape", self.html)

    def test_slash_focuses_search(self):
        """Pressing / should focus the module search input."""
        # The JS should reference the slash key
        self.assertIn("module-search", self.html)
        # Should focus on / key
        self.assertTrue(
            "'/' " in self.html or '"/"' in self.html or "Slash" in self.html,
            "JS must handle / key for search focus",
        )


class TestPrintStyles(unittest.TestCase):
    """Dashboard must have print-friendly styles."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_print_media_query(self):
        """CSS must include @media print."""
        self.assertIn("@media print", self.html)

    def test_print_hides_interactive_elements(self):
        """Print should hide the theme toggle and search input."""
        # The print CSS should hide interactive elements
        print_match = re.search(
            r"@media\s+print\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}",
            self.html, re.DOTALL,
        )
        self.assertIsNotNone(print_match, "Must have @media print block")
        print_css = print_match.group(1)
        self.assertIn("display:none", print_css.replace(" ", "").replace(": ", ":"))


class TestEmbeddedDataExport(unittest.TestCase):
    """Dashboard must embed JSON data for programmatic access."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.data = _sample_data()
        self.html = self.renderer.render(self.data)

    def test_json_data_embedded(self):
        """Dashboard HTML must contain embedded JSON data."""
        self.assertIn('id="dashboard-data"', self.html)

    def test_embedded_json_is_valid(self):
        """Embedded JSON must be parseable."""
        match = re.search(
            r'<script[^>]*id="dashboard-data"[^>]*type="application/json"[^>]*>(.*?)</script>',
            self.html, re.DOTALL,
        )
        self.assertIsNotNone(match, "Must have JSON script tag")
        parsed = json.loads(match.group(1))
        self.assertIsInstance(parsed, dict)

    def test_embedded_json_has_modules(self):
        """Embedded JSON must include module data."""
        match = re.search(
            r'<script[^>]*id="dashboard-data"[^>]*type="application/json"[^>]*>(.*?)</script>',
            self.html, re.DOTALL,
        )
        parsed = json.loads(match.group(1))
        self.assertIn("modules", parsed)
        self.assertEqual(len(parsed["modules"]), 3)

    def test_embedded_json_has_metrics(self):
        """Embedded JSON must include metric data."""
        match = re.search(
            r'<script[^>]*id="dashboard-data"[^>]*type="application/json"[^>]*>(.*?)</script>',
            self.html, re.DOTALL,
        )
        parsed = json.loads(match.group(1))
        self.assertIn("metrics", parsed)

    def test_embedded_json_has_session_number(self):
        """Embedded JSON must include session number."""
        match = re.search(
            r'<script[^>]*id="dashboard-data"[^>]*type="application/json"[^>]*>(.*?)</script>',
            self.html, re.DOTALL,
        )
        parsed = json.loads(match.group(1))
        self.assertEqual(parsed["session_number"], 165)


class TestAccessibility(unittest.TestCase):
    """Dashboard must have basic accessibility attributes."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_aria_labels_on_interactive(self):
        """Theme toggle must have aria-label."""
        self.assertIn("aria-label", self.html)

    def test_role_on_search(self):
        """Search input must have appropriate role or label."""
        # Either aria-label or a <label> element
        self.assertTrue(
            'aria-label' in self.html or '<label' in self.html,
            "Search must be labeled for accessibility",
        )

    def test_table_has_scope(self):
        """Table headers should have scope attribute."""
        self.assertIn('scope="col"', self.html)

    def test_skip_to_content_or_landmark(self):
        """Dashboard should have a main landmark role."""
        self.assertIn('role="main"', self.html)


class TestPhase5Integration(unittest.TestCase):
    """Integration: all Phase 5 features work together."""

    def test_full_render_with_all_features(self):
        """Render with refresh + dark theme should include all Phase 5 features."""
        renderer = DashboardRenderer()
        html = renderer.render(_sample_data(), theme="dark", refresh_seconds=45)
        # Dark theme
        self.assertIn('data-theme="dark"', html)
        # Auto-refresh
        self.assertIn('content="45"', html)
        # Keyboard shortcuts
        self.assertIn("Escape", html)
        # Print styles
        self.assertIn("@media print", html)
        # Embedded data
        self.assertIn('id="dashboard-data"', html)
        # Responsive
        self.assertRegex(html, r"@media\s*\(max-width:\s*768px\)")
        # Accessibility
        self.assertIn("aria-label", html)

    def test_file_output_with_refresh(self):
        """render_to_file with refresh_seconds should work."""
        renderer = DashboardRenderer()
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            renderer.render_to_file(_sample_data(), path, theme="light", refresh_seconds=30)
            with open(path) as f:
                html = f.read()
            self.assertIn('http-equiv="refresh"', html)
        finally:
            os.unlink(path)

    def test_empty_data_with_all_features(self):
        """Phase 5 features must not crash with empty data."""
        renderer = DashboardRenderer()
        html = renderer.render(DashboardData(), refresh_seconds=60)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("@media print", html)
        self.assertIn('id="dashboard-data"', html)


if __name__ == "__main__":
    unittest.main()
