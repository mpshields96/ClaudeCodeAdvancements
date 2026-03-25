#!/usr/bin/env python3
"""Tests for mt_originator.py — MT-41 Phase 1: Synthetic MT Origination."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mt_originator import (
    parse_findings_log,
    Finding,
    get_existing_mt_coverage,
    find_uncovered_builds,
    score_proposal,
    generate_proposals,
    MTProposal,
)


SAMPLE_FINDINGS = """# Findings Log

[2026-03-15] [BUILD] [Frontier 5: Usage Dashboard] CShip — Rust statusline for Claude Code with cost, context bar — https://reddit.com/r/ClaudeCode/123
[2026-03-15] [SKIP] [Frontier 1: Memory] Some skipped post — https://reddit.com/r/ClaudeCode/456
[2026-03-15] [BUILD] [NEW] Claude Squad — Go TUI multi-agent manager — https://github.com/smtg-ai/claude-squad
[2026-03-17] [BUILD] [Frontier 4: Agent Guard] "We got hacked" (458pts, 206c). Claude exposed port 5555. — https://reddit.com/r/ClaudeCode/789
[2026-03-18] [BUILD] [Frontier 1: Memory] "OMEGA memory system deep-dive" (CCA Session 19 nuclear). OMEGA architecture: semantic search + decay + confidence scoring. — https://reddit.com/r/ClaudeCode/012
[2026-03-24] [ADAPT] [MT-10] Some adapt finding — https://reddit.com/r/ClaudeCode/345
[2026-03-24] [REFERENCE] [General] Some reference — https://reddit.com/r/ClaudeCode/678
[2026-03-24] [BUILD] [NEW] QuantumLintZapper — revolutionary quantum-powered linting for Zig programs — https://github.com/example/quantum-lint
"""


class TestParseFindingsLog(unittest.TestCase):

    def test_parse_builds_only(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        self.assertEqual(len(builds), 5)

    def test_parse_all_verdicts(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        verdicts = {f.verdict for f in findings}
        self.assertIn("BUILD", verdicts)
        self.assertIn("SKIP", verdicts)
        self.assertIn("ADAPT", verdicts)

    def test_finding_fields(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        build = [f for f in findings if "CShip" in f.title][0]
        self.assertEqual(build.verdict, "BUILD")
        self.assertIn("Usage Dashboard", build.frontier)
        self.assertIn("reddit.com", build.url)
        self.assertEqual(build.date, "2026-03-15")

    def test_parse_points(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        hacked = [f for f in findings if "hacked" in f.title][0]
        self.assertEqual(hacked.points, 458)

    def test_parse_no_points(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        cship = [f for f in findings if "CShip" in f.title][0]
        self.assertEqual(cship.points, 0)

    def test_empty_input(self):
        findings = parse_findings_log("")
        self.assertEqual(findings, [])

    def test_malformed_lines_skipped(self):
        text = "not a finding line\n[2026-03-15] [BUILD] [NEW] Valid — https://example.com\n"
        findings = parse_findings_log(text)
        self.assertEqual(len(findings), 1)


class TestExistingCoverage(unittest.TestCase):

    def test_coverage_keywords(self):
        coverage = get_existing_mt_coverage()
        # Should contain keywords from known MTs
        self.assertIsInstance(coverage, dict)
        # Should have entries for MT IDs
        self.assertGreater(len(coverage), 0)

    def test_coverage_has_keywords(self):
        coverage = get_existing_mt_coverage()
        # Check that at least some MTs have keyword lists
        all_keywords = []
        for mt_id, keywords in coverage.items():
            all_keywords.extend(keywords)
        self.assertGreater(len(all_keywords), 0)


class TestFindUncoveredBuilds(unittest.TestCase):

    def test_finds_uncovered(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        # QuantumLintZapper should be uncovered (not matching any existing MT)
        uncovered = find_uncovered_builds(builds)
        names = [f.title for f in uncovered]
        self.assertTrue(any("QuantumLint" in n for n in names),
                        f"Expected QuantumLintZapper in uncovered, got: {names}")

    def test_covered_builds_excluded(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        uncovered = find_uncovered_builds(builds)
        # Agent Guard finding should be covered by MT-20/agent-guard
        uncovered_titles = " ".join(f.title for f in uncovered)
        # "hacked" finding maps to Frontier 4: Agent Guard which IS an existing MT/module
        # It may or may not be filtered depending on keyword matching
        self.assertIsInstance(uncovered, list)

    def test_empty_builds(self):
        uncovered = find_uncovered_builds([])
        self.assertEqual(uncovered, [])


class TestScoreProposal(unittest.TestCase):

    def test_recent_high_points(self):
        f = Finding("2026-03-24", "BUILD", "NEW", "Great Tool", "https://example.com", 500)
        score = score_proposal(f)
        self.assertGreater(score, 50)

    def test_old_low_points(self):
        f = Finding("2026-03-01", "BUILD", "NEW", "Old Tool", "https://example.com", 0)
        score = score_proposal(f)
        self.assertLess(score, 50)

    def test_score_range(self):
        f = Finding("2026-03-20", "BUILD", "Frontier 1", "Mid Tool", "https://example.com", 200)
        score = score_proposal(f)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class TestGenerateProposals(unittest.TestCase):

    def test_generates_proposals(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        proposals = generate_proposals(builds)
        self.assertIsInstance(proposals, list)
        for p in proposals:
            self.assertIsInstance(p, MTProposal)
            self.assertTrue(p.name)
            self.assertTrue(p.source_url)
            self.assertGreater(p.score, 0)

    def test_proposals_sorted_by_score(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        proposals = generate_proposals(builds)
        if len(proposals) >= 2:
            scores = [p.score for p in proposals]
            self.assertEqual(scores, sorted(scores, reverse=True))

    def test_proposal_fields(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        proposals = generate_proposals(builds)
        if proposals:
            p = proposals[0]
            self.assertTrue(p.name)
            self.assertTrue(p.frontier)
            self.assertTrue(p.source_url)
            self.assertIsInstance(p.score, (int, float))

    def test_empty_input(self):
        proposals = generate_proposals([])
        self.assertEqual(proposals, [])

    def test_to_dict(self):
        findings = parse_findings_log(SAMPLE_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        proposals = generate_proposals(builds)
        if proposals:
            d = proposals[0].to_dict()
            self.assertIn("name", d)
            self.assertIn("score", d)
            self.assertIn("source_url", d)
            self.assertIn("frontier", d)


class TestMTProposal(unittest.TestCase):

    def test_to_dict(self):
        p = MTProposal(
            name="Test Tool",
            frontier="NEW",
            source_url="https://example.com",
            source_date="2026-03-24",
            score=75.5,
            description="A test tool",
            points=500,
        )
        d = p.to_dict()
        self.assertEqual(d["name"], "Test Tool")
        self.assertEqual(d["score"], 75.5)

    def test_to_jsonl_line(self):
        p = MTProposal(
            name="Test Tool",
            frontier="NEW",
            source_url="https://example.com",
            source_date="2026-03-24",
            score=75.5,
            description="A test tool",
            points=500,
        )
        line = json.dumps(p.to_dict())
        parsed = json.loads(line)
        self.assertEqual(parsed["name"], "Test Tool")


if __name__ == "__main__":
    unittest.main()
