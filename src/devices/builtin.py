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
# pylint: disable=wrong-spelling-in-comment, wrong-spelling-in-docstring
"""Built-in generic fixture definitions (dimmers and generic LED fixtures)."""

from __future__ import annotations

from .color import profile_from_emitters
from .device import ChannelType, FixtureType
from .fixture import (
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
    FixtureLibrary,
)


def create_dimmer_definition(fine: bool = False) -> FixtureDefinition:
    """Create a generic dimmer fixture definition.

    Args:
        fine: If True, defaults to 16-bit mode (coarse + fine).
    """
    mode_8bit = DmxModeDefinition(
        name="8-bit",
        channel_defs=[
            ChannelDefinition(
                channel_type=ChannelType.INTENSITY,
                offset=0,
                label="Dimmer",
            )
        ],
        description="Standard 1-channel 8-bit dimmer",
    )

    mode_16bit = DmxModeDefinition(
        name="16-bit",
        channel_defs=[
            ChannelDefinition(
                channel_type=ChannelType.INTENSITY,
                offset=0,
                fine_offset=1,
                label="Dimmer",
            )
        ],
        description="High-resolution 2-channel 16-bit dimmer",
    )

    modes = [mode_16bit, mode_8bit] if fine else [mode_8bit, mode_16bit]
    model_name = "Dimmer 16-bit" if fine else "Dimmer"

    return FixtureDefinition(
        manufacturer="Generic",
        model=model_name,
        fixture_type=FixtureType.DIMMER,
        dmx_modes=modes,
        notes="Standard generic dimmer fixture",
    )


def create_rgb_definition() -> FixtureDefinition:
    """Create a generic RGB 3-channel fixture definition with sRGB color profile."""
    mode = DmxModeDefinition(
        name="RGB 3ch",
        channel_defs=[
            ChannelDefinition(ChannelType.RED, offset=0, label="Red"),
            ChannelDefinition(ChannelType.GREEN, offset=1, label="Green"),
            ChannelDefinition(ChannelType.BLUE, offset=2, label="Blue"),
        ],
        description="Standard 3-channel RGB fixture",
    )

    color_profile = profile_from_emitters(
        name="Generic LED RGB",
        emitters=[
            ("Red", 0.640, 0.330, 21.26, 625.0),
            ("Green", 0.300, 0.600, 71.52, 525.0),
            ("Blue", 0.150, 0.060, 7.22, 465.0),
        ],
    )

    return FixtureDefinition(
        manufacturer="Generic",
        model="LED RGB",
        fixture_type=FixtureType.LED_PAR,
        dmx_modes=[mode],
        color_profile=color_profile,
        notes="Generic 3-channel RGB LED fixture",
    )


def create_rgbw_definition() -> FixtureDefinition:
    """Create a generic RGBW 4-channel fixture definition."""
    mode = DmxModeDefinition(
        name="RGBW 4ch",
        channel_defs=[
            ChannelDefinition(ChannelType.RED, offset=0, label="Red"),
            ChannelDefinition(ChannelType.GREEN, offset=1, label="Green"),
            ChannelDefinition(ChannelType.BLUE, offset=2, label="Blue"),
            ChannelDefinition(ChannelType.WHITE, offset=3, label="White"),
        ],
        description="Standard 4-channel RGBW fixture",
    )

    color_profile = profile_from_emitters(
        name="Generic LED RGBW",
        emitters=[
            ("Red", 0.640, 0.330, 21.26, 625.0),
            ("Green", 0.300, 0.600, 71.52, 525.0),
            ("Blue", 0.150, 0.060, 7.22, 465.0),
            ("White", 0.3127, 0.3290, 100.0, 0.0),
        ],
    )

    return FixtureDefinition(
        manufacturer="Generic",
        model="LED RGBW",
        fixture_type=FixtureType.LED_PAR,
        dmx_modes=[mode],
        color_profile=color_profile,
        notes="Generic 4-channel RGBW LED fixture",
    )


def create_rgba_definition() -> FixtureDefinition:
    """Create a generic RGBA 4-channel fixture definition."""
    mode = DmxModeDefinition(
        name="RGBA 4ch",
        channel_defs=[
            ChannelDefinition(ChannelType.RED, offset=0, label="Red"),
            ChannelDefinition(ChannelType.GREEN, offset=1, label="Green"),
            ChannelDefinition(ChannelType.BLUE, offset=2, label="Blue"),
            ChannelDefinition(ChannelType.AMBER, offset=3, label="Amber"),
        ],
        description="Standard 4-channel RGBA fixture",
    )

    color_profile = profile_from_emitters(
        name="Generic LED RGBA",
        emitters=[
            ("Red", 0.640, 0.330, 21.26, 625.0),
            ("Green", 0.300, 0.600, 71.52, 525.0),
            ("Blue", 0.150, 0.060, 7.22, 465.0),
            ("Amber", 0.590, 0.400, 50.0, 590.0),
        ],
    )

    return FixtureDefinition(
        manufacturer="Generic",
        model="LED RGBA",
        fixture_type=FixtureType.LED_PAR,
        dmx_modes=[mode],
        color_profile=color_profile,
        notes="Generic 4-channel RGBA LED fixture",
    )


def populate_builtin_library(
    library: FixtureLibrary | None = None,
) -> FixtureLibrary:
    """Populate a FixtureLibrary with all built-in generic definitions."""
    lib = library if library is not None else FixtureLibrary()
    lib.register(create_dimmer_definition(fine=False))
    lib.register(create_dimmer_definition(fine=True))
    lib.register(create_rgb_definition())
    lib.register(create_rgbw_definition())
    lib.register(create_rgba_definition())
    return lib
