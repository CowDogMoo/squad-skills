#!/usr/bin/env python3
"""Draw a tab's notes over a constant-Q spectrogram of the recording.

The single most convincing check of a transcription is visual: put every
written note on top of the guitar's own pitch trace and look. A right note sits
on a bright line; a wrong one floats in the dark. It is also the picture to hand
the user, because they can verify it without trusting any metric.

The region is given in arrangement terms - a start offset into the audio file
for the first downbeat, the tempo, and the bar number that downbeat carries -
so the grid lines are the bars, beats and 32nds the tab is written on.

Notes come from a MIDI file (the tab's export, already on the same timeline as
the region) or from a spec file, one note per line:

    # bar  beat_start  beat_len  midi   [label]
    36     3.0         0.125     74     19
    36     3.125       0.25      75     20h

beat_start is 1-based within the bar (3.0 = beat 3). midi may also be a note
name (D5). The optional label is drawn next to the line (a fret, a technique).

    python overlay_tab.py CLIP.wav --start 0.0 --bpm 120 --bar 36 --bars 2 \
        --spec lick.spec --tuning B0,E1,A1,E2,A2,D3,G3,B3,E4 --png lick.png
    python overlay_tab.py CLIP.wav --start 12.0 --bpm 120 --bar 33 --bars 4 \
        --midi tab.mid --midi-offset-beats 128 --fmin C1 --octaves 4 --png heavy.png

Pass two specs/MIDIs (--compare) to draw a before/after pair stacked, which is
the clearest way to show the user what changed and why.
"""

import argparse
import sys

import librosa
import matplotlib
import numpy as np
import soundfile as sf

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

NAMES = "C C# D D# E F F# G G# A A# B".split()


def note_name(m):
    m = int(round(m))
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def to_midi(tok):
    try:
        return float(tok)
    except ValueError:
        return float(librosa.note_to_midi(tok))


def read_spec(path, beats_per_bar):
    notes = []
    for line in open(path):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        bar, start, length, midi = int(parts[0]), float(parts[1]), float(parts[2]), to_midi(parts[3])
        label = parts[4] if len(parts) > 4 else ""
        beat = (bar - 1) * beats_per_bar + (start - 1)
        notes.append((beat, beat + length, midi, label))
    return notes


def read_midi(path, bpm, offset_beats):
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(path)
    spb = 60.0 / bpm
    out = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            out.append((n.start / spb + offset_beats, n.end / spb + offset_beats, n.pitch, ""))
    return out


