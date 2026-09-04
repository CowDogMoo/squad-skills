#!/usr/bin/env node
// test.mjs — offline unit tests for the cquorum harness. No network, no
// claude CLI: judge/render/extract logic is exercised via module imports and
// by spawning node on the harness's own scripts. Judged run dirs are always
// temp COPIES of testdata so the checked-in fixtures stay pristine.
//
// Prints exactly "harness tests passed" (stdout) only when every assertion
// passed; otherwise prints the failing case and exits 1.

import assert from 'node:assert/strict';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { canonicalJson, judgeRun, ProtocolError, validateBallot } from './judge.mjs';
import { checkPromptIndependence, COMPLETION_QUESTION, renderPrompt } from './render-prompts.mjs';
import { extractBallot, stripFence } from './run-seats.mjs';

const HARNESS = dirname(fileURLToPath(import.meta.url));
const TESTDATA = join(HARNESS, 'testdata');
const JUDGE = join(HARNESS, 'judge.mjs');
const RENDER = join(HARNESS, 'render-prompts.mjs');
const RUN_SEATS = join(HARNESS, 'run-seats.mjs');
const EXEC_SEAT = join(HARNESS, 'exec-seat.mjs');
const LOG_VERDICT = join(HARNESS, 'log-verdict.mjs');

const scratch = mkdtempSync(join(tmpdir(), 'cquorum-test-'));
function copyRun(name) {
  const dest = join(scratch, `${name}-${copyRun.n++}`);
  cpSync(join(TESTDATA, name), dest, { recursive: true });
  return dest;
}
copyRun.n = 0;

function seatState(verdict, seatId) {
  const seat = verdict.seats.find((s) => s.seat_id === seatId);
  assert.ok(seat, `seat ${seatId} missing from verdict`);
  return seat;
}

function runNode(args, env = {}) {
  return spawnSync(process.execPath, args, { encoding: 'utf8', env: { ...process.env, ...env } });
}

function mkRun(name, panel) {
  const dir = join(scratch, name);
  mkdirSync(join(dir, 'ballots'), { recursive: true });
  writeFileSync(join(dir, 'panel.json'), canonicalJson(panel));
  return dir;
}

const tests = [];
function test(name, fn) {
  tests.push([name, fn]);
}

test('unanimous complete -> COMPLETE', () => {
  const verdict = judgeRun(copyRun('run-unanimous'));
  assert.equal(verdict.verdict, 'COMPLETE');
  assert.equal(verdict.$schema, 'cquorum/verdict/v1');
  for (const seat of verdict.seats) assert.equal(seat.state, 'complete');
  assert.deepEqual(verdict.work_queue, []);
  assert.deepEqual(verdict.counts, {
    absent: 0, abstain: 0, complete: 3, malformed: 0, required: 3, seats: 3, veto: 0,
  });
});

test('single veto -> NOT_COMPLETE with veto in work_queue', () => {
  const verdict = judgeRun(copyRun('run-veto'));
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  assert.equal(seatState(verdict, 'correctness').state, 'veto');
  assert.equal(verdict.work_queue.length, 1);
  assert.deepEqual(verdict.work_queue[0], {
    criterion: 'SumRange must include the upper bound',
    evidence: 'main.go:14 loops i < hi but TASK.md requires inclusive range',
    seat_id: 'correctness',
  });
  assert.equal(verdict.counts.veto, 1);
});

test('abstain -> NOT_COMPLETE', () => {
  const verdict = judgeRun(copyRun('run-abstain'));
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  const seat = seatState(verdict, 'test-quality');
  assert.equal(seat.state, 'abstain');
  assert.deepEqual(seat.faults, []); // explicit abstain is not a fault
  assert.deepEqual(verdict.work_queue, []);
});

test('absent ballot file -> NOT_COMPLETE with seat state absent', () => {
  const verdict = judgeRun(copyRun('run-absent'));
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  const seat = seatState(verdict, 'test-quality');
  assert.equal(seat.state, 'absent');
  assert.deepEqual(seat.faults, ['no ballot file']);
  assert.equal(verdict.counts.absent, 1);
});

