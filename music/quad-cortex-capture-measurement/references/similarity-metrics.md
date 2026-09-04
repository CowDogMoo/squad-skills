# Similarity metrics for capture verification

Distilled from a 2026-09-04 deep-research pass over the neural amp modeling
literature and capture-community practice. This file is the source for every
ESR or null-depth ladder this skill quotes.

## ESR — the community headline

`ESR = Σ(y − ŷ)² / Σy²` on time-aligned, gain-matched audio, with the plugin
as reference `y`. 0 = identical; 0.01 ≈ −20 dB residual. It is the number the
Neural Amp Modeler trainer prints after every run, so quoting it makes this
skill's measurements comparable with every NAM/AIDA-X/ToneX accuracy
conversation.

Ladders actually shipped in tools:

| ESR | NAM (`nam/train/core.py`) | AIDA-X best practices |
| --- | --- | --- |
| < 0.01 | "Great!" | 0–0.05 "great success" |
| < 0.035 | "Not bad!" | — |
| < 0.1 | "might sound ok" | 0.15–0.2 slightly noticeable |
| < 0.3 | "probably won't sound great" | 0.2–0.35 "sister amp" |
| ≥ 0.3 | "something went wrong" | > 0.9 check levels/alignment |

Qualifiers that keep the number honest:

- **The floor.** NAM warns when the validation signal's replicate self-ESR
  exceeds 0.01 — the chain's own noise bounds achievable ESR. A physical
  tube rig re-recorded with the same DI self-nulls near **ESR ≈ 0.04**.
  Measure the rig's floor once (same pass recorded twice, run the two takes
  through `analyze.py` as PLUGIN and QC) and report capture ESR relative to
  it via `--esr-floor`.
- **Perception tracks it loosely.** The MUSHRA study (Wright et al. 2020):
  ESR 0.002–0.007 rated ~97/100 (transparent); 0.02–0.04 audible but still
  "Good/Excellent"; ordering not monotonic (an RNN at 0.042 beat a WaveNet
  at 0.028). The **pre-emphasized variant** (first-order high-pass
  1 − 0.85z⁻¹, or A-weighting) tracks hearing better — `analyze.py` prints
  both.
- **Cross-architecture pairs read high.** A QC capture measured against the
  plugin it models cannot reach NAM-vs-own-training-target ESR: different
  nonlinear engines put distortion harmonics at different phases, which is
  the same reason the program-material null stays at −1.5 to −2.5 dB.

## Null depth — why the community numbers disagree

All of these are correct for what they measure:

| Null | What was nulled |
| --- | --- |
| ~−88 dB | identical digital files (DeltaWave's floor) |
| ~−60 dB | two electronics chains, the "audibly transparent" consensus |
| mid-−40s dB | an honest DAC→ADC analog loop |
| ~−14 dB (ESR 0.04) | a tube rig re-recorded against itself |
| −1.5 to −2.5 dB | QC capture vs plugin, high-gain program material |

The gradient is nonlinearity and phase, not measurement error. A single null
number also hides *where* the residual lives — a delta concentrated below
300 Hz can score fine and still sound worse — which is why this skill always
pairs it with banded deltas.

## The metric hierarchy (strictest → most forgiving)

1. **Raw null / plain ESR** — punishes level, time, phase, EQ, and
   nonlinearity at once.
2. **Null after best-fit linear EQ** (the script's Wiener step; DeltaWave's
   EQ match) — removes linear tone differences, isolating nonlinear and
   temporal mismatch.
3. **Phase-blind spectral metrics** (banded deltas; multi-resolution STFT
   loss if a comparative number across candidate captures is wanted —
   `auraloss.freq.MultiResolutionSTFTLoss`) — pure tone match. Per-band
   coherence sits alongside this rung as the localizer: level- and
   EQ-independent, it says *where* the residual is nonlinear mismatch
   rather than fixable tone difference (the SKILL's coherence-gated EQ rule
   comes from exactly this).
4. **Perceptually weighted views** (DeltaWave's PK metric: equal-loudness
   weighting + ERB smoothing; ≤ −70 dB ≈ "unlikely audible") — map residual
   to audibility.

Interpret cross-architecture results on rungs 2–3; quote rung-1 ESR for
community comparability with the qualifiers above.

## Perceptual and learned metrics — verdicts for guitar

- **ViSQOL v3** — the one off-the-shelf perceptual MOS worth running:
  dedicated 48 kHz audio/music mode, outputs 1–5 (saturates ~4.75).
  Codec-trained, so treat as secondary.
- **PESQ / STOI** — speech-only, invalid for music. **PEAQ / PEMO-Q** —
  codec-calibrated or license-locked; skip.
- **CDPAM** — pair-level learned perceptual distance, right shape but
  speech-trained; relative signal only, after local calibration.
- **AFx-Rep (ST-ITO)** — embedding trained specifically on production style
  (EQ, drive, dynamics) independent of content; the best learned complement
  if one is ever wanted. Research code, no published calibration.
- **FAD / KAD** — distribution-level; invalid for one capture vs one
  reference. Don't reach for them here.

Every threshold above calibrates locally: score known-identical, known-good,
and known-bad pairs from this rig before trusting an absolute number.

## Sources

- NAM and its ESR ladder: <https://github.com/sdatkinson/neural-amp-modeler>
- DAFx-19 pre-emphasized ESR: <https://dafx.de/paper-archive/2019/DAFx2019_paper_43.pdf>
- MUSHRA-vs-ESR study: <https://www.mdpi.com/2076-3417/10/3/766>
- A-weighted perceptual loss: <https://arxiv.org/abs/1911.08922>
- Neural amp modeling review: <https://www.mdpi.com/2076-3417/12/12/5894>
- AIDA-X ladder: <https://mod.audio/modeling-amps-and-pedals-for-the-aida-x-plugin-best-practices/>
- GuitarML guidance: <https://keyth72.medium.com/guitarml-faq-6b18abc1116c>
- Rig self-ESR ≈ 0.04: <https://thegearforum.com/threads/nam-neural-amp-modeler.1698/page-17>
- DeltaWave method + PK metric: <https://deltaw.org/> and <https://deltaw.org/pk_metric.html>
- −60 dB transparency consensus: <https://gearspace.com/board/so-much-gear-so-little-time/532582-null-tests.html>
- auraloss (ESR/MR-STFT losses): <https://github.com/csteinmetz1/auraloss>
- ViSQOL: <https://github.com/google/visqol>
- CDPAM: <https://github.com/pranaymanocha/PerceptualAudio>
- AFx-Rep / ST-ITO: <https://github.com/csteinmetz1/st-ito>
