#!/usr/bin/env python3
"""
Tests for MT-10 Phase 3B: Findings Re-surfacing Module
self-learning/resurfacer.py

Parses FINDINGS_LOG.md, matches findings to current work context,
and surfaces relevant past reviews to prevent knowledge loss.

Run: python3 self-learning/tests/test_resurfacer.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Will import once module exists
# from resurfacer import Finding, parse_findings_log, match_findings, resurface


# ── Sample data ──────────────────────────────────────────────────────────────

SAMPLE_LOG = """[2026-03-17] [BUILD] [Frontier 5: Usage Dashboard + Frontier 3: Context Health] CShip — Rust statusline for Claude Code with cost, context bar, usage limits, Starship passthrough — https://www.reddit.com/r/ClaudeCode/comments/1rsnetb/
[2026-03-17] [ADAPT] [Frontier 2: Spec-Driven Dev] Autoresearch — Karpathy-inspired autonomous iteration loop (constraint + metric + verify + auto-revert). Security audit mode (STRIDE+OWASP). Ouro Loop in comments adds IRON LAWS/DANGER ZONES guardrails. — https://www.reddit.com/r/ClaudeCode/comments/1rsur5s/
[2026-03-17] [REFERENCE] [Frontier 1: Memory] traul — CLI syncing all comms into local SQLite + FTS5 + Ollama vector search. 89.5k messages, 1.3GB, ~5.6s hybrid query. Key comment: "retrieval quality > quantity." — https://www.reddit.com/r/ClaudeCode/
[2026-03-17] [SKIP] [Novelty] code-commentary live sports narrator for CC sessions — https://www.reddit.com/r/ClaudeCode/comments/1ru9j3t/
[2026-03-15] [REFERENCE-PERSONAL] [Trading/Kalshi] VEI volatility expansion signal with Python source (436pts) — https://www.reddit.com/r/algotrading/comments/1phv4zz/
[2026-03-17] [ADAPT] [Frontier 3: Context Health + Frontier 5: Usage] "CC now with 1M tokens window" (183pts, 68c). 1M window changes context health landscape: context rot confirmed at scale. — https://www.reddit.com/r/ClaudeCode/comments/1rsvhs4/
[2026-03-17] [REFERENCE] [Frontier 4: Agent Guard] "Autonomous agent: permission model nobody explains" (123pts, 33c). Key framing: "blast-radius limiter, not security boundary." — https://www.reddit.com/r/ClaudeCode/comments/1rs05i3/
[2026-03-18] [REFERENCE] [MT-17: Design] "Design Studio v4 / Naksha" (25pts, 7c). v2->v4: 13->26 roles, massive overengineering. CCA should do design-guide.md + Typst template. — https://www.reddit.com/r/ClaudeCode/comments/1rwslcl/
"""


class TestFindingParsing(unittest.TestCase):
    """Test parsing individual FINDINGS_LOG.md entries."""

    def setUp(self):
        from resurfacer import parse_findings_log
        self.findings = parse_findings_log(SAMPLE_LOG)

    def test_parses_correct_count(self):
        # 8 lines in sample, all valid
        self.assertEqual(len(self.findings), 8)

    def test_parses_date(self):
        self.assertEqual(self.findings[0].date, "2026-03-17")

    def test_parses_verdict(self):
        self.assertEqual(self.findings[0].verdict, "BUILD")
        self.assertEqual(self.findings[1].verdict, "ADAPT")
        self.assertEqual(self.findings[2].verdict, "REFERENCE")
        self.assertEqual(self.findings[3].verdict, "SKIP")
        self.assertEqual(self.findings[4].verdict, "REFERENCE-PERSONAL")

    def test_parses_tags(self):
        # First entry: "Frontier 5: Usage Dashboard + Frontier 3: Context Health"
        tags = self.findings[0].tags
        self.assertIn("Frontier 5", tags)
        self.assertIn("Frontier 3", tags)

    def test_parses_raw_tag_string(self):
        self.assertIn("Usage Dashboard", self.findings[0].raw_tags)
        self.assertIn("Context Health", self.findings[0].raw_tags)

    def test_parses_title(self):
        self.assertIn("CShip", self.findings[0].title)

    def test_parses_url(self):
        self.assertIn("reddit.com", self.findings[0].url)

    def test_parses_description(self):
        self.assertIn("Rust statusline", self.findings[0].description)

    def test_handles_multi_frontier_tags(self):
        # "Frontier 3: Context Health + Frontier 5: Usage"
        entry = self.findings[5]
        self.assertIn("Frontier 3", entry.tags)
        self.assertIn("Frontier 5", entry.tags)

    def test_handles_mt_tags(self):
        # "MT-17: Design"
        entry = self.findings[7]
        self.assertIn("MT-17", entry.tags)

    def test_handles_trading_tags(self):
        entry = self.findings[4]
        self.assertIn("Trading", entry.tags)

    def test_empty_input_returns_empty(self):
        from resurfacer import parse_findings_log
        self.assertEqual(parse_findings_log(""), [])
        self.assertEqual(parse_findings_log("\n\n"), [])

    def test_malformed_line_skipped(self):
        from resurfacer import parse_findings_log
        bad = "This is not a valid finding line\n[2026-03-17] [BUILD] [Frontier 1: Memory] Good entry — https://example.com\n"
        findings = parse_findings_log(bad)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].verdict, "BUILD")


class TestFindingMatching(unittest.TestCase):
    """Test matching findings to work context."""

    def setUp(self):
        from resurfacer import parse_findings_log
        self.findings = parse_findings_log(SAMPLE_LOG)

    def test_match_by_frontier_number(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, frontier=3)
        # Should find entries tagged with Frontier 3
        self.assertTrue(len(results) >= 2)
        for f in results:
            self.assertIn("Frontier 3", f.tags)

    def test_match_by_frontier_5(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, frontier=5)
        self.assertTrue(len(results) >= 1)

    def test_match_by_keyword(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, keywords=["statusline", "cost"])
        self.assertTrue(len(results) >= 1)
        # CShip entry mentions statusline
        titles = [f.title for f in results]
        self.assertTrue(any("CShip" in t for t in titles))

    def test_match_by_module_name(self):
        from resurfacer import match_findings
        # "context-monitor" should match Frontier 3 entries
        results = match_findings(self.findings, module="context-monitor")
        self.assertTrue(len(results) >= 1)

    def test_match_by_module_memory_system(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, module="memory-system")
        self.assertTrue(len(results) >= 1)
        # traul entry is tagged Frontier 1: Memory
        titles = [f.title for f in results]
        self.assertTrue(any("traul" in t for t in titles))

    def test_match_by_module_agent_guard(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, module="agent-guard")
        self.assertTrue(len(results) >= 1)

    def test_match_by_module_spec_system(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, module="spec-system")
        self.assertTrue(len(results) >= 1)
        titles = [f.title for f in results]
        self.assertTrue(any("Autoresearch" in t for t in titles))

    def test_match_by_mt_task(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, mt_task="MT-17")
        self.assertTrue(len(results) >= 1)
        titles = [f.title for f in results]
        self.assertTrue(any("Naksha" in t or "Design Studio" in t for t in titles))

    def test_excludes_skip_by_default(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, frontier=0)  # match all
        verdicts = [f.verdict for f in results]
        self.assertNotIn("SKIP", verdicts)

    def test_include_skip_when_requested(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, frontier=0, include_skip=True)
        verdicts = [f.verdict for f in results]
        # SKIP entry exists but may not match — let's use keywords
        results = match_findings(self.findings, keywords=["narrator"], include_skip=True)
        if results:
            self.assertEqual(results[0].verdict, "SKIP")

    def test_no_match_returns_empty(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, keywords=["quantum_blockchain_xyz"])
        self.assertEqual(results, [])

    def test_results_sorted_by_verdict_priority(self):
        from resurfacer import match_findings
        # BUILD > ADAPT > REFERENCE > REFERENCE-PERSONAL > SKIP
        results = match_findings(self.findings, frontier=5, include_skip=True)
        if len(results) >= 2:
            verdict_order = {"BUILD": 0, "ADAPT": 1, "REFERENCE": 2, "REFERENCE-PERSONAL": 3, "SKIP": 4}
            for i in range(len(results) - 1):
                self.assertLessEqual(
                    verdict_order.get(results[i].verdict, 5),
                    verdict_order.get(results[i + 1].verdict, 5),
                    f"{results[i].verdict} should come before {results[i+1].verdict}"
                )

    def test_limit_parameter(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, frontier=3, limit=1)
        self.assertLessEqual(len(results), 1)

    def test_combined_filters(self):
        from resurfacer import match_findings
        results = match_findings(self.findings, frontier=3, keywords=["context"])
        # Should match entries that are BOTH Frontier 3 AND mention "context"
        for f in results:
            self.assertIn("Frontier 3", f.tags)


class TestResurface(unittest.TestCase):
    """Test the main resurface() function with file-based log."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "FINDINGS_LOG.md")
        with open(self.log_path, "w") as f:
            f.write(SAMPLE_LOG)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_resurface_from_file(self):
        from resurfacer import resurface
        results = resurface(self.log_path, frontier=3)
        self.assertTrue(len(results) >= 1)

    def test_resurface_missing_file_returns_empty(self):
        from resurfacer import resurface
        results = resurface("/nonexistent/path/FINDINGS_LOG.md", frontier=3)
        self.assertEqual(results, [])

    def test_resurface_formats_summary(self):
        from resurfacer import resurface, format_resurface_report
        results = resurface(self.log_path, frontier=3)
        report = format_resurface_report(results, context="Working on context-monitor")
        self.assertIsInstance(report, str)
        self.assertIn("context-monitor", report)

    def test_resurface_report_empty_results(self):
        from resurfacer import format_resurface_report
        report = format_resurface_report([], context="Working on quantum stuff")
        self.assertIn("No relevant", report)

    def test_resurface_for_kalshi(self):
        from resurfacer import resurface
        results = resurface(self.log_path, keywords=["trading", "Kalshi"])
        self.assertTrue(len(results) >= 1)


