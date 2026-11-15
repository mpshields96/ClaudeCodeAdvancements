#!/usr/bin/env python3
"""next_man_up: paper-only, advisory next-man-up screen. Stdlib only, Python 3.9 safe.

Question it answers for any slate: when a starter is out, is the next man's role weaker, preserved, stronger,
mixed or unknown versus the starter, and is that already in the posted prices? It never changes a price, a win
probability, a call or the order of calls.

  screen_slate(spec, base_dir=".")  -> report dict (schema replacement_report/1)
  screen_team(...)                  -> one team's block (used by screen_slate)
  replacement_context(report, team=None, player=None, event_id=None) -> the object for call.replacement_context
  CLI: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I next_man_up.py <spec.json> <report.json>

Rules that matter (see INTERFACE.md):
  * Workload, efficiency, team expectation and receiving are read separately. The posted prices already contain the
    availability news, so nothing here is added to a price (no double counting).
  * A posted line is a threshold with a no-vig probability near 50%: it is not a mean forecast.
  * The post-news team total or spread describes the priced scoring environment. It cannot show the absence's marginal
    effect without a pre-news counterfactual (spec field pre_news); without one the marginal effect is "unknown".
  * Team season stats are team context, never the replacement's efficiency.
  * Last-N means consecutive 2026 game rows with a stat line; no 2025 padding; the denominator is always shown.
  * Every value is K (known, sourced), E (computed from K values) or U (unknown). Nothing is filled from memory.
"""
import hashlib
import json
import os
import re
import statistics
import sys
import unicodedata
from datetime import datetime, timezone
from html import unescape

SCHEMA_VERSION = "replacement_report/1"
CTX_SCHEMA = "replacement_context/1"

RULES = {
    "workload_band": 0.10,          # candidate/starter ratio within +-10% = preserved
    "efficiency_band": 0.10,
    "receiving_band": 0.15,
    "team_points_band": 1.0,        # implied points change vs pre-news, points
    "efficiency_min_carries": 50,   # both players need this many 2026 carries for an efficiency verdict
    "starter_min_games": 4,         # fewer starter games = low confidence
    "priced_in_up_ratio": 1.5,      # role news says up: line / own 2026 average at least this = priced in
    "unpriced_up_ratio": 1.15,      # below this = possibly unpriced
    "priced_in_down_ratio": 0.85,   # role news says down: line / own average at most this = priced in
    "single_game_share": 0.5,       # one game supplying at least this share of receiving yards is flagged
    "no_double_count": "Posted prices already contain the availability news as of their capture time; nothing in this "
                       "report adjusts a price, a win probability, a call or the order of calls.",
}

BOOK_SHORT = {"draftkings": "DK", "fanduel": "FD", "betmgm": "MGM", "espnbet": "tSB", "betrivers": "BR"}
MARKETS = {"player_rush_yds": "rush_yds", "player_rush_attempts": "rush_attempts",
           "player_reception_yds": "rec_yds", "player_pass_yds": "pass_yds"}


# ---------------------------------------------------------------- small helpers
def norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = s.lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def prob_from_american(a):
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def no_vig(over, under):
    po, pu = prob_from_american(over), prob_from_american(under)
    return po / (po + pu), po + pu - 1.0


def med(xs):
    return statistics.median(xs) if xs else None


def r(x, n=3):
    return None if x is None else round(x, n)


def label_ratio(ratio, band):
    if ratio is None:
        return "unknown"
    if ratio < 1.0 - band:
        return "weaker"
    if ratio > 1.0 + band:
        return "stronger"
    return "preserved"


def comp(label, value_label, basis, confidence=None, **extra):
    d = {"label": label, "value_label": value_label, "basis": basis}
    if confidence:
        d["confidence"] = confidence
    d.update(extra)
    return d


# ---------------------------------------------------------------- NFL.com game log
def _text(cell):
    return " ".join(unescape(re.sub(r"<[^>]+>", "", cell)).split())


