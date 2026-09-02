---
name: quad-cortex-preset-editing
description: Edit a Quad Cortex preset from the Cortex Control desktop app via screen control - load a Neural Capture into a preset, put the blocks in the right order, bypass what should not be in the signal path, set makeup gain on the right knob, save, and report honestly which claim rung the result reached (configured, structurally faithful, or measured). Use for "set up this preset", "put my capture in a preset", "use the amp and cab capture", "fix the block order", "why is this preset laggy or thin", "clean up my QC preset", or any request to change what is on a Quad Cortex preset grid. Do NOT use for making a Neural Capture (that is quad-cortex-plugin-capture), for editing presets on the hardware touchscreen, or for tone advice with no preset to edit.
---

# Quad Cortex preset editing (Cortex Control)

Change what is on a Quad Cortex preset grid so a Neural Capture is used the
way it was captured, then say exactly how much that proves.

Rig: Cortex Control v4.0.0 on macOS, two monitors.

## Objective and guardrails

Done means: the preset is saved with the requested capture loaded, the block
order is canonical, nothing sits in the path that is absent from the
reference, and the final report names the claim rung reached and the
measurement that would reach the next one.

- **Never claim "closer", "sounds like", "matches", or "optimized for the
  sound" without the measured same-performance comparison.** Structural
  cleanup is rung 2, not rung 3.
- **Click every block and read its panel before changing anything.** Icon
  colour is not block type — yellow was Pitch, the teal cube was a Reverb.
- **Bypass, don't delete**, unless the user says delete. Bypass is reversible
  and keeps the user's settings.
- **Makeup gain goes on the capture block's Volume, never its Gain.** Gain
  changes how hard the model is driven.
- **Save is a real write to the user's preset.** Do it once, at the end, after
  a screenshot confirms every change, and confirm the "Preset saved." toast.
- **The preset and the plugin are the user's instrument. Editing either in
  service of a *measurement* is their call, not yours.** This skill's remit is
  the structural cleanup the user asked for. Anything you want to change only
  so a number comes out cleaner — a gate, a pitch block, an EQ, a level — gets
  named to the user with its cost, and waits for a yes. Restore it afterwards
  and say so.
- Stop and ask if: the capture the user named is not in MY CAPTURES; the
  preset has more than one row with an input assigned (parallel paths — the
  bucket sort below assumes one path); a block's panel shows something you
  cannot identify; or a drag lands somewhere unexpected and undo is unclear.

## Terminology

- **Preset** — the grid: rows of blocks, scenes A–H. "Profile" is not QC
  language; users may say it and mean either preset or capture.
- **Neural Capture** ("capture") — the model of an amp, pedal, or plugin.
  Lives in a Neural Capture block.
- **Block** — one square on the grid. Bypassed blocks render dimmed or filled;
  active blocks have a bright outline.
- **IR Loader** — the block that loads a cabinet impulse response.
- **Input block** ("In 1") — per-preset input gain and input gate. Impedance
  and Instrument/Line type live in the global I/O settings, not the preset.

## Host-environment translation

| Abstract action | Cowork / desktop bridge |
| --- | --- |
| Resolve + request app control | `computer_resolve_access` → `computer_request_access` with app "Cortex Control" (bundle `com.NeuralDSP.CortexControl`), entries passed verbatim |
| Look | `computer_screenshot` (scale 0.6 for orientation, 1.0 before precise clicks), `computer_zoom` for panel values |
| Click / drag / type | `computer_left_click`, `computer_double_click`, `computer_left_click_drag`, `computer_type`, `computer_key` |
| Read the reference facts | connected project folder via `device_bash` / `device_stage_files` |

Granting Cortex Control hides every other app — Ableton, TotalMix, terminal —
from screenshots. If you need one of those in the same job, request them in
the same access call. Cortex Control may be on either monitor;
`computer_request_access` reports which.

## The claim ladder

Every preset job ends on one of these rungs, and the report must say which.
The canonical definition and the measurement method live in
`quad-cortex-capture-measurement`; the short form:

1. **Configured** — the named capture is loaded and the preset saved. No claim
   about sound.
2. **Structurally faithful** — every block in the audio path is either part of
   the reference chain or sits after the capture as a deliberate addition;
   nothing in front of or inside the reference chain is missing from the
   reference; makeup gain is on Volume. Still no claim about sound. This is
   where reasoning alone can get you, and where this skill's own work ends.
3. **Measured** — the same-performance comparison has been run and analyzed.
   Only here may you say "closer", "matches", or "differs by X".

