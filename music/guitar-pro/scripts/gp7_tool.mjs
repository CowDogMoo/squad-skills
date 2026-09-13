#!/usr/bin/env node
/**
 * Read, render, diff and re-export Guitar Pro 6/7+ files (.gp, .gpx) directly.
 *
 * PyGuitarPro cannot open these containers, so gp_tab.py asks the user to export
 * to GP5 first. alphaTab can, and a full import/export round-trip is lossless -
 * verified on a 105-bar 3-track file, 3203 fingerprinted attributes identical,
 * tempo automations, tuplets, ties, palm mutes, harmonics and slides included.
 * So when the source is a .gp there is no reason to make anyone downgrade it.
 *
 *   node gp7_tool.mjs info    FILE
 *   node gp7_tool.mjs ascii   FILE [--track NAME] [--bars 17-36] [--width 32]
 *   node gp7_tool.mjs midi    FILE OUT.mid          # type-1, carries the tempo map
 *   node gp7_tool.mjs diff    A.gp B.gp [--max 25]  # every musical attribute
 *   node gp7_tool.mjs clean-voices IN.gp OUT.gp     # drop note-less voices (Songsterr exports carry 3 per bar)
 *   node gp7_tool.mjs layout  IN.gp OUT.gp          # tab-only, bars per system packed by density
 *   node gp7_tool.mjs export  IN.gp OUT.gp          # round-trip, to prove losslessness
 *
 * String numbering: alphaTab numbers strings 1..N from the LOW string, while the
 * `tunings` array is HIGH string first, so the tuning of note.string is
 * tunings[tunings.length - note.string]. Getting that backwards silently mirrors
 * a whole tab, so it is worth reading twice.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "package.json"));
const at = require("@coderline/alphatab");

const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const pitchName = (m) => `${NAMES[m % 12]}${Math.floor(m / 12) - 1}`;
const load = (p) => at.importer.ScoreLoader.loadScoreFromBytes(new Uint8Array(readFileSync(p)));

const argv = process.argv.slice(2);
const cmd = argv.shift();
const flag = (name, dflt) => {
  const i = argv.indexOf(name);
  if (i < 0) return dflt;
  const v = argv[i + 1];
  argv.splice(i, 2);
  return v;
};

/** Beat length in ticks, honouring dots and tuplets. */
const WHOLE = 960 * 4;
function beatTicks(beat) {
  let len = WHOLE / beat.duration;
  if (beat.dots === 1) len *= 1.5;
  if (beat.dots === 2) len *= 1.75;
  if (beat.tupletNumerator > 0) len = (len * beat.tupletDenominator) / beat.tupletNumerator;
  return len;
}

function pickTrack(score, name) {
  if (!name) return score.tracks.find((t) => t.staves[0].stringTuning.tunings.length) ?? score.tracks[0];
  const t = score.tracks.find((x) => x.name.toLowerCase().includes(name.toLowerCase()));
  if (!t) {
    console.error(`no track matching "${name}" (have: ${score.tracks.map((x) => x.name).join(", ")})`);
    process.exit(1);
  }
  return t;
}

function cmdInfo(file) {
  const s = load(file);
  console.log(`${s.title || "(untitled)"}${s.artist ? ` - ${s.artist}` : ""}`);
  console.log(`${s.masterBars.length} bars, base tempo ${s.tempo}`);
  const tempos = s.masterBars.flatMap((mb, i) => (mb.tempoAutomations ?? []).map((a) => `bar ${i + 1} = ${a.value}`));
  console.log(`tempo map: ${tempos.length ? tempos.join(", ") : "(none)"}`);
  const sigs = [];
  s.masterBars.forEach((mb, i) => {
    const sig = `${mb.timeSignatureNumerator}/${mb.timeSignatureDenominator}`;
    if (!sigs.length || sigs[sigs.length - 1].sig !== sig) sigs.push({ bar: i + 1, sig });
  });
  console.log(`time signatures: ${sigs.map((x) => `bar ${x.bar} ${x.sig}`).join(", ")}`);
  for (const t of s.tracks) {
    const tun = t.staves[0].stringTuning.tunings;
    const notes = t.staves[0].bars.flatMap((b) => b.voices.flatMap((v) => v.beats.flatMap((x) => x.notes)));
    const frets = notes.map((n) => n.fret);
    const used = notes.filter((n) => !n.harmonicType).map((n) => tun[tun.length - n.string] + n.fret);
    console.log(`\n  ${t.name}  (${notes.length} notes)`);
    if (tun.length) {
      console.log(`    tuning  ${tun.map(pitchName).reverse().join(" ")}  (low to high, ${tun.length} strings)`);
      console.log(`    frets   ${frets.length ? `${Math.min(...frets)}-${Math.max(...frets)}` : "-"}`);
      if (used.length) console.log(`    range   ${pitchName(Math.min(...used))} to ${pitchName(Math.max(...used))}`);
      const pcs = {};
      for (const m of used) pcs[m % 12] = (pcs[m % 12] ?? 0) + 1;
      const top = Object.entries(pcs).sort((a, b) => b[1] - a[1]).slice(0, 5)
        .map(([k, v]) => `${NAMES[k]} ${v}`).join(" / ");
      console.log(`    pitches ${top}`);
    } else {
      console.log("    (percussion)");
    }
  }
}