def _cells(row):
    return [_text(c) for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", row, re.S | re.I)]


def parse_nfl_log(html_text):
    """Parse a saved nfl.com player 2026 game-log page. Returns {title, headers, games(newest first), error}."""
    t = re.search(r"<title>(.*?)</title>", html_text, re.S)
    out = {"title": _text(t.group(1)) if t else "", "headers": [], "games": [], "error": None}
    m = re.search(r">Regular Season</h3>.*?<table\b[^>]*>(.*?)</table>", html_text, re.S | re.I)
    if not m:
        out["error"] = "no regular-season table on the page (no 2026 regular-season game rows)"
        return out
    rows = [_cells(x) for x in re.findall(r"<tr\b[^>]*>(.*?)</tr>", m.group(1), re.S)]
    if not rows or rows[0][:4] != ["WK", "Game Date", "OPP", "RESULT"]:
        out["error"] = "unrecognized game-log columns"
        return out
    out["headers"] = rows[0][4:]
    for row in rows[1:]:
        if len(row) != len(rows[0]) or not row[0].isdigit() or not re.fullmatch(r"[WLT]\s+\d+\s*-\s*\d+", row[3]):
            continue
        date = datetime.strptime(row[1], "%m/%d/%Y").date().isoformat()
        out["games"].append({"date": date, "week": int(row[0]), "opponent": row[2], "result": row[3],
                             "values": [v or None for v in row[4:]]})
    out["games"].sort(key=lambda g: g["date"], reverse=True)
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def history_from_log(parsed, before_date):
    """2026 usage from game rows dated before `before_date` that carry a stat line. Blank cells beside filled cells are 0."""
    h = parsed["headers"]
    if parsed.get("error") or not h:
        return {"label": "U", "error": parsed.get("error") or "no headers", "appearances": 0}
    i_att = h.index("ATT") if "ATT" in h else None
    i_rec = h.index("REC") if "REC" in h else None
    rows = [g for g in parsed["games"] if g["date"] < before_date]
    stat_rows = [g for g in rows if any(v is not None for v in g["values"])]
    carries = sum(_num(g["values"][i_att]) for g in stat_rows) if i_att is not None else None
    ryds = sum(_num(g["values"][i_att + 1]) for g in stat_rows) if i_att is not None else None
    rec = sum(_num(g["values"][i_rec]) for g in stat_rows) if i_rec is not None else None
    recy = sum(_num(g["values"][i_rec + 1]) for g in stat_rows) if i_rec is not None else None
    n = len(stat_rows)
    rec_games = [_num(g["values"][i_rec + 1]) for g in stat_rows] if i_rec is not None else []
    out = {"label": "K", "appearances": n, "rows_without_stat_line": len(rows) - n,
           "weeks": [g["week"] for g in reversed(stat_rows)],
           "carries": carries, "yards": ryds, "ypc": r(ryds / carries, 2) if carries else None,
           "carries_pg": r(carries / n, 2) if n and carries is not None else None,
           "rush_yds_pg": r(ryds / n, 2) if n and ryds is not None else None,
           "max_carries": max((_num(g["values"][i_att]) for g in stat_rows), default=None) if i_att is not None else None,
           "receptions": rec, "rec_yards": recy,
           "rec_yds_pg": r(recy / n, 2) if n and recy is not None else None,
           "yds_per_reception": r(recy / rec, 2) if rec else None,
           "max_game_rec_yards": max(rec_games) if rec_games else None,
           "sample_note": "%d consecutive 2026 game rows with a stat line before %s (%d rows with no stat line left out, appearance "
                          "not verified for those); no 2025 padding" % (n, before_date, len(rows) - n)}
    return out


# ---------------------------------------------------------------- market
def collect_quotes(bookmakers, captured_utc):
    """player_norm -> stat -> list of per-book, per-line quotes (both sides kept apart)."""
    q = {}
    for bk in bookmakers:
        short = BOOK_SHORT.get(bk.get("key"), bk.get("key"))
        for mk in bk.get("markets", []):
            stat = MARKETS.get(mk.get("key"))
            if not stat:
                continue
            sides = {}
            for o in mk.get("outcomes", []):
                if o.get("description") is None or o.get("point") is None:
                    continue
                sides.setdefault((norm(o["description"]), o["point"]), {})[o["name"]] = o["price"]
            for (pn, pt), s in sides.items():
                q.setdefault(pn, {}).setdefault(stat, []).append(
                    {"book": short, "line": pt, "over": s.get("Over"), "under": s.get("Under"),
                     "last_update_utc": mk.get("last_update"), "captured_utc": captured_utc})
    return q


def summarize_market(quotes):
    books, nv = [], []
    for x in quotes:
        both = x["over"] is not None and x["under"] is not None
        e = dict(x)
        e["same_line_both_sides"] = both
        if both:
            e["no_vig_over"], e["hold"] = [r(v, 4) for v in no_vig(x["over"], x["under"])]
            nv.append(e["no_vig_over"])
        else:
            e["no_vig_over"] = e["hold"] = None
        books.append(e)
    lines = [x["line"] for x in quotes]
    s = {"label": "K", "books": books, "line_min": min(lines), "line_max": max(lines), "line_median": med(lines),
         "no_vig_over_min": min(nv) if nv else None, "no_vig_over_max": max(nv) if nv else None,
         "captured_utc": max(x["captured_utc"] for x in quotes),
         "threshold_note": "A posted threshold, not a mean forecast; no-vig over probability is computed only where the same book "
                           "posted both sides at the same line, from that book's own two prices."}
    return s


def team_environment(game, team, captured_utc):
    """Priced scoring environment from books that posted BOTH a spread for the team and a total.
    The capture time is always kept; a missing feed last_update is marked unverified, never an error."""
    per = []
    for bk in game.get("bookmakers", []):
        sp = tt = None
        lu = []
        for mk in bk.get("markets", []):
            for o in mk.get("outcomes", []):
                if mk.get("key") == "spreads" and o.get("name") == team and o.get("point") is not None:
                    sp = o["point"]; lu.append(mk.get("last_update"))
                elif mk.get("key") == "totals" and o.get("name") == "Over" and o.get("point") is not None:
                    tt = o["point"]; lu.append(mk.get("last_update"))
        if sp is not None and tt is not None:
            lu = [x for x in lu if x]
            per.append({"book": BOOK_SHORT.get(bk.get("key"), bk.get("key")), "spread": sp, "total": tt,
                        "last_update_utc": max(lu) if lu else None})
    if not per:
        return {"label": "U", "note": "no book in the saved feed posted both a spread for this team and a total"}
    sp = [p["spread"] for p in per]
    tt = [p["total"] for p in per]
    s, t = med(sp), med(tt)
    lus = [p["last_update_utc"] for p in per if p["last_update_utc"]]
    return {"label": "K", "spread": s, "spread_range": [min(sp), max(sp)], "total": t, "total_range": [min(tt), max(tt)],
            "implied_points": r((t - s) / 2.0, 2), "implied_points_label": "E",
            "books": sorted(str(p["book"]) for p in per), "per_book": per,
            "captured_utc": captured_utc,
            "book_last_update_max_utc": max(lus) if lus else None,
            "update_status": "feed last_update present" if lus else "unverified: the feed gave no last_update; capture time kept",
            "meaning": "the priced post-news scoring environment; not evidence of a preserved offence and not the absence's effect"}


def environment_change(env, pre_news, news_utc):
    """An observed, NONCAUSAL change in the priced environment. Requires two observed captures from the same
    books, the earlier one before both the current capture and the absence news. Otherwise unknown."""
    why = []
    if not pre_news:
        why.append("no pre-news capture supplied")
    else:
        if (env or {}).get("label") != "K" or not isinstance(env.get("implied_points"), (int, float)):
            why.append("the later (current) environment is not observed")
        if pre_news.get("label") != "K" or not isinstance(pre_news.get("implied_points"), (int, float)):
            why.append("the pre-news environment is not an observed value")
        if not pre_news.get("source"):
            why.append("pre-news capture has no source")
        if not pre_news.get("books") or sorted(pre_news.get("books") or []) != sorted((env or {}).get("books") or ["?"]):
            why.append("pre-news and current captures are not from the same books")
        try:
            before, news, after = (datetime.fromisoformat(value.replace("Z", "+00:00")) for value in
                                   (pre_news.get("captured_utc"), news_utc, (env or {}).get("captured_utc")))
            if any(stamp.tzinfo is None for stamp in (before, news, after)) or not before < news < after:
                why.append("the two dated captures must straddle the published absence news")
        except (AttributeError, TypeError, ValueError):
            why.append("capture or absence-news time is missing or invalid")
    if why:
        return {"vs_pre_news": "unknown", "label": "U", "reasons": why,
                "needs": "observed pre-news and post-news spread/total from the same books, captured before and after the news"}
    d = r(env["implied_points"] - pre_news["implied_points"], 2)
    return {"vs_pre_news": d, "label": "E", "pre_news": pre_news,
            "note": "observed change in the priced scoring environment between two same-book captures; noncausal, not the absence's effect"}


def espn_team_context(team_json, opp_json, starter_hist):
    def cat(j, block, name):
        d = {}
        try:
            cats = j["results"]["stats"]["categories"] if block == "stats" else j["results"]["opponent"]
            for c in cats:
                if c["name"] == name:
                    for s in c["stats"]:
                        d[s["name"]] = s.get("value")
        except (KeyError, TypeError):
            pass
        return d
    rush = cat(team_json, "stats", "rushing")
    if not rush.get("rushingAttempts"):
        return {"label": "U", "note": "team stats missing"}
    g = rush.get("teamGamesPlayed")
    att, yds = rush["rushingAttempts"], rush["rushingYards"]
    out = {"label": "K", "source": "ESPN team statistics JSON (saved)", "games": g,
           "rush_att": att, "rush_yds": yds, "rush_att_pg": r(att / g, 2) if g else None, "rush_ypc": r(yds / att, 3),
           "points_pg": rush.get("totalPointsPerGame"),
           "note": "season team context, includes quarterback rushes and every back; it is not any one replacement's efficiency"}
    if opp_json:
        o = cat(opp_json, "opponent", "rushing")
        if o.get("rushingAttempts"):
            out["opp_allowed_ypc"] = r(o["rushingYards"] / o["rushingAttempts"], 3)
            out["opp_allowed_ypg"] = o.get("rushingYardsPerGame")
    if g and starter_hist and starter_hist.get("carries") and starter_hist.get("appearances") == g:
        ea, ey = att - starter_hist["carries"], yds - starter_hist["yards"]
        out["ex_starter_rush"] = {"label": "E", "att": ea, "yds": ey, "ypc": r(ey / ea, 2) if ea > 0 else None,
                                  "note": "team totals minus the absent starter's own game-log totals: every other rusher including quarterbacks"}
    return out


# ---------------------------------------------------------------- the screen (pure)
def _market_median(market, stat):
    m = (market or {}).get("stats", {}).get(stat)
    return m["line_median"] if m else None


def _role_stat(role):
    return ("rush_attempts", "rush_yds") if role == "rushing" else (None, "rec_yds")


def evaluate_candidate(cand, starter_hist, env, role, pre_news, rules=RULES):
    hist = cand.get("history_2026") or {"label": "U", "appearances": 0}
    market = cand.get("market") or {"label": "U", "stats": {}}
    att_stat, out_stat = _role_stat(role)
    c = {}
    thin = (starter_hist.get("appearances") or 0) < rules["starter_min_games"]
    if thin:
        # a starter baseline from too few game rows is not a baseline: every starter comparison is unknown
        why = ("starter baseline unavailable: %d game rows with a stat line in the 2026 log (minimum %d); the log page may be incomplete"
               % (starter_hist.get("appearances") or 0, rules["starter_min_games"]))
        for k in ("workload", "output", "efficiency", "team_expectation") + (("receiving",) if role == "rushing" else ()):
            c[k] = comp("unknown", "U", why, "low")
        return c, "unknown", 0, 5 if role == "rushing" else 4, "low"
    # workload: attempts threshold vs the starter's carries per game (rushing role only)
    att = _market_median(market, "rush_attempts") if att_stat else None
    if att is not None and starter_hist.get("carries_pg"):
        ratio = att / starter_hist["carries_pg"]
        c["workload"] = comp(label_ratio(ratio, rules["workload_band"]), "E",
                             "attempts threshold %s (a ~50%% no-vig marker, not a mean forecast) vs %s carries per game for the starter over %d games (ratio %.2f)"
                             % (att, starter_hist["carries_pg"], starter_hist["appearances"], ratio), "low", ratio=r(ratio, 2))
    else:
        c["workload"] = comp("unknown", "U", "no attempts market and/or no starter carries history; usage share not estimated from yards", "low")
    # output: yards threshold vs the starter's yards per game (volume x efficiency, not separable)
    pg_key = "rush_yds_pg" if role == "rushing" else "rec_yds_pg"
    line = _market_median(market, out_stat)
    if line is not None and starter_hist.get(pg_key):
        ratio = line / starter_hist[pg_key]
        c["output"] = comp(label_ratio(ratio, rules["workload_band"]), "E",
                           "%s threshold %s vs the starter's %s per game over %d games (ratio %.2f); volume and efficiency are combined here"
                           % (out_stat, line, starter_hist[pg_key], starter_hist["appearances"], ratio), "low", ratio=r(ratio, 2))
    else:
        c["output"] = comp("unknown", "U", "no %s market and/or no starter yardage history" % out_stat, "low")
    # efficiency
    key = "ypc" if role == "rushing" else "yds_per_reception"
    n_key = "carries" if role == "rushing" else "receptions"
    cv, sv = hist.get(key), starter_hist.get(key)
    cn, sn = hist.get(n_key) or 0, starter_hist.get(n_key) or 0
    if cv and sv and cn >= rules["efficiency_min_carries"] and sn >= rules["efficiency_min_carries"]:
        ratio = cv / sv
        c["efficiency"] = comp(label_ratio(ratio, rules["efficiency_band"]), "E",
                               "%s %.2f on %d vs the starter's %.2f on %d (ratio %.2f)" % (key, cv, cn, sv, sn, ratio), "medium")
    else:
        c["efficiency"] = comp("unknown", "U",
                               "samples too small or missing for an efficiency verdict (candidate %s on %s, starter %s on %s; minimum %d each)"
                               % (cv, cn, sv, sn, rules["efficiency_min_carries"]), "low")
    # team expectation: only a pre-news counterfactual can show the marginal effect
    cur = env.get("implied_points") if env.get("label") == "K" else None
    # pre_news here is the environment_change() result, never the raw pre-news dict
    d = pre_news.get("vs_pre_news") if isinstance(pre_news, dict) else None
    if isinstance(d, (int, float)) and cur is not None:
        lab = "preserved" if abs(d) <= rules["team_points_band"] else ("weaker" if d < 0 else "stronger")
        c["team_expectation"] = comp(lab, "E", "observed noncausal change in priced implied points between two same-book captures: %+.2f (now %.2f)" % (d, cur), "medium")
    else:
        c["team_expectation"] = comp("unknown", "U", "only the post-news priced environment is available (implied points %s); the injury's marginal effect needs an observed same-book pre-news capture"
                                     % cur, "low")
    # receiving role for backs
    if role == "rushing":
        rl = _market_median(market, "rec_yds")
        if rl is not None and starter_hist.get("rec_yds_pg"):
            ratio = rl / starter_hist["rec_yds_pg"]
            c["receiving"] = comp(label_ratio(ratio, rules["receiving_band"]), "E",
                                  "receiving-yards threshold %s vs the starter's %s per game (ratio %.2f)" % (rl, starter_hist["rec_yds_pg"], ratio), "low", ratio=r(ratio, 2))
        else:
            c["receiving"] = comp("unknown", "U", "no receiving market and/or starter receiving history", "low")
    decision = [c["workload"] if c["workload"]["label"] != "unknown" else c["output"], c["efficiency"], c["team_expectation"]]
    if role == "rushing":
        decision.append(c["receiving"])
    decided = [x["label"] for x in decision if x["label"] != "unknown"]
    if not decided:
        vs = "unknown"
    elif "weaker" in decided and "stronger" in decided:
        vs = "mixed"
    elif "weaker" in decided:
        vs = "weaker"
    elif "stronger" in decided:
        vs = "stronger"
    else:
        vs = "preserved"
    unknown_n = len(decision) - len(decided)
    conf = "low" if (unknown_n >= 2 or (starter_hist.get("appearances") or 0) < rules["starter_min_games"]) else ("medium" if unknown_n == 1 else "high")
    return c, vs, len(decided), len(decision), conf


def priced_status(cand, role, rules=RULES):
    market = cand.get("market") or {}
    hist = cand.get("history_2026") or {}
    if not market.get("stats"):
        return "no_market", None, "no posted market for this player in the saved feed or direct pulls"
    att_stat, out_stat = _role_stat(role)
    if att_stat and "rush_attempts" in market["stats"] and hist.get("carries_pg"):
        line, own, what = market["stats"]["rush_attempts"]["line_median"], hist["carries_pg"], "attempts threshold / own carries per game"
    else:
        pg = hist.get("rush_yds_pg") if role == "rushing" else hist.get("rec_yds_pg")
        st = market["stats"].get(out_stat)
        if not st or not pg:
            return "unknown", None, "no comparable own 2026 average"
        line, own, what = st["line_median"], pg, "%s threshold / own 2026 per-game average" % out_stat
    ratio = line / own
    d = cand.get("role_direction")
    if d == "up":
        s = "priced_in" if ratio >= rules["priced_in_up_ratio"] else ("partly_priced" if ratio >= rules["unpriced_up_ratio"] else "possibly_unpriced")
    elif d == "down":
        s = "priced_in" if ratio <= rules["priced_in_down_ratio"] else ("partly_priced" if ratio <= 1.0 else "possibly_unpriced")
    else:
        return "unknown", r(ratio, 2), "a market exists (%s = %.2f) but no role-change direction was supplied" % (what, ratio)
    return s, r(ratio, 2), "%s = %.2f against a role-%s claim" % (what, ratio, d)


def computed_evidence(cand, starter_hist, role, rules=RULES):
    ev, ce = [], []
    h = cand.get("history_2026") or {}
    mk = (cand.get("market") or {}).get("stats", {})
    if role == "rushing" and h.get("carries") is not None:
        if h["carries"] < rules["efficiency_min_carries"]:
            ce.append({"id": "small_sample", "kind": "hard", "label": "K",
                       "text": "only %d carries in %d game rows with a stat line; his highest single game is %d carries"
                               % (h["carries"], h["appearances"], h["max_carries"] or 0)})
        att = mk.get("rush_attempts", {}).get("line_median")
        if att and h.get("max_carries") is not None and h["max_carries"] < att * 0.6:
            ce.append({"id": "untested_volume", "kind": "hard", "label": "K",
                       "text": "his 2026 high is %d carries; the posted attempts threshold is %s, a volume he has not shown this season" % (h["max_carries"], att)})
    if h.get("rec_yards") and h.get("max_game_rec_yards") and h["max_game_rec_yards"] / h["rec_yards"] >= rules["single_game_share"]:
        ce.append({"id": "receiving_concentration", "kind": "hard", "label": "K",
                   "text": "%d of his %d receiving yards came in one game; the rest averages %.1f per game row"
                           % (h["max_game_rec_yards"], h["rec_yards"], (h["rec_yards"] - h["max_game_rec_yards"]) / max(h["appearances"] - 1, 1))})
    if h.get("appearances", 0) == 0:
        ce.append({"id": "no_2026_rows", "kind": "hard", "label": "K", "text": "no 2026 regular-season game rows with a stat line: %s" % (h.get("error") or "none")})
    return ev, ce


UNAVAILABLE = {"out", "ruled out", "inactive", "injured reserve", "ir", "reserve/injured", "suspended"}
CONDITIONAL = {"questionable", "doubtful", "game-time decision", "game time decision"}


def _status(record):
    return str((record or {}).get("status") or "").strip().casefold()


def screen_team_block(t, rules=RULES, built_utc=None, as_of_utc=None, report_name="replacements/replacement_report_20261115.json"):
    """t is a fully loaded team input. Pure: no file access."""
    role = t.get("role", "rushing")
    absences = t.get("absences", [])
    out = {"team": t["team"], "screen_status": None, "team_context": t.get("team_context"), "priced_environment": t["environment"],
           "marginal_effect_of_absence": {"vs_pre_news": "unknown", "needs": "pre-news spread, total and player lines"},
           "absences": [{k: a[k] for k in ("player", "status", "label", "source", "note") if k in a} for a in absences],
           "starter": None, "candidates": [], "unavailable_candidates": [], "unknowns": list(t.get("unknowns", []))}
    if not absences:
        out["screen_status"] = "unknown_absence"
        out["replacement_context"] = _ctx(t, out, [], "unknown", "unknown", "unscreened", "low", built_utc, as_of_utc, report_name,
                                          "No dated availability record was supplied for this team: its absences are unknown, which is not the same as none.")
        return out
    starter = absences[0]
    sh = starter.get("history_2026") or {"label": "U", "appearances": 0}
    out["starter"] = {"player": starter["player"], "history_2026": sh}
    pre = t.get("pre_news")
    news_utc = (starter.get("source") or {}).get("published_utc")
    chg = environment_change(t["environment"], pre, news_utc)
    if pre:
        out["marginal_effect_of_absence"] = chg
    out_by_name = {a["player"].casefold(): a for a in absences if _status(a) in UNAVAILABLE}
    cands = []
    for candidate in t.get("candidates", []):
        availability = candidate.get("availability")
        excluded = availability if _status(availability) in UNAVAILABLE else out_by_name.get(candidate["player"].casefold())
        if excluded:
            out["unavailable_candidates"].append(dict(candidate, exclusion=excluded,
                exclusion_reason="Unavailable for this game. Prior role reports and prices are retained as evidence."))
        else:
            cands.append(candidate)
    if not cands:
        out["screen_status"] = "unknown_next_man"
        out["unknowns"].append("no next man identified for %s" % starter["player"])
        out["replacement_context"] = _ctx(t, out, [], "unknown", "unknown", "qualify", "low", built_utc, as_of_utc, report_name,
                                          "%s is %s and no next man was identified: replacement role unknown." % (starter["player"], starter.get("status")))
        return out
    out["screen_status"] = "screened"
    nm, labels, statuses, confs = [], [], [], []
    for cd in cands:
        comps, vs, nd, ntot, conf = evaluate_candidate(cd, sh, t["environment"], role, chg, rules)
        availability = _status(cd.get("availability"))
        conditional = availability in CONDITIONAL
        if conditional:
            conf = "low"
        ps, ratio, pbasis = priced_status(cd, role, rules)
        ev, ce = computed_evidence(cd, sh, role, rules)
        o = {"player": cd["player"], "position": cd.get("position", "RB"), "availability": cd.get("availability"),
             "role_evidence": cd.get("role_evidence", []), "role_direction": cd.get("role_direction"),
             "history_2026": cd.get("history_2026"), "market": cd.get("market"),
             "components": comps, "components_decided": "%d of %d" % (nd, ntot), "vs_starter": vs,
             "priced_status": ps, "priced_basis": pbasis, "line_vs_own_average": ratio,
             "evidence": cd.get("evidence", []) + ev, "counterevidence": cd.get("counterevidence", []) + ce,
             "interpretation": cd.get("interpretation", []), "freshness": cd.get("freshness", {}), "unknowns": list(cd.get("unknowns", [])),
             "confidence": conf}
        if not (cd.get("market") or {}).get("stats"):
            o["unknowns"].append("no posted market in the saved feed or direct pulls")
        if (cd.get("history_2026") or {}).get("appearances", 0) == 0:
            o["unknowns"].append("no 2026 game-log stat line")
        if conditional:
            o["unknowns"].append("Game availability is %s. This role depends on the player being active." % availability)
        out["candidates"].append(o)
        nm.append({"player": cd["player"], "vs_starter": vs, "priced_status": ps, "has_market": bool((cd.get("market") or {}).get("stats")),
                   "availability_status": availability or "unknown", "conditional": conditional,
                   "role_claim_kind": next((e["kind"] for e in cd.get("role_evidence", [])), "none")})
        if vs != "unknown":
            labels.append(vs)
        statuses.append(ps)
        confs.append(conf)
    if not labels:
        team_vs = "unknown"
    else:
        team_vs = labels[0] if len(set(labels)) == 1 else "mixed"
    if "possibly_unpriced" in statuses:
        team_ps = "possibly_unpriced"
    elif statuses and all(s == "priced_in" for s in statuses):
        team_ps = "priced_in"
    elif all(s == "no_market" for s in statuses):
        team_ps = "no_market"
    elif any(s in ("partly_priced", "priced_in") for s in statuses):
        team_ps = "partly_priced"
    else:
        team_ps = "unknown"
    team_conf = "low" if ("low" in confs or t.get("committee_possible")) else ("medium" if "medium" in confs else "high")
    flag = "info" if (team_vs in ("preserved", "stronger") and team_ps == "priced_in" and team_conf != "low") else "qualify"
    out["replacement_context"] = _ctx(t, out, nm, team_vs, team_ps, flag, team_conf, built_utc, as_of_utc, report_name, _qualifier(t, out))
    return out


def _qualifier(t, out):
    st = out["starter"]
    sh = st["history_2026"]
    a = out["absences"][0]
    primary = next((c for c in out["candidates"] if (c.get("market") or {}).get("stats")), out["candidates"][0])
    mk = (primary.get("market") or {}).get("stats", {})
    att, ry = mk.get("rush_attempts"), mk.get("rush_yds")
    bits = ["%s is %s" % (a["player"], a.get("status"))]
    if att and sh.get("carries_pg"):
        bits.append("%s's attempts threshold is %s against %s's %s carries per game (a threshold, not a mean forecast)" % (primary["player"], att["line_median"], st["player"], sh["carries_pg"]))
    elif ry and sh.get("rush_yds_pg"):
        bits.append("%s's rush-yards threshold is %s against %s's %s per game over %d games" % (primary["player"], ry["line_median"], st["player"], sh["rush_yds_pg"], sh["appearances"]))
    ph = primary.get("history_2026") or {}
    if ph.get("carries") is not None:
        bits.append("his own 2026 sample is %d carries in %d game rows" % (ph["carries"], ph["appearances"]))
    if t.get("committee_possible"):
        bits.append("a committee outcome is possible")
    for candidate in out["candidates"]:
        status = _status(candidate.get("availability"))
        if status in CONDITIONAL:
            bits.append("%s is %s and must be active for this role" % (candidate["player"], status))
    env = out["priced_environment"]
    if env.get("label") == "K":
        bits.append("the posted total %s is the priced environment, not the effect of the absence" % env["total"])
    return "; ".join(bits) + "."


def _ctx(t, out, next_men, vs, ps, flag, conf, built_utc, as_of_utc, report_name, qualifier):
    return {"schema_version": CTX_SCHEMA, "event_id": t.get("event_id"), "team": t["team"], "built_utc": built_utc, "as_of_utc": as_of_utc,
            "absent": [{"player": a["player"], "status": a.get("status"), "source_published_utc": (a.get("source") or {}).get("published_utc")} for a in out["absences"]],
            "next_men": next_men, "committee_possible": bool(t.get("committee_possible")),
            "vs_starter": vs, "priced_status": ps, "flag": flag, "qualifier": qualifier, "confidence": conf,
            "win_probability_adjustment": None, "auto_upgrade": False, "reorders_issued_calls": False,
            "no_double_count": RULES["no_double_count"], "report": report_name}


# ---------------------------------------------------------------- loading (file access)
def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _src_with_sha(src, base_dir, inputs):
    s = dict(src)
    f = s.get("file")
    if f:
        p = f if os.path.isabs(f) else os.path.join(base_dir, f)
        s["sha256"] = file_sha(p)
        inputs.append({"file": f, "sha256": s["sha256"], "url": s.get("url"), "retrieved_utc": s.get("retrieved_utc")})
    return s


def load_team(spec_team, feed, quotes, game_by_team, base_dir, before_date, inputs, built_utc, as_of_holder):
    team = spec_team["team"]
    game = game_by_team.get(team)
    if not game:
        raise ValueError("team %s is not in the feed" % team)
    env = team_environment(game, team, feed["captured_utc"])
    t = {"team": team, "event_id": game["id"], "role": spec_team.get("role", "rushing"), "environment": env,
         "committee_possible": bool(spec_team.get("committee_possible")), "pre_news": spec_team.get("pre_news"),
         "unknowns": list(spec_team.get("unknowns", [])), "absences": [], "candidates": []}

    def hist_for(p):
        lg = p.get("log")
        if not lg:
            return {"label": "U", "appearances": 0, "error": "no game-log page supplied"}
        src = _src_with_sha(lg, base_dir, inputs)
        parsed = parse_nfl_log(_read(os.path.join(base_dir, lg["file"]) if not os.path.isabs(lg["file"]) else lg["file"]))
        h = history_from_log(parsed, before_date)
        h["source"] = src
        as_of_holder.append(lg.get("retrieved_utc"))
        return h

    for a in spec_team.get("absences", []):
        src = _src_with_sha(a["source"], base_dir, inputs)
        as_of_holder.append(src.get("retrieved_utc"))
        t["absences"].append({"player": a["player"], "status": a["status"], "label": "K", "source": src, "note": a.get("note"),
                              "history_2026": hist_for(a)})
    for c in spec_team.get("candidates", []):
        cd = {"player": c["player"], "position": c.get("position", "RB"), "role_direction": c.get("role_direction"),
              "evidence": [dict(e) for e in c.get("evidence", [])], "counterevidence": [dict(e) for e in c.get("counterevidence", [])],
              "interpretation": [dict(e) for e in c.get("interpretation", [])], "role_evidence": [dict(e) for e in c.get("role_evidence", [])],
              "freshness": c.get("freshness", {}), "unknowns": list(c.get("unknowns", []))}
        for e in cd["role_evidence"] + cd["evidence"] + cd["counterevidence"] + cd["interpretation"]:
            if "source" in e:
                e["source"] = _src_with_sha(e["source"], base_dir, inputs)
                as_of_holder.append(e["source"].get("retrieved_utc"))
        if c.get("availability"):
            cd["availability"] = dict(c["availability"], source=_src_with_sha(c["availability"]["source"], base_dir, inputs))
            as_of_holder.append(cd["availability"]["source"].get("retrieved_utc"))
        cd["history_2026"] = hist_for(c)
        pq = quotes.get(norm(c["player"]), {})
        stats = {}
        for stat, qs in pq.items():
            # keep only the quotes for this event (quotes are keyed per event id by the caller)
            stats[stat] = summarize_market(qs)
        cd["market"] = {"label": "K" if stats else "U", "stats": stats}
        t["candidates"].append(cd)
    # team context
    es = spec_team.get("espn_stats")
    if es:
        tj = json.loads(_read(es["team"] if os.path.isabs(es["team"]) else os.path.join(base_dir, es["team"])))
        oj = None
        if es.get("opponent"):
            oj = json.loads(_read(es["opponent"] if os.path.isabs(es["opponent"]) else os.path.join(base_dir, es["opponent"])))
        for k in ("team", "opponent"):
            if es.get(k):
                pth = es[k] if os.path.isabs(es[k]) else os.path.join(base_dir, es[k])
                inputs.append({"file": es[k], "sha256": file_sha(pth), "retrieved_utc": es.get(k + "_retrieved_utc") or es["retrieved_utc"], "url": es.get(k + "_url")})
        as_of_holder.append(es.get("retrieved_utc"))
        sh = t["absences"][0]["history_2026"] if t["absences"] else None
        t["team_context"] = espn_team_context(tj, oj, sh if sh and sh.get("carries") else None)
    else:
        t["team_context"] = {"label": "U", "note": "no team stats supplied"}
    return t


def screen_slate(spec, base_dir="."):
    """Screen any slate. spec: feed (path) or feed_data (dict), extra_markets (list of {file, event_id?}), teams (list)."""
    built = utc_now()
    inputs, as_of_holder = [], []
    if spec.get("feed_data") is not None:
        feed = spec["feed_data"]
    else:
        fp = spec["feed"] if os.path.isabs(spec["feed"]) else os.path.join(base_dir, spec["feed"])
        feed = json.loads(_read(fp))
        inputs.append({"file": spec["feed"], "sha256": file_sha(fp), "captured_utc": feed.get("captured_utc")})
    as_of_holder.append(feed.get("captured_utc"))
    before = (spec.get("before_date") or (feed["captured_utc"][:10]))  # games on or after this date are not read
    # quotes per event
    ev_quotes = {}
    for ev in feed.get("event_odds", []):
        ev_quotes.setdefault(ev["id"], {})
        for pn, d in collect_quotes(ev.get("bookmakers", []), feed["captured_utc"]).items():
            ev_quotes[ev["id"]].setdefault(pn, {}).update(d)
    for ex in spec.get("extra_markets", []):
        xp = ex["file"] if os.path.isabs(ex["file"]) else os.path.join(base_dir, ex["file"])
        xd = json.loads(_read(xp))
        inputs.append({"file": ex["file"], "sha256": file_sha(xp), "captured_utc": xd.get("captured_utc"), "market": xd.get("market")})
        as_of_holder.append(xd.get("captured_utc"))
        ev = xd["event"]
        for pn, d in collect_quotes(ev.get("bookmakers", []), xd["captured_utc"]).items():
            ev_quotes.setdefault(ev["id"], {}).setdefault(pn, {}).update(d)
    by_event, spec_by_team, unscreened = {}, {}, []
    for st in spec.get("teams", []):
        spec_by_team[st["team"]] = st
    games = feed.get("games") or feed.get("event_odds") or []
    for g in games:
        by_event[g["id"]] = {"event": {"event_id": g["id"], "away_team": g["away_team"], "home_team": g["home_team"], "commence_utc": g["commence_time"]},
                             "teams": {}}
    # build per-event team blocks
    report_name = spec.get("report_name", "replacements/replacement_report_20261115.json")
    built_blocks = []
    for g in games:
        for tm in (g["away_team"], g["home_team"]):
            gb = {tm: g}
            if tm in spec_by_team:
                t = load_team(spec_by_team[tm], feed, ev_quotes.get(g["id"], {}), gb, base_dir, before, inputs, built, as_of_holder)
                built_blocks.append((g["id"], tm, t))
            else:
                t = {"team": tm, "event_id": g["id"], "environment": team_environment(g, tm, feed["captured_utc"]), "absences": [], "candidates": [],
                     "team_context": {"label": "U", "note": "no team stats supplied"}, "unknowns": ["no dated availability record supplied"]}
                built_blocks.append((g["id"], tm, t))
    as_of = max(x for x in as_of_holder if x)
    for eid, tm, t in built_blocks:
        by_event[eid]["teams"][tm] = screen_team_block(t, RULES, built, as_of, report_name)
    for eid, e in by_event.items():
        if all(tb["screen_status"] == "unknown_absence" for tb in e["teams"].values()):
            unscreened.append(eid)
    return {"schema_version": SCHEMA_VERSION, "report_id": spec.get("report_id", "replacement_report"), "built_utc": built, "as_of_utc": as_of,
            "paper_only": True, "advisory_only": True, "inputs": inputs, "rules": RULES, "by_event": by_event,
            "unscreened_events": unscreened,
            "unknowns": ["A team without a dated availability record is reported as unknown_absence, never as 'no absence'.",
                         "Snaps, routes, targets and goal-line shares are not in the public pages used; unknown unless a spec supplies them.",
                         "Final inactives (about 90 minutes before kickoff) supersede every availability record here."]}


def replacement_context(report, team=None, player=None, event_id=None):
    """Return the replacement_context object for a team or player; an explicit unscreened object if nothing matches."""
    tn = norm(team) if team else None
    pn = norm(player) if player else None
    for eid, e in report["by_event"].items():
        if event_id and eid != event_id:
            continue
        for name, tb in e["teams"].items():
            if tn and norm(name) != tn:
                continue
            if pn:
                names = [norm(c["player"]) for c in tb["candidates"]] + [norm(a["player"]) for a in tb["absences"]]
                if pn not in names:
                    continue
            return tb["replacement_context"]
    return {"schema_version": CTX_SCHEMA, "event_id": event_id, "team": team, "vs_starter": "unknown", "priced_status": "unknown", "flag": "unscreened",
            "qualifier": "Not found in the report: unknown, not 'no absence'.", "confidence": "low", "win_probability_adjustment": None,
            "auto_upgrade": False, "reorders_issued_calls": False, "no_double_count": RULES["no_double_count"]}


def main(argv):
    if len(argv) != 3:
        print("usage: next_man_up.py <spec.json> <report.json>")
        return 2
    spec_path = os.path.abspath(argv[1])
    spec = json.loads(_read(spec_path))
    rep = screen_slate(spec, os.path.dirname(os.path.dirname(spec_path)))  # spec sits in replacements/cases/
    with open(argv[2], "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1, sort_keys=False)
        f.write("\n")
    for eid, e in rep["by_event"].items():
        for tm, tb in e["teams"].items():
            if tb["screen_status"] != "unknown_absence":
                c = tb["replacement_context"]
                print("%s: %s | vs_starter=%s priced=%s flag=%s conf=%s" % (tm, tb["screen_status"], c["vs_starter"], c["priced_status"], c["flag"], c["confidence"]))
    print("events", len(rep["by_event"]), "unscreened events", len(rep["unscreened_events"]), "as_of", rep["as_of_utc"], "built", rep["built_utc"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
