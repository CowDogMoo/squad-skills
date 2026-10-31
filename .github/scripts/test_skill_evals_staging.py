#!/usr/bin/env python3
"""Tests for how skill_evals.py stages case inputs for claude plugin eval.

In Skill Evals run 41233408616 (Claude Code 2.1.296), ansible-collection-release
case-1 and case-2 scored 0: their prompts pointed the agent at inputs under
staged/<skill>/evals/files/, and claude plugin eval denies the agent every
directory named evals/ (as well as the --eval-dir) so it cannot read case
definitions. Every read was refused, so the agent never saw its inputs.

Run: python .github/scripts/test_skill_evals_staging.py
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import skill_evals  # noqa: E402

EXPECTATION = "The response names the missing section and does not invent one"


class StagingTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.dest = self.tmp / "staged"

    def stage(self, name: str, src: Path, opts: dict | None = None) -> list[str]:
        runnable = {name: opts or {}}
        with mock.patch.object(skill_evals, "allowlist", return_value=runnable), \
                contextlib.redirect_stdout(io.StringIO()):
            return skill_evals.stage(name, src, self.dest)

    def make_skill(self, files: dict[str, str], cases: list[dict]) -> Path:
        skill = self.tmp / "src" / "demo"
        for rel, text in {"SKILL.md": "---\nname: demo\n---\n", **files}.items():
            (skill / rel).parent.mkdir(parents=True, exist_ok=True)
            (skill / rel).write_text(text, encoding="utf-8")
        evals = {"skill_name": "demo", "evals": cases}
        (skill / "evals").mkdir(exist_ok=True)
        (skill / "evals" / "evals.json").write_text(json.dumps(evals), encoding="utf-8")
        return skill

    def test_every_runnable_skill_can_read_its_inputs(self) -> None:
        skills = skill_evals.skill_dirs()
        for name in sorted(skill_evals.allowlist()):
            with self.subTest(skill=name):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(skill_evals.stage(name, skills[name], self.dest), [])
                self.assertEqual(skill_evals.check_staged(self.dest / name), [])

    def test_ansible_collection_release_inputs_leave_evals_dir(self) -> None:
        name = "ansible-collection-release"
        with contextlib.redirect_stdout(io.StringIO()):
            skill_evals.stage(name, skill_evals.skill_dirs()[name], self.dest)
        plugin = self.dest / name
        for case in ("case-1", "case-2"):
            prompt = (plugin / skill_evals.CASE_DIR / case / "prompt.md").read_text(encoding="utf-8")
            listed, named = skill_evals.prompt_paths(prompt, plugin)
            self.assertTrue(listed, case)
            self.assertNotIn("/evals/", prompt)
            for path in listed + named:
                self.assertEqual(path.relative_to(plugin).parts[0], skill_evals.INPUTS_DIR)
            for path in listed:
                self.assertTrue(path.is_file(), path)
        self.assertFalse((plugin / "evals").exists())

    def test_run_41233408616_layout_is_caught(self) -> None:
        plugin = self.dest / "demo"
        (plugin / "evals" / "files").mkdir(parents=True)
        (plugin / "evals" / "files" / "in.txt").write_text("x\n", encoding="utf-8")
        skill_evals.write_case(
            plugin / skill_evals.CASE_DIR / "case-1",
            f"Read it.\n\n{skill_evals.INPUT_LIST_HEADER}\n- {plugin / 'evals' / 'files' / 'in.txt'}",
            ["Read"], {"expectation-1": f"---\ntype: llm\nweight: 1\n---\n\n{EXPECTATION}\n"}, 5, 60,
        )
        problems = skill_evals.check_staged(plugin)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("is inside evals/", problems[0])

    def test_inputs_are_staged_and_expectations_are_not(self) -> None:
        skill = self.make_skill(
            {"evals/files/col/a.yaml": "a: 1\n", "evals/notes.md": EXPECTATION, "scripts/x.py": ""},
            [
                {"id": 1, "prompt": "Check evals/files/col/a.yaml and ./evals/files/col/.",
                 "expectations": [EXPECTATION], "files": ["evals/files/col/a.yaml"]},
                {"id": 2, "prompt": "Run scripts/x.py.", "expectations": ["ok"],
                 "files": ["scripts/x.py"]},
            ],
        )
        self.assertEqual(self.stage("demo", skill), [])
        plugin = self.dest / "demo"
        self.assertEqual(skill_evals.check_staged(plugin), [])
        self.assertTrue((plugin / "eval-inputs" / "files" / "col" / "a.yaml").is_file())
        self.assertFalse((plugin / "evals").exists())
        self.assertFalse((plugin / "eval-inputs" / "notes.md").exists())
        prompt = (plugin / "ci-evals" / "case-1" / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(f"Check {plugin}/eval-inputs/files/col/a.yaml and {plugin}/eval-inputs/files/col/.", prompt)
        prompt = (plugin / "ci-evals" / "case-2" / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(f"- {plugin}/scripts/x.py", prompt)

    def test_prompt_rewrite_leaves_other_paths_alone(self) -> None:
        sub = skill_evals.EVALS_REF.sub
        self.assertEqual(sub("R/", "see evals/a and `evals/b`"), "see R/a and `R/b`")
        self.assertEqual(sub("R/", "see ./evals/a"), "see R/a")
        for text in ("my-evals/a", "foo/evals/a", "evals.json", "ci-evals/a"):
            self.assertEqual(sub("R/", text), text)

    def test_input_under_a_fenced_name_is_caught(self) -> None:
        for rel, why in [
            ("evals/files/ci-evals/in.txt", "is inside ci-evals/"),
            ("evals/files/Evals/in.txt", "is inside Evals/"),
            ("evals/files/.git/in.txt", "is inside .git/"),
            ("evals/files/out/report.html", "is named report.html"),
        ]:
            with self.subTest(rel=rel):
                skill = self.make_skill(
                    {rel: "x\n"},
                    [{"id": 1, "prompt": "Read it.", "expectations": ["ok"], "files": [rel]}],
                )
                self.assertEqual(self.stage("demo", skill), [])
                problems = skill_evals.check_staged(self.dest / "demo")
                self.assertTrue(any(why in p for p in problems), problems)
                for d in (self.dest, self.tmp / "src"):
                    for p in sorted(d.rglob("*"), reverse=True):
                        p.rmdir() if p.is_dir() else p.unlink()

    def test_input_beside_run_results_is_caught(self) -> None:
        skill = self.make_skill(
            {"evals/files/run/in.txt": "x\n", "evals/files/run/old/aggregate-result.json": "{}"},
            [{"id": 1, "prompt": "Read it.", "expectations": ["ok"],
              "files": ["evals/files/run/in.txt", "evals/files/run/old/aggregate-result.json"]}],
        )
        self.assertEqual(self.stage("demo", skill), [])
        problems = skill_evals.check_staged(self.dest / "demo")
        self.assertTrue(any("holds run results" in p for p in problems), problems)

    def test_expectation_in_a_reachable_file_is_caught(self) -> None:
        skill = self.make_skill(
            {"evals/files/in.txt": f"cheat sheet: {EXPECTATION}\n"},
            [{"id": 1, "prompt": "Read it.", "expectations": [EXPECTATION],
              "files": ["evals/files/in.txt"]}],
        )
        self.assertEqual(self.stage("demo", skill), [])
        problems = skill_evals.check_staged(self.dest / "demo")
        self.assertEqual(problems, ["eval-inputs/files/in.txt holds a case expectation the agent could read"])

    def test_evals_json_cannot_be_an_input(self) -> None:
        skill = self.make_skill(
            {}, [{"id": 1, "prompt": "Read it.", "expectations": ["ok"], "files": ["evals/evals.json"]}],
        )
        self.assertTrue(any("its own expectations" in e for e in skill_evals.check_evals(skill)))

    def test_reserved_inputs_dir_is_refused(self) -> None:
        skill = self.make_skill(
            {"eval-inputs/x.txt": "x\n"},
            [{"id": 1, "prompt": "Hi.", "expectations": ["ok"]}],
        )
        self.assertEqual(self.stage("demo", skill), ["eval-inputs/ is reserved for staged eval inputs"])


if __name__ == "__main__":
    unittest.main()
