#!/usr/bin/env python3
"""
slim_init.py — Codified slim session startup for CCA.

Replaces the 10-minute full init (4 large file reads + 109 test suites + counting)
with a ~1 minute automated startup:
  1. Parse SESSION_STATE.md for orientation
  2. Run 10-suite smoke test via init_cache.py
  3. Run priority_picker.py for task recommendation
  4. Output structured init summary

CLI:
    python3 slim_init.py              # Run full slim init
    python3 slim_init.py --json       # JSON output
    python3 slim_init.py orient       # Just parse SESSION_STATE
    python3 slim_init.py smoke        # Just run smoke test
    python3 slim_init.py priority     # Just run priority picker

Stdlib only. No external dependencies.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from session_id import normalize as normalize_session_id

PROJECT_ROOT = Path(__file__).resolve().parent
SESSION_STATE_PATH = PROJECT_ROOT / "SESSION_STATE.md"
TODAYS_TASKS_PATH = PROJECT_ROOT / "TODAYS_TASKS.md"
DIRECTIVES_PATH = PROJECT_ROOT / "MATTHEW_DIRECTIVES.md"

INIT_STEPS = ["smoke", "priority", "summary"]


def parse_session_state(content: str) -> dict:
    """Parse SESSION_STATE.md for quick orientation."""
    result: dict = {}

    # Session number and date
    m = re.search(r"Session\s+(\d+)\s*(?:—|-)\s*(\d{4}-\d{2}-\d{2})", content)
    if m:
        result["session_num"] = int(m.group(1))
        result["session_id"] = normalize_session_id(m.group(1))
        result["session_date"] = m.group(2)
    else:
        m = re.search(r"Session\s+(\d+)", content)
        if m:
            result["session_num"] = int(m.group(1))
            result["session_id"] = normalize_session_id(m.group(1))

    # Test counts — handle both formats:
    #   "Tests: ~109 suites, ~4373 total passing"
    #   "Tests: 2897/2897 passing"
    m = re.search(r"Tests:\s*~?(\d+)\s*suites?,\s*~?(\d+)\s*total", content)
    if m:
        result["suite_count"] = int(m.group(1))
        result["test_count"] = int(m.group(2))
    else:
        m = re.search(r"Tests:\s*(\d+)/(\d+)\s*passing", content)
        if m:
            result["test_count"] = int(m.group(1))

    # Hivemind streak
    m = re.search(r"Hivemind:\s*(\d+)(?:st|nd|rd|th)\s+consecutive\s+PASS", content)
    if m:
        result["hivemind_streak"] = int(m.group(1))

    # Next items
    next_items = []
    in_next = False
    for line in content.split("\n"):
        if "**Next" in line and "prioritized" in line.lower():
            in_next = True
            continue
        if in_next:
            stripped = line.strip()
            if stripped.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                # Strip the number prefix
                item = re.sub(r"^\d+\.\s*", "", stripped)
                next_items.append(item)
            elif stripped.startswith("---") or (stripped.startswith("**") and stripped != ""):
                break
            elif not stripped:
                if next_items:
                    break
    result["next_items"] = next_items

    return result


def run_smoke() -> dict:
    """Run the 10-suite smoke test via init_cache.py."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "init_cache.py"), "smoke"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        output = proc.stdout.strip()

        # Parse "Smoke: N/M passed"
        m = re.search(r"Smoke:\s*(\d+)/(\d+)\s*passed", output)
        if m:
            passed_count = int(m.group(1))
            total_count = int(m.group(2))
            return {
                "passed": passed_count == total_count,
                "suites_passed": passed_count,
                "suites_total": total_count,
                "output": output,
            }

        return {
            "passed": proc.returncode == 0,
            "suites_passed": 0,
            "suites_total": 0,
            "output": output,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "suites_passed": 0,
            "suites_total": 0,
            "error": "Timeout: smoke test exceeded 60 seconds",
        }


