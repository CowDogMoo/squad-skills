#!/usr/bin/env node
// exec-seat.mjs — a quorum seat whose ballot is grounded in EXECUTING a
// command rather than reading. Adopted from squad-quorum-design.md §2.3:
// only an execution that actually ran is evidence. The ballot always carries
// artifacts (exit code, output hash, duration) so a `requires_artifacts`
// panel seat accepts it; a failed execution is a cited veto, and a hung or
// unstartable one is an abstain (§2.10) — fail-closed either way under
// unanimity. Exit 126/127 (a shell wrapper's "cannot execute" / "command not
// found") counts as unstartable, so a typo can't pass as a reproduction under
// --expect nonzero.
//
// Usage:
//   node exec-seat.mjs <run-dir> <seat_id> [options] -- <command> [args...]
// Options:
//   --criterion "<text>"   acceptance criterion this execution decides
//                          (default: "execution check passes: <command>")
//   --cwd <dir>            working directory for the command (default: cwd)
//   --timeout <ms>         kill after this long; verdict becomes "abstain"
//                          with timed_out artifacts (default 300000)
//   --expect zero|nonzero  which exit class means the criterion is met
//                          (default zero; use nonzero when the command is a
//                          reproduction that MUST fail for the task to count
//                          as complete)
//
// Writes <run-dir>/ballots/<seat_id>.json (canonical JSON) and the raw
// combined output to <run-dir>/raw/<seat_id>.out. Multiple calls on the same
// <run-dir> and <seat_id> accumulate checks into a single ballot (any
// "incomplete" check keeps the seat "incomplete" with all failing criteria
// preserved; else any "abstain" keeps it "abstain"; else "complete"). Exits 0
// whenever a ballot was written (any verdict), 1 on usage or corrupt-prior-ballot
// error.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { canonicalJson, validateBallot } from './judge.mjs';

function usage(msg) {
  console.error(`exec-seat: ${msg}`);
  process.exit(1);
}

const argv = process.argv.slice(2);
const sep = argv.indexOf('--');
if (sep === -1) usage('missing "--" before the command');
const head = argv.slice(0, sep);
const command = argv.slice(sep + 1);
if (head.length < 2) usage('usage: exec-seat.mjs <run-dir> <seat_id> [options] -- <command> [args...]');
if (command.length === 0) usage('empty command after "--"');
const [runDir, seatId] = head;

let criterion = `execution check passes: ${command.join(' ')}`;
let cwd = process.cwd();
let timeout = 300000;
let expect = 'zero';
for (let i = 2; i < head.length; i += 2) {
  const flag = head[i];
  const value = head[i + 1];
  if (value === undefined) usage(`flag ${flag} needs a value`);
  if (flag === '--criterion') criterion = value;
  else if (flag === '--cwd') cwd = value;
  else if (flag === '--timeout') timeout = Number(value);
  else if (flag === '--expect') expect = value;
  else usage(`unknown flag ${flag}`);
}
if (!['zero', 'nonzero'].includes(expect)) usage('--expect must be zero or nonzero');
if (!Number.isFinite(timeout) || timeout <= 0) usage('--timeout must be a positive number of ms');

const ballotPath = join(runDir, 'ballots', `${seatId}.json`);
const rawOutPath = join(runDir, 'raw', `${seatId}.out`);
let prior = null;
if (existsSync(ballotPath)) {
  let parsed;
  try {
    parsed = JSON.parse(readFileSync(ballotPath, 'utf8'));
  } catch (err) {
    usage(`existing ballot ${ballotPath} is unparsable (${err.message}); start a fresh run directory`);
  }
  const check = validateBallot(parsed, seatId);
  if (!check.valid) {
    usage(`existing ballot ${ballotPath} is schema-invalid (${check.errors.join('; ')}); start a fresh run directory`);
  }
  prior = parsed;
}

const started = Date.now();
const res = spawnSync(command[0], command.slice(1), {
  cwd,
  timeout,
  encoding: 'utf8',
  maxBuffer: 8 * 1024 * 1024,
});
const durationMs = Date.now() - started;
const output = `${res.stdout ?? ''}${res.stderr ?? ''}`;
const timedOut = res.error?.code === 'ETIMEDOUT';
const spawnFailed = Boolean(res.error) && !timedOut;
const exitCode = typeof res.status === 'number' ? res.status : -1;
const notExecutable = exitCode === 126 || exitCode === 127;

mkdirSync(join(runDir, 'ballots'), { recursive: true });
mkdirSync(join(runDir, 'raw'), { recursive: true });

