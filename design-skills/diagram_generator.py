#!/usr/bin/env python3
"""Diagram generator — MT-32 Phase 6.

Generates flow diagrams and sequence diagrams as publication-quality SVG.
No external dependencies — pure stdlib + CCA design tokens.

Supported diagram types:
- FlowDiagram: nodes + directed edges → flowchart (processes, decisions, terminals)
- SequenceDiagram: actors + messages → UML sequence diagram

Usage:
    from design_skills.diagram_generator import (
        FlowDiagram, SequenceDiagram, render_diagram, save_diagram
    )

    # Flow diagram
    fd = FlowDiagram(title="Request Flow")
    fd.add_node("start", "Start", kind="terminal")
    fd.add_node("auth", "Authenticate", kind="process")
    fd.add_node("ok", "Authorized?", kind="decision")
    fd.add_node("handle", "Handle Request", kind="process")
    fd.add_node("deny", "Return 401", kind="process")
    fd.add_edge("start", "auth")
    fd.add_edge("auth", "ok")
    fd.add_edge("ok", "handle", label="yes")
    fd.add_edge("ok", "deny", label="no")
    svg = render_diagram(fd)
    save_diagram(fd, "request_flow.svg")

    # Sequence diagram
    sd = SequenceDiagram(title="OAuth Flow")
    sd.add_actor("user", "User")
    sd.add_actor("app", "App")
    sd.add_actor("auth", "Auth Provider")
    sd.add_message("user", "app", "Click Login")
    sd.add_message("app", "auth", "Redirect →")
    sd.add_message("auth", "app", "Token ←", style="return")
    svg = render_diagram(sd)
"""

import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from chart_generator import _escape, SVG_NS, FONT_FAMILY, CCA_COLORS

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

DIAGRAM_BG = CCA_COLORS["background"]
DIAGRAM_BORDER = CCA_COLORS["border"]
DIAGRAM_TEXT = CCA_COLORS["dark"]
DIAGRAM_PRIMARY = CCA_COLORS["primary"]
DIAGRAM_MUTED = CCA_COLORS["muted"]
DIAGRAM_SUCCESS = CCA_COLORS["success"]
DIAGRAM_WARNING = CCA_COLORS["warning"]

NODE_KINDS = {"process", "decision", "terminal", "data", "io"}


# ===========================================================================
# FLOW DIAGRAM
# ===========================================================================

@dataclass
class FlowNode:
    """A node in a flow diagram."""
    id: str
    label: str
    kind: str = "process"   # process | decision | terminal | data | io
    color: Optional[str] = None  # override fill color


@dataclass
class FlowEdge:
    """A directed edge between two flow nodes."""
    src: str
    dst: str
    label: Optional[str] = None
    style: str = "normal"   # normal | dashed


@dataclass
class FlowDiagram:
    """Flow / flowchart diagram."""
    title: Optional[str] = None
    direction: str = "top-down"  # top-down | left-right
    node_width: int = 140
    node_height: int = 44
    h_gap: int = 60    # horizontal gap between nodes at same level
    v_gap: int = 50    # vertical gap between levels

    _nodes: Dict[str, FlowNode] = field(default_factory=dict, repr=False)
    _edges: List[FlowEdge] = field(default_factory=list, repr=False)

    def add_node(self, id: str, label: str, kind: str = "process",
                 color: Optional[str] = None) -> "FlowDiagram":
        """Add a node. kind: process | decision | terminal | data | io."""
        if kind not in NODE_KINDS:
            raise ValueError(f"Unknown node kind '{kind}'. Use: {NODE_KINDS}")
        self._nodes[id] = FlowNode(id=id, label=label, kind=kind, color=color)
        return self

    def add_edge(self, src: str, dst: str, label: Optional[str] = None,
                 style: str = "normal") -> "FlowDiagram":
        """Add a directed edge src → dst."""
        self._edges.append(FlowEdge(src=src, dst=dst, label=label, style=style))
        return self


# ---------------------------------------------------------------------------
# Flow layout engine
# ---------------------------------------------------------------------------

