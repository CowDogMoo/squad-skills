---
name: enqueue-coverage-targets-rust
description: "Orchestrator-workers pattern for Rust test coverage: a deterministic Bash command runs cargo llvm-cov (fallback cargo tarpaulin) and queues source files below target into /tmp/squad-targets.txt, then you drain it by writing inline #[cfg(test)] mod tests blocks. Load on iteration 1 of any Rust coverage-raising agent run."
allowed-tools: Bash, Read, Write, Edit
metadata:
  author: Jayson Grace
  version: 1.0.0
---

# Enqueue Coverage Targets (Rust)

You are entering an **orchestrator-workers** pattern (Anthropic, "Building Effective Agents"). The orchestrator is this skill plus the Bash command below. The worker is you, after Step 1.

The pattern exists because every previous attempt at letting the agent discover gaps autonomously ended the same way: 30+ iterations of measuring, 0 tests written. Discovery is deterministic — it does not need a reasoning model. The model's job is the part that needs reasoning: writing tests that exercise real code paths.

# Step 1 — Orchestrator (your iteration immediately after this skill call)

Your **next tool call** must be this exact Bash command, verbatim:

```bash
set -e
TARGET="${SQUAD_COVERAGE_TARGET:-75}"
mkdir -p /tmp/squad-rust
# Clear stale queue from prior runs of other-language agents.
rm -f /tmp/squad-targets.txt
# Language gate: refuse to proceed if this isn't a Rust project.
if [ ! -f Cargo.toml ] && [ ! -f Cargo.lock ]; then
  echo "NOT_A_RUST_PROJECT: no Cargo.toml in $(pwd). This agent only works in Rust projects. Stop here and emit an honest 'no Rust source' report — do NOT pivot to other languages." >&2
  echo "" > /tmp/squad-targets.txt
  echo "=== queue size ==="; echo 0
  exit 0
fi
if command -v cargo-llvm-cov >/dev/null 2>&1; then
  cargo llvm-cov --json --output-path /tmp/squad-rust/cov.json --quiet 2>&1 \
    | tee /tmp/squad-tests.out > /dev/null || true
  TOOL=llvm-cov
elif command -v cargo-tarpaulin >/dev/null 2>&1; then
  cargo tarpaulin --out Json --output-dir /tmp/squad-rust --quiet 2>&1 \
    | tee /tmp/squad-tests.out > /dev/null || true
  TOOL=tarpaulin
else
  echo "NO_COVERAGE_TOOL: install cargo-llvm-cov or cargo-tarpaulin" >&2
  TOOL=none
fi
python3 - "$TARGET" "$TOOL" <<'PY'
import json, sys
target = int(sys.argv[1])
tool = sys.argv[2]
rows = []
if tool == "llvm-cov":
    try:
        with open("/tmp/squad-rust/cov.json") as f:
            data = json.load(f)
        for fr in data.get("data", []):
            for fl in fr.get("files", []):
                pct = fl.get("summary", {}).get("lines", {}).get("percent", 0)
                if pct < target:
                    rows.append((pct, fl["filename"]))
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass
elif tool == "tarpaulin":
    try:
        with open("/tmp/squad-rust/tarpaulin-report.json") as f:
            data = json.load(f)
        for fname, info in data.get("files", {}).items():
            total = info.get("coverable", 0) or 1
            covered = info.get("covered", 0)
            pct = 100.0 * covered / total
            if pct < target:
                rows.append((pct, fname))
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass
rows.sort()
with open("/tmp/squad-targets.txt", "w") as f:
    for pct, path in rows:
        f.write(f"{path}\t{pct:.1f}%\t(target {target}%)\n")
print(f"queued {len(rows)} files below {target}% (tool={tool})")
PY
echo "=== /tmp/squad-targets.txt (worker queue) ==="
cat /tmp/squad-targets.txt 2>/dev/null || echo "(empty queue)"
echo "=== queue size ==="
wc -l < /tmp/squad-targets.txt 2>/dev/null || echo 0
```

Export `SQUAD_COVERAGE_TARGET` to your run's target percent before invoking, or it defaults to 75. The script auto-detects `cargo-llvm-cov` (preferred) or `cargo-tarpaulin`.

`/tmp/squad-targets.txt` columns are tab-separated: `<source-file-path>\t<pct>%\t(target N%)`. Sorted ascending by current coverage so the worst-covered files are first.

