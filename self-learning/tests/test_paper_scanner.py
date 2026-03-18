#!/usr/bin/env python3
"""Tests for paper_scanner.py — MT-12 academic paper discovery and evaluation."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import paper_scanner


class TestEvaluatePaper(unittest.TestCase):
    """Test the paper evaluation scoring system."""

    def test_high_citation_paper(self):
        paper = {"citationCount": 150, "venue": "NeurIPS", "publicationDate": "2025-01-15",
                 "abstract": "We present an agent framework for tool use.", "openAccessPdf": {"url": "http://pdf"}}
        result = paper_scanner.evaluate_paper(paper)
        self.assertGreaterEqual(result["score"], 60)
        self.assertEqual(result["venue_quality"], "top")

    def test_low_citation_paper(self):
        paper = {"citationCount": 2, "venue": "", "publicationDate": "2020-01-01",
                 "abstract": "A study.", "openAccessPdf": None}
        result = paper_scanner.evaluate_paper(paper)
        self.assertLess(result["score"], 30)

    def test_code_availability_detected(self):
        paper = {"citationCount": 10, "venue": "", "publicationDate": "2025-01-01",
                 "abstract": "Our code is available at github.com/example/repo"}
        result = paper_scanner.evaluate_paper(paper)
        self.assertTrue(result["has_code"])

    def test_no_code_detected(self):
        paper = {"citationCount": 10, "venue": "", "publicationDate": "2025-01-01",
                 "abstract": "We present theoretical results."}
        result = paper_scanner.evaluate_paper(paper)
        self.assertFalse(result["has_code"])

    def test_domain_match_agents(self):
        paper = {"citationCount": 20, "venue": "ICML", "publicationDate": "2025-06-01",
                 "abstract": "We propose a multi-agent system for code generation with tool use capabilities."}
        result = paper_scanner.evaluate_paper(paper)
        self.assertIn("agents", result["domain_hits"])

    def test_domain_match_prediction(self):
        paper = {"citationCount": 30, "venue": "KDD", "publicationDate": "2025-01-01",
                 "abstract": "Calibration techniques for prediction market forecasting models."}
        result = paper_scanner.evaluate_paper(paper)
        self.assertIn("prediction", result["domain_hits"])

    def test_domain_match_statistics(self):
        paper = {"citationCount": 15, "venue": "JMLR", "publicationDate": "2025-01-01",
                 "abstract": "Bayesian inference for anomaly detection in time series data."}
        result = paper_scanner.evaluate_paper(paper)
        self.assertIn("statistics", result["domain_hits"])

    def test_domain_match_interaction(self):
        paper = {"citationCount": 25, "venue": "ACL", "publicationDate": "2025-01-01",
                 "abstract": "Systematic evaluation of prompt engineering techniques for LLM evaluation."}
        result = paper_scanner.evaluate_paper(paper)
        self.assertIn("interaction", result["domain_hits"])

    def test_no_domain_match(self):
        paper = {"citationCount": 50, "venue": "Nature", "publicationDate": "2025-01-01",
                 "abstract": "Crystal structure of a novel protein binding domain."}
        result = paper_scanner.evaluate_paper(paper)
        self.assertEqual(result["domain_hits"], {})

    def test_top_venue_scored(self):
        for venue in ["NeurIPS", "ICML", "ICLR", "AAAI", "ACL", "KDD"]:
            paper = {"citationCount": 0, "venue": venue, "publicationDate": "", "abstract": ""}
            result = paper_scanner.evaluate_paper(paper)
            self.assertEqual(result["venue_quality"], "top", f"Failed for venue: {venue}")

    def test_unknown_venue(self):
        paper = {"citationCount": 0, "venue": "", "publicationDate": "", "abstract": ""}
        result = paper_scanner.evaluate_paper(paper)
        self.assertEqual(result["venue_quality"], "unknown")

    def test_recency_current_year(self):
        from datetime import datetime
        year = datetime.now().year
        paper = {"citationCount": 0, "venue": "", "publicationDate": f"{year}-06-01", "abstract": ""}
        result = paper_scanner.evaluate_paper(paper)
        self.assertTrue(any("Very recent" in r for r in result["reasons"]))

    def test_recency_old_paper(self):
        paper = {"citationCount": 0, "venue": "", "publicationDate": "2018-01-01", "abstract": ""}
        result = paper_scanner.evaluate_paper(paper)
        self.assertFalse(any("recent" in r.lower() for r in result["reasons"]))

    def test_open_access_pdf_scored(self):
        paper = {"citationCount": 0, "venue": "", "publicationDate": "",
                 "abstract": "", "openAccessPdf": {"url": "http://example.com/paper.pdf"}}
        result = paper_scanner.evaluate_paper(paper)
        self.assertTrue(any("Open access" in r for r in result["reasons"]))

    def test_score_capped_at_100(self):
        paper = {"citationCount": 500, "venue": "NeurIPS", "publicationDate": "2026-01-01",
                 "abstract": "An agent for tool use with multi-agent coordination and code generation. "
                             "Open source implementation available at github.com/example.",
                 "openAccessPdf": {"url": "http://pdf"}}
        result = paper_scanner.evaluate_paper(paper)
        self.assertLessEqual(result["score"], 100)

    def test_none_values_handled(self):
        """Paper with None values should not crash."""
        paper = {"citationCount": None, "venue": None, "publicationDate": None,
                 "abstract": None, "openAccessPdf": None}
        result = paper_scanner.evaluate_paper(paper)
        self.assertIsInstance(result["score"], int)

    def test_empty_paper_handled(self):
        result = paper_scanner.evaluate_paper({})
        self.assertIsInstance(result["score"], int)
        self.assertEqual(result["venue_quality"], "unknown")
        self.assertFalse(result["has_code"])

    def test_reasons_always_list(self):
        result = paper_scanner.evaluate_paper({})
        self.assertIsInstance(result["reasons"], list)
        self.assertTrue(len(result["reasons"]) > 0)

    def test_fifty_citations(self):
        paper = {"citationCount": 50, "venue": "", "publicationDate": "", "abstract": ""}
        result = paper_scanner.evaluate_paper(paper)
        self.assertTrue(any("Good citations" in r for r in result["reasons"]))

    def test_moderate_citations(self):
        paper = {"citationCount": 15, "venue": "", "publicationDate": "", "abstract": ""}
        result = paper_scanner.evaluate_paper(paper)
        self.assertTrue(any("Moderate citations" in r for r in result["reasons"]))

    def test_some_citations(self):
        paper = {"citationCount": 7, "venue": "", "publicationDate": "", "abstract": ""}
        result = paper_scanner.evaluate_paper(paper)
        self.assertTrue(any("Some citations" in r for r in result["reasons"]))


class TestPaperLog(unittest.TestCase):
    """Test paper logging and stats."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_log = paper_scanner.PAPER_LOG
        paper_scanner.PAPER_LOG = os.path.join(self.tmpdir, "papers.jsonl")

    def tearDown(self):
        paper_scanner.PAPER_LOG = self.orig_log
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_log_paper_creates_file(self):
        paper = {"title": "Test Paper", "authors": [{"name": "Alice"}],
                 "url": "http://example.com", "venue": "ICML",
                 "publicationDate": "2025-01-01", "citationCount": 10}
        evaluation = {"score": 65, "venue_quality": "top", "has_code": False,
                      "domain_hits": {"agents": 2}, "reasons": ["Top venue"]}
        entry = paper_scanner.log_paper(paper, evaluation, "IMPLEMENT")
        self.assertTrue(os.path.exists(paper_scanner.PAPER_LOG))
        self.assertEqual(entry["verdict"], "IMPLEMENT")
        self.assertEqual(entry["title"], "Test Paper")

    def test_load_empty_log(self):
        entries = paper_scanner.load_paper_log()
        self.assertEqual(entries, [])

    def test_load_populated_log(self):
        # Write 3 entries
        for i in range(3):
            paper = {"title": f"Paper {i}", "authors": [], "url": "",
                     "venue": "", "publicationDate": "2025-01-01", "citationCount": i * 10}
            evaluation = {"score": 50 + i * 10, "venue_quality": "good", "has_code": False,
                          "domain_hits": {}, "reasons": []}
            paper_scanner.log_paper(paper, evaluation, "REFERENCE")

        entries = paper_scanner.load_paper_log()
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["title"], "Paper 0")

    def test_stats_empty(self):
        stats = paper_scanner.paper_stats()
        self.assertEqual(stats["total"], 0)

    def test_stats_populated(self):
        papers = [
            ({"title": "A", "authors": [], "url": "", "venue": "ICML",
              "publicationDate": "2025-01-01", "citationCount": 50},
             {"score": 70, "venue_quality": "top", "has_code": True,
              "domain_hits": {"agents": 2}, "reasons": []}, "IMPLEMENT"),
            ({"title": "B", "authors": [], "url": "", "venue": "",
              "publicationDate": "2024-01-01", "citationCount": 5},
             {"score": 25, "venue_quality": "unknown", "has_code": False,
              "domain_hits": {"statistics": 1}, "reasons": []}, "SKIP"),
        ]
        for paper, evaluation, verdict in papers:
            paper_scanner.log_paper(paper, evaluation, verdict)

        stats = paper_scanner.paper_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["by_verdict"]["IMPLEMENT"], 1)
        self.assertEqual(stats["by_verdict"]["SKIP"], 1)
        self.assertEqual(stats["avg_score"], 47.5)
        self.assertIn("agents", stats["by_domain"])

    def test_log_paper_appends(self):
        for i in range(5):
            paper = {"title": f"Paper {i}", "authors": [], "url": "",
                     "venue": "", "publicationDate": "", "citationCount": 0}
            paper_scanner.log_paper(paper, {"score": 0, "venue_quality": "unknown",
                                            "has_code": False, "domain_hits": {}, "reasons": []}, "SKIP")

        entries = paper_scanner.load_paper_log()
        self.assertEqual(len(entries), 5)

    def test_log_entry_has_timestamp(self):
        paper = {"title": "Test", "authors": [], "url": "", "venue": "",
                 "publicationDate": "", "citationCount": 0}
        entry = paper_scanner.log_paper(paper, {"score": 0, "venue_quality": "unknown",
                                                "has_code": False, "domain_hits": {}, "reasons": []}, "SKIP")
        self.assertIn("timestamp", entry)


