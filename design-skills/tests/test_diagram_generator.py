"""Tests for diagram_generator.py — MT-32 Phase 6."""
import os
import tempfile

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from diagram_generator import (
    FlowDiagram, FlowNode, FlowEdge,
    SequenceDiagram, SequenceActor, SequenceMessage,
    render_diagram, render_flow_diagram, render_sequence_diagram,
    save_diagram,
)


# ---------------------------------------------------------------------------
# FlowDiagram — construction
# ---------------------------------------------------------------------------

class TestFlowDiagramConstruction:
    def _simple(self):
        fd = FlowDiagram()
        fd.add_node("a", "Step A")
        fd.add_node("b", "Step B")
        fd.add_edge("a", "b")
        return fd

    def test_add_node_returns_self(self):
        fd = FlowDiagram()
        result = fd.add_node("x", "X")
        assert result is fd

    def test_add_edge_returns_self(self):
        fd = FlowDiagram()
        fd.add_node("a", "A").add_node("b", "B")
        result = fd.add_edge("a", "b")
        assert result is fd

    def test_node_kinds_accepted(self):
        fd = FlowDiagram()
        for kind in ("process", "decision", "terminal", "data", "io"):
            fd.add_node(kind, kind.capitalize(), kind=kind)
        assert len(fd._nodes) == 5

    def test_invalid_kind_raises(self):
        fd = FlowDiagram()
        with pytest.raises(ValueError, match="Unknown node kind"):
            fd.add_node("x", "X", kind="banana")

    def test_nodes_stored(self):
        fd = self._simple()
        assert "a" in fd._nodes
        assert "b" in fd._nodes

    def test_edges_stored(self):
        fd = self._simple()
        assert len(fd._edges) == 1
        assert fd._edges[0].src == "a"
        assert fd._edges[0].dst == "b"

    def test_edge_with_label(self):
        fd = FlowDiagram()
        fd.add_node("a", "A").add_node("b", "B")
        fd.add_edge("a", "b", label="yes")
        assert fd._edges[0].label == "yes"

    def test_edge_dashed_style(self):
        fd = FlowDiagram()
        fd.add_node("a", "A").add_node("b", "B")
        fd.add_edge("a", "b", style="dashed")
        assert fd._edges[0].style == "dashed"


# ---------------------------------------------------------------------------
# FlowDiagram — rendering
# ---------------------------------------------------------------------------

