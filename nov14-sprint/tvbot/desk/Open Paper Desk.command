#!/bin/zsh
# Open the offline paper desk from Finder on this Mac.
set -eu
desk_dir="${0:A:h}"
exec /usr/bin/python3 -IB "$desk_dir/launch.py" "$@"
