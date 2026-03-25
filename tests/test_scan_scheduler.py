#!/usr/bin/env python3
"""Tests for scan_scheduler.py — MT-40: Automated Nuclear Scanning Loop."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scan_scheduler import (
    ScanScheduler,
    ScanRecommendation,
    SubStaleness,
    SCAN_POLICIES,
)


def make_registry_data(subs_and_ages: dict[str, int]) -> dict:
    """Create mock scan registry data. ages in days."""
    data = {}
    now = datetime.now(timezone.utc)
    for slug, days_ago in subs_and_ages.items():
        ts = (now - timedelta(days=days_ago)).isoformat()
        data[slug] = {"last_scan": ts, "posts_scanned": 50, "builds": 1, "adapts": 2}
    return data


class TestScanPolicies(unittest.TestCase):

    def test_policies_exist_for_key_subs(self):
        self.assertIn("claudecode", SCAN_POLICIES)
        self.assertIn("claudeai", SCAN_POLICIES)
        self.assertIn("vibecoding", SCAN_POLICIES)

    def test_policy_has_required_fields(self):
        for slug, policy in SCAN_POLICIES.items():
            self.assertIn("max_age_days", policy)
            self.assertIn("priority", policy)
            self.assertGreater(policy["max_age_days"], 0)


class TestSubStaleness(unittest.TestCase):

    def test_stale_sub(self):
        s = SubStaleness("claudecode", days_since_scan=5, max_age_days=3, priority=10)
        self.assertTrue(s.is_stale)
        self.assertEqual(s.days_overdue, 2)

    def test_fresh_sub(self):
        s = SubStaleness("claudecode", days_since_scan=1, max_age_days=3, priority=10)
        self.assertFalse(s.is_stale)
        self.assertEqual(s.days_overdue, 0)

    def test_never_scanned(self):
        s = SubStaleness("claudecode", days_since_scan=999, max_age_days=3, priority=10)
        self.assertTrue(s.is_stale)

    def test_urgency_score(self):
        s = SubStaleness("claudecode", days_since_scan=10, max_age_days=3, priority=10)
        # urgency = priority * (days_overdue / max_age_days)
        self.assertGreater(s.urgency, 0)

    def test_exact_boundary(self):
        s = SubStaleness("claudecode", days_since_scan=3, max_age_days=3, priority=10)
        self.assertFalse(s.is_stale)  # exactly at threshold = not stale yet


class TestScanScheduler(unittest.TestCase):

    def test_all_fresh(self):
        data = make_registry_data({"claudecode": 1, "claudeai": 2, "vibecoding": 1})
        sched = ScanScheduler(registry_data=data)
        rec = sched.recommend()
        self.assertEqual(rec.action, "OK")
        self.assertEqual(len(rec.stale_subs), 0)

    def test_one_stale(self):
        data = make_registry_data({"claudecode": 5, "claudeai": 1, "vibecoding": 1})
        sched = ScanScheduler(registry_data=data)
        rec = sched.recommend()
        self.assertEqual(rec.action, "SCAN_NOW")
        self.assertEqual(len(rec.stale_subs), 1)
        self.assertEqual(rec.stale_subs[0].slug, "claudecode")

    def test_multiple_stale_sorted_by_urgency(self):
        data = make_registry_data({"claudecode": 10, "claudeai": 8, "vibecoding": 5})
        sched = ScanScheduler(registry_data=data)
        rec = sched.recommend()
        self.assertEqual(rec.action, "SCAN_NOW")
        self.assertGreater(len(rec.stale_subs), 1)
        # Should be sorted by urgency descending
        urgencies = [s.urgency for s in rec.stale_subs]
        self.assertEqual(urgencies, sorted(urgencies, reverse=True))

    def test_missing_sub_treated_as_never_scanned(self):
        data = make_registry_data({"claudeai": 1})  # claudecode missing
        sched = ScanScheduler(registry_data=data)
        rec = sched.recommend()
        # claudecode is in policies but not in data -> never scanned -> stale
        stale_slugs = [s.slug for s in rec.stale_subs]
        self.assertIn("claudecode", stale_slugs)

    def test_empty_registry(self):
        sched = ScanScheduler(registry_data={})
        rec = sched.recommend()
        self.assertEqual(rec.action, "SCAN_NOW")
        # All policy subs should be stale
        self.assertGreater(len(rec.stale_subs), 0)

    def test_top_target(self):
        data = make_registry_data({"claudecode": 10, "claudeai": 1, "vibecoding": 1})
        sched = ScanScheduler(registry_data=data)
        rec = sched.recommend()
        self.assertEqual(rec.top_target, "claudecode")

    def test_format_brief(self):
        data = make_registry_data({"claudecode": 5})
        sched = ScanScheduler(registry_data=data)
        rec = sched.recommend()
        brief = rec.format_brief()
        self.assertIn("claudecode", brief)
        self.assertIn("SCAN_NOW", brief)

    def test_ok_format(self):
        data = make_registry_data({"claudecode": 1, "claudeai": 1, "vibecoding": 1})
        sched = ScanScheduler(registry_data=data)
        rec = sched.recommend()
        brief = rec.format_brief()
        self.assertIn("OK", brief)


class TestScanSchedulerFromRegistry(unittest.TestCase):

    def test_loads_from_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "scan_registry.json")
            data = make_registry_data({"claudecode": 5})
            with open(path, "w") as f:
                json.dump(data, f)
            sched = ScanScheduler.from_registry_file(path)
            rec = sched.recommend()
            self.assertEqual(rec.action, "SCAN_NOW")

    def test_missing_file(self):
        sched = ScanScheduler.from_registry_file("/nonexistent/path.json")
        rec = sched.recommend()
        # All subs treated as never scanned
        self.assertEqual(rec.action, "SCAN_NOW")


class TestAutoTrigger(unittest.TestCase):
    """Tests for Phase 3: auto-trigger integration."""

    def test_should_auto_scan_when_stale(self):
        data = make_registry_data({"claudecode": 5, "claudeai": 1, "vibecoding": 1})
        sched = ScanScheduler(registry_data=data)
        result = sched.should_auto_scan()
        self.assertTrue(result["should_scan"])
        self.assertEqual(result["top_target"], "claudecode")
        self.assertGreater(result["stale_count"], 0)

    def test_should_not_auto_scan_when_fresh(self):
        data = make_registry_data({"claudecode": 1, "claudeai": 1, "vibecoding": 1})
        sched = ScanScheduler(registry_data=data)
        result = sched.should_auto_scan()
        self.assertFalse(result["should_scan"])
        self.assertIsNone(result["top_target"])

    def test_scan_command_for_sub(self):
        sched = ScanScheduler(registry_data={})
        cmd = sched.scan_command("claudecode")
        self.assertIn("nuclear_fetcher.py", cmd)
        self.assertIn("claudecode", cmd)
        self.assertIn("--classify", cmd)
        self.assertIn("--dedup", cmd)

    def test_scan_command_includes_hot_rising(self):
        sched = ScanScheduler(registry_data={})
        cmd = sched.scan_command("claudeai")
        self.assertIn("--hot", cmd)
        self.assertIn("--rising", cmd)

    def test_all_stale_targets_returns_ordered_list(self):
        data = make_registry_data({"claudecode": 10, "claudeai": 8, "vibecoding": 7})
        sched = ScanScheduler(registry_data=data)
        result = sched.should_auto_scan()
        self.assertTrue(result["should_scan"])
        self.assertIsInstance(result["all_targets"], list)
        self.assertGreater(len(result["all_targets"]), 1)

    def test_should_auto_scan_returns_slugs(self):
        data = make_registry_data({"claudecode": 10})
        sched = ScanScheduler(registry_data=data)
        result = sched.should_auto_scan()
        self.assertIn("all_targets", result)
        for target in result["all_targets"]:
            self.assertIsInstance(target, str)


if __name__ == "__main__":
    unittest.main()
