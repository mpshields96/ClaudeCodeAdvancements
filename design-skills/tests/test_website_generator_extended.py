#!/usr/bin/env python3
"""Extended tests for website_generator.py — edge cases, error paths, XSS, anchor generation.

Covers gaps in the base test suite:
- Anchor generation edge cases (spaces, special chars, numbers, slashes, caps)
- Section level clamping (level < 2 → 2, level > 3 → 3)
- XSS in all user-controlled fields (nav URLs, metric values, code_block, code_lang)
- Feature card: icon + link together, link XSS
- DocsPage: module field, description XSS, title in <title> tag, minimal nav
- _demo_landing_page() exercise
- CSS helper function output
- Constants (COLORS, FONTS) structure
- Return type assertions
- Large input handling (many features/metrics/sections)
- Unicode and emoji content
- MetricCard unit XSS
- Code block with no lang
- NavLink URL XSS in docs
- Docs page title in <title> with "Documentation" suffix
"""

import html as html_mod
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from website_generator import (
    COLORS,
    FONTS,
    DocSection,
    DocsPage,
    FeatureCard,
    LandingPage,
    MetricCard,
    NavLink,
    _base_css,
    _collect_landing_page,
    _demo_landing_page,
    _docs_css,
    _landing_css,
    render_docs_page,
    render_landing_page,
    write_docs_page,
    write_landing_page,
)


# ── Constants ─────────────────────────────────────────────────────────────────

class TestConstants(unittest.TestCase):

    def test_colors_has_required_keys(self):
        for key in ("primary", "accent", "highlight", "success", "muted", "background", "surface", "border"):
            self.assertIn(key, COLORS)

    def test_colors_are_hex_strings(self):
        for key, val in COLORS.items():
            self.assertTrue(val.startswith("#"), f"{key} should be hex but got {val!r}")
            self.assertGreater(len(val), 3)

    def test_fonts_has_body_and_mono(self):
        self.assertIn("body", FONTS)
        self.assertIn("mono", FONTS)

    def test_fonts_are_nonempty_strings(self):
        for key, val in FONTS.items():
            self.assertIsInstance(val, str)
            self.assertGreater(len(val), 0)


# ── CSS helpers ───────────────────────────────────────────────────────────────

class TestCSSHelpers(unittest.TestCase):

    def test_base_css_returns_string(self):
        css = _base_css()
        self.assertIsInstance(css, str)
        self.assertGreater(len(css), 100)

    def test_base_css_contains_nav_class(self):
        css = _base_css()
        self.assertIn(".nav", css)

    def test_base_css_contains_primary_color(self):
        css = _base_css()
        self.assertIn(COLORS["primary"], css)

    def test_landing_css_returns_string(self):
        css = _landing_css()
        self.assertIsInstance(css, str)
        self.assertGreater(len(css), 100)

    def test_landing_css_has_hero_class(self):
        css = _landing_css()
        self.assertIn(".hero", css)

    def test_landing_css_has_feature_card_class(self):
        css = _landing_css()
        self.assertIn(".feature-card", css)

    def test_docs_css_returns_string(self):
        css = _docs_css()
        self.assertIsInstance(css, str)
        self.assertGreater(len(css), 100)

    def test_docs_css_has_sidebar_class(self):
        css = _docs_css()
        self.assertIn(".docs-sidebar", css)

    def test_docs_css_has_media_query(self):
        css = _docs_css()
        self.assertIn("@media", css)


# ── render_landing_page return type ──────────────────────────────────────────

class TestReturnTypes(unittest.TestCase):

    def _minimal_landing(self):
        return LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://x.com"
        )

    def _minimal_docs(self):
        return DocsPage(title="D", module="mod", description="desc")

    def test_render_landing_returns_str(self):
        result = render_landing_page(self._minimal_landing())
        self.assertIsInstance(result, str)

    def test_render_docs_returns_str(self):
        result = render_docs_page(self._minimal_docs())
        self.assertIsInstance(result, str)


# ── XSS: all user-controlled fields ──────────────────────────────────────────

