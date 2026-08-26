---
name: score-coverage-and-report-gaps
description: Measure baseline test coverage, enumerate zero-coverage functions and untested packages, prioritize by impact, write tests, re-verify, and report the before/after delta. Use from any language-specific test-coverage agent; the caller supplies the coverage tool, idiom patterns, and target percentage.
allowed-tools: Read, Glob, Edit, Write, Bash
metadata:
  author: Jayson Grace
  version: 1.1.0
---

# Score Coverage and Report Gaps

You are working a test-coverage pass through a codebase: measure
where you are, identify the highest-impact gaps, write tests, and
re-measure. This skill gives you the five-phase loop, the discipline
rules, and the gap-analysis requirement that holds even when the
overall target is met. The caller (a language-specific test agent)
supplies the coverage tool, idiom patterns, file naming, and target
percentage.

## Inputs the caller supplies

- **Language** — Go, Python, Rust, Node/TypeScript, etc.
- **Source-file glob and filter** — already established when the
  agent participates in the pre-discovered-files contract; covered
  by `_includes/hard-rules/pre-discovered-files.md` from the
  agent's side.
- **Coverage command** — the single command that produces both a
  total percentage and a per-file/per-package breakdown:
  - Go: `go test ./... -coverprofile=coverage.out -count=1` plus
    `go tool cover -func=coverage.out`.
  - Python: `pytest --cov=<pkg> --cov-branch --cov-report=term-missing`.
  - Rust: `cargo llvm-cov` (preferred) or `cargo tarpaulin`.
  - Node: `npm test -- --coverage --passWithNoTests` or
    `npx jest --coverage`.
- **Zero-coverage enumeration command** — how to list functions
  at 0% and packages/modules with no tests at all. Caller-specific
  shell incantation (the gap-analysis Phase 1.5 step).
- **Test-file naming rule** — `_test.go`, `test_*.py` (in
  `tests/` mirroring source), inline `#[cfg(test)] mod tests` for
  Rust (never a `tests/` directory), `*.test.ts` / `*.spec.ts`.
- **Idiom patterns** — table-driven + `t.Run` for Go,
  `@pytest.mark.parametrize` for Python, `rstest` / `test-case`
  for Rust, `it.each` / `test.each` for Node. The caller's
  hard-rules section specifies which.
- **Target percentage** — usually `COVERAGE_TARGET` (default
  75%), with exceptions for entry-point/CLI code (50-60%) when
  the language has a `main`/`cmd`/`bin/` carve-out.
- **Verify command** — usually the same as the coverage command,
  but some agents also run a separate build/typecheck
  (`go build ./...`, `python -m py_compile`, `cargo build
  --tests`, `npx tsc --noEmit`).
- **Filesystem and mocking primitives** — `t.TempDir()` for Go,
  `tmp_path` fixture for Python, `tempfile::tempdir()` for Rust,
  `os.tmpdir()` / `tmp` for Node. Mock strategy is caller-
  specific (interfaces for Go, `autospec=True` for Python,
  trait-based for Rust, `jest.mock`/`vi.mock` for Node).

## Iteration budget

Scales with codebase size; caller tunes the numbers. Typical:

- **Small** (≤15-20 files): 12-15 iterations.
- **Medium** (16-50): 20-25 iterations.
- **Large** (50+): 25-35 iterations; prioritize entry points,
  business logic, public API.

**Read-then-write cadence.** Read 2-3 source files, immediately
write tests, then read 2-3 more. Never accumulate more than 5
unprocessed reads. **First test written by iteration 6.** Do not
read the whole codebase first — reasoning models exhaust output
tokens if they think too long before acting.

## Phase 0 — Use Pre-collected Data

If the orchestrator injected a `Pre-discovered source files` list,
use it (covered by the pre-discovered-files include on the agent
side). Do NOT run a redundant pass/fail test command — go straight
to the coverage measurement in Phase 1.

## Phase 1 — Measure baseline

