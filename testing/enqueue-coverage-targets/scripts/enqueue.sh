#!/usr/bin/env bash
# Build the worker queue for a coverage-raising run.
#
# Usage: enqueue.sh [go|nodejs|python|rust]
#
# With no argument the language is detected from the repository root
# (go.mod, package.json, Cargo.toml, *.py). Every language writes the same
# two files so the worker phase in SKILL.md is language-independent:
#
#   /tmp/squad-targets.txt   <unit>\t<pct>%\t(target N%)  — sorted worst-first
#   /tmp/squad-uncovered.out per-function / per-line hit data for target selection
#
# Environment:
#   SQUAD_COVERAGE_TARGET      percent threshold (default 75)
#   SQUAD_CMD_COVERAGE_TARGET  Go only: separate threshold for */cmd/* packages
#   SQUAD_PYTHON_PKG           Python only: package passed to --cov (default .)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lang="${1:-}"

if [ -z "$lang" ]; then
	if [ -f go.mod ]; then
		lang=go
	elif [ -f Cargo.toml ] || [ -f Cargo.lock ]; then
		lang=rust
	elif [ -f package.json ]; then
		lang=nodejs
	elif [ -n "$(find . -name '*.py' -not -path '*/.venv/*' -not -path '*/node_modules/*' -print -quit 2>/dev/null)" ]; then
		lang=python
	else
		echo "UNKNOWN_PROJECT: no go.mod, Cargo.toml, package.json, or .py files in $(pwd)." >&2
		echo "Stop here and report 'no supported source' honestly — do not pivot to another language." >&2
		: >/tmp/squad-targets.txt
		echo "=== queue size ==="
		echo 0
		exit 0
	fi
fi

case "$lang" in
go | nodejs | python | rust) ;;
*)
	echo "usage: enqueue.sh [go|nodejs|python|rust]" >&2
	exit 2
	;;
esac

# Clear stale state from prior runs (possibly a different language).
rm -f /tmp/squad-targets.txt /tmp/squad-uncovered.out

export SQUAD_COVERAGE_TARGET="${SQUAD_COVERAGE_TARGET:-75}"
bash "$here/enqueue_$lang.sh"

echo "=== /tmp/squad-targets.txt (worker queue, language=$lang) ==="
cat /tmp/squad-targets.txt 2>/dev/null || echo "(empty queue)"
echo "=== queue size ==="
wc -l </tmp/squad-targets.txt 2>/dev/null || echo 0