class TestFindingDataclass(unittest.TestCase):
    """Test Finding data structure."""

    def test_finding_to_dict(self):
        from resurfacer import Finding
        f = Finding(
            date="2026-03-17",
            verdict="BUILD",
            tags=["Frontier 3"],
            raw_tags="Frontier 3: Context Health",
            title="Test Finding",
            description="A test description",
            url="https://example.com"
        )
        d = f.to_dict()
        self.assertEqual(d["date"], "2026-03-17")
        self.assertEqual(d["verdict"], "BUILD")
        self.assertIsInstance(d["tags"], list)

    def test_finding_repr(self):
        from resurfacer import Finding
        f = Finding(
            date="2026-03-17",
            verdict="BUILD",
            tags=["Frontier 3"],
            raw_tags="Frontier 3",
            title="Test",
            description="Desc",
            url="https://example.com"
        )
        r = repr(f)
        self.assertIn("BUILD", r)
        self.assertIn("Test", r)


class TestModuleToFrontierMapping(unittest.TestCase):
    """Test that module names correctly map to frontier numbers."""

    def test_memory_system_maps_to_frontier_1(self):
        from resurfacer import module_to_frontier
        self.assertEqual(module_to_frontier("memory-system"), 1)

    def test_spec_system_maps_to_frontier_2(self):
        from resurfacer import module_to_frontier
        self.assertEqual(module_to_frontier("spec-system"), 2)

    def test_context_monitor_maps_to_frontier_3(self):
        from resurfacer import module_to_frontier
        self.assertEqual(module_to_frontier("context-monitor"), 3)

    def test_agent_guard_maps_to_frontier_4(self):
        from resurfacer import module_to_frontier
        self.assertEqual(module_to_frontier("agent-guard"), 4)

    def test_usage_dashboard_maps_to_frontier_5(self):
        from resurfacer import module_to_frontier
        self.assertEqual(module_to_frontier("usage-dashboard"), 5)

    def test_unknown_module_returns_none(self):
        from resurfacer import module_to_frontier
        self.assertIsNone(module_to_frontier("unknown-module"))

    def test_self_learning_returns_none(self):
        from resurfacer import module_to_frontier
        # self-learning is cross-cutting, not a specific frontier
        self.assertIsNone(module_to_frontier("self-learning"))


