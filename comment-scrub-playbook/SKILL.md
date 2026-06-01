---
name: comment-scrub-playbook
description: Classify source-code comments into five delete-candidate categories (states-the-obvious, LLM-generated, no-info, non-idiomatic, visual noise) and decide delete vs. trim vs. keep. Use when scrubbing useless or LLM-slop comments from a codebase.
---

# Comment Scrub Playbook

You are deciding, for each comment block in source code, whether to
**delete it entirely**, **trim it** to keep a useful fragment, or
**keep it as-is**. This skill gives you the rubric. The caller
(usually a language-specific scrub agent) supplies the file glob,
the language-specific directive list, and the build-verify command.

# Inputs the caller supplies

- **Language** — Go, Rust, Python, Node, etc. Drives a few per-
  language exceptions noted below.
- **Exempt-directive list** — comments the language treats as
  machine-readable directives (`//go:*`, `//nolint`, `#[allow(...)]`,
  `# type:`, `# noqa`, JSDoc tags, etc.). These are never targets.
- **Exported-doc protection** — does the language's tooling require
  doc comments on exported items? (Go: yes — `golint`/`go vet`
  enforce. Rust: only for `pub` items under
  `#![deny(missing_docs)]`. Python: no enforcement at the language
  level.) Tautological exported docs **stay** in languages with
  tooling enforcement; a separate doc-comments agent rewrites them.

# Unit of analysis

A **comment block** = one contiguous run of single-line comment
markers (`//`, `#`) or one fenced block (`/* ... */`,
`""" ... """`, `=begin ... =end`). Do not score individual lines
inside a multi-line block separately. For the underlying tell-by-tell
scoring used in Category 2 below, see `detect-llm-tells` — load it
on the first iteration that needs to score a block and keep the body
in context.

# Always-exempt content

Never target these regardless of category:

- Convention markers: `TODO`, `FIXME`, `HACK`, `NOTE`, `XXX`, `BUG(`,
  `SAFETY:`, `Deprecated:`.
- Language-supplied exempt directives (caller provides the list).
- License and copyright headers.
- Generated files (`// Code generated ... DO NOT EDIT.`,
  `@generated`, protobuf/tonic/openapi output).
- Code inside doc-comment examples (`/// ```` blocks, doctests,
  `>>>` Python examples). The body is executable test code.
- Section headers that are part of a language's doc convention
  (`# Errors`, `# Panics`, `# Safety`, `# Examples` in Rust;
  `Args:`/`Returns:`/`Raises:` in Python Google-style; `@param`,
  `@returns`, `@throws` in JSDoc). The prose **under** them can
  still be a target.

# The five categories

A comment block is a delete-candidate if **any** of these fire.
Category 2 requires the 3+ cluster threshold from
`detect-llm-tells`; categories 1, 3, 4, 5 need one clear
violation each.

## Category 1 — States the obvious

The comment restates what the very next line of code already says.
Inline narration is the canonical case: `// Verb the noun` directly
above a line that does exactly that verb on that noun is **always**
a deletion. No exceptions for "aids scanning" or "consistent style."

Verb-phrase test: if you can mechanically map the comment's
verb+object onto the next statement's verb+object, it's a Category
1 deletion. Examples:

- `// Increment counter` above `counter++`
- `// Return the result` above `return result`
- `// Loop through items` above `for item in items:`
- `// NewFoo creates a new Foo` above `func NewFoo() *Foo` — and on
  a **non-exported** name, this deletes. On an **exported** name in
  a language with tooling enforcement (Go), it stays.

**Keep** comments that add information the code doesn't show:
config paths, validation guarantees, fallthrough rationale,
non-obvious lifetime/ownership constraints.

**Partially obvious comments:** if a comment mixes obvious
restatement with a useful cross-reference or "why," **trim** to
keep the non-obvious part.

## Category 2 — LLM-generated

