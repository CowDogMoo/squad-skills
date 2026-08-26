# Python

Queue unit: module (source file). `/tmp/squad-uncovered.out` lines are
`<file>:<line>`, one per statement the current suite never executes.

## Pick targets for a queued module

```bash
grep -F '<file>:' /tmp/squad-uncovered.out | head -15
```

Aim tests at the functions containing those lines.

## Files

- Mirror rule: `myapp/core/store.py` → `tests/core/test_store.py` (or
  `tests/test_store.py` for flat layouts — follow the repo).
- Read the source module plus every existing `test_*.py` that targets it
  before writing.
- Set `SQUAD_PYTHON_PKG` to the top-level package (e.g. `myapp`) before
  Step 1 if the repo isn't laid out with sources at the root; otherwise
  `--cov=.` measures test files too and skews the numbers.

## Idiom

- `pytest` style: plain `def test_*` functions, fixtures, `tmp_path`,
  `monkeypatch`.
- `@pytest.mark.parametrize` with `pytest.param(..., id="name")` for 2+
  cases.
- Import everything you reference (`pathlib.Path`, etc.).

## Verify and re-measure (Step 3)

```bash
python -m pytest -q
python -m pytest --cov="${SQUAD_PYTHON_PKG:-.}" -q 2>&1 | tail -20
```
