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

import json
import pathlib
import typing

from olc.controllers.midi import Midi
from olc.define import MAX_FADER_PAGE
from olc.files.write import WriteFile
from olc.show.curve import LimitCurve, PointsCurve
from olc.show.effect import serialize_effect_refs
from olc.show.fader import FaderType
from olc.show.palette import serialize_palette_refs

if typing.TYPE_CHECKING:
    from olc.show.lightshow import LightShow
    from olc.show.sequence import Sequence


class OlcWriter(WriteFile):
    """Write olc file"""

    data: dict[str, typing.Any]
    midi: Midi | None

    def __init__(
        self,
        file: pathlib.Path | str | typing.Any,  # noqa: ANN401
        lightshow: LightShow,
        midi: Midi | None = None,
    ) -> None:
        super().__init__(file, lightshow, compressed=True)
        self.lightshow = lightshow
        self.midi = midi
        self.data = {}
        self.data = {
            "application": "olc",
            "version": "0.8.5.beta",
            "normalized_levels": True,
        }

    def export(self) -> None:
        self._show_metadata()
        self._curves()
        self._fixture_definitions()
        self._devices()
        self._sequences()
        self._groups()
        self._palettes()
        self._effects()
        self._faders()
        self._independents()
        self._midi()
        self._universes()
        self._workspace()
        self._park()

        json_str = json.dumps(self.data, indent=2, ensure_ascii=False, sort_keys=False)

        if self.stream:
            self.stream.write(bytes(json_str, "utf-8"))

    def _show_metadata(self) -> None:
        title = getattr(self.lightshow, "title", "")
        home_preset = getattr(self.lightshow, "home_preset", None)
        fader_bank = getattr(self.lightshow, "fader_bank", None)
        fader_pages = getattr(fader_bank, "max_fader_page", MAX_FADER_PAGE)
        skip_empty = bool(getattr(fader_bank, "skip_empty_pages", False))
        meta: dict[str, typing.Any] = {}
        if title:
            meta["title"] = str(title)
        if home_preset is not None:
            meta["home_preset"] = float(home_preset)
        if fader_pages != MAX_FADER_PAGE:
            meta["fader_pages"] = int(fader_pages)
        if skip_empty:
            meta["skip_empty_fader_pages"] = True
        if meta:
            self.data["show_metadata"] = meta

    def _fixture_definitions(self) -> None:
        if not hasattr(self.lightshow, "fixture_library"):
            return
        defs = [fdef.to_dict() for fdef in self.lightshow.fixture_library.all()]
        if defs:
            self.data["fixture_definitions"] = defs

    def _devices(self) -> None:
        if not self.lightshow.patch.devices:
            return
        self.data["devices"] = {
            dev_id: dev.to_dict()
            for dev_id, dev in self.lightshow.patch.devices.items()
        }

    def _sequences(self) -> None:
        self.data["sequences"] = {}
        self._do_sequence(self.lightshow.main_playback)
        for seq in self.lightshow.sequences:
            self._do_sequence(seq)

    def _do_sequence(self, sequence: Sequence) -> None:
        seq_index = sequence.index
        seq_entry: dict[str, typing.Any] = {
            "label": sequence.text,
            "tracking_mode": bool(getattr(sequence, "tracking_mode", False)),
            "mib_enabled": bool(getattr(sequence, "mib_enabled", True)),
            "mib_fade_time": float(getattr(sequence, "mib_fade_time", 2.0)),
            "steps": {},
            "cues": {},
        }
        if hasattr(sequence, "playback_options_to_dict"):
            seq_entry.update(sequence.playback_options_to_dict())
        self.data["sequences"][seq_index] = seq_entry
        for index, step in enumerate(sequence.steps):
            if not step.cue or step.cue.number == 0:
                continue
            self.data["sequences"][seq_index]["steps"][index] = {
                "cue": step.cue.number,
                "time_in": step.time_in,
                "time_out": step.time_out,
            }
            if step.delay_in:
                self.data["sequences"][seq_index]["steps"][index]["delay_in"] = (
                    step.delay_in
                )
            if step.delay_out:
                self.data["sequences"][seq_index]["steps"][index]["delay_out"] = (
                    step.delay_out
                )
            if step.wait:
                self.data["sequences"][seq_index]["steps"][index]["wait"] = step.wait
            for ifcb_attr in (
                "time_position",
                "delay_position",
                "time_color",
                "delay_color",
                "time_beam",
                "delay_beam",
            ):
                ifcb_val = getattr(step, ifcb_attr, None)
                if ifcb_val is not None:
                    self.data["sequences"][seq_index]["steps"][index][ifcb_attr] = (
                        ifcb_val
                    )
            if step.channel_time:
                self.data["sequences"][seq_index]["steps"][index]["channel_time"] = {}
                for channel, times in step.channel_time.items():
                    self.data["sequences"][seq_index]["steps"][index]["channel_time"][
                        channel
                    ] = {"delay": times.delay, "time": times.time}
            if step.text:
                self.data["sequences"][seq_index]["steps"][index]["label"] = step.text
            cue_dict = self._build_cue_dict(step.cue)
            self.data["sequences"][seq_index]["cues"][step.cue.number] = cue_dict

    @staticmethod
    def _build_cue_dict(cue: typing.Any) -> dict[str, typing.Any]:  # noqa: ANN401
        cue_dict: dict[str, typing.Any] = {
            "label": cue.text,
            "channels": cue.channels,
        }
        if cue.device_values:
            cue_dict["device_values"] = cue.device_values
        if cue.palette_refs:
            cue_dict["palette_refs"] = serialize_palette_refs(cue.palette_refs)
        if getattr(cue, "effect_refs", None):
            cue_dict["effect_refs"] = serialize_effect_refs(cue.effect_refs)
        if cue.is_block:
            cue_dict["is_block"] = cue.is_block
        if getattr(cue, "is_assert", False):
            cue_dict["is_assert"] = True
        if getattr(cue, "is_int_block", False):
            cue_dict["is_int_block"] = True
        if notes := getattr(cue, "notes", ""):
            cue_dict["notes"] = notes
        if (exec_preset := getattr(cue, "execute_preset", None)) is not None:
            cue_dict["execute_preset"] = float(exec_preset)
        return cue_dict

    def _palettes(self) -> None:
        if not hasattr(self.lightshow, "palettes") or len(self.lightshow.palettes) == 0:
            return
        self.data["palettes"] = self.lightshow.palettes.to_dict()

    def _effects(self) -> None:
        if not hasattr(self.lightshow, "effects") or len(self.lightshow.effects) == 0:
            return
        self.data["effects"] = self.lightshow.effects.to_list()

    def _groups(self) -> None:
        self.data["groups"] = {}
        for group in self.lightshow.groups:
            self.data["groups"][group.index] = {
                "label": group.text,
                "channels": group.get_channels(),
            }
        if not self.data["groups"]:
            del self.data["groups"]

    def _faders(self) -> None:
        self.data["faders"] = {}
        for page, faders in self.lightshow.fader_bank.faders.items():
            for index, fader in faders.items():
                content_type = self.lightshow.fader_bank.get_fader_type(page, index)
                number = index - 1 + ((page - 1) * 10)
                if content_type == FaderType.SEQUENCE:
                    contents_val = (
                        fader.contents.index if fader.contents is not None else None
                    )
                    self.data["faders"][number] = {
                        "page": page,
                        "number": index,
                        "type": int(content_type),
                        "contents": contents_val,
                        "text": fader.text,
                    }
                elif content_type == FaderType.PRESET:
                    contents_val = (
                        fader.contents.number if fader.contents is not None else None
                    )
                    preset_entry: dict[str, typing.Any] = {
                        "page": page,
                        "number": index,
                        "type": int(content_type),
                        "contents": contents_val,
                        "text": fader.text,
                    }
                    if getattr(fader, "intensity_master", False):
                        preset_entry["intensity_master"] = True
                    self.data["faders"][number] = preset_entry
                elif content_type == FaderType.CHANNELS:
                    ch_contents = getattr(fader, "contents", None)
                    self.data["faders"][number] = {
                        "page": page,
                        "number": index,
                        "type": int(content_type),
                        "contents": (
                            dict(ch_contents) if isinstance(ch_contents, dict) else None
                        ),
                        "text": fader.text,
                    }
                elif content_type == FaderType.EFFECT:
                    contents_val = (
                        fader.contents.number if fader.contents is not None else None
                    )
                    fader_entry: dict[str, typing.Any] = {
                        "page": page,
                        "number": index,
                        "type": int(content_type),
                        "contents": contents_val,
                        "text": fader.text,
                    }
                    eff_chs = getattr(fader, "effect_channels", None)
                    if eff_chs:
                        fader_entry["effect_channels"] = list(eff_chs)
                    ctrl_mode = getattr(fader, "control_mode", "size")
                    if ctrl_mode and ctrl_mode != "size":
                        fader_entry["control_mode"] = ctrl_mode
                    base_chs = getattr(fader, "base_channels", None)
                    if base_chs:
                        fader_entry["base_channels"] = dict(base_chs)
                    if getattr(fader, "modifier_only", False):
                        fader_entry["modifier_only"] = True
                        fader_entry["min_scale"] = float(
                            getattr(fader, "min_scale", 0.0)
                        )
                        fader_entry["max_scale"] = float(
                            getattr(fader, "max_scale", 4.0)
                        )
                        fader_entry["level"] = float(getattr(fader, "level", 0.5))
                    self.data["faders"][number] = fader_entry
                elif content_type == FaderType.FX_MASTER:
                    self.data["faders"][number] = {
                        "page": page,
                        "number": index,
                        "type": int(content_type),
                        "text": fader.text,
                        "master_kind": getattr(fader, "master_kind", "speed"),
                        "master_id": int(getattr(fader, "master_id", 1)),
                        "level": float(getattr(fader, "level", 0.5)),
                    }
                elif content_type == FaderType.MAIN:
                    self.data["faders"][number] = {
                        "page": page,
                        "number": index,
                        "type": int(content_type),
                        "text": fader.text,
                    }
                if number in self.data["faders"]:
                    if getattr(fader, "exempt_grand_master", False):
                        self.data["faders"][number]["exempt_grand_master"] = True
                    for flag in (
                        "exclude_record",
                        "inhibitive",
                        "solo_mode",
                        "swop_protect",
                        "locked",
                    ):
                        if getattr(fader, flag, False):
                            self.data["faders"][number][flag] = True
                    if getattr(fader, "inhibitive", False):
                        self.data["faders"][number]["level"] = float(fader.level)
                    if self.lightshow.fader_bank.is_fader_fixed(page, index):
                        self.data["faders"][number]["fixed"] = True
        if not self.data["faders"]:
            del self.data["faders"]

    def _independents(self) -> None:
        self.data["independents"] = {}
        for inde in self.lightshow.independents.independents:
            self.data["independents"][inde.number] = {
                "type": inde.inde_type,
                "label": inde.text,
                "channels": inde.levels,
            }

    def _curves(self) -> None:
        self.data["curves"] = {}
        for key, curve in self.lightshow.curves.curves.items():
            if key >= 10:
                curve_type = curve.__class__.__name__
                if isinstance(curve, LimitCurve):
                    self.data["curves"][key] = {
                        "type": curve_type,
                        "limit": curve.limit,
                        "label": curve.name,
                    }
                elif isinstance(curve, PointsCurve):
                    self.data["curves"][key] = {
                        "type": curve_type,
                        "points": curve.points,
                        "label": curve.name,
                    }
        if not self.data["curves"]:
            del self.data["curves"]

    def _midi(self) -> None:
        if not self.midi:
            return

        if isinstance(self.midi, Midi):
            self.data["midi_mapping"] = self.midi.to_dict()
        else:
            self.data["midi_mapping"] = Midi.to_dict(self.midi)

    def _universes(self) -> None:
        universe_map = getattr(self.lightshow, "universe_map", None)
        if universe_map is None:
            return

        self.data["universes"] = {}
        for config in universe_map:
            u = config.universe_id
            # We only serialize configured universes (like 1 to 4)
            if u == 0:
                continue
            protocols = [p.name for p in config.protocols]
            self.data["universes"][str(u)] = {
                "protocols": protocols,
                "artnet": {
                    "net": config.artnet.net,
                    "sub": config.artnet.sub,
                    "sync_active": config.artnet.sync_active,
                },
                "sacn": {
                    "priority": config.sacn.priority,
                    "sync_address": config.sacn.sync_address,
                },
                "dmx_usb_pro": {
                    "port": config.dmx_usb_pro.port,
                    "port_index": config.dmx_usb_pro.port_index,
                    "model": config.dmx_usb_pro.model,
                },
            }

    def _workspace(self) -> None:
        workspace = getattr(self.lightshow, "workspace", None)
        if workspace:
            self.data["workspace"] = workspace

    def _park(self) -> None:
        park = getattr(self.lightshow, "park", None)
        if park is not None:
            park_data = park.to_dict()
            if park_data.get("channels") or park_data.get("addresses"):
                self.data["park"] = park_data
