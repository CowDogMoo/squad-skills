#!/usr/bin/env python3
"""Tests for the trigger suites and the ablation mode in skill_evals.py.

Trigger suites (<category>/_trigger-evals/<family>.json) check that a request
loads the one skill of an overlapping family it should, and that near misses
load none. Ablation (--ablation with-without) adds a no-skill arm to the skill
suites and reports the delta.

Run: python .github/scripts/test_skill_evals_triggers.py
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import skill_evals  # noqa: E402


def minimal_suite(family: str = "demo") -> dict:
    """A valid suite over two real skills: 15 should-trigger, 5 should-not."""
    members = ["go-review-criteria", "golang-security-guide"]
    queries = []
    for i in range(1, 16):
        queries.append({"id": i, "query": f"Go request {i}", "expect": members[i % 2]})
    for i in range(16, 21):
        queries.append({"id": i, "query": f"Unrelated request {i}", "expect": None})
    return {"family": family, "description": "Two Go skills.", "skills": members, "queries": queries}


class TriggerSuiteTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.skills = skill_evals.skill_dirs()

    def check(self, data: dict, family: str = "demo") -> list[str]:
        path = self.tmp / f"{family}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return skill_evals.check_trigger_suite(path, self.skills)

    def test_every_suite_in_the_repo_is_valid(self) -> None:
        suites = skill_evals.trigger_suites()
        self.assertTrue(suites, "no trigger suites found")
        for family, paths in sorted(suites.items()):
            with self.subTest(family=family):
                self.assertEqual(len(paths), 1, paths)
                self.assertEqual(skill_evals.check_trigger_suite(paths[0], self.skills), [])

    def test_minimal_suite_is_valid(self) -> None:
        self.assertEqual(self.check(minimal_suite()), [])

    def test_problems_are_caught(self) -> None:
        def broken(change) -> dict:
            data = copy.deepcopy(minimal_suite())
            change(data)
            return data

        cases = {
            "does not match file name": lambda d: d.update(family="other"),
            "at least 20 queries": lambda d: d["queries"].pop(),
            "no skill folder is named 'no-such-skill'": lambda d: d["skills"].append("no-such-skill"),
            "golang-security-guide has no query that should load it": lambda d: [
                q.update(expect="go-review-criteria") for q in d["queries"] if q["expect"]
            ],
            "at least 5 should-not-trigger cases": lambda d: d["queries"][-1].update(expect="go-review-criteria"),
            "not in this family's skills": lambda d: d["queries"][0].update(expect="python-review-criteria"),
            "both expects and forbids": lambda d: d["queries"][0].update({"not": [d["queries"][0]["expect"]]}),
            "has 'not' but expects nothing": lambda d: d["queries"][-1].update({"not": ["go-review-criteria"]}),
            "duplicate id": lambda d: d["queries"][1].update(id=1),
            "repeats an earlier query": lambda d: d["queries"][1].update(query="go request 1"),
            "needs 'expect'": lambda d: d["queries"][0].pop("expect"),
            "unknown keys": lambda d: d["queries"][0].update(expected="x"),
        }
        for message, change in cases.items():
            with self.subTest(message=message):
                errors = self.check(broken(change))
                self.assertTrue(any(message in e for e in errors), errors)

    def test_duplicate_family_across_categories_is_caught(self) -> None:
        root = skill_evals.ROOT
        paths = [root / "engineering/_trigger-evals/go.json", root / "testing/_trigger-evals/go.json"]
        with mock.patch.object(skill_evals, "trigger_suites", return_value={"go": paths}):
            log = io.StringIO()
            with contextlib.redirect_stdout(log):
                skill_evals.cmd_validate(None)
        self.assertIn("trigger family 'go' is defined more than once", log.getvalue())


class SkillPatternTest(unittest.TestCase):
    """The tool_used input_match runs as a JavaScript regex; these patterns use
    only syntax Python and JavaScript read the same way."""

    def test_matches_plain_and_plugin_skill_inputs(self) -> None:
        pattern = re.compile(skill_evals.skill_loaded("go-review-criteria"))
        for text in (
            '{"skill":"go-review-criteria"}',
            '{"skill": "triggers-go:go-review-criteria"}',
            "{'skill': 'go-review-criteria'}",
        ):
            self.assertRegex(text, pattern)

    def test_does_not_match_a_sibling(self) -> None:
        pattern = re.compile(skill_evals.skill_loaded("go-review-criteria"))
        for text in (
            '{"skill":"nodejs-review-criteria"}',
            '{"skill":"triggers-go:go-review-criteria-extra"}',
            '{"skill":"go-review"}',
        ):
            self.assertNotRegex(text, pattern)
        either = re.compile(skill_evals.skills_loaded(["go-pipeline", "go-security-audit"]))
        self.assertRegex('{"skill":"p:go-security-audit"}', either)
        self.assertNotRegex('{"skill":"rust-pipeline"}', either)


class StageTriggersTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dest = Path(tmp.name) / "staged"
        family, paths = sorted(skill_evals.trigger_suites().items())[0]
        self.family, self.suite = family, paths[0]
        self.data = json.loads(self.suite.read_text(encoding="utf-8"))
        self.assertEqual(skill_evals.stage_triggers(family, self.suite, self.dest), [])
        self.plugin = self.dest / f"{skill_evals.TRIGGER_PREFIX}{family}"

    def graders(self, case: str) -> dict[str, str]:
        gdir = self.plugin / skill_evals.CASE_DIR / case / "graders"
        return {g.stem: g.read_text(encoding="utf-8") for g in sorted(gdir.glob("*.md"))}

    def test_plugin_holds_every_skill_and_a_bare_manifest(self) -> None:
        manifest = json.loads((self.plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest, {"name": self.plugin.name})
        staged = {p.parent.name for p in (self.plugin / "skills").glob("*/SKILL.md")}
        self.assertEqual(staged, set(skill_evals.skill_dirs()))
        self.assertFalse(list((self.plugin / "skills").glob("*/evals")))

    def test_one_case_per_query(self) -> None:
        self.assertEqual(skill_evals.count_cases(self.plugin), len(self.data["queries"]))
        for q in self.data["queries"]:
            case = f"case-{q['id']:02d}"
            prompt = (self.plugin / skill_evals.CASE_DIR / case / "prompt.md").read_text(encoding="utf-8")
            self.assertIn('allowed_tools: ["Skill"]', prompt)
            self.assertIn(skill_evals.TRIGGER_PREAMBLE + q["query"], prompt)
            graders = self.graders(case)
            for body in graders.values():
                self.assertIn("type: tool_used\ntool: Skill\n", body)
            if q["expect"] is None:
                self.assertEqual(list(graders), ["loads-no-family-skill"])
                self.assertIn("max: 0", graders["loads-no-family-skill"])
            else:
                self.assertIn("min: 1", graders[f"loads-{q['expect']}"])
                for name in q.get("not", []):
                    self.assertIn("max: 0", graders[f"does-not-load-{name}"])


class PlanAndCommandTest(unittest.TestCase):
    def plan(self, **kwargs) -> tuple[int, list[str]]:
        args = type("Args", (), {"canary_only": False, "skill": None, "suite": "skills", **kwargs})
        log = io.StringIO()
        with contextlib.redirect_stdout(log), mock.patch.dict("os.environ", {"GITHUB_OUTPUT": ""}):
            code = skill_evals.cmd_plan(args)
        line = [x for x in log.getvalue().splitlines() if x.startswith("skills=")]
        return code, json.loads(line[0].split("=", 1)[1]) if line else []

    def test_suites(self) -> None:
        families = sorted(skill_evals.trigger_suites())
        _code, skills = self.plan(suite="skills")
        self.assertTrue(skills)
        self.assertFalse(any(skill_evals.is_trigger(n) for n in skills))
        _code, triggers = self.plan(suite="triggers")
        self.assertEqual(triggers, [skill_evals.TRIGGER_PREFIX + f for f in families])
        _code, both = self.plan(suite="all")
        self.assertEqual(both, skills + triggers)
        code, one = self.plan(suite="triggers", skill=families[0])
        self.assertEqual((code, one), (0, [skill_evals.TRIGGER_PREFIX + families[0]]))
        code, _none = self.plan(suite="triggers", skill="no-such-family")
        self.assertEqual(code, 1)

    def test_skill_with_suite_all_is_refused(self) -> None:
        skill = next(iter(skill_evals.allowlist()))
        code, planned = self.plan(suite="all", skill=skill)
        self.assertEqual((code, planned), (1, []))

    def test_knowledge_halves_run_only_when_asked_for(self) -> None:
        runnable, skip = skill_evals.allowlist(), skill_evals.skipped()
        engineering = sorted(
            n for n, d in skill_evals.skill_dirs().items()
            if d.parent.name == "engineering" and (d / "evals" / "evals.json").is_file() and n not in skip
        )
        halves = {}
        for suite in ("knowledge-1", "knowledge-2"):
            _code, halves[suite] = self.plan(suite=suite)
            self.assertTrue(halves[suite], suite)
        self.assertFalse(set(halves["knowledge-1"]) & set(halves["knowledge-2"]))
        knowledge = sorted(halves["knowledge-1"] + halves["knowledge-2"])
        self.assertEqual(knowledge, engineering)
        for orchestrator in ("go-pipeline", "go-security-audit", "rust-pipeline"):
            self.assertIn(orchestrator, skip)
        for suite in ("skills", "all"):
            _code, planned = self.plan(suite=suite)
            self.assertFalse(set(planned) & set(knowledge), suite)
        first = halves["knowledge-1"][0]
        code, one = self.plan(suite="knowledge-1", skill=first)
        self.assertEqual((code, one), (0, [first]))
        for suite in ("skills", "knowledge-2"):
            _code, none = self.plan(suite=suite, skill=first)
            self.assertEqual(none, [], suite)

    def test_ablation_reaches_skill_suites_only(self) -> None:
        config = skill_evals.load_config()
        out = Path("/out")
        skill = next(iter(config["ci_runnable"]))
        cmd = skill_evals.eval_command("claude", out, out, skill, config, 3, "with-without")
        self.assertEqual(cmd[cmd.index("--ablation") + 1], "with-without")
        for name in (skill_evals.CANARY, skill_evals.TRIGGER_PREFIX + "go"):
            cmd = skill_evals.eval_command("claude", out, out, name, config, 3, "with-without")
            self.assertEqual(cmd[cmd.index("--ablation") + 1], "none", name)
        cmd = skill_evals.eval_command("claude", out, out, skill_evals.TRIGGER_PREFIX + "go", config, 3)
        self.assertNotIn("--allow-tools", cmd)
        self.assertEqual(cmd[cmd.index("--runs") + 1], "3")


class JudgeTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def result(self, cases: list[tuple[str, list[float], list[float]]]) -> Path:
        data = {"partial": False, "cases": []}
        for name, with_scores, without_scores in cases:
            arm = lambda scores: [{"score": s, "error": None, "graders": []} for s in scores]  # noqa: E731
            arms = {"with": arm(with_scores)}
            if without_scores:
                arms["without"] = arm(without_scores)
            data["cases"].append({"name": name, "graders": [], "arms": arms})
        path = self.tmp / "result.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def judge(self, name: str, path: Path, threshold: float) -> tuple[int, str]:
        with contextlib.redirect_stdout(io.StringIO()):
            return skill_evals.judge(name, path, threshold)

    def test_ablation_table_reports_the_delta(self) -> None:
        path = self.result([("case-1", [1.0, 0.8], [0.4, 0.6]), ("case-2", [0.5], [0.5])])
        code, text = self.judge("demo", path, 0.5)
        self.assertEqual(code, 0)
        self.assertIn("| case-1 | 0.90 | 0.50 | +0.40 |", text)
        self.assertIn("| case-2 | 0.50 | 0.50 | +0.00 |", text)
        self.assertIn("| **mean** | 0.70 | 0.50 | +0.20 |", text)

    def test_no_ablation_table_without_a_baseline(self) -> None:
        _code, text = self.judge("demo", self.result([("case-1", [1.0], [])]), 0.5)
        self.assertNotIn("Without skill", text)

    def test_trigger_suite_reports_routing(self) -> None:
        path = self.result([("case-01", [1.0], []), ("case-02", [0.0], []), ("case-03", [1.0], [])])
        code, text = self.judge(skill_evals.TRIGGER_PREFIX + "demo", path, 0.6)
        self.assertEqual(code, 1)
        self.assertIn("Routing: 2 of 3 queries met the threshold.", text)

    def test_partial_run_counts_only_real_cases(self) -> None:
        path = self.result([(f"case-{n:02d}", [1.0], []) for n in range(1, 13)])
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(partial=True, partialReason="max cost reached")
        path.write_text(json.dumps(data), encoding="utf-8")
        code, text = self.judge(skill_evals.TRIGGER_PREFIX + "demo", path, 0.6)
        self.assertEqual(code, 1)
        self.assertIn("Routing: 12 of 12 queries met the threshold.", text)
        self.assertIn("the run stopped before every case ran", text)
        self.assertNotIn("did not run", text)

    def test_cmd_judge_uses_the_trigger_threshold(self) -> None:
        bundle, out = self.tmp / "bundle", self.tmp / "out"
        (bundle / "harness").mkdir(parents=True)
        config = skill_evals.load_config()
        config["trigger_threshold"] = 0.3
        (bundle / "harness" / skill_evals.CONFIG.name).write_text(json.dumps(config), encoding="utf-8")
        name = skill_evals.TRIGGER_PREFIX + "demo"
        (bundle / "harness" / "skills.json").write_text(json.dumps([name]), encoding="utf-8")
        out.mkdir()
        canary = HERE / "testdata" / "skill-evals-canary-run-41233408616.json"
        (out / f"{skill_evals.CANARY}.json").write_text(canary.read_text(encoding="utf-8"), encoding="utf-8")
        (out / f"{name}.json").write_text(self.result([("case-01", [0.5], [])]).read_text(), encoding="utf-8")
        args = type("Args", (), {"bundle": str(bundle), "out": str(out), "threshold": None})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(skill_evals.cmd_judge(args), 0)


if __name__ == "__main__":
    unittest.main()
