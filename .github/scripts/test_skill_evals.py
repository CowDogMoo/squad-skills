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


if __name__ == "__main__":
    unittest.main()
