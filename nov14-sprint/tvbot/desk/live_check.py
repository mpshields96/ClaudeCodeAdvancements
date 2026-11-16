"""Operator's read-only SPY connection check for an Alpaca live account."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

DESK = Path(__file__).resolve().parent
if __name__ == "__main__":
    sys.path.insert(0, str(DESK))

from alpaca import FEED, live, readiness, sizing
from alpaca.setup import CredentialsError
from alpaca.sessions import classify
from alpaca.transport import TransportRefused
from orders.calendar import SessionCalendar

QUOTE_PATH = "/v2/stocks/SPY/quotes/latest"
TRADING_READS = {"/v2/account", "/v2/assets/SPY", "/v2/clock"}


class ReadOnlyLiveTransport(live.LiveHttpsTransport):
    """Limit this process to the four requests in the connection check."""

    def request(self, method, origin_key, path, query=None, body=None):
        trading_read = origin_key == "trading" and path in TRADING_READS and not query
        quote_read = origin_key == "data" and path == QUOTE_PATH and query == {"feed": FEED}
        if method != "GET" or body is not None or not (trading_read or quote_read):
            raise TransportRefused("outside the four read-only connection checks")
        return super().request(method, origin_key, path, query=query)


def format_result(result, session):
    def label(flag, yes, no):
        return {True: yes, False: no}.get(flag, "unverified")

    verified = result["connection_verified"]
    lines = ["Live account connection " + ("verified." if verified else "incomplete."),
             "Account trading permission: " + label(result["account_allows_trading"], "active", "blocked or unverified"),
             "SPY tradability: " + label(result["spy_tradable"], "tradable", "unavailable or unverified"),
             "Regular-session broker clock: " + label(result["market_open"], "open", "closed"),
             "Local session: " + session["session"].lower().replace("_", " ")]
    quote = result.get("quote")
    if quote and quote["valid"]:
        lines.append("Latest IEX bid / ask: {:.2f} / {:.2f} USD, observed {}".format(
            quote["bid"], quote["ask"], quote["quote_utc"]))
    reasons = ["LIVE_CREDENTIALS_UNAVAILABLE" if r == "PAPER_CREDENTIALS_UNAVAILABLE" else r
               for r in result["reasons"]]
    if not session["desk_supported"]:
        reasons.append("OUTSIDE_REGULAR_SESSION")
    if reasons:
        lines.append("Check details: " + ", ".join(reasons))
    else:
        lines.append("The clock, account, SPY and quote passed this connection check.")
    lines.append("The check is complete. Trading remains a separate operator action.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=DESK / live.LIVE_STATE_DIRNAME)
    parser.add_argument("--limits", type=Path, help="approved live snapshot in the live state folder")
    parser.add_argument("--provider", choices=sorted(live.LIVE_PROVIDERS), default="keychain")
    args = parser.parse_args(argv)
    try:
        state_dir = live.check_live_state_dir(str(args.state_dir))
        limits_path = str(args.limits or sizing.approved_path(state_dir))
        shown = live.check_live_limits(limits_path, state_dir)
        if not sys.stdin.isatty():
            raise live.LiveGateRefused("start the connection check from a terminal")
        values = shown["values"]
        phrase = live.confirm_phrase(values["fixed_shares"], live.session_date())
        print("Alpaca live account · read-only connection check")
        print("Checks account eligibility, SPY, the venue clock and the latest free IEX quote.")
        print("The check uses GET requests only.")
        print("Reviewed live limits: {} shares, ${:,.2f} per order, ${:,.2f} risk per trade, "
              "${:,.2f} total exposure, ${:,.2f} daily loss.".format(
                  values["fixed_shares"], values["per_trade_notional"], values["max_loss_per_trade"],
                  values["gross_exposure"], values["daily_loss"]))
        print("To run the four reads, type {}.".format(phrase))
        typed = input("> ")
        auth = live.live_gate_authorize(limits_path, state_dir, live.LIVE_PORT, typed,
                                        sys.stdin.isatty(), shown_hash=shown["hash"])
    except (live.LiveGateRefused, EOFError, KeyboardInterrupt) as exc:
        print("Connection check stopped before contacting Alpaca. " + str(exc), file=sys.stderr)
        return 2
    try:
        transport = ReadOnlyLiveTransport(live.make_live_provider(args.provider), auth)
    except (TransportRefused, CredentialsError, OSError):
        print("Could not initialize the live connection. Check the live credential provider.", file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc)
    result = readiness.check_connection(transport, now=now)
    session = classify(now, SessionCalendar())
    print(format_result(result, session))
    return 0 if result["connection_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
