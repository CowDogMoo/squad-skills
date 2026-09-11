---
name: quad-cortex-plugin-capture
description: Run a Neural Capture of a software amp-sim plugin (Neural DSP, Odeholm thall amp, or any VST/AU) into the Quad Cortex, using the user's rig - RME Fireface UCX II, Ableton Live, Cortex Control, TotalMix FX. Covers cabling, TotalMix routing, Ableton track setup, capture-time plugin state (as played, gate off), level calibration, running Neural Capture Version 1 from Cortex Control, and A/B verification. Trigger on "neural capture", "capture this plugin", "capture my amp sim", "quad cortex capture", "QC capture", "why is my capture quieter", or any request to turn a plugin preset into a Quad Cortex capture. Do NOT use for capturing physical amps/pedals (the manual covers that), for measuring an existing capture against its plugin reference (quad-cortex-capture-measurement), or for general Ableton/QC questions unrelated to capturing.
---

# Quad Cortex plugin capture

Turn a plugin preset into a Quad Cortex Neural Capture by looping the QC's
capture signal through the computer: QC → RME interface → Ableton (plugin) →
RME → QC.

Rig: RME Fireface UCX II, Ableton Live 12, Cortex Control, TotalMix FX.
Full inventory in `references/rig-and-automation.md`.

## Workflow

1. Cable the loop and set TotalMix so nothing but the plugin reaches QC In 2.
2. Leave the plugin exactly as played and turn only the gate fully off
   (Tighten Gate −100 dB). Read it back.
3. Calibrate levels: input side sets the tone, return side sets loudness only.
4. Run Neural Capture **Version 1** from Cortex Control, one screen at a time.
5. Judge it on the A/B screen, then save.
6. Write the capture-time state into `CAPTURE-TEST-STATE.md` before leaving.

## Cabling

- **QC CAPTURE OUT → RME front In 4.** CAPTURE OUT is a dedicated 1/4" jack
  directly BELOW the headphone jack, between OUT 2/R and OUT 3/L. It is NOT
  XLR Out 1. It carries the capture test signal, and in normal grid mode it
  also taps the dry In 1 signal, which is useful for recording DIs.
- **RME rear line out (3 or 5) → QC Input 2** — the capture return.
- **Guitar → QC Input 1** — reference for the level check and the A/B.
- History: the 2026-08-23 capture that set the quality bar used **In 3** at
  gain +13; the cable moved to In 4 on 2026-08-24 for an experiment that
  measured worse, and the 2026-08-25 edit of this file made In 4 standard. In 4
  is fine — the calibration (gain 13, Line, AutoSet off) is what must travel
  with it.

The QC cannot loop to itself over USB, so the physical loop is mandatory for
**capturing**. For **comparing** a capture to the plugin afterwards, the QC's
USB audio replaces all of the RME input cabling — see
`quad-cortex-capture-measurement`.

## TotalMix

The one rule that decides whether the capture is usable: **only the Ableton
playback channel reaches the output feeding QC In 2.** Every hardware input
row and every other software playback row in that submix goes to −∞. A leak
from either sums dry signal with the plugin, and the capture models the sum.
**And that one row must actually be up** — found at −∞ on 2026-09-01, which
would have captured silence. Check both directions; the strips are custom-named
and `references/totalmix-routing.md` says which is which.

Then, on the input receiving CAPTURE OUT (In 4): Inst OFF, +13 dBu, AutoSet
OFF, gain calibrated so hard playing peaks near −15 dBFS in Ableton. **On this
rig the calibrated value is gain 13** (2026-08-23 on In 3 and 2026-09-11 on
In 4: In 4 tracks the QC In 1 meter at IN 1 LEVEL 0 dB to 0.1 dB). The
interface gain and the plugin's Input Gain are one calibration, not two: the
accepted 2026-09-11 thall-amp capture ran **In 4 gain 13 with plugin Input
Gain +16.8 dB** (screenshot: `references/thall-amp-input-ideal.png`). An
earlier note here warned against the +17 Input Gain as "chasing meters"; the
accepted capture disproved that, so the pair above is the standard. Change
neither one alone.

