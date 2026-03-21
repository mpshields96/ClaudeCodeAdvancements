#!/usr/bin/env python3
"""
paper_digest.py — MT-12 Phase 3: Academic paper digest generator.

Takes papers from paper_scanner's log (papers.jsonl) and generates
actionable summaries for:
- Kalshi research chat (via cross-chat bridge)
- CCA session context (agents, context management domains)

Tracks which papers have been processed to avoid re-sending.

Usage:
    python3 paper_digest.py kalshi          # Kalshi-relevant digest
    python3 paper_digest.py cca             # CCA-relevant digest
    python3 paper_digest.py bridge          # Concise bridge message for Kalshi chat
    python3 paper_digest.py unprocessed     # Show unprocessed papers
    python3 paper_digest.py stats           # Digest statistics
"""

import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import Optional


# === Data Classes ===

@dataclass
class DigestEntry:
    """A processed paper ready for digest output."""
    title: str
    authors: str
    url: str
    score: int
    domain: str
    verdict: str  # IMPLEMENT / REFERENCE / SKIP
    relevance_to_kalshi: str
    actionable_insight: str

    def to_dict(self) -> dict:
        return asdict(self)


# === Domain Relevance ===

# Domains most relevant to Kalshi bot (prediction markets, trading, statistics)
KALSHI_DOMAINS = {"prediction", "statistics", "trading_systems"}

# Domains most relevant to CCA (agents, context management, code review)
CCA_DOMAINS = {"agents", "context_management", "code_review", "interaction"}

# Kalshi relevance bonus by domain
KALSHI_DOMAIN_BONUS = {
    "prediction": 30,
    "trading_systems": 30,
    "statistics": 20,
    "agents": 5,
    "context_management": 5,
    "code_review": 0,
    "interaction": 0,
}

# Verdict bonus for ranking
VERDICT_BONUS = {
    "IMPLEMENT": 20,
    "REFERENCE": 0,
    "SKIP": -30,
}


# === Filtering ===

def filter_papers_by_domain(papers: list[dict], domain: str) -> list[dict]:
    """Filter papers to those matching a specific domain."""
    return [p for p in papers if domain in p.get("domains", [])]


def rank_for_kalshi_relevance(papers: list[dict]) -> list[dict]:
    """Rank papers by Kalshi-specific relevance.

    Prediction/trading/statistics domains get large bonuses.
    IMPLEMENT verdict gets bonus over REFERENCE.
    SKIP verdict gets penalty.
    """
    def kalshi_score(paper):
        base = paper.get("score", 0)
        # Domain bonus: best matching Kalshi domain
        domains = paper.get("domains", [])
        domain_bonus = max(
            (KALSHI_DOMAIN_BONUS.get(d, 0) for d in domains),
            default=0
        )
        # Verdict bonus
        verdict = paper.get("verdict", "SKIP")
        v_bonus = VERDICT_BONUS.get(verdict, 0)
        return base + domain_bonus + v_bonus

    return sorted(papers, key=kalshi_score, reverse=True)


# === Digest Generation ===

def generate_digest_markdown(entries: list[DigestEntry], title: str = "Paper Digest") -> list[str] | str:
    """Generate a markdown digest from DigestEntry list.

    Returns markdown string with numbered entries.
    """
    if not entries:
        return f"# {title}\n\nNo papers to digest."

    lines = [f"# {title}\n"]
    for i, entry in enumerate(entries, 1):
        lines.append(f"## {i}. [{entry.verdict}] {entry.title}")
        lines.append(f"**Authors:** {entry.authors}")
        lines.append(f"**Score:** {entry.score}/100 | **Domain:** {entry.domain}")
        lines.append(f"**URL:** {entry.url}")
        lines.append(f"**Kalshi relevance:** {entry.relevance_to_kalshi}")
        lines.append(f"**Actionable insight:** {entry.actionable_insight}")
        lines.append("")

    return "\n".join(lines)


def format_digest_for_bridge(entries: list[DigestEntry], max_entries: int = 5) -> str:
    """Format digest as a concise bridge message for cross-chat delivery.

    Keeps messages short — bridge messages should be actionable, not verbose.
    """
    if not entries:
        return "PAPER DIGEST: No new papers to report."

    top = entries[:max_entries]
    lines = [f"PAPER DIGEST ({len(top)} papers):"]
    for entry in top:
        lines.append(
            f"- [{entry.verdict}] {entry.title} (score {entry.score}) "
            f"— {entry.actionable_insight}"
        )
    return "\n".join(lines)


# === Main Digest Class ===

