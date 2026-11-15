"""Read-only weekly football context for the exact contracts in weekly_api.screen()."""
import hashlib
import importlib.util
import json
import re
from datetime import date
from functools import lru_cache
from math import isfinite, sqrt
from pathlib import Path
from zoneinfo import ZoneInfo

import picker
import selection_decisions
import selection_markets
import selection_release
from sunday_availability import _name_key as player_key

DEFAULT_GAMES = Path(picker.LANE) / "data/raw/games.csv"
WINDOWS = ("early", "late", "night")
MARKETS = {"h2h": "moneyline", "spreads": "spread", "totals": "total"}
METHOD = ("At most two distinct contracts per window, including two from one game. Require a fresh-at-capture in-band offer, "
          "at least two books pricing both sides at the exact line, and market and football estimates "
          "above 50%. Rank by market probability, then football probability, then exact contract ID. "
          "The market median includes the offering book where it quoted both sides. "
          "All prices are observations; final health, personal terms and fill are unknown.")


@lru_cache(maxsize=4)
def _load_history(path, file_stamp, manifest_stamp, cutoff):
    digest = picker.sha256_file(path)
    manifest = path.with_name("MANIFEST.json")
    entries = json.loads(manifest.read_text())["files"] if manifest_stamp else []
    receipt = next((item for item in entries if Path(item["path"]).name == path.name), None)
    if receipt is None or receipt.get("sha256") != digest:
        raise ValueError("The game archive has no matching source receipt.")
    rows = picker.load_games(path)
    predictions, state = picker.walk(rows, picker.PARAMS, cutoff)
    tune = [p for p in predictions if picker.PARAMS["tune_seasons"][0] <= p["game"]["season"] <= picker.PARAMS["tune_seasons"][1]]
    dispersion = {}
    for key, field, sign in (("sd_margin", "margin", -1), ("sd_total", "total", 1)):
        if tune:
            errors = [(p["game"]["home_score"] + sign * p["game"]["away_score"] - p[field]) ** 2 for p in tune]
            dispersion[key] = sqrt(sum(errors) / len(errors))
    source = {"source": "nflverse schedule and final scores", "url": receipt["url"], "sha256": digest,
              "retrieved_utc": receipt["retrieved_at_utc"], "data_through": max((p["game"]["gameday"] for p in predictions), default=None),
              "exclusive_cutoff_date": cutoff, "training_games_for_dispersion": len(tune)}
    return rows, state, dispersion, source


def _team(rows, team, season, cutoff, day):
    form = picker.team_form(rows, team, season, cutoff)
    pending = [{"date": g["gameday"], "week": g["week"], "game_id": g["game_id"],
                "opponent": g["away"] if g["home"] == team else g["home"]}
               for g in rows if team in (g["away"], g["home"]) and g["season"] == season and g["gameday"] < day
               and (g["gameday"] >= cutoff or None in (g["home_score"], g["away_score"]))]
    return {"team": team, "form": form, "intervening_ungraded_games": pending}


