---
name: enqueue-coverage-targets
description: "Orchestrator-workers pattern for raising test coverage in Go, Node.js/TypeScript, Python, or Rust: a bundled script measures coverage once and queues every package or file below target into /tmp/squad-targets.txt, then you drain the queue by reading source and writing tests, and re-measure only at the end. Load on iteration 1 of any coverage-raising agent run, whatever the language. Don't use for a one-off 'write a test for this function' request or for measuring coverage without writing tests (use score-coverage-and-report-gaps for the report-only case)."
allowed-tools: Bash, Read, Write, Edit
metadata:
  author: Jayson Grace
  version: 2.0.0
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

Run the queue builder from the repository root. It auto-detects the language
from `go.mod`, `Cargo.toml`, `package.json`, or `.py` files; pass the language
explicitly if the repo is mixed:

```bash
export SQUAD_COVERAGE_TARGET=75   # your run's target percent
bash scripts/enqueue.sh           # or: bash scripts/enqueue.sh go|nodejs|python|rust
```

(`scripts/` is relative to this skill's directory; squad exposes it as
`$SQUAD_SKILL_DIR/scripts/enqueue.sh`.)

It writes two files that every later step depends on:

- `/tmp/squad-targets.txt` — the worker queue, one unit per line,
  tab-separated `<unit>\t<pct>%\t(target N%)`, sorted worst-first.
- `/tmp/squad-uncovered.out` — per-function or per-line hit data used to
  choose which functions to test inside each unit (format varies by
  language; the reference file shows the `grep` to use).

Extra knobs: `SQUAD_CMD_COVERAGE_TARGET` (Go, separate target for
`*/cmd/*`), `SQUAD_PYTHON_PKG` (Python, the package passed to `--cov`).

If the script reports `NOT_A_<LANG>_PROJECT` or `NO_COVERAGE_TOOL`, the queue
is empty on purpose. Write an honest "no source / tool missing" report and
stop. Don't install packages on the user's system and don't pivot to a
different language — a run that silently changes scope is worse than one that
reports it can't proceed.

## Step 1a — Pick targets mechanically

Before writing any test for a queued unit, grep `/tmp/squad-uncovered.out`
for that unit (exact command in the reference file) and take the 3–5
lowest-hit functions or lines. Test only those. Prior runs that chose
targets by judgment wrote many tests against already-covered code and moved
the number 0% — the hit data is what makes a test count.

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
a projection:

- **Files Touched** — only files you `Write`d or `Edit`ed this run.
- **Tests Added** — only test functions you appended this run.
- **After %** — from re-measurement, or "not measured".

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
need discretion. This skill removes it by running discovery in a script,
limiting post-Step-1 tools to Read / Write / Edit, and fixing the batch shape
(Read iteration → Write iteration → repeat) so the agent can't stall in
single-unit over-thoroughness.
