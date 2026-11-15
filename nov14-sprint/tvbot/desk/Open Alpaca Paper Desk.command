#!/bin/zsh
# Open the Alpaca PAPER desk from Finder in MOCK mode: local fake venue, synthetic ids,
# no network, no credentials. Your own first paper session is a separate explicit
# command that needs your approved limits; see alpaca/SETUP.md.
set -u
desk_dir="${0:A:h}"
py=(/usr/bin/python3 -IB)
# MOCK only (Codex 22:46Z). Refuse any option that could pick another transport or broker,
# including argparse abbreviations (--t..., --b...), before anything runs. The connected
# paper desk has its own command: after-approval/Open Connected Paper Desk.command.
for arg in "$@"; do
  case "$arg" in
    --t*|--b*|*https*)
      echo "REFUSED: this Finder command runs the MOCK desk only (local fake Alpaca, no network)."
      echo "It does not accept '$arg'. After you approve your limits, the connected paper desk"
      echo "has its own command: after-approval/Open Connected Paper Desk.command"
      echo "Nothing was started. Press Return to close this window."
      read -r _
      exit 2
      ;;
  esac
done
echo "Alpaca PAPER desk, MOCK mode (local only). Running the mock walkthrough check first..."
echo
if ! "${py[@]}" "$desk_dir/launch.py" --broker alpaca-paper --check; then
  echo
  echo "Mock check FAILED. Nothing was sent to any broker. The desk will not start."
  echo "Press Return to close this window."
  read -r _
  exit 1
fi
echo
echo "Read-only first connection check, for you to run after you approve limits in the"
echo "sizing worksheet (four GET requests, no order is ever submitted):"
echo "  /usr/bin/python3 -IB \"$desk_dir/alpaca/readiness.py\" --state-dir <your paper state dir> --limits <your approved limits file>"
echo
echo "Starting the MOCK desk now. Manual only: nothing runs in the background."
echo "Close this window or press Ctrl-C to stop it."
exec "${py[@]}" "$desk_dir/launch.py" --broker alpaca-paper "$@" --transport mock
