#!/usr/bin/env python3
"""Repo policy checks for shared skills and plugin manifests.

  check_skills.py policy [--root DIR]
      - no SKILL.md may declare `allowed-tools` (squad intersects it across
        every loaded skill and never pops it, and Claude Code treats it as a
        pre-approval, so it either strips tools or weakens safety)
      - every plugin manifest carries the same `version`

  check_skills.py version-bump --base REF [--root DIR]
      Fails when skill or manifest content changed against REF but the plugin
      `version` did not, so marketplace consumers on a pinned version still
      receive the change.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

MANIFESTS = (
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "music/.claude-plugin/plugin.json",
)
BUMP_PATHS = re.compile(
    r"^(?:(?:cooking|devices|music|release|testing|writing-quality)/(?!.*/evals/).*"
    r"|\.claude-plugin/.*|\.codex-plugin/.*)$"
)
ALLOWED_TOOLS = re.compile(r"^allowed-tools\s*:", re.MULTILINE)


def frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)
    return match.group(1) if match else ""


def skill_files(root: Path) -> list[Path]:
    return sorted(
        p for p in root.glob("*/*/SKILL.md") if not p.parts[-3].startswith(".")
    )


def check_allowed_tools(root: Path) -> list[str]:
    return [
        f"{p.relative_to(root)}: `allowed-tools` is banned on shared skills"
        for p in skill_files(root)
        if ALLOWED_TOOLS.search(frontmatter(p))
    ]


def load(root: Path, rel: str) -> dict:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def check_versions(root: Path) -> list[str]:
    versions = {}
    for rel in MANIFESTS:
        if (root / rel).exists():
            versions[rel] = load(root, rel).get("version")
    errors = [f"{rel}: no `version`" for rel, v in versions.items() if not v]
    if len({v for v in versions.values() if v}) > 1:
        errors.append(
            "plugin manifests disagree on version: "
            + ", ".join(f"{rel}={v}" for rel, v in versions.items())
        )
    return errors


def policy(root: Path) -> list[str]:
    return check_allowed_tools(root) + check_versions(root)


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def version_bump(root: Path, base: str) -> list[str]:
    changed = [
        f for f in git(root, "diff", "--name-only", f"{base}...HEAD").splitlines()
        if BUMP_PATHS.match(f)
    ]
    if not changed:
        return []
    old = json.loads(git(root, "show", f"{base}:{MANIFESTS[0]}")).get("version")
    new = load(root, MANIFESTS[0]).get("version")
    if old != new:
        return []
    return [
        f"plugin version is still {new} but {len(changed)} skill/manifest file(s) "
        f"changed (e.g. {changed[0]}); bump `version` in all plugin manifests"
    ]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["policy", "version-bump"])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--base", help="git ref to compare against (version-bump)")
    args = ap.parse_args(argv)
    if args.command == "policy":
        errors = policy(args.root)
    else:
        if not args.base:
            ap.error("version-bump needs --base")
        errors = version_bump(args.root, args.base)
    for e in errors:
        print(f"::error::{e}")
    if errors:
        return 1
    print(f"✓ {args.command} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