class TestFormatAuthors(unittest.TestCase):
    """Test author formatting."""

    def test_dict_authors(self):
        paper = {"authors": [{"name": "Alice Smith"}, {"name": "Bob Jones"}]}
        result = paper_scanner._format_authors(paper)
        self.assertIn("Alice Smith", result)
        self.assertIn("Bob Jones", result)

    def test_string_authors(self):
        paper = {"authors": ["Alice Smith", "Bob Jones"]}
        result = paper_scanner._format_authors(paper)
        self.assertIn("Alice Smith", result)

    def test_many_authors_truncated(self):
        paper = {"authors": [{"name": f"Author {i}"} for i in range(10)]}
        result = paper_scanner._format_authors(paper)
        self.assertIn("et al.", result)
        self.assertIn("10 total", result)

    def test_no_authors(self):
        paper = {"authors": []}
        result = paper_scanner._format_authors(paper)
        self.assertEqual(result, "")

    def test_missing_authors_key(self):
        paper = {}
        result = paper_scanner._format_authors(paper)
        self.assertEqual(result, "")


class TestArxivParsing(unittest.TestCase):
    """Test arXiv XML response parsing."""

    SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2301.12345v1</id>
        <title>Test Paper Title</title>
        <summary>This is a test abstract about agent systems.</summary>
        <published>2023-01-15T00:00:00Z</published>
        <author><name>Alice Researcher</name></author>
        <author><name>Bob Scientist</name></author>
        <link title="pdf" href="http://arxiv.org/pdf/2301.12345v1" />
      </entry>
    </feed>"""

    def test_parse_single_entry(self):
        papers = paper_scanner._parse_arxiv_response(self.SAMPLE_ARXIV_XML)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "Test Paper Title")
        self.assertEqual(papers[0]["arxiv_id"], "2301.12345")
        self.assertEqual(len(papers[0]["authors"]), 2)
        self.assertEqual(papers[0]["source"], "arxiv")

    def test_parse_pdf_link(self):
        papers = paper_scanner._parse_arxiv_response(self.SAMPLE_ARXIV_XML)
        self.assertIn("pdf", papers[0]["pdf_url"])

    def test_parse_empty_feed(self):
        xml = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
        papers = paper_scanner._parse_arxiv_response(xml)
        self.assertEqual(papers, [])

    def test_parse_invalid_xml(self):
        papers = paper_scanner._parse_arxiv_response("not xml at all")
        self.assertEqual(len(papers), 1)
        self.assertIn("error", papers[0])

    def test_parse_multiple_entries(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2301.11111v1</id>
            <title>Paper One</title>
            <summary>Abstract one.</summary>
            <published>2023-01-01T00:00:00Z</published>
          </entry>
          <entry>
            <id>http://arxiv.org/abs/2301.22222v2</id>
            <title>Paper Two</title>
            <summary>Abstract two.</summary>
            <published>2023-02-01T00:00:00Z</published>
          </entry>
        </feed>"""
        papers = paper_scanner._parse_arxiv_response(xml)
        self.assertEqual(len(papers), 2)
        self.assertEqual(papers[0]["title"], "Paper One")
        self.assertEqual(papers[1]["arxiv_id"], "2301.22222")


