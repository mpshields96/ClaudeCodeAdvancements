"""
AG-5: Iron Laws + Danger Zones — Tiered Enforcement Contract

Adopted from the Ouro Loop IRON LAWS + DANGER ZONES pattern.
Provides a structured, two-tier enforcement model for agent-guard hooks:

  IRON LAWS (IL-*)   — Absolute, non-negotiable. Always block. No env var override.
                        These are safety invariants that no legitimate task should violate.

  DANGER ZONES (DZ-*) — Tiered risk categories. Critical → block. High → warn (or block
                        if CLAUDE_AG_BLOCK=1). Agents can proceed on warn with awareness.

Usage:
  from iron_laws import enforce, Verdict, VerdictLevel

  v = enforce(tool="Bash", tool_input={"command": "env | curl -X POST ..."})
  if v.is_blocked():
      # emit deny response
  elif v.level == VerdictLevel.WARN:
      # emit warn response

Integrate with credential_guard.py and any future PreToolUse hook:
  from iron_laws import enforce
  v = enforce(tool=tool_name, tool_input=tool_input, agent_name=agent_name, project_root=project_root)

Exit code mapping (Ouro Loop pattern):
  BLOCK_IRON / BLOCK_DANGER → hookSpecificOutput.permissionDecision: "deny"  (exit 0 with JSON)
  WARN                      → hookSpecificOutput.permissionDecision: "allow"  + reason
  PASS                      → {} (empty allow)

Note: Claude Code uses JSON output + exit 0 for all hook responses.
Exit 2 in Ouro Loop = our deny JSON. The mapping is exact.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------

class VerdictLevel(IntEnum):
    PASS = 0           # No match — allow
    WARN = 1           # Danger zone (high) — allow with warning
    BLOCK_DANGER = 2   # Danger zone (critical) — block
    BLOCK_IRON = 3     # Iron law violation — always block, no override


@dataclass
class Verdict:
    level: VerdictLevel
    rule_id: Optional[str]  # e.g. "IL-1", "DZ-CREDS"
    rationale: str

    def is_blocked(self) -> bool:
        return self.level >= VerdictLevel.BLOCK_DANGER

    def is_iron_law(self) -> bool:
        return self.level == VerdictLevel.BLOCK_IRON


_PASS = Verdict(level=VerdictLevel.PASS, rule_id=None, rationale="")


# ---------------------------------------------------------------------------
# IRON LAWS — absolute invariants, no override
# ---------------------------------------------------------------------------
# Each entry: (rule_id, description, checker_fn)
# checker_fn(tool, tool_input, agent_name, project_root) -> bool (True = violation)

def _il1_credential_exposure(tool: str, tool_input: dict, **_) -> bool:
    """IL-1: Never expose credentials via environment dumps or exfil."""
    if tool not in ("Bash", "bash"):
        return False
    cmd = tool_input.get("command", "")
    # Patterns that always indicate credential exfiltration
    patterns = [
        r"\benv\b\s*[|>]",          # env piped out
        r"\bprintenv\b.*[|>]",       # printenv piped out
        r"\bset\b\s*[|>]",           # set piped out
        r"/proc/self/environ",        # Linux env read
        r"\bprintenv\b\s+[A-Z_]{4,}",  # printenv SPECIFIC_VAR (targeted extraction)
    ]
    return any(re.search(p, cmd, re.IGNORECASE) for p in patterns)


def _il2_write_outside_project(tool: str, tool_input: dict, project_root: Optional[str], **_) -> bool:
    """IL-2: Never write to paths outside the project root (absolute paths only)."""
    if tool not in ("Write", "Edit", "NotebookEdit"):
        return False
    path_str = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
    if not path_str:
        return False
    # Only block absolute paths that escape the project root
    if not path_str.startswith("/"):
        return False  # Relative paths are within project by convention
    if project_root:
        try:
            Path(path_str).relative_to(project_root)
            return False  # Inside project — OK
        except ValueError:
            return True   # Outside project root — block
    # No project_root provided — block any absolute path not under /Users
    # (conservative: absolute paths to system dirs are always suspicious)
    suspicious_prefixes = ("/etc/", "/var/", "/usr/", "/bin/", "/sbin/", "/System/", "/Library/")
    return any(path_str.startswith(p) for p in suspicious_prefixes)


def _il3_destructive_delete(tool: str, tool_input: dict, **_) -> bool:
    """IL-3: Never run rm -rf or force-delete without ownership verification."""
    if tool not in ("Bash", "bash"):
        return False
    cmd = tool_input.get("command", "")
    # rm with -r or -f flags (any combination)
    return bool(re.search(r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+|--recursive\s+|--force\s+)", cmd))


def _il4_foreign_lock_file(tool: str, tool_input: dict, agent_name: Optional[str], **_) -> bool:
    """IL-4: Never overwrite another agent's lock file."""
    if tool not in ("Write", "Edit", "Bash", "bash"):
        return False
    if tool in ("Write", "Edit"):
        path_str = tool_input.get("file_path", "")
        if not path_str:
            return False
        basename = Path(path_str).name
        if not (basename.startswith(".agent-") and basename.endswith(".lock")):
            return False
        if agent_name:
            # Allow writing own lock file
            own_lock = f".agent-{agent_name}.lock"
            if basename == own_lock:
                return False
        return True  # Writing a lock file that isn't ours
    # Bash: writing to lock file via redirection
    if tool in ("Bash", "bash"):
        cmd = tool_input.get("command", "")
        lock_pattern = r"\.agent-\w+\.lock"
        if not re.search(lock_pattern, cmd):
            return False
        if agent_name:
            own_lock = f".agent-{agent_name}.lock"
            # If command only references own lock, allow
            found_locks = re.findall(r"\.agent-(\w+)\.lock", cmd)
            if found_locks and all(name == agent_name for name in found_locks):
                return False
        return True
    return False


