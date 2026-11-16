#!/bin/zsh
# Starts the live (real-money) SPY desk after your separate live limits approval.
# You type the confirmation yourself; the desk opens with the live adapter disabled.
set -eu
desk_dir="${0:A:h:h}"
live_dir="$desk_dir/state-alpaca-live"
approved="$live_dir/limits_approved.json"
if [[ ! -f "$approved" ]]; then
  print 'Use Review Live Limits first. The live desk starts only from your separately approved live limits.'
  exit 2
fi
print 'Starting the live SPY desk. You will type a confirmation; the live adapter starts disabled.'
exec /usr/bin/python3 -IB "$desk_dir/alpaca/live_launch.py" start --state-dir "$live_dir" --limits "$approved"
