#!/usr/bin/env python3
"""
meta_tracker.py — MT-49 Phase 1: Meta-Learning Effectiveness Tracker

Tracks whether the self-learning system is actually learning. Measures principle
usage rates, identifies zombie principles (created but never validated), and
produces a health score for the meta-learning loop.

The core insight: 93% of principles (168/181) have never been used or scored.
The self-learning system generates principles but doesn't validate them against
real outcomes. This module closes that gap by measuring and reporting on the
learning loop's actual effectiveness.

Usage:
    python3 self-learning/meta_tracker.py health --session 223
    python3 self-learning/meta_tracker.py zombies --session 223
    python3 self-learning/meta_tracker.py snapshot --session 223
    python3 self-learning/meta_tracker.py trend
    python3 self-learning/meta_tracker.py init-briefing --session 223
"""

import json
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRINCIPLES_PATH = os.path.join(SCRIPT_DIR, "principles.jsonl")
SNAPSHOTS_PATH = os.path.join(SCRIPT_DIR, "meta_snapshots.jsonl")

# A principle is a "zombie" if it has 0 usage and was created 30+ sessions ago
ZOMBIE_SESSION_THRESHOLD = 30


def _load_principles(path):
    """Load principles from JSONL, latest version wins."""
    principles = {}
    if not os.path.exists(path):
        return principles
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                pid = data.get("id", "")
                if pid and not data.get("pruned", False):
                    principles[pid] = data
            except (json.JSONDecodeError, TypeError):
                continue
    return principles


def _load_snapshots(path):
    """Load meta snapshots from JSONL."""
    snapshots = []
    if not os.path.exists(path):
        return snapshots
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                snapshots.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return snapshots