def _comparison(c, game, model, spread_error):
    market = MARKETS.get(c.get("market"))
    if not market or c.get("period") != "full_game" or not c.get("reviewable") or c.get("event_id") != game["event_id"]:
        return None
    if c["id"] != selection_markets.key_for(game["event_id"], c["market"], c["subject"], c["side"], c["point"]):
        return None
    offer = c.get("best_in_band") or c.get("best") or {}
    price = offer.get("price")
    quoted = any(q.get("fresh", True) and q["book"] == offer.get("book") and q["price"] == price for q in c["quotes"])
    if not quoted or not offer.get("in_band") or not isinstance(price, int) or not 100 <= abs(price) <= 200:
        return None
    consensus = c.get("no_vig") or {}
    market_prob = consensus.get("median")
    if consensus.get("books", 0) < 2 or not isinstance(market_prob, (float, int)) or not 0.5 < market_prob <= 1:
        return None
    side = c["side"]
    if market == "total" and side in ("Under", "Over"):
        side = side.lower()
    elif market != "total" and side in (game["away"]["name"], game["home"]["name"]):
        side = "home" if side == game["home"]["name"] else "away"
    else:
        return None
    point = c["point"]
    if market != "moneyline" and (not isinstance(point, (float, int)) or not isfinite(point)
                                   or not spread_error.get("sd_total" if market == "total" else "sd_margin")):
        return None
    bet = {"period": "full_game", "market": market, "line": point, "side": side}
    def probability(line):
        return selection_decisions.model_probability(dict(bet, line=line), {"model": model}, spread_error)
    model_prob = probability(point)
    if market != "moneyline" and float(point).is_integer():
        # Integer scores can land on the line. Compare the two decided tails with the two-way book probability.
        lower, upper = sorted((probability(point - 0.5), probability(point + 0.5)))
        model_prob = lower / (lower + 1 - upper)
    if model_prob <= 0.5:
        return None
    decimal_price = selection_markets.decimal_odds(price)
    be = 1 / decimal_price
    return {"id": c["id"], "event_id": game["event_id"], "window": game["window"], "label": c["label"],
            "game": "%s at %s" % (game["away"]["abbr"], game["home"]["abbr"]), "book": offer["book"], "price": price,
            "provider_updated_utc": offer.get("updated_utc") or offer.get("provider_updated_utc"),
            "market_probability": market_prob, "market_books": consensus["books"], "break_even": round(be, 6),
            "model_probability": round(model_prob, 6), "model_minus_market_pp": round(100 * (model_prob - market_prob), 2),
            "model_minus_break_even_pp": round(100 * (model_prob - be), 2),
            "market_estimated_return_per_unit": round(market_prob * decimal_price - 1, 6),
            "model_estimated_return_per_unit": round(model_prob * decimal_price - 1, 6),
            "return_basis": "Estimated per unit at this quote, conditional on a decided outcome; personal fill unknown.",
            "clv": None, "clv_status": "No verified closing observation in this screen.", "status": "provisional"}



def _read_availability(screen, inputs_root):
    """Read only the source worker's saved weekly records, never the capture operation."""
    import sunday_availability
    day = screen["date"]
    if inputs_root is None:
        folder = Path(screen["edition"].get("path") or "").parent
        folder = folder.parent if folder.name == "captures" else folder
        inputs_root = folder.parent if folder.name == day else Path(__file__).resolve().parent / "weekly_inputs"
    p = Path(inputs_root) / day / "schedule.json"
    try:
        raw = p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != screen["inputs"]["schedule"]["sha256"]:
            raise ValueError("Saved schedule differs from the screened edition.")
        schedule = json.loads(raw)
        as_of = selection_markets.instant(screen["generated_utc"])
        out = sunday_availability.read(day, schedule, inputs_root, as_of=as_of)
        if importlib.util.find_spec("sunday_club_news") is not None:
            from sunday_club_news import merged
            out = merged(day, schedule, inputs_root, out, as_of=as_of)
        observed = out.get("captured_utc")
        if observed and selection_markets.instant(observed) > as_of:
            raise ValueError("Availability was retrieved after the screen was generated.")
        return out
    except (OSError, KeyError, ValueError, TypeError) as exc:
        return {"status":"unavailable", "captured_utc":None, "sources":{}, "by_event":{}, "limitations":[str(exc)]}


def _supported_replacements(role):
    named = {player_key(r["player"]) for r in role["next_men"]}
    supported = set()
    for candidate in role.get("opportunity", []):
        player = player_key(candidate["player"])
        if player not in named:
            continue
        for evidence in candidate.get("role") or []:
            source = evidence.get("source") or {}
            url = source.get("url")
            if not url or not evidence.get("text"):
                continue
            # Depth order alone does not corroborate a workload.
            source_type = player_key(" ".join((str(evidence.get("kind", "")), str(source.get("label", "")), url)))
            if "depthchart" not in source_type and evidence.get("kind") not in ("depth", "depth_only"):
                supported.add(player)
                break
    return supported


def _publication_instant(value):
    # Python 3.9 fromisoformat accepts 3 or 6 fractional digits. Club sources use other widths.
    value = re.sub(r"([T ]\d{2}:\d{2}:\d{2})\.(\d+)", lambda m: m[1] + "." + m[2][:6].ljust(6, "0"), value)
    return selection_markets.instant(value)


