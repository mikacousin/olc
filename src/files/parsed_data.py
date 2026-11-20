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
from __future__ import annotations

import typing

from olc.controllers.midi import Midi
from olc.define import MAX_FADER_PER_PAGE
from olc.devices.device import LightingDevice
from olc.devices.fixture import FixtureDefinition
from olc.files.import_types import Action
from olc.show.channel_time import ChannelTime
from olc.show.cue import Cue
from olc.show.curve import InterpolateCurve, LimitCurve, SegmentsCurve
from olc.show.effect import deserialize_effect_refs
from olc.show.fader import LEGACY_FADER_TYPE_GROUP, FaderType
from olc.show.group import Group
from olc.show.independent import IndependentType
from olc.show.palette import PaletteCategory, deserialize_palette_refs
from olc.show.sequence import Sequence
from olc.show.step import Step

if typing.TYPE_CHECKING:
    from olc.show.lightshow import LightShow


class ParsedData:
    """To store imported information"""

    patch: dict[int, list]
    sequence: dict
    data: dict
    lightshow: LightShow
    midi: Midi | None

    def __init__(self, lightshow: LightShow, midi: Midi | None = None) -> None:
        self.lightshow = lightshow
        self.midi = midi
        self.data = {
            "console": {"console": "", "manufacturer": ""},
            "curves": {},
            "fixture_definitions": [],
            "devices": {},
            "patch": {},
            "sequences": {1: {"label": "", "mode": "normal", "steps": {}, "cues": {}}},
            "groups": {},
            "palettes": {},
            "effects": [],
            "independents": {},
            "cues": {},
            "faders": {},
            "midi": {},
            "universes": {},
            "workspace": {},
        }

    def clean(self) -> None:
        """Remove useless data and migrate legacy groups/faders to Groups/Presets."""
        # Remove Sequences without cue
        keys = []
        for sequence, values in self.data["sequences"].items():
            if not values.get("cues"):
                keys.append(sequence)
        for key in keys:
            self.data["sequences"].pop(key)

        faders_data = self.data.get("faders") or {}
        referenced_legacy_groups: set[float] = {
            float(values["contents"])
            for values in faders_data.values()
            if values.get("type") == LEGACY_FADER_TYPE_GROUP
            and isinstance(values.get("contents"), (int, float))
        }

        presets_dict: dict[typing.Any, typing.Any] | None = None

        for group_number, grp in (self.data.get("groups") or {}).items():
            raw_chans = grp.get("channels")
            if isinstance(raw_chans, dict):
                raw_levels: typing.Any = raw_chans
                grp["channels"] = list(
                    dict.fromkeys(int(ch) for ch in raw_levels.keys())
                )
            else:
                raw_levels = grp.pop("legacy_levels", None)
                grp["channels"] = list(
                    dict.fromkeys(int(ch) for ch in (raw_chans or []))
                )

            if (isinstance(raw_levels, dict) and raw_levels) or (
                float(group_number) in referenced_legacy_groups
            ):
                norm_levels = (
                    self._normalize_channels_dict(raw_levels)
                    if isinstance(raw_levels, dict)
                    else {}
                )
                if presets_dict is None:
                    presets_dict = self.data.setdefault("palettes", {}).setdefault(
                        PaletteCategory.PRESET.value, {}
                    )
                p_num = float(group_number)
                if p_num not in presets_dict:
                    presets_dict[p_num] = {
                        "category": PaletteCategory.PRESET.value,
                        "number": p_num,
                        "label": grp.get("label") or str(group_number),
                        "channels": norm_levels,
                    }

        if not faders_data:
            return

        preset_num = 1.0
        for values in faders_data.values():
            raw_type = values.get("type")
            if raw_type == LEGACY_FADER_TYPE_GROUP:
                values["type"] = FaderType.PRESET
            elif raw_type == FaderType.CHANNELS:
                if presets_dict is None:
                    presets_dict = self.data.setdefault("palettes", {}).setdefault(
                        PaletteCategory.PRESET.value, {}
                    )
                while preset_num in presets_dict:
                    preset_num += 1.0
                norm_levels = self._normalize_channels_dict(values.get("contents"))
                label = values.get("label") or f"Preset {int(preset_num)}"
                presets_dict[preset_num] = {
                    "category": PaletteCategory.PRESET.value,
                    "number": preset_num,
                    "label": label,
                    "channels": norm_levels,
                }
                values["type"] = FaderType.PRESET
                values["contents"] = preset_num
                preset_num += 1.0
            elif isinstance(raw_type, int) and not isinstance(raw_type, FaderType):
                try:
                    values["type"] = FaderType(raw_type)
                except ValueError:
                    values["type"] = FaderType.NONE

    def import_midi(self) -> None:
        """Import MIDI mapping"""
        if not self.data["midi"] or not self.midi:
            return

        if isinstance(self.midi, Midi):
            self.midi.from_dict(self.data["midi"])
        else:
            Midi.from_dict(self.midi, self.data["midi"])

    @staticmethod
    def _create_curve_from_dict(
        values: dict,
    ) -> LimitCurve | SegmentsCurve | InterpolateCurve | None:
        """Create a curve instance from serialized dictionary."""
        curve_type = values.get("type")
        if curve_type == "LimitCurve":
            limit_val = values["limit"]
            limit_int = (
                int(round(limit_val * 255.0))
                if isinstance(limit_val, float) and 0.0 <= limit_val <= 1.0
                else int(limit_val)
            )
            return LimitCurve(limit=limit_int)
        if curve_type == "SegmentsCurve":
            curve: SegmentsCurve | InterpolateCurve = SegmentsCurve()
        elif curve_type == "InterpolateCurve":
            curve = InterpolateCurve()
        else:
            return None

        points = values.get("points", [])
        is_norm = values.get("normalized", False) or any(
            isinstance(p[0], float) and 0.0 < p[0] < 1.0 for p in points
        )
        for point in points:
            if is_norm:
                curve.add_normalized_point(float(point[0]), float(point[1]))
            else:
                curve.add_point(int(round(point[0])), int(round(point[1])))
        return curve

    def import_curves(self) -> None:
        """Import curves data"""
        if not self.data["curves"]:
            return
        for curve_nb, values in self.data["curves"].items():
            curve = self._create_curve_from_dict(values)
            if not curve:
                continue
            self.lightshow.curves.curves[curve_nb] = curve
            label = values.get("label")
            if label:
                curve.name = label

    def import_fixture_definitions(self) -> None:
        """Import embedded fixture definitions into lightshow.fixture_library."""
        fdefs = self.data.get("fixture_definitions")
        if not fdefs or not hasattr(self.lightshow, "fixture_library"):
            return
        for fdef_dict in fdefs:
            if isinstance(fdef_dict, dict):
                fdef = FixtureDefinition.from_dict(fdef_dict)
                self.lightshow.fixture_library.register(fdef)

    def import_patch(self) -> None:
        """Import data patch and lighting devices."""
        self.import_fixture_definitions()
        devices_data = self.data.get("devices")
        imported_dev_ids: set[int] = set()
        if devices_data:
            for dev_id, dev_dict in devices_data.items():
                if not isinstance(dev_dict, dict):
                    continue
                device = LightingDevice.from_dict(dev_dict)
                if (
                    device.color_profile is None
                    and device.manufacturer
                    and device.model
                    and hasattr(self.lightshow, "fixture_library")
                ):
                    fdef = self.lightshow.fixture_library.get_by_key(
                        f"{device.manufacturer}:{device.model}"
                    )
                    if fdef is not None and fdef.color_profile is not None:
                        device.color_profile = fdef.color_profile
                self.lightshow.patch.restore_device(device)
                imported_dev_ids.add(int(dev_id))
            self.lightshow.patch.invalidate_cache()

        for channel, values in self.data["patch"].items():
            if int(channel) in imported_dev_ids:
                continue
            for out in values:
                output = out["output"]
                universe = out["universe"]
                curve_nb = out.get("curve", 0)
                self.lightshow.patch.add_output(channel, output, universe, curve_nb)

    def _normalize_channels_dict(
        self, channels: dict[typing.Any, typing.Any] | None
    ) -> dict[int, float]:
        """Convert channel levels dict to normalized [0.0..1.0] floats."""
        if not channels:
            return {}
        is_norm = bool(self.data.get("normalized_levels", True))
        return {
            int(ch): max(
                0.0,
                min(1.0, float(lvl) if is_norm else float(lvl) / 255.0),
            )
            for ch, lvl in channels.items()
        }

    def import_groups(self) -> None:
        """Import groups data as ordered pure channel selections."""
        if not self.data.get("groups"):
            return
        for group_number, values in self.data["groups"].items():
            raw_channels = values.get("channels")
            if isinstance(raw_channels, dict):
                channels = list(dict.fromkeys(int(ch) for ch in raw_channels.keys()))
            elif isinstance(raw_channels, (list, tuple, set)):
                channels = list(dict.fromkeys(int(ch) for ch in raw_channels))
            else:
                channels = []
            label = values.get("label") or ""
            group = self.lightshow.groups.get(group_number)
            if group is not None:
                group.set_text(label)
                group.set_channels(channels)
            else:
                # Create new group
                self.lightshow.groups.add(Group(group_number, channels, label))

    def import_palettes(self) -> None:
        """Import IFCB Palettes and Presets data."""
        palettes_data = self.data.get("palettes")
        if not palettes_data or not hasattr(self.lightshow, "palettes"):
            return
        self.lightshow.palettes.from_dict(palettes_data, clear=False)

    def import_effects(self) -> None:
        """Import procedural Effects data."""
        effects_data = self.data.get("effects")
        if not effects_data or not hasattr(self.lightshow, "effects"):
            return
        self.lightshow.effects.from_list(effects_data)

    def import_faders(self, actions: dict[str, typing.Any]) -> None:
        """Import faders data

        Args:
            actions: Imported action
        """
        if not self.data["faders"]:
            return
        for values in self.data["faders"].values():
            page = values.get("page")
            number = values.get("number")
            fader_type = values.get("type")
            contents = values.get("contents")
            # Don't create fader for non imported elements
            if (
                fader_type == FaderType.SEQUENCE
                and actions["sequences"].get(contents) is Action.IGNORE
            ):
                continue
            if (
                fader_type == FaderType.PRESET
                and actions.get("palettes", Action.REPLACE) is Action.IGNORE
                and actions["sequences"].get(1) is Action.IGNORE
            ):
                continue
            if (
                fader_type == FaderType.EFFECT
                and actions.get("effects", Action.REPLACE) is Action.IGNORE
            ):
                continue
            if number <= MAX_FADER_PER_PAGE:
                self.lightshow.fader_bank.set_fader(page, number, fader_type, contents)
                if fader_type == FaderType.EFFECT:
                    fader_obj = self.lightshow.fader_bank.faders[page][number]
                    eff_chs = values.get("effect_channels")
                    if isinstance(eff_chs, list) and hasattr(
                        fader_obj, "effect_channels"
                    ):
                        fader_obj.effect_channels = [int(c) for c in eff_chs]
                        if hasattr(fader_obj, "update_channels"):
                            fader_obj.update_channels()
                    ctrl_mode = values.get("control_mode")
                    if ctrl_mode in ("size", "rate") and hasattr(
                        fader_obj, "control_mode"
                    ):
                        fader_obj.control_mode = str(ctrl_mode)

    def import_independents(self) -> None:
        """Import independents data"""
        for inde_number, values in self.data["independents"].items():
            channels = self._normalize_channels_dict(values.get("channels"))
            label = values.get("label")
            inde_type = IndependentType(values.get("type", "knob"))
            for inde in self.lightshow.independents.independents:
                if inde_number == inde.number:
                    inde.text = label
                    inde.levels = channels
                    inde.inde_type = inde_type
                    self.lightshow.independents.update(inde)
                    break

    @staticmethod
    def _apply_cue_metadata(cue: Cue, cue_dict: dict[str, typing.Any]) -> None:
        """Apply device_values and is_block metadata to a cue."""
        dev_vals = cue_dict.get("device_values")
        if dev_vals:
            cue.device_values = {
                int(k): {str(pk): pv for pk, pv in v.items()}
                for k, v in dev_vals.items()
            }
        else:
            cue.device_values = {}
        cue.palette_refs = deserialize_palette_refs(cue_dict.get("palette_refs"))
        cue.effect_refs = deserialize_effect_refs(cue_dict.get("effect_refs"))
        cue.is_block = bool(cue_dict.get("is_block", False))

    @staticmethod
    def _build_step_from_dict(
        sequence: int, cue: Cue, values: dict[str, typing.Any]
    ) -> Step:
        """Construct a Step from parsed dictionary values including IFCB times."""
        channel_time = {}
        ct_dict = values.get("channel_time")
        if isinstance(ct_dict, dict):
            for channel, times in ct_dict.items():
                channel_time[channel] = ChannelTime(
                    times.get("delay", 0.0), times.get("time", 0.0)
                )
        return Step(
            sequence,
            cue,
            time_in=float(values.get("time_in", 5.0)),
            time_out=float(values.get("time_out", 5.0)),
            delay_in=float(values.get("delay_in", 0.0)),
            delay_out=float(values.get("delay_out", 0.0)),
            wait=float(values.get("wait", 0.0)),
            channel_time=channel_time,
            text=str(values.get("label", "")),
            time_position=values.get("time_position"),
            delay_position=values.get("delay_position"),
            time_color=values.get("time_color"),
            delay_color=values.get("delay_color"),
            time_beam=values.get("time_beam"),
            delay_beam=values.get("delay_beam"),
        )

    @staticmethod
    def _update_step_timings_from_dict(
        step: Step, values: dict[str, typing.Any]
    ) -> None:
        """Update fade timings, delays, channel times, and IFCB times on a step."""
        if "time_in" in values:
            step.time_in = float(values["time_in"])
        if "time_out" in values:
            step.time_out = float(values["time_out"])
        if "delay_in" in values:
            step.delay_in = float(values["delay_in"])
        if "delay_out" in values:
            step.delay_out = float(values["delay_out"])
        if "wait" in values:
            step.wait = float(values["wait"])
        if "channel_time" in values:
            channel_time: dict[int, ChannelTime] = {}
            ct_dict = values["channel_time"]
            if isinstance(ct_dict, dict):
                for channel, times in ct_dict.items():
                    channel_time[int(channel)] = ChannelTime(
                        times.get("delay", 0.0), times.get("time", 0.0)
                    )
            step.channel_time = channel_time
        ParsedData._update_step_ifcb_timings_from_dict(step, values)

    @staticmethod
    def _update_step_ifcb_timings_from_dict(
        step: Step, values: dict[str, typing.Any]
    ) -> None:
        """Update IFCB discrete fade and delay times on a step."""
        if "time_position" in values:
            step.time_position = values["time_position"]
        if "delay_position" in values:
            step.delay_position = values["delay_position"]
        if "time_color" in values:
            step.time_color = values["time_color"]
        if "delay_color" in values:
            step.delay_color = values["delay_color"]
        if "time_beam" in values:
            step.time_beam = values["time_beam"]
        if "delay_beam" in values:
            step.delay_beam = values["delay_beam"]

    def import_presets(self) -> None:
        """Import presets data"""
        for preset_number, values in self.data["cues"].items():
            channels = self._normalize_channels_dict(values.get("channels"))
            label = values.get("label")
            cue = self.lightshow.cues.get(preset_number, 0)
            if cue is not None:
                cue.channels = channels
                cue.text = label
            else:
                cue = Cue(0, preset_number, channels, label)
                self.lightshow.cues.add(cue)
                self.lightshow.main_playback.update_channels()
            self._apply_cue_metadata(cue, values)

    def import_main_playback(self, sequence: int, action: Action) -> None:
        """Import Main Playback

        Args:
            sequence: Sequence number (Main Playback is always 1)
            action: Action type
        """
        if action is Action.REPLACE:
            self._replace_main_playback(sequence)
        elif action is Action.MERGE:
            self._merge_main_playback(sequence)

    def _replace_main_playback(self, sequence: int) -> None:
        seq_data = self.data["sequences"][sequence]
        self.lightshow.main_playback.tracking_mode = bool(
            seq_data.get("tracking_mode", False)
        )
        self.lightshow.main_playback.mib_enabled = bool(
            seq_data.get("mib_enabled", True)
        )
        self.lightshow.main_playback.mib_fade_time = float(
            seq_data.get("mib_fade_time", 2.0)
        )
        for values in seq_data["steps"].values():
            cue_number = values.get("cue")
            cue_dict = seq_data["cues"][cue_number]
            cue_channels = self._normalize_channels_dict(cue_dict["channels"])
            cue_text = cue_dict["label"]
            cue = self.lightshow.cues.get(cue_number, 0)
            if cue is not None:
                # If cue exist, update it
                cue.channels = cue_channels
                cue.text = cue_text
            else:
                # Else, create it
                cue = Cue(0, cue_number, cue_channels, text=cue_text)
                self.lightshow.cues.add(cue)
            self._apply_cue_metadata(cue, cue_dict)
            step = self._build_step_from_dict(sequence, cue, values)
            self.lightshow.main_playback.add_step(step)

    def _merge_main_playback(self, sequence: int) -> None:
        seq_data = self.data["sequences"][sequence]
        if "tracking_mode" in seq_data:
            self.lightshow.main_playback.tracking_mode = bool(seq_data["tracking_mode"])
        if "mib_enabled" in seq_data:
            self.lightshow.main_playback.mib_enabled = bool(seq_data["mib_enabled"])
        if "mib_fade_time" in seq_data:
            self.lightshow.main_playback.mib_fade_time = float(
                seq_data["mib_fade_time"]
            )
        sentinel_step = (
            self.lightshow.main_playback.steps.pop()
            if len(self.lightshow.main_playback.steps) > 1
            else None
        )
        for values in seq_data["steps"].values():
            cue_number = values.get("cue")
            cue_dict = seq_data["cues"][cue_number]
            cue_channels = self._normalize_channels_dict(cue_dict["channels"])
            cue_text = cue_dict["label"]
            existing_idx = next(
                (
                    idx
                    for idx, s in enumerate(self.lightshow.main_playback.steps)
                    if s.cue is not None and s.cue.number == cue_number
                ),
                None,
            )
            if existing_idx is not None:
                # If cue exist, update it
                existing_step = self.lightshow.main_playback.steps[existing_idx]
                cue = existing_step.cue
                if cue:
                    cue.channels = cue_channels
                    cue.text = cue_text
                    self._apply_cue_metadata(cue, cue_dict)
                existing_step.text = values.get("label", existing_step.text)
                self._update_step_timings_from_dict(existing_step, values)
            else:
                _found, step_nb = self.lightshow.main_playback.get_step(cue_number)
                cue = Cue(0, cue_number, cue_channels, text=cue_text)
                self.lightshow.cues.add(cue)
                self.lightshow.main_playback.update_channels()
                self._apply_cue_metadata(cue, cue_dict)
                step = self._build_step_from_dict(sequence, cue, values)
                self.lightshow.main_playback.insert_step(step_nb, step)
        if sentinel_step is not None:
            self.lightshow.main_playback.steps.append(sentinel_step)
            self.lightshow.main_playback.last = len(self.lightshow.main_playback.steps)

    def import_chaser(self, sequence: int, action: Action) -> None:
        """Import Chaser

        Args:
            sequence: Sequence number
            action: Action type
        """
        seq_data = self.data["sequences"][sequence]
        label = seq_data["label"]
        type_seq = "Chaser" if seq_data.get("mode") == "chaser" else "Normal"
        for index, chsr in enumerate(self.lightshow.chasers):
            if chsr.index == sequence:
                self.lightshow.chasers[index].text = label
                self.lightshow.chasers[index].type_seq = type_seq
                break
        else:
            self.lightshow.chasers.append(
                Sequence(
                    sequence,
                    type_seq=type_seq,
                    text=label,
                    lightshow=self.lightshow,
                )
            )
            index = -1
            del self.lightshow.chasers[index].steps[1:]
        if "tracking_mode" in seq_data or action is Action.REPLACE:
            self.lightshow.chasers[index].tracking_mode = bool(
                seq_data.get("tracking_mode", False)
            )
        if "mib_enabled" in seq_data or action is Action.REPLACE:
            self.lightshow.chasers[index].mib_enabled = bool(
                seq_data.get("mib_enabled", True)
            )
        if "mib_fade_time" in seq_data or action is Action.REPLACE:
            self.lightshow.chasers[index].mib_fade_time = float(
                seq_data.get("mib_fade_time", 2.0)
            )
        if action is Action.REPLACE:
            self._replace_chaser(sequence, index)
        elif action is Action.MERGE:
            self._merge_chaser(sequence, index)

    def _merge_chaser(self, sequence: int, index: int) -> None:
        for values in self.data["sequences"][sequence]["steps"].values():
            cue_number = values.get("cue")
            cue_dict = self.data["sequences"][sequence]["cues"][cue_number]
            cue_channels = self._normalize_channels_dict(cue_dict["channels"])
            cue_text = cue_dict["label"]
            chaser_seq = self.lightshow.chasers[index]
            existing_idx = next(
                (
                    idx
                    for idx, s in enumerate(chaser_seq.steps)
                    if s.cue is not None and s.cue.number == cue_number
                ),
                None,
            )
            if existing_idx is not None:
                existing_step = chaser_seq.steps[existing_idx]
                cue = existing_step.cue
                if cue:
                    cue.channels = cue_channels
                    cue.text = cue_text
                    self._apply_cue_metadata(cue, cue_dict)
                existing_step.text = values.get("label", existing_step.text)
                self._update_step_timings_from_dict(existing_step, values)
            else:
                _found, step_nb = chaser_seq.get_step(cue_number)
                cue = Cue(sequence, cue_number, cue_channels, text=cue_text)
                chaser_seq.cues.add(cue)
                self._apply_cue_metadata(cue, cue_dict)
                step = self._build_step_from_dict(sequence, cue, values)
                chaser_seq.insert_step(step_nb, step)

    def _replace_chaser(self, sequence: int, index: int) -> None:
        for values in self.data["sequences"][sequence]["steps"].values():
            cue_number = values.get("cue")
            cue_dict = self.data["sequences"][sequence]["cues"][cue_number]
            cue_channels = self._normalize_channels_dict(cue_dict["channels"])
            cue_text = cue_dict["label"]
            for cue in self.lightshow.chasers[index].cues:
                if cue.number == cue_number:
                    # If cue exist, update it
                    cue.channels = cue_channels
                    cue.text = cue_text
                    self._apply_cue_metadata(cue, cue_dict)
                    break
            else:
                # Else, create it
                cue = Cue(sequence, cue_number, cue_channels, text=cue_text)
                self.lightshow.chasers[index].cues.add(cue)
                self._apply_cue_metadata(cue, cue_dict)
            step = self._build_step_from_dict(sequence, cue, values)
            self.lightshow.chasers[index].add_step(step)
