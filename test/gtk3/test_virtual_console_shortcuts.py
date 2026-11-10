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
"""GUI behavior tests for Virtual Console keyboard shortcuts display."""

from __future__ import annotations

import cairo
import pytest
from gi.repository import Gdk, Gtk

from olc.gtk3.application import Application
from olc.gtk3.widgets.button import ButtonWidget
from olc.gtk3.widgets.go import GoWidget

from test.gtk3.conftest import process_events  # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_virtual_console_shortcut_labels(app_gui: Application) -> None:
    """Test Virtual Console buttons have their expected shortcut badges assigned."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    # Primary navigation & playback
    assert vc.go_button.shortcut_text == "Space / ^G"
    assert vc.seq_minus.shortcut_text == "Alt+↑"
    assert vc.seq_plus.shortcut_text == "Alt+↓"

    # Targets & Selection
    assert vc.channel.shortcut_text == "C"
    assert vc.group.shortcut_text == "G"
    assert vc.cue.shortcut_text == "Q"
    assert vc.address.shortcut_text == "⇧D"
    assert vc.slash.shortcut_text == "/"

    # Multiple shortcut buttons
    assert vc.full.shortcut_text == "F / ⇧A"
    assert vc.out.shortcut_text == "O / ⇧O"
    assert vc.record.shortcut_text == "R / ⇧R"
    assert vc.update.shortcut_text == "U / ⇧U"
    assert vc.clear.shortcut_text == "Esc / ⇧C"
    assert vc.enter.shortcut_text == "↵ / Ent"

    # Command line keywords
    assert vc.thru.shortcut_text == "T"
    assert vc.plus.shortcut_text == "+"
    assert vc.minus.shortcut_text == "-"
    assert vc.all.shortcut_text == "M"
    assert vc.seq.shortcut_text == "S"
    assert vc.odd.shortcut_text == "J"
    assert vc.even.shortcut_text == "E"
    assert vc.at_level.shortcut_text == "A"
    assert vc.sneak.shortcut_text == "N"
    assert vc.time.shortcut_text == "I"
    assert vc.delay.shortcut_text == "Y"
    assert vc.block.shortcut_text == "B"
    assert vc.unblock.shortcut_text == "Alt+B"
    assert vc.delete.shortcut_text == "D"
    assert vc.goto.shortcut_text == "⇧Q"
    assert vc.park.shortcut_text == "⇧P"
    assert vc.unpark.shortcut_text == "Alt+P"
    assert vc.undo.shortcut_text == "^Z"
    assert vc.redo.shortcut_text == "⇧^Z"

    # Moving Lights & Tools
    assert vc.home.shortcut_text == "H / ⇧H"
    assert vc.locate.shortcut_text == "L / ⇧L"
    assert vc.position.shortcut_text == "P"
    assert vc.focus.shortcut_text == "Alt+F"
    assert vc.color.shortcut_text == "Alt+C"
    assert vc.beam.shortcut_text == "Alt+M"

    # Digits and symbols
    assert vc.zero.shortcut_text == "0"
    assert vc.one.shortcut_text == "1"
    assert vc.nine.shortcut_text == "9"
    assert vc.dot.shortcut_text == "."
    assert vc.backspace.shortcut_text == "⌫"

    # Arrows
    assert vc.up.shortcut_text == "↑"
    assert vc.down.shortcut_text == "↓"
    assert vc.left.shortcut_text == "←"
    assert vc.right.shortcut_text == "→"

    # Verify phantom/view buttons are removed
    assert not hasattr(vc, "live")
    assert not hasattr(vc, "format")
    assert not hasattr(vc, "blind")
    assert not hasattr(vc, "output")
    assert not hasattr(vc, "preset")
    assert not hasattr(vc, "track")

    vc.close()
    process_events()


def test_virtual_console_shortcuts_toggle_button(app_gui: Application) -> None:
    """Test toggle button on HeaderBar controls shortcut badges visibility."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    assert hasattr(vc, "shortcuts_toggle")
    assert isinstance(vc.shortcuts_toggle, Gtk.ToggleButton)

    # Initial state: shortcuts hidden
    vc.queue_draw()
    assert vc.shortcuts_toggle.get_active() is False
    assert vc.full.show_shortcut is False
    assert vc.go_button.show_shortcut is False
    assert vc.sneak.show_shortcut is False

    # Toggle button active -> show shortcuts
    vc.shortcuts_toggle.set_active(True)
    process_events()
    assert vc.full.show_shortcut is True
    assert vc.go_button.show_shortcut is True
    assert vc.sneak.show_shortcut is True

    # Toggle button inactive -> hide shortcuts
    vc.shortcuts_toggle.set_active(False)
    process_events()
    assert vc.full.show_shortcut is False
    assert vc.go_button.show_shortcut is False
    assert vc.sneak.show_shortcut is False

    vc.close()
    process_events()


