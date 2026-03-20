#!/usr/bin/env python3
"""Tech Debt Tracker — MT-20 Full Vision: SATD trend analysis.

Scans a codebase for SATD markers, stores historical snapshots as JSONL,
and identifies hotspot modules (files with growing or persistent technical debt).

Usage:
  python3 tech_debt_tracker.py scan /path/to/project
  python3 tech_debt_tracker.py report
  python3 tech_debt_tracker.py hotspots [--top N]
"""

import datetime
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Add parent dir for satd_detector import
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

try:
    from satd_detector import SATDDetector
    _satd_available = True
except ImportError:
    _satd_available = False

# File extensions to scan
_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".hpp", ".rb", ".php", ".cs", ".swift", ".kt", ".scala", ".sh",
    ".bash", ".zsh", ".fish",
}

# Skip extensions (prose/config, not code)
_SKIP_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".txt", ".rst", ".toml",
                    ".ini", ".cfg", ".lock", ".sum"}

# Default db path
DEFAULT_DB_PATH = os.path.expanduser("~/.cca-tech-debt.jsonl")

# Trend thresholds
_INCREASE_THRESHOLD = 1   # more than this many new markers = increasing
_DECREASE_THRESHOLD = -1  # fewer than this many = decreasing


@dataclass
class DebtSnapshot:
    timestamp: str
    file_path: str
    markers: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "file_path": self.file_path,
            "markers": self.markers,
            "marker_count": len(self.markers),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DebtSnapshot":
        return cls(
            timestamp=d.get("timestamp", ""),
            file_path=d.get("file_path", ""),
            markers=d.get("markers", []),
        )


@dataclass
class HotspotFile:
    file_path: str
    current_count: int
    trend: str  # "increasing" | "stable" | "decreasing" | "new"

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "current_count": self.current_count,
            "trend": self.trend,
        }


