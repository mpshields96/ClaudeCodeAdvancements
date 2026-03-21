"""
loop_health.py — Per-session health tracking for cca-loop.

Records session grades, test counts, durations, and error types.
Detects regressions (test count drops, grade drops 2+ sessions in a row).
Provides summary statistics for the cca-loop status/history commands.
"""

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CCA_DIR = Path.home() / "Projects/ClaudeCodeAdvancements"
HEALTH_FILE = CCA_DIR / ".cca-loop-health.jsonl"
SESSION_STATE_FILE = CCA_DIR / "SESSION_STATE.md"

GRADE_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
SCORE_TO_GRADE = {4: "A", 3: "B", 2: "C", 1: "D", 0: "F"}


@dataclass
class SessionHealth:
    session_id: str
    timestamp: str
    grade: str
    test_pass: int
    test_fail: int
    duration_secs: int
    error_type: Optional[str] = None  # "timeout", "crash", "regression", None
    notes: str = ""


def parse_session_state(state_path: Path = SESSION_STATE_FILE) -> dict:
    """Parse SESSION_STATE.md for test counts and grade."""
    if not state_path.exists():
        return {}

    text = state_path.read_text()
    result: dict = {}

    # Extract test counts: "2897/2897 passing"
    m = re.search(r"Tests:\s*(\d+)/(\d+)\s*passing", text)
    if m:
        result["test_pass"] = int(m.group(1))
        result["test_total"] = int(m.group(2))
        result["test_fail"] = result["test_total"] - result["test_pass"]
    else:
        result["test_pass"] = 0
        result["test_total"] = 0
        result["test_fail"] = 0

    # Extract session number
    m = re.search(r"Session\s+(\d+)", text)
    if m:
        result["session_num"] = int(m.group(1))

    # Derive grade from pass rate
    total = result.get("test_total", 0)
    if total > 0:
        rate = result["test_pass"] / total
        if rate >= 1.0:
            result["grade"] = "A"
        elif rate >= 0.95:
            result["grade"] = "B"
        elif rate >= 0.85:
            result["grade"] = "C"
        elif rate >= 0.70:
            result["grade"] = "D"
        else:
            result["grade"] = "F"
    else:
        result["grade"] = "unknown"

    return result


def record_session(
    session_id: str,
    duration_secs: int,
    error_type: Optional[str] = None,
    notes: str = "",
    health_file: Path = HEALTH_FILE,
    state_path: Path = SESSION_STATE_FILE,
) -> SessionHealth:
    """Record a completed session's health metrics."""
    state = parse_session_state(state_path)

    health = SessionHealth(
        session_id=session_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        grade=state.get("grade", "unknown"),
        test_pass=state.get("test_pass", 0),
        test_fail=state.get("test_fail", 0),
        duration_secs=duration_secs,
        error_type=error_type,
        notes=notes,
    )

    health_file.parent.mkdir(parents=True, exist_ok=True)
    with open(health_file, "a") as f:
        f.write(json.dumps(asdict(health)) + "\n")

    return health


def load_history(
    n: Optional[int] = None, health_file: Path = HEALTH_FILE
) -> list:
    """Load session history from health file. Returns list of SessionHealth."""
    if not health_file.exists():
        return []

    records = []
    with open(health_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            records.append(SessionHealth(**data))

    if n is not None:
        records = records[-n:]
    return records


def detect_regressions(history: list) -> list:
    """
    Detect regressions in recent sessions.

    Returns list of regression description strings:
    - "test_count_drop: N -> M" when latest session has fewer total tests
    - "grade_drop: X -> Y -> Z" when grade dropped 2+ sessions in a row
    """
    regressions = []

    if len(history) < 2:
        return regressions

    recent = history[-1]
    previous = history[-2]

    # Test count drop
    total_recent = recent.test_pass + recent.test_fail
    total_prev = previous.test_pass + previous.test_fail

    if total_recent < total_prev:
        regressions.append(f"test_count_drop: {total_prev} -> {total_recent}")

    # Grade drop 2+ sessions in a row
    if len(history) >= 3:
        g0 = GRADE_ORDER.get(history[-3].grade, -1)
        g1 = GRADE_ORDER.get(history[-2].grade, -1)
        g2 = GRADE_ORDER.get(history[-1].grade, -1)

        if g0 >= 0 and g1 >= 0 and g2 >= 0 and g1 < g0 and g2 < g1:
            regressions.append(
                f"grade_drop: {history[-3].grade} -> {history[-2].grade} -> {history[-1].grade}"
            )

    return regressions


def get_summary(
    n: Optional[int] = None, health_file: Path = HEALTH_FILE
) -> dict:
    """
    Get summary statistics for the loop.

    Returns dict with:
    - sessions: total records loaded
    - sessions_today: sessions completed today
    - average_grade: overall average grade letter
    - test_pass_rate: float 0-1
    - last_error: most recent error_type or None
    - current_streak: consecutive sessions without error
    - regressions: list of regression strings
    """
    history = load_history(n, health_file)

    if not history:
        return {
            "sessions": 0,
            "sessions_today": 0,
            "average_grade": "unknown",
            "test_pass_rate": 0.0,
            "last_error": None,
            "current_streak": 0,
            "regressions": [],
        }

    today = datetime.now(timezone.utc).date().isoformat()
    today_sessions = [h for h in history if h.timestamp[:10] == today]

    # Average grade
    grade_scores = [GRADE_ORDER[h.grade] for h in history if h.grade in GRADE_ORDER]
    if grade_scores:
        avg_score = sum(grade_scores) / len(grade_scores)
        avg_grade = SCORE_TO_GRADE.get(round(avg_score), "unknown")
    else:
        avg_grade = "unknown"

    # Test pass rate across all sessions
    total_pass = sum(h.test_pass for h in history)
    total_tests = sum(h.test_pass + h.test_fail for h in history)
    pass_rate = total_pass / total_tests if total_tests > 0 else 0.0

    # Last error
    last_error = next((h.error_type for h in reversed(history) if h.error_type), None)

    # Current streak (consecutive sessions with no error_type)
    streak = 0
    for h in reversed(history):
        if h.error_type is None:
            streak += 1
        else:
            break

    regressions = detect_regressions(history)

    return {
        "sessions": len(history),
        "sessions_today": len(today_sessions),
        "average_grade": avg_grade,
        "test_pass_rate": round(pass_rate, 3),
        "last_error": last_error,
        "current_streak": streak,
        "regressions": regressions,
    }


def format_history_table(history: list) -> str:
    """Format history as a table string for display."""
    if not history:
        return "No session history found."

    lines = [
        f"{'#':<4} {'Session ID':<30} {'Grade':<6} {'Tests':<12} {'Duration':<12} {'Error':<12}",
        "-" * 80,
    ]
    for i, h in enumerate(history, 1):
        total = h.test_pass + h.test_fail
        duration = f"{h.duration_secs // 60}m{h.duration_secs % 60:02d}s"
        error = h.error_type or "-"
        lines.append(
            f"{i:<4} {h.session_id:<30} {h.grade:<6} {f'{h.test_pass}/{total}':<12} {duration:<12} {error:<12}"
        )
    return "\n".join(lines)
