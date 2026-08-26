# Go

Queue unit: package (import path). `/tmp/squad-uncovered.out` lines are
`<file:line>\t<pct>\t<func>` from `go tool cover -func`.

## Pick targets for a queued package

```bash
grep '<pkg-path>' /tmp/squad-uncovered.out | sort -t$'\t' -k2 -n | head -8
```

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

```bash
go build ./... && go test ./...
go test -cover ./... 2>&1 | grep "coverage:"
```
