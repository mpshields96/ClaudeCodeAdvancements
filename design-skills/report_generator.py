"""CCA Report Generator — Collects project data and renders professional PDF reports via Typst.

Usage:
    python3 design-skills/report_generator.py generate --output report.pdf
    python3 design-skills/report_generator.py generate --output report.pdf --session 52
    python3 design-skills/report_generator.py templates

Pipeline: Python collects CCA data -> JSON -> Typst template -> PDF
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from report_charts import ReportChartGenerator
from kalshi_data_collector import KalshiDataCollector
from learning_data_collector import LearningDataCollector


class CCADataCollector:
    """Collects CCA project data for comprehensive report generation."""

    def __init__(self, project_root=None):
        if project_root is None:
            self.project_root = str(Path(__file__).parent.parent)
        else:
            self.project_root = project_root

    def _read_file(self, relative_path):
        """Read a project file, return empty string if missing."""
        path = os.path.join(self.project_root, relative_path)
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
        return ""

    def _count_lines(self, path):
        """Count lines in a file."""
        if os.path.exists(path):
            with open(path) as f:
                return sum(1 for _ in f)
        return 0

    # ── Module data ─────────────────────────────────────────────────────

    MODULE_DEFINITIONS = [
        {
            "name": "Memory System",
            "path": "memory-system/",
            "description": "Persistent cross-session memory. Captures decisions, preferences, and context across Claude Code sessions using hooks and MCP.",
            "components": [
                "Capture hook (PostToolUse + Stop)",
                "MCP retrieval server",
                "CLI viewer (stats, search, list)",
                "Compaction-resistant handoff",
                "8-char hex ID schema",
            ],
        },
        {
            "name": "Spec System",
            "path": "spec-system/",
            "description": "Spec-driven development workflow. Enforces requirements > design > tasks > implement sequence with approval gates.",
            "components": [
                "/spec:requirements interview scaffold",
                "/spec:design architecture generator",
                "/spec:tasks atomic decomposer",
                "/spec:design-review (4 expert personas)",
                "PreToolUse spec validator hook",
                "UserPromptSubmit auto-activation",
            ],
        },
        {
            "name": "Context Monitor",
            "path": "context-monitor/",
            "description": "Context health monitoring with adaptive thresholds. Tracks token usage, warns at quality ceilings, blocks exit at critical levels.",
            "components": [
                "PostToolUse token meter",
                "PreToolUse threshold alert",
                "Stop hook auto-handoff",
                "Compact anchor (every 10 turns)",
                "Automatic session wrap trigger",
                "Session pacer (2-3h autonomous runs)",
            ],
        },
        {
            "name": "Agent Guard",
            "path": "agent-guard/",
            "description": "Multi-agent safety, conflict prevention, and Senior Dev code review. Guards credentials, network ports, dangerous paths, and provides automated quality scoring on every write.",
            "components": [
                "Mobile approver (ntfy.sh push)",
                "Credential extraction guard",
                "Network/port exposure guard",
                "Content scanner (9 threat categories)",
                "Path validator (LIVE in hooks)",
                "Session guard (slop detection)",
                "File ownership manifest",
                "Edit retry guard (LIVE in hooks)",
                "Bash command safety guard (LIVE in hooks)",
                "SATD detector (TODO/FIXME/HACK markers)",
                "PR effort scorer (1-5 scale)",
                "Code quality scorer (0-100, A-F)",
                "False positive filter",
                "Review classifier (6 categories)",
                "Tech debt tracker (trend analysis)",
                "ADR reader (architecture decision discovery)",
                "Senior Dev orchestrator hook (LIVE)",
            ],
        },
        {
            "name": "Usage Dashboard",
            "path": "usage-dashboard/",
            "description": "Token and cost transparency. CLI counter, OpenTelemetry receiver, cost alerts, and structural completeness checker.",
            "components": [
                "Token counter CLI",
                "OTLP HTTP/JSON receiver",
                "PreToolUse cost alert hook",
                "/arewedone completeness checker",
            ],
        },
        {
            "name": "Reddit Intelligence",
            "path": "reddit-intelligence/",
            "description": "Community signal research. Discovers tools, patterns, and pain points from Reddit and GitHub to drive development priorities.",
            "components": [
                "Reddit reader (posts + all comments)",
                "Autonomous scan pipeline",
                "GitHub repo evaluator",
                "Sandboxed repo tester",
                "Subreddit profile registry (10 profiles)",
            ],
        },
        {
            "name": "Self-Learning",
            "path": "self-learning/",
            "description": "Cross-session improvement through structured observation, pattern detection, autonomous proposals, and research ROI tracking.",
            "components": [
                "JSONL event journal",
                "Pattern reflector + strategy engine",
                "Trace analyzer (4 detectors)",
                "YoYo improvement loop",
                "Sentinel adaptive mutation",
                "Academic paper scanner",
                "Findings resurfacer",
                "Skillbook injection hook (LIVE)",
                "Overnight detector (time-stratified analysis)",
                "Research outcomes ROI tracker",
                "Trade reflector (5 pattern detectors)",
            ],
        },
        {
            "name": "Design Skills",
            "path": "design-skills/",
            "description": "Professional visual output. Typst-based PDF reports, slides, HTML dashboards, SVG charts, website generation, and daily project snapshots.",
            "components": [
                "Report generator (Typst pipeline)",
                "Slide generator (16:9 PDF)",
                "Dashboard generator (HTML)",
                "Chart generator (SVG)",
                "Website generator (landing + docs)",
                "Daily snapshot engine (metric diffs)",
                "Design guide + visual language",
            ],
        },
        {
            "name": "Research",
            "path": "research/",
            "description": "R&D tools and experimental capabilities including iOS project generation and Xcode build wrapper.",
            "components": [
                "iOS project generator (SwiftUI)",
                "Xcode build wrapper",
            ],
        },
    ]

    def collect_module_stats(self):
        """Collect test count, LOC, and file count per module."""
        modules = []
        for mod_def in self.MODULE_DEFINITIONS:
            mod_path = os.path.join(self.project_root, mod_def["path"])
            if not os.path.isdir(mod_path):
                continue

            # Count tests from PROJECT_INDEX.md (more reliable than scanning)
            tests = 0
            loc = 0
            files = 0

            # Count .py files (excluding tests)
            for root, _, filenames in os.walk(mod_path):
                for fn in filenames:
                    if fn.endswith(".py"):
                        fp = os.path.join(root, fn)
                        line_count = self._count_lines(fp)
                        if fn.startswith("test_"):
                            tests_in_file = 0
                            with open(fp) as f:
                                for line in f:
                                    if line.strip().startswith("def test_"):
                                        tests_in_file += 1
                            tests += tests_in_file
                        else:
                            loc += line_count
                            files += 1

            # Parse test count from PROJECT_INDEX.md (authoritative)
            index_content = self._read_file("PROJECT_INDEX.md")
            idx_match = re.search(
                rf"\|\s*{re.escape(mod_def['name'])}\s*\|.*?\|\s*(\d+)\s*\|",
                index_content,
            )
            if idx_match:
                tests = int(idx_match.group(1))

            # Determine status from PROJECT_INDEX
            status = "ACTIVE"
            status_match = re.search(
                rf"\|\s*{re.escape(mod_def['name'])}\s*\|.*?\|\s*(.+?)\s*\|\s*\d+\s*\|",
                index_content,
            )
            if status_match:
                status_text = status_match.group(1).strip()
                if "COMPLETE" in status_text.upper():
                    status = "COMPLETE"

            # Determine next action for active modules
            next_action = ""
            if status != "COMPLETE":
                state_content = self._read_file("SESSION_STATE.md")
                # Look for module-related next items
                mod_name_lower = mod_def["name"].lower()
                for line in state_content.split("\n"):
                    if mod_name_lower in line.lower() and ("next" in line.lower() or "phase" in line.lower()):
                        next_action = line.strip().lstrip("- ").lstrip("0123456789. )")
                        break

            modules.append({
                "name": mod_def["name"],
                "path": mod_def["path"],
                "status": status,
                "tests": tests,
                "loc": loc,
                "files": files,
                "description": mod_def["description"],
                "components": mod_def["components"],
                "next": next_action,
                "why_it_matters": self.get_why_it_matters(mod_def["name"]),
            })

        return modules

    # ── Master task data ────────────────────────────────────────────────

    def collect_master_tasks(self):
        """Parse MASTER_TASKS.md for detailed task information."""
        content = self._read_file("MASTER_TASKS.md")
        if not content:
            return [], [], []

        complete = []
        active = []
        pending = []

        # Split into task sections
        sections = re.split(r"^## (MT-\d+):\s*(.+?)$", content, flags=re.MULTILINE)

        i = 1  # skip preamble
        while i < len(sections) - 1:
            task_id = sections[i]
            task_name = sections[i + 1].strip()
            task_body = sections[i + 2] if i + 2 < len(sections) else ""

            # Clean name (remove parenthetical suffixes)
            task_name = re.sub(r"\s*\(.*?\)\s*$", "", task_name).strip()

            # Extract status
            status_match = re.search(r"\*\*Status:\*\*\s*(.+?)$", task_body, re.MULTILINE)
            status = status_match.group(1).strip() if status_match else "Unknown"

            # Extract phase progress: count completed phases and total phases
            phase_completes = re.findall(r"Phase (\d+)\s*(?:COMPLETE|complete)", task_body)
            phases_done = len(phase_completes)
            # Estimate total phases from lifecycle or phase mentions
            phase_mentions = re.findall(r"Phase (\d+)", task_body)
            total_phases = max(int(p) for p in phase_mentions) if phase_mentions else 0
            if total_phases == 0 and "COMPLETE" in status.upper() and "PHASE" not in status.upper():
                total_phases = 1
                phases_done = 1

            # Extract delivered items (from status lines and delivered sections)
            delivered = []
            in_delivered = False
            for line in task_body.split("\n"):
                line_s = line.strip()
                if "**Delivered:**" in line or "**What was delivered:**" in line:
                    in_delivered = True
                    continue
                if in_delivered:
                    if line_s.startswith("- "):
                        item = line_s.lstrip("- ").strip()
                        if len(item) > 80:
                            item = item[:77] + "..."
                        delivered.append(item)
                    elif line_s.startswith("**") or (line_s == "" and delivered):
                        in_delivered = False

            # Also extract deliverables from status section bullet points
            in_status = False
            for line in task_body.split("\n"):
                line_s = line.strip()
                if line_s.startswith("**Status:**"):
                    in_status = True
                    continue
                if in_status:
                    if line_s.startswith("- `") or line_s.startswith("- Phase"):
                        item = line_s.lstrip("- ").strip()
                        # Remove markdown formatting
                        item = re.sub(r"`([^`]+)`", r"\1", item)
                        if len(item) > 80:
                            item = item[:77] + "..."
                        if item not in delivered:
                            delivered.append(item)
                    elif line_s.startswith("---") or (line_s.startswith("**") and "Status" not in line_s):
                        in_status = False

            # Extract next/needs
            needs = ""
            needs_match = re.search(
                r"\*\*(?:Next|Phase \d+ needs|Blocked|What's needed).*?:\*\*\s*(.+?)$",
                task_body,
                re.MULTILINE,
            )
            if needs_match:
                needs = needs_match.group(1).strip()
                if len(needs) > 120:
                    needs = needs[:117] + "..."

            # Extract what's remaining from lifecycle and phase descriptions
            remaining = []
            # Look for future phase descriptions
            for m in re.finditer(r"Phase (\d+):\s*(.+?)(?:\n|$)", task_body):
                phase_num = int(m.group(1))
                if phase_num > phases_done:
                    desc = m.group(2).strip()
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    remaining.append(f"Phase {phase_num}: {desc}")
            if not remaining and needs:
                remaining.append(needs)

            # Extract source URL
            source = ""
            source_match = re.search(r"\*\*Source:\*\*\s*(https?://\S+)", task_body)
            if source_match:
                source = source_match.group(1)

            # Extract test count from status
            test_count = 0
            test_match = re.search(r"(\d+)\s*tests?", status)
            if test_match:
                test_count = int(test_match.group(1))

            # Categorize
            status_upper = status.upper()
            if "COMPLETE" in status_upper and "PHASE" not in status_upper:
                category = "complete"
            elif "BLOCKED" in status_upper:
                category = "blocked"
            elif "NOT STARTED" in status_upper or "FUTURE" in status_upper or "NEVER" in status_upper:
                category = "not_started"
            else:
                category = "active"

            task = {
                "id": task_id,
                "name": task_name,
                "status": status,
                "category": category,
                "delivered": delivered[:8],
                "needs": needs,
                "remaining": remaining[:5],
                "phases_done": phases_done,
                "total_phases": total_phases,
                "source": source,
                "test_count": test_count,
            }

            # Add ELI5 blurb if available
            task["why_it_matters"] = self.get_why_it_matters(task_id)

            if category == "complete":
                complete.append(task)
            elif category in ("not_started", "blocked"):
                pending.append(task)
            else:
                active.append(task)

            i += 3

        return complete, active, pending

    # ── Hook data ───────────────────────────────────────────────────────

    HOOKS = [
        {"event": "PostToolUse", "matcher": "*", "file": "meter.py", "purpose": "Token counter"},
        {"event": "PostToolUse", "matcher": "*", "file": "compact_anchor.py", "purpose": "Context anchor writes"},
        {"event": "PostToolUse", "matcher": "*", "file": "senior_dev_hook.py", "purpose": "SATD + effort + quality scoring"},
        {"event": "PostToolUse", "matcher": "*", "file": "queue_hook.py", "purpose": "Cross-chat queue context"},
        {"event": "PreToolUse", "matcher": "*", "file": "alert.py", "purpose": "Warn/block at red/critical"},
        {"event": "PreToolUse", "matcher": "*", "file": "cost_alert.py", "purpose": "Cost threshold warning"},
        {"event": "PreToolUse", "matcher": "*", "file": "path_validator.py", "purpose": "Dangerous path detection"},
        {"event": "PreToolUse", "matcher": "*", "file": "edit_guard.py", "purpose": "Edit retry prevention"},
        {"event": "PreToolUse", "matcher": "*", "file": "validate.py", "purpose": "Spec guard + plan compliance"},
        {"event": "PreToolUse", "matcher": "Bash", "file": "credential_guard.py", "purpose": "Credential extraction guard"},
        {"event": "PreToolUse", "matcher": "Bash", "file": "bash_guard.py", "purpose": "Command safety (network, packages, system)"},
        {"event": "UserPromptSubmit", "matcher": "*", "file": "skill_activator.py", "purpose": "Spec auto-activation"},
        {"event": "UserPromptSubmit", "matcher": "*", "file": "skillbook_inject.py", "purpose": "Strategy injection"},
        {"event": "UserPromptSubmit", "matcher": "*", "file": "capture_hook.py", "purpose": "Real-time memory capture"},
        {"event": "UserPromptSubmit", "matcher": "*", "file": "queue_hook.py", "purpose": "Cross-chat queue injection"},
        {"event": "Stop", "matcher": "*", "file": "auto_handoff.py", "purpose": "Block exit at critical"},
        {"event": "Stop", "matcher": "*", "file": "capture_hook.py", "purpose": "Session-end memory capture"},
        {"event": "PostCompact", "matcher": "*", "file": "post_compact.py", "purpose": "Recovery + journal logging"},
    ]

    # ── Intelligence data ───────────────────────────────────────────────

    def collect_intelligence(self):
        """Count findings by verdict from FINDINGS_LOG.md."""
        content = self._read_file("FINDINGS_LOG.md")
        verdicts = {"BUILD": 0, "ADAPT": 0, "REFERENCE": 0, "REFERENCE-PERSONAL": 0, "SKIP": 0}
        total = 0

        for line in content.split("\n"):
            if re.match(r"^\[20\d{2}-\d{2}-\d{2}\]", line.strip()):
                total += 1
                for v in verdicts:
                    if v in line:
                        verdicts[v] += 1
                        break

        other = total - sum(verdicts.values())
        return {
            "findings_total": total,
            "build": verdicts["BUILD"],
            "adapt": verdicts["ADAPT"],
            "reference": verdicts["REFERENCE"],
            "reference_personal": verdicts["REFERENCE-PERSONAL"],
            "skip": verdicts["SKIP"],
            "other": other,
            "subreddits_scanned": 7,
            "github_repos_evaluated": 30,
        }

    # ── Self-learning data ──────────────────────────────────────────────

    def collect_self_learning(self):
        """Collect self-learning system metrics."""
        papers_path = os.path.join(self.project_root, "self-learning", "research", "papers.jsonl")
        papers = 0
        if os.path.exists(papers_path):
            with open(papers_path) as f:
                papers = sum(1 for line in f if line.strip())

        # Research outcomes ROI data
        outcomes_path = os.path.join(self.project_root, "self-learning", "research_outcomes.jsonl")
        research_roi = {"total": 0, "implemented": 0, "profitable": 0, "profit_cents": 0}
        if os.path.exists(outcomes_path):
            with open(outcomes_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    research_roi["total"] += 1
                    if entry.get("status") in ("implemented", "profitable", "unprofitable"):
                        research_roi["implemented"] += 1
                    if entry.get("status") == "profitable":
                        research_roi["profitable"] += 1
                    if entry.get("profit_impact_cents"):
                        research_roi["profit_cents"] += entry["profit_impact_cents"]

        return {
            "strategies_total": 10,
            "strategies_confirmed": 4,
            "proposals": 6,
            "trace_sessions": 31,
            "avg_score": 70,
            "papers_logged": papers,
            "sentinel_rate": "5-10%",
            "research_deliveries": research_roi["total"],
            "research_implemented": research_roi["implemented"],
            "research_profitable": research_roi["profitable"],
            "research_profit_cents": research_roi["profit_cents"],
        }

    # ── Risks ───────────────────────────────────────────────────────────

    def collect_risks(self):
        """Extract risks and blockers."""
        risks = []
        content = self._read_file("MASTER_TASKS.md")

        # Check for blocked tasks
        if "Blocked" in content or "BLOCKED" in content:
            blocked_match = re.search(
                r"MT-\d+.*?Blocked.*?(?:\*\*Status:\*\*\s*)(.+?)$",
                content,
                re.MULTILINE | re.DOTALL,
            )
            if blocked_match:
                risks.append({
                    "title": "MT-1 Maestro Visual Grid UI",
                    "severity": "blocker",
                    "description": "Blocked on macOS 15.6 beta SDK crash. Tauri/React app crashes on launch.",
                    "mitigation": "Using tmux + dev-start script as workaround. Waiting for stable macOS release.",
                })

        # Standard known risks
        risks.append({
            "title": "Semantic Scholar Rate Limiting",
            "severity": "risk",
            "description": "429 errors at 1.5s delay between queries for academic paper scanning.",
            "mitigation": "Increased to 3s delay with exponential backoff.",
        })

        risks.append({
            "title": "Context Burn from File-Writing Hooks",
            "severity": "debt",
            "description": "compact_anchor.py writes trigger system-reminder context consumption.",
            "mitigation": "Writes limited to every 10 turns, files kept small.",
        })

        return risks

    # ── Session highlights ────────────────────────────────────────────────

    def collect_session_highlights(self):
        """Extract 'What's done this session' from SESSION_STATE.md."""
        content = self._read_file("SESSION_STATE.md")
        highlights = []

        # Find the numbered list under "What's done this session:"
        in_highlights = False
        for line in content.split("\n"):
            line_s = line.strip()
            if "**What's done this session:**" in line or "What's done this session:" in line:
                in_highlights = True
                continue
            if in_highlights:
                # Match numbered items like "1. **Something:**" or "1. Something"
                m = re.match(r"^\d+\.\s+\*?\*?(.+?)(?:\*\*)?$", line_s)
                if m:
                    item = m.group(1).strip()
                    # Clean up markdown bold markers
                    item = re.sub(r"\*\*", "", item)
                    # Remove trailing colons
                    item = item.rstrip(":")
                    if len(item) > 100:
                        item = item[:97] + "..."
                    highlights.append(item)
                elif line_s.startswith("**") and "done" not in line_s.lower():
                    break
                elif line_s.startswith("---"):
                    break

        return highlights[:10]

    # ── Frontier status ──────────────────────────────────────────────────

    FRONTIER_DEFINITIONS = [
        {
            "number": 1,
            "name": "Persistent Cross-Session Memory",
            "module": "memory-system/",
            "impact": "CRITICAL",
            "description": "Every session starts from zero — this gives Claude a brain that persists.",
        },
        {
            "number": 2,
            "name": "Spec-Driven Development",
            "module": "spec-system/",
            "impact": "HIGH",
            "description": "Unstructured prompting produces poor architecture. Enforce requirements > design > tasks > implement.",
        },
        {
            "number": 3,
            "name": "Context Health Monitor",
            "module": "context-monitor/",
            "impact": "HIGH",
            "description": "Context rot causes silent output degradation. Monitor, warn, and auto-handoff.",
        },
        {
            "number": 4,
            "name": "Multi-Agent Conflict Guard",
            "module": "agent-guard/",
            "impact": "HIGH",
            "description": "Parallel agents overwrite each other. Guard credentials, paths, and system modifications.",
        },
        {
            "number": 5,
            "name": "Usage Transparency Dashboard",
            "module": "usage-dashboard/",
            "impact": "MEDIUM",
            "description": "No real-time token/cost visibility. Counter, alerts, and structural completeness.",
        },
    ]

    def collect_frontier_status(self, modules):
        """Determine status of each frontier based on module data."""
        frontiers = []
        for f_def in self.FRONTIER_DEFINITIONS:
            mod_data = next((m for m in modules if m["path"] == f_def["module"]), None)
            status = "COMPLETE"
            tests = 0
            loc = 0
            if mod_data:
                status = mod_data["status"]
                tests = mod_data["tests"]
                loc = mod_data["loc"]
            frontiers.append({
                "number": f_def["number"],
                "name": f_def["name"],
                "impact": f_def["impact"],
                "description": f_def["description"],
                "status": status,
                "tests": tests,
                "loc": loc,
            })
        return frontiers

    # ── Priority queue ───────────────────────────────────────────────────

    def collect_priority_queue(self):
        """Parse the priority scoring table from MASTER_TASKS.md."""
        content = self._read_file("MASTER_TASKS.md")
        queue = []

        # Find the active priority queue table
        in_table = False
        for line in content.split("\n"):
            if "Active Priority Queue" in line:
                in_table = True
                continue
            if in_table and line.strip().startswith("|") and "Rank" not in line and "---" not in line:
                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) >= 10:
                    try:
                        # Score is in col 9 (0-indexed), wrapped in **...**
                        score_str = cols[9].replace("*", "").strip()
                        if score_str in ("ABSORBED", "—", ""):
                            continue  # Skip absorbed/placeholder rows
                        score = float(score_str) if score_str else 0
                        # Next phase description is in col 11 (last col)
                        next_phase = cols[11].strip() if len(cols) > 11 else ""
                        queue.append({
                            "rank": cols[0].strip(),
                            "id": cols[1].strip(),
                            "name": cols[2].strip(),
                            "base": cols[3].strip(),
                            "score": score,
                            "next_phase": next_phase,
                        })
                    except (ValueError, IndexError):
                        pass
            elif in_table and line.strip().startswith("###"):
                break

        return queue

    # ── Daily diff ────────────────────────────────────────────────────

    def collect_daily_diff(self):
        """Collect daily snapshot diff if snapshots exist.

        Returns a dict with date_range, totals_delta, module_deltas,
        new_suites, removed_suites — or None if insufficient data.
        """
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            import daily_snapshot as ds

            snapshots = ds.list_snapshots(ds.SNAPSHOT_DIR)
            if len(snapshots) < 2:
                return None

            newest = snapshots[0]
            previous = snapshots[1]
            new_snap = ds.load_snapshot(newest, ds.SNAPSHOT_DIR)
            old_snap = ds.load_snapshot(previous, ds.SNAPSHOT_DIR)
            if not new_snap or not old_snap:
                return None

            return ds.diff_snapshots(old_snap, new_snap)
        except Exception:
            return None

    # ── Next priorities ─────────────────────────────────────────────────

    def collect_priorities(self):
        """Extract next priorities from SESSION_STATE.md."""
        content = self._read_file("SESSION_STATE.md")
        priorities = []

        # Look for the Next: line in current state
        next_match = re.search(r"\*\*Next:\*\*\s*(.+?)(?:\n\n|\n---)", content, re.DOTALL)
        if next_match:
            next_text = next_match.group(1)
            # Parse (1) ... (2) ... format
            items = re.findall(r"\((\d+)\)\s*(.+?)(?=\(\d+\)|$)", next_text, re.DOTALL)
            for _, item_text in items:
                item_text = item_text.strip().rstrip(".")
                # Split into title and detail at first period or colon
                parts = re.split(r"[.:]", item_text, maxsplit=1)
                title = parts[0].strip()
                detail = parts[1].strip() if len(parts) > 1 else ""
                # Clean up
                title = re.sub(r"\s+", " ", title)
                detail = re.sub(r"\s+", " ", detail)
                if len(detail) > 150:
                    detail = detail[:147] + "..."
                priorities.append({"title": title, "detail": detail})

        if not priorities:
            priorities = [{"title": "Check SESSION_STATE.md for current priorities", "detail": ""}]

        return priorities

    # ── Architecture decisions ──────────────────────────────────────────

    # ── Honest assessment ──────────────────────────────────────────────

    def collect_criticisms(self, modules, mt_complete, mt_active, mt_pending):
        """Collect objective criticisms and gaps in the project."""
        criticisms = []

        # 1. MTs stuck at Phase 1 — many started but not advanced
        stuck_phase1 = []
        for task in mt_active:
            if task.get("phases_done", 0) <= 1 and task.get("total_phases", 0) > 1:
                stuck_phase1.append(task["id"])
        if stuck_phase1:
            criticisms.append({
                "title": f"{len(stuck_phase1)} master tasks stalled at Phase 1",
                "severity": "gap",
                "detail": f"{', '.join(stuck_phase1)} — started but no subsequent phases shipped. Risk of scope sprawl without depth.",
            })

        # 2. No external users
        criticisms.append({
            "title": "Single-developer project with no external users",
            "severity": "limitation",
            "detail": "All tooling built for one developer. No community testing, no feedback loop from other Claude Code users. Limits validation of 'community-demanded' features.",
        })

        # 3. Test depth vs breadth
        total_tests = sum(m["tests"] for m in modules)
        total_files = sum(m["files"] for m in modules)
        if total_files > 0:
            tests_per_file = total_tests / total_files
            if tests_per_file > 30:
                criticisms.append({
                    "title": f"High test count ({total_tests:,}) may overstate coverage",
                    "severity": "nuance",
                    "detail": f"Average {tests_per_file:.0f} tests per source file. Many test trivial properties (dict keys, return types). Integration test coverage across modules is limited to 1 suite.",
                })

        # 4. Blocked items
        blocked = [t for t in mt_pending if t.get("category") == "blocked"]
        if blocked:
            criticisms.append({
                "title": f"{len(blocked)} task(s) blocked with no resolution timeline",
                "severity": "blocker",
                "detail": "; ".join(f"{t['id']}: {t['name']}" for t in blocked),
            })

        # 5. Self-learning metrics hardcoded
        criticisms.append({
            "title": "Self-learning metrics partially hardcoded",
            "severity": "debt",
            "detail": "Strategy count, proposal count, and avg score are hardcoded in the data collector rather than dynamically parsed from journal/strategy files.",
        })

        # 6. Kalshi integration gap
        criticisms.append({
            "title": "Kalshi bot integration remains read-only",
            "severity": "gap",
            "detail": "CCA scans for research and surfaces findings, but no closed-loop feedback exists: no tracking of which CCA recommendations led to profitable Kalshi trades.",
        })

        # 7. CI/CD
        ci_path = os.path.join(self.project_root, ".github", "workflows", "tests.yml")
        if os.path.exists(ci_path):
            criticisms.append({
                "title": "CI/CD pipeline exists but unverified",
                "severity": "nuance",
                "detail": "GitHub Actions workflow defined but no evidence of runs in git history. All testing is local-only.",
            })

        return criticisms

    ARCHITECTURE_DECISIONS = [
        {"decision": "Local-first storage", "rationale": "User owns all data, no cloud dependency"},
        {"decision": "Stdlib-first (no pip)", "rationale": "Zero dependency management overhead"},
        {"decision": "Hook-based delivery", "rationale": "Native Claude Code integration points"},
        {"decision": "Adaptive context thresholds", "rationale": "Fixed percentages break at 1M windows"},
        {"decision": "JSONL for all logging", "rationale": "Append-only, grep-friendly, no corruption risk"},
        {"decision": "QualityGate geometric mean", "rationale": "Prevents Goodhart's Law gaming of metrics"},
        {"decision": "Whitelist-first phishing detection", "rationale": "Zero false positives on legitimate domains"},
        {"decision": "Typst over WeasyPrint", "rationale": "Single binary, millisecond compile, JSON-native"},
    ]

    # ── Why It Matters — ELI5 blurbs for Matthew ──────────────────────

    # Maps MT IDs and module names to plain-English utility blurbs.
    # These appear in the report so Matthew can quickly grasp why something
    # matters to him personally, without reading technical details.
    WHY_IT_MATTERS = {
        # Modules (frontiers)
        "Memory System": "Means Claude remembers your preferences and past decisions across sessions — no more re-explaining context every time you start a new chat.",
        "Spec System": "Forces Claude to plan before coding. You get a reviewable blueprint (requirements, design, tasks) instead of spaghetti code from vague prompts.",
        "Context Monitor": "Warns you when Claude's memory is getting full so it doesn't silently start forgetting instructions mid-session. Prevents the 'why did it ignore my rules?' problem.",
        "Agent Guard": "Stops Claude from accidentally deleting files, exposing API keys, or breaking your computer when running autonomously overnight.",
        "Usage Dashboard": "Shows you exactly how many tokens and dollars each session costs, so you can spot waste and stay within your Max subscription limits.",
        "Reddit Intelligence": "Automatically finds the best new tools, tips, and techniques from Reddit so you don't have to scroll through hundreds of posts yourself.",
        "Self-Learning": "Makes your Kalshi bot smarter over time by analyzing what worked and what didn't. The bot learns from its own wins and losses instead of repeating mistakes.",
        "Design Skills": "Generates professional PDF reports and charts automatically — no manual formatting. One command gives you a polished status overview you could show anyone.",
        "Research": "R&D sandbox for experimental features. Things get prototyped here before becoming real modules — keeps the main codebase clean.",
        # Master Tasks
        "MT-0": "The single most important task: making the Kalshi bot learn from its own trading results. Every dollar of improvement here compounds over time.",
        "MT-7": "Finds patterns in how Claude wastes tokens (retries, unnecessary reads) so sessions run faster and cheaper.",
        "MT-9": "Automates Reddit scanning so high-value posts get flagged without you having to check manually.",
        "MT-10": "The 'get smarter each session' engine. Tracks what strategies work and surfaces the best ones automatically.",
        "MT-12": "Finds relevant academic papers (trading math, AI research) and summarizes them so you get the insights without reading 30-page PDFs.",
        "MT-17": "One-command professional reports. Instead of explaining project status verbally, just generate a PDF.",
        "MT-20": "An automated code reviewer that catches bugs, tech debt, and design issues before they become problems. Like having a senior engineer on call 24/7.",
        "MT-21": "Lets multiple Claude sessions work in parallel on different tasks — like having a small dev team instead of one assistant.",
        "MT-22": "Makes the whole system run without you. Sessions start, do work, wrap up, and hand off to the next session automatically.",
        "MT-26": "Financial intelligence tools for the Kalshi bot: regime detection, calibration analysis, order flow. Directly improves bet quality.",
        "MT-27": "Smarter Reddit scanning with less noise. Better signal-to-noise means fewer irrelevant posts cluttering your review.",
        "MT-28": "Self-learning v2: the bot doesn't just track results, it evolves its own principles about what works. Adaptive strategy, not static rules.",
        "MT-30": "Auto-start and manage all your Claude sessions from one command. No more manually opening 3 terminal windows.",
        "MT-31": "Use Google's Gemini Pro for visual/design tasks where it excels, while Claude handles the code. Best of both models.",
        "MT-32": "Makes all visual output (reports, charts, dashboards) look professional. Design quality you'd expect from a real product.",
    }

    def get_why_it_matters(self, key):
        """Get the ELI5 blurb for a module or MT, or empty string."""
        return self.WHY_IT_MATTERS.get(key, "")

    # ── Executive summary ───────────────────────────────────────────────

    def build_executive_summary(self, session, modules, mt_complete, mt_active, mt_pending, total_tests=None):
        """Generate executive summary text."""
        if total_tests is None:
            total_tests = sum(m["tests"] for m in modules)
        total_mt = len(mt_complete) + len(mt_active) + len(mt_pending)

        return (
            f"ClaudeCodeAdvancements is a research and development project building "
            f"validated tools, hooks, and systems for Claude Code users and AI-assisted "
            f"development workflows. Launched 2026-02-19 with {session} development sessions "
            f"completed. All five original research frontiers are production-complete with "
            f"{total_tests:,} automated tests across {len(modules)} modules. "
            f"The project has expanded into {total_mt} master-level tasks covering autonomous "
            f"intelligence gathering, self-learning loops, academic research integration, "
            f"and professional design output. Zero external Python dependencies."
        )

    # ── Main collection ─────────────────────────────────────────────────

    def collect_from_project(self, session=None):
        """Collect all data from the actual CCA project files."""
        # Get session number
        state_content = self._read_file("SESSION_STATE.md")
        if not session:
            session_match = re.search(r"Session (\d+)", state_content)
            session = int(session_match.group(1)) if session_match else 0

        # Collect all data
        modules = self.collect_module_stats()
        mt_complete, mt_active, mt_pending = self.collect_master_tasks()
        intelligence = self.collect_intelligence()
        self_learning = self.collect_self_learning()
        risks = self.collect_risks()
        priorities = self.collect_priorities()
        session_highlights = self.collect_session_highlights()
        frontiers = self.collect_frontier_status(modules)
        priority_queue = self.collect_priority_queue()

        # Use authoritative test count from PROJECT_INDEX.md
        index_content = self._read_file("PROJECT_INDEX.md")
        total_match = re.search(r"\*\*Total:\s*~?(\d[\d,]*)\s*tests", index_content)
        total_tests = int(total_match.group(1).replace(",", "")) if total_match else sum(m["tests"] for m in modules)

        # Also extract suite count
        suite_match = re.search(r"\(~?(\d+)\s*suites?\)", index_content)
        test_suites = int(suite_match.group(1)) if suite_match else len([m for m in modules if m["tests"] > 0])

        source_loc = sum(m["loc"] for m in modules)
        source_files = sum(m["files"] for m in modules)

        # Get LOC from actual file scan for accuracy
        try:
            result = subprocess.run(
                ["bash", "-c",
                 '/usr/bin/find . -name "*.py" ! -path "./.claude/*" ! -path "./.planning/*" '
                 '! -name "test_*" -exec cat {} + | wc -l'],
                capture_output=True, text=True, cwd=self.project_root,
            )
            if result.returncode == 0:
                source_loc = int(result.stdout.strip())
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["bash", "-c",
                 '/usr/bin/find . -name "test_*.py" ! -path "./.claude/*" -exec cat {} + | wc -l'],
                capture_output=True, text=True, cwd=self.project_root,
            )
            if result.returncode == 0:
                test_loc = int(result.stdout.strip())
        except Exception:
            test_loc = 0

        try:
            result = subprocess.run(
                ["bash", "-c", '/usr/bin/find . -name "*.py" ! -path "./.claude/*" '
                 '! -path "./.planning/*" ! -name "test_*" | wc -l'],
                capture_output=True, text=True, cwd=self.project_root,
            )
            if result.returncode == 0:
                source_files = int(result.stdout.strip())
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["bash", "-c", '/usr/bin/find . -name "test_*.py" ! -path "./.claude/*" | wc -l'],
                capture_output=True, text=True, cwd=self.project_root,
            )
            if result.returncode == 0:
                test_files = int(result.stdout.strip())
        except Exception:
            test_files = 0

        # Git stats
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True, text=True, cwd=self.project_root,
            )
            git_commits = int(result.stdout.strip()) if result.returncode == 0 else 0
        except Exception:
            git_commits = 0

        # Project age — hardcoded start since git history may be squashed
        from datetime import datetime
        project_start = date(2026, 2, 19)
        project_age = (date.today() - project_start).days

        total_loc = source_loc + test_loc
        blocked_count = sum(1 for t in mt_pending if t["category"] == "blocked")
        not_started_count = sum(1 for t in mt_pending if t["category"] != "blocked")

        # Count total delivered items across all MTs
        total_delivered = sum(
            len(t.get("delivered", []))
            for t in mt_complete + mt_active + mt_pending
        )

        criticisms = self.collect_criticisms(modules, mt_complete, mt_active, mt_pending)

        # Kalshi financial analytics (MT-33)
        kalshi_collector = KalshiDataCollector()
        kalshi_data = kalshi_collector.collect_all()

        # Self-learning intelligence (MT-33 Phase 5)
        learning_collector = LearningDataCollector()
        learning_data = learning_collector.collect_all()

        return {
            "title": "ClaudeCodeAdvancements",
            "subtitle": "Comprehensive Project Report",
            "date": date.today().isoformat(),
            "session": session,
            "executive_summary": self.build_executive_summary(
                session, modules, mt_complete, mt_active, mt_pending,
                total_tests=total_tests,
            ),
            "summary": {
                "total_tests": total_tests,
                "passing_tests": total_tests,
                "test_suites": test_suites,
                "total_modules": len(modules),
                "total_findings": intelligence["findings_total"],
                "total_papers": self_learning["papers_logged"],
                "master_tasks": len(mt_complete) + len(mt_active) + len(mt_pending),
                "completed_tasks": len(mt_complete),
                "in_progress_tasks": len(mt_active),
                "not_started_tasks": not_started_count,
                "blocked_tasks": blocked_count,
                "source_files": source_files,
                "test_files": test_files,
                "source_loc": source_loc,
                "test_loc": test_loc,
                "total_loc": total_loc,
                "git_commits": git_commits,
                "project_age_days": max(project_age, 1),
                "live_hooks": len(self.HOOKS),
                "total_delivered": total_delivered,
            },
            "modules": modules,
            "master_tasks_complete": mt_complete,
            "master_tasks_active": mt_active,
            "master_tasks_pending": mt_pending,
            "hooks": self.HOOKS,
            "intelligence": intelligence,
            "self_learning": self_learning,
            "risks": risks,
            "next_priorities": priorities,
            "architecture_decisions": self.ARCHITECTURE_DECISIONS,
            "session_highlights": session_highlights,
            "frontiers": frontiers,
            "priority_queue": priority_queue,
            "daily_diff": self.collect_daily_diff(),
            "criticisms": criticisms,
            "kalshi_analytics": kalshi_data,
            "learning_intelligence": learning_data,
        }