**Phase 1 is EXACTLY ONE iteration.** Fuse the caller's coverage command and
the gap-analysis incantation into a single Bash invocation that pipes each
artifact to its own `/tmp/<artifact>.out` file. After Phase 1, do not re-run
coverage commands until Phase 4. Repeated measurement (running `go test -cover`
or `pytest --cov` multiple times with varying filters) was the dominant cost
driver in failed runs of language-specific agents. For any per-package detail
you need later, `grep` / `awk` over the saved artifact files.

1. Run the caller's coverage command, capturing output to a file.
2. Record total coverage and per-package/per-file breakdown — to files.
3. **MANDATORY gap analysis** — run even if the total exceeds the
   target. Without it, the run is a failure (the orchestrator
   needs the gap list to decide on the next stage). The caller
   provides the specific incantation; it produces three artifacts:
   - Packages/modules with no test files at all.
   - Functions at 0% coverage, ranked by file with most.
   - The top 20-30 specific zero-coverage functions by impact.

All three artifacts emerge from the SAME Bash call. After Phase 1, treat
`go test -cover` / `pytest --cov` / `cargo llvm-cov` etc. as forbidden tool
calls until Phase 4.

## Phase 2 — Prioritize

Sort the work like this:

1. **Packages/modules with no test files** — almost always the
   biggest single-step win.
2. **Files with the most zero-coverage functions** — concentrated
   gaps are cheaper to close than scattered ones.
3. **Within a file:** business logic > exported/public functions
   > non-trivial code with branches or error returns > simple
   wrappers.
4. **Entry-point exception** — `cmd/`, `bin/`, `src/index.*`,
   `main.rs` binaries get a lower target (50-60%) because they
   often legitimately can't reach the standard target without
   mocking `os.Exit` / `process.exit` / `std::process::exit`.
   Document untestable wiring instead of contorting tests to hit
   it.

## Phase 3 — Write Tests

For each priority file/package, in order:

1. Read the source file once.
2. Read any existing test file once for the project's patterns
   (assertion style, fixture conventions, naming).
3. Write tests using the caller's idiom patterns and naming rule.
   **Use Write, not Edit, for new test files** — one Write call
   replaces many fragile Edits. Use Edit only for small additions
   (≤30 lines) to existing blocks.
4. Run the per-file/per-package coverage command if the language
   supports it (`go test -cover ./<pkg>/...`,
   `pytest --cov=<mod>`, `cargo llvm-cov -p <pkg>`,
   `npx jest --coverage <path>`).
5. Below the per-file target? Write more tests. Hit the entry-
   point exception? Document the untestable functions and move on.

## Phase 4 — Verify

1. Run the full coverage command one more time.
2. Re-check the per-file/per-package breakdown. Any non-exempt
   file still below target → loop back to Phase 3 (within budget).
3. Run the separate verify command if the caller declared one
   (`go build ./...`, `cargo build --tests`, `npx tsc --noEmit`).

## Phase 5 — Report

Emit the structured report. **The coverage delta (before → after)
is mandatory** — omitting it is a failure. So is the gap-analysis
section, even on runs where the total was already above target.
The orchestrator and the human reader both need to see what
remains uncovered.

Report shape the caller assembles:

- **Coverage Report** — Target, Before, After, Delta.
- **Discovered Gaps** — modules with no test files; functions at
  0% (top 10-20 by impact).
- **Tested Packages/Modules** — per-unit before/after table with
  target and met/not-met.
- **Tests Written** — per-file list of test names.
- **Skipped Functions** — every deliberately untested function
  with a specific reason. "module requires database" /
  "file imports redis" are **invalid skip reasons** — find pure
  logic inside the file and test that; only the specific
  I/O-bound function may be skipped.
- **Files Touched** — every test file created or modified.
- **Validation** — coverage command PASS/FAIL; build command
  PASS/FAIL.

## Cross-cutting discipline rules

These hold regardless of language.

- **Only create or modify test files.** Never edit non-test
  source. If a function is untestable without changing its
  signature, skip and note why in the Skipped Functions table.
- **Tests must pass.** Run the verify command after writing; fix
  test code only.
- **No test-only interfaces / traits / protocols** added to
  source files for testability. Work with what exists.
- **No empty test files.** Every test file must have
  at least one real test function / `it` block / `func Test*`.
