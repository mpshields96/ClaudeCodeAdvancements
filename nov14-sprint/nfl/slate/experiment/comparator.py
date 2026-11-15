#!/usr/bin/python3
"""Blinded public-comparator ledger. Standalone: it never imports or writes journal.py data.

What it is for
    Freeze a public pregame call made by somebody else (a Reddit handle, say) so that
    it can be compared, after the games, with the bot's own calls. It is a yardstick,
    never an input: nothing here feeds selection, ranking or a probability.

Rules it enforces
    * A call needs a posted price and a post time, and must be posted, observed and
      frozen here before kickoff. Anything else is refused (exit 1).
    * An edited post is refused: its pregame content cannot be shown.
    * A Sunday with no observed call is recorded as `missing`. It is never a loss,
      a pass or an invented row. `no_play` is only for an explicit public no-play
      that was observed before the first kickoff.
    * Blinded: before a call's kickoff, `status` and `grade` print counts only, never
      the pick. The file on disk is plain text, so the blinding is a procedure, not
      encryption: do not open comparators.jsonl before kickoff.
    * A call is graded at its own posted line and price. A different line is a
      different contract. No final recorded means "unknown", not a loss.
    * Rows are append-only and hash-chained. A correction is a new row.
    * No profit claim. Flat units are arithmetic at the posted price, which may not
      have been attainable.

Run (system Python 3.9, standard library only):
    /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B comparator.py [--data DIR] COMMAND
Exit codes: 0 done, 1 refused or verification failed, 2 bad command line.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_STORE = HERE / "comparator_data"
LEDGER = "comparators.jsonl"
GENESIS = "0" * 64
NO_CLAIM = ("No profit claim: flat units are arithmetic at the posted price, "
            "which may not have been attainable.")
RULE = ("Comparators never feed selection, ranking or a probability. "
        "Missing is not a loss. Only prospective rows count.")


class Refused(Exception):
    """The entry breaks a rule; nothing was written."""


# ---------------------------------------------------------------- small helpers

def parse_utc(text, what="time"):
    if not isinstance(text, str) or not text.strip().endswith("Z"):
        raise Refused("%s must be UTC ending in Z, like 2026-11-15T18:00:00Z" % what)
    body = text.strip()[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M"):
        try:
            parsed = datetime.datetime.strptime(body, fmt)
        except ValueError:
            continue
        return parsed.replace(microsecond=0, tzinfo=datetime.timezone.utc)
    raise Refused("%s is not a UTC time like 2026-11-15T18:00:00Z: %r" % (what, text))


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def parse_price(value):
    if value is None or str(value).strip() == "":
        raise Refused("price is missing: a comparator call needs the posted price")
    text = str(value).strip().replace("−", "-")
    try:
        price = int(text[1:]) if text.startswith("+") else int(text)
    except ValueError:
        raise Refused("price must be American odds such as -113 or +120, not %r" % value)
    if abs(price) < 100:
        raise Refused("price must be American odds of +100 or longer, or -100 or shorter")
    return price


def parse_line(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        line = float(str(value).strip().replace("−", "-"))
    except ValueError:
        raise Refused("line must be a number such as 57.5 or -3, not %r" % value)
    if math.isnan(line) or math.isinf(line):
        raise Refused("line must be a finite number")
    return line


def need(value, what):
    if value is None or not str(value).strip():
        raise Refused("%s is required" % what)
    return " ".join(str(value).split())


def parse_slate(value):
    text = need(value, "slate")
    try:
        datetime.datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise Refused("slate must be a date like 2026-11-15")
    return text


def grade_kind(side, line):
    """over_under: value is the stat or total. spread and moneyline: value is the
    picked side's final margin (its points minus the opponent's)."""
    if side.casefold() in ("over", "under"):
        if line is None:
            raise Refused("an over or under call needs a line")
        return "over_under"
    return "moneyline" if line is None else "spread"


def settle(kind, side, line, value):
    if kind == "over_under":
        diff = value - line
        if side.casefold() == "under":
            diff = -diff
    elif kind == "spread":
        diff = value + line
    else:
        diff = value
    if diff > 0:
        return "win"
    return "loss" if diff < 0 else "push"


def flat_units(result, price):
    if result == "win":
        return round(price / 100.0 if price > 0 else 100.0 / abs(price), 4)
    return -1.0 if result == "loss" else 0.0


def breakeven(price):
    return 100.0 / (price + 100.0) if price > 0 else abs(price) / (abs(price) + 100.0)


def wilson(wins, n, z=1.959964):
    """Wilson 95% score interval for a win rate; None when nothing is graded."""
    if n <= 0:
        return None
    p = wins / float(n)
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def row_sha(row):
    body = {key: value for key, value in row.items() if key != "sha"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def call_identity(handle, slate, event, event_id, market, subject, side, line):
    parts = [handle.casefold(), (event_id or (slate + "/" + event)).casefold(),
             market.casefold(), (subject or "").casefold(), side.casefold(),
             "none" if line is None else repr(float(line))]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- the store

class Store(object):
    """Append-only, hash-chained JSONL file with a lock around every write."""

    def __init__(self, folder=None, ledger=LEDGER):
        self.folder = Path(folder) if folder else DEFAULT_STORE
        self.path = self.folder / ledger

    def rows(self):
        if not self.path.is_file():
            return []
        out = []
        with open(self.path, encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    out.append({"_unreadable_line": number})
        return out

    def problems(self, rows=None):
        rows = self.rows() if rows is None else rows
        found = []
        prev = GENESIS
        for index, row in enumerate(rows, 1):
            if "_unreadable_line" in row:
                found.append("line %d is not valid JSON" % row["_unreadable_line"])
                break
            if row.get("seq") != index:
                found.append("row %d has seq %r" % (index, row.get("seq")))
            if row.get("prev") != prev:
                found.append("row %d does not chain to the row before it" % index)
            if row.get("sha") != row_sha(row):
                found.append("row %d was changed after it was written" % index)
            prev = row.get("sha")
        return found

    def append(self, build):
        """build(rows) returns the new row's fields, or raises Refused. Runs under the
        lock, so duplicate checks are atomic across writers."""
        self.folder.mkdir(parents=True, exist_ok=True)
        with open(str(self.folder / ".lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            rows = self.rows()
            bad = self.problems(rows)
            if bad:
                raise Refused("ledger failed verification, nothing written: " + bad[0])
            row = dict(build(rows))
            row["seq"] = len(rows) + 1
            row["prev"] = rows[-1]["sha"] if rows else GENESIS
            row["sha"] = row_sha(row)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return row


def _slate_rows(rows, handle, slate, kind):
    return [row for row in rows if row.get("kind") == kind
            and row.get("handle", "").casefold() == handle.casefold()
            and row.get("slate") == slate]


# ---------------------------------------------------------------- writers

def add_call(store, handle, slate, event, kickoff_utc, market, side, price, book,
             posted_utc, observed_utc, source_ref, observed_by, selection_basis,
             line=None, subject=None, event_id=None, edited=False, bot_cid=None,
             note=None, source_files=None, now=None):
    now = now or utc_now()
    handle = need(handle, "handle")
    slate = parse_slate(slate)
    event = need(event, "event")
    market = need(market, "market")
    side = need(side, "side")
    book = need(book, "book (write 'unstated' if the post names none)")
    source_ref = need(source_ref, "source reference")
    observed_by = need(observed_by, "who observed it")
    selection_basis = need(selection_basis, "selection basis")
    price = parse_price(price)
    line = parse_line(line)
    kind = grade_kind(side, line)
    kickoff = parse_utc(kickoff_utc, "kickoff")
    posted = parse_utc(posted_utc, "posted time")
    observed = parse_utc(observed_utc, "observed time")
    if edited:
        raise Refused("the post was edited, so its pregame content cannot be shown")
    if posted >= kickoff:
        raise Refused("posted at or after kickoff: not a pregame call")
    if observed >= kickoff:
        raise Refused("observed at or after kickoff: not frozen pregame")
    if observed < posted:
        raise Refused("observed time is before the post time")
    if observed > now:
        raise Refused("observed time is in the future")
    if now >= kickoff:
        raise Refused("kickoff has passed: a call must be frozen here before kickoff")
    subject = " ".join(str(subject).split()) if subject else ""
    event_id = str(event_id).strip() if event_id else ""
    call_id = call_identity(handle, slate, event, event_id, market, subject, side, line)

    def build(rows):
        if any(row.get("kind") == "call" and row.get("call_id") == call_id for row in rows):
            raise Refused("duplicate: this handle's call on this exact contract "
                          "is already frozen (%s)" % call_id)
        if _slate_rows(rows, handle, slate, "no_play"):
            raise Refused("this handle already has a no_play row for %s" % slate)
        return {
            "kind": "call", "call_id": call_id, "handle": handle, "slate": slate,
            "event": event, "event_id": event_id, "kickoff_utc": iso(kickoff),
            "market": market, "subject": subject, "side": side, "line": line,
            "grade_as": kind, "price": price, "book": book,
            "posted_utc": iso(posted), "observed_utc": iso(observed),
            "recorded_utc": iso(now), "source_ref": source_ref,
            "observed_by": observed_by, "selection_basis": selection_basis,
            "edited": False, "bot_cid": (str(bot_cid).strip() if bot_cid else ""),
            "note": (" ".join(str(note).split()) if note else ""),
            "source_files": source_files or {},
        }
    return store.append(build)


def record_missing(store, handle, slate, checked_utc, source_ref, observed_by,
                   note=None, now=None):
    now = now or utc_now()
    handle = need(handle, "handle")
    slate = parse_slate(slate)
    checked = parse_utc(checked_utc, "checked time")
    source_ref = need(source_ref, "source reference")
    observed_by = need(observed_by, "who checked")
    if checked > now:
        raise Refused("checked time is in the future")

    def build(rows):
        if _slate_rows(rows, handle, slate, "call"):
            raise Refused("this handle already has a frozen call for %s" % slate)
        if _slate_rows(rows, handle, slate, "no_play"):
            raise Refused("this handle already has a no_play row for %s" % slate)
        if any(row.get("checked_utc") == iso(checked)
               for row in _slate_rows(rows, handle, slate, "missing")):
            raise Refused("duplicate: this check is already recorded")
        return {
            "kind": "missing", "handle": handle, "slate": slate,
            "checked_utc": iso(checked), "recorded_utc": iso(now),
            "source_ref": source_ref, "observed_by": observed_by,
            "note": (" ".join(str(note).split()) if note else ""),
            "meaning": "no call observed as of the check; not a loss, a pass or a pick",
        }
    return store.append(build)


def record_no_play(store, handle, slate, first_kickoff_utc, posted_utc, observed_utc,
                   source_ref, observed_by, note=None, now=None):
    now = now or utc_now()
    handle = need(handle, "handle")
    slate = parse_slate(slate)
    kickoff = parse_utc(first_kickoff_utc, "first kickoff")
    posted = parse_utc(posted_utc, "posted time")
    observed = parse_utc(observed_utc, "observed time")
    source_ref = need(source_ref, "source reference")
    observed_by = need(observed_by, "who observed it")
    if posted >= kickoff or observed >= kickoff or now >= kickoff:
        raise Refused("a no_play counts only when posted, observed and frozen "
                      "before the first kickoff")
    if observed < posted or observed > now:
        raise Refused("observed time must be after the post and not in the future")

    def build(rows):
        if _slate_rows(rows, handle, slate, "call"):
            raise Refused("this handle already has a frozen call for %s" % slate)
        if _slate_rows(rows, handle, slate, "no_play"):
            raise Refused("duplicate: no_play is already recorded for %s" % slate)
        return {
            "kind": "no_play", "handle": handle, "slate": slate,
            "first_kickoff_utc": iso(kickoff), "posted_utc": iso(posted),
            "observed_utc": iso(observed), "recorded_utc": iso(now),
            "source_ref": source_ref, "observed_by": observed_by,
            "note": (" ".join(str(note).split()) if note else ""),
        }
    return store.append(build)


def record_result(store, call_id, final_utc, source_ref, recorded_by, value=None,
                  void_reason=None, correct=False, reason=None, now=None):
    now = now or utc_now()
    call_id = need(call_id, "call id")
    final = parse_utc(final_utc, "final time")
    source_ref = need(source_ref, "source reference")
    recorded_by = need(recorded_by, "who recorded it")
    if (value is None) == (not void_reason):
        raise Refused("give exactly one of a final value or a void reason")
    if value is not None:
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise Refused("final value must be a number")
        if math.isnan(value) or math.isinf(value):
            raise Refused("final value must be a finite number")
    if correct and not (reason and str(reason).strip()):
        raise Refused("a correction needs a reason")

    def build(rows):
        calls = [row for row in rows if row.get("kind") == "call"
                 and row.get("call_id") == call_id]
        if not calls:
            raise Refused("no frozen call has id %s" % call_id)
        call = calls[0]
        kickoff = parse_utc(call["kickoff_utc"], "kickoff")
        if now < kickoff or final < kickoff:
            raise Refused("no result before kickoff")
        if final > now:
            raise Refused("final time is in the future")
        earlier = [row for row in rows if row.get("kind") == "result"
                   and row.get("call_id") == call_id]
        if earlier and not correct:
            raise Refused("this call already has a result; use a correction with a reason")
        if correct and not earlier:
            raise Refused("there is no earlier result to correct")
        if void_reason:
            result = "void"
        else:
            result = settle(call["grade_as"], call["side"], call["line"], value)
        return {
            "kind": "result", "call_id": call_id, "result": result,
            "final_value": value, "void_reason": (need(void_reason, "void reason")
                                                  if void_reason else ""),
            "graded_at": {"line": call["line"], "price": call["price"],
                          "grade_as": call["grade_as"]},
            "flat_units_at_posted_price": flat_units(result, call["price"]),
            "final_utc": iso(final), "recorded_utc": iso(now),
            "source_ref": source_ref, "recorded_by": recorded_by,
            "corrects_seq": (earlier[-1]["seq"] if earlier else None),
            "reason": (" ".join(str(reason).split()) if reason else ""),
        }
    return store.append(build)


def import_ledger(store, posts_file, definitions_file, slate, observed_by,
                  selection_basis, now=None):
    """Freeze the calls in a prospective ledger pair written by the observer:
    posts (author, original_post, published_utc, edited, posted_price, optional
    matchup) and definitions (post, event_id, kickoff, market, subject, side, point,
    minimum_price). Every row is checked before anything is written."""
    now = now or utc_now()
    with open(posts_file, encoding="utf-8") as handle:
        posts_doc = json.load(handle)
    with open(definitions_file, encoding="utf-8") as handle:
        defs_doc = json.load(handle)
    posts = None
    for value in (posts_doc.values() if isinstance(posts_doc, dict) else []):
        if isinstance(value, list) and value and all(
                isinstance(item, dict) and "original_post" in item for item in value):
            posts = value
    definitions = defs_doc.get("definitions") if isinstance(defs_doc, dict) else None
    if not posts or not definitions:
        raise Refused("the ledger pair does not hold posts and definitions")
    observed_utc = need(posts_doc.get("observed_utc"), "observed_utc in the posts file")
    slate = parse_slate(slate or posts_doc.get("slate"))
    if posts_doc.get("slate") and posts_doc.get("slate") != slate:
        raise Refused("the posts file is for slate %s, not %s" % (posts_doc.get("slate"), slate))
    selection_basis = selection_basis or posts_doc.get("sample_rule")
    by_link = {}
    for item in definitions:
        by_link[item.get("post")] = item
    files = {"posts_file": Path(posts_file).name, "posts_sha256": sha256_file(posts_file),
             "definitions_file": Path(definitions_file).name,
             "definitions_sha256": sha256_file(definitions_file)}
    prepared = []
    for post in posts:
        link = post.get("original_post")
        spec = by_link.get(link)
        if spec is None:
            raise Refused("no contract definition for post %s" % link)
        price = parse_price(post.get("posted_price"))
        if parse_price(spec.get("minimum_price")) != price:
            raise Refused("posted price and definition price differ for %s" % link)
        prepared.append(dict(
            handle=post.get("author"), slate=slate,
            event=post.get("matchup") or spec.get("event_id"),
            event_id=spec.get("event_id"), kickoff_utc=spec.get("kickoff"),
            market=spec.get("market"), subject=spec.get("subject"),
            side=spec.get("side"), line=spec.get("point"), price=price,
            book="unstated in the source ledger", posted_utc=post.get("published_utc"),
            observed_utc=observed_utc, source_ref=link, observed_by=observed_by,
            selection_basis=selection_basis, edited=bool(post.get("edited")),
            source_files=files))
    if len(prepared) != len(definitions):
        raise Refused("posts and definitions do not match one to one")
    real_rows = store.rows()
    existing = set(row.get("call_id") for row in real_rows if row.get("kind") == "call")
    for fields in prepared:
        if _slate_rows(real_rows, need(fields["handle"], "handle"), slate, "no_play"):
            raise Refused("%s already has a no_play row for %s" % (fields["handle"], slate))
    scratch = Store(store.folder, ledger=".import-check.jsonl")
    if scratch.path.exists():
        scratch.path.unlink()
    try:
        for fields in prepared:  # dry run against an empty scratch ledger
            row = add_call(scratch, now=now, **fields)
            if row["call_id"] in existing:
                raise Refused("duplicate: %s is already frozen" % row["call_id"])
    finally:
        if scratch.path.exists():
            scratch.path.unlink()
    return [add_call(store, now=now, **fields) for fields in prepared]


# ---------------------------------------------------------------- reports

def _tally():
    return {"win": 0, "loss": 0, "push": 0, "void": 0, "unknown_final": 0,
            "blinded": 0, "units": 0.0, "breakevens": []}


def _finish(tally):
    graded = tally["win"] + tally["loss"]
    interval = wilson(tally["win"], graded)
    evens = tally.pop("breakevens")
    tally["graded_win_loss"] = graded
    tally["win_rate"] = round(tally["win"] / float(graded), 4) if graded else None
    tally["wilson95"] = [round(interval[0], 4), round(interval[1], 4)] if interval else None
    tally["mean_breakeven_at_posted_prices"] = (
        round(sum(evens) / len(evens), 4) if evens else None)
    tally["flat_units_at_posted_prices"] = round(tally.pop("units"), 4)
    return tally


def build_report(rows, now=None, problems=None):
    """One report for status and grade. Picks appear only for calls whose kickoff
    has passed; before that a call is only counted."""
    now = now or utc_now()
    latest = {}
    for row in rows:
        if row.get("kind") == "result":
            latest[row["call_id"]] = row
    slates = {}
    records = {}
    pooled = _tally()
    shown = []
    for row in rows:
        kind = row.get("kind")
        if kind not in ("call", "missing", "no_play"):
            continue
        key = (row["handle"].casefold(), row["slate"])
        entry = slates.setdefault(key, {
            "handle": row["handle"], "slate": row["slate"], "state": "missing",
            "calls_frozen": 0, "blinded_until_kickoff": 0, "last_missing_check_utc": None,
            "selection_basis": ""})
        if kind == "missing":
            entry["last_missing_check_utc"] = row["checked_utc"]
            continue
        if kind == "no_play":
            entry["state"] = "no_play"
            continue
        entry["state"] = "calls"
        entry["calls_frozen"] += 1
        entry["selection_basis"] = row.get("selection_basis", "")
        tally = records.setdefault(entry["handle"], _tally())
        if parse_utc(row["kickoff_utc"], "kickoff") > now:
            entry["blinded_until_kickoff"] += 1
            tally["blinded"] += 1
            pooled["blinded"] += 1
            continue
        result = latest.get(row["call_id"])
        outcome = result["result"] if result else "unknown_final"
        for target in (tally, pooled):
            target[outcome] += 1
            if outcome in ("win", "loss"):
                target["units"] += flat_units(outcome, row["price"])
                target["breakevens"].append(breakeven(row["price"]))
        shown.append({
            "call_id": row["call_id"], "handle": row["handle"], "slate": row["slate"],
            "event": row["event"], "market": row["market"], "subject": row["subject"],
            "side": row["side"], "line": row["line"], "price": row["price"],
            "book": row["book"], "posted_utc": row["posted_utc"],
            "kickoff_utc": row["kickoff_utc"], "bot_cid": row.get("bot_cid", ""),
            "result": outcome if result else "unknown (no final recorded)",
            "final_value": result["final_value"] if result else None,
            "source_ref": row["source_ref"]})
    return {
        "as_of_utc": iso(now), "rule": RULE, "no_claim": NO_CLAIM,
        "chain_problems": list(problems or []),
        "slates": [slates[key] for key in sorted(slates)],
        "records": dict((handle, _finish(records[handle])) for handle in sorted(records)),
        "pooled": _finish(pooled), "unblinded_calls": shown,
    }


def _record_line(name, tally):
    rate = ("win rate %.1f%% (Wilson 95%% %.1f%%-%.1f%%), mean break-even %.1f%%" % (
        100 * tally["win_rate"], 100 * tally["wilson95"][0], 100 * tally["wilson95"][1],
        100 * tally["mean_breakeven_at_posted_prices"])
        if tally["graded_win_loss"] else "no graded win or loss yet")
    return ("%s: %d-%d, %d push, %d void, %d unknown final, %d blinded; %s; "
            "flat units at posted prices %+.2f" % (
                name, tally["win"], tally["loss"], tally["push"], tally["void"],
                tally["unknown_final"], tally["blinded"], rate,
                tally["flat_units_at_posted_prices"]))


def render(report, with_calls):
    lines = ["Public comparators as of %s (kept apart from the bot's calls)"
             % report["as_of_utc"], report["rule"]]
    if report["chain_problems"]:
        lines.append("LEDGER PROBLEM: " + "; ".join(report["chain_problems"]))
    if not report["slates"]:
        lines.append("No comparator rows yet.")
    for entry in report["slates"]:
        if entry["state"] == "calls":
            detail = "%d call(s) frozen pregame, %d still blinded until kickoff" % (
                entry["calls_frozen"], entry["blinded_until_kickoff"])
        elif entry["state"] == "no_play":
            detail = "explicit no-play observed before kickoff"
        else:
            detail = ("missing: no call observed (last check %s); not a loss or a pass"
                      % entry["last_missing_check_utc"])
        lines.append("  %s on %s: %s" % (entry["handle"], entry["slate"], detail))
    for handle, tally in report["records"].items():
        lines.append("  " + _record_line(handle, tally))
    if len(report["records"]) > 1:
        lines.append("  " + _record_line("all handles pooled", report["pooled"]))
    if with_calls:
        for call in report["unblinded_calls"]:
            line = "" if call["line"] is None else " %s" % call["line"]
            lines.append("  [%s] %s: %s %s %s%s at %+d (%s) -> %s" % (
                call["call_id"], call["handle"], call["event"],
                call["subject"] or call["market"], call["side"], line, call["price"],
                call["book"], call["result"]))
        hidden = report["pooled"]["blinded"]
        if hidden:
            lines.append("  %d call(s) are hidden until their kickoff." % hidden)
    lines.append(report["no_claim"])
    return "\n".join(lines)


# ---------------------------------------------------------------- command line

def build_parser():
    parser = argparse.ArgumentParser(
        prog="comparator.py", description="Blinded public-comparator ledger (paper only).")
    parser.add_argument("--data", help="store folder (default: comparator_data beside this file)")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    add = sub.add_parser("add", help="freeze one observed public pregame call")
    for flag in ("--handle", "--slate", "--event", "--kickoff-utc", "--market", "--side",
                 "--price", "--book", "--posted-utc", "--observed-utc", "--source-ref",
                 "--observed-by", "--selection-basis", "--line", "--subject",
                 "--event-id", "--bot-cid", "--note"):
        add.add_argument(flag)
    add.add_argument("--edited", action="store_true", help="the post shows as edited")

    missing = sub.add_parser("missing", help="record that no call was observed")
    for flag in ("--handle", "--slate", "--checked-utc", "--source-ref", "--observed-by",
                 "--note"):
        missing.add_argument(flag)

    no_play = sub.add_parser("no-play", help="record an explicit public no-play")
    for flag in ("--handle", "--slate", "--first-kickoff-utc", "--posted-utc",
                 "--observed-utc", "--source-ref", "--observed-by", "--note"):
        no_play.add_argument(flag)

    result = sub.add_parser("result", help="record a final for a frozen call")
    for flag in ("--call-id", "--value", "--void", "--final-utc", "--source-ref",
                 "--recorded-by", "--reason"):
        result.add_argument(flag)
    result.add_argument("--correct", action="store_true")

    imported = sub.add_parser("import-ledger", help="freeze an observer's ledger pair")
    for flag in ("--posts", "--definitions", "--slate", "--observed-by",
                 "--selection-basis"):
        imported.add_argument(flag)

    for name in ("status", "grade"):
        report = sub.add_parser(name)
        report.add_argument("--json", action="store_true")
    sub.add_parser("verify", help="check the hash chain")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    store = Store(args.data)
    try:
        if args.command == "add":
            row = add_call(
                store, args.handle, args.slate, args.event, args.kickoff_utc, args.market,
                args.side, args.price, args.book, args.posted_utc, args.observed_utc,
                args.source_ref, args.observed_by, args.selection_basis, line=args.line,
                subject=args.subject, event_id=args.event_id, edited=args.edited,
                bot_cid=args.bot_cid, note=args.note)
            print("Frozen call %s for %s (row %d). It stays hidden until kickoff."
                  % (row["call_id"], row["handle"], row["seq"]))
        elif args.command == "missing":
            row = record_missing(store, args.handle, args.slate, args.checked_utc,
                                 args.source_ref, args.observed_by, note=args.note)
            print("Recorded missing for %s on %s (row %d): not a loss or a pass."
                  % (row["handle"], row["slate"], row["seq"]))
        elif args.command == "no-play":
            row = record_no_play(store, args.handle, args.slate, args.first_kickoff_utc,
                                 args.posted_utc, args.observed_utc, args.source_ref,
                                 args.observed_by, note=args.note)
            print("Recorded no-play for %s on %s (row %d)."
                  % (row["handle"], row["slate"], row["seq"]))
        elif args.command == "result":
            row = record_result(store, args.call_id, args.final_utc, args.source_ref,
                                args.recorded_by, value=args.value, void_reason=args.void,
                                correct=args.correct, reason=args.reason)
            print("Result for %s: %s at the posted line and price (row %d)."
                  % (row["call_id"], row["result"], row["seq"]))
        elif args.command == "import-ledger":
            if not args.posts or not args.definitions:
                raise Refused("--posts and --definitions are required")
            rows = import_ledger(store, args.posts, args.definitions, args.slate,
                                 args.observed_by, args.selection_basis)
            print("Froze %d call(s): %s. They stay hidden until kickoff."
                  % (len(rows), ", ".join(row["call_id"] for row in rows)))
        elif args.command == "verify":
            rows = store.rows()
            bad = store.problems(rows)
            if bad:
                print("FAILED: " + "; ".join(bad))
                return 1
            print("Chain intact: %d row(s)." % len(rows))
        else:
            rows = store.rows()
            report = build_report(rows, problems=store.problems(rows))
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(render(report, with_calls=(args.command == "grade")))
            if report["chain_problems"]:
                return 1
    except Refused as refusal:
        print("REFUSED: %s" % refusal, file=sys.stderr)
        return 1
    except (OSError, ValueError) as problem:
        print("REFUSED: could not read the input (%s)" % problem, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
