#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Pregame experiment and evaluation journal for the NFL Sunday slate.

What it keeps, each in its own append-only file under data/:

  predictions  what the bot (or the price capture) said before kickoff:
               exact line, price, book and quote time. Never rewritten.
  hypotheses   a football hypothesis registered before kickoff (sha256 + UTC).
  decisions    Matthew's take / pass / alternative, with his reason.
  tickets      a bet Matthew says he placed himself (book, price, stake).
  finals       observed scores, player results and voids, each with a source.
  closes       a later price for the same exact line (information only).

Rules built in:
  * One candidate = event + period + market + team or player + exact line + side.
  * An original record is never changed. A new price is a new record.
  * Decisions and hypotheses must be entered before kickoff, or they are
    refused (or, with --late, kept but left out of the pregame score).
  * A final cannot be entered before the game could have ended.
  * Grading uses the recorded price. Push and void return the stake.
    A missing final is "unknown", never guessed.
  * Later prices and estimated value are shown for information. They never
    pick, change or remove anything.

This tool reads local files only. It has no network code, no keys, no
accounts and places no bets. Python 3.9 standard library only.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import sys

sys.dont_write_bytecode = True

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA = os.path.join(HERE, "data")
UTC = datetime.timezone.utc

BAND_LOW, BAND_HIGH = -200, 200      # inclusive, American odds
MAX_QUOTE_AGE_MIN = 30               # same staleness cut as Codex's compare_books.py
MIN_GAME_MINUTES = 150               # no NFL game ends sooner than this after kickoff
CONTROL_TOLERANCE = 0.025            # break-even distance for a price-matched control

JOURNALS = ("predictions", "hypotheses", "decisions", "tickets", "finals", "closes", "controls", "research", "settlements")
SETTLEMENT_OUTCOMES = ("win", "loss", "push", "void", "refund", "cashout", "adjustment", "other")
RESEARCH_STATUSES = ("rejected", "supported", "open", "untested")
ACTIONS = ("take", "pass", "alternative")
RESERVED = ("seq", "recorded_utc", "prev", "sha")
PERIOD_SUFFIX = (("_h1", "h1"), ("_h2", "h2"), ("_q1", "q1"), ("_q2", "q2"), ("_q3", "q3"), ("_q4", "q4"))
PERIOD_NAMES = {"game": "full game", "h1": "first half", "h2": "second half",
                "q1": "first quarter", "q2": "second quarter", "q3": "third quarter", "q4": "fourth quarter"}
WINDOW_NAMES = {"early": "Morning / noon", "late": "Late afternoon", "night": "Sunday night"}
STAT_NAMES = {"player_pass_yds": "passing yards", "player_rush_yds": "rushing yards",
              "player_reception_yds": "receiving yards", "player_receptions": "receptions",
              "player_pass_tds": "passing touchdowns", "player_pass_attempts": "pass attempts",
              "player_pass_completions": "completions", "player_rush_attempts": "rush attempts",
              "player_anytime_td": "anytime touchdown"}
BOOK_NAMES = {"betmgm": "BetMGM", "betrivers": "BetRivers", "draftkings": "DraftKings",
              "espnbet": "theScore Bet", "fanduel": "FanDuel"}
MARKET_ORDER = {"h2h": 0, "spreads": 1, "totals": 2, "team_totals": 3}


class JournalError(Exception):
    """A refused action. The message is shown to the user as written."""


# ---------------------------------------------------------------- time and odds

def utc_now():
    return datetime.datetime.now(UTC).replace(microsecond=0)


def stamp(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text):
    s = str(text).strip()
    if s[-1:] in ("Z", "z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(s)
    except ValueError:
        raise JournalError("Not a time I can read: %r. Use the form 2026-11-15T18:00:00Z." % (text,))
    if dt.tzinfo is None:
        raise JournalError("The time %r has no time zone. Add Z for UTC." % (text,))
    return dt.astimezone(UTC)


def central(dt):
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("America/Chicago"))
    except Exception:  # no tz database: November is standard time, UTC-6
        return dt.astimezone(datetime.timezone(datetime.timedelta(hours=-6)))


def central_label(dt):
    loc = central(dt)
    return loc.strftime("%a %b %d, %I:%M %p Central").replace(" 0", " ")


def window_of(kickoff):
    hour = central(kickoff).hour
    return "early" if hour < 14 else "late" if hour < 18 else "night"


def valid_price(p):
    return (isinstance(p, (int, float)) and not isinstance(p, bool)
            and math.isfinite(p) and abs(p) >= 100)


def decimal_odds(p):
    if not valid_price(p):
        raise JournalError("Not valid American odds: %r (use numbers like -110 or +160)." % (p,))
    return 1.0 + (p / 100.0 if p > 0 else 100.0 / abs(p))


def implied(p):
    return 1.0 / decimal_odds(p)


def in_band(p):
    return valid_price(p) and BAND_LOW <= p <= BAND_HIGH


def novig(p, other):
    a, b = implied(p), implied(other)
    return a / (a + b)


def profit(price, result, stake=1.0):
    """Money back beyond the stake, at the recorded price. None when unknown."""
    if result == "win":
        return stake * (decimal_odds(price) - 1.0)
    if result == "loss":
        return -float(stake)
    if result in ("push", "void"):
        return 0.0
    return None


def wilson(wins, n, z=1.96):
    if not n:
        return None
    p = wins / float(n)
    d = 1.0 + z * z / n
    c = (p + z * z / (2.0 * n)) / d
    h = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fmt_price(p):
    return "%+d" % int(p) if float(p).is_integer() else "%+g" % p


def fmt_point(pt, signed=False):
    if pt is None:
        return ""
    x = float(pt)
    if x == 0:
        x = 0.0
    return ("%+g" % x) if signed else ("%g" % x)


def pct(x, digits=1):
    return "n/a" if x is None else ("%." + str(digits) + "f%%") % (100.0 * x)


def units(x):
    return "n/a" if x is None else "%+.2f" % x


def book_name(key):
    return BOOK_NAMES.get(str(key or "").lower(), str(key or "book not given"))


# ---------------------------------------------------------------- identity

def norm_text(s):
    return " ".join(str(s if s is not None else "").split()).casefold()


def norm_point(p):
    if p is None:
        return "none"
    x = float(p)
    if x == 0:
        x = 0.0
    return "%.2f" % x


def period_of(market):
    for suffix, name in PERIOD_SUFFIX:
        if str(market).endswith(suffix):
            return name
    return "game"


def base_market(market):
    m = str(market)
    for suffix, _name in PERIOD_SUFFIX:
        if m.endswith(suffix):
            return m[:-len(suffix)]
    return m


def candidate_id(event_id, market, subject, point, side):
    """Stable id from event, period, market, team or player, exact line and side."""
    key = [norm_text(event_id), period_of(market), norm_text(market),
           norm_text(subject), norm_point(point), norm_text(side)]
    digest = hashlib.sha256(json.dumps(key, separators=(",", ":")).encode("utf-8")).hexdigest()
    return digest[:12]


def make_identity(event_id, market, subject, point, side):
    return {"event_id": str(event_id), "period": period_of(market), "market": str(market),
            "subject": " ".join(str(subject or "").split()),
            "point": None if point is None else float(point), "side": " ".join(str(side).split())}


def make_label(identity):
    base, per = base_market(identity["market"]), identity["period"]
    side, subj, pt = identity["side"], identity["subject"], identity["point"]
    if base == "h2h":
        text = "%s to win" % side
    elif base == "spreads":
        text = "%s %s" % (side, fmt_point(pt, signed=True))
    elif base == "totals":
        text = "%s %s total points" % (side, fmt_point(pt))
    elif base == "team_totals":
        text = "%s %s %s team points" % (subj, side.lower(), fmt_point(pt))
    elif base.startswith("player_"):
        text = "%s %s %s %s" % (subj, side.lower(), fmt_point(pt), STAT_NAMES.get(base, base))
    else:
        text = " ".join(x for x in (subj, side, fmt_point(pt), base) if x)
    return text if per == "game" else "%s: %s" % (PERIOD_NAMES.get(per, per).capitalize(), text)


def short_game(home, away):
    return "%s at %s" % (str(away).split()[-1], str(home).split()[-1])


# ---------------------------------------------------------------- files

