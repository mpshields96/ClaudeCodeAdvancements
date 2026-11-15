#!/usr/bin/env python3
"""Independent audit of nov14-sprint/nfl/walkforward (paper research only).

Does not import wf.py. Reads games.csv and the walkforward's bets_primary.csv
read-only, regrades every bet with adv_lib, and stresses the listed juice.
Prints a JSON summary to stdout; writes walkforward_audit.json next to this file
(aggregates only, no third-party rows).

    /usr/bin/python3 -I nov14-sprint/nfl/adversarial/audit_walkforward.py
"""
import csv
import datetime
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adv_lib as A  # noqa: E402

NFL = os.path.dirname(HERE)
GAMES = os.path.join(NFL, "data", "raw", "games.csv")
WF = os.path.join(NFL, "walkforward")
BETS = os.path.join(WF, "results", "bets_primary.csv")
WFRES = os.path.join(WF, "results", "walkforward_results.json")
POST = ("REG", "WC", "DIV", "CON", "SB")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def raw_rows():
    with open(GAMES, newline="") as fh:
        return {r["game_id"]: r for r in csv.DictReader(fh)}


def num(s):
    s = (s or "").strip()
    if s in ("", "NA"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def hold(a, b):
    return A.implied(a) + A.implied(b) - 1.0


def roi(rows, key):
    n = len(rows)
    return round(100.0 * sum(r[key] for r in rows) / n, 2) if n else None


def main():
    raw = raw_rows()
    out = {"run_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "inputs": {"games_csv_sha256": sha(GAMES), "bets_primary_sha256": sha(BETS),
                      "walkforward_results_sha256": sha(WFRES)}}

    # 1. Listed juice realism in 2012-2025 (bettable game types, scored).
    juice = {}
    for mk, (ka, kb) in {"spread": ("home_spread_odds", "away_spread_odds"),
                         "total": ("over_odds", "under_odds")}.items():
        hs, n, le0, lt2, asym, plus = [], 0, 0, 0, 0, 0
        for r in raw.values():
            if not (2012 <= int(r["season"]) <= 2025) or r["game_type"] not in POST:
                continue
            if num(r["home_score"]) is None:
                continue
            a, b = num(r[ka]), num(r[kb])
            if a is None or b is None or abs(a) < 100 or abs(b) < 100:
                continue
            n += 1
            h = hold(a, b)
            hs.append(h)
            le0 += h <= 1e-12
            lt2 += h < 0.02
            asym += a != b
            plus += (a > 0) or (b > 0)
        hs.sort()
        juice[mk] = {"games": n, "mean_hold_pct": round(100 * sum(hs) / n, 3),
                     "median_hold_pct": round(100 * hs[n // 2], 3),
                     "share_hold_le_0_pct": round(100.0 * le0 / n, 2),
                     "share_hold_below_2pct_pct": round(100.0 * lt2 / n, 2),
                     "share_sides_differ_pct": round(100.0 * asym / n, 2),
                     "share_with_plus_money_side_pct": round(100.0 * plus / n, 2),
                     "flat_110_hold_pct": round(100 * hold(-110, -110), 3)}
    out["listed_juice_2012_2025"] = juice

    # 2. Regrade every walkforward primary bet independently, then re-price.
    with open(BETS, newline="") as fh:
        bets = list(csv.DictReader(fh))
    mism = []
    rows = []
    mk_map = {"win": "moneyline", "cover": "pointSpread", "over": "total"}
    for b in bets:
        g = raw[b["game_id"]]
        hs_, as_ = num(g["home_score"]), num(g["away_score"])
        m = b["market"]
        line = num(b["line"]) if b["line"] not in ("", "None") else None
        odds = float(b["odds"])
        if m == "cover":
            assert line == num(g["spread_line"]), b["game_id"]
            # adv_lib grades spreads in the nflverse home-favored convention (spread_line itself).
            out_me = A.grade("spread", b["side"], line, hs_, as_)
            adv = A.adverse_line("spread", b["side"], line, 0.5)
            out_half = A.grade("spread", b["side"], adv, hs_, as_)
        elif m == "over":
            assert line == num(g["total_line"]), b["game_id"]
            out_me = A.grade("total", b["side"], line, hs_, as_)
            out_half = A.grade("total", b["side"], A.adverse_line("total", b["side"], line, 0.5), hs_, as_)
        else:
            out_me = A.grade("moneyline", b["side"], None, hs_, as_)
            out_half = out_me
        theirs = {"win": "W", "loss": "L", "push": "P"}[b["outcome"]]
        theirs_half = {"win": "W", "loss": "L", "push": "P"}[b["outcome_minus_half_point"]]
        p_listed = A.payout(out_me, odds)
        p10 = A.payout(out_me, A.worsen_american(odds, 10))
        pboth = A.payout(out_half, A.worsen_american(odds, 10))
        if (out_me != theirs or out_half != theirs_half
                or abs(p_listed - float(b["profit_listed"])) > 1e-5
                or abs(p10 - float(b["profit_minus_10c"])) > 1e-5
                or abs(pboth - float(b["profit_both"])) > 1e-5):
            mism.append(b["game_id"] + ":" + m)
        other = None
        if m == "cover":
            other = num(g["away_spread_odds"]) if b["side"] == "home" else num(g["home_spread_odds"])
        elif m == "over":
            other = num(g["under_odds"]) if b["side"] == "over" else num(g["over_odds"])
        cheaper = None if other is None else (A.implied(odds) < A.implied(other) - 1e-12)
        flat = None if m == "win" else A.payout(out_me, -110)
        rows.append({"season": int(b["season"]), "market": m, "side": b["side"], "odds": odds,
                     "out": out_me, "listed": p_listed, "m10": p10, "both": pboth,
                     "flat110": flat, "flat110_half": None if m == "win" else A.payout(out_half, -110),
                     "flat115": None if m == "win" else A.payout(out_me, -115),
                     "be": A.implied(odds), "edge": float(b["edge"]), "cheaper": cheaper})
    out["regrade"] = {"bets": len(bets), "mismatches": len(mism), "first_mismatches": mism[:10]}

    per = {}
    for m in ("win", "cover", "over"):
        rs = [r for r in rows if r["market"] == m and r["season"] <= 2025]
        w = sum(r["out"] == "W" for r in rs)
        l = sum(r["out"] == "L" for r in rs)
        p = len(rs) - w - l
        d = {"bets": len(rs), "W": w, "L": l, "P": p,
             "mean_breakeven_listed_pct": round(100 * sum(r["be"] for r in rs) / len(rs), 2),
             "roi_listed": roi(rs, "listed"), "roi_minus_10c": roi(rs, "m10"), "roi_both": roi(rs, "both"),
             "share_bets_plus_money_pct": round(100.0 * sum(r["odds"] > 0 for r in rs) / len(rs), 2),
             "breakeven_price_no_move": A.breakeven_price(w, l)}
        if m != "win":
            d["share_bets_on_cheaper_juice_side_pct"] = round(
                100.0 * sum(bool(r["cheaper"]) for r in rs) / len(rs), 2)
            d.update({"roi_flat_minus110": roi(rs, "flat110"), "roi_flat_minus115": roi(rs, "flat115"),
                      "roi_flat_minus110_half_point": roi(rs, "flat110_half")})
        per[m] = d
    out["walkforward_bets_2012_2025"] = per

    # 2b. Era split: archive juice is low-hold through 2022 and DK-like (about 4.7%) from 2023.
    hold_by_season = {}
    for S in range(2012, 2027):
        for mk, (ka, kb) in {"spread": ("home_spread_odds", "away_spread_odds"),
                             "total": ("over_odds", "under_odds")}.items():
            hs = []
            for r in raw.values():
                if int(r["season"]) != S or r["game_type"] not in POST:
                    continue
                a, b = num(r[ka]), num(r[kb])
                if a is None or b is None or abs(a) < 100 or abs(b) < 100:
                    continue
                hs.append(hold(a, b))
            if hs:
                hold_by_season.setdefault(str(S), {})[mk] = round(100 * sum(hs) / len(hs), 2)
    out["mean_listed_hold_pct_by_season"] = hold_by_season
    eras = {"2012_2022_low_hold": (2012, 2022), "2023_2026_dk_like": (2023, 2026)}
    era_out = {}
    for name, (lo, hi) in eras.items():
        for m in ("cover", "over", "win"):
            rs = [r for r in rows if r["market"] == m and lo <= r["season"] <= hi and r["out"] in "WLP"]
            if not rs:
                continue
            w = sum(r["out"] == "W" for r in rs)
            l = sum(r["out"] == "L" for r in rs)
            d = {"bets": len(rs), "W": w, "L": l, "P": len(rs) - w - l,
                 "roi_listed": roi(rs, "listed"), "roi_minus_10c": roi(rs, "m10"), "roi_both": roi(rs, "both"),
                 "mean_breakeven_listed_pct": round(100 * sum(r["be"] for r in rs) / len(rs), 2)}
            if m != "win":
                d["roi_flat_minus110"] = roi(rs, "flat110")
                d["share_bets_on_cheaper_juice_side_pct"] = round(
                    100.0 * sum(bool(r["cheaper"]) for r in rs) / len(rs), 2)
            era_out.setdefault(name, {})[m] = d
    out["walkforward_by_juice_era"] = era_out

    # 3. Check the fit windows recorded in their results: fit seasons end before the test season.
    res = json.load(open(WFRES))
    bad = []
    for k, v in res["primary"]["coefficients"].items():
        S = int(k.split("_")[0])
        if v["fit_seasons"][1] >= S:
            bad.append(k)
    out["fit_window_check"] = {"fits": len(res["primary"]["coefficients"]), "fit_end_not_before_test": bad}

    path = os.path.join(HERE, "walkforward_audit.json")
    with open(path, "w") as fh:
        fh.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
