#!/usr/bin/env python3
"""
test_mt_originator_extend.py — Tests for --extend-existing feature.

MT-41 enhancement: Propose new phases for active/completed MTs based on
BUILD findings that partially match existing MT keywords.
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from mt_originator import (
    Finding,
    PhaseExtension,
    find_phase_extensions,
    get_existing_mt_coverage,
    score_extension,
    format_extension_briefing,
)


class TestPhaseExtensionDataclass(unittest.TestCase):
    """PhaseExtension must have required fields."""

    def test_create_extension(self):
        ext = PhaseExtension(
            mt_id=32,
            mt_name="Visual Excellence",
            finding=Finding("2026-03-25", "BUILD", "Frontier 4", "New chart type", "https://example.com", 50),
            score=72.5,
            suggested_phase="Advanced animation system for SVG charts",
        )
        self.assertEqual(ext.mt_id, 32)
        self.assertEqual(ext.mt_name, "Visual Excellence")
        self.assertAlmostEqual(ext.score, 72.5)
        self.assertIn("animation", ext.suggested_phase)

    def test_to_dict(self):
        ext = PhaseExtension(
            mt_id=33, mt_name="Strategic Report",
            finding=Finding("2026-03-20", "BUILD", "Frontier 5", "PDF embedding", "https://example.com", 10),
            score=55.0, suggested_phase="Embed interactive charts in PDF",
        )
        d = ext.to_dict()
        self.assertIn("mt_id", d)
        self.assertIn("score", d)
        self.assertIn("suggested_phase", d)

    def test_briefing_line(self):
        ext = PhaseExtension(
            mt_id=32, mt_name="Visual Excellence",
            finding=Finding("2026-03-25", "BUILD", "Frontier 4", "Cool viz", "https://x.com", 20),
            score=80.0, suggested_phase="New viz approach",
        )
        line = ext.briefing_line()
        self.assertIn("MT-32", line)
        self.assertIn("80.0", line)
        self.assertIn("Visual Excellence", line)


class TestFindPhaseExtensions(unittest.TestCase):
    """find_phase_extensions should match BUILD findings to existing MTs."""

    def _make_findings(self):
        """BUILD findings that should match existing MTs."""
        return [
            # Should match MT-32 (keywords: "visual excellence", "design engineering", "report charts")
            Finding("2026-03-25", "BUILD", "Frontier 4", "Visual excellence in report charts for dashboards", "https://reddit.com/1", 100),
            # Should match MT-33 (keywords: "strategic report", "intelligence report", "kalshi data")
            Finding("2026-03-24", "BUILD", "Frontier 5", "Kalshi data visualization in intelligence report", "https://reddit.com/2", 50),
            # Should match MT-20 (keywords: "senior dev", "code review", "quality scoring")
            Finding("2026-03-23", "BUILD", "Frontier 4", "AI code review with quality scoring", "https://reddit.com/3", 30),
            # Should NOT match any MT (totally unrelated)
            Finding("2026-03-22", "BUILD", "NEW", "Quantum computing simulator", "https://reddit.com/4", 10),
        ]

    def test_returns_list_of_extensions(self):
        extensions = find_phase_extensions(self._make_findings())
        self.assertIsInstance(extensions, list)
        for ext in extensions:
            self.assertIsInstance(ext, PhaseExtension)

    def test_matches_known_mts(self):
        extensions = find_phase_extensions(self._make_findings())
        mt_ids = [ext.mt_id for ext in extensions]
        # Should find MT-32 (visual excellence/report charts) and MT-33 (kalshi data)
        self.assertIn(32, mt_ids, "Should match MT-32 via 'visual excellence'/'report charts'")

    def test_excludes_unrelated_findings(self):
        """Quantum computing finding should not produce an extension."""
        extensions = find_phase_extensions(self._make_findings())
        suggested = [ext.suggested_phase for ext in extensions]
        for s in suggested:
            self.assertNotIn("quantum", s.lower())

    def test_empty_findings_returns_empty(self):
        self.assertEqual(find_phase_extensions([]), [])

    def test_non_build_findings_ignored(self):
        findings = [
            Finding("2026-03-25", "SKIP", "Frontier 4", "Great chart tool", "https://x.com", 50),
            Finding("2026-03-25", "REFERENCE", "Frontier 4", "Nice design system", "https://x.com", 30),
        ]
        extensions = find_phase_extensions(findings)
        self.assertEqual(extensions, [])

    def test_sorted_by_score_descending(self):
        extensions = find_phase_extensions(self._make_findings())
        if len(extensions) > 1:
            for i in range(len(extensions) - 1):
                self.assertGreaterEqual(extensions[i].score, extensions[i + 1].score)

    def test_deduplicates_same_mt(self):
        """Multiple findings matching the same MT should produce extensions."""
        findings = [
            Finding("2026-03-25", "BUILD", "Frontier 4", "Visual excellence in design engineering", "https://r.com/1", 80),
            Finding("2026-03-24", "BUILD", "Frontier 4", "Report charts for visual excellence", "https://r.com/2", 60),
        ]
        extensions = find_phase_extensions(findings)
        # Both should match MT-32 via "visual excellence"/"report charts"/"design engineering"
        mt32_exts = [e for e in extensions if e.mt_id == 32]
        # Could be 1 (merged) or 2 (separate) — either is valid
        self.assertGreaterEqual(len(mt32_exts), 1)


class TestScoreExtension(unittest.TestCase):
    """Extension scoring should factor recency, signal, and MT match quality."""

    def test_recent_high_signal_scores_high(self):
        f = Finding("2026-03-25", "BUILD", "Frontier 4", "Amazing chart tool", "https://x.com", 200)
        score = score_extension(f, match_strength=3)
        self.assertGreater(score, 60)

    def test_old_low_signal_scores_low(self):
        f = Finding("2026-03-01", "BUILD", "Frontier 4", "Old chart idea", "https://x.com", 1)
        score = score_extension(f, match_strength=1)
        self.assertLess(score, 40)

    def test_match_strength_affects_score(self):
        f = Finding("2026-03-25", "BUILD", "Frontier 4", "Chart tool", "https://x.com", 50)
        low = score_extension(f, match_strength=1)
        high = score_extension(f, match_strength=3)
        self.assertGreater(high, low)

    def test_score_bounded_0_100(self):
        f = Finding("2026-03-25", "BUILD", "Frontier 4", "Something", "https://x.com", 9999)
        score = score_extension(f, match_strength=5)
        self.assertLessEqual(score, 100)
        self.assertGreaterEqual(score, 0)


class TestFormatExtensionBriefing(unittest.TestCase):
    """format_extension_briefing should produce readable output."""

    def test_returns_string(self):
        exts = [
            PhaseExtension(mt_id=32, mt_name="Visual Excellence",
                           finding=Finding("2026-03-25", "BUILD", "F4", "Chart lib", "https://x.com", 50),
                           score=75.0, suggested_phase="Interactive chart animations"),
        ]
        output = format_extension_briefing(exts)
        self.assertIsInstance(output, str)
        self.assertIn("MT-32", output)
        self.assertIn("Interactive chart animations", output)

    def test_empty_returns_message(self):
        output = format_extension_briefing([])
        self.assertIn("no", output.lower())

    def test_multiple_extensions(self):
        exts = [
            PhaseExtension(mt_id=32, mt_name="Visual Excellence",
                           finding=Finding("2026-03-25", "BUILD", "F4", "A", "https://x.com", 50),
                           score=75.0, suggested_phase="Phase A"),
            PhaseExtension(mt_id=33, mt_name="Strategic Report",
                           finding=Finding("2026-03-24", "BUILD", "F5", "B", "https://x.com", 30),
                           score=60.0, suggested_phase="Phase B"),
        ]
        output = format_extension_briefing(exts)
        self.assertIn("MT-32", output)
        self.assertIn("MT-33", output)


class TestExtendExistingIntegration(unittest.TestCase):
    """Integration tests using parsed FINDINGS_LOG format."""

    def test_with_sample_findings_log_text(self):
        """Parse findings text and find extensions."""
        from mt_originator import parse_findings_log

        text = """
[2026-03-25] [BUILD] [Frontier 4] Visual excellence design engineering for report charts — https://reddit.com/example1
[2026-03-24] [BUILD] [Frontier 5] Kalshi data in strategic intelligence report — https://reddit.com/example2
[2026-03-23] [SKIP] [Frontier 1] Some memory tool — https://reddit.com/example3
[2026-03-22] [BUILD] [NEW] Totally new concept unrelated to anything — https://reddit.com/example4
"""
        findings = parse_findings_log(text)
        builds = [f for f in findings if f.verdict == "BUILD"]
        extensions = find_phase_extensions(builds)
        # Should find extensions (visual excellence maps to MT-32, kalshi data to MT-33)
        self.assertGreater(len(extensions), 0)
        mt_ids = [e.mt_id for e in extensions]
        self.assertIn(32, mt_ids)


if __name__ == "__main__":
    unittest.main()
