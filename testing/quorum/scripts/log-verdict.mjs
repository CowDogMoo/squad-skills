#!/usr/bin/env node
// log-verdict.mjs — append-only outcome log for /quorum verdicts. Adopted
// from squad-quorum-design.md §2.8: recorded verdicts plus later human
// labels are the only honest way to ever calibrate seats empirically instead
// of guessing. Append-only: labels are correction lines, never rewrites.
//
// Append: node log-verdict.mjs <run-dir> [--project <name>]
// Label:  node log-verdict.mjs --label <run_id> correct|incorrect|unsure [--note "<text>"]
// Log file: $QUORUM_STATE_DIR/verdicts.jsonl (default ~/.claude/quorum-state/).
// The default deliberately lives OUTSIDE the skill directory: the skill is a
// symlink into a git repo, and run history is local state, not source.

import { mkdirSync, readFileSync, appendFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve, basename } from 'node:path';
import { createHash } from 'node:crypto';

const stateDir = process.env.QUORUM_STATE_DIR || join(homedir(), '.claude/quorum-state');
mkdirSync(stateDir, { recursive: true });
const logPath = join(stateDir, 'verdicts.jsonl');
const argv = process.argv.slice(2);
const die = (m) => { console.error(`log-verdict: ${m}`); process.exit(1); };

if (argv[0] === '--label') {
  const runId = argv[1];
  const label = argv[2];
  if (!runId || !['correct', 'incorrect', 'unsure'].includes(label)) {
    die('usage: log-verdict.mjs --label <run_id> correct|incorrect|unsure [--note "<text>"]');
  }
  const noteIdx = argv.indexOf('--note');
  const record = {
    kind: 'label',
    label,
    note: noteIdx === -1 ? null : argv[noteIdx + 1] ?? null,
    run_id: runId,
    ts: new Date().toISOString(),
  };
  appendFileSync(logPath, `${JSON.stringify(record)}\n`);
  console.log(`labeled ${runId}: ${label}`);
  process.exit(0);
}

const runDir = argv[0];
if (!runDir || runDir.startsWith('--')) die('usage: log-verdict.mjs <run-dir> [--project <name>] | --label <run_id> <label>');
const projIdx = argv.indexOf('--project');
const project = projIdx === -1 ? basename(process.cwd()) : argv[projIdx + 1] ?? die('--project needs a value');
let verdictBytes;
let verdict;
try {
  verdictBytes = readFileSync(join(runDir, 'verdict.json'));
  verdict = JSON.parse(verdictBytes.toString('utf8'));
} catch (err) {
  die(`cannot read verdict.json in ${runDir}: ${err.message}`);
}
const runId = createHash('sha256').update(verdictBytes).update(resolve(runDir)).digest('hex').slice(0, 16);
const record = {
  kind: 'verdict',
  label: null,
  project,
  run_dir: resolve(runDir),
  run_id: runId,
  seats: verdict.seats.map((s) => ({ seat_id: s.seat_id, state: s.state })),
  ts: new Date().toISOString(),
  verdict: verdict.verdict,
};
appendFileSync(logPath, `${JSON.stringify(record)}\n`);
console.log(`logged ${runId}: ${verdict.verdict}`);