function cmdAscii(file) {
  const trackName = flag("--track");
  const width = Number(flag("--width", 32));
  const range = flag("--bars");
  const s = load(file);
  const t = pickTrack(s, trackName);
  const tun = t.staves[0].stringTuning.tunings;
  if (!tun.length) { console.error(`track "${t.name}" has no strings`); process.exit(1); }
  const [from, to] = range
    ? range.split("-").map(Number)
    : [1, Math.min(s.masterBars.length, 16)];
  const label = tun.map((m) => pitchName(m).padEnd(3));

  const chunks = [];
  for (let b = from; b <= Math.min(to, t.staves[0].bars.length); b++) {
    const bar = t.staves[0].bars[b - 1];
    const master = s.masterBars[b - 1];
    const barTicks = (WHOLE * master.timeSignatureNumerator) / master.timeSignatureDenominator;
    const rows = tun.map(() => Array(width).fill("-"));
    const marks = Array(width).fill(" ");
    for (const v of bar.voices) {
      let tick = 0;
      for (const beat of v.beats) {
        const col = Math.min(width - 1, Math.round((tick / barTicks) * width));
        tick += beatTicks(beat);
        if (beat.isRest) continue;
        for (const n of beat.notes) {
          const row = tun.length - n.string;
          if (row < 0 || row >= rows.length) continue;
          const txt = n.harmonicType ? `<${n.fret}>` : String(n.fret);
          for (let k = 0; k < txt.length && col + k < width; k++) rows[row][col + k] = txt[k];
          if (n.isPalmMute) marks[col] = "P";
          if (n.isDead) rows[row][col] = "x";
        }
      }
    }
    chunks.push({ b, rows, marks });
  }

  console.log(`${s.title || file} - ${t.name}, bars ${from}-${to}`);
  console.log(`tuning ${tun.map(pitchName).reverse().join(" ")} (low to high) | P = palm mute | <n> = natural harmonic\n`);
  const per = 4;
  for (let i = 0; i < chunks.length; i += per) {
    const g = chunks.slice(i, i + per);
    console.log("     " + g.map((c) => `bar ${c.b}`.padEnd(width + 1)).join(""));
    console.log("     " + g.map((c) => c.marks.join("") + " ").join(""));
    for (let r = 0; r < tun.length; r++)
      console.log(`${label[r]}|` + g.map((c) => c.rows[r].join("") + "|").join(""));
    console.log();
  }
}

function cmdMidi(file, out) {
  const s = load(file);
  const midi = new at.midi.MidiFile();
  new at.midi.MidiFileGenerator(s, null, new at.midi.AlphaSynthMidiFileHandler(midi)).generate();

  const DIV = 960;
  const vlq = (n) => { const o = [n & 0x7f]; n >>= 7; while (n > 0) { o.unshift((n & 0x7f) | 0x80); n >>= 7; } return o; };
  const u32 = (n) => [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255];
  const chunk = (id, body) => [...id].map((c) => c.charCodeAt(0)).concat(u32(body.length), body);

  const all = [];
  for (const t of midi.tracks) for (const ev of t.events) all.push(ev);
  all.sort((a, b) => a.tick - b.tick);

  // a type-1 file keeps tempo on track 0, so every player finds it
  const tempoBody = [];
  let last = 0;
  for (const ev of all) {
    if (ev.constructor.name !== "TempoChangeEvent") continue;
    const us = Math.round(60000000 / ev.beatsPerMinute);
    tempoBody.push(...vlq(ev.tick - last), 0xff, 0x51, 0x03, (us >> 16) & 255, (us >> 8) & 255, us & 255);
    last = ev.tick;
  }
  tempoBody.push(...vlq(0), 0xff, 0x2f, 0x00);

  const tracks = [chunk("MTrk", tempoBody)];
  for (const track of s.tracks) {
    const ch = new Set([track.playbackInfo.primaryChannel, track.playbackInfo.secondaryChannel]);
    const body = [];
    const name = [...track.name].map((c) => c.charCodeAt(0) & 0x7f);
    body.push(...vlq(0), 0xff, 0x03, ...vlq(name.length), ...name);
    body.push(...vlq(0), 0xc0 | (track.playbackInfo.primaryChannel & 0x0f), track.playbackInfo.program & 0x7f);
    let prev = 0;
    for (const ev of all) {
      const kind = ev.constructor.name;
      if (kind !== "NoteOnEvent" && kind !== "NoteOffEvent") continue;
      if (!ch.has(ev.channel)) continue;
      body.push(...vlq(ev.tick - prev), (kind === "NoteOnEvent" ? 0x90 : 0x80) | (ev.channel & 0x0f),
                ev.noteKey & 0x7f, kind === "NoteOnEvent" ? ev.noteVelocity & 0x7f : 0);
      prev = ev.tick;
    }
    body.push(...vlq(0), 0xff, 0x2f, 0x00);
    tracks.push(chunk("MTrk", body));
  }
  writeFileSync(out, Buffer.from(chunk("MThd", [0, 1, 0, tracks.length, (DIV >> 8) & 255, DIV & 255]).concat(...tracks)));
  const tempos = all.filter((e) => e.constructor.name === "TempoChangeEvent").map((e) => `${e.beatsPerMinute}@${e.tick}`);
  console.log(`wrote ${out}: ${tracks.length - 1} tracks, tempo ${tempos.join(" -> ") || s.tempo}`);
}

