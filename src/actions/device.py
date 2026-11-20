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
"""Core actions for multi-parameter lighting devices (Pan, Tilt, Color)."""

from __future__ import annotations

import typing

from olc.core.action import Action
from olc.devices.device import COLOR_CHANNEL_TYPES, ChannelType

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


def _update_dmx_and_send(app: CoreApplication) -> None:
    """Helper to update DMX frame and send if backend DMX is active."""
    backend = getattr(app, "backend", None)
    backend_dmx = getattr(backend, "dmx", None) if backend is not None else None
    if backend_dmx is not None and type(backend_dmx).__name__ == "Dmx":
        backend_dmx.set_levels()


def _snapshot_live_state(
    app: CoreApplication, ch: int, old_map: dict[int, typing.Any]
) -> None:
    """Capture channel live state snapshot once before modifying parameters."""
    live_state = getattr(app, "live_state", None)
    if live_state is not None and ch not in old_map:
        old_map[ch] = live_state.snapshot_channel(ch)


def _mark_live_manual(
    app: CoreApplication,
    ch: int,
    params: typing.Iterable[str],
    new_map: dict[int, typing.Any],
) -> None:
    """Mark *params* manual on *ch* (breaking palette refs) and save snapshot."""
    live_state = getattr(app, "live_state", None)
    if live_state is None:
        return
    param_list = [p for p in params if p]
    if param_list:
        live_state.mark_manual_params(ch, param_list, break_refs=True)
    new_map[ch] = live_state.snapshot_channel(ch)


def _restore_live_states(
    app: CoreApplication, state_map: dict[int, typing.Any]
) -> None:
    """Restore per-channel live state snapshots."""
    live_state = getattr(app, "live_state", None)
    if live_state is None:
        return
    for ch, snap in state_map.items():
        live_state.restore_channel(ch, snap)


class DevicePanTiltAdjustAction(Action):
    """Action to adjust Pan and/or Tilt relatively on selected or target devices."""

    name = "device.adjust_pan_tilt"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.pan_delta: float = 0.0
        self.tilt_delta: float = 0.0
        self.channels: list[int] | None = None
        self.old_positions: dict[int, tuple[float, float]] = {}
        self.new_positions: dict[int, tuple[float, float]] = {}
        self._old_live_states: dict[int, typing.Any] = {}
        self._new_live_states: dict[int, typing.Any] = {}

    def configure(
        self,
        pan_delta: float = 0.0,
        tilt_delta: float = 0.0,
        channels: list[int] | None = None,
    ) -> None:
        """Configure relative adjustments in degrees.

        Args:
            pan_delta: Delta in degrees to add to current Pan.
            tilt_delta: Delta in degrees to add to current Tilt.
            channels: Specific channel IDs, or None to use active selection.
        """
        self.pan_delta = float(pan_delta)
        self.tilt_delta = float(tilt_delta)
        self.channels = list(channels) if channels is not None else None

    def execute(self) -> None:
        """Apply relative pan/tilt adjustments."""
        targets = (
            self.channels
            if self.channels is not None
            else list(getattr(self.app, "selected_channels", []))
        )
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None or not targets:
            self.can_undo = False
            return

        self.old_positions = {}
        self.new_positions = {}
        self._old_live_states = {}
        self._new_live_states = {}

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None:
                continue

            has_pan = dev.get_channel(ChannelType.PAN) is not None
            has_tilt = dev.get_channel(ChannelType.TILT) is not None
            if not has_pan and not has_tilt:
                continue

            _snapshot_live_state(self.app, ch, self._old_live_states)
            self.old_positions[ch] = (dev.pan_degrees, dev.tilt_degrees)
            changed_params: list[str] = []
            if self.pan_delta != 0.0 and has_pan:
                dev.set_pan_degrees(dev.pan_degrees + self.pan_delta)
                changed_params.append("pan")
            if self.tilt_delta != 0.0 and has_tilt:
                dev.set_tilt_degrees(dev.tilt_degrees + self.tilt_delta)
                changed_params.append("tilt")
            self.new_positions[ch] = (dev.pan_degrees, dev.tilt_degrees)
            _mark_live_manual(self.app, ch, changed_params, self._new_live_states)

        if not self.new_positions:
            self.can_undo = False
            return

        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_positions.keys()))

    def undo(self) -> None:
        """Revert devices to their previous pan/tilt positions."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, (old_pan, old_tilt) in self.old_positions.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                if dev.get_channel(ChannelType.PAN) is not None:
                    dev.set_pan_degrees(old_pan)
                if dev.get_channel(ChannelType.TILT) is not None:
                    dev.set_tilt_degrees(old_tilt)

        _restore_live_states(self.app, self._old_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.old_positions.keys()))

    def redo(self) -> None:
        """Reapply new pan/tilt positions."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, (new_pan, new_tilt) in self.new_positions.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                if dev.get_channel(ChannelType.PAN) is not None:
                    dev.set_pan_degrees(new_pan)
                if dev.get_channel(ChannelType.TILT) is not None:
                    dev.set_tilt_degrees(new_tilt)

        _restore_live_states(self.app, self._new_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_positions.keys()))


