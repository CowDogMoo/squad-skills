---
name: quad-cortex-plugin-capture
description: Run a Neural Capture of a software amp-sim plugin (Neural DSP, Odeholm thall amp, or any VST/AU) into the Quad Cortex, using Jayson's rig - RME Fireface UCX II, Ableton Live, Cortex Control, TotalMix FX. Covers cabling, TotalMix routing, Ableton track setup, capture-safe plugin state, level calibration, running Neural Capture V2 from Cortex Control, and A/B verification. Trigger on "neural capture", "capture this plugin", "capture my amp sim", "quad cortex capture", "QC capture", "why is my capture quieter", or any request to turn a plugin preset into a Quad Cortex capture. Do NOT use for capturing physical amps/pedals (the manual covers that), for measuring an existing capture against its plugin reference (quad-cortex-capture-measurement), or for general Ableton/QC questions unrelated to capturing.
---

# Quad Cortex plugin capture

Turn a plugin preset into a Quad Cortex Neural Capture by looping the QC's
capture signal through the computer: QC → RME interface → Ableton (plugin) →
RME → QC. Everything below was learned by actually doing this on Jayson's rig;
the gotchas are real ones that were hit.

## The rig

- Interface: RME Fireface UCX II ("Fireface UCX II (24196183)"), TotalMix FX.
- DAW: Ableton Live 12 Suite, project `~/Music/Ableton/Recording Projects/amp-sim-neural-capture Project`.
- Cortex Control (desktop app) can run the entire Neural Capture flow — no
  need to touch the hardware screen. Menu (⋯, top right) → **New Neural Capture**.
- Two monitors: Ableton usually on one (ASUS XG32VQR or VG32VQ1B), TotalMix /
  Cortex Control on the other. When automating, expect windows on either.

## Cabling

- **QC CAPTURE OUT → RME front In 3.** CAPTURE OUT is a dedicated 1/4" jack
  directly BELOW the headphone jack (between OUT 2/R and OUT 3/L). It is NOT
  XLR Out 1. It carries the capture test signal, and in normal grid mode it
  also taps the dry In 1 signal (useful for recording DIs).
- **RME rear line out (3 or 5) → QC Input 2** (the capture return).
- **Guitar → QC Input 1** (reference for level check and A/B).
- The QC cannot loop to itself over USB; the physical loop is mandatory
  for **capturing**. For **comparing** a capture to the plugin afterwards,
  the QC's USB audio (Dry Input + Wet Signal channels) replaces all of the
  RME input cabling — see `quad-cortex-capture-measurement`.

## TotalMix

On the input receiving CAPTURE OUT (In 3):

- **Inst. OFF** (line mode), ref level **+13 dBu** (front 3/4 offer only +13/+19),
  **AutoSet OFF**, no EQ/dynamics, FX send −∞.
- Gain **+13 dB** was the calibrated value that made the capture signal land at
  DI-realistic levels (~−15 dBFS peaks) in Ableton. Recalibrate by ear of the
  meters, not by trusting this number.

On the output feeding QC In 2 (Out 3 or 5):

- In that output's mix: **only the Ableton playback channel at 0.0 dB; every
  hardware input row at −∞.** If the hardware input leaks into the return
  output, dry signal sums with the plugin and the capture is garbage. This is
  the #1 plugin-capture killer.
- Hardware output fader at 0 dB (check it — snapshots leave it at −∞),
  ref +13 dBu, Loopback OFF, FX Return −∞.

On the input receiving the QC's normal output (In 4, for A/B recording):

- Inst OFF, +13 dBu, gain 0, AutoSet OFF. The QC's main out is far hotter than
  its Capture Out.

