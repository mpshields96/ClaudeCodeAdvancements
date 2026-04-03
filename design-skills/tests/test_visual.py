"""Tests for visual.py — MT-32 Phase 7 integration layer."""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import visual as V
import chart_generator as cg


# ---------------------------------------------------------------------------
# Import / __all__
# ---------------------------------------------------------------------------

class TestImports:
    def test_all_defined(self):
        assert hasattr(V, "__all__")
        assert len(V.__all__) >= 60

    def test_no_private_in_all(self):
        for name in V.__all__:
            assert not name.startswith("_"), f"{name} is private"

    def test_all_names_exist(self):
        for name in V.__all__:
            assert hasattr(V, name), f"__all__ lists '{name}' but it is not on the module"


# ---------------------------------------------------------------------------
# Chart pillar
# ---------------------------------------------------------------------------

class TestChartPillar:
    def test_bar_chart_accessible(self):
        assert V.BarChart is not None

    def test_line_chart_accessible(self):
        assert V.LineChart is not None

    def test_donut_chart_accessible(self):
        assert V.DonutChart is not None

    def test_render_chart_svg_accessible(self):
        assert callable(V.render_chart_svg)

    def test_save_chart_svg_accessible(self):
        assert callable(V.save_chart_svg)


# ---------------------------------------------------------------------------
# Component pillar
# ---------------------------------------------------------------------------

class TestComponentPillar:
    def test_card_accessible(self):
        assert callable(V.card)

    def test_stat_card_accessible(self):
        assert callable(V.stat_card)

    def test_data_table_accessible(self):
        assert callable(V.data_table)

    def test_page_accessible(self):
        assert callable(V.page)

    def test_component_stylesheet_accessible(self):
        assert callable(V.component_stylesheet)

    def test_card_produces_html(self):
        html = V.card("Title", "<p>body</p>")
        assert "Title" in html

    def test_stat_card_produces_html(self):
        html = V.stat_card("Metric", "42")
        assert "Metric" in html
        assert "42" in html


# ---------------------------------------------------------------------------
# Diagram pillar
# ---------------------------------------------------------------------------

class TestDiagramPillar:
    def test_flow_diagram_accessible(self):
        assert V.FlowDiagram is not None

    def test_sequence_diagram_accessible(self):
        assert V.SequenceDiagram is not None

    def test_render_diagram_accessible(self):
        assert callable(V.render_diagram)

    def test_save_diagram_accessible(self):
        assert callable(V.save_diagram)

    def test_flow_diagram_renders(self):
        fd = V.FlowDiagram()
        fd.add_node("a", "A").add_node("b", "B")
        fd.add_edge("a", "b")
        svg = V.render_diagram(fd)
        assert svg.startswith("<svg")

    def test_sequence_diagram_renders(self):
        sd = V.SequenceDiagram()
        sd.add_actor("u", "User").add_actor("s", "Server")
        sd.add_message("u", "s", "req")
        svg = V.render_diagram(sd)
        assert svg.startswith("<svg")


# ---------------------------------------------------------------------------
# Figure pillar
# ---------------------------------------------------------------------------

class TestFigurePillar:
    def test_figure_accessible(self):
        assert V.Figure is not None

    def test_figure_panel_accessible(self):
        assert V.FigurePanel is not None

    def test_render_figure_accessible(self):
        assert callable(V.render_figure)

    def test_save_figure_accessible(self):
        assert callable(V.save_figure)

    def test_quick_figure_accessible(self):
        assert callable(V.quick_figure)

    def test_annotation_types_accessible(self):
        assert V.Annotation is not None
        assert V.TextAnnotation is not None
        assert V.ArrowAnnotation is not None
        assert V.HighlightAnnotation is not None


# ---------------------------------------------------------------------------
# Dashboard pillar
# ---------------------------------------------------------------------------

class TestDashboardPillar:
    def test_dashboard_renderer_accessible(self):
        assert V.DashboardRenderer is not None

    def test_dashboard_data_accessible(self):
        assert V.DashboardData is not None


# ---------------------------------------------------------------------------
# Slide pillar
# ---------------------------------------------------------------------------

class TestSlidePillar:
    def test_slide_generator_accessible(self):
        assert V.SlideGenerator is not None

    def test_slide_data_collector_accessible(self):
        assert V.SlideDataCollector is not None

    def test_collect_slides_accessible(self):
        assert callable(V.collect_slides_from_project)


