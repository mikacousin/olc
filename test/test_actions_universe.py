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
"""Unit tests for universe configuration actions and Undo/Redo."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from olc.core.app import CoreApplication
from olc.core.universe_config import Protocol, UniverseMap
from olc.gtk3.event_bridge import GuiEventBridge
from olc.settings import SettingsTab


def _create_app_with_universe_map() -> tuple[CoreApplication, MagicMock]:
    """Helper to instantiate CoreApplication with a mock engine holding UniverseMap."""
    settings = MagicMock()
    app = CoreApplication(settings)
    mock_engine = MagicMock()
    mock_engine.universe_map = UniverseMap(8)
    app.engine = mock_engine
    return app, mock_engine


def test_universe_set_protocol_artnet() -> None:
    """Test universe.set_protocol action for Art-Net with Undo and Redo."""
    app, mock_engine = _create_app_with_universe_map()

    events: list[tuple[int, str, bool]] = []

    def on_protocol_changed(universe: int, proto: str, enabled: bool) -> None:
        events.append((universe, proto, enabled))

    app.subscribe("universe.protocol_changed", on_protocol_changed)

    # Initially universe 1 has no protocols
    u1 = mock_engine.universe_map[1]
    assert Protocol.ARTNET not in u1.protocols

    # Enable Art-Net via string
    app.action_registry.execute("universe.set_protocol", 1, "ARTNET", True)
    assert Protocol.ARTNET in u1.protocols
    mock_engine.reload_universe.assert_called_with(1)
    assert app.lightshow.modified is True
    assert events == [(1, "ARTNET", True)]

    # Undo
    app.history.undo()
    assert Protocol.ARTNET not in u1.protocols
    assert events[-1] == (1, "ARTNET", False)

    # Redo
    app.history.redo()
    assert Protocol.ARTNET in u1.protocols
    assert events[-1] == (1, "ARTNET", True)


def test_universe_set_protocol_sacn_and_dmx_usb() -> None:
    """Test universe.set_protocol action with Protocol objects and disabling."""
    app, mock_engine = _create_app_with_universe_map()
    u2 = mock_engine.universe_map[2]

    # Enable sACN and DMX USB Pro
    app.action_registry.execute("universe.set_protocol", 2, Protocol.SACN, True)
    app.action_registry.execute("universe.set_protocol", 2, Protocol.DMX_USB_PRO, True)
    assert Protocol.SACN in u2.protocols
    assert Protocol.DMX_USB_PRO in u2.protocols

    # Disable sACN
    app.action_registry.execute("universe.set_protocol", 2, Protocol.SACN, False)
    assert Protocol.SACN not in u2.protocols
    assert Protocol.DMX_USB_PRO in u2.protocols

    # Undo disable -> sACN re-enabled
    app.history.undo()
    assert Protocol.SACN in u2.protocols


def test_universe_set_protocol_invalid() -> None:
    """Test universe.set_protocol error handling for invalid universe or protocol."""
    app, _ = _create_app_with_universe_map()

    # Universe not found
    with pytest.raises(ValueError, match="Universe 999 not found"):
        app.action_registry.execute("universe.set_protocol", 999, "ARTNET", True)

    # Unknown protocol string
    with pytest.raises(ValueError, match="Unknown universe protocol"):
        app.action_registry.execute("universe.set_protocol", 1, "UNKNOWN_PROTO", True)

    # sACN forbidden on universe 0
    with pytest.raises(ValueError, match="not allowed on universe 0"):
        app.action_registry.execute("universe.set_protocol", 0, Protocol.SACN, True)


def test_universe_set_config_artnet() -> None:
    """Test universe.set_config action for Art-Net parameters with Undo/Redo."""
    app, mock_engine = _create_app_with_universe_map()
    u1 = mock_engine.universe_map[1]

    assert u1.artnet.net == 0
    assert u1.artnet.sub == 0
    assert u1.artnet.sync_active is False

    events: list[tuple[int, dict]] = []

    def on_config_changed(universe: int, changed: dict) -> None:
        events.append((universe, changed))

    app.subscribe("universe.config_changed", on_config_changed)

    # Set Art-Net net, sub and sync_active
    app.action_registry.execute(
        "universe.set_config",
        1,
        artnet_net=2,
        artnet_sub=5,
        artnet_sync_active=True,
    )

    assert u1.artnet.net == 2
    assert u1.artnet.sub == 5
    assert u1.artnet.sync_active is True
    assert mock_engine.reload_universe.called
    assert events == [
        (
            1,
            {
                "artnet_net": 2,
                "artnet_sub": 5,
                "artnet_sync_active": True,
            },
        )
    ]

    # Undo
    app.history.undo()
    assert u1.artnet.net == 0
    assert u1.artnet.sub == 0
    assert u1.artnet.sync_active is False

    # Redo
    app.history.redo()
    assert u1.artnet.net == 2
    assert u1.artnet.sub == 5
    assert u1.artnet.sync_active is True


def test_universe_set_config_sacn_and_dmx_usb_pro() -> None:
    """Test universe.set_config action for sACN and DMX USB Pro parameters."""
    app, mock_engine = _create_app_with_universe_map()
    u2 = mock_engine.universe_map[2]

    app.action_registry.execute(
        "universe.set_config",
        2,
        sacn_priority=150,
        sacn_sync_address=10,
        dmx_usb_pro_port="/dev/ttyUSB0",
        dmx_usb_pro_port_index=2,
        dmx_usb_pro_model="Pro Mk2",
        protocols={Protocol.ARTNET, Protocol.SACN},
    )

    assert u2.sacn.priority == 150
    assert u2.sacn.sync_address == 10
    assert u2.dmx_usb_pro.port == "/dev/ttyUSB0"
    assert u2.dmx_usb_pro.port_index == 2
    assert u2.dmx_usb_pro.model == "Pro Mk2"
    assert u2.protocols == frozenset({Protocol.ARTNET, Protocol.SACN})

    # Undo restores initial values
    app.history.undo()
    assert u2.sacn.priority == 100
    assert u2.sacn.sync_address == 0
    assert u2.dmx_usb_pro.port == "Auto-detect"
    assert u2.dmx_usb_pro.port_index == 1
    assert u2.dmx_usb_pro.model == "Auto-detect"
    assert u2.protocols == frozenset()

    # Redo
    app.history.redo()
    assert u2.sacn.priority == 150
    assert u2.sacn.sync_address == 10
    assert u2.dmx_usb_pro.port == "/dev/ttyUSB0"
    assert u2.dmx_usb_pro.port_index == 2
    assert u2.dmx_usb_pro.model == "Pro Mk2"
    assert u2.protocols == frozenset({Protocol.ARTNET, Protocol.SACN})


def test_universe_set_config_invalid_universe() -> None:
    """Test universe.set_config error when universe is not in universe_map."""
    app, _ = _create_app_with_universe_map()

    with pytest.raises(ValueError, match="Universe 999 not found"):
        app.action_registry.execute("universe.set_config", 999, artnet_net=1)


def test_event_bridge_universe_settings_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test GuiEventBridge routes universe events to SettingsTab."""
    monkeypatch.setattr("gi.repository.GLib.idle_add", lambda func, *args: func(*args))
    mock_app = MagicMock()
    core = CoreApplication(MagicMock())
    mock_app.core = core

    mock_settings_tab = MagicMock()
    mock_app.tabs = MagicMock()
    mock_app.tabs.tabs = {"settings": mock_settings_tab}

    _bridge = GuiEventBridge(mock_app)

    # 1. Trigger universe.protocol_changed
    core.emit("universe.protocol_changed", 1, "ARTNET", True)
    mock_settings_tab.update_universe_ui.assert_called_once_with(1)

    # 2. Trigger universe.config_changed
    mock_settings_tab.update_universe_ui.reset_mock()
    core.emit("universe.config_changed", 2, {"artnet_net": 1})
    mock_settings_tab.update_universe_ui.assert_called_once_with(2)


