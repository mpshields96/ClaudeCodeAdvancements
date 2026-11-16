#!/usr/bin/env python3
"""The distinct LIVE-money command. Separate from launch.py on purpose: no flag there reaches live.

    /usr/bin/python3 -I alpaca/live_launch.py approve-limits --draft-from MY_LIVE_LIMITS.json
    /usr/bin/python3 -I alpaca/live_launch.py start --limits state-alpaca-live/limits_approved.json

`start` runs every check of the live gate (alpaca/live.py) before anything else: a live state dir
(state-alpaca-live, never a paper one), a non-paper port, an operator-approved limits snapshot stored in
that dir and approved with `approve-limits`, a real terminal, and the typed phrase
"LIVE SPY <shares> SHARES <today's CT date>". It reads no key and opens no socket while checking.

THIS BUILD STOPS AFTER THE GATE (exit 3). The session controller (alpaca_session.py, coordinator-owned)
labels every Alpaca session as paper and keeps paper state, so a live session cannot be shown honestly
yet. Wiring it is a separate, reviewed change; see LIVE_READINESS.md.

Exit codes: 0 approve-limits saved; 2 refused (nothing sent); 3 gate passed, live session not wired.
"""
import argparse
import os
import sys

DESK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DESK not in sys.path:
    sys.path.insert(0, DESK)

from alpaca import live as L  # noqa: E402
from alpaca import sizing  # noqa: E402

DEFAULT_LIVE_STATE = os.path.join(DESK, L.LIVE_STATE_DIRNAME)
NOT_WIRED = ("LIVE GATE PASSED for %s, %d shares. Nothing was sent: the live session controller is not "
             "wired in this build (alpaca_session.py labels every Alpaca session as paper). No key was "
             "read and no connection was opened.")


def _parser():
    p = argparse.ArgumentParser(prog="live_launch.py", description="LIVE-money Alpaca gate (off by default)")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("start", help="run the per-session live gate")
    s.add_argument("--limits", default=None, help="your approved LIVE limits inside state-alpaca-live/")
    s.add_argument("--state-dir", default=DEFAULT_LIVE_STATE)
    s.add_argument("--port", type=int, default=L.LIVE_PORT)
    s.add_argument("--provider", choices=sorted(L.LIVE_PROVIDERS), default="keychain")
    a = sub.add_parser("approve-limits", help="approve LIVE limits you wrote yourself")
    a.add_argument("--state-dir", default=DEFAULT_LIVE_STATE)
    a.add_argument("--draft-from", default=None, help="a JSON file with your five values")
    return p


def _refuse(err, msg):
    err.write("REFUSED (live): %s\nNothing was sent; no key was read; no connection was opened.\n" % msg)
    return 2


def _start(args, out, err, isatty, read_line):
    try:
        state_dir = L.check_live_state_dir(args.state_dir)
        L.check_live_port(args.port)
        loaded = L.check_live_limits(args.limits, state_dir)
        if not isatty():
            raise L.LiveGateRefused("the live confirmation must be typed at a terminal (piped input refused)")
        want = L.confirm_phrase(loaded["values"]["fixed_shares"], L.session_date())
        out.write("%s\nLimits: %s\nTo start REAL-MONEY trading for this session only, type exactly:\n  %s\n> "
                  % (L.LABEL_ALPACA_LIVE, loaded["values"], want))
        out.flush()
        typed = read_line()
        auth = L.live_gate_authorize(args.limits, state_dir, args.port, typed, isatty(),
                                     shown_hash=loaded["hash"])
    except L.LiveGateRefused as e:
        return _refuse(err, str(e))
    out.write(NOT_WIRED % (auth.session_date, auth.shares) + "\n")
    return 3


def _approve(args, out, err, isatty, read_line):
    try:
        path = os.path.abspath(args.state_dir)
        if os.path.basename(path.rstrip(os.sep)) != L.LIVE_STATE_DIRNAME:
            raise L.LiveGateRefused("live limits are approved only in a folder named %s" % L.LIVE_STATE_DIRNAME)
        os.makedirs(path, exist_ok=True)
        L.check_live_state_dir(path)
        if not isatty():
            raise L.LiveGateRefused("live limits must be approved at a terminal (piped input refused)")
        if args.draft_from:
            obj, why = sizing._read_json(args.draft_from)
            if not isinstance(obj, dict):
                raise L.LiveGateRefused("draft file: %s" % (why or "not a JSON object"))
            sizing.save_draft(path, obj.get("values", obj), copied_from=os.path.basename(args.draft_from))
        draft = sizing.read_draft(path)
        if not draft:
            raise L.LiveGateRefused("no live draft yet; pass --draft-from with your five values")
        out.write("LIVE limits draft: %s\nType exactly: %s\n> " % (draft.get("values"), L.LIVE_CONFIRM_LIMITS))
        out.flush()
        if (read_line() or "").strip() != L.LIVE_CONFIRM_LIMITS:
            raise L.LiveGateRefused("approval phrase did not match")
        out.write("Reason (one line): ")
        out.flush()
        reason = read_line()
        old = sizing.read_approved(path) or {}
        snap = sizing.approve(path, sizing.CONFIRM_PHRASE, reason,
                              reviewed_draft_hash=sizing.content_hash(draft.get("values")),
                              prior_approved_hash=old.get("hash"), by=L.LIVE_APPROVER)
    except (L.LiveGateRefused, sizing.LimitsError) as e:
        return _refuse(err, str(e))
    out.write("Approved LIVE limits saved: %s\n" % sizing.approved_path(path))
    return 0 if snap else 2


def main(argv=None, out=None, err=None, isatty=None, read_line=None):
    out, err = out or sys.stdout, err or sys.stderr
    isatty = isatty or (lambda: bool(sys.stdin and sys.stdin.isatty()))
    read_line = read_line or (lambda: sys.stdin.readline())
    args = _parser().parse_args(argv)
    if args.cmd == "start":
        return _start(args, out, err, isatty, read_line)
    if args.cmd == "approve-limits":
        return _approve(args, out, err, isatty, read_line)
    return _refuse(err, "choose a subcommand: start or approve-limits (see LIVE_READINESS.md)")


if __name__ == "__main__":
    sys.exit(main())
