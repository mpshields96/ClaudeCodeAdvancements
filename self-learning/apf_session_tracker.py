#!/usr/bin/env python3
"""
apf_session_tracker.py — MT-27 Phase 5: APF trend tracking per session.

Records APF snapshots at each session wrap, enabling session-over-session
trend visibility. Answers: "Is our scanning getting smarter?"

Storage: Append-only JSONL at ~/.cca-apf-snapshots.jsonl
Each line: {session, timestamp, total, apf, build, adapt, by_frontier}

CLI:
    python3 apf_session_tracker.py snapshot S115    # Record current APF as S115
    python3 apf_session_tracker.py trend            # Show APF trend over sessions
    python3 apf_session_tracker.py status           # One-liner for wrap reports
    python3 apf_session_tracker.py json             # JSON output of all snapshots

Stdlib only. No external dependencies.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent dir for hit_rate_tracker import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hit_rate_tracker import parse_findings, compute_apf, compute_by_frontier

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FINDINGS_PATH = PROJECT_ROOT / "FINDINGS_LOG.md"
DEFAULT_SNAPSHOT_PATH = Path.home() / ".cca-apf-snapshots.jsonl"


def record_snapshot(
    session_id: str,
    findings_path: Path = DEFAULT_FINDINGS_PATH,
    snapshot_path: Path = DEFAULT_SNAPSHOT_PATH,
) -> dict:
    """Record current APF as a snapshot for this session.

    Appends one JSON line to the snapshot file. Append-only — never overwrites.
    """
    entries = parse_findings(findings_path)
    metrics = compute_apf(entries)
    by_frontier = compute_by_frontier(entries) if entries else {}

    snapshot = {
        "session": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": metrics.get("total", 0),
        "apf": metrics.get("apf", 0.0),
        "build": metrics.get("build", 0),
        "adapt": metrics.get("adapt", 0),
        "skip": metrics.get("skip", 0),
        "signal": metrics.get("signal", 0),
        "by_frontier": by_frontier,
    }

    with open(snapshot_path, "a") as f:
        f.write(json.dumps(snapshot) + "\n")

    return snapshot


def get_trend(snapshot_path: Path = DEFAULT_SNAPSHOT_PATH) -> list[dict]:
    """Read all snapshots and compute deltas.

    Returns list of snapshots with apf_delta added (None for first entry).
    Corrupt lines are silently skipped.
    """
    if not snapshot_path.exists():
        return []

    content = snapshot_path.read_text().strip()
    if not content:
        return []

    snapshots = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            snapshots.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # Add deltas
    for i, snap in enumerate(snapshots):
        if i == 0:
            snap["apf_delta"] = None
        else:
            prev_apf = snapshots[i - 1].get("apf", 0.0)
            snap["apf_delta"] = round(snap.get("apf", 0.0) - prev_apf, 1)

    return snapshots


def get_latest_snapshot(snapshot_path: Path = DEFAULT_SNAPSHOT_PATH) -> dict | None:
    """Return the most recent snapshot, or None if no snapshots exist."""
    trend = get_trend(snapshot_path)
    return trend[-1] if trend else None


def compact_status(snapshot_path: Path = DEFAULT_SNAPSHOT_PATH) -> str:
    """One-liner APF session status for wrap reports.

    Returns something like:
      APF Session: S115 22.7% (+1.7 vs S114) | 335 findings
    """
    trend = get_trend(snapshot_path)
    if not trend:
        return "APF Session: No snapshots recorded yet"

    latest = trend[-1]
    session = latest.get("session", "?")
    apf = latest.get("apf", 0.0)
    total = latest.get("total", 0)

    if latest.get("apf_delta") is not None and len(trend) >= 2:
        delta = latest["apf_delta"]
        prev_session = trend[-2].get("session", "?")
        sign = "+" if delta >= 0 else ""
        return f"APF Session: {session} {apf}% ({sign}{delta} vs {prev_session}) | {total} findings"

    return f"APF Session: {session} {apf}% | {total} findings"


def format_trend(trend: list[dict]) -> str:
    """Pretty-print the APF trend over sessions."""
    if not trend:
        return "No APF snapshots recorded yet. Run 'snapshot <session_id>' to start tracking."

    lines = ["APF Trend by Session:", ""]

    for snap in trend:
        session = snap.get("session", "?")
        apf = snap.get("apf", 0.0)
        total = snap.get("total", 0)
        delta = snap.get("apf_delta")

        # Visual bar
        bar = "#" * int(apf / 2.5) if apf > 0 else ""

        # Delta string
        if delta is not None:
            sign = "+" if delta >= 0 else ""
            delta_str = f" ({sign}{delta})"
        else:
            delta_str = ""

        lines.append(f"  {session:>6}: {apf:5.1f}%{delta_str:>10} | {total:4d} finds  {bar}")

    # Summary
    if len(trend) >= 2:
        first_apf = trend[0].get("apf", 0.0)
        last_apf = trend[-1].get("apf", 0.0)
        overall_delta = round(last_apf - first_apf, 1)
        sign = "+" if overall_delta >= 0 else ""
        lines.append("")
        lines.append(f"  Overall: {sign}{overall_delta}% across {len(trend)} sessions")

    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "trend"

    if cmd == "snapshot":
        if len(args) < 2:
            print("Usage: apf_session_tracker.py snapshot <session_id>")
            sys.exit(1)
        session_id = args[1]
        snap = record_snapshot(session_id)
        print(f"Recorded APF snapshot for {session_id}: {snap['apf']}% ({snap['total']} findings)")

    elif cmd == "trend":
        trend = get_trend()
        print(format_trend(trend))

    elif cmd == "status":
        print(compact_status())

    elif cmd == "json":
        trend = get_trend()
        print(json.dumps(trend, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: apf_session_tracker.py [snapshot <id>|trend|status|json]")
        sys.exit(1)


if __name__ == "__main__":
    main()
