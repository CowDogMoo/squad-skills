# Worked example: QC "1A Graft" → Fortin Grind + Archetype Gojira X

Goal: record guitars in Ableton with the tone of the Quad Cortex preset
"1A Graft" (scene A). Done 2026-11-07/08. Kept as calibration for what a good
result looks like, not as a procedure to repeat.

## Reference take

Guitar → QC Input 1; Live's input device = Quad Cortex at 48 kHz, output on
the audio interface. One take recorded QC USB channel 1 (DI) and channels
3/4 (wet) together. The QC preset was measured as played, with its 20 % Room
reverb on; the Gojira chain had its 20 % reverb on too.

## Attempt 1: Gojira only, OD as a Grind stand-in (rejected)

Preset "Graft": the mapping in `block-mapping.md` with Gojira's OD pedal on
as a clean boost in place of the Fortin Grind (`odDist` 0.078, `odLevel`
0.532, `odTone` 0.607) and the QC EQ copied as read.

Level and broad EQ matched; drive did not: coherence 0.3–0.7, ESR 0.77,
null −1.2 dB. An 8-point sweep of OD settings never beat ESR 0.68. Coherence
stayed at or below 0.80 in every band. The deficit was the drive stage, so
EQ was not attempted.

## Attempt 2: Nameless Grind → Gojira (kept)

- Fortin Nameless Suite X, preset "Graft Grind": gate on, Grind on with
  Boost 0.46, amp/EQ/cab/post-FX sections off, input and output 0 dB.
- Archetype Gojira X, preset "Graft with Nameless Grind": the Graft mapping
  with Gojira's gate off, OD off, custom IR on selected cab slot 2, EQ
  re-fitted to +2.7 / −0.5 / −5.2 / −4.5 / +2.5 / +3 / +1.5 / +1 / 0 and
  `outputGain` 3.4.

The bundled specs in `specs/` rebuild both from the factory defaults.

Result on the same take, scored with `quad-cortex-capture-measurement`'s
`analyze.py` (deltas QC − plugin, bands 60–120, 120–250, 250–500, 500–1k,
1–2k, 2–4k, 4–5k, 5–8k, 8–12k Hz):

| Metric | Value |
| --- | --- |
| Cross-correlation (same performance) | 0.96 |
| Loudness offset | within 0.1 dB |
| Band deltas (dB) | +0.4 / +0.3 / −0.2 / +0.2 / −0.1 / −0.1 / 0.0 / 0.0 / +0.1 |
| Coherence | 0.96 / 0.96 / 0.95 / 0.95 / 0.94 / 0.91 / 0.87 / 0.80 / 0.68 |
| Null after gain match | −11.2 dB |
| ESR | 0.0755 |

Every band within 0.4 dB from 60 Hz up; ESR in the "borderline-to-good"
gap of the ladder (< 0.05 good, ~0.1 borderline).

## Rung reached and what is still open

**Measured, on one take.** Open:

- One take. The EQ was fitted on the same take it was scored on, so the band
  deltas are a fit until a second take confirms them.
- Reverb on both sides. Two different reverbs contaminate coherence and the
  null; a reverb-off take would read the chain alone.
- Top-band coherence is the lowest (0.80 at 5–8 kHz, 0.68 at 8–12 kHz).
- Nobody had listened A/B yet.

## Offline render validation

The offline render of the Gojira preset and Live's own re-amp of the same DI
through the same preset nulled to −20.5 dB with ESR 0.009. After the IR was
moved out of Downloads and both presets were repointed, a re-render was
bit-identical.

## Cost (48 kHz, 128-sample blocks, this Mac)

| Chain | Load (one core) | Reported latency |
| --- | --- | --- |
| Gojira "Graft" alone | 4.8 % | 42 samples |
| Nameless "Graft Grind" alone | 1.6 % | 57 samples |
| Grind → Gojira | 6.2 % | 99 samples (≈ 2.1 ms) |

## Input path note

Switching the recording input between the QC's dry USB channel and the audio
interface's instrument input changed the level into the chain: a short test
showed peaks about 2 dB apart, which changes how hard the Grind and amp are
driven. Re-check gain staging whenever the input path changes.