def scan_todays_tasks() -> dict:
    """Scan TODAYS_TASKS.md for remaining TODO items (Matthew directive S178)."""
    result: dict = {"todos": [], "count": 0}
    if not TODAYS_TASKS_PATH.exists():
        return result
    try:
        content = TODAYS_TASKS_PATH.read_text()
        for line in content.splitlines():
            if "[TODO]" in line:
                # Extract task label (e.g., "### C1. MT-26 Dead Code Cleanup [TODO]")
                task = line.strip().lstrip("#").strip()
                result["todos"].append(task)
        result["count"] = len(result["todos"])
    except Exception:
        pass
    return result


def scan_directives() -> dict:
    """Scan MATTHEW_DIRECTIVES.md for the latest directive (S181 — perpetual log)."""
    result: dict = {"latest_title": "", "latest_session": ""}
    if not DIRECTIVES_PATH.exists():
        return result
    try:
        content = DIRECTIVES_PATH.read_text()
        # Find the most recent "## SN —" header
        import re
        headers = re.findall(r"^## (S\d+) — .+ \((.+)\)$", content, re.MULTILINE)
        if headers:
            last = headers[-1]
            result["latest_session"] = last[0]
            result["latest_title"] = last[1]
    except Exception:
        pass
    return result


def run_priority() -> dict:
    """Run priority_picker.py recommend."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "priority_picker.py"), "recommend"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        if proc.returncode != 0:
            return {"error": proc.stderr.strip() or "priority_picker failed", "raw": proc.stdout}

        output = proc.stdout.strip()

        # Extract top pick
        m = re.search(r"\*\*TOP PICK:\*\*\s*(.+?)(?:\n|$)", output)
        top_pick = m.group(1).strip() if m else output.split("\n")[0]

        return {"top_pick": top_pick, "raw": output}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout: priority_picker exceeded 30 seconds"}


def run_principle_seeder() -> dict:
    """Run principle_seeder.py seed-all (idempotent — skips existing)."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "principle_seeder.py"), "seed-all"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()

        if proc.returncode != 0:
            return {"seeded": 0, "error": proc.stderr.strip() or "principle_seeder failed", "raw": output}

        # Parse "Seeded N principles total"
        m = re.search(r"Seeded\s+(\d+)\s+principles?\s+total", output)
        seeded = int(m.group(1)) if m else 0

        return {"seeded": seeded, "raw": output}
    except subprocess.TimeoutExpired:
        return {"seeded": 0, "error": "Timeout: principle_seeder exceeded 30 seconds"}


def run_mt_proposals() -> dict:
    """Run mt_originator.py --briefing for MT-41 proposals."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "mt_originator.py"), "--briefing"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            return {"proposals": [], "raw": ""}

        # Count proposals (lines starting with spaces + "[score]")
        proposal_lines = re.findall(r"^\s+\[\d+", output, re.MULTILINE)
        return {"proposals": proposal_lines, "count": len(proposal_lines), "raw": output}
    except subprocess.TimeoutExpired:
        return {"proposals": [], "count": 0, "raw": "", "error": "Timeout"}


def run_meta_learning() -> dict:
    """Run meta_learning_dashboard.py --brief for self-learning health."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "meta_learning_dashboard.py"), "--brief"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            error = proc.stderr.strip() or "meta_learning_dashboard failed"
            return {"status": "", "brief": "", "error": error}

        # Parse status from "Self-Learning: STATUS | ..."
        m = re.search(r"Self-Learning:\s*(\w+)", output)
        status = m.group(1) if m else ""

        return {"status": status, "brief": output}
    except subprocess.TimeoutExpired:
        return {"status": "", "brief": "", "error": "Timeout: meta_learning_dashboard exceeded 30 seconds"}


