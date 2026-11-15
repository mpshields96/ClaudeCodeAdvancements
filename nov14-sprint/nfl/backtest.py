#!/usr/bin/env python3
"""Backtest of the pre-registered NFL rules in RULES.md. Paper research only.

Run from anywhere:
    python3 -I nov14-sprint/nfl/backtest.py            # full run
    python3 -I nov14-sprint/nfl/backtest.py --selftest # convention checks

Standard library only, Python 3.9 compatible. Reads data/raw/games.csv
(hash-checked against data/raw/MANIFEST.json). Writes only inside this
folder: frozen_rules.json (first run), VARIANT_LOG.jsonl (append),
results/backtest_results.json, results/backtest_report.txt.

Order of work, matching RULES.md:
  1. score all 10 variants on TRAINING seasons only
  2. choose one variant per family from training, freeze it
  3. score only the frozen variants on HELD-OUT seasons, once
"""
import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)  # -I mode leaves the script folder off sys.path
import rules  # noqa: E402

TRAIN = (2006, 2022)
HOLDOUT = (2023, 2025)
MIN_TRAIN_BETS = 150
WIN_PAYOUT_110 = 100.0 / 110.0   # +0.9091 units per unit risked
BREAKEVEN = 110.0 / 210.0        # 52.38%
BOOT_N = 10000
BOOT_SEED = 20261114
Z95 = 1.959963984540054
Z_BONF = statistics.NormalDist().inv_cdf(1 - 0.0125 / 2)  # 98.75% two-sided

# The ONLY fields a rule may see. Scores never enter this dict.
PRE_GAME_FIELDS = ("spread_line", "total_line", "away_rest", "home_rest")

DATA_REL = os.path.join("data", "raw", "games.csv")
MANIFEST_REL = os.path.join("data", "raw", "MANIFEST.json")


class Refused(Exception):
    pass


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(s, cast):
    s = (s or "").strip()
    if s == "" or s.upper() == "NA":
        return None
    try:
        return cast(float(s)) if cast is int else cast(s)
    except ValueError:
        return None


def load_games(data_path, manifest_path):
    """Hash-check the CSV against the manifest, then parse it as data."""
    if not os.path.isfile(data_path):
        raise Refused("INPUT_MISSING: %s" % data_path)
    if not os.path.isfile(manifest_path):
        raise Refused("MANIFEST_MISSING: %s" % manifest_path)
    with open(manifest_path) as fh:
        manifest = json.load(fh)
    entry = None
    for f in manifest.get("files", []):
        if f.get("path", "").endswith("games.csv"):
            entry = f
    if entry is None:
        raise Refused("MANIFEST_MISSING: no games.csv entry")
    with open(data_path, "rb") as fh:
        raw = fh.read()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != entry["sha256"] or len(raw) != entry["bytes"]:
        raise Refused("INPUT_HASH_MISMATCH: %s has sha256 %s (%d bytes); "
                      "manifest expects %s (%d bytes)"
                      % (data_path, sha, len(raw), entry["sha256"], entry["bytes"]))
    games = []
    reader = csv.DictReader(raw.decode("utf-8").splitlines())
    for r in reader:
        if r.get("game_type") != "REG":
            continue
        season = _num(r.get("season"), int)
        hs = _num(r.get("home_score"), float)
        as_ = _num(r.get("away_score"), float)
        if season is None or hs is None or as_ is None:
            continue  # not final yet
        games.append({
            "game_id": r["game_id"], "season": season,
            "spread_line": _num(r.get("spread_line"), float),
            "total_line": _num(r.get("total_line"), float),
            "away_rest": _num(r.get("away_rest"), int),
            "home_rest": _num(r.get("home_rest"), int),
            "home_score": hs, "away_score": as_,
            "home_spread_odds": _num(r.get("home_spread_odds"), float),
            "away_spread_odds": _num(r.get("away_spread_odds"), float),
            "under_odds": _num(r.get("under_odds"), float),
            "over_odds": _num(r.get("over_odds"), float),
        })
    return games, entry


