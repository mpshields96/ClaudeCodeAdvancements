"""Tests for mandate_monitor.py — cross-session mandate progress monitor."""
import json
import os
import tempfile
import unittest

from mandate_monitor import (
    DayRecord,
    MandateMonitor,
    TrajectoryAnalysis,
)


class TestDayRecord(unittest.TestCase):
    """Tests for DayRecord dataclass."""

    def test_win_rate_normal(self):
        r = DayRecord(day=1, date_str="2026-03-27", pnl=20.0, bets=64, wins=60, losses=4)
        self.assertAlmostEqual(r.win_rate(), 60 / 64)

    def test_win_rate_zero_bets(self):
        r = DayRecord(day=1, date_str="2026-03-27", pnl=0.0, bets=0, wins=0, losses=0)
        self.assertEqual(r.win_rate(), 0.0)

    def test_to_dict_roundtrip(self):
        r = DayRecord(day=2, date_str="2026-03-28", pnl=-5.0, bets=30, wins=27, losses=3)
        d = r.to_dict()
        r2 = DayRecord.from_dict(d)
        self.assertEqual(r.day, r2.day)
        self.assertEqual(r.pnl, r2.pnl)
        self.assertEqual(r.bets, r2.bets)

    def test_recorded_at_auto_set(self):
        r = DayRecord(day=1, date_str="2026-03-27", pnl=10.0, bets=50, wins=47, losses=3)
        self.assertTrue(len(r.recorded_at) > 0)

    def test_from_dict_ignores_extra_keys(self):
        d = {"day": 1, "date_str": "2026-03-27", "pnl": 5.0, "bets": 10,
             "wins": 9, "losses": 1, "recorded_at": "2026-03-27T00:00:00Z",
             "extra_key": "should_be_ignored"}
        r = DayRecord.from_dict(d)
        self.assertEqual(r.day, 1)


