"""Provenance gate for the paper runner. Standard library only (Python 3.9).

Policy (binding, see ../RECONCILE.md): nothing that comes from TradingView may
feed this runner. The gate is fail-closed in two layers:

1. A closed schema. A feed must be a JSON Lines file whose first record is a
   manifest naming a source on the permitted list. Every other record must be
   a bar with only the known fields. Anything else rejects the whole file.
2. A marker scan. Any TradingView marker anywhere in the file text, the file
   name, or the declared transport headers rejects the whole file and names
   the marker, so the reason is readable.

A rejected file is never partly processed.
"""
import json
import os
import re

MANIFEST_REQUIRED = ("type", "source", "generator", "symbol", "timeframe_minutes")
MANIFEST_KEYS = set(MANIFEST_REQUIRED) | {
    "seed", "created_utc", "note", "transport", "period",
}
BAR_KEYS = {
    "type", "seq", "symbol", "ts_open", "ts_close", "delivered_ts",
    "open", "high", "low", "close", "volume", "source",
}

# The only source accepted with no further paperwork.
BUILTIN_SOURCES = {"synthetic"}
SYNTHETIC_SYMBOL_PREFIX = "SYNTH-"

# Source addresses TradingView publishes for its webhook alerts
# (support article 43000529348, checked 2026-11-14; see RECONCILE.md).
TV_WEBHOOK_IPS = ("52.89.214.238", "34.212.75.30", "54.218.53.128", "52.32.178.7")

_EXCHANGES = (
    "AMEX|NASDAQ|NYSE|ARCA|BATS|CBOE|CME|CME_MINI|CBOT|NYMEX|COMEX|BINANCE|"
    "COINBASE|BITSTAMP|KRAKEN|BYBIT|OANDA|FX|FX_IDC|FOREXCOM|TVC|CRYPTOCAP|"
    "INDEX|SP|DJ|ECONOMICS|FRED|CAPITALCOM|PEPPERSTONE|KALSHI"
)

# (compiled regex, plain-English label). Case-insensitive unless noted.
TV_MARKERS = [
    (re.compile(r"trading\s*[-_]?\s*view", re.I), "names TradingView"),
    (re.compile(r"(?<![a-z0-9])tv(?![a-z0-9])", re.I), "standalone token 'tv'"),
    (re.compile(r"pine\s*script|(?<![a-z0-9])pine(?![a-z0-9])", re.I), "names Pine"),
    (re.compile(r"\{\{\s*[a-z_.]+\s*\}\}", re.I), "alert placeholder like {{close}}"),
    (re.compile(r"strategy\.(order|position|market_position|prev_market)", re.I),
     "strategy alert field"),
    (re.compile(r"alert[_\s-]?(name|message|id|condition)|alertcondition", re.I),
     "alert field"),
    (re.compile(r"web[-_\s]?hook", re.I), "webhook marker"),
    (re.compile(r"(?<![A-Za-z0-9])(?:%s)\s*[:_]\s*[A-Z0-9.!]{1,15}(?![a-z])" % _EXCHANGES),
     "exchange-prefixed ticker id (EXCHANGE:SYMBOL)"),
    (re.compile("|".join(re.escape(ip) for ip in TV_WEBHOOK_IPS)),
     "TradingView webhook source address"),
]

_CSV_EXPORT_HEADER = re.compile(r"^\s*time\s*,\s*open\s*,\s*high\s*,\s*low\s*,\s*close", re.I)


class ProvenanceResult(object):
    def __init__(self):
        self.ok = False
        self.reasons = []      # list of plain-English strings
        self.manifest = None
        self.records = []      # list of (line_number, dict) for bar records
        self.codes = set()     # tradingview_origin / source_not_permitted / schema_rejected

    def fail(self, reason):
        if reason not in self.reasons:
            self.reasons.append(reason)
        if "TradingView marker" in reason or "chart-export" in reason:
            self.codes.add("tradingview_origin")
        elif "permitted list" in reason:
            self.codes.add("source_not_permitted")
        else:
            self.codes.add("schema_rejected")

    def primary_code(self):
        for code in ("tradingview_origin", "source_not_permitted", "schema_rejected"):
            if code in self.codes:
                return code
        return "schema_rejected"


