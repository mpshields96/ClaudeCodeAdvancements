#!/bin/zsh
# Timed, operator-started Alpaca PAPER session. You start it; it never starts itself and installs no schedule.
# It opens (or attaches to) the connected paper desk, checks the strategy on a timer, shows each check,
# and at the end reconciles with the broker and reports flat or exposed.
# It never presses Enable or Arm: orders still need your own manual controls in the desk.
# The regular-hours desk ("Open Connected Paper Desk") is separate; this runner only drives that same paper desk.
# Examples: no arguments = 60 minutes, a check every 60 seconds, Stop & Close at the end.
#   --minutes 30 --every 60 --at-end leave --no-browser
set -eu
desk_dir="${0:A:h:h}"
exec /usr/bin/python3 -IB "$desk_dir/alpaca/paper_runner.py" "$@"
