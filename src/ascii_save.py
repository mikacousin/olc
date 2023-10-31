# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2023 Mika Cousin <mika.cousin@gmail.com>
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
from typing import Dict
from gi.repository import Gio
from olc.curve import LimitCurve, SegmentsCurve, InterpolateCurve
from olc.define import App


def save_main_playback(stream: Gio.FileOutputStream) -> None:
    """Save Main Sequence

    Args:
        stream: File
    """
    stream.write(
        bytes(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
            "utf8",
        )
    )
    stream.write(bytes("! Main sequence\n\n", "utf8"))
    stream.write(bytes("$SEQUENCE 1 0\n\n", "utf8"))
    for step in App().sequence.steps:
        if int(step.cue.memory) != 0:
            # Save integers as integers
            time_out = (
                str(int(step.time_out))
                if step.time_out.is_integer()
                else str(step.time_out)
            )
            delay_out = (
                str(int(step.delay_out))
                if step.delay_out.is_integer()
                else str(step.delay_out)
            )
            time_in = (
                str(int(step.time_in))
                if step.time_in.is_integer()
                else str(step.time_in)
            )
            delay_in = (
                str(int(step.delay_in))
                if step.delay_in.is_integer()
                else str(step.delay_in)
            )
            wait = str(int(step.wait)) if step.wait.is_integer() else str(step.wait)
            stream.write(bytes(f"CUE {str(step.cue.memory)}" + "\n", "utf8"))
            stream.write(bytes(f"DOWN {time_out} {delay_out}" + "\n", "utf8"))
            stream.write(bytes(f"UP {time_in} {delay_in}" + "\n", "utf8"))
            stream.write(bytes(f"$$WAIT {wait}" + "\n", "utf8"))
            #  Chanel Time if any
            for chan in step.channel_time.keys():
                delay = (
                    str(int(step.channel_time[chan].delay))
                    if step.channel_time[chan].delay.is_integer()
                    else str(step.channel_time[chan].delay)
                )
                time = (
                    str(int(step.channel_time[chan].time))
                    if step.channel_time[chan].time.is_integer()
                    else str(step.channel_time[chan].time)
                )
                stream.write(bytes(f"$$PARTTIME {delay} {time}" + "\n", "utf8"))
                stream.write(bytes(f"$$PARTTIMECHAN {str(chan)}" + "\n", "utf8"))
            stream.write(bytes(f"TEXT {step.text}" + "\n", "iso-8859-1"))
            stream.write(bytes(f"$$TEXT {ascii(step.text)[1:-1]}" + "\n", "ascii"))
            _save_channels(stream, step.cue.channels)
            stream.write(bytes("\n", "utf8"))


def save_chasers(stream: Gio.FileOutputStream) -> None:
    """Save Chasers

    Args:
        stream: File
    """
    stream.write(bytes("! Additional Sequences\n\n", "utf8"))

    for chaser in App().chasers:
        stream.write(bytes(f"$SEQUENCE {str(chaser.index)}" + "\n", "utf8"))
        stream.write(bytes(f"TEXT {chaser.text}" + "\n\n", "utf8"))
        for step in chaser.steps:
            if int(step.cue.memory) != 0:
                # Save integers as integers
                time_out = (
                    str(int(step.time_out))
                    if step.time_out.is_integer()
                    else str(step.time_out)
                )
                delay_out = (
                    str(int(step.delay_out))
                    if step.delay_out.is_integer()
                    else str(step.delay_out)
                )
                time_in = (
                    str(int(step.time_in))
                    if step.time_in.is_integer()
                    else str(step.time_in)
                )
                delay_in = (
                    str(int(step.delay_in))
                    if step.delay_in.is_integer()
                    else str(step.delay_in)
                )
                wait = str(int(step.wait)) if step.wait.is_integer() else str(step.wait)
                stream.write(
                    bytes(
                        f"$CUE {str(chaser.index)} {str(step.cue.memory)}" + "\n",
                        "utf8",
                    )
                )

                stream.write(bytes(f"DOWN {time_out} {delay_out}" + "\n", "utf8"))
                stream.write(bytes(f"UP {time_in} {delay_in}" + "\n", "utf8"))
                stream.write(bytes(f"$$WAIT {wait}" + "\n", "utf8"))
                _save_channels(stream, step.cue.channels)
                stream.write(bytes("\n", "utf8"))


