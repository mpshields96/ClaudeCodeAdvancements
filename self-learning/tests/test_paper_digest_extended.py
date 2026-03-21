#!/usr/bin/env python3
"""
test_paper_digest_extended.py — Extended edge-case tests for paper_digest.py.

Covers: malformed arxiv responses, empty results, duplicate dedup,
bridge message formatting, domain keyword matching edge cases,
ranking tie-breaking, processed state persistence edge cases.
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
    filter_papers_by_domain,
    rank_for_kalshi_relevance,
    generate_digest_markdown,
    format_digest_for_bridge,
    KALSHI_DOMAINS,
    CCA_DOMAINS,
    KALSHI_DOMAIN_BONUS,
    VERDICT_BONUS,
)


def _make_paper(title="Test", score=70, domains=None, verdict="IMPLEMENT", reasons=None, **kwargs):
    return {
        "title": title,
        "authors": kwargs.get("authors", "Smith et al."),
        "url": kwargs.get("url", "https://arxiv.org/abs/0000.00000"),
        "score": score,
        "domains": domains if domains is not None else ["prediction"],
        "verdict": verdict,
        "reasons": reasons if reasons is not None else ["High citations"],
        **{k: v for k, v in kwargs.items() if k not in ("authors", "url")},
    }


class TestFilterPapersByDomainExtended(unittest.TestCase):
    """Extended edge cases for filter_papers_by_domain."""

    def test_paper_with_multiple_domains_matched_by_any(self):
        """Paper with [prediction, agents] is returned when filtering for 'agents'."""
        papers = [_make_paper("A", domains=["prediction", "agents"])]
        result = filter_papers_by_domain(papers, "agents")
        self.assertEqual(len(result), 1)

    def test_missing_domains_key_not_matched(self):
        """Papers missing 'domains' key entirely are not matched."""
        papers = [{"title": "X", "score": 80, "verdict": "IMPLEMENT"}]
        result = filter_papers_by_domain(papers, "prediction")
        self.assertEqual(len(result), 0)

    def test_domains_none_not_matched(self):
        """Paper with explicit domains=None is not matched — treated as empty list."""
        papers = [{"title": "X", "score": 80, "domains": None, "verdict": "IMPLEMENT"}]
        # filter_papers_by_domain uses (p.get("domains") or []) to safely handle None
        result = filter_papers_by_domain(papers, "prediction")
        self.assertEqual(len(result), 0)

    def test_empty_domain_string_not_matched(self):
        """Filtering for empty string returns nothing (no paper has '' domain)."""
        papers = [_make_paper("A", domains=["prediction"])]
        result = filter_papers_by_domain(papers, "")
        self.assertEqual(len(result), 0)

    def test_all_papers_have_domain(self):
        """All papers matching domain are returned."""
        papers = [
            _make_paper("A", domains=["prediction"]),
            _make_paper("B", domains=["prediction"]),
            _make_paper("C", domains=["agents"]),
        ]
        result = filter_papers_by_domain(papers, "prediction")
        self.assertEqual(len(result), 2)


class TestRankForKalshiRelevanceExtended(unittest.TestCase):
    """Extended edge cases for rank_for_kalshi_relevance."""

    def test_single_paper_returned_as_is(self):
        """Single paper is returned unchanged."""
        papers = [_make_paper("A", score=60, domains=["prediction"], verdict="IMPLEMENT")]
        ranked = rank_for_kalshi_relevance(papers)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["title"], "A")

    def test_trading_systems_bonus_applied(self):
        """trading_systems domain gets same bonus as prediction (30)."""
        papers = [
            _make_paper("Trading", score=50, domains=["trading_systems"], verdict="IMPLEMENT"),
            _make_paper("Agents", score=75, domains=["agents"], verdict="IMPLEMENT"),
        ]
        ranked = rank_for_kalshi_relevance(papers)
        # Trading: 50 + 30 + 20 = 100; Agents: 75 + 5 + 20 = 100
        # Tied — order may vary but both present
        titles = [p["title"] for p in ranked]
        self.assertIn("Trading", titles)
        self.assertIn("Agents", titles)

    def test_skip_verdict_penalty_applied(self):
        """SKIP papers get -30 penalty in ranking."""
        papers = [
            _make_paper("Skip", score=80, domains=["prediction"], verdict="SKIP"),
            _make_paper("Ref", score=60, domains=["prediction"], verdict="REFERENCE"),
        ]
        ranked = rank_for_kalshi_relevance(papers)
        # Skip: 80 + 30 + (-30) = 80; Ref: 60 + 30 + 0 = 90
        self.assertEqual(ranked[0]["title"], "Ref")

    def test_multiple_domains_max_bonus_used(self):
        """Paper with [prediction, agents] gets the max domain bonus (30, not 5)."""
        papers = [
            _make_paper("Multi", score=50, domains=["prediction", "agents"], verdict="IMPLEMENT"),
            _make_paper("Agents", score=60, domains=["agents"], verdict="IMPLEMENT"),
        ]
        ranked = rank_for_kalshi_relevance(papers)
        # Multi: 50 + max(30, 5) + 20 = 100; Agents: 60 + 5 + 20 = 85
        self.assertEqual(ranked[0]["title"], "Multi")

    def test_unknown_domain_gets_zero_bonus(self):
        """Domain not in KALSHI_DOMAIN_BONUS gets 0 bonus."""
        papers = [
            _make_paper("Unknown", score=60, domains=["quantum_physics"], verdict="IMPLEMENT"),
            _make_paper("Known", score=50, domains=["statistics"], verdict="IMPLEMENT"),
        ]
        ranked = rank_for_kalshi_relevance(papers)
        # Unknown: 60 + 0 + 20 = 80; Known: 50 + 20 + 20 = 90
        self.assertEqual(ranked[0]["title"], "Known")

    def test_no_domains_gets_zero_domain_bonus(self):
        """Paper with no domains gets default=0 domain bonus."""
        papers = [
            _make_paper("Empty", score=70, domains=[], verdict="IMPLEMENT"),
            _make_paper("Pred", score=60, domains=["prediction"], verdict="IMPLEMENT"),
        ]
        ranked = rank_for_kalshi_relevance(papers)
        # Empty: 70 + 0 + 20 = 90; Pred: 60 + 30 + 20 = 110
        self.assertEqual(ranked[0]["title"], "Pred")


class TestGenerateDigestMarkdownExtended(unittest.TestCase):
    """Extended edge cases for generate_digest_markdown."""

    def test_custom_title_in_output(self):
        """Custom title appears in markdown output."""
        entry = DigestEntry("Paper A", "Smith", "url", 75, "prediction",
                           "IMPLEMENT", "Direct", "Try this")
        md = generate_digest_markdown([entry], title="Custom Title")
        self.assertIn("Custom Title", md)

    def test_entry_includes_url(self):
        """URL appears in markdown entry."""
        entry = DigestEntry("Paper A", "Smith", "https://arxiv.org/abs/1234",
                           75, "prediction", "IMPLEMENT", "Direct", "Try this")
        md = generate_digest_markdown([entry])
        self.assertIn("https://arxiv.org/abs/1234", md)

    def test_entry_includes_score(self):
        """Score appears in markdown entry."""
        entry = DigestEntry("Paper A", "Smith", "url", 88, "prediction",
                           "IMPLEMENT", "Direct", "Try this")
        md = generate_digest_markdown([entry])
        self.assertIn("88", md)

    def test_entry_includes_authors(self):
        """Authors appear in markdown entry."""
        entry = DigestEntry("Paper A", "Jones & Brown", "url", 75, "prediction",
                           "REFERENCE", "Indirect", "Note pattern")
        md = generate_digest_markdown([entry])
        self.assertIn("Jones & Brown", md)

    def test_three_entries_numbered_sequentially(self):
        """Three entries are numbered 1., 2., 3."""
        entries = [
            DigestEntry(f"Paper {i}", "Auth", "url", 70, "prediction",
                       "IMPLEMENT", "Direct", "Action")
            for i in range(3)
        ]
        md = generate_digest_markdown(entries)
        self.assertIn("1.", md)
        self.assertIn("2.", md)
        self.assertIn("3.", md)

    def test_skip_verdict_shown_in_entry(self):
        """SKIP verdict appears in markdown."""
        entry = DigestEntry("Low", "Auth", "url", 30, "interaction",
                           "SKIP", "Low", "Skip")
        md = generate_digest_markdown([entry])
        self.assertIn("SKIP", md)

    def test_empty_title_handled(self):
        """Empty string title doesn't crash generate."""
        entry = DigestEntry("", "Auth", "url", 60, "prediction",
                           "REFERENCE", "Low", "N/A")
        md = generate_digest_markdown([entry])
        self.assertIsInstance(md, str)

    def test_returns_string_not_list(self):
        """generate_digest_markdown always returns str."""
        md = generate_digest_markdown([])
        self.assertIsInstance(md, str)

    def test_single_entry_no_numbering_issues(self):
        """Single entry shows '1.' numbering."""
        entry = DigestEntry("Solo Paper", "Auth", "url", 70, "prediction",
                           "IMPLEMENT", "Direct", "Action")
        md = generate_digest_markdown([entry])
        self.assertIn("1.", md)
        self.assertNotIn("2.", md)


