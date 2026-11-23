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
"""GUI-specific tests for tab actions in Application and Bridge."""

from __future__ import annotations

import typing

import pytest
from gi.repository import Gtk

from olc.gtk3.application import Application
from olc.gtk3.settings import SettingsTab
from test.gtk3.conftest import process_events  # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_app_callbacks_execute_switch_tab_action(app_gui: Application) -> None:
    """Test that menu callbacks trigger SwitchTabAction on the Core."""
    executed_actions = []
    original_execute = app_gui.core.action_registry.execute

    def mock_execute(
        name: str,
        *args: typing.Any,  # noqa: ANN401
        **kwargs: typing.Any,  # noqa: ANN401
    ) -> typing.Any:  # noqa: ANN401
        executed_actions.append((name, args))
        return original_execute(name, *args, **kwargs)

    registry = typing.cast(typing.Any, app_gui.core.action_registry)
    registry.execute = mock_execute

    try:
        # Call independents callback
        app_gui.independents(None, None)
        process_events()
        assert ("gui.tab_open", ("indes",)) in executed_actions

        # Call curves callback
        app_gui.curves(None, None)
        process_events()
        assert ("gui.tab_open", ("curves",)) in executed_actions

        # Call faders callback
        app_gui.faders(None, None)
        process_events()
        assert ("gui.tab_open", ("faders",)) in executed_actions
    finally:
        registry.execute = original_execute


def test_manual_tab_switch_executes_action(app_gui: Application) -> None:
    """Test that manual notebook page switch triggers gui.tab_open action."""
    # Ensure window and tabs are open
    app_gui.faders(None, None)
    process_events()

    assert app_gui.tabs is not None
    tab = app_gui.tabs.tabs["faders"]
    assert tab is not None
    notebook = tab.get_parent()
    assert notebook is not None
    notebook_nb = typing.cast(Gtk.Notebook, notebook)

    executed_actions = []
    original_execute = app_gui.core.action_registry.execute

    def mock_execute(
        name: str,
        *args: typing.Any,  # noqa: ANN401
        **kwargs: typing.Any,  # noqa: ANN401
    ) -> typing.Any:  # noqa: ANN401
        executed_actions.append((name, args))
        return original_execute(name, *args, **kwargs)

    registry = typing.cast(typing.Any, app_gui.core.action_registry)
    registry.execute = mock_execute

    try:
        # Switch physically to page 0 (playback)
        notebook_nb.set_current_page(0)
        process_events()

        assert ("gui.tab_open", ("playback", "playback")) in executed_actions
    finally:
        registry.execute = original_execute


def test_gui_tab_cross_notebook_move(app_gui: Application) -> None:
    """Test moving a tab between notebooks physically and checking its Undo/Redo."""
    app = app_gui
    # Open "indes" tab (starts in playback by default)
    app.independents(None, None)
    process_events()

    assert app.window is not None
    assert app.tabs is not None
    tab = app.tabs.tabs["indes"]
    assert tab is not None
    notebook = tab.get_parent()
    assert notebook is app.window.playback

    # Move "indes" to live notebook logically (simulating move_tab shortcut)
    app.core.action_registry.execute("gui.tab_move", "indes", "playback", "live", 0)
    process_events()

    # Verify physical parent is now live_view
    assert tab.get_parent() is app.window.live_view

    # Undo the move action
    app.core.history.undo()
    process_events()

    # Verify tab is back in playback notebook
    assert tab.get_parent() is app.window.playback

    # Redo the move action
    app.core.history.redo()
    process_events()

    # Verify tab is in live notebook again
    assert tab.get_parent() is app.window.live_view


