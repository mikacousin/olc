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
from gi.repository import Gdk, Gtk
from olc.define import MAX_FADER_PAGE, App
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
        super().__init__(title="Virtual Console")
        self.set_default_size(400, 300)

        # On close window
        self.connect("delete-event", self._close)

        # Header bar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = "Virtual Console"
        self.set_titlebar(self.header)
        self.midi = Gtk.ToggleButton("MIDI")
        self.midi.set_name("midi_toggle")
        self.midi.connect("toggled", self._on_button_toggled, "MIDI")
        self.header.pack_end(self.midi)

        # Numeric Pad
        self.num_pad = Gtk.Grid()
        # self.num_pad.set_column_homogeneous(True)
        # self.num_pad.set_row_homogeneous(True)
        self.zero = ButtonWidget("0", "number_0")
        self.zero.connect("clicked", self._on_zero)
        self.one = ButtonWidget("1", "number_1")
        self.one.connect("clicked", self._on_1)
        self.two = ButtonWidget("2", "number_2")
        self.two.connect("clicked", self._on_2)
        self.three = ButtonWidget("3", "number_3")
        self.three.connect("clicked", self._on_3)
        self.four = ButtonWidget("4", "number_4")
        self.four.connect("clicked", self._on_4)
        self.five = ButtonWidget("5", "number_5")
        self.five.connect("clicked", self._on_5)
        self.six = ButtonWidget("6", "number_6")
        self.six.connect("clicked", self._on_6)
        self.seven = ButtonWidget("7", "number_7")
        self.seven.connect("clicked", self._on_7)
        self.eight = ButtonWidget("8", "number_8")
        self.eight.connect("clicked", self._on_8)
        self.nine = ButtonWidget("9", "number_9")
        self.nine.connect("clicked", self._on_9)
        self.dot = ButtonWidget(".", "dot")
        self.dot.connect("clicked", self._on_dot)
        self.clear = ButtonWidget("C", "clear")
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
        self.time = ButtonWidget("Time", "time")
        self.time.connect("clicked", self._on_time)
        self.delay = ButtonWidget("Delay", "delay")
        self.delay.connect("clicked", self._on_delay)
        self.button_in = ButtonWidget("In")
        self.button_out = ButtonWidget("Out")
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
        self.seq.connect("clicked", self._on_seq)
        self.empty1 = ButtonWidget(" ")
        self.empty2 = ButtonWidget(" ")
        self.preset = ButtonWidget("Preset", "preset")
        self.preset.connect("clicked", self._on_preset)
        self.group = ButtonWidget("Group", "group")
        self.group.connect("clicked", self._on_group)
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
        adjustment = Gtk.Adjustment(round(App().backend.dmx.grand_master.value * 255),
                                    0, 255, 1, 10, 0)
        self.scale_grand_master = FaderWidget(text="gm",
                                              orientation=Gtk.Orientation.VERTICAL,
                                              adjustment=adjustment)
        self.scale_grand_master.value = App().backend.dmx.grand_master
        self.scale_grand_master.connect("clicked", self._scale_clicked)
        self.scale_grand_master.connect("value-changed", self.grand_master_moved)
        self.scale_grand_master.set_draw_value(False)
        self.scale_grand_master.set_vexpand(True)
        self.scale_grand_master.set_inverted(True)
        self.output = ButtonWidget("Output", "output")
        self.output.connect("clicked", self._on_output)
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
        self.update.connect("clicked", self._on_update)
        self.record = ButtonWidget("Record", "record")
        self.record.connect("clicked", self._on_record)
        self.track = ButtonWidget("Track", "track")
        self.track.connect("clicked", self._on_track)
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
        self.thru.connect("clicked", self._on_thru)
        self.channel = ButtonWidget("Ch", "ch")
        self.channel.connect("clicked", self._on_channel)
        self.plus = ButtonWidget("+", "plus")
        self.plus.connect("clicked", self._on_plus)
        self.minus = ButtonWidget("-", "minus")
        self.minus.connect("clicked", self._on_minus)
        self.all = ButtonWidget("All", "all")
        self.all.connect("clicked", self._on_all)
        self.at_level = ButtonWidget("@", "at")
        self.at_level.connect("clicked", self._on_at)
        self.percent_plus = ButtonWidget("+%", "percent_plus")
        self.percent_plus.connect("clicked", self._on_percent_plus)
        self.percent_minus = ButtonWidget("-%", "percent_minus")
        self.percent_minus.connect("clicked", self._on_percent_minus)
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

        # Insert, Delete, Escape, Modify, Up, Down, Left, Right
        self.modify_pad = Gtk.Grid()
        # self.modify_pad.set_column_homogeneous(True)
        # self.modify_pad.set_row_homogeneous(True)
        self.insert = ButtonWidget("Insert")
        self.delete = ButtonWidget("Delete")
        self.esc = ButtonWidget("Esc")
        self.modify = ButtonWidget("Modify")
        self.up = ButtonWidget("^", "up")
        self.up.connect("clicked", self._on_up)
        self.down = ButtonWidget("v", "down")
        self.down.connect("clicked", self._on_down)
        self.left = ButtonWidget("<", "left")
        self.left.connect("clicked", self._on_left)
        self.right = ButtonWidget(">", "right")
        self.right.connect("clicked", self._on_right)
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
        self.wheel.connect("moved", self._on_wheel)
        self.wheel.connect("clicked", self._controller_clicked)

        # Crossfade and more
        self.crossfade_pad = Gtk.Grid()
        # self.crossfade_pad.set_column_homogeneous(True)
        # self.crossfade_pad.set_row_homogeneous(True)
        self.live = ButtonWidget("Live")
        self.format = ButtonWidget("Format")
        self.blind = ButtonWidget("Blind")
        self.goto = ButtonWidget("Goto", "goto")
        self.goto.connect("clicked", self._on_goto)
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
        self.label = Gtk.Label("")
        self.crossfade_pad.attach(self.label, 0, 7, 1, 1)

        # Independents
        self.independents = Gtk.Grid()
        self.independent1 = KnobWidget(text="inde_1")
        self.independent1.connect("clicked", self._inde_clicked)
        self.independent1.connect("changed", self._inde_changed)
        self.independent1.value = App().lightshow.independents.independents[0].level
        self.independent2 = KnobWidget(text="inde_2")
        self.independent2.connect("clicked", self._inde_clicked)
        self.independent2.connect("changed", self._inde_changed)
        self.independent2.value = App().lightshow.independents.independents[1].level
        self.independent3 = KnobWidget(text="inde_3")
        self.independent3.connect("clicked", self._inde_clicked)
        self.independent3.connect("changed", self._inde_changed)
        self.independent3.value = App().lightshow.independents.independents[2].level
        self.independent4 = KnobWidget(text="inde_4")
        self.independent4.connect("clicked", self._inde_clicked)
        self.independent4.connect("changed", self._inde_changed)
        self.independent4.value = App().lightshow.independents.independents[3].level
        self.independent5 = KnobWidget(text="inde_5")
        self.independent5.connect("clicked", self._inde_clicked)
        self.independent5.connect("changed", self._inde_changed)
        self.independent5.value = App().lightshow.independents.independents[4].level
        self.independent6 = KnobWidget(text="inde_6")
        self.independent6.connect("clicked", self._inde_clicked)
        self.independent6.connect("changed", self._inde_changed)
        self.independent6.value = App().lightshow.independents.independents[5].level
        self.independent7 = ToggleWidget(text="inde_7")
        self.independent8 = ToggleWidget(text="inde_8")
        self.independent9 = ToggleWidget(text="inde_9")
        self.independent7.connect("clicked", self._inde_clicked)
        if App().lightshow.independents.independents[6].level:
            self.independent7.set_active(True)
            self.independent7.value = 255
        self.independent8.connect("clicked", self._inde_clicked)
        if App().lightshow.independents.independents[7].level:
            self.independent8.set_active(True)
            self.independent8.value = 255
        self.independent9.connect("clicked", self._inde_clicked)
        if App().lightshow.independents.independents[8].level:
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
        self.go_button = GoWidget()
        self.go_button.connect("clicked", self._on_go)
        self.seq_plus = ButtonWidget("Seq+", "seq_plus")
        self.seq_plus.connect("clicked", self._on_seq_plus)
        self.seq_minus = ButtonWidget("Seq-", "seq_minus")
        self.seq_minus.connect("clicked", self._on_seq_minus)
        self.goback = ButtonWidget("Go Back", "go_back")
        self.goback.connect("clicked", self._on_go_back)
        self.pause = PauseWidget("Pause", "pause")
        self.pause.connect("clicked", self._on_pause)
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
                    text=f"master_{i + 1}",
                    orientation=Gtk.Orientation.VERTICAL,
                    adjustment=adjustment,
                ))
            self.masters[i].set_vexpand(True)
            self.masters[i].set_draw_value(False)
            self.masters[i].set_inverted(True)
            self.masters[i].connect("value-changed", self.master_moved)
            self.masters[i].connect("clicked", self._master_clicked)
            self.flashes.append(FlashWidget(""))
            self.flashes[i].connect("button-press-event", self._flash_on)
            self.flashes[i].connect("button-release-event", self._flash_off)
            self.flashes[i].connect("clicked", self._on_flash)
            self.masters_pad.attach(self.masters[i], i, 0, 1, 1)
            self.masters_pad.attach(self.flashes[i], i, 1, 1, 1)
            text = f"flash_{i + 1}"
            self.flashes[i].text = text
        for fader in App().lightshow.faders:
            if fader.page == App().fader_page:
                index = fader.number - 1
                # Flash with master's name
                self.flashes[index].label = fader.text
                # Fader at master's value
                value = App().lightshow.faders[index +
                                               ((App().fader_page - 1) * 10)].value
                self.masters[index].set_value(value)
        self.fader_pages = Gtk.Grid()
        self.fader_page_plus = ButtonWidget("Page+", "fader_page_plus")
        self.fader_page_plus.connect("clicked", self._on_fader_page)
        self.fader_page_minus = ButtonWidget("Page-", "fader_page_minus")
        self.fader_page_minus.connect("clicked", self._on_fader_page)
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

    def _close(self, _widget, _param):
        """Mark Window as closed

        Returns:
            False
        """
        App().virtual_console = None
        return False

    def _on_button_toggled(self, button, name):
        """MIDI learn On / Off

        Args:
            button: Button clicked
            name: Name of the button
        """
        if button.get_active() and name == "MIDI":
            App().midi.learning = " "
        elif name == "MIDI":
            App().midi.learning = ""
            App().virtual_console.queue_draw()

    def _on_fader_page(self, widget):
        """Change fader page

        Args:
            widget: clicked button
        """
        if App().midi.learning:
            if widget is self.fader_page_plus:
                App().midi.learning = "fader_page_plus"
            elif widget is self.fader_page_minus:
                App().midi.learning = "fader_page_minus"
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
            for master in App().lightshow.faders:
                if master.page == App().fader_page:
                    text = f"master_{master.number + ((App().fader_page - 1) * 10)}"
                    self.masters[master.number - 1].text = text
                    val = master.value
                    self.masters[master.number - 1].set_value(val)
                    self.flashes[master.number - 1].label = master.text
                    self.flashes[master.number - 1].queue_draw()
            App().midi.messages.lcd.show_masters()

    def _on_time(self, _widget):
        """Time button"""
        if App().midi.learning:
            App().midi.learning = "time"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_T
            App().window.on_key_press_event(None, event)

    def _on_delay(self, _widget):
        """Delay button"""
        if App().midi.learning:
            App().midi.learning = "delay"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_D
            App().window.on_key_press_event(None, event)

    def _on_go(self, _widget):
        """Go"""
        if App().midi.learning:
            App().midi.learning = "go"
            self.queue_draw()
        else:
            App().lightshow.main_playback.do_go(None, None)

    def _on_go_back(self, _widget):
        """Go back"""
        if App().midi.learning:
            App().midi.learning = "go_back"
            self.queue_draw()
        else:
            App().lightshow.main_playback.go_back(None, None)

    def _on_pause(self, _widget):
        """Pause"""
        if App().midi.learning:
            App().midi.learning = "pause"
            self.queue_draw()
        else:
            App().lightshow.main_playback.pause(None, None)

    def _on_seq_plus(self, _widget):
        """Sequence +"""
        if App().midi.learning:
            App().midi.learning = "seq_plus"
            self.queue_draw()
        else:
            App().lightshow.main_playback.sequence_plus()

    def _on_seq_minus(self, _widget):
        """Sequence -"""
        if App().midi.learning:
            App().midi.learning = "seq_minus"
            self.queue_draw()
        else:
            App().lightshow.main_playback.sequence_minus()

    def _on_output(self, _widget):
        """Output"""
        if App().midi.learning:
            App().midi.learning = "output"
            self.queue_draw()
        else:
            App().patch_outputs(None, None)

    def _on_seq(self, _widget):
        """Seq"""
        if App().midi.learning:
            App().midi.learning = "seq"
            self.queue_draw()
        else:
            App().lightshow.main_playback(None, None)

    def _on_preset(self, _widget):
        """Preset"""
        if App().midi.learning:
            App().midi.learning = "preset"
            self.queue_draw()
        else:
            App().memories_cb(None, None)

    def _on_group(self, _widget):
        """Group"""
        if App().midi.learning:
            App().midi.learning = "group"
            self.queue_draw()
        else:
            App().groups_cb(None, None)

    def _on_track(self, _widget):
        """Track channels"""
        if App().midi.learning:
            App().midi.learning = "track"
            self.queue_draw()
        else:
            App().track_channels(None, None)

    def _on_goto(self, _widget):
        """Goto"""
        if App().midi.learning:
            App().midi.learning = "goto"
            self.queue_draw()
        else:
            App().lightshow.main_playback.goto(App().window.commandline.get_string())
            App().window.commandline.set_string("")

    def _on_channel(self, _widget):
        """Channel button"""
        if App().midi.learning:
            App().midi.learning = "ch"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_c
            App().window.on_key_press_event(None, event)

    def _on_thru(self, _widget):
        """Thru"""
        if App().midi.learning:
            App().midi.learning = "thru"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_greater
            App().window.on_key_press_event(None, event)

    def _on_plus(self, _widget):
        """+ button"""
        if App().midi.learning:
            App().midi.learning = "plus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_plus
            App().window.on_key_press_event(None, event)

    def _on_minus(self, _widget):
        """- button"""
        if App().midi.learning:
            App().midi.learning = "minus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_minus
            App().window.on_key_press_event(None, event)

    def _on_all(self, _widget):
        """All"""
        if App().midi.learning:
            App().midi.learning = "all"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_a
            App().window.on_key_press_event(None, event)

    def _on_at(self, _widget):
        """At level"""
        if App().midi.learning:
            App().midi.learning = "at"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_equal
            App().window.on_key_press_event(None, event)

    def _on_percent_plus(self, _widget):
        """% +"""
        if App().midi.learning:
            App().midi.learning = "percent_plus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_exclam
            App().window.on_key_press_event(None, event)

    def _on_percent_minus(self, _widget):
        """% -"""
        if App().midi.learning:
            App().midi.learning = "percent_minus"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_colon
            App().window.on_key_press_event(None, event)

    def _on_update(self, _widget):
        """Update"""
        if App().midi.learning:
            App().midi.learning = "update"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_U
            App().window.on_key_press_event(None, event)

    def _on_record(self, _widget):
        """Record"""
        if App().midi.learning:
            App().midi.learning = "record"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_R
            App().window.on_key_press_event(None, event)

    def _on_right(self, _widget):
        """Right arrow"""
        if App().midi.learning:
            App().midi.learning = "right"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Right
            App().window.on_key_press_event(None, event)

    def _on_left(self, _widget):
        """Left arrow"""
        if App().midi.learning:
            App().midi.learning = "left"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Left
            App().window.on_key_press_event(None, event)

    def _on_up(self, _widget):
        """Up arrow"""
        if App().midi.learning:
            App().midi.learning = "up"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Up
            App().window.on_key_press_event(None, event)

    def _on_down(self, _widget):
        """Down arrow"""
        if App().midi.learning:
            App().midi.learning = "down"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_Down
            App().window.on_key_press_event(None, event)

    def _on_clear(self, _widget):
        """Clear"""
        if App().midi.learning:
            App().midi.learning = "clear"
            self.queue_draw()
        else:
            event = Gdk.EventKey()
            event.keyval = Gdk.KEY_BackSpace
            App().window.on_key_press_event(None, event)

    def _on_zero(self, _widget):
        """0"""
        if App().midi.learning:
            App().midi.learning = "number_0"
            self.queue_draw()
        else:
            App().window.commandline.add_string("0")

    def _on_1(self, _widget):
        """1"""
        if App().midi.learning:
            App().midi.learning = "number_1"
            self.queue_draw()
        else:
            App().window.commandline.add_string("1")

    def _on_2(self, _widget):
        """2"""
        if App().midi.learning:
            App().midi.learning = "number_2"
            self.queue_draw()
        else:
            App().window.commandline.add_string("2")

    def _on_3(self, _widget):
        """3"""
        if App().midi.learning:
            App().midi.learning = "number_3"
            self.queue_draw()
        else:
            App().window.commandline.add_string("3")

    def _on_4(self, _widget):
        """4"""
        if App().midi.learning:
            App().midi.learning = "number_4"
            self.queue_draw()
        else:
            App().window.commandline.add_string("4")

    def _on_5(self, _widget):
        """5"""
        if App().midi.learning:
            App().midi.learning = "number_5"
            self.queue_draw()
        else:
            App().window.commandline.add_string("5")

    def _on_6(self, _widget):
        """6"""
        if App().midi.learning:
            App().midi.learning = "number_6"
            self.queue_draw()
        else:
            App().window.commandline.add_string("6")

    def _on_7(self, _widget):
        """7"""
        if App().midi.learning:
            App().midi.learning = "number_7"
            self.queue_draw()
        else:
            App().window.commandline.add_string("7")

    def _on_8(self, _widget):
        """8"""
        if App().midi.learning:
            App().midi.learning = "number_8"
            self.queue_draw()
        else:
            App().window.commandline.add_string("8")

    def _on_9(self, _widget):
        """9"""
        if App().midi.learning:
            App().midi.learning = "number_9"
            self.queue_draw()
        else:
            App().window.commandline.add_string("9")

    def _on_dot(self, _widget):
        """."""
        if App().midi.learning:
            App().midi.learning = "dot"
            self.queue_draw()
        else:
            App().window.commandline.add_string(".")

    def _flash_on(self, widget, _event):
        """Flash button pressed

        Args:
            widget: Button clicked
        """
        if not App().midi.learning:
            for i, flash in enumerate(self.flashes):
                if flash == widget:
                    index = i + ((App().fader_page - 1) * 10)
                    App().lightshow.faders[index].flash_on()

    def _flash_off(self, widget, _event):
        """Flash button released

        Args:
            widget: Button clicked
        """
        if not App().midi.learning:
            for i, flash in enumerate(self.flashes):
                if flash == widget:
                    index = i + ((App().fader_page - 1) * 10)
                    App().lightshow.faders[index].flash_off()

    def _on_flash(self, widget):
        """Flash button clicked

        Args:
            widget: Button clicked
        """
        if App().midi.learning:
            index = self.flashes.index(widget) + 1
            text = f"flash_{index}"
            App().midi.learning = text
            self.queue_draw()

    def master_moved(self, master):
        """Fader moved

        Args:
            master: FaderWidget
        """
        if App().midi.learning:
            index = self.masters.index(master) + 1
            text = f"master_{index}"
            App().midi.learning = text
            self.queue_draw()
        else:
            value = master.get_value()
            index = self.masters.index(master)
            index = index + ((App().fader_page - 1) * 10)
            App().lightshow.faders[index].set_level(value)
            midi_fader = App().midi.faders.faders[self.masters.index(master)]
            midi_fader.set_state(value)

    def _master_clicked(self, master):
        """Fader clicked

        Args:
            master: FaderWidget
        """
        if App().midi.learning:
            index = self.masters.index(master) + 1
            text = f"master_{index}"
            App().midi.learning = text
            self.queue_draw()

    def scale_moved(self, scale):
        """Crossfade moved

        Args:
            scale (FaderWidget): crossfade fader
        """
        if App().midi.learning:
            if scale == self.scale_a:
                App().midi.learning = "crossfade_out"
            elif scale == self.scale_b:
                App().midi.learning = "crossfade_in"
            self.queue_draw()
        else:
            value = scale.get_value()

            if scale == self.scale_a:
                App().crossfade.scale_a.set_value(value)
                midi_fader = App().midi.xfade.fader_out
                midi_fader.set_state(value)
                if App().crossfade.manual:
                    App().crossfade.scale_moved(App().crossfade.scale_a)
            elif scale == self.scale_b:
                App().crossfade.scale_b.set_value(value)
                midi_fader = App().midi.xfade.fader_in
                midi_fader.set_state(value)
                if App().crossfade.manual:
                    App().crossfade.scale_moved(App().crossfade.scale_b)

    def _scale_clicked(self, scale):
        """Crossfade or Grand Master clicked

        Args:
            scale: FaderWidget
        """
        if App().midi.learning:
            if scale == self.scale_a:
                App().midi.learning = "crossfade_out"
            elif scale == self.scale_b:
                App().midi.learning = "crossfade_in"
            elif scale == self.scale_grand_master:
                App().midi.learning = "gm"
            self.queue_draw()

    def grand_master_moved(self, scale):
        """Grand Master moved

        Args:
            scale: GM FaderWidget
        """
        if App().midi.learning:
            App().midi.learning = "gm"
            self.queue_draw()
        else:
            value = scale.get_value()
            App().backend.dmx.grand_master.set_level(value / 255)
            App().window.grand_master.queue_draw()
            midi_fader = App().midi.faders.gm_fader
            midi_fader.set_state(value)

    def _controller_clicked(self, widget):
        """Controller clicked

        Args:
            widget: Object clicked
        """
        if App().midi.learning and widget == self.wheel:
            App().midi.learning = "wheel"
        self.queue_draw()

    def _on_wheel(self, _widget, direction, step):
        """Wheel for channels level

        Args:
            direction (Gdk.ScrollDirection): Up or down
            step (int): increment or decrement step size
        """
        if App().midi.learning:
            return
        child = App().window.get_active_tab()
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

    def _inde_clicked(self, widget):
        """Independent clicked

        Args:
            widget: Object clicked
        """
        if App().midi.learning:
            if widget == self.independent1:
                App().midi.learning = "inde_1"
            elif widget == self.independent2:
                App().midi.learning = "inde_2"
            elif widget == self.independent3:
                App().midi.learning = "inde_3"
            elif widget == self.independent4:
                App().midi.learning = "inde_4"
            elif widget == self.independent5:
                App().midi.learning = "inde_5"
            elif widget == self.independent6:
                App().midi.learning = "inde_6"
            elif widget == self.independent7:
                App().midi.learning = "inde_7"
                widget.set_active(False)
            elif widget == self.independent8:
                App().midi.learning = "inde_8"
                widget.set_active(False)
            elif widget == self.independent9:
                App().midi.learning = "inde_9"
                widget.set_active(False)
            self.queue_draw()
        else:
            if widget == self.independent7 and widget.get_active():
                App().lightshow.independents.independents[6].level = 255
                App().lightshow.independents.independents[6].update_dmx()
            elif widget == self.independent7 and not widget.get_active():
                App().lightshow.independents.independents[6].level = 0
                App().lightshow.independents.independents[6].update_dmx()
            if widget == self.independent8:
                if widget.get_active():
                    App().lightshow.independents.independents[7].level = 255
                    App().lightshow.independents.independents[7].update_dmx()
                elif not widget.get_active():
                    App().lightshow.independents.independents[7].level = 0
                    App().lightshow.independents.independents[7].update_dmx()
            if widget == self.independent9:
                if widget.get_active():
                    App().lightshow.independents.independents[8].level = 255
                    App().lightshow.independents.independents[8].update_dmx()
                elif not widget.get_active():
                    App().lightshow.independents.independents[8].level = 0
                    App().lightshow.independents.independents[8].update_dmx()

    def _inde_changed(self, widget):
        """Independent value changed

        Args:
            widget: Object changed
        """
        if App().midi.learning:
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
        value = widget.value
        inde = App().lightshow.independents.independents[index]
        midi_fader = App().midi.faders.inde_faders[index]
        inde.set_level(value)
        midi_fader.set_state(value)
