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
"""Actions for real-time DMX and Universe level manipulation."""

from __future__ import annotations

import typing

import numpy as np
from olc.core.action import Action
from olc.core.universe_config import Protocol, UniverseConfig
from olc.define import UNIVERSES

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class UniverseBlackoutAction(Action):
    """Action to blackout a specific DMX universe."""

    name = "universe.blackout"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.universe: int = 1
        self.old_frame: typing.Optional[np.ndarray] = None

    def configure(self, universe: int) -> None:
        """Configure the action with the universe to blackout.

        Args:
            universe: The DMX universe identifier.
        """
        self.universe = universe

    def execute(self) -> None:
        """Execute blackout on the configured universe."""
        self.old_frame = None

        if self.app.engine is not None:
            try:
                univ = self.app.engine.universe(self.universe)
                self.old_frame = univ.snapshot()
                univ.blackout()
            except KeyError:
                pass

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            if self.universe in UNIVERSES:
                idx = UNIVERSES.index(self.universe)
                if self.old_frame is None:
                    self.old_frame = backend.dmx.frame[idx].copy()
                backend.dmx.frame[idx].fill(0)

        self.app.emit("universe.blackout_changed", self.universe)

    def undo(self) -> None:
        """Restore universe channel levels prior to blackout."""
        if self.old_frame is not None:
            if self.app.engine is not None:
                try:
                    self.app.engine.universe(self.universe).apply_array(self.old_frame)
                except KeyError:
                    pass
            backend = getattr(self.app, "backend", None)
            if backend is not None and getattr(backend, "dmx", None) is not None:
                if self.universe in UNIVERSES:
                    idx = UNIVERSES.index(self.universe)
                    np.copyto(backend.dmx.frame[idx], self.old_frame)
        self.app.emit("universe.blackout_changed", self.universe)

    def redo(self) -> None:
        """Re-apply blackout on the configured universe."""
        if self.app.engine is not None:
            try:
                self.app.engine.universe(self.universe).blackout()
            except KeyError:
                pass
        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            if self.universe in UNIVERSES:
                idx = UNIVERSES.index(self.universe)
                backend.dmx.frame[idx].fill(0)
        self.app.emit("universe.blackout_changed", self.universe)


class DmxSetUniverseLevelsAction(Action):
    """Action to set specific channel levels on a universe."""

    name = "dmx.set_universe_levels"
    can_undo = False

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.universe: int = 1
        self.channels: dict[int, int] = {}

    def configure(self, universe: int, channels: dict[int, int]) -> None:
        """Configure the action with target universe and channel levels.

        Args:
            universe: The DMX universe identifier.
            channels: Dictionary mapping channel index to DMX level (0-255).
        """
        self.universe = universe
        self.channels = dict(channels)

    def execute(self) -> None:
        """Apply channel levels to the target universe."""
        if self.app.engine is not None:
            try:
                self.app.engine.set_channels(self.universe, self.channels)
            except KeyError:
                pass

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            if self.universe in UNIVERSES:
                idx = UNIVERSES.index(self.universe)
                frame = backend.dmx.frame[idx]
                for ch, val in self.channels.items():
                    if 0 <= ch < 512:
                        frame[ch] = int(np.clip(val, 0, 255))

        self.app.emit("universe.dmx_changed", self.universe, self.channels)


