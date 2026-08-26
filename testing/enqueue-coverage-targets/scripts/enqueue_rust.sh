#!/usr/bin/env bash
# Rust: queue source files below target via cargo-llvm-cov (preferred) or tarpaulin.
# Called by enqueue.sh; not meant to be run alone.
set -euo pipefail
TARGET="${SQUAD_COVERAGE_TARGET:-75}"
OUT=/tmp/squad-rust
mkdir -p "$OUT"

if [ ! -f Cargo.toml ] && [ ! -f Cargo.lock ]; then
	echo "NOT_A_RUST_PROJECT: no Cargo.toml in $(pwd). Report 'no Rust source' honestly and stop." >&2
	: >/tmp/squad-targets.txt
	exit 0
fi

if command -v cargo-llvm-cov >/dev/null 2>&1; then
	TOOL=llvm-cov
	cargo llvm-cov --json --output-path "$OUT/cov.json" --quiet 2>&1 | tee /tmp/squad-tests.out >/dev/null || true
elif command -v cargo-tarpaulin >/dev/null 2>&1; then
	TOOL=tarpaulin
	cargo tarpaulin --out Json --output-dir "$OUT" --quiet 2>&1 | tee /tmp/squad-tests.out >/dev/null || true
else
	echo "NO_COVERAGE_TOOL: neither cargo-llvm-cov nor cargo-tarpaulin is installed. Do not install one — report it under Skipped." >&2
	: >/tmp/squad-targets.txt
	exit 0
fi

python3 - "$TARGET" "$TOOL" "$OUT" <<'PY'
import json, sys
target, tool, out = int(sys.argv[1]), sys.argv[2], sys.argv[3]
rows, fns = [], []
try:
    if tool == "llvm-cov":
        data = json.load(open(f"{out}/cov.json"))
        for fr in data.get("data", []):
            for fl in fr.get("files", []):
                rows.append((fl.get("summary", {}).get("lines", {}).get("percent", 0), fl["filename"]))
            for fn in fr.get("functions", []):
                for fname in fn.get("filenames", []):
                    fns.append((fname, fn.get("count", 0), fn["name"]))
    else:
        data = json.load(open(f"{out}/tarpaulin-report.json"))
        for fname, info in data.get("files", {}).items():
            total = info.get("coverable", 0) or 1
            rows.append((100.0 * info.get("covered", 0) / total, fname))
            for tr in info.get("traces", []):
                fns.append((fname, tr.get("stats", {}).get("Line", 0), f"line:{tr.get('line', 0)}"))
except (FileNotFoundError, KeyError, json.JSONDecodeError):
    pass
rows.sort()
with open("/tmp/squad-targets.txt", "w") as f:
    for pct, path in rows:
        if pct < target:
            f.write(f"{path}\t{pct:.1f}%\t(target {target}%)\n")
# <file>\t<hit-count>\t<fn-or-line>
with open("/tmp/squad-uncovered.out", "w") as f:
    for fname, count, name in fns:
        f.write(f"{fname}\t{count}\t{name}\n")
print(f"queued {sum(1 for p,_ in rows if p < target)} files below {target}% (tool={tool})")
PY
