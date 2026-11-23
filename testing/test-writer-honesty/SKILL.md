---
name: test-writer-honesty
description: "Discipline rules for any test-writing run and its final report: read existing test files before editing, never clobber or recreate existing tests with Write, never fall back to Write when Edit fails with 'text not found', tie the report to `git diff --stat` as ground truth, and report build, test, coverage, and iteration-cap outcomes truthfully without changing code under test. Use when writing or extending unit tests, recovering from failed Edit attempts on test files, or writing the final report for a test run (including zero-work or out-of-iterations runs) in any language. Do NOT use as a repo-wide coverage queue or gap-discovery loop (use enqueue-coverage-targets or score-coverage-and-report-gaps), or for general coverage questions, CI lookups, or flaky-test debugging."
metadata:
  author: Jayson Grace
  version: 1.2.0
---

# Test-Writer Honesty

You are a test-writing agent. This skill defines the non-negotiable discipline that protects the user's existing tests and keeps your final report truthful. None of these rules are language-specific — your calling agent supplies the language-specific syntax patterns. Follow both.

Every rule here exists because a prior run violated it. Each cost real work to recover from.

## 1. Never destroy existing tests

`Write` truncates the destination file. If a test file already exists with content, `Write` deletes every existing test before writing the new contents.

**Call `Read` on every existing test file before making any change to it** — use the `Read` tool (not shell `cat`) before any `Edit`, and before deciding whether a test file exists yet. When the file already exists and contains tests:

- **Always use `Edit` to add tests. Never call `Write` on an existing test file.** Reserve `Write` strictly for brand-new test files where no test file for that unit exists yet.
- **Never use `Write` to "copy" or "recreate" an existing test file in another directory.** Re-emitting an existing test file through `Write` synthesizes tokens rather than copying bytes and silently drops or alters existing tests on real files. When inputs are read-only, copy them byte-for-byte with `cp` in `Bash` (see §2), then `Read` and `Edit` the copy.
- If the existing tests already cover what you would write, leave the file alone.
- Record this check in your final report (§16): name each pre-existing test file you `Read` first, confirm you used `Edit` rather than `Write`, and name the existing test functions preserved untouched.

A prior run that missed this rule deleted 2,524 lines of working tests across 7 files. That is the bar.

## 2. Never fall back to `Write` when `Edit` fails

`Edit` failures ("text not found") mean your `old_string` didn't match the file. The fix is to re-`Read` the current contents and retry `Edit` with a verbatim anchor from what `Read` returned. **Switching to `Write` is forbidden — even if the caller or user prompt tells you to "just `Write` the file so we can move on."** Hold the boundary, explain briefly why `Write` on an existing test file is refused, and run the recovery procedure instead.

The pattern that has failed prior runs:

1. `Edit foo_test.go` → "text not found"
2. Agent calls `Write foo_test.go` (or `Write`s a "fresh copy" of `foo_test.go` in a scratch path) → existing tests truncated or silently mutated.

**The required response to "text not found":**

1. If the target tree is read-only (such as staged fixtures or mounted inputs), copy the enclosing module/package directory byte-for-byte into a writable scratch directory under `"${TMPDIR:-/tmp}"` using `Bash` (`work=$(mktemp -d "${TMPDIR:-/tmp}/work.XXXXXX") && cp -R <src-dir>/. "$work/" && echo "$work"`), using a fresh `mktemp -d` directory for every copy so no stale files or `.git` from another run or package leak in. Copying into `"${TMPDIR:-/tmp}"` avoids permission denials on protected working directories while keeping `go.mod` / package metadata intact. Never substitute `Write` for `cp`.
2. Call `Read` on the test file you are about to edit so its exact current lines are in context.
3. Pick an exact multi-line `old_string` anchor directly from the lines `Read` returned and apply `Edit`. When the failed `Edit` was reported to you rather than made by you, that report is attempt 1 and your `Edit` here is the retry.
4. **Report the recovery (§16 Edit recovery):** state that you re-`Read` the file and retried `Edit`, quote the anchor you copied from the `Read` output, and give the attempt count and result. Keep the cause factual: the original `old_string` did not match the file's current contents. Without this record, the user cannot tell a verified retry from a guess, nor see which lines their failed anchor should have matched.
5. **3-strike and blocked-edit skip rule:** If `Edit` still fails after 3 re-read-and-retry attempts on the same file — or if sandbox permissions block creating a byte-for-byte copy and block editing in place — **STOP trying to edit that file, do NOT call `Write`, and do NOT stall waiting for interactive input in an autonomous run.** Emit your final report (§16) and list the package/module under **Skipped** with the concrete reason.

