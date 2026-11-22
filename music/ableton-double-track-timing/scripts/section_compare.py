#!/usr/bin/env python3
"""Alias-free audio confirmation: compare a section with an earlier copy of itself,
track by track. Offline, read-only.

When a section is built from copies (a repeated riff, a second chorus), each
track should play the same audio in both places. Cross-correlating a track's
source audio over the suspect section against the same track over the
reference section gives an exact shift, with correlation near 1.000 for
identical takes. Riff periodicity can't fool it the way the double-vs-double
DI comparison is fooled, because the two signals are the same audio. Run it on
both sides of a double: the side that shows a shift is the side that moved.

    python3 section_compare.py SET.als --tracks "Jayson Scratch" "Jason Scratch" \
        --ref 341 --test 357 --length 8

Here --ref 341 --test 357 compares beats 357-365 against 341-349. A shift of
+31 ms (corr 1.00) means the test section plays 31 ms later than its copy.
A corr well below about 0.9 means the two sections aren't the same audio
(a different take or edit), so the shift means little.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alsio  # noqa: E402
import attack_audit as A  # noqa: E402

FS = 2000.0   # 0.5 ms grid


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('als')
    ap.add_argument('--tracks', nargs='+', required=True, help='names or #index')
    ap.add_argument('--ref', type=float, required=True, help='start beat of the reference (known good) section')
    ap.add_argument('--test', type=float, required=True, help='start beat of the suspect section')
    ap.add_argument('--length', type=float, required=True, help='section length in beats')
    ap.add_argument('--window-ms', type=float, default=100.0, help='max shift searched (default 100)')
    ap.add_argument('--gate-db', type=float, default=-25.0)
    a = ap.parse_args(argv)

    root = alsio.load(a.als)
    trs = alsio.tracks(root, a.als)
    tm = alsio.tempo_map(root, trs)
    ids = [alsio.resolve_track(trs, s) for s in a.tracks]
    n = A.grid_len(tm, trs, ids, FS)
    r0, r1 = tm.b2s(a.ref), tm.b2s(a.ref + a.length)
    t0 = tm.b2s(a.test)
    dur = r1 - r0
    t1 = tm.b2s(a.test + a.length)
    if abs((t1 - t0) - dur) > 0.002:
        print(f'note: the sections differ in length in seconds ({dur:.3f} vs {t1 - t0:.3f} s): tempo differs; '
              'the shift is measured from the section starts')
    pad = int(a.window_ms / 1000 * FS)
    print(f'test beats {a.test:g}-{a.test + a.length:g} (bar {alsio.bar_beat(a.test)}) vs reference '
          f'{a.ref:g}-{a.ref + a.length:g} (bar {alsio.bar_beat(a.ref)}), window +-{a.window_ms:g} ms\n')
    for ti in ids:
        env = A.track_env(trs, ti, tm, n, a.gate_db, FS)
        att = A.attack(env)
        i0, j0 = int(round(r0 * FS)), int(round(t0 * FS))
        m = int(round(dur * FS))
        ref = att[i0:i0 + m]
        best = (-2.0, 0)
        nr = np.linalg.norm(ref)
        for lag in range(-pad, pad + 1):
            s = j0 + lag
            if s < 0 or s + m > len(att):
                continue
            seg = att[s:s + m]
            ns = np.linalg.norm(seg)
            if nr == 0 or ns == 0:
                continue
            c = float(np.dot(ref, seg)) / (nr * ns)
            if c > best[0]:
                best = (c, lag)
        if best[0] <= -1:
            print(f'{alsio.tname(trs, ti)}: no audio above the gate in one of the sections')
            continue
        ms = best[1] / FS * 1000
        beats = tm.s2b(t0 + ms / 1000) - a.test
        verdict = ('same audio' if best[0] >= 0.9 else 'NOT the same audio: shift unreliable')
        print(f'{alsio.tname(trs, ti):28s} shift {ms:+7.2f} ms ({beats:+.4f} beat)  corr {best[0]:.3f}  {verdict}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