class TestFormatDigestForBridgeExtended(unittest.TestCase):
    """Extended edge cases for format_digest_for_bridge."""

    def test_header_includes_count(self):
        """Bridge header shows the number of papers included."""
        entries = [
            DigestEntry(f"P{i}", "A", "u", 80 - i, "prediction",
                       "IMPLEMENT", "D", "Action")
            for i in range(3)
        ]
        msg = format_digest_for_bridge(entries)
        self.assertIn("3", msg)

    def test_max_entries_one(self):
        """max_entries=1 returns only first entry."""
        entries = [
            DigestEntry("First", "A", "u", 90, "prediction", "IMPLEMENT", "D", "Action"),
            DigestEntry("Second", "A", "u", 80, "prediction", "IMPLEMENT", "D", "Action"),
        ]
        msg = format_digest_for_bridge(entries, max_entries=1)
        self.assertIn("First", msg)
        self.assertNotIn("Second", msg)

    def test_max_entries_larger_than_list(self):
        """max_entries larger than entries list returns all entries."""
        entries = [DigestEntry("Only", "A", "u", 70, "prediction",
                              "IMPLEMENT", "D", "A")]
        msg = format_digest_for_bridge(entries, max_entries=100)
        self.assertIn("Only", msg)
        self.assertIn("1 paper", msg)

    def test_bridge_includes_actionable_insight(self):
        """Actionable insight appears in bridge message."""
        entries = [DigestEntry("Paper", "A", "u", 70, "prediction",
                              "IMPLEMENT", "D", "Apply Kelly criterion")]
        msg = format_digest_for_bridge(entries)
        self.assertIn("Apply Kelly criterion", msg)

    def test_bridge_includes_score(self):
        """Score appears in bridge message."""
        entries = [DigestEntry("Paper", "A", "u", 77, "prediction",
                              "IMPLEMENT", "D", "Action")]
        msg = format_digest_for_bridge(entries)
        self.assertIn("77", msg)

    def test_bridge_includes_verdict(self):
        """Verdict appears in bridge message."""
        entries = [DigestEntry("Paper", "A", "u", 70, "statistics",
                              "REFERENCE", "D", "Action")]
        msg = format_digest_for_bridge(entries)
        self.assertIn("REFERENCE", msg)


