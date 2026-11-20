# Thall amp — the plugin, and what a Neural Capture does with it

Odeholm Audio **thall amp v1.0.4**. Everything about capturing it was learned
on the user's rig across captures V1–V5 and the later Ashen captures,
measured each time with `references/measurement.md`; the versions and
verdicts are in `references/lab-history.md`. Everything about its controls
and presets is read from the plugin itself — its published parameter info,
its own tooltip text, and the preset files on disk.

- What every control means in ordinary guitar terms, and which QC block
  replaces it: `references/thall-amp-plain-language-guide.md`.
- Every control, its range, its tooltip, and its capture verdict:
  `references/thall-amp-control-reference.md`.
- All 53 factory presets with values and per-preset capture warnings:
  `references/thall-amp-factory-presets.md`.
- Read any preset file without touching the live plugin:
  `scripts/read_preset.py`.

## The rule that matters most

**Capture the preset in the state you actually play it. Do not neuter
controls to make the capture measure better.**

This was learned the expensive way. The 60–120 Hz deficit that dogged V1, V2
and V4 traces to the plugin's **Tighten Chug** control being at 50%. Setting
Chug to 0 and recapturing (V5) fixed the measurement spectacularly — 60–120
went from −4.0 dB at coherence 0.43 to −0.7 dB at 0.58, and with one
corrective bell every band from 60 Hz to 12 kHz sat within 1.1 dB. It was
the best-measuring capture the project ever produced.

The user's verdict on hearing it: *"v5 without chug 100% DOES NOT sound
right at all."* V5 was rejected.

Chug-0 is not a cleaner version of the same amp. It is a different amp
sound. The measurement is a servant of the sound, never the reverse. When a
measurement and the ears disagree about which capture is better, the ears win
and the measurement's job is to explain why.

## The plugin in one screen

    in -> Input Gain -> Tone Matching -> Shape (Gate, Chug)
       -> Pitch (Whammy, Low Dirt, Thicken) -> Amp -> Cab
       -> Lo-Cut / Hi-Cut / Lo-Fi -> Output Gain -> out

Five section power switches — Tone Matching, Shape, Pitch, Amplifier, Cab —
each bypass their whole section. Two of them bite:

- **Shape Power off kills the gate *and* Chug.** To silence only the gate,
  set Tighten Gate to −100 dB and leave Shape Power on. That is why the
  capture-safe state names the gate parameter and not the switch.
- **Pitch Power off kills Whammy, Thicken, Cleanse, Latency** and possibly
  Low Dirt. Older captures (V4) turned it off to drop the pitch shifter's
  latency; it now stays exactly as the preset plays it. The gate is the only
  control a capture changes.

The 30 automatable parameters, ranges, and defaults are in
`references/thall-amp-control-reference.md`. Live's **Device On** is the plugin's Host
Bypass; the plugin's own **Power** (parameter 2) is a second, separate
bypass.

## What a Neural Capture can and cannot model

A capture learns a **static** nonlinear system. Sort every control by that
one question before capturing anything.

| Captures faithfully | Cannot be captured |
| ------------------- | ------------------ |
| Amp Drive, Lo, Mid, Hi, Presence | **Tighten Chug** — emphasis that follows pick attack |
| The cab (internal or a loaded IR) | **Pitch Thicken** — generates an octave below |
| Tone Matching (a static input EQ) | **Pitch Whammy** — pitch shifting |
| Low Dirt (static pre-distortion) | **Tighten Gate** — level-dependent; **always −100 dB before capturing**, the one change made to any preset (`SKILL.md`) |
| Input Gain (baked in — it sets the drive) | Anything with modulation assigned |
| Lo-Cut, Hi-Cut, Lo-Fi (output filters) | |

Lo-Cut is first order and Hi-Cut second order, and a capture reproduces both
less steeply than the plugin does. Output Gain is loudness only and is not
part of the tone.

Everything in the right column leaves a permanent band deficit with low
coherence wherever it operates. Record it; do not chase it.

