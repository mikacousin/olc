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
"""GDTF (General Device Type Format, DIN SPEC 15800) import adapter."""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional

from .color import FixtureColorProfile, extract_color_profile
from .device import ChannelRange, ChannelType, FixtureType
from .fixture import ChannelDefinition, DmxModeDefinition, FixtureDefinition

try:
    import pygdtf

    HAS_PYGDTF = True
except ImportError:
    pygdtf = None  # type: ignore[assignment]
    HAS_PYGDTF = False

GDTF_ATTRIBUTE_MAP: dict[str, ChannelType] = {
    "Dimmer": ChannelType.INTENSITY,
    "Shutter1": ChannelType.STROBE,
    "Shutter1Strobe": ChannelType.STROBE,
    "Shutter2": ChannelType.STROBE,
    "Pan": ChannelType.PAN,
    "Tilt": ChannelType.TILT,
    "ColorAdd_R": ChannelType.RED,
    "ColorRGB_Red": ChannelType.RED,
    "ColorAdd_G": ChannelType.GREEN,
    "ColorRGB_Green": ChannelType.GREEN,
    "ColorAdd_B": ChannelType.BLUE,
    "ColorRGB_Blue": ChannelType.BLUE,
    "ColorAdd_W": ChannelType.WHITE,
    "ColorAdd_WW": ChannelType.WHITE,
    "ColorAdd_CW": ChannelType.WHITE,
    "ColorAdd_A": ChannelType.AMBER,
    "ColorAdd_UV": ChannelType.GENERIC,
    "Color1": ChannelType.COLOR_WHEEL,
    "Color1WheelSpin": ChannelType.COLOR_WHEEL,
    "Color2": ChannelType.COLOR_WHEEL,
    "Gobo1": ChannelType.GOBO_WHEEL,
    "Gobo1WheelSpin": ChannelType.GOBO_WHEEL,
    "Gobo1WheelIndex": ChannelType.GOBO_WHEEL,
    "Gobo2": ChannelType.GOBO_WHEEL,
    "Zoom": ChannelType.ZOOM,
    "Focus1": ChannelType.FOCUS,
    "Iris": ChannelType.IRIS,
    "Prism1": ChannelType.PRISM,
    "Control": ChannelType.MACRO,
    "Effects1": ChannelType.MACRO,
    "ColorMacro1": ChannelType.MACRO,
    "Reset": ChannelType.RESET,
}

_FIXTURE_TYPE_KEYWORDS: list[tuple[str, FixtureType]] = [
    ("moving head", FixtureType.MOVING_HEAD),
    ("movinghead", FixtureType.MOVING_HEAD),
    ("spot", FixtureType.MOVING_HEAD),
    ("beam", FixtureType.MOVING_HEAD),
    ("wash", FixtureType.MOVING_HEAD),
    ("led par", FixtureType.LED_PAR),
    ("par", FixtureType.LED_PAR),
    ("strobe", FixtureType.STROBE),
    ("laser", FixtureType.LASER),
    ("dimmer", FixtureType.DIMMER),
]


def _attr_to_channel_type(attr: str) -> ChannelType:
    return GDTF_ATTRIBUTE_MAP.get(attr, ChannelType.GENERIC)


def _infer_fixture_type(name: str, description: str = "") -> FixtureType:
    text = (name + " " + description).lower()
    for keyword, ftype in _FIXTURE_TYPE_KEYWORDS:
        if keyword in text:
            return ftype
    return FixtureType.GENERIC


