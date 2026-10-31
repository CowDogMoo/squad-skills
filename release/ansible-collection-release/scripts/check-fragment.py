#!/usr/bin/env python3
"""Validate an antsibull-changelog fragment beyond what `antsibull-changelog lint` checks.

Usage: check-fragment.py FRAGMENT [CONFIG]

CONFIG defaults to changelogs/config.yaml next to the fragment's changelogs/
directory. Exits 0 when the fragment is clean, 1 when it has findings, 2 on
usage or parse errors.
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML is required (pip install pyyaml)")

FORBIDDEN_KEYS = {"release_date", "ancestor", "releases"}
DEFAULT_SECTIONS = [
    "major_changes",
    "minor_changes",
    "breaking_changes",
    "deprecated_features",
    "removed_features",
    "security_fixes",
    "bugfixes",
    "known_issues",
]
# A plain (unquoted) list item with " #" is cut at the comment marker.
UNQUOTED_HASH = re.compile(r"""^\s*-\s+(?!['"|>])\S.*?\s#""")


def load_sections(config_path: Path) -> list[str]:
    if not config_path.exists():
        print(f"note: {config_path} not found; using antsibull's default sections")
        return DEFAULT_SECTIONS
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    sections = config.get("sections")
    if not sections:
        return DEFAULT_SECTIONS
    return [s[0] if isinstance(s, list) else s for s in sections]


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    fragment = Path(sys.argv[1])
    if not fragment.exists():
        print(f"error: {fragment} not found", file=sys.stderr)
        return 2
    config = (
        Path(sys.argv[2])
        if len(sys.argv) == 3
        else fragment.resolve().parent.parent / "config.yaml"
    )

    raw = fragment.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        print(f"error: {fragment} is not valid YAML: {exc}", file=sys.stderr)
        return 2

    findings: list[str] = []
    if not isinstance(data, dict) or not data:
        findings.append("fragment must be a non-empty mapping of section -> entries")
        data = {}

    allowed = set(load_sections(config)) | {"release_summary"}
    for key, value in data.items():
        if key in FORBIDDEN_KEYS:
            findings.append(f"'{key}' must not appear in a fragment; antsibull adds it")
            continue
        if key not in allowed:
            findings.append(
                f"section '{key}' is not in {config.name} (allowed: {', '.join(sorted(allowed))})"
            )
        if key == "release_summary":
            if not isinstance(value, str) or not value.strip():
                findings.append("release_summary must be a non-empty string, not a list")
            continue
        if not isinstance(value, list) or not value:
            findings.append(f"section '{key}' must be a non-empty list of strings")
            continue
        for entry in value:
            if not isinstance(entry, str):
                findings.append(f"section '{key}' has a non-string entry: {entry!r}")
            elif entry.count("(") != entry.count(")"):
                findings.append(f"section '{key}' has unbalanced parentheses: {entry!r}")

    for lineno, line in enumerate(raw.splitlines(), 1):
        if UNQUOTED_HASH.match(line):
            findings.append(
                f"line {lineno}: unquoted ' #' is parsed as a comment and truncates the entry; "
                f"single-quote it: {line.strip()}"
            )

    if findings:
        print(f"{fragment}: {len(findings)} finding(s)")
        for f in findings:
            print(f"  - {f}")
        return 1
    print(f"{fragment}: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