Words allowed per rung: rung 1 "loaded"; rung 2 "clean", "faithful to the
capture", "nothing extra in the path"; rung 3 "closer", "within N dB", "nulls
to −X dB". The report shape in step 6 enforces this.

## Step-by-step

### 0. Establish the reference before touching the grid

The reference is what the capture was made of. Read it, don't guess.

For a plugin capture, `quad-cortex-plugin-capture` records the capture-time
plugin state in the project's `CAPTURE-TEST-STATE.md`: cab on/off, Lo/Hi Cut,
tone-match profile, In/Out gain, gate off, pitch off, mono. An "Amp and Cab"
capture has the cab and filters baked in; an "Amp" capture needs an IR after
it.

Write the reference chain as one line, for example: `guitar → [thall amp: gate
off, pitch off, cab ON, LoCut 97, HiCut 8.6k] → out`.

### 1. Get in and orient

1. Resolve and request access to Cortex Control. Screenshot at scale 0.6.
2. Confirm the preset name in the header is the one the user means. A `*`
   after the name means unsaved changes already exist — tell the user before
   proceeding, because Save will commit those too.
3. Note the grid layout: 4 rows, 8 block slots per row, row 1 fed by the input
   block on the left, rows chained via "Row N" / "Prev. row" tiles, ending at
   "Multi Out". Rows whose left tile is a `+` have no input and do not process
   audio.

### 2. Inventory every block

Click each block in path order, screenshot, and record: block type from the
panel title (for example "Pitch Wham", "Reverb Room", "Equalizer Graphic-9",
"Neural Capture Thall Monomythic Amp and Cab"); active or bypassed (power
button top-right of the panel, dimmed panel = bypassed); and the values that
matter — pitch mix and semitones, EQ curve/HPF/LPF/output, IR name and level,
capture Gain and Volume, gate reduction, reverb mix.

Icon legend as observed in v4.0.0 — use it to plan, never to conclude:

| Icon | Was actually |
| --- | --- |
| Grey burst | Utility Adaptive Gate |
| Yellow curve | Pitch (Pitch Shifter, Wham) — not a drive |
| Purple camera | Neural Capture |
| Dark purple spectrum bars | IR Loader |
| Teal wireframe cube | Reverb (Room) — not a cab |
| Blue faders | Equalizer Graphic-9 (also used for Utility blocks) |
| Orange sine | Modulation |

Read the capture block's **full name** every time. Successive captures of the
same amp look identical on the grid, and takes have been analysed against the
wrong assumption because the panel was never opened.

### 3. Bucket sort against the reference

For each block in the path:

- **In the reference** — the capture itself, or a gate the reference also had:
  keep, at unity.
- **Not in the reference but fine after the capture** — reverb, delay, a
  post-capture gate for modelled hiss, a level-only EQ: move it after the
  capture if it is not already there. Reverb and delay go last.
- **Not in the reference and in or before the reference chain** — pitch at
  unity, compensating EQ carves, an IR on an Amp+Cab capture, a boost the
  plugin did not have: bypass.

Special cases:

- Pitch blocks at 0 semitones or pedal 0% still run the pitch engine: latency
  and smeared attack. Bypass; the user re-enables when using the pedal.
- **The Pitch Shifter block has only Mix, Coarse and Fine — no wet-path
  filter.** A plugin octave with its own tone control does not port to one row:
  an EQ placed beside the pitch block to supply that filter hits the dry
  signal and everything else downstream, so a "low-pass the octave at N Hz"
  instruction becomes a low-pass on the whole chain into the capture. Filtering
  only the shifted voice needs Splitter → [pitch + EQ] and dry → Mixer. On one
  row, set Mix and Coarse, leave the filter out, and report "close, not
  exact" — never transcribe the plugin's filter frequency into a single-row
  pitch spec.
- An EQ with an HPF/LPF duplicating the plugin's baked Lo/Hi Cut is
  double-filtering. Bypass rather than reset, so the curve survives.
- If the EQ's Output was the only makeup gain, carry that number to the
  capture's Volume.
- IR Loader on an Amp+Cab capture: bypass, but keep the IR loaded so switching
  to the amp-only capture is one toggle.

### 4. Apply changes

- **Bypass**: click the block, then the power icon at the top-right of its
  panel. Verify: the panel dims and the block fill changes; the header gains a
  `*`.
- **Reorder**: `computer_left_click_drag` from the block centre to an empty
  slot centre. Slot centres are evenly spaced across the row. Drag into an
  empty slot, never onto another block. Screenshot after every drag.
- **Set a value**: `computer_double_click` on the value text, not the knob,
  then `cmd+a`, type the number, `return`. Screenshot to confirm the field
  left edit mode and shows the value.
