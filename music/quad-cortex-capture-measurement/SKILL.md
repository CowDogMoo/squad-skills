---
name: quad-cortex-capture-measurement
description: Measure how close a Quad Cortex Neural Capture (or the preset hosting it) is to the plugin it was captured from, using Jayson's one-cable QC-over-USB method - record DI, plugin, and QC in one pass, analyze with the bundled scripts/analyze.py (LUFS offset, banded spectral deltas, per-band coherence, null depth), and interpret against known-good thresholds. Canonical home of the claim ladder (configured / structurally faithful / measured) shared with quad-cortex-plugin-capture and quad-cortex-preset-editing. Trigger on "compare my capture", "how close is my capture", "null test", "measure capture accuracy", "reamp test my capture", "run the comparison", "is my capture accurate", "why does my capture sound different", or any request to verify a capture or preset against its plugin reference with numbers. Do NOT use for making a Neural Capture (quad-cortex-plugin-capture) or for editing the preset grid (quad-cortex-preset-editing).
---

# Quad Cortex capture measurement

Decide — with numbers, from one recorded performance — how close a Neural
Capture or the preset hosting it is to the plugin it was captured from.
`quad-cortex-plugin-capture` sends captures here to be verified;
`quad-cortex-preset-editing` sends presets here to reach rung 3. Everything
below was learned doing it on Jayson's rig (Quad Cortex, RME Fireface UCX II,
Ableton Live 12, Cortex Control); the gotchas are real ones that were hit.

## The claim ladder (canonical)

Every capture or preset job ends on one of these rungs, and the report must
say which. Both sibling skills defer to this definition.

1. **Configured** — the capture is saved / loaded in a preset. No claim about
   sound. Allowed words: "loaded", "saved".
2. **Structurally faithful** — the signal path contains nothing the plugin
   reference did not, and nothing from the reference is missing. Reasoning
   alone gets you here. Allowed words: "clean", "faithful to the capture",
   "nothing extra in the path".
3. **Measured** — the one-pass comparison below has been run and analyzed.
   Only here may you say "closer", "matches", "within N dB", "nulls to
   −X dB". Drive/attack/feel beyond what the null shows are judged by ear
   (Cortex Control A/B screen, and by Jayson); say so once, briefly, not as
   a caveat.

Never use rung-3 language for rung-1/2 work. This rule exists because it was
broken on 2026-08-23 ("optimized for the amp sound" after structural cleanup
only) and the user had to ask "how did you test this" to surface it.

## The method — one cable, QC over USB, one pass (since 2026-08-24)

The guitar has one jack. A single pass records DI, plugin, and QC at once,
sample-locked, from the same performance:

- **Guitar → QC Input 1.** That is the only audio cable involved.
- The QC's USB stream carries the input pre-grid ("Dry Input 1") and the
  processed output ("Wet Signal L/R") on separate channels. Ableton uses the
  QC as its **input** device; the Fireface stays the **output** device so
  monitoring does not change.
- Ableton tracks: "Thall Amp Raw Dawg" ← Ext. In 1 (QC Dry Input 1), plugin
  on that track, Monitor Auto, armed; "REC plugin post FX" ← Thall track
  Post FX; "QC amp and cab" ← Ext. In 3/4 (QC Wet Signal L/R). All three
  armed, hit record, play 20–30 s once.

Do NOT propose two passes, a third cable, a reamp, or "plug the other cable
in" — there is no other cable. Do NOT ask to check TotalMix meters; the RME
inputs are not in the path.

QC USB channel map (as macOS lists them for the "Quad Cortex" device, 8 in /
8 out): in 1–2 **Dry Input 1/2** (pre-grid guitar), in 3–4 **Wet Signal L/R**,
in 5–8 From Grid 5–8; out 1–2 XLR Output 1/2, out 3–4 TRS Output 3/4,
out 5–8 To Grid 5–8.

### Setup facts learned doing it

- **Wet Signal follows the preset's output routing.** With the last row
  ending on "Out 3" the Wet channels were silent in Ableton. Set the lane
  output tile to **Multi Out** and make sure **USB Output 3/4** is enabled in
  the Multiple Outputs list (Cortex Control: click the Out tile → OUTPUT
  list → Multiple Outputs). Save the preset. Then the QC track meters. This
  is the only silent-channel cause seen.