## Why Chug cannot be captured

The plugin's own tooltip: *"Adjusts the strength of the chug processor.
Higher values put more emphasis on pick attack."* Emphasis that follows the
attack is a function of time, and a static model has no time. Chug lives in
the Shape section beside the gate, with its own Frequency control (1.6 kHz
on the standing preset). The capture learns some average of what Chug does
and the moment-to-moment behaviour is lost.

That is exactly what the coherence column reports, and it is measurable:

| Plugin Chug | 60–120 Hz delta | 60–120 Hz coherence |
| ----------- | --------------- | ------------------- |
| 50% (as played) | −3.7 to −5.0 dB | 0.27 – 0.52 |
| 0%              | −0.4 to −1.0 dB | 0.58 – 0.64 |

The control take that proved it: V4 measured against the plugin at **Chug 0**
scored 0.27 coherence at 60–120, versus V5's 0.58 against the identical
reference. Chug 0 is a *harder* target for a Chug-50 capture, not an easier
one, so the low-end gap belongs entirely to the capture-versus-Chug mismatch
and not to the choice of reference.

**A roughly −4 dB deficit at 60–120 Hz with coherence around 0.4–0.5 is the
EXPECTED result for any Chug-50 capture of this amp. It is the price of
Chug, and Chug is what makes it sound right. It is not a defect.**

EQ can move the reported number, and moving it would be cosmetic. The shapes
tried — +3 Q1.5, +4 Q3 — average only about +2.4 dB across 60–120 Hz, so
they landed within about a dB of each other; and at coherence 0.4–0.5
flattening the band does not improve the null. A static boost would be
averaging out a dynamic control. It is not a capture-input-level item — V2
tested a hotter capture input and made it worse. It is not a
capture-quality item — V5 proved the model is fine once Chug is out of the
way. Stop chasing it.

A high-pass on the QC side is still always worth having. The reason is not
the plugin's Lo-Cut — that is **Off** on the standing preset — but that the
capture carried +22 dB at 30–45 Hz that the plugin did not. The general rule
is in `references/measurement.md`.

## The Tone Lock trap

**Tone Lock is on for this rig, so a preset does not load its own tone-match
settings or input gain.** The plugin's tooltip: *"When locked, prevents tone
match and input gain parameters from changing when switching presets."*

Two pieces of evidence, both re-checkable: the user's own saved preset
records Tone Lock enabled, and the live plugin has been read at Input Gain
+2.4 dB while the preset it was on (Simone Pietroforte – Brutal Death
Thall, identified by matching its stored values against a live parameter
read) stores +8.6 dB.

Consequences worth remembering:

- A preset file's `tone_power`, `tone_amount`, `tone_smooth` and
  `input_gain` are **not** what is running. Everything else in the file is.
- 12 factory presets ship a tone-match profile learned from their author's
  guitar, three of them at Amount 100%. None of those profiles load here.
  The rig's own profile stays in the chain instead — and gets baked into any
  capture made from those presets.
- Confirm the profile by name in the plugin window. **"No Tone Profile"
  means none is loaded**, whatever the Amount knob reads. That is the state
  the accepted capture was made in — record it, do not load one.

## Read the preset, don't guess it

`scripts/read_preset.py` parses the plugin's `.afx` files (JUCE ValueTrees)
with no dependencies, and flags the capture hazards in each:

```bash
P="$HOME/Library/Odeholm Audio/thall amp/Presets/Factory"
python3 scripts/read_preset.py "$P/Mirar - Leo.afx"          # every value
python3 scripts/read_preset.py --plan "$P/Mirar - Leo.afx"   # how to capture it
python3 scripts/read_preset.py --library                     # all of them, one line each
python3 scripts/read_preset.py --diff A.afx B.afx
```

Use it to recover a capture's reference state months later, to check what a
preset changes before loading it, or to answer "what does this preset
actually do" without disturbing a session. Two things it cannot tell you:
parameters some plugin versions save without a value (reported as *not
stored*), and anything Tone Lock overrides. Read those from the live plugin
— and read them **back after writing**, because `ableton-mcp` has echoed a
stale display string on write, on this exact plugin, on Chug.

