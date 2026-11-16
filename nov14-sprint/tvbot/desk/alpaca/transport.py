"""HTTPS transport for the Alpaca PAPER adapter (CONTRACT.md section 1).

One call shape:  request(method, origin_key, path, query=None, body=None) -> (status, payload)

Rules this module enforces, whatever the caller passes:
- Only the fixed origins in alpaca.ORIGINS ("trading" = paper host, "data" = market data host).
  A host in REFUSED_HOSTS (the live-money host) is refused even if ORIGINS were edited, and a host
  that differs from the import-time fixed set is refused too.
- Every redirect is refused. The final response URL must be on the requested host.
- Paths are strict: start with /v2/, a small character set, no "://", "@", "..", "\\", whitespace,
  control chars, "?", "#" or "%". Query values are urlencoded here, never by callers.
- Data requests may only use feed=iex (the free feed). Any other feed, or a paid-route parameter,
  is refused before anything is sent.
- TLS verification stays on (default context). Environment proxies are ignored.
- Credentials come from the provider on every request and go only into the two Alpaca auth headers.
  They never appear in repr, exception text or logs.

Error mapping: timeouts, connection errors and 5xx on POST raise BrokerUncertain (an order may exist);
on GET/DELETE they raise BrokerOutage. Any 4xx returns (status, payload) for the caller to map.

Tests inject an `opener` (an object with .open(request, timeout=...)); no test opens a socket.
"""
import http.client
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

from alpaca import API_PREFIX, FEED, ORIGINS, REFUSED_HOSTS
from orders.fake_broker import BrokerOutage, BrokerUncertain

# Auth header names (Alpaca Trading API docs, "Authentication").
HEADER_KEY_ID = "APCA-API-KEY-ID"
HEADER_SECRET = "APCA-API-SECRET-KEY"
USER_AGENT = "paper-desk-alpaca-paper/1"
METHODS = ("GET", "POST", "DELETE")

_FIXED_ORIGINS = dict(ORIGINS)          # frozen at import; later edits to ORIGINS are refused
_PATH_RE = re.compile(r"^/v2/[A-Za-z0-9/_\-.:]*$")
_QUERY_KEY_RE = re.compile(r"^[a-z_]{1,40}$")
_PAID_DATA_PARAMS = ("sip", "otc", "boats", "overnight")


class TransportRefused(Exception):
    """The transport refused a request. `sent` says whether anything reached a server."""

    def __init__(self, message, sent=False):
        Exception.__init__(self, message)
        self.sent = bool(sent)


def _host_of(origin):
    p = urllib.parse.urlsplit(origin)
    return p, (p.hostname or "").lower()


def resolve_origin(origin_key):
    """Return (origin, host) for a fixed origin key, or raise TransportRefused."""
    if origin_key not in ("trading", "data"):
        raise TransportRefused("unknown origin key")
    origin = ORIGINS.get(origin_key)
    if not isinstance(origin, str):
        raise TransportRefused("origin missing")
    parts, host = _host_of(origin)
    if host in REFUSED_HOSTS or any(host == h.lower() for h in REFUSED_HOSTS):
        raise TransportRefused("refused host (live-money trading host)")
    if origin != _FIXED_ORIGINS.get(origin_key):
        raise TransportRefused("origin differs from the fixed paper/data origin")
    if parts.scheme != "https" or parts.username or parts.password or parts.port not in (None, 443):
        raise TransportRefused("origin must be plain https on the default port")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise TransportRefused("origin must be a bare host")
    return origin.rstrip("/"), host


def validate_path(path):
    if not isinstance(path, str) or not path.startswith(API_PREFIX):
        raise TransportRefused("path must start with /v2/")
    for bad in ("://", "@", "..", "\\", "?", "#", "%"):
        if bad in path:
            raise TransportRefused("path contains a refused sequence")
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) >= 0x7f for ch in path):
        raise TransportRefused("path contains whitespace or control characters")
    if not _PATH_RE.match(path):
        raise TransportRefused("path contains a refused character")
    return path


def encode_query(origin_key, query):
    if not query:
        return ""
    if not isinstance(query, dict):
        raise TransportRefused("query must be a dict")
    pairs = []
    for k in sorted(query):
        v = query[k]
        if not isinstance(k, str) or not _QUERY_KEY_RE.match(k):
            raise TransportRefused("query key refused")
        if isinstance(v, bool):
            v = "true" if v else "false"
        elif isinstance(v, (int, float)):
            v = str(v)
        elif not isinstance(v, str):
            raise TransportRefused("query value must be a string or number")
        if any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in v):
            raise TransportRefused("query value contains control characters")
        pairs.append((k, v))
    if origin_key == "data":
        check_data_query(dict(pairs))
    return urllib.parse.urlencode(pairs)


def check_data_query(query):
    """Free IEX only: a feed other than iex, or a paid-route value (sip, otc, boats, overnight), is refused."""
    feed = query.get("feed")
    if feed is not None and feed != FEED:
        raise TransportRefused("feed refused: only the free iex feed is allowed")
    for k, v in query.items():
        if k != "feed" and isinstance(v, str) and v.lower() in _PAID_DATA_PARAMS:
            raise TransportRefused("paid data route refused")


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TransportRefused("redirect refused", sent=True)


def default_opener():
    ctx = ssl.create_default_context()      # certificate and hostname verification on
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),     # ignore environment proxies
        _RefuseRedirects(),
        urllib.request.HTTPSHandler(context=ctx),
    )


