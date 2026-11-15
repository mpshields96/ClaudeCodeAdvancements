#!/usr/bin/env python3
"""NFL walk-forward model vs listed market prices. Paper research only.

Reproduce everything (from any folder):
    /usr/bin/python3 -I nov14-sprint/nfl/walkforward/wf.py

Standard library only, Python 3.9 compatible. Every setting comes from
PREREGISTRATION.json (frozen before the first test run). Reads
../data/raw/games.csv after checking its SHA-256 against the
pre-registration. Writes only inside this folder:
    results/walkforward_results.json   deterministic (no timestamps)
    results/bets_primary.csv           derived from third-party data; keep uncommitted
    RUN_LOG.jsonl                      one appended line per run (UTC, hashes)

Nothing here places a bet or reads an account. No paper result implies a
real edge.
"""
import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import random
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
NFL = os.path.dirname(HERE)
DATA = os.path.join(NFL, "data", "raw", "games.csv")
PREREG = os.path.join(HERE, "PREREGISTRATION.json")

BET_GAME_TYPES = ("REG", "WC", "DIV", "CON", "SB")
FRANCHISE = {"STL": "LA", "SD": "LAC", "OAK": "LV"}  # deviation 1 in prereg
ISSUE34_GAMES = ("2021_15_NE_IND", "2021_17_CLE_PIT", "2023_02_IND_HOU")
# Pre-game fields of game g a feature may read. Scores never enter.
PREGAME_FIELDS = ("game_id", "season", "week", "gameday", "game_type", "home", "away",
                  "location", "spread_line", "total_line", "ml_home", "ml_away",
                  "sp_home", "sp_away", "over", "under", "home_rest", "away_rest",
                  "div_game", "roof")


class Refused(Exception):
    pass


# ---------------------------------------------------------------- odds math
def valid_odds(x):
    return x is not None and not math.isnan(x) and abs(x) >= 100


def implied(odds):
    """Implied probability (with vig) of an American price."""
    if odds < 0:
        return -odds / (-odds + 100.0)
    return 100.0 / (odds + 100.0)


def profit(odds):
    """Profit in units on a 1-unit win at an American price."""
    if odds < 0:
        return 100.0 / -odds
    return odds / 100.0


def devig(odds_a, odds_b):
    """Multiplicative devig of a two-way market -> (fair_a, fair_b)."""
    qa, qb = implied(odds_a), implied(odds_b)
    s = qa + qb
    return qa / s, qb / s


def worse_cents(odds, cents=10):
    """Price `cents` worse on the American cents scale (-110->-120, +105->-105)."""
    c = odds - 100 if odds >= 100 else odds + 100
    c -= cents
    return c + 100 if c >= 0 else c - 100


def settle(outcome, odds):
    if outcome == "win":
        return profit(odds)
    if outcome == "loss":
        return -1.0
    return 0.0


def grade(market, side, line, home_score, away_score):
    """Outcome of one bet. `line` is the line the bettor holds."""
    if market == "win":
        m = home_score - away_score
        if m == 0:
            return "push"
        return "win" if (m > 0) == (side == "home") else "loss"
    if market == "cover":
        m = home_score - away_score
        if m == line:
            return "push"
        return "win" if (m > line) == (side == "home") else "loss"
    t = home_score + away_score
    if t == line:
        return "push"
    return "win" if (t > line) == (side == "over") else "loss"


# ---------------------------------------------------------------- data
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _num(s):
    s = (s or "").strip()
    if s == "" or s.upper() == "NA":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_games(path, expect_sha=None):
    if not os.path.isfile(path):
        raise Refused("INPUT_MISSING: %s" % path)
    if expect_sha is not None and sha256_file(path) != expect_sha:
        raise Refused("DATA_HASH_MISMATCH: %s" % path)
    games = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            g = {
                "game_id": r["game_id"], "season": int(r["season"]), "week": int(r["week"]),
                "gameday": r["gameday"], "game_type": r["game_type"],
                "home": r["home_team"], "away": r["away_team"], "location": r["location"],
                "home_score": _num(r["home_score"]), "away_score": _num(r["away_score"]),
                "spread_line": _num(r["spread_line"]), "total_line": _num(r["total_line"]),
                "ml_home": _num(r["home_moneyline"]), "ml_away": _num(r["away_moneyline"]),
                "sp_home": _num(r["home_spread_odds"]), "sp_away": _num(r["away_spread_odds"]),
                "over": _num(r["over_odds"]), "under": _num(r["under_odds"]),
                "home_rest": _num(r["home_rest"]), "away_rest": _num(r["away_rest"]),
                "div_game": _num(r["div_game"]), "roof": r["roof"],
            }
            games.append(g)
    games.sort(key=lambda g: (g["gameday"], g["game_id"]))
    return games