# ---------------------------------------------------------------------------
# make_flow factory
# ---------------------------------------------------------------------------

class TestMakeFlow:
    def test_returns_flow_diagram(self):
        fd = V.make_flow()
        assert isinstance(fd, V.FlowDiagram)

    def test_with_title(self):
        fd = V.make_flow("My Flow")
        assert fd.title == "My Flow"

    def test_no_title(self):
        fd = V.make_flow()
        assert fd.title == ""

    def test_supports_chaining(self):
        fd = V.make_flow()
        result = fd.add_node("a", "A")
        assert result is fd

    def test_renders_after_factory(self):
        fd = V.make_flow("Pipeline")
        fd.add_node("s", "Start", kind="terminal")
        fd.add_node("e", "End", kind="terminal")
        fd.add_edge("s", "e")
        svg = V.render_diagram(fd)
        assert "Pipeline" in svg
        assert "Start" in svg


# ---------------------------------------------------------------------------
# make_sequence factory
# ---------------------------------------------------------------------------

class TestMakeSequence:
    def test_returns_sequence_diagram(self):
        sd = V.make_sequence()
        assert isinstance(sd, V.SequenceDiagram)

    def test_with_title(self):
        sd = V.make_sequence("Auth")
        assert sd.title == "Auth"

    def test_no_title(self):
        sd = V.make_sequence()
        assert sd.title == ""

    def test_renders_after_factory(self):
        sd = V.make_sequence("Login")
        sd.add_actor("u", "User").add_actor("s", "Server")
        sd.add_message("u", "s", "POST /login")
        sd.add_message("s", "u", "200 OK", style="return")
        svg = V.render_diagram(sd)
        assert "Login" in svg
        assert "User" in svg
        assert "Server" in svg


# ---------------------------------------------------------------------------
# make_chart factory
# ---------------------------------------------------------------------------

class TestMakeChart:
    _data = [("A", 10), ("B", 20), ("C", 15)]

    def test_bar(self):
        c = V.make_chart("bar", data=self._data)
        assert isinstance(c, V.BarChart)

    def test_line(self):
        c = V.make_chart("line", data=self._data)
        assert isinstance(c, V.LineChart)

    def test_donut(self):
        c = V.make_chart("donut", data=self._data)
        assert isinstance(c, V.DonutChart)

    def test_hbar(self):
        c = V.make_chart("hbar", data=self._data)
        assert isinstance(c, V.HorizontalBarChart)

    def test_horizontal_bar_alias(self):
        c = V.make_chart("horizontal_bar", data=self._data)
        assert isinstance(c, V.HorizontalBarChart)

    def test_scatter(self):
        # ScatterPlot takes series (list of dicts), not data
        c = V.make_chart("scatter", series=[{"label": "S", "points": [(1, 2), (3, 4)]}])
        assert isinstance(c, V.ScatterPlot)

    def test_case_insensitive(self):
        c = V.make_chart("BAR", data=self._data)
        assert isinstance(c, V.BarChart)

    def test_hyphen_normalised(self):
        # StackedBarChart requires series_names alongside data
        c = V.make_chart("stacked-bar", data=self._data, series_names=["A"])
        assert isinstance(c, V.StackedBarChart)

    def test_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown chart kind"):
            V.make_chart("banana", data=[])

    def test_kwargs_forwarded(self):
        c = V.make_chart("bar", data=self._data, title="My Chart")
        assert c.title == "My Chart"

    def test_gauge(self):
        # GaugeChart takes value (float), not data
        c = V.make_chart("gauge", value=75.0)
        assert isinstance(c, V.GaugeChart)

    def test_radar(self):
        c = V.make_chart("radar", data=self._data)
        assert isinstance(c, V.RadarChart)


# ---------------------------------------------------------------------------
# Cross-pillar: save round-trips
# ---------------------------------------------------------------------------

class TestSaveIntegration:
    def test_save_flow_diagram(self):
        fd = V.make_flow()
        fd.add_node("a", "A").add_node("b", "B")
        fd.add_edge("a", "b")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "flow.svg")
            result = V.save_diagram(fd, path)
            assert os.path.exists(path)
            assert result == path
            content = open(path).read()
            assert "<svg" in content

    def test_save_sequence_diagram(self):
        sd = V.make_sequence()
        sd.add_actor("a", "A").add_actor("b", "B")
        sd.add_message("a", "b", "hi")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seq.svg")
            V.save_diagram(sd, path)
            assert os.path.exists(path)
