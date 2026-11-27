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
"""Background execution threads and state interpolation for sequence playback."""

from __future__ import annotations

import threading
import time
import typing
from typing import Optional

import numpy as np

from olc.core.tracking import DEFAULT_MIB_FADE_TIME, TrackingEngine
from olc.define import MAX_CHANNELS
from olc.devices.channel import COLOR_CHANNEL_TYPES, ChannelType
from olc.show.step import Step, get_parameter_family

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication
    from olc.show.patch import PatchManager
    from olc.show.sequence import Sequence


def get_cue(step: Step) -> typing.Any:  # noqa: ANN401
    """Get the cue object from step as Any to simplify type checking."""
    return step.cue


_INTERPOLATABLE_NORM_CHANNEL_TYPES: tuple[ChannelType, ...] = (
    ChannelType.RED,
    ChannelType.GREEN,
    ChannelType.BLUE,
    ChannelType.WHITE,
    ChannelType.AMBER,
    ChannelType.LIME,
    ChannelType.CYAN,
    ChannelType.INDIGO,
    ChannelType.MAGENTA,
    ChannelType.YELLOW,
    ChannelType.COLOR_WHEEL,
    ChannelType.GOBO_WHEEL,
    ChannelType.FROST,
    ChannelType.PRISM,
)
_COLOR_PARAM_NAMES: frozenset[str] = frozenset(
    {
        "color",
        "colour",
        "red",
        "green",
        "blue",
        "white",
        "amber",
        "lime",
        "cyan",
        "indigo",
        "magenta",
        "yellow",
        "color_wheel",
        "cct",
        "color_temp",
        "colortemp",
    }
)


def _get_device_preview_rgb(
    dev: typing.Any,  # noqa: ANN401
) -> Optional[tuple[float, float, float]]:
    """Return normalized (r, g, b) preview color from *dev* if color-capable."""
    fn = getattr(dev, "get_preview_rgb", None)
    if callable(fn):
        preview = fn()
        if preview is not None:
            return (float(preview[0]), float(preview[1]), float(preview[2]))
    return None


def _snapshot_dev_diff_state(
    dev: typing.Any,  # noqa: ANN401
) -> tuple[
    Optional[tuple[float, float, float]],
    Optional[tuple[float, float, float]],
    tuple[int, ...],
    float,
]:
    """Capture lightweight device state for change detection during fades."""
    preview = _get_device_preview_rgb(dev)
    srgb = getattr(dev, "color_srgb", None)
    srgb_t = (float(srgb.r), float(srgb.g), float(srgb.b)) if srgb is not None else None
    dmx_vals = tuple(int(ch.value) for ch in getattr(dev, "channels", ()))
    intensity = float(getattr(dev, "intensity", 0.0))
    return (preview, srgb_t, dmx_vals, intensity)


def _has_device_changed(
    before: tuple[
        Optional[tuple[float, float, float]],
        Optional[tuple[float, float, float]],
        tuple[int, ...],
        float,
    ],
    dev: typing.Any,  # noqa: ANN401
    *,
    touched_color_param: bool = False,
) -> tuple[bool, bool]:
    """Compare device state against *before*; return (changed, color_changed)."""
    after_preview, after_srgb, after_dmx, after_int = _snapshot_dev_diff_state(dev)
    b_preview, b_srgb, b_dmx, b_int = before

    rgb_moved = False
    if b_preview is not None and after_preview is not None:
        rgb_moved = any(
            abs(a - b) > 1e-4 for a, b in zip(b_preview, after_preview, strict=False)
        )
    elif b_srgb is not None and after_srgb is not None:
        rgb_moved = any(
            abs(a - b) > 1e-4 for a, b in zip(b_srgb, after_srgb, strict=False)
        )

    dmx_moved = b_dmx != after_dmx
    int_moved = abs(after_int - b_int) > 1e-5
    color_moved = rgb_moved or (dmx_moved and touched_color_param)
    any_moved = color_moved or dmx_moved or int_moved
    return any_moved, color_moved


def _emit_device_changes(
    app: Optional[CoreApplication],
    changed_devices: set[int],
    color_changed: set[int],
) -> None:
    """Emit differential device color and parameter events onto *app*."""
    if app is None or not changed_devices or not hasattr(app, "emit"):
        return
    if color_changed:
        app.emit("device.color_changed", sorted(color_changed), None)
    param_only = changed_devices - color_changed
    if param_only:
        app.emit("device.parameters_changed", sorted(param_only))


def _has_user_intensity_override(app: Optional[CoreApplication], channel: int) -> bool:
    """Return True if *channel* holds a manual intensity override in DMX levels."""
    if app is None:
        return False
    backend = getattr(app, "backend", None)
    dmx = getattr(backend, "dmx", None) if backend is not None else None
    levels = getattr(dmx, "levels", None) if dmx is not None else None
    if isinstance(levels, dict):
        user_arr = levels.get("user")
        if user_arr is not None and 1 <= channel <= len(user_arr):
            return float(user_arr[channel - 1]) >= 0.0
    return False


def _apply_resolved_device_values(
    patch: Optional[PatchManager],
    resolved: typing.Any,  # noqa: ANN401
    app: Optional[CoreApplication] = None,
    *,
    clear_live_state: bool = True,
    force_assert: bool = False,
) -> tuple[set[int], set[int]]:
    """Apply final resolved device values, emit events, and update live_state."""
    changed_devices: set[int] = set()
    color_changed: set[int] = set()
    device_values = getattr(resolved, "device_values", None)
    if patch is None or not device_values:
        return changed_devices, color_changed

    live_state = getattr(app, "live_state", None) if app is not None else None
    for dev_id, params in device_values.items():
        dev = patch.get_device(dev_id)
        if dev is None:
            continue
        before = _snapshot_dev_diff_state(dev)
        dev.apply_device_values(params)
        touched_color = any(str(k).lower() in _COLOR_PARAM_NAMES for k in params)
        any_moved, col_moved = _has_device_changed(
            before, dev, touched_color_param=touched_color
        )
        if any_moved or force_assert:
            changed_devices.add(dev_id)
            if col_moved or (force_assert and touched_color):
                color_changed.add(dev_id)
        if (clear_live_state or force_assert) and live_state is not None:
            to_clear = [
                k
                for k in params
                if not (
                    str(k).lower() == "intensity"
                    and _has_user_intensity_override(app, dev_id)
                )
            ]
            if to_clear:
                live_state.clear_params(dev_id, to_clear)

    _emit_device_changes(app, changed_devices, color_changed)
    return changed_devices, color_changed