def _flow_levels(diagram: FlowDiagram) -> Dict[str, int]:
    """Assign each node a level (row) using longest-path layering."""
    nodes = list(diagram._nodes.keys())
    # Build adjacency and in-degree
    successors: Dict[str, List[str]] = {n: [] for n in nodes}
    predecessors: Dict[str, List[str]] = {n: [] for n in nodes}
    for e in diagram._edges:
        if e.src in successors and e.dst in predecessors:
            successors[e.src].append(e.dst)
            predecessors[e.dst].append(e.src)

    # Longest-path level assignment (handles cycles by ignoring back-edges)
    level: Dict[str, int] = {}
    visited = set()

    def assign(node: str, depth: int) -> None:
        if node not in level or level[node] < depth:
            level[node] = depth
        if node in visited:
            return
        visited.add(node)
        for s in successors[node]:
            assign(s, depth + 1)

    roots = [n for n in nodes if not predecessors[n]]
    if not roots:
        roots = nodes[:1]  # fallback: first node

    for r in roots:
        assign(r, 0)

    # Ensure all nodes have a level (disconnected nodes get level 0)
    for n in nodes:
        if n not in level:
            level[n] = 0

    return level


def _flow_positions(diagram: FlowDiagram) -> Dict[str, Tuple[float, float]]:
    """Compute (cx, cy) center positions for each node."""
    levels = _flow_levels(diagram)
    nw = diagram.node_width
    nh = diagram.node_height
    hg = diagram.h_gap
    vg = diagram.v_gap

    # Group nodes by level
    by_level: Dict[int, List[str]] = {}
    for node_id, lv in levels.items():
        by_level.setdefault(lv, []).append(node_id)

    # Sort within level by insertion order
    insertion_order = list(diagram._nodes.keys())
    for lv in by_level:
        by_level[lv].sort(key=lambda n: insertion_order.index(n))

    max_count = max(len(v) for v in by_level.values())
    total_width = max_count * nw + (max_count - 1) * hg

    pos: Dict[str, Tuple[float, float]] = {}
    for lv, node_ids in sorted(by_level.items()):
        count = len(node_ids)
        row_width = count * nw + (count - 1) * hg
        x_start = (total_width - row_width) / 2 + nw / 2
        cy = lv * (nh + vg) + nh / 2

        for i, nid in enumerate(node_ids):
            cx = x_start + i * (nw + hg)
            pos[nid] = (cx, cy)

    return pos


def _render_flow_node(node: FlowNode, cx: float, cy: float,
                      nw: int, nh: int) -> str:
    """Render a single flow node to SVG."""
    x = cx - nw / 2
    y = cy - nh / 2
    label = _escape(node.label)

    fill = node.color or {
        "process": CCA_COLORS["background"],
        "decision": "#fff8e1",
        "terminal": DIAGRAM_PRIMARY,
        "data": "#e8f4f8",
        "io": "#e8f4f8",
    }.get(node.kind, CCA_COLORS["background"])

    text_fill = "white" if node.kind == "terminal" else DIAGRAM_TEXT
    stroke = DIAGRAM_PRIMARY

    parts = []
    if node.kind == "terminal":
        # Rounded rectangle (pill)
        r = nh / 2
        parts.append(
            f'<rect x="{x}" y="{y}" width="{nw}" height="{nh}" '
            f'rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>\n'
        )
    elif node.kind == "decision":
        # Diamond
        pts = (
            f"{cx},{y} "         # top
            f"{x + nw},{cy} "   # right
            f"{cx},{y + nh} "   # bottom
            f"{x},{cy}"          # left
        )
        parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>\n'
        )
    elif node.kind in ("data", "io"):
        # Parallelogram
        skew = 10
        pts = (
            f"{x + skew},{y} "
            f"{x + nw},{y} "
            f"{x + nw - skew},{y + nh} "
            f"{x},{y + nh}"
        )
        parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>\n'
        )
    else:
        # Rectangle
        parts.append(
            f'<rect x="{x}" y="{y}" width="{nw}" height="{nh}" '
            f'rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>\n'
        )

    # Label (wrap at ~18 chars)
    words = node.label.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 > 18 and current:
            lines.append(current.strip())
            current = w
        else:
            current += " " + w
    if current:
        lines.append(current.strip())

    line_h = 14
    y_text_start = cy - (len(lines) - 1) * line_h / 2
    for i, line in enumerate(lines):
        ty = y_text_start + i * line_h
        parts.append(
            f'<text x="{cx}" y="{ty + 4}" font-family="{FONT_FAMILY}" '
            f'font-size="11" fill="{text_fill}" text-anchor="middle" '
            f'dominant-baseline="middle">{_escape(line)}</text>\n'
        )

    return "".join(parts)


