"""Unit tests for weekly/weekly_api.py (API id weekly/1).

Run: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I weekly/test_weekly_api.py   (from nov14-sprint/nfl/slate)

Standard library only, Python 3.9. No network. The real 2026-11-22 inputs are copied into a temp folder for every
test; nothing is written to weekly/reviews/ or weekly/published/. The server clock is pinned to
2026-11-15T08:00:00Z (after the real capture, well before every kickoff) unless a test moves it.
"""
import ast
import contextlib
import copy
import hashlib
import io
import json
import math
import re
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
SLATE = HERE.parent
sys.path.append(str(HERE))      # -I drops the script folder from sys.path; append so the stdlib always wins
sys.path.append(str(SLATE))

import weekly_api as W  # noqa: E402

try:
    import selection_markets as SM  # the engine's own key and label functions (read-only reference)
except Exception:  # pragma: no cover - the parity tests skip when the engine module cannot be imported
    SM = None

DAY = "2026-11-22"
REAL_DAY_DIR = SLATE / "weekly_inputs" / DAY
UTC = timezone.utc
NOW0 = datetime(2026, 11, 15, 8, 0, 0, tzinfo=UTC)
REAL_REVIEWS = HERE / "reviews"
REAL_PUBLISHED = HERE / "published"
_BEFORE = {}

BRIEF = SLATE / "pdf_export" / "brief.py"


def load_brief():
    """brief.py's own validators, extracted from the source (pypdf and reportlab are not installed here)."""
    try:
        tree = ast.parse(BRIEF.read_text())
    except (OSError, SyntaxError):
        return None
    funcs = {"require", "digest", "load", "stamp", "validprice", "dec", "nonempty", "identity", "url_ok",
             "validate_card", "initial_quote", "check_capture"}
    assigns = {"CT", "NAMES"}
    body = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in funcs:
            body.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in assigns for t in n.targets):
            body.append(n)
    try:
        from zoneinfo import ZoneInfo
        ns = dict(hashlib=hashlib, json=json, math=math, re=re, date=date, datetime=datetime, timedelta=timedelta,
                  timezone=timezone, Path=Path, urlsplit=urlsplit, ZoneInfo=ZoneInfo)
        exec(compile(ast.Module(body=body, type_ignores=[]), str(BRIEF), "exec"), ns)
        for name in ("validate_card", "initial_quote", "check_capture"):
            if name not in ns:
                return None
        return ns
    except Exception:
        return None


REAL_ANNOTATIONS = HERE / "annotations"
FROZEN_NOV15 = [SLATE / "slate_20261115.json", SLATE / "frozen_picker.json"]   # the weekly code must never touch these


def _listing(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.is_dir() else None


def _frozen_hashes():
    return {p.name: (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None) for p in FROZEN_NOV15}


def setUpModule():
    _BEFORE["reviews"] = _listing(REAL_REVIEWS)
    _BEFORE["published"] = _listing(REAL_PUBLISHED)
    _BEFORE["annotations"] = _listing(REAL_ANNOTATIONS)
    _BEFORE["frozen"] = _frozen_hashes()


def tearDownModule():
    assert _listing(REAL_REVIEWS) == _BEFORE["reviews"], "tests changed the real weekly/reviews folder"
    assert _listing(REAL_PUBLISHED) == _BEFORE["published"], "tests changed the real weekly/published folder"
    assert _listing(REAL_ANNOTATIONS) == _BEFORE["annotations"], "tests changed the real weekly/annotations folder"
    assert _frozen_hashes() == _BEFORE["frozen"], "tests changed a frozen Nov 15 file"


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tree_hashes(root):
    return {str(p.relative_to(root)): sha_file(p) for p in sorted(Path(root).rglob("*")) if p.is_file()}


class Base(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="weekly-test-"))
        self.inputs = self.tmp / "inputs"
        self.work = self.tmp / "work"
        shutil.copytree(str(REAL_DAY_DIR), str(self.inputs / DAY))
        self.saved = (W.INPUTS, W.REVIEWS, W.PUBLISHED, W.clock, W.MAX_PER_DATE, W.MAX_PER_WINDOW, W.ANNOTATIONS)
        W.INPUTS, W.REVIEWS, W.PUBLISHED = self.inputs, self.work / "reviews", self.work / "published"
        W.ANNOTATIONS = self.work / "annotations"
        self.now = NOW0
        W.clock = lambda: self.now

    def tearDown(self):
        (W.INPUTS, W.REVIEWS, W.PUBLISHED, W.clock, W.MAX_PER_DATE, W.MAX_PER_WINDOW, W.ANNOTATIONS) = self.saved
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    # ------------------------------------------------------------ helpers
    def refused(self, code, fn, *a, **kw):
        with self.assertRaises(W.Refused) as cm:
            fn(*a, **kw)
        self.assertEqual(cm.exception.code, code, cm.exception.detail)
        return cm.exception

    def scr(self, **kw):
        return W.screen(DAY, **kw)

    def kick(self, text):
        return W.parse_ts(text)

    def pick(self, scr, window, market="spreads", exclude=(), max_price=150, side=None):
        for w in scr["windows"]:
            if w["name"] != window:
                continue
            for g in w["games"]:
                if g["event_id"] in exclude or g["state"] != "scheduled":
                    continue
                for c in g["contracts"]:
                    if (c["market"] == market and c["reviewable"] and c["best_in_band"]
                            and c["best_in_band"]["price"] <= max_price and (side is None or c["side"] == side)):
                        return g, c
        self.fail("no reviewable %s contract in window %s" % (market, window))

    def call(self, c, floor=None, **extra):
        d = dict(event_id=c["event_id"], market=c["market"], subject=c["subject"], side=c["side"], point=c["point"],
                 minimum_price=floor if floor is not None else c["best_in_band"]["price"],
                 thesis="Test thesis for " + c["label"], counterevidence="Test counterevidence: injuries unknown.",
                 condition="Only if inactives are clean at kickoff.", sources=["https://www.espn.com/nfl/scoreboard"])
        d.update(extra)
        return d

    def payload(self, scr, windows, calls, **kw):
        p = dict(api="weekly/1", date=DAY, author="unit test",
                 edition=dict(captured_utc=scr["edition"]["captured_utc"], sha256=scr["edition"]["sha256"]),
                 windows=windows, calls=calls)
        p.update(kw)
        return p

    def basic_review(self):
        """early: 1 call, late: 1 call, night: no_play. Returns (scr, payload, calls)."""
        scr = self.scr()
        _, ce = self.pick(scr, "early")
        _, cl = self.pick(scr, "late")
        calls = [self.call(ce), self.call(cl)]
        pay = self.payload(scr, {"early": {"decision": "calls", "note": "n1"}, "late": {"decision": "calls"},
                                 "night": {"decision": "no_play", "note": "nothing I would take", "considered": "night spread"}},
                           calls)
        return scr, pay, calls

    def add_capture(self, name, captured_utc, mutate):
        base = json.loads((self.inputs / DAY / "captures").glob("*.json").__next__().read_text())
        doc = copy.deepcopy(base)
        doc["captured_utc"] = captured_utc
        mutate(doc)
        p = self.inputs / DAY / "captures" / name
        p.write_text(json.dumps(doc, sort_keys=True))
        return p

    def add_detailed(self, name="2026-11-15T075000Z.json", captured_utc="2026-11-15T07:50:00Z", n_games=2):
        """A capture that also has event_odds (the Nov 15 detailed shape) for the first n_games games."""
        upd = "2026-11-15T07:48:00Z"

        def mutate(doc):
            doc["event_odds"] = []
            for g in doc["games"][:n_games]:
                home, away = g["home_team"], g["away_team"]
                outs_tt = [dict(name=n, description=team, point=21.5, price=p) for team in (home, away)
                           for n, p in (("Over", -110), ("Under", -110))]
                markets = [
                    dict(key="team_totals", last_update=upd, outcomes=outs_tt),
                    dict(key="h2h_h1", last_update=upd, outcomes=[dict(name=home, price=-130), dict(name=away, price=110)]),
                    dict(key="spreads_h1", last_update=upd, outcomes=[dict(name=home, point=-3.5, price=-110), dict(name=away, point=3.5, price=-110)]),
                    dict(key="totals_h1", last_update=upd, outcomes=[dict(name="Over", point=21.5, price=-110), dict(name="Under", point=21.5, price=-110)]),
                    dict(key="team_totals_h1", last_update=upd, outcomes=[dict(name="Over", description=home, point=10.5, price=-105), dict(name="Under", description=home, point=10.5, price=-115)]),
                    dict(key="player_pass_yds", last_update=upd, outcomes=[dict(name="Over", description="Test Passer", point=270.5, price=-115), dict(name="Under", description="Test Passer", point=270.5, price=-105)]),
                    dict(key="player_rush_yds", last_update=upd, outcomes=[dict(name="Over", description="Test Runner", point=64.5, price=-110), dict(name="Under", description="Test Runner", point=64.5, price=-110)]),
                    dict(key="player_reception_yds", last_update=upd, outcomes=[dict(name="Over", description="Test Receiver", point=52.5, price=-120), dict(name="Under", description="Test Receiver", point=52.5, price=100)]),
                    dict(key="player_anytime_td", last_update=upd, outcomes=[dict(name="Yes", description="Test Runner", price=120)]),
                ]
                doc["event_odds"].append(dict(id=g["id"], sport_key="americanfootball_nfl", sport_title="NFL",
                                              commence_time=g["commence_time"], home_team=home, away_team=away,
                                              bookmakers=[dict(key="fanduel", title="FanDuel", last_update=upd, markets=markets)]))
        return self.add_capture(name, captured_utc, mutate)

    def publish_basic(self):
        scr, pay, calls = self.basic_review()
        W.submit_review(DAY, pay)
        return scr, pay, calls, W.publish(DAY)


