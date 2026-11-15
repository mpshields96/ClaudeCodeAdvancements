#!/usr/bin/env python3
"""Fetch public ESPN postgame data once, by hand, and feed it to the postgame intake.

One call is one click. It sends GET requests only, with the default urllib request and no
key, account, cookie or header changes. It has no retry, loop or schedule. Requests:
  * one scoreboard per date:  https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=YYYYMMDD
  * one game summary (boxscore) per completed scoreboard game that matches a journal game whose
    player results are still missing: .../nfl/summary?event=<ESPN event id>
Every response is saved raw in a new folder captures/espn.<UTC>/ with MANIFEST.json (url, time,
HTTP status, bytes, sha256). Nothing is overwritten. The saved files then go through
postgame.import_from_public, which alone writes to the journal, through the journal's own
record_final and record_player_result. A failed request (403, timeout, not JSON) is a refusal
for that item; the other items still proceed.

    import espn_fetch
    summary = espn_fetch.fetch_and_import(journal_dir, now=None, save_root=None, dates=None)

CLI (exit 0 nothing pending, 2 some items pending, 1 a refusal or failed request):
    /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -B espn_fetch.py [--data DIR] [--json] [--date YYYYMMDD ...]

Stdlib only, Python 3.9. No Odds API, no odds_feed.
"""
from __future__ import print_function

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT = os.path.dirname(HERE)
for _d in (EXPERIMENT, HERE):
    if _d not in sys.path:
        sys.path.insert(0, _d)

import journal as J  # noqa: E402  (read-only to this module's author)
import postgame as PG  # noqa: E402

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=%s"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=%s"
CAPTURES = os.path.join(HERE, "captures")
TIMEOUT = 20
MAX_BYTES = 20 * 1024 * 1024
DATE = re.compile(r"^\d{8}$")
EVENT_ID = re.compile(r"^\d{1,12}$")
URLOPEN = urllib.request.urlopen   # the tests swap in a fake opener; nothing here sets headers


def _valid_date(text):
    if not isinstance(text, str) or not DATE.match(text):
        return False
    try:
        datetime.datetime.strptime(text, "%Y%m%d")
    except ValueError:
        return False
    return True


def due_dates(state, now):
    """US dates (YYYYMMDD) of journal games past kickoff + 150 minutes that still lack a final or a player result."""
    needs = PG.needs_of(state)
    out = set()
    for ev_id, ev in state.events.items():
        kick = J.parse_utc(ev["kickoff_utc"])
        if now < J._earliest_final(kick):
            continue
        players = (needs.get(ev_id) or {}).get("players") or set()
        lacks_player = any((ev_id, key, market) not in state.player_results for key, _s, market in players)
        lacks_half = bool(needs.get(ev_id, {}).get("h1") and state.scores.get(ev_id, {}).get("h1_home") is None)
        if ev_id not in state.scores or lacks_player or lacks_half:
            out.add((kick - PG.LOCAL_SHIFT).strftime("%Y%m%d"))
    return sorted(out)


def _new_dir(root, start):
    os.makedirs(root, exist_ok=True)
    base = os.path.join(root, "espn." + start.strftime("%Y%m%dT%H%M%SZ"))
    path, n = base, 1
    while True:
        try:
            os.mkdir(path)
            return path
        except FileExistsError:
            n += 1
            path = "%s.%d" % (base, n)


