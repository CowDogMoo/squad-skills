#!/usr/bin/env python3
"""Turn a measured spec into a riff string the guitar-pro skill can write.

Two jobs, and both exist because of a delivered tab that was called unplayable
while every per-note metric on it looked fine.

**1. Durations come from a closed vocabulary, never from a measured gap.**
Onset-to-onset spans produce lengths like 5/4 or 7/4 of a quarter note, which no
single note value can draw, so the writer splits each into re-picked notes and
the rhythm reads as a stutter. 7.6% of one job's segments were like that.
`--single-note-durations` instead solves each bar: it walks the bar in legal
note values and picks the partition whose boundaries land nearest the measured
attacks, charging for every attack it has to swallow. The bar still sums to its
signature and every beat is writable. Songsterr's 105-bar track uses eight
duration kinds in total - that is the target, not forty - so dotted and triplet
values also carry a small cost, and win only where the music needs them.

**2. Fingering respects the hand.** The first version of this scorer had
fret-spread, mean fret, position continuity and a string-stay bonus, but no
reach limit and no cross-string jump penalty, which is how a lone fret 11 landed
in the middle of a frets-3-to-7 riff. Both are here now, named after the
Songsterr ruleset terms in references/songsterr.md.

    python tab_build.py section.spec --tuning E2,A2,D3,G3,B3,E4 \\
        --single-note-durations --out riff.txt

**3. Dyads and chords, and tremolo.** A spec line may list several notes
(`1 2.0 5.0 A#3 F#4`), the same format riff_midi.py reads; they are fingered
together on different strings within the hand's reach. `--tremolo 16` writes
every segment as straight sixteenths, re-picked, which is how a tremolo riff is
tabbed, instead of solving held note values.

    python tab_build.py riff.spec --tuning E2,A2,D3,G3,B3,E4 --tremolo 16 \\
        --bpm 120 --gp5 tab.gp5 --midi tab.mid

`--gp5` hands the riff to gp5_write.py, which writes the Guitar Pro file,
reloads it, exports `--midi` from the reload and prints its ASCII tab - the
input compare_rolls.py needs to check the written file against cleaned.mid.

Input lines are `BAR START_BEAT END_BEAT NOTE [NOTE ...]`, beats 1-based within
the bar, as emitted by riff_cycle.py and stamp_cycle.py and read by
riff_midi.py. Output is a gp_tab riff string: `DURATION:STRING.FRET` beats
(chords joined with `+`), bars separated by `|`.
"""
from __future__ import annotations

import argparse
import itertools
import os
import re
import sys

import librosa

TICKS_PER_BEAT = 480

# The closed vocabulary. A name is what gp_tab's DURATION token expects: a
# number, an optional '.' for a dot, an optional 't' for a triplet. The class
# cost keeps the vocabulary small - a dot or a triplet has to earn its place.
PLAIN = [("1", 4.0), ("2", 2.0), ("4", 1.0), ("8", 0.5), ("16", 0.25), ("32", 0.125)]
CLASS_COST = {"": 0.0, ".": 8.0, "t": 16.0}


def _vocabulary():
    out = {}
    for name, beats in PLAIN:
        for mark, factor in (("", 1.0), (".", 1.5), ("t", 2 / 3)):
            ticks = int(round(beats * factor * TICKS_PER_BEAT))
            if ticks > 0:
                out[name + mark] = (ticks, CLASS_COST[mark])
    return sorted(((n, t, c) for n, (t, c) in out.items()), key=lambda d: -d[1])


DURATIONS = _vocabulary()

SWALLOW_PENALTY = 240.0      # ticks of cost for an attack no boundary lands on
BOUNDARY_TOLERANCE = 30.0    # ticks; inside this an attack counts as landed on

# Fingering weights, named after the Songsterr ruleset terms in songsterr.md.
OUT_OF_REACH_PENALTY = 50.0
CROSS_STRING_JUMP_PENALTY = 50.0
CROSS_STRING_JUMP_MIN_FRET_DELTA = 3
STRING_STAY_BONUS = 2.0
SHIFT_WEIGHT = 1.0
MEAN_FRET_BIAS = 0.25
CHORD_SPAN_WEIGHT = 1.0      # per fret between a chord's lowest and highest fretted note


