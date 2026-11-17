#!/bin/zsh
# Automated Alpaca PAPER session. You start it once; it never starts itself and installs no schedule.
# It opens (or attaches to) the connected paper desk, runs the checked reconcile, waits for the strategy
# warm-up and an open regular session, then presses the paper desk's Enable and Arm once (arm expiry no
# later than the run end) and checks every 30 seconds. It stops on a desk Stop, a risk latch, an unresolved
# or unknown order, an outside order or a lost connection, and never enables or arms again in that run.
# At the end it presses Stop & Close if the desk still holds its own paper exposure, reconciles, and
# reports FLAT, EXPOSED or UNRESOLVED. It never presses Clear Stop, Play or Schedule.
# A desk whose /api/health lacks "arm_bounded_expiry": true can't hold Arm to the run end; there it
# presses nothing and runs monitor-only (alpaca/AUTOMATED_PAPER.md, "Arm expiry").
# For a monitor-only run (never presses Enable or Arm) use "Run Timed Paper Session.command" instead.
# Defaults: 120 minutes, a check every 30 seconds, Stop & Close at the end. Later options win, e.g.
#   --minutes 60 --no-browser
set -eu
desk_dir="${0:A:h:h}"
exec /usr/bin/python3 -IB "$desk_dir/alpaca/paper_runner.py" --auto --minutes 120 --every 30 "$@"
