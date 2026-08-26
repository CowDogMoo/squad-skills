# Rust

Queue unit: source file. `/tmp/squad-uncovered.out` lines are
`<file>\t<hit-count>\t<fn-name>` (cargo-llvm-cov) or
`<file>\t<hit-count>\tline:<n>` (tarpaulin fallback).

## Pick targets for a queued file

```bash
grep -F '<file>' /tmp/squad-uncovered.out | sort -t$'\t' -k2 -n | head -8
```

Take the 3–5 lowest-hit entries.

## Files — the source-edit boundary

Rust unit tests live inside the source file in a `#[cfg(test)] mod tests`
block, so this is the one language where you edit source files. The
boundary is: append a new `mod tests` block, or `Edit` inside an existing
one. Never touch code outside that block; a function that can't be tested
without a production change goes under Skipped.

Read the source file (including any existing `mod tests`) before writing.
If a `mod tests` block already exists, `Edit` it — writing the whole file
would discard everything else in it.

## Idiom

- `#[test]`, or `#[tokio::test]` for async.
- `rstest` or `test-case` for parameterized tests.
- `assert_matches!` over `assert!(matches!(...))`.
- `Result`-returning tests with `?`.
- `tempfile::tempdir()` for filesystem tests.
- `use` every type the test module references (`use super::*;` covers the
  parent module only).

## Verify and re-measure (Step 3)

```bash
cargo build && cargo test
cargo llvm-cov --summary-only   # or: cargo tarpaulin --out Stdout
```
