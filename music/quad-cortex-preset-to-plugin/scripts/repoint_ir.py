#!/usr/bin/env python3
"""Repoint every IR file path in a Neural DSP preset from OLD to NEW.

Use it after moving an impulse response out of a temporary folder (such as
Downloads): every string prop containing OLD is rewritten with NEW, in
place. A copy of the original is written to PRESET.pre-irmove first, and
the result is loaded back to confirm it still round-trips, OLD is gone and
the new paths exist on disk.

Usage (standard library only):
  python3 -I repoint_ir.py PRESET.xml OLD_PREFIX NEW_PREFIX [--dry-run]
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ndsp_preset import load, walk, write_tree  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('preset')
    ap.add_argument('old')
    ap.add_argument('new')
    ap.add_argument('--dry-run', action='store_true', help='print the changes, write nothing')
    a = ap.parse_args()

    tree, tail = load(a.preset)
    changed = []

    def rewrite(node):
        for p in node['props']:
            if p[1] == 's' and a.old in p[2]:
                p[2] = p[2].replace(a.old, a.new)
                changed.append((node['name'], p[0], p[2]))
        for c in node['kids']:
            rewrite(c)

    rewrite(tree)
    if not changed:
        sys.exit(f"no paths containing {a.old!r} in {a.preset}")
    for node, key, after in changed:
        exists = 'exists' if os.path.exists(after) else 'MISSING ON DISK'
        print(f"{node}.{key} -> {after} ({exists})")
    if a.dry_run:
        return 0

    shutil.copy2(a.preset, a.preset + '.pre-irmove')
    with open(a.preset, 'wb') as fh:
        fh.write(write_tree(tree) + tail)

    back, _ = load(a.preset)
    left = [k for _, k, ty, v in walk(back) if ty == 's' and a.old in v.replace(a.new, '')]
    missing = [v for _, _, v in changed if not os.path.exists(v)]
    print(f"backup: {a.preset}.pre-irmove")
    print(f"read back: round-trip ok, old path remaining in {len(left)} props, "
          f"{len(missing)} new paths missing on disk")
    return 1 if left or missing else 0


if __name__ == '__main__':
    sys.exit(main())
