#!/usr/bin/env node
// run-seats.mjs — invoke one voter per rendered prompt and collect ballots.
//
// Usage: node run-seats.mjs <prompt-dir> <ballots-out-dir> [--dry-run]
//   <prompt-dir>/<seat_id>.prompt.md   rendered prompts (render-prompts.mjs)
//   <prompt-dir>/_run.json             {fixture_dir} — the staged fixture the
//                                      voter is granted via --add-dir/cwd
// Writes ballots to <ballots-out-dir>/<seat_id>.json and every raw envelope
// (always, even partial/timeout output) to <ballots-out-dir>/../raw/<seat_id>.json.
//
// Voter invocation (equivalent of the A3-proven shell recipe
//   env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT claude -p "$(cat promptfile)" \
//     --model sonnet --output-format json --strict-mcp-config \
//     --setting-sources user --allowedTools Read Grep Glob \
//     --add-dir <staged-fixture-dir>
// ): spawn("claude", args) with CLAUDECODE and CLAUDE_CODE_ENTRYPOINT removed
// from the child env, cwd set to the staged fixture dir.
// [cmd] verified against `claude --help` on claude 2.1.236 (2026-09-04):
// -p/--print, --model, --output-format <json>, --strict-mcp-config,
// --setting-sources <sources>, --allowedTools <tools...>, --add-dir
// <directories...> all present — the A3 recipe works unchanged; no flag
// corrections needed.
//
// Failure handling per seat: timeout (300s) or hang => kill, NO ballot file
// (judge sees absent). Envelope unparsable / .result missing / ballot JSON
// invalid => NO ballot file (judge sees absent), raw envelope saved for the
// post-mortem. A ballot file is written only for a schema-valid ballot.
//
// --dry-run skips the claude CLI call (for tests): each seat's envelope is
// read from <prompt-dir>/dryrun/<seat_id>.envelope.json when present
// (exercising the full extraction/validation path), otherwise the seat is
// treated as absent.

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { realpathSync } from 'node:fs';

// True when this module is the script node was invoked with, comparing
// realpaths so a symlinked install still runs its CLI main().
function isMainScript(argvPath, moduleUrl) {
  const real = (p) => { try { return realpathSync(p); } catch { return resolve(p); } };
  return real(argvPath) === real(fileURLToPath(moduleUrl));
}
import { canonicalJson, validateBallot } from './judge.mjs';

export const MAX_CONCURRENT = 4;
export const SEAT_TIMEOUT_MS = 300_000;
const PROMPT_SUFFIX = '.prompt.md';

export function buildSeatArgs(promptText, fixtureDir) {
  return [
    '-p', promptText,
    '--model', 'sonnet',
    '--output-format', 'json',
    '--strict-mcp-config',
    '--setting-sources', 'user',
    '--allowedTools', 'Read', 'Grep', 'Glob',
    '--add-dir', fixtureDir,
  ];
}

// Strip at most one surrounding markdown code fence (```json ... ``` or bare).
export function stripFence(text) {
  const trimmed = text.trim();
  const match = trimmed.match(/^```[A-Za-z0-9_-]*[ \t]*\r?\n([\s\S]*?)\r?\n?```$/);
  return match ? match[1].trim() : trimmed;
}

// Parse a claude --output-format json envelope, pull the ballot JSON out of
// .result, and validate it. Returns {ok: true, ballot} or {ok: false, reason}.
export function extractBallot(envelopeText, expectedSeatId) {
  let envelope;
  try {
    envelope = JSON.parse(envelopeText);
  } catch (err) {
    return { ok: false, reason: `envelope is not JSON: ${err.message}` };
  }
  const result = envelope === null || typeof envelope !== 'object' ? undefined : envelope.result;
  if (typeof result !== 'string') {
    return { ok: false, reason: 'envelope has no string .result field' };
  }
  let ballot;
  try {
    ballot = JSON.parse(stripFence(result));
  } catch (err) {
    return { ok: false, reason: `.result does not contain ballot JSON: ${err.message}` };
  }
  const { valid, errors } = validateBallot(ballot, expectedSeatId);
  if (!valid) {
    return { ok: false, reason: `ballot schema-invalid: ${errors.join('; ')}` };
  }
  return { ok: true, ballot };
}

function invokeClaude(promptText, fixtureDir) {
  return new Promise((resolvePromise) => {
    const env = { ...process.env };
    delete env.CLAUDECODE; // equivalent of env -u CLAUDECODE
    delete env.CLAUDE_CODE_ENTRYPOINT; // equivalent of env -u CLAUDE_CODE_ENTRYPOINT
    const child = spawn('claude', buildSeatArgs(promptText, fixtureDir), {
      cwd: fixtureDir,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill('SIGKILL'); // hang => kill => no ballot file => judge sees absent
    }, SEAT_TIMEOUT_MS);
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', (err) => {
      clearTimeout(timer);
      resolvePromise({ stdout, stderr: `${stderr}\nspawn error: ${err.message}`, code: null, timedOut });
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      resolvePromise({ stdout, stderr, code, timedOut });
    });
  });
}

