#!/bin/zsh
set -eu
desk_dir="${0:A:h:h}"
if [[ ! -f "$desk_dir/state-alpaca-live/limits_approved.json" ]]; then
  print 'Use Review Live Limits first. This check uses the separately approved live worksheet.'
  exit 2
fi
exec /usr/bin/python3 -IB "$desk_dir/live_check.py"
