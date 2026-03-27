#!/usr/bin/env python3
"""
subreddit_scanner.py — Full subreddit absorption tool

Paginates through the Reddit JSON API (100 posts/page) to fetch ALL posts
in a subreddit, with filtering, sorting, and export capabilities.

Usage:
    python3 subreddit_scanner.py scan r/ClaudePlaysPokemon
    python3 subreddit_scanner.py scan r/ClaudePlaysPokemon --sort top --min-score 10
    python3 subreddit_scanner.py scan r/ClaudePlaysPokemon --exclude "shitpost,song,meme"
    python3 subreddit_scanner.py scan r/ClaudePlaysPokemon --output results.json
    python3 subreddit_scanner.py read r/ClaudePlaysPokemon post123

Stdlib only — no external dependencies.
"""

import sys
import json
import re
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Optional

HEADERS = {"User-Agent": "ClaudeCodeScanner/1.0 (ClaudeCodeAdvancements; read-only)"}
API_BASE = "https://www.reddit.com"
MAX_PER_PAGE = 100
# Reddit rate limit: ~1 request per second for unauthenticated
RATE_LIMIT_DELAY = 1.2


@dataclass
class PostSummary:
    """Lightweight summary of a Reddit post."""
    id: str
    title: str
    author: str
    score: int
    num_comments: int
    created_utc: float
    permalink: str
    subreddit: str
    is_self: bool
    selftext: str
    url: str
    flair: Optional[str]
    upvote_ratio: float

    def full_url(self) -> str:
        return f"https://www.reddit.com{self.permalink}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PostSummary":
        return cls(**d)


