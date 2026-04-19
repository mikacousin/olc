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
# pylint: disable=too-many-lines
import typing

from gi.repository import Gdk, Gtk
from olc.define import MAX_FADER_PAGE
from olc.widgets.button import ButtonWidget
from olc.widgets.controller import ControllerWidget
from olc.widgets.fader import FaderWidget
from olc.widgets.flash import FlashWidget
from olc.widgets.go import GoWidget
from olc.widgets.knob import KnobWidget
from olc.widgets.pause import PauseWidget
from olc.widgets.toggle import ToggleWidget

if typing.TYPE_CHECKING:
    from olc.application import Application


# pylint: disable=too-many-instance-attributes
class VirtualConsoleWindow(Gtk.Window):
    """Virtual Console Window"""

    # pylint: disable=too-many-statements
    def __init__(self, app: Application) -> None:
        self.app = app

        super().__init__(title="Virtual Console")
        self.set_default_size(400, 300)

        # On close window
        self.connect("delete-event", self._close)

        # Header bar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = "Virtual Console"
        self.set_titlebar(self.header)
        self.midi = Gtk.ToggleButton(label="MIDI")
        self.midi.set_name("midi_toggle")
        self.midi.connect("toggled", self._on_button_toggled, "MIDI")
        self.header.pack_end(self.midi)

        # Numeric Pad
        self.num_pad = Gtk.Grid()
        # self.num_pad.set_column_homogeneous(True)
        # self.num_pad.set_row_homogeneous(True)
        self.zero = ButtonWidget(label="0", text="number_0", midi=self.app.midi)
        self.zero.connect("clicked", self._on_zero)
        self.one = ButtonWidget(label="1", text="number_1", midi=self.app.midi)
        self.one.connect("clicked", self._on_1)
        self.two = ButtonWidget(label="2", text="number_2", midi=self.app.midi)
        self.two.connect("clicked", self._on_2)
        self.three = ButtonWidget(label="3", text="number_3", midi=self.app.midi)
        self.three.connect("clicked", self._on_3)
        self.four = ButtonWidget(label="4", text="number_4", midi=self.app.midi)
        self.four.connect("clicked", self._on_4)
        self.five = ButtonWidget(label="5", text="number_5", midi=self.app.midi)
        self.five.connect("clicked", self._on_5)
        self.six = ButtonWidget(label="6", text="number_6", midi=self.app.midi)
        self.six.connect("clicked", self._on_6)
        self.seven = ButtonWidget(label="7", text="number_7", midi=self.app.midi)
        self.seven.connect("clicked", self._on_7)
        self.eight = ButtonWidget(label="8", text="number_8", midi=self.app.midi)
        self.eight.connect("clicked", self._on_8)
        self.nine = ButtonWidget(label="9", text="number_9", midi=self.app.midi)
        self.nine.connect("clicked", self._on_9)
        self.dot = ButtonWidget(label=".", text="dot", midi=self.app.midi)
        self.dot.connect("clicked", self._on_dot)
        self.clear = ButtonWidget(label="C", text="clear", midi=self.app.midi)
        self.clear.connect("clicked", self._on_clear)
        self.num_pad.attach(self.zero, 0, 3, 1, 1)
        self.num_pad.attach(self.clear, 1, 3, 1, 1)
        self.num_pad.attach(self.dot, 2, 3, 1, 1)
        self.num_pad.attach(self.one, 0, 2, 1, 1)
        self.num_pad.attach(self.two, 1, 2, 1, 1)
        self.num_pad.attach(self.three, 2, 2, 1, 1)
        self.num_pad.attach(self.four, 0, 1, 1, 1)
        self.num_pad.attach(self.five, 1, 1, 1, 1)
        self.num_pad.attach(self.six, 2, 1, 1, 1)
        self.num_pad.attach(self.seven, 0, 0, 1, 1)
        self.num_pad.attach(self.eight, 1, 0, 1, 1)
        self.num_pad.attach(self.nine, 2, 0, 1, 1)

        # Time keys
        self.time_pad = Gtk.Grid()
        # self.time_pad.set_column_homogeneous(True)
        # self.time_pad.set_row_homogeneous(True)
        self.time = ButtonWidget(label="Time", text="time", midi=self.app.midi)
        self.time.connect("clicked", self._on_time)
        self.delay = ButtonWidget(label="Delay", text="delay", midi=self.app.midi)
        self.delay.connect("clicked", self._on_delay)
        self.button_in = ButtonWidget(label="In", midi=self.app.midi)
        self.button_out = ButtonWidget(label="Out", midi=self.app.midi)
        self.label = Gtk.Label(label="")
        self.time_pad.attach(self.label, 0, 0, 1, 1)
        self.label = Gtk.Label(label="")
        self.time_pad.attach(self.label, 1, 0, 1, 1)
        self.time_pad.attach(self.time, 2, 0, 1, 1)
        self.time_pad.attach(self.delay, 2, 1, 1, 1)
        self.time_pad.attach(self.button_in, 2, 2, 1, 1)
        self.time_pad.attach(self.button_out, 2, 3, 1, 1)

        # Seq, Preset, Group ...
        self.seq_pad = Gtk.Grid()
        # self.seq_pad.set_column_homogeneous(True)
        # self.seq_pad.set_row_homogeneous(True)
        self.seq = ButtonWidget(label="Seq", text="seq", midi=self.app.midi)
        self.seq.connect("clicked", self._on_seq)
        self.empty1 = ButtonWidget(label=" ", midi=self.app.midi)
        self.empty2 = ButtonWidget(label=" ", midi=self.app.midi)
        self.preset = ButtonWidget(label="Preset", text="preset", midi=self.app.midi)
        self.preset.connect("clicked", self._on_preset)
        self.group = ButtonWidget(label="Group", text="group", midi=self.app.midi)
        self.group.connect("clicked", self._on_group)
        self.effect = ButtonWidget(label="Effect", midi=self.app.midi)
        self.seq_pad.attach(self.seq, 0, 2, 1, 1)
        self.seq_pad.attach(self.empty1, 1, 2, 1, 1)
        self.seq_pad.attach(self.empty2, 2, 2, 1, 1)
        self.seq_pad.attach(self.preset, 0, 3, 1, 1)
        self.seq_pad.attach(self.group, 1, 3, 1, 1)
        self.seq_pad.attach(self.effect, 2, 3, 1, 1)
        self.label = Gtk.Label(label="")
        self.seq_pad.attach(self.label, 0, 0, 1, 1)
        self.label = Gtk.Label(label="")
        self.seq_pad.attach(self.label, 0, 1, 1, 1)

        # Output grid
        self.output_pad = Gtk.Grid()
        self.output = ButtonWidget(label="Output", text="output", midi=self.app.midi)
        self.output.connect("clicked", self._on_output)
        self.label = Gtk.Label(label="")
        self.output_pad.attach(self.label, 1, 0, 1, 1)
        self.output_pad.attach(self.output, 2, 0, 1, 1)
        self.label = Gtk.Label(label="")
        self.output_pad.attach(self.label, 2, 1, 1, 1)
        self.label = Gtk.Label(label="")
        self.output_pad.attach(self.label, 2, 2, 1, 1)
        self.label = Gtk.Label(label="")
        self.output_pad.attach(self.label, 2, 3, 1, 1)

        # Update, Record, Track
        self.rec_pad = Gtk.Grid()
        # self.rec_pad.set_column_homogeneous(True)
        # self.rec_pad.set_row_homogeneous(True)
        self.update = ButtonWidget(label="Update", text="update", midi=self.app.midi)
        self.update.connect("clicked", self._on_update)
        self.record = ButtonWidget(label="Record", text="record", midi=self.app.midi)
        self.record.connect("clicked", self._on_record)
        self.track = ButtonWidget(label="Track", text="track", midi=self.app.midi)
        self.track.connect("clicked", self._on_track)
        self.rec_pad.attach(self.update, 0, 0, 1, 1)
        self.rec_pad.attach(self.record, 2, 0, 1, 1)
        self.rec_pad.attach(self.track, 0, 2, 1, 1)
        self.label = Gtk.Label(label="")
        self.rec_pad.attach(self.label, 0, 1, 1, 1)
        self.label = Gtk.Label(label="")
        self.rec_pad.attach(self.label, 0, 3, 1, 1)
        self.label = Gtk.Label(label="")
        self.rec_pad.attach(self.label, 1, 3, 1, 1)

        # Thru, Channel, +, -, All, @, +%, -%
        self.thru_pad = Gtk.Grid()
        # self.thru_pad.set_column_homogeneous(True)
        # self.thru_pad.set_row_homogeneous(True)
        self.thru = ButtonWidget(label="Thru", text="thru", midi=self.app.midi)
        self.thru.connect("clicked", self._on_thru)
        self.channel = ButtonWidget(label="Ch", text="ch", midi=self.app.midi)
        self.channel.connect("clicked", self._on_channel)
        self.plus = ButtonWidget(label="+", text="plus", midi=self.app.midi)
        self.plus.connect("clicked", self._on_plus)
        self.minus = ButtonWidget(label="-", text="minus", midi=self.app.midi)
        self.minus.connect("clicked", self._on_minus)
        self.all = ButtonWidget(label="All", text="all", midi=self.app.midi)
        self.all.connect("clicked", self._on_all)
        self.at_level = ButtonWidget(label="@", text="at", midi=self.app.midi)
        self.at_level.connect("clicked", self._on_at)
        self.percent_plus = ButtonWidget(
            label="+%", text="percent_plus", midi=self.app.midi
        )
        self.percent_plus.connect("clicked", self._on_percent_plus)
        self.percent_minus = ButtonWidget(
            label="-%", text="percent_minus", midi=self.app.midi
        )
        self.percent_minus.connect("clicked", self._on_percent_minus)
        self.thru_pad.attach(self.thru, 0, 0, 1, 1)
        self.thru_pad.attach(self.channel, 0, 1, 1, 1)
        self.thru_pad.attach(self.plus, 0, 2, 1, 1)
        self.thru_pad.attach(self.minus, 0, 3, 1, 1)
        self.thru_pad.attach(self.all, 0, 4, 1, 1)
        self.thru_pad.attach(self.at_level, 2, 0, 1, 1)
        self.thru_pad.attach(self.percent_plus, 2, 1, 1, 1)
        self.thru_pad.attach(self.percent_minus, 2, 2, 1, 1)
        self.label = Gtk.Label(label="")
        self.thru_pad.attach(self.label, 1, 0, 1, 1)
        self.label = Gtk.Label(label="")
        self.thru_pad.attach(self.label, 2, 3, 1, 1)
        self.label = Gtk.Label(label="")
        self.thru_pad.attach(self.label, 2, 4, 1, 1)

        # Insert, Delete, Escape, Modify, Up, Down, Left, Right
        self.modify_pad = Gtk.Grid()
        # self.modify_pad.set_column_homogeneous(True)
        # self.modify_pad.set_row_homogeneous(True)
        self.insert = ButtonWidget(label="Insert", midi=self.app.midi)
        self.delete = ButtonWidget(label="Delete", midi=self.app.midi)
        self.esc = ButtonWidget(label="Esc", midi=self.app.midi)
        self.modify = ButtonWidget(label="Modify", midi=self.app.midi)
        self.up = ButtonWidget(label="^", text="up", midi=self.app.midi)
        self.up.connect("clicked", self._on_up)
        self.down = ButtonWidget(label="v", text="down", midi=self.app.midi)
        self.down.connect("clicked", self._on_down)
        self.left = ButtonWidget(label="<", text="left", midi=self.app.midi)
        self.left.connect("clicked", self._on_left)
        self.right = ButtonWidget(label=">", text="right", midi=self.app.midi)
        self.right.connect("clicked", self._on_right)
        self.modify_pad.attach(self.insert, 0, 0, 1, 1)
        self.modify_pad.attach(self.delete, 2, 0, 1, 1)
        self.modify_pad.attach(self.esc, 0, 2, 1, 1)
        self.modify_pad.attach(self.modify, 2, 2, 1, 1)
        self.modify_pad.attach(self.up, 1, 2, 1, 1)
        self.modify_pad.attach(self.down, 1, 3, 1, 1)
        self.modify_pad.attach(self.left, 0, 3, 1, 1)
        self.modify_pad.attach(self.right, 2, 3, 1, 1)
        self.label = Gtk.Label(label="")
        self.modify_pad.attach(self.label, 0, 1, 1, 1)

        # Controller for channels level
        self.wheel = ControllerWidget(text="wheel", midi=self.app.midi)
        self.wheel.connect("moved", self._on_wheel)
        self.wheel.connect("clicked", self._controller_clicked)

        # Crossfade and more
        self.crossfade_pad = Gtk.Grid()
        # self.crossfade_pad.set_column_homogeneous(True)
        # self.crossfade_pad.set_row_homogeneous(True)
        self.live = ButtonWidget(label="Live", midi=self.app.midi)
        self.format = ButtonWidget(label="Format", midi=self.app.midi)
        self.blind = ButtonWidget(label="Blind", midi=self.app.midi)
        self.goto = ButtonWidget(label="Goto", text="goto", midi=self.app.midi)
        self.goto.connect("clicked", self._on_goto)
        self.a = ButtonWidget(label="A", midi=self.app.midi)
        self.b = ButtonWidget(label="B", midi=self.app.midi)

        adjustment = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scale_a = FaderWidget(
            text="crossfade_out",
            red=0.3,
            green=0.3,
            blue=0.7,
            orientation=Gtk.Orientation.VERTICAL,
            adjustment=adjustment,
        )
        self.scale_a.led = False
        self.scale_a.connect("clicked", self._scale_clicked)
        self.scale_a.set_draw_value(False)
        self.scale_a.set_vexpand(True)
        self.scale_a.set_inverted(True)
        self.scale_a.connect("value-changed", self.scale_moved)

        adjustment = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
        self.scale_b = FaderWidget(
            text="crossfade_in",
            red=0.6,
            green=0.2,
            blue=0.2,
            orientation=Gtk.Orientation.VERTICAL,
            adjustment=adjustment,
        )
        self.scale_b.led = False
        self.scale_b.connect("clicked", self._scale_clicked)
        self.scale_b.set_draw_value(False)
        self.scale_b.set_vexpand(True)
        self.scale_b.set_inverted(True)
        self.scale_b.connect("value-changed", self.scale_moved)

        self.crossfade_pad.attach(self.live, 0, 4, 1, 1)
        self.crossfade_pad.attach(self.format, 0, 5, 1, 1)
        self.crossfade_pad.attach(self.blind, 0, 6, 1, 1)
        self.crossfade_pad.attach(self.goto, 1, 0, 1, 1)
        self.crossfade_pad.attach(self.a, 1, 1, 1, 1)
        self.crossfade_pad.attach(self.b, 2, 1, 1, 1)
        self.crossfade_pad.attach(self.scale_a, 1, 2, 1, 6)
        self.crossfade_pad.attach(self.scale_b, 2, 2, 1, 6)
        self.label = Gtk.Label(label="")
        self.crossfade_pad.attach(self.label, 0, 7, 1, 1)

        # Independents
        self.independents = Gtk.Grid()
        self.independent1 = KnobWidget(self.app.midi, text="inde_1")
        self.independent1.connect("clicked", self._inde_clicked)
        self.independent1.connect("changed", self._inde_changed)
        self.independent1.value = self.app.lightshow.independents.independents[0].level
        self.independent2 = KnobWidget(self.app.midi, text="inde_2")
        self.independent2.connect("clicked", self._inde_clicked)
        self.independent2.connect("changed", self._inde_changed)
        self.independent2.value = self.app.lightshow.independents.independents[1].level
        self.independent3 = KnobWidget(self.app.midi, text="inde_3")
        self.independent3.connect("clicked", self._inde_clicked)
        self.independent3.connect("changed", self._inde_changed)
        self.independent3.value = self.app.lightshow.independents.independents[2].level
        self.independent4 = KnobWidget(self.app.midi, text="inde_4")
        self.independent4.connect("clicked", self._inde_clicked)
        self.independent4.connect("changed", self._inde_changed)
        self.independent4.value = self.app.lightshow.independents.independents[3].level
        self.independent5 = KnobWidget(self.app.midi, text="inde_5")
        self.independent5.connect("clicked", self._inde_clicked)
        self.independent5.connect("changed", self._inde_changed)
        self.independent5.value = self.app.lightshow.independents.independents[4].level
        self.independent6 = KnobWidget(self.app.midi, text="inde_6")
        self.independent6.connect("clicked", self._inde_clicked)
        self.independent6.connect("changed", self._inde_changed)
        self.independent6.value = self.app.lightshow.independents.independents[5].level
        self.independent7 = ToggleWidget(self.app.midi, text="inde_7")
        self.independent8 = ToggleWidget(self.app.midi, text="inde_8")
        self.independent9 = ToggleWidget(self.app.midi, text="inde_9")
        self.independent7.connect("clicked", self._inde_clicked)
        if self.app.lightshow.independents.independents[6].level:
            self.independent7.set_active(True)
        self.independent8.connect("clicked", self._inde_clicked)
        if self.app.lightshow.independents.independents[7].level:
            self.independent8.set_active(True)
        self.independent9.connect("clicked", self._inde_clicked)
        if self.app.lightshow.independents.independents[8].level:
            self.independent9.set_active(True)
        self.independents.attach(self.independent1, 0, 0, 1, 1)
        self.independents.attach(self.independent2, 1, 0, 1, 1)
        self.independents.attach(self.independent3, 2, 0, 1, 1)
        self.independents.attach(self.independent4, 0, 1, 1, 1)
        self.independents.attach(self.independent5, 1, 1, 1, 1)
        self.independents.attach(self.independent6, 2, 1, 1, 1)
        self.independents.attach(self.independent7, 0, 2, 1, 1)
        self.independents.attach(self.independent8, 1, 2, 1, 1)
        self.independents.attach(self.independent9, 2, 2, 1, 1)

        # Go, Seq-, Seq+, Pause, Go Back
        self.go_pad = Gtk.Grid()
        self.go_button = GoWidget(self.app.midi)
        self.go_button.connect("clicked", self._on_go)
        self.seq_plus = ButtonWidget(
            label="Next Cue", text="seq_plus", midi=self.app.midi
        )
        self.seq_plus.connect("clicked", self._on_seq_plus)
        self.seq_minus = ButtonWidget(
            label="Prev Cue", text="seq_minus", midi=self.app.midi
        )
        self.seq_minus.connect("clicked", self._on_seq_minus)
        self.goback = ButtonWidget(label="Go Back", text="go_back", midi=self.app.midi)
        self.goback.connect("clicked", self._on_go_back)
        self.pause = PauseWidget("Pause", "pause", midi=self.app.midi)
        self.pause.connect("clicked", self._on_pause)
        self.go_pad.attach(self.seq_minus, 0, 0, 1, 1)
        self.go_pad.attach(self.seq_plus, 1, 0, 1, 1)
        self.go_pad.attach(self.pause, 0, 1, 1, 1)
        self.go_pad.attach(self.goback, 1, 1, 1, 1)
        self.go_pad.attach(self.go_button, 0, 2, 2, 1)
        self.label = Gtk.Label(label="")
        self.go_pad.attach(self.label, 2, 3, 1, 1)

        # Faders
        self.faders_pad = Gtk.Grid()
        self.faders = []
        self.flashes = []
        for i in range(10):  # 10 Faders per page
            adjustment = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
            self.faders.append(
                FaderWidget(
                    text=f"fader_{i + 1}",
                    orientation=Gtk.Orientation.VERTICAL,
                    adjustment=adjustment,
                )
            )
            self.faders[i].set_vexpand(True)
            self.faders[i].set_draw_value(False)
            self.faders[i].set_inverted(True)
            self.faders[i].connect("value-changed", self.fader_moved)
            self.faders[i].connect("clicked", self._fader_clicked)
            self.flashes.append(FlashWidget("", midi=self.app.midi))
            self.flashes[i].connect("button-press-event", self._flash_on)
            self.flashes[i].connect("button-release-event", self._flash_off)
            self.flashes[i].connect("clicked", self._on_flash)
            self.faders_pad.attach(self.faders[i], i, 0, 1, 1)
            self.faders_pad.attach(self.flashes[i], i, 1, 1, 1)
            text = f"flash_{i + 1}"
            self.flashes[i].text = text
        fader_bank = self.app.lightshow.fader_bank
        for fader in fader_bank.faders[fader_bank.active_page].values():
            # Flash with fader name
            self.flashes[fader.index - 1].label = fader.text
            # Fader at fader level
            level = round(fader.level * 255)
            self.faders[fader.index - 1].set_value(level)
        self.fader_pages = Gtk.Grid()
        self.fader_page_plus = ButtonWidget(
            label="Page+", text="page_plus", midi=self.app.midi
        )
        self.fader_page_plus.connect("clicked", self._on_fader_page)
        self.fader_page_minus = ButtonWidget(
            label="Page-", text="page_minus", midi=self.app.midi
        )
        self.fader_page_minus.connect("clicked", self._on_fader_page)
        self.page_number = Gtk.Label(label=str(fader_bank.active_page))
        self.fader_pages.attach(self.fader_page_plus, 0, 0, 1, 1)
        self.fader_pages.attach(self.page_number, 0, 1, 1, 1)
        self.fader_pages.attach(self.fader_page_minus, 0, 2, 1, 1)
        self.faders_pad.attach(self.fader_pages, 11, 0, 1, 1)

        # General Grid
        self.grid = Gtk.Grid()
        # self.grid.set_column_homogeneous(True)
        # self.grid.set_row_homogeneous(True)
        self.grid.set_row_spacing(10)
        self.grid.set_column_spacing(10)
        self.grid.attach(self.output_pad, 0, 0, 1, 1)
        self.grid.attach(self.time_pad, 0, 1, 1, 1)
        self.grid.attach(self.seq_pad, 1, 0, 1, 1)
        self.grid.attach(self.num_pad, 1, 1, 1, 1)
        self.grid.attach(self.rec_pad, 2, 0, 1, 1)
        self.grid.attach(self.thru_pad, 2, 1, 1, 1)
        self.grid.attach(self.modify_pad, 3, 0, 1, 1)
        self.grid.attach(self.wheel, 3, 1, 1, 1)
        self.grid.attach(self.crossfade_pad, 4, 0, 1, 2)
        self.grid.attach(self.independents, 5, 0, 1, 1)
        self.grid.attach(self.go_pad, 5, 1, 1, 1)
        self.grid.attach(self.faders_pad, 6, 0, 1, 2)

        self.add(self.grid)

        # Send keyboard events to a dispatch function
        if self.app.window and self.app.window.live_view:
            self.connect(
                "key_press_event", self.app.window.live_view.on_key_press_event
            )

    def _close(self, _widget: Gtk.Widget, _event: Gdk.Event) -> bool:
        """Mark Window as closed

        Returns:
            False to propagate the event further
        """
        self.app.virtual_console = None
        return False

    def _on_button_toggled(self, button: Gtk.ToggleButton, name: str) -> None:
        """MIDI learn On / Off

        Args:
            button: Button clicked
            name: Name of the button
        """
        if button.get_active() and name == "MIDI":
            if self.app.midi:
                self.app.midi.learning = " "
        elif name == "MIDI":
            if self.app.midi:
                self.app.midi.learning = ""
            if self.app.virtual_console:
                self.app.virtual_console.queue_draw()

    def _on_fader_page(self, widget: Gtk.Widget) -> None:
        """Change fader page

        Args:
            widget: clicked button
        """
        if self.app.midi and self.app.midi.learning:
            if widget is self.fader_page_plus:
                self.app.midi.learning = "page_plus"
            elif widget is self.fader_page_minus:
                self.app.midi.learning = "page_minus"
            self.queue_draw()
        else:
            fader_bank = self.app.lightshow.fader_bank
            if widget is self.fader_page_plus:
                fader_bank.active_page += 1
                if fader_bank.active_page > MAX_FADER_PAGE:
                    fader_bank.active_page = 1
            elif widget is self.fader_page_minus:
                fader_bank.active_page -= 1
                if fader_bank.active_page < 1:
                    fader_bank.active_page = MAX_FADER_PAGE
            self.page_number.set_label(str(fader_bank.active_page))
            # Redraw Faders and Flashes
            for fader in fader_bank.faders[fader_bank.active_page].values():
                text = f"fader_{fader.index + ((fader_bank.active_page - 1) * 10)}"
                self.faders[fader.index - 1].text = text
                val = round(fader.level * 255)
                self.faders[fader.index - 1].set_value(val)
                self.flashes[fader.index - 1].label = fader.text
                self.flashes[fader.index - 1].queue_draw()
            if self.app.midi:
                self.app.midi.messages.lcd.show_faders()

    def _on_time(self, _widget: Gtk.Widget) -> None:
        """Time button"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "time"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_T
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_delay(self, _widget: Gtk.Widget) -> None:
        """Delay button"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "delay"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_D
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_go(self, _widget: Gtk.Widget) -> None:
        """Go"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "go"
            self.queue_draw()
        else:
            self.app.lightshow.main_playback.do_go(None, False)

    def _on_go_back(self, _widget: Gtk.Widget) -> None:
        """Go back"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "go_back"
            self.queue_draw()
        else:
            self.app.lightshow.main_playback.go_back(None, None)

    def _on_pause(self, _widget: Gtk.Widget) -> None:
        """Pause"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "pause"
            self.queue_draw()
        else:
            self.app.lightshow.main_playback.pause(None, None)

    def _on_seq_plus(self, _widget: Gtk.Widget) -> None:
        """Sequence +"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "seq_plus"
            self.queue_draw()
        else:
            self.app.lightshow.main_playback.sequence_plus()

    def _on_seq_minus(self, _widget: Gtk.Widget) -> None:
        """Sequence -"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "seq_minus"
            self.queue_draw()
        else:
            self.app.lightshow.main_playback.sequence_minus()

    def _on_output(self, _widget: Gtk.Widget) -> None:
        """Output"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "output"
            self.queue_draw()
        else:
            self.app.patch_outputs(typing.cast(typing.Any, None), None)

    def _on_seq(self, _widget: Gtk.Widget) -> None:
        """Seq"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "seq"
            self.queue_draw()
        else:
            self.app.sequences(typing.cast(typing.Any, None), None)

    def _on_preset(self, _widget: Gtk.Widget) -> None:
        """Preset"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "preset"
            self.queue_draw()
        else:
            self.app.memories_cb(typing.cast(typing.Any, None), None)

    def _on_group(self, _widget: Gtk.Widget) -> None:
        """Group"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "group"
            self.queue_draw()
        else:
            self.app.groups_cb(typing.cast(typing.Any, None), None)

    def _on_track(self, _widget: Gtk.Widget) -> None:
        """Track channels"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "track"
            self.queue_draw()
        else:
            self.app.track_channels(typing.cast(typing.Any, None), None)

    def _on_goto(self, _widget: Gtk.Widget) -> None:
        """Goto"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "goto"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.lightshow.main_playback.goto(
                    self.app.window.commandline.get_string()
                )
                self.app.window.commandline.set_string("")

    def _on_channel(self, _widget: Gtk.Widget) -> None:
        """Channel button"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "ch"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_c
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_thru(self, _widget: Gtk.Widget) -> None:
        """Thru"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "thru"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_greater
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_plus(self, _widget: Gtk.Widget) -> None:
        """+ button"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "plus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_plus
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_minus(self, _widget: Gtk.Widget) -> None:
        """- button"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "minus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_minus
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_all(self, _widget: Gtk.Widget) -> None:
        """All"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "all"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_a
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_at(self, _widget: Gtk.Widget) -> None:
        """At level"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "at"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_equal
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_percent_plus(self, _widget: Gtk.Widget) -> None:
        """% +"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "percent_plus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_exclam
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_percent_minus(self, _widget: Gtk.Widget) -> None:
        """% -"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "percent_minus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_colon
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_update(self, _widget: Gtk.Widget) -> None:
        """Update"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "update"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_U
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_record(self, _widget: Gtk.Widget) -> None:
        """Record"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "record"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_R
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_right(self, _widget: Gtk.Widget) -> None:
        """Right arrow"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "right"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Right
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_left(self, _widget: Gtk.Widget) -> None:
        """Left arrow"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "left"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Left
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_up(self, _widget: Gtk.Widget) -> None:
        """Up arrow"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "up"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Up
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_down(self, _widget: Gtk.Widget) -> None:
        """Down arrow"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "down"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Down
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_clear(self, _widget: Gtk.Widget) -> None:
        """Clear"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "clear"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_BackSpace
            if self.app.window:
                self.app.window.on_key_press_event(self, event)

    def _on_zero(self, _widget: Gtk.Widget) -> None:
        """0"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_0"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("0")

    def _on_1(self, _widget: Gtk.Widget) -> None:
        """1"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_1"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("1")

    def _on_2(self, _widget: Gtk.Widget) -> None:
        """2"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_2"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("2")

    def _on_3(self, _widget: Gtk.Widget) -> None:
        """3"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_3"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("3")

    def _on_4(self, _widget: Gtk.Widget) -> None:
        """4"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_4"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("4")

    def _on_5(self, _widget: Gtk.Widget) -> None:
        """5"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_5"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("5")

    def _on_6(self, _widget: Gtk.Widget) -> None:
        """6"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_6"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("6")

    def _on_7(self, _widget: Gtk.Widget) -> None:
        """7"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_7"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("7")

    def _on_8(self, _widget: Gtk.Widget) -> None:
        """8"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_8"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("8")

    def _on_9(self, _widget: Gtk.Widget) -> None:
        """9"""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "number_9"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string("9")

    def _on_dot(self, _widget: Gtk.Widget) -> None:
        """."""
        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = "dot"
            self.queue_draw()
        else:
            if self.app.window:
                self.app.window.commandline.add_string(".")

    def _flash_on(self, widget: Gtk.Widget, _event: Gdk.Event) -> None:
        """Flash button pressed

        Args:
            widget: Button clicked
        """
        if self.app.midi and not self.app.midi.learning:
            for index, flash in enumerate(self.flashes):
                if flash == widget:
                    fader_bank = self.app.lightshow.fader_bank
                    fader_bank.faders[fader_bank.active_page][index + 1].flash_on()

    def _flash_off(self, widget: Gtk.Widget, _event: Gdk.Event) -> None:
        """Flash button released

        Args:
            widget: Button clicked
        """
        if self.app.midi and not self.app.midi.learning:
            for index, flash in enumerate(self.flashes):
                if flash == widget:
                    fader_bank = self.app.lightshow.fader_bank
                    fader_bank.faders[fader_bank.active_page][index + 1].flash_off()

    def _on_flash(self, widget: Gtk.Widget) -> None:
        """Flash button clicked

        Args:
            widget: Button clicked
        """
        if self.app.midi and self.app.midi.learning:
            index = self.flashes.index(widget) + 1
            text = f"flash_{index}"
            self.app.midi.learning = text
            self.queue_draw()

    def fader_moved(self, fader: FaderWidget) -> None:
        """Fader moved

        Args:
            fader: FaderWidget
        """
        if self.app.midi and self.app.midi.learning:
            index = self.faders.index(fader) + 1
            text = f"fader_{index}"
            self.app.midi.learning = text
            self.queue_draw()
        else:
            value = fader.get_value()
            index = self.faders.index(fader) + 1
            fader_bank = self.app.lightshow.fader_bank
            fader_bank.faders[fader_bank.active_page][index].set_level(value / 255)
            if self.app.midi:
                midi_fader = self.app.midi.faders.faders[self.faders.index(fader)]
                midi_fader.set_state(int(value))

    def _fader_clicked(self, fader: FaderWidget) -> None:
        """Fader clicked

        Args:
            fader: FaderWidget
        """
        if self.app.midi and self.app.midi.learning:
            index = self.faders.index(fader) + 1
            text = f"fader_{index}"
            self.app.midi.learning = text
            self.queue_draw()

    def scale_moved(self, scale: FaderWidget) -> None:
        """Crossfade moved

        Args:
            scale (FaderWidget): crossfade fader
        """
        if self.app.midi and self.app.midi.learning:
            if scale == self.scale_a:
                self.app.midi.learning = "crossfade_out"
            elif scale == self.scale_b:
                self.app.midi.learning = "crossfade_in"
            self.queue_draw()
        else:
            value = scale.get_value()

            if not self.app.crossfade:
                return
            if scale == self.scale_a:
                self.app.crossfade.scale_a.set_value(int(value))
                if self.app.midi:
                    midi_fader = self.app.midi.xfade.fader_out
                    midi_fader.set_state(int(value))
                if self.app.crossfade.manual:
                    self.app.crossfade.scale_moved(self.app.crossfade.scale_a)
            elif scale == self.scale_b:
                self.app.crossfade.scale_b.set_value(int(value))
                if self.app.midi:
                    midi_fader = self.app.midi.xfade.fader_in
                    midi_fader.set_state(int(value))
                if self.app.crossfade.manual:
                    self.app.crossfade.scale_moved(self.app.crossfade.scale_b)

    def _scale_clicked(self, scale: FaderWidget) -> None:
        """Crossfade clicked

        Args:
            scale: FaderWidget
        """
        if self.app.midi and self.app.midi.learning:
            if scale == self.scale_a:
                self.app.midi.learning = "crossfade_out"
            elif scale == self.scale_b:
                self.app.midi.learning = "crossfade_in"
            self.queue_draw()

    def _controller_clicked(self, widget: Gtk.Widget) -> None:
        """Controller clicked

        Args:
            widget: Object clicked
        """
        if self.app.midi and self.app.midi.learning and widget == self.wheel:
            self.app.midi.learning = "wheel"
        self.queue_draw()

    def _on_wheel(
        self, _widget: Gtk.Widget, direction: Gdk.ScrollDirection, step: int
    ) -> None:
        """Wheel for channels level

        Args:
            direction : Up or down
            step : increment or decrement step size
        """
        if self.app.midi and self.app.midi.learning:
            return
        if not self.app.window:
            return
        child = self.app.window.get_active_tab()
        channels_view = None
        if (
            self.app.window.live_view
            and child == self.app.window.live_view.channels_view
        ):
            channels_view = child
        elif child in (
            self.app.tabs.tabs["groups"],
            self.app.tabs.tabs["indes"],
            self.app.tabs.tabs["faders"],
            self.app.tabs.tabs["memories"],
            self.app.tabs.tabs["sequences"],
        ):
            channels_view = typing.cast(typing.Any, child).channels_view
        if channels_view:
            typing.cast(typing.Any, channels_view).wheel_level(step, direction)

    def _inde_clicked(self, widget: Gtk.Widget) -> None:
        """Independent clicked

        Args:
            widget: Object clicked
        """
        mapping = {
            self.independent1: ("inde_1", None),
            self.independent2: ("inde_2", None),
            self.independent3: ("inde_3", None),
            self.independent4: ("inde_4", None),
            self.independent5: ("inde_5", None),
            self.independent6: ("inde_6", None),
            self.independent7: ("inde_7", 6),
            self.independent8: ("inde_8", 7),
            self.independent9: ("inde_9", 8),
        }

        if widget not in mapping:
            return

        name, inde_idx = mapping[widget]

        if self.app.midi and self.app.midi.learning:
            self.app.midi.learning = name
            if widget in (self.independent7, self.independent8, self.independent9):
                typing.cast(typing.Any, widget).set_active(False)
            self.queue_draw()
        elif inde_idx is not None:
            level = 255 if typing.cast(typing.Any, widget).get_active() else 0
            self.app.lightshow.independents.independents[inde_idx].level = level
            self.app.lightshow.independents.independents[inde_idx].update_dmx()

    def _inde_changed(self, widget: Gtk.Widget) -> None:
        """Independent value changed

        Args:
            widget: Object changed
        """
        if self.app.midi and self.app.midi.learning:
            return
        if widget == self.independent1:
            index = 0
        elif widget == self.independent2:
            index = 1
        elif widget == self.independent3:
            index = 2
        elif widget == self.independent4:
            index = 3
        elif widget == self.independent5:
            index = 4
        elif widget == self.independent6:
            index = 5
        else:
            return
        value = typing.cast(typing.Any, widget).value
        inde = self.app.lightshow.independents.independents[index]
        inde.set_level(value)
        if self.app.midi:
            midi_fader = self.app.midi.faders.inde_faders[index]
            midi_fader.set_state(int(value))