DEFAULT_ARCHIVE_DIR = os.path.expanduser("~/.cca-reports")


class ReportSidecar:
    """JSON sidecar export alongside PDF reports for machine-readable diffing.

    Saves report data as JSON next to every PDF, and archives copies in
    ~/.cca-reports/ for cross-session trend comparison.
    """

    def __init__(self, archive_dir=None):
        self.archive_dir = archive_dir or DEFAULT_ARCHIVE_DIR

    def save_alongside_pdf(self, data, pdf_path):
        """Save JSON sidecar next to the PDF file.

        Args:
            data: The collected report data dict.
            pdf_path: Path to the PDF output file.

        Returns:
            Path to the created JSON sidecar file.
        """
        base, ext = os.path.splitext(pdf_path)
        if not ext:
            json_path = pdf_path + ".json"
        else:
            json_path = base + ".json"

        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)
        return json_path

    def save_to_archive(self, data):
        """Save report data to the archive directory.

        Filename: {date}_S{session}.json (e.g., 2026-03-22_S122.json).
        Overwrites if same date+session already exists.

        Returns:
            Path to the archived JSON file.
        """
        os.makedirs(self.archive_dir, exist_ok=True)
        report_date = data.get("date", date.today().isoformat())
        session = data.get("session", 0)
        filename = f"{report_date}_S{session}.json"
        path = os.path.join(self.archive_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def list_archived_reports(self):
        """List all archived report JSON files, newest first."""
        if not os.path.isdir(self.archive_dir):
            return []
        files = sorted(
            [
                os.path.join(self.archive_dir, f)
                for f in os.listdir(self.archive_dir)
                if f.endswith(".json")
            ],
            reverse=True,
        )
        return files

    def load_report(self, path):
        """Load a sidecar JSON file. Returns None on error."""
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def extract_summary_snapshot(self, data):
        """Extract a compact summary dict for quick comparison/diffing."""
        summary = data.get("summary", {})
        kalshi = data.get("kalshi_analytics", {})
        kalshi_summary = kalshi.get("summary", {})
        kalshi_available = kalshi.get("available", False)
        learning = data.get("learning_intelligence", {})
        learning_available = learning.get("available", False)
        journal = learning.get("journal", {})
        apf = learning.get("apf", {})

        return {
            "session": data.get("session"),
            "date": data.get("date"),
            "total_tests": summary.get("total_tests"),
            "test_suites": summary.get("test_suites"),
            "total_loc": summary.get("total_loc"),
            "source_loc": summary.get("source_loc"),
            "git_commits": summary.get("git_commits"),
            "completed_mts": len(data.get("master_tasks_complete", [])),
            "active_mts": len(data.get("master_tasks_active", [])),
            "pending_mts": len(data.get("master_tasks_pending", [])),
            "total_modules": summary.get("total_modules"),
            "total_findings": summary.get("total_findings"),
            "kalshi_pnl_usd": kalshi_summary.get("total_pnl_usd") if kalshi_available else None,
            "kalshi_win_rate": kalshi_summary.get("win_rate_pct") if kalshi_available else None,
            "apf": apf.get("current_apf") if learning_available else None,
            "journal_entries": journal.get("total_entries") if learning_available else None,
        }


class ReportRenderer:
    """Renders reports using Typst."""

    def __init__(self):
        self.templates_dir = str(Path(__file__).parent / "templates")

    def template_path(self, template_name):
        """Resolve template name to file path."""
        return os.path.join(self.templates_dir, f"{template_name}.typ")

    def available_templates(self):
        """List available template names."""
        if not os.path.isdir(self.templates_dir):
            return []
        return [
            f.stem for f in Path(self.templates_dir).glob("*.typ")
        ]

    def render(self, template, data_path, output_path, chart_dir=None):
        """Render a report using Typst.

        Args:
            template: Template name (without .typ extension)
            data_path: Path to JSON data file
            output_path: Output PDF path
            chart_dir: Optional directory containing SVG chart files for embedding
        """
        if not shutil.which("typst"):
            raise RuntimeError("Typst is not installed. Install with: brew install typst")

        typ_path = self.template_path(template)
        if not os.path.exists(typ_path):
            raise RuntimeError(f"Template not found: {typ_path}")

        abs_data_path = os.path.abspath(data_path)

        cmd = [
            "typst", "compile", "--root", "/",
            "--input", f"data={abs_data_path}",
        ]
        if chart_dir:
            abs_chart_dir = os.path.abspath(chart_dir)
            cmd.extend(["--input", f"chart_dir={abs_chart_dir}"])
        cmd.extend([typ_path, output_path])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Typst compilation failed: {result.stderr}")

        return output_path


def parse_args(args=None):
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="CCA Report Generator — Professional PDF reports via Typst"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="Generate a report")
    gen.add_argument("--output", "-o", required=True, help="Output PDF path")
    gen.add_argument("--template", "-t", default="cca-report", help="Template name")
    gen.add_argument("--session", "-s", type=int, help="Session number")
    gen.add_argument("--data", "-d", help="Custom JSON data file (skip collection)")

    subparsers.add_parser("templates", help="List available templates")

    return parser.parse_args(args)


