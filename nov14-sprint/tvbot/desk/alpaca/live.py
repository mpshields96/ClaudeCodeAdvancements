"""LIVE-money Alpaca separation. OFF by default; nothing in the paper path can reach it.

What is separate from paper, and how:
- Host: live trading is https://api.alpaca.markets (Alpaca docs, "Paper Trading": the paper host is
  paper-api.alpaca.markets and paper keys differ from live keys). LIVE_ORIGINS are frozen at import here;
  the paper transport (alpaca/transport.py) refuses api.alpaca.markets outright, and the live transport
  below refuses paper-api.alpaca.markets outright. Market data uses the same data host for both.
- Keys: live keys live under the Keychain service "alpaca-live" (accounts "key-id", "secret-key") or the
  environment variables ALPACA_LIVE_API_KEY_ID / ALPACA_LIVE_API_SECRET_KEY. Paper providers refuse those
  names (alpaca/setup.py); live providers refuse the paper ones. Each provider declares a mode, and each
  transport refuses a provider of the other mode. Key-id prefixes (paper PK, live AK) are refused across
  modes too, but Alpaca calls the prefix a hint; the host is the real boundary.
- State and port: state-alpaca-live/ and port 8795 only, never the paper state dirs. Every paper and
  rehearsal port is refused, including each one's fallback ports (8765-8784, 18855-18874, 18858-18877),
  as are port 0 and anything outside 1-65535. Live binds its one port exactly and never moves to another.
- Activation: only through the distinct command alpaca/live_launch.py, every session: an operator-approved
  limits snapshot stored inside the live state dir and approved there, a real terminal, and a typed phrase
  that names today's date and the share count. LiveHttpsTransport cannot be built without the
  LiveAuthorization that gate mints. No URL, flag or argument on the paper path selects any of this.

Nothing here reads a key or opens a socket at import or construction time. Tests inject openers.
"""
import copy
import datetime as _dt
import os
import subprocess
import urllib.parse

from alpaca import DATA_ORIGIN
from alpaca.setup import (CredentialsError, LIVE_ENV_KEY_VAR, LIVE_ENV_SECRET_VAR, LIVE_KEYCHAIN_SERVICE,
                          ENV_KEY_VAR, ENV_SECRET_VAR, KEYCHAIN_SERVICE, SECURITY_BIN,
                          KEYCHAIN_KEY_ACCOUNT, KEYCHAIN_SECRET_ACCOUNT)
from alpaca.state import AdapterState
from alpaca.transport import HttpsTransport, TransportRefused

LIVE_TRADING_ORIGIN = "https://api.alpaca.markets"
LIVE_ORIGINS = {"trading": LIVE_TRADING_ORIGIN, "data": DATA_ORIGIN}
_LIVE_FIXED = dict(LIVE_ORIGINS)                  # frozen at import; later edits are refused
LIVE_REFUSED_HOSTS = ("paper-api.alpaca.markets",)
PAPER_KEY_PREFIXES = ("PK",)

LIVE_STATE_DIRNAME = "state-alpaca-live"
LIVE_STATE_FILE = "alpaca_live.json"
LIVE_PORT = 8795
PAPER_PORT = 8765                                 # launch.DEFAULT_PORT; a live session never uses it
INSTALLED_MOCK_PORT = 18855                       # the installed rehearsal (mock) desk's URL
INSTALLED_PAPER_PORT = 18858                      # after-approval/Open Connected Paper Desk.command
FREE_PORT_TRIES = 20                              # launch.free_port(tries=20): preferred port + 19 more
NON_LIVE_PREFERRED_PORTS = ((PAPER_PORT, "paper desk"), (INSTALLED_MOCK_PORT, "installed rehearsal desk"),
                            (INSTALLED_PAPER_PORT, "installed paper desk"))