- **Capture block**: the MY CAPTURES list is on the left when the block is
  selected, and the loaded capture name is in the panel title. Gain 0.0,
  Bass/Mid/Treble 0.0 unless the user asks otherwise, Volume = makeup, which
  starts at +4 to +6 dB for a plugin capture that came out quieter than
  downloaded ones.
- **Drag-moving an EQ block keeps its old bands.** RESET it before dialling a
  new curve; a parked Parametric-3 arrived with HP 99 Hz and a −12 dB hi
  shelf.

Do one change, one screenshot. Batched blind clicks are how the capture
skill's only real failure happened.

### 5. Save

Click the disk icon to the right of the preset name. Confirm the "Preset
saved." toast and that the `*` is gone. Screenshot. Do not save if any earlier
screenshot showed something you did not intend.

### 6. Report

Use this shape, in prose, and fill the rung honestly:

> Chain now: In 1 → … → Multi Out (mark bypassed blocks).
> Changed: what and why, one clause each.
> Left alone: what and why.
> Rung reached: 1 / 2 / 3, with the sentence "No listening or measurement was
> done" if below 3.
> To reach rung 3: the measurement recipe below.

## Canonical block order for a capture preset

`Input → gate → (pitch / whammy, only when used) → [drives that were in the
reference] → Neural Capture → IR Loader (amp-only captures) → EQ → modulation
→ delay → reverb → Multi Out`

For an Amp+Cab capture the IR Loader slot is empty or bypassed. Keep the row
layout so switching between the amp-only and amp+cab captures is: change the
capture in the block, toggle the IR Loader. Nothing else moves.

## Reaching rung 3

Run `quad-cortex-capture-measurement`: one guitar cable, QC over USB, one pass
records DI, plugin, and QC together, and its bundled `scripts/analyze.py` does
the aligned comparison — LUFS offset, banded deltas, per-band coherence, null
depth — plus the interpretation. The preset side of that job, which this skill
must set up before the take:

- Preset input block on In 1. Reverb and delay in the preset bypassed for the
  take. **Reverb and delay, and nothing else.** Do not bypass the post-capture
  EQ, the input gate, or the capture Volume for a measurement take: every take
  in the measurement skill's `references/calibration-baseline.md` was measured
  with a post-capture EQ active, so a take with it bypassed compares to no
  stored baseline. Measure the preset the user plays. An EQ curve that is
  wrong for this preset — a bell carried over from an earlier capture, say —
  is a finding for the measurement to report, not a pre-edit.
- **The lane output must reach USB.** Set the Out tile at the end of the audio
  path to **Multi Out** and confirm USB Output 3/4 is enabled in the Multiple
  Outputs list. With the tile on "Out 3" the Wet Signal channels are silent
  and the QC track in Live stays dark. Save before recording.
- One take per preset variant; each variant is one more 30 s take.
- Plugin in its capture-time reference state from `CAPTURE-TEST-STATE.md` (see
  step 0) — cab ON if the capture is Amp+Cab.

The measurement skill owns everything after that, including what the numbers
mean and how take content biases them. From a Cowork session, stage the three
WAVs to the cloud workspace and run the analysis there — the local VM has run
out of disk installing scipy.

## Troubleshooting

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| A block is not the type its icon suggests | Icon colour is not block type | Click it and read the panel title; the icon legend is for planning only |
| An IR Loader panel is dimmed but still names an IR | Bypassed with the IR kept, not empty | Nothing to fix; that is the intended amp+cab state |
| Unsure whether changes are saved | The header `*` is the only unsaved indicator | It clears on save, alongside the "Preset saved." toast |
| A block looks active but the audio says otherwise | The filled look on the grid is selection, not state | Zoom the panel's top-right glyph and compare it with a block you know is bypassed; then confirm from the audio — an EQ really in the path leaves its HPF slope or bell in the next take's spectrum |
| Clicks land far above where they were aimed | The click-offset bug | `references/screen-control-workarounds.md` |
| Every click does nothing | An un-granted app is frontmost, or the cursor is parked on the other monitor | `references/screen-control-workarounds.md` |
| Coordinates from earlier in the session miss | The window moves and resizes, and the user is working in the same app | Re-screenshot at scale 1.0 before every action |

## Reference files

- `references/screen-control-workarounds.md` — the click-offset bug and its
  two workarounds, value fields and TotalMix under the offset, focus and
  monitor problems.
- `references/cortex-control-ui-map.md` — v4.0.0 layout facts and two observed
  coordinate maps, for rough orientation only.
- `references/worked-examples.md` — finished presets and what they measured,
  as calibration for a good result.
