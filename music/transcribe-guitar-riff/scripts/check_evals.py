#!/usr/bin/env python3
"""Structural check of a skill's evals/evals.json (mirrors the repo CI rules)."""
import json
import os
import sys


def main(skill_dir: str) -> int:
    path = os.path.join(skill_dir, "evals", "evals.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    errors = []
    name = os.path.basename(os.path.normpath(skill_dir))
    if data.get("skill_name") != name:
        errors.append(f"skill_name {data.get('skill_name')!r} != directory {name!r}")
    evals = data.get("evals", [])
    if len(evals) < 2:
        errors.append("need at least 2 evals")
    for ev in evals:
        if not ev.get("prompt"):
            errors.append(f"eval {ev.get('id')} has no prompt")
        if len(ev.get("expectations", [])) < 2:
            errors.append(f"eval {ev.get('id')} needs at least 2 expectations")
        for f in ev.get("files", []):
            if not os.path.exists(os.path.join(skill_dir, f)):
                errors.append(f"eval {ev.get('id')} references missing fixture {f}")
    if errors:
        print("EVALS FAILED:\n  " + "\n  ".join(errors))
        return 1
    print(f"EVALS OK ({len(evals)} evals)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