def test_virtual_console_f1_hold_and_release(app_gui: Application) -> None:
    """Test holding F1 temporarily reveals shortcuts and releasing F1 hides them."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    assert vc.is_holding_f1 is False
    assert vc.full.show_shortcut is False

    # Simulate F1 press
    controller = vc.key_controller
    handled_press = vc._on_key_controller_pressed(
        controller, Gdk.KEY_F1, 0, Gdk.ModifierType(0)
    )
    assert handled_press is True
    assert vc.is_holding_f1 is True
    assert vc.full.show_shortcut is True
    assert vc.go_button.show_shortcut is True

    # Simulate F1 release
    handled_release = vc._on_key_controller_released(
        controller, Gdk.KEY_F1, 0, Gdk.ModifierType(0)
    )
    assert handled_release is True
    assert vc.is_holding_f1 is False
    assert vc.full.show_shortcut is False
    assert vc.go_button.show_shortcut is False

    # Simulate F1 press followed by focus loss
    vc._on_key_controller_pressed(controller, Gdk.KEY_F1, 0, Gdk.ModifierType(0))
    assert vc.is_holding_f1 is True
    assert vc.full.show_shortcut is True

    focus_event = Gdk.EventFocus()
    vc._on_focus_out(vc, focus_event)
    assert vc.is_holding_f1 is False
    assert vc.full.show_shortcut is False

    vc.close()
    process_events()


def test_widgets_cairo_draw_with_shortcuts() -> None:
    """Test Cairo drawing of ButtonWidget and GoWidget with shortcut badge active."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 120, 80)
    cr = cairo.Context(surface)

    # 1. ButtonWidget with short shortcut
    btn_short = ButtonWidget(label="Thru", text="thru", shortcut_text="T")
    btn_short.show_shortcut = True
    btn_short.do_draw(cr)

    # 2. ButtonWidget with long multiple shortcuts
    btn_long = ButtonWidget(label="Full", text="full", shortcut_text="F / ⇧A")
    btn_long.show_shortcut = True
    btn_long.do_draw(cr)

    # 3. GoWidget with multiple shortcuts
    go = GoWidget(shortcut_text="Space / ^G")
    go.show_shortcut = True
    go.do_draw(cr)


