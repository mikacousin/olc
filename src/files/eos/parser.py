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
"""Native ETC Eos (``.esf3d`` / ``.esf2``) showfile parser."""

from __future__ import annotations

import logging
import pathlib
import zipfile
from typing import TYPE_CHECKING, Any

from olc.define import MAX_FADER_PER_PAGE, NB_UNIVERSES, UNIVERSES
from olc.devices.channel import ChannelType
from olc.devices.color_pick.gels import lookup_gel, resolve_gel_hex
from olc.devices.device import compute_focus_point_from_orientation
from olc.files.ascii.eos_devices import (
    _PHYSICAL_PARAM_NAMES,
    EOS_GENERIC_PARAM_NAMES,
    EOS_PARAM_TO_CHANNEL_TYPE,
)
from olc.files.ascii.eos_effects import (
    EOS_TYPE_ABSOLUTE,
    EOS_TYPE_COLOR,
    EOS_TYPE_FOCUS,
    EOS_TYPE_LINEAR,
    EOS_TYPE_STEPBASED,
    convert_eos_effect,
    eos_envelope_mode,
    new_eos_effect,
)
from olc.files.eos.a3d import (
    eos_euler_to_olc,
    parse_working_a3d_patch,
    parse_working_a3d_scenery,
)
from olc.files.eos.gdtf_enrich import (
    enrich_fixture_from_gdtf,
    match_eos_fixture_definition,
    should_use_gdtf_for_personality,
)
from olc.files.eos.personality import (
    EosPersonality,
    build_olc_fixture_definition,
    evaluate_eos_param_to_dmx,
    parse_param_categories,
    parse_param_types,
    parse_personalities,
)
from olc.files.eos.wire import decode_showdat
from olc.show.fader import FaderType
from olc.show.palette import PaletteCategory

if TYPE_CHECKING:
    from olc.files.import_file import ImportFile

LOGGER = logging.getLogger(__name__)


def _resolve_file_path(file_obj: object) -> pathlib.Path:
    """Resolve ``pathlib.Path``, ``str``, or Gio ``GFile`` to a local Path."""
    if isinstance(file_obj, pathlib.Path):
        return file_obj
    if isinstance(file_obj, str):
        return pathlib.Path(file_obj)
    get_path = getattr(file_obj, "get_path", None)
    if callable(get_path):
        resolved = get_path()
        if resolved:
            return pathlib.Path(str(resolved))
    return pathlib.Path(str(file_obj))


def _iter_eos_channel_blocks(container: list[Any]) -> list[tuple[list[int], list[Any]]]:
    """Iterate ``(channels, ch_params_obj)`` blocks in ``cue[22]`` or ``palette[6]``.

    Eos compresses channels that share identical values using a trailing
    ``clone_count`` followed by ``clone_count`` additional channel numbers:
    ``ch, 0, ch_obj, clone_count, [clone_ch_1, ...]``.
    """
    blocks: list[tuple[list[int], list[Any]]] = []
    if not isinstance(container, list) or len(container) < 6:
        return blocks
    k = 3
    n = len(container)
    while k + 3 < n:
        ch = container[k]
        ch_obj = container[k + 2]
        if not isinstance(ch, int) or not isinstance(ch_obj, list):
            break
        clone_cnt = container[k + 3] if isinstance(container[k + 3], int) else 0
        clones = [
            c
            for c in container[k + 4 : k + 4 + clone_cnt]
            if isinstance(c, int) and c > 0
        ]
        blocks.append(([ch, *clones], ch_obj))
        k += 4 + clone_cnt
    return blocks


_REF_CAT_TO_NAME: dict[int, str] = {
    1: PaletteCategory.INTENSITY.value,
    2: PaletteCategory.FOCUS.value,
    3: PaletteCategory.COLOR.value,
    4: PaletteCategory.BEAM.value,
}


_REF_CAT_TO_PREFIX: dict[int, str] = {
    1: "IP",
    2: "FP",
    3: "CP",
    4: "BP",
}


def _extract_effect_step_token(st: list[Any]) -> str:
    """Extract palette/preset token or numeric level from an Eos effect step."""
    ref_kind = st[7] if len(st) > 7 and isinstance(st[7], int) else 0
    ref_obj = st[16] if len(st) > 16 and isinstance(st[16], list) else None
    if (
        ref_obj is not None
        and len(ref_obj) >= 4
        and isinstance(ref_obj[2], int)
        and ref_obj[2] > 0
    ):
        num = ref_obj[2] / 10000.0
        if ref_kind == 4:
            return f"PR {num:g}"
        if ref_kind == 3:
            cat_id = ref_obj[3]
            prefix = _REF_CAT_TO_PREFIX.get(cat_id) if isinstance(cat_id, int) else None
            if prefix is not None:
                return f"{prefix} {num:g}"
    val = st[3] if len(st) > 3 and isinstance(st[3], (int, float)) else 0.0
    return str(val)


def _extract_palette_ref(v_node: list[Any]) -> tuple[str, float] | None:
    """Extract ``(category_str, number)`` from an Eos ``v_node`` if referenced."""
    if len(v_node) <= 7:
        return None
    ref_kind = v_node[4]
    ref_obj = v_node[7]
    if not isinstance(ref_obj, list) or len(ref_obj) < 4:
        return None
    raw_num = ref_obj[2]
    if not isinstance(raw_num, int):
        return None
    num = raw_num / 10000.0
    if ref_kind == 4:
        return PaletteCategory.PRESET.value, num
    if ref_kind == 3:
        cat_id = ref_obj[3]
        cat_str = _REF_CAT_TO_NAME.get(cat_id) if isinstance(cat_id, int) else None
        if cat_str is not None:
            return cat_str, num
    return None


def _parse_eos_channel_params(
    ch_params_obj: list[Any],
    channel_num: int,
    refs_out: dict[int, tuple[str, float]] | None = None,
    part_out: list[int] | None = None,
) -> dict[int, float]:
    """Parse Eos cue/palette mixed complex+flat parameter list for a channel.

    In ``showdat.dat``, each channel parameter block uses:
      ``["OBJ", 0, <total>, <pid>, ["OBJ", ...], <flat_cnt>, <pid, val>..., ...]``
    followed by a trailing footer ``["OBJ", 1, <channel_num>, ...]``.
    """
    raw: dict[int, float] = {}
    if not isinstance(ch_params_obj, list) or len(ch_params_obj) < 4:
        return raw

    i = 3
    n = len(ch_params_obj)
    while i < n:
        tok = ch_params_obj[i]
        # Stop at trailing channel footer
        if isinstance(tok, list) and len(tok) >= 3 and tok[0] == "OBJ" and tok[1] == 1:
            break
        if (
            isinstance(tok, int)
            and i + 1 < n
            and isinstance(ch_params_obj[i + 1], list)
        ):
            pid = tok
            val_obj = ch_params_obj[i + 1]
            cur_ref: tuple[str, float] | None = None
            # Complex entry: cue uses val_obj[2][10], palette uses val_obj[2][2]
            v_node: list[Any] | None = None
            if len(val_obj) >= 3 and isinstance(val_obj[2], list):
                v2 = val_obj[2]
                if (
                    part_out is not None
                    and len(v2) > 4
                    and isinstance(v2[4], int)
                    and v2[4] > 1
                ):
                    part_out.append(v2[4])
                if len(v2) > 10 and isinstance(v2[10], list):
                    v_node = v2[10]
                elif len(v2) >= 3 and isinstance(v2[2], list):
                    v_node = v2[2]
            if (
                v_node is not None
                and len(v_node) >= 3
                and isinstance(v_node[2], (int, float))
            ):
                raw[pid] = float(v_node[2])
                cur_ref = _extract_palette_ref(v_node)
                if cur_ref is not None and refs_out is not None:
                    refs_out[pid] = cur_ref
            i += 2
            # Followed by flat_count and flat_count (pid, value) pairs
            if i < n and isinstance(ch_params_obj[i], int):
                flat_cnt = ch_params_obj[i]
                i += 1
                for _ in range(flat_cnt):
                    if i + 1 < n and isinstance(ch_params_obj[i], int):
                        f_pid = ch_params_obj[i]
                        f_val = ch_params_obj[i + 1]
                        if isinstance(f_val, (int, float)):
                            raw[f_pid] = float(f_val)
                            if cur_ref is not None and refs_out is not None:
                                refs_out[f_pid] = cur_ref
                        i += 2
                    else:
                        break
        else:
            i += 1

    _ = channel_num
    return raw


