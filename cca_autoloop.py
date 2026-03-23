#!/usr/bin/env python3
"""
cca_autoloop.py — MT-30 Phase 6: CCA-only auto-loop.

Reads SESSION_RESUME.md and spawns new Claude Code sessions in a loop.
Replaces Matthew's manual workflow of copy-paste resume prompt -> new chat.

Usage:
    python3 cca_autoloop.py start                    # Run the auto-loop
    python3 cca_autoloop.py start --dry-run           # Simulate without spawning
    python3 cca_autoloop.py start --max-iterations 5  # Limit iterations
    python3 cca_autoloop.py status                    # Show loop state
    python3 cca_autoloop.py status --state-file path  # Show state from file

How it works:
    1. Read SESSION_RESUME.md (written by /cca-wrap at end of each session)
    2. Spawn `claude` with the resume prompt as initial input
    3. Wait for session to complete (claude exits)
    4. Read the NEW SESSION_RESUME.md (written by the session that just ended)
    5. Repeat until max_iterations or safety stop

Safety:
    - Max iterations (default 50) prevents infinite loops
    - 3 consecutive crashes = auto-stop
    - 3 consecutive short sessions (<30s) = auto-stop (something is broken)
    - Cooldown between sessions (default 15s)
    - Never spawns more than 1 claude at a time
    - Always unsets ANTHROPIC_API_KEY (Max subscription auth)
    - Audit log for every iteration

Can be used:
    - Standalone: `python3 cca_autoloop.py start`
    - Via tmux: `tmux new-window -n cca-loop 'python3 cca_autoloop.py start'`
    - As daemon command: set in session_daemon_config.json

Stdlib only. No external dependencies.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PROJECT_DIR = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
DEFAULT_MAX_ITERATIONS = 50
DEFAULT_COOLDOWN = 15
MIN_COOLDOWN = 5
MIN_SESSION_DURATION = 30  # Sessions shorter than this are suspicious
MAX_CONSECUTIVE_CRASHES = 3
MAX_CONSECUTIVE_SHORT = 3
FALLBACK_PROMPT = "Run /cca-init then /cca-auto. No resume prompt was found."

# Model alternation strategies
VALID_MODEL_STRATEGIES = ("round-robin", "opus-primary", "sonnet-primary")
DEFAULT_MODEL_STRATEGY = "round-robin"
MODEL_OPUS = "opus"
MODEL_SONNET = "sonnet"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class AutoLoopConfig:
    """Configuration for the auto-loop."""
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    cooldown_seconds: int = DEFAULT_COOLDOWN
    project_dir: str = DEFAULT_PROJECT_DIR
    resume_file: str = ""
    dry_run: bool = False
    log_file: str = ""
    state_file: str = ""
    model_strategy: str = DEFAULT_MODEL_STRATEGY
    desktop_mode: bool = False

    def __post_init__(self):
        # Enforce minimums
        if self.max_iterations < 1:
            self.max_iterations = 1
        if self.cooldown_seconds < MIN_COOLDOWN:
            self.cooldown_seconds = MIN_COOLDOWN

        # Validate model strategy
        if self.model_strategy not in VALID_MODEL_STRATEGIES:
            self.model_strategy = DEFAULT_MODEL_STRATEGY

        # Derive resume_file from project_dir if not set
        if not self.resume_file:
            self.resume_file = os.path.join(self.project_dir, "SESSION_RESUME.md")

        # Derive log/state paths
        if not self.log_file:
            self.log_file = os.path.expanduser("~/.cca-autoloop.log")
        if not self.state_file:
            self.state_file = os.path.expanduser("~/.cca-autoloop-state.json")

    @classmethod
    def from_json(cls, path: str) -> "AutoLoopConfig":
        """Load config from a JSON file. Falls back to defaults on error."""
        try:
            with open(path) as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (OSError, json.JSONDecodeError, TypeError):
            return cls()


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class AutoLoopState:
    """Runtime state tracking for the auto-loop."""
    iteration: int = 0
    total_sessions: int = 0
    total_crashes: int = 0
    last_exit_code: Optional[int] = None
    should_stop: bool = False
    stop_reason: str = ""
    max_iterations: int = DEFAULT_MAX_ITERATIONS

    # Internal tracking
    _consecutive_crashes: int = field(default=0, repr=False)
    _consecutive_short: int = field(default=0, repr=False)
    _session_durations: list = field(default_factory=list, repr=False)
    _models_used: list = field(default_factory=list, repr=False)

    def record_session(self, exit_code: int, duration: float, model: str = ""):
        """Record the result of a completed session."""
        self.iteration += 1
        self.total_sessions += 1
        self.last_exit_code = exit_code
        self._session_durations.append(duration)
        if model:
            self._models_used.append(model)

        # Track crashes
        if exit_code != 0:
            self.total_crashes += 1
            self._consecutive_crashes += 1
        else:
            self._consecutive_crashes = 0

        # Track short sessions
        if duration < MIN_SESSION_DURATION:
            self._consecutive_short += 1
        else:
            self._consecutive_short = 0

        # Check stop conditions
        if self._consecutive_crashes >= MAX_CONSECUTIVE_CRASHES:
            self.should_stop = True
            self.stop_reason = f"{MAX_CONSECUTIVE_CRASHES}_consecutive_crashes"
        elif self._consecutive_short >= MAX_CONSECUTIVE_SHORT:
            self.should_stop = True
            self.stop_reason = f"{MAX_CONSECUTIVE_SHORT}_consecutive_short_sessions"
        elif self.iteration >= self.max_iterations:
            self.should_stop = True
            self.stop_reason = "max_iterations_reached"

    def summary(self) -> str:
        """Human-readable summary."""
        avg_dur = (
            sum(self._session_durations) / len(self._session_durations)
            if self._session_durations
            else 0
        )
        lines = [
            f"Iterations: {self.iteration}/{self.max_iterations}",
            f"Sessions: {self.total_sessions}  Crashes: {self.total_crashes}",
            f"Avg duration: {avg_dur:.0f}s",
            f"Last exit: {self.last_exit_code}",
        ]
        if self.should_stop:
            lines.append(f"STOPPED: {self.stop_reason}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "iteration": self.iteration,
            "total_sessions": self.total_sessions,
            "total_crashes": self.total_crashes,
            "last_exit_code": self.last_exit_code,
            "should_stop": self.should_stop,
            "stop_reason": self.stop_reason,
            "models_used": list(self._models_used),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_resume_prompt(path: str) -> str:
    """Read the resume prompt from SESSION_RESUME.md.

    Returns the prompt text, or a fallback if the file is missing/empty.
    """
    try:
        with open(path) as f:
            content = f.read().strip()
        if not content:
            return FALLBACK_PROMPT
        return content
    except OSError:
        return FALLBACK_PROMPT


def select_model(strategy: str, iteration: int) -> str:
    """Select which model to use for this iteration.

    Args:
        strategy: One of 'round-robin', 'opus-primary', 'sonnet-primary'
        iteration: 1-based iteration number

    Returns:
        Model name string ('opus' or 'sonnet')
    """
    if strategy == "opus-primary":
        return MODEL_OPUS
    elif strategy == "sonnet-primary":
        return MODEL_SONNET
    else:
        # round-robin: odd iterations = sonnet, even = opus
        return MODEL_SONNET if iteration % 2 == 1 else MODEL_OPUS


def build_claude_command(
    resume_prompt: str,
    project_dir: str,
    model: Optional[str] = None,
) -> list[str]:
    """Build the claude CLI command with resume prompt.

    Args:
        resume_prompt: The resume prompt text
        project_dir: Path to the project directory
        model: Optional model name ('opus' or 'sonnet'). If None, no --model flag.

    Returns a list of arguments (no shell escaping needed — subprocess handles it).
    """
    if not resume_prompt.strip():
        resume_prompt = FALLBACK_PROMPT

    # Construct the prompt that mimics Matthew's manual workflow:
    # /cca-init then review prompt below then /cca-auto
    # <resume prompt content>
    full_prompt = (
        "/cca-init then review prompt below then /cca-auto\n\n"
        f"{resume_prompt}"
    )

    cmd = ["claude"]
    if model:
        cmd.extend(["--model", model])
    cmd.append(full_prompt)
    return cmd


# ---------------------------------------------------------------------------
# Desktop Mode
# ---------------------------------------------------------------------------

def write_desktop_wrapper(
    project_dir: str,
    model: str,
    model_strategy: str,
    iteration: int,
    prompt_file: str,
    sentinel_file: str,
) -> str:
    """Write a self-contained wrapper script for desktop mode.

    The wrapper runs claude in the Terminal.app window, then writes
    the exit code to sentinel_file so the controller can detect completion.

    Returns the path to the wrapper script.
    """
    wrapper_path = os.path.join(
        tempfile.gettempdir(),
        f"cca-autoloop-wrapper-{os.getpid()}-{iteration}.sh",
    )
    script = f"""#!/bin/bash