def scan_text_for_markers(text):
    """Return the labels of every TradingView marker found in text."""
    found = []
    for rx, label in TV_MARKERS:
        m = rx.search(text)
        if m:
            found.append("%s: %r" % (label, m.group(0)[:40]))
    return found


def load_permitted_sources(path):
    """Extra sources need a terms URL, a quote of the terms and a named human
    approver. A source whose own name carries a TradingView marker is refused
    even if someone lists it."""
    permitted = {}
    if not path or not os.path.exists(path):
        return permitted
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    for entry in doc.get("permitted", []):
        name = str(entry.get("name", "")).strip().lower()
        needed = ("terms_url", "terms_quote", "approved_by", "approved_utc")
        if not name or any(not str(entry.get(k, "")).strip() for k in needed):
            continue
        if scan_text_for_markers(json.dumps(entry)):
            continue
        permitted[name] = entry
    return permitted


def check_feed(path, permitted_sources_path=None):
    """Decide whether a feed file may be read. Never raises on bad content."""
    res = ProvenanceResult()
    base = os.path.basename(path)

    for hit in scan_text_for_markers(base):
        res.fail("file name carries a TradingView marker (%s)" % hit)

    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        res.fail("cannot read feed as UTF-8 text: %s" % exc.__class__.__name__)
        return res

    first_line = text.split("\n", 1)[0]
    if _CSV_EXPORT_HEADER.match(first_line):
        res.fail("first line looks like a chart-export CSV header (time,open,high,low,close)")

    for hit in scan_text_for_markers(text):
        res.fail("content carries a TradingView marker (%s)" % hit)

    if not base.lower().endswith(".jsonl"):
        res.fail("not a .jsonl feed with a manifest; only that format is accepted")

    lines = [ln for ln in text.split("\n")]
    parsed = []
    for i, ln in enumerate(lines, start=1):
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            res.fail("line %d is not JSON" % i)
            continue
        if not isinstance(obj, dict):
            res.fail("line %d is not a JSON object" % i)
            continue
        parsed.append((i, obj))

    if res.reasons:
        return res
    if not parsed:
        res.fail("empty feed")
        return res

    line_no, manifest = parsed[0]
    if manifest.get("type") != "manifest":
        res.fail("first record is not a manifest; origin is unknown")
        return res
    unknown = sorted(set(manifest.keys()) - MANIFEST_KEYS)
    if unknown:
        res.fail("manifest has unknown fields %s; the schema is closed" % unknown)
    for k in MANIFEST_REQUIRED:
        if k not in manifest:
            res.fail("manifest is missing %r" % k)
    source = str(manifest.get("source", "")).strip().lower()
    permitted = set(BUILTIN_SOURCES)
    permitted |= set(load_permitted_sources(permitted_sources_path).keys())
    if source not in permitted:
        res.fail("source %r is not on the permitted list %s" % (source, sorted(permitted)))
    symbol = manifest.get("symbol")
    if source == "synthetic" and not (isinstance(symbol, str)
                                      and symbol.startswith(SYNTHETIC_SYMBOL_PREFIX)):
        res.fail("a synthetic feed must use a %s* symbol, got %r"
                 % (SYNTHETIC_SYMBOL_PREFIX, symbol))
    transport = manifest.get("transport")
    if transport is not None:
        for hit in scan_text_for_markers(json.dumps(transport)):
            res.fail("transport metadata carries a TradingView marker (%s)" % hit)
        if source == "synthetic":
            res.fail("a synthetic feed cannot have arrived over a transport; got transport metadata")

    for i, obj in parsed[1:]:
        if obj.get("type") != "bar":
            res.fail("line %d has record type %r; only 'bar' is accepted" % (i, obj.get("type")))
            continue
        unknown = sorted(set(obj.keys()) - BAR_KEYS)
        if unknown:
            res.fail("line %d has unknown fields %s; the schema is closed" % (i, unknown))
        if "source" in obj and str(obj.get("source")).strip().lower() != source:
            res.fail("line %d source %r differs from the manifest" % (i, obj.get("source")))
        if "symbol" in obj and obj.get("symbol") != symbol:
            res.fail("line %d symbol %r differs from the manifest" % (i, obj.get("symbol")))
        res.records.append((i, obj))

    if res.reasons:
        res.records = []
        return res
    res.ok = True
    res.manifest = manifest
    return res
