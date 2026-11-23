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
import os
import re
import subprocess
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
                cases = self.dest / name / skill_evals.CASE_DIR
                self.assertFalse(any(p.is_symlink() for p in cases.rglob("*")))

    def test_ansible_collection_release_inputs_leave_evals_dir(self) -> None:
        name = "ansible-collection-release"
        with contextlib.redirect_stdout(io.StringIO()):
            skill_evals.stage(name, skill_evals.skill_dirs()[name], self.dest)
        plugin = self.dest / name
        for case in ("case-1", "case-2"):
            prompt, _criteria = skill_evals.read_case(plugin / skill_evals.CASE_DIR / case)
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
        prompt, _criteria = skill_evals.read_case(plugin / "ci-evals" / "case-1")
        self.assertIn(f"Check {plugin}/eval-inputs/files/col/a.yaml and {plugin}/eval-inputs/files/col/.", prompt)
        prompt = (plugin / "ci-evals" / "case-2" / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(f"- {plugin}/scripts/x.py", prompt)

    def test_inputs_are_granted_to_the_no_skill_arm(self) -> None:
        # Under --ablation with-without the no-skill arm is denied every read
        # inside the plugin, so a case with inputs grants them with
        # context.add_dirs, which may only name a path inside the case
        # directory, containing plain copies of that case's inputs.
        skill = self.make_skill(
            {"evals/files/in.txt": "x\n", "evals/files/other.txt": "other\n", "scripts/x.py": ""},
            [
                {"id": 1, "prompt": "Read evals/files/in.txt.", "expectations": [EXPECTATION],
                 "files": ["evals/files/in.txt"]},
                {"id": 2, "prompt": "Run scripts/x.py.", "expectations": ["ok"],
                 "files": ["scripts/x.py"]},
                {"id": 3, "prompt": "Read evals/files/other.txt.", "expectations": ["ok"],
                 "files": ["evals/files/other.txt"]},
            ],
        )
        self.assertEqual(self.stage("demo", skill), [])
        plugin = self.dest / "demo"
        case_dir = plugin / skill_evals.CASE_DIR / "case-1"
        self.assertFalse((case_dir / "prompt.md").exists())
        case = json.loads((case_dir / "case.yaml").read_text(encoding="utf-8"))
        self.assertEqual(case["context"]["add_dirs"], [skill_evals.CASE_INPUTS])
        inputs = case_dir / skill_evals.CASE_INPUTS
        self.assertTrue(inputs.is_dir())
        self.assertFalse(any(p.is_symlink() for p in case_dir.rglob("*")))
        copied = inputs / "files" / "in.txt"
        self.assertEqual(copied.read_text(encoding="utf-8"), "x\n")
        self.assertFalse((inputs / "files" / "other.txt").exists())
        self.assertFalse((inputs / "evals.json").exists())
        copied.write_text("changed\n", encoding="utf-8")
        self.assertEqual((plugin / skill_evals.INPUTS_DIR / "files" / "in.txt").read_text(), "x\n")
        self.assertEqual((skill / "evals" / "files" / "in.txt").read_text(), "x\n")
        self.assertEqual(case["graders"][0]["criteria"], EXPECTATION)
        self.assertEqual(case["execution"]["allowed_tools"], skill_evals.BASE_TOOLS)
        # An input kept outside evals/ is never granted to the baseline arm.
        self.assertTrue((plugin / skill_evals.CASE_DIR / "case-2" / "prompt.md").is_file())
        self.assertEqual(skill_evals.check_staged(plugin), [])

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

    def test_expectation_in_case_yaml_is_still_checked(self) -> None:
        # read_case must hand check_staged the criteria of case.yaml cases, or
        # the leak scan would pass any input holding its own answer.
        skill = self.make_skill(
            {"evals/files/in.txt": "x\n", "scripts/notes.txt": f"{EXPECTATION}\n"},
            [{"id": 1, "prompt": "Read evals/files/in.txt.", "expectations": [EXPECTATION],
              "files": ["evals/files/in.txt"]}],
        )
        self.assertEqual(self.stage("demo", skill), [])
        problems = skill_evals.check_staged(self.dest / "demo")
        self.assertEqual(problems, ["scripts/notes.txt holds a case expectation the agent could read"])

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

    def test_staged_input_header_avoids_blocked_cp_instruction(self) -> None:
        # claude plugin eval runs `claude -p` under `--permission-mode dontAsk`
        # with `Edit(//<staged-skill>/**)` disallowed and only the scratch cwd
        # in workingDirectories, so Claude Code's Bash filter denies `cp` from
        # staged inputs into cwd. The staged header must stay single-line for
        # prompt_paths() and steer the model away from `cp`/`mv` instead of
        # telling it "copy one into your working directory".
        self.assertNotIn("\n", skill_evals.INPUT_LIST_HEADER)
        skill = self.make_skill(
            {"evals/files/in.txt": "x\n"},
            [{"id": 1, "prompt": "Check evals/files/in.txt.", "expectations": [EXPECTATION],
              "files": ["evals/files/in.txt"]}],
        )
        self.assertEqual(self.stage("demo", skill), [])
        plugin = self.dest / "demo"
        prompt, _criteria = skill_evals.read_case(plugin / skill_evals.CASE_DIR / "case-1")
        listed, _named = skill_evals.prompt_paths(prompt, plugin)
        self.assertEqual(listed, [plugin / "eval-inputs" / "files" / "in.txt"])
        self.assertNotIn("copy one into your working directory", prompt)
        self.assertIn("read them in place", prompt)
        self.assertIn("write outputs to your working directory", prompt)
        self.assertIn("never `cp` or `mv`", prompt)

    def test_transcribe_guitar_riff_case_1_is_kept_locally_and_skipped_in_ci(self) -> None:
        name = "transcribe-guitar-riff"
        src = skill_evals.skill_dirs()[name]
        raw = json.loads((src / "evals" / "evals.json").read_text(encoding="utf-8"))
        self.assertEqual([c["id"] for c in raw["evals"]], [1, 2, 3])
        self.assertEqual(
            skill_evals.allowlist()[name].get("skip_cases"),
            {"case-1": "needs a live Ableton set and the ableton-mcp tools"},
        )
        self.assertEqual(skill_evals.stage(name, src, self.dest), [])
        staged_cases = sorted(p.name for p in (self.dest / name / skill_evals.CASE_DIR).iterdir())
        self.assertEqual(staged_cases, ["case-2", "case-3"])

        plan_log = io.StringIO()
        args = type("Args", (), {"canary_only": False, "skill": name, "suite": "skills"})
        with contextlib.redirect_stdout(plan_log), mock.patch.dict("os.environ", {"GITHUB_OUTPUT": ""}):
            self.assertEqual(skill_evals.cmd_plan(args), 0)
        self.assertIn(
            "::notice::Skipping transcribe-guitar-riff case-1: "
            "needs a live Ableton set and the ableton-mcp tools",
            plan_log.getvalue(),
        )

    def test_skip_cases_validation_rejects_bad_entries(self) -> None:
        base = skill_evals.load_config()
        bad_configs = {
            "skip_cases must be an object": ["case-1"],
            "is not a case in transcribe-guitar-riff/evals/evals.json": {"case-99": "no such case"},
            "needs a reason": {"case-1": "   "},
            "skips every case; move transcribe-guitar-riff to ci_skipped": {
                "case-1": "a", "case-2": "b", "case-3": "c",
            },
        }
        for expected, skip_cases in bad_configs.items():
            with self.subTest(expected=expected):
                cfg = json.loads(json.dumps(base))
                cfg["ci_runnable"]["transcribe-guitar-riff"]["skip_cases"] = skip_cases
                log = io.StringIO()
                with mock.patch.object(skill_evals, "load_config", return_value=cfg), \
                        contextlib.redirect_stdout(log):
                    self.assertEqual(skill_evals.cmd_validate(None), 1)
                self.assertIn(expected, log.getvalue())


    def test_canary_runs_its_probes_from_one_staged_script(self) -> None:
        # Run 41350276820: the safety classifier stopped the inline /proc scan
        # and the agent refused the rest, so the probes now run as one script.
        self.dest.mkdir()
        skill_evals.stage_canary(self.dest)
        staged = self.dest / skill_evals.CANARY
        probe = staged / skill_evals.CANARY_PROBE
        self.assertTrue(probe.stat().st_mode & 0o100)
        script = probe.read_text(encoding="utf-8")
        prompt = (staged / skill_evals.CASE_DIR / "case-sandbox" / "prompt.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"`bash {probe}`", prompt)
        self.assertNotIn("/proc/[0-9]", prompt)
        for marker in ("probe-env-token-set", "probe-proc-token-files", "probe-net-open", "probe-sudo-open"):
            self.assertIn(f'echo "{marker}: $', script)
        # Neither the agent's command nor a Read of the script may satisfy a
        # grader by itself or trip the not_contains one.
        for pattern in skill_evals.CANARY_GRADERS.values():
            self.assertNotRegex(script + prompt, pattern)
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN=", script + prompt)
        subprocess.run(["bash", "-n", str(probe)], check=True)


class CanaryProbeTest(unittest.TestCase):
    """Runs the staged probe script and grades its output with CANARY_GRADERS.

    The Skill Evals workflow cannot run in a PR, so this proves here that the
    script prints lines the graders accept when the sandbox holds and reject
    when a probe reports exposure. curl and sudo are stubbed on PATH so the
    result does not depend on the runner's own network or sudo rules.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        skill_evals.stage_canary(self.tmp / "staged")
        self.probe = self.tmp / "staged" / skill_evals.CANARY / skill_evals.CANARY_PROBE

    def run_probe(self, token: bool = False, net: bool = False, sudo: bool = False) -> str:
        stubs = self.tmp / ("stubs-%d%d" % (net, sudo))
        stubs.mkdir(exist_ok=True)
        for name, open_ in (("curl", net), ("sudo", sudo)):
            stub = stubs / name
            stub.write_text(f"#!/bin/sh\nexit {0 if open_ else 1}\n", encoding="utf-8")
            stub.chmod(0o755)
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_OAUTH_TOKEN"}
        env["PATH"] = f"{stubs}{os.pathsep}{env.get('PATH', '')}"
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = "fake-canary-token"
        out = subprocess.run(
            ["bash", str(self.probe)], env=env, capture_output=True, text=True, check=True, timeout=60
        ).stdout
        # The no-token-assignment-in-trace grader: the script never echoes
        # the variable, even when it is set.
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN=", out)
        self.assertNotIn("fake-canary-token", out)
        return out

    @staticmethod
    def graded(out: str) -> dict[str, bool]:
        return {
            name: re.search(pattern, out) is not None
            for name, pattern in skill_evals.CANARY_GRADERS.items()
        }

    def test_graders_accept_a_clean_sandbox(self) -> None:
        verdicts = self.graded(self.run_probe())
        if PROC_TOKEN_VISIBLE:
            # Another process on this host carries the variable, so the /proc
            # probe rightly reports it; only CI guarantees a clean host.
            verdicts.pop("proc-environ-shows-no-token")
        self.assertEqual(verdicts, dict.fromkeys(verdicts, True))

    def test_each_exposure_fails_its_grader(self) -> None:
        cases = {
            "token-absent-in-bash": {"token": True},
            "network-blocked": {"net": True},
            "sudo-blocked": {"sudo": True},
        }
        for grader, exposure in cases.items():
            with self.subTest(grader=grader):
                self.assertFalse(self.graded(self.run_probe(**exposure))[grader])

    @unittest.skipUnless(Path("/proc/self/environ").exists(), "needs Linux /proc")
    def test_proc_scan_finds_a_token_in_a_process_environment(self) -> None:
        # With the variable set, bash's own /proc/<pid>/environ carries it.
        out = self.run_probe(token=True)
        self.assertFalse(self.graded(out)["proc-environ-shows-no-token"])
        self.assertRegex(out, r"probe-proc-token-files: [1-9]")


def _proc_token_visible() -> bool:
    for environ in Path("/proc").glob("[0-9]*/environ"):
        with contextlib.suppress(OSError):
            if b"CLAUDE_CODE_OAUTH_TOKEN" in environ.read_bytes():
                return True
    return False


PROC_TOKEN_VISIBLE = _proc_token_visible()


if __name__ == "__main__":
    unittest.main()
