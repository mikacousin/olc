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
from .gobo import GoboAsset, resolve_builtin_gobo

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
    "ColorAdd_RY": ChannelType.RED,
    "ColorAdd_G": ChannelType.GREEN,
    "ColorRGB_Green": ChannelType.GREEN,
    "ColorAdd_B": ChannelType.BLUE,
    "ColorRGB_Blue": ChannelType.BLUE,
    "ColorAdd_W": ChannelType.WHITE,
    "ColorAdd_WW": ChannelType.WHITE,
    "ColorAdd_CW": ChannelType.WHITE,
    "ColorAdd_A": ChannelType.AMBER,
    "ColorAdd_GY": ChannelType.LIME,
    "ColorAdd_L": ChannelType.LIME,
    "ColorAdd_C": ChannelType.CYAN,
    "ColorSub_C": ChannelType.CYAN,
    "ColorAdd_BC": ChannelType.INDIGO,
    "ColorAdd_M": ChannelType.MAGENTA,
    "ColorSub_M": ChannelType.MAGENTA,
    "ColorAdd_Y": ChannelType.YELLOW,
    "ColorSub_Y": ChannelType.YELLOW,
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
    "Frost": ChannelType.FROST,
    "Frost1": ChannelType.FROST,
    "Frost2": ChannelType.FROST,
    "Control": ChannelType.MACRO,
    "Effects1": ChannelType.MACRO,
    "ColorMacro1": ChannelType.MACRO,
    "Reset": ChannelType.RESET,
    "ColorTemperature": ChannelType.COLOR_TEMP,
    "CTC": ChannelType.COLOR_TEMP,
    "CTC1": ChannelType.COLOR_TEMP,
    "CTO": ChannelType.COLOR_TEMP,
    "CTO1": ChannelType.COLOR_TEMP,
}

