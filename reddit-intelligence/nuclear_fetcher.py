#!/usr/bin/env python3
"""
nuclear_fetcher.py — Fetch top N posts from a subreddit for batch /cca-review.
Stdlib only. No Claude tokens consumed.

Usage:
    python3 nuclear_fetcher.py r/ClaudeCode 150 year
    python3 nuclear_fetcher.py r/ClaudeCode 100 year --output posts.json
    python3 nuclear_fetcher.py r/ClaudeCode 150 year --min-score 50
    python3 nuclear_fetcher.py r/ClaudeCode 150 year --dedup findings.log

Outputs JSON array of post metadata, sorted by score descending.
"""

import sys
import json
import time
import urllib.request
import argparse
import os
import re

HEADERS = {"User-Agent": "ClaudeCodeReader/2.0 (NuclearScan; read-only)"}
API_BASE = "https://www.reddit.com"
PAGE_SIZE = 100  # Reddit max per request


def fetch_json(url):
    """Fetch URL and parse JSON. Respects rate limits."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_top_posts(subreddit, limit=150, timeframe="year"):
    """
    Paginate through /top?t=<timeframe> collecting post metadata.
    Returns list of dicts sorted by score descending.
    """
    posts = []
    after = None
    pages = 0
    max_pages = (limit // PAGE_SIZE) + 2  # Safety cap

    while len(posts) < limit and pages < max_pages:
        url = f"{API_BASE}/r/{subreddit}/top.json?t={timeframe}&limit={PAGE_SIZE}"
        if after:
            url += f"&after={after}"

        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"ERROR fetching page {pages + 1}: {e}", file=sys.stderr)
            break

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        for item in children:
            d = item.get("data", {})
            posts.append({
                "id": d.get("id", ""),
                "title": d.get("title", ""),
                "author": d.get("author") or "[deleted]",
                "score": d.get("score", 0),
                "upvote_ratio": d.get("upvote_ratio", 0),
                "num_comments": d.get("num_comments", 0),
                "created_utc": d.get("created_utc", 0),
                "flair": d.get("link_flair_text") or "",
                "is_self": d.get("is_self", True),
                "url": d.get("url", ""),
                "permalink": f"https://www.reddit.com{d.get('permalink', '')}",
                "selftext_length": len(d.get("selftext") or ""),
                "subreddit": d.get("subreddit", subreddit),
            })

        after = data.get("data", {}).get("after")
        if not after:
            break

        pages += 1
        time.sleep(1.0)  # Respect rate limits

    # Sort by score descending, truncate to limit
    posts.sort(key=lambda p: p["score"], reverse=True)
    return posts[:limit]


def load_findings_urls(findings_path):
    """Extract all URLs from FINDINGS_LOG.md for deduplication."""
    urls = set()
    if not os.path.exists(findings_path):
        return urls
    with open(findings_path, "r") as f:
        for line in f:
            # Extract reddit URLs from findings entries
            for match in re.finditer(r"https://www\.reddit\.com/r/\w+/comments/(\w+)", line):
                urls.add(match.group(1))
    return urls


def classify_post(post):
    """
    Fast triage: classify post as NEEDLE, MAYBE, or HAY.

    NEEDLE = high signal, definitely read (high score + substantive)
    MAYBE = worth a quick scan of title/body
    HAY = almost certainly skip (memes, low effort, off-topic)
    """
    title_lower = post["title"].lower()
    score = post["score"]
    comments = post["num_comments"]
    flair = (post.get("flair") or "").lower()
    is_self = post["is_self"]
    body_len = post.get("selftext_length", 0)

    # HAY patterns — almost always trash for our purposes
    hay_keywords = [
        "meme", "humor", "funny", "lmao", "lol", "rant", "unpopular opinion",
        "am i the only", "does anyone else", "shower thought", "hot take",
        "goodbye claude", "switching to", "cancelling", "canceled my sub",
        "pricing", "rate limit", "how much do you spend", "api cost",
        "gpt vs claude", "gemini vs", "copilot vs", "cursor vs",
        "jailbreak", "bypass", "prompt injection",
        "first time using", "just discovered", "eli5",
    ]

    # NEEDLE patterns — high-signal keywords
    needle_keywords = [
        "claude.md", "claudemd", "hook", "mcp server", "mcp tool",
        "workflow", "automation", "multi-agent", "parallel agent",
        "context window", "context rot", "compaction", "token",
        "memory", "persistent", "cross-session", "session management",
        "spec", "architecture", "design doc", "requirements",
        "file locking", "conflict", "credential", "security",
        "dashboard", "monitor", "statusline", "usage",
        "tool", "built", "made", "created", "open source",
        "tips", "tricks", "best practice", "workflow", "setup",
        "tmux", "terminal", "cli", "tui",
        "self-evolving", "self-learning", "autonomous", "agent",
    ]

    # Flair-based classification
    hay_flairs = ["humor", "meme", "rant", "meta"]
    needle_flairs = ["tutorial / guide", "showcase", "tool", "discussion"]

    # Check HAY
    if flair in hay_flairs:
        return "HAY"
    if any(kw in title_lower for kw in hay_keywords):
        return "HAY"
    if not is_self and body_len == 0 and score < 200:
        # Link post with no body and moderate score — likely image/meme
        return "HAY"

    # Check NEEDLE
    if flair in needle_flairs and score >= 100:
        return "NEEDLE"
    if any(kw in title_lower for kw in needle_keywords):
        return "NEEDLE"
    if is_self and body_len > 500 and score >= 100:
        # Substantive self-post with good score
        return "NEEDLE"
    if comments >= 50 and score >= 150:
        # High engagement
        return "NEEDLE"

    return "MAYBE"


def subreddit_slug(subreddit):
    """Convert subreddit name to filesystem-safe slug for file naming.

    Examples:
        r/ClaudeCode -> claudecode
        ClaudeAI -> claudeai
        r/LocalLLaMA -> localllama
    """
    sub = re.sub(r"^/?r/", "", subreddit.strip()).lower()
    return re.sub(r"[^a-z0-9]", "", sub)


def main():
    parser = argparse.ArgumentParser(description="Fetch top Reddit posts for batch review")
    parser.add_argument("subreddit", help="Subreddit (e.g., r/ClaudeCode)")
    parser.add_argument("limit", type=int, nargs="?", default=150, help="Number of posts to fetch")
    parser.add_argument("timeframe", nargs="?", default="year",
                        choices=["hour", "day", "week", "month", "year", "all"],
                        help="Time range for top sort")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--min-score", type=int, default=0, help="Minimum score filter")
    parser.add_argument("--dedup", help="Path to FINDINGS_LOG.md for deduplication")
    parser.add_argument("--classify", action="store_true",
                        help="Add NEEDLE/MAYBE/HAY classification to each post")
    parser.add_argument("--summary", action="store_true",
                        help="Print human-readable summary instead of JSON")

    args = parser.parse_args()

    sub = re.sub(r"^/?r/", "", args.subreddit.strip())

    print(f"Fetching top {args.limit} posts from r/{sub} (t={args.timeframe})...", file=sys.stderr)
    posts = fetch_top_posts(sub, args.limit, args.timeframe)
    print(f"Fetched {len(posts)} posts", file=sys.stderr)

    # Apply min-score filter
    if args.min_score > 0:
        before = len(posts)
        posts = [p for p in posts if p["score"] >= args.min_score]
        print(f"Score filter (>={args.min_score}): {before} -> {len(posts)}", file=sys.stderr)

    # Dedup against FINDINGS_LOG
    if args.dedup:
        known_ids = load_findings_urls(args.dedup)
        before = len(posts)
        for p in posts:
            p["already_reviewed"] = p["id"] in known_ids
        deduped = [p for p in posts if not p.get("already_reviewed")]
        print(f"Dedup vs FINDINGS_LOG: {before} -> {len(deduped)} new ({before - len(deduped)} already reviewed)",
              file=sys.stderr)
        posts = deduped

    # Classify
    if args.classify:
        for p in posts:
            p["triage"] = classify_post(p)
        needles = sum(1 for p in posts if p["triage"] == "NEEDLE")
        maybes = sum(1 for p in posts if p["triage"] == "MAYBE")
        hay = sum(1 for p in posts if p["triage"] == "HAY")
        print(f"Classification: {needles} NEEDLE, {maybes} MAYBE, {hay} HAY", file=sys.stderr)

    # Output
    if args.summary:
        print(f"\nr/{sub} — TOP {args.timeframe.upper()} — {len(posts)} posts\n")
        for i, p in enumerate(posts, 1):
            triage = f" [{p['triage']}]" if "triage" in p else ""
            flair_str = f" [{p['flair']}]" if p.get("flair") else ""
            print(f"{i:3d}. [{p['score']:4d} pts | {p['num_comments']:3d} comments]{triage}{flair_str}")
            print(f"     {p['title'][:100]}")
            print(f"     {p['permalink']}")
            print()
    else:
        output = json.dumps(posts, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"Written to {args.output}", file=sys.stderr)
        else:
            print(output)


if __name__ == "__main__":
    main()
