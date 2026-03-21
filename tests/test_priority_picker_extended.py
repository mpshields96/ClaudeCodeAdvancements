#!/usr/bin/env python3
"""Extended edge-case tests for priority_picker.py.

Targets: all tasks blocked, empty MASTER_TASKS.md, malformed entries,
zero-score edge cases, stagnation penalty overflow/boundary conditions.

Complements tests/test_priority_picker.py (55 tests — base coverage).
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from priority_picker import (
    MasterTask, TaskStatus, Urgency, PriorityPicker, get_known_tasks
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kwargs) -> MasterTask:
    """Create a MasterTask with sensible defaults overrideable by kwargs."""
    defaults = {
        "mt_id": 99, "name": "Test Task", "base_value": 5,
        "status": TaskStatus.ACTIVE, "last_touched_session": 90,
        "current_session": 98, "phases_completed": 1,
        "phases_total": 4, "aging_rate": 1.0,
    }
    defaults.update(kwargs)
    return MasterTask(**defaults)


def _blocked_picker() -> PriorityPicker:
    """PriorityPicker where all tasks are blocked with NO self-resolution note."""
    picker = PriorityPicker(current_session=98)
    picker.tasks = [
        MasterTask(mt_id=1, name="Blocked A", base_value=5,
                   status=TaskStatus.BLOCKED, last_touched_session=90,
                   current_session=98, block_reason="external dependency"),
        MasterTask(mt_id=2, name="Blocked B", base_value=8,
                   status=TaskStatus.BLOCKED, last_touched_session=80,
                   current_session=98, block_reason="waiting on Anthropic"),
    ]
    return picker


def _empty_picker() -> PriorityPicker:
    picker = PriorityPicker(current_session=98)
    picker.tasks = []
    return picker


# ---------------------------------------------------------------------------
# All Tasks Blocked (no unblockable self-resolution notes)
# ---------------------------------------------------------------------------

class TestAllTasksBlocked(unittest.TestCase):
    """PriorityPicker with only blocked tasks that have no self-resolution notes."""

    def test_active_tasks_returns_empty(self):
        self.assertEqual(len(_blocked_picker().active_tasks()), 0)

    def test_ranked_returns_empty(self):
        self.assertEqual(len(_blocked_picker().ranked()), 0)

    def test_pick_next_returns_empty(self):
        self.assertEqual(len(_blocked_picker().pick_next(3)), 0)

    def test_stagnating_returns_empty(self):
        """stagnating() only inspects active tasks — blocked tasks are invisible."""
        self.assertEqual(len(_blocked_picker().stagnating()), 0)

    def test_near_complete_returns_empty(self):
        self.assertEqual(len(_blocked_picker().near_complete()), 0)

    def test_unblockable_returns_empty_when_no_self_resolution(self):
        """Tasks without self_resolution_note do not qualify as unblockable."""
        self.assertEqual(len(_blocked_picker().unblockable_tasks()), 0)

    def test_include_blocked_still_empty_without_self_resolution(self):
        """ranked(include_blocked=True) returns empty if no self-resolution notes."""
        self.assertEqual(len(_blocked_picker().ranked(include_blocked=True)), 0)

    def test_summary_table_has_header_only(self):
        table = _blocked_picker().summary_table()
        self.assertIn("| Rank |", table)
        # Data rows start with "| <digit>" — should be zero
        data_rows = [
            ln for ln in table.split("\n")
            if ln.startswith("| ") and "Rank" not in ln and not ln.startswith("|---")
        ]
        self.assertEqual(len(data_rows), 0)

    def test_recommendations_has_no_top_pick(self):
        rec = _blocked_picker().recommendations()
        self.assertNotIn("TOP PICK", rec)

    def test_to_json_returns_empty_list(self):
        data = json.loads(_blocked_picker().to_json())
        self.assertEqual(data, [])

    def test_blocked_tasks_are_counted(self):
        """blocked_tasks() should still see them even though active_tasks() is empty."""
        blocked = _blocked_picker().blocked_tasks()
        self.assertEqual(len(blocked), 2)


# ---------------------------------------------------------------------------
# Empty Task List (MASTER_TASKS.md scenario — nothing parsed)
# ---------------------------------------------------------------------------

class TestEmptyTaskList(unittest.TestCase):
    """PriorityPicker with completely empty task list."""

    def test_active_tasks_empty(self):
        self.assertEqual(len(_empty_picker().active_tasks()), 0)

    def test_blocked_tasks_empty(self):
        self.assertEqual(len(_empty_picker().blocked_tasks()), 0)

    def test_unblockable_tasks_empty(self):
        self.assertEqual(len(_empty_picker().unblockable_tasks()), 0)

    def test_ranked_empty(self):
        self.assertEqual(len(_empty_picker().ranked()), 0)

    def test_ranked_with_blocked_empty(self):
        self.assertEqual(len(_empty_picker().ranked(include_blocked=True)), 0)

    def test_pick_next_returns_empty(self):
        self.assertEqual(len(_empty_picker().pick_next(5)), 0)

    def test_stagnating_empty(self):
        self.assertEqual(len(_empty_picker().stagnating()), 0)

    def test_near_complete_empty(self):
        self.assertEqual(len(_empty_picker().near_complete()), 0)

    def test_to_json_returns_empty_array(self):
        data = json.loads(_empty_picker().to_json())
        self.assertEqual(data, [])

    def test_recommendations_returns_string_not_crash(self):
        rec = _empty_picker().recommendations()
        self.assertIsInstance(rec, str)

    def test_recommendations_has_no_top_pick(self):
        self.assertNotIn("TOP PICK", _empty_picker().recommendations())

    def test_summary_table_has_header(self):
        table = _empty_picker().summary_table()
        self.assertIn("| Rank |", table)


# ---------------------------------------------------------------------------
# Malformed / Boundary Entries
# ---------------------------------------------------------------------------

class TestMalformedEntries(unittest.TestCase):
    """Unusual but possible task configurations that must not raise exceptions."""

    def test_phases_completed_exceeds_phases_total(self):
        """completion_pct > 100 is possible if data is inconsistent — must not crash."""
        t = _task(phases_completed=6, phases_total=5)
        self.assertGreater(t.completion_pct, 100.0)

    def test_phases_exceed_total_still_gives_max_bonus(self):
        """completion_pct > 90 still awards the 3-point completion bonus."""
        t = _task(phases_completed=10, phases_total=5)
        self.assertEqual(t.completion_bonus, 3.0)

    def test_phases_exceed_total_still_gives_max_roi(self):
        """completion_pct > 85 still awards the 2-point ROI estimate."""
        t = _task(phases_completed=10, phases_total=5)
        self.assertEqual(t.roi_estimate, 2.0)

    def test_last_touched_after_current_session_is_negative(self):
        """Future-dated touch gives negative sessions_since_touch — no crash."""
        t = _task(last_touched_session=200, current_session=98)
        self.assertLess(t.sessions_since_touch, 0)

    def test_future_touch_no_stagnation_flag(self):
        """Negative sessions_since_touch never triggers stagnation."""
        t = _task(base_value=1, last_touched_session=200, current_session=98)
        self.assertFalse(t.stagnation_flag)

    def test_zero_aging_rate_produces_no_raw_aging(self):
        """aging_rate=0 means no aging regardless of how long untouched."""
        t = _task(base_value=5, last_touched_session=1, current_session=98, aging_rate=0.0)
        self.assertEqual(t.raw_aging, 0.0)
        self.assertEqual(t.aging_capped, 0.0)

    def test_zero_aging_rate_prevents_stagnation_flag_for_positive_base(self):
        """With aging_rate=0, aging_capped=0 < base_value → stagnation=False."""
        t = _task(base_value=5, last_touched_session=1, current_session=98, aging_rate=0.0)
        # 0 >= 5 is False, so flag can't be True
        self.assertFalse(t.stagnation_flag)

    def test_very_long_task_name_in_summary_table(self):
        """100-char name is truncated (next_action[:50]) without crashing."""
        picker = PriorityPicker(current_session=98)
        picker.tasks = [
            MasterTask(mt_id=1, name="X" * 100, base_value=5,
                       status=TaskStatus.ACTIVE, last_touched_session=95,
                       current_session=98, next_action="A" * 100)
        ]
        table = picker.summary_table()
        self.assertIn("| Rank |", table)
        self.assertIn("MT-1", table)


# ---------------------------------------------------------------------------
# Zero-Score Edge Cases
# ---------------------------------------------------------------------------

class TestZeroScoreEdgeCases(unittest.TestCase):
    """Zero and near-zero score boundary conditions."""

    def test_fresh_task_score_equals_base_value(self):
        """Task just touched, 0% complete, no bonuses = exactly base_value."""
        t = _task(base_value=7, last_touched_session=98, current_session=98,
                  phases_completed=0, phases_total=4)
        # base=7, aging=0, bonus=0, roi=0, stag=0
        self.assertAlmostEqual(t.improved_score, 7.0)

    def test_zero_base_zero_aging_zero_score(self):
        """base=0, touched this session, no phases = score of 0."""
        t = _task(base_value=0, last_touched_session=98, current_session=98,
                  phases_completed=0, phases_total=4)
        self.assertAlmostEqual(t.improved_score, 0.0)

    def test_stagnation_caps_max_score_to_2x_base_minus_one(self):
        """Stagnating task: max score is (2 * base_value - 1) not (2 * base_value)."""
        t = _task(base_value=5, last_touched_session=None, current_session=98,
                  phases_completed=0, phases_total=4)
        # base=5, aging=5(capped), stag=-1 → 9.0
        self.assertAlmostEqual(t.improved_score, 9.0)

    def test_pick_next_more_than_available_returns_all(self):
        """Requesting N tasks when only 1 exists returns the 1, not crash."""
        picker = PriorityPicker(current_session=98)
        picker.tasks = [_task(mt_id=1, last_touched_session=98, current_session=98)]
        result = picker.pick_next(10)
        self.assertEqual(len(result), 1)

    def test_two_identical_score_tasks_both_ranked(self):
        """Tied scores — both tasks appear in ranked output."""
        picker = PriorityPicker(current_session=98)
        t1 = _task(mt_id=1, base_value=5, last_touched_session=98, current_session=98,
                   phases_completed=0, phases_total=4)
        t2 = _task(mt_id=2, base_value=5, last_touched_session=98, current_session=98,
                   phases_completed=0, phases_total=4)
        picker.tasks = [t1, t2]
        ranked = picker.ranked()
        self.assertEqual(len(ranked), 2)
        self.assertAlmostEqual(ranked[0].improved_score, ranked[1].improved_score)

    def test_single_task_picker_top_pick(self):
        """With one task, it's always the top pick."""
        picker = PriorityPicker(current_session=98)
        picker.tasks = [_task(mt_id=42)]
        top = picker.pick_next(1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0].mt_id, 42)