**Mute In 4 in TotalMix for the capture workspace.** Mute is monitor-side only
(Ableton still records In 4) and it kills every send of the CAPTURE OUT signal
at once. Found 2026-09-11: In 4 sent to Analog 1/2 at −3.7 dB while RME Out 1/2
reaches QC In 1 — at gain 13 that loop oscillated (QC In 1 −7.8 dBFS with no
guitar). The Analog 3/4 leak check alone would not have caught it.

Loading any TotalMix snapshot or workspace silently reverts all of this.
Re-verify before every capture session.

Full strip settings, both leak modes, OSC remote control, and what to do if
the input gain knob will not take screen control:
`references/totalmix-routing.md`.

## Ableton

- Audio prefs: Fireface driver, **48 kHz** (the QC is 48k), buffer **128**.
  Latency is fine — the QC measures and compensates loop latency; dropouts are
  what ruin captures.
- Capture track: Audio From **Ext. In 4** (mono), **Monitor: In**, Audio To
  the ext out feeding QC In 2. Routing direct to Ext. Out bypasses the master,
  so nothing else can leak in. The plugin is the only device. Nothing on Main.
- Monitor sometimes flips back to Auto/Off when clicking around track headers.
  Verify **Monitor: In** right before the level check.
- Ableton records a track's **input**, pre-FX. To capture a plugin's output,
  record onto a second track with Audio From = that track, **Post FX**.
- `ableton-mcp` can set plugin parameters, rename tracks, delete devices, and
  set volumes. Use it for anything it covers; use screen control only for I/O
  routing, monitor buttons, arming, and transport.

## Capture-time plugin state

**The thall amp is captured exactly as played, with one change: Tighten Gate
→ −100 dB (param 10, normalized 0). That is literally the only change.**
Chug, pitch, drive, EQ, tone match, mono/stereo, cab — everything else stays
where the preset plays it. Do not power the pitch section off, do not flip
mono, do not zero Chug. The user confirmed this on 2026-09-11 after the
Ashen captures; it supersedes the older "capture-safe" recipe (gate off,
pitch off, mono) that V4 was made with. That recipe is history, not
procedure — do not apply it unless the user asks for it by name.

Why the gate is the exception: a Neural Capture models a static nonlinear
system, and a gate is a level-dependent choke. Leaving it on bakes in an
averaged version that reads as "thin, clanky, unamped" next to the plugin
even when the capture measures within 1 dB of it. Measured/heard 2026-09-11
on Ashen: three V2 captures with the gate at −50 ("wind" measured ±0.9 dB,
ESR 0.66, body coherence 0.68–0.71) were all rejected by ear; the first
capture with the gate at −100 — otherwise untouched, made with Neural
Capture V1 — was accepted immediately. Set the gate parameter, not Shape
Power: Shape Power off also kills Chug.

Cab: **OFF for an "Amp" capture** (use IRs on the QC), **ON for "Amp + Cab"**,
which is the only way to keep a non-exportable internal cab. Do both if the
user wants both; save both. Cab state is the preset's, not a capture-safe
override.

Record the state in `CAPTURE-TEST-STATE.md`: the play state is the
measurement reference (gate excepted), and the old capture-safe coherence
baselines do not apply (Brutal Death organic read 0.68–0.81; V2b capture-safe
0.67–0.77; two capture-safe draws of identical state differed by more than
that on their own).

**Use Neural Capture Version 1, not Version 2, for this plugin.** V2 makes
bad captures of it: every rejected Ashen capture was V2, the accepted
2026-09-11 capture is V1, and the two downloaded thall-amp captures the user
rates highest are V1. V1 is on-device, about three minutes, no cloud. Do not
offer V2 as "better" — the skill used to say that, and it was wrong for this
amp.

**Dynamic controls stay exactly where the preset plays them.** A time-varying
control — anything that ducks, tightens, or gates by level — cannot be
reproduced by a static model, and leaves a permanent band deficit with low
coherence wherever it operates. Capture it anyway. Zeroing it produces a
better-measuring capture of a *different* amp sound. Record the expected
deficit in `CAPTURE-TEST-STATE.md` so downstream work does not read it as a
defect, and do not chase it with EQ. The worked case, on the thall amp's
Tighten Chug control, is in `thall-amp-neural-capture`.