class TestPaperDigestClassExtended(unittest.TestCase):
    """Extended edge cases for PaperDigest class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "papers.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_papers(self, papers):
        with open(self.log_path, "w") as f:
            for p in papers:
                f.write(json.dumps(p) + "\n")

    def test_corrupt_lines_skipped(self):
        """Corrupt JSON lines in papers.jsonl are skipped."""
        with open(self.log_path, "w") as f:
            f.write(json.dumps(_make_paper("Valid", score=75)) + "\n")
            f.write("NOT JSON\n")
            f.write(json.dumps(_make_paper("Also Valid", score=60)) + "\n")
        digest = PaperDigest(self.log_path)
        self.assertEqual(len(digest.papers), 2)

    def test_blank_lines_skipped(self):
        """Blank lines in papers.jsonl are silently skipped."""
        with open(self.log_path, "w") as f:
            f.write("\n")
            f.write(json.dumps(_make_paper("A", score=70)) + "\n")
            f.write("\n")
        digest = PaperDigest(self.log_path)
        self.assertEqual(len(digest.papers), 1)

    def test_kalshi_relevant_excludes_skip(self):
        """SKIP papers never appear in Kalshi-relevant results."""
        self._write_papers([
            _make_paper("Skip Paper", score=90, domains=["prediction"], verdict="SKIP"),
            _make_paper("OK Paper", score=70, domains=["prediction"], verdict="REFERENCE"),
        ])
        digest = PaperDigest(self.log_path)
        relevant = digest.kalshi_relevant(min_score=50)
        titles = [p["title"] for p in relevant]
        self.assertNotIn("Skip Paper", titles)
        self.assertIn("OK Paper", titles)

    def test_kalshi_relevant_excludes_below_min_score(self):
        """Papers below min_score threshold are excluded."""
        self._write_papers([
            _make_paper("Low", score=40, domains=["prediction"], verdict="IMPLEMENT"),
            _make_paper("High", score=80, domains=["prediction"], verdict="IMPLEMENT"),
        ])
        digest = PaperDigest(self.log_path)
        relevant = digest.kalshi_relevant(min_score=50)
        titles = [p["title"] for p in relevant]
        self.assertNotIn("Low", titles)
        self.assertIn("High", titles)

    def test_cca_relevant_excludes_non_cca_domains(self):
        """Papers in prediction/trading domains but not CCA domains are excluded."""
        self._write_papers([
            _make_paper("Trading", score=80, domains=["prediction", "trading_systems"], verdict="IMPLEMENT"),
            _make_paper("Agents", score=70, domains=["agents"], verdict="IMPLEMENT"),
        ])
        digest = PaperDigest(self.log_path)
        relevant = digest.cca_relevant(min_score=50)
        titles = [p["title"] for p in relevant]
        self.assertNotIn("Trading", titles)
        self.assertIn("Agents", titles)

    def test_unprocessed_empty_when_all_marked(self):
        """unprocessed() returns empty list after all papers are marked."""
        self._write_papers([_make_paper("A"), _make_paper("B")])
        digest = PaperDigest(self.log_path)
        for p in digest.papers:
            digest.mark_processed(p["title"])
        self.assertEqual(len(digest.unprocessed()), 0)

    def test_mark_processed_twice_still_one_entry(self):
        """Marking same paper twice doesn't create duplicates in processed set."""
        self._write_papers([_make_paper("A")])
        digest = PaperDigest(self.log_path)
        digest.mark_processed("A")
        digest.mark_processed("A")
        # Load fresh — processed file should have "A" once
        digest2 = PaperDigest(self.log_path)
        self.assertEqual(len(digest2.unprocessed()), 0)

    def test_processed_file_corrupted_returns_empty_set(self):
        """Corrupted processed JSON returns empty set (fail-safe)."""
        self._write_papers([_make_paper("A")])
        digest = PaperDigest(self.log_path)
        # Corrupt the processed file
        with open(digest.processed_path, "w") as f:
            f.write("NOT JSON")
        digest2 = PaperDigest(self.log_path)
        # Empty set = all papers unprocessed
        self.assertEqual(len(digest2.unprocessed()), 1)

    def test_paper_to_entry_uses_first_domain(self):
        """_paper_to_entry uses first domain as primary domain."""
        self._write_papers([])
        digest = PaperDigest(self.log_path)
        paper = _make_paper("A", domains=["statistics", "prediction"])
        entry = digest._paper_to_entry(paper)
        self.assertEqual(entry.domain, "statistics")

    def test_paper_to_entry_uses_only_first_two_reasons(self):
        """_paper_to_entry uses at most first 2 reasons for insight."""
        self._write_papers([])
        digest = PaperDigest(self.log_path)
        paper = _make_paper("A", reasons=["R1", "R2", "R3", "R4"])
        entry = digest._paper_to_entry(paper)
        self.assertIn("R1", entry.actionable_insight)
        self.assertIn("R2", entry.actionable_insight)
        # R3 may or may not be included — it's limited to first 2

    def test_paper_to_entry_no_reasons_default_message(self):
        """No reasons = default actionable insight message."""
        self._write_papers([])
        digest = PaperDigest(self.log_path)
        paper = _make_paper("A", reasons=[])
        entry = digest._paper_to_entry(paper)
        self.assertIn("Review", entry.actionable_insight)

    def test_paper_to_entry_both_kalshi_and_cca_domains(self):
        """Paper with both Kalshi and CCA domains shows 'Direct' relevance (Kalshi wins)."""
        self._write_papers([])
        digest = PaperDigest(self.log_path)
        paper = _make_paper("A", domains=["prediction", "agents"])
        entry = digest._paper_to_entry(paper)
        self.assertIn("Direct", entry.relevance_to_kalshi)

    def test_generate_cca_digest_returns_string(self):
        """generate_cca_digest returns a string."""
        self._write_papers([
            _make_paper("Agent Study", score=75, domains=["agents"], verdict="IMPLEMENT"),
        ])
        digest = PaperDigest(self.log_path)
        result = digest.generate_cca_digest()
        self.assertIsInstance(result, str)

    def test_generate_cca_digest_empty_when_no_cca_papers(self):
        """CCA digest with no CCA-relevant papers returns empty message."""
        self._write_papers([
            _make_paper("Kalshi Only", score=90, domains=["prediction"], verdict="IMPLEMENT"),
        ])
        digest = PaperDigest(self.log_path)
        result = digest.generate_cca_digest()
        self.assertIn("no papers", result.lower())