@dataclass
class ScanResult:
    """Result of a full subreddit scan."""
    subreddit: str
    total_posts: int
    posts: list
    pages_fetched: int

    def post_urls(self) -> list:
        return [p.full_url() for p in self.posts]

    def save(self, path: str):
        data = {
            "subreddit": self.subreddit,
            "total_posts": self.total_posts,
            "pages_fetched": self.pages_fetched,
            "posts": [p.to_dict() for p in self.posts],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "ScanResult":
        with open(path) as f:
            data = json.load(f)
        posts = [PostSummary.from_dict(p) for p in data["posts"]]
        return cls(
            subreddit=data["subreddit"],
            total_posts=data["total_posts"],
            posts=posts,
            pages_fetched=data["pages_fetched"],
        )


def build_listing_url(subreddit: str, sort: str = "hot", limit: int = 100,
                      timeframe: str = "", after: Optional[str] = None) -> str:
    """Build a Reddit JSON API listing URL with pagination support."""
    limit = min(limit, MAX_PER_PAGE)
    url = f"{API_BASE}/r/{subreddit}/{sort}.json?limit={limit}&raw_json=1"
    if sort == "top" and timeframe:
        url += f"&t={timeframe}"
    if after:
        url += f"&after={after}"
    return url


def fetch_json(url: str) -> dict:
    """Fetch URL and parse JSON. Handles rate limiting."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"  Rate limited — waiting 5s...", file=sys.stderr)
            time.sleep(5)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        raise


def parse_listing_response(data: dict) -> tuple:
    """Parse a Reddit listing response into (posts, after_token)."""
    children = data.get("data", {}).get("children", [])
    after_token = data.get("data", {}).get("after")

    posts = []
    for item in children:
        if item.get("kind") != "t3":
            continue
        d = item.get("data", {})
        posts.append(PostSummary(
            id=d.get("id", ""),
            title=d.get("title", ""),
            author=d.get("author") or "[deleted]",
            score=d.get("score", 0),
            num_comments=d.get("num_comments", 0),
            created_utc=d.get("created_utc", 0),
            permalink=d.get("permalink", ""),
            subreddit=d.get("subreddit", ""),
            is_self=d.get("is_self", True),
            selftext=d.get("selftext", ""),
            url=d.get("url", ""),
            flair=d.get("link_flair_text"),
            upvote_ratio=d.get("upvote_ratio", 0),
        ))

    return posts, after_token


def filter_posts(posts: list, min_score: int = 0,
                 exclude_flairs: Optional[list] = None,
                 exclude_title_patterns: Optional[list] = None) -> list:
    """Filter posts by score, flair, and title patterns."""
    exclude_flairs = [f.lower() for f in (exclude_flairs or [])]
    exclude_patterns = [p.lower() for p in (exclude_title_patterns or [])]

    filtered = []
    for p in posts:
        if p.score < min_score:
            continue
        if p.flair and p.flair.lower() in exclude_flairs:
            continue
        title_lower = p.title.lower()
        if any(pat in title_lower for pat in exclude_patterns):
            continue
        filtered.append(p)

    return filtered


def format_post_table(posts: list, subreddit: str = "", sort_by: str = "score") -> str:
    """Format posts as a readable ranked table."""
    if sort_by == "score":
        sorted_posts = sorted(posts, key=lambda p: p.score, reverse=True)
    elif sort_by == "comments":
        sorted_posts = sorted(posts, key=lambda p: p.num_comments, reverse=True)
    elif sort_by == "date":
        sorted_posts = sorted(posts, key=lambda p: p.created_utc, reverse=True)
    else:
        sorted_posts = posts

    lines = []
    if subreddit:
        lines.append(f"r/{subreddit} — {len(sorted_posts)} posts (sorted by {sort_by})")
        lines.append("")

    for i, p in enumerate(sorted_posts, 1):
        flair_str = f" [{p.flair}]" if p.flair else ""
        link_str = f" [link]" if not p.is_self else ""
        lines.append(f"{i:3d}. [{p.score:3d}pts, {p.num_comments:3d}c] {p.title[:90]}{flair_str}{link_str}")
        lines.append(f"     u/{p.author} | {p.full_url()}")

    return "\n".join(lines)


def scan_subreddit(subreddit: str, sort: str = "new", timeframe: str = "all",
                   max_pages: int = 20, verbose: bool = True) -> ScanResult:
    """Scan an entire subreddit by paginating through the JSON API.

    Args:
        subreddit: Subreddit name (without r/ prefix)
        sort: Sort order — new, hot, top, rising
        timeframe: For top sort — hour, day, week, month, year, all
        max_pages: Maximum pages to fetch (100 posts each, default 20 = 2000 posts)
        verbose: Print progress to stderr

    Returns:
        ScanResult with all posts
    """
    all_posts = []
    seen_ids = set()
    after_token = None
    page = 0

    while page < max_pages:
        url = build_listing_url(subreddit, sort=sort, timeframe=timeframe, after=after_token)
        if verbose:
            print(f"  Page {page + 1}: fetching {url[:80]}...", file=sys.stderr)

        try:
            data = fetch_json(url)
        except Exception as e:
            if verbose:
                print(f"  Error on page {page + 1}: {e}", file=sys.stderr)
            break

        posts, after_token = parse_listing_response(data)

        # Deduplicate
        new_posts = [p for p in posts if p.id not in seen_ids]
        for p in new_posts:
            seen_ids.add(p.id)
        all_posts.extend(new_posts)

        page += 1

        if verbose:
            print(f"  Page {page}: got {len(new_posts)} new posts (total: {len(all_posts)})",
                  file=sys.stderr)

        # Stop if no more pages
        if not after_token or len(posts) == 0:
            if verbose:
                print(f"  No more pages — scan complete.", file=sys.stderr)
            break

        # Rate limit
        time.sleep(RATE_LIMIT_DELAY)

    return ScanResult(
        subreddit=subreddit,
        total_posts=len(all_posts),
        posts=all_posts,
        pages_fetched=page,
    )


def parse_cli_args(argv: list) -> dict:
    """Parse CLI arguments into a config dict."""
    if not argv:
        return {"mode": "help"}

    mode = argv[0].lower()
    args = {"mode": mode}

    if mode == "scan":
        if len(argv) < 2:
            args["mode"] = "help"
            return args
        sub = argv[1].strip()
        args["subreddit"] = re.sub(r"^/?r/", "", sub)
        args["sort"] = "new"
        args["min_score"] = 0
        args["exclude_patterns"] = []
        args["exclude_flairs"] = []
        args["output"] = None
        args["timeframe"] = "all"
        args["max_pages"] = 20

        i = 2
        while i < len(argv):
            if argv[i] == "--sort" and i + 1 < len(argv):
                args["sort"] = argv[i + 1]
                i += 2
            elif argv[i] == "--min-score" and i + 1 < len(argv):
                args["min_score"] = int(argv[i + 1])
                i += 2
            elif argv[i] == "--exclude" and i + 1 < len(argv):
                args["exclude_patterns"] = [p.strip() for p in argv[i + 1].split(",")]
                i += 2
            elif argv[i] == "--exclude-flairs" and i + 1 < len(argv):
                args["exclude_flairs"] = [f.strip() for f in argv[i + 1].split(",")]
                i += 2
            elif argv[i] == "--output" and i + 1 < len(argv):
                args["output"] = argv[i + 1]
                i += 2
            elif argv[i] == "--timeframe" and i + 1 < len(argv):
                args["timeframe"] = argv[i + 1]
                i += 2
            elif argv[i] == "--max-pages" and i + 1 < len(argv):
                args["max_pages"] = int(argv[i + 1])
                i += 2
            else:
                i += 1

    elif mode == "read":
        if len(argv) >= 3:
            sub = argv[1].strip()
            args["subreddit"] = re.sub(r"^/?r/", "", sub)
            args["post_id"] = argv[2]
        else:
            args["mode"] = "help"

    return args


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    args = parse_cli_args(sys.argv[1:])

    if args["mode"] == "help":
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    if args["mode"] == "scan":
        sub = args["subreddit"]
        print(f"Scanning r/{sub} (sort={args['sort']}, max_pages={args.get('max_pages', 20)})...",
              file=sys.stderr)

        result = scan_subreddit(
            sub,
            sort=args["sort"],
            timeframe=args.get("timeframe", "all"),
            max_pages=args.get("max_pages", 20),
        )

        # Filter
        filtered = filter_posts(
            result.posts,
            min_score=args.get("min_score", 0),
            exclude_flairs=args.get("exclude_flairs", []),
            exclude_title_patterns=args.get("exclude_patterns", []),
        )

        # Output
        if args.get("output"):
            filtered_result = ScanResult(
                subreddit=sub,
                total_posts=len(filtered),
                posts=filtered,
                pages_fetched=result.pages_fetched,
            )
            filtered_result.save(args["output"])
            print(f"\nSaved {len(filtered)} posts to {args['output']}", file=sys.stderr)

        # Always print table to stdout
        print(format_post_table(filtered, subreddit=sub))
        print(f"\n--- Total: {result.total_posts} fetched, {len(filtered)} after filters, "
              f"{result.pages_fetched} pages ---")

    elif args["mode"] == "read":
        # Delegate to reddit_reader for single post reading
        from reddit_reader import read_post
        print(read_post(args["subreddit"], args["post_id"]))


if __name__ == "__main__":
    main()