class DmxTestOutputAction(Action):
    """Action to set a test level on DMX output(s)."""

    name = "dmx.test_output"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.targets: list[tuple[int, int]] = []
        self.level: int = 255
        self.old_levels: dict[tuple[int, int], int] = {}

    def configure(
        self,
        output: int | list[tuple[int, int]],
        universe: int = 1,
        level: int = 255,
    ) -> None:
        """Configure the action with target output(s) and test level.

        Args:
            output: Single output (1-512) or list of (output, universe) tuples.
            universe: DMX universe identifier if output is an integer.
            level: Level to apply (0-255).
        """
        if isinstance(output, list):
            self.targets = list(output)
            self.level = level if level != 255 else (universe if universe != 1 else 255)
        else:
            self.targets = [(output, universe)]
            self.level = level

    def execute(self) -> None:
        """Apply test level to configured outputs."""
        backend = getattr(self.app, "backend", None)
        self.old_levels = {}
        for out, univ in self.targets:
            old = 0
            if backend is not None and getattr(backend, "dmx", None) is not None:
                old = backend.dmx.user_outputs.get((out, univ), 0)
                backend.dmx.send_user_output(out, univ, self.level)
            elif self.app.engine is not None:
                try:
                    old = int(self.app.engine.universe(univ).array[out - 1])
                    self.app.engine.universe(univ).array[out - 1] = self.level
                except (KeyError, IndexError, AttributeError):
                    pass
            self.old_levels[(out, univ)] = old
            self.app.emit("dmx.user_output_changed", univ, out, self.level)

    def undo(self) -> None:
        """Restore previous output levels prior to test."""
        backend = getattr(self.app, "backend", None)
        for (out, univ), old in self.old_levels.items():
            if backend is not None and getattr(backend, "dmx", None) is not None:
                backend.dmx.send_user_output(out, univ, old)
            elif self.app.engine is not None:
                try:
                    self.app.engine.universe(univ).array[out - 1] = old
                except (KeyError, IndexError, AttributeError):
                    pass
            self.app.emit("dmx.user_output_changed", univ, out, old)

    def redo(self) -> None:
        """Re-apply test level to target outputs."""
        backend = getattr(self.app, "backend", None)
        for out, univ in self.targets:
            if backend is not None and getattr(backend, "dmx", None) is not None:
                backend.dmx.send_user_output(out, univ, self.level)
            elif self.app.engine is not None:
                try:
                    self.app.engine.universe(univ).array[out - 1] = self.level
                except (KeyError, IndexError, AttributeError):
                    pass
            self.app.emit("dmx.user_output_changed", univ, out, self.level)


class DmxClearUserOutputsAction(Action):
    """Action to clear all active test/user output overrides."""

    name = "dmx.clear_user_outputs"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_user_outputs: dict[tuple[int, int], int] = {}

    def execute(self) -> None:
        """Clear all active user outputs, setting them back to 0."""
        backend = getattr(self.app, "backend", None)
        self.old_user_outputs = {}
        if backend is not None and getattr(backend, "dmx", None) is not None:
            self.old_user_outputs = dict(backend.dmx.user_outputs)
            for out, univ in list(self.old_user_outputs.keys()):
                backend.dmx.send_user_output(out, univ, 0)
            backend.dmx.user_outputs.clear()
        self.app.emit("dmx.user_outputs_cleared")

    def undo(self) -> None:
        """Restore previous user output levels prior to clear."""
        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            for (out, univ), lvl in self.old_user_outputs.items():
                backend.dmx.send_user_output(out, univ, lvl)
                self.app.emit("dmx.user_output_changed", univ, out, lvl)
        self.app.emit("dmx.user_outputs_changed")

    def redo(self) -> None:
        """Re-apply clear on user outputs."""
        self.execute()