def _edge_attach_points(src_id: str, dst_id: str,
                        pos: Dict[str, Tuple[float, float]],
                        nw: int, nh: int) -> Tuple[float, float, float, float]:
    """Compute edge start/end points on node boundaries."""
    sx, sy = pos[src_id]
    dx, dy = pos[dst_id]

    # Determine which face to exit/enter based on direction
    if abs(dy - sy) >= abs(dx - sx):
        # Vertical dominant
        if dy > sy:
            return sx, sy + nh / 2, dx, dy - nh / 2  # bottom → top
        else:
            return sx, sy - nh / 2, dx, dy + nh / 2  # top → bottom
    else:
        # Horizontal dominant
        if dx > sx:
            return sx + nw / 2, sy, dx - nw / 2, dy  # right → left
        else:
            return sx - nw / 2, sy, dx + nw / 2, dy  # left → right


def render_flow_diagram(diagram: FlowDiagram) -> str:
    """Render a FlowDiagram to SVG string."""
    if not diagram._nodes:
        raise ValueError("FlowDiagram has no nodes")

    pos = _flow_positions(diagram)
    nw = diagram.node_width
    nh = diagram.node_height
    pad = 40
    title_h = 36 if diagram.title else 0

    # Compute canvas bounds
    xs = [cx for cx, _ in pos.values()]
    ys = [cy for _, cy in pos.values()]
    min_x = min(xs) - nw / 2
    max_x = max(xs) + nw / 2
    min_y = min(ys) - nh / 2
    max_y = max(ys) + nh / 2

    canvas_w = (max_x - min_x) + 2 * pad
    canvas_h = (max_y - min_y) + 2 * pad + title_h

    # Offset to center content in canvas
    ox = pad - min_x
    oy = pad + title_h - min_y

    parts = [
        f'<svg xmlns="{SVG_NS}" width="{canvas_w:.0f}" height="{canvas_h:.0f}" '
        f'viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}">\n',
        f'<rect width="{canvas_w:.0f}" height="{canvas_h:.0f}" fill="{DIAGRAM_BG}"/>\n',
        # Arrowhead defs
        '<defs>\n',
        '<marker id="fa" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">\n',
        f'  <polygon points="0 0, 8 3, 0 6" fill="{DIAGRAM_PRIMARY}"/>\n',
        '</marker>\n',
        '<marker id="fa-dash" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">\n',
        f'  <polygon points="0 0, 8 3, 0 6" fill="{DIAGRAM_MUTED}"/>\n',
        '</marker>\n',
        '</defs>\n',
    ]

    if diagram.title:
        parts.append(
            f'<text x="{canvas_w / 2}" y="22" font-family="{FONT_FAMILY}" '
            f'font-size="14" font-weight="bold" fill="{DIAGRAM_PRIMARY}" '
            f'text-anchor="middle">{_escape(diagram.title)}</text>\n'
        )

    # Draw edges first (under nodes)
    for edge in diagram._edges:
        if edge.src not in pos or edge.dst not in pos:
            continue
        x1, y1, x2, y2 = _edge_attach_points(edge.src, edge.dst, pos, nw, nh)
        x1 += ox; y1 += oy; x2 += ox; y2 += oy

        marker = "fa-dash" if edge.style == "dashed" else "fa"
        dash = 'stroke-dasharray="6,3"' if edge.style == "dashed" else ""
        color = DIAGRAM_MUTED if edge.style == "dashed" else DIAGRAM_PRIMARY

        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="1.5" {dash} '
            f'marker-end="url(#{marker})"/>\n'
        )

        if edge.label:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2 - 6
            parts.append(
                f'<text x="{mx:.1f}" y="{my:.1f}" font-family="{FONT_FAMILY}" '
                f'font-size="9" fill="{DIAGRAM_MUTED}" text-anchor="middle">'
                f'{_escape(edge.label)}</text>\n'
            )

    # Draw nodes
    for nid, node in diagram._nodes.items():
        cx, cy = pos[nid]
        parts.append(_render_flow_node(node, cx + ox, cy + oy, nw, nh))

    parts.append('</svg>\n')
    return "".join(parts)