class TestFlowDiagramRendering:
    def _pipeline(self):
        fd = FlowDiagram(title="Pipeline")
        fd.add_node("start", "Start", kind="terminal")
        fd.add_node("validate", "Validate Input", kind="process")
        fd.add_node("ok", "Valid?", kind="decision")
        fd.add_node("process", "Process", kind="process")
        fd.add_node("error", "Return Error", kind="process")
        fd.add_node("end", "Done", kind="terminal")
        fd.add_edge("start", "validate")
        fd.add_edge("validate", "ok")
        fd.add_edge("ok", "process", label="yes")
        fd.add_edge("ok", "error", label="no")
        fd.add_edge("process", "end")
        fd.add_edge("error", "end")
        return fd

    def test_renders_svg(self):
        svg = render_diagram(self._pipeline())
        assert svg.startswith("<svg")
        assert svg.strip().endswith("</svg>")

    def test_svg_has_title(self):
        svg = render_diagram(self._pipeline())
        assert "Pipeline" in svg

    def test_svg_has_node_labels(self):
        svg = render_diagram(self._pipeline())
        assert "Validate" in svg
        assert "Valid?" in svg
        assert "Process" in svg

    def test_svg_has_edge_labels(self):
        svg = render_diagram(self._pipeline())
        assert "yes" in svg
        assert "no" in svg

    def test_no_title(self):
        fd = FlowDiagram()
        fd.add_node("a", "A").add_node("b", "B")
        fd.add_edge("a", "b")
        svg = render_diagram(fd)
        assert "<svg" in svg

    def test_single_node(self):
        fd = FlowDiagram()
        fd.add_node("only", "Only Node")
        svg = render_diagram(fd)
        assert "Only Node" in svg

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            render_diagram(FlowDiagram())

    def test_all_node_kinds_render(self):
        fd = FlowDiagram()
        for kind in ("process", "decision", "terminal", "data", "io"):
            fd.add_node(kind, f"{kind.capitalize()} Node", kind=kind)
        svg = render_diagram(fd)
        for kind in ("process", "decision", "terminal", "data", "io"):
            assert kind.capitalize() in svg

    def test_dashed_edge_renders(self):
        fd = FlowDiagram()
        fd.add_node("a", "A").add_node("b", "B")
        fd.add_edge("a", "b", style="dashed")
        svg = render_diagram(fd)
        assert "stroke-dasharray" in svg

    def test_decision_diamond(self):
        fd = FlowDiagram()
        fd.add_node("d", "Decision?", kind="decision")
        svg = render_diagram(fd)
        assert "polygon" in svg

    def test_terminal_pill(self):
        fd = FlowDiagram()
        fd.add_node("t", "Start", kind="terminal")
        svg = render_diagram(fd)
        assert "rect" in svg

    def test_defs_contains_arrowhead(self):
        fd = FlowDiagram()
        fd.add_node("a", "A").add_node("b", "B")
        fd.add_edge("a", "b")
        svg = render_diagram(fd)
        assert "<defs>" in svg
        assert "marker" in svg

    def test_svg_dimensions_positive(self):
        import re
        fd = FlowDiagram()
        fd.add_node("a", "A").add_node("b", "B")
        fd.add_edge("a", "b")
        svg = render_diagram(fd)
        m = re.search(r'width="(\d+)" height="(\d+)"', svg)
        assert m
        assert int(m.group(1)) > 0
        assert int(m.group(2)) > 0

    def test_multi_level_layout(self):
        fd = FlowDiagram()
        for i in range(4):
            fd.add_node(str(i), f"Step {i}")
        for i in range(3):
            fd.add_edge(str(i), str(i + 1))
        svg = render_diagram(fd)
        for i in range(4):
            assert f"Step {i}" in svg

    def test_parallel_branches(self):
        fd = FlowDiagram()
        fd.add_node("root", "Root")
        fd.add_node("left", "Left Branch")
        fd.add_node("right", "Right Branch")
        fd.add_node("merge", "Merge")
        fd.add_edge("root", "left")
        fd.add_edge("root", "right")
        fd.add_edge("left", "merge")
        fd.add_edge("right", "merge")
        svg = render_diagram(fd)
        assert "Left Branch" in svg
        assert "Right Branch" in svg

    def test_unknown_edge_nodes_ignored(self):
        fd = FlowDiagram()
        fd.add_node("a", "A")
        fd.add_edge("a", "nonexistent")
        # Should not raise, just skip
        svg = render_diagram(fd)
        assert "A" in svg

    def test_long_label_wraps(self):
        fd = FlowDiagram()
        fd.add_node("a", "This Is A Very Long Node Label That Should Wrap")
        svg = render_diagram(fd)
        assert "<text" in svg

    def test_node_color_override(self):
        fd = FlowDiagram()
        fd.add_node("a", "Colored", color="#ff0000")
        svg = render_diagram(fd)
        assert "#ff0000" in svg


# ---------------------------------------------------------------------------
# SequenceDiagram — construction
# ---------------------------------------------------------------------------

class TestSequenceDiagramConstruction:
    def test_add_actor_returns_self(self):
        sd = SequenceDiagram()
        result = sd.add_actor("a", "Actor A")
        assert result is sd

    def test_add_message_returns_self(self):
        sd = SequenceDiagram()
        sd.add_actor("a", "A").add_actor("b", "B")
        result = sd.add_message("a", "b", "Hello")
        assert result is sd

    def test_actors_stored(self):
        sd = SequenceDiagram()
        sd.add_actor("u", "User").add_actor("s", "Server")
        assert len(sd._actors) == 2
        assert sd._actors[0].id == "u"
        assert sd._actors[1].label == "Server"

    def test_messages_stored(self):
        sd = SequenceDiagram()
        sd.add_actor("a", "A").add_actor("b", "B")
        sd.add_message("a", "b", "ping")
        assert len(sd._messages) == 1
        assert sd._messages[0].label == "ping"

    def test_actor_index_built(self):
        sd = SequenceDiagram()
        sd.add_actor("x", "X").add_actor("y", "Y")
        assert sd._actor_idx["x"] == 0
        assert sd._actor_idx["y"] == 1


# ---------------------------------------------------------------------------
# SequenceDiagram — rendering
# ---------------------------------------------------------------------------