## 3. `git diff` is the ground truth for your report

**Establish a `git` baseline first when working in a copied or untracked directory.** If you copied read-only inputs into a scratch directory (the `mktemp -d` path from §2) or your target directory is not yet tracked by git, `git diff --stat` will print nothing unless git has the unmodified originals in its index. Immediately after copying — **before** any `Edit` or `Write` — check `git -C <dir> rev-parse --is-inside-work-tree`. Only when that fails (a scratch copy outside any repository) run `git init -q && git add -A` inside that working copy (no `git commit` needed). When the directory is inside an existing repository but its files are untracked, stage only those untracked files in that repository instead (`git -C <dir> ls-files -z --others --exclude-standard -- . | xargs -0 git -C <dir> add --`), leaving tracked files and the user's staged/unstaged split alone, and list those paths in the report (§16) so the user can `git restore --staged` them; never create a nested repository inside a user's tree. If you later create a brand-new test file with `Write`, run `git add -N <new-file>` so `git diff` tracks its added lines too. Never replace `git diff --stat` with `diff -u` or `git diff --no-index` when staging the baseline lets real `git diff --stat` run.

Before drafting the final report, run these two commands as Bash calls in the working tree:

```bash
git diff --stat
```

Authoritative list of which files you actually changed.

```bash
git diff -U0 -- '<test-glob>' | grep -E '^(\+<test-decl-prefix>|-<test-decl-prefix>|diff --git)'
```

Authoritative count of new test declarations added (`+`) and check that zero existing test declarations were removed (`-`) per file. (Your calling agent supplies the test-glob and test-decl-prefix for its language — e.g. `'*_test.go'` and `func Test` for Go; `'test_*.py' 'tests/**'` and `def test_` for Python; `'*_test.rs'` and `fn test_` for Rust; etc.)

Then bind your report fields to these outputs:

- **Files Touched** = the exact file list from `git diff --stat`. If empty, write `"none"`. A file you only `Read` does NOT belong here. An `Edit` that "succeeded" in the tool sense but produced zero net diff (idempotent edits that cancelled out) does NOT belong here.
- **Tests Added (numeric)** = the count of `+<test-decl>` lines per package from `git diff` (`0` when empty). Modifications to existing test functions (adding setup lines, fixing assertions, renaming) are NOT additions — they count as `0`.
- **Tests Written** (named list) = only the NEW test function names, or `"none"`. Do NOT list existing functions you tweaked. Do NOT list test names you saw while reading.
- **Quote the literal `git diff --stat` stdout in a fenced block** in the report so a reviewer can verify your numbers (or write `(empty — zero files changed)` when no edits were made).

## 4. Pre-report integrity check

Before you start drafting the report, count how many successful `Write` and `Edit` calls you made this run that produced a non-empty diff.

If that count is **zero** (for example, you hit the iteration cap before writing tests, found no source files in your language, or skipped every target), the report must state those exact zero-work values explicitly — a prose summary that leaves fields implicit or implies work happened when none did is the fabrication this skill exists to prevent:

- **Files Touched:** `none`
- **Tests Added:** `0` (for every package/module)
- **Tests Written:** `none`
- **After-coverage:** `not measured (<explicit cause — e.g., iteration cap hit before any tests or coverage command could run>)`
- **Validation:** `not run (<cause>)` (unless you actually ran build/test commands, in which case report their real exit status)

**Do not list test functions you saw while reading, and do not list hypothetical test names you planned to write.** Existing tests existed before you arrived, and planned tests do not exist on disk — neither belongs in Tests Written or anywhere that could be misread as work completed. Reading a file is not writing tests; do not conflate the two.

## 5. Validation reflects reality

Your Validation section reflects the actual exit status of the build and test commands you ran as your last tool calls — a reviewer will re-run them, so a wrong PASS is caught immediately and discredits the whole report.