# ---------------------------------------------------------------- parity with the engine
@unittest.skipIf(SM is None, "selection_markets is not importable here")
class TestEngineParity(Base):
    def test_constants_match_engine(self):
        self.assertEqual(W.MARKETS, SM.MARKETS)
        self.assertEqual(W.PROP_NAMES, SM.NAMES)
        self.assertEqual(W.WINDOW_LABELS, SM.WINDOWS)

    def _all_contracts(self, scr):
        for w in scr["windows"]:
            for g in w["games"]:
                for c in g["contracts"]:
                    yield g, c

    def _check(self, scr):
        n = 0
        for g, c in self._all_contracts(scr):
            want = SM.key_for(c["event_id"], c["market"], c["subject"], c["side"], c["point"])
            self.assertEqual(c["id"], want)
            core = SM.label_for(c["market"], c["subject"], c["side"], c["point"])
            self.assertTrue(c["label"].startswith(core + " ("), (c["label"], core))
            n += 1
        return n

    def test_ids_and_labels_on_real_capture(self):
        n = self._check(self.scr())
        self.assertGreater(n, 80)

    def test_ids_and_labels_on_detailed_capture(self):
        self.add_detailed()
        scr = self.scr()
        n = self._check(scr)
        markets = {c["market"] for _, c in self._all_contracts(scr)}
        self.assertEqual(markets, set(W.MARKETS))
        self.assertGreater(n, 100)

    def test_window_of_matches_engine(self):
        for w in self.scr()["windows"]:
            for g in w["games"]:
                self.assertEqual(SM.window(g["kickoff_utc"]), g["window"])


# ---------------------------------------------------------------- date picker and screen
class TestScreen(Base):
    def test_dates(self):
        d = W.dates()
        self.assertEqual(len(d["dates"]), 1)
        row = d["dates"][0]
        self.assertEqual((row["date"], row["games"], row["state"], row["editions"]), (DAY, 11, "ready", 1))
        self.assertEqual(row["windows"], {"early": 7, "late": 3, "night": 1})
        self.assertEqual(set(row["review_state"].values()), {"unreviewed"})
        self.assertFalse(row["published"])
        self.assertRegex(row["latest_sha256"], r"^[a-f0-9]{64}$")

    def test_bad_and_missing_dates(self):
        for bad in ("2026-11-15", "2026-11-23", "2026-13-01", "garbage", "2026-11-8", None, 20261122):
            self.refused("BAD_DATE", W.screen, bad)
        self.refused("NO_INPUTS", W.screen, "2026-11-29")
        self.refused("NO_CARD", W.current_card, DAY)

    def test_screen_is_market_only_and_complete(self):
        s = self.scr()
        self.assertTrue(s["provisional"])
        self.assertIsNone(s["engine"])
        self.assertEqual(sum(len(w["games"]) for w in s["windows"]), 11)
        self.assertEqual({w["name"]: len(w["games"]) for w in s["windows"]}, {"early": 7, "late": 3, "night": 1})
        self.assertEqual(s["inputs"]["odds"]["markets_present"], ["h2h", "spreads", "totals"])
        self.assertEqual(len(s["inputs"]["odds"]["markets_unavailable"]), 8)
        self.assertTrue(any("unavailable in this capture" in m and "main lines only" in m for m in s["missing"]))
        self.assertTrue(any("betmgm" in w and "espnbet" in w for w in s["warnings"]))
        self.assertIn("unknown", s["evidence_labels"])
        for w in s["windows"]:
            self.assertEqual(w["max_calls"], 2)
            for g in w["games"]:
                self.assertTrue(g["espn_event_id"], "every game pairs with the schedule")
                self.assertEqual(g["markets_unavailable"] and len(g["markets_unavailable"]), 8)
                self.assertTrue(any("markets not in this capture" in m for m in g["missing"]))

    def test_no_cross_game_contamination(self):
        s = self.scr()
        seen = {}
        for w in s["windows"]:
            for g in w["games"]:
                for c in g["contracts"]:
                    self.assertEqual(c["event_id"], g["event_id"])
                    self.assertTrue(c["id"].startswith(g["event_id"] + ":"))
                    self.assertNotIn(c["id"], seen, "contract ids are unique across games")
                    seen[c["id"]] = g["event_id"]
                    self.assertTrue(c["label"].endswith("(%s at %s)" % (g["away"]["abbr"], g["home"]["abbr"])))
        self.assertEqual(len(set(seen.values())), 11)

    def test_filters(self):
        s = self.scr(window="late", market="spreads", band_only=True)
        self.assertEqual([w["name"] for w in s["windows"]], ["late"])
        for g in s["windows"][0]["games"]:
            for c in g["contracts"]:
                self.assertEqual(c["market"], "spreads")
                self.assertIsNotNone(c["best_in_band"])
        self.refused("BAD_WINDOW", W.screen, DAY, window="noon")
        self.refused("BAD_MARKET", W.screen, DAY, market="player_anytime_td")
        self.refused("EDITION_UNKNOWN", W.screen, DAY, edition="2026-01-01T00:00:00Z")
        self.refused("EDITION_UNKNOWN", W.screen, DAY, edition="0" * 64)

    def test_edition_pins_resolve(self):
        s = self.scr()
        by_ts = self.scr(edition=s["edition"]["captured_utc"])
        by_sha = self.scr(edition=s["edition"]["sha256"])
        self.assertEqual(by_ts["edition"]["sha256"], by_sha["edition"]["sha256"], s["edition"]["sha256"])
        self.assertTrue(s["edition"]["is_latest"])

    def test_screen_is_a_pure_read(self):
        before = tree_hashes(self.inputs)
        self.scr()
        W.dates()
        self.assertEqual(before, tree_hashes(self.inputs))
        self.assertFalse(self.work.exists(), "screen and dates must not create reviews/ or published/")

    def test_contract_fields_and_freshness_rules(self):
        s = self.scr()
        for w in s["windows"]:
            for g in w["games"]:
                for c in g["contracts"]:
                    self.assertEqual(c["period"], "full_game")
                    if c["market"] in ("h2h", "spreads"):
                        self.assertEqual(c["subject"], "")
                    for q in c["quotes"]:
                        self.assertEqual(q["in_band"], 100 <= abs(q["price"]) <= 200)
                        self.assertEqual(q["fresh"], q["age_seconds_at_capture"] is not None and 0 <= q["age_seconds_at_capture"] <= 1800)
                    if c["best_in_band"]:
                        self.assertTrue(c["best_in_band"]["in_band"])
                        self.assertTrue(c["reviewable"])
                    else:
                        self.assertFalse(c["reviewable"])
                        self.assertTrue(c["why_not"])
                    nv = c["no_vig"]
                    self.assertEqual(nv["label"], "derived")
                    if nv["median"] is not None:
                        self.assertTrue(0 < nv["median"] < 1)

    def test_started_games_are_not_reviewable(self):
        s0 = self.scr()
        first = self.kick(s0["windows"][0]["first_kickoff_utc"])
        self.now = first + timedelta(minutes=1)
        s = self.scr()
        self.assertEqual(s["windows"][0]["state"], "closed")
        started = [g for g in s["windows"][0]["games"] if g["state"] == "started"]
        self.assertTrue(started)
        for g in started:
            for c in g["contracts"]:
                self.assertFalse(c["reviewable"])
                self.assertEqual(c["why_not"], "game has started")
        self.assertEqual(W.dates()["dates"][0]["state"], "partly_started")

    def test_stale_quote_cannot_back_a_call(self):
        def old(doc):
            for g in doc["games"]:
                for bk in g["bookmakers"]:
                    bk["last_update"] = "2026-11-15T05:00:00Z"
                    for m in bk["markets"]:
                        m["last_update"] = "2026-11-15T05:00:00Z"
        self.add_capture("2026-11-15T074000Z.json", "2026-11-15T07:40:00Z", old)
        s = self.scr()
        for w in s["windows"]:
            for g in w["games"]:
                for c in g["contracts"]:
                    self.assertFalse(c["reviewable"])
                    for q in c["quotes"]:
                        self.assertFalse(q["fresh"])
                    self.assertIn("no fresh quote", c["why_not"])

    def test_unpaired_schedule_and_odds_are_flagged_not_guessed(self):
        sched = self.inputs / DAY / "schedule.json"
        doc = json.loads(sched.read_text())
        doc["events"] = doc["events"][1:]
        sched.write_text(json.dumps(doc))
        s = self.scr()
        unpaired = [g for w in s["windows"] for g in w["games"] if g["espn_event_id"] is None]
        self.assertEqual(len(unpaired), 1)
        self.assertTrue(any("not in schedule.json" in m for m in unpaired[0]["missing"]))
        self.assertTrue(any("not in schedule.json" in w for w in s["warnings"]))

    def test_detailed_capture_supported_and_unsupported_markets(self):
        self.add_detailed()
        s = self.scr()
        self.assertEqual(s["edition"]["captured_utc"], "2026-11-15T07:50:00Z")
        self.assertEqual(s["inputs"]["odds"]["markets_unavailable"], [])
        self.assertNotIn("player_anytime_td", {c["market"] for w in s["windows"] for g in w["games"] for c in g["contracts"]})
        with_detail = [g for w in s["windows"] for g in w["games"] if any(c["market"] == "player_pass_yds" for c in g["contracts"])]
        without = [g for w in s["windows"] for g in w["games"] if g not in with_detail]
        self.assertEqual(len(with_detail), 2)
        for g in with_detail:
            self.assertEqual(g["markets_unavailable"], [])
        for g in without:
            self.assertEqual(len(g["markets_unavailable"]), 8)
        prop = [c for g in with_detail for c in g["contracts"] if c["market"] == "player_pass_yds" and c["side"] == "Over"][0]
        self.assertEqual((prop["subject"], prop["point"]), ("Test Passer", 270.5))
        self.assertIn("passing yards", prop["label"])
        self.assertEqual(prop["no_vig"]["books"], 1)
        half = [c for g in with_detail for c in g["contracts"] if c["market"] == "spreads_h1"][0]
        self.assertTrue(half["label"].startswith("First half · "))
        self.assertEqual(half["period"], "first_half")

    def test_event_odds_that_match_no_base_game_is_skipped(self):
        def bad(doc):
            doc["event_odds"] = [dict(id="f" * 32, home_team="Nobody", away_team="Else", commence_time="2026-11-22T18:00:00Z",
                                      bookmakers=[dict(key="fanduel", markets=[dict(key="team_totals", outcomes=[dict(name="Over", description="Nobody", point=1.5, price=-110)])])])]
        self.add_capture("2026-11-15T075500Z.json", "2026-11-15T07:55:00Z", bad)
        s = self.scr()
        self.assertTrue(any("does not match a base game" in w for w in s["warnings"]))
        self.assertEqual(s["inputs"]["odds"]["markets_present"], ["h2h", "spreads", "totals"])


