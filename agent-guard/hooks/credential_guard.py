"""
AG-3: Credential-Extraction Guard — PreToolUse

Intercepts Bash tool calls and blocks (or warns about) commands that are known
vectors for credential/secret exfiltration. This guards against prompt injection
attacks where malicious content tries to trick Claude into running commands that
dump environment variables, API keys, or other secrets.

Primary threats guarded:
  1. docker compose config / docker inspect  — dumps all env vars from compose files
  2. printenv / env | command                — dumps entire environment
  3. cat .env / cat ~/.aws / cat ~/.ssh      — reads credential files directly
  4. /proc/self/environ                      — reads process environment (Linux)
  5. history | (pipe)                        — command history may contain secrets

Behavior:
  - Default: warn Claude, but allow (with explanation of what the command does)
  - Opt-in blocking: set CLAUDE_CRED_GUARD_BLOCK=1 to block flagged commands
  - Disabled: set CLAUDE_CRED_GUARD_DISABLED=1

Wire as PreToolUse hook:
  {
    "hooks": {
      "PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type":"command","command":"python3 .../credential_guard.py"}]}
      ]
    }
  }

Note: Use "Bash" matcher (not "") so this only fires on Bash calls, not all tools.
"""
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Threat patterns
# ---------------------------------------------------------------------------

# Each entry: (pattern_regex, threat_description, severity)
# severity: "critical" = block by default, "high" = warn and block if BLOCK=1
THREAT_PATTERNS = [
    # Docker credential extraction
    (
        r"docker[\s-]+compose\s+config",
        "docker compose config dumps ALL environment variables including secrets from .env files",
        "critical",
    ),
    (
        r"docker\s+inspect\s+",
        "docker inspect can expose container environment variables including mounted secrets",
        "high",
    ),
    # Environment variable dumps
    (
        r"\bprintenv\b",
        "printenv prints all environment variables including API keys and tokens",
        "high",
    ),
    (
        r"\benv\b\s*[|>]",
        "env piped to another command exfiltrates all environment variables",
        "critical",
    ),
    (
        r"\bset\b\s*[|>]",
        "bash 'set' piped out dumps all shell variables and functions including secrets",
        "high",
    ),
    # Credential file reads
    (
        r"cat\s+\.env\b",
        "cat .env reads the project .env file which typically contains API keys and database passwords",
        "critical",
    ),
    (
        r"cat\s+['\"]?\.env['\"]?",
        "reading .env file exposes all configured secrets",
        "critical",
    ),
    (
        r"cat\s+~?/?\.aws/",
        "reading ~/.aws/ exposes AWS access keys and secret keys",
        "critical",
    ),
    (
        r"cat\s+~?/?\.ssh/(?!known_hosts|config)",
        "reading ~/.ssh/ private key files exposes SSH credentials",
        "critical",
    ),
    (
        r"/proc/self/environ",
        "/proc/self/environ exposes the current process environment variables on Linux",
        "critical",
    ),
    # History exfiltration
    (
        r"\bhistory\b\s*[|>]",
        "piping command history may expose previously used API keys, passwords, and tokens",
        "high",
    ),
    # Credential scanning tools used offensively
    (
        r"\bgrep\b.{0,60}(password|api.?key|secret|token|credential).{0,30}[|>]",
        "searching for credentials and piping results out is a common exfiltration pattern",
        "high",
    ),
]


def check_command(command: str) -> list[dict]:
    """
    Check a bash command string against all threat patterns.
    Returns list of {pattern, description, severity} for each match.
    """
    threats = []
    for pattern, description, severity in THREAT_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            threats.append({
                "pattern": pattern,
                "description": description,
                "severity": severity,
            })
    return threats


def has_critical_threat(threats: list[dict]) -> bool:
    return any(t["severity"] == "critical" for t in threats)


def build_warn_message(command: str, threats: list[dict], blocking: bool) -> str:
    threat_lines = "\n".join(
        f"  [{t['severity'].upper()}] {t['description']}" for t in threats
    )
    action = "Blocking this command." if blocking else "Proceeding — verify this command is safe."
    return (
        f"[AG-3] Credential-extraction risk detected in Bash command:\n"
        f"  Command: {command[:120]}\n"
        f"Threat(s):\n{threat_lines}\n"
        f"{action}"
    )


def _allow_response() -> dict:
    return {}


def _warn_response(message: str) -> dict:
    return {
        "hookSpecificOutput": {
            "permissionDecision": "allow",
        },
        "suppressOutput": False,
        "reason": message,
    }


def _block_response(message: str) -> dict:
    return {
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "denyReason": message,
        },
    }


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if os.environ.get("CLAUDE_CRED_GUARD_DISABLED") == "1":
        print(json.dumps(_allow_response()))
        sys.exit(0)

    blocking = os.environ.get("CLAUDE_CRED_GUARD_BLOCK") == "1"

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # Only act on Bash tool calls
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Bash", "bash"):
        print(json.dumps(_allow_response()))
        sys.exit(0)

    # Extract the command from the tool input
    tool_input = payload.get("tool_input", {})
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except (json.JSONDecodeError, ValueError):
            tool_input = {}
    command = tool_input.get("command", "")

    if not command:
        print(json.dumps(_allow_response()))
        sys.exit(0)

    threats = check_command(command)
    if not threats:
        print(json.dumps(_allow_response()))
        sys.exit(0)

    should_block = blocking or has_critical_threat(threats)
    message = build_warn_message(command, threats, should_block)

    if should_block:
        print(json.dumps(_block_response(message)))
    else:
        print(json.dumps(_warn_response(message)))

    sys.exit(0)


if __name__ == "__main__":
    main()
