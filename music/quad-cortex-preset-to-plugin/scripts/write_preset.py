#!/usr/bin/env python3
"""Write a Neural DSP preset from a template preset plus named values.

Start from a template (the plugin's factory `Default.xml`, or an existing
User preset for a variant), set values by key, write the result, then load
it back and check every value landed. Keys are `prop` or `prop@node`, where
node is the ValueTree type that holds the prop. A bare key sets that prop in
every node that has it: a bare `sectionActive` switches every section and
still reads back ok, so scope it (`sectionActive@pedalParameters`) to change
one section. Values are given as text and converted to the type the template holds.

A spec file is a flat JSON object of key -> value; keys starting with `_`
are comments. `--set` pairs are applied after the spec and override it.

Refuses to write when a key is not in the template (a typo, or a key the
plugin version does not have), and refuses to overwrite an existing file;
to replace one, remove it first.

Usage (standard library only):
  python3 -I write_preset.py TEMPLATE.xml OUT.xml --spec SPEC.json
  python3 -I write_preset.py SRC.xml OUT.xml --set leadEQBand1=2.7 --set outputGain=3.4
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ndsp_preset import coerce, get_values, load, walk, write_tree, set_values  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('template')
    ap.add_argument('out')
    ap.add_argument('--spec', help='JSON object of key -> value')
    ap.add_argument('--set', action='append', default=[], metavar='KEY=VALUE')
    a = ap.parse_args()

    values = {}
    if a.spec:
        with open(a.spec, encoding='utf-8') as fh:
            spec = json.load(fh)
        values.update({k: v for k, v in spec.items() if not k.startswith('_')})
    for pair in a.set:
        if '=' not in pair:
            sys.exit(f"--set needs KEY=VALUE, got {pair!r}")
        k, v = pair.split('=', 1)
        values[k] = v
    if not values:
        sys.exit("nothing to set: pass --spec and/or --set")

    tree, tail = load(a.template)
    done = set_values(tree, values)
    missing = sorted(set(values) - done)
    if missing:
        sys.exit(f"keys not found in {a.template}: {missing}")

    out = Path(a.out)
    if out.exists():
        sys.exit(f"{out} exists; refusing to overwrite it (remove it first to replace it)")
    out.write_bytes(write_tree(tree) + tail)

    # Read back from disk and compare every requested value.
    back, _ = load(out)
    got = get_values(back, list(values))
    bad = []
    types = {}
    for _, k, ty, _ in walk(back):
        types.setdefault(k, ty)
    for key, want in values.items():
        prop = key.split('@', 1)[0]
        expect = coerce(types[prop], want)
        if not got[key] or any(v != expect for v in got[key]):
            bad.append(f"{key}: wanted {expect!r}, file has {got[key]!r}")
    if bad:
        sys.exit("read-back FAILED:\n  " + "\n  ".join(bad))
    print(f"wrote {out}: {len(values)} values set, read back ok")


if __name__ == '__main__':
    sys.exit(main())
