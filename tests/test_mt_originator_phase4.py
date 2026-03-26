#!/usr/bin/env python3
"""Tests for mt_originator.py — MT-52 Phase 1: Intelligence-Driven Origination.

New capabilities:
- ADAPT verdict processing (actionable findings, not just BUILD)
- Stalled MT detection (MASTER_TASKS.md scan for stalled/dead MTs)
- Cross-chat intelligence (POLYBOT_TO_CCA.md unresolved requests -> research MTs)
- Unified origination pipeline (all 3 sources -> ranked proposals)
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mt_originator import (
    parse_findings_log,
    Finding,
    MTProposal,
    PhaseExtension,
    find_phase_extensions,
    score_extension,
    get_existing_mt_coverage,
)


# ============================================================
# New imports (will be added by implementation)
# ============================================================
try:
    from mt_originator import (
        find_actionable_adapts,
        parse_master_tasks_status,
        MTStatus,
        find_stalled_mts,
        parse_cross_chat_requests,
        CrossChatRequest,
        find_unresolved_requests,
        unified_origination,
        OriginationReport,
    )
    PHASE4_AVAILABLE = True
except ImportError:
    PHASE4_AVAILABLE = False


# --- Test data ---

ADAPT_FINDINGS = """# Findings Log

[2026-03-25] [BUILD] [MT-32: Visual Excellence] "Claude Code + Google Stitch" (333pts, r/ClaudeCode). Full UI design generation workflow. — https://reddit.com/r/ClaudeCode/stitch
[2026-03-25] [ADAPT] [Frontier 4: Agent Guard] "Claude Code has a hidden runtime" (r/ClaudeCode). UserPromptSubmit hook intercept pattern. — https://reddit.com/r/ClaudeCode/runtime
[2026-03-25] [ADAPT] [MT-0 Kalshi + MT-37] "Claude's finance plugins" (228pts, r/Anthropic). Claude native financial analysis. — https://reddit.com/r/Anthropic/finance
[2026-03-25] [ADAPT] [MT-0 Kalshi + MT-37] "122K-line trading simulator" (116pts, r/ClaudeAI). margincall.io with VaR, drawdown. — https://reddit.com/r/ClaudeAI/margincall
[2026-03-25] [REFERENCE] [Frontier 3: Context] "Your Claude Code Limits Didn't Shrink" (188pts). Context window analysis. — https://reddit.com/r/ClaudeAI/limits
[2026-03-25] [SKIP] [General] "OpenClaw debugging patterns" (66pts). Irrelevant framework. — https://reddit.com/r/AskClaw/openclaw
[2026-03-24] [ADAPT] [MT-10] "YoYo improvement for trading" (45pts). Trade reflector patterns. — https://reddit.com/r/algotrading/yoyo
"""

MASTER_TASKS_WITH_STATUS = """# Master-Level Tasks

---

## MT-0: Kalshi Bot Self-Learning Integration (BIGGEST)

**Status:** COMPLETE (Phase 1: S21, Phase 2: deployed).

---

## MT-5: Claude Pro Bridge

**Status:** Future task. Needs research on Claude Pro's current integration options.

---

## MT-7: Trace Analysis

**Status:** COMPLETE — trace_analyzer.py built and validated (S26-S28).

---

## MT-19: Local LLM Fine-Tuning

**Status:** PAUSED — depends on local GPU (Matthew has M1 Mac, no NVIDIA).

---

## MT-34: Medical AI Tool

**Status:** Future task. On hold.

---

## MT-37: Investment Portfolio Intelligence (UBER)

**Status:** Phase 1 COMPLETE. Next: Phase 2 (Architecture Design).

---

## MT-50: Kalshi Copytrade Bot Research (UBER-LEVEL)

**Status:** PROPOSED — needs Phase 1 research.

---

## MT-51: Kalshi New Market Expansion Research

**Status:** PROPOSED — needs Phase 1 research.
"""

CROSS_CHAT_REQUESTS = """# POLYBOT → CCA REQUESTS

## REQUEST 1 — Political Markets Volume Probe [STATUS: PENDING]
Probe KXPRES / KXELECTION / KXCONGRESS political tickers.
Questions: what 1-week+ political markets at 70-90c with >500 volume?

## REQUEST 2 — Multivariate Kelly [STATUS: RESOLVED]
CCA confirmed: 1/N conservative scaling sufficient.

## REQUEST 4 — OVERNIGHT/TIME-OF-DAY RESEARCH [STATUS: OPEN]
Priority: URGENT
Is there academic evidence for time-of-day effects on crypto prediction market accuracy?

## REQUEST 5 — KALSHI LEADERBOARD MARKET ANALYSIS [STATUS: OPEN]
Priority: NORMAL
What markets are top Kalshi performers actually trading?