def apply_arbitrated_output(
    app: Optional[CoreApplication],
    backend: typing.Any,  # noqa: ANN401
    patch: Optional[PatchManager],
    composed: typing.Any,  # noqa: ANN401
    *,
    force_assert: bool = False,
    clear_live_state: bool = True,
    released_to_home: dict[int, set[str]] | None = None,
) -> None:
    """Push composed PlaybackArbitrator output to DMX, devices, and Live state."""
    if (
        backend is not None
        and hasattr(backend, "dmx")
        and hasattr(backend.dmx, "levels")
        and "sequence" in backend.dmx.levels
    ):
        n_ch = min(len(backend.dmx.levels["sequence"]), len(composed.intensities))
        backend.dmx.levels["sequence"][:n_ch] = composed.intensities[:n_ch]

    if patch is not None:
        if getattr(composed, "device_values", None):
            _apply_resolved_device_values(
                patch,
                composed,
                app,
                clear_live_state=clear_live_state,
                force_assert=force_assert,
            )
        merged_released: dict[int, set[str]] = {}
        comp_released = getattr(composed, "released_to_home", None)
        if comp_released:
            for dev_id, params in comp_released.items():
                merged_released.setdefault(dev_id, set()).update(params)
        if released_to_home:
            for dev_id, params in released_to_home.items():
                merged_released.setdefault(dev_id, set()).update(params)

        if merged_released:
            comp_intensities = getattr(composed, "intensities", None)
            changed_home: set[int] = set()
            color_home: set[int] = set()
            for dev_id, params in merged_released.items():
                dev = patch.get_device(dev_id)
                if dev is None:
                    continue
                home_vals: dict[str, typing.Any] = {}
                for p in params:
                    p_low = str(p).lower()
                    if p_low in ("color", "colour"):
                        home_vals["color"] = "#ffffff"
                    elif p_low in ("pan", "tilt"):
                        home_vals[p_low] = 0.5
                    elif p_low == "intensity":
                        comp_int = (
                            float(comp_intensities[dev_id - 1])
                            if comp_intensities is not None
                            and 1 <= dev_id <= len(comp_intensities)
                            else 0.0
                        )
                        if (
                            not _has_user_intensity_override(app, dev_id)
                            and comp_int <= 0.0
                        ):
                            home_vals["intensity"] = 0.0
                    else:
                        home_vals[p_low] = 0.0
                if home_vals and hasattr(dev, "apply_device_values"):
                    dev.apply_device_values(home_vals)
                    changed_home.add(dev_id)
                    if "color" in home_vals:
                        color_home.add(dev_id)
            if changed_home:
                _emit_device_changes(app, changed_home, color_home)

    if backend is not None and hasattr(backend, "dmx") and backend.dmx is not None:
        backend.dmx.set_levels()


def is_main_sequence(seq: typing.Any) -> bool:  # noqa: ANN401
    """Return True iff *seq* is currently configured as the Main Sequence."""
    app = getattr(seq, "app", None)
    engine = getattr(app, "playback_engine", None) if app is not None else None
    seq_idx = float(getattr(seq, "index", 1.0))
    if engine is not None:
        return bool(engine.is_main_sequence(seq_idx))
    return seq_idx == 1.0


def _notify_runner(
    seq: typing.Any,  # noqa: ANN401
    state_value: str,
    *,
    fade_progress: float = 0.0,
    fade_remaining: float = 0.0,
) -> None:
    """Update PlaybackEngine runner telemetry if available."""
    app = getattr(seq, "app", None)
    engine = getattr(app, "playback_engine", None) if app is not None else None
    if engine is None:
        return
    from olc.core.playback_engine import RunnerState

    engine.notify_runner_state(
        float(getattr(seq, "index", 1.0)),
        RunnerState(state_value),
        fade_progress=fade_progress,
        fade_remaining=fade_remaining,
    )


def _sync_resolved_effects(  # pylint: disable=too-many-locals,too-many-branches
    app: Optional[CoreApplication],
    resolved: typing.Any,  # noqa: ANN401
    *,
    fade_time: float = 0.0,
    clear_live_state: bool = True,
) -> None:
    """Synchronize the EffectsEngine with resolved cue effect_refs.

    Ensures phase continuity across tracked cues and applies Fade-by-Size over
    *fade_time* seconds when effects start or stop during a cue transition.
    """
    if app is None:
        return
    eff_eng = getattr(app, "effects_engine", None)
    if eff_eng is None:
        return

    effect_refs = getattr(resolved, "effect_refs", None)
    if not isinstance(effect_refs, dict):
        effect_refs = {}

    live_state = getattr(app, "live_state", None)
    manual_effect_channels: set[int] = set()
    if (
        not clear_live_state
        and live_state is not None
        and hasattr(live_state, "get_all_effect_refs")
    ):
        manual_effect_channels = set(live_state.get_all_effect_refs().keys())

    # Group resolved channel effect specs by effect_number while preserving order
    grouped: dict[
        float,
        tuple[
            list[tuple[int, int]],
            dict[str, typing.Any],
        ],
    ] = {}
    target_channels_by_fx: dict[float, set[int]] = {}
    for ch_raw, spec in effect_refs.items():
        ch = int(ch_raw)
        if ch in manual_effect_channels:
            continue
        if not isinstance(spec, dict) or spec.get("stop"):
            continue
        fx_num = spec.get("effect")
        if fx_num is None:
            fx_num = spec.get("effect_number")
        if fx_num is None:
            continue
        fx_id = float(fx_num)
        sel_idx = int(spec.get("order_index", spec.get("selection_index", 0)))
        if fx_id not in grouped:
            grouped[fx_id] = ([], dict(spec))
        grouped[fx_id][0].append((sel_idx, ch))
        target_channels_by_fx.setdefault(fx_id, set()).add(ch)

    # Stop any running effects (or channels) not present in target resolved state
    if hasattr(eff_eng, "get_active_instances"):
        for inst in eff_eng.get_active_instances():
            fx_id = float(inst.effect_number)
            keep_set = target_channels_by_fx.get(fx_id, set()) | (
                set(inst.channels) & manual_effect_channels
            )
            drop_channels = [ch for ch in inst.channels if ch not in keep_set]
            if drop_channels:
                if len(drop_channels) == len(inst.channels):
                    eff_eng.stop_effect(effect_number=fx_id, fade_out=fade_time)
                else:
                    eff_eng.stop_effect(channels=drop_channels, fade_out=fade_time)

    # Start or update target resolved effects (preserving phase when already active)
    for fx_id, (indexed_channels, first_spec) in grouped.items():
        indexed_channels.sort(key=lambda item: (item[0], item[1]))
        ordered_channels = [ch for _idx, ch in indexed_channels]
        eff_eng.start_effect(
            fx_id,
            ordered_channels,
            fade_in=fade_time,
            rate_scale=float(first_spec.get("rate_scale", 1.0)),
            size_scale=float(first_spec.get("size_scale", 1.0)),
            groups_override=first_spec.get("groups", first_spec.get("groups_override")),
            blocks_override=first_spec.get("blocks", first_spec.get("blocks_override")),
            wings_override=first_spec.get("wings", first_spec.get("wings_override")),
        )

    if (
        clear_live_state
        and live_state is not None
        and hasattr(live_state, "clear_effect_refs")
    ):
        live_state.clear_effect_refs()


