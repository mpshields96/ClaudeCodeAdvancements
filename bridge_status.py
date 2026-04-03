#!/usr/bin/env python3
"""bridge_status.py - tri-chat communication health for CCA/Codex/Kalshi.

Usage:
    python3 bridge_status.py
    python3 bridge_status.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable


DEFAULT_CCA_ROOT = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
DEFAULT_POLYBOT_ROOT = "/Users/matthewshields/Projects/polymarket-bot"
DEFAULT_CROSS_CHAT_DIR = os.path.expanduser("~/.claude/cross-chat")

HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@dataclass
class LaneStatus:
    name: str
    path: str
    exists: bool
    modified_at: str | None
    age_hours: float | None
    latest_heading: str | None


@dataclass
class BridgeStatus:
    lanes: list[LaneStatus]
    attention: list[str]
    overall: str


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _extract_latest_heading(text: str) -> str | None:
    matches = HEADING_RE.findall(text)
    if not matches:
        return None
    return matches[-1].strip()


def _lane_status(name: str, path: str, now: datetime) -> LaneStatus:
    if not os.path.exists(path):
        return LaneStatus(name, path, False, None, None, None)

    stat = os.stat(path)
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    try:
        text = _read_text(path)
    except OSError:
        text = ""

    return LaneStatus(
        name=name,
        path=path,
        exists=True,
        modified_at=modified.isoformat(),
        age_hours=round((now - modified).total_seconds() / 3600.0, 2),
        latest_heading=_extract_latest_heading(text),
    )


def _find_lane(lanes: Iterable[LaneStatus], name: str) -> LaneStatus | None:
    for lane in lanes:
        if lane.name == name:
            return lane
    return None


def _format_age(age_hours: float | None) -> str:
    if age_hours is None:
        return "n/a"
    if age_hours < 1:
        return f"{int(age_hours * 60)}m"
    if age_hours < 48:
        return f"{age_hours:.1f}h"
    return f"{age_hours / 24.0:.1f}d"


def build_attention(
    lanes: list[LaneStatus],
    stale_hours: float = 48.0,
    response_gap_hours: float = 12.0,
) -> list[str]:
    items: list[str] = []

    for lane in lanes:
        if not lane.exists:
            items.append(f"{lane.name}: missing")
            continue
        if lane.age_hours is not None and lane.age_hours > stale_hours:
            items.append(f"{lane.name}: stale ({_format_age(lane.age_hours)} old)")

    polybot_to_cca = _find_lane(lanes, "Kalshi -> CCA")
    cca_to_polybot = _find_lane(lanes, "CCA -> Kalshi")
    if (
        polybot_to_cca
        and cca_to_polybot
        and polybot_to_cca.exists
        and cca_to_polybot.exists
        and polybot_to_cca.age_hours is not None
        and cca_to_polybot.age_hours is not None
    ):
        lag = cca_to_polybot.age_hours - polybot_to_cca.age_hours
        if lag > response_gap_hours:
            items.append(
                f"Kalshi -> CCA is newer than CCA -> Kalshi by {lag:.1f}h; reply/relay may be pending"
            )

    codex_obs = _find_lane(lanes, "Kalshi -> Codex")
    codex_to_cca = _find_lane(lanes, "Codex -> CCA")
    if (
        codex_obs
        and codex_to_cca
        and codex_obs.exists
        and codex_to_cca.exists
        and codex_obs.age_hours is not None
        and codex_to_cca.age_hours is not None
    ):
        lag = codex_to_cca.age_hours - codex_obs.age_hours
        if lag > response_gap_hours:
            items.append(
                f"Kalshi -> Codex is newer than Codex -> CCA by {lag:.1f}h; CCA relay may be lagging"
            )

    return items


def collect_bridge_status(
    cca_root: str = DEFAULT_CCA_ROOT,
    polybot_root: str = DEFAULT_POLYBOT_ROOT,
    cross_chat_dir: str = DEFAULT_CROSS_CHAT_DIR,
    stale_hours: float = 48.0,
    response_gap_hours: float = 12.0,
    now: datetime | None = None,
) -> BridgeStatus:
    now = now or datetime.now(timezone.utc)
    lanes = [
        _lane_status("CCA -> Codex", os.path.join(cca_root, "CLAUDE_TO_CODEX.md"), now),
        _lane_status("Codex -> CCA", os.path.join(cca_root, "CODEX_TO_CLAUDE.md"), now),
        _lane_status("CCA -> Kalshi", os.path.join(cross_chat_dir, "CCA_TO_POLYBOT.md"), now),
        _lane_status("Kalshi -> CCA", os.path.join(cross_chat_dir, "POLYBOT_TO_CCA.md"), now),
        _lane_status("Kalshi -> Codex", os.path.join(polybot_root, "CODEX_OBSERVATIONS.md"), now),
    ]
    attention = build_attention(
        lanes,
        stale_hours=stale_hours,
        response_gap_hours=response_gap_hours,
    )
    overall = "healthy" if not attention else "attention"
    return BridgeStatus(lanes=lanes, attention=attention, overall=overall)


def format_report(status: BridgeStatus) -> str:
    lines = [
        f"3-WAY BRIDGE STATUS: {status.overall.upper()}",
        "",
        "Lane freshness:",
    ]
    for lane in status.lanes:
        heading = lane.latest_heading or "no heading found"
        state = "missing" if not lane.exists else _format_age(lane.age_hours)
        lines.append(f"- {lane.name}: {state}")
        lines.append(f"  Path: {lane.path}")
        lines.append(f"  Latest: {heading}")

    lines.append("")
    lines.append("Attention:")
    if not status.attention:
        lines.append("- none")
    else:
        for item in status.attention:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show tri-chat bridge freshness and likely relay gaps.")
    parser.add_argument("--cca-root", default=DEFAULT_CCA_ROOT, help="CCA repo root.")
    parser.add_argument("--polybot-root", default=DEFAULT_POLYBOT_ROOT, help="Polybot repo root.")
    parser.add_argument("--cross-chat-dir", default=DEFAULT_CROSS_CHAT_DIR, help="Cross-chat dir.")
    parser.add_argument("--stale-hours", type=float, default=48.0, help="Age threshold for stale lanes.")
    parser.add_argument(
        "--response-gap-hours",
        type=float,
        default=12.0,
        help="Age gap threshold for likely pending relay/reply.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args(argv)

    status = collect_bridge_status(
        cca_root=args.cca_root,
        polybot_root=args.polybot_root,
        cross_chat_dir=args.cross_chat_dir,
        stale_hours=args.stale_hours,
        response_gap_hours=args.response_gap_hours,
    )

    if args.json:
        payload = {
            "overall": status.overall,
            "lanes": [asdict(lane) for lane in status.lanes],
            "attention": status.attention,
        }
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(format_report(status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
