---
name: quad-cortex-neural-capture
description: Quad Cortex Neural Capture work on the user's rig (RME UCX II, Ableton, Cortex Control) - capture an amp-sim plugin into the QC, edit the preset hosting a capture, measure a capture against its plugin with analyze.py (null test, band deltas, coherence, ESR), and the Odeholm thall amp's controls, presets and capture rules. Not for porting a QC preset to plugins (quad-cortex-preset-to-plugin).
---

# Quad Cortex Neural Capture

Turn a plugin preset into a Quad Cortex Neural Capture, put that capture in a
preset, and say with numbers how close it is to the plugin. One rig: Quad
Cortex, RME Fireface UCX II, Ableton Live 12, Cortex Control, TotalMix FX.

Pick the runbook for the job, read it, and follow it. The rules below hold
for every job and are not repeated in the runbooks.

| Job | Read |
| --- | --- |
| Make a capture: cabling, TotalMix, Ableton, levels, running Neural Capture V1, saving | `references/capture.md` |
| Change a preset grid in Cortex Control: inventory, block order, bypasses, makeup, save | `references/preset-editing.md` |
| Measure a capture or preset against its plugin: one-pass take, `scripts/analyze.py`, thresholds | `references/measurement.md` |
| Anything about the Odeholm thall amp: controls, Tone Lock, factory presets, `scripts/read_preset.py`, why Chug cannot be captured | `references/thall-amp.md` |
| What happened before: capture versions and verdicts, the standing preset and its measured envelope, dated incidents, open items | `references/lab-history.md` |

Rebuilding a QC preset's tone as plugins in the DAW is the other direction;
that is `quad-cortex-preset-to-plugin`, which borrows `scripts/analyze.py`
and the measurement method from here.

## The claim ladder

Every capture, preset, or measurement job ends on one of these rungs, and the
report says which. Never a higher one.

1. **Configured.** The capture is saved, or loaded in a preset and the preset
   saved. No claim about sound. Words: "loaded", "saved".
2. **Structurally faithful.** Every block in the audio path is either part of
   the reference chain or sits after the capture as a deliberate addition;
   nothing in front of or inside the reference chain is missing from the
   reference; makeup gain is on Volume. Reasoning alone gets you here, and
   preset editing ends here. Words: "clean", "faithful to the capture",
   "nothing extra in the path".
3. **Measured.** The one-pass same-performance comparison in
   `references/measurement.md` has been run and analyzed. Only here may you
   say "closer", "matches", "within N dB", "nulls to −X dB". Drive, attack,
   and feel beyond what the null shows are judged by ear (the Cortex Control
   A/B screen, and the player); say so once, briefly, not as a caveat.

A structural cleanup is not evidence about sound. "Optimized for the amp
sound" is a rung-3 claim, and a capture that has only been A/B'd by ear is
not "measured". Below rung 3, the report says "No listening or measurement
was done" and names the measurement that would reach the next rung.

## The capture recipe

- **Capture the plugin exactly as played, with one change: the gate fully
  off** (on the thall amp, Tighten Gate −100 dB through the parameter, not
  Shape Power, which also kills Chug). A Neural Capture models a static
  system, and a gate is a level-dependent choke; left on, it bakes in an
  averaged version that sounds thin, clanky, and unamped next to the plugin
  even when it measures within 1 dB. Everything else — pitch, Chug, drive,
  EQ, tone match, mono/stereo, cab — stays where the preset plays it. The
  older "capture-safe" recipe (gate off, pitch off, mono) is history; use it
  only if the user asks for it by name.
- **Use Neural Capture Version 1.** V2 made every rejected capture of the
  thall amp; V1 made the accepted one and the downloaded captures the user
  rates highest. Do not offer V2 as "better".
- **Dynamic controls stay where the preset plays them.** Anything that ducks,
  tightens, or gates by level cannot be reproduced by a static model and
  leaves a permanent band deficit with low coherence where it operates.
  Capture it anyway and record the expected deficit. Zeroing it to improve a
  measurement produces a better-measuring capture of a *different* sound, and
  EQ that flattens the deficit is cosmetic. When numbers and ears disagree
  about which capture is better, the ears win and the measurement's job is to
  explain why.

