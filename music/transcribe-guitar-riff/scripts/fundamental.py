#!/usr/bin/env python3
"""Name the notes in a passage from the band their own fundamentals live in.

Two jobs, in the order they have to happen:

1. **Calibrate.** Point `--reference` at a passage whose notes are already
   settled and pass `--expect` with those note names. The offsets printed tell
   you how far the recording sits from concert pitch. Until you know that, an
   absolute pitch call is meaningless - a peak at 90.8 Hz is F#2 thirty cents
   flat or F2 seventy cents sharp, and nothing in the peak itself decides which.

2. **Read.** Give a band that contains the fundamentals of the part you are
   asking about and nothing else's. Not a harmonic band: every instrument above
   you has fundamentals where you have partials, so a harmonic band answers a
   question about a different instrument and does not say so. This is the quiet
   form of the band-limited trap in references/analysis-notes.md - a template
   scored over 70-100 Hz once preferred F# to F because the strongest peak there
   belonged to the second guitar, while the 34-50 Hz band, where nothing else
   plays, gave F1 outright with the wrong answer 318 cents away.

Peaks are refined by parabolic interpolation on the log magnitude, so the answer
is not quantised to the FFT's bin spacing - which matters down low, where a
65536-point window at 44.1 kHz still spans about 28 cents per bin at 45 Hz.

    python fundamental.py CLIP.wav --band 34 50
    python fundamental.py CLIP.wav --band 115 175 --expect C3,B2,E3,D#3
    python fundamental.py CLIP.wav --band 34 50 --candidates D1,F1,F#1 --json out.json
"""
from __future__ import annotations

import argparse
import json

import librosa
import numpy as np

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(hz: float) -> tuple[str, float]:
    midi = 12 * np.log2(hz / 440.0) + 69
    n = int(round(midi))
    return f"{NAMES[n % 12]}{n // 12 - 1}", float((midi - n) * 100)


def peaks_in_band(y, sr, lo, hi, n_fft, top):
    """Mean spectrum over the non-silent frames, then interpolated local maxima."""
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=n_fft // 8))
    loud = S.max(axis=0) > 0.05 * S.max()
    if loud.any():
        S = S[:, loud]
    prof = S.mean(axis=1)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    df = freqs[1] - freqs[0]

    def refine(i):
        a, b, c = (np.log(max(prof[i + k], 1e-12)) for k in (-1, 0, 1))
        denom = a - 2 * b + c
        return (i + (0.5 * (a - c) / denom if denom else 0.0)) * df

    band = np.where((freqs >= lo) & (freqs <= hi))[0]
    band = band[(band > 0) & (band < len(prof) - 1)]
    found = [i for i in band if prof[i] > prof[i - 1] and prof[i] >= prof[i + 1]]
    found.sort(key=lambda i: -prof[i])
    out = []
    for i in found[:top]:
        hz = refine(i)
        name, cents = note_name(hz)
        out.append({"hz": round(float(hz), 3), "rel": round(float(prof[i] / prof[found[0]]), 3),
                    "note": name, "cents": round(cents, 1)})
    return out, df


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav")
    ap.add_argument("--band", nargs=2, type=float, required=True, metavar=("LO", "HI"),
                    help="Hz range holding the fundamentals of the part in question")
    ap.add_argument("--expect", default="",
                    help="comma-separated note names already known to be in this passage; "
                         "prints the offset of each measured peak from them")
    ap.add_argument("--candidates", default="",
                    help="comma-separated note names to score explicitly, e.g. D1,F1,F#1")
    ap.add_argument("--n-fft", type=int, default=65536)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--json", dest="json_out", default="")
    args = ap.parse_args()

    y, sr = librosa.load(args.wav, sr=None, mono=True)
    lo, hi = args.band
    if hi <= lo:
        ap.error("--band needs LO < HI")
    peaks, df = peaks_in_band(y, sr, lo, hi, args.n_fft, args.top)
    if not peaks:
        print(f"no peaks in {lo}-{hi} Hz - widen the band or check the clip is not silent")
        return 1

    print(f"# {args.wav}   {lo}-{hi} Hz, {df:.3f} Hz bins, {len(y) / sr:.2f}s")
    expect = [n for n in args.expect.split(",") if n]
    for p in peaks:
        line = f"  {p['hz']:9.3f} Hz  {p['rel']:.2f}  {p['note']:<4} {p['cents']:+7.1f} cents"
        for e in expect:
            line += f"   | vs {e}: {1200 * np.log2(p['hz'] / librosa.note_to_hz(e)):+7.1f}c"
        print(line)

    if expect:
        offs = []
        for e in expect:
            hz = librosa.note_to_hz(e)
            near = min(peaks, key=lambda p: abs(1200 * np.log2(p["hz"] / hz)))
            offs.append(1200 * np.log2(near["hz"] / hz))
        within = [o for o in offs if abs(o) < 50]
        if within:
            print(f"\nreference pitch: {np.mean(within):+.1f} cents from concert "
                  f"({len(within)}/{len(expect)} expected notes matched within 50c)")
            if abs(np.mean(within)) > 25:
                print("  NOTE: that is enough to change a semitone call - carry it into every reading below")

    scored = []
    if args.candidates:
        print("\nnamed candidates (distance from the strongest peak):")
        for c in args.candidates.split(","):
            hz = librosa.note_to_hz(c)
            near = min(peaks, key=lambda p: abs(1200 * np.log2(p["hz"] / hz)))
            cents = 1200 * np.log2(near["hz"] / hz)
            scored.append({"note": c, "nearest_hz": near["hz"], "cents": round(float(cents), 1),
                           "rel": near["rel"]})
            # a candidate is only present if a peak is BOTH close in pitch and
            # actually loud - a weak peak 17 cents away is a neighbour's skirt,
            # not the note, and calling it a match is how a wrong reading
            # survives a check that looked rigorous
            verdict = ("present" if near["rel"] >= 0.6 else f"weak ({near['rel']:.2f})") \
                if abs(cents) < 50 else "absent"
            print(f"   {c:<4} {hz:8.2f} Hz -> nearest peak {near['hz']:8.3f} Hz "
                  f"{cents:+8.1f}c  rel {near['rel']:.2f}  {verdict}")
        strong = [x for x in scored if abs(x["cents"]) < 50 and x["rel"] >= 0.6]
        if len(strong) == 1:
            print(f"\n   -> {strong[0]['note']} is the only candidate both in tune and loud here")
        elif not strong:
            print("\n   -> none of these candidates is both in tune and loud; widen --candidates")

    if args.json_out:
        json.dump({"wav": args.wav, "band": [lo, hi], "bin_hz": round(float(df), 4),
                   "peaks": peaks, "candidates": scored}, open(args.json_out, "w"), indent=2)
        print(f"\njson: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
