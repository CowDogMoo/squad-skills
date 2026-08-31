---
name: quad-cortex-capture-measurement
description: Measure how close a Quad Cortex Neural Capture (or the preset hosting it) is to the plugin it was captured from, using a one-cable QC-over-USB method - record DI, plugin, and QC in one pass, analyze with the bundled scripts/analyze.py (LUFS offset, banded spectral deltas, per-band coherence, null depth), and interpret against known-good thresholds. Canonical home of the claim ladder (configured / structurally faithful / measured) shared with quad-cortex-plugin-capture and quad-cortex-preset-editing. Trigger on "compare my capture", "how close is my capture", "null test", "measure capture accuracy", "reamp test my capture", "run the comparison", "is my capture accurate", "why does my capture sound different", or any request to verify a capture or preset against its plugin reference with numbers. Do NOT use for making a Neural Capture (quad-cortex-plugin-capture) or for editing the preset grid (quad-cortex-preset-editing).
---

# Quad Cortex capture measurement

Decide — with numbers, from one recorded performance — how close a Neural
Capture or the preset hosting it is to the plugin it was captured from.
`quad-cortex-plugin-capture` sends captures here to be verified;
`quad-cortex-preset-editing` sends presets here to reach rung 3.

Rig: Quad Cortex, RME Fireface UCX II, Ableton Live 12, Cortex Control.

## Workflow

1. Run the pre-flight checks with tools, before the user plays.
2. Record one 20–30 s pass that captures DI, plugin, and QC together.
3. Run `scripts/analyze.py` on the three files.
4. Read the numbers against the thresholds below.
5. Report the claim-ladder rung reached, and never a higher one.

## The claim ladder (canonical)

Every capture or preset job ends on one of these rungs, and the report must
say which. Both sibling skills defer to this definition.

1. **Configured** — the capture is saved or loaded in a preset. No claim
   about sound. Allowed words: "loaded", "saved".
2. **Structurally faithful** — the signal path contains nothing the plugin
   reference did not, and nothing from the reference is missing. Reasoning
   alone gets you here. Allowed words: "clean", "faithful to the capture",
   "nothing extra in the path".
3. **Measured** — the one-pass comparison below has been run and analyzed.
   Only here may you say "closer", "matches", "within N dB", "nulls to
   −X dB". Drive, attack, and feel beyond what the null shows are judged by
   ear (Cortex Control A/B screen, and by the player); say so once, briefly, not
   as a caveat.

**Never use rung-3 language for rung-1/2 work.** A structural cleanup is not
evidence about sound, and describing one as "optimized for the amp sound"
is a rung-3 claim with no measurement behind it.

## Recording the take — one cable, QC over USB, one pass

The guitar has one jack. A single pass records DI, plugin, and QC at once,
sample-locked, from the same performance:

- **Guitar → QC Input 1.** That is the only audio cable involved.
- The QC's USB stream carries the input pre-grid ("Dry Input 1") and the
  processed output ("Wet Signal L/R") on separate channels. Ableton uses the
  QC as its **input** device; the Fireface stays the **output** device so
  monitoring does not change.
- Ableton tracks, all three armed: "Thall Amp Raw Dawg" ← Ext. In 1 (QC Dry
  Input 1), plugin on that track, Monitor Auto; "REC plugin post FX" ←
  Thall track Post FX; "QC amp and cab" ← Ext. In 3/4 (QC Wet Signal L/R).

Do NOT propose two passes, a third cable, a reamp, or "plug the other cable
in" — there is no other cable. Do NOT ask to check TotalMix meters; the RME
inputs are not in the path. If the user describes the cabling as "QC → RME
In 4", that is the QC's analog out — the same processed signal the USB Wet
channels carry, plus a DAC/ADC round trip — and it leaves no dry guitar
anywhere on the RME for the plugin. Say so once, then use the USB method;
don't build a Fireface-input variant around it.

Then:

1. Put the plugin in its capture-time reference state. Read it from the
   project's `CAPTURE-TEST-STATE.md`, which `quad-cortex-plugin-capture`
   writes (cab ON if the capture is Amp+Cab, Lo/Hi Cut, In/Out gain, gate
   off, pitch off, mono). Don't guess it. **Say which controls you are about
   to move and get a yes before moving them** — see "Whose call it is" below.
2. Preset input block on In 1, reverb and delay bypassed for the take, lane
   output routed to USB, preset saved.
3. Play 20–30 s continuously: chugs, single notes, one ringing chord.
4. One take per preset variant.

