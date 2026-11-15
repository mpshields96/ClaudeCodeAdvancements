#!/usr/bin/env python3
"""Read-only cross-check of the data integrator's props_20261115.json against my own independent read of the same 06:55:06Z feed. No network, stdlib only, Python 3.9 safe.

Usage: props_xcheck_integrator.py <review.json> <props_20261115.json> <official_player_logs.json> <out.md>
Run as: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I props_xcheck_integrator.py ...

It does not edit the integrator's file. Two checks:
 1. Quotes: every (player, market, book, line) with its Over and Under price in my review.json is looked up in the integrator's props and excluded_props.
 2. Form counts: at each DraftKings line, my last-10 over/under counts (props_form_check.py rules) against the integrator's historical_results_at_current_line.last_10.
    Rule difference (integrator file built 07:38:37Z or later): the integrator counts a game where it verified the player appeared (from game stats, a gamebook or club source) but the page shows no stat line as a derived zero (included_derived_zeros) and keeps it in the window; I leave an all-empty game row out as "no stat line" but count a blank market cell beside other filled cells as 0 yards. Games it verifies as inactive are left out of its window, as in mine.
"""
import json, sys, re, unicodedata, collections

BK = {"draftkings": "DK", "fanduel": "FD", "betmgm": "MGM", "espnbet": "tSB", "betrivers": "BR"}
SHORT = {"player_pass_yds": "pass yds", "player_rush_yds": "rush yds", "player_reception_yds": "rec yds"}
LAYOUT = {("REC", "YDS"): {"player_reception_yds": 1, "player_rush_yds": 6},
          ("ATT", "YDS"): {"player_rush_yds": 1, "player_reception_yds": 6},
          ("COMP", "ATT"): {"player_pass_yds": 2, "player_rush_yds": 10}}


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


def my_series(log, market):
    lay = LAYOUT.get(tuple(log["headers"][:2]))
    if not lay or market not in lay:
        return None
    idx = lay[market]
    out = []
    for g in log["games"]:  # newest first
        vals = g["values"]
        if all(v is None for v in vals):
            out.append(None)
        else:
            v = num(vals[idx])
            out.append((0.0, True) if v is None else (v, False))  # (yards, market cell blank beside other filled cells)
    return out


