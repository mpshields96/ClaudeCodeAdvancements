#!/usr/bin/env python3
"""Tests for priority_picker.py — MT priority selection system."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from priority_picker import (
    MasterTask, TaskStatus, Urgency, PriorityPicker, get_known_tasks
)


class TestMasterTask(unittest.TestCase):
    """Test MasterTask dataclass and scoring."""

    def _make_task(self, **kwargs):
        defaults = {
            "mt_id": 1, "name": "Test Task", "base_value": 5,
            "status": TaskStatus.ACTIVE, "last_touched_session": 90,
            "current_session": 98, "phases_completed": 1,
            "phases_total": 4, "aging_rate": 1.0,
        }
        defaults.update(kwargs)
        return MasterTask(**defaults)

    def test_sessions_since_touch(self):
        t = self._make_task(last_touched_session=90, current_session=98)
        self.assertEqual(t.sessions_since_touch, 8)

    def test_sessions_since_touch_never_touched(self):
        t = self._make_task(last_touched_session=None, current_session=98)
        self.assertEqual(t.sessions_since_touch, 98)

    def test_sessions_since_touch_just_touched(self):
        t = self._make_task(last_touched_session=98, current_session=98)
        self.assertEqual(t.sessions_since_touch, 0)

    def test_completion_pct(self):
        t = self._make_task(phases_completed=3, phases_total=4)
        self.assertAlmostEqual(t.completion_pct, 75.0)

    def test_completion_pct_zero_phases(self):
        t = self._make_task(phases_completed=0, phases_total=0)
        self.assertAlmostEqual(t.completion_pct, 0.0)

    def test_completion_pct_full(self):
        t = self._make_task(phases_completed=6, phases_total=6)
        self.assertAlmostEqual(t.completion_pct, 100.0)

    def test_aging_capped_at_base(self):
        t = self._make_task(base_value=5, last_touched_session=50, current_session=98)
        # raw aging = 48 * 1.0 = 48, but cap = 5 (1x base)
        self.assertEqual(t.aging_capped, 5.0)

    def test_aging_under_cap(self):
        t = self._make_task(base_value=9, last_touched_session=95, current_session=98)
        # raw aging = 3 * 1.0 = 3, cap = 9
        self.assertEqual(t.aging_capped, 3.0)

    def test_aging_rate_half(self):
        t = self._make_task(base_value=5, last_touched_session=90, aging_rate=0.5)
        # raw aging = 8 * 0.5 = 4.0, cap = 5
        self.assertEqual(t.aging_capped, 4.0)

    def test_original_score(self):
        t = self._make_task(base_value=9, last_touched_session=95)
        # base=9, aging=3
        self.assertEqual(t.original_score, 12.0)

    def test_completion_bonus_under_50(self):
        t = self._make_task(phases_completed=1, phases_total=4)  # 25%
        self.assertEqual(t.completion_bonus, 0.0)

    def test_completion_bonus_50_74(self):
        t = self._make_task(phases_completed=3, phases_total=5)  # 60%
        self.assertEqual(t.completion_bonus, 1.0)

    def test_completion_bonus_75_89(self):
        t = self._make_task(phases_completed=4, phases_total=5)  # 80%
        self.assertEqual(t.completion_bonus, 2.0)

    def test_completion_bonus_90_plus(self):
        t = self._make_task(phases_completed=9, phases_total=10)  # 90%
        self.assertEqual(t.completion_bonus, 3.0)

    def test_stagnation_flag_true(self):
        # At cap (aging >= base) and untouched 10+ sessions
        t = self._make_task(base_value=4, last_touched_session=None, current_session=98)
        self.assertTrue(t.stagnation_flag)

    def test_stagnation_flag_false_recent(self):
        t = self._make_task(base_value=4, last_touched_session=95)
        self.assertFalse(t.stagnation_flag)

    def test_stagnation_flag_false_under_cap(self):
        t = self._make_task(base_value=100, last_touched_session=80, current_session=98)
        # aging = 18, cap = 100, not at cap
        self.assertFalse(t.stagnation_flag)

    def test_stagnation_penalty(self):
        t = self._make_task(base_value=4, last_touched_session=None)
        self.assertEqual(t.stagnation_penalty, 1.0)  # Bonus to surface dusty tasks

    def test_no_stagnation_penalty_when_recent(self):
        t = self._make_task(base_value=4, last_touched_session=97)
        self.assertEqual(t.stagnation_penalty, 0.0)

    def test_roi_estimate_near_done(self):
        t = self._make_task(phases_completed=9, phases_total=10)  # 90% = ~1 session
        self.assertEqual(t.roi_estimate, 2.0)

    def test_roi_estimate_two_sessions(self):
        t = self._make_task(phases_completed=7, phases_total=10)  # 70% = ~2-3 sessions
        self.assertEqual(t.roi_estimate, 1.0)

    def test_roi_estimate_many_sessions(self):
        t = self._make_task(phases_completed=1, phases_total=10)  # 10%
        self.assertEqual(t.roi_estimate, 0.0)

    def test_urgency_near_complete(self):
        t = self._make_task(phases_completed=4, phases_total=5)  # 80%
        self.assertEqual(t.urgency, Urgency.NEAR_COMPLETE)

    def test_urgency_stagnating(self):
        t = self._make_task(base_value=4, last_touched_session=None,
                           phases_completed=0, phases_total=5)
        self.assertEqual(t.urgency, Urgency.STAGNATING)

    def test_urgency_aging(self):
        t = self._make_task(last_touched_session=90, phases_completed=1, phases_total=4)
        self.assertEqual(t.urgency, Urgency.AGING)

    def test_urgency_routine(self):
        t = self._make_task(last_touched_session=97, phases_completed=1, phases_total=4)
        self.assertEqual(t.urgency, Urgency.ROUTINE)

    def test_improved_score_formula(self):
        t = self._make_task(base_value=9, last_touched_session=95,
                           phases_completed=2, phases_total=3)
        # base=9, aging=3, completion=67% -> bonus=1.0, roi=0 (33% remaining > 30%), stag=0
        expected = 9 + 3 + 1.0 + 0.0 + 0
        self.assertAlmostEqual(t.improved_score, expected)

    def test_improved_score_with_stagnation(self):
        t = self._make_task(base_value=4, last_touched_session=None,
                           phases_completed=0, phases_total=5)
        # base=4, aging=4(capped), completion=0%->0, roi=0, stag=+1 (dust bonus)
        expected = 4 + 4 + 0 + 0 + 1
        self.assertAlmostEqual(t.improved_score, expected)

    def test_to_dict(self):
        t = self._make_task()
        d = t.to_dict()
        self.assertIn("mt_id", d)
        self.assertIn("improved_score", d)
        self.assertIn("urgency", d)
        self.assertIn("completion_pct", d)
        self.assertEqual(d["status"], "active")

    def test_near_complete_beats_stagnating(self):
        """A near-complete task should score higher than a stagnating one."""
        near = self._make_task(mt_id=1, base_value=8, last_touched_session=96,
                              phases_completed=5, phases_total=6)  # 83%
        stag = self._make_task(mt_id=2, base_value=4, last_touched_session=None,
                              phases_completed=0, phases_total=5)
        self.assertGreater(near.improved_score, stag.improved_score)


class TestPriorityPicker(unittest.TestCase):
    """Test PriorityPicker ranking and selection."""

    def test_active_tasks(self):
        picker = PriorityPicker(current_session=98)
        active = picker.active_tasks()
        self.assertTrue(all(t.status == TaskStatus.ACTIVE for t in active))

    def test_blocked_tasks(self):
        picker = PriorityPicker(current_session=98)
        blocked = picker.blocked_tasks()
        self.assertTrue(all(t.status == TaskStatus.BLOCKED for t in blocked))

    def test_ranked_returns_sorted(self):
        picker = PriorityPicker(current_session=98)
        ranked = picker.ranked()
        scores = [t.improved_score for t in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_pick_next_returns_top(self):
        picker = PriorityPicker(current_session=98)
        top = picker.pick_next(1)
        self.assertEqual(len(top), 1)
        # pick_next uses full_ranking (active + growth unified)
        full = picker.full_ranking()
        mt_items = [i for i in full if i["type"] in ("mt", "growth")]
        if mt_items:
            import re as _re
            mt_match = _re.search(r"MT-(\d+)", mt_items[0]["name"])
            if mt_match:
                self.assertEqual(top[0].mt_id, int(mt_match.group(1)))

    def test_pick_next_count(self):
        picker = PriorityPicker(current_session=100)
        active_count = len(picker.active_tasks())
        top2 = picker.pick_next(2)
        self.assertEqual(len(top2), min(2, active_count))

    def test_pick_next_with_blocked(self):
        picker = PriorityPicker(current_session=98)
        without = picker.pick_next(10, include_blocked=False)
        with_blocked = picker.pick_next(10, include_blocked=True)
        self.assertGreaterEqual(len(with_blocked), len(without))

    def test_unblockable_tasks(self):
        picker = PriorityPicker(current_session=98)
        ub = picker.unblockable_tasks()
        for t in ub:
            self.assertIn("SELF-RESOLVED", t.self_resolution_note)

    def test_stagnating(self):
        picker = PriorityPicker(current_session=98)
        stag = picker.stagnating()
        for t in stag:
            self.assertTrue(t.stagnation_flag)

    def test_near_complete(self):
        picker = PriorityPicker(current_session=98)
        nc = picker.near_complete()
        for t in nc:
            self.assertGreaterEqual(t.completion_pct, 75)

    def test_summary_table_is_markdown(self):
        picker = PriorityPicker(current_session=98)
        table = picker.summary_table()
        self.assertIn("| Rank |", table)
        self.assertIn("MT-", table)

    def test_recommendations_not_empty(self):
        picker = PriorityPicker(current_session=98)
        rec = picker.recommendations()
        self.assertIn("TOP PICK", rec)

    def test_to_json_valid(self):
        picker = PriorityPicker(current_session=98)
        data = json.loads(picker.to_json())
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIn("improved_score", data[0])

    def test_mt22_completed_desktop_scope(self):
        """MT-22 COMPLETED S162 — desktop Electron app automation validated by 160+ sessions."""
        picker = PriorityPicker(current_session=162)
        mt22 = [t for t in picker.tasks if t.mt_id == 22]
        self.assertEqual(len(mt22), 1)
        self.assertEqual(mt22[0].status, TaskStatus.COMPLETED)
        self.assertIn("Desktop", mt22[0].name)

    def test_session_number_affects_aging(self):
        picker_early = PriorityPicker(current_session=98)
        picker_late = PriorityPicker(current_session=120)
        ranked_early = picker_early.ranked()
        ranked_late = picker_late.ranked()
        # Tasks should have higher aging scores later
        for te, tl in zip(ranked_early, ranked_late):
            if te.mt_id == tl.mt_id and te.last_touched_session is not None:
                self.assertGreaterEqual(tl.improved_score, te.improved_score)


class TestGetKnownTasks(unittest.TestCase):
    """Test the task registry."""

    def test_returns_tasks(self):
        tasks = get_known_tasks(98)
        self.assertGreater(len(tasks), 0)

    def test_all_have_ids(self):
        for t in get_known_tasks(98):
            self.assertIsInstance(t.mt_id, int)

    def test_no_duplicate_ids(self):
        tasks = get_known_tasks(98)
        ids = [t.mt_id for t in tasks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_have_next_action(self):
        for t in get_known_tasks(98):
            self.assertTrue(len(t.next_action) > 0, f"MT-{t.mt_id} missing next_action")

    def test_current_session_propagated(self):
        tasks = get_known_tasks(150)
        for t in tasks:
            self.assertEqual(t.current_session, 150)

    def test_blocked_tasks_have_reason(self):
        for t in get_known_tasks(98):
            if t.status == TaskStatus.BLOCKED:
                self.assertIsNotNone(t.block_reason, f"MT-{t.mt_id} blocked without reason")


class TestStagnationAlert(unittest.TestCase):
    """Test stagnation alert for /cca-init briefing."""

    def test_stagnation_alert_detects_aging_mt(self):
        """MTs untouched 5+ sessions should appear in alert."""
        picker = PriorityPicker(current_session=162)
        alert = picker.stagnation_alert()
        # Completed MTs should NOT appear
        self.assertNotIn("MT-27", alert)
        self.assertNotIn("MT-22", alert)
        self.assertNotIn("MT-35", alert)
        # Alert is a string, may or may not have active stagnating MTs
        self.assertIsInstance(alert, str)

    def test_stagnation_alert_empty_when_all_recent(self):
        """No alert if all active MTs were touched recently."""
        picker = PriorityPicker(current_session=124)
        # Override with all-recent tasks
        picker.tasks = [
            MasterTask(mt_id=1, name="Recent", base_value=5,
                      status=TaskStatus.ACTIVE, last_touched_session=123,
                      current_session=124, phases_completed=1, phases_total=3),
        ]
        alert = picker.stagnation_alert()
        self.assertEqual(alert, "")

    def test_stagnation_alert_shows_sessions_untouched(self):
        """Alert includes how many sessions untouched."""
        picker = PriorityPicker(current_session=124)
        picker.tasks = [
            MasterTask(mt_id=99, name="Old Task", base_value=8,
                      status=TaskStatus.ACTIVE, last_touched_session=100,
                      current_session=124, phases_completed=1, phases_total=3),
        ]
        alert = picker.stagnation_alert()
        self.assertIn("24 sessions", alert)

    def test_stagnation_alert_sorted_by_priority(self):
        """Higher-priority MTs appear first in alert."""
        picker = PriorityPicker(current_session=124)
        picker.tasks = [
            MasterTask(mt_id=1, name="Low", base_value=3,
                      status=TaskStatus.ACTIVE, last_touched_session=100,
                      current_session=124, phases_completed=0, phases_total=3),
            MasterTask(mt_id=2, name="High", base_value=10,
                      status=TaskStatus.ACTIVE, last_touched_session=100,
                      current_session=124, phases_completed=1, phases_total=3),
        ]
        alert = picker.stagnation_alert()
        mt2_pos = alert.index("MT-2")
        mt1_pos = alert.index("MT-1")
        self.assertLess(mt2_pos, mt1_pos)

    def test_stagnation_alert_excludes_completed(self):
        """Completed MTs never appear in stagnation alert."""
        picker = PriorityPicker(current_session=124)
        picker.tasks = [
            MasterTask(mt_id=1, name="Done", base_value=10,
                      status=TaskStatus.COMPLETED, last_touched_session=50,
                      current_session=124, phases_completed=3, phases_total=3),
        ]
        alert = picker.stagnation_alert()
        self.assertEqual(alert, "")

    def test_stagnation_alert_threshold_5_sessions(self):
        """Tasks untouched exactly 5 sessions should be flagged."""
        picker = PriorityPicker(current_session=124)
        picker.tasks = [
            MasterTask(mt_id=1, name="Edge", base_value=5,
                      status=TaskStatus.ACTIVE, last_touched_session=119,
                      current_session=124, phases_completed=1, phases_total=3),
        ]
        alert = picker.stagnation_alert()
        self.assertIn("MT-1", alert)

    def test_stagnation_alert_threshold_4_sessions_no_flag(self):
        """Tasks untouched only 4 sessions should NOT be flagged."""
        picker = PriorityPicker(current_session=124)
        picker.tasks = [
            MasterTask(mt_id=1, name="Recent-ish", base_value=5,
                      status=TaskStatus.ACTIVE, last_touched_session=120,
                      current_session=124, phases_completed=1, phases_total=3),
        ]
        alert = picker.stagnation_alert()
        self.assertEqual(alert, "")

    def test_priority_vs_resume_detects_mismatch(self):
        """Should flag when resume prompt suggests lower-priority MT over higher."""
        picker = PriorityPicker(current_session=124)
        picker.tasks = [
            MasterTask(mt_id=0, name="High Priority", base_value=10,
                      status=TaskStatus.ACTIVE, last_touched_session=105,
                      current_session=124, phases_completed=1, phases_total=3),
            MasterTask(mt_id=32, name="Low Priority", base_value=6,
                      status=TaskStatus.ACTIVE, last_touched_session=123,
                      current_session=124, phases_completed=2, phases_total=8),
        ]
        mismatch = picker.priority_vs_resume(resume_mt_ids=[32])
        self.assertTrue(len(mismatch) > 0)
        self.assertEqual(mismatch[0].mt_id, 0)

    def test_priority_vs_resume_no_mismatch_when_aligned(self):
        """No mismatch when resume prompt suggests the top priority."""
        picker = PriorityPicker(current_session=124)
        picker.tasks = [
            MasterTask(mt_id=0, name="Top", base_value=10,
                      status=TaskStatus.ACTIVE, last_touched_session=123,
                      current_session=124, phases_completed=1, phases_total=3),
        ]
        mismatch = picker.priority_vs_resume(resume_mt_ids=[0])
        self.assertEqual(len(mismatch), 0)

    def test_init_briefing_format(self):
        """init_briefing() returns a formatted string for /cca-init."""
        picker = PriorityPicker(current_session=124)
        briefing = picker.init_briefing()
        self.assertIsInstance(briefing, str)


class TestS130PriorityReorder(unittest.TestCase):
    """Tests for S130 Matthew priority reorder directive."""

    def test_mt10_yoyo_in_registry(self):
        """MT-10 (YoYo) must exist — COMPLETED as of S97."""
        tasks = get_known_tasks(131)
        mt10 = [t for t in tasks if t.mt_id == 10]
        self.assertEqual(len(mt10), 1)
        self.assertEqual(mt10[0].base_value, 10)
        self.assertEqual(mt10[0].status, TaskStatus.COMPLETED)

    def test_mt9_reddit_intel_in_registry(self):
        """MT-9 (Reddit Intelligence) must exist in top 5-10 tier."""
        tasks = get_known_tasks(131)
        mt9 = [t for t in tasks if t.mt_id == 9]
        self.assertEqual(len(mt9), 1)
        self.assertGreaterEqual(mt9[0].base_value, 7)

    def test_mt11_github_intel_in_registry(self):
        """MT-11 (GitHub Intelligence) must exist in top 5-10 tier."""
        tasks = get_known_tasks(131)
        mt11 = [t for t in tasks if t.mt_id == 11]
        self.assertEqual(len(mt11), 1)
        self.assertGreaterEqual(mt11[0].base_value, 7)

    def test_mt14_autonomous_scanner_in_registry(self):
        """MT-14 (Autonomous Scanner) must exist."""
        tasks = get_known_tasks(131)
        mt14 = [t for t in tasks if t.mt_id == 14]
        self.assertEqual(len(mt14), 1)
        self.assertGreaterEqual(mt14[0].base_value, 6)

    def test_mt7_code_health_in_registry(self):
        """MT-7 (Code Health) must exist in growth tier."""
        tasks = get_known_tasks(131)
        mt7 = [t for t in tasks if t.mt_id == 7]
        self.assertEqual(len(mt7), 1)
        self.assertGreaterEqual(mt7[0].base_value, 5)

    def test_mt27_crown_jewel_bump(self):
        """MT-27 base_value bumped from 5 to 8 per S130 crown jewel status."""
        tasks = get_known_tasks(131)
        mt27 = [t for t in tasks if t.mt_id == 27]
        self.assertEqual(len(mt27), 1)
        self.assertGreaterEqual(mt27[0].base_value, 8)

    def test_active_tasks_ranked_by_score(self):
        """Active tasks should be ranked by improved_score descending."""
        picker = PriorityPicker(current_session=162)
        ranked = picker.ranked()
        if len(ranked) < 2:
            self.skipTest("Need at least 2 active tasks")
        for i in range(len(ranked) - 1):
            self.assertGreaterEqual(ranked[i].improved_score, ranked[i+1].improved_score)

    def test_mt22_desktop_electron_completed(self):
        """MT-22 completed — desktop Electron app automation validated by usage."""
        tasks = get_known_tasks(162)
        mt22 = [t for t in tasks if t.mt_id == 22]
        self.assertEqual(len(mt22), 1)
        self.assertEqual(mt22[0].status, TaskStatus.COMPLETED)
        self.assertEqual(mt22[0].base_value, 10)
        self.assertIn("Electron", mt22[0].name)

    def test_no_duplicate_mt_ids_after_reorder(self):
        """No duplicate MT IDs after adding new entries."""
        tasks = get_known_tasks(131)
        ids = [t.mt_id for t in tasks]
        self.assertEqual(len(ids), len(set(ids)), f"Duplicates: {[x for x in ids if ids.count(x) > 1]}")


class TestEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_zero_base_value(self):
        t = MasterTask(mt_id=99, name="Zero", base_value=0,
                      status=TaskStatus.ACTIVE, last_touched_session=90,
                      current_session=98)
        self.assertEqual(t.improved_score, 0.0)

    def test_max_completion(self):
        t = MasterTask(mt_id=99, name="Done", base_value=5,
                      status=TaskStatus.ACTIVE, last_touched_session=98,
                      current_session=98, phases_completed=10, phases_total=10)
        self.assertEqual(t.completion_pct, 100.0)
        self.assertEqual(t.completion_bonus, 3.0)
        self.assertEqual(t.roi_estimate, 2.0)

    def test_single_phase_task(self):
        t = MasterTask(mt_id=99, name="Single", base_value=3,
                      status=TaskStatus.ACTIVE, last_touched_session=98,
                      current_session=98, phases_completed=0, phases_total=1)
        self.assertEqual(t.completion_pct, 0.0)

    def test_picker_with_all_blocked(self):
        """PriorityPicker handles edge case of no active tasks."""
        picker = PriorityPicker(current_session=98)
        # Override tasks to all blocked
        picker.tasks = [
            MasterTask(mt_id=1, name="Blocked", base_value=5,
                      status=TaskStatus.BLOCKED, last_touched_session=90,
                      current_session=98, block_reason="test")
        ]
        self.assertEqual(len(picker.active_tasks()), 0)
        self.assertEqual(len(picker.ranked()), 0)
        self.assertEqual(len(picker.pick_next(3)), 0)

    def test_picker_empty(self):
        picker = PriorityPicker(current_session=98)
        picker.tasks = []
        self.assertEqual(len(picker.ranked()), 0)
        rec = picker.recommendations()
        self.assertIsInstance(rec, str)


class TestReopenMT(unittest.TestCase):
    """Tests for reopening completed MTs with new phases."""

    def test_reopen_completed_mt(self):
        """Reopening a completed MT makes it active with new phase."""
        picker = PriorityPicker(current_session=145)
        # MT-10 is COMPLETED
        mt10 = [t for t in picker.tasks if t.mt_id == 10][0]
        self.assertEqual(mt10.status, TaskStatus.COMPLETED)

        result = picker.reopen_mt(10, "Phase 7: New capability", 7)
        self.assertTrue(result)
        self.assertEqual(mt10.status, TaskStatus.ACTIVE)
        self.assertEqual(mt10.phases_total, 7)
        self.assertEqual(mt10.next_action, "Phase 7: New capability")
        self.assertIn(mt10, picker.active_tasks())

    def test_reopen_invalid_total_rejected(self):
        """Cannot reopen with phases_total <= phases_completed."""
        picker = PriorityPicker(current_session=145)
        result = picker.reopen_mt(10, "Bad reopen", 5)  # MT-10 has 6 completed
        self.assertFalse(result)

    def test_reopen_nonexistent_mt(self):
        """Reopening unknown MT returns False."""
        picker = PriorityPicker(current_session=145)
        self.assertFalse(picker.reopen_mt(999, "Nope", 5))

    def test_reopen_resets_last_touched(self):
        """Reopened MT gets current session as last_touched."""
        picker = PriorityPicker(current_session=150)
        picker.reopen_mt(26, "Tier 3 Phase 2 with numpy", 8)
        mt26 = [t for t in picker.tasks if t.mt_id == 26][0]
        self.assertEqual(mt26.last_touched_session, 150)

    def test_completed_tasks_list(self):
        """completed_tasks() returns only COMPLETED MTs."""
        picker = PriorityPicker(current_session=145)
        completed = picker.completed_tasks()
        self.assertTrue(all(t.status == TaskStatus.COMPLETED for t in completed))
        # MT-10, MT-26, MT-0 should all be in there
        completed_ids = {t.mt_id for t in completed}
        self.assertIn(10, completed_ids)
        self.assertIn(26, completed_ids)
        self.assertIn(0, completed_ids)


class TestRecurringTasks(unittest.TestCase):
    """Tests for recurring task staleness detection."""

    def test_recurring_task_creation(self):
        from priority_picker import RecurringTask
        rt = RecurringTask(
            task_id="nuclear_scan",
            name="Nuclear Reddit/GitHub scan",
            base_priority=8,
            staleness_days=3,
            last_run_date="2026-03-21",
            current_date="2026-03-24",
        )
        self.assertEqual(rt.days_stale, 3)

    def test_recurring_task_overdue(self):
        from priority_picker import RecurringTask
        rt = RecurringTask(
            task_id="nuclear_scan",
            name="Nuclear Reddit/GitHub scan",
            base_priority=8,
            staleness_days=3,
            last_run_date="2026-03-20",
            current_date="2026-03-24",
        )
        self.assertTrue(rt.is_overdue)
        self.assertEqual(rt.days_stale, 4)

    def test_recurring_task_not_overdue(self):
        from priority_picker import RecurringTask
        rt = RecurringTask(
            task_id="nuclear_scan",
            name="Nuclear Reddit/GitHub scan",
            base_priority=8,
            staleness_days=3,
            last_run_date="2026-03-23",
            current_date="2026-03-24",
        )
        self.assertFalse(rt.is_overdue)

    def test_recurring_task_score(self):
        from priority_picker import RecurringTask
        rt = RecurringTask(
            task_id="nuclear_scan",
            name="Nuclear Reddit/GitHub scan",
            base_priority=8,
            staleness_days=3,
            last_run_date="2026-03-20",
            current_date="2026-03-24",
        )
        # Overdue by 1 day: base + (days_over * 2) = 8 + 2 = 10
        self.assertEqual(rt.score, 10.0)

    def test_recurring_task_score_not_overdue(self):
        from priority_picker import RecurringTask
        rt = RecurringTask(
            task_id="nuclear_scan",
            name="Nuclear Reddit/GitHub scan",
            base_priority=8,
            staleness_days=3,
            last_run_date="2026-03-24",
            current_date="2026-03-24",
        )
        self.assertEqual(rt.score, 0.0)

    def test_recurring_task_never_run(self):
        from priority_picker import RecurringTask
        rt = RecurringTask(
            task_id="nuclear_scan",
            name="Nuclear Reddit/GitHub scan",
            base_priority=8,
            staleness_days=3,
            last_run_date=None,
            current_date="2026-03-24",
        )
        self.assertTrue(rt.is_overdue)
        # Never run = max staleness score (base + cap at 2x)
        self.assertGreaterEqual(rt.score, 8.0)


class TestGrowthActions(unittest.TestCase):
    """Tests for growth actions on completed MTs."""

    def test_growth_action_field(self):
        t = MasterTask(
            mt_id=10, name="YoYo", base_value=10,
            status=TaskStatus.COMPLETED, last_touched_session=125,
            current_session=149, phases_completed=6, phases_total=6,
            growth_action="Integrate ResearcherSkill convergence detection pattern",
            growth_priority=6,
        )
        self.assertEqual(t.growth_action, "Integrate ResearcherSkill convergence detection pattern")
        self.assertEqual(t.growth_priority, 6)

    def test_growth_action_default_none(self):
        t = MasterTask(
            mt_id=10, name="YoYo", base_value=10,
            status=TaskStatus.COMPLETED, last_touched_session=125,
            current_session=149, phases_completed=6, phases_total=6,
        )
        self.assertIsNone(t.growth_action)
        self.assertEqual(t.growth_priority, 0)

    def test_picker_growth_tasks(self):
        from priority_picker import PriorityPicker
        picker = PriorityPicker(current_session=149)
        # Override with test data
        picker.tasks = [
            MasterTask(mt_id=10, name="YoYo", base_value=10,
                      status=TaskStatus.COMPLETED, last_touched_session=125,
                      current_session=149, phases_completed=6, phases_total=6,
                      growth_action="Extend with convergence detection",
                      growth_priority=6),
            MasterTask(mt_id=99, name="No growth", base_value=8,
                      status=TaskStatus.COMPLETED, last_touched_session=100,
                      current_session=149, phases_completed=3, phases_total=3),
        ]
        growth = picker.growth_tasks()
        self.assertEqual(len(growth), 1)
        self.assertEqual(growth[0].mt_id, 10)


class TestDirectiveQueue(unittest.TestCase):
    """Tests for Matthew's explicit session directives."""

    def test_add_directive(self):
        from priority_picker import PriorityPicker, Directive
        picker = PriorityPicker(current_session=149)
        d = Directive(
            text="Nuclear reddit/github scan — subs 5-6 days stale",
            priority=9,
            source="S148",
        )
        picker.add_directive(d)
        self.assertEqual(len(picker.directives), 1)

    def test_directive_appears_in_full_ranking(self):
        from priority_picker import PriorityPicker, Directive
        picker = PriorityPicker(current_session=149)
        # Override tasks to a controlled set so directive is highest
        picker.tasks = [
            MasterTask(mt_id=1, name="Low", base_value=3,
                      status=TaskStatus.ACTIVE, last_touched_session=148,
                      current_session=149, phases_completed=1, phases_total=4),
        ]
        d = Directive(
            text="Nuclear reddit/github scan",
            priority=15,
            source="S148",
        )
        picker.add_directive(d)
        full = picker.full_ranking()
        self.assertGreater(len(full), 0)
        # Directive with priority 15 should beat MT with score ~4
        self.assertEqual(full[0]["type"], "directive")
        self.assertEqual(full[0]["score"], 15)

    def test_full_ranking_mixes_all_types(self):
        from priority_picker import PriorityPicker, Directive, RecurringTask
        picker = PriorityPicker(current_session=149)
        picker.add_directive(Directive("Do X", priority=5, source="S148"))
        picker.add_recurring(RecurringTask(
            task_id="scan", name="Scan", base_priority=8,
            staleness_days=3, last_run_date="2026-03-20",
            current_date="2026-03-24",
        ))
        full = picker.full_ranking()
        types = {item["type"] for item in full}
        # Should have at least mt and one of directive/recurring
        self.assertTrue(len(types) >= 2)

    def test_full_ranking_sorted_by_score(self):
        from priority_picker import PriorityPicker, Directive
        picker = PriorityPicker(current_session=149)
        picker.add_directive(Directive("Low", priority=1, source="test"))
        picker.add_directive(Directive("High", priority=99, source="test"))
        full = picker.full_ranking()
        scores = [item["score"] for item in full]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestFullRecommend(unittest.TestCase):
    """Tests for the enhanced recommendations output."""

    def test_recommend_shows_all_sections(self):
        from priority_picker import PriorityPicker, Directive, RecurringTask
        picker = PriorityPicker(current_session=149)
        picker.add_directive(Directive("Nuclear scan", priority=9, source="S148"))
        picker.add_recurring(RecurringTask(
            task_id="scan", name="Nuclear scan",
            base_priority=8, staleness_days=3,
            last_run_date="2026-03-20", current_date="2026-03-24",
        ))
        # Add a growth task
        picker.tasks = [
            MasterTask(mt_id=22, name="Desktop", base_value=10,
                      status=TaskStatus.ACTIVE, last_touched_session=142,
                      current_session=149, phases_completed=3, phases_total=4),
            MasterTask(mt_id=10, name="YoYo", base_value=10,
                      status=TaskStatus.COMPLETED, last_touched_session=125,
                      current_session=149, phases_completed=6, phases_total=6,
                      growth_action="Convergence detection", growth_priority=6),
        ]
        rec = picker.full_recommendations()
        self.assertIn("DIRECTIVES", rec)
        self.assertIn("OVERDUE", rec)
        self.assertIn("ACTIVE", rec)
        self.assertIn("GROWTH", rec)


if __name__ == "__main__":
    unittest.main()