class TestDomainQueries(unittest.TestCase):
    """Test domain configuration."""

    def test_all_domains_have_queries(self):
        for domain in ["agents", "prediction", "statistics", "interaction"]:
            self.assertIn(domain, paper_scanner.DOMAIN_QUERIES)
            self.assertTrue(len(paper_scanner.DOMAIN_QUERIES[domain]) > 0)

    def test_domain_queries_are_strings(self):
        for domain, queries in paper_scanner.DOMAIN_QUERIES.items():
            for q in queries:
                self.assertIsInstance(q, str)
                self.assertTrue(len(q) > 5, f"Query too short in domain {domain}: {q}")


class TestSearchDomain(unittest.TestCase):
    """Test domain search with mocked API."""

    @patch("paper_scanner.search_semantic_scholar")
    @patch("paper_scanner.time")
    def test_search_domain_dedupes(self, mock_time, mock_search):
        """Duplicate papers across queries should be deduped."""
        mock_time.sleep = MagicMock()
        mock_search.return_value = [
            {"title": "Same Paper", "citationCount": 10, "venue": "ICML",
             "publicationDate": "2025-01-01", "abstract": "agent tool use"},
        ]

        results = paper_scanner.search_domain("agents")
        # 4 queries all return the same paper — should be deduped to 1
        self.assertEqual(len(results), 1)

    @patch("paper_scanner.search_semantic_scholar")
    @patch("paper_scanner.time")
    def test_search_domain_sorts_by_score(self, mock_time, mock_search):
        mock_time.sleep = MagicMock()
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    {"title": "Low Paper", "citationCount": 1, "venue": "",
                     "publicationDate": "2020-01-01", "abstract": "stuff"},
                ]
            elif call_count[0] == 2:
                return [
                    {"title": "High Paper", "citationCount": 200, "venue": "NeurIPS",
                     "publicationDate": "2025-01-01", "abstract": "agent multi-agent tool use",
                     "openAccessPdf": {"url": "http://pdf"}},
                ]
            return []

        mock_search.side_effect = side_effect
        results = paper_scanner.search_domain("agents")
        self.assertTrue(len(results) >= 2)
        # First result should be highest scored
        self.assertGreater(results[0][1]["score"], results[-1][1]["score"])

    @patch("paper_scanner.search_semantic_scholar")
    @patch("paper_scanner.time")
    def test_search_domain_handles_errors(self, mock_time, mock_search):
        mock_time.sleep = MagicMock()
        mock_search.return_value = [{"error": "timeout"}]
        results = paper_scanner.search_domain("agents")
        self.assertEqual(results, [])

    def test_search_domain_unknown(self):
        results = paper_scanner.search_domain("nonexistent")
        self.assertEqual(results, [])


