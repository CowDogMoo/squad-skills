---
name: quad-cortex-preset-editing
description: Edit a Quad Cortex preset from the Cortex Control desktop app via screen control - load a Neural Capture into a preset, put the blocks in the right order, bypass what should not be in the signal path, set makeup gain on the right knob, save, and report honestly which claim rung the result reached (configured, structurally faithful, or measured). Use for "set up this preset", "put my capture in a preset", "use the amp and cab capture", "fix the block order", "why is this preset laggy or thin", "clean up my QC preset", or any request to change what is on a Quad Cortex preset grid. Do NOT use for making a Neural Capture (that is quad-cortex-plugin-capture), for editing presets on the hardware touchscreen, or for tone advice with no preset to edit.
---

# Quad Cortex preset editing (Cortex Control)

Change what is on a Quad Cortex preset grid so a Neural Capture is used the
way it was captured, then say exactly how much that proves. Learned on
Jayson's rig (Cortex Control v4.0.0 on macOS, two monitors); the gotchas
below were all hit for real.

## Objective and guardrails

Done means: the preset is saved with the requested capture loaded, the
block order is canonical, nothing sits in the path that is absent from the
reference, and the final report names the claim rung reached and the
measurement that would reach the next one.

- **Never claim "closer", "sounds like", "matches" or "optimized for the
  sound" without the measured same-performance comparison.** Structural
  cleanup is rung 2, not rung 3 (see the claim ladder). This rule exists
  because it was broken on 2026-08-23 and the user had to ask "how did you
  test this" to surface it.
- **Click every block and read its panel before changing anything.** Icon
  color is not block type (yellow was Pitch, the teal cube was a Reverb).
- **Bypass, don't delete**, unless the user says delete. Bypass is
  reversible and keeps the user's settings.
- **Makeup gain goes on the capture block's Volume, never its Gain.** Gain
  changes how hard the model is driven.
- **Save is a real write to the user's preset.** Do it once, at the end,
  after a screenshot confirms every change, and confirm the "Preset saved."
  toast appeared.
- Stop and ask if: the capture named by the user is not in MY CAPTURES;
  the preset has more than one row with an input assigned (parallel paths -
  the bucket sort below assumes one path); a block's panel shows something
  you cannot identify; or a drag lands somewhere unexpected and undo is
  unclear.

## Terminology

- **Preset** - the grid (rows of blocks, A-H scenes). "Profile" is not QC
  language; users may say it and mean either preset or capture.
- **Neural Capture** ("capture") - the model of an amp/pedal/plugin. Lives
  in a Neural Capture block.
- **Block** - one square on the grid. Bypassed blocks render dimmed / filled;
  active blocks have a bright outline.
- **IR Loader** - block that loads a cabinet impulse response.
- **Input block** ("In 1") - per-preset input gain and input gate. Impedance
  and Instrument/Line type are in the global I/O settings, not the preset.

## Host-environment translation

| Abstract action | Cowork / desktop bridge |
| --- | --- |
| Resolve + request app control | `computer_resolve_access` -> `computer_request_access` with app "Cortex Control" (bundle `com.NeuralDSP.CortexControl`), entries passed verbatim |
| Look | `computer_screenshot` (scale 0.6 for orientation, 1.0 before precise clicks), `computer_zoom` for panel values |
| Click / drag / type | `computer_left_click`, `computer_double_click`, `computer_left_click_drag`, `computer_type`, `computer_key` |
| Read the reference facts | connected project folder via `device_bash` / `device_stage_files` |

Granting Cortex Control hides every other app (Ableton, TotalMix, terminal...)
from screenshots. If you need Ableton or TotalMix in the same job, request
them in the same access call. Cortex Control may be on either monitor;
`computer_request_access` reports which.

## The claim ladder

Every preset job ends on one of these rungs, and the report must say which.
The canonical definition and the measurement method live in
`quad-cortex-capture-measurement`; the short form:

