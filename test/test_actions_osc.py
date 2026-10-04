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
"""Unit tests for OSC actions and Undo/Redo."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from gi.repository import Gtk
from olc.core.app import CoreApplication
from olc.core.backends.osc.delegate import OSCDelegate
from olc.core.osc import EngineOSCServer
from olc.gtk3.event_bridge import GuiEventBridge
from olc.gtk3.window import Window
from olc.settings import SettingsTab


def test_osc_toggle_enable_and_disable() -> None:
    """Test osc.toggle action to enable and disable OSC services."""
    settings = MagicMock()
    settings.get_boolean.return_value = False
    settings.get_string.return_value = "192.168.1.100"
    settings.get_int.side_effect = lambda key: (
        8001 if key == "osc-client-port" else 9001
    )

    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    toggled_events: list[bool] = []

    def on_osc_toggled(enabled: bool) -> None:
        toggled_events.append(enabled)

    app.subscribe("osc.toggled", on_osc_toggled)

    # 1. Enable OSC
    app.action_registry.execute("osc.toggle", True)
    assert toggled_events == [True]
    mock_engine.start_osc.assert_called_once_with(
        host="192.168.1.100",
        client_port=8001,
        server_port=9001,
    )
    mock_engine.register_osc_delegate.assert_called_once()
    assert getattr(app, "osc_delegate", None) is not None
    assert len(app.history.undo_stack) == 1

    # Undo toggle -> Disable OSC
    app.history.undo()
    assert toggled_events == [True, False]
    mock_engine.stop_osc.assert_called_once()
    assert getattr(app, "osc_delegate", None) is None

    # Redo toggle -> Re-enable OSC
    app.history.redo()
    assert toggled_events == [True, False, True]
    assert mock_engine.start_osc.call_count == 2
    assert getattr(app, "osc_delegate", None) is not None


def test_osc_set_config_and_undo_redo() -> None:
    """Test osc.set_config action and its undo/redo capabilities."""
    settings = MagicMock()
    settings.get_string.return_value = "127.0.0.1"
    settings.get_int.side_effect = lambda key: (
        8000 if key == "osc-client-port" else 9000
    )

    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    config_events: list[tuple[str, int, int]] = []

    def on_config_changed(host: str, client_port: int, server_port: int) -> None:
        config_events.append((host, client_port, server_port))

    app.subscribe("osc.config_changed", on_config_changed)

    # Execute new configuration
    app.action_registry.execute("osc.set_config", "10.0.0.42", 8020, 9020)
    mock_engine.update_osc_client.assert_called_once_with(host="10.0.0.42", port=8020)
    mock_engine.update_osc_server.assert_called_once_with(9020)
    assert config_events == [("10.0.0.42", 8020, 9020)]

    # Undo configuration change
    app.history.undo()
    assert mock_engine.update_osc_client.call_count == 2
    mock_engine.update_osc_client.assert_called_with(host="127.0.0.1", port=8000)
    assert mock_engine.update_osc_server.call_count == 2
    mock_engine.update_osc_server.assert_called_with(9000)
    assert config_events == [("10.0.0.42", 8020, 9020), ("127.0.0.1", 8000, 9000)]

    # Redo configuration change
    app.history.redo()
    assert mock_engine.update_osc_client.call_count == 3
    mock_engine.update_osc_client.assert_called_with(host="10.0.0.42", port=8020)
    assert mock_engine.update_osc_server.call_count == 3
    mock_engine.update_osc_server.assert_called_with(9020)
    assert config_events[-1] == ("10.0.0.42", 8020, 9020)


def test_osc_delegate_telemetry_events() -> None:
    """Test OSCDelegate sends telemetry in response to core decoupled events."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    delegate = OSCDelegate(app)
    app.osc_delegate = delegate

    # 1. Test commandline.changed telemetry
    app.commandline.set_string("1 THRU 10 @ 80")
    mock_engine.send_osc.assert_called_with("/olc/command_line", "1 THRU 10 @ 80")

    # 2. Test fader.level_changed telemetry
    app.emit("fader.level_changed", 3, 0.5)
    mock_engine.send_osc.assert_called_with("/olc/fader/1/3/level", 128)

    # 3. Test patch.selected_outputs_changed telemetry
    app.lightshow.patch_by_outputs.outputs = [1, 2]
    app.lightshow.patch_by_outputs.last = 2
    app.emit("patch.selected_outputs_changed")
    mock_engine.send_osc.assert_called_with(
        "/olc/patch/selected_outputs", app.lightshow.patch_by_outputs.get_selected()
    )


