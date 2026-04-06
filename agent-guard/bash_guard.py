#!/usr/bin/env python3
"""
AG-9: Bash Command Safety Guard — PreToolUse hook for Bash calls.

Comprehensive blocklist for dangerous Bash commands that could:
- Make network requests (except git)
- Install/uninstall packages globally
- Kill/manage processes
- Modify system configuration
- Redirect output outside the CCA project folder
- Perform destructive filesystem operations outside project
- Access financial APIs

Levels:
- BLOCK: dangerous command detected, deny the operation
- WARN: potentially dangerous but not critical (git reset --hard, etc.)
- PASS: safe, allow the operation

Usage as library:
    guard = BashGuard(project_root="/path/to/project")
    result = guard.check("curl https://evil.com")  # {"level": "BLOCK", "reason": "..."}

Usage as PreToolUse hook:
    Reads JSON from stdin, writes JSON to stdout.
    Wire with matcher "Bash" in settings.local.json.

Stdlib only. No external dependencies.
"""

import json
import os
import re
import sys


# === Network egress commands (BLOCK all except git) ===
NETWORK_PATTERNS = [
    (r"\bcurl\b", "curl: network request"),
    (r"\bwget\b", "wget: network download"),
    (r"\bnc\b", "nc/netcat: raw network connection"),
    (r"\bncat\b", "ncat: network connection"),
    (r"\bnetcat\b", "netcat: raw network connection"),
    (r"\bssh\b(?!\s*-)", "ssh: remote shell"),  # ssh without flags is a connection
    (r"\bssh\s+", "ssh: remote connection"),
    (r"\bscp\b", "scp: remote file copy"),
    (r"\bsftp\b", "sftp: remote file transfer"),
    (r"\brsync\b.*@", "rsync: remote sync (has @ = remote target)"),
    (r"\btelnet\b", "telnet: remote connection"),
    (r"\bnmap\b", "nmap: network scanner"),
    (r"\bpython3?\s+-m\s+http\.server", "python http server: exposes local files"),
    (r"\bopen\s+https?://", "open URL: launches browser"),
]

# === Package management (BLOCK all installs/uninstalls) ===
PACKAGE_PATTERNS = [
    (r"\bpip3?\s+install\b", "pip install: global package install"),
    (r"\bpip3?\s+uninstall\b", "pip uninstall: package removal"),
    (r"\bnpm\s+install\s+-g\b", "npm install -g: global package install"),
    (r"\bnpm\s+uninstall\b", "npm uninstall: package removal"),
    (r"\bbrew\s+(install|uninstall|remove|upgrade)\b", "brew: system package management"),
    (r"\bgem\s+install\b", "gem install: Ruby package install"),
    (r"\bcargo\s+install\b", "cargo install: Rust package install"),
    (r"\bapt(-get)?\s+(install|remove|purge)\b", "apt: system package management"),
    (r"\byum\s+(install|remove)\b", "yum: system package management"),
    (r"\bdnf\s+(install|remove)\b", "dnf: system package management"),
    (r"\bpacman\s+-S\b", "pacman: system package install"),
]

# === Process management (BLOCK) ===
PROCESS_PATTERNS = [
    (r"\bkill\b\s+(-\d+\s+)?\d+", "kill: process termination"),
    (r"\bkill\b\s+-\w+\s+\d+", "kill: process signal"),
    (r"\bkillall\b", "killall: mass process termination"),
    (r"\bpkill\b", "pkill: pattern-based process kill"),
    (r"\blaunchctl\b", "launchctl: macOS service management"),
    (r"\bsystemctl\b", "systemctl: Linux service management"),
    (r"\bservice\b\s+\w+\s+(start|stop|restart|reload)", "service: daemon management"),
]