def pre_game_view(g):
    """What a rule is allowed to see. Built fresh so no score can leak."""
    view = {k: g[k] for k in PRE_GAME_FIELDS}
    assert set(view) == set(PRE_GAME_FIELDS)
    return view


def recorded_price(g, market, side):
    if market == "spread":
        return g["home_spread_odds"] if side == "home" else g["away_spread_odds"]
    return g["under_odds"] if side == "under" else g["over_odds"]


def bet_return(outcome, price=None):
    """Return in units for a 1-unit bet. price None means flat -110."""
    if outcome == "push":
        return 0.0
    if outcome == "loss":
        return -1.0
    return WIN_PAYOUT_110 if price is None else rules.american_profit(price, 1.0)


def empty_tally():
    return {"bets": 0, "w": 0, "l": 0, "p": 0, "returns": [],
            "passes": 0, "shadow_w": 0, "shadow_l": 0, "shadow_p": 0,
            "passes_no_side": 0, "skipped_missing_input": 0,
            "returns_recorded": [], "recorded_price_missing": 0}


def score(decider, games):
    """decider(view) -> rules.decide-style dict. Scores takes AND passes."""
    t = empty_tally()
    for g in games:
        try:
            d = decider(pre_game_view(g))
        except ValueError:
            t["skipped_missing_input"] += 1
            continue
        if d["side"] is None:
            t["passes"] += 1
            t["passes_no_side"] += 1
            continue
        outcome = rules.grade(d["market"], d["side"], d["line"],
                              g["home_score"], g["away_score"])
        if d["action"] == "take":
            t["bets"] += 1
            t[{"win": "w", "loss": "l", "push": "p"}[outcome]] += 1
            t["returns"].append(bet_return(outcome))
            price = recorded_price(g, d["market"], d["side"])
            if price is None:
                t["recorded_price_missing"] += 1
                t["returns_recorded"].append(bet_return(outcome))
            else:
                t["returns_recorded"].append(bet_return(outcome, price))
        else:
            t["passes"] += 1
            t[{"win": "shadow_w", "loss": "shadow_l", "push": "shadow_p"}[outcome]] += 1
    return t


def wilson(w, n, z):
    if n == 0:
        return (None, None)
    p = w / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - half, centre + half)


def binom_tail(w, n, p0):
    """P(X >= w) for X ~ Binomial(n, p0), in log space."""
    if n == 0:
        return None
    total = 0.0
    for k in range(w, n + 1):
        lg = (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
              + k * math.log(p0) + (n - k) * math.log(1 - p0))
        total += math.exp(lg)
    return min(1.0, total)


def boot_roi_ci(returns, seed):
    n = len(returns)
    if n == 0:
        return (None, None)
    rng = random.Random(seed)
    means = []
    for _ in range(BOOT_N):
        means.append(sum(rng.choices(returns, k=n)) / n)
    means.sort()
    return (means[int(0.025 * BOOT_N)], means[int(0.975 * BOOT_N) - 1])


def summarize(t, with_intervals):
    decided = t["w"] + t["l"]
    out = {
        "bets": t["bets"], "wins": t["w"], "losses": t["l"], "pushes": t["p"],
        "win_rate": (t["w"] / decided) if decided else None,
        "roi_at_minus110": (sum(t["returns"]) / t["bets"]) if t["bets"] else None,
        "units_at_minus110": sum(t["returns"]),
        "passes": t["passes"],
        "shadow_record_of_passes": [t["shadow_w"], t["shadow_l"], t["shadow_p"]],
        "passes_no_side": t["passes_no_side"],
        "skipped_missing_input": t["skipped_missing_input"],
    }
    sd = t["shadow_w"] + t["shadow_l"]
    out["shadow_win_rate_of_passes"] = (t["shadow_w"] / sd) if sd else None
    if with_intervals:
        lo, hi = wilson(t["w"], decided, Z95)
        blo, bhi = wilson(t["w"], decided, Z_BONF)
        rlo, rhi = boot_roi_ci(t["returns"], BOOT_SEED)
        out.update({
            "win_rate_ci95": [lo, hi],
            "win_rate_ci98_75_bonferroni": [blo, bhi],
            "roi_ci95_bootstrap": [rlo, rhi],
            "p_value_one_sided_vs_breakeven": binom_tail(t["w"], decided, BREAKEVEN),
            "roi_at_recorded_odds": (sum(t["returns_recorded"]) / t["bets"]) if t["bets"] else None,
            "recorded_price_missing": t["recorded_price_missing"],
        })
    return out


