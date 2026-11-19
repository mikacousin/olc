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
"""Palette and Preset data structures with cascade propagation."""

from __future__ import annotations

import copy
import typing
from dataclasses import dataclass, field
from enum import Enum

if typing.TYPE_CHECKING:
    from olc.show.cue import Cue
    from olc.show.lightshow import LightShow

PaletteRef = tuple[str, float]


class PaletteCategory(str, Enum):
    """Supported IFCB palette categories plus multi-attribute Presets."""

    INTENSITY = "intensity"
    FOCUS = "focus"
    COLOR = "color"
    BEAM = "beam"
    PRESET = "preset"


def serialize_palette_refs(
    refs: dict[int, dict[str, PaletteRef]],
) -> dict[int, dict[str, list[typing.Any]]]:
    """Serialize palette_refs mapping to JSON-friendly nested dictionaries."""
    result: dict[int, dict[str, list[typing.Any]]] = {}
    for ch, param_map in refs.items():
        if not param_map:
            continue
        result[int(ch)] = {
            str(param): [str(ref[0]), float(ref[1])] for param, ref in param_map.items()
        }
    return result


def deserialize_palette_refs(
    raw: typing.Any,  # noqa: ANN401
) -> dict[int, dict[str, PaletteRef]]:
    """Deserialize JSON palette_refs payload into typed integer-keyed mappings."""
    if not isinstance(raw, dict):
        return {}
    result: dict[int, dict[str, PaletteRef]] = {}
    for ch_key, param_map in raw.items():
        if not isinstance(param_map, dict):
            continue
        try:
            ch = int(ch_key)
        except (TypeError, ValueError):
            continue
        parsed_params: dict[str, PaletteRef] = {}
        for param_name, ref_pair in param_map.items():
            if isinstance(ref_pair, (list, tuple)) and len(ref_pair) >= 2:
                try:
                    parsed_params[str(param_name)] = (
                        str(ref_pair[0]),
                        float(ref_pair[1]),
                    )
                except (TypeError, ValueError):
                    continue
        if parsed_params:
            result[ch] = parsed_params
    return result


@dataclass
class Palette:
    """Reusable intensity, focus, color, beam palette, or multi-attribute Preset."""

    category: PaletteCategory
    number: float
    text: str = ""
    channels: dict[int, float] = field(default_factory=dict)
    device_values: dict[int, dict[str, typing.Any]] = field(default_factory=dict)
    palette_refs: dict[int, dict[str, PaletteRef]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, typing.Any]:
        """Serialize palette or preset into a JSON-compatible dictionary."""
        data: dict[str, typing.Any] = {
            "category": self.category.value,
            "number": float(self.number),
            "label": self.text,
        }
        if self.channels:
            data["channels"] = {int(k): float(v) for k, v in self.channels.items()}
        if self.device_values:
            data["device_values"] = {
                int(k): copy.deepcopy(v) for k, v in self.device_values.items()
            }
        if self.palette_refs:
            data["palette_refs"] = serialize_palette_refs(self.palette_refs)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> Palette:
        """Deserialize palette or preset from a dictionary."""
        raw_cat = data.get("category", PaletteCategory.COLOR.value)
        category = (
            raw_cat
            if isinstance(raw_cat, PaletteCategory)
            else PaletteCategory(str(raw_cat))
        )
        number = float(data["number"])
        label = str(data.get("label", data.get("text", "")))
        raw_channels = data.get("channels") or {}
        channels: dict[int, float] = {int(k): float(v) for k, v in raw_channels.items()}
        raw_dev = data.get("device_values") or {}
        device_values: dict[int, dict[str, typing.Any]] = {
            int(k): {str(pk): copy.deepcopy(pv) for pk, pv in v.items()}
            for k, v in raw_dev.items()
            if isinstance(v, dict)
        }
        palette_refs = deserialize_palette_refs(data.get("palette_refs"))
        return cls(
            category=category,
            number=number,
            text=label,
            channels=channels,
            device_values=device_values,
            palette_refs=palette_refs,
        )