def scored(g):
    return g["home_score"] is not None and g["away_score"] is not None


def pregame_view(g):
    return {k: g[k] for k in PREGAME_FIELDS}


def flagged_quality(g):
    """Spread sign disagrees with the moneyline favourite (|spread| >= 1.5)."""
    s, h, a = g["spread_line"], g["ml_home"], g["ml_away"]
    if s is None or not (valid_odds(h) and valid_odds(a)) or abs(s) < 1.5:
        return False
    home_fav_ml = implied(h) > implied(a)
    return home_fav_ml != (s > 0)


# ---------------------------------------------------------------- ratings
def compute_features(games, cfg):
    """Pre-game features for every game, strictly as of the day before its gameday.

    Games are processed one date at a time: all features for a date are read
    before any result of that date updates the ratings.
    """
    ecfg, pcfg = cfg["ratings"]["elo"], cfg["ratings"]["points"]
    e0, k, hfa_e = float(ecfg["initial"]), float(ecfg["k"]), float(ecfg["home_field_elo"])
    per_pt = float(ecfg["elo_points_per_spread_point"])
    alpha, p0 = float(pcfg["alpha"]), float(pcfg["initial"])
    keep = 2.0 / 3.0
    elo, off, dfn, last_season = {}, {}, {}, {}
    season_pts = {}  # season -> [points, team-games] from processed results
    feats = {}
    by_date = {}
    for g in games:
        by_date.setdefault(g["gameday"], []).append(g)
    for day in sorted(by_date):
        day_games = by_date[day]
        for g in day_games:
            v = pregame_view(g)
            s = v["season"]
            for t in (FRANCHISE.get(v["home"], v["home"]), FRANCHISE.get(v["away"], v["away"])):
                if t not in elo:
                    elo[t], off[t], dfn[t], last_season[t] = e0, p0, p0, s
                elif last_season[t] != s:
                    elo[t] = e0 + keep * (elo[t] - e0)
                    prev = season_pts.get(last_season[t])
                    m = prev[0] / prev[1] if prev and prev[1] else p0
                    off[t] = m + keep * (off[t] - m)
                    dfn[t] = m + keep * (dfn[t] - m)
                    last_season[t] = s
            h, a = FRANCHISE.get(v["home"], v["home"]), FRANCHISE.get(v["away"], v["away"])
            hfa = 0.0 if v["location"] == "Neutral" else hfa_e
            ediff = elo[h] + hfa - elo[a]
            pred_h = (off[h] + dfn[a]) / 2.0
            pred_a = (off[a] + dfn[h]) / 2.0
            rest = 0.0
            if v["home_rest"] is not None and v["away_rest"] is not None:
                rest = max(-7.0, min(7.0, v["home_rest"] - v["away_rest"])) / 7.0
            f = {"elo_home": elo[h], "elo_away": elo[a], "hfa": hfa,
                 "elo_diff_incl_hfa_over_100": ediff / 100.0,
                 "rest_diff_clip7_over_7": rest,
                 "div_game": 1.0 if v["div_game"] == 1 else 0.0,
                 "dome": 1.0 if v["roof"] == "dome" else 0.0,
                 "pts_pred_home": pred_h, "pts_pred_away": pred_a}
            if valid_odds(v["ml_home"]) and valid_odds(v["ml_away"]):
                ph, _ = devig(v["ml_home"], v["ml_away"])
                f["logit_market_fair_home_win"] = math.log(ph / (1.0 - ph))
            if v["spread_line"] is not None:
                sl = v["spread_line"]
                f["elo_spread_minus_line_over_7"] = (ediff / per_pt - sl) / 7.0
                f["pts_margin_minus_line_over_7"] = (pred_h - pred_a - sl) / 7.0
                f["spread_line_over_7"] = sl / 7.0
            if v["total_line"] is not None:
                tl = v["total_line"]
                f["pts_total_minus_line_over_10"] = (pred_h + pred_a - tl) / 10.0
                f["total_line_over_10"] = tl / 10.0
            feats[v["game_id"]] = f
        for g in day_games:  # results of this date update ratings only now
            if not scored(g):
                continue
            h, a = FRANCHISE.get(g["home"], g["home"]), FRANCHISE.get(g["away"], g["away"])
            hfa = 0.0 if g["location"] == "Neutral" else hfa_e
            diff = elo[h] + hfa - elo[a]
            p_home = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
            margin = g["home_score"] - g["away_score"]
            if margin > 0:
                res, wdiff = 1.0, diff
            elif margin < 0:
                res, wdiff = 0.0, -diff
            else:
                res, wdiff = 0.5, 0.0
            mult = math.log(abs(margin) + 1.0) * 2.2 / (wdiff * 0.001 + 2.2)
            shift = k * mult * (res - p_home)
            elo[h] += shift
            elo[a] -= shift
            hs, as_ = g["home_score"], g["away_score"]
            off[h] += alpha * (hs - off[h])
            dfn[h] += alpha * (as_ - dfn[h])
            off[a] += alpha * (as_ - off[a])
            dfn[a] += alpha * (hs - dfn[a])
            sp = season_pts.setdefault(g["season"], [0.0, 0])
            sp[0] += hs + as_
            sp[1] += 2
    return feats


