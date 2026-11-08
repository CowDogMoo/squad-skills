#!/usr/bin/env python3
"""Print the Home Screen icons that no Unjiggle operation will move, as JSON. Read-only.

Unjiggle silently drops these IDs from every operation:
  - pinned: an entry with no bundleIdentifier. On iOS 26 that's every offloaded app
    (cloud icon), plus web clips and App Clips.
  - duplicate: an app with more than one icon (iOS 26 can show Settings or Shortcuts twice).
A folder holding any of them survives every operation, rebuild_pages included.

Run it with the workspace venv's python, from the workspace root:
  .venv/bin/python <skill>/scripts/fixed_ids.py > state/fixed.json
  .venv/bin/python <skill>/scripts/fixed_ids.py --from-file ~/.unjiggle/backups/layout-....json
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    from unjiggle import device
    from unjiggle.device import dates_from_backup, entry_app_id, is_folder_entry, is_pinned_entry
    from unjiggle.layout_engine import _raw_fixed_ids
except ImportError:
    sys.exit("unjiggle is not importable: run this with the workspace venv (.venv/bin/python).")


def raw_entries(raw):
    pages = raw if isinstance(raw, list) else [raw.get("buttonBar", [])] + raw.get("iconLists", [])
    for page in pages:
        for item in page:
            if is_folder_entry(item):
                for folder_page in item.get("iconLists") or []:
                    yield from folder_page
            else:
                yield item


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--from-file", help="read a saved raw icon state (an Unjiggle backup) instead of the phone")
    args = parser.parse_args()
    if args.from_file:
        raw = dates_from_backup(json.loads(Path(args.from_file).read_text()))
    else:
        lockdown, _ = device.connect()
        raw = device.read_layout(lockdown).raw

    fixed = _raw_fixed_ids(raw)
    pinned = {entry_app_id(e) for e in raw_entries(raw) if is_pinned_entry(e)} & fixed
    counts = Counter(entry_app_id(e) for e in raw_entries(raw) if entry_app_id(e))
    duplicate = {b for b in fixed if counts[b] > 1}
    json.dump({
        "fixed": sorted(fixed),
        "pinned": sorted(pinned),
        "duplicate": sorted(duplicate),
    }, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