def run_mt_extensions() -> dict:
    """Run mt_originator.py --extend-existing for phase extension proposals."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "mt_originator.py"),
             "--extend-existing", "--top", "3", "--min-score", "50"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            return {"extensions": [], "raw": ""}

        # Count extension lines (start with spaces + "[score]")
        ext_lines = re.findall(r"^\s+\[\d+", output, re.MULTILINE)
        return {"extensions": ext_lines, "count": len(ext_lines), "raw": output}
    except subprocess.TimeoutExpired:
        return {"extensions": [], "count": 0, "raw": "", "error": "Timeout"}


def run_unified_origination() -> dict:
    """Run mt_originator.py --unified for MT-52 3-source intelligence briefing.

    Combines: ADAPT findings + stalled MTs + cross-chat requests into one report.
    This is the comprehensive view wired into /cca-init (S183).
    """
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "mt_originator.py"), "--unified"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            return {"total": 0, "raw": ""}

        # Parse "N actionable items" from summary
        m = re.search(r"(\d+)\s+actionable\s+items?", output)
        total = int(m.group(1)) if m else 0

        # Parse section counts
        adapts = len(re.findall(r"^\s+MT-\d+.*ADAPT", output, re.MULTILINE))
        stalled = len(re.findall(r"^\s+MT-\d+:.*\[", output, re.MULTILINE))
        requests = len(re.findall(r"^\s+REQ-\d+:", output, re.MULTILINE))

        return {
            "total": total,
            "adapts": adapts,
            "stalled": stalled,
            "requests": requests,
            "raw": output,
        }
    except subprocess.TimeoutExpired:
        return {"total": 0, "raw": "", "error": "Timeout: unified origination exceeded 30 seconds"}


def run_outcomes_enricher() -> dict:
    """Run outcomes_enricher.py enrich to add missing REQ entries (idempotent)."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "outcomes_enricher.py"), "enrich"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            return {"enriched": 0}

        # Parse "Added N entries to ..."
        m = re.search(r"Added\s+(\d+)\s+entries?", output)
        enriched = int(m.group(1)) if m else 0

        return {"enriched": enriched, "raw": output}
    except subprocess.TimeoutExpired:
        return {"enriched": 0, "error": "Timeout: outcomes_enricher exceeded 15 seconds"}


def run_predictive_recommendations(session_num: int = 0) -> dict:
    """Run predictive_recommender.py summary for pre-session recommendations."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "predictive_recommender.py"),
             "summary", "--domains", "cca_operations", "trading_research",
             "--session", str(session_num)],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            return {"recommendations": 0}

        # Count recommendation lines (lines with "[XX%]")
        rec_lines = [l for l in output.split("\n") if "[" in l and "%]" in l]

        return {"recommendations": len(rec_lines), "brief": output}
    except subprocess.TimeoutExpired:
        return {"recommendations": 0, "error": "Timeout"}


def run_transfer_proposals() -> dict:
    """Run principle_transfer.py propose + review for active transfer proposals."""
    try:
        # Auto-propose new transfers (idempotent — deduplicates)
        subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "principle_transfer.py"),
             "propose", "--max", "5"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        # Get summary
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "principle_transfer.py"),
             "review"],
            capture_output=True, text=True, timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            return {"pending": 0}

        # Parse pending count
        m = re.search(r"(\d+)\s+pending", output)
        pending = int(m.group(1)) if m else 0

        # Extract top proposal text
        top_text = ""
        lines = output.split("\n")
        for line in lines:
            if line.strip().startswith("["):
                top_text = line.strip()
                break

        return {"pending": pending, "top_text": top_text, "raw": output}
    except subprocess.TimeoutExpired:
        return {"pending": 0, "error": "Timeout"}


def run_principle_discoverer() -> dict:
    """Run principle_discoverer.py discover --dry-run to surface new patterns."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "principle_discoverer.py"),
             "discover", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            error = proc.stderr.strip() or "principle_discoverer failed"
            return {"discovered": 0, "error": error, "raw": output}

        # Parse "Discovered: N patterns"
        m = re.search(r"Discovered:\s*(\d+)\s*patterns?", output)
        discovered = int(m.group(1)) if m else 0

        return {"discovered": discovered, "raw": output}
    except subprocess.TimeoutExpired:
        return {"discovered": 0, "error": "Timeout: principle_discoverer exceeded 30 seconds"}


