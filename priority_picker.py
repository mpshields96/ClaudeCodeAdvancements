#!/usr/bin/env python3
"""priority_picker.py — Automated MT priority selection for autonomous task picking.

Reads MASTER_TASKS.md, computes priority scores with an improved formula,
and returns the top-N tasks to work on. Replaces manual table parsing.

Improvements over the original scoring system:
1. Completion proximity bonus — tasks near completion get a boost
2. Stagnation penalty — capped tasks that haven't been touched get flagged
3. Blocked re-evaluation — checks if blocked tasks should be unblocked
4. ROI scoring — estimated value per session-hour invested
5. CLI interface for autonomous task selection
"""

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class TaskStatus(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class Urgency(Enum):
    """How time-sensitive the task is."""
    ROUTINE = "routine"           # No deadline pressure
    AGING = "aging"               # Getting stale, should be touched
    STAGNATING = "stagnating"     # Capped and untouched — needs attention or archival
    NEAR_COMPLETE = "near_complete"  # 1-2 sessions from done


@dataclass
class MasterTask:
    """Parsed representation of a Master-Level Task."""
    mt_id: int
    name: str
    base_value: float
    status: TaskStatus
    last_touched_session: Optional[int]  # None = never touched
    current_session: int = 100
    phases_completed: int = 0
    phases_total: int = 0
    aging_rate: float = 1.0  # 1.0 for partial, 0.5 for not-started
    block_reason: Optional[str] = None
    self_resolution_note: Optional[str] = None
    next_action: str = ""
    tags: list = field(default_factory=list)

    @property
    def sessions_since_touch(self) -> int:
        if self.last_touched_session is None:
            return self.current_session  # Never touched = max age
        return self.current_session - self.last_touched_session

    @property
    def completion_pct(self) -> float:
        if self.phases_total == 0:
            return 0.0
        return (self.phases_completed / self.phases_total) * 100

    @property
    def raw_aging(self) -> float:
        return self.sessions_since_touch * self.aging_rate

    @property
    def aging_capped(self) -> float:
        cap = self.base_value  # Cap at 1x base (total max = 2x base)
        return min(self.raw_aging, cap)

    @property
    def original_score(self) -> float:
        """Original formula: base + capped aging."""
        return self.base_value + self.aging_capped

    @property
    def completion_bonus(self) -> float:
        """Bonus for tasks near completion (75%+ done).

        Logic: A task at 90% completion should get priority over a task at 10%
        completion with the same base value, because 1 more session finishes it.

        Scale: 0-3 points. Kicks in at 50%+, max at 90%+.
        """
        if self.completion_pct < 50:
            return 0.0
        if self.completion_pct >= 90:
            return 3.0
        if self.completion_pct >= 75:
            return 2.0
        return 1.0  # 50-74%

    @property
    def stagnation_flag(self) -> bool:
        """True if task has been at cap for 10+ sessions without being worked on."""
        return (self.aging_capped >= self.base_value and
                self.sessions_since_touch >= 10)

    @property
    def stagnation_penalty(self) -> float:
        """Penalty for stagnating tasks that should be worked or archived.

        Stagnating tasks (capped, untouched 10+ sessions) get -1.0.
        This prevents them from permanently blocking the queue while
        providing a signal that they need attention (work or archive).
        """
        if self.stagnation_flag:
            return -1.0
        return 0.0

    @property
    def roi_estimate(self) -> float:
        """Estimated sessions needed to complete next meaningful phase.

        Lower is better — 1 session to complete > 5 sessions to complete.
        Returns a bonus: 2.0 for 1-session tasks, 1.0 for 2-session, 0 for 3+.
        """
        remaining_pct = 100 - self.completion_pct
        if remaining_pct <= 15:  # ~1 session left
            return 2.0
        if remaining_pct <= 30:  # ~2 sessions left
            return 1.0
        return 0.0

    @property
    def urgency(self) -> Urgency:
        if self.completion_pct >= 75:
            return Urgency.NEAR_COMPLETE
        if self.stagnation_flag:
            return Urgency.STAGNATING
        if self.sessions_since_touch >= 5:
            return Urgency.AGING
        return Urgency.ROUTINE

    @property
    def improved_score(self) -> float:
        """Improved priority formula.

        score = base_value + aging_capped + completion_bonus + roi_estimate + stagnation_penalty

        This rewards:
        - High base value (force multiplier)
        - Tasks that haven't been touched (aging)
        - Tasks near completion (completion bonus)
        - Quick-win tasks (ROI estimate)

        And penalizes:
        - Tasks stuck at cap with no progress (stagnation)
        """
        return (self.base_value + self.aging_capped +
                self.completion_bonus + self.roi_estimate +
                self.stagnation_penalty)

    def to_dict(self) -> dict:
        return {
            "mt_id": self.mt_id,
            "name": self.name,
            "base_value": self.base_value,
            "status": self.status.value,
            "last_touched_session": self.last_touched_session,
            "sessions_since_touch": self.sessions_since_touch,
            "phases": f"{self.phases_completed}/{self.phases_total}",
            "completion_pct": round(self.completion_pct, 1),
            "original_score": round(self.original_score, 1),
            "improved_score": round(self.improved_score, 1),
            "urgency": self.urgency.value,
            "completion_bonus": self.completion_bonus,
            "roi_estimate": self.roi_estimate,
            "stagnation_penalty": self.stagnation_penalty,
            "next_action": self.next_action,
        }


def get_known_tasks(current_session: int = 124) -> list[MasterTask]:
    """Return the current MT registry.

    This is the source of truth for task metadata that can't be reliably
    parsed from MASTER_TASKS.md (phases, completion %, etc).
    Updates should be made here when tasks progress.

    IMPORTANT: Update last_touched_session every time an MT is worked on.
    Stale values here cause the priority picker to give bad recommendations.
    Last registry update: S124 (2026-03-23).
    """
    return [
        # === HIGHEST PRIORITY (Financial + Self-Learning) ===
        MasterTask(
            mt_id=0, name="Kalshi bot self-learning integration",
            base_value=10, status=TaskStatus.ACTIVE,
            last_touched_session=105, current_session=current_session,
            phases_completed=1, phases_total=3,
            aging_rate=1.0,
            next_action="Phase 2: Deploy self-learning to Kalshi bot. CCA prep complete, needs Kalshi chat execution.",
            tags=["kalshi", "self-learning", "trading"],
        ),
        # === COMPLETED ===
        MasterTask(
            mt_id=22, name="Autonomous 1-hour loop",
            base_value=9, status=TaskStatus.COMPLETED,
            last_touched_session=99, current_session=current_session,
            phases_completed=3, phases_total=3,  # GRADUATED S99 — 3/3 gate passed
            aging_rate=1.0,
            next_action="GRADUATED. Gate passed 3/3 supervised trials.",
            tags=["autonomy", "hivemind"],
        ),
        MasterTask(
            mt_id=21, name="Hivemind multi-chat coordination",
            base_value=8, status=TaskStatus.COMPLETED,
            last_touched_session=99, current_session=current_session,
            phases_completed=2, phases_total=2,  # Phase 3 (3-chat) SHELVED — 2-chat sufficient
            aging_rate=1.0,
            next_action="SHELVED Phase 3 (3-chat). 2-chat is sufficient per Matthew.",
            tags=["coordination", "hivemind"],
        ),
        # === ARCHIVED (stagnation resolver recommended, S100) ===
        MasterTask(
            mt_id=18, name="Academic writing workspace",
            base_value=4, status=TaskStatus.COMPLETED,
            last_touched_session=None, current_session=current_session,
            phases_completed=0, phases_total=5,
            aging_rate=0.5,
            next_action="ARCHIVED S100: 100 sessions untouched, 0% complete. Revisit if priorities change.",
            tags=["personal", "academic"],
        ),
        MasterTask(
            mt_id=13, name="iOS/macOS app development",
            base_value=4, status=TaskStatus.COMPLETED,
            last_touched_session=49, current_session=current_session,
            phases_completed=2, phases_total=6,
            aging_rate=0.5,
            next_action="ARCHIVED S100: 51 sessions untouched. Phase 2 done. Revisit when mobile is priority.",
            tags=["mobile", "kalshi"],
        ),
        MasterTask(
            mt_id=12, name="Academic research papers",
            base_value=6, status=TaskStatus.COMPLETED,
            last_touched_session=102, current_session=current_session,
            phases_completed=6, phases_total=6,  # ALL 6 PHASES COMPLETE (S102)
            aging_rate=0,
            next_action="DONE. All 6 phases: scanner, digest, bridge, 1242 papers, confidence calibrator, hit_rate_tracker.",
            tags=["research", "kalshi"],
        ),
        # === NEW MTs (S103 Strategic Vision) ===
        MasterTask(
            mt_id=23, name="Mobile Remote Control v2 (Telegram/Discord Channels)",
            base_value=5, status=TaskStatus.BLOCKED,
            last_touched_session=112, current_session=current_session,
            phases_completed=0, phases_total=6,
            aging_rate=0.5,
            block_reason="EXTERNALLY RESOLVED: Claude Code Channels shipped 2026-03-20",
            self_resolution_note="Official Telegram+Discord MCP channels. Matthew needs to install + test.",
            next_action="Matthew: install Telegram channel plugin, test with active session.",
            tags=["mobile", "remote"],
        ),
        MasterTask(
            mt_id=24, name="Visualization & Graphics Engine",
            base_value=6, status=TaskStatus.COMPLETED,
            last_touched_session=118, current_session=current_session,
            phases_completed=5, phases_total=5,  # Absorbed into MT-32
            aging_rate=0,
            next_action="ABSORBED into MT-32 (Visual Excellence). All chart work continues there.",
            tags=["visual", "reports"],
        ),
        MasterTask(
            mt_id=25, name="Presentation Generator (Matthew's Style)",
            base_value=5, status=TaskStatus.BLOCKED,
            last_touched_session=103, current_session=current_session,
            phases_completed=0, phases_total=5,
            aging_rate=0.5,
            block_reason="WAITING on Matthew's style samples and preferences",
            self_resolution_note="Matthew to provide Grand Rounds / psychopharm lecture samples.",
            next_action="BLOCKED: awaiting style samples from Matthew.",
            tags=["personal", "academic", "presentations"],
        ),
        MasterTask(
            mt_id=26, name="Financial Intelligence Engine",
            base_value=9, status=TaskStatus.ACTIVE,
            last_touched_session=125, current_session=current_session,
            phases_completed=7, phases_total=7,  # S125: E2E validated. Tier 3 Phase 2 (Kalman) deferred.
            aging_rate=0.5,
            next_action="CCA scope COMPLETE. 79 pipeline tests. Tier 3 Phase 2 deferred (needs numpy).",
            tags=["kalshi", "trading", "research"],
        ),
        MasterTask(
            mt_id=27, name="CCA Nuclear v2 (Enhanced Scanning)",
            base_value=5, status=TaskStatus.ACTIVE,
            last_touched_session=114, current_session=current_session,
            phases_completed=3, phases_total=5,
            aging_rate=0.5,
            next_action="Phase 4: NEEDLE precision improvement (reduce false positives).",
            tags=["scanning", "intelligence"],
        ),
        MasterTask(
            mt_id=28, name="Self-Learning v2 (Multi-Domain)",
            base_value=10, status=TaskStatus.COMPLETED,
            last_touched_session=111, current_session=current_session,
            phases_completed=6, phases_total=6,  # ALL COMPLETE: registry, plugin, transfer, feedback, predictive, sentinel_bridge
            aging_rate=0,
            next_action="DONE. All 6 phases complete. Full adaptive self-learning pipeline.",
            tags=["self-learning", "kalshi"],
        ),
        MasterTask(
            mt_id=29, name="Cowork + Pro Bridge Hivemind",
            base_value=2, status=TaskStatus.COMPLETED,
            last_touched_session=114, current_session=current_session,
            phases_completed=1, phases_total=6,
            aging_rate=0.5,
            next_action="SKIP — Cowork adds no value. Revisit if Anthropic ships shared context.",
            tags=["bridge", "hivemind", "cowork"],
        ),
        MasterTask(
            mt_id=30, name="Session Daemon (Tmux Auto-Spawn)",
            base_value=8, status=TaskStatus.COMPLETED,
            last_touched_session=113, current_session=current_session,
            phases_completed=5, phases_total=5,
            aging_rate=1.0,
            next_action="COMPLETE. All 5 phases shipped (S110-S113). 181 tests.",
            tags=["automation", "hivemind", "tmux"],
        ),
        MasterTask(
            mt_id=20, name="Senior dev agent",
            base_value=7, status=TaskStatus.COMPLETED,
            last_touched_session=101, current_session=current_session,
            phases_completed=9, phases_total=9,  # All phases + gaps closed S101. E2E LLM validated.
            aging_rate=0,
            next_action="DONE. Feature-complete. All gaps closed, E2E validated with real API.",
            tags=["quality", "senior-dev"],
        ),
        # === NEW MTs (S115-S124) ===
        MasterTask(
            mt_id=31, name="Gemini Flash Integration",
            base_value=6, status=TaskStatus.ACTIVE,
            last_touched_session=125, current_session=current_session,
            phases_completed=1, phases_total=4,  # S125: Flash works, Pro unavailable. Scope narrowed.
            aging_rate=0.5,
            next_action="Build Flash-powered CCA tools (code analysis, search). Pro unavailable (web only, no API).",
            tags=["integration", "multi-model"],
        ),
        MasterTask(
            mt_id=32, name="Visual Excellence & Design Engineering",
            base_value=6, status=TaskStatus.ACTIVE,
            last_touched_session=125, current_session=current_session,
            phases_completed=3, phases_total=8,  # S125: +coverage_ratio, +hook_coverage charts
            aging_rate=0.5,
            next_action="Per-file test distribution HistogramChart, then more CCA statistical charts.",
            tags=["visual", "reports", "design"],
        ),
        MasterTask(
            mt_id=33, name="Strategic Intelligence Report",
            base_value=7, status=TaskStatus.COMPLETED,
            last_touched_session=123, current_session=current_session,
            phases_completed=6, phases_total=6,  # All 6 phases COMPLETE
            aging_rate=0,
            next_action="DONE. All 6 phases shipped: collectors, charts, Typst, sidecar, differ.",
            tags=["reports", "kalshi", "intelligence"],
        ),
        MasterTask(
            mt_id=34, name="Medical AI Tool (OpenEvidence replacement)",
            base_value=4, status=TaskStatus.BLOCKED,
            last_touched_session=121, current_session=current_session,
            phases_completed=0, phases_total=6,
            aging_rate=0.5,
            block_reason="IDEA stage only — waiting for Matthew greenlight",
            self_resolution_note=None,
            next_action="BLOCKED: awaiting Matthew decision on scope and requirements.",
            tags=["personal", "medical"],
        ),
        # === BLOCKED ===
        MasterTask(
            mt_id=1, name="Maestro visual grid UI",
            base_value=7, status=TaskStatus.BLOCKED,
            last_touched_session=98, current_session=current_session,
            phases_completed=0, phases_total=3,
            aging_rate=0.5,
            block_reason="Was blocked on macOS SDK",
            self_resolution_note="MOSTLY SELF-RESOLVED (S96): Claude Control best candidate. Try install.",
            next_action="Try Claude Control install + test. If works, MT-1 solved.",
            tags=["ui", "visual"],
        ),
        MasterTask(
            mt_id=5, name="Claude Pro <-> Claude Code bridge",
            base_value=5, status=TaskStatus.BLOCKED,
            last_touched_session=None, current_session=current_session,
            phases_completed=0, phases_total=4,
            aging_rate=0.5,
            block_reason="Needs research on Claude Pro integration options",
            self_resolution_note="PARTIALLY SELF-RESOLVED: Remote Control + Chrome extension exist.",
            next_action="Evaluate existing tools (Remote Control, Chrome extension).",
            tags=["bridge", "productivity"],
        ),
        MasterTask(
            mt_id=16, name="Detachable chat tabs",
            base_value=3, status=TaskStatus.BLOCKED,
            last_touched_session=None, current_session=current_session,
            phases_completed=0, phases_total=1,
            aging_rate=0.5,
            block_reason="Anthropic feature request",
            self_resolution_note="STILL OPEN: GitHub issues filed. Nimbalyst workaround exists.",
            next_action="Monitor. Low priority.",
            tags=["ux"],
        ),
        MasterTask(
            mt_id=19, name="Local LLM fine-tuning",
            base_value=2, status=TaskStatus.BLOCKED,
            last_touched_session=None, current_session=current_session,
            phases_completed=0, phases_total=7,
            aging_rate=0.5,
            block_reason="Needs GPU resources, long-term exploration",
            self_resolution_note="STILL OPEN: Not self-resolving.",
            next_action="Long-term. Wait for Mac GPU support maturity.",
            tags=["ml", "long-term"],
        ),
    ]


class PriorityPicker:
    """Computes priority rankings and picks next task for autonomous work."""

    def __init__(self, current_session: int = 105):
        self.current_session = current_session
        self.tasks = get_known_tasks(current_session)

    def active_tasks(self) -> list[MasterTask]:
        return [t for t in self.tasks if t.status == TaskStatus.ACTIVE]

    def blocked_tasks(self) -> list[MasterTask]:
        return [t for t in self.tasks if t.status == TaskStatus.BLOCKED]

    def unblockable_tasks(self) -> list[MasterTask]:
        """Blocked tasks that have self-resolution notes suggesting they can be unblocked."""
        return [t for t in self.blocked_tasks()
                if t.self_resolution_note and
                ("MOSTLY SELF-RESOLVED" in t.self_resolution_note or
                 "PARTIALLY SELF-RESOLVED" in t.self_resolution_note)]

    def ranked(self, include_blocked: bool = False) -> list[MasterTask]:
        """Return tasks sorted by improved_score descending."""
        pool = self.active_tasks()
        if include_blocked:
            pool += self.unblockable_tasks()
        return sorted(pool, key=lambda t: t.improved_score, reverse=True)

    def pick_next(self, count: int = 1, include_blocked: bool = False) -> list[MasterTask]:
        """Pick the top N tasks to work on."""
        return self.ranked(include_blocked)[:count]

    def stagnating(self) -> list[MasterTask]:
        """Tasks that have been at cap and untouched for 10+ sessions."""
        return [t for t in self.active_tasks() if t.stagnation_flag]

    def near_complete(self) -> list[MasterTask]:
        """Tasks at 75%+ completion."""
        return [t for t in self.active_tasks() if t.completion_pct >= 75]

    def summary_table(self, include_blocked: bool = False) -> str:
        """Generate a markdown priority table."""
        ranked = self.ranked(include_blocked)
        lines = [
            "| Rank | MT | Task | Base | Age | Comp% | Bonus | ROI | Stag | **Score** | Urgency | Next |",
            "|------|----|------|------|-----|-------|-------|-----|------|-----------|---------|------|",
        ]
        for i, t in enumerate(ranked, 1):
            lines.append(
                f"| {i} | MT-{t.mt_id} | {t.name} | {t.base_value} | "
                f"+{t.aging_capped:.1f} | {t.completion_pct:.0f}% | "
                f"+{t.completion_bonus:.1f} | +{t.roi_estimate:.1f} | "
                f"{t.stagnation_penalty:.1f} | **{t.improved_score:.1f}** | "
                f"{t.urgency.value} | {t.next_action[:50]} |"
            )
        return "\n".join(lines)

    def stagnation_alert(self, threshold: int = 5) -> str:
        """Generate stagnation alert for /cca-init briefing.

        Returns empty string if no MTs are stagnating beyond threshold.
        Otherwise returns a concise warning listing neglected high-priority MTs.
        """
        aging = [t for t in self.active_tasks()
                 if t.sessions_since_touch >= threshold]
        if not aging:
            return ""
        # Sort by improved_score descending (highest priority first)
        aging.sort(key=lambda t: t.improved_score, reverse=True)
        lines = ["STAGNATION WARNING:"]
        for t in aging:
            lines.append(
                f"  MT-{t.mt_id} ({t.name}) — base={t.base_value}, "
                f"untouched {t.sessions_since_touch} sessions, "
                f"score={t.improved_score:.1f}"
            )
        return "\n".join(lines)

    def priority_vs_resume(self, resume_mt_ids: list[int]) -> list[MasterTask]:
        """Compare resume prompt suggestions against picker rankings.

        Returns MTs that rank higher than ALL resume suggestions but aren't
        in the resume list — these are being neglected by recency bias.
        """
        ranked = self.ranked()
        if not ranked or not resume_mt_ids:
            return []
        # Find the best rank position of any resume MT
        resume_positions = []
        for i, t in enumerate(ranked):
            if t.mt_id in resume_mt_ids:
                resume_positions.append(i)
        if not resume_positions:
            return []
        best_resume_pos = min(resume_positions)
        # Return MTs that rank above the best resume suggestion
        return [t for t in ranked[:best_resume_pos]
                if t.mt_id not in resume_mt_ids]

    def init_briefing(self) -> str:
        """Generate priority briefing for /cca-init.

        Combines stagnation alert + top picks into concise init output.
        """
        lines = []
        alert = self.stagnation_alert()
        if alert:
            lines.append(alert)
            lines.append("")
        top = self.pick_next(3)
        if top:
            lines.append("PRIORITY RANKING:")
            for i, t in enumerate(top, 1):
                lines.append(
                    f"  {i}. MT-{t.mt_id} ({t.name}) — "
                    f"score={t.improved_score:.1f} [{t.urgency.value}]"
                )
        return "\n".join(lines)

    def recommendations(self) -> str:
        """Generate actionable recommendations for the session."""
        lines = []

        # Top pick
        top = self.pick_next(1)
        if top:
            t = top[0]
            lines.append(f"**TOP PICK:** MT-{t.mt_id} ({t.name}) — score {t.improved_score:.1f}")
            lines.append(f"  Next: {t.next_action}")
            lines.append("")

        # Near-complete tasks (quick wins)
        nc = self.near_complete()
        if nc:
            lines.append("**QUICK WINS (75%+ complete):**")
            for t in nc:
                lines.append(f"  - MT-{t.mt_id}: {t.completion_pct:.0f}% done — {t.next_action[:60]}")
            lines.append("")

        # Stagnating tasks (need attention) — with resolver recommendations
        stag = self.stagnating()
        if stag:
            lines.append("**STAGNATING (need work or archival decision):**")
            try:
                from stagnation_resolver import classify_stagnation, recommend_action
                for t in stag:
                    cls = classify_stagnation(
                        t.sessions_since_touch,
                        t.completion_pct,  # already 0-100
                        int(t.base_value),
                    )
                    rec = recommend_action(
                        f"MT-{t.mt_id}",
                        cls["severity"],
                        t.sessions_since_touch,
                        t.completion_pct,  # already 0-100
                    )
                    lines.append(
                        f"  - MT-{t.mt_id}: {t.name} — untouched {t.sessions_since_touch} sessions "
                        f"[{cls['severity'].upper()}] -> {rec['action']}"
                    )
            except ImportError:
                for t in stag:
                    lines.append(f"  - MT-{t.mt_id}: {t.name} — untouched {t.sessions_since_touch} sessions")
            lines.append("")

        # Unblockable tasks
        ub = self.unblockable_tasks()
        if ub:
            lines.append("**POTENTIALLY UNBLOCKABLE:**")
            for t in ub:
                lines.append(f"  - MT-{t.mt_id}: {t.self_resolution_note}")
            lines.append("")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Export full ranking as JSON."""
        return json.dumps(
            [t.to_dict() for t in self.ranked(include_blocked=True)],
            indent=2
        )


def main():
    """CLI interface for priority_picker."""
    import argparse
    parser = argparse.ArgumentParser(description="MT Priority Picker")
    parser.add_argument("command", nargs="?", default="pick",
                       choices=["pick", "rank", "table", "recommend", "json", "stagnating", "init-briefing"],
                       help="Command to run")
    parser.add_argument("--session", type=int, default=124, help="Current session number")
    parser.add_argument("--count", type=int, default=3, help="Number of tasks to pick")
    parser.add_argument("--include-blocked", action="store_true", help="Include unblockable tasks")
    args = parser.parse_args()

    picker = PriorityPicker(current_session=args.session)

    if args.command == "pick":
        tasks = picker.pick_next(args.count, args.include_blocked)
        for i, t in enumerate(tasks, 1):
            print(f"{i}. MT-{t.mt_id} ({t.name}) — score {t.improved_score:.1f}")
            print(f"   {t.next_action}")
            print()

    elif args.command == "rank":
        for i, t in enumerate(picker.ranked(args.include_blocked), 1):
            print(f"{i}. MT-{t.mt_id}: {t.improved_score:.1f} ({t.urgency.value}) — {t.name}")

    elif args.command == "table":
        print(picker.summary_table(args.include_blocked))

    elif args.command == "recommend":
        print(picker.recommendations())

    elif args.command == "json":
        print(picker.to_json())

    elif args.command == "stagnating":
        stag = picker.stagnating()
        if stag:
            for t in stag:
                print(f"MT-{t.mt_id}: {t.name} — untouched {t.sessions_since_touch} sessions, cap {t.base_value*2}")
        else:
            print("No stagnating tasks.")

    elif args.command == "init-briefing":
        print(picker.init_briefing())


if __name__ == "__main__":
    main()
