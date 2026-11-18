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

import typing

from olc.define import NB_UNIVERSES, UNIVERSES
from olc.devices.channel import COLOR_CHANNEL_TYPES, ChannelType, FixtureType

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
    "gobo_select_2": ChannelType.GOBO_WHEEL,
    "shutter_strobe": ChannelType.STROBE,
    "zoom": ChannelType.ZOOM,
    "edge": ChannelType.FOCUS,
    "iris": ChannelType.IRIS,
    "beam_fx_select": ChannelType.PRISM,
    "diffusion": ChannelType.FROST,
    "medium_diffusion": ChannelType.FROST,
    "_macros": ChannelType.MACRO,
    "fixture_global_reset": ChannelType.RESET,
    "color_temperature": ChannelType.COLOR_TEMP,
    "cto": ChannelType.COLOR_TEMP,
}

# Parameter names expected by LightingDevice.apply_device_parameter()
_PHYSICAL_PARAM_NAMES: dict[str, str] = {
    "pan": "pan",
    "tilt": "tilt",
    "zoom": "zoom",
    "edge": "focus",
    "color_temperature": "color_temp",
    "cto": "color_temp",
}


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


def build_device_and_definition(
    channel: int,
    pers_id: int,
    dmx_addr: int,
    curve_id: int,
    pers: dict[str, typing.Any],
    param_types: dict[int, str],
) -> tuple[dict[str, typing.Any], dict[str, typing.Any]] | None:
    """Build (device_dict, fixture_definition_dict) from an Eos $Patch entry."""
    univ_index = int((dmx_addr - 1) / 512)
    if univ_index < 0 or univ_index >= NB_UNIVERSES:
        return None
    universe = UNIVERSES[univ_index]
    base_address = dmx_addr - (512 * univ_index)

    manuf = str(pers.get("manufacturer") or "Generic")
    model = str(pers.get("model") or f"Personality {pers_id}")
    footprint = int(pers.get("footprint", 1))
    pers_channels: list[dict[str, typing.Any]] = pers.get("channels", [])

    dev_channels: list[dict[str, typing.Any]] = []
    mode_channels: list[dict[str, typing.Any]] = []
    ctypes: list[ChannelType] = []

    for idx, pc in enumerate(pers_channels, start=1):
        p_id = int(pc["param_id"])
        p_name = param_types.get(p_id, f"param_{p_id}")
        ctype = map_eos_param_type(p_name)
        ctypes.append(ctype)

        num_bytes = int(pc.get("bytes", 1))
        off_c = int(pc.get("offset_coarse", idx))
        off_f = int(pc.get("offset_fine", 0))
        def_val = int(pc.get("default", 0))
        phys_min = float(pc.get("phys_min", 0.0))
        phys_max = float(pc.get("phys_max", 1.0))

        addr_c = base_address + off_c - 1
        if addr_c < 1 or addr_c > 512:
            continue

        def_c = (def_val >> 8) & 0xFF if num_bytes == 2 else def_val & 0xFF
        dev_channels.append(
            {
                "channel_type": ctype.value,
                "universe": universe,
                "address": addr_c,
                "value": 0,
                "default_value": def_c,
                "fine": False,
                "ultra_fine": False,
                "label": p_name,
                "physical_min": phys_min,
                "physical_max": phys_max,
            }
        )

        fine_off_mode: int | None = None
        if num_bytes == 2 and off_f > 0:
            addr_f = base_address + off_f - 1
            if 1 <= addr_f <= 512:
                dev_channels.append(
                    {
                        "channel_type": ctype.value,
                        "universe": universe,
                        "address": addr_f,
                        "value": 0,
                        "default_value": def_val & 0xFF,
                        "fine": True,
                        "ultra_fine": False,
                        "label": f"{p_name} Fine",
                        "physical_min": phys_min,
                        "physical_max": phys_max,
                    }
                )
                fine_off_mode = off_f

        mode_channels.append(
            {
                "channel_type": ctype.value,
                "offset": off_c,
                "label": p_name,
                "default_value": def_c,
                "fine_offset": fine_off_mode,
                "physical_min": phys_min,
                "physical_max": phys_max,
            }
        )

    if not dev_channels:
        return None

    ftype = infer_fixture_type(ctypes)
    device_dict: dict[str, typing.Any] = {
        "fixture_id": channel,
        "label": f"{model} {channel}",
        "fixture_type": ftype.value,
        "manufacturer": manuf,
        "model": model,
        "mode_name": f"{footprint}ch",
        "gdtf_id": str(pers.get("dcid", "")),
        "curve_id": curve_id,
        "channels": dev_channels,
    }
    fdef_dict: dict[str, typing.Any] = {
        "manufacturer": manuf,
        "model": model,
        "fixture_type": ftype.value,
        "gdtf_id": str(pers.get("dcid", "")),
        "dmx_modes": [
            {
                "name": f"{footprint}ch",
                "footprint": footprint,
                "channels": mode_channels,
            }
        ],
    }
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
        max_raw = 65535.0 if num_bytes == 2 else 255.0
        norm = max(0.0, min(1.0, raw_val / max_raw))

        if p_name == "intens":
            intensity_val = norm
            dev_vals["intensity"] = norm
        elif p_name in _PHYSICAL_PARAM_NAMES:
            olcname = _PHYSICAL_PARAM_NAMES[p_name]
            phys_min = float(pc.get("phys_min", 0.0)) if pc else 0.0
            phys_max = float(pc.get("phys_max", 1.0)) if pc else 1.0
            dev_vals[olcname] = phys_min + norm * (phys_max - phys_min)
        elif p_name in ("red", "green", "blue"):
            rgb[p_name] = norm
        elif p_name in ("cyan", "magenta", "yellow"):
            cmy[p_name] = norm
        else:
            ctype = map_eos_param_type(p_name)
            if ctype is not ChannelType.GENERIC:
                dev_vals[ctype.value] = norm

    if rgb:
        r = round(rgb.get("red", 0.0) * 255)
        g = round(rgb.get("green", 0.0) * 255)
        b = round(rgb.get("blue", 0.0) * 255)
        dev_vals["color"] = f"#{r:02x}{g:02x}{b:02x}"
    elif cmy:
        r = round((1.0 - cmy.get("cyan", 0.0)) * 255)
        g = round((1.0 - cmy.get("magenta", 0.0)) * 255)
        b = round((1.0 - cmy.get("yellow", 0.0)) * 255)
        dev_vals["color"] = f"#{r:02x}{g:02x}{b:02x}"

    return dev_vals, intensity_val
