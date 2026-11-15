#!/bin/zsh
# A Finder action for the first authenticated paper test after local limits approval.
set -eu
desk_dir="${0:A:h:h}"
worksheet_dir="$desk_dir/state-alpaca-mock"
approved="$worksheet_dir/limits_approved.json"
if [[ ! -f "$approved" ]]; then
  print 'Open the SPY paper desk, choose Setup (limits), and approve your own values first.'
  exit 2
fi
print 'Checking your Alpaca paper account, SPY, the market clock and free IEX quote.'
exec /usr/bin/python3 -IB "$desk_dir/alpaca/readiness.py" --state-dir "$worksheet_dir" --limits "$approved" "$@"
