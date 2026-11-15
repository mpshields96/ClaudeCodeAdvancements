#!/usr/bin/env python3
"""Form check: set the integrator's nfl.com game-log form file beside the posted prop lines. Read-only, no network, stdlib only, Python 3.9 safe.

Usage: props_form_check.py <review.json> <official_player_logs.json> <out_form.md>
Run as: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I props_form_check.py ...

Descriptive only. It does not predict anything and is not a calibrated test. Form is each player's consecutive 2026 regular-season games (the integrator's file has no 2025 rows; nothing is padded) counted against TODAY's posted line, a retro-fit: it is not scored against the lines posted at the time of each game, which this script does not have.
A game whose every stat cell is empty is "no stat line" (inactive, not targeted, or not used: the page does not say which) and is left out of the averages.
A game with some other stat filled in but the market's own cells empty counts as 0 for that market.
"""
import json, sys, re, unicodedata, statistics, collections

SHORT = {"player_pass_yds": "pass yds", "player_rush_yds": "rush yds", "player_reception_yds": "rec yds"}
BK = {"draftkings": "DK", "fanduel": "FD", "betmgm": "MGM", "espnbet": "tSB", "betrivers": "BR"}
CODEX_NAMED = [("Jaylen Warren", "player_reception_yds"), ("Rico Dowdle", "player_reception_yds"), ("Joe Burrow", "player_rush_yds"),
               ("Joe Burrow", "player_pass_yds"), ("Emmett Johnson", "player_rush_yds"), ("Emmett Johnson", "player_reception_yds"),
               ("John Metchie III", "player_reception_yds"), ("Jordan Love", "player_pass_yds"), ("Brock Bowers", "player_reception_yds"),
               ("Jaxon Smith-Njigba", "player_reception_yds")]
# column index of each market's yards cell, by the log table's header order
LAYOUT = {
    ("REC", "YDS"): {"player_reception_yds": 1, "player_rush_yds": 6},
    ("ATT", "YDS"): {"player_rush_yds": 1, "player_reception_yds": 6},
    ("COMP", "ATT"): {"player_pass_yds": 2, "player_rush_yds": 10},
}


def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def series(log, market):
    """Return list of (week, opponent, value or None). None = no stat line."""
    lay = LAYOUT.get(tuple(log["headers"][:2]))
    if not lay or market not in lay:
        return None
    idx = lay[market]
    out = []
    for g in log["games"]:
        vals = g["values"]
        if all(v is None for v in vals):
            out.append((g["week"], g["opponent"], None))
        else:
            v = num(vals[idx])
            out.append((g["week"], g["opponent"], 0.0 if v is None else v))
    return out


def modal(x):
    pl = sorted(x["per_line"], key=lambda p: (-p["n_books"], p["line"]))
    return pl[0] if pl else None


