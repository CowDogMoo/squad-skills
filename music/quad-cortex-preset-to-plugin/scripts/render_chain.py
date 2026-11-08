#!/usr/bin/env python3
"""Offline re-amp: render a DI wav through a chain of Neural DSP plugins.

Each plugin is loaded headless with Spotify's `pedalboard` (no DAW, no plugin
window) and given a saved preset: the preset's `appModel` values are applied
onto the plugin's own state XML by node path, so the preset file is the one
source of truth. After loading, the script waits 3 s for file-based loads
(a custom IR) to settle, reads the state back from each plugin and prints every
value that did not take. A mismatch that is only number formatting ('1' vs
'1.0') is not counted. A mono DI is duplicated to two channels, the way Live
feeds a mono track into a stereo plugin. Output is a 32-bit float wav at the
DI's sample rate, so a peak over full scale is kept, not clipped.

Validated against Live's own re-amp of the same DI: null -20.5 dB, ESR 0.009,
so an offline render stands in for a Live re-amp when comparing settings.

Usage:
  uv run --with pedalboard --with soundfile --with numpy python -I render_chain.py \\
    DI.wav OUT.wav "/Library/Audio/Plug-Ins/VST3/<Plugin>.vst3=<preset>.xml" [...]

A spec without `=PRESET` loads the plugin in its default state.
"""
import argparse
import struct
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from pedalboard import Pedalboard, load_plugin  # noqa: E402

from juce_state import components, mb_decode, replace_component, split  # noqa: E402
from ndsp_preset import load as load_preset  # noqa: E402

SETTLE = 3.0


def as_text(t, v):
    if t == 'b':
        return 'true' if v else 'false'
    if t == 'd':
        return repr(v)
    return str(v)


def same(a, b):
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except ValueError:
        return False


def inner_xml(plugin):
    raw = plugin.raw_state
    inner = mb_decode(components(split(raw)[0])['IComponent'])
    if inner[:4] != b'VC2!':
        raise ValueError("inner plugin state is not a VC2! block; not a Neural DSP plugin?")
    n = struct.unpack('<I', inner[4:8])[0]
    return raw, inner[8:8 + n].decode('utf-8'), inner[8 + n:]


def app_model(preset_path):
    tree, tail = load_preset(preset_path)
    if tail:
        raise ValueError(f"{preset_path}: unexpected trailing bytes")
    return next(k for k in tree['kids'] if k['name'] == 'appModel')


def apply_preset(plugin, preset_path):
    """Apply a preset file's appModel onto the plugin's state; return stats."""
    raw, xml_text, rest = inner_xml(plugin)
    root = ET.fromstring(xml_text)
    stats = {'set': 0, 'changed': 0, 'missing': []}

    def walk(node, el, path):
        for k, t, v in node['props']:
            if k in el.attrib:
                new = as_text(t, v)
                stats['changed'] += el.attrib[k] != new
                el.attrib[k] = new
                stats['set'] += 1
            else:
                stats['missing'].append(f"{path}@{k}")
        for c in node['kids']:
            match = [e for e in el if e.tag == c['name']]
            if len(match) != 1:
                stats['missing'].append(f"{path}/{c['name']} (x{len(match)})")
                continue
            walk(c, match[0], f"{path}/{c['name']}")

    walk(app_model(preset_path), root, 'appModel')
    body = ('<?xml version="1.0" encoding="UTF-8"?> '
            + ET.tostring(root, encoding='unicode')).encode('utf-8')
    plugin.raw_state = replace_component(raw, b'VC2!' + struct.pack('<I', len(body)) + body + rest)
    return stats


def read_back(plugin, preset_path):
    """List preset values the plugin does not hold after loading."""
    root = ET.fromstring(inner_xml(plugin)[1])
    bad = []

    def chk(node, el, path):
        for k, t, v in node['props']:
            if k in el.attrib and not same(el.attrib[k], as_text(t, v)):
                bad.append(f"{path}@{k}: plugin={el.attrib[k]!r} preset={as_text(t, v)!r}")
        for c in node['kids']:
            m = [e for e in el if e.tag == c['name']]
            if len(m) == 1:
                chk(c, m[0], f"{path}/{c['name']}")

    chk(app_model(preset_path), root, 'appModel')
    return bad


def load_chain(specs):
    chain = []
    for spec in specs:
        ppath, _, preset = spec.partition('=')
        p = load_plugin(ppath)
        if preset:
            st = apply_preset(p, preset)
            print(f"{Path(ppath).name} <- {Path(preset).name}: {st['set']} values set, "
                  f"{st['changed']} differ from the plugin's default, missing {st['missing']}")
        else:
            print(f"{Path(ppath).name}: default state")
        chain.append((p, preset or None))
    return chain


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('di')
    ap.add_argument('out')
    ap.add_argument('chain', nargs='+', metavar='PLUGIN.vst3[=PRESET.xml]')
    a = ap.parse_args()

    chain = load_chain(a.chain)
    time.sleep(SETTLE)
    for p, preset in chain:
        if preset:
            bad = read_back(p, preset)
            print(f"  {Path(preset).name} read-back mismatches: {len(bad)}")
            for line in bad[:20]:
                print(f"    {line}")

    x, sr = sf.read(a.di, always_2d=True)
    x = x.T
    if x.shape[0] == 1:
        x = np.vstack([x, x])
    y = Pedalboard([p for p, _ in chain])(x.astype(np.float32), sr)
    print(f"in peak {np.abs(x).max():.3f}  out peak {np.abs(y).max():.3f}  "
          f"{y.shape[0]} ch, {y.shape[1] / sr:.1f} s @ {sr} Hz")
    sf.write(a.out, y.T, sr, subtype='FLOAT')
    print("wrote", a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