## REQUEST 18 — HOUR+ASSET GUARD ANALYSIS [STATUS: OPEN]
Priority: URGENT (S127)
Q1. KXSOL 05:xx UTC academic structural basis?
Q2. 08:xx block re-evaluation?

## REQUEST 25 — NEW EDGE DISCOVERY [STATUS: OPEN]
Priority: URGENT
Find 2-3 market types with structural basis, EV > 3%, volume for 5+ bets/day.
"""


@unittest.skipUnless(PHASE4_AVAILABLE, "Phase 4 not yet implemented")
class TestFindActionableAdapts(unittest.TestCase):
    """ADAPT findings that map to existing MTs should produce phase extensions."""

    def test_finds_adapt_extensions(self):
        findings = parse_findings_log(ADAPT_FINDINGS)
        adapts = find_actionable_adapts(findings)
        self.assertIsInstance(adapts, list)
        self.assertGreater(len(adapts), 0)
        for ext in adapts:
            self.assertIsInstance(ext, PhaseExtension)

    def test_only_adapt_verdict(self):
        """Should only process ADAPT findings, not BUILD/REFERENCE/SKIP."""
        findings = parse_findings_log(ADAPT_FINDINGS)
        adapts = find_actionable_adapts(findings)
        for ext in adapts:
            self.assertEqual(ext.finding.verdict, "ADAPT")

    def test_maps_to_existing_mt(self):
        """ADAPT findings should map to specific existing MTs."""
        findings = parse_findings_log(ADAPT_FINDINGS)
        adapts = find_actionable_adapts(findings)
        mt_ids = {ext.mt_id for ext in adapts}
        # Should map to known MTs (not frontier pseudo-IDs 100+)
        for mt_id in mt_ids:
            self.assertLess(mt_id, 100)

    def test_empty_input(self):
        adapts = find_actionable_adapts([])
        self.assertEqual(adapts, [])

    def test_no_adapts_returns_empty(self):
        only_builds = "[2026-03-25] [BUILD] [NEW] Something — https://example.com\n"
        findings = parse_findings_log(only_builds)
        adapts = find_actionable_adapts(findings)
        self.assertEqual(adapts, [])

    def test_scored_and_sorted(self):
        findings = parse_findings_log(ADAPT_FINDINGS)
        adapts = find_actionable_adapts(findings)
        if len(adapts) >= 2:
            scores = [ext.score for ext in adapts]
            self.assertEqual(scores, sorted(scores, reverse=True))


@unittest.skipUnless(PHASE4_AVAILABLE, "Phase 4 not yet implemented")
class TestParseMasterTasksStatus(unittest.TestCase):
    """Parse MASTER_TASKS.md to extract MT statuses."""

    def test_parses_statuses(self):
        statuses = parse_master_tasks_status(MASTER_TASKS_WITH_STATUS)
        self.assertIsInstance(statuses, list)
        self.assertGreater(len(statuses), 0)
        for s in statuses:
            self.assertIsInstance(s, MTStatus)

    def test_mt_fields(self):
        statuses = parse_master_tasks_status(MASTER_TASKS_WITH_STATUS)
        ids = {s.mt_id for s in statuses}
        self.assertIn(0, ids)
        self.assertIn(37, ids)

    def test_status_categories(self):
        """Should detect COMPLETE, PROPOSED, PAUSED, FUTURE, IN_PROGRESS."""
        statuses = parse_master_tasks_status(MASTER_TASKS_WITH_STATUS)
        status_map = {s.mt_id: s.status for s in statuses}
        self.assertEqual(status_map[0], "COMPLETE")
        self.assertEqual(status_map[19], "PAUSED")
        self.assertIn(status_map[5], ("FUTURE", "PAUSED"))

    def test_empty_input(self):
        statuses = parse_master_tasks_status("")
        self.assertEqual(statuses, [])


@unittest.skipUnless(PHASE4_AVAILABLE, "Phase 4 not yet implemented")
class TestFindStalledMTs(unittest.TestCase):
    """Detect stalled/dormant MTs that could be expanded."""

    def test_finds_stalled(self):
        statuses = parse_master_tasks_status(MASTER_TASKS_WITH_STATUS)
        stalled = find_stalled_mts(statuses)
        self.assertIsInstance(stalled, list)
        # PAUSED and FUTURE MTs should be flagged
        mt_ids = {s.mt_id for s in stalled}
        self.assertIn(19, mt_ids)  # PAUSED

    def test_complete_not_stalled(self):
        """COMPLETE MTs should NOT be flagged as stalled (they might need expansion, but that's different)."""
        statuses = parse_master_tasks_status(MASTER_TASKS_WITH_STATUS)
        stalled = find_stalled_mts(statuses)
        stalled_ids = {s.mt_id for s in stalled}
        self.assertNotIn(0, stalled_ids)  # MT-0 is COMPLETE
        self.assertNotIn(7, stalled_ids)  # MT-7 is COMPLETE

    def test_proposed_flagged(self):
        """PROPOSED MTs should be flagged — they need action."""
        statuses = parse_master_tasks_status(MASTER_TASKS_WITH_STATUS)
        stalled = find_stalled_mts(statuses)
        stalled_ids = {s.mt_id for s in stalled}
        self.assertIn(50, stalled_ids)  # MT-50 is PROPOSED
        self.assertIn(51, stalled_ids)  # MT-51 is PROPOSED

    def test_empty_input(self):
        stalled = find_stalled_mts([])
        self.assertEqual(stalled, [])


@unittest.skipUnless(PHASE4_AVAILABLE, "Phase 4 not yet implemented")
class TestParseCrossChatRequests(unittest.TestCase):
    """Parse POLYBOT_TO_CCA.md for structured requests."""

    def test_parses_requests(self):
        requests = parse_cross_chat_requests(CROSS_CHAT_REQUESTS)
        self.assertIsInstance(requests, list)
        self.assertGreater(len(requests), 0)
        for r in requests:
            self.assertIsInstance(r, CrossChatRequest)

    def test_request_fields(self):
        requests = parse_cross_chat_requests(CROSS_CHAT_REQUESTS)
        req1 = [r for r in requests if r.request_id == 1][0]
        self.assertEqual(req1.status, "PENDING")
        self.assertIn("Political", req1.title)

    def test_finds_open_requests(self):
        requests = parse_cross_chat_requests(CROSS_CHAT_REQUESTS)
        open_reqs = [r for r in requests if r.status in ("OPEN", "PENDING")]
        self.assertGreater(len(open_reqs), 0)

    def test_resolved_excluded_from_open(self):
        requests = parse_cross_chat_requests(CROSS_CHAT_REQUESTS)
        open_reqs = [r for r in requests if r.status in ("OPEN", "PENDING")]
        open_ids = {r.request_id for r in open_reqs}
        self.assertNotIn(2, open_ids)  # REQUEST 2 is RESOLVED

    def test_empty_input(self):
        requests = parse_cross_chat_requests("")
        self.assertEqual(requests, [])


@unittest.skipUnless(PHASE4_AVAILABLE, "Phase 4 not yet implemented")
class TestFindUnresolvedRequests(unittest.TestCase):
    """Find requests that could spawn new MTs or research tasks."""

    def test_finds_unresolved(self):
        requests = parse_cross_chat_requests(CROSS_CHAT_REQUESTS)
        unresolved = find_unresolved_requests(requests)
        self.assertIsInstance(unresolved, list)
        self.assertGreater(len(unresolved), 0)

    def test_urgent_ranked_higher(self):
        requests = parse_cross_chat_requests(CROSS_CHAT_REQUESTS)
        unresolved = find_unresolved_requests(requests)
        if len(unresolved) >= 2:
            # URGENT requests should be first
            first_priority = unresolved[0].priority
            self.assertEqual(first_priority, "URGENT")


@unittest.skipUnless(PHASE4_AVAILABLE, "Phase 4 not yet implemented")
class TestUnifiedOrigination(unittest.TestCase):
    """All 3 sources combined into one ranked report."""

    def test_produces_report(self):
        report = unified_origination(
            findings_text=ADAPT_FINDINGS,
            master_tasks_text=MASTER_TASKS_WITH_STATUS,
            cross_chat_text=CROSS_CHAT_REQUESTS,
        )
        self.assertIsInstance(report, OriginationReport)

    def test_report_has_all_sections(self):
        report = unified_origination(
            findings_text=ADAPT_FINDINGS,
            master_tasks_text=MASTER_TASKS_WITH_STATUS,
            cross_chat_text=CROSS_CHAT_REQUESTS,
        )
        self.assertIsInstance(report.adapt_extensions, list)
        self.assertIsInstance(report.stalled_mts, list)
        self.assertIsInstance(report.unresolved_requests, list)
        self.assertIsInstance(report.new_mt_proposals, list)

    def test_report_total_actions(self):
        report = unified_origination(
            findings_text=ADAPT_FINDINGS,
            master_tasks_text=MASTER_TASKS_WITH_STATUS,
            cross_chat_text=CROSS_CHAT_REQUESTS,
        )
        total = report.total_actions()
        self.assertGreater(total, 0)

    def test_report_summary(self):
        report = unified_origination(
            findings_text=ADAPT_FINDINGS,
            master_tasks_text=MASTER_TASKS_WITH_STATUS,
            cross_chat_text=CROSS_CHAT_REQUESTS,
        )
        summary = report.summary()
        self.assertIsInstance(summary, str)
        self.assertGreater(len(summary), 0)

    def test_empty_inputs(self):
        report = unified_origination(
            findings_text="",
            master_tasks_text="",
            cross_chat_text="",
        )
        self.assertEqual(report.total_actions(), 0)


if __name__ == "__main__":
    unittest.main()
