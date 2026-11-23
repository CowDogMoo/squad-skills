# Go

Queue unit: package (import path). `/tmp/squad-uncovered.out` lines are
`<file:line>\t<pct>\t<func>` from `go tool cover -func`.

## Pick targets for a queued package

```bash
awk -F'\t' -v u='<pkg-path>/' 'index($1, u) == 1 && substr($1, length(u) + 1) !~ /\// && $2 != "100.0%"' \
    /tmp/squad-uncovered.out | sort -t$'\t' -k2 -n | head -8
```

These are the rows `enqueue.sh` printed per unit in Step 1. If
`/tmp/squad-uncovered.out` is gone by now (a fresh `/tmp` per command), use
that output instead of re-measuring.

Take the 3–5 lowest-percentage functions. Packages with no test files at
all don't print a `coverage:` line and so never reach the queue — if you
notice one while reading, treat it as a bonus target, not a reason to
re-measure.

## Files

- Mirror rule: `foo.go` → `foo_test.go` in the same directory.
- Read one or two of the largest `.go` files in the package plus **every**
  existing `_test.go` before writing. Confirm the import path from the
  file header or `go list`, never from the directory name.

## Idiom

- Black-box `package foo_test` by default.
- Table-driven `[]struct{...}` with `t.Run` for 2+ cases.
- `t.TempDir()` for filesystem tests; no global state swapping.
- Import everything you touch (`runtime.GOOS` → `"runtime"`,
  `filepath.Join` → `"path/filepath"`).

## Verify and re-measure (Step 3)

Run from the module root (or `"$work"` when Step 1a created a working copy):

```bash
go build ./... && { go test ./... -coverprofile=/tmp/squad-after.out -count=1; go tool cover -func=/tmp/squad-after.out | tail -1; }
```