def _decode_channel_values(
    raw_params: dict[int, float],
    personality: EosPersonality | None,
    param_names: dict[int, str],
    *,
    virtual_context: dict[int, float] | None = None,
) -> tuple[dict[str, Any], float | None]:
    """Convert raw Eos user parameter values into OLC ``device_values`` & intensity."""
    dev_vals: dict[str, Any] = {}
    intensity_val: float | None = None
    rgb: dict[str, float] = {}
    cmy: dict[str, float] = {}
    eval_ctx = dict(virtual_context) if virtual_context else {}
    eval_ctx.update(raw_params)

    for pid, user_val in raw_params.items():
        pname = param_names.get(pid, "").lower()
        pdef = personality.params.get(pid) if personality is not None else None

        if pid == 1 or pname == "intens":
            norm = max(0.0, min(1.0, user_val / 100.0))
            intensity_val = norm
            if personality is not None and not personality.is_dimmer:
                dev_vals["intensity"] = norm
            continue

        if pdef is not None and pdef.is_virtual:
            # Virtual mode parameter (e.g. Gobo_Mode 279) is used as context,
            # not emitted as a DMX channel value.
            continue

        if pdef is not None:
            dmx = evaluate_eos_param_to_dmx(pdef, user_val, eval_ctx, personality)
            if dmx is None:
                continue
            norm = max(0.0, min(1.0, dmx / float(pdef.max_dmx)))
        else:
            # Fallback if personality is missing
            norm = max(0.0, min(1.0, user_val / 100.0))

        if pname in _PHYSICAL_PARAM_NAMES:
            olcname = _PHYSICAL_PARAM_NAMES[pname]
            if pname in ("color_temperature", "cto") and user_val > 100.0:
                dev_vals[olcname] = float(user_val)
            else:
                if pdef is not None:
                    phys_min, phys_max, _ = pdef.physical_bounds()
                else:
                    phys_min, phys_max = 0.0, 1.0
                dev_vals[olcname] = phys_min + norm * (phys_max - phys_min)
        elif pname in ("red", "green", "blue"):
            rgb[pname] = norm
        elif pname in ("cyan", "magenta", "yellow"):
            cmy[pname] = norm
        else:
            ctype = EOS_PARAM_TO_CHANNEL_TYPE.get(pname, ChannelType.GENERIC)
            if ctype is not ChannelType.GENERIC:
                key = ctype.value
                existing = dev_vals.get(key)
                if not isinstance(existing, (int, float)) or norm > float(existing):
                    dev_vals[key] = norm
            elif pname and (pdef is not None or pname in EOS_GENERIC_PARAM_NAMES):
                dev_vals[pname] = norm

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
        for comp in ("cyan", "magenta", "yellow"):
            dev_vals[comp] = cmy.get(comp, 0.0)

    return dev_vals, intensity_val


def _parse_cue_effect_raw(
    cue23: object, cue26: object
) -> tuple[
    dict[float, list[int]],
    set[int],
    dict[float, tuple[float | None, float | None]],
]:
    """Extract ``(started, stopped, scales)`` from ``cue[23]`` and ``cue[26]``."""
    scales: dict[float, tuple[float | None, float | None]] = {}
    if isinstance(cue26, list) and len(cue26) >= 5:
        k = 3
        while k + 1 < len(cue26):
            raw_eff = cue26[k]
            meta = cue26[k + 1]
            if (
                isinstance(raw_eff, int)
                and raw_eff > 0
                and isinstance(meta, list)
                and len(meta) >= 4
            ):
                size_scale = (
                    float(meta[2]) / 100.0
                    if isinstance(meta[2], (int, float))
                    else None
                )
                rate_scale = (
                    float(meta[3]) / 100.0
                    if isinstance(meta[3], (int, float))
                    else None
                )
                scales[raw_eff / 10000.0] = (size_scale, rate_scale)
            k += 2

    started: dict[float, list[int]] = {}
    stopped: set[int] = set()
    if isinstance(cue23, list):
        for channels, ch_obj in _iter_eos_channel_blocks(cue23):
            i = 3
            while i + 1 < len(ch_obj):
                tok = ch_obj[i]
                if isinstance(tok, list) and tok[0] == "OBJ" and tok[1] == 1:
                    break
                val_obj = ch_obj[i + 1]
                if (
                    isinstance(tok, int)
                    and isinstance(val_obj, list)
                    and len(val_obj) >= 3
                    and isinstance(val_obj[2], list)
                    and len(val_obj[2]) >= 3
                    and isinstance(val_obj[2][2], int)
                ):
                    raw_eff_val = val_obj[2][2]
                    if raw_eff_val == 0:
                        stopped.update(channels)
                    elif raw_eff_val > 0:
                        eff_num = raw_eff_val / 10000.0
                        lst = started.setdefault(eff_num, [])
                        for ch in channels:
                            if ch not in lst:
                                lst.append(ch)
                i += 2
                if i < len(ch_obj) and isinstance(ch_obj[i], int):
                    i += 1 + ch_obj[i] * 2

    return started, stopped, scales


def _resample_curve_points(
    pts: list[tuple[float, float]], max_points: int = 64
) -> list[tuple[float, float]]:
    """Downsample normalized (t, y) curve points while preserving endpoints."""
    if len(pts) <= 1:
        return pts
    # Deduplicate points that collapse to the same 8-bit x slot
    by_slot: dict[int, tuple[float, float]] = {}
    for t, y in pts:
        tx = max(0.0, min(1.0, float(t)))
        ty = max(0.0, min(1.0, float(y)))
        by_slot[int(round(tx * 255.0))] = (tx, ty)
    ordered = [by_slot[k] for k in sorted(by_slot)]
    if len(ordered) <= max_points:
        return ordered
    step = (len(ordered) - 1) / float(max_points - 1)
    indices = [int(round(i * step)) for i in range(max_points - 1)] + [len(ordered) - 1]
    return [ordered[idx] for idx in dict.fromkeys(indices)]