class DeviceSetPanTiltAction(Action):
    """Action to set absolute Pan and/or Tilt positions in degrees."""

    name = "device.set_pan_tilt"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.pan: float | None = None
        self.tilt: float | None = None
        self.channels: list[int] | None = None
        self.old_positions: dict[int, tuple[float, float]] = {}
        self.new_positions: dict[int, tuple[float, float]] = {}
        self._old_live_states: dict[int, typing.Any] = {}
        self._new_live_states: dict[int, typing.Any] = {}

    def configure(
        self,
        pan: float | None = None,
        tilt: float | None = None,
        channels: list[int] | None = None,
    ) -> None:
        """Configure absolute target positions in degrees.

        Args:
            pan: Absolute Pan in degrees, or None to keep unchanged.
            tilt: Absolute Tilt in degrees, or None to keep unchanged.
            channels: Specific channel IDs, or None to use active selection.
        """
        self.pan = float(pan) if pan is not None else None
        self.tilt = float(tilt) if tilt is not None else None
        self.channels = list(channels) if channels is not None else None

    def execute(self) -> None:
        """Apply absolute pan/tilt positions."""
        targets = (
            self.channels
            if self.channels is not None
            else list(getattr(self.app, "selected_channels", []))
        )
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None or not targets or (self.pan is None and self.tilt is None):
            self.can_undo = False
            return

        self.old_positions = {}
        self.new_positions = {}
        self._old_live_states = {}
        self._new_live_states = {}

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None:
                continue

            has_pan = dev.get_channel(ChannelType.PAN) is not None
            has_tilt = dev.get_channel(ChannelType.TILT) is not None
            if not has_pan and not has_tilt:
                continue

            _snapshot_live_state(self.app, ch, self._old_live_states)
            self.old_positions[ch] = (dev.pan_degrees, dev.tilt_degrees)
            changed_params: list[str] = []
            if self.pan is not None and has_pan:
                dev.set_pan_degrees(self.pan)
                changed_params.append("pan")
            if self.tilt is not None and has_tilt:
                dev.set_tilt_degrees(self.tilt)
                changed_params.append("tilt")
            self.new_positions[ch] = (dev.pan_degrees, dev.tilt_degrees)
            _mark_live_manual(self.app, ch, changed_params, self._new_live_states)

        if not self.new_positions:
            self.can_undo = False
            return

        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_positions.keys()))

    def undo(self) -> None:
        """Revert devices to old pan/tilt positions."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, (old_pan, old_tilt) in self.old_positions.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                if dev.get_channel(ChannelType.PAN) is not None:
                    dev.set_pan_degrees(old_pan)
                if dev.get_channel(ChannelType.TILT) is not None:
                    dev.set_tilt_degrees(old_tilt)

        _restore_live_states(self.app, self._old_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.old_positions.keys()))

    def redo(self) -> None:
        """Reapply new pan/tilt positions."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, (new_pan, new_tilt) in self.new_positions.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                if dev.get_channel(ChannelType.PAN) is not None:
                    dev.set_pan_degrees(new_pan)
                if dev.get_channel(ChannelType.TILT) is not None:
                    dev.set_tilt_degrees(new_tilt)

        _restore_live_states(self.app, self._new_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_positions.keys()))


