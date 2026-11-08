#!/usr/bin/env python3
"""Turn a target layout (plans/<name>.target.json) into Unjiggle operations, and check a
`json check-operations` result against that target. Plain Python, no Unjiggle needed.

Target file:
  {
    "daily": ["com.apple.MobileSMS", "com.apple.mobileslideshow"],
    "renames": [["Google", "Work"]],
    "folders": [
      {"name": "Work", "how": "move", "apps": ["com.google.Docs", "com.apple.mobilenotes"]},
      {"name": "AI", "how": "create", "page": 1, "apps": ["com.openai.chat"]}
    ],
    "app_library": ["com.example.unused"]
  }
  daily       optional. Loose on page 1, in this order, via rebuild_pages. rebuild_pages takes
              every app it isn't given off the Home Screen first, so with "daily" every movable
              app must be placed somewhere in the target (build refuses otherwise).
  renames     optional [old, new] pairs, applied before the folder ops.
  folders     "move" fills an existing folder (name after renames); "create" makes a new one,
              optionally on 0-based "page".
  app_library optional. Taken off the Home Screen; the apps stay installed.

  python3 build_plan.py build plans/x.target.json state/scan.json state/fixed.json plans/x.ops.json
  python3 build_plan.py verify plans/x.target.json state/scan.json state/x.check.json
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def items_ids(items):
    out = []
    for it in items:
        if it.get("type") == "app":
            out.append(it["app"]["bundle_id"])
        elif it.get("type") == "folder":
            for page in it["folder"]["apps"]:
                out.extend(a["bundle_id"] for a in page)
    return out


def layout_ids(layout):
    ids = items_ids(layout.get("dock", []))
    for page in layout.get("pages", []):
        ids.extend(items_ids(page))
    return ids


def placed(target):
    ids = Counter(target.get("daily", []))
    for folder in target.get("folders", []):
        ids.update(folder["apps"])
    ids.update(target.get("app_library", []))
    return ids


def build(args) -> None:
    target, scan = load(args.target), load(args.scan)
    fixed_data = load(args.fixed)
    fixed = set(fixed_data["fixed"] if isinstance(fixed_data, dict) else fixed_data)
    counts = Counter(layout_ids(scan))
    dock = set(items_ids(scan.get("dock", [])))
    movable = set(counts) - dock - fixed

    assigned = placed(target)
    dupes = sorted(b for b, n in assigned.items() if n > 1)
    unknown = sorted(b for b in assigned if b not in counts)
    unmovable = sorted(b for b in assigned if b in fixed or b in dock)
    unplaced = sorted(movable - set(assigned))
    print(f"apps {len(counts)}: dock {len(dock)}, fixed {len(fixed)}, movable {len(movable)}; placed {len(assigned)}")
    problems = []
    if dupes:
        problems.append(f"placed twice: {dupes}")
    if unknown:
        problems.append(f"not on the Home Screen (drag them out on the phone first): {unknown}")
    if unmovable:
        problems.append(f"fixed or in the dock, no op will move them: {unmovable}")
    if unplaced and target.get("daily"):
        problems.append(f"rebuild_pages would take these off the Home Screen; place them: {unplaced}")
    elif unplaced:
        more = f" (+{len(unplaced) - 10} more)" if len(unplaced) > 10 else ""
        print(f"note: {len(unplaced)} movable apps stay where they are: {unplaced[:10]}{more}")
    if problems:
        sys.exit("refusing to write ops:\n  " + "\n  ".join(problems))

    ops = []
    if target.get("daily"):
        ops.append({"action": "rebuild_pages", "bundle_ids": target["daily"]})
    ops += [{"action": "rename_folder", "old_name": old, "folder_name": new} for old, new in target.get("renames", [])]
    for folder in target.get("folders", []):
        if folder.get("how") == "create":
            op = {"action": "create_folder", "folder_name": folder["name"], "bundle_ids": folder["apps"]}
            if folder.get("page") is not None:
                op["target_page"] = folder["page"]
            ops.append(op)
    for folder in target.get("folders", []):
        if folder.get("how", "move") == "move":
            ops.append({"action": "move_to_folder", "folder_name": folder["name"], "bundle_ids": folder["apps"]})
    if target.get("app_library"):
        ops.append({"action": "move_to_app_library", "bundle_ids": target["app_library"]})
    Path(args.out).write_text(json.dumps({"snapshot_id": scan["snapshot_id"], "operations": ops}, indent=1) + "\n")
    print(f"wrote {len(ops)} operations to {args.out}")


def verify(args) -> None:
    target, scan, check = load(args.target), load(args.scan), load(args.check)
    proposed = check["proposed_layout"]
    library = set(target.get("app_library", []))
    before = Counter(b for b in layout_ids(scan) if b not in library)
    after = Counter(layout_ids(proposed))
    ok = True
    gone = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    changed = sorted(b for b in before if b in after and before[b] != after[b])
    print(f"icons before {sum(before.values())} (excluding App Library moves) / after {sum(after.values())}")
    if gone or added or changed:
        print(f"  gone {gone}\n  added {added}\n  count changed {changed}")
        ok = False
    still_there = sorted(library & set(after))
    if still_there:
        print(f"meant for the App Library but still on the Home Screen: {still_there}")
        ok = False
    folders = {}
    for page in proposed.get("pages", []):
        for it in page:
            if it.get("type") == "folder":
                name = it["folder"]["display_name"]
                if name in folders:
                    print(f"two folders named {name}")
                    ok = False
                folders[name] = set(items_ids([it]))
    for folder in target.get("folders", []):
        missing = set(folder["apps"]) - folders.get(folder["name"], set())
        if missing:
            print(f"folder {folder['name']} is missing {sorted(missing)}")
            ok = False
    if target.get("daily"):
        first = proposed.get("pages", [[]])[0]
        loose = set(items_ids([it for it in first if it.get("type") == "app"]))
        if set(target["daily"]) - loose:
            print(f"not loose on page 1: {sorted(set(target['daily']) - loose)}")
            ok = False
    print("verify:", "OK" if ok else "PROBLEMS")
    sys.exit(0 if ok else 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    for name in ("target", "scan", "fixed", "out"):
        b.add_argument(name)
    v = sub.add_parser("verify")
    for name in ("target", "scan", "check"):
        v.add_argument(name)
    args = parser.parse_args()
    {"build": build, "verify": verify}[args.command](args)


if __name__ == "__main__":
    main()
