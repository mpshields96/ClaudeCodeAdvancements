"""Offline research harness for the desk strategies (worker C).

    /usr/bin/python3 -I nov14-sprint/tvbot/desk/strategies/research.py

HARNESS EVIDENCE (SYNTHETIC). Paper and offline only; every number is
simulated. Uses the same replay engine as the desk (engine.Replayer), so
research and desk decisions cannot drift apart. The declaration in
strategies/RULES.md section 6 (and DECLARATION below) was fixed before this
script was first run. Writes desk/out/research/RESEARCH_RESULT.json and .md.
Private gold data is not read here; any private run writes only to
desk/out/research_private/.
"""
import datetime
import hashlib
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
TVBOT = os.path.dirname(DESK)
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from strategies import base as B      # noqa: E402
from strategies import engine as E    # noqa: E402

FIX = os.path.join(TVBOT, "fixtures")
OUT = os.path.join(DESK, "out", "research")
CLAIM = os.path.join(OUT, "HOLDOUT_CLAIM.json")
LABEL = "HARNESS EVIDENCE (SYNTHETIC)"
REF_BALANCE = 10000.0
SEED = 20261115
BOOT_N = 2000

# (name, engine kind, extra cfg). First entry is the declared candidate.
STRATS = [
    ("gold_basket_escalating", "gold_basket", {"research_escalation": True}),
    ("cash", "cash", {}),
    ("fixed_risk_single", "fixed_risk_single", {}),
    ("bounded_fixed", "bounded_fixed", {}),
    ("gold_alternating", "gold_alternating", {"research_escalation": True}),
    ("gold_basket_session_reset", "gold_basket",
     {"research_escalation": True, "gold_params": {"reset_pivots_each_session": True}}),
    ("ema", "ema", {}),
    ("ema_overnight", "ema_overnight", {}),
]
SCENARIOS = [
    ("base", {}),
    ("zero_commission", {"costs": {"commission_per_share": 0.0, "commission_min": 0.0}}),
    ("costs_x2", {"cost_mult": 2.0}),
    ("costs_x3", {"cost_mult": 3.0}),
    ("delay_1_bar", {"delay_bars": 1}),
    ("miss_every_5th_entry", {"miss_every": 5}),
    ("partial_half", {"partial_frac": 0.5}),
]
FOLDS = [("F1", 0, 30), ("F2", 30, 60), ("F3", 60, 90)]

DECLARATION = {
    "declared_before_results": "strategies/RULES.md section 6, frozen ~17:25Z 2026-11-15",
    "candidate": "gold_basket_escalating (gold_basket with research escalation 1/2/4)",
    "baseline": "cash ($0 every session)",
    "comparators": [s[0] for s in STRATS[2:]],
    "metric": "mean daily net USD after costs, every session counted, $0 sessions included",
    "walk_forward": "rules frozen, no refit: chronological evaluation windows F1=sessions 1-30, "
                    "F2=31-60, F3=61-90 of normal_bars",
    "untouched_final_period": "holdout_bars.jsonl (30 sessions), claimed once with the rule hash",
    "stress": [s[0] for s in SCENARIOS],
    "path_checks": "every start session of normal_bars, worst intrabar marks, $10,000 research reference "
                   "balance (assumption, not Matthew's limit); margin breach = gross > 2x equity or "
                   "equity < 25% of gross; barriers -6% / +10%",
    "bootstrap": "weekly blocks, %d resamples, seed %d" % (BOOT_N, SEED),
    "pass_criterion": "mean > 0 overall and in F1, F2, F3; holdout mean > 0; bootstrap p05 > 0; "
                      "costs x2 mean > 0. Otherwise 'does not beat cash'.",
    "test_size": "tvbot/config/smaller_size.json order_notional, TEST VALUES, never tuned",
}

CODEX_GOLD = {
    "what": "Codex private 2023 XAUUSD spot replay of the Reddit gold basket (escalating legs, +$3/-$6)",
    "net_usd": -104.78,
    "sessions": 127,
    "causal_replay_net_usd": -137.17,
    "notes": "627 modeled fills; worst basket mark -$8.93; max net notional $13,587.32; with $10k and "
             "100% collateral, short of capital on 3 entry days",
    "basis": "historical spot bid/ask quotes with Codex's fee/slip assumptions; not broker fills, not a "
             "US-instrument result, private data not used or published here",
    "sources": ["nov14-sprint/codex/SUPERVISOR_1631Z.md", "nov14-sprint/tvbot/desk/CONTRACT.md"],
    "simulated": True,
}


