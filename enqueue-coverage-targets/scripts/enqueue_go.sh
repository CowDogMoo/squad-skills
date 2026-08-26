#!/usr/bin/env bash
# Go: queue packages below target. Called by enqueue.sh; not meant to be run alone.
set -euo pipefail
TARGET="${SQUAD_COVERAGE_TARGET:-75}"
CMD_TARGET="${SQUAD_CMD_COVERAGE_TARGET:-$TARGET}"

if [ ! -f go.mod ]; then
	echo "NOT_A_GO_PROJECT: no go.mod in $(pwd). Report 'no Go source' honestly and stop." >&2
	: >/tmp/squad-targets.txt
	exit 0
fi

# SQUAD_SKILL_DIR is unset so `go test` does not inherit a path that some
# test helpers treat as a fixture root.
env -u SQUAD_SKILL_DIR go test ./... -coverprofile=/tmp/squad-cov.out \
	-count=1 2>&1 | tee /tmp/squad-tests.out >/dev/null || true
go tool cover -func=/tmp/squad-cov.out >/tmp/squad-funcs.out
go test -cover ./... 2>&1 | grep "coverage:" >/tmp/squad-pkg-cov.out || true

awk -v target="$TARGET" -v cmd_target="$CMD_TARGET" '
  {
    pct = 0; pkg = ""
    for (i=1; i<=NF; i++) if ($i ~ /coverage:/) { pct = $(i+1)+0 }
    for (i=1; i<=NF; i++) if ($i ~ /\//) { pkg = $i }
    if (pkg == "" || pkg ~ /^\[/) next
    tgt = (pkg ~ /\/cmd\//) ? cmd_target : target
    if (pct < tgt) printf "%s\t%.1f%%\t(target %d%%)\n", pkg, pct, tgt
  }
' /tmp/squad-pkg-cov.out | sort -t$'\t' -k2 -n >/tmp/squad-targets.txt

# Per-function hit data: <file:line>\t<pct>\t<func>  (from go tool cover -func)
grep -v '^total:' /tmp/squad-funcs.out |
	awk '{ printf "%s\t%s\t%s\n", $1, $3, $2 }' >/tmp/squad-uncovered.out || true

echo "=== overall ==="
tail -1 /tmp/squad-funcs.out
