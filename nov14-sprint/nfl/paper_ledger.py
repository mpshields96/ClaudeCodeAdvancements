#!/usr/bin/env python3
"""Paper-only NFL pick ledger. No real bets, no accounts, no money.

Run: python3 -I nov14-sprint/nfl/paper_ledger.py <command>   (any cwd)

Commands: slate, generate, add, close, settle, settle-manual, status.

Design rules (see the task spec):
  * Standard library only, Python 3.9.
  * Append-only JSON Lines: ledger.jsonl, rejections.jsonl, settlements.jsonl,
    observations.jsonl (closing-line observations tied to a pick_id).
  * One contract = game, rule version, market, selection (player + stat for a
    prop), side, line (%g). Stored as contract_key; duplicates are found by
    recomputing it from each existing row, so old rows keep working.
  * Prices in the downloaded file are archived paper observations. The 12-hour
    gate is a check on the age of the FILE, not proof of a live quote.
  * Rule logic lives in rules.py (decide, grade, american_profit). Not
    re-implemented here.
  * ONE gate, validate_entry(), is used by every command that writes a pick.
  * The CSV is untrusted data: csv.DictReader only, SHA-256 checked against
    data/raw/MANIFEST.json before use, nothing from it is ever evaluated.
  * Foreknowledge boundary: in real mode the decision time is always the
    system clock. --now is only allowed for fixtures or a custom ledger dir.
"""
import argparse
import csv
import fcntl
import hashlib
import io
import json
import math
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

NFL_DIR = os.path.dirname(os.path.abspath(__file__))
# `python3 -I` does not put the script directory on sys.path.
sys.dont_write_bytecode = True
sys.path.insert(0, NFL_DIR)
import rules  # noqa: E402

BANNER = "PAPER ONLY - no real bets, no accounts, no money"

# --- constants -------------------------------------------------------------
# Max paper stake per pick, in units.
STAKE_CAP_UNITS = 1.0
# Stake used for every rule-generated take.
DEFAULT_STAKE_UNITS = 1.0
# Staleness gate (hours). For generated rows it is the age of the downloaded
# FILE at decision time; it never shows a quote is fresh, offered or
# available. For manual picks it is the age of the user-reported quote time.
MAX_LINE_AGE_HOURS = 12.0
# Pre-stated stop rule: settled paper P&L 10 units or more below its running
# peak, or cumulative settled P&L <= -10 units: no new TAKE is accepted.
STOP_DRAWDOWN_UNITS = 10.0
# The user's own stated American-odds band for hand picks. Out-of-band manual
# picks are still accepted but recorded with price_in_band false.
MANUAL_PRICE_BAND = (-170, 150)

# --- paths -----------------------------------------------------------------
GAMES_REL = "data/raw/games.csv"
GAMES_PATH = os.path.join(NFL_DIR, "data", "raw", "games.csv")
MANIFEST_PATH = os.path.join(NFL_DIR, "data", "raw", "MANIFEST.json")
DEFAULT_FROZEN = os.path.join(NFL_DIR, "frozen_rules.json")
REAL_LEDGER_DIR = os.path.join(NFL_DIR, "ledger")
FIXTURE_LEDGER_DIR = os.path.join(REAL_LEDGER_DIR, "fixture")

LEDGER_NAME = "ledger.jsonl"
REJECTIONS_NAME = "rejections.jsonl"
SETTLEMENTS_NAME = "settlements.jsonl"
OBSERVATIONS_NAME = "observations.jsonl"

# Plain one-line notice printed by slate, generate and status. Every price in
# the downloaded file is an archived paper observation, never a live quote.
PRICE_NOTICE = ("Prices are archived paper observations. File retrieved %s. "
                "Sportsbook quote time unknown. Not a live or executable "
                "price.")

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
MANUAL_RULE_RE = re.compile(r"MANUAL-[A-Za-z0-9._-]+")

SIDES_BY_MARKET = {
    "spread": ("home", "away"),
    "moneyline": ("home", "away"),
    "total": ("over", "under"),
    "prop": ("over", "under", "home", "away"),
}
# (market, side) -> game-dict key (same name as the CSV column)
PRICE_FIELDS = {
    ("spread", "home"): "home_spread_odds",
    ("spread", "away"): "away_spread_odds",
    ("total", "under"): "under_odds",
    ("total", "over"): "over_odds",
    ("moneyline", "home"): "home_moneyline",
    ("moneyline", "away"): "away_moneyline",
}

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_STOP_RULE = 3


