#!/usr/bin/env python3
"""Exact placement check: find copies of a take sitting a fraction of a beat off
the other copies of that take. Offline, from the saved .als only.

Every arrangement audio clip plays a window of one audio file. Its anchor,
start minus start marker (beats), is where that file's beat 0 lands. Copies
of a take moved by whole beats or bars keep the same fractional anchor; a copy
whose fraction differs was nudged, or deliberately re-timed. That is how a
+0.0625-beat (31 ms at 120 BPM) accidental nudge that made two doubled guitars
flam was caught. A flag is a lead, not a verdict: confirm with audio before
moving anything, and explain the flags you leave alone.

    python3 placement_check.py SET.als
    python3 placement_check.py SET.als --pair "Jayson Scratch=Jason Scratch" --json flags.json
    python3 placement_check.py SET.als --inject "Jayson Scratch@357+0.0625"     # positive control
    python3 placement_check.py SET.als --explained HANDOFF.md                   # gate: all flags explained

Exit codes: 0 ok (or CONTROL OK / PLACEMENT OK), 1 control failed or flags unexplained, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alsio  # noqa: E402


def _frac(x):
    return round(((x % 1.0) + 1.0) % 1.0, 4)


def _circ(a, b):
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def _signed(v, ref):
    return round(((v - ref + 0.5) % 1.0) - 0.5, 4)


def _same_warp(a, b, tol=1e-3):
    wa, wb = a['warp_markers'], b['warp_markers']
    return len(wa) == len(wb) and all(abs(x[0] - y[0]) <= tol and abs(x[1] - y[1]) <= tol for x, y in zip(wa, wb))


def groups_for(trs, track_ids):
    """{(track, file, k): [clips]}: placement-usable copies of one take with the same warp markers.

    Copies that were re-warped (different markers) map audio to beats differently,
    so their anchors are not comparable; they form their own group (k = 1, 2, ...).
    """
    g = {}
    for ti in track_ids:
        for c in trs[ti]['clips']:
            if not alsio.placement_usable(c):
                continue
            k = 0
            while (ti, c['file'], k) in g and not _same_warp(g[(ti, c['file'], k)][0], c):
                k += 1
            g.setdefault((ti, c['file'], k), []).append(c)
    return g


def rewarped_takes(groups):
    """[(track, file, n_variants)] for takes whose copies carry different warp markers."""
    n = Counter((ti, f) for ti, f, _ in groups)
    return sorted((ti, os.path.basename(f), k) for (ti, f), k in n.items() if k > 1)


def detect(trs, track_ids, tol=0.005):
    """Return (flags, stats). A flag is one clip whose anchor fraction differs from its group's reference."""
    flags = []
    stats = dict(groups=0, multi_copy_groups=0, clips=0)
    groups = groups_for(trs, track_ids)
    stats['rewarped'] = rewarped_takes(groups)
    for (ti, f, _), cs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        stats['groups'] += 1
        stats['clips'] += len(cs)
        if len(cs) < 2:
            continue
        stats['multi_copy_groups'] += 1
        fr = [_frac(alsio.anchor(c)) for c in cs]
        # cluster fractions within tol, count members per cluster
        counts = Counter()
        reps = []
        for v in fr:
            for r in reps:
                if _circ(v, r) <= tol:
                    counts[r] += 1
                    break
            else:
                reps.append(v)
                counts[v] += 1
        top = max(counts.values())
        cands = [r for r in reps if counts[r] == top]
        ref = min(cands, key=lambda r: (min(r, 1 - r), reps.index(r)))   # tie -> anchor nearest the beat grid
        tie = len(cands) > 1
        for c, v in zip(cs, fr):
            if _circ(v, ref) <= tol:
                continue
            off = _signed(v, ref)
            others = [o['start'] for o, w in zip(cs, fr) if _circ(w, ref) <= tol]
            flags.append(dict(track=ti, track_name=trs[ti]['name'], start=round(c['start'], 4),
                              end=round(c['end'], 4), clip=c['name'], file=os.path.basename(f),
                              anchor_frac=v, group_frac=ref, off_beats=off, n_in_group=len(cs),
                              reference_copies=[round(x, 4) for x in others], tie=tie,
                              suggest_start=round(c['start'] - off, 4)))
    return flags, stats


def group_id(groups, ti, c):
    for (t, f, k), cs in groups.items():
        if t == ti and any(x is c for x in cs):
            return (f, k)
    return None


