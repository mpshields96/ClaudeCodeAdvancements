#!/usr/bin/env python3
"""Self-test for real_intake.py. PAPER ONLY.

Everything here runs in temporary folders. The real ledger and the real
output folder are fingerprinted before and after and must not change.

The prices come from the archived real price capture in real/inputs/. The
after-the-game scores are INVENTED FIXTURES, used only to exercise the
scoring path that real finals will take. They never reach the real ledger.

Run:
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B \
      tests/fixtures/selftest_real_intake.py
"""
import contextlib
import copy
import csv
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, HERE)

import paper_ledger as pl  # noqa: E402
import real_intake as ri  # noqa: E402

REAL_LEDGER = pl.REAL_LEDGER_DIR
REAL_OUT = os.path.join(HERE, "real")
IN_SB = os.path.join(REAL_OUT, "inputs",
                     "nfl-scoreboard.20261114T225142Z.json")
IN_LN = os.path.join(REAL_OUT, "inputs",
                     "nfl-public-lines.20261114T225342Z.json")
PRE_NOW = "2026-11-15T05:00:00Z"        # after the capture, before kickoffs
POST_CAPTURE = "2026-11-17T06:00:00Z"   # after the last week 10 game
POST_NOW = "2026-11-17T07:00:00Z"
FIXTURE_SOURCE = "FIXTURE scores for the self-test, invented, not real"
RESULTS = []


def check(name, ok, extra=""):
    RESULTS.append(bool(ok))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name,
                        "" if ok else "   <-- " + str(extra)[:400]))


def fingerprint(root):
    out = []
    for base, _dirs, files in sorted(os.walk(root)):
        for name in sorted(files):
            p = os.path.join(base, name)
            with open(p, "rb") as f:
                raw = f.read()
            out.append((os.path.relpath(p, root), len(raw),
                        hashlib.sha256(raw).hexdigest()))
    return out


def jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


class Box(object):
    """One scratch ledger plus numbered scratch input and output folders."""

    def __init__(self, tmp, name):
        self.root = os.path.join(tmp, name)
        self.ledger = os.path.join(self.root, "ledger")
        os.makedirs(self.ledger)
        shutil.copyfile(os.path.join(REAL_LEDGER, "ledger.jsonl"),
                        os.path.join(self.ledger, "ledger.jsonl"))
        self.n = 0

    def run(self, sb, ln, now, apply=False, ledger_dir=None, out_dir=None):
        self.n += 1
        data = os.path.join(self.root, "in%d" % self.n)
        out = out_dir or os.path.join(self.root, "out%d" % self.n)
        os.makedirs(data)
        sb_path = os.path.join(data, "scoreboard.json")
        ln_path = os.path.join(data, "lines.json")
        with open(sb_path, "w", encoding="utf-8") as f:
            json.dump(sb, f)
        with open(ln_path, "w", encoding="utf-8") as f:
            json.dump(ln, f)
        argv = ["--scoreboard", sb_path, "--lines", ln_path,
                "--out-dir", out, "--ledger-dir", ledger_dir or self.ledger]
        if now:
            argv += ["--now", now]
        if apply:
            argv.append("--apply")
        so, se = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(so), contextlib.redirect_stderr(se):
            try:
                code = ri.main(argv)
            except SystemExit as exc:
                code = exc.code
        res = {"code": code, "out": so.getvalue(), "err": se.getvalue(),
               "dir": out, "receipt": {}, "scores": []}
        rp = os.path.join(out, "INTAKE_RECEIPT.json")
        if os.path.exists(rp):
            with open(rp, "r", encoding="utf-8") as f:
                res["receipt"] = json.load(f)
        sp = os.path.join(out, "week10_rule_scores.csv")
        if os.path.exists(sp):
            with open(sp, "r", encoding="utf-8", newline="") as f:
                res["scores"] = list(csv.DictReader(f))
        return res


def by_status(res):
    return res["receipt"].get("counts", {}).get("rule_rows_by_status", {})


