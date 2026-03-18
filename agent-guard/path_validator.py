#!/usr/bin/env python3
"""
path_validator.py — AG-7: Dangerous path and command detection for Agent Guard.

Catches:
- File writes to system directories (/etc, /System, /usr, /Library)
- Path traversal attacks (../../etc/passwd)
- Destructive shell commands (rm -rf /, dd, mkfs, chmod on system files)
- Pipe-to-bash patterns (curl | bash)
- Drive-wiping commands (rmdir /s /q F:\\)

Levels:
- BLOCK: definitely dangerous, deny the operation
- WARN: potentially dangerous, inject warning context
- PASS: safe, allow the operation

Usage as library:
    v = PathValidator(project_root="/path/to/project")
    result = v.check("/etc/passwd")           # {"level": "BLOCK", "reason": "..."}
    result = v.check_command("rm -rf /")      # {"level": "BLOCK", "reason": "..."}

Usage as PreToolUse hook:
    Reads JSON from stdin, writes JSON to stdout.
    Checks Write/Edit file_path and Bash command for dangerous patterns.

Stdlib only. No external dependencies.
"""

import os
import re
import sys


# System directories that should never be written to
SYSTEM_DIRS = (
    "/etc", "/System", "/Library", "/usr", "/bin", "/sbin",
    "/var", "/private", "/boot", "/dev", "/proc", "/sys",
)

# Destructive command patterns (regex)
DESTRUCTIVE_COMMANDS = [
    # rm -rf on root, home, or drive letters
    (r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|(-[a-zA-Z]*f[a-zA-Z]*r))\s+(/\s|/\"|/$)", "rm -rf root"),
    (r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|(-[a-zA-Z]*f[a-zA-Z]*r))\s+(~/?(\s|$|\"|')|\$HOME)", "rm -rf home"),
    (r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|(-[a-zA-Z]*f[a-zA-Z]*r))\s+`", "rm -rf with command substitution"),
    # Windows drive wipe
    (r"rmdir\s+/s\s+/q\s+[A-Z]:\\", "Windows drive wipe"),
    # dd to disk device
    (r"dd\s+.*of=/dev/[sh]d", "dd to disk device"),
    # mkfs on any device
    (r"mkfs", "filesystem format"),
    # chmod on system files
    (r"chmod\s+\d+\s+/(etc|usr|bin|sbin|System|Library)", "chmod on system directory"),
    # Pipe to shell
    (r"curl\s+.*\|\s*(ba)?sh", "curl pipe to shell"),
    (r"wget\s+.*\|\s*(ba)?sh", "wget pipe to shell"),
]

# Warned command patterns (less severe)
WARNED_COMMANDS = [
    (r"git\s+reset\s+--hard", "git reset --hard (destructive)"),
    (r"git\s+push\s+.*--force", "git force push"),
    (r"git\s+clean\s+-[a-zA-Z]*f", "git clean (deletes files)"),
]


class PathValidator:
    """Validates file paths and shell commands for safety."""

    def __init__(self, project_root: str = ""):
        self._project_root = os.path.normpath(project_root) if project_root else ""

    def check(self, path) -> dict:
        """Check a file path for safety.

        Returns: {"level": "PASS"|"WARN"|"BLOCK", "reason": str}
        """
        if not path:
            return {"level": "PASS", "reason": ""}

        # Detect traversal BEFORE normalization
        raw = str(path)
        has_traversal = ".." in raw

        # Normalize the path (resolve .., //, etc.)
        resolved = os.path.normpath(os.path.expanduser(raw))

        # If it's relative and we have a project root, make it absolute
        if not os.path.isabs(resolved) and self._project_root:
            resolved = os.path.normpath(os.path.join(self._project_root, resolved))

        # Check for path traversal: if after normalization it escapes project
        if self._project_root and os.path.isabs(resolved):
            if not resolved.startswith(self._project_root):
                # Path traversal that escapes project is always BLOCK
                if has_traversal:
                    return {
                        "level": "BLOCK",
                        "reason": f"Path traversal escapes project root: {raw} -> {resolved}",
                    }
                # Outside project — check if it's a system dir
                for sys_dir in SYSTEM_DIRS:
                    if resolved == sys_dir or resolved.startswith(sys_dir + "/"):
                        return {
                            "level": "BLOCK",
                            "reason": f"Path targets system directory: {sys_dir}",
                        }
                # Root path
                if resolved == "/":
                    return {
                        "level": "BLOCK",
                        "reason": "Path targets filesystem root",
                    }
                # Home dotfiles
                home = os.path.expanduser("~")
                if resolved.startswith(home + "/."):
                    return {
                        "level": "WARN",
                        "reason": f"Path targets home dotfile: {resolved}",
                    }
                # General outside-project
                return {
                    "level": "WARN",
                    "reason": f"Path is outside project root: {resolved}",
                }

        # Inside project or relative — safe
        return {"level": "PASS", "reason": ""}

    def check_command(self, command) -> dict:
        """Check a shell command for dangerous patterns.

        Returns: {"level": "PASS"|"WARN"|"BLOCK", "reason": str}
        """
        if not command:
            return {"level": "PASS", "reason": ""}

        cmd = str(command)

        # Check destructive patterns
        for pattern, desc in DESTRUCTIVE_COMMANDS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return {
                    "level": "BLOCK",
                    "reason": f"Destructive command detected: {desc}",
                }

        # Check warned patterns
        for pattern, desc in WARNED_COMMANDS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return {
                    "level": "WARN",
                    "reason": f"Potentially dangerous: {desc}",
                }

        return {"level": "PASS", "reason": ""}


def main():
    """PreToolUse hook entry point. Reads JSON from stdin, writes JSON to stdout."""
    import json

    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    cwd = hook_input.get("cwd", "")

    validator = PathValidator(project_root=cwd)

    # Check file paths for Write/Edit
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        result = validator.check(file_path)
        if result["level"] == "BLOCK":
            json.dump({
                "hookSpecificOutput": {
                    "permissionDecision": "deny",
                    "reason": result["reason"],
                }
            }, sys.stdout)
            return
        elif result["level"] == "WARN":
            json.dump({
                "hookSpecificOutput": {
                    "additionalContext": f"PATH WARNING: {result['reason']}",
                }
            }, sys.stdout)
            return

    # Check commands for Bash
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        result = validator.check_command(command)
        if result["level"] == "BLOCK":
            json.dump({
                "hookSpecificOutput": {
                    "permissionDecision": "deny",
                    "reason": result["reason"],
                }
            }, sys.stdout)
            return
        elif result["level"] == "WARN":
            json.dump({
                "hookSpecificOutput": {
                    "additionalContext": f"COMMAND WARNING: {result['reason']}",
                }
            }, sys.stdout)
            return

    # Default: allow
    json.dump({}, sys.stdout)


if __name__ == "__main__":
    main()
