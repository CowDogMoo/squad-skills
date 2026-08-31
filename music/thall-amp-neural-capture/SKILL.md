---
name: thall-amp-neural-capture
description: Amp-specific knowledge for capturing the Odeholm thall amp plugin into the Quad Cortex and judging the result - the capture-as-played rule, why the Tighten Chug control cannot be modelled by a Neural Capture, the expected 60-120 Hz signature that follows from it, the V1-V5 capture history and verdicts, and the known-good measured envelope for the standing V4 capture. Pair with quad-cortex-plugin-capture (how to run a capture), quad-cortex-capture-measurement (how to measure one), and quad-cortex-preset-editing (how to host one in a preset); those carry the general method, this carries the substance for this amp. Trigger on "thall amp", "thall capture", "Mirar Leo", "Monomythic", "Chug", "why is my low end missing", "60-120 hole", "which thall capture should I use", "V4 vs V5", or any question about capturing or measuring this particular plugin. Do NOT use for other plugins or for general QC workflow questions.
---

# Thall amp — Neural Capture specifics

Everything here was learned capturing the Odeholm thall amp plugin into a Quad
Cortex on the user's rig across V1–V5 (2026-08-23 to 2026-08-30) and measuring
every version with `quad-cortex-capture-measurement`.

## The rule that matters most

**Capture the preset in the state you actually play it. Do not neuter controls
to make the capture measure better.**

This was learned the expensive way. The 60–120 Hz deficit that dogged V1, V2 and
V4 traces to the plugin's **Tighten Chug** control being at 50%. Setting Chug to
0 and recapturing (V5) fixed the measurement spectacularly — 60–120 went from
−4.0 dB at coherence 0.43 to −0.7 dB at 0.58, and with one corrective bell every
band from 60 Hz to 12 kHz sat within 1.1 dB. It was the best-measuring capture
the project ever produced.

The user's verdict on hearing it: *"v5 without chug 100% DOES NOT sound right at
all."* V5 was rejected. V4 remains the standing capture.

Chug-0 is not a cleaner version of the same amp. It is a different amp sound.
The measurement is a servant of the sound, never the reverse. When a measurement
and the ears disagree about which capture is better, the ears win and the
measurement's job is to explain why.

## Why Chug cannot be captured

A Neural Capture models a **static** nonlinear system. Tighten Chug is a
**dynamic**, time-varying process — it lives in the plugin's Tighten section
beside the gate, with its own Frequency control at 1.6 kHz. A static model
cannot reproduce a time-varying one; the capture learns some average of what
Chug does and the moment-to-moment behaviour is lost.

That is exactly what the coherence column reports, and it is measurable:

| Plugin Chug | 60–120 Hz delta | 60–120 Hz coherence |
| ----------- | --------------- | ------------------- |
| 50% (as played) | −3.7 to −5.0 dB | 0.27 – 0.52 |
| 0%              | −0.4 to −1.0 dB | 0.58 – 0.64 |

The control take that proved it: V4 measured against the plugin at **Chug 0**
scored 0.27 coherence at 60–120, versus V5's 0.58 against the identical
reference. Chug 0 is a *harder* target for a Chug-50 capture, not an easier one,
so the low-end gap belongs entirely to the capture-versus-Chug mismatch and not
to the choice of reference.

**A roughly −4 dB deficit at 60–120 Hz with coherence around 0.4–0.5 is the
EXPECTED result for any Chug-50 capture of this amp. It is the price of Chug,
and Chug is what makes it sound right. It is not a defect.**

It is not an EQ item — bells at +3 Q1.5, +4 Q3 and every other shape moved it
less than ~1 dB, because coherence there is far below the ~0.8 threshold where
linear EQ can move a band. It is not a capture-input-level item — V2 tested a
hotter capture input and made it worse. It is not a capture-quality item — V5
proved the model is fine once Chug is out of the way. Stop chasing it.

A high-pass below the plugin's own 65 Hz low cut is still always worth having
on this amp — see the general rule in `quad-cortex-capture-measurement`.

## Capture-time reference state (V4 — the standing capture)

Read this back from the live plugin; never assume it. Chug is the parameter
that has produced a stale `ableton-mcp` display string on write — see the
read-back rule in `quad-cortex-plugin-capture`.

- Tighten Chug **50%**, Tighten Frequency 1.6 kHz
- Tighten Gate **−100 dB** (fully off)
- Pitch Power **Off**, Mono/Stereo Toggle **Off**
- Cab Power **On** (this is an "Amp and Cab" capture)
- Input Gain **+2.4 dB**, Output Gain **0.0 dB**
- Lo-Fi Off, Low Dirt 0%, Lo-Cut Off, Hi-Cut Off
- Tone Matching On, Amount 30%, Smooth 80%
- Amp Drive 61%, Lo +0.0, Mid +1.9, Hi +3.1, Presence +1.6

## Capture history and verdicts

| Version | What it was | Verdict |
| ------- | ----------- | ------- |
| V1 | First Monomythic capture, Chug 50 | Superseded; had the 60–120 hole |
| V2 | Hotter capture input | **Rejected** — proved hotter input makes the hole worse, plus 1 kHz+ fizz |
| V3 | No notes kept | **Rejected** — +10–15 dB sub, rolled off above 2 kHz, coherence 0.29 |
| V4 | "Thall Mirar Leo Amp and Cab", Chug 50 | **STANDING CAPTURE.** Sounds right, measures well everywhere Chug allows |
| V5 | "…Amp and Cab NoCh", Chug 0 | **Rejected by ear** despite being the best-measuring capture made here |

Keep V5 on the unit. It is the proof of the Chug hypothesis and the reason the
60–120 item is closed.

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

A later take that measures materially worse than this between 250 Hz and 8 kHz
means something drifted — reverb un-bypassed, lane output moved, wrong capture
loaded — not that the capture degraded.

## Levels

The user's working heuristic for the preset's output level: **hard chugs should
push the meter barely into red.** That corresponds to QC peaks near −2 dBFS and
lands the level offset within a few tenths of the plugin — the 16:54 take peaked
at −2.13 dBFS with a +0.01 dB offset, which is the target.

Caveat: "barely red" leaves very little margin. A take at capture Volume +6 with
a hotter capture (V5) reached 0.00 dBFS and clipped 134 samples, which adds
nonlinearity the plugin does not have and quietly degrades coherence and null
depth. For a **measurement** take, back off so peaks land near −3 dBFS; for
playing, barely-red is fine.

## What is closed, and what is still open

**Closed:** the 60–120 Hz deficit. Cause identified (Chug is dynamic and
unmodellable), hypothesis confirmed by V5, control take rules out the reference
as an explanation. V4 plus the standing preset is finished at rung 3, measured.

**Open, only if curiosity strikes:**

1. A **Chug 25** capture. A two-point dose-response now exists, so it should
   land between V4 and V5 on both coherence and delta. The only question is
   whether the feel survives — and "100% does not sound right" at Chug 0 is not
   encouraging.
2. Capture at Chug 0 (which models the static amp beautifully) and reproduce the
   dynamic Chug behaviour with a QC dynamics block after the capture. Splits the
   problem along the line the measurement drew. Unproven, and matching Chug by
   ear would be its own project.

Do not reopen the 60–120 item by any other route.
