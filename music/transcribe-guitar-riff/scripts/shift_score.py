#!/usr/bin/env python3
"""Frame-level pitch agreement between a tab and the recording, with controls.

A tab note is right when the guitar is sounding that pitch for the time the note
is written. So track the recording's pitch frame by frame (pYIN), lay the tab's
sounding pitch over the same frames, and count the frames where they agree to
within half a semitone. On its own that number means little - so the script also
scores the SAME notes shifted -1/+1 semitone and -1/+1 octave. A real match
beats every shifted copy by a wide margin (77-88% against 1-21% on two real
jobs); a tab that only scores near its controls is not tracking the audio.

Why frame-level over the whole timeline, not per note: scoring each note on the
middle of its own window throws away most of a 32nd note and misjudged a fast
lick the wrong way round on a real job (the worse version scored higher).

Settings that mattered in practice:
  * pYIN frame 1024, hop 64. Hop 32 left almost every frame unvoiced on a
    distorted lead, which made every candidate look perfect on a handful of frames.
  * The band and fmin decide the octave pYIN can see. On a distorted bounce,
    fmin 150 Hz read a lead an octave low and fmin 300 Hz read it right. Settle
    the octave first (octave_check.py, Basic Pitch) and only then choose fmin;
    the octave-free column shows how much of the score depends on that choice.

Tabs come as a MIDI file or as the overlay_tab.py spec format
(bar beat_start beat_len midi [label]). The region is given the same way as
overlay_tab.py: --start (seconds in the file at the first downbeat), --bpm,
--bar, --bars.

    python shift_score.py LEAD.wav --start 0 --bpm 120 --bar 36 --bars 1 \
        --spec new.spec --require-beats old.spec --fmin 300 --band 280 5000

With --require-beats the script exits 1 unless the candidate scores strictly
higher than the known-bad tab - use it as the gate before shipping a rewrite.
"""

import argparse
import sys

import librosa
import numpy as np
import scipy.signal as ss
import soundfile as sf

from overlay_tab import read_midi, read_spec  # same note formats


def load_notes(path, a):
    if path.lower().endswith((".mid", ".midi")):
        return read_midi(path, a.bpm, a.midi_offset_beats)
    return read_spec(path, a.beats_per_bar)


def track(a):
    x, sr = sf.read(a.wav, dtype="float32", always_2d=True)
    x = x.mean(1)
    spb = 60.0 / a.bpm
    s0, s1 = a.start, a.start + a.bars * a.beats_per_bar * spb
    seg = x[max(0, int(s0 * sr)): int(s1 * sr)]
    if a.band:
        sos = ss.butter(4, a.band, btype="band", fs=sr, output="sos")
        seg = ss.sosfiltfilt(sos, seg).astype(np.float32)
    f0, _, _ = librosa.pyin(seg, fmin=a.fmin, fmax=a.fmax, sr=sr,
                            frame_length=a.frame, hop_length=a.hop, fill_na=np.nan)
    beat0 = (a.bar - 1) * a.beats_per_bar
    t_beats = beat0 + np.arange(len(f0)) * a.hop / sr / spb
    return t_beats, librosa.hz_to_midi(f0)


def agreement(notes, tb, mm, shift=0.0, octave_free=False):
    exp = np.full(len(tb), np.nan)
    for st, en, m, _ in notes:
        exp[(tb >= st) & (tb < en)] = m + shift
    ok = ~np.isnan(exp) & ~np.isnan(mm)
    if not ok.any():
        return float("nan"), 0
    d = mm[ok] - exp[ok]
    if octave_free:
        d = (d + 6) % 12 - 6
    return float(np.mean(np.abs(d) < 0.5)), int(ok.sum())


def row(label, notes, tb, mm):
    base, n = agreement(notes, tb, mm)
    cols = [agreement(notes, tb, mm, s)[0] for s in (-1, 1, -12, 12)]
    of, _ = agreement(notes, tb, mm, octave_free=True)
    pct = lambda v: "  n/a" if np.isnan(v) else f"{v:5.0%}"
    print(f"{label:28s} {pct(base)} | -1st {pct(cols[0])} +1st {pct(cols[1])} | "
          f"-oct {pct(cols[2])} +oct {pct(cols[3])} | octave-free {pct(of)}  ({n} voiced frames)")
    return base


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav")
    ap.add_argument("tab", nargs="?", help="candidate tab (spec or MIDI); or use --spec/--midi")
    ap.add_argument("--spec")
    ap.add_argument("--midi")
    ap.add_argument("--midi-offset-beats", type=float, default=0.0)
    ap.add_argument("--require-beats", help="known-bad tab the candidate must beat; exit 1 if it does not")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--bar", type=int, required=True)
    ap.add_argument("--bars", type=float, default=1.0)
    ap.add_argument("--fmin", type=float, default=150.0)
    ap.add_argument("--fmax", type=float, default=1400.0)
    ap.add_argument("--band", type=float, nargs=2, metavar=("LO", "HI"), help="band-pass before pYIN, Hz")
    ap.add_argument("--frame", type=int, default=1024)
    ap.add_argument("--hop", type=int, default=64)
    a = ap.parse_args()

    cand = a.tab or a.spec or a.midi
    if not cand:
        sys.exit("give a candidate tab (positional, --spec or --midi)")
    tb, mm = track(a)
    voiced = np.mean(~np.isnan(mm))
    print(f"pYIN voiced {voiced:.0%} of frames (fmin {a.fmin:g} Hz, frame {a.frame}, hop {a.hop})")
    if voiced < 0.15:
        print("WARNING: very few voiced frames - scores rest on a sliver of the audio; widen the band/fmin")
    good = row("candidate", load_notes(cand, a), tb, mm)
    if a.require_beats:
        bad = row("known-bad", load_notes(a.require_beats, a), tb, mm)
        if not good > bad:
            print("FAIL: the candidate does not beat the known-bad tab on this check")
            sys.exit(1)
        print("PASS: candidate beats the known-bad tab")


if __name__ == "__main__":
    main()
