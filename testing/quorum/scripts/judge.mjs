#!/usr/bin/env node
// judge.mjs — deterministic unanimity judge for cquorum completion gating.
//
// Usage: node judge.mjs <run-dir>
//   <run-dir>/panel.json           [{seat_id, jurisdiction, required}, ...]
//   <run-dir>/ballots/<seat_id>.json  one ballot per seat (see ballot-schema.md)
// Writes <run-dir>/verdict.json (canonical JSON: recursively sorted keys,
// 2-space indent, trailing newline, no timestamps, integer-only counts).
//
// Semantics: verdict COMPLETE iff EVERY required seat has a schema-valid
// ballot with verdict "complete" (and empty unmet). Any veto, abstain,
// absent, or malformed required seat => NOT_COMPLETE. Malformed ballots are
// never repaired. An "incomplete" verdict without at least one cited unmet
// criterion is demoted to abstain with a seat fault (a veto must be
// actionable); a "complete" verdict with non-empty unmet is contradictory
// and likewise demoted. work_queue aggregates cited unmet criteria in
// stable order (panel order, then unmet order), deduplicated by exact
// criterion string (first citing seat wins).
//
// Exit 0 when a verdict is written. Exit 2 (no verdict) only for protocol
// corruption: missing/unparsable/invalid panel.json, duplicate seat_id,
// or an unknown file in ballots/.

import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { realpathSync } from 'node:fs';

// True when this module is the script node was invoked with, comparing
// realpaths so a symlinked install still runs its CLI main().
function isMainScript(argvPath, moduleUrl) {
  const real = (p) => { try { return realpathSync(p); } catch { return resolve(p); } };
  return real(argvPath) === real(fileURLToPath(moduleUrl));
}

export class ProtocolError extends Error {}

const VERDICTS = ['complete', 'incomplete', 'abstain'];

// Recursively sort object keys so serialization is order-independent.
export function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value !== null && typeof value === 'object') {
    const out = {};
    for (const key of Object.keys(value).sort()) out[key] = canonicalize(value[key]);
    return out;
  }
  return value;
}

export function canonicalJson(value) {
  return `${JSON.stringify(canonicalize(value), null, 2)}\n`;
}

// Validate a parsed ballot against ballot-schema.md. Returns
// {valid, errors}. Unknown extra keys are tolerated; core fields are strict.
// When expectedSeatId is given, ballot.seat_id must match it.
export function validateBallot(raw, expectedSeatId = null) {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return { valid: false, errors: ['ballot is not a JSON object'] };
  }
  const errors = [];
  if (typeof raw.seat_id !== 'string' || raw.seat_id.length === 0) {
    errors.push('seat_id must be a non-empty string');
  } else if (expectedSeatId !== null && raw.seat_id !== expectedSeatId) {
    errors.push(`seat_id "${raw.seat_id}" does not match expected seat "${expectedSeatId}"`);
  }
  if (typeof raw.jurisdiction !== 'string' || raw.jurisdiction.length === 0) {
    errors.push('jurisdiction must be a non-empty string');
  }
  if (!VERDICTS.includes(raw.verdict)) {
    errors.push('verdict must be "complete", "incomplete", or "abstain"');
  }
  if (raw.unmet !== undefined) {
    if (!Array.isArray(raw.unmet)) {
      errors.push('unmet must be an array');
    } else {
      raw.unmet.forEach((item, i) => {
        if (item === null || typeof item !== 'object' || Array.isArray(item)) {
          errors.push(`unmet[${i}] must be an object`);
          return;
        }
        if (typeof item.criterion !== 'string' || item.criterion.trim().length === 0) {
          errors.push(`unmet[${i}].criterion must be a non-empty string`);
        }
        if (typeof item.evidence !== 'string') {
          errors.push(`unmet[${i}].evidence must be a string`);
        }
      });
    }
  }
  if (raw.evidence !== undefined) {
    if (!Array.isArray(raw.evidence) || raw.evidence.some((e) => typeof e !== 'string')) {
      errors.push('evidence must be an array of strings');
    }
  }
  if (raw.confidence !== undefined) {
    if (
      typeof raw.confidence !== 'number' ||
      !Number.isFinite(raw.confidence) ||
      raw.confidence < 0 ||
      raw.confidence > 1
    ) {
      errors.push('confidence must be a finite number in [0, 1]');
    }
  }
  if (raw.artifacts !== undefined) {
    if (raw.artifacts === null || typeof raw.artifacts !== 'object' || Array.isArray(raw.artifacts)) {
      errors.push('artifacts must be an object');
    } else {
      for (const [key, value] of Object.entries(raw.artifacts)) {
        if (!['string', 'number', 'boolean'].includes(typeof value)) {
          errors.push(`artifacts["${key}"] must be a string, number, or boolean`);
        }
      }
    }
  }
  return { valid: errors.length === 0, errors };
}

function loadPanel(runDir) {
  const panelPath = join(runDir, 'panel.json');
  if (!existsSync(panelPath)) throw new ProtocolError(`missing panel.json in ${runDir}`);
  let panel;
  try {
    panel = JSON.parse(readFileSync(panelPath, 'utf8'));
  } catch (err) {
    throw new ProtocolError(`unparsable panel.json: ${err.message}`);
  }
  if (!Array.isArray(panel) || panel.length === 0) {
    throw new ProtocolError('panel.json must be a non-empty array of seats');
  }
  const seen = new Set();
  for (const seat of panel) {
    if (
      seat === null ||
      typeof seat !== 'object' ||
      Array.isArray(seat) ||
      typeof seat.seat_id !== 'string' ||
      seat.seat_id.length === 0
    ) {
      throw new ProtocolError('every panel.json entry must be an object with a non-empty seat_id');
    }
    if (seen.has(seat.seat_id)) {
      throw new ProtocolError(`duplicate seat_id in panel.json: ${seat.seat_id}`);
    }
    if (seat.requires_artifacts !== undefined && typeof seat.requires_artifacts !== 'boolean') {
      throw new ProtocolError(`seat ${seat.seat_id}: requires_artifacts must be a boolean`);
    }
    seen.add(seat.seat_id);
  }
  return { panel, seatIds: seen };
}

