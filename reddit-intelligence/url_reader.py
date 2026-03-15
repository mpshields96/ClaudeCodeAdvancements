#!/usr/bin/env python3
"""
url_reader.py — Universal URL reader for Claude Code sessions.
Routes to the best tool per site. No browser needed.

Usage:
    python3 url_reader.py <url>

Routing:
    reddit.com  → reddit_reader.py (JSON API, full comments)
    youtube.com → yt-dlp (transcript extraction with timestamps)
    everything  → defuddle (clean article extraction, strips ads/nav)

Dependencies:
    - reddit_reader.py (bundled, stdlib-only)
    - defuddle (npm install -g defuddle)
    - yt-dlp (brew install yt-dlp)
"""

import sys
import os
import subprocess
import json
import re
import shutil
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def is_reddit(url):
    return "reddit.com" in url or url.startswith("r/")


def is_youtube(url):
    return any(x in url for x in ["youtube.com/watch", "youtu.be/", "youtube.com/shorts"])


def read_reddit(url):
    """Route to reddit_reader.py for full post + comments."""
    reader = os.path.join(SCRIPT_DIR, "reddit_reader.py")
    result = subprocess.run(
        [sys.executable, reader, url],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return f"REDDIT READER ERROR: {result.stderr.strip()}"
    return result.stdout


def read_youtube(url):
    """Extract YouTube transcript via yt-dlp, return formatted text."""
    if not shutil.which("yt-dlp"):
        return "ERROR: yt-dlp not installed. Run: brew install yt-dlp"

    # Get video title
    title_result = subprocess.run(
        ["yt-dlp", "--print", "%(title)s", "--skip-download", url],
        capture_output=True, text=True, timeout=30
    )
    title = title_result.stdout.strip() if title_result.returncode == 0 else "Unknown"

    # Get channel
    channel_result = subprocess.run(
        ["yt-dlp", "--print", "%(channel)s", "--skip-download", url],
        capture_output=True, text=True, timeout=30
    )
    channel = channel_result.stdout.strip() if channel_result.returncode == 0 else "Unknown"

    # Get description
    desc_result = subprocess.run(
        ["yt-dlp", "--print", "%(description)s", "--skip-download", url],
        capture_output=True, text=True, timeout=30
    )
    description = desc_result.stdout.strip() if desc_result.returncode == 0 else ""

    # Download subtitles
    with tempfile.TemporaryDirectory() as tmpdir:
        sub_path = os.path.join(tmpdir, "subs")
        result = subprocess.run(
            ["yt-dlp", "--write-sub", "--write-auto-sub", "--sub-lang", "en",
             "--skip-download", "--sub-format", "json3", "-o", sub_path, url],
            capture_output=True, text=True, timeout=60
        )

        sub_file = sub_path + ".en.json3"
        if not os.path.exists(sub_file):
            # Try without manual subs
            sub_files = [f for f in os.listdir(tmpdir) if f.endswith(".json3")]
            if sub_files:
                sub_file = os.path.join(tmpdir, sub_files[0])
            else:
                return (
                    f"URL: {url}\n"
                    f"TITLE: {title}\n"
                    f"CHANNEL: {channel}\n\n"
                    f"DESCRIPTION:\n{description[:2000]}\n\n"
                    "TRANSCRIPT: Not available (no captions found)"
                )

        with open(sub_file) as f:
            data = json.load(f)

        events = data.get("events", [])
        lines = []
        seen = set()
        for e in events:
            segs = e.get("segs", [])
            text = "".join(s.get("utf8", "") for s in segs).strip()
            text = re.sub(r"\s+", " ", text)
            if not text or text == "\n" or text in seen:
                continue
            seen.add(text)
            ts = e.get("tStartMs", 0) // 1000
            mins, secs = divmod(ts, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                lines.append(f"[{hours}:{mins:02d}:{secs:02d}] {text}")
            else:
                lines.append(f"[{mins}:{secs:02d}] {text}")

    transcript = "\n".join(lines)

    return (
        f"URL: {url}\n"
        f"TITLE: {title}\n"
        f"CHANNEL: {channel}\n\n"
        f"DESCRIPTION:\n{description[:2000]}\n\n"
        f"--- TRANSCRIPT ({len(lines)} lines) ---\n\n"
        f"{transcript}"
    )


def read_webpage(url):
    """Use defuddle to extract clean article content."""
    if not shutil.which("defuddle"):
        return f"ERROR: defuddle not installed. Run: npm install -g defuddle\nFalling back to raw URL: {url}"

    result = subprocess.run(
        ["defuddle", "parse", url, "--markdown"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return f"DEFUDDLE ERROR: {result.stderr.strip()}\nURL: {url}"

    content = result.stdout.strip()
    if not content:
        return f"DEFUDDLE: No content extracted from {url}"

    return f"URL: {url}\n\n{content}"


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1].strip()

    try:
        if is_reddit(url):
            print(read_reddit(url))
        elif is_youtube(url):
            print(read_youtube(url))
        else:
            print(read_webpage(url))
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: Request took too long for {url}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