def _extract_eos_effect_curve_points(
    curve_obj: list[Any],
) -> tuple[
    int,
    list[list[float]],
    list[tuple[float, float]],
    list[tuple[float, float]],
]:
    """Extract (dim, raw_data, x_norm_pts, y_norm_pts) from ``curve_obj[10]``."""
    dim = (
        int(curve_obj[4]) if len(curve_obj) > 4 and isinstance(curve_obj[4], int) else 0
    )
    cycle_ms = (
        float(curve_obj[8])
        if len(curve_obj) > 8
        and isinstance(curve_obj[8], (int, float))
        and curve_obj[8] > 0
        else 0.0
    )
    pts_tbl = (
        curve_obj[10]
        if len(curve_obj) > 10 and isinstance(curve_obj[10], list)
        else None
    )
    if pts_tbl is None:
        return dim, [], [], []

    raw_rows: list[tuple[float, float, float]] = []
    raw_data: list[list[float]] = []
    si = 10
    while si + 1 < len(pts_tbl):
        pt = pts_tbl[si + 1]
        if isinstance(pt, list) and len(pt) >= 7:
            vx = -1.0 if pt[3] is None else max(-1.0, min(1.0, float(pt[3])))
            vy = (
                (-1.0 if pt[4] is None else max(-1.0, min(1.0, float(pt[4]))))
                if dim >= 2
                else 0.0
            )
            dt_ms = (
                float(pt[6]) if isinstance(pt[6], (int, float)) and pt[6] >= 0 else 0.0
            )
            raw_rows.append((vx, vy, dt_ms))
            raw_data.append([vx, vy] if dim >= 2 else [vx])
        si += 2

    if len(raw_rows) < 2:
        return dim, raw_data, [], []

    total_dt = sum(dt for _, _, dt in raw_rows)
    denom = total_dt if total_dt > 0.0 else cycle_ms
    x_pts: list[tuple[float, float]] = []
    y_pts: list[tuple[float, float]] = []

    if denom > 0.0:
        acc = 0.0
        for idx, (vx, vy, dt_ms) in enumerate(raw_rows):
            if idx == 0:
                t_norm = 0.0
                if dt_ms > 0.0:
                    acc += dt_ms
            else:
                acc += dt_ms
                t_norm = max(0.0, min(1.0, acc / denom))
            x_pts.append((t_norm, max(0.0, min(1.0, (vx + 1.0) * 0.5))))
            if dim >= 2:
                y_pts.append((t_norm, max(0.0, min(1.0, (vy + 1.0) * 0.5))))
        if x_pts[-1][0] < 0.999:
            x_pts.append((1.0, x_pts[0][1]))
            if dim >= 2 and y_pts:
                y_pts.append((1.0, y_pts[0][1]))
    else:
        n_pts = len(raw_rows)
        for idx, (vx, vy, _dt) in enumerate(raw_rows):
            t_norm = idx / float(n_pts - 1)
            x_pts.append((t_norm, max(0.0, min(1.0, (vx + 1.0) * 0.5))))
            if dim >= 2:
                y_pts.append((t_norm, max(0.0, min(1.0, (vy + 1.0) * 0.5))))

    return (
        dim,
        raw_data,
        _resample_curve_points(x_pts),
        _resample_curve_points(y_pts),
    )


def _alloc_curve_id(curves_dict: dict[int, Any], start: int = 1000) -> int:
    """Return the first unused integer curve ID starting at *start*."""
    cid = start
    while cid in curves_dict:
        cid += 1
    return cid


def _pid_to_olc_key(
    pid: int, personality: EosPersonality | None, param_names: dict[int, str]
) -> str | None:
    """Map an Eos ``param_id`` to the OLC ``device_values`` / ``palette_refs`` key."""
    pname = param_names.get(pid, "").lower()
    if pid == 1 or pname == "intens":
        return "intensity"
    pdef = personality.params.get(pid) if personality is not None else None
    if pdef is not None and pdef.is_virtual:
        return None
    if pname in _PHYSICAL_PARAM_NAMES:
        return _PHYSICAL_PARAM_NAMES[pname]
    if pname in ("red", "green", "blue", "cyan", "magenta", "yellow"):
        return pname
    ctype = EOS_PARAM_TO_CHANNEL_TYPE.get(pname, ChannelType.GENERIC)
    if ctype is not ChannelType.GENERIC:
        return ctype.value
    if pname and (pdef is not None or pname in EOS_GENERIC_PARAM_NAMES):
        return pname
    return None


def _classify_palette_category(
    channels_raw: dict[int, dict[int, float]],
    param_names: dict[int, str],
    param_categories: dict[int, int] | None = None,
) -> PaletteCategory:
    """Infer OLC PaletteCategory from Eos ``tree[3]`` parameter categories."""
    has_focus = False
    has_color = False
    has_beam = False
    has_intens = False

    for params in channels_raw.values():
        for pid in params:
            cat_id = param_categories.get(pid) if param_categories else None
            if cat_id == 1:
                has_intens = True
            elif cat_id == 2:
                has_focus = True
            elif cat_id == 3:
                has_color = True
            elif cat_id in (4, 5, 6):
                has_beam = True
            else:
                pname = param_names.get(pid, "").lower()
                if pid == 1 or pname == "intens":
                    has_intens = True
                elif pname in ("pan", "tilt"):
                    has_focus = True
                elif pname in (
                    "red",
                    "green",
                    "blue",
                    "white",
                    "amber",
                    "lime",
                    "cyan",
                    "magenta",
                    "yellow",
                    "indigo",
                    "color_select",
                    "color_temperature",
                    "cto",
                ):
                    has_color = True
                else:
                    has_beam = True

    cats = sum((has_intens, has_focus, has_color, has_beam))
    if cats > 1:
        return PaletteCategory.PRESET
    if has_focus:
        return PaletteCategory.FOCUS
    if has_color:
        return PaletteCategory.COLOR
    if has_beam:
        return PaletteCategory.BEAM
    if has_intens:
        return PaletteCategory.INTENSITY
    return PaletteCategory.PRESET


def _extract_ms_time(
    obj: object,
    default_sec: float = 0.0,
    *,
    explicit_only: bool = False,
) -> tuple[float | None, float | None]:
    """Extract ``(time_sec, delay_sec)`` from a cue timing ``OBJ``."""
    if not isinstance(obj, list) or len(obj) < 4:
        return None, None
    t_ms = obj[2]
    d_ms = obj[3]
    if explicit_only:
        t_explicit = len(obj) <= 5 or obj[5] is None
        d_explicit = len(obj) > 4 and obj[4] is None
        t_sec = (
            float(t_ms) / 1000.0
            if t_explicit and isinstance(t_ms, (int, float))
            else None
        )
        d_sec = (
            float(d_ms) / 1000.0
            if d_explicit and isinstance(d_ms, (int, float))
            else None
        )
        return t_sec, d_sec
    t_sec = float(t_ms) / 1000.0 if isinstance(t_ms, (int, float)) else default_sec
    d_sec = float(d_ms) / 1000.0 if isinstance(d_ms, (int, float)) else 0.0
    return t_sec, d_sec


def _parse_cue_discrete_times(cue24: object) -> dict[int, dict[str, float]]:
    """Extract per-channel discrete fade/delay times from ``cue[24]``."""
    result: dict[int, dict[str, float]] = {}
    if not isinstance(cue24, list):
        return result
    for channels, ch_obj in _iter_eos_channel_blocks(cue24):
        chosen: tuple[float, float] | None = None
        i = 3
        n = len(ch_obj)
        while i + 1 < n:
            tok = ch_obj[i]
            if (
                isinstance(tok, list)
                and len(tok) >= 3
                and tok[0] == "OBJ"
                and tok[1] == 1
            ):
                break
            t_obj = ch_obj[i + 1]
            if isinstance(tok, int) and isinstance(t_obj, list):
                t_ms = (
                    t_obj[2][2]
                    if len(t_obj) > 2
                    and isinstance(t_obj[2], list)
                    and len(t_obj[2]) > 2
                    and isinstance(t_obj[2][2], (int, float))
                    else None
                )
                if t_ms is not None:
                    d_ms = (
                        t_obj[3][2]
                        if len(t_obj) > 3
                        and isinstance(t_obj[3], list)
                        and len(t_obj[3]) > 2
                        and isinstance(t_obj[3][2], (int, float))
                        else 0.0
                    )
                    pair = (float(d_ms) / 1000.0, float(t_ms) / 1000.0)
                    if tok == 1:
                        chosen = pair
                        break
                    if chosen is None:
                        chosen = pair
                i += 2
            else:
                i += 1
        if chosen is not None:
            delay_s, time_s = chosen
            for ch in channels:
                result[ch] = {"delay": delay_s, "time": time_s}
    return result