class TestMandateMonitor(unittest.TestCase):
    """Tests for MandateMonitor."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmpfile.close()
        self.monitor = MandateMonitor(state_file=self.tmpfile.name)

    def tearDown(self):
        if os.path.exists(self.tmpfile.name):
            os.remove(self.tmpfile.name)

    def test_empty_monitor(self):
        self.assertEqual(self.monitor.days_recorded(), 0)
        self.assertEqual(self.monitor.total_pnl(), 0.0)

    def test_record_day(self):
        r = self.monitor.record_day(1, "2026-03-27", 20.5, 64, 60, 4)
        self.assertEqual(r.day, 1)
        self.assertEqual(self.monitor.days_recorded(), 1)
        self.assertAlmostEqual(self.monitor.total_pnl(), 20.5)

    def test_record_multiple_days(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        self.monitor.record_day(2, "2026-03-28", 15.0, 55, 51, 4)
        self.monitor.record_day(3, "2026-03-29", -5.0, 40, 35, 5)
        self.assertEqual(self.monitor.days_recorded(), 3)
        self.assertAlmostEqual(self.monitor.total_pnl(), 30.0)

    def test_overwrite_existing_day(self):
        self.monitor.record_day(1, "2026-03-27", 10.0, 50, 47, 3)
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)  # correction
        self.assertEqual(self.monitor.days_recorded(), 1)
        self.assertAlmostEqual(self.monitor.total_pnl(), 20.0)

    def test_persistence_across_instances(self):
        self.monitor.record_day(1, "2026-03-27", 18.0, 60, 56, 4)
        self.monitor.record_day(2, "2026-03-28", 22.0, 70, 66, 4)
        # New instance reads from same file
        monitor2 = MandateMonitor(state_file=self.tmpfile.name)
        self.assertEqual(monitor2.days_recorded(), 2)
        self.assertAlmostEqual(monitor2.total_pnl(), 40.0)

    def test_clear(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        self.monitor.clear()
        self.assertEqual(self.monitor.days_recorded(), 0)
        self.assertFalse(os.path.exists(self.tmpfile.name))

    def test_day_summary(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        summary = self.monitor.day_summary(1)
        self.assertIn("Day 1", summary)
        self.assertIn("$+20.00", summary)
        self.assertIn("64 bets", summary)

    def test_day_summary_missing(self):
        self.assertIsNone(self.monitor.day_summary(1))

    def test_records_sorted_by_day(self):
        self.monitor.record_day(3, "2026-03-29", 10.0, 50, 47, 3)
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        self.monitor.record_day(2, "2026-03-28", 15.0, 55, 51, 4)
        days = [r.day for r in self.monitor.records]
        self.assertEqual(days, [1, 2, 3])


class TestTrajectoryAnalysis(unittest.TestCase):
    """Tests for trajectory analysis."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmpfile.close()
        self.monitor = MandateMonitor(state_file=self.tmpfile.name)

    def tearDown(self):
        if os.path.exists(self.tmpfile.name):
            os.remove(self.tmpfile.name)

    def test_no_data_analysis(self):
        a = self.monitor.analyze()
        self.assertEqual(a.days_recorded, 0)
        self.assertEqual(a.pace_verdict, "NO_DATA")
        self.assertEqual(a.trend, "INSUFFICIENT_DATA")

    def test_ahead_pace(self):
        self.monitor.record_day(1, "2026-03-27", 28.0, 80, 76, 4)
        a = self.monitor.analyze()
        self.assertEqual(a.pace_verdict, "AHEAD")

    def test_on_track_pace(self):
        self.monitor.record_day(1, "2026-03-27", 18.0, 64, 60, 4)
        a = self.monitor.analyze()
        self.assertEqual(a.pace_verdict, "ON_TRACK")

    def test_behind_pace(self):
        self.monitor.record_day(1, "2026-03-27", 10.0, 40, 37, 3)
        a = self.monitor.analyze()
        self.assertEqual(a.pace_verdict, "BEHIND")

    def test_critical_pace(self):
        self.monitor.record_day(1, "2026-03-27", 2.0, 10, 9, 1)
        a = self.monitor.analyze()
        self.assertEqual(a.pace_verdict, "CRITICAL")

    def test_projected_total(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        a = self.monitor.analyze()
        self.assertAlmostEqual(a.projected_total, 100.0)  # 20 * 5 days

    def test_needed_daily_rate(self):
        self.monitor.record_day(1, "2026-03-27", 10.0, 50, 47, 3)
        a = self.monitor.analyze()
        # Target: 15 * 5 = 75. After day 1: 10. Need 65 in 4 days = 16.25/day
        self.assertAlmostEqual(a.needed_daily_rate, 16.25)

    def test_overall_win_rate(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        self.monitor.record_day(2, "2026-03-28", 15.0, 50, 46, 4)
        a = self.monitor.analyze()
        self.assertAlmostEqual(a.overall_wr, 106 / 114)

    def test_trend_improving(self):
        self.monitor.record_day(1, "2026-03-27", 10.0, 50, 47, 3)
        self.monitor.record_day(2, "2026-03-28", 25.0, 70, 66, 4)
        a = self.monitor.analyze()
        self.assertEqual(a.trend, "IMPROVING")

    def test_trend_declining(self):
        self.monitor.record_day(1, "2026-03-27", 25.0, 70, 66, 4)
        self.monitor.record_day(2, "2026-03-28", 5.0, 30, 27, 3)
        a = self.monitor.analyze()
        self.assertEqual(a.trend, "DECLINING")

    def test_trend_stable(self):
        self.monitor.record_day(1, "2026-03-27", 18.0, 60, 56, 4)
        self.monitor.record_day(2, "2026-03-28", 19.0, 62, 58, 4)
        a = self.monitor.analyze()
        self.assertEqual(a.trend, "STABLE")

    def test_trend_insufficient_data(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        a = self.monitor.analyze()
        self.assertEqual(a.trend, "INSUFFICIENT_DATA")

    def test_consecutive_red_days(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        self.monitor.record_day(2, "2026-03-28", -3.0, 30, 26, 4)
        self.monitor.record_day(3, "2026-03-29", -5.0, 25, 21, 4)
        a = self.monitor.analyze()
        self.assertEqual(a.consecutive_red_days, 2)

    def test_no_consecutive_red_days(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        self.monitor.record_day(2, "2026-03-28", 15.0, 55, 51, 4)
        a = self.monitor.analyze()
        self.assertEqual(a.consecutive_red_days, 0)

    def test_best_worst_day(self):
        self.monitor.record_day(1, "2026-03-27", 25.0, 70, 66, 4)
        self.monitor.record_day(2, "2026-03-28", -8.0, 30, 24, 6)
        self.monitor.record_day(3, "2026-03-29", 15.0, 55, 51, 4)
        a = self.monitor.analyze()
        self.assertAlmostEqual(a.best_day_pnl, 25.0)
        self.assertAlmostEqual(a.worst_day_pnl, -8.0)

    def test_days_remaining(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        self.monitor.record_day(2, "2026-03-28", 18.0, 60, 56, 4)
        a = self.monitor.analyze()
        self.assertEqual(a.days_remaining, 3)

    def test_full_mandate_zero_remaining(self):
        for i in range(1, 6):
            self.monitor.record_day(i, f"2026-03-{26+i}", 20.0, 64, 60, 4)
        a = self.monitor.analyze()
        self.assertEqual(a.days_remaining, 0)

    def test_to_dict(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        a = self.monitor.analyze()
        d = a.to_dict()
        self.assertIn("pace_verdict", d)
        self.assertIn("projected_total", d)
        self.assertIn("trend", d)


class TestTrajectoryText(unittest.TestCase):
    """Tests for text output."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmpfile.close()
        self.monitor = MandateMonitor(state_file=self.tmpfile.name)

    def tearDown(self):
        if os.path.exists(self.tmpfile.name):
            os.remove(self.tmpfile.name)

    def test_empty_trajectory_text(self):
        text = self.monitor.trajectory_text()
        self.assertIn("No data", text)

    def test_trajectory_text_with_data(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        text = self.monitor.trajectory_text()
        self.assertIn("MANDATE MONITOR", text)
        self.assertIn("Day 1/5", text)
        self.assertIn("$+20.00", text)

    def test_health_check_no_data(self):
        text = self.monitor.health_check()
        self.assertIn("awaiting", text)

    def test_health_check_with_data(self):
        self.monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        text = self.monitor.health_check()
        self.assertIn("MANDATE Day 1/5", text)
        self.assertIn("ON_TRACK", text)

    def test_red_day_warning_in_text(self):
        self.monitor.record_day(1, "2026-03-27", -5.0, 30, 25, 5)
        text = self.monitor.trajectory_text()
        self.assertIn("WARNING", text)
        self.assertIn("consecutive red", text)


class TestJsonlPersistence(unittest.TestCase):
    """Tests for JSONL file format and corruption handling."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmpfile.close()

    def tearDown(self):
        if os.path.exists(self.tmpfile.name):
            os.remove(self.tmpfile.name)

    def test_jsonl_format(self):
        monitor = MandateMonitor(state_file=self.tmpfile.name)
        monitor.record_day(1, "2026-03-27", 20.0, 64, 60, 4)
        with open(self.tmpfile.name) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertEqual(data["day"], 1)
        self.assertEqual(data["pnl"], 20.0)

    def test_handles_corrupted_lines(self):
        with open(self.tmpfile.name, "w") as f:
            f.write('{"day":1,"date_str":"2026-03-27","pnl":20.0,"bets":64,"wins":60,"losses":4,"recorded_at":"2026-03-27T00:00:00Z"}\n')
            f.write("CORRUPTED LINE\n")
            f.write('{"day":2,"date_str":"2026-03-28","pnl":15.0,"bets":55,"wins":51,"losses":4,"recorded_at":"2026-03-28T00:00:00Z"}\n')
        monitor = MandateMonitor(state_file=self.tmpfile.name)
        self.assertEqual(monitor.days_recorded(), 2)  # skips corrupted line

    def test_nonexistent_file(self):
        monitor = MandateMonitor(state_file="/tmp/nonexistent_mandate_test.jsonl")
        self.assertEqual(monitor.days_recorded(), 0)


if __name__ == "__main__":
    unittest.main()
