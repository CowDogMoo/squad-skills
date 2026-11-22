#!/usr/bin/env python3
"""Move arrangement clips by exact beat amounts through the AbletonMCP socket.
Opt-in: only when the user has explicitly asked for the fix. Dry run by default.

PLAN.json lists the moves, each one a clip addressed by track and its current
start beat:

    {"moves": [{"track": "Jayson Scratch", "from": 357.0625, "to": 357.0},
               {"track": "#1",             "from": 362.0625, "to": 362.0}]}

    python3 apply_moves.py PLAN.json --als SET.als              # dry run, offline: order, overlaps, gaps
    python3 apply_moves.py PLAN.json --execute --out fixdir/    # do it in Live

What --execute does, in order:
  1. Refuses if the transport is playing (--allow-playing to override).
  2. Saves fixdir/pre_fix_snapshot.json (get_arrangement_info) for collateral.py.
  3. Orders the moves so no clip ever lands on a clip that has not moved yet
     (moving later: latest first; moving earlier: earliest first). A move that
     overlaps a neighbour makes Live truncate that neighbour.
  4. Moves each clip with move_arrangement_clip (copy, verify, delete original),
     re-reading the track after every move and stopping at the first surprise.
  5. With --close-gaps, re-closes a gap the move opened against a clip it used to
     touch, by extending the earlier clip's loop_end (warped clips only).
  6. Writes fixdir/applied_moves.json: the allowed changes collateral.py checks.

Then save the set, re-run the measurements, and run collateral.py.
Exit codes: 0 done (or dry run ok), 1 stopped on a problem, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

EPS = 1e-3


def load_plan(path):
    with open(path) as fh:
        p = json.load(fh)
    moves = p['moves'] if isinstance(p, dict) else p
    for m in moves:
        if not {'track', 'from', 'to'} <= set(m):
            raise SystemExit(f'each move needs track, from, to: {m}')
        m['from'], m['to'] = float(m['from']), float(m['to'])
    return moves


def resolve(tracks, spec, at=None):
    """tracks: [{index, name, clips}]; spec: name, '#N' or int. With several tracks
    of one name, the one holding an audio clip that starts at beat `at` wins."""
    s = str(spec).strip()
    if s.lstrip('#').isdigit() and not any(t['name'] == s for t in tracks):
        hit = [t for t in tracks if t['index'] == int(s.lstrip('#'))]
    else:
        hit = [t for t in tracks if t['name'] == s]
        if len(hit) > 1 and at is not None:
            holding = [t for t in hit if any(abs(c['start'] - at) < EPS for c in t['clips'])]
            hit = holding if len(holding) == 1 else hit
    if len(hit) != 1:
        raise SystemExit(f'track {spec!r}: {len(hit)} matches; use "#index"')
    return hit[0]


def order_moves(tracks, moves):
    """Greedy order per track so a destination never overlaps an unmoved clip."""
    ordered = []
    by_track = {}
    for m in moves:
        by_track.setdefault(m['ti'], []).append(m)
    for ti, ms in by_track.items():
        spans = {round(c['start'], 6): (c['start'], c['end']) for c in tracks[ti]['clips']}
        pending = sorted(ms, key=lambda m: (-m['from'] if m['to'] > m['from'] else m['from']))
        while pending:
            for m in pending:
                length = m['end'] - m['from']
                lo, hi = m['to'], m['to'] + length
                clash = [s for k, s in spans.items() if k != round(m['from'], 6) and s[0] < hi - EPS and lo < s[1] - EPS]
                if not clash:
                    ordered.append(m)
                    del spans[round(m['from'], 6)]
                    spans[round(m['to'], 6)] = (lo, hi)
                    pending.remove(m)
                    break
            else:
                raise SystemExit('cannot order these moves without overlapping an unmoved clip: '
                                 + ', '.join(f'#{m["ti"]} {m["from"]}->{m["to"]}' for m in pending)
                                 + '. Split the plan or move a neighbour first.')
    return ordered


def gap_fixes(tracks, ordered):
    """loop_end extensions that re-close gaps a move opens against a clip it touched."""
    moved = {(m['ti'], round(m['from'], 6)) for m in ordered}
    fixes = []
    for m in ordered:
        clips = tracks[m['ti']]['clips']
        d = m['to'] - m['from']
        if d < 0:                                       # moved earlier: gap after it
            nxt = [c for c in clips if abs(c['start'] - m['end']) < EPS and (m['ti'], round(c['start'], 6)) not in moved]
            if nxt:
                fixes.append(dict(ti=m['ti'], start=m['to'], end_from=m['end'] + d, end_to=nxt[0]['start'],
                                  warped=m['warped'], why=f're-close {-d:g}-beat gap before clip at {nxt[0]["start"]}'))
        elif d > 0:                                     # moved later: gap before it
            prv = [c for c in clips if abs(c['end'] - m['from']) < EPS and (m['ti'], round(c['start'], 6)) not in moved]
            if prv:
                fixes.append(dict(ti=m['ti'], start=prv[0]['start'], end_from=prv[0]['end'], end_to=m['to'],
                                  warped=prv[0].get('warping', prv[0].get('warp', True)),
                                  why=f'extend previous clip to meet the moved clip at {m["to"]}'))
    return fixes


def offline_tracks(als):
    import alsio
    root = alsio.load(als)
    out = []
    for t in alsio.tracks(root, als):
        out.append(dict(index=t['index'], name=t['name'],
                        clips=[dict(start=c['start'], end=c['end'], name=c['name'], warp=c['warp'],
                                    loop_end=c['loop_end']) for c in t['clips']]))
    return out


def live_tracks(info):
    out = []
    for t in info['tracks']:
        out.append(dict(index=t['index'], name=t['name'],
                        clips=[dict(start=c['start_time'], end=c['end_time'], name=c['name'], index=c['index'],
                                    warp=c.get('warping', False), loop_end=c.get('loop_end'))
                               for c in t['arrangement_clips'] if c.get('is_audio')]))
    return out


def prepare(tracks, moves):
    by_index = {t['index']: t for t in tracks}
    for m in moves:
        t = resolve(tracks, m['track'], m['from'])
        hit = [c for c in t['clips'] if abs(c['start'] - m['from']) < EPS]
        if len(hit) != 1:
            raise SystemExit(f'track #{t["index"]} {t["name"]!r}: {len(hit)} audio clips start at {m["from"]}')
        m.update(ti=t['index'], end=hit[0]['end'], name=hit[0]['name'], warped=hit[0]['warp'])
    return by_index


def describe(ordered, fixes, tracks):
    print('planned moves, in execution order:')
    for i, m in enumerate(ordered, 1):
        print(f'  {i}. #{m["ti"]} {tracks[m["ti"]]["name"]!r} clip "{m["name"]}" {m["from"]} -> {m["to"]} '
              f'({m["to"] - m["from"]:+.4f} beat)')
    if fixes:
        print('gaps these moves open against clips they touched (closed only with --close-gaps):')
        for f in fixes:
            tag = '' if f['warped'] else '  [unwarped: left open]'
            print(f'  #{f["ti"]} clip at {f["start"]}: end {f["end_from"]:.4f} -> {f["end_to"]:.4f} ({f["why"]}){tag}')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('plan')
    ap.add_argument('--als', help='saved set, for an offline dry run')
    ap.add_argument('--execute', action='store_true', help='actually move clips in Live (opt-in)')
    ap.add_argument('--close-gaps', action='store_true', help='extend loop_end to re-close gaps the moves open')
    ap.add_argument('--allow-playing', action='store_true')
    ap.add_argument('--out', default='.', help='folder for pre_fix_snapshot.json and applied_moves.json')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=9877)
    a = ap.parse_args(argv)
    moves = load_plan(a.plan)

    if not a.execute:
        if not a.als:
            print('dry run needs --als SET.als (or pass --execute to plan against Live)')
            return 2
        tracks = offline_tracks(a.als)
        by_index = prepare(tracks, moves)
        ordered = order_moves(by_index, moves)
        describe(ordered, gap_fixes(by_index, ordered), by_index)
        print('\ndry run only: nothing was sent to Live. Add --execute once the user has asked for the fix.')
        return 0

    import live_socket as L
    info = L.arrangement(a.host, a.port)
    if info['transport'].get('is_playing') and not a.allow_playing:
        print('transport is playing: stop playback first (or --allow-playing)')
        return 1
    os.makedirs(a.out, exist_ok=True)
    snap = os.path.join(a.out, 'pre_fix_snapshot.json')
    with open(snap, 'w') as fh:
        json.dump(info, fh, indent=1)
    tracks = live_tracks(info)
    by_index = prepare(tracks, moves)
    ordered = order_moves(by_index, moves)
    fixes = gap_fixes(by_index, ordered)
    describe(ordered, fixes, by_index)
    log = dict(moves=[], loop_end=[], snapshot=os.path.abspath(snap))
    logp = os.path.join(a.out, 'applied_moves.json')

    def save_log():
        with open(logp, 'w') as fh:
            json.dump(log, fh, indent=1)

    def clips_now(ti):
        return live_tracks(L.arrangement(a.host, a.port, ti))[0]['clips']

    for m in ordered:
        before = clips_now(m['ti'])
        cur = [c for c in before if abs(c['start'] - m['from']) < EPS]
        if len(cur) != 1:
            print(f'STOP: expected one clip at {m["from"]} on #{m["ti"]}, found {len(cur)}')
            save_log()
            return 1
        res = L.call('move_arrangement_clip', a.host, a.port, track_index=m['ti'],
                     clip_index=cur[0]['index'], destination_time=m['to'])
        after = clips_now(m['ti'])
        landed = [c for c in after if abs(c['start'] - m['to']) < EPS and abs((c['end'] - c['start']) - (m['end'] - m['from'])) < EPS]
        others_before = sorted((round(c['start'], 4), round(c['end'], 4)) for c in before if c is not cur[0])
        others_after = sorted((round(c['start'], 4), round(c['end'], 4)) for c in after if not landed or c is not landed[0])
        if not landed or others_before != others_after or res.get('overlapped_clips'):
            print(f'STOP after #{m["ti"]} {m["from"]}->{m["to"]}: landed={bool(landed)}, '
                  f'overlapped={res.get("overlapped_clips")}, neighbours changed={others_before != others_after}. '
                  'Undo in Live (Cmd+Z) if this is wrong.')
            log['moves'].append(dict(track=m['ti'], **{'from': m['from'], 'to': m['to']}))
            save_log()
            return 1
        log['moves'].append(dict(track=m['ti'], **{'from': m['from'], 'to': m['to']}))
        print(f'moved #{m["ti"]} {m["from"]} -> {m["to"]}')
    if a.close_gaps:
        for f in fixes:
            if not f['warped']:
                continue
            now = clips_now(f['ti'])
            c = [x for x in now if abs(x['start'] - f['start']) < EPS]
            if len(c) != 1 or c[0]['loop_end'] is None:
                print(f'skip gap fix at #{f["ti"]} {f["start"]}: clip not found')
                continue
            new_le = c[0]['loop_end'] + (f['end_to'] - c[0]['end'])
            L.call('set_arrangement_clip_property', a.host, a.port, track_index=f['ti'], clip_index=c[0]['index'],
                   property='loop_end', value=new_le)
            chk = [x for x in clips_now(f['ti']) if abs(x['start'] - f['start']) < EPS]
            okk = chk and abs(chk[0]['end'] - f['end_to']) < EPS
            log['loop_end'].append(dict(track=f['ti'], start=f['start'], end_from=c[0]['end'], end_to=f['end_to']))
            print(f'{"closed" if okk else "CHECK"} gap: #{f["ti"]} clip at {f["start"]} now ends '
                  f'{chk[0]["end"] if chk else "?"} (wanted {f["end_to"]})')
    save_log()
    print(f'\nwrote {logp}. Next: save the set, re-measure, then run collateral.py --before {snap} --live --allowed {logp}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