def detect_pairs(trs, pairs, tol=0.005, single=None):
    """Double-vs-double check: wherever the same two takes play together (same take on
    side A, same take on side B), their relative anchor should be the same. An
    occurrence whose relative anchor differs means one side moved against the other.
    """
    flags = []
    single = single or []
    single_keys = {(f['track'], round(f['start'], 4)) for f in single}
    for a, b in pairs:
        groups = groups_for(trs, [a, b])
        occ = {}
        for ca in trs[a]['clips']:
            if not alsio.placement_usable(ca):
                continue
            for cb in trs[b]['clips']:
                if not alsio.placement_usable(cb) or not (ca['start'] < cb['end'] and cb['start'] < ca['end']):
                    continue
                key = (group_id(groups, a, ca), group_id(groups, b, cb))
                occ.setdefault(key, []).append((ca, cb, _frac(alsio.anchor(ca) - alsio.anchor(cb))))
        for key, items in occ.items():
            if len(items) < 2:
                continue
            clusters = []                       # [rel fraction, [items]]
            for it in items:
                cl = next((cl for cl in clusters if _circ(it[2], cl[0]) <= tol), None)
                if cl is None:
                    clusters.append([it[2], [it]])
                else:
                    cl[1].append(it)
            top = max(len(cl[1]) for cl in clusters)
            cands = [cl for cl in clusters if len(cl[1]) == top]

            def nflags(cl):
                return sum(((a, round(x['start'], 4)) in single_keys) + ((b, round(y['start'], 4)) in single_keys)
                           for x, y, _ in cl[1]) / len(cl[1])
            # tie -> the pairing whose clips sit on their own takes' anchors, then the on-grid relation
            ref = min(cands, key=lambda cl: (nflags(cl), min(cl[0], 1 - cl[0]), clusters.index(cl)))
            ra, rb, _ = ref[1][0]
            for ca, cb, v in items:
                if _circ(v, ref[0]) <= tol:
                    continue
                da = _signed(_frac(alsio.anchor(ca)), _frac(alsio.anchor(ra)))
                db = _signed(_frac(alsio.anchor(cb)), _frac(alsio.anchor(rb)))
                if abs(da) > tol and abs(db) <= tol:
                    who = (f'{alsio.tname(trs, a)} moved ({da:+.4f} beat vs its copy at {round(ra["start"], 4)}); '
                           f'the {trs[b]["name"]} clip matches its copy at {round(rb["start"], 4)}')
                elif abs(db) > tol and abs(da) <= tol:
                    who = (f'{alsio.tname(trs, b)} moved ({db:+.4f} beat vs its copy at {round(rb["start"], 4)}); '
                           f'the {trs[a]["name"]} clip matches its copy at {round(ra["start"], 4)}')
                else:
                    who = f'both sides differ from their copies ({da:+.4f} / {db:+.4f} beat): decide by ear'
                flags.append(dict(a=a, b=b, a_name=trs[a]['name'], b_name=trs[b]['name'],
                                  a_start=round(ca['start'], 4), b_start=round(cb['start'], 4),
                                  a_clip=ca['name'], b_clip=cb['name'], rel_off_beats=_signed(v, ref[0]),
                                  same_pairing_at=[(round(x['start'], 4), round(y['start'], 4)) for x, y, _ in ref[1]],
                                  tie=len(cands) > 1, who=who))
    return flags


def annotate(flags, trs, tm, pairs, bpb, tol=0.005):
    partner = {}
    for a, b in pairs:
        partner[a], partner[b] = b, a
    for f in flags:
        off = f['off_beats']
        f['bar'] = alsio.bar_beat(f['start'], bpb)
        f['off_ms'] = round(tm.beats_to_ms(f['start'] - off, off), 1)
        grid16 = abs(off / 0.25 - round(off / 0.25)) * 0.25 <= tol
        f['kind'] = ('16th-grid shift: looks like a deliberate rhythmic edit or slice'
                     if grid16 else 'sub-16th shift: an accidental nudge or a manual timing fix; confirm by ear')
        notes = []
        same_group = [g for g in flags if g is not f and g['track'] == f['track'] and g['file'] == f['file']
                      and abs(g['off_beats'] - off) <= tol]
        if same_group:
            notes.append(f'same offset on {len(same_group) + 1} copies of this take '
                         f'({", ".join(str(g["start"]) for g in same_group)}): a repeated edit pattern?')
        together = [g for g in flags if g is not f and g['track'] == f['track'] and g['file'] != f['file']
                    and abs(g['off_beats'] - off) <= tol and abs(g['start'] - f['start']) <= 2 * bpb]
        if together:
            notes.append('same offset as ' + ', '.join(f'{g["start"]} ({g["clip"]}, other take)' for g in together)
                         + ': nudged together as one selection?')
        p = partner.get(f['track'])
        if p is not None:
            f['partner'] = alsio.tname(trs, p)
        if f['tie']:
            notes.append(f'only {f["n_in_group"]} copies split evenly; the on-grid anchor was taken as the reference')
        f['notes'] = notes
    return flags