# ---------------------------------------------------------------- logistic
def _solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-300:
            raise Refused("SINGULAR_MATRIX")
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            if f:
                for j in range(c, n + 1):
                    M[r][j] -= f * M[c][j]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][j] * x[j] for j in range(r + 1, n))) / M[r][r]
    return x


def sigmoid(z):
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def fit_logistic(X, y, lam, max_iter, tol):
    """L2 logistic regression by Newton-Raphson. Intercept (index 0) unpenalised."""
    p = len(X[0]) + 1
    w = [0.0] * p
    rows = [[1.0] + list(x) for x in X]
    for _ in range(max_iter):
        g = [0.0] * p
        H = [[0.0] * p for _ in range(p)]
        for xr, yr in zip(rows, y):
            mu = sigmoid(sum(wi * xi for wi, xi in zip(w, xr)))
            r = yr - mu
            s = mu * (1.0 - mu)
            for i in range(p):
                g[i] += r * xr[i]
                si = s * xr[i]
                Hi = H[i]
                for j in range(i, p):
                    Hi[j] += si * xr[j]
        for i in range(p):
            for j in range(i):
                H[i][j] = H[j][i]
        for i in range(1, p):
            g[i] -= lam * w[i]
            H[i][i] += lam
        delta = _solve(H, g)
        w = [wi + di for wi, di in zip(w, delta)]
        if max(abs(d) for d in delta) < tol:
            break
    return w


def predict(w, x):
    return sigmoid(w[0] + sum(wi * xi for wi, xi in zip(w[1:], x)))


# ---------------------------------------------------------------- markets
def market_sides(market):
    return ("home", "away") if market in ("win", "cover") else ("over", "under")


def listed_prices(g, market):
    """(odds_side1, odds_side2, assumed_flag) or None when no bet is possible."""
    if market == "win":
        if valid_odds(g["ml_home"]) and valid_odds(g["ml_away"]):
            return g["ml_home"], g["ml_away"], False
        return None
    a, b = (g["sp_home"], g["sp_away"]) if market == "cover" else (g["over"], g["under"])
    line = g["spread_line"] if market == "cover" else g["total_line"]
    if line is None:
        return None
    if valid_odds(a) and valid_odds(b):
        return a, b, False
    return (a if valid_odds(a) else -110.0), (b if valid_odds(b) else -110.0), True