async function runSeat({ seatId, promptPath, promptDir, fixtureDir, ballotsDir, rawDir, dryRun }) {
  let envelopeText = null;
  let note = '';
  if (dryRun) {
    const staged = join(promptDir, 'dryrun', `${seatId}.envelope.json`);
    if (existsSync(staged)) {
      envelopeText = readFileSync(staged, 'utf8');
      note = 'dry-run (staged envelope)';
    } else {
      note = 'dry-run (no staged envelope, seat absent)';
    }
  } else {
    const promptText = readFileSync(promptPath, 'utf8');
    const { stdout, stderr, code, timedOut } = await invokeClaude(promptText, fixtureDir);
    envelopeText = stdout.length > 0 ? stdout : null;
    if (timedOut) note = `timed out after ${SEAT_TIMEOUT_MS / 1000}s, killed`;
    else if (code !== 0) note = `claude exited ${code}: ${stderr.trim().slice(0, 300)}`;
  }

  // Save every raw envelope always — even partial output from a killed seat.
  if (envelopeText !== null) {
    writeFileSync(join(rawDir, `${seatId}.json`), envelopeText);
  }

  if (envelopeText === null) {
    return { seatId, outcome: `absent: no output (${note || 'empty stdout'})` };
  }
  const extracted = extractBallot(envelopeText, seatId);
  if (!extracted.ok) {
    // Write NOTHING to ballots/ — the judge sees absent; raw/ has the evidence.
    return { seatId, outcome: `absent: ${extracted.reason}${note ? ` [${note}]` : ''}` };
  }
  writeFileSync(join(ballotsDir, `${seatId}.json`), canonicalJson(extracted.ballot));
  return { seatId, outcome: `ballot: ${extracted.ballot.verdict}${note ? ` [${note}]` : ''}` };
}

async function runPool(tasks, width) {
  const results = [];
  let next = 0;
  async function worker() {
    while (next < tasks.length) {
      const index = next;
      next += 1;
      results[index] = await tasks[index]();
    }
  }
  await Promise.all(Array.from({ length: Math.min(width, tasks.length) }, worker));
  return results;
}

async function main(argv) {
  const positional = argv.slice(2).filter((a) => a !== '--dry-run');
  const dryRun = argv.includes('--dry-run');
  const [promptDirArg, ballotsOutArg] = positional;
  if (!promptDirArg || !ballotsOutArg) {
    console.error('usage: node run-seats.mjs <prompt-dir> <ballots-out-dir> [--dry-run]');
    process.exit(1);
  }
  const promptDir = resolve(promptDirArg);
  const ballotsDir = resolve(ballotsOutArg);
  const rawDir = join(dirname(ballotsDir), 'raw');
  const runMeta = JSON.parse(readFileSync(join(promptDir, '_run.json'), 'utf8'));
  const fixtureDir = runMeta.fixture_dir;
  if (typeof fixtureDir !== 'string' || fixtureDir.length === 0) {
    console.error('_run.json must contain a non-empty fixture_dir');
    process.exit(1);
  }
  mkdirSync(ballotsDir, { recursive: true });
  mkdirSync(rawDir, { recursive: true });

  const promptFiles = readdirSync(promptDir)
    .filter((name) => name.endsWith(PROMPT_SUFFIX))
    .sort();
  if (promptFiles.length === 0) {
    console.error(`no ${PROMPT_SUFFIX} files in ${promptDir}`);
    process.exit(1);
  }
  if (dryRun) {
    console.log(`dry-run: skipping CLI; would invoke per seat: env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT claude ${buildSeatArgs('<prompt>', fixtureDir).join(' ')}`);
  }
  const tasks = promptFiles.map((name) => () =>
    runSeat({
      seatId: basename(name, PROMPT_SUFFIX),
      promptPath: join(promptDir, name),
      promptDir,
      fixtureDir,
      ballotsDir,
      rawDir,
      dryRun,
    }));
  const results = await runPool(tasks, MAX_CONCURRENT);
  for (const { seatId, outcome } of results) console.log(`${seatId}: ${outcome}`);
}

// Entry guard via realpath: this skill is installed as a symlink, so
// argv[1] can be the symlinked path while import.meta.url is realpath-ed.
// Comparing unresolved paths would silently skip main().
if (process.argv[1] && isMainScript(process.argv[1], import.meta.url)) {
  await main(process.argv);
}
