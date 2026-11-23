#!/usr/bin/env python3
"""Per-grid-slot fundamental estimation for distorted guitar, with fretting.

Monophonic pitch trackers (pYIN, CREPE-style) return "unvoiced" on a wall of
tremolo-picked distorted guitar. This script instead computes a constant-Q
transform, sums harmonic energy back onto each candidate fundamental
(librosa.salience), averages it per rhythmic grid slot, and prints the top
fundamentals per slot with string/fret candidates for a given tuning.

    python riff_salience.py RIFF.wav --bpm 120 --tuning C1,G1,C2,F2,A#2,D#3,G3,C4
    python riff_salience.py RIFF.wav --bpm 120 --png salience.png --json slots.json
    python riff_salience.py RIFF.wav --bpm 120 --assert 1.1.2:A#3 --assert 3.3.1:D4

Also prints the long-term spectrum peaks and flags peaks that are the
difference of two stronger peaks (distortion intermodulation) - those are
not played notes even though they sit near a low open string.
"""
from __future__ import annotations

import argparse
import json
import sys

import librosa
import numpy as np


def parse_tuning(s: str) -> list[tuple[str, float]]:
    names = [n.strip().replace("♯", "#").replace("♭", "b") for n in s.split(",") if n.strip()]
    # low to high on input; string 1 is the highest
    return [(f"{len(names)-i} {n}", float(librosa.note_to_hz(n))) for i, n in enumerate(names)]


def positions(hz: float, tuning, max_fret=24, n=3) -> str:
    out = []
    for label, open_hz in tuning:
        fret = int(round(12 * np.log2(hz / open_hz)))
        if 0 <= fret <= max_fret:
            out.append((fret, f"str{label.split()[0]}:{fret}"))
    out.sort()
    return "/".join(p[1] for p in out[:n])


def note_name(hz: float) -> str:
    return librosa.midi_to_note(int(round(librosa.hz_to_midi(hz)))).replace("♯", "#")


def cents_off(hz: float) -> float:
    midi = float(librosa.hz_to_midi(hz))
    return (midi - round(midi)) * 100


def drop_octave_duplicates(peaks, s, freqs, ratio=0.5, tol_cents=40):
    """Drop a peak when a peak one octave below carries at least `ratio` of its
    salience. A real fundamental f also lights up 2f (its even harmonics are
    2f's harmonics), so the higher peak is usually an octave error, not a
    played note. A genuine octave dyad is collapsed too; check the long-term
    spectrum if that matters."""
    keep = []
    for j in peaks:
        f = freqs[j]
        below = [k for k in peaks if abs(1200 * np.log2(freqs[k] * 2 / f)) <= tol_cents]
        if any(s[k] >= ratio * s[j] for k in below):
            continue
        keep.append(j)
    return keep