- **Strict 1:1 test file naming.** `foo.go` → `foo_test.go`;
  `foo.py` → `test_foo.py`; `foo.ts` → `foo.test.ts`. No
  `_extra_test`, `_coverage_test`, `.extra.test.ts` variants
  unless the framework forces them. Add to existing test files
  when present.
- **No global state swapping** of stdout/stderr/process state.
  Use the language's DI / capture primitives (`cmd.SetOut(&buf)`,
  `capsys` / `monkeypatch`, return values, `jest.spyOn` /
  `vi.spyOn`).
- **No shared mutable state between tests.** Reset mocks /
  fixtures in `beforeEach` / `t.Cleanup` / Python fixture
  teardown / Rust scope.
- **Assert on error content, not just existence.** Check the
  error message substring or pattern-match the error type — not
  just `err != nil` / `is_err()` / `expect(...).toThrow()`.
- **No variable shadowing.** Use distinct names: `got` / `want`,
  `actual` / `expected`, `result`.
- **Use the language's temp-dir primitive** for filesystem
  tests. Never write to fixed paths.
- **Coverage measurement uses the caller's exact command.**
  Don't parse coverage files directly when a summary tool exists
  (`go tool cover -func`, `cargo llvm-cov report`,
  `coverage report`, Jest's `--coverageReporters text`).
- **Always analyze gaps — even if target is met.** A run without
  the gap-analysis section is a failure regardless of total
  percentage.
- **Budget awareness.** Prefer Write over Edit for new test
  files. Cap at 20 iterations per package/module.
- **Wind-down protocol.** Approaching the iteration cap: stop
  writing, run final coverage, emit the report. A partial report
  with accurate results is infinitely better than no report.
- **STOP after verify.** Once the coverage command passes the
  final time, emit the report IMMEDIATELY in the same response.
  No extra tool calls.

## Boundary — what stays in the caller

This skill is the loop and the discipline. The caller owns:

- The exact coverage command and per-tool gap-analysis
  invocation.
- The language's idiom patterns
  (`t.Helper`/`t.Parallel`/table-driven, `pytest` fixtures and
  marks, `rstest`/`#[track_caller]`,
  `describe`/`it`/`beforeEach`).
- The test-file naming rule and placement
  (`_test.go` adjacent to source, `tests/` mirror for Python,
  inline `#[cfg(test)] mod tests` for Rust — **never** a
  `tests/` directory; `*.test.ts` adjacent).
- Mocking strategy (interfaces vs. `autospec=True` vs. trait-
  based vs. `jest.mock`).
- Language-specific assertion idioms (`assert_matches!`,
  `pytest.raises`, etc.).
- Entry-point carve-outs (`cmd/*` for Go, `bin/` and
  `src/index.*` for Node).
- The `COVERAGE_TARGET` default and any per-area overrides.
- The OUTPUT FORMAT shape (the skill specifies sections; the
  caller specifies the exact table columns and headers).

## Anti-goals

- Do NOT mock `os.Exit` / `process.exit` /
  `std::process::exit` to inflate entry-point coverage.
- Do NOT add interfaces, traits, protocols, or exports to source
  files for testability.
- Do NOT write smoke/import-only tests
  (`import X; assert X.__name__`) — they cover nothing.
- Do NOT use `git stash` / `git checkout` / `git reset` to undo
  test changes. Use Edit-to-undo, or delete the bad test file
  with Write.
- Do NOT skip an entire file because it touches I/O — find the
  pure logic inside (query builders, transforms, validation,
  config parsing) and test that. Only specific I/O-bound
  functions go in Skipped Functions.

## Examples

### Example 1 — Go service at 58%, target 75%

Caller: `agents/go-test-coverage`. Coverage command:
`go test ./... -coverprofile=coverage.out -count=1`. Target: 75%.
Cap: 20 iter.

Phase 1: baseline 58.2%. Gap analysis turns up:

- 2 packages with no `_test.go` files at all (`internal/parser/`,
  `internal/cache/`).
- 14 funcs at 0% coverage; top concentration in `internal/parser/`.

Phase 2 priority order: parser package first (no test file, most
zero-coverage funcs in one place), then cache package, then
scattered zero-coverage funcs across handlers.

Phase 3: write `internal/parser/parser_test.go` as one `Write` call
with table-driven tests (caller's idiom) — `t.Run` per case. Then
`internal/cache/cache_test.go`. Per-package coverage after each
package hits target.

Phase 4: final `go test ./... -cover` → 76.4%. Build verify
`go build ./...` → PASS.

Phase 5 report includes Delta (58.2% → 76.4%), Discovered Gaps,
Tested Packages table, Skipped Functions (4 I/O wrappers around
`os.Exit` and DB pool init), and Validation row.

### Example 2 — Total above target but gaps still required

Phase 1: total coverage 81% (above 75% target). Tempted to skip
gap analysis.

Action: run the gap analysis anyway. The MANDATORY rule fires
regardless of total. Find that 3 modules have 100% but 2 modules
have 0% — the average hides the bimodal split. Report them in
Discovered Gaps so the orchestrator can decide whether to do a
targeted pass on the untested modules.

### Example 3 — Python package with entry-point carve-out

Caller: `agents/python-test-coverage`. Source includes `cli/main.py`
which wires `argparse` to handlers and calls `sys.exit`.

Phase 2 priority: write tests for the handler functions (pure
logic). Mark `main()` itself as entry-point exception (50-60%
target, not 75%).

Phase 3: tests cover the handlers via direct imports. `main()` is
covered partially through `runpy`-style invocation but stays under
60% because `sys.exit` paths can't be exercised without mocking
(forbidden by hard rule).

Phase 5 Skipped Functions notes `main` with reason
"entry-point/CLI carve-out; sys.exit unmockable".

## Troubleshooting

### Error: Gap-analysis section missing from report

**Symptom:** Report has coverage delta but no "Discovered Gaps"
section.

**Cause:** Phase 1.5 was skipped because the total exceeded target.

**Solution:** The gap analysis is MANDATORY regardless of total.
Re-run the caller's zero-coverage enumeration command and append a
Discovered Gaps section before emitting the report. A run without it
is a failure even if the percentage is great.

### Error: Tempted to mock `os.Exit` / `process.exit` / `std::process::exit`

**Symptom:** Entry-point file (`cmd/`, `main.rs`, `src/index.*`,
`bin/`) below target; the only way to hit more lines is to mock
process exit.

**Solution:** Don't. Hard rule. Apply the entry-point carve-out
(50-60%) and document the unmockable lines in Skipped Functions.
Mocking process exit produces tests that pass without verifying
real behavior.

### Error: Wrote a test-only interface/trait into source code

**Symptom:** Source file gained a new interface/trait/protocol whose
only consumer is the test file.

**Cause:** Cross-cutting rule "No test-only interfaces" violated.

**Solution:** Revert the source-file change. Use whatever exists in
the source today, or skip the function and document why. Adding
testability scaffolding is out of scope — the skill's job is to
write tests against existing code.

### Error: Empty test file in the diff

**Symptom:** A `*_test.go` / `test_*.py` / `*.test.ts` file exists
with imports but no actual `Test*` / `it` / `test` block.

**Cause:** Iteration ran out mid-write or model batched
incorrectly.

**Solution:** Either complete the
file with at least one real test, or delete it. The verify command
won't catch this on its own (zero tests is "passing"); the human
reader will reject the diff.

### Error: Iteration cap hit before final verify

**Symptom:** Out of iterations with tests still being written.

**Solution:** Apply the wind-down protocol. Stop writing. Run the
final coverage command. Emit the report with whatever the current
delta is and a Skipped Functions section listing what didn't get
done due to budget. A partial accurate report beats no report.

### Error: Skipped a whole file because "it touches the database"

**Symptom:** File added to Skipped Functions with reason
"requires DB" or "I/O-bound".

**Cause:** Invalid skip reason.

**Solution:** Open the file. Find the pure logic — query builders,
transforms, validation, config parsing, error formatters — and test
those. Only the specific I/O-bound function (the one that actually
opens the connection) is a legitimate skip. The rest of the file is
fair game.
