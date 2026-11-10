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
from __future__ import annotations

import typing

from gi.repository import Gdk, GLib, Gtk

from olc.core.parser.tokens import TokenType
from olc.gtk3.widgets.button import ButtonWidget
from olc.gtk3.widgets.controller import ControllerWidget
from olc.gtk3.widgets.fader import FaderWidget
from olc.gtk3.widgets.flash import FlashWidget
from olc.gtk3.widgets.go import GoWidget
from olc.gtk3.widgets.knob import KnobWidget
from olc.gtk3.widgets.pause import PauseWidget
from olc.gtk3.widgets.toggle import ToggleWidget
from olc.independent import IndependentType

if typing.TYPE_CHECKING:
    from olc.core.commandline import CoreCommandLine
    from olc.gtk3.application import Application


# pylint: disable=too-many-instance-attributes
class VirtualConsoleWindow(Gtk.Window):
    """Virtual Console Window"""

    app: Application
    commandline: CoreCommandLine
    blackout: Gtk.ToggleButton
    midi: Gtk.ToggleButton
    shortcuts_toggle: Gtk.ToggleButton
    is_holding_f1: bool
    updating_blackout: bool

    # pylint: disable=too-many-statements
    def __init__(self, app: Application) -> None:
        self.app = app
        self.commandline = app.core.commandline
        self.is_holding_f1 = False
        self.updating_fader = False
        self.updating_independent = False
        self.updating_blackout = False

        super().__init__(title="Virtual Console")
        self.set_default_size(400, 300)

        # On close window
        self.connect("delete-event", self._close)
        self.connect("focus-out-event", self._on_focus_out)

        # Header bar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = "Virtual Console"
        self.set_titlebar(self.header)

        # Blackout toggle button
        self.blackout = Gtk.ToggleButton(label="BLACKOUT")
        self.blackout.get_style_context().add_class("olc-blackout-toggle")
        self.blackout.set_tooltip_text("Toggle Scenic Blackout (DBO) (Ctrl+Shift+B)")
        self.blackout.connect("toggled", self._on_blackout_toggled)
        self.header.pack_start(self.blackout)

        # Park alert indicator button
        self.park_indicator = Gtk.Button(label="PARK")
        self.park_indicator.get_style_context().add_class("olc-park-indicator")
        self.park_indicator.set_tooltip_text(
            "Parked channels or addresses active. Click to unpark all."
        )
        self.park_indicator.set_no_show_all(True)
        self.park_indicator.set_visible(False)
        self.park_indicator.connect("clicked", self._on_park_indicator_clicked)
        self.header.pack_start(self.park_indicator)

        self.midi = Gtk.ToggleButton(label="MIDI")
        self.midi.get_style_context().add_class("olc-midi-toggle")
        self.midi.connect("toggled", self._on_button_toggled, "MIDI")
        self.header.pack_end(self.midi)

        # Keyboard shortcuts toggle button
        self.shortcuts_toggle = Gtk.ToggleButton(label="⌨")
        self.shortcuts_toggle.get_style_context().add_class("olc-shortcuts-toggle")
        self.shortcuts_toggle.set_tooltip_text(
            "Afficher les raccourcis clavier (ou maintenir F1)"
        )
        self.shortcuts_toggle.connect("toggled", self._on_shortcuts_toggled)
        self.header.pack_end(self.shortcuts_toggle)

        # Initial blackout display state
        initial_blackout = bool(getattr(self.app.core, "blackout_active", False))
        backend = getattr(self.app.core, "backend", None)
        if backend and hasattr(backend, "dmx"):
            initial_blackout = bool(getattr(backend.dmx, "blackout", initial_blackout))
        self.update_blackout_display(initial_blackout)

        # Zone 1: Numeric Pad & Target Keys (4x5)
        self.num_pad = Gtk.Grid()
        self.channel = ButtonWidget(label="Channel", text="channel", shortcut_text="C")
        self.channel.connect("clicked", self._on_channel)
        self.group = ButtonWidget(label="Group", text="group", shortcut_text="G")
        self.group.connect("clicked", self._on_group)
        self.cue = ButtonWidget(label="Cue", text="cue", shortcut_text="Q")
        self.cue.connect("clicked", self._on_cue)
        self.address = ButtonWidget(label="Address", text="address", shortcut_text="⇧D")
        self.address.connect("clicked", self._on_address)

        self.seven = ButtonWidget(label="7", text="number_7", shortcut_text="7")
        self.seven.connect("clicked", self._on_7)
        self.eight = ButtonWidget(label="8", text="number_8", shortcut_text="8")
        self.eight.connect("clicked", self._on_8)
        self.nine = ButtonWidget(label="9", text="number_9", shortcut_text="9")
        self.nine.connect("clicked", self._on_9)
        self.thru = ButtonWidget(label="Thru", text="thru", shortcut_text="T")
        self.thru.connect("clicked", self._on_thru)

        self.four = ButtonWidget(label="4", text="number_4", shortcut_text="4")
        self.four.connect("clicked", self._on_4)
        self.five = ButtonWidget(label="5", text="number_5", shortcut_text="5")
        self.five.connect("clicked", self._on_5)
        self.six = ButtonWidget(label="6", text="number_6", shortcut_text="6")
        self.six.connect("clicked", self._on_6)
        self.plus = ButtonWidget(label="+", text="plus", shortcut_text="+")
        self.plus.connect("clicked", self._on_plus)

        self.one = ButtonWidget(label="1", text="number_1", shortcut_text="1")
        self.one.connect("clicked", self._on_1)
        self.two = ButtonWidget(label="2", text="number_2", shortcut_text="2")
        self.two.connect("clicked", self._on_2)
        self.three = ButtonWidget(label="3", text="number_3", shortcut_text="3")
        self.three.connect("clicked", self._on_3)
        self.minus = ButtonWidget(label="-", text="minus", shortcut_text="-")
        self.minus.connect("clicked", self._on_minus)

        self.zero = ButtonWidget(label="0", text="number_0", shortcut_text="0")
        self.zero.connect("clicked", self._on_zero)
        self.dot = ButtonWidget(label=".", text="dot", shortcut_text=".")
        self.dot.connect("clicked", self._on_dot)
        self.slash = ButtonWidget(label="/", text="slash", shortcut_text="/")
        self.slash.connect("clicked", self._on_slash)
        self.enter = ButtonWidget(label="Enter", text="enter", shortcut_text="↵ / Ent")
        self.enter.connect("clicked", self._on_enter)

        # Attach Zone 1
        self.num_pad.attach(self.channel, 0, 0, 1, 1)
        self.num_pad.attach(self.group, 1, 0, 1, 1)
        self.num_pad.attach(self.cue, 2, 0, 1, 1)
        self.num_pad.attach(self.address, 3, 0, 1, 1)

        self.num_pad.attach(self.seven, 0, 1, 1, 1)
        self.num_pad.attach(self.eight, 1, 1, 1, 1)
        self.num_pad.attach(self.nine, 2, 1, 1, 1)
        self.num_pad.attach(self.thru, 3, 1, 1, 1)

        self.num_pad.attach(self.four, 0, 2, 1, 1)
        self.num_pad.attach(self.five, 1, 2, 1, 1)
        self.num_pad.attach(self.six, 2, 2, 1, 1)
        self.num_pad.attach(self.plus, 3, 2, 1, 1)

        self.num_pad.attach(self.one, 0, 3, 1, 1)
        self.num_pad.attach(self.two, 1, 3, 1, 1)
        self.num_pad.attach(self.three, 2, 3, 1, 1)
        self.num_pad.attach(self.minus, 3, 3, 1, 1)

        self.num_pad.attach(self.zero, 0, 4, 1, 1)
        self.num_pad.attach(self.dot, 1, 4, 1, 1)
        self.num_pad.attach(self.slash, 2, 4, 1, 1)
        self.num_pad.attach(self.enter, 3, 4, 1, 1)

        # Zone 2: Levels, Actions & Command Line Editing (4x5)
        self.actions_pad = Gtk.Grid()
        self.at_level = ButtonWidget(label="At", text="at", shortcut_text="A")
        self.at_level.connect("clicked", self._on_at)
        self.full = ButtonWidget(label="Full", text="full", shortcut_text="F / ⇧A")
        self.full.connect("clicked", self._on_full)
        self.out = ButtonWidget(label="Out", text="out", shortcut_text="O / ⇧O")
        self.out.connect("clicked", self._on_out)
        self.clear = ButtonWidget(label="Clear", text="clear", shortcut_text="Esc / ⇧C")
        self.clear.connect("clicked", self._on_clear)

        self.percent_plus = ButtonWidget(
            label="+%", text="percent_plus", shortcut_text="^↑"
        )
        self.percent_plus.connect("clicked", self._on_percent_plus)
        self.percent_minus = ButtonWidget(
            label="-%", text="percent_minus", shortcut_text="^↓"
        )
        self.percent_minus.connect("clicked", self._on_percent_minus)
        self.block = ButtonWidget(label="Block", text="block", shortcut_text="B")
        self.block.connect("clicked", self._on_block)
        self.backspace = ButtonWidget(
            label="Backspace", text="backspace", shortcut_text="⌫"
        )
        self.backspace.connect("clicked", self._on_backspace)

        self.record = ButtonWidget(
            label="Record", text="record", shortcut_text="R / ⇧R"
        )
        self.record.connect("clicked", self._on_record)
        self.update = ButtonWidget(
            label="Update", text="update", shortcut_text="U / ⇧U"
        )
        self.update.connect("clicked", self._on_update)
        self.delete = ButtonWidget(label="Delete", text="delete", shortcut_text="D")
        self.delete.connect("clicked", self._on_delete)
        self.goto = ButtonWidget(label="Goto", text="goto", shortcut_text="⇧Q")
        self.goto.connect("clicked", self._on_goto)

        self.time = ButtonWidget(label="Time", text="time", shortcut_text="I")
        self.time.connect("clicked", self._on_time)
        self.delay = ButtonWidget(label="Delay", text="delay", shortcut_text="Y")
        self.delay.connect("clicked", self._on_delay)
        self.sneak = ButtonWidget(label="Sneak", text="sneak", shortcut_text="N")
        self.sneak.connect("clicked", self._on_sneak)
        self.unblock = ButtonWidget(
            label="Unblock", text="unblock", shortcut_text="Alt+B"
        )
        self.unblock.connect("clicked", self._on_unblock)

        self.park = ButtonWidget(label="Park", text="park", shortcut_text="⇧P")
        self.park.connect("clicked", self._on_park)
        self.unpark = ButtonWidget(label="Unpark", text="unpark", shortcut_text="Alt+P")
        self.unpark.connect("clicked", self._on_unpark)
        self.undo = ButtonWidget(label="Undo", text="undo", shortcut_text="^Z")
        self.undo.connect("clicked", self._on_undo)
        self.redo = ButtonWidget(label="Redo", text="redo", shortcut_text="⇧^Z")
        self.redo.connect("clicked", self._on_redo)

        # Attach Zone 2
        self.actions_pad.attach(self.at_level, 0, 0, 1, 1)
        self.actions_pad.attach(self.full, 1, 0, 1, 1)
        self.actions_pad.attach(self.out, 2, 0, 1, 1)
        self.actions_pad.attach(self.clear, 3, 0, 1, 1)

        self.actions_pad.attach(self.percent_plus, 0, 1, 1, 1)
        self.actions_pad.attach(self.percent_minus, 1, 1, 1, 1)
        self.actions_pad.attach(self.block, 2, 1, 1, 1)
        self.actions_pad.attach(self.backspace, 3, 1, 1, 1)

        self.actions_pad.attach(self.record, 0, 2, 1, 1)
        self.actions_pad.attach(self.update, 1, 2, 1, 1)
        self.actions_pad.attach(self.delete, 2, 2, 1, 1)
        self.actions_pad.attach(self.goto, 3, 2, 1, 1)

        self.actions_pad.attach(self.time, 0, 3, 1, 1)
        self.actions_pad.attach(self.delay, 1, 3, 1, 1)
        self.actions_pad.attach(self.sneak, 2, 3, 1, 1)
        self.actions_pad.attach(self.unblock, 3, 3, 1, 1)

        self.actions_pad.attach(self.park, 0, 4, 1, 1)
        self.actions_pad.attach(self.unpark, 1, 4, 1, 1)
        self.actions_pad.attach(self.undo, 2, 4, 1, 1)
        self.actions_pad.attach(self.redo, 3, 4, 1, 1)

        # Zone 3: Moving Lights & Selection Tools (2x5)
        self.tools_pad = Gtk.Grid()
        self.home = ButtonWidget(label="Home", text="home", shortcut_text="H / ⇧H")
        self.home.connect("clicked", self._on_home)
        self.locate = ButtonWidget(
            label="Locate", text="locate", shortcut_text="L / ⇧L"
        )
        self.locate.connect("clicked", self._on_locate)

        self.position = ButtonWidget(
            label="Position", text="position", shortcut_text="P"
        )
        self.position.connect("clicked", self._on_position)
        self.focus = ButtonWidget(label="Focus", text="focus", shortcut_text="Alt+F")
        self.focus.connect("clicked", self._on_focus)

        self.color = ButtonWidget(label="Color", text="color", shortcut_text="Alt+C")
        self.color.connect("clicked", self._on_color)
        self.beam = ButtonWidget(label="Beam", text="beam", shortcut_text="Alt+M")
        self.beam.connect("clicked", self._on_beam)

        self.all = ButtonWidget(label="All", text="all", shortcut_text="M")
        self.all.connect("clicked", self._on_all)
        self.seq = ButtonWidget(label="Seq", text="seq", shortcut_text="S")
        self.seq.connect("clicked", self._on_seq)

        self.odd = ButtonWidget(label="Odd", text="odd", shortcut_text="J")
        self.odd.connect("clicked", self._on_odd)
        self.even = ButtonWidget(label="Even", text="even", shortcut_text="E")
        self.even.connect("clicked", self._on_even)

        # Attach Zone 3
        self.tools_pad.attach(self.home, 0, 0, 1, 1)
        self.tools_pad.attach(self.locate, 1, 0, 1, 1)
        self.tools_pad.attach(self.position, 0, 1, 1, 1)
        self.tools_pad.attach(self.focus, 1, 1, 1, 1)
        self.tools_pad.attach(self.color, 0, 2, 1, 1)
        self.tools_pad.attach(self.beam, 1, 2, 1, 1)
        self.tools_pad.attach(self.all, 0, 3, 1, 1)
        self.tools_pad.attach(self.seq, 1, 3, 1, 1)
        self.tools_pad.attach(self.odd, 0, 4, 1, 1)
        self.tools_pad.attach(self.even, 1, 4, 1, 1)

        # Navigation Pad (Up, Down, Left, Right)
        self.modify_pad = Gtk.Grid()
        # self.modify_pad.set_column_homogeneous(True)
        # self.modify_pad.set_row_homogeneous(True)
        self.up = ButtonWidget(label="^", text="up", shortcut_text="↑")
        self.up.connect("clicked", self._on_up)
        self.down = ButtonWidget(label="v", text="down", shortcut_text="↓")
        self.down.connect("clicked", self._on_down)
        self.left = ButtonWidget(label="<", text="left", shortcut_text="←")
        self.left.connect("clicked", self._on_left)
        self.right = ButtonWidget(label=">", text="right", shortcut_text="→")
        self.right.connect("clicked", self._on_right)
        self.modify_pad.attach(self.up, 1, 0, 1, 1)
        self.modify_pad.attach(self.left, 0, 1, 1, 1)
        self.modify_pad.attach(self.down, 1, 1, 1, 1)
        self.modify_pad.attach(self.right, 2, 1, 1, 1)

        # Controller for channels level
        self.wheel = ControllerWidget(text="wheel", midi=self.app.midi)
        self.wheel.connect("moved", self._on_wheel)
        self.wheel.connect("clicked", self._controller_clicked)

        # Crossfade
        self.crossfade_pad = Gtk.Grid()
        self.crossfade_pad.set_column_spacing(5)

        adjustment = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=255,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        self.scale_a = FaderWidget(
            text="crossfade_out",
            red=0.3,
            green=0.3,
            blue=0.7,
            orientation=Gtk.Orientation.VERTICAL,
            adjustment=adjustment,
            midi=self.app.midi,
            crossfade=self.app.crossfade,
            is_crossfade=True,
        )
        self.scale_a.led = False
        self.scale_a.connect("clicked", self._scale_clicked)
        self.scale_a.set_draw_value(False)
        self.scale_a.set_vexpand(True)
        self.scale_a.set_inverted(True)
        self.scale_a.connect("value-changed", self.scale_moved)

        adjustment = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=255,
            step_increment=1,
            page_increment=10,
            page_size=0,
        )
        self.scale_b = FaderWidget(
            text="crossfade_in",
            red=0.6,
            green=0.2,
            blue=0.2,
            orientation=Gtk.Orientation.VERTICAL,
            adjustment=adjustment,
            midi=self.app.midi,
            crossfade=self.app.crossfade,
            is_crossfade=True,
        )
        self.scale_b.led = False
        self.scale_b.connect("clicked", self._scale_clicked)
        self.scale_b.set_draw_value(False)
        self.scale_b.set_vexpand(True)
        self.scale_b.set_inverted(True)
        self.scale_b.connect("value-changed", self.scale_moved)

        self.crossfade_pad.attach(self.scale_a, 0, 0, 1, 1)
        self.crossfade_pad.attach(self.scale_b, 1, 0, 1, 1)

        # Independents
        self.independents = Gtk.Grid()
        self.independent_widgets: list[KnobWidget | ToggleWidget] = []
        self.build_independents()

        # Go, Seq-, Seq+, Pause, Go Back
        self.go_pad = Gtk.Grid()
        self.go_button = GoWidget(shortcut_text="Space / ^G")
        self.go_button.connect("clicked", self._on_go)
        self.seq_plus = ButtonWidget(
            label="Next Cue", text="playback.sequence_plus", shortcut_text="Alt+↓"
        )
        self.seq_plus.connect("clicked", self._on_seq_plus)
        self.seq_minus = ButtonWidget(
            label="Prev Cue", text="playback.sequence_minus", shortcut_text="Alt+↑"
        )
        self.seq_minus.connect("clicked", self._on_seq_minus)
        self.goback = ButtonWidget(
            label="Go Back", text="playback.go_back", shortcut_text="^B"
        )
        self.goback.connect("clicked", self._on_go_back)
        self.pause = PauseWidget("Pause", "playback.pause")
        self.pause.connect("clicked", self._on_pause)
        self.go_pad.attach(self.seq_minus, 0, 0, 1, 1)
        self.go_pad.attach(self.seq_plus, 1, 0, 1, 1)
        self.go_pad.attach(self.pause, 0, 1, 1, 1)
        self.go_pad.attach(self.goback, 1, 1, 1, 1)
        self.go_pad.attach(self.go_button, 0, 2, 2, 1)

        # Faders
        self.faders_pad = Gtk.Grid()
        self.faders = []
        self.flashes = []
        for i in range(10):  # 10 Faders per page
            adjustment = Gtk.Adjustment(
                value=0,
                lower=0,
                upper=255,
                step_increment=1,
                page_increment=10,
                page_size=0,
            )
            self.faders.append(
                FaderWidget(
                    text=f"fader_{i + 1}",
                    orientation=Gtk.Orientation.VERTICAL,
                    adjustment=adjustment,
                    midi=self.app.midi,
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
        fader_bank = self.app.core.lightshow.fader_bank
        for fader in fader_bank.faders[fader_bank.active_page].values():
            # Flash with fader name
            self.flashes[fader.index - 1].label = fader.text
            # Fader at fader level
            level = round(fader.level * 255)
            self.faders[fader.index - 1].set_value(level)
        self.fader_pages = Gtk.Grid()
        self.fader_page_plus = ButtonWidget(label="Page+", text="page_plus")
        self.fader_page_plus.connect("clicked", self._on_fader_page)
        self.fader_page_minus = ButtonWidget(label="Page-", text="page_minus")
        self.fader_page_minus.connect("clicked", self._on_fader_page)
        self.page_number = Gtk.Label(label=str(fader_bank.active_page))
        self.fader_pages.attach(self.fader_page_plus, 0, 0, 1, 1)
        self.fader_pages.attach(self.page_number, 0, 1, 1, 1)
        self.fader_pages.attach(self.fader_page_minus, 0, 2, 1, 1)
        self.faders_pad.attach(self.fader_pages, 11, 0, 1, 1)

        # General Grid (7 Columns)
        self.grid = Gtk.Grid()
        self.grid.set_row_spacing(10)
        self.grid.set_column_spacing(10)
        self.grid.attach(self.num_pad, 0, 0, 1, 2)
        self.grid.attach(self.actions_pad, 1, 0, 1, 2)
        self.grid.attach(self.tools_pad, 2, 0, 1, 2)
        self.grid.attach(self.modify_pad, 3, 0, 1, 1)
        self.grid.attach(self.wheel, 3, 1, 1, 1)
        self.grid.attach(self.crossfade_pad, 4, 0, 1, 2)
        self.grid.attach(self.independents, 5, 0, 1, 1)
        self.grid.attach(self.go_pad, 5, 1, 1, 1)
        self.grid.attach(self.faders_pad, 6, 0, 1, 2)

        self.add(self.grid)

        # Listen for events to dynamically update button sensitivity
        self.app.core.subscribe("commandline.changed", self._on_commandline_changed)
        self.app.core.subscribe("park.changed", self._on_park_changed)
        self.app.core.subscribe("history.changed", self._on_history_changed)
        self.update_button_sensitivity()
        if (
            hasattr(self.app.core, "lightshow")
            and hasattr(self.app.core.lightshow, "park")
            and self.app.core.lightshow.park.total_parked_count() > 0
        ):
            self._update_park_indicator(
                self.app.core.lightshow.park.total_parked_count()
            )

        # Handle keyboard events via modern EventControllerKey
        self.key_controller = Gtk.EventControllerKey.new(self)
        self.key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.key_controller.connect("key-pressed", self._on_key_controller_pressed)
        self.key_controller.connect("key-released", self._on_key_controller_released)

    def _on_shortcuts_toggled(self, _btn: Gtk.ToggleButton) -> None:
        """Handle toggling the display of keyboard shortcuts."""
        self.queue_draw()

    def _on_focus_out(self, _widget: Gtk.Widget, _event: Gdk.EventFocus) -> bool:
        """Reset F1 hold state if window loses focus."""
        if self.is_holding_f1:
            self.is_holding_f1 = False
            self.queue_draw()
        return False

    def _on_key_controller_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        """Handle keyboard events for Virtual Console.

        Closes the window on Control+W, handles F1 overlay toggle,
        and delegates console shortcuts and modifiers to the main window.

        Args:
            controller: Gtk EventControllerKey.
            keyval: Key value.
            keycode: Hardware keycode.
            state: Modifier state.

        Returns:
            True if event handled, False otherwise.
        """
        if keyval == Gdk.KEY_F1:
            if not self.is_holding_f1:
                self.is_holding_f1 = True
                self.queue_draw()
            return True

        modifiers = int(state) & Gtk.accelerator_get_default_mod_mask()
        if bool(modifiers & Gdk.ModifierType.CONTROL_MASK) and keyval in (
            Gdk.KEY_w,
            Gdk.KEY_W,
        ):
            self.close()
            return True

        if self.app.window is not None:
            return bool(
                self.app.window._on_key_controller_pressed(
                    controller, keyval, keycode, state
                )
            )
        return False

    def _on_key_controller_released(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        """Handle key release events for Virtual Console.

        Args:
            _controller: Gtk EventControllerKey.
            keyval: Key value.
            _keycode: Hardware keycode.
            _state: Modifier state.

        Returns:
            True if event handled, False otherwise.
        """
        if keyval == Gdk.KEY_F1:
            if self.is_holding_f1:
                self.is_holding_f1 = False
                self.queue_draw()
            return True
        return False

    @property
    def is_learning_midi(self) -> bool:
        """Return True if the console is currently learning a MIDI command."""
        return self.app.midi is not None and bool(self.app.midi.learning)

    def _close(self, _widget: Gtk.Widget, _event: Gdk.Event) -> bool:
        """Mark Window as closed

        Returns:
            False to propagate the event further
        """
        self.app.core.unsubscribe("commandline.changed", self._on_commandline_changed)
        self.app.core.unsubscribe("park.changed", self._on_park_changed)
        self.app.core.unsubscribe("history.changed", self._on_history_changed)
        self.app.virtual_console = None
        return False

    def _on_commandline_changed(self, _text: str) -> None:
        """Handle commandline buffer changes by refreshing button sensitivity."""
        self.update_button_sensitivity()

    def _on_history_changed(self, _data: object) -> None:
        """Handle undo/redo history changed event."""
        GLib.idle_add(self.update_button_sensitivity)

    def update_button_sensitivity(self) -> None:
        """Enable or disable commandline buttons based on parser expectations."""
        if self.is_learning_midi:
            return

        cmd_text = self.commandline.get_string()
        expected = set(self.commandline.parser.get_expected_tokens(cmd_text))
        is_empty = not cmd_text.strip()

        def set_sens(attr_name: str, sensitive: bool) -> None:
            btn = getattr(self, attr_name, None)
            if btn is not None:
                btn.set_sensitive(sensitive)

        # Zone 1: Numeric pad & targets
        can_number = (TokenType.NUMBER in expected) or is_empty
        for num_name in (
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "dot",
        ):
            set_sens(num_name, can_number)

        set_sens("slash", TokenType.SLASH in expected)
        set_sens("channel", TokenType.CHANNEL in expected or is_empty)
        set_sens("cue", TokenType.CUE in expected or is_empty)
        set_sens("group", TokenType.GROUP in expected or is_empty)
        set_sens("address", TokenType.ADDRESS in expected or is_empty)
        set_sens("thru", TokenType.THRU in expected)
        set_sens("plus", TokenType.PLUS in expected)
        set_sens("minus", TokenType.MINUS in expected)
        set_sens("enter", not is_empty)

        # Zone 2: Actions, Levels & Editing
        set_sens("at_level", TokenType.AT in expected)
        set_sens("full", TokenType.FULL in expected)
        set_sens("out", TokenType.OUT in expected)
        set_sens("clear", True)
        set_sens("percent_plus", TokenType.AT in expected)
        set_sens("percent_minus", TokenType.AT in expected)
        set_sens("block", TokenType.BLOCK in expected)
        set_sens("backspace", not is_empty)
        set_sens("record", TokenType.RECORD in expected or is_empty)
        set_sens("update", TokenType.UPDATE in expected or is_empty)
        set_sens("delete", TokenType.DELETE in expected or is_empty)
        set_sens("goto", TokenType.GOTO in expected or is_empty)
        set_sens("time", TokenType.TIME in expected)
        set_sens("delay", TokenType.DELAY in expected)
        set_sens("sneak", TokenType.SNEAK in expected or is_empty)
        set_sens("unblock", TokenType.UNBLOCK in expected)
        set_sens("park", TokenType.PARK in expected or is_empty)
        set_sens("unpark", TokenType.UNPARK in expected or is_empty)

        can_undo = bool(
            hasattr(self.app.core, "history")
            and getattr(self.app.core.history, "can_undo", False)
        )
        can_redo = bool(
            hasattr(self.app.core, "history")
            and getattr(self.app.core.history, "can_redo", False)
        )
        set_sens("undo", can_undo)
        set_sens("redo", can_redo)

        # Zone 3: Tools & Moving Lights
        set_sens("home", TokenType.HOME in expected or is_empty)
        set_sens("locate", TokenType.LOCATE in expected or is_empty)
        set_sens("position", TokenType.POSITION in expected or is_empty)
        set_sens("focus", TokenType.FOCUS in expected or is_empty)
        set_sens("color", TokenType.COLOR in expected or is_empty)
        set_sens("beam", TokenType.BEAM in expected or is_empty)
        set_sens("all", TokenType.ALL in expected or is_empty)
        set_sens("seq", TokenType.SEQUENCE in expected or is_empty)
        set_sens("odd", TokenType.ODD in expected)
        set_sens("even", TokenType.EVEN in expected)

        self.queue_draw()

    def _on_button_toggled(self, button: Gtk.ToggleButton, name: str) -> None:
        """MIDI learn On / Off

        Args:
            button: Button clicked
            name: Name of the button
        """
        if name == "MIDI":
            action_name = " " if button.get_active() else None
            self.app.core.action_registry.execute("midi.learn_toggle", action_name)
            if self.app.virtual_console:
                self.app.virtual_console.queue_draw()

    def _on_blackout_toggled(self, button: Gtk.ToggleButton) -> None:
        """Handle blackout toggle button interaction."""
        if self.updating_blackout:
            return

        target_state = button.get_active()
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "dmx.blackout_all"
            current_state = bool(getattr(self.app.core, "blackout_active", False))
            self.update_blackout_display(current_state)
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("dmx.blackout_all", target_state)

    def update_blackout_display(self, state: bool | None = None) -> None:
        """Update blackout toggle button state without re-triggering action.

        Args:
            state: Explicit boolean state or None to query core.blackout_active.
        """
        if state is None:
            state = bool(getattr(self.app.core, "blackout_active", False))
        self.updating_blackout = True
        try:
            if self.blackout.get_active() != state:
                self.blackout.set_active(state)
        finally:
            self.updating_blackout = False

    def _on_fader_page(self, widget: Gtk.Widget) -> None:
        """Change fader page

        Args:
            widget: clicked button
        """
        if self.is_learning_midi and self.app.midi is not None:
            if widget is self.fader_page_plus:
                self.app.midi.learning = "page_plus"
            elif widget is self.fader_page_minus:
                self.app.midi.learning = "page_minus"
            self.queue_draw()
        else:
            fader_bank = self.app.core.lightshow.fader_bank
            target_page = fader_bank.active_page
            if widget is self.fader_page_plus:
                target_page += 1
            elif widget is self.fader_page_minus:
                target_page -= 1

            if self.app is not None and hasattr(self.app.core, "action_registry"):
                self.app.core.action_registry.execute("fader.set_page", target_page)
            else:
                fader_bank.active_page = target_page
                self.update_page_display()

    def update_page_display(self) -> None:
        """Update fader page labels and values on virtual console and MIDI."""
        fader_bank = self.app.core.lightshow.fader_bank
        self.page_number.set_label(str(fader_bank.active_page))
        for fader in fader_bank.faders[fader_bank.active_page].values():
            text = f"fader_{fader.index + ((fader_bank.active_page - 1) * 10)}"
            self.faders[fader.index - 1].text = text
            val = round(fader.level * 255)
            self.faders[fader.index - 1].set_value(val)
            self.flashes[fader.index - 1].label = fader.text
            self.flashes[fader.index - 1].queue_draw()
        if self.app.midi is not None:
            for fader in fader_bank.faders[fader_bank.active_page].values():
                self.app.midi.faders.faders[fader.index - 1].set_state(fader.level)
            self.app.midi.messages.lcd.show_faders()

    def _on_time(self, _widget: Gtk.Widget) -> None:
        """Time button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "time"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " TIME ")

    def _on_delay(self, _widget: Gtk.Widget) -> None:
        """Delay button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "delay"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " DELAY ")

    def _on_go(self, _widget: Gtk.Widget) -> None:
        """Go"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "playback.go"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("playback.go")

    def _on_go_back(self, _widget: Gtk.Widget) -> None:
        """Go back"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "playback.go_back"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("playback.go_back")

    def _on_pause(self, _widget: Gtk.Widget) -> None:
        """Pause"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "playback.pause"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("playback.pause")

    def _on_seq_plus(self, _widget: Gtk.Widget) -> None:
        """Sequence +"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "playback.sequence_plus"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("playback.sequence_plus")

    def _on_seq_minus(self, _widget: Gtk.Widget) -> None:
        """Sequence -"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "playback.sequence_minus"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("playback.sequence_minus")

    def _on_channel(self, _widget: Gtk.Widget) -> None:
        """Channel button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "channel"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}CHANNEL "
            )

    def _on_cue(self, _widget: Gtk.Widget) -> None:
        """Cue button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "cue"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}CUE "
            )

    def _on_slash(self, _widget: Gtk.Widget) -> None:
        """Slash button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "slash"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "/")

    def _on_address(self, _widget: Gtk.Widget) -> None:
        """Address button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "address"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}ADDRESS "
            )

    def _on_park(self, _widget: Gtk.Widget) -> None:
        """Park button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "park"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}PARK "
            )

    def _on_unpark(self, _widget: Gtk.Widget) -> None:
        """Unpark button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "unpark"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}UNPARK "
            )

    def _on_park_changed(self, count: int) -> None:
        """Handle park state changed event."""
        GLib.idle_add(self._update_park_indicator, count)

    def _update_park_indicator(self, count: int) -> bool:
        if hasattr(self, "park_indicator") and self.park_indicator:
            if count > 0:
                self.park_indicator.set_label(f"⚠️ PARK ({count})")
                self.park_indicator.set_visible(True)
            else:
                self.park_indicator.set_visible(False)
        return False

    def _on_park_indicator_clicked(self, _widget: Gtk.Widget) -> None:
        """Unpark all parked items on indicator click."""
        self.app.core.action_registry.execute("park.unpark_all")

    def _on_seq(self, _widget: Gtk.Widget) -> None:
        """Seq"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "seq"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}SEQ "
            )

    def _on_group(self, _widget: Gtk.Widget) -> None:
        """Group"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "group"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}GROUP "
            )

    def _on_unblock(self, _widget: Gtk.Widget) -> None:
        """Unblock button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "unblock"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}UNBLOCK "
            )

    def _on_home(self, _widget: Gtk.Widget) -> None:
        """Home button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "home"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}HOME"
            )

    def _on_locate(self, _widget: Gtk.Widget) -> None:
        """Locate button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "locate"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}LOCATE"
            )

    def _on_position(self, _widget: Gtk.Widget) -> None:
        """Position button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "position"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}POSITION "
            )

    def _on_focus(self, _widget: Gtk.Widget) -> None:
        """Focus button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "focus"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}FOCUS "
            )

    def _on_color(self, _widget: Gtk.Widget) -> None:
        """Color button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "color"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}COLOR "
            )

    def _on_beam(self, _widget: Gtk.Widget) -> None:
        """Beam button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "beam"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}BEAM "
            )

    def _on_undo(self, _widget: Gtk.Widget) -> None:
        """Undo button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "undo"
            self.queue_draw()
        else:
            if hasattr(self.app.core, "action_registry"):
                self.app.core.action_registry.execute("edit.undo")

    def _on_redo(self, _widget: Gtk.Widget) -> None:
        """Redo button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "redo"
            self.queue_draw()
        else:
            if hasattr(self.app.core, "action_registry"):
                self.app.core.action_registry.execute("edit.redo")

    def _on_goto(self, _widget: Gtk.Widget) -> None:
        """Goto"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "goto"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute(
                "commandline.append_char", "GOTO CUE "
            )

    def _on_delete(self, _widget: Gtk.Widget) -> None:
        """Delete"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "delete"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "DELETE ")

    def _on_sneak(self, _widget: Gtk.Widget) -> None:
        """Sneak"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "sneak"
            self.queue_draw()
        else:
            curr = self.commandline.get_string()
            prefix = " " if curr and not curr.endswith(" ") else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}SNEAK "
            )

    def _on_full(self, _widget: Gtk.Widget) -> None:
        """Full"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "full"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " AT FULL")

    def _on_out(self, _widget: Gtk.Widget) -> None:
        """Out"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "out"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " AT OUT")

    def _on_odd(self, _widget: Gtk.Widget) -> None:
        """Odd"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "odd"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " ODD")

    def _on_even(self, _widget: Gtk.Widget) -> None:
        """Even"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "even"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " EVEN")

    def _on_block(self, _widget: Gtk.Widget) -> None:
        """Block"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "block"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " BLOCK")

    def _on_thru(self, _widget: Gtk.Widget) -> None:
        """Thru"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "thru"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " THRU ")

    def _on_plus(self, _widget: Gtk.Widget) -> None:
        """+ button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "plus"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " + ")

    def _on_minus(self, _widget: Gtk.Widget) -> None:
        """- button"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "minus"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " - ")

    def _on_all(self, _widget: Gtk.Widget) -> None:
        """All"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "all"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "ALL")

    def _on_at(self, _widget: Gtk.Widget) -> None:
        """At level"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "at"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " AT ")

    def _on_percent_plus(self, _widget: Gtk.Widget) -> None:
        """% +"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "percent_plus"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " AT + 10")

    def _on_percent_minus(self, _widget: Gtk.Widget) -> None:
        """% -"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "percent_minus"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", " AT - 10")

    def _on_update(self, _widget: Gtk.Widget) -> None:
        """Update"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "update"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}UPDATE "
            )

    def _on_record(self, _widget: Gtk.Widget) -> None:
        """Record"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "record"
            self.queue_draw()
        else:
            curr = self.app.core.commandline.get_string()
            prefix = " " if (curr and not curr.endswith(" ")) else ""
            self.app.core.action_registry.execute(
                "commandline.append_char", f"{prefix}RECORD "
            )

    def _on_right(self, _widget: Gtk.Widget) -> None:
        """Right arrow"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "right"
            self.queue_draw()
        else:
            if self.app.window and hasattr(self.app.window, "live_view"):
                self.app.window.live_view.channels_view.select_next()

    def _on_left(self, _widget: Gtk.Widget) -> None:
        """Left arrow"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "left"
            self.queue_draw()
        else:
            if self.app.window and hasattr(self.app.window, "live_view"):
                self.app.window.live_view.channels_view.select_previous()

    def _on_up(self, _widget: Gtk.Widget) -> None:
        """Up arrow"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "up"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.history_prev")

    def _on_down(self, _widget: Gtk.Widget) -> None:
        """Down arrow"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "down"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.history_next")

    def _on_clear(self, _widget: Gtk.Widget) -> None:
        """Clear"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "clear"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.clear")

    def _on_backspace(self, _widget: Gtk.Widget) -> None:
        """Backspace"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "backspace"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.backspace")

    def _on_enter(self, _widget: Gtk.Widget) -> None:
        """Enter"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "enter"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.execute")

    def _on_zero(self, _widget: Gtk.Widget) -> None:
        """0"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_0"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "0")

    def _on_1(self, _widget: Gtk.Widget) -> None:
        """1"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_1"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "1")

    def _on_2(self, _widget: Gtk.Widget) -> None:
        """2"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_2"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "2")

    def _on_3(self, _widget: Gtk.Widget) -> None:
        """3"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_3"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "3")

    def _on_4(self, _widget: Gtk.Widget) -> None:
        """4"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_4"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "4")

    def _on_5(self, _widget: Gtk.Widget) -> None:
        """5"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_5"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "5")

    def _on_6(self, _widget: Gtk.Widget) -> None:
        """6"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_6"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "6")

    def _on_7(self, _widget: Gtk.Widget) -> None:
        """7"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_7"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "7")

    def _on_8(self, _widget: Gtk.Widget) -> None:
        """8"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_8"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "8")

    def _on_9(self, _widget: Gtk.Widget) -> None:
        """9"""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "number_9"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", "9")

    def _on_dot(self, _widget: Gtk.Widget) -> None:
        """."""
        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = "dot"
            self.queue_draw()
        else:
            self.app.core.action_registry.execute("commandline.append_char", ".")

    def _flash_on(self, widget: Gtk.Widget, _event: Gdk.Event) -> None:
        """Flash button pressed

        Args:
            widget: Button clicked
        """
        if self.app.midi is not None and not self.app.midi.learning:
            for index, flash in enumerate(self.flashes):
                if flash == widget:
                    fader_bank = self.app.core.lightshow.fader_bank
                    self.app.core.action_registry.execute(
                        "fader.flash", fader_bank.active_page, index + 1, True
                    )

    def _flash_off(self, widget: Gtk.Widget, _event: Gdk.Event) -> None:
        """Flash button released

        Args:
            widget: Button clicked
        """
        if self.app.midi is not None and not self.app.midi.learning:
            for index, flash in enumerate(self.flashes):
                if flash == widget:
                    fader_bank = self.app.core.lightshow.fader_bank
                    self.app.core.action_registry.execute(
                        "fader.flash", fader_bank.active_page, index + 1, False
                    )

    def _on_flash(self, widget: FlashWidget) -> None:
        """Flash button clicked

        Args:
            widget: Button clicked
        """
        if self.is_learning_midi and self.app.midi is not None:
            index = self.flashes.index(widget) + 1
            text = f"flash_{index}"
            self.app.midi.learning = text
            self.queue_draw()

    def fader_moved(self, fader: FaderWidget) -> None:
        """Fader moved

        Args:
            fader: FaderWidget
        """
        if self.updating_fader:
            return

        if self.is_learning_midi and self.app.midi is not None:
            index = self.faders.index(fader) + 1
            text = f"fader_{index}"
            self.app.midi.learning = text
            self.queue_draw()
        else:
            value = fader.get_value()
            index = self.faders.index(fader) + 1
            fader_bank = self.app.core.lightshow.fader_bank
            if self.app is not None and hasattr(self.app.core, "action_registry"):
                self.app.core.action_registry.execute(
                    "fader.set_level", fader_bank.active_page, index, value / 255
                )
            else:
                fader_bank.faders[fader_bank.active_page][index].set_level(value / 255)

    def _fader_clicked(self, fader: FaderWidget) -> None:
        """Fader clicked

        Args:
            fader: FaderWidget
        """
        if self.is_learning_midi and self.app.midi is not None:
            index = self.faders.index(fader) + 1
            text = f"fader_{index}"
            self.app.midi.learning = text
            self.queue_draw()

    def scale_moved(self, scale: FaderWidget) -> None:
        """Crossfade moved

        Args:
            scale (FaderWidget): crossfade fader
        """
        if self.is_learning_midi and self.app.midi is not None:
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
                if self.app.midi is not None:
                    midi_fader = self.app.midi.xfade.fader_out
                    midi_fader.set_state(int(value))
                if self.app.crossfade.manual:
                    self.app.crossfade.scale_moved(self.app.crossfade.scale_a)
            elif scale == self.scale_b:
                self.app.crossfade.scale_b.set_value(int(value))
                if self.app.midi is not None:
                    midi_fader = self.app.midi.xfade.fader_in
                    midi_fader.set_state(int(value))
                if self.app.crossfade.manual:
                    self.app.crossfade.scale_moved(self.app.crossfade.scale_b)

    def _scale_clicked(self, scale: FaderWidget) -> None:
        """Crossfade clicked

        Args:
            scale: FaderWidget
        """
        if self.is_learning_midi and self.app.midi is not None:
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
        if self.is_learning_midi and widget == self.wheel and self.app.midi is not None:
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
        if self.is_learning_midi:
            return
        child = self.app.window.get_active_tab() if self.app.window else None
        if self.app.tabs and child in (
            self.app.tabs.tabs["groups"],
            self.app.tabs.tabs["indes"],
            self.app.tabs.tabs["faders"],
            self.app.tabs.tabs["memories"],
            self.app.tabs.tabs["sequences"],
        ):
            channels_view = getattr(child, "channels_view", None)
            if channels_view and hasattr(channels_view, "wheel_level"):
                typing.cast(typing.Any, channels_view).wheel_level(step, direction)
                return
        dir_val = 1 if direction == Gdk.ScrollDirection.UP else -1
        self.app.core.action_registry.execute("channel.wheel_adjust", step, dir_val)

    def _inde_clicked(self, widget: KnobWidget | ToggleWidget) -> None:
        """Independent clicked

        Args:
            widget: Object clicked
        """
        if widget not in self.independent_widgets:
            return

        idx = self.independent_widgets.index(widget)
        inde = self.app.core.lightshow.independents.independents[idx]
        name = f"inde_{inde.number}"

        if self.is_learning_midi and self.app.midi is not None:
            self.app.midi.learning = name
            if isinstance(widget, ToggleWidget):
                widget.set_active(False)
            self.queue_draw()
        elif isinstance(widget, ToggleWidget):
            if self.updating_independent:
                return
            level = 1.0 if widget.get_active() else 0.0
            if self.app is not None and hasattr(self.app.core, "action_registry"):
                self.app.core.action_registry.execute(
                    "independent.set_level", inde.number, level
                )
            else:
                raw_level = round(level * 255)
                inde.level = raw_level
                inde.update_dmx()

    def _inde_changed(self, widget: Gtk.Widget) -> None:
        """Independent value changed

        Args:
            widget: Object changed
        """
        if self.is_learning_midi:
            return
        if self.updating_independent:
            return
        if widget not in self.independent_widgets:
            return
        idx = self.independent_widgets.index(typing.cast(typing.Any, widget))
        if not isinstance(widget, KnobWidget):
            return

        value = widget.value
        level_float = value / 255.0
        inde = self.app.core.lightshow.independents.independents[idx]
        if self.app is not None and hasattr(self.app.core, "action_registry"):
            self.app.core.action_registry.execute(
                "independent.set_level", inde.number, level_float
            )
        else:
            inde.set_level(int(value))
            if self.app.midi is not None:
                midi_fader = self.app.midi.faders.inde_faders[idx]
                midi_fader.set_state(int(value))

    def queue_draw(self) -> None:
        """Synchronize learning states and shortcut display before drawing."""
        show_sc = bool(
            (hasattr(self, "shortcuts_toggle") and self.shortcuts_toggle.get_active())
            or getattr(self, "is_holding_f1", False)
        )
        if hasattr(self, "go_button") and self.go_button:
            is_learning = False
            if self.app.midi and self.app.midi.learning == "playback.go":
                is_learning = True
            self.go_button.is_learning = is_learning
            self.go_button.show_shortcut = show_sc
        if hasattr(self, "pause") and self.pause:
            is_learning = False
            if self.app.midi and self.app.midi.learning == "playback.pause":
                is_learning = True
            self.pause.is_learning = is_learning
            self.pause.show_shortcut = show_sc

        for attr in list(self.__dict__.values()) + list(self.independent_widgets):
            if isinstance(attr, ButtonWidget):
                is_learning = False
                if (
                    self.app.midi
                    and attr.text != "None"
                    and self.app.midi.learning == attr.text
                ):
                    is_learning = True
                attr.is_learning = is_learning
                attr.show_shortcut = show_sc

        super().queue_draw()

    def update_independent_display(self, number: int, level: float) -> None:
        """Update independent slider or button state in GUI."""
        self.updating_independent = True
        try:
            idx = number - 1
            if 0 <= idx < len(self.independent_widgets):
                widget = self.independent_widgets[idx]
                if isinstance(widget, KnobWidget):
                    widget.value = level * 255
                elif isinstance(widget, ToggleWidget):
                    widget.set_active(level > 0.5)
        finally:
            self.updating_independent = False

    def build_independents(self) -> None:
        """Dynamically build independent widgets based on model configuration."""
        for child in self.independents.get_children():
            self.independents.remove(child)

        self.independent_widgets = []
        indes = self.app.core.lightshow.independents.independents

        for idx, inde in enumerate(indes):
            name = f"inde_{inde.number}"
            if inde.inde_type == IndependentType.BUTTON:
                widget: KnobWidget | ToggleWidget = ToggleWidget(
                    self.app.midi, text=name
                )
                widget.connect("clicked", self._inde_clicked)
                if inde.level > 0.5:
                    widget.set_active(True)
            else:
                widget = KnobWidget(self.app.midi, text=name)
                widget.connect("clicked", self._inde_clicked)
                widget.connect("changed", self._inde_changed)
                widget.value = inde.level * 255

            self.independent_widgets.append(widget)
            col = idx % 3
            row = idx // 3
            self.independents.attach(widget, col, row, 1, 1)

        self.independents.show_all()

    def rebuild_independent(self, number: int) -> None:
        """Rebuild a specific independent widget on type change.

        Args:
            number: The independent number (1 to 9).
        """
        idx = number - 1
        if not 0 <= idx < len(self.independent_widgets):
            return

        old_widget = self.independent_widgets[idx]
        self.independents.remove(old_widget)

        inde = self.app.core.lightshow.independents.independents[idx]
        name = f"inde_{inde.number}"

        if inde.inde_type == IndependentType.BUTTON:
            widget: KnobWidget | ToggleWidget = ToggleWidget(self.app.midi, text=name)
            widget.connect("clicked", self._inde_clicked)
            if inde.level > 0.5:
                widget.set_active(True)
        else:
            widget = KnobWidget(self.app.midi, text=name)
            widget.connect("clicked", self._inde_clicked)
            widget.connect("changed", self._inde_changed)
            widget.value = inde.level * 255

        self.independent_widgets[idx] = widget
        col = idx % 3
        row = idx // 3
        self.independents.attach(widget, col, row, 1, 1)
        widget.show_all()

    @property
    def independent1(self) -> KnobWidget:
        """Get independent 1 widget."""
        return typing.cast(KnobWidget, self.independent_widgets[0])

    @property
    def independent2(self) -> KnobWidget:
        """Get independent 2 widget."""
        return typing.cast(KnobWidget, self.independent_widgets[1])

    @property
    def independent3(self) -> KnobWidget:
        """Get independent 3 widget."""
        return typing.cast(KnobWidget, self.independent_widgets[2])

    @property
    def independent4(self) -> KnobWidget:
        """Get independent 4 widget."""
        return typing.cast(KnobWidget, self.independent_widgets[3])

    @property
    def independent5(self) -> KnobWidget:
        """Get independent 5 widget."""
        return typing.cast(KnobWidget, self.independent_widgets[4])

    @property
    def independent6(self) -> KnobWidget:
        """Get independent 6 widget."""
        return typing.cast(KnobWidget, self.independent_widgets[5])

    @property
    def independent7(self) -> ToggleWidget:
        """Get independent 7 widget."""
        return typing.cast(ToggleWidget, self.independent_widgets[6])

    @property
    def independent8(self) -> ToggleWidget:
        """Get independent 8 widget."""
        return typing.cast(ToggleWidget, self.independent_widgets[7])

    @property
    def independent9(self) -> ToggleWidget:
        """Get independent 9 widget."""
        return typing.cast(ToggleWidget, self.independent_widgets[8])
