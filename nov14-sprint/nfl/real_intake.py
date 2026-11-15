#!/usr/bin/env python3
"""Real-data intake for the NFL paper ledger. PAPER ONLY.

Reads two JSON captures (untrusted data, never executed):
  --scoreboard  real games, teams, kickoff times and final scores. No prices.
  --lines       public ESPN display of sportsbook prices for the same games.

Writes into --out-dir (default: nfl/real/):
  weekNN_games.csv        every real game, with source URL and retrieval time
  weekNN_finals.csv       finals only, in the shape that
                          `paper_ledger.py settle --results-file` reads
  weekNN_prices.csv       every real price observation, with URL and time
  weekNN_rule_scores.csv  each frozen rule on each real game: the decision at
                          the real line, the real price, and the score status
  REAL_WEEKNN.md          the same in plain English
  INTAKE_RECEIPT.json     input hashes, counts and the run time

With --apply it also writes to the ledger, only through paper_ledger.py:
  * each real price is recorded on the ledger pick with the identical
    contract (same game, rule, side and line) as a price observation that is
    NOT a closing line (`close --not-a-close`);
  * the real finals file is given to `settle`.

Rules this script keeps:
  * It never invents a price or a line. A rule row with no real price
    observation at its exact line is marked "no price, not scored".
  * A price for one line is never attached to a pick at another line.
  * Every output row carries the source URL and the retrieval time.
  * Rest days come from the nflverse schedule file (a schedule fact).

Standard library only, Python 3.9. Run with:
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I real_intake.py ...
"""

import argparse
import contextlib
import csv
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import paper_ledger as pl  # noqa: E402
import rules  # noqa: E402

MAX_INPUT_BYTES = 2 * 1024 * 1024
NO_PRICE = "no price, not scored"
NO_SIDE = "rule has no side here, nothing to price"
AWAITING = "real price recorded, awaiting final"
SCORED = "scored at the real price"
UNMATCHED = "game not matched to the schedule file, not scored"

# Scoreboard abbreviations that differ from the nflverse ones.
ABBR_FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "LVR": "LV",
            "NOS": "NO", "NEP": "NE", "GNB": "GB", "KAN": "KC", "SFO": "SF",
            "TAM": "TB"}

FULL_NAME = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET",
    "Green Bay Packers": "GB", "Houston Texans": "HOU",
    "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA",
    "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO",
    "New York Giants": "NYG", "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}

TS_LOOSE = re.compile(
    r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::(\d{2}))?(?:\.\d+)?"
    r"(?:Z|\+00:00)")
PRICE_RE = re.compile(r"[+-]?\d{3,5}")
HANDICAP_RE = re.compile(r"[+-]?\d{1,2}(?:\.5)?")
TOTAL_RE = re.compile(r"([ou])(\d{1,3}(?:\.5)?)")


class IntakeError(Exception):
    pass


def say(msg=""):
    sys.stdout.write(msg + "\n")


def text_of(value, limit=300):
    """Untrusted value -> short printable text. Never evaluated."""
    if value is None:
        return ""
    return pl.clean(str(value))[:limit]


def url_of(value):
    """Keep only a plain https URL, else ''."""
    text = text_of(value, 400)
    if text.startswith("https://") and " " not in text and "?" != text[-1:]:
        return text
    return ""


def norm_ts(value):
    """Loose UTC ISO text -> strict 'YYYY-MM-DDTHH:MM:SSZ', or None."""
    if not isinstance(value, str):
        return None
    m = TS_LOOSE.fullmatch(value.strip())
    if not m:
        return None
    strict = "%sT%s:%sZ" % (m.group(1), m.group(2), m.group(3) or "00")
    return strict if pl.parse_ts(strict) is not None else None


def read_json(path, what):
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise IntakeError("cannot read %s (%s): %s" % (what, path, exc))
    if len(data) > MAX_INPUT_BYTES:
        raise IntakeError("%s is larger than %d bytes" % (what,
                                                           MAX_INPUT_BYTES))
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise IntakeError("%s is not valid UTF-8 JSON: %s" % (what, exc))
    if not isinstance(doc, dict):
        raise IntakeError("%s is not a JSON object" % what)
    return doc, hashlib.sha256(data).hexdigest(), len(data)


