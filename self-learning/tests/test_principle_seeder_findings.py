#!/usr/bin/env python3
"""Tests for principle_seeder.py — seed from FINDINGS_LOG.md (MT-28 growth)."""
import json
import os
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from principle_seeder import (
    parse_findings_for_seeding,
    finding_to_principle_text,
    map_finding_to_domain,
    seed_principles_from_findings,
)


SAMPLE_FINDINGS = """# Findings Log

[2026-03-15] [BUILD] [Frontier 5: Usage Dashboard] CShip — Rust statusline for Claude Code with cost, context bar (200pts) — https://reddit.com/r/ClaudeCode/123
[2026-03-15] [SKIP] [Frontier 1: Memory] Some skipped post — https://reddit.com/r/ClaudeCode/456
[2026-03-17] [BUILD] [Frontier 4: Agent Guard] "We got hacked" (458pts, 206c). Claude exposed port 5555 — https://reddit.com/r/ClaudeCode/789
[2026-03-18] [ADAPT] [Frontier 1: Memory] OMEGA memory system deep-dive (120pts). Semantic search + decay + confidence scoring — https://reddit.com/r/ClaudeCode/012
[2026-03-24] [REFERENCE] [General] Some reference — https://reddit.com/r/ClaudeCode/678
[2026-03-24] [BUILD] [NEW] QuantumLintZapper — revolutionary quantum-powered linting for Zig (10pts) — https://github.com/example/qlint
[2026-03-25] [BUILD] [Frontier 1: Memory] "Claude Code can now /dream" (1657pts). Anthropic ships native memory consolidation — https://reddit.com/r/ClaudeCode/dream
"""


class TestParseFindingsForSeeding(unittest.TestCase):

    def test_parses_build_and_adapt(self):
        results = parse_findings_for_seeding(SAMPLE_FINDINGS)
        verdicts = {r["verdict"] for r in results}
        self.assertIn("BUILD", verdicts)
        self.assertIn("ADAPT", verdicts)

    def test_excludes_skip_and_reference(self):
        results = parse_findings_for_seeding(SAMPLE_FINDINGS)
        verdicts = {r["verdict"] for r in results}
        self.assertNotIn("SKIP", verdicts)
        self.assertNotIn("REFERENCE", verdicts)

    def test_extracts_points(self):
        results = parse_findings_for_seeding(SAMPLE_FINDINGS)
        hacked = [r for r in results if "hacked" in r["title"]]
        self.assertEqual(len(hacked), 1)
        self.assertEqual(hacked[0]["points"], 458)

    def test_extracts_frontier(self):
        results = parse_findings_for_seeding(SAMPLE_FINDINGS)
        cship = [r for r in results if "CShip" in r["title"]]
        self.assertEqual(len(cship), 1)
        self.assertIn("Usage Dashboard", cship[0]["frontier"])

    def test_empty_input(self):
        results = parse_findings_for_seeding("")
        self.assertEqual(results, [])

    def test_min_points_filter(self):
        results = parse_findings_for_seeding(SAMPLE_FINDINGS, min_points=100)
        # QuantumLint has 10pts, should be filtered
        names = [r["title"] for r in results]
        self.assertFalse(any("QuantumLint" in n for n in names))
        # CShip has 200pts, should pass
        self.assertTrue(any("CShip" in n for n in names))


class TestFindingToPrincipleText(unittest.TestCase):

    def test_build_finding(self):
        text = finding_to_principle_text("BUILD", "CShip statusline", "Frontier 5: Usage Dashboard")
        self.assertIn("CShip", text)
        self.assertIn("usage", text.lower())

    def test_adapt_finding(self):
        text = finding_to_principle_text("ADAPT", "OMEGA memory", "Frontier 1: Memory")
        self.assertIn("OMEGA", text)

    def test_not_empty(self):
        text = finding_to_principle_text("BUILD", "SomeTool", "NEW")
        self.assertTrue(len(text) > 10)


class TestMapFindingToDomain(unittest.TestCase):

    def test_memory_frontier(self):
        domain = map_finding_to_domain("Frontier 1: Memory", "OMEGA memory system")
        self.assertEqual(domain, "cca_operations")

    def test_agent_guard_frontier(self):
        domain = map_finding_to_domain("Frontier 4: Agent Guard", "security tool")
        self.assertEqual(domain, "code_quality")

    def test_usage_frontier(self):
        domain = map_finding_to_domain("Frontier 5: Usage Dashboard", "token counter")
        self.assertEqual(domain, "cca_operations")

    def test_new_frontier(self):
        domain = map_finding_to_domain("NEW", "some brand new tool")
        self.assertIn(domain, ["general", "cca_operations", "code_quality",
                                "nuclear_scan", "session_management",
                                "trading_research", "trading_execution"])

    def test_trading_content(self):
        domain = map_finding_to_domain("NEW", "Kalshi trading bot edge detection")
        self.assertEqual(domain, "trading_research")


