# Node.js / TypeScript

Queue unit: source file. `/tmp/squad-uncovered.out` lines are
`<file>\t<hit-count>\t<fn-name>` from istanbul's `coverage-final.json`.
The enqueue script prefers `vitest` and falls back to `jest`, detected
from `package.json`.

## Pick targets for a queued file

```bash
awk -F'\t' -v u='<file>' '$1 == u' /tmp/squad-uncovered.out | sort -t$'\t' -k2 -n | head -8
```

These are the rows `enqueue.sh` printed per unit in Step 1. If
`/tmp/squad-uncovered.out` is gone by now (a fresh `/tmp` per command), use
that output instead of re-measuring.

Take the 3–5 lowest-hit functions.

## Files

- Mirror rule: `src/foo.ts` → `src/foo.test.ts` (or the project's existing
  convention — `__tests__/foo.test.ts`, `*.spec.ts`; follow whatever the
  repo already uses).
- Read the source file plus every existing test file for it before writing.
- Match the project's module system (ESM vs CommonJS) and distinguish
  default from named exports; a mis-cased or wrong-style import is the top
  compile failure in generated tests.

## Idiom

- `describe` / `test` / `expect`.
- `vi.mock` (vitest) or `jest.mock` for module mocks.
- `beforeEach` / `afterEach` for setup; `test.each` / `it.each` for
  parameterized cases.

## Verify and re-measure (Step 3)

Run from the project root (or `"$work"` when Step 1a created a working copy):

```bash
npx vitest run --coverage # or: npx jest --coverage
```