def _get(url, save_dir, name, clock):
    """One GET. Saves the body only on HTTP 200. Returns the manifest row."""
    rec = {"url": url, "http_status": None, "retrieved_utc": None, "bytes": 0, "sha256": None,
           "path": None, "error": None}
    body = None
    try:
        resp = URLOPEN(url, timeout=TIMEOUT)
        try:
            rec["http_status"] = resp.getcode()
            body = resp.read(MAX_BYTES + 1)
        finally:
            resp.close()
    except urllib.error.HTTPError as err:
        rec["http_status"] = err.code
        rec["error"] = "HTTP %s %s" % (err.code, err.reason)
        try:
            err.close()
        except Exception:
            pass
    except Exception as err:  # timeout, DNS, refused connection: recorded, never retried
        rec["error"] = "%s: %s" % (type(err).__name__, err)
    rec["retrieved_utc"] = J.stamp(clock())
    if rec["error"] is None and rec["http_status"] != 200:
        rec["error"] = "HTTP %s" % rec["http_status"]
    if rec["error"] is None and body is not None and len(body) > MAX_BYTES:
        rec["error"] = "response over %d bytes; not saved" % MAX_BYTES
    if rec["error"] is not None or body is None:
        if rec["error"] is None:
            rec["error"] = "no body"
        return rec, None
    path = os.path.join(save_dir, name)
    with open(path, "xb") as fh:   # "x": never overwrite
        fh.write(body)
    rec.update({"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "path": os.path.abspath(path)})
    try:
        doc = json.loads(body.decode("utf-8"))
    except Exception as err:
        rec["error"] = "saved, but not JSON (%s)" % type(err).__name__
        return rec, None
    return rec, doc


def _write_manifest(save_dir, start, requests):
    doc = {"made_by": "postgame/espn_fetch.py", "run_utc": J.stamp(start),
           "note": "Raw public ESPN responses, GET only, no key or account. Read with python3 -I.",
           "requests": requests}
    with open(os.path.join(save_dir, "MANIFEST.json"), "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _summary_targets(state, doc):
    """ESPN event ids of completed scoreboard games that match one journal game still missing a player result."""
    needs = PG.needs_of(state)
    out = []
    for ev in doc.get("events") or [] if isinstance(doc, dict) else []:
        if not isinstance(ev, dict):
            continue
        comps = ev.get("competitions")
        if not isinstance(comps,list) or len(comps)!=1 or not isinstance(comps[0],dict):
            continue
        comp = comps[0]
        final, _status = PG._espn_final(comp.get("status") or ev.get("status"))
        if not final:
            continue
        teams = dict((c.get("homeAway"), c) for c in comp.get("competitors") or [] if isinstance(c, dict))
        home = ((teams.get("home") or {}).get("team") or {}).get("displayName")
        away = ((teams.get("away") or {}).get("team") or {}).get("displayName")
        hits = PG._espn_matches(state, home, away, ev.get("date"), ev.get("id"))
        if len(hits) != 1:
            continue
        players = (needs.get(hits[0]) or {}).get("players") or set()
        lacks_player = any((hits[0], key, market) not in state.player_results for key, _s, market in players)
        lacks_half = bool(needs.get(hits[0],{}).get("h1") and state.scores.get(hits[0],{}).get("h1_home") is None
                          and any(PG._h1_from_linescores(teams[side].get("linescores")) is None for side in ("home","away")))
        if not (lacks_player or lacks_half):
            continue
        espn_id = str(ev.get("id") or "")
        if EVENT_ID.match(espn_id) and espn_id not in out:
            out.append(espn_id)
    return out


def fetch_and_import(journal_dir, now=None, save_root=None, dates=None):
    """Fetch once, save raw, then run postgame.import_from_public on the saved files. See the module doc."""
    start = now or J.utc_now()
    clock = (lambda: now) if now is not None else J.utc_now
    bad = [d for d in (dates or []) if not _valid_date(d)]
    refusals = [{"what": "--date %s" % d, "reason": "not a YYYYMMDD calendar date; nothing fetched for it"} for d in bad]
    try:
        state = J.State(J.Journal(journal_dir))
    except J.JournalError as err:
        summary = PG.import_from_public(journal_dir, paths=[], now=now)   # reports the journal refusal
        summary["fetch"] = {"save_dir": None, "dates": [], "requests": [], "error": str(err)}
        return PG._finish(summary)
    want = sorted(set(d for d in dates if _valid_date(d))) if dates is not None else due_dates(state, start)
    if not want:
        summary = PG.import_from_public(journal_dir,paths=[],now=now)
        summary["refused"].extend(refusals)
        summary["notes"].append("No due date to fetch. No request or new capture was made.")
        summary["fetch"] = {"save_dir":None, "dates":[], "requests":[]}
        return PG._finish(summary)
    save_dir = _new_dir(save_root or CAPTURES, start)
    requests, saved, requested_ids = [], [], set()
    for day in want:
        rec, doc = _get(SCOREBOARD % day, save_dir, "scoreboard_%s.json" % day, clock)
        requests.append(rec)
        if rec["error"] is not None:
            refusals.append({"what": rec["url"], "reason": "request failed: %s; nothing recorded from it" % rec["error"]})
            continue
        saved.append(rec["path"])
        for espn_id in _summary_targets(state, doc):
            if espn_id in requested_ids:
                continue
            requested_ids.add(espn_id)
            srec, _sdoc = _get(SUMMARY % espn_id, save_dir, "summary_%s.json" % espn_id, clock)
            requests.append(srec)
            if srec["error"] is not None:
                refusals.append({"what": srec["url"], "reason": "request failed: %s; that game's player numbers "
                                 "stay pending" % srec["error"]})
                continue
            saved.append(srec["path"])
    _write_manifest(save_dir, start, requests)
    receipts = {r["path"]:r for r in requests if r.get("path") and not r.get("error")}
    summary = PG.import_from_public(journal_dir, paths=saved, now=now, receipts=receipts)
    summary["refused"].extend(refusals)
    summary["fetch"] = {"save_dir": os.path.abspath(save_dir), "dates": want, "requests": requests}
    return PG._finish(summary)


def render(summary):
    f = summary.get("fetch") or {}
    lines = ["ESPN fetch into %s (dates: %s)" % (f.get("save_dir"), ", ".join(f.get("dates") or []) or "none")]
    for r in f.get("requests") or []:
        if r["error"] is None:
            lines.append("  GET %s -> HTTP %s, %d bytes, sha256 %s" % (r["url"], r["http_status"], r["bytes"], r["sha256"][:12]))
        else:
            lines.append("  GET %s -> FAILED: %s" % (r["url"], r["error"]))
    return "\n".join(lines) + "\n" + PG.render(summary)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fetch public ESPN postgame data once and record it in the journal.")
    ap.add_argument("--data", default=J.DEFAULT_DATA, help="the journal's data directory")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    ap.add_argument("--date", nargs="+", action="extend", metavar="YYYYMMDD",
                    help="dates to fetch (default: the journal's own due dates)")
    args = ap.parse_args(argv)
    summary = fetch_and_import(args.data, dates=args.date)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str) if args.json else render(summary))
    return summary["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