## The user's instrument

- The plugin and the preset are the user's instrument. Reading their state is
  yours; writing it is theirs. Anything you want to change only so a number
  comes out cleaner — a gate, a pitch block, an EQ, a level — gets named with
  its cost and waits for a yes. One question covers the whole set. Restore
  each one afterwards and say so. Working unattended, leave them alone and
  report what the contamination makes unreadable.
- Starting a capture and saving a preset write to the user's hardware. Unless
  the user asked for exactly that write, confirm before **Start Capture** and
  before **Save**. A request to build, fill, or set up a preset asks for that
  preset to be saved; saving over a different existing preset still needs a
  yes. Save once, at the end, after a screenshot confirms every change.
- **Makeup gain goes on the capture block's Volume, never its Gain.** Gain
  changes how hard the model is driven.
- **Read back after every write, and trust the plugin window.** The
  `ableton-mcp` write response can echo a stale display string, and
  Ableton's normalized VST3 values can mislead (+12 dB displayed for what the
  UI showed as +2.4). Re-read all parameters after a write and treat the
  read-back as the record.

## CAPTURE-TEST-STATE.md

The capture project's `CAPTURE-TEST-STATE.md` is the reference every job
reads: capture name, Amp vs Amp+Cab, cab on/off, Lo/Hi Cut, tone-match
profile, In/Out gain, Neural Capture version, the play-state values with the
gate as the only change, the In 4 gain used, and the expected deficit from
any dynamic control. A capture session writes it before leaving; preset
editing reads it as "the reference"; measurement reads it to put the plugin
back in capture-time state. Without it every later job is guessing, so read
it, don't infer it.

## Reference files

Runbooks:

- `references/capture.md` — making a capture, end to end.
- `references/preset-editing.md` — changing a preset grid in Cortex Control.
- `references/measurement.md` — the one-pass measurement and how to read it.
- `references/thall-amp.md` — the thall amp and what a capture does with it.
- `references/lab-history.md` — dated history, the standing capture and its
  measured envelope, open items.

Capture detail:

- `references/totalmix-routing.md` — strip settings, both return-leak modes,
  the snapshot warning, OSC, the plugin-Input-Gain substitute.
- `references/rig-and-automation.md` — rig inventory and screen-control
  lessons during a capture.
- `references/neural-capture-v1-calibration-ideal.png` and
  `references/thall-amp-input-ideal.png` — the Cortex Control calibration
  screen and the thall amp input panel for the accepted capture. Match them.

Preset-editing detail:

- `references/screen-control-workarounds.md` — the click-offset bug, value
  fields, focus and monitor problems.
- `references/cortex-control-ui-map.md` — v4.0.0 layout facts and coordinate
  maps, for orientation only.
- `references/preset-worked-examples.md` — finished presets and what they
  measured.

Measurement detail:

- `references/rig-and-daw-setup.md` — QC USB channel map, the capture and
  measurement Live sets, reading the log and the `.als`, patching a set.
- `references/calibration-baseline.md` — known-good calibration takes.
- `references/eq-and-coherence.md` — what a post-capture EQ does to a band
  delta, and what coherence governs.
- `references/similarity-metrics.md` — the ESR ladder with sources and the
  metric hierarchy.
- `references/idle-noise-diagnostic.md` — proving what the device runs
  without a note played.
- `references/cross-take-validity.md` — why cross-take plugin comparison
  fails.
- `references/legacy-and-reamp-methods.md` — the two-cable and reamp methods.
  Don't propose either unprompted.

Thall amp detail:

- `references/thall-amp-plain-language-guide.md` — every control in guitar
  terms and the QC block that replaces it.
- `references/thall-amp-control-reference.md` — every control, range,
  tooltip, and capture verdict.
- `references/thall-amp-factory-presets.md` — all 53 factory presets with
  per-preset capture warnings.

Scripts:

- `scripts/analyze.py` — the aligned DI / plugin / QC comparison.
- `scripts/read_preset.py` — reads thall amp `.afx` preset files offline.
