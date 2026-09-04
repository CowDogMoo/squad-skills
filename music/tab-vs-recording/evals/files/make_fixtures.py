#!/usr/bin/env python3
"""Generate deterministic fixtures for compare_tab.py's controls.

Writes into the given directory:
  tab.mid      - the "tab": an E-minor power-chord riff with a single-note line
  perf.mid     - the "performance": the same music, tempo-stretched 1.13x and
                 shifted 0.4 s (doubles as the ground-truth transcription)
  perf.wav     - sine rendition of perf.mid at 22050 Hz (no soundfont needed)
  wrongtab.mid - a deliberately different piece (Ab-major triplet arpeggios)

A correct pipeline scores tab.mid vs perf.wav near F1 1.0 and wrongtab.mid
far lower with a much worse DTW cost; the evals and the repo's gate checks
rely on exactly that separation.

Deps: numpy soundfile pretty_midi
  uv run --with numpy --with soundfile --with pretty_midi make_fixtures.py <out-dir>
"""

import sys
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf


def render(pm, fs=22050):
    """Pluck-like render: four decaying harmonics with a 5 ms attack ramp and
    exponential decay. Pure sines have no transients and smear the CQT at
    guitar pitches, which no real recording does; this stays realistic."""
    audio = np.zeros(int((pm.get_end_time() + 0.5) * fs))
    for inst in pm.instruments:
        for n in inst.notes:
            f0 = 440.0 * 2 ** ((n.pitch - 69) / 12)
            t = np.arange(int((n.end - n.start) * fs)) / fs
            tone = sum((0.6**k) * np.sin(2 * np.pi * f0 * (k + 1) * t) for k in range(4))
            env = np.minimum(1.0, t / 0.005) * np.exp(-t / 0.5)
            i0 = int(n.start * fs)
            audio[i0:i0 + len(t)] += tone * env * (n.velocity / 127.0)
    return audio / (np.abs(audio).max() + 1e-9) * 0.9


def build(events, program=27):
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=program)
    for start, dur, pitches in events:
        for p in pitches if isinstance(pitches, list) else [pitches]:
            inst.notes.append(pretty_midi.Note(velocity=96, pitch=p,
                                               start=start, end=start + dur))
    pm.instruments.append(inst)
    return pm


def melody_a():
    events, t, beat = [], 0.0, 60.0 / 110.0
    e5, g5, d5 = [40, 47], [43, 50], [38, 45]
    line = [52, 55, 57, 59, 62, 59, 57, 55]
    for _ in range(4):
        for chord in (e5, e5, g5, d5):
            events.append((t, beat * 0.9, chord))
            t += beat
        for p in line:
            events.append((t, beat * 0.45, p))
            t += beat * 0.5
    events.append((t, beat * 2, [40, 47, 52]))
    return events


def melody_b():
    events, t, beat = [], 0.0, 60.0 / 96.0
    arps = [[44, 48, 51], [46, 49, 53], [48, 51, 56], [51, 56, 60]]
    for bar in range(6):
        arp = arps[bar % 4]
        for p in arp + arp[::-1]:
            events.append((t, beat / 3 * 0.9, p))
            t += beat / 3
        events.append((t, beat * 0.9, arp[0] - 12))
        t += beat
    return events


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: make_fixtures.py <out-dir>")
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)

    tab = build(melody_a())
    tab.write(str(out / "tab.mid"))
    build(melody_b()).write(str(out / "wrongtab.mid"))

    perf = build(melody_a())
    end = perf.get_end_time()
    perf.adjust_times(np.array([0.0, end]), np.array([0.4, 0.4 + end * 1.13]))
    perf.write(str(out / "perf.mid"))
    sf.write(str(out / "perf.wav"), render(perf).astype(np.float32), 22050)
    print(f"fixtures written to {out}")


if __name__ == "__main__":
    main()