PAPER_STATE_DIRNAMES = ("state", "state-alpaca-paper", "state-alpaca-mock")
LIVE_APPROVER = "operator via live_launch approve-limits"
LIVE_CONFIRM_LIMITS = "APPROVE LIVE LIMITS"
LABEL_ALPACA_LIVE = "ALPACA LIVE (REAL MONEY in your Alpaca live brokerage account)"
AUTH_MAX_AGE_S = 16 * 3600                        # one session; a new day needs a new typed phrase


class LiveAdapterState(AdapterState):
    """The live adapter's on/off state, in <state-alpaca-live>/alpaca_live.json. It never writes
    alpaca_paper.json, which the live gate refuses to find in a live folder."""
    FILE = LIVE_STATE_FILE


def check_live_key_id(key_id):
    if not isinstance(key_id, str) or not key_id.strip():
        raise CredentialsError("the live key id is empty")
    if key_id != key_id.strip() or any(c.isspace() for c in key_id):
        raise CredentialsError("the live key id contains spaces or line breaks")
    if key_id.upper().startswith(PAPER_KEY_PREFIXES):
        raise CredentialsError("this key id looks like a PAPER key (it starts with PK); live needs live keys")
    return key_id


def _check_live_secret(secret):
    if not isinstance(secret, str) or not secret.strip() or any(c.isspace() for c in secret):
        raise CredentialsError("the live secret key is empty or contains spaces or line breaks")
    return secret


def _default_runner(argv):
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          universal_newlines=True, timeout=15, check=False)
    return proc.returncode, proc.stdout


class LiveKeychainProvider(object):
    """Live keys from Keychain service "alpaca-live". Read only inside get(). The service is fixed."""

    mode = "live"

    def __init__(self, runner=None):
        self.service = LIVE_KEYCHAIN_SERVICE
        assert self.service != KEYCHAIN_SERVICE
        self._runner = runner

    def _read(self, account):
        argv = [SECURITY_BIN, "find-generic-password", "-s", self.service, "-a", account, "-w"]
        try:
            code, out = (self._runner or _default_runner)(argv)
        except (OSError, subprocess.SubprocessError):
            raise CredentialsError("could not run %s for the live Keychain item" % SECURITY_BIN) from None
        if code != 0:
            raise CredentialsError("live Keychain item %s / %s not found or access denied" % (self.service, account))
        return (out or "").rstrip("\r\n")

    def get(self):
        return (check_live_key_id(self._read(KEYCHAIN_KEY_ACCOUNT)),
                _check_live_secret(self._read(KEYCHAIN_SECRET_ACCOUNT)))

    def describe(self):
        return "macOS Keychain service '%s' (LIVE keys); read only when a live session sends" % self.service

    def __repr__(self):
        return "LiveKeychainProvider(service=%r)" % self.service


class LiveEnvProvider(object):
    """Live keys from ALPACA_LIVE_API_KEY_ID / ALPACA_LIVE_API_SECRET_KEY, read only inside get()."""

    mode = "live"

    def __init__(self, environ=None):
        self._environ = environ
        self.key_var, self.secret_var = LIVE_ENV_KEY_VAR, LIVE_ENV_SECRET_VAR
        assert self.key_var not in (ENV_KEY_VAR, ENV_SECRET_VAR)

    def get(self):
        env = self._environ if self._environ is not None else os.environ
        key_id, secret = env.get(self.key_var), env.get(self.secret_var)
        if not key_id or not secret:
            raise CredentialsError("%s / %s are not set" % (self.key_var, self.secret_var))
        return check_live_key_id(key_id), _check_live_secret(secret)

    def describe(self):
        return "environment variables %s and %s (LIVE keys)" % (self.key_var, self.secret_var)

    def __repr__(self):
        return "LiveEnvProvider(%s, %s)" % (self.key_var, self.secret_var)


LIVE_PROVIDERS = {"keychain": LiveKeychainProvider, "env": LiveEnvProvider}


def make_live_provider(kind="keychain", **kwargs):
    try:
        return LIVE_PROVIDERS[kind](**kwargs)
    except KeyError:
        raise CredentialsError("unknown live credentials source; use keychain or env") from None


