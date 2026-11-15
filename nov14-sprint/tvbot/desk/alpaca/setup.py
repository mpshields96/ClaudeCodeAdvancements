"""Operator setup for the Alpaca PAPER adapter: credentials providers and the limits loader.

Credentials providers share one interface (CONTRACT.md section 1):
    provider.get() -> (key_id, secret)     called by the transport per request, at Matthew's runtime
    provider.describe() -> str             where the keys come from; never any key material

Nothing here reads a key at import or construction time. KeychainProvider runs /usr/bin/security only
inside get(); EnvProvider reads the environment only inside get(). Tests inject a fake runner or a
fake environ and never touch the real Keychain or environment. Error text never contains a key id
or a secret.

Both providers refuse a key id that looks like a LIVE-money key. Alpaca's own security guide, read
2026-11-15 (https://alpaca.markets/learn/api-key-security-best-practices-for-alpaca-builders):
"While Paper keys often begin with a PK... prefix and Live keys with an AK... prefix, these prefixes are
visual hints." The guide calls the host the authoritative boundary. So the real guard is the fixed
paper host in transport.py. This check is a second layer: it refuses an AK-looking key id, and it does
not require PK, so a genuine paper key with an unusual prefix still works.

The limits loader lives in alpaca/sizing.py and is re-exported here.
"""
import os
import subprocess

from alpaca.sizing import LimitsError, load_limits, as_session_limits  # noqa: F401  (re-export)

SECURITY_BIN = "/usr/bin/security"
KEYCHAIN_SERVICE = "alpaca-paper"
KEYCHAIN_KEY_ACCOUNT = "key-id"
KEYCHAIN_SECRET_ACCOUNT = "secret-key"
ENV_KEY_VAR = "APCA_API_KEY_ID"
ENV_SECRET_VAR = "APCA_API_SECRET_KEY"

LIVE_KEY_PREFIXES = ("AK",)     # a hint only (see above); the paper host is the real boundary


class CredentialsError(Exception):
    """Why paper credentials are unavailable. Never includes key material."""


def check_key_id(key_id):
    """Refuse an empty, spaced or LIVE-looking key id. Returns it unchanged."""
    if not isinstance(key_id, str) or not key_id.strip():
        raise CredentialsError("the paper key id is empty")
    if key_id != key_id.strip() or any(c.isspace() for c in key_id):
        raise CredentialsError("the paper key id contains spaces or line breaks; store it again without them")
    up = key_id.upper()
    if up.startswith(LIVE_KEY_PREFIXES):
        raise CredentialsError("this key id looks like a LIVE-money key (it starts with %s). The desk "
                               "accepts paper keys only; make keys from your Alpaca paper account."
                               % "/".join(LIVE_KEY_PREFIXES))
    return key_id


def _check_secret(secret):
    if not isinstance(secret, str) or not secret.strip():
        raise CredentialsError("the paper secret key is empty")
    if any(c.isspace() for c in secret):
        raise CredentialsError("the paper secret key contains spaces or line breaks; store it again without them")
    return secret


def _default_runner(argv):
    """Run /usr/bin/security without a shell. Returns (returncode, stdout). Only get() calls this."""
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          universal_newlines=True, timeout=15, check=False)
    return proc.returncode, proc.stdout


class KeychainProvider(object):
    """Paper keys from two macOS Keychain generic-password items (see SETUP.md for how to store them).

    service "alpaca-paper", accounts "key-id" and "secret-key". Read with
    `/usr/bin/security find-generic-password -s alpaca-paper -a <account> -w`, only inside get()."""

    def __init__(self, service=KEYCHAIN_SERVICE, key_account=KEYCHAIN_KEY_ACCOUNT,
                 secret_account=KEYCHAIN_SECRET_ACCOUNT, runner=None):
        self.service = str(service)
        self.key_account = str(key_account)
        self.secret_account = str(secret_account)
        self._runner = runner

    def _read(self, account):
        argv = [SECURITY_BIN, "find-generic-password", "-s", self.service, "-a", account, "-w"]
        runner = self._runner or _default_runner
        try:
            code, out = runner(argv)
        except (OSError, subprocess.SubprocessError):
            raise CredentialsError("could not run %s to read the Keychain item %s / %s"
                                   % (SECURITY_BIN, self.service, account)) from None
        if code != 0:
            raise CredentialsError("Keychain item %s / %s was not found or access was denied (security exit %s). "
                                   "See SETUP.md step 3." % (self.service, account, code))
        return (out or "").rstrip("\r\n")

    def get(self):
        key_id = check_key_id(self._read(self.key_account))
        secret = _check_secret(self._read(self.secret_account))
        return key_id, secret

    def describe(self):
        return ("macOS Keychain items service '%s' (accounts '%s' and '%s'); read only when a real "
                "paper session sends a request" % (self.service, self.key_account, self.secret_account))

    def __repr__(self):
        return "KeychainProvider(service=%r)" % self.service


class EnvProvider(object):
    """Paper keys from APCA_API_KEY_ID / APCA_API_SECRET_KEY, read only inside get().

    environ: a mapping to read instead of os.environ (tests pass a fake dict)."""

    def __init__(self, environ=None, key_var=ENV_KEY_VAR, secret_var=ENV_SECRET_VAR):
        self._environ = environ
        self.key_var = str(key_var)
        self.secret_var = str(secret_var)

    def get(self):
        env = self._environ if self._environ is not None else os.environ
        key_id = env.get(self.key_var)
        if not key_id:
            raise CredentialsError("%s is not set" % self.key_var)
        secret = env.get(self.secret_var)
        if not secret:
            raise CredentialsError("%s is not set" % self.secret_var)
        return check_key_id(key_id), _check_secret(secret)

    def describe(self):
        return ("environment variables %s and %s; read only when a real paper session sends a request"
                % (self.key_var, self.secret_var))

    def __repr__(self):
        return "EnvProvider(%s, %s)" % (self.key_var, self.secret_var)


PROVIDERS = {"keychain": KeychainProvider, "env": EnvProvider}


def make_provider(kind="keychain", **kwargs):
    """'keychain' (default) or 'env'. Constructing one reads nothing."""
    try:
        cls = PROVIDERS[kind]
    except KeyError:
        raise CredentialsError("unknown credentials source %r; use keychain or env" % str(kind)[:20]) from None
    return cls(**kwargs)
