#!/usr/bin/env python3
"""Read, round-trip-verify, edit and write Neural DSP preset files.

A Neural DSP preset `.xml` (Archetype Gojira X, Fortin Nameless Suite X, and
the other Archetype/Suite plugins) is a JUCE ValueTree in its binary
`writeToStream` form, despite the extension. Layout per tree:

    typeName\\0, CompressedInt numProps, props (name\\0, var),
    CompressedInt numChildren, children

var = CompressedInt numBytes, marker, payload. Markers: 1 int, 2 true,
3 false, 4 double, 5 string (\\0-terminated), 6 int64. CompressedInt is one
count byte n (high bit = negative) followed by n little-endian bytes.

Every load re-serializes the tree and asserts it reproduces the file byte for
byte, so a file this module cannot represent exactly is refused, not
rewritten.

Usage (standard library only):
  python3 -I ndsp_preset.py PRESET.xml             # dump path, key, type, value
  python3 -I ndsp_preset.py PRESET.xml | rg leadEQ # filter the dump
"""
import argparse
import struct
import sys


def read_cint(b, i):
    n = b[i]
    i += 1
    neg = bool(n & 0x80)
    n &= 0x7F
    v = int.from_bytes(b[i:i + n], 'little') if n else 0
    return (-v if neg else v), i + n


def write_cint(v):
    neg = v < 0
    v = abs(v)
    raw = v.to_bytes((v.bit_length() + 7) // 8, 'little') if v else b''
    return bytes([len(raw) | (0x80 if neg else 0)]) + raw


def read_cstr(b, i):
    j = b.index(0, i)
    return b[i:j].decode('utf-8'), j + 1


def read_var(b, i):
    n, i = read_cint(b, i)
    payload = b[i:i + n]
    i += n
    m = payload[0]
    if m == 5:
        return ('s', payload[1:-1].decode('utf-8')), i
    if m == 2:
        return ('b', True), i
    if m == 3:
        return ('b', False), i
    if m == 1:
        return ('i', struct.unpack('<i', payload[1:5])[0]), i
    if m == 4:
        return ('d', struct.unpack('<d', payload[1:9])[0]), i
    if m == 6:
        return ('l', struct.unpack('<q', payload[1:9])[0]), i
    return ('raw', payload.hex()), i


def write_var(t, v):
    if t == 's':
        p = b'\x05' + v.encode('utf-8') + b'\x00'
    elif t == 'b':
        p = b'\x02' if v else b'\x03'
    elif t == 'i':
        p = b'\x01' + struct.pack('<i', v)
    elif t == 'd':
        p = b'\x04' + struct.pack('<d', v)
    elif t == 'l':
        p = b'\x06' + struct.pack('<q', v)
    else:
        p = bytes.fromhex(v)
    return write_cint(len(p)) + p


def read_tree(b, i=0):
    name, i = read_cstr(b, i)
    nprops, i = read_cint(b, i)
    props = []
    for _ in range(nprops):
        k, i = read_cstr(b, i)
        (t, v), i = read_var(b, i)
        props.append([k, t, v])
    nch, i = read_cint(b, i)
    kids = []
    for _ in range(nch):
        c, i = read_tree(b, i)
        kids.append(c)
    return {'name': name, 'props': props, 'kids': kids}, i


def write_tree(t):
    out = t['name'].encode('utf-8') + b'\x00' + write_cint(len(t['props']))
    for k, ty, v in t['props']:
        out += k.encode('utf-8') + b'\x00' + write_var(ty, v)
    out += write_cint(len(t['kids']))
    for c in t['kids']:
        out += write_tree(c)
    return out


def walk(t, path=''):
    p = f"{path}/{t['name']}"
    for k, ty, v in t['props']:
        yield p, k, ty, v
    for c in t['kids']:
        yield from walk(c, p)


def load(path):
    """Return (tree, trailing_bytes); refuse a file that does not round-trip."""
    with open(path, 'rb') as fh:
        b = fh.read()
    t, end = read_tree(b)
    if write_tree(t) != b[:end]:
        raise ValueError(f"{path}: round-trip mismatch, refusing to edit it")
    return t, b[end:]


def coerce(ty, value):
    """Convert a value given as text to the type the template already holds."""
    if ty == 's':
        return str(value)
    if ty == 'b':
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ('1', 'true', 'yes', 'on')
    if ty in ('i', 'l'):
        return int(value)
    if ty == 'd':
        return float(value)
    raise ValueError(f"cannot set a property of raw type {ty!r}")


def set_values(tree, values):
    """Set props in place. A key is `prop` or `prop@node` (node = the
    ValueTree type name holding it, e.g. `sectionActive@pedalParameters`).
    A scoped key wins over a bare one. Returns the set of keys applied."""
    done = set()

    def apply(node):
        for p in node['props']:
            for key in (f"{p[0]}@{node['name']}", p[0]):
                if key in values:
                    p[2] = coerce(p[1], values[key])
                    done.add(key)
                    break
        for c in node['kids']:
            apply(c)

    apply(tree)
    return done


def get_values(tree, keys):
    """Return {key: [values...]} for `prop` or `prop@node` keys. A scoped
    key wins over a bare one, as in set_values."""
    found = {k: [] for k in keys}
    for path, k, ty, v in walk(tree):
        node = path.rsplit('/', 1)[-1]
        for key in (f"{k}@{node}", k):
            if key in found:
                found[key].append(v)
                break
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('preset')
    a = ap.parse_args()
    t, tail = load(a.preset)
    for p, k, ty, v in walk(t):
        print(f"{p}\t{k}\t{ty}\t{v}")
    print(f"# round-trip ok; trailing bytes: {len(tail)}")


if __name__ == '__main__':
    sys.exit(main())
