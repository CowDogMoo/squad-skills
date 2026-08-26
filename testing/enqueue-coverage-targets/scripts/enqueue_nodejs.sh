#!/usr/bin/env bash
# Node.js / TypeScript: queue source files below target via vitest or jest.
# Called by enqueue.sh; not meant to be run alone.
set -euo pipefail
TARGET="${SQUAD_COVERAGE_TARGET:-75}"
OUT=/tmp/squad-node
mkdir -p "$OUT"

if [ ! -f package.json ]; then
	echo "NOT_A_NODE_PROJECT: no package.json in $(pwd). Report 'no Node source' honestly and stop." >&2
	: >/tmp/squad-targets.txt
	exit 0
fi

if grep -q '"vitest"' package.json; then
	TOOL=vitest
	npx vitest run --coverage --coverage.reporter=json-summary --coverage.reporter=json \
		--coverage.reportsDirectory="$OUT" 2>&1 | tee /tmp/squad-tests.out >/dev/null || true
elif grep -q '"jest"' package.json; then
	TOOL=jest
	npx jest --coverage --coverageReporters=json-summary --coverageReporters=json \
		--coverageDirectory="$OUT" 2>&1 | tee /tmp/squad-tests.out >/dev/null || true
else
	echo "NO_COVERAGE_TOOL: package.json has neither vitest nor jest. Do not install one — report it under Skipped." >&2
	: >/tmp/squad-targets.txt
	exit 0
fi

node - "$TARGET" "$OUT" "$TOOL" <<'JS'
const fs = require('fs');
const [target, out, tool] = [parseInt(process.argv[2], 10), process.argv[3], process.argv[4]];
let summary;
try { summary = JSON.parse(fs.readFileSync(`${out}/coverage-summary.json`, 'utf8')); }
catch { console.error('NO_REPORT'); fs.writeFileSync('/tmp/squad-targets.txt', ''); process.exit(0); }
const rows = [];
for (const [p, info] of Object.entries(summary)) {
  if (p === 'total') continue;
  const pct = info.statements ? info.statements.pct : 0;
  if (pct < target) rows.push([pct, p]);
}
rows.sort((a, b) => a[0] - b[0]);
fs.writeFileSync('/tmp/squad-targets.txt',
  rows.map(([pct, p]) => `${p}\t${pct.toFixed(1)}%\t(target ${target}%)`).join('\n') + (rows.length ? '\n' : ''));
console.log(`queued ${rows.length} files below ${target}% (tool=${tool})`);
if (summary.total && summary.total.statements) console.log(`overall: ${summary.total.statements.pct}%`);

// Per-function hit counts from istanbul's coverage-final.json: <file>\t<hits>\t<fn>
try {
  const cov = JSON.parse(fs.readFileSync(`${out}/coverage-final.json`, 'utf8'));
  const lines = [];
  for (const [fpath, c] of Object.entries(cov))
    for (const [id, info] of Object.entries(c.fnMap || {}))
      lines.push(`${fpath}\t${c.f[id] || 0}\t${info.name || 'anon'}`);
  fs.writeFileSync('/tmp/squad-uncovered.out', lines.join('\n') + (lines.length ? '\n' : ''));
} catch { /* optional */ }
JS
