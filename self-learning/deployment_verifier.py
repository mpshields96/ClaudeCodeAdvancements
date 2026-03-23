"""MT-0 Deployment Verifier — validates self-learning integration in Kalshi bot.

Checks whether the polymarket-bot has properly integrated CCA's self-learning
system by looking for expected files, journal entries, and wiring.

Usage:
    # From CCA project:
    python3 self-learning/deployment_verifier.py /path/to/polymarket-bot
    python3 self-learning/deployment_verifier.py ~/Projects/polymarket-bot

    # Programmatic:
    from deployment_verifier import DeploymentVerifier
    v = DeploymentVerifier("/path/to/polymarket-bot")
    summary = v.run_all()
    print(v.format_report(summary))
"""
import json
import os
import sys

# Valid event types matching CCA journal.py trading schema
VALID_EVENT_TYPES = [
    "bet_placed",
    "bet_outcome",
    "market_research",
    "edge_discovered",
    "edge_rejected",
    "strategy_shift",
]


class DeploymentVerifier:
    """Validates MT-0 self-learning deployment in the Kalshi bot."""

    def __init__(self, bot_root):
        self.bot_root = bot_root

    def _path(self, *parts):
        return os.path.join(self.bot_root, *parts)

    def _file_exists(self, *parts):
        return os.path.isfile(self._path(*parts))

    def _read_file(self, *parts):
        path = self._path(*parts)
        if os.path.isfile(path):
            with open(path) as f:
                return f.read()
        return ""

    # ── Individual checks ────────────────────────────────────────────────

    def check_trading_journal(self):
        """Check if trading_journal.py exists with log_event function."""
        path = self._path("src", "self_learning", "trading_journal.py")
        if not os.path.isfile(path):
            return {"check": "trading_journal", "status": "FAIL",
                    "message": "src/self_learning/trading_journal.py not found"}

        content = self._read_file("src", "self_learning", "trading_journal.py")
        if "log_event" not in content:
            return {"check": "trading_journal", "status": "WARN",
                    "message": "trading_journal.py exists but log_event function not found"}

        return {"check": "trading_journal", "status": "PASS",
                "message": "trading_journal.py found with log_event"}

    def check_research_tracker(self):
        """Check if research_tracker.py exists."""
        path = self._path("src", "self_learning", "research_tracker.py")
        if not os.path.isfile(path):
            return {"check": "research_tracker", "status": "FAIL",
                    "message": "src/self_learning/research_tracker.py not found"}

        content = self._read_file("src", "self_learning", "research_tracker.py")
        if "log_research_outcome" not in content:
            return {"check": "research_tracker", "status": "WARN",
                    "message": "research_tracker.py exists but log_research_outcome not found"}

        return {"check": "research_tracker", "status": "PASS",
                "message": "research_tracker.py found with log_research_outcome"}

    def check_journal_data(self):
        """Check if trading journal JSONL has valid entries."""
        path = self._path("data", "trading_journal.jsonl")
        if not os.path.isfile(path):
            return {"check": "journal_data", "status": "FAIL",
                    "message": "data/trading_journal.jsonl not found"}

        entries = []
        invalid_count = 0
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                    if not self.validate_entry(entry):
                        invalid_count += 1
                except json.JSONDecodeError:
                    invalid_count += 1

        if not entries:
            return {"check": "journal_data", "status": "WARN",
                    "message": "trading_journal.jsonl exists but is empty",
                    "entry_count": 0}

        if invalid_count > 0:
            return {"check": "journal_data", "status": "WARN",
                    "message": f"{len(entries)} entries, {invalid_count} invalid",
                    "entry_count": len(entries), "invalid_count": invalid_count}

        return {"check": "journal_data", "status": "PASS",
                "message": f"{len(entries)} valid entries",
                "entry_count": len(entries)}

    def check_live_wiring(self):
        """Check if live.py references trading_journal."""
        path = self._path("src", "execution", "live.py")
        if not os.path.isfile(path):
            return {"check": "live_wiring", "status": "SKIP",
                    "message": "src/execution/live.py not found (may use different path)"}

        content = self._read_file("src", "execution", "live.py")
        if "trading_journal" not in content and "log_event" not in content:
            return {"check": "live_wiring", "status": "FAIL",
                    "message": "live.py exists but no trading_journal reference found"}

        return {"check": "live_wiring", "status": "PASS",
                "message": "live.py references trading_journal"}

    # ── Schema validation ────────────────────────────────────────────────

    def validate_entry(self, entry):
        """Validate a journal entry against the MT-0 schema."""
        if not isinstance(entry, dict):
            return False
        required = ["event_type", "domain", "metrics"]
        for field in required:
            if field not in entry:
                return False
        if entry["event_type"] not in VALID_EVENT_TYPES:
            return False
        if not isinstance(entry["metrics"], dict):
            return False
        return True

    # ── Aggregate ────────────────────────────────────────────────────────

    def run_all(self):
        """Run all deployment checks and return structured summary."""
        checks = [
            self.check_trading_journal(),
            self.check_research_tracker(),
            self.check_journal_data(),
            self.check_live_wiring(),
        ]

        statuses = [c["status"] for c in checks]
        pass_count = statuses.count("PASS")
        fail_count = statuses.count("FAIL")
        active_checks = [s for s in statuses if s != "SKIP"]

        if fail_count == len(active_checks):
            overall = "FAIL"
        elif pass_count == len(active_checks):
            overall = "PASS"
        else:
            overall = "PARTIAL"

        return {"checks": checks, "overall": overall,
                "pass_count": pass_count, "fail_count": fail_count}

    def format_report(self, summary):
        """Format summary as human-readable text report."""
        lines = [
            "MT-0 Deployment Verification Report",
            "=" * 40,
            f"Overall: {summary['overall']}",
            f"Passed: {summary['pass_count']} / {len(summary['checks'])}",
            "",
        ]
        for check in summary["checks"]:
            icon = {"PASS": "[OK]", "FAIL": "[!!]", "WARN": "[??]", "SKIP": "[--]"}.get(check["status"], "[??]")
            lines.append(f"  {icon} {check['check']}: {check['message']}")

        if summary["overall"] == "FAIL":
            lines.extend([
                "",
                "Next step: Follow KALSHI_MT0_TASK_BRIEF.md to deploy self-learning.",
            ])
        elif summary["overall"] == "PARTIAL":
            lines.extend([
                "",
                "Some components deployed. Complete remaining items from task brief.",
            ])

        return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 deployment_verifier.py /path/to/polymarket-bot")
        sys.exit(1)

    bot_root = os.path.expanduser(sys.argv[1])
    if not os.path.isdir(bot_root):
        print(f"Error: {bot_root} is not a directory")
        sys.exit(1)

    verifier = DeploymentVerifier(bot_root)
    summary = verifier.run_all()
    print(verifier.format_report(summary))
    sys.exit(0 if summary["overall"] == "PASS" else 1)


if __name__ == "__main__":
    main()
