#!/usr/bin/env python3
"""
batch_report.py — Aggregate trace analysis across multiple sessions.

Reads all .jsonl transcript files from a directory, runs TraceAnalyzer on each,
and produces an aggregate health report with:
- Score distribution (excellent/good/poor/critical)
- Retry hotspots (files causing retries across multiple sessions)
- Waste statistics (average read waste)
- Actionable recommendations

Usage:
    python3 batch_report.py [DIRECTORY]           # Text report (default: CCA transcripts)
    python3 batch_report.py [DIRECTORY] --json     # JSON output

Stdlib only. No external dependencies.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent))

from trace_analyzer import TraceAnalyzer


# Default transcript directory for CCA
DEFAULT_DIR = os.path.expanduser(
    "~/.claude/projects/-Users-matthewshields-Projects-ClaudeCodeAdvancements/"
)


class BatchReport:
    """Aggregate trace analysis across multiple sessions."""

    def __init__(self, directory: str):
        self._dir = directory
        self._result = None

    def analyze(self) -> dict:
        """Run TraceAnalyzer on every .jsonl in the directory. Return aggregate."""
        scores = []
        waste_rates = []
        retry_files = {}
        errors = 0

        # Only top-level .jsonl files (skip subagent dirs)
        for fname in sorted(os.listdir(self._dir)):
            if not fname.endswith(".jsonl"):
                continue
            path = os.path.join(self._dir, fname)
            if not os.path.isfile(path):
                continue

            try:
                report = TraceAnalyzer(path).analyze()
                scores.append(report["score"])

                # Waste
                waste = report.get("waste", {})
                total_reads = waste.get("total_reads", 0)
                if total_reads > 0:
                    waste_rates.append(waste.get("waste_rate", 0))

                # Retries
                retries = report.get("retries", {}).get("retries", [])
                for loop in retries:
                    fname_key = loop.get("file", "unknown")
                    # Shorten paths
                    if "ClaudeCodeAdvancements/" in fname_key:
                        fname_key = fname_key.split("ClaudeCodeAdvancements/")[-1]
                    retry_files[fname_key] = retry_files.get(fname_key, 0) + 1
            except Exception:
                errors += 1

        n = len(scores)
        if n == 0:
            self._result = {
                "sessions_analyzed": 0,
                "errors": errors,
                "score_avg": 0,
                "score_min": 0,
                "score_max": 0,
                "score_distribution": {
                    "excellent": 0, "good": 0, "poor": 0, "critical": 0,
                },
                "waste_avg": 0,
                "waste_max": 0,
                "retry_hotspots": [],
                "recommendations": [],
            }
            return self._result

        # Score distribution
        dist = {
            "excellent": sum(1 for s in scores if s >= 80),
            "good": sum(1 for s in scores if 60 <= s < 80),
            "poor": sum(1 for s in scores if 40 <= s < 60),
            "critical": sum(1 for s in scores if s < 40),
        }

        # Retry hotspots (sorted by frequency)
        hotspots = [
            {"file": f, "sessions": c}
            for f, c in sorted(retry_files.items(), key=lambda x: -x[1])
        ]

        # Waste stats
        waste_avg = sum(waste_rates) / len(waste_rates) if waste_rates else 0
        waste_max = max(waste_rates) if waste_rates else 0

        # Recommendations
        recs = []
        if hotspots:
            top = hotspots[0]
            if top["sessions"] >= n * 0.3:
                recs.append(
                    f"CRITICAL: {top['file']} causes retries in {top['sessions']}/{n} sessions "
                    f"({top['sessions']/n:.0%}). Consider caching or reducing edit frequency."
                )
        if waste_avg > 0.4:
            recs.append(
                f"High average read waste ({waste_avg:.0%}). "
                "Read files only when you will reference them within the next 20 tool calls."
            )
        if dist["critical"] > n * 0.15:
            recs.append(
                f"{dist['critical']}/{n} sessions scored critically. "
                "Review those sessions for systemic issues."
            )

        self._result = {
            "sessions_analyzed": n,
            "errors": errors,
            "score_avg": round(sum(scores) / n, 1),
            "score_min": min(scores),
            "score_max": max(scores),
            "score_median": sorted(scores)[n // 2],
            "score_distribution": dist,
            "waste_avg": round(waste_avg, 3),
            "waste_max": round(waste_max, 3),
            "retry_hotspots": hotspots[:10],
            "recommendations": recs,
        }
        return self._result

    def text_report(self) -> str:
        """Format the aggregate as a human-readable text report."""
        if self._result is None:
            self.analyze()
        r = self._result
        n = r["sessions_analyzed"]
        if n == 0:
            return "No sessions found to analyze."

        lines = [
            f"=== Batch Trace Report ({n} sessions) ===",
            "",
            f"Score: avg={r['score_avg']}, min={r['score_min']}, max={r['score_max']}, "
            f"median={r.get('score_median', 'N/A')}",
            "",
            "Distribution:",
            f"  Excellent (80+): {r['score_distribution']['excellent']}",
            f"  Good (60-79):    {r['score_distribution']['good']}",
            f"  Poor (40-59):    {r['score_distribution']['poor']}",
            f"  Critical (<40):  {r['score_distribution']['critical']}",
            "",
            f"Read waste: avg={r['waste_avg']:.0%}, max={r['waste_max']:.0%}",
            "",
        ]

        if r["retry_hotspots"]:
            lines.append("Retry hotspots:")
            for h in r["retry_hotspots"][:5]:
                pct = h["sessions"] / n * 100
                lines.append(f"  {h['file']}: {h['sessions']}/{n} sessions ({pct:.0f}%)")
            lines.append("")

        if r["recommendations"]:
            lines.append("Recommendations:")
            for rec in r["recommendations"]:
                lines.append(f"  - {rec}")
            lines.append("")

        if r["errors"]:
            lines.append(f"Errors: {r['errors']} sessions failed to parse")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate trace analysis across multiple sessions."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=DEFAULT_DIR,
        help="Directory containing .jsonl transcript files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of text",
    )
    args = parser.parse_args()

    report = BatchReport(args.directory)
    result = report.analyze()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(report.text_report())


if __name__ == "__main__":
    main()
