---
name: doc-comments-discovery-and-fix-loop
description: Discover public/exported declarations missing or carrying deficient doc comments, prioritize by impact, apply proportional fixes in a read-then-edit loop, verify the result compiles, and report. Use from any language-specific doc-comments agent, or when asked to document a package's public API or audit doc-comment coverage; the caller supplies language style and verify command. Do NOT use to delete useless or LLM-generated comments — that is comment-scrub-playbook.
allowed-tools: Read, Glob, Edit, Bash
metadata:
  author: CowDogMoo
  version: 1.1.0
---

# Doc Comments Discovery and Fix Loop

You are working a doc-comment cleanup pass through a codebase. This
skill gives you the four-phase loop, the prioritization order, the
proportionality rule, and the read-then-edit discipline. The caller
(a language-specific doc-comments agent) supplies the language's
style conventions and verify command.

## Inputs the caller supplies

- **Language** — Go, Python, Rust, Node/TypeScript, etc.
- **Source-file glob and filter** — e.g. `**/*.go` minus
  `_test.go`/`vendor/`; `**/*.py` minus `__pycache__/`/`.venv/`/
  `test_*.py`; `**/*.rs` minus `target/`; `**/*.{js,ts,mjs,cjs}`
  minus `node_modules/`/`dist/`/`build/`/`coverage/`/test files.
- **Public-vs-private predicate** — Go: capitalized identifier.
  Python: name does not start with `_`. Rust: `pub` or
  `pub(crate)`. Node: has `export` keyword.
- **Style ruleset** — the agent's `REVIEW CATEGORIES` and `WHAT TO
  FIX` / `HOW TO FIX` sections. The skill does not re-state them.
- **Verify command** — `go build ./...`, `python -m py_compile` +
  optional `ruff check`, `cargo build`, `npx tsc --noEmit` (or
  `node --check` for plain JS).
- **Revert mechanism** — `git checkout -- <file>` for most
  languages. Rust forbids `git checkout`; use Edit-to-undo
  instead. The caller declares which.
- **Iteration cap** — usually 12 / 20 / 25 by codebase size.
- **Optional Pre-discovered list** — if the orchestrator injected
  `Pre-discovered source files`, treat it as authoritative and
  skip Glob.

## Iteration budget

Scales with codebase size; caller tunes the numbers:

- **Small (≤20 files):** ~12 iterations.
- **Medium (21-50):** ~20 iterations.
- **Large (50+):** ~25 iterations; prioritize entry points, core
  logic, public API. Document what was skipped.

Allocate roughly: Phase 1 (1 iter), Phase 2 (varies by size),
Phase 3 (2-4 iter with edits batched), Phase 4 (1 iter — verify
and report in the SAME response).

**Read-then-edit cadence.** Read 3-5 files in parallel, edit them,
read the next batch. Never accumulate more than 5 unprocessed reads
without editing. **First Edit by iteration 4.** Do not read the
entire codebase first.

## Phase 1 — Discover (1 iteration)

1. If the prompt includes `Pre-discovered source files`, use that
   list. Skip Glob.
2. Otherwise Glob the caller-supplied pattern and apply the filter.
3. Reference documents already included in the system prompt — do
   NOT Read them as files.

## Phase 2 — Analyze

Read source files in parallel batches of 3-5. For each file,
catalog every public declaration with at least one of:

- No doc comment at all.
- Doc comment is a fragment, not a complete sentence.
- Doc comment is redundant (restates the name; "Process processes
  the data").
- Doc comment violates the language's convention shape (caller's
  style ruleset specifies which — first-word rule for Go, summary
  line for Python, `///` vs `//!` for Rust, `@param`/`@returns`
  for Node, etc.).
- Missing convention-mandated sections (`# Errors`/`# Panics`/
  `# Safety` for Rust, `Args:`/`Returns:`/`Raises:` for Python
  Google-style, `@param`/`@throws` for Node).
- Module-level / file-level / package-level docstring missing.

**Before prioritizing, drop self-documenting names.** Do NOT catalog a
declaration whose name already fully conveys its behavior — getters,
`String`/`new`/`len`/`is_empty`, trivial constructors. A doc that would
only restate the identifier is a non-finding: record it in the skipped
table as "trivial" and never put it in the fix queue.

**Prioritize:**

1. **Safety-critical and unsafe** — missing `# Safety` on Rust
   `pub unsafe fn` is always first when the language has the
   concept.
