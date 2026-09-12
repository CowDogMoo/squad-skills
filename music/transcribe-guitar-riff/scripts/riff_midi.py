#!/usr/bin/env python3
"""Turn a hand-written riff spec into a cleaned MIDI file and Ableton note list.

Spec format, one segment per line (blank lines and # comments ignored):

    bar  start_beat  end_beat  NOTE [NOTE ...]
    1    1.0         2.0       A#3
    1    2.0         5.0       A#3 F#4      # beats are 1-based, end exclusive
    4    1.0         3.0       A3

Beat 5.0 in 4/4 means the end of the bar. Every note in a segment sounds for
the whole segment. Bars are numbered from 1 in the spec; --bar-offset only
changes the labels printed in the table.

    python riff_midi.py riff.spec --bpm 120 --out cleaned.mid
    python riff_midi.py riff.spec --bpm 120 --out cleaned.mid --ableton-json notes.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import librosa
import pretty_midi


def parse_spec(path: str, beats_per_bar: int):
    segs = []
    with open(path) as fh:
        for ln, raw in enumerate(fh, 1):
            # a comment starts at a '#' that begins the line or follows whitespace;
            # the '#' inside A#3 is a sharp, not a comment
            line = re.sub(r"(^|\s)#.*$", "", raw).strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                raise SystemExit(f"{path}:{ln}: need 'bar start end NOTE...', got {raw.rstrip()!r}")
            bar, b0, b1 = int(parts[0]), float(parts[1]), float(parts[2])
            if not (1.0 <= b0 < b1 <= beats_per_bar + 1):
                raise SystemExit(f"{path}:{ln}: beats must satisfy 1 <= start < end <= {beats_per_bar + 1}")
            notes = [int(round(librosa.note_to_midi(n.replace("♯", "#")))) for n in parts[3:]]
            t0 = (bar - 1) * beats_per_bar + (b0 - 1)
            t1 = (bar - 1) * beats_per_bar + (b1 - 1)
            segs.append((t0, t1, notes))
    return segs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--out", required=True, help="MIDI file to write")
    ap.add_argument("--ableton-json", help="also write the note list for the ableton-mcp add_notes_to_clip tool")
    ap.add_argument("--bar-offset", type=int, default=1, help="arrangement bar of spec bar 1 (labels only)")
    ap.add_argument("--velocity", type=int, default=100)
    ap.add_argument("--program", type=int, default=30, help="General MIDI program (30 = distortion guitar)")
    args = ap.parse_args(argv)

    segs = parse_spec(args.spec, args.beats_per_bar)
    spb = 60.0 / args.bpm
    pm = pretty_midi.PrettyMIDI(initial_tempo=args.bpm)
    inst = pretty_midi.Instrument(program=args.program, name="riff transcription")
    ableton = []
    for t0, t1, notes in segs:
        for n in notes:
            inst.notes.append(pretty_midi.Note(velocity=args.velocity, pitch=n, start=t0 * spb, end=t1 * spb))
            ableton.append({"pitch": n, "start_time": t0, "duration": t1 - t0, "velocity": args.velocity, "mute": False})
    pm.instruments.append(inst)
    pm.write(args.out)
    if args.ableton_json:
        with open(args.ableton_json, "w") as fh:
            json.dump(ableton, fh)
    total_beats = max((t1 for _, t1, _ in segs), default=0)
    print(f"wrote {args.out}: {len(inst.notes)} notes, {len(segs)} segments, {total_beats / args.beats_per_bar:.2f} bars at {args.bpm:g} BPM")
    print("bar(arr)  beats        notes")
    for t0, t1, notes in segs:
        bar = int(t0 // args.beats_per_bar)
        b0 = t0 - bar * args.beats_per_bar + 1
        b1 = t1 - bar * args.beats_per_bar + 1
        names = " ".join(librosa.midi_to_note(n).replace("♯", "#") for n in notes)
        print(f"{bar + args.bar_offset:8d}  {b0:4.2f}-{b1:4.2f}   {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