def target(g, market):
    """1/0 for side 1 of the market, None for a push/tie (dropped from fit and scoring)."""
    hs, as_ = g["home_score"], g["away_score"]
    if market == "win":
        m = hs - as_
        return None if m == 0 else (1 if m > 0 else 0)
    if market == "cover":
        if g["spread_line"] is None:
            return None
        m = hs - as_ - g["spread_line"]
        return None if m == 0 else (1 if m > 0 else 0)
    if g["total_line"] is None:
        return None
    t = hs + as_ - g["total_line"]
    return None if t == 0 else (1 if t > 0 else 0)


def design_row(f, names):
    if any(n not in f for n in names):
        return None
    return [f[n] for n in names]


def fit_rows(games, feats, market, names, lo, hi):
    X, y = [], []
    for g in games:
        if not (lo <= g["season"] <= hi) or not scored(g):
            continue
        if market == "win" and listed_prices(g, "win") is None:
            continue
        row = design_row(feats[g["game_id"]], names)
        t = target(g, market)
        if row is None or t is None:
            continue
        X.append(row)
        y.append(t)
    return X, y


def make_bet(g, market, side, p_side, fair_side, odds, assumed):
    hs, as_ = g["home_score"], g["away_score"]
    line = None if market == "win" else (g["spread_line"] if market == "cover" else g["total_line"])
    out = grade(market, side, line, hs, as_)
    if market == "win":
        out_half = out
    else:
        worse = 0.5 if side in ("home", "over") else -0.5
        out_half = grade(market, side, line + worse, hs, as_)
    o10 = worse_cents(odds)
    return {"game_id": g["game_id"], "season": g["season"], "week": g["week"],
            "market": market, "side": side, "line": line, "odds": odds,
            "price_assumed": assumed, "p_model": p_side, "p_fair": fair_side,
            "edge": p_side - fair_side, "outcome": out,
            "profit_listed": settle(out, odds), "profit_minus_10c": settle(out, o10),
            "outcome_minus_half_point": out_half,
            "profit_minus_half_point": settle(out_half, odds),
            "profit_both": settle(out_half, o10),
            "breakeven": implied(odds), "quality_flag": flagged_quality(g) or g["game_id"] in ISSUE34_GAMES}


def walk_forward(games, feats, cfg):
    mcfg, wcfg = cfg["models"], cfg["walk_forward"]
    lam, iters, tol = float(mcfg["l2_lambda"]), int(mcfg["max_iter"]), float(mcfg["tol"])
    starts = {"win": 2006, "cover": 2002, "over": 2002}
    thresholds = sorted(set([cfg["selection"]["primary_edge_threshold"]] +
                            cfg["selection"]["sensitivity_thresholds_reported_not_chosen"]))
    preds, bets, coefs = [], {th: [] for th in thresholds}, {}
    for S in wcfg["test_seasons"]:
        for market in ("win", "cover", "over"):
            names = mcfg[market]["features"]
            X, y = fit_rows(games, feats, market, names, starts[market], S - 1)
            w = fit_logistic(X, y, lam, iters, tol)
            coefs["%d_%s" % (S, market)] = {"n_fit": len(X), "fit_seasons": [starts[market], S - 1],
                                           "weights": dict(zip(["intercept"] + names, w))}
            for g in games:
                if g["season"] != S or not scored(g) or g["game_type"] not in BET_GAME_TYPES:
                    continue
                row = design_row(feats[g["game_id"]], names)
                pr = listed_prices(g, market)
                if row is None or pr is None:
                    continue
                p1 = predict(w, row)
                f1, f2 = devig(pr[0], pr[1])
                t = target(g, market)
                preds.append({"game_id": g["game_id"], "season": S, "week": g["week"],
                              "market": market, "p_model": p1, "p_fair": f1, "y": t,
                              "price_assumed": pr[2]})
                s1, s2 = market_sides(market)
                e1, e2 = p1 - f1, (1.0 - p1) - f2
                for th in thresholds:
                    if e1 >= e2 and e1 >= th and e1 > 0:
                        bets[th].append(make_bet(g, market, s1, p1, f1, pr[0], pr[2]))
                    elif e2 > e1 and e2 >= th and e2 > 0:
                        bets[th].append(make_bet(g, market, s2, 1.0 - p1, f2, pr[1], pr[2]))
    return preds, bets, coefs


