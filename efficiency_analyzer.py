#!/usr/bin/env python3
"""efficiency_analyzer.py — MT-36 Phase 2: Session overhead analysis.

Analyzes WHERE session time goes (init/wrap/test vs code) and recommends
specific optimizations. Uses session_timer.py data as input.

Usage:
    python3 efficiency_analyzer.py                  # Analyze all sessions
    python3 efficiency_analyzer.py --last 5          # Last 5 sessions only
    python3 efficiency_analyzer.py --json             # JSON output
    python3 efficiency_analyzer.py --command init     # Init overhead only

Categories:
    - Overhead: init, wrap, test, doc
    - Productive: code
    - Other: other (uncategorized)

Key metrics:
    - Overhead ratio: overhead / (overhead + productive)
    - Top sinks: highest-duration overhead steps
    - Trends: is overhead improving, stable, or worsening?

Stdlib only. No external dependencies.
"""
import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from session_timer import load_timing_history, DEFAULT_LOG_PATH

OVERHEAD_CATEGORIES = {"init", "wrap", "test", "doc"}
PRODUCTIVE_CATEGORIES = {"code"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    """A specific optimization recommendation."""
    title: str
    category: str
    current_cost_s: float
    estimated_savings_s: float
    difficulty: str  # low, medium, high
    description: str

    @property
    def savings_pct(self) -> float:
        if self.current_cost_s <= 0:
            return 0.0
        return round(self.estimated_savings_s / self.current_cost_s * 100, 1)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["savings_pct"] = self.savings_pct
        return d


class SessionProfile:
    """Overhead breakdown for a single session."""

    def __init__(self, session_id: int, steps: list[dict]):
        self.session_id = session_id
        self.steps = steps

    @property
    def total_duration(self) -> float:
        return sum(s["duration_s"] for s in self.steps)

    @property
    def overhead_duration(self) -> float:
        return sum(
            s["duration_s"] for s in self.steps
            if s["category"] in OVERHEAD_CATEGORIES
        )

    @property
    def productive_duration(self) -> float:
        return sum(
            s["duration_s"] for s in self.steps
            if s["category"] in PRODUCTIVE_CATEGORIES
        )

    @property
    def overhead_ratio(self) -> float:
        total = self.total_duration
        if total <= 0:
            return 0.0
        return self.overhead_duration / total

    def category_breakdown(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for s in self.steps:
            cat = s["category"]
            result[cat] = result.get(cat, 0.0) + s["duration_s"]
        return result

    def top_overhead_steps(self, n: int = 5) -> list[dict]:
        """Top N overhead steps by duration (excludes code)."""
        overhead = [
            s for s in self.steps
            if s["category"] in OVERHEAD_CATEGORIES
        ]
        return sorted(overhead, key=lambda s: s["duration_s"], reverse=True)[:n]


# ---------------------------------------------------------------------------
# Multi-session analyzer
# ---------------------------------------------------------------------------

class OverheadAnalyzer:
    """Analyze overhead trends across multiple sessions."""

    def __init__(self, history: list[dict]):
        self.history = history
        self.profiles = [
            SessionProfile(
                session_id=entry.get("session_id", 0),
                steps=entry.get("steps", []),
            )
            for entry in history
        ]

    def analyze(self) -> dict:
        """Produce a full overhead analysis report."""
        n = len(self.profiles)
        if n == 0:
            return {
                "sessions_analyzed": 0,
                "avg_overhead_ratio": 0.0,
                "recommendations": [],
            }

        ratios = [p.overhead_ratio for p in self.profiles]
        avg_ratio = sum(ratios) / len(ratios)

        result = {
            "sessions_analyzed": n,
            "avg_overhead_ratio": round(avg_ratio, 3),
            "worst_overhead_ratio": round(max(ratios), 3),
            "best_overhead_ratio": round(min(ratios), 3),
            "overhead_trend": self._compute_trend(ratios),
            "top_sinks": self._top_sinks(),
            "category_trends": self._category_trends(),
            "recommendations": self._generate_recommendations(),
        }
        return result

    def _compute_trend(self, values: list[float]) -> str:
        """Determine if values are improving, stable, or worsening."""
        if len(values) < 2:
            return "stable"
        # Compare first half avg to second half avg
        mid = len(values) // 2
        first_half = sum(values[:mid]) / max(mid, 1)
        second_half = sum(values[mid:]) / max(len(values) - mid, 1)
        diff = second_half - first_half
        if diff > 0.05:
            return "worsening"
        if diff < -0.05:
            return "improving"
        return "stable"

    def _top_sinks(self, n: int = 5) -> list[dict]:
        """Identify steps that consistently consume the most overhead time."""
        step_totals: dict[str, list[float]] = {}
        step_cats: dict[str, str] = {}
        for profile in self.profiles:
            for s in profile.steps:
                if s["category"] not in OVERHEAD_CATEGORIES:
                    continue
                name = s["name"]
                step_totals.setdefault(name, []).append(s["duration_s"])
                step_cats[name] = s["category"]

        sinks = []
        for name, durations in step_totals.items():
            avg = sum(durations) / len(durations)
            sinks.append({
                "name": name,
                "avg_duration_s": round(avg, 2),
                "category": step_cats[name],
                "occurrences": len(durations),
            })

        return sorted(sinks, key=lambda s: s["avg_duration_s"], reverse=True)[:n]

    def _category_trends(self) -> dict[str, str]:
        """Per-category trend (improving/stable/worsening)."""
        if len(self.profiles) < 2:
            return {}

        cat_series: dict[str, list[float]] = {}
        for profile in self.profiles:
            breakdown = profile.category_breakdown()
            for cat in OVERHEAD_CATEGORIES:
                cat_series.setdefault(cat, []).append(breakdown.get(cat, 0.0))

        return {
            cat: self._compute_trend(values)
            for cat, values in cat_series.items()
        }

    def _generate_recommendations(self) -> list[dict]:
        """Generate optimization recommendations based on patterns."""
        recs = []
        sinks = self._top_sinks(10)

        for sink in sinks:
            name = sink["name"]
            avg = sink["avg_duration_s"]
            cat = sink["category"]

            # Test suite optimization
            if "test" in name.lower() and avg > 60:
                recs.append(Recommendation(
                    title=f"Optimize {name}",
                    category=cat,
                    current_cost_s=avg,
                    estimated_savings_s=avg * 0.5,
                    difficulty="medium",
                    description="Parallelize test execution or use incremental testing.",
                ).to_dict())

            # Self-learning consolidation
            if "self_learning" in name.lower() and avg > 30:
                recs.append(Recommendation(
                    title=f"Consolidate {name}",
                    category=cat,
                    current_cost_s=avg,
                    estimated_savings_s=avg * 0.6,
                    difficulty="high",
                    description="Batch subprocess calls into fewer invocations.",
                ).to_dict())

            # Init enrichment
            if "enrichment" in name.lower() and avg > 10:
                recs.append(Recommendation(
                    title=f"Defer {name}",
                    category=cat,
                    current_cost_s=avg,
                    estimated_savings_s=avg * 0.7,
                    difficulty="medium",
                    description="Move non-critical enrichment to auto loop.",
                ).to_dict())

            # Doc updates
            if cat == "doc" and avg > 15:
                recs.append(Recommendation(
                    title=f"Streamline {name}",
                    category=cat,
                    current_cost_s=avg,
                    estimated_savings_s=avg * 0.3,
                    difficulty="low",
                    description="Reduce doc update verbosity or defer to wrap.",
                ).to_dict())

        return recs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def analyze_command_overhead(steps: list[dict], command: str) -> dict:
    """Analyze overhead for a specific command (init/wrap/auto)."""
    cmd_steps = [
        s for s in steps
        if s["name"].startswith(f"{command}:")
    ]
    total = sum(s["duration_s"] for s in cmd_steps)
    return {
        "command": command,
        "total_s": round(total, 2),
        "step_count": len(cmd_steps),
        "steps": sorted(cmd_steps, key=lambda s: s["duration_s"], reverse=True),
    }


def compute_overhead_ratio(overhead_s: float, productive_s: float) -> float:
    """Compute overhead ratio from raw durations."""
    total = overhead_s + productive_s
    if total <= 0:
        return 0.0
    return round(overhead_s / total, 4)


def format_analysis_report(analysis: dict) -> str:
    """Format analysis dict into human-readable report."""
    if analysis.get("sessions_analyzed", 0) == 0:
        return "No timing data available. Wire session_timer into init/wrap/auto first."

    lines = []
    n = analysis["sessions_analyzed"]
    avg = analysis["avg_overhead_ratio"]
    lines.append(f"Sessions analyzed: {n}")
    lines.append(f"Avg overhead ratio: {avg * 100:.1f}%")

    if "worst_overhead_ratio" in analysis:
        worst = analysis["worst_overhead_ratio"]
        best = analysis["best_overhead_ratio"]
        lines.append(f"Range: {best * 100:.1f}% (best) — {worst * 100:.1f}% (worst)")

    if "overhead_trend" in analysis:
        lines.append(f"Trend: {analysis['overhead_trend']}")

    # Top sinks
    sinks = analysis.get("top_sinks", [])
    if sinks:
        lines.append("")
        lines.append("Top overhead sinks:")
        for i, sink in enumerate(sinks[:5], 1):
            lines.append(
                f"  {i}. {sink['name']} — {sink['avg_duration_s']:.1f}s avg "
                f"({sink['category']}, {sink['occurrences']}x)"
            )

    # Category trends
    cat_trends = analysis.get("category_trends", {})
    if cat_trends:
        lines.append("")
        lines.append("Category trends:")
        for cat, trend in sorted(cat_trends.items()):
            lines.append(f"  {cat}: {trend}")

    # Recommendations
    recs = analysis.get("recommendations", [])
    if recs:
        lines.append("")
        lines.append("Recommendations:")
        for i, rec in enumerate(recs[:5], 1):
            lines.append(
                f"  {i}. {rec['title']} — save ~{rec['estimated_savings_s']:.0f}s "
                f"({rec['savings_pct']:.0f}% of {rec['current_cost_s']:.0f}s) "
                f"[{rec['difficulty']}]"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Static wrap analysis (known structure)
# ---------------------------------------------------------------------------

# CCA wrap command steps with estimated token cost and criticality.
# Based on cca-wrap.md analysis (S147).
WRAP_STEPS = [
    # (step_id, description, est_tokens, category, critical)
    ("0.5", "Start wrap timer", 50, "wrap", False),
    ("1", "Run ALL test suites (213 suites)", 8000, "test", True),
    ("1.5", "Senior dev review (5 files)", 3000, "wrap", False),
    ("1.7", "APF checkpoint (hit_rate_tracker)", 500, "wrap", False),
    ("1.8", "APF session snapshot", 200, "wrap", False),
    ("2", "Self-assessment (human writes)", 500, "wrap", True),
    ("2.5", "Mark doc update timer", 50, "doc", False),
    ("3", "Update SESSION_STATE.md", 1000, "doc", True),
    ("4", "Append to CHANGELOG.md", 800, "doc", True),
    ("5", "Capture LEARNINGS.md", 500, "doc", False),
    ("6a", "Log session outcome to journal", 300, "wrap", False),
    ("6a.1", "Record outcome (trend tracking)", 400, "wrap", False),
    ("6a.5", "Log pain/win signals", 400, "wrap", False),
    ("6a.6", "Persist wrap assessment", 300, "wrap", False),
    ("6a.7", "Extract advancement tips", 300, "wrap", False),
    ("6b", "Run reflection (pattern detect)", 800, "wrap", False),
    ("6c", "Auto-escalate learnings to rules", 500, "wrap", False),
    ("6d", "Apply strategy changes", 500, "wrap", False),
    ("6e", "Check recurring anti-patterns", 300, "wrap", False),
    ("6f", "Skillbook evolution", 1000, "wrap", False),
    ("6g", "/arewedone structural health", 800, "wrap", False),
    ("6g.5", "Sentinel adaptation cycle", 500, "wrap", False),
    ("6h", "Validate skillbook strategies", 400, "wrap", False),
    ("6i", "Print session learning summary", 200, "wrap", True),
    ("7", "Update PROJECT_INDEX.md", 500, "doc", True),
    ("7.5", "Cross-chat comms update", 800, "doc", True),
    ("8", "Stage and display diff", 300, "other", True),
    ("8.5", "Send session-end notification", 200, "other", False),
    ("8.9", "Deregister from orchestrator", 100, "other", False),
    ("9", "Resume prompt + SESSION_RESUME.md", 500, "other", True),
    ("9.5", "Finalize session timer", 200, "other", False),
    ("10", "Trigger next session (autoloop)", 200, "other", True),
]


def analyze_wrap_overhead() -> dict:
    """Static analysis of cca-wrap overhead based on known step structure.

    Returns analysis with total token cost, critical vs deferrable breakdown,
    and specific recommendations for a slim wrap.
    """
    total_tokens = sum(s[2] for s in WRAP_STEPS)
    critical_tokens = sum(s[2] for s in WRAP_STEPS if s[4])
    deferrable_tokens = total_tokens - critical_tokens

    critical_steps = [(s[0], s[1], s[2]) for s in WRAP_STEPS if s[4]]
    deferrable_steps = [(s[0], s[1], s[2]) for s in WRAP_STEPS if not s[4]]

    # Group deferrable by category
    deferrable_by_cat: dict[str, int] = {}
    for s in WRAP_STEPS:
        if not s[4]:
            cat = s[3]
            deferrable_by_cat[cat] = deferrable_by_cat.get(cat, 0) + s[2]

    return {
        "total_estimated_tokens": total_tokens,
        "critical_tokens": critical_tokens,
        "deferrable_tokens": deferrable_tokens,
        "savings_pct": round(deferrable_tokens / total_tokens * 100, 1) if total_tokens > 0 else 0,
        "step_count": len(WRAP_STEPS),
        "critical_count": len(critical_steps),
        "deferrable_count": len(deferrable_steps),
        "critical_steps": [
            {"step": s[0], "desc": s[1], "tokens": s[2]} for s in critical_steps
        ],
        "deferrable_steps": [
            {"step": s[0], "desc": s[1], "tokens": s[2]} for s in deferrable_steps
        ],
        "deferrable_by_category": deferrable_by_cat,
        "slim_wrap_proposal": {
            "keep": [s[1] for s in critical_steps],
            "defer_to_next_init": [
                "Senior dev review", "APF checkpoint", "APF snapshot",
                "Skillbook evolution", "/arewedone health check",
                "Sentinel adaptation", "Strategy validation",
            ],
            "batch_into_one_call": [
                "journal log + outcome tracker + pain/win signals + wrap assessment + tips",
            ],
            "estimated_slim_tokens": critical_tokens + 1000,  # critical + batched self-learning
            "estimated_savings": deferrable_tokens - 1000,
        },
    }


def format_wrap_analysis() -> str:
    """Human-readable wrap overhead analysis."""
    a = analyze_wrap_overhead()
    lines = [
        f"CCA WRAP OVERHEAD ANALYSIS (MT-36 Phase 2)",
        f"",
        f"Total steps: {a['step_count']} ({a['critical_count']} critical, {a['deferrable_count']} deferrable)",
        f"Estimated tokens: {a['total_estimated_tokens']:,} total",
        f"  Critical: {a['critical_tokens']:,} ({100 - a['savings_pct']:.0f}%)",
        f"  Deferrable: {a['deferrable_tokens']:,} ({a['savings_pct']:.0f}%)",
        f"",
        f"CRITICAL STEPS (must keep in wrap):",
    ]
    for s in a["critical_steps"]:
        lines.append(f"  Step {s['step']}: {s['desc']} (~{s['tokens']:,} tokens)")

    lines.append("")
    lines.append("TOP DEFERRABLE STEPS (move to next init or batch):")
    deferred = sorted(a["deferrable_steps"], key=lambda s: s["tokens"], reverse=True)
    for s in deferred[:8]:
        lines.append(f"  Step {s['step']}: {s['desc']} (~{s['tokens']:,} tokens)")

    lines.append("")
    slim = a["slim_wrap_proposal"]
    lines.append(f"SLIM WRAP PROPOSAL:")
    lines.append(f"  Estimated tokens: ~{slim['estimated_slim_tokens']:,} (vs {a['total_estimated_tokens']:,} current)")
    lines.append(f"  Estimated savings: ~{slim['estimated_savings']:,} tokens ({a['savings_pct']:.0f}%)")
    lines.append(f"  Defer to next init: {len(slim['defer_to_next_init'])} steps")
    lines.append(f"  Batch into 1 call: {len(slim['batch_into_one_call'])} step groups")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Session efficiency analyzer")
    parser.add_argument("--last", type=int, help="Analyze last N sessions only")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--command", choices=["init", "wrap", "auto"],
                       help="Analyze specific command overhead")
    parser.add_argument("--wrap-analysis", action="store_true",
                       help="Static wrap overhead analysis")
    parser.add_argument("--path", default=DEFAULT_LOG_PATH,
                       help="Path to timing JSONL")
    args = parser.parse_args()

    if args.wrap_analysis:
        print(format_wrap_analysis())
        return

    history = load_timing_history(args.path)
    if args.last and args.last > 0:
        history = history[-args.last:]

    if args.command:
        # Flatten all steps from history
        all_steps = []
        for entry in history:
            all_steps.extend(entry.get("steps", []))
        result = analyze_command_overhead(all_steps, args.command)
    else:
        analyzer = OverheadAnalyzer(history)
        result = analyzer.analyze()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if args.command:
            print(f"Command: {result['command']}")
            print(f"Total: {result['total_s']:.1f}s ({result['step_count']} steps)")
            for s in result["steps"][:10]:
                print(f"  {s['name']}: {s['duration_s']:.1f}s")
        else:
            print(format_analysis_report(result))


if __name__ == "__main__":
    main()
