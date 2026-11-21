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
"""Consolidated per-channel display snapshots for Live tiles, Table view, and Cues."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from olc.core.live_state import LiveParameterState
from olc.core.tracking import (
    ResolvedState,
    TrackingDisplayState,
    TrackingEngine,
    classify_channel_tracking_state,
    get_tracking_color,
)
from olc.define import MAX_CHANNELS
from olc.devices.channel import COLOR_CHANNEL_TYPES, ChannelType, FixtureType
from olc.show.step import get_parameter_family

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.core.effects_engine import EffectsEngine
    from olc.devices.device import LightingDevice
    from olc.show.effect import EffectManager
    from olc.show.lightshow import LightShow
    from olc.show.palette import PaletteManager, PaletteRef

_SHORT_PREFIX_MAP: dict[str, str] = {
    "intensity": "IP",
    "intens": "IP",
    "int": "IP",
    "focus": "FP",
    "position": "FP",
    "pos": "FP",
    "color": "CP",
    "colour": "CP",
    "beam": "BP",
    "preset": "P",
    "effect": "FX",
    "fx": "FX",
}

_COLOR_EMITTER_NAMES: frozenset[str] = frozenset(ct.value for ct in COLOR_CHANNEL_TYPES)

_PARAM_ALIASES: dict[str, tuple[str, ...]] = {
    "color": ("color", "colour"),
    "colour": ("color", "colour"),
    "cct": ("cct", "color_temp", "colortemp"),
    "color_temp": ("cct", "color_temp", "colortemp"),
    "colortemp": ("cct", "color_temp", "colortemp"),
    "strobe": ("strobe", "shutter"),
    "shutter": ("strobe", "shutter"),
    "gobo": ("gobo", "gobo_wheel"),
    "gobo_wheel": ("gobo", "gobo_wheel"),
}

_PARK_COLOR: dict[str, float] = {"red": 1.0, "green": 0.7, "blue": 0.0}
_FADER_COLOR: dict[str, float] = {"red": 0.4, "green": 0.7, "blue": 0.4}
_INDEP_COLOR: dict[str, float] = {"red": 0.4, "green": 0.4, "blue": 0.7}

_BEAM_PARAM_TYPES: tuple[tuple[str, ChannelType], ...] = (
    ("zoom", ChannelType.ZOOM),
    ("focus", ChannelType.FOCUS),
    ("iris", ChannelType.IRIS),
    ("strobe", ChannelType.STROBE),
    ("gobo", ChannelType.GOBO_WHEEL),
    ("frost", ChannelType.FROST),
    ("prism", ChannelType.PRISM),
)


@dataclass(frozen=True)
class PaletteRefDisplay:
    """Resolved UI presentation of a Palette or Preset reference."""

    category: str
    number: float
    short_ref: str
    label: str
    is_partial: bool = False


@dataclass(frozen=True)
class AttributeFamilySnapshot:
    """Consolidated snapshot for one IFCB attribute family on a channel."""

    family: str
    available: bool
    tracking_state: TrackingDisplayState
    is_manual: bool
    palette_ref: Optional[PaletteRefDisplay]
    summary_value: str
    parameters: dict[str, Any] = field(default_factory=dict)
    parameter_refs: dict[str, PaletteRefDisplay] = field(default_factory=dict)
    percent_summary: str = ""
    dmx_summary: str = ""
    parameter_dmx: dict[str, int] = field(default_factory=dict)
    parameter_percent: dict[str, float] = field(default_factory=dict)
    effect_ref: Optional[PaletteRefDisplay] = None


@dataclass(frozen=True)
class ChannelDisplaySnapshot:
    """Full display model for a single channel tile or table row."""

    channel: int
    is_patched: bool
    is_selected: bool
    is_parked: bool
    is_manual: bool
    intensity: float
    next_intensity: Optional[float]
    intensity_state: TrackingDisplayState
    intensity_source: str
    intensity_color: dict[str, float]
    intensity_ref: Optional[PaletteRefDisplay]
    has_device: bool
    is_moving_head: bool
    device_label: str
    fixture_name: str
    address_str: str
    has_color: bool
    preview_rgb: Optional[tuple[float, float, float]]
    focus: AttributeFamilySnapshot
    color: AttributeFamilySnapshot
    beam: AttributeFamilySnapshot
    has_fcb_move: bool
    is_mib: bool
    intensity_effect_ref: Optional[PaletteRefDisplay] = None
    effect_ref: Optional[PaletteRefDisplay] = None


def _format_palette_num(number: float) -> str:
    """Format palette/preset number concisely (2.0 -> '2', 2.5 -> '2.5')."""
    num = float(number)
    return str(int(num)) if num.is_integer() else f"{num:g}"


def format_short_palette_ref(category: str, number: float) -> str:
    """Format concise console palette identifier such as 'CP 2' or 'P 1.5'."""
    cat_low = str(category).strip().lower()
    prefix = _SHORT_PREFIX_MAP.get(cat_low)
    if prefix is None:
        prefix = f"{cat_low[:1].upper()}P" if cat_low else "P"
    return f"{prefix} {_format_palette_num(number)}"


def format_family_readout(
    family_snap: AttributeFamilySnapshot,
    readout: str = "auto",
) -> str:
    """Format an attribute family cell or tombstone slot per *readout* mode.

    Args:
        family_snap: Snapshot for the Focus, Color, or Beam family.
        readout: One of ``"auto"``, ``"label"``, ``"ref"``, ``"percent"``,
            ``"dmx"``, or ``"value"``.
    """
    if not family_snap.available and family_snap.effect_ref is None:
        return ""
    mode = str(readout).strip().lower()
    ref = family_snap.palette_ref
    fx_ref = family_snap.effect_ref
    suffix = "+" if (ref is not None and ref.is_partial) else ""

    if mode in ("auto", "label"):
        parts: list[str] = []
        if ref is not None:
            parts.append(
                f"{ref.label}{suffix}" if ref.label else f"{ref.short_ref}{suffix}"
            )
        if fx_ref is not None:
            parts.append(
                fx_ref.label if (mode == "label" and fx_ref.label) else fx_ref.short_ref
            )
        if parts:
            return " + ".join(parts)
        return family_snap.summary_value

    if mode == "ref":
        parts = []
        if ref is not None:
            parts.append(f"{ref.short_ref}{suffix}")
        if fx_ref is not None:
            parts.append(fx_ref.short_ref)
        if parts:
            return " + ".join(parts)
        return family_snap.summary_value

    if mode == "percent":
        return family_snap.percent_summary or family_snap.summary_value

    if mode == "dmx":
        return family_snap.dmx_summary or family_snap.summary_value

    return family_snap.summary_value


def _format_single_param_value(param_key: str, val: Any) -> str:  # noqa: ANN401
    """Format a single physical/normalized parameter value concisely."""
    p_low = str(param_key).strip().lower()
    if p_low in ("pan", "tilt", "zoom"):
        return f"{round(float(val))}°" if isinstance(val, (int, float)) else ""
    if p_low == "focus":
        return f"{float(val):.1f}m" if isinstance(val, (int, float)) else ""
    if p_low == "cct":
        return f"{round(float(val))}K" if isinstance(val, (int, float)) else ""
    if p_low == "strobe":
        if not isinstance(val, (int, float)):
            return str(val)
        return f"{float(val):.1f}Hz" if float(val) > 0.0 else "Open"
    if p_low == "iris":
        if not isinstance(val, (int, float)):
            return str(val)
        fval = float(val)
        return f"{round(fval * 100)}%" if fval <= 1.0 else f"{round(fval)}%"
    if p_low == "gobo":
        return "Open" if val in (None, 0, "") else str(val)
    if p_low in _COLOR_EMITTER_NAMES or p_low in ("color_wheel", "frost", "prism"):
        return (
            f"{round(float(val) * 100)}%" if isinstance(val, (int, float)) else str(val)
        )
    return "" if val is None else str(val)


def format_parameter_readout(
    family_snap: AttributeFamilySnapshot,
    param_key: str,
    readout: str = "auto",
) -> str:
    """Format one parameter cell per *readout* mode.

    Args:
        family_snap: Snapshot for the Focus, Color, or Beam family.
        param_key: Canonical parameter key (e.g. ``"pan"``, ``"cyan"``, ``"zoom"``).
        readout: One of ``"auto"``, ``"label"``, ``"ref"``, ``"percent"``,
            ``"dmx"``, or ``"value"``.
    """
    if param_key not in family_snap.parameters:
        return ""
    pref = family_snap.parameter_refs.get(param_key)
    mode = str(readout).strip().lower()
    val_txt = _format_single_param_value(param_key, family_snap.parameters[param_key])

    if mode in ("auto", "label"):
        if pref is not None:
            return pref.label or pref.short_ref
        return val_txt
    if mode == "ref":
        if pref is not None:
            return pref.short_ref
        return val_txt
    if mode == "percent":
        if param_key in family_snap.parameter_percent:
            return f"{round(family_snap.parameter_percent[param_key])}%"
        return val_txt
    if mode == "dmx":
        if param_key in family_snap.parameter_dmx:
            return str(family_snap.parameter_dmx[param_key])
        return val_txt
    return val_txt


def _make_palette_ref_display(
    palettes: Optional[PaletteManager],
    ref: PaletteRef,
    *,
    is_partial: bool = False,
) -> PaletteRefDisplay:
    cat_str, num_val = str(ref[0]), float(ref[1])
    pal = palettes.get(cat_str, num_val) if palettes is not None else None
    label = (
        str(pal.text).strip() if pal is not None and getattr(pal, "text", None) else ""
    )
    return PaletteRefDisplay(
        category=cat_str,
        number=num_val,
        short_ref=format_short_palette_ref(cat_str, num_val),
        label=label,
        is_partial=is_partial,
    )


def _make_effect_ref_display(
    effects: Optional[EffectManager],
    effect_number: float,
) -> PaletteRefDisplay:
    num_val = float(effect_number)
    eff = effects.get(num_val) if effects is not None else None
    label = (
        str(eff.label).strip()
        if eff is not None and getattr(eff, "label", None)
        else ""
    )
    return PaletteRefDisplay(
        category="effect",
        number=num_val,
        short_ref=f"FX {_format_palette_num(num_val)}",
        label=label,
        is_partial=False,
    )


def _resolve_channel_effect_refs_by_family(
    channel: int,
    *,
    effects: Optional[EffectManager],
    effects_engine: Optional[EffectsEngine],
    live_state: Optional[LiveParameterState],
    resolved_step: Optional[ResolvedState],
    is_live: bool,
) -> dict[str, PaletteRefDisplay]:
    """Resolve active Effect references per IFCB family on *channel*."""
    if effects is None:
        return {}

    effect_numbers: list[float] = []
    if is_live:
        if effects_engine is not None and hasattr(
            effects_engine, "get_channel_effects"
        ):
            for inst in effects_engine.get_channel_effects(channel):
                if not getattr(inst, "remove_on_fade_end", False):
                    effect_numbers.append(float(inst.effect_number))
        if (
            not effect_numbers
            and live_state is not None
            and hasattr(live_state, "get_effect_ref")
        ):
            lfx = live_state.get_effect_ref(channel)
            if isinstance(lfx, dict) and not lfx.get("stop"):
                fx_num = lfx.get("effect", lfx.get("effect_number"))
                if fx_num is not None:
                    effect_numbers.append(float(fx_num))
    elif resolved_step is not None:
        rfx = getattr(resolved_step, "effect_refs", {}).get(channel)
        if isinstance(rfx, dict) and not rfx.get("stop"):
            fx_num = rfx.get("effect", rfx.get("effect_number"))
            if fx_num is not None:
                effect_numbers.append(float(fx_num))

    result: dict[str, PaletteRefDisplay] = {}
    for fx_num in effect_numbers:
        disp = _make_effect_ref_display(effects, fx_num)
        result.setdefault("any", disp)
        eff = effects.get(fx_num)
        if eff is not None and getattr(eff, "layers", None):
            for layer in eff.layers:
                fam = LiveParameterState.normalize_family(
                    get_parameter_family(str(layer.parameter))
                )
                result[fam] = disp
        else:
            result.setdefault("intensity", disp)
    return result


def _lookup_step_param_ref(
    resolved_step: Optional[ResolvedState],
    channel: int,
    param_name: str,
) -> Optional[PaletteRef]:
    if resolved_step is None:
        return None
    ch_refs = resolved_step.palette_refs.get(channel)
    if not ch_refs:
        return None
    p_low = str(param_name).lower()
    candidates = [param_name, p_low, *_PARAM_ALIASES.get(p_low, ())]
    if p_low in _COLOR_EMITTER_NAMES:
        candidates.extend(("color", "colour"))
    candidates.append("*")
    for cand in candidates:
        if cand in ch_refs:
            raw = ch_refs[cand]
            if isinstance(raw, (tuple, list)) and len(raw) >= 2:
                return (str(raw[0]), float(raw[1]))
    return None


def _lookup_live_param_ref(
    live_state: Optional[LiveParameterState],
    resolved_step: Optional[ResolvedState],
    channel: int,
    param_name: str,
) -> tuple[Optional[PaletteRef], bool]:
    """Return ``(effective_ref, is_manual)`` checking live overrides before cue."""
    if live_state is not None and live_state.is_param_manual(channel, param_name):
        lref = live_state.get_palette_ref(channel, param_name)
        if lref is None and str(param_name).lower() in _COLOR_EMITTER_NAMES:
            lref = live_state.get_palette_ref(channel, "color")
        return lref, True
    if live_state is not None:
        lref = live_state.get_palette_ref(channel, param_name)
        if lref is None and str(param_name).lower() in _COLOR_EMITTER_NAMES:
            lref = live_state.get_palette_ref(channel, "color")
        if lref is not None:
            return lref, True
    return _lookup_step_param_ref(resolved_step, channel, param_name), False


def _resolve_family_palette_and_states(
    family: str,
    param_keys: list[str],
    *,
    channel: int,
    palettes: Optional[PaletteManager],
    live_state: Optional[LiveParameterState],
    resolved_step: Optional[ResolvedState],
    is_live: bool,
) -> tuple[
    TrackingDisplayState,
    bool,
    Optional[PaletteRefDisplay],
    dict[str, PaletteRefDisplay],
]:
    if not param_keys:
        return TrackingDisplayState.INACTIVE, False, None, {}

    raw_refs: list[Optional[PaletteRef]] = []
    param_refs_out: dict[str, PaletteRefDisplay] = {}
    any_manual = False

    if (
        is_live
        and live_state is not None
        and live_state.is_family_manual(channel, family)
    ):
        any_manual = True

    for key in param_keys:
        if is_live:
            ref, p_manual = _lookup_live_param_ref(
                live_state, resolved_step, channel, key
            )
            if p_manual:
                any_manual = True
        else:
            ref = _lookup_step_param_ref(resolved_step, channel, key)
        raw_refs.append(ref)
        if ref is not None:
            param_refs_out[key] = _make_palette_ref_display(palettes, ref)

    family_ref: Optional[PaletteRefDisplay] = None
    non_null = [r for r in raw_refs if r is not None]
    if non_null:
        unique = list(dict.fromkeys((str(r[0]), float(r[1])) for r in non_null))
        is_partial = len(unique) > 1 or len(non_null) < len(param_keys)
        family_ref = _make_palette_ref_display(
            palettes, unique[0], is_partial=is_partial
        )

    if any_manual:
        t_state = TrackingDisplayState.MANUAL
    elif resolved_step is not None:
        t_state = resolved_step.family_states.get(channel, {}).get(
            family, TrackingDisplayState.INACTIVE
        )
    else:
        t_state = TrackingDisplayState.INACTIVE

    return t_state, any_manual, family_ref, param_refs_out


def _normalize_lvl(raw: float) -> float:
    val = float(raw)
    if val < 0.0:
        return 0.0
    if val > 1.0:
        return min(1.0, val / 255.0)
    return val


def _format_hex_rgb(rgb: tuple[float, float, float]) -> str:
    return (
        f"#{round(max(0.0, min(1.0, rgb[0])) * 255):02X}"
        f"{round(max(0.0, min(1.0, rgb[1])) * 255):02X}"
        f"{round(max(0.0, min(1.0, rgb[2])) * 255):02X}"
    )


def _is_dev_moving_head(dev: Optional[LightingDevice]) -> bool:
    if dev is None:
        return False
    if dev.fixture_type == FixtureType.MOVING_HEAD:
        return True
    return any(
        ch.channel_type in (ChannelType.PAN, ChannelType.TILT)
        for ch in getattr(dev, "channels", ())
    )


def _build_device_family_snapshots(  # pylint: disable=too-many-locals, too-many-branches
    dev: Optional[LightingDevice],
    *,
    channel: int,
    palettes: Optional[PaletteManager],
    live_state: Optional[LiveParameterState],
    resolved_step: Optional[ResolvedState],
    is_live: bool,
    family_effect_refs: Optional[dict[str, PaletteRefDisplay]] = None,
) -> tuple[
    AttributeFamilySnapshot,
    AttributeFamilySnapshot,
    AttributeFamilySnapshot,
    bool,
    Optional[tuple[float, float, float]],
]:
    """Build Focus, Color, and Beam snapshots along with preview_rgb."""
    fx_map = family_effect_refs or {}
    step_dev_vals = (
        dict(resolved_step.device_values.get(channel, {}))
        if resolved_step is not None
        else {}
    )

    # --- FOCUS (Position) ---
    focus_params: dict[str, Any] = {}
    focus_dmx: list[str] = []
    focus_pct: list[str] = []
    focus_param_dmx: dict[str, int] = {}
    focus_param_pct: dict[str, float] = {}
    if dev is not None:
        pan_ch = dev.get_channel(ChannelType.PAN)
        tilt_ch = dev.get_channel(ChannelType.TILT)
        if pan_ch is not None:
            pan_val = (
                dev.pan_degrees if is_live else float(step_dev_vals.get("pan", 0.0))
            )
            focus_params["pan"] = pan_val
            p_norm = dev.get_parameter_normalized(ChannelType.PAN)
            if is_live:
                focus_dmx.append(str(pan_ch.value))
                pct_val = (p_norm if p_norm is not None else 0.0) * 100.0
                focus_pct.append(f"{round(pct_val)}%")
                focus_param_dmx["pan"] = int(pan_ch.value)
                focus_param_pct["pan"] = pct_val
        if tilt_ch is not None:
            tilt_val = (
                dev.tilt_degrees if is_live else float(step_dev_vals.get("tilt", 0.0))
            )
            focus_params["tilt"] = tilt_val
            t_norm = dev.get_parameter_normalized(ChannelType.TILT)
            if is_live:
                focus_dmx.append(str(tilt_ch.value))
                pct_val = (t_norm if t_norm is not None else 0.0) * 100.0
                focus_pct.append(f"{round(pct_val)}%")
                focus_param_dmx["tilt"] = int(tilt_ch.value)
                focus_param_pct["tilt"] = pct_val
    else:
        for pk in ("pan", "tilt"):
            if pk in step_dev_vals:
                focus_params[pk] = float(step_dev_vals[pk])

    if "pan" in focus_params and "tilt" in focus_params:
        focus_summary = f"{round(focus_params['pan'])}°/{round(focus_params['tilt'])}°"
    elif "pan" in focus_params:
        focus_summary = f"P {round(focus_params['pan'])}°"
    elif "tilt" in focus_params:
        focus_summary = f"T {round(focus_params['tilt'])}°"
    else:
        focus_summary = ""

    f_state, f_manual, f_ref, f_prefs = _resolve_family_palette_and_states(
        "position",
        list(focus_params.keys()),
        channel=channel,
        palettes=palettes,
        live_state=live_state,
        resolved_step=resolved_step,
        is_live=is_live,
    )
    focus_snap = AttributeFamilySnapshot(
        family="position",
        available=bool(focus_params),
        tracking_state=f_state,
        is_manual=f_manual,
        palette_ref=f_ref,
        summary_value=focus_summary,
        parameters=focus_params,
        parameter_refs=f_prefs,
        percent_summary="/".join(focus_pct) if focus_pct else focus_summary,
        dmx_summary="/".join(focus_dmx) if focus_dmx else focus_summary,
        parameter_dmx=focus_param_dmx,
        parameter_percent=focus_param_pct,
        effect_ref=fx_map.get("position"),
    )

    # --- COLOR ---
    has_color = False
    preview_rgb: Optional[tuple[float, float, float]] = None
    color_params: dict[str, Any] = {}
    color_dmx: list[str] = []
    color_pct: list[str] = []
    color_param_dmx: dict[str, int] = {}
    color_param_pct: dict[str, float] = {}
    if dev is not None:
        has_color = dev.has_color_capability
        if has_color:
            if is_live:
                preview_rgb = dev.get_preview_rgb()
            else:
                preview_rgb = _resolve_step_preview_rgb(dev, step_dev_vals)
            for ctype in COLOR_CHANNEL_TYPES:
                c_ch = dev.get_channel(ctype)
                if c_ch is not None:
                    n_val = (
                        dev.get_parameter_normalized(ctype)
                        if is_live
                        else _resolve_step_emitter_norm(
                            ctype, step_dev_vals, preview_rgb
                        )
                    )
                    norm_f = n_val if n_val is not None else 0.0
                    color_params[ctype.value] = norm_f
                    if is_live:
                        color_dmx.append(str(c_ch.value))
                        color_pct.append(f"{round(norm_f * 100)}%")
                        color_param_dmx[ctype.value] = int(c_ch.value)
                        color_param_pct[ctype.value] = norm_f * 100.0
                    else:
                        color_param_dmx[ctype.value] = round(norm_f * 255.0)
                        color_param_pct[ctype.value] = norm_f * 100.0
        cct_ch = dev.get_channel(ChannelType.COLOR_TEMP)
        if cct_ch is not None:
            has_color = True
            cct_val = (
                dev.color_temp_kelvin
                if is_live
                else step_dev_vals.get("cct", step_dev_vals.get("color_temp"))
            )
            if cct_val is not None:
                color_params["cct"] = float(cct_val)
            elif not is_live:
                color_params["cct"] = 3200.0
            if is_live:
                color_dmx.append(str(cct_ch.value))
                color_param_dmx["cct"] = int(cct_ch.value)
                n_cct = dev.get_parameter_normalized(ChannelType.COLOR_TEMP)
                if n_cct is not None:
                    color_param_pct["cct"] = float(n_cct) * 100.0
        cw_ch = dev.get_channel(ChannelType.COLOR_WHEEL)
        if cw_ch is not None:
            has_color = True
            cw_val = (
                dev.get_parameter_normalized(ChannelType.COLOR_WHEEL)
                if is_live
                else step_dev_vals.get("color_wheel")
            )
            cw_norm = _normalize_lvl(float(cw_val)) if cw_val is not None else 0.0
            color_params["color_wheel"] = cw_norm
            if is_live:
                color_dmx.append(str(cw_ch.value))
                color_param_dmx["color_wheel"] = int(cw_ch.value)
                color_param_pct["color_wheel"] = cw_norm * 100.0
            else:
                color_param_dmx["color_wheel"] = round(cw_norm * 255.0)
                color_param_pct["color_wheel"] = cw_norm * 100.0
    elif "color" in step_dev_vals or any(
        k in step_dev_vals for k in _COLOR_EMITTER_NAMES
    ):
        has_color = True
        preview_rgb = _resolve_step_preview_rgb(None, step_dev_vals)
        if preview_rgb is not None:
            color_params["color"] = _format_hex_rgb(preview_rgb)

    if preview_rgb is not None:
        color_summary = _format_hex_rgb(preview_rgb)
    elif "cct" in color_params:
        color_summary = f"{round(float(color_params['cct']))}K"
    elif "color_wheel" in color_params:
        color_summary = f"CW {round(float(color_params['color_wheel']) * 100)}%"
    else:
        color_summary = ""

    color_ref_keys = list(color_params.keys())
    if has_color and not color_ref_keys:
        color_ref_keys = ["color"]
    c_state, c_manual, c_ref, c_prefs = _resolve_family_palette_and_states(
        "color",
        color_ref_keys if color_params or has_color else [],
        channel=channel,
        palettes=palettes,
        live_state=live_state,
        resolved_step=resolved_step,
        is_live=is_live,
    )
    if (
        c_manual
        and live_state is not None
        and any(
            k in _COLOR_EMITTER_NAMES
            and live_state.get_palette_ref(channel, k) is None
            and live_state.get_palette_ref(channel, "color") is None
            for k in live_state.get_manual_params(channel)
        )
        and c_ref is not None
    ):
        # Safety check: unlinked manual emitter edits clear color refs.
        c_ref = None

    color_snap = AttributeFamilySnapshot(
        family="color",
        available=has_color,
        tracking_state=c_state,
        is_manual=c_manual,
        palette_ref=c_ref,
        summary_value=color_summary,
        parameters=color_params,
        parameter_refs=c_prefs,
        percent_summary=" ".join(color_pct[:3]) if color_pct else color_summary,
        dmx_summary=" ".join(color_dmx[:4]) if color_dmx else color_summary,
        parameter_dmx=color_param_dmx,
        parameter_percent=color_param_pct,
        effect_ref=fx_map.get("color"),
    )

    # --- BEAM ---
    beam_params: dict[str, Any] = {}
    beam_dmx: list[str] = []
    beam_pct: list[str] = []
    beam_param_dmx: dict[str, int] = {}
    beam_param_pct: dict[str, float] = {}
    beam_parts: list[str] = []

    if dev is not None:
        for p_key, ctype in _BEAM_PARAM_TYPES:
            b_ch = dev.get_channel(ctype)
            if b_ch is None:
                continue
            val = _read_device_beam_value(dev, p_key, ctype, step_dev_vals, is_live)
            beam_params[p_key] = val
            if is_live:
                beam_dmx.append(str(b_ch.value))
                beam_param_dmx[p_key] = int(b_ch.value)
                n_b = dev.get_parameter_normalized(ctype)
                if n_b is not None:
                    beam_pct.append(f"{round(n_b * 100)}%")
                    beam_param_pct[p_key] = float(n_b) * 100.0
            elif p_key in ("frost", "prism") and isinstance(val, (int, float)):
                n_b = _normalize_lvl(float(val))
                beam_param_dmx[p_key] = round(n_b * 255.0)
                beam_param_pct[p_key] = n_b * 100.0
    else:
        for p_key, _ in _BEAM_PARAM_TYPES:
            if p_key in step_dev_vals:
                beam_params[p_key] = step_dev_vals[p_key]

    beam_parts.extend(_format_beam_parts(beam_params))
    beam_summary = " ".join(beam_parts[:2])

    b_state, b_manual, b_ref, b_prefs = _resolve_family_palette_and_states(
        "beam",
        list(beam_params.keys()),
        channel=channel,
        palettes=palettes,
        live_state=live_state,
        resolved_step=resolved_step,
        is_live=is_live,
    )
    beam_snap = AttributeFamilySnapshot(
        family="beam",
        available=bool(beam_params),
        tracking_state=b_state,
        is_manual=b_manual,
        palette_ref=b_ref,
        summary_value=beam_summary,
        parameters=beam_params,
        parameter_refs=b_prefs,
        percent_summary=" ".join(beam_pct[:2]) if beam_pct else beam_summary,
        dmx_summary=" ".join(beam_dmx[:2]) if beam_dmx else beam_summary,
        parameter_dmx=beam_param_dmx,
        parameter_percent=beam_param_pct,
        effect_ref=fx_map.get("beam"),
    )

    return focus_snap, color_snap, beam_snap, has_color, preview_rgb


def _read_device_beam_value(
    dev: LightingDevice,
    p_key: str,
    ctype: ChannelType,
    step_dev_vals: dict[str, Any],
    is_live: bool,
) -> Any:  # noqa: ANN401
    if is_live:
        if p_key == "zoom":
            return dev.zoom_degrees
        if p_key == "focus":
            return dev.focus_meters
        if p_key == "iris":
            return dev.iris
        if p_key == "strobe":
            return dev.strobe_hz
        if p_key == "gobo":
            return dev.gobo if dev.gobo is not None else 0
        return dev.get_parameter_normalized(ctype)
    if p_key in step_dev_vals:
        return step_dev_vals[p_key]
    if p_key == "strobe" and "shutter" in step_dev_vals:
        return step_dev_vals["shutter"]
    if p_key == "gobo" and "gobo_wheel" in step_dev_vals:
        return step_dev_vals["gobo_wheel"]
    return None


def _format_beam_parts(beam_params: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    if "zoom" in beam_params and isinstance(beam_params["zoom"], (int, float)):
        parts.append(f"{round(float(beam_params['zoom']))}°")
    if "focus" in beam_params and isinstance(beam_params["focus"], (int, float)):
        parts.append(f"{float(beam_params['focus']):.1f}m")
    if "iris" in beam_params and isinstance(beam_params["iris"], (int, float)):
        parts.append(f"Ir {round(float(beam_params['iris']))}")
    if "gobo" in beam_params and beam_params["gobo"] not in (None, 0, ""):
        parts.append(str(beam_params["gobo"]))
    if "strobe" in beam_params and isinstance(beam_params["strobe"], (int, float)):
        st = float(beam_params["strobe"])
        if st > 0.0:
            parts.append(f"{st:.1f}Hz")
    if "frost" in beam_params and isinstance(beam_params["frost"], (int, float)):
        fr = float(beam_params["frost"])
        if fr > 0.0:
            parts.append(f"Fr {round(fr * 100)}%")
    if "prism" in beam_params and isinstance(beam_params["prism"], (int, float)):
        pr = float(beam_params["prism"])
        if pr > 0.0:
            parts.append(f"Pr {round(pr * 100)}%")
    return parts


def _parse_hex_or_tuple_rgb(
    value: Any,  # noqa: ANN401
) -> Optional[tuple[float, float, float]]:
    if isinstance(value, str):
        s = value.strip().lstrip("#")
        if len(s) in (6, 8):
            try:
                return (
                    int(s[0:2], 16) / 255.0,
                    int(s[2:4], 16) / 255.0,
                    int(s[4:6], 16) / 255.0,
                )
            except ValueError:
                return None
    elif isinstance(value, (tuple, list)) and len(value) >= 3:
        return (
            max(0.0, min(1.0, float(value[0]))),
            max(0.0, min(1.0, float(value[1]))),
            max(0.0, min(1.0, float(value[2]))),
        )
    return None


def _resolve_step_preview_rgb(
    dev: Optional[LightingDevice],
    step_dev_vals: dict[str, Any],
) -> Optional[tuple[float, float, float]]:
    raw_col = step_dev_vals.get("color", step_dev_vals.get("colour"))
    parsed = _parse_hex_or_tuple_rgb(raw_col)
    if parsed is not None:
        return parsed
    if dev is not None and dev.is_subtractive_cmy:
        c = _normalize_lvl(float(step_dev_vals.get("cyan", 0.0)))
        m = _normalize_lvl(float(step_dev_vals.get("magenta", 0.0)))
        y = _normalize_lvl(float(step_dev_vals.get("yellow", 0.0)))
        return (1.0 - c, 1.0 - m, 1.0 - y)
    if any(k in step_dev_vals for k in ("red", "green", "blue")):
        return (
            _normalize_lvl(float(step_dev_vals.get("red", 0.0))),
            _normalize_lvl(float(step_dev_vals.get("green", 0.0))),
            _normalize_lvl(float(step_dev_vals.get("blue", 0.0))),
        )
    if dev is not None and dev.has_color_capability:
        return (1.0, 1.0, 1.0)
    return None


def _resolve_step_emitter_norm(
    ctype: ChannelType,
    step_dev_vals: dict[str, Any],
    preview_rgb: Optional[tuple[float, float, float]],
) -> Optional[float]:
    if ctype.value in step_dev_vals:
        return _normalize_lvl(float(step_dev_vals[ctype.value]))
    if preview_rgb is None:
        return 0.0
    if ctype == ChannelType.RED:
        return preview_rgb[0]
    if ctype == ChannelType.GREEN:
        return preview_rgb[1]
    if ctype == ChannelType.BLUE:
        return preview_rgb[2]
    if ctype == ChannelType.CYAN:
        return 1.0 - preview_rgb[0]
    if ctype == ChannelType.MAGENTA:
        return 1.0 - preview_rgb[1]
    if ctype == ChannelType.YELLOW:
        return 1.0 - preview_rgb[2]
    return 0.0


def build_live_channel_snapshot(  # pylint: disable=too-many-locals, too-many-branches
    app: CoreApplication,
    channel: int,
    *,
    resolved_step: Optional[ResolvedState] = None,
    prev_resolved: Optional[ResolvedState] = None,
    next_levels: Optional[typing.Sequence[float]] = None,
) -> ChannelDisplaySnapshot:
    """Build a consolidated ChannelDisplaySnapshot from live CoreApplication state."""
    ch = int(channel)
    lightshow = app.lightshow
    patch = getattr(lightshow, "patch", None)
    dev = patch.devices.get(ch) if patch is not None else None
    is_patched = dev is not None and bool(getattr(dev, "channels", ()))
    is_selected = ch in getattr(app, "selected_channels", ())

    park_mgr = getattr(lightshow, "park", None)
    is_parked = bool(
        park_mgr is not None
        and hasattr(park_mgr, "is_channel_parked")
        and park_mgr.is_channel_parked(ch)
    )

    main_pb = getattr(lightshow, "main_playback", None)
    main_pos = getattr(main_pb, "position", 0) if main_pb is not None else 0
    if (
        resolved_step is None
        and main_pb is not None
        and isinstance(getattr(main_pb, "steps", None), list)
        and 0 <= main_pos < len(main_pb.steps)
    ):
        resolved_step = TrackingEngine.resolve_step_state(
            main_pb,
            main_pos,
            tracking_mode=bool(getattr(main_pb, "tracking_mode", False)),
            patch=patch,
        )

    palettes = getattr(lightshow, "palettes", None)
    live_state: Optional[LiveParameterState] = getattr(app, "live_state", None)
    backend = getattr(app, "backend", None)
    dmx = getattr(backend, "dmx", None) if backend is not None else None

    main_fader_val = app.get_main_fader_value()
    raw_user = app.get_user_channel_level(ch - 1) if 1 <= ch <= MAX_CHANNELS else -1.0

    # Determine live intensity level, source, and tracking state
    intensity_norm = 0.0
    intensity_source = "none"
    intensity_state = TrackingDisplayState.INACTIVE
    intensity_color = get_tracking_color(TrackingDisplayState.INACTIVE)

    if is_parked and park_mgr is not None:
        park_val = park_mgr.get_channel_park_level(ch)
        intensity_norm = (
            _normalize_lvl(float(park_val)) if park_val is not None else 0.0
        )
        intensity_source = "park"
        intensity_state = TrackingDisplayState.INACTIVE
        intensity_color = dict(_PARK_COLOR)
    else:
        raw_comp, raw_col = app.get_channel_composite_level(ch - 1)
        seq_lvl = (
            float(dmx.levels["sequence"][ch - 1])
            if dmx is not None and isinstance(getattr(dmx, "levels", None), dict)
            else 0.0
        )
        regular_fader_lvl = (
            float(dmx.levels["faders"][ch - 1])
            if dmx is not None and isinstance(getattr(dmx, "levels", None), dict)
            else 0.0
        )
        gm_exempt_lvl = (
            float(dmx.levels["faders_gm_exempt"][ch - 1])
            if dmx is not None
            and isinstance(getattr(dmx, "levels", None), dict)
            and "faders_gm_exempt" in dmx.levels
            else 0.0
        )
        intensity_norm = _normalize_lvl(
            max(float(raw_comp) * main_fader_val, gm_exempt_lvl)
        )
        fader_lvl = max(regular_fader_lvl, gm_exempt_lvl)
        inde_arr = getattr(getattr(lightshow, "independents", None), "dmx", ())
        inde_lvl = float(inde_arr[ch - 1]) if 1 <= ch <= len(inde_arr) else 0.0

        if raw_user >= 0.0:
            intensity_source = "manual"
            intensity_state = TrackingDisplayState.MANUAL
            intensity_color = get_tracking_color(TrackingDisplayState.MANUAL)
        elif inde_lvl > max(seq_lvl, fader_lvl):
            intensity_source = "independent"
            intensity_state = TrackingDisplayState.INACTIVE
            intensity_color = dict(_INDEP_COLOR)
        elif fader_lvl > seq_lvl:
            intensity_source = "fader"
            intensity_state = TrackingDisplayState.INACTIVE
            intensity_color = dict(_FADER_COLOR)
        else:
            step_state, _ = classify_channel_tracking_state(
                main_pb,
                main_pos,
                ch,
                curr_resolved=resolved_step,
                prev_resolved=prev_resolved,
            )
            intensity_state = step_state
            intensity_color = (
                dict(raw_col) if raw_col else get_tracking_color(step_state)
            )
            intensity_source = (
                "cue" if step_state is not TrackingDisplayState.INACTIVE else "none"
            )

    # Intensity palette reference
    int_ref_display: Optional[PaletteRefDisplay] = None
    if intensity_source == "manual":
        int_ref, _ = _lookup_live_param_ref(live_state, resolved_step, ch, "intensity")
        if int_ref is not None:
            int_ref_display = _make_palette_ref_display(palettes, int_ref)
    elif (
        intensity_source == "cue"
        and intensity_state is not TrackingDisplayState.INACTIVE
    ):
        int_ref = _lookup_step_param_ref(resolved_step, ch, "intensity")
        if int_ref is not None:
            int_ref_display = _make_palette_ref_display(palettes, int_ref)

    next_intensity: Optional[float] = None
    if next_levels is not None and 1 <= ch <= len(next_levels):
        next_intensity = _normalize_lvl(float(next_levels[ch - 1]) * main_fader_val)

    effects = getattr(lightshow, "effects", None)
    eff_eng = getattr(app, "effects_engine", None)
    fx_by_fam = _resolve_channel_effect_refs_by_family(
        ch,
        effects=effects,
        effects_engine=eff_eng,
        live_state=live_state,
        resolved_step=resolved_step,
        is_live=True,
    )

    focus_snap, color_snap, beam_snap, has_color, preview_rgb = (
        _build_device_family_snapshots(
            dev,
            channel=ch,
            palettes=palettes,
            live_state=live_state,
            resolved_step=resolved_step,
            is_live=True,
            family_effect_refs=fx_by_fam,
        )
    )

    has_live_fx = bool(
        live_state is not None
        and hasattr(live_state, "get_effect_ref")
        and live_state.get_effect_ref(ch) is not None
    )
    is_manual = (
        raw_user >= 0.0
        or has_live_fx
        or focus_snap.is_manual
        or color_snap.is_manual
        or beam_snap.is_manual
    )
    has_fcb_move = (
        (resolved_step.has_fcb_move(ch) if resolved_step is not None else False)
        or focus_snap.is_manual
        or color_snap.is_manual
        or beam_snap.is_manual
    )
    is_mib = resolved_step.is_mib(ch) if resolved_step is not None else False

    has_non_dimmer = bool(dev is not None and dev.fixture_type != FixtureType.DIMMER)
    device_label = str(dev.label) if dev is not None else ""
    fixture_name = str(dev.fixture_name) if dev is not None else ""
    address_str = (
        f"{dev.universe_display_str}/{dev.address_range_str}"
        if dev is not None and dev.channels
        else ""
    )

    return ChannelDisplaySnapshot(
        channel=ch,
        is_patched=is_patched,
        is_selected=is_selected,
        is_parked=is_parked,
        is_manual=is_manual,
        intensity=intensity_norm,
        next_intensity=next_intensity,
        intensity_state=intensity_state,
        intensity_source=intensity_source,
        intensity_color=intensity_color,
        intensity_ref=int_ref_display,
        has_device=has_non_dimmer,
        is_moving_head=_is_dev_moving_head(dev),
        device_label=device_label,
        fixture_name=fixture_name,
        address_str=address_str,
        has_color=has_color,
        preview_rgb=preview_rgb,
        focus=focus_snap,
        color=color_snap,
        beam=beam_snap,
        has_fcb_move=has_fcb_move,
        is_mib=is_mib,
        intensity_effect_ref=fx_by_fam.get("intensity"),
        effect_ref=fx_by_fam.get("any"),
    )


def _build_static_snapshot_from_state(  # pylint: disable=too-many-locals, too-many-arguments
    lightshow: LightShow,
    ch: int,
    *,
    int_state: TrackingDisplayState,
    raw_lvl: float,
    resolved_step: ResolvedState,
    override_level: Optional[float] = None,
) -> ChannelDisplaySnapshot:
    """Assemble a static Cue or Sequence step ChannelDisplaySnapshot."""
    patch = getattr(lightshow, "patch", None)
    dev = patch.devices.get(ch) if patch is not None else None
    is_patched = dev is not None and bool(getattr(dev, "channels", ()))
    palettes = getattr(lightshow, "palettes", None)

    if override_level is not None and float(override_level) >= 0.0:
        intensity_norm = _normalize_lvl(float(override_level))
        eff_int_state = TrackingDisplayState.MANUAL
        intensity_color = get_tracking_color(TrackingDisplayState.MANUAL)
        intensity_source = "manual"
        is_manual = True
    else:
        intensity_norm = _normalize_lvl(float(raw_lvl))
        eff_int_state = int_state
        intensity_color = get_tracking_color(int_state)
        intensity_source = (
            "cue" if int_state is not TrackingDisplayState.INACTIVE else "none"
        )
        is_manual = False

    int_ref_display: Optional[PaletteRefDisplay] = None
    if eff_int_state is not TrackingDisplayState.INACTIVE and not is_manual:
        int_ref = _lookup_step_param_ref(resolved_step, ch, "intensity")
        if int_ref is not None:
            int_ref_display = _make_palette_ref_display(palettes, int_ref)

    effects = getattr(lightshow, "effects", None)
    fx_by_fam = _resolve_channel_effect_refs_by_family(
        ch,
        effects=effects,
        effects_engine=None,
        live_state=None,
        resolved_step=resolved_step,
        is_live=False,
    )

    focus_snap, color_snap, beam_snap, has_color, preview_rgb = (
        _build_device_family_snapshots(
            dev,
            channel=ch,
            palettes=palettes,
            live_state=None,
            resolved_step=resolved_step,
            is_live=False,
            family_effect_refs=fx_by_fam,
        )
    )

    has_non_dimmer = bool(dev is not None and dev.fixture_type != FixtureType.DIMMER)
    device_label = str(dev.label) if dev is not None else ""
    fixture_name = str(dev.fixture_name) if dev is not None else ""
    address_str = (
        f"{dev.universe_display_str}/{dev.address_range_str}"
        if dev is not None and dev.channels
        else ""
    )

    return ChannelDisplaySnapshot(
        channel=ch,
        is_patched=is_patched,
        is_selected=False,
        is_parked=False,
        is_manual=is_manual,
        intensity=intensity_norm,
        next_intensity=None,
        intensity_state=eff_int_state,
        intensity_source=intensity_source,
        intensity_color=intensity_color,
        intensity_ref=int_ref_display,
        has_device=has_non_dimmer,
        is_moving_head=_is_dev_moving_head(dev),
        device_label=device_label,
        fixture_name=fixture_name,
        address_str=address_str,
        has_color=has_color,
        preview_rgb=preview_rgb,
        focus=focus_snap,
        color=color_snap,
        beam=beam_snap,
        has_fcb_move=resolved_step.has_fcb_move(ch),
        is_mib=resolved_step.is_mib(ch),
        intensity_effect_ref=fx_by_fam.get("intensity"),
        effect_ref=fx_by_fam.get("any"),
    )


def build_step_channel_snapshot(  # pylint: disable=too-many-locals
    lightshow: LightShow,
    sequence: Any,  # noqa: ANN401
    step_index: int,
    channel: int,
    *,
    resolved_step: Optional[ResolvedState] = None,
    prev_resolved: Optional[ResolvedState] = None,
    override_level: Optional[float] = None,
) -> ChannelDisplaySnapshot:
    """Build a ChannelDisplaySnapshot for a static Sequence step."""
    ch = int(channel)
    patch = getattr(lightshow, "patch", None)
    tracking_mode = bool(getattr(sequence, "tracking_mode", False))

    if resolved_step is None:
        resolved_step = TrackingEngine.resolve_step_state(
            sequence, step_index, tracking_mode=tracking_mode, patch=patch
        )
    if prev_resolved is None and step_index > 1:
        prev_resolved = TrackingEngine.resolve_step_state(
            sequence, step_index - 1, tracking_mode=tracking_mode, patch=patch
        )

    int_state, raw_lvl = classify_channel_tracking_state(
        sequence,
        step_index,
        ch,
        curr_resolved=resolved_step,
        prev_resolved=prev_resolved,
    )
    return _build_static_snapshot_from_state(
        lightshow,
        ch,
        int_state=int_state,
        raw_lvl=float(raw_lvl),
        resolved_step=resolved_step,
        override_level=override_level,
    )


def build_cue_channel_snapshot(
    lightshow: LightShow,
    cue: Any,  # noqa: ANN401
    channel: int,
    *,
    override_level: Optional[float] = None,
) -> ChannelDisplaySnapshot:
    """Build an isolated ChannelDisplaySnapshot for a standalone Cue."""
    ch = int(channel)
    raw_lvl = float(cue.get_level(ch)) if hasattr(cue, "get_level") else 0.0
    if 1 <= ch <= MAX_CHANNELS:
        ch_arr = np.zeros(MAX_CHANNELS, dtype=np.float64)
        ch_arr[ch - 1] = raw_lvl
    else:
        ch_arr = np.zeros(MAX_CHANNELS, dtype=np.float64)

    cue_dev_vals = getattr(cue, "device_values", {})
    ch_dev_vals = (
        dict(cue_dev_vals.get(ch, {})) if isinstance(cue_dev_vals, dict) else {}
    )

    cue_refs = getattr(cue, "palette_refs", {})
    ch_refs = dict(cue_refs.get(ch, {})) if isinstance(cue_refs, dict) else {}

    cue_fx_refs = getattr(cue, "effect_refs", {})
    ch_fx_ref = (
        dict(cue_fx_refs[ch])
        if isinstance(cue_fx_refs, dict) and isinstance(cue_fx_refs.get(ch), dict)
        else None
    )

    active_families: set[str] = set()
    for p_name in ch_dev_vals:
        fam = LiveParameterState.normalize_family(get_parameter_family(str(p_name)))
        if fam in ("position", "color", "beam"):
            active_families.add(fam)
    for r_key, r_val in ch_refs.items():
        if str(r_key) == "*" and isinstance(r_val, (tuple, list)) and r_val:
            fam = LiveParameterState.normalize_family(str(r_val[0]))
        else:
            fam = LiveParameterState.normalize_family(get_parameter_family(str(r_key)))
        if fam in ("position", "color", "beam"):
            active_families.add(fam)

    fam_states: dict[str, TrackingDisplayState] = {
        fam: (
            TrackingDisplayState.HARD_VALUE
            if fam in active_families
            else TrackingDisplayState.INACTIVE
        )
        for fam in ("position", "color", "beam")
    }

    cue_resolved = ResolvedState(
        channels=ch_arr,
        device_values={ch: ch_dev_vals} if ch_dev_vals else {},
        palette_refs={ch: ch_refs} if ch_refs else {},
        effect_refs={ch: ch_fx_ref} if ch_fx_ref else {},
        family_states={ch: fam_states},
    )
    int_state = (
        TrackingDisplayState.HARD_VALUE
        if raw_lvl > 0.0
        else TrackingDisplayState.INACTIVE
    )
    return _build_static_snapshot_from_state(
        lightshow,
        ch,
        int_state=int_state,
        raw_lvl=raw_lvl,
        resolved_step=cue_resolved,
        override_level=override_level,
    )


__all__ = [
    "AttributeFamilySnapshot",
    "ChannelDisplaySnapshot",
    "PaletteRefDisplay",
    "build_cue_channel_snapshot",
    "build_live_channel_snapshot",
    "build_step_channel_snapshot",
    "format_family_readout",
    "format_parameter_readout",
    "format_short_palette_ref",
]
