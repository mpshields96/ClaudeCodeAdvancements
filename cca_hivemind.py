#!/usr/bin/env python3
"""
cca_hivemind.py — Multi-Chat Orchestrator and Coordinator

Enables a hivemind workflow where one Claude Code chat can:
1. Detect all active Claude sessions (ps-based)
2. Classify them by project (CCA, Kalshi, unknown)
3. Send directives via queue (async — picked up on next hook fire)
4. Inject messages directly into Terminal.app windows (AppleScript)
5. Report status of all sessions and queues

This is the coordination brain. Individual chats are the workers.

Usage:
    python3 cca_hivemind.py status         # Show all sessions + queue state
    python3 cca_hivemind.py send <target> <message>  # Send via queue
    python3 cca_hivemind.py inject <window> <message> # Direct Terminal injection
    python3 cca_hivemind.py assign <target> <task>    # Queue a task assignment

Safety:
    - Injection text is validated against dangerous patterns
    - No credential content allowed in injections
    - No destructive commands (rm -rf, DROP TABLE, etc.)
    - Injection is keyboard simulation — the other Claude sees it as user input

Stdlib only. No external dependencies.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INTERNAL_PATH = os.path.join(SCRIPT_DIR, "cca_internal_queue.jsonl")
DEFAULT_CROSS_PATH = os.path.join(SCRIPT_DIR, "cross_chat_queue.jsonl")

# Dangerous patterns that must never be injected
DANGEROUS_PATTERNS = [
    re.compile(r'rm\s+-rf\s+/', re.IGNORECASE),
    re.compile(r'DROP\s+TABLE', re.IGNORECASE),
    re.compile(r'DROP\s+DATABASE', re.IGNORECASE),
    re.compile(r'curl\s+.*\|\s*bash', re.IGNORECASE),
    re.compile(r'wget\s+.*\|\s*bash', re.IGNORECASE),
    re.compile(r'curl\s+.*\|\s*sh', re.IGNORECASE),
    re.compile(r'mkfs\b', re.IGNORECASE),
    re.compile(r'dd\s+if=', re.IGNORECASE),
    re.compile(r':\(\)\s*\{', re.IGNORECASE),  # fork bomb
    re.compile(r'>\s*/dev/sd[a-z]', re.IGNORECASE),
    re.compile(r'sk-[A-Za-z0-9\-]{20,}'),  # Anthropic API keys
    re.compile(r'export\s+\w*(KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)\w*\s*=', re.IGNORECASE),
]


# --- Process Detection ---

def parse_claude_processes(ps_lines: List[str]) -> List[dict]:
    """Parse ps output lines to find Claude Code processes.

    Expects lines like: "501 12345 claude --model opus"
    """
    processes = []
    for line in ps_lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[1])
        except (ValueError, IndexError):
            continue
        cmdline = parts[2] if len(parts) > 2 else ""
        model = "unknown"
        if "--model" in cmdline:
            model_match = re.search(r'--model\s+(\w+)', cmdline)
            if model_match:
                model = model_match.group(1)
        processes.append({
            "pid": pid,
            "cmdline": cmdline,
            "model": model,
        })
    return processes


def classify_session(cwd: str, cmdline: str = "") -> str:
    """Classify a session by its working directory."""
    if "ClaudeCodeAdvancements" in cwd:
        return "cca"
    elif "polymarket-bot" in cwd:
        return "kalshi"
    return "unknown"


def detect_active_sessions() -> List[dict]:
    """Detect all active Claude Code sessions on this machine."""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=5
        )
        sessions = []
        for line in result.stdout.splitlines():
            if "claude" in line.lower() and "--model" in line:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    pid = int(parts[1])
                    cmdline = parts[10]
                    # Try to get cwd
                    cwd = ""
                    try:
                        lsof = subprocess.run(
                            ["lsof", "-p", str(pid), "-Fn"],
                            capture_output=True, text=True, timeout=3
                        )
                        for l in lsof.stdout.splitlines():
                            if l.startswith("n/") and "Projects" in l:
                                cwd = l[1:]
                                break
                    except (subprocess.TimeoutExpired, OSError):
                        pass

                    project = classify_session(cwd, cmdline)
                    model = "unknown"
                    m = re.search(r'--model\s+(\w+)', cmdline)
                    if m:
                        model = m.group(1)

                    sessions.append({
                        "pid": pid,
                        "project": project,
                        "model": model,
                        "cwd": cwd,
                        "cmdline": cmdline,
                    })
        return sessions
    except (subprocess.TimeoutExpired, OSError):
        return []


# --- Injection ---

def validate_injection_text(text: str) -> bool:
    """Validate that injection text is safe.

    Returns False if text contains dangerous patterns.
    """
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(text):
            return False
    return True


def build_injection_text(
    directive: str,
    from_chat: str = "hivemind",
    priority: str = "medium",
    context: str = "",
) -> str:
    """Build text suitable for injection into another chat session.

    The text appears as if the user typed it — the other Claude
    interprets it as a user message.
    """
    lines = [
        f"[HIVEMIND DIRECTIVE from {from_chat} — {priority.upper()}]",
        directive,
    ]
    if context:
        lines.append(f"Context: {context}")
    lines.append(
        "Check internal queue for details: python3 cca_internal_queue.py unread --for <your_id>"
    )
    return "\n".join(lines)


def generate_terminal_injection_script(
    text: str,
    window_index: int = 1,
) -> str:
    """Generate AppleScript to type text into a Terminal.app window.

    Uses keystroke simulation — the text appears as if typed by the user.
    Window index 1 = frontmost, 2 = second, etc.
    """
    # Escape for AppleScript string
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    # Replace newlines with return keystrokes
    escaped = escaped.replace("\n", "\\n")

    return f'''tell application "Terminal"
    activate
    set targetWindow to window {window_index}
    do script "" in targetWindow
    delay 0.1
    tell application "System Events"
        tell process "Terminal"
            keystroke "{escaped}"
            keystroke return
        end tell
    end tell
end tell'''


def list_terminal_windows() -> List[dict]:
    """List Terminal.app windows with index, title, and activity hints.

    Returns list of dicts with window_index, title, activity_hint.
    Activity hints are parsed from the window title (e.g. "Python", "caffeinate").
    """
    script = '''tell application "Terminal"
    set windowInfo to ""
    repeat with i from 1 to count of windows
        set w to window i
        set windowInfo to windowInfo & i & "|" & name of w & linefeed
    end repeat
    return windowInfo
end tell'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5
        )
        windows = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 1)
            if len(parts) == 2:
                idx = int(parts[0])
                title = parts[1]
                # Extract activity hint from title
                # Title format: "user — ⠂ Claude Code — <activity> ◂ claude ..."
                activity = "unknown"
                if "Claude Code" in title:
                    # Parse between "Claude Code — " and " ◂"
                    m = re.search(r'Claude Code\s*[—-]\s*(.+?)\s*◂', title)
                    if m:
                        activity = m.group(1).strip()
                windows.append({
                    "window_index": idx,
                    "title": title,
                    "activity": activity,
                    "is_claude": "claude" in title.lower(),
                })
        return windows
    except (subprocess.TimeoutExpired, OSError):
        return []


def discover_windows() -> str:
    """Discover and describe all Terminal.app windows.

    Returns a formatted report. Window indices are EPHEMERAL —
    they change as windows are opened, closed, or reordered.
    Always re-discover before targeting a window.
    """
    windows = list_terminal_windows()
    if not windows:
        return "No Terminal windows found (may need accessibility permissions)."

    lines = ["TERMINAL WINDOWS (indices are ephemeral — re-discover before each ping):"]
    claude_count = 0
    for w in windows:
        marker = "*" if w["is_claude"] else " "
        lines.append(
            f"  {marker} Window {w['window_index']}: "
            f"activity={w['activity']}"
        )
        if w["is_claude"]:
            claude_count += 1

    lines.append(f"\n{claude_count} Claude session(s) detected in Terminal.")
    lines.append("Use 'hivemind ping <target> <window#>' to message a specific window.")
    lines.append("IMPORTANT: Re-run 'discover' before each ping — window order shifts.")
    return "\n".join(lines)


# --- Queue Integration ---

def send_directive(
    target_internal: str,
    subject: str,
    body: str = "",
    priority: str = "medium",
    from_chat: str = "desktop",
    queue_path: str = DEFAULT_INTERNAL_PATH,
) -> dict:
    """Send a directive via the internal queue.

    This is the SAFE way to communicate — async, through the queue.
    The target chat picks it up on its next hook fire.
    """
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    content_hash = hashlib.sha256(
        f"{from_chat}:{subject}:{ts}".encode()
    ).hexdigest()[:8]
    msg_id = f"cca_{ts.replace('-', '').replace(':', '').replace('.', '_')}_{content_hash}"

    msg = {
        "id": msg_id,
        "sender": from_chat,
        "target": target_internal,
        "subject": subject,
        "body": body,
        "priority": priority,
        "category": "handoff",
        "status": "unread",
        "created_at": ts,
    }

    with open(queue_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, separators=(",", ":")) + "\n")

    return msg


# --- Status Report ---

def _load_unread_summary(path: str) -> dict:
    """Load unread counts per target from a queue file."""
    summary = {}
    if not os.path.exists(path):
        return summary
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("status") == "unread":
                        target = msg.get("target", "?")
                        if target not in summary:
                            summary[target] = {"total": 0}
                        summary[target]["total"] += 1
                        p = msg.get("priority", "medium")
                        summary[target][p] = summary[target].get(p, 0) + 1
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return summary


def format_status_report(
    sessions: List[dict],
    queue_summary: dict,
    internal_summary: dict,
) -> str:
    """Format a hivemind status report."""
    lines = ["=== CCA Hivemind Status ===", ""]

    # Sessions
    if sessions:
        lines.append(f"ACTIVE SESSIONS ({len(sessions)}):")
        for s in sessions:
            lines.append(
                f"  PID {s.get('pid', '?')} | "
                f"{s.get('project', 'unknown')} | "
                f"model={s.get('model', '?')}"
            )
    else:
        lines.append("No active Claude sessions detected.")
    lines.append("")

    # Cross-chat queue
    if queue_summary:
        lines.append("CROSS-CHAT QUEUE:")
        for target, counts in queue_summary.items():
            parts = [f"{counts['total']} unread"]
            for p in ["critical", "high", "medium", "low"]:
                if p in counts and counts[p] > 0:
                    parts.append(f"{counts[p]} {p}")
            lines.append(f"  {target}: {', '.join(parts)}")
    else:
        lines.append("Cross-chat queue: empty")
    lines.append("")

    # Internal queue
    if internal_summary:
        lines.append("INTERNAL QUEUE:")
        for target, counts in internal_summary.items():
            parts = [f"{counts['total']} unread"]
            for p in ["critical", "high", "medium", "low"]:
                if p in counts and counts[p] > 0:
                    parts.append(f"{counts[p]} {p}")
            lines.append(f"  {target}: {', '.join(parts)}")
    else:
        lines.append("Internal queue: empty")

    return "\n".join(lines)


# --- CLI ---

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 cca_hivemind.py {status|send|inject|assign|ping|windows}")
        print("")
        print("Commands:")
        print("  status                    Show all sessions + queue state")
        print("  send <target> <message>   Send directive via internal queue")
        print("  inject <window#> <text>   Inject text into Terminal window (AppleScript)")
        print("  assign <target> <task>    Queue a task assignment")
        print("  ping <target> <window#>   Queue message + poke Terminal window")
        print("  windows                   List Terminal.app windows for targeting")
        print("  discover                  Identify Claude windows with activity hints")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "status":
        sessions = detect_active_sessions()
        cross = _load_unread_summary(DEFAULT_CROSS_PATH)
        internal = _load_unread_summary(DEFAULT_INTERNAL_PATH)
        print(format_status_report(sessions, cross, internal))

    elif cmd == "send":
        if len(sys.argv) < 4:
            print("Usage: send <target> <message>")
            sys.exit(1)
        target = sys.argv[2]
        message = " ".join(sys.argv[3:])
        msg = send_directive(target, subject=message, from_chat="hivemind")
        print(f"Sent to {target}: {msg['id']}")

    elif cmd == "inject":
        if len(sys.argv) < 4:
            print("Usage: inject <window_index> <text>")
            sys.exit(1)
        window = int(sys.argv[2])
        text = " ".join(sys.argv[3:])
        if not validate_injection_text(text):
            print("BLOCKED: Injection text contains dangerous patterns.")
            sys.exit(1)
        script = generate_terminal_injection_script(text, window)
        print(f"Generated AppleScript for window {window}:")
        print(script)
        print("\nTo execute: osascript -e '<script>'")
        print("(Not auto-executing for safety — review the script first)")

    elif cmd == "assign":
        if len(sys.argv) < 4:
            print("Usage: assign <target> <task_description>")
            sys.exit(1)
        target = sys.argv[2]
        task = " ".join(sys.argv[3:])
        msg = send_directive(
            target, subject=task, from_chat="hivemind", priority="high",
            body=f"Task assigned by hivemind at {datetime.now(timezone.utc).isoformat()}"
        )
        print(f"Assigned to {target}: {msg['id']}")
        print(f"  Task: {task}")

    elif cmd == "ping":
        if len(sys.argv) < 4:
            print("Usage: ping <target> <window_index>")
            print("  Sends queue message + pokes Terminal window with 'check queue'")
            sys.exit(1)
        target = sys.argv[2]
        window = int(sys.argv[3])
        message = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else "New hivemind directive — check your queue"
        # Step 1: Send via queue
        msg = send_directive(target, subject=message, from_chat="hivemind", priority="high")
        print(f"Queued: {msg['id']}")
        # Step 2: Poke the terminal window
        ping_text = f"[HIVEMIND PING] Check queue: python3 cca_internal_queue.py unread --for {target}"
        if not validate_injection_text(ping_text):
            print("BLOCKED: ping text failed validation")
            sys.exit(1)
        script = generate_terminal_injection_script(ping_text, window)
        try:
            subprocess.run(
                ["osascript", "-e", script],
                timeout=5, capture_output=True
            )
            print(f"Pinged Terminal window {window}")
        except (subprocess.TimeoutExpired, OSError) as e:
            print(f"Ping failed (queue message still sent): {e}")

    elif cmd == "discover":
        print(discover_windows())

    elif cmd == "windows":
        # List Terminal.app windows
        script = '''tell application "Terminal"
    set windowList to ""
    repeat with i from 1 to count of windows
        set w to window i
        set windowList to windowList & i & ": " & name of w & linefeed
    end repeat
    return windowList
end tell'''
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                print("Terminal.app windows:")
                print(result.stdout)
            else:
                print("No Terminal windows found.")
        except (subprocess.TimeoutExpired, OSError):
            print("Could not query Terminal.app (may need accessibility permissions)")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
