#!/usr/bin/env python3
"""Compare two Ableton Live sets (.als) and list what changed, track by track.

Built for reviewing an edit to a shared set: keep the original untouched,
Save Live Set As... the edit under a new name in the same project, then run
this on the pair. Tracks are matched by Live's track Id, so a rename shows
as a change, not as a remove plus an add.

Compares only these fields: tracks added and removed; for every track in
both sets: name, type, group, input and output routing, monitoring, volume,
pan, track on/off (Speaker, i.e. mute), solo, sends, arm, devices (name and
on/off), take-lane count and arrangement/session clips (kind, name, start;
take-lane clips included); then the main track, tempo and locators. It also
prints the return-track count. It does not compare device parameter values,
clip length, gain, warp or notes, automation, or set-level options such as
Reduced Latency When Monitoring.

Read-only, standard library only:
  python3 -I als_diff.py BASE.als NEW.als
Exit status: 0 no differences in the compared fields (not proof that the sets
are identical), 1 differences found, 2 a file could not be read.
"""
import argparse
import gzip
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict

DEVICE_NAME_TAGS = ('.//PlugName', './/Vst3PluginInfo/Name', './/AuPluginInfo/Name',
                    'UserName', 'EffectiveName')


def load(path):
    with gzip.open(path) as fh:
        return ET.fromstring(fh.read())


def val(el, path, attr='Value'):
    n = el.find(path) if el is not None else None
    return n.get(attr) if n is not None else None


def first(root, *paths):
    for p in paths:
        n = root.find(p)
        if n is not None:
            return n
    return None


def dev_list(chain):
    out = []
    devs = chain.find('Devices') if chain is not None else None
    if devs is None:
        return out
    for d in devs:
        name = None
        for tag in DEVICE_NAME_TAGS:
            n = d.find(tag)
            if n is not None and n.get('Value'):
                name = n.get('Value')
                break
        on = val(d, 'On/Manual')
        out.append(f"{d.tag}:{name or d.tag}{'' if on in (None, 'true') else ' [off]'}")
    return out


def clips(track):
    res = []
    for kind, tag in (('A', 'AudioClip'), ('M', 'MidiClip')):
        for c in track.iter(tag):
            res.append((kind, val(c, 'Name'), val(c, 'CurrentStart')))
    return sorted(res, key=lambda x: (x[0], str(x[2]), str(x[1])))


def track_info(t):
    dc = t.find('DeviceChain')
    mixer = dc.find('Mixer') if dc is not None else None
    inner = dc.find('DeviceChain') if dc is not None else None
    info = OrderedDict()
    info['name'] = val(t, 'Name/EffectiveName')
    info['type'] = t.tag
    info['group'] = val(t, 'TrackGroupId')
    if dc is not None:
        info['in'] = f"{val(dc, 'AudioInputRouting/Target')} | {val(dc, 'MidiInputRouting/Target')}"
        info['out'] = val(dc, 'AudioOutputRouting/Target')
        # 0 In, 1 Auto, 2 Off
        info['monitor'] = val(dc, 'MainSequencer/MonitoringEnum') or val(dc, 'MonitoringEnum')
    if mixer is not None:
        info['volume'] = val(mixer, 'Volume/Manual')
        info['pan'] = val(mixer, 'Pan/Manual')
        info['speaker(on)'] = val(mixer, 'Speaker/Manual')
        info['solo'] = val(mixer, 'SoloSink')
        sends = mixer.find('Sends')
        info['sends'] = [val(s, 'Send/Manual') for s in sends] if sends is not None else []
    info['arm'] = val(t, './/Recorder/IsArmed') or val(t, './/IsArmed')
    info['devices'] = dev_list(inner)
    info['take_lanes'] = len(t.findall('.//TakeLane'))
    info['clips'] = clips(t)
    return info


def tracks(root):
    out = OrderedDict()
    tr = root.find('LiveSet/Tracks')
    for t in (tr if tr is not None else []):
        out[t.get('Id')] = track_info(t)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('base')
    ap.add_argument('new')
    a = ap.parse_args()
    try:
        ra, rb = load(a.base), load(a.new)
    except (OSError, ET.ParseError) as exc:
        print(f"cannot read set: {exc}", file=sys.stderr)
        return 2

    ta, tb = tracks(ra), tracks(rb)
    differences = 0
    print(f"tracks: base {len(ta)}, new {len(tb)}")
    for tid, i in tb.items():
        if tid not in ta:
            differences += 1
            print(f"\nADDED track Id {tid}: {i['name']} ({i['type']})")
            for k in ('in', 'out', 'monitor', 'volume', 'pan', 'arm', 'devices', 'take_lanes'):
                print(f"   {k}: {i.get(k)}")
            print(f"   clips: {len(i['clips'])}")
    for tid, i in ta.items():
        if tid not in tb:
            differences += 1
            print(f"\nREMOVED track Id {tid}: {i['name']}")

    changed = 0
    for tid, x in ta.items():
        if tid not in tb:
            continue
        y = tb[tid]
        diffs = [(k, x.get(k), y.get(k)) for k in x if x.get(k) != y.get(k)]
        if not diffs:
            continue
        changed += 1
        print(f"\nCHANGED track {x['name']!r} (Id {tid}):")
        for k, u, v in diffs:
            if k == 'clips':
                su, sv = set(u), set(v)
                print(f"   clips: -{len(su - sv)} +{len(sv - su)}  "
                      f"removed={sorted(su - sv, key=str)[:5]} added={sorted(sv - su, key=str)[:5]}")
            else:
                print(f"   {k}: {u!r} -> {v!r}")
    differences += changed
    print(f"\nunchanged existing tracks: {sum(1 for t in ta if t in tb) - changed}; changed: {changed}")

    ma = first(ra, 'LiveSet/MainTrack', 'LiveSet/MasterTrack')
    mb = first(rb, 'LiveSet/MainTrack', 'LiveSet/MasterTrack')
    ia = track_info(ma) if ma is not None else {}
    ib = track_info(mb) if mb is not None else {}
    md = [(k, ia.get(k), ib.get(k)) for k in ia if ia.get(k) != ib.get(k) and k != 'clips']
    differences += len(md)
    print("\nmain track:", "unchanged" if not md else "")
    for k, u, v in md:
        print(f"   {k}: {u!r} -> {v!r}")

    tempo_a = val(ma, 'DeviceChain/Mixer/Tempo/Manual')
    tempo_b = val(mb, 'DeviceChain/Mixer/Tempo/Manual')
    differences += tempo_a != tempo_b
    print("tempo:", tempo_a, '->', tempo_b)
    la = [(val(n, 'Time'), val(n, 'Name')) for n in ra.iter('Locator')]
    lb = [(val(n, 'Time'), val(n, 'Name')) for n in rb.iter('Locator')]
    differences += la != lb
    print("locators:", "unchanged" if la == lb else f"{la} -> {lb}")
    ret_a = len(ra.findall('LiveSet/Tracks/ReturnTrack'))
    ret_b = len(rb.findall('LiveSet/Tracks/ReturnTrack'))
    print("return tracks:", ret_a, '->', ret_b)
    return 1 if differences else 0


if __name__ == '__main__':
    sys.exit(main())