def analyze(y, sr, bpm, grid, bars_per_meter, offset_s, fmin_hz, fmax_hz, top, bar_offset, tuning, collapse_octaves=False, on_grid_only=True, tune_cents=0.0):
    shift = 2 ** (-tune_cents / 1200.0)  # a guitar N cents sharp: divide measured Hz by 2^(N/1200) to land on the grid
    hop = 512
    # Put the CQT bins on the guitar's actual grid: with the lowest bin at C1
    # raised by the offset, every fretted note falls on a bin centre instead of
    # straddling two, so peaks keep their full height.
    fmin = librosa.note_to_hz("C1") / shift
    bpo = 36
    n_bins = 6 * bpo
    C = np.abs(librosa.cqt(y, sr=sr, hop_length=hop, fmin=fmin, n_bins=n_bins, bins_per_octave=bpo))
    freqs = librosa.cqt_frequencies(n_bins, fmin=fmin, bins_per_octave=bpo)
    sal = librosa.salience(C, freqs=freqs, harmonics=[1, 2, 3, 4, 5], weights=[1, 0.8, 0.6, 0.5, 0.4], fill_value=0)
    times = librosa.times_like(sal, sr=sr, hop_length=hop)
    slot_len = 60.0 / bpm * bars_per_meter / grid  # seconds per grid slot
    n_slots = int((times[-1] - offset_s) / slot_len)
    rng = (freqs >= fmin_hz) & (freqs <= fmax_hz)
    ref = float(np.max(sal)) if np.max(sal) > 0 else 1.0
    rows = []
    for i in range(n_slots):
        t0 = offset_s + i * slot_len
        m = (times >= t0) & (times < t0 + slot_len)
        if not m.any():
            continue
        s = sal[:, m].mean(axis=1)
        idx = np.where(rng)[0]
        peaks = [j for j in idx[1:-1] if s[j] > s[j - 1] and s[j] >= s[j + 1]]
        if on_grid_only:
            # A tuned guitar's fundamentals land on the 0-cent bin of the
            # 3-bins-per-semitone CQT; intermodulation junk lands on any bin,
            # so dropping the +-33-cent bins removes two thirds of the junk
            # and none of the played notes (assuming the guitar is within
            # ~20 cents of A440 - pass --all-peaks otherwise).
            peaks = [j for j in peaks if abs(cents_off(freqs[j] * shift)) <= 20]
        if collapse_octaves:
            peaks = drop_octave_duplicates(peaks, s, freqs)
        peaks.sort(key=lambda j: -s[j])
        peaks = peaks[:top]
        per_bar = grid
        bar = bar_offset + i // per_bar
        beat = (i % per_bar) // (grid // bars_per_meter) + 1
        sub = i % (grid // bars_per_meter) + 1
        cands = []
        for j in peaks:
            hz = float(freqs[j]) * shift
            midi = float(librosa.hz_to_midi(hz))
            cands.append(
                {
                    "note": note_name(hz),
                    "hz": round(hz, 1),
                    "cents": int(round((midi - round(midi)) * 100)),
                    "db": round(float(20 * np.log10(s[j] / ref + 1e-12)), 1),
                    "frets": positions(hz, tuning),
                }
            )
        rows.append({"slot": f"{bar}.{beat}.{sub}", "t": round(t0, 3), "candidates": cands})
    return rows


def long_term_peaks(y, sr, fmin_hz=25, fmax_hz=800, floor_db=-35):
    n_fft = 8192
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=1024))
    f = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    avg = S.mean(axis=1)
    db = librosa.amplitude_to_db(avg, ref=np.max)
    m = (f >= fmin_hz) & (f <= fmax_hz)
    idx = np.where(m)[0]
    peaks = [j for j in idx[1:-1] if avg[j] > avg[j - 1] and avg[j] >= avg[j + 1] and db[j] > floor_db]
    peaks.sort(key=lambda j: -avg[j])
    out = [(float(f[j]), float(db[j])) for j in peaks[:20]]
    # Intermodulation flag: a played note sits within a few cents of equal
    # temperament (the guitar is tuned); a distortion difference tone sits
    # wherever the arithmetic puts it. Flag a peak only when it is BOTH more
    # than 20 cents off the nearest note AND equal (within 3 Hz) to the
    # difference of two other peaks.
    flagged = []
    for hz, d in out:
        midi = librosa.hz_to_midi(hz)
        cents = (midi - round(midi)) * 100
        if abs(cents) <= 20:
            continue
        for a, _ in out:
            for b, _ in out:
                if a > b and abs((a - b) - hz) <= 3.0:
                    flagged.append((hz, a, b))
                    break
            else:
                continue
            break
    return out, flagged