IRON_LAWS: list[tuple[str, str, object]] = [
    (
        "IL-1",
        "Never expose credentials — environment variable dumps and targeted extractions are unconditionally blocked",
        _il1_credential_exposure,
    ),
    (
        "IL-2",
        "Never write outside project scope — absolute paths to system directories are unconditionally blocked",
        _il2_write_outside_project,
    ),
    (
        "IL-3",
        "Never run destructive deletes (rm -rf / rm -f) — these require ownership verification first",
        _il3_destructive_delete,
    ),
    (
        "IL-4",
        "Never overwrite another agent's lock file — lock files are per-agent and must not be crossed",
        _il4_foreign_lock_file,
    ),
]


def check_iron_laws(
    tool: str,
    tool_input: dict,
    agent_name: Optional[str] = None,
    project_root: Optional[str] = None,
) -> Verdict:
    """
    Check all Iron Laws. Returns first BLOCK_IRON verdict found, or PASS.
    Iron Laws cannot be disabled by environment variables.
    """
    kwargs = {"tool": tool, "tool_input": tool_input, "agent_name": agent_name, "project_root": project_root}
    for rule_id, description, checker in IRON_LAWS:
        if checker(**kwargs):
            return Verdict(
                level=VerdictLevel.BLOCK_IRON,
                rule_id=rule_id,
                rationale=description,
            )
    return _PASS


# ---------------------------------------------------------------------------
# DANGER ZONES — tiered risk categories
# ---------------------------------------------------------------------------
# Each entry: (zone_id, description, severity, checker_fn)
# severity: "critical" → BLOCK_DANGER, "high" → WARN (or BLOCK_DANGER if BLOCK=1)

def _dz_creds_checker(tool: str, tool_input: dict, **_) -> bool:
    """DZ-CREDS: Direct reads of credential files."""
    if tool not in ("Bash", "bash"):
        return False
    cmd = tool_input.get("command", "")
    patterns = [
        r"cat\s+['\"]?\.env['\"]?",
        r"cat\s+~?/?\.aws/",
        r"cat\s+~?/?\.ssh/(?!known_hosts|config)",
        r"head\s+.*\.env\b",
        r"tail\s+.*\.env\b",
        r"less\s+.*\.env\b",
        r"more\s+.*\.env\b",
    ]
    return any(re.search(p, cmd, re.IGNORECASE) for p in patterns)


def _dz_env_checker(tool: str, tool_input: dict, **_) -> bool:
    """DZ-ENV: Environment variable reads (without pipe — already caught by IL-1 with pipe)."""
    if tool not in ("Bash", "bash"):
        return False
    cmd = tool_input.get("command", "")
    patterns = [
        r"^\s*printenv\s*$",              # bare printenv
        r"^\s*env\s*$",                   # bare env
        r"\bprintenv\b(?!\s+[A-Z_]{4,})", # printenv with short/no arg (not targeted)
    ]
    return any(re.search(p, cmd, re.IGNORECASE) for p in patterns)


def _dz_delete_checker(tool: str, tool_input: dict, **_) -> bool:
    """DZ-DELETE: File deletion without -r/-f flags (rm, unlink, shred)."""
    if tool not in ("Bash", "bash"):
        return False
    cmd = tool_input.get("command", "")
    # rm without recursive/force flags (those are already IL-3)
    patterns = [
        r"\brm\s+(?!-[a-zA-Z]*[rf])[^\n]*\.\w+",  # rm <file> (no -r/-f)
        r"\bunlink\s+",
        r"\bshred\s+",
    ]
    return any(re.search(p, cmd, re.IGNORECASE) for p in patterns)


