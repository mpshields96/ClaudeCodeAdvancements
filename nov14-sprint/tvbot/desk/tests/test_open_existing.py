"""alpaca/open_existing.py: the Finder reopen finds this exact desk on its preferred port or a fallback
port, and never opens a desk with another state folder or broker mode. Loopback fake health servers
only; the browser opener is captured, so nothing is opened."""
import http.server
import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import unittest

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)


def _load():
    spec = importlib.util.spec_from_file_location("open_existing", os.path.join(DESK, "alpaca", "open_existing.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OE = _load()


def _health_server(port, health):
    body = json.dumps(health).encode()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/api/health" else 404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _two_free_ports():
    """Two consecutive free loopback ports, so one desk can sit on the other's fallback port."""
    for _ in range(50):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            first = s.getsockname()[1]
        if first + 1 > 65535:
            continue
        try:
            with socket.socket() as a, socket.socket() as b:
                a.bind(("127.0.0.1", first))
                b.bind(("127.0.0.1", first + 1))
            return first
        except OSError:
            continue
    raise unittest.SkipTest("no two consecutive free loopback ports")


class ReopenFindsThisDeskOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="open-existing-")
        self.mine = os.path.join(self.tmp, "mine")
        self.other = os.path.join(self.tmp, "other")
        os.makedirs(self.mine)
        os.makedirs(self.other)
        self.servers = []
        self.first = _two_free_ports()

    def tearDown(self):
        for s in self.servers:
            s.shutdown()
            s.server_close()

    def serve(self, port, state_dir, mode="alpaca-mock", attached=True):
        self.servers.append(_health_server(port, {"controller_attached": attached, "broker_mode": mode,
                                                  "state_dir": state_dir}))

    def run_main(self):
        opened = []
        code = OE.main([str(self.first), self.mine, "alpaca-mock"], call=lambda cmd: opened.append(cmd[-1]) or 0)
        return code, opened

    def test_reopens_this_desk_on_its_fallback_port_never_the_foreign_one(self):
        # 62327/62328 case: another desk holds the preferred port, this one moved to the next port.
        self.serve(self.first, self.other)
        self.serve(self.first + 1, self.mine)
        code, opened = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(opened, ["http://127.0.0.1:%d/" % (self.first + 1)])

    def test_foreign_desks_only_opens_nothing(self):
        self.serve(self.first, self.other)                         # other state folder
        self.serve(self.first + 1, self.mine, mode="alpaca-paper")  # same folder, other broker mode
        code, opened = self.run_main()
        self.assertEqual(code, 1)
        self.assertEqual(opened, [])

    def test_scan_width_matches_launch_free_port(self):
        import launch
        self.assertEqual(OE.FALLBACK_TRIES, launch.free_port.__defaults__[0])


if __name__ == "__main__":
    unittest.main()
