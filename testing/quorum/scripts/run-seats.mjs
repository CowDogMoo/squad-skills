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
// Voter invocation is driver-based, so the gate is not tied to one vendor CLI.
// Select with QUORUM_SEAT_CLI=claude|custom; when unset, claude is used if its
// binary is on PATH. QUORUM_SEAT_BIN overrides the binary path (requires
// QUORUM_SEAT_CLI) and QUORUM_SEAT_MODEL overrides the model.
//
// claude driver (the A3-proven shell recipe
//   env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT claude -p "$(cat promptfile)" \
//     --model sonnet --output-format json --strict-mcp-config \
//     --setting-sources user --allowedTools Read Grep Glob \
//     --add-dir <staged-fixture-dir>
// ): spawn("claude", args) with CLAUDECODE and CLAUDE_CODE_ENTRYPOINT removed
// from the child env, cwd set to the staged fixture dir. Result text is the
// envelope's .result string; .is_error === true is a reported failure.
// [cmd] verified against `claude --help` on claude 2.1.236 (2026-09-04):
// -p/--print, --model, --output-format <json>, --strict-mcp-config,
// --setting-sources <sources>, --allowedTools <tools...>, --add-dir
// <directories...> all present — the A3 recipe works unchanged; no flag
// corrections needed.
//
// custom driver: any other CLI that prints one JSON envelope on stdout. It is
// configured entirely from the environment so no vendor-specific argv lives
// in this file:
//   QUORUM_SEAT_BIN           binary path (required)
//   QUORUM_SEAT_ARGS          JSON array of argv; an element equal to
//                             {prompt}, {fixture_dir} or {model} is replaced
//                             (required; must reference {prompt})
//   QUORUM_SEAT_RESULT_FIELD  envelope key holding the voter's text (default
//                             "result")
//   QUORUM_SEAT_STATUS_FIELD  optional envelope key; when set, the seat fails
//                             closed unless its value equals
//                             QUORUM_SEAT_STATUS_OK (default "SUCCESS")
//   QUORUM_SEAT_SCRUB_ENV     comma-separated env vars removed from the child
// It is the operator's job to make a custom seat read-only and independent
// of the calling conversation; the harness cannot verify that for a CLI it
// does not know. A setup banner printed before the JSON is tolerated.
//
// Failure handling per seat: timeout (300s) or hang => kill, NO ballot file
// (judge sees absent). Envelope unparsable / result field missing / ballot JSON
// invalid => NO ballot file (judge sees absent), raw envelope saved for the
// post-mortem. A ballot file is written only for a schema-valid ballot.
//
// --dry-run skips the CLI call (for tests): each seat's envelope is
// read from <prompt-dir>/dryrun/<seat_id>.envelope.json when present
// (exercising the full extraction/validation path), otherwise the seat is
// treated as absent.

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { basename, delimiter, dirname, join, resolve } from 'node:path';
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

// A seat driver adapts one vendor CLI to the harness contract: how to build
// argv, how to sanitise the child env, and how to find the voter's final text
// in that CLI's JSON envelope.
export const SEAT_DRIVERS = {
  claude: {
    label: 'claude',
    defaultBin: 'claude',
    defaultModel: 'sonnet',
    resultField: 'result',
    autoDetect: true,
    buildArgs(promptText, fixtureDir, model) {
      return [
        '-p', promptText,
        '--model', model,
        '--output-format', 'json',
        '--strict-mcp-config',
        '--setting-sources', 'user',
        '--allowedTools', 'Read', 'Grep', 'Glob',
        '--add-dir', fixtureDir,
      ];
    },
    scrubEnv(env) {
      delete env.CLAUDECODE; // equivalent of env -u CLAUDECODE
      delete env.CLAUDE_CODE_ENTRYPOINT; // equivalent of env -u CLAUDE_CODE_ENTRYPOINT
    },
    resultFrom(envelope) {
      return typeof envelope.result === 'string' ? envelope.result : undefined;
    },
    failureFrom(envelope) {
      return envelope.is_error === true ? 'is_error' : null;
    },
  },
};

const CUSTOM_PLACEHOLDERS = ['{prompt}', '{fixture_dir}', '{model}'];