1. **Configured** - the named capture is loaded and the preset saved. No
   claim about sound.
2. **Structurally faithful** - every block in the audio path is either part
   of the reference chain or sits after the capture as a deliberate addition;
   nothing in front of or inside the reference chain is missing from the
   reference; makeup gain is on Volume. Still no claim about sound. This is
   where reasoning alone can get you, and where this skill's own work ends.
3. **Measured** - the same-performance comparison has been run and analyzed
   (see "Reaching rung 3" below). Only here may you say "closer", "matches",
   or "differs by X".

Words allowed per rung: rung 1 "loaded"; rung 2 "clean", "faithful to the
capture", "nothing extra in the path"; rung 3 "closer", "within N dB",
"nulls to -X dB". The report template at the end enforces this.

## Step-by-step

### 0. Establish the reference before touching the grid

The reference is what the capture was made of. Read it, don't guess:

- For a plugin capture, `quad-cortex-plugin-capture` records the capture-time
  plugin state in the project's `CAPTURE-TEST-STATE.md` (or equivalent):
  cab on/off, Lo/Hi Cut, tone-match profile, In/Out gain, gate off, pitch
  off, mono. An "Amp and Cab" capture has the cab and filters baked in; an
  "Amp" capture needs an IR after it.
- Write the reference chain as one line, e.g. `guitar -> [thall amp: gate
  off, pitch off, cab ON, LoCut 97, HiCut 8.6k] -> out`.

### 1. Get in and orient

1. Resolve and request access to Cortex Control. Screenshot at scale 0.6.
2. Confirm the preset name in the header is the one the user means. A `*`
   after the name means unsaved changes exist already - tell the user before
   proceeding, because Save will commit those too.
3. Note the grid layout: 4 rows, 8 block slots per row, row 1 fed by the
   input block on the left, rows chained via "Row N" / "Prev. row" tiles,
   ending at "Multi Out". Rows whose left tile is a `+` have no input and do
   not process audio.

### 2. Inventory every block

Click each block in path order, screenshot, and record: block type (from the
panel title, e.g. "Pitch Wham", "Reverb Room", "Equalizer Graphic-9",
"Neural Capture Thall Monomythic Amp and Cab"), active or bypassed (power
button top-right of the panel; dimmed panel = bypassed), and the values that
matter (pitch mix/semitones, EQ curve/HPF/LPF/output, IR name/level, capture
Gain/Volume, gate reduction, reverb mix).

Icon legend as observed in v4.0.0 - use it to plan, never to conclude:

| Icon | Was actually |
| --- | --- |
| Grey burst | Utility Adaptive Gate |
| Yellow curve | Pitch (Pitch Shifter, Wham) - not a drive |
| Purple camera | Neural Capture |
| Dark purple spectrum bars | IR Loader |
| Teal wireframe cube | Reverb (Room) - not a cab |
| Blue faders | Equalizer Graphic-9 (also used for Utility blocks) |
| Orange sine | Modulation |

### 3. Bucket sort against the reference

For each block in the path:

- **In the reference** (the capture itself; a gate the reference also had):
  keep, at unity.
- **Not in the reference but fine after the capture** (reverb, delay, a
  post-capture gate for modeled hiss, a level-only EQ): move after the
  capture if it is not already there. Reverb/delay go last.
- **Not in the reference and in or before the reference chain** (pitch at
  unity, compensating EQ carves, an IR on an Amp+Cab capture, a boost the
  plugin did not have): bypass.

Special cases:

- Pitch blocks at 0 semitones / pedal 0% still run the pitch engine: latency
  and smeared attack. Bypass; the user re-enables when using the pedal.
- An EQ with an HPF/LPF that duplicates the plugin's baked Lo/Hi Cut is
  double-filtering. Bypass rather than reset so the curve survives.
- If the EQ's Output was the only makeup gain, carry that number to the
  capture's Volume.
- IR Loader on an Amp+Cab capture: bypass, keep the IR loaded so switching
  to the amp-only capture is one toggle.

