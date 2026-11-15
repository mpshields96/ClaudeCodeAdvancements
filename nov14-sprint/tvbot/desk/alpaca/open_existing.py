"""Return success only after reopening this exact local desk in its browser."""
import argparse
import http.client
import json
from pathlib import Path
import subprocess


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
    except (OSError, ValueError, TypeError, KeyError, http.client.HTTPException):
        return False
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", type=int)
    parser.add_argument("state_dir", type=Path)
    parser.add_argument("mode", choices=("alpaca-mock", "alpaca-paper"))
    args = parser.parse_args()
    if not is_same_desk(args.port, args.state_dir, args.mode):
        raise SystemExit(1)
    url = "http://127.0.0.1:{}/".format(args.port)
    print("The desk is already running. Reopening " + url)
    raise SystemExit(subprocess.call(["/usr/bin/open", url]))