def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class Journal(object):
    """Append-only JSON-lines files. Each line carries the hash of the line before it."""

    def __init__(self, data_dir=DEFAULT_DATA):
        self.dir = data_dir

    def path(self, name):
        if name not in JOURNALS:
            raise JournalError("Unknown journal %r." % (name,))
        return os.path.join(self.dir, name + ".jsonl")

    @staticmethod
    def _dump(rec):
        return json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @classmethod
    def _digest(cls, rec):
        body = dict((k, v) for k, v in rec.items() if k != "sha")
        return hashlib.sha256(cls._dump(body).encode("utf-8")).hexdigest()

    def read(self, name):
        path = self.path(name)
        if not os.path.exists(path):
            return []
        rows, prev = [], ""
        with open(path, "r", encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                line = line.rstrip("\n")
                try:
                    rec = json.loads(line)
                    ok = (isinstance(rec, dict) and rec.get("seq") == n and rec.get("prev") == prev
                          and rec.get("sha") == self._digest(rec))
                except ValueError:
                    ok = False
                if not ok:
                    raise JournalError(
                        "%s.jsonl line %d fails its integrity check: the file was changed outside "
                        "this tool. Nothing was written. Restore the file before continuing." % (name, n))
                prev = rec["sha"]
                rows.append(rec)
        return rows

    def append_many(self, name, bodies, now, *, validate=None):
        if not bodies:
            return []
        os.makedirs(self.dir, exist_ok=True)
        lock = open(os.path.join(self.dir, ".lock"), "a")
        try:
            if fcntl is not None:
                fcntl.flock(lock, fcntl.LOCK_EX)
            rows = self.read(name)
            if validate is not None:
                validate(rows)
            seq, prev, out, lines = len(rows), (rows[-1]["sha"] if rows else ""), [], []
            for body in bodies:
                rec = dict(body)
                for k in RESERVED:
                    if k in rec:
                        raise JournalError("Reserved field %r in a new record." % (k,))
                seq += 1
                rec["seq"], rec["recorded_utc"], rec["prev"] = seq, stamp(now), prev
                rec["sha"] = self._digest(rec)
                prev = rec["sha"]
                out.append(rec)
                lines.append(self._dump(rec))
            with open(self.path(name), "a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return out
        finally:
            lock.close()

    def append(self, name, body, now, *, validate=None):
        return self.append_many(name, [body], now, validate=validate)[0]

    def verify(self):
        """Return (lines per journal, list of problems)."""
        counts, problems = {}, []
        for name in JOURNALS:
            try:
                counts[name] = len(self.read(name))
            except JournalError as err:
                counts[name] = None
                problems.append(str(err))
        return counts, problems


class State(object):
    """Everything in the journals, read once and indexed."""

    def __init__(self, journal):
        self.j = journal
        self.predictions = journal.read("predictions")
        self.hypotheses = journal.read("hypotheses")
        self.decisions = journal.read("decisions")
        self.tickets = journal.read("tickets")
        self.settlements = journal.read("settlements")
        self.settled_by_ticket = {s["ticket_id"]: s for s in self.settlements}
        self.finals = journal.read("finals")
        self.closes = journal.read("closes")
        self.controls = journal.read("controls")
        self.research = journal.read("research")
        self.events, self.records = {}, {}
        for r in self.predictions:
            ev = r["identity"]["event_id"]
            self.events.setdefault(ev, {"event_id": ev, "home_team": r["home_team"],
                                        "away_team": r["away_team"], "kickoff_utc": r["kickoff_utc"],
                                        "game": r["game"]})
            self.records.setdefault(r["cid"], []).append(r)
        self.scores, self.player_results, self.voids, self.close_by_cid = {}, {}, {}, {}
        for f in self.finals:
            if f["type"] == "score":
                self.scores[f["event_id"]] = f
            elif f["type"] == "player":
                self.player_results[(f["event_id"], norm_text(f["player"]), f["market"])] = f
            elif f["type"] == "void":
                self.voids[f["cid"]] = f
        for c in self.closes:
            old = self.close_by_cid.get(c["cid"])
            if old is None or c["captured_utc"] >= old["captured_utc"]:
                self.close_by_cid[c["cid"]] = c

    def original(self, cid):
        """The bot's original for this candidate: its first posted call, else the first record."""
        recs = self.records[cid]
        for r in recs:
            if r["role"] == "call":
                return r
        return recs[0]

    def pool(self, cid):
        for r in self.records.get(cid, []):
            if r["role"] == "pool":
                return r
        return None

    def first_by_role(self, role):
        out = {}
        for r in self.predictions:
            if r["role"] == role and r["cid"] not in out:
                out[r["cid"]] = r
        return out

    def resolve(self, token):
        t = str(token or "").strip().lower()
        if len(t) < 4:
            raise JournalError("Give at least the first 4 characters of the bet's id (see 'list').")
        hits = [cid for cid in self.records if cid.startswith(t)]
        if not hits:
            raise JournalError("No bet in the journal has an id starting with %r." % (token,))
        if len(hits) > 1:
            raise JournalError("%r matches %d bets. Give more characters of the id." % (token, len(hits)))
        return hits[0]

    def resolve_event(self, token):
        t = norm_text(token)
        if not t:
            raise JournalError("Name the game: a team name or the event id.")
        hits = [e for e in self.events if e.lower() == t or (len(t) >= 6 and e.lower().startswith(t))]
        if not hits:
            words = t.split()
            hits = [e for e, ev in self.events.items() if all(w in norm_text(ev["game"]) for w in words)]
        if not hits:
            raise JournalError("No loaded game matches %r." % (token,))
        if len(hits) > 1:
            raise JournalError("%r matches %d games. Use a team name that appears in one game only." % (token, len(hits)))
        return hits[0]

    def resolve_hypothesis(self, token):
        t = str(token or "").strip().lower()
        hits = [h for h in self.hypotheses if h["hypothesis_id"].lower().startswith(t)] if len(t) >= 3 else []
        if len(hits) != 1:
            raise JournalError("No single registered hypothesis matches %r (see 'status')." % (token,))
        return hits[0]["hypothesis_id"]


# ---------------------------------------------------------------- reading a price capture

def contracts_from_capture(snap, max_age_min=MAX_QUOTE_AGE_MIN):
    """Every exact contract side in an Odds-API-shaped capture, with each book's quote.

    Quotes are dropped (and counted) when the game had started at capture time, when a
    quote has no time, is dated after the capture or at/after kickoff, or is older than
    max_age_min at capture. A contract is keyed on its exact line; lines are never mixed.
    """
    captured = parse_utc(snap["captured_utc"])
    rows = {}
    skipped = {"game_started": 0, "no_quote_time": 0, "quote_after_capture_or_kickoff": 0,
               "stale_quote": 0, "bad_price": 0, "unknown_side": 0, "no_line": 0}
    for section in ("games", "event_odds"):
        for ev in snap.get(section) or []:
            kickoff = parse_utc(ev["commence_time"])
            if kickoff <= captured:
                skipped["game_started"] += 1
                continue
            home, away = ev["home_team"], ev["away_team"]
            for book in ev.get("bookmakers") or []:
                for m in book.get("markets") or []:
                    outs = m.get("outcomes") or []
                    when_txt = m.get("last_update") or book.get("last_update")
                    if not when_txt:
                        skipped["no_quote_time"] += len(outs)
                        continue
                    when = parse_utc(when_txt)
                    if when > captured or when >= kickoff:
                        skipped["quote_after_capture_or_kickoff"] += len(outs)
                        continue
                    if captured - when > datetime.timedelta(minutes=max_age_min):
                        skipped["stale_quote"] += len(outs)
                        continue
                    kind = m["key"]
                    base = base_market(kind)
                    for o in outs:
                        side, point, price = o.get("name"), o.get("point"), o.get("price")
                        subject = o.get("description") or ""
                        if not valid_price(price):
                            skipped["bad_price"] += 1
                            continue
                        if base in ("h2h", "spreads"):
                            if side not in (home, away):
                                skipped["unknown_side"] += 1
                                continue
                            other_name = home if side == away else away
                            other_point = None if point is None else -point
                        else:
                            if side not in ("Over", "Under"):
                                skipped["unknown_side"] += 1
                                continue
                            other_name = "Under" if side == "Over" else "Over"
                            other_point = point
                        if base != "h2h" and point is None:
                            skipped["no_line"] += 1
                            continue
                        other = None
                        for x in outs:
                            if (x.get("name") == other_name and x.get("point") == other_point
                                    and (x.get("description") or "") == subject and valid_price(x.get("price"))):
                                other = x
                                break
                        ident = make_identity(ev["id"], kind, subject, point, side)
                        cid = candidate_id(ev["id"], kind, subject, point, side)
                        row = rows.get(cid)
                        if row is None:
                            row = rows[cid] = {
                                "role": "pool", "cid": cid, "identity": ident, "label": make_label(ident),
                                "game": "%s at %s" % (away, home), "home_team": home, "away_team": away,
                                "kickoff_utc": stamp(kickoff), "window": window_of(kickoff), "quotes": {}}
                        row["quotes"][book["key"]] = {
                            "price": price, "quote_utc": stamp(when),
                            "fair": novig(price, other["price"]) if other else None}
    for row in rows.values():
        finish_pool_row(row)
    ordered = sorted(rows.values(), key=sort_key)
    return ordered, skipped, captured


def finish_pool_row(row):
    quotes = row["quotes"]
    band = sorted((-decimal_odds(q["price"]), b) for b, q in quotes.items() if in_band(q["price"]))
    anyq = sorted((-decimal_odds(q["price"]), b) for b, q in quotes.items())
    book = (band or anyq)[0][1]
    fairs = sorted(q["fair"] for q in quotes.values() if q["fair"] is not None)
    if fairs:
        mid = len(fairs) // 2
        prob = fairs[mid] if len(fairs) % 2 else (fairs[mid - 1] + fairs[mid]) / 2.0
    else:
        prob = None
    row["price"] = quotes[book]["price"]
    row["book"] = book
    row["quote_utc"] = quotes[book]["quote_utc"]
    row["in_band"] = bool(band)
    row["price_basis"] = ("best price across books inside the -200 to +200 band" if band
                          else "best price across books (no book is inside the -200 to +200 band)")
    row["market_prob"] = prob
    row["market_prob_books"] = len(fairs)
    row["is_favorite"] = (prob > 0.5) if (row["identity"]["market"] == "h2h" and prob is not None) else None


def sort_key(rec):
    ident = rec["identity"]
    return (rec["kickoff_utc"], rec["game"], MARKET_ORDER.get(base_market(ident["market"]), 9),
            ident["market"], norm_text(ident["subject"]), norm_point(ident["point"]), norm_text(ident["side"]))


def import_capture(journal, path, now):
    """Record every exact contract in a price capture as an original pool record."""
    snap = load_json(path)
    rows, skipped, captured = contracts_from_capture(snap)
    if captured > now + datetime.timedelta(minutes=5):
        raise JournalError("The capture is dated %s, which is after the clock here (%s). Refused."
                           % (stamp(captured), stamp(now)))
    sha = sha256_file(path)
    source = {"file": os.path.abspath(path), "sha256": sha, "captured_utc": stamp(captured)}
    state = State(journal)
    seen = set(r["cid"] for r in state.predictions if r["role"] == "pool" and r["source"]["sha256"] == sha)
    bodies = []
    for row in rows:
        if row["cid"] in seen:
            continue
        body = dict(row)
        body["source"] = source
        bodies.append(body)
    journal.append_many("predictions", bodies, now)
    return {"contracts_in_capture": len(rows), "new_records": len(bodies),
            "already_recorded": len(rows) - len(bodies), "skipped_quotes": skipped,
            "capture_sha256": sha, "captured_utc": stamp(captured)}


# ---------------------------------------------------------------- the bot's posted calls

def first_key(d, names):
    for n in names:
        if isinstance(d, dict) and d.get(n) is not None:
            return d[n]
    return None


def call_body(call, doc, state, source, now, late):
    if not isinstance(call, dict):
        raise JournalError("not an object")
    event_id, market, side = call.get("event_id"), call.get("market"), call.get("side")
    if not (event_id and market and side):
        raise JournalError("missing event_id, market or side")
    subject, point = call.get("subject") or "", call.get("point")
    if base_market(market) != "h2h" and point is None:
        raise JournalError("no line (point) for a market that needs one")
    if point is not None and not isinstance(point, (int, float)):
        raise JournalError("the line (point) is not a number")
    quote = call.get("quote") if isinstance(call.get("quote"), dict) else {}
    price = first_key(call, ("price", "best_price", "quoted_price"))
    if price is None:
        price = first_key(quote, ("price",))
    basis = "the bot's call price, as written in the picker file"
    if price is None and call.get("minimum_price") is not None:
        price = call["minimum_price"]
        basis = "the bot's minimum acceptable price (the picker file gave no quoted price)"
    if not valid_price(price):
        raise JournalError("no usable American price")
    book = first_key(call, ("book", "book_key", "sportsbook")) or first_key(quote, ("book", "book_key"))
    quote_txt = (first_key(call, ("updated", "quote_utc", "book_updated_utc", "provider_updated_utc", "observed_utc"))
                 or first_key(quote, ("updated", "quote_utc", "book_updated_utc", "provider_updated_utc", "observed_utc")))
    known = state.events.get(str(event_id)) or {}
    home = call.get("home_team") or known.get("home_team")
    away = call.get("away_team") or known.get("away_team")
    kick_txt = first_key(call, ("kickoff", "kickoff_utc", "commence_time")) or known.get("kickoff_utc")
    if not (home and away and kick_txt):
        raise JournalError("the game is not loaded yet; run import-capture on the price capture first")
    kickoff = parse_utc(kick_txt)
    quote_utc = None
    if quote_txt:
        qdt = parse_utc(quote_txt)
        if qdt >= kickoff:
            raise JournalError("its quote time is not before kickoff")
        quote_utc = stamp(qdt)
    pregame = now < kickoff
    if not pregame and not late:
        raise JournalError("kickoff has passed, so it cannot be recorded as a pregame original "
                           "(use --late to keep it, flagged and unscored)")
    ident = make_identity(event_id, market, subject, point, side)
    return {"role": "call", "cid": candidate_id(event_id, market, subject, point, side),
            "identity": ident, "label": make_label(ident), "game": "%s at %s" % (away, home),
            "home_team": home, "away_team": away, "kickoff_utc": stamp(kickoff),
            "window": window_of(kickoff), "price": price, "book": book, "quote_utc": quote_utc,
            "price_basis": basis, "in_band": in_band(price),
            "minimum_price": call.get("minimum_price"), "pregame_verified": pregame,
            "decided_utc_in_file": first_key(doc, ("decided_utc", "generated_utc", "created_utc")) if isinstance(doc, dict) else None,
            "original": call, "source": source}


def import_calls(journal, path, now, late=False):
    """Record the bot's posted calls from the picker's selection file, exactly as written."""
    doc = load_json(path)
    calls = doc.get("calls") if isinstance(doc, dict) else doc
    if not isinstance(calls, list):
        raise JournalError("No 'calls' list in %s." % (path,))
    sha = sha256_file(path)
    source = {"file": os.path.abspath(path), "sha256": sha,
              "captured_utc": first_key(doc, ("captured_utc", "capture_utc")) if isinstance(doc, dict) else None}
    state = State(journal)
    bodies, refused, repeats = [], [], 0
    for i, call in enumerate(calls):
        try:
            body = call_body(call, doc, state, source, now, late)
        except JournalError as err:
            refused.append("call %d: %s" % (i + 1, err))
            continue
        if any(r["role"] == "call" and r["source"]["sha256"] == sha for r in state.records.get(body["cid"], [])):
            repeats += 1
            continue
        if any(b["cid"] == body["cid"] for b in bodies):
            refused.append("call %d: the same exact bet appears twice in the file" % (i + 1))
            continue
        bodies.append(body)
    journal.append_many("predictions", bodies, now)
    return {"calls_in_file": len(calls), "new_records": len(bodies), "already_recorded": repeats,
            "refused": refused, "file_sha256": sha}


def add_manual(journal, event, market, side, price, book, now, subject="", point=None,
               quote_utc=None, by="matthew", note=""):
    """A bet Matthew wants tracked that is not in the capture (his own line and price)."""
    state = State(journal)
    ev_id = state.resolve_event(event)
    ev = state.events[ev_id]
    if not valid_price(price):
        raise JournalError("Not valid American odds: %r." % (price,))
    base = base_market(market)
    if base == "h2h":
        point = None
    elif point is None:
        raise JournalError("This market needs a line (--point).")
    if base in ("h2h", "spreads"):
        hits = [t for t in (ev["home_team"], ev["away_team"]) if norm_text(side) in norm_text(t)]
        if len(hits) != 1:
            raise JournalError("For this market the side must be one of the two teams: %s or %s."
                               % (ev["away_team"], ev["home_team"]))
        side = hits[0]
    else:
        if norm_text(side) not in ("over", "under"):
            raise JournalError("For this market the side must be Over or Under.")
        side = side.strip().capitalize()
        if not str(subject).strip() and base != "totals":
            raise JournalError("Name the team or player (--subject).")
    kickoff = parse_utc(ev["kickoff_utc"])
    if now >= kickoff:
        raise JournalError("Kickoff has passed; a pregame bet cannot be added now.")
    qutc = stamp(now)
    if quote_utc:
        qdt = parse_utc(quote_utc)
        if qdt >= kickoff or qdt > now:
            raise JournalError("The quote time must be before kickoff and not in the future.")
        qutc = stamp(qdt)
    ident = make_identity(ev_id, market, subject, point, side)
    cid = candidate_id(ev_id, market, subject, point, side)
    body = {"role": "manual", "cid": cid, "identity": ident, "label": make_label(ident),
            "game": ev["game"], "home_team": ev["home_team"], "away_team": ev["away_team"],
            "kickoff_utc": ev["kickoff_utc"], "window": window_of(kickoff), "price": price,
            "book": book, "quote_utc": qutc, "price_basis": "entered by %s" % by,
            "in_band": in_band(price), "entered_by": by, "note": note,
            "source": {"file": None, "sha256": None, "captured_utc": None}}
    return journal.append("predictions", body, now)


# ---------------------------------------------------------------- Matthew's entries

def snapshot(rec):
    return {"prediction_seq": rec["seq"], "role": rec["role"], "label": rec["label"],
            "point": rec["identity"]["point"], "price": rec["price"], "book": rec["book"],
            "quote_utc": rec["quote_utc"], "kickoff_utc": rec["kickoff_utc"],
            "recorded_utc": rec["recorded_utc"]}


def record_hypothesis(journal, text, now, by="matthew", events=(), cids=(), late=False):
    state = State(journal)
    text = str(text or "").strip()
    if len(text) < 15:
        raise JournalError("Write the hypothesis as a full sentence that a result could prove wrong.")
    ev_ids = [state.resolve_event(e) for e in events]
    c_ids = [state.resolve(c) for c in cids]
    kicks = ([parse_utc(state.events[e]["kickoff_utc"]) for e in ev_ids]
             + [parse_utc(state.original(c)["kickoff_utc"]) for c in c_ids])
    scope = "named games and bets"
    if not kicks:
        kicks = [parse_utc(e["kickoff_utc"]) for e in state.events.values()]
        scope = "whole loaded slate"
    if not kicks:
        raise JournalError("No games are loaded yet. Run import-capture first, so the hypothesis "
                           "can be checked against kickoff.")
    first = min(kicks)
    pregame = now < first
    if not pregame and not late:
        raise JournalError("The first game this covers kicked off at %s. A hypothesis must be registered "
                           "before kickoff. (--late keeps it, flagged as after the fact.)" % stamp(first))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if any(h["text_sha256"] == digest for h in state.hypotheses):
        raise JournalError("That exact hypothesis is already registered.")
    body = {"hypothesis_id": "H" + digest[:8], "by": by, "text": text, "text_sha256": digest,
            "event_ids": ev_ids, "cids": c_ids, "scope": scope,
            "first_kickoff_utc": stamp(first), "pregame": pregame}
    return journal.append("hypotheses", body, now)


def record_decision(journal, token, action, reason, now, by="matthew", alt=None, hypothesis=None,
                    price=None, book=None, revise=False, late=False):
    state = State(journal)
    cid = state.resolve(token)
    if action not in ACTIONS:
        raise JournalError("The action must be take, pass or alternative.")
    reason = " ".join(str(reason or "").split())
    if len(reason) < 3:
        raise JournalError("A reason is required: a sentence in your own words.")
    orig = state.original(cid)
    kickoff = parse_utc(orig["kickoff_utc"])
    alt_cid, alt_orig = None, None
    if action == "alternative":
        if not alt:
            raise JournalError("An alternative needs the id of the bet you prefer instead (--alt).")
        alt_cid = state.resolve(alt)
        if alt_cid == cid:
            raise JournalError("The alternative is the same bet. Use 'take' instead.")
        alt_orig = state.original(alt_cid)
        kickoff = min(kickoff, parse_utc(alt_orig["kickoff_utc"]))
    elif alt:
        raise JournalError("--alt only goes with the action 'alternative'.")
    if price is not None:
        if action == "pass":
            raise JournalError("A pass has no price. Leave --price out.")
        if not valid_price(price):
            raise JournalError("Not valid American odds: %r." % (price,))
    pregame = now < kickoff
    if not pregame and not late:
        raise JournalError("Kickoff has passed (%s). A decision must be entered before kickoff. "
                           "(--late keeps it in the journal, flagged and left out of the score.)" % stamp(kickoff))
    prior = [d for d in state.decisions if d["cid"] == cid and d["by"] == by and d["pregame"]]
    if prior and pregame and not revise:
        raise JournalError("You already recorded '%s' on this bet at %s. Add --revise to record a change "
                           "of mind; the first entry stays in the journal."
                           % (prior[-1]["action"], prior[-1]["recorded_utc"]))
    body = {"cid": cid, "by": by, "action": action, "reason": reason, "pregame": pregame,
            "alt_cid": alt_cid, "hypothesis_id": state.resolve_hypothesis(hypothesis) if hypothesis else None,
            "chosen_price": price, "chosen_book": book,
            "revision_of_seq": prior[-1]["seq"] if (prior and pregame) else None,
            "bot_original": snapshot(orig), "alt_original": snapshot(alt_orig) if alt_orig else None}
    return journal.append("decisions", body, now)


def ticket_id(ticket):
    """A stable identifier for one original ticket, including tickets in older journals."""
    return "T" + ticket["sha"]


def ticket_fingerprint(ticket):
    return (ticket["cid"], norm_text(ticket["book"]), ticket["price"], ticket["stake"],
            norm_text(ticket["stake_unit"]), ticket["point"], ticket.get("placed_utc_reported"))


def compare_call_price(original, point, price):
    floor = original.get("minimum_price")
    if floor is None or norm_point(point) != norm_point(original["identity"]["point"]):
        return None
    return decimal_odds(price) >= decimal_odds(floor)


def record_ticket(journal, token, book, price, stake, now, by="matthew", unit="dollars",
                  point=None, placed_utc=None, note="", offered_price=None):
    """A bet Matthew reports he placed himself. Kept apart from every recommendation.

    offered_price is optional: the price the sportsbook showed him for this exact bet when he looked.
    It is kept on the same ticket line, for information. The ticket is graded at `price`, never at it.
    """
    state = State(journal)
    cid = state.resolve(token)
    orig = state.original(cid)
    if not valid_price(price):
        raise JournalError("Not valid American odds: %r." % (price,))
    try:
        stake = float(stake)
    except (TypeError, ValueError):
        raise JournalError("The stake must be a number.")
    if not (math.isfinite(stake) and stake > 0):
        raise JournalError("The stake must be more than zero.")
    book = " ".join(str(book or "").split())
    if not book:
        raise JournalError("Name the sportsbook the ticket is at.")
    if offered_price is not None and not valid_price(offered_price):
        raise JournalError("The offered price is not valid American odds: %r." % (offered_price,))
    own = orig["identity"]["point"]
    if point is None:
        tpoint = own
    else:
        if base_market(orig["identity"]["market"]) == "h2h":
            raise JournalError("A match-winner bet has no line. Leave --point out.")
        tpoint = float(point)
    if tpoint is not None and not math.isfinite(tpoint):
        raise JournalError("The accepted line must be finite.")
    if not placed_utc:
        raise JournalError("Enter the actual ticket placement time with its time zone.")
    placed = parse_utc(placed_utc)
    kickoff = parse_utc(orig["kickoff_utc"])
    if placed > now or placed >= kickoff:
        raise JournalError("The reported placement must be before kickoff and cannot be in the future.")
    body = {"cid": cid, "by": by, "book": book, "price": price, "stake": stake, "stake_unit": unit,
            "point": tpoint, "line_differs": norm_point(tpoint) != norm_point(own),
            "placed_utc_reported": stamp(placed), "accepted_in_band": in_band(price),
            "issued_minimum_price": orig.get("minimum_price"),
            "meets_issued_minimum": compare_call_price(orig, tpoint, price),
            "recorded_before_kickoff": now < kickoff, "note": note, "offered_price": offered_price,
            "bot_original": snapshot(orig)}
    fingerprint = ticket_fingerprint(body)

    def reject_duplicate(rows):
        if any(ticket_fingerprint(prior) == fingerprint for prior in rows):
            raise JournalError("This exact ticket was already recorded.")

    row = journal.append("tickets", body, now, validate=reject_duplicate)
    return dict(row, ticket_id=ticket_id(row))


def record_settlement(journal, ticket_id, gross_return, outcome, now, *, confirmed,
                      prior_sha=None, note="", by="matthew"):
    """Append the operator return the user reports, or a version-checked correction."""
    if confirmed is not True:
        raise JournalError("Confirm the return shown by the sportsbook, including any returned stake.")
    if outcome not in SETTLEMENT_OUTCOMES:
        raise JournalError("Choose a sportsbook settlement outcome.")
    if isinstance(gross_return, bool):
        raise JournalError("Enter the total actually returned, including stake.")
    try:
        gross = float(gross_return)
    except (ValueError, TypeError, OverflowError):
        raise JournalError("Enter the total actually returned, including stake.")
    if not math.isfinite(gross) or gross < 0:
        raise JournalError("The total returned must be finite and zero or greater.")
    tickets = {"T" + t["sha"]: t for t in journal.read("tickets")}
    if ticket_id not in tickets:
        raise JournalError("Choose an existing individual ticket.")
    ticket = tickets[ticket_id]
    if now < parse_utc(ticket.get("placed_utc_reported") or ticket["recorded_utc"]):
        raise JournalError("The return cannot precede the ticket.")
    note = str(note or "").strip()
    if prior_sha and not note:
        raise JournalError("Add a note explaining the revised book return.")
    body = {"ticket_id": ticket_id, "cid": ticket["cid"], "gross_return": gross,
            "outcome": outcome, "note": note, "by": by, "source": "user-confirmed sportsbook return",
            "stake_unit": ticket["stake_unit"], "supersedes": prior_sha or None}

    def require_current(rows):
        current = next((s for s in reversed(rows) if s["ticket_id"] == ticket_id), None)
        if (current["sha"] if current else None) != (prior_sha or None):
            raise JournalError("This ticket's settlement has changed. Reload the latest return before correcting it.")

    return journal.append("settlements", body, now, validate=require_current)


# ---------------------------------------------------------------- observed outcomes

def _score(value, what):
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise JournalError("%s must be a whole number." % what)
    if v < 0 or v != float(value):
        raise JournalError("%s must be a whole number, zero or more." % what)
    return v


def _earliest_final(kickoff):
    return kickoff + datetime.timedelta(minutes=MIN_GAME_MINUTES)


def _clean(text):
    return " ".join(str(text or "").split())


def record_control(journal, token, control_token, rule, now, by="codex", book=None, price=None,
                   source="", late=False):
    """Pair one bet with one matched control picked before kickoff.

    A control is a comparison, never a bet. Its price is the one already recorded in the capture
    (at the named book, or the pool's best price); a price is never typed in or invented. One control
    per bet, registered before either game starts, and never swapped afterwards.
    """
    state = State(journal)
    cid = state.resolve(token)
    ccid = state.resolve(control_token)
    if cid == ccid:
        raise JournalError("A bet cannot be its own control.")
    bet, ctl = state.original(cid), state.original(ccid)
    if ctl["identity"]["event_id"] == bet["identity"]["event_id"]:
        raise JournalError("A control must come from a different game.")
    if any(c["cid"] == cid for c in state.controls):
        raise JournalError("That bet already has a registered control. Controls are not swapped after the fact.")
    rule = _clean(rule)
    if len(rule) < 15:
        raise JournalError("State the matching rule in a sentence (--rule).")
    row = state.first_by_role("pool").get(ccid) or ctl
    quotes = row.get("quotes") or {}
    if book:
        hits = [b for b in quotes if norm_text(b) == norm_text(book)]
        if not hits:
            raise JournalError("There is no recorded quote from %r for that control. A control price is never invented."
                               % (book,))
        cbook, cprice, cquote = hits[0], quotes[hits[0]]["price"], quotes[hits[0]]["quote_utc"]
    else:
        cbook, cprice, cquote = row["book"], row["price"], row["quote_utc"]
    if price is not None and price != cprice:
        raise JournalError("The recorded price for that control at %s is %s, not %r."
                           % (cbook, fmt_price(cprice), price))
    first = min(parse_utc(bet["kickoff_utc"]), parse_utc(ctl["kickoff_utc"]))
    pregame = now < first
    if not pregame and not late:
        raise JournalError("A control is registered before either game starts "
                           "(use --late to keep it, flagged and unscored).")
    body = {"cid": cid, "control_cid": ccid, "by": by, "rule": rule,
            "rule_sha256": hashlib.sha256(rule.encode("utf-8")).hexdigest(),
            "book": cbook, "price": cprice, "quote_utc": cquote, "pregame_verified": pregame,
            "source": _clean(source), "bet_original": snapshot(bet), "control_original": snapshot(ctl)}
    return journal.append("controls", body, now)


def record_research(journal, title, status, summary, evidence, now, by="experiment owner",
                    scope_note="", changed_live_rule=False):
    """One line in the research register: an idea that was tested and what became of it.

    It needs no games loaded and never touches a prediction. A later line can add to an earlier one;
    nothing is ever edited or removed.
    """
    title, summary, evidence, scope_note = _clean(title), _clean(summary), _clean(evidence), _clean(scope_note)
    status = _clean(status).lower()
    if status not in RESEARCH_STATUSES:
        raise JournalError("The status must be one of: %s." % ", ".join(RESEARCH_STATUSES))
    if len(title) < 8:
        raise JournalError("Give the idea a title of at least 8 characters.")
    if len(summary) < 30:
        raise JournalError("Say what was tested and what was found, in a sentence or two.")
    if not evidence:
        raise JournalError("Say where the evidence is (--evidence).")
    digest = hashlib.sha256(json.dumps([title.lower(), status, summary.lower()]).encode("utf-8")).hexdigest()
    if any(r["text_sha256"] == digest for r in journal.read("research")):
        raise JournalError("That exact research note is already in the register.")
    body = {"research_id": "R" + digest[:8], "title": title, "status": status, "summary": summary,
            "evidence": evidence, "scope_note": scope_note, "changed_live_rule": bool(changed_live_rule),
            "by": _clean(by) or "experiment owner", "text_sha256": digest}
    return journal.append("research", body, now)


def record_final(journal, event, home_score, away_score, source, now, h1_home=None, h1_away=None):
    state = State(journal)
    ev_id = state.resolve_event(event)
    ev = state.events[ev_id]
    kickoff = parse_utc(ev["kickoff_utc"])
    if now < _earliest_final(kickoff):
        raise JournalError("%s cannot be final yet (kickoff %s). No result is recorded before the game "
                           "could have ended." % (ev["game"], ev["kickoff_utc"]))
    source = " ".join(str(source or "").split())
    if not source:
        raise JournalError("Say where the score came from (--source).")
    if (h1_home is None) != (h1_away is None):
        raise JournalError("Give both first-half scores or neither.")
    body = {"type": "score", "event_id": ev_id, "home_team": ev["home_team"], "away_team": ev["away_team"],
            "home_score": _score(home_score, "The home score"), "away_score": _score(away_score, "The away score"),
            "h1_home": None if h1_home is None else _score(h1_home, "The first-half home score"),
            "h1_away": None if h1_away is None else _score(h1_away, "The first-half away score"),
            "source": source}
    return journal.append("finals", body, now)


def record_player_result(journal, event, player, market, value, source, now):
    state = State(journal)
    ev_id = state.resolve_event(event)
    kickoff = parse_utc(state.events[ev_id]["kickoff_utc"])
    if now < _earliest_final(kickoff):
        raise JournalError("That game cannot be final yet. No player result is recorded before it could have ended.")
    source = " ".join(str(source or "").split())
    if not source:
        raise JournalError("Say where the number came from (--source).")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise JournalError("The player's number must be a number.")
    player = " ".join(str(player or "").split())
    if not player:
        raise JournalError("Name the player.")
    if not str(market).startswith("player_") or not math.isfinite(value):
        raise JournalError("Supply the exact player market and a finite stat.")
    body = {"type": "player", "event_id": ev_id, "player": player, "market": market,
            "value": value, "source": source}
    return journal.append("finals", body, now)


def record_void(journal, token, reason, source, now):
    state = State(journal)
    cid = state.resolve(token)
    reason, source = " ".join(str(reason or "").split()), " ".join(str(source or "").split())
    if not reason or not source:
        raise JournalError("A void needs a reason and a source.")
    return journal.append("finals", {"type": "void", "cid": cid, "reason": reason, "source": source}, now)


def import_finals(journal, path, now):
    """Finals from an agent-made file: Codex's ESPN lines capture, or a plain list of rows."""
    doc = load_json(path)
    rows = doc
    if isinstance(doc, dict):
        rows = doc.get("games") if doc.get("games") is not None else doc.get("finals")
    if not isinstance(rows, list):
        raise JournalError("No 'games' or 'finals' list in %s." % (path,))
    sha = sha256_file(path)
    state = State(journal)
    by_teams = dict(((norm_text(e["home_team"]), norm_text(e["away_team"])), k) for k, e in state.events.items())
    bodies, notes = [], []
    for g in rows:
        if not isinstance(g, dict):
            continue
        if isinstance(g.get("teams"), dict):
            home, away = g["teams"].get("home"), g["teams"].get("away")
            fs = g.get("final_score") or {}
            hs, as_ = fs.get("home"), fs.get("away")
            done = g.get("state") == "STATUS_FINAL"
        else:
            home, away = g.get("home_team"), g.get("away_team")
            hs, as_ = g.get("home_score"), g.get("away_score")
            done = str(g.get("status") or g.get("state") or "").lower() in ("final", "status_final")
        ev_id = g.get("odds_event_id") if g.get("odds_event_id") in state.events else None
        if ev_id is None:
            ev_id = by_teams.get((norm_text(home), norm_text(away)))
        if ev_id is None:
            continue
        ev = state.events[ev_id]
        if not done or hs is None or as_ is None:
            notes.append("%s: not final in the file" % ev["game"])
            continue
        if now < _earliest_final(parse_utc(ev["kickoff_utc"])):
            notes.append("%s: refused, the game cannot be final yet" % ev["game"])
            continue
        old = state.scores.get(ev_id)
        if old and old["home_score"] == hs and old["away_score"] == as_ and old.get("h1_home") == g.get("h1_home"):
            continue
        bodies.append({"type": "score", "event_id": ev_id, "home_team": ev["home_team"],
                       "away_team": ev["away_team"], "home_score": _score(hs, "The home score"),
                       "away_score": _score(as_, "The away score"),
                       "h1_home": None if g.get("h1_home") is None else _score(g.get("h1_home"), "The first-half home score"),
                       "h1_away": None if g.get("h1_away") is None else _score(g.get("h1_away"), "The first-half away score"),
                       "source": "%s (file %s, sha256 %s)" % (g.get("source_url") or g.get("source") or "agent capture",
                                                               os.path.basename(path), sha[:12])})
    journal.append_many("finals", bodies, now)
    return {"finals_recorded": len(bodies), "notes": notes}


def tracked_cids(state):
    out = set(r["cid"] for r in state.predictions if r["role"] in ("call", "manual"))
    for d in state.decisions:
        out.add(d["cid"])
        if d.get("alt_cid"):
            out.add(d["alt_cid"])
    for t in state.tickets:
        out.add(t["cid"])
    return out


def import_close(journal, path, now):
    """A later price for the same exact line of every tracked bet. Information only."""
    snap = load_json(path)
    rows, _skipped, captured = contracts_from_capture(snap)
    if captured > now + datetime.timedelta(minutes=5):
        raise JournalError("The capture is dated after the clock here. Refused.")
    sha = sha256_file(path)
    by_cid = dict((r["cid"], r) for r in rows)
    state = State(journal)
    bodies, missing = [], 0
    for cid in sorted(tracked_cids(state)):
        row = by_cid.get(cid)
        if row is None:
            missing += 1
            continue
        if any(c["cid"] == cid and c["source"]["sha256"] == sha for c in state.closes):
            continue
        bodies.append({"cid": cid, "price": row["price"], "book": row["book"], "in_band": row["in_band"],
                       "market_prob": row["market_prob"], "market_prob_books": row["market_prob_books"],
                       "quotes": row["quotes"], "captured_utc": stamp(captured), "kickoff_utc": row["kickoff_utc"],
                       "source": {"file": os.path.abspath(path), "sha256": sha, "captured_utc": stamp(captured)}})
    journal.append_many("closes", bodies, now)
    return {"later_prices_recorded": len(bodies), "tracked_bets_with_no_price_at_their_exact_line": missing}


# ---------------------------------------------------------------- grading

def _over_under(value, point, side):
    if value == point:
        return "push"
    over = value > point
    return "win" if over == (norm_text(side) == "over") else "loss"


def settle(rec, state, point=None):
    """(result, detail) for one record: win, loss, push, void or unknown."""
    ident = rec["identity"]
    void = state.voids.get(rec["cid"])
    if void:
        return "void", "void: %s" % void["reason"]
    base, per = base_market(ident["market"]), ident["period"]
    pt = ident["point"] if point is None else point
    if base.startswith("player_"):
        if period_of(ident["market"]) != per:
            return "unknown", "conflicting player market and period"
        pr = state.player_results.get((ident["event_id"], norm_text(ident["subject"]), ident["market"]))
        if not pr:
            return "unknown", "no player result recorded"
        return _over_under(pr["value"], pt, ident["side"]), "%s had %g" % (ident["subject"], pr["value"])
    final = state.scores.get(ident["event_id"])
    if not final:
        return "unknown", "no final recorded"
    if per == "game":
        hs, as_ = final["home_score"], final["away_score"]
    elif per == "h1":
        hs, as_ = final.get("h1_home"), final.get("h1_away")
        if hs is None or as_ is None:
            return "unknown", "no first-half score recorded"
    else:
        return "unknown", "%s is not graded by this tool" % PERIOD_NAMES.get(per, per)
    home, away = rec["home_team"], rec["away_team"]
    detail = "%s %d, %s %d%s" % (away, as_, home, hs, "" if per == "game" else " (first half)")
    if base in ("h2h", "spreads"):
        if norm_text(ident["side"]) == norm_text(home):
            margin = hs - as_
        elif norm_text(ident["side"]) == norm_text(away):
            margin = as_ - hs
        else:
            return "unknown", "the side is not one of the two teams"
        adj = margin + (pt or 0.0) if base == "spreads" else margin
        return ("win" if adj > 0 else "loss" if adj < 0 else "push"), detail
    if base == "totals":
        return _over_under(hs + as_, pt, ident["side"]), detail
    if base == "team_totals":
        if norm_text(ident["subject"]) == norm_text(home):
            pts = hs
        elif norm_text(ident["subject"]) == norm_text(away):
            pts = as_
        else:
            return "unknown", "the team is not one of the two teams"
        return _over_under(pts, pt, ident["side"]), detail
    return "unknown", "the market %s is not graded by this tool" % ident["market"]


def grade_at(rec, state, price=None, stake=1.0, point=None):
    price = rec["price"] if price is None else price
    result, detail = settle(rec, state, point)
    return {"result": result, "detail": detail, "price": price, "stake": stake,
            "units": profit(price, result, stake)}


def tally(items):
    t = {"n": len(items), "win": 0, "loss": 0, "push": 0, "void": 0, "unknown": 0,
         "units": 0.0, "staked": 0.0}
    for it in items:
        t[it["result"]] += 1
        if it["units"] is not None:
            t["units"] += it["units"]
        if it["result"] in ("win", "loss"):
            t["staked"] += it.get("stake", 1.0)
    decided = t["win"] + t["loss"]
    t["decided"] = decided
    t["win_rate"] = (t["win"] / float(decided)) if decided else None
    t["wilson95"] = wilson(t["win"], decided)
    t["return_per_unit"] = (t["units"] / t["staked"]) if t["staked"] else None
    return t


def describe(rec, state):
    pool = state.pool(rec["cid"])
    prob = pool["market_prob"] if pool else None
    be = implied(rec["price"])
    close = state.close_by_cid.get(rec["cid"])
    out = {"cid": rec["cid"], "label": rec["label"], "game": rec["game"],
           "short_game": short_game(rec["home_team"], rec["away_team"]),
           "kickoff_utc": rec["kickoff_utc"], "window": rec["window"], "role": rec["role"],
           "price": rec["price"], "book": rec["book"], "quote_utc": rec["quote_utc"],
           "price_basis": rec["price_basis"], "in_band": in_band(rec["price"]),
           "market_prob": prob, "market_prob_books": pool["market_prob_books"] if pool else 0,
           "breakeven": be,
           "est_value_per_unit": (prob * decimal_odds(rec["price"]) - 1.0)
                                 if prob is not None and pool["market_prob_books"] > 1 else None,
           "later_price": None}
    if close:
        mins = int((parse_utc(close["kickoff_utc"]) - parse_utc(close["captured_utc"])).total_seconds() // 60)
        out["later_price"] = {
            "price": close["price"], "book": close["book"], "captured_utc": close["captured_utc"],
            "minutes_before_kickoff": mins, "market_prob": close["market_prob"],
            "points_vs_breakeven": (close["market_prob"] - be) if close["market_prob"] is not None else None}
    return out


def effective_decisions(state):
    """Latest pregame decision per person and bet, plus how many pregame entries there were."""
    eff, counts, late = {}, {}, []
    for d in state.decisions:
        if not d["pregame"]:
            late.append(d)
            continue
        key = (d["by"], d["cid"])
        eff[key] = d
        counts[key] = counts.get(key, 0) + 1
    return [(d, counts[(d["by"], d["cid"])]) for d in eff.values()], late


def evaluate(state):
    calls = []
    for cid, rec in state.first_by_role("call").items():
        row = describe(rec, state)
        row.update(grade_at(rec, state))
        row["pregame_verified"] = rec.get("pregame_verified", True)
        calls.append(row)
    calls.sort(key=lambda r: (r["kickoff_utc"], r["game"], r["label"]))

    eff, late = effective_decisions(state)
    decisions = []
    for d, n_entries in eff:
        orig = state.original(d["cid"])
        row = describe(orig, state)
        bot = grade_at(orig, state)
        row.update({"action": d["action"], "by": d["by"], "reason": d["reason"],
                    "decided_utc": d["recorded_utc"], "hypothesis_id": d["hypothesis_id"],
                    "entries": n_entries, "bot_is_call": orig["role"] == "call",
                    "bot_result": bot["result"], "bot_units": bot["units"], "bot_detail": bot["detail"],
                    "chosen_price": d.get("chosen_price"), "chosen_book": d.get("chosen_book")})
        if d["action"] == "take":
            mine = grade_at(orig, state, price=d.get("chosen_price"))
            row.update({"your_label": orig["label"], "your_price": mine["price"],
                        "result": mine["result"], "units": mine["units"], "stake": 1.0})
        elif d["action"] == "alternative":
            alt = state.original(d["alt_cid"])
            mine = grade_at(alt, state, price=d.get("chosen_price"))
            row.update({"your_label": alt["label"], "your_price": mine["price"], "alt_cid": alt["cid"],
                        "result": mine["result"], "units": mine["units"], "stake": 1.0})
        else:
            row.update({"your_label": "no bet", "your_price": None, "result": "no bet", "units": 0.0, "stake": 0.0})
        decisions.append(row)
    decisions.sort(key=lambda r: (r["kickoff_utc"], r["game"], r["label"]))

    tickets = []
    for t in state.tickets:
        orig = state.original(t["cid"])
        g = grade_at(orig, state, price=t["price"], stake=t["stake"], point=t["point"])
        label = orig["label"]
        if t["line_differs"]:
            ident = dict(orig["identity"])
            ident["point"] = t["point"]
            label = make_label(ident)
        tid = ticket_id(t)
        settlement = state.settled_by_ticket.get(tid)
        tickets.append({"ticket_id": tid, "cid": t["cid"], "label": label, "game": orig["game"],
                        "short_game": short_game(orig["home_team"], orig["away_team"]),
                        "accepted_in_band": in_band(t["price"]), "settlement": settlement,
                        "issued_minimum_price": orig.get("minimum_price"),
                        "meets_issued_minimum": compare_call_price(orig, t["point"], t["price"]),
                        "estimated_gross_return": t["stake"] + g["units"] if g["units"] is not None else None,
                        "actual_net": round(settlement["gross_return"] - t["stake"], 10) if settlement else None,
                        "book": t["book"], "price": t["price"], "stake": t["stake"],
                        "stake_unit": t["stake_unit"], "line_differs": t["line_differs"],
                        "bot_label": orig["label"], "bot_price": orig["price"], "bot_book": orig["book"],
                        "placed_utc_reported": t["placed_utc_reported"], "recorded_utc": t["recorded_utc"],
                        "recorded_before_kickoff": t["recorded_before_kickoff"],
                        "offered_price": t.get("offered_price"),
                        "result": g["result"], "units": g["units"], "detail": g["detail"]})

    decided_cids = dict((r["cid"], r["action"]) for r in decisions if r["by"] == "matthew")
    agreement = {}
    for name in ("take", "pass", "alternative", "no decision"):
        agreement[name] = tally([c for c in calls if decided_cids.get(c["cid"], "no decision") == name])

    passes = [{"result": r["bot_result"], "units": r["bot_units"], "stake": 1.0} for r in decisions if r["action"] == "pass"]
    score = {
        "bot_calls": tally(calls),
        "your_takes": tally([r for r in decisions if r["action"] == "take"]),
        "your_alternatives": tally([r for r in decisions if r["action"] == "alternative"]),
        "bets_you_passed": tally(passes),
        "bot_calls_by_your_decision": agreement,
    }
    by_unit = {}
    for t in tickets:
        by_unit.setdefault(t["stake_unit"], []).append(t)
    score["your_tickets"] = dict((u, tally(rows)) for u, rows in by_unit.items())
    score["confirmed_ticket_returns"] = {}
    for unit, rows in by_unit.items():
        settled = [t for t in rows if t["settlement"] is not None]
        score["confirmed_ticket_returns"][unit] = {
            "confirmed_count": len(settled), "pending_count": len(rows) - len(settled),
            "confirmed_stake": math.fsum(t["stake"] for t in settled),
            "gross_return": math.fsum(t["settlement"]["gross_return"] for t in settled),
            "net_return": math.fsum(t["actual_net"] for t in settled)}

    acted = set(c["cid"] for c in calls)
    for r in decisions:
        if r["action"] == "take":
            acted.add(r["cid"])
        elif r["action"] == "alternative":
            acted.add(r["alt_cid"])
    score["benchmarks"] = benchmarks(state, calls, acted)

    pairs = []
    for c in state.controls:
        bet, ctl = state.original(c["cid"]), state.original(c["control_cid"])
        gb, gc = grade_at(bet, state), grade_at(ctl, state, price=c["price"])
        pairs.append({"cid": c["cid"], "label": bet["label"], "game": bet["game"],
                      "short_game": short_game(bet["home_team"], bet["away_team"]),
                      "price": bet["price"], "book": bet["book"], "result": gb["result"], "units": gb["units"],
                      "control_cid": c["control_cid"], "control_label": ctl["label"], "control_game": ctl["game"],
                      "control_short_game": short_game(ctl["home_team"], ctl["away_team"]),
                      "control_price": c["price"], "control_book": c["book"],
                      "control_result": gc["result"], "control_units": gc["units"],
                      "rule": c["rule"], "rule_sha256": c["rule_sha256"], "by": c["by"], "source": c["source"],
                      "recorded_utc": c["recorded_utc"], "pregame_verified": c["pregame_verified"]})
    scored = [p for p in pairs if p["pregame_verified"]]
    score["registered_controls"] = {
        "bets": tally([{"result": p["result"], "units": p["units"], "stake": 1.0} for p in scored]),
        "controls": tally([{"result": p["control_result"], "units": p["control_units"], "stake": 1.0}
                           for p in scored])}

    return {"calls": calls, "decisions": decisions, "tickets": tickets, "score": score,
            "controls": pairs, "research": state.research,
            "late_decisions": [{"cid": d["cid"], "action": d["action"], "reason": d["reason"],
                                "recorded_utc": d["recorded_utc"], "label": state.original(d["cid"])["label"]}
                               for d in late],
            "hypotheses": state.hypotheses}


def benchmarks(state, calls, acted):
    pool = state.first_by_role("pool")
    fav_band, fav_all = [], []
    for r in pool.values():
        if r["identity"]["market"] == "h2h" and r.get("is_favorite"):
            g = grade_at(r, state)
            fav_all.append(g)
            if in_band(r["price"]):
                fav_band.append(g)
    top = {}
    for r in pool.values():
        if r["identity"]["market"] == "h2h" and in_band(r["price"]) and r.get("market_prob") is not None:
            key = (-r["market_prob"], r["kickoff_utc"], r["game"], r["cid"])
            if r["window"] not in top or key < top[r["window"]][0]:
                top[r["window"]] = (key, r)
    top_rows = []
    for w in sorted(top):
        r = top[w][1]
        g = grade_at(r, state)
        g.update({"cid": r["cid"], "label": r["label"], "game": r["game"], "book": r["book"],
                  "window": w, "market_prob": r["market_prob"]})
        top_rows.append(g)
    controls = {}
    for cid in sorted(acted):
        a = state.original(cid)
        be = implied(a["price"])
        for r in pool.values():
            if r["cid"] in acted or not in_band(r["price"]):
                continue
            if r["identity"]["event_id"] == a["identity"]["event_id"]:
                continue
            if r["identity"]["market"] != a["identity"]["market"]:
                continue
            if abs(implied(r["price"]) - be) <= CONTROL_TOLERANCE:
                if r["cid"] not in controls:                     # graded once, at its own recorded price
                    g = grade_at(r, state)
                    g.update({"cid": r["cid"], "label": r["label"], "game": r["game"], "book": r["book"],
                              "break_even": implied(r["price"]), "matched_to": []})
                    controls[r["cid"]] = g
                controls[r["cid"]]["matched_to"].append(cid)
    expected = [c for c in calls if c["market_prob"] is not None and c["result"] in ("win", "loss")]
    return {
        "moneyline_favorites_in_band": tally(fav_band),
        "moneyline_favorites_any_price": tally(fav_all),
        "price_matched_controls": tally(list(controls.values())),
        "price_matched_control_rows": sorted(controls.values(), key=lambda g: (g["game"], g["label"], g["cid"])),
        "top_favorite_per_window_in_band": tally(top_rows),
        "top_favorite_per_window_rows": top_rows,
        "market_expected_wins_on_bot_calls": {
            "graded_calls": len(expected),
            "expected_wins": sum(c["market_prob"] for c in expected),
            "actual_wins": sum(1 for c in expected if c["result"] == "win")},
    }


# ---------------------------------------------------------------- report

def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in row) + " |")
    return out


def record_text(t):
    if not t["n"]:
        return "none yet"
    bits = ["%d-%d" % (t["win"], t["loss"])]
    if t["push"]:
        bits.append("%d push" % t["push"])
    if t["void"]:
        bits.append("%d void" % t["void"])
    if t["unknown"]:
        bits.append("%d not graded yet" % t["unknown"])
    return ", ".join(bits)


def rate_text(t):
    if not t["decided"]:
        return "n/a"
    lo, hi = t["wilson95"]
    return "%s (95%% range %s to %s)" % (pct(t["win_rate"], 0), pct(lo, 0), pct(hi, 0))


def price_at(price, book):
    return "%s at %s" % (fmt_price(price), book_name(book))


def result_text(result, units_value, unit="units"):
    if result == "unknown":
        return "not graded yet"
    if result == "no bet":
        return "no bet"
    return "%s (%s %s)" % (result, units(units_value), unit)


def usage_lines(cmd):
    return [
        "Run these from the sprint folder. `J` stands for:",
        "",
        "    " + cmd,
        "",
        "- `J form` asks the questions one at a time.",
        "- `J list chiefs` shows every priced bet matching a word, with its id. `J list --calls` shows the bot's calls.",
        "- `J decide ID take --reason \"...\"`, or `pass`, or `alternative --alt OTHER_ID`. Must be before kickoff.",
        "- `J hypothesis --text \"...\" --event chiefs` registers a football hypothesis before kickoff.",
        "- `J ticket ID --book FanDuel --offered-price -115 --price -120 --stake 10 "
        "--placed-utc ACTUAL_PLACEMENT_TIME` records a ticket you placed. Replace ACTUAL_PLACEMENT_TIME "
        "with the date and time shown on your own ticket, including its timezone. The accepted price is `--price`.",
        "- `J settlement TICKET_ID --gross-return AMOUNT --outcome OUTCOME --confirmed` records "
        "what the sportsbook returned, including any refunded stake. Find individual ticket IDs with `J grade`.",
        "- `J control ID CONTROL_ID --rule \"...\" --book betmgm` pairs a bet with one matched control before kickoff.",
        "- `J research --title \"...\" --status rejected --summary \"...\" --evidence PATH` adds a tested idea to the register.",
        "- `J final chiefs --home 20 --away 27 --source \"ESPN box score\"` records a result. `J report` rewrites this page.",
    ]


def render_report(state, now, cmd):
    ev = evaluate(state)
    counts, problems = state.j.verify()
    roles = {}
    for r in state.predictions:
        roles[r["role"]] = roles.get(r["role"], 0) + 1
    captures = sorted(set(r["source"]["captured_utc"] for r in state.predictions
                          if r["role"] == "pool" and r["source"].get("captured_utc")))
    L = ["# Pregame journal: evaluation", "",
         "Written %s by `journal.py report`. Journal integrity: %s." % (
             stamp(now), "OK, every line checks out" if not problems else "FAILED, see below"), ""]
    for p in problems:
        L.append("- %s" % p)
    L += ["**What this is.** A local record of what the bot said before kickoff, what you decided and why, "
          "any ticket you report, and what happened. Original entries are never rewritten. It talks to no "
          "sportsbook and places nothing. One unit means one flat stake per bet. Later prices and estimated "
          "value are shown for information; they never choose a bet. Nothing here is a profit claim.", "",
          "## Use it", ""] + usage_lines(cmd) + ["", "## Where it stands", ""]
    L += md_table(["Item", "Count"], [
        ["Games loaded", len(state.events)],
        ["Priced bets kept as controls (every exact line in the capture)", roles.get("pool", 0)],
        ["Bot calls recorded", len(ev["calls"])],
        ["Bets you added yourself", roles.get("manual", 0)],
        ["Hypotheses registered", len(state.hypotheses)],
        ["Your decisions (pregame)", len(ev["decisions"])],
        ["Your tickets", len(ev["tickets"])],
        ["Games with a final", len(state.scores)],
    ])
    if captures:
        L += ["", "Price capture times: %s. Prices move; each row keeps the time of its own quote." % ", ".join(captures)]

    L += ["", "## Hypotheses", ""]
    if state.hypotheses:
        L += md_table(["Id", "By", "Registered (UTC)", "Before kickoff", "Hypothesis", "sha256 of the text"],
                      [[h["hypothesis_id"], h["by"], h["recorded_utc"], "yes" if h["pregame"] else "NO, after the fact",
                        h["text"], h["text_sha256"][:16] + "..."] for h in state.hypotheses])
    else:
        L.append("None registered yet.")

    L += ["", "## Bot calls, as first recorded", ""]
    if ev["calls"]:
        rows = []
        for c in ev["calls"]:
            rows.append([c["short_game"], c["label"], price_at(c["price"], c["book"]), c["quote_utc"] or "not given",
                         pct(c["market_prob"]), pct(c["breakeven"]), pct(c["est_value_per_unit"]),
                         result_text(c["result"], c["units"]) + ("" if c["pregame_verified"] else " [recorded after kickoff]")])
        L += md_table(["Game", "Call", "Price", "Quote time (UTC)", "Market's chance", "Break-even", "Est. value (info)", "Result"], rows)
    else:
        L.append("No bot call has been recorded yet. When the picker writes its selection file, load it with "
                 "`J import-calls PATH` before kickoff.")

    L += ["", "## Your decisions", ""]
    if ev["decisions"]:
        rows = []
        for r in ev["decisions"]:
            yours = "no bet" if r["action"] == "pass" else "%s, %s" % (
                r["your_label"], fmt_price(r["your_price"]) + (" (your price)" if r["chosen_price"] is not None else ""))
            rows.append([r["short_game"], "%s, %s%s" % (r["label"], price_at(r["price"], r["book"]),
                                                       "" if r["bot_is_call"] else " (not a bot call)"),
                         r["action"] + (" (changed %d times)" % (r["entries"] - 1) if r["entries"] > 1 else ""),
                         yours, r["reason"], result_text(r["bot_result"], r["bot_units"]),
                         result_text(r["result"], r["units"])])
        L += md_table(["Game", "Bot's original", "You", "Your bet", "Your reason", "Bot's line result", "Your result"], rows)
    else:
        L.append("None yet.")
    if ev["late_decisions"]:
        L += ["", "Entered after kickoff, kept but not scored: " + "; ".join(
            "%s on %s (%s)" % (d["action"], d["label"], d["recorded_utc"]) for d in ev["late_decisions"]) + "."]

    L += ["", "## Your tickets (only what you reported)", ""]
    if ev["tickets"]:
        rows = []
        for t in ev["tickets"]:
            rows.append([t["short_game"], t["label"] + (" [different line from the bot's %s]" % t["bot_label"] if t["line_differs"] else ""),
                         "%s at %s%s%s" % (fmt_price(t["price"]), t["book"],
                                           "" if t["accepted_in_band"] else " [outside selection band]",
                                           " [below the issued minimum]" if t["meets_issued_minimum"] is False else ""),
                         "not recorded" if t.get("offered_price") is None else fmt_price(t["offered_price"]),
                         "%g %s" % (t["stake"], t["stake_unit"]),
                         price_at(t["bot_price"], t["bot_book"]),
                         (t["placed_utc_reported"] or "placement unknown") + (" [entered after kickoff]"
                          if not t["recorded_before_kickoff"] else "") + " / recorded " + t["recorded_utc"],
                         result_text(t["result"], t["units"], t["stake_unit"]),
                         ("%s: %g gross, %+.2f net" % (t["settlement"]["outcome"],
                          t["settlement"]["gross_return"], t["actual_net"])) if t["settlement"] else "Pending"])
        L += md_table(["Game", "Ticket", "Your price (graded)", "Price the book showed you", "Stake", "Bot's original price",
                       "Placed (your report)", "Score-based estimate", "Book-confirmed return"], rows)
        for unit, total in ev["score"]["confirmed_ticket_returns"].items():
            L.append("Confirmed returns in %s: %d settled, %d pending, %g stake on settled tickets, "
                     "%g gross returned, %+.2f net." % (unit, total["confirmed_count"], total["pending_count"],
                     total["confirmed_stake"], total["gross_return"], total["net_return"]))
    else:
        L.append("None reported.")

    s = ev["score"]
    L += ["", "## Scorecard (one unit per bet, at the recorded price)", ""]
    rows = [["Bot calls", record_text(s["bot_calls"]), rate_text(s["bot_calls"]), units(s["bot_calls"]["units"])],
            ["Bets you took", record_text(s["your_takes"]), rate_text(s["your_takes"]), units(s["your_takes"]["units"])],
            ["Your alternatives", record_text(s["your_alternatives"]), rate_text(s["your_alternatives"]), units(s["your_alternatives"]["units"])],
            ["Bets you passed (what they did anyway)", record_text(s["bets_you_passed"]), rate_text(s["bets_you_passed"]), units(s["bets_you_passed"]["units"])]]
    for name in ("take", "pass", "alternative", "no decision"):
        t = s["bot_calls_by_your_decision"][name]
        rows.append(["Bot calls where you chose: %s" % name, record_text(t), rate_text(t), units(t["units"])])
    for unit, t in sorted(s["your_tickets"].items()):
        rows.append(["Your tickets, score-based estimate (%s)" % unit, record_text(t), rate_text(t),
                     "%s %s" % (units(t["units"]), unit)])
    L += md_table(["Group", "Won-lost", "Win rate", "Units"], rows)

    b = s["benchmarks"]
    m = b["market_expected_wins_on_bot_calls"]
    L += ["", "## Benchmarks from the same slate", ""]
    L += md_table(["Benchmark", "Won-lost", "Win rate", "Units"], [
        ["Every moneyline favorite priced inside -200 to +200", record_text(b["moneyline_favorites_in_band"]),
         rate_text(b["moneyline_favorites_in_band"]), units(b["moneyline_favorites_in_band"]["units"])],
        ["Every moneyline favorite at any price", record_text(b["moneyline_favorites_any_price"]),
         rate_text(b["moneyline_favorites_any_price"]), units(b["moneyline_favorites_any_price"]["units"])],
        ["Price-matched controls (same market, other games, break-even within 2.5 points)",
         record_text(b["price_matched_controls"]), rate_text(b["price_matched_controls"]),
         units(b["price_matched_controls"]["units"])],
        ["The most likely in-band moneyline in each window (the picker's frozen control)",
         record_text(b["top_favorite_per_window_in_band"]), rate_text(b["top_favorite_per_window_in_band"]),
         units(b["top_favorite_per_window_in_band"]["units"])],
    ])
    L += ["", "Price-matched controls found for the bets acted on: %d. Each is graded once, at its own recorded "
              "price, one unit. `J grade` lists every one." % len(b["price_matched_control_rows"])]
    if m["graded_calls"]:
        L += ["", "The market's own vig-free numbers expected %.1f wins from the %d graded bot calls; there were %d."
              % (m["expected_wins"], m["graded_calls"], m["actual_wins"])]

    later = [r for r in ev["calls"] + [d for d in ev["decisions"] if not d["bot_is_call"]] if r["later_price"]]
    L += ["", "## Later prices (information only)", ""]
    if later:
        rows = []
        for r in later:
            lp = r["later_price"]
            rows.append([r["short_game"], r["label"], price_at(r["price"], r["book"]), price_at(lp["price"], lp["book"]),
                         "%d min before kickoff" % lp["minutes_before_kickoff"],
                         "n/a" if lp["points_vs_breakeven"] is None else "%+.1f points" % (100.0 * lp["points_vs_breakeven"])])
        L += md_table(["Game", "Bet", "Recorded price", "Later best price, same exact line", "When",
                       "Later market chance minus your break-even"], rows)
    else:
        L.append("No later capture has been loaded. If the line moved, there is no later price for the old line, and none is borrowed.")

    L += ["", "## Matched controls registered before kickoff", ""]
    if ev["controls"]:
        rows = []
        for p in ev["controls"]:
            rows.append(["%s (%s)" % (p["label"], p["short_game"]), price_at(p["price"], p["book"]),
                         result_text(p["result"], p["units"], "units"),
                         "%s (%s)" % (p["control_label"], p["control_short_game"]),
                         price_at(p["control_price"], p["control_book"]),
                         result_text(p["control_result"], p["control_units"], "units"),
                         "%s, %s%s" % (p["by"], p["recorded_utc"],
                                       "" if p["pregame_verified"] else ", AFTER KICKOFF, not scored")])
        L += md_table(["Bet", "Recorded price", "Result", "Matched control (not a bet)", "Control price",
                       "Control result", "Registered"], rows)
        L += ["", "A control is a comparison picked by a stated rule before the games. It is graded at its own "
                  "recorded price and is never a recommendation."]
        for p in ev["controls"]:
            L.append("- Rule for %s: %s" % (p["label"], p["rule"]))
    else:
        L.append("None registered.")

    L += ["", "## Research register (ideas tested; kept or retired)", ""]
    if ev["research"]:
        for r in ev["research"]:
            L.append("- %s, %s: %s (recorded %s by %s). %s Evidence: `%s`.%s %s" % (
                r["research_id"], r["status"].upper(), r["title"], r["recorded_utc"], r["by"], r["summary"],
                r["evidence"], (" Scope: " + r["scope_note"]) if r["scope_note"] else "",
                "A live rule was changed." if r["changed_live_rule"] else "No live rule was changed."))
    else:
        L.append("Nothing registered yet.")

    L += ["", "## Honest limits", "",
          "- One Sunday is a tiny sample. A win rate from a handful of bets says almost nothing; the 95% range shows how wide the doubt is.",
          "- The market's chance is the middle of the books' prices with the bookmaker's margin removed. It is the market's opinion, not proof of value.",
          "- A bet is graded only when a final was entered with a source. First-half bets need the half-time score and player bets need the player's number; otherwise they stay \"not graded yet\".",
          "- Prices come from a saved capture. Nothing here confirms the price a book would actually offer you in Louisiana at the moment you bet.",
          "- Tickets are only what you report. This tool has no access to any account.", ""]
    return "\n".join(L), ev


def default_report_path(journal):
    if os.path.abspath(journal.dir) == os.path.abspath(DEFAULT_DATA):
        return os.path.join(HERE, "EVALUATION.md")
    return os.path.join(journal.dir, "EVALUATION.md")


def run_command_text(journal):
    base = "/usr/bin/python3 -I -B nfl/slate/experiment/journal.py"
    if os.path.abspath(journal.dir) != os.path.abspath(DEFAULT_DATA):
        base += " --data " + journal.dir
    return base


def write_report(journal, now, out=None):
    state = State(journal)
    text, ev = render_report(state, now, run_command_text(journal))
    out = out or default_report_path(journal)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, out)
    return out, ev


