---
name: thall-amp-neural-capture
description: Amp-specific knowledge for capturing the Odeholm thall amp plugin into the Quad Cortex and judging the result - what every one of its 30 controls does and whether a static Neural Capture can model it, why Tighten Chug and Pitch Thicken cannot be, the Tone Lock trap that makes a preset load differently from its file, the 53 factory presets including the ones with missing cab IRs or embedded tone profiles, a bundled reader for preset files, the V1-V5 capture history, and the measured envelope for the standing V4 capture. Pair with quad-cortex-plugin-capture, quad-cortex-capture-measurement, and quad-cortex-preset-editing, which carry the general method. Trigger on "thall amp", "thall capture", "Mirar Leo", "Monomythic", "Chug", "Thicken", "Tone Match", "what does this knob do", "which preset should I capture", "why is my low end missing", "60-120 hole", "V4 vs V5", or any question about this plugin's controls, presets, capturing, or measuring. Do NOT use for other plugins or for general QC workflow questions.
---

# Thall amp — the plugin, and what a Neural Capture does with it

Odeholm Audio **thall amp v1.0.4**. Everything about capturing it was learned
on the user's rig across V1–V5 (2026-08-23 to 2026-08-30), measured every
time with `quad-cortex-capture-measurement`. Everything about its controls
and presets is read from the plugin itself — its published parameter info,
its own tooltip text, and the preset files on disk.

- What every control means in ordinary guitar terms, and which QC block
  replaces it: `references/plain-language-guide.md`.
- Every control, its range, its tooltip, and its capture verdict:
  `references/control-reference.md`.
- All 53 factory presets with values and per-preset capture warnings:
  `references/factory-presets.md`.
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
right at all."* V5 was rejected. V4 remains the standing capture.

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
  Low Dirt. The capture workflow turns it off to drop the pitch shifter's
  latency, which is correct only when Thicken is already at 0.