class TestSequenceDiagramRendering:
    def _oauth(self):
        sd = SequenceDiagram(title="OAuth Flow")
        sd.add_actor("user", "User")
        sd.add_actor("app", "App")
        sd.add_actor("provider", "Provider")
        sd.add_message("user", "app", "Login")
        sd.add_message("app", "provider", "Redirect")
        sd.add_message("provider", "app", "Token", style="return")
        sd.add_message("app", "user", "Success")
        return sd

    def test_renders_svg(self):
        svg = render_diagram(self._oauth())
        assert svg.startswith("<svg")
        assert svg.strip().endswith("</svg>")

    def test_title_in_svg(self):
        svg = render_diagram(self._oauth())
        assert "OAuth Flow" in svg

    def test_actor_labels_in_svg(self):
        svg = render_diagram(self._oauth())
        assert "User" in svg
        assert "App" in svg
        assert "Provider" in svg

    def test_message_labels_in_svg(self):
        svg = render_diagram(self._oauth())
        assert "Login" in svg
        assert "Token" in svg

    def test_return_message_dashed(self):
        svg = render_diagram(self._oauth())
        assert "stroke-dasharray" in svg

    def test_lifelines_present(self):
        svg = render_diagram(self._oauth())
        # Lifelines are dashed vertical lines
        assert "stroke-dasharray" in svg

    def test_actor_boxes_top_and_bottom(self):
        sd = SequenceDiagram()
        sd.add_actor("a", "A").add_actor("b", "B")
        sd.add_message("a", "b", "msg")
        svg = render_diagram(sd)
        # Actors appear at both top and bottom — label appears twice
        assert svg.count(">A<") >= 2

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            render_diagram(SequenceDiagram())

    def test_no_title(self):
        sd = SequenceDiagram()
        sd.add_actor("a", "A").add_actor("b", "B")
        sd.add_message("a", "b", "hi")
        svg = render_diagram(sd)
        assert "<svg" in svg

    def test_self_message(self):
        sd = SequenceDiagram()
        sd.add_actor("a", "A")
        sd.add_message("a", "a", "loop", style="self")
        svg = render_diagram(sd)
        assert "loop" in svg
        assert "<path" in svg  # self-messages use path

    def test_single_actor(self):
        sd = SequenceDiagram()
        sd.add_actor("a", "Solo")
        svg = render_diagram(sd)
        assert "Solo" in svg

    def test_many_actors(self):
        sd = SequenceDiagram()
        for i in range(5):
            sd.add_actor(str(i), f"Actor{i}")
        sd.add_message("0", "4", "cross")
        svg = render_diagram(sd)
        for i in range(5):
            assert f"Actor{i}" in svg

    def test_svg_dimensions_positive(self):
        import re
        sd = self._oauth()
        svg = render_diagram(sd)
        m = re.search(r'width="(\d+)" height="(\d+)"', svg)
        assert m
        assert int(m.group(1)) > 0
        assert int(m.group(2)) > 0

    def test_defs_contain_markers(self):
        svg = render_diagram(self._oauth())
        assert "<defs>" in svg
        assert "marker" in svg

    def test_sync_style_default(self):
        sd = SequenceDiagram()
        sd.add_actor("a", "A").add_actor("b", "B")
        sd.add_message("a", "b", "req")
        msg = sd._messages[0]
        assert msg.style == "sync"


# ---------------------------------------------------------------------------
# render_diagram dispatch
# ---------------------------------------------------------------------------

class TestRenderDiagramDispatch:
    def test_flow_dispatches(self):
        fd = FlowDiagram()
        fd.add_node("a", "A")
        svg = render_diagram(fd)
        assert "<svg" in svg

    def test_sequence_dispatches(self):
        sd = SequenceDiagram()
        sd.add_actor("a", "A").add_actor("b", "B")
        sd.add_message("a", "b", "hi")
        svg = render_diagram(sd)
        assert "<svg" in svg

    def test_unknown_type_raises(self):
        with pytest.raises(TypeError, match="Unsupported diagram type"):
            render_diagram("not a diagram")

    def test_unknown_type_raises_for_dict(self):
        with pytest.raises(TypeError):
            render_diagram({})


# ---------------------------------------------------------------------------
# save_diagram
# ---------------------------------------------------------------------------

class TestSaveDiagram:
    def _simple_flow(self):
        fd = FlowDiagram()
        fd.add_node("a", "A").add_node("b", "B")
        fd.add_edge("a", "b")
        return fd

    def test_saves_file(self):
        fd = self._simple_flow()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.svg")
            result = save_diagram(fd, path)
            assert os.path.exists(path)
            assert result == path

    def test_file_contains_svg(self):
        fd = self._simple_flow()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.svg")
            save_diagram(fd, path)
            content = open(path).read()
            assert "<svg" in content

    def test_creates_parent_dirs(self):
        fd = self._simple_flow()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "dir", "out.svg")
            save_diagram(fd, path)
            assert os.path.exists(path)

    def test_returns_path(self):
        fd = self._simple_flow()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.svg")
            result = save_diagram(fd, path)
            assert result == path

    def test_sequence_saves(self):
        sd = SequenceDiagram()
        sd.add_actor("a", "A").add_actor("b", "B")
        sd.add_message("a", "b", "hi")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seq.svg")
            save_diagram(sd, path)
            assert os.path.exists(path)