class TestSeedPrinciplesFromFindings(unittest.TestCase):

    def test_seeds_principles(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as pf:
            pf.flush()
            principles_path = pf.name

        try:
            results = seed_principles_from_findings(
                findings_text=SAMPLE_FINDINGS,
                principles_path=principles_path,
                min_points=0,
            )
            self.assertGreater(len(results), 0)

            # Verify principles written
            with open(principles_path) as f:
                lines = [l.strip() for l in f if l.strip()]
            self.assertGreater(len(lines), 0)

            # Each line should be valid JSON with expected fields
            for line in lines:
                p = json.loads(line)
                self.assertIn("text", p)
                self.assertIn("source_domain", p)
        finally:
            os.unlink(principles_path)

    def test_dedup_prevents_double_seed(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as pf:
            pf.flush()
            principles_path = pf.name

        try:
            r1 = seed_principles_from_findings(
                findings_text=SAMPLE_FINDINGS,
                principles_path=principles_path,
                min_points=0,
            )
            r2 = seed_principles_from_findings(
                findings_text=SAMPLE_FINDINGS,
                principles_path=principles_path,
                min_points=0,
            )
            self.assertEqual(len(r2), 0, "Second seed should find all duplicates")
        finally:
            os.unlink(principles_path)

    def test_min_points_respected(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as pf:
            pf.flush()
            principles_path = pf.name

        try:
            results = seed_principles_from_findings(
                findings_text=SAMPLE_FINDINGS,
                principles_path=principles_path,
                min_points=200,
            )
            # Only findings with 200+ points should seed
            # CShip=200, hacked=458, dream=1657, OMEGA=120 (ADAPT, 120 < 200)
            for r in results:
                self.assertGreaterEqual(r["points"], 200)
        finally:
            os.unlink(principles_path)

    def test_source_context_includes_findings(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as pf:
            pf.flush()
            principles_path = pf.name

        try:
            results = seed_principles_from_findings(
                findings_text=SAMPLE_FINDINGS,
                principles_path=principles_path,
                min_points=0,
            )
            for r in results:
                self.assertIn("FINDINGS_LOG", r["source_context"])
        finally:
            os.unlink(principles_path)

    def test_empty_findings(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as pf:
            pf.flush()
            principles_path = pf.name

        try:
            results = seed_principles_from_findings(
                findings_text="",
                principles_path=principles_path,
            )
            self.assertEqual(results, [])
        finally:
            os.unlink(principles_path)


class TestTradeSeeder(unittest.TestCase):
    """Tests for seed_principles_from_trades (MT-28 growth, S193)."""

    def setUp(self):
        from principle_seeder import seed_principles_from_trades, proposal_to_principle_text
        self.seed_fn = seed_principles_from_trades
        self.text_fn = proposal_to_principle_text

    def _make_proposal(self, pattern="win_rate_drift", severity="warning",
                       recommendation="WR dropped from 95% to 80%", p_value=0.01):
        return {
            "pattern": pattern,
            "severity": severity,
            "recommendation": recommendation,
            "action_type": "monitor",
            "evidence": {"p_value": p_value},
        }

    def test_proposal_to_principle_text_warning(self):
        p = self._make_proposal(severity="warning")
        text = self.text_fn(p)
        self.assertIn("Trade signal", text)
        self.assertIn("win_rate_drift", text)

    def test_proposal_to_principle_text_info(self):
        p = self._make_proposal(severity="info")
        text = self.text_fn(p)
        self.assertIn("Trade observation", text)

    def test_proposal_text_truncation(self):
        long_rec = "A" * 200
        p = self._make_proposal(recommendation=long_rec)
        text = self.text_fn(p)
        self.assertLessEqual(len(text), 250)  # prefix + truncated rec

    def test_seed_empty_proposals(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            principles_path = f.name
        try:
            results = self.seed_fn([], principles_path=principles_path)
            self.assertEqual(results, [])
        finally:
            os.unlink(principles_path)

    def test_seed_single_proposal(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            principles_path = f.name
        try:
            proposals = [self._make_proposal()]
            results = self.seed_fn(proposals, principles_path=principles_path)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["domain"], "trading_execution")
            self.assertEqual(results[0]["pattern"], "win_rate_drift")
        finally:
            os.unlink(principles_path)

    def test_seed_deduplicates(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            principles_path = f.name
        try:
            proposals = [self._make_proposal(), self._make_proposal()]
            results = self.seed_fn(proposals, principles_path=principles_path)
            self.assertEqual(len(results), 1)  # second is duplicate
        finally:
            os.unlink(principles_path)

    def test_seed_multiple_patterns(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            principles_path = f.name
        try:
            proposals = [
                self._make_proposal(pattern="win_rate_drift", recommendation="WR drift detected"),
                self._make_proposal(pattern="time_of_day_bias", recommendation="Hour 3 UTC is worst"),
                self._make_proposal(pattern="edge_erosion", recommendation="Edge declining"),
            ]
            results = self.seed_fn(proposals, principles_path=principles_path)
            self.assertEqual(len(results), 3)
            domains = {r["domain"] for r in results}
            self.assertIn("trading_execution", domains)
            self.assertIn("trading_research", domains)
        finally:
            os.unlink(principles_path)

    def test_seeded_principles_persist(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            principles_path = f.name
        try:
            proposals = [self._make_proposal()]
            self.seed_fn(proposals, principles_path=principles_path)
            with open(principles_path) as f:
                lines = [l.strip() for l in f if l.strip()]
            self.assertEqual(len(lines), 1)
            p = json.loads(lines[0])
            self.assertIn("trade_reflector", p.get("source_context", ""))
        finally:
            os.unlink(principles_path)

    def test_domain_mapping_sizing(self):
        p = self._make_proposal(pattern="sizing_inefficiency")
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            principles_path = f.name
        try:
            results = self.seed_fn([p], principles_path=principles_path)
            self.assertEqual(results[0]["domain"], "trading_execution")
        finally:
            os.unlink(principles_path)

    def test_domain_mapping_unknown_pattern(self):
        p = self._make_proposal(pattern="unknown_pattern")
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            principles_path = f.name
        try:
            results = self.seed_fn([p], principles_path=principles_path)
            self.assertEqual(results[0]["domain"], "trading_research")
        finally:
            os.unlink(principles_path)


if __name__ == "__main__":
    unittest.main()