def test_virtual_console_shortcut_delegation(app_gui: Application) -> None:
    """Test Virtual Console delegates modifier shortcuts to Main Window."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console
    controller = vc.key_controller
    cmdline = app_gui.core.commandline

    # 1. Ctrl+Alt+O delegates to Main Window and appends "OUT "
    ctrl_alt = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK
    cmdline.clear()
    assert vc._on_key_controller_pressed(controller, Gdk.KEY_o, 0, ctrl_alt) is True
    assert cmdline.get_string() == "OUT "

    # 2. Ctrl+B delegates to Main Window and executes playback.go_back
    executed: list[str] = []
    orig_exec = app_gui.core.action_registry.execute

    def spy_exec(name: str, *args: object, **kwargs: object) -> object:
        executed.append(name)
        return orig_exec(name, *args, **kwargs)

    app_gui.core.action_registry.execute = spy_exec  # type: ignore[assignment]
    try:
        assert (
            vc._on_key_controller_pressed(
                controller, Gdk.KEY_b, 0, Gdk.ModifierType.CONTROL_MASK
            )
            is True
        )
        assert "playback.go_back" in executed

        # 3. Ctrl+Shift+B delegates and executes dmx.blackout_all
        executed.clear()
        ctrl_shift = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        assert (
            vc._on_key_controller_pressed(controller, Gdk.KEY_b, 0, ctrl_shift) is True
        )
        assert "dmx.blackout_all" in executed
    finally:
        app_gui.core.action_registry.execute = orig_exec  # type: ignore[assignment]

    vc.close()
    process_events()


def test_virtual_console_button_clicks_and_syntax(app_gui: Application) -> None:
    """Test clicking buttons on the virtual console builds valid command syntax."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console
    cmdline = app_gui.core.commandline

    cmdline.clear()
    vc._on_channel(vc.channel)
    assert cmdline.get_string() == "CHANNEL "

    vc._on_1(vc.one)
    assert cmdline.get_string() == "CHANNEL 1"

    vc._on_thru(vc.thru)
    assert cmdline.get_string() == "CHANNEL 1 THRU "

    vc._on_5(vc.five)
    assert cmdline.get_string() == "CHANNEL 1 THRU 5"

    vc._on_backspace(vc.backspace)
    assert cmdline.get_string() == "CHANNEL 1 THRU "

    vc._on_clear(vc.clear)
    assert cmdline.get_string() == ""

    # Test cue syntax
    vc._on_cue(vc.cue)
    assert cmdline.get_string() == "CUE "

    vc._on_1(vc.one)
    vc._on_dot(vc.dot)
    vc._on_5(vc.five)
    assert cmdline.get_string() == "CUE 1.5"

    # Test address with slash
    cmdline.clear()
    vc._on_address(vc.address)
    assert cmdline.get_string() == "ADDRESS "
    vc._on_1(vc.one)
    vc._on_slash(vc.slash)
    vc._on_2(vc.two)
    assert cmdline.get_string() == "ADDRESS 1/2"

    # Test unblock
    cmdline.clear()
    vc._on_cue(vc.cue)
    vc._on_1(vc.one)
    vc._on_unblock(vc.unblock)
    assert cmdline.get_string() == "CUE 1 UNBLOCK "

    # Test home and locate
    cmdline.clear()
    vc._on_1(vc.one)
    vc._on_home(vc.home)
    assert cmdline.get_string() == "1 HOME"

    cmdline.clear()
    vc._on_1(vc.one)
    vc._on_locate(vc.locate)
    assert cmdline.get_string() == "1 LOCATE"

    cmdline.clear()
    vc.close()
    process_events()


def test_virtual_console_sensitivity_flow(app_gui: Application) -> None:
    """Test dynamic button sensitivity updates correctly as tokens are typed."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console
    cmdline = app_gui.core.commandline

    # When empty:
    cmdline.clear()
    vc.update_button_sensitivity()
    assert vc.channel.get_sensitive() is True
    assert vc.cue.get_sensitive() is True
    assert vc.group.get_sensitive() is True
    assert vc.address.get_sensitive() is True
    assert vc.enter.get_sensitive() is False
    assert vc.backspace.get_sensitive() is False
    assert vc.slash.get_sensitive() is False
    assert vc.thru.get_sensitive() is True  # Can continue existing fixture selection

    # After entering a channel: "1 "
    cmdline.set_string("1 ")
    vc.update_button_sensitivity()
    assert vc.enter.get_sensitive() is True
    assert vc.backspace.get_sensitive() is True
    assert vc.thru.get_sensitive() is True
    assert vc.plus.get_sensitive() is True
    assert vc.minus.get_sensitive() is True
    assert vc.at_level.get_sensitive() is True
    assert vc.home.get_sensitive() is True
    assert vc.locate.get_sensitive() is True
    assert vc.position.get_sensitive() is True

    # After complete command "1 AT 50"
    cmdline.set_string("1 AT 50")
    vc.update_button_sensitivity()
    assert vc.enter.get_sensitive() is True
    assert vc.thru.get_sensitive() is False

    cmdline.clear()
    vc.close()
    process_events()