# ---------------------------------------------------------------- review intake
class TestReview(Base):
    def test_submit_list_verify_and_window_states(self):
        scr, pay, calls = self.basic_review()
        r = W.submit_review(DAY, pay)
        self.assertTrue(r["ok"])
        self.assertFalse(r["duplicate"])
        self.assertEqual([x["window"] for x in r["rows"]], ["early", "late", "night"])
        self.assertEqual({w: v["state"] for w, v in r["window_states"].items()}, {"early": "calls", "late": "calls", "night": "no_play"})
        self.assertEqual(r["warnings"], [])
        for row in r["rows"]:
            self.assertEqual(row["received_utc"], "2026-11-15T08:00:00Z")
            self.assertTrue(row["edition_is_latest"])
            self.assertFalse(row["late"])
        v = W.verify(DAY)
        self.assertEqual(v["rows"], 3)
        self.assertEqual(v["head_sha256"], r["rows"][-1]["sha256"])
        lst = W.list_reviews(DAY)
        self.assertTrue(lst["chain_ok"])
        self.assertEqual(len(lst["rows"]), 3)
        self.assertEqual(W.dates()["dates"][0]["review_state"], {"early": "calls", "late": "calls", "night": "no_play"})
        # rows are hash chained and append-only
        prev = "0" * 64
        for row in lst["rows"]:
            self.assertEqual(row["prev_sha256"], prev)
            prev = row["sha256"]

    def test_server_stamps_observed_price_and_client_time_is_only_stored(self):
        scr, pay, calls = self.basic_review()
        pay["client_utc"] = "2099-01-01T00:00:00Z"
        for c in pay["calls"]:
            c["observed_price"] = 9999     # a client-supplied observed price must be ignored
            c["observed"] = dict(book="nobook", price=9999)
        r = W.submit_review(DAY, pay)
        self.assertEqual(r["rows"][0]["client_claimed_utc"], "2099-01-01T00:00:00Z")
        self.assertEqual(r["rows"][0]["received_utc"], "2026-11-15T08:00:00Z")
        for row in r["rows"]:
            for c in row["calls"]:
                self.assertNotEqual(c["observed"]["book"], "nobook")
                src = [x for w in scr["windows"] for g in w["games"] for x in g["contracts"] if x["id"] == c["id"]][0]
                self.assertIn((c["observed"]["book"], c["observed"]["price"]), [(q["book"], q["price"]) for q in src["quotes"] if q["fresh"] and q["in_band"]])
                self.assertGreaterEqual(W.dec(c["observed"]["price"]), W.dec(c["minimum_price"]))

    def test_duplicate_resubmission_writes_nothing(self):
        scr, pay, calls = self.basic_review()
        W.submit_review(DAY, pay)
        path = W.REVIEWS / DAY / "reviews.jsonl"
        before = path.read_bytes()
        r2 = W.submit_review(DAY, copy.deepcopy(pay))
        self.assertTrue(r2["duplicate"])
        self.assertEqual(r2["rows"], [])
        self.assertEqual(path.read_bytes(), before)

    def test_revision_is_a_new_row_that_supersedes(self):
        scr, pay, calls = self.basic_review()
        first = W.submit_review(DAY, pay)
        pay2 = copy.deepcopy(pay)
        pay2["windows"] = {"night": {"decision": "no_play", "note": "changed my mind about the reason"}}
        pay2["calls"] = []
        r = W.submit_review(DAY, pay2)
        self.assertEqual(len(r["rows"]), 1)
        self.assertEqual(r["rows"][0]["supersedes"], first["rows"][2]["row_id"])
        lst = W.list_reviews(DAY)
        self.assertEqual(len(lst["rows"]), 4)               # nothing was edited or deleted
        self.assertEqual(lst["rows"][2], first["rows"][2])
        self.assertEqual(W.verify(DAY)["rows"], 4)

    def test_silence_is_not_a_pass(self):
        scr = self.scr()
        W.submit_review(DAY, self.payload(scr, {"early": {"decision": "no_play", "note": "nothing"}}, []))
        st = W.list_reviews(DAY)["window_states"]
        self.assertEqual(st["early"]["state"], "no_play")
        self.assertEqual(st["late"]["state"], "unreviewed")
        self.assertEqual(st["night"]["state"], "unreviewed")
        late_first = self.kick([w for w in scr["windows"] if w["name"] == "late"][0]["first_kickoff_utc"])
        self.now = late_first + timedelta(minutes=1)
        st = W.list_reviews(DAY)["window_states"]
        self.assertEqual(st["late"]["state"], "unreviewed_after_close")
        self.assertEqual(st["night"]["state"], "unreviewed")
        pub = W.publish(DAY)
        card = json.loads(Path(pub["sunday_card_path"]).read_text())
        self.assertEqual([p["window"] for p in card["passes"]], ["Morning / noon"])
        self.assertEqual(card["unreviewed_windows"], ["Afternoon", "Sunday night"])
        self.assertEqual(card["calls"], [])

    # ---- refusals
    def test_payload_shape_refusals(self):
        scr, pay, calls = self.basic_review()
        self.refused("BAD_PAYLOAD", W.submit_review, DAY, [])
        self.refused("BAD_PAYLOAD", W.submit_review, DAY, dict(pay, date="2026-11-29"))
        self.refused("BAD_PAYLOAD", W.submit_review, DAY, dict(pay, api="weekly/2"))
        self.refused("BAD_PAYLOAD", W.submit_review, DAY, dict(pay, windows={}))
        self.refused("BAD_PAYLOAD", W.submit_review, DAY, dict(pay, late="yes"))
        self.refused("BAD_PAYLOAD", W.submit_review, DAY, dict(pay, calls="x"))
        self.refused("INCOMPLETE_FIELD", W.submit_review, DAY, dict(pay, author=""))
        self.refused("BAD_WINDOW", W.submit_review, DAY, dict(pay, windows={"noon": {"decision": "calls"}}))
        self.refused("BAD_DECISION", W.submit_review, DAY, dict(pay, windows={"early": {"decision": "maybe"}}))
        self.refused("BAD_DATE", W.submit_review, "2026-11-15", pay)
        self.assertFalse((W.REVIEWS / DAY / "reviews.jsonl").exists(), "refusals write nothing")

    def test_edition_pin_refusals(self):
        scr, pay, calls = self.basic_review()
        self.refused("EDITION_UNKNOWN", W.submit_review, DAY, dict(pay, edition=None))
        self.refused("EDITION_UNKNOWN", W.submit_review, DAY, dict(pay, edition=dict(captured_utc="2026-11-15T07:34:18Z")))
        self.refused("EDITION_UNKNOWN", W.submit_review, DAY, dict(pay, edition=dict(captured_utc="2026-11-15T07:34:18Z", sha256="1" * 64)))
        self.add_capture("2026-11-15T090000Z.json", "2026-11-15T09:00:00Z", lambda d: None)   # dated after the pinned clock
        fut = [e for e in W.editions(DAY)[0] if e["captured_utc"] == "2026-11-15T09:00:00Z"][0]
        pay2 = dict(pay, edition=dict(captured_utc=fut["captured_utc"], sha256=fut["sha256"]))
        e = self.refused("EDITION_UNKNOWN", W.submit_review, DAY, pay2)
        self.assertIn("future", e.detail)

    def test_contract_refusals(self):
        scr = self.scr()
        _, c = self.pick(scr, "early")
        base = self.call(c)

        def go(call, **kw):
            return W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [call], **kw))

        self.refused("UNKNOWN_CONTRACT", go, dict(base, market="player_anytime_td"))
        e = self.refused("UNKNOWN_CONTRACT", go, dict(base, market="team_totals", subject="Anyone", side="Over", point=20.5))
        self.assertIn("main lines only", e.detail)
        self.refused("UNKNOWN_CONTRACT", go, dict(base, event_id="e" * 32))
        self.refused("UNKNOWN_CONTRACT", go, dict(base, point=base["point"] + 40.0))
        self.refused("UNKNOWN_CONTRACT", go, dict(base, side="Not A Team"))
        for k in ("event_id", "market", "side"):
            self.refused("INCOMPLETE_FIELD", go, {x: y for x, y in base.items() if x != k})
        for k in ("thesis", "counterevidence", "condition"):
            self.refused("INCOMPLETE_FIELD", go, {x: y for x, y in base.items() if x != k})
            self.refused("INCOMPLETE_FIELD", go, dict(base, **{k: "   "}))
        self.refused("INCOMPLETE_FIELD", go, dict(base, minimum_price="-110"))
        self.refused("INCOMPLETE_FIELD", go, dict(base, minimum_price=-110.5))
        self.refused("INCOMPLETE_FIELD", go, dict(base, minimum_price=50))
        self.refused("INCOMPLETE_FIELD", go, dict(base, minimum_price=None))
        self.refused("INCOMPLETE_FIELD", go, dict(base, sources=["http://example.com/x"]))
        self.refused("INCOMPLETE_FIELD", go, dict(base, sources=["https://example.com/x?api_key=abc"]))
        self.refused("INCOMPLETE_FIELD", go, dict(base, sources="https://example.com/x"))
        self.refused("INCOMPLETE_FIELD", go, dict(base, point="14"))
        for floor in (-250, 250, -201, 201):
            self.refused("PRICE_OUT_OF_BAND", go, dict(base, minimum_price=floor))
        # the "rationale" and "risk" names are accepted aliases
        alias = {k: v for k, v in base.items() if k not in ("thesis", "counterevidence")}
        alias.update(rationale="alias thesis", risk="alias counter")
        r = go(alias)
        self.assertEqual(r["rows"][0]["calls"][0]["thesis"], "alias thesis")
        self.assertEqual(r["rows"][0]["calls"][0]["counterevidence"], "alias counter")

    def test_floor_above_quote(self):
        scr = self.scr()
        _, c = self.pick(scr, "early")
        p = c["best_in_band"]["price"]
        floor = min(200, p + 30) if p > 0 else 105
        e = self.refused("FLOOR_ABOVE_QUOTE", W.submit_review, DAY,
                         self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c, floor=floor)]))
        self.assertIn("pays less than your floor", e.detail)
        # exactly the best price is accepted
        W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c, floor=p)]))

    def test_window_game_and_count_limits(self):
        scr = self.scr()
        ge1, c1 = self.pick(scr, "early")
        ge2, c2 = self.pick(scr, "early", exclude=(ge1["event_id"],))
        ge3, c3 = self.pick(scr, "early", exclude=(ge1["event_id"], ge2["event_id"]))
        _, cl = self.pick(scr, "late")
        # a call in a window the payload does not declare as 'calls'
        self.refused("WRONG_WINDOW", W.submit_review, DAY, self.payload(scr, {"late": {"decision": "calls"}}, [self.call(c1)]))
        self.refused("WRONG_WINDOW", W.submit_review, DAY, self.payload(scr, {"early": {"decision": "no_play"}}, [self.call(c1)]))
        # two DISTINCT contracts in one game (a side and a total) are allowed: Matthew's rule is 0-2 per window, not one per game
        tot = [x for x in ge1["contracts"] if x["market"] == "totals" and x["reviewable"] and x["best_in_band"]][0]
        r = W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c1), self.call(tot)]))
        self.assertEqual([c["market"] for c in r["rows"][0]["calls"]], ["spreads", "totals"])
        self.assertEqual({c["event_id"] for c in r["rows"][0]["calls"]}, {ge1["event_id"]})
        # the very same contract twice is refused, with a code that says so (not a game rule)
        e = self.refused("DUPLICATE_CONTRACT", W.submit_review, DAY,
                         self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c1), self.call(c1, thesis="again")]))
        self.assertIn(c1["label"], e.detail)
        # more than two in a window, whether in three games or three contracts of one game
        self.refused("WINDOW_LIMIT", W.submit_review, DAY,
                     self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c1), self.call(c2), self.call(c3)]))
        self.refused("WINDOW_LIMIT", W.submit_review, DAY,
                     self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c1), self.call(tot), self.call(c2)]))
        # exactly two is fine
        r = W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c1), self.call(c2)]))
        self.assertEqual(len(r["rows"][0]["calls"]), 2)
        # 'calls' with no call in the window
        self.refused("INCOMPLETE_FIELD", W.submit_review, DAY, self.payload(scr, {"early": {"decision": "calls"}, "late": {"decision": "calls"}}, [self.call(c1)]))

    def test_date_limit_counts_other_windows(self):
        # With 3 windows x 2 calls the date cap (6) can't be exceeded through the public rules, so lower it to prove the check runs.
        W.MAX_PER_DATE = 3
        scr = self.scr()
        ge1, c1 = self.pick(scr, "early")
        ge2, c2 = self.pick(scr, "early", exclude=(ge1["event_id"],))
        gl1, l1 = self.pick(scr, "late")
        gl2, l2 = self.pick(scr, "late", exclude=(gl1["event_id"],))
        W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c1), self.call(c2)]))
        self.refused("DATE_LIMIT", W.submit_review, DAY, self.payload(scr, {"late": {"decision": "calls"}}, [self.call(l1), self.call(l2)]))
        W.submit_review(DAY, self.payload(scr, {"late": {"decision": "calls"}}, [self.call(l1)]))      # 3 in total is allowed

    def test_after_kickoff_needs_late_flag_and_late_rows_are_excluded(self):
        scr = self.scr()
        ge, ce = self.pick(scr, "early")
        self.now = self.kick(ge["kickoff_utc"]) + timedelta(minutes=2)
        pay = self.payload(scr, {"early": {"decision": "calls"}}, [self.call(ce)])
        self.refused("AFTER_KICKOFF", W.submit_review, DAY, pay)
        self.refused("AFTER_KICKOFF", W.submit_review, DAY, self.payload(scr, {"early": {"decision": "no_play", "note": "late pass"}}, []))
        self.assertFalse((W.REVIEWS / DAY / "reviews.jsonl").exists())
        r = W.submit_review(DAY, dict(pay, late=True))
        self.assertTrue(r["rows"][0]["late"])
        self.assertTrue(any("late=true" in w for w in r["warnings"]))
        self.assertEqual(W.list_reviews(DAY)["window_states"]["early"]["state"], "unreviewed_after_close")
        self.refused("NOTHING_TO_PUBLISH", W.publish, DAY)

    def test_window_closes_at_its_first_kickoff_even_for_a_later_game(self):
        # Stagger one early game by 20 minutes in a newer capture so the window has two different kickoffs.
        target = {}

        def stagger(doc):
            for g in doc["games"]:
                t = W.parse_ts(g["commence_time"])
                if W.window_of(t) == "early" and "id" not in target:
                    target["id"] = g["id"]
                    g["commence_time"] = W.ts(t + timedelta(minutes=20))
        self.add_capture("2026-11-15T075000Z.json", "2026-11-15T07:50:00Z", stagger)
        scr = self.scr()
        early = [w for w in scr["windows"] if w["name"] == "early"][0]
        later = [g for g in early["games"] if g["kickoff_utc"] > early["first_kickoff_utc"]]
        self.assertEqual(len(later), 1, "one early game should now start later than the rest")
        others = tuple(g["event_id"] for g in early["games"] if g is not later[0])
        _, c = self.pick(scr, "early", exclude=others)
        self.assertEqual(c["event_id"], later[0]["event_id"])
        self.now = self.kick(early["first_kickoff_utc"]) + timedelta(seconds=30)    # the game itself has not started
        self.assertEqual([g["state"] for g in self.scr()["windows"][0]["games"] if g["event_id"] == later[0]["event_id"]], ["scheduled"])
        e = self.refused("AFTER_KICKOFF", W.submit_review, DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c)]))
        self.assertIn("window started", e.detail)
        r = W.submit_review(DAY, dict(self.payload(scr, {"early": {"decision": "calls"}}, [self.call(c)]), late=True))
        self.assertTrue(r["rows"][0]["late"])

    def test_older_edition_is_accepted_with_a_warning(self):
        scr, pay, calls = self.basic_review()
        self.add_capture("2026-11-15T075000Z.json", "2026-11-15T07:50:00Z", lambda d: None)
        r = W.submit_review(DAY, pay)
        self.assertTrue(any("not the latest" in w for w in r["warnings"]))
        self.assertFalse(r["rows"][0]["edition_is_latest"])

    def test_chain_tampering_is_detected(self):
        scr, pay, calls = self.basic_review()
        W.submit_review(DAY, pay)
        path = W.REVIEWS / DAY / "reviews.jsonl"
        text = path.read_text()
        path.write_text(text.replace("nothing I would take", "nothing I would takE", 1))
        self.refused("CHAIN_BROKEN", W.verify, DAY)
        self.refused("CHAIN_BROKEN", W.publish, DAY)
        self.refused("CHAIN_BROKEN", W.submit_review, DAY, dict(pay, author="someone else"))
        lst = W.list_reviews(DAY)
        self.assertFalse(lst["chain_ok"])
        self.assertTrue(lst["chain_problem"])
        # deleting a row breaks the chain too
        lines = text.splitlines(True)
        path.write_text("".join(lines[:1] + lines[2:]))
        self.refused("CHAIN_BROKEN", W.verify, DAY)