2. **Missing on complex public functions** — multi-parameter,
   `Result`-returning, async, or otherwise non-trivial.
3. **Missing on simple public functions.**
4. **Improvements** to existing-but-deficient doc comments.
5. **Module / package / file-level** docs last.

Coverage is mandatory for small/medium codebases. For large
codebases, document what was deferred. Coverage is satisfied for
trivial / self-documenting names by listing them in the skipped
table, not by documenting them — a restating comment is not coverage.

## Phase 3 — Fix and Verify

1. Apply fixes via Edit, highest priority first. Group fixes by
   file to minimize Edit calls.
2. **One fix per edit** — keep diffs focused and reviewable.
3. After each batch, Read only the edited lines to verify
   placement. (Rust agents typically read after every Edit because
   `git checkout` is forbidden — caller-specific.)
4. After ALL fixes, run the caller's verify command.
5. If verify fails, use the caller-declared revert mechanism on the
   offending file and move the finding to the skipped table. Do
   NOT proceed past a failing build.

## Phase 4 — Report

Run verify AND output the report in the SAME response. Populate the
skipped table from Phase 2 notes — do not re-explore.

The caller's `OUTPUT FORMAT` section dictates the exact report
shape; the skill only requires that:

- Every file touched appears in the report.
- The skipped table includes every declaration deliberately not
  documented, with the reason (trivial, private, generated,
  build-failed).
- The verify-command result (PASS/FAIL) is included.

## Cross-cutting discipline rules

These hold regardless of language.

- **Public declarations only.** Skip private/unexported names
  entirely. Check the public-vs-private predicate **before** any
  Edit.
- **Only modify doc comments.** Never change code logic,
  signatures, imports, values, or behavior. If a fix would touch
  any of those, skip it.
- **No new dependencies.** Doc-comment changes never require
  import or dependency changes.
- **Respect existing good comments.** Only fix doc comments that
  are missing, fragments, factually wrong, or convention-violating.
  Do NOT lateral-rewrite for style preference. When adding sections
  (Args/Returns/Raises, `# Errors`, `@param`) to an existing
  comment, keep the original summary line verbatim.
- **Proportionality.** One-line getter → one-line comment.
  Complex constructor or async function → multi-paragraph with
  convention sections. Self-documenting names
  (`Info`/`Warn`/`Close`/`new`/`len`/`is_empty`/getters) may need
  NO comment — list as trivial in the skipped table.
- **No trivial struct/field docs.** Only document fields when the
  name is genuinely ambiguous or semantics are non-obvious (units,
  encoding, invariants, lifetime/ownership).
