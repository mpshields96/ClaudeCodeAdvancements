#!/usr/bin/env python3
"""
test_dashboard_component_integration.py — MT-32 Phase 5.

Tests that dashboard_generator.py uses component_library components:
- stat_card() for metrics
- badge() for module status
- component_stylesheet() CSS included in output
- component_library importable from dashboard_generator context
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard_generator import (
    DashboardRenderer,
    DashboardData,
    ModuleCard,
    MasterTaskRow,
    MetricCard,
)


def _sample_data() -> DashboardData:
    data = DashboardData(title="Component Integration Test", session_number=257)
    data.metrics = [
        MetricCard(label="Tests", value="12490", status="success"),
        MetricCard(label="Suites", value="351", status="info"),
    ]
    data.modules = [
        ModuleCard(name="Memory System", path="memory-system/", status="COMPLETE", tests=340, items="MEM-1-5"),
        ModuleCard(name="Agent Guard", path="agent-guard/", status="ACTIVE", tests=1073, items="AG-1-9"),
        ModuleCard(name="Self-Learning", path="self-learning/", status="FAILING", tests=0, items="—"),
    ]
    data.master_tasks = [
        MasterTaskRow(id="MT-32", name="Visual Excellence", score=8.0, status="Phase 5"),
        MasterTaskRow(id="MT-49", name="Self-Learning UBER", score=21.0, status="Phase 1"),
    ]
    return data


class TestStatCardIntegration(unittest.TestCase):
    """Metrics section must use stat_card() from component_library."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_stat_card_class_in_metrics(self):
        """Rendered HTML must contain cca-stat-card class (from stat_card())."""
        self.assertIn("cca-stat-card", self.html)

    def test_each_metric_renders_component_stat_card(self):
        """Each metric wrapper should contain a component-library stat card."""
        matches = re.findall(
            r'<div class="metric-card">\s*<div class="cca-stat-card">',
            self.html,
        )
        self.assertEqual(len(matches), 2)

    def test_stat_label_present(self):
        """Metric labels must appear inside stat-card elements."""
        self.assertIn("cca-stat-label", self.html)

    def test_stat_value_present(self):
        """Metric values must appear inside stat-card elements."""
        self.assertIn("cca-stat-value", self.html)

    def test_metric_values_visible(self):
        """All metric values must appear in rendered output."""
        self.assertIn("12490", self.html)
        self.assertIn("351", self.html)

    def test_metric_labels_visible(self):
        """All metric labels must appear in rendered output."""
        self.assertIn("Tests", self.html)
        self.assertIn("Suites", self.html)


class TestBadgeIntegration(unittest.TestCase):
    """Module status must use badge() from component_library."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_badge_class_in_modules(self):
        """Module cards must use cca-badge class for status."""
        self.assertIn("cca-badge", self.html)

    def test_each_module_renders_component_badge(self):
        """Each module card should contain a component-library badge."""
        matches = re.findall(
            r'<div class="module-card"[^>]*>.*?<span class="cca-badge',
            self.html,
            re.DOTALL,
        )
        self.assertEqual(len(matches), 3)

    def test_complete_status_badge(self):
        """COMPLETE modules must have a badge."""
        # COMPLETE should appear as a badge somewhere near the module
        self.assertIn("COMPLETE", self.html)

    def test_active_status_badge(self):
        """ACTIVE modules must have a badge."""
        self.assertIn("ACTIVE", self.html)

    def test_failing_status_badge(self):
        """FAILING modules must have a badge."""
        self.assertIn("FAILING", self.html)


class TestComponentStylesheetIntegration(unittest.TestCase):
    """component_stylesheet() CSS must be included in rendered output."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_cca_btn_class_in_css(self):
        """component_stylesheet .cca-btn CSS must be present."""
        self.assertIn(".cca-btn", self.html)

    def test_cca_stat_card_css(self):
        """component_stylesheet .cca-stat-card CSS must be present."""
        self.assertIn(".cca-stat-card", self.html)

    def test_cca_badge_css(self):
        """component_stylesheet .cca-badge CSS must be present."""
        self.assertIn(".cca-badge", self.html)

    def test_component_css_in_style_tag(self):
        """Component CSS must appear inside a <style> tag."""
        style_match = re.search(r"<style>(.*?)</style>", self.html, re.DOTALL)
        self.assertIsNotNone(style_match, "Expected <style> block in output")
        style_content = style_match.group(1)
        self.assertIn(".cca-stat-card", style_content)


class TestBackwardsCompatibility(unittest.TestCase):
    """Existing dashboard features must still work after component_library wiring."""

    def setUp(self):
        self.renderer = DashboardRenderer()
        self.html = self.renderer.render(_sample_data())

    def test_theme_toggle_still_present(self):
        self.assertIn('id="theme-toggle"', self.html)

    def test_dark_theme_css_still_present(self):
        self.assertIn("data-theme", self.html)
        self.assertIn("dark", self.html)

    def test_sortable_table_still_present(self):
        self.assertIn("sortable", self.html)

    def test_module_search_still_present(self):
        self.assertIn('id="module-search"', self.html)

    def test_data_name_on_module_cards(self):
        self.assertIn("data-name=", self.html)

    def test_collapsible_sections_still_present(self):
        self.assertIn("collapsible", self.html)

    def test_valid_html_structure(self):
        self.assertIn("<!DOCTYPE html>", self.html)
        self.assertIn("</html>", self.html)

    def test_module_names_visible(self):
        self.assertIn("Memory System", self.html)
        self.assertIn("Agent Guard", self.html)

    def test_task_ids_visible(self):
        self.assertIn("MT-32", self.html)
        self.assertIn("MT-49", self.html)

    def test_xss_safety(self):
        data = _sample_data()
        data.title = "<script>alert(1)</script>"
        html = self.renderer.render(data)
        self.assertNotIn("<script>alert(1)</script>", html)


if __name__ == "__main__":
    unittest.main()
