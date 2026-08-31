#!/usr/bin/env node
/**
 * gp7_export.mjs -- write a native Guitar Pro 7/8 (.gp) file via alphaTab.
 *
 * This exists for one reason: the .gp5 binary format cannot hold more than 7
 * strings, and an 8-string player would rather open a real Guitar Pro file
 * than import a MusicXML. alphaTab's Gp7Exporter writes the modern zip/GPIF
 * container, which has no such limit.
 *
 * Usage:  node gp7_export.mjs <input.json> <output.gp>
 *
 * The input JSON is emitted by gp_tab.py -- see Tab.gp7() there. Strings are
 * numbered the Guitar Pro way (1 = highest), and tunings are listed low-first,
 * matching the rest of this skill.
 */

import { readFileSync, writeFileSync } from "node:fs";

const [, , inputPath, outputPath] = process.argv;
if (!inputPath || !outputPath) {
  console.error("usage: node gp7_export.mjs <input.json> <output.gp>");
  process.exit(2);
}

let alphaTab;
try {
  const mod = await import("@coderline/alphatab");
  alphaTab = mod.default ?? mod;
} catch (err) {
  console.error(
    "alphaTab is not installed. Install it next to this script with:\n" +
      "    npm install @coderline/alphatab\n" +
      `original error: ${err.message}`,
  );
  process.exit(3);
}

const M = alphaTab.model;
const spec = JSON.parse(readFileSync(inputPath, "utf8"));

const score = new M.Score();
score.title = spec.title ?? "Untitled";
score.artist = spec.artist ?? "";
score.album = spec.album ?? "";
const tempo = spec.tempo ?? 120;

// Master bars carry time signature and are shared across every track, so they
// have to be built once up front from the longest track. Tempo is not a
// settable property on Score -- it is derived from a tempo automation on the
// first master bar, which is what actually gets written into the file.
const barCount = Math.max(...spec.tracks.map((t) => t.bars.length));
for (let i = 0; i < barCount; i++) {
  const mb = new M.MasterBar();
  const ts = spec.tracks[0].bars[i]?.ts ?? spec.tracks[0].bars[0]?.ts ?? [4, 4];
  mb.timeSignatureNumerator = ts[0];
  mb.timeSignatureDenominator = ts[1];
  if (i === 0) {
    mb.tempoAutomations = [M.Automation.buildTempoAutomation(false, 0, tempo, 2)];
  }
  const sectionText = spec.tracks[0].bars[i]?.section;
  if (sectionText) {
    const section = new M.Section();
    section.text = sectionText;
    section.marker = sectionText;
    mb.section = section;
  }
  score.addMasterBar(mb);
}

const DURATIONS = {
  1: M.Duration.Whole,
  2: M.Duration.Half,
  4: M.Duration.Quarter,
  8: M.Duration.Eighth,
  16: M.Duration.Sixteenth,
  32: M.Duration.ThirtySecond,
  64: M.Duration.SixtyFourth,
};