# === System modification (BLOCK) ===
SYSTEM_PATTERNS = [
    (r"\bsudo\b", "sudo: privilege escalation"),
    (r"\bsu\s+(-\s+)?(\w+|root)", "su: user switch"),
    (r"\bdefaults\s+write\b", "defaults write: macOS system preference modification"),
    (r"\bdscl\b", "dscl: macOS directory service (user management)"),
    (r"\bscutil\b", "scutil: macOS system configuration"),
    (r"\bnetworksetup\b", "networksetup: macOS network configuration"),
    (r"\bcsrutil\b", "csrutil: SIP configuration"),
    (r"\bspctl\b", "spctl: Gatekeeper configuration"),
    (r"\bcrontab\s+-[er]", "crontab: scheduled task modification"),
    (r"\bgit\s+config\s+--global\b", "git config --global: global git configuration"),
    (r"\bgit\s+config\s+--system\b", "git config --system: system git configuration"),
    (r"\bchmod\b\s+\d+\s+/(etc|usr|bin|sbin|System|Library|var)", "chmod on system path"),
    (r"\bchown\b\s+\S+\s+/(etc|usr|bin|sbin|System|Library|var)", "chown on system path"),
]

# === Destructive outside-project commands (BLOCK) ===
# Static patterns that are always dangerous regardless of project.
# Project-aware rm -rf check is done dynamically in BashGuard.check() using self._project_root.
DESTRUCTIVE_PATTERNS = [
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-rf|-fr)\s+(~|\$HOME|\.\.\/\.\.)", "rm -rf home or parent escape"),
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-rf|-fr)\s+/$", "rm -rf root"),
]