def resolve_live_origin(origin_key):
    if origin_key not in ("trading", "data"):
        raise TransportRefused("unknown origin key")
    origin = LIVE_ORIGINS.get(origin_key)
    if not isinstance(origin, str):
        raise TransportRefused("origin missing")
    parts = urllib.parse.urlsplit(origin)
    host = (parts.hostname or "").lower()
    if host in LIVE_REFUSED_HOSTS:
        raise TransportRefused("refused host (paper host on the live transport)")
    if origin != _LIVE_FIXED.get(origin_key):
        raise TransportRefused("origin differs from the fixed live/data origin")
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443) \
            or parts.path not in ("", "/") or parts.query or parts.fragment:
        raise TransportRefused("origin must be a bare https host on the default port")
    return origin.rstrip("/"), host


_MINT = object()        # only live_gate_authorize() holds this; LiveAuthorization refuses anything else


class LiveAuthorization(object):
    """Proof that this session passed the live gate. Minted only by live_gate_authorize()."""

    def __init__(self, mint, session_date, shares, limits_hash, state_dir, issued_monotonic, limits=None):
        if mint is not _MINT:
            raise TransportRefused("a live authorization can only come from the live gate")
        self.session_date = session_date
        self.shares = shares
        self.limits_hash = limits_hash
        # The exact approved snapshot the operator saw and confirmed. A controller must use these
        # values, not re-read the file (the 02:40Z binding finding).
        self.limits = copy.deepcopy(limits) if limits is not None else None
        self.state_dir = state_dir
        self.issued_monotonic = issued_monotonic

    def valid(self, now_monotonic):
        return 0 <= now_monotonic - self.issued_monotonic <= AUTH_MAX_AGE_S

    def __repr__(self):
        return "LiveAuthorization(%s, %d shares)" % (self.session_date, self.shares)


class LiveHttpsTransport(HttpsTransport):
    """The LIVE transport. Same request rules as paper, its own frozen origins, live-mode keys only,
    and a LiveAuthorization from this session's gate."""

    MODE = "live"
    USER_AGENT = "paper-desk-alpaca-live/1"
    REFUSED_KEY_PREFIXES = PAPER_KEY_PREFIXES

    def __init__(self, credentials_provider, authorization, timeout_s=10, opener=None, monotonic=None):
        import time
        self._monotonic = monotonic or time.monotonic
        if not isinstance(authorization, LiveAuthorization) or not authorization.valid(self._monotonic()):
            raise TransportRefused("no valid live authorization for this session; run alpaca/live_launch.py")
        self.authorization = authorization
        HttpsTransport.__init__(self, credentials_provider, timeout_s=timeout_s, opener=opener)

    def _origins(self):
        return _LIVE_FIXED

    def _resolve(self, origin_key):
        if not self.authorization.valid(self._monotonic()):
            raise TransportRefused("live authorization expired; run the live gate again")
        return resolve_live_origin(origin_key)


# ---- the per-session gate (pure checks; reads files only; no keys, no sockets) ----

class LiveGateRefused(Exception):
    pass


def session_date(now_utc=None):
    """Today's date on the desk's calendar clock (America/Chicago, the CT clock the calendar uses)."""
    from zoneinfo import ZoneInfo
    now_utc = now_utc or _dt.datetime.now(_dt.timezone.utc)
    return now_utc.astimezone(ZoneInfo("America/Chicago")).date().isoformat()


def confirm_phrase(shares, date_str):
    return "LIVE SPY %d SHARES %s" % (int(shares), date_str)


def check_live_state_dir(state_dir):
    path = os.path.abspath(state_dir)
    if os.path.basename(path.rstrip(os.sep)) != LIVE_STATE_DIRNAME:
        raise LiveGateRefused("the live state dir must be named %s (paper state dirs are refused)"
                              % LIVE_STATE_DIRNAME)
    if os.path.exists(os.path.join(path, "alpaca_paper.json")):
        raise LiveGateRefused("that folder holds paper adapter state; live needs its own folder")
    return path