class TestXSSAllFields(unittest.TestCase):
    """Every user-supplied field that ends up in HTML must be escaped."""

    def test_xss_in_tagline(self):
        page = LandingPage(
            title="T", tagline='<img src=x onerror=alert(1)>',
            hero_cta_text="Go", hero_cta_url="https://safe.com"
        )
        out = render_landing_page(page)
        self.assertNotIn("<img src=x", out)
        self.assertIn("&lt;img", out)

    def test_xss_in_hero_cta_text(self):
        page = LandingPage(
            title="T", tagline="tg",
            hero_cta_text='<script>bad()</script>',
            hero_cta_url="https://safe.com"
        )
        out = render_landing_page(page)
        self.assertNotIn("<script>bad()", out)

    def test_xss_in_hero_cta_url_quote_injection(self):
        """html.escape protects against quote-breaking injection in URL attributes."""
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go",
            hero_cta_url='https://x.com?a=" onclick="evil()'
        )
        out = render_landing_page(page)
        # The injected double-quote must be escaped to &quot; — breaking the injection
        self.assertNotIn('" onclick="evil()', out)
        self.assertIn("&quot;", out)

    def test_xss_in_feature_title(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=[FeatureCard('<b>evil</b>', "desc")]
        )
        out = render_landing_page(page)
        self.assertNotIn("<b>evil</b>", out)
        self.assertIn("&lt;b&gt;evil&lt;/b&gt;", out)

    def test_xss_in_feature_link_url_quote_injection(self):
        """Quote injection in feature link URL is blocked by html.escape."""
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=[FeatureCard("Title", "desc", link='https://x.com?" onclick="evil()')]
        )
        out = render_landing_page(page)
        self.assertNotIn('" onclick="evil()', out)
        self.assertIn("&quot;", out)

    def test_xss_in_feature_icon(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=[FeatureCard("Title", "desc", icon='<script>x()</script>')]
        )
        out = render_landing_page(page)
        self.assertNotIn("<script>x()", out)

    def test_xss_in_metric_label(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            metrics=[MetricCard('<script>lbl()</script>', "100")]
        )
        out = render_landing_page(page)
        self.assertNotIn("<script>lbl()", out)

    def test_xss_in_metric_value(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            metrics=[MetricCard("Tests", '<script>val()</script>')]
        )
        out = render_landing_page(page)
        self.assertNotIn("<script>val()", out)

    def test_xss_in_metric_unit(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            metrics=[MetricCard("Tests", "99", unit='<script>unit()</script>')]
        )
        out = render_landing_page(page)
        self.assertNotIn("<script>unit()", out)

    def test_xss_in_nav_link_label(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            nav_links=[NavLink('<script>nav()</script>', '/')]
        )
        out = render_landing_page(page)
        self.assertNotIn("<script>nav()", out)

    def test_xss_in_nav_link_url_quote_injection(self):
        """Quote injection in nav link URL is blocked by html.escape."""
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            nav_links=[NavLink("Go", 'https://x.com?" onclick="evil()')]
        )
        out = render_landing_page(page)
        self.assertNotIn('" onclick="evil()', out)
        self.assertIn("&quot;", out)

    def test_xss_in_docs_title(self):
        page = DocsPage(
            title='<script>evil()</script>', module="mod", description="d"
        )
        out = render_docs_page(page)
        self.assertNotIn("<script>evil()", out)

    def test_xss_in_docs_description(self):
        page = DocsPage(
            title="T", module="mod", description='<img onerror=x src=y>'
        )
        out = render_docs_page(page)
        self.assertNotIn("<img onerror=x", out)

    def test_xss_in_docs_section_heading(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection('<script>h()</script>', "content")]
        )
        out = render_docs_page(page)
        self.assertNotIn("<script>h()", out)

    def test_xss_in_code_block_escaped_in_pre(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "c", code_block='<script>evil()</script>')]
        )
        out = render_docs_page(page)
        # Inside <pre><code> the content must be HTML-escaped to avoid XSS
        self.assertNotIn("<script>evil()", out)

    def test_xss_in_code_lang_attribute(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "c", code_block="x=1", code_lang='"onclick=evil()')]
        )
        out = render_docs_page(page)
        self.assertNotIn('"onclick=evil()', out)

    def test_xss_in_docs_nav_link_url_quote_injection(self):
        """Quote injection in docs nav link URL is blocked by html.escape."""
        page = DocsPage(
            title="T", module="mod", description="d",
            nav_links=[NavLink("Go", 'https://x.com?" onclick="evil()')]
        )
        out = render_docs_page(page)
        self.assertNotIn('" onclick="evil()', out)
        self.assertIn("&quot;", out)


# ── Section level clamping ────────────────────────────────────────────────────

