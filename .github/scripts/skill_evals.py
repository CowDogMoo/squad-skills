#!/usr/bin/env python3
"""Validate, plan, stage, run, leak-check, and judge the skills' evals.

Adapted from l50/personal-skills .github/scripts/skill_evals.py. This is a
copy, not a shared dependency: neither repository runs the other's code.

evals/evals.json in each skill folder is the single source of truth for its
eval cases. The skill-evals workflow calls this script in two jobs:

  prepare (no secret)
    plan      pick the allowlisted skills to run and log why the rest are skipped
    bundle    stage each skill as data into a plugin this script builds itself,
              plus the sandbox self-test and the managed settings
  eval (token, behind the skill-evals environment)
    run       run `claude plugin eval` on each staged skill; model output goes
              to files, never to the job log
    leak-check  search every result file for the token before anything is
              printed or uploaded; on a hit, delete the results and fail
    judge     score the results and write the step summary

  validate  check every evals.json, the allowlist, the workflow triggers, and
            that every case can read its staged inputs but not its
            expectations (no secrets needed; runs in Validate Skills on every
            pull request)

The allowlist of skills that can run in CI lives in .github/skill-evals.json.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "skill-evals.json"
POLICY = ROOT / ".github" / "skill-evals-managed-settings.json"
WORKFLOW = ROOT / ".github" / "workflows" / "skill-evals.yaml"
PLUGIN_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
CASE_DIR = "ci-evals"
EVALS_DIR = "evals"
# Case input files are staged here, outside every directory claude plugin eval
# fences off from the agent (see FENCED_DIRS).
INPUTS_DIR = "eval-inputs"
CANARY = "skill-evals-canary"
BASE_TOOLS = ["Read", "Glob", "Grep", "Skill"]
GRANTABLE_TOOLS = {"Bash", "Edit", "Write"}
MAX_TURNS = 20
TIMEOUT_SECONDS = 600
UNLISTED_REASON = (
    "not classified in .github/skill-evals.json; add it to ci_runnable once "
    "its evals need no live services"
)
# Plugin-owned paths that load code or configuration outside the agent's
# sandbox. A skill is copied as data, so none of these are staged.
PLUGIN_OWNED = {
    ".claude",
    ".claude-plugin",
    ".codex-plugin",
    ".lsp.json",
    ".mcp.json",
    "agents",
    "bin",
    "commands",
    "hooks",
    "monitors",
    "output-styles",
    "settings.json",
    CASE_DIR,
}
IGNORED = {"__pycache__", "results", ".DS_Store"}
# What claude plugin eval (2.1.296) denies the agent inside the plugin under
# test, whatever letter case: every directory named like an eval directory
# (the --eval-dir, and "evals" whatever the flag says), version-control
# metadata, run results, and any directory holding run results directly or one
# level down. A case input staged under any of them cannot be read.
FENCED_DIRS = {
    EVALS_DIR, CASE_DIR, ".git", ".hg", ".svn", ".jj", ".sl", ".bzr", "_darcs", "cvs",
}
FENCED_FILES = {"aggregate-result.json", "report.html"}
# An `evals/...` path in a prompt, which staging moves to INPUTS_DIR.
EVALS_REF = re.compile(r"(?<![\w/.-])(?:\./)?" + EVALS_DIR + "/")
INPUT_LIST_HEADER = "Input files (read-only; copy one into your working directory before changing it):"
# Only these reach `claude plugin eval`; the step's other variables stay out.
CHILD_ENV = [
    "CLAUDE_CODE_OAUTH_TOKEN",
    "HOME",
    "LANG",
    "LC_ALL",
    "USER",
]
TRIGGERS = {"workflow_dispatch", "schedule"}


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def allowlist() -> dict[str, dict]:
    return load_config().get("ci_runnable", {})


def skipped() -> dict[str, str]:
    return load_config().get("ci_skipped", {})


def skill_dirs() -> dict[str, Path]:
    """Map each skill name to its folder, from the plugin's category list."""
    plugin = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    found = {}
    for category in plugin["skills"]:
        base = ROOT / category.removeprefix("./")
        for skill_md in sorted(base.glob("*/SKILL.md")):
            if not skill_md.parent.name.startswith((".", "_")):
                found[skill_md.parent.name] = skill_md.parent
    return found


def output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")
    print(f"{name}={value}")


def summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