def _apply_execute_preset(
    sequence: Sequence,
    backend: typing.Any,  # noqa: ANN401
    app: Optional[CoreApplication],
    target_cue: typing.Any,  # noqa: ANN401
) -> None:
    """Trigger a referenced Submaster/Preset from Eos ``$$Action Execute S``."""
    exec_num_raw = getattr(target_cue, "execute_preset", None)
    if exec_num_raw is None:
        return
    exec_num = float(exec_num_raw)
    lightshow = getattr(sequence, "lightshow", None)
    if lightshow is None and app is not None:
        lightshow = getattr(app, "lightshow", None)
    if lightshow is None:
        return

    from olc.show.fader import FaderPreset  # pylint: disable=import-outside-toplevel
    from olc.show.palette import (  # pylint: disable=import-outside-toplevel
        PaletteCategory,
    )

    mounted = False
    faders = getattr(getattr(lightshow, "fader_bank", None), "faders", None)
    if isinstance(faders, dict):
        for page_faders in faders.values():
            if not isinstance(page_faders, dict):
                continue
            for fader in page_faders.values():
                if (
                    isinstance(fader, FaderPreset)
                    and getattr(getattr(fader, "contents", None), "number", None)
                    == exec_num
                ):
                    fader.set_level(1.0)
                    mounted = True
    if mounted:
        return

    palettes = getattr(lightshow, "palettes", None)
    preset = (
        palettes.get(PaletteCategory.PRESET, exec_num) if palettes is not None else None
    )
    if preset is None:
        return

    if (
        backend
        and hasattr(backend, "dmx")
        and hasattr(backend.dmx, "levels")
        and "sequence" in backend.dmx.levels
    ):
        seq_levels = backend.dmx.levels["sequence"]
        for ch_raw, lvl in getattr(preset, "channels", {}).items():
            ch_int = int(ch_raw)
            if 1 <= ch_int <= len(seq_levels):
                seq_levels[ch_int - 1] = max(float(seq_levels[ch_int - 1]), float(lvl))
    if sequence.patch is not None and getattr(preset, "device_values", None):
        _apply_resolved_device_values(
            sequence.patch, preset, app, clear_live_state=True
        )


def _capture_device_states(
    patch: Optional[PatchManager],
) -> dict[int, dict[str, typing.Any]]:
    """Capture current physical attribute states of all patched devices."""
    states: dict[int, dict[str, typing.Any]] = {}
    if patch is None:
        return states
    for dev_id, dev in getattr(patch, "devices", {}).items():
        rgb = _get_device_preview_rgb(dev)
        if rgb is None:
            srgb = getattr(dev, "color_srgb", None)
            rgb = (srgb.r, srgb.g, srgb.b) if srgb is not None else (0.0, 0.0, 0.0)
        norm_params: dict[str, float] = {}
        get_norm = getattr(dev, "get_parameter_normalized", None)
        get_ch = getattr(dev, "get_channel", None)
        if callable(get_norm) and callable(get_ch):
            for ctype in _INTERPOLATABLE_NORM_CHANNEL_TYPES:
                if get_ch(ctype) is not None:
                    n_val = get_norm(ctype)
                    if n_val is not None:
                        norm_params[ctype.value] = float(n_val)
        get_by_label = getattr(dev, "get_channel_normalized_by_label", None)
        if callable(get_by_label):
            for ch in getattr(dev, "channels", ()):
                if (
                    ch.channel_type == ChannelType.GENERIC
                    and not ch.fine
                    and not ch.ultra_fine
                    and ch.label
                ):
                    n_val = get_by_label(ch.label)
                    if n_val is not None:
                        norm_params[ch.label.lower()] = float(n_val)
        states[dev_id] = {
            "intensity": getattr(dev, "intensity", 0.0),
            "pan": getattr(dev, "pan_degrees", 0.0),
            "tilt": getattr(dev, "tilt_degrees", 0.0),
            "zoom": getattr(dev, "zoom_degrees", None),
            "focus": getattr(dev, "focus_meters", None),
            "strobe": getattr(dev, "strobe_hz", None),
            "cct": getattr(dev, "color_temp_kelvin", None),
            "iris": getattr(dev, "iris", None),
            "color_rgb": rgb,
            "norm_params": norm_params,
        }
    return states