def print_flags(flags, trs, stats, skipped):
    print(f'placement flags: {len(flags)}  (tracks checked: {stats["tracks"]}, takes: {stats["groups"]}, '
          f'takes with >=2 copies: {stats["multi_copy_groups"]}, clips: {stats["clips"]})')
    if skipped:
        print('  not checked: ' + '; '.join(f'{k} {v}' for k, v in skipped.items() if v))
    for ti, f, k in stats.get('rewarped', []):
        print(f'  note: {alsio.tname(trs, ti)} take {f} has copies with {k} different warp-marker sets '
              f'(re-warped slices); each set is compared only with itself')
    for f in flags:
        sign = 'late' if f['off_beats'] > 0 else 'early'
        print(f'\n#{f["track"]} {f["track_name"]}  start {f["start"]} (bar {f["bar"]}) - {f["end"]}  '
              f'"{f["clip"]}"  take {f["file"]}')
        print(f'   off {f["off_beats"]:+.4f} beat = {f["off_ms"]:+.1f} ms {sign} vs its other copies at '
              f'{f["reference_copies"]} -> if wrong, move to {f["suggest_start"]}')
        print(f'   {f["kind"]}')
        for n in f['notes']:
            print(f'   - {n}')


def print_pair_flags(pflags, tm, bpb):
    print(f'\npair alignment flags (the same two takes sit differently against each other elsewhere): {len(pflags)}')
    for f in pflags:
        st = max(f['a_start'], f['b_start'])
        ms = tm.beats_to_ms(st, f['rel_off_beats'])
        print(f'\n#{f["a"]} {f["a_name"]} @ {f["a_start"]}  vs  #{f["b"]} {f["b_name"]} @ {f["b_start"]}  (bar {alsio.bar_beat(st, bpb)})')
        print(f'   relative to #{f["b"]}, #{f["a"]} is {f["rel_off_beats"]:+.4f} beat ({ms:+.1f} ms) off from how these same '
              f'two takes line up at {f["same_pairing_at"]}'
              + (' (only two pairings: the one whose clips sit on their own takes\' anchors is the reference)' if f['tie'] else ''))
        print(f'   -> {f["who"]}')


def explained_keys(path):
    keys = set()
    pat = re.compile(r'^\s*[-*]\s*placement\s+track\s+#?(\d+)\s+start\s+(-?[0-9.]+)\s*:', re.I)
    with open(path) as fh:
        for line in fh:
            m = pat.match(line)
            if m:
                keys.add((int(m.group(1)), float(m.group(2))))
    return keys


