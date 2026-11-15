#!/bin/sh
# Offline rebuild of the packaged historical edition, using only its dated inputs.
set -eu
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -d "$base/../release_data" ]; then
    src="$base/../release_data"
elif [ -d "$base/examples/sunday" ]; then
    src="$base/examples/sunday"
else
    src="/Users/matthewshields/Documents/Codex/2026-11-14/paper-desk-final-closeout/outputs/NFL_Live"
fi
set --
if [ -f "$src/sunday_20261115_watchlist.json" ]; then
    set -- --watchlist "$src/sunday_20261115_watchlist.json"
fi
"$base/generate_brief" --card "$src/Sunday_Card.json" --snapshot "$src/sunday-odds.json" --observations "$src/observations" --output "$base/Sunday_NFL_Brief.pdf" "$@"
