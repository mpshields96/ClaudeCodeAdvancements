#!/usr/bin/env python3
"""
Reddit Scout — Research utility for ClaudeCodeAdvancements.
Fetches top posts from relevant subreddits and logs findings for human review.

SECURITY CONTRACT (non-negotiable):
- Read-only: fetches public JSON from Reddit. No auth, no credentials.
- Never installs, clones, or executes anything found in posts.
- Never writes outside ClaudeCodeAdvancements folder.
- Output is a structured research log for human/Claude review only.
- Ideas are extracted as patterns — never as runnable code.

Usage:
  python3 research/reddit_scout.py               # run scout, save findings
  python3 research/reddit_scout.py --dry-run      # print findings, don't save
  python3 research/reddit_scout.py --summary      # print last finding file

Run: python3 research/tests/test_reddit_scout.py
"""

import json
import sys
import os
import re
import time
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ── Configuration ─────────────────────────────────────────────────────────────

SUBREDDITS = ["ClaudeAI", "ClaudeCode", "vibecoding"]

# Fetch top 25 hot posts per subreddit
REDDIT_URL = "https://www.reddit.com/r/{sub}/hot.json?limit=25"

# Keywords that indicate a post is relevant to our frontiers
RELEVANCE_KEYWORDS = [
    # Frontier 1: Memory
    "memory", "persistent", "remember", "forget", "context loss", "session",
    # Frontier 2: Spec / planning
    "spec", "requirements", "planning", "architecture", "workflow", "prompt engineering",
    # Frontier 3: Context
    "context window", "context limit", "compaction", "token limit", "degradation",
    # Frontier 4: Multi-agent
    "multi-agent", "parallel", "agent", "worktree", "concurrent", "conflict",
    # Frontier 5: Usage / cost
    "cost", "token", "usage", "billing", "expensive", "credits",
    # General Claude Code signal
    "claude code", "hooks", "mcp", "slash command", "automation", "agentic",
]

# Keywords that flag a post as rat poison — log but never act on
RAT_POISON_KEYWORDS = [
    "install", "pip install", "npm install", "download", "clone",
    "exe", "malware", "scam", "hack", "bypass", "jailbreak",
    "credentials", "api key", "token", "password", "login as",
]

FINDINGS_DIR = Path(__file__).parent / "findings"
USER_AGENT = "ClaudeCodeAdvancements-ResearchScout/1.0 (research only; no auth)"


# ── Fetching ──────────────────────────────────────────────────────────────────

def fetch_subreddit(subreddit: str, dry_run: bool = False) -> list[dict]:
    """Fetch hot posts from a subreddit. Returns list of post dicts."""
    url = REDDIT_URL.format(sub=subreddit)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        posts = data.get("data", {}).get("children", [])
        return [p["data"] for p in posts if p.get("kind") == "t3"]
    except (URLError, HTTPError, json.JSONDecodeError, KeyError) as e:
        if not dry_run:
            print(f"  [scout] Warning: could not fetch r/{subreddit}: {e}", file=sys.stderr)
        return []


# ── Relevance scoring ─────────────────────────────────────────────────────────

def _text(post: dict) -> str:
    """Combine title + selftext for keyword matching."""
    return (post.get("title", "") + " " + post.get("selftext", "")).lower()


def relevance_score(post: dict) -> int:
    """Count how many relevance keywords appear in the post. 0 = not relevant."""
    text = _text(post)
    return sum(1 for kw in RELEVANCE_KEYWORDS if kw in text)


def is_rat_poison(post: dict) -> bool:
    """True if the post contains rat poison keywords."""
    text = _text(post)
    return any(kw in text for kw in RAT_POISON_KEYWORDS)


def extract_idea(post: dict) -> str:
    """
    Extract a one-line idea summary from a post.
    Never copies code. Captures the pattern or pain point only.
    """
    title = post.get("title", "").strip()
    score = post.get("score", 0)
    num_comments = post.get("num_comments", 0)
    url = f"https://reddit.com{post.get('permalink', '')}"
    return f"{title} (↑{score}, {num_comments} comments) — {url}"


# ── Frontier mapping ──────────────────────────────────────────────────────────

FRONTIER_KEYWORDS = {
    "memory-system": ["memory", "persistent", "remember", "forget", "session", "context loss"],
    "spec-system": ["spec", "requirements", "planning", "architecture", "workflow"],
    "context-monitor": ["context window", "context limit", "compaction", "token limit", "degradation"],
    "agent-guard": ["multi-agent", "parallel", "agent", "worktree", "concurrent", "conflict"],
    "usage-dashboard": ["cost", "token", "usage", "billing", "expensive", "credits"],
}


