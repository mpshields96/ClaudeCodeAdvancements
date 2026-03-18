#!/usr/bin/env python3
"""improver.py — MT-10: YoYo self-learning improvement loop.

Generates structured improvement proposals from detected patterns
(trace analysis + reflect patterns), classifies risk, tracks lifecycle,
and provides the data layer for the Observe → Detect → Hypothesize →
Build → Validate → Commit loop.

This module is the "Hypothesize" brain. Claude Code is the "Build" hands.

Usage:
    python3 self-learning/improver.py stats              # Show improvement stats
    python3 self-learning/improver.py pending             # Show pending proposals
    python3 self-learning/improver.py actionable          # Show approved, ready to build
    python3 self-learning/improver.py generate <trace.jsonl>  # Generate proposals from trace
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STORE_PATH = os.path.join(SCRIPT_DIR, "improvements.jsonl")

VALID_RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
VALID_STATUSES = ("proposed", "approved", "building", "validated", "committed", "rejected", "superseded")
VALID_SOURCES = ("trace_analysis", "reflect_pattern", "manual", "sentinel_mutation", "sentinel_cross_pollination")

# Files that should never be targeted by improvement proposals
PROTECTED_FILES = {"CLAUDE.md", ".env", ".env.local", "settings.local.json", "credentials.json"}
PROTECTED_PATTERNS = {".env", "credential", "secret", "token", "apikey", "api_key"}


def _make_id():
    """Generate a unique improvement proposal ID."""
    import secrets
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(4)  # 8 hex chars
    return f"imp_{ts}_{suffix}"


def _is_protected_file(filepath):
    """Check if a file path is protected from modification."""
    if not filepath:
        return False
    name = Path(filepath).name
    if name in PROTECTED_FILES:
        return True
    name_lower = name.lower()
    return any(p in name_lower for p in PROTECTED_PATTERNS)


def classify_risk(target_file=None, target_module="self-learning", modifies_hook=False):
    """Classify the risk level of a proposed improvement.

    LOW: new utility file (no existing code modified)
    MEDIUM: new hook, or modifying existing non-hook code
    HIGH: modifying existing hook, or anything trading-related
    """
    # Trading is always HIGH — never auto-adjust
    if target_module == "trading":
        return "HIGH"

    # Modifying an existing hook file
    if target_file and modifies_hook:
        return "HIGH"

    # New hook (no existing file, but it's a hook)
    if modifies_hook:
        return "MEDIUM"

    # Modifying existing non-hook code
    if target_file:
        return "MEDIUM"

    # New utility file
    return "LOW"


# ---------------------------------------------------------------------------
# QualityGate — geometric mean anti-gaming (sentrux / Nash 1950 pattern)
# ---------------------------------------------------------------------------

class QualityGate:
    """Multi-metric quality gate using geometric mean scoring.

    Prevents Goodhart's Law gaming in self-improvement loops: you can't
    sacrifice one metric to boost another, because a zero (or low value)
    in any dimension tanks the composite score.

    All metrics are normalized to [0.0, 1.0]. The geometric mean of N
    metrics is (m1 * m2 * ... * mN) ^ (1/N). Requires at least 2 metrics
    to prevent single-metric gaming.
    """

    def __init__(self, threshold=0.5):
        self.threshold = threshold

    def evaluate(self, metrics):
        """Evaluate metrics against the quality gate.

        Args:
            metrics: dict of {metric_name: float} where values are 0.0-1.0

        Returns:
            dict with: passed, geometric_mean, metrics, threshold, weakest_metric
        """
        if len(metrics) < 2:
            return {
                "passed": False,
                "geometric_mean": 0.0,
                "metrics": dict(metrics),
                "threshold": self.threshold,
                "weakest_metric": None,
                "error": "Quality gate requires at least 2 metrics",
            }

        # Clamp values to [0.0, 1.0]
        clamped = {}
        for k, v in metrics.items():
            clamped[k] = max(0.0, min(1.0, v))

        # Geometric mean: (product)^(1/n)
        product = 1.0
        for v in clamped.values():
            product *= v
        geo_mean = product ** (1.0 / len(clamped))

        # Identify weakest metric
        weakest = min(clamped, key=clamped.get)

        return {
            "passed": geo_mean >= self.threshold,
            "geometric_mean": geo_mean,
            "metrics": clamped,
            "threshold": self.threshold,
            "weakest_metric": weakest,
        }


# ---------------------------------------------------------------------------
# ImprovementProposal
# ---------------------------------------------------------------------------

class ImprovementProposal:
    """A structured improvement proposal."""

    def __init__(self, pattern_type, pattern_data, source, proposed_fix,
                 expected_improvement, test_plan, risk_level, target_module,
                 target_file=None, session_id=None):
        if risk_level not in VALID_RISK_LEVELS:
            raise ValueError(f"Invalid risk_level: {risk_level}. Must be one of {VALID_RISK_LEVELS}")
        if source not in VALID_SOURCES:
            raise ValueError(f"Invalid source: {source}. Must be one of {VALID_SOURCES}")

        self.id = _make_id()
        self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.status = "proposed"
        self.pattern_type = pattern_type
        self.pattern_data = pattern_data
        self.source = source
        self.proposed_fix = proposed_fix
        self.expected_improvement = expected_improvement
        self.test_plan = test_plan
        self.risk_level = risk_level
        self.target_module = target_module
        self.target_file = target_file
        self.outcome = None
        self.session_id = session_id

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "status": self.status,
            "pattern_type": self.pattern_type,
            "pattern_data": self.pattern_data,
            "source": self.source,
            "proposed_fix": self.proposed_fix,
            "expected_improvement": self.expected_improvement,
            "test_plan": self.test_plan,
            "risk_level": self.risk_level,
            "target_module": self.target_module,
            "target_file": self.target_file,
            "outcome": self.outcome,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, d):
        p = cls.__new__(cls)
        p.id = d["id"]
        p.timestamp = d["timestamp"]
        p.status = d.get("status", "proposed")
        p.pattern_type = d["pattern_type"]
        p.pattern_data = d.get("pattern_data", {})
        p.source = d.get("source", "manual")
        p.proposed_fix = d["proposed_fix"]
        p.expected_improvement = d.get("expected_improvement", "")
        p.test_plan = d.get("test_plan", "")
        p.risk_level = d.get("risk_level", "LOW")
        p.target_module = d.get("target_module", "self-learning")
        p.target_file = d.get("target_file")
        p.outcome = d.get("outcome")
        p.session_id = d.get("session_id")
        return p


# ---------------------------------------------------------------------------
# ImprovementStore
# ---------------------------------------------------------------------------

class ImprovementStore:
    """JSONL persistence for improvement proposals."""

    def __init__(self, path=None):
        self._path = path or DEFAULT_STORE_PATH

    def load_all(self):
        if not os.path.exists(self._path):
            return []
        proposals = []
        with open(self._path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    proposals.append(ImprovementProposal.from_dict(d))
                except (json.JSONDecodeError, KeyError):
                    continue
        return proposals

    def append(self, proposal):
        with open(self._path, "a") as f:
            f.write(json.dumps(proposal.to_dict(), separators=(",", ":")) + "\n")

    def _rewrite(self, proposals):
        """Rewrite the entire store (for updates). Atomic via tmp+rename."""
        tmp = self._path + ".tmp"
        with open(tmp, "w") as f:
            for p in proposals:
                f.write(json.dumps(p.to_dict(), separators=(",", ":")) + "\n")
        os.replace(tmp, self._path)

    def update_status(self, proposal_id, new_status):
        proposals = self.load_all()
        changed = False
        for p in proposals:
            if p.id == proposal_id:
                p.status = new_status
                changed = True
                break
        if changed:
            self._rewrite(proposals)

    def update_outcome(self, proposal_id, outcome):
        proposals = self.load_all()
        changed = False
        for p in proposals:
            if p.id == proposal_id:
                p.outcome = outcome
                changed = True
                break
        if changed:
            self._rewrite(proposals)

    def get_pending(self):
        return [p for p in self.load_all() if p.status == "proposed"]

    def get_by_status(self, status):
        return [p for p in self.load_all() if p.status == status]


# ---------------------------------------------------------------------------
# ProposalGenerator
# ---------------------------------------------------------------------------

class ProposalGenerator:
    """Generate improvement proposals from trace reports and reflect patterns."""

    @staticmethod
    def from_trace_report(trace_report, session_id=None):
        """Generate proposals from a TraceAnalyzer report."""
        proposals = []
        seen_files = set()  # Dedup retries on same file

        # Retry loops → proposals
        for r in trace_report.get("retries", {}).get("retries", []):
            fp = r.get("file", "unknown")
            if _is_protected_file(fp):
                continue
            if fp in seen_files:
                continue
            seen_files.add(fp)

            severity = r.get("severity", "minor")
            count = r.get("count", 0)
            risk = classify_risk(target_file=None, target_module="self-learning", modifies_hook=False)

            proposals.append(ImprovementProposal(
                pattern_type="retry_loop",
                pattern_data={"file": fp, "tool": r.get("tool"), "count": count, "severity": severity},
                source="trace_analysis",
                proposed_fix=f"Add pre-read guard before Edit on {fp} — read file state before retrying",
                expected_improvement=f"Reduce retry loops on {fp} (currently {count} consecutive calls)",
                test_plan="Run trace_analyzer on next 3 sessions, compare retry count for this file",
                risk_level=risk,
                target_module="self-learning",
                session_id=session_id,
            ))

        # High waste → proposal
        waste = trace_report.get("waste", {})
        waste_rate = waste.get("waste_rate", 0)
        if waste_rate > 0.3:
            wasted = waste.get("wasted_reads", [])
            proposals.append(ImprovementProposal(
                pattern_type="high_waste",
                pattern_data={"waste_rate": waste_rate, "wasted_count": len(wasted)},
                source="trace_analysis",
                proposed_fix="Track file references to avoid speculative reads — only read files you will use",
                expected_improvement=f"Reduce read waste from {waste_rate:.0%} to under 20%",
                test_plan="Compare waste_rate across 3 sessions after applying fix",
                risk_level="LOW",
                target_module="self-learning",
                session_id=session_id,
            ))

        # Low efficiency → proposal
        eff = trace_report.get("efficiency", {})
        if eff.get("rating") == "poor":
            proposals.append(ImprovementProposal(
                pattern_type="low_efficiency",
                pattern_data={"ratio": eff.get("ratio"), "unique_files": eff.get("unique_files"), "total_calls": eff.get("total_calls")},
                source="trace_analysis",
                proposed_fix="Reduce redundant tool calls on same files — batch operations where possible",
                expected_improvement=f"Improve tool efficiency ratio from {eff.get('ratio')} to >0.1",
                test_plan="Compare efficiency ratio across 3 sessions",
                risk_level="LOW",
                target_module="self-learning",
                session_id=session_id,
            ))

        # No deliverables → proposal
        vel = trace_report.get("velocity", {})
        if vel.get("total_calls", 0) > 10 and vel.get("deliverables", 0) == 0:
            proposals.append(ImprovementProposal(
                pattern_type="no_deliverables",
                pattern_data={"total_calls": vel.get("total_calls")},
                source="trace_analysis",
                proposed_fix="Commit progress incrementally — don't accumulate large uncommitted changes",
                expected_improvement="At least 1 commit per 30 tool calls",
                test_plan="Check velocity_pct > 0 in trace analysis for next 3 sessions",
                risk_level="LOW",
                target_module="self-learning",
                session_id=session_id,
            ))

        return proposals

    @staticmethod
    def from_reflect_patterns(patterns, session_id=None):
        """Generate proposals from reflect.py pattern detection results."""
        proposals = []

        for p in patterns:
            ptype = p.get("type", "unknown")
            data = p.get("data", {})

            if ptype == "high_skip_rate":
                proposals.append(ImprovementProposal(
                    pattern_type="high_skip_rate",
                    pattern_data=data,
                    source="reflect_pattern",
                    proposed_fix=f"Raise min_score_threshold to filter more noise (suggestion: {p.get('suggestion', {})})",
                    expected_improvement=f"Reduce skip rate from {data.get('skip_rate', 0):.0%}",
                    test_plan="Compare skip rate before/after threshold change",
                    risk_level="LOW",
                    target_module="self-learning",
                    session_id=session_id,
                ))

            elif ptype == "low_build_rate":
                proposals.append(ImprovementProposal(
                    pattern_type="low_build_rate",
                    pattern_data=data,
                    source="reflect_pattern",
                    proposed_fix="Refine high_value_keywords or scan different subreddits",
                    expected_improvement=f"Improve BUILD rate from {data.get('build_rate', 0):.1%}",
                    test_plan="Compare build_rate after keyword/subreddit adjustment",
                    risk_level="LOW",
                    target_module="reddit-intelligence",
                    session_id=session_id,
                ))

            elif ptype == "losing_strategy":
                proposals.append(ImprovementProposal(
                    pattern_type="losing_strategy",
                    pattern_data=data,
                    source="reflect_pattern",
                    proposed_fix=f"Review or retire strategy '{data.get('strategy', 'unknown')}' — {data.get('win_rate', 0):.0%} win rate, {data.get('pnl_cents', 0)}c PnL",
                    expected_improvement="Eliminate losing strategy or tune parameters",
                    test_plan=f"Track PnL for next {data.get('bets', 20)} bets after adjustment",
                    risk_level="HIGH",  # Trading = always HIGH
                    target_module="trading",
                    session_id=session_id,
                ))

            elif ptype == "research_dead_end":
                proposals.append(ImprovementProposal(
                    pattern_type="research_dead_end",
                    pattern_data=data,
                    source="reflect_pattern",
                    proposed_fix=f"Prune research path '{data.get('path', 'unknown')}' — 0 actionable results in {data.get('sessions', 0)} sessions",
                    expected_improvement="Free research bandwidth for higher-yield paths",
                    test_plan="Track actionable rate after pruning",
                    risk_level="HIGH",  # Trading = always HIGH
                    target_module="trading",
                    session_id=session_id,
                ))

            elif ptype == "negative_pnl":
                proposals.append(ImprovementProposal(
                    pattern_type="negative_pnl",
                    pattern_data=data,
                    source="reflect_pattern",
                    proposed_fix=f"Cumulative PnL is {data.get('pnl_cents', 0)}c — review all active strategies",
                    expected_improvement="Return to positive cumulative PnL",
                    test_plan="Track cumulative PnL weekly",
                    risk_level="HIGH",
                    target_module="trading",
                    session_id=session_id,
                ))

            elif ptype == "stale_strategy":
                proposals.append(ImprovementProposal(
                    pattern_type="stale_strategy",
                    pattern_data=data,
                    source="reflect_pattern",
                    proposed_fix=f"Run reflect --apply to update strategy.json ({data.get('days_old', 0)} days old)",
                    expected_improvement="Strategy parameters aligned with recent patterns",
                    test_plan="Verify strategy.json version bumped after apply",
                    risk_level="LOW",
                    target_module="self-learning",
                    session_id=session_id,
                ))

            elif ptype == "consecutive_failures":
                proposals.append(ImprovementProposal(
                    pattern_type="consecutive_failures",
                    pattern_data=data,
                    source="reflect_pattern",
                    proposed_fix="Investigate root cause of consecutive session failures",
                    expected_improvement="Break failure streak",
                    test_plan="Next 3 sessions achieve success outcome",
                    risk_level="MEDIUM",
                    target_module="self-learning",
                    session_id=session_id,
                ))

            elif ptype == "high_pain_rate":
                proposals.append(ImprovementProposal(
                    pattern_type="high_pain_rate",
                    pattern_data=data,
                    source="reflect_pattern",
                    proposed_fix=f"Investigate top pain domain: {data.get('top_pain_domain', 'unknown')}",
                    expected_improvement="Increase win/pain ratio above 50%",
                    test_plan="Track pain/win ratio over next 5 sessions",
                    risk_level="MEDIUM",
                    target_module="self-learning",
                    session_id=session_id,
                ))

        return proposals


# ---------------------------------------------------------------------------
# SentinelMutator — adaptive mutation engine (X-Men Sentinel pattern)
# ---------------------------------------------------------------------------

# Domains that the Sentinel can reason about
SENTINEL_DOMAINS = (
    "self-learning", "reddit-intelligence", "context-monitor",
    "agent-guard", "usage-dashboard", "memory-system", "spec-system",
)

# Mutation strategies per pattern type — each is an alternative approach
MUTATION_STRATEGIES = {
    "retry_loop": [
        "Cache file state in memory before tool calls to avoid redundant reads",
        "Split large edits into smaller atomic changes to reduce retry likelihood",
        "Add file content hash check — skip Edit if content already matches target",
    ],
    "high_waste": [
        "Use Glob to verify file existence before reading — avoid 404-style waste",
        "Batch related file reads into a single discovery pass",
        "Track accessed files in session state — skip files already in context",
    ],
    "low_efficiency": [
        "Cache tool results for identical inputs within a sliding window",
        "Batch sequential Grep calls into one regex with alternation",
        "Pre-compute file dependency graph to minimize redundant traversals",
    ],
    "no_deliverables": [
        "Set a 15-tool-call checkpoint — if no commit, review progress and plan",
        "Use TodoWrite at start of task to enforce commit-per-todo discipline",
        "Break work into smaller increments with explicit success criteria",
    ],
    "high_skip_rate": [
        "Add title-length filter — very short titles are usually low-signal",
        "Weight score by subreddit baseline — a 50pt post in r/ClaudeCode is noise, in niche subs it's signal",
        "Use comment_count/score ratio to detect engagement quality",
    ],
    "low_build_rate": [
        "Expand keyword set to catch adjacent terminology (e.g. 'hook' → 'plugin', 'extension', 'middleware')",
        "Add code-presence detection — posts with GitHub links are more likely BUILD",
        "Scan nested comments for tool mentions — top-level text may be vague but comments reveal specifics",
    ],
}

MAX_MUTATION_DEPTH = 2      # Conservative: shallow mutation chains only (was 3)
MAX_MUTATIONS_PER_CYCLE = 2  # Conservative: 5-10% effect ceiling (was 5)


class SentinelMutator:
    """Adaptive mutation engine for the self-learning improvement loop.

    Like the X-Men Sentinels, this system:
    1. Analyzes failures and generates counter-strategies (mutations)
    2. Cross-pollinates successful patterns across domains
    3. Proactively scans for weak spots with no coverage
    """

    def mutate_from_failure(self, rejected_proposal):
        """Generate mutated counter-strategies from a rejected proposal.

        Args:
            rejected_proposal: An ImprovementProposal with status='rejected'

        Returns:
            List of new ImprovementProposal objects (mutations)
        """
        if rejected_proposal.status != "rejected":
            return []

        # Check mutation depth — don't recurse forever
        depth = rejected_proposal.pattern_data.get("mutation_depth", 0)
        if depth >= MAX_MUTATION_DEPTH:
            return []

        # Protected files block mutations
        target_file = rejected_proposal.pattern_data.get("file", "")
        if _is_protected_file(target_file):
            return []

        # Find alternative strategies for this pattern type
        base_type = rejected_proposal.pattern_type.replace("_mutation", "")
        strategies = MUTATION_STRATEGIES.get(base_type, [])

        # Filter out the original fix (we know it didn't work)
        original_fix = rejected_proposal.proposed_fix
        alternatives = [s for s in strategies if s != original_fix]

        if not alternatives:
            # Generic fallback: try the inverse approach
            alternatives = [f"Inverse approach for {base_type}: instead of preventing, detect and recover"]

        # Pick the first unused alternative
        mutation = ImprovementProposal(
            pattern_type=f"{base_type}_mutation",
            pattern_data={
                **rejected_proposal.pattern_data,
                "mutation_of": rejected_proposal.id,
                "mutation_depth": depth + 1,
                "original_fix_that_failed": original_fix,
            },
            source="sentinel_mutation",
            proposed_fix=alternatives[0],
            expected_improvement=rejected_proposal.expected_improvement,
            test_plan=rejected_proposal.test_plan,
            risk_level=rejected_proposal.risk_level,  # At least as risky
            target_module=rejected_proposal.target_module,
            target_file=rejected_proposal.target_file,
        )
        return [mutation]

    def cross_pollinate(self, proposals):
        """Apply successful patterns from one domain to others.

        Args:
            proposals: List of ImprovementProposal objects

        Returns:
            List of new cross-domain ImprovementProposal objects
        """
        successful = [
            p for p in proposals
            if p.status in ("validated", "committed")
            and p.target_module != "trading"  # Never cross-pollinate trading
        ]

        if not successful:
            return []

        new_proposals = []
        seen_domains = set()

        for p in successful:
            # Determine which other domains could benefit
            source_domain = p.target_module
            for target_domain in SENTINEL_DOMAINS:
                if target_domain == source_domain:
                    continue
                if target_domain in seen_domains:
                    continue

                # Adapt the fix for the new domain
                adapted_fix = f"[Cross-pollinated from {source_domain}] {p.proposed_fix}"

                cross = ImprovementProposal(
                    pattern_type=p.pattern_type,
                    pattern_data={
                        "cross_from": p.id,
                        "origin_module": source_domain,
                        "original_fix": p.proposed_fix,
                    },
                    source="sentinel_cross_pollination",
                    proposed_fix=adapted_fix,
                    expected_improvement=f"Apply proven pattern from {source_domain} to {target_domain}",
                    test_plan=f"Run same validation as {p.id} but in {target_domain} context",
                    risk_level="LOW",  # Cross-pollination is exploratory
                    target_module=target_domain,
                )
                new_proposals.append(cross)
                seen_domains.add(target_domain)
                break  # One cross per successful proposal

        return new_proposals

    def scan_weaknesses(self, proposals):
        """Proactively identify domains with no coverage or high failure rates.

        Args:
            proposals: List of all ImprovementProposal objects

        Returns:
            List of gap reports: [{"domain": str, "reason": str}, ...]
        """
        # Count proposals per domain
        domain_stats = {}
        for d in SENTINEL_DOMAINS:
            domain_stats[d] = {"total": 0, "rejected": 0, "active": 0}

        for p in proposals:
            module = p.target_module
            if module not in domain_stats:
                continue
            domain_stats[module]["total"] += 1
            if p.status == "rejected":
                domain_stats[module]["rejected"] += 1
            elif p.status in ("proposed", "approved", "building"):
                domain_stats[module]["active"] += 1

        gaps = []
        for domain, stats in domain_stats.items():
            if stats["total"] == 0:
                gaps.append({
                    "domain": domain,
                    "reason": "No improvement proposals exist — unexplored territory",
                })
            elif stats["active"] == 0 and stats["rejected"] > 0:
                gaps.append({
                    "domain": domain,
                    "reason": f"All {stats['rejected']} proposals rejected — needs new approach",
                })
            elif stats["total"] >= 3 and stats["rejected"] / stats["total"] > 0.66:
                gaps.append({
                    "domain": domain,
                    "reason": f"High rejection rate ({stats['rejected']}/{stats['total']}) — strategies not working",
                })

        return gaps


# ---------------------------------------------------------------------------
# Improver — orchestrator
# ---------------------------------------------------------------------------

class Improver:
    """Orchestrate the improvement proposal lifecycle.

    The YoYo loop:
    1. Observe: trace_analyzer.py + reflect.py detect patterns
    2. Hypothesize: this module generates proposals
    3. Build: Claude Code reads proposals and implements fixes
    4. Validate: trace_analyzer re-runs, outcome recorded
    5. Commit/Reject: based on whether metrics improved
    """

    def __init__(self, store_path=None, max_proposals_per_session=5, auto_approve_low=False):
        self.store = ImprovementStore(store_path)
        self.max_proposals_per_session = max_proposals_per_session
        self.auto_approve_low = auto_approve_low
        self.sentinel = SentinelMutator()

    def _dedup_proposals(self, new_proposals):
        """Remove proposals that duplicate existing active ones."""
        existing = self.store.load_all()
        active_keys = set()
        for p in existing:
            if p.status not in ("rejected", "superseded", "committed"):
                key = (p.pattern_type, json.dumps(p.pattern_data.get("file", ""), sort_keys=True))
                active_keys.add(key)

        deduped = []
        for p in new_proposals:
            key = (p.pattern_type, json.dumps(p.pattern_data.get("file", ""), sort_keys=True))
            if key not in active_keys:
                deduped.append(p)
                active_keys.add(key)
        return deduped

    def generate_from_trace(self, trace_report, session_id=None):
        """Generate proposals from a trace analysis report."""
        raw = ProposalGenerator.from_trace_report(trace_report, session_id=session_id)
        proposals = self._dedup_proposals(raw)
        proposals = proposals[:self.max_proposals_per_session]

        if self.auto_approve_low:
            for p in proposals:
                if p.risk_level == "LOW":
                    p.status = "approved"

        for p in proposals:
            self.store.append(p)
        return proposals

    def generate_from_reflect(self, patterns, session_id=None):
        """Generate proposals from reflect.py pattern detection."""
        raw = ProposalGenerator.from_reflect_patterns(patterns, session_id=session_id)
        proposals = self._dedup_proposals(raw)
        proposals = proposals[:self.max_proposals_per_session]

        if self.auto_approve_low:
            for p in proposals:
                if p.risk_level == "LOW":
                    p.status = "approved"

        for p in proposals:
            self.store.append(p)
        return proposals

    def get_actionable(self):
        """Get proposals that are approved and ready to build."""
        return self.store.get_by_status("approved")

    def record_outcome(self, proposal_id, improved, metric_before=None, metric_after=None):
        """Record the outcome of an attempted improvement."""
        outcome = {
            "improved": improved,
            "metric_before": metric_before,
            "metric_after": metric_after,
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.store.update_outcome(proposal_id, outcome)
        new_status = "validated" if improved else "rejected"
        self.store.update_status(proposal_id, new_status)

    def evolve(self):
        """Run the Sentinel adaptation cycle.

        1. Mutate rejected proposals into counter-strategies
        2. Cross-pollinate successful patterns across domains
        3. Scan for weak spots with no coverage

        Returns dict with counts: {mutations, cross_pollinations, weakness_gaps}
        """
        all_proposals = self.store.load_all()

        # 1. Mutate from failures
        rejected = [p for p in all_proposals if p.status == "rejected"]
        mutations = []
        for r in rejected:
            new_mutations = self.sentinel.mutate_from_failure(r)
            mutations.extend(new_mutations)
            if len(mutations) >= MAX_MUTATIONS_PER_CYCLE:
                break
        mutations = mutations[:MAX_MUTATIONS_PER_CYCLE]

        # Dedup against existing proposals
        mutations = self._dedup_proposals(mutations)

        # 2. Cross-pollinate successes
        cross = self.sentinel.cross_pollinate(all_proposals)
        cross = self._dedup_proposals(cross)

        # 3. Scan weaknesses
        gaps = self.sentinel.scan_weaknesses(all_proposals)

        # Persist new proposals
        for m in mutations:
            self.store.append(m)
        for c in cross:
            self.store.append(c)

        return {
            "mutations": len(mutations),
            "cross_pollinations": len(cross),
            "weakness_gaps": len(gaps),
            "gap_details": gaps,
        }

    def get_stats(self):
        """Get improvement system statistics."""
        all_proposals = self.store.load_all()
        by_status = {}
        for p in all_proposals:
            by_status[p.status] = by_status.get(p.status, 0) + 1

        committed = by_status.get("committed", 0) + by_status.get("validated", 0)
        rejected = by_status.get("rejected", 0)
        decided = committed + rejected

        return {
            "total": len(all_proposals),
            "by_status": by_status,
            "by_risk": {
                level: sum(1 for p in all_proposals if p.risk_level == level)
                for level in VALID_RISK_LEVELS
            },
            "by_source": {
                source: sum(1 for p in all_proposals if p.source == source)
                for source in VALID_SOURCES
            },
            "success_rate": committed / decided if decided > 0 else None,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    import argparse
    parser = argparse.ArgumentParser(description="CCA Improvement Proposals (MT-10)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("stats", help="Show improvement stats")
    sub.add_parser("pending", help="Show pending proposals")
    sub.add_parser("actionable", help="Show approved proposals ready to build")
    sub.add_parser("all", help="Show all proposals")

    gen_p = sub.add_parser("generate", help="Generate proposals from trace report")
    gen_p.add_argument("trace_path", help="Path to trace report JSON or transcript JSONL")
    gen_p.add_argument("--session", type=int, help="Session ID")
    gen_p.add_argument("--auto-approve", action="store_true", help="Auto-approve LOW risk")

    approve_p = sub.add_parser("approve", help="Approve a proposal")
    approve_p.add_argument("proposal_id", help="Proposal ID to approve")

    sub.add_parser("evolve", help="Run Sentinel adaptive mutation cycle")

    outcome_p = sub.add_parser("outcome", help="Record an outcome")
    outcome_p.add_argument("proposal_id", help="Proposal ID")
    outcome_p.add_argument("--improved", action="store_true", help="Did it improve?")
    outcome_p.add_argument("--before", type=float, help="Metric before")
    outcome_p.add_argument("--after", type=float, help="Metric after")

    args = parser.parse_args()
    imp = Improver(auto_approve_low=getattr(args, "auto_approve", False))

    if args.command == "stats":
        stats = imp.get_stats()
        print(json.dumps(stats, indent=2))

    elif args.command == "pending":
        for p in imp.store.get_pending():
            print(f"[{p.risk_level}] {p.id}: {p.proposed_fix}")

    elif args.command == "actionable":
        for p in imp.get_actionable():
            print(f"[{p.risk_level}] {p.id}: {p.proposed_fix}")

    elif args.command == "all":
        for p in imp.store.load_all():
            print(f"[{p.status}] [{p.risk_level}] {p.id}: {p.pattern_type} — {p.proposed_fix[:80]}")

    elif args.command == "generate":
        from trace_analyzer import TraceAnalyzer
        report = TraceAnalyzer(args.trace_path).analyze()
        proposals = imp.generate_from_trace(report, session_id=args.session)
        print(f"Generated {len(proposals)} proposals:")
        for p in proposals:
            print(f"  [{p.risk_level}] {p.pattern_type}: {p.proposed_fix[:80]}")

    elif args.command == "approve":
        imp.store.update_status(args.proposal_id, "approved")
        print(f"Approved: {args.proposal_id}")

    elif args.command == "evolve":
        result = imp.evolve()
        print(f"Sentinel evolution cycle complete:")
        print(f"  Mutations: {result['mutations']}")
        print(f"  Cross-pollinations: {result['cross_pollinations']}")
        print(f"  Weakness gaps: {result['weakness_gaps']}")
        for g in result.get("gap_details", []):
            print(f"    - {g['domain']}: {g['reason']}")

    elif args.command == "outcome":
        imp.record_outcome(args.proposal_id, improved=args.improved,
                          metric_before=args.before, metric_after=args.after)
        status = "validated" if args.improved else "rejected"
        print(f"Recorded outcome for {args.proposal_id}: {status}")

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
