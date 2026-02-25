#!/usr/bin/env python3
"""
AG-1: Mobile Approver — PreToolUse hook
Sends a push notification to your iPhone when Claude Code wants to run a
destructive operation. Tap Allow or Deny on your lock screen. Claude waits.

Uses ntfy.sh (free, no account needed for basic use).
Zero external dependencies — Python stdlib only.

Setup (one-time):
  1. Install ntfy app on iPhone: https://apps.apple.com/app/ntfy/id1625396347
  2. export MOBILE_APPROVER_TOPIC=cc-yourname   (pick any unique string)
  3. In ntfy app: tap + and subscribe to that topic
  4. Register this hook in Claude Code settings (see MOBILE_SETUP.md)

Environment variables:
  MOBILE_APPROVER_TOPIC      Required. Your unique ntfy topic name.
  MOBILE_APPROVER_TIMEOUT    Seconds to wait for response (default: 60)
  MOBILE_APPROVER_DEFAULT    Decision on timeout: "allow" or "deny" (default: "allow")
  MOBILE_APPROVER_DISABLED   Set to "1" to disable without removing hook

Run tests: python3 agent-guard/tests/test_mobile_approver.py
"""

import json
import sys
import os
import uuid
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote

NTFY_BASE = "https://ntfy.sh"

# Tools that trigger mobile approval. Read/search ops are always allowed silently.
APPROVAL_REQUIRED_TOOLS = {
    "Bash",
    "Write",
    "Edit",
    "NotebookEdit",
    "Task",
}

# Tools always silently allowed — never interrupt for these
ALWAYS_ALLOW_TOOLS = {
    "Read", "Glob", "Grep", "WebFetch", "WebSearch",
    "TodoWrite", "TodoRead", "AskUserQuestion",
    "mcp__supabase__list_tables",  # read-only MCP calls
}


# ── ntfy helpers ──────────────────────────────────────────────────────────────

def _ntfy_publish(topic: str, title: str, message: str, response_topic: str) -> bool:
    """
    Publish a notification to ntfy with Allow/Deny action buttons.
    The buttons POST 'allow' or 'deny' to the response_topic.
    Returns True on success.
    """
    url = f"{NTFY_BASE}/{quote(topic)}"
    allow_action = f"http, Allow, {NTFY_BASE}/{response_topic}, method=POST, body=allow, clear=true"
    deny_action = f"http, Deny, {NTFY_BASE}/{response_topic}, method=POST, body=deny, clear=true"

    headers = {
        "Title": title,
        "Message": message,
        "Priority": "high",
        "Tags": "claude,key",
        "Actions": f"{allow_action}; {deny_action}",
        "Content-Type": "text/plain",
    }

    req = Request(url, data=message.encode(), headers=headers, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (URLError, HTTPError):
        return False


def _ntfy_poll(response_topic: str, timeout: int) -> str | None:
    """
    Poll ntfy for a response on response_topic.
    Returns "allow", "deny", or None on timeout.
    Polls every 2 seconds up to timeout.
    """
    url = f"{NTFY_BASE}/{response_topic}/json?poll=1&since=all"
    deadline = time.time() + timeout
    last_check = time.time() - 3  # force immediate first check

    while time.time() < deadline:
        if time.time() - last_check >= 2:
            last_check = time.time()
            req = Request(url, headers={"User-Agent": "ClaudeCodeAdvancements-MobileApprover/1.0"})
            try:
                with urlopen(req, timeout=5) as resp:
                    raw = resp.read().decode().strip()
                if raw:
                    # ntfy returns newline-delimited JSON; take the last message
                    for line in reversed(raw.splitlines()):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                            body = msg.get("message", "").strip().lower()
                            if body in ("allow", "deny"):
                                return body
                        except json.JSONDecodeError:
                            continue
            except (URLError, HTTPError):
                pass  # network hiccup — keep polling
        time.sleep(0.5)

    return None  # timeout


# ── Decision logic ────────────────────────────────────────────────────────────

def _needs_approval(tool_name: str) -> bool:
    if tool_name in ALWAYS_ALLOW_TOOLS:
        return False
    return tool_name in APPROVAL_REQUIRED_TOOLS


def _format_notification(tool_name: str, tool_input: dict) -> tuple[str, str]:
    """Return (title, message) for the notification."""
    title = f"Claude Code: {tool_name}"

    details = []
    if "command" in tool_input:
        cmd = tool_input["command"][:120]
        details.append(f"Command: {cmd}")
    if "file_path" in tool_input:
        path = tool_input["file_path"]
        # Show relative path if possible
        cwd = os.getcwd()
        if path.startswith(cwd):
            path = path[len(cwd):].lstrip("/")
        details.append(f"File: {path}")
    if "description" in tool_input:
        details.append(tool_input["description"][:100])
    if not details:
        raw = json.dumps(tool_input)[:150]
        details.append(raw)

    message = "\n".join(details) if details else tool_name
    return title, message


def _allow_response() -> dict:
    return {
        "hookSpecificOutput": {
            "permissionDecision": "allow"
        }
    }


def _deny_response(reason: str = "Denied from iPhone") -> dict:
    return {
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "denyReason": reason
        }
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Check disabled flag
    if os.environ.get("MOBILE_APPROVER_DISABLED", "0") == "1":
        print(json.dumps(_allow_response()))
        return

    # Read hook input
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        print(json.dumps(_allow_response()))
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Always allow non-destructive tools
    if not _needs_approval(tool_name):
        print(json.dumps(_allow_response()))
        return

    # Get config
    topic = os.environ.get("MOBILE_APPROVER_TOPIC", "").strip()
    if not topic:
        # No topic configured — fall through silently (don't block work)
        print(json.dumps(_allow_response()))
        return

    timeout = int(os.environ.get("MOBILE_APPROVER_TIMEOUT", "60"))
    default = os.environ.get("MOBILE_APPROVER_DEFAULT", "allow").lower()
    if default not in ("allow", "deny"):
        default = "allow"

    # Unique response topic for this request (prevents cross-contamination)
    short_id = uuid.uuid4().hex[:8]
    response_topic = f"{topic}-resp-{short_id}"

    title, message = _format_notification(tool_name, tool_input)

    # Send notification
    sent = _ntfy_publish(topic, title, message, response_topic)
    if not sent:
        # Can't reach ntfy — fail open (allow) so work isn't silently blocked
        print(json.dumps(_allow_response()))
        return

    # Wait for response
    decision = _ntfy_poll(response_topic, timeout)

    if decision is None:
        # Timeout — use configured default
        if default == "deny":
            print(json.dumps(_deny_response("Timed out — denied by default")))
        else:
            print(json.dumps(_allow_response()))
        return

    if decision == "deny":
        print(json.dumps(_deny_response("Denied from iPhone")))
    else:
        print(json.dumps(_allow_response()))


if __name__ == "__main__":
    main()