## Making a capture that sounds like the preset

Every control lands in one of three places. Sorting a preset into them is
the whole job; `--plan` above does the sorting for you.

1. **Baked in** — set it right before Start Capture and the QC reproduces it
   for free. Input Gain, Tone Matching, Low Dirt, the whole amp section, the
   cab, Lo-Cut, Hi-Cut, Lo-Fi.
2. **Rebuilt on the grid** — turn it off in the plugin for the capture and
   put a QC block back in its place. **The gate, and only the gate.** Tighten
   Gate → −100 dB via the parameter (not Shape Power, which takes Chug with
   it), then a gate block before the capture on the QC.
3. **Captured as played** — everything else, including Whammy, Thicken,
   Chug and its Frequency, and the mono/stereo toggle. Expect the deficit
   wherever a dynamic or pitch control operates, record it, do not EQ it
   away.

**The only change from the organic preset is the gate to −100 dB** (the
capture recipe in `SKILL.md`). The older recipe — pitch section off, mono —
is what V4 was made with and is history. The idea that a captured pitch
shifter "learns a worse version of the amp" was never confirmed by ear on
this plugin; the gate-on captures were, and they were the ones that sounded
wrong. `--plan` prints the plan in these terms.

**Standing input state (the accepted Ashen capture):** plugin
**Input Gain +16.8 dB** with RME In 4 at gain 13, Tone Match **locked** and
showing **No Tone Profile** (Amount 30%, Smooth 80% — inert without a
profile), Lo Cut 97 Hz, hard playing around −13 dBFS on the plugin's Input
meter. Screenshot in `references/thall-amp-input-ideal.png`. Input Gain
is baked into a capture, so this number is part of the recipe, not a
per-session calibration; set it before Start Capture and leave it alone.

**Use Neural Capture Version 1** (`SKILL.md`). The ideal calibration screen
is `references/neural-capture-v1-calibration-ideal.png`.

Plain-language meanings for every control, the QC block that replaces each
rebuilt one, and the grid order they go back in:
`references/thall-amp-plain-language-guide.md`.

## Levels

The user's working heuristic for the preset's output level: **hard chugs
should push the meter barely into red.** That corresponds to QC peaks near
−2 dBFS and lands the level offset within a few tenths of the plugin — the
standing capture's best take peaked at −2.13 dBFS with a +0.01 dB offset,
which is the target (`references/lab-history.md`).

Caveat: "barely red" leaves very little margin. A take at capture Volume +6
with a hotter capture (V5) reached 0.00 dBFS and clipped 134 samples, which
adds nonlinearity the plugin does not have and quietly degrades coherence
and null depth. For a **measurement** take, back off so peaks land near
−3 dBFS; for playing, barely-red is fine.

The plugin's **Auto Gain** button ("click and play hard for 5 seconds") sets
Input Gain for you. Input Gain is baked into a capture, so run it before
capturing and never between a capture and its measurement take.

## Session gotchas specific to this plugin

- **The tuner mutes the input.** Tuner Auto-Mute is on by default, so a
  tuner left open feeds the capture loop silence.
- **An expired licence adds noise to the output**, and a capture would model
  it. Confirm the licence before a session.
- **11 factory presets load a cab IR that is not on this machine** (all the
  Lance Prenc ones, The Old Way, two Simone Pietroforte ones). They fall back
  to the internal cab, so they do not sound as their authors built them, and
  capturing one captures the fallback. List in
  `references/thall-amp-factory-presets.md`.
- **The plugin is not necessarily on the preset a capture was made from.**
  Check with a live parameter read before a measurement take, not from
  memory.
- **Verify against the plugin window, not only parameter readouts**
  (`SKILL.md`).

The standing capture, its preset, its measured envelope, and the open items
are in `references/lab-history.md`.
