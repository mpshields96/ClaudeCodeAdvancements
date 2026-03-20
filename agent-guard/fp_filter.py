#!/usr/bin/env python3
"""FP Filter — MT-20 Senior Dev Agent: false positive filter for SATD/effort findings.

Reduces noise by:
- Identifying test files (lower priority for SATD/effort findings)
- Identifying vendored files (skip entirely)
- Scoring confidence that a finding is NOT a false positive (0.0-1.0)
- Filtering a list of findings to only high-confidence ones

Confidence rules:
- Vendored files: 0.0 (always skip)
- Test files: 0.6 (reduce, but HIGH severity findings still pass)
- Normal files: 1.0 (full confidence)
"""

import re
from typing import Optional


# Vendored path segments (case-sensitive)
_VENDOR_SEGMENTS = {
    "vendor",
    "node_modules",
    ".venv",
    "venv",
    "site-packages",
    "dist-packages",
    ".tox",
    "bower_components",
    "generated",
    "third_party",
}

# Regex patterns for test file detection
_TEST_FILE_PATTERNS = [
    re.compile(r"(?:^|/)test_[^/]+$"),           # test_*.py
    re.compile(r"(?:^|/)[^/]+_test\.[^/]+$"),    # *_test.go, *_test.py
    re.compile(r"(?:^|/)__tests__/"),             # __tests__/ directory
    re.compile(r"(?:^|/)tests?/"),               # tests/ or test/ directory
    re.compile(r"\.(test|spec)\.[^/]+$"),         # *.test.js, *.spec.ts
]

# Severity levels considered HIGH (always pass through even in test files)
_HIGH_SEVERITY_VALUES = {"HIGH", "CRITICAL", "high", "critical"}

# Confidence floor for test files
_TEST_FILE_CONFIDENCE = 0.6


class FPFilter:
    def is_test_file(self, file_path) -> bool:
        """Return True if the file appears to be a test file."""
        if not file_path:
            return False
        path = str(file_path)
        # Normalize to forward slashes
        path = path.replace("\\", "/")
        return any(p.search(path) for p in _TEST_FILE_PATTERNS)

    def is_vendored(self, file_path) -> bool:
        """Return True if the file is in a vendored/third-party directory."""
        if not file_path:
            return False
        path = str(file_path).replace("\\", "/")
        segments = path.split("/")
        return any(seg in _VENDOR_SEGMENTS for seg in segments)

    def should_skip(self, file_path) -> bool:
        """Return True if the file should be skipped entirely (vendored)."""
        return self.is_vendored(file_path)

    def confidence(self, file_path, finding_text: str = "") -> float:
        """
        Return confidence [0.0, 1.0] that a finding from this file is NOT a false positive.

        - Vendored files: 0.0
        - Test files: 0.6
        - Normal files: 1.0
        """
        if not file_path:
            return 1.0
        if self.is_vendored(file_path):
            return 0.0
        if self.is_test_file(file_path):
            return _TEST_FILE_CONFIDENCE
        return 1.0

    def filter_findings(self, findings: list, file_path: str, threshold: float = 0.5) -> list:
        """
        Filter findings list based on confidence threshold and severity.

        - Vendored files: all findings dropped (confidence = 0.0)
        - Test files: HIGH severity findings always kept; others filtered at threshold
        - Normal files: all findings kept
        """
        if not findings:
            return []

        conf = self.confidence(file_path)
        if conf == 0.0:
            return []

        if conf >= 1.0:
            return list(findings)

        # Test file path: keep HIGH severity, filter others
        result = []
        for finding in findings:
            severity = finding.get("severity", "")
            if severity in _HIGH_SEVERITY_VALUES:
                result.append(finding)
            elif conf >= threshold:
                result.append(finding)

        return result
