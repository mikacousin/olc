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
"""GUI behavior tests for the Faders tab and Virtual Console faders."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals, no-name-in-module

from __future__ import annotations

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.fader import FaderTab  # noqa: E402
from olc.show.fader_bank import FaderType  # noqa: E402
from olc.show.palette import Palette, PaletteCategory  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_fader_tab_behavior(app_gui: Application) -> None:
    """Test FaderTab configuration and undo/redo."""
    # 1. Open faders tab
    app_gui.activate_action("faders", None)
    process_events()

    assert app_gui.tabs is not None
    fader_tab = app_gui.tabs.tabs.get("faders")
    assert isinstance(fader_tab, FaderTab)

    # 2. Get first fader (page 1, index 1)
    fader_edit = fader_tab.fader_widgets.get((1, 1))

    assert fader_edit is not None, "FaderEdit for page 1, index 1 not found"
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE

    # 3. Configure fader 1 as PRESET fader
    app_gui.core.lightshow.palettes.clear()
    app_gui.core.lightshow.palettes.add(
        Palette(PaletteCategory.PRESET, 1.0, "Preset A", channels={1: 1.0})
    )
    process_events()

    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is None
    )

    # Setting type to PRESET
    fader_edit._on_type_changed(Gtk.ModelButton(), FaderType.PRESET)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is None
    )

    # Setting contents to Preset 1.0
    mock_button = Gtk.ModelButton()
    mock_button.set_label("1 : Preset A")
    fader_edit._on_contents_changed(mock_button, FaderType.PRESET, 1.0)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is not None
    )

    # Simulate raising the fader to 50%
    app_gui.core.lightshow.fader_bank.faders[1][1].set_level(0.5)
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.5

    # 4. Change contents to Preset B (2.0)
    app_gui.core.lightshow.palettes.add(
        Palette(PaletteCategory.PRESET, 2.0, "Preset B", channels={2: 1.0})
    )
    process_events()
    mock_button2 = Gtk.ModelButton()
    mock_button2.set_label("2 : Preset B")
    fader_edit._on_contents_changed(mock_button2, FaderType.PRESET, 2.0)
    process_events()

    # The fader level is reset to 0 upon content change
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.0
    contents_b = getattr(
        app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None
    )
    assert contents_b is not None
    assert contents_b.number == 2.0

    # Raise the fader again to 50%
    app_gui.core.lightshow.fader_bank.faders[1][1].set_level(0.5)

    # 5. First Ctrl+Z (reverts contents to Preset A)
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    # The level must be reset to 0 because content changed back to Preset A (1.0)
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.0
    contents_a = getattr(
        app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None
    )
    assert contents_a is not None
    assert contents_a.number == 1.0

    # Raise the fader again to 50%
    app_gui.core.lightshow.fader_bank.faders[1][1].set_level(0.5)

    # 6. Second Ctrl+Z (reverts contents to None)
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.0
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is None
    )

    # Raise the fader again to 50% (should be inert on a type with None contents,
    # but let's test the type change level reset)
    app_gui.core.lightshow.fader_bank.faders[1][1].set_level(0.5)

    # 7. Third Ctrl+Z (reverts type to NONE)
    app_gui.activate_action("undo", None)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.0
    assert (
        getattr(app_gui.core.lightshow.fader_bank.faders[1][1], "contents", None)
        is None
    )


def test_fader_set_level_action(app_gui: Application) -> None:
    """Test that fader.set_level action works and correctly updates Virtual Console."""
    # 1. Setup Virtual Console GUI
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None

    # Get first fader (widget and logical fader)
    gui_fader_widget = app_gui.virtual_console.faders[0]
    logical_fader = app_gui.core.lightshow.fader_bank.faders[1][1]

    # Verify initial levels
    assert logical_fader.level == 0.0
    assert gui_fader_widget.get_value() == 0.0

    # 2. Configure fader 1 contents as Preset 1 (channels: {1: 1.0})
    app_gui.core.lightshow.palettes.clear()
    app_gui.core.lightshow.palettes.add(
        Palette(PaletteCategory.PRESET, 1.0, "Preset A", channels={1: 1.0})
    )
    app_gui.core.lightshow.fader_bank.set_fader(1, 1, FaderType.PRESET, 1.0)
    process_events()

    # Re-evaluate logical_fader as it has been replaced with a FaderPreset instance
    logical_fader = app_gui.core.lightshow.fader_bank.faders[1][1]
    assert logical_fader.level == 0.0
    assert logical_fader.dmx[0] == 0

    # 3. Execute action: Set fader 1 (page 1, index 1) to 80% (0.8)
    app_gui.core.action_registry.execute("fader.set_level", 1, 1, 0.8)
    process_events()

    # 4. Assert passive updates
    # A. Model level updated to 0.8
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.8
    # B. DMX output reflects normalized change (channel 1 is at 80% -> 0.8)
    assert app_gui.core.lightshow.fader_bank.faders[1][1].dmx[0] == pytest.approx(0.8)
    # C. GUI fader widget value updated to 0.8 * 255 = 204
    assert gui_fader_widget.get_value() == 204.0

    # 5. Move GUI fader slider directly to 50%
    gui_fader_widget.set_value(127.5)  # 50%
    # Trigger value-changed callback
    app_gui.virtual_console.fader_moved(gui_fader_widget)
    process_events()

    # Model and DMX must reflect 50%
    assert app_gui.core.lightshow.fader_bank.faders[1][1].level == 0.5
    assert app_gui.core.lightshow.fader_bank.faders[1][1].dmx[0] == pytest.approx(0.5)

    # Close Virtual Console window
    app_gui.virtual_console.close()
    process_events()


def test_virtual_console_present_if_already_open(app_gui: Application) -> None:
    """Test that virtual_console action calls present() if already open."""
    # 1. Open the virtual console
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None

    # 2. Patch present() method
    from unittest.mock import patch

    with patch.object(app_gui.virtual_console, "present") as mock_present:
        # 3. Activate action again
        app_gui.activate_action("virtual_console", None)
        process_events()

        # 4. Check that present was called
        mock_present.assert_called_once()

    # Clean up
    app_gui.virtual_console.close()
    process_events()


def test_fader_set_page_action(app_gui: Application) -> None:
    """Test that fader.set_page action works and correctly updates Virtual Console."""
    # 1. Setup Virtual Console GUI
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None

    # Verify initial page is 1
    assert app_gui.core.lightshow.fader_bank.active_page == 1
    assert app_gui.virtual_console.page_number.get_label() == "1"

    # 2. Execute fader.set_page action to switch to page 2
    app_gui.core.action_registry.execute("fader.set_page", 2)
    process_events()

    # Verify page is 2 in model and GUI
    assert app_gui.core.lightshow.fader_bank.active_page == 2
    assert app_gui.virtual_console.page_number.get_label() == "2"

    # 3. Click Page+ button on Virtual Console (should transition to page 3)
    app_gui.virtual_console._on_fader_page(app_gui.virtual_console.fader_page_plus)
    process_events()

    assert app_gui.core.lightshow.fader_bank.active_page == 3
    assert app_gui.virtual_console.page_number.get_label() == "3"

    # 4. Click Page- button on Virtual Console (should transition back to page 2)
    app_gui.virtual_console._on_fader_page(app_gui.virtual_console.fader_page_minus)
    process_events()

    assert app_gui.core.lightshow.fader_bank.active_page == 2
    assert app_gui.virtual_console.page_number.get_label() == "2"

    # Clean up
    app_gui.virtual_console.close()
    process_events()


def test_virtual_console_ctrl_w_closes_window_without_sequence_step(
    app_gui: Application,
) -> None:
    """Test that Control+W on focused virtual console closes it without
    advancing sequence.
    """
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    initial_pos = app_gui.core.lightshow.main_playback.position

    handled = vc._on_key_controller_pressed(
        vc.key_controller, Gdk.KEY_w, 0, Gdk.ModifierType.CONTROL_MASK
    )
    process_events()

    assert handled is True
    assert app_gui.virtual_console is None
    assert app_gui.core.lightshow.main_playback.position == initial_pos


def test_window_key_controller_ignores_ctrl_w(app_gui: Application) -> None:
    """Test that main Window._on_key_controller_pressed ignores keys with Control."""
    assert app_gui.window is not None
    initial_pos = app_gui.core.lightshow.main_playback.position

    res = app_gui.window._on_key_controller_pressed(
        app_gui.window.key_controller, Gdk.KEY_w, 0, Gdk.ModifierType.CONTROL_MASK
    )
    process_events()

    assert res is False
    assert app_gui.core.lightshow.main_playback.position == initial_pos


def test_virtual_console_normal_key_delegates_to_live_view(
    app_gui: Application,
) -> None:
    """Test that normal keys without modifiers delegate to live view."""
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console

    vc._on_key_controller_pressed(vc.key_controller, Gdk.KEY_9, 0, Gdk.ModifierType(0))
    process_events()

    assert app_gui.core.commandline.get_string() == "9"
    app_gui.core.action_registry.execute("commandline.clear")

    vc.close()
    process_events()


def test_fader_tab_effect_assignment_and_virtual_console_effect_key(
    app_gui: Application,
) -> None:
    """Test FaderType.EFFECT in FaderTab and the Effect key in VirtualConsole."""
    app_gui.core.action_registry.execute(
        "effect.create", 1.0, "Sine Wave", template_id="sine_dimmer"
    )
    app_gui.core.selected_channels = [1, 2]
    process_events()

    # 1. Open Faders tab and assign Fader 2 on Page 1 to EFFECT 1.0
    app_gui.activate_action("faders", None)
    process_events()
    assert app_gui.tabs is not None
    fader_tab = app_gui.tabs.tabs.get("faders")
    assert isinstance(fader_tab, FaderTab)

    fader_edit = fader_tab.fader_widgets.get((1, 2))
    assert fader_edit is not None

    fader_edit._on_type_changed(Gtk.ModelButton(), FaderType.EFFECT)
    process_events()
    assert app_gui.core.lightshow.fader_bank.get_fader_type(1, 2) == FaderType.EFFECT

    btn = Gtk.ModelButton()
    btn.set_label("1 : Sine Wave")
    fader_edit._on_contents_changed(btn, FaderType.EFFECT, 1.0)
    process_events()
    fader2 = app_gui.core.lightshow.fader_bank.faders[1][2]
    assert fader2.contents is not None
    assert fader2.contents.number == 1.0

    # Verify FaderEdit effect controls (Mode + Target Channels)
    assert fader_edit.effect_controls_box is not None
    assert fader_edit.effect_mode_button is not None
    assert fader_edit.effect_channels_button is not None

    fader_edit._on_effect_mode_changed(Gtk.ModelButton(), "both")
    process_events()
    assert fader2.control_mode == "both"
    assert fader_edit.effect_mode_button.get_label() == "Mode: Size+Rate"

    app_gui.core.selected_channels = [5, 6, 7]
    fader_edit._on_effect_channels_from_selection(Gtk.ModelButton())
    process_events()
    assert fader2.effect_channels == [5, 6, 7]
    assert fader_edit.effect_channels_button.get_label() == "Ch 5..7"

    fader_edit._on_effect_channels_clear(Gtk.ModelButton())
    process_events()
    assert fader2.effect_channels == []
    assert fader_edit.effect_channels_button.get_label() == "Auto (Sel)"

    # Restore channels & mode to keep size scaling check clean
    fader_edit._on_effect_mode_changed(Gtk.ModelButton(), "size")
    app_gui.core.selected_channels = [1, 2]
    fader_edit._on_effect_channels_from_selection(Gtk.ModelButton())
    process_events()

    # Move fader 2 to 60% -> starts effect
    app_gui.core.action_registry.execute("fader.set_level", 1, 2, 0.6)
    process_events()
    active = app_gui.core.effects_engine.get_active_instances()
    assert len(active) == 1
    assert active[0].size_scale == pytest.approx(0.6)

    # Bring fader 2 back to 0% -> stops effect
    app_gui.core.action_registry.execute("fader.set_level", 1, 2, 0.0)
    process_events()
    assert len(app_gui.core.effects_engine.get_active_instances()) == 0

    # Switching back to FaderType.NONE removes effect_controls_box
    fader_edit._on_type_changed(Gtk.ModelButton(), FaderType.NONE)
    process_events()
    assert fader_edit.effect_controls_box is None

    # 2. Verify Virtual Console Effect button
    app_gui.activate_action("virtual_console", None)
    process_events()
    assert app_gui.virtual_console is not None
    vc = app_gui.virtual_console
    assert hasattr(vc, "effect")
    assert vc.effect.text == "effect"
    assert vc.effect.shortcut_text == "Alt+E"

    app_gui.core.action_registry.execute("commandline.clear")
    vc._on_effect(vc.effect)
    process_events()
    assert app_gui.core.commandline.get_string() == "EFFECT "

    app_gui.core.action_registry.execute("commandline.clear")
    vc.close()
    process_events()


def test_fader_tab_page_selector_and_hot_resize(app_gui: Application) -> None:
    """Test FaderTab Page -/SpinButton/Page + selector and hot page resize."""
    app_gui.core.lightshow.fader_bank.reset_faders(reset_page_count=True)
    app_gui.core.history.clear()

    try:
        app_gui.activate_action("faders", None)
        process_events()

        assert app_gui.tabs is not None
        fader_tab = app_gui.tabs.tabs.get("faders")
        assert isinstance(fader_tab, FaderTab)

        # On-demand instantiation: only Page 1 widgets exist initially
        assert fader_tab.current_page == 1
        assert len(fader_tab.fader_widgets) == 10
        assert set(fader_tab.fader_widgets.keys()) == {(1, i) for i in range(1, 11)}

        # Page + increments to page 2
        fader_tab.btn_page_next.clicked()
        process_events()
        assert fader_tab.current_page == 2
        assert fader_tab.spin_page.get_value_as_int() == 2
        assert set(fader_tab.fader_widgets.keys()) == {(2, i) for i in range(1, 11)}

        # Page - wraps cleanly from 2 -> 1 -> 10
        fader_tab.btn_page_prev.clicked()
        process_events()
        assert fader_tab.current_page == 1
        fader_tab.btn_page_prev.clicked()
        process_events()
        assert fader_tab.current_page == 10
        assert set(fader_tab.fader_widgets.keys()) == {(10, i) for i in range(1, 11)}

        # Hot-increase to 15 pages and navigate via SpinButton to page 14
        app_gui.core.action_registry.execute("fader.set_page_count", page_count=15)
        process_events()
        assert fader_tab.label_total_pages.get_text() == "/ 15"
        fader_tab.spin_page.set_value(14.0)
        process_events()
        assert fader_tab.current_page == 14
        assert (14, 1) in fader_tab.fader_widgets

        # Hot-decrease to 5 pages clamps current_page cleanly to 5
        app_gui.core.action_registry.execute("fader.set_page_count", page_count=5)
        process_events()
        assert fader_tab.current_page == 5
        assert fader_tab.spin_page.get_value_as_int() == 5
        assert fader_tab.label_total_pages.get_text() == "/ 5"
        assert set(fader_tab.fader_widgets.keys()) == {(5, i) for i in range(1, 11)}
    finally:
        app_gui.core.lightshow.fader_bank.reset_faders(reset_page_count=True)
        app_gui.core.history.clear()
