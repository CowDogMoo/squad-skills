---
name: enqueue-coverage-targets-nodejs
description: "Orchestrator-workers pattern for Node.js/TypeScript test coverage: a deterministic Bash command runs vitest/jest --coverage and queues source files below target into /tmp/squad-targets.txt, then you drain it by writing *.test.ts files. Load on iteration 1 of any Node.js coverage-raising agent run."
allowed-tools: Bash, Read, Write, Edit
metadata:
  author: Jayson Grace
  version: 1.0.0
---

# Enqueue Coverage Targets (Node.js / TypeScript)

You are entering an **orchestrator-workers** pattern (Anthropic, "Building Effective Agents"). The orchestrator is this skill plus the Bash command below. The worker is you, after Step 1.

The pattern exists because every previous attempt at letting the agent discover gaps autonomously ended the same way: 30+ iterations of measuring, 0 tests written. Discovery is deterministic — it does not need a reasoning model. The model's job is the part that needs reasoning: writing tests that exercise real code paths.

# Step 1 — Orchestrator (your iteration immediately after this skill call)

Your **next tool call** must be this exact Bash command, verbatim:

```bash
set -e
TARGET="${SQUAD_COVERAGE_TARGET:-75}"
mkdir -p /tmp/squad-node
# Clear stale queue from prior runs of other-language agents.
rm -f /tmp/squad-targets.txt
# Language gate: refuse to proceed if this isn't a Node project.
if [ ! -f package.json ]; then
  echo "NOT_A_NODE_PROJECT: no package.json in $(pwd). This agent only works in Node.js/TypeScript projects. Stop here and emit an honest 'no source' report — do NOT pivot to other languages." >&2
  echo "" > /tmp/squad-targets.txt
  echo "=== queue size ==="; echo 0
  exit 0
fi
if [ -f package.json ]; then
  if grep -q '"vitest"' package.json 2>/dev/null; then
    npx vitest run --coverage --coverage.reporter=json-summary --coverage.reporter=json \
      --coverage.reportsDirectory=/tmp/squad-node 2>&1 \
      | tee /tmp/squad-tests.out > /dev/null || true
    REPORT=/tmp/squad-node/coverage-summary.json
    TOOL=vitest
  elif grep -q '"jest"' package.json 2>/dev/null; then
    npx jest --coverage --coverageReporters=json-summary --coverageReporters=json \
      --coverageDirectory=/tmp/squad-node 2>&1 \
      | tee /tmp/squad-tests.out > /dev/null || true
    REPORT=/tmp/squad-node/coverage-summary.json
    TOOL=jest
  else
    echo "NO_COVERAGE_TOOL: package.json has neither vitest nor jest" >&2
    REPORT=""
    TOOL=none
  fi
else
  echo "NO_PACKAGE_JSON: not a Node project" >&2
  REPORT=""
  TOOL=none
fi
node -e "
const fs = require('fs');
const target = parseInt(process.argv[1], 10);
const report = process.argv[2];
const tool = process.argv[3];
let data;
try { data = JSON.parse(fs.readFileSync(report, 'utf8')); }
catch (e) { console.error('NO_REPORT'); process.exit(0); }
const rows = [];
for (const [path, info] of Object.entries(data)) {
  if (path === 'total') continue;
  const pct = info.statements ? info.statements.pct : 0;
  if (pct < target) rows.push([pct, path]);
}
rows.sort((a, b) => a[0] - b[0]);
const lines = rows.map(([pct, p]) => p + '\t' + pct.toFixed(1) + '%\t(target ' + target + '%)');
fs.writeFileSync('/tmp/squad-targets.txt', lines.join('\n') + (lines.length ? '\n' : ''));
console.log('queued ' + rows.length + ' files below ' + target + '% (tool=' + tool + ')');
if (data.total && data.total.statements) console.log('overall: ' + data.total.statements.pct + '%');
" "$TARGET" "$REPORT" "$TOOL" 2>&1 || echo "report-parse-failed"
node -e "
const fs = require('fs');
let cov;
try { cov = JSON.parse(fs.readFileSync('/tmp/squad-node/coverage-final.json', 'utf8')); }
catch (e) { process.exit(0); }
// Per-function uncovered targets file — for test-writer-honesty §14
// (mechanical target selection). Format: <file>\t<hit-count>\t<fn-name>
const out = fs.createWriteStream('/tmp/squad-uncovered.out');
for (const [fpath, c] of Object.entries(cov)) {
  for (const [id, info] of Object.entries(c.fnMap || {})) {
    out.write(\`\${fpath}\\t\${c.f[id] || 0}\\t\${info.name || 'anon'}\\n\`);
  }
}
out.end();
" 2>/dev/null || true
echo "=== /tmp/squad-targets.txt (worker queue) ==="
cat /tmp/squad-targets.txt 2>/dev/null || echo "(empty queue)"
echo "=== queue size ==="
wc -l < /tmp/squad-targets.txt 2>/dev/null || echo 0
```