function checkBallotDir(ballotsDir, seatIds) {
  if (!existsSync(ballotsDir)) return; // all seats absent — judged, not corruption
  for (const name of readdirSync(ballotsDir)) {
    if (name.startsWith('.')) continue; // tolerate .DS_Store and friends
    const stem = name.endsWith('.json') ? name.slice(0, -'.json'.length) : null;
    if (stem === null || !seatIds.has(stem)) {
      throw new ProtocolError(`unknown ballot file: ballots/${name}`);
    }
  }
}

// Judge one seat. Returns {state, faults, unmet} where unmet is the list of
// valid citations (only non-empty for state "veto").
function judgeSeat(seat, ballotsDir) {
  const faults = [];
  const ballotPath = join(ballotsDir, `${seat.seat_id}.json`);
  if (!existsSync(ballotPath)) {
    return { state: 'absent', faults: ['no ballot file'], unmet: [] };
  }
  let ballot;
  try {
    ballot = JSON.parse(readFileSync(ballotPath, 'utf8'));
  } catch (err) {
    return { state: 'malformed', faults: [`unparsable ballot: ${err.message}`], unmet: [] };
  }
  const { valid, errors } = validateBallot(ballot, seat.seat_id);
  if (!valid) {
    return { state: 'malformed', faults: errors.map((e) => `schema-invalid: ${e}`), unmet: [] };
  }
  // Artifacts-or-abstain (squad-quorum-design §2.3): on a seat declared
  // requires_artifacts, an assent or veto that carries no execution artifacts
  // is ungrounded testimony and is demoted; only explicit abstain is exempt.
  if (seat.requires_artifacts === true && ballot.verdict !== 'abstain') {
    const grounded =
      ballot.artifacts !== undefined &&
      ballot.artifacts !== null &&
      Object.keys(ballot.artifacts).length > 0;
    if (!grounded) {
      faults.push('vote without required execution artifacts; demoted to abstain');
      return { state: 'abstain', faults, unmet: [] };
    }
  }
  const unmet = Array.isArray(ballot.unmet) ? ballot.unmet : [];
  if (ballot.verdict === 'complete') {
    if (unmet.length > 0) {
      faults.push('contradictory ballot: verdict "complete" with non-empty unmet; demoted to abstain');
      return { state: 'abstain', faults, unmet: [] };
    }
    return { state: 'complete', faults, unmet: [] };
  }
  if (ballot.verdict === 'incomplete') {
    if (unmet.length === 0) {
      faults.push('veto without citation: verdict "incomplete" with empty unmet; demoted to abstain');
      return { state: 'abstain', faults, unmet: [] };
    }
    return { state: 'veto', faults, unmet };
  }
  return { state: 'abstain', faults, unmet: [] };
}

// Pure judging core: reads panel + ballots under runDir, returns the verdict
// object (does not write). Throws ProtocolError on protocol corruption.
export function judgeRun(runDir) {
  const { panel, seatIds } = loadPanel(runDir);
  const ballotsDir = join(runDir, 'ballots');
  checkBallotDir(ballotsDir, seatIds);

  const seats = [];
  const workQueue = [];
  const citedCriteria = new Set();
  const counts = {
    absent: 0,
    abstain: 0,
    complete: 0,
    malformed: 0,
    required: 0,
    seats: panel.length,
    veto: 0,
  };

  let allRequiredComplete = true;
  for (const seat of panel) {
    const required = seat.required !== false;
    if (required) counts.required += 1;
    const { state, faults, unmet } = judgeSeat(seat, ballotsDir);
    counts[state] += 1;
    if (required && state !== 'complete') allRequiredComplete = false;
    for (const item of unmet) {
      if (citedCriteria.has(item.criterion)) continue; // dedup by exact criterion, first citer wins
      citedCriteria.add(item.criterion);
      workQueue.push({ criterion: item.criterion, evidence: item.evidence, seat_id: seat.seat_id });
    }
    seats.push({ faults, seat_id: seat.seat_id, state });
  }

  return {
    $schema: 'cquorum/verdict/v1',
    counts,
    seats,
    verdict: allRequiredComplete ? 'COMPLETE' : 'NOT_COMPLETE',
    work_queue: workQueue,
  };
}

function main(argv) {
  const runDir = argv[2];
  if (!runDir) {
    console.error('usage: node judge.mjs <run-dir>');
    process.exit(2);
  }
  let verdict;
  try {
    verdict = judgeRun(runDir);
  } catch (err) {
    if (err instanceof ProtocolError) {
      console.error(`protocol corruption: ${err.message}`);
      process.exit(2);
    }
    throw err;
  }
  writeFileSync(join(runDir, 'verdict.json'), canonicalJson(verdict));
  console.log(`verdict: ${verdict.verdict}`);
  process.exit(0);
}

// Entry guard via realpath: this skill is installed as a symlink, so
// argv[1] can be the symlinked path while import.meta.url is realpath-ed.
// Comparing unresolved paths would silently skip main().
if (process.argv[1] && isMainScript(process.argv[1], import.meta.url)) {
  main(process.argv);
}
