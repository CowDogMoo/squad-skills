#!/usr/bin/env python3
"""Collateral check: prove the arrangement changed only by the allowed clip moves
(and loop_end gap fixes) and nothing else.

Compares every clip on every track (audio and MIDI: start, end, name, muted,
loop start) between a "before" and an "after" state. The before/after states
can each be a saved .als, or a get_arrangement_info snapshot (JSON) from Live;
--live reads the after state from Live's socket (opt-in, read-only).

    python3 collateral.py --before fix/pre_fix_snapshot.json --live --allowed fix/applied_moves.json
    python3 collateral.py --before before.als --after after.als --allowed fix/applied_moves.json   # offline

applied_moves.json (apply_moves.py writes it; hand-written is fine):
    {"moves": [{"track": 1, "from": 357.0625, "to": 357.0}],
     "loop_end": [{"track": 1, "start": 362.0, "end_to": 363.9578}]}

Exit codes: 0 COLLATERAL OK, 1 unexpected differences, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TOL = 1e-3     # beats


def _key(start, end, name, muted, loop_start, kind):
    return (float(start), float(end), name, bool(muted), float(loop_start), kind)


def _same(x, y):
    return x[2:4] == y[2:4] and x[5] == y[5] and all(abs(x[i] - y[i]) <= TOL for i in (0, 1, 4))


def _minus(xs, ys):
    """Multiset difference xs - ys with tolerant matching."""
    left = list(ys)
    out = []
    for x in xs:
        j = next((j for j, y in enumerate(left) if _same(x, y)), None)
        if j is None:
            out.append(x)
        else:
            left.pop(j)
    return out


def from_als(path):
    import alsio
    root = alsio.load(path)
    out = {}
    for t in alsio.tracks(root, path):
        if t['kind'] == 'GroupTrack':
            continue
        ks = [_key(c['start'], c['end'], c['name'], c['muted'], c['loop_start'], 'audio') for c in t['clips']]
        ks += [_key(c['start'], c['end'], c['name'], c['muted'], c['loop_start'], 'midi') for c in t['midi_clips']]
        out[t['index']] = (t['name'], list(ks))
    return out


def from_snapshot(info):
    out = {}
    for t in info['tracks']:
        if t.get('is_group_track'):
            continue
        ks = [_key(c['start_time'], c['end_time'], c['name'], c['muted'], c.get('loop_start', 0),
                   'audio' if c.get('is_audio') else 'midi') for c in t['arrangement_clips']]
        out[t['index']] = (t['name'], list(ks))
    return out


def load_state(path):
    if path.endswith('.json'):
        with open(path) as fh:
            return from_snapshot(json.load(fh))
    return from_als(path)


def expected_after(before, allowed):
    """Apply the allowed moves and loop_end changes to the before state."""
    exp = {ti: (name, list(c)) for ti, (name, c) in before.items()}
    problems = []
    for m in allowed.get('moves', []):
        ti, f, to = int(m['track']), float(m['from']), float(m['to'])
        if ti not in exp:
            problems.append(f'allowed move on unknown track {ti}')
            continue
        hit = [k for k in exp[ti][1] if abs(k[0] - f) < TOL]
        if len(hit) != 1:
            problems.append(f'allowed move #{ti} {f}->{to}: {len(hit)} clips start at {f} in the before state')
            continue
        k = hit[0]
        exp[ti][1].remove(k)
        exp[ti][1].append((to, k[1] + (to - k[0])) + k[2:])
    for g in allowed.get('loop_end', []):
        ti, st, end_to = int(g['track']), float(g['start']), float(g['end_to'])
        hit = [k for k in exp.get(ti, (None, []))[1] if abs(k[0] - st) < TOL]
        if len(hit) != 1:
            problems.append(f'allowed loop_end change #{ti} at {st}: {len(hit)} clips start there')
            continue
        k = hit[0]
        exp[ti][1].remove(k)
        exp[ti][1].append((k[0], end_to) + k[2:])
    return exp, problems


def compare(exp, after):
    bad = []
    for ti in sorted(set(exp) | set(after)):
        if ti not in after:
            bad.append(f'track {ti} {exp[ti][0]!r} missing after')
            continue
        if ti not in exp:
            bad.append(f'track {ti} {after[ti][0]!r} added')
            continue
        if exp[ti][0] != after[ti][0]:
            bad.append(f'track {ti} renamed {exp[ti][0]!r} -> {after[ti][0]!r}')
        gone = _minus(exp[ti][1], after[ti][1])
        new = _minus(after[ti][1], exp[ti][1])
        for k in sorted(gone):
            bad.append(f'track {ti} {exp[ti][0]!r}: expected clip missing/changed {k}')
        for k in sorted(new):
            bad.append(f'track {ti} {after[ti][0]!r}: unexpected clip {k}')
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--before', required=True, help='pre-fix state: .als or snapshot .json')
    ap.add_argument('--after', help='post-fix state: .als or snapshot .json')
    ap.add_argument('--live', action='store_true', help='read the after state from Live (socket, read-only)')
    ap.add_argument('--allowed', help='applied_moves.json; omit to require no change at all')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=9877)
    a = ap.parse_args(argv)
    if bool(a.after) == bool(a.live):
        print('give exactly one of --after FILE or --live')
        return 2
    before = load_state(a.before)
    if a.live:
        import live_socket as L
        after = from_snapshot(L.arrangement(a.host, a.port))
    else:
        after = load_state(a.after)
    allowed = {}
    if a.allowed:
        with open(a.allowed) as fh:
            allowed = json.load(fh)
    exp, problems = expected_after(before, allowed)
    bad = problems + compare(exp, after)
    for b in bad:
        print('UNEXPECTED', b)
    n_moves, n_le = len(allowed.get('moves', [])), len(allowed.get('loop_end', []))
    n_clips = sum(len(c) for _, c in after.values())
    print(f'tracks {len(before)} -> {len(after)}, clips after {n_clips}, allowed moves {n_moves}, loop_end changes {n_le}')
    if bad:
        return 1
    print('COLLATERAL OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
