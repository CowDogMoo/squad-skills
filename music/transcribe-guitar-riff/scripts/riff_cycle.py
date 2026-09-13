#!/usr/bin/env python3
"""Find the repeating unit of a riff, average every repetition, read it once.

This is the step that separates a tab from a pitch log. A riff is written once
and played N times; reading each bar independently produces N slightly different
bars, each individually defensible and collectively unplayable. Averaging the
spectral evidence across the repetitions instead raises the signal-to-noise
ratio by about sqrt(N), and what comes out is one clean cycle to stamp down.

Three passes:

1. Per-sixteenth harmonic-comb salience over a chosen band, per channel.
2. Cycle detection: correlate the slot-feature sequence against itself at every
   plausible bar lag and take the lag whose self-similarity is highest AND whose
   within-cycle variance drops most. Both are reported so a weak cycle is
   visible rather than assumed.
3. Fold: average the salience of all slots that share a cycle position, then
   read the pitch once per position.

    python riff_cycle.py CLIP.wav --bpm 120 --origin-beat 64 --bars 21,36 \
        --tuning C1,G1,C2,F2,A#2,D#3,G3,C4 --band 40,110

Outputs the cycle as a spec fragment on stdout and the full evidence as JSON.
"""
from __future__ import annotations

import argparse
import json
import sys

import librosa
import numpy as np
import soundfile as sf

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
HARMONICS = [1, 2, 3, 4, 5, 6, 7, 8]
# 3f and 5f carry the octave decision; 1f is down-weighted because a cab eats it.
WEIGHTS = [0.30, 0.90, 1.30, 0.80, 1.10, 0.55, 0.45, 0.30]


def name_of(midi: int) -> str:
    return f"{NAMES[midi % 12]}{midi // 12 - 1}"


