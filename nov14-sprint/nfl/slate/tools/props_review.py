#!/usr/bin/env python3
"""Props review: reconcile the shared 06:55:06Z multi-book feed against the ESPN DraftKings capture.

Read-only on both inputs. Makes no network request. Stdlib only, Python 3.9 safe.
Usage: props_review.py <sunday-odds.json> <espn_propbets_dir> <public_lines.json> <out.json>
Run as: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I props_review.py ...
"""
import json, sys, glob, re, collections, unicodedata, itertools

MARKETS = {
    "player_pass_yds": "Total Passing Yards (incl. overtime)",
    "player_rush_yds": "Total Rushing Yards (incl. overtime)",
    "player_reception_yds": "Total Receiving Yards (incl. overtime)",
}


def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def prob(price):
    return 100.0 / (price + 100.0) if price > 0 else -price / (-price + 100.0)


def main(feed_p, espn_dir, lines_p, out_p):
    feed = json.load(open(feed_p))
    lines = json.load(open(lines_p))
    man = json.load(open(espn_dir + "/MANIFEST.json"))

    # rosters: team displayName -> abbreviation, players
    teams = {}
    by_id = {}
    for fn in sorted(glob.glob(espn_dir + "/roster_*.json")):
        r = json.load(open(fn))
        t = r["team"]
        pl = {}
        for grp in r["athletes"]:
            for a in grp["items"]:
                rec = {"id": a["id"], "name": a["fullName"], "pos": (a.get("position") or {}).get("abbreviation"),
                       "inj": a.get("injuries") or [], "status": (a.get("status") or {}).get("name")}
                pl.setdefault(norm(a["fullName"]), []).append(rec)
                by_id[a["id"]] = {"team": t["displayName"], **rec}
        teams[t["displayName"]] = {"abbr": t["abbreviation"], "players": pl, "roster_ts": r.get("timestamp")}

    # ESPN events by team names
    espn_events = {}
    for g in lines["games"]:
        espn_events[g["event_id"]] = g
    # print team name shape for mapping
    sample = next(iter(espn_events.values()))
    abbr2name = {v["abbr"]: k for k, v in teams.items()}

    def tname(x):
        if isinstance(x, dict):
            x = x.get("abbr") or x.get("abbreviation") or x.get("name") or x.get("team") or x.get("displayName")
        return abbr2name.get(x, x)

    ev_by_pair = {}
    for eid, g in espn_events.items():
        h, a = tname(g["teams"]["home"]), tname(g["teams"]["away"])
        ev_by_pair[(h, a)] = (eid, g["kickoff_utc"])

    # ESPN DraftKings lines: (eid, athlete id, type) -> list of dicts (dedupe)
    espn = collections.defaultdict(list)
    for fn in sorted(glob.glob(espn_dir + "/propbets_*_p*.json")):
        eid = re.search(r"propbets_(\d+)_p", fn).group(1)
        for it in json.load(open(fn))["items"]:
            tn = it["type"]["name"]
            if tn in MARKETS.values():
                aid = it["athlete"]["$ref"].split("/athletes/")[1].split("?")[0]
                cur = (it.get("current") or {}).get("target") or {}
                op = (it.get("open") or {}).get("target") or {}
                espn[(eid, aid, tn)].append({"line": cur.get("value"), "open": op.get("value"), "updated": it.get("lastUpdated")})

    rows = []
    unmatched_events = []
    for ev in feed["event_odds"]:
        pair = (ev["home_team"], ev["away_team"])
        eid_kick = ev_by_pair.get(pair)
        if not eid_kick:
            unmatched_events.append(pair)
            continue
        eid, kick = eid_kick
        # collect per market, player: book -> list of outcomes
        agg = collections.defaultdict(lambda: collections.defaultdict(lambda: {"Over": [], "Under": []}))
        for bk in ev["bookmakers"]:
            for m in bk["markets"]:
                if m["key"] not in MARKETS:
                    continue
                for o in m["outcomes"]:
                    agg[(m["key"], o["description"])][bk["key"]][o["name"]].append(
                        {"point": o.get("point"), "price": o.get("price"), "upd": m["last_update"]})
        for (mk, player), books in agg.items():
            rows.append({"odds_event_id": ev["id"], "event_id": eid, "kickoff_utc": kick, "home": ev["home_team"],
                         "away": ev["away_team"], "market": mk, "player": player, "books": books})

    review = []
    for r in rows:
        # candidate team: whichever of home/away rosters has this normalized name
        cands = []
        for tm in (r["home"], r["away"]):
            for rec in teams.get(tm, {}).get("players", {}).get(norm(r["player"]), []):
                cands.append((tm, rec))
        identity = {"status": "unmatched"}
        if len(cands) == 1:
            identity = {"status": "matched", "team": cands[0][0], "espn_id": cands[0][1]["id"], "pos": cands[0][1]["pos"],
                        "espn_name": cands[0][1]["name"], "injuries": cands[0][1]["inj"]}
        elif len(cands) > 1:
            identity = {"status": "ambiguous", "n": len(cands)}
        # by line
        lines_seen = collections.defaultdict(dict)  # point -> book -> (over, under)
        dup_flags = []
        for bk, sides in r["books"].items():
            if len(sides["Over"]) != 1 or len(sides["Under"]) != 1:
                dup_flags.append({"book": bk, "n_over": len(sides["Over"]), "n_under": len(sides["Under"])})
                continue
            o, u = sides["Over"][0], sides["Under"][0]
            if o["point"] != u["point"]:
                dup_flags.append({"book": bk, "over_point": o["point"], "under_point": u["point"]})
                continue
            lines_seen[o["point"]][bk] = (o["price"], u["price"], o["upd"])
        per_line = []
        for pt, bks in sorted(lines_seen.items()):
            novig = {}
            for bk, (op, up, upd) in bks.items():
                po, pu = prob(op), prob(up)
                novig[bk] = {"over": op, "under": up, "hold": round(po + pu - 1, 4), "p_over_novig": round(po / (po + pu), 4), "upd": upd}
            cons = sum(v["p_over_novig"] for v in novig.values()) / len(novig)
            best_over = max(bks.items(), key=lambda kv: kv[1][0])
            best_under = max(bks.items(), key=lambda kv: kv[1][1])
            per_line.append({"line": pt, "n_books": len(bks), "consensus_p_over": round(cons, 4), "books": novig,
                             "best_over": {"book": best_over[0], "price": best_over[1][0]},
                             "best_under": {"book": best_under[0], "price": best_under[1][1]}})
        # espn comparison
        esp = None
        if identity["status"] == "matched":
            lst = espn.get((r["event_id"], identity["espn_id"], MARKETS[r["market"]]), [])
            uniq = {(x["line"], x["open"], x["updated"]) for x in lst}
            esp = {"n_rows": len(lst), "unique": sorted(uniq, key=lambda t: (t[2] or ""))}
            dk = lines_seen and None
        dk_line = None
        for pt, bks in lines_seen.items():
            if "draftkings" in bks:
                dk_line = pt
        # lock check: Over at book A (line La) plus Under at book B (line Lb), La <= Lb, so at least one side wins.
        # Guaranteed profit exists only if implied(Over) + implied(Under) < 1. Pure arithmetic on sourced prices.
        best_lock = None
        for la, bks_a in lines_seen.items():
            for lb, bks_b in lines_seen.items():
                if la > lb:
                    continue
                for ba, (oa, _, _) in bks_a.items():
                    for bb, (_, ub, _) in bks_b.items():
                        if ba == bb:
                            continue
                        s = prob(oa) + prob(ub)
                        if best_lock is None or s < best_lock["sum"]:
                            best_lock = {"sum": round(s, 4), "over_book": ba, "over_line": la, "over_price": oa,
                                         "under_book": bb, "under_line": lb, "under_price": ub}
        review.append({"lock": best_lock, "event_id": r["event_id"], "odds_event_id": r["odds_event_id"], "kickoff_utc": r["kickoff_utc"],
                       "matchup": r["away"] + " at " + r["home"], "market": r["market"], "player": r["player"],
                       "identity": identity, "per_line": per_line, "dup_flags": dup_flags, "espn_dk": esp,
                       "feed_dk_line": dk_line, "n_books_total": len(r["books"])})

    inv = {v: k for k, v in MARKETS.items()}
    seen = set()
    for x in review:
        if x["identity"]["status"] == "matched":
            seen.add((x["event_id"], x["identity"]["espn_id"], MARKETS[x["market"]]))
    espn_only = []
    for (eid, aid, tn), lst in sorted(espn.items()):
        if (eid, aid, tn) not in seen:
            a = by_id.get(aid, {})
            espn_only.append({"event_id": eid, "espn_id": aid, "player": a.get("name"), "team": a.get("team"),
                              "pos": a.get("pos"), "market": inv[tn], "line": lst[0]["line"], "updated": lst[0]["updated"]})

    out = {"espn_only": espn_only, "feed_captured_utc": feed["captured_utc"], "espn_capture_utc": man["retrieved_utc"],
           "unmatched_events": unmatched_events, "n_rows": len(review), "review": review,
           "feed_missing": feed.get("missing"), "feed_observations": feed.get("observations")}
    json.dump(out, open(out_p, "w"), indent=1, default=str)
    print("rows", len(review), "unmatched events", unmatched_events)
    print(collections.Counter(x["identity"]["status"] for x in review))
    print(collections.Counter(x["market"] for x in review))


if __name__ == "__main__":
    main(*sys.argv[1:5])