def _parse_rgb_norm(value: typing.Any) -> Optional[tuple[float, float, float]]:  # noqa: ANN401
    """Parse hex color or RGB tuple into normalized (r, g, b) in [0.0, 1.0]."""
    if isinstance(value, str):
        hex_str = value.strip().lstrip("#")
        if len(hex_str) in (6, 8):
            try:
                return (
                    int(hex_str[0:2], 16) / 255.0,
                    int(hex_str[2:4], 16) / 255.0,
                    int(hex_str[4:6], 16) / 255.0,
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


def _is_continuous_norm_param(dev: typing.Any, p_lower: str) -> bool:  # noqa: ANN401
    """Return True if *p_lower* is continuous (not a discrete multi-range wheel)."""
    if p_lower in ("gobo_wheel", "gobo", "gobo_select_2", "color_wheel"):
        return False
    ch = None
    try:
        ctype = ChannelType(p_lower)
    except ValueError:
        ctype = None
    if ctype is not None:
        get_ch = getattr(dev, "get_channel", None)
        if callable(get_ch):
            ch = get_ch(ctype)
    if ch is None:
        get_res_lbl = getattr(dev, "_get_resolution_channels_by_label", None)
        if callable(get_res_lbl):
            res = get_res_lbl(p_lower)
            if isinstance(res, tuple) and res:
                ch = res[0]
    ranges = getattr(ch, "ranges", None) if ch is not None else None
    return not (isinstance(ranges, list) and ranges)


def _build_fade_target_device_values(
    resolved: typing.Any,  # noqa: ANN401
    old_device_states: dict[int, dict[str, typing.Any]],
) -> dict[int, dict[str, typing.Any]]:
    """Build target device_values including 0.0 intensity for lit missing devices."""
    raw_dev_values = getattr(resolved, "device_values", None) or {}
    target: dict[int, dict[str, typing.Any]] = {
        dev_id: dict(params) for dev_id, params in raw_dev_values.items()
    }
    resolved_channels = getattr(resolved, "channels", ())
    for dev_id, start_state in old_device_states.items():
        if float(start_state.get("intensity", 0.0)) <= 0.0:
            continue
        existing = target.get(dev_id)
        if existing and "intensity" in {str(k).lower() for k in existing}:
            continue
        ch_lvl = (
            float(resolved_channels[dev_id - 1])
            if 1 <= dev_id <= len(resolved_channels)
            else 0.0
        )
        target.setdefault(dev_id, {})["intensity"] = ch_lvl
    return target


def _interpolate_device_states(  # pylint: disable=too-many-locals, too-many-arguments, too-many-positional-arguments, too-many-branches
    patch: Optional[PatchManager],
    start_states: dict[int, dict[str, typing.Any]],
    target_values: dict[int, dict[str, typing.Any]],
    factor: float,
    mib_factors: Optional[dict[int, float]] = None,
    mib_parameters: Optional[dict[int, set[str]]] = None,
    intensity_out_factors: Optional[dict[int, float]] = None,
    family_factors: Optional[dict[str, float]] = None,
    explicit_families: Optional[set[str]] = None,
    color_changed_out: Optional[set[int]] = None,
) -> set[int]:
    """Interpolate continuous physical device parameters at progress factor.

    Returns:
        Set of 1-based device/channel IDs whose state actually changed on this tick.
    """
    changed_devices: set[int] = set()
    if patch is None or not target_values:
        return changed_devices
    alpha = max(0.0, min(1.0, factor))
    scalar_map = {
        "pan": "pan",
        "tilt": "tilt",
        "zoom": "zoom",
        "focus": "focus",
        "strobe": "strobe",
        "cct": "cct",
        "color_temp": "cct",
        "colortemp": "cct",
        "iris": "iris",
    }
    norm_emitter_names = {ct.value for ct in COLOR_CHANNEL_TYPES}
    for dev_id, params in target_values.items():
        dev = patch.get_device(dev_id)
        if dev is None:
            continue
        before = _snapshot_dev_diff_state(dev)
        touched_color = False
        start = start_states.get(dev_id, {})
        start_norm = start.get("norm_params", {})
        lower_keys = {str(k).lower() for k in params}
        has_explicit_rgb = {"red", "green", "blue"}.issubset(lower_keys)
        has_explicit_cmy = {"cyan", "magenta", "yellow"}.issubset(lower_keys)
        ordered_params = [
            (k, v) for k, v in params.items() if str(k).lower() in ("color", "colour")
        ] + [
            (k, v)
            for k, v in params.items()
            if str(k).lower() not in ("color", "colour")
        ]
        for param_name, target_val in ordered_params:
            p_lower = param_name.lower()
            if p_lower in ("color", "colour") and (
                has_explicit_rgb or has_explicit_cmy
            ):
                continue
            if p_lower == "intensity":
                s_val = float(start.get("intensity", getattr(dev, "intensity", 0.0)))
                t_val = float(target_val)
                int_alpha = alpha
                if (
                    t_val < s_val
                    and intensity_out_factors is not None
                    and dev_id in intensity_out_factors
                ):
                    int_alpha = max(0.0, min(1.0, intensity_out_factors[dev_id]))
                dev.set_intensity(s_val + int_alpha * (t_val - s_val))
                continue

            family = get_parameter_family(param_name)
            param_alpha = (
                max(0.0, min(1.0, family_factors.get(family, alpha)))
                if family_factors is not None
                else alpha
            )
            is_explicit_family = (
                explicit_families is not None and family in explicit_families
            )
            if (
                not is_explicit_family
                and mib_factors is not None
                and dev_id in mib_factors
                and (
                    mib_parameters is None
                    or param_name in mib_parameters.get(dev_id, set())
                )
            ):
                param_alpha = max(0.0, min(1.0, mib_factors[dev_id]))

            if p_lower in _COLOR_PARAM_NAMES:
                touched_color = True

            if p_lower in scalar_map:
                s_key = scalar_map[p_lower]
                s_opt = start.get(s_key)
                if s_opt is not None:
                    interp = float(s_opt) + param_alpha * (
                        float(target_val) - float(s_opt)
                    )
                    dev.apply_device_parameter(p_lower, interp)
                else:
                    dev.apply_device_parameter(p_lower, float(target_val))
            elif p_lower in ("color", "colour"):
                target_rgb = _parse_rgb_norm(target_val)
                if target_rgb is not None and hasattr(dev, "set_color_srgb"):
                    r0, g0, b0 = start.get("color_rgb", (0.0, 0.0, 0.0))
                    dev.set_color_srgb(
                        r0 + param_alpha * (target_rgb[0] - r0),
                        g0 + param_alpha * (target_rgb[1] - g0),
                        b0 + param_alpha * (target_rgb[2] - b0),
                    )
                else:
                    dev.apply_device_parameter(p_lower, target_val)
            elif (
                p_lower in norm_emitter_names
                or (
                    isinstance(start_norm, dict)
                    and p_lower in start_norm
                    and _is_continuous_norm_param(dev, p_lower)
                )
            ) and isinstance(target_val, (int, float)):
                t_norm = float(target_val)
                if t_norm > 1.0:
                    t_norm /= 255.0
                t_norm = max(0.0, min(1.0, t_norm))
                s_opt = (
                    start_norm.get(p_lower) if isinstance(start_norm, dict) else None
                )
                if s_opt is not None:
                    interp_norm = float(s_opt) + param_alpha * (t_norm - float(s_opt))
                    dev.apply_device_parameter(p_lower, interp_norm)
                elif param_alpha > 0.0:
                    dev.apply_device_parameter(p_lower, t_norm)
            elif param_alpha > 0.0:
                dev.apply_device_parameter(p_lower, target_val)

        any_moved, col_moved = _has_device_changed(
            before, dev, touched_color_param=touched_color
        )
        if any_moved:
            changed_devices.add(dev_id)
            if col_moved and color_changed_out is not None:
                color_changed_out.add(dev_id)
    return changed_devices


def _apply_step_curve(
    lightshow: typing.Any,  # noqa: ANN401
    curve_id: int,
    factor: float,
) -> float:
    """Transform a linear fade progress *factor* in [0, 1] by *curve_id*."""
    clamped = max(0.0, min(1.0, float(factor)))
    if curve_id <= 0 or lightshow is None:
        return clamped
    curves = getattr(lightshow, "curves", None)
    if curves is None or not hasattr(curves, "get_curve"):
        return clamped
    curve = curves.get_curve(int(curve_id))
    if curve is None:
        return clamped
    try:
        return max(0.0, min(1.0, float(curve.evaluate_normalized(clamped))))
    except NotImplementedError:
        idx = max(0, min(255, round(clamped * 255.0)))
        return max(0.0, min(1.0, float(curve.values_array[idx]) / 255.0))


def _next_step(sequence: Sequence, target_step: int | None = None) -> int:
    """Next Step after Go

    Args:
        sequence: Main Playback
        target_step: Step index that just became active on stage.

    Returns:
        Upcoming step index
    """
    active_idx = target_step if target_step is not None else sequence.position + 1
    if active_idx < sequence.last - 1:
        sequence.position = active_idx
        next_step = sequence.resolve_next_step_index(active_idx, consume_loop=False)
    # If no next step, go to beginning
    else:
        sequence.position = 0
        next_step = 1

    # Main window's subtitle
    subtitle = (
        f"Cue : {get_cue(sequence.steps[sequence.position]).number} "
        f"{sequence.steps[sequence.position].text} - Next Cue : "
        f"{get_cue(sequence.steps[next_step]).number} "
        f"{sequence.steps[next_step].text}"
    )

    # Emit event for GUI (GuiEventBridge)
    if sequence.app is not None and is_main_sequence(sequence):
        sequence.app.emit(
            "playback.step_changed",
            {
                "position": sequence.position,
                "next_step": next_step,
                "subtitle": subtitle,
                "total_time": sequence.steps[next_step].total_time,
                "time_in": sequence.steps[next_step].time_in,
                "time_out": sequence.steps[next_step].time_out,
                "delay_in": sequence.steps[next_step].delay_in,
                "delay_out": sequence.steps[next_step].delay_out,
                "wait": sequence.steps[next_step].wait,
                "channel_time": sequence.steps[next_step].channel_time,
                "curve_id": int(getattr(sequence.steps[next_step], "curve_id", 0)),
            },
        )
    return next_step


# pylint: disable=too-many-instance-attributes
class ThreadGo(threading.Thread):
    """Thread object for Go"""

    sequence: Sequence
    old_channels_levels: np.ndarray
    old_device_states: dict[int, dict[str, typing.Any]]
    total_time: float
    time_in: float
    time_out: float
    wait: float
    delay_in: float
    delay_out: float
    goto: bool
    override_time: Optional[float]
    backend: typing.Any

    def __init__(
        self,
        goto: bool,
        sequence: Sequence,
        override_time: Optional[float] = None,
    ) -> None:
        threading.Thread.__init__(self, name="ThreadGo", daemon=True)
        self._stopevent = threading.Event()
        self.pause = threading.Event()
        self.pause.set()
        self.sequence = sequence
        self.override_time = override_time
        # To save channels levels when user sends Go
        self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        self.old_device_states = {}
        if goto:
            self.target_step = self.sequence.position + 1
        else:
            self.target_step = self.sequence.resolve_next_step_index(
                self.sequence.position, consume_loop=True
            )
        if not 0 <= self.target_step < len(self.sequence.steps):
            self.target_step = 1 if len(self.sequence.steps) > 1 else 0
        next_step = self.target_step
        if override_time is not None:
            self.total_time = override_time * 1000.0
            self.time_in = override_time * 1000.0
            self.time_out = override_time * 1000.0
            self.wait = 0.0
            self.delay_in = 0.0
            self.delay_out = 0.0
        else:
            self.total_time = self.sequence.steps[next_step].total_time * 1000
            self.time_in = self.sequence.steps[next_step].time_in * 1000
            self.time_out = self.sequence.steps[next_step].time_out * 1000
            self.wait = self.sequence.steps[next_step].wait * 1000
            self.delay_in = self.sequence.steps[next_step].delay_in * 1000
            self.delay_out = self.sequence.steps[next_step].delay_out * 1000
        self.goto = goto

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.sequence.app

    @property
    def backend(self) -> typing.Any:  # noqa: ANN401
        """Get parent application's DMX backend safely."""
        return self.sequence.backend

    def _was_device_lit(self, dev_id: int) -> bool:
        """Return True if dev_id had non-zero intensity when Go was triggered."""
        if (
            1 <= dev_id <= len(self.old_channels_levels)
            and int(self.old_channels_levels[dev_id - 1]) > 0
        ):
            return True
        old_int = float(self.old_device_states.get(dev_id, {}).get("intensity", 0.0))
        return old_int > 0.0

    def _get_device_dark_time_ms(self, step: Step, dev_id: int) -> float:
        """Return elapsed time (ms) when a fading-out device reaches 0% intensity."""
        if (
            self.override_time is None
            and step.channel_time
            and dev_id in step.channel_time
        ):
            ct = step.channel_time[dev_id]
            return self.wait + (ct.delay + ct.time) * 1000.0
        return self.wait + self.delay_out + self.time_out

    def _capture_start_levels(self) -> None:
        """Capture sequential channels levels and device states when Go is sent"""
        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        arb_state = arb.get_state(self.sequence.index) if arb is not None else None
        if arb_state is not None and arb_state.active:
            self.old_channels_levels = arb_state.intensities.copy()
        elif (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and hasattr(self.backend.dmx, "levels")
            and "sequence" in self.backend.dmx.levels
        ):
            self.old_channels_levels = self.backend.dmx.levels["sequence"].copy()
            user_levels = self.backend.dmx.levels.get("user")
            if user_levels is not None:
                user_mask = user_levels >= 0.0
                self.old_channels_levels[user_mask] = user_levels[user_mask]
        else:
            self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        self.old_device_states = _capture_device_states(self.sequence.patch)

        next_step_idx = self.target_step
        if 0 <= next_step_idx < len(self.sequence.steps):
            step = self.sequence.steps[next_step_idx]
            resolved = TrackingEngine.resolve_step_state(
                self.sequence,
                next_step_idx,
                tracking_mode=self.sequence.tracking_mode,
                patch=self.sequence.patch,
            )
            mib_dur_ms = max(
                0.0,
                float(getattr(self.sequence, "mib_fade_time", DEFAULT_MIB_FADE_TIME))
                * 1000.0,
            )
            for dev_id, mib_params in resolved.mib_parameters.items():
                has_non_explicit_mib = any(
                    not step.has_explicit_family_timing(get_parameter_family(p))
                    for p in mib_params
                )
                if has_non_explicit_mib and self._was_device_lit(dev_id):
                    t_dark_ms = self._get_device_dark_time_ms(step, dev_id)
                    self.total_time = max(self.total_time, t_dark_ms + mib_dur_ms)

            fade_s = (
                self.override_time
                if self.override_time is not None
                else float(step.time_in)
            )
            _sync_resolved_effects(
                self.app,
                resolved,
                fade_time=max(0.0, fade_s),
                clear_live_state=True,
            )

    def _sync_dmx_levels(self) -> None:
        """Push final levels to DMX while preserving user overrides."""
        if (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and self.backend.dmx is not None
        ):
            self.backend.dmx.set_levels()

    def _finalize_go(self) -> None:
        """Finish load cue after sequence transition"""
        target_step_idx = (
            self.target_step if 0 <= self.target_step < self.sequence.last else 0
        )

        # Resolve full sequential state via TrackingEngine
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            target_step_idx,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )

        target_cue = (
            self.sequence.steps[target_step_idx].cue
            if 0 <= target_step_idx < len(self.sequence.steps)
            else None
        )
        is_assert = bool(getattr(target_cue, "is_assert", False))
        cue_num = getattr(target_cue, "number", None)

        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if arb is not None:
            composed = arb.set_sequence_output(
                self.sequence.index,
                resolved.channels,
                resolved.device_values,
                priority=getattr(self.sequence, "priority", 20),
                htp_intensity=getattr(self.sequence, "htp_intensity", True),
                cue_number=cue_num,
                off_on_overwritten=getattr(self.sequence, "off_on_overwritten", False),
                assert_all=is_assert,
            )
            apply_arbitrated_output(
                self.app,
                self.backend,
                self.sequence.patch,
                composed,
                force_assert=is_assert,
            )
        else:
            # Block-copy levels to sequential dmx levels
            if (
                self.backend
                and hasattr(self.backend, "dmx")
                and hasattr(self.backend.dmx, "levels")
                and "sequence" in self.backend.dmx.levels
            ):
                n_ch = min(
                    len(self.backend.dmx.levels["sequence"]), len(resolved.channels)
                )
                self.backend.dmx.levels["sequence"][:n_ch] = resolved.channels[:n_ch]

            # Apply multi-parameter device values and emit differential events
            if self.sequence.patch is not None:
                _apply_resolved_device_values(
                    self.sequence.patch,
                    resolved,
                    self.app,
                    force_assert=is_assert,
                )

        _sync_resolved_effects(self.app, resolved, fade_time=0.0, clear_live_state=True)
        _apply_execute_preset(self.sequence, self.backend, self.app, target_cue)

        self.sequence.on_go = False
        is_main = is_main_sequence(self.sequence)
        if is_main and self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(0)
            self.app.crossfade.scale_b.set_value(0)

        if arb is None:
            self._sync_dmx_levels()

        self.sequence.update_channels()
        next_step = _next_step(self.sequence, target_step=target_step_idx)

        _notify_runner(self.sequence, "active", fade_progress=0.0, fade_remaining=0.0)

        # Emit event for GUI (GuiEventBridge)
        if is_main and self.app is not None:
            self.app.emit(
                "playback.transition_completed",
                {
                    "next_step": next_step,
                },
            )

        if self.sequence.steps[next_step].wait:
            self.sequence.do_go(None)

    def run(self) -> None:
        self._capture_start_levels()
        start_pause = None
        pause_time = 0.0
        start_time = time.time() * 1000
        i = (time.time() * 1000) - start_time
        while i < self.total_time and not self._stopevent.is_set():
            if not self.pause.is_set():
                if not start_pause:
                    start_pause = time.time() * 1000
                self.pause.wait()
                pause_time += (time.time() * 1000) - start_pause
            else:
                start_pause = None
                i = (time.time() * 1000) - (start_time + pause_time)
                self.update_levels(i)
                self._stopevent.wait(0.05)

        if self._stopevent.is_set():
            return

        self._finalize_go()

    def stop(self) -> None:
        """Stop"""
        self._stopevent.set()
        self.pause.set()

    def update_levels(self, i: float) -> None:
        """Update levels

        Args:
            i: Time spent
        """
        val = round((255 / self.total_time) * i)
        is_main = is_main_sequence(self.sequence)
        if is_main and self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(val)
            self.app.crossfade.scale_b.set_value(val)

        progress = (
            max(0.0, min(1.0, i / self.total_time)) if self.total_time > 0 else 1.0
        )
        remaining = max(0.0, (self.total_time - i) / 1000.0)
        _notify_runner(
            self.sequence, "fading", fade_progress=progress, fade_remaining=remaining
        )

        # Emit event for GUI (GuiEventBridge)
        if is_main and self.app is not None:
            self.app.emit(
                "playback.transition_progress",
                {
                    "time_spent": i,
                    "total_time": self.total_time,
                    "progress_val": val,
                    "sequence_position": self.sequence.position,
                },
            )

        # Wait for wait time
        if i > self.wait:
            if self.goto:
                self._do_goto(i)
            else:
                self._do_go(i)

    def _do_goto(self, i: float) -> None:
        """Goto

        Args:
            i: Time spent
        """
        self._do_go(i)

    def _do_go(self, i: float) -> None:
        """Go

        Args:
            i: Time spent
        """
        step = self.sequence.steps[self.target_step]

        lvls = self._calculate_transitions_go(i, step)
        self._apply_channel_times_go(lvls, i, step)

        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and hasattr(self.backend.dmx, "levels")
            and "sequence" in self.backend.dmx.levels
        ):
            if arb is not None:
                composed = arb.set_sequence_output(
                    self.sequence.index,
                    np.clip(lvls, 0.0, 1.0),
                    priority=getattr(self.sequence, "priority", 20),
                    htp_intensity=getattr(self.sequence, "htp_intensity", True),
                    off_on_overwritten=getattr(
                        self.sequence, "off_on_overwritten", False
                    ),
                )
                n_ch = min(
                    len(self.backend.dmx.levels["sequence"]),
                    len(composed.intensities),
                )
                self.backend.dmx.levels["sequence"][:n_ch] = composed.intensities[:n_ch]
            else:
                self.backend.dmx.levels["sequence"][:] = np.clip(lvls, 0.0, 1.0)
            self.backend.dmx.set_levels()

    def _compute_device_factors_go(  # pylint: disable=too-many-locals, too-many-branches
        self,
        i: float,
        step: Step,
        resolved: typing.Any,  # noqa: ANN401
    ) -> tuple[
        float,
        dict[int, float],
        dict[int, float],
        dict[str, float],
        set[str],
    ]:
        """Compute LTP, MIB, intensity-out, and IFCB family factors at elapsed ms i."""

        def _window_factor(delay_s: float, time_s: float) -> float:
            start_ms = self.wait + delay_s * 1000.0
            dur_ms = time_s * 1000.0
            if dur_ms <= 0:
                return 1.0 if i >= start_ms else 0.0
            return max(0.0, min(1.0, (i - start_ms) / dur_ms))

        if self.override_time is not None:
            ltp_factor = _window_factor(0.0, self.override_time)
            default_out_factor = ltp_factor
            family_factors: dict[str, float] = {
                "position": ltp_factor,
                "color": ltp_factor,
                "beam": ltp_factor,
            }
            explicit_families: set[str] = set()
        else:
            curve_id = int(getattr(step, "curve_id", 0))
            lightshow = getattr(self.sequence, "lightshow", None)
            ltp_factor = _apply_step_curve(
                lightshow, curve_id, _window_factor(step.delay_in, step.time_in)
            )
            default_out_factor = _apply_step_curve(
                lightshow, curve_id, _window_factor(step.delay_out, step.time_out)
            )
            family_factors = {
                "position": _apply_step_curve(
                    lightshow,
                    curve_id,
                    _window_factor(
                        step.effective_delay_position, step.effective_time_position
                    ),
                ),
                "color": _apply_step_curve(
                    lightshow,
                    curve_id,
                    _window_factor(
                        step.effective_delay_color, step.effective_time_color
                    ),
                ),
                "beam": _apply_step_curve(
                    lightshow,
                    curve_id,
                    _window_factor(step.effective_delay_beam, step.effective_time_beam),
                ),
            }
            explicit_families = {
                fam
                for fam in ("position", "color", "beam")
                if step.has_explicit_family_timing(fam)
            }

        mib_factors: dict[int, float] = {}
        intensity_out_factors: dict[int, float] = {}
        mib_dur_ms = max(
            0.0,
            float(getattr(self.sequence, "mib_fade_time", DEFAULT_MIB_FADE_TIME))
            * 1000.0,
        )

        for dev_id, mib_params in resolved.mib_parameters.items():
            has_non_explicit = any(
                not step.has_explicit_family_timing(get_parameter_family(p))
                for p in mib_params
            )
            if not has_non_explicit:
                continue
            if self._was_device_lit(dev_id):
                t_dark_ms = self._get_device_dark_time_ms(step, dev_id)
                if i < t_dark_ms:
                    factor = 0.0
                elif mib_dur_ms <= 0:
                    factor = 1.0
                else:
                    factor = max(0.0, min(1.0, (i - t_dark_ms) / mib_dur_ms))
            else:
                factor = ltp_factor
            mib_factors[dev_id] = factor

        for dev_id in getattr(self.sequence.patch, "devices", {}):
            if (
                self.override_time is None
                and step.channel_time
                and dev_id in step.channel_time
            ):
                ct = step.channel_time[dev_id]
                intensity_out_factors[dev_id] = _window_factor(ct.delay, ct.time)
            else:
                intensity_out_factors[dev_id] = default_out_factor

        return (
            ltp_factor,
            mib_factors,
            intensity_out_factors,
            family_factors,
            explicit_families,
        )

    def _calculate_transitions_go(  # pylint: disable=too-many-locals
        self,
        i: float,
        step: Step,
    ) -> np.ndarray:
        """Calculate channels levels transitions for Go"""
        old_levels = self.old_channels_levels.astype(np.float64)
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            self.target_step,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )
        next_levels = resolved.channels.astype(np.float64)

        if self.override_time is not None:
            time_in = self.override_time * 1000.0
            time_out = self.override_time * 1000.0
            delay_in = 0.0
            delay_out = 0.0
        else:
            time_in = step.time_in * 1000
            time_out = step.time_out * 1000
            delay_in = step.delay_in * 1000
            delay_out = step.delay_out * 1000

        # Precompute progression factors
        curve_id = int(getattr(step, "curve_id", 0))
        lightshow = getattr(self.sequence, "lightshow", None)
        factor_in = _apply_step_curve(
            lightshow,
            curve_id,
            max(0.0, min(1.0, (i - delay_in - self.wait) / time_in))
            if time_in > 0
            else (1.0 if (i - delay_in - self.wait) >= 0 else 0.0),
        )
        factor_out = _apply_step_curve(
            lightshow,
            curve_id,
            max(0.0, min(1.0, (i - delay_out - self.wait) / time_out))
            if time_out > 0
            else (1.0 if (i - delay_out - self.wait) >= 0 else 0.0),
        )

        # Vectorized calculation for In, Out and Stationary channels
        diff = next_levels - old_levels
        factors = np.where(diff > 0, factor_in, factor_out)
        lvls = old_levels + diff * factors

        # Interpolate multi-parameter device values
        target_device_values = _build_fade_target_device_values(
            resolved, self.old_device_states
        )
        if target_device_values and self.sequence.patch is not None:
            (
                ltp_factor,
                mib_factors,
                intensity_out_factors,
                family_factors,
                explicit_families,
            ) = self._compute_device_factors_go(i, step, resolved)
            color_changed: set[int] = set()
            changed = _interpolate_device_states(
                self.sequence.patch,
                self.old_device_states,
                target_device_values,
                ltp_factor,
                mib_factors=mib_factors,
                mib_parameters=resolved.mib_parameters,
                intensity_out_factors=intensity_out_factors,
                family_factors=family_factors,
                explicit_families=explicit_families,
                color_changed_out=color_changed,
            )
            _emit_device_changes(self.app, changed, color_changed)

        return lvls

    def _apply_channel_times_go(self, lvls: np.ndarray, i: float, step: Step) -> None:
        """Apply individual channel times."""
        if not step.channel_time or self.override_time is not None:
            return
        old_levels = self.old_channels_levels.astype(np.float64)
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            self.target_step,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )
        next_levels = resolved.channels.astype(np.float64)
        for channel, ct in step.channel_time.items():
            o_lvl = old_levels[channel - 1]
            n_lvl = next_levels[channel - 1]
            if n_lvl < o_lvl:  # Decay
                if i < ct.delay * 1000 + self.wait:
                    lvl = o_lvl
                elif i < (ct.delay + ct.time) * 1000 + self.wait:
                    factor = (i - ct.delay * 1000 - self.wait) / (ct.time * 1000)
                    lvl = o_lvl - abs((n_lvl - o_lvl) * factor)
                else:
                    lvl = n_lvl
                lvls[channel - 1] = lvl
            elif n_lvl > o_lvl:  # Attack
                if i < ct.delay * 1000 + self.wait:
                    lvl = o_lvl
                elif i < (ct.delay + ct.time) * 1000 + self.wait:
                    factor = (i - ct.delay * 1000 - self.wait) / (ct.time * 1000)
                    lvl = (n_lvl - o_lvl) * factor + o_lvl
                else:
                    lvl = n_lvl
                lvls[channel - 1] = lvl


