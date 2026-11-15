"""Public, regular-season NFL injury designations and timestamped depth-chart context.

capture(day, schedule, root) fetches explicitly, at most once per hour per dated
schedule after a successful read. read(...) only reads saved snapshots. Supply
the raw ESPN NFL scoreboard (or its weekly_api.load_schedule wrapper) and the
weekly_inputs directory. Results are keyed by ESPN event ID, not odds event ID.
"""
import csv
import fcntl
import gzip
import hashlib
import io
import json
import os
import tempfile
import unicodedata
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

UTC = timezone.utc
CENTRAL = ZoneInfo("America/Chicago")
TTL = timedelta(hours=1)
BASE = "https://github.com/nflverse/nflverse-data/releases/download"
LICENSE = "https://github.com/nflverse/nflverse-data/blob/main/LICENSE.md"
SCHEMA = "sunday_availability/1"
REVISION = 2
MISSING = {"", "NA", "N/A"}
ABSENCES = {"Out", "Doubtful"}
LIMITS = [
    "Weekly game designations are separate from practice participation and final inactives. An empty result cannot establish health.",
    "Injury observation times record our retrieval. The season feed supplies no individual publication time.",
    "Depth ranks describe a recorded formation. Named candidates have unconfirmed workloads and price impact.",
]

def _now():
    return datetime.now(UTC)

def _stamp(t):
    return t.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

def _instant(s):
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("Timezone required")
    return t.astimezone(UTC)

def _team(s):
    return {"WSH": "WAS", "LAR": "LA", "JAC": "JAX"}.get(s, s)

def _events(day, schedule):
    day = date.fromisoformat(str(day))
    doc = schedule.get("doc", schedule)
    if not isinstance(doc.get("events"), list):
        raise ValueError("An ESPN scoreboard with events is required.")
    if doc.get("leagues") and not any(lg.get("slug") == "nfl" for lg in doc["leagues"]):
        raise ValueError("Expected an NFL scoreboard")
    events = {}
    scheduled_teams = set()
    for ev in doc["events"]:
        kick = _instant(ev["date"])
        if kick.astimezone(CENTRAL).date() != day:
            continue
        eid = str(ev["id"])
        if not eid.isdigit() or eid in events:
            raise ValueError("Missing or duplicate ESPN event ID")
        sides = {c["homeAway"]: _team(c["team"]["abbreviation"]) for c in ev["competitions"][0]["competitors"]}
        teams = [sides["away"], sides["home"]]
        if not all(teams) or len(set(teams)) != 2:
            raise ValueError("Schedule must identify both teams")
        if scheduled_teams.intersection(teams):
            raise ValueError("NFL team scheduled more than once on the same day")
        scheduled_teams.update(teams)
        events[eid] = dict(espn_event_id=eid, teams=teams, kickoff_utc=_stamp(kick),
                           season=int(ev["season"]["year"]), season_type=int(ev["season"]["type"]),
                           week=int(ev["week"]["number"]))
    return events

def _blank(events, status, note=None):
    return dict(schema=SCHEMA, revision=REVISION, status=status, captured_utc=None, expires_utc=None, sources={},
                limitations=LIMITS + ([note] if note else []),
                by_event={eid:dict(e, status=status, records=[], team_coverage={}) for eid,e in events.items()})

def _identity(events):
    return hashlib.sha256(json.dumps(events, sort_keys=True).encode()).hexdigest()

def _digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def _capture_name(stamp, sig):
    return "capture-" + stamp.strftime("%Y%m%dT%H%M%S%fZ") + "-" + sig + ".json"