# ---------------------------------------------------------------- publish and the published card
class TestPublish(Base):
    KEYS = {"ok", "api", "date", "unchanged", "published_utc", "output_path", "sunday_card_path", "card_path", "current_path",
            "history_sunday_card_path", "history_card_path", "capture_path", "capture_sha256", "sunday_card_sha256",
            "card_sha256", "review_rows"}

    def test_publish_files_and_result_keys(self):
        scr, pay, calls, pub = self.publish_basic()
        self.assertTrue(self.KEYS <= set(pub), self.KEYS - set(pub))
        self.assertFalse(pub["unchanged"])
        self.assertEqual(pub["output_path"], pub["sunday_card_path"])
        self.assertEqual(pub["capture_sha256"], scr["edition"]["sha256"])
        self.assertEqual(Path(pub["capture_path"]).resolve(), Path(scr["edition"]["path"]).resolve())
        out = Path(pub["sunday_card_path"]).parent
        self.assertEqual(out, W.PUBLISHED / DAY)
        for name in ("Sunday_Card.json", "Card.json", "CURRENT.json"):
            self.assertTrue((out / name).is_file(), name)
        self.assertTrue(Path(pub["history_sunday_card_path"]).is_file())
        self.assertTrue(Path(pub["history_card_path"]).is_file())
        self.assertEqual(sha_file(pub["sunday_card_path"]), pub["sunday_card_sha256"])
        self.assertEqual(sha_file(pub["card_path"]), pub["card_sha256"])
        self.assertEqual(sha_file(pub["history_sunday_card_path"]), pub["sunday_card_sha256"])
        self.assertTrue(W.dates()["dates"][0]["published"])

    def test_sunday_card_shape_and_no_inherited_nov15_calls(self):
        scr, pay, calls, pub = self.publish_basic()
        card = json.loads(Path(pub["sunday_card_path"]).read_text())
        self.assertEqual(card["slate_date"], DAY)
        self.assertEqual(card["earliest_snapshot"], scr["edition"]["captured_utc"])
        self.assertEqual(card["snapshot_sha256"], scr["edition"]["sha256"])
        self.assertEqual(card["issued_utc"], "2026-11-15T08:00:00Z")
        self.assertEqual(len(card["calls"]), 2)
        self.assertEqual(len(card["passes"]), 1)
        self.assertEqual(card["passes"][0]["window"], "Sunday night")
        self.assertEqual(card["passes"][0]["decision"], "Pass")
        self.assertEqual(card["passes"][0]["considered"], "night spread")
        self.assertEqual(card["unreviewed_windows"], [])
        self.assertTrue(card["source"]["paper_only"])
        need = {"label", "event_id", "window", "kickoff", "game", "market", "side", "subject", "point", "minimum_price",
                "observed_book", "observed_price", "book_updated_utc", "condition", "thesis", "counterevidence", "source",
                "decision", "ticket"}
        for c in card["calls"]:
            self.assertTrue(need <= set(c), need - set(c))
            self.assertIsNone(c["ticket"])
            self.assertTrue(c["kickoff"].startswith(DAY))
            self.assertLess(card["issued_utc"], c["kickoff"])
            self.assertTrue(c["source"].startswith("https://"))
        slate15 = SLATE / "slate_20261115.json"
        if slate15.is_file():
            ids15 = {g.get("event_id") or g.get("id") for g in json.loads(slate15.read_text()).get("games", [])}
            self.assertFalse(ids15 & {c["event_id"] for c in card["calls"]})
        self.assertNotIn("96d09884cab7d0444c8f95551def07f43a94ed9de22695a280947310d4106932", json.dumps(card))

    def test_card_json_evidence_labels_and_availability(self):
        scr, pay, calls, pub = self.publish_basic()
        full = json.loads(Path(pub["card_path"]).read_text())
        self.assertTrue(full["paper_only"])
        self.assertEqual(full["summary"]["calls"], 2)
        self.assertEqual(full["summary"]["no_play_windows"], 1)
        self.assertEqual(full["summary"]["unreviewed_windows"], 0)
        self.assertEqual(len(full["markets_unavailable_in_capture"]), 8)
        for w in full["windows"]:
            for c in w["calls"]:
                ev = c["evidence"]
                self.assertEqual((ev["price"], ev["no_vig"], ev["judgment"]), ("known", "derived", "estimated"))
                self.assertEqual((ev["fill_and_personal_price"], ev["final_inactives"]), ("unknown", "unknown"))
                self.assertIs(ev["local_availability_verified"], False)
                self.assertEqual(c["state"], "pregame_at_issue")

    def test_brief_py_accepts_the_published_card(self):
        brief = load_brief()
        if brief is None:
            self.skipTest("brief.py validators could not be extracted")
        scr, pay, calls, pub = self.publish_basic()
        card = json.loads(Path(pub["sunday_card_path"]).read_text())
        brief["validate_card"](card)
        for c in card["calls"]:
            q = brief["initial_quote"](c, card)
            self.assertEqual((q["book"], q["price"]), (c["observed_book"], c["observed_price"]))
        brief["check_capture"](pub["capture_path"], card)

    def test_brief_py_rejects_a_tampered_card_or_capture(self):
        brief = load_brief()
        if brief is None:
            self.skipTest("brief.py validators could not be extracted")
        scr, pay, calls, pub = self.publish_basic()
        card = json.loads(Path(pub["sunday_card_path"]).read_text())
        bad = copy.deepcopy(card)
        bad["snapshot_sha256"] = "2" * 64
        with self.assertRaises(Exception):
            brief["check_capture"](pub["capture_path"], bad)
        bad2 = copy.deepcopy(card)
        bad2["calls"][0]["observed_price"] = bad2["calls"][0]["observed_price"] + 7
        with self.assertRaises(Exception):
            brief["check_capture"](pub["capture_path"], bad2)

    def test_publish_is_idempotent_and_history_is_write_once(self):
        scr, pay, calls, pub = self.publish_basic()
        hist = Path(pub["history_sunday_card_path"]).parent
        before = tree_hashes(hist)
        again = W.publish(DAY)
        self.assertTrue(again["unchanged"])
        self.assertEqual(again["sunday_card_sha256"], pub["sunday_card_sha256"])
        self.assertEqual(tree_hashes(hist), before)
        # a revision changes the card: one new pair in history, the old pair untouched
        pay2 = self.payload(scr, {"night": {"decision": "no_play", "note": "revised reason"}}, [])
        self.now = self.now + timedelta(minutes=5)
        W.submit_review(DAY, pay2)
        newer = W.publish(DAY)
        self.assertFalse(newer["unchanged"])
        after = tree_hashes(hist)
        self.assertEqual(len(after), len(before) + 2)
        for k, v in before.items():
            self.assertEqual(after[k], v, "history file %s changed" % k)
        self.assertNotEqual(newer["sunday_card_sha256"], pub["sunday_card_sha256"])
        cur = W.current_card(DAY)
        self.assertEqual(cur["sunday_card"]["passes"][0]["reason"], "revised reason")

    def test_current_card_rehashes(self):
        scr, pay, calls, pub = self.publish_basic()
        cur = W.current_card(DAY)
        self.assertTrue(cur["unchanged"])
        self.assertTrue(self.KEYS <= set(cur))
        self.assertEqual(cur["sunday_card"]["slate_date"], DAY)
        self.assertEqual(cur["card"]["date"], DAY)
        Path(pub["sunday_card_path"]).write_text(Path(pub["sunday_card_path"]).read_text().replace("Pass", "Pasx"))
        self.refused("CHAIN_BROKEN", W.current_card, DAY)

    def test_nothing_to_publish_and_no_card(self):
        self.refused("NOTHING_TO_PUBLISH", W.publish, DAY)
        self.refused("NO_CARD", W.current_card, DAY)

    def test_started_before_issue_calls_leave_the_sunday_card(self):
        scr = self.scr()
        ge, ce = self.pick(scr, "early")
        W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(ce)]))
        first = W.publish(DAY)
        c1 = json.loads(Path(first["sunday_card_path"]).read_text())
        self.assertEqual(len(c1["calls"]), 1)
        self.assertEqual(c1["excluded_started_before_issue"], [])
        # later, after that game began, another window gets its decision; issued_utc moves past the kickoff
        self.now = self.kick(ge["kickoff_utc"]) + timedelta(minutes=5)
        W.submit_review(DAY, self.payload(scr, {"night": {"decision": "no_play", "note": "pass"}}, []))
        second = W.publish(DAY)
        c2 = json.loads(Path(second["sunday_card_path"]).read_text())
        self.assertEqual(c2["calls"], [])
        self.assertEqual([x["event_id"] for x in c2["excluded_started_before_issue"]], [ce["event_id"]])
        full = json.loads(Path(second["card_path"]).read_text())
        self.assertEqual(full["summary"]["calls_started_before_issue"], 1)
        self.assertEqual(full["summary"]["calls_in_sunday_card"], 0)
        self.assertEqual(full["windows"][0]["calls"][0]["state"], "started_before_issue")
        # the snapshot published before kickoff is still in history and still has the call
        old = json.loads(Path(first["history_sunday_card_path"]).read_text())
        self.assertEqual(len(old["calls"]), 1)

    def test_mixed_editions_refused(self):
        scr = self.scr()
        _, ce = self.pick(scr, "early")
        W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(ce)]))
        self.add_capture("2026-11-15T075000Z.json", "2026-11-15T07:50:00Z", lambda d: None)
        scr2 = self.scr()
        self.assertNotEqual(scr["edition"]["sha256"], scr2["edition"]["sha256"])
        _, cl = self.pick(scr2, "late")
        W.submit_review(DAY, self.payload(scr2, {"late": {"decision": "calls"}}, [self.call(cl)]))
        e = self.refused("MIXED_EDITIONS", W.publish, DAY)
        self.assertIn("resubmit", e.detail)
        # resubmitting the early window against the same edition fixes it
        _, ce2 = self.pick(scr2, "early")
        W.submit_review(DAY, self.payload(scr2, {"early": {"decision": "calls"}}, [self.call(ce2)]))
        pub = W.publish(DAY)
        self.assertEqual(json.loads(Path(pub["sunday_card_path"]).read_text())["earliest_snapshot"], "2026-11-15T07:50:00Z")

    def test_detailed_capture_calls_publish_with_full_identity(self):
        self.add_detailed()
        scr = self.scr()
        self.assertEqual(scr["edition"]["captured_utc"], "2026-11-15T07:50:00Z")
        picks = []
        for w in scr["windows"]:
            for g in w["games"]:
                for c in g["contracts"]:
                    if c["market"] in ("player_pass_yds", "team_totals", "spreads_h1") and c["reviewable"] and c["side"] in ("Over", g["home"]["name"]):
                        picks.append((w["name"], g, c))
        by_market = {}
        for wn, g, c in picks:
            by_market.setdefault(c["market"], (wn, g, c))
        self.assertEqual(set(by_market), {"player_pass_yds", "team_totals", "spreads_h1"})
        wn, g, prop = by_market["player_pass_yds"]
        pay = self.payload(scr, {wn: {"decision": "calls"}}, [self.call(prop)])
        W.submit_review(DAY, pay)
        pub = W.publish(DAY)
        card = json.loads(Path(pub["sunday_card_path"]).read_text())
        c = card["calls"][0]
        self.assertEqual((c["market"], c["subject"], c["side"], c["point"]), ("player_pass_yds", "Test Passer", "Over", 270.5))
        self.assertEqual(c["observed_book"], "fanduel")
        self.assertIn("passing yards", c["label"])
        brief = load_brief()
        if brief is not None:
            brief["validate_card"](card)
            brief["check_capture"](pub["capture_path"], card)

    def test_main_only_capture_states_other_markets_unavailable(self):
        scr = self.scr()
        _, ce = self.pick(scr, "early")
        e = self.refused("UNKNOWN_CONTRACT", W.submit_review, DAY,
                         self.payload(scr, {"early": {"decision": "calls"}}, [dict(self.call(ce), market="player_pass_yds", subject="Some Passer", side="Over", point=250.5)]))
        self.assertIn("player_pass_yds", e.detail)
        self.assertIn("main lines only", e.detail)

    def test_published_files_have_no_secrets(self):
        scr, pay, calls, pub = self.publish_basic()
        for p in Path(pub["sunday_card_path"]).parent.rglob("*.json"):
            text = p.read_text()
            self.assertIsNone(re.search(r"sk-[A-Za-z0-9\-]{20,}", text))
            self.assertNotIn("apiKey", text)
            self.assertNotIn("api_key", text)