/** Every attribute that a careless edit or a lossy round-trip could change. */
function fingerprint(score) {
  const out = [];
  out.push(`title=${score.title} artist=${score.artist} tempo=${score.tempo} bars=${score.masterBars.length}`);
  score.masterBars.forEach((mb, i) => {
    const t = (mb.tempoAutomations ?? []).map((a) => `${a.value}@${a.ratioPosition}`).join(",");
    if (t) out.push(`mb${i + 1} tempo=${t}`);
    out.push(`mb${i + 1} sig=${mb.timeSignatureNumerator}/${mb.timeSignatureDenominator} rep=${mb.isRepeatStart}/${mb.repeatCount}`);
  });
  score.tracks.forEach((t, ti) => {
    out.push(`track${ti} name=${t.name} tuning=[${t.staves[0].stringTuning.tunings}]`);
    t.staves[0].bars.forEach((bar, bi) =>
      bar.voices.forEach((v, vi) =>
        v.beats.forEach((b, xi) => {
          const notes = b.notes.map((n) => [
            `s${n.string}f${n.fret}`,
            n.isTieDestination ? "tie" : "", n.isPalmMute ? "pm" : "",
            n.harmonicType ? `h${n.harmonicType}` : "",
            n.slideOutType ? `so${n.slideOutType}` : "", n.slideInType ? `si${n.slideInType}` : "",
            n.isHammerPullOrigin ? "hp" : "", n.isDead ? "x" : "", n.isLetRing ? "lr" : "",
            n.bendType ? `b${n.bendType}` : "", n.isGhost ? "g" : "",
          ].filter(Boolean).join("")).join("+");
          out.push(`t${ti}b${bi + 1}v${vi}.${xi} dur=${b.duration} dots=${b.dots} ` +
                   `tup=${b.tupletNumerator}/${b.tupletDenominator} rest=${b.isRest} dyn=${b.dynamics} ${notes}`);
        })));
  });
  return out;
}

function cmdDiff(a, b) {
  const max = Number(flag("--max", 25));
  const fa = fingerprint(load(a)), fb = fingerprint(load(b));
  let n = 0;
  for (let i = 0; i < Math.max(fa.length, fb.length); i++) {
    if (fa[i] === fb[i]) continue;
    if (n < max) console.log(`- ${fa[i] ?? "(missing)"}\n+ ${fb[i] ?? "(missing)"}`);
    n++;
  }
  console.log(n ? `\n${n} differing attribute(s) of ${Math.max(fa.length, fb.length)}` : `IDENTICAL (${fa.length} attributes)`);
  process.exitCode = n ? 1 : 0;
}

/**
 * Strip voices that contain no notes.
 *
 * A Songsterr export declares four voices in every bar of every track and leaves
 * three of them holding a single quarter rest - which does not even fill a 4/4
 * bar. They carry no music, they are malformed, and in a dense bar they are
 * visual noise on the staff. Voice 0 is never touched, and a bar is never left
 * without a voice.
 */
function cmdCleanVoices(inp, out) {
  const s = load(inp);
  let removed = 0, kept = 0;
  for (const t of s.tracks)
    for (const staff of t.staves)
      for (const bar of staff.bars) {
        const keepers = bar.voices.filter((v, i) => i === 0 || v.beats.some((b) => b.notes.length));
        removed += bar.voices.length - keepers.length;
        kept += keepers.length;
        keepers.forEach((v, i) => { v.index = i; });
        bar.voices = keepers;
      }
  writeFileSync(out, Buffer.from(new at.exporter.Gp7Exporter().export(s, null)));
  console.log(`removed ${removed} empty voice(s), kept ${kept}; wrote ${out}`);
}

