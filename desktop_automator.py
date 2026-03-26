"""desktop_automator.py — MT-22: Claude Desktop App Automation.

Automates Claude.app (Electron) via AppleScript + CoreGraphics.
Designed for supervised/unsupervised auto-loop on the desktop app.

Matthew directive (S130/S132): This is THE #1 priority. Automate
the Claude Code desktop Electron app so it runs 2-3 hour autonomous
sessions while Matthew watches and interacts freely.

Architecture:
- AppleScript for app control (activate, keystroke, window management)
- CoreGraphics for coordinate-based mouse clicks (tab switching)
- Clipboard-based prompt injection (reliable for long prompts)
- Conservative timeout-based response detection (no state access)
- Full audit logging (every action timestamped in JSONL)
- Safety: always verify frontmost app before sending keystrokes

Tab switching (S140): Electron ignores AppleScript keystrokes (Cmd+3)
for tab switching. CoreGraphics CGEvent mouse clicks work because they
go through the HID event tap — same path as physical mouse clicks.
"""

import ctypes
import ctypes.util
import json
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# --- Constants ---

BUNDLE_ID = "com.anthropic.claudefordesktop"
APP_NAME = "Claude"
DEFAULT_ACTIVATE_DELAY = 0.5  # seconds after activate before keystroke
DEFAULT_RESPONSE_TIMEOUT = 120  # seconds to wait for response
DEFAULT_AUDIT_LOG = Path.home() / ".cca-desktop-autoloop.jsonl"

# Tab geometry constants (derived from Claude.app layout analysis, S140)
# The tab island [Chat | Cowork | Code] is centered in the window header.
# Each tab is ~55-65 points wide. Code is the rightmost tab.
TAB_Y_OFFSET = 10       # points below window top edge to tab center
TAB_ISLAND_WIDTH = 195   # approximate total width of the 3-tab island
TAB_WIDTH = 65           # approximate width per tab
# Offsets from window center X to each tab center:
TAB_OFFSETS = {"Chat": -65, "Cowork": 0, "Code": 65}

# "+ New session" button geometry (top-left sidebar on Code tab)
# Calibrated via live cursor sweep with Matthew (S140).
# Button is in the left sidebar, below the tab bar.
NEW_SESSION_BTN_X_OFFSET = 70   # from window left edge to button center
NEW_SESSION_BTN_Y_OFFSET = 60   # from window top edge to button center (39+60=99)

# Model selector button geometry (bottom-right of Code tab input area, S186)
# The model button shows current model name (e.g. "Opus 4.6 (1M context) v").
# Position is relative to window edges. Needs live calibration if UI changes.
MODEL_BTN_X_FROM_RIGHT = 100    # points from window right edge to button center (calibrated S186)
MODEL_BTN_Y_FROM_BOTTOM = 33    # points from window bottom edge to button center

# Model dropdown option offsets (relative to button, negative = upward)
# When the dropdown opens, options are listed vertically above the button.
# Each option is approximately 36px tall. Order may vary — calibrate if needed.
# These are Y offsets from the model button center to each option center.
MODEL_OPTION_OFFSETS = {
    "opus-4-6-1m": -40,    # "Opus 4.6 (1M context)" — target for autoloop
    "opus-4-6": -76,       # "Opus 4.6"
    "sonnet-4-6": -112,    # "Sonnet 4.6"
    "haiku-4-5": -148,     # "Haiku 4.5"
}


# --- CoreGraphics mouse click (ctypes) ---

class _CGPoint(ctypes.Structure):
    """CoreGraphics CGPoint for mouse event coordinates."""
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


def _load_cg():
    """Load CoreGraphics framework. Returns None if unavailable."""
    try:
        path = ctypes.util.find_library('CoreGraphics')
        if not path:
            return None
        cg = ctypes.cdll.LoadLibrary(path)
        # Set up function signatures
        cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
        cg.CGEventCreateMouseEvent.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, _CGPoint, ctypes.c_uint32,
        ]
        cg.CGEventPost.restype = None
        cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        cg.CFRelease.restype = None
        cg.CFRelease.argtypes = [ctypes.c_void_p]
        # Idle time detection (MT-35 Phase 2)
        cg.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
        cg.CGEventSourceSecondsSinceLastEventType.argtypes = [
            ctypes.c_int32, ctypes.c_uint32,
        ]
        return cg
    except (OSError, AttributeError):
        return None


