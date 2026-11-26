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
"""ETC Eos binary personality extractor and conditional parameter evaluator."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

from olc.devices.color import FixtureColorProfile, default_cmy_profile
from olc.devices.device import ChannelRange, ChannelType, FixtureType
from olc.devices.fixture import (
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
)
from olc.files.ascii.eos_devices import (
    EOS_PARAM_TO_CHANNEL_TYPE,
    build_default_color_profile,
)


@dataclass(frozen=True)
class EosSubRange:
    """Single DMX-to-user mapping sub-range inside an Eos parameter."""

    label: str
    dmx_min: int
    dmx_max: int
    user_min: float
    user_max: float
    home_dmx: int

    def contains_user(self, value: float) -> bool:
        """Return True if *value* falls within [user_min, user_max]."""
        lo = min(self.user_min, self.user_max)
        hi = max(self.user_min, self.user_max)
        return lo - 1e-6 <= value <= hi + 1e-6


@dataclass(frozen=True)
class EosRangeBlock:
    """Conditional block of sub-ranges gated on a virtual/mode parameter."""

    cond_param_id: int | None
    cond_min: float
    cond_max: float
    subranges: list[EosSubRange] = field(default_factory=list)

    def matches(self, active_params: dict[int, float]) -> bool:
        """Return True when this block's condition is satisfied."""
        if self.cond_param_id is None:
            return True
        if self.cond_param_id not in active_params:
            return False
        val = active_params[self.cond_param_id]
        lo = min(self.cond_min, self.cond_max)
        hi = max(self.cond_min, self.cond_max)
        return lo - 1e-6 <= val <= hi + 1e-6


@dataclass
class EosParamDef:
    """Extracted Eos parameter definition from ``tree[2]``."""

    param_id: int
    name: str
    home_dmx: int
    offset: int | None  # 0-based coarse DMX offset; None for virtual params
    fine_offset: int | None = None
    num_bytes: int = 1
    range_blocks: list[EosRangeBlock] = field(default_factory=list)

    @property
    def is_virtual(self) -> bool:
        """Return True if this parameter has no physical DMX channel."""
        return self.offset is None

    @property
    def max_dmx(self) -> int:
        """Maximum integer DMX value (255 for 8-bit, 65535 for 16-bit)."""
        return 65535 if self.num_bytes >= 2 else 255

    def physical_bounds(self) -> tuple[float, float, str]:
        """Return ``(min, max, unit)`` from the primary sub-range."""
        for block in self.range_blocks:
            for sr in block.subranges:
                if sr.user_min != sr.user_max:
                    lbl = sr.label.lower()
                    unit = "deg" if "deg" in lbl or " d" in lbl else ""
                    return float(sr.user_min), float(sr.user_max), unit
        return 0.0, 1.0, ""


@dataclass
class EosPersonality:
    """Complete fixture personality decoded from ``showdat.dat`` ``tree[2]``."""

    guid: str
    manufacturer: str
    model: str
    display_name: str
    category: str
    footprint: int
    params: dict[int, EosParamDef] = field(default_factory=dict)
    has_subtractive_cmy: bool = False
    has_additive_rgb: bool = False

    @property
    def is_dimmer(self) -> bool:
        """Return True if this personality is a simple dimmer."""
        cat = self.category.lower()
        if "dimmer" in cat and len(self.physical_params()) <= 1:
            return True
        phys = self.physical_params()
        return len(phys) == 1 and phys[0].name.lower() == "intens"

    def physical_params(self) -> list[EosParamDef]:
        """Return parameters that map to actual DMX offsets, sorted by offset."""
        return sorted(
            (p for p in self.params.values() if not p.is_virtual),
            key=lambda p: p.offset if p.offset is not None else 0,
        )


def parse_param_types(tree3: list[Any]) -> dict[int, str]:
    """Build ``param_id -> param_name`` mapping from ``tree[3]``."""
    result: dict[int, str] = {}
    if not isinstance(tree3, list):
        return result
    for item in tree3:
        if (
            isinstance(item, list)
            and len(item) >= 6
            and isinstance(item[2], str)
            and isinstance(item[5], int)
        ):
            result[item[5]] = item[2]
    return result


