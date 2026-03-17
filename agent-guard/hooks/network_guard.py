"""
AG-5: Network/Port Exposure Guard — PreToolUse

Intercepts Bash tool calls and blocks (or warns about) commands that
expose ports to the internet, modify firewall rules, or change network
configuration. Built from "We got hacked" incident (458pts, 206 comments
on r/ClaudeCode) where Claude exposed ADB port 5555 on a Hetzner VM
and a crypto miner exploited it within hours.

Primary threats guarded:
  1. adb tcpip                      — exposes ADB debug port to world
  2. ufw disable / iptables -F      — disables firewall entirely
  3. ufw allow / iptables ACCEPT    — opens firewall ports
  4. docker -p PORT:PORT            — binds port to 0.0.0.0 by default
  5. python http.server / nc -l     — starts listener on all interfaces
  6. ngrok / cloudflared            — tunnels local ports to public internet
  7. ssh -R 0.0.0.0:                — remote forward to all interfaces
  8. /etc/hosts, sshd_config writes — network config modifications

Behavior:
  - Default: critical threats block, high threats warn
  - Opt-in full blocking: set CLAUDE_NET_GUARD_BLOCK=1
  - Disabled: set CLAUDE_NET_GUARD_DISABLED=1

Wire as PreToolUse hook:
  {
    "hooks": {
      "PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type":"command","command":"python3 .../network_guard.py"}]}
      ]
    }
  }
"""
import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# Threat patterns
# ---------------------------------------------------------------------------

# Each entry: (pattern_regex, threat_description, severity)
# severity: "critical" = block by default, "high" = warn (block if NET_GUARD_BLOCK=1)
THREAT_PATTERNS = [
    # ADB debug port exposure (the exact "We got hacked" vector)
    (
        r"\badb\s+tcpip\b",
        "adb tcpip exposes Android Debug Bridge to the network — the exact attack vector from 'We got hacked' incident",
        "critical",
    ),
    # Firewall disable — critical
    (
        r"\bufw\s+disable\b",
        "ufw disable turns off the firewall entirely, exposing all ports to the internet",
        "critical",
    ),
    (
        r"\biptables\s+-F\b",
        "iptables -F flushes all firewall rules, leaving the system completely exposed",
        "critical",
    ),
    (
        r"\biptables\s+--flush\b",
        "iptables --flush clears all firewall rules",
        "critical",
    ),
    # Tunnel services — critical (expose local ports to public internet)
    (
        r"\bngrok\s+(http|tcp|tls)\b",
        "ngrok creates a public tunnel to a local port, exposing it to the entire internet",
        "critical",
    ),
    (
        r"\bcloudflared\s+tunnel\b",
        "cloudflared tunnel exposes local services to the public internet via Cloudflare",
        "critical",
    ),
    # Firewall port opening — high
    (
        r"\bufw\s+allow\b",
        "ufw allow opens a firewall port — verify this is intentional and scoped correctly",
        "high",
    ),
    (
        r"\bufw\s+delete\b",
        "ufw delete removes a firewall rule — this may expose previously blocked ports",
        "high",
    ),
    (
        r"\biptables\s+(-A|--append)\s+\w+.*-j\s+ACCEPT\b",
        "iptables ACCEPT rule opens a port through the firewall",
        "high",
    ),
    (
        r"\bnft\s+add\s+rule\b",
        "nftables rule addition may open firewall ports",
        "high",
    ),
    (
        r"\bfirewall-cmd\s+--add-port\b",
        "firewall-cmd --add-port opens a port in the firewall",
        "high",
    ),
    # Docker port binding — high (defaults to 0.0.0.0)
    # Match -p PORT:PORT but NOT -p 127.0.0.1:PORT:PORT
    (
        r"docker\s+run\b[^|;]*\s-p\s+(?!127\.0\.0\.1:)\d+:\d+",
        "docker -p without 127.0.0.1 prefix binds to 0.0.0.0 (all interfaces) by default",
        "high",
    ),
    (
        r"docker\s+run\b[^|;]*\s-p\s+0\.0\.0\.0:",
        "docker -p 0.0.0.0: explicitly binds port to all network interfaces",
        "high",
    ),
    # Port listening — high
    (
        r"\bnc\s+.*-l",
        "netcat listener may expose a port to the network",
        "high",
    ),
    (
        r"\bsocat\s+TCP-LISTEN:",
        "socat TCP-LISTEN creates a network listener that may be reachable externally",
        "high",
    ),
    # Python HTTP server — high (defaults to all interfaces)
    # Match http.server without --bind 127.0.0.1 / --bind localhost
    (
        r"python3?\s+-m\s+http\.server\b(?!.*--bind\s+(?:127\.0\.0\.1|localhost))",
        "python http.server without --bind 127.0.0.1 listens on all interfaces by default",
        "high",
    ),
    # Explicit 0.0.0.0 binding (in code, config, or CLI args)
    (
        r"(?:listen|bind|host)\s*[(=].{0,30}0\.0\.0\.0",
        "binding to 0.0.0.0 makes the service reachable from all network interfaces",
        "high",
    ),
    # SSH remote forwarding to all interfaces
    (
        r"ssh\s+.*-R\s+0\.0\.0\.0:",
        "ssh -R 0.0.0.0: forwards a remote port on all interfaces, exposing it publicly",
        "high",
    ),
    # Network config file modifications — high
    (
        r"(?:echo|printf|tee|sed\s+-i|>>)\s+.*(/etc/hosts)\b",
        "modifying /etc/hosts changes DNS resolution — verify this is intentional",
        "high",
    ),
    (
        r"(?:sed|echo|printf|cat|tee|nano|vim|vi)\s+.*/etc/ssh/sshd_config\b",
        "modifying sshd_config changes SSH server security settings",
        "high",
    ),
]


def check_command(command: str) -> list[dict]:
    """Check a bash command against all threat patterns.

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
        f"[AG-5] Network/port exposure risk detected in Bash command:\n"
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
    if os.environ.get("CLAUDE_NET_GUARD_DISABLED") == "1":
        print(json.dumps(_allow_response()))
        sys.exit(0)

    blocking = os.environ.get("CLAUDE_NET_GUARD_BLOCK") == "1"

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