**Verify against the plugin UI, not just parameter readouts.** Ableton's
normalized values for VST3 params can mislead: +12 dB was displayed for what
the UI showed as +2.4. Open the plugin window and confirm Input/Output gain and
the tone-match state. "No Tone Profile" means none is loaded, whatever the
preset name suggests — and for the thall amp that is the accepted capture
state (see Levels), so record it rather than "fix" it.

**Read parameters back after writing them.** The `ableton-mcp` write response
can echo a stale display string: setting Tighten Chug to normalized 0.5
returned "Set Tighten Chug to 0%" while a fresh read of all 30 parameters
correctly showed 50%. Re-read after any write and treat the read-back as the
record.

## Levels

- **Input side — baked into the capture.** The interface gain on In 4 sets how
  hard the plugin is driven, exactly like guitar-into-amp gain staging. Target
  hard-played peaks around **−15 to −12 dBFS** into the plugin, which is what a
  real DI does. During the level check the QC In 1 meter and the Ableton/RME
  In 4 meter should read within ~1 dB of each other.
- **Return side — arbitrary, NOT part of the tone.** Aim for QC **In 2 peaks
  ≈ −12 dB** (Neural DSP's target), using QC In 2 Level, plugin output, or the
  TotalMix output fader. This only sets the capture's output loudness.
- Cortex Control calibration screen, the ideal for this plugin
  (screenshot: `references/neural-capture-v1-calibration-ideal.png`, taken
  right before Start Capture on the accepted 2026-09-11 capture):

  | Control | Value |
  | ------- | ----- |
  | Version | **1** |
  | IN 1 LEVEL (Instrument) | **4.0 dB**, type Instrument, 1 MΩ, phantom off |
  | IN 2 LEVEL (Device) | **1.0 dB**, type Instrument, 1 MΩ, phantom off |
  | IN 2 meter | peaks around **−4 dB** (red marker at −4.3) |
  | CABSIM | **Off** (the plugin's cab is in the capture) |

  The In 4 calibration against the QC In 1 meter is done at IN 1 LEVEL 0 dB;
  the capture then runs with the values above. Type values in — double-click
  the number, `cmd+A`, type, `Return`.
- **Thall amp input panel for the same capture**
  (`references/thall-amp-input-ideal.png`): **Input Gain +16.8 dB**, Tone
  Match **locked** with **No Tone Profile**, Amount 30%, Smooth 80%, Lo Cut
  97 Hz, hard playing sitting around −13 dBFS on the plugin's own Input
  meter. "No Tone Profile" is the accepted state for this capture, not a
  fault to fix — do not go looking for a profile to load.

## Running Neural Capture V1 (Cortex Control)

1. ⋯ menu → New Neural Capture → **Version 1**. The header must read
   "NEURAL CAPTURE VERSION 1" before anything else is clicked. V1 processes
   on the device; no internet, no upload, no cloud training. Click through
   the connection screens.
2. Calibration screen: set the table above, then compare against
   `references/neural-capture-v1-calibration-ideal.png` — same tab
   (Calibration, not Ground Lift), same knob values, same CABSIM state. The
   IN 2 meter should show signal with a peak marker near −4 dB while the
   plugin plays. CABSIM here is monitoring-only — ON while capturing amp-only
   so it is listenable, OFF when the plugin's cab is in the capture.
3. **Metadata screen — go one click at a time.** It pre-fills the previous
   name plus " 2" and the previous type, and a misplaced click starts the
   capture with the wrong metadata. Set name, instrument (Guitar), and type
   (Amp vs Amp + Cab), and screenshot-verify before pressing Start Capture.
4. Recording plus on-device training takes about three minutes. Nobody plays
   during this; the QC sends its own test signals.
5. The A/B screen alternates every 2 s between capture and reference. Judge
   gain, chug tightness, pick attack, and mids. Close but wrong is almost
   always input level. Then SAVE, and confirm the "Neural Capture Saved"
   screen actually appeared.
6. On the QC afterwards: gate block before the capture, cab/IR block after an
   amp-only capture. Naming convention in use: "Thall Monomythic Amp",
   "Thall Monomythic Amp and Cab".

## Record the reference for downstream work

Before leaving a capture session, write the capture-time plugin state into the
project's `CAPTURE-TEST-STATE.md`: capture name, Amp vs Amp+Cab, cab on/off,
Lo/Hi Cut, tone-match profile, In/Out gain, the Neural Capture version (V1),
a line confirming the gate is the only change from the play state (with the
pitch/mono/Chug values as played), and the In 4 gain used.

`quad-cortex-preset-editing` reads this as "the reference" when it puts the
capture into a preset, and `quad-cortex-capture-measurement` reads it to put
the plugin back into capture-time state for the comparison take. Without it,
both are guessing.

Also record the DAW hand-off. Capturing leaves Live's input device on the
Fireface, and every invalid measurement take so far traces to that being left
behind. Since 2026-09-08 measurement takes are recorded in their own set
(`amp-sim-measurement Project`, see the measurement skill's
`references/rig-and-daw-setup.md`), so the capture track can stay on Ext. In 4
in this set; the input device is a global Live preference and still has to go
back. Either switch it to **Quad Cortex** yourself, or write a line in
`CAPTURE-TEST-STATE.md` saying it was left on the Fireface so the measurement
skill's pre-flight catches it.

## Verifying the capture

The immediate judgment is the Cortex Control A/B screen: gain, chug tightness,
pick attack, mids.

For numbers — "matches within N dB", null depth, coherence — hand off to
`quad-cortex-capture-measurement`. One guitar cable, QC over USB, one pass
records DI, plugin, and QC together, and its bundled `scripts/analyze.py`
produces LUFS offset, banded spectral deltas, per-band coherence, and null
depth with interpretation thresholds for high-gain captures.

That skill is also the canonical home of the claim ladder (configured /
structurally faithful / measured). A capture that has only been A/B'd by ear
is not "measured"; do not use rung-3 language for it.

## Troubleshooting

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| Capture sounds like dry guitar mixed in | A hardware input or another software playback row is live in the return submix | `references/totalmix-routing.md` |
| Settings reverted between sessions | A TotalMix snapshot or workspace was loaded | Re-verify every strip setting |
| Capture is quieter than a downloaded one | Expected: a capture reproduces the loop's gain as measured, and whoever made the other one used a hotter return | Capture block **Volume**, start +4–6 dB. Never the capture's Gain — that changes how hard the model is driven. To bake it in, recapture with plugin Output +6 dB; tone is identical |
| Plugin UI and parameter readout disagree | Normalized VST3 values display misleadingly | Trust the plugin window |
| Capture started with the wrong name or type | The metadata screen pre-fills and a stray click starts it | One click, one screenshot, then Start |
| Level check meters disagree by more than ~1 dB | In 4 gain is off calibration | Recalibrate against the meters, not the stored number |
| Capture sounds thin, clanky, unamped next to the plugin, yet measures close | The plugin's gate was on during the capture, or it was a V2 run | Tighten Gate −100 dB, Version 1, recapture |

## Hand-off

- Editing the preset that hosts the capture — block order, bypasses, makeup
  gain: `quad-cortex-preset-editing`.
- Measuring the capture against its plugin reference:
  `quad-cortex-capture-measurement`.
- Odeholm thall amp specifics — the capture-as-played rule, why Chug cannot be
  modelled, the V1–V5 history, the standing capture and its measured envelope:
  `thall-amp-neural-capture`. Read it before capturing or judging that plugin.

## Reference files

- `references/totalmix-routing.md` — full TotalMix strip settings, both return
  leak modes, the snapshot warning, and the plugin-Input-Gain substitute.
- `references/rig-and-automation.md` — rig inventory and the screen-control
  lessons that apply during a capture.
- `references/neural-capture-v1-calibration-ideal.png` — the Cortex Control
  calibration screen exactly as it was for the accepted 2026-09-11 thall-amp
  capture (V1, In 1 4.0 dB, In 2 1.0 dB, CABSIM off). Match it.
- `references/thall-amp-input-ideal.png` — the thall amp input panel for the
  same capture (Input Gain +16.8 dB, Tone Match locked, No Tone Profile,
  Amount 30 / Smooth 80, Lo Cut 97 Hz). Match it too.