def parse_param_categories(tree3: list[Any]) -> dict[int, int]:
    """Build ``param_id -> Eos category`` mapping from ``tree[3]``.

    Eos categories: ``1=Intensity``, ``2=Focus``, ``3=Color``, ``4/5/6=Beam``.
    """
    result: dict[int, int] = {}
    if not isinstance(tree3, list):
        return result
    for item in tree3:
        if (
            isinstance(item, list)
            and len(item) >= 6
            and isinstance(item[4], int)
            and isinstance(item[5], int)
        ):
            result[item[5]] = item[4]
    return result


def _parse_condition(cond_obj: object) -> tuple[int | None, float, float]:
    """Parse Eos conditional range header."""
    if not isinstance(cond_obj, list) or len(cond_obj) < 3:
        return None, 0.0, 0.0
    if cond_obj[2] == 0:
        return None, 0.0, 0.0
    if len(cond_obj) >= 4 and isinstance(cond_obj[3], list):
        c_inner = cond_obj[3]
        if len(c_inner) >= 4 and isinstance(c_inner[2], int):
            cond_pid = c_inner[2]
            bounds_wrap = c_inner[3]
            if (
                isinstance(bounds_wrap, list)
                and len(bounds_wrap) >= 4
                and isinstance(bounds_wrap[3], list)
                and len(bounds_wrap[3]) >= 4
            ):
                b = bounds_wrap[3]
                return cond_pid, float(b[2]), float(b[3])
    return None, 0.0, 0.0


def _parse_subrange(sr: object) -> EosSubRange | None:
    if not isinstance(sr, list) or len(sr) < 10:
        return None
    if not isinstance(sr[3], (int, float)) or not isinstance(sr[4], (int, float)):
        return None
    if not isinstance(sr[5], (int, float)) or not isinstance(sr[6], (int, float)):
        return None
    home = int(sr[9]) if isinstance(sr[9], (int, float)) else int(sr[3])
    return EosSubRange(
        label=str(sr[2] or ""),
        dmx_min=int(sr[3]),
        dmx_max=int(sr[4]),
        user_min=float(sr[5]),
        user_max=float(sr[6]),
        home_dmx=home,
    )


def _parse_param_entry(item: object, param_names: dict[int, str]) -> EosParamDef | None:
    if not isinstance(item, list) or len(item) < 5:
        return None
    if not isinstance(item[3], list) or len(item[3]) < 5:
        return None
    inner = item[3][4]
    if not isinstance(inner, list) or len(inner) < 7 or not isinstance(inner[3], int):
        return None

    pid = inner[3]
    home_dmx = int(inner[4]) if isinstance(inner[4], (int, float)) else 0
    name = param_names.get(pid, f"param_{pid}")

    # Parse DMX offsets from item[4]: ["OBJ", 0, count, ["OBJ", 0, coarse], ...]
    offset: int | None = None
    fine_offset: int | None = None
    num_bytes = 0
    dmx_info = item[4]
    if (
        isinstance(dmx_info, list)
        and len(dmx_info) >= 3
        and isinstance(dmx_info[2], int)
    ):
        count = dmx_info[2]
        if count >= 1 and len(dmx_info) >= 4 and isinstance(dmx_info[3], list):
            if len(dmx_info[3]) >= 3 and isinstance(dmx_info[3][2], int):
                offset = dmx_info[3][2]
                num_bytes = 1
        if count >= 2 and len(dmx_info) >= 5 and isinstance(dmx_info[4], list):
            if len(dmx_info[4]) >= 3 and isinstance(dmx_info[4][2], int):
                fine_offset = dmx_info[4][2]
                num_bytes = 2

    range_blocks: list[EosRangeBlock] = []
    ranges_list = inner[6]
    if isinstance(ranges_list, list) and len(ranges_list) > 2:
        for block_raw in ranges_list[2:]:
            if not isinstance(block_raw, list) or len(block_raw) < 4:
                continue
            cond_pid, cond_min, cond_max = _parse_condition(block_raw[2])
            subranges: list[EosSubRange] = []
            sr_list = block_raw[3]
            if isinstance(sr_list, list) and len(sr_list) > 2:
                for sr_raw in sr_list[2:]:
                    sr = _parse_subrange(sr_raw)
                    if sr is not None:
                        subranges.append(sr)
            range_blocks.append(
                EosRangeBlock(
                    cond_param_id=cond_pid,
                    cond_min=cond_min,
                    cond_max=cond_max,
                    subranges=subranges,
                )
            )

    return EosParamDef(
        param_id=pid,
        name=name,
        home_dmx=home_dmx,
        offset=offset,
        fine_offset=fine_offset,
        num_bytes=num_bytes,
        range_blocks=range_blocks,
    )


