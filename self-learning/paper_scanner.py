#!/usr/bin/env python3
"""
paper_scanner.py — MT-12: Academic paper discovery and evaluation.

Searches Semantic Scholar and arXiv for papers relevant to CCA domains:
- Prediction markets and forecasting
- AI agent architecture (self-improvement, tool use, context management)
- Statistical methods (Bayesian inference, time series, anomaly detection)
- Human-AI interaction (prompt engineering, cognitive load)

Uses only stdlib (urllib, json, xml). No external dependencies.

Usage:
    python3 paper_scanner.py search "query terms"
    python3 paper_scanner.py search "query terms" --domain agents --min-citations 10
    python3 paper_scanner.py evaluate <paper_id>
    python3 paper_scanner.py log
    python3 paper_scanner.py stats
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

# === Configuration ===

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
ARXIV_BASE = "http://export.arxiv.org/api/query"

# Fields to request from Semantic Scholar
SS_FIELDS = "title,url,abstract,citationCount,publicationDate,openAccessPdf,authors,venue,publicationTypes,fieldsOfStudy,externalIds"

# Paper log file
PAPER_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "research", "papers.jsonl")

# Quality thresholds
MIN_CITATION_DEFAULT = 5
TOP_VENUES = {
    "neurips", "nips", "icml", "iclr", "aaai", "acl", "emnlp", "naacl",
    "cvpr", "iccv", "eccv", "sigir", "kdd", "www", "ijcai",
    "nature", "science", "pnas", "arxiv",  # arXiv as source, not venue quality
    "jmlr", "tacl", "tmlr",
    "ieee", "acm",
}

# Domain search queries — curated for CCA and Kalshi relevance
# Rate limit retry config
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds, doubles each retry

DOMAIN_QUERIES = {
    "agents": [
        "AI agent self-improvement tool use",
        "LLM agent context management optimization",
        "multi-agent coordination conflict resolution",
        "code generation agent evaluation benchmark",
    ],
    "prediction": [
        "prediction market calibration automated trading",
        "forecasting aggregation information markets",
        "binary event prediction Bayesian updating",
        "market microstructure algorithmic trading",
    ],
    "statistics": [
        "Bayesian inference online learning time series",
        "anomaly detection streaming data real-time",
        "sequential decision making bandit algorithms",
        "probability calibration machine learning",
    ],
    "interaction": [
        "prompt engineering systematic evaluation",
        "human AI collaboration cognitive load",
        "LLM output quality measurement",
        "developer tools AI assistance IDE",
    ],
}


# === HTTP Helpers ===

def _fetch_json(url, timeout=15):
    """Fetch JSON from URL with retry on 429 rate limit.

    Returns parsed JSON dict/list, or {"error": str} on failure.
    """
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CCA-PaperScanner/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay)
                continue
            return {"error": str(e)}
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            return {"error": str(e)}
    return {"error": "Max retries exceeded"}


# === Semantic Scholar Client ===

def search_semantic_scholar(query, year_range=None, min_citations=None,
                            fields_of_study=None, limit=20):
    """Search Semantic Scholar for papers.

    Args:
        query: Search query string
        year_range: e.g. "2023-" or "2022-2024"
        min_citations: Minimum citation count filter
        fields_of_study: e.g. "Computer Science"
        limit: Max results to return

    Returns:
        List of paper dicts with requested fields.
    """
    params = {
        "query": query,
        "fields": SS_FIELDS,
        "limit": str(min(limit, 100)),  # API max is 100 per page
    }
    if year_range:
        params["year"] = year_range
    if min_citations is not None:
        params["minCitationCount"] = str(min_citations)
    if fields_of_study:
        params["fieldsOfStudy"] = fields_of_study

    url = f"{SEMANTIC_SCHOLAR_BASE}/paper/search/bulk?{urllib.parse.urlencode(params)}"
    data = _fetch_json(url)
    if "error" in data:
        return [data]
    return data.get("data", [])


def get_paper_details(paper_id):
    """Get detailed info for a single paper by Semantic Scholar ID or DOI.

    Args:
        paper_id: Semantic Scholar paper ID, DOI, or arXiv ID (e.g. "arXiv:2301.12345")

    Returns:
        Paper dict with all fields, or error dict.
    """
    url = f"{SEMANTIC_SCHOLAR_BASE}/paper/{urllib.parse.quote(paper_id, safe='')}?fields={SS_FIELDS}"
    return _fetch_json(url)


# === arXiv Client ===

def search_arxiv(query, max_results=10):
    """Search arXiv for papers.

    Args:
        query: Search query (arXiv query syntax)
        max_results: Max results to return

    Returns:
        List of paper dicts with title, summary, authors, links, published date.
    """
    params = {
        "search_query": f"all:{query}",
        "start": "0",
        "max_results": str(max_results),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = f"{ARXIV_BASE}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CCA-PaperScanner/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode("utf-8")
            return _parse_arxiv_response(xml_data)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        return [{"error": str(e)}]


def _parse_arxiv_response(xml_data):
    """Parse arXiv Atom XML response into paper dicts."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers = []

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return [{"error": "Failed to parse arXiv XML response"}]

    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        published_el = entry.find("atom:published", ns)
        id_el = entry.find("atom:id", ns)

        authors = []
        for author_el in entry.findall("atom:author", ns):
            name_el = author_el.find("atom:name", ns)
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())

        # Extract arXiv ID from URL
        arxiv_url = id_el.text.strip() if id_el is not None and id_el.text else ""
        arxiv_id = ""
        if arxiv_url:
            match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?$", arxiv_url)
            if match:
                arxiv_id = match.group(1)

        pdf_link = ""
        for link_el in entry.findall("atom:link", ns):
            if link_el.get("title") == "pdf":
                pdf_link = link_el.get("href", "")

        papers.append({
            "title": title_el.text.strip() if title_el is not None and title_el.text else "",
            "abstract": summary_el.text.strip() if summary_el is not None and summary_el.text else "",
            "authors": authors,
            "published": published_el.text.strip() if published_el is not None and published_el.text else "",
            "arxiv_id": arxiv_id,
            "url": arxiv_url,
            "pdf_url": pdf_link,
            "source": "arxiv",
        })

    return papers