def run_recalibration(current_session: int = 0) -> dict:
    """Run confidence_recalibrator.py summary for staleness info."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "confidence_recalibrator.py"),
             "recalibrate", "--session", str(current_session)],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            return {"decayed": 0, "total": 0}

        # Parse "Decayed: N  Stable: M"
        m = re.search(r"Decayed:\s*(\d+)", output)
        decayed = int(m.group(1)) if m else 0
        m = re.search(r"(\d+)\s*principles?", output)
        total = int(m.group(1)) if m else 0

        return {"decayed": decayed, "total": total, "raw": output}
    except subprocess.TimeoutExpired:
        return {"decayed": 0, "total": 0, "error": "Timeout"}


def run_research_roi() -> dict:
    """Run research_roi_resolver.py report --json for delivery ROI summary."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "research_roi_resolver.py"),
             "report", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            return {"total": 0, "resolved": 0}

        data = json.loads(output)
        return {
            "total": data.get("total_deliveries", 0),
            "resolved": data.get("resolved", 0),
            "by_status": data.get("by_status", {}),
        }
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"total": 0, "resolved": 0, "error": "Timeout or parse error"}


def run_session_metrics() -> dict:
    """Run session_metrics.py for session-over-session trends."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "session_metrics.py"), "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )

        if proc.returncode != 0 or not proc.stdout.strip():
            return {"total_sessions": 0}

        report = json.loads(proc.stdout)
        # Build briefing text inline
        briefing_parts = []
        ts = report.get("total_sessions", 0)
        if ts == 0:
            return {"total_sessions": 0}

        gt = report.get("grade_trend", {})
        if gt.get("direction") != "insufficient_data":
            briefing_parts.append(f"grades {gt['direction']}")
        tv = report.get("test_velocity_trend", {})
        if tv.get("direction") != "insufficient_data":
            briefing_parts.append(f"test velocity {tv['direction']}")

        brief = f"{ts} sessions tracked"
        if briefing_parts:
            brief += f" — {', '.join(briefing_parts)}"

        pc = report.get("principle_count", {})
        return {
            "total_sessions": ts,
            "brief": brief,
            "active_principles": pc.get("active", 0),
            "report": report,
        }
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"total_sessions": 0}


def run_reflect_brief() -> dict:
    """Run reflect.py --brief for journal pattern analysis (deferred from wrap step 7)."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "self-learning" / "reflect.py"), "--brief"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )

        output = proc.stdout.strip()
        if proc.returncode != 0 or not output:
            return {"patterns": 0, "entries": 0, "brief": ""}

        # Parse "N entries, M patterns detected"
        m = re.search(r"(\d+)\s+entries?,\s*(\d+)\s+patterns?\s+detected", output)
        entries = int(m.group(1)) if m else 0
        patterns = int(m.group(2)) if m else 0

        return {"patterns": patterns, "entries": entries, "brief": output}
    except subprocess.TimeoutExpired:
        return {"patterns": 0, "entries": 0, "brief": "", "error": "Timeout: reflect exceeded 30 seconds"}


def run_timeline(n: int = 5) -> dict:
    """Run session_timeline.py recent N for quick history."""
    try:
        proc = subprocess.run(
            ["python3", str(PROJECT_ROOT / "session_timeline.py"), "recent", str(n)],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )

        if proc.returncode != 0:
            return {"error": proc.stderr.strip() or "session_timeline failed", "raw": "", "session_count": 0}

        output = proc.stdout.strip()

        # Count session lines (lines starting with whitespace + S followed by digits)
        import re
        session_lines = re.findall(r"^\s+S\d+:", output, re.MULTILINE)
        count = len(session_lines)

        return {"raw": output, "session_count": count}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout: session_timeline exceeded 15 seconds", "raw": "", "session_count": 0}


