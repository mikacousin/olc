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
        backend_dmx.send()


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

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None:
                continue

            has_pan = dev.get_channel(ChannelType.PAN) is not None
            has_tilt = dev.get_channel(ChannelType.TILT) is not None
            if not has_pan and not has_tilt:
                continue

            self.old_positions[ch] = (dev.pan_degrees, dev.tilt_degrees)
            if self.pan_delta != 0.0 and has_pan:
                dev.set_pan_degrees(dev.pan_degrees + self.pan_delta)
            if self.tilt_delta != 0.0 and has_tilt:
                dev.set_tilt_degrees(dev.tilt_degrees + self.tilt_delta)
            self.new_positions[ch] = (dev.pan_degrees, dev.tilt_degrees)

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

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None:
                continue

            has_pan = dev.get_channel(ChannelType.PAN) is not None
            has_tilt = dev.get_channel(ChannelType.TILT) is not None
            if not has_pan and not has_tilt:
                continue

            self.old_positions[ch] = (dev.pan_degrees, dev.tilt_degrees)
            if self.pan is not None and has_pan:
                dev.set_pan_degrees(self.pan)
            if self.tilt is not None and has_tilt:
                dev.set_tilt_degrees(self.tilt)
            self.new_positions[ch] = (dev.pan_degrees, dev.tilt_degrees)

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

        for ch in targets:
            dev = patch.devices.get(ch)
            if dev is None:
                continue

            has_color = any(c.channel_type in COLOR_CHANNEL_TYPES for c in dev.channels)
            if not has_color:
                continue

            srgb = dev.color_srgb
            self.old_colors[ch] = (srgb.r, srgb.g, srgb.b)
            dev.set_color_rgb_float(self.r, self.g, self.b)
            self.new_colors[ch] = (self.r, self.g, self.b)

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
                dev.set_color_rgb_float(r, g, b)

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
                dev.set_color_rgb_float(r, g, b)

        _update_dmx_and_send(self.app)
        self.app.emit(
            "device.color_changed",
            list(self.new_colors.keys()),
            (self.r, self.g, self.b),
        )