def _prior_publications(role):
    """Use publication times attached to this specific player's status or role evidence."""
    dates = {}
    for absence in role.get("absent", []):
        if absence.get("source_published_utc"):
            dates[player_key(absence["player"])] = _publication_instant(absence["source_published_utc"])
    for candidate in role.get("opportunity", []):
        key = player_key(candidate["player"])
        for claim in candidate.get("role") or []:
            published = (claim.get("source") or {}).get("published_utc")
            if published:
                when = _publication_instant(published)
                dates[key] = max(dates.get(key, when), when)
    return dates


def _publication_order(record, prior, known_by):
    timestamp = record.get("player_published_utc")
    day = date.fromisoformat(record["published"]) if record.get("published") else None
    if timestamp:
        when = _publication_instant(timestamp)
        if prior is not None:
            return (when > prior) - (when < prior)
        return 0 if when <= known_by else None
    if day is None:
        return None
    # The form records a date on the desk's Central calendar, not a publication time.
    if prior is not None:
        prior_day = prior.astimezone(selection_markets.CENTRAL).date()
        return (day > prior_day) - (day < prior_day)
    # The role already contained the conflicting status by this cutoff. A prior-day
    # article entered later cannot establish a subsequent change when publication is unknown.
    return 0 if day < known_by.astimezone(selection_markets.CENTRAL).date() else None


def _current_role(role, team, latest, source_cutoff):
    """Apply later observed personnel news to a new projection; retain the original assessment for replay."""
    starter = (role.get("capability", {}).get("starter") or {}).get("player")
    if not starter:
        return role, set(), set()
    starter_key = player_key(starter)
    supported = _supported_replacements(role)
    prior_status = {player_key(n["player"]): str(n.get("availability_status") or "").casefold()
                    for n in role["next_men"]}
    prior_status.update({player_key(a["player"]): str(a.get("status") or "").casefold()
                         for a in role.get("absent", []) if player_key(a["player"]) == starter_key})
    prior_status.setdefault(starter_key, "")
    cutoff = role.get("latest_source_utc") or source_cutoff or role.get("effective_as_of_utc")
    publications = _prior_publications(role)
    changed, older, unordered = {}, set(), set()
    for name, previous in prior_status.items():
        rec = latest.get((team, name))
        if not rec or not cutoff or selection_markets.instant(rec["observed_utc"]) <= selection_markets.instant(cutoff):
            continue
        status = rec["status"]
        if status.casefold() == previous or status not in ("Out", "Doubtful", "Questionable", "Designation removed"):
            continue
        if status == "Designation removed" and name != starter_key and previous not in ("out", "doubtful", "questionable"):
            continue
        order = _publication_order(rec, publications.get(name), selection_markets.instant(cutoff))
        if order == -1:
            older.add(name)
            continue
        if order == 0:
            unordered.add(name)
        changed[name] = rec
    if not changed:
        credited = {starter_key} if supported and role["screen_status"] == "screened" else set()
        return role, credited, older

    latest_note = max(changed.values(), key=lambda rec: selection_markets.instant(rec["observed_utc"]))
    descriptions = []
    for name, rec in changed.items():
        if name in unordered:
            dated = rec.get("published") or rec.get("player_published_utc")
            descriptions.append(f'{rec["player"]} has conflicting reports. The earlier review listed '
                                f'{prior_status[name] or "unknown status"} and the report dated {dated} lists '
                                f'{rec["status"].lower()}. Their publication order is unknown')
        else:
            descriptions.append(f'{rec["player"]} ({rec["status"].lower()}, observed {rec["observed_utc"]})')
    removed = {name for name, rec in changed.items() if rec["status"] in ("Out", "Doubtful")}
    remaining = [n["player"] for n in role["next_men"] if player_key(n["player"]) in supported - removed]
    starter_update = changed.get(starter_key, {}).get("status")
    if starter_update == "Designation removed" and starter_key not in unordered:
        state = "starter_cleared"
        disposition = f'{starter}’s designation was removed. The earlier workload projection depended on his absence. Confirm his game-day role.'
        remaining = []
    elif not remaining:
        state = "unknown_next_man"
        disposition = "No remaining replacement has a corroborated workload. Hold this matchup until a new role review."
    else:
        state = "screened"
        qualifier = (f'{starter}’s availability is uncertain. '
                     if starter_key in unordered or starter_update in ("Doubtful", "Questionable") else "")
        disposition = (qualifier + "The prior review also named " + ", ".join(remaining)
                       + ". The workload split needs a new review.")
    # Never carry an old lead assignment, prop outlook or workload estimate forward as current.
    current = {k:role[k] for k in ("team", "date", "event_id", "capture_sha256") if k in role}
    current.update(
        prior_review=role, status="unknown", screen_status=state,
        flag="qualify" if state == "screened" else None,
        effective_as_of_utc=max(filter(None, (role.get("effective_as_of_utc"), latest_note["observed_utc"])),
                                key=selection_markets.instant), latest_source_utc=latest_note["observed_utc"],
        display="Pregame update: " + ", ".join(descriptions) + ". " + disposition,
        next_men=[{"player":name,
                   "availability_status":("conflicting reports" if player_key(name) in unordered else
                                          changed.get(player_key(name), {}).get("status") or prior_status[player_key(name)] or "unconfirmed"),
                   "workload":"unconfirmed"} for name in remaining],
        sources=[{"label":r["player"] + " status", "url":r["source_url"], "observed_utc":r["observed_utc"],
                  "published":r.get("published"), "player_published_utc":r.get("player_published_utc")}
                 for r in changed.values()])
    # A remaining corroborated contributor supports a conditional review of this specific
    # rotation. Independent absences elsewhere on the team still need their own review.
    credited = {starter_key} | (supported & removed) if state == "screened" else set()
    return current, credited, older