# ---------------------------------------------------------------- CLI
class SameGame(Base):
    """Helpers for the same-event rule: 0-2 calls per window, distinct contracts, shared-event note on published calls."""

    def game_with(self, window, *markets):
        """(screen, game, {market: [reviewable in-band contracts]}) for the first scheduled game in the window that has all markets."""
        scr = self.scr()
        for w in scr["windows"]:
            if w["name"] != window:
                continue
            for g in w["games"]:
                if g["state"] != "scheduled":
                    continue
                got = {m: [c for c in g["contracts"] if c["market"] == m and c["reviewable"] and c["best_in_band"]] for m in markets}
                if all(got.values()):
                    return scr, g, got
        self.fail("no game in %s with %s" % (window, markets))

    def other_window_call(self, scr, window, exclude=()):
        return self.pick(scr, window, exclude=exclude)[1]

    def third_in_same_direction(self, m, *used):
        """A third contract in the game that clashes with neither of `used`: another line in the same direction as one of them."""
        ids = {c["id"] for c in used}
        for c in used:
            for o in m[c["market"]]:
                if o["id"] not in ids and o["side"] == c["side"]:
                    return o
        self.fail("no same-direction third contract")


class TestSameGameRule(SameGame):
    def test_side_plus_total_same_game_allowed_dup_and_third_rejected(self):
        scr, g, m = self.game_with("early", "spreads", "totals")
        side, tot = m["spreads"][0], m["totals"][0]
        r = W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(side), self.call(tot)]))
        self.assertEqual(len(r["rows"][0]["calls"]), 2)
        self.refused("DUPLICATE_CONTRACT", W.submit_review, DAY,
                     self.payload(scr, {"early": {"decision": "calls"}}, [self.call(side), self.call(side, thesis="same contract again")]))
        third = self.third_in_same_direction(m, side, tot)
        self.refused("WINDOW_LIMIT", W.submit_review, DAY,
                     self.payload(scr, {"early": {"decision": "calls"}}, [self.call(side), self.call(tot), self.call(third)]))
        self.assertEqual(W.verify(DAY)["rows"], 1)          # only the accepted review was written

    def test_the_one_game_sunday_night_window_takes_zero_one_or_two(self):
        scr, g, m = self.game_with("night", "spreads", "totals")
        self.assertEqual(len([w for w in scr["windows"] if w["name"] == "night"][0]["games"]), 1)
        two = [self.call(m["spreads"][0]), self.call(m["totals"][0])]
        r = W.submit_review(DAY, self.payload(scr, {"night": {"decision": "calls"}}, two))
        self.assertEqual({c["event_id"] for c in r["rows"][0]["calls"]}, {g["event_id"]})
        self.assertEqual(len(r["rows"][0]["calls"]), 2)
        W.submit_review(DAY, self.payload(scr, {"night": {"decision": "calls"}}, two[:1]))      # one
        W.submit_review(DAY, self.payload(scr, {"night": {"decision": "no_play", "note": "pass"}}, []))   # zero
        self.refused("WINDOW_LIMIT", W.submit_review, DAY,
                     self.payload(scr, {"night": {"decision": "calls"}}, two + [self.call(self.third_in_same_direction(m, m["spreads"][0], m["totals"][0]))]))

    def test_shared_event_note_is_on_the_published_calls_only(self):
        brief = load_brief()
        scr, g, m = self.game_with("early", "spreads", "totals")
        side, tot = m["spreads"][0], m["totals"][0]
        lone = self.other_window_call(scr, "late")
        W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}, "late": {"decision": "calls"},
                                                "night": {"decision": "no_play", "note": "pass"}},
                                          [self.call(side), self.call(tot), self.call(lone)]))
        pub = W.publish(DAY)
        sunday = json.loads(Path(pub["sunday_card_path"]).read_text())
        full = json.loads(Path(pub["card_path"]).read_text())
        by_label = {c["label"]: c for c in sunday["calls"]}
        self.assertEqual(len(by_label), 3)
        for c in (side, tot):
            sh = by_label[c["label"]]["shared_event"]
            self.assertEqual((sh["event_id"], sh["calls_in_event"]), (g["event_id"], 2))
            self.assertTrue(sh["note"].startswith("Correlated: 2 calls on this card are in the same game"))
            self.assertIn("not independent", sh["note"])
            self.assertEqual([o["relation"] for o in sh["others"]], ["different_markets"])
            self.assertNotIn("opposite sides", sh["note"])
        self.assertNotIn("shared_event", by_label[lone["label"]])
        self.assertEqual(full["summary"]["calls_sharing_an_event"], 2)
        card_calls = {c["label"]: c for w in full["windows"] for c in w["calls"]}
        self.assertEqual(card_calls[side["label"]]["shared_event"], by_label[side["label"]]["shared_event"])
        self.assertNotIn("shared_event", card_calls[lone["label"]])
        if brief is not None:                                # the PDF's own validator still accepts a same-game card
            brief["validate_card"](sunday)
            brief["check_capture"](pub["capture_path"], sunday)

    def test_opposite_sides_of_one_market_are_refused_not_flagged(self):
        # release decision (integrated release owner, 2026-11-15): formal picks decline opposite directions
        scr, g, m = self.game_with("night", "spreads")
        a = m["spreads"][0]
        b = [c for c in m["spreads"] if c["side"] != a["side"]][0]
        e = self.refused("OPPOSITE_DIRECTION", W.submit_review, DAY,
                         self.payload(scr, {"night": {"decision": "calls"}}, [self.call(a), self.call(b)]))
        self.assertIn(a["label"], e.detail)
        self.assertIn(b["label"], e.detail)
        self.assertEqual(W.list_reviews(DAY)["rows"], [])

    def test_frozen_nov15_files_are_not_touched_by_a_full_run(self):
        before = _frozen_hashes()
        self.assertTrue(all(before.values()), before)
        scr, g, m = self.game_with("early", "spreads", "totals")
        W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(m["spreads"][0]), self.call(m["totals"][0])]))
        W.annotate(DAY, dict(api="weekly/1", date=DAY, author_kind="codex", author="reviewer", stance="concern", text="n"))
        pub = W.publish(DAY)
        self.assertEqual(_frozen_hashes(), before)
        blob = json.dumps(json.loads(Path(pub["sunday_card_path"]).read_text()))
        ids15 = {x.get("event_id") or x.get("id") for x in json.loads((SLATE / "slate_20261115.json").read_text()).get("games", [])}
        self.assertFalse([i for i in ids15 if i and i in blob])


