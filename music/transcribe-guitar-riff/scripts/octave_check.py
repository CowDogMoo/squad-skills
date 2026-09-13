#!/usr/bin/env python3
"""Decide a riff's octave with a search band that cannot prejudge the answer.

This exists because of a real failure. A low-string tracker was run over
38-100 Hz, it answered "F1/F#1", and that answer was then cited as independent
confirmation of an earlier F1/F#1 reading. It was nothing of the kind: a comb
that can only look below 100 Hz can only ever return a note below 100 Hz. The
riff was actually on F#2 at 92.5 Hz, an octave up, and the tab was unplayable
because of it.

So: sample many attacks across the section, and at each one score every
candidate against the peaks the spectrum actually has, over a band derived from
the candidates rather than from a guess. A band-limited search is a hypothesis,
not a measurement.

**How a candidate is scored.** Two numbers, and a candidate has to win both:

- *coverage* - the share of observed peak amplitude that some partial of the
  candidate explains. A candidate an octave ABOVE the truth scores badly here:
  nothing in its series lands on the real fundamental or on any odd partial.
- *presence* - the 1/k-weighted share of the candidate's own predicted partials
  that the spectrum actually shows. A candidate an octave BELOW the truth
  scores badly here: it predicts f/2, 3f/2, 5f/2, and none of them exist.

The score is their product, so the only way to win is to explain what is there
AND to have nothing missing. A candidate a semitone off scores near zero on
both, because a cents error is the same at every partial - if k=1 is 100 cents
out, so is k=8, and no amount of leakage rescues it.

    python octave_check.py CLIP.wav --bpm 120 --origin-beat 64 --bars 21,36 \
        --candidates F1,F#1,F2,F#2,F3
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

import librosa
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fundamental import note_name  # noqa: E402  (same directory, one naming rule)

HARMONICS = 10
TOLERANCE_CENTS = 35.0


def spectrum_peaks(seg, sr, lo, hi, floor=0.02, top=48):
    """Interpolated local maxima of one window, as (hz, amplitude) pairs.

    The FFT is zero-padded 8x so parabolic interpolation can place a peak well
    inside a bin - which matters down low, where a raw bin is worth more than a
    semitone. Peaks below `floor` of the loudest are dropped as leakage.
    """
    n = 1 << (int(np.ceil(np.log2(len(seg)))) + 3)
    mag = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    df = freqs[1] - freqs[0]
    peak = mag.max()
    if peak <= 0:
        return []

    band = np.where((freqs >= lo) & (freqs <= hi))[0]
    band = band[(band > 0) & (band < len(mag) - 1)]
    out = []
    for i in band:
        if mag[i] < floor * peak or mag[i] < mag[i - 1] or mag[i] < mag[i + 1]:
            continue
        a, b, c = (np.log(max(mag[i + k], 1e-12)) for k in (-1, 0, 1))
        denom = a - 2 * b + c
        shift = 0.5 * (a - c) / denom if denom else 0.0
        out.append((float((i + shift) * df), float(mag[i] / peak)))
    out.sort(key=lambda p: -p[1])
    return out[:top]


def score_candidate(peaks, f0, harmonics=HARMONICS, cents=TOLERANCE_CENTS):
    """(score, coverage, presence) for one candidate fundamental.

    coverage - share of observed amplitude explained by a partial of f0.
    presence - 1/k-weighted share of f0's own partials the spectrum shows.
    """
    if not peaks or f0 <= 0:
        return 0.0, 0.0, 0.0

    total = sum(a for _, a in peaks) or 1.0
    explained = 0.0
    for hz, amp in peaks:
        k = round(hz / f0)
        if 1 <= k <= harmonics and abs(1200 * np.log2(hz / (k * f0))) <= cents:
            explained += amp
    coverage = explained / total

    weight_sum = present = 0.0
    for k in range(1, harmonics + 1):
        w = 1.0 / k
        weight_sum += w
        target = f0 * k
        if any(abs(1200 * np.log2(hz / target)) <= cents for hz, _ in peaks):
            present += w
    presence = present / weight_sum

    return coverage * presence, coverage, presence


def analysis_band(cands_hz, harmonics=HARMONICS):
    """Wide enough to hold every candidate's fundamental and its odd partials.

    Deriving this from the candidates rather than taking it from the user is
    the whole point: the band can no longer be set to exclude the answer.
    """
    lo = min(cands_hz) * 2 ** (-TOLERANCE_CENTS / 1200) * 0.9
    hi = max(cands_hz) * harmonics * 2 ** (TOLERANCE_CENTS / 1200) * 1.1
    return max(lo, 10.0), hi


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--origin-beat", type=float, default=0.0)
    ap.add_argument("--bars", required=True, help="LO,HI inclusive, 1-based")
    ap.add_argument("--candidates", default="F1,F#1,F2,F#2,F3")
    ap.add_argument("--beats-per-bar", type=float, default=4.0)
    ap.add_argument("--window", type=float, default=0.40, help="analysis window per sample, seconds")
    ap.add_argument("--per-bar", type=int, default=4, help="sample points per bar")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    lo_bar, hi_bar = (int(x) for x in args.bars.split(","))
    y, sr = sf.read(args.wav, always_2d=True)
    mono = y.mean(axis=1)
    spb = 60.0 / args.bpm
    cands = [c.strip() for c in args.candidates.split(",") if c.strip()]
    cands_hz = [float(librosa.note_to_hz(c)) for c in cands]
    lo_hz, hi_hz = analysis_band(cands_hz)
    hi_hz = min(hi_hz, sr / 2)

    wins = collections.Counter()
    rows = []
    margins = []
    for bar in range(lo_bar, hi_bar + 1):
        for k in range(args.per_bar):
            beat = (bar - 1) * args.beats_per_bar + k * (args.beats_per_bar / args.per_bar)
            t0 = (beat - args.origin_beat) * spb
            a, b = int(t0 * sr), int((t0 + args.window) * sr)
            if a < 0 or b > len(mono):
                continue
            seg = mono[a:b]
            if np.sqrt((seg ** 2).mean()) < 1e-4:
                continue
            peaks = spectrum_peaks(seg, sr, lo_hz, hi_hz)
            if not peaks:
                continue
            scored = sorted(
                ((score_candidate(peaks, hz), name) for hz, name in zip(cands_hz, cands)),
                key=lambda s: -s[0][0],
            )
            (best_score, coverage, presence), best = scored[0]
            if best_score <= 0:
                continue
            runner = scored[1][0][0] if len(scored) > 1 else 0.0
            wins[best] += 1
            margins.append(best_score - runner)
            rows.append({
                "bar": bar, "point": k, "winner": best,
                "coverage": round(coverage, 3), "presence": round(presence, 3),
                "loudest_peak_hz": round(peaks[0][0], 2),
                "loudest_peak_note": note_name(peaks[0][0])[0],
                "scores": {n: round(s[0], 4) for s, n in scored},
            })

    total = sum(wins.values())
    print(f"octave fit over bars {lo_bar}-{hi_bar}, {total} sampled attacks")
    print(f"searched {lo_hz:.1f}-{hi_hz:.1f} Hz, derived from the candidates "
          f"(a band you choose yourself cannot test the octave)")
    print("score = coverage x presence; a candidate must explain the peaks that "
          "are there AND have none of its own missing")
    for c in cands:
        n = wins.get(c, 0)
        bar = "#" * int(40 * n / total) if total else ""
        print(f"  {c:>4s} wins {n:4d} / {total}  {100 * n / total if total else 0:5.1f}%  {bar}")

    if not total:
        print("\nno attack was loud enough to score - check --bars, --origin-beat and --bpm")
        return 1

    top, n = wins.most_common(1)[0]
    share = 100 * n / total
    print(f"\nverdict: {top} ({share:.1f}% of sampled attacks, "
          f"median margin over the runner-up {np.median(margins):.3f})")
    if share < 60:
        print("LOW AGREEMENT: the attacks disagree about the octave. Treat this as "
              "unresolved and cross-check with fundamental.py and Basic Pitch "
              "before writing anything.")
    if args.json:
        json.dump({"bars": [lo_bar, hi_bar], "total": total, "band_hz": [lo_hz, hi_hz],
                   "wins": dict(wins), "verdict": top, "share": share, "rows": rows},
                  open(args.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
