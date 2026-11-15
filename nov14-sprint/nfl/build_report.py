#!/usr/bin/env python3
"""Build the NFL paper desk results sheet (one HTML file with inline SVG).

Every number on the sheet is read from files this lane produced:
  results/backtest_results.json   (written by backtest.py)
  frozen_rules.json               (written by backtest.py, first run)
  data/raw/games.csv              (downloaded data, hash-checked here)
  ledger/ledger.jsonl             (written by paper_ledger.py generate)
The slate's rule calls are recomputed with rules.py and compared with the
ledger; a mismatch refuses the build. Stdlib only, Python 3.9 compatible.

Run from the CCA root:
  python3 -I nov14-sprint/nfl/build_report.py
Then print to PDF with headless Chrome (command in STATUS.md).
"""
import csv
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
import rules  # noqa: E402

OUT_DIR = os.path.join(HERE, "report")
OUT_HTML = os.path.join(OUT_DIR, "NFL_Paper_Desk.html")
W = 476

INK, INK2, MUTED, FAINT, RULE = "#1b222b", "#49515b", "#636a72", "#9a9fa5", "#e5e3dd"
COOL, COOL_L, WARM, WARM_L, RANGE = "#0e5e8a", "#8fb5cd", "#c56c21", "#e9bd96", "#bfc3c8"
SERIF = "Charter, 'Iowan Old Style', Georgia, serif"
SANS = "'Avenir Next', Avenir, Seravek, 'Gill Sans', sans-serif"

PLAIN = {
    "HOME_DOG": "Home underdogs",
    "BIG_DOG": "Any big underdog",
    "REST_EDGE": "Team with more rest",
    "HIGH_TOTAL_UNDER": "Under on high totals",
}
SHORT = {
    "HOME_DOG": "home dog",
    "BIG_DOG": "big dog",
    "REST_EDGE": "rest",
    "HIGH_TOTAL_UNDER": "under",
}


class Refused(Exception):
    pass


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pct(x, d=1):
    return ("%." + str(d) + "f%%") % (100.0 * x)


def spct(x, d=1):
    return ("%+." + str(d) + "f%%") % (100.0 * x)


def rule_phrase(fam, value):
    v = "%g" % float(value)
    if fam == "HOME_DOG":
        return "Home underdogs getting %s or more points" % v
    if fam == "BIG_DOG":
        return "Any underdog getting %s or more points" % v
    if fam == "REST_EDGE":
        return "The team with %s or more extra rest days" % v
    return "Under, when the total is %s or higher" % v


def rule_label(fam, value):
    v = "%g" % float(value)
    if fam == "HOME_DOG":
        return "Home underdogs, %s+ points" % v
    if fam == "BIG_DOG":
        return "Any underdog, %s+ points" % v
    if fam == "REST_EDGE":
        return "%s+ more rest days" % v
    return "Under, total %s+" % v


# ---------- inputs ----------

def load_inputs():
    with open(os.path.join(HERE, "results", "backtest_results.json")) as f:
        res = json.load(f)
    with open(os.path.join(HERE, "frozen_rules.json")) as f:
        frozen = json.load(f)
    with open(os.path.join(HERE, "data", "raw", "MANIFEST.json")) as f:
        man = json.load(f)["files"][0]
    path = os.path.join(HERE, "data", "raw", "games.csv")
    with open(path, "rb") as f:
        raw = f.read()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != man["sha256"]:
        raise Refused("INPUT_HASH_MISMATCH games.csv is not the manifest file")
    if frozen["data_sha256"] != sha:
        raise Refused("FROZEN_DATA_MISMATCH rules were frozen on other data")
    games = list(csv.DictReader(raw.decode("utf-8").splitlines()))
    return res, frozen, man, games


def num(s):
    if s is None or s == "" or s == "NA":
        return None
    return float(s)


def slate_games(games):
    """All games in the earliest week that still has an unplayed game."""
    open_ = [g for g in games if g["game_type"] == "REG" and num(g["home_score"]) is None
             and num(g["spread_line"]) is not None]
    if not open_:
        raise Refused("NO_SLATE no unplayed regular-season game with a line")
    season = min(int(g["season"]) for g in open_)
    week = min(int(g["week"]) for g in open_ if int(g["season"]) == season)
    rows = [g for g in games if int(g["season"]) == season and int(g["week"]) == week]
    rows.sort(key=lambda g: (g["gameday"], g["gametime"], g["game_id"]))
    return season, week, rows


