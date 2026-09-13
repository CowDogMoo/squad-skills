#!/usr/bin/env python3
"""Fit a clip's tempo to its own attacks, instead of trusting a warp marker.

Ableton's warp markers record the tempo Live *thought* the clip was at when it
was recorded. That is a guess, and on a real job it was 5.7% wrong (86 BPM for
a clip actually played at 81.33), which pushed every bar line progressively out
of place and was then explained away as the player's timing wobble.

So measure it. For each candidate tempo, lay a grid of `--div` divisions per
beat, search the phase offset, and score how much onset energy lands on grid
lines. The tempo whose grid the attacks actually sit on wins, and the printed
margin over the runner-up says how much to trust it.

    python tempo_fit.py "clip (mono).wav" --min 70 --max 100 --div 2
    python tempo_fit.py CLIP.wav --candidates 81.3253,86,120 --div 2
"""
from __future__ import annotations

import argparse
import json

import librosa
import numpy as np


def onset_env(y, sr, hop=256):
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, aggregate=np.median)
    return env / (env.max() or 1.0), librosa.times_like(env, sr=sr, hop_length=hop)


def score_tempo(env, times, bpm, div, dur, tol=0.035, phases=48):
    """Best onset energy captured by a grid at this tempo, over all phases."""
    step = 60.0 / bpm / div
    best, best_phase = -1.0, 0.0
    for k in range(phases):
        phase = k * step / phases
        total, n = 0.0, 0
        t = phase
        while t < dur:
            band = (times >= t - tol) & (times <= t + tol)
            if band.any():
                total += float(env[band].max())
                n += 1
            t += step
        if n:
            mean = total / n
            if mean > best:
                best, best_phase = mean, phase
    return best, best_phase


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav")
    ap.add_argument("--min", type=float, default=70.0)
    ap.add_argument("--max", type=float, default=100.0)
    ap.add_argument("--step", type=float, default=0.25)
    ap.add_argument("--candidates", default="", help="comma-separated tempos to report explicitly")
    ap.add_argument("--div", type=int, default=2, help="grid divisions per beat (2 = eighths)")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    y, sr = librosa.load(args.wav, sr=None, mono=True)
    env, times = onset_env(y, sr)
    dur = len(y) / sr

    grid = np.arange(args.min, args.max + 1e-9, args.step)
    scored = [(float(b), *score_tempo(env, times, float(b), args.div, dur)) for b in grid]
    scored.sort(key=lambda r: -r[1])
    best_bpm, best_score, best_phase = scored[0]

    # runner-up that is not a near-neighbour of the winner, so the margin means something
    runner = next((r for r in scored[1:] if abs(r[0] - best_bpm) > 2.0), scored[1])

    print(f"# {args.wav}  ({dur:.2f}s, grid = 1/{args.div} beat)")
    print(f"best fit       {best_bpm:8.3f} BPM   score {best_score:.4f}  phase {best_phase * 1000:.0f}ms")
    print(f"runner-up      {runner[0]:8.3f} BPM   score {runner[1]:.4f}   "
          f"(margin {100 * (best_score - runner[1]) / runner[1]:+.1f}%)")
    print("\ntop 8 candidates:")
    for b, s, _ in scored[:8]:
        print(f"   {b:8.3f} BPM  {s:.4f}  {'#' * int(s * 50)}")

    named = []
    if args.candidates:
        print("\nnamed candidates:")
        for c in args.candidates.split(","):
            b = float(c)
            s, ph = score_tempo(env, times, b, args.div, dur)
            named.append({"bpm": b, "score": round(s, 4)})
            rel = 100 * (s - best_score) / best_score
            print(f"   {b:8.3f} BPM  {s:.4f}  ({rel:+.1f}% vs best)")

    if args.json:
        json.dump({"wav": args.wav, "best_bpm": best_bpm, "best_score": round(best_score, 4),
                   "phase_s": round(best_phase, 4), "runner_up": {"bpm": runner[0], "score": round(runner[1], 4)},
                   "named": named, "div": args.div}, open(args.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
