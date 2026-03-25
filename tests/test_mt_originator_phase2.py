#!/usr/bin/env python3
"""Tests for mt_originator.py — MT-41 Phase 2-3: Enhanced scoring + MASTER_TASKS append."""

import json
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mt_originator import (
    parse_findings_log,
    Finding,
    MTProposal,
    find_clusters,
    score_with_clusters,
    generate_rich_proposals,
    format_mt_entry,
    find_next_mt_id,
    append_to_master_tasks,
    load_proposals,
    get_top_proposals_for_briefing,
)


# --- Test data ---

CLUSTERED_FINDINGS = """# Findings Log

[2026-03-20] [BUILD] [Frontier 1: Memory] Claude Memory MCP — persistent memory via MCP server (200pts) — https://github.com/example/memory-mcp
[2026-03-21] [BUILD] [Frontier 1: Memory] MemoryLayer — another memory persistence tool (150pts) — https://github.com/example/memorylayer
[2026-03-22] [BUILD] [Frontier 1: Memory] RememberAll — cross-session recall system (300pts) — https://github.com/example/rememberall
[2026-03-23] [BUILD] [NEW] QuantumLint — revolutionary linting (50pts) — https://github.com/example/qlint
[2026-03-24] [BUILD] [Frontier 3: Context] ContextSaver — context window optimization (100pts) — https://github.com/example/ctxsave
"""

MASTER_TASKS_SAMPLE = """# Master-Level Tasks — CCA Aspirational Goals

---

## MT-0: Kalshi Bot Self-Learning Integration (BIGGEST)

**Source:** CCA self-learning architecture
**Status:** COMPLETE

---

## MT-41: Synthetic MT Origination

**Source:** Matthew directive (S160)
**Status:** Phase 1 COMPLETE
"""