def rule_calls(frozen, g):
    """Frozen-rule takes for one game: list of (version_id, family, side, text)."""
    view = {"spread_line": num(g["spread_line"]), "total_line": num(g["total_line"]),
            "away_rest": num(g["away_rest"]), "home_rest": num(g["home_rest"])}
    out = []
    for r in frozen["rules"]:
        d = rules.decide(r["family"], r["value"], view)
        if d["action"] != "take":
            continue
        if d["market"] == "total":
            text = "Under %g" % d["line"]
        elif d["side"] == "home":
            text = "%s %+g" % (g["home_team"], -d["line"])
        else:
            text = "%s %+g" % (g["away_team"], d["line"])
        out.append((r["version_id"], r["family"], d["side"], text))
    return out


def load_ledger():
    path = os.path.join(HERE, "ledger", "ledger.jsonl")
    if not os.path.exists(path):
        return None, {}
    rows = []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    rej = {}
    rpath = os.path.join(HERE, "ledger", "rejections.jsonl")
    if os.path.exists(rpath):
        with open(rpath) as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    code = json.loads(ln).get("code", "?")
                    rej[code] = rej.get(code, 0) + 1
    return rows, rej


def in_band(price):
    if price is None:
        return False
    return (0 < price <= 150) or (-170 <= price < 0)


def kickoff_central(g):
    """games.csv gametime is US Eastern; Central is one hour earlier."""
    y, m, d = [int(x) for x in g["gameday"].split("-")]
    hh, mm = [int(x) for x in g["gametime"].split(":")]
    dt = datetime.datetime(y, m, d, hh, mm) - datetime.timedelta(hours=1)
    h12 = dt.hour % 12 or 12
    return "%s %d %s" % (dt.strftime("%a"), dt.day, "%d:%02d %s" % (h12, dt.minute, "AM" if dt.hour < 12 else "PM"))


# ---------- svg ----------

def t(x, y, s, size=11, fill=INK2, weight=400, anchor="start", family=SANS):
    return ('<text x="%.1f" y="%.1f" font-size="%s" fill="%s" font-weight="%s" text-anchor="%s" '
            'font-family="%s">%s</text>' % (x, y, size, fill, weight, anchor, family, esc(s)))


def ln(x1, y1, x2, y2, stroke=RULE, w=1.0, extra=""):
    return ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%s" %s/>'
            % (x1, y1, x2, y2, stroke, w, extra))


def svg_wrap(parts, h, desc):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="100%%" role="img" '
            'aria-label="%s">%s</svg>' % (W, h, esc(desc), "".join(parts)))


def chart_intervals(res, frozen):
    be = res["breakeven"]
    hold = res["holdout"]
    clear = sum(1 for r in frozen["rules"] if hold[r["version_id"]]["win_rate_ci95"][0] > be)
    title = ("None of the four intervals clears break-even" if clear == 0
             else "%d of %d intervals clear break-even" % (clear, len(frozen["rules"])))
    parts = [t(0, 17, title, 16, INK, 600, family=SERIF),
             t(0, 35, "Held-out seasons %d to %d. Win rate with its 95%% interval, priced at -110."
               % tuple(res["holdout_seasons"]), 11, INK2)]
    x0, x1, lo, hi = 150.0, 372.0, 0.30, 0.80

    def X(p):
        return x0 + (x1 - x0) * (p - lo) / (hi - lo)

    top, rowh = 66.0, 37.0
    n = len(frozen["rules"])
    bottom = top + rowh * n
    for k in range(6):
        p = lo + 0.1 * k
        parts.append(ln(X(p), top - 6, X(p), bottom, RULE, 0.8))
        parts.append(t(X(p), bottom + 13, "%d%%" % round(100 * p), 9.5, MUTED, anchor="middle"))
    parts.append(ln(X(be), top - 14, X(be), bottom, WARM, 1.2, 'stroke-dasharray="3 2.5"'))
    parts.append(t(X(be), top - 18, "break-even %s" % pct(be, 2), 9.5, "#9a4d12", 600, anchor="middle"))
    for i, r in enumerate(frozen["rules"]):
        s = hold[r["version_id"]]
        cy = top + rowh * i + rowh / 2
        a, b = s["win_rate_ci95"]
        good = a > be
        parts.append(t(0, cy - 2, rule_label(r["family"], r["value"]), 10.5, INK, 600))
        parts.append(t(0, cy + 11, "%d bets, %d passes" % (s["bets"], s["passes"]), 9, MUTED))
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="7" rx="3.5" fill="%s"/>'
                     % (X(a), cy - 3.5, X(b) - X(a), COOL_L if good else RANGE))
        parts.append('<circle cx="%.1f" cy="%.1f" r="4.6" fill="%s" stroke="#fcfaf6" stroke-width="1.2"/>'
                     % (X(s["win_rate"]), cy, COOL if good else INK))
        parts.append(t(x1 + 12, cy - 2, "%d-%d-%d" % (s["wins"], s["losses"], s["pushes"]), 10.5, INK, 600))
        parts.append(t(x1 + 12, cy + 11, "%s, %s to %s" % (pct(s["win_rate"]), pct(a, 0), pct(b, 0)), 9, MUTED))
    sy = bottom + 30
    parts.append(ln(0, sy - 10, W, sy - 10, RULE, 0.8))
    parts.append(t(0, sy + 3, "Dot: win rate on decided bets. Bar: 95% Wilson interval. A rule passes only if the whole bar",
                   9.5, MUTED))
    parts.append(t(0, sy + 15.5, "sits right of the dashed line. Source: backtest.py on nflverse games.csv, run %s."
                   % res["run_ts_utc"], 9.5, MUTED))
    return svg_wrap(parts, sy + 22, title)


