"""trace_analyzer.py — MT-7: Transcript JSONL pattern analysis.

Parses Claude Code session transcripts and detects inefficiency patterns:
- RetryDetector: same tool on same file 3+ consecutive times
- WasteDetector: Read calls whose file is never referenced in the next 20 entries
- EfficiencyCalculator: unique files / total tool calls ratio
- VelocityCalculator: commits + file creates per 100 tool calls

Usage:
    python3 trace_analyzer.py <path/to/session.jsonl>
    python3 trace_analyzer.py <path> --json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metric_config import get_metric

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOISE_TYPES = {"progress", "queue-operation"}
ORIENTATION_FILES = {
    "CLAUDE.md", "SESSION_STATE.md", "PROJECT_INDEX.md",
    "MASTER_ROADMAP.md", "ROADMAP.md",
}
WASTE_WINDOW = get_metric("trace_analyzer.waste_window", 20)


# ---------------------------------------------------------------------------
# TranscriptEntry
# ---------------------------------------------------------------------------

class TranscriptEntry:
    """Parse one JSONL line from a Claude Code transcript.

    Exposes clean attributes regardless of the raw entry shape:
    - type: str ("user", "assistant", "progress", "system", "queue-operation", ...)
    - tool_name: str | None — name of tool called (assistant entries only)
    - file_path: str | None — file_path input arg if present
    - command: str | None — command input arg (Bash)
    - is_error: bool — True if any tool_result content has is_error=True
    - usage: dict | None — token usage from assistant entries
    - is_noise: bool — True for progress/queue-operation entries
    - is_orientation: bool — True if this is a Read of a session-start orientation file
    - uuid: str | None
    - timestamp: datetime | None
    """

    def __init__(self, raw: dict):
        self._raw = raw
        self.type: str = raw.get("type", "")
        self.uuid: Optional[str] = raw.get("uuid")

        ts = raw.get("timestamp")
        self.timestamp: Optional[datetime] = self._parse_ts(ts)

        message = raw.get("message") or {}
        content = message.get("content") or []

        # Detect tool call (assistant with tool_use content block)
        self.tool_name: Optional[str] = None
        self.file_path: Optional[str] = None
        self.command: Optional[str] = None
        self.usage: Optional[dict] = None

        if self.type == "assistant":
            self.usage = message.get("usage")
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    self.tool_name = block.get("name")
                    inp = block.get("input") or {}
                    self.file_path = inp.get("file_path")
                    self.command = inp.get("command")
                    break

        # Detect is_error from tool_result content blocks
        self.is_error: bool = False
        if self.type == "user" and raw.get("toolUseResult") is not None:
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    if block.get("is_error"):
                        self.is_error = True
                        break

        self.is_noise: bool = self.type in NOISE_TYPES

        # Orientation read: Read of a known session-start file
        self.is_orientation: bool = (
            self.tool_name == "Read"
            and self.file_path is not None
            and Path(self.file_path).name in ORIENTATION_FILES
        )

    @staticmethod
    def _parse_ts(ts_str: Optional[str]) -> Optional[datetime]:
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None


# ---------------------------------------------------------------------------
# TranscriptSession
# ---------------------------------------------------------------------------

class TranscriptSession:
    """Load a .jsonl file and provide filtered views.

    - all_entries: every entry (including noise)
    - signal_entries: noise filtered out
    - tool_calls: assistant entries with a tool_name
    - unique_files: set of all file_path values referenced
    - total_output_tokens: sum of output_tokens across all assistant entries
    - session_id: first sessionId found
    """

    def __init__(self, path: str):
        self._path = path
        self.all_entries: list[TranscriptEntry] = []
        self.session_id: Optional[str] = None

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry = TranscriptEntry(raw)
                self.all_entries.append(entry)
                if self.session_id is None:
                    self.session_id = raw.get("sessionId")

        self.signal_entries: list[TranscriptEntry] = [
            e for e in self.all_entries if not e.is_noise
        ]
        self.tool_calls: list[TranscriptEntry] = [
            e for e in self.signal_entries if e.tool_name is not None
        ]
        self.unique_files: set[str] = {
            e.file_path for e in self.tool_calls if e.file_path
        }
        self.total_output_tokens: int = sum(
            (e.usage or {}).get("output_tokens", 0)
            for e in self.signal_entries
            if e.usage
        )


# ---------------------------------------------------------------------------
# RetryDetector
# ---------------------------------------------------------------------------

class RetryDetector:
    """Detect retry loops: same tool on same file 3+ consecutive times.

    Thresholds: 3-4 = minor, 5-7 = major, 8+ = critical.
    error_confirmed = True if intervening tool_results have is_error=True.
    """

    MINOR = get_metric("trace_analyzer.retry_minor", 3)
    MAJOR = get_metric("trace_analyzer.retry_major", 5)
    CRITICAL = get_metric("trace_analyzer.retry_critical", 8)

    def detect(self, session: TranscriptSession) -> dict:
        retries = []
        entries = session.signal_entries

        i = 0
        while i < len(entries):
            entry = entries[i]
            if not entry.tool_name or not entry.file_path:
                i += 1
                continue

            # Count consecutive same-tool same-file
            tool = entry.tool_name
            fp = entry.file_path
            run = [i]
            j = i + 1
            error_confirmed = False

            while j < len(entries):
                nxt = entries[j]
                if nxt.is_error:
                    error_confirmed = True
                    j += 1
                    continue
                if nxt.tool_name == tool and nxt.file_path == fp:
                    run.append(j)
                    j += 1
                elif nxt.tool_name is None:
                    # tool result or text — skip, keep scanning
                    j += 1
                else:
                    break

            count = len(run)
            if count >= self.MINOR:
                if count >= self.CRITICAL:
                    severity = "critical"
                elif count >= self.MAJOR:
                    severity = "major"
                else:
                    severity = "minor"
                retries.append({
                    "file": fp,
                    "tool": tool,
                    "count": count,
                    "severity": severity,
                    "error_confirmed": error_confirmed,
                    "start_index": i,
                })
                i = run[-1] + 1
            else:
                i += 1

        return {"retries": retries, "total_retries": len(retries)}


# ---------------------------------------------------------------------------
# WasteDetector
# ---------------------------------------------------------------------------

class WasteDetector:
    """Detect Read calls whose file is never referenced in the next WASTE_WINDOW entries.

    Orientation reads (CLAUDE.md, SESSION_STATE.md, etc.) are always exempt.
    waste_rate = wasted_reads / total_reads (0.0 to 1.0).
    """

    def detect(self, session: TranscriptSession) -> dict:
        entries = session.signal_entries
        wasted = []
        total_reads = 0

        for idx, entry in enumerate(entries):
            if entry.tool_name != "Read" or not entry.file_path:
                continue
            if entry.is_orientation:
                continue

            total_reads += 1
            fp = entry.file_path
            fp_name = Path(fp).name

            # Forward-scan WASTE_WINDOW signal entries for any reference to fp
            window = entries[idx + 1: idx + 1 + WASTE_WINDOW]
            referenced = False
            for later in window:
                if later.file_path and (later.file_path == fp or Path(later.file_path).name == fp_name):
                    referenced = True
                    break
                if later.command and fp_name in later.command:
                    referenced = True
                    break

            if not referenced:
                wasted.append({"file": fp, "position": idx})

        waste_rate = len(wasted) / total_reads if total_reads > 0 else 0.0
        return {
            "wasted_reads": wasted,
            "total_reads": total_reads,
            "waste_rate": waste_rate,
        }


# ---------------------------------------------------------------------------
# EfficiencyCalculator
# ---------------------------------------------------------------------------

class EfficiencyCalculator:
    """Unique files touched / total tool calls.

    Thresholds (from real-data analysis):
    - good: ratio > 0.3
    - mediocre: 0.1 <= ratio <= 0.3
    - poor: ratio < 0.1
    """

    def calculate(self, session: TranscriptSession) -> dict:
        total = len(session.tool_calls)
        if total == 0:
            return {"ratio": None, "rating": "unknown", "unique_files": 0, "total_calls": 0}

        unique = len(session.unique_files)
        ratio = unique / total

        if ratio > 0.3:
            rating = "good"
        elif ratio >= 0.1:
            rating = "mediocre"
        else:
            rating = "poor"

        return {
            "ratio": round(ratio, 3),
            "rating": rating,
            "unique_files": unique,
            "total_calls": total,
        }


# ---------------------------------------------------------------------------
# VelocityCalculator
# ---------------------------------------------------------------------------

class VelocityCalculator:
    """Commits + file creates per 100 tool calls (velocity_pct).

    Commits: detected by Bash input containing "git commit".
    File creates: detected by Write tool calls.
    """

    def calculate(self, session: TranscriptSession) -> dict:
        commits = 0
        file_creates = 0

        for entry in session.tool_calls:
            if entry.tool_name == "Bash" and entry.command:
                if "git commit" in entry.command:
                    commits += 1
            elif entry.tool_name == "Write":
                file_creates += 1

        deliverables = commits + file_creates
        total_calls = len(session.tool_calls)
        velocity_pct = (deliverables / total_calls * 100) if total_calls > 0 else 0.0

        return {
            "commits": commits,
            "file_creates": file_creates,
            "deliverables": deliverables,
            "total_calls": total_calls,
            "velocity_pct": round(velocity_pct, 2),
        }


# ---------------------------------------------------------------------------
# TraceAnalyzer — orchestrator
# ---------------------------------------------------------------------------

class TraceAnalyzer:
    """Orchestrate all detectors and produce a structured JSON report.

    Score: 0-100 composite quality score.
    - Starts at 100
    - Each critical retry: -20, major: -10, minor: -5
    - Waste rate > 50%: -20, > 30%: -10
    - Efficiency poor: -15, mediocre: -5
    - No deliverables (>10 tool calls): -10

    Recommendations: human-readable list of suggested improvements.
    """

    def __init__(self, path: str):
        self._path = path

    def analyze(self) -> dict:
        session = TranscriptSession(self._path)

        retry_result = RetryDetector().detect(session)
        waste_result = WasteDetector().detect(session)
        efficiency_result = EfficiencyCalculator().calculate(session)
        velocity_result = VelocityCalculator().calculate(session)

        score = 100
        recommendations = []

        # Retry penalties
        for r in retry_result["retries"]:
            if r["severity"] == "critical":
                score -= 20
                recommendations.append(
                    f"Critical retry loop on {r['file']} ({r['count']} calls) — "
                    "read error output before retrying"
                )
            elif r["severity"] == "major":
                score -= 10
                recommendations.append(
                    f"Major retry loop on {r['file']} ({r['count']} calls) — "
                    "consider reading file state before retrying"
                )
            else:
                score -= 5
                recommendations.append(
                    f"Minor retry on {r['file']} ({r['count']} calls)"
                )

        # Waste penalties
        waste_rate = waste_result["waste_rate"]
        if waste_rate > 0.5:
            score -= 20
            recommendations.append(
                f"High read waste ({waste_rate:.0%}) — "
                f"{len(waste_result['wasted_reads'])} reads never referenced"
            )
        elif waste_rate > 0.3:
            score -= 10
            recommendations.append(
                f"Moderate read waste ({waste_rate:.0%}) — "
                "read files only when needed"
            )

        # Efficiency penalties
        if efficiency_result["rating"] == "poor":
            score -= 15
            recommendations.append(
                f"Low tool efficiency (ratio {efficiency_result['ratio']}) — "
                "many tool calls on few files; reduce redundant reads"
            )
        elif efficiency_result["rating"] == "mediocre":
            score -= 5

        # Velocity penalty
        if velocity_result["total_calls"] > 10 and velocity_result["deliverables"] == 0:
            score -= 10
            recommendations.append(
                "No commits or file creates despite significant tool usage — "
                "commit progress incrementally"
            )

        score = max(0, score)

        return {
            "session_id": session.session_id,
            "score": score,
            "retries": retry_result,
            "waste": waste_result,
            "efficiency": efficiency_result,
            "velocity": velocity_result,
            "recommendations": recommendations,
            "total_entries": len(session.all_entries),
            "signal_entries": len(session.signal_entries),
            "noise_filtered": len(session.all_entries) - len(session.signal_entries),
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _print_report(report: dict, as_json: bool = False):
    if as_json:
        print(json.dumps(report, indent=2))
        return

    print(f"\nTrace Analysis Report")
    print(f"Session: {report['session_id'] or 'unknown'}")
    print(f"Score:   {report['score']}/100")
    print(f"Entries: {report['total_entries']} total, {report['noise_filtered']} noise filtered")
    print()

    eff = report["efficiency"]
    print(f"Efficiency:  {eff['rating']} (ratio {eff['ratio']}, "
          f"{eff['unique_files']} files / {eff['total_calls']} calls)")

    v = report["velocity"]
    print(f"Velocity:    {v['velocity_pct']:.1f}% "
          f"({v['commits']} commits, {v['file_creates']} creates / {v['total_calls']} calls)")

    waste = report["waste"]
    print(f"Read waste:  {waste['waste_rate']:.0%} "
          f"({len(waste['wasted_reads'])}/{waste['total_reads']} reads unused)")

    retries = report["retries"]
    print(f"Retries:     {retries['total_retries']} loops detected")

    if report["recommendations"]:
        print("\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"  - {rec}")
    else:
        print("\nNo issues detected.")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 trace_analyzer.py <session.jsonl> [--json]")
        sys.exit(1)

    path = sys.argv[1]
    as_json = "--json" in sys.argv

    if not Path(path).exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    report = TraceAnalyzer(path).analyze()
    _print_report(report, as_json=as_json)
