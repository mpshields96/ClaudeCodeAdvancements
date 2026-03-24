"""Self-learning intelligence data collector for MT-33 Strategic Intelligence Report.

Reads journal.jsonl and APF snapshots to extract learning metrics,
event distributions, and trend data for report charts.

Usage:
    from learning_data_collector import LearningDataCollector
    collector = LearningDataCollector()
    data = collector.collect_all()

Data sources:
    - self-learning/journal.jsonl — structured event journal
    - ~/.cca-apf-snapshots.jsonl — APF trend snapshots per session
"""
import json
import os
from collections import Counter
from pathlib import Path


DEFAULT_JOURNAL = str(
    Path(__file__).parent.parent / "self-learning" / "journal.jsonl"
)
DEFAULT_APF = os.path.expanduser("~/.cca-apf-snapshots.jsonl")


class LearningDataCollector:
    """Collects self-learning intelligence data for report integration."""

    def __init__(self, journal_path=None, apf_path=None):
        self.journal_path = journal_path or DEFAULT_JOURNAL
        self.apf_path = apf_path or DEFAULT_APF

    def is_available(self):
        """Check if at least one data source exists."""
        return (
            os.path.exists(self.journal_path) and os.path.getsize(self.journal_path) > 0
        ) or (
            os.path.exists(self.apf_path) and os.path.getsize(self.apf_path) > 0
        )

    def _read_jsonl(self, path):
        """Read JSONL file, skip malformed lines."""
        entries = []
        if not os.path.exists(path):
            return entries
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    # ── Journal stats ────────────────────────────────────────────────────

    def get_journal_stats(self):
        """Aggregate journal event statistics."""
        entries = self._read_jsonl(self.journal_path)
        if not entries:
            return self._empty_journal()

        event_counts = Counter()
        domain_counts = Counter()
        timestamps = []

        for e in entries:
            event_type = e.get("event_type", "unknown")
            event_counts[event_type] += 1
            domain = e.get("domain")
            if domain:
                domain_counts[domain] += 1
            ts = e.get("timestamp", "")
            if ts:
                timestamps.append(ts)

        wins = event_counts.get("win", 0)
        pains = event_counts.get("pain", 0)
        win_pain_ratio = round(wins / pains, 2) if pains > 0 else None

        timestamps.sort()

        return {
            "total_entries": len(entries),
            "event_counts": dict(event_counts.most_common()),
            "domain_counts": dict(domain_counts.most_common()),
            "first_entry": timestamps[0] if timestamps else "",
            "last_entry": timestamps[-1] if timestamps else "",
            "wins": wins,
            "pains": pains,
            "win_pain_ratio": win_pain_ratio,
        }

    def _empty_journal(self):
        return {
            "total_entries": 0,
            "event_counts": {},
            "domain_counts": {},
            "first_entry": "",
            "last_entry": "",
            "wins": 0,
            "pains": 0,
            "win_pain_ratio": None,
        }

    # ── APF stats ────────────────────────────────────────────────────────

    def get_apf_stats(self):
        """Extract APF trend and current state."""
        snapshots = self._read_jsonl(self.apf_path)
        if not snapshots:
            return self._empty_apf()

        latest = snapshots[-1]
        trend = [
            {
                "session": s.get("session", ""),
                "apf": s.get("apf", 0),
                "total": s.get("total", 0),
                "build": s.get("build", 0),
                "signal": s.get("signal", 0),
            }
            for s in snapshots
        ]

        apf_change = 0.0
        if len(snapshots) >= 2:
            apf_change = round(
                snapshots[-1].get("apf", 0) - snapshots[-2].get("apf", 0), 1
            )

        # Frontier breakdown from latest
        frontier_breakdown = []
        by_frontier = latest.get("by_frontier", {})
        for name, data in sorted(by_frontier.items()):
            if isinstance(data, dict) and data.get("total", 0) > 0:
                frontier_breakdown.append({
                    "frontier": name,
                    "apf": data.get("apf", 0),
                    "total": data.get("total", 0),
                })

        return {
            "current_apf": latest.get("apf", 0),
            "latest_session": latest.get("session", ""),
            "total_reviewed": latest.get("total", 0),
            "total_build": latest.get("build", 0),
            "total_signal": latest.get("signal", 0),
            "apf_change": apf_change,
            "trend": trend,
            "frontier_breakdown": frontier_breakdown,
        }

    def _empty_apf(self):
        return {
            "current_apf": 0,
            "latest_session": "",
            "total_reviewed": 0,
            "total_build": 0,
            "total_signal": 0,
            "apf_change": 0,
            "trend": [],
            "frontier_breakdown": [],
        }

    # ── Chart-ready data ─────────────────────────────────────────────────

    def chart_event_types(self):
        """BarChart data: journal event type distribution."""
        stats = self.get_journal_stats()
        counts = stats["event_counts"]
        # Filter out infrastructure noise — these dominate charts but aren't learning events
        noise_types = {"unknown", "context_monitor_alert", "compact_anchor", "meter_update",
                       "hook_fired", "queue_check"}
        filtered = {k: v for k, v in counts.items() if k not in noise_types}
        sorted_items = sorted(filtered.items(), key=lambda x: -x[1])
        return {
            "labels": [item[0] for item in sorted_items],
            "values": [item[1] for item in sorted_items],
        }

    def chart_apf_trend(self):
        """Sparkline/LineChart data: APF score over sessions."""
        stats = self.get_apf_stats()
        trend = stats["trend"]
        return {
            "labels": [t["session"] for t in trend],
            "values": [t["apf"] for t in trend],
        }

    def chart_domain_distribution(self):
        """DonutChart data: journal entries by domain."""
        stats = self.get_journal_stats()
        counts = stats["domain_counts"]
        sorted_items = sorted(counts.items(), key=lambda x: -x[1])
        return {
            "labels": [item[0] for item in sorted_items],
            "values": [item[1] for item in sorted_items],
        }

    # ── Aggregator ───────────────────────────────────────────────────────

    def collect_all(self):
        """Collect all self-learning data for report integration."""
        available = self.is_available()
        return {
            "available": available,
            "journal": self.get_journal_stats(),
            "apf": self.get_apf_stats(),
            "charts": {
                "event_types": self.chart_event_types(),
                "apf_trend": self.chart_apf_trend(),
                "domain_distribution": self.chart_domain_distribution(),
            },
        }