GDTF_PHYSICAL_DEFAULTS: dict[ChannelType, tuple[float, float, str]] = {
    ChannelType.PAN: (-270.0, 270.0, "deg"),
    ChannelType.TILT: (-135.0, 135.0, "deg"),
    ChannelType.ZOOM: (10.0, 40.0, "deg"),
    ChannelType.STROBE: (1.0, 25.0, "Hz"),
    ChannelType.FOCUS: (1.0, 50.0, "m"),
    ChannelType.COLOR_TEMP: (2700.0, 6500.0, "K"),
    ChannelType.INTENSITY: (0.0, 1.0, "%"),
    ChannelType.IRIS: (0.0, 100.0, "%"),
    ChannelType.FROST: (0.0, 100.0, "%"),
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


def _resolve_physical_bounds(
    ch_type: ChannelType, p_from: object, p_to: object
) -> tuple[float, float, str]:
    def_min, def_max, def_unit = GDTF_PHYSICAL_DEFAULTS.get(ch_type, (0.0, 1.0, ""))
    if isinstance(p_from, (int, float, str)) and isinstance(p_to, (int, float, str)):
        try:
            f_from = float(p_from)
            f_to = float(p_to)
            if (
                ch_type in (ChannelType.PAN, ChannelType.TILT)
                and f_from == 0.0
                and f_to == 1.0
            ):
                return def_min, def_max, def_unit
            if f_from != f_to:
                return f_from, f_to, def_unit
        except (ValueError, TypeError):
            pass
    return def_min, def_max, def_unit


def _resolve_bit_shift(functions: list[dict[str, Any]]) -> int:
    """Determine bit shift needed to downscale GDTF channel functions to 8-bit."""
    max_val = 0
    for cf in functions:
        for key in ("dmx_from", "dmx_to", "default"):
            val = cf.get(key)
            if isinstance(val, int) and val > max_val:
                max_val = val
    if max_val > 0xFFFFFF:
        return 24
    if max_val > 0xFFFF:
        return 16
    if max_val > 0xFF:
        return 8
    return 0


def _normalize_ranges(ranges: list[ChannelRange]) -> list[ChannelRange]:
    """Sort and clamp overlapping ChannelRanges so coarse 8-bit bounds are disjoint."""
    if len(ranges) <= 1:
        return ranges
    sorted_ranges = sorted(ranges, key=lambda r: (r.value_min, r.value_max))
    normalized: list[ChannelRange] = []
    prev_hi = -1
    for r in sorted_ranges:
        lo = r.value_min
        hi = r.value_max
        if lo <= prev_hi:
            lo = prev_hi + 1
        if lo > hi:
            continue
        snap = max(lo, min(hi, r.snap_value)) if r.snap_value is not None else None
        if lo != r.value_min or hi != r.value_max or snap != r.snap_value:
            normalized.append(
                ChannelRange(
                    label=r.label,
                    channel_type=r.channel_type,
                    value_min=lo,
                    value_max=hi,
                    snap_value=snap,
                    description=r.description,
                    physical_min=r.physical_min,
                    physical_max=r.physical_max,
                    physical_unit=r.physical_unit,
                    gobo_id=r.gobo_id,
                )
            )
        else:
            normalized.append(r)
        prev_hi = hi
    return normalized


class GdtfImporter:
    """Imports GDTF archives and creates FixtureDefinition instances."""

    def __init__(self) -> None:
        self.last_gobo_assets: dict[str, GoboAsset] = {}

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
        self.last_gobo_assets = self._read_wheel_gobos(path, gdtf_obj)
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
            getattr(gdtf_obj, "name", None) or "",
            getattr(gdtf_obj, "description", None) or "",
        )

        dmx_modes = [self._adapt_mode(m) for m in getattr(gdtf_obj, "dmx_modes", [])]

        color_profile: Optional[FixtureColorProfile] = None
        try:
            color_profile = extract_color_profile(gdtf_obj)
        except ValueError:
            pass

        return FixtureDefinition(
            manufacturer=getattr(gdtf_obj, "manufacturer", None) or "Unknown",
            model=getattr(gdtf_obj, "name", None) or "Unknown",
            fixture_type=fixture_type,
            dmx_modes=dmx_modes,
            color_profile=color_profile,
            gdtf_id=str(getattr(gdtf_obj, "fixture_type_id", None) or ""),
            thumbnail=thumbnail,
            notes=getattr(gdtf_obj, "description", None) or "",
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
            name=getattr(mode, "name", None) or "Default", channel_defs=channel_defs
        )

    def _adapt_channel(  # pylint: disable=too-many-locals
        self, ch: dict[str, Any]
    ) -> Optional[ChannelDefinition]:
        attr_name = ch.get("attribute", "NoFeature")
        if attr_name in ("NoFeature", ""):
            return None

        offsets = ch.get("offset")
        if not offsets or offsets[0] is None or offsets[0] <= 0:
            return None
        offset = offsets[0] - 1  # 0-based
        fine_offset = offsets[1] - 1 if len(offsets) > 1 else None
        ultra_fine_offset = offsets[2] - 1 if len(offsets) > 2 else None
        default_val = ch.get("default", 0)
        highlight_val = ch.get("highlight")

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

        target_cf = (
            real_functions[0]
            if real_functions
            else (all_functions[0] if all_functions else {})
        )
        p_from = target_cf.get("physical_from")
        p_to = target_cf.get("physical_to")

        if len(real_functions) <= 1:
            ch_type = _attr_to_channel_type(attr_name)
            phys_min, phys_max, phys_unit = _resolve_physical_bounds(
                ch_type, p_from, p_to
            )
            return ChannelDefinition(
                channel_type=ch_type,
                offset=offset,
                label=attr_name,
                default_value=default_val,
                highlight_value=highlight_val,
                fine_offset=fine_offset,
                ultra_fine_offset=ultra_fine_offset,
                physical_min=phys_min,
                physical_max=phys_max,
                physical_unit=phys_unit,
            )

        bit_shift = _resolve_bit_shift(real_functions)
        raw_ranges = [
            r
            for cf in real_functions
            if (r := self._adapt_function(cf, bit_shift)) is not None
        ]
        ranges = _normalize_ranges(raw_ranges)
        if not ranges:
            return None

        types = {r.channel_type for r in ranges}
        ch_type = types.pop() if len(types) == 1 else ChannelType.GENERIC
        phys_min, phys_max, phys_unit = _resolve_physical_bounds(ch_type, p_from, p_to)

        return ChannelDefinition(
            channel_type=ch_type,
            offset=offset,
            label=attr_name,
            default_value=default_val,
            highlight_value=highlight_val,
            fine_offset=fine_offset,
            ultra_fine_offset=ultra_fine_offset,
            ranges=ranges,
            physical_min=phys_min,
            physical_max=phys_max,
            physical_unit=phys_unit,
        )

    def _adapt_function(
        self, cf: dict[str, Any], bit_shift: int = 0
    ) -> Optional[ChannelRange]:
        attr = cf.get("attribute", "NoFeature")
        if attr in ("NoFeature", ""):
            return None

        name = cf.get("name") or attr
        raw_from = int(cf.get("dmx_from", 0))
        raw_to = int(cf.get("dmx_to", (256 << bit_shift) - 1))
        raw_default = cf.get("default")
        dmx_from = max(0, min(255, raw_from >> bit_shift))
        dmx_to = max(0, min(255, raw_to >> bit_shift))
        lo, hi = (dmx_from, dmx_to) if dmx_from <= dmx_to else (dmx_to, dmx_from)
        snap = (
            max(lo, min(hi, raw_default >> bit_shift))
            if isinstance(raw_default, int)
            else lo
        )
        ch_type = _attr_to_channel_type(attr)

        p_from = cf.get("physical_from")
        p_to = cf.get("physical_to")
        phys_min, phys_max, phys_unit = _resolve_physical_bounds(ch_type, p_from, p_to)

        snap_names = [cs["name"] for cs in cf.get("channel_sets", []) if cs.get("name")]
        gobo_id = ""
        if ch_type is ChannelType.GOBO_WHEEL:
            gobo_id = self._resolve_cf_gobo_id(cf, name)

        return ChannelRange(
            label=name,
            channel_type=ch_type,
            value_min=lo,
            value_max=hi,
            snap_value=snap,
            description=", ".join(snap_names) if snap_names else name,
            physical_min=phys_min,
            physical_max=phys_max,
            physical_unit=phys_unit,
            gobo_id=gobo_id,
        )

    def _resolve_cf_gobo_id(self, cf: dict[str, Any], fallback_name: str) -> str:
        wheel = str(cf.get("wheel") or "")
        for cs in cf.get("channel_sets", []):
            slot_idx = cs.get("wheel_slot_index")
            if slot_idx:
                key = f"{wheel}:{slot_idx}"
                if key in self.last_gobo_assets:
                    return self.last_gobo_assets[key].gobo_id
        return resolve_builtin_gobo(fallback_name, 0)

    @staticmethod
    def _read_wheel_gobos(
        gdtf_path: Path,
        gdtf_obj: Any,  # noqa: ANN401
    ) -> dict[str, GoboAsset]:
        assets: dict[str, GoboAsset] = {}
        ft_id = str(getattr(gdtf_obj, "fixture_type_id", None) or gdtf_path.stem)
        try:
            with zipfile.ZipFile(gdtf_path) as zf:
                names = set(zf.namelist())
                for wheel in getattr(gdtf_obj, "wheels", []) or []:
                    w_name = str(getattr(wheel, "name", "") or "")
                    for idx, slot in enumerate(
                        getattr(wheel, "wheel_slots", []) or [], start=1
                    ):
                        media = str(getattr(slot, "media_file_name", "") or "").strip()
                        if not media:
                            continue
                        for ext in ("png", "svg", "jpg"):
                            cand = f"wheels/{media}.{ext}"
                            if cand in names:
                                gid = f"gdtf:{ft_id}:{media}"
                                assets[f"{w_name}:{idx}"] = GoboAsset(
                                    gobo_id=gid,
                                    name=str(getattr(slot, "name", "") or media),
                                    data=zf.read(cand),
                                    ext=ext,
                                )
                                break
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return assets

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