def save_groups(stream: Gio.FileOutputStream) -> None:
    """Save Groups

    Args:
        stream: File
    """
    stream.write(
        bytes(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
            "utf8",
        )
    )
    stream.write(bytes("! Groups (presets not in sequence)\n", "utf8"))
    stream.write(bytes("! GROUP  Standard ASCII Light Cues\n", "utf8"))
    stream.write(bytes("! CHAN   Standard ASCII Light Cues\n", "utf8"))
    stream.write(bytes("! TEXT   Standard ASCII Light Cues\n", "utf8"))
    stream.write(bytes("! $$TEXT  Unicode encoded version of the same text\n", "utf8"))

    for group in App().groups:
        stream.write(bytes(f"GROUP {str(group.index)}" + "\n", "utf8"))
        stream.write(
            bytes(f"TEXT {ascii(group.text)[1:-1]}" + "\n", "utf8")
            .decode("utf8")
            .encode("ascii")
        )

        stream.write(bytes(f"$$TEXT {group.text}" + "\n", "utf8"))
        _save_channels(stream, group.channels)
        stream.write(bytes("\n", "utf8"))


def save_congo_groups(stream: Gio.FileOutputStream) -> None:
    """Save Congo Groups

    Args:
        stream: File
    """
    stream.write(
        bytes(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
            "utf8",
        )
    )
    stream.write(bytes("! Congo Groups\n", "utf8"))
    stream.write(bytes("! $GROUP  Group number\n", "utf8"))
    stream.write(bytes("! CHAN    Standard ASCII Light Cues\n", "utf8"))
    stream.write(bytes("! TEXT    Standard ASCII Light Cues\n", "utf8"))
    stream.write(bytes("! $$TEXT  Unicode encoded version of the same text\n", "utf8"))
    stream.write(bytes("CLEAR $GROUP\n\n", "utf8"))

    for group in App().groups:
        stream.write(bytes(f"$GROUP {str(group.index)}" + "\n", "utf8"))
        stream.write(
            bytes(f"TEXT {ascii(group.text)[1:-1]}" + "\n", "utf8")
            .decode("utf8")
            .encode("ascii")
        )

        stream.write(bytes(f"$$TEXT {group.text}" + "\n", "utf8"))
        _save_channels(stream, group.channels)
        stream.write(bytes("\n", "utf8"))


def save_masters(stream: Gio.FileOutputStream) -> None:
    """Save Masters

    Args:
        stream: File
    """
    stream.write(
        bytes(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
            "utf8",
        )
    )
    stream.write(bytes("! Master Pages\n", "utf8"))
    stream.write(bytes("! $MASTPAGE     Master page number\n", "utf8"))
    stream.write(bytes("! TEXT          Master page text\n", "utf8"))
    stream.write(
        bytes("! $TEXT         Unicode encoded version of the same text\n", "utf8")
    )
    stream.write(bytes("! $MASTPAGEITEM Page number, Master number,\n", "utf8"))
    stream.write(
        bytes("!               Content type (2 = Channels, 3 = Chaser,\n", "utf8")
    )
    stream.write(
        bytes("!               13 = Group), Content value (Chaser#, Group#),\n", "utf8")
    )
    stream.write(bytes("!               Time In, Wait time, Time Out,\n", "utf8"))
    stream.write(bytes("!               Flash level (0-255)\n", "utf8"))
    stream.write(bytes("CLEAR $MASTPAGE\n\n", "utf8"))
    stream.write(bytes("$MASTPAGE 1 0 0 0\n", "utf8"))
    page = 1
    for master in App().masters:
        if master.page != page:
            page = master.page
            stream.write(bytes("\n$MASTPAGE " + str(page) + " 0 0 0\n", "utf8"))
        # MASTPAGEITEM :
        # page, sub, type, content, timeIn, autotime, timeOut, target,,,,,,
        if not master.content_value or master.content_type == 2:
            content = "0"
        else:
            content = (
                str(int(master.content_value))
                if master.content_value.is_integer()
                else str(master.content_value)
            )
        stream.write(
            bytes(
                "$MASTPAGEITEM "
                + str(master.page)
                + " "
                + str(master.number)
                + " "
                + str(master.content_type)
                + " "
                + content
                + " 5 0 5 255\n",
                "utf8",
            )
        )
        # Master of Channels, save them
        if master.content_type == 2:
            _save_channels(stream, master.content_value)

    stream.write(bytes("\n", "utf8"))