# === Paper Evaluation ===

def evaluate_paper(paper):
    """Score a paper for CCA/Kalshi relevance.

    Returns dict with:
        score: 0-100 relevance score
        venue_quality: "top" / "good" / "unknown"
        has_code: bool
        reasons: list of scoring reasons
    """
    score = 0
    reasons = []

    # Citation impact (up to 25 points)
    citations = paper.get("citationCount", 0) or 0
    if citations >= 100:
        score += 25
        reasons.append(f"High citations ({citations})")
    elif citations >= 50:
        score += 20
        reasons.append(f"Good citations ({citations})")
    elif citations >= 10:
        score += 15
        reasons.append(f"Moderate citations ({citations})")
    elif citations >= 5:
        score += 10
        reasons.append(f"Some citations ({citations})")
    else:
        reasons.append(f"Low citations ({citations})")

    # Venue quality (up to 25 points)
    venue = (paper.get("venue") or "").lower()
    venue_quality = "unknown"
    if any(v in venue for v in TOP_VENUES):
        score += 25
        venue_quality = "top"
        reasons.append(f"Top venue: {venue}")
    elif venue:
        score += 10
        venue_quality = "good"
        reasons.append(f"Known venue: {venue}")
    else:
        reasons.append("No venue info")

    # Open access / code availability (up to 15 points)
    has_code = False
    oa_pdf = paper.get("openAccessPdf")
    if oa_pdf and isinstance(oa_pdf, dict) and oa_pdf.get("url"):
        score += 10
        reasons.append("Open access PDF available")

    # Check abstract for code/implementation signals
    abstract = (paper.get("abstract") or "").lower()
    code_signals = ["github.com", "our code", "open source", "implementation available",
                    "code release", "repository", "we release"]
    if any(signal in abstract for signal in code_signals):
        score += 5
        has_code = True
        reasons.append("Code availability mentioned")

    # Recency (up to 15 points)
    pub_date = paper.get("publicationDate") or ""
    if pub_date:
        try:
            year = int(pub_date[:4])
            current_year = datetime.now().year
            if year >= current_year:
                score += 15
                reasons.append(f"Very recent ({year})")
            elif year >= current_year - 1:
                score += 10
                reasons.append(f"Recent ({year})")
            elif year >= current_year - 2:
                score += 5
                reasons.append(f"Somewhat recent ({year})")
        except (ValueError, IndexError):
            pass

    # Domain relevance (up to 20 points) — keyword matching in abstract
    domain_keywords = {
        "agents": ["agent", "tool use", "self-improvement", "code generation",
                    "context window", "multi-agent"],
        "prediction": ["prediction market", "forecasting", "calibration",
                       "trading", "market microstructure", "binary event"],
        "statistics": ["bayesian", "time series", "anomaly detection",
                       "sequential decision", "bandit", "probability calibration"],
        "interaction": ["prompt engineering", "human-ai", "cognitive load",
                        "developer tool", "ide", "llm evaluation"],
    }

    domain_hits = {}
    for domain, keywords in domain_keywords.items():
        hits = sum(1 for kw in keywords if kw in abstract)
        if hits > 0:
            domain_hits[domain] = hits

    if domain_hits:
        best_domain = max(domain_hits, key=domain_hits.get)
        best_hits = domain_hits[best_domain]
        domain_score = min(20, best_hits * 7)
        score += domain_score
        reasons.append(f"Domain match: {best_domain} ({best_hits} keywords)")

    return {
        "score": min(100, score),
        "venue_quality": venue_quality,
        "has_code": has_code,
        "domain_hits": domain_hits,
        "reasons": reasons,
    }