class MetaTracker:
    """Tracks self-learning system effectiveness."""

    def __init__(self, principles_path=None, snapshots_path=None):
        self.principles_path = principles_path or PRINCIPLES_PATH
        self.snapshots_path = snapshots_path or SNAPSHOTS_PATH

    def _principles(self):
        return _load_principles(self.principles_path)

    def health(self, current_session=0):
        """Compute meta-learning health metrics."""
        principles = self._principles()
        total = len(principles)
        if total == 0:
            return {
                "total": 0, "active": 0, "zombies": 0, "reinforced": 0,
                "usage_rate": 0.0, "avg_score": 0.0, "health_score": 0.5,
                "domains": {},
            }

        active = 0
        zombies = 0
        reinforced = 0
        scores = []
        domain_counts = {}

        for p in principles.values():
            usage = p.get("usage_count", 0)
            success = p.get("success_count", 0)
            created = p.get("created_session", 0)
            domain = p.get("source_domain", "general")

            # Laplace score
            score = (success + 1) / (usage + 2)
            scores.append(score)

            # Domain tracking
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

            if usage > 0:
                active += 1
                if score >= 0.7 and usage >= 5:
                    reinforced += 1
            elif current_session - created >= ZOMBIE_SESSION_THRESHOLD:
                zombies += 1

        usage_rate = active / total if total > 0 else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Health score: weighted combination
        # 40% usage rate (are principles being used?)
        # 30% non-zombie rate (is the registry clean?)
        # 30% average score (are used principles effective?)
        non_zombie_rate = 1.0 - (zombies / total) if total > 0 else 1.0
        health_score = (0.4 * usage_rate) + (0.3 * non_zombie_rate) + (0.3 * avg_score)
        health_score = round(min(1.0, max(0.0, health_score)), 3)

        return {
            "total": total,
            "active": active,
            "zombies": zombies,
            "reinforced": reinforced,
            "usage_rate": round(usage_rate, 3),
            "avg_score": round(avg_score, 3),
            "health_score": health_score,
            "domains": domain_counts,
        }

    def list_zombies(self, current_session=0, limit=20):
        """List zombie principles (unused for 30+ sessions after creation)."""
        principles = self._principles()
        zombies = []
        for p in principles.values():
            usage = p.get("usage_count", 0)
            created = p.get("created_session", 0)
            if usage == 0 and current_session - created >= ZOMBIE_SESSION_THRESHOLD:
                zombies.append({
                    "id": p["id"],
                    "text": p.get("text", ""),
                    "domain": p.get("source_domain", "general"),
                    "created_session": created,
                    "sessions_stale": current_session - created,
                })
        # Sort by staleness (oldest first)
        zombies.sort(key=lambda z: z["sessions_stale"], reverse=True)
        return zombies[:limit]

    def snapshot(self, session=0):
        """Record a point-in-time snapshot of meta-learning health."""
        health = self.health(current_session=session)
        snap = {
            "session": session,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **health,
        }
        with open(self.snapshots_path, "a") as f:
            f.write(json.dumps(snap) + "\n")
        return snap

    def trend(self, last_n=5):
        """Analyze health score trend over recent snapshots."""
        snapshots = _load_snapshots(self.snapshots_path)
        if len(snapshots) < 2:
            return {"status": "insufficient_data", "snapshots": len(snapshots)}

        recent = snapshots[-last_n:]
        scores = [s.get("health_score", 0) for s in recent]

        if len(scores) < 2:
            return {"status": "insufficient_data", "snapshots": len(scores)}

        # Simple trend: compare first half avg to second half avg
        mid = len(scores) // 2
        first_half = sum(scores[:mid]) / mid
        second_half = sum(scores[mid:]) / (len(scores) - mid)

        delta = second_half - first_half
        if delta > 0.05:
            status = "improving"
        elif delta < -0.05:
            status = "declining"
        else:
            status = "stable"

        return {
            "status": status,
            "delta": round(delta, 3),
            "latest": round(scores[-1], 3),
            "snapshots": len(recent),
        }

    def init_briefing(self, current_session=0):
        """Produce a one-line briefing for /cca-init."""
        health = self.health(current_session=current_session)
        trend = self.trend()

        parts = [
            f"Meta-learning: {health['active']}/{health['total']} active",
            f"{health['zombies']} zombies",
            f"health={health['health_score']:.2f}",
        ]
        if health["reinforced"] > 0:
            parts.append(f"{health['reinforced']} reinforced")
        if trend["status"] != "insufficient_data":
            parts.append(f"trend={trend['status']}")

        return " | ".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Meta-learning effectiveness tracker")
    parser.add_argument("--principles-path", default=PRINCIPLES_PATH)
    parser.add_argument("--snapshots-path", default=SNAPSHOTS_PATH)

    parser.add_argument("--session", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("health", help="Show meta-learning health")
    sub.add_parser("zombies", help="List zombie principles")
    sub.add_parser("snapshot", help="Record health snapshot")
    sub.add_parser("trend", help="Show health trend")
    sub.add_parser("init-briefing", help="One-line briefing")

    args = parser.parse_args()
    mt = MetaTracker(args.principles_path, args.snapshots_path)

    if args.command == "health":
        health = mt.health(current_session=args.session)
        print(f"Meta-Learning Health (Session {args.session}):")
        print(f"  Total principles: {health['total']}")
        print(f"  Active (used >= 1): {health['active']}")
        print(f"  Zombies (unused {ZOMBIE_SESSION_THRESHOLD}+ sessions): {health['zombies']}")
        print(f"  Reinforced (score >= 0.7, usage >= 5): {health['reinforced']}")
        print(f"  Usage rate: {health['usage_rate']:.1%}")
        print(f"  Avg score: {health['avg_score']:.3f}")
        print(f"  Health score: {health['health_score']:.3f}")
        print(f"  Domains: {health['domains']}")

    elif args.command == "zombies":
        zombies = mt.list_zombies(current_session=args.session, limit=args.limit)
        print(f"Zombie Principles ({len(zombies)} found, session {args.session}):")
        for z in zombies:
            print(f"  [{z['sessions_stale']}s stale] {z['id']} ({z['domain']})")
            print(f"    {z['text'][:80]}")

    elif args.command == "snapshot":
        snap = mt.snapshot(session=args.session)
        print(f"Snapshot recorded: health={snap['health_score']:.3f}, "
              f"active={snap['active']}/{snap['total']}, zombies={snap['zombies']}")

    elif args.command == "trend":
        trend = mt.trend()
        if trend["status"] == "insufficient_data":
            print(f"Trend: insufficient data ({trend['snapshots']} snapshots)")
        else:
            print(f"Trend: {trend['status']} (delta={trend['delta']:+.3f}, "
                  f"latest={trend['latest']:.3f}, snapshots={trend['snapshots']})")

    elif args.command == "init-briefing":
        print(mt.init_briefing(current_session=args.session))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
