# Node.js / TypeScript

Queue unit: source file. `/tmp/squad-uncovered.out` lines are
`<file>\t<hit-count>\t<fn-name>` from istanbul's `coverage-final.json`.
The enqueue script prefers `vitest` and falls back to `jest`, detected
from `package.json`.

## Pick targets for a queued file

```bash
grep -F '<file>' /tmp/squad-uncovered.out | sort -t$'\t' -k2 -n | head -8
```

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

```bash
npx vitest run            # or: npx jest
npx vitest run --coverage # or: npx jest --coverage
```
