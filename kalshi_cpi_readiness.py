#!/usr/bin/env python3
"""kalshi_cpi_readiness.py - audit April CPI micro-live readiness for polybot.

Usage:
    python3 kalshi_cpi_readiness.py
    python3 kalshi_cpi_readiness.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


DEFAULT_POLYBOT_ROOT = "/Users/matthewshields/Projects/polymarket-bot"
_RELEASE_RE = re.compile(
    r"NEXT CPI RELEASE:\s*(\d{4}-\d{2}-\d{2}) at (\d{2}:\d{2}) ET \((\d{2}:\d{2}) UTC\)"
)


@dataclass
class ReadinessCheck:
    name: str
    status: str
    detail: str


@dataclass
class CPIReadinessReport:
    overall: str
    release_label: str | None
    hours_until_release: float | None
    checks: list[ReadinessCheck]
    blockers: list[str]
    next_actions: list[str]


def _read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def _path(polybot_root: str, relative: str) -> str:
    return os.path.join(polybot_root, relative)


def _parse_config_mode(config_text: str) -> str | None:
    in_kalshi = False
    for raw_line in config_text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith(" "):
            in_kalshi = line.strip() == "kalshi:"
            continue
        if in_kalshi:
            match = re.match(r"\s*mode:\s*([A-Za-z_]+)", line)
            if match:
                return match.group(1)
    return None


def _parse_release_label(monitor_text: str) -> tuple[str | None, datetime | None]:
    match = _RELEASE_RE.search(monitor_text)
    if not match:
        return None, None
    date_str, _, utc_time = match.groups()
    release_dt = datetime.fromisoformat(f"{date_str}T{utc_time}:00+00:00")
    return match.group(0).replace("NEXT CPI RELEASE: ", ""), release_dt


def _check(
    name: str,
    condition: bool,
    ok_detail: str,
    fail_detail: str,
) -> ReadinessCheck:
    return ReadinessCheck(
        name=name,
        status="pass" if condition else "fail",
        detail=ok_detail if condition else fail_detail,
    )


def collect_cpi_readiness(
    polybot_root: str = DEFAULT_POLYBOT_ROOT,
    now: datetime | None = None,
) -> CPIReadinessReport:
    now = now or datetime.now(timezone.utc)

    strategy_text = _read_text(_path(polybot_root, "src/strategies/economics_sniper.py"))
    main_text = _read_text(_path(polybot_root, "main.py"))
    config_text = _read_text(_path(polybot_root, "config.yaml"))
    monitor_text = _read_text(_path(polybot_root, "scripts/cpi_release_monitor.py"))
    econ_tests_text = _read_text(_path(polybot_root, "tests/test_economics_sniper.py"))
    monitor_tests_text = _read_text(_path(polybot_root, "tests/test_cpi_monitor.py"))

    mode = _parse_config_mode(config_text)
    release_label, release_dt = _parse_release_label(monitor_text)
    hours_until_release = None
    if release_dt is not None:
        hours_until_release = round((release_dt - now).total_seconds() / 3600.0, 1)

    checks = [
        _check(
            "economics_strategy",
            all(
                token in strategy_text
                for token in (
                    "PAPER_CALIBRATION_USD: float = 0.50",
                    "_DEFAULT_TRIGGER_PRICE_CENTS = 88.0",
                    "_DEFAULT_MAX_SECONDS_REMAINING = 172800",
                    "_DEFAULT_HARD_SKIP_SECONDS = 300",
                )
            ),
            "economics_sniper has the expected 88c floor, 48h gate, 5m hard skip, and 0.50 USD paper sizing.",
            "economics_sniper is missing one or more expected CPI paper-trial parameters.",
        ),
        _check(
            "main_wiring",
            all(
                token in main_text
                for token in (
                    "async def economics_sniper_loop(",
                    'name=\"economics_sniper_loop\"',
                    'logger.info(\"Economics sniper loop started',
                )
            ),
            "main.py wires economics_sniper_loop into the normal async task set.",
            "main.py does not appear to wire economics_sniper_loop into the normal task set.",
        ),
        _check(
            "paper_guardrails",
            all(
                token in main_text
                for token in (
                    "PaperExecutor",
                    "check_paper_order_allowed",
                    "strategy.PAPER_CALIBRATION_USD",
                )
            ),
            "economics_sniper still runs through PaperExecutor plus paper kill-switch checks.",
            "paper execution or paper kill-switch guards are missing from economics_sniper_loop.",
        ),
        _check(
            "cpi_monitor",
            "NOT a trading bot" in monitor_text and release_label is not None,
            f"cpi_release_monitor is present and targets {release_label}.",
            "cpi_release_monitor is missing or does not expose the next CPI release timing.",
        ),
        _check(
            "test_coverage",
            "TestEconomicsSniperTimeGate" in econ_tests_text and "TestDetectPriceChange" in monitor_tests_text,
            "Both economics_sniper and cpi_release_monitor have targeted test files.",
            "Targeted CPI/economics test coverage is missing.",
        ),
    ]

    if mode == "demo":
        checks.append(
            ReadinessCheck(
                name="config_mode",
                status="pass",
                detail="config.yaml keeps Kalshi in demo mode by default.",
            )
        )
    elif mode:
        checks.append(
            ReadinessCheck(
                name="config_mode",
                status="warn",
                detail=f"config.yaml is set to '{mode}' instead of demo; double-check before any April 10 run.",
            )
        )
    else:
        checks.append(
            ReadinessCheck(
                name="config_mode",
                status="warn",
                detail="Could not determine kalshi.mode from config.yaml.",
            )
        )

    if release_dt is not None and hours_until_release is not None:
        if hours_until_release < 0:
            release_detail = f"The scripted CPI release window ({release_label}) is already in the past."
            release_status = "warn"
        else:
            release_detail = f"{hours_until_release:.1f}h remain until the scripted CPI release window ({release_label})."
            release_status = "pass"
    else:
        release_detail = "Could not parse the scripted CPI release window."
        release_status = "warn"
    checks.append(ReadinessCheck(name="release_window", status=release_status, detail=release_detail))

    blockers: list[str] = []
    if any(check.status == "fail" for check in checks):
        blockers.append("Structural CPI readiness checks are failing; fix the missing code or coverage before treating April 10 as deployable.")
    blockers.extend(
        [
            "Confirm open KXCPI contracts actually exist in the 24-48h window starting April 8; the code is ready, but market availability is still a live dependency.",
            "Run scripts/cpi_release_monitor.py on April 10 starting around 08:28 ET to verify whether Kalshi reprices slowly enough to justify any micro-live escalation.",
            "Keep economics_sniper paper-only through the first CPI cycle; promote only after reviewing fills, timing, and kill-switch behavior.",
        ]
    )

    overall = "blocked" if any(check.status == "fail" for check in checks) else "watch"
    next_actions = [
        "Run `python3 kalshi_cpi_readiness.py` before April 8 and again on April 10 morning.",
        "If `overall=watch`, verify KXCPI market availability and then run `python3 scripts/cpi_release_monitor.py` from the polybot repo at 08:28 ET.",
        "After the CPI event, write the observed lag and repricing verdict back to CCA_TO_POLYBOT.md and CODEX_OBSERVATIONS.md.",
    ]

    return CPIReadinessReport(
        overall=overall,
        release_label=release_label,
        hours_until_release=hours_until_release,
        checks=checks,
        blockers=blockers,
        next_actions=next_actions,
    )


def format_report(report: CPIReadinessReport) -> str:
    lines = [f"CPI READINESS: {report.overall.upper()}"]
    if report.release_label:
        lines.append(f"Release: {report.release_label}")
    lines.append("")
    lines.append("Checks:")
    for check in report.checks:
        lines.append(f"- {check.name}: {check.status}")
        lines.append(f"  {check.detail}")

    lines.append("")
    lines.append("Blockers:")
    for blocker in report.blockers:
        lines.append(f"- {blocker}")

    lines.append("")
    lines.append("Next Actions:")
    for action in report.next_actions:
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Kalshi CPI micro-live readiness from the CCA repo.")
    parser.add_argument("--polybot-root", default=DEFAULT_POLYBOT_ROOT, help="Polybot repo root.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args(argv)

    report = collect_cpi_readiness(polybot_root=args.polybot_root)
    if args.json:
        payload = {
            "overall": report.overall,
            "release_label": report.release_label,
            "hours_until_release": report.hours_until_release,
            "checks": [asdict(check) for check in report.checks],
            "blockers": report.blockers,
            "next_actions": report.next_actions,
        }
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
