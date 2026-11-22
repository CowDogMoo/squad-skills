#!/usr/bin/env python3
"""Build the eval fixtures from a source Live set, without touching the source.

    python3 make_fixtures.py SOURCE.als OUTDIR

Writes into OUTDIR:
  coven-snapshot.als   a byte-identical copy of SOURCE (the full-audit case)
  planted-nudge.als    the copy with the "Jayson Scratch" clips that start at
                       beats 357.0 and 362.0 shifted +0.0625 beat (CurrentStart,
                       CurrentEnd and the event Time), re-gzipped. This recreates
                       the real bar 90-91 flam the method was built on.

The edit is made on the raw XML text, so every other byte of the set survives,
and the result is re-read to prove that exactly those two clips moved. Other
plants: --shift "TRACK@START+DELTA" (repeatable) replaces the default.

The source set's clips point at audio files by absolute path, so the fixtures
only work on a machine where those recordings exist.
"""
from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'scripts'))
import alsio  # noqa: E402
import collateral  # noqa: E402

DEFAULT_SHIFTS = ['Jayson Scratch@357+0.0625', 'Jayson Scratch@362+0.0625']
TRACK_RE = re.compile(r'\n\t\t\t<(AudioTrack|MidiTrack|GroupTrack|ReturnTrack) Id="')
CLIP_RE = re.compile(r'<AudioClip Id="\d+" Time="([^"]+)">')


def fmt(x):
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def track_spans(text):
    a = text.index('\n\t\t<Tracks>')
    b = text.index('\n\t\t</Tracks>', a)
    starts = [(m.start(), m.group(1)) for m in TRACK_RE.finditer(text, a, b)]
    spans = []
    for i, (s, kind) in enumerate(starts):
        e = starts[i + 1][0] if i + 1 < len(starts) else b
        if kind != 'ReturnTrack':
            spans.append((s, e))
    return spans


def plant(text, ti, start, delta, spans):
    s, e = spans[ti]
    seg = text[s:e]
    hits = []
    for m in CLIP_RE.finditer(seg):
        end_tag = seg.index('</AudioClip>', m.end())
        block = seg[m.start():end_tag]
        cs = re.search(r'<CurrentStart Value="([^"]+)" />', block)
        if cs and abs(float(cs.group(1)) - start) < 1e-6 and '<MainSequencer>' not in block:
            hits.append((m.start(), end_tag, block))
    if len(hits) != 1:
        raise SystemExit(f'track #{ti}: expected one audio clip at CurrentStart {start}, found {len(hits)}')
    b0, b1, block = hits[0]
    ce = float(re.search(r'<CurrentEnd Value="([^"]+)" />', block).group(1))
    t_attr = float(CLIP_RE.match(block).group(1))
    new = CLIP_RE.sub(lambda m: m.group(0).replace(f'Time="{m.group(1)}"', f'Time="{fmt(t_attr + delta)}"'), block, count=1)
    new = re.sub(r'<CurrentStart Value="[^"]+" />', f'<CurrentStart Value="{fmt(start + delta)}" />', new, count=1)
    new = re.sub(r'<CurrentEnd Value="[^"]+" />', f'<CurrentEnd Value="{fmt(ce + delta)}" />', new, count=1)
    return text[:s] + seg[:b0] + new + seg[b1:] + text[e:]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source')
    ap.add_argument('outdir')
    ap.add_argument('--shift', action='append', help='"TRACK@START+DELTA" (default: the bar 90-91 plant)')
    a = ap.parse_args(argv)
    os.makedirs(a.outdir, exist_ok=True)
    src = os.path.abspath(a.source)
    snap = os.path.join(a.outdir, 'coven-snapshot.als')
    shutil.copyfile(src, snap)                       # read-only use of the source from here on

    with gzip.open(snap, 'rb') as f:
        text = f.read().decode('utf-8')
    root = alsio.load(snap)
    trs = alsio.tracks(root, snap)
    shifts = [alsio.parse_inject(trs, s) for s in (a.shift or DEFAULT_SHIFTS)]
    spans = track_spans(text)
    if len(spans) != len(trs):
        raise SystemExit(f'track count mismatch: text {len(spans)} vs parsed {len(trs)}')
    for ti, start, delta in shifts:
        text = plant(text, ti, start, delta, spans)
        spans = track_spans(text)
    out = os.path.join(a.outdir, 'planted-nudge.als')
    with open(out, 'wb') as f:
        f.write(gzip.compress(text.encode('utf-8'), mtime=0))

    allowed = dict(moves=[dict(track=ti, **{'from': st, 'to': st + d}) for ti, st, d in shifts])
    exp, problems = collateral.expected_after(collateral.from_als(snap), allowed)
    bad = problems + collateral.compare(exp, collateral.from_als(out))
    for b in bad:
        print('UNEXPECTED', b)
    if bad:
        return 1
    for ti, st, d in shifts:
        print(f'planted: #{ti} {trs[ti]["name"]!r} clip at {st} -> {st + d}')
    print(f'wrote {snap}\nwrote {out}\nFIXTURES OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