def _detect_spd_color_methods(pers_raw: list[Any]) -> tuple[bool, bool]:
    """Detect subtractive CMY / additive RGB from optional base64 SPD JSON."""
    if len(pers_raw) <= 22 or not isinstance(pers_raw[22], list):
        return False, False
    blob_container = pers_raw[22]
    if len(blob_container) <= 6 or not isinstance(blob_container[6], str):
        return False, False
    try:
        decoded = base64.b64decode(blob_container[6])
        spd = json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return False, False

    has_cmy = False
    has_rgb = False
    for ch in spd.get("channels", []):
        if not isinstance(ch, dict):
            continue
        method = str(ch.get("method", "")).lower()
        cname = str(ch.get("name", "")).lower()
        if method == "subtractive" or cname in ("cyan", "magenta", "yellow"):
            has_cmy = True
        elif cname in ("red", "green", "blue"):
            has_rgb = True
    return has_cmy, has_rgb


def parse_personalities(
    tree2: list[Any], param_names: dict[int, str]
) -> dict[str, EosPersonality]:
    """Extract all fixture personalities from ``tree[2]`` keyed by GUID."""
    personalities: dict[str, EosPersonality] = {}
    if not isinstance(tree2, list):
        return personalities

    for entry in tree2:
        if (
            not isinstance(entry, list)
            or len(entry) < 19
            or not isinstance(entry[2], list)
            or len(entry[2]) < 11
            or not isinstance(entry[2][2], str)
        ):
            continue

        ddef = entry[2]
        guid = ddef[2]
        manufacturer = str(ddef[5] or "")
        model = str(ddef[6] or "")
        category = str(ddef[7] or "")
        display_name = str(ddef[18] or model) if len(ddef) > 18 else model
        footprint = int(entry[3]) if isinstance(entry[3], int) else 0

        params: dict[int, EosParamDef] = {}
        if (
            isinstance(ddef[10], list)
            and len(ddef[10]) >= 4
            and isinstance(ddef[10][3], list)
        ):
            for raw_p in ddef[10][3][3:]:
                pdef = _parse_param_entry(raw_p, param_names)
                if pdef is not None:
                    params[pdef.param_id] = pdef

        if footprint <= 0:
            max_off = -1
            for pdef in params.values():
                if pdef.offset is not None:
                    max_off = max(max_off, pdef.offset)
                if pdef.fine_offset is not None:
                    max_off = max(max_off, pdef.fine_offset)
            footprint = max_off + 1 if max_off >= 0 else 1

        has_cmy, has_rgb = _detect_spd_color_methods(entry)
        personalities[guid] = EosPersonality(
            guid=guid,
            manufacturer=manufacturer,
            model=model,
            display_name=display_name,
            category=category,
            footprint=footprint,
            params=params,
            has_subtractive_cmy=has_cmy,
            has_additive_rgb=has_rgb,
        )

    return personalities


_CONTINUOUS_UNITS = ("%", "deg", " d", "hz", "rpm", "sec", " s")


def evaluate_eos_param_to_dmx(
    param: EosParamDef,
    user_value: float,
    active_params: dict[int, float],
    personality: EosPersonality | None = None,
) -> int | None:
    """Evaluate an Eos user parameter value to an exact 8/16-bit DMX value.

    Handles conditional range blocks (virtual mode parameters such as
    ``Gobo_Mode``) and inverted DMX sub-ranges (``dmx_min > dmx_max``).
    """
    if param.is_virtual or not param.range_blocks:
        return None

    # Build effective context including home values for any missing virtual params
    ctx = dict(active_params)
    if personality is not None:
        for block in param.range_blocks:
            if block.cond_param_id is not None and block.cond_param_id not in ctx:
                vparam = personality.params.get(block.cond_param_id)
                if vparam is not None:
                    ctx[block.cond_param_id] = float(vparam.home_dmx)

    selected_block: EosRangeBlock | None = None
    for block in param.range_blocks:
        if block.matches(ctx):
            selected_block = block
            break

    # Fallback: pick block whose subranges contain user_value, or first block
    if selected_block is None:
        for block in param.range_blocks:
            if any(sr.contains_user(user_value) for sr in block.subranges):
                selected_block = block
                break
    if selected_block is None:
        selected_block = param.range_blocks[0]

    if not selected_block.subranges:
        return param.home_dmx

    target_sr: EosSubRange | None = None
    for sr in selected_block.subranges:
        if sr.contains_user(user_value):
            target_sr = sr
            break
    if target_sr is None:
        # Clamp to closest subrange by distance to [user_min, user_max]
        target_sr = min(
            selected_block.subranges,
            key=lambda sr: min(
                abs(user_value - sr.user_min), abs(user_value - sr.user_max)
            ),
        )

    span = target_sr.user_max - target_sr.user_min
    if abs(span) < 1e-9:
        return max(0, min(param.max_dmx, target_sr.home_dmx))

    lbl_lower = target_sr.label.lower()
    if (
        0.8 <= abs(span) <= 1.2
        and abs(user_value - round(user_value)) < 1e-4
        and not any(unit in lbl_lower for unit in _CONTINUOUS_UNITS)
    ):
        return max(0, min(param.max_dmx, target_sr.home_dmx))

    t = (user_value - target_sr.user_min) / span
    t = max(0.0, min(1.0, t))

    dmx = int(round(target_sr.dmx_min + t * (target_sr.dmx_max - target_sr.dmx_min)))
    return max(0, min(param.max_dmx, dmx))


