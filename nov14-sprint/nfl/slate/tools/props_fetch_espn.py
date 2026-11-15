"""Capture ESPN public keyless prop-bet JSON for the Sunday Nov 15 2026 NFL slate.

Usage: /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 -I props_fetch_espn.py <lines_json> <out_dir>
Stdlib only (Python 3.9). Plain urllib, default user agent, no key, no login, no retry on 403.
Writes raw response bytes to <out_dir>/<name>.json plus MANIFEST.json (url, retrieved_utc,
http, bytes, sha256). Never overwrites: out_dir must not exist.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
SUNDAY_PREFIXES = ("2026-11-15",)
EXTRA_KICKOFFS = ("2026-11-16T01:20Z",)  # Sunday night PIT at CIN


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def fetch(url, timeout=40):
    """One GET. Returns (http_code, body_bytes, error_or_None). One retry only on a network error."""
    last_err = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.getcode(), r.read(), None
        except urllib.error.HTTPError as e:  # 403, 404 etc: record, never bypass, never retry
            return e.code, e.read() if hasattr(e, "read") else b"", "HTTPError"
        except Exception as e:  # network error / timeout: one retry
            last_err = repr(e)
            time.sleep(1.0)
    return 0, b"", last_err


class Store:
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.manifest = []

    def get(self, name, url):
        retrieved = utc_now()
        code, body, err = fetch(url)
        sha = hashlib.sha256(body).hexdigest()
        path = os.path.join(self.out_dir, name + ".json")
        if body:
            with open(path, "wb") as f:
                f.write(body)
        self.manifest.append({"name": name, "url": url, "retrieved_utc": retrieved,
                              "http": code, "bytes": len(body), "sha256": sha, "error": err})
        return code, body


def fetch_event(store, event_id):
    base = "%s/events/%s/competitions/%s" % (CORE, event_id, event_id)
    store.get("odds_%s" % event_id, base + "/odds?lang=en&region=us")
    url = base + "/odds/100/propBets?lang=en&region=us&page=%d"
    code, body = store.get("propbets_%s_p001" % event_id, url % 1)
    if code != 200:
        return
    pages = json.loads(body.decode("utf-8")).get("pageCount", 1)
    for p in range(2, pages + 1):
        store.get("propbets_%s_p%03d" % (event_id, p), url % p)
        time.sleep(0.05)


def main():
    lines_path, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=False)
    with open(lines_path, encoding="utf-8") as f:
        lines = json.load(f)
    events = []
    for g in lines["games"]:
        k = g["kickoff_utc"]
        if k.startswith(SUNDAY_PREFIXES) or k in EXTRA_KICKOFFS:
            events.append(g["event_id"])
    assert len(events) == 12, events
    store = Store(out_dir)
    store.get("teams", SITE + "/teams?limit=40")
    team_ids = set()
    code, body = store.manifest and (store.manifest[0]["http"], open(os.path.join(out_dir, "teams.json"), "rb").read())
    teams = json.loads(body.decode("utf-8"))["sports"][0]["leagues"][0]["teams"]
    id_by_name = {t["team"]["displayName"]: t["team"]["id"] for t in teams}
    for g in lines["games"]:
        if g["event_id"] in events:
            team_ids.add(id_by_name[g["teams"]["home"]])
            team_ids.add(id_by_name[g["teams"]["away"]])
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda e: fetch_event(store, e), events))
        list(ex.map(lambda t: store.get("roster_%s" % t, "%s/teams/%s/roster" % (SITE, t)), sorted(team_ids)))
    store.manifest.sort(key=lambda m: m["name"])
    with open(os.path.join(out_dir, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump({"retrieved_utc": utc_now(), "events": events, "files": store.manifest}, f, indent=1)
    bad = [m for m in store.manifest if m["http"] != 200]
    print("files=%d non200=%d" % (len(store.manifest), len(bad)))
    for m in bad[:20]:
        print(m["name"], m["http"], m["error"])


if __name__ == "__main__":
    main()
