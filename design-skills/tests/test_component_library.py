"""Tests for design-skills/component_library.py — MT-32 Phase 4.

UI component library: reusable HTML components backed by CCA design tokens.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import component_library as cl


class TestButton(unittest.TestCase):
    def test_primary_contains_label(self):
        html = cl.button("Submit")
        self.assertIn("Submit", html)

    def test_returns_button_tag(self):
        html = cl.button("OK")
        self.assertIn("<button", html)

    def test_primary_variant_class(self):
        html = cl.button("X", variant="primary")
        self.assertIn("cca-btn-primary", html)

    def test_secondary_variant_class(self):
        html = cl.button("X", variant="secondary")
        self.assertIn("cca-btn-secondary", html)

    def test_danger_variant_class(self):
        html = cl.button("Delete", variant="danger")
        self.assertIn("cca-btn-danger", html)

    def test_ghost_variant_class(self):
        html = cl.button("Cancel", variant="ghost")
        self.assertIn("cca-btn-ghost", html)

    def test_size_sm(self):
        html = cl.button("X", size="sm")
        self.assertIn("cca-btn-sm", html)

    def test_size_lg(self):
        html = cl.button("X", size="lg")
        self.assertIn("cca-btn-lg", html)

    def test_href_produces_anchor(self):
        html = cl.button("Go", href="https://example.com")
        self.assertIn("<a ", html)
        self.assertIn("https://example.com", html)

    def test_disabled_attribute(self):
        html = cl.button("X", disabled=True)
        self.assertIn("disabled", html)

    def test_default_type_submit_not_button(self):
        # Default variant is primary, should have type="button" by default
        html = cl.button("Click")
        self.assertIn('type="button"', html)

    def test_invalid_variant_falls_back(self):
        html = cl.button("X", variant="nonexistent")
        self.assertIn("cca-btn-", html)


class TestBadge(unittest.TestCase):
    def test_contains_text(self):
        html = cl.badge("NEW")
        self.assertIn("NEW", html)

    def test_default_variant(self):
        html = cl.badge("tag")
        self.assertIn("cca-badge", html)

    def test_success_variant(self):
        html = cl.badge("OK", variant="success")
        self.assertIn("cca-badge-success", html)

    def test_warning_variant(self):
        html = cl.badge("WARN", variant="warning")
        self.assertIn("cca-badge-warning", html)

    def test_danger_variant(self):
        html = cl.badge("ERR", variant="danger")
        self.assertIn("cca-badge-danger", html)

    def test_neutral_variant(self):
        html = cl.badge("info", variant="neutral")
        self.assertIn("cca-badge-neutral", html)


class TestAlert(unittest.TestCase):
    def test_contains_message(self):
        html = cl.alert("Something happened")
        self.assertIn("Something happened", html)

    def test_info_variant(self):
        html = cl.alert("msg", variant="info")
        self.assertIn("cca-alert-info", html)

    def test_success_variant(self):
        html = cl.alert("msg", variant="success")
        self.assertIn("cca-alert-success", html)

    def test_warning_variant(self):
        html = cl.alert("msg", variant="warning")
        self.assertIn("cca-alert-warning", html)

    def test_danger_variant(self):
        html = cl.alert("msg", variant="danger")
        self.assertIn("cca-alert-danger", html)

    def test_title_included(self):
        html = cl.alert("body text", title="Heads up")
        self.assertIn("Heads up", html)
        self.assertIn("body text", html)

    def test_no_title_still_renders(self):
        html = cl.alert("msg")
        self.assertIn("msg", html)

    def test_dismissible_flag(self):
        html = cl.alert("msg", dismissible=True)
        self.assertIn("cca-alert-dismiss", html)


class TestCard(unittest.TestCase):
    def test_title_in_output(self):
        html = cl.card("My Card", "body text")
        self.assertIn("My Card", html)

    def test_body_in_output(self):
        html = cl.card("T", "content here")
        self.assertIn("content here", html)

    def test_footer_when_given(self):
        html = cl.card("T", "body", footer="footer text")
        self.assertIn("footer text", html)

    def test_no_footer_by_default(self):
        html = cl.card("T", "body")
        self.assertNotIn("cca-card-footer", html)

    def test_elevated_variant(self):
        html = cl.card("T", "body", variant="elevated")
        self.assertIn("cca-card-elevated", html)

    def test_outlined_variant(self):
        html = cl.card("T", "body", variant="outlined")
        self.assertIn("cca-card-outlined", html)

    def test_default_variant(self):
        html = cl.card("T", "body")
        self.assertIn("cca-card", html)

    def test_html_body_rendered_raw(self):
        html = cl.card("T", "<p>raw</p>")
        self.assertIn("<p>raw</p>", html)


class TestProgressBar(unittest.TestCase):
    def test_contains_percentage(self):
        html = cl.progress_bar(75, 100)
        self.assertIn("75", html)

    def test_zero_value(self):
        html = cl.progress_bar(0, 100)
        self.assertIn("0", html)

    def test_max_value(self):
        html = cl.progress_bar(100, 100)
        self.assertIn("100", html)

    def test_label_included(self):
        html = cl.progress_bar(50, 100, label="Loading")
        self.assertIn("Loading", html)

    def test_success_variant(self):
        html = cl.progress_bar(80, 100, variant="success")
        self.assertIn("cca-progress-success", html)

    def test_warning_variant(self):
        html = cl.progress_bar(50, 100, variant="warning")
        self.assertIn("cca-progress-warning", html)

    def test_danger_variant(self):
        html = cl.progress_bar(10, 100, variant="danger")
        self.assertIn("cca-progress-danger", html)

    def test_width_style_set(self):
        html = cl.progress_bar(40, 100)
        self.assertIn("40%", html)

    def test_clamped_over_max(self):
        html = cl.progress_bar(200, 100)
        self.assertIn("100%", html)

    def test_clamped_below_zero(self):
        html = cl.progress_bar(-5, 100)
        self.assertIn("0%", html)


class TestDataTable(unittest.TestCase):
    def test_headers_rendered(self):
        html = cl.data_table(["Name", "Score"], [["Alice", "99"]])
        self.assertIn("Name", html)
        self.assertIn("Score", html)

    def test_rows_rendered(self):
        html = cl.data_table(["A"], [["row1"], ["row2"]])
        self.assertIn("row1", html)
        self.assertIn("row2", html)

    def test_table_tag_present(self):
        html = cl.data_table(["H"], [["v"]])
        self.assertIn("<table", html)

    def test_empty_rows_renders(self):
        html = cl.data_table(["H"], [])
        self.assertIn("cca-table-empty", html)

    def test_caption_when_given(self):
        html = cl.data_table(["H"], [["v"]], caption="My Table")
        self.assertIn("My Table", html)
        self.assertIn("<caption", html)

    def test_striped_class(self):
        html = cl.data_table(["H"], [["v"]], striped=True)
        self.assertIn("cca-table-striped", html)

    def test_compact_class(self):
        html = cl.data_table(["H"], [["v"]], compact=True)
        self.assertIn("cca-table-compact", html)

    def test_header_count_matches(self):
        html = cl.data_table(["A", "B", "C"], [["1", "2", "3"]])
        self.assertEqual(html.count("<th>"), 3)


class TestTabs(unittest.TestCase):
    def test_tab_labels_present(self):
        html = cl.tabs([("Tab A", "content A"), ("Tab B", "content B")])
        self.assertIn("Tab A", html)
        self.assertIn("Tab B", html)

    def test_tab_content_present(self):
        html = cl.tabs([("T", "my content")])
        self.assertIn("my content", html)

    def test_active_tab_marked(self):
        html = cl.tabs([("First", "c1"), ("Second", "c2")], active_index=1)
        self.assertIn("cca-tab-active", html)

    def test_default_active_is_zero(self):
        html = cl.tabs([("T1", "c1"), ("T2", "c2")])
        # First tab should be active
        idx = html.find("cca-tab-active")
        self.assertGreater(idx, -1)

    def test_empty_tabs_returns_empty_container(self):
        html = cl.tabs([])
        self.assertIn("cca-tabs", html)

    def test_panel_ids_unique(self):
        html = cl.tabs([("A", "ca"), ("B", "cb"), ("C", "cc")])
        self.assertIn("cca-panel-", html)


class TestStatCard(unittest.TestCase):
    def test_label_present(self):
        html = cl.stat_card("Revenue", "1,234")
        self.assertIn("Revenue", html)

    def test_value_present(self):
        html = cl.stat_card("Score", "99.5")
        self.assertIn("99.5", html)

    def test_positive_delta(self):
        html = cl.stat_card("X", "10", delta="+5%", delta_dir="up")
        self.assertIn("+5%", html)
        self.assertIn("cca-delta-up", html)

    def test_negative_delta(self):
        html = cl.stat_card("X", "10", delta="-2%", delta_dir="down")
        self.assertIn("-2%", html)
        self.assertIn("cca-delta-down", html)

    def test_no_delta_renders(self):
        html = cl.stat_card("X", "42")
        self.assertIn("cca-stat-card", html)

    def test_subtitle_when_given(self):
        html = cl.stat_card("X", "5", subtitle="vs last week")
        self.assertIn("vs last week", html)


class TestComponentStylesheet(unittest.TestCase):
    def test_returns_string(self):
        css = cl.component_stylesheet()
        self.assertIsInstance(css, str)

    def test_includes_token_vars(self):
        css = cl.component_stylesheet()
        self.assertIn("--cca-primary", css)

    def test_includes_button_styles(self):
        css = cl.component_stylesheet()
        self.assertIn("cca-btn", css)

    def test_includes_card_styles(self):
        css = cl.component_stylesheet()
        self.assertIn("cca-card", css)

    def test_includes_table_styles(self):
        css = cl.component_stylesheet()
        self.assertIn("cca-table", css)

    def test_includes_badge_styles(self):
        css = cl.component_stylesheet()
        self.assertIn("cca-badge", css)


class TestPage(unittest.TestCase):
    def test_returns_full_html(self):
        html = cl.page("Test Page", ["<p>Hello</p>"])
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<html", html)

    def test_title_in_head(self):
        html = cl.page("My Title", [])
        self.assertIn("<title>My Title</title>", html)

    def test_components_in_body(self):
        html = cl.page("T", ["<p>comp1</p>", "<p>comp2</p>"])
        self.assertIn("comp1", html)
        self.assertIn("comp2", html)

    def test_stylesheet_included(self):
        html = cl.page("T", [])
        self.assertIn("cca-btn", html)

    def test_dark_theme_class(self):
        html = cl.page("T", [], theme="dark")
        self.assertIn("cca-theme-dark", html)


if __name__ == "__main__":
    unittest.main()