# ---------------------------------------------------------------- listing and the form

def search(state, words, now, calls_only=False, window=None, include_started=False, band_only=False):
    words = [norm_text(w) for w in words if norm_text(w)]
    rows = []
    for cid in state.records:
        rec = state.original(cid)
        if calls_only and rec["role"] != "call":
            continue
        if window and rec["window"] != window:
            continue
        if band_only and not in_band(rec["price"]):
            continue
        if not include_started and parse_utc(rec["kickoff_utc"]) <= now:
            continue
        hay = norm_text(" ".join((rec["label"], rec["game"], rec["identity"]["market"], rec["cid"])))
        if all(w in hay for w in words):
            rows.append(rec)
    rows.sort(key=lambda r: (0 if r["role"] == "call" else 1,) + sort_key(r))
    return rows


def line_for(rec, state):
    pool = state.pool(rec["cid"])
    prob = pool["market_prob"] if pool else None
    tag = {"call": "BOT CALL", "manual": "yours", "pool": ""}[rec["role"]]
    return "%s  %-18s %-52s %-22s chance %-6s %s%s" % (
        rec["cid"][:8], short_game(rec["home_team"], rec["away_team"]), rec["label"][:52],
        price_at(rec["price"], rec["book"]), pct(prob), "" if in_band(rec["price"]) else "[outside -200/+200] ", tag)