// Build the custom driver from the environment. Throws on a missing or
// malformed setting so a misconfigured seat fails at startup, not at judge time.
export function customDriverFrom(env) {
  const rawArgs = (env.QUORUM_SEAT_ARGS || '').trim();
  if (!rawArgs) throw new Error('QUORUM_SEAT_CLI=custom requires QUORUM_SEAT_ARGS (a JSON array of argv)');
  let template;
  try {
    template = JSON.parse(rawArgs);
  } catch (err) {
    throw new Error(`QUORUM_SEAT_ARGS is not valid JSON: ${err.message}`);
  }
  if (!Array.isArray(template) || !template.every((a) => typeof a === 'string')) {
    throw new Error('QUORUM_SEAT_ARGS must be a JSON array of strings');
  }
  if (!template.includes('{prompt}')) {
    throw new Error('QUORUM_SEAT_ARGS must contain a "{prompt}" element so the seat receives its prompt');
  }
  const resultField = (env.QUORUM_SEAT_RESULT_FIELD || '').trim() || 'result';
  const statusField = (env.QUORUM_SEAT_STATUS_FIELD || '').trim();
  const statusOk = (env.QUORUM_SEAT_STATUS_OK || '').trim() || 'SUCCESS';
  const scrub = (env.QUORUM_SEAT_SCRUB_ENV || '').split(',').map((v) => v.trim()).filter(Boolean);
  return {
    label: 'custom',
    defaultBin: '',
    defaultModel: '',
    resultField,
    autoDetect: false,
    buildArgs(promptText, fixtureDir, model) {
      const values = { '{prompt}': promptText, '{fixture_dir}': fixtureDir, '{model}': model };
      const args = [];
      for (const arg of template) {
        if (arg === '{model}' && !model) {
          // Drop the placeholder and its preceding flag (e.g. "--model") when
          // no model is configured, so a blank value is never passed through.
          if (args.length && args[args.length - 1].startsWith('-')) args.pop();
          continue;
        }
        args.push(CUSTOM_PLACEHOLDERS.includes(arg) ? values[arg] : arg);
      }
      return args;
    },
    scrubEnv(env) {
      for (const name of scrub) delete env[name];
    },
    resultFrom(envelope) {
      return typeof envelope[resultField] === 'string' ? envelope[resultField] : undefined;
    },
    failureFrom(envelope) {
      if (!statusField) return null;
      const status = envelope[statusField];
      return status === statusOk ? null : `${statusField} ${JSON.stringify(status)}`;
    },
  };
}

function binExists(bin) {
  if (bin.includes('/') || bin.includes('\\')) return existsSync(bin);
  const dirs = (process.env.PATH || '').split(delimiter).filter(Boolean);
  return dirs.some((dir) => existsSync(join(dir, bin)));
}

// Pick the driver: explicit QUORUM_SEAT_CLI wins, otherwise the first
// auto-detectable driver whose binary is actually present. Never silently fall
// through to a missing binary — an unrunnable seat would read as a mysterious
// absence at judge time. A bin override without a named driver is rejected
// rather than guessed, because the override would bind to whichever driver
// happens to come first.
export function resolveDriver(env = process.env) {
  const requested = (env.QUORUM_SEAT_CLI || '').trim();
  const model = (env.QUORUM_SEAT_MODEL || '').trim();
  const overrideBin = (env.QUORUM_SEAT_BIN || '').trim();
  const names = [...Object.keys(SEAT_DRIVERS), 'custom'];
  if (requested) {
    if (requested === 'custom') {
      if (!overrideBin) throw new Error('QUORUM_SEAT_CLI=custom requires QUORUM_SEAT_BIN');
      return { driver: customDriverFrom(env), bin: overrideBin, model };
    }
    const driver = SEAT_DRIVERS[requested];
    if (!driver) {
      throw new Error(`unknown QUORUM_SEAT_CLI ${JSON.stringify(requested)}; expected one of: ${names.join(', ')}`);
    }
    return { driver, bin: overrideBin || driver.defaultBin, model: model || driver.defaultModel };
  }
  if (overrideBin) {
    throw new Error(`QUORUM_SEAT_BIN is set but QUORUM_SEAT_CLI is not; name the driver (${names.join('|')}) the binary belongs to`);
  }
  for (const driver of Object.values(SEAT_DRIVERS)) {
    if (driver.autoDetect && binExists(driver.defaultBin)) {
      return { driver, bin: driver.defaultBin, model: model || driver.defaultModel };
    }
  }
  throw new Error(
    `no seat CLI found (looked for: ${Object.values(SEAT_DRIVERS).map((d) => d.defaultBin).join(', ')}). ` +
    `Set QUORUM_SEAT_CLI=${names.join('|')}, and QUORUM_SEAT_BIN if the binary is elsewhere.`);
}

