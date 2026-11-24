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


class PaletteMode(str, Enum):
    """Scope/resolution mode for a Palette or Preset."""

    SELECTIVE = "selective"
    BY_TYPE = "by_type"
    UNIVERSAL = "universal"


def default_mode_for_category(category: PaletteCategory | str) -> PaletteMode:
    """Return the default recording mode for a given palette category."""
    cat = (
        category
        if isinstance(category, PaletteCategory)
        else PaletteCategory(str(category).lower())
    )
    if cat in (PaletteCategory.FOCUS, PaletteCategory.PRESET):
        return PaletteMode.SELECTIVE
    return PaletteMode.BY_TYPE


def get_channel_type_key(lightshow: LightShow | None, channel: int) -> str | None:
    """Return the fixture ``type_key`` for *channel* in *lightshow*, if patched."""
    if lightshow is None:
        return None
    patch = getattr(lightshow, "patch", None)
    devices = getattr(patch, "devices", None) if patch is not None else None
    if not isinstance(devices, dict):
        return None
    dev = devices.get(int(channel))
    if dev is None:
        return None
    return getattr(dev, "type_key", None)


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
    mode: PaletteMode = PaletteMode.SELECTIVE
    locked: bool = False
    by_type_channels: dict[str, float] = field(default_factory=dict)
    by_type_values: dict[str, dict[str, typing.Any]] = field(default_factory=dict)
    universal_intensity: float | None = None
    universal_values: dict[str, typing.Any] = field(default_factory=dict)

    def resolve_intensity(
        self, channel: int, type_key: str | None = None
    ) -> float | None:
        """Resolve intensity for *channel* (Selective > By-Type > Universal)."""
        ch = int(channel)
        if ch in self.channels:
            return float(self.channels[ch])
        if type_key and type_key in self.by_type_channels:
            return float(self.by_type_channels[type_key])
        if self.universal_intensity is not None:
            return float(self.universal_intensity)
        return None

    def resolve_device_values(
        self, channel: int, type_key: str | None = None
    ) -> dict[str, typing.Any]:
        """Resolve device attributes for *channel* (Selective > By-Type > Universal)."""
        resolved: dict[str, typing.Any] = {}
        if self.universal_values:
            for pk, pv in self.universal_values.items():
                resolved[pk] = copy.deepcopy(pv)
        if type_key and type_key in self.by_type_values:
            for pk, pv in self.by_type_values[type_key].items():
                resolved[pk] = copy.deepcopy(pv)
        ch = int(channel)
        if ch in self.device_values:
            for pk, pv in self.device_values[ch].items():
                resolved[pk] = copy.deepcopy(pv)
        return resolved

    def resolve_channel(
        self, channel: int, type_key: str | None = None
    ) -> tuple[float | None, dict[str, typing.Any]]:
        """Return ``(intensity, device_values)`` resolved for *channel*."""
        return (
            self.resolve_intensity(channel, type_key),
            self.resolve_device_values(channel, type_key),
        )

    def has_data_for_channel(self, channel: int, type_key: str | None = None) -> bool:
        """Return True if any layer (Selective, By-Type, or Universal) applies."""
        ch = int(channel)
        if ch in self.channels or ch in self.device_values:
            return True
        if type_key and (
            type_key in self.by_type_channels or type_key in self.by_type_values
        ):
            return True
        return self.universal_intensity is not None or bool(self.universal_values)

    def to_dict(self) -> dict[str, typing.Any]:
        """Serialize palette or preset into a JSON-compatible dictionary."""
        data: dict[str, typing.Any] = {
            "category": self.category.value,
            "number": float(self.number),
            "label": self.text,
        }
        if self.mode is not PaletteMode.SELECTIVE:
            data["mode"] = self.mode.value
        if self.locked:
            data["locked"] = True
        if self.channels:
            data["channels"] = {int(k): float(v) for k, v in self.channels.items()}
        if self.device_values:
            data["device_values"] = {
                int(k): copy.deepcopy(v) for k, v in self.device_values.items()
            }
        if self.by_type_channels:
            data["by_type_channels"] = {
                str(k): float(v) for k, v in self.by_type_channels.items()
            }
        if self.by_type_values:
            data["by_type_values"] = {
                str(k): copy.deepcopy(v) for k, v in self.by_type_values.items()
            }
        if self.universal_intensity is not None:
            data["universal_intensity"] = float(self.universal_intensity)
        if self.universal_values:
            data["universal_values"] = copy.deepcopy(self.universal_values)
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
        raw_mode = data.get("mode", PaletteMode.SELECTIVE.value)
        try:
            mode = (
                raw_mode
                if isinstance(raw_mode, PaletteMode)
                else PaletteMode(str(raw_mode).lower())
            )
        except ValueError:
            mode = PaletteMode.SELECTIVE
        locked = bool(data.get("locked", False))
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
        raw_bt_ch = data.get("by_type_channels") or {}
        by_type_channels: dict[str, float] = {
            str(k): float(v) for k, v in raw_bt_ch.items()
        }
        raw_bt_val = data.get("by_type_values") or {}
        by_type_values: dict[str, dict[str, typing.Any]] = {
            str(k): {str(pk): copy.deepcopy(pv) for pk, pv in v.items()}
            for k, v in raw_bt_val.items()
            if isinstance(v, dict)
        }
        raw_univ_int = data.get("universal_intensity")
        universal_intensity = float(raw_univ_int) if raw_univ_int is not None else None
        raw_univ_val = data.get("universal_values") or {}
        universal_values: dict[str, typing.Any] = (
            {str(pk): copy.deepcopy(pv) for pk, pv in raw_univ_val.items()}
            if isinstance(raw_univ_val, dict)
            else {}
        )
        palette_refs = deserialize_palette_refs(data.get("palette_refs"))
        return cls(
            category=category,
            number=number,
            text=label,
            channels=channels,
            device_values=device_values,
            palette_refs=palette_refs,
            mode=mode,
            locked=locked,
            by_type_channels=by_type_channels,
            by_type_values=by_type_values,
            universal_intensity=universal_intensity,
            universal_values=universal_values,
        )


