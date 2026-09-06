---
name: quad-cortex-plugin-capture
description: Run a Neural Capture of a software amp-sim plugin (Neural DSP, Odeholm thall amp, or any VST/AU) into the Quad Cortex, using the user's rig - RME Fireface UCX II, Ableton Live, Cortex Control, TotalMix FX. Covers cabling, TotalMix routing, Ableton track setup, capture-safe plugin state, level calibration, running Neural Capture V2 from Cortex Control, and A/B verification. Trigger on "neural capture", "capture this plugin", "capture my amp sim", "quad cortex capture", "QC capture", "why is my capture quieter", or any request to turn a plugin preset into a Quad Cortex capture. Do NOT use for capturing physical amps/pedals (the manual covers that), for measuring an existing capture against its plugin reference (quad-cortex-capture-measurement), or for general Ableton/QC questions unrelated to capturing.
---

# Quad Cortex plugin capture

Turn a plugin preset into a Quad Cortex Neural Capture by looping the QC's
capture signal through the computer: QC → RME interface → Ableton (plugin) →
RME → QC.

Rig: RME Fireface UCX II, Ableton Live 12, Cortex Control, TotalMix FX.
Full inventory in `references/rig-and-automation.md`.

## Workflow

1. Cable the loop and set TotalMix so nothing but the plugin reaches QC In 2.
2. Set the plugin to its capture-safe state — or leave it as played if the
   user chooses an organic capture — and read it back.
3. Calibrate levels: input side sets the tone, return side sets loudness only.
4. Run Neural Capture V2 from Cortex Control, one screen at a time.
5. Judge it on the A/B screen, then save.
6. Write the capture-time state into `CAPTURE-TEST-STATE.md` before leaving.

## Cabling

- **QC CAPTURE OUT → RME front In 4.** CAPTURE OUT is a dedicated 1/4" jack
  directly BELOW the headphone jack, between OUT 2/R and OUT 3/L. It is NOT
  XLR Out 1. It carries the capture test signal, and in normal grid mode it
  also taps the dry In 1 signal, which is useful for recording DIs.
- **RME rear line out (3 or 5) → QC Input 2** — the capture return.
- **Guitar → QC Input 1** — reference for the level check and the A/B.

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
OFF, gain calibrated so hard playing peaks near −15 dBFS in Ableton.

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

## Capture-safe plugin state

A Neural Capture models a static nonlinear system. Before capturing (thall amp
parameter indices in parens, via `ableton-mcp`):

- **Gate fully off** — Tighten Gate → −100 dB (param 10, normalized 0).
- **Pitch/time section powered off** (param 13). Even at 0 st it adds latency
  and processing.
- **Mono** (param 30 → 0).
- Static things are fine to leave: tone-match EQ, Low Dirt at 0, Lo/Hi Cut.
- **Cab OFF for an "Amp" capture** (use IRs on the QC), **ON for "Amp + Cab"**,
  which is the only way to keep a non-exportable internal cab. Do both; save
  both.

**Organic capture is a valid mode, and it is the user's call.** The
capture-safe overrides above are the default because they make the capture
comparable to capture-safe baselines — but the user may choose to capture the
preset fully organic: gate, pitch, everything exactly as played (done
~2026-09-04/05 for "Brutal Death Thall", Tighten Gate −30, Pitch On, measured
2026-09-05). Do not "correct" that choice. Consequences to record in
`CAPTURE-TEST-STATE.md`: the **measurement reference becomes the play state**
(no overrides, no restore step for takes), and the capture-safe coherence
baselines do not apply. That capture's body coherence read 0.68–0.81 across
its clean 2026-09-05 takes (the clipped 14:46 take excluded) — below the best
capture-safe result on this rig (Monomythic, 0.87–0.94) but level with the
capture-safe capture of the same preset (V2b, 0.67–0.77), and two
capture-safe draws of identical state (V2 vs V2b) differed by more than that
on their own. So no organic-vs-capture-safe
gap has been measured; if one exists, the leading explanation is that the
model can only average the live gate/pitch behaviour, and that is
unconfirmed. State the mode explicitly in the file — a reader must never have
to guess which reference a capture answers to.

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
that the tone-match profile is actually loaded — "No Tone Profile" means it is
not, even when the preset name suggests otherwise.

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
- In the Cortex Control calibration screen: In 1 = Instrument, 0 dB, 1 MΩ;
  In 2 = Instrument. Type the values in — double-click the number, `cmd+A`,
  type, `Return`.

## Running Neural Capture V2 (Cortex Control)

1. ⋯ menu → New Neural Capture → **Version 2** (cloud-processed and better;
   the QC needs internet). Click through the connection screens.
2. Calibration screen: set levels as above. CABSIM here is monitoring-only —
   ON while capturing amp-only so it is listenable, OFF when the plugin's cab
   is in the capture.
3. **Metadata screen — go one click at a time.** It pre-fills the previous
   name plus " 2" and the previous type, and a misplaced click starts the
   capture with the wrong metadata. Set name, instrument (Guitar), and type
   (Amp vs Amp + Cab — the type is sent to cloud training, so treat it as
   load-bearing), and screenshot-verify before pressing Start Capture.
4. Recording takes 2–3 min, then upload, then cloud training 3–5 min. Nobody
   plays during this; the QC sends its own test signals.
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
Lo/Hi Cut, tone-match profile, In/Out gain, the capture mode (capture-safe or
organic) with the gate/pitch/mono state, and the In 4 gain used.

`quad-cortex-preset-editing` reads this as "the reference" when it puts the
capture into a preset, and `quad-cortex-capture-measurement` reads it to put
the plugin back into capture-time state for the comparison take. Without it,
both are guessing.

Also record the DAW hand-off. Capturing leaves Live's input device on the
Fireface and the plugin track on Ext. In 4, and every invalid measurement take
so far traces to that state being left behind. Either switch the input device
back to **Quad Cortex** and the plugin track to **Ext. In 1**, or write a line
in `CAPTURE-TEST-STATE.md` saying it was left on the Fireface so the
measurement skill's pre-flight catches it.

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
