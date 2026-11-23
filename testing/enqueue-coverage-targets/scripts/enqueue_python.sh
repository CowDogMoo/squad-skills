#!/usr/bin/env bash
# Python: queue modules below target via pytest --cov.
# Called by enqueue.sh; not meant to be run alone.
set -euo pipefail
TARGET="${SQUAD_COVERAGE_TARGET:-75}"
PKG="${SQUAD_PYTHON_PKG:-.}"

if [ -z "$(find . -name '*.py' -not -path '*/.venv/*' -not -path '*/__pycache__/*' -not -path '*/node_modules/*' -print -quit 2>/dev/null)" ]; then
	echo "NOT_A_PYTHON_PROJECT: no .py source in $(pwd). Report 'no Python source' honestly and stop." >&2
	: >/tmp/squad-targets.txt
	exit 0
fi

# Keep coverage data and the pytest cache out of the project so the run also
# works on a read-only checkout and leaves no .coverage file behind.
export COVERAGE_FILE=/tmp/squad-coverage-data
python -m pytest -p no:cacheprovider --cov="$PKG" --cov-branch --cov-report=term-missing \
	--cov-report=json:/tmp/squad-cov.json -q 2>&1 | tee /tmp/squad-tests.out >/dev/null || true

python - "$TARGET" <<'PY'
import json, sys
target = int(sys.argv[1])
try:
    data = json.load(open('/tmp/squad-cov.json'))
except FileNotFoundError:
    print('NO_COVERAGE_DATA: pytest-cov is not installed or produced no report. Do not install it — report it under Skipped.', file=sys.stderr)
    open('/tmp/squad-targets.txt', 'w').close()
    sys.exit(0)
import re
# Test code is never a queue unit: with --cov=. the suite measures itself.
is_test = re.compile(r'(^|/)(tests?|testing)/|(^|/)(test_[^/]*|[^/]*_test|conftest)\.py$').search
files = {p: i for p, i in data.get('files', {}).items() if not is_test(p)}
rows = sorted((info.get('summary', {}).get('percent_covered', 0), path)
              for path, info in files.items())
with open('/tmp/squad-targets.txt', 'w') as f:
    for pct, path in rows:
        if pct < target:
            f.write(f'{path}\t{pct:.1f}%\t(target {target}%)\n')
# Per-line uncovered statements: <file>:<line>
with open('/tmp/squad-uncovered.out', 'w') as out:
    for path, info in files.items():
        for ln in info.get('missing_lines', []):
            out.write(f'{path}:{ln}\n')
print(f"queued {sum(1 for p,_ in rows if p < target)} modules below {target}%")
print(f"overall: {data.get('totals', {}).get('percent_covered', 0):.1f}%")
PY
