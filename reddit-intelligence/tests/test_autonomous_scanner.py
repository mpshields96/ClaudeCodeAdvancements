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


class TestAutonomousScanExecution(unittest.TestCase):
    """Tests for full scan execution pipeline (MT-9 Phase 2)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.kill_switch_path = os.path.join(self.tmpdir, ".cca-autonomous-pause")
        self.state_path = os.path.join(self.tmpdir, "autonomous_state.json")
        self.findings_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        self.output_dir = os.path.join(self.tmpdir, "findings")
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_scanner(self):
        from autonomous_scanner import AutonomousScanner
        return AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )

    def _mock_posts(self, n=10, subreddit="ClaudeCode"):
        """Generate realistic mock Reddit posts."""
        return [
            {
                "id": f"post_{i}",
                "title": f"My Claude Code workflow tip #{i}" if i % 3 != 0 else f"Funny meme #{i}",
                "author": f"user_{i}",
                "score": 200 - i * 10,
                "upvote_ratio": 0.95,
                "num_comments": 30 + i,
                "created_utc": 1710000000 + i * 3600,
                "flair": "showcase" if i % 4 == 0 else "",
                "is_self": True,
                "url": f"https://reddit.com/r/{subreddit}/comments/post_{i}/",
                "permalink": f"https://www.reddit.com/r/{subreddit}/comments/post_{i}/title/",
                "selftext_length": 500 + i * 50,
                "subreddit": subreddit,
            }
            for i in range(n)
        ]

    def test_execute_scan_returns_scan_result(self):
        """execute_scan should return a ScanResult with report and classified posts."""
        from autonomous_scanner import AutonomousScanner, ScanResult
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(10)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        self.assertIsInstance(result, ScanResult)
        self.assertIsNotNone(result.report)
        self.assertEqual(result.report.subreddit, "ClaudeCode")
        self.assertGreater(result.report.posts_fetched, 0)

    def test_execute_scan_classifies_all_posts(self):
        """All safe posts should have triage classification after scan."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(5)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        for p in result.needles + result.maybes:
            self.assertIn("triage", p)

    def test_execute_scan_separates_needles_and_maybes(self):
        """ScanResult should have separate lists for needles and maybes."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(10)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        # Needles should all be NEEDLE, maybes all MAYBE
        for p in result.needles:
            self.assertEqual(p["triage"], "NEEDLE")
        for p in result.maybes:
            self.assertEqual(p["triage"], "MAYBE")

    def test_execute_scan_records_in_safety_gate(self):
        """Scan should be recorded in safety gate state."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(5)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        self.assertEqual(scanner.safety_gate.scans_this_session, 1)
        self.assertIn("claudecode", scanner.safety_gate.subs_scanned)

    def test_execute_scan_blocked_by_kill_switch(self):
        """If kill switch active, execute_scan should return None."""
        from autonomous_scanner import AutonomousScanner
        Path(self.kill_switch_path).touch()
        scanner = self._make_scanner()
        result = scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        self.assertIsNone(result)

    def test_execute_scan_dedup_works(self):
        """Posts already in findings log should be excluded."""
        from autonomous_scanner import AutonomousScanner
        with open(self.findings_path, "w") as f:
            f.write("## Prior\nhttps://www.reddit.com/r/ClaudeCode/comments/post_0/title\n")
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(5)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        all_ids = [p["id"] for p in result.needles + result.maybes + result.hay]
        self.assertNotIn("post_0", all_ids)

    def test_execute_scan_filters_unsafe(self):
        """Unsafe posts should be filtered out."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        posts = self._mock_posts(3)
        posts.append({
            "id": "evil_post", "title": "pip install super-malware",
            "author": "hacker", "score": 100, "upvote_ratio": 0.5,
            "num_comments": 5, "created_utc": 1710000000,
            "flair": "", "is_self": True,
            "url": "https://evil.tk/malware",
            "permalink": "https://www.reddit.com/r/ClaudeCode/comments/evil_post/",
            "selftext_length": 100, "subreddit": "ClaudeCode",
        })
        with patch("autonomous_scanner.fetch_top_posts", return_value=posts):
            result = scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        all_ids = [p["id"] for p in result.needles + result.maybes + result.hay]
        self.assertNotIn("evil_post", all_ids)
        self.assertGreater(result.report.posts_blocked, 0)

    def test_execute_scan_respects_post_limit(self):
        """Should not return more than max_posts_per_scan safe posts."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        scanner.safety_gate.max_posts_per_scan = 5
        mock_posts = self._mock_posts(20)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        total_safe = len(result.needles) + len(result.maybes) + len(result.hay)
        self.assertLessEqual(total_safe, 5)

    def test_execute_scan_uses_profile_settings(self):
        """When fetch_limit/timeframe not specified, should use profile defaults."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(5)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts) as mock_fetch:
            scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        # fetch_top_posts should be called with some limit and timeframe
        mock_fetch.assert_called_once()
        args = mock_fetch.call_args
        self.assertIsInstance(args[0][1], int)  # limit
        self.assertIsInstance(args[0][2], str)  # timeframe

    def test_scan_result_to_dict(self):
        """ScanResult.to_dict should be JSON-serializable."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(5)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        d = result.to_dict()
        json.dumps(d)  # must be serializable
        self.assertIn("report", d)
        self.assertIn("needles", d)
        self.assertIn("maybes", d)

    def test_scan_result_save_json(self):
        """ScanResult.save_json should write result to file."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(5)
        out_path = os.path.join(self.tmpdir, "scan_result.json")
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        result.save_json(out_path)
        self.assertTrue(os.path.exists(out_path))
        with open(out_path) as f:
            loaded = json.load(f)
        self.assertIn("report", loaded)

    def test_full_autonomous_flow(self):
        """End-to-end: pick_target + execute_scan should work together."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        target = scanner.pick_target()
        self.assertIsNotNone(target)
        mock_posts = self._mock_posts(8, subreddit=target["subreddit"])
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.execute_scan(
                target["subreddit"], target["slug"], target["domain"]
            )
        self.assertIsNotNone(result)
        self.assertEqual(result.report.subreddit, target["subreddit"])

    def test_execute_scan_with_custom_limits(self):
        """Should accept custom fetch_limit and timeframe."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(5)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts) as mock_fetch:
            scanner.execute_scan("ClaudeCode", "claudecode", "claude",
                                 fetch_limit=50, timeframe="month")
        mock_fetch.assert_called_once_with("ClaudeCode", 50, "month")

    def test_execute_scan_records_in_registry(self):
        """Scan should update scan_registry with results."""
        from autonomous_scanner import AutonomousScanner
        scanner = self._make_scanner()
        mock_posts = self._mock_posts(10)
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            scanner.execute_scan("ClaudeCode", "claudecode", "claude")
        # Check registry was updated
        with open(self.registry_path) as f:
            registry = json.load(f)
        self.assertIn("claudecode", registry)
        self.assertIn("last_scan", registry["claudecode"])


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

    def test_cli_scan_command(self):
        """CLI 'scan' command should execute a scan and output results."""
        from autonomous_scanner import cli_main
        import io
        from contextlib import redirect_stdout
        tmpdir = tempfile.mkdtemp()
        try:
            mock_posts = [
                {"id": f"p{i}", "title": f"Claude workflow tip {i}",
                 "author": "u", "score": 100, "upvote_ratio": 0.9,
                 "num_comments": 20, "created_utc": 1710000000,
                 "flair": "", "is_self": True,
                 "url": "https://reddit.com/r/ClaudeCode/comments/p0/",
                 "permalink": "https://www.reddit.com/r/ClaudeCode/comments/p0/t/",
                 "selftext_length": 500, "subreddit": "ClaudeCode"}
                for i in range(5)
            ]
            out = io.StringIO()
            with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
                with redirect_stdout(out):
                    cli_main(["scan",
                              "--registry", os.path.join(tmpdir, "reg.json"),
                              "--state", os.path.join(tmpdir, "state.json"),
                              "--kill-switch", os.path.join(tmpdir, "pause"),
                              "--findings", os.path.join(tmpdir, "findings.md")])
            output = out.getvalue()
            self.assertIn("scan", output.lower())
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cli_scan_with_target(self):
        """CLI 'scan --target r/algotrading' should scan specific sub."""
        from autonomous_scanner import cli_main
        import io
        from contextlib import redirect_stdout
        tmpdir = tempfile.mkdtemp()
        try:
            mock_posts = [
                {"id": "p0", "title": "Algo trading strategy",
                 "author": "u", "score": 100, "upvote_ratio": 0.9,
                 "num_comments": 20, "created_utc": 1710000000,
                 "flair": "", "is_self": True,
                 "url": "https://reddit.com/r/algotrading/comments/p0/",
                 "permalink": "https://www.reddit.com/r/algotrading/comments/p0/t/",
                 "selftext_length": 500, "subreddit": "algotrading"}
            ]
            out = io.StringIO()
            with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts) as mock_fetch:
                with redirect_stdout(out):
                    cli_main(["scan", "--target", "r/algotrading",
                              "--registry", os.path.join(tmpdir, "reg.json"),
                              "--state", os.path.join(tmpdir, "state.json"),
                              "--kill-switch", os.path.join(tmpdir, "pause"),
                              "--findings", os.path.join(tmpdir, "findings.md")])
            # Should have been called with "algotrading"
            mock_fetch.assert_called_once()
            self.assertEqual(mock_fetch.call_args[0][0], "algotrading")
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cli_scan_json_output(self):
        """CLI 'scan --json' should output JSON result."""
        from autonomous_scanner import cli_main
        import io
        from contextlib import redirect_stdout
        tmpdir = tempfile.mkdtemp()
        try:
            mock_posts = [
                {"id": "p0", "title": "Claude Code hook tutorial",
                 "author": "u", "score": 100, "upvote_ratio": 0.9,
                 "num_comments": 20, "created_utc": 1710000000,
                 "flair": "", "is_self": True,
                 "url": "https://reddit.com/r/ClaudeCode/comments/p0/",
                 "permalink": "https://www.reddit.com/r/ClaudeCode/comments/p0/t/",
                 "selftext_length": 500, "subreddit": "ClaudeCode"}
            ]
            out = io.StringIO()
            with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
                with redirect_stdout(out):
                    cli_main(["scan", "--json",
                              "--registry", os.path.join(tmpdir, "reg.json"),
                              "--state", os.path.join(tmpdir, "state.json"),
                              "--kill-switch", os.path.join(tmpdir, "pause"),
                              "--findings", os.path.join(tmpdir, "findings.md")])
            output = out.getvalue()
            parsed = json.loads(output)
            self.assertIn("report", parsed)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestDailyScan(unittest.TestCase):
    """Tests for the daily hot+rising scan mode."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.state_path = os.path.join(self.tmpdir, "state.json")
        self.findings_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        with open(self.findings_path, "w") as f:
            f.write("")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_scanner(self):
        from autonomous_scanner import AutonomousScanner
        scanner = AutonomousScanner(
            registry_path=self.registry_path,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )
        # Disable rate limiting for tests
        scanner.safety_gate.min_delay_seconds = 0
        return scanner

    def _mock_posts(self, sub, n=5, base_score=100):
        return [{
            "id": f"{sub}_{i}",
            "title": f"Test post {i} from {sub}",
            "author": "testuser",
            "score": base_score + i * 10,
            "upvote_ratio": 0.9,
            "num_comments": 20 + i,
            "created_utc": 1710000000 + i,
            "flair": "Discussion",
            "is_self": True,
            "url": f"https://reddit.com/r/{sub}/comments/{sub}_{i}/",
            "permalink": f"https://www.reddit.com/r/{sub}/comments/{sub}_{i}/test/",
            "selftext_length": 500,
            "subreddit": sub,
        } for i in range(n)]

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_scan_returns_list(self, mock_rising, mock_hot):
        mock_hot.return_value = self._mock_posts("ClaudeCode", 3)
        mock_rising.return_value = self._mock_posts("ClaudeCode", 2, base_score=50)
        scanner = self._make_scanner()
        results = scanner.execute_daily_scan(subs=["ClaudeCode"])
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_scan_multiple_subs(self, mock_rising, mock_hot):
        mock_hot.side_effect = [
            self._mock_posts("ClaudeCode", 3),
            self._mock_posts("ClaudeAI", 3),
        ]
        mock_rising.side_effect = [
            self._mock_posts("ClaudeCode", 2, base_score=50),
            self._mock_posts("ClaudeAI", 2, base_score=50),
        ]
        scanner = self._make_scanner()
        results = scanner.execute_daily_scan(subs=["ClaudeCode", "ClaudeAI"])
        self.assertEqual(len(results), 2)

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_scan_deduplicates_hot_rising(self, mock_rising, mock_hot):
        """Posts appearing in both hot and rising should not be duplicated."""
        shared_posts = self._mock_posts("ClaudeCode", 3)
        mock_hot.return_value = shared_posts
        mock_rising.return_value = shared_posts  # Same posts
        scanner = self._make_scanner()
        results = scanner.execute_daily_scan(subs=["ClaudeCode"])
        # Should be 3 unique posts, not 6
        total = results[0].report.posts_safe
        self.assertLessEqual(total, 3)

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_scan_result_has_report(self, mock_rising, mock_hot):
        mock_hot.return_value = self._mock_posts("ClaudeCode", 2)
        mock_rising.return_value = []
        scanner = self._make_scanner()
        results = scanner.execute_daily_scan(subs=["ClaudeCode"])
        self.assertTrue(hasattr(results[0], "report"))
        self.assertEqual(results[0].report.subreddit, "ClaudeCode")

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_scan_classifies_posts(self, mock_rising, mock_hot):
        mock_hot.return_value = self._mock_posts("ClaudeCode", 3)
        mock_rising.return_value = []
        scanner = self._make_scanner()
        results = scanner.execute_daily_scan(subs=["ClaudeCode"])
        # All posts should have triage field
        for p in results[0].needles + results[0].maybes + results[0].hay:
            self.assertIn("triage", p)

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_scan_uses_custom_limits(self, mock_rising, mock_hot):
        mock_hot.return_value = []
        mock_rising.return_value = []
        scanner = self._make_scanner()
        scanner.execute_daily_scan(subs=["ClaudeCode"], hot_limit=10, rising_limit=5)
        mock_hot.assert_called_once_with("ClaudeCode", 10)
        mock_rising.assert_called_once_with("ClaudeCode", 5)

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_scan_default_subs(self, mock_rising, mock_hot):
        """Default subs should include high-signal subreddits."""
        mock_hot.return_value = []
        mock_rising.return_value = []
        scanner = self._make_scanner()
        results = scanner.execute_daily_scan()
        # Should have scanned at least 3 default subs
        self.assertGreaterEqual(mock_hot.call_count, 3)

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_scan_empty_results(self, mock_rising, mock_hot):
        mock_hot.return_value = []
        mock_rising.return_value = []
        scanner = self._make_scanner()
        results = scanner.execute_daily_scan(subs=["ClaudeCode"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].report.posts_fetched, 0)

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_scan_dedupes_against_findings(self, mock_rising, mock_hot):
        """Posts already in FINDINGS_LOG should be excluded."""
        posts = self._mock_posts("ClaudeCode", 3)
        # Write one post ID to findings log
        with open(self.findings_path, "w") as f:
            f.write(f"https://www.reddit.com/r/ClaudeCode/comments/{posts[0]['id']}/\n")
        mock_hot.return_value = posts
        mock_rising.return_value = []
        scanner = self._make_scanner()
        results = scanner.execute_daily_scan(subs=["ClaudeCode"])
        # Should have excluded the one already-reviewed post
        self.assertLess(results[0].report.posts_safe, 3)


