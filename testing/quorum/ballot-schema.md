# cquorum ballot contract

A ballot is one seat's answer to the completion question for one staged
fixture. Ballots are plain JSON files at `<run-dir>/ballots/<seat_id>.json`.
The judge (`judge.mjs`) consumes them; the seat runner (`run-seats.mjs`)
produces them by extracting the voter's final JSON message.

## Ballot JSON shape

```json
{
  "seat_id": "spec-coverage",
  "jurisdiction": "spec-coverage",
  "verdict": "complete",
  "unmet": [
    { "criterion": "criterion text as stated or paraphrased", "evidence": "file:line or observation backing the veto" }
  ],
  "evidence": ["citation backing an affirmation"],
  "confidence": 0.85
}
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `seat_id` | string | yes | non-empty; MUST equal the ballot filename stem and the panel seat it answers for. Mismatch = schema-invalid. |
| `jurisdiction` | string | yes | non-empty; the scope the seat judged (a jurisdiction name, or `global` for personality seats). |
| `verdict` | string | yes | exactly one of `"complete"`, `"incomplete"`, `"abstain"`. |
| `unmet` | array | no (default `[]`) | each item an object with non-empty string `criterion` and string `evidence`. Wrong item shape = schema-invalid. |
| `evidence` | array of strings | no (default `[]`) | citations supporting the verdict. |
| `confidence` | number | no | finite, in `[0, 1]` inclusive when present. |
| `artifacts` | object | no | execution evidence (e.g. `exit_code`, `output_sha256`, `duration_ms`); values must be strings, numbers, or booleans. Produced by `exec-seat.mjs`; REQUIRED in practice on any panel seat declared `requires_artifacts` (see demotion rule 3). |

Unknown extra keys are tolerated (voters ramble); the core fields above are
validated strictly. A ballot that fails any rule is **malformed** and is never
repaired — the judge records the seat as `malformed` with the specific
schema faults.

## Demotion rules (valid ballots, adjusted verdicts)

1. **Uncited veto → abstain.** `verdict: "incomplete"` with a missing or
   empty `unmet` array is DEMOTED to abstain, and the seat gets the fault
   `veto without citation`. A veto must be actionable: no cited unmet
   criterion, no veto.
2. **Contradictory affirmation → abstain.** `verdict: "complete"` with a
   non-empty `unmet` array is contradictory; it is demoted to abstain with a
   recorded fault. A gate against false-completes must not count a
   self-contradicting ballot as an affirmation.

3. **Ungrounded vote on an execution seat → abstain.** When the panel entry
   declares `"requires_artifacts": true`, any `complete` or `incomplete`
   ballot whose `artifacts` object is missing or empty is demoted to abstain
   with the fault `vote without required execution artifacts`. "Looks like it
   would work" is not evidence (squad-quorum-design §2.3); only an execution
   that ran is. An explicit `abstain` needs no artifacts.

Demotion is a judge-side interpretation of a schema-VALID ballot; it is
distinct from `malformed` (schema-invalid, ballot discarded entirely).

`panel.json` seats may carry `"requires_artifacts": true` (boolean; any other
type is protocol corruption) alongside `seat_id`, `jurisdiction`, and
`required`.

## Seat states (as recorded in verdict.json)

| State | Meaning |
|---|---|
| `complete` | schema-valid ballot, verdict `complete`, empty `unmet` |
| `veto` | schema-valid ballot, verdict `incomplete`, at least one cited unmet criterion |
| `abstain` | verdict `abstain`, or a demoted ballot (rules above; fault recorded) |
| `absent` | no `ballots/<seat_id>.json` file exists (hang/kill/no output) |
| `malformed` | ballot file unparsable or schema-invalid (never repaired) |

## Judge semantics (unanimity)

`verdict.json` verdict is `COMPLETE` **iff every required panel seat is in
state `complete`**. Any `veto`, `abstain`, `absent`, or `malformed` required
seat forces `NOT_COMPLETE`. Seats with `"required": false` in `panel.json`
are recorded but never block (all cquorum panels mark every seat required;
`required` defaults to `true` when omitted).

`work_queue` aggregates every cited unmet criterion from every `veto` seat,
in stable order (panel order, then within-ballot `unmet` order),
**deduplicated by exact `criterion` string** — the first citing seat's entry
(its `evidence` and `seat_id`) wins. The work queue is the actionable
output: what to fix before re-judging.

`counts` holds integer tallies only: per-state counts plus `required`
(number of required seats) and `seats` (panel size).

## Canonical verdict.json output

- Object keys recursively sorted; arrays keep semantic order.
- 2-space indent, single trailing newline.
- No timestamps; no floats in derived fields (ballot `confidence` is never
  echoed into verdict.json).
- Judging the same run dir twice yields byte-identical verdict.json.

## Exit codes (judge.mjs)

- `0` — a verdict was written (COMPLETE or NOT_COMPLETE alike).
- `2` — protocol corruption, no verdict written: missing/unparsable/invalid
  `panel.json`, duplicate `seat_id` in the panel, or an unknown file in
  `ballots/` (any non-dotfile that is not `<panel seat_id>.json`).

Seat-level problems (absent/malformed ballots) are NOT corruption — they are
judged as designed and produce a NOT_COMPLETE verdict with exit 0.