class DmxBlackoutAllAction(Action):
    """Action to blackout all DMX universes simultaneously."""

    name = "dmx.blackout_all"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_frames: dict[int, np.ndarray] = {}

    def execute(self) -> None:
        """Execute blackout on all universes."""
        self.old_frames = {}

        for universe in UNIVERSES:
            if self.app.engine is not None:
                try:
                    univ = self.app.engine.universe(universe)
                    self.old_frames[universe] = univ.snapshot()
                    univ.blackout()
                except KeyError:
                    pass

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            for idx, universe in enumerate(UNIVERSES):
                if universe not in self.old_frames:
                    self.old_frames[universe] = backend.dmx.frame[idx].copy()
                backend.dmx.frame[idx].fill(0)

        self.app.emit("dmx.blackout_all_changed", True)

    def undo(self) -> None:
        """Restore all universes prior to blackout."""
        for universe, old_frame in self.old_frames.items():
            if self.app.engine is not None:
                try:
                    self.app.engine.universe(universe).apply_array(old_frame)
                except KeyError:
                    pass
            backend = getattr(self.app, "backend", None)
            if backend is not None and getattr(backend, "dmx", None) is not None:
                if universe in UNIVERSES:
                    idx = UNIVERSES.index(universe)
                    np.copyto(backend.dmx.frame[idx], old_frame)

        self.app.emit("dmx.blackout_all_changed", False)

    def redo(self) -> None:
        """Re-apply blackout on all universes."""
        for universe in UNIVERSES:
            if self.app.engine is not None:
                try:
                    self.app.engine.universe(universe).blackout()
                except KeyError:
                    pass
        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            for idx in range(len(UNIVERSES)):
                backend.dmx.frame[idx].fill(0)

        self.app.emit("dmx.blackout_all_changed", True)


def _normalize_protocol(protocol: str | Protocol | object) -> Protocol:
    """Normalize string or Protocol value to Protocol member.

    Args:
        protocol: Protocol value or string name.

    Returns:
        Corresponding Protocol member.
    """
    if isinstance(protocol, Protocol):
        return protocol
    if isinstance(protocol, str):
        proto_upper = protocol.strip().upper()
        if proto_upper in ("ARTNET", "ART_NET", "ART-NET"):
            return Protocol.ARTNET
        if proto_upper in ("SACN", "S_ACN", "E1.31"):
            return Protocol.SACN
        if proto_upper in ("DMX_USB_PRO", "DMXUSBPRO", "ENTTEC"):
            return Protocol.DMX_USB_PRO
    raise ValueError(f"Unknown universe protocol: {protocol}")


class UniverseSetProtocolAction(Action):
    """Action to enable or disable an output protocol on a universe."""

    name = "universe.set_protocol"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.universe: int = 1
        self.protocol: Protocol = Protocol.ARTNET
        self.enabled: bool = True
        self.old_enabled: bool = False

    def configure(
        self, universe: int, protocol: str | Protocol, enabled: bool = True
    ) -> None:
        """Configure the action with target universe, protocol, and state.

        Args:
            universe: Non-negative universe number.
            protocol: Protocol name or Protocol value.
            enabled: True to enable protocol, False to disable.
        """
        self.universe = universe
        self.protocol = _normalize_protocol(protocol)
        self.enabled = enabled

    def execute(self) -> None:
        """Enable or disable the protocol on the universe."""
        engine = getattr(self.app, "engine", None)
        if engine is None:
            raise RuntimeError("Engine is not available")

        if self.universe not in engine.universe_map:
            raise ValueError(f"Universe {self.universe} not found")

        config = engine.universe_map[self.universe]
        self.old_enabled = self.protocol in config.protocols

        if self.enabled:
            config.enable(self.protocol)
        else:
            config.disable(self.protocol)

        engine.reload_universe(self.universe)
        if hasattr(self.app, "lightshow") and self.app.lightshow is not None:
            self.app.lightshow.set_modified()

        self.app.emit(
            "universe.protocol_changed",
            self.universe,
            self.protocol.name,
            self.enabled,
        )

    def undo(self) -> None:
        """Restore previous protocol enable/disable state."""
        engine = getattr(self.app, "engine", None)
        if engine is None or self.universe not in engine.universe_map:
            return

        config = engine.universe_map[self.universe]
        if self.old_enabled:
            config.enable(self.protocol)
        else:
            config.disable(self.protocol)

        engine.reload_universe(self.universe)
        if hasattr(self.app, "lightshow") and self.app.lightshow is not None:
            self.app.lightshow.set_modified()

        self.app.emit(
            "universe.protocol_changed",
            self.universe,
            self.protocol.name,
            self.old_enabled,
        )

    def redo(self) -> None:
        """Re-apply protocol enable/disable state."""
        self.execute()


