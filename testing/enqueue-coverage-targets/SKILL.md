---
name: enqueue-coverage-targets
description: "Raise test coverage in Go, Node.js/TypeScript, Python, or Rust: a bundled script measures coverage once and prints a queue of every package or file below target (also saved to /tmp/squad-targets.txt), then you drain the queue by reading source and writing tests, and re-measure only at the end. Do NOT use for a one-off 'write a test for this function' request or for measuring coverage without writing tests (use score-coverage-and-report-gaps for the report-only case)."
metadata:
  author: Jayson Grace
  version: 2.1.1
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

It also saves the same data to two files, for shells that keep `/tmp` between
commands:

- `/tmp/squad-targets.txt` — the worker queue, one unit per line,
  tab-separated `<unit>\t<pct>%\t(target N%)`, sorted worst-first.
- `/tmp/squad-uncovered.out` — per-function or per-line hit data used to
  choose which functions to test inside each unit (format varies by
  language; the reference file shows the command to use).

**Its stdout is the authoritative copy of both.** It prints the overall
percentage, the whole queue, and the lowest-hit rows for each queued unit
(the first 15 units). Sandboxed shells can give
every command a fresh `/tmp`, so a later read of `/tmp/squad-uncovered.out` may
find nothing. When that happens, work from the Step 1 output. Don't re-run the
script or any coverage command to get the data back; that is the re-measuring
this skill forbids.

Extra knobs: `SQUAD_CMD_COVERAGE_TARGET` (Go, separate target for
`*/cmd/*`), `SQUAD_PYTHON_PKG` (Python, the package passed to `--cov`; set it
to the top-level package when sources aren't at the repo root).

If the script reports `UNKNOWN_PROJECT`, `NOT_A_<LANG>_PROJECT`,
`NO_COVERAGE_TOOL`, or `NO_COVERAGE_DATA`, the queue is empty on purpose.
Stop immediately and send the fenced report below in its early-stop form
(`Before: not measured`, `After: not measured`, `Files Touched: none`,
`Tests Added: none`).
Don't install packages on the user's system, don't create source files to
test, and don't pivot to a different language. A run that silently changes
scope is worse than one that reports it can't proceed.

## Step 1a — Working copy (only if the project can't be edited in place)

Edit the project in place by default. Only make a working copy when the
project directory is read-only, sits outside your writable working
directories, or the request asks to leave the original untouched.

Build the copy outside the original tree, choosing the copy method up front:

1. Set `$work` to a new directory outside the project and outside any git
   repository that contains it: `<absolute path of your working
   directory>/<project directory name>-work` (for example
   `/scratch/run/cov-go-work`) when your working directory is outside both,
   otherwise `${TMPDIR:-/tmp}/<project directory name>-work`. If that path
   already exists (an earlier run's copy may hold its only tests), never
   write into it: append `-2`, `-3`, and so on until the path is new. Use
   that absolute path in every later tool call.
2. Copy the whole project, not just the queued units, with one method:
   - **Inputs declared read-only, or not writable by you** (the project is
     read-only or sits outside your writable working directories): `Read`
     every source, test, manifest, config, and fixture file (`go.mod`,
     `pyproject.toml`, `conftest.py`, `setup.cfg`, `.coveragerc`,
     `package.json`, `tsconfig.json`, `vitest.config.*`, `Cargo.toml`,
     `build.rs`, `testdata/`, lockfiles, and the like) at its original path
     and `Write` its content verbatim to the same relative path under
     `"$work"`, the method such environments provide for changing read-only
     inputs. Change nothing while copying. Skip `.git` and build output
     (`target`, `dist`, `__pycache__`). Link dependency directories instead
     of copying them, so the copy uses the same installed tools without
     installing anything: `ln -s /path/to/project/node_modules
     "$work/node_modules"` (likewise `vendor` and `.venv`). If the tests need
     a binary fixture (`*.gz`, `*.png`, `*.pkl`, and the like), `Read` and
     `Write` can't copy it verbatim: stop instead of copying it.
   - **Otherwise** (the project is writable and the request asks to leave the
     original untouched): copy it in one command, skipping `.git`:

     ```bash
     mkdir -p "$work" && cp -R /path/to/project/. "$work/" && rm -rf "$work/.git"
     ```

3. Stage that verbatim baseline before adding any test, so `git diff` shows
   exactly what this run changed and that every original test survived:

   ```bash
   git -C "$work" init -q && git -C "$work" add -A
   ```

Make this copy **before** Step 2. From here on, `"$work"` is the project:

- Call `Read` on source and existing test files at their `"$work/..."` paths
  before editing them.
- Add tests to existing test files, including the baseline copies, strictly
  with `Edit`, never a second `Write`, and keep every original test
  unremoved and unrenamed.
- Run Step 3 build, test, coverage re-measurement, and `git diff` from inside
  `"$work"`. The queue from Step 1 stays valid because the code is identical.

If any step of the chosen method is refused, or a needed binary fixture
can't be copied, stop and send the report below in its early-stop form
(`Files Touched: none`, `Tests Added: none`, `After: not measured`), naming
the refused action or fixture under `Skipped`. Never retry a refused action
with another tool (`Read`+`Write` after a refused `cp`, or `cp`, `cat >`,
`tee`, or a script after a refused `Write`) or look for another way around
the refusal.

## Step 1b — Pick targets mechanically

Read the reference file for the project's language (`references/<lang>.md`;
naming, idiom, and the verify commands come from it). Then, for each queued
unit, take the 3–5 lowest-hit functions or uncovered line ranges from
`/tmp/squad-uncovered.out` — already printed in Step 1's hit rows (use those
printed rows directly if `/tmp/squad-uncovered.out` is gone). Test only those.
Prior runs that chose targets by judgment wrote many tests against
already-covered code and moved the number 0% — the hit data is what makes a
test count.

