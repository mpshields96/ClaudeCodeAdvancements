#!/usr/bin/env python3
"""Senior Dev Hook — MT-20 PostToolUse orchestrator.

Runs on every Write/Edit tool call. Orchestrates:
1. SATD Detector — surfaces TODO/FIXME/HACK/WORKAROUND markers
2. Effort Scorer — estimates review complexity (1-5 scale)
3. False Positive Filter — reduces noise (when available)
4. Review Classifier — CRScore-style output filtering (when available)

Combines all findings into a single additionalContext string.
Gracefully degrades if submodules are not yet built (imports guarded).

Entry point: stdin JSON (PostToolUse payload) -> stdout JSON (hook response).
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import Optional

# Add agent-guard to path for sibling imports
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

# Import submodules with graceful degradation
_satd_available = False
_effort_available = False
_fp_filter_available = False
_review_classifier_available = False

try:
    from satd_detector import SATDDetector
    _satd_available = True
except ImportError:
    pass

try:
    from effort_scorer import EffortScorer
    _effort_available = True
except ImportError:
    pass

try:
    from fp_filter import FPFilter
    _fp_filter_available = True
except ImportError:
    pass

try:
    from review_classifier import ReviewClassifier
    _review_classifier_available = True
except ImportError:
    pass


# Max combined additionalContext length
MAX_CONTEXT_LENGTH = 2000

# Only emit effort context for scores >= this threshold
EFFORT_THRESHOLD = 3

# File extensions to skip entirely (non-code)
SKIP_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".txt", ".rst", ".toml", ".ini", ".cfg", ".lock"}


@dataclass
class SeniorDevFinding:
    """A single finding from any submodule."""
    source: str       # "satd", "effort", "fp_filter", "review_classifier"
    severity: str     # "HIGH", "MEDIUM", "LOW", "INFO"
    message: str


class SeniorDevHook:
    """PostToolUse hook that orchestrates all senior dev submodules."""

    def __init__(self):
        self._satd = SATDDetector() if _satd_available else None
        self._effort = EffortScorer() if _effort_available else None
        self._fp_filter = FPFilter() if _fp_filter_available else None
        self._classifier = ReviewClassifier() if _review_classifier_available else None

    @property
    def available_modules(self) -> list:
        """Return list of available submodule names."""
        modules = []
        if self._satd:
            modules.append("satd_detector")
        if self._effort:
            modules.append("effort_scorer")
        if self._fp_filter:
            modules.append("fp_filter")
        if self._classifier:
            modules.append("review_classifier")
        return modules

    def analyze(self, content: str, file_path: str = "") -> list:
        """Run all available submodules on content. Returns list of SeniorDevFinding."""
        if not content:
            return []

        # Skip non-code files
        if file_path:
            ext = _get_extension(file_path)
            if ext in SKIP_EXTENSIONS:
                return []

        findings = []

        # 1. SATD Detection
        if self._satd:
            markers = self._satd.scan_file_content(content, file_path=file_path)
            for m in markers:
                findings.append(SeniorDevFinding(
                    source="satd",
                    severity=m.level.name,
                    message=f"Line {m.line}: {m.marker_type} — {m.text}",
                ))

        # 2. Effort Scoring
        if self._effort:
            score = self._effort.score_content(content, file_path=file_path)
            if score.score >= EFFORT_THRESHOLD:
                findings.append(SeniorDevFinding(
                    source="effort",
                    severity="INFO",
                    message=f"Effort: {score.score}/5 ({score.label}) — {score.loc} LOC, {score.complexity} complexity markers",
                ))

        return findings

    def format_context(self, findings: list) -> str:
        """Format findings into a concise additionalContext string."""
        if not findings:
            return ""

        # Sort by severity: HIGH > MEDIUM > LOW > INFO
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
        sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 4))

        lines = ["[Senior Dev] Code quality findings:"]
        for f in sorted_findings:
            lines.append(f"  [{f.severity}] ({f.source}) {f.message}")

        context = "\n".join(lines)

        # Truncate if too long
        if len(context) > MAX_CONTEXT_LENGTH:
            # Keep HIGH findings, truncate the rest
            high_findings = [f for f in sorted_findings if f.severity == "HIGH"]
            other_count = len(sorted_findings) - len(high_findings)

            trunc_lines = ["[Senior Dev] Code quality findings (truncated):"]
            for f in high_findings:
                trunc_lines.append(f"  [{f.severity}] ({f.source}) {f.message}")
            if other_count > 0:
                trunc_lines.append(f"  ... and {other_count} lower-severity findings")

            context = "\n".join(trunc_lines)
            if len(context) > MAX_CONTEXT_LENGTH:
                context = context[:MAX_CONTEXT_LENGTH - 3] + "..."

        return context

    def hook_output(self, payload: dict) -> dict:
        """
        Process a PostToolUse hook payload.
        Returns {} if no findings, or {"additionalContext": "..."} if findings.
        """
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {})

        # Only analyze Write and Edit
        if tool_name == "Write":
            content = tool_input.get("content", "")
            file_path = tool_input.get("file_path", "")
        elif tool_name == "Edit":
            content = tool_input.get("new_string", "")
            file_path = tool_input.get("file_path", "")
        else:
            return {}

        if not content:
            return {}

        findings = self.analyze(content, file_path=file_path)
        if not findings:
            return {}

        context = self.format_context(findings)
        if not context:
            return {}

        return {"additionalContext": context}


def _get_extension(file_path: str) -> str:
    """Return lowercase file extension including dot, or '' if none."""
    basename = file_path.split("/")[-1]
    if "." not in basename:
        return ""
    return "." + basename.rsplit(".", 1)[-1].lower()


def main():
    """PostToolUse hook entry point. Reads stdin JSON, outputs hook response JSON."""
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({}))
            return

        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({}))
        return

    hook = SeniorDevHook()
    output = hook.hook_output(payload)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