def in_range(g, rng):
    return rng[0] <= g["season"] <= rng[1]


def variant_decider(family, value):
    return lambda view: rules.decide(family, value, view)


def baseline_deciders():
    def always_home(v):
        if v["spread_line"] is None:
            raise ValueError("missing input: spread_line")
        return {"action": "take", "market": "spread", "side": "home",
                "line": v["spread_line"], "reason": "baseline"}

    def always_dog(v):
        if v["spread_line"] is None:
            raise ValueError("missing input: spread_line")
        sl = v["spread_line"]
        side = None if sl == 0 else ("away" if sl > 0 else "home")
        return {"action": "take" if side else "pass", "market": "spread",
                "side": side, "line": sl, "reason": "baseline"}

    def always_under(v):
        if v["total_line"] is None:
            raise ValueError("missing input: total_line")
        return {"action": "take", "market": "total", "side": "under",
                "line": v["total_line"], "reason": "baseline"}

    return [("BASELINE_ALWAYS_HOME", always_home),
            ("BASELINE_ALWAYS_DOG", always_dog),
            ("BASELINE_ALWAYS_UNDER", always_under)]


def pct(x):
    return "   n/a" if x is None else "%6.2f%%" % (100.0 * x)


def run(args):
    data_path = args.data or os.path.join(HERE, DATA_REL)
    manifest_path = os.path.join(HERE, MANIFEST_REL)
    games, src = load_games(data_path, manifest_path)
    train = [g for g in games if in_range(g, TRAIN)]
    hold = [g for g in games if in_range(g, HOLDOUT)]
    run_ts = utc_now()
    log_lines = []
    lines = []
    P = lines.append

    P("NFL rule backtest (paper research only). Run %s" % run_ts)
    P("Data: %s" % src["url"])
    P("  retrieved %s, %d bytes, sha256 %s" % (src["retrieved_at_utc"], src["bytes"], src["sha256"]))
    P("Line: nflverse spread_line / total_line (one number per game; book and capture time not stated by the source).")
    P("Price: flat -110 both sides. Win +0.9091u, loss -1u, push 0. Break-even %.2f%%." % (100 * BREAKEVEN))
    P("Training seasons %d-%d: %d regular-season games. Held-out %d-%d: %d games."
      % (TRAIN[0], TRAIN[1], len(train), HOLDOUT[0], HOLDOUT[1], len(hold)))
    P("")

    # ---- Step 1: every variant on TRAINING only -------------------------
    P("STEP 1. All 10 pre-registered variants, TRAINING seasons only")
    P("%-26s %6s %-14s %8s %8s %7s  %s" % ("variant", "bets", "W-L-P", "win%", "ROI", "passes", "shadow W-L-P of passes"))
    train_stats = {}
    for fam, value, vid in rules.all_variants():
        s = summarize(score(variant_decider(fam, value), train), False)
        train_stats[vid] = (fam, value, s)
        P("%-26s %6d %-14s %8s %8s %7d  %d-%d-%d (%s)" % (
            vid, s["bets"], "%d-%d-%d" % (s["wins"], s["losses"], s["pushes"]),
            pct(s["win_rate"]), pct(s["roi_at_minus110"]), s["passes"],
            s["shadow_record_of_passes"][0], s["shadow_record_of_passes"][1],
            s["shadow_record_of_passes"][2], pct(s["shadow_win_rate_of_passes"]).strip()))

    # ---- Step 2: choose per family on training, then freeze --------------
    chosen = []
    for fam in rules.FAMILY_ORDER:
        best = None
        for value in rules.FAMILIES[fam]["grid"]:
            vid = rules.version_id(fam, value)
            s = train_stats[vid][2]
            if s["bets"] < MIN_TRAIN_BETS or s["roi_at_minus110"] is None:
                continue
            if best is None or s["roi_at_minus110"] > best[2]:
                best = (vid, value, s["roi_at_minus110"])
        if best is None:
            raise Refused("NO_ELIGIBLE_VARIANT: %s has no variant with %d training bets" % (fam, MIN_TRAIN_BETS))
        chosen.append({"version_id": best[0], "family": fam, "value": best[1],
                       "train_roi_at_minus110": best[2]})
    chosen_ids = [c["version_id"] for c in chosen]

    for vid, (fam, value, s) in train_stats.items():
        log_lines.append({"run_ts_utc": run_ts, "data_sha256": src["sha256"], "period": "train",
                          "seasons": list(TRAIN), "role": "candidate", "version_id": vid,
                          "family": fam, "value": value, "selected": vid in chosen_ids,
                          "bets": s["bets"], "wins": s["wins"], "losses": s["losses"],
                          "pushes": s["pushes"], "win_rate": s["win_rate"],
                          "roi_at_minus110": s["roi_at_minus110"], "passes": s["passes"]})

    frozen_path = os.path.join(HERE, "frozen_rules.json")
    if os.path.isfile(frozen_path):
        with open(frozen_path) as fh:
            frozen = json.load(fh)
        frozen_ids = [r["version_id"] for r in frozen["rules"]]
        if frozen_ids != chosen_ids or frozen.get("data_sha256") != src["sha256"]:
            raise Refused("FROZEN_MISMATCH: frozen_rules.json has %s on data %s; this run chose %s on data %s. "
                          "A changed rule or dataset is a new version, not a replay."
                          % (frozen_ids, frozen.get("data_sha256"), chosen_ids, src["sha256"]))
        freeze_note = "frozen_rules.json already existed (frozen %s); this run's training choice matches it." % frozen["frozen_at_utc"]
    else:
        frozen = {"frozen_at_utc": run_ts, "ruleset_version": rules.RULESET_VERSION,
                  "data_sha256": src["sha256"], "train_seasons": list(TRAIN),
                  "holdout_seasons": list(HOLDOUT),
                  "selection": "highest training ROI at -110 per family, min %d training bets" % MIN_TRAIN_BETS,
                  "rules": chosen}
        with open(frozen_path, "w") as fh:
            json.dump(frozen, fh, indent=2)
            fh.write("\n")
        freeze_note = "frozen_rules.json written now (%s), before any held-out scoring." % run_ts
    P("")
    P("STEP 2. Chosen on training and frozen: %s" % ", ".join(chosen_ids))
    P("  %s" % freeze_note)
    P("")

    # ---- Step 3: frozen variants on HELD-OUT, once -----------------------
    P("STEP 3. Frozen variants on HELD-OUT seasons %d-%d (the other 6 variants are never scored here)" % HOLDOUT)
    hold_stats = {}
    for c in chosen:
        t = score(variant_decider(c["family"], c["value"]), hold)
        s = summarize(t, True)
        by_season = {}
        for yr in range(HOLDOUT[0], HOLDOUT[1] + 1):
            ys = summarize(score(variant_decider(c["family"], c["value"]),
                                 [g for g in hold if g["season"] == yr]), False)
            by_season[str(yr)] = {"bets": ys["bets"], "record": "%d-%d-%d" % (ys["wins"], ys["losses"], ys["pushes"]),
                                  "roi_at_minus110": ys["roi_at_minus110"]}
        s["by_season"] = by_season
        edge = (c["train_roi_at_minus110"] > 0 and s["win_rate_ci95"][0] is not None
                and s["win_rate_ci95"][0] > BREAKEVEN)
        s["verdict"] = "EDGE (pre-registered test met)" if edge else "NO DEMONSTRATED EDGE"
        hold_stats[c["version_id"]] = s
        P("")
        P("%s   -> %s" % (c["version_id"], s["verdict"]))
        P("  training ROI %s (%s)" % (pct(c["train_roi_at_minus110"]).strip(),
                                      "above zero" if c["train_roi_at_minus110"] > 0 else "NOT above zero"))
        P("  takes: %d bets, record %d-%d-%d, win rate %s (break-even %.2f%%)"
          % (s["bets"], s["wins"], s["losses"], s["pushes"], pct(s["win_rate"]).strip(), 100 * BREAKEVEN))
        P("  win-rate 95%% interval %s to %s; Bonferroni 98.75%% interval %s to %s"
          % (pct(s["win_rate_ci95"][0]).strip(), pct(s["win_rate_ci95"][1]).strip(),
             pct(s["win_rate_ci98_75_bonferroni"][0]).strip(), pct(s["win_rate_ci98_75_bonferroni"][1]).strip()))
        P("  ROI after vig at -110: %s (%+.2f units); 95%% bootstrap interval %s to %s"
          % (pct(s["roi_at_minus110"]).strip(), s["units_at_minus110"],
             pct(s["roi_ci95_bootstrap"][0]).strip(), pct(s["roi_ci95_bootstrap"][1]).strip()))
        P("  one-sided p-value against break-even: %.3f" % s["p_value_one_sided_vs_breakeven"])
        P("  ROI at the file's recorded odds: %s (%d bets had no recorded price and used -110)"
          % (pct(s["roi_at_recorded_odds"]).strip(), s["recorded_price_missing"]))
        P("  passes: %d games; shadow record of passes %d-%d-%d (%s); %d passes had no side"
          % (s["passes"], s["shadow_record_of_passes"][0], s["shadow_record_of_passes"][1],
             s["shadow_record_of_passes"][2], pct(s["shadow_win_rate_of_passes"]).strip(), s["passes_no_side"]))
        P("  by season: " + "; ".join("%s %s (%d bets, ROI %s)" % (yr, v["record"], v["bets"], pct(v["roi_at_minus110"]).strip())
                                      for yr, v in sorted(by_season.items())))
        log_lines.append({"run_ts_utc": run_ts, "data_sha256": src["sha256"], "period": "holdout",
                          "seasons": list(HOLDOUT), "role": "frozen", "version_id": c["version_id"],
                          "family": c["family"], "value": c["value"], "selected": True,
                          "bets": s["bets"], "wins": s["wins"], "losses": s["losses"],
                          "pushes": s["pushes"], "win_rate": s["win_rate"],
                          "roi_at_minus110": s["roi_at_minus110"], "passes": s["passes"],
                          "verdict": s["verdict"]})

    # ---- Context only: baselines ----------------------------------------
    P("")
    P("CONTEXT ONLY (never used for selection): baselines at -110")
    base_stats = {}
    for name, dec in baseline_deciders():
        for label, subset, rng in (("train", train, TRAIN), ("holdout", hold, HOLDOUT)):
            s = summarize(score(dec, subset), False)
            base_stats["%s|%s" % (name, label)] = s
            P("  %-22s %-8s %5d bets, %d-%d-%d, win %s, ROI %s"
              % (name, label, s["bets"], s["wins"], s["losses"], s["pushes"],
                 pct(s["win_rate"]).strip(), pct(s["roi_at_minus110"]).strip()))
            log_lines.append({"run_ts_utc": run_ts, "data_sha256": src["sha256"], "period": label,
                              "seasons": list(rng), "role": "baseline", "version_id": name,
                              "selected": False, "bets": s["bets"], "wins": s["wins"],
                              "losses": s["losses"], "pushes": s["pushes"],
                              "win_rate": s["win_rate"], "roi_at_minus110": s["roi_at_minus110"],
                              "passes": s["passes"]})

    # ---- Plain verdict ---------------------------------------------------
    edges = [vid for vid, s in hold_stats.items() if s["verdict"].startswith("EDGE")]
    P("")
    P("RESULT")
    if edges:
        P("  %d of 4 frozen rules met the pre-registered edge test: %s." % (len(edges), ", ".join(edges)))
        P("  This is a historical paper result on one line per game. It authorizes nothing.")
    else:
        P("  No demonstrated edge. None of the 4 frozen rules met the pre-registered test")
        P("  (training ROI above zero AND held-out 95% win-rate interval entirely above 52.38%).")
        P("  The samples are small: this fails to show an edge, it does not prove there is none.")
        P("  The p-values above are one-sided and not adjusted for testing 4 rules (multiply by 4).")
    P("  Variants tried in total: 10 candidates on training, 4 frozen on held-out, 3 context baselines.")

    report = "\n".join(lines) + "\n"
    sys.stdout.write(report)

    results = {"run_ts_utc": run_ts, "data": src, "train_seasons": list(TRAIN),
               "holdout_seasons": list(HOLDOUT), "breakeven": BREAKEVEN,
               "price": "flat -110", "games_train": len(train), "games_holdout": len(hold),
               "training": {vid: v[2] for vid, v in train_stats.items()},
               "frozen": chosen, "holdout": hold_stats, "baselines": base_stats,
               "edges": edges}

    first_path = os.path.join(HERE, "results", "holdout_first_evaluation.json")
    core = json.dumps({"frozen": chosen_ids, "holdout": hold_stats}, sort_keys=True)
    core_sha = hashlib.sha256(core.encode("utf-8")).hexdigest()
    # Every look at the held-out seasons is logged: --no-write runs too, and
    # before the replay check so a REPLAY_MISMATCH run is still on record.
    for ln in log_lines:
        ln["no_write"] = bool(args.no_write)
    with open(os.path.join(HERE, "VARIANT_LOG.jsonl"), "a") as fh:
        for ln in log_lines:
            fh.write(json.dumps(ln, sort_keys=True) + "\n")
    if not args.no_write:
        os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
        if os.path.isfile(first_path):
            with open(first_path) as fh:
                first = json.load(fh)
            same = first.get("core_sha256") == core_sha
            msg = ("Replay check: held-out numbers %s the first evaluation of %s."
                   % ("MATCH" if same else "DO NOT MATCH", first.get("run_ts_utc")))
            sys.stdout.write(msg + "\n")
            report += msg + "\n"
            if not same:
                raise Refused("REPLAY_MISMATCH: held-out result changed since the first evaluation")
        else:
            with open(first_path, "w") as fh:
                json.dump({"run_ts_utc": run_ts, "core_sha256": core_sha,
                           "frozen": chosen_ids}, fh, indent=2)
                fh.write("\n")
        with open(os.path.join(HERE, "results", "backtest_results.json"), "w") as fh:
            json.dump(results, fh, indent=2)
            fh.write("\n")
        with open(os.path.join(HERE, "results", "backtest_report.txt"), "w") as fh:
            fh.write(report)
    return 0