### 4. Apply changes

- **Bypass**: click the block, then the power icon at the top-right of its
  panel. Verify: panel dims and block fill changes. Header gains `*`.
- **Reorder**: `computer_left_click_drag` from the block center to an empty
  slot center. Slot centers are evenly spaced across the row; drag into an
  empty slot, not onto another block. Screenshot after every drag.
- **Set a value**: `computer_double_click` on the value text (not the knob),
  `cmd+a`, type the number, `return`. Screenshot to confirm the field left
  edit mode and shows the value.
- **Capture block**: MY CAPTURES list is on the left when the block is
  selected; the loaded capture name is in the panel title. Gain 0.0, Bass/Mid/
  Treble 0.0 unless the user asks otherwise, Volume = makeup (start +4 to +6
  dB for a plugin capture that came out quieter than downloaded ones).

Do one change, one screenshot. Batched blind clicks are how the capture
skill's only real failure happened.

### 5. Save

Click the disk icon right of the preset name. Confirm the "Preset saved."
toast and that the `*` is gone. Screenshot. Do not save if any earlier
screenshot showed something you did not intend.

### 6. Report

Use this shape, in prose, and fill the rung honestly:

> Chain now: In 1 -> ... -> Multi Out (mark bypassed blocks).
> Changed: what and why, one clause each.
> Left alone: what and why.
> Rung reached: 1 / 2 / 3, with the sentence "No listening or measurement
> was done" if below 3.
> To reach rung 3: the measurement recipe below.

## Canonical block order for a capture preset

`Input -> gate -> (pitch / whammy, only when used) -> [drives that were in
the reference] -> Neural Capture -> IR Loader (amp-only captures) -> EQ ->
modulation -> delay -> reverb -> Multi Out`

For an Amp+Cab capture, the IR Loader slot is empty or bypassed. Keep the
row layout so switching between the amp-only and amp+cab captures is: change
the capture in the block, toggle the IR Loader. Nothing else moves.

## Reaching rung 3

Run `quad-cortex-capture-measurement`: one guitar cable, QC over USB, one
pass records DI, plugin, and QC together, and its bundled
`scripts/analyze.py` does the aligned comparison (LUFS offset, banded
deltas, per-band coherence, null depth) plus the interpretation. The preset
side of that job — what this skill must set up before the take:

- Preset input block on In 1. Reverb/delay in the preset bypassed for the
  take.
- **The lane output must reach USB.** Set the Out tile at the end of the
  audio path to **Multi Out** and confirm USB Output 3/4 is enabled in the
  Multiple Outputs list; with the tile on "Out 3" the Wet Signal channels
  are silent and the QC track in Live stays dark. Save before recording.
- One take per preset variant (each variant = one more 30 s take).
- Plugin in its capture-time reference state, read from
  `CAPTURE-TEST-STATE.md` (see step 0) — cab ON if the capture is Amp+Cab.

## Worked example: 1D Thall Experimental, 2026-08-24 (rung 3, final)

Chain: In 1 -> Adaptive Gate -> Pitch Shifter (bypassed) -> row 3: Wham
(bypassed) -> Neural Capture "Thall Monomythic Amp and Cab" (Gain 0.0,
Volume +6.0) -> IR Loader (bypassed, IR kept) -> Parametric-3 (band 1 Peak
+3.0 dB @ 90 Hz Q 1.50; band 2 Hi pass 65 Hz; band 3 flat; Output 0) ->
Reverb Room -> Multi Out (USB Output 3/4 enabled). Lane output volume -3.0.

Measured (15:07 take, same performance): 250 Hz-12 kHz within 0.2 dB of
the plugin in every band; 60-120 Hz -3.1; 120-250 +2.4; QC +4.1 dB louder
(Utility on the Live QC track -3.8 dB); coherence 0.93 / 0.94 / 0.87 at
120-250 / 250-500 / 500-1k, 0.55 at 60-120; null -3.4 dB gain, -4.9 dB
linear EQ. Volume +14 clipped ("crackly") - +6 is the ceiling on this path.