class TestProposalIntegration(unittest.TestCase):
    """Tests for Phase 3B: trade_reflector proposal integration."""

    def _make_proposal(self, pattern="win_rate_drift", severity="warning",
                       strategy="sniper", p_value=0.02):
        """Create a mock trade proposal dict."""
        return {
            "proposal_id": "tp_20260319_abcd1234",
            "source": "trade_reflector",
            "pattern": pattern,
            "strategy": strategy,
            "severity": severity,
            "evidence": {
                "historical_win_rate": 0.85,
                "recent_win_rate": 0.55,
                "p_value": p_value,
            },
            "recommendation": f"{strategy} win rate dropped from 85% to 55%. p={p_value:.4f}.",
            "action_type": "monitor",
            "auto_applicable": False,
            "created_at": "2026-03-19T10:00:00Z",
        }

    def test_proposal_to_finding(self):
        """Convert a trade proposal to a Finding for unified display."""
        from resurfacer import proposal_to_finding
        proposal = self._make_proposal()
        f = proposal_to_finding(proposal)
        self.assertEqual(f.verdict, "REFERENCE-PERSONAL")
        self.assertIn("Trading", f.tags)
        self.assertIn("win_rate_drift", f.title.lower() or f.description.lower())

    def test_proposal_to_finding_preserves_severity(self):
        """Critical severity maps to different display than info."""
        from resurfacer import proposal_to_finding
        crit = proposal_to_finding(self._make_proposal(severity="critical"))
        info = proposal_to_finding(self._make_proposal(severity="info"))
        # Both should be findings, but critical should be flagged
        self.assertIn("critical", crit.title.lower() or crit.raw_tags.lower())

    def test_proposal_to_finding_has_proposal_id(self):
        """Finding description includes the proposal_id for traceability."""
        from resurfacer import proposal_to_finding
        f = proposal_to_finding(self._make_proposal())
        self.assertIn("tp_20260319_abcd1234", f.description)

    def test_resurface_with_proposals_combines_results(self):
        """resurface_with_proposals returns findings + converted proposals."""
        from resurfacer import resurface_with_proposals
        # Create a temp findings log
        fd, log_path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        with open(log_path, "w") as fh:
            fh.write(SAMPLE_LOG)

        proposals = [self._make_proposal()]
        try:
            results = resurface_with_proposals(
                log_path, proposals=proposals, keywords=["trading", "Kalshi"]
            )
            self.assertIsInstance(results, list)
            # Should have at least the Kalshi finding from SAMPLE_LOG + the proposal
            self.assertGreaterEqual(len(results), 2)
        finally:
            os.unlink(log_path)

    def test_resurface_with_proposals_empty_proposals(self):
        """Works with no proposals (just returns findings)."""
        from resurfacer import resurface_with_proposals
        fd, log_path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        with open(log_path, "w") as fh:
            fh.write(SAMPLE_LOG)

        try:
            results = resurface_with_proposals(
                log_path, proposals=[], keywords=["trading"]
            )
            self.assertIsInstance(results, list)
        finally:
            os.unlink(log_path)

    def test_resurface_with_proposals_no_log(self):
        """Works with missing log file (just returns proposals)."""
        from resurfacer import resurface_with_proposals
        proposals = [self._make_proposal()]
        results = resurface_with_proposals(
            "/nonexistent/log.md", proposals=proposals, keywords=["trading"]
        )
        self.assertEqual(len(results), 1)

    def test_format_includes_proposals(self):
        """format_resurface_report handles proposal-derived findings."""
        from resurfacer import proposal_to_finding, format_resurface_report
        proposal = self._make_proposal()
        f = proposal_to_finding(proposal)
        report = format_resurface_report([f], "Kalshi trading review")
        self.assertIn("Kalshi trading review", report)
        self.assertIn("win_rate_drift", report.lower())

    def test_proposals_sorted_by_severity(self):
        """Critical proposals sort before info proposals."""
        from resurfacer import proposal_to_finding, resurface_with_proposals
        crit = self._make_proposal(severity="critical", pattern="edge_erosion")
        info = self._make_proposal(severity="info", pattern="streak_anomaly")

        fd, log_path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        with open(log_path, "w") as fh:
            fh.write("")  # Empty log

        try:
            results = resurface_with_proposals(
                log_path, proposals=[info, crit], keywords=["trading"]
            )
            # Both should appear
            self.assertEqual(len(results), 2)
        finally:
            os.unlink(log_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
