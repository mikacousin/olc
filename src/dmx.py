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

from olc.core.park import ParkManager
from olc.core.tracking import (
    TrackingDisplayState,
    classify_channel_tracking_state,
    get_tracking_color,
)
from olc.define import DMX_INTERVAL, MAX_CHANNELS
from olc.main_fader import MainFader
from olc.patch import DMXPatch
from olc.timer import RepeatedTimer

if typing.TYPE_CHECKING:
    from olc.core.backends import DMXBackend
    from olc.core.lightshow import LightShow


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
    blackout: bool
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
        self.blackout = False
        # Dimmers levels (floating-point for silky-smooth 16/24-bit crossfades)
        self.levels = DmxLevels(
            {
                "sequence": np.zeros(MAX_CHANNELS, dtype=np.float64),
                "user": np.full(MAX_CHANNELS, -1, dtype=np.int16),
                "faders": np.zeros(MAX_CHANNELS, dtype=np.float64),
            }
        )
        # DMX values
        self.frame = [np.zeros(512, dtype=np.uint8) for _ in self.patch.universes]
        self._old_frame = [np.zeros(512, dtype=np.uint8) for _ in self.patch.universes]
        self._old_channel_levels = np.zeros(MAX_CHANNELS, dtype=np.uint8)
        self._old_user_mask = np.zeros(MAX_CHANNELS, dtype=bool)
        # To test outputs
        self.user_outputs = {}
        # Callbacks for UI updates
        self.output_callbacks = []
        # Callbacks for notifications
        self.notification_callbacks = []
        # Thread to send DMX every DMX_INTERVAL ms
        self.thread = RepeatedTimer(DMX_INTERVAL / 1000, self.send)

    def add_universe(self, universe: int) -> None:
        """Add a universe frame to Dmx."""
        index = self.patch.universes.index(universe)
        self.frame.insert(index, np.zeros(512, dtype=np.uint8))
        self._old_frame.insert(index, np.zeros(512, dtype=np.uint8))

    def remove_universe(self, universe: int, index: int | None = None) -> None:
        """Remove a universe frame from Dmx."""
        to_del = [key for key in self.user_outputs if key[1] == universe]
        for key in to_del:
            del self.user_outputs[key]
        if index is None:
            if universe in self.patch.universes:
                index = self.patch.universes.index(universe)
        if index is not None and 0 <= index < len(self.frame):
            self.frame.pop(index)
            self._old_frame.pop(index)

    def get_composite_level(self, channel_idx: int) -> tuple[int, dict[str, float]]:
        """Get the composite level and state color for a channel (0-indexed).

        Args:
            channel_idx: Channel index (0 to MAX_CHANNELS - 1)

        Returns:
            Tuple of (composite_level, color_dict)
        """
        park_mgr = getattr(self.lightshow, "park", None)
        if isinstance(park_mgr, ParkManager) and park_mgr.is_channel_parked(
            channel_idx + 1
        ):
            parked_val = park_mgr.get_channel_park_level(channel_idx + 1)
            if parked_val is not None:
                return int(parked_val), {"red": 1.0, "green": 0.7, "blue": 0.0}

        main_pb = self.lightshow.main_playback
        state, _ = classify_channel_tracking_state(
            main_pb, getattr(main_pb, "position", 0), channel_idx + 1
        )
        color_level = get_tracking_color(state)
        level = self.levels["sequence"][channel_idx]
        if self.levels["user"][channel_idx] != -1:
            level = self.levels["user"][channel_idx]
            color_level = get_tracking_color(TrackingDisplayState.MANUAL)
        else:
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
        park_mgr = getattr(self.lightshow, "park", None)
        if isinstance(park_mgr, ParkManager) and park_mgr.parked_channels:
            for ch, lvl in park_mgr.parked_channels.items():
                if 1 <= ch <= len(composite):
                    composite[ch - 1] = lvl
        return composite

    @property
    def effective_intensity_mult(self) -> float:
        """Effective intensity scaling factor combining Main Fader and Blackout."""
        return 0.0 if self.blackout else self.main_fader.value

    def _update_dynamic_devices(self, composite: np.ndarray) -> None:
        """Update dynamic intensity devices (Virtual Dimmer, 16/24-bit dimmers)."""
        if not hasattr(self.patch, "dynamic_intensity_devices"):
            return
        main_val = self.effective_intensity_mult
        park_mgr = getattr(self.lightshow, "park", None)
        for dev in self.patch.dynamic_intensity_devices:
            dev_id = dev.fixture_id
            if 1 <= dev_id <= len(composite):
                if isinstance(park_mgr, ParkManager) and park_mgr.is_channel_parked(
                    dev_id
                ):
                    parked_val = park_mgr.get_channel_park_level(dev_id) or 0
                    target_norm = float(parked_val) / 255.0
                    dev._target_intensity = target_norm
                    dev.set_intensity(target_norm)
                    continue
                user_val = self.levels["user"][dev_id - 1]
                comp_val = composite[dev_id - 1]
                if user_val != -1:
                    target_norm = float(user_val) / 255.0
                elif comp_val > 0:
                    target_norm = float(comp_val) / 255.0
                else:
                    curr_int = (
                        dev._target_intensity
                        if dev._target_intensity is not None
                        else dev.intensity
                    )
                    target_norm = float(curr_int)
                dev._target_intensity = target_norm
                dev.set_intensity(target_norm * main_val)

    def set_levels(self) -> None:
        """Set DMX frame levels"""
        composite = self.get_all_composite_levels()

        self.patch.update_numpy_cache_if_dirty()

        self._update_dynamic_devices(composite)

        # Extract levels for each patched output slot
        out_levels = composite[self.patch.map_src_channels].astype(np.float64)

        # Apply curves by block with continuous normalized evaluation
        unique_curves = np.unique(self.patch.map_dst_curves)
        for curve_numb in unique_curves:
            if curve_numb != 0:
                curve = self.lightshow.curves.get_curve(curve_numb)
                if curve:
                    curve_mask = self.patch.map_dst_curves == curve_numb
                    try:
                        norm_in = out_levels[curve_mask] / 255.0
                        out_levels[curve_mask] = (
                            curve.evaluate_normalized(norm_in) * 255.0
                        )
                    except NotImplementedError:
                        out_levels[curve_mask] = curve.values_array[
                            out_levels[curve_mask].astype(np.uint8)
                        ]

        # Scale by Main Fader and Blackout (unless channel is parked)
        intensity_mult = self.effective_intensity_mult
        park_mgr = getattr(self.lightshow, "park", None)
        if isinstance(park_mgr, ParkManager) and park_mgr.parked_channels:
            parked_indices = np.array(
                [ch - 1 for ch in park_mgr.parked_channels], dtype=int
            )
            is_parked_slot = np.isin(self.patch.map_src_channels, parked_indices)
            scaled = np.round(out_levels * intensity_mult)
            scaled[is_parked_slot] = np.round(out_levels[is_parked_slot])
            out_levels = scaled.astype(np.uint8)
        else:
            out_levels = np.round(out_levels * intensity_mult).astype(np.uint8)

        # Distribute levels to self.frame using advanced indexing
        map_dst_univ = self.patch.map_dst_universes
        map_dst_out = self.patch.map_dst_outputs
        for index in range(len(self.patch.universes)):
            if len(map_dst_univ) != len(map_dst_out) or len(map_dst_univ) != len(
                out_levels
            ):
                break
            univ_mask = map_dst_univ == index
            if np.any(univ_mask) and index < len(self.frame):
                self.frame[index][map_dst_out[univ_mask]] = out_levels[univ_mask]

        # Distribute multi-parameter device channels (Pan, Tilt, Color, Gobo...)
        if (
            hasattr(self.patch, "device_channel_refs")
            and self.patch.device_channel_refs
        ):
            dev_vals = np.fromiter(
                (ch.value for _, ch in self.patch.device_channel_refs),
                dtype=np.float64,
                count=len(self.patch.device_channel_refs),
            )
            # Scale HTP channels by Main Fader and Blackout, leaving LTP untouched
            if hasattr(self.patch, "map_dev_is_htp") and np.any(
                self.patch.map_dev_is_htp
            ):
                htp_mask = self.patch.map_dev_is_htp
                dev_vals[htp_mask] = np.round(dev_vals[htp_mask] * intensity_mult)

            dev_vals_u8 = dev_vals.astype(np.uint8)
            for index in range(len(self.patch.universes)):
                univ_mask = self.patch.map_dev_dst_universes == index
                if np.any(univ_mask) and index < len(self.frame):
                    self.frame[index][self.patch.map_dev_dst_outputs[univ_mask]] = (
                        dev_vals_u8[univ_mask]
                    )

        # Override physical DMX output addresses that are parked
        if isinstance(park_mgr, ParkManager) and park_mgr.parked_addresses:
            for (univ, out), level in park_mgr.parked_addresses.items():
                if univ in self.patch.universes:
                    u_idx = self.patch.universes.index(univ)
                    if u_idx < len(self.frame) and 1 <= out <= 512:
                        self.frame[u_idx][out - 1] = level

    def send(self) -> None:
        """Send DMX values to CoreEngine"""
        if self.lightshow.app is not None and self.lightshow.app.engine is not None:
            engine = self.lightshow.app.engine
            for index, universe in enumerate(self.patch.universes):
                if index >= len(self.frame) or index >= len(self._old_frame):
                    break
                current_frame = self.frame[index]
                old_frame = self._old_frame[index]
                if not np.array_equal(current_frame, old_frame):
                    changed_outputs = np.where(current_frame != old_frame)[0].tolist()
                    if changed_outputs:
                        GLib.idle_add(
                            self.trigger_output_callbacks, universe, changed_outputs
                        )
                    np.copyto(self._old_frame[index], current_frame)
                univ_slot = engine.universe(universe)
                if univ_slot is not None:
                    univ_slot.apply_array(current_frame)

            # Compute composite levels for all channels to check for modifications
            self.patch.update_numpy_cache_if_dirty()

            composite = self.get_all_composite_levels()
            scaled = composite * self.effective_intensity_mult
            park_mgr = getattr(self.lightshow, "park", None)
            if isinstance(park_mgr, ParkManager) and park_mgr.parked_channels:
                for ch, lvl in park_mgr.parked_channels.items():
                    if 1 <= ch <= len(scaled):
                        scaled[ch - 1] = lvl
            current_display_levels = np.round(scaled).astype(np.uint8)

            user_levels = self.levels.get("user")
            if user_levels is not None:
                user_mask = user_levels != -1
            else:
                user_mask = np.zeros(MAX_CHANNELS, dtype=bool)
            user_changed = user_mask != self._old_user_mask

            changed_indices = np.where(
                (current_display_levels != self._old_channel_levels) | user_changed
            )[0]

            if len(changed_indices) > 0:
                self._old_channel_levels[changed_indices] = current_display_levels[
                    changed_indices
                ]
                self._old_user_mask[changed_indices] = user_mask[changed_indices]
                changed_channels = (changed_indices + 1).tolist()
                GLib.idle_add(self.trigger_channels_update, changed_channels)

    def trigger_channels_update(self, changed_channels: list[int]) -> None:
        """Trigger channel widgets updates on the main thread."""
        app_any = typing.cast(typing.Any, self.lightshow.app)
        if app_any is not None and app_any.window is not None:
            live_view = app_any.window.live_view
            main_pb = self.lightshow.main_playback
            for channel in changed_channels:
                _, seq_level = classify_channel_tracking_state(
                    main_pb, main_pb.position, channel
                )
                seq_next_level = main_pb.get_next_channel_level(channel, seq_level)
                live_view.update_channel_widget(channel, seq_next_level)

    def all_outputs_at_zero(self) -> None:
        """All DMX outputs to 0"""
        for index, universe in enumerate(self.patch.universes):
            if index < len(self.frame):
                self.frame[index].fill(0)
            if self.lightshow.app is not None and self.lightshow.app.engine is not None:
                univ_slot = self.lightshow.app.engine.universe(universe)
                if univ_slot is not None:
                    univ_slot.blackout()

    def send_user_output(self, output: int, universe: int, level: int) -> None:
        """Send level to an output

        Args:
            output: Output number (1-512)
            universe: Universe number (one in patch.universes)
            level: Output level (0-255)
        """
        self.user_outputs[(output, universe)] = level
        if universe in self.patch.universes:
            index = self.patch.universes.index(universe)
            if index < len(self.frame):
                self.frame[index][output - 1] = level
        if not level:
            self.user_outputs.pop((output, universe), None)
        if self.lightshow.app is not None and self.lightshow.app.engine is not None:
            univ_slot = self.lightshow.app.engine.universe(universe)
            if univ_slot is not None:
                univ_slot.array[output - 1] = level

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
