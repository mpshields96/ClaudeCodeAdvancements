"""Real-bar input for the paper runner. Standard library only.

There is one way in. Matthew exports a CSV file himself from a source whose
terms allow this use, and writes a small source file that names the source,
its terms page, a short quote of the terms and his own sign-off. This module
checks both, converts the CSV into the runner's feed format, and writes a
permitted-sources file so the runner's own provenance gate checks it again.

It fails closed. No source file means no bars are read and no signal is made.
Anything that looks like it came from TradingView is refused whole. Nothing
here opens a network connection, holds a key or places an order.

CSV format (header exactly, all times UTC):
    ts,open,high,low,close,volume
    2026-11-10T14:30:00Z,101.20,101.90,100.80,101.55,120400
`ts` is the time the bar opens. For daily rows `ts` may be a plain date
(2026-11-10) if the source file gives `daily_open_utc`.
"""
import csv
import hashlib
import io
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone

import provenance

SOURCE_SCHEMA = "tvbot-real-source-1"
REPORT_SCHEMA = "tvbot-real-source-report-1"
CSV_HEADER = ["ts", "open", "high", "low", "close", "volume"]
# Some vendors name the first column `datetime` and write `2026-11-13 14:30:00` with no zone.
# That shape is read only when the source file says "naive_ts_is_utc": true.
CSV_HEADER_ALT = ["datetime", "open", "high", "low", "close", "volume"]
REQUIRED = ("source_name", "terms_url", "terms_quote", "approved_by", "approved_utc",
            "csv_path", "symbol", "timeframe_minutes")
OPTIONAL = ("schema", "note", "daily_open_utc", "naive_ts_is_utc")
MAX_ROWS = 200000
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NAIVE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
TOD_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,39}$")
SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
NOT_A_PERSON = ("claude", "codex", "agent", "assistant", "gpt", "bot", "model")
DELIVERY_ASSUMPTION = ("A saved file has no arrival times, so each bar is treated as arriving "
                       "at the moment it closes. A decision is ready a few seconds later and "
                       "fills at the open of the next bar that opens after that.")
NO_SOURCE_MESSAGE = (
    "NO REAL SOURCE IS SET UP. No bars were read and no signal was made.\n"
    "To connect one, follow section (b) of nov14-sprint/tvbot/START_TONIGHT.md: export a CSV\n"
    "yourself from a source whose terms allow it, then write the small source file it describes.")


class SourceRefused(Exception):
    def __init__(self, code, message):
        Exception.__init__(self, message)
        self.code = code


def _refuse(code, message):
    raise SourceRefused(code, message)


def _parse_ts(text):
    return datetime.strptime(text, TS_FMT).replace(tzinfo=timezone.utc)


def _fmt_ts(dt):
    return dt.strftime(TS_FMT)


def _markers(label, text):
    hits = provenance.scan_text_for_markers(text)
    if hits:
        _refuse("tradingview_origin",
                "%s carries a TradingView marker (%s). TradingView data, exports and alerts "
                "are never read by this runner." % (label, "; ".join(hits)))