The 30 automatable parameters, ranges, and defaults are in
`references/control-reference.md`. Live's **Device On** is the plugin's Host
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
| Low Dirt (static pre-distortion) | **Tighten Gate** — level-dependent; off for a capture-safe capture, as played for an organic one (user's call, see `quad-cortex-plugin-capture`) |
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
is in `quad-cortex-capture-measurement`.

## The Tone Lock trap

**Tone Lock is on for this rig, so a preset does not load its own tone-match
settings or input gain.** The plugin's tooltip: *"When locked, prevents tone
match and input gain parameters from changing when switching presets."*

Two pieces of evidence, both re-checkable: the user's own saved preset
records Tone Lock enabled, and on 2026-08-31 the live plugin sat at Input
Gain +2.4 dB while the preset it was on (Simone Pietroforte – Brutal Death
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
  means none is loaded**, whatever the Amount knob reads.

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
   put a QC block back in its place. The gate, Whammy, and Thicken.
3. **Lost** — Chug and its Frequency. Capture as played, expect the deficit,
   record it, do not EQ it away.

The mistake to avoid is capturing something in bucket 2 rather than
rebuilding it. A capture trained on a signal containing a pitch shifter does
not learn the pitch shifter — it learns a worse version of the amp.

Plain-language meanings for every control, the QC block that replaces each
rebuilt one, and the grid order they go back in:
`references/plain-language-guide.md`.

## Capture-time state for V4 (the standing capture)

V4 is the factory preset **Mirar – Leo** with five deliberate changes:

| Control | Mirar – Leo as shipped | V4 capture-time | Why |
| ------- | ---------------------- | --------------- | --- |
| Tighten Gate | −12 dB | **−100 dB** | a gate swallows the QC's own test signal |
| Pitch Power | On | **Off** | drops the pitch shifter's latency — and Thicken with it |
| Mono/Stereo Toggle | On (stereo) | **Off** (mono) | the capture loop is mono |
| Tone Matching Power | Off in the file | **On**, Amount 30%, Smooth 80% | Tone Lock kept the rig's own profile |
| Input Gain | +0.0 dB | **+2.4 dB** | level calibration into the plugin |
| Cab Power | On | On | an "Amp and Cab" capture |

Unchanged from the factory preset: Amp Drive 61%, Lo +0.0, Mid +1.9,
Hi +3.1, Presence +1.6; Tighten Chug 50% at 1.6 kHz; Low Dirt 0%; Lo-Fi,
Lo-Cut and Hi-Cut all Off; Output Gain +0.0.

**What is missing is on the QC, not in the capture.** Mirar – Leo ships
**Pitch Thicken at 17%** — an octave-down summed into the dry signal before
the amp, so it changes how the amp distorts, not just what sits under it.
Powering the Pitch section off was the right call at capture time: a pitch
shifter is not something a static model can learn, and leaving it in would
have corrupted the amp model as well. But the octave then has to come back
as a **QC pitch block before the capture**, and the standing preset does not
have one — its Wham and Pitch Shifter blocks are bypassed. No recapture is
needed; enable the Pitch Shifter at **Coarse −12, Mix 17%**.

**Do not write a low-pass into that spec.** The QC Pitch Shifter block has
exactly three parameters — **Mix, Coarse, Fine** — and no wet-path filter, so
there is nowhere on it to put the plugin's Pitch Hi-Cut (10.0 kHz in Leo, read
from the preset file). An EQ dropped on the same row to supply it filters the
**whole** signal into the capture, not the octave: a handoff spec of "−12 st,
mix 17%, low-pass 270 Hz" applied literally would have hung a 270 Hz brick
wall across the entire guitar. Filtering only the shifted voice needs a
Splitter → [pitch block + EQ] and dry → Mixer. Leo's Hi-Cut is near full range
anyway, so a bare single-row pitch block is a small error here — but say
"close, not exact". See `references/plain-language-guide.md`.

## Capture history and verdicts

| Version | What it was | Verdict |
| ------- | ----------- | ------- |
| V1 | First Monomythic capture, Chug 50 | Superseded; had the 60–120 hole |
| V2 | Hotter capture input | **Rejected** — proved hotter input makes the hole worse, plus 1 kHz+ fizz |
| V3 | No notes kept | **Rejected** — +10–15 dB sub, rolled off above 2 kHz, coherence 0.29 |
| V4 | "Thall Mirar Leo Amp and Cab", Chug 50 | **STANDING CAPTURE.** Sounds right, measures well everywhere Chug allows |
| V5 | "…Amp and Cab NoCh", Chug 0 | **Rejected by ear** despite being the best-measuring capture made here |

Keep V5 on the unit. It is the proof of the Chug hypothesis and the reason
the 60–120 item is closed.

V1's source preset, **Jesse Zuretti – Monomythic**, is worth knowing about:
it runs Chug at 100% at 51 Hz, Drive 100%, and a 48 kHz tone profile at
Amount 100% that Tone Lock prevented from loading. Chug at 100% right in the
band that later became "the 60–120 hole" is the whole story of V1.

## The standing preset ("1D Thall Experimental")

- Capture block: **Thall Mirar Leo Amp and Cab** (V4), Gain 0.0,
  Bass/Mid/Treble 0.0, **Volume +6.0**
- Parametric-3 **active**: band 1 Peak **350 Hz Q1.00 +2.5 dB**, band 2
  **HPF 55 Hz Q0.71**, band 3 hi shelf **0.0** (zeroed — it was V1's fix and
  pulled V4's flat top down ~0.5 dB)
- IR Loader and Reverb **bypassed**; lane output **0.0**, Multi Out with
  USB Output 3/4 enabled

Never put makeup gain on the capture block's **Gain** — that changes how hard
the model is driven. Volume only.

## Known-good measured envelope (V4 vs the real amp at Chug 50)

Best measurement to date, 2026-08-30 16:54 take, 67.6 s continuous:

| Band | Delta | Coherence |
| ---- | ----- | --------- |
| Level offset | **+0.01 dB** | — |
| 60–120 | **−3.7** (expected — Chug) | 0.51 |
| 120–250 | +1.2 | 0.79 |
| 250–500 | +0.7 | 0.84 |
| 500 Hz–1 kHz | +0.4 | 0.80 |
| 1–2 kHz | −0.2 | 0.60 |
| 2–8 kHz | −0.1 to +0.0 | 0.14 – 0.36 |
| 8–12 kHz | −0.6 | 0.05 |
| Null | **−3.0 gain / −4.1 linear EQ** | — |

A later take that measures materially worse than this between 250 Hz and
8 kHz means something drifted — reverb un-bypassed, lane output moved, wrong
capture loaded, or the plugin left on a different preset — not that the
capture degraded.

## Levels

The user's working heuristic for the preset's output level: **hard chugs
should push the meter barely into red.** That corresponds to QC peaks near
−2 dBFS and lands the level offset within a few tenths of the plugin — the
16:54 take peaked at −2.13 dBFS with a +0.01 dB offset, which is the target.

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
  `references/factory-presets.md`.
- **The plugin is not necessarily on the preset a capture was made from.**
  Check with a live parameter read before a measurement take, not from
  memory.
- **Verify against the plugin window, not only parameter readouts** — the
  general rule and its worked example live in `quad-cortex-plugin-capture`.

## What is closed, and what is still open

**Closed:** the 60–120 Hz deficit. Cause identified (Chug is dynamic and
unmodellable), hypothesis confirmed by V5, control take rules out the
reference as an explanation. V4 plus the standing preset is finished at
rung 3, measured.

**Open:**

1. **The standing preset is missing Leo's octave.** Mirar – Leo ships Pitch
   Thicken at 17% and the capture correctly excluded it, but the QC pitch
   block that should replace it is bypassed. Enable the Pitch Shifter at
   **Coarse −12, Mix 17%**, before the capture block, then A/B against the
   plugin with its pitch section on. **No low-pass on that row** — the block
   has only Mix/Coarse/Fine, and an EQ beside it filters the dry signal too
   (see the note above). A preset edit, not a recapture.
2. **Does Pitch Power off also bypass Low Dirt?** The UI files Low Dirt
   under the pitch section. It has not mattered — every capture so far used
   Low Dirt 0 — but 37 of 54 installed presets have it above zero. Set Low
   Dirt to 100, toggle Pitch Power, listen.
3. A **Chug 25** capture, only if curiosity strikes. A two-point
   dose-response now exists, so it should land between V4 and V5 on both
   coherence and delta. The only question is whether the feel survives — and
   "100% does not sound right" at Chug 0 is not encouraging.
4. Capture at Chug 0 (which models the static amp beautifully) and reproduce
   the dynamic Chug behaviour with a QC dynamics block after the capture.
   Splits the problem along the line the measurement drew. Unproven, and
   matching Chug by ear would be its own project.

Do not reopen the 60–120 item by any other route.
