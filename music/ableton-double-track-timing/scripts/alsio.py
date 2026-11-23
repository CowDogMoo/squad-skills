#!/usr/bin/env python3
"""Read-only access to a saved Ableton Live set (.als).

Gives the tempo map (beats <-> seconds, from the set's tempo automation),
every arrangement audio clip with its warp markers, and doubled-track pairs
(auto-found from L/R track names, or given explicitly as "A=B"). Nothing here
talks to Live: it reads the file Live last saved, so save the set first.

    python3 alsio.py SET.als                       # tempo, audio tracks, auto pairs
    python3 alsio.py SET.als --pair "Jayson Scratch=Jason Scratch"
    python3 alsio.py SET.als --list "Jayson Scratch" "Jason Scratch" --range 336 368   # clip table

Track specs used by every script in this skill: a track name ("Gtr L"), or
"#N" for Live's 0-based track index (return tracks are not counted, which
matches the index the AbletonMCP socket uses).
"""
from __future__ import annotations

import argparse
import copy
import gzip
import os
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np

FLOOR_DB = -60.0


# ---------------------------------------------------------------- loading

def load(path):
    """Parse a .als (gzipped XML; plain XML also accepted) into an Element."""
    with open(path, 'rb') as f:
        head = f.read(2)
    opener = gzip.open if head == b'\x1f\x8b' else open
    with opener(path, 'rb') as f:
        return ET.fromstring(f.read())


def _v(el, path, default=None):
    x = el.find(path)
    return default if x is None else x.get('Value', default)


# ---------------------------------------------------------------- tempo

def _main_track(root):
    for tag in ('MainTrack', 'MasterTrack'):          # Live 12 renamed Master -> Main
        m = root.find('LiveSet/' + tag)
        if m is not None:
            return m
    raise ValueError('no MainTrack/MasterTrack element: is this an Ableton Live set?')


def tempo_events(root):
    """[(beat, bpm), ...] from the song tempo automation; one event if not automated.

    Events keep file order for equal times, so two events at one beat act as a step.
    """
    m = _main_track(root)
    tempo = m.find('DeviceChain/Mixer/Tempo')
    base = float(_v(tempo, 'Manual'))
    tid = tempo.find('AutomationTarget').get('Id')
    for env in m.findall('AutomationEnvelopes/Envelopes/AutomationEnvelope'):
        if _v(env, 'EnvelopeTarget/PointeeId') == tid:
            ev = [(float(e.get('Time')), float(e.get('Value')))
                  for e in env.findall('Automation/Events/FloatEvent')]
            ev.sort(key=lambda x: x[0])                  # stable: keeps step order
            if ev:
                return ev
    return [(0.0, base)]


class TempoMap:
    """Beats <-> seconds through the song's tempo automation.

    Live ramps tempo linearly between automation breakpoints; two breakpoints at
    the same beat are a step. Integrated on a 1/64-beat grid (sub-ms accurate).
    """

    def __init__(self, events, end_beat, step=1 / 64):
        ev = [(max(t, 0.0), v) for t, v in events]
        self._T = np.array([t for t, _ in ev])
        self._V = np.array([v for _, v in ev])
        self.beats = np.arange(0.0, end_beat + step, step)
        mid = self.beats[:-1] + step / 2
        self.secs = np.concatenate([[0.0], np.cumsum(60.0 / self.bpm(mid) * step)])

    def bpm(self, b):
        b = np.atleast_1d(np.asarray(b, dtype=float))
        T, V = self._T, self._V
        i = np.searchsorted(T, b, side='right')
        out = np.empty_like(b)
        lo, hi = i == 0, i >= len(T)
        out[lo], out[hi] = V[0], V[-1]
        mid = ~(lo | hi)
        j = i[mid]
        t0, t1, v0, v1 = T[j - 1], T[j], V[j - 1], V[j]
        out[mid] = v0 + (v1 - v0) * (b[mid] - t0) / (t1 - t0)
        return out

    def b2s(self, b):
        r = np.interp(b, self.beats, self.secs)
        return float(r) if np.ndim(r) == 0 else r

    def s2b(self, s):
        r = np.interp(s, self.secs, self.beats)
        return float(r) if np.ndim(r) == 0 else r

    def beats_to_ms(self, beat, d_beats):
        """Length in ms of d_beats starting at beat (tempo-aware)."""
        return (self.b2s(beat + d_beats) - self.b2s(beat)) * 1000.0


def tempo_map(root, trs=None, pad_beats=64.0):
    trs = trs if trs is not None else tracks(root)
    end = max([c['end'] for t in trs for c in t['clips']] + [16.0]) + pad_beats
    return TempoMap(tempo_events(root), end)


