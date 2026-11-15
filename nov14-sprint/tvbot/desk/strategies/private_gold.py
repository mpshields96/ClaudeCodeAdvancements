"""Private cross-check: the desk gold_basket engine on Codex's XAUUSD minute data.

LOCAL ONLY. The source data are third-party minute bid candles that Codex
downloaded into its own workspace; neither they nor any output of this script
are committed or published. Outputs go only to desk/out/research_private/
(aggregates only, no bar rows), which carries a '*' .gitignore.

Declared before running (2026-11-15, worker C):
  primary   = 2023, gold_basket with research escalation 1/2/4, pivots reset
              each session (Codex PREREGISTRATION: no warm-up across days),
              base costs per_unit_bid spread $0.30 + slip $0.05 per oz.
  baseline  = cash ($0 every session).
  metric    = mean daily net USD after costs, every qualifying session counted.
  pass      = 2023 mean > 0 and weekly-block bootstrap p05 > 0 and double-cost
              mean > 0; otherwise "does not beat cash".
  context   = 2021 and 2022, the fixed (no escalation) basket, the desk's
              chained-pivot variant, zero and double costs. Not used to choose.

Mapping to the engine (differences from Codex's replay are disclosed):
  * 08:00-15:54 New York minutes -> 95 five-minute bid bars, plus the 15:55
    minute as a one-minute final bar, so exits queued at the 15:50 bar close
    fill at the 15:55 open (Codex flattens on the 15:55 open too).
  * Basket +$3/-$6 checks happen at five-minute closes, fills at the next
    five-minute open; Codex checks every one-minute close. Mine is coarser.
  * The source has no volume (all 0), so bars carry volume None (unknown)
    instead of 0; otherwise the engine would refuse every fill.
  * Size is the TEST VALUE order_notional $2,000: floor(2000 / price) oz,
    i.e. 1 oz below $2,000/oz and 0 oz (no trade) at or above it.

Run:  /usr/bin/python3 -I nov14-sprint/tvbot/desk/strategies/private_gold.py
"""
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import sys
import time
import zipfile
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from strategies import base as B      # noqa: E402
from strategies import engine as E    # noqa: E402
from strategies import research as RS  # noqa: E402

SRC = os.environ.get("GOLD_PRIVATE_SRC", "")  # local-only private data folder; not published
OUT = os.path.join(DESK, "out", "research_private")
NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
EST = dt.timezone(dt.timedelta(hours=-5))
SESSION = 476  # 08:00..15:55 inclusive, one-minute stamps
YEARS = (2021, 2022, 2023)
COSTS = {
    "zero": {"kind": "per_unit_bid", "spread": 0.0, "slip": 0.0, "commission_per_unit": 0.0},
    "base": {"kind": "per_unit_bid", "spread": 0.30, "slip": 0.05, "commission_per_unit": 0.0},
    "double": {"kind": "per_unit_bid", "spread": 0.60, "slip": 0.10, "commission_per_unit": 0.0},
}
MODES = (
    ("escalating_reset", {"research_escalation": True, "gold_params": {"reset_pivots_each_session": True}}),
    ("fixed_reset", {"research_escalation": False, "gold_params": {"reset_pivots_each_session": True}}),
    ("escalating_chained", {"research_escalation": True}),
)
PRIMARY = ("2023", "escalating_reset", "base")
CODEX_2023 = {"mode": "escalating", "costs": "base", "sessions": 127, "net_usd": -104.78,
              "causal_net_usd": -137.17, "source": "nov14-sprint/codex/SUPERVISOR_1631Z.md"}


def read_sessions(year):
    """Complete 476-minute New York sessions, Codex's inclusion rules."""
    path = os.path.join(SRC, "xauusd_%d_M1.zip" % year)
    with open(os.path.join(SRC, "xauusd_%d_M1.json" % year), "r", encoding="utf-8") as fh:
        receipt = json.load(fh)
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    if digest != receipt.get("sha256"):
        raise SystemExit("sha256 mismatch for %s" % path)
    by_day, bad = {}, set()
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(name) as f:
            for stamp, o, h, l, c, _v in csv.reader(io.TextIOWrapper(f, encoding="ascii"), delimiter=";"):
                t = dt.datetime.strptime(stamp, "%Y%m%d %H%M%S").replace(tzinfo=EST)
                ny = t.astimezone(NY)
                if ny.weekday() > 4:
                    continue
                m = (ny.hour - 8) * 60 + ny.minute
                if not 0 <= m < SESSION:
                    continue
                vals = tuple(float(x) for x in (o, h, l, c))
                op, hi, lo, cl = vals
                day = ny.date()
                slot = by_day.setdefault(day, {})
                if (m in slot or t.second != 0 or not all(math.isfinite(x) and x > 0 for x in vals)
                        or lo > min(op, cl) or hi < max(op, cl)):
                    bad.add(day)
                slot[m] = (t.astimezone(UTC), vals)
    days = sorted(d for d, s in by_day.items() if len(s) == SESSION and d not in bad)
    return [[by_day[d][k] for k in range(SESSION)] for d in days], {
        "sha256": digest, "weekdays_with_rows": len(by_day), "included_sessions": len(days),
        "excluded_incomplete_or_invalid": len(by_day) - len(days)}