Levels: DI peaks −6 to −12 dBFS with QC In 1 at 0 dB / Instrument (the
thall amp's DI measured −5.9 dBFS there). Check the
QC track's peak too, not just the DI. Aim for QC peaks near **−3 dBFS** on a
measurement take and reject any take with samples at full scale — clipping
adds nonlinearity the plugin does not have, which depresses coherence and
shallows the null, biasing the result against the capture. A preset set so
hard chugs push the meter barely into red lands QC peaks near −2 dBFS: right
for playing, almost no margin for measuring. When a full level match needs
more makeup than one control gives, split it between the capture Volume and
the lane output Volume; running out is headroom, not a knob limit.

Ableton records a track's input **pre-FX**, so a clip on the plugin track is
the DI, the plugin's sound only exists on the Post-FX REC track, and a
Utility on the QC track is not in the recorded file — set that after
measuring.

### Whose call it is

The plugin and the preset are the user's instrument, and the two controls
this method most often has to move — **Tighten Gate off, Pitch Power off** —
are the two the user is most likely to be playing through right now. Reading
state is yours. Writing it is theirs.

- Name the controls, say what each costs the measurement if left as-is, and
  wait for a yes. One question covers the whole set.
- Restore every one of them the moment the take is recorded, and say so.
- Working unattended, leave them alone, take the pass as configured, and
  report which bands the contamination makes unreadable.

A contaminated take you can explain is a smaller failure than a silent edit
to somebody's rig. Both are avoidable by asking.

### Do NOT bypass the post-capture EQ for a measurement take

Step 2 lists reverb and delay. It stops there on purpose.

Every take in `references/calibration-baseline.md` was measured with a
post-capture EQ **active** — the four 2026-08-24 takes are an EQ sweep, and
the standing-preset envelope in `thall-amp-neural-capture` was measured
through its Parametric-3. Bypass the EQ and the numbers compare to nothing;
there is no stored raw-capture baseline to land them against.

The same holds for the preset's input gate, its capture Volume, and its lane
output. Measure the preset the user plays. An EQ curve that is wrong for the
preset — a bell left over from an earlier capture, say — is a **finding for
the measurement to report**, not something to change before measuring it.

## Pre-flight checks

Every invalid take so far had the same signature and the same root causes.
Check these with tools before the user plays, not by asking them.

1. **Sanity-check the newest take, if one exists.** Stage the three newest
   WAVs and compare them sample-for-sample. DI == REC (plugin post FX) means
   the plugin was bypassed. DI == one channel of the QC file means the "DI"
   track is fed from the same physical input as the QC track. All three
   bit-identical means both at once — that has happened, and the set looked
   fine at a glance.
2. **Plugin state** via `ableton-mcp` `get_device_parameters(show_all=true)`
   on the plugin's track, compared line by line against
   `CAPTURE-TEST-STATE.md`. Report the diff to the user and get a yes before
   writing any of it back (see "Whose call it is"); a state file that lists a
   restore step — "Tighten Gate → −30 dB, Pitch Power → On after the capture"
   — means the user is deliberately running the play state, not drifting. The
   parameter that bites is **"Device On"** — the thall amp has been found
   bypassed twice in one session, including after a set reload, so re-check it
   after *any* reload or preset load.
   `enable_device` fixes it; `set_device_parameter` with normalized 0.0 sets
   Tighten Gate to −100 dB and Pitch Power off.
3. **Live's audio input device must be "Quad Cortex".** After a capture
   session it stays on the Fireface, because `quad-cortex-plugin-capture`
   switches it there. Read it from Live's log rather than the UI.
4. **Track routing, arm, and solo** — read from the `.als`, not the screen.

For steps 3 and 4, and for changing anything Live's UI refuses to change,
see `references/rig-and-daw-setup.md`.

## Analysis — scripts/analyze.py

Run the bundled script on the three files (deps: numpy, scipy, soundfile,
pyloudnorm, matplotlib — `uv run --with ...` works):

```bash
python3 scripts/analyze.py DI.wav PLUGIN.wav QC.wav \
  --out-dir <project folder> --label "15:07 take, Thall Amp+Cab vs plugin"
```

Pass the original Ableton filenames, not renamed copies: the plot name
`null-test-YYYY-MM-DD-HHMM.png` takes HHMM from the `[YYYY-MM-DD HHMMSS]`
stamp and otherwise falls back to the clock.

Keep any reimplementation identical to this, so results stay comparable
across sessions:

- **Same-performance check** by full-band cross-correlation of QC vs plugin.
  A clear peak (|r| ≥ 0.4) within a few ms says same take; a negative peak
  is the QC's expected polarity inversion relative to the plugin (measured
  at −0.54 on this rig), which is harmless for spectra because the null uses
  a signed gain. Do NOT use
  envelope correlation here — a saturated high-gain plugin with its gate off
  has an almost flat envelope (idle −24 dBFS RMS vs −22 playing), so
  envelope correlation reads ~0.3 even on the same take.