class DeviceSetColorAction(Action):
    """Action to set color (RGB) on selected or target color-capable devices."""

    name = "device.set_color"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.r: float = 1.0
        self.g: float = 1.0
        self.b: float = 1.0
        self.channels: list[int] | None = None
        self.old_colors: dict[int, tuple[float, float, float]] = {}
        self.new_colors: dict[int, tuple[float, float, float]] = {}
        self._old_live_states: dict[int, typing.Any] = {}
        self._new_live_states: dict[int, typing.Any] = {}

    def configure(
        self,
        r: float,
        g: float,
        b: float,
        channels: list[int] | None = None,
    ) -> None:
        """Configure target color components (supports 0.0..1.0 or 0..255).

        Args:
            r: Red value.
            g: Green value.
            b: Blue value.
            channels: Specific channel IDs, or None to use active selection.
        """
        raw_r, raw_g, raw_b = float(r), float(g), float(b)
        if raw_r > 1.0 or raw_g > 1.0 or raw_b > 1.0:
            raw_r /= 255.0
            raw_g /= 255.0
            raw_b /= 255.0
        self.r = max(0.0, min(1.0, raw_r))
        self.g = max(0.0, min(1.0, raw_g))
        self.b = max(0.0, min(1.0, raw_b))
        self.channels = list(channels) if channels is not None else None

    def execute(self) -> None:
        """Apply color to devices."""
        targets = (
            self.channels
            if self.channels is not None
            else list(getattr(self.app, "selected_channels", []))
        )
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None or not targets:
            self.can_undo = False
            return

        self.old_colors = {}
        self.new_colors = {}
        self._old_live_states = {}
        self._new_live_states = {}

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None:
                continue

            has_color = any(c.channel_type in COLOR_CHANNEL_TYPES for c in dev.channels)
            if not has_color:
                continue

            _snapshot_live_state(self.app, ch, self._old_live_states)
            srgb = dev.color_srgb
            self.old_colors[ch] = (srgb.r, srgb.g, srgb.b)
            dev.set_color_srgb(self.r, self.g, self.b)
            self.new_colors[ch] = (self.r, self.g, self.b)
            _mark_live_manual(self.app, ch, ("color",), self._new_live_states)

        if not self.new_colors:
            self.can_undo = False
            return

        _update_dmx_and_send(self.app)
        self.app.emit(
            "device.color_changed",
            list(self.new_colors.keys()),
            (self.r, self.g, self.b),
        )

    def undo(self) -> None:
        """Revert devices to their previous colors."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, (r, g, b) in self.old_colors.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                dev.set_color_srgb(r, g, b)

        _restore_live_states(self.app, self._old_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.color_changed", list(self.old_colors.keys()), None)

    def redo(self) -> None:
        """Reapply new color."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, (r, g, b) in self.new_colors.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                dev.set_color_srgb(r, g, b)

        _restore_live_states(self.app, self._new_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit(
            "device.color_changed",
            list(self.new_colors.keys()),
            (self.r, self.g, self.b),
        )


_PARAM_NAME_MAP: dict[str, ChannelType] = {
    "zoom": ChannelType.ZOOM,
    "focus": ChannelType.FOCUS,
    "iris": ChannelType.IRIS,
    "strobe": ChannelType.STROBE,
    "shutter": ChannelType.STROBE,
    "frost": ChannelType.FROST,
    "gobo": ChannelType.GOBO_WHEEL,
    "gobo_wheel": ChannelType.GOBO_WHEEL,
    "prism": ChannelType.PRISM,
    "cct": ChannelType.COLOR_TEMP,
    "kelvin": ChannelType.COLOR_TEMP,
    "color_temp": ChannelType.COLOR_TEMP,
    "color_wheel": ChannelType.COLOR_WHEEL,
    "intensity": ChannelType.INTENSITY,
    "pan": ChannelType.PAN,
    "tilt": ChannelType.TILT,
    "macro": ChannelType.MACRO,
    "reset": ChannelType.RESET,
}


def _resolve_channel_type(param: str | ChannelType) -> ChannelType | None:
    """Resolve string parameter name or ChannelType enum into ChannelType."""
    if isinstance(param, ChannelType):
        return param
    if isinstance(param, str):
        normalized = param.lower().strip()
        if normalized in _PARAM_NAME_MAP:
            return _PARAM_NAME_MAP[normalized]
        try:
            return ChannelType(normalized)
        except ValueError:
            return None
    return None


class DeviceSetParameterAction(Action):
    """Action to set a normalized or physical parameter value on target devices."""

    name = "device.set_parameter"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.parameter: str | ChannelType = ""
        self.ch_type: ChannelType | None = None
        self.value: float = 0.0
        self.is_physical: bool = False
        self.channels: list[int] | None = None
        self.old_values: dict[int, float] = {}
        self.new_values: dict[int, float] = {}
        self._old_live_states: dict[int, typing.Any] = {}
        self._new_live_states: dict[int, typing.Any] = {}

    def configure(
        self,
        parameter: str | ChannelType,
        value: float,
        channels: list[int] | None = None,
        is_physical: bool = False,
    ) -> None:
        """Configure target parameter and value.

        Args:
            parameter: ChannelType or parameter name (e.g. 'zoom', 'focus', 'iris').
            value: Normalized value [0.0..1.0] or physical value if is_physical=True.
            channels: Specific channel IDs, or None to use active selection.
            is_physical: True if value is in physical units (degrees, meters, Hz).
        """
        self.parameter = parameter
        self.ch_type = _resolve_channel_type(parameter)
        self.value = float(value)
        self.is_physical = is_physical
        self.channels = list(channels) if channels is not None else None

    def execute(self) -> None:
        """Apply parameter value to target devices."""
        if self.ch_type is None:
            self.can_undo = False
            return

        targets = (
            self.channels
            if self.channels is not None
            else list(getattr(self.app, "selected_channels", []))
        )
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None or not targets:
            self.can_undo = False
            return

        self.old_values = {}
        self.new_values = {}
        self._old_live_states = {}
        self._new_live_states = {}
        param_key = self.ch_type.value

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None or dev.get_channel(self.ch_type) is None:
                continue

            _snapshot_live_state(self.app, ch, self._old_live_states)
            old_norm = dev.get_parameter_normalized(self.ch_type)
            self.old_values[ch] = old_norm if old_norm is not None else 0.0

            if self.is_physical:
                if hasattr(dev, "apply_device_parameter"):
                    param_name = getattr(self.ch_type, "value", str(self.parameter))
                    dev.apply_device_parameter(param_name, self.value)
                    new_norm = dev.get_parameter_normalized(self.ch_type)
                    self.new_values[ch] = new_norm if new_norm is not None else 0.0
                else:
                    # Map physical to normalized via internal helper
                    dev._set_physical_parameter(  # pylint: disable=protected-access
                        self.ch_type, self.value
                    )
                    new_norm = dev.get_parameter_normalized(self.ch_type)
                    self.new_values[ch] = new_norm if new_norm is not None else 0.0
            else:
                clamped = max(0.0, min(1.0, self.value))
                dev.set_parameter_normalized(self.ch_type, clamped)
                self.new_values[ch] = clamped
            _mark_live_manual(self.app, ch, (param_key,), self._new_live_states)

        if not self.new_values:
            self.can_undo = False
            return

        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_values.keys()))

    def undo(self) -> None:
        """Revert target devices to their previous parameter values."""
        if self.ch_type is None:
            return

        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, old_val in self.old_values.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                dev.set_parameter_normalized(self.ch_type, old_val)

        _restore_live_states(self.app, self._old_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.old_values.keys()))

    def redo(self) -> None:
        """Reapply target parameter values."""
        if self.ch_type is None:
            return

        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, new_val in self.new_values.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                dev.set_parameter_normalized(self.ch_type, new_val)

        _restore_live_states(self.app, self._new_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_values.keys()))

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return structured execution result for OSC/UI feedback."""
        return {
            "parameter": self.ch_type.value if self.ch_type is not None else "",
            "value": self.value,
            "channels": list(self.new_values.keys()),
        }


class DeviceAdjustParameterAction(Action):
    """Action to adjust a normalized parameter relatively (jog-wheel) with Undo."""

    name = "device.adjust_parameter"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.parameter: str | ChannelType = ""
        self.ch_type: ChannelType | None = None
        self.delta: float = 0.0
        self.channels: list[int] | None = None
        self.old_values: dict[int, float] = {}
        self.new_values: dict[int, float] = {}
        self._old_live_states: dict[int, typing.Any] = {}
        self._new_live_states: dict[int, typing.Any] = {}

    def configure(
        self,
        parameter: str | ChannelType,
        delta: float,
        channels: list[int] | None = None,
    ) -> None:
        """Configure relative delta adjustment.

        Args:
            parameter: ChannelType or parameter name (e.g. 'zoom', 'focus').
            delta: Normalized delta to add (e.g. +0.05, -0.05).
            channels: Specific channel IDs, or None to use active selection.
        """
        self.parameter = parameter
        self.ch_type = _resolve_channel_type(parameter)
        self.delta = float(delta)
        self.channels = list(channels) if channels is not None else None

    def execute(self) -> None:
        """Apply relative adjustment to target devices."""
        if self.ch_type is None:
            self.can_undo = False
            return

        targets = (
            self.channels
            if self.channels is not None
            else list(getattr(self.app, "selected_channels", []))
        )
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None or not targets or self.delta == 0.0:
            self.can_undo = False
            return

        self.old_values = {}
        self.new_values = {}
        self._old_live_states = {}
        self._new_live_states = {}
        param_key = self.ch_type.value

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None or dev.get_channel(self.ch_type) is None:
                continue

            _snapshot_live_state(self.app, ch, self._old_live_states)
            old_norm = dev.get_parameter_normalized(self.ch_type)
            cur_norm = old_norm if old_norm is not None else 0.0
            new_norm = max(0.0, min(1.0, cur_norm + self.delta))

            self.old_values[ch] = cur_norm
            dev.set_parameter_normalized(self.ch_type, new_norm)
            self.new_values[ch] = new_norm
            _mark_live_manual(self.app, ch, (param_key,), self._new_live_states)

        if not self.new_values:
            self.can_undo = False
            return

        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_values.keys()))

    def undo(self) -> None:
        """Revert target devices to old parameter values."""
        if self.ch_type is None:
            return

        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, old_val in self.old_values.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                dev.set_parameter_normalized(self.ch_type, old_val)

        _restore_live_states(self.app, self._old_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.old_values.keys()))

    def redo(self) -> None:
        """Reapply adjusted parameter values."""
        if self.ch_type is None:
            return

        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, new_val in self.new_values.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                dev.set_parameter_normalized(self.ch_type, new_val)

        _restore_live_states(self.app, self._new_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_values.keys()))

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return structured execution result for OSC/UI feedback."""
        return {
            "parameter": self.ch_type.value if self.ch_type is not None else "",
            "delta": self.delta,
            "channels": list(self.new_values.keys()),
        }