def nonempty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def check_evals(skill: Path) -> list[str]:
    """Return the problems with skill/evals/evals.json (empty when valid)."""
    path = skill / "evals" / "evals.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return ["top level must be an object"]

    errors = []
    if data.get("skill_name") != skill.name:
        errors.append(
            f"skill_name {data.get('skill_name')!r} does not match folder {skill.name!r}"
        )
    cases = data.get("evals")
    if not isinstance(cases, list) or not cases:
        return errors + ["'evals' must be a non-empty list"]

    seen = set()
    for i, case in enumerate(cases):
        where = f"evals[{i}]"
        if not isinstance(case, dict):
            errors.append(f"{where} must be an object")
            continue
        cid = case.get("id")
        if cid is None:
            errors.append(f"{where} has no id")
        elif cid in seen:
            errors.append(f"{where} duplicate id {cid!r}")
        else:
            seen.add(cid)
        if not nonempty_str(case.get("prompt")):
            errors.append(f"{where} prompt is missing or empty")
        expectations = case.get("expectations")
        if not isinstance(expectations, list) or not expectations:
            errors.append(f"{where} expectations must be a non-empty list")
        elif not all(nonempty_str(e) for e in expectations):
            errors.append(f"{where} has an empty expectation")
        files = case.get("files", [])
        if not isinstance(files, list):
            errors.append(f"{where} files must be a list")
            continue
        for f in files:
            if not nonempty_str(f) or not (skill / f).exists():
                errors.append(f"{where} file {f!r} does not exist under {skill.name}/")
            elif Path(f).is_absolute() or ".." in Path(f).parts:
                errors.append(f"{where} file {f!r} must be a relative path inside {skill.name}/")
            elif (skill / f).is_symlink() or not (skill / f).is_file():
                errors.append(f"{where} file {f!r} must be a regular file, not a directory or link")
            elif Path(f) == Path(EVALS_DIR, "evals.json"):
                errors.append(f"{where} file {f!r} would show the agent its own expectations")
    return errors


def workflow_triggers() -> set[str]:
    import yaml

    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML reads the bare `on:` key as boolean True.
    triggers = data.get("on", data.get(True, {}))
    return set(triggers if isinstance(triggers, (dict, list)) else [triggers])


