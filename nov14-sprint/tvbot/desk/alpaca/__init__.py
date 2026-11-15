"""Alpaca PAPER adapter for the paper desk (opt-in, SPY only, free IEX data only).

Shared constants. Every module in this package imports from here so the fixed
hosts, symbol, feed and evidence labels cannot drift. See CONTRACT.md.

Nothing in this package is imported by the default offline desk. The adapter is
used only when the launcher is started with --broker alpaca-paper.
"""

# Fixed origins. The ONLY two hosts the real transport may ever contact.
TRADING_ORIGIN = "https://paper-api.alpaca.markets"
DATA_ORIGIN = "https://data.alpaca.markets"
ORIGINS = {"trading": TRADING_ORIGIN, "data": DATA_ORIGIN}
# Explicitly refused even if someone edits ORIGINS: the live-money trading host.
REFUSED_HOSTS = ("api.alpaca.markets",)
API_PREFIX = "/v2/"

SYMBOL = "SPY"
FEED = "iex"                 # free IEX feed only; "sip" (paid) is refused
ORDER_TYPES = ("market", "limit", "stop")
TIME_IN_FORCE = "day"

# Evidence labels. Every order, fill, event and UI banner carries exactly one.
LABEL_ALPACA_PAPER = "ALPACA PAPER (Alpaca's simulated paper account; no real money)"
LABEL_INJECTED = "INJECTED TRANSPORT (synthetic ids, no network)"
LABEL_MOCK_LOCAL = "MOCK LOCAL (in-process fake Alpaca; synthetic ids and bars)"
LABEL_OFFLINE_FAKE = "FakeBroker (offline, in-process)"
DATA_LABEL_IEX = "ALPACA IEX (free feed; IEX-only volume, not consolidated)"
DATA_LABEL_MOCK = "MOCK IEX BARS (synthetic, no market data)"

STATE_FILE = "alpaca_paper.json"   # persisted enable/disabled state, inside the desk state dir