Export `SQUAD_COVERAGE_TARGET` to your run's target percent before invoking, or it defaults to 75. The script auto-detects `vitest` (preferred) or `jest` from `package.json`.

`/tmp/squad-targets.txt` columns are tab-separated: `<source-file-path>\t<pct>%\t(target N%)`. Sorted ascending by current coverage so the worst-covered files are first.

If neither test framework is present, the queue will be empty — document the missing tool under Skipped Functions and exit honestly. Do NOT install packages on the user's system.

# Step 1a — Mechanical target selection (for test-writer-honesty §14)

The Step-1 command also wrote `/tmp/squad-uncovered.out` (per-function
hit counts from istanbul's `coverage-final.json`). Before writing any
test for a queue source file `<file>`, run:

```bash
grep -F "<file>" /tmp/squad-uncovered.out | sort -k2 -n | head -8
```

Test ONLY the FIRST 3-5 listed functions (those with the LOWEST hit
counts). Functions not in that top-8 are FORBIDDEN targets per §14.

# Step 2 — Worker mode (every iteration after Step 1)

Read `/tmp/squad-targets.txt` once. That list is your queue. Drain it in batches of 3–5 files until empty OR you have used 80% of your cost budget OR 80% of your iteration budget.

For each batch:

1. **Read iteration:** parallel `Read` calls per file in the batch:
   - The source file from the queue (e.g. `src/utils/parse.ts`). Confirm the file path and the exports you'll test.
   - **Every existing `*.test.ts` / `*.test.js` / `*.spec.ts` for that source.** Check both adjacent (`src/utils/parse.test.ts`) and `__tests__` directory layouts. Skipping this is how previous runs destroyed working tests.
2. **Write/Edit iteration:** parallel calls, one per file in the batch:
   - If a test file for the target source already exists, use `Edit` to ADD test functions. **Never `Write` over an existing test file — `Write` truncates the file and destroys the existing tests.**
   - If no test file exists, use `Write` to create one. Follow the project's existing convention (adjacent `.test.ts` vs `__tests__/`); if no convention is established, prefer adjacent `.test.ts`.
   - Every name your test references must appear in source you actually read this iteration. Don't guess module paths, default-vs-named exports, or symbol names.
   - Each file must contain at least one real `test(...)`/`it(...)` (or `describe` with nested `test`) with meaningful assertions on the lowest-coverage code paths. Empty stubs are forbidden.
3. Move to the next batch. Do NOT re-measure coverage between batches.

Aim for 3+ files per Write/Edit iteration. Single-file iterations are wasteful.

# Step 3 — Verify and report (last 2–3 iterations)

Run the project's build check (`npx tsc --noEmit` if TypeScript) and the test runner (`npx vitest run` or `npx jest`). Fix only test code on failure.

**Re-measurement is mandatory for the "After" coverage number.** Re-run the Step-1 command and copy real per-file percentages into your report. If you skip this step, the "After" column MUST say "not measured" — never invent a percentage.

# Hard constraints (these override your judgment)

- **Only test files** (`*.test.ts`, `*.test.js`, `*.spec.ts`, files under `__tests__/`) with `Write` / `Edit`. Source edits are out of scope; document required source changes under Skipped Functions.
- **Never destroy existing tests.** `Write` truncates. Before any `Write` on an existing path, you must have read its current contents and be preserving every `test(...)` / `it(...)` / `describe(...)` in it. Default to `Edit` for any test file that already exists.
- **`Edit` failed → re-Read, fix the anchor, retry `Edit`. NEVER fall back to `Write` on a file you just tried to `Edit`.** "Text not found" means your `old_string` is wrong, not that the file should be overwritten. Three failed `Edit` attempts on the same file → skip the module and document it under Skipped Functions.
- **No coverage commands during writing.** Re-running `vitest --coverage`/`jest --coverage` between batches is forbidden. The queue in `/tmp/squad-targets.txt` is your sole source of truth until Step 3.
- **Do not load `Skill("score-coverage-and-report-gaps")`.** That skill's five-phase loop is what you're replacing.
- **Imports complete.** Match the project's module system (ESM vs CommonJS). Distinguish default vs named exports. Missing or mis-cased imports are a top quality bug.
- **Idiom:** `describe`/`test`/`expect` (vitest or jest); `vi.mock`/`jest.mock` for module mocks; `beforeEach`/`afterEach` for setup; `test.each`/`it.each` for parameterized tests.

# Why this pattern works

The previous agent shape (let the LLM decide what to measure, what to prioritize, when to start writing) failed every run: 30–50 iterations on measurement, 0–3 tests written. The bug isn't the prompt — it's the agent having discretion over a step that doesn't need discretion. This skill takes that discretion away by:

1. Embedding the exact Bash command for discovery (deterministic).
2. Constraining post-Step-1 tool use to Read / Write / Edit (no coverage commands until final verify).
3. Defining a fixed batch shape (Read iter → Write iter → repeat) so the agent can't get stuck in single-file over-thoroughness.

The model's reasoning is reserved for the only part of the task that needs it: writing test code that exercises specific functions.
