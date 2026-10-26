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
import { checkPromptIndependence, COMPLETION_QUESTION, renderPrompt, validateSeats } from './render-prompts.mjs';
import { customDriverFrom, extractBallot, extractEnvelopeText, extractRawBallot, hasValidBallot, resolveDriver, SEAT_DRIVERS, stripFence, verifyDriverBin } from './run-seats.mjs';

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

test('protocol corruption: a panel with no required seat cannot pass vacuously', () => {
  const dir = mkRun('no-required', [{ jurisdiction: 'global', required: false, seat_id: 'skeptic' }]);
  assert.throws(() => judgeRun(dir), /no required seat/);
  const res = runNode([JUDGE, dir]);
  assert.equal(res.status, 2, `stdout=${res.stdout} stderr=${res.stderr}`);
  assert.ok(!existsSync(join(dir, 'verdict.json')), 'verdict.json must not be written on corruption');
});

test('protocol corruption: panel.json may not drop or demote a rendered seat', () => {
  const seats = JSON.parse(readFileSync(join(HARNESS, 'presets', 'completion-default.seats.json'), 'utf8'));
  const complete = (s) => ({ seat_id: s.seat_id, jurisdiction: s.jurisdiction, verdict: 'complete', unmet: [], evidence: ['x'] });
  const full = seats.map((s) => ({ jurisdiction: s.jurisdiction, seat_id: s.seat_id }));
  const withPrompts = (name, panel) => {
    const dir = mkRun(name, panel);
    assert.equal(runNode([RENDER, join(TESTDATA, 'fixture-mini'), join(HARNESS, 'presets', 'completion-default.seats.json'), join(dir, 'prompts')]).status, 0);
    return dir;
  };

  // skeptic stayed absent; quietly leaving it out of the panel must not yield COMPLETE.
  const dropped = withPrompts('rendered-dropped', full.filter((s) => s.seat_id !== 'skeptic'));
  for (const s of seats.filter((x) => x.seat_id !== 'skeptic')) {
    writeFileSync(join(dropped, 'ballots', `${s.seat_id}.json`), canonicalJson(complete(s)));
  }
  assert.throws(() => judgeRun(dropped), /omits rendered seat "skeptic"/);

  const demoted = withPrompts('rendered-demoted', full.map((s) => (s.seat_id === 'skeptic' ? { ...s, required: false } : s)));
  assert.throws(() => judgeRun(demoted), /marks rendered seat "skeptic" optional/);

  // Extra non-rendered seats (gates, exec seats) are fine alongside the rendered ones.
  const ok = withPrompts('rendered-ok', [{ jurisdiction: 'deterministic-checks', seat_id: 'gates' }, ...full]);
  writeFileSync(join(ok, 'ballots', 'gates.json'), canonicalJson({ seat_id: 'gates', jurisdiction: 'deterministic-checks', verdict: 'complete', unmet: [], evidence: ['x'] }));
  for (const s of seats) writeFileSync(join(ok, 'ballots', `${s.seat_id}.json`), canonicalJson(complete(s)));
  assert.equal(judgeRun(ok).verdict, 'COMPLETE');
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

test('resolveDriver honours QUORUM_SEAT_CLI, bin and model overrides', () => {
  const overridden = resolveDriver({ QUORUM_SEAT_CLI: 'claude', QUORUM_SEAT_BIN: '/opt/claude', QUORUM_SEAT_MODEL: 'opus' });
  assert.equal(overridden.driver.label, 'claude');
  assert.equal(overridden.bin, '/opt/claude');
  assert.equal(overridden.model, 'opus');

  assert.throws(() => resolveDriver({ QUORUM_SEAT_CLI: 'nope' }), /unknown QUORUM_SEAT_CLI/);
  // Auto-detect with nothing installed must fail loudly, not pick a missing binary.
  const savedPath = process.env.PATH;
  process.env.PATH = '';
  try {
    assert.throws(() => resolveDriver({}), /no seat CLI found/);
  } finally {
    process.env.PATH = savedPath;
  }
  // A bin override with no named driver would bind to whichever driver comes
  // first — reject it instead of guessing.
  assert.throws(() => resolveDriver({ QUORUM_SEAT_BIN: '/bin/sh' }), /QUORUM_SEAT_BIN is set but QUORUM_SEAT_CLI is not/);
});

test('resolveDriver auto-detects claude when its binary is on PATH, without running it', () => {
  const fakeBinDir = join(scratch, 'fake-bin');
  mkdirSync(fakeBinDir, { recursive: true });
  const ran = join(scratch, 'fake-bin-ran');
  writeFileSync(join(fakeBinDir, 'claude'), `#!/bin/sh\ntouch '${ran}'\necho "2.1.236 (Claude Code)"\n`, { mode: 0o755 });
  const savedPath = process.env.PATH;
  process.env.PATH = `${fakeBinDir}:${savedPath}`;
  try {
    const picked = resolveDriver({});
    assert.equal(picked.driver.label, 'claude');
    assert.equal(picked.bin, 'claude');
    assert.equal(picked.model, 'sonnet');
    assert.equal(picked.source, 'auto-detect');
    assert.ok(!existsSync(ran), 'resolveDriver must not spawn the binary; main() checks it once');
  } finally {
    process.env.PATH = savedPath;
  }
});

test('verifyDriverBin trips on leftover or naive claude stubs', () => {
  const stubDir = join(scratch, 'stub-bin');
  mkdirSync(stubDir, { recursive: true });
  const stub = (name, body) => {
    const path = join(stubDir, name);
    writeFileSync(path, body, { mode: 0o755 });
    return path;
  };

  const genuine = stub('claude-genuine', '#!/bin/sh\necho "2.1.236 (Claude Code)"\n');
  assert.equal(verifyDriverBin(SEAT_DRIVERS.claude, genuine), genuine);
  assert.throws(() => verifyDriverBin(SEAT_DRIVERS.claude, join(stubDir, 'missing')), /seat binary not found/);

  // Script with the ballot keys written into it.
  const staticStub = stub('claude-static-stub',
    '#!/usr/bin/env node\nconsole.log(JSON.stringify({ result: JSON.stringify({ seat_id: "skeptic", verdict: "complete" }) }));\n');
  assert.throws(() => verifyDriverBin(SEAT_DRIVERS.claude, staticStub), /refusing voter stub.*hardcoded ballot schema keys/);

  // --version answering with a JSON envelope (key split so the static check
  // does not fire first).
  const keyA = 'res' + 'ult';
  const envelopeStub = stub('claude-envelope-stub', `#!/bin/sh\necho '{"${keyA}": "fake ballot"}'\n`);
  assert.throws(() => verifyDriverBin(SEAT_DRIVERS.claude, envelopeStub), /refusing claude binary.*JSON ballot envelope/);

  const emptyStub = stub('claude-empty', '#!/bin/sh\nexit 0\n');
  assert.throws(() => verifyDriverBin(SEAT_DRIVERS.claude, emptyStub), /refusing broken or fake claude binary.*empty stdout/);

  const failingStub = stub('claude-failing', '#!/bin/sh\nexit 3\n');
  assert.throws(() => verifyDriverBin(SEAT_DRIVERS.claude, failingStub), /--version failed \(exited 3\)/);

  // Regression: a signal-killed probe has status null and no .error; it used
  // to crash with a TypeError instead of the named refusal.
  const killedStub = stub('claude-killed', '#!/bin/sh\nkill -9 $$\n');
  assert.throws(() => verifyDriverBin(SEAT_DRIVERS.claude, killedStub), /--version failed \(killed by SIGKILL\)/);
});

test('verifyDriverBin only checks existence for custom drivers', () => {
  const custom = customDriverFrom({ QUORUM_SEAT_ARGS: '["{prompt}"]' });
  // Regression: a legitimate wrapper that merely mentions the ballot keys was
  // refused as a spoofed stub.
  const wrapper = join(scratch, 'custom-wrapper.sh');
  writeFileSync(wrapper, '#!/bin/sh\n# Forwards to the real voter; its ballot carries seat_id and verdict.\nexit 1\n', { mode: 0o755 });
  assert.equal(verifyDriverBin(custom, wrapper), wrapper);
  assert.throws(() => verifyDriverBin(custom, join(scratch, 'no-such-voter')), /seat binary not found/);
});

function writeSeatDriver(name, config) {
  const stateDir = join(scratch, name);
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(join(stateDir, 'seat-driver.json'), typeof config === 'string' ? config : JSON.stringify(config));
  return stateDir;
}

test('resolveDriver reads seat-driver.json from stateDir; env wins per key', () => {
  const stateDir = writeSeatDriver('driver-state', {
    QUORUM_SEAT_CLI: 'custom',
    QUORUM_SEAT_BIN: '/opt/persistent-voter',
    QUORUM_SEAT_ARGS: '["-p", "{prompt}", "--add-dir", "{fixture_dir}"]',
    QUORUM_SEAT_RESULT_FIELD: 'response',
    QUORUM_SEAT_MODEL: 'file-model',
  });
  const configPath = join(stateDir, 'seat-driver.json');

  const picked = resolveDriver({}, { stateDir });
  assert.equal(picked.driver.label, 'custom');
  assert.equal(picked.bin, '/opt/persistent-voter');
  assert.equal(picked.driver.resultField, 'response');
  assert.equal(picked.model, 'file-model');
  assert.equal(picked.source, configPath);

  // A non-blank env value beats the file for that key; a blank one does not.
  const mixed = resolveDriver({ QUORUM_SEAT_MODEL: 'env-model', QUORUM_SEAT_BIN: ' ' }, { stateDir });
  assert.equal(mixed.model, 'env-model');
  assert.equal(mixed.bin, '/opt/persistent-voter');

  // QUORUM_SEAT_CLI in env skips the file entirely.
  const explicit = resolveDriver({ QUORUM_SEAT_CLI: 'claude', QUORUM_SEAT_BIN: '/opt/explicit-claude' }, { stateDir });
  assert.equal(explicit.driver.label, 'claude');
  assert.equal(explicit.bin, '/opt/explicit-claude');
  assert.equal(explicit.model, 'sonnet');
  assert.equal(explicit.source, 'QUORUM_SEAT_CLI');

  // Without a stateDir the file is never read, whatever the env holds.
  assert.throws(() => resolveDriver({ QUORUM_STATE_DIR: stateDir, QUORUM_SEAT_BIN: '/x' }), /QUORUM_SEAT_BIN is set but QUORUM_SEAT_CLI is not/);

  // QUORUM_SEAT_ARGS may be a native JSON array.
  const arrayArgs = resolveDriver({}, { stateDir: writeSeatDriver('driver-state-array', {
    QUORUM_SEAT_CLI: 'custom', QUORUM_SEAT_BIN: '/opt/v', QUORUM_SEAT_ARGS: ['ask', '{prompt}'],
  }) });
  assert.deepEqual(arrayArgs.driver.buildArgs('vote', '/f', ''), ['ask', 'vote']);

  // No file: falls through to the usual resolution.
  const none = resolveDriver({ QUORUM_SEAT_CLI: 'claude' }, { stateDir: join(scratch, 'no-state-here') });
  assert.equal(none.source, 'QUORUM_SEAT_CLI');
});

test('a malformed seat-driver.json fails with a named error', () => {
  const cases = [
    ['bad-json', '{not json', /invalid JSON in .*seat-driver\.json/],
    ['bad-array', '[]', /must contain a JSON object/],
    ['bad-key', { PATH: '/evil', QUORUM_SEAT_CLI: 'claude' }, /unexpected key "PATH"/],
    ['bad-value', { QUORUM_SEAT_CLI: 'custom', QUORUM_SEAT_BIN: 7 }, /QUORUM_SEAT_BIN must be a string$/],
    ['bad-scrub', { QUORUM_SEAT_SCRUB_ENV: ['A', 'B'] }, /QUORUM_SEAT_SCRUB_ENV must be a string$/],
    ['bad-args', { QUORUM_SEAT_ARGS: { a: 1 } }, /QUORUM_SEAT_ARGS must be a string or an array of strings/],
  ];
  for (const [name, config, pattern] of cases) {
    const stateDir = writeSeatDriver(`driver-${name}`, config);
    assert.throws(() => resolveDriver({}, { stateDir }), pattern, name);
  }
});

// A fake claude for main()-level tests. It logs each invocation's first arg
// and, past --version, prints a valid ballot envelope kept in a sibling file,
// so the script itself carries no ballot keys and is not refused as a stub.
function writeFakeClaude(dir, log) {
  mkdirSync(dir, { recursive: true });
  const ballot = { seat_id: 'alpha', jurisdiction: 'global', verdict: 'complete', unmet: [], evidence: ['e'], confidence: 1 };
  const envelope = join(dir, 'envelope.json');
  writeFileSync(envelope, JSON.stringify({ result: JSON.stringify(ballot) }));
  writeFileSync(join(dir, 'claude'), [
    '#!/bin/sh',
    `echo "$1" >> '${log}'`,
    'if [ "$1" = "--version" ]; then echo "2.1.236 (Claude Code)"; exit 0; fi',
    `cat '${envelope}'`,
    '',
  ].join('\n'), { mode: 0o755 });
}

function mkSeatPrompts(name) {
  const promptDir = join(scratch, name, 'prompts');
  mkdirSync(promptDir, { recursive: true });
  writeFileSync(join(promptDir, '_run.json'), canonicalJson({ fixture_dir: join(TESTDATA, 'fixture-mini') }));
  writeFileSync(join(promptDir, 'alpha.prompt.md'), 'vote please\n');
  return { promptDir, ballotsDir: join(scratch, name, 'ballots') };
}

const SEAT_ENV_CLEARED = {
  QUORUM_SEAT_CLI: '', QUORUM_SEAT_BIN: '', QUORUM_SEAT_MODEL: '', QUORUM_SEAT_ARGS: '',
  QUORUM_SEAT_RESULT_FIELD: '', QUORUM_SEAT_STATUS_FIELD: '', QUORUM_SEAT_STATUS_OK: '', QUORUM_SEAT_SCRUB_ENV: '',
};

test('run-seats checks the claude binary once, spawns it, and names the source', () => {
  const binDir = join(scratch, 'main-claude-bin');
  const log = join(scratch, 'main-claude.log');
  writeFakeClaude(binDir, log);
  const { promptDir, ballotsDir } = mkSeatPrompts('main-claude');
  const res = runNode([RUN_SEATS, promptDir, ballotsDir], {
    ...SEAT_ENV_CLEARED,
    QUORUM_STATE_DIR: join(scratch, 'main-claude-empty-state'),
    PATH: `${binDir}:${process.env.PATH}`,
  });
  assert.equal(res.status, 0, res.stderr);
  assert.ok(res.stdout.includes(`seat CLI: claude (${join(binDir, 'claude')}) model=sonnet [from auto-detect]`), res.stdout);
  assert.ok(existsSync(join(ballotsDir, 'alpha.json')), 'ballot not written');
  // Regression: --version used to be probed twice on auto-detect.
  assert.deepEqual(readFileSync(log, 'utf8').trim().split('\n'), ['--version', '-p']);
});

test('run-seats exits 1 on a refused claude stub and writes no ballot', () => {
  const binDir = join(scratch, 'main-stub-bin');
  mkdirSync(binDir, { recursive: true });
  writeFileSync(join(binDir, 'claude'), '#!/bin/sh\nexit 0\n', { mode: 0o755 });
  const { promptDir, ballotsDir } = mkSeatPrompts('main-stub');
  const res = runNode([RUN_SEATS, promptDir, ballotsDir], {
    ...SEAT_ENV_CLEARED,
    QUORUM_STATE_DIR: join(scratch, 'main-stub-empty-state'),
    PATH: `${binDir}:${process.env.PATH}`,
  });
  assert.equal(res.status, 1);
  assert.match(res.stderr, /refusing broken or fake claude binary.*empty stdout/);
  assert.ok(!existsSync(join(ballotsDir, 'alpha.json')), 'a refused seat must not produce a ballot');
});

test('run-seats loads ~/.claude/quorum-state/seat-driver.json by default and says so', () => {
  const home = join(scratch, 'fake-home');
  const binDir = join(scratch, 'main-custom-bin');
  writeFakeClaude(binDir, join(scratch, 'main-custom.log'));
  const stateDir = join(home, '.claude', 'quorum-state');
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(join(stateDir, 'seat-driver.json'), JSON.stringify({
    QUORUM_SEAT_CLI: 'custom',
    QUORUM_SEAT_BIN: join(binDir, 'claude'),
    QUORUM_SEAT_ARGS: ['-p', '{prompt}'],
  }));
  const { promptDir, ballotsDir } = mkSeatPrompts('main-custom');
  const res = runNode([RUN_SEATS, promptDir, ballotsDir], { ...SEAT_ENV_CLEARED, HOME: home, QUORUM_STATE_DIR: '' });
  assert.equal(res.status, 0, res.stderr);
  assert.ok(res.stdout.includes(`[from ${join(stateDir, 'seat-driver.json')}]`), res.stdout);
  assert.equal(JSON.parse(readFileSync(join(ballotsDir, 'alpha.json'), 'utf8')).verdict, 'complete');
});

test('custom driver is built from env and rejects a broken configuration', () => {
  assert.throws(() => resolveDriver({ QUORUM_SEAT_CLI: 'custom' }), /requires QUORUM_SEAT_BIN/);
  assert.throws(() => resolveDriver({ QUORUM_SEAT_CLI: 'custom', QUORUM_SEAT_BIN: '/opt/voter' }), /requires QUORUM_SEAT_ARGS/);
  assert.throws(() => customDriverFrom({ QUORUM_SEAT_ARGS: 'not json' }), /not valid JSON/);
  assert.throws(() => customDriverFrom({ QUORUM_SEAT_ARGS: '{"a":1}' }), /array of strings/);
  assert.throws(() => customDriverFrom({ QUORUM_SEAT_ARGS: '["--json"]' }), /"\{prompt\}"/);

  const picked = resolveDriver({
    QUORUM_SEAT_CLI: 'custom',
    QUORUM_SEAT_BIN: '/opt/voter',
    QUORUM_SEAT_ARGS: '["ask", "{prompt}", "--json", "--dir", "{fixture_dir}", "--model", "{model}"]',
    QUORUM_SEAT_MODEL: 'big-model',
    QUORUM_SEAT_SCRUB_ENV: 'VOTER_SESSION, VOTER_PARENT',
  });
  assert.equal(picked.driver.label, 'custom');
  assert.equal(picked.bin, '/opt/voter');
  assert.deepEqual(
    picked.driver.buildArgs('vote please', '/tmp/fixture', picked.model),
    ['ask', 'vote please', '--json', '--dir', '/tmp/fixture', '--model', 'big-model'],
  );
  // No model configured: drop the placeholder and its flag, never pass a blank.
  assert.deepEqual(
    picked.driver.buildArgs('vote please', '/tmp/fixture', ''),
    ['ask', 'vote please', '--json', '--dir', '/tmp/fixture'],
  );
  const env = { VOTER_SESSION: 'x', VOTER_PARENT: 'y', KEEP: 'z' };
  picked.driver.scrubEnv(env);
  assert.deepEqual(env, { KEEP: 'z' });
});

test('extractEnvelopeText recovers the envelope past a CLI setup banner', () => {
  const envelope = JSON.stringify({ response: 'hi' });
  assert.equal(extractEnvelopeText(envelope), envelope);
  assert.equal(extractEnvelopeText(`=== seat ready: /tmp/x ===\n${envelope}\n`), envelope);
  assert.equal(extractEnvelopeText('banner only, no json'), null);
  assert.equal(extractEnvelopeText(''), null);
  assert.equal(extractEnvelopeText('[1,2,3]'), null); // arrays are not envelopes
});

test('custom driver reads its result field and fails closed on a bad status', () => {
  const custom = customDriverFrom({
    QUORUM_SEAT_ARGS: '["{prompt}"]',
    QUORUM_SEAT_RESULT_FIELD: 'response',
    QUORUM_SEAT_STATUS_FIELD: 'status',
    QUORUM_SEAT_STATUS_OK: 'OK',
  });
  const ballot = { seat_id: 'alpha', jurisdiction: 'global', verdict: 'complete', unmet: [], evidence: ['e'], confidence: 1 };
  const ok = `=== seat ready: /tmp/x ===\n${JSON.stringify({ status: 'OK', response: JSON.stringify(ballot) })}`;
  assert.equal(extractBallot(ok, 'alpha', custom).ok, true);

  // A claude-shaped envelope has no .response — must not be silently accepted.
  assert.equal(extractBallot(JSON.stringify({ status: 'OK', result: JSON.stringify(ballot) }), 'alpha', custom).ok, false);

  const failed = extractBallot(JSON.stringify({ status: 'ERROR', response: JSON.stringify(ballot) }), 'alpha', custom);
  assert.equal(failed.ok, false);
  assert.match(failed.reason, /status "ERROR"/);
  // Missing status field is not success.
  assert.equal(extractBallot(JSON.stringify({ response: JSON.stringify(ballot) }), 'alpha', custom).ok, false);

  // Without a status field configured, only the result field decides.
  const plain = customDriverFrom({ QUORUM_SEAT_ARGS: '["{prompt}"]' });
  assert.equal(extractBallot(JSON.stringify({ result: JSON.stringify(ballot) }), 'alpha', plain).ok, true);
});

test('claude driver fails closed on an is_error envelope', () => {
  const failed = extractBallot(JSON.stringify({ is_error: true, result: 'API error 529' }), 'alpha');
  assert.equal(failed.ok, false);
  assert.match(failed.reason, /voter reported is_error/);
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

test('exec-seat: exit 126/127 never ran -> abstain under either polarity', () => {
  for (const expect of ['zero', 'nonzero']) {
    for (const code of [126, 127]) {
      const dir = mkRun(`exec-notrun-${expect}-${code}`, EXEC_PANEL.map((s) => ({ ...s, seat_id: 'exec' })));
      const res = runNode([EXEC_SEAT, dir, 'exec', '--expect', expect, '--',
        process.execPath, '-e', `console.error("nope: command not found"); process.exit(${code})`]);
      assert.equal(res.status, 0, res.stderr);
      const ballot = JSON.parse(readFileSync(join(dir, 'ballots', 'exec.json'), 'utf8'));
      assert.equal(ballot.verdict, 'abstain', `expect=${expect} exit=${code}`);
      assert.equal(ballot.artifacts.exit_code, code);
      assert.ok(ballot.evidence[0].includes('not found or not executable'), ballot.evidence[0]);
      assert.equal(judgeRun(dir).verdict, 'NOT_COMPLETE');
    }
  }
});

test('rendered prompt carries the untrusted-content boundary, independence intact', () => {
  const seats = JSON.parse(readFileSync(join(TESTDATA, 'seats-mini.json'), 'utf8'));
  const prompt = renderPrompt(seats[0], '/tmp/none');
  assert.ok(prompt.includes('UNTRUSTED CONTENT BOUNDARY'), 'boundary missing');
  assert.ok(prompt.includes('You are read-only'), 'read-only instruction missing');
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

test('all 3-seat presets validate, enforce veto-scope rule, and render independent prompts', () => {
  const presetsDir = join(HARNESS, 'presets');
  const fixtureDir = join(TESTDATA, 'fixture-mini');
  const presetNames = [
    'completion-default.seats.json',
    'tradeoff-evaluation.seats.json',
    'finding-validation.seats.json',
  ];
  for (const name of presetNames) {
    const presetPath = join(presetsDir, name);
    const seats = JSON.parse(readFileSync(presetPath, 'utf8'));
    validateSeats(seats);
    assert.equal(seats.length, 3, `${name} must define a 3-seat subagent panel`);
    for (const seat of seats) {
      assert.ok(
        seat.persona.includes("A veto must cite an acceptance criterion's required artifact"),
        `${name} seat ${seat.seat_id} missing veto-scope rule`,
      );
    }
    const outDir = join(scratch, `preset-${name}`);
    const res = runNode([RENDER, fixtureDir, presetPath, outDir]);
    assert.equal(res.status, 0, `${name} render failed: ${res.stderr}`);
    for (const seat of seats) {
      const prompt = readFileSync(join(outDir, `${seat.seat_id}.prompt.md`), 'utf8');
      assert.deepEqual(checkPromptIndependence(prompt, seat.seat_id, seats), [], `${name} prompt independence failed for ${seat.seat_id}`);
    }
  }
});

test('extractRawBallot accepts bare/fenced subagent JSON and CLI envelopes, rejects prose', () => {
  const ballot = { seat_id: 'skeptic', jurisdiction: 'global', verdict: 'complete', unmet: [], evidence: ['ok'], confidence: 0.9 };
  assert.equal(extractRawBallot(JSON.stringify(ballot), 'skeptic').ok, true);
  assert.equal(extractRawBallot('```json\n' + JSON.stringify(ballot) + '\n```', 'skeptic').ok, true);
  assert.equal(extractRawBallot(JSON.stringify({ result: JSON.stringify(ballot) }), 'skeptic').ok, true);
  assert.equal(extractRawBallot(JSON.stringify(ballot), 'correctness').ok, false);
  assert.equal(extractRawBallot('I checked everything and it is complete.', 'skeptic').ok, false);
  assert.equal(extractRawBallot('', 'skeptic').ok, false);
});

test('run-seats --from-raw, --seat, and --missing-only support parallel subagents and selective re-ask', () => {
  const promptDir = join(scratch, 'subagent-prompts');
  const runDir = join(scratch, 'subagent-run');
  const ballotsDir = join(runDir, 'ballots');
  const rawDir = join(runDir, 'raw');
  const fixtureDir = join(TESTDATA, 'fixture-mini');
  const presetPath = join(HARNESS, 'presets', 'completion-default.seats.json');
  assert.equal(runNode([RENDER, fixtureDir, presetPath, promptDir]).status, 0);
  mkdirSync(rawDir, { recursive: true });

  const skepticBallot = { seat_id: 'skeptic', jurisdiction: 'global', verdict: 'complete', unmet: [], evidence: ['main.go:1'], confidence: 0.9 };
  const correctnessBallot = { seat_id: 'correctness', jurisdiction: 'correctness', verdict: 'complete', unmet: [], evidence: ['main_test.go:1'], confidence: 0.95 };
  writeFileSync(join(rawDir, 'skeptic.txt'), '```json\n' + JSON.stringify(skepticBallot, null, 2) + '\n```\n');
  writeFileSync(join(rawDir, 'correctness.txt'), JSON.stringify(correctnessBallot));
  writeFileSync(join(rawDir, 'spec-coverage.txt'), 'Looks complete to me, all tests pass!');

  // First pass: --from-raw with PATH cleared proves no CLI binary is required.
  const first = runNode([RUN_SEATS, promptDir, ballotsDir, '--from-raw'], { PATH: '' });
  assert.equal(first.status, 0, first.stderr);
  assert.equal(hasValidBallot(ballotsDir, 'skeptic'), true);
  assert.equal(hasValidBallot(ballotsDir, 'correctness'), true);
  assert.equal(hasValidBallot(ballotsDir, 'spec-coverage'), false);

  // Unknown --seat fails with exit 1.
  const badSeat = runNode([RUN_SEATS, promptDir, ballotsDir, '--from-raw', '--seat', 'nonexistent'], { PATH: '' });
  assert.equal(badSeat.status, 1);

  // Selective re-ask: update raw/spec-coverage.txt and run --from-raw --missing-only.
  const specBallot = { seat_id: 'spec-coverage', jurisdiction: 'spec-coverage', verdict: 'complete', unmet: [], evidence: ['main_test.go:10'], confidence: 0.9 };
  writeFileSync(join(rawDir, 'spec-coverage.txt'), JSON.stringify(specBallot));
  const reask = runNode([RUN_SEATS, promptDir, ballotsDir, '--from-raw', '--missing-only'], { PATH: '' });
  assert.equal(reask.status, 0, reask.stderr);
  assert.ok(reask.stdout.includes('spec-coverage: ballot: complete'), reask.stdout);
  assert.ok(!reask.stdout.includes('skeptic:'), 'already-valid skeptic ballot must not be re-processed');
  assert.equal(hasValidBallot(ballotsDir, 'spec-coverage'), true);

  // When all seats have valid ballots, --missing-only is a no-op and exits 0.
  const noop = runNode([RUN_SEATS, promptDir, ballotsDir, '--missing-only'], { PATH: '' });
  assert.equal(noop.status, 0, noop.stderr);
  assert.ok(noop.stdout.includes('all selected seats already have valid ballots'), noop.stdout);
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