# ---------------------------------------------------------------------------
# Stagnation Penalty — Boundary and Overflow
# ---------------------------------------------------------------------------

class TestStagnationPenaltyBoundary(unittest.TestCase):
    """Boundary and overflow conditions for stagnation_flag and stagnation_penalty."""

    def test_stagnation_triggers_at_exactly_10_sessions(self):
        """Boundary: exactly 10 sessions since touch + at cap → stagnating."""
        t = _task(base_value=3, last_touched_session=88, current_session=98,
                  phases_completed=0, phases_total=4)
        # sessions_since_touch=10, raw_aging=10, capped=3, 3>=3 AND 10>=10
        self.assertTrue(t.stagnation_flag)
        self.assertEqual(t.stagnation_penalty, -1.0)

    def test_stagnation_does_not_trigger_at_9_sessions(self):
        """9 sessions since touch: below 10-session threshold → no stagnation."""
        t = _task(base_value=3, last_touched_session=89, current_session=98,
                  phases_completed=0, phases_total=4)
        # sessions_since_touch=9, 9 < 10 → False
        self.assertFalse(t.stagnation_flag)
        self.assertEqual(t.stagnation_penalty, 0.0)

    def test_stagnation_penalty_is_fixed_minus_one(self):
        """Penalty is always exactly -1.0 regardless of how long stagnating."""
        barely_stagnating = _task(base_value=3, last_touched_session=88, current_session=98,
                                  phases_completed=0, phases_total=4)
        very_stagnating = _task(base_value=3, last_touched_session=None, current_session=98,
                                phases_completed=0, phases_total=4)
        self.assertEqual(barely_stagnating.stagnation_penalty, -1.0)
        self.assertEqual(very_stagnating.stagnation_penalty, -1.0)

    def test_stagnation_penalty_does_not_compound_across_tasks(self):
        """Two stagnating tasks each carry -1.0 individually — they don't compound."""
        picker = PriorityPicker(current_session=98)
        picker.tasks = [
            _task(mt_id=1, base_value=2, last_touched_session=None, current_session=98,
                  phases_completed=0, phases_total=4),
            _task(mt_id=2, base_value=2, last_touched_session=None, current_session=98,
                  phases_completed=0, phases_total=4),
        ]
        stagnating = picker.stagnating()
        self.assertEqual(len(stagnating), 2)
        for t in stagnating:
            self.assertEqual(t.stagnation_penalty, -1.0)

    def test_stagnation_flag_requires_cap_reached(self):
        """At cap AND 10+ sessions: flag True. Under cap AND 10+ sessions: flag False."""
        at_cap = _task(base_value=5, last_touched_session=85, current_session=98,
                       phases_completed=0, phases_total=4)
        # sessions=13, aging=13 capped at 5 = 5 >= 5 → True
        self.assertTrue(at_cap.stagnation_flag)

        under_cap = _task(base_value=100, last_touched_session=85, current_session=98,
                          phases_completed=0, phases_total=4)
        # sessions=13, aging=13 < 100 → False
        self.assertFalse(under_cap.stagnation_flag)

    def test_stagnation_score_stays_positive_for_high_base(self):
        """High base_value tasks remain positive even with stagnation penalty."""
        t = _task(base_value=10, last_touched_session=None, current_session=98,
                  phases_completed=0, phases_total=4)
        # base=10, aging=10(capped), stag=-1 → score=19
        self.assertGreater(t.improved_score, 0)
        self.assertAlmostEqual(t.improved_score, 19.0)

    def test_stagnation_flag_false_when_at_cap_but_under_10_sessions(self):
        """At cap but only 9 sessions → not stagnating."""
        t = _task(base_value=3, last_touched_session=89, current_session=98,
                  phases_completed=0, phases_total=4)
        # aging=9, capped=3 >= 3, but sessions=9 < 10 → False
        self.assertFalse(t.stagnation_flag)

    def test_multiple_stagnating_tasks_in_picker_all_returned(self):
        """picker.stagnating() returns all stagnating active tasks."""
        picker = PriorityPicker(current_session=98)
        picker.tasks = [
            _task(mt_id=1, base_value=2, last_touched_session=None, current_session=98,
                  phases_completed=0, phases_total=4),
            _task(mt_id=2, base_value=3, last_touched_session=85, current_session=98,
                  phases_completed=0, phases_total=4),
            _task(mt_id=3, base_value=5, last_touched_session=97, current_session=98,
                  phases_completed=0, phases_total=4),  # NOT stagnating (only 1 session)
        ]
        stagnating = picker.stagnating()
        stagnating_ids = {t.mt_id for t in stagnating}
        self.assertIn(1, stagnating_ids)
        self.assertIn(2, stagnating_ids)
        self.assertNotIn(3, stagnating_ids)