def chart_roi(res, frozen):
    hold, train = res["holdout"], res["training"]
    pos = [r for r in frozen["rules"] if hold[r["version_id"]]["roi_at_minus110"] > 0]
    if len(pos) == 1:
        title = "Only one rule stayed positive, on %d bets" % hold[pos[0]["version_id"]]["bets"]
    else:
        title = "%d of %d rules stayed positive on held-out seasons" % (len(pos), len(frozen["rules"]))
    parts = [t(0, 17, title, 16, INK, 600, family=SERIF),
             t(0, 35, "Return per unit staked after the vig at -110. Zero is break-even.", 11, INK2)]
    parts.append('<rect x="0" y="45" width="9" height="9" rx="2" fill="%s"/>' % COOL_L)
    parts.append(t(13, 53, "Training %d to %d" % tuple(res["train_seasons"]), 9.5, INK2))
    parts.append('<rect x="128" y="45" width="9" height="9" rx="2" fill="%s"/>' % INK)
    parts.append(t(141, 53, "Held-out %d to %d (looked at once)" % tuple(res["holdout_seasons"]), 9.5, INK2))
    x0, x1, lim = 150.0, 440.0, 0.22
    mid = (x0 + x1) / 2

    def X(v):
        v = max(-lim, min(lim, v))
        return mid + (x1 - mid) * v / lim

    top, rowh = 70.0, 40.0
    n = len(frozen["rules"])
    bottom = top + rowh * n
    for v in (-0.2, -0.1, 0.1, 0.2):
        parts.append(ln(X(v), top - 4, X(v), bottom, RULE, 0.8))
        parts.append(t(X(v), bottom + 13, "%+d%%" % round(100 * v), 9.5, MUTED, anchor="middle"))
    parts.append(ln(mid, top - 4, mid, bottom, INK2, 1.0))
    parts.append(t(mid, bottom + 13, "0", 9.5, MUTED, anchor="middle"))
    for i, r in enumerate(frozen["rules"]):
        vid = r["version_id"]
        cy = top + rowh * i + rowh / 2
        parts.append(t(0, cy - 2, rule_label(r["family"], r["value"]), 10.5, INK, 600))
        parts.append(t(0, cy + 11, "%d training bets, %d held-out" % (train[vid]["bets"], hold[vid]["bets"]),
                       9, MUTED))
        for j, (v, fill) in enumerate(((train[vid]["roi_at_minus110"], COOL_L),
                                       (hold[vid]["roi_at_minus110"], INK))):
            y = cy - 12 + 13 * j
            xa, xb = sorted((mid, X(v)))
            parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="10" rx="2" fill="%s"/>'
                         % (xa, y, max(xb - xa, 1.0), fill))
            if v >= 0:
                parts.append(t(xb + 4, y + 8.5, spct(v), 9.5, INK2, 600 if j else 400))
            else:
                parts.append(t(xa - 4, y + 8.5, spct(v), 9.5, INK2, 600 if j else 400, anchor="end"))
    sy = bottom + 30
    parts.append(ln(0, sy - 10, W, sy - 10, RULE, 0.8))
    parts.append(t(0, sy + 3, "Rules were chosen on training seasons only, then frozen (%s) before the held-out run."
                   % frozen["frozen_at_utc"], 9.5, MUTED))
    return svg_wrap(parts, sy + 10, title)


