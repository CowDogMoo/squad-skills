---
name: enqueue-coverage-targets
description: "Raise test coverage in Go, Node.js/TypeScript, Python, or Rust: a bundled script measures coverage once and queues every package or file below target into /tmp/squad-targets.txt, then you drain the queue by reading source and writing tests, and re-measure only at the end. Do NOT use for a one-off 'write a test for this function' request or for measuring coverage without writing tests (use score-coverage-and-report-gaps for the report-only case)."
metadata:
  author: Jayson Grace
  version: 2.1.0
---

# Enqueue Coverage Targets

You are entering an **orchestrator-workers** pattern (Anthropic, "Building
Effective Agents"). The orchestrator is `scripts/enqueue.sh`; the worker is
you, from Step 2 onward.

The pattern exists because every earlier attempt at letting the agent
discover coverage gaps on its own ended the same way: 30–50 iterations of
measuring, 0–3 tests written. Discovery is deterministic and does not need a
reasoning model, so the script does it once. Your reasoning is reserved for
the only part that needs it: writing tests that exercise real code paths.

The workflow below is language-independent. Language-specific facts — test
file naming, idioms, the verify command, how to pick target functions — live
in one reference file per language. Read the one that matches the project
before Step 2:

| Language              | Reference               | Queue unit                    |
| --------------------- | ----------------------- | ----------------------------- |
| Go                    | `references/go.md`      | package                       |
| Node.js / TypeScript  | `references/nodejs.md`  | source file                   |
| Python                | `references/python.md`  | module (source file)          |
| Rust                  | `references/rust.md`    | source file                   |

## Step 1 — Orchestrate (your first tool call after loading this skill)

Run the queue builder as **one standalone command**, with the target from the
request and the project directory as an argument. It auto-detects the language
from `go.mod`, `Cargo.toml`, `package.json`, or `.py` files; pass the language
too if the repo is mixed:

```bash
SQUAD_COVERAGE_TARGET=90 bash scripts/enqueue.sh python /path/to/project
#                      ^ the request's target    ^ or go|nodejs|rust, or omit to auto-detect
```

(`scripts/` is relative to this skill's directory; squad exposes it as
`$SQUAD_SKILL_DIR/scripts/enqueue.sh`.) With no project argument it runs in
the current directory.

Why standalone, with the directory as an argument: if the command starts with
`mkdir`, `cp`, or `cd ... &&`, one denied or failed step skips the queue
builder, and the run then drifts into judging targets by hand. The script only
reads the project (coverage data and caches go to `/tmp`), so it runs fine on a
read-only checkout. Make any working copy (Step 1a) **after** it, not before.

It builds two files that every later step depends on:

- `/tmp/squad-targets.txt` — the worker queue, one unit per line,
  tab-separated `<unit>\t<pct>%\t(target N%)`, sorted worst-first.
- `/tmp/squad-uncovered.out` — per-function or per-line hit data used to
  choose which functions to test inside each unit (format varies by
  language; the reference file shows the `grep` to use).

**Its stdout is the authoritative copy of both.** It prints the overall
percentage, the whole queue, and the lowest-hit rows for each queued unit
(the first 15 units; `SQUAD_HITS_UNITS` raises that). Sandboxed shells can give
every command a fresh `/tmp`, so a later `grep /tmp/squad-uncovered.out` may
find nothing. When that happens, work from the Step 1 output. Don't re-run the
script or any coverage command to get the data back; that is the re-measuring
this skill forbids.

Extra knobs: `SQUAD_CMD_COVERAGE_TARGET` (Go, separate target for
`*/cmd/*`), `SQUAD_PYTHON_PKG` (Python, the package passed to `--cov`; set it
to the top-level package when sources aren't at the repo root).

If the script reports `UNKNOWN_PROJECT`, `NOT_A_<LANG>_PROJECT`, or
`NO_COVERAGE_TOOL`, the queue is empty on purpose. Stop, and send the report
below in its early-stop form (`Files Touched: none`, `After: not measured`).
Don't install packages on the user's system, don't create source files to
test, and don't pivot to a different language. A run that silently changes
scope is worse than one that reports it can't proceed.

## Step 1a — Working copy (only if the project can't be edited in place)

If the project directory is read-only, or the request says to copy it before
changing it, make a writable copy now and do every later step in the copy.
Use `cp -r`. If the shell denies the copy, stop and send the report below in
its early-stop form, naming the denied copy under Skipped. Do not look for
another way around a denial.

After that the copy is the project. An existing test file in it still gets
`Edit`, never a second `Write` with new contents, and its original tests must
survive. The queue from Step 1 stays valid because the code is the same.

## Step 1b — Pick targets mechanically

Read the reference file for the project's language (`references/<lang>.md`;
naming, idiom, and the verify commands come from it). Then, for each queued
unit, take the 3–5 lowest-hit functions or lines from the hit rows Step 1
printed (the same rows as the `grep` in the reference file). Test only those.
Prior runs that chose targets by judgment wrote many tests against
already-covered code and moved the number 0% — the hit data is what makes a
test count.

## Step 2 — Work the queue (every iteration after Step 1)

Read `/tmp/squad-targets.txt` once. Drain it in batches of 3–5 units until it
is empty or you've used 80% of your cost or iteration budget.

For each batch:

1. **Read iteration** — parallel `Read` calls, one per unit:
   - The source file(s) for the unit. Confirm the real import/module path
     and the exact names and signatures you intend to test. Guessing a
     symbol from a package name produces a test that doesn't compile, which
     costs more than the test would have earned.
   - **Every existing test file for that unit.** You need to know what is
     already tested before adding anything, and this read is also what
     protects the file in the next step.
2. **Write/Edit iteration** — parallel calls, one per unit:
   - If a test file for the target source already exists, `Edit` it to add
     tests. `Write` truncates the destination, so writing to an existing
     test file deletes every test in it — a prior run lost 2,524 lines
     across 7 files this way.
   - If no test file exists, `Write` a new one named per the language's
     mirror rule (in the reference file).
   - Every symbol you reference must have appeared in source you read this
     iteration.
   - Each file must contain at least one real test with meaningful
     assertions on the lowest-coverage functions. Empty stubs waste the
     iteration.
3. Move to the next batch **without re-measuring coverage.** The queue is
   your source of truth until Step 3; re-measuring mid-run is how earlier
   runs burned their whole budget on discovery.

Aim for 3+ units per Write/Edit iteration. Single-unit iterations are
wasteful given ~25 iterations and a long queue.

When `Edit` fails with "text not found", your `old_string` is wrong — re-`Read`
the file, pick a real anchor, retry. After three failed attempts on one file,
skip the unit and list it under Skipped. Falling back to `Write` at that
point is exactly the truncation failure above.

## Step 3 — Verify and report (last 2–3 iterations)

Run the language's build and test commands once (reference file). Fix only
test code on failure.

Then re-measure coverage with the command in the reference file and copy the
real numbers into the report. If you skip re-measurement, the "After" column
says "not measured" — a projected number is a fabrication, and the caller's
report format treats it as one.

Emit the caller's OUTPUT FORMAT report as a transcript of what happened, not
a projection. The reader sees only this final message, so every claim about
how the run went has to be in it. If the caller doesn't dictate a format, use:

```text
Coverage Report
  Target: <N>%   Before: <overall % from Step 1>   After: <re-measured % | not measured>
Files Touched
  <path> (Edit | Write)        or: none
Tests Added
  <test name> in <file> — covers <function or lines from the hit rows>      or: none
Skipped
  <unit or function> — <specific reason>      or: none
Run Record
  1. First command: <exact enqueue.sh command with target and language>; queue: <units and %>
  2. Reference read: references/<lang>.md — applied: <naming / idiom>
  3. Targets taken from the hit rows: <unit>: <functions or lines>
  4. Per file: Read <source>; Read <existing test file> (its tests: <names>); then Edit | Write <file>
  5. Existing tests kept: <names>
  6. Coverage commands run: enqueue.sh (Step 1), <verify command> (Step 3); none in between
```

- **Files Touched** — only files you `Write`d or `Edit`ed this run (a working
  copy's files are not "touched"; say that you made a copy).
- **Tests Added** — only test functions you appended this run.
- **After** — from re-measurement, or the literal `not measured`.
- **Run Record** — in the order it happened, naming the tool for each file.
  Never write "edited in place" or "kept existing tests" without having read
  the file first and saying so.
- **Early stop** (nothing to queue): `Files Touched: none`, `Tests Added: none`,
  `After: not measured`, plus the script's reason in one line.

## Constraints that override your judgment

- **Test files only.** Source edits are out of scope; document a needed
  source change under Skipped. (Rust is the exception — tests live in
  `#[cfg(test)]` blocks inside source files; the Rust reference explains the
  boundary.)
- **No coverage commands between Step 1 and Step 3.**
- **No git-based undo** (`stash`, `checkout`, `restore`). Other agents' work
  is in the tree; undo with `Edit` instead.
- **Don't load `score-coverage-and-report-gaps`.** Its discover-measure loop
  is the behaviour this skill replaces.
- **Imports must be complete** for every symbol a test references. Missing
  imports are the most common quality bug in generated tests.

## Why this pattern works

The previous agent shape gave the model discretion over a step that doesn't
need discretion. This skill removes it by running discovery in a script and
fixing the batch shape (Read iteration → Write iteration → repeat) so the
agent can't stall in single-unit over-thoroughness.