def selftest():
    """Convention and leak checks on hand-made cases. No data file needed."""
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    g = rules.grade
    # home favored by 3 (spread_line +3): home wins by 7 covers, by 3 pushes, by 1 fails
    ok("home fav covers", g("spread", "home", 3.0, 27, 20) == "win")
    ok("home fav push", g("spread", "home", 3.0, 23, 20) == "push")
    ok("home fav fails", g("spread", "home", 3.0, 21, 20) == "loss")
    ok("away dog covers when fav fails", g("spread", "away", 3.0, 21, 20) == "win")
    # home dog +3.5 (spread_line -3.5): loses by 3 covers, loses by 4 fails
    ok("home dog covers", g("spread", "home", -3.5, 17, 20) == "win")
    ok("home dog fails", g("spread", "home", -3.5, 16, 20) == "loss")
    ok("under wins", g("total", "under", 47.5, 20, 17) == "win")
    ok("under loses", g("total", "under", 47.5, 31, 17) == "loss")
    ok("total push", g("total", "under", 47.0, 30, 17) == "push")
    d = rules.decide
    ok("HOME_DOG take", d("HOME_DOG", 3.0, {"spread_line": -3.0})["action"] == "take")
    ok("HOME_DOG pass when favored", d("HOME_DOG", 3.0, {"spread_line": 2.5})["action"] == "pass")
    ok("BIG_DOG picks away dog", d("BIG_DOG", 7.0, {"spread_line": 7.5})["side"] == "away")
    ok("BIG_DOG picks home dog", d("BIG_DOG", 7.0, {"spread_line": -10.0})["side"] == "home")
    ok("REST_EDGE picks rested away", d("REST_EDGE", 3, {"spread_line": 1.0, "away_rest": 14, "home_rest": 7})["side"] == "away")
    ok("REST_EDGE equal rest passes", d("REST_EDGE", 3, {"spread_line": 1.0, "away_rest": 7, "home_rest": 7})["action"] == "pass")
    ok("UNDER take", d("HIGH_TOTAL_UNDER", 47.0, {"total_line": 47.0})["action"] == "take")
    try:
        d("HOME_DOG", 3.0, {"spread_line": None})
        ok("missing line raises", False)
    except ValueError:
        ok("missing line raises", True)
    ok("-110 win pays 0.909", abs(bet_return("win") - 0.90909) < 1e-4)
    ok("+150 win pays 1.5", abs(rules.american_profit(150) - 1.5) < 1e-9)
    ok("-170 win pays 0.588", abs(rules.american_profit(-170) - 100.0 / 170.0) < 1e-9)
    ok("break-even 52.38%", abs(BREAKEVEN - 0.5238) < 1e-4)
    # leak check: a rule sees only pre-game fields, so changing the score cannot change its decision
    base = {"game_id": "x", "season": 2020, "spread_line": -4.0, "total_line": 50.0,
            "away_rest": 7, "home_rest": 10, "home_score": 10.0, "away_score": 40.0}
    flip = dict(base, home_score=40.0, away_score=10.0)
    same = all(d(f, v, pre_game_view(base)) == d(f, v, pre_game_view(flip))
               for f, v, _ in rules.all_variants())
    ok("decisions ignore scores", same)
    ok("pre-game view has no score keys", set(pre_game_view(base)) == set(PRE_GAME_FIELDS))
    lo, hi = wilson(50, 100, Z95)
    ok("wilson 50/100", abs(lo - 0.4038) < 1e-3 and abs(hi - 0.5962) < 1e-3)
    ok("binom tail sums to 1", abs(binom_tail(0, 30, 0.5238) - 1.0) < 1e-9)
    bad = [n for n, c in checks if not c]
    for n, c in checks:
        print("%s  %s" % ("PASS" if c else "FAIL", n))
    print("selftest: %d checks, %d failed" % (len(checks), len(bad)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="Backtest of the pre-registered NFL rules (paper research only).")
    ap.add_argument("--data", help="path to games.csv (default: data/raw/games.csv next to this script). "
                                   "It must match the hash in data/raw/MANIFEST.json.")
    ap.add_argument("--no-write", action="store_true", help="print the report and write no result files; the look is still appended to VARIANT_LOG.jsonl")
    ap.add_argument("--selftest", action="store_true", help="run convention and leak checks only")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    try:
        return run(args)
    except Refused as e:
        sys.stderr.write("REFUSED %s\n" % e)
        print("REFUSED %s" % str(e).split(":")[0])
        return 2


if __name__ == "__main__":
    sys.exit(main())
