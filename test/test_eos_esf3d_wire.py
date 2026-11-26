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
"""Unit tests for the ETC Eos ``showdat.dat`` binary wire codec."""

from __future__ import annotations

import pytest

from olc.files.eos.wire import decode_showdat, encode_showdat


@pytest.mark.parametrize("header", [0x76, 0x78])
def test_wire_roundtrip_all_types(header: int) -> None:
    """Round-trip all supported showdat wire types and headers."""
    tree = [
        ["OBJ", 0, 0, 1, 255, 65535, 1_000_000, -1, -55, -150000, None],
        ["OBJ", 1, "Cue élève 1", "Ayrton_Gobo_Wheel_3", 12.5, -0.25],
    ]
    encoded = encode_showdat(header, tree)
    dec_header, dec_tree = decode_showdat(encoded)
    assert dec_header == header
    assert dec_tree == tree


def test_wire_error_handling() -> None:
    """Reject truncated, unknown-tag, and unbalanced streams."""
    with pytest.raises(ValueError, match="too short"):
        decode_showdat(b"\x76\x00")

    with pytest.raises(ValueError, match="Unknown showdat tag"):
        decode_showdat(b"\x76\x00\x00\x00\x99")

    with pytest.raises(ValueError, match="Unbalanced"):
        decode_showdat(b"\x76\x00\x00\x00\x02")

    with pytest.raises(ValueError, match="Unclosed"):
        decode_showdat(b"\x76\x00\x00\x00\x01\x00")
