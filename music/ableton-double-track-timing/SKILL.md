---
name: ableton-double-track-timing
description: Find timing slips between doubled guitar tracks in an Ableton Live set, and fix them only when asked. Covers copies of a take nudged a fraction of a beat and doubles that flam. Bundled scripts read the saved .als offline (tempo map, clips, warp markers) and run an exact clip-placement check, a DI attack-envelope cross-correlation and an optional amp-render second opinion, each with a positive control and a gate ledger. Use it whenever doubled or L/R guitars sound flammy, smeared, phasey, noisy or chorus-y where they're doubled, or the user asks to find timing problems, tighten the doubles, check whether two takes are in sync, or audit clip placement, even if they never say "timing". Do NOT use it to transcribe notes (transcribe-guitar-riff), for mix, EQ or level work (odeholm-mix-master), or for general Live UI chores such as export or Save As (ableton-live-computer-use).
---

# Double-track timing in Ableton Live

Doubled guitars only sound huge when the two takes hit together. A copy nudged
by 1/64 of a beat (31 ms at 120 BPM) turns a tight double into a smeared flam
that the user hears as "noise". This skill finds those slips from the saved
set, says which clip moved and by how much, and fixes them only on request.

The method came from a real session. The first detector below found the bar-91
flam that ears and spectrograms had blamed on string noise. The audio
detectors then caught smaller slips, but only where two independent
measurements agreed.

## Host-environment translation

| Action                       | Claude Code                                                                                                                            | Other hosts                                                                   |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Run the scripts              | Bash: `uv run --with-requirements scripts/requirements.txt python scripts/<name>.py ...` (or any Python 3.9+ with numpy and soundfile) | same, via the host's shell tool                                               |
| Render amp stems (optional)  | `Skill("ableton-live-computer-use")`, export recipe                                                                                    | ask the user to export one stem per doubled track                             |
| Move clips (only on request) | `scripts/apply_moves.py --execute` (AbletonMCP socket 127.0.0.1:9877)                                                                  | the same JSON commands from any socket client, or the user moves them by hand |

Paths are relative to this skill's directory (`${CLAUDE_SKILL_DIR}` or
`$SQUAD_SKILL_DIR`).

## Guardrails

- **Read-only by default.** Finding and reporting never touches Live: every
  detector reads the saved `.als` and the audio files on disk. Connect to the
  Live socket only for a fix the user has explicitly asked for. An audit
  request is not a fix request; when in doubt, report and ask.
- **Save first.** Warp markers and MIDI notes exist only in the saved `.als`,
  because the Live API doesn't expose them, so an unsaved session gives stale
  data. Ask the user to save (Cmd+S), then check the file's modification
  time. If the file is older than their last edit, say so.
- **Never edit the `.als` itself.** Fixes go through Live, which the user can
  undo. Make test copies (planted nudges, experiments) somewhere outside the
  project folder.
- **No screen control unless rendering is needed.** Renders go through the
  ableton-live-computer-use skill, and screen-driven exports are fragile: a
  stray keystroke once deleted selected tracks. Never leave tracks or time
  selected, screenshot before every dropdown pick because the rows shift,
  and keep renders to a minimum.
- **A flag is a lead, not a verdict.** Some offsets are deliberate timing
  fixes or rhythmic slice edits. Confirm with audio before recommending a
  move, and say why you left each remaining flag alone.

## Workflow

### 1. Inventory the set

```bash
python scripts/alsio.py "SET.als" --pair "Jayson Scratch=Jason Scratch"
```

