#!/usr/bin/env python3
"""Minimal client for the AbletonMCP remote script's socket (127.0.0.1:9877).

Sends {"type": ..., "params": {...}} and returns the decoded reply. Track and
clip indices are 0-based. Only apply_moves.py and collateral.py --live use this;
every other script in the skill works offline from the saved .als.
"""
from __future__ import annotations

import json
import socket

HOST, PORT = '127.0.0.1', 9877


class LiveError(RuntimeError):
    pass


def call(cmd, host=HOST, port=PORT, timeout=60.0, **params):
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(json.dumps({'type': cmd, 'params': params}).encode())
        buf = b''
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            try:
                reply = json.loads(buf.decode())
                break
            except ValueError:
                continue
        else:
            reply = None
    if not reply:
        raise LiveError(f'{cmd}: no reply from Live (is the AbletonMCP control surface loaded?)')
    if reply.get('status') == 'error':
        raise LiveError(f'{cmd}: {reply.get("message")}')
    return reply.get('result', reply)


def arrangement(host=HOST, port=PORT, track_index=-1):
    """get_arrangement_info: {'transport': {...}, 'tracks': [{index, name, arrangement_clips: [...]}, ...]}."""
    return call('get_arrangement_info', host, port, track_index=track_index)
