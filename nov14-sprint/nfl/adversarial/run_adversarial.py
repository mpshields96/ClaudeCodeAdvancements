"""Run the independent replay, adversarial checks and accepted-price stress.

Usage: /usr/bin/python3 -I run_adversarial.py   (absolute paths inside; writes adversarial_results.json)
Paper and research only. Reads lane outputs as data; imports no lane code.
"""
import csv
import datetime
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adv_lib as A  # noqa: E402

NFL = os.path.dirname(HERE)
GAMES = os.path.join(NFL, "data", "raw", "games.csv")
PICKER = os.path.join(NFL, "slate", "frozen_picker.json")
LANE_POT = os.path.join(NFL, "slate", "results", "past_only_test.json")
REAL = os.path.join(NFL, "real")
OUT = os.path.join(HERE, "adversarial_results.json")

# Lane numbers to match, copied from results/backtest_report.txt (run 2026-11-14T22:00:58Z).
LANE_TRAIN = {
    ("HOME_DOG", 1): (1558, 766, 754, 38, -3.70), ("HOME_DOG", 3): (1146, 571, 545, 30, -2.26),
    ("HOME_DOG", 7): (339, 181, 154, 4, 3.11), ("BIG_DOG", 7): (1367, 677, 656, 34, -2.97),
    ("BIG_DOG", 10): (607, 316, 273, 18, 2.35), ("BIG_DOG", 14): (147, 75, 66, 6, 1.48),
    ("REST_EDGE", 3): (903, 451, 429, 23, -2.10), ("REST_EDGE", 6): (447, 225, 210, 12, -1.22),
    ("HIGH_TOTAL_UNDER", 47): (1304, 673, 614, 17, -0.17), ("HIGH_TOTAL_UNDER", 50): (519, 261, 249, 9, -2.26),
}
LANE_HOLD = {
    ("HOME_DOG", 7): (63, 38, 23, 2, 18.33, 18.43), ("BIG_DOG", 10): (79, 33, 45, 1, -18.99, -18.87),
    ("REST_EDGE", 6): (69, 33, 35, 1, -7.25, -7.52), ("HIGH_TOTAL_UNDER", 47): (218, 108, 108, 2, -4.50, -4.07),
}
LANE_BASE = {
    ("home", "train"): (4383, 2073, 2197, 113, -7.13), ("home", "hold"): (816, 400, 397, 19, -4.09),
    ("dog", "train"): (4379, 2208, 2058, 113, -1.16), ("dog", "hold"): (816, 386, 411, 19, -7.36),
    ("under", "train"): (4383, 2173, 2141, 69, -3.78), ("under", "hold"): (816, 400, 411, 5, -5.80),
}
MOVES = [0.0, 0.5, 1.0, 1.5]
JUICE = [-110.0, -115.0, -120.0]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def pct(x):
    return None if x is None else round(100.0 * x, 2)


def cmp(mine, lane, label, mismatches):
    if tuple(mine) != tuple(lane):
        mismatches.append({"what": label, "mine": list(mine), "lane": list(lane)})


def wlp(s):
    return (s["bets"], s["w"], s["l"], s["p"])


