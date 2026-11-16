"""after-approval/Start Live Desk.command: a Finder start for the live desk. It runs only live_launch.py
start with the live folder and approved live limits, keeps the typed confirmation interactive, and refuses
without approved live limits. It is run in a temporary copy of the desk whose live_launch.py is a stand-in
that only records its arguments, so nothing real is started and nothing is sent."""
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMAND = os.path.join(DESK, "after-approval", "Start Live Desk.command")
ZSH = "/bin/zsh"


def _text():
    with open(COMMAND) as f:
        return f.read()


class StartLiveDeskCommandFileTests(unittest.TestCase):
    def test_exists_and_is_executable(self):
        self.assertTrue(os.path.isfile(COMMAND))
        self.assertTrue(os.stat(COMMAND).st_mode & stat.S_IXUSR)
        self.assertTrue(_text().startswith("#!/bin/zsh\n"))
        self.assertIn("set -eu", _text())

    def test_no_personal_path(self):
        text = _text()
        for bad in ("/Users/", "/home/", "~/", "$HOME", "local_", "Documents"):
            self.assertNotIn(bad, text)

    def test_calls_only_live_launch_start(self):
        text = _text()
        calls = re.findall(r"/usr/bin/python3[^\n]*", text)
        self.assertEqual(len(calls), 1, calls)
        self.assertIn('"$desk_dir/alpaca/live_launch.py" start', calls[0])
        for other in ("launch.py --", "live_check.py", "readiness.py", "open_existing.py", "approve-limits", "curl", "security "):
            self.assertNotIn(other, text.replace("live_launch.py", ""))

    def test_confirmation_stays_interactive(self):
        text = _text()
        self.assertNotIn("|", text)            # nothing piped into the prompt
        self.assertNotIn("<<", text)
        self.assertNotIn("yes", text.lower().replace("you ", ""))
        self.assertNotIn('"$@"', text)         # no extra flags passed through
        self.assertNotIn("--port", text)       # the launcher's own live port


@unittest.skipUnless(os.path.exists(ZSH), "zsh not available")
class StartLiveDeskCommandRunTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="start-live-desk-")
        os.makedirs(os.path.join(self.root, "after-approval"))
        os.makedirs(os.path.join(self.root, "alpaca"))
        self.cmd = os.path.join(self.root, "after-approval", "Start Live Desk.command")
        shutil.copy2(COMMAND, self.cmd)
        self.record = os.path.join(self.root, "argv.json")
        with open(os.path.join(self.root, "alpaca", "live_launch.py"), "w") as f:
            f.write("import json, sys\njson.dump(sys.argv[1:], open(%r, 'w'))\n" % self.record)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_cmd(self):
        return subprocess.run([ZSH, self.cmd], capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin"})

    def test_refuses_without_approved_live_limits(self):
        r = self.run_cmd()
        self.assertEqual(r.returncode, 2)
        self.assertIn("Use Review Live Limits first", r.stdout)
        self.assertFalse(os.path.exists(self.record))

    def test_runs_live_launch_start_with_the_live_folder_and_limits(self):
        live = os.path.join(self.root, "state-alpaca-live")
        os.makedirs(live)
        approved = os.path.join(live, "limits_approved.json")
        with open(approved, "w") as f:
            f.write("{}")
        r = self.run_cmd()
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.record) as f:
            argv = json.load(f)
        real_live = os.path.realpath(live)
        self.assertEqual(argv[0], "start")
        self.assertEqual(argv[1:], ["--state-dir", argv[2], "--limits", argv[4]])
        self.assertEqual(os.path.realpath(argv[2]), real_live)
        self.assertEqual(os.path.realpath(argv[4]), os.path.realpath(approved))


if __name__ == "__main__":
    unittest.main()