def show_text(rec, state, now=None):
    d = describe(rec, state)
    kick = parse_utc(rec["kickoff_utc"])
    out = ["%s  %s" % (rec["cid"], rec["label"]),
           "  Game: %s. Kickoff %s (%s), %s window." % (rec["game"], rec["kickoff_utc"], central_label(kick),
                                                     WINDOW_NAMES[rec["window"]]),
           "  Original record: %s, quoted %s. Basis: %s. Journal line %d, written %s."
           % (price_at(rec["price"], rec["book"]), rec["quote_utc"] or "time not given", rec["price_basis"],
              rec["seq"], rec["recorded_utc"])]
    pool = state.pool(rec["cid"])
    if pool:
        out.append("  Every book at this exact line: " + ", ".join(
            "%s %s" % (book_name(b), fmt_price(q["price"])) for b, q in sorted(pool["quotes"].items())) + ".")
    out.append("  Market's chance with the margin removed: %s (%d books). Break-even at %s: %s. "
               "Estimated value per unit: %s (information only)."
               % (pct(d["market_prob"]), d["market_prob_books"], fmt_price(rec["price"]), pct(d["breakeven"]),
                  pct(d["est_value_per_unit"])))
    out.append("  Inside the -200 to +200 price band: %s." % ("yes" if d["in_band"] else "no"))
    if rec.get("quote_utc"):
        age = ((now or utc_now()) - parse_utc(rec["quote_utc"])).total_seconds() / 60
        if age >= 0:
            out.append("  Saved quote age at viewing: %.0f minutes. Recheck the exact line before using it." % age)
    return "\n".join(out)