class TestOppositeDirectionPure(unittest.TestCase):
    """opposite_direction_pair on synthetic calls, with the thresholds the release owner named."""

    G = "Test Away at Test Home"

    def c(self, market, side, point, subject="", event="e1"):
        return dict(event_id=event, market=market, subject=subject, side=side, point=point, game=self.G,
                    label="%s %s %s %s" % (subject, side, point, market))

    def test_named_clashes(self):
        for a, b in (
            (self.c("player_rush_yds", "Over", 22.5, "Jaylen Warren"), self.c("player_rush_yds", "Under", 24.5, "Jaylen Warren")),
            (self.c("totals", "Over", 45.5), self.c("totals", "Under", 47.5)),
            (self.c("spreads", "Test Home", -3.5), self.c("spreads", "Test Away", 2.5)),
            (self.c("h2h", "Test Home", None), self.c("h2h", "Test Away", None)),
            (self.c("spreads_h1", "Test Home", -1.5), self.c("spreads_h1", "Test Away", 2.5)),
            (self.c("team_totals", "Over", 24.5, "Test Home"), self.c("team_totals", "Under", 20.5, "Test Home")),
            (self.c("totals_h1", "Over", 21.5), self.c("totals_h1", "Under", 22.5)),
        ):
            self.assertEqual(W.opposite_direction_pair([a, b]), (a, b), a)
            self.assertEqual(W.opposite_direction_pair([b, a]), (b, a), a)

    def test_things_that_are_not_clashes(self):
        base = self.c("player_rush_yds", "Over", 22.5, "Jaylen Warren")
        for other in (
            self.c("player_rush_yds", "Over", 24.5, "Jaylen Warren"),                 # same direction, other line
            self.c("player_rush_yds", "Under", 24.5, "Najee Harris"),                 # other player
            self.c("player_reception_yds", "Under", 24.5, "Jaylen Warren"),           # other market
            self.c("player_rush_yds", "Under", 24.5, "Jaylen Warren", event="e2"),    # other game
        ):
            self.assertIsNone(W.opposite_direction_pair([base, other]), other)
        self.assertIsNone(W.opposite_direction_pair([self.c("totals", "Over", 45.5), self.c("totals_h1", "Under", 22.5)]))   # other period
        self.assertIsNone(W.opposite_direction_pair([self.c("team_totals", "Over", 21.5, "Test Home"), self.c("team_totals", "Under", 21.5, "Test Away")]))
        self.assertIsNone(W.opposite_direction_pair([self.c("h2h", "Test Home", None), self.c("spreads", "Test Away", 2.5)]))   # ML against a spread
        self.assertIsNone(W.opposite_direction_pair([self.c("spreads", "Test Home", -3.5), self.c("spreads", "Test Home", -6.5)]))
        self.assertIsNone(W.opposite_direction_pair([]))
        self.assertIsNone(W.opposite_direction_pair([base]))

    def test_first_clash_in_a_longer_list_is_named(self):
        a, t, b = self.c("spreads", "Test Home", -3.5), self.c("totals", "Over", 45.5), self.c("spreads", "Test Away", 2.5)
        self.assertEqual(W.opposite_direction_pair([a, t, b]), (a, b))


