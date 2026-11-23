# Gate ledger template (unlazy-style)

Copy this to the job's working folder as `GATES.md`. Replace `SET`, the pair,
and the control clip, then mark each gate only when its CHECK prints the
EXPECT marker with exit code 0. Keep `HANDOFF.md` beside it. Run every CHECK
from the skill directory, or prefix the script paths with
`${CLAUDE_SKILL_DIR}/`.

```markdown
# Gates: double-track timing, <song>

Scope: find every timing slip between the doubled tracks of <SET>, fix the
clear ones only if the user asked, and explain every flag left alone.

- [ ] G1: the placement detector catches an injected fractional nudge on a clean, reused clip, and the real state stays clean there
  CHECK: python scripts/placement_check.py "SET.als" --pair "A=B" --inject "A@<start>+0.0625"
  EXPECT: CONTROL OK
  EVIDENCE: pending

- [ ] G2: every placement flag on the checked tracks is fixed or explained in HANDOFF.md
  CHECK: python scripts/placement_check.py "SET.als" --pair "A=B" --explained HANDOFF.md
  EXPECT: PLACEMENT OK
  EVIDENCE: pending

- [ ] G3: every clip that DI and render agree is >= 15 ms off its double is fixed (re-measured) or explained in HANDOFF.md
  CHECK: python scripts/render_xcheck.py "SET.als" --pair "A=B" --stem "A=a.wav@<beat>" --stem "B=b.wav@<beat>" --explained HANDOFF.md
  EXPECT: AUDIO OK
  EVIDENCE: pending

- [ ] G4: nothing in the arrangement changed except the moves in fix/applied_moves.json
  CHECK: python scripts/collateral.py --before fix/pre_fix_snapshot.json --after "SET.als" --allowed fix/applied_moves.json
  EXPECT: COLLATERAL OK
  EVIDENCE: pending
```

## Variants

- **Audit only (no fix requested):** G4 doesn't apply; record
  `ABANDON: G4 nothing was moved (audit only)` and report it as such.
- **No renders:** G3 becomes a manual gate. Every DI flag goes in the report
  as unconfirmed, with its bar, and the user decides whether a render is
  worth it. Don't call a DI-only flag a problem.
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
fix removed needs no line.
