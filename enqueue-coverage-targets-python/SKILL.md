---
name: enqueue-coverage-targets-python
description: "Orchestrator-workers pattern for Python test coverage: a deterministic Bash command runs pytest --cov and queues modules below target into /tmp/squad-targets.txt, then you drain it by writing test_*.py files. Load on iteration 1 of any Python coverage-raising agent run."
allowed-tools: Bash, Read, Write, Edit
metadata:
  author: Jayson Grace
  version: 1.0.0
---

# Enqueue Coverage Targets (Python)

You are entering an **orchestrator-workers** pattern (Anthropic, "Building Effective Agents"). The orchestrator is this skill plus the Bash command below. The worker is you, after Step 1.

This pattern exists because every previous attempt at letting the agent discover gaps autonomously ended the same way: 30+ iterations of measuring, 0 tests written. Discovery is deterministic — it does not need a reasoning model. The model's job is the part that needs reasoning: writing tests that exercise real code paths.

# Step 1 — Orchestrator (your iteration immediately after this skill call)

Your **next tool call** must be this exact Bash command, verbatim:

```bash
set -e
TARGET="${SQUAD_COVERAGE_TARGET:-75}"
PKG="${SQUAD_PYTHON_PKG:-.}"
# Clear stale queue from prior runs of other-language agents.
rm -f /tmp/squad-targets.txt
# Language gate: refuse to proceed if no Python source exists.
if [ -z "$(find . -name '*.py' -not -path '*/.venv/*' -not -path '*/__pycache__/*' -not -path '*/node_modules/*' -print -quit 2>/dev/null)" ]; then
  echo "NOT_A_PYTHON_PROJECT: no .py source files in $(pwd). This agent only works in Python projects. Stop here and emit an honest 'no Python source' report — do NOT pivot to other languages." >&2
  echo "" > /tmp/squad-targets.txt
  echo "=== queue size ==="; echo 0
  exit 0
fi
python -m pytest --cov="$PKG" --cov-branch --cov-report=term-missing \
  --cov-report=json:/tmp/squad-cov.json -q 2>&1 \
  | tee /tmp/squad-tests.out > /dev/null || true
python -c "
import json, sys
try:
    with open('/tmp/squad-cov.json') as f:
        data = json.load(f)
except FileNotFoundError:
    print('NO_COVERAGE_DATA', file=sys.stderr); sys.exit(0)
target = int('${TARGET}')
rows = []
for path, info in data.get('files', {}).items():
    pct = info.get('summary', {}).get('percent_covered', 0)
    if pct < target:
        rows.append((pct, path))
rows.sort()
with open('/tmp/squad-targets.txt', 'w') as f:
    for pct, path in rows:
        f.write(f'{path}\t{pct:.1f}%\t(target {target}%)\n')
print(f'queued {len(rows)} modules below {target}%')
totals = data.get('totals', {})
print(f\"overall: {totals.get('percent_covered', 0):.1f}%\")
"
python -c "
import json
try:
    d = json.load(open('/tmp/squad-cov.json'))
except FileNotFoundError:
    raise SystemExit(0)
# Per-line uncovered targets file — for test-writer-honesty §14
# (mechanical target selection). Format: <file>:<line>
with open('/tmp/squad-uncovered.out', 'w') as out:
    for path, info in d.get('files', {}).items():
        for ln in info.get('missing_lines', []):
            out.write(f'{path}:{ln}\n')
" 2>/dev/null || true
echo "=== /tmp/squad-targets.txt (worker queue) ==="
cat /tmp/squad-targets.txt 2>/dev/null || echo "(empty queue)"
echo "=== queue size ==="
wc -l < /tmp/squad-targets.txt 2>/dev/null || echo 0
```

Export `SQUAD_COVERAGE_TARGET` to your run's target percent before invoking, or it defaults to 75. Export `SQUAD_PYTHON_PKG` to the package name your project covers (e.g. `myapp`), or it defaults to `.` (current directory).

`/tmp/squad-targets.txt` columns are tab-separated: `<source-file-path>\t<pct>%\t(target N%)`. Sorted ascending by current coverage so the worst-covered files are first.

If `pytest --cov` is not installed, the JSON file won't exist and the queue will be empty — your job becomes documenting the missing tool under Skipped Functions and exiting honestly. Do NOT install packages on the user's system.

