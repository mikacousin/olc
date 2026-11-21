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
"""Convert ETC Eos ``$Effect`` ASCII blocks into OLC EffectDefinition dicts."""

from __future__ import annotations

import re
import typing

from olc.files.ascii.eos_devices import eos_param_id_to_olc_key, parse_eos_param_token

EOS_TYPE_LINEAR = 1
EOS_TYPE_FOCUS = 2
EOS_TYPE_COLOR = 3
EOS_TYPE_ABSOLUTE = 4
EOS_TYPE_STEPBASED = 5

_RGB_IDS = frozenset({12, 13, 14})
_CMY_IDS = frozenset({9, 10, 11})
_PERCENT_RE = re.compile(r"^\(?([+-])?\)?\s*(-?[\d.]+)\s*%?$")


def _fmt_param(
    p_id: int, param_types: dict[int, str], default: str = "intensity"
) -> str:
    key = eos_param_id_to_olc_key(p_id, param_types)
    return key if key is not None else default


def new_eos_effect(number: float) -> dict[str, typing.Any]:
    """Return an empty raw accumulator for an Eos ``$Effect`` block."""
    return {
        "number": float(number),
        "label": "",
        "eos_type": EOS_TYPE_LINEAR,
        "scale": None,
        "grouping": None,
        "param_ids": [],
        "actions": [],
        "steps": [],
        "step_chans": {},
        "data": [],
        "random": False,
    }


def record_eos_effect_line(
    raw: dict[str, typing.Any], keyword: str, args: list[str]
) -> None:
    """Accumulate one secondary line of an Eos ``$Effect`` block into *raw*."""
    try:
        if keyword == "$$type" and args:
            raw["eos_type"] = int(args[0])
        elif keyword == "$$scale" and args:
            raw["scale"] = float(args[0])
        elif keyword == "$$grouping" and args:
            raw["grouping"] = int(float(args[0]))
        elif keyword == "$$paramlist":
            raw["param_ids"] = [int(a) for a in args if a.lstrip("-").isdigit()]
        elif keyword == "$$action" and len(args) >= 4:
            raw["actions"].append(
                (float(args[1]), float(args[2]), " ".join(args[3:]).strip())
            )
        elif keyword == "$$step" and len(args) >= 7:
            raw["steps"].append([float(a) for a in args[1:7]])
        elif keyword == "$$chanlist" and raw["steps"]:
            raw["step_chans"][len(raw["steps"])] = [int(a) for a in args]
        elif keyword == "$$data" and len(args) >= 2:
            raw["data"].append([float(a) for a in args[1:]])
        elif keyword == "$$command" and args and args[0] == "1562":
            raw["random"] = True
    except ValueError:
        return


def _classify_1d_waveform(label: str, data: list[list[float]]) -> str:
    low = label.lower()
    if "alea" in low or "random" in low:
        return "random"
    if "rampe" in low or "ramp" in low:
        if data and len(data) > 1 and data[0][0] > data[-1][0]:
            return "saw_down"
        return "saw_up"
    if "can" in low:
        return "pulse"
    if len(data) >= 8:
        first = data[0][0]
        last = data[-1][0]
        vals = [row[0] for row in data]
        spread = max(vals) - min(vals)
        if spread > 0.05:
            monotonic_up = all(
                b >= a - 1e-3 for a, b in zip(vals, vals[1:], strict=False)
            )
            monotonic_down = all(
                b <= a + 1e-3 for a, b in zip(vals, vals[1:], strict=False)
            )
            if monotonic_up and last > first:
                return "saw_up"
            if monotonic_down and last < first:
                return "saw_down"
    return "sine"


def _classify_2d(label: str, data: list[list[float]]) -> list[dict[str, typing.Any]]:
    low = label.lower()
    reverse = "invers" in low
    if "8" in low or "huit" in low or "figure" in low:
        return [
            {"parameter": "pan", "waveform": "sine", "freq_mult": 1.0},
            {"parameter": "tilt", "waveform": "sine", "freq_mult": 2.0},
        ]
    if "carr" in low or "square" in low:
        return [
            {"parameter": "pan", "waveform": "square", "phase_offset_deg": 0.0},
            {"parameter": "tilt", "waveform": "square", "phase_offset_deg": 90.0},
        ]
    if "triang" in low:
        return [
            {"parameter": "pan", "waveform": "triangle", "phase_offset_deg": 0.0},
            {"parameter": "tilt", "waveform": "triangle", "phase_offset_deg": 90.0},
        ]
    tilt_phase = 180.0 if reverse else 0.0
    return [
        {"parameter": "pan", "waveform": "sine"},
        {"parameter": "tilt", "waveform": "cosine", "phase_offset_deg": tilt_phase},
    ]


def _action_value(token: str) -> tuple[str, float | None, tuple[str, float] | None]:
    """Return (kind, value, palette_ref) for an Eos ``$$Action`` target token."""
    tok = token.strip().lower()
    if not tok or tok == "bkgrd":
        return "bkgrd", None, None
    _raw, ref = parse_eos_param_token(tok.replace(" ", ""))
    if ref is not None:
        return "palette", None, ref
    if tok.startswith("(+)") or tok.startswith("(-)"):
        match = _PERCENT_RE.match(tok.replace("(+)", "").replace("(-)", "").strip())
        if match:
            return "offset", float(match.group(2)), None
    match = _PERCENT_RE.match(tok)
    if match:
        val = float(match.group(2))
        return "level", val, None
    return "bkgrd", None, None