def run_form(journal, ask=input, out=print, clock=utc_now):
    """Question-and-answer entry for Matthew. Returns the number of entries written."""
    written = 0
    out("Pregame journal. Your answers are saved on this computer only. Nothing is sent anywhere,")
    out("and no bet is placed. Press Enter on an empty line to finish.")
    shown = None
    while True:
        state, now = State(journal), clock()
        if shown is None:
            shown = search(state, [], now, calls_only=True)
            if shown:
                out("\nThe bot's calls that have not kicked off:")
            else:
                out("\nNo bot call is loaded yet (or all have kicked off).")
        if shown:
            for i, rec in enumerate(shown[:25], 1):
                out("%2d. %s" % (i, line_for(rec, state)))
            if len(shown) > 25:
                out("    ... %d more. Add a word to narrow it." % (len(shown) - 25))
        ans = ask("\nType a number from the list, or a team or player name to search every priced bet: ").strip()
        if not ans or ans.lower() in ("q", "quit", "exit"):
            break
        if not ans.isdigit():
            shown = search(state, ans.split(), now)
            if not shown:
                out("Nothing priced matches %r." % ans)
            continue
        if not shown or not (1 <= int(ans) <= min(len(shown), 25)):
            out("That number is not on the list.")
            continue
        rec = shown[int(ans) - 1]
        out("\n" + show_text(rec, state, now))
        act = ask("Take it, pass, or prefer an alternative? (t/p/a, Enter to go back): ").strip().lower()
        action = {"t": "take", "take": "take", "p": "pass", "pass": "pass", "a": "alternative",
                  "alternative": "alternative"}.get(act)
        if not action:
            shown = None
            continue
        alt_cid = None
        if action == "alternative":
            words = ask("Which bet instead? Type a team or player name: ").strip()
            options = [r for r in search(state, words.split(), now) if r["cid"] != rec["cid"]][:25]
            if not options:
                out("Nothing priced matches. To use a bet that is not listed, add it first with the 'add' command.")
                continue
            for i, r in enumerate(options, 1):
                out("%2d. %s" % (i, line_for(r, state)))
            pick = ask("Number of the bet you prefer: ").strip()
            if not pick.isdigit() or not (1 <= int(pick) <= len(options)):
                out("That number is not on the list.")
                continue
            alt_cid = options[int(pick) - 1]["cid"]
        reason = ask("Your reason, in a sentence: ").strip()
        hyp_id = None
        hyp = ask("A football hypothesis behind it that the result could prove wrong (Enter to skip): ").strip()
        try:
            if hyp:
                h = record_hypothesis(journal, hyp, clock(), cids=[alt_cid or rec["cid"]])
                hyp_id = h["hypothesis_id"]
                written += 1
                out("Hypothesis %s registered at %s." % (hyp_id, h["recorded_utc"]))
            already = any(d["cid"] == rec["cid"] and d["by"] == "matthew" and d["pregame"] for d in state.decisions)
            revise = False
            if already:
                revise = ask("You already answered on this bet. Record a change of mind? (y/N): ").strip().lower() in ("y", "yes")
                if not revise:
                    continue
            d = record_decision(journal, rec["cid"], action, reason, clock(), alt=alt_cid,
                                hypothesis=hyp_id, revise=revise)
            written += 1
            out("Saved: %s on %s at %s." % (action, rec["label"], d["recorded_utc"]))
            if action != "pass":
                target = alt_cid or rec["cid"]
                if ask("Did you place a real ticket on this yourself? (y/N): ").strip().lower() in ("y", "yes"):
                    book = ask("Sportsbook: ").strip()
                    price = float(ask("Your price (for example -120 or +160): ").strip())
                    stake = ask("Stake in dollars: ").strip()
                    placed = ask("Actual placement time with timezone (for example 2026-11-15T13:05:00Z): ").strip()
                    t = record_ticket(journal, target, book, int(price) if price.is_integer() else price, stake,
                                      clock(), placed_utc=placed)
                    written += 1
                    out("Ticket saved at %s. The bot's original line is unchanged." % t["recorded_utc"])
        except (JournalError, ValueError) as err:
            out("Not saved: %s" % err)
        shown = None
    out("\n%d entr%s written. Run 'report' to refresh EVALUATION.md." % (written, "y" if written == 1 else "ies"))
    return written