test('malformed prose ballot -> NOT_COMPLETE malformed, never repaired', () => {
  const verdict = judgeRun(copyRun('run-malformed'));
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  const seat = seatState(verdict, 'test-quality');
  assert.equal(seat.state, 'malformed');
  assert.ok(seat.faults.some((f) => f.startsWith('unparsable ballot:')), `faults: ${seat.faults}`);
});

test('schema-invalid ballot (bad verdict enum) -> malformed', () => {
  const dir = copyRun('run-unanimous');
  writeFileSync(join(dir, 'ballots', 'correctness.json'), JSON.stringify({
    seat_id: 'correctness', jurisdiction: 'correctness', verdict: 'done', unmet: [],
  }));
  const verdict = judgeRun(dir);
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  const seat = seatState(verdict, 'correctness');
  assert.equal(seat.state, 'malformed');
  assert.ok(seat.faults.some((f) => f.includes('verdict must be')), `faults: ${seat.faults}`);
});

test('veto without citation -> demoted to abstain with seat fault', () => {
  const verdict = judgeRun(copyRun('run-uncited-veto'));
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  const seat = seatState(verdict, 'correctness');
  assert.equal(seat.state, 'abstain');
  assert.ok(seat.faults.some((f) => f.includes('veto without citation')), `faults: ${seat.faults}`);
  assert.deepEqual(verdict.work_queue, []); // an uncited veto contributes nothing actionable
  assert.equal(verdict.counts.veto, 0);
});

test('contradictory "complete" with non-empty unmet -> demoted to abstain', () => {
  const dir = copyRun('run-unanimous');
  writeFileSync(join(dir, 'ballots', 'correctness.json'), JSON.stringify({
    seat_id: 'correctness', jurisdiction: 'correctness', verdict: 'complete',
    unmet: [{ criterion: 'x', evidence: 'y' }],
  }));
  const verdict = judgeRun(dir);
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  const seat = seatState(verdict, 'correctness');
  assert.equal(seat.state, 'abstain');
  assert.ok(seat.faults.some((f) => f.includes('contradictory')), `faults: ${seat.faults}`);
});

test('determinism: judge run twice -> byte-identical verdict.json', () => {
  const dir = copyRun('run-veto');
  const first = runNode([JUDGE, dir]);
  assert.equal(first.status, 0, first.stderr);
  const bytes1 = readFileSync(join(dir, 'verdict.json'));
  const second = runNode([JUDGE, dir]);
  assert.equal(second.status, 0, second.stderr);
  const bytes2 = readFileSync(join(dir, 'verdict.json'));
  assert.ok(bytes1.equals(bytes2), 'verdict.json differs between identical runs');
  assert.ok(bytes1.toString('utf8').endsWith('}\n'), 'canonical output must end with a trailing newline');
});

test('mutation: flipping one ballot flips the verdict', () => {
  const dir = copyRun('run-unanimous');
  const before = judgeRun(dir);
  assert.equal(before.verdict, 'COMPLETE');
  writeFileSync(join(dir, 'ballots', 'test-quality.json'), JSON.stringify({
    seat_id: 'test-quality', jurisdiction: 'test-quality', verdict: 'incomplete',
    unmet: [{ criterion: 'criterion 3 has no covering test', evidence: 'main_test.go lacks it' }],
  }));
  const after = judgeRun(dir);
  assert.equal(after.verdict, 'NOT_COMPLETE');
  assert.notDeepEqual(before, after, 'judge output did not react to a flipped ballot');
  assert.equal(after.work_queue.length, 1);
  assert.equal(after.work_queue[0].seat_id, 'test-quality');
});

test('work_queue dedups by criterion in stable panel order', () => {
  const verdict = judgeRun(copyRun('run-dedup'));
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  assert.deepEqual(verdict.work_queue, [
    {
      criterion: 'criterion 2 lacks a covering test',
      evidence: 'no test exercises ParseFlags error path', // first citer (panel order) wins
      seat_id: 'spec-coverage',
    },
    {
      criterion: 'error message must name the flag',
      evidence: 'main.go:22 returns generic error',
      seat_id: 'correctness',
    },
  ]);
});

test('protocol corruption: duplicate seat_id -> exit 2, no verdict written', () => {
  const dir = copyRun('run-dup-seat');
  const res = runNode([JUDGE, dir]);
  assert.equal(res.status, 2, `stdout=${res.stdout} stderr=${res.stderr}`);
  assert.ok(res.stderr.includes('duplicate seat_id'), res.stderr);
  assert.ok(!existsSync(join(dir, 'verdict.json')), 'verdict.json must not be written on corruption');
});

