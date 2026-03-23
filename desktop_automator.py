"""desktop_automator.py — MT-22: Claude Desktop App Automation.

Automates Claude.app (Electron) via AppleScript keystroke emulation.
Designed for supervised/unsupervised auto-loop on the desktop app.

Matthew directive (S130/S132): This is THE #1 priority. Automate
the Claude Code desktop Electron app so it runs 2-3 hour autonomous
sessions while Matthew watches and interacts freely.

Architecture:
- AppleScript for app control (activate, keystroke, window management)
- Clipboard-based prompt injection (reliable for long prompts)
- Conservative timeout-based response detection (no state access)
- Full audit logging (every action timestamped in JSONL)
- Safety: always verify frontmost app before sending keystrokes
"""

import json
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# --- Constants ---

BUNDLE_ID = "com.anthropic.claudefordesktop"
APP_NAME = "Claude"
DEFAULT_ACTIVATE_DELAY = 0.5  # seconds after activate before keystroke
DEFAULT_RESPONSE_TIMEOUT = 120  # seconds to wait for response
DEFAULT_AUDIT_LOG = Path.home() / ".cca-desktop-autoloop.jsonl"


# --- Data classes ---

@dataclass
class LoopConfig:
    """Configuration for the desktop auto-loop."""
    max_iterations: int = 50
    max_consecutive_failures: int = 3
    cooldown_seconds: int = 15
    response_timeout: int = DEFAULT_RESPONSE_TIMEOUT
    dry_run: bool = False


@dataclass
class LoopResult:
    """Result of a single loop iteration."""
    iteration: int
    success: bool
    prompt_length: int
    duration: float
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# --- Main class ---