def run_control(trs, track_ids, injections, tol):
    real, _ = detect(trs, track_ids, tol)
    groups = groups_for(trs, track_ids)
    ok = True
    for ti, start, delta in injections:
        c = next((c for c in trs[ti]['clips'] if abs(c['start'] - start) < 1e-3), None)
        label = f'{alsio.tname(trs, ti)} @ {start}'
        if c is None or not alsio.placement_usable(c):
            print(f'FAIL {label}: no unmuted warped clip there')
            ok = False
            continue
        n = max([len(v) for (t, f, _), v in groups.items() if t == ti and f == c['file'] and c in v] or [0])
        if n < 2:
            print(f'FAIL {label}: only copy of its take; this detector cannot see it (pick a reused take)')
            ok = False
            continue
        if ti not in track_ids:
            print(f'FAIL {label}: track not in the checked set')
            ok = False
            continue
        if abs(delta - round(delta)) <= tol:
            print(f'FAIL {label}: a whole-beat shift is invisible by design; inject a fraction of a beat')
            ok = False
            continue
        if any(f['track'] == ti and abs(f['start'] - start) < 1e-3 for f in real):
            print(f'FAIL {label}: already flagged in the real state; inject on a clean clip')
            ok = False
            continue
    if not ok:
        return False
    inj, _ = detect(alsio.apply_inject(trs, injections), track_ids, tol)
    for ti, start, delta in injections:
        want = _signed(_frac(delta), 0.0)
        hit = [f for f in inj if f['track'] == ti and abs(f['start'] - (start + delta)) < 1e-3]
        if hit and abs(abs(hit[0]['off_beats']) - abs(want)) <= tol:
            print(f'caught  {alsio.tname(trs, ti)} @ {start}{delta:+g}: flagged off {hit[0]["off_beats"]:+.4f} beat')
        else:
            got = [(f['track'], f['start'], f['off_beats']) for f in inj if f['track'] == ti]
            print(f'MISSED  {alsio.tname(trs, ti)} @ {start}{delta:+g}; flags on that track: {got}')
            ok = False
    print(f'real state: those clips are clean; {len(real)} flags elsewhere')
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('als')
    ap.add_argument('--tracks', nargs='+', help='restrict to these tracks (names or #index); default all active audio tracks')
    ap.add_argument('--pair', action='append', default=[], help='double "A=B" for partner notes (auto L/R pairs are added)')
    ap.add_argument('--no-auto', action='store_true', help='do not add auto-found L/R pairs')
    ap.add_argument('--tol', type=float, default=0.005, help='anchor tolerance in beats (default 0.005 = 2.5 ms at 120 BPM)')
    ap.add_argument('--inject', action='append', default=[],
                    help='positive control "TRACK@START+DELTA": shift that clip in a copy and require it to be caught')
    ap.add_argument('--explained', help='HANDOFF.md; every flag must have a "- placement track N start S: why" line')
    ap.add_argument('--beats-per-bar', type=float, default=4)
    ap.add_argument('--json', help='write flags as JSON here')
    a = ap.parse_args(argv)

    root = alsio.load(a.als)
    trs = alsio.tracks(root, a.als)
    tm = alsio.tempo_map(root, trs)
    if a.tracks:
        track_ids = sorted({alsio.resolve_track(trs, s) for s in a.tracks})
    else:
        track_ids = [t['index'] for t in trs if t['active'] and any(alsio.placement_usable(c) for c in t['clips'])]
    skipped = Counter()
    for t in trs:
        for c in t['clips']:
            if t['index'] not in track_ids:
                skipped['clips on inactive/unselected tracks'] += 1
            elif c['muted']:
                skipped['muted clips'] += 1
            elif not c['warp']:
                skipped['unwarped clips'] += 1
            elif not c['file_exists']:
                skipped['clips with missing files'] += 1

    if a.inject:
        injections = [alsio.parse_inject(trs, s) for s in a.inject]
        ok = run_control(trs, track_ids, injections, a.tol)
        print('CONTROL OK' if ok else 'CONTROL FAILED')
        return 0 if ok else 1

    pairs, _ = alsio.pairs_from_args(trs, a.pair, auto=not a.no_auto)
    flags, stats = detect(trs, track_ids, a.tol)
    stats['tracks'] = len(track_ids)
    annotate(flags, trs, tm, pairs, a.beats_per_bar, a.tol)
    pflags = detect_pairs(trs, pairs, a.tol, flags)
    print('pairs: ' + (', '.join(f'{alsio.tname(trs, p)} = {alsio.tname(trs, q)}' for p, q in pairs) or 'none'))
    print_flags(flags, trs, stats, skipped)
    print_pair_flags(pflags, tm, a.beats_per_bar)
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(dict(set=os.path.abspath(a.als), stats=stats,
                           pairs=[[p, q] for p, q in pairs], flags=flags, pair_flags=pflags), fh, indent=1)
    if a.explained:
        keys = explained_keys(a.explained)
        miss = [f for f in flags if not any(k[0] == f['track'] and abs(k[1] - f['start']) < 1e-3 for k in keys)]
        print()
        for f in miss:
            print(f'UNEXPLAINED placement track {f["track"]} start {f["start"]} ({f["track_name"]}, bar {f["bar"]})')
        print(f'placement flags {len(flags)}, unexplained {len(miss)}')
        if miss:
            return 1
        print('PLACEMENT OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
