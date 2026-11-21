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
"""Helpers for importing ETC Eos personalities, patches, and cue parameters."""

from __future__ import annotations

import re
import typing

from olc.define import NB_UNIVERSES, UNIVERSES
from olc.devices.channel import COLOR_CHANNEL_TYPES, ChannelType, FixtureType
from olc.devices.color import CIExyY, EmitterProfile, FixtureColorProfile
from olc.devices.fixture import FixtureDefinition

_PALETTE_REF_RE = re.compile(r"^(ip|fp|cp|bp|pr)(\d+(?:\.\d+)?)$")
_PALETTE_PREFIX_TO_CATEGORY: dict[str, str] = {
    "ip": "intensity",
    "fp": "focus",
    "cp": "color",
    "bp": "beam",
    "pr": "preset",
}

EOS_PARAM_TO_CHANNEL_TYPE: dict[str, ChannelType] = {
    "intens": ChannelType.INTENSITY,
    "pan": ChannelType.PAN,
    "tilt": ChannelType.TILT,
    "red": ChannelType.RED,
    "green": ChannelType.GREEN,
    "blue": ChannelType.BLUE,
    "white": ChannelType.WHITE,
    "amber": ChannelType.AMBER,
    "lime": ChannelType.LIME,
    "cyan": ChannelType.CYAN,
    "indigo": ChannelType.INDIGO,
    "magenta": ChannelType.MAGENTA,
    "yellow": ChannelType.YELLOW,
    "color_select": ChannelType.COLOR_WHEEL,
    "gobo_select": ChannelType.GOBO_WHEEL,
    "shutter_strobe": ChannelType.STROBE,
    "zoom": ChannelType.ZOOM,
    "edge": ChannelType.FOCUS,
    "iris": ChannelType.IRIS,
    "beam_fx_select": ChannelType.PRISM,
    "diffusion": ChannelType.FROST,
    "_macros": ChannelType.MACRO,
    "fixture_global_reset": ChannelType.RESET,
    "color_temperature": ChannelType.COLOR_TEMP,
    "cto": ChannelType.COLOR_TEMP,
}

# Standard Eos optical/framing/control parameter names kept as ChannelType.GENERIC
# channels keyed by their lowercased personality label.
EOS_GENERIC_PARAM_NAMES: frozenset[str] = frozenset(
    {
        "gobo_select_2",
        "gobo_index/speed",
        "gobo_index/speed_2",
        "beam_fx_index/speed",
        "beam_fx_index/speed_2",
        "animation_select",
        "animation_index/speed",
        "medium_diffusion",
        "frame_assembly",
        "frame_a_1",
        "frame_b_1",
        "frame_a_2",
        "frame_b_2",
        "frame_a_3",
        "frame_b_3",
        "frame_a_4",
        "frame_b_4",
        "edge_mode",
        "position_mspeed",
        "lamp_control",
        "color_mix",
        "color_mix_crossfade_rate",
        "chase",
        "chase_rate",
        "chase_level",
        "pwm_frequency",
        "dimmer_curve",
        "tint",
        "led_engine_effects",
        "led_engine_effect_rate",
        "led_engine_effect_step_time",
    }
)

# Parameter names expected by LightingDevice.apply_device_parameter()
_PHYSICAL_PARAM_NAMES: dict[str, str] = {
    "pan": "pan",
    "tilt": "tilt",
    "zoom": "zoom",
    "edge": "focus",
    "color_temperature": "color_temp",
    "cto": "color_temp",
}


def parse_eos_param_token(
    token: str,
) -> tuple[float | None, tuple[str, float] | None]:
    """Parse an Eos $$Param token into a numeric value or a palette reference.

    Handles standard numbers, gel/library prefixed values (``GL106#65535``),
    by-type / untyped markers (``t255``, ``u255``), and palette/preset
    references (``IP<n>``, ``FP<n>``, ``CP<n>``, ``BP<n>``, ``PR<n>``).
    """
    tok = token.strip().lower()
    if not tok:
        return None, None
    if match := _PALETTE_REF_RE.match(tok):
        prefix, num_str = match.groups()
        return None, (_PALETTE_PREFIX_TO_CATEGORY[prefix], float(num_str))
    if "#" in tok:
        _, raw_part = tok.rsplit("#", 1)
        try:
            return float(raw_part), None
        except ValueError:
            return None, None
    if tok[0] in ("t", "u") and len(tok) > 1:
        try:
            return float(tok[1:]), None
        except ValueError:
            return None, None
    try:
        return float(tok), None
    except ValueError:
        return None, None