If neither coverage tool is installed, the queue will be empty — document the missing tool under Skipped Functions and exit honestly. Do NOT install packages on the user's system.

# Step 2 — Worker mode (every iteration after Step 1)

Read `/tmp/squad-targets.txt` once. That list is your queue. Drain it in batches of 3–5 files until empty OR you have used 80% of your cost budget OR 80% of your iteration budget.

For each batch:

1. **Read iteration:** parallel `Read` calls per file in the batch — the `.rs` source file from the queue. Look at the bottom of the file to see if an existing `#[cfg(test)] mod tests` block is present, and what it covers. Skipping this is how previous runs destroyed working tests.
2. **Write/Edit iteration:** parallel calls, one per file in the batch:
   - If the source file already has a `#[cfg(test)] mod tests` block, use `Edit` to ADD test functions INSIDE that block. **Never `Write` over an existing source file — `Write` truncates and would destroy the non-test code too.**
   - If no `#[cfg(test)] mod tests` block exists, use `Edit` to append one at the end of the file.
   - **NEVER create files in `tests/` directory** — Rust convention here is inline `#[cfg(test)] mod tests` at the bottom of each source file.
   - Every name your test references must appear in the source you actually read this iteration. Don't guess module paths or symbol names.
   - Each `mod tests` must contain at least one real `#[test] fn` with meaningful assertions on the lowest-coverage functions. Empty stubs are forbidden.
3. Move to the next batch. Do NOT re-measure coverage between batches.

Aim for 3+ files per Write/Edit iteration. Single-file iterations are wasteful.

# Step 3 — Verify and report (last 2–3 iterations)

Run `cargo build --tests` then `cargo test --quiet`. Fix only test code on failure.

**Re-measurement is mandatory for the "After" coverage number.** Re-run the Step-1 command and copy real per-file percentages into your report. If you skip this step, the "After" column MUST say "not measured" — never invent a percentage.

# Hard constraints (these override your judgment)

- **Edits to source `.rs` files are limited to appending or extending `#[cfg(test)] mod tests` blocks.** Never modify production code outside those blocks. Untestable without source changes → Skipped Functions.
- **Never destroy existing tests.** `Write` truncates. Before any `Write` on an existing path, you must have read its current contents and be preserving every `#[test] fn` in it. Default to `Edit` for any file that already has a `mod tests` block.
- **`Edit` failed → re-Read, fix the anchor, retry `Edit`. NEVER fall back to `Write` on a file you just tried to `Edit`.** "Text not found" means your `old_string` is wrong, not that the file should be overwritten. Three failed `Edit` attempts on the same file → skip the module and document it under Skipped Functions. This rule overrides any prior agent guidance that said "switch to Write immediately" — that guidance was wrong and has destroyed work.
- **No revert via git.** Don't `git stash`, `git checkout`, or `git restore` to undo your edits — they destroy prior agents' work. If you need to undo, use `Edit` with the previous content.
- **No coverage commands during writing.** Re-running `cargo llvm-cov`/`cargo tarpaulin` between batches is forbidden. The queue in `/tmp/squad-targets.txt` is your sole source of truth until Step 3.
- **Do not load `Skill("score-coverage-and-report-gaps")`.** That skill's five-phase loop is what you're replacing.
- **Imports complete.** Bring `use` statements into the test module for every type referenced. Missing imports are a top quality bug.
- **Idiom:** `#[test]` (or `#[tokio::test]` for async); `rstest` or `test-case` for parameterized tests; `assert_matches!` over `assert!(matches!(...))`; `Result`-returning tests with `?`; `tempfile::tempdir()` for filesystem tests.

# Why this pattern works

The previous agent shape (let the LLM decide what to measure, what to prioritize, when to start writing) failed every run: 30–50 iterations on measurement, 0–3 tests written. The bug isn't the prompt — it's the agent having discretion over a step that doesn't need discretion. This skill takes that discretion away by:

1. Embedding the exact Bash command for discovery (deterministic).
2. Constraining post-Step-1 tool use to Read / Write / Edit (no coverage commands until final verify).
3. Defining a fixed batch shape (Read iter → Write iter → repeat) so the agent can't get stuck in single-file over-thoroughness.

The model's reasoning is reserved for the only part of the task that needs it: writing test code that exercises specific functions.
