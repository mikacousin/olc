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

from olc.define import NB_UNIVERSES, UNIVERSES
from olc.devices.channel import ChannelType
from olc.devices.color_pick.gels import lookup_gel, resolve_gel_hex
from olc.devices.device import compute_focus_point_from_orientation
from olc.files.ascii.eos_devices import (
    _PHYSICAL_PARAM_NAMES,
    EOS_GENERIC_PARAM_NAMES,
    EOS_PARAM_TO_CHANNEL_TYPE,
)
from olc.files.eos.a3d import eos_euler_to_olc, parse_working_a3d_patch
from olc.files.eos.personality import (
    EosPersonality,
    build_olc_fixture_definition,
    evaluate_eos_param_to_dmx,
    parse_param_types,
    parse_personalities,
)
from olc.files.eos.wire import decode_showdat
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


def _parse_eos_channel_params(
    ch_params_obj: list[Any], channel_num: int
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
            # Complex entry: user value lives at val_obj[2][10][2]
            if (
                len(val_obj) >= 3
                and isinstance(val_obj[2], list)
                and len(val_obj[2]) > 10
                and isinstance(val_obj[2][10], list)
                and len(val_obj[2][10]) >= 3
                and isinstance(val_obj[2][10][2], (int, float))
            ):
                raw[pid] = float(val_obj[2][10][2])
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


def _classify_palette_category(
    channels_raw: dict[int, dict[int, float]], param_names: dict[int, str]
) -> PaletteCategory:
    """Infer OLC PaletteCategory from the Eos parameters present in a palette."""
    has_focus = False
    has_color = False
    has_beam = False
    has_intens = False

    for params in channels_raw.values():
        for pid in params:
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
    obj: object, default_sec: float = 0.0
) -> tuple[float | None, float | None]:
    """Extract ``(time_sec, delay_sec)`` from a cue timing ``OBJ``."""
    if not isinstance(obj, list) or len(obj) < 4:
        return None, None
    t_ms = obj[2]
    d_ms = obj[3]
    t_sec = float(t_ms) / 1000.0 if isinstance(t_ms, (int, float)) else default_sec
    d_sec = float(d_ms) / 1000.0 if isinstance(d_ms, (int, float)) else 0.0
    return t_sec, d_sec


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

        param_names = parse_param_types(tree[3] if len(tree) > 3 else [])
        personalities = parse_personalities(
            tree[2] if len(tree) > 2 else [], param_names
        )

        # Register FixtureDefinitions directly from tree[2] (no GDTF switch needed)
        data = self.imported.data.data
        fdef_by_guid: dict[str, dict[str, Any]] = {}
        for guid, pers in personalities.items():
            if not pers.is_dimmer:
                fdef_dict = build_olc_fixture_definition(pers).to_dict()
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
        data: dict[str, Any],
    ) -> None:
        cuelist_labels: dict[int, str] = {}
        raw_cues: list[
            tuple[
                int | None,
                float,
                dict[int, dict[int, float]],
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
                seq = data["sequences"].setdefault(
                    cl_id,
                    {"label": cl_label, "mode": "normal", "steps": {}, "cues": {}},
                )
                if cl_label:
                    seq["label"] = cl_label
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

                if isinstance(item[22], list):
                    for channels, ch_obj in _iter_eos_channel_blocks(item[22]):
                        raw_p = _parse_eos_channel_params(ch_obj, channels[0])
                        if raw_p:
                            for ch in channels:
                                raw_p_by_ch[ch] = raw_p

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
                    _extract_ms_time(item[19][5])
                    if isinstance(item[19], list) and len(item[19]) > 5
                    else (None, None)
                )
                t_col, d_col = (
                    _extract_ms_time(item[19][6])
                    if isinstance(item[19], list) and len(item[19]) > 6
                    else (None, None)
                )
                t_bm, d_bm = (
                    _extract_ms_time(item[19][7])
                    if isinstance(item[19], list) and len(item[19]) > 7
                    else (None, None)
                )

                cue_dict: dict[str, Any] = {
                    "number": cue_num,
                    "label": label,
                    "channels": {},
                    "device_values": {},
                }
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
                raw_cues.append(
                    (explicit_cl, cue_num, raw_p_by_ch, cue_dict, step_dict)
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
                    cat = _classify_palette_category(raw_by_ch, param_names)
                    data.setdefault("palettes", {}).setdefault(cat.value, {})[
                        pal_num
                    ] = {
                        "category": cat.value,
                        "number": pal_num,
                        "label": label,
                        "channels": pal_channels,
                        "device_values": pal_dev_vals,
                    }

        # Route cues into their Cue Lists without collisions
        cues_by_list: dict[
            int,
            list[
                tuple[
                    float,
                    dict[int, dict[int, float]],
                    dict[str, Any],
                    dict[str, Any],
                ]
            ],
        ] = {}
        explicit_nums_in_cl1: set[float] = set()
        for explicit_cl, cue_num, raw_p_by_ch, cue_dict, step_dict in raw_cues:
            if explicit_cl is not None:
                cues_by_list.setdefault(explicit_cl, []).append(
                    (cue_num, raw_p_by_ch, cue_dict, step_dict)
                )
                if explicit_cl == 1:
                    explicit_nums_in_cl1.add(cue_num)

        fallback_cl = max(cuelist_labels) if len(cuelist_labels) > 1 else 1
        for explicit_cl, cue_num, raw_p_by_ch, cue_dict, step_dict in raw_cues:
            if explicit_cl is None:
                target_cl = fallback_cl if cue_num in explicit_nums_in_cl1 else 1
                cues_by_list.setdefault(target_cl, []).append(
                    (cue_num, raw_p_by_ch, cue_dict, step_dict)
                )

        # Evaluate each Cue List in cue-number order while tracking virtual params
        for cl_id, cl_cues in sorted(cues_by_list.items()):
            seq = data["sequences"].setdefault(
                cl_id,
                {
                    "label": cuelist_labels.get(cl_id, ""),
                    "mode": "normal",
                    "steps": {},
                    "cues": {},
                },
            )
            if cl_id in cuelist_labels and cuelist_labels[cl_id]:
                seq["label"] = cuelist_labels[cl_id]
            cl_cues.sort(key=lambda c: c[0])
            tracked_virtuals: dict[int, dict[int, float]] = {}

            for step_idx, (cue_num, raw_p_by_ch, cue_dict, step_dict) in enumerate(
                cl_cues, 1
            ):
                cue_channels: dict[int, float] = {}
                device_values: dict[int, dict[str, Any]] = {}
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
                cue_dict["channels"] = cue_channels
                cue_dict["device_values"] = device_values
                seq["cues"][cue_num] = cue_dict
                seq["steps"][step_idx] = step_dict
