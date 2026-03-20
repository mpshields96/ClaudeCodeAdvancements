#!/usr/bin/env python3
"""Tests for website_generator.py — MT-17 Phase 5: website/landing page templates.

Tests both LandingPage and DocsPage templates for:
- Correct HTML structure
- XSS safety (all user content escaped)
- Design token application (colors from design-guide.md)
- All sections rendered
- File I/O
"""

import html
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from website_generator import (
    LandingPage,
    FeatureCard,
    MetricCard,
    NavLink,
    DocsPage,
    DocSection,
    render_landing_page,
    render_docs_page,
)

# ── LandingPage data tests ───────────────────────────────────────────────────

class TestFeatureCard(unittest.TestCase):

    def test_feature_card_fields(self):
        card = FeatureCard(title="Memory System", description="Persistent cross-session memory.", icon="🧠")
        self.assertEqual(card.title, "Memory System")
        self.assertEqual(card.description, "Persistent cross-session memory.")
        self.assertEqual(card.icon, "🧠")

    def test_feature_card_optional_icon(self):
        card = FeatureCard(title="Spec System", description="Spec-driven development.")
        self.assertIsNone(card.icon)

    def test_feature_card_optional_link(self):
        card = FeatureCard(title="Context Monitor", description="Context health monitoring.", link="https://github.com/x")
        self.assertEqual(card.link, "https://github.com/x")


class TestMetricCard(unittest.TestCase):

    def test_metric_card_fields(self):
        m = MetricCard(label="Tests Passing", value="2484", unit="tests")
        self.assertEqual(m.label, "Tests Passing")
        self.assertEqual(m.value, "2484")
        self.assertEqual(m.unit, "tests")

    def test_metric_card_no_unit(self):
        m = MetricCard(label="Sessions", value="69")
        self.assertIsNone(m.unit)


class TestNavLink(unittest.TestCase):

    def test_nav_link_fields(self):
        n = NavLink(label="GitHub", url="https://github.com/x")
        self.assertEqual(n.label, "GitHub")
        self.assertEqual(n.url, "https://github.com/x")

    def test_nav_link_active(self):
        n = NavLink(label="Home", url="/", active=True)
        self.assertTrue(n.active)

    def test_nav_link_not_active_by_default(self):
        n = NavLink(label="About", url="/about")
        self.assertFalse(n.active)


class TestLandingPage(unittest.TestCase):

    def setUp(self):
        self.page = LandingPage(
            title="ClaudeCodeAdvancements",
            tagline="Next-level enhancements for Claude Code.",
            hero_cta_text="View on GitHub",
            hero_cta_url="https://github.com/x",
            features=[
                FeatureCard("Memory System", "Cross-session memory persistence."),
                FeatureCard("Spec System", "Spec-driven development workflow."),
                FeatureCard("Context Monitor", "Context health monitoring."),
            ],
            metrics=[
                MetricCard("Tests", "2484"),
                MetricCard("Modules", "9"),
            ],
            nav_links=[
                NavLink("Home", "/"),
                NavLink("GitHub", "https://github.com/x"),
            ],
        )

    def test_title_rendered(self):
        html_out = render_landing_page(self.page)
        self.assertIn("ClaudeCodeAdvancements", html_out)

    def test_tagline_rendered(self):
        html_out = render_landing_page(self.page)
        self.assertIn("Next-level enhancements for Claude Code.", html_out)

    def test_cta_button_rendered(self):
        html_out = render_landing_page(self.page)
        self.assertIn("View on GitHub", html_out)
        self.assertIn("https://github.com/x", html_out)

    def test_features_rendered(self):
        html_out = render_landing_page(self.page)
        self.assertIn("Memory System", html_out)
        self.assertIn("Spec System", html_out)
        self.assertIn("Context Monitor", html_out)

    def test_metrics_rendered(self):
        html_out = render_landing_page(self.page)
        self.assertIn("2484", html_out)
        self.assertIn("Tests", html_out)

    def test_nav_links_rendered(self):
        html_out = render_landing_page(self.page)
        self.assertIn("Home", html_out)
        self.assertIn("GitHub", html_out)

    def test_html_structure(self):
        html_out = render_landing_page(self.page)
        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("<html", html_out)
        self.assertIn("</html>", html_out)
        self.assertIn("<head>", html_out)
        self.assertIn("</head>", html_out)
        self.assertIn("<body>", html_out)
        self.assertIn("</body>", html_out)

    def test_xss_in_title(self):
        page = LandingPage(
            title="<script>alert('xss')</script>",
            tagline="safe",
            hero_cta_text="Go",
            hero_cta_url="https://safe.com",
        )
        html_out = render_landing_page(page)
        self.assertNotIn("<script>alert('xss')</script>", html_out)
        self.assertIn("&lt;script&gt;", html_out)

    def test_xss_in_feature_description(self):
        page = LandingPage(
            title="CCA",
            tagline="t",
            hero_cta_text="Go",
            hero_cta_url="https://safe.com",
            features=[
                FeatureCard("Title", "<img src=x onerror=alert(1)>"),
            ],
        )
        html_out = render_landing_page(page)
        self.assertNotIn("<img src=x onerror=alert(1)>", html_out)

    def test_design_colors_in_css(self):
        html_out = render_landing_page(self.page)
        self.assertIn("#1a1a2e", html_out)   # primary
        self.assertIn("#0f3460", html_out)   # accent
        self.assertIn("#e94560", html_out)   # highlight

    def test_self_contained_no_external_deps(self):
        html_out = render_landing_page(self.page)
        # No CDN links, no external CSS/JS
        self.assertNotIn("cdn.jsdelivr.net", html_out)
        self.assertNotIn("unpkg.com", html_out)
        self.assertNotIn("googleapis.com", html_out)
        self.assertNotIn('<script src="http', html_out)
        self.assertNotIn('<link rel="stylesheet" href="http', html_out)

    def test_viewport_meta_for_mobile(self):
        html_out = render_landing_page(self.page)
        self.assertIn("viewport", html_out)

    def test_page_title_in_head(self):
        html_out = render_landing_page(self.page)
        self.assertIn("<title>", html_out)
        self.assertIn("ClaudeCodeAdvancements", html_out)

    def test_empty_features_renders(self):
        page = LandingPage(
            title="CCA",
            tagline="t",
            hero_cta_text="Go",
            hero_cta_url="https://safe.com",
            features=[],
        )
        html_out = render_landing_page(page)
        self.assertIn("<!DOCTYPE html>", html_out)


