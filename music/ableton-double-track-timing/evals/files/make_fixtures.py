#!/usr/bin/env python3
"""Generate offline timing eval inputs: python3 make_fixtures.py OUTDIR.

Uses only the standard library. Writes clean-control.als, planted-nudge.als,
full-audit.als and five tiny PCM WAVs, all synthetic, with relative sample paths.
The gzipped XML contains the Live fields read by the bundled offline scripts;
it is a parser fixture, not a complete project intended to open in Live.

Ground truth (120 BPM, 4/4):
* Clean: all doubled attacks coincide; repeated sections start at 4, 12, 20, 28.
* Planted: Scratch A at 20 and 28 moves +0.0625 beat (+31.25 ms).
* Audit: Rhythm R at 19.96 is -0.04 beat (-20 ms) against its copies;
  Audio R has +20 ms inside its source WAV, invisible to clip placement;
  Scratch A/B both have deliberate half-beat slices at 36.5, 40.5, 44.5,
  plus four on-grid copies of the same slice take. Clean L/R stays clean.

No recordings, source sets, Live process, or network are used. These sparse
signals exercise attack correlation, not dense-riff realism or amp renders.
"""
from __future__ import annotations

import argparse
import gzip
import math
from pathlib import Path
import struct
import wave
import xml.etree.ElementTree as ET


def write_audio(path: Path, frequency: float, delay: float = 0.0) -> None:
    """Write irregular, gated tone bursts with a known attack delay."""
    rate = 8000
    onsets = (0.16, 0.39, 0.73, 1.08, 1.49, 1.82)
    data = bytearray()
    for i in range(int(2.1 * rate)):
        t = i / rate - delay
        value = 0.0
        for onset in onsets:
            age = t - onset
            if 0 <= age < 0.08:
                value = 0.65 * math.sin(2 * math.pi * frequency * age)
                break
        data.extend(struct.pack('<h', round(value * 32767)))
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        wav.writeframes(data)


def value(parent: ET.Element, tag: str, val: object) -> None:
    ET.SubElement(parent, tag, Value=str(val))


def add_track(parent: ET.Element, index: int, name: str, sample: str,
              starts: list[float], slices: bool = False) -> None:
    track = ET.SubElement(parent, 'AudioTrack', Id=str(index))
    value(ET.SubElement(track, 'Name'), 'EffectiveName', name)
    chain = ET.SubElement(track, 'DeviceChain')
    value(ET.SubElement(ET.SubElement(chain, 'Mixer'), 'Speaker'), 'Manual', 'true')
    seq = ET.SubElement(chain, 'MainSequencer')
    events = ET.SubElement(ET.SubElement(ET.SubElement(seq, 'Sample'), 'ArrangerAutomation'), 'Events')
    clips = [(s, sample) for s in starts]
    if slices:
        clips += [(s, sample.replace('.wav', '-slice.wav'))
                  for s in (36.5, 40.5, 44.5, 52, 56, 60, 64)]
    for i, (start, file) in enumerate(clips):
        clip = ET.SubElement(events, 'AudioClip', Id=str(index * 100 + i), Time=str(start))
        for tag, val in [('CurrentStart', start), ('CurrentEnd', start + 4),
                         ('Name', name + ' phrase'), ('Disabled', 'false'), ('IsWarped', 'true')]:
            value(clip, tag, val)
        loop = ET.SubElement(clip, 'Loop')
        for tag, val in [('LoopStart', 0), ('LoopEnd', 4), ('StartRelative', 0), ('LoopOn', 'false')]:
            value(loop, tag, val)
        ref = ET.SubElement(ET.SubElement(clip, 'SampleRef'), 'FileRef')
        value(ref, 'Path', '')
        value(ref, 'RelativePath', 'Samples/' + file)
        markers = ET.SubElement(clip, 'WarpMarkers')
        for j, (sec, beat) in enumerate(((0, 0), (2, 4))):
            ET.SubElement(markers, 'WarpMarker', Id=str(j), SecTime=str(sec), BeatTime=str(beat))


def write_set(path: Path, kind: str) -> None:
    """Write only generated XML, with a constant tempo and relative file refs."""
    root = ET.Element('Ableton', MajorVersion='5', MinorVersion='12.0_12000')
    live = ET.SubElement(root, 'LiveSet')
    tracks = ET.SubElement(live, 'Tracks')
    starts = [4, 12, 20, 28]
    for i, (name, sample) in enumerate((('Scratch A', 'a.wav'), ('Scratch B', 'b.wav'),
                                       ('Rhythm L', 'a.wav'), ('Rhythm R', 'b.wav'),
                                       ('Clean L', 'a.wav'), ('Clean R', 'b.wav'),
                                       ('Audio L', 'a.wav'), ('Audio R', 'b.wav'))):
        positions = starts.copy()
        if kind == 'planted' and name == 'Scratch A':
            positions[2:] = [20.0625, 28.0625]
        if kind == 'audit':
            if name == 'Rhythm R':
                positions[2] = 19.96
            if name == 'Audio R':
                sample = 'delayed.wav'
        add_track(tracks, i, name, sample, positions, slices=kind == 'audit' and i < 2)
    tempo = ET.SubElement(ET.SubElement(ET.SubElement(
        ET.SubElement(live, 'MainTrack'), 'DeviceChain'), 'Mixer'), 'Tempo')
    value(tempo, 'Manual', 120)
    ET.SubElement(tempo, 'AutomationTarget', Id='1000')
    path.write_bytes(gzip.compress(ET.tostring(root, encoding='utf-8', xml_declaration=True), mtime=0))


def build(outdir: Path) -> None:
    """Build the same portable fixture bytes in any output directory."""
    samples = outdir / 'Samples'
    samples.mkdir(parents=True, exist_ok=True)
    for name, frequency, delay in [('a.wav', 200, 0), ('b.wav', 300, 0),
                                    ('delayed.wav', 300, 0.020),
                                    ('a-slice.wav', 200, 0), ('b-slice.wav', 300, 0)]:
        write_audio(samples / name, frequency, delay)
    for name, kind in [('clean-control.als', 'clean'), ('planted-nudge.als', 'planted'),
                       ('full-audit.als', 'audit')]:
        write_set(outdir / name, kind)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('outdir', type=Path)
    args = parser.parse_args()
    build(args.outdir)
    print(f'Synthetic timing fixtures written to {args.outdir}')


if __name__ == '__main__':
    main()
