#!/usr/bin/env bash
# Runs the bundled script suites: gp_tab, the transcription selftest, and
# the quorum harness tests. Used by pre-commit and by CI (Script Tests job).
# Needs node and uv. The two Python suites install their own requirements
# into uv's cache, so nothing is written into the repo.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"

echo "== quorum harness tests"
node "$root/testing/quorum/scripts/test.mjs"

echo "== gp_tab tests"
uv run --quiet --with-requirements "$root/music/guitar-pro/scripts/requirements.txt" \
	python "$root/music/guitar-pro/scripts/test_gp_tab.py"

echo "== transcribe-guitar-riff selftest"
uv run --quiet --with-requirements "$root/music/transcribe-guitar-riff/scripts/requirements.txt" \
	python "$root/music/transcribe-guitar-riff/scripts/selftest.py"