def _availability_for(game, data, roles, as_of, source_cutoff=None):
    ev = data.get("by_event", {}).get(str(game.get("espn_event_id"))) or {}
    status = ev.get("status", data["status"])
    report = {"status":status, "captured_utc":data.get("captured_utc"), "records":[], "unresolved_starters":[], "uncertain_roles":[],
              "team_coverage":ev.get("team_coverage", {}), "limitations":data.get("limitations", []),
              "replacement_context":roles}
    if status not in ("reported", "partial"):
        return report
    away, home = (picker.ABBR.get(game[s]["name"]) for s in ("away", "home"))
    kickoff = selection_markets.instant(game["kickoff_utc"])
    if (ev.get("teams") != [away, home] or selection_markets.instant(ev["kickoff_utc"]) != kickoff):
        report.update(status="event_mismatch", team_coverage={})
        return report
    latest = {}
    reviewed_at = selection_markets.instant(as_of)
    for rec in ev.get("records", []):
        observed = selection_markets.instant(rec["observed_utc"])
        if observed > reviewed_at or observed >= kickoff or rec["team"] not in (away, home):
            continue
        key = rec["team"], player_key(rec["player"])
        if key not in latest or observed > selection_markets.instant(latest[key]["observed_utc"]):
            latest[key] = rec
    current_roles, reviewed, older_reports = [], set(), set()
    for role in roles:
        team = picker.ABBR.get(role["team"])
        if team not in (away, home) or role.get("event_id") != game.get("event_id"):
            continue
        current, credited, older = _current_role(role, team, latest, source_cutoff)
        current_roles.append(current)
        older_reports.update((team, name) for name in older)
        reviewed.update((team, name) for name in credited)
    report["replacement_context"] = current_roles
    for key, rec in latest.items():
        if key in older_reports:
            report.setdefault("superseded_records", []).append(dict(rec, reason="Player-specific role evidence was published later."))
            continue
        if rec["status"] not in ("Out", "Doubtful"):
            continue
        report["records"].append(rec)
        if key not in reviewed:
            material = (rec.get("starter_status") == "listed_first" or
                        (rec.get("origin") == "operator_bulletin" and rec.get("reported_material") is True))
            destination = "unresolved_starters" if material else "uncertain_roles"
            report[destination].append({"player":rec["player"], "team":rec["team"], "position":rec["position"],
                    "status":rec["status"], "source_url":rec["source_url"], "observed_utc":rec["observed_utc"],
                    "starter_status":rec.get("starter_status"),"reported_material":rec.get("reported_material",False),
                    "depth_chart_utc":rec.get("depth_chart_utc"), "depth_source_url":rec.get("depth_source_url")})
    return report