How it got there (four takes, one variant each): lo shelf +3 @ 75 -> peak
+3 @ 90 Q1.5 -> peak +4 @ 90 Q3 + HPF 50 -> peak +3 @ 90 Q1.5 + HPF 65.
The bell never moved 80-100 Hz more than ~1 dB in any form because
coherence there is ~0.5 (see quad-cortex-capture-measurement, "The EQ-vs-
coherence lesson"); the HPF is what improved the null and coherence. Do not
add more low-end EQ to this preset; the residual 80-100 Hz gap is a
recapture item.

## Worked example: 1D Thall Experimental, 2026-08-23 (rung 2)

Reference: thall amp plugin, Monomythic preset, captured as "Thall Monomythic
Amp and Cab" (Internal Cab, Lo Cut 97 Hz, Hi Cut 8.6 kHz baked in; gate off,
pitch off, mono).

Found: In 1 -> Adaptive Gate 70% -> Pitch Shifter (0 st, 100% mix, ON) ->
row 3: Wham (pedal 0%, ON) -> Neural Capture (Amp and Cab, all 0.0) ->
Reverb Room 15% -> IR Loader (Impact Studios_IR 1, +3 dB, bypassed) ->
Graphic-9 EQ (-3/-2/-2/-2/+1.5/0/0/-2/-2, HPF 97, Output +4, ON) -> Multi Out.

Did: bypassed both pitch blocks; moved IR Loader to directly after the
capture and EQ after that so reverb is last; bypassed the EQ; set capture
Volume +4.0 (Gain stays 0.0); saved, toast confirmed.

Rung reached: 2. No listening or measurement was done. The first report said
"optimized for the amp sound"; that was rung-3 language on rung-2 work.

## Cortex Control UI facts (v4.0.0)

- Layout: preset header (back/forward arrows, name, disk icon, `⋮` menu,
  scenes A-H) above the 4-row grid; block panel below the grid, its title
  at the top with the power button top-right and RESET (EQ) left of that.
- Selecting a block opens the matching category list on the left (e.g. all
  reverb types), which is how you learn what the block really is.
- The `x` at a block's top-right corner deletes it. Avoid it unless deleting.
- Value fields accept typed numbers after double-click; knobs ignore scroll.
- Clicking the Out tile at the end of a row opens the OUTPUT list on the
  left (Multiple Outputs / Output 1/2 / Output 3/4 / USB Output 3/4 ...);
  the panel below shows Lane output control (Volume, Pan, Mute, Solo, meter).
- The window is not always centered or full size, and coordinates go stale:
  always take a fresh 1.0-scale screenshot and read positions from it. Two
  observed coordinate maps (window centered vs upper-left) are in
  `references/cortex-control-ui-map.md`, for rough orientation only.

## Gotchas

- Block colors mislead; panels do not. Two wrong identifications happened
  from a screenshot alone before any block was clicked.
- A dimmed IR Loader panel with a name still loaded is bypassed-with-IR, not
  empty.
- The header `*` is the only unsaved indicator; it clears on save.
- Access grants drop when the remote-device session drops; re-resolve and
  re-request rather than retrying clicks.
- Chrome (or any un-granted app) in front blocks every click; ask the user
  to bring Cortex Control forward rather than retrying.
- **Click-offset bug (seen 2026-08-29).** Hover (`computer_mouse_move`) landed
  where aimed, but every click / mouse-down landed a fixed ~270 px ABOVE the
  aim point on both monitors, and double-clicks were unusable (they
  deselected the block). Symptoms: clicking a row-3 block opens the preset
  browser or switches scenes; clicks in the top ~270 px do nothing. Diagnose
  with a probe click on something harmless whose y is unique (a scene
  button, a left-panel category), never on a block's `x`. Workaround that
  worked end to end: aim `y_real + 270`; have the user click GIG VIEW
  (bottom bar, out of reach) so the selected row sits at y~177 and the panel
  title/power at y~322, value text at y~432-543; edit values with a single
  click on the value text (it enters edit mode), then `cmd+a`, type,
  `return`. Reachable real y is limited to the frame height minus the offset.
  After calibration probes, re-check scene A and the scene/stomp toggle
  (top-right of the header) before saving.