def score_of(value):
    """A final score must be a plain int from 0 to 200, else None."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 0 <= value <= 200 else None


def price_of(value):
    """'+124' / '-118' / 'EVEN' -> int American price, else None."""
    text = text_of(value, 12).strip()
    if text.upper() in ("EVEN", "EV"):
        return 100
    if not PRICE_RE.fullmatch(text):
        return None
    price = int(text)
    return price if abs(price) >= 100 else None


def num_text(x):
    return "" if x is None else "%g" % x


def price_text(p):
    return "" if p is None else "%+d" % p


# --- the two untrusted inputs ----------------------------------------------
def load_scoreboard(path):
    doc, sha, nbytes = read_json(path, "scoreboard file")
    meta = {
        "path": os.path.abspath(path), "sha256": sha, "bytes": nbytes,
        "source": text_of(doc.get("source")),
        "source_url": url_of(doc.get("source_page")),
        "retrieved_at_utc": norm_ts(doc.get("captured_at")),
        "retrieved_at_raw": text_of(doc.get("captured_at"), 40),
    }
    if meta["retrieved_at_utc"] is None:
        raise IntakeError("scoreboard file has no usable captured_at time")
    if not meta["source_url"]:
        raise IntakeError("scoreboard file has no https source_page")
    games = doc.get("games")
    if not isinstance(games, list) or not games or len(games) > 64:
        raise IntakeError("scoreboard file has no usable games list")
    rows = []
    for i, g in enumerate(games, 1):
        if not isinstance(g, dict) or not isinstance(g.get("teams"), list):
            raise IntakeError("scoreboard game %d is malformed" % i)
        home = [t for t in g["teams"] if isinstance(t, dict)
                and t.get("home") is True]
        away = [t for t in g["teams"] if isinstance(t, dict)
                and t.get("home") is False]
        if len(home) != 1 or len(away) != 1 or len(g["teams"]) != 2:
            raise IntakeError("scoreboard game %d needs one home and one "
                              "away team" % i)
        def abbr(t):
            raw = text_of(t.get("team"), 6).upper()
            return ABBR_FIX.get(raw, raw)
        rows.append({
            "provider_event_id": text_of(g.get("provider_event_id"), 40),
            "kickoff_utc": norm_ts(g.get("kickoff_utc")),
            "status": text_of(g.get("status"), 40),
            "home_team": abbr(home[0]), "away_team": abbr(away[0]),
            "home_name": text_of(home[0].get("name"), 40),
            "away_name": text_of(away[0].get("name"), 40),
            "home_score": score_of(home[0].get("score")),
            "away_score": score_of(away[0].get("score")),
            "home_score_raw": home[0].get("score"),
            "away_score_raw": away[0].get("score"),
        })
    return meta, rows


def load_lines(path):
    doc, sha, nbytes = read_json(path, "public lines file")
    meta = {"path": os.path.abspath(path), "sha256": sha, "bytes": nbytes,
            "price_note": text_of(doc.get("price_note"), 400)}
    games = doc.get("games")
    if not isinstance(games, list) or len(games) > 64:
        raise IntakeError("public lines file has no usable games list")
    rows = []
    for i, g in enumerate(games, 1):
        if not isinstance(g, dict) or not isinstance(g.get("teams"), dict):
            raise IntakeError("public lines game %d is malformed" % i)
        home = FULL_NAME.get(text_of(g["teams"].get("home"), 60))
        away = FULL_NAME.get(text_of(g["teams"].get("away"), 60))
        final = g.get("final_score")
        fh = fa = None
        if isinstance(final, dict):
            fh, fa = score_of(final.get("home")), score_of(final.get("away"))
        obs = []
        refs = g.get("book_references")
        for ref in (refs if isinstance(refs, list) else []):
            if not isinstance(ref, dict):
                continue
            observed = norm_ts(ref.get("observed_utc"))
            markets = ref.get("markets")
            for m in (markets if isinstance(markets, list) else []):
                if not isinstance(m, dict):
                    continue
                obs.append({
                    "book": text_of(ref.get("book"), 40),
                    "observed_utc": observed,
                    "book_updated_utc": norm_ts(ref.get("book_updated_utc")),
                    "local_availability_verified":
                        ref.get("local_availability_verified") is True,
                    "market": text_of(m.get("market"), 20),
                    "side": text_of(m.get("side"), 10),
                    "line_raw": text_of(m.get("line"), 12),
                    "price": price_of(m.get("american_price")),
                    "price_raw": text_of(m.get("american_price"), 12),
                })
        rows.append({
            "event_id": text_of(g.get("event_id"), 40),
            "home_team": home, "away_team": away,
            "kickoff_utc": norm_ts(g.get("kickoff_utc")),
            "state": text_of(g.get("state"), 40),
            "final_home": fh, "final_away": fa,
            "source_url": url_of(g.get("source_url")),
            "event_url": url_of(g.get("event_url")),
            "observations": obs,
        })
    return meta, rows


# --- real prices for one game ----------------------------------------------
def real_market(line_game):
    """Turn one game's observations into the rule inputs.

    Returns (market dict or None, reason). The market dict holds the real
    spread in the nflverse convention (home favored positive), the real
    total, each side's real price, the book, the observation time and URL.
    Anything inconsistent returns None with the reason: no number is guessed.
    """
    if line_game is None:
        return None, "no entry in the public lines file"
    books = sorted(set(o["book"] for o in line_game["observations"]))
    if not books:
        return None, "the source holds no price for this game"
    if len(books) != 1:
        return None, "more than one book listed; none chosen"
    obs = line_game["observations"]
    times = set(o["observed_utc"] for o in obs)
    if len(times) != 1 or None in times:
        return None, "price observation time missing or mixed"
    if not line_game["source_url"]:
        return None, "price rows have no https source URL"
    found = {}
    for o in obs:
        key = (o["market"], o["side"])
        if key in found:
            return None, "repeated %s %s row" % key
        found[key] = o
    out = {"book": books[0], "observed_utc": times.pop(),
           "source_url": line_game["source_url"],
           "local_availability_verified":
               all(o["local_availability_verified"] for o in obs),
           "spread_line": None, "total_line": None, "price": {}}
    sp_a, sp_h = found.get(("pointSpread", "away")), found.get(
        ("pointSpread", "home"))
    if sp_a and sp_h and HANDICAP_RE.fullmatch(sp_a["line_raw"]) and \
            HANDICAP_RE.fullmatch(sp_h["line_raw"]) and \
            sp_a["price"] is not None and sp_h["price"] is not None:
        a, h = float(sp_a["line_raw"]), float(sp_h["line_raw"])
        if a == -h:
            # away handicap +2.5 means the home team is favored by 2.5
            out["spread_line"] = a
            out["price"]["spread", "away"] = sp_a["price"]
            out["price"]["spread", "home"] = sp_h["price"]
    t_o, t_u = found.get(("total", "over")), found.get(("total", "under"))
    if t_o and t_u and t_o["price"] is not None and t_u["price"] is not None:
        mo, mu = TOTAL_RE.fullmatch(t_o["line_raw"]), TOTAL_RE.fullmatch(
            t_u["line_raw"])
        if mo and mu and mo.group(1) == "o" and mu.group(1) == "u" and \
                mo.group(2) == mu.group(2):
            out["total_line"] = float(mo.group(2))
            out["price"]["total", "over"] = t_o["price"]
            out["price"]["total", "under"] = t_u["price"]
    return out, ""


def ledger_rule_rows(ledger_dir):
    """(game_id, rule_version) -> rule-generated ledger entry."""
    entries = pl.load_jsonl(pl.Paths(ledger_dir).ledger)
    index = {}
    for e in entries:
        if e.get("entered_by") == "rule" and not e.get("fixture"):
            index[(e.get("game_id"), e.get("rule_version"))] = e
    return index


def build(args):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if args.now:
        # tests only; main() refuses it on the real ledger or real out dir
        now = pl.parse_ts(args.now)
        if now is None:
            raise IntakeError("--now is not a UTC timestamp")
    sb_meta, sb_games = load_scoreboard(args.scoreboard)
    ln_meta, ln_games = load_lines(args.lines)
    retrieved = pl.parse_ts(sb_meta["retrieved_at_utc"])
    if retrieved > now:
        raise IntakeError("scoreboard capture time is in the future")
    inputs = pl.load_inputs()
    frozen = pl.load_frozen(pl.DEFAULT_FROZEN, now)
    sched = {}
    for g in inputs.games:
        if g["kickoff"] is not None:
            sched[(g["away_team"], g["home_team"],
                   pl.fmt_ts(g["kickoff"]))] = g
    lines_by_key = {}
    for lg in ln_games:
        lines_by_key[(lg["away_team"], lg["home_team"],
                      lg["kickoff_utc"])] = lg
    ledger = ledger_rule_rows(args.ledger_dir)

    games_out, finals_out, prices_out, score_out, notes = [], [], [], [], []
    weeks = set()
    for sg in sb_games:
        key = (sg["away_team"], sg["home_team"], sg["kickoff_utc"])
        ng = sched.get(key)
        lg = lines_by_key.get(key)
        game_id = ng["game_id"] if ng else ""
        if ng:
            weeks.add((ng["season"], ng["week"]))
        kickoff = pl.parse_ts(sg["kickoff_utc"] or "")
        # A final needs the official status, two plain int scores, and a
        # capture taken after kickoff.
        is_final = (sg["status"] == "ScoresOfficial"
                    and sg["home_score"] is not None
                    and sg["away_score"] is not None
                    and kickoff is not None and retrieved > kickoff)
        final_note = ""
        if is_final and lg is not None and lg["final_home"] is not None and (
                lg["final_home"] != sg["home_score"]
                or lg["final_away"] != sg["away_score"]):
            is_final = False
            final_note = ("the two sources disagree on the final (%s-%s vs "
                          "%s-%s); not used" % (
                              sg["away_score"], sg["home_score"],
                              lg["final_away"], lg["final_home"]))
            notes.append("%s: %s" % (game_id or "%s@%s" % key[:2],
                                     final_note))
        if not ng:
            notes.append("%s@%s kickoff %s is not in the schedule file; "
                         "kept in the games list, not scored"
                         % (sg["away_team"], sg["home_team"],
                            sg["kickoff_utc"]))
        market, why_no_price = real_market(lg)
        games_out.append({
            "game_id": game_id, "away_team": sg["away_team"],
            "home_team": sg["home_team"], "away_name": sg["away_name"],
            "home_name": sg["home_name"], "kickoff_utc": sg["kickoff_utc"],
            "status": sg["status"],
            "away_score": num_text(sg["away_score"]) if is_final else "",
            "home_score": num_text(sg["home_score"]) if is_final else "",
            "final": "yes" if is_final else "no",
            "schedule_match": "yes" if ng else "no",
            "real_price_available": "yes" if market else "no",
            "provider_event_id": sg["provider_event_id"],
            "source": sb_meta["source"], "source_url": sb_meta["source_url"],
            "retrieved_at_utc": sb_meta["retrieved_at_utc"],
            "source_file_sha256": sb_meta["sha256"], "note": final_note,
        })
        if is_final and ng:
            finals_out.append({
                "game_id": game_id, "home_team": sg["home_team"],
                "away_team": sg["away_team"],
                "home_score": sg["home_score"],
                "away_score": sg["away_score"],
                "source": sb_meta["source"],
                "source_url": sb_meta["source_url"],
                "retrieved_at_utc": sb_meta["retrieved_at_utc"],
                "provider_event_id": sg["provider_event_id"],
                "status": sg["status"],
            })
        if lg is not None:
            for o in lg["observations"]:
                prices_out.append({
                    "game_id": game_id, "away_team": sg["away_team"],
                    "home_team": sg["home_team"],
                    "kickoff_utc": sg["kickoff_utc"], "book": o["book"],
                    "market": o["market"], "side": o["side"],
                    "line_as_shown": o["line_raw"],
                    "price_american": price_text(o["price"]),
                    "price_as_shown": o["price_raw"],
                    "observed_utc": o["observed_utc"] or "",
                    "book_updated_utc": o["book_updated_utc"] or "unknown",
                    "local_availability_verified":
                        "yes" if o["local_availability_verified"] else "no",
                    "source": "%s via ESPN public scoreboard display"
                              % o["book"],
                    "source_url": lg["source_url"],
                    "source_file_sha256": ln_meta["sha256"],
                })
        for rule in frozen:
            row = {
                "game_id": game_id, "away_team": sg["away_team"],
                "home_team": sg["home_team"],
                "kickoff_utc": sg["kickoff_utc"],
                "rule_version": rule["version_id"], "action": "",
                "market": rules.FAMILIES[rule["family"]]["market"],
                "side": "", "real_line": "", "line_convention": "",
                "real_price_american": "", "book": "", "price_observed_utc": "",
                "price_source_url": "", "local_availability_verified": "",
                "final_away_score": num_text(sg["away_score"])
                if is_final else "",
                "final_home_score": num_text(sg["home_score"])
                if is_final else "",
                "result_source_url": sb_meta["source_url"],
                "result_retrieved_at_utc": sb_meta["retrieved_at_utc"],
                "score_status": "", "outcome": "", "pnl_units": "",
                "shadow_outcome": "", "shadow_pnl_units": "",
                "ledger_pick_id": "", "ledger_agrees": "", "reason": "",
                "_price": None, "_line": None, "_entry": None,
            }
            score_out.append(row)
            entry = ledger.get((game_id, rule["version_id"])) if ng else None
            if entry is not None:
                row["ledger_pick_id"] = entry["pick_id"]
                row["_entry"] = entry
            if not ng:
                row["score_status"] = UNMATCHED
                continue
            line = None
            if market is not None:
                line = market["total_line"] if row["market"] == "total" \
                    else market["spread_line"]
            if market is None or line is None:
                row["score_status"] = NO_PRICE
                row["reason"] = why_no_price or (
                    "the source holds no usable %s line" % row["market"])
                continue
            dec = rules.decide(rule["family"], rule["value"], {
                "spread_line": market["spread_line"],
                "total_line": market["total_line"],
                "away_rest": ng["away_rest"], "home_rest": ng["home_rest"]})
            row["action"], row["side"] = dec["action"], dec["side"] or ""
            row["real_line"], row["_line"] = num_text(dec["line"]), dec["line"]
            row["line_convention"] = (
                "total points" if row["market"] == "total" else
                "home favored when positive (away %+g, home %+g)"
                % (dec["line"], -dec["line"]))
            row["reason"] = dec["reason"]
            row["book"] = market["book"]
            row["price_observed_utc"] = market["observed_utc"]
            row["price_source_url"] = market["source_url"]
            row["local_availability_verified"] = \
                "yes" if market["local_availability_verified"] else "no"
            if dec["side"] is None:
                row["score_status"] = NO_SIDE
            else:
                price = market["price"].get((row["market"], dec["side"]))
                if price is None:
                    row["score_status"] = NO_PRICE
                    row["reason"] = "the source holds no price for this side"
                else:
                    row["_price"] = price
                    row["real_price_american"] = price_text(price)
                    if is_final:
                        outcome = rules.grade(
                            row["market"], dec["side"], dec["line"],
                            sg["home_score"], sg["away_score"])
                        pnl = pl.pnl_for(outcome, price, 1.0)
                        row["score_status"] = SCORED
                        if dec["action"] == "take":
                            row["outcome"] = outcome
                            row["pnl_units"] = "%+.4f" % pnl
                        else:
                            row["outcome"] = "pass"
                            row["pnl_units"] = "+0.0000"
                            row["shadow_outcome"] = outcome
                            row["shadow_pnl_units"] = "%+.4f" % pnl
                    else:
                        row["score_status"] = AWAITING
            if entry is None:
                row["ledger_agrees"] = "no ledger row for this game and rule"
            else:
                diffs = []
                if entry.get("action") != dec["action"]:
                    diffs.append("action %s" % entry.get("action"))
                if entry.get("side") != dec["side"]:
                    diffs.append("side %s" % entry.get("side"))
                if pl.line_text(entry.get("line")) != pl.line_text(
                        dec["line"]):
                    diffs.append("line %s" % pl.line_text(entry.get("line")))
                if row["_price"] is not None and (
                        entry.get("price_american") is None or float(
                            entry["price_american"]) != float(row["_price"])):
                    diffs.append("price %s" % num_text(
                        entry.get("price_american")))
                row["ledger_agrees"] = "yes" if not diffs else (
                    "NO, ledger has " + ", ".join(diffs))
    if len(weeks) != 1:
        raise IntakeError("the scoreboard games do not map to exactly one "
                          "season and week: %s" % sorted(weeks))
    season, week = weeks.pop()
    return {
        "now": now, "season": season, "week": week, "sb_meta": sb_meta,
        "ln_meta": ln_meta, "inputs": inputs, "games": games_out,
        "finals": finals_out, "prices": prices_out, "scores": score_out,
        "notes": notes,
    }


# --- writing -----------------------------------------------------------------
def write_csv(path, cols, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore",
                           lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.replace(tmp, path)


def write_text(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


GAME_COLS = ["game_id", "away_team", "home_team", "away_name", "home_name",
             "kickoff_utc", "status", "away_score", "home_score", "final",
             "schedule_match", "real_price_available", "provider_event_id",
             "source", "source_url", "retrieved_at_utc",
             "source_file_sha256", "note"]
FINAL_COLS = ["game_id", "home_team", "away_team", "home_score",
              "away_score", "source", "source_url", "retrieved_at_utc",
              "provider_event_id", "status"]
PRICE_COLS = ["game_id", "away_team", "home_team", "kickoff_utc", "book",
              "market", "side", "line_as_shown", "price_american",
              "price_as_shown", "observed_utc", "book_updated_utc",
              "local_availability_verified", "source", "source_url",
              "source_file_sha256"]
SCORE_COLS = ["game_id", "away_team", "home_team", "kickoff_utc",
              "rule_version", "action", "market", "side", "real_line",
              "line_convention", "real_price_american", "book",
              "price_observed_utc", "price_source_url",
              "local_availability_verified", "final_away_score",
              "final_home_score", "result_source_url",
              "result_retrieved_at_utc", "score_status", "outcome",
              "pnl_units", "shadow_outcome", "shadow_pnl_units",
              "ledger_pick_id", "ledger_agrees", "reason"]


AGREE_TEXT = {"yes": "same decision, side, line and price as the real "
                     "source"}


def count_by(rows, key):
    out = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


def markdown(res, tag, applied):
    g, s = res["games"], res["scores"]
    by_status = count_by(s, "score_status")
    lines = []
    add = lines.append
    add("# Real NFL data: %d week %d" % (res["season"], res["week"]))
    add("")
    add("PAPER ONLY. No bets, no accounts, no money. Written by "
        "`real_intake.py` at %s (system clock)." % pl.fmt_ts(res["now"]))
    add("")
    add("## Where every number came from")
    add("")
    add("- Games, teams, kickoff times and finals: %s, page %s, captured %s "
        "(file sha256 `%s`)." % (res["sb_meta"]["source"],
                                  res["sb_meta"]["source_url"],
                                  res["sb_meta"]["retrieved_at_utc"],
                                  res["sb_meta"]["sha256"]))
    urls = sorted(set(p["source_url"] for p in res["prices"]))
    times = sorted(set(p["observed_utc"] for p in res["prices"]))
    books = sorted(set(p["book"] for p in res["prices"]))
    add("- Prices: %s as shown on the public ESPN scoreboard, observed %s "
        "(file sha256 `%s`). URLs: %s."
        % (", ".join(books) or "none", ", ".join(times) or "never",
           res["ln_meta"]["sha256"], ", ".join(urls) or "none"))
    add("- Capture note carried from the price file: \"%s\""
        % res["ln_meta"]["price_note"])
    add("- Rest days: nflverse schedule file %s, retrieved %s."
        % (res["inputs"].url, res["inputs"].retrieved_str))
    add("- These prices were read %s. They are not closing lines, and "
        "nobody has checked that they are offered in Louisiana."
        % ("before kickoff" if times else "never"))
    add("")
    add("## What is real and what is missing")
    add("")
    add("- Real games: %d. Finals in the source: %d. Games with a real "
        "price: %d. Games with no price: %d."
        % (len(g), sum(1 for x in g if x["final"] == "yes"),
           sum(1 for x in g if x["real_price_available"] == "yes"),
           sum(1 for x in g if x["real_price_available"] == "no")))
    add("- Rule rows (frozen rules x games): %d." % len(s))
    for status in (SCORED, AWAITING, NO_PRICE, NO_SIDE, UNMATCHED):
        if by_status.get(status):
            add("  - %s: %d" % (status, by_status[status]))
    agree = count_by([r for r in s if r["ledger_agrees"]], "ledger_agrees")
    add("- Compared with the paper ledger rows: %s."
        % ("; ".join("%s: %d" % (AGREE_TEXT.get(k, k), v)
                     for k, v in sorted(agree.items()))
           or "nothing to compare"))
    if applied is not None:
        add("- Ledger writes this run: %s." % applied)
    for n in res["notes"]:
        add("- NOTE: %s" % n)
    add("")
    add("## Games")
    add("")
    add("| Kickoff (UTC) | Game | Status | Final | Real spread (home) | "
        "Real total |")
    add("|---|---|---|---|---|---|")
    first = {}
    for r in s:
        first.setdefault((r["away_team"], r["home_team"]), {})[
            r["market"]] = r
    for x in g:
        rows = first.get((x["away_team"], x["home_team"]), {})
        sp, to = rows.get("spread"), rows.get("total")
        spread = total = "no price"
        if sp is not None and sp["_line"] is not None:
            spread = "%s %+g" % (x["home_team"], -sp["_line"])
        if to is not None and to["_line"] is not None:
            total = "%g" % to["_line"]
        final = ("%s %s, %s %s" % (x["away_team"], x["away_score"],
                                   x["home_team"], x["home_score"])
                 if x["final"] == "yes" else "not played yet")
        add("| %s | %s at %s | %s | %s | %s | %s |"
            % (x["kickoff_utc"], x["away_team"], x["home_team"], x["status"],
               final, spread, total))
    add("")
    add("## Frozen rules on the real games")
    add("")
    add("A take is a paper pick. A pass is scored on its shadow side so "
        "passes are counted too. Spread lines are shown for the picked side.")
    add("")
    add("| Game | Rule | Decision | Pick | Real price | Score |")
    add("|---|---|---|---|---|---|")
    for r in s:
        pick = ""
        if r["_line"] is not None and r["side"]:
            if r["market"] == "total":
                pick = "%s %g" % (r["side"], r["_line"])
            else:
                team = r["home_team"] if r["side"] == "home" \
                    else r["away_team"]
                hcap = -r["_line"] if r["side"] == "home" else r["_line"]
                pick = "%s %+g" % (team, hcap)
        score = r["score_status"]
        if r["score_status"] == SCORED:
            score = ("%s, %s units" % (r["outcome"], r["pnl_units"])
                     if r["action"] == "take" else
                     "pass; shadow %s, %s units"
                     % (r["shadow_outcome"], r["shadow_pnl_units"]))
        add("| %s at %s | %s | %s | %s | %s | %s |"
            % (r["away_team"], r["home_team"], r["rule_version"],
               r["action"] or "-", pick or "-",
               r["real_price_american"] or "-", score))
    add("")
    add("Files beside this one: `%s_games.csv`, `%s_finals.csv`, "
        "`%s_prices.csv`, `%s_rule_scores.csv`, `INTAKE_RECEIPT.json`. Every "
        "row in them carries its source URL and retrieval time." %
        (tag, tag, tag, tag))
    add("")
    add("Paper output never implies a real edge or authorizes real money.")
    return "\n".join(lines) + "\n"


# --- ledger writes (only through paper_ledger.py) ---------------------------
def call_ledger(argv):
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf_out), \
            contextlib.redirect_stderr(buf_err):
        code = pl.main(argv)
    return code, buf_out.getvalue(), buf_err.getvalue()


def backed_finals(res):
    """Split the real finals into (backed, held back).

    The ledger settles a take at the price stored on its own row. So a final
    goes to settle only when every rule row of that game is either scored at
    a real price that matches the ledger row exactly (decision, side, line
    and price) or has no side. Any other final is held back, so no row is
    ever settled at a price the real source does not hold.
    """
    by_game = {}
    for r in res["scores"]:
        by_game.setdefault(r["game_id"], []).append(r)
    backed, held = [], []
    for f in res["finals"]:
        rs = by_game.get(f["game_id"], [])
        ok = bool(rs) and all(
            r["score_status"] in (SCORED, NO_SIDE)
            and r["ledger_agrees"] == "yes" for r in rs)
        (backed if ok else held).append(f)
    return backed, held


def apply_to_ledger(res, args, finals_path):
    """Record real prices on identical contracts, then give settle the finals."""
    extra = ["--ledger-dir", os.path.abspath(args.ledger_dir)]
    if args.now:
        extra += ["--now", args.now]
    existing = set()
    for o in pl.load_jsonl(pl.Paths(args.ledger_dir).observations):
        existing.add((o.get("pick_id"), o.get("quote_ts_utc"),
                      o.get("source"), float(o.get("price_american") or 0)))
    counts = {"recorded": 0, "already_recorded": 0, "refused": 0,
              "line_differs_not_recorded": 0}
    refusals = []
    for r in res["scores"]:
        entry = r["_entry"]
        if entry is None or r["_price"] is None or not r["side"]:
            continue
        # identical contract only: same side and the same line text
        if entry.get("side") != r["side"] or pl.line_text(
                entry.get("line")) != pl.line_text(r["_line"]):
            counts["line_differs_not_recorded"] += 1
            continue
        source = ("%s via ESPN public scoreboard display, read before "
                  "kickoff, not a closing line; %s; capture file sha256 %s"
                  % (r["book"], r["price_source_url"],
                     res["ln_meta"]["sha256"]))
        key = (entry["pick_id"], r["price_observed_utc"], source,
               float(r["_price"]))
        if key in existing:
            counts["already_recorded"] += 1
            continue
        code, _, errtext = call_ledger(
            ["close", "--pick-id", entry["pick_id"],
             "--line=%s" % pl.line_text(entry.get("line")),
             "--price", str(r["_price"]), "--source", source,
             "--quote-ts", r["price_observed_utc"], "--not-a-close"] + extra)
        if code == pl.EXIT_OK:
            counts["recorded"] += 1
            existing.add(key)
        else:
            counts["refused"] += 1
            refusals.append("%s: %s" % (entry["pick_id"],
                                        pl.clean(errtext.strip())[:200]))
    settle_text = "no finals in the source, settle not run"
    settle_code = None
    if res["finals"]:
        backed, held = backed_finals(res)
        settle_path = os.path.splitext(finals_path)[0] + "_for_settle.csv"
        write_csv(settle_path, FINAL_COLS, backed)
        if backed:
            settle_code, out_text, err_text = call_ledger(
                ["settle", "--results-file", settle_path, "--results-ts",
                 res["sb_meta"]["retrieved_at_utc"]] + extra)
            summary = [ln for ln in out_text.splitlines()
                       if ln.startswith("SUMMARY")]
            settle_text = (summary[0] if summary else
                           "settle exit %s %s" % (settle_code,
                                                  pl.clean(err_text)[:200]))
        else:
            settle_text = "settle not run"
        if held:
            settle_text += ("; %d final(s) held back from settle, no real "
                            "price on the identical ledger contract: %s"
                            % (len(held), ", ".join(
                                f["game_id"] or "unmatched" for f in held)))
    return counts, refusals, settle_text, settle_code


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="real_intake.py", allow_abbrev=False,
        description="Load real NFL games, finals and prices for the paper "
                    "ledger. " + pl.BANNER)
    ap.add_argument("--scoreboard", required=True,
                    help="JSON capture of real games and scores (data only)")
    ap.add_argument("--lines", required=True,
                    help="JSON capture of public price displays (data only)")
    ap.add_argument("--out-dir", default=os.path.join(HERE, "real"))
    ap.add_argument("--ledger-dir", default=pl.REAL_LEDGER_DIR)
    ap.add_argument("--apply", action="store_true",
                    help="also record the real prices on the ledger picks "
                         "and give the real finals to settle. Without it "
                         "nothing in the ledger is written")
    ap.add_argument("--now", metavar="ISO",
                    help="tests only: a pretend clock. Refused unless both "
                         "--ledger-dir and --out-dir are scratch folders")
    args = ap.parse_args(argv)
    if args.now and (
            os.path.realpath(args.ledger_dir)
            == os.path.realpath(pl.REAL_LEDGER_DIR)
            or os.path.realpath(args.out_dir)
            == os.path.realpath(os.path.join(HERE, "real"))):
        sys.stderr.write("REFUSED NOW_OVERRIDE_NOT_ALLOWED: --now is for "
                         "tests only. It needs a scratch --ledger-dir and a "
                         "scratch --out-dir\n")
        return 2
    try:
        res = build(args)
    except IntakeError as exc:
        sys.stderr.write("REFUSED INTAKE_INVALID: %s\n" % exc)
        return 2
    except pl.Refusal as exc:
        sys.stderr.write("REFUSED %s: %s\n" % (exc.code, exc))
        return 2
    tag = "week%02d" % res["week"]
    os.makedirs(args.out_dir, exist_ok=True)
    finals_path = os.path.join(args.out_dir, tag + "_finals.csv")
    write_csv(os.path.join(args.out_dir, tag + "_games.csv"), GAME_COLS,
              res["games"])
    write_csv(finals_path, FINAL_COLS, res["finals"])
    write_csv(os.path.join(args.out_dir, tag + "_prices.csv"), PRICE_COLS,
              res["prices"])
    write_csv(os.path.join(args.out_dir, tag + "_rule_scores.csv"),
              SCORE_COLS, res["scores"])
    applied_text = None
    applied = None
    code = 0
    if args.apply:
        counts, refusals, settle_text, settle_code = apply_to_ledger(
            res, args, finals_path)
        applied = {"ledger_dir": os.path.abspath(args.ledger_dir),
                   "price_observations": counts, "refusals": refusals,
                   "settle": settle_text}
        applied_text = ("%d real prices recorded on identical contracts, %d "
                        "already there, %d refused, %d not recorded because "
                        "the line differs; settle: %s"
                        % (counts["recorded"], counts["already_recorded"],
                           counts["refused"],
                           counts["line_differs_not_recorded"], settle_text))
        if counts["refused"] or settle_code not in (None, pl.EXIT_OK):
            code = 2
    write_text(os.path.join(args.out_dir, "REAL_%s.md" % tag.upper()),
               markdown(res, tag, applied_text))
    by_status = count_by(res["scores"], "score_status")
    receipt = {
        "paper_only": True,
        "generated_at_utc": pl.fmt_ts(res["now"]),
        "season": res["season"], "week": res["week"],
        "inputs": {
            "scoreboard": {k: res["sb_meta"][k] for k in (
                "path", "sha256", "bytes", "source", "source_url",
                "retrieved_at_utc", "retrieved_at_raw")},
            "public_lines": {k: res["ln_meta"][k] for k in (
                "path", "sha256", "bytes", "price_note")},
            "schedule": {"url": res["inputs"].url,
                         "sha256": res["inputs"].sha256,
                         "retrieved_at_utc": res["inputs"].retrieved_str},
        },
        "counts": {
            "games": len(res["games"]),
            "finals": len(res["finals"]),
            "games_with_real_price": sum(
                1 for x in res["games"] if x["real_price_available"] == "yes"),
            "price_rows": len(res["prices"]),
            "rule_rows": len(res["scores"]),
            "rule_rows_by_status": by_status,
            "ledger_agreement": count_by(
                [r for r in res["scores"] if r["ledger_agrees"]],
                "ledger_agrees"),
        },
        "notes": res["notes"],
        "applied_to_ledger": applied,
    }
    write_text(os.path.join(args.out_dir, "INTAKE_RECEIPT.json"),
               json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    say(pl.BANNER)
    say("REAL INTAKE %d week %d: %d games, %d finals, %d games with a real "
        "price, %d price rows" % (
            res["season"], res["week"], len(res["games"]),
            len(res["finals"]), receipt["counts"]["games_with_real_price"],
            len(res["prices"])))
    for status in (SCORED, AWAITING, NO_PRICE, NO_SIDE, UNMATCHED):
        say("  rule rows, %-48s %d" % (status + ":", by_status.get(status, 0)))
    for k, v in sorted(receipt["counts"]["ledger_agreement"].items()):
        say("  ledger comparison, %s: %d" % (AGREE_TEXT.get(k, k), v))
    for n in res["notes"]:
        say("  NOTE: %s" % n)
    if applied_text:
        say("LEDGER: " + applied_text)
        for r in applied["refusals"]:
            say("  REFUSED " + r)
    else:
        say("LEDGER: not touched (dry run; add --apply to record the real "
            "prices and settle the real finals)")
    say("Wrote %s" % os.path.abspath(args.out_dir))
    return code


if __name__ == "__main__":
    sys.exit(main())
