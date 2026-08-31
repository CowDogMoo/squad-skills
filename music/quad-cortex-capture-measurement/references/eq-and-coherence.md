# EQ, band deltas, and coherence

Why a post-capture EQ moves a reported band delta by an amount you can
compute in advance, why coherence is not part of that amount, and what
coherence does decide. Supersedes the earlier "EQ-vs-coherence lesson",
which attributed an observation to the wrong cause.

## The law

`scripts/analyze.py` normalises each spectrum to its own 500 Hz–2 kHz mean
before differencing, and reports each band as an unweighted mean of power
across the bins in it. A linear EQ on the QC therefore multiplies the band's
power by its own response and leaves the plugin alone, so

```text
Δdelta(band) = Ḡ(band) − Ḡ(500 Hz–2 kHz)

Ḡ(S) = 10·log10( mean_{f∈S} P(f)·|H(f)|² / mean_{f∈S} P(f) )
```

with `P` the pre-EQ QC spectrum and `H` the EQ's response. Two corollaries
that matter in practice:

- The gain that counts is the average over the **whole reporting band**, not
  the peak. A bell narrower than its band is heavily diluted.
- An EQ that reaches into 500 Hz–2 kHz lifts the reference and gives part of
  the move back.

This assumes the EQ is **downstream of the capture block**, as the
Parametric-3 is in every chain in this corpus. An EQ ahead of a nonlinear
block is not a linear operation on the output and none of this applies.

## Coherence is invariant under EQ

γ² = |Sxy|²/(Sxx·Syy). Filtering y by H multiplies Sxy by H\* and Syy by
|H|², which cancels exactly. Measured on controlled fixtures: **0.00001**
change under a +2.5 dB shelf at 4 kHz. A 90 Hz Q3 bell shows 0.013, which is
Welch estimator leakage for a filter narrower than the analysis bandwidth,
not an effect — at `nperseg` 16384 instead of 4096 it falls to 0.001.

So coherence cannot be what decides whether EQ moves a delta. Two fixtures
built identical except for coherence above 1.2 kHz, same −2.6 dB high-band
deficit, same +2.5 dB shelf at 4 kHz:

| band | coherence 0.15 | coherence 1.00 | difference |
| ---- | -------------- | -------------- | ---------- |
| 4–5 kHz | moved +1.52 dB | moved +1.51 dB | 0.005 dB |
| 5–8 kHz | moved +2.14 dB | moved +2.14 dB | 0.004 dB |
| 8–12 kHz | moved +2.42 dB | moved +2.42 dB | 0.002 dB |

Predicted against measured: 0.000 dB error in every cell. Run end to end
through `scripts/analyze.py` on a fixture the tool itself scores at
coherence 0.16 / 0.17 / 0.17, the deltas moved +1.50 / +2.10 / +2.40 dB
against +1.49 / +2.06 / +2.40 predicted.

## What coherence does decide

The null. Same magnitude correction, applied linear-phase so the corrector's
own phase is not a confound (controlled fixtures, not rig figures):

| coherence | null before (gain / lin-EQ) | after | gain-match null |
| --------- | --------------------------- | ----- | --------------- |
| 1.00 | −16.4 / −67.4 dB | −22.5 / −66.7 dB | improved 6.1 dB |
| 0.15 | −3.2 / −5.0 dB | −2.9 / −3.9 dB | worsened 0.3 dB |

Below ~0.8, flattening a band buys long-term tonal balance and no time-domain
match; the residual gets marginally louder because two uncorrelated signals
of matched magnitude do not cancel. That is a real reason to be careful, and
a different one from "the EQ will not work".

## Re-analysis of the 2026-08-24 bells

`references/calibration-baseline.md` records four takes, one post-capture EQ
shape each. Model each as `D0 + Ḡ(60–120 Hz)`, one free parameter for the
no-EQ delta, no coherence term:

| take | EQ shape | Ḡ | measured | modelled | residual |
| ---- | -------- | - | -------- | -------- | -------- |
| 13:07 | lo shelf +3 @ 75 | +1.11 dB | −3.4 | −3.33 | −0.07 |
| 13:24 | peak +3 @ 90 Q1.5 | +2.36 dB | −2.3 | −2.08 | −0.22 |
| 13:31 | peak +4 @ 90 Q3 + HPF 50 | +1.84 dB | −2.5 | −2.60 | +0.10 |
| 15:07 | peak +3 @ 90 Q1.5 + HPF 65 | +1.14 dB | −3.1 | −3.30 | +0.20 |

Largest residual **0.22 dB** against this skill's own 0.8 dB cross-take noise
floor, and the implied no-EQ delta is **−4.4 dB**, inside the −4 to −5 dB the
corpus reports for that capture from separate takes. Power-weighting by a
real QC spectrum instead of flat gives −4.6 dB and residuals ≤ 0.21 dB.

Every shape tried had only +1.1 to +2.4 dB of band-mean gain across
60–120 Hz, because a bell at 90 Hz is narrower than the band it is scored
in, and two of the four takes handed part of it back with a high-pass. The
old reading — "the bell never moved it, because coherence there is ~0.5" —
compared takes whose gains differed by about a dB and credited coherence for
the result. The EQ moved the band every time, by the amount its shape
predicts.

None of this touches the Chug diagnosis. That the 60–120 Hz deficit is a
dynamic-process signature rests on the V4/V5 control take in
`thall-amp-neural-capture`, not on the EQ argument, and it stands.
