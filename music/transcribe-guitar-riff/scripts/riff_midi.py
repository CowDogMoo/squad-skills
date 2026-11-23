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
    python riff_midi.py riff.spec --bpm 120 --out cleaned.mid --evidence slots.json

--evidence takes riff_salience.py's --json output (run with the same
--bar-offset) and prints the lines the reading rests on: the per-beat entry
of every beat the spec writes, every row of each beat whose entry does not
list all its written notes, and a pitch map. Paste that block whole rather
than assembling rows by hand.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys

import librosa
import pretty_midi


INTERVALS = ["unison", "minor 2nd", "major 2nd", "minor 3rd", "major 3rd", "perfect 4th",
             "tritone", "perfect 5th", "minor 6th", "major 6th", "minor 7th", "major 7th"]


def interval_name(semitones: int) -> str:
    """Name the interval between two MIDI notes (an octave counts as compound)."""
    octaves, rest = divmod(semitones, 12)
    if rest == 0 and octaves:
        return "octave" if octaves == 1 else f"{octaves} octaves"
    name = INTERVALS[rest]
    return name if not octaves else f"{name} + {octaves} oct"


def intervals_above_bass(notes: list[int]) -> str:
    """Each upper note's interval above the lowest one, e.g. 'A#3-F4 perfect 5th'."""
    ordered = sorted(notes)
    bass = ordered[0]
    return "; ".join(
        f"{librosa.midi_to_note(bass, unicode=False)}-{librosa.midi_to_note(n, unicode=False)} "
        f"{interval_name(n - bass)}"
        for n in ordered[1:]
    )


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


def note_label(n: int) -> str:
    return librosa.midi_to_note(n).replace("♯", "#")


def print_evidence(segs, slots_path: str, beats_per_bar: int, bar_offset: int) -> None:
    from riff_salience import PER_BEAT_HEADER, format_beat, format_peak, per_beat_summary

    with open(slots_path) as fh:
        data = json.load(fh)
    rows = data["slots"]
    per_beat_slots = data["grid"] // beats_per_bar
    summary = per_beat_summary(rows)
    by_id = {r["slot"]: r for r in rows}

    def slot_id(i: int) -> str:
        bar, rest = divmod(i, data["grid"])
        return f"{bar + bar_offset}.{rest // per_beat_slots + 1}.{rest % per_beat_slots + 1}"

    def shows(r, name: str) -> bool:
        return any(c["note"] == name for c in r["candidates"])

    covered: dict[str, set[int]] = {}
    for t0, t1, notes in segs:
        for name in map(note_label, notes):
            covered.setdefault(name, set()).update(
                range(round(t0 * per_beat_slots), round(t1 * per_beat_slots)))
    written: dict[str, list[str]] = {}
    for name, idxs in covered.items():
        for i in sorted(idxs):
            key = slot_id(i).rsplit(".", 1)[0]
            if name not in written.setdefault(key, []):
                written[key].append(name)
    keys = sorted(written, key=lambda k: tuple(int(x) for x in k.split(".")))
    stable = {k: summary[k][0] if k in summary else [] for k in keys}
    short = {k for k in keys if any(n not in stable[k] for n in written[k])}
    # rows to show: every row of a beat whose entry misses a written note, plus
    # the slot where each voice starts and the slot after it stops
    show = {r["slot"] for r in rows if r["slot"].rsplit(".", 1)[0] in short}
    for idxs in covered.values():
        show.update(slot_id(i) for i in idxs if i - 1 not in idxs)
        show.update(slot_id(i + 1) for i in idxs if i + 1 not in idxs)

    print("\nevidence for the reading (riff_midi.py --evidence; paste it whole):")
    print(PER_BEAT_HEADER)
    for k in keys:
        print(format_beat(k, *summary[k]) if k in summary else f"  {k:6s} (no slots in the JSON)")
    print("\nrows where a voice starts or stops, and every row of a beat whose entry"
          " does not list all the notes written there (note cents dB):")
    for r in rows:
        if r["slot"] in show:
            desc = " | ".join(f"{c['note']} {c['cents']:+d} {c['db']:.1f}dB" for c in r["candidates"])
            print(f"  {r['slot']:9s} {desc}")
    print("\npitch map (pitch: beat entries that list it | rows that show it on other beats"
          " | long-term peak, if any):")
    for name in covered:
        entries = [k for k in keys if name in written[k] and name in stable[k]]
        other = [slot_id(i) for i in sorted(covered[name])
                 if slot_id(i).rsplit(".", 1)[0] in short and name not in stable[slot_id(i).rsplit(".", 1)[0]]
                 and slot_id(i) in by_id and shows(by_id[slot_id(i)], name)]
        peaks = [format_peak(hz, d).strip() for hz, d in sorted(data.get("long_term_peaks", []))
                 if librosa.hz_to_note(hz).replace("♯", "#") == name]
        print(f"  {name:4s} {' '.join(entries) or '-'} | {' '.join(other) or '-'}"
              + (f" | {'; '.join(peaks)}" if peaks else ""))
        unshown = [k for k in keys if name in written[k] and name not in stable[k]
                   and not any(shows(r, name) for r in rows if r["slot"].startswith(k + "."))]
        if unshown:
            print(f"       written on beats where no row shows it: {' '.join(unshown)}")
    print(f"  no other pitch is written ({len(covered)} pitches)")


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
    ap.add_argument("--evidence", metavar="SLOTS_JSON", help="riff_salience.py --json output; print the evidence block and pitch map for the reading")
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
    print("bar(arr)  beats        notes          intervals above the lowest note")
    for t0, t1, notes in segs:
        bar = int(t0 // args.beats_per_bar)
        b0 = t0 - bar * args.beats_per_bar + 1
        b1 = t1 - bar * args.beats_per_bar + 1
        names = " ".join(map(note_label, notes))
        intervals = intervals_above_bass(notes) if len(notes) > 1 else "-"
        print(f"{bar + args.bar_offset:8d}  {b0:4.2f}-{b1:4.2f}   {names:<14} {intervals}")
    if args.evidence:
        print_evidence(segs, args.evidence, args.beats_per_bar, args.bar_offset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
