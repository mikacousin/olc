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

import colorsys
import typing

from olc.controllers.osc.parser import parse_osc_normalized
from olc.controllers.osc.transport import make_method
from olc.devices.color_pick import KELVIN_MAX, KELVIN_MIN, kelvin_to_srgb
from olc.devices.device import COLOR_CHANNEL_TYPES, ChannelType

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class DevicesRoutesMixin:
    """OSC routes for encoder wheels, selected fixtures, and per-device parameters."""

    if typing.TYPE_CHECKING:
        app: CoreApplication

        def _execute_action(
            self, name: str, *args: object, **kwargs: object
        ) -> object: ...
        def _is_momentary_press(self, args: list) -> bool: ...

    @make_method("/olc/wheel/intensity")
    def _wheel_intensity(self, _address: str, args: list) -> None:
        """Adjust selected channels level relatively with encoder wheel."""
        delta = float(args[0]) if args else 1.0
        step = round(abs(delta))
        direction = 1 if delta >= 0 else -1
        self._execute_action("channel.wheel_adjust", step, direction)

    @make_method("/olc/wheel/pan")
    def _wheel_pan(self, _address: str, args: list) -> None:
        """Adjust selected fixtures pan relatively in degrees."""
        delta = float(args[0]) if args else 1.0
        self._execute_action("device.adjust_pan_tilt", delta, 0.0)

    @make_method("/olc/wheel/tilt")
    def _wheel_tilt(self, _address: str, args: list) -> None:
        """Adjust selected fixtures tilt relatively in degrees."""
        delta = float(args[0]) if args else 1.0
        self._execute_action("device.adjust_pan_tilt", 0.0, delta)

    @make_method("/olc/wheel/zoom")
    def _wheel_zoom(self, _address: str, args: list) -> None:
        """Adjust selected fixtures zoom relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "zoom", delta)

    @make_method("/olc/wheel/focus")
    def _wheel_focus(self, _address: str, args: list) -> None:
        """Adjust selected fixtures focus relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "focus", delta)

    @make_method("/olc/wheel/iris")
    def _wheel_iris(self, _address: str, args: list) -> None:
        """Adjust selected fixtures iris relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "iris", delta)

    @make_method("/olc/wheel/strobe")
    def _wheel_strobe(self, _address: str, args: list) -> None:
        """Adjust selected fixtures strobe relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "strobe", delta)

    @make_method("/olc/wheel/frost")
    def _wheel_frost(self, _address: str, args: list) -> None:
        """Adjust selected fixtures frost filter relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "frost", delta)

    @make_method("/olc/wheel/gobo")
    def _wheel_gobo(self, _address: str, args: list) -> None:
        """Adjust selected fixtures gobo wheel relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "gobo_wheel", delta)

    @make_method("/olc/wheel/prism")
    def _wheel_prism(self, _address: str, args: list) -> None:
        """Adjust selected fixtures prism relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "prism", delta)

    @make_method("/olc/wheel/cct")
    @make_method("/olc/wheel/kelvin")
    def _wheel_kelvin(self, _address: str, args: list) -> None:
        """Adjust selected fixtures color temperature relatively."""
        delta = float(args[0]) if args else 0.05
        self._execute_action("device.adjust_parameter", "color_temp", delta)

    @make_method("/olc/wheel/param/*")
    def _wheel_param_generic(self, address: str, args: list) -> None:
        """Adjust selected fixtures generic parameter relatively."""
        parts = address.split("/")
        if len(parts) >= 5:
            param_name = parts[4]
            delta = float(args[0]) if args else 0.05
            self._execute_action("device.adjust_parameter", param_name, delta)

    @make_method("/olc/selected/intensity")
    def _selected_intensity(self, _address: str, args: list) -> None:
        """Set normalized intensity [0.0..1.0] on all selected channels."""
        if not args:
            return
        norm_level = parse_osc_normalized(args[0])
        for ch in list(getattr(self.app, "selected_channels", [])):
            self._execute_action("channel.set_level", ch, norm_level)

    @make_method("/olc/selected/pan")
    def _selected_pan(self, _address: str, args: list) -> None:
        """Set absolute pan coordinate in degrees on selected fixtures."""
        if args:
            val = float(args[0])
            self._execute_action("device.set_pan_tilt", val, None)

    @make_method("/olc/selected/pan/norm")
    def _selected_pan_norm(self, _address: str, args: list) -> None:
        """Set normalized pan [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "pan", norm)

    @make_method("/olc/selected/tilt")
    def _selected_tilt(self, _address: str, args: list) -> None:
        """Set absolute tilt coordinate in degrees on selected fixtures."""
        if args:
            val = float(args[0])
            self._execute_action("device.set_pan_tilt", None, val)

    @make_method("/olc/selected/tilt/norm")
    def _selected_tilt_norm(self, _address: str, args: list) -> None:
        """Set normalized tilt [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "tilt", norm)

    def _get_selected_srgb(self) -> tuple[float, float, float]:
        """Return current (r, g, b) of the last selected fixture or (1, 1, 1)."""
        selected = getattr(self.app, "selected_channels", [])
        patch = getattr(self.app.lightshow, "patch", None)
        if selected and patch is not None:
            dev = patch.devices.get(selected[-1])
            if dev is not None:
                srgb = getattr(dev, "color_srgb", None)
                if srgb is not None:
                    return (float(srgb.r), float(srgb.g), float(srgb.b))
        return (1.0, 1.0, 1.0)

    @make_method("/olc/selected/color/rgb")
    def _selected_color_rgb(self, _address: str, args: list) -> None:
        """Set RGB color on selected fixtures."""
        if len(args) >= 3:
            r = float(args[0])
            g = float(args[1])
            b = float(args[2])
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/color/r")
    def _selected_color_r(self, _address: str, args: list) -> None:
        """Set red component [0.0..1.0] on selected fixtures."""
        if args:
            _, g, b = self._get_selected_srgb()
            r = parse_osc_normalized(args[0])
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/color/g")
    def _selected_color_g(self, _address: str, args: list) -> None:
        """Set green component [0.0..1.0] on selected fixtures."""
        if args:
            r, _, b = self._get_selected_srgb()
            g = parse_osc_normalized(args[0])
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/color/b")
    def _selected_color_b(self, _address: str, args: list) -> None:
        """Set blue component [0.0..1.0] on selected fixtures."""
        if args:
            r, g, _ = self._get_selected_srgb()
            b = parse_osc_normalized(args[0])
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/color/hue")
    def _selected_color_hue(self, _address: str, args: list) -> None:
        """Set hue component [0.0..1.0] on selected fixtures."""
        if args:
            r, g, b = self._get_selected_srgb()
            _, s, v = colorsys.rgb_to_hsv(r, g, b)
            if v < 0.01:
                v = 1.0
            if s < 0.01:
                s = 1.0
            h = parse_osc_normalized(args[0])
            nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
            self._execute_action("device.set_color", nr, ng, nb)

    @make_method("/olc/selected/color/sat")
    def _selected_color_sat(self, _address: str, args: list) -> None:
        """Set saturation component [0.0..1.0] on selected fixtures."""
        if args:
            r, g, b = self._get_selected_srgb()
            h, _, v = colorsys.rgb_to_hsv(r, g, b)
            if v < 0.01:
                v = 1.0
            s = parse_osc_normalized(args[0])
            nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
            self._execute_action("device.set_color", nr, ng, nb)

    @make_method("/olc/selected/color/hsv")
    def _selected_color_hsv(self, _address: str, args: list) -> None:
        """Set HSV color on selected fixtures (converts to RGB)."""
        if len(args) >= 2:
            h = float(args[0])
            s = float(args[1])
            v = float(args[2]) if len(args) >= 3 else 1.0
            if h > 1.0:
                h = h / 360.0
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            self._execute_action("device.set_color", r, g, b)

    @make_method("/olc/selected/zoom")
    def _selected_zoom(self, _address: str, args: list) -> None:
        """Set normalized zoom [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "zoom", norm)

    @make_method("/olc/selected/zoom/degrees")
    def _selected_zoom_degrees(self, _address: str, args: list) -> None:
        """Set physical zoom angle in degrees on selected fixtures."""
        if args:
            deg = float(args[0])
            self._execute_action("device.set_parameter", "zoom", deg, is_physical=True)

    @make_method("/olc/selected/focus")
    def _selected_focus(self, _address: str, args: list) -> None:
        """Set normalized focus [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "focus", norm)

    @make_method("/olc/selected/focus/meters")
    def _selected_focus_meters(self, _address: str, args: list) -> None:
        """Set physical focus distance in meters on selected fixtures."""
        if args:
            dist = float(args[0])
            self._execute_action(
                "device.set_parameter", "focus", dist, is_physical=True
            )

    @make_method("/olc/selected/iris")
    def _selected_iris(self, _address: str, args: list) -> None:
        """Set normalized iris aperture [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "iris", norm)

    @make_method("/olc/selected/strobe")
    def _selected_strobe(self, _address: str, args: list) -> None:
        """Set normalized strobe frequency [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "strobe", norm)

    @make_method("/olc/selected/strobe/hz")
    def _selected_strobe_hz(self, _address: str, args: list) -> None:
        """Set physical strobe frequency in Hz on selected fixtures."""
        if args:
            freq = float(args[0])
            self._execute_action(
                "device.set_parameter", "strobe", freq, is_physical=True
            )

    @make_method("/olc/selected/frost")
    def _selected_frost(self, _address: str, args: list) -> None:
        """Set normalized frost filter [0.0..1.0] on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "frost", norm)

    @make_method("/olc/selected/gobo")
    def _selected_gobo(self, _address: str, args: list) -> None:
        """Set gobo wheel normalized position or index on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "gobo_wheel", norm)

    @make_method("/olc/selected/prism")
    def _selected_prism(self, _address: str, args: list) -> None:
        """Set prism normalized level or insertion on selected fixtures."""
        if args:
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", "prism", norm)

    def _apply_kelvin_to_selected(self, k: float) -> None:
        """Apply Kelvin value (normalized 0..1 or physical K) to selected fixtures."""
        if 0.0 <= k <= 1.0:
            self._execute_action("device.set_parameter", "color_temp", k)
            kelvin_val = KELVIN_MIN + k * (KELVIN_MAX - KELVIN_MIN)
        else:
            self._execute_action(
                "device.set_parameter", "color_temp", k, is_physical=True
            )
            kelvin_val = k

        patch = self.app.lightshow.patch
        color_only_ids: list[int] = []
        for ch_id in self.app.selected_channels:
            dev = patch.devices.get(ch_id)
            if dev is None:
                continue
            if dev.get_channel(ChannelType.COLOR_TEMP) is None and any(
                dev.get_channel(ct) is not None for ct in COLOR_CHANNEL_TYPES
            ):
                color_only_ids.append(ch_id)
        if color_only_ids:
            r, g, b = kelvin_to_srgb(kelvin_val)
            self._execute_action("device.set_color", r, g, b, channels=color_only_ids)

    @make_method("/olc/selected/color/kelvin")
    @make_method("/olc/selected/cct")
    def _selected_color_kelvin(self, _address: str, args: list) -> None:
        """Set color temperature in Kelvin on selected fixtures."""
        if args:
            self._apply_kelvin_to_selected(float(args[0]))

    @make_method("/olc/selected/color/kelvin/*")
    def _selected_color_kelvin_preset(self, address: str, args: list) -> None:
        """Set color temperature preset in Kelvin."""
        if not self._is_momentary_press(args):
            return
        parts = address.split("/")
        if len(parts) >= 6:
            try:
                k = float(parts[5])
                self._apply_kelvin_to_selected(k)
            except ValueError:
                pass

    @make_method("/olc/selected/param/*")
    def _selected_param_generic(self, address: str, args: list) -> None:
        """Set generic normalized parameter on selected fixtures."""
        if not args:
            return
        parts = address.split("/")
        if len(parts) >= 5:
            param_name = parts[4]
            norm = parse_osc_normalized(args[0])
            self._execute_action("device.set_parameter", param_name, norm)

    @make_method("/olc/device/*/zoom")
    def _device_zoom(self, address: str, args: list) -> None:
        """Set normalized zoom for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "zoom", norm, channels=[ch])

    @make_method("/olc/device/*/focus")
    def _device_focus(self, address: str, args: list) -> None:
        """Set normalized focus for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "focus", norm, channels=[ch])

    @make_method("/olc/device/*/iris")
    def _device_iris(self, address: str, args: list) -> None:
        """Set normalized iris for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "iris", norm, channels=[ch])

    @make_method("/olc/device/*/strobe")
    def _device_strobe(self, address: str, args: list) -> None:
        """Set normalized strobe for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "strobe", norm, channels=[ch])

    @make_method("/olc/device/*/frost")
    def _device_frost(self, address: str, args: list) -> None:
        """Set normalized frost for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "frost", norm, channels=[ch])

    @make_method("/olc/device/*/gobo")
    def _device_gobo(self, address: str, args: list) -> None:
        """Set normalized gobo for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "gobo_wheel", norm, channels=[ch])

    @make_method("/olc/device/*/prism")
    def _device_prism(self, address: str, args: list) -> None:
        """Set normalized prism for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", "prism", norm, channels=[ch])

    @make_method("/olc/device/*/pan")
    def _device_pan(self, address: str, args: list) -> None:
        """Set absolute pan coordinate in degrees for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        val = float(args[0])
        self._execute_action("device.set_pan_tilt", val, None, channels=[ch])

    @make_method("/olc/device/*/tilt")
    def _device_tilt(self, address: str, args: list) -> None:
        """Set absolute tilt coordinate in degrees for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        val = float(args[0])
        self._execute_action("device.set_pan_tilt", None, val, channels=[ch])

    @make_method("/olc/device/*/color/rgb")
    def _device_color_rgb(self, address: str, args: list) -> None:
        """Set RGB color for a specific device."""
        if len(args) < 3:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
        except (IndexError, ValueError):
            return
        r = float(args[0])
        g = float(args[1])
        b = float(args[2])
        self._execute_action("device.set_color", r, g, b, channels=[ch])

    @make_method("/olc/device/*/param/*")
    def _device_param_generic(self, address: str, args: list) -> None:
        """Set generic normalized parameter for a specific device."""
        if not args:
            return
        parts = address.split("/")
        try:
            ch = int(parts[3])
            param_name = parts[5]
        except (IndexError, ValueError):
            return
        norm = parse_osc_normalized(args[0])
        self._execute_action("device.set_parameter", param_name, norm, channels=[ch])

    @make_method("/olc/selected/home")
    def _selected_home(self, _address: str, args: list) -> None:
        """Reset selected fixtures to default Home values (intensity unchanged)."""
        if args and float(args[0]) == 0.0:
            return
        self._execute_action("device.home")

    @make_method("/olc/selected/locate")
    def _selected_locate(self, _address: str, args: list) -> None:
        """Locate selected fixtures to Home with full intensity."""
        if args and float(args[0]) == 0.0:
            return
        self._execute_action("device.locate")

    @make_method("/olc/device/*/home")
    def _device_home(self, address: str, args: list) -> None:
        """Reset specific fixture to default Home values."""
        if args and float(args[0]) == 0.0:
            return
        parts = address.split("/")
        try:
            dev_id = int(parts[3])
        except (IndexError, ValueError):
            return
        self._execute_action("device.home", channels=[dev_id])

    @make_method("/olc/device/*/locate")
    def _device_locate(self, address: str, args: list) -> None:
        """Locate specific fixture with full intensity."""
        if args and float(args[0]) == 0.0:
            return
        parts = address.split("/")
        try:
            dev_id = int(parts[3])
        except (IndexError, ValueError):
            return
        self._execute_action("device.locate", channels=[dev_id])
