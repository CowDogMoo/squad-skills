#!/usr/bin/env bash
# Standard-library-only fixtures; outputs go in the case working directory.
set -eu
python3 "$(dirname "$0")/../files/make_fixtures.py" .
