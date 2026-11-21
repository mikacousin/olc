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

import pathlib
import typing
from collections.abc import Mapping

from olc.define import UNIVERSES, strip_accents
from olc.files.write import WriteFile
from olc.show.curve import LimitCurve
from olc.show.effect import DistributeDirection, EffectMode, WaveformType
from olc.show.fader import FaderType

if typing.TYPE_CHECKING:
    from olc.show.effect import EffectDefinition
    from olc.show.lightshow import LightShow
    from olc.show.palette import PaletteRef

_OLC_PARAM_TO_EOS: dict[str, tuple[int, int, str]] = {
    "intensity": (1, 0, "Intens"),
    "pan": (2, 1, "Pan"),
    "tilt": (3, 1, "Tilt"),
    "color": (12, 2, "Red"),
    "zoom": (15, 3, "Zoom"),
    "focus": (16, 3, "Edge"),
    "strobe": (21, 3, "Shutter_Strobe"),
    "color_temp": (22, 2, "Color_Temperature"),
}

_PALETTE_CAT_TO_EOS_PREFIX: dict[str, str] = {
    "intensity": "IP",
    "focus": "FP",
    "color": "CP",
    "beam": "BP",
    "preset": "PR",
}


class AsciiWriter(WriteFile):
    """Write ASCII Light Cue file"""

    def __init__(
        self,
        file: pathlib.Path | str | typing.Any,  # noqa: ANN401
        lightshow: LightShow,
    ) -> None:
        super().__init__(file, lightshow)

        self.lightshow = lightshow

    def export(self) -> None:
        self._header()
        self._effects()
        self._main_playback()
        self._sequences()
        self._groups()
        self._masters()
        self._patch()
        self._independents()
        self._end()

    def _header(self) -> None:
        if self.stream is None:
            return
        self.stream.write(bytes("IDENT 3:0\n", "ascii"))
        self.stream.write(bytes("MANUFACTURER MIKA\n", "ascii"))
        self.stream.write(bytes("CONSOLE OLC\n\n", "ascii"))
        self.stream.write(bytes("CLEAR ALL\n\n", "ascii"))

    def _main_playback(self) -> None:
        if self.stream is None:
            return
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii")
        )
        self.stream.write(bytes("! Main sequence\n\n", "ascii"))
        self.stream.write(bytes("$SEQUENCE 1 0\n\n", "ascii"))
        for step in self.lightshow.main_playback.steps:
            if not step.cue or step.cue.number == 0:
                continue
            self.stream.write(bytes(f"CUE {step.cue.number}\n", "ascii"))
            # Save integers as integers
            time_out = self._float_to_str(step.time_out)
            delay_out = self._float_to_str(step.delay_out)
            time_in = self._float_to_str(step.time_in)
            delay_in = self._float_to_str(step.delay_in)
            wait = self._float_to_str(step.wait)
            self.stream.write(bytes(f"DOWN {time_out} {delay_out}\n", "ascii"))
            self.stream.write(bytes(f"UP {time_in} {delay_in}\n", "ascii"))
            self.stream.write(bytes(f"$$WAIT {wait}\n", "ascii"))
            # ChannelTime
            for chan in step.channel_time.keys():
                delay = self._float_to_str(step.channel_time[chan].delay)
                time = self._float_to_str(step.channel_time[chan].time)
                self.stream.write(bytes(f"$$PARTTIME {delay} {time}\n", "ascii"))
                self.stream.write(bytes(f"$$PARTTIMECHAN {chan}\n", "ascii"))
            self._ascii_text(step.text)
            self.stream.write(bytes(f"$$TEXT {step.text}\n", "utf8"))
            self._save_channels(step.cue.channels)
            self._save_effect_refs(step.cue.effect_refs)
            self.stream.write(bytes("\n", "ascii"))

    def _effects(self) -> None:
        if self.stream is None or not hasattr(self.lightshow, "effects"):
            return
        effects = self.lightshow.effects.all()
        if not effects:
            return
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii")
        )
        self.stream.write(bytes("! Effects\n\n", "ascii"))

        used_params: dict[int, tuple[int, str]] = {}
        for eff in effects:
            for layer in eff.layers:
                info = _OLC_PARAM_TO_EOS.get(layer.parameter)
                if info is not None and info[0] != 1:
                    used_params[info[0]] = (info[1], info[2])
        for p_id in sorted(used_params):
            p_cat, p_name = used_params[p_id]
            self.stream.write(bytes(f"$PARAMTYPE {p_id} {p_cat} {p_name}\n", "ascii"))
        if used_params:
            self.stream.write(bytes("\n", "ascii"))

        for eff in effects:
            self._write_single_effect(eff)

    def _write_single_effect(self, eff: EffectDefinition) -> None:
        if self.stream is None:
            return
        self.stream.write(bytes(f"$EFFECT {self._float_to_str(eff.number)}\n", "ascii"))
        if eff.label:
            self._ascii_text(eff.label)
            self.stream.write(bytes(f"$$TEXT {eff.label}\n", "utf8"))

        layer_params = [layer.parameter for layer in eff.layers]
        first = eff.layers[0] if eff.layers else None
        if len(eff.layers) >= 2 and "pan" in layer_params and "tilt" in layer_params:
            self.stream.write(bytes("$$TYPE 2\n", "ascii"))
            self.stream.write(bytes("$$PARAMLIST 2 3\n", "ascii"))
            self.stream.write(
                bytes(f"$$SCALE {self._float_to_str(eff.layers[0].size)}\n", "ascii")
            )
        elif (
            first is not None
            and first.parameter == "color"
            and first.waveform == WaveformType.RAINBOW
        ):
            self.stream.write(bytes("$$TYPE 3\n", "ascii"))
            self.stream.write(bytes("$$PARAMLIST 12 13 14\n", "ascii"))
        elif first is not None and first.mode == EffectMode.ABSOLUTE:
            p_id = _OLC_PARAM_TO_EOS.get(first.parameter, (1, 0, "Intens"))[0]
            self.stream.write(bytes("$$TYPE 4\n", "ascii"))
            self.stream.write(bytes(f"$$PARAMLIST {p_id}\n", "ascii"))
            span1 = max(0.01, eff.cycle_time * first.duty_cycle)
            span2 = max(0.01, eff.cycle_time * (1.0 - first.duty_cycle))
            if first.softness <= 0.1:
                t1, d1, t2, d2 = 0.0, span1, 0.0, span2
            else:
                t1, d1, t2, d2 = span1, 0.0, span2, 0.0
            tok1 = self._format_effect_action_token(first.low_palette, first.low_value)
            tok2 = self._format_effect_action_token(
                first.high_palette, first.high_value
            )
            self.stream.write(bytes(f"$$ACTION 1 {t1:.3f} {d1:.3f} {tok1}\n", "ascii"))
            self.stream.write(bytes(f"$$ACTION 2 {t2:.3f} {d2:.3f} {tok2}\n", "ascii"))
        else:
            p_id = (
                _OLC_PARAM_TO_EOS.get(first.parameter, (1, 0, "Intens"))[0]
                if first is not None
                else 1
            )
            scale = first.size if first is not None else 50.0
            self.stream.write(bytes("$$TYPE 1\n", "ascii"))
            self.stream.write(bytes(f"$$PARAMLIST {p_id}\n", "ascii"))
            self.stream.write(bytes(f"$$SCALE {self._float_to_str(scale)}\n", "ascii"))
            if first is not None and first.waveform in (
                WaveformType.SAW_UP,
                WaveformType.SAW_DOWN,
            ):
                for step_i in range(8):
                    val = step_i / 7.0
                    if first.waveform == WaveformType.SAW_DOWN:
                        val = 1.0 - val
                    self.stream.write(
                        bytes(f"$$DATA {step_i + 1} {val:.4f}\n", "ascii")
                    )

        self.stream.write(bytes(f"$$GROUPING {eff.groups}\n", "ascii"))
        if eff.direction == DistributeDirection.RANDOM:
            self.stream.write(bytes("$$COMMAND 1562\n", "ascii"))
        self.stream.write(bytes("\n", "ascii"))

    def _format_effect_action_token(
        self,
        palette_ref: PaletteRef | None,
        value: float | str | None,
    ) -> str:
        """Format an Eos $$ACTION target token from a palette ref or numeric bound."""
        if palette_ref is not None:
            prefix = _PALETTE_CAT_TO_EOS_PREFIX.get(str(palette_ref[0]).strip().lower())
            if prefix:
                return f"{prefix}{self._float_to_str(float(palette_ref[1]))}"
        if isinstance(value, (int, float)):
            return self._float_to_str(float(value))
        return "Bkgrd"

    def _save_effect_refs(
        self, effect_refs: Mapping[int, dict[str, typing.Any]]
    ) -> None:
        """Write $$EFFECTCHAN and $$EFFECTDATA lines for cue effect references."""
        if self.stream is None or not effect_refs:
            return
        stopped_chans: list[int] = []
        by_fx: dict[float, tuple[list[tuple[int, int]], dict[str, typing.Any]]] = {}
        for ch_raw, spec in effect_refs.items():
            if not isinstance(spec, dict):
                continue
            ch = int(ch_raw)
            if spec.get("stop"):
                stopped_chans.append(ch)
                continue
            fx_num = spec.get("effect")
            if fx_num is None:
                fx_num = spec.get("effect_number")
            if fx_num is None:
                continue
            fx_id = float(fx_num)
            order_idx = int(spec.get("order_index", spec.get("selection_index", 0)))
            if fx_id not in by_fx:
                by_fx[fx_id] = ([], spec)
            by_fx[fx_id][0].append((order_idx, ch))

        for ch in sorted(stopped_chans):
            self.stream.write(bytes(f"$$EFFECTCHAN 0 {ch} 1\n", "ascii"))

        for fx_id in sorted(by_fx):
            indexed_chans, spec = by_fx[fx_id]
            indexed_chans.sort(key=lambda item: (item[0], item[1]))
            fx_str = self._float_to_str(fx_id)
            for _order, ch in indexed_chans:
                self.stream.write(bytes(f"$$EFFECTCHAN {fx_str} {ch} 1\n", "ascii"))
            rate_scale = float(spec.get("rate_scale", 1.0))
            if abs(rate_scale - 1.0) > 1e-4:
                pct = self._float_to_str(round(rate_scale * 100.0, 3))
                self.stream.write(bytes(f"$$EFFECTDATA {fx_str} RATE {pct}\n", "ascii"))
            size_scale = float(spec.get("size_scale", 1.0))
            if abs(size_scale - 1.0) > 1e-4:
                pct = self._float_to_str(round(size_scale * 100.0, 3))
                self.stream.write(bytes(f"$$EFFECTDATA {fx_str} SIZE {pct}\n", "ascii"))

    def _sequences(self) -> None:
        if self.stream is None:
            return
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii")
        )
        self.stream.write(bytes("! Additional Sequences\n\n", "ascii"))
        for seq in self.lightshow.sequences:
            self.stream.write(bytes(f"$SEQUENCE {seq.index}\n", "ascii"))
            self._ascii_text(seq.text)
            self.stream.write(bytes(f"$$TEXT {seq.text}\n\n", "utf8"))
            for step in seq.steps:
                if not step.cue or step.cue.number == 0:
                    continue
                # Save integers as integers
                time_out = self._float_to_str(step.time_out)
                delay_out = self._float_to_str(step.delay_out)
                time_in = self._float_to_str(step.time_in)
                delay_in = self._float_to_str(step.delay_in)
                wait = self._float_to_str(step.wait)
                self.stream.write(
                    bytes(f"$CUE {seq.index} {step.cue.number}\n", "ascii")
                )
                self.stream.write(bytes(f"DOWN {time_out} {delay_out}\n", "ascii"))
                self.stream.write(bytes(f"UP {time_in} {delay_in}\n", "ascii"))
                self.stream.write(bytes(f"$$WAIT {wait}\n", "ascii"))
                if step.text:
                    self._ascii_text(step.text)
                    self.stream.write(bytes(f"$$TEXT {step.text}\n", "utf8"))
                self._save_channels(step.cue.channels)
                self._save_effect_refs(step.cue.effect_refs)
                self.stream.write(bytes("\n", "ascii"))

    def _groups(self) -> None:
        if self.stream is None:
            return
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii")
        )
        self.stream.write(bytes("! Groups (channel selections)\n", "ascii"))
        self.stream.write(bytes("! $GROUP     Group number\n", "ascii"))
        self.stream.write(bytes("! TEXT       Standard ASCII Light Cues\n", "ascii"))
        self.stream.write(
            bytes("! $$TEXT     Unicode encoded version of the same text\n", "ascii")
        )
        self.stream.write(bytes("! $$CHANLIST Ordered channel numbers\n", "ascii"))
        self.stream.write(bytes("CLEAR $GROUP\n\n", "ascii"))
        for group in self.lightshow.groups:
            self.stream.write(bytes(f"$GROUP {group.index}\n", "ascii"))
            self._ascii_text(group.text)
            self.stream.write(bytes(f"$$TEXT {group.text}\n", "utf8"))
            self._save_channel_list(group.get_channels())
            self.stream.write(bytes("\n", "ascii"))

    def _masters(self) -> None:
        if self.stream is None:
            return
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii")
        )
        self.stream.write(bytes("! Master Pages\n", "ascii"))
        self.stream.write(bytes("! $MASTPAGE     Master page number\n", "ascii"))
        self.stream.write(bytes("! TEXT          Master page text\n", "ascii"))
        self.stream.write(
            bytes("! $TEXT         Unicode encoded version of the same text\n", "ascii")
        )
        self.stream.write(
            bytes("! $MASTPAGEITEM Page number, Master number,\n", "ascii")
        )
        self.stream.write(
            bytes("!               Content type (1=Preset, 2=Channels,\n", "ascii")
        )
        self.stream.write(
            bytes("!               3=Sequence, 4=Effect, 99=Main Fader),\n", "ascii")
        )
        self.stream.write(
            bytes(
                "!               Content value (Preset#, Sequence#, Effect#),\n",
                "ascii",
            )
        )
        self.stream.write(
            bytes("!               Time In, Wait time, Time Out,\n", "ascii")
        )
        self.stream.write(bytes("!               Flash level (0-255)\n", "ascii"))
        self.stream.write(bytes("CLEAR $MASTPAGE\n", "ascii"))
        for page, faders in self.lightshow.fader_bank.faders.items():
            self.stream.write(bytes(f"\n$MASTPAGE {page} 0 0 0\n", "ascii"))
            for index, fader in faders.items():
                contents = "0"
                content_type = self.lightshow.fader_bank.get_fader_type(page, index)
                if content_type == FaderType.SEQUENCE and fader.contents is not None:
                    contents = str(fader.contents.index)
                elif content_type == FaderType.PRESET and fader.contents is not None:
                    contents = self._float_to_str(fader.contents.number)
                elif content_type == FaderType.EFFECT and fader.contents is not None:
                    contents = self._float_to_str(fader.contents.number)
                if content_type not in (FaderType.NONE, FaderType.MAIN):
                    self.stream.write(
                        bytes(
                            f"$MASTPAGEITEM {page} {index} {int(content_type)} "
                            f"{contents} 5 0 5 255\n",
                            "ascii",
                        )
                    )
                    if content_type == FaderType.EFFECT:
                        if eff_chs := getattr(fader, "effect_channels", []):
                            self._save_channel_list(list(eff_chs))
                        ctrl_mode = getattr(fader, "control_mode", "size")
                        if ctrl_mode in ("rate", "both"):
                            self.stream.write(
                                bytes(f"$$EFFECTMODE {ctrl_mode}\n", "ascii")
                            )
        self.stream.write(bytes("\n", "ascii"))

    def _patch(self) -> None:
        if self.stream is None:
            return
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii")
        )
        self.stream.write(bytes("! Patch\n", "ascii"))
        self.stream.write(bytes("CLEAR PATCH\n\n", "ascii"))
        i = 1
        patch = ""
        for channel, dev in self.lightshow.patch.devices.items():
            if not dev.channels:
                continue
            for ch in dev.channels:
                if ch.channel_type.value != "intensity" or ch.fine or ch.ultra_fine:
                    continue
                output = ch.address
                univ = ch.universe
                index = UNIVERSES.index(univ)
                limit = 255
                curve = self.lightshow.curves.get_curve(dev.curve_id)
                if isinstance(curve, LimitCurve):
                    limit = curve.limit
                level = "H" + format(limit, "02X")
                patch += f" {channel}<{output + 512 * index}@{level}"
                if not i % 4 and patch != "":
                    self.stream.write(bytes(f"PATCH 1{patch}\n", "ascii"))
                    patch = ""
                i += 1
        if patch != "":
            self.stream.write(bytes(f"PATCH 1{patch}\n", "ascii"))
        self.stream.write(bytes("\n", "ascii"))

    def _independents(self) -> None:
        if self.stream is None:
            return
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii")
        )
        self.stream.write(bytes("! Independents\n\n", "ascii"))
        for inde in self.lightshow.independents.independents:
            self.stream.write(bytes(f"$SPECIALFUNCTION {inde.number} 0 0\n", "ascii"))
            self._ascii_text(inde.text)
            self.stream.write(bytes(f"$$TEXT {inde.text}\n", "utf8"))
            self._save_channels(inde.levels)
            self.stream.write(bytes("\n", "utf8"))

    def _end(self) -> None:
        if self.stream is None:
            return
        self.stream.write(bytes("ENDDATA\n", "ascii"))

    def _save_channel_list(self, chans: list[int]) -> None:
        """Save ordered group channel list using $$CHANLIST.

        Args:
            chans: Ordered list of channel numbers.
        """
        if self.stream is None or not chans:
            return
        for i in range(0, len(chans), 10):
            chunk = " ".join(str(int(ch)) for ch in chans[i : i + 10])
            self.stream.write(bytes(f"$$CHANLIST {chunk}\n", "ascii"))

    def _save_channels(self, chans: Mapping[int, int | float]) -> None:
        """Save channels

        Args:
            chans: Channels and Levels
        """
        if self.stream is None:
            return
        channels = ""
        i = 1
        for chan, level in chans.items():
            if level != 0:
                lvl = "H" + format(int(round(level)), "02X")
                channels += f" {chan}/{lvl}"
                # 6 Channels per line
                if not i % 6 and channels != "":
                    self.stream.write(bytes(f"CHAN{channels}\n", "ascii"))
                    channels = ""
                i += 1
        if channels != "":
            self.stream.write(bytes(f"CHAN{channels}\n", "ascii"))

    def _ascii_text(self, text: str) -> None:
        """Convert string to ASCII and write it to file

        Args:
            text: Text to write
        """
        if self.stream is None:
            return
        self.stream.write(
            bytes(f"TEXT {strip_accents(text)}\n", "utf8")
            .decode("utf8")
            .encode("ascii")
        )

    def _float_to_str(self, number: float) -> str:
        val = float(number)
        return str(int(val)) if val.is_integer() else str(val)
