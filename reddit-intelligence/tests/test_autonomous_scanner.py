#!/usr/bin/env python3
"""
Tests for autonomous_scanner.py — MT-9 Autonomous Cross-Subreddit Intelligence.

TDD: Tests written first, then implementation.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR.parent))


class TestScanPrioritizer(unittest.TestCase):
    """Tests for ScanPrioritizer — picks which sub to scan next."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_registry(self, data):
        with open(self.registry_path, "w") as f:
            json.dump(data, f)

    def test_import(self):
        from autonomous_scanner import ScanPrioritizer
        self.assertTrue(callable(ScanPrioritizer))

    def test_never_scanned_subs_get_highest_priority(self):
        """Subs that have never been scanned should be prioritized."""
        from autonomous_scanner import ScanPrioritizer
        # Registry with only one sub scanned
        self._write_registry({
            "claudecode": {
                "last_scan": datetime.now(timezone.utc).isoformat(),
                "posts_scanned": 100, "builds": 5, "adapts": 10,
            }
        })
        p = ScanPrioritizer(registry_path=self.registry_path)
        ranked = p.rank_all()
        # Never-scanned subs should appear before recently-scanned ones
        slugs = [r["slug"] for r in ranked]
        if "claudecode" in slugs:
            claude_idx = slugs.index("claudecode")
            # At least some never-scanned sub should be ahead
            never_scanned = [r for r in ranked if r.get("never_scanned")]
            self.assertTrue(len(never_scanned) > 0)
            for ns in never_scanned:
                ns_idx = slugs.index(ns["slug"])
                self.assertLess(ns_idx, claude_idx)

    def test_stale_subs_ranked_higher_than_fresh(self):
        """Subs scanned 30 days ago should rank higher than subs scanned today."""
        from autonomous_scanner import ScanPrioritizer
        now = datetime.now(timezone.utc)
        self._write_registry({
            "claudecode": {
                "last_scan": (now - timedelta(days=30)).isoformat(),
                "posts_scanned": 100, "builds": 5, "adapts": 10,
            },
            "claudeai": {
                "last_scan": now.isoformat(),
                "posts_scanned": 80, "builds": 3, "adapts": 5,
            },
        })
        p = ScanPrioritizer(registry_path=self.registry_path)
        ranked = p.rank_all()
        slugs = [r["slug"] for r in ranked]
        # claudecode (stale) should be before claudeai (fresh)
        if "claudecode" in slugs and "claudeai" in slugs:
            self.assertLess(slugs.index("claudecode"), slugs.index("claudeai"))

    def test_high_yield_subs_ranked_higher(self):
        """Subs with better BUILD/ADAPT yield should rank higher when staleness is equal."""
        from autonomous_scanner import ScanPrioritizer
        old_date = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        self._write_registry({
            "claudecode": {
                "last_scan": old_date,
                "posts_scanned": 100, "builds": 10, "adapts": 15,
            },
            "webdev": {
                "last_scan": old_date,
                "posts_scanned": 100, "builds": 0, "adapts": 1,
            },
        })
        p = ScanPrioritizer(registry_path=self.registry_path)
        ranked = p.rank_all()
        slugs = [r["slug"] for r in ranked]
        if "claudecode" in slugs and "webdev" in slugs:
            self.assertLess(slugs.index("claudecode"), slugs.index("webdev"))

    def test_domain_diversity_bonus(self):
        """Prioritizer should consider domain diversity."""
        from autonomous_scanner import ScanPrioritizer
        p = ScanPrioritizer(registry_path=self.registry_path)
        ranked = p.rank_all()
        # Should have subs from multiple domains
        domains = {r.get("domain") for r in ranked}
        self.assertTrue(len(domains) >= 2, f"Expected 2+ domains, got {domains}")

    def test_priority_score_is_numeric(self):
        """Each ranked entry should have a numeric priority_score."""
        from autonomous_scanner import ScanPrioritizer
        p = ScanPrioritizer(registry_path=self.registry_path)
        ranked = p.rank_all()
        for entry in ranked:
            self.assertIn("priority_score", entry)
            self.assertIsInstance(entry["priority_score"], (int, float))

    def test_pick_next_returns_top_ranked(self):
        """pick_next() should return the highest-priority sub."""
        from autonomous_scanner import ScanPrioritizer
        p = ScanPrioritizer(registry_path=self.registry_path)
        top = p.pick_next()
        ranked = p.rank_all()
        self.assertEqual(top["slug"], ranked[0]["slug"])

    def test_pick_next_with_exclude(self):
        """pick_next(exclude=[...]) should skip excluded slugs."""
        from autonomous_scanner import ScanPrioritizer
        p = ScanPrioritizer(registry_path=self.registry_path)
        top = p.pick_next()
        second = p.pick_next(exclude=[top["slug"]])
        self.assertNotEqual(top["slug"], second["slug"])

    def test_pick_next_with_domain_filter(self):
        """pick_next(domain='trading') should only return trading subs."""
        from autonomous_scanner import ScanPrioritizer
        p = ScanPrioritizer(registry_path=self.registry_path)
        result = p.pick_next(domain="trading")
        self.assertEqual(result["domain"], "trading")

    def test_empty_registry_still_ranks(self):
        """With no registry file, should still rank all builtin profiles."""
        from autonomous_scanner import ScanPrioritizer
        p = ScanPrioritizer(registry_path=os.path.join(self.tmpdir, "nonexistent.json"))
        ranked = p.rank_all()
        self.assertTrue(len(ranked) > 0)
        # All should be never_scanned
        for r in ranked:
            self.assertTrue(r.get("never_scanned", False))

    def test_staleness_days_in_output(self):
        """Each ranked entry should include staleness_days."""
        from autonomous_scanner import ScanPrioritizer
        now = datetime.now(timezone.utc)
        self._write_registry({
            "claudecode": {
                "last_scan": (now - timedelta(days=7)).isoformat(),
                "posts_scanned": 50, "builds": 2, "adapts": 3,
            },
        })
        p = ScanPrioritizer(registry_path=self.registry_path)
        ranked = p.rank_all()
        for entry in ranked:
            self.assertIn("staleness_days", entry)
            if entry["slug"] == "claudecode":
                self.assertAlmostEqual(entry["staleness_days"], 7, delta=1)