def test_settings_tab_home_preset_spin_and_undo_redo(app_gui: Application) -> None:
    """Test SettingsTab Home Preset SpinButton sync with action and show.new."""
    app = app_gui
    app.core.lightshow.home_preset = None
    app.core.history.clear()

    try:
        app.core.action_registry.execute("gui.tab_open", "settings")
        process_events()

        assert app.tabs is not None
        settings_tab = typing.cast(SettingsTab, app.tabs.tabs["settings"])
        assert settings_tab is not None
        assert settings_tab.spin_home_preset is not None
        assert settings_tab.spin_home_preset.get_value() == pytest.approx(0.0)

        # User changes SpinButton to 999.0
        settings_tab.spin_home_preset.set_value(999.0)
        process_events()
        assert app.core.lightshow.home_preset == pytest.approx(999.0)

        # Undo restores None and UI resets to 0.0
        app.core.history.undo()
        process_events()
        assert app.core.lightshow.home_preset is None
        assert settings_tab.spin_home_preset.get_value() == pytest.approx(0.0)

        # Redo restores 999.0 and UI updates
        app.core.history.redo()
        process_events()
        assert app.core.lightshow.home_preset == pytest.approx(999.0)
        assert settings_tab.spin_home_preset.get_value() == pytest.approx(999.0)

        # Setting 0.0 clears home_preset
        settings_tab.spin_home_preset.set_value(0.0)
        process_events()
        assert app.core.lightshow.home_preset is None

        # Setting value and creating a new show resets both model and UI
        settings_tab.spin_home_preset.set_value(50.0)
        process_events()
        assert app.core.lightshow.home_preset == pytest.approx(50.0)

        app.core.action_registry.execute("show.new")
        process_events()
        assert app.core.lightshow.home_preset is None
        assert settings_tab.spin_home_preset.get_value() == pytest.approx(0.0)
    finally:
        app.core.lightshow.home_preset = None
        app.core.lightshow.title = ""
        app.core.history.clear()