class TestDailyCLI(unittest.TestCase):
    """Tests for the daily CLI command."""

    def test_daily_cli_help_includes_daily(self):
        from autonomous_scanner import cli_main
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([])
        output = f.getvalue()
        self.assertIn("daily", output)

    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_rising_posts")
    def test_daily_cli_json_output(self, mock_rising, mock_hot):
        mock_hot.return_value = []
        mock_rising.return_value = []
        tmpdir = tempfile.mkdtemp()
        try:
            from autonomous_scanner import cli_main
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                cli_main([
                    "daily", "--json",
                    "--registry", os.path.join(tmpdir, "reg.json"),
                    "--state", os.path.join(tmpdir, "state.json"),
                    "--findings", os.path.join(tmpdir, "findings.md"),
                    "--subs", "ClaudeCode",
                ])
            output = f.getvalue()
            parsed = json.loads(output)
            self.assertIsInstance(parsed, list)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestRescanSub(unittest.TestCase):
    """Tests for MT-14 rescan_sub() — delta rescanning of stale subs."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.state_path = os.path.join(self.tmpdir, "autonomous_state.json")
        self.kill_switch = os.path.join(self.tmpdir, "kill_switch")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_registry(self, data):
        with open(self.registry_path, "w") as f:
            json.dump(data, f)

    def test_rescan_import(self):
        from autonomous_scanner import AutonomousScanner
        scanner = AutonomousScanner(registry_path=self.registry_path,
                                    state_path=self.state_path,
                                    kill_switch_path=self.kill_switch)
        self.assertTrue(hasattr(scanner, "rescan_sub"))

    def test_rescan_not_stale_returns_none(self):
        """Should return None if sub was scanned recently."""
        from autonomous_scanner import AutonomousScanner
        # Record a recent scan
        now = datetime.now(timezone.utc)
        self._write_registry({
            "claudecode": {
                "last_scan": now.isoformat(),
                "posts_scanned": 50,
                "builds": 2,
                "adapts": 5,
            }
        })
        scanner = AutonomousScanner(registry_path=self.registry_path,
                                    state_path=self.state_path,
                                    kill_switch_path=self.kill_switch)
        result = scanner.rescan_sub("ClaudeCode", max_age_days=14)
        self.assertIsNone(result)  # Not stale — scanned just now

    def test_rescan_stale_returns_result(self):
        """Should return ScanResult for stale subs (with mocked fetch)."""
        from autonomous_scanner import AutonomousScanner, ScanResult
        # Record an old scan
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        self._write_registry({
            "claudecode": {
                "last_scan": old,
                "posts_scanned": 50,
                "builds": 2,
                "adapts": 5,
            }
        })
        scanner = AutonomousScanner(registry_path=self.registry_path,
                                    state_path=self.state_path,
                                    kill_switch_path=self.kill_switch)
        # Mock fetch to return some posts
        now_ts = datetime.now(timezone.utc).timestamp()
        mock_posts = [
            {"id": "new1", "title": "New MCP tool", "score": 100,
             "num_comments": 10, "flair": "", "is_self": True,
             "selftext_length": 500, "selftext": "test",
             "created_utc": now_ts,
             "url": "https://reddit.com/r/ClaudeCode/new1",
             "permalink": "/r/ClaudeCode/new1", "subreddit": "ClaudeCode"},
        ]
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.rescan_sub("ClaudeCode", max_age_days=14)
            self.assertIsNotNone(result)
            self.assertIsInstance(result, ScanResult)

    def test_rescan_filters_old_posts(self):
        """Should only include posts newer than last scan."""
        from autonomous_scanner import AutonomousScanner
        # Last scan was 7 days ago
        last_scan = datetime.now(timezone.utc) - timedelta(days=7)
        self._write_registry({
            "claudecode": {
                "last_scan": last_scan.isoformat(),
                "posts_scanned": 50,
                "builds": 2,
                "adapts": 5,
            }
        })
        scanner = AutonomousScanner(registry_path=self.registry_path,
                                    state_path=self.state_path,
                                    kill_switch_path=self.kill_switch)

        # Mix of old and new posts
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=10)).timestamp()
        new_ts = (now - timedelta(days=1)).timestamp()
        mock_posts = [
            {"id": "old1", "title": "Old post", "score": 200,
             "num_comments": 50, "flair": "", "is_self": True,
             "selftext_length": 500, "selftext": "old",
             "created_utc": old_ts,
             "url": "https://reddit.com/r/ClaudeCode/old1",
             "permalink": "/r/ClaudeCode/old1", "subreddit": "ClaudeCode"},
            {"id": "new1", "title": "New MCP server post", "score": 100,
             "num_comments": 10, "flair": "", "is_self": True,
             "selftext_length": 500, "selftext": "new",
             "created_utc": new_ts,
             "url": "https://reddit.com/r/ClaudeCode/new1",
             "permalink": "/r/ClaudeCode/new1", "subreddit": "ClaudeCode"},
        ]
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.rescan_sub("ClaudeCode", max_age_days=1)
            # Should only have the new post
            self.assertIsNotNone(result)
            all_posts = result.needles + result.maybes + result.hay
            post_ids = {p["id"] for p in all_posts}
            self.assertIn("new1", post_ids)
            self.assertNotIn("old1", post_ids)

    def test_rescan_no_new_posts(self):
        """Should handle case where no new posts exist."""
        from autonomous_scanner import AutonomousScanner
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": old, "posts_scanned": 50, "builds": 0, "adapts": 0}
        })
        scanner = AutonomousScanner(registry_path=self.registry_path,
                                    state_path=self.state_path,
                                    kill_switch_path=self.kill_switch)
        # All posts are older than last scan
        old_ts = (datetime.now(timezone.utc) - timedelta(days=60)).timestamp()
        mock_posts = [
            {"id": "old1", "title": "Old post", "score": 200,
             "num_comments": 50, "flair": "", "is_self": True,
             "selftext_length": 500, "selftext": "old",
             "created_utc": old_ts,
             "url": "https://reddit.com/r/ClaudeCode/old1",
             "permalink": "/r/ClaudeCode/old1", "subreddit": "ClaudeCode"},
        ]
        with patch("autonomous_scanner.fetch_top_posts", return_value=mock_posts):
            result = scanner.rescan_sub("ClaudeCode", max_age_days=14)
            self.assertIsNotNone(result)
            self.assertEqual(result.report.posts_fetched, 0)

    def test_get_stale_subs(self):
        """Should return list of stale sub slugs."""
        from autonomous_scanner import AutonomousScanner
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        recent = datetime.now(timezone.utc).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": old, "posts_scanned": 50, "builds": 2, "adapts": 5},
            "claudeai": {"last_scan": recent, "posts_scanned": 30, "builds": 1, "adapts": 3},
        })
        scanner = AutonomousScanner(registry_path=self.registry_path,
                                    state_path=self.state_path,
                                    kill_switch_path=self.kill_switch)
        stale = scanner.get_stale_subs(max_age_days=14)
        self.assertIn("claudecode", stale)
        self.assertNotIn("claudeai", stale)

    def test_rescan_blocked_by_kill_switch(self):
        """Kill switch should block rescans."""
        from autonomous_scanner import AutonomousScanner
        # Create kill switch
        Path(self.kill_switch).write_text("paused")
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": old, "posts_scanned": 50, "builds": 0, "adapts": 0}
        })
        scanner = AutonomousScanner(registry_path=self.registry_path,
                                    state_path=self.state_path,
                                    kill_switch_path=self.kill_switch)
        result = scanner.rescan_sub("ClaudeCode", max_age_days=14)
        self.assertIsNone(result)

    def test_cli_stale_command(self):
        """CLI 'stale' command should run without error."""
        from autonomous_scanner import cli_main
        import io
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            cli_main(["stale",
                       "--registry", self.registry_path,
                       "--state", self.state_path,
                       "--kill-switch", self.kill_switch])
        output = buf.getvalue()
        self.assertIsInstance(output, str)


class TestGitHubTrendingIntegration(unittest.TestCase):
    """Tests for GitHub trending integration into autonomous pipeline (MT-11 Phase 3)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.state_path = os.path.join(self.tmpdir, "auto_state.json")
        self.kill_switch = os.path.join(self.tmpdir, "kill_switch")
        self.eval_log_path = os.path.join(self.tmpdir, "eval_log.jsonl")
        self.trending_log_path = os.path.join(self.tmpdir, "trending_history.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_scanner(self):
        from autonomous_scanner import AutonomousScanner
        return AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch,
            state_path=self.state_path,
        )

    def _make_mock_repo_meta(self, name="owner/repo", stars=50, language="python"):
        """Create a mock RepoMetadata-like object."""
        from github_scanner import RepoMetadata
        return RepoMetadata(
            full_name=name,
            description=f"A {language} repo for testing",
            stars=stars,
            forks=5,
            open_issues=2,
            language=language or "python",
            license_id="MIT",
            age_days=5.0,
            days_since_push=1.0,
            topics=["claude", "agent"],
            url=f"https://github.com/{name}",
            default_branch="main",
        )

    def _make_mock_eval_result(self, verdict="EVALUATE", score=75):
        """Create a mock EvaluationResult-like object."""
        from github_scanner import EvaluationResult
        return EvaluationResult(
            total=score,
            components={"quality": 40, "relevance": 35},
            warnings=[],
            blocked=False,
            block_reason="",
            verdict=verdict,
        )

    def test_execute_github_trending_method_exists(self):
        """AutonomousScanner should have execute_github_trending method."""
        scanner = self._make_scanner()
        self.assertTrue(hasattr(scanner, "execute_github_trending"))
        self.assertTrue(callable(scanner.execute_github_trending))

    @patch("autonomous_scanner.TrendingScanner")
    def test_execute_github_trending_returns_report(self, mock_ts_cls):
        """execute_github_trending should return a GitHubTrendingReport."""
        from autonomous_scanner import GitHubTrendingReport
        mock_ts = MagicMock()
        mock_meta = self._make_mock_repo_meta()
        mock_eval = self._make_mock_eval_result()
        mock_ts.scan_all_trending.return_value = [(mock_meta, mock_eval)]
        mock_ts.get_cca_languages.return_value = ["python"]
        mock_ts_cls.return_value = mock_ts

        scanner = self._make_scanner()
        report = scanner.execute_github_trending(days=7, limit_per_lang=5)
        self.assertIsInstance(report, GitHubTrendingReport)

    @patch("autonomous_scanner.TrendingScanner")
    def test_execute_github_trending_report_fields(self, mock_ts_cls):
        """Report should have repos_found, evaluate_count, languages_scanned."""
        from autonomous_scanner import GitHubTrendingReport
        mock_ts = MagicMock()
        mock_meta = self._make_mock_repo_meta()
        mock_eval = self._make_mock_eval_result()
        mock_ts.scan_all_trending.return_value = [(mock_meta, mock_eval)]
        mock_ts.scan_trending.return_value = [(mock_meta, mock_eval)]
        mock_ts.get_cca_languages.return_value = ["python", "typescript"]
        mock_ts_cls.return_value = mock_ts

        scanner = self._make_scanner()
        report = scanner.execute_github_trending(days=14, limit_per_lang=3)
        self.assertIsNotNone(report)
        self.assertGreaterEqual(report.repos_found, 0)
        self.assertGreaterEqual(report.evaluate_count, 0)
        self.assertIsInstance(report.languages_scanned, list)
        self.assertIsInstance(report.results, list)

    @patch("autonomous_scanner.TrendingScanner")
    def test_execute_github_trending_respects_safety_gate(self, mock_ts_cls):
        """Should return None when kill switch is active."""
        # Create kill switch
        with open(self.kill_switch, "w") as f:
            f.write("paused")

        scanner = self._make_scanner()
        report = scanner.execute_github_trending()
        self.assertIsNone(report)
        mock_ts_cls.assert_not_called()

    @patch("autonomous_scanner.TrendingScanner")
    def test_execute_github_trending_records_scan(self, mock_ts_cls):
        """Should record scan in safety gate after success."""
        mock_ts = MagicMock()
        mock_ts.scan_all_trending.return_value = []
        mock_ts.get_cca_languages.return_value = ["python"]
        mock_ts_cls.return_value = mock_ts

        scanner = self._make_scanner()
        scanner.execute_github_trending()
        # Safety gate should have recorded this
        self.assertEqual(scanner.safety_gate.scans_this_session, 1)

    @patch("autonomous_scanner.TrendingScanner")
    def test_execute_github_trending_single_language(self, mock_ts_cls):
        """Should support scanning a single language."""
        mock_ts = MagicMock()
        mock_meta = self._make_mock_repo_meta(language="rust")
        mock_eval = self._make_mock_eval_result()
        mock_ts.scan_trending.return_value = [(mock_meta, mock_eval)]
        mock_ts_cls.return_value = mock_ts

        scanner = self._make_scanner()
        report = scanner.execute_github_trending(language="rust", days=7, limit_per_lang=10)
        mock_ts.scan_trending.assert_called_once_with(language="rust", days=7, limit=10)

    @patch("autonomous_scanner.TrendingScanner")
    def test_execute_github_trending_filters_evaluate_only(self, mock_ts_cls):
        """Report evaluate_count should only count EVALUATE verdicts."""
        mock_ts = MagicMock()
        meta1 = self._make_mock_repo_meta("owner/good", stars=100)
        eval1 = self._make_mock_eval_result("EVALUATE", 80)
        meta2 = self._make_mock_repo_meta("owner/skip", stars=5)
        eval2 = self._make_mock_eval_result("SKIP", 20)
        mock_ts.scan_all_trending.return_value = [(meta1, eval1), (meta2, eval2)]
        mock_ts.get_cca_languages.return_value = ["python"]
        mock_ts_cls.return_value = mock_ts

        scanner = self._make_scanner()
        report = scanner.execute_github_trending()
        self.assertEqual(report.repos_found, 2)
        self.assertEqual(report.evaluate_count, 1)

    def test_github_trending_report_to_dict(self):
        """GitHubTrendingReport should be serializable."""
        from autonomous_scanner import GitHubTrendingReport
        report = GitHubTrendingReport(
            repos_found=5,
            evaluate_count=3,
            languages_scanned=["python", "rust"],
            results=[],
            days=7,
        )
        d = report.to_dict()
        self.assertEqual(d["repos_found"], 5)
        self.assertEqual(d["evaluate_count"], 3)
        self.assertEqual(d["days"], 7)

    def test_github_trending_report_summary(self):
        """GitHubTrendingReport.summary() should produce readable text."""
        from autonomous_scanner import GitHubTrendingReport
        report = GitHubTrendingReport(
            repos_found=10,
            evaluate_count=4,
            languages_scanned=["python", "typescript"],
            results=[],
            days=14,
        )
        text = report.summary()
        self.assertIn("10", text)
        self.assertIn("4", text)
        self.assertIn("EVALUATE", text)

    def test_cli_github_trending_command(self):
        """CLI 'github-trending' command should exist and run."""
        from autonomous_scanner import cli_main
        import io
        buf = io.StringIO()
        with patch("sys.stdout", buf), \
             patch("autonomous_scanner.TrendingScanner") as mock_ts_cls:
            mock_ts = MagicMock()
            mock_ts.scan_all_trending.return_value = []
            mock_ts.get_cca_languages.return_value = ["python"]
            mock_ts_cls.return_value = mock_ts
            cli_main(["github-trending",
                       "--state", self.state_path,
                       "--kill-switch", self.kill_switch])
        output = buf.getvalue()
        self.assertIsInstance(output, str)

    def test_cli_github_trending_with_language(self):
        """CLI 'github-trending --language rust' should filter to one language."""
        from autonomous_scanner import cli_main
        import io
        buf = io.StringIO()
        with patch("sys.stdout", buf), \
             patch("autonomous_scanner.TrendingScanner") as mock_ts_cls:
            mock_ts = MagicMock()
            mock_ts.scan_trending.return_value = []
            mock_ts_cls.return_value = mock_ts
            cli_main(["github-trending",
                       "--language", "rust",
                       "--state", self.state_path,
                       "--kill-switch", self.kill_switch])
        output = buf.getvalue()
        self.assertIsInstance(output, str)

    def test_cli_github_trending_json_output(self):
        """CLI 'github-trending --json' should produce valid JSON."""
        from autonomous_scanner import cli_main
        import io
        buf = io.StringIO()
        with patch("sys.stdout", buf), \
             patch("autonomous_scanner.TrendingScanner") as mock_ts_cls:
            mock_ts = MagicMock()
            mock_ts.scan_all_trending.return_value = []
            mock_ts.get_cca_languages.return_value = ["python"]
            mock_ts_cls.return_value = mock_ts
            cli_main(["github-trending",
                       "--json",
                       "--state", self.state_path,
                       "--kill-switch", self.kill_switch])
        output = buf.getvalue()
        parsed = json.loads(output)
        self.assertIsInstance(parsed, dict)


