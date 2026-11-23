#!/usr/bin/env python3
"""Per-clip timing offsets between doubled tracks, measured from the source audio
(DI recordings) through the set's warp markers and tempo map. Offline, read-only.

For each pair, every clip's source audio is mapped onto the arrangement time grid
(500 Hz) through its warp markers, turned into a level envelope with a gate
(DI below -25 dBFS counts as silence: an amp's input gate hears nothing there),
and then into an attack curve (rising edges = pick attacks). Over each clip's
span, the attack curves of the two sides are cross-correlated in a narrow
window (+-25 ms by default); the peak lag is how far that clip trails its
double (positive = late, negative = early).

Dense 16th/32nd riffs repeat every 125/62.5 ms, so a wide window can lock onto
the wrong attack: keep the window narrow and treat a single-method result as a
lead. Confirm with render_xcheck.py (amp renders) or by ear before moving.

    python3 attack_audit.py SET.als                                   # auto L/R pairs
    python3 attack_audit.py SET.als --pair "Jayson Scratch=Jason Scratch" --json di.json
    python3 attack_audit.py SET.als --pair "A=B" --range 336 368      # only clips in beats 336-368
    python3 attack_audit.py SET.als --pair "A=B" --inject "A@357+0.0625"   # positive control

Exit codes: 0 ok / CONTROL OK, 1 control failed, 2 usage error.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alsio  # noqa: E402

FS = 500.0                  # envelope rate: 2 ms grid
FLOOR = alsio.FLOOR_DB


def floor_for(gate_db):
    """Level written for 'silent' frames: -60 dB, or 20 dB under a very low gate."""
    return min(FLOOR, gate_db - 20.0)


# ---------------------------------------------------------------- envelopes

@functools.lru_cache(maxsize=None)
def file_env(path, gate_db, fs=FS):
    """Level envelope (dB) of an audio file at ~fs Hz, gated; returns (db, rate)."""
    import soundfile as sf
    y, sr = sf.read(path, dtype='float32', always_2d=True)
    y = y.mean(axis=1)
    h = max(1, int(round(sr / fs)))
    n = len(y) // h
    e = np.sqrt((y[:n * h].reshape(n, h).astype(np.float64) ** 2).mean(axis=1))
    db = 20 * np.log10(e + 1e-9)
    db[db < gate_db] = floor_for(gate_db)
    return db, sr / h


def grid_len(tm, trs, track_ids, fs=FS):
    end = max([c['end'] for ti in track_ids for c in trs[ti]['clips']] + [4.0])
    return int(np.ceil(tm.b2s(end) * fs)) + 1


def track_env(trs, ti, tm, n, gate_db, fs=FS):
    """Source-audio level (dB) of one track on the arrangement time grid."""
    fl = floor_for(gate_db)
    out = np.full(n, fl)
    for c in trs[ti]['clips']:
        if not alsio.usable(c):
            continue
        i0 = int(np.ceil(tm.b2s(c['start']) * fs))
        i1 = min(int(np.ceil(tm.b2s(c['end']) * fs)), n)
        if i1 <= i0:
            continue
        x = tm.s2b(np.arange(i0, i1) / fs)
        s = alsio.clip_file_secs(c, x, tm)
        db, rate = file_env(c['file'], gate_db)
        k = np.floor(s * rate).astype(np.int64)
        ok = (k >= 0) & (k < len(db))
        vals = np.full(len(k), fl)
        vals[ok] = db[k[ok]]
        out[i0:i1] = np.maximum(out[i0:i1], vals)
    return out


def track_cov(trs, ti, tm, n, fs=FS):
    """True where the track has a usable clip playing (independent of level)."""
    cov = np.zeros(n, dtype=bool)
    for c in trs[ti]['clips']:
        if alsio.usable(c):
            i0 = int(np.ceil(tm.b2s(c['start']) * fs))
            i1 = min(int(np.ceil(tm.b2s(c['end']) * fs)), n)
            cov[i0:max(i0, i1)] = True
    return cov


def attack(env):
    """Rising edges of a dB envelope, lightly smoothed (sigma 3 ms): pick attacks."""
    d = np.diff(env, prepend=env[0])
    d[d < 0] = 0
    g = np.exp(-0.5 * (np.arange(-4, 5) / 1.5) ** 2)
    return np.convolve(d, g / g.sum(), 'same')


def xc_lag(a, b, max_lag_ms, fs=FS):
    """(lag ms by which b trails a, normalised peak correlation); (None, 0) if either is silent."""
    L = int(round(max_lag_ms / 1000 * fs))
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return None, 0.0
    best = (-2.0, 0)
    for lag in range(-L, L + 1):
        x = a[max(0, -lag):len(a) - max(0, lag)]
        y = b[max(0, lag):len(b) - max(0, -lag)]
        c = float(np.dot(x, y)) / (na * nb)
        if c > best[0]:
            best = (c, lag)
    return best[1] / fs * 1000, best[0]


# ---------------------------------------------------------------- measurement

def measure(trs, pairs, tm, env, att, window_ms, fs=FS, rng=None, bpb=4,
            min_span_s=0.25, min_joint=0.05, cov=None, floor=FLOOR):
    """Per-clip rows for both sides of every pair, plus a whole-pair summary.

    env/att: {track index: array} on the same grid. A clip is measured when it is
    at least min_span_s long and both sides sound together (above the gate) for
    >= min_joint of it. cov: {track index: clip-coverage mask} for the overall lag.
    """
    rows, summary = [], []
    for a, b in pairs:
        act = {ti: env[ti] > floor for ti in (a, b)}
        both = act[a] & act[b]
        overlap = (cov[a] & cov[b]) if cov else np.ones(len(env[a]), dtype=bool)
        if overlap.any() and both.any():
            lag, corr = xc_lag(att[a] * overlap, att[b] * overlap, window_ms, fs)
        else:
            lag, corr = None, 0.0
        summary.append(dict(a=a, b=b, a_name=trs[a]['name'], b_name=trs[b]['name'],
                            overlap_s=round(overlap.sum() / fs, 1), sounding_s=round(both.sum() / fs, 1),
                            overall_lag_ms=lag, overall_corr=round(corr, 2)))
        for me, other in ((a, b), (b, a)):
            for c in trs[me]['clips']:
                if not alsio.usable(c):
                    continue
                if rng and not (c['start'] < rng[1] and rng[0] < c['end']):
                    continue
                t0, t1 = tm.b2s(c['start']), tm.b2s(c['end'])
                i0, i1 = int(np.ceil(t0 * fs)), int(np.ceil(t1 * fs))
                if t1 - t0 < min_span_s or i1 <= i0:
                    continue
                joint = float((act[me][i0:i1] & act[other][i0:i1]).mean())
                if joint < min_joint:
                    continue
                lg, cr = xc_lag(att[other][i0:i1], att[me][i0:i1], window_ms, fs)
                if lg is None:
                    continue
                rows.append(dict(pair=f'{trs[a]["name"]} = {trs[b]["name"]}', track=me, track_name=trs[me]['name'],
                                 partner=other, partner_name=trs[other]['name'],
                                 start=round(c['start'], 4), end=round(c['end'], 4), clip=c['name'],
                                 bars=f'{alsio.bar_beat(c["start"], bpb)}-{alsio.bar_beat(c["end"], bpb)}',
                                 joint=round(joint, 2), lag_ms=round(lg, 1), corr=round(cr, 2),
                                 at_edge=bool(abs(lg) >= window_ms - 1000 / fs)))
    return rows, summary


def build(trs, track_ids, tm, gate_db, fs=FS):
    """(env, att, cov) dicts keyed by track index, all on one arrangement-time grid."""
    n = grid_len(tm, trs, track_ids, fs)
    env = {ti: track_env(trs, ti, tm, n, gate_db, fs) for ti in track_ids}
    att = {ti: attack(e) for ti, e in env.items()}
    cov = {ti: track_cov(trs, ti, tm, n, fs) for ti in track_ids}
    return env, att, cov


def flag_rows(rows, min_ms, min_corr):
    for r in rows:
        r['flag'] = bool(abs(r['lag_ms']) >= min_ms and r['corr'] >= min_corr)
    return rows


def print_report(rows, summary, trs, a):
    print(f'DI attack audit: window +-{a.window_ms:g} ms, gate {a.gate_db:g} dBFS, '
          f'flag at |lag| >= {a.min_ms:g} ms with corr >= {a.min_corr:g}')
    print('lag = how far the clip trails its double (+ late, - early); "edge" = at the window limit, unreliable\n')
    for s in summary:
        ol = 'n/a' if s['overall_lag_ms'] is None else f'{s["overall_lag_ms"]:+.1f} ms (corr {s["overall_corr"]:.2f})'
        print(f'pair #{s["a"]} {s["a_name"]} = #{s["b"]} {s["b_name"]}: '
              f'#{s["b"]} trails #{s["a"]} overall by {ol}; clips overlap {s["overlap_s"]} s, '
              f'both above the gate {s["sounding_s"]} s')
        mine = [r for r in rows if r['pair'] == f'{s["a_name"]} = {s["b_name"]}']
        if not mine and s['overlap_s'] > 0:
            print(f'   no clip measurable: too little audio above the {a.gate_db:g} dBFS gate on one side '
                  '(quiet DI, or not a DI). Re-run this pair with a lower --gate-db (e.g. -40).')
        for r in sorted(mine, key=lambda r: (r['start'], r['track'])):
            mark = ('FLAG' if r['flag'] else '') + (' edge' if r['at_edge'] else '')
            print(f'   #{r["track"]:<3} {r["track_name"][:18]:18s} {r["start"]:9.4f}-{r["end"]:9.4f} '
                  f'bar {r["bars"]:<22s} "{r["clip"][:20]}"'.ljust(98) +
                  f' {r["lag_ms"]:+6.1f} ms  corr {r["corr"]:.2f}  {mark}')
        print()
    fl = [r for r in rows if r['flag']]
    print(f'clips measured {len(rows)}, flagged {len(fl)} (single method: confirm before moving)')


def run_control(trs, pairs, tm, injections, a):
    ids = sorted({i for p in pairs for i in p})
    for ti, start, delta in injections:
        if ti not in ids:
            print(f'FAIL {alsio.tname(trs, ti)} is not in any analysed pair')
            return False
    env, att, cov = build(trs, ids, tm, a.gate_db)
    real, _ = measure(trs, pairs, tm, env, att, a.window_ms, cov=cov, floor=floor_for(a.gate_db))
    t2 = alsio.apply_inject(trs, injections)
    env2, att2, cov2 = build(t2, ids, tm, a.gate_db)
    inj, _ = measure(t2, pairs, tm, env2, att2, a.window_ms, cov=cov2, floor=floor_for(a.gate_db))
    ok = True
    for ti, start, delta in injections:
        before = [r for r in real if r['track'] == ti and abs(r['start'] - start) < 1e-3]
        after = [r for r in inj if r['track'] == ti and abs(r['start'] - (start + delta)) < 1e-3]
        if not before or not after:
            print(f'FAIL {alsio.tname(trs, ti)} @ {start}: clip not measurable (too short or partner silent there)')
            ok = False
            continue
        # The shift is heard where the clip plays, so convert it at the clip's midpoint tempo,
        # not at its start (a clip starting on a tempo change would otherwise get the old tempo).
        mid = (before[0]['start'] + before[0]['end']) / 2.0
        d_ms = tm.beats_to_ms(mid, delta)
        b0, a0 = before[0]['lag_ms'], after[0]['lag_ms']
        raw_expect = b0 + d_ms
        expect = float(np.clip(raw_expect, -a.window_ms, a.window_ms))
        # Pass when the lag follows the injected shift, wherever it lands: a shift that cancels an
        # existing lag is tracked just as well as one that creates a flag. A shift big enough to
        # matter is still required, and an expectation past the window edge cannot be confirmed.
        good = (abs(a0 - expect) <= 6.0 and abs(d_ms) >= a.min_ms * 0.5
                and abs(raw_expect) < a.window_ms - 1.0)
        print(f'{"caught " if good else "MISSED "} {alsio.tname(trs, ti)} @ {start}{delta:+g} beat ({d_ms:+.1f} ms): '
              f'lag {b0:+.1f} -> {a0:+.1f} ms (expected about {expect:+.1f}), corr {after[0]["corr"]:.2f}')
        if not good:
            print('         the DI method cannot resolve a slip of this size here (dense or periodic attacks alias '
                  'inside the window): rely on placement_check.py, a render cross-check, or ears for this region')
        ok &= good
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('als')
    ap.add_argument('--pair', action='append', default=[], help='double "A=B" (names or #index); repeatable')
    ap.add_argument('--no-auto', action='store_true', help='only the --pair doubles, no auto L/R pairs')
    ap.add_argument('--window-ms', type=float, default=25.0, help='max lag searched (default 25)')
    ap.add_argument('--gate-db', type=float, default=-25.0, help='source level treated as silence (default -25 dBFS, for DI)')
    ap.add_argument('--min-ms', type=float, default=15.0, help='flag threshold (default 15 ms)')
    ap.add_argument('--min-corr', type=float, default=0.3, help='flag only when peak correlation >= this (default 0.3)')
    ap.add_argument('--range', nargs=2, type=float, metavar=('START', 'END'), help='only clips overlapping these beats')
    ap.add_argument('--inject', action='append', default=[],
                    help='positive control "TRACK@START+DELTA": shift that clip in a copy and require the lag to follow')
    ap.add_argument('--beats-per-bar', type=float, default=4)
    ap.add_argument('--json', help='write rows and pair summaries here (render_xcheck.py --di-json reads it)')
    a = ap.parse_args(argv)

    root = alsio.load(a.als)
    trs = alsio.tracks(root, a.als)
    tm = alsio.tempo_map(root, trs)
    pairs, notes = alsio.pairs_from_args(trs, a.pair, auto=not a.no_auto)
    if not pairs:
        print('no pairs: name doubles "X L"/"X R" or pass --pair "A=B"')
        return 2
    missing = sorted({os.path.basename(c['file'] or '?') for p in pairs for ti in p for c in trs[ti]['clips']
                      if not c['muted'] and not c['file_exists']})
    if missing:
        print(f'warning: {len(missing)} source files not found; their clips are skipped: {missing[:5]}')

    if a.inject:
        injections = [alsio.parse_inject(trs, s) for s in a.inject]
        ok = run_control(trs, pairs, tm, injections, a)
        print('CONTROL OK' if ok else 'CONTROL FAILED')
        return 0 if ok else 1

    ids = sorted({i for p in pairs for i in p})
    env, att, cov = build(trs, ids, tm, a.gate_db)
    rows, summary = measure(trs, pairs, tm, env, att, a.window_ms, rng=a.range, bpb=a.beats_per_bar, cov=cov,
                            floor=floor_for(a.gate_db))
    flag_rows(rows, a.min_ms, a.min_corr)
    for n in notes:
        print('note:', n)
    print_report(rows, summary, trs, a)
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(dict(set=os.path.abspath(a.als), method='di', window_ms=a.window_ms, gate_db=a.gate_db,
                           pairs=summary, rows=rows), fh, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