- **Click-offset bug, second session (2026-08-29 evening, ~260 px).** More
  facts: `computer_cursor_position` right after a click reports `y-260`, so
  that is the one-call diagnosis. It is app-side — the two displays are
  top-aligned in System Settings, so there is nothing for the user to
  rearrange; report it via thumbs-down feedback. `left_mouse_down`/`up` at
  an exactly-moved cursor do NOT register either, so move+down+up is not a
  workaround. Windows on the non-primary display received no clicks at all
  in this session — ask for the app on the primary (menu-bar) monitor.
  Window-level drags DO work through the offset, which gives a better fix
  than Gig View for the unreachable bottom band: **shrink the Cortex
  Control window** — drag its top-left corner down ~260 px (start at corner
  y+260, end at corner y+520), then drag the title bar back to the top
  (start at bar y+260, end at 286). The window then ends at ~y 555 and the
  wizard's FILL METADATA / START / SAVE and the bottom bar become reachable;
  verify by toggling GIG VIEW at its y+260 and back.
- **TotalMix under the click bug:** buttons (Inst, AutoSet, submix mute)
  take clicks at the offset; the gain knob ignored every drag form
  (`left_click_drag`, stepped down/move/up, scroll, typed value; a
  double-click resets it to 0). For a capture that needs analog input gain
  you cannot set, put the same dB into the plugin's Input Gain via
  ableton-mcp for the capture and reset it afterwards — equivalent
  pre-nonlinearity (2026-08-29 V4: RME In 4 gain 0.0, plugin In +2.4 ->
  +15.4, back to +2.4 before the measurement take).
- **Read the capture block's full name every time.** V1/V2/V3/V4 look
  identical on the grid; on 2026-08-29 two takes were analysed against the
  wrong assumption (V3 loaded where V1 was expected) before the panel was
  read. And the 10:41 note "preset not in saved state" was wrong for the
  same reason — the blocks were exactly as saved; the capture had changed.
- **Value fields under the click bug (2026-08-29, later):** a single
  `computer_left_click` on the value text at its y+260 puts the field into
  edit mode (value highlighted); `computer_double_click` at the same aim
  did NOT — it landed as a plain click at the uncorrected y and selected an
  empty grid slot instead. Use single click, then `cmd+a`, type, `return`.
  Another un-granted app (Signal) being frontmost — even on the other
  monitor — blocks every click; `computer_open_application` on Cortex
  Control brings it back to front without asking the user.
- **Ableton take from screen control:** F9 (Arrangement Record) with the
  transport stopped records from the arrangement start, not the insert
  marker; Live also reuses the file names of a previous 0-byte aborted arm
  for the real take, so pair by content/mtime, not just the `[timestamp]`.
  The local Cowork VM ran out of disk installing scipy — stage the three
  WAVs to the cloud workspace and run analyze.py there instead.
- The user is usually working in the same app at the same time (loading
  TotalMix workspaces, moving windows between monitors, saving the preset).
  Re-screenshot before every action; a stale screenshot is how a click
  lands in the preset browser.
- Panel state glyphs: bright panel + plain power glyph = active; dimmed
  panel + strikethrough/bypass glyph = bypassed. The block's filled look is
  selection, not state.
- Drag-moving an EQ block keeps its old bands; RESET it before dialling the
  new curve (a parked Parametric-3 came with HP 99 Hz and a -12 dB hi shelf).
- The capture models the plugin's noise floor too: a plugin with its gate
  at -100 dB idled at -30 dBFS RMS, and the capture takes idled the same. A
  post-capture gate handles this; the input gate does not.