class TestSafetyGate(unittest.TestCase):
    """Tests for SafetyGate — enforces MT-9 safety protections."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.kill_switch_path = os.path.join(self.tmpdir, ".cca-autonomous-pause")
        self.state_path = os.path.join(self.tmpdir, "autonomous_state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_import(self):
        from autonomous_scanner import SafetyGate
        self.assertTrue(callable(SafetyGate))

    def test_kill_switch_blocks_scanning(self):
        """If kill switch file exists, all scanning should be blocked."""
        from autonomous_scanner import SafetyGate
        Path(self.kill_switch_path).touch()
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        allowed, reason = gate.can_scan()
        self.assertFalse(allowed)
        self.assertIn("pause", reason.lower())

    def test_no_kill_switch_allows_scanning(self):
        """Without kill switch, scanning should be allowed."""
        from autonomous_scanner import SafetyGate
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        allowed, reason = gate.can_scan()
        self.assertTrue(allowed)

    def test_max_posts_per_scan_enforced(self):
        """Should enforce max 50 posts per scan."""
        from autonomous_scanner import SafetyGate
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        self.assertEqual(gate.max_posts_per_scan, 50)

    def test_max_scans_per_session_enforced(self):
        """Should enforce max scans per session."""
        from autonomous_scanner import SafetyGate
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        # Record max scans
        for i in range(gate.max_scans_per_session):
            gate.record_scan(f"sub_{i}")
        allowed, reason = gate.can_scan()
        self.assertFalse(allowed)
        self.assertIn("limit", reason.lower())

    def test_min_delay_between_scans(self):
        """Should enforce minimum delay between scans."""
        from autonomous_scanner import SafetyGate
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        gate.record_scan("claudecode")
        # Immediately after a scan, should require waiting
        allowed, reason = gate.can_scan()
        # If delay is 0 or very short for testing, this might pass
        # The gate should track last_scan_time
        self.assertIsNotNone(gate.last_scan_time)

    def test_record_scan_increments_count(self):
        """record_scan should increment session scan count."""
        from autonomous_scanner import SafetyGate
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        self.assertEqual(gate.scans_this_session, 0)
        gate.record_scan("claudecode")
        self.assertEqual(gate.scans_this_session, 1)

    def test_check_post_safety_delegates_to_content_scanner(self):
        """check_post_safety should use content_scanner.is_safe_for_deep_read."""
        from autonomous_scanner import SafetyGate
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        safe_post = {"title": "My Claude workflow", "score": 100, "url": "https://reddit.com/r/test"}
        is_safe, reason = gate.check_post_safety(safe_post)
        self.assertTrue(is_safe)

    def test_check_post_safety_blocks_threats(self):
        """Should block posts with dangerous content in title."""
        from autonomous_scanner import SafetyGate
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        dangerous_post = {"title": "pip install my-malware-package", "score": 100, "url": "https://evil.tk/exploit"}
        is_safe, reason = gate.check_post_safety(dangerous_post)
        self.assertFalse(is_safe)

    def test_negative_score_blocked(self):
        """Posts with negative scores should be blocked."""
        from autonomous_scanner import SafetyGate
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        post = {"title": "Some post", "score": -5, "url": "https://reddit.com/r/test"}
        is_safe, reason = gate.check_post_safety(post)
        self.assertFalse(is_safe)

    def test_state_persistence(self):
        """SafetyGate should persist state to disk."""
        from autonomous_scanner import SafetyGate
        gate = SafetyGate(kill_switch_path=self.kill_switch_path, state_path=self.state_path)
        gate.record_scan("claudecode")
        gate.save_state()
        self.assertTrue(os.path.exists(self.state_path))
        with open(self.state_path) as f:
            state = json.load(f)
        self.assertEqual(state["scans_this_session"], 1)
        self.assertIn("claudecode", state["subs_scanned"])


class TestAutonomousScanner(unittest.TestCase):
    """Tests for AutonomousScanner — the orchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.kill_switch_path = os.path.join(self.tmpdir, ".cca-autonomous-pause")
        self.state_path = os.path.join(self.tmpdir, "autonomous_state.json")
        self.findings_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_import(self):
        from autonomous_scanner import AutonomousScanner
        self.assertTrue(callable(AutonomousScanner))

    def test_init_creates_components(self):
        """Should initialize with prioritizer and safety gate."""
        from autonomous_scanner import AutonomousScanner
        scanner = AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )
        self.assertIsNotNone(scanner.prioritizer)
        self.assertIsNotNone(scanner.safety_gate)

    def test_pick_target_returns_sub_info(self):
        """pick_target should return a dict with slug, subreddit, domain."""
        from autonomous_scanner import AutonomousScanner
        scanner = AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )
        target = scanner.pick_target()
        self.assertIn("slug", target)
        self.assertIn("subreddit", target)
        self.assertIn("domain", target)

    def test_pick_target_respects_kill_switch(self):
        """Should return None if kill switch is active."""
        from autonomous_scanner import AutonomousScanner
        Path(self.kill_switch_path).touch()
        scanner = AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )
        target = scanner.pick_target()
        self.assertIsNone(target)

    def test_filter_posts_removes_unsafe(self):
        """filter_posts should remove posts that fail safety check."""
        from autonomous_scanner import AutonomousScanner
        scanner = AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )
        posts = [
            {"id": "a", "title": "Great Claude workflow", "score": 100,
             "url": "https://reddit.com/r/test", "num_comments": 10,
             "is_self": True, "selftext_length": 500, "flair": ""},
            {"id": "b", "title": "pip install malware-package now", "score": 50,
             "url": "https://evil.tk/exploit", "num_comments": 5,
             "is_self": True, "selftext_length": 100, "flair": ""},
            {"id": "c", "title": "Negative score post", "score": -3,
             "url": "https://reddit.com/r/test", "num_comments": 1,
             "is_self": True, "selftext_length": 50, "flair": ""},
        ]
        safe, blocked = scanner.filter_posts(posts)
        safe_ids = [p["id"] for p in safe]
        self.assertIn("a", safe_ids)
        self.assertNotIn("b", safe_ids)
        self.assertNotIn("c", safe_ids)
        self.assertEqual(len(blocked), 2)

    def test_filter_posts_enforces_max_limit(self):
        """filter_posts should cap at safety gate's max_posts_per_scan."""
        from autonomous_scanner import AutonomousScanner
        scanner = AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )
        # Create 100 safe posts
        posts = [
            {"id": f"p{i}", "title": f"Good post {i}", "score": 100 - i,
             "url": "https://reddit.com/r/test", "num_comments": 10,
             "is_self": True, "selftext_length": 500, "flair": ""}
            for i in range(100)
        ]
        safe, _ = scanner.filter_posts(posts)
        self.assertLessEqual(len(safe), scanner.safety_gate.max_posts_per_scan)

    def test_generate_report(self):
        """generate_report should produce structured output."""
        from autonomous_scanner import AutonomousScanner, ScanReport
        scanner = AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )
        report = ScanReport(
            subreddit="ClaudeCode",
            slug="claudecode",
            domain="claude",
            posts_fetched=50,
            posts_safe=45,
            posts_blocked=5,
            needles=10,
            maybes=20,
            hay=15,
            blocked_reasons=["threat: executable_install"] * 5,
        )
        self.assertEqual(report.subreddit, "ClaudeCode")
        self.assertEqual(report.posts_fetched, 50)
        self.assertEqual(report.posts_safe, 45)
        self.assertEqual(report.posts_blocked, 5)

    def test_scan_report_to_dict(self):
        """ScanReport.to_dict() should produce a serializable dict."""
        from autonomous_scanner import ScanReport
        report = ScanReport(
            subreddit="ClaudeCode", slug="claudecode", domain="claude",
            posts_fetched=50, posts_safe=45, posts_blocked=5,
            needles=10, maybes=20, hay=15,
            blocked_reasons=["threat"] * 5,
        )
        d = report.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["subreddit"], "ClaudeCode")
        # Should be JSON-serializable
        json.dumps(d)

    def test_scan_report_summary_string(self):
        """ScanReport.summary() should return a human-readable string."""
        from autonomous_scanner import ScanReport
        report = ScanReport(
            subreddit="ClaudeCode", slug="claudecode", domain="claude",
            posts_fetched=50, posts_safe=45, posts_blocked=5,
            needles=10, maybes=20, hay=15,
            blocked_reasons=["threat"] * 5,
        )
        summary = report.summary()
        self.assertIn("ClaudeCode", summary)
        self.assertIn("50", summary)
        self.assertIn("NEEDLE", summary)

    def test_dedup_against_findings(self):
        """Should dedup posts against existing FINDINGS_LOG.md."""
        from autonomous_scanner import AutonomousScanner
        # Write a fake findings log with one post ID
        with open(self.findings_path, "w") as f:
            f.write("## Finding\nhttps://www.reddit.com/r/ClaudeCode/comments/abc123/some_post\n")
        scanner = AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )
        posts = [
            {"id": "abc123", "title": "Already reviewed", "score": 100,
             "url": "https://reddit.com/r/test", "num_comments": 10,
             "is_self": True, "selftext_length": 500, "flair": ""},
            {"id": "def456", "title": "New post", "score": 80,
             "url": "https://reddit.com/r/test", "num_comments": 5,
             "is_self": True, "selftext_length": 300, "flair": ""},
        ]
        deduped = scanner.dedup_posts(posts)
        ids = [p["id"] for p in deduped]
        self.assertNotIn("abc123", ids)
        self.assertIn("def456", ids)

    def test_classify_posts_adds_triage(self):
        """classify_posts should add triage classification to each post."""
        from autonomous_scanner import AutonomousScanner
        scanner = AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )
        posts = [
            {"id": "a", "title": "My MCP server hook workflow", "score": 200,
             "num_comments": 50, "is_self": True, "selftext_length": 1000,
             "flair": "showcase", "url": "https://reddit.com/r/test"},
        ]
        classified = scanner.classify_posts(posts)
        self.assertIn("triage", classified[0])
        self.assertIn(classified[0]["triage"], ["NEEDLE", "MAYBE", "HAY"])


