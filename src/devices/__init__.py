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
"""Devices subsystem for OpenLightingConsole.

Includes fixtures, color calibration, GDTF, and patch management.
"""

from .builtin import (
    create_dimmer_definition,
    create_moving_head_definition,
    create_rgb_definition,
    create_rgba_definition,
    create_rgbw_definition,
    populate_builtin_library,
)
from .color import (
    CIEXYZ,
    CIExyY,
    ColorMatcher,
    EmitterProfile,
    FixtureColorProfile,
    MatchResult,
    delta_e76,
    extract_color_profile,
    profile_from_emitters,
    sRGB,
)
from .device import (
    COLOR_CHANNEL_TYPES,
    Channel,
    ChannelRange,
    ChannelType,
    DmxAddress,
    FixtureType,
    LightingDevice,
)
from .fixture import (
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
    FixtureLibrary,
)
from .gdtf import (
    GDTF_ATTRIBUTE_MAP,
    HAS_PYGDTF,
    GdtfImporter,
)

__all__ = [
    # device
    "DmxAddress",
    "ChannelType",
    "ChannelRange",
    "Channel",
    "FixtureType",
    "LightingDevice",
    "COLOR_CHANNEL_TYPES",
    # fixture
    "ChannelDefinition",
    "DmxModeDefinition",
    "FixtureDefinition",
    "FixtureLibrary",
    # builtin
    "create_dimmer_definition",
    "create_moving_head_definition",
    "create_rgb_definition",
    "create_rgbw_definition",
    "create_rgba_definition",
    "populate_builtin_library",
    # gdtf
    "GdtfImporter",
    "GDTF_ATTRIBUTE_MAP",
    "HAS_PYGDTF",
    # color
    "CIExyY",
    "CIEXYZ",
    "sRGB",
    "EmitterProfile",
    "FixtureColorProfile",
    "ColorMatcher",
    "MatchResult",
    "extract_color_profile",
    "profile_from_emitters",
    "delta_e76",
]

__version__ = "0.1.0"