# ---------------------------------------------------------------------------
# Unblockable Task Edge Cases
# ---------------------------------------------------------------------------

class TestUnblockableEdgeCases(unittest.TestCase):
    """Edge cases around self-resolution note parsing for unblockable tasks."""

    def test_blocked_task_with_mostly_self_resolved_is_unblockable(self):
        picker = PriorityPicker(current_session=98)
        picker.tasks = [
            MasterTask(mt_id=1, name="Mostly Done", base_value=5,
                       status=TaskStatus.BLOCKED, last_touched_session=90,
                       current_session=98, block_reason="old reason",
                       self_resolution_note="MOSTLY SELF-RESOLVED: Try X.")
        ]
        self.assertEqual(len(picker.unblockable_tasks()), 1)

    def test_blocked_task_with_partial_self_resolved_is_unblockable(self):
        picker = PriorityPicker(current_session=98)
        picker.tasks = [
            MasterTask(mt_id=2, name="Partially Done", base_value=5,
                       status=TaskStatus.BLOCKED, last_touched_session=90,
                       current_session=98, block_reason="some blocker",
                       self_resolution_note="PARTIALLY SELF-RESOLVED: Check bridge tools.")
        ]
        self.assertEqual(len(picker.unblockable_tasks()), 1)

    def test_blocked_task_with_still_open_note_is_not_unblockable(self):
        """'STILL OPEN' note does not qualify for unblockable."""
        picker = PriorityPicker(current_session=98)
        picker.tasks = [
            MasterTask(mt_id=3, name="Still Blocked", base_value=5,
                       status=TaskStatus.BLOCKED, last_touched_session=90,
                       current_session=98, block_reason="hard blocker",
                       self_resolution_note="STILL OPEN: Not self-resolving.")
        ]
        self.assertEqual(len(picker.unblockable_tasks()), 0)

    def test_unblockable_tasks_included_in_ranked_with_flag(self):
        """ranked(include_blocked=True) includes unblockable tasks."""
        picker = PriorityPicker(current_session=98)
        picker.tasks = [
            MasterTask(mt_id=1, name="Unblockable", base_value=5,
                       status=TaskStatus.BLOCKED, last_touched_session=90,
                       current_session=98, block_reason="x",
                       self_resolution_note="MOSTLY SELF-RESOLVED: just test.")
        ]
        with_blocked = picker.ranked(include_blocked=True)
        without_blocked = picker.ranked(include_blocked=False)
        self.assertEqual(len(with_blocked), 1)
        self.assertEqual(len(without_blocked), 0)


