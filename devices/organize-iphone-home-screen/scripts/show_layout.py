#!/usr/bin/env python3
"""Render a Home Screen layout as readable text: dock, then each page with its folders.

Takes a `json scan` output, or a `json check-operations` output (its proposed_layout).
With --fixed (the output of fixed_ids.py), offloaded/pinned icons get ☁ and duplicate
icons get ⧉. With --names (a scan), names come from that scan, which helps when the
layout being shown is a check output. Plain Python, no Unjiggle needed.

  python3 show_layout.py state/scan.json --fixed state/fixed.json
  python3 show_layout.py state/reorg.check.json --fixed state/fixed.json --names state/scan.json
"""
import argparse
import json
from pathlib import Path


def collect_names(layout, names):
    for page in [layout.get("dock", []), *layout.get("pages", [])]:
        for it in page:
            if it.get("type") == "app":
                names.setdefault(it["app"]["bundle_id"], it["app"].get("display_name"))
            elif it.get("type") == "folder":
                for fp in it["folder"]["apps"]:
                    for a in fp:
                        names.setdefault(a["bundle_id"], a.get("display_name"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("layout", help="a json scan or json check-operations output")
    parser.add_argument("--fixed", help="fixed_ids.py output")
    parser.add_argument("--names", help="a json scan to take display names from")
    args = parser.parse_args()

    data = json.loads(Path(args.layout).read_text())
    layout = data.get("proposed_layout", data)
    fixed = json.loads(Path(args.fixed).read_text()) if args.fixed else {}
    pinned, duplicate = set(fixed.get("pinned", [])), set(fixed.get("duplicate", []))
    names = {}
    if args.names:
        collect_names(json.loads(Path(args.names).read_text()), names)
    collect_names(layout, names)

    def name(bundle_id):
        n = names.get(bundle_id) or bundle_id
        for sep in (":", " - ", " – "):
            n = n.split(sep)[0]
        n = n.strip()
        return n + (" ☁" if bundle_id in pinned else " ⧉" if bundle_id in duplicate else "")

    def show(it):
        kind = it.get("type")
        if kind == "app":
            return name(it["app"]["bundle_id"])
        if kind == "folder":
            pages = [[name(a["bundle_id"]) for a in fp] for fp in it["folder"]["apps"]]
            count = sum(len(p) for p in pages)
            return f"📁 {it['folder']['display_name']} ({count}): " + " | ".join(", ".join(p) for p in pages)
        widget = it.get("widget", {})
        return f"▦ widget {widget.get('container_bundle_id', '')} {widget.get('grid_size', '')}".rstrip()

    print("DOCK:", ", ".join(show(x) for x in layout.get("dock", [])))
    for i, page in enumerate(layout.get("pages", []), 1):
        print(f"\nPAGE {i}")
        for it in page:
            print("  ", show(it))


if __name__ == "__main__":
    main()
