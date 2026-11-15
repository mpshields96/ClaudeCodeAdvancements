#!/usr/bin/env python3
"""Build nfl/slate/slate_20261115.json from saved captures. One self-contained, stdlib-only file.

Run (from anywhere, absolute paths):
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I build_slate.py \
     --out slate_20261115.json --espn-summary-dir inputs/espn-summary.<UTC> \
     --espn-stats-dir inputs/espn-team-statistics.<UTC> --espn-depth-dir inputs/espn-depthcharts.<UTC> \
     --nfl-injuries-dir inputs/nfl-com-injuries-reg10.<UTC> --odds-shared <sunday-odds.json> \
     --health <NFL_SUNDAY_HEALTH.json> --lines <nfl-public-lines.json> --games-csv <games.csv>

Rules this script follows (BRIEF.md guards): no network, no future information, nothing estimated or filled
from memory. A value that cannot be read from a saved source goes into that game's `missing` list.
Evidence labels: known = read from a source; derived = arithmetic on known source values (formula named);
unknown = missing or the sources conflict. The only `estimated` label is the inactives-time window
(a timing rule, not a data value).
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

SEASON = 2026
BEFORE = "2026-11-15"  # only games with gameday < this count as history
SOURCE_NFL_VERSION = "nflverse games.csv"
NV_TO_ESPN = {"LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR", "WAS": "WSH"}
ESPN_TO_NV = {"LAR": "LA"}
OFF_SLOTS = set(["qb", "rb", "fb", "wr1", "wr2", "wr3", "te", "te2", "lt", "lg", "c", "rg", "rt"])
ST_SLOTS = set(["pk", "k", "p", "ls", "kr", "pr", "h"])
POS = (r"(?:OLB|ILB|MLB|EDGE|FB|QB|RB|WR|TE|OT|OG|OL|DL|DE|DT|NT|LB|CB|SS|FS|DB|LS|PK|KR|PR|C|G|T|S|K|P)")
HEALTH_ENTRY = re.compile(r"(?:(?P<pos>" + POS + r")\s+)?(?P<name>[A-Z][^(),]*?)\s*\((?P<inj>[^)]*)\)")
SEVERITY = {"Out": 0, "Doubtful": 1, "Questionable": 2}

WARNINGS = []
SOURCES = []
SRC_BY_KEY = {}


def warn(msg):
    WARNINGS.append(msg)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def zt(s):
    """Normalise a UTC timestamp string to YYYY-MM-DDTHH:MM:SSZ."""
    if not s:
        return None
    s = str(s)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?", s)
    if not m:
        return s
    return "%sT%s:%s:%sZ" % (m.group(1), m.group(2), m.group(3), m.group(4) or "00")


def add_source(path, url, retrieved_utc, role, sha=None, extra=None):
    key = os.path.abspath(path)
    if key in SRC_BY_KEY:
        return SRC_BY_KEY[key]
    sid = "S%d" % (len(SOURCES) + 1)
    rec = {
        "id": sid,
        "role": role,
        "url": url,
        "retrieved_utc": retrieved_utc,
        "sha256": sha or sha256_file(path),
        "local_file": key,
    }
    if extra:
        rec.update(extra)
    SOURCES.append(rec)
    SRC_BY_KEY[key] = sid
    return sid


def norm_name(s):
    s = (s or "").lower().replace(".", "").replace("'", "").replace("’", "").replace("-", " ")
    parts = [p for p in re.split(r"\s+", s.strip()) if p]
    while parts and parts[-1] in ("jr", "sr", "ii", "iii", "iv", "v"):
        parts.pop()
    return " ".join(parts)


def last_first(s):
    p = norm_name(s).split(" ")
    if not p or not p[0]:
        return ("", "")
    return (p[-1], p[0][0])


def fnum(x):
    try:
        if x is None or str(x).strip() == "":
            return None
        return float(x)
    except Exception:
        return None


def rnd(x, n=2):
    return None if x is None else round(x, n)


def load_capture(folder, role):
    mpath = os.path.join(folder, "MANIFEST.json")
    man = load_json(mpath)
    out = {}
    for e in man["files"]:
        if e.get("error") or e.get("http_status") != 200:
            warn("capture %s file %s not usable: status=%s error=%s" % (folder, e.get("file"), e.get("http_status"), e.get("error")))
            continue
        p = os.path.join(folder, e["file"])
        sha = sha256_file(p)
        if sha != e["sha256"]:
            warn("sha256 mismatch for %s (manifest %s, disk %s)" % (p, e["sha256"], sha))
        sid = add_source(p, e["url"], e["retrieved_utc"], role, sha=sha, extra={"manifest": mpath})
        out[e["file"]] = {"path": p, "entry": e, "sid": sid}
    return out


# ---------------------------------------------------------------- NFL.com injury table parser
class NflInjuryParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.team = None
        self.in_sub = False
        self.in_sub_span = False
        self.sub_buf = ""
        self.in_tr = False
        self.in_cell = False
        self.buf = ""
        self.cells = []
        self.href = None
        self.rows = []
        self.sections = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "div" and "d3-o-section-sub-title" in cls:
            self.in_sub = True
        elif tag == "span" and self.in_sub:
            self.in_sub_span = True
            self.sub_buf = ""
        elif tag == "tr":
            self.in_tr = True
            self.cells = []
            self.href = None
        elif tag in ("td", "th") and self.in_tr:
            self.in_cell = True
            self.buf = ""
        elif tag == "a" and self.in_cell and (a.get("href") or "").startswith("/players/"):
            self.href = a.get("href")

    def handle_endtag(self, tag):
        if tag == "span" and self.in_sub_span:
            self.team = " ".join(self.sub_buf.split())
            self.sections.append(self.team)
            self.in_sub_span = False
            self.in_sub = False
        elif tag in ("td", "th") and self.in_cell:
            self.cells.append(" ".join(self.buf.split()))
            self.in_cell = False
        elif tag == "tr" and self.in_tr:
            if self.team and len(self.cells) >= 5 and self.cells[0] != "Player":
                self.rows.append({
                    "team_nick": self.team, "player": self.cells[0], "position": self.cells[1],
                    "injury": self.cells[2], "practice": self.cells[3], "game_status": self.cells[4],
                    "href": self.href,
                })
            self.in_tr = False

    def handle_data(self, d):
        if self.in_cell:
            self.buf += d
        if self.in_sub_span:
            self.sub_buf += d


def parse_health_text(text):
    """Return ([ (pos, name, injury) ... ], warnings) from a Codex health string."""
    out = []
    w = []
    if not text:
        return out, w
    for m in HEALTH_ENTRY.finditer(text):
        name = m.group("name").strip()
        if not name:
            continue
        out.append((m.group("pos"), name, (m.group("inj") or "").strip()))
    n_paren = text.count("(")
    if n_paren != len(out):
        w.append("health parse: %d '(' but %d entries parsed in: %s" % (n_paren, len(out), text[:160]))
    return out, w


# ---------------------------------------------------------------- nflverse history
def one_game(r, nv):
    home = r["home_team"] == nv
    hs = int(r["home_score"])
    as_ = int(r["away_score"])
    pf, pa = (hs, as_) if home else (as_, hs)
    su = "W" if pf > pa else ("L" if pf < pa else "T")
    sl = fnum(r["spread_line"])
    tl = fnum(r["total_line"])
    if sl is None:
        ats = None
    else:
        m = (hs - as_) - sl
        v = m if home else -m
        ats = "W" if v > 0 else ("L" if v < 0 else "P")
    tot = hs + as_
    ou = None if tl is None else ("O" if tot > tl else ("U" if tot < tl else "P"))
    venue = "neutral" if r["location"] == "Neutral" else ("home" if home else "away")
    opp = r["away_team"] if home else r["home_team"]
    if r.get("result", "") != "" and int(float(r["result"])) != hs - as_:
        warn("result column disagrees with scores for %s" % r["game_id"])
    return {
        "game_id": r["game_id"], "week": int(r["week"]), "gameday": r["gameday"],
        "opponent": NV_TO_ESPN.get(opp, opp), "venue": venue,
        "team_score": pf, "opp_score": pa, "su": su,
        "team_spread_line": None if sl is None else (-sl if home else sl),
        "spread_line_home_positive": sl, "ats": ats,
        "total_line": tl, "total": tot, "ou": ou,
        "team_qb": r["home_qb_name"] if home else r["away_qb_name"],
        "opp_qb": r["away_qb_name"] if home else r["home_qb_name"],
    }


def summarize(gs):
    n = len(gs)
    su = [sum(1 for g in gs if g["su"] == k) for k in ("W", "L", "T")]
    ats = [sum(1 for g in gs if g["ats"] == k) for k in ("W", "L", "P")]
    ou = [sum(1 for g in gs if g["ou"] == k) for k in ("O", "U", "P")]
    pf = sum(g["team_score"] for g in gs)
    pa = sum(g["opp_score"] for g in gs)
    return {
        "games": n,
        "su": "%d-%d-%d" % tuple(su),
        "ats": "%d-%d-%d" % tuple(ats),
        "ou": "%d-%d-%d" % tuple(ou),
        "ats_games_missing": sum(1 for g in gs if g["ats"] is None),
        "ou_games_missing": sum(1 for g in gs if g["ou"] is None),
        "pf_total": pf, "pa_total": pa,
        "pf_per_game": rnd(pf / float(n)) if n else None,
        "pa_per_game": rnd(pa / float(n)) if n else None,
    }


# ---------------------------------------------------------------- ESPN stats
def cat_stat(cats, cat, name):
    for c in cats or []:
        if c.get("name") == cat:
            for s in c.get("stats", []):
                if s.get("name") == name:
                    return s
    return None


def build_stats_block(tfile, rec):
    t = load_json(tfile)
    r = t.get("results") or {}
    own = (r.get("stats") or {}).get("categories") or []
    opp = r.get("opponent") or []
    url = rec["entry"]["url"]
    ret = rec["entry"]["retrieved_utc"]
    games = None
    g = cat_stat(own, "passing", "teamGamesPlayed")
    if g:
        games = g["value"]
    season = (t.get("season") or {}).get("year")
    missing = []

    def known(cats, cat, name, label_name=None):
        s = cat_stat(cats, cat, name)
        if s is None:
            missing.append("%s.%s" % (cat, name))
            return None
        return {"value": s["value"], "label": "known", "espn_field": "%s.%s" % (cat, name),
                "source_url": url, "retrieved_utc": ret}

    def per_game(total_item, field):
        if total_item is None or not games:
            return None
        return {"value": rnd(total_item["value"] / float(games), 3), "label": "derived",
                "formula": "%s / teamGamesPlayed" % field, "espn_field": field,
                "source_url": url, "retrieved_utc": ret}

    def ratio(num, den, field):
        if num is None or den is None or not den["value"]:
            return None
        return {"value": rnd(num["value"] / float(den["value"]), 3), "label": "derived",
                "formula": field, "source_url": url, "retrieved_utc": ret}

    off = {}
    off["games_played"] = known(own, "passing", "teamGamesPlayed")
    off["points_total"] = known(own, "scoring", "totalPoints")
    off["points_per_game"] = per_game(off["points_total"], "scoring.totalPoints")
    off["total_yards"] = known(own, "rushing", "totalYards")
    off["total_plays"] = known(own, "rushing", "totalOffensivePlays")
    off["yards_per_game"] = per_game(off["total_yards"], "rushing.totalYards")
    off["yards_per_play"] = ratio(off["total_yards"], off["total_plays"], "rushing.totalYards / rushing.totalOffensivePlays")
    off["pass_yards_total"] = known(own, "passing", "passingYards")
    off["pass_yards_per_game"] = per_game(off["pass_yards_total"], "passing.passingYards")
    off["yards_per_pass_attempt"] = known(own, "passing", "yardsPerPassAttempt")
    off["rush_yards_total"] = known(own, "rushing", "rushingYards")
    off["rush_yards_per_game"] = per_game(off["rush_yards_total"], "rushing.rushingYards")
    off["yards_per_rush"] = known(own, "rushing", "yardsPerRushAttempt")
    off["giveaways_total"] = known(own, "miscellaneous", "totalGiveaways")
    off["giveaways_per_game"] = per_game(off["giveaways_total"], "miscellaneous.totalGiveaways")
    off["turnover_differential"] = known(own, "miscellaneous", "turnOverDifferential")
    off["third_down_pct"] = known(own, "miscellaneous", "thirdDownConvPct")
    off["redzone_scoring_pct"] = known(own, "miscellaneous", "redzoneScoringPct")
    off["redzone_touchdown_pct"] = known(own, "miscellaneous", "redzoneTouchdownPct")
    off["sacks_taken"] = known(own, "passing", "sacks")
    off["sacks_taken_per_game"] = per_game(off["sacks_taken"], "passing.sacks")

    de = {}
    de["points_allowed_total"] = known(opp, "scoring", "totalPoints")
    de["points_allowed_per_game"] = per_game(de["points_allowed_total"], "opponent.scoring.totalPoints")
    de["yards_allowed_total"] = known(opp, "rushing", "totalYards")
    de["plays_faced"] = known(opp, "rushing", "totalOffensivePlays")
    de["yards_allowed_per_game"] = per_game(de["yards_allowed_total"], "opponent.rushing.totalYards")
    de["yards_allowed_per_play"] = ratio(de["yards_allowed_total"], de["plays_faced"], "opponent.rushing.totalYards / opponent.rushing.totalOffensivePlays")
    de["pass_yards_allowed_total"] = known(opp, "passing", "passingYards")
    de["pass_yards_allowed_per_game"] = per_game(de["pass_yards_allowed_total"], "opponent.passing.passingYards")
    de["rush_yards_allowed_total"] = known(opp, "rushing", "rushingYards")
    de["rush_yards_allowed_per_game"] = per_game(de["rush_yards_allowed_total"], "opponent.rushing.rushingYards")
    de["yards_per_rush_allowed"] = known(opp, "rushing", "yardsPerRushAttempt")
    de["yards_per_pass_attempt_allowed"] = known(opp, "passing", "yardsPerPassAttempt")
    de["third_down_pct_allowed"] = known(opp, "miscellaneous", "thirdDownConvPct")
    de["redzone_scoring_pct_allowed"] = known(opp, "miscellaneous", "redzoneScoringPct")
    de["redzone_touchdown_pct_allowed"] = known(opp, "miscellaneous", "redzoneTouchdownPct")
    de["takeaways_total"] = known(own, "miscellaneous", "totalTakeaways")
    de["takeaways_per_game"] = per_game(de["takeaways_total"], "miscellaneous.totalTakeaways")
    de["sacks_made"] = known(own, "defensive", "sacks")
    de["sacks_made_per_game"] = per_game(de["sacks_made"], "defensive.sacks")
    return {
        "season": season,
        "games_played": games,
        "source_url": url, "retrieved_utc": ret, "source_id": rec["sid"],
        "offense": off, "defense": de,
        "rank_note": "ESPN feed carries no league ranks; ranks are derived in league_ranks from per-game values across the captured teams (label: derived).",
        "missing": missing,
    }


# ---------------------------------------------------------------- derived league ranks
# (block, metric, direction): "high" = a larger value ranks better (rank 1 = best), "low" = a smaller value ranks better.
RANK_METRICS = [
    ("offense", "points_per_game", "high"), ("offense", "yards_per_game", "high"), ("offense", "yards_per_play", "high"),
    ("offense", "pass_yards_per_game", "high"), ("offense", "rush_yards_per_game", "high"),
    ("offense", "third_down_pct", "high"), ("offense", "giveaways_per_game", "low"),
    ("defense", "points_allowed_per_game", "low"), ("defense", "yards_allowed_per_game", "low"),
    ("defense", "yards_allowed_per_play", "low"), ("defense", "pass_yards_allowed_per_game", "low"),
    ("defense", "rush_yards_allowed_per_game", "low"), ("defense", "third_down_pct_allowed", "low"),
    ("defense", "takeaways_per_game", "high"), ("defense", "sacks_made_per_game", "high"),
]


def compute_ranks(all_blocks):
    """all_blocks: team id -> build_stats_block() result for every team with a capture.
    Returns team id -> {"offense": {metric: {...}}, "defense": {...}}. Competition ranking (ties share a rank)."""
    out = dict((tid, {"offense": {}, "defense": {}}) for tid in all_blocks)
    for blk, metric, direction in RANK_METRICS:
        vals = {}
        for tid, st in all_blocks.items():
            item = (st.get(blk) or {}).get(metric)
            if item is not None and item.get("value") is not None:
                vals[tid] = item["value"]
        for tid, v in vals.items():
            better = [x for x in vals.values() if (x > v if direction == "high" else x < v)]
            out[tid][blk][metric] = {"rank": len(better) + 1, "of": len(vals), "value": v,
                                     "direction": "higher is better" if direction == "high" else "lower is better"}
    return out


# ---------------------------------------------------------------- club QB announcement check
# Expected starters come from the club page titles (verified below against the captured page text);
# a page that does not name the starter and a start sentence leaves the QB label unchanged.
CLUB_QB_EXPECT = {"ARI": "Carson Beck", "CLE": "Deshaun Watson", "LV": "Fernando Mendoza",
                  "MIA": "Kyle McCord", "MIN": "Kirk Cousins", "SEA": "Drew Lock"}
HEALTH_WORDS = ("limited", "injur", "oblique", "elbow", "questionable", "concussion", "illness", "did not practice", "dnp")


def check_club_page(path, full_name):
    import html as _html
    raw = open(path, encoding="utf-8", errors="replace").read()
    mt = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    title = re.sub(r"\s+", " ", _html.unescape(mt.group(1))).strip() if mt else None
    body = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", raw)
    txt = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", body)))
    last = full_name.split(" ")[-1]
    mentions = len(re.findall(r"\b%s\b" % re.escape(last), txt))
    full_found = full_name in txt
    sents = [x for x in re.split(r"(?<=[.!?])\s+", txt) if re.search(r"\b%s\b" % re.escape(last), x)]
    start_sent = [x for x in sents if re.search(r"\b(start|starts|starter|starting)\b", x, re.I)]
    health = sorted(set(w for x in sents for w in HEALTH_WORDS if w in x.lower()))
    return {"page_title": title, "full_name_found": full_found, "last_name_mentions": mentions,
            "start_sentence_found": bool(start_sent), "health_words_in_sentences_naming_starter": health}


# ---------------------------------------------------------------- ESPN depth chart
def build_depth(dfile, rec):
    d = load_json(dfile)
    best = {}  # athlete id -> placement
    qbs = []
    for form in d.get("depthchart", []):
        for slot, pos in (form.get("positions") or {}).items():
            unit = "offense" if slot in OFF_SLOTS else ("special_teams" if slot in ST_SLOTS else "defense")
            for i, a in enumerate(pos.get("athletes") or []):
                aid = str(a.get("id"))
                entry = {"unit": unit, "formation": form.get("name"), "slot": slot, "order": i,
                         "espn_athlete_id": aid, "name": a.get("displayName"),
                         "depth_injury_flags": a.get("injuries") or []}
                cur = best.get(aid)
                if cur is None or (i < cur["order"]):
                    best[aid] = entry
                if slot == "qb":
                    qbs.append({"name": a.get("displayName"), "order": i, "espn_athlete_id": aid,
                                "depth_injury_flags": a.get("injuries") or []})
    seen = set()
    qb_list = []
    for q in sorted(qbs, key=lambda x: x["order"]):
        if q["espn_athlete_id"] not in seen:
            seen.add(q["espn_athlete_id"])
            qb_list.append(q)
    return {"by_id": best, "qbs": qb_list, "source_id": rec["sid"], "url": rec["entry"]["url"],
            "retrieved_utc": rec["entry"]["retrieved_utc"], "timestamp": d.get("timestamp")}


# ---------------------------------------------------------------- ESPN summary
def parse_summary(path, rec):
    s = load_json(path)
    comp = s["header"]["competitions"][0]
    teams = {}
    for c in comp["competitors"]:
        t = c["team"]
        teams[c["homeAway"]] = {"id": str(t["id"]), "abbr": t["abbreviation"], "name": t.get("name"),
                                "display": t.get("displayName")}
    inj = {}
    for blk in s.get("injuries") or []:
        tid = str((blk.get("team") or {}).get("id"))
        rows = []
        for e in blk.get("injuries") or []:
            a = e.get("athlete") or {}
            det = e.get("details") or {}
            rows.append({
                "espn_athlete_id": str(a.get("id")), "player": a.get("displayName") or a.get("fullName"),
                "position": (a.get("position") or {}).get("abbreviation"), "status": e.get("status"),
                "date": zt(e.get("date")), "type": det.get("type"), "location": det.get("location"),
                "detail": det.get("detail"), "side": det.get("side"), "return_date": det.get("returnDate"),
            })
        inj[tid] = rows
    overall = {}
    for grp in (s.get("standings") or {}).get("groups") or []:
        for e in (grp.get("standings") or {}).get("entries") or []:
            for st in e.get("stats") or []:
                if st.get("name") == "overall":
                    overall[str(e.get("id"))] = st.get("displayValue")
    leaders = {}
    for blk in s.get("leaders") or []:
        tid = str((blk.get("team") or {}).get("id"))
        rows = []
        for cat in blk.get("leaders") or []:
            lst = cat.get("leaders") or []
            if not lst:
                continue
            ld = lst[0]
            ath = ld.get("athlete") or {}
            rows.append({"category": cat.get("name"), "player": ath.get("displayName"),
                         "position": (ath.get("position") or {}).get("abbreviation"),
                         "value": ld.get("displayValue"), "espn_athlete_id": str(ath.get("id"))})
        leaders[tid] = rows
    wx = (s.get("gameInfo") or {}).get("weather")
    return {"event_id": str(s["header"]["id"]), "date": zt(comp.get("date")), "neutral": bool(comp.get("neutralSite")),
            "weather": wx if isinstance(wx, dict) and wx else None,
            "teams": teams, "injuries": inj, "overall": overall, "leaders": leaders,
            "source_id": rec["sid"], "url": rec["entry"]["url"], "retrieved_utc": rec["entry"]["retrieved_utc"]}


# ---------------------------------------------------------------- shared odds
def american(x):
    if x is None:
        return None
    s = str(x).strip()
    try:
        return int(s.replace("+", ""))
    except Exception:
        return None


def book_quote(b):
    q = {"book_key": b["key"], "book": b.get("title"), "last_update": zt(b.get("last_update")),
         "ml": None, "spread": None, "total": None}
    for m in b.get("markets", []):
        lu = zt(m.get("last_update"))
        o = m.get("outcomes", [])
        if m["key"] == "h2h":
            q["ml"] = {"outcomes": dict((x["name"], x["price"]) for x in o), "last_update": lu}
        elif m["key"] == "spreads":
            q["spread"] = {"outcomes": dict((x["name"], (x["price"], x.get("point"))) for x in o), "last_update": lu}
        elif m["key"] == "totals":
            q["total"] = {"outcomes": dict((x["name"], (x["price"], x.get("point"))) for x in o), "last_update": lu}
    return q


def build_cross_book(og, home_full, away_full, src_id, captured):
    books = []
    for b in og.get("bookmakers", []):
        q = book_quote(b)
        row = {"book_key": q["book_key"], "book": q["book"], "last_update": q["last_update"]}
        if q["ml"]:
            row["ml"] = {"home": q["ml"]["outcomes"].get(home_full), "away": q["ml"]["outcomes"].get(away_full),
                         "last_update": q["ml"]["last_update"]}
        if q["spread"]:
            h = q["spread"]["outcomes"].get(home_full) or (None, None)
            a = q["spread"]["outcomes"].get(away_full) or (None, None)
            row["spread"] = {"home_line": h[1], "home_price": h[0], "away_line": a[1], "away_price": a[0],
                             "last_update": q["spread"]["last_update"]}
        if q["total"]:
            ov = q["total"]["outcomes"].get("Over") or (None, None)
            un = q["total"]["outcomes"].get("Under") or (None, None)
            row["total"] = {"line": ov[1] if ov[1] is not None else un[1], "over_price": ov[0], "under_price": un[0],
                            "last_update": q["total"]["last_update"]}
        books.append(row)

    def best_of(items, side_price_key):
        """items = [(book, price, last_update)] -> best (highest) price with ties listed."""
        items = [i for i in items if i[1] is not None]
        if not items:
            return None
        mx = max(i[1] for i in items)
        top = [i for i in items if i[1] == mx]
        return {"price": mx, "books": [t[0] for t in top], "last_update": top[0][2],
                "last_updates": dict((t[0], t[2]) for t in top)}

    best = {"ml": {}, "spread": [], "total": []}
    for side in ("home", "away"):
        best["ml"][side] = best_of([(b["book_key"], b["ml"][side], b["ml"]["last_update"]) for b in books if b.get("ml")], side)
    groups = {}
    for b in books:
        if b.get("spread") and b["spread"]["home_line"] is not None:
            groups.setdefault(b["spread"]["home_line"], []).append(b)
    for hl in sorted(groups, key=lambda k: (-len(groups[k]), k)):
        g = groups[hl]
        best["spread"].append({
            "home_line": hl, "away_line": g[0]["spread"]["away_line"], "n_books": len(g),
            "books": [b["book_key"] for b in g],
            "home": best_of([(b["book_key"], b["spread"]["home_price"], b["spread"]["last_update"]) for b in g], "home"),
            "away": best_of([(b["book_key"], b["spread"]["away_price"], b["spread"]["last_update"]) for b in g], "away"),
        })
    groups = {}
    for b in books:
        if b.get("total") and b["total"]["line"] is not None:
            groups.setdefault(b["total"]["line"], []).append(b)
    for ln in sorted(groups, key=lambda k: (-len(groups[k]), k)):
        g = groups[ln]
        best["total"].append({
            "line": ln, "n_books": len(g), "books": [b["book_key"] for b in g],
            "over": best_of([(b["book_key"], b["total"]["over_price"], b["total"]["last_update"]) for b in g], "over"),
            "under": best_of([(b["book_key"], b["total"]["under_price"], b["total"]["last_update"]) for b in g], "under"),
        })
    return {
        "source_id": src_id, "captured_utc": captured, "label": "known",
        "note": ("Shared Codex capture of the LA books (Odds API format). Best price = highest American price among the "
                 "books quoting the same line; spreads and totals are grouped by line because prices at different lines "
                 "are not comparable. Each quote keeps its own last_update."),
        "odds_event_id": og.get("id"), "commence_time": zt(og.get("commence_time")),
        "books": books, "best": best,
        "line_dispersion": {"spread_home_lines": sorted(set(b["spread"]["home_line"] for b in books if b.get("spread"))),
                            "total_lines": sorted(set(b["total"]["line"] for b in books if b.get("total")))},
    }


def parse_dk_snapshot(g, lines_path, lines_sid, missing):
    bk = None
    for b in g.get("book_references", []):
        if b.get("book") == "DraftKings":
            bk = b
            break
    if bk is None:
        missing.append("DraftKings display snapshot absent from nfl-public-lines file")
        return None
    mk = {}
    for m in bk["markets"]:
        mk[(m["market"], m["side"])] = m

    def pr(key):
        m = mk.get(key)
        return american(m["american_price"]) if m else None

    def ln(key):
        m = mk.get(key)
        if not m or m.get("line") in (None, ""):
            return None
        return fnum(re.sub(r"^[ou]", "", str(m["line"])))

    snap = {
        "book": "DraftKings", "observed_utc": zt(bk["observed_utc"]), "source_file": lines_path, "source_id": lines_sid,
        "ml": {"home": pr(("moneyline", "home")), "away": pr(("moneyline", "away"))},
        "spread": {"home_line": ln(("pointSpread", "home")), "home_price": pr(("pointSpread", "home")),
                   "away_line": ln(("pointSpread", "away")), "away_price": pr(("pointSpread", "away"))},
        "total": {"line": ln(("total", "over")), "over_price": pr(("total", "over")), "under_price": pr(("total", "under"))},
        "local_availability_verified": bool(bk.get("local_availability_verified")),
        "label": ("known: ESPN display price of DraftKings, observed %s. Not a confirmed Louisiana quote. The shared %s capture "
                  "in odds.cross_book is the live-price source." % (zt(bk["observed_utc"]), "06:55Z")),
    }
    for k, v in (("ml.home", snap["ml"]["home"]), ("ml.away", snap["ml"]["away"]), ("spread.home_line", snap["spread"]["home_line"]),
                 ("total.line", snap["total"]["line"])):
        if v is None:
            missing.append("DraftKings snapshot value missing: %s" % k)
    return snap


# ---------------------------------------------------------------- main build
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--espn-summary-dir", required=True)
    ap.add_argument("--espn-stats-dir", required=True)
    ap.add_argument("--espn-depth-dir", required=True)
    ap.add_argument("--nfl-injuries-dir", required=True)
    ap.add_argument("--odds-shared", required=True)
    ap.add_argument("--health", required=True)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--games-csv", required=True)
    ap.add_argument("--espn-stats-extra-dir", default=None,
                    help="capture of ESPN team statistics for teams not on the slate; used only to derive 32-team ranks")
    ap.add_argument("--club-qb-dir", default=None,
                    help="capture of club QB announcement pages (<TEAM>.html); verifies the starter named for the six flagged teams")
    ap.add_argument("--games-csv-retrieved-utc", default="2026-11-14T21:16:58Z")
    ap.add_argument("--built-utc", default=None)
    a = ap.parse_args()

    built_utc = a.built_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---- load sources
    summ_cap = load_capture(a.espn_summary_dir, "espn_summary")
    stats_cap = load_capture(a.espn_stats_dir, "espn_team_statistics")
    depth_cap = load_capture(a.espn_depth_dir, "espn_depthchart")
    nfl_cap = load_capture(a.nfl_injuries_dir, "nfl_com_injury_report")

    lines = load_json(a.lines)
    lines_sid = add_source(a.lines, "file:" + os.path.abspath(a.lines), zt(lines.get("capture_complete_utc")), "dk_display_lines",
                           extra={"note": "ESPN-displayed DraftKings lines; upstream url " + str((lines.get("games") or [{}])[0].get("source_url"))})
    odds = load_json(a.odds_shared)
    odds_sid = add_source(a.odds_shared, "file:" + os.path.abspath(a.odds_shared), zt(odds.get("captured_utc")), "shared_odds_capture",
                          extra={"note": "Codex shared Sunday odds capture (Odds API format, LA books). No Odds API call was made by this lane."})
    health = load_json(a.health)
    health_sid = add_source(a.health, health.get("url"), zt(health.get("captured_utc")), "codex_health",
                            extra={"note": "Codex capture of the NFL.com week 10 injury report text; file note: " + str(health.get("note"))})
    csv_sid = add_source(a.games_csv, "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv",
                         a.games_csv_retrieved_utc, "nflverse_games")
    with open(a.games_csv, newline="", encoding="utf-8") as f:
        nv_rows = list(csv.DictReader(f))

    # ---- parse ESPN summaries
    summaries = {}
    for fn, rec in sorted(summ_cap.items()):
        if not fn.startswith("event_") or not fn.endswith(".json"):
            continue
        ps = parse_summary(rec["path"], rec)
        summaries[ps["event_id"]] = ps
    team_by_id = {}
    for ps in summaries.values():
        for side in ("home", "away"):
            t = ps["teams"][side]
            team_by_id[t["id"]] = t
    nick_to_id = dict((t["name"].upper(), tid) for tid, t in team_by_id.items())
    display_to_id = dict((t["display"], tid) for tid, t in team_by_id.items())

    # ---- ESPN stats and depth charts
    stats = {}
    for fn, rec in stats_cap.items():
        m = re.match(r"^team_(\d+)\.json$", fn)
        if m:
            stats[m.group(1)] = build_stats_block(rec["path"], rec)
    depth = {}
    for fn, rec in depth_cap.items():
        m = re.match(r"^team_(\d+)\.json$", fn)
        if m:
            depth[m.group(1)] = build_depth(rec["path"], rec)

    # ---- derived 32-team ranks (slate teams plus the extra capture of the other teams)
    extra_stats = {}
    extra_sids = []
    if a.espn_stats_extra_dir:
        extra_cap = load_capture(a.espn_stats_extra_dir, "espn_team_statistics_nonslate")
        for fn, rec in extra_cap.items():
            m = re.match(r"^team_(\d+)\.json$", fn)
            if m:
                extra_stats[m.group(1)] = build_stats_block(rec["path"], rec)
                extra_sids.append(rec["sid"])
    all_stat_blocks = dict(extra_stats)
    all_stat_blocks.update(stats)
    ranks = compute_ranks(all_stat_blocks)
    n_ranked = len(all_stat_blocks)
    if n_ranked != 32:
        warn("league ranks computed over %d teams, not 32" % n_ranked)

    # ---- club QB announcement captures (optional)
    club = {}
    if a.club_qb_dir:
        club_cap = load_capture(a.club_qb_dir, "club_qb_announcement")
        for fn, rec in club_cap.items():
            m = re.match(r"^([A-Z]{2,3})\.html$", fn)
            if m and m.group(1) in CLUB_QB_EXPECT:
                chk = check_club_page(rec["path"], CLUB_QB_EXPECT[m.group(1)])
                chk.update({"team": m.group(1), "expected_starter": CLUB_QB_EXPECT[m.group(1)], "source_url": rec["entry"]["url"],
                            "retrieved_utc": rec["entry"]["retrieved_utc"], "http_status": rec["entry"]["http_status"],
                            "sha256": rec["entry"]["sha256"], "source_id": rec["sid"]})
                chk["verified"] = bool(chk["full_name_found"] and chk["start_sentence_found"])
                club[m.group(1)] = chk

    # ---- NFL.com injury report
    nfl_rec = nfl_cap.get("nfl_injuries_reg10.html")
    parser = NflInjuryParser()
    with open(nfl_rec["path"], "r", encoding="utf-8", errors="replace") as f:
        parser.feed(f.read())
    nfl_rows_by_team = {}
    for r in parser.rows:
        tid = nick_to_id.get(r["team_nick"].upper())
        if tid:
            nfl_rows_by_team.setdefault(tid, []).append(r)
    nfl_total_rows = len(parser.rows)

    # ---- games list: lines-file games that have an ESPN summary
    games_src = [g for g in lines["games"] if g["event_id"] in summaries]
    games_src.sort(key=lambda g: (g["kickoff_utc"], g["event_id"]))
    if len(games_src) != 12:
        warn("expected 12 Sunday games, found %d" % len(games_src))
    odds_games = {}
    for og in odds["games"]:
        odds_games[(og["home_team"], og["away_team"])] = og

    # ---- helper: nflverse rows
    def nv_code(abbr):
        return ESPN_TO_NV.get(abbr, abbr)

    def hist(abbr):
        c = nv_code(abbr)
        gs = []
        for r in nv_rows:
            if r["season"] != str(SEASON) or r["game_type"] != "REG":
                continue
            if r["home_score"] == "" or r["away_score"] == "" or r["gameday"] >= BEFORE:
                continue
            if r["home_team"] == c or r["away_team"] == c:
                gs.append(r)
        gs.sort(key=lambda r: (r["gameday"], int(r["week"])))
        return [one_game(r, c) for r in gs]

    def upcoming_row(h_abbr, a_abbr):
        for r in nv_rows:
            if r["season"] == str(SEASON) and r["home_score"] == "" and r["home_team"] == nv_code(h_abbr) and r["away_team"] == nv_code(a_abbr):
                return r
        return None

    def h2h(h_abbr, a_abbr):
        pair = set([h_abbr, a_abbr])
        out = []
        for r in nv_rows:
            try:
                season = int(r["season"])
            except Exception:
                continue
            if season < 2016 or r["home_score"] == "" or r["gameday"] >= BEFORE:
                continue
            h = NV_TO_ESPN.get(r["home_team"], r["home_team"])
            aw = NV_TO_ESPN.get(r["away_team"], r["away_team"])
            if set([h, aw]) != pair:
                continue
            out.append({"season": season, "week": int(r["week"]), "game_type": r["game_type"], "gameday": r["gameday"],
                        "home": h, "away": aw, "home_score": int(r["home_score"]), "away_score": int(r["away_score"]),
                        "neutral": r["location"] == "Neutral", "spread_line_home_positive": fnum(r["spread_line"]),
                        "total_line": fnum(r["total_line"]), "nflverse_game_id": r["game_id"]})
        out.sort(key=lambda x: (x["gameday"], x["week"]), reverse=True)
        return out

    # ---- injuries per team
    def build_team_injuries(tid, abbr):
        rows = {}  # key -> row

        def find(name, pos, aid=None):
            if aid:
                for k, r in rows.items():
                    if r.get("espn_athlete_id") == aid:
                        return k
            nk = norm_name(name)
            if nk in rows:
                return nk
            ln, fi = last_first(name)
            cand = [k for k, r in rows.items() if last_first(r["player"]) == (ln, fi) and (not pos or not r["position"] or r["position"] == pos)]
            if len(cand) == 1:
                return cand[0]
            cand = [k for k, r in rows.items() if last_first(r["player"])[0] == ln and pos and r["position"] == pos]
            if len(cand) == 1:
                return cand[0]
            return None

        def new_row(name, pos, aid=None):
            k = norm_name(name)
            if k in rows:
                k = k + "#2"
            rows[k] = {"team": abbr, "player": name, "position": pos, "espn_athlete_id": aid,
                       "codex_health": None, "nfl_com": None, "espn": None, "depth_chart": None}
            return k

        # 1) Codex health (first, per coordinator)
        hs = (health.get("team_status") or {}).get(team_by_id[tid]["name"].upper())
        if hs is None:
            warn("health file has no entry for %s" % team_by_id[tid]["name"])
        else:
            for key, txt in hs.items():
                entries, w = parse_health_text(txt)
                for x in w:
                    warn("%s %s: %s" % (abbr, key, x))
                for pos, name, inj in entries:
                    k = find(name, pos) or new_row(name, pos)
                    rows[k]["position"] = rows[k]["position"] or pos
                    rows[k]["codex_health"] = {"status": key.capitalize(), "injury": inj, "as_of_utc": zt(health.get("captured_utc")),
                                               "source_url": health.get("url"), "source_id": health_sid}
        # 2) NFL.com HTML table
        for r in nfl_rows_by_team.get(tid, []):
            has_flag = bool(r["injury"] or r["game_status"] or not r["practice"].lower().startswith("full"))
            if not has_flag:
                continue
            k = find(r["player"], r["position"]) or new_row(r["player"], r["position"])
            rows[k]["position"] = rows[k]["position"] or r["position"]
            rows[k]["nfl_com"] = {"injury": r["injury"] or None, "practice_status": r["practice"] or None,
                                  "game_status": r["game_status"] or None, "as_of_utc": nfl_rec["entry"]["retrieved_utc"],
                                  "as_of_basis": "retrieval time; the page carries no publication timestamp",
                                  "source_url": nfl_rec["entry"]["url"], "source_id": nfl_rec["sid"]}
        # 3) ESPN summary injuries
        ps = None
        for p in summaries.values():
            if tid in p["injuries"]:
                ps = p
                break
        if ps is not None:
            for r in ps["injuries"][tid]:
                if not r["player"]:
                    continue
                k = find(r["player"], r["position"], r["espn_athlete_id"]) or new_row(r["player"], r["position"], r["espn_athlete_id"])
                rows[k]["espn_athlete_id"] = r["espn_athlete_id"]
                rows[k]["position"] = rows[k]["position"] or r["position"]
                rows[k]["espn"] = {"status": r["status"], "as_of_utc": r["date"], "type": r["type"], "detail": r["detail"],
                                   "location": r["location"], "side": r["side"], "return_date": r["return_date"],
                                   "source_url": ps["url"], "retrieved_utc": ps["retrieved_utc"], "source_id": ps["source_id"]}
        # 4) depth chart and leaders enrichment
        dp = depth.get(tid)
        leaders = {}
        for p in summaries.values():
            if tid in p["leaders"]:
                leaders = p["leaders"][tid]
        for k, r in rows.items():
            placement = None
            if dp is not None:
                if r.get("espn_athlete_id") and r["espn_athlete_id"] in dp["by_id"]:
                    placement = dp["by_id"][r["espn_athlete_id"]]
                else:
                    ln, fi = last_first(r["player"])
                    cands = [v for v in dp["by_id"].values() if last_first(v["name"]) == (ln, fi)]
                    if len(cands) == 1:
                        placement = cands[0]
                if placement:
                    r["depth_chart"] = {"unit": placement["unit"], "formation": placement["formation"], "slot": placement["slot"],
                                        "order": placement["order"], "first_string": placement["order"] == 0,
                                        "depth_injury_flags": placement["depth_injury_flags"],
                                        "source_url": dp["url"], "retrieved_utc": dp["retrieved_utc"], "source_id": dp["source_id"]}
            lead = [l["category"] for l in leaders if l.get("espn_athlete_id") == r.get("espn_athlete_id") or
                    (l.get("player") and norm_name(l["player"]) == norm_name(r["player"]))]
            r["stat_leader_categories"] = lead
        # finalise rows
        final = []
        for k, r in rows.items():
            ch, nf, es = r["codex_health"], r["nfl_com"], r["espn"]
            stat_candidates = []
            if ch:
                stat_candidates.append(("codex_health", ch["status"]))
            if nf and nf["game_status"]:
                stat_candidates.append(("nfl_com", nf["game_status"]))
            if es and es["status"]:
                stat_candidates.append(("espn", es["status"]))
            if stat_candidates:
                status, basis = stat_candidates[0][1], stat_candidates[0][0]
            else:
                status, basis = "No designation", "none"

            def canon(s):
                s = (s or "").lower()
                return {"day-to-day": "questionable"}.get(s, s)

            vals = set(canon(v) for _, v in stat_candidates)
            conflict = len(vals) > 1
            r["status"] = status
            r["status_basis"] = basis
            r["status_by_source"] = dict(stat_candidates)
            r["status_conflict"] = conflict
            r["evidence"] = "unknown" if conflict else ("known" if stat_candidates else "known")
            r["evidence_note"] = ("sources disagree on game status; treat as unknown until the inactives" if conflict else
                                  ("status read from %s" % basis if stat_candidates else "listed with practice or injury note only; no game designation in any source"))
            r["practice"] = nf["practice_status"] if nf else None
            r["practice_label"] = "known (NFL.com, retrieval time as-of)" if nf else "unknown (no NFL.com row; ESPN carries no practice data)"
            primary = {"codex_health": ch, "nfl_com": nf, "espn": es}.get(basis)
            r["report_utc"] = (primary or {}).get("as_of_utc") or (nf or {}).get("as_of_utc") or (es or {}).get("as_of_utc")
            r["source_url"] = (primary or {}).get("source_url") or (nf or {}).get("source_url") or (es or {}).get("source_url")
            r["source_ids"] = sorted(set(x["source_id"] for x in (ch, nf, es, r["depth_chart"]) if x))
            flags = []
            if r["position"] == "QB":
                flags.append("QB")
            dc = r["depth_chart"]
            if dc and dc["first_string"] and dc["unit"] in ("offense", "defense"):
                flags.append("first_string_" + dc["unit"])
            if r["stat_leader_categories"]:
                flags.append("team_stat_leader")
            r["key_flags"] = flags
            r["key_starter"] = bool(flags)
            r["open_at_inactives"] = status in ("Questionable", "Doubtful") or basis == "none"
            final.append(r)
        final.sort(key=lambda r: (SEVERITY.get(r["status"], 3), not r["key_starter"], r["player"]))
        return final

    # ---- build games
    games_out = []
    team_cache = {}
    for g in games_src:
        eid = g["event_id"]
        ps = summaries[eid]
        h, aw = ps["teams"]["home"], ps["teams"]["away"]
        missing = []
        src_ids = [ps["source_id"], lines_sid, odds_sid, health_sid, csv_sid, nfl_rec["sid"]]
        kick = zt(g["kickoff_utc"])
        if ps["date"] != kick:
            warn("kickoff mismatch for %s: lines %s vs ESPN summary %s" % (eid, kick, ps["date"]))
        neutral = bool(g.get("neutral_site"))
        urow = upcoming_row(h["abbr"], aw["abbr"])
        if urow is None:
            missing.append("nflverse upcoming schedule row not found for %s at %s" % (aw["abbr"], h["abbr"]))
        else:
            if (urow["location"] == "Neutral") != neutral:
                warn("neutral flag mismatch lines vs nflverse for %s" % eid)
        kdt = datetime.strptime(kick, "%Y-%m-%dT%H:%M:%SZ")
        inactives = (kdt - timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # odds
        snap = parse_dk_snapshot(g, a.lines, lines_sid, missing)
        og = odds_games.get((h["display"], aw["display"]))
        cross = None
        if og is None:
            missing.append("shared odds capture has no event for %s at %s" % (aw["display"], h["display"]))
        else:
            if zt(og["commence_time"]) != kick:
                warn("commence_time mismatch for %s: shared %s vs ESPN %s" % (eid, zt(og["commence_time"]), kick))
            cross = build_cross_book(og, h["display"], aw["display"], odds_sid, zt(odds.get("captured_utc")))
        baseline = None
        if urow is not None:
            sl = fnum(urow["spread_line"])
            baseline = {"source_id": csv_sid, "label": "known (nflverse schedule row; prior-day snapshot, may differ from current prices)",
                        "retrieved_utc": a.games_csv_retrieved_utc, "nflverse_game_id": urow["game_id"],
                        "home_spread": None if sl is None else -sl, "spread_line_home_positive": sl,
                        "total_line": fnum(urow["total_line"]), "home_moneyline": american(urow["home_moneyline"]),
                        "away_moneyline": american(urow["away_moneyline"]),
                        "home_spread_odds": american(urow["home_spread_odds"]), "away_spread_odds": american(urow["away_spread_odds"]),
                        "over_odds": american(urow["over_odds"]), "under_odds": american(urow["under_odds"])}
        odds_blk = dict(snap or {})
        odds_blk["cross_book"] = cross
        odds_blk["nflverse_baseline"] = baseline

        teams_out = {}
        inj_all = []
        game_caveats = []
        for side, tinfo in (("home", h), ("away", aw)):
            tid = tinfo["id"]
            abbr = tinfo["abbr"]
            if tid in team_cache and False:
                pass
            hg = hist(abbr)
            tot = summarize(hg)
            venue_split = {}
            for v in ("home", "away", "neutral"):
                venue_split[v] = summarize([x for x in hg if x["venue"] == v])
            last4 = [dict((k, x[k]) for k in ("week", "gameday", "opponent", "venue", "team_score", "opp_score", "su",
                                               "team_spread_line", "ats", "total_line", "total", "ou", "game_id")) for x in hg[-4:]]
            tmissing = []
            if tot["ats_games_missing"]:
                tmissing.append("%s: spread line missing in nflverse for %d completed 2026 game(s); ATS record excludes them" % (abbr, tot["ats_games_missing"]))
            if tot["ou_games_missing"]:
                tmissing.append("%s: total line missing in nflverse for %d completed 2026 game(s); O/U record excludes them" % (abbr, tot["ou_games_missing"]))
            # records crosscheck
            espn_rec = None
            for p in summaries.values():
                if tid in p["overall"]:
                    espn_rec = p["overall"][tid]
            nv_su = "%s" % tot["su"]
            wl = [int(x) for x in nv_su.split("-")]
            nv_short = "%d-%d" % (wl[0], wl[1]) if wl[2] == 0 else "%d-%d-%d" % tuple(wl)
            rec_ok = (espn_rec == nv_short) if espn_rec else None
            if espn_rec and not rec_ok:
                tmissing.append("%s: nflverse record %s disagrees with ESPN standings %s (unresolved)" % (abbr, nv_short, espn_rec))
            # rest, QB
            rest = None
            if urow is not None:
                rest = fnum(urow["home_rest"] if side == "home" else urow["away_rest"])
            lastday = hg[-1]["gameday"] if hg else None
            since = None
            if lastday:
                since = (datetime.strptime(BEFORE, "%Y-%m-%d") - datetime.strptime(lastday, "%Y-%m-%d")).days
            listed_qb = (urow["home_qb_name"] if side == "home" else urow["away_qb_name"]) if urow is not None else None
            last_qb = {"name": hg[-1]["team_qb"], "game_id": hg[-1]["game_id"], "gameday": hg[-1]["gameday"],
                       "label": "known (nflverse row of the latest completed game)"} if hg else None
            inj = build_team_injuries(tid, abbr)
            dp = depth.get(tid)
            dp_qbs = dp["qbs"] if dp else []
            qb_rows = [r for r in inj if r["position"] == "QB"]
            reasons = []
            names = {}
            if listed_qb:
                names["nflverse_week10_listed"] = listed_qb
            if last_qb:
                names["nflverse_last_start"] = last_qb["name"]
            if dp_qbs:
                names["espn_depth_chart_first"] = dp_qbs[0]["name"]
            lasts = set(last_first(v)[0] for v in names.values() if v)
            if len(lasts) > 1:
                reasons.append("QB name differs across sources: " + "; ".join("%s=%s" % (k, v) for k, v in sorted(names.items())))
            # a QB injury row counts as a conflict only when the QB is the listed or the depth-chart-first QB;
            # an injured third-stringer or a different quarterback in the room is recorded as a room note.
            lead_last = set(last_first(v)[0] for k, v in names.items() if v and k != "nflverse_last_start")
            room_notes = []
            for qr in qb_rows:
                if qr["status"] in SEVERITY or qr["status"] not in ("No designation",):
                    if last_first(qr["player"])[0] in lead_last:
                        reasons.append("QB injury row: %s %s (%s)" % (qr["player"], qr["status"], qr["status_basis"]))
                    else:
                        room_notes.append("QB-room injury row (not the listed or depth-chart-first QB): %s %s (%s)" % (qr["player"], qr["status"], qr["status_basis"]))
            dp_flags = dp_qbs[0]["depth_injury_flags"] if dp_qbs else []
            if dp_flags:
                reasons.append("ESPN depth chart carries an injury/news flag on %s (dated %s; full text in depth_chart_flags)" % (
                    dp_qbs[0]["name"], ", ".join(str(f.get("date")) for f in dp_flags if isinstance(f, dict)) or "unknown"))
            qb_blk = {"names_by_source": names, "espn_depth_chart_qbs": [x["name"] for x in dp_qbs],
                      "injury_rows": [{"player": r["player"], "status": r["status"], "status_by_source": r["status_by_source"],
                                       "practice": r["practice"]} for r in qb_rows],
                      "depth_chart_flags": dp_flags,
                      "room_notes": room_notes,
                      "conflict": bool(reasons), "conflict_reasons": reasons,
                      "label": "unknown" if reasons else "known",
                      "note": "unknown = sources disagree or the listed/depth-chart QB carries an injury designation; confirm at the inactives"}
            tcaveats = []
            ca = club.get(abbr)
            if ca is not None:
                qb_blk["club_announcement"] = dict(ca, label=("known (club page captured by this lane names the starter and a start sentence)"
                                                              if ca["verified"] else "unknown (club page captured, starter not confirmed in its text)"),
                                                   note="Page text is checked by name and keyword only; no page text is copied. Announcement predates the inactives.")
                src_ids.append(ca["source_id"])
            if reasons and ca is not None and ca["verified"]:
                qb_blk["label"] = "known"
                qb_blk["label_basis"] = "club announcement (own capture) names %s as the starter; source conflicts kept in conflict_reasons" % ca["expected_starter"]
                qb_blk["note"] = "known = the club's own page names the starter; nflverse/ESPN listings that disagree are kept in conflict_reasons. Still confirm at the inactives."
                tcaveats.append("%s: starter per club announcement is %s; nflverse or ESPN listings disagreed (%s). Confirm at the inactives." % (
                    abbr, ca["expected_starter"], " | ".join(reasons)))
                if ca["health_words_in_sentences_naming_starter"]:
                    tcaveats.append("%s: club page sentences naming %s carry health words: %s" % (
                        abbr, ca["expected_starter"], ", ".join(ca["health_words_in_sentences_naming_starter"])))
            elif reasons:
                tmissing.append("%s: starting QB unresolved - %s" % (abbr, " | ".join(reasons)))
            counts = {}
            for r in inj:
                counts[r["status"]] = counts.get(r["status"], 0) + 1
            first_out = [r["player"] for r in inj if r["status"] in ("Out", "Injured Reserve") and any(f.startswith("first_string") for f in r["key_flags"])]
            first_q = [r["player"] for r in inj if r["status"] in ("Doubtful", "Questionable") and any(f.startswith("first_string") for f in r["key_flags"])]
            st = stats.get(tid)
            if st is None:
                tmissing.append("%s: ESPN team statistics missing" % abbr)
            else:
                if st["season"] != SEASON:
                    tmissing.append("%s: ESPN statistics season is %s, not %d" % (abbr, st["season"], SEASON))
                if st["missing"]:
                    tmissing.append("%s: ESPN stat fields absent: %s" % (abbr, ", ".join(st["missing"])))
                if st["games_played"] is not None and int(st["games_played"]) != tot["games"]:
                    tmissing.append("%s: ESPN games played %s vs nflverse completed games %d (stat totals may include a different set of games)" % (abbr, st["games_played"], tot["games"]))
            teams_out[side] = {
                "team": abbr, "name": tinfo["display"], "espn_team_id": tid, "nflverse_code": nv_code(abbr),
                "record_basis": "2026 regular season, completed games before %s, nflverse games.csv (label: known)" % BEFORE,
                "games_played": tot["games"], "su": tot["su"], "ats": tot["ats"], "ou": tot["ou"],
                "ats_games_missing": tot["ats_games_missing"], "ou_games_missing": tot["ou_games_missing"],
                "pf_per_game": tot["pf_per_game"], "pa_per_game": tot["pa_per_game"],
                "pf_total": tot["pf_total"], "pa_total": tot["pa_total"],
                "points_label": "derived: sum of nflverse scores / games",
                "espn_standings_overall": espn_rec, "record_crosscheck_ok": rec_ok,
                "last_four": last4, "last_four_order": "oldest first",
                "rest_days": rest, "rest_days_label": "known (nflverse home_rest/away_rest on the upcoming row)",
                "days_since_last_game": since, "last_game_date": lastday,
                "splits": venue_split,
                "qb_last_start": last_qb, "qb_week10_listed": listed_qb,
                "qb_depth_chart": [{"name": x["name"], "order": x["order"], "depth_injury_flags": x["depth_injury_flags"]} for x in dp_qbs],
                "qb": qb_blk,
                "offense": (st or {}).get("offense"), "defense": (st or {}).get("defense"),
                "league_ranks": None if tid not in ranks else {
                    "label": "derived: rank among %d teams with ESPN season statistics captured, from per-game values; rank 1 = best; ties share a rank" % n_ranked,
                    "offense": ranks[tid]["offense"], "defense": ranks[tid]["defense"],
                    "games_played_note": "per-game values, so teams with a different games-played count (a bye or Thursday game) are comparable"},
                "stats_provenance": None if st is None else {"source_url": st["source_url"], "retrieved_utc": st["retrieved_utc"],
                                                              "source_id": st["source_id"], "season": st["season"],
                                                              "games_played": st["games_played"], "rank_note": st["rank_note"]},
                "injury_summary": {"counts_by_status": counts, "first_string_out_or_ir": first_out,
                                   "first_string_questionable_or_doubtful": first_q},
                "leaders_espn": [l for p in summaries.values() for l in p["leaders"].get(tid, [])],
                "missing": tmissing,
                "caveats": tcaveats,
            }
            if st:
                src_ids.append(st["source_id"])
            if dp:
                src_ids.append(dp["source_id"])
            inj_all.extend(inj)
            missing.extend(tmissing)
            game_caveats.extend(tcaveats)

        # NFL.com sections absent for a slate team?
        for side in ("home", "away"):
            if not nfl_rows_by_team.get(teams_out[side]["espn_team_id"]):
                missing.append("%s: no NFL.com injury table rows parsed" % teams_out[side]["team"])
        missing.append("final inactives (released about 90 minutes before kickoff, expected near %s): every Questionable and Doubtful status below is still open" % inactives)
        missing.append("NFL.com injury report publication time (page has no timestamp; retrieval time %s used as the as-of)" % nfl_rec["entry"]["retrieved_utc"])
        missing.append("practice participation for rows absent from the NFL.com table (ESPN carries none)")
        # weather: ESPN summary gameInfo.weather (keyless public feed); no units or forecast hour are stated by the feed
        roof_val = (urow or {}).get("roof") or None
        wx = ps.get("weather")
        if wx:
            wlink = wx.get("link") if isinstance(wx.get("link"), dict) else {}
            weather_blk = {
                "label": "known (ESPN summary gameInfo.weather values, as served); unit reading is an assumption",
                "temperature": wx.get("temperature"), "high_temperature": wx.get("highTemperature"), "low_temperature": wx.get("lowTemperature"),
                "gust": wx.get("gust"), "precipitation": wx.get("precipitation"), "condition_id": wx.get("conditionId"),
                "condition_id_note": "ESPN code only; the feed gives no text for it, so no description is given",
                "unit_assumption": "feed states no units; read as degrees F, mph and percent chance of precipitation (assumption, not stated by the source)",
                "forecast_hour_stated": False,
                "forecast_link": wlink.get("href"),
                "source_id": ps["source_id"], "source_url": ps.get("url"), "retrieved_utc": ps.get("retrieved_utc"),
                "roof_nflverse": roof_val,
                "roof_note": ("nflverse roof value is %s; weather applies only if the roof is open" % roof_val) if roof_val
                             else "nflverse roof value is blank for this game; whether the roof is open is not captured",
            }
        else:
            weather_blk = {"label": "unknown (ESPN summary carries no weather object for this game)", "roof_nflverse": roof_val}
        if not wx:
            missing.append("weather: ESPN summary has no weather object for this game")
        else:
            missing.append("weather forecast hour and units are not stated by the ESPN feed (values are read as F/mph/percent by assumption)")
        if not roof_val:
            missing.append("roof status: blank in nflverse for this game and not given by ESPN")
        if neutral and roof_val:
            missing.append("roof status %s for the neutral-site game is the nflverse value, not independently verified" % roof_val)
        missing.append("Louisiana availability of the DraftKings display price (unverified); use odds.cross_book from the shared capture")

        game = {
            "event_id": eid, "odds_event_id": (og or {}).get("id"), "nflverse_game_id": (urow or {}).get("game_id"),
            "kickoff_utc": kick, "inactives_expected_utc": inactives,
            "inactives_label": "estimated (rule of thumb: about 90 minutes before kickoff; not a sourced time)",
            "home": h["abbr"], "away": aw["abbr"], "home_name": h["display"], "away_name": aw["display"],
            "neutral": neutral, "venue": g.get("venue"),
            "nflverse_context": None if urow is None else {"roof": urow.get("roof") or None, "div_game": urow.get("div_game") or None,
                                                              "home_coach": urow.get("home_coach") or None, "away_coach": urow.get("away_coach") or None,
                                                              "label": "known (nflverse schedule row)"},
            "odds": odds_blk,
            "weather": weather_blk,
            "teams": teams_out,
            "h2h": h2h(h["abbr"], aw["abbr"]),
            "h2h_basis": "completed games 2016 through %s including postseason, nflverse games.csv" % BEFORE,
            "injuries": inj_all,
            "injuries_note": ("Rows combine the Codex copy of the NFL.com report (06:38Z), the NFL.com page (retrieval time as-of) and ESPN summary "
                              "injuries. Players on the NFL.com table with full practice, no injury and no designation are left out."),
            "source_ids": sorted(set(src_ids + extra_sids), key=lambda s: int(s[1:])),
            "caveats": game_caveats,
            "missing": missing,
        }
        games_out.append(game)

    # ---- assemble
    out = {
        "built_utc": built_utc, "slate_date": "2026-11-15", "season": SEASON,
        "purpose": "Inputs for the Sunday Nov 15 2026 NFL picker. Paper and advisory only.",
        "label_legend": {"known": "read from a cited source", "derived": "arithmetic on known source values, formula named",
                         "unknown": "missing or sources conflict", "estimated": "used only for the inactives time rule; no data value is estimated"},
        "as_of": {"espn_summary_retrieved_utc": sorted(set(r["entry"]["retrieved_utc"] for r in summ_cap.values()))[-1],
                  "espn_team_stats_retrieved_utc": sorted(set(r["entry"]["retrieved_utc"] for r in stats_cap.values()))[-1],
                  "espn_depth_retrieved_utc": sorted(set(r["entry"]["retrieved_utc"] for r in depth_cap.values()))[-1],
                  "nfl_com_injuries_retrieved_utc": nfl_rec["entry"]["retrieved_utc"],
                  "codex_health_captured_utc": zt(health.get("captured_utc")),
                  "shared_odds_captured_utc": zt(odds.get("captured_utc")),
                  "dk_display_lines_observed_utc": zt(lines.get("capture_complete_utc")),
                  "nflverse_games_retrieved_utc": a.games_csv_retrieved_utc},
        "sources": SOURCES,
        "builder": {"script": "nfl/slate/tools/build_slate.py", "warnings": WARNINGS},
        "games": games_out,
    }
    # ---- validate
    problems = []
    if len(games_out) != 12:
        problems.append("expected 12 games, got %d" % len(games_out))
    abbrs = set()
    for g in games_out:
        for k in ("event_id", "kickoff_utc", "home", "away", "odds", "teams", "h2h", "injuries", "missing"):
            if g.get(k) in (None, ""):
                problems.append("%s missing field %s" % (g.get("event_id"), k))
        for side in ("home", "away"):
            t = g["teams"][side]
            abbrs.add(t["team"])
            for k in ("su", "ats", "ou", "pf_per_game", "pa_per_game", "last_four", "offense", "defense"):
                if t.get(k) in (None, ""):
                    problems.append("%s %s missing %s" % (g["event_id"], t["team"], k))
            if len(t["last_four"]) != 4:
                problems.append("%s %s last_four has %d" % (g["event_id"], t["team"], len(t["last_four"])))
        if not g["odds"].get("cross_book"):
            problems.append("%s has no cross_book odds" % g["event_id"])
    if len(abbrs) != 24:
        problems.append("expected 24 distinct teams, got %d" % len(abbrs))
    out["builder"]["validation_problems"] = problems
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=False)
        f.write("\n")
    print("wrote %s (%d bytes)" % (a.out, os.path.getsize(a.out)))
    print("games=%d teams=%d sources=%d warnings=%d problems=%d" % (len(games_out), len(abbrs), len(SOURCES), len(WARNINGS), len(problems)))
    for w in WARNINGS:
        print("WARN", w)
    for p in problems:
        print("PROBLEM", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