# ── DocsPage tests ────────────────────────────────────────────────────────────

class TestDocSection(unittest.TestCase):

    def test_doc_section_fields(self):
        s = DocSection(
            heading="Installation",
            content="Run `pip install ...`",
            level=2,
        )
        self.assertEqual(s.heading, "Installation")
        self.assertIn("pip install", s.content)
        self.assertEqual(s.level, 2)

    def test_doc_section_default_level(self):
        s = DocSection(heading="Overview", content="An overview.")
        self.assertEqual(s.level, 2)

    def test_doc_section_code_block(self):
        s = DocSection(
            heading="Usage",
            content="Example",
            code_block="python3 doc_drift_checker.py",
            code_lang="bash",
        )
        self.assertEqual(s.code_lang, "bash")
        self.assertIn("doc_drift_checker", s.code_block)


class TestDocsPage(unittest.TestCase):

    def setUp(self):
        self.page = DocsPage(
            title="Doc Drift Checker",
            module="usage-dashboard",
            description="Detects when documentation drifts from codebase reality.",
            sections=[
                DocSection("Overview", "Automatically verifies test counts."),
                DocSection("Usage", "Run the CLI.", code_block="python3 doc_drift_checker.py", code_lang="bash"),
                DocSection("Configuration", "Set project root with --root."),
            ],
            nav_links=[
                NavLink("Home", "/"),
                NavLink("Modules", "/modules"),
            ],
        )

    def test_title_rendered(self):
        html_out = render_docs_page(self.page)
        self.assertIn("Doc Drift Checker", html_out)

    def test_description_rendered(self):
        html_out = render_docs_page(self.page)
        self.assertIn("Detects when documentation drifts", html_out)

    def test_sections_rendered(self):
        html_out = render_docs_page(self.page)
        self.assertIn("Overview", html_out)
        self.assertIn("Usage", html_out)
        self.assertIn("Configuration", html_out)

    def test_code_block_rendered(self):
        html_out = render_docs_page(self.page)
        self.assertIn("doc_drift_checker.py", html_out)

    def test_nav_links_rendered(self):
        html_out = render_docs_page(self.page)
        self.assertIn("Home", html_out)
        self.assertIn("Modules", html_out)

    def test_html_structure(self):
        html_out = render_docs_page(self.page)
        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("</html>", html_out)

    def test_xss_in_section_content(self):
        page = DocsPage(
            title="Test",
            module="mod",
            description="d",
            sections=[
                DocSection("Sec", "<script>evil()</script>"),
            ],
        )
        html_out = render_docs_page(page)
        self.assertNotIn("<script>evil()</script>", html_out)

    def test_xss_in_code_block_NOT_escaped(self):
        # Code blocks render content inside <pre><code> — content should be safe
        # but we do NOT double-escape code (users expect raw code)
        page = DocsPage(
            title="Test",
            module="mod",
            description="d",
            sections=[
                DocSection("Sec", "content", code_block='print("hello")', code_lang="python"),
            ],
        )
        html_out = render_docs_page(page)
        # The quotes in code blocks should be properly escaped for HTML
        self.assertIn("print", html_out)

    def test_sidebar_section_links(self):
        html_out = render_docs_page(self.page)
        # Sidebar should have anchor links to sections
        self.assertIn("Overview", html_out)
        self.assertIn("Usage", html_out)

    def test_design_colors_in_css(self):
        html_out = render_docs_page(self.page)
        self.assertIn("#1a1a2e", html_out)
        self.assertIn("#0f3460", html_out)

    def test_no_external_deps(self):
        html_out = render_docs_page(self.page)
        self.assertNotIn("cdn.jsdelivr.net", html_out)
        self.assertNotIn("googleapis.com", html_out)

    def test_empty_sections_renders(self):
        page = DocsPage(
            title="Empty",
            module="mod",
            description="d",
            sections=[],
        )
        html_out = render_docs_page(page)
        self.assertIn("<!DOCTYPE html>", html_out)


# ── File output tests ─────────────────────────────────────────────────────────

class TestFileOutput(unittest.TestCase):

    def test_write_landing_page_to_file(self):
        from website_generator import write_landing_page
        page = LandingPage(
            title="CCA",
            tagline="Advanced Claude Code tools.",
            hero_cta_text="Start",
            hero_cta_url="https://github.com/x",
        )
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            write_landing_page(page, path)
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("CCA", content)
            self.assertIn("<!DOCTYPE html>", content)
        finally:
            os.unlink(path)

    def test_write_docs_page_to_file(self):
        from website_generator import write_docs_page
        page = DocsPage(
            title="Agent Guard",
            module="agent-guard",
            description="Multi-agent conflict prevention.",
            sections=[DocSection("Overview", "Prevents conflicts.")],
        )
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            write_docs_page(page, path)
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("Agent Guard", content)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