## Step 2 — Work the queue (every iteration after Step 1)

Drain the queue Step 1 printed (`/tmp/squad-targets.txt` is only a
convenience copy and may be gone) in batches of 3–5 units until it is empty
or you've used 80% of your cost or iteration budget.

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
     mirror rule (in the reference file). In a git repository (always true
     for `"$work"`), then run `git -C <project dir, or "$work"> add -N
     <new-file>` so `git diff` tracks it.
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

From inside the project directory (or `"$work"` when Step 1a created a working
copy), run the language's build, test, and coverage re-measurement commands
once (see `references/<lang>.md`). Then, limited to the files in Files
Touched so other work in the tree stays out of the report, run
`git -C <project dir, or "$work"> diff --stat -- <touched files>` and
`git -C <project dir, or "$work"> diff -- <touched files>` to confirm zero
existing test functions were removed or renamed. If an in-place project has
no git baseline (`git -C <project dir> rev-parse --is-inside-work-tree`
fails), don't create one; skip `git diff` and report
`Diff Summary: not available (no git baseline)`. Fix only test code on
failure.

Copy the real re-measured percentage into the report. If you skip
re-measurement, the `After` field says `not measured` — a projected number is
a fabrication, and the caller's report format treats it as one.

Emit the caller's OUTPUT FORMAT report as a transcript of what happened, not
a projection. The reader sees only this final message, so every claim about
how the run went has to be in it. When the caller doesn't dictate a format,
always emit this fenced `text` block:

```text
Coverage Report
  Target: <N>%   Before: <overall % from Step 1 | not measured>   After: <re-measured % | not measured>
  Working Copy: <in place | <$work path> (verbatim Read+Write | cp -R baseline of <source>, staged in git; originals untouched)>
Files Touched: <none, or newline-indented `<relative-path> (Edit | Write)` lines>
Diff Summary: <none | not available (no git baseline) | `git diff --stat -- <touched files>` output plus confirmation that 0 existing test functions were removed or renamed>
Tests Added: <none, or newline-indented `<test name> in <file> — covers <function or lines from /tmp/squad-uncovered.out>` lines>
Skipped: <none, or newline-indented `<unit or function> — <specific reason>` lines>
Run Record:
  1. First command: <exact standalone enqueue.sh command with target and language>; queue: <units and %>
  2. Reference read: <references/<lang>.md — applied: <naming and idiom> | none (no supported project)>
  3. Targets from /tmp/squad-uncovered.out: <unit: functions or line ranges | none>
  4. Per file: <Read <source>; Read <existing test file> (existing tests: <names>); then Edit | Write <file> | none>
  5. Existing tests preserved in diff: <names (0 removed or renamed test functions in git diff) | not verified (no git baseline) | n/a>
  6. Coverage commands run: <enqueue.sh (Step 1), <Step 3 command>; none in between | enqueue.sh (Step 1) only>
```

- **Files Touched** — only test files you `Edit`ed or `Write`d this run
  (relative to the project or working copy; baseline files written verbatim
  in Step 1a are not touched unless you later `Edit` them), or the literal
  `none`.
- **Tests Added** — only new test functions added this run, each tied to the
  function or lines from `/tmp/squad-uncovered.out` it covers, or `none`.
- **After** — from Step 3 re-measurement, or the literal `not measured`.
- **Run Record** — in the order it happened, naming `Edit` vs `Write` for each
  file and confirming existing test functions were preserved in `git diff`.
  Never claim a file was edited or existing tests were kept without having
  `Read` the file first and verified `git diff`; with no git baseline, say
  the preservation was not verified.
- **Early stop** (nothing to queue): keep the fenced block and write literal
  `Before: not measured`, `After: not measured`, `Files Touched: none`,
  `Diff Summary: none`, and `Tests Added: none`, with the script's reason
  under `Skipped`.

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
