# Capturing a plugin into the Quad Cortex

Turn a plugin preset into a Quad Cortex Neural Capture by looping the QC's
capture signal through the computer: QC → RME interface → Ableton (plugin) →
RME → QC.

The capture recipe (gate off, everything else as played, Version 1), the
claim ladder, and `CAPTURE-TEST-STATE.md` are in `SKILL.md`. Rig inventory:
`rig-and-automation.md`. Not for physical amps or pedals; the QC manual
covers those.

## Workflow

1. Cable the loop and set TotalMix so nothing but the plugin reaches QC In 2.
2. Leave the plugin exactly as played and turn only the gate fully off. Read
   it back.
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

The input that receives CAPTURE OUT does not matter (In 3 and In 4 have both
made good captures); the calibration that travels with it does: gain 13,
Line, AutoSet off.

The QC cannot loop to itself over USB, so the physical loop is mandatory for
**capturing**. For **comparing** a capture to the plugin afterwards, the QC's
USB audio replaces all of the RME input cabling — see `measurement.md`.

## TotalMix

The one rule that decides whether the capture is usable: **only the Ableton
playback channel reaches the output feeding QC In 2.** Every hardware input
row and every other software playback row in that submix goes to −∞. A leak
from either sums dry signal with the plugin, and the capture models the sum.
**And that one row must actually be up** — it has been found at −∞, which
would have captured silence. Check both directions; the strips are
custom-named and `totalmix-routing.md` says which is which.

Then, on the input receiving CAPTURE OUT (In 4): Inst OFF, +13 dBu, AutoSet
OFF, gain calibrated so hard playing peaks near −15 dBFS in Ableton. **On this
rig the calibrated value is gain 13**: In 4 then tracks the QC In 1 meter at
IN 1 LEVEL 0 dB to within 0.1 dB. The interface gain and the plugin's Input
Gain are one calibration, not two: the accepted thall-amp capture ran **In 4
gain 13 with plugin Input Gain +16.8 dB** (screenshot:
`thall-amp-input-ideal.png`). Change neither one alone.

**Mute In 4 in TotalMix for the capture workspace.** Mute is monitor-side only
(Ableton still records In 4) and it kills every send of the CAPTURE OUT signal
at once. An In 4 send to Analog 1/2 while RME Out 1/2 reaches QC In 1 makes a
loop that oscillates at gain 13 (QC In 1 at −7.8 dBFS with no guitar); the
Analog 3/4 leak check alone does not catch it.

Loading any TotalMix snapshot or workspace silently reverts all of this.
Re-verify before every capture session.

Full strip settings, both leak modes, OSC remote control, and what to do if
the input gain knob will not take screen control: `totalmix-routing.md`.

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

Apply the capture recipe in `SKILL.md`. On the thall amp the one change is
**Tighten Gate → −100 dB (param 10, normalized 0)**; do not power the pitch
section off, do not flip mono, do not zero Chug. `thall-amp.md` sorts every
control of that plugin and explains why Chug cannot be modelled.

Cab: **OFF for an "Amp" capture** (use IRs on the QC), **ON for "Amp + Cab"**,
which is the only way to keep a non-exportable internal cab. Do both if the
user wants both; save both. Cab state is the preset's, not a capture
override.

Open the plugin window and confirm Input/Output gain and the tone-match
state. "No Tone Profile" means none is loaded, whatever the preset name
suggests — and for the thall amp that is the accepted capture state (see
Levels), so record it rather than "fix" it.

## Levels

- **Input side — baked into the capture.** The interface gain on In 4 sets how
  hard the plugin is driven, exactly like guitar-into-amp gain staging. Target
  hard-played peaks around **−15 to −12 dBFS** into the plugin, which is what a
  real DI does. During the level check the QC In 1 meter and the Ableton/RME
  In 4 meter should read within ~1 dB of each other.
- **Return side — arbitrary, NOT part of the tone.** Aim for QC **In 2 peaks
  ≈ −12 dB** (Neural DSP's target), using QC In 2 Level, plugin output, or the
  TotalMix output fader. This only sets the capture's output loudness.
- Cortex Control calibration screen, the ideal for this plugin (screenshot:
  `neural-capture-v1-calibration-ideal.png`, taken right before Start
  Capture on the accepted capture):

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
  (`thall-amp-input-ideal.png`): **Input Gain +16.8 dB**, Tone Match
  **locked** with **No Tone Profile**, Amount 30%, Smooth 80%, Lo Cut 97 Hz,
  hard playing sitting around −13 dBFS on the plugin's own Input meter. "No
  Tone Profile" is the accepted state for this capture, not a fault to fix —
  do not go looking for a profile to load.

## Running Neural Capture V1 (Cortex Control)

1. ⋯ menu → New Neural Capture → **Version 1**. The header must read
   "NEURAL CAPTURE VERSION 1" before anything else is clicked. V1 processes
   on the device; no internet, no upload, no cloud training. Click through
   the connection screens.
2. Calibration screen: set the table above, then compare against
   `neural-capture-v1-calibration-ideal.png` — same tab (Calibration, not
   Ground Lift), same knob values, same CABSIM state. The IN 2 meter should
   show signal with a peak marker near −4 dB while the plugin plays. CABSIM
   here is monitoring-only — ON while capturing amp-only so it is listenable,
   OFF when the plugin's cab is in the capture.
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

Before leaving, write `CAPTURE-TEST-STATE.md` with the fields listed in
`SKILL.md`.

Also record the DAW hand-off. Capturing leaves Live's input device on the
Fireface, and every invalid measurement take so far traces to that being left
behind. Measurement takes are recorded in their own set
(`amp-sim-measurement Project`, see `rig-and-daw-setup.md`), so the capture
track can stay on Ext. In 4 in this set; the input device is a global Live
preference and still has to go back. Either switch it to **Quad Cortex**
yourself, or write a line in `CAPTURE-TEST-STATE.md` saying it was left on the
Fireface so the measurement pre-flight catches it.

## Verifying the capture

The immediate judgment is the Cortex Control A/B screen: gain, chug tightness,
pick attack, mids. That is rung 1 plus an ear check, not rung 3.

For numbers — "matches within N dB", null depth, coherence — run
`measurement.md`: one guitar cable, QC over USB, one pass records DI, plugin,
and QC together, and `scripts/analyze.py` does the comparison.

## Troubleshooting

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| Capture sounds like dry guitar mixed in | A hardware input or another software playback row is live in the return submix | `totalmix-routing.md` |
| Settings reverted between sessions | A TotalMix snapshot or workspace was loaded | Re-verify every strip setting |
| Capture is quieter than a downloaded one | Expected: a capture reproduces the loop's gain as measured, and whoever made the other one used a hotter return | Capture block **Volume**, start +4–6 dB, never its Gain (`SKILL.md`). To bake it in, recapture with plugin Output +6 dB; tone is identical |
| Plugin UI and parameter readout disagree | Normalized VST3 values display misleadingly | Trust the plugin window |
| Capture started with the wrong name or type | The metadata screen pre-fills and a stray click starts it | One click, one screenshot, then Start |
| Level check meters disagree by more than ~1 dB | In 4 gain is off calibration | Recalibrate against the meters, not the stored number |
| Capture sounds thin, clanky, unamped next to the plugin, yet measures close | The plugin's gate was on during the capture, or it was a V2 run | Tighten Gate −100 dB, Version 1, recapture |