- If `go build` / `cargo build` / `pytest --collect-only` / `tsc` fails: write **FAIL** and the actual error, not "PASS".
- If the test runner fails: write **FAIL — <reason>**, not "PASS".

A truthful "FAIL — undefined symbol X" is worth more than a false "PASS".

## 6. Failures on files you touched are YOUR failures

If your build or test command fails on a file whose `_test.<ext>` you edited this run, YOU caused it. Do not label it "unrelated". Re-read the file, identify the malformed area, and fix it before reporting. Common causes (language varies):

- Redeclared variables (`:=` reuse in Go, `let` shadowing without intent)
- Duplicate function declarations
- Imports added in the wrong place
- Missing imports for names you referenced
- Symbols that don't actually exist in the source you read

Reporting "FAIL (unrelated failures)" when the failing file is one you just touched is dishonest. Fix it or admit it explicitly: "FAIL — I introduced X by appending Y; fix is Z."

## 7. After-coverage % is measured or "not measured" — never fabricated

"After" coverage requires running the language's coverage tool as your last measurement step:

- Go: `go test -cover ./...`
- Python: `pytest --cov`
- Rust: `cargo tarpaulin` or `cargo llvm-cov`
- Node: `vitest --coverage` / `jest --coverage`

If you ran it, copy the real percentages. If you didn't, write **`not measured (<cause>)`** (for example, `not measured (iteration cap hit before coverage command)` or `not measured (no tests written)`) in the report and in every per-package row. **Never** write "~95%" or "100%" based on what your tests "should" achieve, and never omit the `After-coverage` field altogether when no tests ran. The agent that runs coverage commands and reads real numbers is doing different work than the agent that estimates — don't pretend to be the former when you were the latter.

## 8. Verify symbols and import paths against source you actually read

Every identifier in your tests — every imported package path, every function name, every type, every constant — must appear in a source file you actually `Read` this iteration.

- A package named `daemon` may live at `routine/daemon`, not `daemon`.
- A package might export `Load`, not `NewStore`.
- A function might be `ComputeGrade`, not `CalculateLetterGrade`.

If you cannot point to the file:line where `Foo` is defined, do not call `Foo` in a test. A test that won't compile costs more than the test would have earned in coverage.

## 9. Stay in your language

You are dispatched as a specific language's test agent (go-tests, python-tests, rust-tests, nodejs-tests). If your orchestrator's discovery step reports `NOT_A_<LANG>_PROJECT` or finds no source files in your language, **STOP and emit an honest "no source found" report.** Do NOT pivot to writing tests in another language just because the repo happens to be a different language — that's a different agent's job. Your Files Touched is "none", your Tests Added is 0 in every package, and your report tells the caller to dispatch the correct agent.

This rule exists because a rust-tests run that found no Rust files pivoted to writing Go tests (well-formed, but the wrong agent), instead of stopping. The user should always know which language is being worked on; agents that silently switch lie about scope.

## 10. No contortion tests for coverage

A test exists to catch a bug or document a behavior. If it does neither, delete it instead of writing it. Coverage % is the side effect of real tests, not the goal.

Skip the following patterns even when they would raise coverage. They look like tests but exercise no code under test, so the coverage they add is a false signal:

- **Field-assignment-then-readback.** Constructing a value, assigning each field, and asserting each field reads back the same value tests the language's struct/dict semantics, not the package. Example to avoid (Go): `s := pkg.Status{ServicePath: "/x"}; if s.ServicePath != "/x" { t.Error(...) }`. Equivalent Python: `s = Status(path="/x"); assert s.path == "/x"`. Skip it.
- **Sentinel-existence "tests."** `if pkg.ErrFoo == nil { t.Fatal }` only asserts the package declares the var. Tests the compiler. Skip.
- **Constructor-echo "tests."** Calling `New(x)` and asserting the new value's only-public-field equals `x` when there is no transformation or validation in between. Skip.
- **Functional duplicates.** Before adding `TestFoo_Bar`, scan the package's existing test files for any test that already covers the same input → behavior under a different name (`TestFooBar`, `TestFoo_BarCase`, snake-case vs camel-case variants). A different name is not a different test. Skip.
- **"Should not panic" with no assertions.** A test body that calls a function, has no asserts, and relies on the absence of a panic is only a smoke test. Keep it only when the function under test could plausibly panic on the inputs given and no observable side effect is available to assert on. Otherwise skip.