def save_patch(stream: Gio.FileOutputStream) -> None:
    """Save Patch

    Args:
        stream: File
    """
    stream.write(
        bytes(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
            "utf8",
        )
    )
    stream.write(bytes("! Patch\n", "utf8"))
    stream.write(bytes("CLEAR PATCH\n\n", "utf8"))
    i = 1
    patch = ""
    for channel, outputs in App().patch.channels.items():
        for values in outputs:
            output = values[0]
            univ = values[1]
            index = App().universes.index(univ)
            limit = 255
            curve_num = App().patch.outputs[univ][output][1]
            if curve_num < 0:
                curve = App().curves.get_curve(curve_num)
                limit = curve.limit
            level = "H" + format(limit, "02X")
            patch += f" {str(channel)}<{str(output + 512 * index)}@{level}"
            if not i % 4 and patch != "":
                stream.write(bytes(f"PATCH 1{patch}" + "\n", "utf8"))
                patch = ""
            i += 1
    if patch != "":
        stream.write(bytes(f"PATCH 1{patch}" + "\n", "utf8"))
    stream.write(bytes("\n", "utf8"))


def save_independents(stream: Gio.FileOutputStream) -> None:
    """Save Independents

    Args:
        stream: File
    """
    stream.write(
        bytes(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
            "utf8",
        )
    )
    stream.write(bytes("! Independents\n\n", "utf8"))
    for inde in App().independents.independents:
        stream.write(bytes(f"$SPECIALFUNCTION {inde.number} 0 0\n", "utf8"))
        stream.write(bytes(f"TEXT {inde.text}\n", "iso-8859-1"))
        stream.write(bytes(f"$$TEXT {ascii(inde.text)[1:-1]}\n", "ascii"))
        _save_channels(stream, inde.levels)
        stream.write(bytes("\n", "utf8"))
    stream.write(bytes("\n", "utf8"))


def save_midi_mapping(stream: Gio.FileOutputStream) -> None:
    """Save MIDI mapping

    Args:
        stream: File
    """
    stream.write(
        bytes(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
            "utf8",
        )
    )
    stream.write(bytes("! MIDI mapping\n\n", "utf8"))
    for key, value in App().midi.notes.notes.items():
        stream.write(bytes(f"$$MIDINOTE {key} {value[0]} {value[1]}\n", "utf8"))
    for key, value in App().midi.control_change.control_change.items():
        stream.write(bytes(f"$$MIDICC {key} {value[0]} {value[1]}\n", "utf8"))
    for key, value in App().midi.pitchwheel.pitchwheel.items():
        stream.write(bytes(f"$$MIDIPW {key} {value}\n", "utf8"))
    stream.write(bytes("\n", "utf8"))


def save_curves(stream: Gio.FileOutputStream) -> None:
    """Save Curves

    Args:
        stream: File
    """
    stream.write(
        bytes(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
            "utf8",
        )
    )
    stream.write(bytes("! Curves\n\n", "utf8"))
    for key, curve in App().curves.curves.items():
        if key >= 10:
            curve_type = curve.__class__.__name__
            if isinstance(curve, LimitCurve):
                stream.write(
                    bytes(
                        f"$$CURVE {key} {curve_type} {curve.limit} {curve.name}\n",
                        "utf8",
                    )
                )
            if isinstance(curve, (SegmentsCurve, InterpolateCurve)):
                points = ""
                for point in curve.points:
                    points += f"{point[0]},{point[1]};"
                if points:
                    points = points[:-1]
                stream.write(
                    bytes(
                        f"$$CURVE {key} {curve_type} {points} {curve.name}\n",
                        "utf8",
                    )
                )
    stream.write(bytes("\n", "utf8"))


def save_outputs_curves(stream: Gio.FileOutputStream) -> None:
    """Save Outputs curves

    Args:
        stream: File
    """
    stream.write(
        bytes(
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n",
            "utf8",
        )
    )
    stream.write(bytes("! Output curves\n", "utf8"))
    stream.write(bytes("! $$OUTPUT  Universe, Output number, Curve number\n\n", "utf8"))
    for key, value in App().patch.outputs.items():
        for output, chan_dic in value.items():
            stream.write(bytes(f"$$OUTPUT {key} {output} {chan_dic[1]}\n", "utf8"))
    stream.write(bytes("\n", "utf8"))


def _save_channels(stream: Gio.FileOutputStream, chans: Dict[int, int]) -> None:
    """Save channels

    Args:
        stream: File
        chans: Channels and Levels
    """
    channels = ""
    i = 1
    for chan, level in chans.items():
        if level != 0:
            lvl = "H" + format(level, "02X")
            channels += f" {str(chan)}/{lvl}"
            # 6 Channels per line
            if not i % 6 and channels != "":
                stream.write(bytes(f"CHAN{channels}" + "\n", "utf8"))
                channels = ""
            i += 1
    if channels != "":
        stream.write(bytes(f"CHAN{channels}" + "\n", "utf8"))