class TestOppositeDirection(SameGame):
    """The release decision for formal picks, through submit_review and publish on a capture that carries real thresholds."""

    def lines_capture(self):
        path = self.add_detailed()
        doc = json.loads(path.read_text())
        upd = "2026-11-15T07:48:00Z"
        for e in doc["event_odds"]:
            home, away = e["home_team"], e["away_team"]
            e["bookmakers"].append(dict(key="betmgm", title="BetMGM", last_update=upd, markets=[
                dict(key="player_rush_yds", last_update=upd, outcomes=[
                    dict(name="Over", description="Test Runner", point=22.5, price=-110),
                    dict(name="Under", description="Test Runner", point=24.5, price=-110)]),
                dict(key="player_reception_yds", last_update=upd, outcomes=[
                    dict(name="Over", description="Other Receiver", point=40.5, price=-110),
                    dict(name="Under", description="Other Receiver", point=41.5, price=-110)]),
                dict(key="totals", last_update=upd, outcomes=[
                    dict(name="Over", point=45.5, price=-110), dict(name="Under", point=47.5, price=-110)]),
                dict(key="spreads", last_update=upd, outcomes=[
                    dict(name=home, point=-3.5, price=-110), dict(name=away, point=2.5, price=-110)]),
            ]))
        path.write_text(json.dumps(doc, sort_keys=True))
        return doc

    def setUp(self):
        super().setUp()
        doc = self.lines_capture()
        self.scr0 = self.scr()
        # the game under test needs both moneylines inside the price band (some real favourites are not), so pick one that has them
        for e in doc["event_odds"]:
            for w in self.scr0["windows"]:
                for g in w["games"]:
                    ml = [c for c in g["contracts"] if c["market"] == "h2h" and c["reviewable"]]
                    if g["event_id"] == e["id"] and len(ml) == 2:
                        self.eid, self.home, self.away, self.win = e["id"], e["home_team"], e["away_team"], w["name"]
                        return
        self.fail("no detailed game with both moneylines in band")

    def find(self, **want):
        for w in self.scr0["windows"]:
            for g in w["games"]:
                if g["event_id"] != self.eid:
                    continue
                for c in g["contracts"]:
                    if c["reviewable"] and c["best_in_band"] and all(c.get(k) == v for k, v in want.items()):
                        return c
        self.fail("no reviewable contract %r in the test game" % (want,))

    def submit(self, *cs):
        return W.submit_review(DAY, self.payload(self.scr0, {self.win: {"decision": "calls"}}, [self.call(c) for c in cs]))

    def clash(self, a, b, *words):
        e = self.refused("OPPOSITE_DIRECTION", self.submit, a, b)
        for s in (a["label"], b["label"], "Still allowed together") + words:
            self.assertIn(s, e.detail)
        self.refused("OPPOSITE_DIRECTION", self.submit, b, a)            # order does not matter
        self.assertEqual(W.list_reviews(DAY)["rows"], [])                # nothing was written
        return e

    def test_player_prop_over_and_under_at_different_lines_is_refused(self):
        o = self.find(market="player_rush_yds", subject="Test Runner", side="Over", point=22.5)
        u = self.find(market="player_rush_yds", subject="Test Runner", side="Under", point=24.5)
        self.clash(o, u, "player_rush_yds", "Test Runner", "full game")

    def test_game_total_over_and_under_at_different_lines_is_refused(self):
        self.clash(self.find(market="totals", side="Over", point=45.5), self.find(market="totals", side="Under", point=47.5), "totals")

    def test_spread_and_moneyline_for_opposing_teams_are_refused(self):
        self.clash(self.find(market="spreads", side=self.home, point=-3.5), self.find(market="spreads", side=self.away, point=2.5), "spreads")
        self.clash(self.find(market="h2h", side=self.home), self.find(market="h2h", side=self.away), "h2h")

    def test_first_half_and_team_total_clashes_are_refused(self):
        self.clash(self.find(market="spreads_h1", side=self.home, point=-3.5), self.find(market="spreads_h1", side=self.away, point=3.5),
                   "spreads_h1", "first half")
        self.clash(self.find(market="team_totals", subject=self.home, side="Over"), self.find(market="team_totals", subject=self.home, side="Under"),
                   "team_totals", self.home)

    def test_distinct_independent_markets_stay_allowed_and_are_annotated(self):
        rush_o = self.find(market="player_rush_yds", subject="Test Runner", side="Over", point=22.5)
        cases = (
            ("same direction, other line", rush_o, self.find(market="player_rush_yds", subject="Test Runner", side="Over", point=64.5), "same_market_other_line"),
            ("moneyline and a spread on the other team", self.find(market="h2h", side=self.home),
             self.find(market="spreads", side=self.away, point=2.5), "different_markets"),
            ("full-game total and the first-half total in the other direction", self.find(market="totals", side="Over", point=45.5),
             self.find(market="totals_h1", side="Under"), "different_markets"),
            ("two different players", self.find(market="player_reception_yds", subject="Test Receiver", side="Over"),
             self.find(market="player_reception_yds", subject="Other Receiver", side="Under", point=41.5), "same_market_other_subject"),
            ("team totals for the two different teams", self.find(market="team_totals", subject=self.home, side="Over"),
             self.find(market="team_totals", subject=self.away, side="Under"), "same_market_other_subject"),
        )
        for name, a, b, relation in cases:
            with self.subTest(name):
                self.now = self.now + timedelta(minutes=1)
                r = self.submit(a, b)
                self.assertEqual(len(r["rows"][0]["calls"]), 2)
                sunday = json.loads(Path(W.publish(DAY)["sunday_card_path"]).read_text())
                self.assertEqual(len(sunday["calls"]), 2)
                for c in sunday["calls"]:
                    sh = c["shared_event"]
                    self.assertEqual([o["relation"] for o in sh["others"]], [relation])
                    self.assertTrue(sh["note"].startswith("Correlated: 2 calls on this card are in the same game"))
                    self.assertNotIn("opposite sides", sh["note"])

    def test_refusal_order_is_duplicate_then_opposite_then_window_limit(self):
        o = self.find(market="player_rush_yds", subject="Test Runner", side="Over", point=22.5)
        u = self.find(market="player_rush_yds", subject="Test Runner", side="Under", point=24.5)
        tot = self.find(market="totals", side="Over", point=45.5)
        ml = self.find(market="h2h", side=self.home)
        self.refused("DUPLICATE_CONTRACT", self.submit, o, o, u)
        self.refused("OPPOSITE_DIRECTION", self.submit, o, u, tot)       # three calls, but the direction clash is what to fix
        self.refused("OPPOSITE_DIRECTION", self.submit, o, tot, u)
        self.refused("WINDOW_LIMIT", self.submit, o, tot, ml)            # three calls with no clash is still the count limit
        self.assertEqual(W.list_reviews(DAY)["rows"], [])

    def test_a_refused_revision_leaves_the_active_row_and_card_alone(self):
        o = self.find(market="player_rush_yds", subject="Test Runner", side="Over", point=22.5)
        u = self.find(market="player_rush_yds", subject="Test Runner", side="Under", point=24.5)
        tot = self.find(market="totals", side="Over", point=45.5)
        self.submit(tot, o)
        head = W.verify(DAY)
        before = W.publish(DAY)
        self.now = self.now + timedelta(minutes=1)
        self.refused("OPPOSITE_DIRECTION", self.submit, o, u)
        self.assertEqual(W.verify(DAY), head)
        self.assertEqual(W.current_card(DAY)["sunday_card_sha256"], before["sunday_card_sha256"])

    def test_annotations_may_cover_both_directions_because_they_are_not_calls(self):
        o = self.find(market="player_rush_yds", subject="Test Runner", side="Over", point=22.5)
        u = self.find(market="player_rush_yds", subject="Test Runner", side="Under", point=24.5)
        for c in (o, u):
            r = W.annotate(DAY, dict(api="weekly/1", date=DAY, author_kind="codex", author="red team", stance="concern",
                                     text="Looked at both directions.", scope=dict(contract_id=c["id"])))
            self.assertIs(r["row"]["changes_calls"], False)

    def test_publish_refuses_a_row_written_before_the_rule(self):
        o = self.find(market="player_rush_yds", subject="Test Runner", side="Over", point=22.5)
        u = self.find(market="player_rush_yds", subject="Test Runner", side="Under", point=24.5)
        real = W.opposite_direction_pair
        W.opposite_direction_pair = lambda calls: None                   # what an older engine accepted
        try:
            self.submit(o, u)
        finally:
            W.opposite_direction_pair = real
        e = self.refused("OPPOSITE_DIRECTION", W.publish, DAY)
        self.assertIn("Resubmit", e.detail)
        self.now = self.now + timedelta(minutes=1)
        self.submit(o)                                                    # one direction supersedes the window
        sunday = json.loads(Path(W.publish(DAY)["sunday_card_path"]).read_text())
        self.assertEqual([c["side"] for c in sunday["calls"]], ["Over"])


