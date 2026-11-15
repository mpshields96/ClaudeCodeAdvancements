"""Credentials providers (alpaca/setup.py). Fully synthetic: a fake runner and a fake environ.

No test here runs /usr/bin/security, reads the real environment, or touches any network.
"""
import os
import sys
import unittest

DESK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK_DIR not in sys.path:
    sys.path.insert(0, DESK_DIR)

from alpaca import setup  # noqa: E402

KEY = "PKSYNTHETIC0000TEST"      # synthetic, shaped like a paper key id
SECRET = "synthetic-secret-not-real"
LIVE = "AKSYNTHETIC0000TEST"     # synthetic, shaped like a live key id


class FakeRunner(object):
    def __init__(self, answers):
        self.answers = answers      # account -> (code, stdout)
        self.calls = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        account = argv[argv.index("-a") + 1]
        return self.answers.get(account, (44, ""))


def _no_secret(test, text):
    for s in (KEY, SECRET, LIVE):
        test.assertNotIn(s, text)


class TestKeychainProvider(unittest.TestCase):
    def test_construct_reads_nothing(self):
        runner = FakeRunner({})
        p = setup.KeychainProvider(runner=runner)
        p.describe()
        repr(p)
        self.assertEqual(runner.calls, [])

    def test_get_reads_both_items_with_security(self):
        runner = FakeRunner({"key-id": (0, KEY + "\n"), "secret-key": (0, SECRET + "\n")})
        p = setup.KeychainProvider(runner=runner)
        self.assertEqual(p.get(), (KEY, SECRET))
        self.assertEqual(runner.calls[0], ["/usr/bin/security", "find-generic-password", "-s",
                                           "alpaca-paper", "-a", "key-id", "-w"])
        self.assertEqual(runner.calls[1][5], "secret-key")
        self.assertTrue(all(c[0] == "/usr/bin/security" for c in runner.calls))

    def test_describe_has_no_key_material(self):
        runner = FakeRunner({"key-id": (0, KEY), "secret-key": (0, SECRET)})
        p = setup.KeychainProvider(runner=runner)
        p.get()
        _no_secret(self, p.describe())
        _no_secret(self, repr(p))
        self.assertIn("alpaca-paper", p.describe())

    def test_live_key_refused_without_echoing_it(self):
        runner = FakeRunner({"key-id": (0, LIVE), "secret-key": (0, SECRET)})
        with self.assertRaises(setup.CredentialsError) as cm:
            setup.KeychainProvider(runner=runner).get()
        self.assertIn("LIVE", str(cm.exception))
        _no_secret(self, str(cm.exception))

    def test_lowercase_live_prefix_refused(self):
        runner = FakeRunner({"key-id": (0, "ak" + KEY[2:]), "secret-key": (0, SECRET)})
        with self.assertRaises(setup.CredentialsError):
            setup.KeychainProvider(runner=runner).get()

    def test_unusual_prefix_not_refused(self):
        # Alpaca calls PK/AK "visual hints"; the fixed paper host is the boundary, so only AK is refused.
        odd = "ZZ" + KEY[2:]
        runner = FakeRunner({"key-id": (0, odd), "secret-key": (0, SECRET)})
        self.assertEqual(setup.KeychainProvider(runner=runner).get(), (odd, SECRET))

    def test_missing_item_gives_plain_reason(self):
        runner = FakeRunner({})
        with self.assertRaises(setup.CredentialsError) as cm:
            setup.KeychainProvider(runner=runner).get()
        self.assertIn("not found", str(cm.exception))
        self.assertIn("SETUP.md", str(cm.exception))

    def test_missing_secret_after_good_key(self):
        runner = FakeRunner({"key-id": (0, KEY)})
        with self.assertRaises(setup.CredentialsError) as cm:
            setup.KeychainProvider(runner=runner).get()
        _no_secret(self, str(cm.exception))

    def test_empty_or_spaced_values_refused(self):
        for key, sec in (("", SECRET), (KEY, ""), (KEY + " x", SECRET), (KEY, "a b")):
            runner = FakeRunner({"key-id": (0, key), "secret-key": (0, sec)})
            with self.assertRaises(setup.CredentialsError) as cm:
                setup.KeychainProvider(runner=runner).get()
            _no_secret(self, str(cm.exception))

    def test_runner_oserror_is_plain(self):
        def boom(argv):
            raise OSError("synthetic")
        with self.assertRaises(setup.CredentialsError) as cm:
            setup.KeychainProvider(runner=boom).get()
        self.assertIn("could not run", str(cm.exception))


class TestEnvProvider(unittest.TestCase):
    def test_reads_only_injected_mapping(self):
        env = {"APCA_API_KEY_ID": KEY, "APCA_API_SECRET_KEY": SECRET}
        p = setup.EnvProvider(environ=env)
        self.assertEqual(p.get(), (KEY, SECRET))
        _no_secret(self, p.describe())
        _no_secret(self, repr(p))

    def test_missing_vars(self):
        with self.assertRaises(setup.CredentialsError) as cm:
            setup.EnvProvider(environ={}).get()
        self.assertIn("APCA_API_KEY_ID", str(cm.exception))
        with self.assertRaises(setup.CredentialsError) as cm:
            setup.EnvProvider(environ={"APCA_API_KEY_ID": KEY}).get()
        self.assertIn("APCA_API_SECRET_KEY", str(cm.exception))
        _no_secret(self, str(cm.exception))

    def test_live_key_refused(self):
        env = {"APCA_API_KEY_ID": LIVE, "APCA_API_SECRET_KEY": SECRET}
        with self.assertRaises(setup.CredentialsError) as cm:
            setup.EnvProvider(environ=env).get()
        _no_secret(self, str(cm.exception))


class TestMakeProvider(unittest.TestCase):
    def test_kinds(self):
        self.assertIsInstance(setup.make_provider("keychain", runner=FakeRunner({})), setup.KeychainProvider)
        self.assertIsInstance(setup.make_provider("env", environ={}), setup.EnvProvider)
        with self.assertRaises(setup.CredentialsError):
            setup.make_provider("file")

    def test_limits_loader_reexported(self):
        from alpaca import sizing
        self.assertIs(setup.load_limits, sizing.load_limits)


class TestSourceHygiene(unittest.TestCase):
    def test_security_only_inside_get_path(self):
        with open(os.path.join(DESK_DIR, "alpaca", "setup.py")) as fh:
            src = fh.read()
        self.assertNotIn("shell=True", src)
        self.assertNotIn("add-generic-password", src)   # storing is Matthew's step, never code
        self.assertNotIn("api.alpaca.markets", src)


if __name__ == "__main__":
    unittest.main()