def enrich(screen, games_path=None, replacement_path=None, inputs_root=None):
    """Attach no state to the input and never issue formal calls. Probabilities use 0..1."""
    day = date.fromisoformat(screen["date"])
    edition = screen["edition"]
    captured = selection_markets.instant(edition["captured_utc"])
    cutoff = min(day, captured.astimezone(ZoneInfo("America/Chicago")).date()).isoformat()
    result = {"status": "provisional", "date": day.isoformat(), "edition_sha256": edition["sha256"],
              "captured_utc": edition["captured_utc"], "history": {}, "by_event": {},
              "by_window": {w: [] for w in WINDOWS}, "shortlist": [], "ranked_potentials": [], "warnings": [], "method": METHOD}
    path = Path(games_path or DEFAULT_GAMES)
    manifest = path.with_name("MANIFEST.json")
    try:
        rows, saved_state, errors, source = _load_history(path, path.stat().st_mtime_ns,
                manifest.stat().st_mtime_ns if manifest.is_file() else None, cutoff)
        if selection_markets.instant(source["retrieved_utc"]) > captured:
            raise ValueError("Game archive was acquired after this price edition.")
    except (OSError, KeyError, ValueError) as exc:
        result["warnings"].append("Football screen held. " + str(exc))
        return result
    result["history"] = dict(source)
    # Copy mutable rating dictionaries; processing a new season must not contaminate a cached historical state.
    state = {k: dict(v) if isinstance(v, dict) else v for k, v in saved_state.items()}
    season = day.year - (day.month <= 2)
    picker._roll_season(state, season, picker.PARAMS)
    season_games = [g for g in rows if g["season"] == season and g["game_type"] == "REG"]
    by_week = {}
    for g in season_games:
        by_week.setdefault(g["week"], []).append(g)
    complete = [wk for wk, gs in by_week.items() if all(g["gameday"] < cutoff and None not in
               (g["home_score"], g["away_score"]) for g in gs)]
    result["history"]["latest_complete_regular_week"] = max(complete, default=None)
    result["warnings"].append("Team scores through %s. Last fully scored regular-season week: %s. "
            "Updated starters, injuries and roles for %s are unverified." %
            (source["data_through"] or "unknown", max(complete, default="unknown"), day.isoformat()))
    result["warnings"].append("Weekly rankings use full-game team markets only. Verify the actual price before review. "
                              "The football probabilities are estimates; no validated betting edge or fill is established.")
    event_index = {g["event_id"]: {"away_name": g["away"]["name"], "home_name": g["home"]["name"],
                    "kickoff_utc": g["kickoff_utc"]} for w in screen["windows"] for g in w["games"]}
    role_rows, role_receipt = selection_release.read_report(day.isoformat(), edition["sha256"], event_index,
            screen["generated_utc"], path=replacement_path)
    result["replacement_evidence"] = role_receipt
    availability = _read_availability(screen, inputs_root)
    result["availability"] = {k:availability.get(k) for k in ("status", "captured_utc", "expires_utc", "sources", "limitations")}
    if availability["status"] == "no_week_data":
        result["warnings"].append("The saved weekly injury feed returned no designations for this week. Final availability remains unknown.")
    pool = []
    for window in screen["windows"]:
        for game in window["games"]:
            home, away = (picker.ABBR.get(game[k]["name"]) for k in ("home", "away"))
            neutral = game.get("neutral_site")
            context = {"home": _team(season_games, home, season, cutoff, day.isoformat()),
                       "away": _team(season_games, away, season, cutoff, day.isoformat()),
                       "neutral_site": neutral, "venue": game.get("venue"), "model": None, "caveats": [],
                       "replacement_context": [], "health": "Unknown for this matchup; check updated availability."}
            result["by_event"][game["event_id"]] = context
            if not all([context["home"]["form"]["n"], context["away"]["form"]["n"], isinstance(neutral, bool),
                        game.get("espn_event_id")]):
                context["caveats"].append("Football shortlist held. Current-season form, schedule or venue status is missing.")
                continue
            if any(context[s]["intervening_ungraded_games"] for s in ("away", "home")):
                context["caveats"].append("Intervening games are missing from the saved results. Reassess after their finals.")
            roles = role_rows.get(game["event_id"], [])
            availability_event = _availability_for(game, availability, roles, screen["generated_utc"], role_receipt.get("as_of_utc"))
            roles = availability_event.pop("replacement_context")
            context["replacement_context"] = roles
            coverage = dict(role_receipt.get("team_coverage", {}).get(game["event_id"], {}))
            coverage.update({r["team"]:r["screen_status"] for r in roles})
            context["replacement_team_coverage"] = coverage
            context["caveats"].extend(r["display"] for r in roles)
            if roles:
                context["health"] = "Dated replacement evidence is supplemental; final active lineups remain unverified."
            else:
                context["caveats"].append("No confirmed starting lineups or date-matched replacement evidence in this screen.")
            context["availability"] = availability_event
            unresolved = availability_event["unresolved_starters"]
            for absence in unresolved:
                basis = "listed first on the depth chart" if absence["starter_status"] == "listed_first" else "identified as material in the operator’s sourced club note"
                context["caveats"].append("%s %s (%s) is %s and reported %s. No dated role review matches this player and team." %
                        (absence["team"], absence["player"], absence["position"], basis, absence["status"].lower()))
            uncertain_roles = availability_event["uncertain_roles"]
            for absence in uncertain_roles:
                basis = "operator identified this absence as material" if absence["reported_material"] else "depth rank and replacement impact are unverified"
                context["caveats"].append("%s %s (%s) is %s. %s." % (absence["team"],absence["player"],
                    absence["position"],absence["status"].lower(),basis.capitalize()))
            hold = bool(unresolved) or any(r["screen_status"] == "unknown_next_man" for r in roles)
            context["review_status"] = "provisional"
            if uncertain_roles or any(r.get("flag") == "qualify" for r in roles):
                context["review_status"] = "conditional_role_review"
                context["caveats"].append("The personnel review is conditional. Confirm the cited roles before issuing a call.")
            if hold:
                context["review_status"] = "hold_for_replacement_review"
                context["caveats"].append("Material absence identified; hold the provisional shortlist until the replacement role is reviewed.")
            pred = picker.predict(state, home, away, "Neutral" if neutral else "Home", picker.PARAMS)
            model = {"p_home_win": pred["p_home"], "margin_home": pred["margin"], "total": pred["total"]}
            context["model"] = {k: round(v, 6) for k, v in model.items()}
            context["home_field_applied"] = not neutral
            if game["state"] != "scheduled" or hold:
                continue
            for contract in game["contracts"]:
                item = _comparison(contract, game, model, errors)
                if item:
                    item["review_status"] = context["review_status"]
                    item["caveats"] = list(context["caveats"])
                    pool.append(item)
    pool.sort(key=lambda r: (-r["market_probability"], -r["model_probability"], r["id"]))
    seen = set()
    for item in pool:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        if len(result["ranked_potentials"]) < 5:
            result["ranked_potentials"].append(dict(item, rank=len(result["ranked_potentials"]) + 1, status="watchlist"))
        window = result["by_window"][item["window"]]
        if len(window) < 2:
            window.append(item["id"])
            item.update(rank=len(result["shortlist"]) + 1, window_rank=len(window))
            result["shortlist"].append(item)
    for group in (result["shortlist"], result["ranked_potentials"]):
        for item in group:
            related = [other["id"] for other in group if other["event_id"] == item["event_id"] and other["id"] != item["id"]]
            item["shared_game_contract_ids"] = related
            if related:
                item["caveats"] = item["caveats"] + ["Shared-game exposure: pace, scoring and injuries may affect both outcomes."]
    return result
