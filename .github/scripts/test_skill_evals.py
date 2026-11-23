#!/usr/bin/env python3
"""Tests for the judge in skill_evals.py.

testdata/skill-evals-canary-run-41233408616.json is the sandbox self-test
result from Skill Evals run 41233408616 (Claude Code 2.1.296), trimmed to the
fields the judge reads. Every probe in that run printed 0 and every regex
grader passed, yet the Judge step failed with "could not be graded" for all
five graders: claude plugin eval records a grader's type only in the case's
grader definitions, not in each run's grader results, so the judge took every
regex grader for an LLM grader with no judge votes.

Run: python .github/scripts/test_skill_evals.py
"""

from __future__ import annotations

import contextlib
import copy
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

RUN_41233408616 = HERE / "testdata" / "skill-evals-canary-run-41233408616.json"


def load_run() -> dict:
    return json.loads(RUN_41233408616.read_text(encoding="utf-8"))


class JudgeTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def judge(self, data: dict, threshold: float = 1.0) -> tuple[int, str, str]:
        path = self.tmp / "result.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            code, text = skill_evals.judge(skill_evals.CANARY, path, threshold)
        return code, text, log.getvalue()

    def test_run_41233408616_canary_passes(self) -> None:
        code, text, log = self.judge(load_run())
        self.assertNotIn("could not be graded", log)
        self.assertIn("| case-sandbox | 1.00 | 1.00 | pass |", text)
        self.assertEqual(code, 0)

    def test_run_41233408616_judge_step_passes(self) -> None:
        bundle, out = self.tmp / "bundle", self.tmp / "out"
        (bundle / "harness").mkdir(parents=True)
        (bundle / "harness" / skill_evals.CONFIG.name).write_text(
            skill_evals.CONFIG.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (bundle / "harness" / "skills.json").write_text("[]", encoding="utf-8")
        out.mkdir()
        (out / f"{skill_evals.CANARY}.json").write_text(
            RUN_41233408616.read_text(encoding="utf-8"), encoding="utf-8"
        )
        args = type("Args", (), {"bundle": str(bundle), "out": str(out), "threshold": None})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skill_evals.cmd_judge(args), 0)

    def test_failed_probe_still_fails(self) -> None:
        data = load_run()
        run = data["cases"][0]["arms"]["with"][0]
        for grader in run["graders"]:
            if grader["name"] == "network-blocked":
                grader["passed"] = False
                grader["explanation"] = "pattern not found in trace"
        run["score"] = 0.8
        code, text, _log = self.judge(data)
        self.assertEqual(code, 1)
        self.assertIn("below threshold | network-blocked |", text)

    def test_llm_grader_without_votes_is_a_harness_failure(self) -> None:
        data = load_run()
        case = data["cases"][0]
        case["graders"].append({"name": "judged", "type": "llm", "weight": 1, "config": {}})
        case["arms"]["with"][0]["graders"].append(
            {"name": "judged", "passed": False, "weight": 1, "explanation": "judge call failed",
             "withOnly": False, "scored": True}
        )
        code, text, log = self.judge(data)
        self.assertEqual(code, 1)
        self.assertIn("did not run", text)
        self.assertIn("judged could not be graded: judge call failed", log)
        self.assertNotIn("network-blocked could not be graded", log)

    def test_grader_of_unknown_type_needs_votes(self) -> None:
        data = load_run()
        undefined = copy.deepcopy(data["cases"][0]["arms"]["with"][0]["graders"][0])
        undefined["name"] = "undefined-grader"
        data["cases"][0]["arms"]["with"][0]["graders"].append(undefined)
        code, _text, log = self.judge(data)
        self.assertEqual(code, 1)
        self.assertIn("undefined-grader could not be graded", log)

    def test_skipped_case_is_reported_as_skipped_and_never_counted_as_passed(self) -> None:
        skip = {"case-1": "needs a live Ableton set and the ableton-mcp tools"}
        data = {
            "partial": False,
            "cases": [
                {
                    "name": "case-2",
                    "graders": [],
                    "arms": {
                        "with": [{"score": 1.0, "error": None, "graders": []}],
                        "without": [{"score": 0.4, "error": None, "graders": []}],
                    },
                },
            ],
        }
        path = self.tmp / "skill.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            code, text = skill_evals.judge("transcribe-guitar-riff", path, 0.85, skip_cases=skip)
        self.assertEqual(code, 0)
        self.assertIn(
            "| case-1 | - | - | skipped | needs a live Ableton set and the ableton-mcp tools |",
            text,
        )
        self.assertIn("| case-2 | 1.00 | 1.00 | pass |  |", text)
        self.assertIn("| **mean** | 1.00 | 0.40 | +0.60 |", text)
        self.assertIn("All 1 runnable case(s) met the threshold (1 skipped).", text)

        data["cases"][0]["arms"]["with"][0]["score"] = 0.0
        path.write_text(json.dumps(data), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            code, text = skill_evals.judge("transcribe-guitar-riff", path, 0.85, skip_cases=skip)
        self.assertEqual(code, 1)
        self.assertIn("**Failed:** 1 case(s) scored below the threshold.", text)

    def test_cmd_judge_forwards_per_case_skips_from_bundled_config(self) -> None:
        bundle, out = self.tmp / "bundle", self.tmp / "out"
        (bundle / "harness").mkdir(parents=True)
        (bundle / "harness" / skill_evals.CONFIG.name).write_text(
            skill_evals.CONFIG.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (bundle / "harness" / "skills.json").write_text(
            json.dumps(["transcribe-guitar-riff"]), encoding="utf-8"
        )
        out.mkdir()
        (out / f"{skill_evals.CANARY}.json").write_text(
            RUN_41233408616.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (out / "transcribe-guitar-riff.json").write_text(
            json.dumps({
                "partial": False,
                "cases": [
                    {"name": "case-2", "graders": [], "arms": {"with": [{"score": 1.0, "error": None, "graders": []}]}},
                    {"name": "case-3", "graders": [], "arms": {"with": [{"score": 1.0, "error": None, "graders": []}]}},
                ],
            }),
            encoding="utf-8",
        )
        step_summary = self.tmp / "summary.md"
        args = type("Args", (), {"bundle": str(bundle), "out": str(out), "threshold": None})
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.dict(
            "os.environ", {"GITHUB_STEP_SUMMARY": str(step_summary)}
        ):
            self.assertEqual(skill_evals.cmd_judge(args), 0)
        written = step_summary.read_text(encoding="utf-8")
        self.assertIn(
            "| case-1 | - | - | skipped | needs a live Ableton set and the ableton-mcp tools |",
            written,
        )
        self.assertIn("All 2 runnable case(s) met the threshold (1 skipped).", written)


class ExpectationFocusTest(unittest.TestCase):
    """An expectation is a string or {"text", "focus"}; focus "trace" shows the
    judge the tool calls and their output, not only the final reply."""

    TRACED = {"text": "No pitch is asserted that the salience output does not support", "focus": "trace"}

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def skill(self, expectations: list, files: dict[str, str] | None = None) -> Path:
        skill = self.tmp / "src" / "demo"
        (skill / "evals").mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
        for rel, text in (files or {}).items():
            (skill / rel).parent.mkdir(parents=True, exist_ok=True)
            (skill / rel).write_text(text, encoding="utf-8")
        case = {"id": 1, "prompt": "Do it.", "expectations": expectations}
        if files:
            case["files"] = list(files)
        (skill / "evals" / "evals.json").write_text(
            json.dumps({"skill_name": "demo", "evals": [case]}), encoding="utf-8"
        )
        return skill

    def stage(self, skill: Path) -> Path:
        dest = self.tmp / "staged"
        with mock.patch.object(skill_evals, "allowlist", return_value={"demo": {}}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skill_evals.stage("demo", skill, dest), [])
        return dest / "demo" / skill_evals.CASE_DIR / "case-1"

    def test_string_expectations_are_unchanged(self) -> None:
        case = self.stage(self.skill(["plain"]))
        self.assertEqual(
            (case / "graders" / "expectation-1.md").read_text(encoding="utf-8"),
            "---\ntype: llm\nweight: 1\n---\n\nplain\n",
        )

    def test_trace_focus_is_written_to_the_grader_frontmatter(self) -> None:
        case = self.stage(self.skill(["plain", self.TRACED]))
        self.assertNotIn("focus", (case / "graders" / "expectation-1.md").read_text(encoding="utf-8"))
        self.assertEqual(
            (case / "graders" / "expectation-2.md").read_text(encoding="utf-8"),
            f"---\ntype: llm\nweight: 1\nfocus: trace\n---\n\n{self.TRACED['text']}\n",
        )
        _prompt, criteria = skill_evals.read_case(case)
        self.assertEqual(criteria, ["plain", self.TRACED["text"]])

    def test_trace_focus_is_written_to_case_yaml_for_cases_with_inputs(self) -> None:
        case = self.stage(self.skill(["plain", self.TRACED], {"evals/files/in.txt": "x"}))
        graders = json.loads((case / "case.yaml").read_text(encoding="utf-8"))["graders"]
        self.assertNotIn("focus", graders[0])
        self.assertEqual(graders[1]["focus"], "trace")
        self.assertEqual(graders[1]["criteria"], self.TRACED["text"])

    def test_validation(self) -> None:
        def errors(expectations: list) -> list[str]:
            return skill_evals.check_evals(self.skill(expectations))

        self.assertEqual(errors(["plain", self.TRACED, {"text": "last", "focus": "last_message"}]), [])
        self.assertEqual(errors([{"text": "no focus"}]), [])
        self.assertTrue(any("has an empty expectation" in e for e in errors([" "])))
        self.assertTrue(any("non-empty text" in e for e in errors([{"focus": "trace"}])))
        self.assertTrue(any("non-empty text" in e for e in errors([{"text": "", "focus": "trace"}])))
        self.assertTrue(any("focus must be one of" in e for e in errors([{"text": "x", "focus": "files"}])))
        self.assertTrue(any("only text and focus" in e for e in errors([{"text": "x", "weight": 2}])))
        self.assertTrue(any("has an empty expectation" in e for e in errors([3])))

    def test_transcribe_guitar_riff_case_2_judges_the_salience_criterion_on_the_trace(self) -> None:
        src = skill_evals.skill_dirs()["transcribe-guitar-riff"]
        case = next(
            c for c in json.loads((src / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]
            if c["id"] == 2
        )
        self.assertEqual(skill_evals.check_evals(src), [])
        traced = [e for e in case["expectations"] if skill_evals.expectation_focus(e) == "trace"]
        self.assertEqual(
            [skill_evals.expectation_text(e) for e in traced],
            ["No pitch is asserted that the salience output does not support"],
        )
        self.assertEqual(len(case["expectations"]), 4)


if __name__ == "__main__":
    unittest.main()