# Lazy-load CoreGraphics (loaded on first use)
_cg_lib = None


def _get_cg():
    """Get CoreGraphics library (lazy singleton)."""
    global _cg_lib
    if _cg_lib is None:
        _cg_lib = _load_cg()
    return _cg_lib


# CGEvent constants
_kCGEventLeftMouseDown = 1
_kCGEventLeftMouseUp = 2
_kCGHIDEventTap = 0
# CGEventSourceStateID for combined HID state (all input devices)
_kCGEventSourceStateCombinedSessionState = 0
# CGEventType for "any input" — kCGAnyInputEventType
_kCGAnyInputEventType = 0xFFFFFFFF
_kCGEventMouseMoved = 5


def cg_move_to(x: float, y: float) -> bool:
    """Move mouse cursor to (x, y) WITHOUT clicking. For calibration."""
    cg = _get_cg()
    if cg is None:
        return False
    point = _CGPoint(x, y)
    move = cg.CGEventCreateMouseEvent(None, _kCGEventMouseMoved, point, 0)
    if not move:
        return False
    cg.CGEventPost(_kCGHIDEventTap, move)
    cg.CFRelease(move)
    return True


def cg_click_at(x: float, y: float) -> bool:
    """Click at screen coordinates (x, y) using CoreGraphics.

    Uses CGEventCreateMouseEvent + CGEventPost to send mouse down/up
    through the HID event tap — identical to a physical mouse click.
    This works where AppleScript keystrokes fail (Electron tab switching).

    Args:
        x: Screen X coordinate in points (not pixels)
        y: Screen Y coordinate in points (not pixels)

    Returns True if the click was posted successfully.
    """
    cg = _get_cg()
    if cg is None:
        return False

    point = _CGPoint(x, y)
    down = cg.CGEventCreateMouseEvent(
        None, _kCGEventLeftMouseDown, point, 0
    )
    up = cg.CGEventCreateMouseEvent(
        None, _kCGEventLeftMouseUp, point, 0
    )

    if not down or not up:
        if down:
            cg.CFRelease(down)
        if up:
            cg.CFRelease(up)
        return False

    cg.CGEventPost(_kCGHIDEventTap, down)
    time.sleep(0.05)
    cg.CGEventPost(_kCGHIDEventTap, up)

    cg.CFRelease(down)
    cg.CFRelease(up)
    return True


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
        self.saved_frontmost_app: Optional[str] = None

    # --- Low-level AppleScript execution ---

    def _run_applescript(self, script: str) -> tuple:
        """Execute an AppleScript and return (success, output).

        In dry_run mode, logs the script and returns plausible output
        so the full flow can be simulated end-to-end.
        """
        if self.dry_run:
            self._log("dry_run_applescript", {"script": script[:200]})
            # Return plausible output for common checks
            if "name of processes" in script:
                return (True, "true")  # is_claude_running
            if "frontmost is true" in script:
                return (True, APP_NAME)  # get_frontmost_app
            if "count of windows" in script:
                return (True, "1")  # get_window_count
            if "keystroke" in script and "using command down" in script:
                return (True, "")  # tab switch or other keystroke
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

    # --- Window geometry ---

    def get_window_geometry(self) -> Optional[Tuple[int, int, int, int]]:
        """Get Claude window position and size as (x, y, width, height).

        Returns None if window info can't be retrieved.
        Coordinates are in macOS screen points (not pixels).
        """
        script = (
            'tell application "System Events" to tell process "Claude" to '
            'get {position, size} of window 1'
        )
        ok, output = self._run_applescript(script)
        if not ok:
            return None
        try:
            # Output format: "x, y, width, height"
            parts = [int(p.strip()) for p in output.split(",")]
            if len(parts) == 4:
                return (parts[0], parts[1], parts[2], parts[3])
        except (ValueError, IndexError):
            pass
        return None

    def get_tab_coordinates(self, tab_name: str) -> Optional[Tuple[float, float]]:
        """Calculate screen coordinates for a tab click target.

        Uses window geometry to find the center of the requested tab
        in the top-center island bar: [Chat | Cowork | Code].

        Args:
            tab_name: One of "Chat", "Cowork", "Code"

        Returns (x, y) screen coordinates in points, or None on error.
        """
        if tab_name not in TAB_OFFSETS:
            return None

        geom = self.get_window_geometry()
        if geom is None:
            # Dry run fallback: use reasonable defaults
            if self.dry_run:
                return (727.0, 49.0)
            return None

        win_x, win_y, win_w, win_h = geom
        center_x = win_x + win_w / 2.0
        tab_x = center_x + TAB_OFFSETS[tab_name]
        tab_y = win_y + TAB_Y_OFFSET
        return (tab_x, tab_y)

    # --- Tab switching (Chat / Cowork / Code) ---

    # Claude desktop app has 3 tabs in a top-center island:
    #   Chat | Cowork | Code
    # The autoloop MUST be on the Code tab.
    #
    # S139: AppleScript keystrokes (Cmd+1/2/3) do NOT work — Electron
    # intercepts them differently from physical keyboard input.
    #
    # S140: CoreGraphics CGEvent mouse clicks DO work — they go through
    # the HID event tap, same path as physical mouse clicks. We calculate
    # tab coordinates from window geometry and click directly.
    #
    # Fallback: if CoreGraphics is unavailable, try Cmd+3 keystroke.

    VALID_TABS = {"Chat", "Cowork", "Code"}
    TAB_SHORTCUTS = {"Chat": "1", "Cowork": "2", "Code": "3"}

    def click_tab(self, tab_name: str) -> bool:
        """Click a tab using CoreGraphics coordinate-based mouse click.

        This is the PRIMARY tab switching method (S140). It calculates
        the screen coordinates of the tab from window geometry and posts
        a CGEvent mouse click — identical to a physical mouse click.

        Args:
            tab_name: One of "Chat", "Cowork", "Code"

        Returns True if the click was posted successfully.
        """
        if tab_name not in TAB_OFFSETS:
            self._log("click_tab_failed", {"reason": f"invalid_tab: {tab_name}"})
            return False

        coords = self.get_tab_coordinates(tab_name)
        if coords is None:
            self._log("click_tab_failed", {"reason": "no_window_geometry"})
            return False

        x, y = coords
        if self.dry_run:
            self._log("click_tab_dry_run", {
                "tab": tab_name, "x": x, "y": y,
            })
            return True

        ok = cg_click_at(x, y)
        self._log("click_tab", {
            "tab": tab_name, "x": x, "y": y, "success": ok,
            "method": "CoreGraphics",
        })

        if ok:
            time.sleep(0.3)  # Let Electron process the click

        return ok

    def switch_to_tab(self, tab_name: str) -> bool:
        """Switch to a tab. Tries CoreGraphics click first, falls back to Cmd+N.

        Args:
            tab_name: One of "Chat", "Cowork", "Code"

        Returns True if the tab switch was attempted successfully.
        """
        if tab_name not in self.VALID_TABS:
            self._log("switch_to_tab_failed", {"reason": f"invalid_tab: {tab_name}"})
            return False

        frontmost = self.get_frontmost_app()
        if APP_NAME.lower() not in frontmost.lower():
            self._log("switch_to_tab_failed", {
                "reason": f"wrong_app: {frontmost}",
                "target_tab": tab_name,
            })
            return False

        # Primary: CoreGraphics coordinate click (S140)
        if _get_cg() is not None:
            ok = self.click_tab(tab_name)
            if ok:
                return True
            self._log("switch_to_tab_cg_fallthrough", {"tab": tab_name})

        # Fallback: AppleScript keystroke (unreliable on Electron, S139)
        key = self.TAB_SHORTCUTS[tab_name]
        ok, _ = self._run_applescript(
            f'tell application "System Events" to keystroke "{key}" using command down'
        )
        self._log("switch_to_tab_fallback", {
            "tab": tab_name, "key": f"Cmd+{key}", "success": ok,
            "method": "AppleScript_keystroke",
        })
        if ok and not self.dry_run:
            time.sleep(0.3)
        return ok

    def ensure_code_tab(self) -> bool:
        """Ensure the Code tab is active.

        Uses CoreGraphics coordinate click (primary, S140) with
        AppleScript keystroke fallback. Idempotent — clicking Code
        when already on Code is a no-op.

        Requires Claude to be frontmost (call activate_claude() first).
        """
        ok = self.switch_to_tab("Code")
        self._log("ensure_code_tab", {
            "success": ok,
            "method": "CoreGraphics" if _get_cg() is not None else "AppleScript",
        })
        return ok

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

    def save_frontmost_app(self) -> Optional[str]:
        """Save the current frontmost app so it can be restored after autoloop trigger.

        MT-35: Non-intrusive autoloop. Saves the app Matthew is using so we can
        switch back to it after spawning a new CCA session.

        Returns the app name if saved, None if Claude is already frontmost or error.
        """
        app = self.get_frontmost_app()
        if not app:
            self._log("save_frontmost_skipped", {"reason": "no_frontmost_detected"})
            self.saved_frontmost_app = None
            return None

        # If Claude is already frontmost, nothing to save/restore
        if APP_NAME.lower() in app.lower():
            self._log("save_frontmost_skipped", {"reason": "claude_already_frontmost"})
            self.saved_frontmost_app = None
            return None

        self.saved_frontmost_app = app
        self._log("save_frontmost", {"app": app})
        return app

    def restore_frontmost_app(self) -> bool:
        """Restore the previously frontmost app after autoloop trigger completes.

        MT-35: Returns focus to whatever Matthew was doing before the trigger
        stole the screen for a few seconds.

        Returns True if restoration succeeded, False if nothing to restore or error.
        """
        if not self.saved_frontmost_app:
            return False

        app = self.saved_frontmost_app
        script = f'tell application "{app}" to activate'
        ok, _ = self._run_applescript(script)

        if ok:
            self._log("restore_frontmost", {"app": app})
            self.saved_frontmost_app = None
            return True
        else:
            self._log("restore_frontmost_failed", {"app": app})
            return False

    def get_user_idle_seconds(self) -> "float | None":
        """Get seconds since last user input (mouse/keyboard).

        MT-35 Phase 2: Uses CoreGraphics CGEventSourceSecondsSinceLastEventType
        to detect how long the user has been idle. This lets the autoloop wait
        for a quiet moment before stealing focus.

        Returns float (seconds idle) or None if CG is unavailable.
        In dry_run mode, returns 999.0 (simulates idle user).
        """
        if self.dry_run:
            self._log("idle_check", {"idle_seconds": 999.0, "dry_run": True})
            return 999.0

        cg = _get_cg()
        if cg is None:
            self._log("idle_check", {"idle_seconds": None, "cg_unavailable": True})
            return None

        try:
            idle = cg.CGEventSourceSecondsSinceLastEventType(
                _kCGEventSourceStateCombinedSessionState,
                _kCGAnyInputEventType,
            )
            self._log("idle_check", {"idle_seconds": round(idle, 2)})
            return float(idle)
        except (OSError, ctypes.ArgumentError) as e:
            self._log("idle_check", {"idle_seconds": None, "error": str(e)})
            return None

    def wait_for_idle(
        self,
        idle_threshold: float = 3.0,
        timeout: float = 30.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """Wait until the user has been idle for idle_threshold seconds.

        MT-35 Phase 2: Polls get_user_idle_seconds() until the user is idle
        or the timeout expires. This prevents the autoloop from interrupting
        Matthew while he's actively typing or clicking.

        Args:
            idle_threshold: Seconds of idle time required before proceeding.
            timeout: Max seconds to wait. If user never goes idle, proceed anyway.
            poll_interval: Seconds between idle checks.

        Returns True if idle detected (or CG unavailable — fail open).
        Returns False only if timeout expired while user was active.
        """
        if idle_threshold <= 0:
            self._log("wait_for_idle", {"idle_detected": True, "reason": "zero_threshold"})
            return True

        start = time.monotonic()
        while True:
            idle = self.get_user_idle_seconds()

            # If CG is unavailable, fail open — don't block the trigger
            if idle is None:
                self._log("wait_for_idle", {"idle_detected": True, "reason": "cg_unavailable"})
                return True

            if idle >= idle_threshold:
                self._log("wait_for_idle", {
                    "idle_detected": True,
                    "idle_seconds": round(idle, 2),
                    "waited": round(time.monotonic() - start, 2),
                })
                return True

            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                self._log("wait_for_idle", {
                    "idle_detected": False,
                    "idle_seconds": round(idle, 2),
                    "waited": round(elapsed, 2),
                    "reason": "timeout",
                })
                return False

            time.sleep(poll_interval)

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

    def get_new_session_button_coordinates(self) -> Optional[Tuple[float, float]]:
        """Calculate screen coordinates for the '+ New session' button.

        The button is in the top-left sidebar, visible on the Code tab.
        Returns (x, y) screen coordinates in points, or None on error.
        """
        geom = self.get_window_geometry()
        if geom is None:
            if self.dry_run:
                return (70.0, 90.0)
            return None

        win_x, win_y, win_w, win_h = geom
        btn_x = win_x + NEW_SESSION_BTN_X_OFFSET
        btn_y = win_y + NEW_SESSION_BTN_Y_OFFSET
        return (btn_x, btn_y)

    def click_new_session_button(self) -> bool:
        """Click the '+ New session' button using CoreGraphics.

        This replaces Cmd+N which Electron intercepts and routes to Chat.
        The button is only visible/functional on the Code tab.

        Returns True if the click was posted successfully.
        """
        coords = self.get_new_session_button_coordinates()
        if coords is None:
            self._log("click_new_session_failed", {"reason": "no_coordinates"})
            return False

        x, y = coords
        if self.dry_run:
            self._log("click_new_session_dry_run", {"x": x, "y": y})
            return True

        ok = cg_click_at(x, y)
        self._log("click_new_session", {
            "x": x, "y": y, "success": ok,
            "method": "CoreGraphics",
        })
        return ok

    def get_model_button_coordinates(self) -> Optional[Tuple[float, float]]:
        """Calculate screen coordinates for the model selector button.

        The model button is at the bottom-right of the Code tab input area.
        Returns (x, y) screen coordinates in points, or None on error.
        """
        geom = self.get_window_geometry()
        if geom is None:
            if self.dry_run:
                return (900.0, 750.0)
            return None

        win_x, win_y, win_w, win_h = geom
        btn_x = win_x + win_w - MODEL_BTN_X_FROM_RIGHT
        btn_y = win_y + win_h - MODEL_BTN_Y_FROM_BOTTOM
        return (btn_x, btn_y)

    def click_model_button(self) -> bool:
        """Click the model selector button to open the dropdown.

        Returns True if the click was posted successfully.
        """
        coords = self.get_model_button_coordinates()
        if coords is None:
            self._log("click_model_button_failed", {"reason": "no_coordinates"})
            return False

        x, y = coords
        if self.dry_run:
            self._log("click_model_button_dry_run", {"x": x, "y": y})
            return True

        ok = cg_click_at(x, y)
        self._log("click_model_button", {"x": x, "y": y, "success": ok})
        if ok:
            time.sleep(0.3)
        return ok

    def set_model_via_ui(self, model_key: str = "opus-4-6-1m") -> bool:
        """Set the model via UI dropdown click (no /model command needed).

        Steps:
        1. Click model selector button to open dropdown
        2. Wait for dropdown to appear
        3. Click the target model option by coordinate offset

        Args:
            model_key: Key from MODEL_OPTION_OFFSETS dict.
                       Default "opus-4-6-1m" = Opus 4.6 (1M context).

        Returns True if all clicks posted successfully.
        Note: Coordinate offsets may need live calibration (S186).
        """
        if model_key not in MODEL_OPTION_OFFSETS:
            self._log("set_model_failed", {"reason": f"unknown_model: {model_key}"})
            return False

        # Safety: verify Claude is frontmost
        frontmost = self.get_frontmost_app()
        if APP_NAME.lower() not in frontmost.lower():
            self._log("set_model_failed", {"reason": f"wrong_app: {frontmost}"})
            return False

        # Step 1: Click model button to open dropdown
        if not self.click_model_button():
            self._log("set_model_failed", {"reason": "button_click_failed"})
            return False

        # Step 2: Wait for dropdown to appear
        if not self.dry_run:
            time.sleep(0.5)

        # Step 3: Click the target model option
        btn_coords = self.get_model_button_coordinates()
        if btn_coords is None:
            self._log("set_model_failed", {"reason": "no_coordinates_for_option"})
            return False

        btn_x, btn_y = btn_coords
        offset_y = MODEL_OPTION_OFFSETS[model_key]
        target_x = btn_x
        target_y = btn_y + offset_y

        if self.dry_run:
            self._log("set_model_dry_run", {
                "model": model_key, "x": target_x, "y": target_y,
                "offset_y": offset_y,
            })
            return True

        ok = cg_click_at(target_x, target_y)
        self._log("set_model_click", {
            "model": model_key, "x": target_x, "y": target_y,
            "offset_y": offset_y, "success": ok,
        })

        if ok:
            time.sleep(0.5)  # Wait for model to switch

        return ok

    def new_conversation(self) -> bool:
        """Start a new conversation on the Code tab.

        Uses CoreGraphics clicks ONLY — no AppleScript keystrokes.
        Electron intercepts programmatic Cmd+N and routes to Chat (S140).

        Steps:
        1. Click Code tab (CoreGraphics) — ensure correct tab
        2. Wait for Electron to settle
        3. Click '+ New session' button (CoreGraphics) — NOT Cmd+N
        """
        # Step 1: Ensure Code tab via CoreGraphics click
        if not self.ensure_code_tab():
            self._log("new_conversation_failed", {"reason": "code_tab_unreachable"})
            return False

        # Step 2: Wait for tab switch to settle (Electron rendering)
        if not self.dry_run:
            time.sleep(0.5)

        frontmost = self.get_frontmost_app()
        if APP_NAME.lower() not in frontmost.lower():
            self._log(
                "new_conversation_failed",
                {"reason": f"wrong_app: {frontmost}"},
            )
            return False

        # Step 3: Click "+ New session" button (CoreGraphics, NOT Cmd+N)
        ok = self.click_new_session_button()

        self._log("new_conversation", {"success": ok, "method": "CoreGraphics_button_click"})
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
        """Run one full loop iteration: activate -> ensure Code tab -> send -> wait.

        Returns dict with success status and timing.
        """
        start = time.time()
        result = {"success": False, "prompt_length": len(prompt)}

        # Step 1: Activate Claude
        if not self.activate_claude():
            result["error"] = "activate_failed"
            result["duration"] = time.time() - start
            return result

        # Step 2: Ensure Code tab is active (not Chat or Cowork)
        if not self.ensure_code_tab():
            result["error"] = "code_tab_failed"
            result["duration"] = time.time() - start
            return result

        # Step 3: Send prompt
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

    elif cmd == "calibrate-model":
        # Move cursor to model button position (no click) for visual verification.
        # Usage: python3 desktop_automator.py calibrate-model [X_FROM_RIGHT]
        x_override = int(sys.argv[2]) if len(sys.argv) > 2 else None
        geom = da.get_window_geometry()
        if geom is None:
            print("ERROR: Could not get Claude window geometry.")
            sys.exit(1)
        win_x, win_y, win_w, win_h = geom
        x_from_right = x_override if x_override else MODEL_BTN_X_FROM_RIGHT
        btn_x = win_x + win_w - x_from_right
        btn_y = win_y + win_h - MODEL_BTN_Y_FROM_BOTTOM
        print(f"Window: {win_w}x{win_h} at ({win_x},{win_y})")
        print(f"Model button: X_FROM_RIGHT={x_from_right}, Y_FROM_BOTTOM={MODEL_BTN_Y_FROM_BOTTOM}")
        print(f"Moving cursor to ({btn_x}, {btn_y}) — look at where the cursor lands!")
        print(f"  If too far LEFT:  decrease X_FROM_RIGHT (try {x_from_right - 10})")
        print(f"  If too far RIGHT: increase X_FROM_RIGHT (try {x_from_right + 10})")
        ok = cg_move_to(btn_x, btn_y)
        if ok:
            print(f"Cursor moved. Is it on the model button?")
        else:
            print("ERROR: Could not move cursor (CoreGraphics failed).")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
