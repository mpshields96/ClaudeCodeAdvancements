#!/usr/bin/env python3
"""Sunday NFL cross-market picker (advisory, code-only, past-only).

Standard library only, Python 3.9 compatible. Run with:
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B picker.py <command>

Commands
  backtest  walk-forward past-only test against the market, writes PAST_ONLY_TEST.md
  freeze    record this file's sha256 and the parameters in frozen_picker.json
  slate     compare exact contracts and issue zero to two selections in each Chicago window
  grade     grade every recorded candidate against observed final scores

What the number means
  Market likelihood describes two-sided prices for the exact contract. The
  independent football estimate is shown separately where one exists. Release
  reviewers can document a different pregame judgment at a stated price floor.

Foreknowledge boundary
  Ratings are built only from games dated before the slate date. A slate
  game's final_score field is never read for scoring. Every prediction in the
  backtest is made before that game's result updates the ratings.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import csv
import datetime
import hashlib
import html
import json
import math
import os
import re
import itertools
from pathlib import Path
from tempfile import NamedTemporaryFile

HERE = os.path.dirname(os.path.abspath(__file__))
LANE = os.path.dirname(HERE)
SPRINT = os.path.dirname(LANE)
sys.path.append(LANE)          # appended, so the standard library always wins
sys.path.append(HERE)
import selection_markets as markets
import selection_decisions as decisions
import rules as lane_rules     # noqa: E402  (grading shared with the ledger)

SLATE_DATE = "2026-11-15"
TIMEZONE = "America/Chicago"
EXPECTED_SUNDAY_GAMES = 12

# Fixed before any slate game was scored. One variant, no search on these.
PARAMS = {
    "elo_k": 20.0,
    "elo_hfa": 48.0,
    "elo_mean": 1505.0,
    "elo_season_regress": 1.0 / 3.0,
    "elo_points_per_point": 25.0,
    "pts_alpha": 0.05,
    "pts_season_regress": 0.4,
    "pts_hfa": 2.0,
    "mu_alpha": 0.01,
    "mu_start": 21.5,
    "margin_mix_elo": 0.5,
    "blend_grid": [0.0, 0.25, 0.5, 0.75, 0.9, 1.0],
    "tune_seasons": [2010, 2022],
    "test_a_seasons": [2023, 2025],
    "test_b_seasons": [2026, 2026],
    "edge_points_threshold": 3.0,
    "test_b_weeks": [1, 9],
}

SELECTION_RULE = (
    "At the best available in-band price (-200 to +200), calculate the median, "
    "margin-removed probability at other books quoting both sides of the exact contract. "
    "The provisional screen chooses at most one per Chicago window, highest market probability "
    "first, when at least two other books support the comparison and the independent full-game "
    "football estimate and the market both favor the same side above 50%. "
    "Tie-break by stable contract ID. A pregame release reviewer can select zero to two per window from distinct games "
    "across all supported markets with a sourced football rationale, price floor and contrary case. "
    "An estimated return or closing-line movement is contextual, never a selection requirement."
)

HYPOTHESIS = (
    "Pregame football review plus exact-line shopping may improve prospective one-unit net return "
    "over a frozen highest-probability in-band moneyline control per window. Track hit rate, pushes, "
    "price and one-unit return separately. Record every pass and retain the same controls even if the "
    "reviewer abstains. Grade reviewed picks, the provisional screen and controls as separate groups. "
    "Where independent probabilities exist, score their Brier loss against the same-contract market. "
    "One Sunday is insufficient to establish an edge."
)

ABBR = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Los Angeles Rams": "LA", "Los Angeles Chargers": "LAC",
    "Las Vegas Raiders": "LV", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "Seattle Seahawks": "SEA", "San Francisco 49ers": "SF", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}
FRANCHISE = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


# ---------------------------------------------------------------- helpers

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fnum(x):
    if x is None:
        return None
    x = str(x).strip()
    if x == "" or x.upper() == "NA":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def implied(american):
    """Raw implied probability of an American price (also the break-even)."""
    a = float(american)
    if a == 0:
        raise ValueError("price 0 is not a valid American price")
    return 100.0 / (a + 100.0) if a > 0 else (-a) / ((-a) + 100.0)


def novig(price_a, price_b):
    """Two prices at the same line -> (p_a, p_b, book_margin)."""
    ia, ib = implied(price_a), implied(price_b)
    s = ia + ib
    return ia / s, ib / s, s - 1.0


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def clip(p):
    return min(max(p, 1e-6), 1.0 - 1e-6)


def logit(p):
    p = clip(p)
    return math.log(p / (1.0 - p))


def expit(x):
    return 1.0 / (1.0 + math.exp(-x))


def fmt_price(a):
    a = int(round(float(a)))
    return "+%d" % a if a > 0 else "%d" % a


def pct(x, d=1):
    return "%.*f%%" % (d, 100.0 * x)


def parse_kickoff(s):
    s = s.strip().replace("Z", "+0000")
    for fmt in ("%Y-%m-%dT%H:%M%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError("bad kickoff time: %r" % s)


def local_time(dt):
    """Kickoff in America/Chicago. Returns (date string, label, tz note)."""
    try:
        from zoneinfo import ZoneInfo
        loc = dt.astimezone(ZoneInfo(TIMEZONE))
        note = TIMEZONE
    except Exception:
        loc = dt.astimezone(datetime.timezone(datetime.timedelta(hours=-6)))
        note = "fixed UTC-6 (zone database not available)"
    hour = loc.hour % 12 or 12
    label = "%d:%02d %s" % (hour, loc.minute, "a.m." if loc.hour < 12 else "p.m.")
    return loc.strftime("%Y-%m-%d"), label, note


# ---------------------------------------------------------------- history

def load_games(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append({
            "game_id": r["game_id"], "season": int(r["season"]), "week": int(r["week"]),
            "game_type": r["game_type"], "gameday": r["gameday"],
            "gametime": r.get("gametime", ""), "weekday": r.get("weekday", ""),
            "away": FRANCHISE.get(r["away_team"], r["away_team"]),
            "home": FRANCHISE.get(r["home_team"], r["home_team"]),
            "away_score": fnum(r["away_score"]), "home_score": fnum(r["home_score"]),
            "location": r.get("location", ""),
            "away_ml": fnum(r.get("away_moneyline")), "home_ml": fnum(r.get("home_moneyline")),
            "spread_line": fnum(r.get("spread_line")), "total_line": fnum(r.get("total_line")),
            "away_rest": fnum(r.get("away_rest")), "home_rest": fnum(r.get("home_rest")),
        })
    out.sort(key=lambda g: (g["gameday"], g["gametime"], g["game_id"]))
    return out


def new_state(P):
    return {"elo": {}, "off": {}, "def": {}, "mu": P["mu_start"], "season": None}


def _roll_season(st, season, P):
    if st["season"] is not None and season != st["season"]:
        for t in st["elo"]:
            st["elo"][t] = P["elo_mean"] + (st["elo"][t] - P["elo_mean"]) * (1.0 - P["elo_season_regress"])
        for t in st["off"]:
            st["off"][t] *= (1.0 - P["pts_season_regress"])
            st["def"][t] *= (1.0 - P["pts_season_regress"])
    st["season"] = season


def _get(st, team, P):
    if team not in st["elo"]:
        st["elo"][team] = P["elo_mean"]
        st["off"][team] = 0.0
        st["def"][team] = 0.0


def predict(st, home, away, location, P):
    """Pre-game numbers from the ratings as they stand. Reads no result."""
    _get(st, home, P)
    _get(st, away, P)
    at_home = (location == "Home")
    diff = st["elo"][home] - st["elo"][away] + (P["elo_hfa"] if at_home else 0.0)
    p_home = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
    hfa = P["pts_hfa"] if at_home else 0.0
    home_pts = st["mu"] + st["off"][home] + st["def"][away] + hfa / 2.0
    away_pts = st["mu"] + st["off"][away] + st["def"][home] - hfa / 2.0
    elo_margin = diff / P["elo_points_per_point"]
    pts_margin = home_pts - away_pts
    mix = P["margin_mix_elo"]
    return {
        "p_home": p_home, "elo_diff": diff, "elo_margin": elo_margin,
        "pts_margin": pts_margin, "margin": mix * elo_margin + (1.0 - mix) * pts_margin,
        "home_pts": home_pts, "away_pts": away_pts, "total": home_pts + away_pts,
    }


def update(st, g, pr, P):
    hs, as_ = g["home_score"], g["away_score"]
    m = hs - as_
    s = 1.0 if m > 0 else (0.0 if m < 0 else 0.5)
    if m == 0:
        mult = 1.0
    else:
        winner_diff = pr["elo_diff"] if m > 0 else -pr["elo_diff"]
        mult = math.log(abs(m) + 1.0) * 2.2 / (winner_diff * 0.001 + 2.2)
    delta = P["elo_k"] * mult * (s - pr["p_home"])
    st["elo"][g["home"]] += delta
    st["elo"][g["away"]] -= delta
    rh = hs - pr["home_pts"]
    ra = as_ - pr["away_pts"]
    a = P["pts_alpha"]
    st["off"][g["home"]] += a * rh
    st["def"][g["away"]] += a * rh
    st["off"][g["away"]] += a * ra
    st["def"][g["home"]] += a * ra
    st["mu"] += P["mu_alpha"] * ((hs + as_) / 2.0 - st["mu"])


def walk(games, P, cutoff):
    """Past-only pass over completed games dated before `cutoff`."""
    st = new_state(P)
    preds = []
    # Results from games played later that day cannot inform a simultaneous kickoff.
    completed = (g for g in games if g["gameday"] < cutoff and None not in (g["home_score"], g["away_score"]))
    for _, day_games in itertools.groupby(completed, key=lambda g: g["gameday"]):
        day = []
        for g in day_games:
            _roll_season(st, g["season"], P)
            pr = predict(st, g["home"], g["away"], g["location"], P)
            pr["game"] = g
            day.append(pr)
        preds.extend(day)
        for pr in day:
            update(st, pr["game"], pr, P)
    return preds, st


# ---------------------------------------------------------------- past-only test

def _win(preds, lo_hi):
    lo, hi = lo_hi
    return [p for p in preds if lo <= p["game"]["season"] <= hi]


def _prob_rows(preds):
    rows = []
    for p in preds:
        g = p["game"]
        if g["home_ml"] is None or g["away_ml"] is None:
            continue
        if g["home_score"] == g["away_score"]:
            continue
        pm = novig(g["home_ml"], g["away_ml"])[0]
        rows.append((pm, p["p_home"], 1.0 if g["home_score"] > g["away_score"] else 0.0))
    return rows


def _scores(rows, w):
    """w is the weight on the market in logit space. Returns (log loss, Brier, n)."""
    if not rows:
        return None, None, 0
    ll = 0.0
    br = 0.0
    for pm, pmod, y in rows:
        p = clip(expit(w * logit(pm) + (1.0 - w) * logit(pmod)))
        ll += -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))
        br += (p - y) ** 2
    n = len(rows)
    return ll / n, br / n, n


def _side_test(preds, market, thr):
    """Model side against the posted line. Returns counts for all and for big edges."""
    out = {"all": {"w": 0, "l": 0, "p": 0}, "edge": {"w": 0, "l": 0, "p": 0}}
    for p in preds:
        g = p["game"]
        if market == "spread":
            line = g["spread_line"]
            if line is None:
                continue
            edge = p["margin"] - line
            side = "home" if edge > 0 else "away"
        else:
            line = g["total_line"]
            if line is None:
                continue
            edge = p["total"] - line
            side = "over" if edge > 0 else "under"
        if edge == 0:
            continue
        res = lane_rules.grade(market, side, line, g["home_score"], g["away_score"])
        key = {"win": "w", "loss": "l", "push": "p"}[res]
        out["all"][key] += 1
        if abs(edge) >= thr:
            out["edge"][key] += 1
    return out


def _top2(preds, by):
    """Two most likely moneyline sides on each regular-season Sunday slate."""
    slates = {}
    for p in preds:
        g = p["game"]
        if g["game_type"] != "REG" or g["weekday"] != "Sunday":
            continue
        if g["home_ml"] is None or g["away_ml"] is None:
            continue
        pm = novig(g["home_ml"], g["away_ml"])[0]
        ph = pm if by == "market" else p["p_home"]
        side = "home" if ph >= 0.5 else "away"
        prob = ph if side == "home" else 1.0 - ph
        price = g["home_ml"] if side == "home" else g["away_ml"]
        slates.setdefault((g["season"], g["week"]), []).append((prob, g["game_id"], side, price, g))
    out = {"slates": 0, "bets": 0, "w": 0, "l": 0, "p": 0, "profit": 0.0, "both": 0}
    for key in sorted(slates):
        cand = sorted(slates[key], key=lambda c: (-c[0], c[1]))[:2]
        if len(cand) < 2:
            continue
        out["slates"] += 1
        wins = 0
        for prob, gid, side, price, g in cand:
            res = lane_rules.grade("moneyline", side, None, g["home_score"], g["away_score"])
            out["bets"] += 1
            if res == "win":
                out["w"] += 1
                wins += 1
                out["profit"] += lane_rules.american_profit(price)
            elif res == "loss":
                out["l"] += 1
                out["profit"] -= 1.0
            else:
                out["p"] += 1
        if wins == 2:
            out["both"] += 1
    return out


def _calibration(preds):
    edges = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]
    buckets = [{"lo": edges[i], "hi": edges[i + 1], "n": 0, "sum_p": 0.0, "wins": 0} for i in range(5)]
    for p in preds:
        g = p["game"]
        if g["home_ml"] is None or g["away_ml"] is None or g["home_score"] == g["away_score"]:
            continue
        pm = novig(g["home_ml"], g["away_ml"])[0]
        fav_home = pm >= 0.5
        pf = pm if fav_home else 1.0 - pm
        won = (g["home_score"] > g["away_score"]) == fav_home
        for b in buckets:
            if b["lo"] <= pf < b["hi"]:
                b["n"] += 1
                b["sum_p"] += pf
                b["wins"] += 1 if won else 0
                break
    return buckets


def past_only_test(games, P, cutoff):
    preds, st = walk(games, P, cutoff)
    tune = _win(preds, P["tune_seasons"])
    res = {"cutoff": cutoff, "n_predictions": len(preds), "windows": {}, "grid": []}
    tune_rows = _prob_rows(tune)
    best_w, best_ll = None, None
    for w in P["blend_grid"]:
        ll, br, n = _scores(tune_rows, w)
        res["grid"].append({"market_weight": w, "log_loss": ll, "brier": br, "n": n})
        if best_ll is None or ll < best_ll - 1e-12 or (abs(ll - best_ll) <= 1e-12 and w > best_w):
            best_w, best_ll = w, ll
    res["best_market_weight_on_tune"] = best_w
    sq_m = [(p["game"]["home_score"] - p["game"]["away_score"] - p["margin"]) ** 2 for p in tune]
    sq_t = [(p["game"]["home_score"] + p["game"]["away_score"] - p["total"]) ** 2 for p in tune]
    res["sd_margin"] = math.sqrt(sum(sq_m) / len(sq_m))
    res["sd_total"] = math.sqrt(sum(sq_t) / len(sq_t))
    beats = []
    for name, key in (("tune", "tune_seasons"), ("test_a", "test_a_seasons"), ("test_b", "test_b_seasons")):
        wp = _win(preds, P[key])
        if name == "test_b":
            first, last = P["test_b_weeks"]
            wp = [p for p in wp if p["game"]["game_type"] == "REG" and first <= p["game"]["week"] <= last]
        rows = _prob_rows(wp)
        mk = _scores(rows, 1.0)
        md = _scores(rows, 0.0)
        bl = _scores(rows, best_w)
        thr = P["edge_points_threshold"]
        res["windows"][name] = {
            "seasons": P[key], "weeks": P["test_b_weeks"] if name == "test_b" else None,
            "weeks_included": sorted({p["game"]["week"] for p in wp}), "n_games": len(wp), "n_priced": mk[2],
            "market": {"log_loss": mk[0], "brier": mk[1]},
            "model": {"log_loss": md[0], "brier": md[1]},
            "blend": {"log_loss": bl[0], "brier": bl[1], "market_weight": best_w},
            "spread": _side_test(wp, "spread", thr), "total": _side_test(wp, "total", thr),
            "top2_market": _top2(wp, "market"), "top2_model": _top2(wp, "model"),
        }
        if name != "tune":
            beats.append(mk[0] is not None and bl[0] < mk[0] - 1e-9)
    res["blend_beats_market_in_both_tests"] = bool(best_w < 1.0 and all(beats))
    res["likelihood_basis"] = "blend" if res["blend_beats_market_in_both_tests"] else "market"
    res["calibration_2010_on"] = _calibration([p for p in preds if p["game"]["season"] >= 2010 and (p["game"]["season"] < 2026 or p["game"]["week"] <= 9)])
    return res, preds, st


def _rate(c):
    n = c["w"] + c["l"]
    return ("%d-%d-%d, %s" % (c["w"], c["l"], c["p"], pct(c["w"] / n))) if n else "none"


def past_only_blocks(res):
    W = res["windows"]
    names = [("tune", "Tuning seasons %d-%d" % tuple(W["tune"]["seasons"])),
             ("test_a", "Held out %d-%d" % tuple(W["test_a"]["seasons"])),
             ("test_b", "Held out %d (completed regular-season weeks 1-9)" % W["test_b"]["seasons"][0])]
    b = [("h1", "Past-only test of the Sunday picker"),
         ("p", "Every prediction here was made from games played before the game being scored. "
               "The model's settings were fixed in advance and were not searched. The only fitted "
               "value is the market weight in the blend, chosen on the tuning seasons alone. "
               "The 2023-2025 seasons are a longer historical comparison. The 2026 test covers "
               "completed regular-season weeks 1-9. Thursday of Week 10 is excluded from that test."),
         ("h2", "Who predicts winners better: the market or the model?"),
         ("p", "Log loss and Brier score on every two-sided priced, decided moneyline game. Ties are excluded. Lower is better."),
         ("table", ["Window", "Games", "Market log loss", "Model log loss", "Blend log loss", "Market Brier", "Model Brier", "Blend Brier"],
          [[lab, str(W[k]["n_priced"]), "%.4f" % W[k]["market"]["log_loss"], "%.4f" % W[k]["model"]["log_loss"],
            "%.4f" % W[k]["blend"]["log_loss"], "%.4f" % W[k]["market"]["brier"], "%.4f" % W[k]["model"]["brier"],
            "%.4f" % W[k]["blend"]["brier"]] for k, lab in names]),
         ("p", "Market weight chosen on the tuning seasons: **%.2f** (1.00 means the market alone). "
               "Six weights were tried, all counted: %s." % (
                   res["best_market_weight_on_tune"],
                   ", ".join("%.2f gives %.4f" % (g["market_weight"], g["log_loss"]) for g in res["grid"]))),
         ("p", "**Result: %s**" % (
             "the blend beat the market in both held-out windows, so the hit likelihood uses the blend."
             if res["blend_beats_market_in_both_tests"] else
             "the model does not beat the market in both held-out windows. Every hit likelihood on the "
             "picks page uses a stated market reference when available.")),
         ("h2", "Does the model beat the posted spread or total?"),
         ("p", "The model takes the side its number favours against the posted line. Break-even at -110 is 52.4%%. "
               "Record is wins-losses-pushes; the rate leaves pushes out. A big edge is %g points or more."
               % PARAMS["edge_points_threshold"]),
         ("table", ["Window", "Spread, all games", "Spread, big edge", "Total, all games", "Total, big edge"],
          [[lab, _rate(W[k]["spread"]["all"]), _rate(W[k]["spread"]["edge"]),
            _rate(W[k]["total"]["all"]), _rate(W[k]["total"]["edge"])] for k, lab in names]),
         ("h2", "What picking the two most likely winners each Sunday did"),
         ("p", "Historical unrestricted benchmark across each Sunday: take the two most likely "
               "moneyline sides. Return is profit per unit risked at the archive price. Archive quote times are unknown. "
               "The 2026 sample covers nine Sundays, too few to judge the rule."),
         ("table", ["Window", "Ranked by", "Sundays", "Record", "Both won", "Return per unit"],
          [r for k, lab in names for r in (
              [lab, "market price", str(W[k]["top2_market"]["slates"]), _rate(W[k]["top2_market"]),
               "%d of %d" % (W[k]["top2_market"]["both"], W[k]["top2_market"]["slates"]),
               ("%+.2f%%" % (100.0 * W[k]["top2_market"]["profit"] / W[k]["top2_market"]["bets"])) if W[k]["top2_market"]["bets"] else "none"],
              [lab, "model rating", str(W[k]["top2_model"]["slates"]), _rate(W[k]["top2_model"]),
               "%d of %d" % (W[k]["top2_model"]["both"], W[k]["top2_model"]["slates"]),
               ("%+.2f%%" % (100.0 * W[k]["top2_model"]["profit"] / W[k]["top2_model"]["bets"])) if W[k]["top2_model"]["bets"] else "none"])]),
         ("h2", "Is the market's favourite price honest?"),
         ("p", "All priced, decided games from 2010 through completed 2026 Week 9. If the market says 80%, favourites in that band should win about 80% of the time."),
         ("table", ["Market says", "Games", "Average stated chance", "Favourites actually won"],
          [["%d%% to %d%%" % (round(100 * x["lo"]), min(100, round(100 * x["hi"]))), str(x["n"]),
            pct(x["sum_p"] / x["n"]) if x["n"] else "none", pct(x["wins"] / float(x["n"])) if x["n"] else "none"]
           for x in res["calibration_2010_on"]]),
         ("h2", "Limits of this test"),
         ("ul", ["The archive prices carry no quote time. They are probably near closing prices, which are sharper than a price seen the night before.",
                 "No injury history is in the test. Health is shown on the picks page as context and is not in any number.",
                 "Player props have no history here, so no prop number is tested.",
                 "A good record over all games does not prove the two selected bets will win. The historical two-pick table has no price band or time windows and does not validate Sunday's cross-market process.",
                 "Model residual spread used for cover and over chances: margin %.2f points, total %.2f points (tuning seasons)." % (res["sd_margin"], res["sd_total"])])]
    return b


# ---------------------------------------------------------------- rendering

def _inline_html(t):
    t = html.escape(t, quote=True)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', t)
    return t


def render_md(blocks):
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h1":
            out.append("# " + b[1])
        elif kind == "h2":
            out.append("## " + b[1])
        elif kind == "p":
            out.append(b[1])
        elif kind == "ul":
            out.append("\n".join("- " + i for i in b[1]))
        elif kind == "table":
            head, rows = b[1], b[2]
            lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
            for r in rows:
                lines.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
            out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def render_html(title, blocks):
    css = ("body{background:#fcfaf6;color:#22262a;font-family:Charter,'Bitstream Charter',Georgia,serif;"
           "line-height:1.5;margin:0;padding:24px 16px}main{max-width:900px;margin:0 auto}"
           "h1,h2{color:#0e5e8a;line-height:1.2}h1{font-size:1.9rem}h2{font-size:1.3rem;margin-top:2rem}"
           "a{color:#0e5e8a}.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.92rem}"
           "th,td{border:1px solid #d9d2c3;padding:6px 8px;text-align:left;vertical-align:top}"
           "th{background:#f1ece0}strong{color:#0b4a6d}")
    out = ['<!doctype html>', '<html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           "<title>%s</title><style>%s</style></head><body><main>" % (html.escape(title), css)]
    for b in blocks:
        kind = b[0]
        if kind in ("h1", "h2"):
            out.append("<%s>%s</%s>" % (kind, _inline_html(b[1]), kind))
        elif kind == "p":
            out.append("<p>%s</p>" % _inline_html(b[1]))
        elif kind == "ul":
            out.append("<ul>" + "".join("<li>%s</li>" % _inline_html(i) for i in b[1]) + "</ul>")
        elif kind == "table":
            head, rows = b[1], b[2]
            t = ['<div class="wrap"><table><thead><tr>' + "".join("<th>%s</th>" % _inline_html(h) for h in head) + "</tr></thead><tbody>"]
            for r in rows:
                t.append("<tr>" + "".join("<td>%s</td>" % _inline_html(str(c)) for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
    out.append("</main></body></html>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- slate

def sunday_games(lines_doc):
    """Games whose kickoff falls on the slate date in America/Chicago."""
    out = []
    for g in lines_doc["games"]:
        dt = parse_kickoff(g["kickoff_utc"])
        day, label, note = local_time(dt)
        if day == SLATE_DATE:
            gg = dict(g)
            gg["_kick"] = dt
            gg["_local_label"] = label
            gg["_tz_note"] = note
            out.append(gg)
    out.sort(key=lambda g: (g["_kick"], g["event_id"]))
    return out


def team_form(games, team, season, cutoff):
    f = {"w": 0, "l": 0, "t": 0, "ats_w": 0, "ats_l": 0, "ats_p": 0, "over": 0, "under": 0, "ou_p": 0,
         "pf": 0.0, "pa": 0.0, "n": 0, "last": []}
    for g in games:
        if g["season"] != season or None in (g["home_score"],g["away_score"]) or g["gameday"] >= cutoff:
            continue
        if team not in (g["home"], g["away"]):
            continue
        is_home = g["home"] == team
        pf = g["home_score"] if is_home else g["away_score"]
        pa = g["away_score"] if is_home else g["home_score"]
        f["n"] += 1
        f["pf"] += pf
        f["pa"] += pa
        f["w" if pf > pa else ("l" if pf < pa else "t")] += 1
        if g["spread_line"] is not None:
            r = lane_rules.grade("spread", "home" if is_home else "away", g["spread_line"], g["home_score"], g["away_score"])
            f[{"win": "ats_w", "loss": "ats_l", "push": "ats_p"}[r]] += 1
        if g["total_line"] is not None:
            r = lane_rules.grade("total", "over", g["total_line"], g["home_score"], g["away_score"])
            f[{"win": "over", "loss": "under", "push": "ou_p"}[r]] += 1
        f.setdefault("game_log", []).append({"date":g["gameday"],"week":g["week"],"opponent":g["away"] if is_home else g["home"],
                                            "pf":pf,"pa":pa,"outcome":"W" if pf>pa else "L" if pf<pa else "T"})
        f["last"].append("%s %s %d-%d (wk %d)" % ("W" if pf > pa else ("L" if pf < pa else "T"),
                                                 ("vs " if is_home else "at ") + (g["away"] if is_home else g["home"]),
                                                 int(pf), int(pa), g["week"]))
    log = f.pop("game_log", [])
    f["recent"] = {}
    for cap in (5, 10):
        recent = log[-cap:]
        f["recent"]["last_%d" % cap] = {"requested":cap,"games":len(recent),
            "wins":sum(g["outcome"]=="W" for g in recent),"losses":sum(g["outcome"]=="L" for g in recent),
            "ties":sum(g["outcome"]=="T" for g in recent),"oldest_first":recent}
    f["last"] = f["last"][-4:]
    f["pf_per_game"] = f["pf"] / f["n"] if f["n"] else None
    f["pa_per_game"] = f["pa"] / f["n"] if f["n"] else None
    return f


def head_to_head(games, a, b, cutoff, n=5):
    out = []
    for g in games:
        if g["home_score"] is None or g["gameday"] >= cutoff:
            continue
        if {g["home"], g["away"]} == {a, b}:
            out.append({"season": g["season"], "week": g["week"], "away": g["away"], "home": g["home"],
                        "away_score": int(g["away_score"]), "home_score": int(g["home_score"])})
    return out[-n:]


def load_props(path):
    """Priced props only. A prop needs both sides at one threshold."""
    props, missing = [], []
    if not path or not os.path.exists(path):
        return props, ["no priced prop file"]
    doc = json.load(open(path))
    items = doc if isinstance(doc, list) else (doc.get("props") if isinstance(doc.get("props"), list) else [doc])
    for it in items:
        o, u, line = fnum(it.get("over_american_price")), fnum(it.get("under_american_price")), fnum(it.get("line"))
        name = "%s %s" % (it.get("player"), it.get("market"))
        if o is None or u is None or line is None:
            missing.append("%s: not priced on both sides at one threshold, not scored" % name)
            continue
        props.append({"event_id": str(it.get("event_espn_id")), "player": it.get("player"), "team": it.get("team"),
                      "market": it.get("market"), "line": line, "over_price": o, "under_price": u,
                      "book": it.get("book_reported"), "observed_utc": it.get("checked_utc"),
                      "source_url": it.get("source_url"), "book_update_utc": it.get("book_update_utc")})
    return props, missing


def game_context(games, sched_doc, health, st):
    schedule = {(g["away"], g["home"]): g for g in games if g["season"] == 2026 and g["gameday"] == SLATE_DATE}
    result = {}
    for g in sunday_games(sched_doc):
        away, home = (ABBR[g["teams"][s]] for s in ("away", "home"))
        row = schedule.get((away, home))
        if row is None:
            raise ValueError("Missing archive schedule match for " + g["name"])
        location = row["location"]
        if "neutral_site" in g and (location == "Neutral") != bool(g["neutral_site"]):
            raise ValueError("Inconsistent neutral venue for " + g["name"])
        pr = predict(st, home, away, location, PARAMS)
        statuses = (health or {}).get("team_status", {})
        eid = str(g["event_id"])
        if eid in result:
            raise ValueError("Repeated event in schedule")
        result[eid] = {
            "event_id": eid, "espn_event_id": g.get("espn_event_id", eid), "event_url": g.get("event_url"),
            "nflverse_game_id": row["game_id"], "game": "%s at %s" % (away, home), "name": g["name"],
            "kickoff_utc": g["kickoff_utc"], "kickoff_local": g["_local_label"], "window": markets.window(g["kickoff_utc"]),
            "venue": g.get("venue"), "location": location, "neutral": location == "Neutral",
            "eligible": g.get("state") in (None, "STATUS_SCHEDULED") and g.get("final_score") is None,
            "rest_days": {"away": row["away_rest"], "home": row["home_rest"]},
            "model": {"p_home_win": pr["p_home"], "total": pr["total"], "margin_home": pr["margin"],
                      "offense_points_vs_average": {"away": st["off"][away], "home": st["off"][home]},
                      "defense_points_allowed_vs_average": {"away": st["def"][away], "home": st["def"][home]}},
            "form_2026": {s: team_form(games, team, 2026, SLATE_DATE) for s, team in (("away", away), ("home", home))},
            "head_to_head_last5": head_to_head(games, away, home, SLATE_DATE),
            "health": {s: statuses.get(g["teams"][s].split()[-1].upper()) for s in ("away","home")},
            "injury_report_utc": (health or {}).get("captured_utc"), "injury_source": (health or {}).get("url"),
            "final_inactives_verified": False,
        }
    return result


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def snapshot_json(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), {"path": os.path.relpath(path, SPRINT), "sha256": hashlib.sha256(raw).hexdigest()}


def catalog_source(path):
    return _src(os.fspath(path)) if path and os.path.isfile(path) else None


def price_history(reference, gs, now):
    by_espn = {g["espn_event_id"]: g for g in gs.values()}
    rows, _, _ = markets.collect(None, reference, [], by_espn, now)
    return {r["id"]: r for r in rows}


def attach_context(a, inputs, games, candidates, capture_hash, now, first):
    """Add sourced football context. These joins never replace an offer or rewrite a decision."""
    notes = []
    team_path, prop_path = a.team_context, a.player_context
    by_espn = {g["espn_event_id"]: g for g in games.values()}
    if team_path and os.path.isfile(team_path):
        team_doc, inputs["team_context"] = snapshot_json(team_path)
        validate_context_time(team_doc, now, first)
        for info in team_doc.get("games", []):
            g = by_espn.get(str(info["event_id"]))
            if g is None:
                continue
            if (markets.instant(info["kickoff_utc"]) != markets.instant(g["kickoff_utc"])
                    or info.get("nflverse_game_id") != g["nflverse_game_id"] or info["neutral"] != g["neutral"]):
                raise ValueError("Team context disagrees on event, kickoff or neutral site")
            g["matchup_context"] = {k: info.get(k) for k in (
                "teams", "injuries", "h2h", "h2h_basis", "nflverse_context", "inactives_expected_utc",
                "inactives_label", "source_ids", "missing")}
        inputs["team_context"]["built_utc"] = team_doc.get("built_utc")
    else:
        notes.append("Expanded team and injury file unavailable. Archived team results and the earlier injury snapshot are shown.")
    prop_index = {}
    if prop_path and os.path.isfile(prop_path):
        prop_doc, inputs["player_context"] = snapshot_json(prop_path)
        validate_context_time(prop_doc, now, first)
        inputs["player_context"].update(built_utc=prop_doc["built_utc"],coverage=prop_doc.get("coverage"))
        if prop_doc.get("price_capture", {}).get("sha256") == capture_hash:
            for r in prop_doc.get("props", []) + prop_doc.get("excluded_props", []):
                key = (r["odds_event_id"], r["market"], r["player"], r["line"], r["book_key"])
                if key in prop_index:
                    raise ValueError("Duplicate player evidence for " + str(key))
                prop_index[key] = r
        else:
            notes.append("Player evidence belongs to another price capture. See the source record for its scope.")
    else:
        notes.append("The player history file was unavailable at build time.")
    for c in candidates:
        if c["market"] != "prop":
            continue
        key = (c["event_id"], c["provider_market"], c["subject"], c["line"], c["source"]["book"])
        record = prop_index.get(key)
        if record:
            form = record.get("player_form", {})
            c["player_evidence"] = {k: record.get(k) for k in (
                "team","official_player_name","player_identity_url","availability","eligible_for_form_review",
                "exclusion_reasons","historical_results_at_current_line")}
            c["player_evidence"].update(
                source_url=form.get("source_url"), retrieved_utc=form.get("retrieved_utc"),
                season_avg=form.get("season_avg"), season_games_played=form.get("season_games_played"),
                limitations=form.get("limitations", []), final_inactives_verified=False)
    return notes


def validate_context_time(doc, now, first_kick):
    built = markets.instant(doc["built_utc"])
    if built > markets.instant(now) or built >= markets.instant(first_kick):
        raise ValueError("Football evidence file is future-dated or built after kickoff")


def read_review_verdicts(prose):
    # Display only the reviewer's own verdict column. The market calculation remains in the price record.
    verdicts = []
    in_table = False
    for line in prose.splitlines():
        if not line.startswith("|"):
            if in_table:
                break
            continue
        cells = [v.strip() for v in line.strip().strip("|").split("|")]
        if cells and cells[0].startswith("Candidate") and cells[-1].startswith("Verdict"):
            in_table = True
        elif in_table and cells and any(ch.isalnum() for ch in cells[0]):
            verdicts.append([cells[0], cells[-1]])
    return verdicts


def health_summary(c, game):
    inactives = (game.get("matchup_context") or {}).get("inactives_expected_utc")
    if not inactives:
        inactives = (markets.instant(game["kickoff_utc"])-datetime.timedelta(minutes=90)).isoformat()
    player = c.get("player_evidence") or {}
    return {"official_inactives_verified":False, "inactives_expected_utc":inactives,
            "expected_time_basis":"estimate, 90 minutes before kickoff",
            "report_status":"known" if game.get("injury_report_utc") else "unknown",
            "report_retrieved_utc":game.get("injury_report_utc"), "report_url":game.get("injury_source"),
            "player_availability":player.get("availability"), "final_participation":"unknown"}


# Editorial context for this dated release. Each statement is bound to the exact
# archived official page; only reviewed calls citing that same URL receive it.
CLUB_SOURCES = {
    "chiefs-injury.20261115T072459Z": (
        "6ef05c5db667b991e832043d85a0b225fceedf799dc50fd9ac883014ff50c312",
        "Kansas City's Saturday report lists Kenneth Walker III, Jaylon Moore and Peter Woods out. "
        "Jaydn Ott and Mansoor Delane are questionable. Patrick Mahomes, Travis Kelce, Rashee Rice "
        "and Xavier Worthy were full participants with no game designation."),
    "steelers-matchup.20261115T072500Z": (
        "b7baa35ee36c43a8507099e10e0f9e40f1d49f495661e6c5091a457a9ed7bcc2",
        "Pittsburgh reports that since Rico Dowdle returned, Jaylen Warren has run 46% of routes "
        "and received 10% of targets. Sunday usage depends on the backfield rotation and game script."),
}


def attach_call_evidence(calls, by_id, games, inputs, pages, now):
    for c in calls:
        source = by_id[c["id"]]["source"]
        c["evidence"] = [
            {"label":"known","kind":"price","statement":"Saved book quote and paired prices at the recorded threshold.",
             "source_url":source["source_url"], "retrieved_utc":source["observed_utc"],
             "provider_updated_utc":source["provider_updated_utc"]},
            {"label":"estimated","kind":"football_judgment","statement":c["rationale"],
             "decided_utc":c.get("decided_utc"),"source_urls":c.get("sources",[])},
            {"label":"estimated","kind":"probability","statement":"Margin-removed market likelihood is an estimate. The reference return uses that estimate at the captured price."},
            {"label":"unknown","kind":"participation_and_fill","statement":"Final inactives, actual workload, personal price, stake limits and accepted terms are unknown."},
        ]
        for folder, (digest, note) in CLUB_SOURCES.items():
            directory = Path(HERE)/"inputs"/folder
            meta_path, raw = directory/"source.json", directory/"source.html"
            if not meta_path.is_file() or not raw.is_file():
                continue
            meta, rec = snapshot_json(meta_path)
            url = meta.get("source_url")
            if url not in c.get("sources",[]):
                continue
            if (meta.get("status") != 200 or meta.get("raw_sha256") != digest or sha256_file(raw) != digest
                    or markets.instant(meta["retrieved_utc"]) > markets.instant(now)
                    or markets.instant(meta["retrieved_utc"]) >= markets.instant(c["kickoff"])):
                raise ValueError("Official football source did not match the saved pregame receipt")
            inputs.setdefault("club_reports", {})[folder] = rec
            c["evidence"].append({"label":"known","kind":"official_club_report","statement":note,
                                  "source_url":url,"retrieved_utc":meta["retrieved_utc"],
                                  "raw_sha256":digest,"saved_page":os.path.relpath(raw, SPRINT),
                                  "saved_link":os.path.relpath(raw, pages)})
        game = games[c["event_id"]]
        # Preserve contradictory sources when presenting the team designation.
        for r in (game.get("matchup_context") or {}).get("injuries", []):
            if r.get("player") != "Kenneth Walker III" or "chiefs.com" not in " ".join(c.get("sources",[])):
                continue
            league = r.get("nfl_com") or {}
            if league.get("game_status") and league["game_status"] != "Out":
                c["evidence"].append({"label":"known","kind":"source_disagreement",
                    "statement":"The league injury table listed Walker as %s. The team’s Saturday list above gives its latest reported game designation. Final inactive lists are still pending." % league["game_status"].lower(),
                    "source_url":league.get("source_url"),"retrieved_utc":league.get("as_of_utc")})
    evidence_file = Path(HERE)/"pdf_export/evidence/2026-11-15.json"
    if evidence_file.is_file():
        evidence, rec = snapshot_json(evidence_file)
        if evidence.get("slate_date") != SLATE_DATE:
            return
        for e in evidence.get("calls", []):
            history = e.get("recent_appearances")
            if not history or e.get("market") not in markets.MARKETS:
                continue
            cid = markets.key_for(e["event_id"],e["market"],e.get("subject",""),e["side"],e.get("point"))
            call = next((c for c in calls if c["id"] == cid), None)
            if call is None:
                continue
            inputs["appearance_history"] = rec
            call["recent_appearances"] = appearance_results(history, call)


def appearance_results(history, call):
    if history.get("season") != 2026 or history.get("season_type") != "REG" or not history.get("complete_through_card"):
        raise ValueError("Need complete current-season regular-season player appearances")
    entries = sorted(history["entries"], key=lambda e:e["appearance"])
    if not entries or [e["appearance"] for e in entries] != list(range(1,len(entries)+1)):
        raise ValueError("Appearance sequence contains a duplicate or gap")
    dates = [e["date"] for e in entries]
    if dates != sorted(set(dates)) or any(not ("2026-01-01" <= date < SLATE_DATE) for date in dates):
        raise ValueError("Invalid or future date in appearance sequence")
    def win(value, line):
        return value > line if call["side"] == "Over" else value < line
    counts = {}
    for n in (5,10):
        window = entries[-n:]
        reported = [e for e in window if type(e.get("value")) in (int,float)]
        counts[str(n)] = {"requested":n,"appearances":len(window),"reported":len(reported),
                          "wins_at_current_line":sum(win(e["value"],call["point"]) for e in reported),
                          "pushes":sum(e["value"]==call["point"] for e in reported)}
    paired = [e for e in entries if type(e.get("prior_line")) in (int,float) and type(e.get("value")) in (int,float)]
    return {"season":2026,"entries":entries,"current_line":call["point"],"recent":counts,
            "prior_line_wins":sum(win(e["value"],e["prior_line"]) for e in paired),"prior_line_observations":len(paired),
            "source_url":history.get("source_url"),"prior_line_source_url":history.get("prior_line_source_url"),
            "historical_books_and_quoted_times_verified":False}


def slate_blocks(doc):
    slate, selected = doc["slate"], doc["selections"]
    by_id = {c["id"]: c for c in slate["candidates"]}
    games = {g["event_id"]: g for g in slate["games"]}
    calls = selected["calls"]
    status = "Release review" if selected["stage"] == "reviewed" else "Provisional model screen"
    if not doc["pregame"] or not doc["frozen"]["verified"]:
        status = "Unverified research replay"
    blocks = [("h1", "Sunday NFL selections · November 15, 2026"),
              ("p", "**%s.** %d selection%s across the Chicago slate. Prices below come from the saved %s capture. Personal offered and accepted prices are unknown."
               % (status, len(calls), "" if len(calls) == 1 else "s", selected["capture_utc"])),
              ("table", ["Chicago window", "Matchup and kickoff (CT)", "Decision", "Captured price", "Minimum price"], [
                  [name, " / ".join(c["game"]+" · "+games[c["event_id"]]["kickoff_local"] for c in calls if c["window"] == w) or "—",
                   " / ".join(c["label"] for c in calls if c["window"] == w) or "Pass",
                   " / ".join(c["sportsbook"] + " " + fmt_price(c["price"]) for c in calls if c["window"] == w) or "—",
                   " / ".join(fmt_price(c["minimum_price"]) for c in calls if c["window"] == w) or "—"]
                  for w, name in markets.WINDOWS.items()])]
    for w, name in markets.WINDOWS.items():
        blocks.append(("h2", name))
        note = slate["window_notes"].get(w)
        if note:
            blocks.append(("p", note))
        for call in [c for c in calls if c["window"] == w]:
            c = by_id[call["id"]]
            game = games[c["event_id"]]
            quote = c["source"]
            blocks.extend([("p", "**%s · %s · %s Chicago.** %s"
                            % (c["label"], c["game"], game["kickoff_local"], call["rationale"])),
                           ("p", "**Known · observed price.** %s %s, minimum %s. The break-even rate is %s. **Estimated** market likelihood is %s (%s, %s peer books)."
                            % (quote["title"], fmt_price(c["price"]), fmt_price(call["minimum_price"]), pct(c["break_even"]),
                               pct(c["hit_likelihood"]) if c["hit_likelihood"] is not None else "unknown",
                               c["likelihood_basis"], c["peer_count"])),
                           ("p", "Same-line offers in the capture · " + ", ".join(q["title"]+" "+fmt_price(q["price"]) for q in
                                sorted(c["quotes"].values(), key=lambda q: (-markets.decimal_odds(q["price"]),q["book"]))) + "."),
                           ("p", "Fetched %s. Provider update %s. The model's estimate is %s. At the market estimate the price implies %s per unit risked on a decided outcome."
                            % (quote["observed_utc"], quote["provider_updated_utc"] or "unknown",
                               pct(c["model_estimate"]) if c["model_estimate"] is not None else "unavailable for this market",
                               ("%+.2f%%" % (c["return_per_unit_at_likelihood"]*100)) if c["return_per_unit_at_likelihood"] is not None else "an unknown return")),
                           ("p", "**Football judgment and risk.** " + c["risk"])])
            blocks.append(("p", "**Estimated** inactive-list time %s. **Unknown** final participation, personally available price and acceptable stake."
                           % call["health"]["inactives_expected_utc"]))
            if c.get("condition") and c["condition"] not in c["risk"]:
                blocks.append(("p", c["condition"]))
            if c["consensus_including_offer"] is not None and c["peer_count"]:
                blocks.append(("p", "Across all %d books with both sides, including the offering book, median fair probability is %s."
                               % (c["two_sided_books"], pct(c["consensus_including_offer"]))))
            for item in call.get("evidence", []):
                if item["kind"] in ("official_club_report", "source_disagreement"):
                    links = "[Source](%s)" % item["source_url"]
                    if item.get("saved_link"):
                        links += " · [Saved page](%s)" % item["saved_link"]
                    blocks.append(("p","**Known · %s.** %s Retrieved %s. %s" % (
                        "team publication" if item["kind"] == "official_club_report" else "source discrepancy",
                        item["statement"],item["retrieved_utc"],links)))
            recent = call.get("recent_appearances")
            if recent:
                parts = []
                for n in ("5","10"):
                    win = recent["recent"][n]
                    parts.append("%d/%d above %g in the latest %s appearances (%d available, %d missing stats)"
                                 % (win["wins_at_current_line"],win["reported"],call["point"],n,win["appearances"],win["appearances"]-win["reported"]))
                blocks.append(("p", "**Known · consecutive current-season appearances.** "+" · ".join(parts)
                               +". Zero-yard appearances count. [Official game log](%s)" % recent["source_url"]))
                if recent["prior_line_observations"]:
                    blocks.append(("p", "Against the thresholds published for those individual games, the third-party archive shows %d/%d over. "
                                   "The historical books, quote times and payouts are unverified. [Historical thresholds](%s)"
                                   % (recent["prior_line_wins"],recent["prior_line_observations"],recent["prior_line_source_url"])))
            elif c.get("player_evidence"):
                blocks.append(("p","Verified consecutive appearances are unavailable. The player-evidence record retains the reported game-log rows and any gaps."))
            if c["price_observations"]:
                moves = ["%s %s at %s → %s at %s" % (m["book"],fmt_price(m["earliest_observed_price"]),
                         m["earliest_observed_utc"], fmt_price(m["latest_observed_price"]),m["latest_observed_utc"])
                         for m in c["price_observations"]]
                blocks.append(("p", "Earliest and latest observations supplied to this picker · " + ". ".join(moves) + ". The opener and closing price are unknown."))
            else:
                blocks.append(("p", "This picker has no earlier same-book quote for this exact contract. The opener and closing price are unknown."))
            if c.get("review_sources"):
                blocks.append(("p", "Pregame evidence · " + " · ".join("[Source %d](%s)" % (i+1,u) for i,u in enumerate(c["review_sources"]))))
    blocks.extend([("h2", "Market coverage and game context"),
                   ("p", "%d captured sides, %d distinct contracts, %d in the permitted price range. Each contract keeps its team or player, period, side and exact line. Only same-book pairs at that line enter a margin-removed estimate."
                    % (sum(slate["quoted_sides_by_market"].values()),len(by_id),sum(c["in_price_band"] for c in by_id.values()))),
                   ("table", ["Game", "Kickoff in Chicago", "Venue", "Team records (away / home)", "Points for–against per game (away / home)"],
                    [[g["game"],g["kickoff_local"], (g["venue"] or "unknown") + (" · neutral site" if g["neutral"] else ""),
                      " / ".join("%d–%d–%d" % tuple(f[x] for x in ("w","l","t")) for f in (g["form_2026"]["away"],g["form_2026"]["home"])),
                      " / ".join("%.1f–%.1f" % (f["pf_per_game"], f["pa_per_game"]) if f["n"] else "unknown" for f in (g["form_2026"]["away"],g["form_2026"]["home"]))]
                     for g in sorted(games.values(), key=lambda item: (markets.instant(item["kickoff_utc"]),item["name"]))]),
                   ("p", "The full record includes team form, last meetings, pregame injury evidence, every candidate, pass reason and exact-line book quotes. Official inactives and personal availability were unverified at capture. A neutral venue receives zero home-field advantage.")])
    games_source = doc["inputs"]["games"]
    if games_source.get("source_url"):
        blocks.append(("p", "Historical scores, team records and schedule rows were retrieved %s. Individual archived price times are unknown. [nflverse game archive](%s)"
                       % (games_source["retrieved_utc"], games_source["source_url"])))
    supplements = [label+" built "+doc["inputs"][key]["built_utc"] for key,label in
                   (("team_context","Team and injury file"),("player_context","player form file"))
                   if (doc["inputs"].get(key) or {}).get("built_utc")]
    if supplements:
        blocks.append(("p", ". ".join(supplements)+". These supplement the issued review at "+
                       selected["decided_utc"]+". They do not change its recorded time or terms."))
    if slate.get("context_notes"):
        blocks.append(("ul", slate["context_notes"]))
    for c in calls:
        g = games[c["event_id"]]
        last = g["form_2026"]
        blocks.append(("p", "%s · last five and up to ten 2026 games (away/home W–L–T): %s." % (g["game"],
                      " · ".join(" / ".join("%d–%d–%d (%d games)" % tuple(last[k]["recent"][period][v] for v in ("wins","losses","ties","games")) for k in ("away","home"))
                                 for period in ("last_5","last_10")))))
        h2h = g["head_to_head_last5"]
        if h2h:
            last = h2h[-1]
            blocks.append(("p", "%s · last meeting in the archive, %d Week %d: %s %d, %s %d. Rest days (away/home) %s / %s."
                           % (g["game"],last["season"],last["week"],last["away"],last["away_score"],last["home"],last["home_score"],
                              g["rest_days"]["away"],g["rest_days"]["home"])))
    test = doc["past_only_test"]["windows"]["test_b"]
    independent = doc.get("independent_review")
    if independent:
        blocks.extend([("h2","Independent pregame review"),
                       ("p","The release owner's calls above retain their original timestamp. Read the independent review for its disagreement on price, role assumptions and conditions. "
                        "[Read the football red team](%s)" % independent["link"])])
        if independent["verdicts"]:
            blocks.append(("table", ["Candidate in the independent review","Reviewer verdict"],independent["verdicts"]))
    blocks.extend([("h2", "Pregame experiment"),
                   ("p", doc["hypothesis"]),
                   ("p", "The provisional football screen and final release can differ. The reviewer applies the documented football case, downside and price floor to the full pool. "
                    "Only the release selections in the opening table carry the reviewer’s decision."),
                   ("p", "Rules frozen %s. Football review time %s. Capture digest %s. The review and rule freeze both precede kickoff. The human review may have seen these prices before the rule freeze."
                    % (doc["frozen"].get("frozen_utc") or "unverified", selected.get("decided_utc") or "none",selected["capture_sha256"][:16])),
                   ("table", ["Chicago window", "Frozen market-only control", "Price", "Provisional football screen"],
                    [[label, by_id[cid]["label"] if cid else "Pass", fmt_price(by_id[cid]["price"]) if cid else "—",
                      by_id[slate["screen_by_window"][w]]["label"] if slate["screen_by_window"][w] else "Pass"]
                     for w,label in markets.WINDOWS.items() for cid in [slate["control_by_window"][w]]]),
                   ("p", "For completed 2026 Weeks 1–9, %d decided moneylines give market log loss %.4f versus %.4f for the independent model. Lower is better. The fitted blend uses %.0f%% market weight. No calibrated advantage has been established for the release calls."
                    % (test["n_priced"],test["market"]["log_loss"],test["model"]["log_loss"],100*doc["past_only_test"]["best_market_weight_on_tune"])),
                   ("p", "On a push or void, simulated profit is zero. A booked return requires an accepted ticket. The price-movement comparison uses the same event, book, period, market, side, player or team, and line. A genuine closing observation is needed to compute closing-line value.")])
    return blocks



# ---------------------------------------------------------------- grading

def valid_score_pair(pair):
    return (isinstance(pair, dict) and all(type(pair.get(k)) in (int, float)
            and math.isfinite(pair[k]) and pair[k] >= 0 for k in ("away", "home")))


def load_finals(scores_json, scores_csv):
    finals, by_teams = {}, {}
    if scores_json:
        for g in read_json(scores_json).get("games", []):
            fs = g.get("final_score")
            if g.get("state") == "STATUS_FINAL" and valid_score_pair(fs):
                scores = {k: fs[k] for k in ("home", "away")}
                if valid_score_pair(g.get("first_half_score")):
                    scores["first_half"] = g["first_half_score"]
                finals[str(g["event_id"])] = scores
    if scores_csv:
        for g in load_games(scores_csv):
            if (g["season"] == 2026 and g["gameday"] == SLATE_DATE and
                    None not in (g["home_score"], g["away_score"])):
                by_teams["%s at %s" % (g["away"], g["home"])] = {
                    "home": g["home_score"], "away": g["away_score"]}
    return finals, by_teams


def grade_candidates(doc, finals, by_teams, player_results=None):
    meta = {str(g["event_id"]):g for g in doc["slate"].get("games", [])}
    out = []
    for c in doc["slate"]["candidates"]:
        gid = str(c["event_id"])
        game = meta.get(gid, {})
        fs = finals.get(gid) or finals.get(str(game.get("espn_event_id"))) or by_teams.get(c["game"])
        if c.get("period") == "first_half":
            fs = (fs or {}).get("first_half")
        row = {"id": c["id"], "label": c["label"], "selected": c["selected"], "control": c.get("control", False),
               "provisional_screen": c.get("provisional_screen", False), "price": c["price"],
               "hit_likelihood": c["hit_likelihood"], "result": None, "profit_per_unit": None, "score_for_period": fs}
        if c["market"] == "prop":
            # Only explicit player results for this exact contract. No inference from absence or final scores.
            result = (player_results or {}).get(c["id"])
            if isinstance(result, dict) and result.get("disposition") == "void":
                row["result"] = "void"
            elif isinstance(result, dict) and result.get("disposition") == "played" and type(result.get("value")) in (int, float) and math.isfinite(result["value"]):
                diff = result["value"] - c["line"]
                row["result"] = "push" if diff == 0 else "win" if (diff > 0) == c["side"].startswith("over") else "loss"
            else:
                row["result"] = "ungraded: no verified participation and player stat for this exact contract"
        elif not valid_score_pair(fs):
            row["result"] = "ungraded: no observed score for this period"
        elif c["market"] in ("moneyline", "spread", "total"):
            line = c.get("line")
            if c["market"] == "spread" and c["side"] == "home":
                line = -line
            row["result"] = lane_rules.grade(c["market"], c["side"], line, fs["home"], fs["away"])
        elif c["market"] == "team_total":
            team = ABBR.get(c.get("subject"))
            away, home = c["game"].split(" at ")
            if team in (home, away):
                points = fs["home" if team == home else "away"]
                row["result"] = lane_rules.grade("total", c["side"], c["line"], points, 0)
            else:
                row["result"] = "ungraded: team did not match the recorded game"
        else:
            row["result"] = "ungraded: unknown contract or settlement rules"
        if row["result"] == "win":
            row["profit_per_unit"] = lane_rules.american_profit(c["price"])
        elif row["result"] == "loss":
            row["profit_per_unit"] = -1.0
        elif row["result"] in ("push", "void"):
            row["profit_per_unit"] = 0.0
        out.append(row)
    return out


# ---------------------------------------------------------------- commands

def _src(path, extra=None):
    d = {"path": os.path.relpath(path, SPRINT), "sha256": sha256_file(path)}
    if extra:
        d.update(extra)
    return d


def cmd_backtest(a):
    games = load_games(a.games)
    res, _, _ = past_only_test(games, PARAMS, SLATE_DATE)
    res["run_utc"] = utc_now()
    res["inputs"] = {"games": _src(a.games)}
    res["params"] = PARAMS
    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "past_only_test.json"), "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    blocks = past_only_blocks(res)
    blocks.insert(1, ("p", "Run %s. Input `%s` (sha256 %s). Cutoff: games dated before %s."
                      % (res["run_utc"], res["inputs"]["games"]["path"], res["inputs"]["games"]["sha256"][:16], SLATE_DATE)))
    with open(os.path.join(HERE, "PAST_ONLY_TEST.md"), "w") as f:
        f.write(render_md(blocks))
    for k in ("tune", "test_a", "test_b"):
        w = res["windows"][k]
        print("%-7s n=%4d  logloss market %.4f model %.4f blend %.4f | spread %s | total %s | top2 market %s ret %+.3f | top2 model %s"
              % (k, w["n_priced"], w["market"]["log_loss"], w["model"]["log_loss"], w["blend"]["log_loss"],
                 _rate(w["spread"]["all"]), _rate(w["total"]["all"]), _rate(w["top2_market"]),
                 (w["top2_market"]["profit"] / w["top2_market"]["bets"]) if w["top2_market"]["bets"] else 0.0,
                 _rate(w["top2_model"])))
    print("market weight on tune: %.2f; likelihood basis: %s; sd margin %.2f total %.2f"
          % (res["best_market_weight_on_tune"], res["likelihood_basis"], res["sd_margin"], res["sd_total"]))
    return 0


def freeze_inputs():
    return {name: sha256_file(os.path.join(HERE, name)) for name in
            ("picker.py", "selection_markets.py", "selection_decisions.py")}


def _frozen_state(path):
    if not os.path.isfile(path):
        return {"verified": False, "problem": "Run freeze before scoring."}
    f = read_json(path)
    problem = None
    if f.get("code_sha256") != freeze_inputs() or f.get("rules_sha256") != sha256_file(os.path.join(LANE,"rules.py")):
        problem = "Selection code changed after freeze."
    elif f.get("params") != PARAMS or f.get("selection_rule") != SELECTION_RULE or f.get("hypothesis") != HYPOTHESIS:
        problem = "Frozen parameters or hypothesis differ."
    elif markets.instant(f["frozen_utc"]) >= markets.instant("2026-11-15T14:30:00Z"):
        problem = "Freeze occurred after the first kickoff."
    return dict(f, verified=problem is None, problem=problem)


def atomic_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", prefix="."+path.name+".", dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        try:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def as_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False)+"\n"


def cmd_freeze(a):
    now = utc_now()
    if markets.instant(now) >= markets.instant("2026-11-15T14:30:00Z"):
        raise ValueError("Cannot change the November 15 experiment freeze after its first kickoff")
    previous = _frozen_state(a.frozen)
    if previous.get("verified"):
        print("Verified existing freeze", previous["frozen_utc"])
        return 0
    rec = {"frozen_utc": now, "code_sha256": freeze_inputs(), "picker_sha256": sha256_file(__file__),
           "rules_sha256": sha256_file(os.path.join(LANE, "rules.py")), "params": PARAMS,
           "selection_rule": SELECTION_RULE, "hypothesis": HYPOTHESIS, "slate_date": SLATE_DATE,
           "timezone": TIMEZONE, "expected_sunday_games": EXPECTED_SUNDAY_GAMES, "note": a.note}
    atomic_text(a.frozen, as_json(rec))
    with open(Path(a.frozen).parent/"FREEZE_LOG.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True)+"\n")
    print("Frozen", rec["frozen_utc"], rec["picker_sha256"][:16])
    return 0


def run_slate(a):
    now = utc_now()
    frozen = _frozen_state(a.frozen)
    if frozen.get("frozen_utc") and markets.instant(frozen["frozen_utc"]) > markets.instant(now):
        raise ValueError("Rule freeze is dated after this run")
    if (a.allow_unfrozen or a.allow_late) and (Path(a.out_dir).resolve() == (Path(HERE)/"results").resolve()
                                              or Path(a.report_dir).resolve() == Path(LANE).resolve()):
        raise ValueError("Late or unfrozen research runs need separate --out-dir and --report-dir")
    if not frozen["verified"] and not a.allow_unfrozen:
        raise ValueError(frozen["problem"])
    odds_path = a.odds
    if not a.lines and not odds_path:
        default_odds = Path.home()/"Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live/sunday-odds.json"
        if default_odds.is_file():
            odds_path = str(default_odds)
    default_lines = os.path.join(LANE, "real", "inputs", "nfl-public-lines.20261114T225342Z.json")
    primary = odds_path or a.lines or default_lines
    inputs = {"games": _src(a.games), "health": None}
    data, inputs["lines"] = snapshot_json(primary)
    reference, inputs["schedule_reference"] = snapshot_json(a.schedule_reference)
    props = []
    if odds_path:
        capture = data
        schedule = markets.schedule_from_capture(capture, reference, now)
        stamp = capture["captured_utc"]
        source_type = "The Odds API · saved provider response"
        auxiliary = Path(odds_path).parent/"Final_Decisions.json"
    else:
        capture = None
        schedule = data
        stamp = data["capture_complete_utc"]
        source_type = data.get("price_note") or "Normalized saved book references"
        auxiliary = None
        prop_path = a.props
        if prop_path is None and not (data.get("sources") or [{}])[0].get("saved_file_sha256"):
            prop_path = os.path.join(SPRINT, "codex", "real-intake", "nfl-prop-priced.json")
        if prop_path:
            props, _ = load_props(prop_path)
            inputs["props"] = catalog_source(prop_path)
    if markets.instant(stamp) > markets.instant(now):
        raise ValueError("Capture completion is after the current run")
    inputs["lines"].update(capture_complete_utc=stamp, source_type=source_type)
    manifest = Path(a.games).parent/"MANIFEST.json"
    if Path(a.games).resolve() == (Path(LANE)/"data/raw/games.csv").resolve() and manifest.is_file():
        provenance = next((r for r in read_json(manifest).get("files", []) if r.get("path") == "data/raw/games.csv"), None)
        if not provenance or provenance.get("sha256") != inputs["games"]["sha256"]:
            raise ValueError("Game history differs from its source manifest")
        inputs["games"].update(source_url=provenance["url"], retrieved_utc=provenance["retrieved_at_utc"],
                               row_quote_time="unknown")
    history = load_games(a.games)
    test, _, st = past_only_test(history, PARAMS, SLATE_DATE)
    health = None
    if a.health and os.path.isfile(a.health):
        health, inputs["health"] = snapshot_json(a.health)
    if health and markets.instant(health["captured_utc"]) > markets.instant(now):
        raise ValueError("Injury report was retrieved after the run")
    all_games = game_context(history, schedule, health, st)
    if len(all_games) != EXPECTED_SUNDAY_GAMES:
        raise ValueError("Expected %d distinct Sunday games, got %d" % (EXPECTED_SUNDAY_GAMES, len(all_games)))
    first = min(g["kickoff_utc"] for g in all_games.values())
    pregame = markets.instant(now) < markets.instant(first)
    if not pregame and not a.allow_late:
        raise ValueError("First kickoff has passed. A rerun cannot be recorded as a pregame selection.")
    valid = {eid: g for eid,g in all_games.items() if g["eligible"]}
    candidates, stats, skips = markets.collect(capture, schedule, props, valid, now)
    historical = price_history(reference, valid, now)
    screens, controls = decisions.evaluate(candidates, valid, test, historical)
    context_notes = attach_context(a, inputs, all_games, candidates, inputs["lines"]["sha256"], now, first)
    by_id = {c["id"]: c for c in candidates}
    overlay = None
    if a.decisions:
        overlay, inputs["decisions"] = snapshot_json(a.decisions)
    elif auxiliary and auxiliary.is_file():
        neighbor, neighbor_source = snapshot_json(auxiliary)
        if neighbor.get("capture_sha256") == inputs["lines"]["sha256"]:
            overlay = neighbor
            inputs["decisions"] = neighbor_source
    if overlay is not None:
        picks = decisions.apply_overlay(overlay, candidates, inputs["lines"]["sha256"], stamp, first, now)
    else:
        picks = [cid for cid in screens.values() if cid]
        for cid in picks:
            c = by_id[cid]
            c.update(minimum_price=c["price"], rationale="Highest market probability in this window among contracts where the football model and exact-line peers both favor the side.",
                     risk="Team ratings omit late personnel changes. The held-out model did not improve probability accuracy on the market. Recheck the exact quote and official inactives.")
    decision_time = (overlay or {}).get("decided_utc", now)
    stage = "reviewed" if overlay is not None else "provisional"
    notes = dict((overlay or {}).get("window_notes", {}))
    for w in markets.WINDOWS:
        if not any(by_id[cid]["window"] == w for cid in picks):
            notes.setdefault(w, "Pass. No supported selection was released for this window.")
    for c in candidates:
        c["selected"] = c["id"] in picks
        c["control"] = c["id"] == controls[c["window"]]
        c["provisional_screen"] = c["id"] == screens[c["window"]]
        c["omitted_because"] = None if c["selected"] else (
            "Release reviewer passed on this contract." if overlay is not None and c["in_price_band"]
            else c["screen_exclusion"] or "A higher-ranked candidate filled the window.")
    calls = [decisions.selection_call(by_id[cid]) for cid in picks]
    for call in calls:
        c = by_id[call["id"]]
        call["decided_utc"] = decision_time
        g = all_games[c["event_id"]]
        call["health"] = health_summary(c, g)
        call["player_evidence"] = c.get("player_evidence")
        call["quote_age_at_decision_seconds"] = (markets.instant((overlay or {}).get("decided_utc",now)) -
                                                 markets.instant(call["observed_utc"])).total_seconds()
        call["matchup"] = {k: g[k] for k in ("neutral","venue","form_2026","head_to_head_last5","rest_days")}
        call["model_estimate_basis"] = "Walk-forward game ratings; context only" if c["model_estimate"] is not None else "No calibrated forecast for this market"
        call["settlement_terms"] = "Two-way price. Personal offer, stake, book acceptance and house rules unknown."
        call["market_probability_basis"] = "conditional on a decided outcome" if c["push_possible"] else "no push at posted half-unit line; void rules depend on book"
    
    attach_call_evidence(calls, by_id, all_games, inputs, a.report_dir, now)
    selections = {"schema_version": 2, "stage": stage, "slate_date": SLATE_DATE,
                  "author": (overlay or {}).get("author"), "decided_utc": (overlay or {}).get("decided_utc", now),
                  "run_utc": now, "pregame": pregame, "rules_verified": frozen["verified"],
                  "capture_utc": stamp, "capture_sha256": inputs["lines"]["sha256"],
                  "window_notes": notes, "calls": calls, "tickets": [], "ticket_status": "no ticket recorded"}
    slate = {"games": list(all_games.values()), "candidates": candidates, "picks": picks,
             "control_by_window": controls, "screen_by_window": screens, "window_notes": notes,
             "quoted_sides_by_market": stats, "skipped_quote_reasons": skips, "context_notes": context_notes, "n_sunday_games": len(all_games)}
    review = Path(HERE)/"FOOTBALL_RED_TEAM.md"
    independent = None
    if review.is_file():
        inputs["football_review"] = _src(review)
        independent = {"path":inputs["football_review"]["path"], "link":os.path.relpath(review, a.report_dir),
                       "verdicts":read_review_verdicts(review.read_text())}
    return {"schema_version": 2, "run_utc": now, "slate_date": SLATE_DATE, "pregame": pregame,
            "independent_review":independent,
            "first_kickoff_utc": first, "frozen": frozen, "inputs": inputs, "params": PARAMS,
            "past_only_test": {k:test[k] for k in ("likelihood_basis","best_market_weight_on_tune",
                              "blend_beats_market_in_both_tests","sd_margin","sd_total","windows")},
            "measurement": {"market_likelihood":"vig removed, conditional on a decided outcome",
                            "book_return":"hypothetical unit return; no accepted price observed",
                            "clv":None, "close_status":"no verified closing observation",
                            "source_context":"expanded football inputs are descriptive as of their retrieval and may postdate the issued review"},
            "hypothesis": HYPOTHESIS, "slate": slate, "selections": selections}


def write_slate(a, doc):
    directory, pages = Path(a.out_dir), Path(a.report_dir)
    directory.mkdir(parents=True, exist_ok=True)
    out = directory/"sunday_20261115_candidates.json"
    if out.exists():
        prev = read_json(out)
        same_freeze = (prev.get("schema_version") == doc["schema_version"] and prev.get("frozen") == doc["frozen"]
                       and prev.get("pregame") == doc["pregame"])
        if same_freeze and prev.get("inputs") == doc["inputs"]:
            doc = prev  # Rebuild any missing projections from the recorded decision.
        else:
            primary_inputs = ("games", "lines", "schedule_reference", "decisions", "props")
            same_decision = same_freeze and all(
                (prev.get("inputs", {}).get(k) or {}).get("sha256") == (doc["inputs"].get(k) or {}).get("sha256")
                for k in primary_inputs) and prev["slate"]["picks"] == doc["slate"]["picks"]
            if not same_decision and not a.replace:
                raise ValueError("Decision inputs or rules changed. Use --replace to archive and supersede the recorded slate.")
            if prev.get("pregame") and not doc["pregame"]:
                raise ValueError("A late replay cannot supersede the pregame decision")
            archive = directory/("sunday_20261115_candidates.superseded_"+sha256_file(out)[:16]+".json")
            if not archive.exists():
                atomic_text(archive, out.read_text())
    blocks = slate_blocks(doc)
    atomic_text(pages/"BEST_BETS_SUN_NOV15.md", render_md(blocks))
    atomic_text(pages/"BEST_BETS_SUN_NOV15.html", render_html("Sunday NFL selections · November 15",blocks))
    atomic_text(directory/"sunday_20261115_selections.json", as_json(doc["selections"]))
    atomic_text(out, as_json(doc))
    return doc


def cmd_slate(a):
    import fcntl
    Path(a.out_dir).mkdir(parents=True,exist_ok=True)
    with open(Path(a.out_dir)/".picker-write.lock","a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        doc = write_slate(a, run_slate(a))
    print("%d games, %d exact contracts, %s, frozen %s" % (doc["slate"]["n_sunday_games"],
          len(doc["slate"]["candidates"]),doc["selections"]["stage"],doc["frozen"]["verified"]))
    for window, name in markets.WINDOWS.items():
        calls = [c for c in doc["selections"]["calls"] if c["window"] == window]
        print(name, " | ".join("%s %s %s" % (c["label"],c["book"], fmt_price(c["price"])) for c in calls) or "Pass")
    print("Selection record:", Path(a.out_dir)/"sunday_20261115_selections.json")
    return 0


def cmd_grade(a):
    doc = json.load(open(a.record))
    finals, by_teams = load_finals(a.scores_json, a.scores_csv)
    players = read_json(a.player_results) if a.player_results else {}
    rows = grade_candidates(doc, finals, by_teams, players)
    res = {"graded_utc": utc_now(), "record": os.path.relpath(a.record, SPRINT), "record_run_utc": doc["run_utc"],
           "scores": {"json": _src(a.scores_json) if a.scores_json else None, "csv": _src(a.scores_csv) if a.scores_csv else None},
           "player_results_source": catalog_source(a.player_results), "rows": rows, "basis": "hypothetical one unit at captured price"}
    os.makedirs(a.out_dir, exist_ok=True)
    name = "sunday_20261115_graded_%s.json" % res["graded_utc"].replace(":", "")
    atomic_text(Path(a.out_dir)/name, as_json(res))
    done = [r for r in rows if r["result"] in ("win", "loss", "push", "void")]
    for r in rows:
        if r["selected"]:
            print("PICK %s: %s%s" % (r["label"], r["result"], (" (%+.2f units)" % r["profit_per_unit"]) if r["profit_per_unit"] is not None else ""))
    print("graded %d of %d candidates; wins %d, losses %d, pushes %d; wrote %s" % (
        len(done), len(rows), sum(r["result"] == "win" for r in done), sum(r["result"] == "loss" for r in done),
        sum(r["result"] == "push" for r in done), name))
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="Sunday NFL cross-market picker (advisory)")
    sub = p.add_subparsers(dest="cmd")
    d_games = os.path.join(LANE, "data", "raw", "games.csv")
    d_out = os.path.join(HERE, "results")
    d_frozen = os.path.join(HERE, "frozen_picker.json")
    b = sub.add_parser("backtest")
    b.add_argument("--games", default=d_games)
    b.add_argument("--out-dir", default=d_out)
    f = sub.add_parser("freeze")
    f.add_argument("--frozen", default=d_frozen)
    f.add_argument("--note", default="")
    s = sub.add_parser("slate")
    s.add_argument("--games", default=d_games)
    source = s.add_mutually_exclusive_group()
    source.add_argument("--lines", help="Established normalized game-lines JSON (game prices, any captured book)")
    source.add_argument("--odds", help="Saved full Odds API capture; includes game, first-half, team and player markets")
    s.add_argument("--decisions", help="Pregame release-owner review bound to the capture SHA-256")
    s.add_argument("--schedule-reference", default=os.path.join(LANE, "real","inputs","nfl-public-lines.20261114T225342Z.json"))
    s.add_argument("--report-dir", default=LANE)
    s.add_argument("--team-context", default=os.path.join(HERE, "slate_20261115.json"))
    s.add_argument("--player-context", default=os.path.join(HERE, "props_20261115.json"))
    s.add_argument("--health", default=os.path.join(SPRINT, "codex", "NFL_SUNDAY_HEALTH.json"))
    s.add_argument("--props", help="Additional priced prop input for legacy --lines mode")
    s.add_argument("--props-reference", default=os.path.join(SPRINT, "codex", "real-intake", "nfl-prop-reference.json"))
    s.add_argument("--frozen", default=d_frozen)
    s.add_argument("--out-dir", default=d_out)
    s.add_argument("--allow-unfrozen", action="store_true")
    s.add_argument("--allow-late", action="store_true")
    s.add_argument("--replace", action="store_true")
    g = sub.add_parser("grade")
    g.add_argument("--record", default=os.path.join(d_out, "sunday_20261115_candidates.json"))
    g.add_argument("--scores-json", default=None)
    g.add_argument("--scores-csv", default=None)
    g.add_argument("--player-results", help="JSON keyed by exact contract ID, with disposition played and value, or disposition void")
    g.add_argument("--out-dir", default=d_out)
    return p


def main(argv=None):
    p = build_parser()
    a = p.parse_args(argv)
    if a.cmd == "backtest":
        return cmd_backtest(a)
    if a.cmd == "freeze":
        return cmd_freeze(a)
    if a.cmd == "slate":
        try:
            return cmd_slate(a)
        except (ValueError, KeyError, OSError, TypeError) as exc:
            print("Slate could not be recorded: %s" % exc, file=sys.stderr)
            return 2
    if a.cmd == "grade":
        return cmd_grade(a)
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