def eos_param_id_to_olc_key(
    p_id: int,
    param_types: dict[int, str],
    *,
    pers: dict[str, typing.Any] | None = None,
) -> str | None:
    """Map an Eos parameter ID to its OLC channel/device_values key."""
    p_name = param_types.get(p_id, "").lower()
    if not p_name:
        return "intensity" if p_id == 1 else None
    if p_name == "intens":
        return "intensity"
    if p_name in _PHYSICAL_PARAM_NAMES:
        return _PHYSICAL_PARAM_NAMES[p_name]
    if p_name in ("red", "green", "blue", "cyan", "magenta", "yellow"):
        return "color"
    ctype = map_eos_param_type(p_name)
    if ctype is not ChannelType.GENERIC:
        return ctype.value
    if p_name in EOS_GENERIC_PARAM_NAMES:
        return p_name
    if pers is not None and any(
        int(pc["param_id"]) == p_id for pc in pers.get("channels", [])
    ):
        return p_name
    return None


def map_eos_param_type(eos_name: str) -> ChannelType:
    """Map an Eos $ParamType name to an OLC ChannelType."""
    return EOS_PARAM_TO_CHANNEL_TYPE.get(eos_name.lower(), ChannelType.GENERIC)


def is_dimmer_personality(
    pers: dict[str, typing.Any], param_types: dict[int, str]
) -> bool:
    """Return True if *pers* represents a simple 1-channel dimmer."""
    channels = pers.get("channels", [])
    footprint = int(pers.get("footprint", len(channels) or 1))
    if footprint != 1 or len(channels) != 1:
        return False
    p_name = param_types.get(channels[0]["param_id"], "").lower()
    return p_name in ("intens", "")


def infer_fixture_type(channel_types: list[ChannelType]) -> FixtureType:
    """Infer FixtureType from a personality's channel types."""
    ctype_set = set(channel_types)
    if ChannelType.PAN in ctype_set or ChannelType.TILT in ctype_set:
        return FixtureType.MOVING_HEAD
    if ctype_set & COLOR_CHANNEL_TYPES:
        return FixtureType.LED_PAR
    if ChannelType.STROBE in ctype_set and len(ctype_set) <= 2:
        return FixtureType.STROBE
    if ctype_set == {ChannelType.INTENSITY}:
        return FixtureType.DIMMER
    return FixtureType.GENERIC


_ADDITIVE_EMITTER_DEFAULTS: dict[
    ChannelType, tuple[str, float, float, float, float, str]
] = {
    ChannelType.RED: ("Red", 0.6400, 0.3300, 21.26, 625.0, "ColorAdd_R"),
    ChannelType.GREEN: ("Green", 0.3000, 0.6000, 71.52, 525.0, "ColorAdd_G"),
    ChannelType.BLUE: ("Blue", 0.1500, 0.0600, 7.22, 465.0, "ColorAdd_B"),
    ChannelType.WHITE: ("White", 0.3127, 0.3290, 100.0, 0.0, "ColorAdd_W"),
    ChannelType.AMBER: ("Amber", 0.5900, 0.4000, 50.0, 590.0, "ColorAdd_A"),
    ChannelType.LIME: ("Lime", 0.3225, 0.3870, 80.0, 560.0, "ColorAdd_GY"),
    ChannelType.CYAN: ("Cyan", 0.0454, 0.2950, 25.0, 490.0, "ColorAdd_C"),
    ChannelType.INDIGO: ("Indigo", 0.1689, 0.0069, 5.0, 430.0, "ColorAdd_BC"),
}

_REQUIRED_RGB_TYPES: frozenset[ChannelType] = frozenset(
    {ChannelType.RED, ChannelType.GREEN, ChannelType.BLUE}
)

