#!/usr/bin/env python3
"""Piano-roll equivalence of two MIDI files on a rhythmic grid.

Samples both files on every grid slot (default sixteenths) and compares the
set of sounding pitches per slot. This is the right comparison between a
cleaned transcription (sustained notes) and a tab export (every tremolo
hit as its own note): onset lists differ, sounding pitches must not.

    python compare_rolls.py a.mid b.mid --bpm 120
    python compare_rolls.py a.mid b.mid --bpm 120 --expect match      # prints ROLLS MATCH, exit 0
    python compare_rolls.py a.mid b.mid --bpm 120 --expect mismatch   # prints ROLLS DIFFER, exit 0
"""
from __future__ import annotations

import argparse
import sys

import librosa
import mido


def roll(path: str, bpm: float, slots_per_beat: int, n_slots: int | None):
    m = mido.MidiFile(path)
    tpb = m.ticks_per_beat
    notes = []
    for tr in m.tracks:
        t = 0
        open_ = {}
        for msg in tr:
            t += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                open_[msg.note] = t
            elif msg.type in ("note_off", "note_on") and msg.note in open_:
                notes.append((open_.pop(msg.note) / tpb, t / tpb, msg.note))
    end_beat = max((e for _, e, _ in notes), default=0.0)
    total = n_slots if n_slots else int(end_beat * slots_per_beat + 0.999)
    grid = []
    for i in range(total):
        b = i / slots_per_beat + 0.01
        grid.append(frozenset(p for s, e, p in notes if s <= b < e))
    return grid


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--bpm", type=float, default=120.0, help="informational; MIDI timing is in beats")
    ap.add_argument("--slots-per-beat", type=int, default=4)
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--expect", choices=["match", "mismatch"], help="exit non-zero unless the outcome is this")
    args = ap.parse_args(argv)

    ra = roll(args.a, args.bpm, args.slots_per_beat, None)
    rb = roll(args.b, args.bpm, args.slots_per_beat, None)
    n = max(len(ra), len(rb))
    ra += [frozenset()] * (n - len(ra))
    rb += [frozenset()] * (n - len(rb))
    diffs = [(i, ra[i], rb[i]) for i in range(n) if ra[i] != rb[i]]
    print(f"slots compared: {n} ({args.slots_per_beat}/beat); mismatching: {len(diffs)}")
    for i, x, y in diffs[:40]:
        bar = i // (args.slots_per_beat * args.beats_per_bar) + 1
        beat = (i % (args.slots_per_beat * args.beats_per_bar)) / args.slots_per_beat + 1
        na = " ".join(librosa.midi_to_note(p).replace("♯", "#") for p in sorted(x)) or "-"
        nb = " ".join(librosa.midi_to_note(p).replace("♯", "#") for p in sorted(y)) or "-"
        print(f"  bar {bar} beat {beat:.2f}: a=[{na}] b=[{nb}]")
    outcome = "match" if not diffs else "mismatch"
    print("ROLLS MATCH" if outcome == "match" else "ROLLS DIFFER")
    if args.expect and args.expect != outcome:
        print(f"EXPECTATION FAILED: expected {args.expect}, got {outcome}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