class DeviceHomeAction(Action):
    """Action to reset fixture parameters to default Home values."""

    name = "device.home"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channels: list[int] | None = None
        self.category: str | None = None
        self.old_states: dict[int, dict[int, int]] = {}
        self.new_states: dict[int, dict[int, int]] = {}
        self.old_intensities: dict[int, float] = {}
        self.new_intensities: dict[int, float] = {}
        self._old_live_states: dict[int, typing.Any] = {}
        self._new_live_states: dict[int, typing.Any] = {}

    def configure(
        self,
        channels: list[int] | None = None,
        category: str | None = None,
    ) -> None:
        """Configure target channels and optional parameter category filter."""
        self.channels = list(channels) if channels is not None else None
        self.category = str(category).lower() if category is not None else None

    def execute(self) -> None:
        """Apply home reset to target or selected fixtures."""
        targets = (
            self.channels
            if self.channels is not None
            else list(getattr(self.app, "selected_channels", []))
        )
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None or not targets:
            self.can_undo = False
            return

        self.old_states = {}
        self.new_states = {}
        self.old_intensities = {}
        self.new_intensities = {}
        self._old_live_states = {}
        self._new_live_states = {}
        live_state = getattr(self.app, "live_state", None)

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None:
                continue

            _snapshot_live_state(self.app, ch, self._old_live_states)
            self.old_states[ch] = {c.address: c.value for c in dev.channels}
            self.old_intensities[ch] = dev.intensity
            dev.home(self.category)
            self.new_states[ch] = {c.address: c.value for c in dev.channels}
            self.new_intensities[ch] = dev.intensity
            if live_state is not None:
                live_state.break_family_refs(ch, self.category)
                changed_params = [
                    c.channel_type.value
                    for c in dev.channels
                    if c.value != self.old_states[ch].get(c.address)
                ]
                _mark_live_manual(self.app, ch, changed_params, self._new_live_states)

        if not self.new_states:
            self.can_undo = False
            return

        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_states.keys()))

    def undo(self) -> None:
        """Revert target devices to states before home."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, states in self.old_states.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                for c in dev.channels:
                    if c.address in states:
                        c.set_value(states[c.address])
                if ch in self.old_intensities:
                    dev.set_intensity(self.old_intensities[ch])

        _restore_live_states(self.app, self._old_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.old_states.keys()))

    def redo(self) -> None:
        """Reapply home states."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        for ch, states in self.new_states.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                for c in dev.channels:
                    if c.address in states:
                        c.set_value(states[c.address])
                if ch in self.new_intensities:
                    dev.set_intensity(self.new_intensities[ch])

        _restore_live_states(self.app, self._new_live_states)
        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_states.keys()))