def test_settings_tab_update_universe_ui() -> None:
    """Test SettingsTab.update_universe_ui refreshes widget states."""
    # pylint: disable=protected-access
    tab = SettingsTab.__new__(SettingsTab)
    tab._updating_settings = False

    mock_engine = MagicMock()
    mock_engine.universe_map = UniverseMap(8)
    u1 = mock_engine.universe_map[1]
    u1.enable(Protocol.ARTNET)
    u1.artnet.net = 3
    u1.artnet.sub = 7
    u1.artnet.sync_active = True

    tab.app = MagicMock()
    tab.app.engine = mock_engine

    widgets = {
        "artnet_check": MagicMock(),
        "net_spin": MagicMock(),
        "sub_spin": MagicMock(),
        "sync_switch": MagicMock(),
        "sacn_check": MagicMock(),
        "prio_spin": MagicMock(),
        "sacn_sync_spin": MagicMock(),
        "dmx_usb_pro_check": MagicMock(),
        "port_combo": MagicMock(),
        "port_index_combo": MagicMock(),
        "model_combo": MagicMock(),
    }
    widgets["port_combo"].get_model.return_value = None
    tab.universe_widgets = {1: widgets}

    tab.update_universe_ui(1)

    widgets["artnet_check"].set_active.assert_called_once_with(True)
    widgets["net_spin"].set_value.assert_called_once_with(3)
    widgets["sub_spin"].set_value.assert_called_once_with(7)
    widgets["sync_switch"].set_active.assert_called_once_with(True)
    widgets["sacn_check"].set_active.assert_called_once_with(False)
    assert not tab._updating_settings
