#!/usr/bin/env python3
"""Turn props_review.py output into markdown tables and summary counts. Stdlib only. No network.
Usage: props_review_tables.py <review.json> <out_tables.md>
"""
import json, sys, collections

SHORT = {"player_pass_yds": "pass yds", "player_rush_yds": "rush yds", "player_reception_yds": "rec yds"}
# feed key espnbet carries the title "theScore Bet" in sunday-odds.json; labelled tSB here so it is not confused with ESPN, the DraftKings line source
BK = {"draftkings": "DK", "fanduel": "FD", "betmgm": "MGM", "espnbet": "tSB", "betrivers": "BR"}
# props named in Codex's Matchup_Review.md (its shortlist and its closest passes); listed here only to print their feed ladders
CODEX_NAMED = [("Jaylen Warren", "player_reception_yds"), ("Rico Dowdle", "player_reception_yds"), ("Joe Burrow", "player_rush_yds"),
               ("Joe Burrow", "player_pass_yds"), ("Emmett Johnson", "player_rush_yds"), ("Emmett Johnson", "player_reception_yds"),
               ("John Metchie III", "player_reception_yds"), ("Jordan Love", "player_pass_yds"), ("Brock Bowers", "player_reception_yds"),
               ("Jaxon Smith-Njigba", "player_reception_yds")]


def modal(x):
    # line posted by the most books; ties go to the line with the most books then the lower line
    pl = sorted(x["per_line"], key=lambda p: (-p["n_books"], p["line"]))
    return pl[0] if pl else None


def fmt_price(p):
    return ("+%d" % p) if p > 0 else str(p)


