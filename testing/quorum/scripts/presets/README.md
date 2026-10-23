# Seat presets by task class

Class-scoped role sets (squad-quorum-design.md §5): different questions get
different seats, not one global set. Each `*.seats.json` validates against
`render-prompts.mjs` `validateSeats`.

- `completion-default.seats.json` — "is the task complete?" Default 3-seat
  subagent panel (`skeptic`, `correctness`, `spec-coverage`), with the
  veto-scope rule baked into every seat persona. Pair with the `gates` ballot
  (deterministic checks).
- `tradeoff-evaluation.seats.json` — "does option A make sense vs. option B?"
  3-seat subagent panel (`skeptic`, `architecture-parity`,
  `empirical-evidence`) for architectural, design, and trade-off evaluations.
  Pair with a `gates` / benchmark execution ballot.
- `finding-validation.seats.json` — "is this finding real?" 3-seat subagent
  panel (`skeptic-reader`, `reachability-verifier`, `evidence-corroborator`)
  over the evidence, paired with a **repro execution seat** produced by
  `exec-seat.mjs` (not an LLM): panel entry
  `{"seat_id": "repro", "jurisdiction": "execution", "required": true, "requires_artifacts": true}`.
  A reproduction that fails to run is a cited veto; a reader vote is never a
  substitute for the execution artifact.

Stakes tiers (see SKILL.md):

- **low** — gates ballot only, no model seats.
- **default** — gates + 3-seat subagent panel
  (`completion-default.seats.json` or `tradeoff-evaluation.seats.json`),
  spawned as independent subagents in parallel.
- **high / finding-shaped** — gates + 3-seat subagent panel + an
  `exec-seat.mjs` seat with `requires_artifacts: true`.
- **custom jurisdiction seats** — any added seat MUST append this sentence to
  its persona: "A veto must cite an acceptance criterion's required artifact;
  the criterion's own text is the bar — do not veto for style, robustness, or
  improvements the criteria do not require." Without it, jurisdiction panels
  hold genuinely complete work on non-criterion nitpicks. Never seat
  personality-variant panels (skeptic/technical/pragmatic) without distinct
  jurisdictions.