class TestAnnotations(SameGame):
    def ann(self, **kw):
        d = dict(api="weekly/1", date=DAY, author_kind="codex", author="red team", stance="concern",
                 text="The total depends on one weather read.", sources=["https://www.espn.com/nfl/scoreboard"])
        d.update(kw)
        return d

    def test_author_kind_is_required_and_never_defaulted(self):
        for bad in (None, "", "Human", "user", "matthew", 7):
            p = self.ann()
            if bad is None:
                p.pop("author_kind")
            else:
                p["author_kind"] = bad
            self.refused("BAD_AUTHOR_KIND", W.annotate, DAY, p)
        for kind in ("human", "claude", "codex", "other"):
            r = W.annotate(DAY, self.ann(author_kind=kind, text="note from %s" % kind))
            self.assertEqual(r["row"]["author_kind"], kind)
            self.assertIs(r["row"]["is_review"], False)
            self.assertIs(r["row"]["changes_calls"], False)
        self.assertEqual(W.verify_annotations(DAY)["rows"], 4)

    def test_shape_refusals(self):
        scr = self.scr()
        c = self.pick(scr, "early")[1]
        self.refused("BAD_STANCE", W.annotate, DAY, self.ann(stance="approve"))
        self.refused("BAD_STANCE", W.annotate, DAY, self.ann(stance=None))
        self.refused("INCOMPLETE_FIELD", W.annotate, DAY, self.ann(text="  "))
        self.refused("INCOMPLETE_FIELD", W.annotate, DAY, self.ann(text="x" * 4001))
        self.refused("INCOMPLETE_FIELD", W.annotate, DAY, self.ann(author="a" * 81))
        self.refused("INCOMPLETE_FIELD", W.annotate, DAY, self.ann(sources=["http://insecure.example/x"]))
        self.refused("INCOMPLETE_FIELD", W.annotate, DAY, self.ann(sources=["https://x.example/p?api_key=abc"]))
        self.refused("BAD_SCOPE", W.annotate, DAY, self.ann(scope=dict(game="x")))
        self.refused("BAD_SCOPE", W.annotate, DAY, self.ann(scope=dict(window="noon")))
        self.refused("BAD_SCOPE", W.annotate, DAY, self.ann(scope="early"))
        self.refused("BAD_SCOPE", W.annotate, DAY, self.ann(scope=dict(window="late", contract_id=c["id"])))
        self.refused("UNKNOWN_CONTRACT", W.annotate, DAY, self.ann(scope=dict(contract_id="nope:nope")))
        self.refused("BAD_PAYLOAD", W.annotate, DAY, self.ann(date="2026-11-29"))
        self.refused("BAD_PAYLOAD", W.annotate, DAY, self.ann(api="weekly/2"))
        self.refused("BAD_PAYLOAD", W.annotate, DAY, ["not", "an", "object"])
        self.refused("BAD_DATE", W.annotate, "2026-11-15", self.ann(date="2026-11-15"))
        self.refused("EDITION_UNKNOWN", W.annotate, DAY, self.ann(edition=dict(captured_utc="2026-11-15T07:34:18Z", sha256="0" * 64)))
        self.assertEqual(W.verify_annotations(DAY)["rows"], 0)           # nothing was written by any refusal
        # scope may be omitted (whole week/date), or hold a window, or a contract id
        W.annotate(DAY, self.ann(text="whole date"))
        W.annotate(DAY, self.ann(text="window", scope=dict(window="early")))
        W.annotate(DAY, self.ann(text="contract", scope=dict(contract_id=c["id"])))
        self.assertEqual(W.verify_annotations(DAY)["rows"], 3)

    def test_chain_dedup_and_tamper(self):
        r1 = W.annotate(DAY, self.ann(text="first"))
        again = W.annotate(DAY, self.ann(text="first"))
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["row"]["sha256"], r1["row"]["sha256"])
        r2 = W.annotate(DAY, self.ann(text="second", author_kind="claude"))
        self.assertEqual((r1["row"]["seq"], r2["row"]["seq"]), (1, 2))
        self.assertEqual(r2["row"]["prev_sha256"], r1["row"]["sha256"])
        self.assertEqual(W.verify_annotations(DAY)["head_sha256"], r2["row"]["sha256"])
        self.assertEqual(W.list_annotations(DAY)["chain_ok"], True)
        path = W.ANNOTATIONS / DAY / "annotations.jsonl"
        lines = path.read_text().splitlines()
        row = json.loads(lines[0])
        row["author_kind"] = "human"                                    # relabel a Claude/Codex note as human
        lines[0] = json.dumps(row, sort_keys=True)
        path.write_text("\n".join(lines) + "\n")
        self.refused("CHAIN_BROKEN", W.verify_annotations, DAY)
        self.assertFalse(W.list_annotations(DAY)["chain_ok"])
        self.refused("CHAIN_BROKEN", W.annotate, DAY, self.ann(text="third"))

    def test_received_after_kickoff_is_labelled(self):
        scr = self.scr()
        first = min(self.kick(g["kickoff_utc"]) for w in scr["windows"] if w["name"] == "early" for g in w["games"])
        r = W.annotate(DAY, self.ann(text="before", scope=dict(window="early")))
        self.assertIs(r["row"]["received_after_kickoff"], False)
        self.assertEqual(r["warnings"], [])
        self.now = first + timedelta(minutes=10)
        r = W.annotate(DAY, self.ann(text="after", scope=dict(window="early")))
        self.assertIs(r["row"]["received_after_kickoff"], True)
        self.assertTrue(r["warnings"])
        late = W.annotate(DAY, self.ann(text="late window is still open", scope=dict(window="late")))
        self.assertIs(late["row"]["received_after_kickoff"], False)

    def test_an_annotation_is_not_a_review_and_changes_no_call(self):
        scr, g, m = self.game_with("early", "spreads", "totals")
        side = m["spreads"][0]
        W.submit_review(DAY, self.payload(scr, {"early": {"decision": "calls"}}, [self.call(side)]))
        first = W.publish(DAY)
        sunday_before = Path(first["sunday_card_path"]).read_bytes()
        reviews_before = Path(W.REVIEWS / DAY / "reviews.jsonl").read_bytes()
        r = W.annotate(DAY, self.ann(text="Counter: price already moved.", scope=dict(contract_id=side["id"])))
        self.assertEqual(Path(W.REVIEWS / DAY / "reviews.jsonl").read_bytes(), reviews_before)
        self.assertEqual(W.list_reviews(DAY)["rows"][0]["author_kind"], "unspecified")
        again = W.publish(DAY)                                          # same pinned clock: history files must not collide
        self.assertFalse(again["unchanged"])
        self.assertEqual(Path(again["sunday_card_path"]).read_bytes(), sunday_before)       # the card the PDF reads is unchanged
        self.assertEqual(json.loads(Path(again["sunday_card_path"]).read_text())["calls"][0]["label"], side["label"])
        self.assertNotIn("annotation", Path(again["sunday_card_path"]).read_text())
        full = json.loads(Path(again["card_path"]).read_text())
        self.assertEqual([a["row_id"] for a in full["annotations"]], [r["row"]["row_id"]])
        self.assertEqual(full["annotations"][0]["author_kind"], "codex")
        self.assertIs(full["annotations"][0]["is_review"], False)
        self.assertEqual(full["annotation_head_sha256"], r["row"]["sha256"])
        self.assertIn("not the reviewer's decision", full["annotations_note"])
        call = full["windows"][0]["calls"][0]
        self.assertEqual(call["annotation_rows"], [r["row"]["row_id"]])
        self.assertEqual(full["summary"]["annotations"], 1)
        self.assertEqual(W.publish(DAY)["unchanged"], True)             # and republishing again is idempotent

    def test_window_scoped_note_and_review_author_kind_on_the_card(self):
        scr = self.scr()
        c = self.pick(scr, "early")[1]
        p = self.payload(scr, {"early": {"decision": "calls"}, "night": {"decision": "no_play", "note": "pass"}}, [self.call(c)],
                         author="Matthew", author_kind="human")
        W.submit_review(DAY, p)
        a_win = W.annotate(DAY, self.ann(text="Night: agree with the pass.", stance="supports", scope=dict(window="night"), author_kind="claude"))
        a_all = W.annotate(DAY, self.ann(text="Whole-date note.", stance="info"))
        full = json.loads(Path(W.publish(DAY)["card_path"]).read_text())
        wins = {w["name"]: w for w in full["windows"]}
        self.assertEqual(wins["night"]["annotation_rows"], [a_win["row"]["row_id"]])
        self.assertEqual(wins["early"]["annotation_rows"], [])
        self.assertEqual((wins["early"]["review_author"], wins["early"]["review_author_kind"]), ("Matthew", "human"))
        self.assertEqual(wins["night"]["review_author_kind"], "human")
        self.assertEqual({a["row_id"] for a in full["annotations"]}, {a_win["row"]["row_id"], a_all["row"]["row_id"]})
        self.assertEqual({a["author_kind"] for a in full["annotations"]}, {"claude", "codex"})

    def test_review_without_author_kind_is_unspecified_never_human(self):
        scr, pay, calls = self.basic_review()
        pay.pop("author_kind", None)
        r = W.submit_review(DAY, pay)
        self.assertEqual({x["author_kind"] for x in r["rows"]}, {"unspecified"})
        full = json.loads(Path(W.publish(DAY)["card_path"]).read_text())
        self.assertEqual({w["review_author_kind"] for w in full["windows"] if "review_author_kind" in w}, {"unspecified"})
        bad = copy.deepcopy(pay)
        bad["author_kind"] = "Matthew"
        self.refused("BAD_AUTHOR_KIND", W.submit_review, DAY, bad)
        # the kind is part of the review's identity: the same body filed as human is a new row, not a duplicate
        other = copy.deepcopy(pay)
        other["author_kind"] = "human"
        r2 = W.submit_review(DAY, other)
        self.assertFalse(r2["duplicate"])



class TestCli(Base):
    def run_cli(self, *argv, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        old_in = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = W.main(["--inputs", str(self.inputs), "--work", str(self.work)] + list(argv))
        finally:
            sys.stdin = old_in
        return code, (json.loads(out.getvalue()) if out.getvalue().strip() else None), err.getvalue()

    def test_full_cli_flow_and_exit_codes(self):
        code, d, _ = self.run_cli("dates")
        self.assertEqual((code, d["ok"]), (0, True))
        code, s, _ = self.run_cli("screen", DAY, "--window", "early", "--market", "spreads", "--band-only")
        self.assertEqual(code, 0)
        self.assertEqual([w["name"] for w in s["windows"]], ["early"])
        W.clock = lambda: self.now
        _, ce = self.pick(s, "early")
        _, cl = self.pick(self.scr(), "late")
        pay = self.payload(s, {"early": {"decision": "calls"}, "late": {"decision": "calls"}}, [self.call(ce), self.call(cl)])
        pfile = self.tmp / "payload.json"
        pfile.write_text(json.dumps(pay))
        code, r, _ = self.run_cli("review", "submit", DAY, "--payload", str(pfile))
        self.assertEqual((code, r["ok"], len(r["rows"])), (0, True, 2))
        code, r, _ = self.run_cli("review", "submit", DAY, "--payload", "-", stdin=json.dumps(pay))
        self.assertEqual((code, r["duplicate"]), (0, True))
        code, v, _ = self.run_cli("review", "verify", DAY)
        self.assertEqual((code, v["rows"]), (0, 2))
        code, lst, _ = self.run_cli("review", "list", DAY)
        self.assertEqual((code, lst["chain_ok"]), (0, True))
        code, p, _ = self.run_cli("publish", DAY)
        self.assertEqual((code, p["unchanged"]), (0, False))
        code, c, _ = self.run_cli("card", DAY)
        self.assertEqual(code, 0)
        self.assertEqual(len(c["sunday_card"]["calls"]), 2)
        self.assertTrue(str(p["sunday_card_path"]).startswith(str(self.work.resolve())))

    def test_cli_annotate_flow(self):
        ann = dict(api="weekly/1", date=DAY, author_kind="codex", author="red team", stance="concern", text="One weather read.")
        pfile = self.tmp / "ann.json"
        pfile.write_text(json.dumps(ann))
        code, r, _ = self.run_cli("annotate", "submit", DAY, "--payload", str(pfile))
        self.assertEqual((code, r["ok"], r["duplicate"]), (0, True, False))
        code, r, _ = self.run_cli("annotate", "submit", DAY, "--payload", "-", stdin=json.dumps(ann))
        self.assertEqual((code, r["duplicate"]), (0, True))
        code, r, _ = self.run_cli("annotate", "list", DAY)
        self.assertEqual((code, len(r["rows"]), r["chain_ok"]), (0, 1, True))
        code, r, _ = self.run_cli("annotate", "verify", DAY)
        self.assertEqual((code, r["rows"]), (0, 1))
        code, r, err = self.run_cli("annotate", "submit", DAY, "--payload", "-", stdin=json.dumps(dict(ann, author_kind="boss")))
        self.assertEqual((code, r["code"]), (1, "BAD_AUTHOR_KIND"))
        self.assertIn("REFUSED BAD_AUTHOR_KIND", err)
        self.assertTrue((self.work / "annotations" / DAY / "annotations.jsonl").is_file())    # --work moved it, as for reviews

    def test_refusals_exit_1_with_a_code(self):
        code, d, err = self.run_cli("screen", "2026-11-15")
        self.assertEqual(code, 1)
        self.assertEqual((d["ok"], d["code"]), (False, "BAD_DATE"))
        self.assertIn("REFUSED BAD_DATE", err)
        code, d, _ = self.run_cli("card", DAY)
        self.assertEqual((code, d["code"]), (1, "NO_CARD"))
        code, d, _ = self.run_cli("review", "submit", DAY, "--payload", str(self.tmp / "missing.json"))
        self.assertEqual((code, d["code"]), (1, "BAD_PAYLOAD"))
        code, d, _ = self.run_cli("review", "submit", DAY, "--payload", "-", stdin="not json")
        self.assertEqual((code, d["code"]), (1, "BAD_PAYLOAD"))

    def test_usage_errors_exit_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                W.main(["--inputs", str(self.inputs), "bogus"])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
