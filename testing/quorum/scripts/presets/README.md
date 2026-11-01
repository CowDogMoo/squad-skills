# Seat presets by task class

Class-scoped role sets (squad-quorum-design.md §5): different questions get
different seats, not one global set. Each `*.seats.json` validates against
`render-prompts.mjs` `validateSeats`. Every class has a one-seat default and a
`-panel` variant that is used only when the user explicitly asks for a panel.

- `completion-default.seats.json` — "is the task complete?" One global
  skeptic, the configuration the 2026-09-04 benchmark measured (SKILL.md
  states its caveats). Pair with the `gates` ballot
  (deterministic checks).
- `completion-panel.seats.json` — opt-in 3-seat panel (`skeptic`,
  `correctness`, `spec-coverage`).
- `tradeoff-evaluation.seats.json` — "does option A make sense vs. option B?"
  One global skeptic over the staged evidence. Pair with a `gates` / benchmark
  execution ballot.
- `tradeoff-evaluation-panel.seats.json` — opt-in 3-seat panel (`skeptic`,
  `architecture-parity`, `empirical-evidence`).
- `finding-validation.seats.json` — "is this finding real?" One skeptic reader
  over the evidence, paired with a **repro execution seat** produced by
  `exec-seat.mjs` (not an LLM): panel entry
  `{"seat_id": "repro", "jurisdiction": "execution", "required": true, "requires_artifacts": true}`.
  A reproduction that runs without confirming the claim is a cited veto; one
  that cannot start (timeout, spawn failure, exit 126/127) abstains. A reader
  vote is never a substitute for the execution artifact.
- `finding-validation-panel.seats.json` — opt-in 3-seat panel
  (`skeptic-reader`, `reachability-verifier`, `evidence-corroborator`), still
  paired with the repro execution seat.

Stakes tiers (see SKILL.md):

- **low** — gates ballot only, no model seat.
- **default** — gates + one skeptic (best measured so far, 2026-09-04).
- **high / finding-shaped** — gates + skeptic + an `exec-seat.mjs` seat with
  `requires_artifacts: true`.
- **panel (explicit opt-in only)** — a `-panel` preset or custom jurisdiction
  seats. Every panel seat persona MUST end with this sentence: "A veto must
  cite an acceptance criterion's required artifact; the criterion's own text is
  the bar — do not veto for style, robustness, or improvements the criteria do
  not require." Without it the measured jurisdiction panel wrongly held 100% of
  genuinely complete work; with it, panels are still unmeasured. Never seat
  personality-variant panels (measured 95.83% lockstep with the single skeptic
  at 2.41x cost).