def build_summary(smoke: dict, priority: dict, state: dict) -> dict:
    """Combine all init results into a summary."""
    blockers = []
    if not smoke.get("passed", False):
        blockers.append(f"Smoke test failed: {smoke.get('suites_passed', 0)}/{smoke.get('suites_total', 0)}")

    ready = len(blockers) == 0

    summary = {
        "ready": ready,
        "last_session": state.get("session_num"),
        "last_session_id": state.get("session_id", "S?"),
        "top_pick": priority.get("top_pick", "unknown"),
        "smoke_status": f"{smoke.get('suites_passed', 0)}/{smoke.get('suites_total', 0)} {'PASS' if smoke.get('passed') else 'FAIL'}",
        "blockers": blockers,
    }

    if "test_count" in state:
        summary["cached_test_count"] = state["test_count"]
    if "suite_count" in state:
        summary["cached_suite_count"] = state["suite_count"]
    if "hivemind_streak" in state:
        summary["hivemind_streak"] = state["hivemind_streak"]

    return summary


def format_summary(summary: dict) -> str:
    """Format summary for human-readable display."""
    lines = []
    status = "READY" if summary["ready"] else "BLOCKED"
    lines.append(f"Slim Init: {status}")
    lines.append(f"  Last session: {summary.get('last_session_id', 'S?')}")
    lines.append(f"  Smoke: {summary.get('smoke_status', '?')}")
    # TODAYS_TASKS.md — authoritative daily list (Matthew directive S178)
    if summary.get("todays_tasks_count", 0) > 0:
        lines.append(f"  TODAY'S TASKS ({summary['todays_tasks_count']} remaining):")
        for task in summary.get("todays_tasks", []):
            lines.append(f"    - {task}")
        lines.append(f"  Top pick (after today's tasks): {summary.get('top_pick', '?')}")
    else:
        lines.append(f"  Today's tasks: ALL DONE")
        lines.append(f"  Top pick: {summary.get('top_pick', '?')}")

    if summary.get("meta_learning_brief"):
        lines.append(f"  {summary['meta_learning_brief']}")
    if summary.get("principles_seeded", 0) > 0:
        lines.append(f"  Principles seeded: {summary['principles_seeded']} new")
    if summary.get("cached_test_count"):
        lines.append(f"  Tests: ~{summary['cached_test_count']} ({summary.get('cached_suite_count', '?')} suites)")
    if summary.get("hivemind_streak"):
        lines.append(f"  Hivemind: {summary['hivemind_streak']}th consecutive PASS")

    if summary.get("transfer_pending", 0) > 0:
        lines.append(f"  Transfer proposals: {summary['transfer_pending']} pending")
        if summary.get("transfer_top"):
            lines.append(f"    Top: {summary['transfer_top']}")
    if summary.get("discoveries_count", 0) > 0:
        lines.append(f"  Discoveries: {summary['discoveries_count']} new patterns (dry-run)")
    if summary.get("recal_decayed", 0) > 0:
        lines.append(f"  Recalibration: {summary['recal_decayed']}/{summary.get('recal_total', 0)} principles decayed (staleness)")
    if summary.get("roi_resolved", 0) > 0:
        lines.append(f"  Research ROI: {summary['roi_resolved']}/{summary.get('roi_total', 0)} deliveries resolved")
    if summary.get("enriched_count", 0) > 0:
        lines.append(f"  Enriched: {summary['enriched_count']} new REQ entries added to outcomes")
    if summary.get("predictions_count", 0) > 0:
        lines.append(f"  Predictions: {summary['predictions_count']} principle recommendations")
    if summary.get("directive_latest"):
        lines.append(f"  Directive: {summary['directive_session']} — {summary['directive_latest']}")
        lines.append(f"    (Read MATTHEW_DIRECTIVES.md — perpetual inspiration log)")
    if summary.get("reflect_patterns", 0) > 0:
        lines.append(f"  Reflect: {summary['reflect_patterns']} patterns — {summary.get('reflect_brief', '')}")
    if summary.get("session_metrics_brief"):
        lines.append(f"  Metrics: {summary['session_metrics_brief']}")
    if summary.get("blockers"):
        lines.append("  BLOCKERS:")
        for b in summary["blockers"]:
            lines.append(f"    - {b}")

    if summary.get("mt_proposals_count", 0) > 0:
        lines.append(f"  MT proposals: {summary['mt_proposals_count']} from findings")
    if summary.get("unified_origination_total", 0) > 0:
        lines.append(f"  Origination: {summary['unified_origination_total']} actionable items (ADAPT + stalled MTs + cross-chat)")

    if summary.get("timeline_raw"):
        lines.append(f"\n  Recent sessions:")
        for tl in summary["timeline_raw"].split("\n"):
            tl = tl.strip()
            if tl.startswith("S") and ":" in tl:
                lines.append(f"    {tl}")

    return "\n".join(lines)


