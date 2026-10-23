#!/usr/bin/env node
// run-seats.mjs — invoke one voter per rendered prompt and collect ballots.
//
// Usage: node run-seats.mjs <prompt-dir> <ballots-out-dir> [--dry-run] [--from-raw] [--missing-only] [--seat <seat_id> ...]
//   <prompt-dir>/<seat_id>.prompt.md   rendered prompts (render-prompts.mjs)
//   <prompt-dir>/_run.json             {fixture_dir} — the staged fixture the
//                                      voter is granted via --add-dir/cwd
// Writes ballots to <ballots-out-dir>/<seat_id>.json and every raw envelope
// (always, even partial/timeout output) to <ballots-out-dir>/../raw/<seat_id>.json.
//
// Subagent mode (--from-raw): when seats are spawned in parallel via host
// subagents (e.g. Agent / Task tools) rather than a shell CLI, save each
// subagent's verbatim final response to
// <ballots-out-dir>/../raw/<seat_id>.txt (or .json) and run with --from-raw.
// This validates each raw response against the ballot schema and writes only
// schema-valid ballots to <ballots-out-dir>/<seat_id>.json.
//
// Selective re-ask flags:
//   --seat <seat_id>   run/extract only the named seat(s) (repeatable)
//   --missing-only     skip seats that already have a schema-valid ballot in
//                      <ballots-out-dir>/<seat_id>.json (enforces "never re-run
//                      a validly parsed ballot" on multi-seat panels)
//
// Voter invocation is driver-based, so the gate is not tied to one vendor CLI.
// Select with QUORUM_SEAT_CLI=claude|custom; when unset, the QUORUM_SEAT_*
// settings in $QUORUM_STATE_DIR/seat-driver.json (default
// ~/.claude/quorum-state/seat-driver.json) apply, and failing that claude is
// used if its binary is on PATH. Per key, the environment beats the file.
// QUORUM_SEAT_BIN overrides the binary path (requires QUORUM_SEAT_CLI) and
// QUORUM_SEAT_MODEL overrides the model. Before any seat runs the chosen
// binary must exist; a claude binary must also answer --version and not look
// like a hand-written ballot stub (a tripwire for leftovers, not proof).
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