test('protocol corruption: unknown ballot file and missing panel.json', () => {
  assert.throws(() => judgeRun(copyRun('run-unknown-ballot')), ProtocolError);
  const empty = join(scratch, 'empty-run');
  mkdirSync(empty, { recursive: true });
  assert.throws(() => judgeRun(empty), ProtocolError);
});

test('validateBallot enforces confidence range and seat match', () => {
  const base = { seat_id: 'a', jurisdiction: 'j', verdict: 'complete', unmet: [], evidence: [], confidence: 0.5 };
  assert.equal(validateBallot(base, 'a').valid, true);
  assert.equal(validateBallot({ ...base, confidence: 1.5 }, 'a').valid, false);
  assert.equal(validateBallot(base, 'b').valid, false);
  assert.equal(validateBallot({ ...base, unmet: ['not-an-object'] }, 'a').valid, false);
});

test('independence checker FAILS on the contaminated testdata prompt', () => {
  const seats = JSON.parse(readFileSync(join(TESTDATA, 'seats-mini.json'), 'utf8'));
  const prompt = readFileSync(join(TESTDATA, 'prompts-contaminated', 'spec-coverage.prompt.md'), 'utf8');
  const violations = checkPromptIndependence(prompt, 'spec-coverage', seats);
  assert.ok(violations.length >= 2, `expected multiple violations, got: ${JSON.stringify(violations)}`);
  assert.ok(violations.some((v) => v.includes('forbidden string')), `no ground-truth violation in: ${violations}`);
  assert.ok(violations.some((v) => v.includes('"correctness"')), `no cross-seat violation in: ${violations}`);
});

test('independence checker skips values shared with the seat itself', () => {
  const seats = [
    { seat_id: 'skeptic', jurisdiction: 'global', style: 'personality', persona: 'assume unfinished' },
    { seat_id: 'pragmatic', jurisdiction: 'global', style: 'personality', persona: 'value shipped work' },
  ];
  const clean = 'Scope: global — judge the task as a whole.';
  assert.deepEqual(checkPromptIndependence(clean, 'skeptic', seats), []);
  const dirty = 'Scope: global. By the way, seat pragmatic already voted.';
  assert.ok(checkPromptIndependence(dirty, 'skeptic', seats).length > 0);
});

test('render-prompts emits clean, complete prompts for every seat', () => {
  const outDir = join(scratch, 'prompts-out');
  const fixtureDir = join(TESTDATA, 'fixture-mini');
  const res = runNode([RENDER, fixtureDir, join(TESTDATA, 'seats-mini.json'), outDir]);
  assert.equal(res.status, 0, res.stderr);
  const seats = JSON.parse(readFileSync(join(TESTDATA, 'seats-mini.json'), 'utf8'));
  for (const seat of seats) {
    const path = join(outDir, `${seat.seat_id}.prompt.md`);
    assert.ok(existsSync(path), `missing prompt for ${seat.seat_id}`);
    const prompt = readFileSync(path, 'utf8');
    assert.deepEqual(checkPromptIndependence(prompt, seat.seat_id, seats), [], `contaminated prompt for ${seat.seat_id}`);
    assert.ok(prompt.includes(COMPLETION_QUESTION), 'completion question missing');
    assert.ok(prompt.includes(`"seat_id": ${JSON.stringify(seat.seat_id)}`), 'ballot contract not seat-pinned');
    assert.ok(prompt.includes('cited evidence per acceptance criterion'), 'skeptic bias missing');
    assert.ok(prompt.includes(resolve(fixtureDir)), 'fixture dir missing from prompt');
  }
  const meta = JSON.parse(readFileSync(join(outDir, '_run.json'), 'utf8'));
  assert.equal(meta.fixture_dir, resolve(fixtureDir));
  // renderPrompt is what main uses — spot-check the pure function agrees.
  assert.equal(renderPrompt(seats[0], resolve(fixtureDir)), readFileSync(join(outDir, 'spec-coverage.prompt.md'), 'utf8'));
});