class PaperDigest:
    """Main digest engine — loads papers, filters, generates output."""

    def __init__(self, log_path: str = None):
        if log_path is None:
            log_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "research", "papers.jsonl"
            )
        self.log_path = log_path
        self.processed_path = log_path.replace(".jsonl", "_processed.json")
        self.papers = self._load_papers()
        self._processed = self._load_processed()

    def _load_papers(self) -> list[dict]:
        if not os.path.exists(self.log_path):
            return []
        entries = []
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def _load_processed(self) -> set[str]:
        if not os.path.exists(self.processed_path):
            return set()
        try:
            with open(self.processed_path) as f:
                data = json.load(f)
            return set(data.get("processed_titles", []))
        except (json.JSONDecodeError, KeyError):
            return set()

    def _save_processed(self):
        os.makedirs(os.path.dirname(self.processed_path) or ".", exist_ok=True)
        with open(self.processed_path, "w") as f:
            json.dump({"processed_titles": sorted(self._processed)}, f, indent=2)

    def kalshi_relevant(self, min_score: int = 50) -> list[dict]:
        """Papers relevant to Kalshi bot (prediction, trading, statistics)."""
        relevant = [
            p for p in self.papers
            if p.get("score", 0) >= min_score
            and p.get("verdict") != "SKIP"
            and any(d in KALSHI_DOMAINS for d in p.get("domains", []))
        ]
        return rank_for_kalshi_relevance(relevant)

    def cca_relevant(self, min_score: int = 50) -> list[dict]:
        """Papers relevant to CCA (agents, context, code review)."""
        relevant = [
            p for p in self.papers
            if p.get("score", 0) >= min_score
            and p.get("verdict") != "SKIP"
            and any(d in CCA_DOMAINS for d in p.get("domains", []))
        ]
        return sorted(relevant, key=lambda p: p.get("score", 0), reverse=True)

    def unprocessed(self) -> list[dict]:
        """Papers not yet sent to any chat."""
        return [p for p in self.papers if p.get("title") not in self._processed]

    def mark_processed(self, title: str):
        """Mark a paper as processed (sent to a chat)."""
        self._processed.add(title)
        self._save_processed()

    def _paper_to_entry(self, paper: dict) -> DigestEntry:
        """Convert a raw paper dict to a DigestEntry."""
        domains = paper.get("domains", [])
        primary_domain = domains[0] if domains else "unknown"

        # Generate relevance description based on domains
        kalshi_domains = [d for d in domains if d in KALSHI_DOMAINS]
        if kalshi_domains:
            relevance = f"Direct: {', '.join(kalshi_domains)}"
        elif any(d in CCA_DOMAINS for d in domains):
            relevance = f"Indirect (CCA): {', '.join(d for d in domains if d in CCA_DOMAINS)}"
        else:
            relevance = "Low relevance"

        # Generate actionable insight from reasons
        reasons = paper.get("reasons", [])
        insight = "; ".join(reasons[:2]) if reasons else "Review paper for applicability"

        return DigestEntry(
            title=paper.get("title", "Untitled"),
            authors=paper.get("authors", "Unknown"),
            url=paper.get("url", ""),
            score=paper.get("score", 0),
            domain=primary_domain,
            verdict=paper.get("verdict", "REFERENCE"),
            relevance_to_kalshi=relevance,
            actionable_insight=insight,
        )

    def generate_kalshi_digest(self, min_score: int = 50) -> str:
        """Generate a Kalshi-focused digest markdown."""
        papers = self.kalshi_relevant(min_score)
        entries = [self._paper_to_entry(p) for p in papers]
        return generate_digest_markdown(entries, title="Kalshi Research Paper Digest")

    def generate_cca_digest(self, min_score: int = 50) -> str:
        """Generate a CCA-focused digest markdown."""
        papers = self.cca_relevant(min_score)
        entries = [self._paper_to_entry(p) for p in papers]
        return generate_digest_markdown(entries, title="CCA Research Paper Digest")

    def generate_bridge_message(self, min_score: int = 50, max_entries: int = 5) -> str:
        """Generate a concise bridge message for Kalshi chat."""
        papers = self.kalshi_relevant(min_score)
        entries = [self._paper_to_entry(p) for p in papers]
        return format_digest_for_bridge(entries, max_entries=max_entries)

    def send_to_kalshi(self, min_score: int = 50, max_entries: int = 5) -> dict | None:
        """Send unprocessed Kalshi-relevant papers to Kalshi research chat via bridge.

        Only sends papers that haven't been sent before. Marks them processed after.
        Returns the sent message dict, or None if nothing to send.
        """
        # Filter to unprocessed + Kalshi-relevant
        unproc_titles = {p.get("title") for p in self.unprocessed()}
        kalshi_papers = [
            p for p in self.kalshi_relevant(min_score)
            if p.get("title") in unproc_titles
        ]

        if not kalshi_papers:
            return None

        entries = [self._paper_to_entry(p) for p in kalshi_papers[:max_entries]]
        bridge_msg = format_digest_for_bridge(entries, max_entries=max_entries)

        # Import cross_chat_queue (sibling directory)
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        try:
            from cross_chat_queue import send_message
            result = send_message(
                sender="cca",
                target="kr",
                subject=f"Paper digest: {len(entries)} Kalshi-relevant papers",
                body=bridge_msg,
                priority="medium",
                category="research_finding",
            )
        except (ImportError, Exception) as e:
            return {"error": str(e)}

        # Mark sent papers as processed
        for entry in entries:
            self.mark_processed(entry.title)

        return result


# === CLI ===

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 paper_digest.py [kalshi|cca|bridge|send|unprocessed|stats]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    digest = PaperDigest()

    if cmd == "kalshi":
        print(digest.generate_kalshi_digest())
    elif cmd == "cca":
        print(digest.generate_cca_digest())
    elif cmd == "bridge":
        print(digest.generate_bridge_message())
    elif cmd == "unprocessed":
        unproc = digest.unprocessed()
        if not unproc:
            print("All papers have been processed.")
        else:
            print(f"{len(unproc)} unprocessed papers:")
            for p in unproc:
                print(f"  [{p.get('verdict')}] ({p.get('score')}/100) {p.get('title')}")
    elif cmd == "stats":
        print(f"Total papers: {len(digest.papers)}")
        kalshi = digest.kalshi_relevant()
        cca = digest.cca_relevant()
        unproc = digest.unprocessed()
        print(f"Kalshi-relevant (score>=50): {len(kalshi)}")
        print(f"CCA-relevant (score>=50): {len(cca)}")
        print(f"Unprocessed: {len(unproc)}")
    elif cmd == "send":
        result = digest.send_to_kalshi()
        if result is None:
            print("No unprocessed Kalshi-relevant papers to send.")
        elif "error" in result:
            print(f"Error sending: {result['error']}")
        else:
            print(f"Sent paper digest to Kalshi research chat: {result.get('subject', '')}")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
