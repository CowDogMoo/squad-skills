#!/usr/bin/env python3
"""Regression tests for portable eval inputs and their measured ground truth.

Run with the skill's scripts/requirements.txt installed. No Live or credentials.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL.parents[1] / '.github' / 'scripts'))
import alsio  # noqa: E402
import skill_evals  # noqa: E402


class FixtureTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.fixtures = self.tmp / 'fixtures'
        self.run_python(SKILL / 'evals/files/make_fixtures.py', self.fixtures)
        self.original = self.fingerprints()

    def tearDown(self):
        self.assertEqual(self.fingerprints(), self.original, 'detectors changed an input')

    def fingerprints(self):
        return {p.relative_to(self.fixtures): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.fixtures.rglob('*') if p.is_file()}

    def run_python(self, script, *args):
        result = subprocess.run([sys.executable, str(script), *map(str, args)],
                                cwd=self.tmp, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def report(self, script, name):
        dest = self.tmp / (script + '.json')
        self.run_python(SKILL / 'scripts' / (script + '.py'), self.fixtures / name,
                        '--pair', 'Scratch A=Scratch B', '--json', dest)
        return json.loads(dest.read_text())

    def test_staged_generator_is_portable_and_inputs_are_usable(self):
        staged = self.tmp / 'staged'
        self.assertEqual(skill_evals.stage(SKILL.name, SKILL, staged), [])
        self.assertEqual(skill_evals.check_staged(staged / SKILL.name), [])
        # Run just the staged input, without its repository siblings.
        isolated = self.tmp / 'generator.py'
        shutil.copyfile(staged / SKILL.name / 'eval-inputs/files/make_fixtures.py', isolated)
        relocated = self.tmp / 'relocated'
        self.run_python(isolated, relocated)
        self.assertEqual(self.original, {
            p.relative_to(relocated): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in relocated.rglob('*') if p.is_file()})
        self.assertLess(sum(p.stat().st_size for p in relocated.rglob('*') if p.is_file()), 200_000)
        for path in relocated.glob('*.als'):
            self.assertEqual(path.read_bytes()[:2], b'\x1f\x8b')
            trs = alsio.tracks(alsio.load(path), path)
            self.assertEqual(len(trs), 8)
            for track in trs:
                for clip in track['clips']:
                    self.assertTrue(alsio.placement_usable(clip), clip)
                    self.assertTrue(Path(clip['file']).is_relative_to(relocated))

    def test_clean_control_and_positive_controls(self):
        self.assertEqual(self.report('placement_check', 'clean-control.als')['flags'], [])
        audio = self.report('attack_audit', 'clean-control.als')
        self.assertEqual(len(audio['rows']), 32)
        self.assertTrue(all(abs(r['lag_ms']) <= 2 and not r['flag'] for r in audio['rows']))
        for script in ('placement_check', 'attack_audit'):
            output = self.run_python(SKILL / 'scripts' / (script + '.py'),
                                     self.fixtures / 'clean-control.als',
                                     '--pair', 'Scratch A=Scratch B', '--inject', 'Scratch A@4+0.04')
            self.assertIn('CONTROL OK', output)

    def test_planted_nudges_have_placement_pair_and_audio_evidence(self):
        report = self.report('placement_check', 'planted-nudge.als')
        self.assertEqual([(f['track'], f['start'], f['off_beats'], f['suggest_start'])
                          for f in report['flags']],
                         [(0, 20.0625, 0.0625, 20.0), (0, 28.0625, 0.0625, 28.0)])
        self.assertEqual(len(report['pair_flags']), 2)
        self.assertTrue(all('Scratch A moved' in f['who'] for f in report['pair_flags']))
        for test in (20, 28):
            output = self.run_python(SKILL / 'scripts/section_compare.py',
                                     self.fixtures / 'planted-nudge.als', '--tracks',
                                     'Scratch A', 'Scratch B', '--ref', 4, '--test', test, '--length', 4)
            lines = [line for line in output.splitlines() if ' shift ' in line]
            self.assertEqual(len(lines), 2)
            for line, expected in zip(lines, (31.25, 0)):
                shift = float(line.split('shift')[1].split('ms')[0])
                corr = float(line.split('corr')[1].split()[0])
                self.assertAlmostEqual(shift, expected, delta=2)
                self.assertGreater(corr, 0.95)

    def test_full_audit_separates_slices_nudge_audio_only_and_clean(self):
        report = self.report('placement_check', 'full-audit.als')
        expected = {(ti, start, -0.5) for ti in (0, 1) for start in (36.5, 40.5, 44.5)}
        expected.add((3, 19.96, -0.04))
        self.assertEqual({(f['track'], f['start'], f['off_beats']) for f in report['flags']}, expected)
        self.assertEqual(report['pairs'], [[0, 1], [2, 3], [4, 5], [6, 7]])
        self.assertEqual(len(report['pair_flags']), 1)
        audio = self.report('attack_audit', 'full-audit.als')
        self.assertEqual(len(audio['rows']), 46)
        for row in audio['rows']:
            if row['track'] == 7:
                self.assertAlmostEqual(row['lag_ms'], 20, delta=2)
                self.assertTrue(row['flag'])
                self.assertGreater(row['corr'], 0.9)
            elif row['track'] == 3 and row['start'] == 19.96:
                self.assertAlmostEqual(row['lag_ms'], -20, delta=2)
                self.assertTrue(row['flag'])
            elif row['track'] in (0, 1, 4, 5):
                self.assertLessEqual(abs(row['lag_ms']), 2)
                self.assertFalse(row['flag'])


if __name__ == '__main__':
    unittest.main()
