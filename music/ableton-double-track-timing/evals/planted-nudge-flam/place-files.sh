#!/usr/bin/env bash
# Builds coven-snapshot.als and planted-nudge.als in the current directory from
# the source set (read-only). Override the source with ADTT_SOURCE_ALS.
set -eu
SRC="${ADTT_SOURCE_ALS:-$HOME/Music/Ableton/Recording Projects/Graft/Liminal Dirge/Coven Project/Coven - Nadir (restored).als}"
uv run --quiet --with numpy python "$(dirname "$0")/../files/make_fixtures.py" "$SRC" .