# Pattern used for dynamic rm -rf outside-project check in BashGuard.check()
_RM_RF_ABSOLUTE = re.compile(
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-rf|-fr)\s+(/[^\s;|&'\"]*)"
)

# === Financial API domains (BLOCK) ===
FINANCIAL_DOMAINS = [
    "api.kalshi.com", "api.coinbase.com", "api.stripe.com",
    "api.binance.com", "api.kraken.com", "api.robinhood.com",
    "api.alpaca.markets", "api.polygon.io", "api.paypal.com",
    "api.plaid.com", "api.schwab.com", "api.fidelity.com",
]

# === Evasion patterns (BLOCK) ===
EVASION_PATTERNS = [
    (r"\beval\b\s+['\"]", "eval with string: command evasion"),
    (r"\bbash\s+-c\b", "bash -c: subshell execution"),
    (r"\bsh\s+-c\b", "sh -c: subshell execution"),
    (r"\bzsh\s+-c\b", "zsh -c: subshell execution"),
    # Script interpreter inline code execution (bypass vector per r/ClaudeCode community reports)
    (r"\bpython3?\s+-c\b", "python -c: inline code execution (evasion vector)"),
    (r"\bperl\s+-e\b", "perl -e: inline code execution (evasion vector)"),
    (r"\bruby\s+-e\b", "ruby -e: inline code execution (evasion vector)"),
    (r"\bnode\s+-e\b", "node -e: inline code execution (evasion vector)"),
    (r"\bpwsh\s+-c\b", "pwsh -c: PowerShell inline execution (evasion vector)"),
    (r"\bpowershell\s+-c\b", "powershell -c: PowerShell inline execution (evasion vector)"),
]

# === Warned commands (WARN, not BLOCK) ===
WARNED_PATTERNS = [
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard: discards uncommitted changes"),
    (r"\bgit\s+push\s+.*--force\b", "git force push: rewrites remote history"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "git clean -f: deletes untracked files"),
    (r"\bgit\s+checkout\s+--\s+\.", "git checkout -- .: discards all changes"),
    (r"\bgit\s+stash\s+drop\b", "git stash drop: permanently discards stash"),
]


class BashGuard:
    """Checks Bash commands for safety before execution."""

    def __init__(self, project_root: str = ""):
        self._project_root = os.path.normpath(project_root) if project_root else ""

    def check(self, command: str) -> dict:
        """Check a Bash command for safety.

        Returns: {"level": "PASS"|"WARN"|"BLOCK", "reason": str, "category": str}
        """
        if not command:
            return {"level": "PASS", "reason": "", "category": ""}

        # Check the full command string (catches chained commands)
        # Also split on ; && || | to check each part
        full_command = command.strip()

        # --- BLOCK checks ---

        # Network egress (except git)
        for pattern, desc in NETWORK_PATTERNS:
            if re.search(pattern, full_command):
                # Allow git commands that happen to match (e.g., "ssh" in git ssh URLs)
                if self._is_git_context(full_command):
                    continue
                return {"level": "BLOCK", "reason": desc, "category": "network"}

        # Financial API domains
        for domain in FINANCIAL_DOMAINS:
            if domain in full_command:
                return {"level": "BLOCK", "reason": f"financial API access: {domain}", "category": "financial"}

        # Package management
        for pattern, desc in PACKAGE_PATTERNS:
            if re.search(pattern, full_command):
                return {"level": "BLOCK", "reason": desc, "category": "package"}

        # Process management
        for pattern, desc in PROCESS_PATTERNS:
            if re.search(pattern, full_command):
                return {"level": "BLOCK", "reason": desc, "category": "process"}

        # System modification
        for pattern, desc in SYSTEM_PATTERNS:
            if re.search(pattern, full_command):
                return {"level": "BLOCK", "reason": desc, "category": "system"}

        # Destructive commands outside project (static: root, home, parent escape)
        for pattern, desc in DESTRUCTIVE_PATTERNS:
            if re.search(pattern, full_command):
                return {"level": "BLOCK", "reason": desc, "category": "destructive"}

        # Dynamic: rm -rf on absolute path outside the project root
        rm_rf_match = _RM_RF_ABSOLUTE.search(full_command)
        if rm_rf_match:
            target = rm_rf_match.group(2).strip("'\"")
            if self._is_outside_project(target):
                return {
                    "level": "BLOCK",
                    "reason": f"rm -rf outside project: {target}",
                    "category": "destructive",
                }

        # Evasion patterns
        for pattern, desc in EVASION_PATTERNS:
            if re.search(pattern, full_command):
                return {"level": "BLOCK", "reason": desc, "category": "evasion"}

        # Output redirect outside project
        redirect_result = self._check_redirects(full_command)
        if redirect_result:
            return redirect_result

        # mv/cp to outside project
        move_result = self._check_move_copy(full_command)
        if move_result:
            return move_result

        # dd of= to outside project
        dd_result = self._check_dd(full_command)
        if dd_result:
            return dd_result

        # tee to outside project
        tee_result = self._check_tee(full_command)
        if tee_result:
            return tee_result

        # --- WARN checks ---
        for pattern, desc in WARNED_PATTERNS:
            if re.search(pattern, full_command):
                return {"level": "WARN", "reason": desc, "category": "git_destructive"}

        return {"level": "PASS", "reason": "", "category": ""}

    def hook_output(self, command: str) -> dict:
        """Generate PreToolUse hook JSON output.

        Returns empty dict for PASS, deny for BLOCK, additionalContext for WARN.
        """
        result = self.check(command)

        if result["level"] == "BLOCK":
            return {
                "hookSpecificOutput": {
                    "permissionDecision": "deny",
                    "reason": f"[AG-9 Bash Guard] BLOCKED: {result['reason']} (category: {result['category']})",
                }
            }
        elif result["level"] == "WARN":
            return {
                "hookSpecificOutput": {
                    "additionalContext": f"[AG-9 Bash Guard] WARNING: {result['reason']}. Proceed with caution.",
                }
            }
        return {}

    def _is_git_context(self, command: str) -> bool:
        """Check if the command is a git operation (network allowed for git)."""
        stripped = command.strip()
        # Direct git commands
        if stripped.startswith("git ") or stripped.startswith("rtk git "):
            return True
        # Git in a chain — check if the network part is within a git context
        # e.g., "cd repo && git pull" is fine
        # But "git status && curl evil.com" is NOT fine — the curl is separate
        return False

    def _check_redirects(self, command: str) -> "dict | None":  # type: ignore
        """Check for output redirects to paths outside the project."""
        # Match > or >> followed by a path
        redirect_matches = re.finditer(r">{1,2}\s*([^\s;|&]+)", command)
        for match in redirect_matches:
            target = match.group(1).strip("'\"")
            if self._is_outside_project(target):
                return {
                    "level": "BLOCK",
                    "reason": f"output redirect to outside project: {target}",
                    "category": "redirect",
                }
        return None

    def _check_move_copy(self, command: str) -> "dict | None":  # type: ignore
        """Check for mv/cp commands that move/copy files outside the project."""
        # mv <source> <dest> — check if dest is outside project
        mv_match = re.search(r"\bmv\s+\S+\s+(\S+)", command)
        if mv_match:
            dest = mv_match.group(1).strip("'\"")
            if self._is_outside_project(dest):
                return {
                    "level": "BLOCK",
                    "reason": f"mv destination outside project: {dest}",
                    "category": "destructive",
                }

        # cp [-flags] <source> <dest> — check if dest is outside project
        # Handles cp, cp -r, cp -a, etc. by skipping flag arguments
        cp_match = re.search(r"\bcp\s+(?:-[a-zA-Z]+\s+)*\S+\s+(\S+)", command)
        if cp_match:
            dest = cp_match.group(1).strip("'\"")
            if self._is_outside_project(dest):
                return {
                    "level": "BLOCK",
                    "reason": f"cp destination outside project: {dest}",
                    "category": "destructive",
                }

        return None

    def _check_dd(self, command: str) -> "dict | None":  # type: ignore
        """Check for dd commands writing outside the project via of= parameter."""
        dd_match = re.search(r"\bdd\b.*\bof=(\S+)", command)
        if dd_match:
            dest = dd_match.group(1).strip("'\"")
            if self._is_outside_project(dest):
                return {
                    "level": "BLOCK",
                    "reason": f"dd output file outside project: {dest}",
                    "category": "destructive",
                }
        return None

    def _check_tee(self, command: str) -> "dict | None":  # type: ignore
        """Check for tee commands writing outside the project."""
        # tee [-a] <path> — the path is the last non-flag argument
        tee_match = re.search(r"\btee\s+(?:-[a-zA-Z]+\s+)*(\S+)", command)
        if tee_match:
            dest = tee_match.group(1).strip("'\"")
            if self._is_outside_project(dest):
                return {
                    "level": "BLOCK",
                    "reason": f"tee output outside project: {dest}",
                    "category": "destructive",
                }
        return None

    def _is_outside_project(self, path: str) -> bool:
        """Check if a path is outside the project root."""
        if not path:
            return False

        # Relative paths (no leading / or ~) are assumed to be within CWD (project)
        if not path.startswith("/") and not path.startswith("~") and not path.startswith("$"):
            # But catch parent directory escapes
            if path.startswith("../") or path.startswith("../../"):
                return True
            return False

        # Expand ~ to home
        expanded = os.path.expanduser(path)
        # Expand $HOME
        if path.startswith("$HOME"):
            expanded = os.path.expandvars(path)

        # Normalize
        normalized = os.path.normpath(expanded)

        # Check if it's within the project root
        if self._project_root and normalized.startswith(self._project_root):
            return False

        # Any absolute path not in project = outside
        return True


def main():
    """PreToolUse hook entry point. Reads JSON from stdin, writes to stdout."""
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        hook_input = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    # Only process Bash tool calls
    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    # Extract the command
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")

    if not command:
        sys.exit(0)

    # Use CCA_PROJECT_ROOT env var if set, else cwd (so behavior is correct in any project).
    # CCA path is the last-resort fallback for backward compatibility.
    project_root = os.environ.get("CCA_PROJECT_ROOT") or os.getcwd() or \
        "/Users/matthewshields/Projects/ClaudeCodeAdvancements"

    guard = BashGuard(project_root=project_root)
    output = guard.hook_output(command)

    if output:
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