_CHANNEL_TYPE_UNIT_DEFAULTS: dict[ChannelType, str] = {
    ChannelType.PAN: "deg",
    ChannelType.TILT: "deg",
    ChannelType.ZOOM: "deg",
    ChannelType.INTENSITY: "%",
    ChannelType.IRIS: "%",
    ChannelType.FROST: "%",
    ChannelType.COLOR_TEMP: "K",
    ChannelType.STROBE: "Hz",
}


def _extract_physical_unit(
    slot_list: list[dict[str, typing.Any]], ctype: ChannelType
) -> str:
    """Infer physical unit string from Eos $$PersSlot labels or ChannelType."""
    for slot in slot_list:
        lbl = str(slot.get("label", "")).strip()
        if not lbl:
            continue
        lbl_lower = lbl.lower()
        if lbl.endswith("%"):
            return "%"
        if lbl == "D" or lbl.endswith(" D"):
            return "deg"
        if lbl_lower.endswith(" sec"):
            return "s"
        if "temp" in lbl_lower or lbl.endswith(" K"):
            return "K"
    return _CHANNEL_TYPE_UNIT_DEFAULTS.get(ctype, "")


def _resolve_channel_physical_bounds(
    pc: dict[str, typing.Any],
) -> tuple[float, float]:
    """Return (phys_min, phys_max), inverting bounds on reversed 1-slot channels."""
    slot_list: list[dict[str, typing.Any]] = pc.get("slot_list", [])
    if len(slot_list) == 1:
        s0 = slot_list[0]
        if int(s0["dmx_min"]) > int(s0["dmx_max"]):
            return float(s0["phys_max"]), float(s0["phys_min"])
    return float(pc.get("phys_min", 0.0)), float(pc.get("phys_max", 1.0))


def _build_channel_ranges(
    slot_list: list[dict[str, typing.Any]],
    num_bytes: int,
    ctype: ChannelType,
    unit: str,
) -> list[dict[str, typing.Any]]:
    """Convert multi-slot Eos $$PersSlot definitions into ChannelRange dicts."""
    if len(slot_list) <= 1:
        return []

    is_16bit = num_bytes == 2 or any(
        max(int(s["dmx_min"]), int(s["dmx_max"])) > 255 for s in slot_list
    )
    parsed: list[tuple[int, int, int, float, float, str]] = []
    for idx, slot in enumerate(slot_list, start=1):
        d0 = int(slot["dmx_min"])
        d1 = int(slot["dmx_max"])
        dsnap = int(slot["dmx_snap"])
        p0 = float(slot["phys_min"])
        p1 = float(slot["phys_max"])
        if d0 > d1:
            d0, d1 = d1, d0
            p0, p1 = p1, p0

        if is_16bit:
            lo, hi, snap = d0 >> 8, d1 >> 8, dsnap >> 8
        else:
            lo, hi, snap = d0, d1, dsnap

        lo = max(0, min(255, lo))
        hi = max(0, min(255, hi))
        if lo > hi:
            lo, hi = hi, lo

        label = str(slot.get("label", "")).strip() or f"Slot {idx}"
        parsed.append((lo, hi, snap, p0, p1, label))

    parsed.sort(key=lambda item: (item[0], item[1]))
    ranges: list[dict[str, typing.Any]] = []
    prev_hi = -1
    for lo, hi, snap, p0, p1, label in parsed:
        if lo <= prev_hi:
            lo = prev_hi + 1
        if lo > hi:
            continue
        snap_clamped = max(lo, min(hi, snap))
        ranges.append(
            {
                "label": label,
                "channel_type": ctype.value,
                "value_min": lo,
                "value_max": hi,
                "snap_value": snap_clamped,
                "physical_min": p0,
                "physical_max": p1,
                "physical_unit": unit,
            }
        )
        prev_hi = hi

    return ranges