test('extractBallot strips one optional fence and validates', () => {
  const ballot = { seat_id: 'alpha', jurisdiction: 'global', verdict: 'complete', unmet: [], evidence: ['ok'], confidence: 0.8 };
  const fenced = JSON.stringify({ result: '```json\n' + JSON.stringify(ballot) + '\n```' });
  const bare = JSON.stringify({ result: JSON.stringify(ballot) });
  assert.equal(extractBallot(fenced, 'alpha').ok, true);
  assert.equal(extractBallot(bare, 'alpha').ok, true);
  assert.equal(stripFence('```\n{"a": 1}\n```'), '{"a": 1}');
  assert.equal(extractBallot(fenced, 'beta').ok, false); // seat mismatch
  assert.equal(extractBallot(JSON.stringify({ result: 'I believe it is complete.' }), 'alpha').ok, false);
  assert.equal(extractBallot('not json at all', 'alpha').ok, false);
  assert.equal(extractBallot(JSON.stringify({ no_result: true }), 'alpha').ok, false);
});

test('run-seats --dry-run: valid envelope -> ballot; invalid -> raw only', () => {
  const promptDir = join(scratch, 'dry-prompts');
  const runDir = join(scratch, 'dry-run-out');
  const ballotsDir = join(runDir, 'ballots');
  mkdirSync(join(promptDir, 'dryrun'), { recursive: true });
  writeFileSync(join(promptDir, '_run.json'), canonicalJson({ fixture_dir: join(TESTDATA, 'fixture-mini') }));
  writeFileSync(join(promptDir, 'alpha.prompt.md'), 'vote please\n');
  writeFileSync(join(promptDir, 'beta.prompt.md'), 'vote please\n');
  writeFileSync(join(promptDir, 'gamma.prompt.md'), 'vote please\n'); // no staged envelope -> absent
  const goodBallot = { seat_id: 'alpha', jurisdiction: 'global', verdict: 'complete', unmet: [], evidence: ['e'], confidence: 1 };
  writeFileSync(join(promptDir, 'dryrun', 'alpha.envelope.json'),
    JSON.stringify({ result: '```json\n' + JSON.stringify(goodBallot) + '\n```' }));
  writeFileSync(join(promptDir, 'dryrun', 'beta.envelope.json'),
    JSON.stringify({ result: 'prose, not a ballot' }));
  const res = runNode([RUN_SEATS, promptDir, ballotsDir, '--dry-run']);
  assert.equal(res.status, 0, res.stderr);
  assert.ok(existsSync(join(ballotsDir, 'alpha.json')), 'valid dry-run ballot not written');
  assert.equal(JSON.parse(readFileSync(join(ballotsDir, 'alpha.json'), 'utf8')).verdict, 'complete');
  assert.ok(!existsSync(join(ballotsDir, 'beta.json')), 'invalid ballot must not be written');
  assert.ok(!existsSync(join(ballotsDir, 'gamma.json')), 'absent seat must not get a ballot');
  assert.ok(existsSync(join(runDir, 'raw', 'alpha.json')), 'raw envelope for alpha missing');
  assert.ok(existsSync(join(runDir, 'raw', 'beta.json')), 'raw envelope for beta missing');
  assert.ok(!existsSync(join(runDir, 'raw', 'gamma.json')), 'no envelope existed for gamma');
});

test('end to end offline: dry-run ballots + panel judge to NOT_COMPLETE', () => {
  // beta (invalid envelope) and gamma (no envelope) from the dry-run above are
  // absent; a panel requiring them must gate NOT_COMPLETE.
  const runDir = join(scratch, 'dry-run-out');
  writeFileSync(join(runDir, 'panel.json'), canonicalJson([
    { jurisdiction: 'global', required: true, seat_id: 'alpha' },
    { jurisdiction: 'global', required: true, seat_id: 'beta' },
    { jurisdiction: 'global', required: true, seat_id: 'gamma' },
  ]));
  const verdict = judgeRun(runDir);
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  assert.equal(seatState(verdict, 'alpha').state, 'complete');
  assert.equal(seatState(verdict, 'beta').state, 'absent');
  assert.equal(seatState(verdict, 'gamma').state, 'absent');
});