- Live only enumerates CoreAudio devices at launch: an Aggregate Device
  created while Live is open does not appear in its Audio Input Device list.
  Separate input (Quad Cortex) / output (Fireface) devices work fine and
  need no restart; both recorded signals come off the same device so their
  alignment is exact regardless. An Aggregate Device — created in macOS
  **Audio MIDI Setup** (Fireface + QC, Fireface as clock, 48 kHz, drift
  correction on the QC) — exists and is selectable after a Live restart if
  the RME inputs are ever needed too.
- Live Input Config: enable Mono 1&2 and Stereo 3/4 (Mono 3&4 too, harmless).
- The plugin's dry feed is the QC's input stage; DI peaked −5.9 dBFS with
  the QC In 1 at 0 dB / Instrument. Fine for the thall amp.
- The QC's Wet Signal is **polarity-inverted** relative to the plugin (cross-
  correlation peak −0.54). Harmless for spectra; the null uses a signed gain.
- Ableton records a track's input pre-FX, so a Utility on the QC track for
  level match is not in the recorded file; set it after measuring.
- **Idle time skews the level offset.** The capture's modelled noise floor
  sits ~13 dB below the plugin's, so a take with pauses reads a more
  negative QC-plugin offset than the same preset played continuously
  (2026-08-29: -8.5 idle-heavy vs -6.6 continuous). Check the DI envelope
  in the plot; quote the offset only from continuous playing. A useful
  variant: one take, change one control mid-way, and compare 1 s RMS
  ratios before/after — it proves whether the control reaches the audio.
  (Branch `docs/qc-idle-noise-diagnostic` reads the same evening as a
  Cortex Control/device desync from idle spectra. The idle comparison was
  made at the same Volume with the EQ bypassed in both takes — it cannot
  separate "not applied" from "EQ was off"; the Volume-step test on the
  21:44 take showed the control reaching the audio within a second, and
  the EQ panel glyph confirmed the block was bypassed. Reconcile before
  merging that branch.)
- **A full level match puts QC peaks near the plugin's.** The thall amp
  peaks around -0.6 dBFS; matching it means QC output peaks ~-2.5 dBFS, so
  the "Volume +14 clipped" note of 08-24 was headroom, not a knob limit.
  Split the makeup between the capture Volume and the lane output Volume.

## Pre-flight before every take (learned 2026-08-29)

Every invalid take so far had the same signature and the same root causes,
so check these with tools before Jayson plays — not by asking him.