class GdtfImporter:
    """Imports GDTF archives and creates FixtureDefinition instances."""

    def load(self, path: str | Path) -> FixtureDefinition:
        """Load a .gdtf file from disk."""
        if not HAS_PYGDTF or pygdtf is None:
            raise ImportError(
                "pygdtf is required to import GDTF files. "
                "Install it with 'pip install pygdtf'."
            )
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"GDTF file not found: {path}")
        gdtf_obj = pygdtf.FixtureType(str(path))
        thumbnail = self._read_thumbnail(path)
        return self._adapt(gdtf_obj, thumbnail)

    def load_from_bytes(self, data: bytes) -> FixtureDefinition:
        """Load a .gdtf file from raw bytes."""
        if not HAS_PYGDTF:
            raise ImportError(
                "pygdtf is required to import GDTF files. "
                "Install it with 'pip install pygdtf'."
            )
        with tempfile.NamedTemporaryFile(suffix=".gdtf", delete=False) as f:
            f.write(data)
            tmp_path = f.name
        try:
            return self.load(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _adapt(
        self,
        gdtf_obj: Any,  # noqa: ANN401
        thumbnail: Optional[bytes],
    ) -> FixtureDefinition:
        fixture_type = _infer_fixture_type(
            getattr(gdtf_obj, "name", ""),
            getattr(gdtf_obj, "description", ""),
        )

        dmx_modes = [self._adapt_mode(m) for m in getattr(gdtf_obj, "dmx_modes", [])]

        color_profile: Optional[FixtureColorProfile] = None
        try:
            color_profile = extract_color_profile(gdtf_obj)
        except ValueError:
            pass

        return FixtureDefinition(
            manufacturer=getattr(gdtf_obj, "manufacturer", "Unknown"),
            model=getattr(gdtf_obj, "name", "Unknown"),
            fixture_type=fixture_type,
            dmx_modes=dmx_modes,
            color_profile=color_profile,
            gdtf_id=str(getattr(gdtf_obj, "fixture_type_id", "")),
            thumbnail=thumbnail,
            notes=getattr(gdtf_obj, "description", ""),
        )

    def _adapt_mode(self, mode: Any) -> DmxModeDefinition:  # noqa: ANN401
        channel_defs: list[ChannelDefinition] = []
        dmx_channels = getattr(mode, "dmx_channels", None)
        if dmx_channels and hasattr(dmx_channels, "as_dict"):
            for ch_dict in dmx_channels.as_dict():
                if ch_dict.get("attribute", "").startswith("+"):
                    continue  # Fine 16-bit channel, handled by coarse offset
                ch_def = self._adapt_channel(ch_dict)
                if ch_def:
                    channel_defs.append(ch_def)
        return DmxModeDefinition(
            name=getattr(mode, "name", "Default"), channel_defs=channel_defs
        )

    def _adapt_channel(self, ch: dict[str, Any]) -> Optional[ChannelDefinition]:
        attr_name = ch.get("attribute", "NoFeature")
        if attr_name in ("NoFeature", ""):
            return None

        offsets = ch.get("offset", [1])
        offset = offsets[0] - 1  # 0-based
        fine_offset = offsets[1] - 1 if len(offsets) > 1 else None
        default_val = ch.get("default", 0)

        all_functions: list[dict[str, Any]] = []
        for lc in ch.get("logical_channels", []):
            all_functions.extend(lc.get("channel_functions", []))

        real_functions = [
            cf
            for cf in all_functions
            if cf.get("attribute", "NoFeature") not in ("NoFeature", "")
            and not (
                cf.get("dmx_from", 0) == 0
                and cf.get("dmx_to", 0) == 0
                and len(all_functions) > 1
            )
        ]

        if len(real_functions) <= 1:
            return ChannelDefinition(
                channel_type=_attr_to_channel_type(attr_name),
                offset=offset,
                label=attr_name,
                default_value=default_val,
                fine_offset=fine_offset,
            )

        ranges = [r for r in map(self._adapt_function, real_functions) if r is not None]
        if not ranges:
            return None

        types = {r.channel_type for r in ranges}
        ch_type = types.pop() if len(types) == 1 else ChannelType.GENERIC

        return ChannelDefinition(
            channel_type=ch_type,
            offset=offset,
            label=attr_name,
            default_value=default_val,
            fine_offset=fine_offset,
            ranges=ranges,
        )

    def _adapt_function(self, cf: dict[str, Any]) -> Optional[ChannelRange]:
        attr = cf.get("attribute", "NoFeature")
        if attr in ("NoFeature", ""):
            return None

        name = cf.get("name", attr)
        dmx_from = cf.get("dmx_from", 0)
        dmx_to = cf.get("dmx_to", 255)
        default = cf.get("default", dmx_from)

        snap_names = [cs["name"] for cs in cf.get("channel_sets", []) if cs.get("name")]

        return ChannelRange(
            label=name,
            channel_type=_attr_to_channel_type(attr),
            value_min=min(dmx_from, dmx_to),
            value_max=max(dmx_from, dmx_to),
            snap_value=default,
            description=", ".join(snap_names) if snap_names else name,
        )

    @staticmethod
    def _read_thumbnail(gdtf_path: Path) -> Optional[bytes]:
        try:
            with zipfile.ZipFile(gdtf_path) as zf:
                for name in ("thumbnail.png", "thumbnail.svg"):
                    if name in zf.namelist():
                        return zf.read(name)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return None