test('validateBallot: artifacts must be an object of scalars', () => {
  const base = { seat_id: 'a', jurisdiction: 'j', verdict: 'complete', unmet: [] };
  assert.equal(validateBallot({ ...base, artifacts: { exit_code: 0, sha: 'x', ok: true } }, 'a').valid, true);
  assert.equal(validateBallot({ ...base, artifacts: ['nope'] }, 'a').valid, false);
  assert.equal(validateBallot({ ...base, artifacts: { bad: { nested: 1 } } }, 'a').valid, false);
});

const EXEC_PANEL = [{ jurisdiction: 'execution', required: true, requires_artifacts: true, seat_id: 'x' }];

test('requires_artifacts: grounded complete passes, ungrounded is demoted', () => {
  const dir = mkRun('req-art-grounded', EXEC_PANEL);
  writeFileSync(join(dir, 'ballots', 'x.json'), JSON.stringify({
    seat_id: 'x', jurisdiction: 'execution', verdict: 'complete', unmet: [], artifacts: { exit_code: 0 },
  }));
  assert.equal(judgeRun(dir).verdict, 'COMPLETE');
  writeFileSync(join(dir, 'ballots', 'x.json'), JSON.stringify({
    seat_id: 'x', jurisdiction: 'execution', verdict: 'complete', unmet: [],
  }));
  const verdict = judgeRun(dir);
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  const seat = seatState(verdict, 'x');
  assert.equal(seat.state, 'abstain');
  assert.ok(seat.faults.some((f) => f.includes('execution artifacts')), `faults: ${seat.faults}`);
});

test('requires_artifacts: ungrounded veto is demoted and cites nothing', () => {
  const dir = mkRun('req-art-veto', EXEC_PANEL);
  writeFileSync(join(dir, 'ballots', 'x.json'), JSON.stringify({
    seat_id: 'x', jurisdiction: 'execution', verdict: 'incomplete',
    unmet: [{ criterion: 'c', evidence: 'opinion only' }],
  }));
  const verdict = judgeRun(dir);
  assert.equal(seatState(verdict, 'x').state, 'abstain');
  assert.deepEqual(verdict.work_queue, []);
});

test('requires_artifacts: explicit abstain needs no artifacts and is no fault', () => {
  const dir = mkRun('req-art-abstain', EXEC_PANEL);
  writeFileSync(join(dir, 'ballots', 'x.json'), JSON.stringify({
    seat_id: 'x', jurisdiction: 'execution', verdict: 'abstain', unmet: [],
  }));
  const verdict = judgeRun(dir);
  const seat = seatState(verdict, 'x');
  assert.equal(seat.state, 'abstain');
  assert.deepEqual(seat.faults, []);
});

test('panel requires_artifacts must be boolean', () => {
  const dir = mkRun('req-art-badflag', [{ jurisdiction: 'execution', requires_artifacts: 'yes', seat_id: 'x' }]);
  assert.throws(() => judgeRun(dir), ProtocolError);
});

test('exec-seat: passing command -> grounded complete, judged COMPLETE', () => {
  const dir = mkRun('exec-pass', EXEC_PANEL.map((s) => ({ ...s, seat_id: 'exec' })));
  const res = runNode([EXEC_SEAT, dir, 'exec', '--', process.execPath, '-e', 'process.exit(0)']);
  assert.equal(res.status, 0, res.stderr);
  const ballot = JSON.parse(readFileSync(join(dir, 'ballots', 'exec.json'), 'utf8'));
  assert.equal(ballot.verdict, 'complete');
  assert.equal(ballot.artifacts.exit_code, 0);
  assert.ok(/^[0-9a-f]{64}$/.test(ballot.artifacts.output_sha256));
  assert.equal(judgeRun(dir).verdict, 'COMPLETE');
});

test('exec-seat: failing command -> cited veto with exit code, judged NOT_COMPLETE', () => {
  const dir = mkRun('exec-fail', EXEC_PANEL.map((s) => ({ ...s, seat_id: 'exec' })));
  const res = runNode([EXEC_SEAT, dir, 'exec', '--criterion', 'probe passes', '--',
    process.execPath, '-e', 'console.error("boom"); process.exit(3)']);
  assert.equal(res.status, 0, res.stderr);
  const ballot = JSON.parse(readFileSync(join(dir, 'ballots', 'exec.json'), 'utf8'));
  assert.equal(ballot.verdict, 'incomplete');
  assert.equal(ballot.artifacts.exit_code, 3);
  assert.equal(ballot.unmet[0].criterion, 'probe passes');
  assert.ok(ballot.unmet[0].evidence.includes('exited 3'), ballot.unmet[0].evidence);
  assert.ok(ballot.unmet[0].evidence.includes('boom'), ballot.unmet[0].evidence);
  assert.ok(existsSync(join(dir, 'raw', 'exec.out')));
  const verdict = judgeRun(dir);
  assert.equal(verdict.verdict, 'NOT_COMPLETE');
  assert.equal(verdict.work_queue.length, 1);
});

