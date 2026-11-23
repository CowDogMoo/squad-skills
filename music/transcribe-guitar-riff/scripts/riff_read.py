#!/usr/bin/env python3
"""Read a riff off the salience rows: which candidates are voices, where each
note starts and ends, and the row that justifies every edge.

riff_salience.py prints candidates; this script makes the reading decisions
that used to be made by hand from its table, the same way every time, and
prints the evidence for each one so the reading can be checked line by line.

    python riff_read.py RIFF.wav --bpm 120 --tuning E2,A2,D3,G3,B3,E4 \
        --lowest A#3@1-3,A3@4 --spec OUT/riff.spec

--lowest takes the note each octave_check.py verdict line named for the lowest
voice, with the bars that verdict covered (one verdict per pedal stretch, bars
numbered as in the slot ids): NOTE@FIRST-LAST, or NOTE@BAR for one bar. Each
note applies only in its own bars; a bare note covers the whole riff. It is
required, and every bar must have one: the octave check is the gate that
decides the register, and this script will not guess it.

Voices, per grid slot (all on-grid salience peaks, not only the top four the
table prints). Every candidate that is not a voice is listed with its reason:

- "no fret": no position in the tuning (below the lowest open string), so
  nobody played it; a distortion product or an image.
- "below X": under the lowest note --lowest names for that bar. The octave check settled
  the lowest voice's register; anything under it is a sub-octave image or a
  difference tone, including the octave below an upper voice.
- "octave above/below X": of two candidates an octave apart, a --lowest note
  always wins; otherwise the one with the higher mean level over the
  surrounding beat is the voice and the other its harmonic or sub-octave
  image. A partner with no peak in this slot (a dip) still counts when it
  peaks in the surrounding slots. "12th / two octaves above X": the 3rd or 4th harmonic of a stronger
  note. A played doubling at these intervals looks the same, so it is never
  read as a voice, and the report says so.
- "N dB under the lead": more than FLOOR_DB under the slot's strongest voice.
- "weaker than N voices": only the --voices strongest count (2 = dyad).

Notes, per pitch: a one-slot gap inside a run is held (a dip, not a rest); a
run of one slot is a flicker and is dropped. A note that a new note in the
same line (nearer its pitch than any other voice) attacks over, while it still
sounds, ends at that attack. A note that fades out on its own has its last
RING_S seconds cut: that sound is the last pick ringing on (measured on
re-picked notes). A held or let-ring note's tail is cut the same way, so it
may be written up to RING_S short; "check by ear" lists each one. A note
still sounding past the last whole bar ends at that barline: the ring-out
after the final chord is its sustain, not another bar. A one-slot dip in the
file's last slot is held too, so a clip cut on the barline keeps its last
sixteenth.

The CQT here uses filters FILTER_SCALE as long as riff_salience.py's table
(still a third of a semitone per bin) so a slot's level leaks less into its
neighbours; the dB values therefore differ a little from the table's.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import librosa
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import riff_salience as rs  # noqa: E402  (same directory, one analysis)

FLOOR_DB = 15.0  # a voice weaker than this below the slot's leader is not read
RING_S = 0.25  # ring after the last pick that a note fading out on its own loses (seconds)
FILTER_SCALE = 0.7  # CQT filter length relative to riff_salience.py's table
OCTAVE_WINDOW = 4  # slots each side used to decide which member of an octave pair sounds
ABSENT_DB = -60.0  # level a slot without the peak contributes to that decision


def midi_of(note: str) -> int:
    return int(round(librosa.note_to_midi(note.replace("♯", "#"))))


def name_of(midi: int) -> str:
    return librosa.midi_to_note(midi, unicode=False)


def parse_lowest(text: str):
    """[(midi, first_bar, last_bar)] from 'A#3@1-3,A3@4'; a bare note covers every bar."""
    out = []
    for item in (x.strip() for x in text.split(",")):
        if not item:
            continue
        note, _, bars = item.partition("@")
        first, _, last = bars.partition("-")
        span = (int(first), int(last or first)) if bars else (None, None)
        out.append((midi_of(note.strip()), *span))
    return out


def classify(rows, lowest: list[set[int]], voices: int):
    """Per slot: the voices, and every other candidate with why it was set aside.

    lowest[i] holds the notes --lowest names for slot i's bar."""
    cand = []
    for r in rows:
        cs = {}
        for c in r["candidates"]:
            m = midi_of(c["note"])
            if m not in cs or c["db"] > cs[m]["db"]:
                cs[m] = c
        cand.append(cs)
    n = len(rows)
    out = []
    for i in range(n):
        cs = cand[i]
        low = lowest[i]
        gate = min(low)
        reason = {}
        for m, c in cs.items():
            if not c["frets"]:
                reason[m] = "no fret"
            elif m < gate:
                reason[m] = f"below {name_of(gate)}"
        lo, hi = max(0, i - OCTAVE_WINDOW), min(n, i + OCTAVE_WINDOW + 1)

        def presence(m):
            # mean level over the surrounding slots, a slot without the peak counting as ABSENT_DB
            return float(np.mean([cand[j][m]["db"] if m in cand[j] else ABSENT_DB for j in range(lo, hi)]))

        def partner(p):
            # a voice an image could belong to: peaking here and not set aside, or (a dip) peaking
            # with a fret in the surrounding slots and not under the gate
            if p in cs:
                return p not in reason
            return p >= gate and any(p in cand[j] and cand[j][p]["frets"] for j in range(lo, hi))

        for m in sorted(cs):
            if m in reason:
                continue
            if m in low:
                continue  # the octave check named this register; its octaves are the images
            for other, rel in ((m - 12, "above"), (m + 12, "below")):
                if partner(other):
                    if other in low:
                        reason[m] = f"octave {rel} {name_of(other)}"
                        break
                    pm, po = presence(m), presence(other)
                    lower_wins = rel == "above"  # ties go to the lower note
                    if pm < po or (pm == po and lower_wins):
                        reason[m] = f"octave {rel} {name_of(other)}"
                        break
        for m in sorted(cs):
            for k, name in ((19, "12th"), (24, "two octaves")):
                lower = m - k
                if m in reason or not partner(lower):
                    continue
                if (cs[lower]["db"] > cs[m]["db"]) if lower in cs else (presence(lower) > presence(m)):
                    reason[m] = f"{name} above {name_of(lower)} (its {3 if k == 19 else 4}rd harmonic)".replace("4rd", "4th")
        live = sorted((m for m in cs if m not in reason), key=lambda m: -cs[m]["db"])
        lead = cs[live[0]]["db"] if live else None
        kept = []
        for m in live:
            if cs[m]["db"] < lead - FLOOR_DB:
                reason[m] = f"{lead - cs[m]['db']:.0f} dB under the lead"
            elif len(kept) >= voices:
                reason[m] = f"weaker than {voices} voices"
            else:
                kept.append(m)
        out.append({"voices": kept, "reason": reason, "cands": cs})
    return out