# ---------------------------------------------------------------- metrics
def summarize_bets(bs):
    n = len(bs)
    w = sum(1 for b in bs if b["outcome"] == "win")
    l = sum(1 for b in bs if b["outcome"] == "loss")
    p = n - w - l
    d = {"bets": n, "wins": w, "losses": l, "pushes": p,
         "price_assumed": sum(1 for b in bs if b["price_assumed"])}
    if n == 0:
        return d
    be = sum(b["breakeven"] for b in bs) / n
    wr = w / (w + l) if (w + l) else None
    d.update({"win_rate_ex_push": wr, "avg_breakeven_win_rate": be,
              "win_rate_minus_breakeven": (wr - be) if wr is not None else None,
              "roi_listed": sum(b["profit_listed"] for b in bs) / n,
              "roi_stress_minus_10c": sum(b["profit_minus_10c"] for b in bs) / n,
              "roi_stress_minus_half_point": sum(b["profit_minus_half_point"] for b in bs) / n,
              "roi_stress_both": sum(b["profit_both"] for b in bs) / n,
              "avg_edge_vs_fair": sum(b["edge"] for b in bs) / n})
    return d


def _ll(p, y):
    p = min(max(p, 1e-12), 1 - 1e-12)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def summarize_preds(ps):
    ps = [r for r in ps if r["y"] is not None]
    n = len(ps)
    if n == 0:
        return {"games": 0}
    llm = sum(_ll(r["p_model"], r["y"]) for r in ps) / n
    llk = sum(_ll(r["p_fair"], r["y"]) for r in ps) / n
    brm = sum((r["p_model"] - r["y"]) ** 2 for r in ps) / n
    brk = sum((r["p_fair"] - r["y"]) ** 2 for r in ps) / n
    return {"games": n, "logloss_model": llm, "logloss_market": llk, "logloss_diff_model_minus_market": llm - llk,
            "brier_model": brm, "brier_market": brk, "brier_diff_model_minus_market": brm - brk,
            "mean_abs_model_minus_market": sum(abs(r["p_model"] - r["p_fair"]) for r in ps) / n}


def bootstrap_samples(n_blocks, reps, seed):
    """Resampled block indices, drawn once so every CI uses the same draws."""
    rng = random.Random(seed)
    return [[rng.randrange(n_blocks) for _ in range(n_blocks)] for _ in range(reps)]


def block_bootstrap(items, value_fn, blocks, samples):
    """95% percentile CI of sum(value)/count over resampled (season, week) blocks."""
    idx = {b: i for i, b in enumerate(blocks)}
    sums, cnts = [0.0] * len(blocks), [0] * len(blocks)
    for it in items:
        i = idx.get((it["season"], it["week"]))
        if i is not None:
            sums[i] += value_fn(it)
            cnts[i] += 1
    stats = []
    for draw in samples:
        s = sum(sums[i] for i in draw)
        c = sum(cnts[i] for i in draw)
        if c:
            stats.append(s / c)
    stats.sort()
    if not stats:
        return None
    lo = stats[int(0.025 * (len(stats) - 1))]
    hi = stats[int(math.ceil(0.975 * (len(stats) - 1)))]
    return [lo, hi]


