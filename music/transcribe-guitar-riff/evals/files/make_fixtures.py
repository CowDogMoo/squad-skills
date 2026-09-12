#!/usr/bin/env python3
"""Generate a deterministic distorted tremolo-dyad riff with a known score.

Writes into the given directory:
  riff.wav      - 4 bars at 120 BPM, straight sixteenths, distorted (tanh
                  waveshaper + tone filter), an A#3 pedal with an upper voice
                  that moves F#4 -> F4 -> D4, then the pedal drops to A3+D4.
                  Same shape as the real riff this skill was built on.
  riff.spec     - the ground-truth spec in riff_midi.py format
  expected.json - per-sixteenth expected sounding note names (bar 1 = first bar)

riff_salience.py must recover every expected note within its top-3
candidates on every slot (positive control), and compare_rolls.py must
reject a one-note-different spec (negative control). scripts/selftest.py
runs both.

Deps: numpy soundfile librosa
  uv run --with numpy --with soundfile --with librosa make_fixtures.py <out-dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

BPM = 120.0
SR = 44100
BEATS_PER_BAR = 4

# (bar, start_beat, end_beat, notes)  - 1-based beats, end exclusive
SPEC = [
    (1, 1.0, 2.0, ["A#3"]),
    (1, 2.0, 5.0, ["A#3", "F#4"]),
    (2, 1.0, 2.0, ["A#3"]),
    (2, 2.0, 3.5, ["A#3", "F4"]),
    (2, 3.5, 5.0, ["A#3"]),
    (3, 1.0, 2.25, ["A#3"]),
    (3, 2.25, 4.25, ["A#3", "D4"]),
    (3, 4.25, 5.0, ["A#3"]),
    (4, 1.0, 2.0, ["A3"]),
    (4, 2.0, 5.0, ["A3", "D4"]),
]


RNG = np.random.default_rng(20260912)


def pluck(f0: float, dur: float, sr: int = SR) -> np.ndarray:
    """Eight decaying harmonics, phase reset by the pick, ringing on under the
    next pick like a real string. Two fixture mistakes to avoid: a perfectly
    periodic tremolo (every pick exactly 8 Hz apart) splits low fundamentals
    into +-8 Hz sidebands the CQT resolves as off-grid bins, and random
    phase per pick with hard-cut notes cancels the fundamental across the
    CQT window - both fail for reasons no real recording reproduces. Timing
    jitter of a few ms is what a hand does and is enough."""
    t = np.arange(int(dur * sr)) / sr
    tone = np.zeros_like(t)
    for k in range(1, 9):
        inharm = 1 + 0.0004 * k * k
        tone += (0.6 ** (k - 1)) * np.sin(2 * np.pi * f0 * k * inharm * t)
    env = np.minimum(1.0, t / 0.003) * np.exp(-t / 0.35)
    return tone * env * RNG.uniform(0.85, 1.0)


def render(spec, sr: int = SR) -> np.ndarray:
    spb = 60.0 / BPM
    n_bars = max(b for b, *_ in spec)
    total = int(n_bars * BEATS_PER_BAR * spb * sr) + sr // 2
    y = np.zeros(total)
    six = spb / 4
    for bar, b0, b1, notes in spec:
        t0 = ((bar - 1) * BEATS_PER_BAR + (b0 - 1)) * spb
        t1 = ((bar - 1) * BEATS_PER_BAR + (b1 - 1)) * spb
        t = t0
        while t < t1 - 1e-9:
            jitter = RNG.uniform(-0.004, 0.004)  # human timing, seconds
            for n in notes:
                p = pluck(float(librosa.note_to_hz(n)), 0.4)
                i0 = max(0, int(round((t + jitter) * sr)))
                y[i0 : i0 + len(p)] += p[: max(0, total - i0)]
            t += six
    # amp-style distortion: pre-emphasis, hard drive, tone stack, cab-ish lowpass
    y = y / (np.abs(y).max() + 1e-9)
    y = np.tanh(4.0 * y)
    # two-pole lowpass ~3.5 kHz (cab-like rolloff) and highpass ~70 Hz
    a = np.exp(-2 * np.pi * 3500 / sr)
    lp = y
    for _ in range(2):
        out = np.zeros_like(lp)
        acc = 0.0
        for i, v in enumerate(lp):
            acc = (1 - a) * v + a * acc
            out[i] = acc
        lp = out
    b = np.exp(-2 * np.pi * 70 / sr)
    hp = np.zeros_like(lp)
    prev_in = 0.0
    prev_out = 0.0
    for i, v in enumerate(lp):
        prev_out = b * (prev_out + v - prev_in)
        prev_in = v
        hp[i] = prev_out
    return hp / (np.abs(hp).max() + 1e-9) * 0.7


def expected_slots(spec):
    out = {}
    for bar, b0, b1, notes in spec:
        s0 = int(round((b0 - 1) * 4))
        s1 = int(round((b1 - 1) * 4))
        for s in range(s0, s1):
            key = f"{bar}.{s // 4 + 1}.{s % 4 + 1}"
            out.setdefault(key, [])
            out[key].extend(notes)
    return out


def main(out_dir: str) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    y = render(SPEC)
    sf.write(out / "riff.wav", y, SR, subtype="PCM_24")
    with open(out / "riff.spec", "w") as fh:
        fh.write("# bar start end notes   (ground truth for riff.wav)\n")
        for bar, b0, b1, notes in SPEC:
            fh.write(f"{bar} {b0} {b1} {' '.join(notes)}\n")
    with open(out / "expected.json", "w") as fh:
        json.dump({"bpm": BPM, "slots": expected_slots(SPEC)}, fh, indent=1)
    print(f"wrote {out/'riff.wav'} ({len(y)/SR:.2f}s), riff.spec, expected.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "fixtures"))