def test_settings_tab_fader_pages_spin_warning_and_undo_redo(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test SettingsTab spin_fader_pages hot update, reduction warning, and Undo."""
    from olc.show.fader import FaderType

    app = app_gui
    app.core.lightshow.fader_bank.reset_faders(reset_page_count=True)
    app.core.history.clear()

    try:
        app.core.action_registry.execute("gui.tab_open", "settings")
        process_events()

        assert app.tabs is not None
        settings_tab = typing.cast(SettingsTab, app.tabs.tabs["settings"])
        assert settings_tab.spin_fader_pages is not None
        assert settings_tab.spin_fader_pages.get_value_as_int() == 10

        # Increase hot to 15 pages
        settings_tab.spin_fader_pages.set_value(15.0)
        process_events()
        assert app.core.lightshow.fader_bank.max_fader_page == 15

        # Populate a fader on page 12
        app.core.action_registry.execute("fader.assign", 12, 1, FaderType.MAIN)
        process_events()

        # Cancel reduction warning -> stays at 15 and widget reverts to 15
        monkeypatch.setattr(
            settings_tab,
            "_confirm_fader_pages_reduction",
            lambda _new, _pop: False,
        )
        settings_tab.spin_fader_pages.set_value(5.0)
        process_events()
        assert app.core.lightshow.fader_bank.max_fader_page == 15
        assert settings_tab.spin_fader_pages.get_value_as_int() == 15
        assert app.core.lightshow.fader_bank.get_fader_type(12, 1) == FaderType.MAIN

        # Confirm reduction warning -> drops to 5, Undo brings page 12 back
        monkeypatch.setattr(
            settings_tab,
            "_confirm_fader_pages_reduction",
            lambda _new, _pop: True,
        )
        settings_tab.spin_fader_pages.set_value(5.0)
        process_events()
        assert app.core.lightshow.fader_bank.max_fader_page == 5
        assert 12 not in app.core.lightshow.fader_bank.faders

        app.core.history.undo()
        process_events()
        assert app.core.lightshow.fader_bank.max_fader_page == 15
        assert app.core.lightshow.fader_bank.get_fader_type(12, 1) == FaderType.MAIN
        assert settings_tab.spin_fader_pages.get_value_as_int() == 15
    finally:
        app.core.lightshow.fader_bank.reset_faders(reset_page_count=True)
        app.core.history.clear()


def test_settings_tab_skip_empty_fader_pages_switch(app_gui: Application) -> None:
    """Test SettingsTab skip_empty_fader_pages switch, Undo/Redo, and show.new."""
    app = app_gui
    app.core.lightshow.fader_bank.reset_faders(reset_page_count=True)
    app.core.history.clear()

    try:
        app.core.action_registry.execute("gui.tab_open", "settings")
        process_events()

        assert app.tabs is not None
        settings_tab = typing.cast(SettingsTab, app.tabs.tabs["settings"])
        sw = settings_tab.switch_skip_empty_fader_pages
        assert sw is not None
        assert sw.get_active() is False

        # Enable via UI switch
        sw.set_active(True)
        process_events()
        assert app.core.lightshow.fader_bank.skip_empty_pages is True
        assert sw.get_state() is True

        # Undo disables in model and UI
        app.core.history.undo()
        process_events()
        assert app.core.lightshow.fader_bank.skip_empty_pages is False
        assert sw.get_state() is False

        # Redo re-enables in model and UI
        app.core.history.redo()
        process_events()
        assert app.core.lightshow.fader_bank.skip_empty_pages is True
        assert sw.get_state() is True

        # show.new resets skip_empty_pages to False in model and UI
        app.core.action_registry.execute("show.new")
        process_events()
        assert app.core.lightshow.fader_bank.skip_empty_pages is False
        assert sw.get_state() is False
    finally:
        app.core.lightshow.fader_bank.reset_faders(reset_page_count=True)
        app.core.history.clear()


def test_settings_tab_notifications_switch(app_gui: Application) -> None:
    """Test SettingsTab desktop notifications switch, GSettings, and Undo/Redo."""
    app = app_gui
    app.core.history.clear()
    schema = getattr(app.settings.props, "settings_schema", None)
    if (
        schema is not None
        and hasattr(schema, "has_key")
        and not schema.has_key("notifications")
    ):
        pytest.skip("GSettings schema not yet compiled with 'notifications' key")

    orig_enabled = bool(app.settings.get_boolean("notifications"))
    app.settings.set_boolean("notifications", True)

    try:
        app.core.action_registry.execute("gui.tab_open", "settings")
        process_events()

        assert app.tabs is not None
        settings_tab = typing.cast(SettingsTab, app.tabs.tabs["settings"])
        sw = settings_tab.switch_notifications
        assert sw is not None
        assert sw.get_active() is True

        # Disable via UI switch
        sw.set_active(False)
        process_events()
        assert app.settings.get_boolean("notifications") is False
        assert sw.get_state() is False

        # Undo restores True in GSettings and UI
        app.core.history.undo()
        process_events()
        assert app.settings.get_boolean("notifications") is True
        assert sw.get_state() is True

        # Redo disables again in GSettings and UI
        app.core.history.redo()
        process_events()
        assert app.settings.get_boolean("notifications") is False
        assert sw.get_state() is False
    finally:
        app.settings.set_boolean("notifications", orig_enabled)
        app.core.history.clear()


def test_fullscreen_keeps_menu_button_and_main_fader(app_gui: Application) -> None:
    """Verify fullscreen keeps burger menu, main fader, and title/subtitle visible."""
    win = app_gui.window
    assert win is not None
    orig_title = win.header.get_title() or "Open Lighting Console"
    orig_subtitle = win.header.get_subtitle() or ""

    try:
        assert win.full is False
        assert win.fullscreen_header.get_visible() is False
        assert win.header_controls.get_parent() is win.header
        assert win.menu_button.get_parent() is win.header_controls

        app_gui.core.action_registry.execute("gui.toggle_fullscreen")
        process_events()

        assert win.full is True
        assert win.fullscreen_header.get_visible() is True
        assert win.header_controls.get_parent() is win.fullscreen_header
        assert win.menu_button.get_visible() is True
        assert win.main_fader.get_visible() is True

        win.header.set_title("Show FS")
        win.header.set_subtitle("Cue 1")
        assert win.fullscreen_header.get_title() == "Show FS"
        assert win.fullscreen_header.get_subtitle() == "Cue 1"

        app_gui.core.action_registry.execute("gui.toggle_fullscreen")
        process_events()

        assert win.full is False
        assert win.fullscreen_header.get_visible() is False
        assert win.header_controls.get_parent() is win.header
        assert win.menu_button.get_visible() is True
    finally:
        if win.full:
            app_gui.core.action_registry.execute("gui.toggle_fullscreen")
            process_events()
        win.header.set_title(orig_title)
        win.header.set_subtitle(orig_subtitle)