def read_spec(path):
    rows = []
    stream = sys.stdin if path == "-" else open(path)
    with stream as fh:
        for raw in fh:
            # a comment starts at a '#' that begins the line or follows
            # whitespace; the '#' inside A#3 is a sharp
            line = re.sub(r"(^|\s)#.*$", "", raw).strip()
            if not line:
                continue
            parts = line.split()
            try:
                if len(parts) < 4:
                    raise ValueError
                notes = tuple(p.replace("\u266f", "#") for p in parts[3:])
                for n in notes:
                    librosa.note_to_midi(n)
                rows.append((int(parts[0]), float(parts[1]), float(parts[2]), notes))
            except (ValueError, librosa.util.exceptions.ParameterError):
                raise SystemExit(f"malformed spec line (want 'BAR START END NOTE [NOTE ...]'): "
                                 f"{raw.strip()!r}") from None
    return rows


def solve_bar(attack_ticks, bar_ticks, durations=DURATIONS):
    """Partition [0, bar_ticks] into legal note values near the measured attacks.

    Dynamic programming over tick positions: dp[t] is the cheapest way to fill
    [0, t] with boundaries at legal positions. The cost charges the distance
    from each boundary to its nearest attack, SWALLOW_PENALTY for every attack
    no boundary got near, and the note value's own class cost.
    """
    attacks = sorted(set(attack_ticks))

    def nearest(t):
        return min((abs(t - a) for a in attacks), default=0.0)

    def swallowed(lo, hi):
        return sum(1 for a in attacks
                   if lo < a < hi and min(a - lo, hi - a) > BOUNDARY_TOLERANCE)

    dp = {0: (0.0, None)}
    for t in range(bar_ticks + 1):
        entry = dp.get(t)
        if entry is None:
            continue
        base = entry[0]
        for name, ticks, class_cost in durations:
            nt = t + ticks
            if nt > bar_ticks:
                continue
            cost = base + class_cost + swallowed(t, nt) * SWALLOW_PENALTY
            if nt != bar_ticks:
                cost += nearest(nt)
            if nt not in dp or cost < dp[nt][0]:
                dp[nt] = (cost, (t, name, ticks))

    if bar_ticks not in dp:
        raise SystemExit(f"no legal partition of a {bar_ticks}-tick bar; check --beats-per-bar")

    out, t = [], bar_ticks
    while t:
        _, back = dp[t]
        prev, name, ticks = back
        out.append((name, ticks))
        t = prev
    out.reverse()
    return out


def note_for(segment_lo, segment_hi, notes):
    """The notes (a tuple) whose measured span overlaps this segment most, or None."""
    best, best_overlap = None, 0.0
    for lo, hi, name in notes:
        overlap = min(hi, segment_hi) - max(lo, segment_lo)
        if overlap > best_overlap:
            best, best_overlap = name, overlap
    return best


def fret_candidates(midi, tuning_midi, max_fret):
    """(string_number, fret) options, gp_tab numbering: string 1 is the highest."""
    n = len(tuning_midi)
    return [(n - i, midi - open_midi)
            for i, open_midi in enumerate(tuning_midi)
            if 0 <= midi - open_midi <= max_fret]


def chord_options(midis, tuning_midi, max_fret, reach):
    """Every way to finger a chord: one (string, fret) per note, no string used
    twice, fretted notes within the hand's reach. Ordered like `midis`."""
    per_note = [fret_candidates(m, tuning_midi, max_fret) for m in midis]
    for m, opts in zip(midis, per_note):
        if not opts:
            raise SystemExit(f"MIDI {m} ({librosa.midi_to_note(m)}) is not reachable "
                             f"on this tuning within {max_fret} frets")
    out = []
    for combo in itertools.product(*per_note):
        if len({s for s, _ in combo}) != len(combo):
            continue
        fretted = [f for _, f in combo if f]
        if fretted and max(fretted) - min(fretted) > reach:
            continue
        out.append(combo)
    if not out:
        names = " ".join(librosa.midi_to_note(m) for m in midis)
        raise SystemExit(f"no fingering plays {names} together within a {reach}-fret reach")
    return out