def _parse_cue_part_timings(
    cue25: object, default_time: float
) -> dict[int, dict[str, float]]:
    """Extract per-part ``(delay, time)`` for Parts > 1 from ``cue[25]``."""
    timings: dict[int, dict[str, float]] = {}
    if (
        not isinstance(cue25, list)
        or len(cue25) < 5
        or not isinstance(cue25[2], int)
        or cue25[2] <= 1
    ):
        return timings
    i = 3
    n = len(cue25)
    while i + 1 < n:
        part_num = cue25[i]
        part_obj = cue25[i + 1]
        if (
            isinstance(part_num, int)
            and part_num > 1
            and isinstance(part_obj, list)
            and len(part_obj) > 8
            and isinstance(part_obj[8], list)
            and len(part_obj[8]) > 3
        ):
            t_up, d_up = _extract_ms_time(part_obj[8][3], default_time)
            timings[part_num] = {
                "delay": d_up if d_up is not None else 0.0,
                "time": t_up if t_up is not None else default_time,
            }
        i += 2
    return timings


def _parse_cue_hang_sec(cue21: object) -> float | None:
    """Extract Hang/Follow time in seconds from ``cue[21]`` if enabled."""
    if (
        isinstance(cue21, list)
        and len(cue21) >= 4
        and isinstance(cue21[2], int)
        and cue21[2] >= 1
        and isinstance(cue21[3], list)
        and len(cue21[3]) >= 4
        and isinstance(cue21[3][3], (int, float))
    ):
        return float(cue21[3][3]) / 1000.0
    return None


