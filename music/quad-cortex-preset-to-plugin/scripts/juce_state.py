#!/usr/bin/env python3
"""JUCE VST3 wrapper state <-> inner plugin state (MemoryBlock base64 variant).

What `pedalboard`'s `plugin.raw_state` holds for a JUCE VST3:

    b"VC2!" + uint32 LE size + XML
      <VST3PluginState><IComponent>N.base64</IComponent>...</VST3PluginState>
    + a verbatim tail (JUCEPrivateData)

The IComponent text is a JUCE MemoryBlock in JUCE's own base64: alphabet
".ABC...XYZabc...xyz0123456789+", 6-bit groups packed least significant bit
first, prefixed with the byte count and a dot. For Neural DSP plugins the
decoded bytes are again "VC2!" + size + an `<appModel>` XML document whose
node tree matches the preset file's `appModel` subtree.

Imported by render_chain.py. As a command it decodes a saved raw state:
  python3 -I juce_state.py STATE.bin    # prints the inner plugin state XML
(save one with `open('STATE.bin','wb').write(plugin.raw_state)`).
"""
import re
import struct
import sys

TABLE = ".ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+"
IDX = {c: i for i, c in enumerate(TABLE)}


def mb_decode(s):
    n, rest = s.split('.', 1)
    n = int(n)
    v = 0
    pos = 0
    for c in rest:
        if c in IDX:
            v |= IDX[c] << pos
            pos += 6
    return (v & ((1 << (8 * n)) - 1)).to_bytes(n, 'little')


def mb_encode(b):
    v = int.from_bytes(b, 'little')
    nch = (len(b) * 8 + 5) // 6
    return f"{len(b)}." + ''.join(TABLE[(v >> (6 * i)) & 63] for i in range(nch))


def split(raw):
    if raw[:4] != b'VC2!':
        raise ValueError("plugin state is not a JUCE VC2! block")
    n = struct.unpack('<I', raw[4:8])[0]
    xml = raw[8:8 + n].decode('utf-8')
    return xml, raw[8 + n:]


def components(xml):
    return {m.group(1): m.group(2) for m in re.finditer(r'<(\w+)>([^<]*)</\1>', xml)}


def replace_component(raw, inner, tag='IComponent'):
    xml, tail = split(raw)
    xml2 = re.sub(rf'<{tag}>[^<]*</{tag}>', f'<{tag}>{mb_encode(inner)}</{tag}>', xml)
    body = xml2.encode('utf-8')
    return b'VC2!' + struct.pack('<I', len(body)) + body + tail


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: juce_state.py STATE.bin")
    with open(sys.argv[1], 'rb') as fh:
        raw = fh.read()
    inner = mb_decode(components(split(raw)[0])['IComponent'])
    if inner[:4] == b'VC2!':
        n = struct.unpack('<I', inner[4:8])[0]
        print(inner[8:8 + n].decode('utf-8'))
        print(f"# trailing private data: {len(inner) - 8 - n} bytes", file=sys.stderr)
    else:
        sys.stdout.buffer.write(inner)
    return 0


if __name__ == '__main__':
    sys.exit(main())