test('exec-seat: --expect nonzero inverts polarity', () => {
  const dir = mkRun('exec-invert', EXEC_PANEL.map((s) => ({ ...s, seat_id: 'exec' })));
  const res = runNode([EXEC_SEAT, dir, 'exec', '--expect', 'nonzero', '--',
    process.execPath, '-e', 'process.exit(1)']);
  assert.equal(res.status, 0, res.stderr);
  assert.equal(JSON.parse(readFileSync(join(dir, 'ballots', 'exec.json'), 'utf8')).verdict, 'complete');
});

test('rendered prompt carries the untrusted-content boundary, independence intact', () => {
  const seats = JSON.parse(readFileSync(join(TESTDATA, 'seats-mini.json'), 'utf8'));
  const prompt = renderPrompt(seats[0], '/tmp/none');
  assert.ok(prompt.includes('UNTRUSTED CONTENT BOUNDARY'), 'boundary missing');
  assert.deepEqual(checkPromptIndependence(prompt, seats[0].seat_id, seats), []);
});

test('log-verdict: appends a verdict line then an append-only label line', () => {
  const dir = copyRun('run-veto');
  assert.equal(runNode([JUDGE, dir]).status, 0);
  const stateDir = join(scratch, 'log-state');
  let res = runNode([LOG_VERDICT, dir, '--project', 'probe'], { QUORUM_STATE_DIR: stateDir });
  assert.equal(res.status, 0, res.stderr);
  const logPath = join(stateDir, 'verdicts.jsonl');
  let lines = readFileSync(logPath, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
  assert.equal(lines.length, 1);
  assert.equal(lines[0].kind, 'verdict');
  assert.equal(lines[0].verdict, 'NOT_COMPLETE');
  assert.equal(lines[0].project, 'probe');
  assert.ok(/^[0-9a-f]{16}$/.test(lines[0].run_id));
  res = runNode([LOG_VERDICT, '--label', lines[0].run_id, 'incorrect', '--note', 'checked by hand'], { QUORUM_STATE_DIR: stateDir });
  assert.equal(res.status, 0, res.stderr);
  lines = readFileSync(logPath, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
  assert.equal(lines.length, 2);
  assert.equal(lines[1].kind, 'label');
  assert.equal(lines[1].label, 'incorrect');
  assert.equal(lines[1].run_id, lines[0].run_id);
});

test('CLI entry guard survives a symlinked install path', () => {
  // The skill ships as a symlink (~/.claude/skills/quorum -> the repo), and
  // SKILL.md tells the agent to invoke scripts through that path. Comparing
  // unresolved argv[1] against the realpath-ed import.meta.url made main()
  // silently skip: exit 0, no verdict written.
  const linkDir = join(scratch, 'symlinked-scripts');
  symlinkSync(HARNESS, linkDir, 'dir');
  const dir = copyRun('run-veto');
  const res = runNode([join(linkDir, 'judge.mjs'), dir]);
  assert.equal(res.status, 0, res.stderr);
  assert.ok(res.stdout.includes('verdict: NOT_COMPLETE'), `no verdict on stdout: ${JSON.stringify(res.stdout)}`);
  assert.ok(existsSync(join(dir, 'verdict.json')), 'judge invoked via symlink wrote no verdict.json');
});

let failed = 0;
for (const [name, fn] of tests) {
  try {
    fn();
    console.error(`ok - ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`FAIL - ${name}\n${err.stack}`);
    break; // first failure is enough; keep output focused
  }
}
rmSync(scratch, { recursive: true, force: true });
if (failed > 0) {
  console.error(`${failed} test failed (${tests.length} total)`);
  process.exit(1);
}
console.log(`harness tests passed (${tests.length} tests)`);