# ---------------------------------------------------------------- command line

def _num(text):
    x = float(text)
    return int(x) if x.is_integer() else x


def build_parser():
    p = argparse.ArgumentParser(
        prog="journal.py",
        description="Pregame experiment and evaluation journal. Local files only; no accounts, keys or bets.")
    p.add_argument("--data", default=DEFAULT_DATA, help="journal folder (default: data/ beside this file)")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("import-capture", help="record every exact priced bet in a saved price capture")
    s.add_argument("path")
    s = sub.add_parser("import-calls", help="record the bot's posted calls from the picker's selection file")
    s.add_argument("path")
    s.add_argument("--late", action="store_true", help="keep calls whose game has started, flagged")
    s = sub.add_parser("add", help="add a bet of your own that is not in the capture")
    s.add_argument("--event", required=True)
    s.add_argument("--market", required=True, help="h2h, spreads, totals, team_totals, totals_h1, player_pass_yds ...")
    s.add_argument("--side", required=True, help="team name, or Over / Under")
    s.add_argument("--subject", default="", help="team or player for team totals and player bets")
    s.add_argument("--point", type=float)
    s.add_argument("--price", type=_num, required=True)
    s.add_argument("--book", required=True)
    s.add_argument("--quote-utc")
    s.add_argument("--note", default="")
    s = sub.add_parser("list", help="list priced bets that have not kicked off")
    s.add_argument("words", nargs="*")
    s.add_argument("--calls", action="store_true", help="only the bot's calls")
    s.add_argument("--window", choices=sorted(WINDOW_NAMES))
    s.add_argument("--band", action="store_true", help="only prices inside -200 to +200")
    s.add_argument("--all", action="store_true", help="include games that have started")
    s.add_argument("--limit", type=int, default=40)
    s = sub.add_parser("show", help="show one bet in full")
    s.add_argument("id")
    s = sub.add_parser("hypothesis", help="register a football hypothesis before kickoff")
    s.add_argument("--text", required=True)
    s.add_argument("--event", action="append", default=[])
    s.add_argument("--id", action="append", default=[], dest="ids")
    s.add_argument("--by", default="matthew")
    s.add_argument("--late", action="store_true")
    s = sub.add_parser("decide", help="record take, pass or alternative, with your reason")
    s.add_argument("id")
    s.add_argument("action", choices=ACTIONS)
    s.add_argument("--reason", required=True)
    s.add_argument("--alt", help="id of the bet you prefer (with 'alternative')")
    s.add_argument("--hypothesis", help="id of a registered hypothesis")
    s.add_argument("--price", type=_num, help="the price you would take it at, if different from the bot's")
    s.add_argument("--book")
    s.add_argument("--by", default="matthew")
    s.add_argument("--revise", action="store_true")
    s.add_argument("--late", action="store_true")
    s = sub.add_parser("ticket", help="record a bet you placed yourself")
    s.add_argument("id")
    s.add_argument("--book", required=True)
    s.add_argument("--price", type=_num, required=True)
    s.add_argument("--stake", type=float, required=True)
    s.add_argument("--unit", default="dollars")
    s.add_argument("--point", type=float, help="your line, if different from the bot's")
    s.add_argument("--placed-utc", required=True)
    s.add_argument("--offered-price", type=_num,
                   help="the price the book showed you (kept for information; the ticket is graded at --price)")
    s.add_argument("--note", default="")
    s = sub.add_parser("settlement", help="record the book's gross return for one ticket")
    s.add_argument("ticket_id")
    s.add_argument("--gross-return", type=float, required=True, help="total returned, including stake")
    s.add_argument("--outcome", choices=SETTLEMENT_OUTCOMES, required=True)
    s.add_argument("--confirmed", action="store_true", help="the operator displayed this return")
    s.add_argument("--prior-sha", help="current settlement hash when correcting an entry")
    s.add_argument("--note", default="")
    s = sub.add_parser("final", help="record a final score")
    s.add_argument("event")
    s.add_argument("--home", type=int, required=True)
    s.add_argument("--away", type=int, required=True)
    s.add_argument("--h1-home", type=int)
    s.add_argument("--h1-away", type=int)
    s.add_argument("--source", required=True)
    s = sub.add_parser("player-result", help="record a player's final number")
    s.add_argument("event")
    s.add_argument("--player", required=True)
    s.add_argument("--market", required=True)
    s.add_argument("--value", type=float, required=True)
    s.add_argument("--source", required=True)
    s = sub.add_parser("void", help="mark a bet void (for example the player did not play)")
    s.add_argument("id")
    s.add_argument("--reason", required=True)
    s.add_argument("--source", required=True)
    s = sub.add_parser("import-finals", help="load finals from an agent-made file")
    s.add_argument("path")
    s = sub.add_parser("import-close", help="load a later capture as later prices (information only)")
    s.add_argument("path")
    s = sub.add_parser("control", help="pair a bet with one matched control, before kickoff")
    s.add_argument("id")
    s.add_argument("control_id")
    s.add_argument("--rule", required=True, help="the matching rule, in a sentence")
    s.add_argument("--book", help="the book whose recorded price is the control's price")
    s.add_argument("--price", type=_num, help="optional check: must equal the recorded price")
    s.add_argument("--by", default="codex")
    s.add_argument("--source", default="")
    s.add_argument("--late", action="store_true")
    s = sub.add_parser("research", help="add a tested idea and its outcome to the research register")
    s.add_argument("--title", required=True)
    s.add_argument("--status", required=True, choices=RESEARCH_STATUSES)
    s.add_argument("--summary", required=True)
    s.add_argument("--evidence", required=True)
    s.add_argument("--scope-note", default="")
    s.add_argument("--by", default="experiment owner")
    s.add_argument("--changed-live-rule", action="store_true")
    s = sub.add_parser("report", help="write EVALUATION.md")
    s.add_argument("--out")
    s = sub.add_parser("grade", help="print the scorecard as JSON")
    sub.add_parser("verify", help="check that no journal line was changed")
    sub.add_parser("status", help="counts and the registered hypotheses")
    sub.add_parser("form", help="answer questions one at a time")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 0
    j = Journal(args.data)
    now = utc_now()
    try:
        if args.cmd == "import-capture":
            r = import_capture(j, args.path, now)
            print("Capture of %s: %d exact bets, %d newly recorded, %d already in the journal."
                  % (r["captured_utc"], r["contracts_in_capture"], r["new_records"], r["already_recorded"]))
            print("Quotes left out: %s" % ", ".join("%s %d" % (k, v) for k, v in sorted(r["skipped_quotes"].items())))
        elif args.cmd == "import-calls":
            r = import_calls(j, args.path, now, late=args.late)
            print("%d calls in the file: %d newly recorded, %d already in the journal, %d refused."
                  % (r["calls_in_file"], r["new_records"], r["already_recorded"], len(r["refused"])))
            for line in r["refused"]:
                print("  refused, %s" % line)
            if r["refused"]:
                return 2
        elif args.cmd == "add":
            rec = add_manual(j, args.event, args.market, args.side, args.price, args.book, now,
                             subject=args.subject, point=args.point, quote_utc=args.quote_utc, note=args.note)
            print("Added %s  %s at %s." % (rec["cid"], rec["label"], price_at(rec["price"], rec["book"])))
        elif args.cmd == "list":
            state = State(j)
            rows = search(state, args.words, now, calls_only=args.calls, window=args.window,
                          include_started=args.all, band_only=args.band)
            for rec in rows[:args.limit]:
                print(line_for(rec, state))
            print("%d shown of %d matching." % (min(len(rows), args.limit), len(rows)))
        elif args.cmd == "show":
            state = State(j)
            print(show_text(state.original(state.resolve(args.id)), state, now))
        elif args.cmd == "hypothesis":
            h = record_hypothesis(j, args.text, now, by=args.by, events=args.event, cids=args.ids, late=args.late)
            print("Registered %s at %s. sha256 of the text: %s" % (h["hypothesis_id"], h["recorded_utc"], h["text_sha256"]))
        elif args.cmd == "decide":
            d = record_decision(j, args.id, args.action, args.reason, now, by=args.by, alt=args.alt,
                                hypothesis=args.hypothesis, price=args.price, book=args.book,
                                revise=args.revise, late=args.late)
            print("Saved: %s on %s at %s%s." % (d["action"], d["bot_original"]["label"], d["recorded_utc"],
                                               "" if d["pregame"] else " (after kickoff, not scored)"))
        elif args.cmd == "ticket":
            t = record_ticket(j, args.id, args.book, args.price, args.stake, now, unit=args.unit,
                              point=args.point, placed_utc=args.placed_utc, note=args.note,
                              offered_price=args.offered_price)
            print("Ticket %s saved at %s: %s at %s, %g %s%s."
                  % (t["ticket_id"], t["recorded_utc"], fmt_price(t["price"]), t["book"], t["stake"],
                     t["stake_unit"], "" if t["accepted_in_band"] else " (accepted price outside the pick band)"))
        elif args.cmd == "settlement":
            row = record_settlement(j, args.ticket_id, args.gross_return, args.outcome, now,
                                    confirmed=args.confirmed, prior_sha=args.prior_sha, note=args.note)
            print("Confirmed %g %s gross for %s. Settlement revision %s."
                  % (row["gross_return"], row["stake_unit"], row["ticket_id"], row["sha"]))
        elif args.cmd == "final":
            f = record_final(j, args.event, args.home, args.away, args.source, now,
                             h1_home=args.h1_home, h1_away=args.h1_away)
            print("Final saved: %s %d, %s %d." % (f["away_team"], f["away_score"], f["home_team"], f["home_score"]))
        elif args.cmd == "player-result":
            f = record_player_result(j, args.event, args.player, args.market, args.value, args.source, now)
            print("Saved: %s, %s = %g." % (f["player"], f["market"], f["value"]))
        elif args.cmd == "void":
            record_void(j, args.id, args.reason, args.source, now)
            print("Marked void.")
        elif args.cmd == "import-finals":
            r = import_finals(j, args.path, now)
            print("%d finals recorded." % r["finals_recorded"])
            for line in r["notes"]:
                print("  %s" % line)
        elif args.cmd == "import-close":
            r = import_close(j, args.path, now)
            print(", ".join("%s: %d" % (k.replace("_", " "), v) for k, v in r.items()))
        elif args.cmd == "control":
            c = record_control(j, args.id, args.control_id, args.rule, now, by=args.by, book=args.book,
                               price=args.price, source=args.source, late=args.late)
            print("Control saved at %s: graded at %s (%s). It is a comparison, not a bet."
                  % (c["recorded_utc"], fmt_price(c["price"]), c["book"]))
        elif args.cmd == "research":
            r = record_research(j, args.title, args.status, args.summary, args.evidence, now, by=args.by,
                                scope_note=args.scope_note, changed_live_rule=args.changed_live_rule)
            print("Research note %s saved at %s: %s, %s."
                  % (r["research_id"], r["recorded_utc"], r["status"].upper(), r["title"]))
        elif args.cmd == "report":
            out, ev = write_report(j, now, args.out)
            s = ev["score"]
            print("Wrote %s" % out)
            print("Bot calls: %s. Bets you took: %s. Tickets: %d."
                  % (record_text(s["bot_calls"]), record_text(s["your_takes"]), len(ev["tickets"])))
        elif args.cmd == "grade":
            print(json.dumps(evaluate(State(j)), indent=2, sort_keys=True))
        elif args.cmd == "verify":
            counts, problems = j.verify()
            for name in JOURNALS:
                print("%-12s %s" % (name, "FAILED" if counts[name] is None else "%d lines, intact" % counts[name]))
            for line in problems:
                print(line)
            if problems:
                return 1
        elif args.cmd == "status":
            state = State(j)
            roles = {}
            for r in state.predictions:
                roles[r["role"]] = roles.get(r["role"], 0) + 1
            print("Games %d. Priced bets %d. Bot calls %d. Your own bets %d. Hypotheses %d. Decisions %d. Tickets %d. Finals %d."
                  % (len(state.events), roles.get("pool", 0), roles.get("call", 0), roles.get("manual", 0),
                     len(state.hypotheses), len(state.decisions), len(state.tickets), len(state.scores)))
            for h in state.hypotheses:
                print("  %s  %s  %s" % (h["hypothesis_id"], h["recorded_utc"], h["text"]))
            print("Registered controls %d. Research notes %d." % (len(state.controls), len(state.research)))
            for r in state.research:
                print("  %s  %s  %s  %s" % (r["research_id"], r["recorded_utc"], r["status"].upper(), r["title"]))
        elif args.cmd == "form":
            run_form(j)
    except JournalError as err:
        print("Refused: %s" % err)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