def to_bars(sessions, symbol):
    bars, seq = [], 0
    for mins in sessions:
        groups = [mins[k:k + 5] for k in range(0, 475, 5)] + [mins[475:476]]
        for g in groups:
            seq += 1
            t0 = g[0][0]
            bars.append({
                "type": "bar", "symbol": symbol, "seq": seq, "simulated": True,
                "ts_open": B.fmt_ts(t0), "ts_close": B.fmt_ts(t0 + dt.timedelta(minutes=len(g))),
                "open": g[0][1][0], "high": max(x[1][1] for x in g),
                "low": min(x[1][2] for x in g), "close": g[-1][1][3], "volume": None,
            })
    return bars


def run_one(bars, mode_cfg, cost):
    cfg = {"session_tz": "America/New_York", "session_close": "15:56",
           "costs": dict(COSTS[cost]), "test_size": B.load_test_size()}
    cfg.update(json.loads(json.dumps(mode_cfg)))
    rep = RS.replay("gold_basket", bars, cfg)
    rows = RS.session_rows(rep, cfg)
    s = RS.summarize(rows)
    s["median_day_usd"] = RS.r4(sorted(r["net"] for r in rows)[len(rows) // 2]) if rows else 0.0
    s["positive_day_share"] = RS.r4(s["win_sessions"] / float(s["sessions"])) if s["sessions"] else 0.0
    s["max_intraday_drawdown_usd"] = RS.r4(RS.path_stats(rep.records)["max_drawdown_usd"])
    s["max_abs_net_oz"] = max([abs(r["qty_close"]) for r in rep.records] + [0])
    s["zero_size_refusals"] = sum(1 for r in rep.records if r.get("reason_code") == "ZERO_SIZE")
    s["baskets_closed"] = getattr(rep.book, "baskets_closed", None)
    s["bootstrap"] = RS.bootstrap(rows)
    return s


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("# Private: licensed third-party data outputs. Never commit or publish.\n*\n")
    quality, results = {}, {}
    for y in YEARS:
        sess, q = read_sessions(y)
        quality[str(y)] = q
        bars = to_bars(sess, "XAUUSD_SPOT_BID_PRIVATE")
        q["bars"] = len(bars)
        results[str(y)] = {}
        for mname, mcfg in MODES:
            results[str(y)][mname] = {c: run_one(bars, mcfg, c) for c in COSTS}
    py, pm, pc = PRIMARY
    p = results[py][pm][pc]
    passed = (p["mean_daily_usd"] > 0 and p["bootstrap"]["p05_mean_daily_usd"] > 0
              and results[py][pm]["double"]["mean_daily_usd"] > 0)
    out = {
        "label": "PRIVATE LOCAL RESEARCH (historical spot bid proxy, not broker fills). Never commit or publish.",
        "simulated": True, "generated": B.fmt_ts(dt.datetime.now(UTC)),
        "rule_hash": RS.rule_hash(), "primary": {"year": py, "mode": pm, "costs": pc},
        "pass_criterion": "2023 mean > 0 and bootstrap p05 > 0 and double-cost mean > 0",
        "verdict": "beats cash" if passed else "does not beat cash",
        "size": "TEST VALUES order_notional %s (floor(notional/price) oz; 0 oz at or above $2,000/oz)"
                % B.load_test_size()["order_notional"],
        "codex_2023_reference": CODEX_2023, "quality": quality, "results": results,
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "PRIVATE_GOLD_RESULT.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    lines = ["# Private gold cross-check (LOCAL ONLY, never commit or publish)", "",
             out["label"], "", "Verdict on the declared primary (%s, %s, %s costs): **%s**." % (py, pm, pc, out["verdict"]),
             "", "| Year | Mode | Costs | Sessions | Mean/day | Total | Worst day | Fills | Max oz | Zero-size refusals | Boot p05..p95 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for y in results:
        for m in results[y]:
            for c, s in results[y][m].items():
                b = s["bootstrap"]
                lines.append("| %s | %s | %s | %d | %+.2f | %+.2f | %+.2f | %d | %d | %d | %+.2f..%+.2f |" % (
                    y, m, c, s["sessions"], s["mean_daily_usd"], s["total_usd"], s["worst_day_usd"],
                    s["fills"], s["max_abs_net_oz"], s["zero_size_refusals"],
                    b["p05_mean_daily_usd"], b["p95_mean_daily_usd"]))
    lines += ["", "Codex's own 2023 replay (one-minute checks, 1/2/4 oz legs): net %+.2f over %d sessions; causal %+.2f."
              % (CODEX_2023["net_usd"], CODEX_2023["sessions"], CODEX_2023["causal_net_usd"]),
              "", "Differences: five-minute basket checks and fills (Codex: one-minute); TEST size gives 1 oz legs "
              "below $2,000/oz and none above, so escalation means 1/2/4 x that base; volume unknown (None).",
              "", "Runtime %.1fs." % out["runtime_s"]]
    with open(os.path.join(OUT, "PRIVATE_GOLD_RESULT.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
