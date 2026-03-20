#!/usr/bin/env python3
"""
Tests for overhead_timer.py — Measures coordination overhead vs productive work
for hivemind Phase 1 metrics.

TDD: Tests first.
"""

import json
import os
import sys
import tempfile
import time
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

import overhead_timer as ot


class TestOverheadTimer(unittest.TestCase):
    """Test the overhead timer API."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "overhead_log.jsonl")

    def test_start_stop_coordination(self):
        timer = ot.OverheadTimer()
        timer.start("coordination")
        time.sleep(0.01)
        elapsed = timer.stop()
        self.assertGreater(elapsed, 0)
        self.assertEqual(timer.current_type, None)

    def test_start_stop_work(self):
        timer = ot.OverheadTimer()
        timer.start("work")
        time.sleep(0.01)
        elapsed = timer.stop()
        self.assertGreater(elapsed, 0)

    def test_get_ratio_no_time(self):
        timer = ot.OverheadTimer()
        ratio = timer.get_ratio()
        self.assertEqual(ratio, 0.0)

    def test_get_ratio_all_coordination(self):
        timer = ot.OverheadTimer()
        timer.coordination_seconds = 10.0
        timer.work_seconds = 0.0
        ratio = timer.get_ratio()
        self.assertEqual(ratio, 1.0)

    def test_get_ratio_all_work(self):
        timer = ot.OverheadTimer()
        timer.coordination_seconds = 0.0
        timer.work_seconds = 10.0
        ratio = timer.get_ratio()
        self.assertEqual(ratio, 0.0)

    def test_get_ratio_mixed(self):
        timer = ot.OverheadTimer()
        timer.coordination_seconds = 2.0
        timer.work_seconds = 8.0
        ratio = timer.get_ratio()
        self.assertAlmostEqual(ratio, 0.2, places=2)

    def test_accumulates_across_segments(self):
        timer = ot.OverheadTimer()
        timer.start("coordination")
        time.sleep(0.01)
        timer.stop()
        timer.start("work")
        time.sleep(0.01)
        timer.stop()
        timer.start("coordination")
        time.sleep(0.01)
        timer.stop()
        self.assertGreater(timer.coordination_seconds, 0)
        self.assertGreater(timer.work_seconds, 0)

    def test_invalid_type_raises(self):
        timer = ot.OverheadTimer()
        with self.assertRaises(ValueError):
            timer.start("invalid")

    def test_double_start_raises(self):
        timer = ot.OverheadTimer()
        timer.start("work")
        with self.assertRaises(RuntimeError):
            timer.start("coordination")

    def test_stop_without_start_raises(self):
        timer = ot.OverheadTimer()
        with self.assertRaises(RuntimeError):
            timer.stop()

    def test_format_summary(self):
        timer = ot.OverheadTimer()
        timer.coordination_seconds = 30.0
        timer.work_seconds = 270.0
        summary = timer.format_summary()
        self.assertIn("10.0%", summary)
        self.assertIn("coordination", summary.lower())

    def test_save_and_load(self):
        timer = ot.OverheadTimer()
        timer.coordination_seconds = 5.0
        timer.work_seconds = 45.0
        timer.save(90, path=self.log_path)

        entries = ot.load_history(path=self.log_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["session"], 90)
        self.assertAlmostEqual(entries[0]["ratio"], 0.1, places=2)

    def test_avg_overhead_across_sessions(self):
        t1 = ot.OverheadTimer()
        t1.coordination_seconds = 10.0
        t1.work_seconds = 90.0
        t1.save(90, path=self.log_path)

        t2 = ot.OverheadTimer()
        t2.coordination_seconds = 20.0
        t2.work_seconds = 80.0
        t2.save(91, path=self.log_path)

        avg = ot.avg_overhead(path=self.log_path)
        self.assertAlmostEqual(avg, 0.15, places=2)


if __name__ == "__main__":
    unittest.main()