# ---------- html ----------

CSS = """
:root{ --paper:#fcfaf6; --ink:#1b222b; --ink2:#49515b; --muted:#636a72; --faint:#9a9fa5;
  --rule:#e5e3dd; --cool:#0e5e8a; --cool-soft:#e6eff4; --warm:#c56c21; --warm-soft:#f7ebdf;
  --serif: Charter, "Iowan Old Style", Georgia, serif;
  --sans: "Avenir Next", Avenir, Seravek, "Gill Sans", sans-serif; }
@page{ size:150mm 250mm; margin:13mm 12mm 15mm 12mm; background:var(--paper);
  @bottom-left{ content:"NFL paper desk \\00b7 private \\00b7 paper only"; font:500 7pt "Avenir Next",Avenir,sans-serif; color:#9a9fa5; }
  @bottom-right{ content:counter(page); font:600 7.5pt "Avenir Next",Avenir,sans-serif; color:#636a72; } }
*{ box-sizing:border-box } html,body{ background:var(--paper); }
body{ margin:0; color:var(--ink); font:9.6pt/1.43 var(--serif); -webkit-print-color-adjust:exact;
  print-color-adjust:exact; font-variant-numeric:lining-nums tabular-nums; hyphens:manual; }
b,strong{ font-weight:700 }
section.pg{ break-before:page; }
figure,table,.callout,.tiles,.answer,.cmd{ break-inside:avoid }
.kicker{ font:600 7.4pt/1.2 var(--sans); letter-spacing:.14em; text-transform:uppercase; color:var(--cool); margin:0 0 3mm; }
h1{ font:700 31pt/1.0 var(--serif); letter-spacing:-.015em; margin:0 0 3mm; }
h2{ font:700 17.5pt/1.12 var(--serif); letter-spacing:-.01em; margin:0 0 2.4mm; }
h3{ font:600 10.6pt/1.25 var(--sans); margin:4.5mm 0 1.4mm; }
p{ margin:0 0 2.2mm; }
.deck{ font:400 12.2pt/1.36 var(--serif); color:var(--ink2); margin:0 0 5mm; }
.note{ font:400 7.6pt/1.4 var(--sans); color:var(--muted); }
.answer{ border-left:2.2pt solid var(--cool); background:var(--cool-soft); padding:3.2mm 4mm 1.2mm; margin:0 0 5mm; border-radius:0 2mm 2mm 0; }
.answer .label{ font:700 7pt/1 var(--sans); letter-spacing:.14em; text-transform:uppercase; color:var(--cool); margin-bottom:1.8mm; }
.answer p{ font-size:10.4pt; line-height:1.45 }
.tiles{ display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:3mm; margin:0 0 5mm; }
.tile{ border-top:1.4pt solid var(--ink); padding:2.2mm 0 0; }
.tile .num{ font:700 19pt/1 var(--serif); letter-spacing:-.01em; }
.tile .num.warm{ color:var(--warm) } .tile .num.cool{ color:var(--cool) }
.tile .cap{ font:400 7.6pt/1.35 var(--sans); color:var(--ink2); margin-top:1.4mm; }
figure{ margin:2.6mm 0 3.4mm; }
table{ width:100%; border-collapse:collapse; font:400 7.8pt/1.36 var(--sans); margin:2mm 0 3.4mm; }
th{ text-align:left; font:700 6.6pt/1.2 var(--sans); letter-spacing:.09em; text-transform:uppercase; color:var(--muted); padding:1.3mm 1.4mm; border-bottom:0.8pt solid var(--ink); vertical-align:bottom; }
td{ padding:1.45mm 1.4mm; border-bottom:0.5pt solid var(--rule); vertical-align:top; }
td.r, th.r{ text-align:right; white-space:nowrap } .nw{ white-space:nowrap }
table.slate{ font-size:7.3pt } table.slate td, table.slate th{ padding-left:1.1mm; padding-right:1.1mm } td.k{ font-weight:600; color:var(--ink) }
tr.pick td{ background:#fff } .dim{ color:var(--faint) } .in{ font-weight:700; color:var(--cool) }
.callout{ background:var(--warm-soft); border-radius:2mm; padding:3mm 3.6mm 1mm; margin:3mm 0 4mm; }
.callout .label{ font:700 7pt/1 var(--sans); letter-spacing:.14em; text-transform:uppercase; color:#9a4d12; margin-bottom:1.6mm; }
.callout p{ font-size:9.2pt }
.cool-box{ background:var(--cool-soft); } .cool-box .label{ color:var(--cool) }
ul.tight{ margin:0 0 3mm; padding-left:4.2mm } ul.tight li{ margin:0 0 1.2mm; font-size:9.1pt; line-height:1.4 }
.cmd{ font:400 6.2pt/1.5 Menlo, Monaco, monospace; background:#fff; border:0.6pt solid var(--rule); border-radius:1.6mm; padding:2mm 2.6mm; margin:0 0 2.4mm; white-space:pre; overflow:hidden; color:var(--ink); }
.two{ display:grid; grid-template-columns:1fr 1fr; gap:4mm; }
"""


