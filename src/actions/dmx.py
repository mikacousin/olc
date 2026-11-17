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

import copy
import typing
from gettext import gettext as _

import numpy as np

from olc.core.action import Action
from olc.define import DEFAULT_UNIVERSES
from olc.dmx import Dmx
from olc.dmx_engine.universe_config import Protocol, UniverseConfig

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


def _get_active_universes(app: CoreApplication) -> list[int]:
    """Return active universe IDs from lightshow universe_map, patch, or backend."""
    if hasattr(app, "lightshow") and app.lightshow is not None:
        umap = getattr(app.lightshow, "universe_map", None)
        if isinstance(umap, dict):
            return list(umap.keys())
        if (
            umap is not None
            and hasattr(umap, "keys")
            and not hasattr(umap, "_mock_return_value")
        ):
            keys = list(umap.keys())
            if keys:
                return keys
        patch = getattr(app.lightshow, "patch", None)
        if patch is not None and isinstance(getattr(patch, "universes", None), list):
            return list(patch.universes)
    backend = getattr(app, "backend", None)
    if backend is not None and getattr(backend, "dmx", None) is not None:
        patch = getattr(backend.dmx, "patch", None)
        if patch is not None and isinstance(getattr(patch, "universes", None), list):
            return list(patch.universes)
    return list(DEFAULT_UNIVERSES)


def _get_patches(app: CoreApplication) -> list[typing.Any]:
    """Return unique active PatchManager instances attached to the app."""
    patches: list[typing.Any] = []
    if hasattr(app, "lightshow") and app.lightshow is not None:
        p = getattr(app.lightshow, "patch", None)
        if p is not None and p not in patches:
            patches.append(p)
    backend = getattr(app, "backend", None)
    if backend is not None and getattr(backend, "dmx", None) is not None:
        p = getattr(backend.dmx, "patch", None)
        if p is not None and p not in patches:
            patches.append(p)
    return patches


def _get_patch_universes(app: CoreApplication) -> list[int]:
    """Return list of universes in patch or fallback to active universes."""
    for p in _get_patches(app):
        if isinstance(getattr(p, "universes", None), list):
            return p.universes
    return _get_active_universes(app)


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
        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None

        if isinstance(backend_dmx, Dmx):
            self.old_frame = backend_dmx.snapshot_universe(self.universe)
            backend_dmx.blackout_universe(self.universe)
        else:
            if self.app.engine is not None:
                try:
                    self.old_frame = self.app.engine.snapshot_universe(self.universe)
                    self.app.engine.blackout(self.universe)
                except KeyError:
                    pass

            if backend_dmx is not None:
                patch_universes = _get_patch_universes(self.app)
                if self.universe in patch_universes:
                    idx = patch_universes.index(self.universe)
                    if idx < len(backend_dmx.frame):
                        if self.old_frame is None:
                            self.old_frame = backend_dmx.frame[idx].copy()
                        backend_dmx.frame[idx].fill(0)

        self.app.emit("universe.blackout_changed", self.universe)

    def undo(self) -> None:
        """Restore universe channel levels prior to blackout."""
        if self.old_frame is not None:
            backend = getattr(self.app, "backend", None)
            backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
            if isinstance(backend_dmx, Dmx):
                backend_dmx.apply_universe_frame(self.universe, self.old_frame)
            else:
                if self.app.engine is not None:
                    try:
                        self.app.engine.apply_universe_frame(
                            self.universe, self.old_frame
                        )
                    except KeyError:
                        pass
                if backend_dmx is not None:
                    patch_universes = _get_patch_universes(self.app)
                    if self.universe in patch_universes:
                        idx = patch_universes.index(self.universe)
                        if idx < len(backend_dmx.frame):
                            np.copyto(backend_dmx.frame[idx], self.old_frame)
        self.app.emit("universe.blackout_changed", self.universe)

    def redo(self) -> None:
        """Re-apply blackout on the configured universe."""
        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
        if isinstance(backend_dmx, Dmx):
            backend_dmx.blackout_universe(self.universe)
        else:
            if self.app.engine is not None:
                try:
                    self.app.engine.blackout(self.universe)
                except KeyError:
                    pass
            if backend_dmx is not None:
                patch_universes = _get_patch_universes(self.app)
                if self.universe in patch_universes:
                    idx = patch_universes.index(self.universe)
                    if idx < len(backend_dmx.frame):
                        backend_dmx.frame[idx].fill(0)
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
        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
        if isinstance(backend_dmx, Dmx):
            backend_dmx.set_universe_levels(self.universe, self.channels)
        else:
            if self.app.engine is not None:
                try:
                    self.app.engine.set_channels(self.universe, self.channels)
                except KeyError:
                    pass

            if backend_dmx is not None:
                patch_universes = _get_patch_universes(self.app)
                if self.universe in patch_universes:
                    idx = patch_universes.index(self.universe)
                    if idx < len(backend_dmx.frame):
                        frame = backend_dmx.frame[idx]
                        for ch, val in self.channels.items():
                            if 0 <= ch < 512:
                                frame[ch] = int(np.clip(val, 0, 255))

        self.app.emit("universe.dmx_changed", self.universe, self.channels)