class TestSectionLevelClamping(unittest.TestCase):

    def test_level_1_clamped_to_h2(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "content", level=1)]
        )
        out = render_docs_page(page)
        self.assertIn("<h2>", out)
        self.assertNotIn("<h1>Sec</h1>", out)

    def test_level_4_clamped_to_h3(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "content", level=4)]
        )
        out = render_docs_page(page)
        self.assertIn("<h3>", out)
        self.assertNotIn("<h4>", out)

    def test_level_5_clamped_to_h3(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "content", level=5)]
        )
        out = render_docs_page(page)
        self.assertNotIn("<h5>", out)

    def test_level_0_clamped_to_h2(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "content", level=0)]
        )
        out = render_docs_page(page)
        self.assertIn("<h2>", out)


# ── Anchor generation edge cases ──────────────────────────────────────────────

class TestAnchorGeneration(unittest.TestCase):

    def _anchor_from(self, heading: str) -> str:
        """Get the generated anchor ID by checking the rendered HTML."""
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection(heading, "content")]
        )
        out = render_docs_page(page)
        # Find id="..." pattern
        import re
        match = re.search(r'id="([^"]+)"', out)
        return match.group(1) if match else ""

    def test_anchor_all_lowercase(self):
        anchor = self._anchor_from("Getting Started")
        self.assertEqual(anchor, "getting-started")

    def test_anchor_spaces_to_hyphens(self):
        anchor = self._anchor_from("Install And Run")
        self.assertEqual(anchor, "install-and-run")

    def test_anchor_slash_to_hyphen(self):
        anchor = self._anchor_from("API/Usage")
        self.assertEqual(anchor, "api-usage")

    def test_anchor_single_word(self):
        anchor = self._anchor_from("Overview")
        self.assertEqual(anchor, "overview")

    def test_anchor_numbers_preserved(self):
        anchor = self._anchor_from("Phase 2 Build")
        self.assertEqual(anchor, "phase-2-build")

    def test_sidebar_references_same_anchor(self):
        """Sidebar href must match section id."""
        heading = "Quick Start"
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection(heading, "content")]
        )
        out = render_docs_page(page)
        self.assertIn('href="#quick-start"', out)
        self.assertIn('id="quick-start"', out)


# ── Feature card combinations ─────────────────────────────────────────────────

class TestFeatureCardCombinations(unittest.TestCase):

    def test_icon_and_link_together(self):
        """Feature card with both icon and link should render both."""
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=[FeatureCard("Memory", "Desc", icon="🧠", link="https://github.com/x")]
        )
        out = render_landing_page(page)
        self.assertIn("🧠", out)
        self.assertIn('href="https://github.com/x"', out)
        self.assertIn("feature-icon", out)

    def test_feature_no_icon_no_link(self):
        """Feature without icon/link should not render icon span element."""
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=[FeatureCard("Plain", "No extras")]
        )
        out = render_landing_page(page)
        # CSS has .feature-icon class but no actual <span class="feature-icon"> should be present
        self.assertNotIn('<span class="feature-icon">', out)
        # Title should be plain text, not in anchor
        self.assertIn("Plain", out)

    def test_multiple_features_all_rendered(self):
        features = [FeatureCard(f"Feature {i}", f"Desc {i}") for i in range(10)]
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=features
        )
        out = render_landing_page(page)
        for i in range(10):
            self.assertIn(f"Feature {i}", out)


# ── Multiple nav links, active state ──────────────────────────────────────────

class TestNavLinkRendering(unittest.TestCase):

    def test_multiple_active_nav_links(self):
        """Multiple active links — each gets active class."""
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            nav_links=[
                NavLink("Home", "/", active=True),
                NavLink("Docs", "/docs", active=True),
            ]
        )
        out = render_landing_page(page)
        self.assertEqual(out.count('class="active"'), 2)

    def test_docs_active_nav_link(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            nav_links=[NavLink("Home", "/", active=True), NavLink("API", "/api")]
        )
        out = render_docs_page(page)
        self.assertIn('class="active"', out)


# ── Docs page: title in <title> tag ──────────────────────────────────────────

class TestDocsPageTitleTag(unittest.TestCase):

    def test_title_tag_has_documentation_suffix(self):
        page = DocsPage(title="My Module", module="mod", description="d")
        out = render_docs_page(page)
        self.assertIn("<title>My Module — Documentation</title>", out)

    def test_landing_page_title_tag_no_suffix(self):
        page = LandingPage(
            title="MyProject", tagline="tg", hero_cta_text="Go", hero_cta_url="https://x.com"
        )
        out = render_landing_page(page)
        self.assertIn("<title>MyProject</title>", out)


