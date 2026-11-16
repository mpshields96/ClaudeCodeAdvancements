"""Return success only after reopening this exact local desk in its browser.

A launcher whose preferred port is busy moves to the next free one (launch.free_port tries the preferred
port and the 19 after it), so the desk may be on any of those ports. Each one is asked for /api/health and
the first whose state folder and broker mode both match this desk is reopened. A desk with another state
folder or mode is never opened; if none matches, nothing is opened and the exit code is 1.
"""
import argparse
import http.client
import json
from pathlib import Path
import subprocess

FALLBACK_TRIES = 20          # launch.free_port(tries=20); test_open_existing checks they agree


def is_same_desk(port, state_dir, broker_mode):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.7)
    try:
        connection.request("GET", "/api/health")
        reply = connection.getresponse()
        if reply.status != 200:
            return False
        health = json.loads(reply.read(32768))
        return (health.get("controller_attached") is True and health.get("broker_mode") == broker_mode
                and Path(health["state_dir"]).resolve() == Path(state_dir).resolve())
    except (OSError, ValueError, TypeError, KeyError, AttributeError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def find_same_desk(port, state_dir, broker_mode, tries=FALLBACK_TRIES):
    """The first port in port..port+tries-1 serving this exact desk, or None."""
    for candidate in range(max(port, 1), min(port + tries, 65536)):
        if is_same_desk(candidate, state_dir, broker_mode):
            return candidate
    return None


def main(argv=None, call=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int)
    parser.add_argument("state_dir", type=Path)
    parser.add_argument("mode", choices=("alpaca-mock", "alpaca-paper"))
    args = parser.parse_args(argv)
    found = find_same_desk(args.port, args.state_dir, args.mode)
    if found is None:
        return 1
    url = "http://127.0.0.1:{}/".format(found)
    print("The desk is already running. Reopening " + url)
    return (call or subprocess.call)(["/usr/bin/open", url])


if __name__ == "__main__":
    raise SystemExit(main())