def main(rev_p, form_p, out_p):
    rv = json.load(open(rev_p))
    fm = json.load(open(form_p))
    R = rv["review"]
    by_norm = collections.defaultdict(list)
    for k, p in fm["players"].items():
        if "error" in p:  # integrator found no unique nfl.com roster match (Dotson, Taylor, Sample)
            continue
        by_norm[norm(k)].append(p)  # keyed by the feed's player name, which is how the integrator looked them up

    def find(x):
        c = by_norm.get(norm(x["player"]), [])
        team = x["identity"].get("team")
        c2 = [p for p in c if p["team_name"] == team]
        return c2[0] if len(c2) == 1 else None

    stats = collections.Counter()
    info = {}
    for x in R:
        key = (x["player"], x["market"], x["matchup"])
        if x["identity"]["status"] != "matched":
            stats["form_no_identity"] += 1
            continue
        p = find(x)
        if not p:
            stats["form_player_absent"] += 1
            continue
        lg = fm["logs"].get(p["log_url"])
        if not lg or not lg.get("headers"):
            stats["form_log_absent"] += 1
            continue
        s = series(lg, x["market"])
        if s is None:
            stats["form_layout_unsupported"] += 1
            continue
        st = fm["season_totals"].get("https://www.nfl.com" + p["player_path"] + "stats/career")
        cat = (st or {}).get("categories", {}).get(x["market"]) or []
        # a player with two teams in 2026 has two rows in the career table; the log covers all of them
        tot = {"yards": sum(c["yards"] for c in cat if c.get("yards") is not None)} if cat else None
        have = [v for (_, _, v) in s if v is not None]
        recon = None
        if tot and tot.get("yards") is not None:
            recon = (sum(have) == tot["yards"])
        stats["form_ok"] += 1
        stats["recon_ok"] += (recon is True)
        stats["recon_bad"] += (recon is False)
        info[key] = {"x": x, "p": p, "lg": lg, "s": s, "have": have, "tot": tot, "recon": recon}
    stats["rows"] = len(R)

    def line_of(x):
        return modal(x)["line"]

    def summ(i):
        h = i["have"]
        if not h:
            return None
        m = line_of(i["x"])
        ladder = [pl["line"] for pl in i["x"]["per_line"]]
        return {"n": len(h), "mean": statistics.mean(h), "med": statistics.median(h), "min": min(h), "max": max(h),
                "over_modal": sum(1 for v in h if v > m), "all_over": min(ladder), "all_under": max(ladder),
                "no_line": sum(1 for (_, _, v) in i["s"] if v is None), "last3": statistics.mean([v for (_, _, v) in i["s"] if v is not None][:3]) if len(h) >= 3 else None}

    out = []
    out.append("### I. Form against today's posted line (nfl.com 2026 game logs captured by the integrator, 07:08Z to 07:11Z; descriptive retro-fit, not a test)\n")
    out.append("Per-game values are consecutive 2026 regular-season games, most recent first, as `week:yards`; no 2025 games are added, and every available game is shown (no player has more than 9, so \"last 10\" means all of them). A dash means no stat line that week (inactive, not used or not targeted; the page does not say which). The hit count applies TODAY's modal line to those past games (a retro-fit: the line posted for each game at the time is not used) out of games with a stat line.\n")
    out.append("| Player, market (game) | Modal line today (books) | Games with stat line | Per game, newest first | Mean / median / last 3 | Games over today's modal line (retro-fit) | Season total check |")
    out.append("|---|---|---|---|---|---|---|")
    done = set()
    order = []
    for nm, mk in CODEX_NAMED:
        for k in info:
            if k[0] == nm and k[1] == mk:
                order.append(k)
    gate_rows = []
    for k, i in info.items():
        x = i["x"]
        m = modal(x)
        e = x["espn_dk"]
        inj = x["identity"].get("injuries")
        dk_ok = None
        if e and e["unique"] and x["feed_dk_line"] is not None:
            dk_ok = (sorted(e["unique"], key=lambda t: t[2] or "")[-1][0] == x["feed_dk_line"])
        if m and m["n_books"] >= 4 and not inj and dk_ok is True:
            gate_rows.append(k)
    for k in sorted(gate_rows, key=lambda k: (info[k]["x"]["kickoff_utc"], k[2], k[1], k[0])):
        if k not in order:
            order.append(k)
    for k in order:
        i = info[k]
        x = i["x"]
        m = modal(x)
        sm = summ(i)
        ser = " ".join("%d:%s" % (w, ("%g" % v) if v is not None else "-") for (w, _, v) in i["s"])
        chk = {True: "log sum equals season total", False: "MISMATCH", None: "no season total"}[i["recon"]]
        if sm:
            out.append("| %s, %s (%s) | %s (%d books) | %d of %d | %s | %.1f / %.1f / %s | %d of %d | %s |" % (
                k[0], SHORT[k[1]], k[2].replace(" at ", " @ "), m["line"], m["n_books"], sm["n"], len(i["s"]), ser,
                sm["mean"], sm["med"], ("%.1f" % sm["last3"]) if sm["last3"] is not None else "n/a", sm["over_modal"], sm["n"], chk))
        else:
            out.append("| %s, %s (%s) | %s (%d books) | 0 of %d | %s | n/a | n/a | %s |" % (k[0], SHORT[k[1]], k[2].replace(" at ", " @ "), m["line"], m["n_books"], len(i["s"]), ser, chk))
    out.append("")

    # form-versus-whole-ladder conflict screen
    conflict = []
    for k, i in info.items():
        sm = summ(i)
        if not sm or sm["n"] < 6:
            continue
        if sm["min"] > sm["all_under"]:
            conflict.append((k, "every game above the highest posted line", sm, i))
        elif sm["max"] < sm["all_over"]:
            conflict.append((k, "every game below the lowest posted line", sm, i))
    stats["conflict_rows"] = len(conflict)
    stats["conflict_above"] = sum(1 for c in conflict if c[1].startswith("every game above"))
    stats["conflict_below"] = sum(1 for c in conflict if c[1].startswith("every game below"))
    out.append("### J. Form-versus-market conflict screen (research prompt only, not picks)\n")
    out.append("Rows with at least 6 consecutive 2026 games with a stat line where every one of those games sits on one side of the entire posted ladder across all books (today's lines applied to past games; a retro-fit). %d rows: %d with every game above the highest posted line, %d with every game below the lowest. "
               "A conflict means the market is pricing something the box scores do not show (role, injury, matchup, game script) or the form is stale. It does not say which, and nothing here shows the market is the side that is wrong.\n"
               % (stats["conflict_rows"], stats["conflict_above"], stats["conflict_below"]))
    out.append("| Player, market (game) | Ladder (low to high) | Games | Range of games | Mean | Direction |")
    out.append("|---|---|---|---|---|---|")
    for k, why, sm, i in sorted(conflict, key=lambda c: (c[0][2], c[0][1], c[0][0])):
        lad = [pl["line"] for pl in i["x"]["per_line"]]
        out.append("| %s, %s (%s) | %g to %g | %d | %g to %g | %.1f | %s |" % (k[0], SHORT[k[1]], k[2].replace(" at ", " @ "), min(lad), max(lad), sm["n"], sm["min"], sm["max"], sm["mean"], why))
    out.append("")
    open(out_p, "w").write("\n".join(out) + "\n")
    print(dict(stats))
    # which Codex-named rows are in info
    print("named found", [(k[0], k[1]) for k in order if (k[0], k[1]) in [(a, b) for a, b in CODEX_NAMED]])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