def build_default_color_profile(
    fixture_name: str, channel_types: list[ChannelType]
) -> FixtureColorProfile | None:
    """Build a generic CIE 1931 color profile for additive RGB+ LED fixtures.

    Returns ``None`` for non-additive or subtractive (CMY) fixtures so they are
    not wrongly solved via additive NNLS matching.
    """
    if not _REQUIRED_RGB_TYPES.issubset(set(channel_types)):
        return None

    emitters: list[EmitterProfile] = []
    seen: set[ChannelType] = set()
    for ctype in channel_types:
        if ctype in seen or ctype not in _ADDITIVE_EMITTER_DEFAULTS:
            continue
        seen.add(ctype)
        name, cie_x, cie_y, cie_lum, wavelength, gdtf_attr = _ADDITIVE_EMITTER_DEFAULTS[
            ctype
        ]
        emitters.append(
            EmitterProfile(
                name=name,
                cie=CIExyY(x=cie_x, y=cie_y, Y=cie_lum),
                dominant_wavelength=wavelength,
                gdtf_attribute=gdtf_attr,
            )
        )

    return FixtureColorProfile(fixture_name=fixture_name, emitters=emitters)


def build_fixture_definition(
    pers_id: int,
    pers: dict[str, typing.Any],
    param_types: dict[int, str],
    mode_name: str | None = None,
) -> dict[str, typing.Any] | None:
    """Build a serialized FixtureDefinition dict from an Eos $Personality."""
    manuf = str(pers.get("manufacturer") or "Generic")
    model = str(pers.get("model") or f"Personality {pers_id}")
    footprint = int(pers.get("footprint", 1))
    pers_channels: list[dict[str, typing.Any]] = pers.get("channels", [])

    channel_defs: list[dict[str, typing.Any]] = []
    ctypes: list[ChannelType] = []

    for idx, pc in enumerate(pers_channels, start=1):
        p_id = int(pc["param_id"])
        p_name = param_types.get(p_id, f"param_{p_id}")
        ctype = map_eos_param_type(p_name)

        num_bytes = int(pc.get("bytes", 1))
        off_c = int(pc.get("offset_coarse", idx))
        if off_c < 1:
            continue
        off_f = int(pc.get("offset_fine", 0))
        def_val = int(pc.get("default", 0))
        slot_list: list[dict[str, typing.Any]] = pc.get("slot_list", [])
        phys_min, phys_max = _resolve_channel_physical_bounds(pc)
        phys_unit = _extract_physical_unit(slot_list, ctype)
        ranges = _build_channel_ranges(slot_list, num_bytes, ctype, phys_unit)

        ctypes.append(ctype)
        offset_0 = off_c - 1
        fine_offset_0: int | None = (
            (off_f - 1) if (num_bytes == 2 and off_f > 0) else None
        )
        default_value = (
            (def_val & 0xFFFF) if fine_offset_0 is not None else (def_val & 0xFF)
        )

        channel_defs.append(
            {
                "channel_type": ctype.value,
                "offset": offset_0,
                "label": p_name,
                "default_value": default_value,
                "fine_offset": fine_offset_0,
                "physical_min": phys_min,
                "physical_max": phys_max,
                "physical_unit": phys_unit,
                "ranges": ranges,
            }
        )

    if not channel_defs:
        return None

    ftype = infer_fixture_type(ctypes)
    resolved_mode = mode_name or f"{footprint}ch"
    fdef_dict: dict[str, typing.Any] = {
        "manufacturer": manuf,
        "model": model,
        "fixture_type": ftype.value,
        "gdtf_id": str(pers.get("dcid", "")),
        "notes": str(pers.get("notes", "")).strip(),
        "dmx_modes": [
            {
                "name": resolved_mode,
                "channel_defs": channel_defs,
            }
        ],
    }

    color_profile = build_default_color_profile(f"{manuf} {model}".strip(), ctypes)
    if color_profile is not None:
        fdef_dict["color_profile"] = color_profile.to_dict()

    return fdef_dict


