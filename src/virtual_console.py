# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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
from gi.repository import Gdk, Gtk
from olc.define import App, MAX_FADER_PAGE
from olc.widgets.button import ButtonWidget
from olc.widgets.controller import ControllerWidget
from olc.widgets.fader import FaderWidget
from olc.widgets.flash import FlashWidget
from olc.widgets.go import GoWidget
from olc.widgets.knob import KnobWidget
from olc.widgets.pause import PauseWidget
from olc.widgets.toggle import ToggleWidget


class VirtualConsoleWindow(Gtk.Window):
    """Virtual Console Window"""

    def __init__(self):
        self.midi_learn = False

        Gtk.Window.__init__(self, title="Virtual Console")
        self.set_default_size(400, 300)

        # On close window
        self.connect("delete-event", self.close)

        # Headerbar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = "Virtual Console"
        self.set_titlebar(self.header)
        self.midi = Gtk.ToggleButton("MIDI")
        self.midi.set_name("midi_toggle")
        self.midi.connect("toggled", self.on_button_toggled, "MIDI")
        self.header.pack_end(self.midi)

        # Numeric Pad
        self.num_pad = Gtk.Grid()
        # self.num_pad.set_column_homogeneous(True)
        # self.num_pad.set_row_homogeneous(True)
        self.zero = ButtonWidget("0", "number_0")
        self.zero.connect("clicked", self.on_zero)
        self.one = ButtonWidget("1", "number_1")
        self.one.connect("clicked", self.on_1)
        self.two = ButtonWidget("2", "number_2")
        self.two.connect("clicked", self.on_2)
        self.three = ButtonWidget("3", "number_3")
        self.three.connect("clicked", self.on_3)
        self.four = ButtonWidget("4", "number_4")
        self.four.connect("clicked", self.on_4)
        self.five = ButtonWidget("5", "number_5")
        self.five.connect("clicked", self.on_5)
        self.six = ButtonWidget("6", "number_6")
        self.six.connect("clicked", self.on_6)
        self.seven = ButtonWidget("7", "number_7")
        self.seven.connect("clicked", self.on_7)
        self.eight = ButtonWidget("8", "number_8")
        self.eight.connect("clicked", self.on_8)
        self.nine = ButtonWidget("9", "number_9")
        self.nine.connect("clicked", self.on_9)
        self.dot = ButtonWidget(".", "dot")
        self.dot.connect("clicked", self.on_dot)
        self.clear = ButtonWidget("C", "clear")
        self.clear.connect("clicked", self.on_clear)
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
        self.time = ButtonWidget("Time", "time")
        self.time.connect("clicked", self.on_time)
        self.delay = ButtonWidget("Delay", "delay")
        self.delay.connect("clicked", self.on_delay)
        self.button_in = ButtonWidget("In")
        self.button_out = ButtonWidget("Out")
        # self.labelGM = Gtk.Label('Grand Master')
        self.label = Gtk.Label("")
        self.time_pad.attach(self.label, 0, 0, 1, 1)
        self.label = Gtk.Label("")
        self.time_pad.attach(self.label, 1, 0, 1, 1)
        self.time_pad.attach(self.time, 2, 0, 1, 1)
        self.time_pad.attach(self.delay, 2, 1, 1, 1)
        self.time_pad.attach(self.button_in, 2, 2, 1, 1)
        self.time_pad.attach(self.button_out, 2, 3, 1, 1)

        # Seq, Preset, Group ...
        self.seq_pad = Gtk.Grid()
        # self.seq_pad.set_column_homogeneous(True)
        # self.seq_pad.set_row_homogeneous(True)
        self.seq = ButtonWidget("Seq", "seq")
        self.seq.connect("clicked", self.on_seq)
        self.empty1 = ButtonWidget(" ")
        self.empty2 = ButtonWidget(" ")
        self.preset = ButtonWidget("Preset", "preset")
        self.preset.connect("clicked", self.on_preset)
        self.group = ButtonWidget("Group", "group")
        self.group.connect("clicked", self.on_group)
        self.effect = ButtonWidget("Effect")
        self.seq_pad.attach(self.seq, 0, 2, 1, 1)
        self.seq_pad.attach(self.empty1, 1, 2, 1, 1)
        self.seq_pad.attach(self.empty2, 2, 2, 1, 1)
        self.seq_pad.attach(self.preset, 0, 3, 1, 1)
        self.seq_pad.attach(self.group, 1, 3, 1, 1)
        self.seq_pad.attach(self.effect, 2, 3, 1, 1)
        self.label = Gtk.Label("")
        self.seq_pad.attach(self.label, 0, 0, 1, 1)
        self.label = Gtk.Label("")
        self.seq_pad.attach(self.label, 0, 1, 1, 1)

        # Grand Master and Output grid
        self.output_pad = Gtk.Grid()
        # self.output_pad.set_column_homogeneous(True)
        # self.output_pad.set_row_homogeneous(True)
        adjustment = Gtk.Adjustment(255, 0, 255, 1, 10, 0)
        self.scale_grand_master = FaderWidget(
            text="gm", orientation=Gtk.Orientation.VERTICAL, adjustment=adjustment
        )
        self.scale_grand_master.value = 255
        # self.scale_grand_master.height = 160
        self.scale_grand_master.connect("clicked", self.scale_clicked)
        self.scale_grand_master.connect("value-changed", self.grand_master_moved)
        self.scale_grand_master.set_draw_value(False)
        self.scale_grand_master.set_vexpand(True)
        self.scale_grand_master.set_inverted(True)
        self.output = ButtonWidget("Output", "output")
        self.output.connect("clicked", self.on_output)
        self.output_pad.attach(self.scale_grand_master, 0, 0, 1, 4)
        self.label = Gtk.Label("")
        self.output_pad.attach(self.label, 1, 0, 1, 1)
        self.output_pad.attach(self.output, 2, 0, 1, 1)
        self.label = Gtk.Label("")
        self.output_pad.attach(self.label, 2, 1, 1, 1)
        self.label = Gtk.Label("")
        self.output_pad.attach(self.label, 2, 2, 1, 1)
        self.label = Gtk.Label("")
        self.output_pad.attach(self.label, 2, 3, 1, 1)

        # Update, Record, Track
        self.rec_pad = Gtk.Grid()
        # self.rec_pad.set_column_homogeneous(True)
        # self.rec_pad.set_row_homogeneous(True)
        self.update = ButtonWidget("Update", "update")
        self.update.connect("clicked", self.on_update)
        self.record = ButtonWidget("Record", "record")
        self.record.connect("clicked", self.on_record)
        self.track = ButtonWidget("Track", "track")
        self.track.connect("clicked", self.on_track)
        self.rec_pad.attach(self.update, 0, 0, 1, 1)
        self.rec_pad.attach(self.record, 2, 0, 1, 1)
        self.rec_pad.attach(self.track, 0, 2, 1, 1)
        self.label = Gtk.Label("")
        self.rec_pad.attach(self.label, 0, 1, 1, 1)
        self.label = Gtk.Label("")
        self.rec_pad.attach(self.label, 0, 3, 1, 1)
        self.label = Gtk.Label("")
        self.rec_pad.attach(self.label, 1, 3, 1, 1)

        # Thru, Channel, +, -, All, @, +%, -%
        self.thru_pad = Gtk.Grid()
        # self.thru_pad.set_column_homogeneous(True)
        # self.thru_pad.set_row_homogeneous(True)
        self.thru = ButtonWidget("Thru", "thru")
        self.thru.connect("clicked", self.on_thru)
        self.channel = ButtonWidget("Ch", "ch")
        self.channel.connect("clicked", self.on_channel)
        self.plus = ButtonWidget("+", "plus")
        self.plus.connect("clicked", self.on_plus)
        self.minus = ButtonWidget("-", "minus")
        self.minus.connect("clicked", self.on_minus)
        self.all = ButtonWidget("All", "all")
        self.all.connect("clicked", self.on_all)
        self.at_level = ButtonWidget("@", "at")
        self.at_level.connect("clicked", self.on_at)
        self.percent_plus = ButtonWidget("+%", "percent_plus")
        self.percent_plus.connect("clicked", self.on_percent_plus)
        self.percent_minus = ButtonWidget("-%", "percent_minus")
        self.percent_minus.connect("clicked", self.on_percent_minus)
        self.thru_pad.attach(self.thru, 0, 0, 1, 1)
        self.thru_pad.attach(self.channel, 0, 1, 1, 1)
        self.thru_pad.attach(self.plus, 0, 2, 1, 1)
        self.thru_pad.attach(self.minus, 0, 3, 1, 1)
        self.thru_pad.attach(self.all, 0, 4, 1, 1)
        self.thru_pad.attach(self.at_level, 2, 0, 1, 1)
        self.thru_pad.attach(self.percent_plus, 2, 1, 1, 1)
        self.thru_pad.attach(self.percent_minus, 2, 2, 1, 1)
        self.label = Gtk.Label("")
        self.thru_pad.attach(self.label, 1, 0, 1, 1)
        self.label = Gtk.Label("")
        self.thru_pad.attach(self.label, 2, 3, 1, 1)
        self.label = Gtk.Label("")
        self.thru_pad.attach(self.label, 2, 4, 1, 1)

        # Insert, Delete, Esc, Modify, Up, Down, Left, Right
        self.modify_pad = Gtk.Grid()
        # self.modify_pad.set_column_homogeneous(True)
        # self.modify_pad.set_row_homogeneous(True)
        self.insert = ButtonWidget("Insert")
        self.delete = ButtonWidget("Delete")
        self.esc = ButtonWidget("Esc")
        self.modify = ButtonWidget("Modify")
        self.up = ButtonWidget("^", "up")
        self.up.connect("clicked", self.on_up)
        self.down = ButtonWidget("v", "down")
        self.down.connect("clicked", self.on_down)
        self.left = ButtonWidget("<", "left")
        self.left.connect("clicked", self.on_left)
        self.right = ButtonWidget(">", "right")
        self.right.connect("clicked", self.on_right)
        self.modify_pad.attach(self.insert, 0, 0, 1, 1)
        self.modify_pad.attach(self.delete, 2, 0, 1, 1)
        self.modify_pad.attach(self.esc, 0, 2, 1, 1)
        self.modify_pad.attach(self.modify, 2, 2, 1, 1)
        self.modify_pad.attach(self.up, 1, 2, 1, 1)
        self.modify_pad.attach(self.down, 1, 3, 1, 1)
        self.modify_pad.attach(self.left, 0, 3, 1, 1)
        self.modify_pad.attach(self.right, 2, 3, 1, 1)
        self.label = Gtk.Label("")
        self.modify_pad.attach(self.label, 0, 1, 1, 1)

        # Controller for channels level
        self.wheel = ControllerWidget(text="wheel")
        self.wheel.connect("moved", self.on_wheel)
        self.wheel.connect("clicked", self.controller_clicked)

        # Crossfade and more
        self.crossfade_pad = Gtk.Grid()
        # self.crossfade_pad.set_column_homogeneous(True)
        # self.crossfade_pad.set_row_homogeneous(True)
        self.live = ButtonWidget("Live")
        self.format = ButtonWidget("Format")
        self.blind = ButtonWidget("Blind")
        self.goto = ButtonWidget("Goto", "goto")
        self.goto.connect("clicked", self.on_goto)
        self.a = ButtonWidget("A")
        self.b = ButtonWidget("B")

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
        self.scale_a.connect("clicked", self.scale_clicked)
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
        self.scale_b.connect("clicked", self.scale_clicked)
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
        self.label = Gtk.Label("")
        self.crossfade_pad.attach(self.label, 0, 7, 1, 1)

        # Independents
        self.independents = Gtk.Grid()
        self.independent1 = KnobWidget(text="inde_1")
        self.independent1.connect("clicked", self.inde_clicked)
        self.independent1.connect("changed", self.inde_changed)
        self.independent1.value = App().independents.independents[0].level
        self.independent2 = KnobWidget(text="inde_2")
        self.independent2.connect("clicked", self.inde_clicked)
        self.independent2.connect("changed", self.inde_changed)
        self.independent2.value = App().independents.independents[1].level
        self.independent3 = KnobWidget(text="inde_3")
        self.independent3.connect("clicked", self.inde_clicked)
        self.independent3.connect("changed", self.inde_changed)
        self.independent3.value = App().independents.independents[2].level
        self.independent4 = KnobWidget(text="inde_4")
        self.independent4.connect("clicked", self.inde_clicked)
        self.independent4.connect("changed", self.inde_changed)
        self.independent4.value = App().independents.independents[3].level
        self.independent5 = KnobWidget(text="inde_5")
        self.independent5.connect("clicked", self.inde_clicked)
        self.independent5.connect("changed", self.inde_changed)
        self.independent5.value = App().independents.independents[4].level
        self.independent6 = KnobWidget(text="inde_6")
        self.independent6.connect("clicked", self.inde_clicked)
        self.independent6.connect("changed", self.inde_changed)
        self.independent6.value = App().independents.independents[5].level
        self.independent7 = ToggleWidget(text="inde_7")
        self.independent8 = ToggleWidget(text="inde_8")
        self.independent9 = ToggleWidget(text="inde_9")
        self.independent7.connect("clicked", self.inde_clicked)
        if App().independents.independents[6].level:
            self.independent7.set_active(True)
            self.independent7.value = 255
        self.independent8.connect("clicked", self.inde_clicked)
        if App().independents.independents[7].level:
            self.independent8.set_active(True)
            self.independent8.value = 255
        self.independent9.connect("clicked", self.inde_clicked)
        if App().independents.independents[8].level:
            self.independent9.set_active(True)
            self.independent9.value = 255
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
        # self.go_pad.set_column_homogeneous(True)
        # self.go_pad.set_row_homogeneous(True)
        self.go_button = GoWidget()
        self.go_button.connect("clicked", self.on_go)
        self.seq_plus = ButtonWidget("Seq+", "seq_plus")
        self.seq_plus.connect("clicked", self.on_seq_plus)
        self.seq_minus = ButtonWidget("Seq-", "seq_minus")
        self.seq_minus.connect("clicked", self.on_seq_minus)
        self.goback = ButtonWidget("Go Back", "go_back")
        self.goback.connect("clicked", self.on_go_back)
        self.pause = PauseWidget("Pause", "pause")
        self.pause.connect("clicked", self.on_pause)
        self.go_pad.attach(self.seq_minus, 0, 0, 1, 1)
        self.go_pad.attach(self.seq_plus, 1, 0, 1, 1)
        self.go_pad.attach(self.pause, 0, 1, 1, 1)
        self.go_pad.attach(self.goback, 1, 1, 1, 1)
        self.go_pad.attach(self.go_button, 0, 2, 2, 1)
        self.label = Gtk.Label("")
        self.go_pad.attach(self.label, 2, 3, 1, 1)

        # Masters
        self.masters_pad = Gtk.Grid()
        self.masters = []
        self.flashes = []
        for i in range(10):  # 10 Faders per page
            adjustment = Gtk.Adjustment(0, 0, 255, 1, 10, 0)
            self.masters.append(
                FaderWidget(
                    text="master_" + str(i + 1),
                    orientation=Gtk.Orientation.VERTICAL,
                    adjustment=adjustment,
                )
            )
            self.masters[i].set_vexpand(True)
            self.masters[i].set_draw_value(False)
            self.masters[i].set_inverted(True)
            self.masters[i].connect("value-changed", self.master_moved)
            self.masters[i].connect("clicked", self.master_clicked)
            self.flashes.append(FlashWidget(""))
            self.flashes[i].connect("button-press-event", self.flash_on)
            self.flashes[i].connect("button-release-event", self.flash_off)
            self.flashes[i].connect("clicked", self.on_flash)
            self.masters_pad.attach(self.masters[i], i, 0, 1, 1)
            self.masters_pad.attach(self.flashes[i], i, 1, 1, 1)
            text = "flash_" + str(i + 1)
            self.flashes[i].text = text
        for master in App().masters:
            if master.page == App().fader_page:
                index = master.number - 1
                # Flash with master's name
                self.flashes[index].label = master.text
                # Fader at master's value
                value = App().masters[index + ((App().fader_page - 1) * 10)].value
                self.masters[index].set_value(value)
        self.fader_pages = Gtk.Grid()
        self.fader_page_plus = ButtonWidget("Page+", "fader_page_plus")
        self.fader_page_plus.connect("clicked", self.on_fader_page)
        self.fader_page_minus = ButtonWidget("Page-", "fader_page_minus")
        self.fader_page_minus.connect("clicked", self.on_fader_page)
        self.page_number = Gtk.Label(App().fader_page)
        self.fader_pages.attach(self.fader_page_plus, 0, 0, 1, 1)
        self.fader_pages.attach(self.page_number, 0, 1, 1, 1)
        self.fader_pages.attach(self.fader_page_minus, 0, 2, 1, 1)
        self.masters_pad.attach(self.fader_pages, 11, 0, 1, 1)

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
        self.grid.attach(self.masters_pad, 6, 0, 1, 2)

        self.add(self.grid)

        # Send keyboard events to a dispatch function
        self.connect("key_press_event", App().window.live_view.on_key_press_event)

    def close(self, _widget, _param):
        """Mark Window as closed

        Returns:
            False
        """
        App().virtual_console = None
        return False

    def on_button_toggled(self, button, name):
        """MIDI learn On / Off

        Args:
            button: Button clicked
            name: Name of the button
        """
        if button.get_active() and name == "MIDI":
            self.midi_learn = True
            App().midi.midi_learn = " "
        elif name == "MIDI":
            self.midi_learn = False
            App().midi.midi_learn = ""
            App().virtual_console.queue_draw()

    def on_fader_page(self, widget):
        """Change fader page

        Args:
            widget: clicked button
        """
        if self.midi_learn:
            if widget is self.fader_page_plus:
                App().midi.midi_learn = "fader_page_plus"
            elif widget is self.fader_page_minus:
                App().midi.midi_learn = "fader_page_minus"
            self.queue_draw()
        else:
            if widget is self.fader_page_plus:
                App().fader_page += 1
                if App().fader_page > MAX_FADER_PAGE:
                    App().fader_page = 1
            elif widget is self.fader_page_minus:
                App().fader_page -= 1
                if App().fader_page < 1:
                    App().fader_page = MAX_FADER_PAGE
            self.page_number.set_label(str(App().fader_page))
            # Redraw Masters and Flashes
            for master in App().masters:
                if master.page == App().fader_page:
                    text = "master_" + str(
                        master.number + ((App().fader_page - 1) * 10)
                    )
                    self.masters[master.number - 1].text = text
                    val = master.value
                    self.masters[master.number - 1].set_value(val)
                    self.flashes[master.number - 1].label = master.text
                    self.flashes[master.number - 1].queue_draw()

    def on_time(self, _widget):
        """Time button"""
        if self.midi_learn:
            App().midi.midi_learn = "time"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_T
            App().window.on_key_press_event(None, event)

    def on_delay(self, _widget):
        """Delay button"""
        if self.midi_learn:
            App().midi.midi_learn = "delay"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_D
            App().window.on_key_press_event(None, event)

    def on_go(self, _widget):
        """Go"""
        if self.midi_learn:
            App().midi.midi_learn = "go"
            self.queue_draw()
        else:
            App().sequence.do_go(None, None)

    def on_go_back(self, _widget):
        """Go back"""
        if self.midi_learn:
            App().midi.midi_learn = "go_back"
            self.queue_draw()
        else:
            App().sequence.go_back(None, None)

    def on_pause(self, _widget):
        """Pause"""
        if self.midi_learn:
            App().midi.midi_learn = "pause"
            self.queue_draw()
        else:
            App().sequence.pause(None, None)

    def on_seq_plus(self, _widget):
        """Sequence +"""
        if self.midi_learn:
            App().midi.midi_learn = "seq_plus"
            self.queue_draw()
        else:
            App().sequence.sequence_plus()

    def on_seq_minus(self, _widget):
        """Sequence -"""
        if self.midi_learn:
            App().midi.midi_learn = "seq_minus"
            self.queue_draw()
        else:
            App().sequence.sequence_minus()

    def on_output(self, _widget):
        """Output"""
        if self.midi_learn:
            App().midi.midi_learn = "output"
            self.queue_draw()
        else:
            App().patch_outputs(None, None)

    def on_seq(self, _widget):
        """Seq"""
        if self.midi_learn:
            App().midi.midi_learn = "seq"
            self.queue_draw()
        else:
            App().sequences(None, None)

    def on_preset(self, _widget):
        """Preset"""
        if self.midi_learn:
            App().midi.midi_learn = "preset"
            self.queue_draw()
        else:
            App().memories_cb(None, None)

    def on_group(self, _widget):
        """Group"""
        if self.midi_learn:
            App().midi.midi_learn = "group"
            self.queue_draw()
        else:
            App().groups_cb(None, None)

    def on_track(self, _widget):
        """Track channels"""
        if self.midi_learn:
            App().midi.midi_learn = "track"
            self.queue_draw()
        else:
            App().track_channels(None, None)

    def on_goto(self, _widget):
        """Goto"""
        if self.midi_learn:
            App().midi.midi_learn = "goto"
            self.queue_draw()
        else:
            App().sequence.goto(App().window.keystring)
            App().window.keystring = ""
            App().window.statusbar.push(App().window.context_id, "")

    def on_channel(self, _widget):
        """Channel button"""
        if self.midi_learn:
            App().midi.midi_learn = "ch"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_c
            App().window.on_key_press_event(None, event)

    def on_thru(self, _widget):
        """Thru"""
        if self.midi_learn:
            App().midi.midi_learn = "thru"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_greater
            App().window.on_key_press_event(None, event)

    def on_plus(self, _widget):
        """+ button"""
        if self.midi_learn:
            App().midi.midi_learn = "plus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_plus
            App().window.on_key_press_event(None, event)

    def on_minus(self, _widget):
        """- button"""
        if self.midi_learn:
            App().midi.midi_learn = "minus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_minus
            App().window.on_key_press_event(None, event)

    def on_all(self, _widget):
        """All"""
        if self.midi_learn:
            App().midi.midi_learn = "all"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_a
            App().window.on_key_press_event(None, event)

    def on_at(self, _widget):
        """At level"""
        if self.midi_learn:
            App().midi.midi_learn = "at"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_equal
            App().window.on_key_press_event(None, event)

    def on_percent_plus(self, _widget):
        """% +"""
        if self.midi_learn:
            App().midi.midi_learn = "percent_plus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_exclam
            App().window.on_key_press_event(None, event)

    def on_percent_minus(self, _widget):
        """% -"""
        if self.midi_learn:
            App().midi.midi_learn = "percent_minus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_colon
            App().window.on_key_press_event(None, event)

    def on_update(self, _widget):
        """Update"""
        if self.midi_learn:
            App().midi.midi_learn = "update"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_U
            App().window.on_key_press_event(None, event)

    def on_record(self, _widget):
        """Record"""
        if self.midi_learn:
            App().midi.midi_learn = "record"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_R
            App().window.on_key_press_event(None, event)

    def on_right(self, _widget):
        """Right arrow"""
        if self.midi_learn:
            App().midi.midi_learn = "right"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Right
            App().window.on_key_press_event(None, event)

    def on_left(self, _widget):
        """Left arrow"""
        if self.midi_learn:
            App().midi.midi_learn = "left"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Left
            App().window.on_key_press_event(None, event)

    def on_up(self, _widget):
        """Up arrow"""
        if self.midi_learn:
            App().midi.midi_learn = "up"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Up
            App().window.on_key_press_event(None, event)

    def on_down(self, _widget):
        """Down arrow"""
        if self.midi_learn:
            App().midi.midi_learn = "down"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Down
            App().window.on_key_press_event(None, event)

    def on_clear(self, _widget):
        """Clear"""
        if self.midi_learn:
            App().midi.midi_learn = "clear"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_BackSpace
            App().window.on_key_press_event(None, event)

    def on_zero(self, _widget):
        """0"""
        if self.midi_learn:
            App().midi.midi_learn = "number_0"
            self.queue_draw()
        else:
            App().window.keystring += "0"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_1(self, _widget):
        """1"""
        if self.midi_learn:
            App().midi.midi_learn = "number_1"
            self.queue_draw()
        else:
            App().window.keystring += "1"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_2(self, _widget):
        """2"""
        if self.midi_learn:
            App().midi.midi_learn = "number_2"
            self.queue_draw()
        else:
            App().window.keystring += "2"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_3(self, _widget):
        """3"""
        if self.midi_learn:
            App().midi.midi_learn = "number_3"
            self.queue_draw()
        else:
            App().window.keystring += "3"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_4(self, _widget):
        """4"""
        if self.midi_learn:
            App().midi.midi_learn = "number_4"
            self.queue_draw()
        else:
            App().window.keystring += "4"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_5(self, _widget):
        """5"""
        if self.midi_learn:
            App().midi.midi_learn = "number_5"
            self.queue_draw()
        else:
            App().window.keystring += "5"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_6(self, _widget):
        """6"""
        if self.midi_learn:
            App().midi.midi_learn = "number_6"
            self.queue_draw()
        else:
            App().window.keystring += "6"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_7(self, _widget):
        """7"""
        if self.midi_learn:
            App().midi.midi_learn = "number_7"
            self.queue_draw()
        else:
            App().window.keystring += "7"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_8(self, _widget):
        """8"""
        if self.midi_learn:
            App().midi.midi_learn = "number_8"
            self.queue_draw()
        else:
            App().window.keystring += "8"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_9(self, _widget):
        """9"""
        if self.midi_learn:
            App().midi.midi_learn = "number_9"
            self.queue_draw()
        else:
            App().window.keystring += "9"
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def on_dot(self, _widget):
        """."""
        if self.midi_learn:
            App().midi.midi_learn = "dot"
            self.queue_draw()
        else:
            App().window.keystring += "."
            App().window.statusbar.push(App().window.context_id, App().window.keystring)

    def flash_on(self, widget, _event):
        """Flash button pressed

        Args:
            widget: Button clicked
        """
        if not self.midi_learn:
            for i, flash in enumerate(self.flashes):
                if flash == widget:
                    # Save Master's value
                    index = i + ((App().fader_page - 1) * 10)
                    App().masters[index].old_value = App().masters[index].value
                    self.masters[i].set_value(255)
                    App().masters[index].set_level(255)

    def flash_off(self, widget, _event):
        """Flash button released

        Args:
            widget: Button clicked
        """
        if not self.midi_learn:
            for i, flash in enumerate(self.flashes):
                if flash == widget:
                    # Restore Master's value
                    index = i + ((App().fader_page - 1) * 10)
                    self.masters[i].set_value(App().masters[index].old_value)
                    App().masters[index].set_level(App().masters[index].old_value)

    def on_flash(self, widget):
        """Flash button clicked

        Args:
            widget: Button clicked
        """
        if self.midi_learn:
            index = self.flashes.index(widget) + 1
            text = "flash_" + str(index)
            App().midi.midi_learn = text
            self.queue_draw()

    def master_moved(self, master):
        """Fader moved

        Args:
            master: FaderWidget
        """
        if self.midi_learn:
            index = self.masters.index(master) + 1
            text = "master_" + str(index)
            App().midi.midi_learn = text
            self.queue_draw()
        else:
            value = master.get_value()
            index = self.masters.index(master)
            index = index + ((App().fader_page - 1) * 10)
            App().masters[index].set_level(value)

    def master_clicked(self, master):
        """Fader clicked

        Args:
            master: FaderWidget
        """
        if self.midi_learn:
            index = self.masters.index(master) + 1
            text = "master_" + str(index)
            App().midi.midi_learn = text
            self.queue_draw()

    def scale_moved(self, scale):
        """Crossfade moved

        Args:
            scale (FaderWidget): xfade fader
        """
        if self.midi_learn:
            if scale == self.scale_a:
                App().midi.midi_learn = "crossfade_out"
            elif scale == self.scale_b:
                App().midi.midi_learn = "crossfade_in"
            self.queue_draw()
        else:
            value = scale.get_value()

            if scale == self.scale_a:
                App().crossfade.scale_a.set_value(value)
                if App().crossfade.manual:
                    App().crossfade.scale_moved(App().crossfade.scale_a)
            elif scale == self.scale_b:
                App().crossfade.scale_b.set_value(value)
                if App().crossfade.manual:
                    App().crossfade.scale_moved(App().crossfade.scale_b)

            if (
                self.scale_a.get_value() == 255
                and self.scale_b.get_value() == 255
                and App().crossfade.manual
            ):
                if self.scale_a.get_inverted():
                    self.scale_a.set_inverted(False)
                    self.scale_b.set_inverted(False)
                else:
                    self.scale_a.set_inverted(True)
                    self.scale_b.set_inverted(True)
                self.scale_a.set_value(0)
                self.scale_b.set_value(0)
                event = Gdk.Event(Gdk.EventType.BUTTON_RELEASE)
                self.scale_a.emit("button-release-event", event)
                self.scale_b.emit("button-release-event", event)

    def scale_clicked(self, scale):
        """Crossfade or Grand Master clicked

        Args:
            scale: FaderWidget
        """
        if self.midi_learn:
            if scale == self.scale_a:
                App().midi.midi_learn = "crossfade_out"
            elif scale == self.scale_b:
                App().midi.midi_learn = "crossfade_in"
            elif scale == self.scale_grand_master:
                App().midi.midi_learn = "gm"
            self.queue_draw()

    def grand_master_moved(self, scale):
        """Grand Master moved

        Args:
            scale: GM FaderWidget
        """
        if self.midi_learn:
            App().midi.midi_learn = "gm"
            self.queue_draw()
        else:
            value = scale.get_value()

            App().dmx.grand_master = value
            App().window.grand_master.queue_draw()

    def controller_clicked(self, widget):
        """Controller clicked

        Args:
            widget: Object clicked
        """
        if self.midi_learn and widget == self.wheel:
            App().midi.midi_learn = "wheel"
        self.queue_draw()

    def on_wheel(self, _widget, direction, step):
        """Wheel for channels level

        Args:
            direction (Gdk.ScrollDirection): Up or down
            step (int): increment or decrement step size
        """
        if self.midi_learn:
            return
        focus = App().window.get_focus()
        page = focus.get_current_page()
        child = focus.get_nth_page(page)
        channels_view = None
        if child == App().window.live_view.channels_view:
            channels_view = child
        elif child in (
            App().tabs.tabs["groups"],
            App().tabs.tabs["indes"],
            App().tabs.tabs["masters"],
            App().tabs.tabs["memories"],
            App().tabs.tabs["sequences"],
        ):
            channels_view = child.channels_view
        if channels_view:
            channels_view.wheel_level(step, direction)

    def inde_clicked(self, widget):
        """Independent clicked

        Args:
            widget: Object clicked
        """
        if self.midi_learn:
            if widget == self.independent1:
                App().midi.midi_learn = "inde_1"
            elif widget == self.independent2:
                App().midi.midi_learn = "inde_2"
            elif widget == self.independent3:
                App().midi.midi_learn = "inde_3"
            elif widget == self.independent4:
                App().midi.midi_learn = "inde_4"
            elif widget == self.independent5:
                App().midi.midi_learn = "inde_5"
            elif widget == self.independent6:
                App().midi.midi_learn = "inde_6"
            elif widget == self.independent7:
                App().midi.midi_learn = "inde_7"
                widget.set_active(False)
            elif widget == self.independent8:
                App().midi.midi_learn = "inde_8"
                widget.set_active(False)
            elif widget == self.independent9:
                App().midi.midi_learn = "inde_9"
                widget.set_active(False)
            self.queue_draw()
        else:
            if widget == self.independent7 and widget.get_active():
                App().independents.independents[6].level = 255
                App().independents.independents[6].update_dmx()
            elif widget == self.independent7 and not widget.get_active():
                App().independents.independents[6].level = 0
                App().independents.independents[6].update_dmx()
            if widget == self.independent8:
                if widget.get_active():
                    App().independents.independents[7].level = 255
                    App().independents.independents[7].update_dmx()
                elif not widget.get_active():
                    App().independents.independents[7].level = 0
                    App().independents.independents[7].update_dmx()
            if widget == self.independent9:
                if widget.get_active():
                    App().independents.independents[8].level = 255
                    App().independents.independents[8].update_dmx()
                elif not widget.get_active():
                    App().independents.independents[8].level = 0
                    App().independents.independents[8].update_dmx()

    def inde_changed(self, widget):
        """Independent value changed

        Args:
            widget: Object changed
        """
        if self.midi_learn:
            return
        if widget == self.independent1:
            App().independents.independents[0].level = widget.value
            App().independents.independents[0].update_dmx()
        elif widget == self.independent2:
            App().independents.independents[1].level = widget.value
            App().independents.independents[1].update_dmx()
        elif widget == self.independent3:
            App().independents.independents[2].level = widget.value
            App().independents.independents[2].update_dmx()
        elif widget == self.independent4:
            App().independents.independents[3].level = widget.value
            App().independents.independents[3].update_dmx()
        elif widget == self.independent5:
            App().independents.independents[4].level = widget.value
            App().independents.independents[4].update_dmx()
        elif widget == self.independent6:
            App().independents.independents[5].level = widget.value
            App().independents.independents[5].update_dmx()
