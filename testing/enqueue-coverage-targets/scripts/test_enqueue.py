#!/usr/bin/env python3
"""Regression tests for enqueue.sh against the skill's own eval fixtures.

Run with pytest and pytest-cov importable (and Go on PATH for the Go test).
Each case works on a read-only copy of a fixture, the way a run against a
read-only checkout does, and checks that the queue and the hit rows reach
stdout, because a sandboxed shell may not keep /tmp between commands.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "enqueue.sh"
FIXTURES = SKILL / "evals" / "files"


def make_read_only(path: Path) -> None:
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            p = Path(root) / name
            p.chmod(p.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


class EnqueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for root, dirs, _ in os.walk(self.tmp):
            for d in dirs:
                (Path(root) / d).chmod(0o755)
        self.tmp.chmod(0o755)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def project(self, name: str) -> Path:
        dest = self.tmp / name
        shutil.copytree(FIXTURES / name, dest)
        make_read_only(dest)
        return dest

    def enqueue(self, *args: str, target: str = "80", cwd: Path | None = None):
        env = {**os.environ, "SQUAD_COVERAGE_TARGET": target}
        return subprocess.run(
            ["bash", str(SCRIPT), *args],
            capture_output=True, text=True, env=env, cwd=cwd or self.tmp, check=False,
        )

    def test_python_read_only_project_prints_queue_and_hits(self):
        proj = self.project("cov-py")
        res = self.enqueue("python", str(proj), target="90")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("app/pricing.py\t", res.stdout)
        self.assertIn("(target 90%)", res.stdout)
        self.assertIn("--- app/pricing.py", res.stdout)
        self.assertIn("app/pricing.py:18", res.stdout)
        self.assertNotIn("tests/test_pricing.py", res.stdout.split("=== queue size ===")[0])
        self.assertFalse((proj / ".coverage").exists())

    def test_python_queues_shipped_testing_package_but_not_tests(self):
        proj = self.tmp / "shipped-testing"
        (proj / "mypkg" / "testing").mkdir(parents=True)
        (proj / "tests").mkdir()
        (proj / "mypkg" / "__init__.py").write_text("")
        (proj / "mypkg" / "testing" / "__init__.py").write_text("")
        (proj / "mypkg" / "testing" / "fixtures.py").write_text(
            "def make(n):\n    if n > 0:\n        return n\n    return -n\n"
        )
        (proj / "tests" / "test_fixtures.py").write_text(
            "from mypkg.testing.fixtures import make\n\n"
            "def test_make():\n    assert make(1) == 1\n"
        )
        make_read_only(proj)
        res = self.enqueue("python", str(proj), target="90")
        self.assertEqual(res.returncode, 0, res.stderr)
        queue = res.stdout.split("=== queue size ===")[0]
        self.assertIn("mypkg/testing/fixtures.py\t", queue)
        self.assertNotIn("tests/test_fixtures.py", queue)

    def test_language_and_directory_arguments_work_in_either_order(self):
        proj = self.project("cov-py")
        res = self.enqueue(str(proj), "python", target="90")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("language=python", res.stdout)

    @unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
    def test_go_autodetect_prints_zero_coverage_functions(self):
        proj = self.project("cov-go")
        res = self.enqueue(str(proj))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("example.com/covgo/calc\t", res.stdout)
        for fn in ("Div", "Clamp", "Mean"):
            self.assertRegex(res.stdout, rf"0\.0%\t{fn}\n")
        self.assertNotRegex(res.stdout, r"100\.0%\tAdd")

    def test_not_a_project_reports_empty_queue(self):
        proj = self.project("not-a-project")
        res = self.enqueue(str(proj), target="75")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("UNKNOWN_PROJECT", res.stderr)
        self.assertIn("=== queue size ===\n0", res.stdout)
        self.assertEqual(Path("/tmp/squad-targets.txt").read_text(), "")

    def test_unknown_argument_is_a_usage_error(self):
        res = self.enqueue("no-such-directory")
        self.assertEqual(res.returncode, 2)
        self.assertIn("usage:", res.stderr)


if __name__ == "__main__":
    unittest.main()