def main(rev_p, out_p):
    d = json.load(open(rev_p))
    R = d["review"]
    lines = []
    stats = collections.Counter()
    elig = []
    for x in R:
        m = modal(x)
        ident = x["identity"]
        inj = ident.get("injuries") or []
        dk_ok = None
        e = x["espn_dk"]
        if e and e["unique"] and x["feed_dk_line"] is not None:
            latest = sorted(e["unique"], key=lambda t: t[2] or "")[-1]
            dk_ok = (latest[0] == x["feed_dk_line"])
        gates = {
            "identity": ident["status"] == "matched",
            "books4": bool(m) and m["n_books"] >= 4,
            "no_inj_flag": not inj,
            "dk_agrees": dk_ok is True,
        }
        x["_gates"] = gates
        x["_modal"] = m
        ok = all(gates.values())
        stats["all_gates"] += ok
        for k, v in gates.items():
            stats["fail_" + k] += (not v)
        if ok:
            elig.append(x)
    stats["rows"] = len(R)
    out = []
    out.append("### A. Quarterback passing-yards lines (24 starters, full game)\n")
    out.append("| Game | QB | Line (books at that line) | Other lines | Over best | Under best | Consensus P(over) | Flags |")
    out.append("|---|---|---|---|---|---|---|---|")
    for x in sorted((r for r in R if r["market"] == "player_pass_yds"), key=lambda r: (r["kickoff_utc"], r["matchup"])):
        m = x["_modal"]
        others = ", ".join("%s (%d)" % (p["line"], p["n_books"]) for p in x["per_line"] if p is not m) or "none"
        fl = []
        if x["identity"].get("injuries"):
            fl.append("injury: " + x["identity"]["injuries"][0]["status"])
        if not x["_gates"]["dk_agrees"]:
            fl.append("DK-vs-ESPN line not confirmed")
        out.append("| %s | %s | %s (%d) | %s | %s %s | %s %s | %.3f | %s |" % (
            x["matchup"], x["player"], m["line"], m["n_books"], others,
            BK[m["best_over"]["book"]], fmt_price(m["best_over"]["price"]),
            BK[m["best_under"]["book"]], fmt_price(m["best_under"]["price"]),
            m["consensus_p_over"], "; ".join(fl) or "-"))
    out.append("")
    out.append("### B. Injury-flagged props (ESPN roster status at 06:58:49Z, before final inactives)\n")
    out.append("| Game | Player | Market | Status (ESPN, as of) | Modal line |")
    out.append("|---|---|---|---|---|")
    for x in R:
        inj = x["identity"].get("injuries") or []
        if inj:
            out.append("| %s | %s | %s | %s (%s) | %s |" % (x["matchup"], x["player"], SHORT[x["market"]], inj[0]["status"], inj[0]["date"], x["_modal"]["line"] if x["_modal"] else "-"))
    out.append("")
    out.append("### C. Identity not resolved (name absent from both ESPN rosters at capture; not guessed)\n")
    for x in R:
        if x["identity"]["status"] != "matched":
            out.append("- %s, %s, %s, books posting: %d, lines: %s" % (x["player"], x["matchup"], SHORT[x["market"]], x["n_books_total"], ", ".join(str(p["line"]) for p in x["per_line"])))
    out.append("")
    out.append("### D. Thin coverage (2 books or fewer)\n")
    for x in R:
        if x["n_books_total"] <= 2:
            out.append("- %s (%s), %s, %d book(s): %s" % (x["player"], x["matchup"], SHORT[x["market"]], x["n_books_total"],
                       "; ".join("%s %s" % (BK[b], x["per_line"][0]["line"]) if False else BK[b] for b in sorted({b for p in x["per_line"] for b in p["books"]}))))
    out.append("")
    out.append("### E. DraftKings line mismatches, feed 06:55Z against ESPN 06:58Z\n")
    for x in R:
        e = x["espn_dk"]
        if e and e["unique"] and x["feed_dk_line"] is not None and not x["_gates"]["dk_agrees"]:
            out.append("- %s (%s), %s: feed DK %s; ESPN current %s, open %s, ESPN lastUpdated %s" % (x["player"], x["matchup"], SHORT[x["market"]], x["feed_dk_line"], e["unique"][-1][0], e["unique"][-1][1], e["unique"][-1][2]))
    out.append("")
    out.append("### F. In the ESPN DraftKings capture but not in the shared feed (full-game yards and the matching feed markets only)\n")
    eo = d["espn_only"]
    out.append("%d ESPN rows. By market: %s.\n" % (len(eo), dict(collections.Counter(r["market"] for r in eo))))
    out.append("### F2. Cross-book lock check (Over at one book, Under at another, Over line not above Under line)\n")
    locks = [x for x in R if x.get("lock")]
    sums = sorted(x["lock"]["sum"] for x in locks)
    stats["lock_rows"] = len(locks)
    stats["lock_sum_lt_1"] = sum(1 for s in sums if s < 1)
    stats["lock_sum_min"] = sums[0] if sums else None
    stats["lock_sum_median"] = sums[len(sums) // 2] if sums else None
    out.append("%d rows checked. Smallest combined implied probability %s (below 1.000 would be a guaranteed profit before limits, rules and the unverified Louisiana availability); median %s; rows below 1.000: %d.\n" % (
        len(locks), stats["lock_sum_min"], stats["lock_sum_median"], stats["lock_sum_lt_1"]))
    out.append("| Closest five | Over | Under | Sum |")
    out.append("|---|---|---|---|")
    for x in sorted(locks, key=lambda r: r["lock"]["sum"])[:5]:
        k = x["lock"]
        out.append("| %s, %s (%s) | %s %s @ %s | %s %s @ %s | %.4f |" % (x["player"], SHORT[x["market"]], x["matchup"].replace(" at ", " @ "),
                   BK[k["over_book"]], k["over_line"], fmt_price(k["over_price"]), BK[k["under_book"]], k["under_line"], fmt_price(k["under_price"]), k["sum"]))
    out.append("")
    out.append("### G. Passed every gate (identity, 4+ books on the line, no injury flag, DraftKings equals ESPN)\n")
    out.append("%d of %d rows. These are market-quality gates only. They say nothing about whether the line is wrong.\n" % (stats["all_gates"], stats["rows"]))
    out.append("| Game | Player | Market | Line (books) | Over best | Under best | P(over) consensus |")
    out.append("|---|---|---|---|---|---|---|")
    for x in sorted(elig, key=lambda r: (r["kickoff_utc"], r["matchup"], r["market"], r["player"])):
        m = x["_modal"]
        out.append("| %s | %s | %s | %s (%d) | %s %s | %s %s | %.3f |" % (
            x["matchup"].replace(" at ", " @ "), x["player"], SHORT[x["market"]], m["line"], m["n_books"],
            BK[m["best_over"]["book"]], fmt_price(m["best_over"]["price"]),
            BK[m["best_under"]["book"]], fmt_price(m["best_under"]["price"]), m["consensus_p_over"]))
    out.append("")
    out.append("### H. Props named in Codex's Matchup_Review.md: the feed ladder for each (price shown as Over / Under)\n")
    out.append("| Player, market | Ladder in the 06:55Z feed (line: book over/under) | DraftKings on ESPN: open to current | ESPN roster status |")
    out.append("|---|---|---|---|")
    for nm, mk in CODEX_NAMED:
        for x in R:
            if x["player"] == nm and x["market"] == mk:
                lad = "; ".join("%s: %s" % (p["line"], ", ".join("%s %s/%s" % (BK[b], fmt_price(v["over"]), fmt_price(v["under"])) for b, v in sorted(p["books"].items()))) for p in x["per_line"])
                e = x["espn_dk"]
                mv = "%s to %s" % (e["unique"][-1][1], e["unique"][-1][0]) if e and e["unique"] else "n/a"
                inj = x["identity"].get("injuries") or []
                out.append("| %s, %s (%s) | %s | %s | %s |" % (nm, SHORT[mk], x["matchup"].replace(" at ", " @ "), lad, mv,
                           "%s (%s)" % (inj[0]["status"], inj[0]["date"]) if inj else "none listed"))
    open(out_p, "w").write("\n".join(out) + "\n")
    print(dict(stats))
    print("espn_only", len(eo), collections.Counter(r["market"] for r in eo))
    print("espn_only unmatched player names", sum(1 for r in eo if not r["player"]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