import { existsSync, mkdirSync, readFileSync, readdirSync, realpathSync, statSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { basename, delimiter, dirname, join, resolve } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

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
    probeVersion: true,
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
    probeVersion: false,
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

export function resolveBinPath(bin, pathEnv = process.env.PATH || '') {
  if (bin.includes('/') || bin.includes('\\')) return existsSync(bin) ? bin : null;
  const dirs = pathEnv.split(delimiter).filter(Boolean);
  for (const dir of dirs) {
    const candidate = join(dir, bin);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

// Check that the seat binary exists and, for a driver with probeVersion, that
// it is not an obvious stand-in: a script with the ballot keys written into
// it, or a binary whose --version fails, is empty, or prints a JSON ballot
// envelope. This is a tripwire for leftover test stubs and naive fakes, not
// authentication: a stub that builds its keys at runtime and answers
// --version passes, and the agent running the gate could write ballot files
// directly anyway. Custom drivers get only the existence check, because their
// wrappers are legitimately scripts and may well mention the ballot keys.
// Returns the resolved path so the seat spawns exactly the checked binary.
export function verifyDriverBin(driver, bin, pathEnv = process.env.PATH || '') {
  const resolved = resolveBinPath(bin, pathEnv);
  if (!resolved) {
    throw new Error(`seat binary not found: ${bin}`);
  }
  if (!driver.probeVersion) return resolved;
  let text = '';
  try {
    const st = statSync(resolved);
    if (st.isFile() && st.size > 0 && st.size < 1024 * 1024) text = readFileSync(resolved, 'utf8');
  } catch {
    // Unreadable is not evidence of a stub; the --version probe still runs.
  }
  if (text.startsWith('#!') && text.includes('seat_id') && text.includes('verdict')) {
    throw new Error(
      `refusing voter stub at ${resolved}: script contains hardcoded ballot schema keys ("seat_id"/"verdict")`,
    );
  }
  const res = spawnSync(resolved, ['--version'], { timeout: 5000, encoding: 'utf8' });
  if (res.error || res.status !== 0) {
    // A signal-killed child has status null and no error, only .signal.
    const why = res.error ? res.error.message : res.status !== null ? `exited ${res.status}` : `killed by ${res.signal}`;
    throw new Error(`refusing broken or fake ${driver.label} binary at ${resolved}: --version failed (${why})`);
  }
  const stdout = (res.stdout || '').trim();
  if (!stdout) {
    throw new Error(
      `refusing broken or fake ${driver.label} binary at ${resolved}: --version produced empty stdout`,
    );
  }
  const maybeEnv = extractEnvelopeText(stdout);
  const parsed = maybeEnv ? asJsonObject(maybeEnv) : null;
  if (parsed && ('result' in parsed || 'response' in parsed || 'verdict' in parsed || 'seat_id' in parsed)) {
    throw new Error(
      `refusing ${driver.label} binary at ${resolved}: --version returned a JSON ballot envelope instead of version info`,
    );
  }
  return resolved;
}

// The quorum state directory; same default as log-verdict.mjs, which keeps
// its own copy so each script stays standalone.
export function stateDirFrom(env = process.env) {
  return env.QUORUM_STATE_DIR || join(homedir(), '.claude/quorum-state');
}

// Read $stateDir/seat-driver.json: a flat JSON object of QUORUM_SEAT_* names
// to string values (QUORUM_SEAT_ARGS may also be a JSON array of strings).
// Returns null when the file does not exist; throws a named error on anything
// malformed so a bad file fails at startup, not as a TypeError mid-resolve.
export function readSeatDriverConfig(stateDir) {
  const configPath = join(stateDir, 'seat-driver.json');
  if (!existsSync(configPath)) return null;
  let parsed;
  try {
    parsed = JSON.parse(readFileSync(configPath, 'utf8'));
  } catch (err) {
    throw new Error(`invalid JSON in ${configPath}: ${err.message}`);
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${configPath} must contain a JSON object`);
  }
  const settings = {};
  for (const [key, value] of Object.entries(parsed)) {
    if (!key.startsWith('QUORUM_SEAT_')) {
      throw new Error(`${configPath}: unexpected key ${JSON.stringify(key)}; only QUORUM_SEAT_* settings belong here`);
    }
    if (key === 'QUORUM_SEAT_ARGS' && Array.isArray(value)) {
      settings[key] = JSON.stringify(value); // customDriverFrom validates the elements
    } else if (typeof value === 'string') {
      settings[key] = value;
    } else {
      throw new Error(`${configPath}: ${key} must be a string${key === 'QUORUM_SEAT_ARGS' ? ' or an array of strings' : ''}`);
    }
  }
  return { configPath, settings };
}

// Pick the driver. Precedence: QUORUM_SEAT_CLI in env, then seat-driver.json
// in opts.stateDir (read only when the caller passes one, so library callers
// and tests never pick up the operator's file by accident), then the first
// auto-detectable driver whose binary is on PATH. Per key, a non-blank env
// value beats the file. `source` says where the driver choice came from so the
// run can print it. Binary checks are main()'s job (verifyDriverBin), so this
// stays free of side effects.
export function resolveDriver(rawEnv = process.env, { stateDir } = {}) {
  let env = rawEnv;
  let source = 'QUORUM_SEAT_CLI';
  if (!(rawEnv.QUORUM_SEAT_CLI || '').trim() && stateDir) {
    const config = readSeatDriverConfig(stateDir);
    if (config) {
      env = { ...rawEnv };
      for (const [key, value] of Object.entries(config.settings)) {
        if (!(rawEnv[key] || '').trim()) env[key] = value;
      }
      source = config.configPath;
    }
  }
  const requested = (env.QUORUM_SEAT_CLI || '').trim();
  const model = (env.QUORUM_SEAT_MODEL || '').trim();
  const overrideBin = (env.QUORUM_SEAT_BIN || '').trim();
  const pathEnv = env.PATH !== undefined ? env.PATH : (process.env.PATH || '');
  const names = [...Object.keys(SEAT_DRIVERS), 'custom'];
  if (requested) {
    if (requested === 'custom') {
      if (!overrideBin) throw new Error('QUORUM_SEAT_CLI=custom requires QUORUM_SEAT_BIN');
      return { driver: customDriverFrom(env), bin: overrideBin, model, source };
    }
    const driver = SEAT_DRIVERS[requested];
    if (!driver) {
      throw new Error(`unknown QUORUM_SEAT_CLI ${JSON.stringify(requested)}; expected one of: ${names.join(', ')}`);
    }
    return { driver, bin: overrideBin || driver.defaultBin, model: model || driver.defaultModel, source };
  }
  if (overrideBin) {
    throw new Error(`QUORUM_SEAT_BIN is set but QUORUM_SEAT_CLI is not; name the driver (${names.join('|')}) the binary belongs to`);
  }
  for (const driver of Object.values(SEAT_DRIVERS)) {
    if (driver.autoDetect && resolveBinPath(driver.defaultBin, pathEnv)) {
      return { driver, bin: driver.defaultBin, model: model || driver.defaultModel, source: 'auto-detect' };
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

// Parse a raw subagent response (direct bare/fenced ballot JSON or a CLI
// JSON envelope) and validate it against the ballot schema.
export function extractRawBallot(rawText, expectedSeatId, driver = SEAT_DRIVERS.claude) {
  const text = String(rawText ?? '').trim();
  if (text === '') {
    return { ok: false, reason: 'raw output is empty' };
  }
  const unfenced = stripFence(text);
  const direct = asJsonObject(unfenced);
  if (direct !== null) {
    const hasEnvelopeResult = typeof driver?.resultFrom === 'function' && typeof driver.resultFrom(direct) === 'string';
    const hasEnvelopeFailure = typeof driver?.failureFrom === 'function' && driver.failureFrom(direct) !== null;
    if (!hasEnvelopeResult && !hasEnvelopeFailure) {
      const { valid, errors } = validateBallot(direct, expectedSeatId);
      if (!valid) {
        return { ok: false, reason: `ballot schema-invalid: ${errors.join('; ')}` };
      }
      return { ok: true, ballot: direct };
    }
  }
  return extractBallot(text, expectedSeatId, driver);
}

export function hasValidBallot(ballotsDir, seatId) {
  const ballotPath = join(ballotsDir, `${seatId}.json`);
  if (!existsSync(ballotPath)) return false;
  const parsed = asJsonObject(readFileSync(ballotPath, 'utf8'));
  if (parsed === null) return false;
  return validateBallot(parsed, seatId).valid;
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

async function runSeat({ seatId, promptPath, promptDir, fixtureDir, ballotsDir, rawDir, dryRun, fromRaw, driver, bin, model }) {
  if (fromRaw) {
    const rawTxt = join(rawDir, `${seatId}.txt`);
    const rawJson = join(rawDir, `${seatId}.json`);
    let rawContent = null;
    let sourceLabel = '';
    if (existsSync(rawTxt)) {
      rawContent = readFileSync(rawTxt, 'utf8');
      sourceLabel = 'from-raw (.txt)';
    } else if (existsSync(rawJson)) {
      rawContent = readFileSync(rawJson, 'utf8');
      sourceLabel = 'from-raw (.json)';
    } else {
      return { seatId, outcome: 'absent: no raw output in raw/ [from-raw]' };
    }
    const extracted = extractRawBallot(rawContent, seatId, driver);
    if (!extracted.ok) {
      return { seatId, outcome: `absent: ${extracted.reason} [${sourceLabel}]` };
    }
    writeFileSync(join(ballotsDir, `${seatId}.json`), canonicalJson(extracted.ballot));
    return { seatId, outcome: `ballot: ${extracted.ballot.verdict} [${sourceLabel}]` };
  }

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

function parseCliArgs(argv) {
  const positional = [];
  const requestedSeats = [];
  let dryRun = false;
  let fromRaw = false;
  let missingOnly = false;
  const args = argv.slice(2);
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '--dry-run') {
      dryRun = true;
    } else if (arg === '--from-raw') {
      fromRaw = true;
    } else if (arg === '--missing-only') {
      missingOnly = true;
    } else if (arg === '--seat') {
      const val = args[i + 1];
      if (!val || val.startsWith('--')) {
        throw new Error('--seat requires a <seat_id> argument');
      }
      requestedSeats.push(val);
      i += 1;
    } else if (arg.startsWith('--seat=')) {
      const val = arg.slice('--seat='.length);
      if (!val) throw new Error('--seat requires a non-empty <seat_id>');
      requestedSeats.push(val);
    } else {
      positional.push(arg);
    }
  }
  return { positional, requestedSeats, dryRun, fromRaw, missingOnly };
}

async function main(argv) {
  let parsed;
  try {
    parsed = parseCliArgs(argv);
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
  const { positional, requestedSeats, dryRun, fromRaw, missingOnly } = parsed;
  const [promptDirArg, ballotsOutArg] = positional;
  if (!promptDirArg || !ballotsOutArg) {
    console.error('usage: node run-seats.mjs <prompt-dir> <ballots-out-dir> [--dry-run] [--from-raw] [--missing-only] [--seat <seat_id> ...]');
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

  const allPromptFiles = readdirSync(promptDir)
    .filter((name) => name.endsWith(PROMPT_SUFFIX))
    .sort();
  if (allPromptFiles.length === 0) {
    console.error(`no ${PROMPT_SUFFIX} files in ${promptDir}`);
    process.exit(1);
  }

  let selectedPromptFiles = allPromptFiles;
  if (requestedSeats.length > 0) {
    const available = new Set(allPromptFiles.map((n) => basename(n, PROMPT_SUFFIX)));
    for (const seatId of requestedSeats) {
      if (!available.has(seatId)) {
        console.error(`unknown seat "${seatId}": no ${seatId}${PROMPT_SUFFIX} in ${promptDir}`);
        process.exit(1);
      }
    }
    const filterSet = new Set(requestedSeats);
    selectedPromptFiles = allPromptFiles.filter((n) => filterSet.has(basename(n, PROMPT_SUFFIX)));
  }

  if (missingOnly) {
    selectedPromptFiles = selectedPromptFiles.filter((n) => !hasValidBallot(ballotsDir, basename(n, PROMPT_SUFFIX)));
    if (selectedPromptFiles.length === 0) {
      console.log('all selected seats already have valid ballots; nothing to run');
      return;
    }
  }

  // Dry-run and from-raw never spawn a CLI, so they must not require one to be installed.
  let driver = SEAT_DRIVERS.claude;
  let bin = driver.defaultBin;
  let model = driver.defaultModel;
  if (!dryRun && !fromRaw) {
    let source;
    try {
      ({ driver, bin, model, source } = resolveDriver(process.env, { stateDir: stateDirFrom(process.env) }));
      bin = verifyDriverBin(driver, bin);
    } catch (err) {
      console.error(err.message);
      process.exit(1);
    }
    console.log(`seat CLI: ${driver.label} (${bin})${model ? ` model=${model}` : ''} [from ${source}]`);
  } else if (fromRaw) {
    if ((process.env.QUORUM_SEAT_CLI || '').trim() === 'custom' && (process.env.QUORUM_SEAT_ARGS || '').trim()) {
      driver = customDriverFrom(process.env);
    }
    console.log(`from-raw: extracting ballots from ${rawDir}`);
  } else {
    console.log(`dry-run: skipping CLI; would invoke per seat: ${bin} ${driver.buildArgs('<prompt>', fixtureDir, model).join(' ')}`);
  }
  const tasks = selectedPromptFiles.map((name) => () =>
    runSeat({
      seatId: basename(name, PROMPT_SUFFIX),
      promptPath: join(promptDir, name),
      promptDir,
      fixtureDir,
      ballotsDir,
      rawDir,
      dryRun,
      fromRaw,
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
