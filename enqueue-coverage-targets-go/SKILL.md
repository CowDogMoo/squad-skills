---
name: enqueue-coverage-targets-go
description: "Orchestrator-workers pattern for Go test coverage: a deterministic Bash command queues packages below target into /tmp/squad-targets.txt, then you drain it by reading source and writing _test.go files. Load on iteration 1 of any Go coverage-raising agent run."
allowed-tools: Bash, Read, Write, Edit
metadata:
  author: Jayson Grace
  version: 1.0.0
---

# Enqueue Coverage Targets (Go)

You are entering an **orchestrator-workers** pattern (Anthropic, "Building
Effective Agents"). The orchestrator is this skill plus the Bash command
below. The worker is you, after Step 1.

The pattern exists because every previous attempt at letting the agent
discover gaps autonomously ended the same way: 40+ iterations of measuring,
0 tests written. Discovery is deterministic — it does not need a reasoning
model. The model's job is the part that needs reasoning: writing tests
that exercise real code paths.

# Step 1 — Orchestrator (your iteration immediately after this skill call)

Your **next tool call** must be this exact Bash command, verbatim:

```bash
set -e
env -u SQUAD_SKILL_DIR go test ./... -coverprofile=/tmp/squad-cov.out \
  -count=1 2>&1 | tee /tmp/squad-tests.out >/dev/null
go tool cover -func=/tmp/squad-cov.out > /tmp/squad-funcs.out
go test -cover ./... 2>&1 | grep "coverage:" > /tmp/squad-pkg-cov.out
TARGET="${SQUAD_COVERAGE_TARGET:-75}"
awk -v target="$TARGET" '
  {
    pct = 0; pkg = ""
    for (i=1; i<=NF; i++) if ($i ~ /coverage:/) { pct = $(i+1)+0 }
    for (i=1; i<=NF; i++) if ($i ~ /github\.com/) { pkg = $i }
    if (pkg == "") next
    tgt = (pkg ~ /\/cmd\//) ? 50 : target
    if (pct < tgt) printf "%s\t%.1f%%\t(target %d%%)\n", pkg, pct, tgt
  }
' /tmp/squad-pkg-cov.out | sort -t$'\t' -k2 -n > /tmp/squad-targets.txt
echo "=== /tmp/squad-targets.txt (worker queue) ==="
cat /tmp/squad-targets.txt
echo "=== overall ==="; tail -1 /tmp/squad-funcs.out
echo "=== queue size ==="; wc -l < /tmp/squad-targets.txt
```

Export `SQUAD_COVERAGE_TARGET` to your run's target percent before invoking,
or it defaults to 75. (e.g. add `export SQUAD_COVERAGE_TARGET=95` at the top.)

`/tmp/squad-targets.txt` columns are tab-separated: `<pkg>\t<pct>%\t(target N%)`.
Sorted ascending by current coverage so the worst packages are first.

# Step 2 — Worker mode (every iteration after Step 1)

Read `/tmp/squad-targets.txt` once. That list is your queue. Drain it in
batches of 3–5 packages until empty OR you have used 80% of your cost
budget OR you have used 80% of your iteration budget.

For each batch:

1. **Read iteration:** parallel `Read` calls per package in the batch:
   - **One or two `.go` source files** (largest by line count). Confirm
     the package's actual on-disk import path (look at the file header
     and your earlier `go list` output) and the names/signatures of the
     functions you intend to test. Do NOT guess import paths or symbol
     names from package name alone.
   - **Every existing `_test.go` in that package.** You MUST know what
     is already tested before you write anything. Skipping this step is
     how previous runs deleted thousands of lines of working tests.