class ThreadGoBack(threading.Thread):
    """Thread Object for Go Back"""

    sequence: Sequence
    old_channels_levels: np.ndarray
    old_device_states: dict[int, dict[str, typing.Any]]
    backend: typing.Any

    def __init__(self, sequence: Sequence) -> None:
        threading.Thread.__init__(self, name="ThreadGoBack", daemon=True)
        self._stopevent = threading.Event()
        self.pause = threading.Event()
        self.pause.set()
        self.sequence = sequence
        # To save channels levels when Go Back starts
        self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        self.old_device_states = {}

    @property
    def app(self) -> CoreApplication | None:
        """Get parent application instance safely."""
        return self.sequence.app

    @property
    def backend(self) -> typing.Any:  # noqa: ANN401
        """Get parent application's DMX backend safely."""
        return self.sequence.backend

    def _capture_start_levels(self) -> None:
        """Capture sequential channels levels and device states when Go Back starts"""
        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        arb_state = arb.get_state(self.sequence.index) if arb is not None else None
        if arb_state is not None and arb_state.active:
            self.old_channels_levels = arb_state.intensities.copy()
        elif (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and hasattr(self.backend.dmx, "levels")
            and "sequence" in self.backend.dmx.levels
        ):
            self.old_channels_levels = self.backend.dmx.levels["sequence"].copy()
            user_levels = self.backend.dmx.levels.get("user")
            if user_levels is not None:
                user_mask = user_levels >= 0.0
                self.old_channels_levels[user_mask] = user_levels[user_mask]
        else:
            self.old_channels_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        self.old_device_states = _capture_device_states(self.sequence.patch)

    def _sync_dmx_levels(self) -> None:
        """Push final levels to DMX while preserving user overrides."""
        if (
            self.backend is not None
            and hasattr(self.backend, "dmx")
            and self.backend.dmx is not None
        ):
            self.backend.dmx.set_levels()

    def _finalize_goback(self, prev_step: int) -> None:
        """Finish load cue after sequence transition"""
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            prev_step,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )

        prev_cue = (
            self.sequence.steps[prev_step].cue
            if 0 <= prev_step < len(self.sequence.steps)
            else None
        )
        is_assert = bool(getattr(prev_cue, "is_assert", False))
        cue_num = getattr(prev_cue, "number", None)

        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if arb is not None:
            composed = arb.set_sequence_output(
                self.sequence.index,
                resolved.channels,
                resolved.device_values,
                priority=getattr(self.sequence, "priority", 20),
                htp_intensity=getattr(self.sequence, "htp_intensity", True),
                cue_number=cue_num,
                off_on_overwritten=getattr(self.sequence, "off_on_overwritten", False),
                assert_all=is_assert,
            )
            apply_arbitrated_output(
                self.app,
                self.backend,
                self.sequence.patch,
                composed,
                force_assert=is_assert,
            )
        else:
            # Block-copy levels to sequential dmx levels
            if (
                self.backend
                and hasattr(self.backend, "dmx")
                and hasattr(self.backend.dmx, "levels")
                and "sequence" in self.backend.dmx.levels
            ):
                n_ch = min(
                    len(self.backend.dmx.levels["sequence"]), len(resolved.channels)
                )
                self.backend.dmx.levels["sequence"][:n_ch] = resolved.channels[:n_ch]

            # Apply multi-parameter device values and emit differential events
            if self.sequence.patch is not None:
                _apply_resolved_device_values(
                    self.sequence.patch,
                    resolved,
                    self.app,
                    force_assert=is_assert,
                )
        _sync_resolved_effects(self.app, resolved, fade_time=0.0, clear_live_state=True)

        self.sequence.on_go = False
        is_main = is_main_sequence(self.sequence)
        if is_main and self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(0)
            self.app.crossfade.scale_b.set_value(0)
        self._sync_dmx_levels()

        self.sequence.update_channels()
        self.sequence.position = prev_step

        _notify_runner(self.sequence, "active", fade_progress=0.0, fade_remaining=0.0)

        subtitle = (
            f"Cue : {get_cue(self.sequence.steps[prev_step]).number} "
            f"{self.sequence.steps[prev_step].text} - Next Cue : "
            f"{get_cue(self.sequence.steps[prev_step + 1]).number} "
            f"{self.sequence.steps[prev_step + 1].text}"
        )

        # Emit event for GUI (GuiEventBridge)
        if is_main and self.app is not None:
            self.app.emit(
                "playback.goback_completed",
                {
                    "prev_step": prev_step,
                    "subtitle": subtitle,
                    "time_in": self.sequence.steps[prev_step + 1].time_in,
                    "time_out": self.sequence.steps[prev_step + 1].time_out,
                    "delay_in": self.sequence.steps[prev_step + 1].delay_in,
                    "delay_out": self.sequence.steps[prev_step + 1].delay_out,
                    "wait": self.sequence.steps[prev_step + 1].wait,
                    "total_time": self.sequence.steps[prev_step + 1].total_time,
                    "channel_time": self.sequence.steps[prev_step + 1].channel_time,
                    "curve_id": int(
                        getattr(self.sequence.steps[prev_step + 1], "curve_id", 0)
                    ),
                },
            )

    def run(self) -> None:
        if self.sequence.last == 2:
            return

        prev_step = self.sequence.position - 1
        self._capture_start_levels()

        go_back_time = 0.0
        if self.app is not None:
            go_back_time = (
                typing.cast(typing.Any, self.app.settings).get_double("go-back-time")
                * 1000
            )
        if 0 <= prev_step < len(self.sequence.steps):
            prev_resolved = TrackingEngine.resolve_step_state(
                self.sequence,
                prev_step,
                tracking_mode=self.sequence.tracking_mode,
                patch=self.sequence.patch,
            )
            _sync_resolved_effects(
                self.app,
                prev_resolved,
                fade_time=max(0.0, go_back_time / 1000.0),
                clear_live_state=True,
            )
        pause_time = 0.0
        start_time = time.time() * 1000
        i = (time.time() * 1000) - start_time
        start_pause = None
        while i < go_back_time and not self._stopevent.is_set():
            if not self.pause.is_set():
                if not start_pause:
                    start_pause = time.time() * 1000
                self.pause.wait()
                pause_time += (time.time() * 1000) - start_pause
            else:
                start_pause = None
                self.update_levels(go_back_time, i, self.sequence.position)
                self._stopevent.wait(0.05)
                i = (time.time() * 1000) - (start_time + pause_time)

        if self._stopevent.is_set():
            return

        self._finalize_goback(prev_step)

    def stop(self) -> None:
        """Stop"""
        self._stopevent.set()
        self.pause.set()

    def update_levels(self, go_back_time: float, i: float, position: int) -> None:
        """Update levels

        Args:
            go_back_time: Default GoBack time
            i: Time spent
            position: Step
        """
        val = round((255 / go_back_time) * i)
        is_main = is_main_sequence(self.sequence)
        if is_main and self.app is not None and self.app.crossfade is not None:
            self.app.crossfade.scale_a.set_value(val)
            self.app.crossfade.scale_b.set_value(val)

        progress = max(0.0, min(1.0, i / go_back_time)) if go_back_time > 0 else 1.0
        remaining = max(0.0, (go_back_time - i) / 1000.0)
        _notify_runner(
            self.sequence, "fading", fade_progress=progress, fade_remaining=remaining
        )

        # Emit event for GUI (GuiEventBridge)
        if is_main and self.app is not None:
            self.app.emit(
                "playback.goback_progress",
                {
                    "time_spent": i,
                    "goback_time": go_back_time,
                    "position": position,
                    "progress_val": val,
                },
            )

        # Resolve previous step state via TrackingEngine
        resolved = TrackingEngine.resolve_step_state(
            self.sequence,
            position - 1,
            tracking_mode=self.sequence.tracking_mode,
            patch=self.sequence.patch,
        )
        old_levels = self.old_channels_levels.astype(np.float64)
        next_levels = resolved.channels.astype(np.float64)
        raw_factor = i / go_back_time if go_back_time > 0 else 1.0
        cur_step = (
            self.sequence.steps[position]
            if 0 <= position < len(self.sequence.steps)
            else None
        )
        factor = _apply_step_curve(
            getattr(self.sequence, "lightshow", None),
            int(getattr(cur_step, "curve_id", 0)) if cur_step is not None else 0,
            raw_factor,
        )
        diff = (next_levels - old_levels) * factor
        lvls = old_levels + diff

        target_device_values = _build_fade_target_device_values(
            resolved, self.old_device_states
        )
        if target_device_values and self.sequence.patch is not None:
            color_changed: set[int] = set()
            changed = _interpolate_device_states(
                self.sequence.patch,
                self.old_device_states,
                target_device_values,
                factor,
                color_changed_out=color_changed,
            )
            _emit_device_changes(self.app, changed, color_changed)

        arb = getattr(self.app, "playback_arbitrator", None) if self.app else None
        if arb is not None:
            composed = arb.set_sequence_output(
                self.sequence.index,
                np.clip(lvls, 0.0, 1.0),
                priority=getattr(self.sequence, "priority", 20),
                htp_intensity=getattr(self.sequence, "htp_intensity", True),
                off_on_overwritten=getattr(self.sequence, "off_on_overwritten", False),
            )
            n_ch = min(
                len(self.backend.dmx.levels["sequence"]), len(composed.intensities)
            )
            self.backend.dmx.levels["sequence"][:n_ch] = composed.intensities[:n_ch]
        else:
            self.backend.dmx.levels["sequence"][:] = np.clip(lvls, 0.0, 1.0)
        self.backend.dmx.set_levels()
