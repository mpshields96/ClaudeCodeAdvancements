#!/bin/zsh
# User-launched, authenticated paper-only session. Credentials and limits stay local.
set -eu
desk_dir="${0:A:h:h}"
approved="$desk_dir/state-alpaca-mock/limits_approved.json"
if [[ ! -f "$approved" ]]; then
  print 'Open the SPY paper desk, choose Setup (limits), and approve your own values first.'
  exit 2
fi
print 'Opening the connected Alpaca paper desk with the approved worksheet. New orders require manual controls.'
exec /usr/bin/python3 -IB "$desk_dir/launch.py" --broker alpaca-paper --transport https \
  --state-dir "$desk_dir/state-alpaca-paper" --limits "$approved" "$@"