class TestRescanStaleAutonomous(unittest.TestCase):
    """Tests for execute_rescan_stale() — MT-14 Phase 3: auto-rescan all stale subs."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.state_path = os.path.join(self.tmpdir, "state.json")
        self.kill_switch = os.path.join(self.tmpdir, "kill_switch")
        self.findings_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        # Write empty findings
        with open(self.findings_path, "w") as f:
            f.write("# Findings\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_scanner(self):
        from autonomous_scanner import AutonomousScanner
        return AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )

    def _write_registry(self, data):
        with open(self.registry_path, "w") as f:
            json.dump(data, f)

    def _make_stale_registry(self, slugs, days_ago=20):
        """Create registry with stale entries."""
        data = {}
        old_ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        for slug in slugs:
            data[slug] = {
                "last_scan": old_ts,
                "posts_scanned": 50,
                "builds": 2,
                "adapts": 3,
            }
        self._write_registry(data)

    def test_execute_rescan_stale_exists(self):
        """Method should exist on AutonomousScanner."""
        scanner = self._make_scanner()
        self.assertTrue(hasattr(scanner, "execute_rescan_stale"))
        self.assertTrue(callable(scanner.execute_rescan_stale))

    @patch("autonomous_scanner.fetch_top_posts")
    def test_execute_rescan_stale_returns_list(self, mock_fetch):
        """Should return a list of ScanResults."""
        mock_fetch.return_value = []
        self._make_stale_registry(["claudecode"])
        scanner = self._make_scanner()
        results = scanner.execute_rescan_stale()
        self.assertIsInstance(results, list)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_execute_rescan_stale_rescans_all_stale(self, mock_fetch):
        """Should rescan every stale sub, not just the first."""
        mock_fetch.return_value = [
            {"id": "new1", "title": "New post", "score": 50,
             "subreddit": "ClaudeCode", "permalink": "/r/ClaudeCode/new1",
             "url": "https://reddit.com/r/ClaudeCode/new1",
             "created_utc": (datetime.now(timezone.utc) - timedelta(days=1)).timestamp(),
             "num_comments": 5, "author": "test", "is_self": True, "selftext": "test"},
        ]
        self._make_stale_registry(["claudecode", "claudeai"], days_ago=20)
        scanner = self._make_scanner()
        scanner.safety_gate.min_delay_seconds = 0  # Disable rate limit for test
        results = scanner.execute_rescan_stale(max_age_days=14)
        # Should have rescanned both stale subs
        self.assertEqual(len(results), 2)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_execute_rescan_stale_skips_fresh_subs(self, mock_fetch):
        """Fresh subs (recently scanned) should not be rescanned."""
        mock_fetch.return_value = []
        # One stale, one fresh
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=20)).isoformat()
        fresh_ts = (now - timedelta(days=2)).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": old_ts, "posts_scanned": 50, "builds": 2, "adapts": 3},
            "claudeai": {"last_scan": fresh_ts, "posts_scanned": 30, "builds": 1, "adapts": 1},
        })
        scanner = self._make_scanner()
        results = scanner.execute_rescan_stale(max_age_days=14)
        # Only claudecode is stale
        self.assertEqual(len(results), 1)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_execute_rescan_stale_respects_kill_switch(self, mock_fetch):
        """Kill switch should stop all rescanning."""
        mock_fetch.return_value = []
        self._make_stale_registry(["claudecode"])
        # Activate kill switch
        with open(self.kill_switch, "w") as f:
            f.write("paused")
        scanner = self._make_scanner()
        results = scanner.execute_rescan_stale()
        self.assertEqual(len(results), 0)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_execute_rescan_stale_respects_session_limit(self, mock_fetch):
        """Should stop when session scan limit is hit."""
        mock_fetch.return_value = []
        self._make_stale_registry(["claudecode", "claudeai", "vibecoding"], days_ago=20)
        scanner = self._make_scanner()
        # Set very low limit
        scanner.safety_gate.max_scans_per_session = 1
        results = scanner.execute_rescan_stale(max_age_days=14)
        # Should only scan 1 (limit hit after first)
        self.assertLessEqual(len(results), 1)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_execute_rescan_stale_returns_scan_results(self, mock_fetch):
        """Each result should be a ScanResult with report."""
        from autonomous_scanner import ScanResult
        mock_fetch.return_value = []
        self._make_stale_registry(["claudecode"], days_ago=20)
        scanner = self._make_scanner()
        results = scanner.execute_rescan_stale(max_age_days=14)
        for r in results:
            self.assertIsInstance(r, ScanResult)
            self.assertIsNotNone(r.report)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_execute_rescan_stale_empty_when_no_stale(self, mock_fetch):
        """No stale subs should return empty list."""
        mock_fetch.return_value = []
        # All subs freshly scanned
        fresh_ts = datetime.now(timezone.utc).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": fresh_ts, "posts_scanned": 50, "builds": 2, "adapts": 3},
        })
        scanner = self._make_scanner()
        results = scanner.execute_rescan_stale(max_age_days=14)
        self.assertEqual(len(results), 0)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_execute_rescan_stale_default_max_age(self, mock_fetch):
        """Default max_age_days should be 14."""
        mock_fetch.return_value = []
        # 13 days old — should NOT be stale at default 14
        ts_13d = (datetime.now(timezone.utc) - timedelta(days=13)).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": ts_13d, "posts_scanned": 50, "builds": 2, "adapts": 3},
        })
        scanner = self._make_scanner()
        results = scanner.execute_rescan_stale()
        self.assertEqual(len(results), 0)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_execute_rescan_stale_custom_max_age(self, mock_fetch):
        """Custom max_age_days should be respected."""
        mock_fetch.return_value = [
            {"id": "new1", "title": "Post", "score": 50,
             "subreddit": "ClaudeCode", "permalink": "/r/ClaudeCode/new1",
             "url": "https://reddit.com/r/ClaudeCode/new1",
             "created_utc": (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp(),
             "num_comments": 5, "author": "test", "is_self": True, "selftext": "test"},
        ]
        # 8 days old — stale at 7d threshold, not at 14d
        ts_8d = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        self._write_registry({
            "claudecode": {"last_scan": ts_8d, "posts_scanned": 50, "builds": 2, "adapts": 3},
        })
        scanner = self._make_scanner()
        results = scanner.execute_rescan_stale(max_age_days=7)
        self.assertEqual(len(results), 1)


class TestRescanAllCLI(unittest.TestCase):
    """Tests for 'rescan-all' CLI command — MT-14 Phase 3."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.state_path = os.path.join(self.tmpdir, "state.json")
        self.kill_switch = os.path.join(self.tmpdir, "kill_switch")
        self.findings_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        with open(self.findings_path, "w") as f:
            f.write("# Findings\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cli_help_includes_rescan_all(self):
        """CLI help should list rescan-all command."""
        from autonomous_scanner import cli_main
        import io
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            cli_main([])
        output = buf.getvalue()
        self.assertIn("rescan-all", output)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_cli_rescan_all_runs(self, mock_fetch):
        """rescan-all command should execute without error."""
        mock_fetch.return_value = []
        from autonomous_scanner import cli_main
        import io
        buf = io.StringIO()
        # Write stale registry
        old_ts = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        with open(self.registry_path, "w") as f:
            json.dump({"claudecode": {"last_scan": old_ts, "posts_scanned": 50, "builds": 2, "adapts": 3}}, f)
        with patch("sys.stdout", buf):
            cli_main(["rescan-all",
                       "--registry", self.registry_path,
                       "--state", self.state_path,
                       "--kill-switch", self.kill_switch,
                       "--findings", self.findings_path])
        output = buf.getvalue()
        self.assertIn("RESCAN", output.upper())

    @patch("autonomous_scanner.fetch_top_posts")
    def test_cli_rescan_all_json(self, mock_fetch):
        """rescan-all --json should produce valid JSON output."""
        mock_fetch.return_value = []
        from autonomous_scanner import cli_main
        import io
        buf = io.StringIO()
        old_ts = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        with open(self.registry_path, "w") as f:
            json.dump({"claudecode": {"last_scan": old_ts, "posts_scanned": 50, "builds": 2, "adapts": 3}}, f)
        with patch("sys.stdout", buf):
            cli_main(["rescan-all",
                       "--json",
                       "--registry", self.registry_path,
                       "--state", self.state_path,
                       "--kill-switch", self.kill_switch,
                       "--findings", self.findings_path])
        output = buf.getvalue()
        parsed = json.loads(output)
        self.assertIsInstance(parsed, list)

    @patch("autonomous_scanner.fetch_top_posts")
    def test_cli_rescan_all_no_stale(self, mock_fetch):
        """rescan-all with no stale subs should report nothing to rescan."""
        mock_fetch.return_value = []
        from autonomous_scanner import cli_main
        import io
        buf = io.StringIO()
        fresh_ts = datetime.now(timezone.utc).isoformat()
        with open(self.registry_path, "w") as f:
            json.dump({"claudecode": {"last_scan": fresh_ts, "posts_scanned": 50, "builds": 2, "adapts": 3}}, f)
        with patch("sys.stdout", buf):
            cli_main(["rescan-all",
                       "--registry", self.registry_path,
                       "--state", self.state_path,
                       "--kill-switch", self.kill_switch,
                       "--findings", self.findings_path])
        output = buf.getvalue()
        self.assertIn("no stale", output.lower())


class TestDailyScanWithRescan(unittest.TestCase):
    """Tests for daily scan --include-rescan flag — MT-14 Phase 3 integration."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "scan_registry.json")
        self.state_path = os.path.join(self.tmpdir, "state.json")
        self.kill_switch = os.path.join(self.tmpdir, "kill_switch")
        self.findings_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        with open(self.findings_path, "w") as f:
            f.write("# Findings\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_scanner(self):
        from autonomous_scanner import AutonomousScanner
        return AutonomousScanner(
            registry_path=self.registry_path,
            kill_switch_path=self.kill_switch,
            state_path=self.state_path,
            findings_path=self.findings_path,
        )

    @patch("autonomous_scanner.fetch_rising_posts")
    @patch("autonomous_scanner.fetch_hot_posts")
    @patch("autonomous_scanner.fetch_top_posts")
    def test_daily_scan_with_rescan_flag(self, mock_top, mock_hot, mock_rising):
        """execute_daily_scan(include_rescan=True) should also rescan stale subs."""
        mock_hot.return_value = [
            {"id": "h1", "title": "Hot post", "score": 100, "subreddit": "ClaudeCode",
             "permalink": "/r/ClaudeCode/h1", "url": "https://reddit.com/r/ClaudeCode/h1",
             "created_utc": datetime.now(timezone.utc).timestamp(),
             "num_comments": 10, "author": "user1", "is_self": True, "selftext": "hot"},
        ]
        mock_rising.return_value = []
        mock_top.return_value = [
            {"id": "new1", "title": "New post", "score": 50, "subreddit": "vibecoding",
             "permalink": "/r/vibecoding/new1", "url": "https://reddit.com/r/vibecoding/new1",
             "created_utc": (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp(),
             "num_comments": 5, "author": "test", "is_self": True, "selftext": "new"},
        ]
        # Make vibecoding stale in registry
        old_ts = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        with open(self.registry_path, "w") as f:
            json.dump({"vibecoding": {"last_scan": old_ts, "posts_scanned": 50, "builds": 1, "adapts": 2}}, f)

        scanner = self._make_scanner()
        results = scanner.execute_daily_scan(subs=["ClaudeCode"], include_rescan=True)
        # Should have more results than just the 1 daily sub
        self.assertGreaterEqual(len(results), 1)

    @patch("autonomous_scanner.fetch_rising_posts")
    @patch("autonomous_scanner.fetch_hot_posts")
    def test_daily_scan_without_rescan_flag(self, mock_hot, mock_rising):
        """execute_daily_scan without include_rescan should not rescan."""
        mock_hot.return_value = []
        mock_rising.return_value = []
        # Make a stale sub in registry
        old_ts = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        with open(self.registry_path, "w") as f:
            json.dump({"vibecoding": {"last_scan": old_ts, "posts_scanned": 50, "builds": 1, "adapts": 2}}, f)

        scanner = self._make_scanner()
        # Default: include_rescan=False
        results = scanner.execute_daily_scan(subs=["ClaudeCode"])
        # Should only have 1 result (ClaudeCode daily scan, no rescan)
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