class TechDebtTracker:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        if _satd_available:
            self._detector = SATDDetector()
        else:
            self._detector = None

    def scan_directory(self, directory: str) -> list:
        """Scan all code files in directory for SATD markers. Returns list of DebtSnapshot."""
        snapshots = []
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for root, dirs, files in os.walk(directory):
            # Skip hidden dirs and common non-code dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and
                       d not in {"node_modules", "__pycache__", ".venv", "venv", "vendor"}]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in _CODE_EXTENSIONS:
                    continue
                if ext in _SKIP_EXTENSIONS:
                    continue

                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except OSError:
                    continue

                markers = self._scan_content(content, fpath)
                # Only create snapshot if there are markers (reduces noise)
                if markers:
                    snapshots.append(DebtSnapshot(
                        timestamp=timestamp,
                        file_path=fpath,
                        markers=markers,
                    ))

        return snapshots

    def _scan_content(self, content: str, file_path: str) -> list:
        """Scan content for SATD markers, return list of dicts."""
        if self._detector is not None:
            markers = self._detector.scan_file_content(content, file_path=file_path)
            return [m.to_dict() for m in markers]
        # Fallback: simple regex scan
        import re
        pattern = re.compile(r"\b(TODO|FIXME|HACK|WORKAROUND|DEBT|XXX|NOTE)\b", re.IGNORECASE)
        results = []
        for lineno, line in enumerate(content.splitlines(), start=1):
            m = pattern.search(line)
            if m:
                results.append({
                    "line": lineno,
                    "type": m.group(1).upper(),
                    "text": line.strip(),
                })
        return results

    def save_snapshots(self, snapshots: list) -> None:
        """Append snapshots to the JSONL db file."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with open(self.db_path, "a", encoding="utf-8") as f:
            for s in snapshots:
                f.write(json.dumps(s.to_dict()) + "\n")

    def load_history(self, file_path: Optional[str] = None) -> list:
        """Load snapshot history from JSONL db. Optionally filter by file_path."""
        if not os.path.exists(self.db_path):
            return []

        snapshots = []
        with open(self.db_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    s = DebtSnapshot.from_dict(d)
                    if file_path is None or s.file_path == file_path:
                        snapshots.append(s)
                except (json.JSONDecodeError, KeyError):
                    continue

        # Sort oldest first
        snapshots.sort(key=lambda s: s.timestamp)
        return snapshots

    def get_hotspots(self, top_n: int = 10) -> list:
        """
        Identify hotspot files from snapshot history.
        Returns list of HotspotFile sorted by current_count descending, limited to top_n.
        """
        all_history = self.load_history()
        if not all_history:
            return []

        # Group by file_path
        by_file: dict = {}
        for s in all_history:
            by_file.setdefault(s.file_path, []).append(s)

        hotspots = []
        for fpath, snapshots in by_file.items():
            # Sort by timestamp
            snapshots.sort(key=lambda s: s.timestamp)
            current = len(snapshots[-1].markers)

            if len(snapshots) == 1:
                trend = "new"
            else:
                prev = len(snapshots[-2].markers)
                delta = current - prev
                if delta > _INCREASE_THRESHOLD:
                    trend = "increasing"
                elif delta < _DECREASE_THRESHOLD:
                    trend = "decreasing"
                else:
                    trend = "stable"

            if current > 0:
                hotspots.append(HotspotFile(
                    file_path=fpath,
                    current_count=current,
                    trend=trend,
                ))

        # Sort by current count descending
        hotspots.sort(key=lambda h: h.current_count, reverse=True)
        return hotspots[:top_n]

    def generate_report(self, top_n: int = 10) -> str:
        """Generate a human-readable summary report of tech debt."""
        hotspots = self.get_hotspots(top_n=top_n)
        all_history = self.load_history()

        if not all_history:
            return "Tech Debt Report: No history yet. Run scan first."

        total_markers = sum(len(s.markers) for s in all_history
                            if s.timestamp == max(s.timestamp for s in all_history))

        lines = [
            "=== Tech Debt Tracker Report ===",
            f"Total SATD markers (latest scan): {total_markers}",
            f"Hotspot files ({len(hotspots)}):",
        ]
        for h in hotspots:
            trend_arrow = {"increasing": "↑", "decreasing": "↓", "stable": "→", "new": "★"}.get(h.trend, "?")
            lines.append(f"  {trend_arrow} {h.file_path}: {h.current_count} markers ({h.trend})")

        return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Tech Debt Tracker")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Scan directory for SATD")
    scan_p.add_argument("directory", help="Directory to scan")
    scan_p.add_argument("--db", default=DEFAULT_DB_PATH, help="DB file path")

    report_p = sub.add_parser("report", help="Generate report")
    report_p.add_argument("--db", default=DEFAULT_DB_PATH, help="DB file path")
    report_p.add_argument("--top", type=int, default=10, help="Top N hotspots")

    hotspots_p = sub.add_parser("hotspots", help="Show hotspot files")
    hotspots_p.add_argument("--db", default=DEFAULT_DB_PATH, help="DB file path")
    hotspots_p.add_argument("--top", type=int, default=10, help="Top N hotspots")

    args = parser.parse_args()

    if args.command == "scan":
        tracker = TechDebtTracker(db_path=args.db)
        snapshots = tracker.scan_directory(args.directory)
        tracker.save_snapshots(snapshots)
        total = sum(len(s.markers) for s in snapshots)
        print(f"Scanned {len(snapshots)} files with debt. Total markers: {total}")
        print(f"Saved to {args.db}")

    elif args.command in ("report", "hotspots"):
        tracker = TechDebtTracker(db_path=args.db)
        if args.command == "report":
            print(tracker.generate_report(top_n=args.top))
        else:
            hotspots = tracker.get_hotspots(top_n=args.top)
            for h in hotspots:
                print(json.dumps(h.to_dict()))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