# Step 1a — Mechanical target selection (for test-writer-honesty §14)

The Step-1 command also wrote `/tmp/squad-uncovered.out` (one
`<file>:<line>` per uncovered statement). Before writing any test for a
queue module `<file>`, run:

```bash
grep -F "<file>:" /tmp/squad-uncovered.out | head -15
```

Target tests at the lines in that list — they're the lines the existing
test suite does NOT execute. Writing tests for already-covered code is
how prior runs added many tests and moved coverage 0%.

# Step 2 — Worker mode (every iteration after Step 1)

Read `/tmp/squad-targets.txt` once. That list is your queue. Drain it in batches of 3–5 modules until empty OR you have used 80% of your cost budget OR 80% of your iteration budget.

For each batch:

1. **Read iteration:** parallel `Read` calls per module in the batch:
   - The source file from the queue (e.g. `myapp/foo.py`). Confirm the module path and the names/signatures of the functions you'll test.
   - **Every existing `test_*.py` for that module** (mirrored at `tests/test_foo.py` or `tests/<subpkg>/test_foo.py`). Skipping this is how previous runs destroyed working tests.
2. **Write/Edit iteration:** parallel calls, one per module in the batch:
   - If a `test_*.py` for the target module already exists, use `Edit` to ADD test functions. **Never `Write` over an existing `test_*.py` — `Write` truncates the file and destroys the existing tests.**
   - If no `test_*.py` exists for the target module, use `Write` to create one named per the mirror rule (`myapp/core/store.py` → `tests/core/test_store.py`).
   - Every name your test references must appear in source you actually read this iteration. Don't guess module paths or symbol names.
   - Each file must contain at least one real `def test_*` with meaningful assertions on the lowest-coverage functions. Empty stubs are forbidden.
3. Move to the next batch. Do NOT re-measure coverage between batches.

Aim for 3+ modules per Write/Edit iteration. Single-module iterations are wasteful.

# Step 3 — Verify and report (last 2–3 iterations)

Run `python -m pytest -q` then `python -m py_compile <changed files>`. Fix only test code on failure.

**Re-measurement is mandatory for the "After" coverage number.** Re-run the Step-1 command and copy real per-file percentages into your report. If you skip this step, the "After" column MUST say "not measured" — never invent a percentage based on what the tests "should" achieve.

# Hard constraints (these override your judgment)

- **Only `test_*.py` files** with `Write` / `Edit`. Source edits are out of scope; document required source changes under Skipped Functions.
- **Never destroy existing tests.** `Write` truncates. Before any `Write` on an existing path, you must have read its current contents and be preserving every `def test_*` in it. Default to `Edit` for any `test_*.py` that already exists.
- **`Edit` failed → re-Read, fix the anchor, retry `Edit`. NEVER fall back to `Write` on a file you just tried to `Edit`.** "Text not found" means your `old_string` is wrong, not that the file should be overwritten. Three failed `Edit` attempts on the same file → skip the module and document it under Skipped Functions.
- **No coverage commands during writing.** Re-running `pytest --cov` between batches is forbidden. The queue in `/tmp/squad-targets.txt` is your sole source of truth until Step 3.
- **Do not load `Skill("score-coverage-and-report-gaps")`.** That skill's five-phase loop is what you're replacing.
- **Imports must be complete.** When you reference `pathlib.Path`, import it. Missing imports are a top quality bug.
- **`pytest` idiom** by default; fixtures, `tmp_path`, `monkeypatch`; `@pytest.mark.parametrize` with `pytest.param(..., id="name")` for 2+ cases.

# Why this pattern works

The previous agent shape (let the LLM decide what to measure, what to prioritize, when to start writing) failed every run: 30–50 iterations on measurement, 0–3 tests written. The bug isn't the prompt — it's the agent having discretion over a step that doesn't need discretion. This skill takes that discretion away by:

1. Embedding the exact Bash command for discovery (deterministic).
2. Constraining post-Step-1 tool use to Read / Write / Edit (no coverage commands until final verify).
3. Defining a fixed batch shape (Read iter → Write iter → repeat) so the agent can't get stuck in single-module over-thoroughness.

The model's reasoning is reserved for the only part of the task that needs it: writing test code that exercises specific functions.