class Esf3dParser:
    """Parser for native ETC Eos ``.esf3d`` / ``.esf2`` binary showfiles."""

    def __init__(
        self,
        imported: ImportFile,
        default_time: float = 5.0,
        importation: bool = False,
    ) -> None:
        self.imported = imported
        self.default_time = default_time
        self.importation = importation

    def read(self) -> None:
        """Read and parse the `.esf3d` file (non-blocking wrapper)."""
        self.read_sync(auto_import=True)

    def read_sync(self, auto_import: bool = True) -> None:
        """Read and parse the `.esf3d` archive synchronously."""
        path = _resolve_file_path(self.imported.file)
        with zipfile.ZipFile(path, "r") as zf:
            if "showdat.dat" not in zf.namelist():
                raise ValueError(f"Archive {path} does not contain showdat.dat")
            showdat_bytes = zf.read("showdat.dat")
            a3d_bytes = (
                zf.read("working.a3d") if "working.a3d" in zf.namelist() else b""
            )

        _header, tree = decode_showdat(showdat_bytes)
        a3d_patch = parse_working_a3d_patch(a3d_bytes)
        a3d_scenery = parse_working_a3d_scenery(a3d_bytes)

        tree3 = tree[3] if len(tree) > 3 else []
        param_names = parse_param_types(tree3)
        param_categories = parse_param_categories(tree3)
        personalities = parse_personalities(
            tree[2] if len(tree) > 2 else [], param_names
        )

        # Register FixtureDefinitions from tree[2], optionally enriched via local GDTF
        data = self.imported.data.data
        if a3d_scenery:
            data["scenery"] = a3d_scenery
        fixture_library = getattr(self.imported.lightshow, "fixture_library", None)
        actions = getattr(self.imported, "actions", {})
        fdef_by_guid: dict[str, dict[str, Any]] = {}
        pers_id = 0
        for guid, pers in sorted(personalities.items()):
            if pers.is_dimmer:
                continue
            pers_id += 1
            eos_fdef = build_olc_fixture_definition(pers)
            match = match_eos_fixture_definition(pers_id, eos_fdef, fixture_library)
            data.setdefault("gdtf_matches", {})[pers_id] = match.to_summary_dict()
            if (
                should_use_gdtf_for_personality(pers_id, match, actions)
                and match.gdtf_definition is not None
                and match.gdtf_mode is not None
            ):
                eos_fdef = enrich_fixture_from_gdtf(
                    eos_fdef, match.gdtf_definition, match.gdtf_mode
                )
            fdef_dict = eos_fdef.to_dict()
            fdef_by_guid[guid] = fdef_dict
            data["fixture_definitions"].append(fdef_dict)

        # Parse Show Metadata
        self._parse_metadata(tree, data)

        # Parse Patch (tree[5])
        ch_personalities = self._parse_patch(
            tree[5] if len(tree) > 5 else [],
            personalities,
            fdef_by_guid,
            a3d_patch,
            data,
        )

        # Parse Cues, Groups, Palettes from tree[6:]
        self._parse_show_objects(
            tree[6:] if len(tree) > 6 else [],
            ch_personalities,
            param_names,
            param_categories,
            data,
        )

        self.imported.data.clean()
        if auto_import:
            if not self.importation:
                self.imported.load_all()
            else:
                self.imported.select_data()

    @staticmethod
    def _parse_metadata(tree: list[Any], data: dict[str, Any]) -> None:
        for item in tree[6:]:
            if (
                isinstance(item, list)
                and len(item) == 11
                and item[0] == "OBJ"
                and item[1] == 1
                and isinstance(item[5], str)
                and item[5]
            ):
                data["show_metadata"]["title"] = item[5]
                break

    @staticmethod
    def _parse_patch(
        tree5: list[Any],
        personalities: dict[str, EosPersonality],
        fdef_by_guid: dict[str, dict[str, Any]],
        a3d_patch: dict[int, dict[str, tuple[float, float, float]]],
        data: dict[str, Any],
    ) -> dict[int, EosPersonality]:
        ch_pers: dict[int, EosPersonality] = {}
        if not isinstance(tree5, list):
            return ch_pers

        for item in tree5:
            if (
                not isinstance(item, list)
                or len(item) < 40
                or not isinstance(item[3], int)
                or item[3] <= 0
            ):
                continue

            ch = item[3]
            guid = item[5] if isinstance(item[5], str) else ""
            addr_start = item[6] if isinstance(item[6], int) else 0
            if addr_start <= 0:
                continue

            univ_idx = (addr_start - 1) // 512
            if univ_idx < 0 or univ_idx >= NB_UNIVERSES:
                continue
            universe = UNIVERSES[univ_idx]
            dmx_addr = ((addr_start - 1) % 512) + 1

            label = ""
            if isinstance(item[4], str) and item[4]:
                label = item[4]
            elif len(item) > 56 and isinstance(item[56], str) and item[56]:
                label = item[56]

            # 3D position & orientation from tree[5][66] or working.a3d fallback
            position = (0.0, 0.0, 0.0)
            orientation = (0.0, 0.0, 0.0)
            has_transform = False
            if len(item) > 66 and isinstance(item[66], list) and len(item[66]) >= 8:
                t = item[66]
                if all(isinstance(t[k], (int, float)) for k in range(2, 8)):
                    px, py, pz = float(t[2]), float(t[3]), float(t[4])
                    rx, ry, rz = float(t[5]), float(t[6]), float(t[7])
                    if any(v != 0.0 for v in (px, py, pz, rx, ry, rz)):
                        position = (px, py, pz)
                        orientation = eos_euler_to_olc(rx, ry, rz)
                        has_transform = True

            if not has_transform and ch in a3d_patch:
                position = a3d_patch[ch].get("position", position)
                orientation = a3d_patch[ch].get("orientation", orientation)
                has_transform = True

            focus_point = compute_focus_point_from_orientation(position, orientation)

            # Optional gel string in patch record
            gel_str = ""
            gel_hex = ""
            for g_idx in (19, 20, 21):
                if len(item) > g_idx and isinstance(item[g_idx], str) and item[g_idx]:
                    if lookup_gel(item[g_idx]) is not None:
                        gel_str = item[g_idx]
                        gel_hex = resolve_gel_hex(gel_str) or ""
                        break

            # Optional BeamAngle at index 64
            beam_angle: float | None = None
            if (
                len(item) > 64
                and isinstance(item[64], (int, float))
                and 1.0 <= float(item[64]) <= 180.0
            ):
                beam_angle = float(item[64])

            pers = personalities.get(guid)
            if pers is not None:
                ch_pers[ch] = pers

            if pers is not None and not pers.is_dimmer and guid in fdef_by_guid:
                from olc.devices.fixture import FixtureDefinition

                fdef = FixtureDefinition.from_dict(fdef_by_guid[guid])
                dev = fdef.instantiate(
                    fixture_id=ch,
                    label=label or f"{fdef.model} {ch}",
                    universe=universe,
                    address=dmx_addr,
                )
                dev.position = position
                dev.orientation = orientation
                dev.focus_point = focus_point
                if beam_angle is not None:
                    dev.beam_angle = beam_angle
                if gel_str:
                    dev.gel = gel_str
                    dev.gel_color = gel_hex
                dev_dict = dev.to_dict()
                dev_dict.pop("intensity", None)
                dev_dict.pop("target_color", None)
                dev_dict.pop("base_emitters", None)
                data["devices"][ch] = dev_dict
            else:
                data["patch"].setdefault(ch, []).append(
                    {
                        "output": dmx_addr,
                        "universe": universe,
                        "curve": 0,
                        "label": label,
                    }
                )
                meta: dict[str, Any] = {}
                if has_transform:
                    meta["position"] = position
                    meta["orientation"] = orientation
                    meta["focus_point"] = focus_point
                if beam_angle is not None:
                    meta["beam_angle"] = beam_angle
                if gel_str:
                    meta["gel"] = gel_str
                    meta["gel_color"] = gel_hex
                if meta:
                    data.setdefault("patch_meta", {})[ch] = meta

        return ch_pers

    def _parse_show_objects(
        self,
        items: list[Any],
        ch_pers: dict[int, EosPersonality],
        param_names: dict[int, str],
        param_categories: dict[int, int],
        data: dict[str, Any],
    ) -> None:
        cuelist_labels: dict[int, str] = {}
        cuelist_order: list[int] = []
        cuelist_start_cues: dict[float, int] = {}
        raw_effects: list[
            tuple[
                dict[str, Any],
                float | None,
                tuple[list[tuple[float, float]], list[tuple[float, float]]],
            ]
        ] = []
        raw_cues: list[
            tuple[
                int | None,
                float,
                dict[int, dict[int, float]],
                dict[int, dict[int, tuple[str, float]]],
                dict[str, Any],
                dict[str, Any],
            ]
        ] = []

        for item in items:
            if not isinstance(item, list):
                continue

            # Cue List: len == 27, item[2] is int cl_id, item[4] is optional label
            if len(item) == 27 and isinstance(item[2], int) and item[2] > 0:
                cl_id = item[2]
                cl_label = str(item[4]) if isinstance(item[4], str) else ""
                cuelist_labels[cl_id] = cl_label
                if cl_id not in cuelist_order:
                    cuelist_order.append(cl_id)
                seq = data["sequences"].setdefault(
                    cl_id,
                    {
                        "label": cl_label,
                        "mode": "normal",
                        "tracking_mode": True,
                        "steps": {},
                        "cues": {},
                    },
                )
                seq["tracking_mode"] = True
                if cl_label:
                    seq["label"] = cl_label
                continue

            # Playback start-cue record: len == 8, item[2] holds (cue*10000, cl_id)
            if (
                len(item) == 8
                and isinstance(item[2], list)
                and len(item[2]) >= 4
                and isinstance(item[2][2], int)
                and item[2][2] > 0
                and isinstance(item[2][3], int)
                and item[2][3] > 0
            ):
                cuelist_start_cues[item[2][2] / 10000.0] = item[2][3]
                continue

            # Cue: len == 31, item[2] is ['OBJ', 1, cue_num*10000, label, ...]
            if (
                len(item) == 31
                and isinstance(item[2], list)
                and len(item[2]) >= 4
                and isinstance(item[2][2], int)
                and item[2][2] > 0
            ):
                explicit_cl: int | None = None
                if (
                    len(item) > 20
                    and isinstance(item[20], list)
                    and len(item[20]) > 3
                    and isinstance(item[20][3], int)
                    and item[20][3] > 0
                ):
                    explicit_cl = item[20][3]

                cue_num = item[2][2] / 10000.0
                label = str(item[2][3]) if isinstance(item[2][3], str) else ""
                raw_p_by_ch: dict[int, dict[int, float]] = {}
                raw_refs_by_ch: dict[int, dict[int, tuple[str, float]]] = {}
                ch_parts: dict[int, int] = {}

                if isinstance(item[22], list):
                    for channels, ch_obj in _iter_eos_channel_blocks(item[22]):
                        ch_refs: dict[int, tuple[str, float]] = {}
                        parts_seen: list[int] = []
                        raw_p = _parse_eos_channel_params(
                            ch_obj,
                            channels[0],
                            refs_out=ch_refs,
                            part_out=parts_seen,
                        )
                        if raw_p:
                            for ch in channels:
                                raw_p_by_ch[ch] = raw_p
                                if ch_refs:
                                    raw_refs_by_ch[ch] = ch_refs
                                if parts_seen:
                                    ch_parts[ch] = parts_seen[0]

                t_up, d_up = (
                    _extract_ms_time(item[19][3], self.default_time)
                    if isinstance(item[19], list) and len(item[19]) > 3
                    else (self.default_time, 0.0)
                )
                t_dn, d_dn = (
                    _extract_ms_time(item[19][4], t_up or self.default_time)
                    if isinstance(item[19], list) and len(item[19]) > 4
                    else (t_up, d_up)
                )
                t_pos, d_pos = (
                    _extract_ms_time(item[19][5], explicit_only=True)
                    if isinstance(item[19], list) and len(item[19]) > 5
                    else (None, None)
                )
                t_col, d_col = (
                    _extract_ms_time(item[19][6], explicit_only=True)
                    if isinstance(item[19], list) and len(item[19]) > 6
                    else (None, None)
                )
                t_bm, d_bm = (
                    _extract_ms_time(item[19][7], explicit_only=True)
                    if isinstance(item[19], list) and len(item[19]) > 7
                    else (None, None)
                )

                cue_dict: dict[str, Any] = {
                    "number": cue_num,
                    "label": label,
                    "channels": {},
                    "device_values": {},
                    "is_int_block": item[12] is not None,
                    "is_block": item[13] is not None,
                    "is_assert": item[14] is not None,
                    "notes": str(item[16]) if isinstance(item[16], str) else "",
                }
                raw_eff_data = _parse_cue_effect_raw(item[23], item[26])
                if any(raw_eff_data):
                    cue_dict["_raw_effect"] = raw_eff_data
                step_dict: dict[str, Any] = {
                    "cue": cue_num,
                    "label": label,
                    "time_in": t_up if t_up is not None else self.default_time,
                    "time_out": t_dn if t_dn is not None else self.default_time,
                    "delay_in": d_up if d_up is not None else 0.0,
                    "delay_out": d_dn if d_dn is not None else 0.0,
                }
                if t_pos is not None:
                    step_dict["time_position"] = t_pos
                if d_pos is not None:
                    step_dict["delay_position"] = d_pos
                if t_col is not None:
                    step_dict["time_color"] = t_col
                if d_col is not None:
                    step_dict["delay_color"] = d_col
                if t_bm is not None:
                    step_dict["time_beam"] = t_bm
                if d_bm is not None:
                    step_dict["delay_beam"] = d_bm

                ch_times: dict[int, dict[str, float]] = {}
                part_timings = _parse_cue_part_timings(item[25], self.default_time)
                if part_timings and ch_parts:
                    for ch, pnum in ch_parts.items():
                        if pnum in part_timings:
                            ch_times[ch] = dict(part_timings[pnum])
                discrete_times = _parse_cue_discrete_times(item[24])
                if discrete_times:
                    ch_times.update(discrete_times)
                if ch_times:
                    step_dict["channel_time"] = ch_times

                hang_sec = _parse_cue_hang_sec(item[21])
                if hang_sec is not None:
                    step_dict["_hang_after"] = hang_sec
                raw_cues.append(
                    (
                        explicit_cl,
                        cue_num,
                        raw_p_by_ch,
                        raw_refs_by_ch,
                        cue_dict,
                        step_dict,
                    )
                )

            # Group: len == 4, item[2] header, item[3] channel list
            elif (
                len(item) == 4
                and isinstance(item[2], list)
                and len(item[2]) >= 4
                and isinstance(item[2][2], int)
                and isinstance(item[3], list)
                and len(item[3]) >= 6
            ):
                grp_num = item[2][2] / 10000.0
                label = str(item[2][3]) if isinstance(item[2][3], str) else ""
                channels = [el for el in item[3][6:] if isinstance(el, int) and el > 0]
                if channels:
                    data["groups"][grp_num] = {
                        "label": label,
                        "channels": list(dict.fromkeys(channels)),
                    }

            # Palette / Preset: len == 10, item[5] header, item[6] channel params
            elif (
                len(item) == 10
                and isinstance(item[5], list)
                and len(item[5]) >= 4
                and isinstance(item[5][2], int)
                and isinstance(item[6], list)
                and len(item[6]) >= 5
            ):
                pal_num = item[5][2] / 10000.0
                label = str(item[5][3]) if isinstance(item[5][3], str) else ""
                raw_by_ch: dict[int, dict[int, float]] = {}
                pal_channels: dict[int, float] = {}
                pal_dev_vals: dict[int, dict[str, Any]] = {}

                for channels, ch_obj in _iter_eos_channel_blocks(item[6]):
                    raw_p = _parse_eos_channel_params(ch_obj, channels[0])
                    if raw_p:
                        for ch in channels:
                            raw_by_ch[ch] = raw_p
                            dvals, ival = _decode_channel_values(
                                raw_p, ch_pers.get(ch), param_names
                            )
                            if ival is not None:
                                pal_channels[ch] = ival
                            if dvals:
                                pal_dev_vals[ch] = dvals

                if raw_by_ch:
                    cat = _classify_palette_category(
                        raw_by_ch, param_names, param_categories
                    )
                    data.setdefault("palettes", {}).setdefault(cat.value, {})[
                        pal_num
                    ] = {
                        "category": cat.value,
                        "number": pal_num,
                        "label": label,
                        "channels": pal_channels,
                        "device_values": pal_dev_vals,
                    }

            # Curve: len == 5, item[3] header, item[4] points
            elif (
                len(item) == 5
                and isinstance(item[3], list)
                and len(item[3]) >= 4
                and isinstance(item[3][2], int)
                and item[3][2] > 0
                and isinstance(item[4], list)
                and len(item[4]) > 10
            ):
                curve_num = item[3][2] // 10000
                if curve_num > 0:
                    label = str(item[3][3]) if isinstance(item[3][3], str) else ""
                    curve_type = (
                        "SteppedCurve" if item[2] is None else "InterpolateCurve"
                    )
                    pts_raw = item[4][10:]
                    points: list[tuple[float, float]] = []
                    idx_p = 0
                    while idx_p + 1 < len(pts_raw):
                        x_val = pts_raw[idx_p]
                        y_obj = pts_raw[idx_p + 1]
                        if (
                            isinstance(x_val, (int, float))
                            and isinstance(y_obj, list)
                            and len(y_obj) >= 3
                            and isinstance(y_obj[2], (int, float))
                        ):
                            nx = max(0.0, min(1.0, float(x_val) / 100.0))
                            ny = max(0.0, min(1.0, float(y_obj[2]) / 100.0))
                            points.append((nx, ny))
                        idx_p += 2
                    if points:
                        data["curves"][curve_num] = {
                            "type": curve_type,
                            "label": label,
                            "points": points,
                            "normalized": True,
                        }

            # Submaster: len == 21, item[2] header, item[16] channels
            elif (
                len(item) == 21
                and isinstance(item[2], list)
                and len(item[2]) >= 4
                and isinstance(item[2][2], int)
                and item[2][2] > 0
                and isinstance(item[16], list)
            ):
                sub_num = float(item[2][2])
                label = str(item[2][3]) if isinstance(item[2][3], str) else ""
                sub_channels: dict[int, float] = {}
                sub_dev_vals: dict[int, dict[str, Any]] = {}
                for channels, ch_obj in _iter_eos_channel_blocks(item[16]):
                    raw_p = _parse_eos_channel_params(ch_obj, channels[0])
                    if raw_p:
                        for ch in channels:
                            dvals, ival = _decode_channel_values(
                                raw_p, ch_pers.get(ch), param_names
                            )
                            if ival is not None:
                                sub_channels[ch] = ival
                            if dvals:
                                sub_dev_vals[ch] = dvals
                sub_int = int(sub_num)
                page = ((sub_int - 1) // MAX_FADER_PER_PAGE) + 1
                fader_nb = ((sub_int - 1) % MAX_FADER_PER_PAGE) + 1
                sub_started, _sub_stopped, sub_scales = _parse_cue_effect_raw(
                    item[17] if len(item) > 17 else None,
                    item[18] if len(item) > 18 else None,
                )
                if sub_started:
                    eff_id, ch_list = next(iter(sub_started.items()))
                    sz, rt = sub_scales.get(eff_id, (None, None))
                    fader_dict: dict[str, Any] = {
                        "page": page,
                        "number": fader_nb,
                        "type": FaderType.EFFECT,
                        "contents": eff_id,
                        "effect_channels": list(ch_list),
                        "control_mode": "size",
                        "label": label,
                        "text": label,
                    }
                    if sub_channels:
                        fader_dict["base_channels"] = sub_channels
                    if sz is not None:
                        fader_dict["base_size_scale"] = sz
                    if rt is not None:
                        fader_dict["base_rate_scale"] = rt
                    data["faders"][(page, fader_nb)] = fader_dict
                    if sub_channels or sub_dev_vals:
                        presets_pool = data.setdefault("palettes", {}).setdefault(
                            PaletteCategory.PRESET.value, {}
                        )
                        if sub_num not in presets_pool:
                            presets_pool[sub_num] = {
                                "category": PaletteCategory.PRESET.value,
                                "number": sub_num,
                                "label": label,
                                "channels": sub_channels,
                                "device_values": sub_dev_vals,
                            }
                else:
                    presets_pool = data.setdefault("palettes", {}).setdefault(
                        PaletteCategory.PRESET.value, {}
                    )
                    if sub_num not in presets_pool:
                        presets_pool[sub_num] = {
                            "category": PaletteCategory.PRESET.value,
                            "number": sub_num,
                            "label": label,
                            "channels": sub_channels,
                            "device_values": sub_dev_vals,
                        }
                    data["faders"][(page, fader_nb)] = {
                        "page": page,
                        "number": fader_nb,
                        "type": FaderType.PRESET,
                        "contents": sub_num,
                        "label": label,
                    }

            # Effect: len == 27, item[2] is ['OBJ', 1, eff_num*10000, label, ...]
            # Exclude Macros of len == 27 which lack item[24][11].
            elif (
                len(item) == 27
                and isinstance(item[2], list)
                and len(item[2]) >= 4
                and isinstance(item[2][2], int)
                and item[2][2] > 0
                and isinstance(item[24], list)
                and len(item[24]) > 11
                and isinstance(item[24][11], list)
            ):
                eff_num = item[2][2] / 10000.0
                label = str(item[2][3]) if isinstance(item[2][3], str) else ""
                raw_eff = new_eos_effect(eff_num)
                raw_eff["label"] = label
                if isinstance(item[3], int) and item[3] > 0:
                    raw_eff["grouping"] = item[3]
                if isinstance(item[4], (int, float)) and item[4] > 0:
                    raw_eff["trail"] = float(item[4])
                if isinstance(item[6], int):
                    raw_eff["entry_mode"] = eos_envelope_mode(item[6])
                if isinstance(item[7], int):
                    raw_eff["exit_mode"] = eos_envelope_mode(item[7])
                if isinstance(item[26], list) and len(item[26]) > 4:
                    if 1562 in item[26][4:]:
                        raw_eff["random"] = True
                e24_11 = item[24][11]
                cycle_ms: float | None = None
                curve_axes: tuple[
                    list[tuple[float, float]], list[tuple[float, float]]
                ] = ([], [])
                if e24_11 is not None:
                    if len(e24_11) > 3 and isinstance(e24_11[3], (int, float)):
                        raw_eff["scale"] = float(e24_11[3])
                    pcount = (
                        e24_11[5]
                        if len(e24_11) > 5 and isinstance(e24_11[5], int)
                        else 0
                    )
                    pids = (
                        [int(x) for x in e24_11[6 : 6 + pcount] if isinstance(x, int)]
                        if pcount > 0
                        else []
                    )
                    raw_eff["param_ids"] = pids
                    curve_idx = 6 + pcount
                    curve_obj = (
                        e24_11[curve_idx]
                        if len(e24_11) > curve_idx
                        and isinstance(e24_11[curve_idx], list)
                        else None
                    )
                    steps_tbl = (
                        curve_obj[10]
                        if curve_obj is not None
                        and len(curve_obj) > 10
                        and isinstance(curve_obj[10], list)
                        else None
                    )
                    if (
                        curve_obj is not None
                        and len(curve_obj) > 8
                        and isinstance(curve_obj[8], (int, float))
                        and curve_obj[8] > 0
                    ):
                        cycle_ms = float(curve_obj[8])
                    step_count = (
                        steps_tbl[2]
                        if steps_tbl is not None
                        and len(steps_tbl) > 2
                        and isinstance(steps_tbl[2], int)
                        else 0
                    )
                    curve_dim = (
                        curve_obj[4]
                        if curve_obj is not None
                        and len(curve_obj) > 4
                        and isinstance(curve_obj[4], int)
                        else 0
                    )
                    is_focus_2d_curve = curve_dim == 2 and any(
                        p in (2, 3) for p in pids
                    )
                    if (
                        0 < step_count <= 16
                        and steps_tbl is not None
                        and not is_focus_2d_curve
                    ):
                        tokens: list[tuple[float, float, float, str]] = []
                        has_pal_ref = False
                        si = 10
                        while si + 1 < len(steps_tbl):
                            st = steps_tbl[si + 1]
                            if isinstance(st, list) and len(st) >= 9:
                                val = st[3] if isinstance(st[3], (int, float)) else 0.0
                                s_ms = st[6] if isinstance(st[6], (int, float)) else 0.0
                                d_ms = st[8] if isinstance(st[8], (int, float)) else 0.0
                                tok = _extract_effect_step_token(st)
                                if tok[:2] in ("IP", "FP", "CP", "BP", "PR"):
                                    has_pal_ref = True
                                tokens.append(
                                    (
                                        float(s_ms) / 1000.0,
                                        float(d_ms) / 1000.0,
                                        float(val),
                                        tok,
                                    )
                                )
                            si += 2
                        is_stepbased = "||ch" in label.lower() or (
                            len(item[24]) > 2 and item[24][2] == 2 and not has_pal_ref
                        )
                        raw_eff["eos_type"] = (
                            EOS_TYPE_STEPBASED if is_stepbased else EOS_TYPE_ABSOLUTE
                        )
                        for s_sec, d_sec, val, tok in tokens:
                            raw_eff["actions"].append((s_sec, d_sec, tok))
                            if is_stepbased:
                                raw_eff["steps"].append(
                                    [s_sec, 0.0, 0.0, 0.0, val, 0.0]
                                )
                            if s_sec + d_sec > 0:
                                raw_eff["step_times_ms"].append(
                                    (s_sec + d_sec) * 1000.0
                                )
                    else:
                        if any(p in (2, 3) for p in pids):
                            raw_eff["eos_type"] = EOS_TYPE_FOCUS
                        elif any(p in (9, 10, 11, 12, 13, 14) for p in pids):
                            raw_eff["eos_type"] = EOS_TYPE_COLOR
                        else:
                            raw_eff["eos_type"] = EOS_TYPE_LINEAR
                        if cycle_ms is not None:
                            raw_eff["step_times_ms"].append(cycle_ms)
                        if curve_obj is not None:
                            _dim, raw_data, x_pts, y_pts = (
                                _extract_eos_effect_curve_points(curve_obj)
                            )
                            if raw_data:
                                raw_eff["data"] = raw_data
                            curve_axes = (x_pts, y_pts)

                raw_effects.append((raw_eff, cycle_ms, curve_axes))

        # Convert effects after palettes are populated so palette-based effects
        # can infer their target parameter (e.g. BP -> zoom).
        curves_dict = data.setdefault("curves", {})
        for raw_eff, cycle_ms, (x_pts, y_pts) in raw_effects:
            eff_dict = convert_eos_effect(
                raw_eff, param_names, palettes=data.get("palettes")
            )
            if cycle_ms is not None and raw_eff["eos_type"] in (
                EOS_TYPE_LINEAR,
                EOS_TYPE_FOCUS,
                EOS_TYPE_COLOR,
            ):
                eff_dict["cycle_time"] = round(cycle_ms / 1000.0, 3)
            eff_label = str(eff_dict.get("label") or f"Effect {eff_dict['number']:g}")
            layers = eff_dict.get("layers")
            if (
                raw_eff["eos_type"] == EOS_TYPE_LINEAR
                and len(x_pts) >= 2
                and max(y for _, y in x_pts) - min(y for _, y in x_pts) > 1e-3
                and isinstance(layers, list)
                and layers
                and layers[0].get("waveform") != "random"
            ):
                cid = _alloc_curve_id(curves_dict)
                curves_dict[cid] = {
                    "type": "SegmentsCurve",
                    "label": eff_label,
                    "points": x_pts,
                    "normalized": True,
                }
                layers[0]["waveform"] = "curve"
                layers[0]["curve_id"] = cid
            elif (
                raw_eff["eos_type"] == EOS_TYPE_FOCUS
                and len(x_pts) >= 2
                and len(y_pts) >= 2
                and (
                    max(y for _, y in x_pts) - min(y for _, y in x_pts) > 1e-3
                    or max(y for _, y in y_pts) - min(y for _, y in y_pts) > 1e-3
                )
                and isinstance(layers, list)
                and len(layers) >= 2
            ):
                cid_x = _alloc_curve_id(curves_dict)
                curves_dict[cid_x] = {
                    "type": "SegmentsCurve",
                    "label": f"{eff_label} (Pan)",
                    "points": x_pts,
                    "normalized": True,
                }
                cid_y = _alloc_curve_id(curves_dict)
                curves_dict[cid_y] = {
                    "type": "SegmentsCurve",
                    "label": f"{eff_label} (Tilt)",
                    "points": y_pts,
                    "normalized": True,
                }
                for layer, cid in ((layers[0], cid_x), (layers[1], cid_y)):
                    layer["waveform"] = "curve"
                    layer["curve_id"] = cid
                    layer.pop("phase_offset_deg", None)
                    layer.pop("freq_mult", None)
            data["effects"].append(eff_dict)

        # Route cues into their Cue Lists without collisions
        cues_by_list: dict[
            int,
            list[
                tuple[
                    float,
                    dict[int, dict[int, float]],
                    dict[int, dict[int, tuple[str, float]]],
                    dict[str, Any],
                    dict[str, Any],
                ]
            ],
        ] = {}
        used_nums: dict[int, set[float]] = {}
        explicit_anchors: list[tuple[float, int]] = []
        for (
            explicit_cl,
            cue_num,
            raw_p_by_ch,
            raw_refs_by_ch,
            cue_dict,
            step_dict,
        ) in raw_cues:
            if explicit_cl is not None:
                cues_by_list.setdefault(explicit_cl, []).append(
                    (cue_num, raw_p_by_ch, raw_refs_by_ch, cue_dict, step_dict)
                )
                used_nums.setdefault(explicit_cl, set()).add(cue_num)
                explicit_anchors.append((cue_num, explicit_cl))

        if not cuelist_order:
            cuelist_order = [1]

        for (
            explicit_cl,
            cue_num,
            raw_p_by_ch,
            raw_refs_by_ch,
            cue_dict,
            step_dict,
        ) in raw_cues:
            if explicit_cl is not None:
                continue
            start_cl = cuelist_start_cues.get(cue_num)
            if start_cl is not None and cue_num not in used_nums.get(start_cl, set()):
                target_cl = start_cl
            elif explicit_anchors:
                candidates = sorted(explicit_anchors, key=lambda a: abs(a[0] - cue_num))
                target_cl = next(
                    (
                        a_cl
                        for _, a_cl in candidates
                        if cue_num not in used_nums.get(a_cl, set())
                    ),
                    candidates[0][1],
                )
            else:
                target_cl = next(
                    (
                        cl_id
                        for cl_id in cuelist_order
                        if cue_num not in used_nums.get(cl_id, set())
                    ),
                    cuelist_order[0],
                )
            used_nums.setdefault(target_cl, set()).add(cue_num)
            cues_by_list.setdefault(target_cl, []).append(
                (cue_num, raw_p_by_ch, raw_refs_by_ch, cue_dict, step_dict)
            )

        # Evaluate each Cue List in cue-number order while tracking virtual params
        for cl_id, cl_cues in sorted(cues_by_list.items()):
            seq = data["sequences"].setdefault(
                cl_id,
                {
                    "label": cuelist_labels.get(cl_id, ""),
                    "mode": "normal",
                    "tracking_mode": True,
                    "steps": {},
                    "cues": {},
                },
            )
            seq["tracking_mode"] = True
            if cl_id in cuelist_labels and cuelist_labels[cl_id]:
                seq["label"] = cuelist_labels[cl_id]
            cl_cues.sort(key=lambda c: c[0])
            tracked_virtuals: dict[int, dict[int, float]] = {}
            active_effects: dict[float, tuple[list[int], float, float]] = {}
            pending_wait: float | None = None

            for step_idx, (
                cue_num,
                raw_p_by_ch,
                raw_refs_by_ch,
                cue_dict,
                step_dict,
            ) in enumerate(cl_cues, 1):
                hang_after = step_dict.pop("_hang_after", None)
                if pending_wait is not None:
                    step_dict["wait"] = pending_wait
                pending_wait = hang_after
                cue_channels: dict[int, float] = {}
                device_values: dict[int, dict[str, Any]] = {}
                palette_refs: dict[int, dict[str, tuple[str, float]]] = {}
                for ch, raw_p in raw_p_by_ch.items():
                    pers = ch_pers.get(ch)
                    ch_virt = tracked_virtuals.setdefault(ch, {})
                    if pers is not None:
                        for pid, val in raw_p.items():
                            pdef = pers.params.get(pid)
                            if pdef is not None and pdef.is_virtual:
                                ch_virt[pid] = val
                    dev_vals, int_val = _decode_channel_values(
                        raw_p, pers, param_names, virtual_context=ch_virt
                    )
                    if int_val is not None:
                        cue_channels[ch] = int_val
                    if dev_vals:
                        device_values[ch] = dev_vals
                    if ch in raw_refs_by_ch:
                        ch_olc_refs: dict[str, tuple[str, float]] = {}
                        for pid, ref in raw_refs_by_ch[ch].items():
                            key = _pid_to_olc_key(pid, pers, param_names)
                            if key is not None:
                                ch_olc_refs[key] = ref
                        if ch_olc_refs:
                            palette_refs[ch] = ch_olc_refs
                cue_dict["channels"] = cue_channels
                cue_dict["device_values"] = device_values
                if palette_refs:
                    cue_dict["palette_refs"] = palette_refs

                raw_eff_tuple = cue_dict.pop("_raw_effect", None)
                if raw_eff_tuple is not None:
                    started, stopped, scales = raw_eff_tuple
                    eff_refs: dict[int, dict[str, Any]] = {}
                    for eff_id in list(active_effects):
                        ch_list, sz, rt = active_effects[eff_id]
                        remaining = [c for c in ch_list if c not in stopped]
                        if remaining:
                            active_effects[eff_id] = (remaining, sz, rt)
                        else:
                            del active_effects[eff_id]
                    for ch in stopped:
                        eff_refs[ch] = {"stop": True}

                    for eff_id, ch_list in started.items():
                        new_sz, new_rt = scales.get(eff_id, (None, None))
                        sz = new_sz if new_sz is not None else 1.0
                        rt = new_rt if new_rt is not None else 1.0
                        active_effects[eff_id] = (list(ch_list), sz, rt)
                        for order_idx, ch in enumerate(ch_list):
                            eff_refs[ch] = {
                                "effect": eff_id,
                                "order_index": order_idx,
                                "channels": list(ch_list),
                                "rate_scale": rt,
                                "size_scale": sz,
                            }

                    for eff_id, (new_sz, new_rt) in scales.items():
                        if (
                            eff_id not in started
                            and eff_id in active_effects
                            and (new_sz is not None or new_rt is not None)
                        ):
                            ch_list, prev_sz, prev_rt = active_effects[eff_id]
                            sz = new_sz if new_sz is not None else prev_sz
                            rt = new_rt if new_rt is not None else prev_rt
                            active_effects[eff_id] = (ch_list, sz, rt)
                            for order_idx, ch in enumerate(ch_list):
                                if ch not in eff_refs:
                                    eff_refs[ch] = {
                                        "effect": eff_id,
                                        "order_index": order_idx,
                                        "channels": list(ch_list),
                                        "rate_scale": rt,
                                        "size_scale": sz,
                                    }

                    if eff_refs:
                        cue_dict["effect_refs"] = eff_refs

                seq["cues"][cue_num] = cue_dict
                seq["steps"][step_idx] = step_dict