def main(rev_p, props_p, form_p, out_p):
    rv = json.load(open(rev_p))["review"]
    pj = json.load(open(props_p))
    fm = json.load(open(form_p))
    ip = {}
    for tag, arr in (("eligible", pj["props"]), ("excluded", pj["excluded_props"])):
        for p in arr:
            k = (norm(p["player"]), p["market"], p["book_key"], p["line"])
            ip.setdefault(k, []).append((tag, p))
    stats = collections.Counter()
    problems = []
    seen = set()
    for x in rv:
        for pl in x["per_line"]:
            for b, v in pl["books"].items():
                k = (norm(x["player"]), x["market"], b, pl["line"])
                seen.add(k)
                stats["my_quotes"] += 1
                hit = ip.get(k)
                if not hit:
                    stats["missing_in_integrator"] += 1
                    problems.append("missing in integrator: %s %s %s %s" % (x["player"], SHORT[x["market"]], BK[b], pl["line"]))
                    continue
                if len(hit) > 1:
                    stats["duplicate_in_integrator"] += 1
                tag, p = hit[0]
                stats["in_" + tag] += 1
                if p["over_american_price"] != v["over"] or p["under_american_price"] != v["under"]:
                    stats["price_mismatch"] += 1
                    problems.append("price mismatch: %s %s %s %s mine %s/%s theirs %s/%s" % (x["player"], SHORT[x["market"]], BK[b], pl["line"], v["over"], v["under"], p["over_american_price"], p["under_american_price"]))
    extra = [k for k in ip if k not in seen]
    stats["integrator_quotes"] = sum(len(v) for v in ip.values())
    stats["integrator_not_in_mine"] = len(extra)
    problems += ["in integrator, not in mine: %s" % (k,) for k in extra[:10]]

    # form counts at the DraftKings line
    by_norm = collections.defaultdict(list)
    for k, p in fm["players"].items():
        if "error" not in p:
            by_norm[norm(k)].append(p)
    diffs = []
    for x in rv:
        if x["feed_dk_line"] is None or x["identity"]["status"] != "matched":
            continue
        k = (norm(x["player"]), x["market"], "draftkings", x["feed_dk_line"])
        hit = ip.get(k)
        if not hit:
            continue
        p = hit[0][1]
        h = (p.get("historical_results_at_current_line") or {}).get("last_10")
        c = by_norm.get(norm(x["player"]), [])
        c = [q for q in c if q["team_name"] == x["identity"].get("team")]
        if not h or len(c) != 1:
            stats["form_not_comparable"] += 1
            continue
        lg = fm["logs"].get(c[0]["log_url"])
        if not lg or not lg.get("headers"):
            stats["form_not_comparable"] += 1
            continue
        s = my_series(lg, x["market"])
        if s is None:
            stats["form_not_comparable"] += 1
            continue
        rows = [v for v in s if v is not None][:10]  # newest first, rows with a stat line only
        vals = [v[0] for v in rows]
        partial = sum(1 for v in rows if v[1])  # blank market cell beside filled cells: I already count it as 0 yards
        mine = (sum(1 for v in vals if v > x["feed_dk_line"]), sum(1 for v in vals if v < x["feed_dk_line"]))
        theirs = (h["over"], h["under"])
        stats["form_compared"] += 1
        dz = h.get("included_derived_zeros") or 0
        # their derived zeros = my all-empty rows they add back + blank-market rows I already count as 0
        explained = (mine[0] == theirs[0] and theirs[1] - mine[1] == dz - partial)
        stats["rows_with_derived_zeros"] += (dz > 0)
        if mine == theirs:
            stats["form_same"] += 1
        else:
            stats["form_diff"] += 1
            stats["diff_explained_by_derived_zeros"] += explained
            diffs.append((x["player"], SHORT[x["market"]], x["feed_dk_line"], mine, theirs, h.get("unreported"), dz, explained, partial))
    out = []
    out.append("### L. Cross-check of the integrator's props_20261115.json (version %s, built %s) against my read of the same 06:55:06Z feed\n" % (pj.get("version"), pj.get("built_utc")))
    out.append("Quotes: %d (player, market, book, line) quotes in my read; %d found in the integrator's file (%d in `props`, %d in `excluded_props`); %d missing; %d with a different Over or Under price; the integrator has %d quotes, %d of them not in my read.\n" % (
        stats["my_quotes"], stats["in_eligible"] + stats["in_excluded"], stats["in_eligible"], stats["in_excluded"], stats["missing_in_integrator"], stats["price_mismatch"], stats["integrator_quotes"], stats["integrator_not_in_mine"]))
    out.append("Form counts at the DraftKings line (last 10 games): %d compared; %d identical; %d different. A difference is expected where the integrator counts a verified appearance with no stat line as a derived zero and I leave that game row out: its over count equals mine and its under count is higher by its derived-zero count less any games where only the market cell is blank beside other filled cells (I already count those as 0 yards). %d of the %d differences fit that rule exactly; %d rows in all carry derived zeros.\n" % (stats["form_compared"], stats["form_same"], stats["form_diff"], stats["diff_explained_by_derived_zeros"], stats["form_diff"], stats["rows_with_derived_zeros"]))
    if diffs:
        out.append("| Player, market | DK line | Mine over/under | Integrator over/under | Integrator unreported rows | Integrator derived zeros | Blank-market rows I already count as 0 | Fits the rule |")
        out.append("|---|---|---|---|---|---|---|---|")
        for d in diffs:
            out.append("| %s, %s | %s | %d/%d | %d/%d | %s | %s | %s | %s |" % (d[0], d[1], d[2], d[3][0], d[3][1], d[4][0], d[4][1], d[5], d[6], d[8], "yes" if d[7] else "NO"))
        out.append("")
    if problems:
        out.append("Quote problems (first 15):\n")
        for t in problems[:15]:
            out.append("- " + t)
        out.append("")
    open(out_p, "w").write("\n".join(out) + "\n")
    print(dict(stats))
    print("diffs", len(diffs), "problems", len(problems))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
