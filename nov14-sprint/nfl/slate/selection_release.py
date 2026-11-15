"""Presentation layer for dated replacement evidence. It does not rate teams or select bets."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit

import selection_markets as markets

HERE = Path(__file__).resolve().parent



def _source_receipts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _source_receipts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _source_receipts(item)


def _links(team):
    """Use only source URLs with an actual observation/receipt time."""
    links = {}
    for entry in _source_receipts(team):
        url = entry.get("url") or entry.get("source_url")
        stamp = entry.get("retrieved_utc") or entry.get("observed_utc")
        if not isinstance(url, str) or not stamp:
            continue
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or "apikey=" in parts.query.lower():
            continue
        label = entry.get("label")
        if not isinstance(label, str) or len(label) <= 2:
            label = parts.hostname.removeprefix("www.")
            path = parts.path.strip("/").split("/")
            if len(path) > 2 and path[0] == "players" and "logs" in path:
                label = path[1].replace("-", " ").title() + " game log"
            elif path and path[0] == "news":
                label += " · " + ("game preview" if "preview" in parts.path or "five-" in parts.path else "team news")
            elif "depth-chart" in parts.path:
                label += " · depth chart"
        if url not in links or markets.instant(links[url]["observed_utc"]) < markets.instant(stamp):
            links[url] = {"label": label, "url": url, "observed_utc": stamp}
    return list(links.values())



def _range(stat):
    low, high = stat["line_min"], stat["line_max"]
    return "%g" % low if low == high else "%g–%g" % (low, high)


def _active_next_men(team):
    excluded = {c["player"] for c in team.get("candidates", [])
                if str((c.get("availability") or {}).get("status") or "").lower() in ("out", "inactive", "ruled out")}
    return [c for c in team["replacement_context"].get("next_men", []) if c.get("player") not in excluded]


def _display(team, opponent):
    """A short report projection of measured usage, market terms and still-uncertain fit."""
    role = team["replacement_context"]
    candidates = team.get("candidates") or []
    starter = team.get("starter") or {}
    eligible = {n["player"] for n in _active_next_men(team)}
    known = [c for c in candidates if c["player"] in eligible and (c.get("market") or {}).get("stats", {}).get("rush_yds")]
    if candidates and not eligible:
        return "%s has a reported absence. No eligible replacement has a verified workload." % (starter.get("player") or team["team"])
    attempts = [c for c in known if c["market"]["stats"].get("rush_attempts")]
    if not starter.get("player") or not known:
        return role.get("qualifier") or "Replacement role and workload are unknown."
    absent = next((a for a in role.get("absent", []) if a["player"] == starter["player"]), {})
    parts = ["%s is %s." % (starter["player"], absent.get("status", "unavailable").lower())]
    if len(attempts) == 1:
        primary = attempts[0]
        stats = primary["market"]["stats"]
        att, yards = stats["rush_attempts"], stats["rush_yds"]
        hard_role = next((e.get("text") for e in primary.get("role_evidence", []) if e.get("kind") == "hard" and e.get("text")), None)
        if hard_role:
            parts.append(hard_role.rstrip(".") + ".")
        parts.append("%s’s posted lines are %s carries (%d books) and %s rushing yards (%d books)." %
                     (primary["player"], _range(att), len({q["book"] for q in att["books"]}),
                      _range(yards), len({q["book"] for q in yards["books"]})))
        others = []
        for c in candidates:
            if c["player"] != primary["player"] and c["player"] in eligible:
                status = str((c.get("availability") or {}).get("status") or "").lower()
                others.append(c["player"] + (" (" + status + ")" if status in ("questionable", "doubtful") else ""))
        if others and not hard_role:
            parts.append("Other possible contributors include " + " and ".join(others) + ".")
        elif hard_role:
            conditions = [name for name in others if "(" in name]
            if conditions:
                parts.append("Confirm " + " and ".join(conditions) + " at inactives.")
        h, s = primary.get("history_2026") or {}, starter.get("history_2026") or {}
        workload = (primary.get("components") or {}).get("workload") or {}
        if s.get("carries_pg") is not None:
            parts.append("%s averaged %.1f carries per game. The %.1f threshold suggests a %s workload with %s confidence." %
                    (starter["player"], s["carries_pg"], att["line_median"],
                     {"weaker":"smaller","stronger":"larger","preserved":"similar"}.get(workload.get("label"),"possible change in"),
                     workload.get("confidence") or "low"))
        if all(v is not None for v in (h.get("max_carries"), h.get("ypc"), h.get("carries"), s.get("ypc"), s.get("carries"))):
            parts.append("%s’s prior high is %d carries. He averaged %.2f yards per carry on %d attempts versus %.2f on %d for %s." %
                         (primary["player"], h["max_carries"], h["ypc"], h["carries"], s["ypc"], s["carries"], starter["player"]))
    else:
        offers = ["%s %s" % (c["player"], _range(c["market"]["stats"]["rush_yds"])) for c in known]
        parts.append("Posted rushing-yard thresholds are %s." % ", ".join(offers))
        if len(known) > 1:
            parts.append("Multiple backs have quoted workloads. Depth order alone cannot settle the split.")
    matchup = team.get("team_context") or {}
    if matchup.get("opp_allowed_ypc") is not None:
        parts.append("The %s have allowed %.2f yards per carry." % (opponent.split()[-1], matchup["opp_allowed_ypc"]))
    parts.append("A lead could favor carries. Passing-down usage matters if trailing.")
    env = team.get("priced_environment") or {}
    if env.get("implied_points") is not None:
        parts.append("Post-news lines imply about %.0f team points. The injury’s incremental win-price effect is unknown." % env["implied_points"])
    else:
        parts.append("The injury’s incremental win-price effect is unknown.")
    return " ".join(parts)


def _normalize(team, team_name, day, capture, event_id, built, opponent):
    role = team["replacement_context"]
    if role.get("schema_version") != "replacement_context/1" or role.get("event_id") != event_id or role.get("team") != team_name:
        raise ValueError("Producer role identity differs from its event and team.")
    if role.get("win_probability_adjustment") is not None or role.get("auto_upgrade") or role.get("reorders_issued_calls"):
        raise ValueError("The replacement report attempts to alter the historical selection.")
    next_men = _active_next_men(team)
    players = {r["player"] for r in role.get("absent", []) + next_men if r.get("player")}
    candidates = team.get("candidates") or []
    evidence = [dict(player=c.get("player"), role=c.get("role_evidence"), markets=c.get("market")) for c in candidates]
    capability = [dict(player=c.get("player"), history=c.get("history_2026"), components=c.get("components"),
                       vs_starter=c.get("vs_starter"), counterevidence=c.get("counterevidence")) for c in candidates]
    vs = role.get("vs_starter", "unknown")
    screen_status = team["screen_status"]
    if screen_status == "screened" and not next_men:
        screen_status = "unknown_next_man"
    qualifier = _display(team, opponent)
    return {"date": day, "event_id": event_id, "capture_sha256": capture, "team": team_name, "players": sorted(players),
            "status": "unknown" if screen_status != "screened" else "estimated", "screen_status": screen_status,
            "effective_as_of_utc": built, "latest_source_utc": role.get("as_of_utc"), "sources": _links(team),
            "display": qualifier, "absent": role.get("absent", []), "next_men": next_men,
            "opportunity": evidence, "capability": {"starter": team.get("starter"), "candidates": capability},
            "relative_to_starter": vs, "confidence": role.get("confidence"), "flag": role.get("flag"),
            "versus_priced_expectation": {"incremental_surprise": "unknown",
                    "role_market_coverage": role.get("priced_status"),
                    "basis": "A post-news quote shows a market for the replacement. It does not measure the news impact or pricing accuracy."},
            "team_price_effect": {"priced_environment": team.get("priced_environment"),
                    "pre_news_comparison": team.get("marginal_effect_of_absence"), "win_probability_adjustment": None,
                    "interpretation": "Post-news prices describe expectations. The incremental injury effect requires independent evidence."},
            "matchup": team.get("team_context"), "game_script": [dict(player=c.get("player"),
                    interpretation=list(c.get("interpretation", [])) + [r for r in c.get("role_evidence", []) if r.get("kind") == "interpretation"],
                    evidence=c.get("evidence"), counterevidence=c.get("counterevidence")) for c in candidates],
            "producer_context": role}


def read_report(day, capture, events, as_of, path=None):
    """Read one dated report; a historical report can never populate another event or feed edition."""
    stamp = date.fromisoformat(day).strftime("%Y%m%d")
    path = Path(path) if path else HERE / "replacements" / ("replacement_report_" + stamp + ".json")
    if not path.is_file():
        return {}, {"status":"unavailable", "date":day, "expected":path.name}
    raw = path.read_bytes()
    try:
        report = json.loads(raw)
    except (ValueError, UnicodeError):
        return {}, {"status":"unavailable", "file":path.name, "sha256":sha256(raw).hexdigest(), "reason":"Unreadable role report."}
    if not isinstance(report, dict):
        return {}, {"status":"unavailable", "file":path.name, "reason":"Invalid role report."}
    receipt = {"file":path.name, "sha256":sha256(raw).hexdigest(), "schema_version":report.get("schema_version"),
               "built_utc":report.get("built_utc"), "as_of_utc":report.get("as_of_utc")}
    def unavailable(reason):
        return {}, dict(receipt, status="unavailable", reason=reason)
    if report.get("schema_version") != "replacement_report/1" or report.get("paper_only") is not True:
        return unavailable("Unrecognized report schema or scope.")
    # The producer records the base feed first and auxiliary market and football receipts afterward.
    inputs = report.get("inputs") or []
    primary = inputs[0] if isinstance(inputs, list) and inputs and isinstance(inputs[0], dict) else {}
    if primary.get("sha256") != capture or not primary.get("captured_utc"):
        return unavailable("No matching source price edition.")
    built = report["built_utc"]
    if markets.instant(built) > markets.instant(as_of) or markets.instant(report["as_of_utc"]) > markets.instant(built):
        return unavailable("The assembled report or its sources were unavailable at this review time.")
    by_event, coverage, skipped = {}, {}, []
    for eid, source in report["by_event"].items():
        if eid not in events:
            continue
        game = events[eid]
        event = source["event"]
        kickoff = game["kickoff_utc"]
        if (eid != event["event_id"] or markets.instant(kickoff) != markets.instant(event["commence_utc"])
                or markets.instant(kickoff).astimezone(markets.CENTRAL).date().isoformat() != day
                or (event["away_team"],event["home_team"]) != (game["away_name"],game["home_name"])):
            skipped.append(eid + ": event, kickoff or teams differed")
            continue
        if markets.instant(built) >= markets.instant(kickoff):
            skipped.append(eid + ": review was assembled after kickoff")
            continue
        records = []
        coverage[eid] = {}
        for team_name, data in source["teams"].items():
            if team_name not in (event["away_team"],event["home_team"]):
                raise ValueError("Replacement team is outside the named event.")
            coverage[eid][team_name] = data.get("screen_status", "unknown_absence")
            if data.get("screen_status") == "unknown_absence":
                continue
            try:
                for item in _source_receipts(data):
                    for key in ("captured_utc", "retrieved_utc", "observed_utc", "last_update_utc", "as_of_utc"):
                        observed = item.get(key)
                        if observed and markets.instant(observed) > markets.instant(report["as_of_utc"]):
                            raise ValueError("A source postdates the report's source cutoff.")
                opponent = event["away_team"] if team_name == event["home_team"] else event["home_team"]
                row = _normalize(data, team_name, day, capture, eid, built, opponent)
                validate_row(row, day, capture, eid, kickoff, as_of)
            except (KeyError, TypeError, ValueError) as exc:
                coverage[eid][team_name] = "unavailable"
                skipped.append("%s %s: %s" % (eid, team_name, exc))
                continue
            records.append(row)
        if records:
            by_event[eid] = records
    return by_event, dict(receipt, status="matched" if by_event else "unavailable", team_coverage=coverage, skipped=skipped)


def validate_row(row, day, capture, event_id, kickoff, as_of=None):
    if row["date"] != day or row["event_id"] != event_id or row["capture_sha256"] != capture:
        raise ValueError("Replacement evidence belongs to a different event, date or price capture.")
    effective = markets.instant(row["effective_as_of_utc"])
    first_snap = markets.instant(kickoff)
    if effective >= first_snap or (as_of and effective > markets.instant(as_of)):
        raise ValueError("Replacement evidence was unavailable before kickoff or at the time of review.")
    for source in row.get("sources", []):
        observed = markets.instant(source["observed_utc"])
        if observed > effective or observed >= first_snap:
            raise ValueError("Replacement source was observed after the review or at/after kickoff.")


def _bound_call(call, rows, day, capture):
    """Project team context onto the exact contract; player props require a named role match."""
    expected = markets.key_for(call["event_id"], call["market"], call["subject"], call["side"], call["point"])
    if call["id"] != expected or call["period"] != markets.MARKETS[call["market"]][1]:
        raise ValueError("Replacement evidence cannot be attached to an inconsistent call identity.")
    is_prop = markets.MARKETS[call["market"]][0] == "prop"
    records = [r for r in rows if not is_prop or call["subject"] in r.get("players", [])]
    term = {key: call[key] for key in ("id", "event_id", "market", "period", "subject", "side", "point", "book", "price")}
    for r in records:
        validate_row(r, day, capture, call["event_id"], call["kickoff"])
    call["replacement_context"] = [
        dict(r, applies_to=term, evidence_after_issue=markets.instant(r["effective_as_of_utc"]) > markets.instant(call["decided_utc"]),
             timing_note="Additional pregame review, assembled separately from the issued call.")
        for r in records]
    call["replacement_review_status"] = ("Conditional; review role, injury and price before use." if records
                                         else "Unknown; no dated replacement assessment matches this contract.")


def _attach_rows(doc, by_event, receipt):
    """Only add evidence fields after scoring. Never assign an injury penalty, stake or probability."""
    selected = doc["selections"]
    doc["inputs"]["replacement_evidence"] = dict(receipt or {"status": "unavailable"},
            projection_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    for g in doc["slate"]["games"]:
        rows = by_event.get(g["event_id"], [])
        for row in rows:
            validate_row(row, selected["slate_date"], selected["capture_sha256"], g["event_id"],
                         g["kickoff_utc"], doc["run_utc"])
        g["replacement_team_coverage"] = (receipt or {}).get("team_coverage", {}).get(g["event_id"], {})
        g["replacement_context"] = rows
        g["replacement_review_status"] = ("See the dated role assessments." if rows else
                "Unknown; no dated replacement assessment matched this game.")
    for call in selected["calls"]:
        _bound_call(call, by_event.get(call["event_id"], []), selected["slate_date"], selected["capture_sha256"])
        call["replacement_team_coverage"] = (receipt or {}).get("team_coverage", {}).get(call["event_id"], {})
    return doc


def _review_notes(doc):
    selected = doc["selections"]
    path = HERE / "results/sunday_20261115_review_evidence.json"
    if not path.is_file():
        return
    raw = path.read_bytes()
    notes = json.loads(raw)
    if (notes.get("slate_date") != selected["slate_date"] or notes.get("capture_sha256") != selected["capture_sha256"]
            or notes.get("issued_utc") != selected["decided_utc"] or markets.instant(notes["verified_utc"]) > markets.instant(doc["run_utc"])):
        return
    doc["inputs"]["supplemental_review"] = {"sha256":sha256(raw).hexdigest(), "file":path.name,
                                             "verified_utc":notes["verified_utc"]}
    if "late" in notes.get("by_window", {}) and selected["window_notes"].get("late"):
        late = notes["by_window"]["late"]
        selected["window_notes_sources"] = {"late": {k:late[k] for k in (
            "display","source","source_url","sha256","retrieved_utc","local_file_modified_utc","source_note")}}
    for call in selected["calls"]:
        note = notes.get("by_call", {}).get(call["id"])
        if not note or markets.instant(notes["verified_utc"]) >= markets.instant(call["kickoff"]):
            continue
        role_check = note["display"] + " Check both designations with the official pregame inactives and reassess the passing-down role."
        call["supplemental_conditions"] = {"display":role_check,"verified_utc":notes["verified_utc"],"players":note["players"]}
        call["evidence"].append({"kind":"supplemental_personnel_review","label":"known","statement":role_check,
                                "source_url":note["players"][0]["source_url"],"retrieved_utc":note["players"][0]["retrieved_utc"]})
        appearance = call.get("recent_appearances")
        if appearance is not None:
            src = note["appearance_source"]
            appearance.update(retrieved_utc=src["retrieved_utc"], raw_sha256=src["sha256"],
                              saved_representation=src["saved_representation"], saved_file_sha256=src["saved_file_sha256"])
            archived = HERE / "inputs/warren-gamelog.20261115T074412Z"
            if (archived / "MANIFEST.json").is_file() and (archived / "page.html").is_file():
                receipt = json.loads((archived / "MANIFEST.json").read_bytes())
                if sha256((archived / "page.html").read_bytes()).hexdigest() == receipt["sha256"]:
                    appearance["corroborating_receipt"] = {k:receipt[k] for k in ("source_url","retrieved_utc","sha256")}
                    appearance["corroborating_receipt"]["saved_file"] = "inputs/" + archived.name + "/page.html"


def attach(doc):
    """Attach the saved producer's dated source record when one is available."""
    selected = doc["selections"]
    by_id = {c["id"]: c for c in doc["slate"]["candidates"]}
    for call in selected["calls"]:
        candidate = by_id[call["id"]]
        if candidate.get("review_policy"):
            selected["review_policy"] = candidate["review_policy"]
            selected["rule_freeze_scope"] = "Historical model and contract scoring; current review eligibility is separately dated."
            call["same_game_contract_ids"] = candidate["same_game_contract_ids"]
            if call["same_game_contract_ids"]:
                call["shared_game_risk"] = "These selections share a game. Injuries, pace and the score can affect both; their outcomes may be correlated."
    games = {}
    for g in doc["slate"]["games"]:
        away, home = g["name"].split(" at ", 1)
        games[g["event_id"]] = {"away_name": away, "home_name": home, "kickoff_utc": g["kickoff_utc"]}
    _review_notes(doc)
    rows, receipt = read_report(selected["slate_date"], selected["capture_sha256"], games, doc["run_utc"])
    return _attach_rows(doc, rows, receipt)