def fret_label(m, tuning, max_fret=24):
    """'s3:19' style candidates for a pitch in the given tuning (strings numbered 1 = highest)."""
    if not tuning:
        return ""
    opens = [librosa.note_to_midi(t) for t in tuning]  # low -> high
    n = len(opens)
    c = [f"s{n - i}:{int(m - o)}" for i, o in enumerate(opens) if 0 <= m - o <= max_fret]
    return "/".join(c[-2:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav")
    ap.add_argument("--start", type=float, required=True, help="seconds in the file at the first downbeat shown")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--bar", type=int, required=True, help="bar number of that downbeat")
    ap.add_argument("--bars", type=float, default=1.0, help="how many bars to draw")
    ap.add_argument("--spec", action="append", default=[], help="note spec (repeat with --compare)")
    ap.add_argument("--midi", action="append", default=[], help="tab MIDI (repeat with --compare)")
    ap.add_argument("--midi-offset-beats", type=float, default=0.0,
                    help="beats to add to MIDI times so they land on the arrangement timeline")
    ap.add_argument("--label", action="append", default=[], help="panel title per spec/MIDI, in order")
    ap.add_argument("--compare", action="store_true", help="one panel per spec/MIDI, stacked")
    ap.add_argument("--tuning", default="", help="open strings low to high, to label frets on the y axis")
    ap.add_argument("--fmin", default="C3", help="lowest note shown (C1 for chugs, C4 for leads)")
    ap.add_argument("--octaves", type=float, default=3.0)
    ap.add_argument("--hop", type=int, default=96)
    ap.add_argument("--vmin", type=float, default=-55.0)
    ap.add_argument("--png", required=True)
    a = ap.parse_args()

    bpb = a.beats_per_bar
    spb = 60.0 / a.bpm
    beat0 = (a.bar - 1) * bpb
    span_beats = a.bars * bpb
    pad = 0.25  # beats of context either side

    x, sr = sf.read(a.wav, dtype="float32", always_2d=True)
    x = x.mean(1)
    s0 = a.start - pad * spb
    s1 = a.start + (span_beats + pad) * spb
    lo = int(round(s0 * sr))
    seg = x[max(0, lo): max(0, int(round(s1 * sr)))]
    if lo < 0:
        seg = np.concatenate([np.zeros(-lo, np.float32), seg])
    if len(seg) < sr // 10 or not np.any(seg):
        sys.exit("region is empty or silent - check --start against the clip's sample seconds")

    bpo = 36
    nb = int(round(a.octaves * 12)) * 3
    fmin_hz = librosa.note_to_hz(a.fmin)
    C = np.abs(librosa.cqt(seg, sr=sr, hop_length=a.hop, fmin=fmin_hz, n_bins=nb,
                           bins_per_octave=bpo, filter_scale=0.6))
    D = librosa.amplitude_to_db(C, ref=C.max())
    m0 = librosa.note_to_midi(a.fmin)
    t_beats0 = beat0 - pad
    ext = [t_beats0, t_beats0 + D.shape[1] * a.hop / sr / spb, m0 - 1 / 3, m0 + nb / 3 - 1 / 3]

    sets = []
    for p in a.spec:
        sets.append(read_spec(p, bpb))
    for p in a.midi:
        sets.append(read_midi(p, a.bpm, a.midi_offset_beats))
    if not sets:
        sets = [[]]
    if not a.compare:
        sets = [[n for s in sets for n in s]]
    labels = a.label + [""] * len(sets)

    tuning = [t.strip() for t in a.tuning.split(",") if t.strip()]
    fig, axs = plt.subplots(len(sets), 1, figsize=(max(14, a.bars * 9), 6.5 * len(sets)), squeeze=False)
    for ax, notes, lab in zip(axs[:, 0], sets, labels):
        ax.imshow(D, origin="lower", aspect="auto", extent=ext, cmap="magma", vmin=a.vmin, vmax=0)
        k = 0.0
        while k <= span_beats + 1e-9:
            b = beat0 + k
            on_bar = abs(k % bpb) < 1e-6
            on_beat = abs(k - round(k)) < 1e-6
            ax.axvline(b, color="w" if on_beat else "0.55",
                       lw=1.6 if on_bar else (0.8 if on_beat else 0.25), alpha=0.9)
            if on_bar:
                ax.text(b + 0.03, ext[3] - 1.2, f"bar {a.bar + int(round(k / bpb))}", color="w", fontsize=12)
            k += 0.125  # 32nd notes in 4/4
        for st, en, m, tag in notes:
            if en < ext[0] or st > ext[1]:
                continue
            ax.plot([st + 0.01, en - 0.01], [m, m], color="cyan", lw=3.5, alpha=0.85)
            if tag:
                ax.text(st + 0.01, m + 0.35, tag, color="cyan", fontsize=11)
        yt = np.arange(int(np.ceil(ext[2])), int(ext[3]))
        ax.set_yticks(yt)
        ax.set_yticklabels([f"{note_name(v)} {fret_label(v, tuning)}".strip() for v in yt], fontsize=8)
        ax.grid(axis="y", color="gray", lw=0.3, alpha=0.4)
        ax.set_xlim(ext[0], ext[1])
        ax.set_xlabel("arrangement beats (grid = 32nds)")
        ax.set_title(lab or a.wav, fontsize=12)
    plt.tight_layout()
    plt.savefig(a.png, dpi=60)
    print(f"wrote {a.png}  ({len(sets)} panel(s), bars {a.bar}-{a.bar + a.bars - 1:g})")


if __name__ == "__main__":
    main()