def map_to_frontier(post: dict) -> str:
    """Return the most relevant frontier name, or 'general'."""
    text = _text(post)
    scores = {
        frontier: sum(1 for kw in kws if kw in text)
        for frontier, kws in FRONTIER_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


# ── Main scout run ─────────────────────────────────────────────────────────────

def run_scout(dry_run: bool = False) -> dict:
    """
    Fetch posts from all subreddits, score for relevance, return findings dict.
    """
    findings = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "subreddits_checked": SUBREDDITS,
        "relevant": [],
        "rat_poison_flagged": [],
        "stats": {}
    }

    for sub in SUBREDDITS:
        if not dry_run:
            print(f"  [scout] Fetching r/{sub}...", file=sys.stderr)
        posts = fetch_subreddit(sub, dry_run=dry_run)
        relevant_count = 0
        poison_count = 0

        for post in posts:
            score = relevance_score(post)
            if score == 0:
                continue

            entry = {
                "subreddit": sub,
                "frontier": map_to_frontier(post),
                "relevance_score": score,
                "idea": extract_idea(post),
                "upvotes": post.get("score", 0),
                "rat_poison": is_rat_poison(post),
            }

            if entry["rat_poison"]:
                findings["rat_poison_flagged"].append(entry)
                poison_count += 1
            else:
                findings["relevant"].append(entry)
                relevant_count += 1

        findings["stats"][sub] = {
            "posts_checked": len(posts),
            "relevant": relevant_count,
            "rat_poison_flagged": poison_count,
        }

        # Be a polite citizen — don't hammer Reddit
        if not dry_run and sub != SUBREDDITS[-1]:
            time.sleep(2)

    # Sort relevant by upvotes descending
    findings["relevant"].sort(key=lambda x: x["upvotes"], reverse=True)

    return findings


def save_findings(findings: dict) -> Path:
    """Write findings to a dated JSON file in research/findings/."""
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = FINDINGS_DIR / f"{date_str}.json"

    # If a file already exists today, merge (don't overwrite earlier run)
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text())
            existing_ideas = {e["idea"] for e in existing.get("relevant", [])}
            new_entries = [e for e in findings["relevant"] if e["idea"] not in existing_ideas]
            existing["relevant"].extend(new_entries)
            existing["relevant"].sort(key=lambda x: x["upvotes"], reverse=True)
            findings = existing
        except (json.JSONDecodeError, KeyError):
            pass  # overwrite if corrupt

    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(findings, indent=2))
    tmp.replace(out_path)
    return out_path


def format_summary(findings: dict) -> str:
    """Human-readable summary of findings."""
    lines = ["", "=== Reddit Scout Findings ==="]
    lines.append(f"Generated: {findings['generated_at']}")
    lines.append(f"Subreddits: {', '.join(findings['subreddits_checked'])}")
    lines.append("")

    by_frontier: dict[str, list] = {}
    for entry in findings["relevant"]:
        f = entry["frontier"]
        by_frontier.setdefault(f, []).append(entry)

    for frontier, entries in sorted(by_frontier.items()):
        lines.append(f"--- {frontier} ({len(entries)} signals) ---")
        for e in entries[:5]:  # top 5 per frontier
            lines.append(f"  [{e['subreddit']}] {e['idea']}")
        lines.append("")

    if findings["rat_poison_flagged"]:
        lines.append(f"--- RAT POISON FLAGGED ({len(findings['rat_poison_flagged'])} posts) ---")
        lines.append("  These were logged but flagged — do not act on them.")
        for e in findings["rat_poison_flagged"][:3]:
            lines.append(f"  [{e['subreddit']}] {e['idea']}")
        lines.append("")

    total = sum(s["posts_checked"] for s in findings["stats"].values())
    relevant = sum(s["relevant"] for s in findings["stats"].values())
    lines.append(f"Checked {total} posts. Found {relevant} relevant signals.")
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reddit Scout for ClaudeCodeAdvancements")
    parser.add_argument("--dry-run", action="store_true", help="Print findings, don't save")
    parser.add_argument("--summary", action="store_true", help="Print most recent findings file")
    args = parser.parse_args()

    if args.summary:
        files = sorted(FINDINGS_DIR.glob("*.json"), reverse=True)
        if not files:
            print("No findings yet. Run without --summary first.")
            return
        findings = json.loads(files[0].read_text())
        print(format_summary(findings))
        return

    findings = run_scout(dry_run=args.dry_run)

    if args.dry_run:
        print(format_summary(findings))
    else:
        out_path = save_findings(findings)
        print(format_summary(findings))
        print(f"\n[scout] Saved to {out_path}")


if __name__ == "__main__":
    main()
