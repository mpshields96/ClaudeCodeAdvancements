#!/usr/bin/env python3
"""Summary statistics behind PROP_REVIEW.md. Reads review.json from props_review.py. No network. Stdlib only.
Usage: props_review_stats.py <review.json>
Run as: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I props_review_stats.py <review.json>
"""
import json, sys, collections, statistics


def prob(price):
    return 100.0 / (price + 100.0) if price > 0 else -price / (-price + 100.0)


def main(p):
    d = json.load(open(p))
    R = d["review"]
    print("feed", d["feed_captured_utc"], "espn", d["espn_capture_utc"], "rows", len(R))
    print("rows by market", dict(collections.Counter(x["market"] for x in R)))
    print("identity", dict(collections.Counter(x["identity"]["status"] for x in R)))
    print("dup_flags rows", sum(1 for x in R if x["dup_flags"]), "unmatched events", d["unmatched_events"])
    print("injury-flagged rows", sum(1 for x in R if x["identity"].get("injuries")))

    # book coverage per row
    print("books per row", dict(sorted(collections.Counter(x["n_books_total"] for x in R).items())))

    # lines per row
    nl = collections.Counter(len(x["per_line"]) for x in R)
    print("distinct lines per row", dict(sorted(nl.items())))
    spread = [max(pl["line"] for pl in x["per_line"]) - min(pl["line"] for pl in x["per_line"]) for x in R if x["per_line"]]
    print("line spread (max-min) median", statistics.median(spread), "max", max(spread), "rows with spread 0:", sum(1 for s in spread if s == 0))
    for mk in ("player_pass_yds", "player_rush_yds", "player_reception_yds"):
        sp = [max(pl["line"] for pl in x["per_line"]) - min(pl["line"] for pl in x["per_line"]) for x in R if x["market"] == mk and x["per_line"]]
        print("  spread", mk, "n", len(sp), "median", statistics.median(sp), "max", max(sp))
    # rows where the most-posted line is posted by 4+ books
    m4 = sum(1 for x in R if x["per_line"] and max(pl["n_books"] for pl in x["per_line"]) >= 4)
    print("rows with 4+ books on one line", m4)

    # holds per book
    holds = collections.defaultdict(list)
    for x in R:
        for pl in x["per_line"]:
            for b, v in pl["books"].items():
                holds[b].append(v["hold"])
    for b, h in sorted(holds.items()):
        print("hold", b, "n", len(h), "median %.4f min %.4f max %.4f" % (statistics.median(h), min(h), max(h)))

    # best price against same-line consensus: positive means the best quote beats the book-average fair probability
    for k in (2, 3, 4):
        edges = []
        for x in R:
            for pl in x["per_line"]:
                if pl["n_books"] >= k:
                    c = pl["consensus_p_over"]
                    eo = c - prob(pl["best_over"]["price"])
                    eu = (1 - c) - prob(pl["best_under"]["price"])
                    edges.append(max(eo, eu))
        pos = sum(1 for e in edges if e > 0)
        print("same-line lines with >=%d books: n %d, best-side edge vs book-average fair: max %.4f median %.4f, count > 0: %d" % (k, len(edges), max(edges), statistics.median(edges), pos))

    # DK feed line against ESPN current line
    comp = same = 0
    diffs = []
    for x in R:
        e = x["espn_dk"]
        if e and e["unique"] and x["feed_dk_line"] is not None:
            comp += 1
            latest = sorted(e["unique"], key=lambda t: t[2] or "")[-1]
            if latest[0] == x["feed_dk_line"]:
                same += 1
            else:
                diffs.append((x["player"], x["market"], x["feed_dk_line"], latest[0]))
    print("DK comparable", comp, "identical", same, "different", diffs)
    nodk = sum(1 for x in R if x["feed_dk_line"] is None)
    print("rows with no DK quote in feed", nodk)
    noesp = sum(1 for x in R if x["identity"]["status"] == "matched" and (not x["espn_dk"] or not x["espn_dk"]["unique"]))
    print("matched rows with no ESPN DK row", noesp)

    # ESPN timestamps after capture
    late = 0
    tot = 0
    mx = ""
    for x in R:
        e = x["espn_dk"]
        if e:
            for u in e["unique"]:
                tot += 1
                if u[2] and u[2] > d["espn_capture_utc"][:16] + "Z":
                    late += 1
                if u[2] and u[2] > mx:
                    mx = u[2]
    print("ESPN unique (line,open,updated) tuples", tot, "with lastUpdated after capture minute", late, "latest", mx)

    # lock check
    locks = sorted(x["lock"]["sum"] for x in R if x.get("lock"))
    print("lock rows", len(locks), "min", locks[0], "median", locks[len(locks) // 2], "below 1:", sum(1 for s in locks if s < 1), "below 1.02:", sum(1 for s in locks if s < 1.02))


if __name__ == "__main__":
    main(sys.argv[1])