def build(res, frozen, man, games, ledger, rejections):
    be = res["breakeven"]
    hold, train = res["holdout"], res["training"]
    fr = frozen["rules"]
    n_pass = len(res.get("edges") or [])
    best = max(fr, key=lambda r: hold[r["version_id"]]["roi_at_minus110"])
    bs = hold[best["version_id"]]
    season, week, slate = slate_games(games)
    open_games = [g for g in slate if num(g["home_score"]) is None]

    calls = {g["game_id"]: rule_calls(frozen, g) for g in open_games}
    n_calls = sum(len(v) for v in calls.values())
    if ledger is not None:
        led_takes = {}
        for e in ledger:
            if str(e.get("action", "")).lower() == "take" and e.get("entered_by", "rule") != "manual" \
                    and not str(e.get("rule_version", "")).startswith("MANUAL"):
                led_takes.setdefault(e["game_id"], set()).add((e["rule_version"], e.get("side")))
        mine = {gid: set((v[0], v[2]) for v in c) for gid, c in calls.items() if c}
        if mine != led_takes:
            raise Refused("LEDGER_MISMATCH sheet rule calls differ from ledger takes: sheet=%r ledger=%r"
                          % (sorted(mine.items()), sorted(led_takes.items())))
        rule_rows = [e for e in ledger if not str(e.get("rule_version", "")).startswith("MANUAL")]
        n_take = sum(1 for e in rule_rows if str(e.get("action", "")).lower() == "take")
        n_passes = sum(1 for e in rule_rows if str(e.get("action", "")).lower() == "pass")
        n_rej = sum(rejections.values())
        ledger_cap = ("paper takes and passes logged for week %d. %d entries were rejected "
                      "(the Thursday game had already kicked off)." % (week, n_rej))
        tile4 = "%d / %d" % (n_take, n_passes)
    else:
        tile4 = "%d" % n_calls
        ledger_cap = "paper takes the frozen rules make for week %d. The ledger has not been generated yet." % week

    h = []
    h.append('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>NFL Paper Desk</title>'
             '<style>%s</style></head><body>' % CSS)

    # ----- page 1
    h.append('<section class="first">')
    h.append('<div class="kicker">NFL paper desk &middot; paper only &middot; 14 November 2026 &middot; For Matthew</div>')
    h.append('<h1>No Demonstrated Edge</h1>')
    h.append('<p class="deck">Four simple betting rules, tested once on %d seasons they had never seen, at the '
             'standard -110 price. What you can use this weekend is a paper ledger for your own takes and '
             'passes. It bets nothing.</p>' % (res["holdout_seasons"][1] - res["holdout_seasons"][0] + 1))
    h.append('<div class="answer"><div class="label">The answer</div>')
    h.append('<p><b>%s of the four rules passed the test.</b> The test was set in writing before any result '
             'was seen: a rule passes only if its whole 95%% interval sits above the %s win rate needed to '
             'break even at -110. The samples are small, so this fails to show an edge. It does not prove '
             'there is none.</p>' % ("None" if n_pass == 0 else str(n_pass), pct(be, 2)))
    h.append('<p>The best-looking rule, %s, went %d-%d-%d (%s). On only %d bets its interval runs from %s to '
             '%s, which still includes break-even. It is a lead to keep watching on paper, not a reason to '
             'bet.</p></div>' % (rule_phrase(best["family"], best["value"]).lower(), bs["wins"], bs["losses"],
                                 bs["pushes"], pct(bs["win_rate"]), bs["bets"], pct(bs["win_rate_ci95"][0]),
                                 pct(bs["win_rate_ci95"][1])))
    h.append('<div class="tiles">')
    h.append('<div class="tile"><div class="num warm">%d of %d</div><div class="cap">rules passed the test '
             'written down in advance</div></div>' % (n_pass, len(fr)))
    h.append('<div class="tile"><div class="num">%s</div><div class="cap">win rate needed to break even at '
             '-110</div></div>' % pct(be, 2))
    h.append('<div class="tile"><div class="num">%d</div><div class="cap">held-out games, %d to %d, each '
             'looked at once</div></div>' % (res["games_holdout"], res["holdout_seasons"][0],
                                             res["holdout_seasons"][1]))
    h.append('<div class="tile"><div class="num cool">%s</div><div class="cap">%s</div></div>'
             % (tile4, ledger_cap))
    h.append('</div>')
    h.append('<figure>%s</figure>' % chart_intervals(res, frozen))
    h.append('<p class="note">Paper output never implies a real edge and authorizes no real money. Agents place '
             'no bets and open no accounts. Built %s from data retrieved %s.</p>'
             % (datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), man["retrieved_at_utc"]))
    h.append('</section>')

    # ----- page 2
    h.append('<section class="pg"><div class="kicker">The test</div>')
    h.append('<h2>What was tested, and what it found</h2>')
    h.append('<p>Ten rule variants were written down before any backtest ran. Each family kept the variant '
             'with the best return on the %d to %d seasons, then the four survivors were frozen and run once '
             'on %d to %d. Every bet is priced at -110. The line is the one in the nflverse file, whose '
             'documentation does not say which book it came from or whether it is a closing line.</p>'
             % (res["train_seasons"][0], res["train_seasons"][1], res["holdout_seasons"][0],
                res["holdout_seasons"][1]))
    h.append('<table><tr><th>Frozen rule</th><th class="r">Bets</th><th class="r">W-L-P</th>'
             '<th class="r">Win rate</th><th class="r">95% interval</th><th class="r">Return</th>'
             '<th class="r">Passed</th><th class="r">Shadow</th></tr>')
    for r in fr:
        s = hold[r["version_id"]]
        sh = s["shadow_record_of_passes"]
        h.append('<tr><td class="k">%s<br><span class="dim">%s</span></td><td class="r">%d</td>'
                 '<td class="r">%d-%d-%d</td><td class="r">%s</td><td class="r">%s to %s</td>'
                 '<td class="r">%s</td><td class="r">%d</td><td class="r">%d-%d-%d</td></tr>'
                 % (esc(rule_label(r["family"], r["value"])), esc(r["version_id"]), s["bets"], s["wins"],
                    s["losses"], s["pushes"], pct(s["win_rate"]), pct(s["win_rate_ci95"][0]),
                    pct(s["win_rate_ci95"][1]), spct(s["roi_at_minus110"]), s["passes"], sh[0], sh[1], sh[2]))
    h.append('</table>')
    h.append('<p class="note">Return is profit per unit staked after the vig. Passed: games the rule skipped. '
             'Shadow: the record of its side on those games, where it had one. '
             'Break-even is %s. All ten variants are in VARIANT_LOG.jsonl.</p>' % pct(be, 2))
    h.append('<figure>%s</figure>' % chart_roi(res, frozen))
    h.append('<div class="callout"><div class="label">Why %s has not shown an edge</div>'
             % esc(rule_label(best["family"], best["value"]).lower()))
    by = bs["by_season"]
    seasons = ", ".join("%s in %s" % (by[k]["record"], k) for k in sorted(by))
    h.append('<p>It was the best of four rules, on %d bets (%s). Its 95%% interval starts at %s, '
             'below the %s break-even; the stricter interval that allows for four rules starts at %s. '
             'A break-even rule would show a record this good about %s of the time alone, and '
             'about %s once four rules are allowed for. Those seasons are now spent: only new games can '
             'judge the rule, which is the paper ledger\'s job.</p></div>'
             % (bs["bets"], seasons, pct(bs["win_rate_ci95"][0]), pct(be, 2),
                pct(bs["win_rate_ci98_75_bonferroni"][0]), pct(bs["p_value_one_sided_vs_breakeven"], 1),
                pct(min(1.0, 4 * bs["p_value_one_sided_vs_breakeven"]), 0)))
    bl = res["baselines"]
    h.append('<p class="note">Baselines, held-out at -110: always home %s, underdog %s, under %s. '
             'An AI model that may remember 2023 to 2025 chose the rule families, so this test is not '
             'fully blind; only the forward ledger is clean.</p>'
             % (spct(bl["BASELINE_ALWAYS_HOME|holdout"]["roi_at_minus110"]),
                spct(bl["BASELINE_ALWAYS_DOG|holdout"]["roi_at_minus110"]),
                spct(bl["BASELINE_ALWAYS_UNDER|holdout"]["roi_at_minus110"])))
    h.append('</section>')

    # ----- page 3
    h.append('<section class="pg"><div class="kicker">This weekend &middot; week %d</div>' % week)
    h.append('<h2>The slate, with the frozen rules\' paper calls</h2>')
    h.append('<p>%d games are still to be played. The rules make %d paper calls on them. These calls come '
             'from rules that did not pass the test, so they are a record to score later, not advice.</p>'
             % (len(open_games), n_calls))
    h.append('<table class="slate"><tr><th>Kickoff, Central</th><th>Game</th><th>Line</th>'
             '<th class="r">Total</th><th>Moneyline</th><th>Paper rule calls</th></tr>')
    for g in slate:
        sl, tl = num(g["spread_line"]), num(g["total_line"])
        am, hm = num(g["away_moneyline"]), num(g["home_moneyline"])
        game = "%s at %s" % (g["away_team"], g["home_team"])
        if g.get("location") == "Neutral":
            game += " (neutral)"
        if sl is None:
            line = ""
        elif sl > 0:
            line = "%s -%g" % (g["home_team"], sl)
        elif sl < 0:
            line = "%s -%g" % (g["away_team"], -sl)
        else:
            line = "pick"

        def ml(team, p):
            if p is None:
                return ""
            s = "%s %+d" % (team, int(p))
            return '<span class="in">%s</span>' % s if in_band(p) else s
        if num(g["home_score"]) is not None:
            h.append('<tr class="dim"><td class="nw">%s</td><td class="nw">%s</td><td class="nw">%s</td><td class="r">%s</td><td></td>'
                     '<td>Already played (%d-%d). Rejected by the ledger.</td></tr>'
                     % (kickoff_central(g), esc(game), esc(line), "%g" % tl if tl is not None else "",
                        int(num(g["away_score"])), int(num(g["home_score"]))))
            continue
        c = calls[g["game_id"]]
        ctext = "; ".join("<b>%s</b> <span class=\"dim\">%s</span>" % (esc(x[3]), SHORT[x[1]]) for x in c) \
            if c else '<span class="dim">pass on all four</span>'
        h.append('<tr%s><td class="nw">%s</td><td class="k nw">%s</td><td class="nw">%s</td><td class="r">%s</td><td class="nw">%s &middot; %s</td>'
                 '<td>%s</td></tr>' % (' class="pick"' if c else "", kickoff_central(g), esc(game), esc(line),
                                       "%g" % tl if tl is not None else "", ml(g["away_team"], am),
                                       ml(g["home_team"], hm), ctext))
    h.append('</table>')
    h.append('<p class="note">Blue moneylines fall inside your +150 to -170 range. Prices are archived paper '
             'observations: the file was retrieved %s, and the sportsbook\'s own quote time is unknown. They '
             'are not live, may no longer be offered, and may differ at any operator you could use.</p>'
             % man["retrieved_at_utc"])
    h.append('<div class="callout cool-box"><div class="label">Your own picks</div>')
    h.append('<p>The data covers team markets only: spread, total and moneyline. It has no player props. '
             'Your way of choosing, watching the game and judging player roles, goes in as a personal entry: '
             'the price you were actually offered, where and when you saw it, take or pass, and your reason. '
             'A prop at 54.5 and the same prop at 60.5 are saved as two different contracts. A closing price '
             'counts only for the identical contract, read after your pick and before kickoff. Any other '
             'quote is kept, labeled and left out of that comparison.</p></div>')
    h.append('</section>')

    # ----- page 4
    h.append('<section class="pg"><div class="kicker">Use it</div>')
    h.append('<h2>How to use it, and where the limits are</h2>')
    h.append('<h3>Opening flow</h3>')
    h.append('<div class="cmd">%s</div>' % esc(OPENING_FLOW))
    h.append('<p class="note">The tool is nov14-sprint/nfl/paper_ledger.py and its records are in '
             'nov14-sprint/nfl/ledger/. To practise without touching the real ledger, put --ledger-dir and an '
             'empty folder of your choice straight after paper_ledger.py. Every command prints "PAPER ONLY". '
             'The ledger refuses a game that has kicked off, a missing or stale line, a quote time later than '
             'the clock, a stake above 1 unit, and a repeat of the same contract. It stops taking new paper '
             'takes after a 10 unit drawdown. Its self-test is '
             'nov14-sprint/nfl/tests/fixtures/selftest_paper_ledger.py.</p>')
    h.append('<div class="two"><div><h3>Limits</h3><ul class="tight">'
             '<li>No rule has a demonstrated edge. Nothing here supports a real bet.</li>'
             '<li>Team markets only. Props are personal entries with prices you type in.</li>'
             '<li>The file\'s line is not verified as a closing line, and its book is not named.</li>'
             '<li>The 2023 to 2025 seasons are spent. Only new games can test a rule now.</li>'
             '<li>Team markets settle from a fresh download of the same file. Props settle by hand.</li>'
             '<li>Closing prices are recorded and labeled. No closing-line value is computed yet.</li>'
             '</ul></div>')
    h.append('<div><h3>Legal channels in Louisiana</h3><ul class="tight">'
             '<li>Only state-licensed sportsbooks. The Gaming Control Board\'s annual report shows eight '
             'mobile brands: Bet365, BetMGM, BetRivers, Caesars, DraftKings, FanDuel, Fanatics and theScore '
             'Bet.</li>'
             '<li>Nine parishes voted no in 2020: Caldwell, Catahoula, Franklin, Jackson, LaSalle, Sabine, '
             'Union, West Carroll and Winn.</li>'
             '<li>Excluded across brands: Kalshi, Polymarket and every other event-contract or '
             'prediction-market product.</li>'
             '<li>Licensing changes. Recheck the Board\'s list first. Sources: LEGAL_CHANNELS.md.</li>'
             '</ul></div></div>')
    h.append('<p class="note">Agents never place bets, sign in or open accounts. Anything real would be '
             'Matthew\'s own decision, by hand, at a licensed operator, after his own check.</p>')
    h.append('</section></body></html>')
    return "\n".join(h), {"season": season, "week": week, "open_games": len(open_games), "rule_calls": n_calls}