# ---------------------------------------------------------------- clips and tracks

def _clip(c, als_dir):
    fr = c.find('SampleRef/FileRef')
    path = _v(fr, 'Path') if fr is not None else None
    rel = _v(fr, 'RelativePath') if fr is not None else None
    file = path
    if (not path or not os.path.exists(path)) and rel and als_dir:
        cand = os.path.normpath(os.path.join(als_dir, rel))
        if os.path.exists(cand):
            file = cand
    return dict(
        start=float(_v(c, 'CurrentStart')), end=float(_v(c, 'CurrentEnd')),
        loop_start=float(_v(c, 'Loop/LoopStart', 0)), loop_end=float(_v(c, 'Loop/LoopEnd', 0)),
        start_rel=float(_v(c, 'Loop/StartRelative', 0) or 0),
        loop_on=_v(c, 'Loop/LoopOn') == 'true',
        muted=_v(c, 'Disabled') == 'true', warp=_v(c, 'IsWarped') == 'true',
        name=_v(c, 'Name', ''), file=file, file_exists=bool(file and os.path.exists(file)),
        warp_markers=sorted((float(w.get('SecTime')), float(w.get('BeatTime')))
                            for w in c.findall('WarpMarkers/WarpMarker')))


def _midi_clip(c):
    return dict(start=float(_v(c, 'CurrentStart')), end=float(_v(c, 'CurrentEnd')),
                loop_start=float(_v(c, 'Loop/LoopStart', 0)), loop_end=float(_v(c, 'Loop/LoopEnd', 0)),
                muted=_v(c, 'Disabled') == 'true', name=_v(c, 'Name', ''))


def tracks(root, als_path=None):
    """Every non-return track: index (Live's), name, kind, active, audio clips, midi clips.

    Only main-lane arrangement clips are read (take lanes are not playing audio).
    """
    als_dir = os.path.dirname(os.path.abspath(als_path)) if als_path else None
    out, idx = [], 0
    for t in root.find('LiveSet/Tracks'):
        if t.tag == 'ReturnTrack':
            continue
        spk = t.find('DeviceChain/Mixer/Speaker/Manual')
        seq = t.find('DeviceChain/MainSequencer')
        audio, midi = [], []
        if seq is not None:
            audio = [_clip(c, als_dir) for c in seq.findall('Sample/ArrangerAutomation/Events/AudioClip')]
            midi = [_midi_clip(c) for c in seq.findall('ClipTimeable/ArrangerAutomation/Events/MidiClip')]
        out.append(dict(index=idx, name=_v(t, 'Name/EffectiveName', ''), kind=t.tag,
                        active=spk is None or spk.get('Value') == 'true',
                        clips=sorted(audio, key=lambda c: c['start']),
                        midi_clips=sorted(midi, key=lambda c: c['start'])))
        idx += 1
    return out


def usable(c):
    """A clip that sounds and can be analysed: unmuted, file on disk, and either
    warped with >=2 warp markers or unwarped (plays at the file's own rate)."""
    return (not c['muted']) and c['file_exists'] and (not c['warp'] or len(c['warp_markers']) >= 2)


def placement_usable(c):
    """Usable for the anchor check: warped (unwarped clips have no beat grid of their own)."""
    return usable(c) and c['warp']


def has_audio(t):
    return t['active'] and any(usable(c) for c in t['clips'])


# ---------------------------------------------------------------- clip time mapping

def clip_file_secs(c, x, tm):
    """Arrangement beats x (array) -> seconds in the clip's audio file.

    Warped clips go through their warp markers; unwarped clips play in real time
    from the start marker (their loop values are already in seconds).
    """
    x = np.asarray(x, dtype=float)
    if c['warp']:
        return clip_beats_to_file_secs(c, clip_beats(c, x))
    return c['loop_start'] + c['start_rel'] + (tm.b2s(x) - tm.b2s(c['start']))


def anchor(c):
    """Arrangement beat where the take's beat 0 lands (start minus start marker)."""
    return c['start'] - (c['loop_start'] + c['start_rel'])


def clip_beats(c, x):
    """Arrangement beats x (array) -> beats inside the clip's audio."""
    cb = c['loop_start'] + c['start_rel'] + (np.asarray(x, dtype=float) - c['start'])
    if c['loop_on'] and c['loop_end'] > c['loop_start']:
        span = c['loop_end'] - c['loop_start']
        over = cb >= c['loop_end']
        cb = np.where(over, c['loop_start'] + np.mod(cb - c['loop_start'], span), cb)
    return cb


