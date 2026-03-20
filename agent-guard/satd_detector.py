#!/usr/bin/env python3
"""SATD Detector — MT-20 Senior Dev Agent: Self-Admitted Technical Debt marker detection.

PostToolUse hook that scans Write/Edit tool content for SATD markers and surfaces them
as additionalContext so Claude is aware of technical debt being introduced.

SATD markers: TODO, FIXME, HACK, WORKAROUND, DEBT, XXX, NOTE
Severity: FIXME/HACK/WORKAROUND/DEBT = HIGH; TODO/XXX = MEDIUM; NOTE = LOW
"""

import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# File extensions to skip (non-code files where TODO comments are normal prose)
SKIP_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".txt", ".rst", ".toml", ".ini", ".cfg"}

# Max additionalContext length to avoid overwhelming Claude
MAX_CONTEXT_LENGTH = 1800


class SATDLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


# Marker type -> severity mapping
_MARKER_LEVELS = {
    "FIXME": SATDLevel.HIGH,
    "HACK": SATDLevel.HIGH,
    "WORKAROUND": SATDLevel.HIGH,
    "DEBT": SATDLevel.HIGH,
    "TODO": SATDLevel.MEDIUM,
    "XXX": SATDLevel.MEDIUM,
    "NOTE": SATDLevel.LOW,
}

# Regex: match any SATD marker (case-insensitive), capture the full line fragment
_SATD_PATTERN = re.compile(
    r"\b(TODO|FIXME|HACK|WORKAROUND|DEBT|XXX|NOTE)\b[:\s]",
    re.IGNORECASE,
)


@dataclass
class SATDMarker:
    line: int
    text: str
    marker_type: str
    level: SATDLevel

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "text": self.text,
            "marker_type": self.marker_type,
            "level": self.level.name,
        }


class SATDDetector:
    def scan(self, content: str) -> list:
        """Scan raw content for SATD markers. Returns list of SATDMarker."""
        if not content:
            return []

        markers = []
        for lineno, line in enumerate(content.splitlines(), start=1):
            m = _SATD_PATTERN.search(line)
            if m:
                marker_type = m.group(1).upper()
                level = _MARKER_LEVELS.get(marker_type, SATDLevel.LOW)
                markers.append(SATDMarker(
                    line=lineno,
                    text=line.strip(),
                    marker_type=marker_type,
                    level=level,
                ))
        return markers

    def scan_file_content(self, content: str, file_path: str = "") -> list:
        """Scan content, skipping non-code file types."""
        if file_path:
            ext = _get_extension(file_path)
            if ext in SKIP_EXTENSIONS:
                return []
        return self.scan(content)

    def hook_output(self, content: str, file_path: str = "") -> dict:
        """
        Produce PostToolUse hook output dict.
        Returns {} if no markers, or {"additionalContext": "..."} if markers found.
        """
        markers = self.scan_file_content(content, file_path=file_path)
        if not markers:
            return {}

        # Sort by severity (HIGH first), then line number
        markers_sorted = sorted(markers, key=lambda m: (-m.level.value, m.line))

        lines = ["SATD markers detected in this file:"]
        for m in markers_sorted:
            lines.append(f"  Line {m.line} [{m.level.name}] {m.text}")

        context = "\n".join(lines)

        # Truncate if too long (many markers)
        if len(context) > MAX_CONTEXT_LENGTH:
            # Keep header + as many HIGH markers as fit, then truncate notice
            high_markers = [m for m in markers_sorted if m.level == SATDLevel.HIGH]
            medium_markers = [m for m in markers_sorted if m.level == SATDLevel.MEDIUM]

            trunc_lines = ["SATD markers detected (showing highest severity):"]
            for m in high_markers:
                trunc_lines.append(f"  Line {m.line} [{m.level.name}] {m.text}")
            if medium_markers:
                trunc_lines.append(f"  ... and {len(medium_markers)} TODO/XXX markers (MEDIUM severity)")

            context = "\n".join(trunc_lines)
            if len(context) > MAX_CONTEXT_LENGTH:
                context = context[:MAX_CONTEXT_LENGTH - 3] + "..."

        return {"additionalContext": context}


def _get_extension(file_path: str) -> str:
    """Return lowercase file extension including dot, or '' if none."""
    if "." not in file_path.split("/")[-1]:
        return ""
    return "." + file_path.rsplit(".", 1)[-1].lower()


def main():
    """PostToolUse hook entry point. Reads stdin JSON, outputs hook response JSON."""
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({}))
            return

        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({}))
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    # Only scan Write and Edit tools
    if tool_name == "Write":
        content = tool_input.get("content", "")
        file_path = tool_input.get("file_path", "")
    elif tool_name == "Edit":
        content = tool_input.get("new_string", "")
        file_path = tool_input.get("file_path", "")
    else:
        print(json.dumps({}))
        return

    if not content:
        print(json.dumps({}))
        return

    detector = SATDDetector()
    output = detector.hook_output(content, file_path=file_path)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
