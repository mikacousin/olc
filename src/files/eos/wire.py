# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2026 Mika Cousin <mika.cousin@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Binary wire-format decoder and encoder for ETC Eos ``showdat.dat``."""

from __future__ import annotations

import struct
from typing import Any

OBJ_MARKER = "OBJ"


def _ensure_bytes(data: bytes, pos: int, count: int) -> None:
    if pos + count > len(data):
        raise ValueError(
            f"Unexpected end of showdat stream at offset {pos} (need {count} bytes)"
        )


def decode_showdat(data: bytes) -> tuple[int, list[Any]]:
    """Decode an ETC Eos ``showdat.dat`` binary stream.

    Args:
        data: Raw bytes of ``showdat.dat``.

    Returns:
        Tuple ``(version_header, tree)`` where ``version_header`` is the
        4-byte little-endian header integer (e.g. ``0x76`` or ``0x78``) and
        ``tree`` is the decoded nested list representation.
    """
    if len(data) < 4:
        raise ValueError("showdat.dat is too short (missing 4-byte header)")

    header = struct.unpack_from("<I", data, 0)[0]
    pos = 4
    total = len(data)
    stack: list[list[Any]] = [[]]

    while pos < total:
        tag_pos = pos
        tag = data[pos]
        pos += 1

        if tag == 0x00:
            stack[-1].append(0)
        elif tag == 0x01:
            _ensure_bytes(data, pos, 1)
            ver = data[pos]
            pos += 1
            obj: list[Any] = [OBJ_MARKER, ver]
            stack[-1].append(obj)
            stack.append(obj)
        elif tag == 0x02:
            if len(stack) <= 1:
                raise ValueError(
                    f"Unbalanced container close tag 0x02 at offset {tag_pos}"
                )
            stack.pop()
        elif tag == 0x03:
            _ensure_bytes(data, pos, 2)
            char_count = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            byte_count = char_count * 2
            _ensure_bytes(data, pos, byte_count)
            text = data[pos : pos + byte_count].decode("utf-16le", errors="replace")
            pos += byte_count
            stack[-1].append(text)
        elif tag == 0x04:
            stack[-1].append(None)
        elif tag == 0x05:
            _ensure_bytes(data, pos, 4)
            val_f32 = struct.unpack_from("<f", data, pos)[0]
            pos += 4
            stack[-1].append(val_f32)
        elif tag == 0x06:
            _ensure_bytes(data, pos, 8)
            val_f64 = struct.unpack_from("<d", data, pos)[0]
            pos += 8
            stack[-1].append(val_f64)
        elif 0x08 <= tag <= 0x0F:
            size = tag - 0x07
            _ensure_bytes(data, pos, size)
            val_u = int.from_bytes(data[pos : pos + size], "little", signed=False)
            pos += size
            stack[-1].append(val_u)
        elif 0xF1 <= tag <= 0xF8:
            size = 0xF9 - tag
            _ensure_bytes(data, pos, size)
            val_neg = -int.from_bytes(data[pos : pos + size], "little", signed=False)
            pos += size
            stack[-1].append(val_neg)
        else:
            raise ValueError(f"Unknown showdat tag 0x{tag:02x} at offset {tag_pos}")

    if len(stack) != 1:
        raise ValueError(
            f"Unclosed showdat container(s): depth {len(stack) - 1} at EOF"
        )

    return header, stack[0]


def _encode_value(out: bytearray, value: object) -> None:
    if value is None:
        out.append(0x04)
    elif isinstance(value, bool):
        out.append(0x00 if not value else 0x08)
        if value:
            out.append(1)
    elif isinstance(value, int):
        if value == 0:
            out.append(0x00)
        elif value > 0:
            byte_len = max(1, (value.bit_length() + 7) // 8)
            if byte_len > 8:
                raise ValueError(f"Integer too large for showdat wire format: {value}")
            out.append(0x07 + byte_len)
            out.extend(value.to_bytes(byte_len, "little", signed=False))
        else:
            mag = -value
            byte_len = max(1, (mag.bit_length() + 7) // 8)
            if byte_len > 8:
                raise ValueError(f"Negative integer too large for showdat: {value}")
            out.append(0xF9 - byte_len)
            out.extend(mag.to_bytes(byte_len, "little", signed=False))
    elif isinstance(value, float):
        out.append(0x06)
        out.extend(struct.pack("<d", value))
    elif isinstance(value, str):
        raw = value.encode("utf-16le")
        char_count = len(raw) // 2
        if char_count > 0xFFFF:
            raise ValueError(f"String too long for showdat wire format: {char_count}")
        out.append(0x03)
        out.extend(struct.pack("<H", char_count))
        out.extend(raw)
    elif isinstance(value, list):
        if len(value) >= 2 and value[0] == OBJ_MARKER and isinstance(value[1], int):
            ver = value[1]
            if not 0 <= ver <= 255:
                raise ValueError(f"Invalid OBJ version byte: {ver}")
            out.append(0x01)
            out.append(ver)
            for item in value[2:]:
                _encode_value(out, item)
            out.append(0x02)
        else:
            for item in value:
                _encode_value(out, item)
    else:
        raise TypeError(
            f"Unsupported type for showdat encoding: {type(value).__name__}"
        )


def encode_showdat(version: int, tree: list[Any]) -> bytes:
    """Encode a nested Python tree into ETC Eos ``showdat.dat`` binary bytes.

    Args:
        version: 4-byte little-endian header integer (e.g. ``0x76`` or ``0x78``).
        tree: Top-level list of values / ``["OBJ", ver, ...]`` containers.

    Returns:
        Encoded binary bytes.
    """
    out = bytearray(struct.pack("<I", version))
    for item in tree:
        _encode_value(out, item)
    return bytes(out)