# === Paper Log ===

def log_paper(paper, evaluation, verdict):
    """Log a paper evaluation to papers.jsonl.

    Args:
        paper: Paper dict from search results
        evaluation: Evaluation dict from evaluate_paper()
        verdict: "IMPLEMENT" / "REFERENCE" / "SKIP"
    """
    os.makedirs(os.path.dirname(PAPER_LOG), exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "title": paper.get("title", ""),
        "authors": _format_authors(paper),
        "url": paper.get("url", ""),
        "venue": paper.get("venue", ""),
        "year": (paper.get("publicationDate") or "")[:4],
        "citations": paper.get("citationCount", 0),
        "score": evaluation["score"],
        "venue_quality": evaluation["venue_quality"],
        "has_code": evaluation["has_code"],
        "domains": list(evaluation.get("domain_hits", {}).keys()),
        "verdict": verdict,
        "reasons": evaluation["reasons"],
    }

    with open(PAPER_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def load_paper_log():
    """Load all entries from papers.jsonl."""
    if not os.path.exists(PAPER_LOG):
        return []
    entries = []
    with open(PAPER_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def _format_authors(paper):
    """Extract author names from paper dict."""
    authors = paper.get("authors", [])
    if not authors:
        return ""
    if isinstance(authors[0], dict):
        names = [a.get("name", "") for a in authors[:5]]
    else:
        names = authors[:5]
    result = ", ".join(n for n in names if n)
    if len(authors) > 5:
        result += f" et al. ({len(authors)} total)"
    return result


def paper_stats():
    """Return summary statistics from the paper log."""
    entries = load_paper_log()
    if not entries:
        return {"total": 0, "by_verdict": {}, "by_domain": {}, "avg_score": 0}

    by_verdict = {}
    by_domain = {}
    scores = []

    for e in entries:
        v = e.get("verdict", "UNKNOWN")
        by_verdict[v] = by_verdict.get(v, 0) + 1
        scores.append(e.get("score", 0))
        for d in e.get("domains", []):
            by_domain[d] = by_domain.get(d, 0) + 1

    return {
        "total": len(entries),
        "by_verdict": by_verdict,
        "by_domain": by_domain,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "top_scored": sorted(entries, key=lambda x: x.get("score", 0), reverse=True)[:5],
    }


# === Domain Search ===

def search_domain(domain, year_range="2024-", min_citations=None, limit=10):
    """Search for papers in a predefined CCA domain.

    Args:
        domain: One of "agents", "prediction", "statistics", "interaction"
        year_range: Year filter for Semantic Scholar
        min_citations: Minimum citation count
        limit: Max results per query

    Returns:
        List of (paper, evaluation) tuples, sorted by score descending.
    """
    queries = DOMAIN_QUERIES.get(domain)
    if not queries:
        return []

    all_results = []
    seen_titles = set()

    for query in queries:
        papers = search_semantic_scholar(
            query,
            year_range=year_range,
            min_citations=min_citations,
            limit=limit,
        )

        for paper in papers:
            if "error" in paper:
                continue
            title = (paper.get("title") or "").lower().strip()
            if title in seen_titles:
                continue
            seen_titles.add(title)

            evaluation = evaluate_paper(paper)
            all_results.append((paper, evaluation))

        # Rate limit: be a good citizen (shared limit across all unauthenticated users)
        # Increased from 1.5s to 3s after hitting 429 rate limits in Session 38
        time.sleep(3.0)

    # Sort by score descending
    all_results.sort(key=lambda x: x[1]["score"], reverse=True)
    return all_results


# === CLI ===

def _print_paper(paper, evaluation=None, index=None):
    """Print a paper in a readable format."""
    prefix = f"[{index}] " if index is not None else ""
    title = paper.get("title", "Untitled")
    authors = _format_authors(paper)
    year = (paper.get("publicationDate") or "")[:4]
    venue = paper.get("venue") or "—"
    citations = paper.get("citationCount", 0) or 0
    url = paper.get("url", "")

    print(f"{prefix}{title}")
    print(f"  Authors: {authors}")
    print(f"  Year: {year} | Venue: {venue} | Citations: {citations}")
    if url:
        print(f"  URL: {url}")

    if evaluation:
        print(f"  Score: {evaluation['score']}/100 — {', '.join(evaluation['reasons'])}")

    print()


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  paper_scanner.py search <query> [--domain <d>] [--min-citations <n>] [--year <range>]")
        print("  paper_scanner.py domain <agents|prediction|statistics|interaction>")
        print("  paper_scanner.py evaluate <paper_id>")
        print("  paper_scanner.py log")
        print("  paper_scanner.py stats")
        sys.exit(1)

    command = sys.argv[1]

    if command == "search":
        if len(sys.argv) < 3:
            print("Usage: paper_scanner.py search <query>")
            sys.exit(1)

        query = sys.argv[2]
        min_cit = None
        year = "2024-"

        # Parse optional flags
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == "--min-citations" and i + 1 < len(args):
                min_cit = int(args[i + 1])
                i += 2
            elif args[i] == "--year" and i + 1 < len(args):
                year = args[i + 1]
                i += 2
            else:
                i += 1

        papers = search_semantic_scholar(query, year_range=year, min_citations=min_cit)
        if not papers:
            print("No results found.")
            return

        for idx, paper in enumerate(papers[:20], 1):
            if "error" in paper:
                print(f"Error: {paper['error']}")
                continue
            evaluation = evaluate_paper(paper)
            _print_paper(paper, evaluation, idx)

    elif command == "domain":
        if len(sys.argv) < 3:
            print(f"Usage: paper_scanner.py domain <{'|'.join(DOMAIN_QUERIES.keys())}>")
            sys.exit(1)

        domain = sys.argv[2]
        if domain not in DOMAIN_QUERIES:
            print(f"Unknown domain: {domain}. Choose from: {', '.join(DOMAIN_QUERIES.keys())}")
            sys.exit(1)

        print(f"Searching domain: {domain}...")
        results = search_domain(domain)
        if not results:
            print("No results found.")
            return

        for idx, (paper, evaluation) in enumerate(results[:20], 1):
            _print_paper(paper, evaluation, idx)

    elif command == "evaluate":
        if len(sys.argv) < 3:
            print("Usage: paper_scanner.py evaluate <paper_id>")
            sys.exit(1)

        paper_id = sys.argv[2]
        paper = get_paper_details(paper_id)
        if "error" in paper:
            print(f"Error: {paper['error']}")
            return

        evaluation = evaluate_paper(paper)
        _print_paper(paper, evaluation)

        # Determine verdict based on score
        if evaluation["score"] >= 60:
            verdict = "IMPLEMENT"
        elif evaluation["score"] >= 30:
            verdict = "REFERENCE"
        else:
            verdict = "SKIP"

        print(f"Verdict: {verdict}")
        entry = log_paper(paper, evaluation, verdict)
        print(f"Logged to {PAPER_LOG}")

    elif command == "log":
        entries = load_paper_log()
        if not entries:
            print("No papers logged yet.")
            return

        for entry in entries:
            v = entry.get("verdict", "?")
            s = entry.get("score", 0)
            t = entry.get("title", "Untitled")
            y = entry.get("year", "?")
            print(f"[{v}] ({s}/100) {t} ({y})")

    elif command == "stats":
        stats = paper_stats()
        if stats["total"] == 0:
            print("No papers logged yet.")
            return

        print(f"Total papers: {stats['total']}")
        print(f"Average score: {stats['avg_score']}/100")
        print(f"By verdict: {json.dumps(stats['by_verdict'])}")
        print(f"By domain: {json.dumps(stats['by_domain'])}")
        if stats.get("top_scored"):
            print("\nTop scored:")
            for p in stats["top_scored"]:
                print(f"  [{p.get('verdict')}] ({p.get('score')}/100) {p.get('title', '')[:80]}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