This prints the tempo map (read from the set's tempo automation), every audio
track with its usable clips and takes, any missing audio files, and the pairs.
Pairs are found automatically from L/R names ("Gtr L"/"Gtr R", "Rhythm
(Left)"). Doubles named after people or takes aren't discoverable, so ask:
"Which tracks double each other besides the L/R ones?" Then pass each answer
as `--pair "A=B"`. Use `"#3"` for a track index when two tracks share a name.
To see the clips around a reported problem, add `--list "A" "B" --range 336 368`.
That prints start, end, bar, anchor, take file, and the mute and warp state.

### 2. Exact placement check (the most reliable detector)

```bash
python scripts/placement_check.py "SET.als" --pair "A=B" --json placement.json
python scripts/placement_check.py "SET.als" --pair "A=B" --inject "A@357+0.0625"   # positive control
```

Every clip plays a window of one take. Its **anchor** (start minus start
marker, in beats) is where the take's beat 0 lands. Copies of a take moved by
whole beats keep the same fractional anchor, so a copy whose fraction differs
was nudged. The script reports two kinds of flag:

- **Single-track flags:** a clip off the other copies of its own take, with
  the offset in beats and in ms at that tempo, the reference copies, and the
  start that would restore it. A tie (two copies that disagree) falls back to
  the on-grid anchor, and the script says so.
- **Pair alignment flags:** the same two takes (one per side of a double)
  line up differently here than where they pair elsewhere. The script names
  the side that moved by comparing each side with its own copy. This is the
  direct "the double flams here" evidence.

Read the classification before recommending anything:

| Signature                                                                                                        | Usually means                                                                                                 |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Sub-16th offset (0.0625, 0.04, 0.094 beat), on one or two neighbouring clips, "nudged together as one selection" | An accidental nudge. Fix candidate.                                                                           |
| Same offset repeated on several copies of a take in a regular pattern                                            | A deliberate slice or rhythm edit. Leave it alone.                                                            |
| 16th-grid offset (0.25, 0.5 beat)                                                                                | A rhythmic edit, not a timing slip                                                                            |
| Off its own copies, yet the pair check and the audio say it already sits tight with its double                   | An earlier manual timing fix. Leave it alone.                                                                 |
| Takes whose copies carry different warp markers                                                                  | Re-warped slices. They're compared only within their own warp set, so they aren't flagged against each other. |

**Control (gate G1):** inject a fractional shift on a clean clip whose take is
reused, and require `CONTROL OK`. The real state must stay clean at that
clip. The control refuses whole-beat shifts and clips that are the only copy
of their take, because the detector is blind to both by design.

### 3. Confirm with audio, alias-free, where a section repeats

```bash
python scripts/section_compare.py "SET.als" --tracks "A" "B" --ref 341 --test 357 --length 8
```

When the suspect bars copy earlier bars, compare each track's source audio
with its own earlier copy. The same take correlates near 1.000 at its true
shift, and riff periodicity can't fool it. The side that shows the shift is
the side that moved. On the reference song this read +31 ms (corr 0.96) for
the nudged Jayson clips and 0 ms (corr 1.00) for Jason. corr below about 0.9
means the sections aren't the same audio, so the shift means nothing. This is
the audio confirmation to reach for first.

### 4. DI attack-envelope audit (double vs double, per clip)

```bash
python scripts/attack_audit.py "SET.als" --pair "A=B" --json di.json
python scripts/attack_audit.py "SET.als" --pair "A=B" --no-auto --inject "A@248.04-0.04"   # control in your region
```

Each clip's source audio is mapped onto the song timeline through its warp
markers and the tempo map. DI below -25 dBFS counts as silence (an amp's
input gate hears nothing there). The two sides' pick-attack curves are then
cross-correlated in a narrow window (±25 ms) over each clip. The lag is how
far the clip trails its double: + is late, - is early. A slip shows on both
sides with opposite signs. "edge" means the result sits at the window limit
and is unreliable.

- Dense 16th/32nd riffs and low notes alias: attack periods of 125 or 62.5 ms,
  and pitch-period ripple near 20 ms on 7- and 8-strings. Run the `--inject`
  control in the region you care about. If it prints MISSED, the DI method
  can't judge that region, so rely on placement and ears there.
- A pair that prints "no clip measurable" is too quiet for the gate (a quiet
  DI, or audio that isn't DI). Re-run that pair with `--gate-db -40`.
- A handful of controls is enough. Use one per region you'll report on, not
  one per clip.
- Leave the guitar-vs-kick comparison out. It was too noisy to use.

### 5. Amp-render cross-check (optional; only when DI flags matter)

Renders cost screen-driven exports, so do them only when a DI flag would
change your recommendation. Export one stem per doubled track through the
ableton-live-computer-use skill. Use the Rendered Track dropdown with a typed
render start and length, leave nothing selected, and press Esc afterwards.
Then run:

```bash
python scripts/render_xcheck.py "SET.als" --pair "A=B" --di-json di.json \
  --stem "A=renders/a.wav@120" --stem "B=renders/b.wav@120" --json xcheck.json
python scripts/render_xcheck.py ... --control-shift-ms 12     # positive control
```

Render start bar N is beat (N-1)*4 in 4/4. A clip is an **agreed problem**
only when both methods say at least 15 ms, in the same direction, and within
10 ms of each other. "contradict" rows (opposite signs) mean aliasing: listen
instead.

Agreement isn't proof on low-tuned chugs. Both methods follow the same notes,
so both can lock onto the same pitch-period echo (about 20-25 ms on 7- and
8-strings) and agree on a lag that isn't there. If the agreed lag sits within
a few ms of the riff's onset-autocorrelation period, or the other bars of the
same clip pair read tight, report it as unconfirmed and ask for a listen.

### 6. Decide, then report

For each flag, decide from the evidence:

| Evidence                                                                                                                                | Call                                                                  |
| --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Pair alignment flag, plus a single-track flag on the side that moved, plus a sub-16th offset, ideally confirmed by `section_compare.py` | Recommend moving that clip back by the offset                         |
| Agreed problem from DI and render                                                                                                       | Recommend a move of the measured ms, converted to beats at that tempo |
| Single audio method only, or the methods contradict                                                                                     | Report as unconfirmed and suggest listening, solo-paired at that bar  |
| Repeated pattern, 16th-grid offset, or already tight by audio                                                                           | Leave it alone and say why                                            |

Report in this shape:

```markdown
## Double-track timing: <set> (saved <time>)

Pairs checked: <A = B, ...> (auto L/R) + <explicit pairs>

### Likely slips: recommended moves

| Bar | Track / clip (start beat) | Evidence | Move |

### Flags left alone, and why

### Unconfirmed audio flags (listen at these bars)

### Controls run

### Next step (fixing happens only if you ask)
```

Convert positions both ways, because users think in bars: beat 357 is bar
90.2 in 4/4 (bar = beat // 4 + 1). Give moves both as beats (exact; what Live
moves) and as ms (what the ear hears).

### 7. Fix: only on an explicit request

When the user says to apply the fix, follow `references/fixing.md`:

1. Write the moves to `plan.json` and run a dry run with
   `python scripts/apply_moves.py plan.json --als SET.als`. Show the user the
   execution order and any gaps the moves would open.
2. Run `python scripts/apply_moves.py plan.json --execute --out fix/` (add
   `--close-gaps` if the moved clip used to touch its neighbour). The script
   snapshots the arrangement, orders the moves so no clip ever overlaps
   another (Live truncates a clip a move lands on), moves each clip, re-reads
   the track after every move, and stops at the first surprise.
3. Ask the user to save. Then re-run the placement check and the audio
   measurement for the fixed bars.
4. Run the collateral check (gate G4):
   `python scripts/collateral.py --before fix/pre_fix_snapshot.json --live --allowed fix/applied_moves.json`.
   It must print COLLATERAL OK.

### 8. Completion gates

For a full audit or fix pass, keep the ledger in `references/gates-template.md`:

- G1: detector control.
- G2: every placement flag fixed or explained.
- G3: every dual-method problem fixed or explained.
- G4: no collateral.

Explanations go in a `HANDOFF.md`, one line per flag
(`- placement track 3 start 346.3125: why`). `placement_check.py --explained`
and `render_xcheck.py --explained` turn those lines into a pass or fail. An
audit-only request stops after G3. Report G4 as not applicable, because
nothing moved.

## What this cannot decide

- **Taste.** A loose double can be the sound. The scripts measure offsets;
  the user decides what's wrong.
- **Slips the placement check can't see.** These are takes used only once,
  copies that were all nudged together, and unwarped clips. For those, only
  the audio methods (and ears) can speak.
- **Single-method audio verdicts in dense riffs.** On the reference song, the
  render control tracked a 15 ms shift in only about 60% of the
  scratch-double clips. That isn't enough to act on alone.
- **Meter changes.** Bar numbers assume one meter from beat 0. For other
  songs pass `--beats-per-bar`.

## Reference files

- `references/method.md` covers how each detector works: the tempo map,
  anchors, warp-marker grouping, pair alignment, the attack envelope, gates,
  aliasing, the thresholds and why, and the numbers measured on the
  reference song.
- `references/fixing.md` covers the AbletonMCP socket commands, move order,
  gaps and `loop_end`, verification, collateral, and safe stem rendering.
- `references/gates-template.md` has the G1-G4 ledger with runnable checks,
  plus the HANDOFF.md line format.
- `scripts/`: `alsio.py` (set reader and CLI), `placement_check.py`,
  `section_compare.py`, `attack_audit.py`, `render_xcheck.py`,
  `apply_moves.py`, `collateral.py`, `live_socket.py`.
- `evals/files/make_fixtures.py` builds a planted-nudge copy of a set for
  testing, and proves that nothing else changed.