def _read_capture(path, day, events, sig, now, *, replay):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if obj.get("revision") != REVISION:
            return _blank(events, "refresh_required", "Refresh the earlier availability capture to verify its identities.")
        checksum = obj.pop("snapshot_sha256")
        if _digest(obj) != checksum or obj["schema"] != SCHEMA or obj["schedule_sha256"] != sig:
            raise ValueError("Saved availability integrity check failed")
        obj["snapshot_sha256"] = checksum
        if set(obj["by_event"]) != set(events) or obj["slate_date"] != str(day):
            raise ValueError("Saved schedule differs")
        for eid, expected in events.items():
            if any(obj["by_event"][eid][key] != value for key,value in expected.items()):
                raise ValueError("Saved event identity differs")
        when = _instant(obj["captured_utc"])
        if replay and path.name != _capture_name(when, sig):
            raise ValueError("Saved capture time differs from its archive name")
        if _instant(obj["expires_utc"]) != when + TTL:
            raise ValueError("Invalid capture lifetime")
        if now < when or now >= when + TTL:
            obj["status"] = "stale"
            obj["limitations"].append("The capture has expired or is future-dated. Run an explicit refresh.")
        for ev in obj["by_event"].values():
            if obj["status"] == "stale" or _instant(ev["kickoff_utc"]) <= now:
                ev.update(status="stale" if obj["status"] == "stale" else "started", records=[], team_coverage={})
        if obj["by_event"] and all(x["status"] == "started" for x in obj["by_event"].values()):
            obj["status"] = "started"
        return obj
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return _blank(events, "unreadable", "The saved availability snapshot could not be verified.")

def _load(day, events, root, as_of=None):
    folder = Path(root) / date.fromisoformat(str(day)).isoformat() / "availability"
    sig = _identity(events)
    paths = sorted(folder.glob("capture-*-" + sig + ".json"), reverse=True)
    if as_of is None:
        if paths:
            return _read_capture(paths[0], day, events, sig, _now(), replay=False)
        return _blank(events, "uncaptured")

    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("as_of requires a timezone-aware datetime")
    now = as_of.astimezone(UTC)
    last_name = _capture_name(now, sig)
    failure = None
    for path in paths:
        if path.name > last_name:
            continue
        snapshot = _read_capture(path, day, events, sig, now, replay=True)
        if snapshot["status"] not in {"unreadable", "refresh_required"}:
            return snapshot
        if failure is None:
            failure = snapshot
    return failure if failure is not None else _blank(events, "uncaptured")

def read(day, schedule, root, *, as_of=None):
    """Read offline. A timezone-aware as_of selects and evaluates the last verified capture then available."""
    return _load(day, _events(day, schedule), root, as_of)

