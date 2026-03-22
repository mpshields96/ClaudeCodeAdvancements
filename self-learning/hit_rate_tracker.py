#!/usr/bin/env python3
"""
hit_rate_tracker.py — MT-12 Phase 6: Discovery pipeline hit rate tracker.

Computes APF (Actionable Per Find) and related metrics from FINDINGS_LOG.md.
APF = (BUILD + ADAPT) / total findings * 100

This is CCA's research efficiency scoreboard. Higher APF = smarter scanning.

CLI:
    python3 hit_rate_tracker.py                # Full report
    python3 hit_rate_tracker.py apf            # Just the APF number
    python3 hit_rate_tracker.py by-frontier    # Breakdown by frontier
    python3 hit_rate_tracker.py trend          # APF trend over time (by date)
    python3 hit_rate_tracker.py json           # JSON output

Stdlib only. No external dependencies.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINDINGS_LOG_PATH = PROJECT_ROOT / "FINDINGS_LOG.md"

VALID_VERDICTS = {"BUILD", "ADAPT", "REFERENCE", "REFERENCE-PERSONAL", "SKIP"}

# Frontier patterns from findings log format
# Order matters: more specific patterns checked first, fallback categories last.
# Case-insensitive matching via re.IGNORECASE.
FRONTIER_PATTERNS = {
    # Core frontiers (most specific)
    "Frontier 1: Memory": re.compile(r"Frontier 1|Memory", re.IGNORECASE),
    "Frontier 2: Spec": re.compile(r"Frontier 2|Spec", re.IGNORECASE),
    "Frontier 3: Context": re.compile(r"Frontier 3|Context", re.IGNORECASE),
    "Frontier 4: Agent Guard": re.compile(r"Frontier 4|Agent.?Guard|AGENT.?GUARD", re.IGNORECASE),
    "Frontier 5: Dashboard": re.compile(r"Frontier 5|Dashboard|Usage", re.IGNORECASE),
    # Kalshi/trading (catch all trading variants)
    "MT-0 Kalshi": re.compile(
        r"MT-0|Kalshi|trading|POLYBOT|Prediction Market|polymarket|algotrading",
        re.IGNORECASE,
    ),
    # Named MTs
    "MT-20 Senior Dev": re.compile(r"MT-20|Senior Dev", re.IGNORECASE),
    "MT-21 Hivemind": re.compile(r"MT-21|Hivemind", re.IGNORECASE),
    # Anthropic official announcements/features
    "Anthropic/Official": re.compile(
        r"Official Feature|Anthropic|Claude Update|CC Feature", re.IGNORECASE,
    ),
    # Cross-cutting (touches multiple frontiers)
    "Cross-Cutting": re.compile(
        r"All Frontiers|Multiple Frontiers|Cross.?Cutting|Multi.?Frontier",
        re.IGNORECASE,
    ),
    # Skip/noise bucket (clearly non-actionable)
    "Skip/Noise": re.compile(
        r"No frontier|OFF.?SCOPE|Meme|Humor|Novelty|Outage|Rant"
        r"|r/ClaudeAI$|r/AutoGPT|r/iOSProgramming|r/MachineLearning|r/webdev"
        r"|AI-Generated|Sentiment only|Comparison",
        re.IGNORECASE,
    ),
    # Personal/misc (not frontier-specific but personally useful)
    "Personal/Misc": re.compile(
        r"Academic|Personal|Psychiatry|UI Wrapper|reddit-intelligence"
        r"|Voice|ADHD|Finance.*Showcase",
        re.IGNORECASE,
    ),
    # Catch-all for other MT-X references (MT-1, MT-8, MT-10, MT-11, MT-13, MT-17, etc.)
    "Other MTs": re.compile(r"MT-\d+|AG-\d+", re.IGNORECASE),
    # Generic tags that don't fit elsewhere
    "General/NEW": re.compile(r"^General|^NEW$|Education|Meta-awareness", re.IGNORECASE),
    # Agent/research patterns (cross-cutting but code-relevant)
    "Agent/Research": re.compile(
        r"Agent Pattern|Research Agent|MCP orchestrat|Code Quality|Security$"
        r"|Self-Learning",
        re.IGNORECASE,
    ),
}


def parse_findings(log_path: Path = FINDINGS_LOG_PATH) -> list[dict]:
    """Parse FINDINGS_LOG.md into structured entries.

    Each entry starts with a date [YYYY-MM-DD] and verdict [VERDICT].
    """
    if not log_path.exists():
        return []

    entries = []
    content = log_path.read_text()

    # Pattern: [date] [VERDICT] [frontier] "title" (score, comments, subreddit)
    line_pattern = re.compile(
        r"^\[(\d{4}-\d{2}-\d{2})\]\s+\[([A-Z\-]+)\]\s+\[([^\]]*)\]\s+(.*)",
        re.MULTILINE,
    )

    for m in line_pattern.finditer(content):
        date = m.group(1)
        verdict = m.group(2)
        frontier_tag = m.group(3)
        rest = m.group(4)

        if verdict not in VALID_VERDICTS:
            continue

        # Extract title (in quotes)
        title_m = re.search(r'"([^"]+)"', rest)
        title = title_m.group(1) if title_m else rest[:60]

        # Extract score
        score_m = re.search(r"\((\d+)pts?", rest)
        score = int(score_m.group(1)) if score_m else 0

        entries.append({
            "date": date,
            "verdict": verdict,
            "frontier": frontier_tag,
            "title": title,
            "score": score,
        })

    return entries


def compute_apf(entries: list[dict]) -> dict:
    """Compute APF and breakdown metrics."""
    if not entries:
        return {"total": 0, "apf": 0.0}

    verdict_counts = Counter(e["verdict"] for e in entries)
    total = len(entries)

    build = verdict_counts.get("BUILD", 0)
    adapt = verdict_counts.get("ADAPT", 0)
    reference = verdict_counts.get("REFERENCE", 0)
    ref_personal = verdict_counts.get("REFERENCE-PERSONAL", 0)
    skip = verdict_counts.get("SKIP", 0)

    signal = build + adapt
    apf = round(signal / total * 100, 1) if total > 0 else 0.0
    useful_rate = round((signal + reference) / total * 100, 1) if total > 0 else 0.0

    return {
        "total": total,
        "build": build,
        "adapt": adapt,
        "reference": reference,
        "reference_personal": ref_personal,
        "skip": skip,
        "signal": signal,
        "apf": apf,
        "useful_rate": useful_rate,
    }


def compute_by_frontier(entries: list[dict]) -> dict[str, dict]:
    """Compute APF broken down by frontier/MT."""
    by_frontier = defaultdict(list)

    for entry in entries:
        frontier_tag = entry["frontier"]
        matched = False
        for name, pattern in FRONTIER_PATTERNS.items():
            if pattern.search(frontier_tag):
                by_frontier[name].append(entry)
                matched = True
                break
        if not matched:
            by_frontier["Other"].append(entry)

    return {name: compute_apf(ents) for name, ents in sorted(by_frontier.items())}


def compute_trend(entries: list[dict], window: int = 7) -> list[dict]:
    """Compute APF trend grouped by date, with rolling window.

    Returns list of {date, daily_apf, rolling_apf, daily_count}.
    """
    by_date = defaultdict(list)
    for entry in entries:
        by_date[entry["date"]].append(entry)

    dates = sorted(by_date.keys())
    trend = []

    for i, date in enumerate(dates):
        daily = compute_apf(by_date[date])

        # Rolling window
        window_start = max(0, i - window + 1)
        window_entries = []
        for d in dates[window_start:i + 1]:
            window_entries.extend(by_date[d])
        rolling = compute_apf(window_entries)

        trend.append({
            "date": date,
            "daily_count": daily["total"],
            "daily_apf": daily["apf"],
            "rolling_apf": rolling["apf"],
            "rolling_window": len(dates[window_start:i + 1]),
        })

    return trend


def format_report(entries: list[dict]) -> str:
    """Format a full hit rate report."""
    metrics = compute_apf(entries)
    lines = [
        "Discovery Pipeline Hit Rate Report",
        f"  Total findings: {metrics['total']}",
        f"  BUILD: {metrics['build']}",
        f"  ADAPT: {metrics['adapt']}",
        f"  REFERENCE: {metrics['reference']}",
        f"  REFERENCE-PERSONAL: {metrics['reference_personal']}",
        f"  SKIP: {metrics['skip']}",
        f"  Signal (BUILD+ADAPT): {metrics['signal']}",
        f"  APF: {metrics['apf']}% (target: 40%)",
        f"  Useful rate: {metrics['useful_rate']}%",
    ]

    by_frontier = compute_by_frontier(entries)
    if by_frontier:
        lines.append("\nBy Frontier:")
        for name, data in by_frontier.items():
            lines.append(
                f"  {name}: APF={data['apf']}% "
                f"({data['signal']}/{data['total']} signal, "
                f"{data['skip']} skip)"
            )

    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "report"

    entries = parse_findings()

    if cmd == "report":
        print(format_report(entries))

    elif cmd == "apf":
        metrics = compute_apf(entries)
        print(f"{metrics['apf']}%")

    elif cmd == "by-frontier":
        by_frontier = compute_by_frontier(entries)
        for name, data in by_frontier.items():
            print(f"{name}: APF={data['apf']}% ({data['signal']}/{data['total']})")

    elif cmd == "trend":
        trend = compute_trend(entries)
        for t in trend:
            bar = "#" * int(t["rolling_apf"] / 5) if t["rolling_apf"] else ""
            print(
                f"  {t['date']}: {t['daily_count']:3d} finds, "
                f"APF={t['daily_apf']:5.1f}% "
                f"(7d roll: {t['rolling_apf']:5.1f}%) {bar}"
            )

    elif cmd == "json":
        metrics = compute_apf(entries)
        metrics["by_frontier"] = compute_by_frontier(entries)
        metrics["trend"] = compute_trend(entries)
        print(json.dumps(metrics, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: hit_rate_tracker.py [report|apf|by-frontier|trend|json]")
        sys.exit(1)


if __name__ == "__main__":
    main()
