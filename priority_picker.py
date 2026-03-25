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
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class TaskStatus(Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ARCHIVED = "archived"  # Matthew decided to kill/archive (S160)


class Urgency(Enum):
    """How time-sensitive the task is."""
    ROUTINE = "routine"           # No deadline pressure
    AGING = "aging"               # Getting stale, should be touched
    STAGNATING = "stagnating"     # Capped and untouched — needs attention or archival
    NEAR_COMPLETE = "near_complete"  # 1-2 sessions from done


@dataclass
class RecurringTask:
    """A recurring maintenance task with staleness-based scoring.

    Examples: nuclear reddit scans, cross-chat checks, doc maintenance.
    These re-enter the priority queue when overdue based on time, not session count.
    """
    task_id: str
    name: str
    base_priority: float
    staleness_days: int  # How many days before considered overdue
    last_run_date: Optional[str]  # ISO date string "YYYY-MM-DD" or None
    current_date: str = ""  # ISO date string

    @property
    def days_stale(self) -> int:
        if not self.last_run_date:
            return 999  # Never run
        try:
            last = date.fromisoformat(self.last_run_date)
            now = date.fromisoformat(self.current_date) if self.current_date else date.today()
            return (now - last).days
        except (ValueError, TypeError):
            return 999

    @property
    def is_overdue(self) -> bool:
        return self.days_stale >= self.staleness_days

    @property
    def score(self) -> float:
        """Score: 0 if not overdue, base + 2*days_over if overdue. Caps at 2x base."""
        if not self.is_overdue:
            return 0.0
        days_over = self.days_stale - self.staleness_days
        raw = self.base_priority + (days_over * 2.0)
        return min(raw, self.base_priority * 2.0)


@dataclass
class Directive:
    """An explicit Matthew directive injected into the priority queue.

    These represent session-specific instructions that override normal scoring.
    """
    text: str
    priority: float
    source: str  # Which session created it, e.g. "S148"


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
    growth_action: Optional[str] = None  # Next growth opportunity for completed MTs
    growth_priority: float = 0  # Priority of growth action (0 = no growth)

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
        """Bonus for stagnating tasks to surface them for attention.

        Stagnating tasks (capped, untouched 10+ sessions) get +1.0 bonus.
        This ensures dusty tasks rise in priority the longer they wait,
        surfacing them for either work or archival.
        """
        if self.stagnation_flag:
            return 1.0
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


def get_known_tasks(current_session: int = 131) -> list[MasterTask]:
    """Return the current MT registry.

    This is the source of truth for task metadata that can't be reliably
    parsed from MASTER_TASKS.md (phases, completion %, etc).
    Updates should be made here when tasks progress.

    IMPORTANT: Update last_touched_session every time an MT is worked on.
    Stale values here cause the priority picker to give bad recommendations.
    Last registry update: S160 (2026-03-24).

    Priority tiers (from Matthew's S130 CCA Report 3-22 notes):
      Crown Jewels (base 9-10): MT-10, MT-0, MT-26, MT-22, MT-28, MT-27
      Top 5-10 (base 7-8): MT-9, MT-11, MT-12, MT-14, MT-21, MT-20
      Growth (base 5-6): MT-17/MT-5, MT-32, MT-33, MT-30, MT-7, MT-31
      Holds/Pivots (base 2-4): MT-1, MT-5, MT-16, MT-19, MT-13, MT-18
      Meta/Infrastructure (base 8-9): MT-39, MT-40, MT-41
    """
    return [
        # === CROWN JEWELS (Matthew S130: preserve, perfect, grow) ===
        MasterTask(
            mt_id=10, name="Self-Learning YoYo Improvement Loop",
            base_value=10, status=TaskStatus.COMPLETED,
            last_touched_session=125, current_session=current_session,
            phases_completed=6, phases_total=6,
            aging_rate=0,
            next_action="COMPLETE. Phase 3A real DB validated, Phase 3B resurfacer done.",
            tags=["self-learning", "core"],
            growth_action="Add convergence detection (ResearcherSkill pattern: metric plateau, discard streaks, approach exhaustion)",
            growth_priority=7,
        ),
        MasterTask(
            mt_id=0, name="Kalshi bot self-learning integration",
            base_value=10, status=TaskStatus.COMPLETED,
            last_touched_session=131, current_session=current_session,
            phases_completed=3, phases_total=3,
            aging_rate=0,
            next_action="COMPLETE. 7 modules deployed to polymarket-bot (DB-direct approach vs CCA journal.py). Closed feedback loop active.",
            tags=["kalshi", "self-learning", "trading"],
            growth_action="Wire principle_registry scoring into live Kalshi bet decisions (bridge CCA self-learning v2 -> polybot)",
            growth_priority=8,
        ),
        MasterTask(
            mt_id=22, name="Desktop Electron app automation",
            base_value=10, status=TaskStatus.COMPLETED,
            last_touched_session=162, current_session=current_session,
            phases_completed=4, phases_total=4,  # S132-S142: phases 1-3. S161: VALIDATED BY USAGE (160+ sessions). Phase 4 COMPLETE.
            aging_rate=0,
            next_action="COMPLETE. All 4 phases: desktop_automator, desktop_autoloop, autoloop_trigger, validated by 160+ sessions.",
            tags=["autonomy", "desktop", "crown-jewel"],
            growth_action="Claude Computer Use integration (native desktop control vs AppleScript)",
            growth_priority=4,
        ),
        MasterTask(
            mt_id=27, name="CCA Nuclear v2 (Enhanced Scanning)",
            base_value=8, status=TaskStatus.COMPLETED,
            last_touched_session=129, current_session=current_session,
            phases_completed=5, phases_total=5,
            aging_rate=0,
            next_action="COMPLETE. All 5 phases done.",
            tags=["scanning", "intelligence", "crown-jewel"],
            growth_action="Auto-schedule recurring scans via cron + staleness-triggered scanning",
            growth_priority=5,
        ),
        # === TOP 5-10 ===
        MasterTask(
            mt_id=9, name="Reddit Intelligence Pipeline",
            base_value=7, status=TaskStatus.COMPLETED,
            last_touched_session=130, current_session=current_session,
            phases_completed=4, phases_total=4,
            aging_rate=0,
            next_action="COMPLETE. Core scanning works, E2E validated.",
            tags=["scanning", "intelligence"],
            growth_action="MCP integration (reddit-mcp-buddy pattern) or comment-level sentiment scoring",
            growth_priority=4,
        ),
        MasterTask(
            mt_id=11, name="GitHub Intelligence Scanner",
            base_value=7, status=TaskStatus.COMPLETED,
            last_touched_session=125, current_session=current_session,
            phases_completed=5, phases_total=5,  # COMPLETE (S83): github_scanner.py + trending, 62 tests
            aging_rate=0,
            next_action="COMPLETE. Scanner + trending built.",
            tags=["scanning", "intelligence"],
        ),
        MasterTask(
            mt_id=14, name="Autonomous Scanner Pipeline",
            base_value=6, status=TaskStatus.COMPLETED,
            last_touched_session=125, current_session=current_session,
            phases_completed=5, phases_total=5,  # COMPLETE (S84): execute_rescan_stale + rescan-all CLI, 101 tests
            aging_rate=0,
            next_action="COMPLETE. Rescan stale + CLI done.",
            tags=["scanning", "autonomy"],
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
        # === GROWTH ===
        MasterTask(
            mt_id=7, name="Code Health / Trace Analyzer",
            base_value=5, status=TaskStatus.COMPLETED,
            last_touched_session=125, current_session=current_session,
            phases_completed=4, phases_total=4,  # COMPLETE: trace_analyzer.py + batch_report.py, 50 tests
            aging_rate=0,
            next_action="COMPLETE. trace_analyzer.py + batch_report.py built and validated.",
            tags=["quality", "self-learning"],
        ),
        MasterTask(
            mt_id=8, name="iPhone Remote Control Perfection",
            base_value=5, status=TaskStatus.ARCHIVED,
            last_touched_session=None, current_session=current_session,
            phases_completed=0, phases_total=4,
            aging_rate=0,
            block_reason="ARCHIVED S160: Matthew approved. Claude Code Channels covers mobile use case.",
            self_resolution_note="SELF-RESOLVED: Claude Code Channels (MT-23) covers mobile use case.",
            next_action="ARCHIVED.",
            tags=["mobile", "remote"],
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
            base_value=5, status=TaskStatus.ARCHIVED,
            last_touched_session=112, current_session=current_session,
            phases_completed=0, phases_total=6,
            aging_rate=0,
            block_reason="ARCHIVED S160: Matthew approved. Official Channels shipped.",
            self_resolution_note="SELF-RESOLVED: Official Telegram+Discord MCP channels shipped.",
            next_action="ARCHIVED.",
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
            base_value=5, status=TaskStatus.ARCHIVED,
            last_touched_session=103, current_session=current_session,
            phases_completed=0, phases_total=5,
            aging_rate=0,
            block_reason="ARCHIVED S160: Matthew approved archive.",
            self_resolution_note=None,
            next_action="ARCHIVED.",
            tags=["personal", "academic", "presentations"],
        ),
        MasterTask(
            mt_id=26, name="Financial Intelligence Engine",
            base_value=9, status=TaskStatus.COMPLETED,
            last_touched_session=125, current_session=current_session,
            phases_completed=7, phases_total=7,
            aging_rate=0,
            next_action="COMPLETE. Tier 3 Phase 2 deferred (needs numpy). 79 pipeline tests.",
            tags=["kalshi", "trading", "research"],
            growth_action="Tier 3 Phase 2: Kalman filter (deferred — needs numpy). Or: wire signal_pipeline into live Kalshi bot",
            growth_priority=7,
        ),
        MasterTask(
            mt_id=28, name="Self-Learning v2 (Multi-Domain)",
            base_value=10, status=TaskStatus.COMPLETED,
            last_touched_session=111, current_session=current_session,
            phases_completed=6, phases_total=6,
            aging_rate=0,
            next_action="DONE. All 6 phases complete. Full adaptive self-learning pipeline.",
            tags=["self-learning", "kalshi"],
            growth_action="Principle seeding from nuclear scan findings (auto-extract patterns from FINDINGS_LOG)",
            growth_priority=6,
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
            base_value=6, status=TaskStatus.ARCHIVED,
            last_touched_session=125, current_session=current_session,
            phases_completed=1, phases_total=4,
            aging_rate=0,
            block_reason="ARCHIVED S160: Matthew approved archive.",
            self_resolution_note="MCP exists but not prioritized.",
            next_action="ARCHIVED.",
            tags=["integration", "multi-model"],
        ),
        MasterTask(
            mt_id=32, name="Visual Excellence & Design Engineering",
            base_value=6, status=TaskStatus.ACTIVE,
            last_touched_session=158, current_session=current_session,
            phases_completed=5, phases_total=8,  # S158: Color palette sync + whitespace fix. S156: MT condensing + integer axes.
            aging_rate=0.5,
            next_action="Phase 6: Design system v2 (design tokens, lint rules, cross-format consistency).",
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
            base_value=4, status=TaskStatus.ARCHIVED,
            last_touched_session=121, current_session=current_session,
            phases_completed=0, phases_total=6,
            aging_rate=0,
            block_reason="ARCHIVED S160: Matthew killed — not greenlit.",
            self_resolution_note=None,
            next_action="ARCHIVED.",
            tags=["personal", "medical"],
        ),
        MasterTask(
            mt_id=35, name="Background Autoloop (non-intrusive desktop loop)",
            base_value=8, status=TaskStatus.COMPLETED,
            last_touched_session=162, current_session=current_session,
            phases_completed=4, phases_total=4,  # S142-S152: Phases 1-3 (save/restore, notification, CLI). S162: Phase 4 (toggle script + macOS shortcut setup).
            aging_rate=0,
            next_action="COMPLETE. All 4 phases: save/restore, notification, autoloop_pause CLI, autoloop_toggle.sh keyboard shortcut.",
            tags=["autonomy", "desktop", "crown-jewel"],
        ),
        # MT-36 moved below MT-38 (both now COMPLETED, S160)
        MasterTask(
            mt_id=37, name="AI Investment Research & Portfolio Intelligence (UBER)",
            base_value=8, status=TaskStatus.BLOCKED,
            last_touched_session=169, current_session=current_session,
            phases_completed=0, phases_total=7,
            aging_rate=0.3,  # Low — very long-term, no rush
            block_reason="UBER-LEVEL. Long-term research project — Phase 1 academic survey not yet started. Full spec in MT37_INVESTMENT_RESEARCH_UBER.md.",
            next_action="Phase 1: Deep academic research survey (MPT, factor models, ETF analysis). 50+ papers.",
            tags=["research", "finance", "long-term", "uber"],
        ),
        MasterTask(
            mt_id=38, name="Peak/Off-Peak Token Budget System",
            base_value=8, status=TaskStatus.COMPLETED,
            last_touched_session=159, current_session=current_session,
            phases_completed=4, phases_total=4,  # Phase 4 done S159: peak-aware autoloop scheduling
            aging_rate=0,
            next_action="COMPLETE. All 4 phases done: token_budget.py, agent blocking hook, autoloop scheduling.",
            tags=["efficiency", "automation", "universal"],
        ),
        MasterTask(
            mt_id=36, name="Session Efficiency Optimizer",
            base_value=8, status=TaskStatus.COMPLETED,
            last_touched_session=160, current_session=current_session,
            phases_completed=5, phases_total=5,  # Phase 5 done S160: efficiency_dashboard.py
            aging_rate=0,
            next_action="COMPLETE. All 5 phases: timer, analyzer, batch_wrap, doc_updater, dashboard.",
            tags=["optimization", "efficiency"],
            growth_action="Wire session_timer into /cca-init and /cca-wrap for live data collection",
            growth_priority=6,
        ),
        # === META/INFRASTRUCTURE (S160 — Matthew directive: fix the system) ===
        MasterTask(
            mt_id=39, name="Priority Picker Overhaul — Dust Detection",
            base_value=9, status=TaskStatus.COMPLETED,
            last_touched_session=162, current_session=current_session,
            phases_completed=3, phases_total=3,  # All 3 phases COMPLETE (S160): registry fixes, growth scoring, dust command + ARCHIVED status
            aging_rate=0,
            next_action="COMPLETE. All 3 phases: registry fixes, growth_score with dust bonus, dust CLI + ARCHIVED status + 8 MTs archived.",
            tags=["meta", "infrastructure", "priority"],
        ),
        MasterTask(
            mt_id=40, name="Automated Nuclear Scanning Loop",
            base_value=9, status=TaskStatus.COMPLETED,
            last_touched_session=162, current_session=current_session,
            phases_completed=4, phases_total=4,  # Phase 3 (S161): auto-scan API. Phase 4 (S162): scan_executor.py pipeline
            aging_rate=0,
            next_action="COMPLETE. All 4 phases: scheduler, init briefing, auto-scan API, executor pipeline.",
            tags=["scanning", "automation", "intelligence"],
        ),
        MasterTask(
            mt_id=41, name="Synthetic MT Origination",
            base_value=8, status=TaskStatus.ACTIVE,
            last_touched_session=160, current_session=current_session,
            phases_completed=1, phases_total=3,  # Phase 1 COMPLETE (S160): mt_originator.py + 22 tests
            aging_rate=1.0,
            next_action="Phase 2: Score proposals with community signal weighting. Phase 3: Auto-append to MASTER_TASKS.md with PROPOSED status.",
            tags=["meta", "intelligence", "automation"],
        ),
        # === MT-42: Kalshi Copytrading (S160 — Matthew request) ===
        MasterTask(
            mt_id=42, name="Kalshi Smart Money Copytrading",
            base_value=9, status=TaskStatus.BLOCKED,
            last_touched_session=161, current_session=current_session,
            phases_completed=1, phases_total=5,
            aging_rate=0,
            block_reason="S161: Phase 1 NEGATIVE RESULT — Kalshi API has no trader attribution, no public order flow, no way to identify smart money. Copytrading not feasible on Kalshi.",
            next_action="BLOCKED — no path forward without Kalshi API changes. Pivot to order_flow_intel.py (MT-26 Tier 3) for alternative approaches.",
            tags=["kalshi", "trading", "edge", "order-flow"],
        ),
        # === NEW MTs (S169 — Matthew directive: document all undocumented goals) ===
        MasterTask(
            mt_id=43, name="Data Analysis Excellence (Excel/PPT MCP Quality)",
            base_value=4, status=TaskStatus.BLOCKED,
            last_touched_session=169, current_session=current_session,
            phases_completed=0, phases_total=3,
            aging_rate=0.3,
            block_reason="Pending definition of specific quality gaps vs current MCP tool output",
            next_action="Phase 1: Assess current xlsx/pptx skill output quality, document gaps.",
            tags=["tools", "quality", "data-analysis"],
        ),
        MasterTask(
            mt_id=44, name="Automated Cross-Chat Task Execution Pipeline",
            base_value=6, status=TaskStatus.BLOCKED,
            last_touched_session=169, current_session=current_session,
            phases_completed=0, phases_total=5,
            aging_rate=0.5,
            block_reason="Infrastructure partially built (cca_comm.py, queue_injector.py). Gaps documented in ORCHESTRATION_GAPS.md.",
            next_action="Phase 1: Auto-inbox processing in /cca-auto-desktop work loop.",
            tags=["coordination", "automation", "hivemind"],
        ),
        MasterTask(
            mt_id=45, name="USAGE-5 Streamlit/Web Dashboard",
            base_value=3, status=TaskStatus.BLOCKED,
            last_touched_session=169, current_session=current_session,
            phases_completed=0, phases_total=3,
            aging_rate=0.2,
            block_reason="Low priority — CLI + HTML dashboards cover most needs. Build only if Matthew requests.",
            next_action="Phase 1: Evaluate whether MT-32 dashboard_generator.py covers the need.",
            tags=["visual", "dashboard", "usage"],
        ),
        MasterTask(
            mt_id=46, name="Report Self-Audit System (Honest Assessment)",
            base_value=5, status=TaskStatus.BLOCKED,
            last_touched_session=169, current_session=current_session,
            phases_completed=0, phases_total=3,
            aging_rate=0.5,
            block_reason="Needs doc_drift_checker.py and arewedone.py analysis to define audit scope first.",
            next_action="Phase 1: Build mt_status_auditor.py — cross-reference MT status claims with code/test reality.",
            tags=["quality", "meta", "reports"],
        ),
        MasterTask(
            mt_id=47, name="External Tool Evaluation Pipeline (BUILD Backlog)",
            base_value=4, status=TaskStatus.BLOCKED,
            last_touched_session=169, current_session=current_session,
            phases_completed=0, phases_total=3,
            aging_rate=0.3,
            block_reason="6 tools in FINDINGS_LOG BUILD backlog. Safety-first: read source only.",
            next_action="Phase 1: Evaluate CShip + claude-devtools source code. ADOPT/ADAPT/PASS verdict.",
            tags=["tools", "intelligence", "evaluation"],
        ),
        MasterTask(
            mt_id=48, name="Report Visual Polish (Chart/Layout Fixes)",
            base_value=5, status=TaskStatus.ACTIVE,
            last_touched_session=169, current_session=current_session,
            phases_completed=1, phases_total=2,
            aging_rate=0.5,
            next_action="Phase 2: Typst template whitespace compression, color sync with design-guide.md, TOC page numbers.",
            tags=["visual", "reports", "design"],
        ),
        MasterTask(
            mt_id=49, name="Self-Learning Evolution Engine (UBER)",
            base_value=10, status=TaskStatus.ACTIVE,
            last_touched_session=169, current_session=current_session,
            phases_completed=1, phases_total=6,
            aging_rate=1.0,
            next_action="Phase 2: Active principle transfer — automated cross-domain proposal with acceptance tracking.",
            tags=["self-learning", "core", "uber", "permanent"],
        ),
        # === BLOCKED ===
        MasterTask(
            mt_id=1, name="Maestro visual grid UI",
            base_value=7, status=TaskStatus.BLOCKED,
            last_touched_session=160, current_session=current_session,
            phases_completed=0, phases_total=3,
            aging_rate=0.5,
            block_reason="S160: Native Agent Teams + tmux is the path. Matthew needs to test.",
            self_resolution_note="SELF-RESOLVED: Claude Agent Teams (native) provides split-pane grid. Also: ccmanager, agtx, claude-squad.",
            next_action="Matthew: run /terminal-setup in Claude Code to get tmux split panes. Test multi-agent grid.",
            tags=["ui", "visual"],
        ),
        MasterTask(
            mt_id=5, name="Claude Pro <-> Claude Code bridge",
            base_value=5, status=TaskStatus.ARCHIVED,
            last_touched_session=None, current_session=current_session,
            phases_completed=0, phases_total=4,
            aging_rate=0,
            block_reason="ARCHIVED S160: Matthew approved. Self-resolved via Remote Control + Chrome ext.",
            self_resolution_note="SELF-RESOLVED: Remote Control + Chrome extension exist.",
            next_action="ARCHIVED.",
            tags=["bridge", "productivity"],
        ),
        MasterTask(
            mt_id=16, name="Detachable chat tabs",
            base_value=3, status=TaskStatus.ARCHIVED,
            last_touched_session=None, current_session=current_session,
            phases_completed=0, phases_total=1,
            aging_rate=0,
            block_reason="ARCHIVED S160: Matthew approved. Anthropic feature request — out of CCA scope.",
            self_resolution_note="Nimbalyst workaround exists.",
            next_action="ARCHIVED.",
            tags=["ux"],
        ),
        MasterTask(
            mt_id=19, name="Local LLM fine-tuning",
            base_value=2, status=TaskStatus.ARCHIVED,
            last_touched_session=None, current_session=current_session,
            phases_completed=0, phases_total=7,
            aging_rate=0,
            block_reason="ARCHIVED S160: Matthew killed. Not prioritized.",
            self_resolution_note=None,
            next_action="ARCHIVED.",
            tags=["ml", "long-term"],
        ),
    ]


class PriorityPicker:
    """Computes priority rankings and picks next task for autonomous work."""

    def __init__(self, current_session: int = 160):
        self.current_session = current_session
        self.tasks = get_known_tasks(current_session)
        self.directives: list[Directive] = []
        self.recurring_tasks: list[RecurringTask] = []

    def add_directive(self, directive: Directive) -> None:
        """Add a Matthew directive to the priority queue."""
        self.directives.append(directive)

    def add_recurring(self, task: RecurringTask) -> None:
        """Add a recurring task to the priority queue."""
        self.recurring_tasks.append(task)

    def growth_tasks(self) -> list[MasterTask]:
        """Completed MTs that have growth actions defined.

        Growth tasks accumulate dust: their effective priority rises
        based on how long they've been ignored (sessions_since_touch).
        This prevents completed-but-growable MTs from becoming invisible.
        """
        return [t for t in self.tasks
                if t.status == TaskStatus.COMPLETED
                and t.growth_action is not None
                and t.growth_priority > 0]

    def growth_score(self, t: MasterTask) -> float:
        """Effective growth score that rises with neglect.

        Base growth_priority + 0.2 per session since last touch, capped at +10.
        A growth task untouched for 50 sessions gets +10 boost, enough to
        compete with active tasks. This ensures dusty tasks surface eventually.
        """
        dust_bonus = min(t.sessions_since_touch * 0.2, 10.0)
        return t.growth_priority + dust_bonus

    def full_ranking(self) -> list[dict]:
        """Unified ranking across all item types: directives, recurring, active MTs, growth MTs.

        Returns a list of dicts with keys: type, name, score, detail.
        Sorted by score descending.
        """
        items = []

        # Directives
        for d in self.directives:
            items.append({
                "type": "directive",
                "name": f"[DIRECTIVE] {d.text}",
                "score": d.priority,
                "detail": f"Source: {d.source}",
            })

        # Overdue recurring tasks
        for rt in self.recurring_tasks:
            if rt.is_overdue:
                items.append({
                    "type": "recurring",
                    "name": f"[OVERDUE] {rt.name}",
                    "score": rt.score,
                    "detail": f"{rt.days_stale}d stale (threshold: {rt.staleness_days}d)",
                })

        # Active MTs
        for t in self.active_tasks():
            items.append({
                "type": "mt",
                "name": f"MT-{t.mt_id}: {t.name}",
                "score": t.improved_score,
                "detail": t.next_action,
            })

        # Growth opportunities on completed MTs (score rises with neglect)
        for t in self.growth_tasks():
            items.append({
                "type": "growth",
                "name": f"MT-{t.mt_id}: {t.name} [GROWTH]",
                "score": self.growth_score(t),
                "detail": f"{t.growth_action} (dust: +{min(t.sessions_since_touch * 0.2, 10.0):.1f})",
            })

        items.sort(key=lambda x: x["score"], reverse=True)
        return items

    def full_recommendations(self) -> str:
        """Enhanced recommendations showing all priority types."""
        lines = []
        full = self.full_ranking()

        # Group by type
        directives = [i for i in full if i["type"] == "directive"]
        overdue = [i for i in full if i["type"] == "recurring"]
        active = [i for i in full if i["type"] == "mt"]
        growth = [i for i in full if i["type"] == "growth"]

        if directives:
            lines.append("**DIRECTIVES (Matthew explicit):**")
            for d in directives:
                lines.append(f"  [{d['score']:.0f}] {d['name'][12:]}")  # strip [DIRECTIVE]
            lines.append("")

        if overdue:
            lines.append("**OVERDUE RECURRING:**")
            for r in overdue:
                lines.append(f"  [{r['score']:.0f}] {r['name'][10:]} — {r['detail']}")  # strip [OVERDUE]
            lines.append("")

        if active:
            lines.append("**ACTIVE MTs:**")
            for a in active:
                lines.append(f"  [{a['score']:.1f}] {a['name']} — {a['detail'][:60]}")
            lines.append("")

        if growth:
            lines.append("**GROWTH OPPORTUNITIES (completed MTs with next steps):**")
            for g in growth:
                lines.append(f"  [{g['score']:.0f}] {g['name']} — {g['detail'][:60]}")
            lines.append("")

        # Unblockable
        ub = self.unblockable_tasks()
        if ub:
            lines.append("**POTENTIALLY UNBLOCKABLE:**")
            for t in ub:
                lines.append(f"  MT-{t.mt_id}: {t.self_resolution_note}")
            lines.append("")

        if not lines:
            lines.append("No actionable items found.")

        return "\n".join(lines)

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

    def completed_tasks(self) -> list[MasterTask]:
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    def reopen_mt(self, mt_id: int, new_phase: str, new_total: int) -> bool:
        """Reopen a completed MT with a new phase.

        Completed MTs can evolve when new requirements emerge, the ecosystem
        changes, or downstream success reveals next steps. This preserves
        completion history while making the MT active again.

        Args:
            mt_id: The MT to reopen
            new_phase: Description of the new phase/next_action
            new_total: New total phases (must be > current phases_completed)

        Returns True if reopened, False if MT not found or invalid.
        """
        for t in self.tasks:
            if t.mt_id == mt_id:
                if new_total <= t.phases_completed:
                    return False
                t.status = TaskStatus.ACTIVE
                t.phases_total = new_total
                t.next_action = new_phase
                t.aging_rate = 1.0
                t.last_touched_session = self.current_session
                return True
        return False

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

    def dust_report(self, threshold: int = 20) -> str:
        """Show ALL neglected work — active, growth, and blocked.

        Unlike stagnating() which only checks active tasks at cap,
        this checks everything: growth tasks untouched for ages, blocked
        tasks that might be unblockable, and active tasks collecting dust.

        Args:
            threshold: sessions since last touch to consider "dusty"
        """
        lines = ["DUST REPORT — All Neglected Work"]
        lines.append(f"(threshold: {threshold}+ sessions untouched)\n")

        found_any = False

        # Active tasks collecting dust
        dusty_active = [t for t in self.active_tasks()
                        if t.sessions_since_touch >= threshold]
        if dusty_active:
            found_any = True
            dusty_active.sort(key=lambda t: t.sessions_since_touch, reverse=True)
            lines.append("DUSTY ACTIVE MTs:")
            for t in dusty_active:
                lines.append(
                    f"  MT-{t.mt_id}: {t.name} — {t.sessions_since_touch} sessions ago, "
                    f"base={t.base_value}, {t.completion_pct:.0f}% done"
                )
                lines.append(f"    Next: {t.next_action[:80]}")
            lines.append("")

        # Growth tasks collecting dust
        dusty_growth = [t for t in self.growth_tasks()
                        if t.sessions_since_touch >= threshold]
        if dusty_growth:
            found_any = True
            dusty_growth.sort(key=lambda t: t.sessions_since_touch, reverse=True)
            lines.append("DUSTY GROWTH OPPORTUNITIES:")
            for t in dusty_growth:
                lines.append(
                    f"  MT-{t.mt_id}: {t.name} — {t.sessions_since_touch} sessions ago, "
                    f"growth_score={self.growth_score(t):.1f}"
                )
                lines.append(f"    Growth: {t.growth_action[:80]}")
            lines.append("")

        # Blocked tasks that might be unblockable
        dusty_blocked = [t for t in self.blocked_tasks()
                         if t.sessions_since_touch >= threshold]
        if dusty_blocked:
            found_any = True
            dusty_blocked.sort(key=lambda t: t.sessions_since_touch, reverse=True)
            lines.append("DUSTY BLOCKED MTs (may need triage/archival):")
            for t in dusty_blocked:
                note = t.self_resolution_note or t.block_reason or "No resolution note"
                lines.append(
                    f"  MT-{t.mt_id}: {t.name} — {t.sessions_since_touch} sessions ago"
                )
                lines.append(f"    Status: {note[:80]}")
            lines.append("")

        # Never-touched tasks (exclude completed and archived)
        never_touched = [t for t in self.tasks
                         if t.last_touched_session is None
                         and t.status not in (TaskStatus.COMPLETED, TaskStatus.ARCHIVED)]
        if never_touched:
            found_any = True
            lines.append("NEVER STARTED:")
            for t in never_touched:
                lines.append(f"  MT-{t.mt_id}: {t.name} — {t.status.value}")
            lines.append("")

        if not found_any:
            lines.append("No dusty tasks found. All MTs are actively maintained.")

        # Summary
        total = len(self.tasks)
        active_count = len(self.active_tasks())
        completed_count = len(self.completed_tasks())
        blocked_count = len(self.blocked_tasks())
        archived_count = len([t for t in self.tasks if t.status == TaskStatus.ARCHIVED])
        growth_count = len(self.growth_tasks())
        dusty_total = len(dusty_active if dusty_active else []) + \
                      len(dusty_growth if dusty_growth else []) + \
                      len(dusty_blocked if dusty_blocked else [])
        lines.append(f"SUMMARY: {total} MTs total | {active_count} active | "
                     f"{completed_count} complete ({growth_count} with growth) | "
                     f"{blocked_count} blocked | {archived_count} archived | {dusty_total} dusty")

        return "\n".join(lines)

    def init_briefing(self) -> str:
        """Generate priority briefing for /cca-init.

        Combines dust alerts + stagnation + top picks + overdue recurring.
        """
        lines = []

        # Dust alert (top 3 dustiest items)
        dusty_growth = sorted(
            [t for t in self.growth_tasks() if t.sessions_since_touch >= 20],
            key=lambda t: self.growth_score(t), reverse=True
        )[:3]
        if dusty_growth:
            lines.append("DUST ALERT (growth MTs neglected 20+ sessions):")
            for t in dusty_growth:
                lines.append(
                    f"  MT-{t.mt_id}: {t.name} — {t.sessions_since_touch} sessions, "
                    f"score={self.growth_score(t):.1f}"
                )
            lines.append("")

        # Overdue recurring tasks
        overdue = [rt for rt in self.recurring_tasks if rt.is_overdue]
        if overdue:
            lines.append("OVERDUE RECURRING:")
            for rt in overdue:
                lines.append(f"  {rt.name} — {rt.days_stale}d stale")
            lines.append("")

        # Scan staleness check (MT-40)
        try:
            from scan_scheduler import ScanScheduler
            sched = ScanScheduler.from_registry_file()
            rec = sched.recommend()
            if rec.action == "SCAN_NOW":
                lines.append(f"SCAN ALERT: {len(rec.stale_subs)} subreddit(s) stale — top target: {rec.top_target}")
                lines.append("")
        except Exception:
            pass  # scan_scheduler not available or broken — skip silently

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


def get_default_recurring_tasks(current_date: str = "") -> list[RecurringTask]:
    """Default recurring tasks for CCA.

    Reads FINDINGS_LOG.md to determine last scan date for nuclear scans.
    """
    if not current_date:
        current_date = date.today().isoformat()

    # Try to detect last nuclear scan date from FINDINGS_LOG
    last_scan_date = None
    findings_path = Path(__file__).parent / "FINDINGS_LOG.md"
    if findings_path.exists():
        try:
            text = findings_path.read_text()
            # Find most recent date entry
            dates = re.findall(r'\[(\d{4}-\d{2}-\d{2})\]', text)
            if dates:
                last_scan_date = dates[-1]
        except Exception:
            pass

    # Try to detect last cross-chat check from cross_chat_queue.jsonl mtime
    last_crosschat_date = None
    crosschat_path = Path(__file__).parent / "cross_chat_queue.jsonl"
    if crosschat_path.exists():
        try:
            mtime = datetime.fromtimestamp(crosschat_path.stat().st_mtime)
            last_crosschat_date = mtime.date().isoformat()
        except Exception:
            pass

    return [
        RecurringTask(
            task_id="nuclear_scan",
            name="Nuclear Reddit/GitHub scan",
            base_priority=8,
            staleness_days=3,
            last_run_date=last_scan_date,
            current_date=current_date,
        ),
        RecurringTask(
            task_id="cross_chat_check",
            name="Cross-chat comms check (CCA <-> Kalshi)",
            base_priority=6,
            staleness_days=2,
            last_run_date=last_crosschat_date,
            current_date=current_date,
        ),
    ]


def main():
    """CLI interface for priority_picker."""
    import argparse
    parser = argparse.ArgumentParser(description="MT Priority Picker")
    parser.add_argument("command", nargs="?", default="pick",
                       choices=["pick", "rank", "table", "recommend", "json",
                                "stagnating", "init-briefing", "full", "dust"],
                       help="Command to run")
    parser.add_argument("--session", type=int, default=160, help="Current session number")
    parser.add_argument("--count", type=int, default=3, help="Number of tasks to pick")
    parser.add_argument("--include-blocked", action="store_true", help="Include unblockable tasks")
    args = parser.parse_args()

    picker = PriorityPicker(current_session=args.session)

    # Always load recurring tasks for full/recommend commands
    if args.command in ("full", "recommend", "init-briefing"):
        for rt in get_default_recurring_tasks():
            picker.add_recurring(rt)

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

    elif args.command == "full":
        print(picker.full_recommendations())

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

    elif args.command == "dust":
        print(picker.dust_report())


if __name__ == "__main__":
    main()