class DmxTestOutputAction(Action):
    """Action to set a test level on DMX output(s)."""

    name = "dmx.test_output"
    history_label = _("Test DMX output")
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.targets: list[tuple[int, int]] = []
        self.release_targets: list[tuple[int, int]] = []
        self.level: int = 255
        self.old_levels: dict[tuple[int, int], int] = {}

    def configure(
        self,
        output: int | list[tuple[int, int]],
        universe: int = 1,
        level: int = 255,
        release_targets: list[tuple[int, int]] | None = None,
    ) -> None:
        """Configure the action with target output(s) and test level.

        Args:
            output: Single output (1-512) or list of (output, universe) tuples.
            universe: DMX universe identifier if output is an integer.
            level: Level to apply (0-255).
            release_targets: Optional list of (output, universe) to release to 0.
        """
        if isinstance(output, list):
            self.targets = list(output)
            self.level = level if level != 255 else (universe if universe != 1 else 255)
        else:
            self.targets = [(output, universe)]
            self.level = level
        self.release_targets = list(release_targets) if release_targets else []

    def get_history_details(self) -> str:
        """Return concise DMX output test details for Undo History."""
        if not self.targets:
            return ""
        pct = int(round((self.level / 255.0) * 100))
        if len(self.targets) == 1:
            out, univ = self.targets[0]
            if self.level <= 0:
                return f"{univ}/{out} → {_('Released')}"
            return f"{univ}/{out} @ {pct}%"
        if self.level <= 0:
            return f"{len(self.targets)} {_('outputs')} → {_('Released')}"
        return f"{len(self.targets)} {_('outputs')} @ {pct}%"

    def _apply_output_level(self, out: int, univ: int, lvl: int) -> None:
        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            backend.dmx.send_user_output(out, univ, lvl)
        elif self.app.engine is not None:
            try:
                self.app.engine.set_output_level(univ, out, lvl)
            except (KeyError, IndexError, AttributeError):
                pass
        self.app.emit("dmx.user_output_changed", univ, out, lvl)

    def _read_output_level(self, out: int, univ: int) -> int:
        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            return int(backend.dmx.user_outputs.get((out, univ), 0))
        if self.app.engine is not None:
            try:
                return int(self.app.engine.get_output_level(univ, out))
            except (KeyError, IndexError, AttributeError):
                pass
        return 0

    def execute(self) -> None:
        """Apply test level to configured outputs and release previous ones."""
        self.old_levels = {}
        for out, univ in self.release_targets:
            self.old_levels[(out, univ)] = self._read_output_level(out, univ)
            self._apply_output_level(out, univ, 0)
        for out, univ in self.targets:
            if (out, univ) not in self.old_levels:
                self.old_levels[(out, univ)] = self._read_output_level(out, univ)
            self._apply_output_level(out, univ, self.level)

    def undo(self) -> None:
        """Restore previous output levels prior to test."""
        for (out, univ), old in self.old_levels.items():
            self._apply_output_level(out, univ, old)

    def redo(self) -> None:
        """Re-apply test level to target outputs."""
        for out, univ in self.release_targets:
            self._apply_output_level(out, univ, 0)
        for out, univ in self.targets:
            self._apply_output_level(out, univ, self.level)


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
        if hasattr(self.app, "address_check"):
            self.app.address_check = None
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
    """Action to blackout all DMX universes simultaneously (Scenic Blackout)."""

    name = "dmx.blackout_all"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_frames: dict[int, np.ndarray] = {}
        self.target_state: bool = True
        self.old_state: bool = False

    def configure(self, state: bool | None = None) -> None:
        """Configure the target blackout state.

        Args:
            state: True for blackout, False for restore, or None to toggle.
        """
        current_state = bool(getattr(self.app, "blackout_active", False))
        if state is None:
            self.target_state = not current_state
        else:
            self.target_state = bool(state)

    def execute(self) -> None:
        """Execute blackout toggle or state change."""
        self.old_state = bool(getattr(self.app, "blackout_active", False))
        self.app.blackout_active = self.target_state
        self.old_frames = {}

        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None

        if backend_dmx is not None:
            backend_dmx.blackout = self.target_state
            if isinstance(backend_dmx, Dmx):
                backend_dmx.set_levels()
                self.app.emit("dmx.blackout_all_changed", self.target_state)
                return
            patch_universes = _get_patch_universes(self.app)
            for idx, universe in enumerate(patch_universes):
                if idx < len(backend_dmx.frame):
                    if universe not in self.old_frames:
                        self.old_frames[universe] = backend_dmx.frame[idx].copy()
                    if self.target_state:
                        backend_dmx.frame[idx].fill(0)

        # Handle engine universes (standalone or mock testing)
        if self.app.engine is not None:
            universes = _get_active_universes(self.app)
            for universe in universes:
                try:
                    if universe not in self.old_frames:
                        self.old_frames[universe] = self.app.engine.snapshot_universe(
                            universe
                        )
                    if self.target_state:
                        self.app.engine.blackout(universe)
                    elif universe in self.old_frames:
                        self.app.engine.apply_universe_frame(
                            universe, self.old_frames[universe]
                        )
                except (KeyError, AttributeError):
                    pass

        self.app.emit("dmx.blackout_all_changed", self.target_state)

    def undo(self) -> None:
        """Restore previous state prior to action."""
        self.app.blackout_active = self.old_state
        backend = getattr(self.app, "backend", None)
        backend_dmx = getattr(backend, "dmx", None) if backend is not None else None

        if backend_dmx is not None:
            backend_dmx.blackout = self.old_state
            if isinstance(backend_dmx, Dmx):
                backend_dmx.set_levels()
                self.app.emit("dmx.blackout_all_changed", self.old_state)
                return
            patch_universes = _get_patch_universes(self.app)
            for idx, universe in enumerate(patch_universes):
                if universe in self.old_frames and idx < len(backend_dmx.frame):
                    np.copyto(backend_dmx.frame[idx], self.old_frames[universe])

        if self.app.engine is not None:
            for universe, old_frame in self.old_frames.items():
                try:
                    if self.old_state:
                        self.app.engine.blackout(universe)
                    else:
                        self.app.engine.apply_universe_frame(universe, old_frame)
                except (KeyError, AttributeError):
                    pass

        self.app.emit("dmx.blackout_all_changed", self.old_state)

    def redo(self) -> None:
        """Re-apply target blackout state."""
        self.execute()

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state for Blackout All."""
        return {
            "blackout": self.target_state,
            "active": self.target_state,
        }


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
        universe_map = self.app.lightshow.universe_map
        if self.universe not in universe_map:
            raise ValueError(f"Universe {self.universe} not found")

        config = universe_map[self.universe]
        self.old_enabled = self.protocol in config.protocols

        if self.enabled:
            config.enable(self.protocol)
        else:
            config.disable(self.protocol)

        if self.app.engine is not None:
            self.app.engine.reload_universe(self.universe)
        self.app.lightshow.set_modified()

        self.app.emit(
            "universe.protocol_changed",
            self.universe,
            self.protocol.name,
            self.enabled,
        )

    def undo(self) -> None:
        """Restore previous protocol enable/disable state."""
        universe_map = self.app.lightshow.universe_map
        if self.universe not in universe_map:
            return

        config = universe_map[self.universe]
        if self.old_enabled:
            config.enable(self.protocol)
        else:
            config.disable(self.protocol)

        if self.app.engine is not None:
            self.app.engine.reload_universe(self.universe)
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
        universe_map = self.app.lightshow.universe_map
        if self.universe not in universe_map:
            raise ValueError(f"Universe {self.universe} not found")

        config = universe_map[self.universe]
        self.old_settings = {}
        self._apply_dict(config, self.settings, self.old_settings)

        if self.app.engine is not None:
            self.app.engine.reload_universe(self.universe)
        self.app.lightshow.set_modified()

        self.app.emit("universe.config_changed", self.universe, dict(self.settings))

    def undo(self) -> None:
        """Restore previous configuration parameters."""
        universe_map = self.app.lightshow.universe_map
        if self.universe not in universe_map:
            return

        config = universe_map[self.universe]
        self._apply_dict(config, self.old_settings, {})

        if self.app.engine is not None:
            self.app.engine.reload_universe(self.universe)
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


def _snapshot_universe_config(
    app: CoreApplication, universe: int
) -> UniverseConfig | None:
    """Return a deep copy of the universe configuration from lightshow if present."""
    lightshow = getattr(app, "lightshow", None)
    universe_map = getattr(lightshow, "universe_map", None)
    if universe_map is not None and universe in universe_map:
        return copy.deepcopy(universe_map[universe])
    return None


class UniverseAddAction(Action):
    """Action to dynamically add a DMX universe with Undo/Redo."""

    name = "universe.add"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.universe: int = 1
        self.config: UniverseConfig | None = None
        self.saved_config: UniverseConfig | None = None
        self.saved_unpatched: dict[int, tuple[int, int]] = {}

    def configure(
        self,
        universe: int | None = None,
        config: UniverseConfig | None = None,
    ) -> None:
        """Configure the universe to add.

        Args:
            universe: Universe ID (positive integer).
                If None, next available ID is chosen.
            config: Optional initial UniverseConfig.
        """
        if universe is None:
            existing = _get_active_universes(self.app)
            universe = max(existing, default=0) + 1
        if universe < 1:
            raise ValueError(f"Universe identifier must be positive, got {universe}")
        self.universe = universe
        self.config = config

    def execute(self) -> None:
        """Add the universe to LightShow, Engine, Patch and Dmx."""
        universe_map = getattr(self.app.lightshow, "universe_map", None)
        if universe_map is not None:
            if self.universe in universe_map:
                raise ValueError(f"Universe {self.universe} already exists")
            universe_map.add_universe(self.universe, self.config)

        if self.app.engine is not None:
            self.app.engine.add_universe(self.universe, self.config)

        for p in _get_patches(self.app):
            p.add_universe(self.universe)

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            backend.dmx.add_universe(self.universe)

        if hasattr(self.app, "lightshow") and self.app.lightshow is not None:
            self.app.lightshow.set_modified()

        self.app.emit("universe.added", self.universe)

    def undo(self) -> None:
        """Undo universe addition by removing it."""
        idx = None
        for p in _get_patches(self.app):
            if hasattr(p, "universes") and self.universe in p.universes:
                idx = p.universes.index(self.universe)
            if hasattr(p, "remove_universe"):
                res = p.remove_universe(self.universe)
                if not self.saved_unpatched and isinstance(res, dict):
                    self.saved_unpatched = res

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            backend.dmx.remove_universe(self.universe, index=idx)

        self.saved_config = _snapshot_universe_config(self.app, self.universe)
        universe_map = getattr(self.app.lightshow, "universe_map", None)
        if universe_map is not None and self.universe in universe_map:
            universe_map.remove_universe(self.universe)

        if self.app.engine is not None:
            self.app.engine.remove_universe(self.universe)

        if hasattr(self.app, "lightshow") and self.app.lightshow is not None:
            self.app.lightshow.set_modified()

        self.app.emit("universe.removed", self.universe)

    def redo(self) -> None:
        """Redo universe addition."""
        cfg = self.saved_config or self.config
        universe_map = getattr(self.app.lightshow, "universe_map", None)
        if universe_map is not None:
            universe_map.add_universe(self.universe, cfg)

        if self.app.engine is not None:
            self.app.engine.add_universe(self.universe, cfg)

        for p in _get_patches(self.app):
            p.add_universe(self.universe)
            for out, (ch, curve) in self.saved_unpatched.items():
                p.add_output(ch, out, self.universe, curve)

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            backend.dmx.add_universe(self.universe)

        if hasattr(self.app, "lightshow") and self.app.lightshow is not None:
            self.app.lightshow.set_modified()

        self.app.emit("universe.added", self.universe)


class UniverseRemoveAction(Action):
    """Action to dynamically remove a DMX universe with Undo/Redo."""

    name = "universe.remove"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.universe: int = 1
        self.saved_config: UniverseConfig | None = None
        self.saved_unpatched: dict[int, tuple[int, int]] = {}
        self.saved_index: int = 0

    def configure(self, universe: int) -> None:
        """Configure the universe to remove.

        Args:
            universe: Universe ID (positive integer).
        """
        self.universe = universe

    def execute(self) -> None:
        """Remove the universe from LightShow, Engine, Patch and Dmx."""
        existing = _get_active_universes(self.app)
        if len(existing) <= 1:
            raise ValueError(
                "Cannot remove the last universe. "
                "At least one universe must be configured."
            )

        self.saved_config = _snapshot_universe_config(self.app, self.universe)

        idx = None
        for p in _get_patches(self.app):
            if hasattr(p, "universes") and self.universe in p.universes:
                idx = p.universes.index(self.universe)
            if hasattr(p, "remove_universe"):
                res = p.remove_universe(self.universe)
                if not self.saved_unpatched and isinstance(res, dict):
                    self.saved_unpatched = res
                    self.saved_index = idx or 0

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            backend.dmx.remove_universe(self.universe, index=idx)

        universe_map = getattr(self.app.lightshow, "universe_map", None)
        if universe_map is not None and self.universe in universe_map:
            universe_map.remove_universe(self.universe)

        if self.app.engine is not None:
            self.app.engine.remove_universe(self.universe)

        if hasattr(self.app, "lightshow") and self.app.lightshow is not None:
            self.app.lightshow.set_modified()

        self.app.emit("universe.removed", self.universe)

    def undo(self) -> None:
        """Undo universe removal by re-adding it and restoring unpatched outputs."""
        universe_map = getattr(self.app.lightshow, "universe_map", None)
        if universe_map is not None:
            universe_map.add_universe(self.universe, self.saved_config)

        if self.app.engine is not None:
            self.app.engine.add_universe(self.universe, self.saved_config)

        for p in _get_patches(self.app):
            p.add_universe(self.universe)
            for out, (ch, curve) in self.saved_unpatched.items():
                p.add_output(ch, out, self.universe, curve)

        backend = getattr(self.app, "backend", None)
        if backend is not None and getattr(backend, "dmx", None) is not None:
            backend.dmx.add_universe(self.universe)

        if hasattr(self.app, "lightshow") and self.app.lightshow is not None:
            self.app.lightshow.set_modified()

        self.app.emit("universe.added", self.universe)

    def redo(self) -> None:
        """Redo universe removal."""
        self.execute()
