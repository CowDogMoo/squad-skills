# Gate ledger template (unlazy-style)

Copy this to the job's working folder as `GATES.md`. Replace `SET`, the pair,
and the control clips. Record the actual commands, settings, exit codes and
measured outputs; mark a gate only after all its checks pass. Controls belong
to every audit, including a targeted check: without a clean negative control
and sensitive positive controls, neither silence nor flags are trustworthy.
Keep `HANDOFF.md` beside it. Run every CHECK from the skill directory, or
prefix the script paths with `${CLAUDE_SKILL_DIR}/`.

```markdown
# Gates: double-track timing, <song>

Scope: find every timing slip between the doubled tracks of <SET>, fix the
clear ones only if the user asked, and explain every flag left alone.

## Pair coverage

| Pair or clean reference set | Placement evidence | DI evidence and regional controls | Independent render evidence | Verdict / next action |
| --- | --- | --- | --- | --- |
| <every pair in scope> | pending | pending | pending or unavailable | clean / flagged with fix / unconfirmed with reason |

Clean requires executed placement and audio evidence supported by controls.
Missing independent renders leave G3 manual/unconfirmed for that pair, even
when its placement and DI checks are clean.

- [ ] G1a: known-clean reference stays clean under placement and DI checks with the audit's settings
  CHECK: python scripts/placement_check.py "CLEAN.als" --pair "C=D" --json clean-placement.json
  CHECK: python scripts/attack_audit.py "CLEAN.als" --pair "C=D" --json clean-di.json
  EXPECT: no placement or pair-alignment flags; measurable audio lags consistent with the clean reference, without flags
  EVIDENCE: pending (record flags, lags, settings and why this reference is known clean)

- [ ] G1b: the placement detector catches an injected fractional nudge on a clean, reused clip from a take with no flagged copies, and the real state stays clean there
  CHECK: python scripts/placement_check.py "SET.als" --pair "A=B" --inject "A@<start>+0.0625"
  EXPECT: CONTROL OK
  EVIDENCE: pending

- [ ] G1c: DI detects an injected slip in each reported region, including the clean reference
  CHECK: python scripts/attack_audit.py "SET.als" --pair "A=B" --no-auto --inject "A@<start>+<delta>"
  EXPECT: CONTROL OK (injected ms magnitude >= --min-ms / 2; abs(baseline lag + injected ms) < --window-ms - 1; measured lag within 6 ms of expected)
  EVIDENCE: pending (record each region, baseline, expected shift and measured shift; MISSED leaves the region unconfirmed)

- [ ] G2: every placement flag on the checked tracks is fixed or explained in HANDOFF.md
  CHECK: python scripts/placement_check.py "SET.als" --pair "A=B" --explained HANDOFF.md
  EXPECT: PLACEMENT OK
  EVIDENCE: pending (include every track/start key; separately reconcile all pair-alignment flags from placement.json because --explained checks only single-track flags)

- [ ] G3: every clip that DI and render agree is >= 15 ms off its double is fixed (re-measured) or explained in HANDOFF.md
  CHECK: python scripts/render_xcheck.py "SET.als" --pair "A=B" --di-json di.json --stem "A=a.wav@<beat>" --stem "B=b.wav@<beat>" --explained HANDOFF.md
  EXPECT: AUDIO OK
  EVIDENCE: pending

- [ ] G4: nothing in the arrangement changed except the moves in fix/applied_moves.json
  CHECK: python scripts/collateral.py --before fix/pre_fix_snapshot.json --after "SET.als" --allowed fix/applied_moves.json
  EXPECT: COLLATERAL OK
  EVIDENCE: pending
```

Before completing G3 with renders, run `render_xcheck.py` with
`--control-shift-ms` and retain its catch rate and unresolvable clips. Passing
G2's explanation check means flags are accounted for, not that they were fixed.
Recommendations left for the user need a HANDOFF line just like flags left alone.

## Variants

- **Audit only (no fix requested):** G4 doesn't apply; record
  `ABANDON: G4 nothing was moved (audit only)` and report it as such.
- **No renders:** G3 becomes a manual gate. Every DI flag goes in the report
  as unconfirmed, with its bar, and the user decides whether a render is
  worth it. Record each affected pair as G3 manual/unconfirmed, with the missing
  render as the reason; do not mark G3 passed because no comparison ran. Don't
  call a DI-only flag a confirmed problem.
- **The DI control MISSED in a region:** note in HANDOFF.md that the audio
  methods can't judge that region, and rely on G2 there.

## HANDOFF.md line format

One line per flag, starting with the key that the `--explained` checks parse.
Give the reason as evidence, not as an opinion:

```markdown
# Timing audit: items explained or left for a decision

- placement track 1 start 209.0098: bar 53, +0.094 beat off its take, but DI and render both put it within 4-8 ms of its double. An earlier deliberate fix; left alone.
- placement track 1 start 268.5: bars 68-70 slice edit, the same -0.5 beat offset repeated 3x. A rhythmic edit, not a nudge; left alone.
- placement track 3 start 346.3125: +0.0625 off its take, but it pairs with Jayson identically in bars 87 and 91 (pair check clean); moving it would make it 31 ms early. Left alone.
- audio track 3 start 149.25: DI -22 vs render +16 ms (contradict), a 32nd-note figure; aliasing. Listen if in doubt.
```

Keys: `placement track <index> start <beat>` for placement flags, and
`audio track <index> start <beat>` for agreed audio problems. A flag that a
fix removed needs no line after re-measurement proves it gone. Account for
pair-alignment flags in the report using both tracks and clip starts; the
parser does not check those rows. Multiple flags may share a reason, but list
every key. Include audio-only flags and manual G3 reasons in the report even
when there are no agreed render problems for `--explained` to parse.
