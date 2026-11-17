"""Read-only checks for an operator's first SPY paper connection.

The command reads an approved limits snapshot before constructing a credentials provider.
A successful check makes four GET requests. It returns no account identifiers, balances or raw API errors.
After an explicit operator action, the desk may also call read_quote with its existing
transport to inspect the IEX top of book. A quote from IEX is a single-venue observation.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alpaca import FEED, SYMBOL
from alpaca.feed import parse_rfc3339
from alpaca.transport import TransportRefused

# Execution freshness policy for each manually requested quote, in seconds.
try:
    from alpaca.trading_profile import MAX_QUOTE_AGE_S as MAX_QUOTE_AGE   # Balanced pace
except ImportError:   # run as a script from alpaca/
    from trading_profile import MAX_QUOTE_AGE_S as MAX_QUOTE_AGE
FUTURE_TOLERANCE = 2
MAX_CLOCK_SKEW = 60

def _timestamp(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        # Alpaca sends RFC 3339 with up to nine fraction digits; Python 3.9's
        # fromisoformat rejects those, so the feed's parser goes first.
        try:
            dt = parse_rfc3339(value)
        except ValueError:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("missing timestamp")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp has no time zone")
    return dt.astimezone(timezone.utc)

def _price(value):
    if isinstance(value, bool):
        raise ValueError("invalid price")
    n = Decimal(str(value))
    if not n.is_finite() or n <= 0 or n > Decimal("1000000000"):
        raise ValueError("invalid price")
    return n

def _get(transport, origin, path, query=None):
    try:
        status, payload = transport.request("GET", origin, path, query=query)
    except TransportRefused as exc:
        # Never return arbitrary exception text, even if a remote service echoed it.
        if not exc.sent and str(exc) in {"credentials unavailable from provider", "invalid credentials"}:
            return None, "PAPER_CREDENTIALS_UNAVAILABLE"
        return None, "REQUEST_REFUSED"
    except Exception:
        return None, "REQUEST_FAILED"
    if status != 200:
        known = {401: "AUTHENTICATION_FAILED", 403: "FORBIDDEN", 404: "UNAVAILABLE",
                 429: "RATE_LIMITED"}
        return None, known.get(status, "HTTP_ERROR")
    if not isinstance(payload, dict):
        return None, "INVALID_RESPONSE"
    return payload, None

def read_quote(transport, now=None):
    """Return valid, fresh, bid, ask, spread_usd/bps and age_s for the pinned free feed.

    All outputs are JSON-safe. A stale or future observation is never fresh. A crossed
    market or malformed payload is invalid. Never substitute a paid or delayed feed.
    """
    out = {"feed": FEED, "symbol": SYMBOL, "valid": False, "fresh": False,
           "reason": None, "bid": None, "ask": None, "spread_usd": None,
           "spread_bps": None, "quote_utc": None, "age_s": None}
    payload, error = _get(transport, "data", "/v2/stocks/SPY/quotes/latest", {"feed": FEED})
    if error:
        out["reason"] = error
        return out
    if payload.get("symbol") != SYMBOL or not isinstance(payload.get("quote"), dict):
        out["reason"] = "SYMBOL_OR_QUOTE_MISMATCH"
        return out
    quote = payload["quote"]
    try:
        observed = _timestamp(quote.get("t"))
        when = _timestamp(now if now is not None else datetime.now(timezone.utc))
        bid, ask = _price(quote.get("bp")), _price(quote.get("ap"))
        _price(quote.get("bs"))
        _price(quote.get("as"))
        age = (when-observed).total_seconds()
    except (ArithmeticError, TypeError, ValueError, OverflowError):
        out["reason"] = "INVALID_QUOTE"
        return out
    if ask < bid:
        out["reason"] = "CROSSED_QUOTE"
        return out
    spread = ask - bid
    out.update(valid=True, bid=float(bid), ask=float(ask), spread_usd=float(spread),
               spread_bps=float(10000*spread/((bid+ask)/2)),
               quote_utc=observed.isoformat(), age_s=round(age, 3))
    if age < -FUTURE_TOLERANCE:
        out["reason"] = "FUTURE_QUOTE"
    elif age > MAX_QUOTE_AGE:
        out["reason"] = "STALE_QUOTE"
    else:
        out.update(fresh=True, reason="FRESH")
    return out

def check_connection(transport, now=None):
    """Inspect read-only connectivity separately from current market conditions."""
    account, aerr = _get(transport, "trading", "/v2/account")
    if aerr:
        # A bad credential or unavailable paper host should prompt for the provider only once.
        return {"mode": "Alpaca paper / read only", "symbol": SYMBOL, "feed": FEED,
                "connection_verified": False, "account_allows_trading": False,
                "spy_tradable": None, "market_open": None, "clock_skew_s": None,
                "quote": None, "market_conditions_ready": False, "reasons": [aerr]}
    asset, serr = _get(transport, "trading", "/v2/assets/SPY")
    clock, cerr = _get(transport, "trading", "/v2/clock")
    account = account or {}
    asset = asset or {}
    clock = clock or {}
    flags = [account.get("trading_blocked"), account.get("account_blocked")]
    account_known = bool(account.get("status")) and all(isinstance(x, bool) for x in flags)
    account_ready = (account_known and account.get("status") == "ACTIVE" and
                     not any(flags) and account.get("trade_suspended_by_user") is not True)
    asset_known = asset.get("symbol") == SYMBOL and isinstance(asset.get("tradable"), bool)
    asset_ready = asset_known and asset.get("status") == "active" and asset.get("tradable") is True
    host_time = _timestamp(now) if now is not None else datetime.now(timezone.utc)
    clock_ok = isinstance(clock.get("is_open"), bool)
    clock_skew = None
    try:
        venue_time = _timestamp(clock.get("timestamp"))
        clock_skew = (host_time-venue_time).total_seconds()
    except (TypeError, ValueError, OverflowError):
        clock_ok = False
        venue_time = host_time
    quote = read_quote(transport, venue_time)
    connected = bool(account_known and asset_known and clock_ok and quote["valid"])
    reasons = []
    if not account_ready:
        reasons.append(aerr or "ACCOUNT_BLOCKED_OR_UNVERIFIED")
    if not asset_ready:
        reasons.append(serr or "SPY_NOT_TRADABLE_OR_UNVERIFIED")
    if not clock_ok:
        reasons.append(cerr or "INVALID_MARKET_CLOCK")
    elif abs(clock_skew) > MAX_CLOCK_SKEW:
        reasons.append("MARKET_CLOCK_SKEW")
    if clock_ok and not clock["is_open"]:
        reasons.append("MARKET_CLOSED")
    if not quote["fresh"]:
        reasons.append(quote["reason"])
    return {"mode": "Alpaca paper / read only", "symbol": SYMBOL, "feed": FEED,
            "connection_verified": connected, "account_allows_trading": account_ready,
            "spy_tradable": asset_ready, "market_open": clock.get("is_open") if clock_ok else None,
            "clock_skew_s": round(clock_skew,3) if clock_skew is not None else None,
            "quote": quote, "market_conditions_ready": not reasons, "reasons": reasons}

def format_result(result):
    """A brief operator readout. Machine-readable output is available with --json."""
    if not result["connection_verified"]:
        headline = "The SPY paper connection could not be fully verified."
    elif result["market_conditions_ready"]:
        headline = "SPY paper connection verified. The market is open and the IEX quote is fresh."
    else:
        headline = "SPY paper connection verified. Current market conditions do not support a new entry."
    lines = [headline, "This check used read-only requests. No order was submitted."]
    quote = result.get("quote") or {}
    if quote.get("valid"):
        lines.append("IEX bid $%.2f / ask $%.2f | spread $%.2f (%.2f bps) | quote age %.1f seconds" %
                     (quote["bid"],quote["ask"],quote["spread_usd"],quote["spread_bps"],quote["age_s"]))
    if result["reasons"]:
        lines.append("Checks: " + ", ".join(tag.replace("_", " ").lower() for tag in result["reasons"]))
    if "PAPER_CREDENTIALS_UNAVAILABLE" in result["reasons"]:
        lines.append("Check the paper key pair in the selected provider. The setup guide lists the Keychain item names.")
    return "\n".join(lines)

def main(argv=None):
    from alpaca.setup import EnvProvider, KeychainProvider
    from alpaca.sizing import LimitsError, load_limits
    from alpaca.transport import HttpsTransport
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state-dir", required=True, help="State directory containing the approved snapshot")
    ap.add_argument("--limits", help="Explicit approved snapshot from the local sizing worksheet")
    ap.add_argument("--provider", choices=("keychain","env"), default="keychain")
    ap.add_argument("--json", action="store_true", help="Show the machine-readable result")
    args = ap.parse_args(argv)
    try:
        load_limits(path=args.limits, state_dir=args.state_dir, allow_draft=False)
    except (LimitsError, OSError, ValueError):
        print("An operator-approved limits snapshot is required. Open the sizing worksheet first.",file=sys.stderr)
        return 2
    provider = KeychainProvider() if args.provider == "keychain" else EnvProvider()
    result = check_connection(HttpsTransport(provider))
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else format_result(result))
    return 0 if result["connection_verified"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