def r4(x):
    return None if x is None else round(float(x), 4)


def load_bars(name, seq_offset=0):
    bars = []
    with open(os.path.join(FIX, name), "r", encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            row = json.loads(ln)
            if row.get("type") != "bar":
                continue
            if seq_offset:
                row = dict(row)
                row["seq"] = int(row["seq"]) + seq_offset
            bars.append(row)
    bars.sort(key=lambda b: (b["ts_close"], b["seq"]))
    return bars


def rule_hash():
    h = hashlib.sha256()
    for f in ("engine.py", "base.py", "registry.py", "RULES.md"):
        with open(os.path.join(HERE, f), "rb") as fh:
            h.update(f.encode() + b"\0" + fh.read() + b"\0")
    return h.hexdigest()


def holdout_gate(rh):
    """Claim the holdout once. Same rule hash later: allowed (deterministic re-run)."""
    if os.path.exists(CLAIM):
        with open(CLAIM, "r", encoding="utf-8") as fh:
            claim = json.load(fh)
        return claim.get("rule_hash") == rh, claim
    claim = {
        "claimed_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "rule_hash": rh,
        "hashed_files": ["strategies/engine.py", "strategies/base.py", "strategies/registry.py",
                         "strategies/RULES.md"],
        "note": "holdout_bars.jsonl first evaluated by worker C strategies with these rules. A changed "
                "rule hash refuses the holdout. EMAX's holdout was already claimed 2026-11-14T22:17:06Z, "
                "so the ema rows are not a first look.",
        "simulated": True,
    }
    with open(CLAIM, "w", encoding="utf-8") as fh:
        json.dump(claim, fh, indent=2, sort_keys=True)
    return True, claim


def replay(kind, bars, cfg):
    c = dict(cfg)
    c["keep_records"] = True
    return E.run(kind, bars, c)


def session_rows(rep, cfg):
    order, last_eq, last_fee = [], {}, {}
    for r in rep.records:
        s = r["session"]
        if s not in last_eq:
            order.append(s)
        last_eq[s] = r["eq_close"]
        last_fee[s] = r["fees"]
    fills = {}
    for f in rep.fills:
        s = B.session_key({"ts_close": f["ts"]}, cfg)
        fills[s] = fills.get(s, 0) + 1
    rows, pe, pf = [], 0.0, 0.0
    for s in order:
        rows.append({"session": s, "net": last_eq[s] - pe, "fees": last_fee[s] - pf, "fills": fills.get(s, 0)})
        pe, pf = last_eq[s], last_fee[s]
    return rows


def summarize(rows):
    v = [r["net"] for r in rows]
    n = len(v)
    tot = sum(v)
    mean = tot / n if n else 0.0
    sd = math.sqrt(sum((x - mean) ** 2 for x in v) / (n - 1)) if n > 1 else 0.0
    return {
        "sessions": n, "total_usd": r4(tot), "mean_daily_usd": r4(mean), "sd_daily_usd": r4(sd),
        "sessions_with_fills": sum(1 for r in rows if r["fills"]),
        "zero_sessions": sum(1 for x in v if abs(x) < 1e-9),
        "win_sessions": sum(1 for x in v if x > 1e-9), "loss_sessions": sum(1 for x in v if x < -1e-9),
        "best_day_usd": r4(max(v) if v else 0.0), "worst_day_usd": r4(min(v) if v else 0.0),
        "fills": sum(r["fills"] for r in rows), "fees_usd": r4(sum(r["fees"] for r in rows)),
        "simulated": True,
    }


def path_stats(records, base_eq=0.0):
    peak, maxdd, breach, barrier = REF_BALANCE, 0.0, None, None
    for r in records:
        ew = REF_BALANCE + r["eq_worst"] - base_eq
        ec = REF_BALANCE + r["eq_close"] - base_eq
        maxdd = max(maxdd, peak - ew)
        peak = max(peak, ec)
        g = r["gross_worst"]
        if breach is None and g > 0 and (g > 2.0 * ew or ew < 0.25 * g):
            breach = r["ts_close"]
        if barrier is None:
            if ew - REF_BALANCE <= -0.06 * REF_BALANCE:
                barrier = "down_-6pct"
            elif ec - REF_BALANCE >= 0.10 * REF_BALANCE:
                barrier = "up_+10pct"
    return {"max_drawdown_usd": maxdd, "margin_breach_ts": breach, "barrier": barrier or "neither"}


def every_start(kind, bars, cfg):
    starts, prev = [], None
    for i, b in enumerate(bars):
        s = B.session_key(b, cfg)
        if s != prev:
            starts.append(i)
            prev = s
    dds, breaches, bar_hits = [], 0, {"down_-6pct": 0, "up_+10pct": 0, "neither": 0}
    for i in starts:
        ps = path_stats(replay(kind, bars[i:], cfg).records)
        dds.append(ps["max_drawdown_usd"])
        breaches += 1 if ps["margin_breach_ts"] else 0
        bar_hits[ps["barrier"]] += 1
    dds_sorted = sorted(dds)
    return {
        "starts": len(starts), "worst_max_drawdown_usd": r4(max(dds)),
        "median_max_drawdown_usd": r4(dds_sorted[len(dds_sorted) // 2]),
        "worst_max_drawdown_pct_of_ref": r4(100.0 * max(dds) / REF_BALANCE),
        "starts_with_margin_breach": breaches, "barrier_first_hit": bar_hits,
        "reference_balance_usd": REF_BALANCE, "simulated": True,
    }


def bootstrap(rows):
    weeks, keys = {}, []
    for r in rows:
        d = datetime.date.fromisoformat(r["session"])
        k = tuple(d.isocalendar()[:2])
        if k not in weeks:
            weeks[k] = []
            keys.append(k)
        weeks[k].append(r["net"])
    blocks = [weeks[k] for k in keys]
    rng = random.Random(SEED)
    means = []
    for _ in range(BOOT_N):
        s = []
        for _ in range(len(blocks)):
            s.extend(blocks[rng.randrange(len(blocks))])
        means.append(sum(s) / len(s))
    means.sort()
    return {"weeks": len(blocks), "resamples": BOOT_N, "seed": SEED,
            "p05_mean_daily_usd": r4(means[int(0.05 * BOOT_N)]),
            "p50_mean_daily_usd": r4(means[BOOT_N // 2]),
            "p95_mean_daily_usd": r4(means[int(0.95 * BOOT_N) - 1]),
            "share_resamples_mean_above_0": r4(sum(1 for m in means if m > 0) / float(BOOT_N)),
            "simulated": True}


def verdict(res):
    b = res["normal"]["base"]
    checks = {
        "normal_mean_gt_0": b["all"]["mean_daily_usd"] > 0,
        "F1_mean_gt_0": b["folds"]["F1"]["mean_daily_usd"] > 0,
        "F2_mean_gt_0": b["folds"]["F2"]["mean_daily_usd"] > 0,
        "F3_mean_gt_0": b["folds"]["F3"]["mean_daily_usd"] > 0,
        "holdout_mean_gt_0": bool(res.get("holdout") and res["holdout"]["base"]["all"]["mean_daily_usd"] > 0),
        "bootstrap_p05_gt_0": res["bootstrap_normal_base"]["p05_mean_daily_usd"] > 0,
        "costs_x2_mean_gt_0": res["normal"]["costs_x2"]["all"]["mean_daily_usd"] > 0,
    }
    return {"checks": checks, "beats_cash": all(checks.values())}


def main(use_holdout=True):
    os.makedirs(OUT, exist_ok=True)
    normal = load_bars("normal_bars.jsonl")
    hold = load_bars("holdout_bars.jsonl", seq_offset=int(normal[-1]["seq"])) if use_holdout else []
    test_size = B.load_test_size()
    rh = rule_hash()
    if use_holdout:
        hold_ok, claim = holdout_gate(rh)
    else:
        hold_ok, claim = False, {"claimed_utc": None, "note": "--no-holdout dry run; holdout not opened"}
    hold_sessions = set(B.session_key(b, {}) for b in hold)
    variants = 0
    out = {}
    for name, kind, extra in STRATS:
        res = {"kind": kind, "rule_id": None, "normal": {}, "holdout": {} if hold_ok else None}
        for scen, sc in SCENARIOS:
            cfg = dict(extra)
            cfg.update(sc)
            cfg["test_size"] = test_size
            rep = replay(kind, normal, cfg)
            res["rule_id"] = res["rule_id"] or rep.rid
            rows = session_rows(rep, cfg)
            res["normal"][scen] = {
                "all": summarize(rows),
                "folds": dict((f, summarize(rows[a:z])) for f, a, z in FOLDS),
                "not_filled_events": sum(1 for e in rep.events if e["event"] == "NOT_FILLED_ZERO_VOLUME"),
                "missed_entries": sum(1 for e in rep.events if e["event"] == "ENTRY_MISSED_STRESS"),
            }
            variants += 1
            if scen == "base":
                res["bootstrap_normal_base"] = bootstrap(rows)
                res["every_start_normal_base"] = every_start(kind, normal, cfg)
                res["daily_normal_base"] = [{"session": r["session"], "net_usd": r4(r["net"]),
                                             "fills": r["fills"]} for r in rows]
            if hold_ok:
                hrep = replay(kind, normal + hold, cfg)
                hrows = [r for r in session_rows(hrep, cfg) if r["session"] in hold_sessions]
                n_norm = sum(1 for r in hrep.records if r["session"] not in hold_sessions)
                base_eq = hrep.records[n_norm - 1]["eq_close"] if n_norm else 0.0
                ps = path_stats(hrep.records[n_norm:], base_eq)
                res["holdout"][scen] = {"all": summarize(hrows),
                                        "path_from_holdout_start": {
                                            "max_drawdown_usd": r4(ps["max_drawdown_usd"]),
                                            "margin_breach_ts": ps["margin_breach_ts"],
                                            "barrier": ps["barrier"]}}
                variants += 1
                if scen == "base":
                    res["bootstrap_holdout_base"] = bootstrap(hrows)
        res["verdict"] = verdict(res)
        out[name] = res
    result = {
        "label": LABEL,
        "simulated": True,
        "generated_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "data": {"normal": "tvbot/fixtures/normal_bars.jsonl (%d bars)" % len(normal),
                 "holdout": "tvbot/fixtures/holdout_bars.jsonl (%d bars)" % len(hold),
                 "source": "synthetic SYNTH-FUND-60M; not evidence about gold or any market"},
        "declaration": DECLARATION,
        "rule_hash": rh,
        "holdout_claim": claim,
        "holdout_evaluated": hold_ok,
        "test_size": {"order_notional": test_size["order_notional"], "label": test_size["label"]},
        "variant_count": {
            "rule_variants": len(STRATS),
            "scenarios": len(SCENARIOS),
            "evaluated_configurations": variants,
            "every_start_replays": sum(out[n]["every_start_normal_base"]["starts"] for n in out),
            "note": "Choosing the best of these after the fact overstates it; the candidate was declared first.",
        },
        "codex_gold_comparison": CODEX_GOLD,
        "strategies": out,
    }
    with open(os.path.join(OUT, "RESEARCH_RESULT.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True)
    with open(os.path.join(OUT, "RESEARCH_RESULT.md"), "w", encoding="utf-8") as fh:
        fh.write(render_md(result))
    return result


def _m(x):
    return "n/a" if x is None else ("%+.2f" % x)


def render_md(res):
    L = []
    a = L.append
    a("# Strategy research result: %s" % res["label"])
    a("")
    a("Every number below is simulated, from synthetic fixture bars (SYNTH-FUND-60M). Nothing here is "
      "evidence about gold, GLD, MGC or any real market. Paper and offline only.")
    a("")
    a("Generated %s. Rule hash `%s`. Holdout evaluated: %s (claim %s)." % (
        res["generated_utc"], res["rule_hash"][:16], res["holdout_evaluated"],
        res["holdout_claim"].get("claimed_utc")))
    a("")
    a("Size: TEST VALUES, order_notional %s from tvbot/config/smaller_size.json (never tuned)." %
      res["test_size"]["order_notional"])
    a("")
    a("## Declared before running")
    a("")
    for k in ("candidate", "baseline", "metric", "walk_forward", "untouched_final_period", "pass_criterion"):
        a("- **%s**: %s" % (k, res["declaration"][k]))
    a("")
    a("## Base costs: mean daily net USD (every session counted)")
    a("")
    a("| Strategy | Normal (90) | F1 | F2 | F3 | Holdout (30) | Fills normal | Fees normal | Worst day | Boot p05..p95 | Beats cash |")
    a("|---|---|---|---|---|---|---|---|---|---|---|")
    for n, s in res["strategies"].items():
        b = s["normal"]["base"]
        h = s["holdout"]["base"]["all"]["mean_daily_usd"] if s.get("holdout") else None
        bs = s["bootstrap_normal_base"]
        a("| %s | %s | %s | %s | %s | %s | %d | %.2f | %s | %s..%s | %s |" % (
            n, _m(b["all"]["mean_daily_usd"]), _m(b["folds"]["F1"]["mean_daily_usd"]),
            _m(b["folds"]["F2"]["mean_daily_usd"]), _m(b["folds"]["F3"]["mean_daily_usd"]), _m(h),
            b["all"]["fills"], b["all"]["fees_usd"], _m(b["all"]["worst_day_usd"]),
            _m(bs["p05_mean_daily_usd"]), _m(bs["p95_mean_daily_usd"]),
            "yes" if s["verdict"]["beats_cash"] else "no"))
    a("")
    a("## Totals (USD, simulated)")
    a("")
    a("| Strategy | Normal total | Holdout total | Sessions with fills (normal) | Zero sessions (normal) |")
    a("|---|---|---|---|---|")
    for n, s in res["strategies"].items():
        b = s["normal"]["base"]["all"]
        h = s["holdout"]["base"]["all"]["total_usd"] if s.get("holdout") else None
        a("| %s | %s | %s | %d | %d |" % (n, _m(b["total_usd"]), _m(h), b["sessions_with_fills"], b["zero_sessions"]))
    a("")
    a("## Stress: normal-period mean daily net USD")
    a("")
    scen = [s[0] for s in SCENARIOS]
    a("| Strategy | " + " | ".join(scen) + " |")
    a("|---|" + "---|" * len(scen))
    for n, s in res["strategies"].items():
        a("| %s | " % n + " | ".join(_m(s["normal"][k]["all"]["mean_daily_usd"]) for k in scen) + " |")
    a("")
    a("## Paths from every start session (normal, base costs, $10,000 research reference)")
    a("")
    a("| Strategy | Starts | Worst max DD | Median max DD | Margin breaches | -6% first | +10% first | Neither |")
    a("|---|---|---|---|---|---|---|---|")
    for n, s in res["strategies"].items():
        e = s["every_start_normal_base"]
        bh = e["barrier_first_hit"]
        a("| %s | %d | %.2f | %.2f | %d | %d | %d | %d |" % (
            n, e["starts"], e["worst_max_drawdown_usd"], e["median_max_drawdown_usd"],
            e["starts_with_margin_breach"], bh["down_-6pct"], bh["up_+10pct"], bh["neither"]))
    a("")
    v = res["variant_count"]
    a("## Variant count")
    a("")
    a("%d rule variants x %d cost/fill scenarios; %d evaluated configurations (normal + holdout) and %d "
      "every-start replays. %s" % (v["rule_variants"], v["scenarios"], v["evaluated_configurations"],
                                   v["every_start_replays"], v["note"]))
    a("")
    c = res["codex_gold_comparison"]
    a("## Historical-spot comparison (not broker fills)")
    a("")
    a("%s: net %+.2f USD over %d sessions; causal replay %+.2f USD. %s. Basis: %s. Sources: %s." % (
        c["what"], c["net_usd"], c["sessions"], c["causal_replay_net_usd"], c["notes"], c["basis"],
        ", ".join(c["sources"])))
    a("")
    a("## Limits")
    a("")
    a("- Hourly OHLC: the order of high and low inside a bar is unknown. Research replay fills are at the next open (the desk itself fills at the next bar's close plus simulated costs); basket "
      "+$3/-$6 checks happen only at closes, so one bar can jump far past the stop.")
    a("- Desk `gold_basket` (no escalation) equals `bounded_fixed` by rule, so it is not run twice.")
    a("- The ema rows reuse EMAX, whose holdout was claimed 2026-11-14T22:17:06Z; its holdout row is not a "
      "first look.")
    a("- The $10,000 reference balance, margin test and -6%/+10% barriers are research assumptions, not "
      "Matthew's limits.")
    a("- Avoided losses are not counted as profit. Cash is $0, and $0 is a valid result.")
    a("")
    return "\n".join(L)


if __name__ == "__main__":
    r = main(use_holdout="--no-holdout" not in sys.argv[1:])
    for n, s in r["strategies"].items():
        b = s["normal"]["base"]["all"]
        h = s["holdout"]["base"]["all"] if s.get("holdout") else {}
        print("%-26s normal mean %+8.3f total %+9.2f fills %3d | holdout mean %s | beats cash %s" % (
            n, b["mean_daily_usd"], b["total_usd"], b["fills"],
            ("%+8.3f" % h["mean_daily_usd"]) if h else "n/a", s["verdict"]["beats_cash"]))
    print("wrote", os.path.join(OUT, "RESEARCH_RESULT.json"))