def _download(kind, season):
    url = f"{BASE}/{kind}/{kind}_{season}.csv.gz"
    max_bytes = (4 if kind == "injuries" else 45) * 1024 * 1024
    with urlopen(Request(url, headers={"User-Agent": "NFL-availability-research/1"}), timeout=20) as r:
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes or not data.startswith(b"\x1f\x8b"):
        raise ValueError(f"Unexpected {kind} archive size or type")
    receipt = dict(status="ok", source_url=url, observed_utc=_stamp(_now()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                   license_url=LICENSE)
    return data, receipt

def _rows(data, required):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream, io.TextIOWrapper(stream, encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        if not required.issubset(rows.fieldnames or []):
            raise ValueError("Public release lacks required columns")
        yield from rows

def _injuries(season, keys):
    data, source = _download("injuries", season)
    grouped = defaultdict(list)
    source.update(rows=0, latest_regular_week=None)
    required = {"season","team","week","gsis_id","full_name","position","report_status","game_type"}
    for r in _rows(data, required):
        source["rows"] += 1
        if r["season"] != str(season) or r["game_type"] != "REG":
            continue
        week = int(r["week"])
        source["latest_regular_week"] = max(week, source["latest_regular_week"] or week)
        key = week, _team(r["team"])
        if key in keys:
            grouped[key].append(r)
    if not source["rows"]:
        raise ValueError("Empty injury release")
    return grouped, source

def _depth(season, teams, observed):
    data, source = _download("depth_charts", season)
    latest, rows = {}, defaultdict(list)
    # Regular-season NFL injury weeks run Tue–Mon. No previous-window chart
    # may supply a rank. Upstream uses UTC ISO strings; parse each unique dt once.
    parsed = {}
    observed = min(observed, _instant(source["observed_utc"]))
    for r in _rows(data, {"dt","team","player_name","gsis_id","pos_grp","pos_slot","pos_abb","pos_rank"}):
        t = _team(r["team"])
        if t not in teams:
            continue
        key = r["dt"]
        if key not in parsed:
            parsed[key] = _instant(key)
        ts = parsed[key]
        start, kickoff = teams[t]
        if not start <= ts <= observed or ts >= kickoff:
            continue
        if t not in latest or ts > latest[t]:
            latest[t] = ts
            rows[t].clear()
        if ts == latest[t] and r["pos_rank"].isdigit() and int(r["pos_rank"]) > 0:
            rows[t].append(r)
    source["chart_timestamps_by_team"] = {k:_stamp(v) for k,v in latest.items()}
    return rows, source

def _roster_status(rows):
    result = defaultdict(set)
    for r in rows:
        pid = r["gsis_id"] if r["gsis_id"] not in MISSING else r["full_name"]
        if pid not in MISSING:
            result[pid].add(r["report_status"].strip() or "undesignated")
    return result

def _name_key(name):
    return "".join(c for c in unicodedata.normalize("NFKD",name).casefold() if c.isalnum())

def _records(team, injury_rows, depth_rows, injury_source, depth_source):
    statuses = _roster_status(injury_rows)
    names = defaultdict(list)
    for row in injury_rows:
        names[_name_key(row["full_name"])].append(row)
    recs = {}
    for r in injury_rows:
        pid, name, status = r["gsis_id"], r["full_name"], r["report_status"].strip()
        identity = name if pid in MISSING else pid
        if status not in ABSENCES or name in MISSING or len(statuses[identity]) != 1 or identity in recs:
            continue
        chart = [d for d in depth_rows if pid not in MISSING and d["gsis_id"] == pid]
        ranks = [dict(formation=d["pos_grp"], slot=d["pos_slot"], position=d["pos_abb"], rank=int(d["pos_rank"])) for d in chart]
        candidates = {}
        starter_slots = {(d["pos_grp"], d["pos_slot"], d["pos_abb"]) for d in chart if d["pos_rank"]=="1"}
        for form,slot,pos in sorted(starter_slots):
            same_slot = [d for d in depth_rows if (d["pos_grp"],d["pos_slot"],d["pos_abb"])==(form,slot,pos)]
            for d in same_slot:
                rank = int(d["pos_rank"])
                cpid, cname = d["gsis_id"], d["player_name"]
                if rank not in (2,3) or cpid in MISSING or cname in MISSING or cpid == pid or _name_key(cname) == _name_key(name):
                    continue
                matches = names.get(_name_key(cname), [])
                if any(row["gsis_id"] not in MISSING and row["gsis_id"] != cpid for row in matches):
                    continue
                known = statuses.get(cpid, set()) | {row["report_status"].strip() or "undesignated" for row in matches}
                if known & ABSENCES or len(known) > 1:
                    continue
                candidates[(form,slot,rank,cname)] = dict(player=cname, position=pos, formation=form, slot=slot, rank=rank,
                    gsis_id=None if cpid in MISSING else cpid, status="candidate_only",
                    injury_designation=next(iter(known)) if len(known)==1 and "undesignated" not in known else "unknown",
                    source_url=depth_source.get("source_url"), observed_utc=depth_source.get("observed_utc"),
                    chart_utc=depth_source.get("chart_timestamps_by_team",{}).get(team))
        recs[identity] = dict(player=name, gsis_id=None if pid in MISSING else pid, team=team, position=r["position"],
            status=status, source_url=injury_source["source_url"], observed_utc=injury_source["observed_utc"],
            player_published_utc=None, starter_status="listed_first" if starter_slots else "unknown",
            materiality="unknown", depth_ranks=ranks, depth_source_url=depth_source.get("source_url") if ranks else None,
            depth_chart_utc=depth_source.get("chart_timestamps_by_team",{}).get(team),
            candidates=[candidates[k] for k in sorted(candidates)])
    return sorted(recs.values(), key=lambda r:r["player"])

def _failed_source(kind,season,exc):
    return dict(status="error", source_url=f"{BASE}/{kind}/{kind}_{season}.csv.gz",
                attempted_utc=_stamp(_now()), error_type=type(exc).__name__)

def _build(events):
    result = _blank(events, "no_events")
    now = _now()
    live = {}
    for eid, ev in result["by_event"].items():
        if _instant(ev["kickoff_utc"]) <= now:
            ev["status"] = "started"
        elif ev["season_type"] != 2:
            ev["status"] = "unsupported_season_type"
        else:
            live[eid] = ev
    for season in sorted({v["season"] for v in live.values()}):
        these = [v for v in live.values() if v["season"] == season]
        wanted = {(v["week"], t) for v in these for t in v["teams"]}
        try:
            by_week, info = _injuries(season, wanted)
        except (OSError, ValueError, EOFError, csv.Error, URLError) as exc:
            result["sources"][f"injuries_{season}"] = _failed_source("injuries",season,exc)
            result["limitations"].append(f"Injury source unavailable for {season} ({type(exc).__name__}).")
            for ev in these:
                ev["status"] = "source_error"
            continue
        result["sources"][f"injuries_{season}"] = info
        teams = {}
        for ev in these:
            kick = _instant(ev["kickoff_utc"])
            local_date = kick.astimezone(CENTRAL).date()
            tuesday = local_date - timedelta(days=(local_date.weekday()-1) % 7)
            week_start = datetime.combine(tuesday,time.min,tzinfo=CENTRAL).astimezone(UTC)
            for team in ev["teams"]:
                if any(r["report_status"] in ABSENCES for r in by_week.get((ev["week"],team),[])):
                    teams[team] = week_start, kick
        depth, depth_source = {}, {}
        if teams:
            try:
                depth, depth_source = _depth(season, teams, _now())
                result["sources"][f"depth_charts_{season}"] = depth_source
            except (OSError, ValueError, EOFError, csv.Error, URLError) as exc:
                result["sources"][f"depth_charts_{season}"] = _failed_source("depth_charts",season,exc)
                result["limitations"].append(f"Depth chart unavailable for {season} ({type(exc).__name__}). Roles are unknown.")
        for ev in these:
            for t in ev["teams"]:
                rows = by_week.get((ev["week"],t), [])
                seen_statuses = _roster_status(rows)
                designations = sum(r["report_status"].strip() not in MISSING for r in rows)
                coverage = "no_team_rows" if not rows else ("rows_observed" if designations else "rows_without_game_designations")
                ev["team_coverage"][t] = dict(source_rows=len(rows), game_designations=designations,
                    conflicting_player_statuses=sum(len(v)>1 for v in seen_statuses.values()), status=coverage)
                ev["records"].extend(_records(t,rows,depth.get(t,[]),info,depth_source))
            found = sum(bool(v["source_rows"]) for v in ev["team_coverage"].values())
            ev["status"] = {0:"no_week_data",1:"partial",2:"reported"}[found]
            if found == 2 and any(not t["game_designations"] for t in ev["team_coverage"].values()):
                ev["status"] = "partial"
            if any(team in teams for team in ev["teams"]):
                ev["depth_status"] = "observed" if depth_source else "source_error"
                if not depth_source:
                    ev["status"] = "partial"
            else:
                ev["depth_status"] = "not_requested"
            if _instant(ev["kickoff_utc"]) <= _now():
                ev.update(status="started", records=[], team_coverage={})
    states = {e["status"] for e in result["by_event"].values()}
    result["status"] = next(iter(states)) if len(states)==1 else ("partial" if states else "no_events")
    return result

def capture(day, schedule, root):
    """Capture public CSVs on explicit invocation. Retry failed sources; retain all snapshots."""
    events = _events(day, schedule)
    day = date.fromisoformat(str(day)).isoformat()
    folder = Path(root) / day / "availability"
    folder.mkdir(parents=True, exist_ok=True)
    sig = _identity(events)
    with (folder/".capture.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        old = _load(day, events, root)
        if old["captured_utc"] and old["status"] not in {"stale","source_error","unreadable"} and not any(
                s.get("status")=="error" for s in old["sources"].values()):
            return old
        obj = _build(events)
        stamp = _now()
        obj.update(captured_utc=_stamp(stamp), expires_utc=_stamp(stamp+TTL), schedule_sha256=sig, slate_date=day)
        obj["snapshot_sha256"] = _digest(obj)
        name = _capture_name(stamp, sig)
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".pending-", mode="w", encoding="utf-8", delete=False) as f:
            pending = Path(f.name)
            try:
                json.dump(obj,f,sort_keys=True,indent=2,allow_nan=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
                os.link(pending,folder/name)
            finally:
                pending.unlink(missing_ok=True)
        return obj
