#!/usr/bin/env python3
"""Tests for paper_digest.py — MT-12 Phase 3: Paper digest generator.

Generates actionable research summaries from paper_scanner's log
for cross-chat delivery to Kalshi research chat.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paper_digest import (
    PaperDigest,
    DigestEntry,
    format_digest_for_bridge,
    filter_papers_by_domain,
    rank_for_kalshi_relevance,
    generate_digest_markdown,
)


class TestDigestEntry(unittest.TestCase):
    """Test DigestEntry dataclass."""

    def test_basic_creation(self):
        entry = DigestEntry(
            title="Test Paper",
            authors="Smith et al.",
            url="https://example.com",
            score=75,
            domain="prediction",
            verdict="IMPLEMENT",
            relevance_to_kalshi="Direct edge detection method",
            actionable_insight="Try Kelly criterion variant for position sizing",
        )
        self.assertEqual(entry.title, "Test Paper")
        self.assertEqual(entry.score, 75)
        self.assertEqual(entry.domain, "prediction")

    def test_to_dict(self):
        entry = DigestEntry(
            title="Test", authors="A", url="http://x",
            score=50, domain="agents", verdict="REFERENCE",
            relevance_to_kalshi="Indirect", actionable_insight="Note pattern",
        )
        d = entry.to_dict()
        self.assertIn("title", d)
        self.assertIn("actionable_insight", d)
        self.assertEqual(d["score"], 50)

    def test_empty_fields(self):
        entry = DigestEntry(
            title="", authors="", url="",
            score=0, domain="", verdict="SKIP",
            relevance_to_kalshi="", actionable_insight="",
        )
        self.assertEqual(entry.title, "")
        self.assertEqual(entry.score, 0)


class TestFilterPapersByDomain(unittest.TestCase):
    """Test domain filtering."""

    def _sample_papers(self):
        return [
            {"title": "A", "domains": ["prediction", "statistics"], "verdict": "IMPLEMENT", "score": 80},
            {"title": "B", "domains": ["agents"], "verdict": "IMPLEMENT", "score": 70},
            {"title": "C", "domains": ["prediction"], "verdict": "REFERENCE", "score": 60},
            {"title": "D", "domains": ["interaction"], "verdict": "SKIP", "score": 30},
            {"title": "E", "domains": [], "verdict": "IMPLEMENT", "score": 65},
        ]

    def test_filter_prediction(self):
        result = filter_papers_by_domain(self._sample_papers(), "prediction")
        self.assertEqual(len(result), 2)
        titles = [p["title"] for p in result]
        self.assertIn("A", titles)
        self.assertIn("C", titles)

    def test_filter_agents(self):
        result = filter_papers_by_domain(self._sample_papers(), "agents")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "B")

    def test_filter_nonexistent_domain(self):
        result = filter_papers_by_domain(self._sample_papers(), "quantum")
        self.assertEqual(len(result), 0)

    def test_filter_empty_papers(self):
        result = filter_papers_by_domain([], "prediction")
        self.assertEqual(len(result), 0)

    def test_filter_no_domain_field(self):
        papers = [{"title": "X", "verdict": "IMPLEMENT", "score": 50}]
        result = filter_papers_by_domain(papers, "agents")
        self.assertEqual(len(result), 0)


class TestRankForKalshiRelevance(unittest.TestCase):
    """Test Kalshi-specific relevance ranking."""

    def test_prediction_papers_rank_higher(self):
        papers = [
            {"title": "Agent Paper", "domains": ["agents"], "score": 80, "verdict": "IMPLEMENT"},
            {"title": "Trading Paper", "domains": ["prediction", "trading_systems"], "score": 70, "verdict": "IMPLEMENT"},
        ]
        ranked = rank_for_kalshi_relevance(papers)
        # Trading/prediction papers should rank higher for Kalshi despite lower base score
        self.assertEqual(ranked[0]["title"], "Trading Paper")

    def test_implement_over_reference(self):
        papers = [
            {"title": "Ref", "domains": ["prediction"], "score": 80, "verdict": "REFERENCE"},
            {"title": "Impl", "domains": ["prediction"], "score": 70, "verdict": "IMPLEMENT"},
        ]
        ranked = rank_for_kalshi_relevance(papers)
        self.assertEqual(ranked[0]["title"], "Impl")

    def test_empty_list(self):
        self.assertEqual(rank_for_kalshi_relevance([]), [])

    def test_statistics_gets_bonus(self):
        papers = [
            {"title": "Interaction", "domains": ["interaction"], "score": 80, "verdict": "IMPLEMENT"},
            {"title": "Stats", "domains": ["statistics"], "score": 70, "verdict": "IMPLEMENT"},
        ]
        ranked = rank_for_kalshi_relevance(papers)
        # Statistics more relevant to Kalshi than interaction
        self.assertEqual(ranked[0]["title"], "Stats")

    def test_skip_verdict_deprioritized(self):
        # Same domain so domain bonus cancels out — verdict decides
        papers = [
            {"title": "Skip", "domains": ["prediction"], "score": 70, "verdict": "SKIP"},
            {"title": "Impl", "domains": ["prediction"], "score": 70, "verdict": "IMPLEMENT"},
        ]
        ranked = rank_for_kalshi_relevance(papers)
        self.assertEqual(ranked[0]["title"], "Impl")


class TestGenerateDigestMarkdown(unittest.TestCase):
    """Test markdown digest generation."""

    def test_basic_markdown(self):
        entries = [
            DigestEntry(
                title="Kelly Criterion Extensions",
                authors="Smith, Jones",
                url="https://arxiv.org/abs/2401.12345",
                score=85,
                domain="prediction",
                verdict="IMPLEMENT",
                relevance_to_kalshi="Position sizing optimization",
                actionable_insight="Fractional Kelly with Bayesian updating reduces drawdown 40%",
            ),
        ]
        md = generate_digest_markdown(entries)
        self.assertIn("Kelly Criterion Extensions", md)
        self.assertIn("IMPLEMENT", md)
        self.assertIn("Position sizing optimization", md)
        self.assertIn("Fractional Kelly", md)

    def test_empty_entries(self):
        md = generate_digest_markdown([])
        self.assertIn("no papers", md.lower())

    def test_multiple_entries(self):
        entries = [
            DigestEntry("A", "Auth1", "url1", 80, "prediction", "IMPLEMENT", "r1", "a1"),
            DigestEntry("B", "Auth2", "url2", 70, "statistics", "REFERENCE", "r2", "a2"),
        ]
        md = generate_digest_markdown(entries)
        self.assertIn("A", md)
        self.assertIn("B", md)
        # Should have sections or numbering
        self.assertIn("1.", md)
        self.assertIn("2.", md)

    def test_markdown_has_header(self):
        entries = [DigestEntry("X", "Y", "u", 60, "agents", "IMPLEMENT", "r", "a")]
        md = generate_digest_markdown(entries)
        self.assertIn("# ", md)  # Has at least one markdown header


class TestFormatDigestForBridge(unittest.TestCase):
    """Test cross-chat bridge formatting."""

    def test_bridge_format_concise(self):
        entries = [
            DigestEntry("Paper A", "Smith", "url", 80, "prediction", "IMPLEMENT",
                       "Edge detection", "Use for signal generation"),
        ]
        bridge_msg = format_digest_for_bridge(entries)
        # Bridge messages should be concise (under 500 chars per entry)
        self.assertLess(len(bridge_msg), 1000)
        self.assertIn("Paper A", bridge_msg)
        self.assertIn("IMPLEMENT", bridge_msg)

    def test_bridge_format_empty(self):
        bridge_msg = format_digest_for_bridge([])
        self.assertIn("no new", bridge_msg.lower())

    def test_bridge_format_max_entries(self):
        entries = [
            DigestEntry(f"Paper {i}", "Auth", "url", 80 - i, "prediction",
                       "IMPLEMENT", "rel", "act")
            for i in range(10)
        ]
        bridge_msg = format_digest_for_bridge(entries, max_entries=3)
        # Should only include top 3
        self.assertIn("Paper 0", bridge_msg)
        self.assertIn("Paper 2", bridge_msg)
        self.assertNotIn("Paper 5", bridge_msg)


class TestPaperDigest(unittest.TestCase):
    """Test the main PaperDigest class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "papers.jsonl")
        # Write sample papers
        papers = [
            {"title": "Bayesian Trading", "authors": "Smith", "url": "http://a",
             "score": 85, "domains": ["prediction", "statistics"], "verdict": "IMPLEMENT",
             "citations": 50, "year": "2025", "reasons": ["High citations"]},
            {"title": "Agent Context", "authors": "Jones", "url": "http://b",
             "score": 70, "domains": ["agents", "context_management"], "verdict": "IMPLEMENT",
             "citations": 20, "year": "2024", "reasons": ["Moderate citations"]},
            {"title": "UI Study", "authors": "Lee", "url": "http://c",
             "score": 40, "domains": ["interaction"], "verdict": "SKIP",
             "citations": 3, "year": "2023", "reasons": ["Low citations"]},
        ]
        with open(self.log_path, "w") as f:
            for p in papers:
                f.write(json.dumps(p) + "\n")

    def test_load_papers(self):
        digest = PaperDigest(self.log_path)
        self.assertEqual(len(digest.papers), 3)

    def test_kalshi_relevant(self):
        digest = PaperDigest(self.log_path)
        relevant = digest.kalshi_relevant(min_score=50)
        # Should include prediction/statistics papers, exclude SKIP
        titles = [p["title"] for p in relevant]
        self.assertIn("Bayesian Trading", titles)
        self.assertNotIn("UI Study", titles)

    def test_kalshi_relevant_min_score(self):
        digest = PaperDigest(self.log_path)
        relevant = digest.kalshi_relevant(min_score=80)
        self.assertEqual(len(relevant), 1)
        self.assertEqual(relevant[0]["title"], "Bayesian Trading")

    def test_cca_relevant(self):
        digest = PaperDigest(self.log_path)
        relevant = digest.cca_relevant(min_score=50)
        titles = [p["title"] for p in relevant]
        self.assertIn("Agent Context", titles)

    def test_unprocessed(self):
        digest = PaperDigest(self.log_path)
        # Initially all papers are unprocessed
        unprocessed = digest.unprocessed()
        self.assertEqual(len(unprocessed), 3)

    def test_mark_processed(self):
        digest = PaperDigest(self.log_path)
        digest.mark_processed("Bayesian Trading")
        unprocessed = digest.unprocessed()
        titles = [p["title"] for p in unprocessed]
        self.assertNotIn("Bayesian Trading", titles)

    def test_mark_processed_persists(self):
        digest = PaperDigest(self.log_path)
        digest.mark_processed("Agent Context")
        # Reload
        digest2 = PaperDigest(self.log_path)
        unprocessed = digest2.unprocessed()
        titles = [p["title"] for p in unprocessed]
        self.assertNotIn("Agent Context", titles)

    def test_missing_log_file(self):
        digest = PaperDigest("/tmp/nonexistent_papers.jsonl")
        self.assertEqual(len(digest.papers), 0)

    def test_generate_kalshi_digest(self):
        digest = PaperDigest(self.log_path)
        md = digest.generate_kalshi_digest()
        self.assertIn("Bayesian Trading", md)

    def test_generate_bridge_message(self):
        digest = PaperDigest(self.log_path)
        msg = digest.generate_bridge_message()
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 0)


if __name__ == "__main__":
    unittest.main()