def run_slim_init(session_state_path: Path = SESSION_STATE_PATH) -> dict:
    """Run the full slim init sequence."""
    # Step 1: Parse SESSION_STATE
    state = {}
    if session_state_path.exists():
        content = session_state_path.read_text()
        state = parse_session_state(content)

    # Step 1.5: Scan TODAYS_TASKS.md (Matthew directive S178 — authoritative daily list)
    todays = scan_todays_tasks()

    # Step 2: Smoke test
    smoke = run_smoke()

    # Step 2.5: Seed principles (idempotent — zero cost if already seeded)
    seeder = run_principle_seeder()

    # Step 3: Priority pick (informational — TODAYS_TASKS takes precedence)
    priority = run_priority()

    # Step 3.5: MT proposals from findings (MT-41)
    mt_proposals = run_mt_proposals()

    # Step 3.6: MT phase extensions for existing MTs (MT-41 Phase 4)
    mt_extensions = run_mt_extensions()

    # Step 3.6b: Unified origination (MT-52 — 3-source intelligence, S183)
    unified = run_unified_origination()

    # Step 3.7: Meta-learning health (MT-49)
    meta_learning = run_meta_learning()

    # Step 3.8: Transfer proposals (MT-49 Phase 2 — auto-propose)
    transfer = run_transfer_proposals()

    # Step 3.9: Principle discovery (MT-49 Phase 3 — dry-run scan)
    discoverer = run_principle_discoverer()

    # Step 3.10: Confidence recalibration (MT-49 Phase 4 — staleness check)
    recal = run_recalibration(current_session=state.get("session_num", 0))

    # Step 3.11: Research ROI (MT-49 Phase 5 — delivery resolution)
    roi = run_research_roi()

    # Step 3.12: Outcomes enricher (MT-49 Phase 5 — auto-enrich missing REQs)
    enricher = run_outcomes_enricher()

    # Step 3.13: Predictive recommendations (MT-28 Phase 5 — pre-session principle ranking)
    predictions = run_predictive_recommendations(session_num=state.get("session_num", 0))

    # Step 3.14: Reflect brief (deferred wrap step 7 — journal pattern analysis)
    reflect = run_reflect_brief()

    # Step 3.15: Session metrics (MT-49 Phase 6 — session-over-session trends)
    session_metrics = run_session_metrics()

    # Step 4: Session timeline (last 5 sessions)
    timeline = run_timeline(5)

    # Step 5: Build summary
    summary = build_summary(smoke, priority, state)
    summary["priority_raw"] = priority.get("raw", "")
    if todays.get("count", 0) > 0:
        summary["todays_tasks"] = todays["todos"]
        summary["todays_tasks_count"] = todays["count"]
    summary["principles_seeded"] = seeder.get("seeded", 0)
    if mt_proposals.get("count", 0) > 0:
        summary["mt_proposals_raw"] = mt_proposals["raw"]
        summary["mt_proposals_count"] = mt_proposals["count"]
    if mt_extensions.get("count", 0) > 0:
        summary["mt_extensions_raw"] = mt_extensions["raw"]
        summary["mt_extensions_count"] = mt_extensions["count"]
    if unified.get("total", 0) > 0:
        summary["unified_origination_raw"] = unified["raw"]
        summary["unified_origination_total"] = unified["total"]
    if timeline.get("raw") and timeline.get("session_count", 0) > 0:
        summary["timeline_raw"] = timeline["raw"]
    if meta_learning.get("brief"):
        summary["meta_learning_brief"] = meta_learning["brief"]
    if transfer.get("pending", 0) > 0:
        summary["transfer_pending"] = transfer["pending"]
        summary["transfer_top"] = transfer.get("top_text", "")
    if discoverer.get("discovered", 0) > 0:
        summary["discoveries_count"] = discoverer["discovered"]
        summary["discoveries_raw"] = discoverer.get("raw", "")
    if recal.get("decayed", 0) > 0:
        summary["recal_decayed"] = recal["decayed"]
        summary["recal_total"] = recal["total"]
    if roi.get("resolved", 0) > 0:
        summary["roi_resolved"] = roi["resolved"]
        summary["roi_total"] = roi["total"]
    if enricher.get("enriched", 0) > 0:
        summary["enriched_count"] = enricher["enriched"]
    if predictions.get("recommendations", 0) > 0:
        summary["predictions_count"] = predictions["recommendations"]
        summary["predictions_brief"] = predictions.get("brief", "")
    if reflect.get("patterns", 0) > 0:
        summary["reflect_patterns"] = reflect["patterns"]
        summary["reflect_brief"] = reflect.get("brief", "")
    if session_metrics.get("total_sessions", 0) > 0:
        summary["session_metrics_brief"] = session_metrics["brief"]
        summary["session_metrics_sessions"] = session_metrics["total_sessions"]

    # Step 5.1: Matthew Directives (S181 — perpetual inspiration log)
    directives = scan_directives()
    if directives.get("latest_title"):
        summary["directive_latest"] = directives["latest_title"]
        summary["directive_session"] = directives["latest_session"]

    return summary


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] not in ("--json", "orient", "smoke", "priority"):
        # Full slim init — compact output to minimize context consumption
        result = run_slim_init()
        if "--json" in args:
            print(json.dumps(result, indent=2))
        elif "--verbose" in args:
            # Legacy verbose mode — dumps raw priority/proposals/extensions
            print(format_summary(result))
            if result.get("priority_raw"):
                print(f"\n{result['priority_raw']}")
            if result.get("mt_proposals_raw"):
                print(f"\n{result['mt_proposals_raw']}")
            if result.get("mt_extensions_raw"):
                print(f"\n{result['mt_extensions_raw']}")
        else:
            # Default: compact mode — summary only, no raw dumps
            print(format_summary(result))
            # Show top pick detail (1 line) and top MT proposal (1 line) only
            if result.get("mt_proposals_raw"):
                lines = result["mt_proposals_raw"].strip().split("\n")
                top_lines = [l for l in lines if l.strip().startswith("[")]
                if top_lines:
                    print(f"\nMT PROPOSALS ({len(top_lines)} above score 30.0):\n")
                    for tl in top_lines[:3]:
                        print(f"  {tl.strip()}")
            if result.get("mt_extensions_raw"):
                lines = result["mt_extensions_raw"].strip().split("\n")
                ext_lines = [l for l in lines if l.strip().startswith("[") or l.strip().startswith("MT-")]
                if ext_lines:
                    print(f"\nPHASE EXTENSIONS ({len(ext_lines)} proposals for existing MTs):\n")
                    for el in ext_lines[:3]:
                        print(f"  {el.strip()}")
    elif args[0] == "--json":
        result = run_slim_init()
        print(json.dumps(result, indent=2))
    elif args[0] == "orient":
        if SESSION_STATE_PATH.exists():
            state = parse_session_state(SESSION_STATE_PATH.read_text())
            print(json.dumps(state, indent=2))
        else:
            print("SESSION_STATE.md not found")
    elif args[0] == "smoke":
        result = run_smoke()
        print(json.dumps(result, indent=2))
    elif args[0] == "priority":
        result = run_priority()
        print(json.dumps(result, indent=2))