def _convert_absolute(raw: dict[str, typing.Any], param: str) -> dict[str, typing.Any]:
    actions: list[tuple[float, float, str]] = raw["actions"]
    total = sum(t + d for t, d, _tok in actions)
    cycle = max(0.05, total)
    first_t, first_d, _ = actions[0] if actions else (0.5, 0.0, "")
    first_span = max(1e-6, first_t + first_d)
    duty = max(0.01, min(1.0, first_span / cycle)) if actions else 0.5
    has_dwell = any(d > 0.0 for _t, d, _tok in actions)
    softness = 0.0 if has_dwell else 0.5

    kinds = [_action_value(tok) for _t, _d, tok in actions]
    palettes = [k[2] for k in kinds if k[0] == "palette" and k[2] is not None]
    layer: dict[str, typing.Any] = {
        "parameter": param,
        "waveform": "pulse",
        "mode": "absolute",
        "duty_cycle": duty,
        "softness": softness,
    }
    if len(palettes) >= 2:
        layer["low_palette"] = list(palettes[0])
        layer["high_palette"] = list(palettes[1])
    elif any(k[0] == "offset" for k in kinds):
        offs = [abs(k[1]) for k in kinds if k[0] == "offset" and k[1] is not None]
        layer["mode"] = "relative"
        layer["size"] = offs[0] if offs else 25.0
    else:
        levels = [k[1] for k in kinds if k[0] == "level" and k[1] is not None]
        has_bkgrd = any(k[0] == "bkgrd" for k in kinds)
        if levels and has_bkgrd:
            layer["low_value"] = levels[0]
        elif len(levels) >= 2:
            layer["low_value"] = min(levels)
            layer["high_value"] = max(levels)
        elif levels:
            layer["low_value"] = levels[0]
    return {"cycle_time": cycle, "layers": [layer]}


def _convert_stepbased(raw: dict[str, typing.Any]) -> dict[str, typing.Any]:
    steps: list[list[float]] = raw["steps"]
    n_steps = max(2, len(steps))
    step_time = steps[0][0] if steps else 1.0
    cycle = max(0.05, step_time * n_steps)
    layer: dict[str, typing.Any] = {
        "parameter": "intensity",
        "waveform": "pulse",
        "mode": "absolute",
        "duty_cycle": 1.0 / n_steps,
        "softness": 0.2,
        "low_value": 0.0,
        "high_value": 100.0,
    }
    return {"cycle_time": cycle, "layers": [layer], "groups": n_steps}


def convert_eos_effect(
    raw: dict[str, typing.Any], param_types: dict[int, str]
) -> dict[str, typing.Any]:
    """Convert a raw Eos ``$Effect`` accumulator into an EffectDefinition dict."""
    eos_type = int(raw["eos_type"])
    ids = list(raw["param_ids"])
    id_set = set(ids)
    label = str(raw["label"] or "").strip()
    if "||" in label:
        label = label.split("||", 1)[0].strip()
    scale = raw["scale"]

    result: dict[str, typing.Any] = {
        "number": float(raw["number"]),
        "label": label or f"Eos Effect {raw['number']:g}",
        "direction": "random" if raw["random"] else "forward",
        "groups": 0,
        "layers": [],
        "cycle_time": 2.0,
    }
    if raw["grouping"] is not None:
        result["groups"] = int(raw["grouping"])

    if eos_type == EOS_TYPE_ABSOLUTE and raw["actions"]:
        param = _fmt_param(ids[0], param_types) if ids else "intensity"
        result.update(_convert_absolute(raw, param))
        return result

    if eos_type == EOS_TYPE_STEPBASED:
        step_result = _convert_stepbased(raw)
        if raw["grouping"] is not None:
            step_result.pop("groups", None)
        result.update(step_result)
        return result

    if eos_type == EOS_TYPE_COLOR or id_set & (_RGB_IDS | _CMY_IDS) or 7 in id_set:
        result["layers"] = [
            {"parameter": "color", "waveform": "rainbow", "mode": "absolute"}
        ]
        result["cycle_time"] = 6.0
        return result

    if eos_type == EOS_TYPE_FOCUS or (2 in id_set and 3 in id_set):
        size = float(scale) if scale is not None else 15.0
        layers = _classify_2d(label, raw["data"])
        for layer in layers:
            layer["mode"] = "relative"
            layer["size"] = size
        result["layers"] = layers
        result["cycle_time"] = 4.0
        return result

    param = _fmt_param(ids[0], param_types) if ids else "intensity"
    wave = _classify_1d_waveform(label, raw["data"])
    size = (
        float(scale) if scale is not None else (50.0 if param == "intensity" else 25.0)
    )
    result["layers"] = [
        {
            "parameter": param,
            "waveform": wave,
            "mode": "relative",
            "size": size,
        }
    ]
    result["cycle_time"] = 3.0
    return result


def parse_effect_data_value(key: str, value: str) -> tuple[str, float] | None:
    """Parse an Eos ``$$EffectData`` key/value pair into an OLC override."""
    try:
        val = float(value)
    except ValueError:
        return None
    k = key.strip().lower()
    if k == "rate":
        return "rate_scale", max(0.01, val / 100.0)
    if k == "size":
        return "size_scale", max(0.0, val / 100.0)
    if k == "axis":
        return "axis_deg", val
    return None
