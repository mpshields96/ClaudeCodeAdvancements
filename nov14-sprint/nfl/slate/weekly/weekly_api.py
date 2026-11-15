"""weekly_api: dated (non-Nov-15) screen, immutable review intake and published card.

Paper only, advisory only. No network, no keys, stdlib only (Python 3.9, run with -I).
Reads weekly_inputs/<date>/{schedule.json,odds.json,captures/*.json} (the front-door owner's files).
Writes only under weekly/reviews/, weekly/annotations/ and weekly/published/. See API.md for the contract.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import statistics
import sys
import tempfile
from datetime import date as _date, datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

API = "weekly/1"
UTC = timezone.utc
CENTRAL = ZoneInfo("America/Chicago")
HERE = Path(__file__).resolve().parent
INPUTS = HERE.parent / "weekly_inputs"
REVIEWS = HERE / "reviews"
ANNOTATIONS = HERE / "annotations"
PUBLISHED = HERE / "published"
AUTHOR_KINDS = ("human", "claude", "codex", "other")
STANCES = ("concern", "supports", "info")
FIRST_DATE = "2026-11-22"
MAX_PER_WINDOW = 2
MAX_PER_DATE = 6
STALE_SECONDS = 1800
BOOKS = ("betmgm", "betrivers", "draftkings", "espnbet", "fanduel")
WINDOWS = ("early", "late", "night")
WINDOW_LABELS = {"early": "Morning / noon", "late": "Afternoon", "night": "Sunday night"}
# Same supported market keys and periods as selection_markets.MARKETS (compared in the tests).
MARKETS = {
    "h2h": ("moneyline", "full_game"), "spreads": ("spread", "full_game"),
    "totals": ("total", "full_game"), "team_totals": ("team_total", "full_game"),
    "h2h_h1": ("moneyline", "first_half"), "spreads_h1": ("spread", "first_half"),
    "totals_h1": ("total", "first_half"), "team_totals_h1": ("team_total", "first_half"),
    "player_pass_yds": ("prop", "full_game"), "player_rush_yds": ("prop", "full_game"),
    "player_reception_yds": ("prop", "full_game"),
}
PROP_NAMES = {"player_pass_yds": "passing yards", "player_rush_yds": "rushing yards",
              "player_reception_yds": "receiving yards"}
MAIN = ("h2h", "spreads", "totals")
ZERO = "0" * 64


class Refused(Exception):
    def __init__(self, code, detail):
        Exception.__init__(self, code + ": " + detail)
        self.code, self.detail = code, detail


def clock():
    return datetime.now(UTC)


# ---------------------------------------------------------------- small helpers
def parse_ts(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be text")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timezone required")
    return t.astimezone(UTC)


def ts(t):
    return t.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def is_price(x):
    return type(x) is int and abs(x) >= 100


def in_band(x):
    return type(x) is int and 100 <= abs(x) <= 200


def dec(x):
    return 1 + x / 100 if x > 0 else 1 + 100 / abs(x)


def key_for(event_id, market, subject, side, line):
    bits = [event_id, MARKETS[market][1], market, subject, side, format(line, ".15g") if line is not None else "-"]
    return ":".join(quote(str(b), safe="") for b in bits)


def window_of(kick):
    hour = kick.astimezone(CENTRAL).hour
    return "early" if hour < 14 else "late" if hour < 18 else "night"


def central_text(t):
    return t.astimezone(CENTRAL).strftime("%a %-I:%M %p CT")


def url_ok(url):
    if not isinstance(url, str) or re.search(r'[\s{}<>"\\]', url):
        return False
    u = urlsplit(url)
    return (u.scheme == "https" and bool(u.hostname) and "." in u.hostname and not u.username
            and not u.password and not re.search(r"(?:^|&)(?:api_?key|token|auth)=", u.query, re.I))


def check_date(day):
    if not isinstance(day, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise Refused("BAD_DATE", "date must look like 2026-11-22")
    try:
        d = _date.fromisoformat(day)
    except ValueError:
        raise Refused("BAD_DATE", "not a real calendar date: " + day)
    if d.weekday() != 6 or day < FIRST_DATE:
        raise Refused("BAD_DATE", "only Sundays on or after %s are supported (the Nov 15 slate has its own engine)" % FIRST_DATE)
    return day


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class lock:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = self.path.open("a")
        fcntl.flock(self.f, fcntl.LOCK_EX)

    def __exit__(self, *exc):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


# ---------------------------------------------------------------- inputs
def load_json_file(p):
    raw = p.read_bytes()
    return raw, json.loads(raw)


def editions(day):
    """Every odds edition for the date, oldest first. captures/ holds them; odds.json is a fallback."""
    base = INPUTS / day
    if not (base / "odds.json").is_file() or not (base / "schedule.json").is_file():
        raise Refused("NO_INPUTS", "weekly_inputs/%s/{schedule.json,odds.json} are missing; the front-door owner acquires them (sunday_intake.acquire)" % day)
    files = sorted((base / "captures").glob("*.json")) if (base / "captures").is_dir() else []
    if not files:
        files = [base / "odds.json"]
    out, skipped = [], []
    for p in files:
        try:
            raw, doc = load_json_file(p)
            if doc.get("day") != day or not isinstance(doc.get("games"), list):
                raise ValueError("not a capture for this date")
            out.append(dict(path=p, sha256=sha(raw), captured=parse_ts(doc["captured_utc"]), doc=doc))
        except (ValueError, KeyError, TypeError, OSError) as err:
            skipped.append("%s: %s" % (p.name, type(err).__name__))
    if not out:
        raise Refused("NO_INPUTS", "no readable odds capture for " + day)
    out.sort(key=lambda e: (e["captured"], e["path"].name))
    newest = out[-1]["sha256"]
    for e in out:
        e["is_latest"] = e["sha256"] == newest
        e["captured_utc"] = ts(e["captured"])
    return out, skipped


def resolve_edition(day, ref):
    eds, _ = editions(day)
    if ref in (None, "latest"):
        return eds[-1]
    want_sha = want_ts = None
    if isinstance(ref, dict):
        want_sha, want_ts = ref.get("sha256"), ref.get("captured_utc")
    elif isinstance(ref, str) and re.fullmatch(r"[a-f0-9]{64}", ref):
        want_sha = ref
    elif isinstance(ref, str):
        want_ts = ref
    else:
        raise Refused("EDITION_UNKNOWN", "edition must be 'latest', a captured_utc, a sha256, or {captured_utc, sha256}")
    for e in eds:
        ok_sha = want_sha is None or e["sha256"] == want_sha
        try:
            ok_ts = want_ts is None or parse_ts(want_ts) == e["captured"]
        except ValueError:
            ok_ts = False
        if ok_sha and ok_ts and (want_sha or want_ts):
            return e
    raise Refused("EDITION_UNKNOWN", "no capture in weekly_inputs/%s/captures matches %s" % (day, json.dumps(ref, sort_keys=True)))


def load_schedule(day):
    raw, doc = load_json_file(INPUTS / day / "schedule.json")
    index = {}
    for ev in doc.get("events", []):
        try:
            comp = ev["competitions"][0]
            names = frozenset(c["team"]["displayName"] for c in comp["competitors"])
            index[(names, ev["date"][:16])] = ev
        except (KeyError, IndexError, TypeError):
            continue
    return dict(sha256=sha(raw), doc=doc, index=index, events=len(doc.get("events", [])))


def _side(comp, which):
    for c in comp["competitors"]:
        if c.get("homeAway") == which:
            return c["team"]
    return {}


# ---------------------------------------------------------------- contracts and games
def build(day, edition):
    """Games and contracts for one edition. Pure function of the files; no clock except 'fresh' uses capture time."""
    doc, cap = edition["doc"], edition["captured"]
    sched = load_schedule(day)
    games, contracts, warnings = {}, {}, []
    present = {}
    for coll in ("games", "event_odds"):
        for e in doc.get(coll, []):
            try:
                eid, kick = e["id"], parse_ts(e["commence_time"])
                home, away = e["home_team"], e["away_team"]
            except (KeyError, ValueError, TypeError):
                warnings.append("a %s entry has no usable id, teams or kickoff; skipped" % coll)
                continue
            if not re.fullmatch(r"[a-f0-9]{32}", str(eid)):
                warnings.append("event id %s is not a 32-hex odds id; skipped" % eid)
                continue
            if coll == "games":
                ev = sched["index"].get((frozenset((home, away)), ts(kick)[:16]))
                comp = ev["competitions"][0] if ev else None
                venue = (comp or {}).get("venue") or {}
                games[eid] = dict(
                    event_id=eid, espn_event_id=(ev or {}).get("id"),
                    away=dict(name=away, abbr=_side(comp, "away").get("abbreviation") if comp else None),
                    home=dict(name=home, abbr=_side(comp, "home").get("abbreviation") if comp else None),
                    kickoff=kick, kickoff_utc=ts(kick), kickoff_ct=central_text(kick), window=window_of(kick),
                    ct_date=kick.astimezone(CENTRAL).date().isoformat(), neutral_site=(comp or {}).get("neutralSite"),
                    venue=venue.get("fullName"), books={}, missing=[] if ev else ["not in schedule.json"],
                    markets_present=set())
                if not ev:
                    warnings.append("%s at %s is in odds.json but not in schedule.json" % (away, home))
            g = games.get(eid)
            if g is None or (g["home"]["name"], g["away"]["name"], g["kickoff_utc"]) != (home, away, ts(kick)):
                warnings.append("event_odds entry %s does not match a base game; skipped" % eid)
                continue
            for bk in e.get("bookmakers", []):
                book = bk.get("key")
                if book not in BOOKS:
                    continue
                for m in bk.get("markets", []):
                    mk = m.get("key")
                    if mk not in MARKETS:
                        present.setdefault("unsupported:" + str(mk), 0)
                        continue
                    g["markets_present"].add(mk)
                    present[mk] = present.get(mk, 0) + 1
                    updated = m.get("last_update") or bk.get("last_update")
                    for o in m.get("outcomes", []):
                        _add_quote(contracts, g, mk, o, book, updated, cap, warnings)
    # Per-book freshness and best prices.
    for c in contracts.values():
        c["quotes"] = sorted(c["quotes"].values(), key=lambda q: q["book"])
        fresh = [q for q in c["quotes"] if q["fresh"]]
        c["best"] = _best(fresh)
        inb = [q for q in fresh if in_band(q["price"])]
        c["best_in_band"] = _best(inb)
    for c in contracts.values():
        c["no_vig"] = _no_vig(c, contracts)
        g = games[c["event_id"]]
        g["books"].update({q["book"]: q["updated_utc"] for q in c["quotes"]})
    return dict(sched=sched, games=games, contracts=contracts, warnings=warnings, present=present)


def _best(quotes):
    if not quotes:
        return None
    q = sorted(quotes, key=lambda x: (-dec(x["price"]), x["book"]))[0]
    return dict(book=q["book"], price=q["price"], updated_utc=q["updated_utc"], in_band=in_band(q["price"]))


def _add_quote(contracts, g, mk, o, book, updated, cap, warnings):
    price = o.get("price")
    if isinstance(price, float) and price.is_integer():
        price = int(price)
    if not is_price(price):
        return
    name, desc = o.get("name"), o.get("description") or ""
    point = o.get("point")
    kind = MARKETS[mk][0]
    if not isinstance(name, str) or not name:
        return
    if kind == "moneyline":
        if name not in (g["home"]["name"], g["away"]["name"]):
            return  # three-way or odd moneyline: different settlement, never mixed in
        subject, side, point = "", name, None
    elif kind == "spread":
        if name not in (g["home"]["name"], g["away"]["name"]) or isinstance(point, bool) or not isinstance(point, (int, float)):
            return
        subject, side, point = "", name, float(point)
    else:
        if name not in ("Over", "Under") or isinstance(point, bool) or not isinstance(point, (int, float)):
            return
        needs_subject = mk.startswith(("player_", "team_totals"))
        subject = desc if needs_subject else ""
        if needs_subject and not subject:
            return
        side, point = name, float(point)
    if point is not None and not -1000 <= point <= 1000:
        return
    cid = key_for(g["event_id"], mk, subject, side, point)
    c = contracts.get(cid)
    if c is None:
        c = contracts[cid] = dict(id=cid, event_id=g["event_id"], period=MARKETS[mk][1], market=mk, subject=subject,
                                  side=side, point=point, quotes={})
    try:
        upd = parse_ts(updated) if updated else None
    except ValueError:
        upd = None
    age = (cap - upd).total_seconds() if upd else None
    rec = dict(book=book, price=price, updated_utc=ts(upd) if upd else None, age_seconds_at_capture=age,
               fresh=age is not None and 0 <= age <= STALE_SECONDS, in_band=in_band(price))
    old = c["quotes"].get(book)
    if old is None or (rec["updated_utc"] or "") >= (old["updated_utc"] or ""):
        c["quotes"][book] = rec


def _opposite(c, contracts):
    mk = c["market"]
    kind = MARKETS[mk][0]
    if kind == "moneyline":
        for o in contracts.values():
            if o["event_id"] == c["event_id"] and o["market"] == mk and o["side"] != c["side"]:
                return o
        return None
    if kind == "spread":
        for o in contracts.values():
            if (o["event_id"] == c["event_id"] and o["market"] == mk and o["side"] != c["side"]
                    and o["point"] == -c["point"]):
                return o
        return None
    other = "Under" if c["side"] == "Over" else "Over"
    return contracts.get(key_for(c["event_id"], mk, c["subject"], other, c["point"]))


def _no_vig(c, contracts):
    o = _opposite(c, contracts)
    if o is None:
        return dict(median=None, books=0, label="derived", note="no opposite side quoted")
    mine = {q["book"]: q["price"] for q in c["quotes"] if q["fresh"]}
    theirs = {q["book"]: q["price"] for q in o["quotes"] if q["fresh"]}
    probs = []
    for b in sorted(set(mine) & set(theirs)):
        a, z = 1 / dec(mine[b]), 1 / dec(theirs[b])
        probs.append(a / (a + z))
    if not probs:
        return dict(median=None, books=0, label="derived", note="no book quotes both sides freshly")
    return dict(median=round(statistics.median(probs), 4), books=len(probs), label="derived")


def contract_view(c, game, now):
    started = now >= game["kickoff"]
    why = None
    if started:
        why = "game has started"
    elif c["best_in_band"] is None:
        why = ("no fresh quote in this capture" if c["best"] is None
               else "best fresh price %+d is outside -200..+200" % c["best"]["price"])
    label = label_for(c, game)
    return dict(id=c["id"], event_id=c["event_id"], period=c["period"], market=c["market"], subject=c["subject"],
                side=c["side"], point=c["point"], label=label, quotes=c["quotes"], best=c["best"],
                best_in_band=c["best_in_band"], no_vig=c["no_vig"], reviewable=why is None, why_not=why)


def label_for(c, game):
    kind, period = MARKETS[c["market"]]
    prefix = "First half · " if period == "first_half" else ""  # same wording as selection_markets.label_for
    if kind == "moneyline":
        base = c["side"] + " to win"
    elif kind == "spread":
        base = "%s %+.1f" % (c["side"], c["point"])
    else:
        unit = PROP_NAMES.get(c["market"], "team points" if kind == "team_total" else "game points")
        base = ("%s %s %g %s" % (c["subject"], c["side"].lower(), c["point"], unit)).strip()
    a, h = game["away"]["abbr"] or game["away"]["name"], game["home"]["abbr"] or game["home"]["name"]
    return "%s%s (%s at %s)" % (prefix, base, a, h)


def _modal_point(contracts, event_id, market, side=None):
    counts = {}
    for c in contracts.values():
        if c["event_id"] == event_id and c["market"] == market and (side is None or c["side"] == side):
            counts[c["point"]] = counts.get(c["point"], 0) + len(c["quotes"])
    return sorted(counts.items(), key=lambda kv: (-kv[1], abs(kv[0] or 0)))[0][0] if counts else None


def _best_price(contracts, event_id, market, side):
    for c in contracts.values():
        if c["event_id"] == event_id and c["market"] == market and c["side"] == side and c["best"]:
            return c["best"]["price"]
    return None


# ---------------------------------------------------------------- public: dates, screen
def dates():
    now = clock()
    out = []
    if INPUTS.is_dir():
        for p in sorted(INPUTS.iterdir()):
            try:
                day = check_date(p.name)
                eds, _ = editions(day)
                b = build(day, eds[-1])
            except (Refused, ValueError, OSError, KeyError):
                continue
            games = sorted(b["games"].values(), key=lambda g: g["kickoff"])
            wins = {w: sum(1 for g in games if g["window"] == w) for w in WINDOWS}
            started = sum(1 for g in games if now >= g["kickoff"])
            state = "all_started" if games and started == len(games) else "partly_started" if started else "ready"
            rows, _ = _read_rows(day, strict=False)
            states = window_states(rows, games, now)
            cur = PUBLISHED / day / "CURRENT.json"
            out.append(dict(date=day, week=(b["sched"]["doc"].get("week") or {}).get("number"), games=len(games),
                            state=state, editions=len(eds), latest_edition_utc=eds[-1]["captured_utc"],
                            latest_sha256=eds[-1]["sha256"], first_kickoff_utc=games[0]["kickoff_utc"] if games else None,
                            windows=wins, review_state={w: states[w]["state"] for w in WINDOWS}, published=cur.is_file()))
    return dict(ok=True, api=API, rule="Sundays on or after %s; inputs come from the front-door owner's sunday_intake.acquire" % FIRST_DATE, dates=out)


def screen(day, edition="latest", window=None, market=None, band_only=False):
    day = check_date(day)
    if window is not None and window not in WINDOWS:
        raise Refused("BAD_WINDOW", "window must be one of " + ", ".join(WINDOWS))
    if market is not None and market not in MARKETS:
        raise Refused("BAD_MARKET", "market must be one of " + ", ".join(sorted(MARKETS)))
    now = clock()
    ed = resolve_edition(day, edition)
    eds, skipped = editions(day)
    b = build(day, ed)
    obs = (ed["doc"].get("observations") or [{}])[0]
    books_present = sorted({bk for g in b["games"].values() for bk in g["books"]})
    requested = ed["doc"].get("books_requested") or []
    union = set()
    for g in b["games"].values():
        union |= g["markets_present"]
    unavailable = [m for m in MARKETS if m not in union]
    warnings = list(b["warnings"]) + ["skipped capture file " + s for s in skipped]
    missing = list(ed["doc"].get("missing") or [])
    missing_books = [x for x in requested if x not in books_present]
    if missing_books:
        warnings.append("%d of %d requested books have no quotes in this edition: %s" % (len(missing_books), len(requested), ", ".join(missing_books)))
    if unavailable:
        missing.append("unavailable in this capture: " + ", ".join(unavailable) +
                       (" (main lines only)" if all(m in union for m in MAIN) and not union - set(MAIN) else ""))
    if not ed["is_latest"]:
        warnings.append("this is not the latest edition (latest was captured %s)" % eds[-1]["captured_utc"])
    wins = []
    games_sorted = sorted(b["games"].values(), key=lambda g: (g["kickoff"], g["away"]["name"]))
    sched_unmatched = _unmatched_schedule(b, day)
    for w in WINDOWS:
        if window and w != window:
            continue
        gl = [g for g in games_sorted if g["window"] == w and g["ct_date"] == day]
        if not gl:
            continue
        wins.append(dict(name=w, label=WINDOW_LABELS[w], first_kickoff_utc=gl[0]["kickoff_utc"], max_calls=MAX_PER_WINDOW,
                         state="closed" if now >= gl[0]["kickoff"] else "open",
                         games=[_game_view(g, b, now, market, band_only) for g in gl]))
    for g in games_sorted:
        if g["ct_date"] != day:
            warnings.append("%s at %s kicks off on %s Central, not %s; excluded" % (g["away"]["name"], g["home"]["name"], g["ct_date"], day))
    return dict(ok=True, api=API, kind="screen", date=day, week=(b["sched"]["doc"].get("week") or {}).get("number"),
                generated_utc=ts(now), provisional=True, engine=None,
                edition=dict(captured_utc=ed["captured_utc"], sha256=ed["sha256"], path=str(ed["path"]), is_latest=ed["is_latest"],
                             age_seconds=max(0, int((now - ed["captured"]).total_seconds()))),
                inputs=dict(schedule=dict(sha256=b["sched"]["sha256"], events=b["sched"]["events"],
                                          observed_utc=(b["sched"]["doc"].get("_source") or {}).get("observed_utc")),
                            odds=dict(books_requested=requested, books_present=books_present, books_missing=missing_books,
                                      markets_present=sorted(union), markets_unavailable=unavailable,
                                      credits_remaining=obs.get("remaining"))),
                windows=wins, warnings=warnings + sched_unmatched, missing=missing,
                evidence_labels="price=known, no_vig=derived, judgment=estimated, fill/personal price/Louisiana availability=unknown")


def _unmatched_schedule(b, day):
    odds_keys = {(frozenset((g["home"]["name"], g["away"]["name"])), g["kickoff_utc"][:16]) for g in b["games"].values()}
    out = []
    for k, ev in b["sched"]["index"].items():
        if k not in odds_keys:
            out.append("schedule event %s (%s) has no match in odds.json" % (ev.get("id"), ev.get("shortName")))
    return out


def _game_view(g, b, now, market, band_only):
    cl = [contract_view(c, g, now) for c in b["contracts"].values() if c["event_id"] == g["event_id"]]
    order = {m: i for i, m in enumerate(MARKETS)}
    cl.sort(key=lambda c: (order[c["market"]], c["subject"], c["side"], c["point"] if c["point"] is not None else 0))
    if market:
        cl = [c for c in cl if c["market"] == market]
    if band_only:
        cl = [c for c in cl if c["best_in_band"]]
    eid = g["event_id"]
    unavailable = [m for m in MARKETS if m not in g["markets_present"]]
    return dict(event_id=eid, espn_event_id=g["espn_event_id"], away=g["away"], home=g["home"],
                kickoff_utc=g["kickoff_utc"], kickoff_ct=g["kickoff_ct"], window=g["window"],
                state="started" if now >= g["kickoff"] else "scheduled", neutral_site=g["neutral_site"], venue=g["venue"],
                books=[dict(key=k, provider_updated_utc=v) for k, v in sorted(g["books"].items())],
                lines=dict(moneyline=dict(home=_best_price(b["contracts"], eid, "h2h", g["home"]["name"]),
                                          away=_best_price(b["contracts"], eid, "h2h", g["away"]["name"]), basis="best fresh price across books"),
                           spread=dict(home_point=_modal_point(b["contracts"], eid, "spreads", g["home"]["name"]), basis="most-quoted point"),
                           total=dict(point=_modal_point(b["contracts"], eid, "totals", "Over"), basis="most-quoted point")),
                contracts=cl, markets_unavailable=unavailable,
                missing=g["missing"] + (["markets not in this capture: " + ", ".join(unavailable)] if unavailable else []))


# ---------------------------------------------------------------- reviews
def _review_path(day):
    return REVIEWS / day / "reviews.jsonl"


def _row_hash(row):
    body = {k: v for k, v in row.items() if k != "sha256"}
    return sha(canon(body))


def _annotation_path(day):
    return ANNOTATIONS / day / "annotations.jsonl"


def _read_rows(day, strict=True, path=None):
    p = path or _review_path(day)
    rows = []
    if not p.is_file():
        return rows, None
    prev, bad = ZERO, None
    for i, line in enumerate(p.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            ok = row.get("prev_sha256") == prev and row.get("sha256") == _row_hash(row) and row.get("seq") == len(rows) + 1
        except ValueError:
            ok, row = False, {}
        if not ok:
            bad = bad or "line %d (%s)" % (i, row.get("row_id", "unreadable"))
            if strict:
                raise Refused("CHAIN_BROKEN", "review history was altered at " + bad)
        rows.append(row)
        prev = row.get("sha256", "")
    return rows, bad


def active_rows(rows):
    """Latest prospective (non-late) row per window. Late rows are recorded but never replace one."""
    out = {}
    for r in rows:
        if not r.get("late"):
            out[r["window"]] = r
    return out


def window_states(rows, games, now):
    act = active_rows(rows)
    first = {}
    for g in games:
        gk = g["kickoff"] if isinstance(g, dict) else g
        w = g["window"]
        first[w] = min(first.get(w, gk), gk)
    out = {}
    for w in WINDOWS:
        r = act.get(w)
        if r:
            out[w] = dict(state=r["decision"], row_id=r["row_id"], calls=len(r.get("calls", [])), note=r.get("note", ""))
        elif w in first and now >= first[w]:
            out[w] = dict(state="unreviewed_after_close")
        else:
            out[w] = dict(state="unreviewed")
    return out


def _fail_field(msg):
    raise Refused("INCOMPLETE_FIELD", msg)


def _text(obj, key, what, optional=False):
    v = obj.get(key)
    if v is None and optional:
        return ""
    if not isinstance(v, str) or not v.strip():
        _fail_field("%s is required (non-empty text)" % what)
    return v.strip()


def submit_review(day, payload):
    day = check_date(day)
    if not isinstance(payload, dict):
        raise Refused("BAD_PAYLOAD", "payload must be a JSON object")
    if payload.get("api") not in (None, API):
        raise Refused("BAD_PAYLOAD", "api must be %s" % API)
    if payload.get("date") != day:
        raise Refused("BAD_PAYLOAD", "payload date %r does not match %s" % (payload.get("date"), day))
    author = _text(payload, "author", "author")
    if len(author) > 80:
        _fail_field("author is too long")
    author_kind = payload.get("author_kind")
    if author_kind is not None and author_kind not in AUTHOR_KINDS:
        raise Refused("BAD_AUTHOR_KIND", "author_kind must be one of %s (or omitted: it is then recorded as 'unspecified', never assumed human)" % ", ".join(AUTHOR_KINDS))
    author_kind = author_kind or "unspecified"
    pin = payload.get("edition")
    if not isinstance(pin, dict) or not pin.get("sha256") or not pin.get("captured_utc"):
        raise Refused("EDITION_UNKNOWN", "edition must pin both captured_utc and sha256 of the capture the reviewer looked at")
    late = payload.get("late", False)
    if not isinstance(late, bool):
        raise Refused("BAD_PAYLOAD", "late must be true or false")
    wspec = payload.get("windows")
    if not isinstance(wspec, dict) or not wspec:
        raise Refused("BAD_PAYLOAD", "windows must name at least one of early, late, night")
    for w, spec in wspec.items():
        if w not in WINDOWS:
            raise Refused("BAD_WINDOW", "unknown window %r; use early, late or night" % w)
        if not isinstance(spec, dict) or spec.get("decision") not in ("calls", "no_play"):
            raise Refused("BAD_DECISION", "window %s needs decision 'calls' or 'no_play'" % w)
    calls_in = payload.get("calls", [])
    if not isinstance(calls_in, list) or any(not isinstance(c, dict) for c in calls_in):
        raise Refused("BAD_PAYLOAD", "calls must be a list of objects")
    now = clock()
    ed = resolve_edition(day, pin)
    if ed["captured"] > now:
        raise Refused("EDITION_UNKNOWN", "the pinned capture is dated %s, which is in the future" % ed["captured_utc"])
    latest = editions(day)[0][-1]
    b = build(day, ed)
    latest_games = build(day, latest)["games"] if latest["sha256"] != ed["sha256"] else b["games"]
    games = b["games"]
    resolved = []
    for c in calls_in:
        resolved.append(_resolve_call(c, b, games, latest_games, now, late))
    # Matthew's rule (weekly/1): 0-2 calls per window, including a one-game Sunday night. Two DISTINCT
    # contracts in one game (for example a side and a total) are allowed and are annotated as correlated
    # when published; the same exact contract twice is refused (DUPLICATE_CONTRACT), and so are opposite
    # directions on the same event, period, market and subject at any threshold (OPPOSITE_DIRECTION).
    per_window, seen_ids = {}, set()
    for r in resolved:
        w = r["window"]
        if w not in wspec or wspec[w]["decision"] != "calls":
            raise Refused("WRONG_WINDOW", "call %s is in the %s window, which this submission does not declare as 'calls'" % (r["label"], w))
        if r["id"] in seen_ids:
            raise Refused("DUPLICATE_CONTRACT", "the same exact contract appears twice (%s)" % r["label"])
        seen_ids.add(r["id"])
        per_window[w] = per_window.get(w, 0) + 1
    clash = opposite_direction_pair(resolved)
    if clash is not None:
        raise Refused("OPPOSITE_DIRECTION", _opposite_detail(*clash))
    for w, n in per_window.items():
        if n > MAX_PER_WINDOW:
            raise Refused("WINDOW_LIMIT", "%d calls in the %s window; the limit is %d" % (n, w, MAX_PER_WINDOW))
    for w, spec in wspec.items():
        if spec["decision"] == "calls" and per_window.get(w, 0) == 0:
            raise Refused("INCOMPLETE_FIELD", "window %s says 'calls' but no call belongs to it (use no_play to pass)" % w)
    rows_now, _ = _read_rows(day)
    with lock(REVIEWS / day / ".lock"):
        rows_now, _ = _read_rows(day)
        act = active_rows(rows_now)
        total = sum(len(r.get("calls", [])) for w, r in act.items() if w not in wspec) + len(resolved)
        if total > MAX_PER_DATE:
            raise Refused("DATE_LIMIT", "%d calls for the date; the limit is %d" % (total, MAX_PER_DATE))
        first = {}
        for g in latest_games.values():
            if g["ct_date"] == day:
                first[g["window"]] = min(first.get(g["window"], g["kickoff"]), g["kickoff"])
        payload_hash = sha(canon({k: v for k, v in payload.items() if k not in ("client_utc",)}))
        new_rows, dup, prev, seq = [], 0, (rows_now[-1]["sha256"] if rows_now else ZERO), len(rows_now)
        for w in WINDOWS:
            if w not in wspec:
                continue
            spec = wspec[w]
            cur = act.get(w)
            my_calls = [r for r in resolved if r["window"] == w]
            body_hash = sha(canon([spec, my_calls, ed["sha256"], author, author_kind]))
            if cur is not None and cur.get("body_sha256") == body_hash and not late:
                dup += 1
                continue
            if w in first and now >= first[w] and not late:
                raise Refused("AFTER_KICKOFF", "the %s window started at %s; a decision or revision now must be sent with late=true and is excluded from the prospective record" % (w, ts(first[w])))
            seq += 1
            row = dict(row_id="%s/%s/%04d" % (day, w, seq), seq=seq, received_utc=ts(now),
                       client_claimed_utc=payload.get("client_utc") if isinstance(payload.get("client_utc"), str) else None,
                       date=day, window=w, decision=spec["decision"], note=(spec.get("note") or "").strip() if isinstance(spec.get("note"), str) else "",
                       considered=(spec.get("considered") or "").strip() if isinstance(spec.get("considered"), str) else "",
                       author=author, author_kind=author_kind, edition=dict(captured_utc=ed["captured_utc"], sha256=ed["sha256"]),
                       edition_is_latest=ed["is_latest"], late=late,
                       calls=my_calls if spec["decision"] == "calls" else [],
                       supersedes=(cur["row_id"] if cur is not None and not late else None),
                       payload_sha256=payload_hash, body_sha256=body_hash, prev_sha256=prev)
            row["sha256"] = _row_hash(row)
            prev = row["sha256"]
            new_rows.append(row)
        if new_rows:
            p = _review_path(day)
            p.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(p), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, b"".join(canon(r) + b"\n" for r in new_rows))
                os.fsync(fd)
            finally:
                os.close(fd)
        all_rows = rows_now + new_rows
    gl = [g for g in latest_games.values() if g["ct_date"] == day]
    warnings = []
    if not ed["is_latest"]:
        warnings.append("pinned edition %s is not the latest (%s)" % (ed["captured_utc"], latest["captured_utc"]))
    if late:
        warnings.append("late=true: recorded but excluded from the prospective claim and from the card")
    return dict(ok=True, api=API, date=day, rows=new_rows, duplicate=bool(dup) and not new_rows, window_states=window_states(all_rows, gl, now),
                warnings=warnings)


def _resolve_call(c, b, games, latest_games, now, late):
    for k in ("event_id", "market", "side"):
        if not isinstance(c.get(k), str) or not c[k]:
            _fail_field("call is missing %s" % k)
    subject = c.get("subject", "")
    if not isinstance(subject, str):
        _fail_field("subject must be text")
    point = c.get("point")
    if point is not None and (isinstance(point, bool) or not isinstance(point, (int, float))):
        _fail_field("point must be a number or null")
    mk = c["market"]
    if mk not in MARKETS:
        raise Refused("UNKNOWN_CONTRACT", "market %r is not a supported market key" % mk)
    cid = key_for(c["event_id"], mk, subject, c["side"], float(point) if point is not None else None)
    contract = b["contracts"].get(cid)
    if contract is None:
        g = games.get(c["event_id"])
        if g is None:
            raise Refused("UNKNOWN_CONTRACT", "event_id %s is not in the pinned capture" % c["event_id"])
        if mk not in g["markets_present"]:
            raise Refused("UNKNOWN_CONTRACT", "market %s is not in the pinned capture for %s at %s (main lines only unless the capture is detailed)" % (mk, g["away"]["name"], g["home"]["name"]))
        raise Refused("UNKNOWN_CONTRACT", "no such quoted side or line in the pinned capture: " + cid)
    g = games[c["event_id"]]
    floor = c.get("minimum_price")
    if not is_price(floor):
        _fail_field("minimum_price must be an integer American price such as -166 or +120")
    if not in_band(floor):
        raise Refused("PRICE_OUT_OF_BAND", "minimum_price %+d is outside -200..+200" % floor)
    thesis = c.get("thesis") if c.get("thesis") is not None else c.get("rationale")
    counter = c.get("counterevidence") if c.get("counterevidence") is not None else c.get("risk")
    cond = c.get("condition")
    for name, v in (("thesis (or rationale)", thesis), ("counterevidence (or risk)", counter), ("condition", cond)):
        if not isinstance(v, str) or not v.strip():
            _fail_field("%s is required (non-empty text)" % name)
    sources = c.get("sources", [])
    if not isinstance(sources, list) or not all(url_ok(s) for s in sources):
        _fail_field("sources must be a list of plain https links without keys or tokens")
    kick = g["kickoff"]
    lg = latest_games.get(c["event_id"])
    if lg is not None:
        kick = min(kick, lg["kickoff"])
    if now >= kick and not late:
        raise Refused("AFTER_KICKOFF", "%s kicked off at %s; a call now must be sent with late=true and is excluded from the prospective record" % (_game_text(g), ts(kick)))
    fresh_in = [q for q in contract["quotes"] if q["fresh"] and in_band(q["price"])]
    ok = [q for q in fresh_in if dec(q["price"]) >= dec(floor)]
    if not ok:
        best = _best(fresh_in)
        if best is None:
            raise Refused("FLOOR_ABOVE_QUOTE", "no fresh in-band quote for %s in the pinned capture" % label_for(contract, g))
        raise Refused("FLOOR_ABOVE_QUOTE", "best fresh in-band quote is %+d (%s), which pays less than your floor %+d" % (best["price"], best["book"], floor))
    q = sorted(ok, key=lambda x: (-dec(x["price"]), x["book"]))[0]
    return dict(id=cid, event_id=c["event_id"], market=mk, period=MARKETS[mk][1], subject=subject, side=c["side"],
                point=float(point) if point is not None else None, label=label_for(contract, g), game=_game_text(g),
                window=g["window"], kickoff_utc=g["kickoff_utc"], minimum_price=floor,
                observed=dict(book=q["book"], price=q["price"], book_updated_utc=q["updated_utc"]),
                no_vig=contract["no_vig"], thesis=thesis.strip(), counterevidence=counter.strip(), condition=cond.strip(),
                sources=sources)


def _game_text(g):
    return "%s at %s" % (g["away"]["name"], g["home"]["name"])


def opposite_direction_pair(calls):
    """First pair of calls (a, b) that take opposite directions on the same event, period, market and subject.

    Direction is the call's `side`: Over against Under for a total, team total or player prop; one team's name
    against the other's for a moneyline or spread. The threshold plays no part, so Over 22.5 with Under 24.5 and
    home -3.5 with away +2.5 both clash. The period is part of the market key (a first-half total is a different
    market from the full-game total), and `subject` is the player or the team the line belongs to, so
    other markets, other periods, other subjects and the same direction at another line are not clashes.
    Arithmetic on the call fields only: no judgment, no network. Formal calls only; nothing here reads a notebook."""
    seen = {}
    for c in calls:
        key = (c["event_id"], c["market"], c["subject"])
        prior = seen.setdefault(key, c)
        if prior["side"] != c["side"]:
            return prior, c
    return None


def _opposite_detail(a, b):
    where = "%s; %s; market %s" % (a.get("game") or a["event_id"], MARKETS[a["market"]][1].replace("_", " "), a["market"])
    if a["subject"]:
        where += "; subject %s" % a["subject"]
    return ("%s and %s take opposite directions on the same event, period, market and subject, at any threshold (%s). "
            "Send one direction per market and subject. Still allowed together: a different market, a different subject "
            "(another player or team), a different period, or the same direction at another line." % (a["label"], b["label"], where))


def _pair_relation(a, b):
    """How two distinct contracts in one game relate. Arithmetic on the contract fields only."""
    if a["market"] != b["market"]:
        return "different_markets"
    if a["subject"] != b["subject"]:
        return "same_market_other_subject"
    if a["side"] != b["side"]:
        return "opposite_sides_same_market"
    return "same_market_other_line"


def shared_event_notes(calls):
    """{contract id: shared_event dict} for every call that shares its event with another actual call."""
    by_event = {}
    for c in calls:
        by_event.setdefault(c["event_id"], []).append(c)
    out = {}
    for eid, group in by_event.items():
        if len(group) < 2:
            continue
        for c in group:
            others = [dict(label=o["label"], id=o["id"], market=o["market"], side=o["side"], point=o["point"],
                           relation=_pair_relation(c, o)) for o in group if o["id"] != c["id"]]
            opp = any(o["relation"] == "opposite_sides_same_market" for o in others)
            note = ("Correlated: %d calls on this card are in the same game, so one game result can decide more than one of them. "
                    "They are not independent calls." % len(group))
            if opp:
                note += " Two of them take opposite sides of the same market."
            out[c["id"]] = dict(event_id=eid, calls_in_event=len(group), others=others, note=note)
    return out


def list_reviews(day):
    day = check_date(day)
    rows, bad = _read_rows(day, strict=False)
    try:
        eds, _ = editions(day)
        games = [g for g in build(day, eds[-1])["games"].values() if g["ct_date"] == day]
    except Refused:
        games = []
    return dict(ok=True, api=API, date=day, rows=rows, window_states=window_states(rows, games, clock()),
                chain_ok=bad is None, chain_problem=bad)


def verify(day):
    day = check_date(day)
    rows, _ = _read_rows(day, strict=True)
    return dict(ok=True, api=API, date=day, rows=len(rows), head_sha256=rows[-1]["sha256"] if rows else ZERO)


# ---------------------------------------------------------------- annotations
def annotate(day, payload):
    """Append one independent (red-team) note. It is not a review and never changes a call."""
    day = check_date(day)
    if not isinstance(payload, dict):
        raise Refused("BAD_PAYLOAD", "payload must be a JSON object")
    if payload.get("api") not in (None, API):
        raise Refused("BAD_PAYLOAD", "api must be %s" % API)
    if payload.get("date") != day:
        raise Refused("BAD_PAYLOAD", "payload date %r does not match %s" % (payload.get("date"), day))
    kind = payload.get("author_kind")
    if kind not in AUTHOR_KINDS:
        raise Refused("BAD_AUTHOR_KIND", "author_kind is required and must be one of %s; it is never defaulted" % ", ".join(AUTHOR_KINDS))
    author = _text(payload, "author", "author")
    if len(author) > 80:
        _fail_field("author is too long")
    stance = payload.get("stance")
    if stance not in STANCES:
        raise Refused("BAD_STANCE", "stance must be one of %s" % ", ".join(STANCES))
    text = _text(payload, "text", "text")
    if len(text) > 4000:
        _fail_field("text is too long (4000 characters at most)")
    sources = payload.get("sources", [])
    if not isinstance(sources, list) or not all(url_ok(s) for s in sources):
        _fail_field("sources must be a list of plain https links without keys or tokens")
    scope_in = payload.get("scope")
    scope_in = {} if scope_in is None else scope_in
    if not isinstance(scope_in, dict) or set(scope_in) - {"window", "contract_id"}:
        raise Refused("BAD_SCOPE", "scope may only hold window and/or contract_id")
    window, cid = scope_in.get("window"), scope_in.get("contract_id")
    if window is not None and window not in WINDOWS:
        raise Refused("BAD_SCOPE", "unknown window %r; use early, late or night" % (window,))
    if cid is not None and (not isinstance(cid, str) or not cid):
        raise Refused("BAD_SCOPE", "contract_id must be a contract id from the screen")
    pin = payload.get("edition")
    ed = resolve_edition(day, pin)
    now = clock()
    if ed["captured"] > now:
        raise Refused("EDITION_UNKNOWN", "the pinned capture is dated %s, which is in the future" % ed["captured_utc"])
    b = build(day, ed)
    games_day = [g for g in b["games"].values() if g["ct_date"] == day]
    if cid is not None:
        contract = b["contracts"].get(cid)
        if contract is None:
            raise Refused("UNKNOWN_CONTRACT", "contract_id %s is not in the %s capture" % (cid, "pinned" if pin else "latest"))
        g = b["games"][contract["event_id"]]
        if window is not None and window != g["window"]:
            raise Refused("BAD_SCOPE", "that contract is in the %s window, not %s" % (g["window"], window))
        kick = g["kickoff"]
    else:
        ks = [g["kickoff"] for g in games_day if window is None or g["window"] == window]
        if window is not None and not ks:
            raise Refused("BAD_SCOPE", "no game in the %s window on %s" % (window, day))
        kick = min(ks) if ks else None
    scope = dict(window=window, contract_id=cid)
    body_hash = sha(canon([kind, author, stance, text, sources, scope, ed["sha256"]]))
    path = _annotation_path(day)
    with lock(ANNOTATIONS / day / ".lock"):
        rows, _ = _read_rows(day, strict=True, path=path)
        for r in rows:
            if r.get("body_sha256") == body_hash:
                return dict(ok=True, api=API, date=day, row=r, duplicate=True, warnings=[])
        row = dict(row_id="%s/annotation/%04d" % (day, len(rows) + 1), seq=len(rows) + 1, received_utc=ts(now), date=day,
                   kind="red_team_annotation", is_review=False, changes_calls=False,
                   author_kind=kind, author=author, stance=stance, text=text, sources=sources, scope=scope,
                   edition=dict(captured_utc=ed["captured_utc"], sha256=ed["sha256"]),
                   edition_pinned=pin not in (None, "latest"),
                   received_after_kickoff=bool(kick is not None and now >= kick),
                   body_sha256=body_hash, prev_sha256=(rows[-1]["sha256"] if rows else ZERO))
        row["sha256"] = _row_hash(row)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, canon(row) + b"\n")
            os.fsync(fd)
        finally:
            os.close(fd)
    warnings = []
    if row["received_after_kickoff"]:
        warnings.append("received after the kickoff of what it is scoped to; recorded and labelled received_after_kickoff")
    return dict(ok=True, api=API, date=day, row=row, duplicate=False, warnings=warnings)


def list_annotations(day):
    day = check_date(day)
    rows, bad = _read_rows(day, strict=False, path=_annotation_path(day))
    return dict(ok=True, api=API, date=day, rows=rows, chain_ok=bad is None, chain_problem=bad)


def verify_annotations(day):
    day = check_date(day)
    rows, _ = _read_rows(day, strict=True, path=_annotation_path(day))
    return dict(ok=True, api=API, date=day, rows=len(rows), head_sha256=rows[-1]["sha256"] if rows else ZERO)


ANNOTATION_CARD_KEYS = ("row_id", "seq", "received_utc", "author_kind", "author", "stance", "text", "sources", "scope", "edition",
                        "edition_pinned", "received_after_kickoff", "is_review", "changes_calls", "sha256")


# ---------------------------------------------------------------- publish
def publish(day):
    day = check_date(day)
    rows, _ = _read_rows(day, strict=True)
    act = active_rows(rows)
    if not act:
        raise Refused("NOTHING_TO_PUBLISH", "no window has a prospective decision yet")
    call_rows = [r for r in act.values() if r["decision"] == "calls"]
    # submit_review already refuses this; the guard keeps a row written before the rule from reaching a card
    clash = opposite_direction_pair([c for r in call_rows for c in r["calls"]])
    if clash is not None:
        raise Refused("OPPOSITE_DIRECTION", _opposite_detail(*clash) + " Resubmit the window with one direction.")
    pins = {r["edition"]["sha256"] for r in call_rows}
    if len(pins) > 1:
        raise Refused("MIXED_EDITIONS", "calls were pinned to different captures (%s); the card carries one snapshot, so resubmit those windows against one edition" %
                      ", ".join(sorted("%s=%s" % (r["window"], r["edition"]["captured_utc"]) for r in call_rows)))
    pool = call_rows or list(act.values())
    ed_ref = sorted((r["edition"] for r in pool), key=lambda e: e["captured_utc"])[-1]
    ed = resolve_edition(day, ed_ref)
    eds, _ = editions(day)
    now = clock()
    games = [g for g in build(day, eds[-1])["games"].values() if g["ct_date"] == day]
    states = window_states(rows, games, now)
    issued = max(parse_ts(r["received_utc"]) for r in act.values())
    calls_sunday, passes, cards_windows, started = [], [], [], []
    shared = shared_event_notes([c for r in call_rows for c in r["calls"]])
    arows, _ = _read_rows(day, strict=True, path=_annotation_path(day))
    ann = [{k: r[k] for k in ANNOTATION_CARD_KEYS if k in r} for r in arows]
    for w in WINDOWS:
        r = act.get(w)
        st = states[w]["state"]
        if r is None:
            cards_windows.append(dict(name=w, label=WINDOW_LABELS[w], state=st, calls=[]))
            continue
        if r["decision"] == "no_play":
            reason = r.get("note") or "No play: the reviewer passed this window and gave no rationale."
            p = dict(window=WINDOW_LABELS[w], decision="Pass", reason=reason)
            if r.get("considered"):
                p["considered"] = r["considered"]
            passes.append(p)
            cards_windows.append(dict(name=w, label=WINDOW_LABELS[w], state="no_play", note=r.get("note", ""), calls=[], review_row=r["row_id"],
                                      review_author=r["author"], review_author_kind=r.get("author_kind", "unspecified"),
                                      annotation_rows=[a["row_id"] for a in ann if a["scope"]["window"] == w and a["scope"]["contract_id"] is None]))
            continue
        cl = []
        for c in r["calls"]:
            call = dict(label=c["label"], event_id=c["event_id"], window=WINDOW_LABELS[w], kickoff=c["kickoff_utc"], game=c["game"],
                        market=c["market"], side=c["side"], subject=c["subject"], point=c["point"], minimum_price=c["minimum_price"],
                        observed_book=c["observed"]["book"], observed_price=c["observed"]["price"],
                        book_updated_utc=c["observed"]["book_updated_utc"], condition=c["condition"], thesis=c["thesis"],
                        counterevidence=c["counterevidence"], source=(c["sources"][0] if c["sources"] else ""),
                        decision="Conditional pregame recommendation", ticket=None)
            if c["id"] in shared:
                call["shared_event"] = shared[c["id"]]
            # brief.py's validate_card needs issued_utc < kickoff for every call, so a call whose game had
            # already started when the latest review landed stays out of Sunday_Card.json (it remains in
            # Card.json and in the history snapshot published before kickoff).
            began = parse_ts(c["kickoff_utc"]) <= issued
            if began:
                started.append(dict(label=c["label"], event_id=c["event_id"], kickoff=c["kickoff_utc"], review_row=r["row_id"]))
            else:
                calls_sunday.append(call)
            cl.append(dict(call, id=c["id"], no_vig=c["no_vig"], sources=c["sources"], review_row=r["row_id"],
                           annotation_rows=[a["row_id"] for a in ann if a["scope"]["contract_id"] == c["id"]],
                           state="started_before_issue" if began else "pregame_at_issue",
                           evidence=dict(price="known", no_vig="derived", judgment="estimated",
                                         fill_and_personal_price="unknown", final_inactives="unknown",
                                         local_availability_verified=False)))
        cards_windows.append(dict(name=w, label=WINDOW_LABELS[w], state="calls", note=r.get("note", ""), calls=cl, review_row=r["row_id"],
                                  review_author=r["author"], review_author_kind=r.get("author_kind", "unspecified"),
                                  annotation_rows=[a["row_id"] for a in ann if a["scope"]["window"] == w and a["scope"]["contract_id"] is None]))
    unreviewed = [w for w in WINDOWS if states[w]["state"].startswith("unreviewed")]
    late_rows = [dict(row_id=r["row_id"], window=r["window"], decision=r["decision"], received_utc=r["received_utc"]) for r in rows if r.get("late")]
    sunday = dict(slate_date=day, issued_utc=ts(issued), earliest_snapshot=ed["captured_utc"], snapshot_sha256=ed["sha256"],
                  calls=calls_sunday, passes=passes, unreviewed_windows=[WINDOW_LABELS[w] for w in unreviewed],
                  excluded_started_before_issue=started,
                  source=dict(producer="weekly/weekly_api.py", api=API, review_rows=[r["row_id"] for r in act.values()],
                              review_head_sha256=rows[-1]["sha256"], paper_only=True))
    card = dict(api=API, kind="card", date=day, paper_only=True,
                disclaimer="Paper-only, advisory. A saved price is not a promise of a fill and says nothing about local availability.",
                issued_utc=ts(issued), edition=dict(captured_utc=ed["captured_utc"], sha256=ed["sha256"], is_latest=ed["is_latest"],
                                                    path=str(ed["path"])),
                windows=cards_windows, late_rows_excluded=late_rows,
                annotations=ann, annotation_head_sha256=(arows[-1]["sha256"] if arows else ZERO),
                annotations_note="Independent red-team notes. They are not the reviewer's decision and change no call. author_kind is declared by the submitter (human, claude, codex or other); a note is never recorded as the human review.",
                markets_unavailable_in_capture=[m for m in MARKETS if m not in set().union(*[g["markets_present"] for g in build(day, ed)["games"].values()])],
                summary=dict(calls=len(calls_sunday) + len(started), calls_in_sunday_card=len(calls_sunday), calls_started_before_issue=len(started),
                             no_play_windows=len(passes), unreviewed_windows=len(unreviewed), late_rows=len(late_rows),
                             calls_sharing_an_event=len(shared), annotations=len(ann)),
                review_rows=[r["row_id"] for r in act.values()], review_head_sha256=rows[-1]["sha256"])
    if not ed["is_latest"]:
        card["warning"] = "a newer capture exists (%s); this card is pinned to %s" % (eds[-1]["captured_utc"], ed["captured_utc"])
    sunday_bytes = json.dumps(sunday, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
    card_bytes = json.dumps(card, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
    out = PUBLISHED / day
    with lock(out / ".lock"):
        cur_path = out / "CURRENT.json"
        if cur_path.is_file():
            cur = json.loads(cur_path.read_text())
            if cur.get("sunday_card_sha256") == sha(sunday_bytes) and cur.get("card_sha256") == sha(card_bytes):
                return _result(day, out, cur, unchanged=True)
        stamp = ts(now).replace(":", "")
        sid, cid = sha(sunday_bytes)[:8], sha(card_bytes)[:8]
        hist = out / "history"
        hist.mkdir(parents=True, exist_ok=True)
        for name, data in ((stamp + "." + sid + ".Sunday_Card.json", sunday_bytes), (stamp + "." + cid + ".Card.json", card_bytes)):
            if (hist / name).is_file():
                # Same second, same content hash: only the other file changed (for example a note was added). Never overwrite.
                if (hist / name).read_bytes() != data:
                    raise Refused("CHAIN_BROKEN", "history file %s already exists with different content" % name)
                continue
            fd = os.open(str(hist / name), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        atomic_write(out / "Sunday_Card.json", sunday_bytes)
        atomic_write(out / "Card.json", card_bytes)
        cur = dict(api=API, date=day, published_utc=ts(now), card="Card.json", sunday_card="Sunday_Card.json",
                   card_sha256=sha(card_bytes), sunday_card_sha256=sha(sunday_bytes),
                   history=dict(card="history/%s.%s.Card.json" % (stamp, cid), sunday_card="history/%s.%s.Sunday_Card.json" % (stamp, sid)),
                   capture_path=str(ed["path"]), capture_sha256=ed["sha256"], capture_captured_utc=ed["captured_utc"],
                   review_rows=[r["row_id"] for r in act.values()], review_head_sha256=rows[-1]["sha256"])
        atomic_write(cur_path, json.dumps(cur, indent=2, sort_keys=True).encode() + b"\n")
    return _result(day, out, cur, unchanged=False)


def _result(day, out, cur, unchanged):
    return dict(ok=True, api=API, date=day, unchanged=unchanged, published_utc=cur["published_utc"],
                output_path=str(out / cur["sunday_card"]), sunday_card_path=str(out / cur["sunday_card"]),
                card_path=str(out / cur["card"]), current_path=str(out / "CURRENT.json"),
                history_sunday_card_path=str(out / cur["history"]["sunday_card"]), history_card_path=str(out / cur["history"]["card"]),
                capture_path=cur["capture_path"], capture_sha256=cur["capture_sha256"],
                sunday_card_sha256=cur["sunday_card_sha256"], card_sha256=cur["card_sha256"], review_rows=cur["review_rows"])


def current_card(day):
    day = check_date(day)
    out = PUBLISHED / day
    p = out / "CURRENT.json"
    if not p.is_file():
        raise Refused("NO_CARD", "nothing has been published for " + day)
    cur = json.loads(p.read_text())
    sraw, craw = (out / cur["sunday_card"]).read_bytes(), (out / cur["card"]).read_bytes()
    if sha(sraw) != cur["sunday_card_sha256"] or sha(craw) != cur["card_sha256"]:
        raise Refused("CHAIN_BROKEN", "published card files no longer match CURRENT.json")
    res = _result(day, out, cur, unchanged=True)
    res.update(card=json.loads(craw), sunday_card=json.loads(sraw))
    return res


# ---------------------------------------------------------------- CLI
def _cli(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inputs", help="weekly_inputs directory (default: ../weekly_inputs)")
    ap.add_argument("--work", help="directory for reviews/ and published/ (default: this folder)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dates")
    s = sub.add_parser("screen")
    s.add_argument("date")
    s.add_argument("--edition", default="latest")
    s.add_argument("--window")
    s.add_argument("--market")
    s.add_argument("--band-only", action="store_true")
    r = sub.add_parser("review")
    rs = r.add_subparsers(dest="rcmd", required=True)
    sm = rs.add_parser("submit")
    sm.add_argument("date")
    sm.add_argument("--payload", required=True, help="path to a JSON file, or - for stdin")
    for name in ("list", "verify"):
        rs.add_parser(name).add_argument("date")
    an = sub.add_parser("annotate")
    ans = an.add_subparsers(dest="acmd", required=True)
    asub = ans.add_parser("submit")
    asub.add_argument("date")
    asub.add_argument("--payload", required=True, help="path to a JSON file, or - for stdin")
    for name in ("list", "verify"):
        ans.add_parser(name).add_argument("date")
    sub.add_parser("publish").add_argument("date")
    sub.add_parser("card").add_argument("date")
    a = ap.parse_args(argv)
    global INPUTS, REVIEWS, ANNOTATIONS, PUBLISHED
    if a.inputs:
        INPUTS = Path(a.inputs).resolve()
    if a.work:
        work = Path(a.work).resolve()
        REVIEWS, ANNOTATIONS, PUBLISHED = work / "reviews", work / "annotations", work / "published"
    if a.cmd == "dates":
        return dates()
    if a.cmd == "screen":
        return screen(a.date, a.edition, a.window, a.market, a.band_only)
    if a.cmd == "review":
        if a.rcmd == "submit":
            try:
                text = sys.stdin.read() if a.payload == "-" else Path(a.payload).read_text()
                payload = json.loads(text)
            except (OSError, ValueError) as err:
                raise Refused("BAD_PAYLOAD", "cannot read payload: %s" % type(err).__name__)
            return submit_review(a.date, payload)
        return list_reviews(a.date) if a.rcmd == "list" else verify(a.date)
    if a.cmd == "annotate":
        if a.acmd == "submit":
            try:
                text = sys.stdin.read() if a.payload == "-" else Path(a.payload).read_text()
                payload = json.loads(text)
            except (OSError, ValueError) as err:
                raise Refused("BAD_PAYLOAD", "cannot read payload: %s" % type(err).__name__)
            return annotate(a.date, payload)
        return list_annotations(a.date) if a.acmd == "list" else verify_annotations(a.date)
    if a.cmd == "publish":
        return publish(a.date)
    return current_card(a.date)


def main(argv=None):
    try:
        out = _cli(sys.argv[1:] if argv is None else argv)
    except Refused as err:
        print(json.dumps(dict(ok=False, api=API, code=err.code, detail=err.detail), indent=2))
        sys.stderr.write("REFUSED %s: %s\n" % (err.code, err.detail))
        return 1
    print(json.dumps(out, indent=2, default=str, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