def estimate_tune_offset(y, sr, max_abs_cents=50):
    """Global tuning offset (cents sharp of A440) from the strongest long-term
    spectral peaks: the circular median of their cents-off-grid values. A
    tuned guitar gives ~0; a take recorded 45 cents sharp gives ~45."""
    peaks, _ = long_term_peaks(y, sr, fmin_hz=60, fmax_hz=1200, floor_db=-30)
    if not peaks:
        return 0.0
    cents = np.array([cents_off(hz) for hz, _ in peaks[:12]])
    # circular statistics on a 100-cent circle so +49 and -49 do not average to 0
    ang = cents / 100.0 * 2 * np.pi
    mean_ang = np.arctan2(np.sin(ang).mean(), np.cos(ang).mean())
    est = mean_ang / (2 * np.pi) * 100.0
    # refine with the median of peaks within 25 cents of the circular mean
    close = [c for c in cents if abs(((c - est + 50) % 100) - 50) <= 25]
    if close:
        est = float(np.median([est + (((c - est + 50) % 100) - 50) for c in close]))
    return float(max(-max_abs_cents, min(max_abs_cents, est)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav")
    ap.add_argument("--bpm", type=float, default=0, help="tempo; 0 = estimate with librosa (report it, then rerun fixed)")
    ap.add_argument("--tuning", default="E2,A2,D3,G3,B3,E4", help="open strings low to high, e.g. C1,G1,C2,F2,A#2,D#3,G3,C4")
    ap.add_argument("--grid", type=int, default=16, help="slots per bar (16 = sixteenth notes in 4/4)")
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--offset", type=float, default=0.0, help="seconds from file start to the first downbeat")
    ap.add_argument("--bar-offset", type=int, default=1, help="number to give the first bar (e.g. the arrangement bar)")
    ap.add_argument("--fmin", type=float, default=30.0, help="lowest fundamental to consider, Hz")
    ap.add_argument("--fmax", type=float, default=600.0, help="highest fundamental to consider, Hz")
    ap.add_argument("--top", type=int, default=4, help="candidates per slot; a dyad plus its octave images needs 4")
    ap.add_argument("--all-peaks", action="store_true", help="keep candidates more than 20 cents off equal temperament (guitar not at A440)")
    ap.add_argument("--tune-offset", type=float, default=None, help="cents the guitar is sharp of A440 (negative = flat); shifts the note grid")
    ap.add_argument("--auto-tune", action="store_true", help="estimate --tune-offset from the long-term spectrum and apply it")
    ap.add_argument("--collapse-octaves", action="store_true", help="drop a candidate when a peak one octave below has half its salience (hurts on heavy distortion; off by default)")
    ap.add_argument("--png", help="write a salience spectrogram with bar/beat lines")
    ap.add_argument("--json", help="write per-slot candidates as JSON")
    ap.add_argument("--assert", dest="asserts", action="append", default=[], help="SLOT:NOTE, e.g. 1.1.2:A#3 - NOTE must be among the top candidates of SLOT")
    args = ap.parse_args(argv)

    y, sr = librosa.load(args.wav, sr=44100, mono=True)
    bpm = args.bpm
    if not bpm:
        est, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(np.atleast_1d(est)[0])
        print(f"estimated tempo: {bpm:.2f} BPM (pass --bpm to fix it; grid alignment depends on it)")
    tuning = parse_tuning(args.tuning)
    tune = args.tune_offset if args.tune_offset is not None else 0.0
    if args.auto_tune and args.tune_offset is None:
        tune = estimate_tune_offset(y, sr)
    if args.auto_tune or args.tune_offset is not None:
        print(f"tuning offset applied: {tune:+.0f} cents ({'estimated' if args.auto_tune and args.tune_offset is None else 'given'}); note names below are corrected by it")
    rows = analyze(y, sr, bpm, args.grid, args.beats_per_bar, args.offset, args.fmin, args.fmax, args.top, args.bar_offset, tuning, collapse_octaves=args.collapse_octaves, on_grid_only=not args.all_peaks, tune_cents=tune)

    print(f"# {args.wav}  {len(y)/sr:.2f}s  bpm={bpm:g}  grid={args.grid}/bar  tuning={args.tuning}")
    print("slot       t(s)    top fundamentals: note cents dB [string:fret]")
    for r in rows:
        desc = " | ".join(f"{c['note']:4s}{c['cents']:+4d} {c['db']:6.1f}dB [{c['frets']}]" for c in r["candidates"])
        print(f"{r['slot']:9s} {r['t']:7.2f}  {desc}")

    # per-beat summary: notes that appear in the top-2 of at least half the beat's slots
    print("\nper-beat sounding notes (in the top-2 of at least half the slots; first = strongest):")
    per_beat: dict[str, list[list[str]]] = {}
    for r in rows:
        key = ".".join(r["slot"].split(".")[:2])
        per_beat.setdefault(key, []).append([c["note"] for c in r["candidates"][:2]])
    for key, slot_notes in per_beat.items():
        counts: dict[str, int] = {}
        for names in slot_notes:
            for n in names:
                counts[n] = counts.get(n, 0) + 1
        n_slots = len(slot_notes)
        stable = sorted((n for n, c in counts.items() if 2 * c >= n_slots), key=lambda n: -counts[n])
        others = sorted(n for n in counts if n not in stable)
        print(f"  {key:6s} {' + '.join(stable) or '?':12s}  (of {n_slots} slots; also seen: {others})")

    peaks, flagged = long_term_peaks(y, sr)
    print("\nlong-term spectrum peaks (Hz, dB rel. max, note):")
    for hz, d in sorted(peaks):
        tag = ""
        for fh, a, b in flagged:
            if fh == hz:
                tag = f"   <- off-grid and = {a:.0f}-{b:.0f} Hz: distortion difference tone, not a played note"
        print(f"  {hz:7.1f}  {d:6.1f}  {librosa.hz_to_note(hz, cents=True)}{tag}")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"bpm": bpm, "grid": args.grid, "tune_offset_cents": tune, "slots": rows, "long_term_peaks": peaks}, fh, indent=1)
    if args.png:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        hop = 256
        fmin = librosa.note_to_hz("C1")
        bpo = 36
        nb = 6 * bpo
        # Same grid shift as analyze(): bins sit on the guitar's actual pitches,
        # and specshow labels them with the corrected (A440) note names.
        shift = 2 ** (-tune / 1200.0)
        C = np.abs(librosa.cqt(y, sr=sr, hop_length=hop, fmin=fmin / shift, n_bins=nb, bins_per_octave=bpo))
        fr = librosa.cqt_frequencies(nb, fmin=fmin / shift, bins_per_octave=bpo)
        sal = librosa.salience(C, freqs=fr, harmonics=[1, 2, 3, 4], weights=[1, 0.7, 0.5, 0.3], fill_value=0)
        D = librosa.amplitude_to_db(sal, ref=np.max)
        fig, ax = plt.subplots(figsize=(26, 10), dpi=90)
        librosa.display.specshow(D, sr=sr, hop_length=hop, x_axis="time", y_axis="cqt_note", fmin=fmin, bins_per_octave=bpo, ax=ax, vmin=-30, vmax=0, cmap="magma")
        beat_s = 60.0 / bpm
        n_beats = int((len(y) / sr - args.offset) / beat_s) + 1
        for b in range(n_beats):
            ax.axvline(args.offset + b * beat_s, color="cyan" if b % args.beats_per_bar == 0 else "white", alpha=0.6 if b % args.beats_per_bar == 0 else 0.25, lw=1)
            if b % args.beats_per_bar == 0:
                ax.text(args.offset + b * beat_s + 0.02, librosa.note_to_hz("B5"), f"bar {args.bar_offset + b // args.beats_per_bar}", color="cyan", fontsize=11)
        ax.set_title(f"{args.wav} - harmonic salience (CQT), {bpm:g} BPM" + (f", tuning {tune:+.0f} cents corrected" if tune else ""))
        fig.tight_layout()
        fig.savefig(args.png)
        print(f"wrote {args.png}")

    if args.asserts:
        by_slot = {r["slot"]: r for r in rows}
        failed = []
        for a in args.asserts:
            slot, note = a.split(":", 1)
            note = note.replace("♯", "#")
            r = by_slot.get(slot)
            names = [c["note"] for c in r["candidates"]] if r else []
            if note not in names:
                failed.append(f"{slot}: wanted {note}, top candidates were {names}")
        if failed:
            print("ASSERTIONS FAILED:\n  " + "\n  ".join(failed))
            return 1
        print(f"ASSERTIONS PASSED ({len(args.asserts)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