Run the block through `detect-llm-tells` (cluster scoring; flag at
3+ converging categories). FLAG = delete-candidate. Common cluster:
LLM vocabulary ("crucial," "leverage," "seamless," "robust") +
model openers ("This function…," "This struct…") + transitions
("Moreover," "Furthermore," "Additionally") + signature
restatement. Single-category hits are too noisy — do **not** delete
on one tell alone.

## Category 3 — Adds nothing useful

Filler that says less than the identifier already does: "helper
function for processing," "handles the logic," "performs the
necessary processing," "A struct that holds data." Apply the
verb-phrase test from Category 1; if the comment's only content is
a paraphrase of the name, it deletes.

## Category 4 — Non-idiomatic

The comment violates the language's doc-comment convention in a way
that means the tooling silently drops it or the convention is
load-bearing. Caller fills in the language-specific list; common
patterns:

- **Go:** doc comment not starting with the declared name; blank
  line between doc comment and declaration (godoc drops it);
  `returns true if` instead of `reports whether`; doc comment on
  an unexported function; sentence fragment instead of full
  sentence.
- **Rust:** `///` on a non-`pub` item; `//` where `///` is required
  (under `missing_docs`); `////` (four slashes is a regular
  comment, not a doc); fragments instead of sentences.
- **Python:** missing module/class/function docstring on a public
  API where the project enforces PEP 257; docstring not starting
  with a one-line summary.
- **Node:** JSDoc on a non-exported member; missing `@param`/
  `@returns` on a documented exported function.

**Blank-line gap fix:** if the only violation is a blank line
between a doc comment and its declaration, **fix the gap** — do
not delete the comment.

## Category 5 — Visual noise

Section dividers (`// --- Config ---`, `// =========`,
`// ******`), numbered step labels (`// Step 1:`, `// Phase 2:`),
and decorative separators inside source files. All step/phase
label variants in source comments are deletions.

Do **not** touch format strings showing step numbers to users
(those live in string literals, not comments).

# Decision matrix

| Block content | Action |
|---|---|
| Pure Category 1 / 3 / 5, or Category 4 violation that can't be fixed in place | **Delete** the whole block |
| Category 2 (FLAG from detect-llm-tells) | **Delete** the whole block |
| Mixed: part Category 1/3 + part useful "why" or cross-reference | **Trim** to the useful fragment |
| Category 4 blank-line gap only | **Fix the gap**, keep the comment |
| Exported-identifier doc comment, language has tooling enforcement, even if tautological | **Keep** (doc-comments agent handles rewrites) |
| Convention marker, exempt directive, license header, generated file, example/doctest body | **Keep** |
| Any doubt that isn't narration | **Keep** |

# Hard guardrails

- **Comments only.** Never modify code, signatures, imports, `use`
  declarations, attributes, macros, string literals, or
  configuration values. If a "deletion" would change behavior,
  skip it.
- **Whitespace discipline.** After deleting a block, leave at most
  one blank line. Never leave a dangling empty `//` /
  `///` / `#` line.
- **Doc comments on exported identifiers in tooling-enforced
  languages stay.** Even tautological ones. The doc-comments agent
  improves them.
- **Code examples inside doc comments are code, not prose.** Do not
  touch the content of `/// ```` blocks, doctests,`>>>` examples,
  or `@example` blocks.
- **Narration is never "in doubt."** Hard Rule 0 in every scrub
  agent. The verb-phrase test exists to prevent rationalizing
  "but it aids scanning" — it doesn't.
- **When in doubt, keep it.** But narration is never in doubt.

# Outputs

This skill produces, for each comment block the caller hands it:

- Decision: `DELETE` / `TRIM` / `KEEP`.
- If `TRIM`: the fragment to keep.
- If `DELETE` or `TRIM`: the firing category (1-5) and, for
  Category 2, the `detect-llm-tells` confidence (HIGH/MEDIUM).
- For Category 4 blank-line-gap cases: `FIX_GAP` instead of
  `DELETE`.

The caller assembles these into Edits and runs the language-specific
build-verify command (`go build ./...`, `cargo check`,
`python -m compileall`, `tsc --noEmit`, etc.) before reporting.
