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
"""Console-style color picker: HS disc, Kelvin slider, hex entry and presets.

All the color math and rate limiting lives in ``olc.devices.color_pick`` (no
GTK, unit tested). This module is only the drawing and the event plumbing.
"""

from __future__ import annotations

import math
import sys
from typing import Any, Callable, Optional

import cairo
from gi.repository import Gdk, GLib, Gtk

from olc.devices import color_pick as cp

DISC_SIZE = 160
SEND_INTERVAL_MS = 33  # ~30 Hz toward the devices while dragging

_MATCH_TEXT = {
    "exact": "exact",
    "close": "close",
    "approx": "approximate",
    "out": "out of gamut",
}
_MATCH_CSS_CLASS = {
    "exact": "olc-match-exact",
    "close": "olc-match-close",
    "approx": "olc-match-approx",
    "out": "olc-match-out",
}
_CSS = b"""
.olc-match-exact { color: #5fbf5f; }
.olc-match-close { color: #a8c85a; }
.olc-match-approx { color: #e0a030; }
.olc-match-out { color: #e05050; }
"""


class _Swatch(Gtk.Button):  # pylint: disable=too-few-public-methods
    """Small flat button filled with a color."""

    def __init__(
        self, name: str, rgb: cp.RGB, on_pick: Callable[[cp.RGB], None]
    ) -> None:
        super().__init__()
        self.rgb = rgb
        self.set_tooltip_text(name)
        self.set_relief(Gtk.ReliefStyle.NONE)
        area = Gtk.DrawingArea()
        area.set_size_request(22, 18)
        area.connect("draw", self._on_draw)
        self.add(area)
        self.connect("clicked", lambda _b: on_pick(self.rgb))

    def _on_draw(self, widget: Gtk.Widget, cr: cairo.Context) -> bool:
        alloc = widget.get_allocation()
        cr.rectangle(0, 0, alloc.width, alloc.height)
        cr.set_source_rgb(*self.rgb)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.35)
        cr.set_line_width(1.0)
        cr.stroke()
        return False