def _parse(raw):
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return {"message": "non-JSON response body"}


class StaticTestProvider(object):
    """Synthetic credentials for tests only. Never a real key.

    mode: "paper" (default) or "live". A transport refuses a provider whose mode is not its own."""

    def __init__(self, key_id, secret, mode="paper"):
        self._key_id = key_id
        self._secret = secret
        self.mode = mode

    def get(self):
        return self._key_id, self._secret

    def describe(self):
        return "static test provider (synthetic values)"

    def __repr__(self):
        return "StaticTestProvider(<synthetic, hidden>)"


def provider_mode(provider):
    """A provider's declared account mode. One that declares nothing is treated as paper."""
    return getattr(provider, "mode", "paper")


class HttpsTransport(object):
    """The PAPER transport. Live trading has its own class (alpaca/live.py) with its own origins, its
    own credentials and a per-session authorization; nothing on this class can be switched to live."""

    MODE = "paper"
    USER_AGENT = USER_AGENT
    REFUSED_KEY_PREFIXES = ("AK",)          # live-looking key ids never go out on the paper host

    def __init__(self, credentials_provider, timeout_s=10, opener=None):
        if provider_mode(credentials_provider) != self.MODE:
            raise TransportRefused("credentials provider is for %r, this transport is %r"
                                   % (str(provider_mode(credentials_provider))[:10], self.MODE))
        self._provider = credentials_provider
        self.timeout_s = float(timeout_s)
        self._opener = opener if opener is not None else default_opener()
        self.injected = opener is not None

    def __repr__(self):
        try:
            desc = str(self._provider.describe())
        except Exception:
            desc = "credentials provider"
        origins = self._origins()
        return "%s(trading=%s, data=%s, credentials=%s)" % (
            type(self).__name__, origins.get("trading"), origins.get("data"), desc)

    __str__ = __repr__

    def _origins(self):
        return _FIXED_ORIGINS

    def _resolve(self, origin_key):
        return resolve_origin(origin_key)

    def _headers(self, has_body):
        try:
            key_id, secret = self._provider.get()
        except Exception:
            raise TransportRefused("credentials unavailable from provider") from None
        for v in (key_id, secret):
            if not isinstance(v, str) or not v or any(ord(c) < 0x21 or ord(c) >= 0x7f for c in v):
                raise TransportRefused("credentials from provider are not usable header values")
        if key_id.upper().startswith(self.REFUSED_KEY_PREFIXES):
            raise TransportRefused("key id prefix belongs to the other account mode; refused for %s"
                                   % self.MODE)
        h = {HEADER_KEY_ID: key_id, HEADER_SECRET: secret, "Accept": "application/json",
             "User-Agent": self.USER_AGENT}
        if has_body:
            h["Content-Type"] = "application/json"
        return h

    def request(self, method, origin_key, path, query=None, body=None):
        if method not in METHODS:
            raise TransportRefused("method refused")
        if provider_mode(self._provider) != self.MODE:
            raise TransportRefused("credentials provider mode changed; refused")
        origin, host = self._resolve(origin_key)
        validate_path(path)
        qs = encode_query(origin_key, query)
        if body is not None and method != "POST":
            raise TransportRefused("body only allowed on POST")
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        url = origin + path + ("?" + qs if qs else "")
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers(data is not None))
        uncertain = method == "POST"
        where = "%s %s %s" % (method, origin_key, path)
        try:
            resp = self._opener.open(req, timeout=self.timeout_s)
        except TransportRefused:
            raise
        except urllib.error.HTTPError as e:
            code = int(e.code)
            try:
                raw = e.read()
            except Exception:
                raw = b""
            finally:
                try:
                    e.close()
                except Exception:
                    pass
            if 300 <= code < 400:
                raise TransportRefused("redirect refused", sent=True) from None
            if code >= 500:
                exc = BrokerUncertain if uncertain else BrokerOutage
                raise exc("%s: server error %d" % (where, code)) from None
            return code, _parse(raw)
        except (socket.timeout, TimeoutError):
            exc = BrokerUncertain if uncertain else BrokerOutage
            raise exc("%s: timed out" % where) from None
        except (urllib.error.URLError, ConnectionError, http.client.HTTPException, OSError) as e:
            exc = BrokerUncertain if uncertain else BrokerOutage
            raise exc("%s: connection failed (%s)" % (where, type(e).__name__)) from None
        try:
            final = resp.geturl() if hasattr(resp, "geturl") else url
            fhost = (urllib.parse.urlsplit(final).hostname or "").lower()
            if fhost != host:
                raise TransportRefused("response came from a different host", sent=True)
            code = int(getattr(resp, "status", None) or resp.getcode())
            if 300 <= code < 400:
                raise TransportRefused("redirect refused", sent=True)
            try:
                raw = resp.read()
            except (socket.timeout, TimeoutError, OSError, http.client.HTTPException) as e:
                exc = BrokerUncertain if uncertain else BrokerOutage
                raise exc("%s: response read failed (%s)" % (where, type(e).__name__)) from None
        finally:
            try:
                resp.close()
            except Exception:
                pass
        if code >= 500:
            exc = BrokerUncertain if uncertain else BrokerOutage
            raise exc("%s: server error %d" % (where, code))
        return code, _parse(raw)