class Refusal(Exception):
    """A whole-command refusal (exit 2)."""

    def __init__(self, code, detail):
        Exception.__init__(self, "%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def out(msg=""):
    print(msg, flush=True)


def err(msg):
    print(msg, file=sys.stderr, flush=True)


# --- small parsing helpers -------------------------------------------------
def clean(text):
    """Strip control characters from untrusted text before printing it."""
    return "".join(ch if (ch.isprintable() and ch not in "\r\n\t") else "?"
                   for ch in str(text))


def parse_ts(text):
    """Strict 'YYYY-MM-DDTHH:MM:SSZ' -> aware UTC datetime, else None."""
    if not isinstance(text, str) or not TS_RE.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, TS_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fmt_ts(dt):
    return dt.astimezone(timezone.utc).strftime(TS_FORMAT)


def parse_float(value):
    """None for empty/None; ValueError for anything not a finite number."""
    if value is None or isinstance(value, bool):
        if value is None:
            return None
        raise ValueError("boolean is not a number")
    if isinstance(value, (int, float)):
        x = float(value)
    else:
        s = str(value).strip()
        if s == "":
            return None
        x = float(s)
    if not math.isfinite(x):
        raise ValueError("not finite")
    return x


def csv_float(value):
    """CSV cell -> finite float, or None when empty/NA/garbage."""
    try:
        return parse_float(value)
    except ValueError:
        return None


def csv_int(value):
    x = csv_float(value)
    if x is None or not x.is_integer():
        return None
    return int(x)


def valid_american(x):
    return x is not None and math.isfinite(x) and abs(x) >= 100


def csv_price(value):
    x = csv_float(value)
    return norm_num(x) if valid_american(x) else None


def norm_num(x):
    """Integral floats become ints (price -110 not -110.0)."""
    if x is None:
        return None
    x = float(x)
    return int(x) if x.is_integer() and abs(x) < 1e12 else x


def in_band(price):
    lo, hi = MANUAL_PRICE_BAND
    return lo <= price <= hi


_TZ_CACHE = []


def eastern_tz():
    if not _TZ_CACHE:
        try:
            from zoneinfo import ZoneInfo
            _TZ_CACHE.append(ZoneInfo("America/New_York"))
        except Exception as exc:  # zoneinfo/tzdata missing
            raise Refusal("TZ_UNAVAILABLE",
                          "cannot load America/New_York: %s" % exc)
    return _TZ_CACHE[0]


def kickoff_from(gameday, gametime):
    """Eastern local gameday+gametime -> UTC datetime, or None if unknown."""
    if not gameday or not gametime:
        return None
    try:
        local = datetime.strptime("%s %s" % (gameday, gametime),
                                  "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return local.replace(tzinfo=eastern_tz()).astimezone(timezone.utc)


# --- contract identity -------------------------------------------------------
def norm_selection(market, selection):
    """'' for team markets; for props the lower-cased, space-collapsed text."""
    if market != "prop":
        return ""
    return " ".join(str(selection or "").lower().replace("|", " ").split())


def line_text(line):
    """A line formatted with %g, or '' when there is none."""
    if line is None or isinstance(line, bool) or line == "":
        return ""
    try:
        return "%g" % float(line)
    except (TypeError, ValueError):
        return str(line)


def contract_identity(entry):
    """One contract = game, rule version, market, selection, side, line.

    Always computed from a row's own fields and never from a stored pick_id,
    so rows written by older versions keep blocking an exact retry.
    """
    return "|".join([
        str(entry.get("game_id")), str(entry.get("rule_version")),
        str(entry.get("market")),
        norm_selection(entry.get("market"), entry.get("selection")),
        str(entry.get("side") or ""), line_text(entry.get("line"))])


def pick_id_for(identity):
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def finalize_entry(entry):
    """Stamp contract_key and the line-aware pick_id on a NEW row."""
    entry["contract_key"] = contract_identity(entry)
    entry["pick_id"] = pick_id_for(entry["contract_key"])
    return entry


# --- input loading (games.csv + manifest) ----------------------------------
def parse_game(row):
    """One CSV row -> game dict with floats/ints (empty -> None)."""
    def txt(key):
        return clean((row.get(key) or "").strip())

    gameday = txt("gameday")
    gametime = txt("gametime")
    return {
        "game_id": txt("game_id"),
        "season": csv_int(row.get("season")),
        "week": csv_int(row.get("week")),
        "gameday": gameday,
        "gametime": gametime,
        "kickoff": kickoff_from(gameday, gametime),
        "away_team": txt("away_team"),
        "home_team": txt("home_team"),
        "away_score": csv_float(row.get("away_score")),
        "home_score": csv_float(row.get("home_score")),
        "away_rest": csv_int(row.get("away_rest")),
        "home_rest": csv_int(row.get("home_rest")),
        "away_moneyline": csv_price(row.get("away_moneyline")),
        "home_moneyline": csv_price(row.get("home_moneyline")),
        "spread_line": csv_float(row.get("spread_line")),
        "away_spread_odds": csv_price(row.get("away_spread_odds")),
        "home_spread_odds": csv_price(row.get("home_spread_odds")),
        "total_line": csv_float(row.get("total_line")),
        "under_odds": csv_price(row.get("under_odds")),
        "over_odds": csv_price(row.get("over_odds")),
    }


def parse_games_text(text, required_cols):
    reader = csv.DictReader(io.StringIO(text))
    cols = reader.fieldnames or []
    missing = [c for c in required_cols if c not in cols]
    if missing:
        raise Refusal("INPUT_INVALID", "CSV is missing columns: %s"
                      % ", ".join(missing))
    games = []
    seen = set()
    for row in reader:
        g = parse_game(row)
        if not g["game_id"]:
            continue
        if g["game_id"] in seen:
            raise Refusal("INPUT_INVALID",
                          "duplicate game_id in CSV: %s" % g["game_id"])
        seen.add(g["game_id"])
        games.append(g)
    return games


def read_text_file(path, what):
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise Refusal("INPUT_MISSING", "cannot read %s (%s): %s"
                      % (what, path, exc))
    return data


class Inputs(object):
    """games.csv after hash verification, plus line-source provenance."""

    def __init__(self, games, url, retrieved_str, sha256):
        self.games = games
        self.by_id = dict((g["game_id"], g) for g in games)
        self.url = url
        self.retrieved_str = retrieved_str
        self.retrieved = parse_ts(retrieved_str)
        self.sha256 = sha256


def load_manifest_entry():
    raw = read_text_file(MANIFEST_PATH, "MANIFEST.json")
    try:
        manifest = json.loads(raw.decode("utf-8"))
        for item in manifest["files"]:
            if item["path"] == GAMES_REL:
                break
        else:
            raise KeyError(GAMES_REL)
        url = str(item["url"])
        retrieved = str(item["retrieved_at_utc"])
        nbytes = int(item["bytes"])
        sha = str(item["sha256"]).lower()
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise Refusal("INPUT_INVALID", "MANIFEST.json unusable: %s" % exc)
    if parse_ts(retrieved) is None:
        raise Refusal("INPUT_INVALID",
                      "manifest retrieved_at_utc is not strict UTC ISO: %r"
                      % retrieved)
    return url, retrieved, nbytes, sha


_INPUT_CACHE = []


def load_inputs():
    """Hash-check games.csv against the manifest, then parse it."""
    if _INPUT_CACHE:
        return _INPUT_CACHE[0]
    url, retrieved, nbytes, sha = load_manifest_entry()
    data = read_text_file(GAMES_PATH, GAMES_REL)
    actual_sha = hashlib.sha256(data).hexdigest()
    if len(data) != nbytes or actual_sha != sha:
        raise Refusal("INPUT_HASH_MISMATCH",
                      "%s has %d bytes sha256 %s; manifest says %d bytes "
                      "sha256 %s" % (GAMES_REL, len(data), actual_sha,
                                     nbytes, sha))
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Refusal("INPUT_INVALID", "games.csv is not UTF-8: %s" % exc)
    games = parse_games_text(text, ["game_id", "season", "week", "gameday"])
    inputs = Inputs(games, url, retrieved, actual_sha)
    _INPUT_CACHE.append(inputs)
    return inputs


# Optional columns of a --results-file: where each final score came from.
RESULT_PROVENANCE_COLS = ("source", "source_url", "retrieved_at_utc")


def load_results_file(path):
    data = read_text_file(path, "results file")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Refusal("INPUT_INVALID", "results file is not UTF-8: %s" % exc)
    games = parse_games_text(text, ["game_id", "home_score", "away_score"])
    by_id = dict((g["game_id"], g) for g in games)
    # Optional per-row provenance columns (real_intake.py writes them). They
    # are copied as cleaned text onto each settlement row, never evaluated.
    for row in csv.DictReader(io.StringIO(text)):
        game = by_id.get(clean((row.get("game_id") or "").strip()))
        if game is None:
            continue
        for col in RESULT_PROVENANCE_COLS:
            val = clean((row.get(col) or "").strip())[:400]
            if col == "retrieved_at_utc" and val and parse_ts(val) is None:
                val = ""
            game["result_" + col] = val or None
    return by_id


# --- slate -----------------------------------------------------------------
def resolve_slate(games, now, season, week):
    if (season is None) != (week is None):
        raise Refusal("BAD_ARGS", "give both --season and --week, or neither")
    if season is None:
        upcoming = [g for g in games
                    if g["kickoff"] is not None and g["kickoff"] > now
                    and g["spread_line"] is not None
                    and g["season"] is not None and g["week"] is not None]
        if not upcoming:
            raise Refusal("NO_SLATE", "no game with a future kickoff and a "
                          "spread_line in games.csv")
        first = min(upcoming, key=lambda g: (g["kickoff"], g["game_id"]))
        season, week = first["season"], first["week"]
    slate = [g for g in games if g["season"] == season and g["week"] == week]
    if not slate:
        raise Refusal("NO_SLATE", "no games for season %s week %s"
                      % (season, week))
    far = datetime(9999, 1, 1, tzinfo=timezone.utc)
    slate.sort(key=lambda g: (g["kickoff"] or far, g["game_id"]))
    return season, week, slate


def spread_text(g):
    sl = g["spread_line"]
    if sl is None:
        return "n/a"
    if sl == 0:
        return "PK"
    if sl > 0:
        return "%s -%g" % (g["home_team"], sl)
    return "%s -%g" % (g["away_team"], -sl)


def ml_text(price):
    if price is None:
        return "n/a"
    return "%+d %s" % (price, "in" if in_band(price) else "OUT")


def cmd_slate(ctx, args):
    inputs = load_inputs()
    season, week, slate = resolve_slate(inputs.games, ctx.now,
                                        args.season, args.week)
    out("SLATE: season %s week %s, decision time %s (%d games)"
        % (season, week, fmt_ts(ctx.now), len(slate)))
    header = ["game_id", "kickoff_utc", "away@home", "spread", "total",
              "away_ML", "home_ML", "status"]
    rows = []
    for g in slate:
        ko = g["kickoff"]
        if ko is None:
            status = "NO KICKOFF"
        elif ko <= ctx.now:
            status = "KICKED OFF"
        else:
            status = "open"
        rows.append([
            g["game_id"], fmt_ts(ko) if ko else "unknown",
            "%s@%s" % (g["away_team"], g["home_team"]), spread_text(g),
            "n/a" if g["total_line"] is None else "%g" % g["total_line"],
            ml_text(g["away_moneyline"]), ml_text(g["home_moneyline"]),
            status])
    widths = [max(len(header[i]), max(len(r[i]) for r in rows))
              for i in range(len(header))]
    out("  ".join(header[i].ljust(widths[i]) for i in range(len(header))))
    for r in rows:
        out("  ".join(r[i].ljust(widths[i]) for i in range(len(header))))
    lo, hi = MANUAL_PRICE_BAND
    out("")
    out("ML band: 'in' means American price between %d and %+d inclusive."
        % (lo, hi))
    out("Team markets only (spread, total, moneyline). Player props are not "
        "in this data source.")
    age = (ctx.now - inputs.retrieved).total_seconds() / 3600.0
    out("Line source: %s retrieved %s (file age %.1f hours at decision time)"
        % (inputs.url, inputs.retrieved_str, age))
    out(PRICE_NOTICE % inputs.retrieved_str)
    if age > MAX_LINE_AGE_HOURS:
        out("WARNING: the downloaded file is older than %g hours; generate "
            "will reject its rows as STALE_LINE until games.csv is "
            "re-fetched. This is a check on the age of the FILE only."
            % MAX_LINE_AGE_HOURS)
    return EXIT_OK


# --- storage ---------------------------------------------------------------
class Paths(object):
    def __init__(self, directory):
        self.dir = directory
        self.ledger = os.path.join(directory, LEDGER_NAME)
        self.rejections = os.path.join(directory, REJECTIONS_NAME)
        self.settlements = os.path.join(directory, SETTLEMENTS_NAME)
        self.observations = os.path.join(directory, OBSERVATIONS_NAME)


@contextmanager
def ledger_lock(directory):
    """Exclusive lock so two writers cannot interleave read-check-append."""
    os.makedirs(directory, exist_ok=True)
    fd = os.open(os.path.join(directory, ".ledger.lock"),
                 os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def load_jsonl(path):
    """Every line must be a JSON object; anything else is LEDGER_CORRUPT."""
    if not os.path.exists(path):
        return []
    records = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                try:
                    rec = json.loads(line)
                except ValueError as exc:
                    raise Refusal("LEDGER_CORRUPT", "%s line %d: %s"
                                  % (path, n, exc))
                if not isinstance(rec, dict):
                    raise Refusal("LEDGER_CORRUPT",
                                  "%s line %d is not a JSON object"
                                  % (path, n))
                records.append(rec)
    except UnicodeDecodeError as exc:
        raise Refusal("LEDGER_CORRUPT", "%s is not valid UTF-8: %s"
                      % (path, exc))
    return records


def is_number(x):
    return (isinstance(x, (int, float)) and not isinstance(x, bool)
            and math.isfinite(x))


def check_entries(entries, path):
    seen = set()
    for i, e in enumerate(entries, 1):
        where = "%s record %d" % (path, i)
        if (e.get("action") not in ("take", "pass")
                or not isinstance(e.get("game_id"), str)
                or not isinstance(e.get("rule_version"), str)
                or e.get("market") not in SIDES_BY_MARKET
                or parse_ts(e.get("kickoff_utc")) is None
                or not is_number(e.get("stake_units"))):
            raise Refusal("LEDGER_CORRUPT", "%s has missing/invalid fields"
                          % where)
        pid = e.get("pick_id")
        if "contract_key" in e:
            # rows written by this version: key and id must match the fields
            if (e["contract_key"] != contract_identity(e)
                    or pid != pick_id_for(e["contract_key"])):
                raise Refusal("LEDGER_CORRUPT",
                              "%s contract_key/pick_id do not match its "
                              "key fields" % where)
        elif not isinstance(pid, str) or not pid:
            # legacy row (no contract_key): keep its old-format pick_id as is
            raise Refusal("LEDGER_CORRUPT", "%s has no pick_id" % where)
        if pid in seen:
            raise Refusal("LEDGER_CORRUPT", "%s repeats pick_id %s"
                          % (where, pid))
        seen.add(pid)


def check_settlements(settlements, entries, path):
    ids = dict((e["pick_id"], e) for e in entries)
    seen = set()
    for i, s in enumerate(settlements, 1):
        where = "%s record %d" % (path, i)
        pid = s.get("pick_id")
        if (pid not in ids or s.get("action") not in ("take", "pass")
                or not isinstance(s.get("outcome"), str)
                or not is_number(s.get("pnl_units"))):
            raise Refusal("LEDGER_CORRUPT",
                          "%s is invalid or has no matching ledger pick"
                          % where)
        if pid in seen:
            raise Refusal("LEDGER_CORRUPT", "%s repeats pick_id %s"
                          % (where, pid))
        seen.add(pid)


def compute_settled_state(settlements):
    """Running settled P&L, peak, drawdown, record, and the stop-rule flag."""
    cum = 0.0
    peak = 0.0
    wins = losses = pushes = 0
    sh_w = sh_l = sh_p = 0
    sh_pnl = 0.0
    for s in settlements:
        if s.get("action") == "take":
            cum += float(s["pnl_units"])
            peak = max(peak, cum)
            if s["outcome"] == "win":
                wins += 1
            elif s["outcome"] == "loss":
                losses += 1
            elif s["outcome"] == "push":
                pushes += 1
        elif s.get("shadow_outcome") in ("win", "loss", "push"):
            sh_w += s["shadow_outcome"] == "win"
            sh_l += s["shadow_outcome"] == "loss"
            sh_p += s["shadow_outcome"] == "push"
            sh_pnl += float(s.get("shadow_pnl_units") or 0.0)
    cum = round(cum, 6)
    peak = round(peak, 6)
    drawdown = round(peak - cum, 6)
    stop = (drawdown >= STOP_DRAWDOWN_UNITS - 1e-9
            or cum <= -STOP_DRAWDOWN_UNITS + 1e-9)
    return {"wins": wins, "losses": losses, "pushes": pushes, "cum": cum,
            "peak": peak, "drawdown": drawdown, "stop_active": stop,
            "shadow_w": sh_w, "shadow_l": sh_l, "shadow_p": sh_p,
            "shadow_pnl": round(sh_pnl, 6)}


def load_state(paths):
    entries = load_jsonl(paths.ledger)
    check_entries(entries, paths.ledger)
    settlements = load_jsonl(paths.settlements)
    check_settlements(settlements, entries, paths.settlements)
    rejections = load_jsonl(paths.rejections)
    for i, r in enumerate(rejections, 1):
        if not isinstance(r.get("code"), str):
            raise Refusal("LEDGER_CORRUPT",
                          "%s record %d has no code" % (paths.rejections, i))
    return {"entries": entries, "rejections": rejections,
            "settlements": settlements,
            "settled": compute_settled_state(settlements)}


def append_jsonl(path, record):
    line = json.dumps(record, allow_nan=False) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


# --- the one validation gate -----------------------------------------------
def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def is_manual(entry):
    return entry.get("price_status") == "user_reported_quote"


def missing_parts(entry):
    """Names of required line/price/timestamp/source parts that are missing."""
    missing = []
    market = entry.get("market")
    is_take = entry.get("action") == "take"
    manual = is_manual(entry)
    if market != "moneyline" and _blank(entry.get("line")):
        missing.append("line")
    price_needed = is_take or entry.get("side") is not None
    if price_needed and _blank(entry.get("price_american")):
        missing.append("price")
    if _blank(entry.get("line_ts_utc")):
        missing.append("quote timestamp (--quote-ts)" if manual
                       else "file retrieval timestamp")
    if _blank(entry.get("line_source")):
        missing.append("quote source (--source)" if manual
                       else "line source")
    return missing


def validate_entry(entry, existing_entries, settled_state, now_utc):
    """Return a rejection code, or None when the entry is acceptable.

    The 12-hour gate (STALE_LINE) is a check on line_ts_utc. For rows built
    from the downloaded file that is the FILE retrieval time: it says how old
    the file is and is never proof that a quote is fresh, still offered or
    available. For manual takes and passes it is the user-reported quote time.
    """
    # Same contract (game, rule version, market, selection, side, line) already
    # in the ledger? Identity is recomputed from every existing row's own
    # fields, so old rows without contract_key still block an exact retry.
    identity = contract_identity(entry)
    for e in existing_entries:
        if contract_identity(e) == identity:
            return "DUPLICATE_PICK"
    kickoff = parse_ts(entry.get("kickoff_utc"))
    if kickoff is None:
        return "MISSING_KICKOFF"
    if now_utc >= kickoff:
        return "KICKOFF_PASSED"
    if missing_parts(entry):
        return "MISSING_LINE"
    line_ts = parse_ts(entry.get("line_ts_utc"))
    if line_ts is None:
        return "BAD_TIMESTAMP"
    if line_ts > now_utc:
        return "FUTURE_DATED_INPUT"
    if now_utc - line_ts > timedelta(hours=MAX_LINE_AGE_HOURS):
        return "STALE_LINE"
    is_take = entry.get("action") == "take"
    if is_take:
        stake = entry.get("stake_units")
        if not is_number(stake) or stake <= 0:
            return "BAD_STAKE"
        if stake > STAKE_CAP_UNITS:
            return "STAKE_OVER_CAP"
    if is_take and settled_state.get("stop_active"):
        return "STOP_RULE_ACTIVE"
    return None


def rejection_detail(code, entry, now_utc):
    """Human text for a code returned by validate_entry (or a pre-check)."""
    ko = entry.get("kickoff_utc")
    if code == "MISSING_KICKOFF":
        return "kickoff time unknown for %s (gametime empty or unparsable)" \
            % entry.get("game_id")
    if code == "KICKOFF_PASSED":
        return "decision time %s is at or after kickoff %s" \
            % (fmt_ts(now_utc), ko)
    if code == "MISSING_LINE":
        return "missing: %s" % ", ".join(missing_parts(entry))
    if code == "BAD_TIMESTAMP":
        return "%s %r is not strict UTC ISO 'YYYY-MM-DDTHH:MM:SSZ'" \
            % ("--quote-ts" if is_manual(entry) else "line_ts_utc",
               entry.get("line_ts_utc"))
    if code == "FUTURE_DATED_INPUT":
        return "%s %s is after decision time %s" \
            % ("user-reported quote time" if is_manual(entry)
               else "file retrieval time", entry.get("line_ts_utc"),
               fmt_ts(now_utc))
    if code == "STALE_LINE":
        age = (now_utc - parse_ts(entry["line_ts_utc"])).total_seconds() \
            / 3600.0
        if is_manual(entry):
            return ("user-reported quote time %s is %.1f hours old at "
                    "decision time; max %g hours"
                    % (entry["line_ts_utc"], age, MAX_LINE_AGE_HOURS))
        return ("the downloaded file (retrieved %s) is %.1f hours old at "
                "decision time; max %g hours. This checks the age of the "
                "FILE only; it is not proof that any sportsbook quote is "
                "fresh, still offered or available"
                % (entry["line_ts_utc"], age, MAX_LINE_AGE_HOURS))
    if code == "BAD_STAKE":
        return "stake %r must be a number greater than 0" \
            % (entry.get("stake_units"),)
    if code == "STAKE_OVER_CAP":
        return "stake %g exceeds cap %g units" \
            % (entry.get("stake_units"), STAKE_CAP_UNITS)
    if code == "DUPLICATE_PICK":
        return "contract already in ledger (game, rule version, market, " \
            "selection, side and line all match): %s" \
            % contract_identity(entry)
    if code == "STOP_RULE_ACTIVE":
        return "stop rule active: settled drawdown reached %g units; " \
            "no new takes" % STOP_DRAWDOWN_UNITS
    return code


def log_rejection(ctx, source, code, detail, entry, dedupe_keys=None):
    """Append to rejections.jsonl. Returns True if a line was written."""
    pid = entry.get("pick_id")
    if dedupe_keys is not None:
        if (pid, code) in dedupe_keys:
            return False
        dedupe_keys.add((pid, code))
    rec = {"ts_utc": fmt_ts(ctx.now), "code": code, "detail": detail,
           "source": source, "fixture": ctx.fixture, "pick_id": pid,
           "entry": entry}
    append_jsonl(ctx.paths.rejections, rec)
    return True


# --- spread line conventions -----------------------------------------------
# A spread line can be written with two opposite signs. Every spread row is
# graded in the convention it was written in, never in the other one.
#   ticket_handicap: the handicap on the side picked, exactly as a sportsbook
#     ticket shows it. "home -2.5" means the home team must win by more than
#     2.5. Used by every personal (manual) spread row.
#   nflverse_home_favored_positive: the archive's spread_line. Positive means
#     the HOME team is favored by that many points, whichever side the rule
#     takes. Used by every rule-generated spread row (same as backtest.py).
CONV_TICKET = "ticket_handicap"
CONV_NFLVERSE = "nflverse_home_favored_positive"
LINE_CONVENTIONS = (CONV_TICKET, CONV_NFLVERSE)


def line_convention_of(entry):
    """(convention, basis) for a spread row.

    basis is "stated" when the row carries line_convention. Rows written
    before the field existed are handled explicitly: a personal row
    (entered_by manual, or a MANUAL- rule id) is a ticket handicap, a
    rule-generated row is the archive convention. An unknown stated value
    raises ValueError so settlement reports UNGRADEABLE instead of guessing.
    """
    stated = entry.get("line_convention")
    if stated is not None:
        if stated not in LINE_CONVENTIONS:
            raise ValueError("unknown line_convention %r" % (stated,))
        return stated, "stated"
    who = entry.get("entered_by")
    if who == "manual" or (who is None and str(
            entry.get("rule_version") or "").startswith("MANUAL-")):
        return CONV_TICKET, "assumed_older_personal_row"
    return CONV_NFLVERSE, "assumed_older_rule_row"


def grade_entry(entry, home_score, away_score):
    """Grade one ledger row. Returns (outcome, convention, basis).

    Totals, moneylines and archive-convention spreads go through rules.grade
    unchanged. A ticket-handicap spread is graded as the selected team's
    margin plus the signed handicap: above 0 wins, below 0 loses, 0 pushes.
    """
    market = entry["market"]
    if market != "spread":
        return (rules.grade(market, entry["side"], entry["line"],
                            home_score, away_score), None, None)
    conv, basis = line_convention_of(entry)
    if conv == CONV_NFLVERSE:
        return (rules.grade(market, entry["side"], entry["line"],
                            home_score, away_score), conv, basis)
    side = entry["side"]
    if side not in ("home", "away"):
        raise ValueError("bad spread side: %r" % (side,))
    hs = float(home_score)
    as_ = float(away_score)
    margin = (hs - as_) if side == "home" else (as_ - hs)
    cover = margin + float(entry["line"])
    if cover == 0:
        return "push", conv, basis
    return ("win" if cover > 0 else "loss"), conv, basis


def ticket_meaning(team, handicap):
    """Plain words for a ticket-handicap spread, e.g. DET -2.5."""
    h = float(handicap)
    whole = (h == int(h))
    if h < 0:
        text = "%s %+g wins the bet only if %s wins the game by more than " \
               "%g points" % (team, h, team, -h)
        if whole:
            text += " (a win by exactly %g is a push)" % -h
        return text
    if h > 0:
        text = "%s %+g wins the bet if %s wins the game or loses by fewer " \
               "than %g points" % (team, h, team, h)
        if whole:
            text += " (a loss by exactly %g is a push)" % h
        return text
    return "%s pick'em wins the bet if %s wins the game (a tie is a push)" \
        % (team, team)


def convention_text(entry):
    try:
        conv, basis = line_convention_of(entry)
    except ValueError as exc:
        return str(exc)
    words = ("the handicap on the side picked, as a ticket shows it"
             if conv == CONV_TICKET else
             "the archive's line, positive when the HOME team is favored")
    return "%s (%s; %s)" % (conv, words, basis.replace("_", " "))


# --- entry builders --------------------------------------------------------
def base_entry(ctx, game, entered_by, rule_version, family, market):
    return finalize_entry({
        "mode": "paper",
        "fixture": ctx.fixture,
        "entered_by": entered_by,
        "game_id": game["game_id"],
        "season": game["season"],
        "week": game["week"],
        "away_team": game["away_team"],
        "home_team": game["home_team"],
        "kickoff_utc": fmt_ts(game["kickoff"]) if game["kickoff"] else None,
        "rule_version": rule_version,
        "family": family,
        "action": None,
        "market": market,
        "side": None,
        "selection": None,
        "line": None,
        "price_american": None,
        "price_field": None,
        "price_in_band": None,
        "stake_units": 0,
        "line_source": None,
        "line_source_sha256": None,
        "line_ts_utc": None,
        "line_ts_kind": None,
        "price_status": None,
        "quote_ts_utc": None,
        "quote_time_verified": False,
        "executable_price": False,
        "file_retrieved_ts_utc": None,
        "decision_ts_utc": fmt_ts(ctx.now),
        "reason": None,
    })


def build_rule_entry(ctx, inputs, game, rule):
    """Run rules.decide and build the (not yet validated) ledger entry."""
    family = rule["family"]
    market = rules.FAMILIES[family]["market"]
    entry = base_entry(ctx, game, "rule", rule["version_id"], family, market)
    entry["line_source"] = inputs.url
    entry["line_source_sha256"] = inputs.sha256
    # Every price in the downloaded file is an archived paper observation. Its
    # time is the FILE retrieval time; the sportsbook quote time is unknown.
    entry["line_ts_utc"] = inputs.retrieved_str
    entry["line_ts_kind"] = "file_retrieval"
    entry["file_retrieved_ts_utc"] = inputs.retrieved_str
    entry["price_status"] = "archived_observation"
    entry["quote_ts_utc"] = None
    entry["quote_time_verified"] = False
    entry["executable_price"] = False
    g = {"spread_line": game["spread_line"], "total_line": game["total_line"],
         "away_rest": game["away_rest"], "home_rest": game["home_rest"]}
    try:
        d = rules.decide(family, rule["value"], g)
    except ValueError as exc:
        # leaves action/side/line/price empty: the gate reports MISSING_LINE
        entry["reason"] = str(exc)
        return entry
    entry["action"] = d["action"]
    entry["market"] = d["market"]
    entry["side"] = d["side"]
    entry["line"] = d["line"]
    if d["market"] == "spread":
        # the archive's spread_line, unchanged: positive = HOME favored
        entry["line_convention"] = CONV_NFLVERSE
    entry["reason"] = d["reason"]
    finalize_entry(entry)
    if d["side"] is not None:
        field = PRICE_FIELDS.get((d["market"], d["side"]))
        entry["price_field"] = field
        entry["price_american"] = game.get(field) if field else None
    entry["stake_units"] = DEFAULT_STAKE_UNITS if d["action"] == "take" else 0
    return entry


# --- frozen rules ----------------------------------------------------------
def load_frozen(path, now):
    raw = read_text_file(path, "frozen rules file")
    try:
        doc = json.loads(raw.decode("utf-8"))
        frozen_at = doc["frozen_at_utc"]
        listed = doc["rules"]
        if not isinstance(listed, list) or not listed:
            raise ValueError("rules must be a non-empty list")
    except (ValueError, KeyError, TypeError) as exc:
        raise Refusal("FROZEN_RULES_INVALID", "%s: %s" % (path, exc))
    ts = parse_ts(frozen_at)
    if ts is None:
        raise Refusal("FROZEN_RULES_INVALID",
                      "frozen_at_utc %r is not strict UTC ISO" % (frozen_at,))
    if ts > now:
        raise Refusal("FROZEN_RULES_INVALID",
                      "rules frozen at %s are after decision time %s"
                      % (frozen_at, fmt_ts(now)))
    if "ruleset_version" in doc and doc["ruleset_version"] != \
            rules.RULESET_VERSION:
        raise Refusal("FROZEN_RULES_INVALID",
                      "ruleset_version %r != rules.py %r"
                      % (doc["ruleset_version"], rules.RULESET_VERSION))
    result = []
    seen = set()
    for item in listed:
        try:
            family = item["family"]
            value = float(item["value"])
            vid = item["version_id"]
            if family not in rules.FAMILIES or not math.isfinite(value):
                raise ValueError("unknown family or bad value")
            if vid != rules.version_id(family, value):
                raise ValueError("version_id %r does not match %s"
                                 % (vid, rules.version_id(family, value)))
        except (KeyError, TypeError, ValueError) as exc:
            raise Refusal("FROZEN_RULES_INVALID",
                          "rule %r: %s" % (item, exc))
        if vid in seen:
            raise Refusal("FROZEN_RULES_INVALID", "repeated rule %s" % vid)
        seen.add(vid)
        result.append({"version_id": vid, "family": family, "value": value})
    return result


# --- generate --------------------------------------------------------------
def cmd_generate(ctx, args):
    inputs = load_inputs()
    season, week, slate = resolve_slate(inputs.games, ctx.now,
                                        args.season, args.week)
    frozen = load_frozen(args.frozen_file or DEFAULT_FROZEN, ctx.now)
    out("GENERATE: season %s week %s, %d games x %d rules, decision time %s"
        % (season, week, len(slate), len(frozen), fmt_ts(ctx.now)))
    out(PRICE_NOTICE % inputs.retrieved_str)
    takes = passes = 0
    rejected = {}
    stop_blocked = False
    with ledger_lock(ctx.paths.dir):
        state = load_state(ctx.paths)
        existing = state["entries"]
        dedupe = set((r.get("pick_id"), r["code"])
                     for r in state["rejections"]
                     if r.get("source") == "generate")
        for game in slate:
            for rule in frozen:
                entry = build_rule_entry(ctx, inputs, game, rule)
                code = validate_entry(entry, existing, state["settled"],
                                      ctx.now)
                tag = "%s %s" % (game["game_id"], rule["version_id"])
                if code is None:
                    append_jsonl(ctx.paths.ledger, entry)
                    existing.append(entry)
                    if entry["action"] == "take":
                        takes += 1
                        out("TAKE      %s %s %s line=%s price=%s stake=%g"
                            % (tag, entry["market"], entry["side"],
                               entry["line"], entry["price_american"],
                               entry["stake_units"]))
                    else:
                        passes += 1
                        out("PASS      %s %s (%s)" % (
                            tag, entry["side"] or "no side", entry["reason"]))
                    continue
                rejected[code] = rejected.get(code, 0) + 1
                if code == "STOP_RULE_ACTIVE":
                    stop_blocked = True
                out("REJECTED  %s %s" % (code, tag))
                if code != "DUPLICATE_PICK":  # re-runs must add nothing
                    log_rejection(ctx, "generate", code,
                                  rejection_detail(code, entry, ctx.now),
                                  entry, dedupe)
    by_code = ", ".join("%s=%d" % (c, rejected[c]) for c in sorted(rejected))
    out("SUMMARY: %d takes, %d passes, %d rejected%s"
        % (takes, passes, sum(rejected.values()),
           " [%s]" % by_code if by_code else ""))
    out("Ledger lines added this run: %d. Ledger dir: %s"
        % (takes + passes, ctx.paths.dir))
    if stop_blocked:
        out("STOP RULE ACTIVE: takes were blocked. Passes are still logged.")
        return EXIT_STOP_RULE
    return EXIT_OK


# --- add (manual pick) -----------------------------------------------------
def check_manual_args(args, game):
    """Structural checks before the gate. Returns (code, detail) or None."""
    rule = args.rule or ""
    if not rule.startswith("MANUAL-"):
        return ("RULE_NOT_MANUAL", "--rule must start with 'MANUAL-'; "
                "rule-generated ids are refused (got %r)" % rule)
    if not MANUAL_RULE_RE.fullmatch(rule):
        return ("BAD_RULE_ID", "--rule may contain only letters, digits, "
                "'.', '_' and '-' after 'MANUAL-'")
    if game is None:
        return ("UNKNOWN_GAME", "game_id %s is not in games.csv"
                % clean(args.game_id))
    if args.side not in SIDES_BY_MARKET[args.market]:
        return ("BAD_SIDE", "side %r is not valid for market %s (use %s)"
                % (args.side, args.market,
                   "/".join(SIDES_BY_MARKET[args.market])))
    if args.market == "prop" and not (args.selection or "").strip():
        return ("MISSING_SELECTION", "prop picks need --selection text "
                "(player + stat)")
    if not (args.reason or "").strip():
        return ("MISSING_REASON", "--reason is required and must not be "
                "empty (say why you take or pass)")
    if args.action == "pass" and args.stake is not None:
        try:
            stake = parse_float(args.stake)
        except ValueError:
            stake = None
        if stake is None or stake != 0:
            return ("BAD_STAKE", "a personal pass is saved with stake 0; "
                    "omit --stake or give 0 (got %r)" % args.stake)
    try:
        price = parse_float(args.price)
    except ValueError:
        return ("BAD_PRICE", "price %r is not a number" % args.price)
    if price is not None and not valid_american(price):
        return ("BAD_PRICE", "price %r is not American odds (needs "
                "abs >= 100)" % args.price)
    try:
        parse_float(args.line)
    except ValueError:
        return ("BAD_LINE", "line %r is not a number" % args.line)
    return None


def build_manual_entry(ctx, args, game):
    if game is None:
        game = {"game_id": clean(args.game_id), "season": None, "week": None,
                "away_team": None, "home_team": None, "kickoff": None}
    entry = base_entry(ctx, game, "manual", args.rule, "MANUAL", args.market)
    entry["action"] = args.action
    entry["side"] = args.side
    selection = (args.selection or "").strip() or None
    entry["selection"] = selection
    try:
        line = parse_float(args.line)
    except ValueError:
        line = None
    entry["line"] = None if args.market == "moneyline" else line
    if args.market == "spread":
        # typed as the handicap on the side picked (home -2.5 = home must win
        # by more than 2.5). Stored as typed; graded in this convention.
        entry["line_convention"] = CONV_TICKET
    finalize_entry(entry)
    try:
        price = parse_float(args.price)
    except ValueError:
        price = None
    entry["price_american"] = norm_num(price)
    entry["price_field"] = "manual"
    entry["price_in_band"] = None if price is None else in_band(price)
    if args.action == "pass":
        entry["stake_units"] = 0
    elif args.stake is None:
        entry["stake_units"] = DEFAULT_STAKE_UNITS
    else:
        try:
            parsed = parse_float(args.stake)
        except ValueError:
            parsed = None
        entry["stake_units"] = args.stake if parsed is None \
            else norm_num(parsed)
    # The price is whatever the user read from an operator. It is a
    # user-reported quote: its time and source are his word, not verified.
    source = (args.source or "").strip() or None
    entry["line_source"] = source
    entry["line_source_sha256"] = None
    entry["line_ts_utc"] = args.quote_ts
    entry["line_ts_kind"] = "user_reported_quote"
    entry["price_status"] = "user_reported_quote"
    entry["quote_ts_utc"] = args.quote_ts
    entry["quote_source"] = source
    entry["quote_time_verified"] = False
    entry["executable_price"] = False
    entry["reason"] = (args.reason or "").strip() or None
    return entry


def reject_add(ctx, code, detail, entry):
    log_rejection(ctx, "add", code, detail, entry)
    err("REJECTED %s: %s" % (code, detail))
    out("REJECTED %s (logged to %s)" % (code, REJECTIONS_NAME))
    return EXIT_REFUSED


def cmd_add(ctx, args):
    inputs = load_inputs()
    game = inputs.by_id.get(clean(args.game_id))
    entry = build_manual_entry(ctx, args, game)
    with ledger_lock(ctx.paths.dir):
        state = load_state(ctx.paths)
        pre = check_manual_args(args, game)
        if pre is not None:
            return reject_add(ctx, pre[0], pre[1], entry)
        code = validate_entry(entry, state["entries"], state["settled"],
                              ctx.now)
        if code is not None:
            return reject_add(ctx, code,
                              rejection_detail(code, entry, ctx.now), entry)
        append_jsonl(ctx.paths.ledger, entry)
    out("ACCEPTED %s %s" % (entry["action"].upper(), entry["pick_id"]))
    out("  %s %s %s %s line=%s price=%s stake=%g"
        % (entry["game_id"], entry["rule_version"], entry["market"],
           entry["side"], entry["line"], entry["price_american"],
           entry["stake_units"]))
    if entry["market"] == "spread":
        team = game["home_team"] if entry["side"] == "home" \
            else game["away_team"]
        out("  spread saved as a ticket handicap on your side: %s"
            % ticket_meaning(team, entry["line"]))
        sl = game.get("spread_line")
        if sl is not None:
            archived = -float(sl) if entry["side"] == "home" else float(sl)
            typed = float(entry["line"])
            if archived * typed < 0:
                out("  note: the archived line has %s at %+g and you typed "
                    "%+g, the opposite sign. Saved as typed (lines move and "
                    "alternate spreads exist). If the sign was a slip, log "
                    "the pick again with the right sign; this row stays."
                    % (team, archived, typed))
    out("  reason: %s" % clean(entry["reason"]))
    out("  price is a user-reported quote (source %s, quote time %s, not "
        "verified)" % (clean(entry["line_source"]), entry["quote_ts_utc"]))
    if entry["price_in_band"] is False:
        out("  note: price %s is outside the manual band %d to %+d "
            "(recorded price_in_band=false)"
            % ((entry["price_american"],) + MANUAL_PRICE_BAND))
    return EXIT_OK


# --- close (closing-line observation) --------------------------------------
def cmd_close(ctx, args):
    """Record a closing-line price against ONE existing pick.

    The observation is tied to the pick_id and to its exact contract. A price
    for one line (for example 60.5) can never be attached to a pick at another
    line (for example 54.5): --line is compared with the pick's own line.
    """
    with ledger_lock(ctx.paths.dir):
        state = load_state(ctx.paths)
        entry = None
        for e in state["entries"]:
            if e["pick_id"] == args.pick_id:
                entry = e
        code = detail = None
        price = None
        quote_ts = parse_ts(args.quote_ts)
        if entry is None:
            code, detail = "UNKNOWN_PICK", "no ledger pick %r" \
                % clean(args.pick_id)
            entry = {"pick_id": clean(args.pick_id)}
        else:
            try:
                price = parse_float(args.price)
            except ValueError:
                price = None
            try:
                given = parse_float(args.line)
            except ValueError:
                given = False
            if args.line is not None and (
                    given is False or given is None
                    or line_text(given) != line_text(entry.get("line"))):
                code = "CONTRACT_MISMATCH"
                detail = ("--line %s does not match this pick's line %s; a "
                          "price for another line cannot be attached to it"
                          % (clean(args.line),
                             line_text(entry.get("line")) or "(none)"))
            elif args.line is None and entry.get("line") is not None:
                code = "MISSING_LINE"
                detail = ("--line is required: this pick is priced against "
                          "line %s, so say which line your quote is for"
                          % line_text(entry.get("line")))
            elif not valid_american(price):
                code, detail = "BAD_PRICE", ("price %r is not American odds "
                                             "(needs abs >= 100)" % args.price)
            elif not (args.source or "").strip():
                code, detail = "MISSING_SOURCE", "--source is required"
            elif quote_ts is None:
                code, detail = "BAD_TIMESTAMP", (
                    "--quote-ts %r is not strict UTC ISO "
                    "'YYYY-MM-DDTHH:MM:SSZ'" % args.quote_ts)
            elif quote_ts > ctx.now:
                code, detail = "FUTURE_DATED_INPUT", (
                    "--quote-ts %s is after decision time %s"
                    % (args.quote_ts, fmt_ts(ctx.now)))
        if code:
            log_rejection(ctx, "close", code, detail, entry)
            err("REJECTED %s: %s" % (code, detail))
            out("REJECTED %s (logged to %s)" % (code, REJECTIONS_NAME))
            return EXIT_REFUSED
        kickoff = parse_ts(entry.get("kickoff_utc"))
        decision = parse_ts(entry.get("decision_ts_utc"))
        reasons = []
        if decision is None:
            reasons.append("pick_decision_time_unknown")
        elif quote_ts < decision:
            reasons.append("quote_before_pick_decision")
        if kickoff is None:
            reasons.append("kickoff_unknown")
        elif quote_ts >= kickoff:
            reasons.append("quote_at_or_after_kickoff")
        # --not-a-close: a real price read well before kickoff. It is tied to
        # the same exact contract but is never an exact-close candidate.
        not_a_close = bool(getattr(args, "not_a_close", False))
        if not_a_close:
            reasons.append("recorded_as_price_observation_not_a_close")
        eligible = not reasons
        rec = {
            "kind": ("price_observation" if not_a_close
                     else "closing_line_observation"),
            "observation_kind": ("price_observation_not_a_close"
                                 if not_a_close else
                                 "exact_close_candidate" if eligible
                                 else "other_observation"),
            "exact_close_eligible": eligible,
            "exclusion_reasons": reasons,
            "line_stated": args.line is not None,
            "pick_decision_ts_utc": entry.get("decision_ts_utc"),
            "kickoff_utc": entry.get("kickoff_utc"),
            "minutes_before_kickoff": (
                None if kickoff is None else
                round((kickoff - quote_ts).total_seconds() / 60.0, 1)),
            "pick_id": entry["pick_id"],
            "contract_key": entry.get("contract_key")
            or contract_identity(entry),
            "game_id": entry["game_id"],
            "rule_version": entry["rule_version"],
            "market": entry["market"],
            "side": entry.get("side"),
            "selection": entry.get("selection"),
            "line": entry.get("line"),
            "price_american": norm_num(price),
            "source": args.source.strip(),
            "quote_ts_utc": args.quote_ts,
            "quote_time_verified": False,
            "quote_before_kickoff": (kickoff is not None
                                     and quote_ts < kickoff),
            "recorded_ts_utc": fmt_ts(ctx.now),
            "fixture": ctx.fixture,
        }
        append_jsonl(ctx.paths.observations, rec)
    out("%s for %s (%s %s %s line=%s): price %s, source %s, "
        "quote time %s (user-reported, not verified)"
        % ("PRICE OBSERVATION RECORDED (not a closing line)" if not_a_close
           else "CLOSE RECORDED" if rec["exact_close_eligible"]
           else "OTHER OBSERVATION RECORDED", rec["pick_id"], rec["game_id"], rec["market"], rec["side"],
           line_text(rec["line"]) or "none", rec["price_american"],
           clean(rec["source"]), rec["quote_ts_utc"]))
    if rec["market"] == "spread":
        out("  this pick's spread line is %s; a close must use the same "
            "number and sign" % convention_text(entry))
    if rec["exact_close_eligible"]:
        out("  exact-close candidate: identical contract, quoted after the "
            "pick's decision time and %s minutes before kickoff"
            % rec["minutes_before_kickoff"])
    else:
        out("  EXCLUDED from exact-close comparison: %s"
            % ", ".join(rec["exclusion_reasons"]))
    out("Observation appended to %s" % OBSERVATIONS_NAME)
    return EXIT_OK


# --- settle ----------------------------------------------------------------
def score_value(x):
    return int(x) if float(x).is_integer() else float(x)


def pnl_for(outcome, price, stake):
    if outcome == "win":
        return round(rules.american_profit(price, stake), 6)
    if outcome == "loss":
        return round(-float(stake), 6)
    return 0.0


def settle_gate(entry, settlements, now_utc):
    """Settlement refusals shared by settle and settle-manual."""
    if now_utc < parse_ts(entry["kickoff_utc"]):
        return "SETTLE_BEFORE_KICKOFF"
    for s in settlements:
        if s.get("pick_id") == entry["pick_id"]:
            return "DUPLICATE_SETTLEMENT"
    return None


def settle_detail(code, entry, now_utc):
    if code == "SETTLE_BEFORE_KICKOFF":
        return "decision time %s is before kickoff %s" \
            % (fmt_ts(now_utc), entry.get("kickoff_utc"))
    if code == "DUPLICATE_SETTLEMENT":
        return "pick %s is already settled" % entry.get("pick_id")
    return code


def base_settlement(ctx, entry, source):
    return {"pick_id": entry["pick_id"], "game_id": entry["game_id"],
            "action": entry["action"], "market": entry["market"],
            "rule_version": entry["rule_version"],
            "settled_ts_utc": fmt_ts(ctx.now), "fixture": ctx.fixture,
            "results_source": source}


def cmd_settle(ctx, args):
    if args.results_file:
        results = load_results_file(args.results_file)
        results_ts = args.results_ts
        source = "%s retrieved_at %s" % (
            os.path.abspath(args.results_file),
            results_ts or "unknown (no --results-ts given)")
    else:
        inputs = load_inputs()
        results = inputs.by_id
        results_ts = args.results_ts or inputs.retrieved_str
        source = "%s sha256 %s retrieved_at %s" % (inputs.url, inputs.sha256,
                                                   results_ts)
    if args.results_ts is not None and parse_ts(args.results_ts) is None:
        raise Refusal("BAD_TIMESTAMP",
                      "--results-ts %r is not strict UTC ISO" % args.results_ts)
    settled_n = {"take": 0, "pass": 0}
    pending = skipped = refused = 0
    out("SETTLE: decision time %s, results source: %s"
        % (fmt_ts(ctx.now), source))
    with ledger_lock(ctx.paths.dir):
        state = load_state(ctx.paths)
        done = set(s["pick_id"] for s in state["settlements"])
        todo = sorted((e for e in state["entries"]
                       if e["pick_id"] not in done),
                      key=lambda e: (e["kickoff_utc"], e["pick_id"]))
        for e in todo:
            tag = "%s %s %s" % (e["pick_id"], e["game_id"], e["rule_version"])
            if e["market"] == "prop":
                out("SKIP      %s needs settle-manual" % tag)
                skipped += 1
                continue
            if e["action"] == "pass" and e["side"] is None:
                skipped += 1
                continue
            row = results.get(e["game_id"])
            if (row is None or row["home_score"] is None
                    or row["away_score"] is None):
                pending += 1
                continue
            if (row["home_team"] and row["home_team"] != e["home_team"]) or \
                    (row["away_team"] and row["away_team"] != e["away_team"]):
                refused += 1
                out("REFUSED   RESULT_MISMATCH %s: teams differ" % tag)
                log_rejection(ctx, "settle", "RESULT_MISMATCH",
                              "results row teams differ from ledger", e)
                continue
            code = settle_gate(e, state["settlements"], ctx.now)
            if code is not None:
                refused += 1
                out("REFUSED   %s %s" % (code, tag))
                log_rejection(ctx, "settle", code,
                              settle_detail(code, e, ctx.now), e)
                continue
            try:
                outcome, conv, basis = grade_entry(
                    e, row["home_score"], row["away_score"])
            except (ValueError, TypeError) as exc:
                refused += 1
                out("REFUSED   UNGRADEABLE %s: %s" % (tag, exc))
                log_rejection(ctx, "settle", "UNGRADEABLE", str(exc), e)
                continue
            rec = base_settlement(ctx, e, source)
            rec["home_score"] = score_value(row["home_score"])
            rec["away_score"] = score_value(row["away_score"])
            rec["side"] = e["side"]
            rec["line"] = e["line"]
            rec["line_convention"] = conv
            rec["line_convention_basis"] = basis
            for col in RESULT_PROVENANCE_COLS:
                if row.get("result_" + col):
                    rec["result_" + col] = row["result_" + col]
            if basis is not None and basis != "stated":
                out("NOTE      %s has no line_convention (older row); graded "
                    "as %s" % (tag, conv))
            if e["action"] == "take":
                rec["outcome"] = outcome
                rec["pnl_units"] = pnl_for(outcome, e["price_american"],
                                           e["stake_units"])
                rec["shadow_outcome"] = None
                rec["shadow_pnl_units"] = None
                out("SETTLED   take %s %s pnl=%+.4fu" % (tag, outcome,
                                                          rec["pnl_units"]))
            else:
                rec["outcome"] = "pass"
                rec["pnl_units"] = 0.0
                rec["shadow_outcome"] = outcome
                rec["shadow_pnl_units"] = pnl_for(outcome, e["price_american"],
                                                  1.0)
                out("SETTLED   pass %s shadow=%s shadow_pnl=%+.4fu"
                    % (tag, outcome, rec["shadow_pnl_units"]))
            append_jsonl(ctx.paths.settlements, rec)
            state["settlements"].append(rec)
            settled_n[e["action"]] += 1
        final = compute_settled_state(state["settlements"])
    out("SUMMARY: settled %d takes, %d passes; pending %d; skipped %d; "
        "refused %d" % (settled_n["take"], settled_n["pass"], pending,
                        skipped, refused))
    out("Paper P&L %+.4fu, peak %+.4fu, drawdown %.4fu"
        % (final["cum"], final["peak"], final["drawdown"]))
    if final["stop_active"]:
        out("STOP RULE: ACTIVE")
    return EXIT_REFUSED if refused else EXIT_OK


def cmd_settle_manual(ctx, args):
    if not (args.result_source or "").strip():
        raise Refusal("MISSING_RESULT_SOURCE", "--result-source is required")
    with ledger_lock(ctx.paths.dir):
        state = load_state(ctx.paths)
        entry = None
        for e in state["entries"]:
            if e["pick_id"] == args.pick_id:
                entry = e
        code = detail = None
        if entry is None:
            code, detail = "UNKNOWN_PICK", "no ledger pick %r" % args.pick_id
            entry = {"pick_id": args.pick_id}
        elif entry["market"] != "prop":
            code = "NOT_A_PROP_TAKE"
            detail = "settle-manual is for prop picks only (props are not " \
                "in the results file); use settle for team markets"
        else:
            code = settle_gate(entry, state["settlements"], ctx.now)
            if code:
                detail = settle_detail(code, entry, ctx.now)
        if code:
            log_rejection(ctx, "settle-manual", code, detail, entry)
            err("REFUSED %s: %s" % (code, detail))
            out("REFUSED %s (logged to %s)" % (code, REJECTIONS_NAME))
            return EXIT_REFUSED
        rec = base_settlement(ctx, entry, args.result_source.strip())
        rec["home_score"] = None
        rec["away_score"] = None
        if entry["action"] == "take":
            rec["outcome"] = args.outcome
            rec["pnl_units"] = pnl_for(args.outcome, entry["price_american"],
                                       entry["stake_units"])
            rec["shadow_outcome"] = None
            rec["shadow_pnl_units"] = None
        else:  # personal pass: no P&L, shadow record at 1u flat
            rec["outcome"] = "pass"
            rec["pnl_units"] = 0.0
            rec["shadow_outcome"] = args.outcome
            rec["shadow_pnl_units"] = pnl_for(
                args.outcome, entry["price_american"], 1.0)
        append_jsonl(ctx.paths.settlements, rec)
        state["settlements"].append(rec)
        final = compute_settled_state(state["settlements"])
    out("SETTLED %s %s pnl=%+.4fu" % (entry["pick_id"], args.outcome,
                                       rec["pnl_units"]))
    out("Paper P&L %+.4fu, peak %+.4fu, drawdown %.4fu"
        % (final["cum"], final["peak"], final["drawdown"]))
    if final["stop_active"]:
        out("STOP RULE: ACTIVE")
    return EXIT_OK


# --- status ----------------------------------------------------------------
def cmd_status(ctx, args):
    state = load_state(ctx.paths)
    entries = state["entries"]
    s = state["settled"]
    takes = [e for e in entries if e["action"] == "take"]
    passes = [e for e in entries if e["action"] == "pass"]
    done = set(x["pick_id"] for x in state["settlements"])
    out("LEDGER: %s%s" % (ctx.paths.dir,
                          " (fixture mode)" if ctx.fixture else ""))
    try:
        retrieved = load_inputs().retrieved_str
    except Refusal as refusal:
        retrieved = "unknown (%s)" % refusal.code
    out(PRICE_NOTICE % retrieved)
    all_obs = load_jsonl(ctx.paths.observations)
    n_price_obs = sum(1 for o in all_obs
                      if o.get("kind") == "price_observation")
    obs = [o for o in all_obs if o.get("kind") != "price_observation"]
    n_exact = sum(1 for o in obs if o.get("exact_close_eligible") is True)
    out("Takes: %d (unsettled %d)   Passes: %d   Rejections: %d   "
        "Closing-line observations: %d (exact-close candidates %d, other %d "
        "excluded from exact-close comparison)"
        % (len(takes), sum(1 for e in takes if e["pick_id"] not in done),
           len(passes), len(state["rejections"]), len(obs), n_exact,
           len(obs) - n_exact))
    if n_price_obs:
        out("Real price observations before kickoff (not closing lines): %d"
            % n_price_obs)
    by_code = {}
    for r in state["rejections"]:
        by_code[r["code"]] = by_code.get(r["code"], 0) + 1
    for code in sorted(by_code):
        out("  rejected %-22s %d" % (code, by_code[code]))
    out("Settled takes W-L-P: %d-%d-%d" % (s["wins"], s["losses"],
                                           s["pushes"]))
    out("Cumulative paper P&L: %+.4f units   peak: %+.4f   current "
        "drawdown: %.4f" % (s["cum"], s["peak"], s["drawdown"]))
    out("Passes shadow record W-L-P (1u flat on the shadow side): %d-%d-%d  "
        "shadow P&L %+.4f units" % (s["shadow_w"], s["shadow_l"],
                                    s["shadow_p"], s["shadow_pnl"]))
    out("Per rule (take/pass):")
    per_rule = {}
    for e in entries:
        c = per_rule.setdefault(e["rule_version"], [0, 0])
        c[0 if e["action"] == "take" else 1] += 1
    for rv in sorted(per_rule):
        out("  %-28s take %d  pass %d" % (rv, per_rule[rv][0],
                                          per_rule[rv][1]))
    if s["stop_active"]:
        out("STOP RULE: ACTIVE")
    else:
        out("STOP RULE: not active (limit %.1fu drawdown)"
            % STOP_DRAWDOWN_UNITS)
    return EXIT_OK


# --- context and CLI -------------------------------------------------------
class Context(object):
    def __init__(self, now, fixture, paths):
        self.now = now
        self.fixture = fixture
        self.paths = paths


def build_context(args):
    if args.ledger_dir:
        directory = os.path.abspath(args.ledger_dir)
    elif args.fixture:
        directory = FIXTURE_LEDGER_DIR
    else:
        directory = REAL_LEDGER_DIR
    is_real_dir = os.path.realpath(directory) == os.path.realpath(
        REAL_LEDGER_DIR)
    if args.fixture and is_real_dir:
        raise Refusal("LEDGER_DIR_CONFLICT",
                      "--fixture cannot write into the real ledger directory")
    if args.now is not None:
        if is_real_dir:
            raise Refusal("NOW_OVERRIDE_NOT_ALLOWED",
                          "--now is only allowed with --fixture or "
                          "--ledger-dir (the real ledger always uses the "
                          "system clock)")
        now = parse_ts(args.now)
        if now is None:
            raise Refusal("BAD_TIMESTAMP",
                          "--now %r is not strict UTC ISO "
                          "'YYYY-MM-DDTHH:MM:SSZ'" % args.now)
    else:
        now = datetime.now(timezone.utc).replace(microsecond=0)
    return Context(now, bool(args.fixture), Paths(directory))


def add_globals(parser, is_sub):
    """Global options work before or after the subcommand."""
    sup = argparse.SUPPRESS if is_sub else None
    parser.add_argument("--fixture", action="store_true",
                        default=sup if is_sub else False,
                        help="use ledger/fixture/ and tag records fixture")
    parser.add_argument("--ledger-dir", default=sup,
                        help="override the ledger directory (tests)")
    parser.add_argument("--now", default=sup, metavar="ISO",
                        help="decision-time override; only with --fixture "
                             "or --ledger-dir")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="paper_ledger.py", allow_abbrev=False,
        description="Paper-only NFL pick ledger. " + BANNER)
    add_globals(parser, False)
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    def new(name, help_text):
        p = sub.add_parser(name, help=help_text, allow_abbrev=False)
        add_globals(p, True)
        return p

    p = new("slate", "show the next slate (read-only)")
    p.add_argument("--season", type=int)
    p.add_argument("--week", type=int)

    p = new("generate", "log rule-generated takes and passes. Prices come "
            "from the downloaded file and are archived observations, not "
            "live quotes. The 12-hour gate checks the age of the FILE only; "
            "it does not show that any quote is fresh, offered or available")
    p.add_argument("--season", type=int)
    p.add_argument("--week", type=int)
    p.add_argument("--frozen-file")

    p = new("add", "log one hand-entered pick (a personal take or pass)")
    p.add_argument("--game-id", required=True)
    p.add_argument("--rule", required=True, help="must start with MANUAL-")
    p.add_argument("--action", required=True, choices=["take", "pass"],
                   help="take = paper bet with a stake (max %g units); pass = "
                        "saved with stake 0 and your reason" % STAKE_CAP_UNITS)
    p.add_argument("--reason", required=True,
                   help="required, not empty: why you take or pass")
    p.add_argument("--market", required=True,
                   choices=["spread", "total", "moneyline", "prop"])
    p.add_argument("--side", required=True,
                   choices=["home", "away", "over", "under"])
    p.add_argument("--price", help="the American price you were offered, "
                   "e.g. -110 or +130 (your range is %d to %+d)"
                   % MANUAL_PRICE_BAND)
    p.add_argument("--quote-ts", "--line-ts", dest="quote_ts", metavar="ISO",
                   help="when you read the price, strict UTC "
                        "YYYY-MM-DDTHH:MM:SSZ. This is YOUR reported quote "
                        "time and is not verified. Rejected as STALE_LINE if "
                        "older than %g hours at decision time"
                        % MAX_LINE_AGE_HOURS)
    p.add_argument("--source", "--line-source", dest="source",
                   help="the operator or site you read the price from")
    p.add_argument("--line", help="spread, total or prop line; part of the "
                   "contract identity (54.5 and 60.5 are different picks). "
                   "For a spread, type the handicap on the side you picked "
                   "exactly as the operator shows it: favorite -2.5, "
                   "underdog +2.5 (write it as --line=-2.5). It is graded "
                   "as that side's margin plus the handicap.")
    p.add_argument("--selection", help="props only: player + stat, e.g. "
                   "'Jane Doe receiving yards'")
    p.add_argument("--stake", help="takes only, default %g, max %g units"
                   % (DEFAULT_STAKE_UNITS, STAKE_CAP_UNITS))

    p = new("close", "record a closing-line price against one existing pick")
    p.add_argument("--pick-id", required=True)
    p.add_argument("--price", required=True,
                   help="American closing price you read")
    p.add_argument("--source", required=True,
                   help="the operator or site you read it from")
    p.add_argument("--quote-ts", required=True, metavar="ISO",
                   help="when you read it, strict UTC YYYY-MM-DDTHH:MM:SSZ "
                        "(your word, not verified)")
    p.add_argument("--line", help="the line this price is for. Required when "
                   "the pick has a line (MISSING_LINE without it). A line "
                   "different from the pick's is rejected as "
                   "CONTRACT_MISMATCH. A quote from before the pick's "
                   "decision time or from kickoff onward is saved as an "
                   "other observation, excluded from exact-close comparison")
    p.add_argument("--not-a-close", action="store_true",
                   help="record this as a real price observation read before "
                        "kickoff, not a closing line. Same exact-contract "
                        "check; never counted as an exact-close candidate")

    p = new("settle", "settle finished games")
    p.add_argument("--results-file")
    p.add_argument("--results-ts")

    p = new("settle-manual", "settle one prop pick by hand")
    p.add_argument("--pick-id", required=True)
    p.add_argument("--outcome", required=True, choices=["win", "loss", "push"])
    p.add_argument("--result-source", required=True)

    new("status", "show counts, P&L and the stop rule (read-only)")
    return parser


COMMANDS = {
    "slate": cmd_slate,
    "generate": cmd_generate,
    "add": cmd_add,
    "close": cmd_close,
    "settle": cmd_settle,
    "settle-manual": cmd_settle_manual,
    "status": cmd_status,
}


def main(argv=None):
    out(BANNER)
    args = build_parser().parse_args(argv)
    try:
        ctx = build_context(args)
        return COMMANDS[args.command](ctx, args)
    except Refusal as refusal:
        err("REFUSED %s: %s" % (refusal.code, refusal.detail))
        out("REFUSED %s" % refusal.code)
        return EXIT_REFUSED
    except OSError as exc:
        err("REFUSED IO_ERROR: %s" % exc)
        out("REFUSED IO_ERROR")
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