**Snapshot warning:** loading any TotalMix snapshot/workspace (e.g. "Loud
Fucking Vocals") silently reverts ALL of the above — Inst modes, gains,
AutoSet, output faders. Re-verify every one of these settings after any
snapshot change, and re-verify before each capture session.

## Ableton

- Audio prefs: Fireface driver, **48 kHz** (QC is 48k), buffer **128** (latency
  is fine — the QC measures and compensates loop latency; dropouts are what
  ruin captures).
- Capture track: Audio From **Ext. In 3** (mono), **Monitor: In**, Audio To the
  ext out feeding QC In 2 (routing direct to Ext. Out bypasses the master, so
  nothing else can leak in). Plugin is the only device. Nothing on Main.
- Monitor sometimes flips back to Auto/Off when clicking around track headers —
  verify Monitor: In right before the level check.
- Ableton records a track's INPUT (pre-FX). To capture a plugin's output,
  record onto a second track with Audio From = that track, **Post FX**.
- The ableton-mcp server can set plugin parameters, rename tracks, delete
  devices, set volumes — use it for anything it covers; use screen control
  only for I/O routing, monitor buttons, arming, transport.

## Capture-safe plugin state

A Neural Capture models a static nonlinear system. Before capturing (thall amp
parameter indices in parens, via ableton-mcp):

- **Gate fully off** (Tighten Gate → −100 dB, param 10, normalized 0).
- **Pitch/time section powered off** (Pitch Power, param 13) — even at 0 st it
  adds latency and processing.
- **Mono** (param 30 → 0).
- Static things are fine to leave: tone-match EQ, Low Dirt at 0, Chug (mostly
  static low-end shaping — if the captured low end is flubby, recapture with
  Chug at 0), Lo/Hi Cut filters.
- **Cab: OFF for an "Amp" capture** (use IRs on the QC), **ON for "Amp + Cab"**
  (the only way to keep a non-exportable internal cab). Do both; save both.
- **Verify against the plugin UI, not just parameter readouts.** Ableton's
  normalized values displayed for VST3 params were misleading at first
  (+12 dB shown for what the UI showed as +2.4). Open the plugin window and
  confirm Input/Output gain and that the tone-match profile is actually
  loaded ("No Tone Profile" means it is not, even if the preset name shows).

## Levels — the part that decides everything

- **Input side (baked into the capture):** the interface gain on In 3 sets how
  hard the plugin is driven, exactly like guitar-into-amp gain staging. Target
  hard-played peaks around **−15 to −12 dBFS** into the plugin (what a real DI
  does). During the level check, the QC In 1 meter and the Ableton/RME In 3
  meter should read within ~1 dB of each other with these settings.
- **Return side (arbitrary, NOT part of the tone):** aim QC **In 2 peaks
  ≈ −12 dB** (Neural DSP's target) using QC In 2 Level / plugin output /
  TotalMix output fader. This only sets the capture's output loudness.
- In the Cortex Control calibration screen: In 1 = Instrument, 0 dB, 1 MΩ;
  In 2 = Instrument; type the level values in (double-click the number,
  cmd+A, type, Return).

## Running Neural Capture V2 (Cortex Control)

1. ⋯ menu → New Neural Capture → **Version 2** (cloud-processed, better; the
   QC needs internet). Click through the connection screens.
2. Calibration screen: set levels as above. CABSIM here is monitoring-only:
   ON while capturing amp-only (so it's listenable), OFF when the plugin's cab
   is in the capture.
3. **Metadata screen — go one click at a time.** It pre-fills the previous
   name + " 2" and the previous type, and a misplaced click starts the capture
   with wrong metadata. Set name, instrument (Guitar), and type (Amp vs
   Amp + Cab — the type is sent to cloud training, treat it as load-bearing),
   THEN Start Capture. Screenshot-verify before pressing start.
4. Recording ≈ 2–3 min, upload, cloud training ≈ 3–5 min. Nobody plays during
   this; the QC sends test signals.
5. A/B screen alternates every 2 s between capture and reference. Judge gain,
   chug tightness, pick attack, mids. If it's close but wrong, it's almost
   always input level. Then SAVE — and confirm the "Neural Capture Saved"
   screen actually appeared.
6. On the QC afterwards: gate block before the capture, cab/IR block after an
   amp-only capture. Name convention used: "Thall Monomythic Amp",
   "Thall Monomythic Amp and Cab".

## "My capture is quieter than a downloaded one"

Expected, and not a quality problem. A capture reproduces the whole loop's
gain as measured; whoever made the downloaded one used a hotter return. Fix
with the capture block's **Volume** (makeup gain, start +4–6 dB). Never
"fix" it with the capture's Gain knob — that changes how hard the model is
driven, i.e. the captured drive character. To bake louder output in, recapture
with plugin Output +6 dB; tone is identical.

## Record the reference for downstream work

Before leaving a capture session, write the capture-time plugin state into
the project's `CAPTURE-TEST-STATE.md`: capture name, Amp vs Amp+Cab, cab
on/off, Lo/Hi Cut, tone-match profile, In/Out gain, gate/pitch/mono state,
In 3 gain used. `quad-cortex-preset-editing` reads this as "the reference"
when it puts the capture into a preset, and `quad-cortex-capture-measurement`
reads it to put the plugin back into capture-time state for the comparison
take; without it both are guessing.

## Verifying the capture

- The immediate judgment is the Cortex Control A/B screen (step 5 above):
  gain, chug tightness, pick attack, mids. Close-but-wrong is almost always
  input level.
- For numbers — "matches within N dB", null depth, coherence — hand off to
  `quad-cortex-capture-measurement`: one guitar cable, QC over USB, one
  pass records DI, plugin, and QC together, and its bundled
  `scripts/analyze.py` produces LUFS offset, banded spectral deltas,
  per-band coherence, and null depth, with interpretation thresholds for
  high-gain captures.
- That skill is also the canonical home of the claim ladder (configured /
  structurally faithful / measured). A capture that has only been A/B'd by
  ear is not "measured"; don't use rung-3 language for it.

## Automation lessons (screen control)

- One click → screenshot → verify, for anything with state (dropdowns,
  metadata forms, TotalMix strips). Batched blind clicks caused the one real
  failure of the session (a capture started with wrong name/type).
- TotalMix knobs ignore scroll; **drag** them (≈30 px ≈ 13 dB) or find the
  value box. cmd+click does not reset faders reliably.
- The wrench icon on an Ableton device titlebar is HOT-SWAP, not "open plugin
  UI" — escape it via the X on the orange "Swapping Audio Effect" banner. The
  plugin window opens from the device's edit (plug) icon and may appear on the
  other monitor.
- Apps must be re-granted after the remote-device session drops; windows move
  between monitors; TotalMix's window can vanish (closed = hidden) — relaunch
  it via app open, and ask the user rather than fighting it for more than two
  attempts.
- Editing the preset that hosts the capture (block order, bypasses, makeup
  gain) is a separate job: `quad-cortex-preset-editing`.