def clip_beats_to_file_secs(c, cb):
    """Clip beats -> seconds in the audio file, through the warp markers (linear
    between markers, extrapolated with the first/last segment's rate)."""
    wm = c['warp_markers']
    S = np.array([s for s, _ in wm])
    B = np.array([b for _, b in wm])
    cb = np.asarray(cb, dtype=float)
    out = np.interp(cb, B, S)
    lo, hi = cb < B[0], cb > B[-1]
    out[lo] = S[0] + (cb[lo] - B[0]) * (S[1] - S[0]) / (B[1] - B[0])
    out[hi] = S[-1] + (cb[hi] - B[-1]) * (S[-1] - S[-2]) / (B[-1] - B[-2])
    return out


# ---------------------------------------------------------------- track specs, pairs, injection

def resolve_track(trs, spec):
    """'#3' / '3' -> index 3; a name -> that track (prefers active tracks with audio)."""
    s = spec.strip()
    m = re.fullmatch(r'#?(\d+)', s)
    named = [t for t in trs if t['name'] == s]
    if m and not named:
        i = int(m.group(1))
        if not 0 <= i < len(trs):
            raise SystemExit(f'track index {i} out of range (0-{len(trs) - 1})')
        return i
    if not named:
        close = [t['name'] for t in trs if s.lower() in t['name'].lower()]
        raise SystemExit(f'no track named {s!r}' + (f'; did you mean one of {close}?' if close else ''))
    if len(named) > 1:
        live = [t for t in named if has_audio(t)]
        if len(live) == 1:
            return live[0]['index']
        raise SystemExit(f'{len(named)} tracks are named {s!r} (indices '
                         f'{[t["index"] for t in named]}); pass "#index" instead')
    return named[0]['index']


def parse_pair(trs, spec):
    if '=' not in spec:
        raise SystemExit(f'--pair wants "A=B", got {spec!r}')
    a, b = spec.split('=', 1)
    ia, ib = resolve_track(trs, a), resolve_track(trs, b)
    if ia == ib:
        raise SystemExit(f'--pair {spec!r} names the same track twice')
    return (ia, ib)


_SIDE_WORD = re.compile(r'^(?P<base>.+?)[\s_\-.]*[(\[]?(?P<side>left|right)[)\]]?(?P<suf>[\s_\-]*\d+)?$', re.I)
_SIDE_LETTER = re.compile(r'^(?P<base>.+?)(?:[\s_\-.]+[(\[]?|[(\[])(?P<side>L|R)[)\]]?(?P<suf>[\s_\-]*\d+)?$')


def side_key(name):
    """'After Riff Gtr L' -> ('after riff gtr', 'L'); 'Rhythm (Right) 2' -> ('rhythm|2', 'R')."""
    n = name.strip()
    m = _SIDE_LETTER.match(n) or _SIDE_WORD.match(n)
    if not m:
        return None
    base = m.group('base').strip(' _-.([').lower()
    suf = (m.group('suf') or '').strip(' _-')
    return (base + ('|' + suf if suf else ''), m.group('side')[0].upper())


def auto_pairs(trs):
    """L/R doubles found from names among active tracks with analysable audio.

    Returns (pairs, notes): pairs as (L index, R index); notes explain skipped names.
    """
    by, notes = {}, []
    for t in trs:
        if not has_audio(t):
            continue
        k = side_key(t['name'])
        if k:
            by.setdefault(k[0], {}).setdefault(k[1], []).append(t['index'])
    pairs = []
    for base, sides in sorted(by.items()):
        if 'L' in sides and 'R' in sides:
            if len(sides['L']) == 1 and len(sides['R']) == 1:
                pairs.append((sides['L'][0], sides['R'][0]))
            else:
                notes.append(f'ambiguous L/R names for {base!r}: {sides}; use --pair "#L=#R"')
        else:
            notes.append(f'{base!r} has only side {list(sides)}: no partner found by name')
    return sorted(pairs), notes


def pairs_from_args(trs, pair_specs, auto=True):
    """Explicit --pair specs first, then auto L/R pairs not already covered."""
    pairs = [parse_pair(trs, s) for s in (pair_specs or [])]
    notes = []
    if auto:
        ap, notes = auto_pairs(trs)
        used = {i for p in pairs for i in p}
        pairs += [p for p in ap if p[0] not in used and p[1] not in used]
    return pairs, notes


_INJ = re.compile(r'^(?P<track>.+)@(?P<start>-?\d+(?:\.\d+)?)(?P<delta>[+-]\d+(?:\.\d+)?)$')