const priorOutput = prior !== null && existsSync(rawOutPath) ? readFileSync(rawOutPath, 'utf8') : '';
const combinedOutput =
  prior !== null && priorOutput.length > 0
    ? `${priorOutput}${priorOutput.endsWith('\n') ? '' : '\n'}--- exec-seat check ---\n${output}`
    : output;
writeFileSync(rawOutPath, combinedOutput);

const singleArtifacts = {
  command: command.join(' '),
  duration_ms: durationMs,
  exit_code: exitCode,
  output_bytes: Buffer.byteLength(output),
  output_sha256: createHash('sha256').update(output).digest('hex'),
  timed_out: timedOut,
};
const firstLine = (output.split('\n').find((l) => l.trim().length > 0) ?? '').trim().slice(0, 200);

let singleBallot;
if (timedOut || spawnFailed || notExecutable) {
  let why;
  if (timedOut) why = `execution timed out after ${timeout}ms`;
  else if (spawnFailed) why = `spawn failed: ${res.error.message}`;
  else why = `${command.join(' ')} exited ${exitCode} (command not found or not executable)${firstLine ? `: ${firstLine}` : ''}`;
  singleBallot = {
    seat_id: seatId,
    jurisdiction: 'execution',
    verdict: 'abstain',
    unmet: [],
    evidence: [why],
    artifacts: singleArtifacts,
  };
} else {
  const met = expect === 'zero' ? exitCode === 0 : exitCode !== 0;
  singleBallot = met
    ? {
        seat_id: seatId,
        jurisdiction: 'execution',
        verdict: 'complete',
        unmet: [],
        evidence: [`${command.join(' ')} exited ${exitCode} (expected ${expect})`],
        artifacts: singleArtifacts,
      }
    : {
        seat_id: seatId,
        jurisdiction: 'execution',
        verdict: 'incomplete',
        unmet: [
          {
            criterion,
            evidence: `${command.join(' ')} exited ${exitCode}${firstLine ? `: ${firstLine}` : ''}`,
          },
        ],
        evidence: [],
        artifacts: singleArtifacts,
      };
}

let ballot = singleBallot;
if (prior !== null) {
  const priorArt = prior.artifacts && typeof prior.artifacts === 'object' ? prior.artifacts : {};
  const prevChecks = typeof priorArt.checks_run === 'number' && priorArt.checks_run >= 1 ? priorArt.checks_run : 1;
  const checksRun = prevChecks + 1;
  const perCheck = {};
  for (const [key, val] of Object.entries(priorArt)) {
    if (key.startsWith('check_')) perCheck[key] = val;
  }
  if (prevChecks === 1 && typeof priorArt.command === 'string') {
    perCheck.check_1_command = priorArt.command;
    if (typeof priorArt.exit_code === 'number') perCheck.check_1_exit_code = priorArt.exit_code;
    if (typeof priorArt.timed_out === 'boolean') perCheck.check_1_timed_out = priorArt.timed_out;
  }
  perCheck[`check_${checksRun}_command`] = command.join(' ');
  perCheck[`check_${checksRun}_exit_code`] = exitCode;
  perCheck[`check_${checksRun}_timed_out`] = timedOut;

  const mergedExitCode =
    singleBallot.verdict !== 'complete'
      ? exitCode
      : prior.verdict !== 'complete' && typeof priorArt.exit_code === 'number'
        ? priorArt.exit_code
        : exitCode;

  const mergedArtifacts = {
    ...perCheck,
    checks_run: checksRun,
    command: typeof priorArt.command === 'string' ? `${priorArt.command} && ${command.join(' ')}` : command.join(' '),
    duration_ms: (typeof priorArt.duration_ms === 'number' ? priorArt.duration_ms : 0) + durationMs,
    exit_code: mergedExitCode,
    output_bytes: Buffer.byteLength(combinedOutput),
    output_sha256: createHash('sha256').update(combinedOutput).digest('hex'),
    timed_out: Boolean(priorArt.timed_out) || timedOut,
  };

  let mergedVerdict = 'complete';
  if (prior.verdict === 'incomplete' || singleBallot.verdict === 'incomplete') {
    mergedVerdict = 'incomplete';
  } else if (prior.verdict === 'abstain' || singleBallot.verdict === 'abstain') {
    mergedVerdict = 'abstain';
  }

  ballot = {
    seat_id: seatId,
    jurisdiction: prior.jurisdiction || 'execution',
    verdict: mergedVerdict,
    unmet: mergedVerdict === 'incomplete' ? [...(prior.unmet ?? []), ...singleBallot.unmet] : [],
    evidence: [...(prior.evidence ?? []), ...singleBallot.evidence],
    artifacts: mergedArtifacts,
  };
}

writeFileSync(ballotPath, canonicalJson(ballot));
console.log(`exec-seat ${seatId}: ${ballot.verdict}`);
