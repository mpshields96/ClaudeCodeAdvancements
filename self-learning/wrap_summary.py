#!/usr/bin/env python3
"""wrap_summary.py — MT-49 unified self-learning health snapshot for session wrap.

Aggregates output from meta_tracker, confidence_recalibrator, and principle_discoverer
into a single concise summary line for the /cca-wrap ritual.

Usage:
    python3 self-learning/wrap_summary.py [--session N] [--json]

Output format (text):
    Self-Learning [S228]: 186 principles (20 active) | 5 auto-discovered |
    Recal: 20 decayed | Meta: 0.76 health | Research ROI: 11/79

Output format (--json):
    {"session": 228, "principles": {...}, "recalibration": {...}, ...}

Stdlib only. No external dependencies.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent


def _run(cmd: list[str], cwd: str = None) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=cwd or str(PROJECT_ROOT), timeout=15
        )
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return ""


def _parse_int(text: str, keyword: str) -> int:
    """Extract integer after 'keyword: N' or 'keyword N' pattern."""
    import re
    # Try "keyword: N" pattern first
    m = re.search(rf"{re.escape(keyword)}[:\s]+(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 0


def gather_principle_stats(session: int) -> dict:
    """Get principle counts from meta_learning_dashboard --brief."""
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from meta_learning_dashboard import PrincipleAnalyzer
        p = PrincipleAnalyzer(str(SCRIPT_DIR / "principles.jsonl"))
        return {
            "total": p.total_principles,
            "active": p.active_principles,
            "pruned": p.pruned_principles,
            "avg_score": round(p.average_score, 3),
        }
    except Exception as e:
        return {"total": 0, "active": 0, "pruned": 0, "avg_score": 0.0, "error": str(e)}


def gather_discoverer_stats() -> dict:
    """Get auto-discovery counts from principle_discoverer status."""
    output = _run([
        sys.executable, str(SCRIPT_DIR / "principle_discoverer.py"), "status"
    ])
    if not output:
        return {"total": 0, "auto_discovered": 0}
    total = _parse_int(output, "Total principles")
    auto = _parse_int(output, "Auto-discovered")
    return {"total": total, "auto_discovered": auto}


def gather_recalibration_stats(session: int) -> dict:
    """Get staleness info from confidence_recalibrator summary."""
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from confidence_recalibrator import recalibrate_all, recalibration_summary
        results = recalibrate_all(current_session=session)
        summary = recalibration_summary(results)
        return {
            "total": summary["total"],
            "decayed": summary["decayed"],
            "stable": summary["stable"],
        }
    except Exception as e:
        return {"total": 0, "decayed": 0, "stable": 0, "error": str(e)}


def gather_meta_health() -> dict:
    """Get meta-learning health score from meta_tracker."""
    output = _run([
        sys.executable, str(SCRIPT_DIR / "meta_tracker.py"), "health"
    ])
    if not output:
        return {"health_score": 0.0, "active": 0, "zombies": 0}
    import re
    health_m = re.search(r"Health score:\s+([\d.]+)", output)
    active_m = re.search(r"Active \(used >= 1\):\s+(\d+)", output)
    zombie_m = re.search(r"Zombies.*?:\s+(\d+)", output)
    return {
        "health_score": float(health_m.group(1)) if health_m else 0.0,
        "active": int(active_m.group(1)) if active_m else 0,
        "zombies": int(zombie_m.group(1)) if zombie_m else 0,
    }


def gather_research_roi() -> dict:
    """Get research ROI summary from research_roi_resolver."""
    output = _run([
        sys.executable, str(SCRIPT_DIR / "research_roi_resolver.py"), "summary"
    ])
    if not output:
        return {"total": 0, "resolved": 0}
    try:
        data = json.loads(output)
        return {
            "total": data.get("Deliveries", 0),
            "resolved": data.get("Resolved", 0),
        }
    except (json.JSONDecodeError, KeyError):
        # Try text parsing
        total = _parse_int(output, "Deliveries")
        resolved = _parse_int(output, "Resolved")
        return {"total": total, "resolved": resolved}


def build_summary(session: int) -> dict:
    """Build full summary dict from all MT-49 subsystems."""
    return {
        "session": session,
        "principles": gather_principle_stats(session),
        "discovery": gather_discoverer_stats(),
        "recalibration": gather_recalibration_stats(session),
        "meta_health": gather_meta_health(),
        "research_roi": gather_research_roi(),
    }


def format_summary(data: dict) -> str:
    """Format summary as a single concise line."""
    s = data["session"]
    p = data["principles"]
    d = data["discovery"]
    r = data["recalibration"]
    m = data["meta_health"]
    roi = data["research_roi"]

    parts = [
        f"{p['total']} principles ({p['active']} active, avg {p['avg_score']:.2f})",
        f"{d['auto_discovered']} auto-discovered",
        f"Recal: {r['decayed']} decayed/{r['total']} total",
        f"Meta health: {m['health_score']:.2f}",
        f"ROI: {roi['resolved']}/{roi['total']} resolved",
    ]
    return f"Self-Learning [S{s}]: " + " | ".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="MT-49 unified self-learning wrap summary"
    )
    parser.add_argument("--session", type=int, default=0,
                        help="Current session number")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    args = parser.parse_args()

    data = build_summary(args.session)

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_summary(data))


if __name__ == "__main__":
    main()
