#!/usr/bin/env python3
"""autoloop_pause.py — Pause/resume the CCA desktop autoloop (MT-35 Phase 4).

Toggles a flag file (~/.cca-autoloop-paused) that both the stop hook and
the trigger check before spawning the next session. When paused, the loop
stays enabled but skips triggering until unpaused.

Usage:
    python3 autoloop_pause.py toggle    # Toggle pause state
    python3 autoloop_pause.py pause     # Pause the loop
    python3 autoloop_pause.py resume    # Resume the loop
    python3 autoloop_pause.py status    # Show current state

S152 — MT-35 Phase 4: keyboard shortcut to pause/resume loop.
"""

import os
import sys
import time

PAUSE_FILE = os.path.expanduser("~/.cca-autoloop-paused")
ENABLED_FILE = os.path.expanduser("~/.cca-autoloop-enabled")


def is_paused() -> bool:
    """Check if autoloop is paused."""
    return os.path.exists(PAUSE_FILE)


def is_enabled() -> bool:
    """Check if autoloop is enabled."""
    env_val = os.environ.get("CCA_AUTOLOOP_ENABLED")
    if env_val is not None:
        return env_val == "1"
    return os.path.exists(ENABLED_FILE)


def pause():
    """Pause the autoloop."""
    with open(PAUSE_FILE, "w") as f:
        f.write(str(time.time()))
    return True


def resume():
    """Resume the autoloop."""
    try:
        os.unlink(PAUSE_FILE)
        return True
    except FileNotFoundError:
        return True  # Already unpaused
    except OSError:
        return False


def toggle() -> bool:
    """Toggle pause state. Returns True if now paused, False if now resumed."""
    if is_paused():
        resume()
        return False
    else:
        pause()
        return True


def status() -> dict:
    """Get current autoloop state."""
    paused = is_paused()
    enabled = is_enabled()
    pause_since = None
    if paused:
        try:
            with open(PAUSE_FILE) as f:
                pause_since = float(f.read().strip())
        except (OSError, ValueError):
            pass
    return {
        "enabled": enabled,
        "paused": paused,
        "effective": enabled and not paused,
        "pause_since": pause_since,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: autoloop_pause.py [toggle|pause|resume|status]")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "toggle":
        now_paused = toggle()
        state = "PAUSED" if now_paused else "RUNNING"
        print(f"Autoloop: {state}")
    elif cmd == "pause":
        pause()
        print("Autoloop: PAUSED")
    elif cmd == "resume":
        resume()
        print("Autoloop: RUNNING")
    elif cmd == "status":
        s = status()
        enabled = "enabled" if s["enabled"] else "disabled"
        paused = " (PAUSED)" if s["paused"] else ""
        effective = "ACTIVE" if s["effective"] else "INACTIVE"
        print(f"Autoloop: {enabled}{paused} -> {effective}")
        if s["pause_since"]:
            elapsed = time.time() - s["pause_since"]
            mins = int(elapsed // 60)
            print(f"Paused for: {mins}m")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