# ===========================================================================
# SEQUENCE DIAGRAM
# ===========================================================================

@dataclass
class SequenceActor:
    """A participant in a sequence diagram."""
    id: str
    label: str


@dataclass
class SequenceMessage:
    """A message between two actors."""
    src: str
    dst: str
    label: str
    style: str = "sync"  # sync | async | return | self


@dataclass
class SequenceDiagram:
    """UML-style sequence diagram."""
    title: Optional[str] = None
    actor_width: int = 110
    actor_height: int = 36
    h_gap: int = 80       # gap between actor columns
    v_gap: int = 42       # gap between messages

    _actors: List[SequenceActor] = field(default_factory=list, repr=False)
    _actor_idx: Dict[str, int] = field(default_factory=dict, repr=False)
    _messages: List[SequenceMessage] = field(default_factory=list, repr=False)

    def add_actor(self, id: str, label: str) -> "SequenceDiagram":
        """Add a participant actor."""
        idx = len(self._actors)
        self._actors.append(SequenceActor(id=id, label=label))
        self._actor_idx[id] = idx
        return self

    def add_message(self, src: str, dst: str, label: str,
                    style: str = "sync") -> "SequenceDiagram":
        """Add a message arrow from src to dst."""
        self._messages.append(SequenceMessage(src=src, dst=dst, label=label, style=style))
        return self