def _apply_palette_param_to_target(
    source: Palette,
    channel: int,
    param_name: str,
    target_channels: typing.MutableMapping[int, typing.Any],
    target_device_values: dict[int, dict[str, typing.Any]],
) -> bool:
    """Copy referenced parameter(s) for *channel* from *source* to target dicts."""
    changed = False
    if param_name == "*":
        if channel in source.channels:
            new_lvl = float(source.channels[channel])
            if target_channels.get(channel) != new_lvl:
                target_channels[channel] = new_lvl
                changed = True
        if channel in source.device_values:
            src_devs = source.device_values[channel]
            dst_devs = target_device_values.setdefault(channel, {})
            for pk, pv in src_devs.items():
                copied = copy.deepcopy(pv)
                if dst_devs.get(pk) != copied:
                    dst_devs[pk] = copied
                    changed = True
        return changed

    if param_name == "intensity":
        lvl: float | None = source.channels.get(channel)
        if lvl is None and channel in source.device_values:
            dev_int = source.device_values[channel].get("intensity")
            if isinstance(dev_int, (int, float)):
                lvl = float(dev_int)
        if lvl is not None:
            if target_channels.get(channel) != float(lvl):
                target_channels[channel] = float(lvl)
                changed = True
            src_devs = source.device_values.get(channel, {})
            if "intensity" in src_devs:
                dst_devs = target_device_values.setdefault(channel, {})
                if dst_devs.get("intensity") != src_devs["intensity"]:
                    dst_devs["intensity"] = copy.deepcopy(src_devs["intensity"])
                    changed = True
        return changed

    src_devs = source.device_values.get(channel, {})
    if param_name in src_devs:
        copied = copy.deepcopy(src_devs[param_name])
        dst_devs = target_device_values.setdefault(channel, {})
        if dst_devs.get(param_name) != copied:
            dst_devs[param_name] = copied
            changed = True
    return changed