def comb_salience(y, sr, f0s, freqs, spec_cols):
    """Comb score for every candidate f0, for one framed spectrum column set."""
    scores = np.zeros((len(f0s), spec_cols.shape[1]))
    for k, w in zip(HARMONICS, WEIGHTS):
        idx = np.clip(np.searchsorted(freqs, f0s * k), 1, len(freqs) - 2)
        band = np.maximum.reduce([spec_cols[idx - 1], spec_cols[idx], spec_cols[idx + 1]])
        scores += w * band
    return scores


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--origin-beat", type=float, default=0.0)
    ap.add_argument("--bars", required=True, help="lo,hi arrangement bars to fold")
    ap.add_argument("--band", default="40,110", help="fmin,fmax Hz for the comb search")
    ap.add_argument("--grid", type=int, default=4, help="slots per beat")
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--max-cycle", type=int, default=8, help="longest cycle to consider, in bars")
    ap.add_argument("--cycle", type=int, default=0, help="force a cycle length instead of detecting")
    ap.add_argument("--tuning", default="C1,G1,C2,F2,A#2,D#3,G3,C4")
    ap.add_argument("--json", default="")
    ap.add_argument("--min-rest-db", type=float, default=-45.0)
    args = ap.parse_args()

    lo_bar, hi_bar = (int(x) for x in args.bars.split(","))
    fmin, fmax = (float(x) for x in args.band.split(","))
    y, sr = sf.read(args.wav, always_2d=True)
    channels = y.shape[1]
    n_fft, hop = 16384, 512
    f0s = np.exp(np.linspace(np.log(fmin), np.log(fmax), 500))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    specs = []
    for ch in range(channels):
        S = np.abs(librosa.stft(y[:, ch], n_fft=n_fft, hop_length=hop, window="hann"))
        specs.append(np.log1p(S / (S.max() + 1e-9) * 1000))
    times = librosa.frames_to_time(np.arange(specs[0].shape[1]), sr=sr, hop_length=hop)

    spb = 60.0 / args.bpm
    slot_beats = 1.0 / args.grid
    slots_per_bar = args.beats_per_bar * args.grid
    first_beat = (lo_bar - 1) * args.beats_per_bar
    n_slots = (hi_bar - lo_bar + 1) * slots_per_bar

    # Pass 1 - per-slot comb salience and level, averaged over channels.
    sal = np.zeros((n_slots, len(f0s)))
    rms = np.zeros(n_slots)
    for s in range(n_slots):
        beat = first_beat + s * slot_beats
        t0 = (beat - args.origin_beat) * spb
        t1 = t0 + slot_beats * spb
        seg = y[int(t0 * sr): int(t1 * sr)]
        rms[s] = 20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9) if len(seg) else -99
        mask = (times >= t0) & (times < t1)
        if not mask.any():
            continue
        acc = np.zeros(len(f0s))
        for ch in range(channels):
            acc += comb_salience(y, sr, f0s, freqs, specs[ch][:, mask]).mean(axis=1)
        sal[s] = acc / channels

    # Discretise each slot to a played pitch or a rest BEFORE looking for the
    # cycle. Comparing raw salience vectors scores ~0.99 for every lag, because
    # they share a broad spectral shape; what actually distinguishes one riff
    # position from another is which note is sounding, so compare that.
    def slot_pitch(vec, level):
        if level < args.min_rest_db:
            return None
        peaks = [i for i in np.argsort(-vec)[:40]
                 if vec[i] >= vec[max(i - 1, 0)] and vec[i] >= vec[min(i + 1, len(vec) - 1)]]
        best = peaks[0] if peaks else int(np.argmax(vec))
        return int(round(librosa.hz_to_midi(float(f0s[best]))))

    seq = [slot_pitch(sal[s], rms[s]) for s in range(n_slots)]

    # Pass 2 - cycle detection over whole-bar lags.
    n_bars = hi_bar - lo_bar + 1
    cycle_scores = {}
    for c in range(1, min(args.max_cycle, n_bars // 2) + 1):
        lag = c * slots_per_bar
        pairs = [(seq[s], seq[s + lag]) for s in range(n_slots - lag)]
        match = sum(1 for a, b in pairs if a == b) / len(pairs) if pairs else 0.0
        # how often each cycle position agrees with its own instances
        agree = []
        for pos in range(lag):
            members = [seq[s] for s in range(pos, n_slots, lag)]
            if len(members) > 1:
                top = max(set(members), key=members.count)
                agree.append(members.count(top) / len(members))
        cycle_scores[c] = {
            "slot_match": round(match, 4),
            "position_agreement": round(float(np.mean(agree)), 4) if agree else 0.0,
            "instances": n_bars // c,
        }
    if args.cycle:
        cycle = args.cycle
    else:
        # Prefer the lag whose slots actually repeat. Require a longer cycle to
        # beat a shorter one by a real margin, so 8 bars is not chosen over 4
        # just because it has fewer instances to disagree.
        best_c, best_v = 1, cycle_scores[1]["slot_match"]
        for c in sorted(cycle_scores):
            if cycle_scores[c]["slot_match"] > best_v + 0.02:
                best_c, best_v = c, cycle_scores[c]["slot_match"]
        cycle = best_c

    # Pass 3 - fold every repetition onto one cycle and read it once.
    cycle_slots = cycle * slots_per_bar
    folded = np.zeros((cycle_slots, len(f0s)))
    folded_rms = np.zeros(cycle_slots)
    counts = np.zeros(cycle_slots)
    for s in range(n_slots):
        pos = s % cycle_slots
        folded[pos] += sal[s]
        folded_rms[pos] += rms[s]
        counts[pos] += 1
    folded /= counts[:, None]
    folded_rms /= counts

    open_midi = [librosa.note_to_midi(t) for t in args.tuning.split(",")]
    reading = []
    for pos in range(cycle_slots):
        if folded_rms[pos] < args.min_rest_db:
            reading.append({"pos": pos, "note": None, "rms": round(float(folded_rms[pos]), 1)})
            continue
        score = folded[pos]
        peaks = [i for i in np.argsort(-score)[:40]
                 if score[i] >= score[max(i - 1, 0)] and score[i] >= score[min(i + 1, len(score) - 1)]]
        best = peaks[0] if peaks else int(np.argmax(score))
        hz = float(f0s[best])
        midi = int(round(librosa.hz_to_midi(hz)))
        cents = int(round((librosa.hz_to_midi(hz) - midi) * 100))
        # agreement across the instances that made this position
        votes = []
        for s in range(pos, n_slots, cycle_slots):
            p = [i for i in np.argsort(-sal[s])[:40]
                 if sal[s][i] >= sal[s][max(i - 1, 0)] and sal[s][i] >= sal[s][min(i + 1, len(score) - 1)]]
            if p:
                votes.append(int(round(librosa.hz_to_midi(float(f0s[p[0]])))))
        agree = votes.count(midi) / len(votes) if votes else 0.0
        reading.append({
            "pos": pos, "bar_in_cycle": pos // slots_per_bar + 1,
            "beat": (pos % slots_per_bar) / args.grid + 1,
            "note": name_of(midi), "midi": midi, "hz": round(hz, 2), "cents": cents,
            "instance_agreement": round(agree, 3), "instances": len(votes),
            "rms": round(float(folded_rms[pos]), 1),
        })

    print(f"# cycle detection over bars {lo_bar}-{hi_bar}", file=sys.stderr)
    for c, v in sorted(cycle_scores.items()):
        mark = "  <- chosen" if c == cycle else ""
        print(f"#   {c} bar(s): {v['slot_match'] * 100:5.1f}% of slots repeat at this lag, "
              f"position agreement {v['position_agreement'] * 100:5.1f}%, "
              f"{v['instances']} instances{mark}", file=sys.stderr)
    weak = [r for r in reading if r["note"] and r["instance_agreement"] < 0.5]
    print(f"# {len(weak)} of {cycle_slots} slots disagree across instances "
          f"(these are the ones to check by ear)", file=sys.stderr)

    # Emit one cycle as spec lines, merging consecutive identical pitches and
    # splitting any note that crosses a bar line (a spec line is per bar, so
    # "3.50 7.00" would silently mean nothing).
    lines, i = [], 0
    while i < cycle_slots:
        r = reading[i]
        if r["note"] is None:
            i += 1
            continue
        j = i
        while j + 1 < cycle_slots and reading[j + 1]["note"] == r["note"]:
            j += 1
        start_beat = i * slot_beats
        end_beat = (j + 1) * slot_beats
        while start_beat < end_beat:
            bar = int(start_beat // args.beats_per_bar) + 1
            bar_end = bar * args.beats_per_bar
            piece_end = min(end_beat, bar_end)
            lines.append(
                f"{bar} {start_beat - (bar - 1) * args.beats_per_bar + 1:.2f} "
                f"{piece_end - (bar - 1) * args.beats_per_bar + 1:.2f} {r['note']}"
            )
            start_beat = piece_end
        i = j + 1
    print(f"# one cycle = {cycle} bar(s); stamp it across bars {lo_bar}-{hi_bar}")
    for line in lines:
        print(line)

    if args.json:
        json.dump({
            "bars": [lo_bar, hi_bar], "cycle_bars": cycle,
            "cycle_scores": cycle_scores, "reading": reading,
            "weak_slots": len(weak), "cycle_slots": cycle_slots,
        }, open(args.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