If you find yourself writing one of these to fill a coverage gap, the gap is telling you the code is too trivial to test. Document it under **Skipped** (§16) with reason "no testable behavior" — that is the honest report.

## 11. Test names must describe the branch the test actually exercises

A test named `TestFoo_WhenBudgetExceeded` is a claim that the test causes `Foo` to take the budget-exceeded branch. The test body has to satisfy that claim, or the name is documenting behaviour the suite doesn't actually check.

Concretely: if the function under test gates a branch on `errors.Is(err, sentinel)` / `isinstance(err, SentinelError)` / `err instanceof Sentinel`, your test's input must actually match that predicate. Constructing a fresh error with the same *message* as the sentinel is not the same as wrapping it — `errors.Is` (or its equivalent) will return false and the test will silently hit a different branch.

Before drafting a test name that promises a specific path:

1. Re-read the function's branch condition.
2. Verify that the input you're passing satisfies the condition. (For Go: if it's `errors.Is(err, X)`, your error must be `X` itself or wrap it with `%w`. For Python: if it's `except X`, your raised error must be `X` or a subclass. For TS/JS: if it's `instanceof X`, same constraint.)
3. If you can't satisfy the condition with available test helpers, either build the satisfying input or rename the test — do NOT ship a name that lies about which path runs.

A name that promises a path the body doesn't exercise is worse than a missing test: it fools the next reader (and the next agent) into thinking the path is covered.

## 12. Never rename or replace an existing test function

`Write` truncation (§1) is the obvious destruction mode. The subtler one is
`Edit`-based destruction: deleting an existing test function and writing a
near-duplicate under a different spelling.

The pattern (from a real run that destroyed 6 tests):

1. Existing file has `TestFindMissedFiresFireOnce` (camelCase).
2. Agent decides snake_case-with-underscore is "cleaner": `TestFindMissedFires_FireOnce`.
3. Agent emits an `Edit` whose `old_string` covers the existing function and whose `new_string` replaces it with the renamed-and-rewritten version.
4. The new version covers the SAME code path under a different name — net loss of test surface, coverage dropped.

**The diff of any pre-existing test file you touch this run should show zero
`-<test-decl>` lines** (where `<test-decl>` is the new-test prefix your
calling agent declared in the caller checklist: `func Test` for Go, `def
test_` for Python, `fn` inside `mod tests` for Rust, `test(`/`it(` for
JS/TS).

If an existing test name bothers you for style reasons, **leave it alone.**
Rename = destruction. Same code path under a new spelling is a
functional duplicate (§10) AND destruction of working tests (§1).

## 13. Never use `_2` / `_3` / `Extra` / `Alt` / `New` to dodge a duplicate-name compile error

You write a test. The compiler/runner errors: "duplicate `TestFoo`
declaration." Your instinct is to rename your new one to `TestFoo2` (or
`testFoo_2`, `TestFooNew`, `TestFooAlt`, `TestFooExtra`) and re-emit. That
instinct is wrong.

The duplicate-name error is a **signal** that `TestFoo` already exists and
already covers the case your new test was going to cover. The new test
under `TestFoo2` would be a functional duplicate (§10) — same input, same
behavior, different spelling. No coverage gain; just clutter.

**The right response:**

1. `Read` the existing `TestFoo` body.
2. Confirm it exercises the case you intended.
3. SKIP — do not write a sibling.
4. If it does NOT exercise your intended case, REPLACE its inputs (carefully, preserving the existing assertions) — but never add a `_2`-suffixed sibling.

Worked example (a real run that wasted iterations): agent wrote
`TestStoreFindByID2` and `TestIsManifestFile2` because `TestStoreFindByID`
and `TestIsManifestFile` already existed. Coverage gain: zero. The
sibling-named tests exercised the same paths under different spellings.

## 14. Mechanical target selection — query, don't guess

Before writing a test for any function in a target file/module/package,
your iteration must include a deterministic query that tells you which
functions in that target have the lowest coverage. When the run was
orchestrated by `enqueue-coverage-targets`, that data is already in
the hit rows its `enqueue.sh` printed (also saved to
`/tmp/squad-uncovered.out`); the exact query is in that skill's
`references/<language>.md`.

Otherwise the calling orchestrator supplies the equivalent command for its
coverage tool.

