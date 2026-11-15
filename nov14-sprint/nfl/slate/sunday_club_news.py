"""Dated, operator-entered club bulletins. Reading a Sunday never contacts a source."""
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

import sunday_availability as availability

STATUSES = ("Out", "Doubtful", "Questionable", "Designation removed")
NFL_DOMAINS = set("""
nfl.com azcardinals.com atlantafalcons.com baltimoreravens.com buffalobills.com
panthers.com chicagobears.com bengals.com clevelandbrowns.com dallascowboys.com
denverbroncos.com detroitlions.com packers.com houstontexans.com colts.com
jaguars.com chiefs.com raiders.com chargers.com therams.com miamidolphins.com
vikings.com patriots.com neworleanssaints.com giants.com newyorkjets.com
philadelphiaeagles.com steelers.com 49ers.com seahawks.com buccaneers.com
tennesseetitans.com commanders.com
""".split())


def official_url(value):
    u = urlsplit(value)
    host = (u.hostname or "").lower()
    return (u.scheme == "https" and not u.username and not u.password and u.port in (None, 443)
            and any(host == site or host.endswith("." + site) for site in NFL_DOMAINS))


def store(day, schedule, root, fields, *, now=None):
    now = now or availability._now()
    events = availability._events(day, schedule)
    eid, _, team = fields.get("club_team", "").partition("/")
    event = events.get(eid, {})
    if team not in event.get("teams", []):
        raise ValueError("Choose a team on this dated schedule.")
    if now >= availability._instant(event["kickoff_utc"]):
        raise ValueError("This game has started. Pregame bulletin entry is closed.")
    player = fields.get("player", "").strip()
    role = fields.get("role", "").strip()
    position = fields.get("position", "").strip().upper()
    status = fields.get("designation")
    source = fields.get("source", "").strip()
    if not player or len(player) > 90 or not role or len(role) > 350 or len(position) > 20:
        raise ValueError("Enter a player and a short description of the role or uncertainty.")
    if status not in STATUSES or not official_url(source) or len(source) > 1500:
        raise ValueError("Choose a designation and cite an official NFL or club page.")
    published = date.fromisoformat(fields.get("published", ""))
    if published > max(now.date(), now.astimezone(availability.CENTRAL).date()) or published > date.fromisoformat(str(day)):
        raise ValueError("A bulletin publication date cannot be in the future.")
    record = dict(schema="club_bulletin/1", day=str(day), event=event, team=team, player=player,
                  position=position or "position unconfirmed", status=status, role=role, source_url=source,
                  published=published.isoformat(), recorded_utc=availability._stamp(now),
                  reported_material=fields.get("material") == "yes")
    data = (json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n").encode()
    folder = Path(root) / str(day) / "club_notes"
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / (hashlib.sha256(data).hexdigest() + ".json")
    with NamedTemporaryFile(dir=folder, delete=False) as f:
        pending = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
            try:
                os.link(pending, receipt)
            except FileExistsError:
                pass
        finally:
            pending.unlink(missing_ok=True)
    return record


def merged(day, schedule, root, data, *, as_of=None):
    now = as_of or availability._now()
    events = availability._events(day, schedule)
    records = {}
    discarded = False
    folder = Path(root) / str(day) / "club_notes"
    for path in folder.glob("*.json"):
        try:
            raw = path.read_bytes()
            obj = json.loads(raw)
            eid = obj["event"]["espn_event_id"]
            if (hashlib.sha256(raw).hexdigest() != path.stem or obj["schema"] != "club_bulletin/1"
                    or obj["day"] != str(day) or events.get(eid) != obj["event"]
                    or obj["team"] not in events[eid]["teams"] or obj["status"] not in STATUSES
                    or not official_url(obj["source_url"])):
                raise ValueError("Unverified bulletin")
            received = availability._instant(obj["recorded_utc"])
            if received > now or now >= availability._instant(events[eid]["kickoff_utc"]):
                continue
            key = eid, obj["team"], availability._name_key(obj["player"])
            order = date.fromisoformat(obj["published"]), received, path.stem
            if key not in records or order > records[key][0]:
                records[key] = order, obj
        except (OSError, KeyError, ValueError, TypeError):
            discarded = True
    if not records and not discarded:
        return data
    result = deepcopy(data)
    if discarded:
        result["limitations"].append("A saved club note could not be matched to its original game or verified.")
    for (eid, team, player_key), (_, row) in sorted(records.items()):
        ev = result["by_event"][eid]
        matches = [r for r in ev["records"] if r["team"] == team and availability._name_key(r["player"]) == player_key]
        if len(matches) > 1:
            result["limitations"].append(f"The club note for {team} {row['player']} matches multiple feed records. Verify the player's identity.")
            continue
        previous = next(iter(matches), None)
        if previous is not None:
            ev["records"].remove(previous)
        ev.setdefault("league_status", ev["status"])
        if ev["status"] != "reported":
            ev["status"] = "partial"
        entry = dict(row, observed_utc=row["recorded_utc"], player_published_utc=None,
                     starter_status="operator_identified" if row["reported_material"] else "unknown",
                     candidates=[], depth_ranks=[], depth_chart_utc=None, depth_source_url=None,
                     previous_feed_status=previous["status"] if previous else None, origin="operator_bulletin")
        # A club designation updates availability. The separate depth-chart source
        # still establishes the player's rank, without establishing a backup's role.
        if previous is not None:
            if entry["position"] == "position unconfirmed" and previous.get("position"):
                entry["position"] = previous["position"]
            if previous.get("depth_source_url") and previous.get("depth_chart_utc"):
                entry.update(depth_ranks=previous.get("depth_ranks", []),
                             depth_chart_utc=previous["depth_chart_utc"],
                             depth_source_url=previous["depth_source_url"])
                if previous.get("starter_status") == "listed_first":
                    entry["starter_status"] = "listed_first"
        ev["records"].append(entry)
    if records:
        result["league_status"] = data["status"]
        if data["status"] != "reported":
            result["status"] = "partial"
        result["limitations"].append("Dated club notes are entered by the operator. League-feed coverage and the club source date are shown separately.")
    return result