class TestFindClusters(unittest.TestCase):
    """Phase 2: Cluster detection groups similar findings."""

    def test_clusters_by_frontier(self):
        findings = parse_findings_log(CLUSTERED_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        clusters = find_clusters(builds)
        # Memory findings should cluster together
        self.assertIsInstance(clusters, dict)
        # Should have at least one cluster with >1 finding
        multi_clusters = [k for k, v in clusters.items() if len(v) > 1]
        self.assertGreater(len(multi_clusters), 0)

    def test_singleton_clusters(self):
        findings = parse_findings_log(CLUSTERED_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        clusters = find_clusters(builds)
        # QuantumLint should be in its own cluster
        all_findings = []
        for v in clusters.values():
            all_findings.extend(v)
        quantum = [f for f in all_findings if "QuantumLint" in f.title]
        self.assertEqual(len(quantum), 1)

    def test_empty_input(self):
        clusters = find_clusters([])
        self.assertEqual(clusters, {})

    def test_cluster_keys_are_strings(self):
        findings = parse_findings_log(CLUSTERED_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        clusters = find_clusters(builds)
        for key in clusters.keys():
            self.assertIsInstance(key, str)


class TestScoreWithClusters(unittest.TestCase):
    """Phase 2: Cluster-boosted scoring."""

    def test_cluster_boosts_score(self):
        f1 = Finding("2026-03-22", "BUILD", "Frontier 1: Memory", "MemTool A", "url1", 100)
        f_solo = Finding("2026-03-22", "BUILD", "Frontier 1: Memory", "SoloTool", "url3", 100)

        # Same frontier, same points — cluster of 2 should beat solo
        score_clustered = score_with_clusters(f1, cluster_size=2)
        score_solo = score_with_clusters(f_solo, cluster_size=1)
        self.assertGreater(score_clustered, score_solo)

    def test_larger_cluster_higher_boost(self):
        f = Finding("2026-03-22", "BUILD", "NEW", "Tool", "url", 100)
        score_2 = score_with_clusters(f, cluster_size=2)
        score_5 = score_with_clusters(f, cluster_size=5)
        self.assertGreater(score_5, score_2)

    def test_cluster_size_1_no_boost(self):
        f = Finding("2026-03-22", "BUILD", "NEW", "Tool", "url", 100)
        score_1 = score_with_clusters(f, cluster_size=1)
        # Should match base score (within rounding)
        from mt_originator import score_proposal
        base = score_proposal(f)
        self.assertAlmostEqual(score_1, base, places=0)

    def test_score_capped_at_100(self):
        f = Finding("2026-03-24", "BUILD", "NEW", "SuperTool", "url", 10000)
        score = score_with_clusters(f, cluster_size=20)
        self.assertLessEqual(score, 100)


class TestGenerateRichProposals(unittest.TestCase):
    """Phase 2: Rich proposals with cluster info and technical sketch."""

    def test_generates_proposals(self):
        findings = parse_findings_log(CLUSTERED_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        proposals = generate_rich_proposals(builds)
        self.assertIsInstance(proposals, list)
        self.assertGreater(len(proposals), 0)

    def test_proposals_have_cluster_size(self):
        findings = parse_findings_log(CLUSTERED_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        proposals = generate_rich_proposals(builds)
        for p in proposals:
            self.assertIsInstance(p, MTProposal)
            self.assertGreater(p.cluster_size, 0)

    def test_proposals_sorted_by_score(self):
        findings = parse_findings_log(CLUSTERED_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        proposals = generate_rich_proposals(builds)
        scores = [p.score for p in proposals]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_clustered_proposals_merged(self):
        """Findings in same cluster should produce ONE proposal, not N."""
        findings = parse_findings_log(CLUSTERED_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        proposals = generate_rich_proposals(builds)
        # 5 builds: 3 memory (1 cluster), 1 quantum, 1 context = 3 proposals
        self.assertLessEqual(len(proposals), 3)

    def test_proposal_has_source_urls(self):
        """Clustered proposal should list all source URLs."""
        findings = parse_findings_log(CLUSTERED_FINDINGS)
        builds = [f for f in findings if f.verdict == "BUILD"]
        proposals = generate_rich_proposals(builds)
        # Find the memory cluster proposal
        mem_proposals = [p for p in proposals if "memory" in p.frontier.lower()]
        if mem_proposals:
            p = mem_proposals[0]
            self.assertIn("|", p.source_url)  # Multiple URLs joined by |


class TestFormatMTEntry(unittest.TestCase):
    """Phase 3: Format proposal as MASTER_TASKS.md entry."""

    def test_basic_format(self):
        p = MTProposal(
            name="QuantumLint",
            frontier="NEW",
            source_url="https://github.com/example/qlint",
            source_date="2026-03-23",
            score=65.0,
            description="Revolutionary linting tool",
            points=50,
            cluster_size=1,
        )
        entry = format_mt_entry(p, mt_id=43)
        self.assertIn("## MT-43: QuantumLint", entry)
        self.assertIn("**Status:** PROPOSED", entry)
        self.assertIn("**Source:**", entry)
        self.assertIn("https://github.com/example/qlint", entry)

    def test_format_includes_score(self):
        p = MTProposal(
            name="TestTool", frontier="Frontier 1", source_url="url",
            source_date="2026-03-24", score=85.5, description="test",
            points=200, cluster_size=3,
        )
        entry = format_mt_entry(p, mt_id=44)
        self.assertIn("85.5", entry)

    def test_format_includes_cluster_info(self):
        p = MTProposal(
            name="MemTools", frontier="Frontier 1: Memory",
            source_url="url1|url2|url3", source_date="2026-03-24",
            score=90.0, description="Memory persistence cluster",
            points=650, cluster_size=3,
        )
        entry = format_mt_entry(p, mt_id=45)
        self.assertIn("3 related findings", entry)

    def test_format_ends_with_separator(self):
        p = MTProposal(
            name="Tool", frontier="NEW", source_url="url",
            source_date="2026-03-24", score=50.0, description="desc",
        )
        entry = format_mt_entry(p, mt_id=46)
        self.assertTrue(entry.strip().endswith("---"))


class TestFindNextMTId(unittest.TestCase):
    """Phase 3: Determine next available MT ID."""

    def test_finds_next_id(self):
        next_id = find_next_mt_id(MASTER_TASKS_SAMPLE)
        self.assertEqual(next_id, 42)

    def test_empty_file(self):
        next_id = find_next_mt_id("")
        self.assertEqual(next_id, 0)

    def test_single_mt(self):
        text = "## MT-5: Something\n"
        next_id = find_next_mt_id(text)
        self.assertEqual(next_id, 6)


class TestAppendToMasterTasks(unittest.TestCase):
    """Phase 3: Append proposal to MASTER_TASKS.md."""

    def test_appends_entry(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(MASTER_TASKS_SAMPLE)
            f.flush()
            path = f.name

        try:
            p = MTProposal(
                name="NewTool", frontier="NEW", source_url="https://example.com",
                source_date="2026-03-24", score=75.0, description="A new tool",
            )
            mt_id = append_to_master_tasks(p, path)
            self.assertEqual(mt_id, 42)

            with open(path) as f:
                content = f.read()
            self.assertIn("## MT-42: NewTool", content)
            self.assertIn("PROPOSED", content)
        finally:
            os.unlink(path)

    def test_dedup_prevents_duplicate(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(MASTER_TASKS_SAMPLE + "\n## MT-42: NewTool\n\n**Status:** PROPOSED\n")
            f.flush()
            path = f.name

        try:
            p = MTProposal(
                name="NewTool", frontier="NEW", source_url="url",
                source_date="2026-03-24", score=75.0, description="A new tool",
            )
            mt_id = append_to_master_tasks(p, path)
            # Should return None or -1 to indicate duplicate
            self.assertIsNone(mt_id)
        finally:
            os.unlink(path)

    def test_sequential_ids(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(MASTER_TASKS_SAMPLE)
            f.flush()
            path = f.name

        try:
            p1 = MTProposal(name="Tool1", frontier="NEW", source_url="u1",
                            source_date="2026-03-24", score=80.0, description="d1")
            p2 = MTProposal(name="Tool2", frontier="NEW", source_url="u2",
                            source_date="2026-03-24", score=70.0, description="d2")
            id1 = append_to_master_tasks(p1, path)
            id2 = append_to_master_tasks(p2, path)
            self.assertEqual(id1, 42)
            self.assertEqual(id2, 43)
        finally:
            os.unlink(path)


class TestLoadProposals(unittest.TestCase):
    """Load proposals from JSONL file."""

    def test_load_proposals(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            p = MTProposal(name="Test", frontier="NEW", source_url="url",
                           source_date="2026-03-24", score=75.0, description="desc",
                           points=100, cluster_size=2)
            f.write(json.dumps(p.to_dict()) + "\n")
            f.flush()
            path = f.name

        try:
            proposals = load_proposals(path)
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0].name, "Test")
            self.assertEqual(proposals[0].cluster_size, 2)
        finally:
            os.unlink(path)

    def test_load_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.flush()
            path = f.name

        try:
            proposals = load_proposals(path)
            self.assertEqual(proposals, [])
        finally:
            os.unlink(path)

    def test_load_missing_file(self):
        proposals = load_proposals("/nonexistent/path.jsonl")
        self.assertEqual(proposals, [])


class TestGetTopProposalsForBriefing(unittest.TestCase):
    """Phase 3: Surface top proposals for /cca-init briefing."""

    def test_returns_top_n(self):
        proposals = [
            MTProposal(name="A", frontier="F1", source_url="u", source_date="d",
                       score=90.0, description="a"),
            MTProposal(name="B", frontier="F2", source_url="u", source_date="d",
                       score=80.0, description="b"),
            MTProposal(name="C", frontier="F3", source_url="u", source_date="d",
                       score=70.0, description="c"),
        ]
        top = get_top_proposals_for_briefing(proposals, n=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].name, "A")
        self.assertEqual(top[1].name, "B")

    def test_empty_proposals(self):
        top = get_top_proposals_for_briefing([], n=3)
        self.assertEqual(top, [])

    def test_fewer_than_n(self):
        proposals = [
            MTProposal(name="A", frontier="F1", source_url="u", source_date="d",
                       score=90.0, description="a"),
        ]
        top = get_top_proposals_for_briefing(proposals, n=5)
        self.assertEqual(len(top), 1)

    def test_filters_low_score(self):
        """Proposals below threshold should not surface."""
        proposals = [
            MTProposal(name="Good", frontier="F1", source_url="u", source_date="d",
                       score=60.0, description="good"),
            MTProposal(name="Bad", frontier="F2", source_url="u", source_date="d",
                       score=15.0, description="bad"),
        ]
        top = get_top_proposals_for_briefing(proposals, n=5, min_score=30.0)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0].name, "Good")

    def test_format_briefing_line(self):
        """Each proposal should format as a concise briefing line."""
        proposals = [
            MTProposal(name="QuantumLint", frontier="NEW", source_url="url",
                       source_date="2026-03-24", score=75.0, description="Quantum linting",
                       cluster_size=1),
        ]
        top = get_top_proposals_for_briefing(proposals, n=3)
        line = top[0].briefing_line()
        self.assertIn("QuantumLint", line)
        self.assertIn("75.0", line)


if __name__ == "__main__":
    unittest.main()