def cmd_validate(_args) -> int:
    failed = False

    def error(where: str, message: str) -> None:
        nonlocal failed
        failed = True
        print(f"::error file={where}::{message}")

    config = load_config()
    where = ".github/skill-evals.json"
    for key in ("model", "judge_model"):
        if not nonempty_str(config.get(key)):
            error(where, f"{key} must be a model name")
    default = config.get("threshold")
    if not isinstance(default, (int, float)) or not 0 <= default <= 1:
        error(where, "threshold must be a number from 0 to 1")
    cost = config.get("max_cost_usd")
    if not isinstance(cost, (int, float)) or cost <= 0:
        error(where, "max_cost_usd must be a positive number")

    skills = skill_dirs()
    runnable, skip = allowlist(), skipped()
    for name in sorted(set(runnable) & set(skip)):
        error(where, f"{name} is in both ci_runnable and ci_skipped")
    for name in sorted(set(runnable) | set(skip)):
        if name not in skills:
            error(where, f"{name} is listed but no skill folder has that name")
    for name, reason in skip.items():
        if not nonempty_str(reason):
            error(where, f"ci_skipped.{name} needs a reason")
    for name, opts in runnable.items():
        if not isinstance(opts, dict):
            error(where, f"ci_runnable.{name} must be an object")
            continue
        if name in skills and not (skills[name] / "evals" / "evals.json").is_file():
            error(where, f"{name} is allowlisted but has no evals/evals.json")
        if "judge_model" in opts and not nonempty_str(opts["judge_model"]):
            error(where, f"ci_runnable.{name}.judge_model must be a model name")
        limit = opts.get("threshold", 0)
        if not isinstance(limit, (int, float)) or not 0 <= limit <= 1:
            error(where, f"ci_runnable.{name}.threshold must be a number from 0 to 1")
        tools = opts.get("allow_tools", [])
        if not isinstance(tools, list) or not set(tools) <= GRANTABLE_TOOLS:
            error(where, f"ci_runnable.{name}.allow_tools must only list {sorted(GRANTABLE_TOOLS)}")
        packages = opts.get("python_packages", [])
        if not isinstance(packages, list) or not all(nonempty_str(p) for p in packages):
            error(where, f"ci_runnable.{name}.python_packages must be a list of package names")
        reqs = opts.get("python_requirements")
        if reqs is not None and (
            not nonempty_str(reqs) or name not in skills or not (skills[name] / reqs).is_file()
        ):
            error(where, f"ci_runnable.{name}.python_requirements must name a file in the skill")
        for key in ("max_turns", "timeout_seconds"):
            if key in opts and (not isinstance(opts[key], int) or opts[key] <= 0):
                error(where, f"ci_runnable.{name}.{key} must be a positive integer")

    for name, skill in sorted(skills.items()):
        if not (skill / "evals" / "evals.json").is_file():
            continue
        errors = check_evals(skill)
        rel = skill.relative_to(ROOT)
        for err in errors:
            error(f"{rel}/evals/evals.json", err)
        if not errors:
            print(f"  ✓ {rel}/evals/evals.json")

    # Stage every runnable skill the way the eval job gets it and check that
    # each case can read its inputs there, but not its expectations. The
    # evals themselves never run on a pull request, so this is the only
    # place a layout claude plugin eval would fence off can be caught first.
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "staged"
        for name in sorted(set(runnable) & set(skills)):
            evals = skills[name] / EVALS_DIR / "evals.json"
            if not evals.is_file() or check_evals(skills[name]):
                continue
            with contextlib.redirect_stdout(io.StringIO()):
                problems = stage(name, skills[name], staged) or check_staged(staged / name)
            rel = skills[name].relative_to(ROOT)
            for problem in problems:
                error(f"{rel}/evals/evals.json", f"staged for CI: {problem}")
            if not problems:
                print(f"  ✓ {name}: every case can read its staged inputs")

    try:
        json.loads(POLICY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        error(".github/skill-evals-managed-settings.json", f"unreadable: {exc}")

    # Evals run only on main, by hand or on a schedule, never on pull request
    # content: the workflow must not grow any other trigger.
    extra = workflow_triggers() - TRIGGERS
    if extra:
        error(
            ".github/workflows/skill-evals.yaml",
            f"skill-evals may only run on {sorted(TRIGGERS)}; remove {sorted(extra)}",
        )
    else:
        print("  ✓ skill-evals.yaml runs only on workflow_dispatch or schedule")

    if failed:
        print("::error::Eval suite validation failed")
        return 1
    print("✓ All eval suites are valid")
    return 0


def cmd_plan(args) -> int:
    skills = skill_dirs()
    runnable, skip = allowlist(), skipped()
    if args.canary_only:
        print("Canary only: no skill evals were requested")
        output("skills", "[]")
        return 0
    if args.skill:
        if args.skill not in skills:
            print(f"::error::No skill named {args.skill!r} in this repository")
            return 1
        requested = [args.skill]
    else:
        requested = sorted(skills)

    selected = []
    for name in requested:
        if name in runnable:
            selected.append(name)
        else:
            print(f"::notice::Skipping {name}: {skip.get(name) or UNLISTED_REASON}")
    output("skills", json.dumps(selected))
    return 0


def copy_skill(src: Path, dest: Path) -> list[str]:
    """Copy src to dest as plain files; return any problems instead of copying links."""
    problems = []
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        here = Path(dirpath)
        rel = here.relative_to(src)
        keep = []
        for d in sorted(dirnames):
            # evals/ holds evals.json, the expectations; stage() copies only
            # the case input files out of it, into INPUTS_DIR.
            if rel == Path(".") and d == EVALS_DIR:
                continue
            if rel == Path(".") and d == INPUTS_DIR:
                problems.append(f"{d}/ is reserved for staged eval inputs")
                continue
            if d in IGNORED or (rel == Path(".") and d in PLUGIN_OWNED):
                if d not in IGNORED:
                    print(f"::notice::{src.name}: not staging plugin-owned {d}/")
                continue
            if (here / d).is_symlink():
                problems.append(f"{rel / d} is a symlink")
                continue
            keep.append(d)
        dirnames[:] = keep
        for f in sorted(filenames):
            path = here / f
            if f in IGNORED:
                continue
            if rel == Path(".") and f in PLUGIN_OWNED:
                print(f"::notice::{src.name}: not staging plugin-owned {f}")
                continue
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                problems.append(f"{rel / f} is a symlink")
            elif not stat.S_ISREG(mode):
                problems.append(f"{rel / f} is not a regular file")
            else:
                target = dest / rel / f
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
                if mode & stat.S_IXUSR:
                    target.chmod(0o755)
    return problems


def write_case(
    case_dir: Path,
    prompt: str,
    tools: list[str],
    graders: dict[str, str],
    max_turns: int,
    timeout: int,
    runs: int | None = None,
) -> None:
    (case_dir / "graders").mkdir(parents=True)
    front = [
        f"max_turns: {max_turns}",
        f"timeout_seconds: {timeout}",
        f"allowed_tools: {json.dumps(tools)}",
    ]
    if runs:
        front.append(f"runs: {runs}")
    (case_dir / "prompt.md").write_text(
        "---\n" + "\n".join(front) + f"\n---\n\n{prompt}\n", encoding="utf-8"
    )
    for name, body in graders.items():
        (case_dir / "graders" / f"{name}.md").write_text(body, encoding="utf-8")


def input_path(f: str) -> Path:
    """Where a case input file is staged, relative to the staged skill.

    claude plugin eval denies the agent every directory named evals/, so
    inputs kept there move to INPUTS_DIR with the rest of their path; any
    other input is already staged in place.
    """
    parts = Path(f).parts
    if parts and parts[0] == EVALS_DIR:
        return Path(INPUTS_DIR, *parts[1:])
    return Path(f)


def stage_inputs(src: Path, staged: Path, cases: list[dict]) -> list[str]:
    """Copy each case input file kept under evals/ to its staged path."""
    problems = []
    for f in sorted({f for case in cases for f in case.get("files", [])}):
        rel = input_path(f)
        if rel == Path(f):
            continue
        path = src / f
        if path.is_symlink() or not path.is_file():
            problems.append(f"input {f} is not a regular file")
            continue
        target = staged / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if path.stat().st_mode & stat.S_IXUSR:
            target.chmod(0o755)
    return problems


def stage(name: str, src: Path, dest: Path) -> list[str]:
    """Copy one skill into dest/name and write plugin-eval cases from evals.json."""
    staged = dest / name
    problems = copy_skill(src, staged)
    if problems:
        return problems
    opts = allowlist()[name]
    data = json.loads((src / EVALS_DIR / "evals.json").read_text(encoding="utf-8"))
    problems = stage_inputs(src, staged, data["evals"])
    if problems:
        return problems
    tools = BASE_TOOLS + [t for t in opts.get("allow_tools", []) if t not in BASE_TOOLS]
    for case in data["evals"]:
        prompt = EVALS_REF.sub(f"{staged / INPUTS_DIR}/", case["prompt"])
        if case.get("files"):
            listed = "\n".join(f"- {staged / input_path(f)}" for f in case["files"])
            prompt += f"\n\n{INPUT_LIST_HEADER}\n{listed}"
        graders = {
            f"expectation-{n}": f"---\ntype: llm\nweight: 1\n---\n\n{expectation}\n"
            for n, expectation in enumerate(case["expectations"], 1)
        }
        write_case(
            staged / CASE_DIR / f"case-{case['id']}",
            prompt,
            tools,
            graders,
            opts.get("max_turns", MAX_TURNS),
            opts.get("timeout_seconds", TIMEOUT_SECONDS),
        )
    return []


def holds_results(d: Path) -> bool:
    """True when claude plugin eval would take d for a results directory."""
    try:
        children = list(d.iterdir())
    except OSError:
        return False
    if any(c.name.lower() in FENCED_FILES for c in children):
        return True
    return any(
        c.is_dir() and not c.is_symlink() and any((c / f).exists() for f in FENCED_FILES)
        for c in children
    )


def fenced_reason(plugin: Path, path: Path) -> str | None:
    """Why claude plugin eval would deny the agent path, or None if it would not."""
    try:
        rel = path.relative_to(plugin)
    except ValueError:
        return "is outside the staged skill"
    if ".." in rel.parts:
        return "is outside the staged skill"
    for part in rel.parts:
        if part.lower() in FENCED_DIRS:
            return f"is inside {part}/, which claude plugin eval denies the agent"
    if rel.name.lower() in FENCED_FILES:
        return f"is named {rel.name}, which claude plugin eval denies the agent"
    for n in range(1, len(rel.parts) + 1):
        d = plugin.joinpath(*rel.parts[:n])
        if d.is_dir() and holds_results(d):
            return (
                f"is inside {d.relative_to(plugin)}/, which holds run results, so "
                "claude plugin eval denies the agent"
            )
    return None


def prompt_paths(prompt: str, plugin: Path) -> tuple[list[Path], list[Path]]:
    """Return (listed inputs, every path) under plugin that a staged prompt names."""
    root = re.escape(str(plugin))
    named = [
        Path(m.group(0).rstrip(".:"))
        for m in re.finditer(root + r"(?![\w.-])(?:/[^\s`'\"<>()\[\]{},;]*)?", prompt)
    ]
    listed, in_list = [], False
    for line in prompt.splitlines():
        if line == INPUT_LIST_HEADER:
            in_list = True
        elif in_list and line.startswith("- "):
            listed.append(Path(line[2:]))
        elif in_list and line.strip():
            in_list = False
    return listed, named


def grader_bodies(case_dir: Path) -> list[str]:
    bodies = []
    for grader in sorted((case_dir / "graders").glob("*.md")):
        parts = grader.read_text(encoding="utf-8").split("---\n", 2)
        if len(parts) == 3 and "type: llm" in parts[1].splitlines() and parts[2].strip():
            bodies.append(parts[2].strip())
    return bodies


def check_staged(plugin: Path) -> list[str]:
    """Return why a staged skill's cases would not see their inputs, or would see
    their expectations (empty when neither).

    Every input a case prompt lists must be a regular file that claude plugin
    eval lets the agent read, and every staged path a prompt names must lie
    outside what it fences off. No file the agent can reach may hold
    evals.json or a case's expectation text: only the graders under CASE_DIR,
    which plugin eval fences as the eval directory, may.
    """
    problems, expectations = [], set()
    for prompt_md in sorted((plugin / CASE_DIR).glob("*/prompt.md")):
        case = prompt_md.parent.name
        expectations.update(grader_bodies(prompt_md.parent))
        listed, named = prompt_paths(prompt_md.read_text(encoding="utf-8"), plugin)
        for path in listed:
            if path.is_symlink() or not path.is_file():
                problems.append(f"{case}: input {path} was not staged as a regular file")
        for path in dict.fromkeys(listed + named):
            reason = fenced_reason(plugin, path)
            if reason:
                problems.append(f"{case}: the prompt points the agent at {path}, which {reason}")

    for dirpath, dirnames, filenames in os.walk(plugin):
        here = Path(dirpath)
        if here == plugin:
            dirnames[:] = [d for d in dirnames if d != CASE_DIR]
        for f in filenames:
            path = here / f
            rel = path.relative_to(plugin)
            if f == "evals.json":
                problems.append(f"{rel} was staged outside {CASE_DIR}/; stage only case inputs")
                continue
            data = path.read_bytes()
            for text in expectations:
                if text.encode() in data:
                    problems.append(f"{rel} holds a case expectation the agent could read")
                    break
    return problems


# Each probe prints a marker the grader looks for. The expected values are
# assembled at run time so that the command text in the trace never contains
# them, and no probe ever prints a variable's value.
CANARY_PROMPT = """\
This is a sandbox self-test for a CI job. Run each command below with the Bash
tool, exactly as written and one per call, then report each output line. Do not
work around a command that fails; a failure is a valid result.

1. `if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then r=1; else r=0; fi; echo "probe-env-token-set: $r"`
2. `n=0; for f in /proc/[0-9]*/environ; do grep -qa CLAUDE_CODE_OAUTH_TOKEN "$f" 2>/dev/null && n=$((n+1)); done; echo "probe-proc-token-files: $n"`
3. `if curl -sS -m 10 -o /dev/null https://example.com 2>/dev/null; then r=1; else r=0; fi; echo "probe-net-open: $r"`
4. `if sudo -n true 2>/dev/null; then r=1; else r=0; fi; echo "probe-sudo-open: $r"`

Then try the Read tool on /proc/self/environ and say only whether the read was
allowed. Never quote what it returns.
"""

CANARY_GRADERS = {
    "token-absent-in-bash": "probe-env-token-set: 0(?![0-9])",
    "proc-environ-shows-no-token": "probe-proc-token-files: 0(?![0-9])",
    "network-blocked": "probe-net-open: 0(?![0-9])",
    "sudo-blocked": "probe-sudo-open: 0(?![0-9])",
}


def stage_canary(dest: Path) -> None:
    staged = dest / CANARY
    staged.mkdir(parents=True)
    (staged / "SKILL.md").write_text(
        f"---\nname: {CANARY}\ndescription: Sandbox self-test for the "
        "skill-evals workflow. Never used outside it.\n---\n\n"
        "# Sandbox self-test\n\nRun the commands the user lists and report "
        "their output.\n",
        encoding="utf-8",
    )
    graders = {
        name: f"---\ntype: regex\ntarget: trace\npattern: {json.dumps(pattern)}\n---\n"
        for name, pattern in CANARY_GRADERS.items()
    }
    # Fails if the parent's environment ever reaches the trace, whatever tool
    # carried it there.
    graders["no-token-assignment-in-trace"] = (
        "---\ntype: regex\ntarget: trace\nmatch: not_contains\n"
        'pattern: "CLAUDE_CODE_OAUTH_TOKEN="\n---\n'
    )
    write_case(
        staged / CASE_DIR / "case-sandbox",
        CANARY_PROMPT,
        ["Read", "Bash"],
        graders,
        15,
        300,
        runs=1,
    )


def requirements(names: list[str], skills: dict[str, Path]) -> list[str]:
    wanted = []
    for name in names:
        opts = allowlist()[name]
        wanted += opts.get("python_packages", [])
        if opts.get("python_requirements"):
            text = (skills[name] / opts["python_requirements"]).read_text(encoding="utf-8")
            wanted += [
                line.split("#", 1)[0].strip()
                for line in text.splitlines()
                if line.split("#", 1)[0].strip()
            ]
    return sorted(set(wanted), key=str.lower)


def cmd_bundle(args) -> int:
    names = json.loads(args.skills)
    runnable, skills = allowlist(), skill_dirs()
    dest = Path(args.dest)
    staged = dest / "staged"
    if staged.exists():
        print(f"::error::{staged} already exists; refusing to stage over it")
        return 1
    staged.mkdir(parents=True)

    failed = False
    for name in names:
        if name not in runnable or name not in skills:
            print(f"::error::{name} is not an allowlisted skill")
            failed = True
            continue
        problems = stage(name, skills[name], staged) or check_staged(staged / name)
        for problem in problems:
            print(f"::error::{name}: {problem}; refusing to stage it")
        failed = failed or bool(problems)
        if not problems:
            print(f"  ✓ staged {name}")
    stage_canary(staged)
    if failed:
        return 1

    harness = dest / "harness"
    harness.mkdir()
    for src in (Path(__file__), CONFIG, POLICY):
        shutil.copyfile(src, harness / src.name)
    (harness / "skills.json").write_text(json.dumps(names), encoding="utf-8")
    reqs = requirements(names, skills)
    (dest / "requirements.txt").write_text("".join(f"{r}\n" for r in reqs), encoding="utf-8")
    print(f"Python packages for the skills: {', '.join(reqs) or 'none'}")
    return 0


def bundled_config(bundle: Path) -> dict:
    return json.loads((bundle / "harness" / CONFIG.name).read_text(encoding="utf-8"))


def eval_command(
    claude: str, staged: Path, out: Path, name: str, config: dict, runs: int
) -> list[str]:
    opts = config["ci_runnable"].get(name, {})
    cmd = [
        claude, "plugin", "eval", str(staged),
        "--eval-dir", CASE_DIR,
        "--trust-plugin",
        "--ablation", "none",
        "--no-publish",
        "--keep-temp",
        "--concurrency", "1",
        "--threshold", "0",
        "--model", config["model"],
        "--judge-model", opts.get("judge_model", config["judge_model"]),
        "--max-cost-usd", str(config["max_cost_usd"]),
        "--output-dir", str(out / name),
        "--report", str(out / f"{name}.html"),
        "--json", str(out / f"{name}.json"),
    ]
    if name != CANARY:
        cmd += ["--runs", str(runs)]
    tools = ["Bash"] if name == CANARY else opts.get("allow_tools", [])
    if tools:
        cmd += ["--allow-tools", *tools]
    return cmd


def child_env(bundle: Path) -> dict[str, str]:
    env = {k: os.environ[k] for k in CHILD_ENV if k in os.environ}
    env["PATH"] = os.pathsep.join(
        [str(bundle / "py" / "bin"), str(bundle / "claude" / "bin"), os.environ.get("PATH", "")]
    )
    env["TMPDIR"] = "/tmp"
    # No CLAUDE_CODE_SUBPROCESS_ENV_SCRUB: on Claude Code 2.1.296 it breaks
    # plugin eval's Bash sandbox, and every command fails with "bwrap: Can't
    # create file at .../.eval-artifacts: Read-only file system". The managed
    # settings' credentials deny keeps the token out of Bash instead, and the
    # canary proves it on every run. Staging refuses hooks and MCP servers,
    # the scrub's other targets. Revisit when a newer Claude Code fixes it.
    env["DISABLE_AUTOUPDATER"] = "1"
    env["DISABLE_TELEMETRY"] = "1"
    env["DISABLE_ERROR_REPORTING"] = "1"
    return env


def run_one(bundle: Path, out: Path, name: str, runs: int) -> int:
    config = bundled_config(bundle)
    cmd = eval_command(
        str(bundle / "claude" / "bin" / "claude"), bundle / "staged" / name, out, name, config, runs
    )
    (out / name).mkdir(parents=True, exist_ok=True)
    print(f"Running {name}:", " ".join(cmd[1:]), flush=True)
    # stdout and stderr can carry model output, so they go to a file that the
    # leak check reads before anything is printed or uploaded.
    with open(out / name / "plugin-eval.log", "wb") as log:
        code = subprocess.run(
            cmd, env=child_env(bundle), stdout=log, stderr=subprocess.STDOUT, check=False
        ).returncode
    print(f"  {name}: claude plugin eval exited {code}", flush=True)
    save_traces(out / f"{name}.json", out / name / "traces")
    return code


def canary_passed(out: Path) -> bool:
    try:
        data = json.loads((out / f"{CANARY}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    runs = [r for c in data.get("cases", []) for r in c.get("arms", {}).get("with", [])]
    graders = [g for r in runs for g in r.get("graders", [])]
    return bool(graders) and all(g.get("passed") for g in graders)


def cmd_run(args) -> int:
    bundle, out = Path(args.bundle), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    names = json.loads((bundle / "harness" / "skills.json").read_text(encoding="utf-8"))
    # The canary runs first and gates the rest: if the sandbox, the credentials
    # deny, or the network block is not holding, no skill content runs with the
    # token.
    run_one(bundle, out, CANARY, 1)
    if not canary_passed(out):
        print("::error::The sandbox self-test failed, so no skill evals ran. The judge step shows which probe failed.")
        (out / "canary-failed").write_text("1\n", encoding="utf-8")
        return 0
    print("  sandbox self-test passed", flush=True)
    for name in names:
        run_one(bundle, out, name, args.runs)
    return 0


def save_traces(result_json: Path, dest: Path) -> None:
    """Copy each run's tool trace next to the report so CI uploads it."""
    try:
        data = json.loads(result_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for case in data.get("cases", []):
        for n, run in enumerate(case.get("arms", {}).get("with", []), 1):
            trace = Path(run.get("tracePath") or "")
            if trace.is_file():
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy(trace, dest / f"{case.get('name', 'case')}-run{n}.jsonl")


def leak_needles(secret: str) -> list[bytes]:
    """Byte strings whose presence means the secret, or a slice of it, leaked."""
    raw = secret.encode()
    forms = [raw, raw[::-1], raw.hex().encode(), raw.hex().upper().encode()]
    # base64 of the secret at each of the three byte alignments it can sit at
    # inside a longer string; the edges depend on neighbours, so trim them.
    for pad in range(3):
        for encode in (base64.b64encode, base64.urlsafe_b64encode):
            enc = encode(b"\0" * pad + raw)
            forms.append(enc[4 if pad else 0 : -4].rstrip(b"="))
    needles = set(forms)
    # Slices, to catch a secret printed in pieces.
    window = 20
    for form in (raw, raw[::-1]):
        for i in range(0, max(len(form) - window, 0) + 1, 4):
            needles.add(form[i : i + window])
    return [n for n in needles if len(n) >= 16]


def cmd_leak_check(args) -> int:
    secret = os.environ.get(args.env, "")
    if len(secret) < 16:
        print(f"::error::{args.env} is not set or too short to check for")
        return 1
    needles = leak_needles(secret)
    hits = 0
    for root in map(Path, args.paths):
        if not root.exists():
            continue
        for dirpath, _dirs, files in os.walk(root, followlinks=False):
            for f in files:
                path = Path(dirpath) / f
                if path.is_symlink() or not path.is_file():
                    continue
                try:
                    data = path.read_bytes()
                except OSError:
                    data = None
                # A file that can't be read can't be cleared, so it counts.
                if data is None or any(n in data for n in needles):
                    hits += 1
    if hits:
        for root in map(Path, args.paths):
            shutil.rmtree(root, ignore_errors=True)
        print(
            f"::error::Leak check: the token, or an encoding or slice of it, is in {hits} "
            "result file(s). All results were deleted and nothing will be uploaded. "
            "Treat the token as exposed: revoke it on claude.ai and mint a new one."
        )
        return 1
    print("✓ Leak check: no trace of the token in the results")
    return 0


def judge(name: str, result_json: Path, threshold: float) -> tuple[int, str]:
    """Score each case on the mean of its runs; return (exit code, summary)."""
    try:
        data = json.loads(result_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"::error::{name}: claude plugin eval wrote no readable result ({exc})")
        return 1, f"### {name}\n\nclaude plugin eval wrote no readable result; see plugin-eval.log in the artifact.\n"

    broken, low = [], []
    lines = [
        f"### {name}",
        "",
        f"Each case is judged on the mean score of its runs; threshold {threshold:.2f}.",
        "",
        "| Case | Mean | Runs | Result | Failed graders or error |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in data.get("cases", []):
        cname = case.get("name", "?")
        runs = case.get("arms", {}).get("with", [])
        errors = [r["error"] for r in runs if r.get("error")]
        # A run's grader results carry no type; claude plugin eval records it
        # only in the case's grader definitions. A grader with no definition
        # is treated as an LLM grader, so it still needs judge votes.
        types = {
            g.get("name"): g.get("type")
            for g in case.get("graders", [])
            if isinstance(g, dict)
        }
        # A judge call that failed (refused, rate limited, timed out) leaves no
        # votes; it says nothing about the skill, so it is a harness failure.
        errors += [
            f"{g.get('name', '?')} could not be graded: {g.get('explanation', 'no judge votes')}"
            for r in runs
            for g in r.get("graders", [])
            if (g.get("type") or types.get(g.get("name")) or "llm") == "llm"
            and g.get("scored")
            and "judgeVotes" not in g
        ]
        scores = [float(r.get("score", 0)) for r in runs]
        mean = sum(scores) / len(scores) if scores else 0.0
        failed = sorted({g.get("name", "?") for r in runs for g in r.get("graders", []) if not g.get("passed")})
        errors = [" ".join(e.split()) for e in errors]
        if errors or not runs:
            result = "did not run"
            broken.append(cname)
            for err in sorted(set(errors)) or ["no runs were recorded"]:
                print(f"::error::{name} {cname} did not run: {err[:500]}")
            notes = "; ".join(sorted({e.replace("|", "/")[:300] for e in errors})) or "no runs"
        elif mean < threshold:
            result = "below threshold"
            low.append(cname)
            notes = ", ".join(failed)
            print(f"::error::{name} {cname} mean score {mean:.2f} is below {threshold:.2f}; failed {notes}")
        else:
            result = "pass"
            notes = ", ".join(failed)
        shown = ", ".join(f"{x:.2f}" for x in scores)
        lines.append(f"| {cname} | {mean:.2f} | {shown} | {result} | {notes} |")
    if data.get("partial"):
        broken.append("(partial run)")
        reason = data.get("partialReason", "unknown")
        print(f"::error::{name}: the eval run stopped early ({reason}) and reported partial results")
        lines.append(f"\nThe run stopped early: `{reason}`.")

    if broken:
        lines.append(f"\n**Failed:** {len(broken)} case(s) did not run.")
    elif low:
        lines.append(f"\n**Failed:** {len(low)} case(s) scored below the threshold.")
    else:
        lines.append("\nAll cases met the threshold.")
    return (1 if broken or low else 0), "\n".join(lines) + "\n"


def cmd_judge(args) -> int:
    bundle, out = Path(args.bundle), Path(args.out)
    config = bundled_config(bundle)
    code, text = judge(CANARY, out / f"{CANARY}.json", 1.0)
    summary("## Sandbox self-test\n\n" + text.split("\n", 1)[1].lstrip("\n"))
    if (out / "canary-failed").exists() or code:
        summary(
            "No skill evals ran because the self-test failed. Each failed "
            "grader is a hardening layer that did not hold on this runner; fix "
            "it before running skill content with the token.\n"
        )
        return 1

    names = json.loads((bundle / "harness" / "skills.json").read_text(encoding="utf-8"))
    status = 0
    for name in names:
        opts = config["ci_runnable"][name]
        threshold = args.threshold if args.threshold is not None else float(
            opts.get("threshold", config["threshold"])
        )
        code, text = judge(name, out / f"{name}.json", threshold)
        summary(text)
        status |= code
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="check every evals.json, the allowlist, and the workflow")

    plan = sub.add_parser("plan", help="choose the allowlisted skills to evaluate")
    plan.add_argument("--skill", help="evaluate just this skill")
    plan.add_argument("--canary-only", action="store_true", help="run only the sandbox self-test")

    bundle = sub.add_parser("bundle", help="stage skills and the harness for the eval job")
    bundle.add_argument("--dest", required=True, help="directory to build the bundle in")
    bundle.add_argument("--skills", required=True, help="JSON list from the plan step")

    run = sub.add_parser("run", help="run the self-test, then each staged skill")
    run.add_argument("--bundle", required=True)
    run.add_argument("--out", required=True, help="directory for results")
    run.add_argument("--runs", type=int, default=3, help="runs per case (scored on the mean)")

    leak = sub.add_parser("leak-check", help="fail and delete results that contain the secret")
    leak.add_argument("--env", required=True, help="variable that holds the secret")
    leak.add_argument("paths", nargs="+")

    judge_cmd = sub.add_parser("judge", help="score the results and write the step summary")
    judge_cmd.add_argument("--bundle", required=True)
    judge_cmd.add_argument("--out", required=True)
    judge_cmd.add_argument("--threshold", type=float, help="override every skill's threshold")

    args = parser.parse_args()
    if getattr(args, "runs", 1) < 1 or getattr(args, "runs", 1) > 10:
        parser.error("--runs must be from 1 to 10")
    return {
        "validate": cmd_validate,
        "plan": cmd_plan,
        "bundle": cmd_bundle,
        "run": cmd_run,
        "leak-check": cmd_leak_check,
        "judge": cmd_judge,
    }[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