def report_blocks(doc, blocks):
    shared_events = set()
    for call in doc["selections"]["calls"]:
        if call.get("shared_game_risk") and call["event_id"] not in shared_events:
            blocks.append(("p", "**Shared-game risk · %s.** %s" % (call["game"], call["shared_game_risk"])))
            shared_events.add(call["event_id"])
        check = call.get("supplemental_conditions")
        if check:
            blocks.append(("p", "**Pregame personnel check · %s.** %s" % (call["label"],check["display"])))
        rows = [r for r in call.get("replacement_context", []) if r.get("display")]
        if not rows:
            if call.get("replacement_review_status") and markets.MARKETS[call["market"]][0] != "prop":
                blocks.append(("p", "**Replacement review · %s.** %s" % (call["label"], call["replacement_review_status"])))
            continue
        blocks.append(("h2", "Replacement assessment · " + call["label"]))
        for row in rows:
            blocks.append(("p", row["display"]))
            links = ["[%s](%s)" % (s["label"], s["url"]) for s in row.get("sources", []) if s.get("url")]
            if links:
                blocks.append(("p", " · ".join(links)))
            if row.get("effective_as_of_utc"):
                blocks.append(("p", "Evidence as of %s. %s" % (row["effective_as_of_utc"], row["timing_note"])))
    for w, source in doc["selections"].get("window_notes_sources", {}).items():
        blocks.append(("p", "**%s pass evidence.** %s [Play-by-play source](%s). %s" %
                       (w.capitalize(), source["display"], source["source_url"], source["source_note"])))
    return blocks