The exact query is per-language and per-orchestrator. The principle is
constant: write tests only for the functions/lines the query lists in its
top 3-5 entries. Testing functions outside that top-N is what causes "I
added 10 tests and coverage moved 0%."

Picking by feel ("this function looks easy to test") was the dominant
failure mode of every prior run that under-delivered. Replace discretion
with the query.

## 15. Iteration budget honesty

If you hit your iteration cap (or your model's tool-call cap) before
running the final verification + coverage re-measurement, **say so
explicitly in the report.** Forms this takes:

- "After: not measured (iteration cap hit before final `<cov-cmd>`)" — required per §7, but this section makes the *cause* visible.
- "Packages untouched this run: X, Y, Z" — list them by name; do not hide them by silence.
- "I burned the first N iterations on cache-served reads / inventory before producing any edits, which left no budget for the planned M-iter verify+report block." — concrete self-attribution.

The model of an honest run that fell short is preferable to the
appearance of a complete run that fabricated. Say what you did, say what
you didn't get to, say why.

## 16. Required final report format

Every run — whether tests were added, packages were skipped, or the iteration budget ran out before any edit — ends with an explicit report containing every field below (if your calling agent supplies a table or section template, use its layout while preserving all of these ground-truth fields and values):

- **Existing Tests Read & Preserved:** Each pre-existing test file you `Read` before editing, confirmation that `Edit` (never `Write`) was used on existing test files, the existing test functions kept unremoved and unrenamed, and confirmation of `0` `-<test-decl>` lines in `git diff` (or `none — no test files edited` on a zero-work run).
- **Edit recovery** (include only when an `Edit` failed with "text not found" this run, or the caller reported one): the file you re-`Read`, the verbatim `old_string` anchor you retried with (its first line or two in a fenced block, copied from the `Read` output), the attempt count, and the result: the retry succeeded, or the file was skipped after 3 attempts (§2).
- **Working copy:** `in place`, or the scratch directory path when you edited a copy (§2), so readers know whether their own tree changed; when you staged untracked files in the user's repository as a baseline (§3), list those paths here.
- **Files Touched:** Exact paths from `git diff --stat`, or `none`.
- **`git diff --stat`:** Verbatim `git diff --stat` output in a fenced code block (or `(empty — zero files changed)` when `git diff --stat` printed nothing because zero files changed).
- **Tests Added:** Numeric count of newly added `+<test-decl>` lines from `git diff` (`0` when none were added).
- **Tests Written:** Names of newly added test functions only, or `none` (never pre-existing or unimplemented test names).
- **After-coverage:** Real measured percentage from the coverage command, or `not measured (<explicit cause, e.g., iteration cap hit before coverage command could run>)`.
- **Validation:** Actual exit status of build, test, and coverage commands (`PASS`, `FAIL — <actual error>`, or `not run (<cause>)`).
- **Skipped:** Every skipped package, file, or function with its concrete reason (e.g., 3 failed `Edit` attempts, read-only/sandbox block where `Write` on an existing test file is forbidden, or `no testable behavior` per §10), or `none`.

## What this skill does NOT cover

Language-specific syntax patterns: idiomatic test layout (table-driven, fixtures, parametrize), how to mock external services, naming conventions, file location (`*_test.go` adjacent vs `tests/` directory), framework choice (`go test`, `pytest`, `jest`, `cargo test`).

Those belong in the calling agent's system prompt. This skill is purely the discipline that keeps any test-writing agent from destroying work or producing dishonest reports — orthogonal to language.

## Caller checklist

Your calling agent (e.g. `go-tests`, `python-tests`) should reference this skill and provide:

- Test file glob (`*_test.go` / `test_*.py` / `*_test.rs` / `*.test.ts`).
- Test declaration prefix for the `git diff` grep (`func Test`, `def test_`, `fn test_`, `test(` / `it(`).
- Build command (`go build ./...`, `tsc --noEmit`, `cargo build --tests`).
- Test command (`go test ./...`, `pytest`, `cargo test`, `jest`).
- Coverage command for the "After" measurement.
- **Mechanical-target query (§14):** the exact Bash command the agent runs to list a target file's lowest-coverage functions/lines. Without this, §14 has no teeth.

The honesty rules above stay constant; only the commands vary.
