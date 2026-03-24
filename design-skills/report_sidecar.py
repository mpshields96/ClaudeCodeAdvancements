"""Report sidecar — JSON export alongside PDF for machine-parseable report data.

Extracts key metrics from the full report data dict and saves a compact JSON
that future chats can load for continuity and trend comparison.

Usage:
    from report_sidecar import ReportSidecar
    sidecar = ReportSidecar()
    sidecar.save(data, "/path/to/report.pdf")  # saves report.sidecar.json

    # Load for comparison:
    old = sidecar.load("/path/to/old_report.sidecar.json")
"""
import json
import os
from datetime import datetime, timezone


class ReportSidecar:
    """Generates and manages JSON sidecar files for CCA reports."""

    SIDECAR_VERSION = 1

    def extract(self, data):
        """Extract key metrics from full report data dict.

        Returns a compact dict suitable for JSON serialization and
        consumption by report_differ.py or future chat sessions.
        """
        summary = data.get("summary", {})
        kalshi = data.get("kalshi_analytics", {})
        learning = data.get("learning_intelligence", {})

        return {
            "sidecar_version": self.SIDECAR_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "session": data.get("session"),
            "date": data.get("date"),

            # CCA project summary
            "summary": {
                "total_tests": summary.get("total_tests", 0),
                "test_suites": summary.get("test_suites", 0),
                "total_loc": summary.get("total_loc", 0),
                "source_loc": summary.get("source_loc", 0),
                "test_loc": summary.get("test_loc", 0),
                "source_files": summary.get("source_files", 0),
                "test_files": summary.get("test_files", 0),
                "git_commits": summary.get("git_commits", 0),
                "live_hooks": summary.get("live_hooks", 0),
                "total_delivered": summary.get("total_delivered", 0),
                "total_findings": data.get("intelligence", {}).get("findings_total", 0),
                "total_papers": data.get("self_learning", {}).get("papers", 0),
                "completed_tasks": len(data.get("master_tasks_complete", [])),
                "in_progress_tasks": len(data.get("master_tasks_active", [])),
            },

            # Module-level metrics
            "modules": [
                {
                    "name": m.get("name", ""),
                    "tests": m.get("tests", 0),
                    "loc": m.get("loc", 0),
                }
                for m in data.get("modules", [])
            ],

            # Master task status
            "master_tasks_complete": [
                {"id": mt.get("id", ""), "name": mt.get("name", "")}
                for mt in data.get("master_tasks_complete", [])
            ],
            "master_tasks_active": [
                {"id": mt.get("id", ""), "name": mt.get("name", "")}
                for mt in data.get("master_tasks_active", [])
            ],
            "master_tasks_pending": [
                {"id": mt.get("id", ""), "name": mt.get("name", "")}
                for mt in data.get("master_tasks_pending", [])
            ],

            # Kalshi analytics (if available)
            "kalshi_analytics": self._extract_kalshi(kalshi),

            # Self-learning intelligence (if available)
            "learning_intelligence": self._extract_learning(learning),
        }

    def _extract_kalshi(self, kalshi):
        """Extract key Kalshi metrics for sidecar."""
        if not kalshi.get("available"):
            return {"available": False}

        summary = kalshi.get("summary", {})
        return {
            "available": True,
            "total_trades": summary.get("total_trades", 0),
            "settled_trades": summary.get("settled_trades", 0),
            "win_rate_pct": summary.get("win_rate_pct"),
            "total_pnl_usd": summary.get("total_pnl_usd"),
            "avg_pnl_usd": summary.get("avg_pnl_usd"),
            "best_strategy": summary.get("best_strategy"),
            "strategies": [
                {
                    "name": s.get("strategy", ""),
                    "trades": s.get("trade_count", 0),
                    "win_rate": s.get("win_rate_pct"),
                    "pnl": s.get("total_pnl_usd"),
                }
                for s in kalshi.get("strategies", [])
            ],
        }

    def _extract_learning(self, learning):
        """Extract key self-learning metrics for sidecar."""
        if not learning.get("available"):
            return {"available": False}

        journal = learning.get("journal", {})
        apf = learning.get("apf", {})
        return {
            "available": True,
            "total_entries": journal.get("total_entries", 0),
            "event_counts": journal.get("event_counts", {}),
            "domain_counts": journal.get("domain_counts", {}),
            "current_apf": apf.get("current_apf"),
            "apf_target": apf.get("target", 40.0),
        }

    def save(self, data, pdf_path):
        """Save sidecar JSON alongside a PDF report.

        Args:
            data: Full report data dict from collect_from_project().
            pdf_path: Path to the PDF file. Sidecar goes next to it.

        Returns:
            Path to the saved sidecar JSON file.
        """
        sidecar = self.extract(data)
        sidecar_path = self._sidecar_path(pdf_path)
        os.makedirs(os.path.dirname(sidecar_path) or ".", exist_ok=True)
        with open(sidecar_path, "w") as f:
            json.dump(sidecar, f, indent=2)
        return sidecar_path

    def load(self, path):
        """Load a sidecar JSON file. Returns None if missing or invalid."""
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def find_latest(self, archive_dir):
        """Find the most recent sidecar in an archive directory.

        Returns (path, data) tuple, or (None, None) if none found.
        """
        if not os.path.isdir(archive_dir):
            return None, None

        sidecars = sorted(
            [f for f in os.listdir(archive_dir) if f.endswith(".sidecar.json")],
            reverse=True,
        )
        if not sidecars:
            return None, None

        path = os.path.join(archive_dir, sidecars[0])
        data = self.load(path)
        return (path, data) if data else (None, None)

    @staticmethod
    def _sidecar_path(pdf_path):
        """Derive sidecar path from PDF path: report.pdf -> report.sidecar.json."""
        base = pdf_path.rsplit(".", 1)[0] if "." in pdf_path else pdf_path
        return f"{base}.sidecar.json"