def _round(o):
    if isinstance(o, float):
        return round(o, 6)
    if isinstance(o, dict):
        return {k: _round(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_round(v) for v in o]
    return o


def baselines(games, seasons):
    """Naive bet-every-game strategies at listed prices (report context, not selection)."""
    def run(market, pick):
        bs = []
        for g in games:
            if g["season"] not in seasons or not scored(g) or g["game_type"] not in BET_GAME_TYPES:
                continue
            pr = listed_prices(g, market)
            if pr is None:
                continue
            side = pick(g)
            if side is None:
                continue
            s1, _ = market_sides(market)
            odds = pr[0] if side == s1 else pr[1]
            f1, f2 = devig(pr[0], pr[1])
            bs.append(make_bet(g, market, side, 0.0, f1 if side == s1 else f2, odds, pr[2]))
        d = summarize_bets(bs)
        return {k: d.get(k) for k in ("bets", "win_rate_ex_push", "avg_breakeven_win_rate", "roi_listed")}

    def ml_fav(g):
        h, a = implied(g["ml_home"]), implied(g["ml_away"])
        return None if h == a else ("home" if h > a else "away")

    def sp_fav(g):
        s = g["spread_line"]
        return None if not s else ("home" if s > 0 else "away")

    flip = {"home": "away", "away": "home", None: None}
    return {
        "win_home": run("win", lambda g: "home"), "win_away": run("win", lambda g: "away"),
        "win_favorite": run("win", ml_fav), "win_underdog": run("win", lambda g: flip[ml_fav(g)]),
        "cover_home": run("cover", lambda g: "home"), "cover_away": run("cover", lambda g: "away"),
        "cover_favorite": run("cover", sp_fav), "cover_underdog": run("cover", lambda g: flip[sp_fav(g)]),
        "over_all": run("over", lambda g: "over"), "under_all": run("over", lambda g: "under"),
    }


def side_breakdown(bs):
    out = {}
    for b in bs:
        key = b["side"]
        if b["market"] in ("win", "cover") and b["line"] is not None:
            fav_home = b["line"] > 0
            key += "_favorite" if (b["side"] == "home") == fav_home and b["line"] != 0 else "_underdog_or_pk"
        elif b["market"] == "win":
            key += "_favorite" if b["breakeven"] > 0.5 else "_underdog_or_pk"
        out.setdefault(key, []).append(b)
    return {k: {kk: summarize_bets(v).get(kk) for kk in ("bets", "roi_listed")} for k, v in sorted(out.items())}


def summarize(games, cfg, preds, bets, coefs, exclude=()):
    if exclude:
        bad = set(exclude)
        preds = [p for p in preds if p["game_id"] not in bad]
        bets = {th: [b for b in bs if b["game_id"] not in bad] for th, bs in bets.items()}
    th0 = cfg["selection"]["primary_edge_threshold"]
    seasons = cfg["walk_forward"]["test_seasons"]
    pooled = [s for s in seasons if s <= 2025]
    bcfg = cfg["metrics"]["bootstrap"]
    reps, seed = 2000, 20261115
    if "2000 resamples" not in bcfg or "seed 20261115" not in bcfg:
        raise Refused("BOOTSTRAP_CONFIG_CHANGED")
    blocks = sorted(set((g["season"], g["week"]) for g in games
                        if g["season"] in pooled and scored(g) and g["game_type"] in BET_GAME_TYPES))
    samples = bootstrap_samples(len(blocks), reps, seed)
    out = {"markets": {}, "bootstrap_blocks": len(blocks)}
    for m in ("win", "cover", "over"):
        mb = [b for b in bets[th0] if b["market"] == m]
        mp = [p for p in preds if p["market"] == m]
        per = {}
        for s in seasons:
            per[str(s)] = {"bets": summarize_bets([b for b in mb if b["season"] == s]),
                           "calibration": summarize_preds([p for p in mp if p["season"] == s])}
        pb = [b for b in mb if b["season"] in pooled]
        pp = [p for p in mp if p["season"] in pooled and p["y"] is not None]
        pooled_d = {"bets": summarize_bets(pb), "calibration": summarize_preds(pp),
                    "ci95_roi_listed": block_bootstrap(pb, lambda b: b["profit_listed"], blocks, samples),
                    "ci95_roi_stress_both": block_bootstrap(pb, lambda b: b["profit_both"], blocks, samples),
                    "ci95_logloss_diff": block_bootstrap(
                        pp, lambda p: _ll(p["p_model"], p["y"]) - _ll(p["p_fair"], p["y"]), blocks, samples),
                    "side_breakdown": side_breakdown(pb)}
        sens = {}
        for th, bs in sorted(bets.items()):
            sb = [b for b in bs if b["market"] == m and b["season"] in pooled]
            sens["%.2f" % th] = summarize_bets(sb)
            sens["%.2f" % th]["ci95_roi_listed"] = block_bootstrap(
                sb, lambda b: b["profit_listed"], blocks, samples)
        roi_ci, ll_ci = pooled_d["ci95_roi_listed"], pooled_d["ci95_logloss_diff"]
        passes = bool(roi_ci and roi_ci[0] > 0 and ll_ci and ll_ci[1] < 0)
        out["markets"][m] = {"per_season": per, "pooled_2012_2025": pooled_d,
                             "season_2026_to_date": per.get("2026"),
                             "all_seasons_incl_2026": {"bets": summarize_bets(mb),
                                                       "calibration": summarize_preds(mp)},
                             "sensitivity_thresholds_pooled_2012_2025": sens,
                             "verdict_rule_pass": passes}
    n_pass = sum(1 for m in out["markets"].values() if m["verdict_rule_pass"])
    if n_pass == 0:
        out["verdict"] = "no demonstrated out-of-sample edge"
    elif n_pass == 1:
        out["verdict"] = "not established: a lone pass among 3 markets tested"
    else:
        out["verdict"] = "paper edge by the pre-registered rule in %d markets (not a real-money edge)" % n_pass
    out["coefficients"] = coefs
    return _round(out), bets[th0]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "results"))
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args(argv)
    cfg = json.load(open(PREREG))
    prereg_sha = sha256_file(PREREG)
    games = load_games(DATA, cfg["data"]["sha256"])
    feats = compute_features(games, cfg)
    preds, bets, coefs = walk_forward(games, feats, cfg)
    res, primary_bets = summarize(games, cfg, preds, bets, coefs)
    flagged = sorted(g["game_id"] for g in games if flagged_quality(g))
    res_q, _ = summarize(games, cfg, preds, bets, coefs, exclude=flagged + list(ISSUE34_GAMES))
    results = {
        "paper_only": True,
        "data_sha256": cfg["data"]["sha256"],
        "prereg_sha256": prereg_sha,
        "code_sha256": sha256_file(os.path.abspath(__file__)),
        "games_in_file": len(games),
        "data_quality": {"spread_sign_vs_moneyline_flagged": flagged,
                         "issue34_games": list(ISSUE34_GAMES),
                         "odds_missing_by_season": {
                             str(s): sum(1 for g in games if g["season"] == s and scored(g)
                                         and listed_prices(g, "win") is None)
                             for s in sorted(set(g["season"] for g in games))}},
        "primary": res,
        "baselines_bet_every_game_pooled_2012_2025": _round(baselines(
            games, [x for x in cfg["walk_forward"]["test_seasons"] if x <= 2025])),
        "sensitivity_excluding_quality_flagged": {
            m: {"pooled_2012_2025": res_q["markets"][m]["pooled_2012_2025"]["bets"],
                "ci95_roi_listed": res_q["markets"][m]["pooled_2012_2025"]["ci95_roi_listed"]}
            for m in ("win", "cover", "over")},
    }
    os.makedirs(args.out, exist_ok=True)
    rpath = os.path.join(args.out, "walkforward_results.json")
    with open(rpath, "w") as fh:
        fh.write(json.dumps(results, indent=1, sort_keys=True) + "\n")
    cols = ["game_id", "season", "week", "market", "side", "line", "odds", "price_assumed",
            "p_model", "p_fair", "edge", "outcome", "profit_listed", "profit_minus_10c",
            "outcome_minus_half_point", "profit_minus_half_point", "profit_both", "quality_flag"]
    with open(os.path.join(args.out, "bets_primary.csv"), "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(cols)
        for b in primary_bets:
            wr.writerow([round(b[c], 6) if isinstance(b[c], float) else b[c] for c in cols])
    if not args.no_log:
        line = {"event": "run", "utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "prereg_sha256": prereg_sha, "results_sha256": sha256_file(rpath),
                "code_sha256": results["code_sha256"], "verdict": res["verdict"]}
        with open(os.path.join(HERE, "RUN_LOG.jsonl"), "a") as fh:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
    print("verdict:", res["verdict"])
    for m in ("win", "cover", "over"):
        pb = res["markets"][m]["pooled_2012_2025"]
        b, c = pb["bets"], pb["calibration"]
        print("%-5s bets=%-5s roi=%-9s ci=%s ll_diff=%s ci=%s" % (
            m, b.get("bets"), b.get("roi_listed"), pb["ci95_roi_listed"],
            c.get("logloss_diff_model_minus_market"), pb["ci95_logloss_diff"]))
    print("wrote", rpath)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refused as e:
        print("REFUSED:", e)
        sys.exit(2)
