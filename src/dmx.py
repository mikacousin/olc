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
from __future__ import annotations

import typing
from typing import Callable, Optional

import numpy as np
from gi.repository import GLib
from olc.define import DMX_INTERVAL, MAX_CHANNELS, NB_UNIVERSES, UNIVERSES
from olc.main_fader import MainFader
from olc.patch import DMXPatch
from olc.timer import RepeatedTimer

if typing.TYPE_CHECKING:
    from olc.backends import DMXBackend
    from olc.lightshow import LightShow


class DmxLevels(dict):
    """Custom dictionary to automatically convert list values to NumPy arrays."""
    def __setitem__(self, key: str, value: object) -> None:
        if isinstance(value, list):
            dtype = np.int16 if key == "user" else np.uint8
            super().__setitem__(key, np.array(value, dtype=dtype))
        else:
            super().__setitem__(key, value)


# pylint: disable=too-many-instance-attributes
class Dmx:
    """Send levels to backend"""

    backend: Optional[DMXBackend]
    patch: DMXPatch
    main_fader: MainFader
    levels: DmxLevels
    frame: list[np.ndarray]
    user_outputs: dict[tuple[int, int], int]
    thread: RepeatedTimer
    output_callbacks: list[Callable[[int, list[int]], None]]
    notification_callbacks: list[Callable[[str, str], None]]

    def __init__(self, backend: Optional[DMXBackend], lightshow: LightShow) -> None:
        self.backend = backend
        self.lightshow = lightshow
        self.patch = self.lightshow.patch
        self.main_fader = MainFader()
        # Dimmers levels
        self.levels = DmxLevels({
            "sequence": np.zeros(MAX_CHANNELS, dtype=np.uint8),
            "user": np.full(MAX_CHANNELS, -1, dtype=np.int16),
            "faders": np.zeros(MAX_CHANNELS, dtype=np.uint8),
        })
        # DMX values
        self.frame = [np.zeros(512, dtype=np.uint8) for _ in range(NB_UNIVERSES)]
        self._old_frame = [np.zeros(512, dtype=np.uint8) for _ in range(NB_UNIVERSES)]
        self._old_channel_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        # To test outputs
        self.user_outputs = {}
        # Callbacks for UI updates
        self.output_callbacks = []
        # Callbacks for notifications
        self.notification_callbacks = []
        # Thread to send DMX every DMX_INTERVAL ms
        self.thread = RepeatedTimer(DMX_INTERVAL / 1000, self.send)

    def get_composite_level(self, channel_idx: int) -> tuple[int, dict[str, float]]:
        """Get the composite level and state color for a channel (0-indexed).

        Args:
            channel_idx: Channel index (0 to MAX_CHANNELS - 1)

        Returns:
            Tuple of (composite_level, color_dict)
        """
        color_level = {"red": 0.9, "green": 0.9, "blue": 0.9}
        level = self.levels["sequence"][channel_idx]
        if (
            not self.lightshow.main_playback.on_go
            and self.levels["user"][channel_idx] != -1
        ):
            level = self.levels["user"][channel_idx]
        if self.levels["faders"][channel_idx] > level:
            level = self.levels["faders"][channel_idx]
            color_level = {"red": 0.4, "green": 0.7, "blue": 0.4}
        if self.lightshow.independents.dmx[channel_idx] > level:
            level = self.lightshow.independents.dmx[channel_idx]
            color_level = {"red": 0.4, "green": 0.4, "blue": 0.7}
        return int(level), color_level

    def get_all_composite_levels(self) -> np.ndarray:
        """Get composite levels for all channels simultaneously by block.

        Returns:
            Array of composite levels.
        """
        composite = self.levels["sequence"].copy()
        composite = np.maximum(composite, self.levels["faders"])
        composite = np.maximum(composite, self.lightshow.independents.dmx)
        user_mask = self.levels["user"] != -1
        composite[user_mask] = self.levels["user"][user_mask]
        return composite

    def set_levels(self) -> None:
        """Set DMX frame levels"""
        composite = self.get_all_composite_levels()

        self.patch.update_numpy_cache_if_dirty()

        # Extract levels for each patched output slot
        out_levels = composite[self.patch.map_src_channels].astype(np.float64)

        # Apply curves by block
        unique_curves = np.unique(self.patch.map_dst_curves)
        for curve_numb in unique_curves:
            if curve_numb != 0:
                curve = self.lightshow.curves.get_curve(curve_numb)
                if curve:
                    curve_mask = self.patch.map_dst_curves == curve_numb
                    out_levels[curve_mask] = curve.values_array[
                        out_levels[curve_mask].astype(np.uint8)
                    ]

        # Scale by Main Fader
        out_levels = np.round(out_levels * self.main_fader.value).astype(np.uint8)

        # Distribute levels to self.frame using advanced indexing
        for index in range(NB_UNIVERSES):
            univ_mask = self.patch.map_dst_universes == index
            if np.any(univ_mask):
                self.frame[index][self.patch.map_dst_outputs[univ_mask]] = out_levels[
                    univ_mask
                ]

    def send(self) -> None:
        """Send DMX values to CoreEngine"""
        if self.lightshow.app is not None and self.lightshow.app.engine is not None:
            engine = self.lightshow.app.engine
            for index, universe in enumerate(UNIVERSES):
                current_frame = self.frame[index]
                old_frame = self._old_frame[index]
                if not np.array_equal(current_frame, old_frame):
                    changed_outputs = np.where(current_frame != old_frame)[0].tolist()
                    if changed_outputs:
                        GLib.idle_add(
                            self.trigger_output_callbacks, universe, changed_outputs
                        )
                    np.copyto(self._old_frame[index], current_frame)
                engine.universe(universe).apply_array(current_frame)

            # Compute composite levels for all channels to check for modifications
            self.patch.update_numpy_cache_if_dirty()

            composite = self.get_all_composite_levels()
            current_display_levels = np.round(
                composite * self.main_fader.value
            ).astype(np.uint8)

            changed_indices = np.where(
                (current_display_levels != self._old_channel_levels)
                & self.patch.is_patched_mask
            )[0]

            if len(changed_indices) > 0:
                self._old_channel_levels[changed_indices] = current_display_levels[
                    changed_indices
                ]
                changed_channels = (changed_indices + 1).tolist()
                GLib.idle_add(self.trigger_channels_update, changed_channels)

    def trigger_channels_update(self, changed_channels: list[int]) -> None:
        """Trigger channel widgets updates on the main thread."""
        if self.lightshow.app is not None and self.lightshow.app.window is not None:
            live_view = self.lightshow.app.window.live_view
            for channel in changed_channels:
                step = self.lightshow.main_playback.steps[
                    self.lightshow.main_playback.position
                ]
                seq_level = 0
                if step.cue is not None:
                    seq_level = step.cue.channels.get(channel, 0)
                seq_next_level = self.lightshow.main_playback.get_next_channel_level(
                    channel, seq_level
                )
                live_view.update_channel_widget(channel, seq_next_level)

    def all_outputs_at_zero(self) -> None:
        """All DMX outputs to 0"""
        for index, universe in enumerate(UNIVERSES):
            self.frame[index].fill(0)
            if self.lightshow.app is not None and self.lightshow.app.engine is not None:
                self.lightshow.app.engine.universe(universe).blackout()

    def send_user_output(self, output: int, universe: int, level: int) -> None:
        """Send level to an output

        Args:
            output: Output number (1-512)
            universe: Universe number (one in UNIVERSES)
            level: Output level (0-255)
        """
        self.user_outputs[(output, universe)] = level
        index = UNIVERSES.index(universe)
        self.frame[index][output - 1] = level
        if not level:
            self.user_outputs.pop((output, universe))
        if self.lightshow.app is not None and self.lightshow.app.engine is not None:
            self.lightshow.app.engine.universe(universe).array[output - 1] = level

    def add_output_callback(self, callback: Callable[[int, list[int]], None]) -> None:
        """Register a callback for output level changes."""
        if callback not in self.output_callbacks:
            self.output_callbacks.append(callback)

    def remove_output_callback(
        self, callback: Callable[[int, list[int]], None]
    ) -> None:
        """Remove a callback for output level changes."""
        if callback in self.output_callbacks:
            self.output_callbacks.remove(callback)

    def trigger_output_callbacks(self, universe: int, outputs: list[int]) -> None:
        """Trigger registered callbacks.

        Args:
            universe: Universe number
            outputs: List of changed output indices
        """
        for callback in self.output_callbacks:
            callback(universe, outputs)

    def add_notification_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback for notifications."""
        if callback not in self.notification_callbacks:
            self.notification_callbacks.append(callback)

    def trigger_notification(self, title: str, body: str) -> None:
        """Trigger registered notification callbacks.

        Args:
            title: Notification title
            body: Notification body text
        """
        for callback in self.notification_callbacks:
            callback(title, body)
