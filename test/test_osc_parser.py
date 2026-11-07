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
"""Tests for OSC argument normalization and parser utilities."""

from __future__ import annotations

import pytest

from olc.core.backends.osc.parser import (
    parse_osc_bool,
    parse_osc_level_dmx,
    parse_osc_normalized,
)


def test_parse_osc_normalized_floats() -> None:
    """Test normalized float parsing within [0.0, 1.0]."""
    assert parse_osc_normalized(0.0) == 0.0
    assert parse_osc_normalized(0.5) == 0.5
    assert parse_osc_normalized(1.0) == 1.0
    assert pytest.approx(parse_osc_normalized(0.7534)) == 0.7534


def test_parse_osc_normalized_legacy_dmx_scale() -> None:
    """Test legacy DMX integers and floats (> 1.0) are properly normalized."""
    assert parse_osc_normalized(255) == 1.0
    assert parse_osc_normalized(255.0) == 1.0
    assert pytest.approx(parse_osc_normalized(128)) == 128 / 255.0
    assert parse_osc_normalized(512) == 1.0  # Clamped to 1.0


def test_parse_osc_normalized_special_and_releases() -> None:
    """Test release signals, booleans, and string representations."""
    assert parse_osc_normalized(-1) == -1.0
    assert parse_osc_normalized(-1.0) == -1.0
    assert parse_osc_normalized(True) == 1.0
    assert parse_osc_normalized(False) == 0.0
    assert parse_osc_normalized(None) == 0.0

    # Strings
    assert parse_osc_normalized("FULL") == 1.0
    assert parse_osc_normalized("out") == 0.0
    assert parse_osc_normalized("zero") == 0.0
    assert parse_osc_normalized("release") == -1.0
    assert pytest.approx(parse_osc_normalized("0.65")) == 0.65
    assert parse_osc_normalized("invalid_string") == 0.0


def test_parse_osc_level_dmx() -> None:
    """Test conversion to 8-bit DMX integer scale."""
    assert parse_osc_level_dmx(1.0) == 255
    assert parse_osc_level_dmx(0.0) == 0
    assert parse_osc_level_dmx(0.5) == 128
    assert parse_osc_level_dmx(255) == 255
    assert parse_osc_level_dmx(128) == 128
    assert parse_osc_level_dmx(-1) == -1


def test_parse_osc_bool() -> None:
    """Test boolean and trigger parsing."""
    assert parse_osc_bool(True) is True
    assert parse_osc_bool(False) is False
    assert parse_osc_bool(1) is True
    assert parse_osc_bool(0) is False
    assert parse_osc_bool(1.0) is True
    assert parse_osc_bool(0.0) is False
    assert parse_osc_bool(None) is False

    assert parse_osc_bool("true") is True
    assert parse_osc_bool("ON") is True
    assert parse_osc_bool("press") is True
    assert parse_osc_bool("down") is True
    assert parse_osc_bool("false") is False
    assert parse_osc_bool("off") is False