class UniverseSetConfigAction(Action):
    """Action to update parameters of a universe with Undo/Redo."""

    name = "universe.set_config"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.universe: int = 1
        self.settings: dict[str, typing.Any] = {}
        self.old_settings: dict[str, typing.Any] = {}

    def configure(
        self,
        universe: int,
        settings: dict[str, typing.Any] | None = None,
        **kwargs: object,
    ) -> None:
        """Configure the action with target universe and settings dictionary.

        Args:
            universe: Non-negative universe identifier.
            settings: Dictionary of configuration parameters.
            **kwargs: Extra parameters passed as keyword arguments.
        """
        self.universe = universe
        combined = dict(settings or {})
        combined.update(kwargs)
        self.settings = combined

    def execute(self) -> None:
        """Apply configured parameters to the universe."""
        engine = getattr(self.app, "engine", None)
        if engine is None:
            raise RuntimeError("Engine is not available")

        if self.universe not in engine.universe_map:
            raise ValueError(f"Universe {self.universe} not found")

        config = engine.universe_map[self.universe]
        self.old_settings = {}
        self._apply_dict(config, self.settings, self.old_settings)

        engine.reload_universe(self.universe)
        if hasattr(self.app, "lightshow") and self.app.lightshow is not None:
            self.app.lightshow.set_modified()

        self.app.emit("universe.config_changed", self.universe, dict(self.settings))

    def undo(self) -> None:
        """Restore previous configuration parameters."""
        engine = getattr(self.app, "engine", None)
        if engine is None or self.universe not in engine.universe_map:
            return

        config = engine.universe_map[self.universe]
        self._apply_dict(config, self.old_settings, {})

        engine.reload_universe(self.universe)
        if hasattr(self.app, "lightshow") and self.app.lightshow is not None:
            self.app.lightshow.set_modified()

        self.app.emit("universe.config_changed", self.universe, dict(self.old_settings))

    def redo(self) -> None:
        """Re-apply configuration parameters."""
        self.execute()

    @staticmethod
    def _apply_dict(
        config: UniverseConfig,
        source: dict[str, typing.Any],
        target_old: dict[str, typing.Any],
    ) -> None:
        """Helper to apply settings dictionary and record previous values."""
        if "artnet_net" in source:
            target_old["artnet_net"] = config.artnet.net
            config.artnet.net = int(source["artnet_net"])
        if "artnet_sub" in source:
            target_old["artnet_sub"] = config.artnet.sub
            config.artnet.sub = int(source["artnet_sub"])
        if "artnet_sync_active" in source:
            target_old["artnet_sync_active"] = config.artnet.sync_active
            config.artnet.sync_active = bool(source["artnet_sync_active"])

        if "sacn_priority" in source:
            target_old["sacn_priority"] = config.sacn.priority
            config.sacn.priority = int(source["sacn_priority"])
        if "sacn_sync_address" in source:
            target_old["sacn_sync_address"] = config.sacn.sync_address
            config.sacn.sync_address = int(source["sacn_sync_address"])

        if "dmx_usb_pro_port" in source:
            target_old["dmx_usb_pro_port"] = config.dmx_usb_pro.port
            config.dmx_usb_pro.port = str(source["dmx_usb_pro_port"])
        if "dmx_usb_pro_port_index" in source:
            target_old["dmx_usb_pro_port_index"] = config.dmx_usb_pro.port_index
            config.dmx_usb_pro.port_index = int(source["dmx_usb_pro_port_index"])
        if "dmx_usb_pro_model" in source:
            target_old["dmx_usb_pro_model"] = config.dmx_usb_pro.model
            config.dmx_usb_pro.model = str(source["dmx_usb_pro_model"])

        if "protocols" in source:
            target_old["protocols"] = set(config.protocols)
            protos = {_normalize_protocol(p) for p in source["protocols"]}
            config.set_protocols(protos)