def main():
    res = {"run_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "inputs": {"games_csv_sha256": sha256(GAMES)}, "mismatches": []}
    mm = res["mismatches"]
    games = A.load_games(GAMES)
    reg = [g for g in games if g["game_type"] == "REG" and A.completed(g)]
    train = [g for g in reg if 2006 <= g["season"] <= 2022]
    hold = [g for g in reg if 2023 <= g["season"] <= 2025]
    y26 = [g for g in reg if g["season"] == 2026 and g["week"] <= 9]
    res["counts"] = {"train_games": len(train), "holdout_games": len(hold), "y2026_w1_9_games": len(y26)}
    cmp((len(train), len(hold)), (4383, 816), "game counts", mm)

    # ------------------------------------------------ 1. replay of the ten variants and four frozen rules
    rep = {"train": {}, "holdout": {}, "y2026_w1_9_extra_look": {}}
    vb_train = {}
    for fam, vals in A.FAMILIES.items():
        for v in vals:
            b = A.bets_for(fam, v, train)
            vb_train["%s-T%s" % (fam, v)] = [(x[0]["game_id"], x[1], x[2]) for x in b]
            s = A.summarize(b)
            rep["train"]["%s-%s" % (fam, v)] = {**s, "roi_pct": pct(s["roi"]), "passes": len(train) - s["bets"]}
            lt = LANE_TRAIN[(fam, v)]
            cmp(wlp(s) + (round(100 * s["roi"], 2),), lt, "train %s %s" % (fam, v), mm)
    vb_hold = {}
    for fam, v in A.FROZEN:
        key = "%s-%s" % (fam, v)
        for wname, win in (("holdout", hold), ("y2026_w1_9_extra_look", y26)):
            b = A.bets_for(fam, v, win)
            s = A.summarize(b)
            sr = A.summarize(b, price_mode="recorded")
            n_dec = s["w"] + s["l"]
            lo95, hi95 = A.wilson(s["w"], n_dec)
            lo99, hi99 = A.wilson(s["w"], n_dec, z=2.4977)
            pval = A.binom_sf(s["w"], n_dec, A.BREAKEVEN_110) if n_dec else None
            rep[wname][key] = {**s, "roi_pct": pct(s["roi"]), "roi_recorded_pct": pct(sr["roi"]),
                               "recorded_dropped": sr["dropped_missing_odds"],
                               "win_rate_pct": pct(s["w"] / n_dec) if n_dec else None,
                               "wilson95_pct": [pct(lo95), pct(hi95)], "wilson9875_pct": [pct(lo99), pct(hi99)],
                               "p_one_sided_vs_52_38": pval,
                               "edge_test_pass": bool(lo95 is not None and lo95 > A.BREAKEVEN_110)}
            if wname == "holdout":
                vb_hold[key] = [(x[0]["game_id"], x[1], x[2]) for x in b]
                lh = LANE_HOLD[(fam, v)]
                cmp(wlp(s) + (round(100 * s["roi"], 2), round(100 * sr["roi"], 2)), lh, "holdout " + key, mm)
    # baselines
    base = {}
    for name in ("home", "dog", "under"):
        for wname, win in (("train", train), ("hold", hold)):
            b = []
            for g in win:
                if name == "home":
                    b.append((g, "spread", "home", g["sl"]))
                elif name == "dog":
                    if g["sl"] is None or g["sl"] == 0:
                        continue
                    b.append((g, "spread", "away" if g["sl"] > 0 else "home", g["sl"]))
                else:
                    b.append((g, "total", "under", g["tl"]))
            s = A.summarize(b)
            base["%s_%s" % (name, wname)] = {**s, "roi_pct": pct(s["roi"])}
            cmp(wlp(s) + (round(100 * s["roi"], 2),), LANE_BASE[(name, wname)], "baseline %s %s" % (name, wname), mm)
    rep["baselines"] = base
    res["rules_replay"] = rep

    # ------------------------------------------------ 2. adversarial checks
    adv = {}
    # 2a training at recorded odds: missing dropped vs silently set to -110
    tr_rec = {}
    for fam, v in A.FROZEN:
        b = A.bets_for(fam, v, train)
        s_flat = A.summarize(b)
        s_drop = A.summarize(b, price_mode="recorded")
        s_def = A.summarize(b, price_mode="recorded", default_missing=-110.0)
        juices = [A.recorded_price(x[0], x[1], x[2]) for x in b if A.recorded_price(x[0], x[1], x[2]) is not None]
        tr_rec["%s-%s" % (fam, v)] = {
            "flat_110_roi_pct": pct(s_flat["roi"]), "recorded_missing_dropped_roi_pct": pct(s_drop["roi"]),
            "recorded_missing_as_110_roi_pct": pct(s_def["roi"]), "missing_odds_bets": s_drop["dropped_missing_odds"],
            "bets": s_flat["bets"], "mean_recorded_breakeven_pct": pct(sum(A.implied(j) for j in juices) / len(juices)) if juices else None}
    adv["train_recorded_odds"] = tr_rec
    # 2b by-season record of the frozen rules, 2006-2026
    by_season = {}
    for fam, v in A.FROZEN:
        rows = {}
        for season in range(2006, 2027):
            win = [g for g in reg if g["season"] == season and (season < 2026 or g["week"] <= 9)]
            s = A.summarize(A.bets_for(fam, v, win))
            rows[season] = [s["w"], s["l"], s["p"], pct(s["roi"])]
        by_season["%s-%s" % (fam, v)] = rows
    adv["by_season"] = by_season
    # 2c family-wise nulls
    null_tr = A.family_null(vb_train, sims=4000)
    null_ho = A.family_null(vb_hold, sims=4000, seed=20261115)
    obs_tr = max(r["roi"] for r in rep["train"].values())
    obs_ho = max(r["roi"] for r in rep["holdout"].values())
    adv["family_null"] = {
        "train_best_of_10_observed_roi_pct": pct(obs_tr),
        "train_null_p_best_ge_observed": sum(1 for x in null_tr if x >= obs_tr - 1e-12) / len(null_tr),
        "train_null_best_median_roi_pct": pct(null_tr[len(null_tr) // 2]),
        "train_null_best_95th_roi_pct": pct(null_tr[int(0.95 * len(null_tr))]),
        "holdout_best_of_4_observed_roi_pct": pct(obs_ho),
        "holdout_null_p_best_ge_observed": sum(1 for x in null_ho if x >= obs_ho - 1e-12) / len(null_ho),
        "holdout_null_best_median_roi_pct": pct(null_ho[len(null_ho) // 2]),
        "holdout_null_best_95th_roi_pct": pct(null_ho[int(0.95 * len(null_ho))]),
        "note": "fair-coin covers at -110 (true ROI -4.55%); shared coin per game keeps overlaps",
    }
    # 2d neutral sites, week-1 rest, overlap, threshold fragility, sign sanity, pushes
    hd_tr = A.bets_for("HOME_DOG", 7, train)
    hd_ho = A.bets_for("HOME_DOG", 7, hold)
    adv["neutral_site_takes"] = {
        "HOME_DOG-7_train": sum(1 for x in hd_tr if x[0]["location"] != "Home"),
        "HOME_DOG-7_holdout": sum(1 for x in hd_ho if x[0]["location"] != "Home"),
        "all_reg_2006_2025_neutral": sum(1 for g in train + hold if g["location"] != "Home"),
    }
    re_tr = A.bets_for("REST_EDGE", 6, train + hold)
    adv["rest_edge_6"] = {
        "takes_2006_2025": len(re_tr), "week1_takes": sum(1 for x in re_tr if x[0]["week"] == 1),
        "week1_rest_values": sorted({(x[0]["hr"], x[0]["ar"]) for x in re_tr if x[0]["week"] == 1})[:10],
    }
    bd_ids = {x[0]["game_id"] for x in A.bets_for("BIG_DOG", 10, train + hold)}
    hd_ids = {x[0]["game_id"] for x in hd_tr + hd_ho}
    adv["overlap_HOME_DOG7_BIG_DOG10_2006_2025"] = {"home_dog7": len(hd_ids), "big_dog10": len(bd_ids),
                                                     "both": len(hd_ids & bd_ids)}
    frag = {}
    for t in (6.0, 6.5, 7.0, 7.5, 8.0, 9.0):
        st = A.summarize(A.bets_for("HOME_DOG", t, train))
        sh = A.summarize(A.bets_for("HOME_DOG", t, hold))
        frag["T%s" % t] = {"train": [st["bets"], pct(st["roi"])], "holdout": [sh["bets"], pct(sh["roi"])]}
    adv["home_dog_threshold_fragility"] = frag
    n = len(train + hold)
    res_sl = [(g["hs"] - g["as"], g["sl"]) for g in train + hold if g["sl"] is not None]
    mx = sum(r for r, _ in res_sl) / len(res_sl)
    my = sum(s for _, s in res_sl) / len(res_sl)
    cov = sum((r - mx) * (s - my) for r, s in res_sl)
    vx = sum((r - mx) ** 2 for r, _ in res_sl)
    vy = sum((s - my) ** 2 for _, s in res_sl)
    fav_win = [((g["hs"] - g["as"]) > 0) == (g["sl"] > 0) for g in train + hold if g["sl"] and g["hs"] != g["as"]]
    adv["sign_sanity_2006_2025"] = {"games": n, "corr_result_spread": round(cov / math.sqrt(vx * vy), 4),
                                    "mean_result_minus_line": round(mx - my, 3),
                                    "favorite_straight_up_win_pct": pct(sum(fav_win) / len(fav_win))}
    push = {}
    for fam, v in A.FROZEN:
        s = A.summarize(A.bets_for(fam, v, hold))
        push["%s-%s" % (fam, v)] = {"pushes": s["p"], "roi_pushes_in_denominator_pct": pct(s["roi"]),
                                    "roi_pushes_excluded_pct": pct(s["profit"] / (s["w"] + s["l"]))}
    adv["push_handling_holdout"] = push
    # key numbers: share of final margins (all REG 2006-2025)
    margins = [abs(g["hs"] - g["as"]) for g in train + hold]
    adv["key_margin_share_pct"] = {str(k): pct(sum(1 for m in margins if m == k) / len(margins)) for k in (1, 2, 3, 4, 6, 7, 10, 14)}
    tot_land = {}
    totals = [g["hs"] + g["as"] for g in train + hold]
    for k in (41, 43, 44, 47, 51):
        tot_land[str(k)] = pct(sum(1 for t in totals if t == k) / len(totals))
    adv["total_points_share_pct"] = tot_land
    # power: bets needed to show a true win rate with the lane's own test (one-sided 2.5%, 80% power)
    def need(p1, p0=A.BREAKEVEN_110):
        za, zb = 1.959964, 0.841621
        return math.ceil(((za * math.sqrt(p0 * (1 - p0)) + zb * math.sqrt(p1 * (1 - p1))) / (p1 - p0)) ** 2)
    adv["power_bets_needed"] = {"true_54pct": need(0.54), "true_55pct": need(0.55), "true_57pct": need(0.57),
                                "true_60pct": need(0.60),
                                "home_dog7_takes_per_season_2006_2025": round(len(hd_ids) / 20.0, 1)}
    res["adversarial"] = adv

    # ------------------------------------------------ 3. accepted-price stress on history
    stress = {}
    for fam, v in A.FROZEN:
        key = "%s-%s" % (fam, v)
        stress[key] = {}
        for wname, win in (("train", train), ("holdout", hold), ("y2026_w1_9", y26), ("all_2006_2025", train + hold)):
            b = A.bets_for(fam, v, win)
            grid = {}
            for d in MOVES:
                for j in JUICE:
                    s = A.summarize(b, d=d, price=j)
                    grid["move%s_%d" % (d, int(j))] = pct(s["roi"])
                s0 = A.summarize(b, d=d)
                be = A.breakeven_price(s0["w"], s0["l"])
                grid["move%s_breakeven_price" % d] = None if be is None else round(be, 1)
                grid["move%s_wlp" % d] = [s0["w"], s0["l"], s0["p"]]
            # largest adverse move with ROI >= 0 at -110 (0.5 steps up to 3)
            tol = None
            for k in range(0, 7):
                d = 0.5 * k
                if A.summarize(b, d=d)["roi"] is not None and A.summarize(b, d=d)["roi"] >= 0:
                    tol = d
                else:
                    break
            grid["max_adverse_move_roi_ge_0_at_110"] = tol
            # adverse selection: book refuses a share of the bets that go on to win
            s0 = A.summarize(b)
            for r in (0.10, 0.25):
                w2 = s0["w"] * (1 - r)
                n2 = w2 + s0["l"] + s0["p"]
                grid["refuse_%d%%_of_winners_roi" % int(r * 100)] = pct((w2 * 100 / 110 - s0["l"]) / n2) if n2 else None
            stress[key][wname] = grid
    res["stress_history"] = stress

    # ------------------------------------------------ 4. picker replay (Elo + points), lane past-only test
    with open(PICKER) as f:
        fp = json.load(f)
    P = fp.get("params", fp)
    preds = A.elo_walk(games, P, "2026-11-15")
    wins = {"tune": (2010, 2022, None), "test_a": (2023, 2025, None), "test_b": (2026, 2026, (1, 9))}
    pk = {"n_predictions": len(preds), "windows": {}}
    with open(LANE_POT) as f:
        lane = json.load(f)
    cmp((len(preds),), (lane["n_predictions"],), "picker n_predictions", mm)
    for wn, (lo, hi, wk) in wins.items():
        wp = [b for b in preds if lo <= b["g"]["season"] <= hi]
        if wk:
            wp = [b for b in wp if b["g"]["game_type"] == "REG" and wk[0] <= b["g"]["week"] <= wk[1]]
        ll_mkt = A.log_loss(wp, 1.0)
        ll_mod = A.log_loss(wp, 0.0)
        sp = A.side_test(wp, "spread")
        to = A.side_test(wp, "total")
        t2m = A.top2(wp, "market")
        t2o = A.top2(wp, "model")
        row = {"n_games": len(wp), "n_priced": ll_mkt[2], "ll_market": ll_mkt[0], "ll_model": ll_mod[0],
               "spread": sp, "total": to, "top2_market": t2m, "top2_model": t2o}
        # price stress on the model's top-2 moneyline picks
        row["top2_model_price_stress_roi_pct"] = {
            str(c): pct(A.top2(wp, "model", price_shift=c)["profit"] / t2o["bets"]) if t2o["bets"] else None
            for c in (0, 5, 10, 15, 20)}
        pk["windows"][wn] = row
        lw = lane["windows"][wn]
        cmp((len(wp), ll_mkt[2]), (lw["n_games"], lw["n_priced"]), "picker %s counts" % wn, mm)
        cmp((round(ll_mkt[0], 6), round(ll_mod[0], 6)),
            (round(lw["market"]["log_loss"], 6), round(lw["model"]["log_loss"], 6)), "picker %s log loss" % wn, mm)
        for mk, lk in (("spread", "spread"), ("total", "total")):
            for band in ("all", "edge"):
                mine = (row[mk][band]["W"], row[mk][band]["L"], row[mk][band]["P"])
                ln = (lw[lk][band]["w"], lw[lk][band]["l"], lw[lk][band]["p"])
                cmp(mine, ln, "picker %s %s %s" % (wn, mk, band), mm)
        for by in ("market", "model"):
            t = row["top2_" + by]
            lt = lw["top2_" + by]
            cmp((t["slates"], t["bets"], t["W"], t["L"], t["P"], t["both"], round(t["profit"], 6)),
                (lt["slates"], lt["bets"], lt["w"], lt["l"], lt["p"], lt["both"], round(lt["profit"], 6)),
                "picker %s top2 %s" % (wn, by), mm)
    tune = [b for b in preds if 2010 <= b["g"]["season"] <= 2022]
    pk["blend_grid_tune_ll"] = {str(w): A.log_loss(tune, w)[0] for w in P["blend_grid"]}
    for w in P["blend_grid"]:
        lg = [x for x in lane["grid"] if abs(x["market_weight"] - w) < 1e-9][0]
        cmp((round(pk["blend_grid_tune_ll"][str(w)], 6),), (round(lg["log_loss"], 6),), "picker blend grid w=%s" % w, mm)
    res["picker_replay"] = pk

    # ------------------------------------------------ 5. real week-10 takes (read-only, not settled)
    takes = []
    with open(os.path.join(REAL, "week10_rule_scores.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["action"] != "take":
                continue
            takes.append(r)
    allhist = train + hold
    wk = []
    for r in takes:
        fam, v = r["rule_version"].split("-v1.")
        v = float(v[1:])
        line = float(r["real_line"])
        price = float(r["real_price_american"])
        market, side = r["market"], r["side"]
        hist = A.bets_for(fam, v, allhist)
        rows = {"game_id": r["game_id"], "rule": r["rule_version"], "market": market, "side": side,
                "line": line, "price": price, "breakeven_pct": pct(A.implied(price))}
        s_hist = A.summarize(hist)
        dec = s_hist["w"] + s_hist["l"]
        rows["rule_history_2006_2025_cover_pct"] = pct(s_hist["w"] / dec)
        lo, hi = A.wilson(s_hist["w"], dec)
        rows["rule_history_wilson95_pct"] = [pct(lo), pct(hi)]
        for d in (0.5, 1.0, 1.5):
            rows["line_after_%s_adverse" % d] = A.adverse_line(market, side, line, d)
            sd = A.summarize(hist, d=d)
            dd = sd["w"] + sd["l"]
            rows["rule_history_cover_pct_after_%s" % d] = pct(sd["w"] / dd)
        for j in (-115.0, -120.0):
            rows["breakeven_at_%d_pct" % int(j)] = pct(A.implied(min(price, j)))
        wk.append(rows)
    # line agreement between games.csv (nflverse) and the captured DraftKings display
    gmap = {g["game_id"]: g for g in games}
    agree = {"spread_same": 0, "spread_compared": 0, "total_same": 0, "total_compared": 0}
    with open(os.path.join(REAL, "week10_prices.csv"), newline="") as f:
        for r in csv.DictReader(f):
            g = gmap.get(r["game_id"])
            if not g or r["market"] not in ("pointSpread", "total"):
                continue
            # totals are shown as "o49.5"/"u49.5"; strip the side letter
            ls = A.fnum(r["line_as_shown"].lstrip("ouOU"))
            if ls is None:
                continue
            if r["market"] == "pointSpread" and r["side"] == "home":
                agree["spread_compared"] += 1
                agree["spread_same"] += int(g["sl"] is not None and abs(-ls - g["sl"]) < 1e-9)
            if r["market"] == "total" and r["side"] == "under":
                agree["total_compared"] += 1
                agree["total_same"] += int(g["tl"] is not None and abs(ls - g["tl"]) < 1e-9)
    res["real_week10"] = {"takes": wk, "nflverse_vs_captured_line_agreement": agree,
                          "note": "read-only; nothing settled or re-priced; captured 2026-11-14T22:53:42Z"}

    # ------------------------------------------------ 6. frozen Sunday card (read-only)
    card = {}
    for price in (-162.0, -166.0, -170.0, -175.0, -180.0):
        be = A.implied(price)
        card["KC_ML_%d" % int(price)] = {"breakeven_pct": pct(be),
                                         "ev_at_market_61.16_pct": pct(0.6116 * A.american_profit(price) - (1 - 0.6116)),
                                         "ev_at_model_60.24_pct": pct(0.6024 * A.american_profit(price) - (1 - 0.6024))}
    for price in (-110.0, -115.0, -120.0, -125.0):
        card["WARREN_REC_YDS_O22.5_%d" % int(price)] = {
            "breakeven_pct": pct(A.implied(price)),
            "ev_at_50pct_pct": pct(0.5 * A.american_profit(price) - 0.5)}
    card["KC_ML_max_price_for_ev_ge_0_at_market"] = round(A.breakeven_price(0.6116, 0.3884), 1)
    card["KC_ML_max_price_for_ev_ge_0_at_model"] = round(A.breakeven_price(0.6024, 0.3976), 1)
    res["frozen_card_stress"] = card

    with open(OUT, "w") as f:
        json.dump(res, f, indent=1, sort_keys=True, default=str)
    print("mismatches:", len(mm))
    for m in mm:
        print("  ", m)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
