#!/usr/bin/env python3
"""Reorder every Home Screen folder so installed apps come first and offloaded icons after.

Unjiggle has no in-folder reorder, `move_to_folder` always appends, and it never moves an
offloaded (pinned) icon. So in a folder that holds one, the installed apps always sit behind
the cloud icons. This script writes the icon state directly instead. Each folder keeps
exactly the same entries; only their order and the folder page breaks (pages of 9) change.
The dock, the pages, the widgets and every entry's fields stay as the phone gave them.

The write bypasses `json check-operations` / `json apply-checked`, so the user approves
each apply in chat, after seeing the preview.

Run it with the workspace venv's python, from the workspace root:
  .venv/bin/python <skill>/scripts/installed_first.py preview
  .venv/bin/python <skill>/scripts/installed_first.py apply
  .venv/bin/python <skill>/scripts/installed_first.py preview --from-file raw.json   # offline

preview is read-only. It saves the raw state and the proposal under --state (default
state/), and apply refuses unless the phone still matches that saved state.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

try:
    from unjiggle import device
    from unjiggle.analyzer import FOLDER_PAGE_SLOTS
    from unjiggle.device import (
        dates_from_backup,
        entry_app_id,
        is_app_store_entry,
        is_folder_entry,
        is_pinned_entry,
        layout_parse_integrity,
        parse_layout_state,
    )
except ImportError:
    sys.exit("unjiggle is not importable: run this with the workspace venv (.venv/bin/python).")


def dump(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def pretty(value) -> str:
    return json.dumps(value, indent=1, sort_keys=True, default=str)


def containers(raw) -> list:
    return raw if isinstance(raw, list) else [raw.get("buttonBar", [])] + raw.get("iconLists", [])


def folders(raw):
    for page in containers(raw):
        for item in page:
            if is_folder_entry(item):
                yield item


def entries(folder) -> list:
    return [e for page in folder.get("iconLists") or [] for e in page]


def reorder(raw):
    """A deep copy of raw with installed apps first in every folder, plus the names of the
    folders it changed and skipped."""
    new = copy.deepcopy(raw)
    changed, skipped = [], []
    for folder in folders(new):
        name = folder.get("displayName")
        flat = entries(folder)
        # An entry Unjiggle can't name isn't an app icon and could be anything: leave the folder.
        if any(entry_app_id(e) is None for e in flat):
            skipped.append(name)
            continue
        ordered = [e for e in flat if is_app_store_entry(e)] + [e for e in flat if not is_app_store_entry(e)]
        pages = [ordered[i:i + FOLDER_PAGE_SLOTS] for i in range(0, len(ordered), FOLDER_PAGE_SLOTS)]
        if pages != folder["iconLists"]:
            folder["iconLists"] = pages
            changed.append(name)
    return new, changed, skipped


def normalized(raw) -> str:
    """raw with each folder's entries flattened and sorted: two states that differ only in
    the order of entries inside folders normalize to the same string."""
    n = copy.deepcopy(raw)
    for folder in folders(n):
        folder["iconLists"] = sorted(dump(e) for e in entries(folder))
    return dump(n)


def verify(before, after) -> list:
    problems = []
    if normalized(before) != normalized(after):
        problems.append("something other than in-folder order changed")
    names = [f.get("displayName") for f in folders(after)]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        problems.append(f"duplicate folder names (read-back can't tell them apart): {dupes}")
    for folder in folders(after):
        if any(not page or len(page) > FOLDER_PAGE_SLOTS for page in folder.get("iconLists") or []):
            problems.append(f"folder {folder.get('displayName')} has an empty or overfull page")
    if layout_parse_integrity(parse_layout_state(after)) != layout_parse_integrity(parse_layout_state(before)):
        problems.append("Unjiggle's parse integrity differs")
    return problems


def name_map(state: Path) -> dict:
    """bundle ID -> display name from a `json scan` in the state folder, if there is one."""
    names = {}
    scan_path = state / "scan.json"
    if not scan_path.exists():
        return names
    scan = json.loads(scan_path.read_text())
    for page in [scan.get("dock", []), *scan.get("pages", [])]:
        for it in page:
            if it.get("type") == "app":
                names[it["app"]["bundle_id"]] = it["app"].get("display_name")
            elif it.get("type") == "folder":
                for fp in it["folder"]["apps"]:
                    for a in fp:
                        names[a["bundle_id"]] = a.get("display_name")
    return names


def label(entry, names) -> str:
    b = entry_app_id(entry)
    n = names.get(b) or b
    # App Store names carry taglines ("Maps: Navigate & Explore"); keep the name.
    for sep in (":", " - ", " – "):
        n = n.split(sep)[0]
    n = n.strip()
    return f"☁ {n}" if is_pinned_entry(entry) else n


def show(before, after, changed, skipped, names) -> None:
    old = {f.get("displayName"): f for f in folders(before)}
    for folder in folders(after):
        name = folder.get("displayName")
        if name not in changed:
            continue
        pattern = " | ".join("".join("☁" if is_pinned_entry(e) else "·" for e in p) for p in old[name]["iconLists"])
        print(f"\n📁 {name}   before: {pattern}")
        for i, page in enumerate(folder["iconLists"], 1):
            print(f"   page {i}: " + ", ".join(label(e, names) for e in page))
    unchanged = [f.get("displayName") for f in folders(after) if f.get("displayName") not in changed + skipped]
    print(f"\nchanged {len(changed)} folders; unchanged {unchanged}; skipped {skipped}")


def folder_orders(raw) -> dict:
    return {f.get("displayName"): [entry_app_id(e) for e in entries(f)] for f in folders(raw)}


def preview(args) -> None:
    state = Path(args.state)
    if args.from_file:
        raw = dates_from_backup(json.loads(Path(args.from_file).read_text()))
    else:
        lockdown, _ = device.connect()
        raw = device.read_layout(lockdown).raw
    new, changed, skipped = reorder(raw)
    problems = verify(raw, new)
    show(raw, new, changed, skipped, name_map(state))
    print("verify:", "OK" if not problems else problems)
    if not args.from_file:
        state.mkdir(parents=True, exist_ok=True)
        (state / "installed_first.before.json").write_text(pretty(raw))
        (state / "installed_first.proposed.json").write_text(pretty(new))
    sys.exit(1 if problems else 0)


def apply(args) -> None:
    from unjiggle.safety import verified_backup

    state = Path(args.state)
    before_path, proposed_path = state / "installed_first.before.json", state / "installed_first.proposed.json"
    if not before_path.exists() or not proposed_path.exists():
        sys.exit("Not written: run preview first and get the user's approval for it.")
    lockdown, _ = device.connect()
    layout = device.read_layout(lockdown)
    raw = layout.raw
    if pretty(raw) != before_path.read_text():
        sys.exit("Not written: the phone changed since the preview. Run preview again and re-ask.")
    new, changed, _ = reorder(raw)
    if pretty(new) != proposed_path.read_text():
        sys.exit("Not written: the rebuilt proposal differs from the previewed one.")
    problems = verify(raw, new)
    if problems:
        sys.exit(f"Not written: {problems}")
    if not changed:
        sys.exit("Not written: every folder already lists installed apps first.")
    backup = verified_backup(lockdown, layout)
    print(f"backup: {backup}")
    if dump(device.read_layout(lockdown).raw) != dump(raw):
        sys.exit(f"Not written: the phone changed after the backup. Backup: {backup}")
    device.write_layout(lockdown, new)
    after = device.read_layout(lockdown).raw
    (state / "installed_first.after.json").write_text(pretty(after))
    if dump(after) == dump(new):
        print(f"written and read back exactly as previewed ({len(changed)} folders). Backup: {backup}")
        return
    want, got = folder_orders(new), folder_orders(after)
    for name in want:
        if want[name] != got.get(name):
            print(f"folder {name} differs: wanted {want[name]} got {got.get(name)}")
    if normalized(after) != normalized(new):
        print("something outside folder order differs from the proposal: rescan and diff before anything else")
    sys.exit(f"Read-back does not match the proposal. Stop and report. Backup: {backup}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["preview", "apply"])
    parser.add_argument("--state", default="state", help="workspace state folder (default: state)")
    parser.add_argument("--from-file", help="preview only: read a saved raw icon state instead of the phone")
    args = parser.parse_args()
    if args.command == "apply" and args.from_file:
        parser.error("--from-file is for preview only")
    {"preview": preview, "apply": apply}[args.command](args)


if __name__ == "__main__":
    main()
