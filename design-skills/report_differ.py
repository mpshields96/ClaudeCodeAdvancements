"""Report differ — compares two JSON sidecar reports to highlight trends.

Produces structured diffs showing what changed between report snapshots:
test growth, LOC changes, MT status transitions, Kalshi P&L movement, APF trends.

Usage:
    from report_differ import ReportDiffer
    differ = ReportDiffer()
    diff = differ.diff_reports(old_data, new_data)
    print(differ.format_summary(diff))

    # Or from files:
    diff = differ.diff_from_files("old.json", "new.json")
"""
import json
import os


class ReportDiffer:
    """Compares two report sidecar JSONs and produces structured diffs."""

    # Summary fields to track with deltas
    TRACKED_SUMMARY_FIELDS = [
        "total_tests", "test_suites", "total_loc", "source_loc", "test_loc",
        "git_commits", "source_files", "test_files", "total_findings",
        "total_papers", "total_delivered", "completed_tasks", "in_progress_tasks",
    ]

    def diff_reports(self, old, new):
        """Diff two report data dicts.

        Args:
            old: The older report data dict.
            new: The newer report data dict.

        Returns:
            Structured diff dict with changes across all report sections.
        """
        return {
            "sessions": self._diff_sessions(old, new),
            "summary_changes": self._diff_summary(old, new),
            "module_changes": self._diff_modules(old, new),
            "mt_changes": self._diff_master_tasks(old, new),
            "kalshi_changes": self._diff_kalshi(old, new),
            "learning_changes": self._diff_learning(old, new),
        }

    def diff_from_files(self, old_path, new_path):
        """Diff two report JSON files by path. Returns None if either is missing."""
        for p in (old_path, new_path):
            if not os.path.exists(p):
                return None
        try:
            with open(old_path) as f:
                old = json.load(f)
            with open(new_path) as f:
                new = json.load(f)
            return self.diff_reports(old, new)
        except (json.JSONDecodeError, OSError):
            return None

    def _diff_sessions(self, old, new):
        return {
            "old": old.get("session"),
            "new": new.get("session"),
            "old_date": old.get("date"),
            "new_date": new.get("date"),
        }

    def _diff_summary(self, old, new):
        old_summary = old.get("summary", {})
        new_summary = new.get("summary", {})
        changes = {}
        for field in self.TRACKED_SUMMARY_FIELDS:
            old_val = old_summary.get(field, 0) or 0
            new_val = new_summary.get(field, 0) or 0
            changes[field] = {
                "old": old_val,
                "new": new_val,
                "delta": new_val - old_val,
            }
        return changes

    def _diff_modules(self, old, new):
        old_mods = {m["name"]: m for m in old.get("modules", [])}
        new_mods = {m["name"]: m for m in new.get("modules", [])}
        all_names = sorted(set(list(old_mods.keys()) + list(new_mods.keys())))

        changes = []
        for name in all_names:
            om = old_mods.get(name, {})
            nm = new_mods.get(name, {})
            is_new = name not in old_mods
            changes.append({
                "name": name,
                "tests_old": om.get("tests", 0),
                "tests_new": nm.get("tests", 0),
                "tests_delta": nm.get("tests", 0) - om.get("tests", 0),
                "loc_old": om.get("loc", 0),
                "loc_new": nm.get("loc", 0),
                "loc_delta": nm.get("loc", 0) - om.get("loc", 0),
                "is_new": is_new,
            })
        return changes

    def _diff_master_tasks(self, old, new):
        old_complete_ids = {mt["id"] for mt in old.get("master_tasks_complete", [])}
        new_complete_ids = {mt["id"] for mt in new.get("master_tasks_complete", [])}
        old_active_ids = {mt["id"] for mt in old.get("master_tasks_active", [])}
        new_active_ids = {mt["id"] for mt in new.get("master_tasks_active", [])}

        # Build lookup for names
        all_mts = {}
        for lst in ("master_tasks_complete", "master_tasks_active", "master_tasks_pending"):
            for mt in old.get(lst, []) + new.get(lst, []):
                all_mts[mt["id"]] = mt

        newly_completed = [
            all_mts[mid] for mid in (new_complete_ids - old_complete_ids)
        ]
        newly_active = [
            all_mts[mid] for mid in (new_active_ids - old_active_ids)
        ]

        old_summary = old.get("summary", {})
        new_summary = new.get("summary", {})

        return {
            "newly_completed": sorted(newly_completed, key=lambda x: x["id"]),
            "newly_active": sorted(newly_active, key=lambda x: x["id"]),
            "completed_delta": (new_summary.get("completed_tasks", 0) or 0) -
                               (old_summary.get("completed_tasks", 0) or 0),
        }

    def _diff_kalshi(self, old, new):
        old_k = old.get("kalshi_analytics", {})
        new_k = new.get("kalshi_analytics", {})
        old_avail = old_k.get("available", False)
        new_avail = new_k.get("available", False)

        if not old_avail and not new_avail:
            return {"pnl_delta": None, "win_rate_delta": None, "became_available": False}

        if not old_avail and new_avail:
            return {"pnl_delta": None, "win_rate_delta": None, "became_available": True}

        old_s = old_k.get("summary", {})
        new_s = new_k.get("summary", {})

        old_pnl = old_s.get("total_pnl_usd", 0) or 0
        new_pnl = new_s.get("total_pnl_usd", 0) or 0
        old_wr = old_s.get("win_rate_pct", 0) or 0
        new_wr = new_s.get("win_rate_pct", 0) or 0

        return {
            "pnl_delta": round(new_pnl - old_pnl, 2),
            "win_rate_delta": round(new_wr - old_wr, 1),
            "became_available": False,
        }

    def _diff_learning(self, old, new):
        old_l = old.get("learning_intelligence", {})
        new_l = new.get("learning_intelligence", {})
        old_avail = old_l.get("available", False)
        new_avail = new_l.get("available", False)

        if not old_avail or not new_avail:
            return {"apf_delta": None, "journal_delta": None, "became_available": not old_avail and new_avail}

        old_apf = old_l.get("apf", {}).get("current_apf", 0) or 0
        new_apf = new_l.get("apf", {}).get("current_apf", 0) or 0
        old_journal = old_l.get("journal", {}).get("total_entries", 0) or 0
        new_journal = new_l.get("journal", {}).get("total_entries", 0) or 0

        return {
            "apf_delta": round(new_apf - old_apf, 1),
            "journal_delta": new_journal - old_journal,
            "became_available": False,
        }

    def format_summary(self, diff):
        """Format a diff as human-readable text."""
        lines = []
        sessions = diff["sessions"]
        lines.append(f"Report Diff: S{sessions['old']} ({sessions['old_date']}) -> S{sessions['new']} ({sessions['new_date']})")
        lines.append("")

        # Check if anything changed
        sc = diff["summary_changes"]
        has_summary = any(v["delta"] != 0 for v in sc.values())
        mt_c = diff["mt_changes"]
        has_mt = bool(mt_c["newly_completed"] or mt_c["newly_active"])
        has_modules = any(m["tests_delta"] != 0 or m["loc_delta"] != 0 for m in diff["module_changes"])
        kc = diff["kalshi_changes"]
        has_kalshi = (kc.get("pnl_delta") is not None and kc.get("pnl_delta", 0) != 0) or kc.get("became_available", False)
        lc = diff["learning_changes"]
        has_learning = lc.get("apf_delta") is not None and lc.get("apf_delta", 0) != 0

        if not has_summary and not has_mt and not has_modules and not has_kalshi and not has_learning:
            lines.append("No changes detected.")
            return "\n".join(lines)

        # Summary deltas
        lines.append("Summary:")
        for field in ["total_tests", "total_loc", "git_commits", "total_delivered"]:
            d = sc[field]
            if d["delta"] != 0:
                sign = "+" if d["delta"] > 0 else ""
                lines.append(f"  {field}: {d['old']} -> {d['new']} ({sign}{d['delta']})")

        # Module changes (only non-zero)
        mod_changes = [m for m in diff["module_changes"] if m["tests_delta"] != 0 or m["loc_delta"] != 0]
        if mod_changes:
            lines.append("")
            lines.append("Module Changes:")
            for m in mod_changes:
                parts = []
                if m["tests_delta"] != 0:
                    sign = "+" if m["tests_delta"] > 0 else ""
                    parts.append(f"tests {sign}{m['tests_delta']}")
                if m["loc_delta"] != 0:
                    sign = "+" if m["loc_delta"] > 0 else ""
                    parts.append(f"LOC {sign}{m['loc_delta']}")
                prefix = "[NEW] " if m["is_new"] else ""
                lines.append(f"  {prefix}{m['name']}: {', '.join(parts)}")

        # MT transitions
        if mt_c["newly_completed"]:
            lines.append("")
            lines.append("Newly Completed MTs:")
            for mt in mt_c["newly_completed"]:
                lines.append(f"  {mt['id']}: {mt['name']}")

        if mt_c["newly_active"]:
            lines.append("")
            lines.append("Newly Active MTs:")
            for mt in mt_c["newly_active"]:
                lines.append(f"  {mt['id']}: {mt['name']}")

        # Kalshi
        if kc.get("pnl_delta") is not None:
            lines.append("")
            sign = "+" if kc["pnl_delta"] > 0 else ""
            lines.append(f"Kalshi P&L: {sign}${kc['pnl_delta']:.2f}, Win Rate: {sign}{kc['win_rate_delta']:.1f}pp")
        elif kc.get("became_available"):
            lines.append("")
            lines.append("Kalshi: newly available (no prior data to compare)")

        # Learning
        if lc.get("apf_delta") is not None:
            lines.append("")
            sign = "+" if lc["apf_delta"] > 0 else ""
            lines.append(f"APF: {sign}{lc['apf_delta']:.1f}, Journal: +{lc['journal_delta']} entries")

        return "\n".join(lines)