OPENING_FLOW = """# From the ClaudeCodeAdvancements folder. System python3 only, nothing to install.
# 1. See the slate and where each moneyline sits against your +150 to -170 range
python3 -I nov14-sprint/nfl/paper_ledger.py slate
# 2. Log the frozen rules' takes and passes (done for week 10; a repeat adds nothing)
python3 -I nov14-sprint/nfl/paper_ledger.py generate
# 3. Your own take at the price you were offered. --quote-ts is the UTC time you read
#    the price; the date command below fills in the time right now.
python3 -I nov14-sprint/nfl/paper_ledger.py add --game-id 2026_10_PIT_CIN \\
  --rule MANUAL-v1 --market prop --selection "Player Name receiving yards" \\
  --side over --line 54.5 --price -115 --action take --reason "role grew" \\
  --source "operator name" --quote-ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# 4. Your own pass on another pick: the same flags with --action pass. Stake is 0.
# 5. The same player relisted at 60.5 is a separate contract: change --line to 60.5.
#    Sending an identical contract again is refused as DUPLICATE_PICK.
# 6. Near kickoff: the price for the identical contract. PICK_ID is printed by step 3.
python3 -I nov14-sprint/nfl/paper_ledger.py close --pick-id PICK_ID --line 54.5 \\
  --price -125 --source "operator name" --quote-ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# 7. After the games: team markets settle from a fresh download, props by hand.
#    NEW_GAMES_CSV is the new file; RETRIEVED_UTC is when it was downloaded.
python3 -I nov14-sprint/nfl/paper_ledger.py settle --results-file NEW_GAMES_CSV \\
  --results-ts RETRIEVED_UTC
python3 -I nov14-sprint/nfl/paper_ledger.py settle-manual --pick-id PICK_ID \\
  --outcome win --result-source "box score, site name"
python3 -I nov14-sprint/nfl/paper_ledger.py status"""


def main():
    try:
        res, frozen, man, games = load_inputs()
        ledger, rejections = load_ledger()
        html, info = build(res, frozen, man, games, ledger, rejections)
    except Refused as e:
        print("REFUSED %s" % e)
        return 2
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    with open(OUT_HTML, "w") as f:
        f.write(html)
    print("wrote %s (%d bytes)" % (OUT_HTML, len(html)))
    print("slate: season %(season)d week %(week)d, %(open_games)d open games, %(rule_calls)d rule calls" % info)
    print("ledger: %s" % ("cross-checked, %d rows" % len(ledger) if ledger is not None else "not generated yet"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
