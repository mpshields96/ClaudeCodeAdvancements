#!/bin/zsh
set -eu
desk_dir="${0:A:h:h}"
worksheet="$desk_dir/state-alpaca-mock/limits_approved.json"
live_draft="$desk_dir/state-alpaca-live/limits_draft.json"
review=(/usr/bin/python3 -IB "$desk_dir/alpaca/live_launch.py" approve-limits)
if [[ -f "$live_draft" ]]; then
  if [[ ! -f "$worksheet" ]]; then
    exec "${review[@]}"
  fi
  print 'Press Return to review your existing live draft, or type WORKSHEET to start from your approved worksheet.'
  read -r choice
  case "$choice" in
    '') exec "${review[@]}" ;;
    WORKSHEET) ;;
    *) print 'Review canceled.'; exit 2 ;;
  esac
elif [[ ! -f "$worksheet" ]]; then
  print 'Open the rehearsal desk and approve your own five values under Setup (limits). Then reopen this review.'
  exit 2
fi
print 'Review your worksheet for the live account. Your typed approval saves a separate live snapshot.'
exec "${review[@]}" --draft-from "$worksheet"