def load_source(path):
    """Read and check the source file Matthew wrote. Returns a dict."""
    if not path or not os.path.isfile(path):
        _refuse("no_source", NO_SOURCE_MESSAGE)
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    _markers("the source file", os.path.basename(path) + "\n" + text)
    try:
        cfg = json.loads(text)
    except ValueError as exc:
        _refuse("schema_rejected", "the source file is not valid JSON: %s" % exc)
    if not isinstance(cfg, dict):
        _refuse("schema_rejected", "the source file must be one JSON object")
    unknown = sorted(set(cfg) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        _refuse("schema_rejected", "the source file has fields this runner does not know: %s"
                % ", ".join(unknown))
    missing = [k for k in REQUIRED if cfg.get(k) in (None, "")]
    if missing:
        _refuse("schema_rejected", "the source file is missing: %s" % ", ".join(missing))
    if cfg.get("schema", SOURCE_SCHEMA) != SOURCE_SCHEMA:
        _refuse("schema_rejected", "schema must be %s" % SOURCE_SCHEMA)
    for k in ("source_name", "terms_url", "terms_quote", "approved_by", "approved_utc",
              "csv_path", "symbol"):
        if not isinstance(cfg[k], str):
            _refuse("schema_rejected", "%s must be text" % k)
    name = cfg["source_name"]
    if not NAME_RE.match(name) or name == "synthetic":
        _refuse("schema_rejected", "source_name must be a short lower-case name such as "
                "'stooq' or 'myfeed' (letters, digits, dot or dash), and not 'synthetic'")
    if not SYMBOL_RE.match(cfg["symbol"]) or cfg["symbol"].startswith("SYNTH"):
        _refuse("schema_rejected", "symbol must be a plain upper-case ticker such as SPY or "
                "BTCUSD, with no exchange prefix, and must not start with SYNTH")
    if not cfg["terms_url"].startswith("https://"):
        _refuse("schema_rejected", "terms_url must be the https address of the source's terms page")
    if len(cfg["terms_quote"].strip()) < 20:
        _refuse("schema_rejected", "terms_quote must quote the line of the terms that allows "
                "this use (at least 20 characters)")
    who = cfg["approved_by"].strip().lower()
    if len(who) < 2 or any(w in who for w in NOT_A_PERSON):
        _refuse("schema_rejected", "approved_by must be the name of the person who read the "
                "terms. An assistant cannot sign off a source.")
    if not TS_RE.match(cfg["approved_utc"]):
        _refuse("schema_rejected", "approved_utc must look like 2026-11-15T05:00:00Z")
    tf = cfg["timeframe_minutes"]
    if isinstance(tf, bool) or not isinstance(tf, int) or tf < 1 or tf > 1440:
        _refuse("schema_rejected", "timeframe_minutes must be a whole number from 1 to 1440")
    if "naive_ts_is_utc" in cfg and cfg["naive_ts_is_utc"] is not True:
        _refuse("schema_rejected", "naive_ts_is_utc, when present, must be true")
    if "daily_open_utc" in cfg and (not isinstance(cfg["daily_open_utc"], str)
                                    or not TOD_RE.match(cfg["daily_open_utc"])):
        _refuse("schema_rejected", "daily_open_utc must look like 14:30:00")
    csv_path = cfg["csv_path"]
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(os.path.dirname(os.path.abspath(path)), csv_path)
    cfg = dict(cfg)
    cfg["csv_path"] = csv_path
    return cfg


def read_csv(cfg, now_utc):
    """Read the CSV named by the source file. Returns (rows, sha256). Any bad row refuses the file."""
    path = cfg["csv_path"]
    if not os.path.isfile(path):
        _refuse("no_source", "the CSV file named in the source file was not found: %s" % path)
    if not path.lower().endswith(".csv"):
        _refuse("schema_rejected", "the real-bar file must be a .csv file")
    with open(path, "rb") as fh:
        raw = fh.read()
    sha = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        _refuse("schema_rejected", "the CSV file is not UTF-8 text")
    first = text.split("\n", 1)[0].strip()
    if provenance._CSV_EXPORT_HEADER.match(first):
        _refuse("tradingview_origin", "the CSV header starts with time,open,high,low,close, "
                "which is the shape of a TradingView chart export. Chart exports are never read.")
    _markers("the CSV file", os.path.basename(path) + "\n" + text)
    reader = csv.reader(io.StringIO(text))
    try:
        header = [c.strip() for c in next(reader)]
    except StopIteration:
        _refuse("schema_rejected", "the CSV file is empty")
    if header not in (CSV_HEADER, CSV_HEADER_ALT):
        _refuse("schema_rejected", "the CSV header must be exactly %s (the first column may "
                "also be named datetime); got %s"
                % (",".join(CSV_HEADER), ",".join(header)[:120]))
    tf = timedelta(minutes=cfg["timeframe_minutes"])
    now = _parse_ts(now_utc)
    rows, prev_close = [], None
    for n, rec in enumerate(reader, start=2):
        if not rec or all(not c.strip() for c in rec):
            continue
        if len(rec) != 6:
            _refuse("schema_rejected", "CSV line %d has %d fields, not 6" % (n, len(rec)))
        ts = rec[0].strip()
        if DATE_RE.match(ts):
            if "daily_open_utc" not in cfg:
                _refuse("schema_rejected", "CSV line %d has a plain date; add daily_open_utc "
                        "(for example 14:30:00) to the source file, or give full UTC times" % n)
            ts = "%sT%sZ" % (ts, cfg["daily_open_utc"])
        elif NAIVE_RE.match(ts):
            if cfg.get("naive_ts_is_utc") is not True:
                _refuse("schema_rejected", "CSV line %d has a time with no zone (%r). If you "
                        "asked the source for UTC times, add \"naive_ts_is_utc\": true to the "
                        "source file; otherwise give UTC times like 2026-11-10T14:30:00Z"
                        % (n, ts))
            ts = "%sT%sZ" % (ts[:10], ts[11:])
        if not TS_RE.match(ts):
            _refuse("schema_rejected", "CSV line %d: ts must be UTC like 2026-11-10T14:30:00Z; "
                    "got %r" % (n, rec[0][:40]))
        try:
            t_open = _parse_ts(ts)
            o, h, l, c, v = [float(x) for x in rec[1:]]
        except ValueError:
            _refuse("schema_rejected", "CSV line %d has a value that is not a date or number" % n)
        if not all(math.isfinite(x) for x in (o, h, l, c, v)) or min(o, h, l, c) <= 0 or v < 0:
            _refuse("schema_rejected", "CSV line %d has a price that is not above zero, or a "
                    "negative volume" % n)
        if h < max(o, c, l) or l > min(o, c):
            _refuse("schema_rejected", "CSV line %d: high or low does not contain the open "
                    "and close" % n)
        t_close = t_open + tf
        if prev_close is not None and t_open < prev_close:
            _refuse("schema_rejected", "CSV line %d opens before the previous bar closed; rows "
                    "must be in time order and must not overlap" % n)
        if t_close > now:
            _refuse("schema_rejected", "CSV line %d is a bar that has not closed yet (it closes "
                    "at %s; the clock is %s). Remove it and run again." % (n, _fmt_ts(t_close), now_utc))
        rows.append({"ts_open": _fmt_ts(t_open), "ts_close": _fmt_ts(t_close),
                     "open": o, "high": h, "low": l, "close": c, "volume": v})
        prev_close = t_close
        if len(rows) > MAX_ROWS:
            _refuse("schema_rejected", "the CSV file has more than %d rows" % MAX_ROWS)
    if not rows:
        _refuse("schema_rejected", "the CSV file has a header but no rows")
    return rows, sha


def convert(source_path, out_dir, now_utc):
    """Check the source, convert its CSV, and write three files in out_dir.

    Returns {"feed", "permitted", "report_path", "report"}. Raises SourceRefused.
    Nothing is written unless every check passes.
    """
    cfg = load_source(source_path)
    rows, sha = read_csv(cfg, now_utc)
    name, sym, tf = cfg["source_name"], cfg["symbol"], cfg["timeframe_minutes"]
    os.makedirs(out_dir, exist_ok=True)
    feed = os.path.join(out_dir, "real_bars.jsonl")
    permitted = os.path.join(out_dir, "permitted_sources.json")
    report_path = os.path.join(out_dir, "last_source.json")
    manifest = {"type": "manifest", "source": name, "generator": "real_feed.py from a CSV file",
                "symbol": sym, "timeframe_minutes": tf, "created_utc": now_utc,
                "note": "REAL BARS, PAPER ONLY. " + DELIVERY_ASSUMPTION}
    lines = [json.dumps(manifest, sort_keys=True)]
    for i, r in enumerate(rows, start=1):
        bar = {"type": "bar", "seq": i, "symbol": sym, "source": name,
               "ts_open": r["ts_open"], "ts_close": r["ts_close"], "delivered_ts": r["ts_close"],
               "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"],
               "volume": r["volume"]}
        lines.append(json.dumps(bar, sort_keys=True))
    with open(permitted, "w", encoding="utf-8") as fh:
        json.dump({"permitted": [{"name": name, "terms_url": cfg["terms_url"],
                                  "terms_quote": cfg["terms_quote"],
                                  "approved_by": cfg["approved_by"],
                                  "approved_utc": cfg["approved_utc"]}]},
                  fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(feed, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    # The runner's own gate must agree before anything is reported as usable.
    chk = provenance.check_feed(feed, permitted)
    if not chk.ok:
        os.remove(feed)
        _refuse(chk.primary_code(), "the converted file did not pass the runner's own check: %s"
                % "; ".join(chk.reasons))
    report = {"schema": REPORT_SCHEMA, "source_name": name, "terms_url": cfg["terms_url"],
              "approved_by": cfg["approved_by"], "approved_utc": cfg["approved_utc"],
              "symbol": sym, "timeframe_minutes": tf, "rows": len(rows),
              "first_ts_open": rows[0]["ts_open"], "last_ts_close": rows[-1]["ts_close"],
              "csv_sha256": sha, "delivery_assumption": DELIVERY_ASSUMPTION,
              "converted_utc": now_utc}
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return {"feed": feed, "permitted": permitted, "report_path": report_path, "report": report}