def _apply_palette_param_to_target(
    source: Palette,
    channel: int,
    param_name: str,
    target_channels: typing.MutableMapping[int, typing.Any],
    target_device_values: dict[int, dict[str, typing.Any]],
    type_key: str | None = None,
) -> bool:
    """Copy referenced parameter(s) for *channel* from *source* to target dicts."""
    changed = False
    resolved_int = source.resolve_intensity(channel, type_key)
    resolved_devs = source.resolve_device_values(channel, type_key)

    if param_name == "*":
        if resolved_int is not None:
            new_lvl = float(resolved_int)
            if target_channels.get(channel) != new_lvl:
                target_channels[channel] = new_lvl
                changed = True
        if resolved_devs:
            dst_devs = target_device_values.setdefault(channel, {})
            for pk, pv in resolved_devs.items():
                copied = copy.deepcopy(pv)
                if dst_devs.get(pk) != copied:
                    dst_devs[pk] = copied
                    changed = True
        return changed

    if param_name == "intensity":
        lvl: float | None = resolved_int
        if lvl is None:
            dev_int = resolved_devs.get("intensity")
            if isinstance(dev_int, (int, float)):
                lvl = float(dev_int)
        if lvl is not None:
            if target_channels.get(channel) != float(lvl):
                target_channels[channel] = float(lvl)
                changed = True
            if "intensity" in resolved_devs:
                dst_devs = target_device_values.setdefault(channel, {})
                if dst_devs.get("intensity") != resolved_devs["intensity"]:
                    dst_devs["intensity"] = copy.deepcopy(resolved_devs["intensity"])
                    changed = True
        return changed

    if param_name in resolved_devs:
        copied = copy.deepcopy(resolved_devs[param_name])
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

    def from_dict(
        self,
        data: dict[typing.Any, typing.Any] | None,
        *,
        clear: bool = True,
    ) -> None:
        """Populate palettes from a serialized mapping, optionally clearing first."""
        if clear:
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
            return {"presets": 0, "cues": 0, "faders": 0, "effects": 0}

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
                                type_key=get_channel_type_key(lightshow, ch),
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
        updated_effects = self._refresh_effects(lightshow, sources_by_key)

        return {
            "presets": len(updated_presets),
            "cues": updated_cues_count,
            "faders": updated_faders,
            "effects": updated_effects,
        }

    @staticmethod
    def _collect_unique_cues(lightshow: LightShow) -> list[Cue]:
        """Collect all unique Cue instances across all sequences."""
        return list(lightshow.iter_all_cues())

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
                        type_key=get_channel_type_key(lightshow, ch),
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

    @staticmethod
    def _refresh_effects(
        lightshow: LightShow,
        sources_by_key: dict[tuple[str, float], Palette],
    ) -> int:
        """Count effects referencing updated palettes and tick engine if live."""
        if not sources_by_key or not hasattr(lightshow, "effects"):
            return 0
        affected_numbers: set[float] = set()
        for eff in lightshow.effects.all():
            for layer in eff.layers:
                for ref in (layer.low_palette, layer.high_palette):
                    if ref is None:
                        continue
                    key = (str(ref[0]).strip().lower(), float(ref[1]))
                    if key in sources_by_key:
                        affected_numbers.add(float(eff.number))
                        break
                if float(eff.number) in affected_numbers:
                    break
        if affected_numbers:
            app = getattr(lightshow, "app", None)
            engine = getattr(app, "effects_engine", None)
            if engine is not None and hasattr(engine, "get_active_instances"):
                active = engine.get_active_instances()
                if any(
                    float(inst.effect_number) in affected_numbers for inst in active
                ):
                    engine.tick()
        return len(affected_numbers)