def test_engine_osc_server_action_dispatch() -> None:
    """Test EngineOSCServer dispatches blackout and set_channels via action registry."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    mock_engine.app = app
    app.engine = mock_engine

    server = EngineOSCServer(9000, engine=mock_engine)
    delegate = OSCDelegate(app)
    server.register_delegate(delegate)

    # 1. Dispatch blackout route
    blackout_events: list[int] = []

    def on_blackout(univ: int) -> None:
        blackout_events.append(univ)

    app.subscribe("universe.blackout_changed", on_blackout)
    server.dispatch("/olc/universe/2/blackout", [])
    assert blackout_events == [2]

    # 2. Dispatch set_channels route (dict format)
    dmx_events: list[tuple[int, dict[int, int]]] = []

    def on_dmx(univ: int, chs: dict[int, int]) -> None:
        dmx_events.append((univ, chs))

    app.subscribe("universe.dmx_changed", on_dmx)
    server.dispatch("/olc/universe/3/set_channels", ['{"0": 255, "1": 128}'])
    assert dmx_events == [(3, {0: 255, 1: 128})]

    # 3. Dispatch set_channels route (pairs format)
    server.dispatch("/olc/universe/3/set_channels", [5, 200, 6, 100])
    assert dmx_events[-1] == (3, {5: 200, 6: 100})


def test_event_bridge_osc_settings_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GuiEventBridge routes osc.config_changed and osc.toggled to SettingsTab."""
    monkeypatch.setattr("gi.repository.GLib.idle_add", lambda func, *args: func(*args))
    mock_app = MagicMock()
    core = CoreApplication(MagicMock())
    mock_app.core = core

    mock_settings_tab = MagicMock()
    mock_app.tabs = MagicMock()
    mock_app.tabs.tabs = {"settings": mock_settings_tab}

    _bridge = GuiEventBridge(mock_app)

    # 1. Trigger osc.config_changed via action undo
    core.emit("osc.config_changed", "192.168.1.55", 8055, 9055)
    mock_settings_tab.update_osc_config.assert_called_once_with(
        "192.168.1.55", 8055, 9055
    )

    # 2. Trigger osc.toggled via action undo
    core.emit("osc.toggled", False)
    mock_settings_tab.update_osc_toggle.assert_called_once_with(False)


def test_settings_tab_update_osc() -> None:
    """Test SettingsTab programmatic updates for OSC widgets."""
    # pylint: disable=protected-access
    tab = SettingsTab.__new__(SettingsTab)
    tab._updating_settings = False
    tab.entry_client_ip = MagicMock()
    tab.entry_client_ip.get_text.return_value = "127.0.0.1"
    tab.spin_client_port = MagicMock()
    tab.spin_client_port.get_value_as_int.return_value = 8000
    tab.spin_client_port.get_text.return_value = "8000"
    tab.spin_server_port = MagicMock()
    tab.spin_server_port.get_value_as_int.return_value = 9000
    tab.spin_server_port.get_text.return_value = "9000"
    tab.switch_osc = MagicMock()
    tab.switch_osc.get_state.return_value = True

    tab.update_osc_config("192.168.0.99", 8099, 9099)
    tab.entry_client_ip.set_text.assert_called_once_with("192.168.0.99")
    tab.spin_client_port.set_value.assert_called_once_with(8099)
    tab.spin_server_port.set_value.assert_called_once_with(9099)
    assert not tab._updating_settings

    # Verify updating when text is dirty/uncommitted
    tab.spin_client_port.get_value_as_int.return_value = 8099
    tab.spin_client_port.get_text.return_value = "9999"  # dirty text
    tab.spin_client_port.set_value.reset_mock()
    tab.update_osc_config("192.168.0.99", 8099, 9099)
    tab.spin_client_port.set_value.assert_called_once_with(8099)

    tab.update_osc_toggle(False)
    tab.switch_osc.set_state.assert_called_once_with(False)
    tab.switch_osc.set_active.assert_called_once_with(False)
    assert not tab._updating_settings


def test_settings_tab_client_ip_focus_out() -> None:
    """Test SettingsTab validates IP on focus out."""
    # pylint: disable=protected-access
    tab = SettingsTab.__new__(SettingsTab)
    tab._updating_settings = False
    tab.settings = MagicMock()
    tab.settings.get_string.return_value = "127.0.0.1"
    tab.app = MagicMock()
    tab.get_parent = MagicMock(return_value=None)

    entry = MagicMock(spec=Gtk.Entry)

    # 1. IP unchanged -> no action executed
    entry.get_text.return_value = "127.0.0.1"
    res = tab._on_client_ip_focus_out(entry, MagicMock())
    assert res is False
    tab.app.core.action_registry.execute.assert_not_called()

    # 2. IP changed to valid IP -> osc.set_config executed
    entry.get_text.return_value = "192.168.1.50"
    res = tab._on_client_ip_focus_out(entry, MagicMock())
    assert res is False
    tab.app.core.action_registry.execute.assert_called_once_with(
        "osc.set_config", host="192.168.1.50"
    )

    # 3. IP changed to invalid IP -> text reverted
    entry.get_text.return_value = "invalid_ip"
    tab.app.core.action_registry.execute.reset_mock()
    res = tab._on_client_ip_focus_out(entry, MagicMock())
    assert res is False
    tab.app.core.action_registry.execute.assert_not_called()
    entry.set_text.assert_called_once_with("127.0.0.1")


def test_window_key_press_delegation() -> None:
    """Test on_window_key_press delegates to focused entry and allows global
    shortcuts."""
    win = Window.__new__(Window)
    mock_entry = MagicMock(spec=Gtk.Entry)
    win.get_focus = MagicMock(return_value=mock_entry)  # type: ignore[method-assign]

    event = MagicMock()

    # 1. Widget consumes event (e.g. space, text typing, Ctrl+C) -> returns True
    mock_entry.event.return_value = True
    assert win.on_window_key_press(MagicMock(), event) is True
    mock_entry.event.assert_called_once_with(event)

    # 2. Widget does not consume event (e.g. Ctrl+Z, Ctrl+Y, Ctrl+S) -> returns False
    mock_entry.event.reset_mock()
    mock_entry.event.return_value = False
    assert win.on_window_key_press(MagicMock(), event) is False
    mock_entry.event.assert_called_once_with(event)

    # 3. Non-entry focused -> returns False immediately without calling event()
    win.get_focus.return_value = MagicMock(spec=Gtk.Button)
    assert win.on_window_key_press(MagicMock(), event) is False