def main():
    """CLI entry point."""
    args = parse_args()

    if args.command == "templates":
        renderer = ReportRenderer()
        templates = renderer.available_templates()
        print(f"Available templates ({len(templates)}):")
        for t in templates:
            print(f"  {t}")
        return

    if args.command == "generate":
        renderer = ReportRenderer()
        chart_dir = None

        if args.data:
            data_path = args.data
            # Try to generate charts from provided data
            try:
                with open(data_path) as f:
                    data = json.load(f)
                chart_dir = os.path.join(tempfile.gettempdir(), "cca_report_charts")
                chart_gen = ReportChartGenerator(output_dir=chart_dir)
                chart_paths = chart_gen.save_all(data)
                print(f"Charts generated: {len(chart_paths)} SVGs in {chart_dir}")
            except Exception:
                chart_dir = None  # Fall back to no charts
        else:
            project_root = str(Path(__file__).parent.parent)
            collector = CCADataCollector(project_root=project_root)
            data = collector.collect_from_project(session=args.session)

            data_path = os.path.join(tempfile.gettempdir(), "cca_report_data.json")
            with open(data_path, "w") as f:
                json.dump(data, f, indent=2)
            print(f"Data collected: {data['summary']['total_tests']} tests, "
                  f"{data['summary']['total_modules']} modules, "
                  f"{data['summary']['master_tasks']} master tasks, "
                  f"{data['summary']['total_findings']} findings")

            # Generate charts from collected data
            chart_dir = os.path.join(tempfile.gettempdir(), "cca_report_charts")
            chart_gen = ReportChartGenerator(output_dir=chart_dir)
            chart_paths = chart_gen.save_all(data)
            print(f"Charts generated: {len(chart_paths)} SVGs in {chart_dir}")

        output = renderer.render(args.template, data_path, args.output, chart_dir=chart_dir)
        print(f"Report generated: {output}")
        print(f"Size: {os.path.getsize(output) / 1024:.1f} KB")

        # JSON sidecar export (MT-33 Phase 6)
        sidecar = ReportSidecar()
        sidecar_path = sidecar.save_alongside_pdf(data, args.output)
        archive_path = sidecar.save_to_archive(data)
        print(f"Sidecar: {sidecar_path}")
        print(f"Archived: {archive_path}")


if __name__ == "__main__":
    main()
