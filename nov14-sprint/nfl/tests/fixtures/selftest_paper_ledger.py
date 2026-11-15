#!/usr/bin/env python3
"""Self-test for paper_ledger.py. Paper only. Temp directories only.

Run: /usr/bin/python3 -I nov14-sprint/nfl/tests/fixtures/selftest_paper_ledger.py

Every case uses a fresh temp ledger directory and a fixed --now, so nothing
depends on the clock and the real ledger/ directory is never written. The
script fingerprints every file in ledger/ at the start and checks at the end
that nothing was added, removed or changed.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
NFL_DIR = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, NFL_DIR)
import paper_ledger as pl  # noqa: E402

FROZEN = os.path.join(HERE, "frozen_rules.json")
NOW = "2026-11-14T21:30:00Z"          # after the file retrieval, before kickoffs
QUOTE_TS = "2026-11-14T21:20:00Z"
RESULTS = []


def check(name, ok, extra=""):
    RESULTS.append(ok)
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        "" if ok else "   <-- " + str(extra)))


def run(ledger_dir, argv, now=NOW):
    """Run paper_ledger.main in-process. Returns (exit, stdout, stderr)."""
    full = list(argv) + ["--ledger-dir", ledger_dir]
    if now:
        full += ["--now", now]
    so, se = io.StringIO(), io.StringIO()
    code = None
    with contextlib.redirect_stdout(so), contextlib.redirect_stderr(se):
        try:
            code = pl.main(full)
        except SystemExit as exc:
            code = exc.code
    return code, so.getvalue(), se.getvalue()


def rows(ledger_dir, name):
    path = os.path.join(ledger_dir, name)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def add_args(game, action, market, side, line, price, selection=None,
             reason="because", stake=None, rule="MANUAL-T", quote_ts=QUOTE_TS,
             source="TestBook"):
    a = ["add", "--game-id", game, "--rule", rule, "--action", action,
         "--reason", reason, "--market", market, "--side", side,
         "--price", str(price), "--quote-ts", quote_ts, "--source", source]
    if line is not None:
        a += ["--line", str(line)]
    if selection is not None:
        a += ["--selection", selection]
    if stake is not None:
        a += ["--stake", str(stake)]
    return a


def last_rejection_code(ledger_dir):
    r = rows(ledger_dir, "rejections.jsonl")
    return r[-1]["code"] if r else None


def real_fingerprint(real):
    """(name, bytes, sha256) for every file in the real ledger directory."""
    out = []
    if os.path.isdir(real):
        for name in sorted(os.listdir(real)):
            with open(os.path.join(real, name), "rb") as f:
                raw = f.read()
            out.append((name, len(raw), hashlib.sha256(raw).hexdigest()))
    return out


def main():
    real = pl.REAL_LEDGER_DIR
    before = real_fingerprint(real)

    inputs = pl.load_inputs()
    now_dt = pl.parse_ts(NOW)
    games = sorted((g for g in inputs.games
                    if g["kickoff"] and g["kickoff"] > now_dt
                    and g["spread_line"] is not None),
                   key=lambda g: (g["kickoff"], g["game_id"]))
    game = games[0]
    gid = game["game_id"]
    tmp_root = tempfile.mkdtemp(prefix="pl_selftest_")
    try:
        d = os.path.join(tmp_root, "a")

        # --- personal pass and personal take ---------------------------------
        code, so, se = run(d, add_args(gid, "pass", "prop", "over", 54.5,
                                       -115, "Jane Doe receiving yards",
                                       reason="line looks sharp"))
        r = rows(d, "ledger.jsonl")
        ok = (code == 0 and len(r) == 1 and r[0]["action"] == "pass"
              and r[0]["stake_units"] == 0
              and r[0]["reason"] == "line looks sharp"
              and r[0]["price_american"] == -115
              and r[0]["price_in_band"] is True
              and r[0]["price_status"] == "user_reported_quote"
              and r[0]["quote_ts_utc"] == QUOTE_TS
              and r[0]["quote_time_verified"] is False
              and r[0]["line_ts_kind"] == "user_reported_quote"
              and r[0]["contract_key"])
        check("personal pass saved with reason, stake 0, price kept",
              ok, (code, so, se, r))
        code, so, se = run(d, add_args(gid, "take", "total", "over", 44.5,
                                       "+120", reason="weather", stake=1))
        r = rows(d, "ledger.jsonl")
        ok = (code == 0 and len(r) == 2 and r[1]["action"] == "take"
              and r[1]["stake_units"] == 1 and r[1]["price_american"] == 120
              and r[1]["price_in_band"] is True and r[1]["reason"] == "weather")
        check("personal take saved", ok, (code, so, se))
        code, so, se = run(d, add_args(gid, "take", "total", "under", 44.5,
                                       "+180", reason="x"))
        r = rows(d, "ledger.jsonl")
        ok = (code == 0 and r[-1]["price_in_band"] is False)
        check("out-of-band price accepted, price_in_band false", ok, (code, r))
        code, so, se = run(d, add_args(gid, "take", "total", "over", 41.5,
                                       -110, stake=2))
        check("take over the stake cap rejected STAKE_OVER_CAP",
              code == 2 and last_rejection_code(d) == "STAKE_OVER_CAP",
              (code, so, se))
        code, so, se = run(d, add_args(gid, "pass", "total", "over", 41.5,
                                       -110, stake=1))
        check("pass with a stake rejected BAD_STAKE",
              code == 2 and last_rejection_code(d) == "BAD_STAKE", (code, so))
        code, so, se = run(d, add_args(gid, "pass", "total", "over", 41.5,
                                       -110, reason="  "))
        check("empty reason rejected MISSING_REASON",
              code == 2 and last_rejection_code(d) == "MISSING_REASON",
              (code, so))
        a = add_args(gid, "pass", "total", "over", 41.5, -110)
        i = a.index("--action")
        del a[i:i + 2]
        code, so, se = run(d, a)
        check("--action is required (argparse error, exit 2)", code == 2, code)
        code, so, se = run(d, add_args(gid, "take", "total", "over", 41.5,
                                       -110, source=" "))
        check("missing source rejected MISSING_LINE",
              code == 2 and last_rejection_code(d) == "MISSING_LINE",
              (code, so))

        # --- contract identity: line is part of it ---------------------------
        sel = "John Roe passing yards"
        code, so, se = run(d, add_args(gid, "take", "prop", "over", 54.5,
                                       -110, sel))
        ok54 = code == 0
        take54 = rows(d, "ledger.jsonl")[-1] if ok54 else {}
        code, so, se = run(d, add_args(gid, "take", "prop", "over", 60.5,
                                       -110, sel))
        take60 = rows(d, "ledger.jsonl")[-1] if code == 0 else {}
        check("same player and side at 54.5 then 60.5 both accepted",
              ok54 and code == 0 and take54["pick_id"] != take60["pick_id"]
              and take54["contract_key"] != take60["contract_key"],
              (take54, take60))
        n = len(rows(d, "ledger.jsonl"))
        code, so, se = run(d, add_args(gid, "take", "prop", "over", 54.5,
                                       -110, sel))
        check("exact retry of the 54.5 take rejected DUPLICATE_PICK",
              code == 2 and last_rejection_code(d) == "DUPLICATE_PICK"
              and len(rows(d, "ledger.jsonl")) == n, (code, so))
        code, so, se = run(d, add_args(gid, "pass", "prop", "over", "54.50",
                                       "+105", "  john   ROE passing yards ",
                                       reason="changed my mind"))
        check("retry as a pass, other price, spacing, case and 54.50 is "
              "still DUPLICATE_PICK",
              code == 2 and last_rejection_code(d) == "DUPLICATE_PICK"
              and len(rows(d, "ledger.jsonl")) == n, (code, so))

        # --- closing-line rule ------------------------------------------------
        pid54 = take54.get("pick_id", "")
        code, so, se = run(d, ["close", "--pick-id", pid54, "--price", "-125",
                               "--source", "TestBook", "--quote-ts",
                               "2026-11-14T21:25:00Z", "--line", "54.5"])
        obs = rows(d, "observations.jsonl")
        ok = (code == 0 and len(obs) == 1 and obs[0]["pick_id"] == pid54
              and obs[0]["line"] == 54.5 and obs[0]["price_american"] == -125
              and obs[0]["quote_time_verified"] is False)
        check("close on the identical contract accepted", ok, (code, so, se))
        code, so, se = run(d, ["close", "--pick-id", pid54, "--price", "-125",
                               "--source", "TestBook", "--quote-ts",
                               "2026-11-14T21:25:00Z", "--line", "60.5"])
        check("close with a different line rejected CONTRACT_MISMATCH",
              code == 2 and last_rejection_code(d) == "CONTRACT_MISMATCH"
              and len(rows(d, "observations.jsonl")) == 1, (code, so, se))
        code, so, se = run(d, ["close", "--pick-id", "0123456789abcdef",
                               "--price", "-125", "--source", "TestBook",
                               "--quote-ts", "2026-11-14T21:25:00Z"])
        check("close on an unknown pick id rejected UNKNOWN_PICK",
              code == 2 and last_rejection_code(d) == "UNKNOWN_PICK", (code, so))

        # --- exact-close safeguards (Codex retest note, 21:37Z) --------------
        check("a quote from before the pick's decision time is saved as an "
              "other observation, excluded from exact-close comparison",
              obs[0].get("exact_close_eligible") is False
              and obs[0].get("observation_kind") == "other_observation"
              and "quote_before_pick_decision"
              in obs[0].get("exclusion_reasons", []), obs[0])
        n_obs = len(rows(d, "observations.jsonl"))
        code, so, se = run(d, ["close", "--pick-id", pid54, "--price", "-125",
                               "--source", "TestBook", "--quote-ts",
                               "2026-11-14T21:25:00Z"])
        check("close without --line on a pick that has a line rejected "
              "MISSING_LINE",
              code == 2 and last_rejection_code(d) == "MISSING_LINE"
              and len(rows(d, "observations.jsonl")) == n_obs, (code, so, se))
        ko = game["kickoff"]
        code, so, se = run(d, ["close", "--pick-id", pid54, "--price", "-130",
                               "--source", "TestBook", "--quote-ts",
                               pl.fmt_ts(ko - pl.timedelta(minutes=40)),
                               "--line", "54.5"],
                           now=pl.fmt_ts(ko - pl.timedelta(minutes=30)))
        o = rows(d, "observations.jsonl")[-1]
        check("identical contract, quoted after the decision and before "
              "kickoff, is an exact-close candidate",
              code == 0 and o.get("exact_close_eligible") is True
              and o.get("observation_kind") == "exact_close_candidate"
              and o.get("exclusion_reasons") == []
              and o.get("minutes_before_kickoff") == 40.0
              and o.get("line_stated") is True, (code, so, se, o))
        code, so, se = run(d, ["close", "--pick-id", pid54, "--price", "-140",
                               "--source", "TestBook", "--quote-ts",
                               pl.fmt_ts(ko + pl.timedelta(minutes=10)),
                               "--line", "54.5"],
                           now=pl.fmt_ts(ko + pl.timedelta(minutes=20)))
        o = rows(d, "observations.jsonl")[-1]
        check("a quote at or after kickoff is excluded from exact-close "
              "comparison",
              code == 0 and o.get("exact_close_eligible") is False
              and "quote_at_or_after_kickoff"
              in o.get("exclusion_reasons", []), (code, so, se, o))
        code, so, se = run(d, ["status"],
                           now=pl.fmt_ts(ko + pl.timedelta(minutes=20)))
        check("status counts exact-close candidates apart from other "
              "observations",
              code == 0 and "exact-close candidates 1, other 2" in so, so)

        # --- a real price read before kickoff is not a closing line ----------
        n_obs = len(rows(d, "observations.jsonl"))
        early = ["--source", "RealBook via public display", "--quote-ts",
                 pl.fmt_ts(ko - pl.timedelta(minutes=40)), "--not-a-close"]
        code, so, se = run(d, ["close", "--pick-id", pid54, "--price", "-135",
                               "--line", "54.5"] + early,
                           now=pl.fmt_ts(ko - pl.timedelta(minutes=30)))
        o = rows(d, "observations.jsonl")[-1]
        check("close --not-a-close stores a real price observation that is "
              "never an exact-close candidate",
              code == 0 and len(rows(d, "observations.jsonl")) == n_obs + 1
              and o.get("kind") == "price_observation"
              and o.get("observation_kind") == "price_observation_not_a_close"
              and o.get("exact_close_eligible") is False
              and "recorded_as_price_observation_not_a_close"
              in o.get("exclusion_reasons", [])
              and o.get("price_american") == -135
              and "PRICE OBSERVATION RECORDED (not a closing line)" in so,
              (code, so, se, o))
        code, so, se = run(d, ["close", "--pick-id", pid54, "--price", "-135",
                               "--line", "60.5"] + early,
                           now=pl.fmt_ts(ko - pl.timedelta(minutes=30)))
        check("close --not-a-close at a different line is still rejected "
              "CONTRACT_MISMATCH",
              code == 2 and last_rejection_code(d) == "CONTRACT_MISMATCH"
              and len(rows(d, "observations.jsonl")) == n_obs + 1,
              (code, so, se))
        code, so, se = run(d, ["status"],
                           now=pl.fmt_ts(ko + pl.timedelta(minutes=20)))
        check("status counts real price observations apart from "
              "closing-line observations",
              code == 0 and "exact-close candidates 1, other 2" in so
              and "Real price observations before kickoff (not closing "
                  "lines): 1" in so, so)

        # --- legacy rows: no contract_key, old-format pick id ----------------
        d2 = os.path.join(tmp_root, "b")
        os.makedirs(d2)
        lsel = "Legacy Guy rushing yards"
        old_id = hashlib.sha256("|".join([gid, "MANUAL-OLD", "prop", lsel])
                                .encode("utf-8")).hexdigest()[:16]
        legacy = {
            "pick_id": old_id, "mode": "paper", "fixture": False,
            "entered_by": "manual", "game_id": gid, "season": game["season"],
            "week": game["week"], "away_team": game["away_team"],
            "home_team": game["home_team"],
            "kickoff_utc": pl.fmt_ts(game["kickoff"]),
            "rule_version": "MANUAL-OLD", "family": "MANUAL",
            "action": "take", "market": "prop", "side": "over",
            "selection": lsel, "line": 70.5, "price_american": -110,
            "price_field": "manual", "price_in_band": True, "stake_units": 1.0,
            "line_source": "OldBook", "line_source_sha256": None,
            "line_ts_utc": QUOTE_TS, "decision_ts_utc": QUOTE_TS,
            "reason": "manual pick"}
        line_text = json.dumps(legacy) + "\n"
        with open(os.path.join(d2, "ledger.jsonl"), "w") as fh:
            fh.write(line_text)
        code, so, se = run(d2, ["status"])
        check("status reads an old-format row",
              code == 0 and "Takes: 1" in so, (code, so, se))
        code, so, se = run(d2, add_args(gid, "take", "prop", "over", 70.5,
                                        -110, lsel, rule="MANUAL-OLD"))
        check("old-format row still blocks its exact retry (DUPLICATE_PICK)",
              code == 2 and last_rejection_code(d2) == "DUPLICATE_PICK",
              (code, so, se))
        code, so, se = run(d2, add_args(gid, "take", "prop", "over", 71.5,
                                        -110, lsel, rule="MANUAL-OLD"))
        check("old-format row allows the same player and side at a "
              "different line", code == 0, (code, so, se))
        with open(os.path.join(d2, "ledger.jsonl")) as fh:
            first = fh.readline()
        check("old-format row is never rewritten", first == line_text,
              first)
        code, so, se = run(d2, ["close", "--pick-id", old_id, "--price",
                                "-120", "--source", "OldBook", "--quote-ts",
                                QUOTE_TS, "--line", "70.5"])
        check("close works on an old-format row", code == 0, (code, so, se))
        late = pl.fmt_ts(game["kickoff"].replace(tzinfo=pl.timezone.utc)
                         + pl.timedelta(hours=5))
        code, so, se = run(d2, ["settle-manual", "--pick-id", old_id,
                                "--outcome", "win", "--result-source",
                                "box score"], now=late)
        s = rows(d2, "settlements.jsonl")
        check("settle-manual settles an old-format row",
              code == 0 and len(s) == 1 and s[0]["pick_id"] == old_id,
              (code, so, se))
        code, so, se = run(d2, ["status"], now=late)
        check("status still reads after settling an old-format row",
              code == 0 and "Settled takes W-L-P: 1-0-0" in so, (code, so))

        # --- generated rows carry the archived labels ------------------------
        d3 = os.path.join(tmp_root, "c")
        code, so, se = run(d3, ["generate", "--frozen-file", FROZEN])
        r = rows(d3, "ledger.jsonl")
        labels_ok = bool(r) and all(
            x["price_status"] == "archived_observation"
            and x["quote_ts_utc"] is None
            and x["quote_time_verified"] is False
            and x["executable_price"] is False
            and x["file_retrieved_ts_utc"] == inputs.retrieved_str
            and x["line_ts_utc"] == inputs.retrieved_str
            and x["line_ts_kind"] == "file_retrieval"
            and x["contract_key"] for x in r)
        check("generated rows carry archived labels, quote_ts_utc null",
              code == 0 and labels_ok, (code, so[-400:], se))
        check("generate prints the archived-price line",
              "Prices are archived paper observations. File retrieved %s. "
              "Sportsbook quote time unknown. Not a live or executable price."
              % inputs.retrieved_str in so, so[:600])
        n = len(r)
        code, so, se = run(d3, ["generate", "--frozen-file", FROZEN])
        check("second generate adds nothing", len(rows(d3, "ledger.jsonl")) == n
              and "Ledger lines added this run: 0" in so, so[-300:])
        for cmd in (["slate"], ["status"]):
            code, so, se = run(d3, cmd)
            check("%s prints the archived-price line" % cmd[0],
                  code == 0 and "Prices are archived paper observations. "
                  "File retrieved %s. Sportsbook quote time unknown. Not a "
                  "live or executable price." % inputs.retrieved_str in so,
                  (code, so[:300], se))

        # --- the 12-hour gate on a generated row is a FILE-age check ----------
        d4 = os.path.join(tmp_root, "d")
        code, so, se = run(d4, ["generate", "--frozen-file", FROZEN],
                           now="2026-11-15T10:00:00Z")
        rej = rows(d4, "rejections.jsonl")
        stale = [x for x in rej if x["code"] == "STALE_LINE"]
        check("stale file gives STALE_LINE whose text says FILE only and "
              "not proof of a fresh quote",
              bool(stale) and "FILE only" in stale[0]["detail"]
              and "not proof" in stale[0]["detail"], (code, so[-300:]))

        # --- manual quote time over 12 hours old ------------------------------
        code, so, se = run(os.path.join(tmp_root, "e"),
                           add_args(gid, "take", "total", "over", 44.5, -110,
                                    quote_ts="2026-11-14T08:00:00Z"))
        check("manual quote time older than 12 hours rejected STALE_LINE",
              code == 2, (code, so))

        # --- spread sign conventions (codex/NFL_Spread_Sign_Defect.md) --------
        # A personal spread is the handicap on the side picked (ticket
        # convention). A rule row keeps the archive's line (positive = HOME
        # favored). Each row must be graded in its own convention.
        def ge(entry, hs, as_):
            return pl.grade_entry(entry, hs, as_)

        tick = {"market": "spread", "entered_by": "manual",
                "line_convention": pl.CONV_TICKET}
        arch = {"market": "spread", "entered_by": "rule",
                "line_convention": pl.CONV_NFLVERSE}
        check("unit: ticket home -2.5, home wins 21-20 -> loss",
              ge(dict(tick, side="home", line=-2.5), 21, 20)[0] == "loss")
        check("unit: ticket home -3, home wins 23-20 -> push",
              ge(dict(tick, side="home", line=-3), 23, 20)[0] == "push")
        check("unit: archive line +2.5 (home favored), home side, 21-20 "
              "-> loss; archive line -2.5 (home is the dog) -> win",
              ge(dict(arch, side="home", line=2.5), 21, 20)[0] == "loss"
              and ge(dict(arch, side="home", line=-2.5), 21, 20)[0] == "win")
        older_p = ge({"market": "spread", "entered_by": "manual",
                      "side": "home", "line": -2.5}, 21, 20)
        older_r = ge({"market": "spread", "entered_by": "rule",
                      "side": "home", "line": -2.5}, 21, 20)
        check("unit: older rows with no line_convention are handled "
              "explicitly (personal = ticket, rule = archive)",
              older_p == ("loss", pl.CONV_TICKET,
                          "assumed_older_personal_row")
              and older_r == ("win", pl.CONV_NFLVERSE,
                              "assumed_older_rule_row"), (older_p, older_r))
        try:
            ge({"market": "spread", "entered_by": "manual", "side": "home",
                "line": -2.5, "line_convention": "bogus"}, 21, 20)
            raised = False
        except ValueError:
            raised = True
        check("unit: unknown line_convention raises instead of guessing",
              raised)

        d5 = os.path.join(tmp_root, "sign")
        g5 = games[:5]
        # (game, side, ticket handicap, home final, away final, want, pnl)
        cases = [
            (g5[0], "home", -2.5, 21, 20, "loss", -1.0),   # wins by less
            (g5[0], "away", 2.5, 21, 20, "win", 0.909091),  # other side
            (g5[1], "home", -3, 23, 20, "push", 0.0),       # push
            (g5[2], "away", -3.5, 20, 27, "win", 0.909091),  # away favorite
            (g5[2], "home", 3.5, 20, 27, "loss", -1.0),
            (g5[3], "away", 6.5, 24, 20, "win", 0.909091),  # away underdog
            (g5[4], "away", 3.5, 27, 20, "loss", -1.0),     # dog, not enough
        ]
        ok_add = True
        for g, side, hcap, hs, as_, want, pnl in cases:
            code, so, se = run(d5, add_args(g["game_id"], "take", "spread",
                                            side, hcap, -110))
            ok_add = ok_add and code == 0 and "ticket handicap" in so
        man = [x for x in rows(d5, "ledger.jsonl")]
        check("personal spreads are saved as typed with line_convention "
              "ticket_handicap and the add output says what the ticket means",
              ok_add and len(man) == len(cases)
              and all(x["line_convention"] == pl.CONV_TICKET for x in man)
              and [x["line"] for x in man] == [c[2] for c in cases],
              [(x["side"], x["line"], x.get("line_convention")) for x in man])
        code, so, se = run(d5, add_args(g5[0]["game_id"], "take", "spread",
                                        "home", -2.5, -110))
        check("exact retry of a personal spread is still DUPLICATE_PICK",
              code == 2 and last_rejection_code(d5) == "DUPLICATE_PICK",
              (code, so))
        code, so, se = run(d5, ["generate", "--frozen-file", FROZEN])
        gen = [x for x in rows(d5, "ledger.jsonl")
               if x["entered_by"] == "rule" and x["market"] == "spread"]
        check("generated spread rows state the archive convention and keep "
              "the archive's line unchanged",
              code == 0 and bool(gen)
              and all(x["line_convention"] == pl.CONV_NFLVERSE
                      and x["line"] == inputs.by_id[x["game_id"]]
                      ["spread_line"] for x in gen), (code, so[-300:]))
        finals = {}
        for g, side, hcap, hs, as_, want, pnl in cases:
            finals[g["game_id"]] = (g, hs, as_)
        res_path = os.path.join(tmp_root, "sign_results.csv")
        with open(res_path, "w") as fh:
            fh.write("game_id,home_team,away_team,home_score,away_score\n")
            for g, hs, as_ in finals.values():
                fh.write("%s,%s,%s,%d,%d\n" % (g["game_id"], g["home_team"],
                                               g["away_team"], hs, as_))
        last_ko = max(g["kickoff"] for g in g5)
        res_ts = pl.fmt_ts(last_ko.replace(tzinfo=pl.timezone.utc)
                           + pl.timedelta(hours=4))
        late5 = pl.fmt_ts(last_ko.replace(tzinfo=pl.timezone.utc)
                          + pl.timedelta(hours=5))
        settle_argv = ["settle", "--results-file", res_path,
                       "--results-ts", res_ts]
        code, so, se = run(d5, settle_argv, now=late5)
        led = dict((x["pick_id"], x) for x in rows(d5, "ledger.jsonl"))
        sett = dict((x["pick_id"], x) for x in rows(d5, "settlements.jsonl"))
        got = []
        for g, side, hcap, hs, as_, want, pnl in cases:
            pid = [p for p, x in led.items()
                   if x["entered_by"] == "manual"
                   and x["game_id"] == g["game_id"] and x["side"] == side
                   and x["line"] == hcap][0]
            srow = sett.get(pid, {})
            got.append((side, hcap, hs, as_, srow.get("outcome"),
                        srow.get("pnl_units"), srow.get("line_convention")))
        names = ["home -2.5 wins 21-20 -> LOSS -1 (the reported defect)",
                 "away +2.5 loses 20-21 -> WIN",
                 "home -3 wins 23-20 -> PUSH 0",
                 "away favorite -3.5 wins 27-20 -> WIN",
                 "home +3.5 loses 20-27 -> LOSS",
                 "away underdog +6.5 loses 20-24 -> WIN",
                 "away underdog +3.5 loses 20-27 -> LOSS"]
        for name, c, gt in zip(names, cases, got):
            check("settle personal spread: " + name,
                  code == 0 and gt[4] == c[5]
                  and gt[5] is not None and abs(gt[5] - c[6]) < 1e-6
                  and gt[6] == pl.CONV_TICKET, (code, gt, so[-300:]))
        ctrl = []
        for pid, x in led.items():
            if x["entered_by"] != "rule" or x["market"] != "spread" \
                    or x["side"] is None or pid not in sett:
                continue
            g, hs, as_ = finals[x["game_id"]]
            want = pl.rules.grade("spread", x["side"], x["line"], hs, as_)
            srow = sett[pid]
            seen_out = srow["outcome"] if x["action"] == "take" \
                else srow["shadow_outcome"]
            ctrl.append(seen_out == want
                        and srow["line_convention"] == pl.CONV_NFLVERSE
                        and srow["line_convention_basis"] == "stated")
        check("generated-rule control: %d rule spread rows settle exactly "
              "as rules.grade does in the archive convention" % len(ctrl),
              len(ctrl) >= 5 and all(ctrl), ctrl)

        # older rows: same picks with the line_convention field removed, as
        # in ledgers written before this fix (the real ledger's rule rows)
        d6 = os.path.join(tmp_root, "sign_old")
        os.makedirs(d6)
        with open(os.path.join(d6, "ledger.jsonl"), "w") as fh:
            for x in rows(d5, "ledger.jsonl"):
                x.pop("line_convention", None)
                fh.write(json.dumps(x) + "\n")
        code, so, se = run(d6, settle_argv, now=late5)
        sett6 = dict((x["pick_id"], x) for x in rows(d6, "settlements.jsonl"))
        same = (set(sett6) == set(sett) and all(
            sett6[p]["outcome"] == sett[p]["outcome"]
            and sett6[p]["shadow_outcome"] == sett[p]["shadow_outcome"]
            and sett6[p]["pnl_units"] == sett[p]["pnl_units"] for p in sett))
        bases = set(x["line_convention_basis"] for x in sett6.values()
                    if x["market"] == "spread")
        check("older rows with no line_convention settle to the same "
              "outcomes, flagged as assumed, with a NOTE line",
              code == 0 and same and bases == {
                  "assumed_older_personal_row", "assumed_older_rule_row"}
              and "has no line_convention (older row)" in so,
              (code, same, bases))

        d7 = os.path.join(tmp_root, "sign_bad")
        os.makedirs(d7)
        with open(os.path.join(d7, "ledger.jsonl"), "w") as fh:
            x = [y for y in rows(d5, "ledger.jsonl")
                 if y["entered_by"] == "manual"][0]
            x["line_convention"] = "bogus"
            fh.write(json.dumps(x) + "\n")
        code, so, se = run(d7, settle_argv, now=late5)
        check("a row with an unknown line_convention is refused UNGRADEABLE "
              "and not settled",
              "REFUSED   UNGRADEABLE" in so
              and not rows(d7, "settlements.jsonl")
              and last_rejection_code(d7) == "UNGRADEABLE", (code, so[-300:]))

        # --- real finals carry their source into the settlement rows ---------
        d8 = os.path.join(tmp_root, "sign_prov")
        os.makedirs(d8)
        shutil.copy(os.path.join(d5, "ledger.jsonl"),
                    os.path.join(d8, "ledger.jsonl"))
        prov_path = os.path.join(tmp_root, "prov_results.csv")
        first_gid = sorted(finals)[0]
        with open(prov_path, "w") as fh:
            fh.write("game_id,home_team,away_team,home_score,away_score,"
                     "source,source_url,retrieved_at_utc\n")
            for g, hs, as_ in finals.values():
                fh.write("%s,%s,%s,%d,%d,Test Scores,"
                         "https://example.invalid/scores,%s\n"
                         % (g["game_id"], g["home_team"], g["away_team"],
                            hs, as_, "yesterday"
                            if g["game_id"] == first_gid else res_ts))
        code, so, se = run(d8, ["settle", "--results-file", prov_path,
                                "--results-ts", res_ts], now=late5)
        sett8 = rows(d8, "settlements.jsonl")
        prov_ok = [x for x in sett8
                   if led[x["pick_id"]]["game_id"] != first_gid]
        prov_bad = [x for x in sett8
                    if led[x["pick_id"]]["game_id"] == first_gid]
        check("settle copies each final's source, URL and retrieval time "
              "onto the settlement row",
              code == 0 and len(sett8) == len(sett) and bool(prov_ok)
              and all(x.get("result_source") == "Test Scores"
                      and x.get("result_source_url")
                      == "https://example.invalid/scores"
                      and x.get("result_retrieved_at_utc") == res_ts
                      for x in prov_ok), (code, so[-300:], prov_ok[:1]))
        check("a retrieval time that is not a timestamp is dropped, and a "
              "results file with no source columns adds none",
              bool(prov_bad)
              and all("result_retrieved_at_utc" not in x
                      and x.get("result_source") == "Test Scores"
                      for x in prov_bad)
              and all("result_source" not in x
                      and "result_source_url" not in x
                      for x in sett.values()), (prov_bad[:1],))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    after = real_fingerprint(real)
    check("real ledger dir is unchanged by the self-test (%d files)"
          % len(before), after == before, (before, after))
    total, bad = len(RESULTS), RESULTS.count(False)
    print("SELFTEST: %d checks, %d failed" % (total, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