class DeviceLocateAction(Action):
    """Action to reset fixture parameters to Home and bring intensity to full / open."""

    name = "device.locate"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channels: list[int] | None = None
        self.old_states: dict[int, dict[int, int]] = {}
        self.new_states: dict[int, dict[int, int]] = {}
        self.old_intensities: dict[int, float] = {}
        self.new_intensities: dict[int, float] = {}
        self._old_live_states: dict[int, typing.Any] = {}
        self._new_live_states: dict[int, typing.Any] = {}
        self.old_user_levels: dict[int, int] = {}

    def configure(self, channels: list[int] | None = None) -> None:
        """Configure target channels, or None for current selection."""
        self.channels = list(channels) if channels is not None else None

    def execute(self) -> None:
        """Apply locate to target or selected fixtures."""
        targets = (
            self.channels
            if self.channels is not None
            else list(getattr(self.app, "selected_channels", []))
        )
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None or not targets:
            self.can_undo = False
            return

        self.old_states = {}
        self.new_states = {}
        self.old_intensities = {}
        self.new_intensities = {}
        self._old_live_states = {}
        self._new_live_states = {}
        self.old_user_levels: dict[int, float] = {}

        backend = getattr(self.app, "backend", None)
        dmx = getattr(backend, "dmx", None) if backend is not None else None
        user_levels = getattr(dmx, "levels", {}).get("user") if dmx else None
        live_state = getattr(self.app, "live_state", None)

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None:
                continue

            _snapshot_live_state(self.app, ch, self._old_live_states)
            self.old_states[ch] = {c.address: c.value for c in dev.channels}
            self.old_intensities[ch] = dev.intensity
            dev.locate()
            self.new_states[ch] = {c.address: c.value for c in dev.channels}
            self.new_intensities[ch] = dev.intensity

            changed_params = [
                c.channel_type.value
                for c in dev.channels
                if c.value != self.old_states[ch].get(c.address)
            ]
            if user_levels is not None and 1 <= ch <= len(user_levels):
                self.old_user_levels[ch] = float(user_levels[ch - 1])
                user_levels[ch - 1] = 1.0
                changed_params.append("intensity")
                self.app.emit("channel.level_changed", ch, 1.0)
            if live_state is not None:
                live_state.break_family_refs(ch, None)
                _mark_live_manual(self.app, ch, changed_params, self._new_live_states)

        if not self.new_states:
            self.can_undo = False
            return

        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_states.keys()))

    def undo(self) -> None:
        """Revert target devices to states before locate."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        backend = getattr(self.app, "backend", None)
        dmx = getattr(backend, "dmx", None) if backend is not None else None
        user_levels = getattr(dmx, "levels", {}).get("user") if dmx else None

        _restore_live_states(self.app, self._old_live_states)
        for ch, states in self.old_states.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                for c in dev.channels:
                    if c.address in states:
                        c.set_value(states[c.address])
                if ch in self.old_intensities:
                    dev.set_intensity(self.old_intensities[ch])
            if (
                user_levels is not None
                and ch in self.old_user_levels
                and 1 <= ch <= len(user_levels)
            ):
                user_levels[ch - 1] = self.old_user_levels[ch]
                self.app.emit("channel.level_changed", ch, self.old_user_levels[ch])

        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.old_states.keys()))

    def redo(self) -> None:
        """Reapply locate states."""
        patch = getattr(self.app.lightshow, "patch", None)
        if patch is None:
            return

        backend = getattr(self.app, "backend", None)
        dmx = getattr(backend, "dmx", None) if backend is not None else None
        user_levels = getattr(dmx, "levels", {}).get("user") if dmx else None

        _restore_live_states(self.app, self._new_live_states)
        for ch, states in self.new_states.items():
            dev = patch.devices.get(ch)
            if dev is not None:
                for c in dev.channels:
                    if c.address in states:
                        c.set_value(states[c.address])
                if ch in self.new_intensities:
                    dev.set_intensity(self.new_intensities[ch])
            if user_levels is not None and 1 <= ch <= len(user_levels):
                user_levels[ch - 1] = 1.0
                self.app.emit("channel.level_changed", ch, 1.0)

        _update_dmx_and_send(self.app)
        self.app.emit("device.parameters_changed", list(self.new_states.keys()))
