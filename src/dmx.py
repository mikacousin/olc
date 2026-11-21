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

import threading
import typing
from typing import Optional

import numpy as np

from olc.core.tracking import (
    TrackingDisplayState,
    classify_channel_tracking_state,
    get_tracking_color,
)
from olc.define import MAX_CHANNELS
from olc.show.main_fader import MainFader
from olc.show.park import ParkManager
from olc.show.patch import PatchManager

if typing.TYPE_CHECKING:
    from olc.core.dmx_backend import DMXBackend
    from olc.show.lightshow import LightShow


class DmxLevels(dict):
    """Custom dictionary to automatically convert list values to NumPy arrays."""

    def __setitem__(self, key: str, value: object) -> None:
        if isinstance(value, list):
            super().__setitem__(key, np.array(value, dtype=np.float64))
        else:
            super().__setitem__(key, value)


# pylint: disable=too-many-instance-attributes
class Dmx:
    """Send levels to backend"""

    backend: Optional[DMXBackend]
    patch: PatchManager
    main_fader: MainFader
    blackout: bool
    levels: DmxLevels
    frame: list[np.ndarray]
    external_dmx: dict[int, np.ndarray]
    user_outputs: dict[tuple[int, int], int]

    def __init__(self, backend: Optional[DMXBackend], lightshow: LightShow) -> None:
        self._lock = threading.RLock()
        self.backend = backend
        self.lightshow = lightshow
        self.patch = self.lightshow.patch
        self.main_fader = MainFader()
        self.blackout = False
        # Normalized channel levels [0.0..1.0] (user uses -1.0 as unset sentinel)
        self.levels = DmxLevels(
            {
                "sequence": np.zeros(MAX_CHANNELS, dtype=np.float64),
                "user": np.full(MAX_CHANNELS, -1.0, dtype=np.float64),
                "faders": np.zeros(MAX_CHANNELS, dtype=np.float64),
                "faders_gm_exempt": np.zeros(MAX_CHANNELS, dtype=np.float64),
            }
        )
        # DMX values
        self.frame = [np.zeros(512, dtype=np.uint8) for _ in self.patch.universes]
        self._old_frame = [np.zeros(512, dtype=np.uint8) for _ in self.patch.universes]
        self._old_channel_levels = np.zeros(MAX_CHANNELS, dtype=np.uint16)
        self._old_user_mask = np.zeros(MAX_CHANNELS, dtype=bool)
        self._old_device_colors: dict[int, tuple[int, int, int]] = {}
        self.external_dmx = {}
        # To test outputs
        self.user_outputs = {}
        # Wire patch callbacks cleanly
        self.patch.on_patch_empty_cb = self.all_outputs_at_zero
        self.patch.on_unpatch_cb = self._on_unpatch_output

    def stop(self) -> None:
        """Stop DMX resources (no background timer thread to join)."""

    def _on_unpatch_output(self, index: int, output: int) -> None:
        """Zero the DMX output slot in frame when unpatched."""
        with self._lock:
            if 0 <= index < len(self.frame) and 0 <= output < 512:
                self.frame[index][output] = 0

    def add_universe(self, universe: int) -> None:
        """Add a universe frame to Dmx."""
        with self._lock:
            index = self.patch.universes.index(universe)
            self.frame.insert(index, np.zeros(512, dtype=np.uint8))
            self._old_frame.insert(index, np.zeros(512, dtype=np.uint8))

    def remove_universe(self, universe: int, index: int | None = None) -> None:
        """Remove a universe frame from Dmx."""
        with self._lock:
            self.external_dmx.pop(universe, None)
            to_del = [key for key in self.user_outputs if key[1] == universe]
            for key in to_del:
                del self.user_outputs[key]
            if index is None:
                if universe in self.patch.universes:
                    index = self.patch.universes.index(universe)
            if index is not None and 0 <= index < len(self.frame):
                self.frame.pop(index)
                self._old_frame.pop(index)

    def get_composite_level(self, channel_idx: int) -> tuple[float, dict[str, float]]:
        """Get the normalized composite level [0.0..1.0] and state color for a channel.

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
                return float(parked_val), {"red": 1.0, "green": 0.7, "blue": 0.0}

        main_pb = self.lightshow.main_playback
        state, _ = classify_channel_tracking_state(
            main_pb, getattr(main_pb, "position", 0), channel_idx + 1
        )
        color_level = get_tracking_color(state)
        level = float(self.levels["sequence"][channel_idx])
        if self.levels["user"][channel_idx] >= 0.0:
            level = float(self.levels["user"][channel_idx])
            color_level = get_tracking_color(TrackingDisplayState.MANUAL)
        else:
            fader_lvl = float(self.levels["faders"][channel_idx])
            if "faders_gm_exempt" in self.levels:
                fader_lvl = max(
                    fader_lvl, float(self.levels["faders_gm_exempt"][channel_idx])
                )
            if fader_lvl > level:
                level = fader_lvl
                color_level = {"red": 0.4, "green": 0.7, "blue": 0.4}
            if self.lightshow.independents.dmx[channel_idx] > level:
                level = float(self.lightshow.independents.dmx[channel_idx])
                color_level = {"red": 0.4, "green": 0.4, "blue": 0.7}
        app = getattr(self.lightshow, "app", None)
        eff_eng = getattr(app, "effects_engine", None)
        if (
            eff_eng is not None
            and getattr(eff_eng, "has_active_effects", False) is True
        ):
            level = eff_eng.apply_channel_intensity(channel_idx + 1, level)
        return level, color_level

    def get_all_composite_levels(self) -> np.ndarray:
        """Get normalized composite levels [0.0..1.0] for all channels simultaneously.

        Returns:
            Array of composite levels.
        """
        composite = self.levels["sequence"].copy()
        composite = np.maximum(composite, self.levels["faders"])
        if "faders_gm_exempt" in self.levels:
            composite = np.maximum(composite, self.levels["faders_gm_exempt"])
        composite = np.maximum(composite, self.lightshow.independents.dmx)
        user_mask = self.levels["user"] >= 0.0
        composite[user_mask] = self.levels["user"][user_mask]
        app = getattr(self.lightshow, "app", None)
        eff_eng = getattr(app, "effects_engine", None)
        if (
            eff_eng is not None
            and getattr(eff_eng, "has_active_effects", False) is True
        ):
            composite = eff_eng.apply_intensity_modulation(composite)
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
        app = getattr(self.lightshow, "app", None)
        eff_eng = getattr(app, "effects_engine", None)
        gm_exempt_arr = self.levels.get("faders_gm_exempt")
        for dev in self.patch.dynamic_intensity_devices:
            dev_id = dev.fixture_id
            if 1 <= dev_id <= len(composite):
                if isinstance(park_mgr, ParkManager) and park_mgr.is_channel_parked(
                    dev_id
                ):
                    parked_val = park_mgr.get_channel_park_level(dev_id) or 0.0
                    target_norm = float(parked_val)
                    dev._target_intensity = target_norm
                    dev.set_intensity(target_norm)
                    continue
                user_val = float(self.levels["user"][dev_id - 1])
                comp_val = float(composite[dev_id - 1])
                gm_lvl = (
                    float(gm_exempt_arr[dev_id - 1])
                    if gm_exempt_arr is not None and 1 <= dev_id <= len(gm_exempt_arr)
                    else 0.0
                )
                has_eff_int = bool(
                    eff_eng is not None
                    and getattr(eff_eng, "has_active_effects", False) is True
                    and eff_eng.is_channel_intensity_modulated(dev_id)
                )
                if has_eff_int or user_val >= 0.0 or comp_val > 0.0:
                    target_norm = comp_val
                else:
                    curr_int = (
                        dev._target_intensity
                        if dev._target_intensity is not None
                        else dev.intensity
                    )
                    target_norm = float(curr_int)
                dev._target_intensity = target_norm
                dev.set_intensity(max(target_norm * main_val, gm_lvl))

    def on_dmx_received(self, universe: int, data: list[int] | np.ndarray) -> None:
        """Store incoming external DMX-In frame, re-merge HTP, and emit event."""
        arr = np.zeros(512, dtype=np.uint8)
        raw = np.asarray(data[:512], dtype=np.uint8)
        arr[: len(raw)] = raw
        with self._lock:
            self.external_dmx[universe] = arr
        self.set_levels()
        if self.lightshow.app is not None:
            self.lightshow.app.emit("dmx.input_received", universe, arr.copy())

    def _apply_output_curves(self, out_levels: np.ndarray) -> np.ndarray:
        """Apply transfer curves across mapped output slots."""
        result = out_levels.copy()
        unique_curves = np.unique(self.patch.map_dst_curves)
        for curve_numb in unique_curves:
            if curve_numb != 0:
                curve = self.lightshow.curves.get_curve(curve_numb)
                if curve:
                    curve_mask = self.patch.map_dst_curves == curve_numb
                    try:
                        result[curve_mask] = curve.evaluate_normalized(
                            result[curve_mask]
                        )
                    except NotImplementedError:
                        result[curve_mask] = (
                            curve.values_array[
                                np.round(
                                    np.clip(result[curve_mask], 0.0, 1.0) * 255.0
                                ).astype(np.uint8)
                            ]
                            / 255.0
                        )
        return result

    def set_levels(self) -> None:
        """Set DMX frame levels and push updated frames to CoreEngine."""
        with self._lock:
            composite = self.get_all_composite_levels()

            self.patch.update_numpy_cache_if_dirty()

            self._update_dynamic_devices(composite)

            for index, univ in enumerate(self.patch.universes):
                if index < len(self.frame) and univ in self.external_dmx:
                    np.copyto(self.frame[index], self.external_dmx[univ])

            # Extract levels for each patched output slot
            out_levels = composite[self.patch.map_src_channels].astype(np.float64)
            out_levels = self._apply_output_curves(out_levels)

            # Scale by Main Fader and Blackout unless GM-exempt or parked
            intensity_mult = self.effective_intensity_mult
            park_mgr = getattr(self.lightshow, "park", None)
            scaled = out_levels * intensity_mult
            gm_exempt_arr = self.levels.get("faders_gm_exempt")
            if gm_exempt_arr is not None and np.any(gm_exempt_arr > 0.0):
                gm_out = gm_exempt_arr[self.patch.map_src_channels].astype(np.float64)
                gm_out = self._apply_output_curves(gm_out)
                scaled = np.maximum(scaled, gm_out)
            if isinstance(park_mgr, ParkManager) and park_mgr.parked_channels:
                parked_indices = np.array(
                    [ch - 1 for ch in park_mgr.parked_channels], dtype=int
                )
                is_parked_slot = np.isin(self.patch.map_src_channels, parked_indices)
                scaled[is_parked_slot] = out_levels[is_parked_slot]
            out_levels_u8 = np.round(np.clip(scaled, 0.0, 1.0) * 255.0).astype(np.uint8)

            # Distribute levels to self.frame using advanced indexing
            map_dst_univ = self.patch.map_dst_universes
            map_dst_out = self.patch.map_dst_outputs
            for index in range(len(self.patch.universes)):
                if len(map_dst_univ) != len(map_dst_out) or len(map_dst_univ) != len(
                    out_levels_u8
                ):
                    break
                univ_mask = map_dst_univ == index
                if np.any(univ_mask) and index < len(self.frame):
                    dst = map_dst_out[univ_mask]
                    if self.patch.universes[index] in self.external_dmx:
                        self.frame[index][dst] = np.maximum(
                            self.frame[index][dst], out_levels_u8[univ_mask]
                        )
                    else:
                        self.frame[index][dst] = out_levels_u8[univ_mask]

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
                        dst = self.patch.map_dev_dst_outputs[univ_mask]
                        if self.patch.universes[index] in self.external_dmx:
                            self.frame[index][dst] = np.maximum(
                                self.frame[index][dst], dev_vals_u8[univ_mask]
                            )
                        else:
                            self.frame[index][dst] = dev_vals_u8[univ_mask]

            for (out, univ), level in self.user_outputs.items():
                if univ in self.patch.universes and 1 <= out <= 512:
                    u_idx = self.patch.universes.index(univ)
                    if u_idx < len(self.frame):
                        self.frame[u_idx][out - 1] = level

            # Override physical DMX output addresses that are parked
            if isinstance(park_mgr, ParkManager) and park_mgr.parked_addresses:
                for (univ, out), level in park_mgr.parked_addresses.items():
                    if univ in self.patch.universes:
                        u_idx = self.patch.universes.index(univ)
                        if u_idx < len(self.frame) and 1 <= out <= 512:
                            self.frame[u_idx][out - 1] = level

        self.send()

    def send(self) -> None:
        """Send DMX values to CoreEngine and emit output/channel update events."""
        if self.lightshow.app is None:
            return
        engine = getattr(self.lightshow.app, "engine", None)
        outputs_to_emit: list[tuple[int, list[int]]] = []
        changed_channels: list[int] = []

        with self._lock:
            for index, universe in enumerate(self.patch.universes):
                if index >= len(self.frame) or index >= len(self._old_frame):
                    break
                current_frame = self.frame[index]
                old_frame = self._old_frame[index]
                if not np.array_equal(current_frame, old_frame):
                    changed_outputs = np.where(current_frame != old_frame)[0].tolist()
                    if changed_outputs:
                        outputs_to_emit.append((universe, changed_outputs))
                    np.copyto(self._old_frame[index], current_frame)
                if engine is not None:
                    try:
                        engine.apply_universe_frame(universe, current_frame)
                    except KeyError:
                        pass

            # Compute composite levels for all channels to check for modifications
            self.patch.update_numpy_cache_if_dirty()

            composite = self.get_all_composite_levels()
            scaled = composite * self.effective_intensity_mult
            park_mgr = getattr(self.lightshow, "park", None)
            if isinstance(park_mgr, ParkManager) and park_mgr.parked_channels:
                for ch, lvl in park_mgr.parked_channels.items():
                    if 1 <= ch <= len(scaled):
                        scaled[ch - 1] = lvl
            current_display_levels = np.round(
                np.clip(scaled, 0.0, 1.0) * 65535.0
            ).astype(np.uint16)

            user_levels = self.levels.get("user")
            if user_levels is not None:
                user_mask = user_levels >= 0.0
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

            devices = getattr(self.patch, "devices", None)
            if isinstance(devices, dict):
                color_changed_channels: list[int] = []
                stale_ids = [
                    dev_id
                    for dev_id in self._old_device_colors
                    if dev_id not in devices
                ]
                for stale_id in stale_ids:
                    self._old_device_colors.pop(stale_id, None)
                for dev_id, dev in devices.items():
                    preview_fn = getattr(dev, "get_preview_rgb", None)
                    if not callable(preview_fn):
                        continue
                    preview = preview_fn()
                    if preview is None:
                        continue
                    quant = (
                        round(max(0.0, min(1.0, float(preview[0]))) * 255.0),
                        round(max(0.0, min(1.0, float(preview[1]))) * 255.0),
                        round(max(0.0, min(1.0, float(preview[2]))) * 255.0),
                    )
                    prev_quant = self._old_device_colors.get(dev_id)
                    if prev_quant is None:
                        self._old_device_colors[dev_id] = quant
                        if quant != (255, 255, 255):
                            color_changed_channels.append(int(dev_id))
                    elif prev_quant != quant:
                        self._old_device_colors[dev_id] = quant
                        color_changed_channels.append(int(dev_id))
                if color_changed_channels:
                    changed_channels = sorted(
                        set(changed_channels) | set(color_changed_channels)
                    )

        for universe, changed_outputs in outputs_to_emit:
            self.trigger_output_callbacks(universe, changed_outputs)
        if changed_channels:
            self.trigger_channels_update(changed_channels)

    def trigger_channels_update(self, changed_channels: list[int]) -> None:
        """Emit channel updates via the CoreApplication event bus."""
        if self.lightshow.app is not None:
            self.lightshow.app.emit("channels.updated", changed_channels)

    def all_outputs_at_zero(self) -> None:
        """All DMX outputs to 0"""
        with self._lock:
            self.external_dmx.clear()
            for index, universe in enumerate(self.patch.universes):
                if index < len(self.frame):
                    self.frame[index].fill(0)
                if (
                    self.lightshow.app is not None
                    and self.lightshow.app.engine is not None
                ):
                    try:
                        self.lightshow.app.engine.blackout(universe)
                    except KeyError:
                        pass

    def send_user_output(self, output: int, universe: int, level: int) -> None:
        """Send level to an output

        Args:
            output: Output number (1-512)
            universe: Universe number (one in patch.universes)
            level: Output level (0-255)
        """
        with self._lock:
            self.user_outputs[(output, universe)] = level
            if universe in self.patch.universes:
                index = self.patch.universes.index(universe)
                if index < len(self.frame):
                    self.frame[index][output - 1] = level
            if not level:
                self.user_outputs.pop((output, universe), None)
            elif (
                self.lightshow.app is not None and self.lightshow.app.engine is not None
            ):
                try:
                    self.lightshow.app.engine.set_output_level(universe, output, level)
                except (KeyError, IndexError):
                    pass
        if not level:
            self.set_levels()

    def get_output_level(self, universe: int, output: int) -> int:
        """Return current DMX level (0-255) for 1-indexed *output* in *universe*."""
        if universe in self.patch.universes and 1 <= output <= 512:
            univ_idx = self.patch.universes.index(universe)
            if univ_idx < len(self.frame):
                return int(self.frame[univ_idx][output - 1])
        if self.lightshow.app is not None and self.lightshow.app.engine is not None:
            try:
                return self.lightshow.app.engine.get_output_level(universe, output)
            except (KeyError, IndexError):
                pass
        return 0

    def snapshot_universe(self, universe: int) -> np.ndarray:
        """Return a copy of the 512-byte DMX buffer for *universe*."""
        if self.lightshow.app is not None and self.lightshow.app.engine is not None:
            try:
                return self.lightshow.app.engine.snapshot_universe(universe)
            except KeyError:
                pass
        if universe in self.patch.universes:
            univ_idx = self.patch.universes.index(universe)
            if univ_idx < len(self.frame):
                return self.frame[univ_idx].copy()
        return np.zeros(512, dtype=np.uint8)

    def apply_universe_frame(self, universe: int, frame: np.ndarray) -> None:
        """Apply a 512-byte DMX buffer to *universe* in both frame and CoreEngine."""
        with self._lock:
            if universe in self.patch.universes:
                univ_idx = self.patch.universes.index(universe)
                if univ_idx < len(self.frame):
                    np.copyto(self.frame[univ_idx], frame, casting="unsafe")
            if self.lightshow.app is not None and self.lightshow.app.engine is not None:
                try:
                    self.lightshow.app.engine.apply_universe_frame(universe, frame)
                except KeyError:
                    pass

    def blackout_universe(self, universe: int) -> None:
        """Zero all 512 DMX outputs for *universe* in both frame and CoreEngine."""
        with self._lock:
            self.external_dmx.pop(universe, None)
            if universe in self.patch.universes:
                univ_idx = self.patch.universes.index(universe)
                if univ_idx < len(self.frame):
                    self.frame[univ_idx].fill(0)
            if self.lightshow.app is not None and self.lightshow.app.engine is not None:
                try:
                    self.lightshow.app.engine.blackout(universe)
                except KeyError:
                    pass

    def set_universe_levels(self, universe: int, channels: dict[int, int]) -> None:
        """Set multiple 0-indexed DMX outputs (0..511) in frame and CoreEngine."""
        with self._lock:
            if universe in self.patch.universes:
                univ_idx = self.patch.universes.index(universe)
                if univ_idx < len(self.frame):
                    frame = self.frame[univ_idx]
                    for ch, val in channels.items():
                        if 0 <= ch < 512:
                            frame[ch] = int(np.clip(val, 0, 255))
            if self.lightshow.app is not None and self.lightshow.app.engine is not None:
                try:
                    self.lightshow.app.engine.set_channels(universe, channels)
                except KeyError:
                    pass

    def reset_levels(self, *, reset_main_fader: bool = True) -> None:
        """Reset sequence/manual/fader levels and optionally main fader to 1.0."""
        self.levels["sequence"].fill(0.0)
        self.levels["user"].fill(-1.0)
        if "faders" in self.levels:
            self.levels["faders"].fill(0.0)
        if "faders_gm_exempt" in self.levels:
            self.levels["faders_gm_exempt"].fill(0.0)
        if reset_main_fader:
            self.main_fader.set_level(1.0)
        self.set_levels()

    def trigger_output_callbacks(self, universe: int, outputs: list[int]) -> None:
        """Emit dmx.outputs_changed event via CoreApplication event bus.

        Args:
            universe: Universe number
            outputs: List of changed output indices
        """
        if self.lightshow.app is not None:
            self.lightshow.app.emit("dmx.outputs_changed", universe, outputs)

    def trigger_notification(self, title: str, body: str) -> None:
        """Emit backend.notification event via CoreApplication event bus.

        Args:
            title: Notification title
            body: Notification body text
        """
        if self.lightshow.app is not None:
            self.lightshow.app.emit("backend.notification", title, body)
