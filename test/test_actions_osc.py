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

from olc.core.app import CoreApplication
from olc.core.backends.osc.delegate import OSCDelegate
from olc.core.osc import EngineOSCServer


def test_osc_toggle_enable_and_disable() -> None:
    """Test osc.toggle action to enable and disable OSC services."""
    settings = MagicMock()
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

    # Verify not undoable
    assert len(app.history.undo_stack) == 0

    # 2. Disable OSC
    app.action_registry.execute("osc.toggle", False)
    assert toggled_events == [True, False]
    mock_engine.stop_osc.assert_called_once()
    assert getattr(app, "osc_delegate", None) is None


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