# ---------------------------------------------------------------------------
# Urgency Classification Edge Cases
# ---------------------------------------------------------------------------

class TestUrgencyEdgeCases(unittest.TestCase):
    """Urgency classification at boundaries."""

    def test_urgency_near_complete_at_exactly_75_percent(self):
        """75% completion is the threshold for NEAR_COMPLETE."""
        t = _task(phases_completed=3, phases_total=4, last_touched_session=97,
                  current_session=98)  # 75%
        self.assertEqual(t.urgency, Urgency.NEAR_COMPLETE)

    def test_urgency_aging_at_exactly_5_sessions(self):
        """sessions_since_touch == 5 → AGING (not STAGNATING, not ROUTINE)."""
        t = _task(base_value=100, last_touched_session=93, current_session=98,
                  phases_completed=0, phases_total=4)
        # sessions=5, aging=5 < 100 cap → not stagnating; completion<75% → not near_complete
        self.assertEqual(t.urgency, Urgency.AGING)

    def test_urgency_routine_at_4_sessions(self):
        """4 sessions since touch → ROUTINE."""
        t = _task(base_value=100, last_touched_session=94, current_session=98,
                  phases_completed=0, phases_total=4)
        self.assertEqual(t.urgency, Urgency.ROUTINE)

    def test_near_complete_takes_priority_over_stagnating_in_urgency(self):
        """75%+ completion → NEAR_COMPLETE even if also flagged stagnating."""
        t = _task(base_value=3, last_touched_session=None, current_session=98,
                  phases_completed=3, phases_total=4)  # 75%, stagnating
        # Urgency check: completion_pct >= 75 is checked FIRST
        self.assertEqual(t.urgency, Urgency.NEAR_COMPLETE)


if __name__ == "__main__":
    unittest.main()