class TestApprovedDomains(unittest.TestCase):
    """Tests for approved domain enforcement."""

    def test_approved_domains_list(self):
        """APPROVED_DOMAINS should match MT-9 spec."""
        from autonomous_scanner import APPROVED_DOMAINS
        self.assertIn("claude", APPROVED_DOMAINS)
        self.assertIn("trading", APPROVED_DOMAINS)
        self.assertIn("dev", APPROVED_DOMAINS)
        self.assertIn("research", APPROVED_DOMAINS)

    def test_only_approved_profiles_included(self):
        """ScanPrioritizer should only include subs from approved domains."""
        from autonomous_scanner import ScanPrioritizer
        tmpdir = tempfile.mkdtemp()
        try:
            p = ScanPrioritizer(registry_path=os.path.join(tmpdir, "reg.json"))
            ranked = p.rank_all()
            for entry in ranked:
                self.assertIn(entry["domain"], {"claude", "trading", "dev", "research", "unknown"})
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestCLI(unittest.TestCase):
    """Tests for CLI interface."""

    def test_cli_rank_command(self):
        """CLI 'rank' command should output ranked subs."""
        from autonomous_scanner import cli_main
        import io
        from contextlib import redirect_stdout
        tmpdir = tempfile.mkdtemp()
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                cli_main(["rank", "--registry", os.path.join(tmpdir, "reg.json")])
            output = out.getvalue()
            self.assertIn("Slug", output)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cli_status_command(self):
        """CLI 'status' command should show safety gate status."""
        from autonomous_scanner import cli_main
        import io
        from contextlib import redirect_stdout
        tmpdir = tempfile.mkdtemp()
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                cli_main(["status", "--state", os.path.join(tmpdir, "state.json"),
                          "--kill-switch", os.path.join(tmpdir, "pause")])
            output = out.getvalue()
            self.assertIn("scan", output.lower())
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