class TestSemanticScholarClient(unittest.TestCase):
    """Test Semantic Scholar API client with mocked HTTP."""

    @patch("paper_scanner.urllib.request.urlopen")
    def test_search_returns_papers(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "data": [{"title": "Test Paper", "citationCount": 10}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock()
        mock_urlopen.return_value = mock_resp

        results = paper_scanner.search_semantic_scholar("test query")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Test Paper")

    @patch("paper_scanner.urllib.request.urlopen")
    def test_search_handles_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        results = paper_scanner.search_semantic_scholar("test")
        self.assertEqual(len(results), 1)
        self.assertIn("error", results[0])

    @patch("paper_scanner.urllib.request.urlopen")
    def test_get_paper_details(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "title": "Detailed Paper", "citationCount": 50
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock()
        mock_urlopen.return_value = mock_resp

        result = paper_scanner.get_paper_details("abc123")
        self.assertEqual(result["title"], "Detailed Paper")

    @patch("paper_scanner.urllib.request.urlopen")
    def test_get_paper_details_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://example.com", 404, "Not Found", {}, None)
        result = paper_scanner.get_paper_details("bad_id")
        self.assertIn("error", result)


import urllib.error


class TestFetchJsonRetry(unittest.TestCase):
    """Test HTTP fetch with 429 retry logic."""

    @patch("paper_scanner.time")
    @patch("paper_scanner.urllib.request.urlopen")
    def test_retry_on_429(self, mock_urlopen, mock_time):
        mock_time.sleep = MagicMock()
        # First call: 429, second call: success
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"title": "Success"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock()

        mock_urlopen.side_effect = [
            urllib.error.HTTPError("http://x", 429, "Rate Limited", {}, None),
            mock_resp,
        ]

        result = paper_scanner._fetch_json("http://example.com/api")
        self.assertEqual(result["title"], "Success")
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_time.sleep.assert_called_once()

    @patch("paper_scanner.time")
    @patch("paper_scanner.urllib.request.urlopen")
    def test_max_retries_exceeded(self, mock_urlopen, mock_time):
        mock_time.sleep = MagicMock()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://x", 429, "Rate Limited", {}, None)

        result = paper_scanner._fetch_json("http://example.com/api")
        self.assertIn("error", result)
        self.assertEqual(mock_urlopen.call_count, 3)  # MAX_RETRIES = 3

    @patch("paper_scanner.urllib.request.urlopen")
    def test_non_429_error_no_retry(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://x", 500, "Server Error", {}, None)

        result = paper_scanner._fetch_json("http://example.com/api")
        self.assertIn("error", result)
        self.assertEqual(mock_urlopen.call_count, 1)  # No retry on 500

    @patch("paper_scanner.time")
    @patch("paper_scanner.urllib.request.urlopen")
    def test_exponential_backoff_delays(self, mock_urlopen, mock_time):
        mock_time.sleep = MagicMock()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://x", 429, "Rate Limited", {}, None)

        paper_scanner._fetch_json("http://example.com/api")
        # Should have slept with exponential delays: 2, 4
        calls = mock_time.sleep.call_args_list
        self.assertEqual(len(calls), 2)  # MAX_RETRIES-1 sleeps
        self.assertEqual(calls[0][0][0], 2)   # RETRY_BASE_DELAY * 2^0
        self.assertEqual(calls[1][0][0], 4)   # RETRY_BASE_DELAY * 2^1


class TestArxivClient(unittest.TestCase):
    """Test arXiv API client with mocked HTTP."""

    @patch("paper_scanner.urllib.request.urlopen")
    def test_search_arxiv_returns_papers(self, mock_urlopen):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2301.12345v1</id>
            <title>ArXiv Paper</title>
            <summary>Abstract.</summary>
            <published>2023-01-15T00:00:00Z</published>
            <author><name>Test Author</name></author>
          </entry>
        </feed>"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = xml.encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock()
        mock_urlopen.return_value = mock_resp

        results = paper_scanner.search_arxiv("test query")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "ArXiv Paper")

    @patch("paper_scanner.urllib.request.urlopen")
    def test_search_arxiv_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("timeout")
        results = paper_scanner.search_arxiv("test")
        self.assertEqual(len(results), 1)
        self.assertIn("error", results[0])


if __name__ == "__main__":
    unittest.main()