def build_device_from_definition(
    channel: int,
    dmx_addr: int,
    curve_id: int,
    fdef_dict: dict[str, typing.Any],
    mode_name: str | None = None,
) -> dict[str, typing.Any] | None:
    """Instantiate a LightingDevice dict from *fdef_dict* and a patch address."""
    univ_index = (dmx_addr - 1) // 512
    if univ_index < 0 or univ_index >= NB_UNIVERSES:
        return None
    universe = UNIVERSES[univ_index]
    base_address = dmx_addr - (512 * univ_index)

    fdef = FixtureDefinition.from_dict(fdef_dict)
    device = fdef.instantiate(
        fixture_id=channel,
        label=f"{fdef.model} {channel}",
        universe=universe,
        address=base_address,
        mode_name=mode_name,
    )
    if not device.channels:
        return None

    device.set_curve_id(curve_id)
    device_dict = device.to_dict()
    # Keep default DMX channel values intact instead of triggering sRGB/intensity
    # re-solving inside LightingDevice.from_dict() during show import.
    device_dict.pop("intensity", None)
    device_dict.pop("target_color", None)
    device_dict.pop("base_emitters", None)
    return device_dict


def build_device_and_definition(
    channel: int,
    pers_id: int,
    dmx_addr: int,
    curve_id: int,
    pers: dict[str, typing.Any],
    param_types: dict[int, str],
) -> tuple[dict[str, typing.Any], dict[str, typing.Any]] | None:
    """Build (device_dict, fixture_definition_dict) from an Eos $Patch entry."""
    fdef_dict = build_fixture_definition(pers_id, pers, param_types)
    if fdef_dict is None:
        return None
    device_dict = build_device_from_definition(channel, dmx_addr, curve_id, fdef_dict)
    if device_dict is None:
        return None
    return device_dict, fdef_dict


def decode_eos_cue_params(
    raw_params: list[tuple[int, float]],
    pers: dict[str, typing.Any] | None,
    param_types: dict[int, str],
) -> tuple[dict[str, typing.Any], float | None]:
    """Convert Eos $$Param pairs into OLC cue device_values and optional intensity."""
    chan_by_param: dict[int, dict[str, typing.Any]] = {}
    if pers is not None:
        for pc in pers.get("channels", []):
            chan_by_param[int(pc["param_id"])] = pc

    dev_vals: dict[str, typing.Any] = {}
    intensity_val: float | None = None
    rgb: dict[str, float] = {}
    cmy: dict[str, float] = {}

    for p_id, raw_val in raw_params:
        p_name = param_types.get(p_id, "").lower()
        pc = chan_by_param.get(p_id)
        num_bytes = int(pc.get("bytes", 1)) if pc else (2 if raw_val > 255 else 1)
        max_raw = 65535.0 if (num_bytes == 2 or raw_val > 255.0) else 255.0
        norm = max(0.0, min(1.0, raw_val / max_raw))

        if p_name == "intens":
            intensity_val = norm
            dev_vals["intensity"] = norm
        elif p_name in _PHYSICAL_PARAM_NAMES:
            olcname = _PHYSICAL_PARAM_NAMES[p_name]
            if pc is not None:
                phys_min, phys_max = _resolve_channel_physical_bounds(pc)
            else:
                phys_min, phys_max = 0.0, 1.0
            dev_vals[olcname] = phys_min + norm * (phys_max - phys_min)
        elif p_name in ("red", "green", "blue"):
            rgb[p_name] = norm
        elif p_name in ("cyan", "magenta", "yellow"):
            cmy[p_name] = norm
        else:
            ctype = map_eos_param_type(p_name)
            if ctype is not ChannelType.GENERIC:
                key = ctype.value
                existing = dev_vals.get(key)
                if not isinstance(existing, (int, float)) or norm > float(existing):
                    dev_vals[key] = norm
            elif p_name and (pc is not None or p_name in EOS_GENERIC_PARAM_NAMES):
                dev_vals[p_name] = norm

    if rgb:
        r = round(rgb.get("red", 0.0) * 255)
        g = round(rgb.get("green", 0.0) * 255)
        b = round(rgb.get("blue", 0.0) * 255)
        dev_vals["color"] = f"#{r:02x}{g:02x}{b:02x}"
        for comp, val in rgb.items():
            dev_vals[comp] = val
    elif cmy:
        r = round((1.0 - cmy.get("cyan", 0.0)) * 255)
        g = round((1.0 - cmy.get("magenta", 0.0)) * 255)
        b = round((1.0 - cmy.get("yellow", 0.0)) * 255)
        dev_vals["color"] = f"#{r:02x}{g:02x}{b:02x}"

    return dev_vals, intensity_val