class DesktopAutomator:
    """Controls Claude desktop app via AppleScript.

    Safety invariant: keystrokes are ONLY sent when Claude is verified
    as the frontmost application. Every action is audit-logged.
    """

    def __init__(
        self,
        activate_delay: float = DEFAULT_ACTIVATE_DELAY,
        response_timeout: int = DEFAULT_RESPONSE_TIMEOUT,
        audit_log: Path = DEFAULT_AUDIT_LOG,
        dry_run: bool = False,
    ):
        self.activate_delay = activate_delay
        self.response_timeout = response_timeout
        self.audit_log = Path(audit_log)
        self.dry_run = dry_run

    # --- Low-level AppleScript execution ---

    def _run_applescript(self, script: str) -> tuple:
        """Execute an AppleScript and return (success, output).

        In dry_run mode, logs the script and returns success without
        actually executing anything.
        """
        if self.dry_run:
            self._log("dry_run_applescript", {"script": script[:200]})
            return (True, "")
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return (result.returncode == 0, result.stdout.strip())
        except subprocess.TimeoutExpired:
            return (False, "timeout")
        except FileNotFoundError:
            return (False, "osascript not found")

    # --- Audit logging ---

    def _log(self, event: str, data: dict = None):
        """Append an event to the audit log (JSONL).

        Silently fails if the log file can't be written — automation
        should not break due to logging issues.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": event,
            **(data or {}),
        }
        try:
            with open(self.audit_log, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    # --- Process detection ---

    def is_claude_running(self) -> bool:
        """Check if Claude.app process is running."""
        script = (
            f'tell application "System Events" to '
            f'(name of processes) contains "{APP_NAME}"'
        )
        ok, output = self._run_applescript(script)
        return ok and output.lower() == "true"

    def get_frontmost_app(self) -> str:
        """Get the name of the frontmost application."""
        script = (
            'tell application "System Events" to name of first '
            'application process whose frontmost is true'
        )
        ok, output = self._run_applescript(script)
        return output if ok else ""

    def get_window_count(self) -> int:
        """Get the number of Claude windows. Returns -1 on error."""
        script = (
            f'tell application "System Events" to '
            f'count of windows of application process "{APP_NAME}"'
        )
        ok, output = self._run_applescript(script)
        if ok:
            try:
                return int(output)
            except ValueError:
                return -1
        return -1

    def get_claude_cpu_usage(self) -> float:
        """Get Claude.app CPU usage percentage. Returns -1.0 on error.

        Uses `ps` to check CPU usage of the Claude process.
        Useful for heuristic idle detection: when CPU drops below
        a threshold after being high, Claude likely finished responding.
        """
        if self.dry_run:
            return 0.0
        try:
            result = subprocess.run(
                ["ps", "-eo", "comm,%cpu"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.split("\n"):
                if "Claude" in line and "Helper" not in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            return float(parts[-1])
                        except ValueError:
                            continue
            return 0.0
        except (subprocess.TimeoutExpired, OSError):
            return -1.0

    def is_claude_idle(self, cpu_threshold: float = 5.0) -> bool:
        """Check if Claude.app appears idle (low CPU usage).

        A rough heuristic: when Claude is generating responses, the
        Electron renderer process uses significant CPU. When it drops
        below the threshold, the response is likely complete.

        This is NOT reliable for precise detection — use as a supplement
        to file-based detection (SESSION_RESUME.md mtime), not a replacement.
        """
        cpu = self.get_claude_cpu_usage()
        if cpu < 0:
            return False  # error — assume not idle
        return cpu < cpu_threshold

    # --- App control ---

    def activate_claude(self) -> bool:
        """Bring Claude app to foreground. Returns True if successful.

        Checks: (1) Claude is running, (2) activate succeeds,
        (3) Claude is actually frontmost after activation.
        """
        if not self.is_claude_running():
            self._log("activate_failed", {"reason": "claude_not_running"})
            return False

        script = f'tell application "{APP_NAME}" to activate'
        ok, _ = self._run_applescript(script)
        if not ok:
            self._log("activate_failed", {"reason": "applescript_error"})
            return False

        time.sleep(self.activate_delay)

        # Verify Claude is now frontmost
        frontmost = self.get_frontmost_app()
        if APP_NAME.lower() not in frontmost.lower():
            self._log(
                "activate_failed",
                {"reason": f"not_frontmost: {frontmost}"},
            )
            return False

        self._log("activate_success")
        return True

    def send_prompt(self, prompt: str) -> bool:
        """Send a prompt to Claude via clipboard + keystroke injection.

        Uses clipboard (not direct keystroke typing) for reliability
        with long and multi-line prompts. Sends with Cmd+Return.

        Safety: verifies Claude is frontmost before any keystroke.
        """
        if not prompt or not prompt.strip():
            self._log("send_failed", {"reason": "empty_prompt"})
            return False

        # Safety: verify Claude is frontmost
        frontmost = self.get_frontmost_app()
        if APP_NAME.lower() not in frontmost.lower():
            self._log(
                "send_failed",
                {"reason": f"wrong_app_frontmost: {frontmost}"},
            )
            return False

        # Step 1: Clear any existing text (Cmd+A, then Delete)
        self._run_applescript(
            'tell application "System Events" to keystroke "a" using command down'
        )
        time.sleep(0.1)
        self._run_applescript(
            'tell application "System Events" to key code 51'
        )  # Delete key
        time.sleep(0.1)

        # Step 2: Set clipboard to prompt text (escaped for AppleScript)
        escaped = prompt.replace("\\", "\\\\").replace('"', '\\"')
        self._run_applescript(f'set the clipboard to "{escaped}"')
        time.sleep(0.1)

        # Step 3: Paste from clipboard (Cmd+V)
        self._run_applescript(
            'tell application "System Events" to keystroke "v" using command down'
        )
        time.sleep(0.3)

        # Step 4: Send with Cmd+Return
        ok, _ = self._run_applescript(
            'tell application "System Events" to keystroke return using command down'
        )

        if ok:
            self._log("send_success", {"prompt_length": len(prompt)})
        else:
            self._log("send_failed", {"reason": "keystroke_error"})

        return ok

    def wait_for_response(self, timeout: int = None) -> bool:
        """Wait for Claude to finish responding.

        Since we cannot detect Claude's state (no API access to the
        Electron app), this uses a conservative timeout.

        Returns True after timeout (assumes response complete).
        """
        timeout = timeout or self.response_timeout
        self._log("waiting_for_response", {"timeout": timeout})

        if not self.dry_run:
            time.sleep(timeout)

        self._log("response_timeout_reached")
        return True

    def close_window(self) -> bool:
        """Close the active Claude window (Cmd+W).

        Safety: only sends keystroke if Claude is frontmost.
        """
        frontmost = self.get_frontmost_app()
        if APP_NAME.lower() not in frontmost.lower():
            self._log("close_failed", {"reason": f"wrong_app: {frontmost}"})
            return False

        ok, _ = self._run_applescript(
            'tell application "System Events" to keystroke "w" using command down'
        )
        self._log("close_window", {"success": ok})
        return ok

    def new_conversation(self) -> bool:
        """Start a new conversation (Cmd+N).

        Safety: only sends keystroke if Claude is frontmost.
        """
        frontmost = self.get_frontmost_app()
        if APP_NAME.lower() not in frontmost.lower():
            self._log(
                "new_conversation_failed",
                {"reason": f"wrong_app: {frontmost}"},
            )
            return False

        ok, _ = self._run_applescript(
            'tell application "System Events" to keystroke "n" using command down'
        )
        self._log("new_conversation", {"success": ok})
        return ok

    # --- Pre-flight ---

    def preflight(self) -> dict:
        """Run pre-flight checks. Returns dict of check results.

        Checks:
        - osascript available
        - Claude.app installed
        - Claude.app running
        - Audit log writable
        """
        checks = {}

        # 1. osascript available
        try:
            subprocess.run(
                ["osascript", "-e", "return 1"],
                capture_output=True,
                timeout=5,
            )
            checks["osascript"] = "PASS"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            checks["osascript"] = "FAIL"

        # 2. Claude.app installed
        app_path = Path("/Applications/Claude.app")
        checks["claude_installed"] = "PASS" if app_path.exists() else "FAIL"

        # 3. Claude.app running
        checks["claude_running"] = "PASS" if self.is_claude_running() else "WARN"

        # 4. Audit log directory writable
        try:
            self.audit_log.parent.mkdir(parents=True, exist_ok=True)
            checks["audit_log"] = "PASS"
        except OSError:
            checks["audit_log"] = "FAIL"

        self._log("preflight", checks)
        return checks

    # --- Loop iteration ---

    def run_loop_iteration(self, prompt: str, timeout: int = None) -> dict:
        """Run one full loop iteration: activate -> send -> wait.

        Returns dict with success status and timing.
        """
        start = time.time()
        result = {"success": False, "prompt_length": len(prompt)}

        # Step 1: Activate Claude
        if not self.activate_claude():
            result["error"] = "activate_failed"
            result["duration"] = time.time() - start
            return result

        # Step 2: Send prompt
        if not self.send_prompt(prompt):
            result["error"] = "send_failed"
            result["duration"] = time.time() - start
            return result

        # Step 3: Wait for response
        self.wait_for_response(timeout)

        result["success"] = True
        result["duration"] = time.time() - start
        self._log("loop_iteration_complete", result)
        return result


# --- CLI ---

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: desktop_automator.py <command> [args]")
        print("Commands:")
        print("  preflight          Run pre-flight checks")
        print("  activate           Activate Claude window")
        print("  send <prompt>      Send a prompt to Claude")
        print("  status             Show Claude process status")
        print("  windows            Show Claude window count")
        print("  dry-run <prompt>   Full iteration in dry-run mode")
        sys.exit(1)

    cmd = sys.argv[1]
    da = DesktopAutomator()

    if cmd == "preflight":
        checks = da.preflight()
        for k, v in checks.items():
            status = "PASS" if v == "PASS" else ("WARN" if v == "WARN" else "FAIL")
            print(f"  {k}: {v}")
        failed = [k for k, v in checks.items() if v == "FAIL"]
        sys.exit(1 if failed else 0)

    elif cmd == "activate":
        ok = da.activate_claude()
        print(f"Activate: {'OK' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)

    elif cmd == "send":
        if len(sys.argv) < 3:
            print("Usage: desktop_automator.py send <prompt>")
            sys.exit(1)
        prompt = " ".join(sys.argv[2:])
        ok = da.send_prompt(prompt)
        print(f"Send: {'OK' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)

    elif cmd == "status":
        running = da.is_claude_running()
        frontmost = da.get_frontmost_app()
        print(f"Claude running: {running}")
        print(f"Frontmost app: {frontmost}")

    elif cmd == "windows":
        count = da.get_window_count()
        print(f"Claude windows: {count}")

    elif cmd == "dry-run":
        prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "/cca-init"
        da_dry = DesktopAutomator(dry_run=True, activate_delay=0)
        result = da_dry.run_loop_iteration(prompt)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