# ── Code block edge cases ─────────────────────────────────────────────────────

class TestCodeBlockEdgeCases(unittest.TestCase):

    def test_code_block_no_lang_renders_empty_class(self):
        """code_lang=None → class="language-" (empty lang)."""
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "c", code_block="x = 1", code_lang=None)]
        )
        out = render_docs_page(page)
        self.assertIn('class="language-"', out)
        self.assertIn("x = 1", out)

    def test_code_block_with_lang_renders_class(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "c", code_block="x = 1", code_lang="python")]
        )
        out = render_docs_page(page)
        self.assertIn('class="language-python"', out)

    def test_code_block_none_no_pre_element(self):
        """No code_block → no <pre> rendered."""
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "content")]
        )
        out = render_docs_page(page)
        # pre should only exist inside CSS definitions, not as an HTML element
        # (CSS may contain 'pre {' so count actual <pre> HTML tags)
        # <pre><code is the pattern to look for
        self.assertNotIn("<pre><code", out)

    def test_code_block_multiline(self):
        code = "line1\nline2\nline3"
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "c", code_block=code, code_lang="bash")]
        )
        out = render_docs_page(page)
        self.assertIn("line1", out)
        self.assertIn("line2", out)
        self.assertIn("line3", out)


# ── Unicode and emoji content ─────────────────────────────────────────────────

class TestUnicodeContent(unittest.TestCase):

    def test_emoji_in_feature_icon_preserved(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=[FeatureCard("Feature", "desc", icon="🚀")]
        )
        out = render_landing_page(page)
        self.assertIn("🚀", out)

    def test_unicode_title(self):
        page = LandingPage(
            title="CCA — Advanced Tools", tagline="tg",
            hero_cta_text="Go", hero_cta_url="https://safe.com"
        )
        out = render_landing_page(page)
        self.assertIn("CCA", out)
        self.assertIn("Advanced Tools", out)

    def test_unicode_in_section_content(self):
        page = DocsPage(
            title="T", module="mod", description="d",
            sections=[DocSection("Sec", "日本語テスト")]
        )
        out = render_docs_page(page)
        self.assertIn("日本語テスト", out)


# ── Large inputs ──────────────────────────────────────────────────────────────

class TestLargeInputs(unittest.TestCase):

    def test_many_metrics_all_rendered(self):
        metrics = [MetricCard(f"Label{i}", str(i * 100)) for i in range(20)]
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            metrics=metrics
        )
        out = render_landing_page(page)
        for i in range(20):
            self.assertIn(f"Label{i}", out)

    def test_many_sections_all_in_sidebar(self):
        sections = [DocSection(f"Section {i}", f"Content {i}") for i in range(15)]
        page = DocsPage(title="T", module="mod", description="d", sections=sections)
        out = render_docs_page(page)
        for i in range(15):
            self.assertIn(f"Section {i}", out)
            self.assertIn(f'href="#section-{i}"', out)


# ── Special string values ─────────────────────────────────────────────────────

class TestSpecialStringValues(unittest.TestCase):

    def test_metric_with_dollar_sign(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            metrics=[MetricCard("Revenue", "$250", unit="/mo")]
        )
        out = render_landing_page(page)
        self.assertIn("$250", out)
        self.assertIn("/mo", out)

    def test_metric_with_percent(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            metrics=[MetricCard("Win Rate", "72%")]
        )
        out = render_landing_page(page)
        self.assertIn("72%", out)

    def test_long_description_in_feature(self):
        long_desc = "A " * 200
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=[FeatureCard("Feature", long_desc)]
        )
        out = render_landing_page(page)
        self.assertIn("A ", out)


# ── _demo_landing_page() ──────────────────────────────────────────────────────

class TestDemoLandingPage(unittest.TestCase):

    def test_demo_returns_landing_page(self):
        page = _demo_landing_page()
        self.assertIsInstance(page, LandingPage)

    def test_demo_has_features(self):
        page = _demo_landing_page()
        self.assertGreater(len(page.features), 0)

    def test_demo_has_metrics(self):
        page = _demo_landing_page()
        self.assertGreater(len(page.metrics), 0)

    def test_demo_has_nav_links(self):
        page = _demo_landing_page()
        self.assertGreater(len(page.nav_links), 0)

    def test_demo_renders_to_valid_html(self):
        page = _demo_landing_page()
        out = render_landing_page(page)
        self.assertIn("<!DOCTYPE html>", out)
        self.assertIn("ClaudeCodeAdvancements", out)

    def test_demo_title_is_cca(self):
        page = _demo_landing_page()
        self.assertEqual(page.title, "ClaudeCodeAdvancements")