def teams(g):
    home = [t for t in g["teams"] if t["home"]][0]
    away = [t for t in g["teams"] if not t["home"]][0]
    return home, away


def post_scoreboard(base, status="ScoresOfficial"):
    """Every game finished, with invented scores. The one real final stays."""
    sb = copy.deepcopy(base)
    sb["source"] = FIXTURE_SOURCE
    sb["captured_at"] = POST_CAPTURE
    for i, g in enumerate(sb["games"]):
        if g["status"] == "ScoresOfficial":
            continue
        home, away = teams(g)
        g["status"] = status
        home["score"] = 17 + (i * 7) % 15
        away["score"] = 13 + (i * 5) % 17
        if home["team"] == "ATL":      # ATL +3 loses by exactly 3: a push
            home["score"], away["score"] = 20, 23
    return sb


def line_game(ln, home_full_name):
    return [g for g in ln["games"]
            if g["teams"]["home"] == home_full_name][0]


def expected(market, side, line, hs, as_):
    """Independent grading. Spread line: home favored when positive."""
    d = (hs + as_ - line) if market == "total" else (hs - as_ - line)
    if d == 0:
        return "push"
    if market == "total":
        return "win" if (d < 0) == (side == "under") else "loss"
    return "win" if (d > 0) == (side == "home") else "loss"


def expected_pnl(outcome, price):
    if outcome == "push":
        return 0.0
    if outcome == "loss":
        return -1.0
    return price / 100.0 if price > 0 else 100.0 / -price