def render_sequence_diagram(diagram: SequenceDiagram) -> str:
    """Render a SequenceDiagram to SVG string."""
    if not diagram._actors:
        raise ValueError("SequenceDiagram has no actors")

    aw = diagram.actor_width
    ah = diagram.actor_height
    hg = diagram.h_gap
    vg = diagram.v_gap
    pad = 20
    title_h = 32 if diagram.title else 0

    n_actors = len(diagram._actors)
    n_messages = len(diagram._messages)

    # Actor center X positions
    actor_cx = [pad + aw / 2 + i * (aw + hg) for i in range(n_actors)]
    canvas_w = actor_cx[-1] + aw / 2 + pad if actor_cx else 200
    lifeline_start = pad + ah
    lifeline_end = lifeline_start + (n_messages + 1) * vg
    canvas_h = lifeline_end + ah + pad + title_h  # bottom actor boxes

    parts = [
        f'<svg xmlns="{SVG_NS}" width="{canvas_w:.0f}" height="{canvas_h:.0f}" '
        f'viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}">\n',
        f'<rect width="{canvas_w:.0f}" height="{canvas_h:.0f}" fill="{DIAGRAM_BG}"/>\n',
        '<defs>\n',
        # Sync arrow (filled)
        '<marker id="sa" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">\n',
        f'  <polygon points="0 0, 8 3, 0 6" fill="{DIAGRAM_PRIMARY}"/>\n',
        '</marker>\n',
        # Return arrow (open)
        '<marker id="ra" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">\n',
        f'  <polyline points="0 0, 8 3, 0 6" fill="none" stroke="{DIAGRAM_MUTED}" stroke-width="1"/>\n',
        '</marker>\n',
        '</defs>\n',
    ]

    top_y = pad + title_h

    if diagram.title:
        parts.append(
            f'<text x="{canvas_w / 2}" y="{pad + 14}" font-family="{FONT_FAMILY}" '
            f'font-size="13" font-weight="bold" fill="{DIAGRAM_PRIMARY}" '
            f'text-anchor="middle">{_escape(diagram.title)}</text>\n'
        )

    # Render actor boxes (top)
    for i, actor in enumerate(diagram._actors):
        cx = actor_cx[i]
        x = cx - aw / 2
        y = top_y
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{aw}" height="{ah}" '
            f'rx="4" fill="{DIAGRAM_PRIMARY}" stroke="{DIAGRAM_PRIMARY}"/>\n'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{y + ah / 2 + 4:.1f}" font-family="{FONT_FAMILY}" '
            f'font-size="11" font-weight="bold" fill="white" text-anchor="middle">'
            f'{_escape(actor.label)}</text>\n'
        )

    # Lifelines
    ll_top = top_y + ah
    ll_bottom = canvas_h - ah - pad
    for i in range(n_actors):
        cx = actor_cx[i]
        parts.append(
            f'<line x1="{cx:.1f}" y1="{ll_top:.1f}" x2="{cx:.1f}" y2="{ll_bottom:.1f}" '
            f'stroke="{DIAGRAM_BORDER}" stroke-width="1" stroke-dasharray="4,3"/>\n'
        )

    # Messages
    for msg_i, msg in enumerate(diagram._messages):
        si = diagram._actor_idx.get(msg.src, 0)
        di = diagram._actor_idx.get(msg.dst, 0)
        sx = actor_cx[si]
        dx = actor_cx[di]
        my = ll_top + (msg_i + 1) * vg

        is_return = msg.style == "return"
        is_self = msg.src == msg.dst
        color = DIAGRAM_MUTED if is_return else DIAGRAM_PRIMARY
        dash = 'stroke-dasharray="5,3"' if is_return else ""
        marker = "ra" if is_return else "sa"

        if is_self:
            # Self-message: small loop to the right
            loop_x = sx + aw / 2 + 20
            parts.append(
                f'<path d="M {sx:.1f} {my:.1f} L {loop_x:.1f} {my:.1f} '
                f'L {loop_x:.1f} {my + 16:.1f} L {sx:.1f} {my + 16:.1f}" '
                f'fill="none" stroke="{color}" stroke-width="1.5" {dash} '
                f'marker-end="url(#{marker})"/>\n'
            )
            parts.append(
                f'<text x="{loop_x + 4:.1f}" y="{my + 10:.1f}" font-family="{FONT_FAMILY}" '
                f'font-size="9" fill="{color}" text-anchor="start">'
                f'{_escape(msg.label)}</text>\n'
            )
        else:
            # Normal message
            # Shorten arrows slightly so they don't overlap actor boxes
            arrow_margin = 4
            if dx > sx:
                x1, x2 = sx + arrow_margin, dx - arrow_margin
            else:
                x1, x2 = sx - arrow_margin, dx + arrow_margin

            parts.append(
                f'<line x1="{x1:.1f}" y1="{my:.1f}" x2="{x2:.1f}" y2="{my:.1f}" '
                f'stroke="{color}" stroke-width="1.5" {dash} '
                f'marker-end="url(#{marker})"/>\n'
            )

            # Label above the arrow, centered
            lx = (x1 + x2) / 2
            ly = my - 5
            parts.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" font-family="{FONT_FAMILY}" '
                f'font-size="9" fill="{color}" text-anchor="middle">'
                f'{_escape(msg.label)}</text>\n'
            )

    # Actor boxes (bottom)
    for i, actor in enumerate(diagram._actors):
        cx = actor_cx[i]
        x = cx - aw / 2
        y = canvas_h - ah - pad
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{aw}" height="{ah}" '
            f'rx="4" fill="{DIAGRAM_PRIMARY}" stroke="{DIAGRAM_PRIMARY}"/>\n'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{y + ah / 2 + 4:.1f}" font-family="{FONT_FAMILY}" '
            f'font-size="11" font-weight="bold" fill="white" text-anchor="middle">'
            f'{_escape(actor.label)}</text>\n'
        )

    parts.append('</svg>\n')
    return "".join(parts)


# ===========================================================================
# Unified API
# ===========================================================================

def render_diagram(diagram) -> str:
    """Render any supported diagram type to SVG string.

    Args:
        diagram: FlowDiagram or SequenceDiagram instance.

    Returns:
        SVG string.

    Raises:
        TypeError: if diagram type is not supported.
    """
    if isinstance(diagram, FlowDiagram):
        return render_flow_diagram(diagram)
    elif isinstance(diagram, SequenceDiagram):
        return render_sequence_diagram(diagram)
    else:
        raise TypeError(f"Unsupported diagram type: {type(diagram).__name__}")


def save_diagram(diagram, path: str) -> str:
    """Render diagram and save to SVG file.

    Creates parent directories if needed.

    Args:
        diagram: FlowDiagram or SequenceDiagram.
        path: Output path (.svg).

    Returns:
        Path written to.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    svg = render_diagram(diagram)
    with open(path, "w") as f:
        f.write(svg)
    return path