// Strip at most one surrounding markdown code fence (```json ... ``` or bare).
export function stripFence(text) {
  const trimmed = text.trim();
  const match = trimmed.match(/^```[A-Za-z0-9_-]*[ \t]*\r?\n([\s\S]*?)\r?\n?```$/);
  return match ? match[1].trim() : trimmed;
}

function asJsonObject(text) {
  try {
    const parsed = JSON.parse(text);
    return parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

// Recover the envelope from raw stdout. Some CLIs print a setup banner before
// the JSON, so a plain JSON.parse of the whole stream is not enough.
export function extractEnvelopeText(stdout) {
  const text = String(stdout).trim();
  if (text === '') return null;
  if (asJsonObject(text)) return text;
  const lines = text.split(/\r?\n/);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i].trim();
    if (line.startsWith('{') && asJsonObject(line)) return line;
  }
  const firstBrace = text.indexOf('{');
  if (firstBrace >= 0) {
    const span = text.slice(firstBrace);
    if (asJsonObject(span)) return span;
  }
  return null;
}

// Parse a driver's JSON envelope, pull the ballot JSON out of the driver's
// result field, and validate it. Returns {ok: true, ballot} or {ok: false, reason}.
export function extractBallot(envelopeText, expectedSeatId, driver = SEAT_DRIVERS.claude) {
  const text = extractEnvelopeText(envelopeText);
  if (text === null) {
    return { ok: false, reason: 'envelope is not JSON: no JSON object found in output' };
  }
  const envelope = asJsonObject(text);
  if (envelope === null) {
    return { ok: false, reason: 'envelope is not a JSON object' };
  }
  const failure = driver.failureFrom(envelope);
  if (failure) {
    return { ok: false, reason: `voter reported ${failure}` };
  }
  const result = driver.resultFrom(envelope);
  if (typeof result !== 'string') {
    return { ok: false, reason: `envelope has no string .${driver.resultField} field` };
  }
  let ballot;
  try {
    ballot = JSON.parse(stripFence(result));
  } catch (err) {
    return { ok: false, reason: `.${driver.resultField} does not contain ballot JSON: ${err.message}` };
  }
  const { valid, errors } = validateBallot(ballot, expectedSeatId);
  if (!valid) {
    return { ok: false, reason: `ballot schema-invalid: ${errors.join('; ')}` };
  }
  return { ok: true, ballot };
}

function invokeSeat(promptText, fixtureDir, driver, bin, model) {
  return new Promise((resolvePromise) => {
    const env = { ...process.env };
    driver.scrubEnv(env);
    const child = spawn(bin, driver.buildArgs(promptText, fixtureDir, model), {
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

async function runSeat({ seatId, promptPath, promptDir, fixtureDir, ballotsDir, rawDir, dryRun, driver, bin, model }) {
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
    const { stdout, stderr, code, timedOut } = await invokeSeat(promptText, fixtureDir, driver, bin, model);
    envelopeText = stdout.length > 0 ? stdout : null;
    if (timedOut) note = `timed out after ${SEAT_TIMEOUT_MS / 1000}s, killed`;
    else if (code !== 0) note = `${driver.label} exited ${code}: ${stderr.trim().slice(0, 300)}`;
  }

  // Save every raw envelope always — even partial output from a killed seat.
  if (envelopeText !== null) {
    writeFileSync(join(rawDir, `${seatId}.json`), envelopeText);
  }

  if (envelopeText === null) {
    return { seatId, outcome: `absent: no output (${note || 'empty stdout'})` };
  }
  const extracted = extractBallot(envelopeText, seatId, driver);
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
  // Dry-run never spawns a CLI, so it must not require one to be installed.
  let driver = SEAT_DRIVERS.claude;
  let bin = driver.defaultBin;
  let model = driver.defaultModel;
  if (!dryRun) {
    try {
      ({ driver, bin, model } = resolveDriver());
    } catch (err) {
      console.error(err.message);
      process.exit(1);
    }
    console.log(`seat CLI: ${driver.label} (${bin})${model ? ` model=${model}` : ''}`);
  } else {
    console.log(`dry-run: skipping CLI; would invoke per seat: ${bin} ${driver.buildArgs('<prompt>', fixtureDir, model).join(' ')}`);
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
      driver,
      bin,
      model,
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