for (const trackSpec of spec.tracks) {
  const track = new M.Track();
  track.name = trackSpec.name ?? "Guitar";
  track.playbackInfo.program = trackSpec.program ?? 30;
  track.playbackInfo.primaryChannel = trackSpec.channel ?? 0;
  track.playbackInfo.secondaryChannel = (trackSpec.channel ?? 0) + 1;
  track.playbackInfo.volume = 15;
  score.addTrack(track);

  const staff = new M.Staff();
  track.addStaff(staff);

  const isPercussion = !!trackSpec.isPercussion;
  if (isPercussion) {
    // Drums have no strings or frets. Each note points at an entry in the
    // track's articulation table, so that table has to be set up first or the
    // notes resolve to nothing.
    staff.isPercussion = true;
    staff.showTablature = false;
    staff.showStandardNotation = true;
    staff.standardNotationLineCount = 5;
    track.playbackInfo.primaryChannel = 9;
    track.playbackInfo.secondaryChannel = 9;
    track.percussionArticulations = (trackSpec.percussionArticulations ?? []).map((a) => {
      const art = new M.InstrumentArticulation();
      Object.assign(art, a);
      return art;
    });
  } else {
    staff.showTablature = true;
    staff.showStandardNotation = true;
    // alphaTab stores tunings highest-string-first; the skill passes them
    // low-first because that is how players say them out loud.
    staff.stringTuning.tunings = [...trackSpec.tuning].reverse();
  }

  for (let barIndex = 0; barIndex < barCount; barIndex++) {
    const bar = new M.Bar();
    staff.addBar(bar);
    const voice = new M.Voice();
    bar.addVoice(voice);

    const barSpec = trackSpec.bars[barIndex];
    const beats = barSpec?.beats ?? [];

    if (beats.length === 0) {
      const rest = new M.Beat();
      rest.duration = M.Duration.Whole;
      rest.isEmpty = false;
      voice.addBeat(rest);
      continue;
    }

    for (const beatSpec of beats) {
      const beat = new M.Beat();
      beat.duration = DURATIONS[beatSpec.duration] ?? M.Duration.Quarter;
      beat.dots = beatSpec.dots ?? 0;
      if (beatSpec.tuplet) {
        beat.tupletNumerator = 3;
        beat.tupletDenominator = 2;
      }
      if (beatSpec.text) beat.text = beatSpec.text;
      voice.addBeat(beat);

      for (const noteSpec of beatSpec.notes ?? []) {
        const note = new M.Note();
        if (isPercussion) {
          note.percussionArticulation = noteSpec.articulation ?? 0;
          // Guitar Pro positions a drum note on the staff from its String and
          // Fret properties, not from the articulation alone. alphaTab drops
          // both on import and does not regenerate them, so a drum note
          // exported without them is missing the fields Guitar Pro needs and
          // takes the application down when it lays the staff out. Setting
          // them here makes the exporter emit the properties.
          if (noteSpec.string !== undefined) note.string = noteSpec.string;
          if (noteSpec.fret !== undefined) note.fret = noteSpec.fret;
          beat.addNote(note);
          continue;
        }
        // alphaTab numbers strings 1 = lowest, the reverse of Guitar Pro's
        // 1 = highest. Flip here so the caller never has to think about it.
        note.string = trackSpec.tuning.length - noteSpec.string + 1;
        note.fret = noteSpec.fret;
        if (noteSpec.palmMute) note.isPalmMute = true;
        if (noteSpec.letRing) note.isLetRing = true;
        if (noteSpec.vibrato) note.vibrato = M.VibratoType.Slight;
        if (noteSpec.hammer) note.isHammerPullOrigin = true;
        if (noteSpec.ghost) note.isGhost = true;
        if (noteSpec.dead) note.isDead = true;
        if (noteSpec.harmonic) {
          // "6p" in a hand-written tab means a pinch harmonic, not a natural
          // one -- they are different symbols and different techniques.
          note.harmonicType = noteSpec.pinch ? M.HarmonicType.Pinch : M.HarmonicType.Natural;
          note.harmonicValue = 0;
        }
        if (noteSpec.slide) note.slideOutType = M.SlideOutType.Shift;
        if (noteSpec.bend) {
          note.bendType = M.BendType.Bend;
          note.addBendPoint(new M.BendPoint(0, 0));
          note.addBendPoint(new M.BendPoint(30, 4));
          note.addBendPoint(new M.BendPoint(60, 4));
        }
        beat.addNote(note);
      }
    }
  }
}

// Lyrics are deliberately NOT applied here. alphaTab's GP7 exporter writes
// them wrongly -- each line truncated to its first word, every Offset set to
// the number of blocks instead of a bar number, and one line per block where
// Guitar Pro has exactly five. The result crashes Guitar Pro on open. The
// Python side writes the lyric block into the GPIF afterwards instead; see
// repair_gpif() in gp_tab.py.

score.finish(new alphaTab.Settings());

const exporter = new alphaTab.exporter.Gp7Exporter();
const bytes = exporter.export(score, new alphaTab.Settings());
writeFileSync(outputPath, Buffer.from(bytes));
console.log(`wrote ${outputPath}`);