1. **Sanity-check the newest take, if one exists**, before trusting the
   setup: stage the three newest WAVs and compare them sample-for-sample.
   DI == REC (plugin post FX) means the plugin was bypassed; DI == one channel
   of the QC file means the "DI" track is fed from the same physical input as
   the QC track (Live input device still on the Fireface, DI track on the
   RME channel carrying the QC's analog out). The 10:13 take on 08-29 had
   both at once (all three files bit-identical) and the set looked fine at
   a glance.
2. **Plugin state via `ableton-mcp` `get_device_parameters(show_all=true)`**
   on the Thall track. Compare every line against `CAPTURE-TEST-STATE.md`.
   The parameter that bites is **"Device On"** — the thall amp has been found
   bypassed (Device On: Off) twice in one session, including once after a
   set reload, so re-check it after *any* reload or preset load, not just at
   the start. `enable_device` fixes it; `set_device_parameter` with
   normalized 0.0 sets Tighten Gate to −100 dB and Pitch Power off.
3. **Live's audio input device must be "Quad Cortex".** After a capture
   session (`quad-cortex-plugin-capture` switches it to the Fireface) it
   stays on the Fireface. Read it without the UI: `~/Library/Preferences/
   Ableton/Live <version>/Log.txt` — the `CoreAudio: Device init:` lines at
   the last launch list what Live enumerated; a device hot-plugged after
   launch (the QC at 09:35 vs launch at 09:28) shows as a later `Device init`
   and is usable, but an Aggregate Device that was not present at launch is
   not. Note the Aggregate Device on this Mac reported **20 In / 20 Out** —
   that is the Fireface alone; it does not include the QC's USB channels, so
   "aggregate for the DI" is not a shortcut, it is an Audio MIDI Setup job
   plus a Live restart.
4. **Track routing** — read it from the set, not the screen: the .als is
   gzipped XML; each `<AudioTrack>` has `<AudioInputRouting><Target
   Value="AudioIn/External/M0"/>` (M = mono, S = stereo, 0-based:
   `M0` = Ext. In 1, `S1` = Ext. In 3/4, `AudioIn/Track.N/PostFxOut` =
   Post FX of track N) with `<LowerDisplayString>` mirroring it ("1",
   "3/4"). Arm is the first `<Recorder><IsArmed>` inside the track's
   `<MainSequence>`; solo is `<SoloSink>` (true = soloed). Wanted state:
   Thall `M0` armed, REC `Track.<thall>/PostFxOut` armed, QC `S1` armed,
   nothing soloed.

If the user describes the cabling as "QC → RME In 4", that is the QC's
analog out — the same processed signal the USB Wet channels carry, plus a
DAC/ADC round trip — and it leaves no dry guitar anywhere on the RME for the
plugin. Say so once, then use the USB method above; don't build a
Fireface-input variant around it.

### Driving Live when the UI won't cooperate (screen control)

- Live's **Settings window and the routing/chooser popups do not respond
  to screen-control clicks** (Settings closes on the first click; chooser
  popups never appear in screenshots; arrow keys do nothing in them). Don't
  burn more than one attempt. The macOS **menu bar works**, including
  keyboard navigation inside it.
- To change routing/arm/solo anyway: `cmd+s` (verify File → Save Live Set
  is greyed out), copy the .als into `Backup/` with a descriptive name,
  patch the XML with a short python read-modify-write on the device
  (`gzip.open` → `str.replace` scoped to the one `<AudioTrack Id="N">`
  block → `gzip.open(..., "wb")`), then reload: click **File**, `Down`×3 to
  "Open Recent Set", `Right`, `Return` on the first entry (the current set).
  Live reloads from disk without a prompt; the input meters light up
  immediately if routing is right. Then re-run step 2 — device state can
  come back different after the reload.
- `ableton-mcp` cannot read or set input routing, monitoring, or the audio
  device; it can read/set device parameters, arm, solo, mute, and volume.
  Use it for verification (steps 1–2), the .als for routing (step 4).

## Idle-noise diagnostic — what is the device actually running? (no playing)

The capture models the plugin's idle hiss, so a silent window's spectrum
carries the whole post-capture chain: capture Volume, EQ block, lane
output. When a measurement contradicts what Cortex Control displays,
record ~30 s of idle (nobody touches the guitar) and compare hiss
spectra. This pinned down the 2026-08-29 "saved but not applied" desync
without a note being played:

- Record via `ableton-mcp` alone: `set_song_time` past the last clip,
  `start_playback`, then punch in with F9 via `osascript` System Events
  key code 101 (F9 while PLAYING punches in at the playhead — no bar-1
  overwrite; needs terminal accessibility). Poll the growing WAV's size,
  then `stop_playback`. Live still reuses a previous aborted arm's
  filenames and creates fresh 0-byte arms — pair by mtime and size.
- Analyze the quietest >= 8 s window per take. Compare **QC minus plugin**
  band levels per take (both hear the same input, so guitar-hum drift
  cancels), then delta that across takes: an engaged HPF 55 shows as
  ~−14/−8 dB at 20–30/30–45 Hz in the hiss; capture Volume moves the
  QC−plugin broadband roughly dB-for-dB.
- 2026-08-29 result: fresh idle matched the flagged 21:17 take's idle
  within 1.1 dB in every band, HPF signature absent, no makeup — the
  device was still on the old working state although Cortex Control had
  shown the edits saved (toast, `*` cleared). **USB audio alive does not
  mean Cortex Control is synced**: the app can save to its local copy
  while the device runs something else. After reconnecting and re-saving,
  confirm with a fresh idle spectrum before asking for a played take.

## Recording the takes

1. Plugin in its capture-time reference state — read it from the project's
   `CAPTURE-TEST-STATE.md`, which `quad-cortex-plugin-capture` writes (cab
   ON if the capture is Amp+Cab, Lo/Hi Cut, In/Out gain, gate off, pitch
   off, mono). Don't guess it.
2. Preset input block on In 1. Reverb/delay in the preset bypassed for the
   take. Lane output routed to USB as above; preset saved.
3. Play 20–30 s: chugs, single notes, one ringing chord. DI peaks −6 to
   −12 dBFS at QC In 1 = 0 dB. Check the QC track's peak too, not just the DI.
   A preset set so hard chugs push the meter barely into red lands QC peaks near
   −2 dBFS — right for playing, almost no margin for a measurement take. A take
   that reaches 0.00 dBFS clips, and clipping adds nonlinearity the plugin does
   not have: it depresses coherence and shallows the null, biasing the result
   against the capture. Aim for QC peaks near −3 dBFS on measurement takes and
   reject any take with samples at full scale.
4. One take per preset variant (each variant = one more 30 s take).

Takes land in `<project>/Samples/Recorded/<track name> NNNN [timestamp].wav`
— mono 24-bit 48k (a stereo Post-FX take from a mono plugin is dual-mono).
Zero-byte files are aborted takes; ignore them. A 3 s take at −90 dBFS is an
arm-and-stop, not data. The plugin recording must match the reference state:
a take with the cab OFF (energy to 15 kHz only −14 dB down) cannot be
compared to anything with a cab or IR.

## Analysis — scripts/analyze.py

Run the bundled script on the three files (deps: numpy, scipy, soundfile,
pyloudnorm, matplotlib — `uv run --with ...` works):

```
python3 scripts/analyze.py DI.wav PLUGIN.wav QC.wav \
  --out-dir <project folder> --label "15:07 take, Thall Amp+Cab vs plugin"
```

What it does (keep any reimplementation identical, so results stay
comparable across sessions):

- **Same-performance check** by full-band cross-correlation of QC vs plugin:
  a clear peak (|r| ≥ 0.4) within a few ms says same take; a negative peak
  is the expected polarity inversion. Do NOT use envelope correlation for
  this — a saturated high-gain plugin with its gate off has an almost flat
  envelope (idle noise −24 dBFS RMS vs −22 playing), so envelope correlation
  reads ~0.3 even on the same take.
- Align by that lag, then: integrated LUFS + peak per signal (the difference
  is the capture block's Volume makeup, or the Utility on the QC track);
  1/6-oct-smoothed Welch spectra normalised to the 500 Hz–2 kHz mean, with
  banded QC−plugin deltas (60–120, 120–250, 250–500, 500–1k, 1–2k, 2–4k,
  4–5k, 5–8k, 8–12k); per-band coherence; null depth after signed gain match
  and after a best-fit 512-tap linear EQ.
- Plot, the style Jayson likes: top panel spectra overlay with coherence in
  grey on a second axis and per-band deltas annotated (title states what is
  compared and that it is the same performance); bottom panel 10 ms RMS
  envelopes of DI, plugin, QC with LUFS/peak in the legend. Saved as
  `null-test-YYYY-MM-DD-HHMM.png` in the project folder, where HHMM is the
  take time parsed from the Ableton filename's `[YYYY-MM-DD HHMMSS]` stamp
  (pass the original filenames, not renamed copies, or it falls back to the
  clock). Note the Ableton stamp is the moment the take was armed, which
  can precede the actual playing by a few minutes.

## What the numbers mean (high-gain captures)

- Bands within **±0.5 dB from 250 Hz up** = a matched capture.
- Coherence ~0.9 at 120–500 Hz falling to ~0.3 by 3 kHz is **normal** —
  different nonlinearities put fizz harmonics at different phases. Null
  depth of only −1.5 to −2.5 dB is therefore expected and is NOT a failed
  capture; the residual is drive character, judged by ear.
- A capture that is actually wrong shows up as **multi-dB band deltas or
  coherence < 0.6 in the 120–500 Hz body** (usually input level at capture
  time).

**The EQ-vs-coherence lesson.** An 80–100 Hz deficit (−4 to −5 dB in fine
bands) never moved more than ~1 dB no matter what a bell EQ did (+3 Q1.5,
+4 Q3), because coherence in 60–120 Hz was only ~0.5 while 120–500 Hz was
0.9. Where coherence is low, the QC's energy in that band is largely not a
linear function of the plugin's, so boosting the band scales the matching
and non-matching parts alike and the normalised delta stays put. Rule:
**only chase a band delta with EQ where coherence is > ~0.8**. Below that,
say so instead of adding more EQ, then work out which of three things it is:
(1) **a capture-time item** — input level or plugin state was wrong, recapture;
(2) **a model limit** — the QC's nonlinearity simply differs there, expected
above ~2 kHz on high-gain material and judged by ear; (3) **an unmodellable
dynamic process** — the reference has a time-varying control operating in that
band, and since a Neural Capture is a static model the deficit is permanent and
correct.

Diagnosis 3 was added 2026-08-30 and it closed this project's oldest
open item: the thall amp's 60–120 Hz deficit is its **Tighten Chug** control.
Capturing with Chug at 0 collapsed the deficit to −0.7 dB at coherence 0.58 and
gave the best-measuring capture of the project — which was then **rejected by
ear**, because Chug-0 is a different amp sound, not a cleaner one. A control
take settled the confound: the Chug-50 capture scored 0.27 coherence against the
Chug-0 reference versus the Chug-0 capture's 0.58, so Chug 0 is a *harder*
target and the gap is entirely the capture-versus-Chug mismatch. **Never
recommend zeroing a dynamic control to improve a measurement.** When the numbers
and the ears disagree about which capture is better, the ears win and the
measurement's job is to explain why. Amp-specific detail:
`thall-amp-neural-capture`.

Conversely, a high-pass below the plugin's own low cut (65 Hz there) is
always worth having: the capture reproduces the plugin's Lo Cut less steeply than the
plugin did, the QC carried +22 dB at 30–45 Hz before the HPF, and the HPF
alone improved the gain-match null by ~2 dB and lifted coherence in every
band.

Known-good calibration baseline (what a finished, matched preset measured):
`references/reference-results-2026-08-24.md`.

## What this method cannot decide

Cross-take comparison of **absolute plugin spectra** is not trustworthy better
than about 2–3 dB. Measured 2026-08-30 against a control set of four plugin
recordings all made at the same setting: normalised band levels below 500 Hz
drift up to 2.13 dB between same-reference takes; DI-relative transfer
(plugin/DI per band, intended to divide out playing) is worse at 3.38 dB,
because the amp is strongly level-dependent so playing intensity changes the
effective transfer; and the time-variance of the low/mid energy ratio spans
4.65–7.59 dB across same-reference takes. Three attempts to build a statistic
that could prove *from the audio* which plugin setting a take used all failed
on this.

**This does not affect the QC−plugin deltas this skill reports.** Those compare
two signals from the same performance, so common-mode playing variation cancels
— the entire reason for the one-pass method. It only means:

- Never compare the plugin track of one take against the plugin track of
  another and draw conclusions from the difference.
- Confirm plugin state by reading parameters back from the live plugin, never by
  inferring it from a recording.
- If audio proof of a plugin setting is ever genuinely needed, the decisive test
  is to re-render **one** DI clip through the plugin at both settings and
  compare those two renders. Same performance, one variable.

Single-take band deltas also carry roughly ±0.8 dB of take-content variance
around 250–500 Hz; treat a change smaller than that between takes of the same
configuration as noise, not as a result.

## Legacy: two cables, two passes (before 2026-08-24)

Earlier comparisons used guitar → RME In 3 for a plugin pass and guitar →
QC → RME In 4 for a QC pass, separate performances. Those charts are
different-performance long-term spectra only; they are still valid for
cab/EQ balance but say nothing about drive. Pair takes by timestamp, trim
to active region, average dual-mono to mono. Old two-cable takes have one
silent channel per take by design; do not diagnose them. Only use this
method if the QC USB path is unavailable.

## Optional: reamp (only if Jayson asks — the USB method makes it unnecessary)

Record a DI once (guitar → RME In 3, no plugin). Reamp that DI at matched
level into the plugin (DI clip → plugin track, record Post FX) and into the
QC (DI clip → spare ext out → QC In 2, preset input block → In 2,
Instrument/1 MΩ/0 dB). Calibrate the send so the QC In 2 meter peaks match
the DI file's peaks. Switch the preset input back to In 1 afterwards. Don't
propose this unprompted.

## File facts

- Ableton records a track's **input**, pre-FX. A clip on the plugin track is
  the DI; the plugin's sound only exists on a Post-FX REC track.
- The capture models the plugin's noise floor: plugin with gate at −100 dB
  idled at −30 dBFS RMS and so did the QC takes. A gate after the capture in
  the preset handles this; the input gate cannot remove modeled hiss.