class HSDiscWidget(Gtk.DrawingArea):  # pylint: disable=too-many-instance-attributes
    """Hue/saturation disc. The disc image is rendered once per size."""

    def __init__(
        self,
        on_change: Callable[[float, float], None],
        on_release: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_change = on_change
        self._on_release = on_release
        self.hue = 0.0
        self.sat = 0.0
        self.rgb: cp.RGB = (1.0, 1.0, 1.0)
        self.dragging = False
        self._surface: Optional[cairo.ImageSurface] = None
        self._surface_key: Optional[tuple[int, int]] = None
        self._surface_data: Any = None  # keeps the pixel buffer alive
        self.set_size_request(DISC_SIZE, DISC_SIZE)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_MOTION_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
        )
        self.connect("button-press-event", self._on_pointer)
        self.connect("motion-notify-event", self._on_pointer)
        self.connect("button-release-event", self._on_button_release)
        self.connect("draw", self._on_draw)

    def set_hs(self, hue: float, sat: float, rgb: cp.RGB) -> None:
        """Move the marker (no callback)."""
        self.hue, self.sat, self.rgb = hue, sat, rgb
        self.queue_draw()

    # -- geometry -------------------------------------------------------------

    def _disc(self) -> tuple[float, float, float]:
        alloc = self.get_allocation()
        radius = max(8.0, min(alloc.width, alloc.height) / 2.0 - 4.0)
        return alloc.width / 2.0, alloc.height / 2.0, radius

    def _on_pointer(self, _w: Gtk.Widget, event: Any) -> bool:  # noqa: ANN401
        self.dragging = True
        cx, cy, radius = self._disc()
        dx, dy = event.x - cx, event.y - cy
        sat = min(1.0, math.hypot(dx, dy) / radius)
        hue = (math.atan2(dy, dx) / (2.0 * math.pi)) % 1.0
        self.hue, self.sat = hue, sat
        self.rgb = cp.hs_to_rgb(hue, sat)
        self.queue_draw()
        self._on_change(hue, sat)
        return True

    def _on_button_release(self, _w: Gtk.Widget, _event: Any) -> bool:  # noqa: ANN401
        self.dragging = False
        self._on_release()
        return True

    # -- drawing --------------------------------------------------------------

    def _ensure_surface(self, diameter: int) -> cairo.ImageSurface:
        scale = max(1, self.get_scale_factor())
        key = (diameter, scale)
        if self._surface is None or self._surface_key != key:
            pixels = cp.render_hs_disc(diameter * scale)
            if sys.byteorder == "big":  # cairo ARGB32 is native-endian
                pixels = pixels[..., ::-1]
            data = bytearray(pixels.tobytes())
            side = diameter * scale
            surface = cairo.ImageSurface.create_for_data(
                data, cairo.FORMAT_ARGB32, side, side, side * 4
            )
            surface.set_device_scale(scale, scale)
            self._surface, self._surface_key, self._surface_data = surface, key, data
        return self._surface

    def _on_draw(self, _w: Gtk.Widget, cr: cairo.Context) -> bool:
        cx, cy, radius = self._disc()
        diameter = int(radius * 2.0)
        surface = self._ensure_surface(diameter)
        cr.set_source_surface(surface, cx - diameter / 2.0, cy - diameter / 2.0)
        cr.paint()

        # Thin rim
        cr.arc(cx, cy, diameter / 2.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.35)
        cr.set_line_width(1.0)
        cr.stroke()

        # Marker at the current hue/saturation
        angle = self.hue * 2.0 * math.pi
        mx = cx + math.cos(angle) * self.sat * radius
        my = cy + math.sin(angle) * self.sat * radius
        cr.arc(mx, my, 6.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgb(*self.rgb)
        cr.fill_preserve()
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.set_line_width(2.0)
        cr.stroke_preserve()
        cr.arc(mx, my, 7.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.6)
        cr.set_line_width(1.0)
        cr.stroke()
        return False


class ConsoleColorPicker(Gtk.Box):  # pylint: disable=too-many-instance-attributes
    """HS disc + Kelvin + hex + presets, feeding one throttled color callback.

    Args:
        on_color: called with normalized sRGB ``(r, g, b)``, at most every
            ``SEND_INTERVAL_MS`` while dragging and once more, exactly, when
            the pointer is released.
    """

    def __init__(self, on_color: Callable[[float, float, float], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._on_color = on_color
        self._rgb: cp.RGB = (1.0, 1.0, 1.0)
        self._hue = 0.0
        self._silent = False
        self._kelvin_dragging = False

        self._throttle = cp.Throttle(
            self._emit, SEND_INTERVAL_MS, GLib.timeout_add, GLib.source_remove
        )

        self.disc = HSDiscWidget(self._on_disc_change, self._throttle.flush)
        self.pack_start(self.disc, False, False, 0)

        # Kelvin
        self.pack_start(Gtk.Label(label="Color temperature", xalign=0), False, False, 0)
        self.kelvin = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, cp.KELVIN_MIN, cp.KELVIN_MAX, 50.0
        )
        self.kelvin.set_value(6500.0)
        self.kelvin.set_name("olc-kelvin")
        self.kelvin.set_digits(0)
        self.kelvin.set_value_pos(Gtk.PositionType.RIGHT)
        self._style_kelvin_trough()
        self.kelvin.connect("value-changed", self._on_kelvin_changed)
        self.kelvin.connect("button-press-event", self._on_kelvin_press)
        self.kelvin.connect("button-release-event", self._on_kelvin_release)
        self.pack_start(self.kelvin, False, False, 0)

        # Hex + match quality
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.hex_entry = Gtk.Entry()
        self.hex_entry.set_max_length(7)
        self.hex_entry.set_width_chars(8)
        self.hex_entry.set_text("#FFFFFF")
        self.hex_entry.connect("activate", self._on_hex_activate)
        self.match_label = Gtk.Label(label="", xalign=0)
        css = Gtk.CssProvider()
        css.load_from_data(_CSS)
        self.match_label.get_style_context().add_provider(
            css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        row.pack_start(self.hex_entry, False, False, 0)
        row.pack_start(self.match_label, True, True, 0)
        self.pack_start(row, False, False, 0)

        # Presets
        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(6)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        for name, rgb in cp.PRESETS:
            flow.add(_Swatch(name, rgb, self._on_preset))
        self.pack_start(flow, False, False, 0)

    # -- public ---------------------------------------------------------------

    def set_color(self, r: float, g: float, b: float) -> None:
        """Show a color (e.g. the lead fixture's) without emitting."""
        if self.disc.dragging or self._kelvin_dragging:
            return  # never fight the user's pointer
        self._rgb = (r, g, b)
        hue, sat = cp.rgb_to_hs(r, g, b, self._hue)
        self._hue = hue
        self.disc.set_hs(hue, sat, cp.hs_to_rgb(hue, sat))
        self._silent = True
        try:
            self.hex_entry.set_text(cp.rgb_to_hex(r, g, b))
        finally:
            self._silent = False

    def set_match(self, delta_e: float, warning: str = "") -> None:
        """Display how closely the selected fixtures reproduce the color."""
        level = cp.classify_match(delta_e, warning)
        ctx = self.match_label.get_style_context()
        for css_class in _MATCH_CSS_CLASS.values():
            ctx.remove_class(css_class)
        ctx.add_class(_MATCH_CSS_CLASS[level])
        text = f"ΔE {delta_e:.1f} · {_MATCH_TEXT[level]}"
        self.match_label.set_text(text)
        self.match_label.set_tooltip_text(warning or None)

    def clear_match(self) -> None:
        """Hide the match indicator (nothing selected)."""
        self.match_label.set_text("")

    def cleanup(self) -> None:
        """Cancel pending timers; call before the widget is destroyed."""
        self._throttle.cancel()

    # -- input handlers -------------------------------------------------------

    def _submit(self, rgb: cp.RGB) -> None:
        self._rgb = rgb
        self._silent = True
        try:
            self.hex_entry.set_text(cp.rgb_to_hex(*rgb))
        finally:
            self._silent = False
        self._throttle.submit(*rgb)

    def _on_disc_change(self, hue: float, sat: float) -> None:
        self._hue = hue
        self._submit(cp.hs_to_rgb(hue, sat))

    def _on_kelvin_changed(self, scale: Gtk.Scale) -> None:
        if self._silent:
            return
        rgb = cp.kelvin_to_srgb(scale.get_value())
        hue, sat = cp.rgb_to_hs(*rgb, self._hue)
        self._hue = hue
        self.disc.set_hs(hue, sat, rgb)
        self._submit(rgb)

    def _on_kelvin_press(self, _w: Gtk.Widget, _event: Any) -> bool:  # noqa: ANN401
        self._kelvin_dragging = True
        return False

    def _on_kelvin_release(
        self,
        _w: Gtk.Widget,
        _event: Any,  # noqa: ANN401
    ) -> bool:
        self._kelvin_dragging = False
        self._throttle.flush()
        return False  # let GTK finish the release

    def _on_hex_activate(self, entry: Gtk.Entry) -> None:
        if self._silent:
            return
        rgb = cp.parse_hex(entry.get_text())
        if rgb is None:
            entry.set_text(cp.rgb_to_hex(*self._rgb))
            return
        self.set_color(*rgb)
        self._throttle.submit(*rgb)
        self._throttle.flush()

    def _on_preset(self, rgb: cp.RGB) -> None:
        self.set_color(*rgb)
        self._throttle.submit(*rgb)
        self._throttle.flush()

    def _emit(self, r: float, g: float, b: float) -> None:
        self._on_color(r, g, b)

    # -- styling --------------------------------------------------------------

    def _style_kelvin_trough(self) -> None:
        stops = []
        samples = 9
        for i in range(samples):
            k = cp.KELVIN_MIN + (cp.KELVIN_MAX - cp.KELVIN_MIN) * i / (samples - 1)
            r, g, b = cp.kelvin_to_srgb(k)
            stops.append(
                f"rgb({cp.to_8bit(r)},{cp.to_8bit(g)},{cp.to_8bit(b)}) "
                f"{i * 100 // (samples - 1)}%"
            )
        css = (
            "#olc-kelvin trough { min-height: 10px; border-radius: 5px; "
            f"background-image: linear-gradient(to right, {', '.join(stops)}); }}"
        )
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        self.kelvin.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
