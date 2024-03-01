# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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

from olc.curve import LimitCurve
from olc.define import UNIVERSES, App, strip_accents
from olc.fader import FaderType
from olc.files.write import WriteFile


class AsciiWriter(WriteFile):
    """Write ASCII Light Cue file"""

    def export(self) -> None:
        self._header()
        self._main_playback()
        self._chasers()
        self._groups()
        self._cobalt_groups()
        self._masters()
        self._patch()
        self._independents()
        self._end()

    def _header(self) -> None:
        self.stream.write(bytes("IDENT 3:0\n", "ascii"))
        self.stream.write(bytes("MANUFACTURER MIKA\n", "ascii"))
        self.stream.write(bytes("CONSOLE OLC\n\n", "ascii"))
        self.stream.write(bytes("CLEAR ALL\n\n", "ascii"))

    def _main_playback(self) -> None:
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii"))
        self.stream.write(bytes("! Main sequence\n\n", "ascii"))
        self.stream.write(bytes("$SEQUENCE 1 0\n\n", "ascii"))
        for step in App().lightshow.main_playback.steps:
            if step.cue.memory == 0:
                continue
            self.stream.write(bytes(f"CUE {step.cue.memory}\n", "ascii"))
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
            self.stream.write(bytes("\n", "ascii"))

    def _chasers(self) -> None:
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii"))
        self.stream.write(bytes("! Additional Sequences\n\n", "ascii"))
        for chaser in App().lightshow.chasers:
            self.stream.write(bytes(f"$SEQUENCE {chaser.index}\n", "ascii"))
            self._ascii_text(chaser.text)
            self.stream.write(bytes(f"$$TEXT {chaser.text}\n\n", "utf8"))
            for step in chaser.steps:
                if step.cue.memory == 0:
                    continue
                # Save integers as integers
                time_out = self._float_to_str(step.time_out)
                delay_out = self._float_to_str(step.delay_out)
                time_in = self._float_to_str(step.time_in)
                delay_in = self._float_to_str(step.delay_in)
                wait = self._float_to_str(step.wait)
                self.stream.write(
                    bytes(f"$CUE {chaser.index} {step.cue.memory}\n", "ascii"))
                self.stream.write(bytes(f"DOWN {time_out} {delay_out}\n", "ascii"))
                self.stream.write(bytes(f"UP {time_in} {delay_in}\n", "ascii"))
                self.stream.write(bytes(f"$$WAIT {wait}\n", "ascii"))
                if step.text:
                    self._ascii_text(step.text)
                    self.stream.write(bytes(f"$$TEXT {step.text}\n", "utf8"))
                self._save_channels(step.cue.channels)
                self.stream.write(bytes("\n", "ascii"))

    def _groups(self) -> None:
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii"))
        self.stream.write(bytes("! Groups (presets not in sequence)\n", "ascii"))
        self.stream.write(bytes("! GROUP  Standard ASCII Light Cues\n", "ascii"))
        self.stream.write(bytes("! CHAN   Standard ASCII Light Cues\n", "ascii"))
        self.stream.write(bytes("! TEXT   Standard ASCII Light Cues\n", "ascii"))
        self.stream.write(
            bytes("! $$TEXT Unicode encoded version of the same text\n\n", "ascii"))
        for group in App().lightshow.groups:
            self.stream.write(bytes(f"GROUP {group.index}\n", "ascii"))
            self._ascii_text(group.text)
            self.stream.write(bytes(f"$$TEXT {group.text}\n", "utf8"))
            self._save_channels(group.channels)
            self.stream.write(bytes("\n", "ascii"))

    def _cobalt_groups(self) -> None:
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii"))
        self.stream.write(bytes("! Congo Groups\n", "ascii"))
        self.stream.write(bytes("! $GROUP  Group number\n", "ascii"))
        self.stream.write(bytes("! CHAN    Standard ASCII Light Cues\n", "ascii"))
        self.stream.write(bytes("! TEXT    Standard ASCII Light Cues\n", "ascii"))
        self.stream.write(
            bytes("! $$TEXT  Unicode encoded version of the same text\n", "ascii"))
        self.stream.write(bytes("CLEAR $GROUP\n\n", "ascii"))
        for group in App().lightshow.groups:
            self.stream.write(bytes(f"$GROUP {group.index}\n", "ascii"))
            self._ascii_text(group.text)
            self.stream.write(bytes(f"$$TEXT {group.text}\n", "utf8"))
            self._save_channels(group.channels)
            self.stream.write(bytes("\n", "ascii"))

    def _masters(self) -> None:
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii"))
        self.stream.write(bytes("! Master Pages\n", "ascii"))
        self.stream.write(bytes("! $MASTPAGE     Master page number\n", "ascii"))
        self.stream.write(bytes("! TEXT          Master page text\n", "ascii"))
        self.stream.write(
            bytes("! $TEXT         Unicode encoded version of the same text\n",
                  "ascii"))
        self.stream.write(
            bytes("! $MASTPAGEITEM Page number, Master number,\n", "ascii"))
        self.stream.write(
            bytes("!               Content type (1=Preset, 2=Channels,\n", "ascii"))
        self.stream.write(
            bytes("!               3=Chaser, 13=Group, 99=Main Fader),\n", "ascii"))
        self.stream.write(
            bytes("!               Content value (Preset#, Chaser#, Group#),\n",
                  "ascii"))
        self.stream.write(
            bytes("!               Time In, Wait time, Time Out,\n", "ascii"))
        self.stream.write(bytes("!               Flash level (0-255)\n", "ascii"))
        self.stream.write(bytes("CLEAR $MASTPAGE\n", "ascii"))
        for page, faders in App().lightshow.fader_bank.faders.items():
            self.stream.write(bytes(f"\n$MASTPAGE {page} 0 0 0\n", "ascii"))
            for index, fader in faders.items():
                content_type = App().lightshow.fader_bank.get_fader_type(page, index)
                if content_type == FaderType.GROUP:
                    contents = self._float_to_str(fader.contents.index)
                elif content_type == FaderType.SEQUENCE:
                    contents = str(fader.contents.index)
                elif content_type == FaderType.PRESET:
                    contents = self._float_to_str(fader.contents.memory)
                if content_type not in (FaderType.NONE, FaderType.MAIN):
                    self.stream.write(
                        bytes(
                            f"$MASTPAGEITEM {page} {index} {content_type} "
                            f"{contents} 5 0 5 255\n", "ascii"))
        self.stream.write(bytes("\n", "ascii"))

    def _patch(self) -> None:
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii"))
        self.stream.write(bytes("! Patch\n", "ascii"))
        self.stream.write(bytes("CLEAR PATCH\n\n", "ascii"))
        i = 1
        patch = ""
        for channel, outputs in App().lightshow.patch.channels.items():
            if not App().lightshow.patch.is_patched(channel):
                continue
            for values in outputs:
                output = values[0]
                univ = values[1]
                index = UNIVERSES.index(univ)
                limit = 255
                curve_num = App().lightshow.patch.outputs[univ][output][1]
                curve = App().lightshow.curves.get_curve(curve_num)
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
        self.stream.write(
            bytes("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n", "ascii"))
        self.stream.write(bytes("! Independents\n\n", "ascii"))
        for inde in App().lightshow.independents.independents:
            self.stream.write(bytes(f"$SPECIALFUNCTION {inde.number} 0 0\n", "ascii"))
            self._ascii_text(inde.text)
            self.stream.write(bytes(f"$$TEXT {inde.text}\n", "utf8"))
            self._save_channels(inde.levels)
            self.stream.write(bytes("\n", "utf8"))

    def _end(self) -> None:
        self.stream.write(bytes("ENDDATA\n", "ascii"))

    def _save_channels(self, chans: dict[int, int]) -> None:
        """Save channels

        Args:
            chans: Channels and Levels
        """
        channels = ""
        i = 1
        for chan, level in chans.items():
            if level != 0:
                lvl = "H" + format(level, "02X")
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
        self.stream.write(
            bytes(f"TEXT {strip_accents(text)}\n",
                  "utf8").decode("utf8").encode("ascii"))

    def _float_to_str(self, number: float) -> str:
        return (str(int(number)) if number.is_integer() else str(number))