- **Read each file ONCE.** Catalog all findings during Phase 2,
  then fix in Phase 3. No re-reading source files after editing
  except to verify the edited region (and even that's optional
  when the caller's Edit mechanism is trusted).
- **One Glob/Grep on repo root, not N per-directory.**
- **No post-fix exploration.** After fixes verify, go straight to
  report. Use Phase-2 notes for the skipped table.
- **Wind-down protocol.** Near the iteration cap: stop fixes, run
  verify, produce report. A partial report beats no report.
- **STOP after verify.** Once the verify command passes, emit the
  report IMMEDIATELY in the same response. No extra tool calls.

## Boundary — what stays in the caller

The skill is the loop. The caller owns:

- The language's first-word / summary-line / opener convention
  ("reports whether" for Go booleans; imperative mood for Python
  functions; `/// ItemName does…` for Rust; "Fetches…"/"Returns…"
  for Node).
- Required-section names and when they fire (Rust `# Errors`/
  `# Panics`/`# Safety`/`# Examples`; Python `Args:`/`Returns:`/
  `Raises:`/`Yields:`; Node `@param`/`@returns`/`@throws`/
  `@example`).
- Quote-style rules (Python `"""` vs `'''`; Rust `///` vs `//`
  vs `////`).
- Tooling-enforced exported-doc protection (covered by the
  `comment-scrub-playbook` skill on the destructive side; this
  skill's job is to make sure the doc exists and is shaped right
  when it's required).
- The exact `HOW TO FIX — CORRECT PATTERNS` examples.
- The `OUTPUT FORMAT` shape.

## Anti-goals

- Do NOT rewrite already-adequate doc comments for style.
- Do NOT add return-type hints in Python (`-> None` is always
  inferable; only non-obvious return types).
- Do NOT add `@type` JSDoc tags when the file is TypeScript —
  the type signature is the source of truth.
- Do NOT touch test files, generated files, or vendored
  directories — they're filtered in Phase 1 and should never
  appear in Phase 2.

## Examples

### Example 1 — Small Go codebase, missing exported docs

Caller: `agents/go-doc-comments`. Iteration cap: 12. Verify:
`go build ./...`.

Phase 1: Glob `**/*.go` minus `_test.go`/`vendor/` → 18 files.

Phase 2 (Read in batches of 5): catalog finds 9 exported funcs and 2
exported types with no doc comment, 3 fragment comments, 1 godoc
gap (blank line between comment and decl).

Prioritize: complex multi-param functions first, then simple
getters, then types.

Phase 3 (Edit): batch fixes per file. For each:

- Add summary line starting with the declared name
  (`// ParseConfig reads the YAML at path and returns a normalized
  Config.`).
- Close the godoc gap (delete the blank line between comment and
  decl).
- Rewrite fragments into complete sentences.
- Deliberately add NO comment to `Name`, `Len`, and `String` — their
  names already convey their behavior, so any comment would just
  restate the identifier. They go to the skipped table, not the diff.

Phase 4: `go build ./...` → PASS. Report includes touched files,
skipped table (3 trivial getters: `Len`, `Name`, `String`), and
the verify result.

### Example 2 — Rust crate with `pub unsafe fn` missing `# Safety`

Caller: `agents/rust-doc-comments`. Revert mechanism: Edit-to-undo
(NOT `git checkout`). Verify: `cargo build`.

Phase 2 prioritization: the `# Safety` violation on a `pub unsafe fn`
jumps to the top — safety-critical comes first regardless of file
order.

Phase 3:

- Add `/// # Safety` block describing the invariants the caller must
  uphold (the caller's style ruleset specifies the wording).
- Read the edited region back after every Edit (Rust convention,
  since `git checkout` is forbidden).
- Move on only after Read confirms placement.

Phase 4: `cargo build` → PASS. Report flags the safety fix at the
top.

### Example 3 — Verify fails after a fix

Verify command (`cargo build`) errors after a doc-comment edit on
`src/parser.rs`.

Action:

1. Identify the offending file (parser.rs).
2. Apply the caller-declared revert (Edit-to-undo for Rust).
3. Move the parser.rs finding to the skipped table with reason
   "build-failed; reverted".
4. Continue with remaining files. Do NOT proceed past a still-failing
   build.

Phase 4 report shows the skipped row plus PASS on the final verify.

## Troubleshooting

### Error: Doc-comment edit broke the build

**Symptom:** Verify command fails after a batch of Edits.

**Solution:** Identify the offending file (usually obvious from the
compiler error). Apply the caller-declared revert mechanism — `git
checkout -- <file>` for most languages, Edit-to-undo for Rust. Move
the file's findings to the skipped table with reason
"build-failed". Continue with the remaining files. Do NOT proceed
past a still-failing build into Phase 4.

### Error: Edit changed code logic, not just comments

**Symptom:** Diff shows a function body or signature changed.

**Cause:** The skill's hard rule is comments-only. A code change
means the Edit's `old_string` was ambiguous and matched into code,
or the model edited the wrong region.

**Solution:** Revert the file. Re-do the doc fix with more specific
context (include 1-2 lines above the comment in `old_string` to
disambiguate). If the same fix keeps catching code, skip the
finding and note it in the skipped table.

### Error: Re-reading the whole codebase after each fix

**Symptom:** The loop is reading files it already cataloged in
Phase 2.

**Cause:** Misapplied read-then-edit cadence.

**Solution:** Read each file ONCE in Phase 2. Cache findings.
Phase 3 reads only the edited region of edited files, never the
whole file again. Phase 4 runs verify and uses the Phase-2 notes
for the skipped table — no re-exploration.

### Error: Iteration cap hit before Phase 4

**Symptom:** Out of iterations with fixes still queued.

**Solution:** Apply the wind-down protocol. Stop adding new fixes.
Run verify on what's already changed. Emit a partial report listing
what was done, what was skipped due to budget, and the verify
result. A partial report beats no report.

### Error: Trivial getters keep getting doc comments added

**Symptom:** `Len`, `Name`, `String`, `len`, `is_empty` all gaining
mechanical one-line docs.

**Cause:** Proportionality rule violated.

**Solution:** Self-documenting names need NO comment. Move them to
the skipped table as "trivial". Only document when the name leaves
real ambiguity (units, encoding, invariants, lifetime, ownership).