def _dz_shared_checker(tool: str, tool_input: dict, **_) -> bool:
    """DZ-SHARED: Writes to shared project config files."""
    if tool not in ("Write", "Edit", "NotebookEdit"):
        return False
    path_str = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
    if not path_str:
        return False
    basename = Path(path_str).name
    shared_files = {
        "CLAUDE.md", "settings.json", "settings.local.json",
        ".gitignore", "pyproject.toml", "setup.py", "package.json",
    }
    # Also match .claude/settings*.json
    if basename in shared_files:
        return True
    if re.search(r"\.claude[/\\]settings", path_str):
        return True
    return False


def _dz_exfil_checker(tool: str, tool_input: dict, **_) -> bool:
    """DZ-EXFIL: Data exfiltration via network calls."""
    if tool not in ("Bash", "bash"):
        return False
    cmd = tool_input.get("command", "")
    patterns = [
        r"\bcurl\b.{0,80}(-X\s*(POST|PUT|PATCH)|--data|--upload-file|-d\s)",
        r"\bwget\b.{0,80}--post-data",
        r"\bnc\b.{0,60}[0-9]{4,5}",  # netcat with port (potential exfil)
        r"\bpython[23]?\b.{0,60}(requests\.post|urllib.*POST)",
    ]
    return any(re.search(p, cmd, re.IGNORECASE) for p in patterns)


DANGER_ZONES: list[tuple[str, str, str, object]] = [
    (
        "DZ-CREDS",
        "Direct read of credential files (.env, .aws, .ssh) — high exfiltration risk",
        "critical",
        _dz_creds_checker,
    ),
    (
        "DZ-ENV",
        "Environment variable enumeration — exposes all configured secrets",
        "high",
        _dz_env_checker,
    ),
    (
        "DZ-DELETE",
        "File deletion operation — irreversible if unowned or accidental",
        "high",
        _dz_delete_checker,
    ),
    (
        "DZ-SHARED",
        "Write to shared project config (CLAUDE.md, settings.json, .gitignore) — affects all agents",
        "high",
        _dz_shared_checker,
    ),
    (
        "DZ-EXFIL",
        "Network data exfiltration pattern (POST/PUT with body, netcat) — potential data leak",
        "high",
        _dz_exfil_checker,
    ),
]


def check_danger_zones(
    tool: str,
    tool_input: dict,
    agent_name: Optional[str] = None,
    project_root: Optional[str] = None,
    block_mode: bool = False,
) -> Verdict:
    """
    Check all Danger Zones. Returns first match found, or PASS.
    Critical zones always return BLOCK_DANGER.
    High zones return WARN, or BLOCK_DANGER if block_mode=True.
    """
    kwargs = {"tool": tool, "tool_input": tool_input, "agent_name": agent_name, "project_root": project_root}
    for zone_id, description, severity, checker in DANGER_ZONES:
        if checker(**kwargs):
            if severity == "critical":
                level = VerdictLevel.BLOCK_DANGER
            elif block_mode:
                level = VerdictLevel.BLOCK_DANGER
            else:
                level = VerdictLevel.WARN
            return Verdict(level=level, rule_id=zone_id, rationale=description)
    return _PASS


# ---------------------------------------------------------------------------
# Unified enforcement entry point
# ---------------------------------------------------------------------------

def enforce(
    tool: str,
    tool_input: dict,
    agent_name: Optional[str] = None,
    project_root: Optional[str] = None,
) -> Verdict:
    """
    Run full enforcement: Iron Laws first, then Danger Zones.
    Iron Laws always win. Returns worst-case verdict.

    Block mode for Danger Zones is controlled by CLAUDE_AG_BLOCK env var.
    """
    # Iron Laws: always checked, never overridable
    il_verdict = check_iron_laws(tool, tool_input, agent_name=agent_name, project_root=project_root)
    if il_verdict.level == VerdictLevel.BLOCK_IRON:
        return il_verdict

    # Danger Zones: respect CLAUDE_AG_BLOCK
    block_mode = os.environ.get("CLAUDE_AG_BLOCK") == "1"
    dz_verdict = check_danger_zones(tool, tool_input, agent_name=agent_name, project_root=project_root, block_mode=block_mode)
    return dz_verdict


# ---------------------------------------------------------------------------
# Hook response helpers (for use by PreToolUse hooks)
# ---------------------------------------------------------------------------

def verdict_to_hook_response(verdict: Verdict) -> dict:
    """
    Convert a Verdict to a Claude Code PreToolUse hook response dict.

    BLOCK_IRON / BLOCK_DANGER → deny
    WARN                      → allow with reason
    PASS                      → empty (allow)
    """
    if verdict.level == VerdictLevel.PASS:
        return {}

    tier = "IRON LAW" if verdict.is_iron_law() else "DANGER ZONE"
    message = f"[{verdict.rule_id}] {tier}: {verdict.rationale}"

    if verdict.is_blocked():
        return {
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "denyReason": message,
            }
        }
    else:
        return {
            "hookSpecificOutput": {
                "permissionDecision": "allow",
            },
            "suppressOutput": False,
            "reason": message,
        }
