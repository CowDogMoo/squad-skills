#!/usr/bin/env python3
"""Repeat one read cycle across a section, the way the music repeats it.

`riff_cycle.py` finds the repeating unit and folds every repetition together so
the reading is made once from all the evidence. This stamps that one cycle back
across the section.

Doing it this way is the point, not a convenience. Reading each bar separately
is the biggest tell of a machine transcription: sixteen subtly different bars
where the music has four, repeated. Every note can be individually defensible
and the result still not be a riff. Stamping guarantees that bars the audio
repeats are written identically.

    python riff_cycle.py CLIP.wav --bpm 120 --bars 21,36 --band 75,200 > cycle.spec
    python stamp_cycle.py cycle.spec --bars 21,36 > section.spec

A spec line is `BAR START_BEAT END_BEAT NOTE`, beats 1-based within the bar, so
a 4/4 bar runs 1.00 to 5.00. Lines starting with `#` are comments and are kept
out of the output. If the cycle is longer than one bar its internal bar numbers
are preserved modulo the cycle length, so a 4-bar cycle stamps as 4-bar blocks.
"""
from __future__ import annotations

import argparse
import sys


def read_spec(path):
    """(lines, cycle_bars_declared) - lines as (bar, start, end, note) tuples."""
    declared = None
    rows = []
    stream = sys.stdin if path == "-" else open(path)
    with stream as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                # riff_cycle.py announces the cycle length in its header comment.
                if "one cycle =" in line:
                    try:
                        declared = int(line.split("one cycle =")[1].split("bar")[0].strip())
                    except (IndexError, ValueError):
                        pass
                continue
            parts = line.split()
            if len(parts) != 4:
                raise SystemExit(f"malformed spec line (want 'BAR START END NOTE'): {line!r}")
            bar, start, end, note = parts
            rows.append((int(bar), float(start), float(end), note))
    return rows, declared


def stamp(rows, cycle_bars, lo_bar, hi_bar):
    first = min(r[0] for r in rows)
    out = []
    for block_start in range(lo_bar, hi_bar + 1, cycle_bars):
        for bar, start, end, note in rows:
            target = block_start + (bar - first)
            if target > hi_bar:
                continue
            out.append((target, start, end, note))
    out.sort(key=lambda r: (r[0], r[1]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="one-cycle spec from riff_cycle.py, or - for stdin")
    ap.add_argument("--bars", required=True, help="LO,HI inclusive, the section to fill")
    ap.add_argument("--cycle-bars", type=int, default=0,
                    help="override the cycle length riff_cycle.py declared in its header")
    ap.add_argument("--out", default="", help="write here instead of stdout")
    args = ap.parse_args()

    lo_bar, hi_bar = (int(x) for x in args.bars.split(","))
    if hi_bar < lo_bar:
        raise SystemExit("--bars is LO,HI with HI >= LO")

    rows, declared = read_spec(args.spec)
    if not rows:
        raise SystemExit("the spec has no note lines")

    cycle_bars = args.cycle_bars or declared
    if not cycle_bars:
        # Fall back to the span the spec itself covers.
        cycle_bars = max(r[0] for r in rows) - min(r[0] for r in rows) + 1
    if cycle_bars < 1:
        raise SystemExit(f"nonsensical cycle length {cycle_bars}")

    out = stamp(rows, cycle_bars, lo_bar, hi_bar)
    span = hi_bar - lo_bar + 1
    reps = -(-span // cycle_bars)
    header = (f"# {len(rows)} line(s) of a {cycle_bars}-bar cycle stamped "
              f"{reps}x across bars {lo_bar}-{hi_bar}")
    body = "\n".join(f"{b} {s:.2f} {e:.2f} {n}" for b, s, e, n in out)
    text = f"{header}\n{body}\n"
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        print(f"{header}\nwrote {len(out)} line(s) to {args.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