def runs_of(flags):
    """[(start, end_exclusive)] of True stretches."""
    runs, s = [], None
    for i, f in enumerate(flags + [False]):
        if f and s is None:
            s = i
        elif not f and s is not None:
            runs.append((s, i))
            s = None
    return runs


def read(rows, slots, n_read, slot_len):
    """Per-note runs with held dips, dropped flickers and cut ring."""
    pitches = sorted({m for s in slots for m in s["voices"]})
    ring_max = max(1, int(round(RING_S / slot_len)))
    raw = []
    for m in pitches:
        on = [m in s["voices"] for s in slots]
        held = []
        for i in range(1, len(on)):
            after = on[i + 1] if i + 1 < len(on) else i >= 2 and on[i - 2]
            if not on[i] and on[i - 1] and after:
                on[i] = True
                held.append(i)
        for s0, s1 in runs_of(on):
            if s1 - s0 >= 2:
                raw.append((m, s0, s1, [h for h in held if s0 <= h < s1]))
    starts = {}
    for m, s0, _, _ in raw:
        starts.setdefault(s0, []).append(m)
    notes = []
    for m, s0, s1, held in raw:
        ringout = s1 > n_read
        end, ring, how = s1, [], "faded"
        if s1 >= len(slots):
            how = "end"
        else:
            # a new note in the same line (nearer this pitch than any other voice sounding
            # at its attack or once this one has stopped) attacking while this one still
            # rings: end at that attack
            def same_line(o, t):
                others = [x for x in {*slots[t]["voices"], *slots[s1]["voices"]} if x not in (m, o)]
                return all(abs(o - m) < abs(x - m) for x in others)

            new = [t for t in range(s0 + 1, s1 + 1) if s1 - t <= ring_max + 1
                   and any(o != m and same_line(o, t) for o in starts.get(t, []))]
            pushed = slots[s1]["reason"].get(m, "").startswith("weaker than")
            if new:
                end, how = new[0], "replaced"
            elif pushed:
                how = "replaced"
            elif not ringout:
                # it faded out on its own: the last RING_S of the sound is its last pick ringing on
                while end - s0 > 2 and len(ring) < ring_max:
                    end -= 1
                    ring.insert(0, end)
        notes.append({"midi": m, "start": s0, "end": min(end, n_read), "ring": [i for i in ring if i < n_read],
                      "sounding": list(range(min(end, n_read), min(s1, n_read))),
                      "ringout": ringout, "how": how, "held": [h for h in held if h < min(end, n_read)]})
    return [x for x in notes if x["end"] > x["start"]]