# ── DocsPage module field ──────────────────────────────────────────────────────

class TestDocsPageModuleField(unittest.TestCase):

    def test_module_field_stored(self):
        page = DocsPage(title="T", module="agent-guard", description="d")
        self.assertEqual(page.module, "agent-guard")

    def test_module_field_not_in_rendered_html_by_default(self):
        """Module is metadata — not rendered directly in output."""
        page = DocsPage(title="T", module="secret-module-xyz", description="d")
        out = render_docs_page(page)
        # module is a data field, not rendered into HTML
        self.assertNotIn("secret-module-xyz", out)


# ── File I/O edge cases ───────────────────────────────────────────────────────

class TestFileIOEdgeCases(unittest.TestCase):

    def test_write_landing_page_utf8_content(self):
        """File written as UTF-8, emoji and unicode survive round-trip."""
        page = LandingPage(
            title="CCA 🚀",
            tagline="Advanced Tools — Next Level",
            hero_cta_text="Start",
            hero_cta_url="https://github.com/x",
        )
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            write_landing_page(page, path)
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("🚀", content)
            self.assertIn("<!DOCTYPE html>", content)
        finally:
            os.unlink(path)

    def test_write_docs_page_overwrites_existing(self):
        """write_docs_page overwrites existing file."""
        page = DocsPage(title="T", module="mod", description="d")
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write("<old content>")
            path = f.name
        try:
            write_docs_page(page, path)
            content = Path(path).read_text(encoding="utf-8")
            self.assertNotIn("<old content>", content)
            self.assertIn("<!DOCTYPE html>", content)
        finally:
            os.unlink(path)


# ── LandingPage: no metrics section when empty ────────────────────────────────

class TestLandingPageOptionalSections(unittest.TestCase):

    def test_no_metrics_no_metrics_strip(self):
        """No metrics → no <div class="metrics-strip"> element in body."""
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            metrics=[]
        )
        out = render_landing_page(page)
        # CSS defines .metrics-strip but no actual HTML element should be rendered
        self.assertNotIn('<div class="metrics-strip">', out)

    def test_no_features_no_features_grid(self):
        """No features → no <div class="features-grid"> element in body."""
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=[]
        )
        out = render_landing_page(page)
        self.assertNotIn('<div class="features-grid">', out)

    def test_with_metrics_has_metrics_strip(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            metrics=[MetricCard("Tests", "100")]
        )
        out = render_landing_page(page)
        self.assertIn("metrics-strip", out)

    def test_with_features_has_features_grid(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com",
            features=[FeatureCard("F", "d")]
        )
        out = render_landing_page(page)
        self.assertIn("features-grid", out)


# ── HTML structure completeness ───────────────────────────────────────────────

class TestHTMLCompleteness(unittest.TestCase):

    def test_landing_has_charset_utf8(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com"
        )
        out = render_landing_page(page)
        self.assertIn('charset="UTF-8"', out)

    def test_docs_has_charset_utf8(self):
        page = DocsPage(title="T", module="mod", description="d")
        out = render_docs_page(page)
        self.assertIn('charset="UTF-8"', out)

    def test_docs_has_viewport_meta(self):
        page = DocsPage(title="T", module="mod", description="d")
        out = render_docs_page(page)
        self.assertIn("viewport", out)

    def test_docs_has_lang_en(self):
        page = DocsPage(title="T", module="mod", description="d")
        out = render_docs_page(page)
        self.assertIn('lang="en"', out)

    def test_landing_has_lang_en(self):
        page = LandingPage(
            title="T", tagline="tg", hero_cta_text="Go", hero_cta_url="https://safe.com"
        )
        out = render_landing_page(page)
        self.assertIn('lang="en"', out)

    def test_docs_layout_wrapper_present(self):
        page = DocsPage(title="T", module="mod", description="d")
        out = render_docs_page(page)
        self.assertIn('class="docs-layout"', out)

    def test_docs_sidebar_present(self):
        page = DocsPage(title="T", module="mod", description="d")
        out = render_docs_page(page)
        self.assertIn('class="docs-sidebar"', out)


if __name__ == "__main__":
    unittest.main()