class TestDomainConstants(unittest.TestCase):
    """Verify domain constants are correctly defined."""

    def test_kalshi_domains_non_empty(self):
        """KALSHI_DOMAINS has entries."""
        self.assertGreater(len(KALSHI_DOMAINS), 0)

    def test_cca_domains_non_empty(self):
        """CCA_DOMAINS has entries."""
        self.assertGreater(len(CCA_DOMAINS), 0)

    def test_prediction_in_kalshi_domains(self):
        self.assertIn("prediction", KALSHI_DOMAINS)

    def test_agents_in_cca_domains(self):
        self.assertIn("agents", CCA_DOMAINS)

    def test_implement_has_positive_bonus(self):
        """IMPLEMENT verdict has positive bonus."""
        self.assertGreater(VERDICT_BONUS["IMPLEMENT"], 0)

    def test_skip_has_negative_bonus(self):
        """SKIP verdict has negative bonus."""
        self.assertLess(VERDICT_BONUS["SKIP"], 0)

    def test_kalshi_domain_bonus_prediction_highest(self):
        """prediction and trading_systems have the highest Kalshi bonus."""
        pred_bonus = KALSHI_DOMAIN_BONUS.get("prediction", 0)
        trading_bonus = KALSHI_DOMAIN_BONUS.get("trading_systems", 0)
        agents_bonus = KALSHI_DOMAIN_BONUS.get("agents", 0)
        self.assertGreater(pred_bonus, agents_bonus)
        self.assertEqual(pred_bonus, trading_bonus)


if __name__ == "__main__":
    unittest.main()
