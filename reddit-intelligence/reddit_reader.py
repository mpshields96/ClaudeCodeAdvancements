#!/usr/bin/env python3
"""
reddit_reader.py — Reddit JSON API reader for Claude Code
No external dependencies — stdlib only (urllib, json, sys, re)

Usage:
    python3 reddit_reader.py <url-or-subreddit> [sort] [limit]

Examples:
    python3 reddit_reader.py r/ClaudeAI
    python3 reddit_reader.py r/ClaudeAI top 10
    python3 reddit_reader.py https://www.reddit.com/r/ClaudeAI/comments/abc123/title/
    python3 reddit_reader.py https://old.reddit.com/r/vibecoding/comments/xyz456/
"""

import sys
import json
import re
import urllib.request

HEADERS = {"User-Agent": "ClaudeCodeReader/1.0 (ClaudeCodeAdvancements; read-only)"}
API_BASE = "https://www.reddit.com"


def fetch_json(url):
    """Fetch URL and parse JSON response. Raises on HTTP errors."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def normalize_url(raw):
    """Normalize old.reddit.com -> www.reddit.com for API calls."""
    return raw.replace("old.reddit.com", "www.reddit.com")


def parse_input(raw):
    """
    Parse a subreddit name or URL into (kind, subreddit, extra).
    kind == 'post'      -> extra is post_id
    kind == 'subreddit' -> extra is sort (hot/new/top/rising)
    """
    raw = raw.strip()

    # Bare subreddit: ClaudeAI or r/ClaudeAI or /r/ClaudeAI
    if not raw.startswith("http"):
        sub = re.sub(r"^/?r/", "", raw)
        return ("subreddit", sub, "hot")

    raw = normalize_url(raw)

    # Post URL: contains /comments/<post_id>
    m = re.search(r"reddit\.com/r/([^/]+)/comments/([a-z0-9]+)", raw, re.IGNORECASE)
    if m:
        return ("post", m.group(1), m.group(2))

    # Subreddit URL: /r/subreddit[/sort]
    m = re.search(r"reddit\.com/r/([^/?#]+)(?:/([^/?#]+))?", raw, re.IGNORECASE)
    if m:
        sub = m.group(1)
        sort_candidate = (m.group(2) or "hot").lower()
        sort = sort_candidate if sort_candidate in ("hot", "new", "top", "rising") else "hot"
        return ("subreddit", sub, sort)

    raise ValueError(f"Cannot parse Reddit input: {raw!r}")


def flatten_comments(children, depth=0, max_depth=10):
    """Recursively flatten comment tree into list of formatted strings."""
    result = []
    if depth > max_depth:
        return result

    for item in children:
        kind = item.get("kind", "")
        if kind == "more":
            # 'more' items require additional API calls — skip for now
            count = item.get("data", {}).get("count", 0)
            if count > 0:
                indent = "  " * depth
                result.append(f"{indent}[... {count} more replies not loaded ...]")
            continue

        if kind != "t1":
            continue

        d = item.get("data", {})
        author = d.get("author") or "[deleted]"
        score = d.get("score", 0)
        body = (d.get("body") or "").strip()

        if body and body not in ("[deleted]", "[removed]"):
            indent = "  " * depth
            body_indented = body.replace("\n", "\n" + indent)
            result.append(f"{indent}[u/{author}] {score} pts\n{indent}{body_indented}")

        replies = d.get("replies", "")
        if isinstance(replies, dict):
            reply_children = replies.get("data", {}).get("children", [])
            result.extend(flatten_comments(reply_children, depth + 1, max_depth))

    return result


def read_post(subreddit, post_id):
    """Fetch a single Reddit post with all comments. Returns formatted string."""
    url = f"{API_BASE}/r/{subreddit}/comments/{post_id}.json?limit=500&depth=10"
    data = fetch_json(url)

    post_data = data[0]["data"]["children"][0]["data"]
    title = post_data.get("title", "")
    author = post_data.get("author") or "[deleted]"
    score = post_data.get("score", 0)
    upvote_ratio = post_data.get("upvote_ratio", 0)
    selftext = (post_data.get("selftext") or "").strip()
    link_url = post_data.get("url", "")
    num_comments = post_data.get("num_comments", 0)
    flair = post_data.get("link_flair_text") or ""
    created = post_data.get("created_utc", 0)
    permalink = f"https://www.reddit.com{post_data.get('permalink', '')}"

    comment_tree = data[1]["data"]["children"]
    comments = flatten_comments(comment_tree)

    lines = [
        f"URL: {permalink}",
        f"SUBREDDIT: r/{subreddit}",
        f"TITLE: {title}",
        f"AUTHOR: u/{author}",
        f"SCORE: {score} ({int(upvote_ratio * 100)}% upvoted)",
        f"COMMENTS: {num_comments} total",
    ]
    if flair:
        lines.append(f"FLAIR: {flair}")
    lines.append("")

    if selftext and selftext not in ("[deleted]", "[removed]"):
        lines.append("POST BODY:")
        lines.append(selftext)
    elif link_url and link_url != permalink:
        lines.append(f"LINK POST: {link_url}")
        lines.append("(no self-text body)")
    else:
        lines.append("(no body text)")

    lines.append("")
    lines.append(f"--- COMMENTS ({len(comments)} loaded of {num_comments} total) ---")
    lines.append("")
    lines.extend(comments)

    return "\n".join(lines)


def read_subreddit(subreddit, sort="hot", limit=25):
    """Fetch post listing for a subreddit. Returns formatted string."""
    url = f"{API_BASE}/r/{subreddit}/{sort}.json?limit={limit}"
    data = fetch_json(url)
    posts = data["data"]["children"]

    lines = [f"r/{subreddit} — {sort.upper()} — {len(posts)} posts\n"]

    for i, item in enumerate(posts, 1):
        d = item.get("data", {})
        title = d.get("title", "")
        author = d.get("author") or "[deleted]"
        score = d.get("score", 0)
        num_comments = d.get("num_comments", 0)
        post_id = d.get("id", "")
        sub = d.get("subreddit", subreddit)
        flair = d.get("link_flair_text") or ""
        permalink = f"https://www.reddit.com/r/{sub}/comments/{post_id}/"
        is_self = d.get("is_self", True)
        external = "" if is_self else f" [link: {d.get('url', '')}]"
        flair_str = f" [{flair}]" if flair else ""

        lines.append(f"{i}. {title}{flair_str}{external}")
        lines.append(f"   u/{author} | {score} pts | {num_comments} comments")
        lines.append(f"   {permalink}")
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    raw = sys.argv[1]

    try:
        kind, sub, extra = parse_input(raw)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if kind == "post":
            print(read_post(sub, extra))
        else:
            sort = sys.argv[2] if len(sys.argv) > 2 else extra
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 25
            print(read_subreddit(sub, sort, limit))
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.reason} — r/{sub} may be private or banned", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"NETWORK ERROR: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"PARSE ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