def chord_cost(combo):
    """What holding this shape costs beyond its lowest note: its span and how
    far up the neck the other notes sit."""
    fretted = [f for _, f in combo if f]
    span = max(fretted) - min(fretted) if fretted else 0
    return CHORD_SPAN_WEIGHT * span + MEAN_FRET_BIAS * sum(f for _, f in combo[1:])


def transition_cost(prev, cur, reach):
    """Cost of moving the hand from one (string, fret) to the next."""
    ps, pf = prev
    cs, cf = cur
    cost = MEAN_FRET_BIAS * cf
    if pf and cf:  # both fretted; an open string costs the hand nothing
        delta = abs(cf - pf)
        cost += SHIFT_WEIGHT * delta
        if delta > reach:
            cost += OUT_OF_REACH_PENALTY
        if cs != ps and delta >= CROSS_STRING_JUMP_MIN_FRET_DELTA:
            cost += CROSS_STRING_JUMP_PENALTY
    if cs == ps:
        cost -= STRING_STAY_BONUS
    return cost


def choose_fingering(midis, tuning_midi, max_fret, reach):
    """Viterbi over fingerings. Each entry of `midis` is a tuple of MIDI numbers
    (one for a single note, two for a dyad) or None for a rest; each result is
    a tuple of (string, fret), one per note in the same order, or None.

    A chord's lowest note carries the hand position from beat to beat, so a
    lone note reduces to the single-note scorer exactly.

    Rests carry no hand position, so they are lifted out and spliced back in
    afterwards - otherwise a rest would break position continuity across it and
    the hand would be told to jump for no reason.
    """
    voiced = [(i, m) for i, m in enumerate(midis) if m is not None]
    if not voiced:
        return [None] * len(midis)

    options = [chord_options(m, tuning_midi, max_fret, reach) for _, m in voiced]

    best = {o: MEAN_FRET_BIAS * o[0][1] + chord_cost(o) for o in options[0]}
    back = [{o: None for o in options[0]}]
    for opts in options[1:]:
        cur, step = {}, {}
        for o in opts:
            chosen, chosen_cost = None, float("inf")
            for p, pc in best.items():
                c = pc + transition_cost(p[0], o[0], reach) + chord_cost(o)
                if c < chosen_cost:
                    chosen, chosen_cost = p, c
            cur[o], step[o] = chosen_cost, chosen
        best, _ = cur, back.append(step)

    end = min(best, key=best.get)
    path = [end]
    for step in reversed(back[1:]):
        path.append(step[path[-1]])
    path.reverse()

    out = [None] * len(midis)
    for (i, _), place in zip(voiced, path):
        out[i] = place
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="spec from riff_cycle.py / stamp_cycle.py, or - for stdin")
    ap.add_argument("--tuning", default="E2,A2,D3,G3,B3,E4", help="low string first")
    ap.add_argument("--beats-per-bar", type=float, default=4.0)
    ap.add_argument("--max-fret", type=int, default=24)
    ap.add_argument("--reach", type=int, default=5, help="frets the hand spans without shifting")
    ap.add_argument("--single-note-durations", action="store_true",
                    help="solve each bar from the closed note-value vocabulary "
                         "(without this, measured spans are written as-is and "
                         "undrawable lengths get split into re-picked notes)")
    ap.add_argument("--tremolo", type=int, choices=[8, 16, 32], default=0, metavar="DUR",
                    help="write every segment as straight re-picked notes of this value "
                         "(16 = sixteenths), the way a tremolo riff is tabbed")
    ap.add_argument("--out", default="")
    ap.add_argument("--gp5", help="also write this Guitar Pro 5 file (via gp5_write.py) and print "
                                  "the reloaded file's summary and ASCII tab")
    ap.add_argument("--midi", help="with --gp5: MIDI export of the reloaded .gp5")
    ap.add_argument("--bpm", type=float, help="tempo for --gp5")
    args = ap.parse_args()
    if args.tremolo and args.single_note_durations:
        ap.error("--tremolo and --single-note-durations are alternatives; pick one")
    if args.gp5 and not args.bpm:
        ap.error("--gp5 needs --bpm")
    if args.midi and not args.gp5:
        ap.error("--midi is exported from the written file, so it needs --gp5")

    tuning_midi = [int(librosa.note_to_midi(t.strip())) for t in args.tuning.split(",")]
    if tuning_midi != sorted(tuning_midi):
        print("# warning: --tuning is read low string first; yours descends", file=sys.stderr)
    bar_ticks = int(round(args.beats_per_bar * TICKS_PER_BEAT))

    rows = read_spec(args.spec)
    if not rows:
        raise SystemExit("the spec has no note lines")

    bars = sorted({r[0] for r in rows})
    out_bars, kinds = [], set()
    swallowed_total = attack_total = undrawable = span_total = 0
    for bar in range(bars[0], bars[-1] + 1):
        notes = sorted(((s - 1) * TICKS_PER_BEAT, (e - 1) * TICKS_PER_BEAT, n)
                       for b, s, e, n in rows if b == bar)
        attacks = [lo for lo, _, _ in notes]
        attack_total += len(attacks)

        if args.tremolo:
            step = 4 * TICKS_PER_BEAT // args.tremolo
            if bar_ticks % step:
                raise SystemExit(f"a {args.beats_per_bar:g}-beat bar is not a whole number of "
                                 f"1/{args.tremolo} notes")
            segments = [(str(args.tremolo), step)] * (bar_ticks // step)
            off_grid = [lo for lo, hi, _ in notes if lo % step or hi % step]
            if off_grid:
                print(f"# warning: bar {bar}: {len(off_grid)} segment edge(s) fall between "
                      f"1/{args.tremolo} slots and were rounded to the nearest slot", file=sys.stderr)
        elif args.single_note_durations:
            segments = solve_bar(attacks, bar_ticks)
        else:
            spans, cursor = [], 0.0
            for lo, hi, _ in notes:
                if lo > cursor:
                    spans.append(lo - cursor)
                spans.append(hi - lo)
                cursor = hi
            if cursor < bar_ticks:
                spans.append(bar_ticks - cursor)
            segments = []
            span_total += len(spans)
            for span in spans:
                name, ticks, _ = min(DURATIONS, key=lambda d: abs(d[1] - span))
                if abs(ticks - span) > BOUNDARY_TOLERANCE:
                    undrawable += 1
                segments.append((name, ticks))

        seg_notes, cursor = [], 0
        for _, ticks in segments:
            seg_notes.append(note_for(cursor, cursor + ticks, notes))
            cursor += ticks

        midis = [tuple(sorted(int(librosa.note_to_midi(n)) for n in group)) if group else None
                 for group in seg_notes]
        path = choose_fingering(midis, tuning_midi, args.max_fret, args.reach)

        beats = []
        for (name, _ticks), place in zip(segments, path):
            kinds.add(name)
            beats.append(f"{name}:r" if place is None
                         else f"{name}:" + "+".join(f"{s}.{f}" for s, f in place))
        out_bars.append(" ".join(beats))

        boundaries, c = set(), 0
        for _, ticks in segments:
            boundaries.add(c)
            c += ticks
        swallowed_total += sum(1 for a in attacks
                               if all(abs(a - b) > BOUNDARY_TOLERANCE for b in boundaries))

    riff = " | ".join(out_bars)
    summary = (f"# {len(out_bars)} bar(s), {len(kinds)} duration kind(s): "
               f"{' '.join(sorted(kinds))}")
    if args.tremolo:
        summary += f"; every segment re-picked as straight 1/{args.tremolo} notes (tremolo)"
    elif args.single_note_durations:
        summary += f"; {swallowed_total} of {attack_total} attack(s) swallowed by the grid"
    else:
        summary += (f"\n# warning: durations came from measured spans; {undrawable} of "
                    f"{span_total} span(s) were not writable as one note value and were "
                    "forced to the nearest. Pass --single-note-durations to solve each "
                    "bar instead.")

    text = f"{summary}\n{riff}\n"
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        print(f"{summary}\nwrote {args.out}")
    else:
        sys.stdout.write(text)
    if args.gp5:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from gp5_write import write_tab
        write_tab(riff, args.tuning, args.bpm, args.gp5, args.midi, args.beats_per_bar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
