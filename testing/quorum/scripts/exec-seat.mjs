#!/usr/bin/env node
// exec-seat.mjs — a quorum seat whose ballot is grounded in EXECUTING a
// command rather than reading. Adopted from squad-quorum-design.md §2.3:
// only an execution that actually ran is evidence. The ballot always carries
// artifacts (exit code, output hash, duration) so a `requires_artifacts`
// panel seat accepts it; a failed execution is a cited veto, and a hung or
// unstartable one is an abstain (§2.10) — fail-closed either way under
// unanimity.
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
// combined output to <run-dir>/raw/<seat_id>.out. Exits 0 whenever a ballot
// was written (any verdict), 1 on usage error.

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { canonicalJson } from './judge.mjs';

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

mkdirSync(join(runDir, 'ballots'), { recursive: true });
mkdirSync(join(runDir, 'raw'), { recursive: true });
writeFileSync(join(runDir, 'raw', `${seatId}.out`), output);

const artifacts = {
  command: command.join(' '),
  duration_ms: durationMs,
  exit_code: exitCode,
  output_bytes: Buffer.byteLength(output),
  output_sha256: createHash('sha256').update(output).digest('hex'),
  timed_out: timedOut,
};
const firstLine = (output.split('\n').find((l) => l.trim().length > 0) ?? '').trim().slice(0, 200);

let ballot;
if (timedOut || spawnFailed) {
  ballot = {
    seat_id: seatId,
    jurisdiction: 'execution',
    verdict: 'abstain',
    unmet: [],
    evidence: [
      timedOut
        ? `execution timed out after ${timeout}ms`
        : `spawn failed: ${res.error.message}`,
    ],
    artifacts,
  };
} else {
  const met = expect === 'zero' ? exitCode === 0 : exitCode !== 0;
  ballot = met
    ? {
        seat_id: seatId,
        jurisdiction: 'execution',
        verdict: 'complete',
        unmet: [],
        evidence: [`${command.join(' ')} exited ${exitCode} (expected ${expect})`],
        artifacts,
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
        artifacts,
      };
}
writeFileSync(join(runDir, 'ballots', `${seatId}.json`), canonicalJson(ballot));
console.log(`exec-seat ${seatId}: ${ballot.verdict}`);