def main():
    print(pl.BANNER)
    for p in (IN_SB, IN_LN):
        if not os.path.exists(p):
            print("FAIL  archived input is missing: %s" % p)
            return 1
    with open(IN_SB, "r", encoding="utf-8") as f:
        base_sb = json.load(f)
    with open(IN_LN, "r", encoding="utf-8") as f:
        base_ln = json.load(f)
    real_before = (fingerprint(REAL_LEDGER), fingerprint(REAL_OUT))
    tmp = tempfile.mkdtemp(prefix="real_intake_selftest_")
    try:
        # ---- the test clock is refused anywhere near the real folders
        a = Box(tmp, "a")
        r = a.run(base_sb, base_ln, PRE_NOW, apply=True,
                  ledger_dir=REAL_LEDGER)
        check("--now with the real ledger is refused before any write",
              r["code"] == 2 and "NOW_OVERRIDE_NOT_ALLOWED" in r["err"]
              and not os.path.exists(r["dir"]), (r["code"], r["err"]))
        r = a.run(base_sb, base_ln, PRE_NOW, apply=True, out_dir=REAL_OUT)
        check("--now with the real output folder is refused",
              r["code"] == 2 and "NOW_OVERRIDE_NOT_ALLOWED" in r["err"]
              and not os.path.exists(os.path.join(a.ledger,
                                                  "observations.jsonl")),
              (r["code"], r["err"]))

        # ---- before kickoff: dry run, then apply, then the same again
        ledger_bytes = open(os.path.join(a.ledger, "ledger.jsonl"),
                            "rb").read()
        r = a.run(base_sb, base_ln, PRE_NOW)
        st = by_status(r)
        check("dry run before kickoff: 44 rows await a final, 4 have no "
              "price, 8 have no side, none scored",
              r["code"] == 0 and st.get(ri.AWAITING) == 44
              and st.get(ri.NO_PRICE) == 4 and st.get(ri.NO_SIDE) == 8
              and ri.SCORED not in st and len(r["scores"]) == 56, st)
        check("a dry run writes nothing to the ledger folder",
              sorted(os.listdir(a.ledger)) == ["ledger.jsonl"],
              os.listdir(a.ledger))
        was = [x for x in r["scores"] if x["game_id"] == "2026_10_WAS_NYG"]
        check("the one real final has no price, so its four rule rows say "
              "'no price, not scored' and carry no outcome",
              len(was) == 4 and all(
                  x["score_status"] == ri.NO_PRICE and not x["outcome"]
                  and not x["pnl_units"] and not x["real_price_american"]
                  for x in was), was)
        check("every priced row carries the book, the price time and an "
              "https source URL",
              all(x["book"] and x["price_observed_utc"]
                  and x["price_source_url"].startswith("https://")
                  for x in r["scores"] if x["real_price_american"]))
        r = a.run(base_sb, base_ln, PRE_NOW, apply=True)
        obs = jsonl(os.path.join(a.ledger, "observations.jsonl"))
        po = r["receipt"].get("applied_to_ledger", {})
        check("apply before kickoff records 44 real prices, none of them a "
              "closing line",
              r["code"] == 0 and len(obs) == 44 and all(
                  o.get("observation_kind") == "price_observation_not_a_close"
                  and o.get("exact_close_eligible") is False for o in obs)
              and po.get("price_observations", {}).get("recorded") == 44,
              (r["code"], len(obs), po, r["err"]))
        check("the one final with no price is held back from settle and "
              "nothing is settled",
              "held back" in po.get("settle", "")
              and "2026_10_WAS_NYG" in po.get("settle", "")
              and not jsonl(os.path.join(a.ledger, "settlements.jsonl")),
              po.get("settle"))
        check("apply never rewrites ledger.jsonl",
              open(os.path.join(a.ledger, "ledger.jsonl"),
                   "rb").read() == ledger_bytes)
        r = a.run(base_sb, base_ln, PRE_NOW, apply=True)
        po = r["receipt"].get("applied_to_ledger", {}).get(
            "price_observations", {})
        check("a second apply records nothing new",
              r["code"] == 0 and po.get("recorded") == 0
              and po.get("already_recorded") == 44 and len(jsonl(
                  os.path.join(a.ledger, "observations.jsonl"))) == 44, po)

        # ---- after the games: fixture finals, original real price capture
        post = post_scoreboard(base_sb)
        finals = {}
        for g in post["games"]:
            home, away = teams(g)
            finals[(ri.ABBR_FIX.get(away["team"], away["team"]),
                    ri.ABBR_FIX.get(home["team"], home["team"]))] = (
                        home["score"], away["score"])
        r = a.run(post, base_ln, POST_NOW, apply=True)
        st = by_status(r)
        check("after the games: the 44 priced rows are scored, the 4 "
              "unpriced rows still are not",
              r["code"] == 0 and st.get(ri.SCORED) == 44
              and st.get(ri.NO_PRICE) == 4 and st.get(ri.NO_SIDE) == 8
              and ri.AWAITING not in st, (r["code"], st, r["err"]))
        bad, seen = [], set()
        for x in r["scores"]:
            if x["score_status"] != ri.SCORED:
                if x["outcome"] or x["pnl_units"] or x["shadow_outcome"]:
                    bad.append(("unscored row has an outcome", x))
                continue
            hs, as_ = finals[(x["away_team"], x["home_team"])]
            want = expected(x["market"], x["side"], float(x["real_line"]),
                            hs, as_)
            pnl = expected_pnl(want, float(x["real_price_american"]))
            seen.add(want)
            if x["action"] == "take":
                got = (x["outcome"], float(x["pnl_units"]))
            else:
                got = (x["shadow_outcome"], float(x["shadow_pnl_units"]))
                if x["outcome"] != "pass" or float(x["pnl_units"]) != 0.0:
                    bad.append(("a pass must score 0", x))
            if got[0] != want or abs(got[1] - pnl) > 0.0001:
                bad.append((want, pnl, x))
        check("every scored row matches an independent grade and the P&L "
              "at the real price (wins, losses and a push all occur)",
              not bad and seen == {"win", "loss", "push"}, (seen, bad[:2]))
        sett = jsonl(os.path.join(a.ledger, "settlements.jsonl"))
        entries = dict((e["pick_id"], e) for e in jsonl(
            os.path.join(a.ledger, "ledger.jsonl")))
        csv_by_pick = dict((x["ledger_pick_id"], x) for x in r["scores"]
                           if x["ledger_pick_id"])
        takes = [s for s in sett if s.get("action") == "take"]
        check("the ledger settles 11 takes and 33 passes, one row each",
              len(sett) == 44 and len(takes) == 11
              and len(set(s["pick_id"] for s in sett)) == 44,
              (len(sett), len(takes)))
        bad = []
        for s in sett:
            x = csv_by_pick.get(s["pick_id"])
            if x is None or x["score_status"] != ri.SCORED:
                bad.append(("settled a row the source did not score", s))
                continue
            stake = float(entries[s["pick_id"]].get("stake_units") or 1.0)
            if s["action"] == "take":
                same = (s["outcome"] == x["outcome"] and abs(
                    float(s["pnl_units"])
                    - stake * float(x["pnl_units"])) < 0.001)
            else:
                same = (s["outcome"] == "pass"
                        and float(s["pnl_units"]) == 0.0
                        and s["shadow_outcome"] == x["shadow_outcome"]
                        and abs(float(s["shadow_pnl_units"])
                                - float(x["shadow_pnl_units"])) < 0.001)
            if not same:
                bad.append((s, x))
        check("each ledger settlement equals the row scored at the real "
              "price", not bad, bad[:1])
        check("each settlement row carries the result source, its URL and "
              "its retrieval time",
              sett and all(
                  s.get("result_source") == FIXTURE_SOURCE
                  and s.get("result_source_url") == base_sb["source_page"]
                  and s.get("result_retrieved_at_utc") == POST_CAPTURE
                  for s in sett), sett[:1])
        check("no settlement exists for the game with no real price",
              not [s for s in sett if s["game_id"] == "2026_10_WAS_NYG"]
              and "2026_10_WAS_NYG" in r["receipt"].get(
                  "applied_to_ledger", {}).get("settle", ""))
        r = a.run(post, base_ln, POST_NOW, apply=True)
        check("running the same finals again settles nothing twice",
              len(jsonl(os.path.join(a.ledger,
                                     "settlements.jsonl"))) == 44,
              (r["code"], r["err"]))

        # ---- a finished game with no price is never scored or settled
        b = Box(tmp, "b")
        ln = copy.deepcopy(base_ln)
        line_game(ln, "Detroit Lions")["book_references"] = []
        b.run(base_sb, ln, PRE_NOW, apply=True)
        r = b.run(post, ln, POST_NOW, apply=True)
        det = [x for x in r["scores"] if x["game_id"] == "2026_10_NE_DET"]
        sett = jsonl(os.path.join(b.ledger, "settlements.jsonl"))
        check("a finished game with no price stays 'no price, not scored' "
              "and the ledger does not settle it",
              len(det) == 4 and all(
                  x["score_status"] == ri.NO_PRICE and not x["outcome"]
                  and not x["shadow_outcome"] for x in det)
              and sett and not [s for s in sett
                                if s["game_id"] == "2026_10_NE_DET"]
              and "2026_10_NE_DET" in r["receipt"].get(
                  "applied_to_ledger", {}).get("settle", ""),
              (det[:1], len(sett)))

        # ---- a real line that differs from the ledger pick
        c = Box(tmp, "c")
        ln = copy.deepcopy(base_ln)
        for bk in line_game(ln, "Green Bay Packers")["book_references"]:
            for m in bk["markets"]:
                if m["market"] == "pointSpread":
                    m["line"] = "+3.5" if m["side"] == "away" else "-3.5"
        r = c.run(base_sb, ln, PRE_NOW, apply=True)
        gb = [x for x in r["scores"] if x["game_id"] == "2026_10_MIN_GB"
              and x["market"] == "spread" and x["side"]]
        gb_picks = set(x["ledger_pick_id"] for x in gb)
        po = r["receipt"].get("applied_to_ledger", {}).get(
            "price_observations", {})
        obs = jsonl(os.path.join(c.ledger, "observations.jsonl"))
        check("a price on a different line is not recorded against the "
              "ledger pick",
              gb and all(x["ledger_agrees"].startswith("NO") for x in gb)
              and po.get("line_differs_not_recorded") == len(gb)
              and not [o for o in obs if o["pick_id"] in gb_picks],
              (po, [x["ledger_agrees"] for x in gb]))
        r = c.run(post, ln, POST_NOW, apply=True)
        sett = jsonl(os.path.join(c.ledger, "settlements.jsonl"))
        check("a game whose real line differs from the ledger is held back "
              "from settle",
              sett and not [s for s in sett
                            if s["game_id"] == "2026_10_MIN_GB"]
              and "2026_10_MIN_GB" in r["receipt"].get(
                  "applied_to_ledger", {}).get("settle", ""),
              r["receipt"].get("applied_to_ledger"))

        # ---- handicaps that do not mirror each other give no spread price
        d = Box(tmp, "d")
        ln = copy.deepcopy(base_ln)
        for bk in line_game(ln, "Dallas Cowboys")["book_references"]:
            for m in bk["markets"]:
                if m["market"] == "pointSpread" and m["side"] == "home":
                    m["line"] = "+4.5"
        r = d.run(base_sb, ln, PRE_NOW)
        dal = [x for x in r["scores"] if x["game_id"] == "2026_10_SF_DAL"]
        check("mismatched away and home handicaps give no spread price, "
              "while the total is still priced",
              len(dal) == 4 and all(
                  x["score_status"] == ri.NO_PRICE
                  and not x["real_price_american"]
                  for x in dal if x["market"] == "spread")
              and [x for x in dal if x["market"] == "total"
                   and x["score_status"] == ri.AWAITING],
              [(x["rule_version"], x["score_status"]) for x in dal])

        # ---- what counts as a final
        r = d.run(post_scoreboard(base_sb, status="InProgress"), base_ln,
                  POST_NOW)
        st = by_status(r)
        check("scores without the official final status are not finals",
              r["code"] == 0 and ri.SCORED not in st
              and st.get(ri.AWAITING) == 44
              and r["receipt"]["counts"]["finals"] == 1, st)
        sb = copy.deepcopy(post)
        for g in sb["games"]:
            home, away = teams(g)
            if home["team"] == "NYG":
                home["score"] = 28
        r = d.run(sb, base_ln, POST_NOW)
        check("when the two sources disagree on a final it is not used",
              r["code"] == 0 and r["receipt"]["counts"]["finals"] == 13
              and any("disagree" in n for n in r["receipt"].get("notes", [])),
              (r["code"], r["receipt"].get("counts"),
               r["receipt"].get("notes")))
        sb = copy.deepcopy(base_sb)
        for g in sb["games"]:
            if g["status"] != "ScoresOfficial":
                home, away = teams(g)
                g["status"] = "ScoresOfficial"
                home["score"], away["score"] = 24, 20
        r = d.run(sb, base_ln, PRE_NOW)
        check("a 'final' captured before kickoff is not a final",
              r["code"] == 0 and ri.SCORED not in by_status(r)
              and r["receipt"]["counts"]["finals"] == 1, by_status(r))

        # ---- malformed or impossible captures are refused
        sb = copy.deepcopy(base_sb)
        del sb["captured_at"]
        r = d.run(sb, base_ln, PRE_NOW)
        check("a scoreboard with no capture time is refused",
              r["code"] == 2 and "INTAKE_INVALID" in r["err"], r["err"])
        r = d.run(post, base_ln, PRE_NOW)
        check("a scoreboard captured in the future is refused",
              r["code"] == 2 and "future" in r["err"], r["err"])
        sb = copy.deepcopy(base_sb)
        sb["source_page"] = "http://example.invalid/not-https"
        r = d.run(sb, base_ln, PRE_NOW)
        check("a scoreboard without an https source page is refused",
              r["code"] == 2 and "INTAKE_INVALID" in r["err"], r["err"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("the real ledger and the real output folder are untouched",
          (fingerprint(REAL_LEDGER), fingerprint(REAL_OUT)) == real_before)
    failed = RESULTS.count(False)
    print("SELFTEST real_intake: %d checks, %d failed"
          % (len(RESULTS), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
