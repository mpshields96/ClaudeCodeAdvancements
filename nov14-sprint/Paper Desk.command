#!/bin/bash
# Paper Desk: double-click to open. Paper only, local only.
HERE="$(cd "$(dirname "$0")" && pwd)"
exec /usr/bin/python3 "$HERE/desk/desk_server.py" --open