def _infer_fixture_type(pers: EosPersonality) -> FixtureType:
    cat = pers.category.lower()
    names = {p.name.lower() for p in pers.physical_params()}
    if "yoke" in cat or "pan" in names or "tilt" in names:
        return FixtureType.MOVING_HEAD
    if "dimmer" in cat or pers.is_dimmer:
        return FixtureType.DIMMER
    if (
        "led" in cat
        or "wash" in cat
        or any(
            c in names for c in ("red", "green", "blue", "cyan", "magenta", "yellow")
        )
    ):
        return FixtureType.LED_PAR
    return FixtureType.GENERIC


def build_olc_fixture_definition(pers: EosPersonality) -> FixtureDefinition:
    """Build an OLC ``FixtureDefinition`` directly from an ``EosPersonality``."""
    channel_defs: list[ChannelDefinition] = []
    seen_offsets: set[int] = set()
    ctypes: set[ChannelType] = set()

    for p in pers.physical_params():
        if p.offset is None or p.offset in seen_offsets:
            continue
        seen_offsets.add(p.offset)
        if p.fine_offset is not None:
            seen_offsets.add(p.fine_offset)

        pname_lower = p.name.lower()
        ctype = EOS_PARAM_TO_CHANNEL_TYPE.get(pname_lower, ChannelType.GENERIC)
        ctypes.add(ctype)

        phys_min, phys_max, phys_unit = p.physical_bounds()

        # Build coarse 0..255 ChannelRanges
        ol_ranges: list[ChannelRange] = []
        shift = 8 if p.num_bytes >= 2 else 0
        for block in p.range_blocks:
            for sr in block.subranges:
                d_lo = min(sr.dmx_min, sr.dmx_max) >> shift
                d_hi = max(sr.dmx_min, sr.dmx_max) >> shift
                d_lo = max(0, min(255, d_lo))
                d_hi = max(d_lo, min(255, d_hi))
                if sr.label:
                    ol_ranges.append(
                        ChannelRange(
                            label=sr.label,
                            channel_type=ctype,
                            value_min=d_lo,
                            value_max=d_hi,
                        )
                    )

        channel_defs.append(
            ChannelDefinition(
                channel_type=ctype,
                offset=p.offset,
                label=p.name,
                default_value=p.home_dmx,
                fine_offset=p.fine_offset,
                ranges=ol_ranges,
                physical_min=phys_min,
                physical_max=phys_max,
                physical_unit=phys_unit,
            )
        )

    ftype = _infer_fixture_type(pers)
    color_profile: FixtureColorProfile | None = None
    if pers.has_subtractive_cmy or (
        ChannelType.CYAN in ctypes
        and ChannelType.MAGENTA in ctypes
        and ChannelType.YELLOW in ctypes
    ):
        color_profile = default_cmy_profile()
    else:
        color_profile = build_default_color_profile(
            f"{pers.manufacturer} {pers.model}".strip(), list(ctypes)
        )

    mode = DmxModeDefinition(
        name=f"Eos {pers.footprint}ch",
        channel_defs=channel_defs,
        description=pers.display_name,
    )
    return FixtureDefinition(
        manufacturer=pers.manufacturer or "ETC Eos",
        model=pers.model or pers.display_name,
        fixture_type=ftype,
        dmx_modes=[mode],
        color_profile=color_profile,
    )