def segments(notes, n_read, grid, beats_per_bar):
    sets = [tuple(sorted(x["midi"] for x in notes if x["start"] <= i < x["end"])) for i in range(n_read)]
    segs = []
    beat_per_slot = beats_per_bar / grid
    for i, s in enumerate(sets):
        bar, pos = divmod(i, grid)
        if segs and segs[-1][0] == bar and segs[-1][3] == s and segs[-1][2] == pos:
            segs[-1][2] = pos + 1
        else:
            segs.append([bar, pos, pos + 1, s])
    return [(bar + 1, 1 + p0 * beat_per_slot, 1 + p1 * beat_per_slot, s) for bar, p0, p1, s in segs if s]


def fmt_beat(b: float) -> str:
    return f"{b:g}" if b != int(b) else f"{b:.1f}"


def row_text(slot_id, slot, reading, ringing, focus=(), past_end=False):
    """One slot's candidates, strongest first: notes in the reading plain, the rest with the reason."""
    cs = slot["cands"]
    order = sorted(cs, key=lambda m: -cs[m]["db"])
    parts = []
    for m in order:
        c = cs[m]
        if m in reading:
            tag = "" if m in slot["voices"] else f" ({slot['reason'][m]}; held)"
        elif m in slot["voices"]:
            tag = (" (ring-out past the last barline)" if past_end else
                   " (ringing on after its last pick)" if m in ringing else " (one-slot flicker)")
        else:
            tag = f" ({slot['reason'][m]})"
        mark = "*" if m in focus else ""
        parts.append(f"{mark}{c['note']} {c['db']:.1f}{tag}")
        if len(parts) >= 5 and all(f not in cs or f in order[:len(parts)] for f in focus):
            break
    for m in sorted(reading - set(cs)):
        parts.append(f"{'*' if m in focus else ''}{name_of(m)} - (no peak in this slot; held)")
    return f"{slot_id}: " + ", ".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav")
    ap.add_argument("--bpm", type=float, required=True)
    ap.add_argument("--tuning", required=True, help="open strings low to high, e.g. E2,A2,D3,G3,B3,E4")
    ap.add_argument("--lowest", required=True, help="the note each octave_check.py verdict line named for the lowest voice, "
                    "with its bars as in the slot ids, e.g. A#3@1-3,A3@4 (a bare note covers every bar)")
    ap.add_argument("--voices", type=int, default=2, help="most voices read per slot (2 = dyad riff)")
    ap.add_argument("--grid", type=int, default=16)
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--offset", type=float, default=0.0, help="seconds from file start to the first downbeat")
    ap.add_argument("--bar-offset", type=int, default=1, help="number of the first bar in the slot ids (the spec always starts at bar 1)")
    ap.add_argument("--fmax", type=float, default=600.0)
    ap.add_argument("--tune-offset", type=float, default=None, help="cents sharp of A440, as riff_salience.py --tune-offset")
    ap.add_argument("--auto-tune", action="store_true")
    ap.add_argument("--spec", help="write the reading as a riff_midi.py spec")
    ap.add_argument("--json", help="write voices, notes and segments as JSON")
    args = ap.parse_args(argv)

    lowest = [n.strip() for n in args.lowest.split(",") if n.strip()]
    try:
        stretches = parse_lowest(args.lowest)
    except ValueError:
        ap.error(f"--lowest {args.lowest!r}: give NOTE, NOTE@BAR or NOTE@FIRST-LAST, comma-separated")
    y, sr = librosa.load(args.wav, sr=44100, mono=True)
    tune = args.tune_offset if args.tune_offset is not None else (rs.estimate_tune_offset(y, sr) if args.auto_tune else 0.0)
    tuning = rs.parse_tuning(args.tuning)
    rows = rs.analyze(y, sr, args.bpm, args.grid, args.beats_per_bar, args.offset, 30.0, args.fmax, 64,
                      args.bar_offset, tuning, tune_cents=tune, filter_scale=FILTER_SCALE)
    slot_len = 60.0 / args.bpm * args.beats_per_bar / args.grid
    n_bars = int(round((len(y) / sr - args.offset) / slot_len, 6)) // args.grid
    if n_bars < 1:
        ap.error(f"{args.wav} holds no whole bar after --offset")
    n_read = min(n_bars * args.grid, len(rows))
    last_bar = args.bar_offset + n_bars - 1
    bar_lowest = {b: {m for m, first, last in stretches if first is None or first <= b <= last}
                  for b in range(args.bar_offset, last_bar + 1)}
    bare = [b for b, low in bar_lowest.items() if not low]
    if bare:
        ap.error(f"--lowest names no note for bar(s) {', '.join(map(str, bare))}")
    slots = classify(rows, [bar_lowest[min(args.bar_offset + i // args.grid, last_bar)] for i in range(len(rows))], args.voices)
    notes = read(rows, slots, n_read, slot_len)
    segs = segments(notes, n_read, args.grid, args.beats_per_bar)
    ids = [r["slot"] for r in rows]

    print(f"# {args.wav}  bpm={args.bpm:g}  {n_bars} bars  tuning={args.tuning}  lowest voice from octave_check: {', '.join(lowest)}"
          + (f"  tuning offset {tune:+.0f} cents" if tune else ""))
    print("reading (riff_midi.py spec: bar start end notes; beats 1-based, end exclusive):")
    spec_lines = [f"{bar} {fmt_beat(b0)} {fmt_beat(b1)} {' '.join(name_of(m) for m in s)}" for bar, b0, b1, s in segs]
    for line in spec_lines:
        print(f"  {line}")

    print("\nnote edges (first and last slot read, and why it stops there):")
    for x in sorted(notes, key=lambda x: (x["start"], x["midi"])):
        nm = name_of(x["midi"])
        span = f"{ids[x['start']]}-{ids[x['end'] - 1]}"
        if x["ringout"] and x["end"] == n_read:
            why = "still sounding at the last barline: ends there, the ring-out is not written"
        elif x["ring"]:
            r = x["ring"]
            dbs = ", ".join(f"{slots[i]['cands'][x['midi']]['db']:.1f}" if x['midi'] in slots[i]['cands'] else "-" for i in r)
            why = (f"fades out on its own; {ids[r[0]]}{'-' + ids[r[-1]] if len(r) > 1 else ''} ({dbs} dB) is the "
                   f"last pick ringing on ({RING_S:g} s), left out")
        elif x["how"] == "replaced" and x["end"] < len(ids):
            why = f"a new note in the same line attacks at {ids[x['end']]}"
        else:
            nxt = x["end"]
            why = f"absent from the voices at {ids[nxt]}" if nxt < len(ids) else "end of file"
        held = f"; held through {', '.join(ids[h] for h in x['held'])} (one-slot dip)" if x["held"] else ""
        frets = next((slots[i]["cands"][x["midi"]]["frets"] for i in range(x["start"], x["end"]) if x["midi"] in slots[i]["cands"]), "")
        print(f"  {nm:4s} {span:13s} {why}{held}")
        print(f"       frets in this tuning (string:fret, string 1 = highest): {frets}")
        lv = " ".join(f"{slots[i]['cands'][x['midi']]['db']:.0f}" if x["midi"] in slots[i]["cands"] else "-"
                      for i in range(x["start"], x["end"]))
        print(f"       dB in each slot read: {lv}")

    print("\nsalience rows (the salience analysis of each slot cited above, strongest first; notes in the reading"
          " plain and *starred where cited, every other candidate with the measured reason it is not read):")
    cited = {}
    for x in notes:
        for i in [x["start"], x["end"] - 1, *x["ring"], *x["held"]] + ([x["end"]] if x["end"] < len(rows) and not x["ring"] else []):
            cited.setdefault(i, set()).add(x["midi"])
    for i in sorted(cited):
        reading = {x["midi"] for x in notes if x["start"] <= i < x["end"]}
        ringing = {x["midi"] for x in notes if i in x["sounding"]}
        print(f"  {row_text(ids[i], slots[i], reading, ringing, cited[i], i >= n_read)}")

    doubts = []
    for x in sorted(notes, key=lambda x: (x["start"], x["midi"])):
        nm = name_of(x["midi"])
        if x["ring"]:
            doubts.append(f"{nm} ends at {ids[x['end'] - 1]}; its sound continues through {ids[x['ring'][-1]]} (ring, or still picked?)")
        if x["held"]:
            doubts.append(f"{nm} is held through a one-slot dip at {', '.join(ids[h] for h in x['held'])}")
    print("\ncheck by ear:")
    for d in doubts or ["(no marginal edges)"]:
        print(f"  {d}")
    print(f"  a note that ends on its own is cut {RING_S:g} s before its fade: a held or let-ring note may really end later")
    print("  octave doublings cannot be told from harmonics here; add any you played after an ear check")

    if args.spec:
        with open(args.spec, "w") as fh:
            fh.write(f"# read by riff_read.py from {os.path.basename(args.wav)} (lowest voice: {', '.join(lowest)})\n")
            fh.write("\n".join(spec_lines) + "\n")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"bpm": args.bpm, "bars": n_bars, "lowest": lowest, "tune_offset_cents": tune, "spec": spec_lines,
                       "notes": [{"note": name_of(x["midi"]), "first": ids[x["start"]], "last": ids[x["end"] - 1],
                                  "ring": [ids[i] for i in x["ring"]], "held": [ids[i] for i in x["held"]], "ends": x["how"]} for x in notes],
                       "slots": [{"slot": ids[i], "voices": [name_of(m) for m in s["voices"]],
                                  "set_aside": {name_of(m): r for m, r in s["reason"].items()}} for i, s in enumerate(slots)]},
                      fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