def parse_inject(trs, spec):
    """'Jayson Scratch@357+0.0625' -> (track index, 357.0, +0.0625)."""
    m = _INJ.match(spec.strip())
    if not m:
        raise SystemExit(f'--inject wants "TRACK@START+DELTA" (beats), got {spec!r}')
    return resolve_track(trs, m.group('track')), float(m.group('start')), float(m.group('delta'))


def apply_inject(trs, injections):
    """Deep copy of trs with the given clips shifted (start and end) by delta beats."""
    t2 = copy.deepcopy(trs)
    for ti, start, delta in injections:
        hit = [c for c in t2[ti]['clips'] if abs(c['start'] - start) < 1e-3]
        if not hit:
            raise SystemExit(f'--inject: no audio clip on track #{ti} {trs[ti]["name"]!r} starts at {start}')
        for c in hit:
            c['start'] += delta
            c['end'] += delta
    return t2


# ---------------------------------------------------------------- formatting

def bar_beat(beat, beats_per_bar=4):
    """Beat 357 -> '90.2' (bar 90, beat 2); beat 362.0625 -> '91.3+0.0625'.

    Assumes one meter from beat 0 (pass --beats-per-bar for non-4/4 songs).
    """
    beat = round(float(beat), 4)
    bar = int(beat // beats_per_bar) + 1
    b = beat - (bar - 1) * beats_per_bar
    whole = int(np.floor(b + 1e-6))
    frac = b - whole
    return f'{bar}.{whole + 1}' + (f'+{frac:.4g}' if frac > 1e-4 else '')


def tname(trs, i):
    return f'#{i} {trs[i]["name"]}'


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('als')
    ap.add_argument('--pair', action='append', default=[], help='explicit double "A=B" (names or #index)')
    ap.add_argument('--list', nargs='+', metavar='TRACK', help='print every audio clip of these tracks (names or #index)')
    ap.add_argument('--range', nargs=2, type=float, metavar=('START', 'END'), help='with --list: only clips overlapping these beats')
    ap.add_argument('--beats-per-bar', type=float, default=4)
    a = ap.parse_args(argv)
    root = load(a.als)
    trs = tracks(root, a.als)
    tm = tempo_map(root, trs)
    if a.list:
        print('track, start-end (beats), bars, anchor = start - start marker, muted/warped, clip name, take file')
        for spec in a.list:
            ti = resolve_track(trs, spec)
            for c in trs[ti]['clips']:
                if a.range and not (c['start'] < a.range[1] and a.range[0] < c['end']):
                    continue
                flags = ('muted ' if c['muted'] else '') + ('' if c['warp'] else 'unwarped ') + \
                        ('' if c['file_exists'] else 'MISSING ')
                print(f'  #{ti} {trs[ti]["name"][:18]:18s} {c["start"]:9.4f}-{c["end"]:9.4f}  '
                      f'bar {bar_beat(c["start"], a.beats_per_bar):>12s}  anchor {anchor(c):9.4f}  {flags:9s}'
                      f'"{c["name"][:24]}"  {os.path.basename(c["file"] or "?")}')
        return 0
    ev = tempo_events(root)
    print(f'set: {a.als}')
    print(f'tracks: {len(trs)} (return tracks not counted)')
    steps = []
    last = None
    for t, v in ev:
        if last is None or abs(v - last) > 1e-9:
            steps.append(f'{max(t, 0):g}:{v:g}')
            last = v
    print('tempo (beat:bpm at each change):', ', '.join(steps[:24]) + (' ...' if len(steps) > 24 else ''))
    print('\naudio tracks (index, name, active, usable clips / all clips, distinct takes):')
    for t in trs:
        if not t['clips']:
            continue
        n_use = sum(usable(c) for c in t['clips'])
        files = len({c['file'] for c in t['clips'] if c['file']})
        missing = sum(1 for c in t['clips'] if not c['muted'] and c['file'] and not c['file_exists'])
        print(f'  #{t["index"]:<3} {t["name"][:40]:40s} {"on " if t["active"] else "off"} '
              f'{n_use:>3}/{len(t["clips"]):<3} takes={files}' + (f'  MISSING FILES: {missing}' if missing else ''))
    pairs, notes = pairs_from_args(trs, a.pair)
    print('\npairs (explicit first, then auto L/R):')
    for p, q in pairs:
        print(f'  {tname(trs, p)}  =  {tname(trs, q)}')
    for n in notes:
        print('  note:', n)
    if not pairs:
        print('  none found; pass --pair "A=B"')
    print(f'\nsong length analysed: beats 0-{tm.beats[-1]:.0f} = {tm.b2s(tm.beats[-1]):.1f} s')


if __name__ == '__main__':
    sys.exit(main())