2. **Write/Edit iteration:** parallel calls, one per package in the batch.
   - If a `_test.go` for the target source file **already exists**, use
     `Edit` (or a new `_test.go` for a different source file in the
     same package) to ADD test functions. **Never `Write` over an
     existing `_test.go` — `Write` truncates the file and destroys the
     existing tests.**
   - If no `_test.go` exists for the target source file, use `Write` to
     create one named per the 1:1 rule (`foo.go` → `foo_test.go`).
   - Every new function must reference symbols you actually saw in
     Step 1's source read. If you couldn't confirm a symbol exists,
     don't reference it.
   - Each file must contain at least one real `func Test*(t *testing.T)`
     with meaningful assertions on the package's lowest-coverage
     functions. Empty stubs are forbidden.
3. Move to the next batch. Do NOT re-measure coverage between batches.

Aim for 3+ packages per Write/Edit iteration. Single-package iterations
are wasteful — you have ~25 iterations and a long queue.

# Step 3 — Verify and report (last 2–3 iterations)

Run `go build ./...` then `go test ./...` once. Fix only test code on
failure.

**Re-measurement is mandatory for the "After" coverage number.** Run
`go test -cover ./... 2>&1 | grep "coverage:"` and copy real package
percentages into your report. If you skip this step, the "After"
column MUST say "not measured" — never invent a percentage based on
what the tests "should" achieve.

Then emit the caller's OUTPUT FORMAT report. The report is a transcript
of your work, not a projection:

- **Files Touched** lists only files you actually `Write`'d or
  `Edit`'d this run. A file you only `Read` does not belong here.
- **Tests Added / Tests Written** count only `func Test*` you
  appended this run. Read-only files contribute 0.
- **After %** is from the re-measurement above, or "not measured".
  Never fabricate.

# Hard constraints (these override your judgment)

- **Only `_test.go` files** with `Write` / `Edit`. Source edits are out of
  scope; document required source changes under Skipped Functions.
- **Never destroy existing tests.** `Write` truncates. Before any `Write`
  on an existing path, you must have read its current contents and be
  preserving every `Test*` function in it. Default to `Edit` for any
  `_test.go` that already exists. If you absolutely must `Write` over an
  existing test file (e.g. a wholesale restructure), every prior
  `Test*` function must appear in the new contents.
- **`Edit` failed → re-Read, fix the anchor, retry `Edit`. NEVER fall
  back to `Write` on a file you just tried to `Edit`.** "Text not
  found" means your `old_string` is wrong, not that the file should
  be overwritten. Three failed Edit attempts on the same file → skip
  the package and document it under Skipped Functions. Falling back
  to `Write` here is how previous runs destroyed working tests.
- **Verify before you reference.** Import paths and symbol names must
  come from a file you actually read in Step 1, not from the package
  name or your prior assumptions. A test that won't compile costs more
  than the test would have earned in coverage.
- **No coverage commands during writing.** `go test -cover`,
  `go test -coverprofile`, and `go tool cover` are forbidden between
  Step 1 and Step 3. The queue in `/tmp/squad-targets.txt` is your sole
  source of truth.
- **Do not load `Skill("score-coverage-and-report-gaps")`.** That skill's
  five-phase loop is what you're replacing — it gave the agent permission
  to over-discover.
- **Imports must be complete.** When you reference `runtime.GOOS`, import
  `"runtime"`. When you use `filepath.Join`, import `"path/filepath"`.
  Missing imports are the #1 quality bug.
- **Black-box `package foo_test`** by default; table-driven `[]struct` +
  `t.Run` for 2+ cases; `t.TempDir()` for files; no global state swapping.

# Why this pattern works

The previous agent shape (let the LLM decide what to measure, what to
prioritize, when to start writing) failed every run: 30–50 iterations on
measurement, 0–3 tests written. The bug isn't the prompt — it's the agent
having discretion over a step that doesn't need discretion. This skill
takes that discretion away by:

1. Embedding the exact Bash command for discovery (deterministic).
2. Constraining post-Step-1 tool use to Read / Write / Edit (no coverage
   commands until final verify).
3. Defining a fixed batch shape (Read iter → Write iter → repeat) so the
   agent can't get stuck in single-package over-thoroughness.

The model's reasoning is reserved for the only part of the task that
needs it: writing test code that exercises specific functions.
