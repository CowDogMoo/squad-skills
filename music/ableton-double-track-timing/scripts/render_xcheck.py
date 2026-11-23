#!/usr/bin/env python3
"""Second opinion from amp-rendered stems: per-clip offsets between doubles measured
on what you actually hear, merged with the DI result. Offline, read-only.

Render one stem per doubled track from Live (the ableton-live-computer-use skill
has the export recipe; one track at a time, typed render start, nothing left
selected). Give each stem with the arrangement beat its render started at:

    python3 render_xcheck.py SET.als --pair "Jayson Scratch=Jason Scratch" \
        --stem "Jayson Scratch=renders/jayson.wav@120" --stem "Jason Scratch=renders/jason.wav@120" \
        --di-json di.json --json xcheck.json

Render start bar N in Live's export dialog = beat (N-1)*4 in 4/4. Several stems
per track are allowed; a later --stem overrides an earlier one over its span
(handy for re-rendering one fixed section).

A clip counts as an agreed problem only when both methods say >= 15 ms, in the
same direction, within 10 ms of each other. Dense 16th/32nd riffs alias (periods
125/62.5 ms), so one method alone often contradicts the other; "contradict" rows
are listed so you can decide by ear.

    --control-shift-ms 30   positive control: shift the second side's stems by 30 ms
                            and require the render lags to follow
    --explained HANDOFF.md  gate: every agreed problem needs "- audio track N start S: why"

Exit codes: 0 ok / CONTROL OK / AUDIO OK, 1 control failed or problems unexplained, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alsio  # noqa: E402
import attack_audit as A  # noqa: E402

_STEM = re.compile(r'^(?P<track>.+?)=(?P<file>.+)@(?P<beat>-?\d+(?:\.\d+)?)$')


def parse_stems(trs, specs):
    out = {}
    for s in specs:
        m = _STEM.match(s.strip())
        if not m:
            raise SystemExit(f'--stem wants "TRACK=FILE@BEAT", got {s!r}')
        f = os.path.expanduser(m.group('file'))
        if not os.path.exists(f):
            raise SystemExit(f'--stem file not found: {f}')
        out.setdefault(alsio.resolve_track(trs, m.group('track')), []).append((f, float(m.group('beat'))))
    return out


def render_env(stems, tm, n, gate_db, shift_ms=0.0, fs=A.FS):
    """Rendered level (dB) on the arrangement grid; returns (env, covered mask)."""
    import soundfile as sf
    env = np.full(n, gate_db)
    cov = np.zeros(n, dtype=bool)
    for path, beat in stems:                     # later stems overwrite earlier ones
        y, sr = sf.read(path, dtype='float32', always_2d=True)
        y = y.mean(axis=1)
        h = max(1, int(round(sr / fs)))
        m = len(y) // h
        db = 20 * np.log10(np.sqrt((y[:m * h].reshape(m, h).astype(np.float64) ** 2).mean(axis=1)) + 1e-9)
        db[db < gate_db] = gate_db
        rate = sr / h
        t0 = tm.b2s(beat) + shift_ms / 1000.0
        i0 = max(0, int(np.ceil(t0 * fs)))
        i1 = min(n, int(np.floor((t0 + m / rate) * fs)))
        if i1 <= i0:
            continue
        k = np.floor((np.arange(i0, i1) / fs - t0) * rate).astype(np.int64)
        k = np.clip(k, 0, m - 1)
        env[i0:i1] = db[k]
        cov[i0:i1] = True
    return env, cov


def render_rows(trs, pairs, tm, stems, a, shift_side=None, shift_ms=0.0):
    ids = sorted({i for p in pairs for i in p})
    n = A.grid_len(tm, trs, ids)
    renv, rcov = {}, {}
    for ti in ids:
        sh = shift_ms if (shift_side is not None and ti in shift_side) else 0.0
        renv[ti], rcov[ti] = render_env(stems[ti], tm, n, a.render_gate_db, sh)
    ratt = {ti: A.attack(e) for ti, e in renv.items()}
    rows = []
    for pa, pb in pairs:
        for me, other in ((pa, pb), (pb, pa)):
            for c in trs[me]['clips']:
                if not alsio.usable(c):
                    continue
                if a.range and not (c['start'] < a.range[1] and a.range[0] < c['end']):
                    continue
                t0, t1 = tm.b2s(c['start']), tm.b2s(c['end'])
                i0, i1 = int(np.ceil(t0 * A.FS)), int(np.ceil(t1 * A.FS))
                if t1 - t0 < 0.25 or i1 <= i0 or min(rcov[me][i0:i1].mean(), rcov[other][i0:i1].mean()) < 0.95:
                    continue
                lg, cr = A.xc_lag(ratt[other][i0:i1], ratt[me][i0:i1], a.window_ms)
                rows.append(dict(pair=f'{trs[pa]["name"]} = {trs[pb]["name"]}', track=me, track_name=trs[me]['name'],
                                 partner=other, start=round(c['start'], 4), end=round(c['end'], 4), clip=c['name'],
                                 bars=f'{alsio.bar_beat(c["start"], a.beats_per_bar)}-'
                                      f'{alsio.bar_beat(c["end"], a.beats_per_bar)}',
                                 render_ms=None if lg is None else round(lg, 1), render_corr=round(cr, 2)))
    return rows


def di_rows(args, trs, pairs, tm):
    if args.di_json:
        with open(args.di_json) as fh:
            return json.load(fh)['rows']
    ids = sorted({i for p in pairs for i in p})
    env, att, cov = A.build(trs, ids, tm, args.gate_db)
    rows, _ = A.measure(trs, pairs, tm, env, att, args.window_ms, cov=cov, floor=A.floor_for(args.gate_db))
    return rows


def merge(rrows, drows, a):
    di = {(r['track'], round(r['start'], 3)): r for r in drows}
    for r in rrows:
        d = di.get((r['track'], round(r['start'], 3)))
        r['di_ms'] = d['lag_ms'] if d else None
        r['di_corr'] = d['corr'] if d else None
        dl, rl = r['di_ms'], r['render_ms']
        both_big = dl is not None and rl is not None and abs(dl) >= a.agree_min_ms and abs(rl) >= a.agree_min_ms
        r['agreed'] = bool(both_big and np.sign(dl) == np.sign(rl) and abs(dl - rl) <= a.agree_tol_ms)
        r['contradict'] = bool(both_big and np.sign(dl) != np.sign(rl))
    return rrows


def explained_keys(path):
    pat = re.compile(r'^\s*[-*]\s*audio\S*\s+track\s+#?(\d+)\s+start\s+(-?[0-9.]+)\s*:', re.I)
    keys = set()
    with open(path) as fh:
        for line in fh:
            m = pat.match(line)
            if m:
                keys.add((int(m.group(1)), float(m.group(2))))
    return keys


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('als')
    ap.add_argument('--stem', action='append', default=[], required=True, help='"TRACK=FILE@BEAT"; repeatable')
    ap.add_argument('--pair', action='append', default=[], help='double "A=B"; auto L/R pairs are added unless --no-auto')
    ap.add_argument('--no-auto', action='store_true')
    ap.add_argument('--di-json', help='attack_audit.py --json output (computed fresh if omitted)')
    ap.add_argument('--window-ms', type=float, default=25.0)
    ap.add_argument('--gate-db', type=float, default=-25.0, help='DI gate when computing DI fresh')
    ap.add_argument('--render-gate-db', type=float, default=-45.0, help='rendered level treated as silence (default -45)')
    ap.add_argument('--agree-min-ms', type=float, default=15.0)
    ap.add_argument('--agree-tol-ms', type=float, default=10.0)
    ap.add_argument('--range', nargs=2, type=float, metavar=('START', 'END'))
    ap.add_argument('--control-shift-ms', type=float, help='positive control: shift the second side of each pair by this')
    ap.add_argument('--explained', help='HANDOFF.md; agreed problems need "- audio track N start S: why" lines')
    ap.add_argument('--beats-per-bar', type=float, default=4)
    ap.add_argument('--json')
    a = ap.parse_args(argv)

    root = alsio.load(a.als)
    trs = alsio.tracks(root, a.als)
    tm = alsio.tempo_map(root, trs)
    stems = parse_stems(trs, a.stem)
    pairs, _ = alsio.pairs_from_args(trs, a.pair, auto=not a.no_auto)
    pairs = [p for p in pairs if p[0] in stems and p[1] in stems]
    if not pairs:
        print('no pair has stems on both sides; give --stem for both tracks of a --pair')
        return 2

    if a.control_shift_ms:
        side_b = {p[1] for p in pairs}
        before = render_rows(trs, pairs, tm, stems, a)
        after = render_rows(trs, pairs, tm, stems, a, shift_side=side_b, shift_ms=a.control_shift_ms)
        caught, missed = 0, []
        after_by = {(r['track'], r['start']): r for r in after}
        for r0 in before:
            r1 = after_by.get((r0['track'], r0['start']))
            if r1 is None or r0['render_ms'] is None or r1['render_ms'] is None:
                continue
            sign = 1 if r0['track'] in side_b else -1
            expect = float(np.clip(r0['render_ms'] + sign * a.control_shift_ms, -a.window_ms, a.window_ms))
            if abs(r1['render_ms'] - expect) <= 6.0:
                caught += 1
            else:
                missed.append(r0)
                print(f'unresolvable #{r0["track"]} {r0["start"]} (bar {r0["bars"]}): render lag {r0["render_ms"]:+.1f} -> '
                      f'{r1["render_ms"]:+.1f} ms (expected about {expect:+.1f})')
        n = caught + len(missed)
        ok = n > 0 and caught >= 0.8 * n
        print(f'render control: shifted side B by {a.control_shift_ms:+g} ms; caught {caught}/{n} clips '
              f'(pass needs >= 80%). Unresolvable clips alias at this size: trust neither method there.')
        print('CONTROL OK' if ok else 'CONTROL FAILED')
        return 0 if ok else 1

    rows = merge(render_rows(trs, pairs, tm, stems, a), di_rows(a, trs, pairs, tm), a)
    print(f'render cross-check: window +-{a.window_ms:g} ms; agreed = both >= {a.agree_min_ms:g} ms, '
          f'same direction, within {a.agree_tol_ms:g} ms')
    print('lag = how far the clip trails its double (+ late, - early)\n')
    for r in sorted(rows, key=lambda r: (r['pair'], r['start'], r['track'])):
        dl = 'n/a' if r['di_ms'] is None else f'{r["di_ms"]:+6.1f} c{r["di_corr"]:.2f}'
        rl = 'n/a' if r['render_ms'] is None else f'{r["render_ms"]:+6.1f} c{r["render_corr"]:.2f}'
        mark = 'AGREED' if r['agreed'] else ('contradict' if r['contradict'] else '')
        print(f'#{r["track"]:<3} {r["track_name"][:18]:18s} {r["start"]:9.4f}-{r["end"]:9.4f} bar {r["bars"]:<22s} '
              f'"{r["clip"][:18]}"'.ljust(96) + f' DI {dl:>12s} | render {rl:>12s}  {mark}')
    ag = [r for r in rows if r['agreed']]
    print(f'\nclips compared {len(rows)}, agreed problems {len(ag)}, contradictions {sum(r["contradict"] for r in rows)}')
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(dict(set=os.path.abspath(a.als), rows=rows), fh, indent=1)
    if a.explained:
        keys = explained_keys(a.explained)
        miss = [r for r in ag if not any(k[0] == r['track'] and abs(k[1] - r['start']) < 1e-3 for k in keys)]
        for r in miss:
            print(f'UNRESOLVED audio track {r["track"]} start {r["start"]} ({r["track_name"]}, bar {r["bars"]})')
        if miss or not rows:
            return 1
        print('AUDIO OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