def non_live_port_ranges():
    """(first, last, name) for every port a paper or rehearsal desk can serve on: each preferred port
    plus launch.free_port's fallback attempts. Live refuses all of them."""
    return tuple((p, p + FREE_PORT_TRIES - 1, name) for p, name in NON_LIVE_PREFERRED_PORTS)


def check_live_port(port):
    """The live desk serves only on its own port. Refused: anything that is not a whole number in
    1-65535 (port 0 would let the system pick one), and every paper or rehearsal port including the
    fallback ports a paper launcher may move to. Live never falls back to another port."""
    if isinstance(port, bool) or not isinstance(port, int):
        raise LiveGateRefused("the live port must be a whole number, got %r" % (port,))
    if not 1 <= port <= 65535:
        raise LiveGateRefused("port %d is outside 1-65535; live uses its own fixed port (%d)" % (port, LIVE_PORT))
    for first, last, name in non_live_port_ranges():
        if first <= port <= last:
            raise LiveGateRefused("port %d is in the %s range (%d-%d, including its fallback ports); "
                                  "live uses its own (%d)" % (port, name, first, last, LIVE_PORT))
    return port


def bind_live_port_exactly(port, host="127.0.0.1"):
    """Bind the checked live port or refuse. Never tries another port (unlike launch.free_port).
    Returns the bound socket; the caller owns it."""
    import socket
    port = check_live_port(port)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
    except OSError as e:
        s.close()
        raise LiveGateRefused("live port %d is in use (%s); live does not move to another port. "
                              "Stop whatever holds it first" % (port, e.strerror or e))
    return s


def check_live_limits(limits_path, state_dir):
    """The limits must be an operator-approved snapshot inside the live state dir, approved there by
    live_launch approve-limits. Returns the load_limits() dict."""
    from alpaca import sizing
    if not limits_path:
        raise LiveGateRefused("--limits is required: your approved LIVE limits (see LIVE_READINESS.md)")
    real = os.path.realpath(limits_path)
    root = os.path.realpath(state_dir)
    if os.path.commonpath([real, root]) != root:
        raise LiveGateRefused("live limits must be stored inside %s; a paper limits file is refused"
                              % LIVE_STATE_DIRNAME)
    try:
        loaded = sizing.load_limits(path=real, allow_draft=False)
    except sizing.LimitsError as e:
        raise LiveGateRefused("live limits refused: %s" % e) from None
    obj, _ = sizing._read_json(real)
    if (obj or {}).get("by") != LIVE_APPROVER:
        raise LiveGateRefused("these limits were not approved with live_launch approve-limits; "
                              "a copied paper approval is refused")
    return loaded


def live_gate_authorize(limits_path, state_dir, port, typed, stdin_is_tty, now_utc=None, monotonic=None,
                        shown_hash=None):
    """Every check, in order, before anything else happens. Returns a LiveAuthorization or raises
    LiveGateRefused. Reads only the limits file; never a key, never the network.

    shown_hash is the full approval-record hash of the limits the operator was shown before typing.
    It is required: if the file now holds any other approval (swapped or re-approved while the prompt
    was open), nothing is authorized. The authorization carries that exact snapshot."""
    import time
    state_dir = check_live_state_dir(state_dir)
    check_live_port(port)
    if not shown_hash:
        raise LiveGateRefused("the limits shown to you before confirming are required (shown_hash)")
    loaded = check_live_limits(limits_path, state_dir)
    if loaded.get("hash") != shown_hash:
        raise LiveGateRefused("the limits file changed while you were confirming; nothing was authorized. "
                              "Run start again and check the limits it shows")
    if not stdin_is_tty:
        raise LiveGateRefused("the live confirmation must be typed at a terminal (piped input refused)")
    shares = int(loaded["values"]["fixed_shares"])
    today = session_date(now_utc)
    want = confirm_phrase(shares, today)
    if (typed or "").strip() != want:
        raise LiveGateRefused("confirmation did not match; type exactly: %s" % want)
    return LiveAuthorization(_MINT, today, shares, loaded["hash"], state_dir,
                             (monotonic or time.monotonic)(), limits=loaded)
