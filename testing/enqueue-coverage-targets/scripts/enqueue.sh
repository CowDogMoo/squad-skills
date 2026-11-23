#!/usr/bin/env bash
# Build the worker queue for a coverage-raising run.
#
# Usage: enqueue.sh [go|nodejs|python|rust] [PROJECT_DIR]
#
# Both arguments are optional and may come in either order. With no language
# the language is detected from the project root (go.mod, package.json,
# Cargo.toml, *.py). PROJECT_DIR defaults to the current directory; passing it
# means the script can be the very first command of a run, with no `cd` or
# `cp` chained in front of it, and it works on a read-only checkout.
#
# Every language writes the same two files so the worker phase in SKILL.md is
# language-independent:
#
#   /tmp/squad-targets.txt   <unit>\t<pct>%\t(target N%)  — sorted worst-first
#   /tmp/squad-uncovered.out per-function / per-line hit data for target selection
#
# Sandboxed shells can give every command a fresh /tmp, so the files above may
# not exist by the next command. The script therefore also prints the queue and
# the lowest-hit data for the queued units to stdout; that output is the
# worker's copy of both files.
#
# Environment:
#   SQUAD_COVERAGE_TARGET      percent threshold (default 75)
#   SQUAD_CMD_COVERAGE_TARGET  Go only: separate threshold for */cmd/* packages
#   SQUAD_PYTHON_PKG           Python only: package passed to --cov (default .)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lang=""
project=""
for arg in "$@"; do
	case "$arg" in
	go | nodejs | python | rust) lang="$arg" ;;
	*) if [ -d "$arg" ]; then
		project="$arg"
	else
		echo "usage: enqueue.sh [go|nodejs|python|rust] [PROJECT_DIR]" >&2
		exit 2
	fi ;;
	esac
done
if [ -n "$project" ]; then
	cd "$project"
fi

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

# Clear stale state from prior runs (possibly a different language).
rm -f /tmp/squad-targets.txt /tmp/squad-uncovered.out

export SQUAD_COVERAGE_TARGET="${SQUAD_COVERAGE_TARGET:-75}"
bash "$here/enqueue_$lang.sh"

echo "=== /tmp/squad-targets.txt (worker queue, language=$lang) ==="
cat /tmp/squad-targets.txt 2>/dev/null || echo "(empty queue)"
echo "=== queue size ==="
wc -l </tmp/squad-targets.txt 2>/dev/null || echo 0

# Lowest-hit data for the first 15 queued units, the same rows
# references/<lang>.md tells the worker to grep out of /tmp/squad-uncovered.out.
echo "=== lowest-hit data per queued unit (rows of /tmp/squad-uncovered.out) ==="
if [ -s /tmp/squad-targets.txt ] && [ -s /tmp/squad-uncovered.out ]; then
	head -n 15 /tmp/squad-targets.txt | while IFS=$'\t' read -r unit _; do
		echo "--- $unit"
		case "$lang" in
		go)
			awk -F'\t' -v u="$unit/" '
				index($1, u) == 1 && substr($1, length(u) + 1) !~ /\// && $2 != "100.0%"' \
				/tmp/squad-uncovered.out | sort -t$'\t' -k2 -n | head -n 8 || true
			;;
		python)
			grep -F "$unit:" /tmp/squad-uncovered.out | head -n 15 || true
			;;
		*)
			grep -F "$unit" /tmp/squad-uncovered.out | sort -t$'\t' -k2 -n | head -n 8 || true
			;;
		esac
	done
else
	echo "(no hit data)"
fi
