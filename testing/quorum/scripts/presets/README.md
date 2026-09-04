# Seat presets by task class

Class-scoped role sets (squad-quorum-design.md §5): different questions get
different seats, not one global set. Each `*.seats.json` validates against
`render-prompts.mjs` `validateSeats`.

- `completion-default.seats.json` — "is the task complete?" One global
  skeptic. Pair with the hand-written `gates` ballot (deterministic checks).
- `finding-validation.seats.json` — "is this finding real?" One skeptic
  reader over the evidence, paired with a **repro execution seat** produced by
  `exec-seat.mjs` (not an LLM): panel entry
  `{"seat_id": "repro", "jurisdiction": "execution", "required": true, "requires_artifacts": true}`.
  A reproduction that fails to run is a cited veto; a reader vote is never a
  substitute for the execution artifact.

Stakes tiers (measured 2026-09-04; see SKILL.md):

- **low** — gates ballot only, no model seat.
- **default** — gates + one skeptic (the measured optimum).
- **high / finding-shaped** — gates + skeptic + an `exec-seat.mjs` seat with
  `requires_artifacts: true`.
- **panel (explicit opt-in only)** — jurisdiction seats may be added ONLY with
  this sentence appended to every persona: "A veto must cite an acceptance
  criterion's required artifact; the criterion's own text is the bar — do not
  veto for style, robustness, or improvements the criteria do not require."
  Without it the measured jurisdiction panel wrongly held 100% of genuinely
  complete work. Never seat personality-variant panels (measured 95.83%
  lockstep with the single skeptic at 2.4x cost).
