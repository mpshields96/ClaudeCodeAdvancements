#!/usr/bin/python3
"""Base rate for the Warren role forecast. Rules fixed here BEFORE the first run.

Question: when a running back with a steady target role has one low-target game,
how often does he draw 4+ targets in his next appearance?

Population: nflverse weekly player stats, position == "RB", season_type == "REG".
An appearance is one row for that player in that season; appearances are ordered
by week within a player-season. Windows never cross seasons. Empty targets = 0.

Index i is the outcome appearance. "Prior seven" = appearances i-8 .. i-2.
"Dip game" = appearance i-1.
  A  dip, strict    prior seven each >= 4 targets, dip game <= 2 targets
  B  dip, broad     prior seven mean >= 4.0 targets, dip game <= 2 targets
  C  control for A  prior seven each >= 4 targets, dip game unconditioned
  D  control for B  prior seven mean >= 4.0 targets, dip game unconditioned
Outcome: targets >= 4 at appearance i. Secondary, information only: receiving
yards > 22.5 at appearance i.

Main sample: seasons 2022-2025. The 2026 file (weeks 1-10) is listed separately
with Jaylen Warren (00-0037228) excluded. One rule set, run once, no tuning.
Wilson 95% intervals treat instances as independent, which they are not (one
player-season can give several), so the intervals are too narrow if anything.
Information only: no call, price or live rule changes; no profit claim.
"""
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict

WARREN = "00-0037228"


def wilson(wins, n, z=1.959964):
    if not n:
        return None
    p = wins / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, mid - half), 4), round(min(1.0, mid + half), 4)]


def num(text):
    try:
        return float(text) if str(text).strip() else 0.0
    except ValueError:
        return 0.0


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path, drop=None):
    seasons = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("position") != "RB" or row.get("season_type") != "REG":
                continue
            if drop and row.get("player_id") == drop:
                continue
            seasons[(row["player_id"], row["season"])].append(
                (int(num(row["week"])), num(row.get("targets")),
                 num(row.get("receiving_yards")), row.get("player_display_name", "")))
    for key in seasons:
        seasons[key].sort()
    return seasons


def tally(seasons):
    out = {rule: {"n": 0, "hit": 0, "yards_over": 0, "player_seasons": set(), "cases": []}
           for rule in "ABCD"}
    for key, games in seasons.items():
        for i in range(8, len(games)):
            prior = [g[1] for g in games[i - 8:i - 1]]
            dip = games[i - 1][1]
            strict = all(t >= 4 for t in prior)
            broad = sum(prior) / 7.0 >= 4.0
            rules = []
            if strict and dip <= 2:
                rules.append("A")
            if broad and dip <= 2:
                rules.append("B")
            if strict:
                rules.append("C")
            if broad:
                rules.append("D")
            for rule in rules:
                bucket = out[rule]
                bucket["n"] += 1
                bucket["hit"] += games[i][1] >= 4
                bucket["yards_over"] += games[i][2] > 22.5
                bucket["player_seasons"].add(key)
                if rule in "AB":
                    bucket["cases"].append(
                        "%s %s wk%d: prior %s, dip %d, next %d tgt %d yds"
                        % (games[i][3], key[1], games[i][0],
                           "/".join(str(int(t)) for t in prior), dip,
                           games[i][1], games[i][2]))
    return out


def report(label, out):
    result = {}
    print(label)
    for rule in "ABCD":
        b = out[rule]
        n, hit, yds = b["n"], b["hit"], b["yards_over"]
        result[rule] = {"instances": n, "player_seasons": len(b["player_seasons"]),
                        "targets_4plus": hit, "rate": round(hit / n, 4) if n else None,
                        "wilson95": wilson(hit, n), "rec_yards_over_22_5": yds,
                        "yards_rate": round(yds / n, 4) if n else None,
                        "yards_wilson95": wilson(yds, n), "cases": b["cases"]}
        print("  %s: %d instance(s) in %d player-season(s); 4+ targets %d (%s, Wilson %s); "
              ">22.5 yds %d (%s)" % (rule, n, len(b["player_seasons"]), hit,
                                    result[rule]["rate"], result[rule]["wilson95"], yds,
                                    result[rule]["yards_rate"]))
    return result


def main(argv):
    out_path, main_files, extra = argv[1], argv[2:6], argv[6]
    merged = {}
    files = {}
    for path in main_files:
        files[path.rsplit("/", 1)[-1]] = sha(path)
        merged.update(load(path))
    files[extra.rsplit("/", 1)[-1]] = sha(extra)
    result = {"files_sha256": files,
              "main_2022_2025": report("2022-2025 regular season, RB", tally(merged)),
              "listed_2026_wk1_10_ex_warren":
                  report("2026 weeks 1-10, RB, Warren excluded", tally(load(extra, WARREN)))}
    for rule in "AB":
        for case in result["main_2022_2025"][rule]["cases"]:
            print("    %s %s" % (rule, case))
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv)
