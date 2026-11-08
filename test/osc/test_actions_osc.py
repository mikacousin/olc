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

import asyncio
from collections.abc import Coroutine
from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from olc.core.app import CoreApplication  # noqa: E402
from olc.core.backends.osc.delegate import OSCDelegate  # noqa: E402
from olc.core.engine import CoreEngine  # noqa: E402
from olc.core.osc import EngineOSCServer  # noqa: E402
from olc.core.universe_config import UniverseMap  # noqa: E402
from olc.gtk3.event_bridge import GuiEventBridge  # noqa: E402
from olc.gtk3.window import Window  # noqa: E402
from olc.settings import SettingsTab  # noqa: E402


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
        enable_static_client=False,
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
    app.action_registry.execute("commandline.set", "1 THRU 10 @ 80")
    mock_engine.publish_osc.assert_called_with(
        "commandline", "/olc/command_line", "1 THRU 10 @ 80"
    )

    # 2. Test fader.level_changed telemetry (normalized float 0.0..1.0)
    app.emit("fader.level_changed", 3, 0.5)
    mock_engine.publish_osc.assert_called_with("faders", "/olc/fader/1/3/level", 0.5)

    # 3. Test patch.changed telemetry
    app.emit("patch.changed")
    mock_engine.publish_osc.assert_called_with(
        "patch", "/olc/patch/changed", len(app.lightshow.patch.devices)
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


def test_osc_start_stop_reentrant_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test repeated start_osc calls without deadlocking on CoreEngine._lock."""

    # Ensure coroutines passed to threadsafe call are closed when loop is mocked
    def mock_run_coroutine(
        coro: Coroutine[object, object, object],
        _loop: asyncio.AbstractEventLoop,
    ) -> MagicMock:
        coro.close()
        return MagicMock()

    monkeypatch.setattr("asyncio.run_coroutine_threadsafe", mock_run_coroutine)

    engine = CoreEngine(UniverseMap(1), monitor_port=5555, no_listen=True)
    engine._network_thread = MagicMock()  # pylint: disable=protected-access

    # Start OSC first time
    engine.start_osc("127.0.0.1", 8000, 9000)
    assert engine.osc_server is not None
    assert engine.osc_client is not None

    # Start OSC second time while already running -> should call stop_osc() internally
    # and re-acquire lock without deadlock
    engine.start_osc("127.0.0.1", 8001, 9001)
    assert engine.osc_server is not None
    assert engine.osc_client is not None

    # Cleanup
    engine.stop_osc()
    engine.stop()
    assert engine.osc_server is None
    assert engine.osc_client is None


def test_osc_toggle_noop_not_undoable() -> None:
    """Test osc.toggle does not create an undoable action when state does not
    change."""
    settings = MagicMock()
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    # Executing toggle to True when already True should not push to history
    app.action_registry.execute("osc.toggle", True)
    assert len(app.history.undo_stack) == 0


def test_osc_delegate_cmd_execution() -> None:
    """Test /olc/cmd endpoint in OSCDelegate executes command and sends status."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    delegate = OSCDelegate(app)

    # 1. Valid command execution
    delegate._cmd("/olc/cmd", ["1 THRU 5 AT 80"])  # pylint: disable=protected-access
    mock_engine.publish_osc.assert_called_with("commandline", "/olc/cmd/status", "OK")

    # 2. Stripping trailing ENTER keyword (case-insensitive)
    delegate._cmd("/olc/cmd", ["10 AT FULL Enter"])  # pylint: disable=protected-access
    assert app.commandline.get_string() == ""  # Successful execution clears buffer
    mock_engine.publish_osc.assert_called_with("commandline", "/olc/cmd/status", "OK")

    # 3. Syntax error execution -> status sends error message
    mock_engine.publish_osc.reset_mock()
    delegate._cmd("/olc/cmd", ["1 AT INVALID_TOKEN"])  # pylint: disable=protected-access
    assert mock_engine.publish_osc.called
    status_call = [
        call
        for call in mock_engine.publish_osc.call_args_list
        if call[0][1] == "/olc/cmd/status"
    ]
    assert len(status_call) == 1
    assert "Syntax Error" in status_call[0][0][2]

    # 4. Empty or invalid args are safely ignored
    mock_engine.publish_osc.reset_mock()
    delegate._cmd("/olc/cmd", [])  # pylint: disable=protected-access
    delegate._cmd("/olc/cmd", [""])  # pylint: disable=protected-access
    delegate._cmd("/olc/cmd", [123])  # pylint: disable=protected-access
    mock_engine.publish_osc.assert_not_called()


# pylint: disable=protected-access
def test_osc_delegate_patch_dimmer() -> None:
    """Test /olc/patch/dimmer endpoint in OSCDelegate."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    delegate = OSCDelegate(app)

    # 1. Valid patch with 3 integer arguments
    mock_engine.publish_osc.reset_mock()
    delegate._patch_dimmer("/olc/patch/dimmer", [1, 1, 10])
    assert 1 in app.lightshow.patch.devices
    dev1 = app.lightshow.patch.devices[1]
    assert dev1.universe == 1
    assert dev1.address == 10
    mock_engine.publish_osc.assert_any_call(
        "patch",
        "/olc/patch/status",
        "OK",
        "/olc/patch/dimmer",
        "Device 1 patched to 1.10",
    )

    # 2. Valid patch with string format "universe.address"
    mock_engine.publish_osc.reset_mock()
    delegate._patch_dimmer("/olc/patch/dimmer", [2, "1.20"])
    assert 2 in app.lightshow.patch.devices
    dev2 = app.lightshow.patch.devices[2]
    assert dev2.universe == 1
    assert dev2.address == 20
    mock_engine.publish_osc.assert_any_call(
        "patch",
        "/olc/patch/status",
        "OK",
        "/olc/patch/dimmer",
        "Device 2 patched to 1.20",
    )

    # 3. Invalid string format
    mock_engine.publish_osc.reset_mock()
    delegate._patch_dimmer("/olc/patch/dimmer", [3, "not_a_valid_format"])
    assert 3 not in app.lightshow.patch.devices
    status_calls = [
        c
        for c in mock_engine.publish_osc.call_args_list
        if c[0][1] == "/olc/patch/status" and c[0][2] == "ERROR"
    ]
    assert len(status_calls) == 1

    # 4. Too few arguments
    mock_engine.publish_osc.reset_mock()
    delegate._patch_dimmer("/olc/patch/dimmer", [4])
    status_calls = [
        c
        for c in mock_engine.publish_osc.call_args_list
        if c[0][1] == "/olc/patch/status" and c[0][2] == "ERROR"
    ]
    assert len(status_calls) == 1

    # 5. Collision detection error
    mock_engine.publish_osc.reset_mock()
    delegate._patch_dimmer("/olc/patch/dimmer", [5, 1, 10])  # Collides with Device 1
    status_calls = [
        c
        for c in mock_engine.publish_osc.call_args_list
        if c[0][1] == "/olc/patch/status" and c[0][2] == "ERROR"
    ]
    assert len(status_calls) == 1

    # 6. Undo/Redo support
    app.history.undo()
    assert 2 not in app.lightshow.patch.devices
    app.history.redo()
    assert 2 in app.lightshow.patch.devices


def test_osc_delegate_patch_device() -> None:
    """Test /olc/patch/device endpoint in OSCDelegate."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    delegate = OSCDelegate(app)

    # 1. Valid fixture patch
    mock_engine.publish_osc.reset_mock()
    delegate._patch_device(
        "/olc/patch/device", [10, "Generic:RGBW", 1, 30, "Default", "LED 1"]
    )
    assert 10 in app.lightshow.patch.devices
    dev = app.lightshow.patch.devices[10]
    assert dev.universe == 1
    assert dev.address == 30
    assert dev.channel_count() == 4
    assert dev.label == "LED 1"
    mock_engine.publish_osc.assert_any_call(
        "patch",
        "/olc/patch/status",
        "OK",
        "/olc/patch/device",
        "Device 10 (Generic LED RGBW) patched to 1.30",
    )

    # 2. Unknown fixture definition
    mock_engine.publish_osc.reset_mock()
    delegate._patch_device("/olc/patch/device", [11, "NonExistent:Fixture", 1, 40])
    assert 11 not in app.lightshow.patch.devices
    status_calls = [
        c
        for c in mock_engine.publish_osc.call_args_list
        if c[0][1] == "/olc/patch/status" and c[0][2] == "ERROR"
    ]
    assert len(status_calls) == 1
    assert "not found in library" in status_calls[0][0][4]

    # 3. Insufficient arguments
    mock_engine.publish_osc.reset_mock()
    delegate._patch_device("/olc/patch/device", [12, "Generic:Dimmer"])
    status_calls = [
        c
        for c in mock_engine.publish_osc.call_args_list
        if c[0][1] == "/olc/patch/status" and c[0][2] == "ERROR"
    ]
    assert len(status_calls) == 1


def test_osc_delegate_patch_unpatch() -> None:
    """Test /olc/patch/unpatch endpoint in OSCDelegate."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    delegate = OSCDelegate(app)
    delegate._patch_dimmer("/olc/patch/dimmer", [1, 1, 10])
    assert 1 in app.lightshow.patch.devices

    # 1. Unpatch device 1
    mock_engine.publish_osc.reset_mock()
    delegate._patch_unpatch("/olc/patch/unpatch", [1])
    assert 1 not in app.lightshow.patch.devices
    mock_engine.publish_osc.assert_any_call(
        "patch", "/olc/patch/status", "OK", "/olc/patch/unpatch", "Device 1 unpatched"
    )

    # 2. Undo unpatch
    app.history.undo()
    assert 1 in app.lightshow.patch.devices

    # 3. Missing argument
    mock_engine.publish_osc.reset_mock()
    delegate._patch_unpatch("/olc/patch/unpatch", [])
    status_calls = [
        c
        for c in mock_engine.publish_osc.call_args_list
        if c[0][1] == "/olc/patch/status" and c[0][2] == "ERROR"
    ]
    assert len(status_calls) == 1


def test_osc_delegate_patch_1on1_and_clear() -> None:
    """Test /olc/patch/1on1 and /olc/patch/clear endpoints in OSCDelegate."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    delegate = OSCDelegate(app)

    # 1. Clear patch
    delegate._patch_clear("/olc/patch/clear", [])
    mock_engine.publish_osc.assert_any_call(
        "patch", "/olc/patch/status", "OK", "/olc/patch/clear", "Patch cleared"
    )
    assert len(app.lightshow.patch.devices) == 0

    # 2. Set 1:1 patch
    delegate._patch_1on1("/olc/patch/1on1", [])
    mock_engine.publish_osc.assert_any_call(
        "patch", "/olc/patch/status", "OK", "/olc/patch/1on1", "Patch reset to 1:1"
    )
    assert len(app.lightshow.patch.devices) > 0


def test_osc_delegate_patch_curve() -> None:
    """Test /olc/patch/curve endpoint in OSCDelegate."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    delegate = OSCDelegate(app)
    delegate._patch_dimmer("/olc/patch/dimmer", [1, 1, 10])

    # 1. Set curve
    mock_engine.publish_osc.reset_mock()
    delegate._patch_curve("/olc/patch/curve", [1, 2])
    assert app.lightshow.patch.devices[1].curve_id == 2
    mock_engine.publish_osc.assert_any_call(
        "patch",
        "/olc/patch/status",
        "OK",
        "/olc/patch/curve",
        "Device 1 curve set to 2",
    )

    # 2. Missing args
    mock_engine.publish_osc.reset_mock()
    delegate._patch_curve("/olc/patch/curve", [1])
    status_calls = [
        c
        for c in mock_engine.publish_osc.call_args_list
        if c[0][1] == "/olc/patch/status" and c[0][2] == "ERROR"
    ]
    assert len(status_calls) == 1


def test_osc_delegate_patch_get_and_dump() -> None:
    """Test /olc/patch/get and /olc/patch/dump query endpoints in OSCDelegate."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    delegate = OSCDelegate(app)
    delegate._patch_dimmer("/olc/patch/dimmer", [1, 1, 10])
    delegate._patch_device(
        "/olc/patch/device", [2, "Generic:RGBW", 1, 20, "Default", "Wash 1"]
    )

    # 1. Query patched device 1
    mock_engine.publish_osc.reset_mock()
    delegate._patch_get("/olc/patch/get", [1])
    mock_engine.publish_osc.assert_called_with(
        "patch", "/olc/patch/device/info", 1, 1, 10, 1, "Generic:Dimmer", "Dimmer 1"
    )

    # 2. Query patched device 2
    mock_engine.publish_osc.reset_mock()
    delegate._patch_get("/olc/patch/get", [2])
    mock_engine.publish_osc.assert_called_with(
        "patch", "/olc/patch/device/info", 2, 1, 20, 4, "Generic:LED RGBW", "Wash 1"
    )

    # 3. Query unpatched device 99
    mock_engine.publish_osc.reset_mock()
    delegate._patch_get("/olc/patch/get", [99])
    mock_engine.publish_osc.assert_called_with(
        "patch", "/olc/patch/device/info", 99, 0, 0, 0, "", ""
    )

    # 4. Dump patch as JSON
    mock_engine.publish_osc.reset_mock()
    delegate._patch_dump("/olc/patch/dump", [])
    assert mock_engine.publish_osc.called
    dump_call = [
        c
        for c in mock_engine.publish_osc.call_args_list
        if c[0][1] == "/olc/patch/dump"
    ]
    assert len(dump_call) == 1
    import json  # pylint: disable=import-outside-toplevel

    data = json.loads(dump_call[0][0][2])
    assert len(data) >= 2
    dev_ids = [d["device_id"] for d in data]
    assert 1 in dev_ids
    assert 2 in dev_ids


def test_osc_pubsub_subscribe_and_direct_dump() -> None:
    """Test /olc/subscribe registers subscriber, dumps patch, and notifies app."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    mock_sub_manager = MagicMock()
    mock_engine.osc_subscriptions = mock_sub_manager
    mock_sub_manager.get_subscribers_snapshot.return_value = [
        {
            "host": "192.168.1.44",
            "port": 8888,
            "topics": ["patch"],
            "last_seen": 100.0,
            "is_static": False,
        }
    ]
    app.engine = mock_engine

    delegate = OSCDelegate(app)
    delegate._patch_dimmer("/olc/patch/dimmer", [1, 1, 10])

    changed_events: list[list] = []
    app.subscribe("osc.subscribers_changed", changed_events.append)

    # Subscribe to "patch" on custom reply port 8888
    delegate._subscribe(
        "/olc/subscribe", ["patch", 8888], sender_addr=("192.168.1.44", 51234)
    )

    mock_sub_manager.subscribe.assert_called_once_with("192.168.1.44", 8888, "patch")
    mock_sub_manager.send_direct.assert_any_call(
        "192.168.1.44", 8888, "/olc/subscribe/status", "OK", "patch"
    )
    # Direct patch dump sent to client
    dump_calls = [
        c
        for c in mock_sub_manager.send_direct.call_args_list
        if c[0][2] == "/olc/patch/dump"
    ]
    assert len(dump_calls) == 1
    assert dump_calls[0][0][0] == "192.168.1.44"
    assert dump_calls[0][0][1] == 8888

    # Event emitted to application bus
    assert len(changed_events) == 1
    assert changed_events[0][0]["host"] == "192.168.1.44"


def test_osc_pubsub_unsubscribe() -> None:
    """Test /olc/unsubscribe removes subscriber and emits osc.subscribers_changed."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    mock_sub_manager = MagicMock()
    mock_engine.osc_subscriptions = mock_sub_manager
    mock_sub_manager.get_subscribers_snapshot.return_value = []
    app.engine = mock_engine

    delegate = OSCDelegate(app)
    changed_events: list[list] = []
    app.subscribe("osc.subscribers_changed", changed_events.append)

    delegate._unsubscribe(
        "/olc/unsubscribe", ["patch", 8888], sender_addr=("192.168.1.44", 51234)
    )

    mock_sub_manager.unsubscribe.assert_called_once_with("192.168.1.44", 8888, "patch")
    mock_sub_manager.send_direct.assert_called_once_with(
        "192.168.1.44", 8888, "/olc/subscribe/status", "OK", "unsubscribed"
    )
    assert len(changed_events) == 1


def test_osc_pubsub_ping_pong() -> None:
    """Test /olc/ping refreshes keepalive and replies with /olc/pong."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    mock_sub_manager = MagicMock()
    mock_engine.osc_subscriptions = mock_sub_manager
    app.engine = mock_engine

    delegate = OSCDelegate(app)
    delegate._ping("/olc/ping", [12345], sender_addr=("192.168.1.44", 8888))

    mock_sub_manager.refresh_keepalive.assert_called_once_with("192.168.1.44", 8888)
    mock_sub_manager.send_direct.assert_called_once_with(
        "192.168.1.44", 8888, "/olc/pong", 12345
    )


def test_osc_remove_subscriber_action() -> None:
    """Test osc.remove_subscriber action evicts subscriber and emits event."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    mock_sub_manager = MagicMock()
    mock_engine.osc_subscriptions = mock_sub_manager
    mock_sub_manager.get_subscribers_snapshot.return_value = []
    app.engine = mock_engine

    changed_events: list[list] = []
    app.subscribe("osc.subscribers_changed", changed_events.append)

    app.action_registry.execute("osc.remove_subscriber", "192.168.1.77", 9000)

    mock_sub_manager.unsubscribe.assert_called_once_with("192.168.1.77", 9000, "all")
    assert len(changed_events) == 1


def test_event_bridge_osc_subscribers_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GuiEventBridge routes osc.subscribers_changed to SettingsTab."""
    monkeypatch.setattr("gi.repository.GLib.idle_add", lambda func, *args: func(*args))
    mock_app = MagicMock()
    core = CoreApplication(MagicMock())
    mock_app.core = core

    mock_settings_tab = MagicMock()
    mock_app.tabs = MagicMock()
    mock_app.tabs.tabs = {"settings": mock_settings_tab}

    _bridge = GuiEventBridge(mock_app)

    sample_subs = [{"host": "192.168.1.99", "port": 8000, "topics": ["all"]}]
    core.emit("osc.subscribers_changed", sample_subs)
    mock_settings_tab.update_osc_subscribers.assert_called_once_with(sample_subs)


def test_settings_tab_update_osc_subscribers() -> None:
    """Test SettingsTab.update_osc_subscribers populates store and updates count."""
    tab = SettingsTab.__new__(SettingsTab)
    mock_store = MagicMock()
    mock_label = MagicMock()
    tab.liststore_osc_subscribers = mock_store
    tab.label_osc_subscribers_count = mock_label

    sample_subs = [
        {
            "host": "192.168.1.10",
            "port": 8000,
            "topics": ["patch"],
            "last_seen": 1000.0,
            "is_static": False,
        },
        {
            "host": "127.0.0.1",
            "port": 8000,
            "topics": ["all"],
            "last_seen": 1000.0,
            "is_static": True,
        },
    ]

    tab.update_osc_subscribers(sample_subs)

    mock_store.clear.assert_called_once()
    assert mock_store.append.call_count == 2
    args0 = mock_store.append.call_args_list[0][0][0]
    assert args0[0] == "192.168.1.10:8000"
    assert args0[1] == "patch"
    assert args0[3] == "192.168.1.10"
    assert args0[4] == 8000

    args1 = mock_store.append.call_args_list[1][0][0]
    assert args1[0] == "127.0.0.1:8000"
    assert "Static" in args1[1]

    mock_label.set_text.assert_called_once()
    assert "2" in mock_label.set_text.call_args[0][0]


def test_osc_toggle_static_client_action() -> None:
    """Test osc.toggle_static_client action and undo/redo."""
    settings = MagicMock()
    settings.get_boolean.return_value = False
    settings.get_string.return_value = "192.168.1.50"
    settings.get_int.return_value = 8500
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    mock_sub_manager = MagicMock()
    mock_engine.osc_subscriptions = mock_sub_manager
    app.engine = mock_engine

    toggled_events: list[bool] = []
    app.subscribe("osc.static_client_toggled", toggled_events.append)

    # 1. Enable static client
    app.action_registry.execute("osc.toggle_static_client", True)
    assert toggled_events == [True]
    mock_engine.set_static_client.assert_called_once_with(
        True, host="192.168.1.50", port=8500
    )

    # 2. Undo -> revert to False
    app.history.undo()
    assert toggled_events == [True, False]
    mock_engine.set_static_client.assert_called_with(
        False, host="192.168.1.50", port=8500
    )

    # 3. Redo -> re-enable
    app.history.redo()
    assert toggled_events == [True, False, True]


def test_core_engine_set_static_client() -> None:
    """Test CoreEngine.set_static_client subscribes or unsubscribes static client."""
    universe_map = UniverseMap()
    engine = CoreEngine(universe_map)
    engine.osc_client = MagicMock()
    engine.osc_client._addr = ("127.0.0.1", 8000)

    # Enable static client
    engine.set_static_client(True, "192.168.1.80", 8800)
    subs = engine.osc_subscriptions.get_subscribers_snapshot()
    assert len(subs) == 1
    assert subs[0]["host"] == "192.168.1.80"
    assert subs[0]["port"] == 8800
    assert subs[0]["is_static"] is True

    # Disable static client
    engine.set_static_client(False)
    subs2 = engine.osc_subscriptions.get_subscribers_snapshot()
    assert len(subs2) == 0


def test_event_bridge_osc_static_client_toggle_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test GuiEventBridge routes osc.static_client_toggled to SettingsTab."""
    monkeypatch.setattr("gi.repository.GLib.idle_add", lambda func, *args: func(*args))
    mock_app = MagicMock()
    core = CoreApplication(MagicMock())
    mock_app.core = core

    mock_settings_tab = MagicMock()
    mock_app.tabs = MagicMock()
    mock_app.tabs.tabs = {"settings": mock_settings_tab}

    _bridge = GuiEventBridge(mock_app)

    core.emit("osc.static_client_toggled", True)
    mock_settings_tab.update_osc_static_client_toggle.assert_called_once_with(True)


def test_settings_tab_update_osc_static_client_toggle() -> None:
    """Test SettingsTab.update_osc_static_client_toggle updates switch and inputs."""
    tab = SettingsTab.__new__(SettingsTab)
    tab._updating_settings = False
    mock_switch = MagicMock()
    mock_switch.get_state.return_value = False
    mock_entry = MagicMock()
    mock_spin = MagicMock()

    tab.switch_static_client = mock_switch
    tab.entry_client_ip = mock_entry
    tab.spin_client_port = mock_spin

    tab.update_osc_static_client_toggle(True)
    mock_switch.set_state.assert_called_once_with(True)
    mock_switch.set_active.assert_called_once_with(True)
    mock_entry.set_sensitive.assert_called_once_with(True)
    mock_spin.set_sensitive.assert_called_once_with(True)
    assert not tab._updating_settings


def test_osc_playback_subscribe_and_telemetry() -> None:
    """Test subscribing to 'playback' receives initial telemetry and dump."""
    from olc.cue import Cue
    from olc.step import Step

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    # Prepare some cues in main playback
    mp = app.lightshow.main_playback
    cue1 = Cue(sequence=1, number=1.0, text="Intro")
    step1 = Step(sequence=1.0, cue=cue1, text="Intro")
    cue2 = Cue(sequence=1, number=2.0, text="Chorus")
    step2 = Step(sequence=1.0, cue=cue2, text="Chorus")
    mp.steps.append(step1)
    mp.steps.append(step2)
    mp.position = 2

    delegate = OSCDelegate(app)
    mock_engine.osc_subscriptions.send_direct.reset_mock()

    delegate._subscribe("/olc/subscribe", ["playback", 8888], ("192.168.1.50", 8888))

    # Check status and telemetry sent to client
    direct_calls = mock_engine.osc_subscriptions.send_direct.call_args_list
    sent_paths = [c[0][2] for c in direct_calls]

    assert "/olc/subscribe/status" in sent_paths
    assert "/olc/playback/active/cue" in sent_paths
    assert "/olc/playback/active/text" in sent_paths
    assert "/olc/playback/next/cue" in sent_paths
    assert "/olc/playback/next/text" in sent_paths
    assert "/olc/playback/state" in sent_paths
    assert "/olc/blackout" in sent_paths
    assert "/olc/mainfader" in sent_paths
    assert "/olc/playback/dump" in sent_paths


def test_osc_playback_goto_cue_and_progress() -> None:
    """Test /olc/playback/goto_cue route and transition progress publishing."""
    from olc.cue import Cue
    from olc.sequence import get_cue
    from olc.step import Step

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    mp = app.lightshow.main_playback
    cue1 = Cue(sequence=1, number=1.0, text="Cue 1")
    step1 = Step(sequence=1.0, cue=cue1, text="Cue 1")
    cue2 = Cue(sequence=1, number=2.0, text="Cue 2")
    step2 = Step(sequence=1.0, cue=cue2, text="Cue 2")
    mp.steps.append(step1)
    mp.steps.append(step2)

    delegate = OSCDelegate(app)

    # 1. Goto cue 2 with override time 3.0s
    delegate._playback_goto_cue("/olc/playback/goto_cue", [2.0, 3.0])
    # Main playback positions to step preceding target, so next step is cue 2
    assert get_cue(mp.steps[mp.position + 1]).number == 2.0

    # 2. Progress event
    mock_engine.publish_osc.reset_mock()
    app.emit(
        "playback.transition_progress",
        {"total_time": 3000.0, "time_spent": 1500.0, "progress_val": 128},
    )
    mock_engine.publish_osc.assert_any_call("playback", "/olc/playback/progress", 0.5)

    # 3. Transition completed
    mock_engine.publish_osc.reset_mock()
    app.emit("playback.transition_completed", {"next_step": 2})
    # Emits 1.0, updates telemetry, then 0.0
    progress_calls = [
        c
        for c in mock_engine.publish_osc.call_args_list
        if c[0][1] == "/olc/playback/progress"
    ]
    assert len(progress_calls) == 2
    assert progress_calls[0][0][2] == 1.0
    assert progress_calls[1][0][2] == 0.0


def test_osc_playback_dump_and_cue_dump() -> None:
    """Test /olc/playback/dump and /olc/cue/dump routes returning JSON."""
    import json

    from olc.cue import Cue
    from olc.step import Step

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    mp = app.lightshow.main_playback
    cue1 = Cue(sequence=1, number=1.0, text="Scene 1")
    step1 = Step(sequence=1.0, cue=cue1, text="Scene 1", time_in=3.0, time_out=4.0)
    mp.steps.append(step1)

    delegate = OSCDelegate(app)
    mock_engine.osc_subscriptions.send_direct.reset_mock()
    mock_engine.publish_osc.reset_mock()

    delegate._playback_dump("/olc/cue/dump", [], sender_addr=("192.168.1.10", 9000))

    # Verify direct reply
    direct_calls = mock_engine.osc_subscriptions.send_direct.call_args_list
    assert len(direct_calls) == 1
    dump_str = direct_calls[0][0][3]
    dump_data = json.loads(dump_str)
    assert len(dump_data) >= 1
    assert any(c["cue"] == 1.0 and c["text"] == "Scene 1" for c in dump_data)


def test_osc_mainfader_and_blackout_routes() -> None:
    """Test /olc/mainfader and /olc/blackout execution and queries."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    delegate = OSCDelegate(app)

    # 1. Set mainfader via float 0.75
    mock_engine.publish_osc.reset_mock()
    delegate._mainfader("/olc/mainfader", [0.75])
    assert getattr(app, "main_fader_level", 0.0) == 0.75
    mock_engine.publish_osc.assert_any_call("playback", "/olc/mainfader", 0.75)

    # 2. Set mainfader via int 128 (normalized to 128/255)
    delegate._mainfader("/olc/mainfader", [128])
    assert abs(getattr(app, "main_fader_level", 0.0) - (128 / 255.0)) < 0.01

    # 3. Query mainfader without args
    mock_engine.osc_subscriptions.send_direct.reset_mock()
    delegate._mainfader("/olc/mainfader", [], sender_addr=("10.0.0.1", 5000))
    mock_engine.osc_subscriptions.send_direct.assert_called_once()
    assert mock_engine.osc_subscriptions.send_direct.call_args[0][2] == "/olc/mainfader"

    # 4. Trigger Blackout ON
    mock_engine.publish_osc.reset_mock()
    delegate._blackout("/olc/blackout", [1], sender_addr=("10.0.0.1", 5000))
    assert getattr(app, "blackout_active", False) is True
    mock_engine.publish_osc.assert_any_call("playback", "/olc/blackout", 1)

    # 5. Toggle Blackout OFF (no args)
    mock_engine.publish_osc.reset_mock()
    delegate._blackout("/olc/blackout", [], sender_addr=("10.0.0.1", 5000))
    assert getattr(app, "blackout_active", True) is False
    mock_engine.publish_osc.assert_any_call("playback", "/olc/blackout", 0)


def test_osc_playback_state_queries() -> None:
    """Test /olc/playback/active/cue, /next/cue, and /state direct queries."""
    from olc.cue import Cue
    from olc.step import Step

    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    app.engine = mock_engine

    mp = app.lightshow.main_playback
    cue1 = Cue(sequence=1, number=5.0, text="Dance")
    step1 = Step(sequence=1.0, cue=cue1, text="Dance")
    cue2 = Cue(sequence=1, number=6.0, text="Bow")
    step2 = Step(sequence=1.0, cue=cue2, text="Bow")
    mp.steps.append(step1)
    mp.steps.append(step2)
    mp.position = 2

    delegate = OSCDelegate(app)

    # Query active cue
    mock_engine.osc_subscriptions.send_direct.reset_mock()
    delegate._playback_query_active_cue(
        "/olc/playback/active/cue", [], sender_addr=("10.0.0.2", 8000)
    )
    mock_engine.osc_subscriptions.send_direct.assert_called_once_with(
        "10.0.0.2", 8000, "/olc/playback/active/cue", 5.0
    )

    # Query next cue
    mock_engine.osc_subscriptions.send_direct.reset_mock()
    delegate._playback_query_next_cue(
        "/olc/playback/next/cue", [], sender_addr=("10.0.0.2", 8000)
    )
    mock_engine.osc_subscriptions.send_direct.assert_called_once_with(
        "10.0.0.2", 8000, "/olc/playback/next/cue", 6.0
    )

    # Query state
    mock_engine.osc_subscriptions.send_direct.reset_mock()
    delegate._playback_query_state(
        "/olc/playback/state", [], sender_addr=("10.0.0.2", 8000)
    )
    mock_engine.osc_subscriptions.send_direct.assert_called_once_with(
        "10.0.0.2", 8000, "/olc/playback/state", "idle"
    )


def test_osc_normalized_routes_and_polymorphism() -> None:
    """Test normalized float inputs and legacy DMX conversions across routes."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_backend.dmx = MagicMock()
    mock_backend.dmx.levels = {"user": [-1] * 1024, "sequence": [0] * 1024}
    mock_backend.dmx.blackout = False
    app.backend = mock_backend

    mock_engine = MagicMock()
    app.engine = mock_engine
    delegate = OSCDelegate(app)

    # 1. Main fader normalized float
    delegate._mainfader("/olc/mainfader", [0.75])
    action = app.action_registry.get("main_fader.set_level")
    assert action.get_feedback_state()["level"] == 0.75

    # 2. Main fader legacy DMX scale
    delegate._mainfader("/olc/mainfader", [128])
    action = app.action_registry.get("main_fader.set_level")
    assert pytest.approx(action.get_feedback_state()["level"]) == 128 / 255.0

    # 3. Channel level normalized float
    delegate._channel_level("/olc/channel/3/level", [0.8])
    action = app.action_registry.get("channel.set_level")
    assert action.get_feedback_state()["normalized_level"] == 0.8
    assert mock_backend.dmx.levels["user"][2] == round(0.8 * 255.0)

    # 4. Channel level legacy DMX int
    delegate._channel_level("/olc/channel/3/level", [200])
    action = app.action_registry.get("channel.set_level")
    assert action.get_feedback_state()["level"] == 200

    # 5. Blackout bool / string
    delegate._blackout("/olc/blackout", ["true"])
    action = app.action_registry.get("dmx.blackout_all")
    assert action.get_feedback_state()["blackout"] is True

    # 6. Fader flash bool / int
    delegate._fader_flash("/olc/fader/1/1/flash", [1])
    action = app.action_registry.get("fader.flash")
    assert action.get_feedback_state()["active"] is True


def test_osc_key_enter_and_backspace() -> None:
    """Test /olc/key/enter and /olc/key/backspace routes."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_backend.dmx = MagicMock()
    mock_backend.dmx.levels = {"user": [-1] * 1024, "sequence": [0] * 1024}
    app.backend = mock_backend

    delegate = OSCDelegate(app)

    # 1. Backspace route
    app.commandline.set_string("123")
    delegate._backspace("/olc/key/backspace", [1])
    assert app.commandline.get_string() == "12"

    # 2. Enter route executing command
    app.commandline.set_string("1 at 50")
    delegate._enter("/olc/key/enter", [1])
    # Channel 1 selected and level 50 applied (or command executed)
    assert app.commandline.get_string() == ""
    assert mock_backend.dmx.levels["user"][0] == 128


def test_osc_keypad_sentence_building() -> None:
    """Test typing full sentence via keypad (1 -> AT -> 50 -> ENTER)."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_backend = MagicMock()
    mock_backend.dmx = MagicMock()
    mock_backend.dmx.levels = {"user": [-1] * 1024, "sequence": [0] * 1024}
    app.backend = mock_backend

    delegate = OSCDelegate(app)

    # Type "1 AT 50"
    delegate._1("/olc/key/1", [1])
    assert app.commandline.get_string() == "1"

    delegate._level("/olc/key/at", [1])
    assert app.commandline.get_string() == "1 AT "

    delegate._5("/olc/key/5", [1])
    delegate._0("/olc/key/0", [1])
    assert app.commandline.get_string() == "1 AT 50"

    delegate._enter("/olc/key/enter", [1])
    assert app.commandline.get_string() == ""
    assert mock_backend.dmx.levels["user"][0] == 128

    # Test THRU and FULL: "1 THRU 3 AT FULL"
    delegate._1("/olc/key/1", [1])
    delegate._thru("/olc/key/thru", [1])
    assert app.commandline.get_string() == "1 THRU "
    delegate._3("/olc/key/3", [1])
    delegate._full("/olc/key/full", [1])
    assert app.commandline.get_string() == "1 THRU 3 AT FULL"
    delegate._enter("/olc/key/enter", [1])
    assert mock_backend.dmx.levels["user"][0] == 255
    assert mock_backend.dmx.levels["user"][1] == 255
    assert mock_backend.dmx.levels["user"][2] == 255


def test_osc_fader_flash_feedback() -> None:
    """Test that fader flash changes publish feedback to /olc/fader/1/{id}/flash."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    app.engine = mock_engine
    delegate = OSCDelegate(app)

    # Trigger flash on fader 1
    delegate._fader_flash("/olc/fader/1/1/flash", [1])
    mock_engine.publish_osc.assert_any_call("faders", "/olc/fader/1/1/flash", 1)

    # Release flash on fader 1
    delegate._fader_flash("/olc/fader/1/1/flash", [0])
    mock_engine.publish_osc.assert_any_call("faders", "/olc/fader/1/1/flash", 0)


def test_osc_selected_pan_tilt_norm_feedback() -> None:
    """Test that moving fixture telemetry publishes both degrees and normalized."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    app.engine = mock_engine
    _delegate = OSCDelegate(app)

    # Patch moving head fixture on channel 1
    from olc.devices.builtin import create_moving_head_definition

    app.lightshow.patch.patch_device(1, create_moving_head_definition(), 1, 1)

    # Select fixture 1 and trigger parameter update (center = 0.5 normalized)
    app.selected_channels = [1]
    app.action_registry.execute("device.set_pan_tilt", 0.0, 0.0)

    calls = [call[0] for call in mock_engine.publish_osc.call_args_list]
    # Check that both degrees and norm were published
    published_topics_addrs = [(c[0], c[1]) for c in calls if len(c) >= 2]
    assert ("channels", "/olc/selected/pan") in published_topics_addrs
    assert ("channels", "/olc/selected/pan/norm") in published_topics_addrs
    assert ("channels", "/olc/selected/tilt") in published_topics_addrs
    assert ("channels", "/olc/selected/tilt/norm") in published_topics_addrs


def test_osc_manual_xfade_control_and_feedback() -> None:
    """Test manual crossfade control routes and OSC position feedback."""
    settings = MagicMock()
    app = CoreApplication(settings)

    mock_engine = MagicMock()
    app.engine = mock_engine
    delegate = OSCDelegate(app)

    # 1. Move Scale A to 0.7
    delegate._playback_xfade_a("/olc/playback/xfade/a", [0.7])
    assert app.crossfade is not None
    assert pytest.approx(app.crossfade.scale_a.get_value(), 0.01) == 0.7
    mock_engine.publish_osc.assert_any_call(
        "playback", "/olc/playback/xfade/a", pytest.approx(0.7, 0.01)
    )

    # 2. Move Scale B to 0.4
    delegate._playback_xfade_b("/olc/playback/xfade/b", [0.4])
    assert pytest.approx(app.crossfade.scale_b.get_value(), 0.01) == 0.4
    mock_engine.publish_osc.assert_any_call(
        "playback", "/olc/playback/xfade/b", pytest.approx(0.4, 0.01)
    )

    # 3. Unified crossfade route
    delegate._playback_xfade("/olc/playback/xfade", [0.5])
    assert pytest.approx(app.crossfade.scale_a.get_value(), 0.01) == 0.5
    assert pytest.approx(app.crossfade.scale_b.get_value(), 0.01) == 0.5


def test_osc_device_home_and_locate() -> None:
    """Test /olc/selected/home, /olc/selected/locate, and /olc/device/{id}/home."""
    from olc.devices.builtin import create_moving_head_definition

    settings = MagicMock()
    app = CoreApplication(settings)
    delegate = OSCDelegate(app)

    app.lightshow.patch.patch_device(1, create_moving_head_definition(), 1, 1)
    dev = app.lightshow.patch.devices[1]

    # Alter fixture
    dev.set_intensity(0.5)
    dev.set_position_degrees(50.0, 30.0)
    app.selected_channels = [1]

    # 1. /olc/selected/home
    delegate._selected_home("/olc/selected/home", [1.0])
    assert dev.intensity == 0.5
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.1)

    # 2. /olc/selected/locate
    dev.set_intensity(0.0)
    delegate._selected_locate("/olc/selected/locate", [1.0])
    assert dev.intensity == 1.0

    # 3. /olc/device/1/home
    dev.set_position_degrees(-40.0, -20.0)
    delegate._device_home("/olc/device/1/home", [1.0])
    assert dev.pan_degrees == pytest.approx(0.0, abs=0.1)