class PaletteManager:
    """Container and cascade propagation manager for IFCB Palettes and Presets."""

    def __init__(self) -> None:
        self._palettes: dict[tuple[PaletteCategory, float], Palette] = {}

    @staticmethod
    def _normalize_category(category: PaletteCategory | str) -> PaletteCategory:
        if isinstance(category, PaletteCategory):
            return category
        return PaletteCategory(str(category).lower())

    def add(self, palette: Palette) -> None:
        """Store or overwrite a palette keyed by (category, number)."""
        self._palettes[(palette.category, float(palette.number))] = palette

    def get(self, category: PaletteCategory | str, number: float) -> Palette | None:
        """Retrieve a palette by category and number, or None."""
        cat = self._normalize_category(category)
        return self._palettes.get((cat, float(number)))

    def delete(self, category: PaletteCategory | str, number: float) -> bool:
        """Remove a palette by category and number; return True if removed."""
        cat = self._normalize_category(category)
        return self._palettes.pop((cat, float(number)), None) is not None

    def list_by_category(self, category: PaletteCategory | str) -> list[Palette]:
        """Return all palettes for *category* sorted by number."""
        cat = self._normalize_category(category)
        items = [p for (c, _num), p in self._palettes.items() if c is cat]
        items.sort(key=lambda p: float(p.number))
        return items

    def all(self) -> list[Palette]:
        """Return all stored palettes sorted by category then number."""
        items = list(self._palettes.values())
        items.sort(key=lambda p: (p.category.value, float(p.number)))
        return items

    def clear(self) -> None:
        """Remove all palettes and presets."""
        self._palettes.clear()

    def __len__(self) -> int:
        return len(self._palettes)

    def __iter__(self) -> typing.Iterator[Palette]:
        return iter(self.all())

    def to_dict(self) -> dict[str, dict[float, dict[str, typing.Any]]]:
        """Serialize all palettes grouped by category value and number."""
        result: dict[str, dict[float, dict[str, typing.Any]]] = {}
        for palette in self.all():
            cat_dict = result.setdefault(palette.category.value, {})
            cat_dict[float(palette.number)] = palette.to_dict()
        return result

    def from_dict(self, data: dict[typing.Any, typing.Any] | None) -> None:
        """Clear and populate palettes from a serialized mapping."""
        self.clear()
        if not isinstance(data, dict):
            return
        for cat_key, entries in data.items():
            if not isinstance(entries, dict):
                continue
            # Support nested {category: {number: palette_dict}}
            if isinstance(cat_key, str) and cat_key in {
                c.value for c in PaletteCategory
            }:
                for num_key, p_data in entries.items():
                    if not isinstance(p_data, dict):
                        continue
                    payload = dict(p_data)
                    payload.setdefault("category", cat_key)
                    payload.setdefault("number", num_key)
                    self.add(Palette.from_dict(payload))
            elif "category" in entries and "number" in entries:
                self.add(Palette.from_dict(entries))

    def propagate_update(
        self,
        lightshow: LightShow,
        category: PaletteCategory | str,
        number: float,
    ) -> dict[str, int]:
        """Cascade updates from an edited palette to Presets, Cues, and Faders."""
        cat = self._normalize_category(category)
        source = self.get(cat, number)
        if source is None:
            return {"presets": 0, "cues": 0, "faders": 0}

        ref_num = float(number)
        updated_presets: list[Palette] = []
        if cat is not PaletteCategory.PRESET:
            for preset in self.list_by_category(PaletteCategory.PRESET):
                if not preset.palette_refs:
                    continue
                preset_changed = False
                for ch, refs in preset.palette_refs.items():
                    for param_name, (r_cat, r_num) in refs.items():
                        if r_cat == cat.value and float(r_num) == ref_num:
                            if _apply_palette_param_to_target(
                                source,
                                ch,
                                param_name,
                                preset.channels,
                                preset.device_values,
                            ):
                                preset_changed = True
                if preset_changed:
                    updated_presets.append(preset)

        sources_by_key: dict[tuple[str, float], Palette] = {
            (cat.value, ref_num): source
        }
        for preset in updated_presets:
            sources_by_key[(PaletteCategory.PRESET.value, float(preset.number))] = (
                preset
            )

        updated_cues_count, updated_cue_objs = self._propagate_to_cues(
            lightshow, sources_by_key
        )
        updated_objects: set[int] = {id(p) for p in updated_presets} | {
            id(c) for c in updated_cue_objs
        }
        updated_faders = self._refresh_faders(lightshow, updated_objects)

        return {
            "presets": len(updated_presets),
            "cues": updated_cues_count,
            "faders": updated_faders,
        }

    @staticmethod
    def _collect_unique_cues(lightshow: LightShow) -> list[Cue]:
        """Collect all unique Cue instances across global cues and sequences."""
        seen: set[int] = set()
        cues: list[Cue] = []
        for cue in lightshow.cues:
            if cue is not None and id(cue) not in seen:
                seen.add(id(cue))
                cues.append(cue)
        sequences = [lightshow.main_playback, *list(lightshow.chasers)]
        for seq in sequences:
            for step in seq.steps:
                cue = getattr(step, "cue", None)
                if cue is not None and id(cue) not in seen:
                    seen.add(id(cue))
                    cues.append(cue)
        return cues

    def _propagate_to_cues(
        self,
        lightshow: LightShow,
        sources_by_key: dict[tuple[str, float], Palette],
    ) -> tuple[int, list[Cue]]:
        """Update all Cues referencing any palette/preset in *sources_by_key*."""
        updated_cues: list[Cue] = []
        for cue in self._collect_unique_cues(lightshow):
            if not cue.palette_refs:
                continue
            cue_changed = False
            for ch, refs in cue.palette_refs.items():
                for param_name, (r_cat, r_num) in refs.items():
                    src_pal = sources_by_key.get((str(r_cat), float(r_num)))
                    if src_pal is None:
                        continue
                    if _apply_palette_param_to_target(
                        src_pal,
                        ch,
                        param_name,
                        cue.channels,
                        cue.device_values,
                    ):
                        cue_changed = True
            if cue_changed:
                updated_cues.append(cue)
        return len(updated_cues), updated_cues

    @staticmethod
    def _refresh_faders(lightshow: LightShow, updated_object_ids: set[int]) -> int:
        """Refresh faders referencing updated Presets or Cues."""
        if not updated_object_ids or not hasattr(lightshow, "fader_bank"):
            return 0
        updated_faders = 0
        for faders in lightshow.fader_bank.faders.values():
            for fader in faders.values():
                contents = getattr(fader, "contents", None)
                if contents is not None and id(contents) in updated_object_ids:
                    if hasattr(fader, "update_channels"):
                        fader.update_channels()
                    if getattr(fader, "level", 0.0) > 0.0 and hasattr(
                        fader, "level_changed"
                    ):
                        fader.level_changed()
                    updated_faders += 1
        return updated_faders