cd "{project_dir}"
unset ANTHROPIC_API_KEY
echo "========================================"
echo "  CCA Auto-Loop — Iteration {iteration}"
echo "  Model: {model} ({model_strategy})"
echo "========================================"
echo ""
PROMPT=$(cat "{prompt_file}")
claude --model "{model}" "$PROMPT"
echo $? > "{sentinel_file}"
echo ""
echo "Session complete. This window will close in 5 seconds..."
sleep 5
exit
"""
    with open(wrapper_path, "w") as f:
        f.write(script)
    os.chmod(wrapper_path, stat.S_IRWXU)
    return wrapper_path


def spawn_desktop_session(wrapper_path: str) -> bool:
    """Open a Terminal.app window running the wrapper script.

    Returns True if osascript succeeded, False otherwise.
    """
    try:
        subprocess.run(
            ["osascript", "-e",
             f'tell application "Terminal" to do script "\'{wrapper_path}\'"'],
            capture_output=True,
            timeout=10,
        )
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


def wait_for_sentinel(sentinel_path: str, poll_interval: float = 2.0, timeout: float = 14400.0) -> int:
    """Poll for the sentinel file and return the exit code.

    Args:
        sentinel_path: Path to the sentinel file written by the wrapper
        poll_interval: Seconds between polls
        timeout: Max seconds to wait (default 4 hours)

    Returns exit code from sentinel file, or 1 on timeout.
    """
    elapsed = 0.0
    while elapsed < timeout:
        if os.path.exists(sentinel_path):
            try:
                with open(sentinel_path) as f:
                    return int(f.read().strip())
            except (ValueError, OSError):
                return 1
        time.sleep(poll_interval)
        elapsed += poll_interval
    return 1  # timeout


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AutoLoopLogger:
    """Simple JSONL audit logger."""

    def __init__(self, path: str):
        self.path = path

    def log(self, event: str, data: Optional[dict] = None):
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            "data": data or {},
        }
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class AutoLoopRunner:
    """Main auto-loop runner. Reads resume prompt, spawns claude, repeats."""

    def __init__(self, config: AutoLoopConfig):
        self.config = config
        self.state = AutoLoopState(max_iterations=config.max_iterations)
        self.logger = AutoLoopLogger(config.log_file)

    def run_one_iteration(self) -> dict:
        """Run a single iteration: read resume, spawn claude, wait.

        Returns a dict with iteration results.
        """
        # Read resume prompt
        resume_prompt = read_resume_prompt(self.config.resume_file)

        # Select model for this iteration (1-based)
        model = select_model(
            self.config.model_strategy,
            self.state.iteration + 1,
        )

        # Build command with model
        cmd = build_claude_command(resume_prompt, self.config.project_dir, model=model)

        self.logger.log("iteration_start", {
            "iteration": self.state.iteration + 1,
            "resume_length": len(resume_prompt),
            "model": model,
            "model_strategy": self.config.model_strategy,
            "dry_run": self.config.dry_run,
        })

        start_time = time.time()

        if self.config.dry_run:
            # Simulate a session
            exit_code = 0
            duration = 0.1  # Near-instant for dry run
        elif self.config.desktop_mode:
            # Desktop mode: open visible Terminal.app window
            iteration_num = self.state.iteration + 1
            sentinel_path = os.path.join(
                tempfile.gettempdir(),
                f"cca-autoloop-sentinel-{os.getpid()}-{iteration_num}",
            )
            prompt_file = os.path.join(
                tempfile.gettempdir(),
                f"cca-autoloop-prompt-{os.getpid()}-{iteration_num}.txt",
            )

            # Write prompt to file (avoids quoting issues)
            with open(prompt_file, "w") as f:
                f.write(cmd[-1])  # The prompt is the last element of cmd

            wrapper_path = write_desktop_wrapper(
                project_dir=self.config.project_dir,
                model=model,
                model_strategy=self.config.model_strategy,
                iteration=iteration_num,
                prompt_file=prompt_file,
                sentinel_file=sentinel_path,
            )

            if spawn_desktop_session(wrapper_path):
                exit_code = wait_for_sentinel(sentinel_path)
            else:
                self.logger.log("desktop_spawn_error", {})
                exit_code = 1

            # Cleanup
            for p in (sentinel_path, wrapper_path, prompt_file):
                try:
                    os.unlink(p)
                except OSError:
                    pass

            duration = time.time() - start_time
        else:
            # Foreground mode: spawn claude as subprocess
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)  # Always use Max subscription

            try:
                result = subprocess.run(
                    cmd,
                    env=env,
                    cwd=self.config.project_dir,
                )
                exit_code = result.returncode
            except Exception as e:
                self.logger.log("spawn_error", {"error": str(e)})
                exit_code = 1

            duration = time.time() - start_time

        # Record result with model info
        self.state.record_session(exit_code=exit_code, duration=duration, model=model)

        result = {
            "iteration": self.state.iteration,
            "exit_code": exit_code,
            "duration": duration,
            "model": model,
            "should_stop": self.state.should_stop,
        }

        self.logger.log("iteration_complete", result)

        # Persist state
        self._save_state()

        return result

    def run(self):
        """Run the full auto-loop until stopped."""
        self.logger.log("loop_started", {
            "max_iterations": self.config.max_iterations,
            "dry_run": self.config.dry_run,
            "project_dir": self.config.project_dir,
        })

        print(f"CCA Auto-Loop starting (max {self.config.max_iterations} iterations)")
        if self.config.dry_run:
            print("DRY RUN — no sessions will be spawned")

        while not self.state.should_stop:
            print(f"\n--- Iteration {self.state.iteration + 1} ---")
            result = self.run_one_iteration()

            print(f"Exit code: {result['exit_code']}  Duration: {result['duration']:.0f}s  Model: {result.get('model', '?')}")

            if self.state.should_stop:
                print(f"\nAuto-loop stopping: {self.state.stop_reason}")
                break

            # Cooldown between sessions
            if not self.config.dry_run:
                print(f"Cooldown: {self.config.cooldown_seconds}s")
                time.sleep(self.config.cooldown_seconds)

        self.logger.log("loop_finished", self.state.to_dict())
        print(f"\n{self.state.summary()}")

    def _save_state(self):
        """Persist state to file."""
        try:
            with open(self.config.state_file, "w") as f:
                json.dump(self.state.to_dict(), f, indent=2)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cli_main(args: list = None):
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        print("cca_autoloop.py — CCA Auto-Loop (MT-30 Phase 6)")
        print()
        print("Commands:")
        print("  start [options]           Start the auto-loop")
        print("    --dry-run               Simulate without spawning claude")
        print("    --max-iterations N      Maximum iterations (default 50)")
        print("    --cooldown N            Seconds between sessions (default 15)")
        print("    --config PATH           Load config from JSON file")
        print("    --model-strategy STR    Model strategy: round-robin|opus-primary|sonnet-primary")
        print("    --desktop               Open each session in a visible Terminal.app window")
        print("  status                    Show current loop state")
        print("    --state-file PATH       Path to state file")
        print()
        return

    cmd = args[0]

    if cmd == "start":
        # Parse options
        dry_run = "--dry-run" in args
        desktop_mode = "--desktop" in args
        max_iter = DEFAULT_MAX_ITERATIONS
        cooldown = DEFAULT_COOLDOWN
        config_path = None
        model_strategy = os.environ.get("MODEL_STRATEGY", DEFAULT_MODEL_STRATEGY)

        for i, arg in enumerate(args[1:], 1):
            if arg == "--max-iterations" and i + 1 < len(args):
                max_iter = int(args[i + 1])
            elif arg == "--cooldown" and i + 1 < len(args):
                cooldown = int(args[i + 1])
            elif arg == "--config" and i + 1 < len(args):
                config_path = args[i + 1]
            elif arg == "--model-strategy" and i + 1 < len(args):
                model_strategy = args[i + 1]

        if config_path:
            cfg = AutoLoopConfig.from_json(config_path)
            if dry_run:
                cfg.dry_run = True
            if desktop_mode:
                cfg.desktop_mode = True
            if "--model-strategy" in args:
                cfg.model_strategy = model_strategy
        else:
            cfg = AutoLoopConfig(
                max_iterations=max_iter,
                cooldown_seconds=cooldown,
                dry_run=dry_run,
                desktop_mode=desktop_mode,
                model_strategy=model_strategy,
            )

        runner = AutoLoopRunner(cfg)
        runner.run()

    elif cmd == "status":
        state_file = os.path.expanduser("~/.cca-autoloop-state.json")
        for i, arg in enumerate(args[1:], 1):
            if arg == "--state-file" and i + 1 < len(args):
                state_file = args[i + 1]

        if os.path.exists(state_file):
            with open(state_file) as f:
                data = json.load(f)
            print("CCA Auto-Loop Status:")
            for k, v in data.items():
                print(f"  {k}: {v}")
        else:
            print("No state file found. Auto-loop may not have run yet.")

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