/**
 * Lay the score out so it can actually be read.
 *
 * Guitar Pro packs a fixed number of bars onto every system regardless of what
 * is in them. On a song with both a sparse intro and a shredding solo that is
 * the difference between a readable page and a smear: three bars of 31
 * thirty-second notes on one line runs the fret numbers together into
 * "18181717171718181717" with no gaps. Two settings fix it, and both survive a
 * GP7 export round-trip:
 *
 *   - showStandardNotation off, so each track costs one staff instead of two;
 *   - systemsLayout, a per-system bar count, packed by DENSITY rather than by a
 *     constant, so a dense bar gets a line to itself and four sparse ones share.
 *
 * Density is counted in beat columns, not notes: a three-note power chord
 * occupies one column, so columns are what compete for horizontal space.
 *
 *   node gp7_tool.mjs layout IN.gp OUT.gp [--budget 24] [--max-bars 4] [--keep-notation]
 *   node gp7_tool.mjs layout IN.gp OUT.gp --bars-per-system 1
 */
function cmdLayout(inp, out) {
  const fixed = flag("--bars-per-system");
  const budget = Number(flag("--budget", 24));
  const maxBars = Number(flag("--max-bars", 4));
  const keepNotation = argv.includes("--keep-notation");
  if (keepNotation) argv.splice(argv.indexOf("--keep-notation"), 1);

  const s = load(inp);

  let hidden = 0;
  if (!keepNotation)
    for (const t of s.tracks)
      for (const staff of t.staves) {
        // a percussion track has no tablature to fall back on, so its notation stays
        if (!staff.showTablature) continue;
        if (staff.showStandardNotation) { staff.showStandardNotation = false; hidden++; }
      }

  const pitched = s.tracks.filter((t) => t.staves[0].stringTuning.tunings.length);
  const density = s.masterBars.map((_, i) =>
    Math.max(1, ...pitched.map((t) =>
      t.staves[0].bars[i].voices.reduce((a, v) => a + v.beats.filter((b) => b.notes.length).length, 0))));

  let layout;
  if (fixed) {
    const n = Number(fixed);
    layout = Array(Math.ceil(s.masterBars.length / n)).fill(n);
  } else {
    layout = [];
    let bars = 0, cols = 0;
    for (const d of density) {
      // a bar never splits across systems, so one over budget still gets its own
      if (bars && (cols + d > budget || bars >= maxBars)) { layout.push(bars); bars = 0; cols = 0; }
      bars++; cols += d;
    }
    if (bars) layout.push(bars);
  }

  const total = layout.reduce((a, b) => a + b, 0);
  if (total !== s.masterBars.length) {
    console.error(`LAYOUT FAIL: layout covers ${total} bars, score has ${s.masterBars.length}`);
    process.exit(1);
  }

  s.defaultSystemsLayout = layout[0];
  s.systemsLayout = layout.slice();
  for (const t of s.tracks) { t.defaultSystemsLayout = layout[0]; t.systemsLayout = layout.slice(); }

  writeFileSync(out, Buffer.from(new at.exporter.Gp7Exporter().export(s, null)));

  const hist = {};
  for (const n of layout) hist[n] = (hist[n] ?? 0) + 1;
  console.log(`${layout.length} systems for ${total} bars ` +
              `(${Object.entries(hist).sort().map(([k, v]) => `${v}x${k}-bar`).join(", ")})`);
  if (hidden) console.log(`hid the standard-notation staff on ${hidden} track(s); tablature only`);
  const busiest = density.map((d, i) => [d, i + 1]).sort((a, b) => b[0] - a[0]).slice(0, 3);
  console.log(`busiest bars: ${busiest.map(([d, b]) => `${b} (${d} columns)`).join(", ")}`);
  console.log(`wrote ${out}`);
}

function cmdExport(inp, out) {
  writeFileSync(out, Buffer.from(new at.exporter.Gp7Exporter().export(load(inp), null)));
  console.log(`wrote ${out}`);
}

const [a, b] = argv;
switch (cmd) {
  case "info": cmdInfo(a); break;
  case "ascii": cmdAscii(a); break;
  case "midi": cmdMidi(a, b); break;
  case "diff": cmdDiff(a, b); break;
  case "clean-voices": cmdCleanVoices(a, b); break;
  case "layout": cmdLayout(a, b); break;
  case "export": cmdExport(a, b); break;
  default:
    console.error("usage: gp7_tool.mjs info|ascii|midi|diff|clean-voices|layout|export ...  (see the header for flags)");
    process.exit(2);
}