- Align by that lag, then compute: integrated LUFS and peak per signal (the
  difference is the capture block's Volume makeup); 1/6-oct-smoothed Welch
  spectra normalised to the 500 Hz–2 kHz mean, with banded QC−plugin deltas
  (60–120, 120–250, 250–500, 500–1k, 1–2k, 2–4k, 4–5k, 5–8k, 8–12k);
  per-band coherence; null depth after a signed gain match and after a
  best-fit 512-tap linear EQ.
- Plot: top panel spectra overlay, coherence in grey on a second axis,
  per-band deltas annotated, title stating what is compared and that it is
  the same performance; bottom panel 10 ms RMS envelopes of DI, plugin, and
  QC with LUFS and peak in the legend.

## Reading the numbers (high-gain captures)

- Bands within **±0.5 dB from 250 Hz up** = a matched capture.
- Coherence ~0.9 at 120–500 Hz falling to ~0.3 by 3 kHz is **normal** —
  different nonlinearities put fizz harmonics at different phases. A null
  depth of only −1.5 to −2.5 dB is therefore expected and is NOT a failed
  capture; the residual is drive character, judged by ear.
- A capture that is actually wrong shows up as **multi-dB band deltas or
  coherence < 0.6 in the 120–500 Hz body**, usually input level at capture
  time.
- Quote the level offset only from continuously played material — idle time
  biases it. See `references/idle-noise-diagnostic.md`.
- Known-good calibration baseline, from a finished matched preset:
  `references/calibration-baseline.md`.

### The EQ-vs-coherence lesson

An 80–100 Hz deficit of −4 to −5 dB never moved more than ~1 dB no matter
what a bell EQ did (+3 Q1.5, +4 Q3), because coherence in 60–120 Hz was only
~0.5 while 120–500 Hz was 0.9. Where coherence is low, the QC's energy in
that band is largely not a linear function of the plugin's, so boosting the
band scales the matching and non-matching parts alike and the normalised
delta stays put.

Rule: **only chase a band delta with EQ where coherence is > ~0.8.** Below
that, say so instead of adding more EQ, then work out which of three things
it is:

1. **A capture-time item** — input level or plugin state was wrong.
   Recapture.
2. **A model limit** — the QC's nonlinearity simply differs there. Expected
   above ~2 kHz on high-gain material, and judged by ear.
3. **An unmodellable dynamic process** — the reference has a time-varying
   control operating in that band. A Neural Capture is a static model, so
   the deficit is permanent and correct.

**Never recommend zeroing a dynamic control to improve a measurement.** It
changes the sound being captured rather than cleaning it up. When the
numbers and the ears disagree about which capture is better, the ears win
and the measurement's job is to explain why. For the worked case that
established diagnosis 3 — the thall amp's Tighten Chug control — see
`thall-amp-neural-capture`.

Conversely, a high-pass below the plugin's own low cut is always worth
having: the capture reproduces the plugin's Lo Cut less steeply than the
plugin did, the QC carried +22 dB at 30–45 Hz before the HPF, and the HPF
alone improved the gain-match null by ~2 dB and lifted coherence in every
band.

## What this method cannot decide

Absolute plugin spectra are not comparable across takes better than about
2–3 dB, so:

- Never compare the plugin track of one take against the plugin track of
  another and draw conclusions from the difference.
- Confirm plugin state by reading parameters back from the live plugin,
  never by inferring it from a recording.
- Treat a between-take change smaller than ±0.8 dB around 250–500 Hz as
  noise, not a result.
- If audio proof of a plugin setting is genuinely needed, re-render **one**
  DI clip through the plugin at both settings and compare those two renders.
  Same performance, one variable.

This does not affect the QC−plugin deltas this skill reports: those compare
two signals from the same performance, so common-mode playing variation
cancels. Supporting measurements: `references/cross-take-validity.md`.

## Troubleshooting

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| QC track silent in Ableton | Wet Signal follows the preset's output routing | Lane output tile → Multi Out, enable USB Output 3/4, save the preset (`references/rig-and-daw-setup.md`) |
| All three takes identical | Plugin bypassed *and* DI track fed from the QC's analog out | Pre-flight steps 1–3 |
| DI == plugin take | Plugin bypassed ("Device On": Off) | `enable_device`, then re-read all parameters |
| Live won't show a new device | Live enumerates CoreAudio at launch | Hot-plugged devices are fine; an Aggregate Device needs a restart |
| Routing popups ignore clicks | Live's Settings and chooser popups don't accept screen control | Patch the `.als` and reload (`references/rig-and-daw-setup.md`) |
| Measurement contradicts Cortex Control | The app can save locally while the device runs the old state | Idle-spectrum comparison (`references/idle-noise-diagnostic.md`) |
| Level offset looks too negative | Idle time in the take | Re-read from continuous playing only |
| Shallow null, low coherence everywhere | Take clipped | Reject the take, re-record at QC peaks ~−3 dBFS |

## Reference files

- `references/rig-and-daw-setup.md` — QC USB channel map, Ableton device and
  routing facts, reading and patching the `.als`, screen-control limits,
  recorded-file facts.
- `references/idle-noise-diagnostic.md` — proving what the device is running
  without a note being played.
- `references/cross-take-validity.md` — why cross-take plugin comparison
  fails, with the numbers.
- `references/legacy-and-reamp-methods.md` — the two-cable method and the
  reamp method. Don't propose either unprompted.
- `references/calibration-baseline.md` — known-good calibration baseline
  (2026-08-24 run).
