#!/usr/bin/env python3
"""Tests for check_skills.py: each policy must pass on the repo and fail on a
deliberately broken copy.

Run with:  python3 .github/scripts/test_check_skills.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import check_skills  # noqa: E402


def make_repo(tmp: Path) -> Path:
    """Copy the files the policy reads into a throwaway git repo."""
    for rel in check_skills.MANIFESTS:
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, dest)
    for skill in check_skills.skill_files(REPO):
        dest = tmp / skill.relative_to(REPO)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(skill, dest)
    return tmp


class PolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = make_repo(Path(self._tmp.name))

    def test_repo_passes(self) -> None:
        self.assertEqual(check_skills.policy(REPO), [])

    def test_allowed_tools_is_banned(self) -> None:
        skill = self.root / "testing/test-writer-honesty/SKILL.md"
        text = skill.read_text(encoding="utf-8")
        skill.write_text(text.replace("\n---\n", "\nallowed-tools: Bash, Read\n---\n", 1), encoding="utf-8")
        errors = check_skills.check_allowed_tools(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("test-writer-honesty", errors[0])

    def test_allowed_tools_in_body_or_comment_is_ignored(self) -> None:
        skill = self.root / "testing/test-writer-honesty/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nallowed-tools: Bash\n", encoding="utf-8")
        self.assertEqual(check_skills.check_allowed_tools(self.root), [])

    def test_invalid_manifest_version(self) -> None:
        manifest = self.root / ".codex-plugin/plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["version"] = "0.0.1"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(check_skills.check_versions(self.root))

    def test_missing_manifest_version(self) -> None:
        manifest = self.root / "music/.claude-plugin/plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        del data["version"]
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(check_skills.check_versions(self.root))


class VersionBumpTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = make_repo(Path(self._tmp.name))
        self.git("init", "-q", "-b", "main")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "add", ".")
        self.commit("base")

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def commit(self, msg: str) -> None:
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-am", msg)

    def edit_skill(self) -> None:
        skill = self.root / "testing/test-writer-honesty/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nmore\n", encoding="utf-8")

    def test_skill_change_without_bump_fails(self) -> None:
        self.git("checkout", "-q", "-b", "pr")
        self.edit_skill()
        self.commit("skill change")
        self.assertEqual(len(check_skills.version_bump(self.root, "main")), 1)

    def test_skill_change_with_bump_passes(self) -> None:
        self.git("checkout", "-q", "-b", "pr")
        self.edit_skill()
        manifest = self.root / ".claude-plugin/plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["version"] += ".1"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.commit("skill change and bump")
        self.assertEqual(check_skills.version_bump(self.root, "main"), [])

    def test_unrelated_change_needs_no_bump(self) -> None:
        self.git("checkout", "-q", "-b", "pr")
        (self.root / "NOTES.md").write_text("x\n", encoding="utf-8")
        self.git("add", "NOTES.md")
        self.commit("docs")
        self.assertEqual(check_skills.version_bump(self.root, "main"), [])


if __name__ == "__main__":
    unittest.main()
