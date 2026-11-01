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
"""Console-style color picker: HS disc, CIE 1931 xy, Kelvin, Tint (Duv), hex, presets.

All the color math and rate limiting lives in ``olc.devices.color_pick`` (no
GTK, unit tested). This module is only the drawing and the event plumbing.
"""

# pylint: disable=too-many-lines

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

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


@dataclass(frozen=True)
class FixtureColorPoint:
    """Chromaticity state of a selected fixture for multi-reticle display."""

    device_id: int
    rgb: cp.RGB
    xy: cp.XY
    is_lead: bool = False


_MATCH_BADGE_RGB: dict[str, cp.RGB] = {
    "exact": (0.37, 0.75, 0.37),
    "close": (0.66, 0.78, 0.35),
    "approx": (0.88, 0.63, 0.19),
    "out": (0.88, 0.31, 0.31),
}


class _Swatch(Gtk.Button):  # pylint: disable=too-few-public-methods
    """Small flat button filled with a color, optional gel code, and ΔE badge."""

    def __init__(
        self,
        name: str,
        rgb: cp.RGB,
        on_pick: Callable[[cp.RGB], None],
        code: str = "",
        gel: Optional[cp.GelSwatch] = None,
    ) -> None:
        super().__init__()
        self.base_name = name
        self.rgb = rgb
        self.code = code
        self.gel = gel
        self.match_level: Optional[str] = None
        self.set_tooltip_text(name)
        self.set_relief(Gtk.ReliefStyle.NONE)
        area = Gtk.DrawingArea()
        area.set_size_request(36 if code else 22, 20 if code else 18)
        area.connect("draw", self._on_draw)
        self._area = area
        self.add(area)
        self.connect("clicked", lambda _b: on_pick(self.rgb))

    def set_match_badge(
        self, level: Optional[str], delta_e: float = 0.0, warning: str = ""
    ) -> None:
        """Update feasibility badge and tooltip for the active Lead profile."""
        self.match_level = level
        if level is None:
            self.set_tooltip_text(self.base_name)
        else:
            warn_str = f" ({warning})" if warning else ""
            self.set_tooltip_text(
                f"{self.base_name} — ΔE {delta_e:.1f} · {_MATCH_TEXT[level]}{warn_str}"
            )
        self._area.queue_draw()

    def _on_draw(self, widget: Gtk.Widget, cr: cairo.Context) -> bool:
        alloc = widget.get_allocation()
        w, h = alloc.width, alloc.height
        cr.rectangle(0, 0, w, h)
        cr.set_source_rgb(*self.rgb)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.35)
        cr.set_line_width(1.0)
        cr.stroke()

        if self.code:
            luma = 0.2126 * self.rgb[0] + 0.7152 * self.rgb[1] + 0.0722 * self.rgb[2]
            if luma > 0.55:
                cr.set_source_rgba(0.05, 0.05, 0.05, 0.9)
            else:
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
            cr.set_font_size(8.5)
            ext = cr.text_extents(self.code)
            cr.move_to(
                (w - ext.width) / 2.0 - ext.x_bearing,
                (h - ext.height) / 2.0 - ext.y_bearing,
            )
            cr.show_text(self.code)

        if self.match_level in _MATCH_BADGE_RGB:
            br, bg, bb = _MATCH_BADGE_RGB[self.match_level]
            cr.new_sub_path()
            cr.arc(w - 4.0, 4.0, 2.8, 0.0, 2.0 * math.pi)
            cr.set_source_rgb(br, bg, bb)
            cr.fill_preserve()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.7)
            cr.set_line_width(0.8)
            cr.stroke()
        return False


class HSDiscWidget(Gtk.DrawingArea):  # pylint: disable=too-many-instance-attributes
    """Hue/saturation disc with gamut polygon and multi-fixture reticles."""

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
        self.gamut_hs: list[tuple[float, float]] = []
        self.points: list[FixtureColorPoint] = []
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

    def set_overlay(
        self,
        gamut_hs: list[tuple[float, float]],
        points: list[FixtureColorPoint],
    ) -> None:
        """Update gamut polygon and multi-fixture reticle positions."""
        self.gamut_hs = list(gamut_hs)
        self.points = list(points)
        self.queue_draw()

    # -- geometry -------------------------------------------------------------

    def _disc(self) -> tuple[float, float, float]:
        alloc = self.get_allocation()
        radius = max(8.0, min(alloc.width, alloc.height) / 2.0 - 4.0)
        return alloc.width / 2.0, alloc.height / 2.0, radius

    @staticmethod
    def _hs_to_px(
        hue: float, sat: float, cx: float, cy: float, radius: float
    ) -> tuple[float, float]:
        angle = hue * 2.0 * math.pi
        return (
            cx + math.cos(angle) * sat * radius,
            cy + math.sin(angle) * sat * radius,
        )

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

    def _on_draw(  # pylint: disable=too-many-locals
        self, _w: Gtk.Widget, cr: cairo.Context
    ) -> bool:
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

        # Lead fixture gamut polygon overlay
        if len(self.gamut_hs) >= 3:
            cr.save()
            for idx, (gh, gs) in enumerate(self.gamut_hs):
                gx, gy = self._hs_to_px(gh, gs, cx, cy, radius)
                if idx == 0:
                    cr.move_to(gx, gy)
                else:
                    cr.line_to(gx, gy)
            cr.close_path()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.55)
            cr.set_line_width(2.0)
            cr.stroke_preserve()
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.85)
            cr.set_dash([4.0, 3.0])
            cr.set_line_width(1.2)
            cr.stroke()
            cr.restore()

        # Satellite fixture reticles
        for pt in self.points:
            if pt.is_lead:
                continue
            ph, ps = cp.rgb_to_hs(*pt.rgb, self.hue)
            px, py = self._hs_to_px(ph, ps, cx, cy, radius)
            cr.arc(px, py, 4.0, 0.0, 2.0 * math.pi)
            cr.set_source_rgba(0.15, 0.85, 0.95, 0.8)
            cr.fill_preserve()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.7)
            cr.set_line_width(1.0)
            cr.stroke()

        # Marker at the current (Lead) hue/saturation
        mx, my = self._hs_to_px(self.hue, self.sat, cx, cy, radius)
        cr.new_sub_path()
        cr.arc(mx, my, 6.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgb(*self.rgb)
        cr.fill_preserve()
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.set_line_width(2.0)
        cr.stroke()
        cr.new_sub_path()
        cr.arc(mx, my, 7.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.6)
        cr.set_line_width(1.0)
        cr.stroke()
        return False


class CIExyWidget(Gtk.DrawingArea):  # pylint: disable=too-many-instance-attributes
    """CIE 1931 xy horseshoe diagram with Planckian locus, gamut hull, and reticles."""

    def __init__(
        self,
        on_change: Callable[[float, float], None],
        on_release: Callable[[], None],
    ) -> None:
        super().__init__()
        self._on_change = on_change
        self._on_release = on_release
        self.cie_x = 0.3127
        self.cie_y = 0.3290
        self.rgb: cp.RGB = (1.0, 1.0, 1.0)
        self.dragging = False
        self.gamut_xy: list[cp.XY] = []
        self.emitters_xy: list[cp.XY] = []
        self.points: list[FixtureColorPoint] = []
        self._planck_xy = cp.planckian_locus_xy(32)
        self._surface: Optional[cairo.ImageSurface] = None
        self._surface_key: Optional[tuple[int, int]] = None
        self._surface_data: Any = None
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

    def set_xy(self, x: float, y: float, rgb: cp.RGB) -> None:
        """Move the CIE xy reticle (no callback)."""
        self.cie_x, self.cie_y, self.rgb = x, y, rgb
        self.queue_draw()

    def set_overlay(
        self,
        gamut_xy: list[cp.XY],
        points: list[FixtureColorPoint],
        emitters_xy: Optional[list[cp.XY]] = None,
    ) -> None:
        """Update emitter gamut polygon and multi-fixture reticle positions."""
        self.gamut_xy = list(gamut_xy)
        self.emitters_xy = (
            list(emitters_xy) if emitters_xy is not None else list(gamut_xy)
        )
        self.points = list(points)
        self.queue_draw()

    # -- geometry -------------------------------------------------------------

    def _box(self) -> tuple[float, float, float]:
        alloc = self.get_allocation()
        side = max(16.0, float(min(alloc.width, alloc.height)) - 8.0)
        ox = (alloc.width - side) / 2.0
        oy = (alloc.height - side) / 2.0
        return ox, oy, side

    @staticmethod
    def _xy_to_px(
        x: float, y: float, ox: float, oy: float, side: float
    ) -> tuple[float, float]:
        px = ox + (x / cp.CIE_X_MAX) * side
        py = oy + (1.0 - y / cp.CIE_Y_MAX) * side
        return px, py

    @staticmethod
    def _px_to_xy(px: float, py: float, ox: float, oy: float, side: float) -> cp.XY:
        nx = max(0.0, min(1.0, (px - ox) / side))
        ny = max(0.0, min(1.0, 1.0 - (py - oy) / side))
        return nx * cp.CIE_X_MAX, ny * cp.CIE_Y_MAX

    def _on_pointer(self, _w: Gtk.Widget, event: Any) -> bool:  # noqa: ANN401
        self.dragging = True
        ox, oy, side = self._box()
        raw_x, raw_y = self._px_to_xy(event.x, event.y, ox, oy, side)
        cx, cy = cp.clamp_xy_to_locus(raw_x, raw_y)
        self.cie_x, self.cie_y = cx, cy
        self.rgb = cp.xy_to_srgb(cx, cy)
        self.queue_draw()
        self._on_change(cx, cy)
        return True

    def _on_button_release(self, _w: Gtk.Widget, _event: Any) -> bool:  # noqa: ANN401
        self.dragging = False
        self._on_release()
        return True

    # -- drawing --------------------------------------------------------------

    def _ensure_surface(self, side_int: int) -> cairo.ImageSurface:
        scale = max(1, self.get_scale_factor())
        key = (side_int, scale)
        if self._surface is None or self._surface_key != key:
            pixels = cp.render_cie_xy_diagram(side_int * scale)
            if sys.byteorder == "big":
                pixels = pixels[..., ::-1]
            data = bytearray(pixels.tobytes())
            px_side = side_int * scale
            surface = cairo.ImageSurface.create_for_data(
                data, cairo.FORMAT_ARGB32, px_side, px_side, px_side * 4
            )
            surface.set_device_scale(scale, scale)
            self._surface, self._surface_key, self._surface_data = surface, key, data
        return self._surface

    def _on_draw(  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        self, _w: Gtk.Widget, cr: cairo.Context
    ) -> bool:
        ox, oy, side = self._box()
        side_int = max(8, int(side))
        surface = self._ensure_surface(side_int)
        cr.set_source_surface(surface, ox, oy)
        cr.paint()

        # Spectral horseshoe outline
        for idx, (lx, ly) in enumerate(cp.SPECTRAL_LOCUS_XY):
            px, py = self._xy_to_px(lx, ly, ox, oy, side)
            if idx == 0:
                cr.move_to(px, py)
            else:
                cr.line_to(px, py)
        cr.close_path()
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.45)
        cr.set_line_width(1.0)
        cr.stroke()

        # Planckian locus curve (1800 K - 12000 K)
        cr.save()
        for idx, (kx, ky) in enumerate(self._planck_xy):
            px, py = self._xy_to_px(kx, ky, ox, oy, side)
            if idx == 0:
                cr.move_to(px, py)
            else:
                cr.line_to(px, py)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.5)
        cr.set_line_width(2.0)
        cr.stroke_preserve()
        cr.set_source_rgba(1.0, 0.96, 0.85, 0.85)
        cr.set_line_width(1.0)
        cr.stroke()
        cr.restore()

        # Lead fixture emitter gamut polygon
        if len(self.gamut_xy) >= 3:
            cr.save()
            for idx, (gx, gy) in enumerate(self.gamut_xy):
                px, py = self._xy_to_px(gx, gy, ox, oy, side)
                if idx == 0:
                    cr.move_to(px, py)
                else:
                    cr.line_to(px, py)
            cr.close_path()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.65)
            cr.set_line_width(2.2)
            cr.stroke_preserve()
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.9)
            cr.set_dash([4.0, 3.0])
            cr.set_line_width(1.2)
            cr.stroke()
            cr.restore()

            for gx, gy in self.emitters_xy or self.gamut_xy:
                px, py = self._xy_to_px(gx, gy, ox, oy, side)
                cr.arc(px, py, 2.5, 0.0, 2.0 * math.pi)
                cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
                cr.fill_preserve()
                cr.set_source_rgba(0.0, 0.0, 0.0, 0.8)
                cr.set_line_width(1.0)
                cr.stroke()

        # Satellite fixture reticles
        for pt in self.points:
            if pt.is_lead:
                continue
            px, py = self._xy_to_px(pt.xy[0], pt.xy[1], ox, oy, side)
            cr.arc(px, py, 4.0, 0.0, 2.0 * math.pi)
            cr.set_source_rgba(0.15, 0.85, 0.95, 0.85)
            cr.fill_preserve()
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.75)
            cr.set_line_width(1.0)
            cr.stroke()

        # Lead reticle at current (cie_x, cie_y)
        mx, my = self._xy_to_px(self.cie_x, self.cie_y, ox, oy, side)
        cr.new_sub_path()
        cr.arc(mx, my, 6.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgb(*self.rgb)
        cr.fill_preserve()
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.set_line_width(2.0)
        cr.stroke()
        cr.new_sub_path()
        cr.arc(mx, my, 7.0, 0.0, 2.0 * math.pi)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.65)
        cr.set_line_width(1.0)
        cr.stroke()
        return False


_EMITTER_SPECS: tuple[tuple[str, str], ...] = (
    ("red", "R"),
    ("green", "G"),
    ("blue", "B"),
    ("white", "W"),
    ("amber", "A"),
    ("lime", "L"),
)


class ConsoleColorPicker(Gtk.Box):  # pylint: disable=too-many-instance-attributes
    """HS disc + CIE 1931 xy + Kelvin + Tint (Duv) + emitter faders + presets.

    Args:
        on_color: called with normalized sRGB ``(r, g, b)``, at most every
            ``SEND_INTERVAL_MS`` while dragging and once more, exactly, when
            the pointer is released.
        on_emitter_changed: optional callback ``(channel_type_value, level_0_1)``
            invoked when an emitter fader is adjusted manually.
        on_strategy_changed: optional callback ``(strategy_name,)`` invoked when
            the NNLS solver strategy changes.
        on_wheel_slot_clicked: optional callback ``(slot_label,)`` invoked when
            a COLOR_WHEEL slot swatch is clicked.
    """

    def __init__(  # pylint: disable=too-many-statements,too-many-locals
        self,
        on_color: Callable[[float, float, float], None],
        on_emitter_changed: Optional[Callable[[str, float], None]] = None,
        on_strategy_changed: Optional[Callable[[str], None]] = None,
        on_wheel_slot_clicked: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._on_color = on_color
        self._on_emitter_changed = on_emitter_changed
        self._on_strategy_changed = on_strategy_changed
        self._on_wheel_slot_clicked = on_wheel_slot_clicked
        self._rgb: cp.RGB = (1.0, 1.0, 1.0)
        self._hue = 0.0
        self._silent = False
        self._kelvin_dragging = False
        self._tint_dragging = False
        self._emitter_dragging = False
        self.gamut_xy: list[cp.XY] = []
        self.gamut_hs: list[tuple[float, float]] = []
        self.fixture_points: list[FixtureColorPoint] = []
        self.wheel_slots: list[tuple[str, cp.RGB]] = []
        self._swatch_solver = cp.ColorSolver()
        self._lead_profile: Optional[Any] = None
        self.swatch_widgets: list[_Swatch] = []

        self._throttle = cp.Throttle(
            self._emit, SEND_INTERVAL_MS, GLib.timeout_add, GLib.source_remove
        )

        # View Switcher: HS Disc | CIE 1931 xy + NNLS Strategy selector
        self.view_stack = Gtk.Stack()
        self.view_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.disc = HSDiscWidget(self._on_disc_change, self._throttle.flush)
        self.cie_xy = CIExyWidget(self._on_cie_xy_change, self._throttle.flush)
        self.view_stack.add_titled(self.disc, "hs", "HS Disc")
        self.view_stack.add_titled(self.cie_xy, "cie_xy", "CIE 1931 xy")

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.view_stack)
        self.strategy_combo = Gtk.ComboBoxText()
        self.strategy_combo.append("spectral", "Match: Spectral")
        self.strategy_combo.append("punch", "Match: Max Punch")
        self.strategy_combo.append("rgb_only", "Match: RGB Only")
        self.strategy_combo.set_active_id("spectral")
        self.strategy_combo.connect("changed", self._on_strategy_combo_changed)
        top_bar.pack_start(switcher, True, False, 0)
        top_bar.pack_end(self.strategy_combo, False, False, 0)
        self.pack_start(top_bar, False, False, 0)
        self.pack_start(self.view_stack, False, False, 0)

        # Kelvin (CCT)
        self.pack_start(
            Gtk.Label(label="Color temperature (K)", xalign=0), False, False, 0
        )
        self.kelvin = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, cp.KELVIN_MIN, cp.KELVIN_MAX, 50.0
        )
        self.kelvin.set_value(6500.0)
        self.kelvin.set_name("olc-kelvin")
        self.kelvin.set_digits(0)
        self.kelvin.set_value_pos(Gtk.PositionType.RIGHT)
        self._style_kelvin_trough()
        self.kelvin.connect("value-changed", self._on_kelvin_or_tint_changed)
        self.kelvin.connect("button-press-event", self._on_kelvin_press)
        self.kelvin.connect("button-release-event", self._on_kelvin_release)
        self.pack_start(self.kelvin, False, False, 0)

        # Tint (Duv)
        self.pack_start(Gtk.Label(label="Tint (Δuv)", xalign=0), False, False, 0)
        self.tint = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, cp.DUV_MIN, cp.DUV_MAX, 0.001
        )
        self.tint.set_value(0.0)
        self.tint.set_name("olc-tint")
        self.tint.set_digits(3)
        self.tint.set_value_pos(Gtk.PositionType.RIGHT)
        self.tint.add_mark(0.0, Gtk.PositionType.BOTTOM, None)
        self._style_tint_trough()
        self.tint.connect("value-changed", self._on_kelvin_or_tint_changed)
        self.tint.connect("button-press-event", self._on_tint_press)
        self.tint.connect("button-release-event", self._on_tint_release)
        self.pack_start(self.tint, False, False, 0)

        # Real-time physical emitter faders (R, G, B, W, A, L)
        self.emitters_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.emitter_rows: dict[str, Gtk.Box] = {}
        self.emitter_scales: dict[str, Gtk.Scale] = {}
        for etype, short_lbl in _EMITTER_SPECS:
            erow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            lbl = Gtk.Label(label=short_lbl, xalign=0.0)
            lbl.set_width_chars(2)
            scale = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 1.0
            )
            scale.set_digits(0)
            scale.set_value_pos(Gtk.PositionType.RIGHT)
            scale.connect("value-changed", self._on_emitter_scale_changed, etype)
            scale.connect("button-press-event", self._on_emitter_press)
            scale.connect("button-release-event", self._on_emitter_release)
            erow.pack_start(lbl, False, False, 0)
            erow.pack_start(scale, True, True, 0)
            erow.set_no_show_all(True)
            lbl.show()
            scale.show()
            self.emitter_rows[etype] = erow
            self.emitter_scales[etype] = scale
            self.emitters_box.pack_start(erow, False, False, 0)
        self.pack_start(self.emitters_box, False, False, 0)

        # Dynamic Color Wheel slots row (shown when COLOR_WHEEL ranges exist)
        self.wheel_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.wheel_box.set_no_show_all(True)
        wheel_lbl = Gtk.Label(label="Color Wheel Slots", xalign=0)
        wheel_lbl.show()
        self.wheel_flow = Gtk.FlowBox()
        self.wheel_flow.set_max_children_per_line(6)
        self.wheel_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.wheel_flow.show()
        self.wheel_box.pack_start(wheel_lbl, False, False, 0)
        self.wheel_box.pack_start(self.wheel_flow, False, False, 0)
        self.pack_start(self.wheel_box, False, False, 0)

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

        # Gel Swatchbook Filter Bar (Search + Manufacturer Filter)
        gel_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.gel_search_entry = Gtk.SearchEntry()
        self.gel_search_entry.set_placeholder_text("Gel # or name (L201, Congo)...")
        self.gel_search_entry.connect("changed", self._on_gel_filter_changed)
        self.gel_search_entry.connect("activate", self._on_gel_search_activate)
        self.gel_filter_combo = Gtk.ComboBoxText()
        self.gel_filter_combo.append("quick", "Quick")
        self.gel_filter_combo.append("All", "All Gels")
        self.gel_filter_combo.append("Lee", "Lee")
        self.gel_filter_combo.append("Rosco", "Rosco")
        self.gel_filter_combo.set_active_id("quick")
        self.gel_filter_combo.connect("changed", self._on_gel_filter_changed)
        gel_bar.pack_start(self.gel_search_entry, True, True, 0)
        gel_bar.pack_end(self.gel_filter_combo, False, False, 0)
        self.pack_start(gel_bar, False, False, 0)

        # Swatchbook Grid
        self.swatch_flow = Gtk.FlowBox()
        self.swatch_flow.set_max_children_per_line(6)
        self.swatch_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.pack_start(self.swatch_flow, False, False, 0)
        self._rebuild_swatches()

    # -- public ---------------------------------------------------------------

    @property
    def is_dragging(self) -> bool:
        """Return True if any interactive surface or slider is being dragged."""
        return (
            self.disc.dragging
            or self.cie_xy.dragging
            or self._kelvin_dragging
            or self._tint_dragging
            or self._emitter_dragging
        )

    def set_color(self, r: float, g: float, b: float) -> None:
        """Show a color (e.g. the lead fixture's) without emitting."""
        if self.is_dragging:
            return  # never fight the user's pointer
        self._rgb = (r, g, b)
        hue, sat = cp.rgb_to_hs(r, g, b, self._hue)
        self._hue = hue
        self.disc.set_hs(hue, sat, cp.hs_to_rgb(hue, sat))
        cx, cy = cp.srgb_to_xy(r, g, b)
        self.cie_xy.set_xy(cx, cy, (r, g, b))
        self._silent = True
        try:
            self.hex_entry.set_text(cp.rgb_to_hex(r, g, b))
        finally:
            self._silent = False

    def set_devices_context(  # pylint: disable=too-many-locals,too-many-branches
        self, lead: Optional[object], devices: Iterable[object]
    ) -> None:
        """Update gamut hull, reticles, emitter faders, and wheel slots."""
        dev_list = list(devices)
        if lead is not None:
            self.gamut_xy = cp.device_gamut_xy(lead)
            self.gamut_hs = cp.device_gamut_hs(lead)
            emitters_xy = cp.device_emitters_xy(lead)
            self._lead_profile = cp.effective_color_profile(lead)
        else:
            self.gamut_xy = []
            self.gamut_hs = []
            emitters_xy = []
            self._lead_profile = None

        points: list[FixtureColorPoint] = []
        present_emitters: set[str] = set()
        for dev in dev_list:
            for ch in getattr(dev, "channels", ()):
                ct_val = getattr(getattr(ch, "channel_type", None), "value", None)
                if isinstance(ct_val, str):
                    present_emitters.add(ct_val)
            srgb = getattr(dev, "color_srgb", None)
            cie = getattr(dev, "color_cie", None)
            if srgb is None:
                continue
            rgb_tuple: cp.RGB = (float(srgb.r), float(srgb.g), float(srgb.b))
            xy_tuple: cp.XY = (
                (float(cie.x), float(cie.y))
                if cie is not None
                else cp.srgb_to_xy(*rgb_tuple)
            )
            points.append(
                FixtureColorPoint(
                    device_id=int(getattr(dev, "device_id", 0)),
                    rgb=rgb_tuple,
                    xy=xy_tuple,
                    is_lead=dev is lead,
                )
            )
        self.fixture_points = points
        self.disc.set_overlay(self.gamut_hs, points)
        self.cie_xy.set_overlay(self.gamut_xy, points, emitters_xy)

        self._update_emitter_faders(lead, present_emitters)
        self._update_wheel_slots(lead, dev_list)
        self._update_swatch_badges()

    def _update_emitter_faders(
        self, lead: Optional[object], present_emitters: set[str]
    ) -> None:
        """Show/hide emitter faders and sync values with the lead fixture."""
        self._silent = True
        try:
            for etype, _lbl in _EMITTER_SPECS:
                erow = self.emitter_rows[etype]
                is_present = etype in present_emitters
                erow.set_visible(is_present)
                if is_present and lead is not None and not self._emitter_dragging:
                    base_map = getattr(lead, "_base_emitters", {})
                    lvl = 0.0
                    for k, v in base_map.items():
                        if getattr(k, "value", k) == etype:
                            lvl = float(v)
                            break
                    self.emitter_scales[etype].set_value(round(lvl * 100.0))
        finally:
            self._silent = False

    def _update_wheel_slots(
        self, lead: Optional[object], dev_list: list[object]
    ) -> None:
        """Populate dynamic COLOR_WHEEL slot swatches if present in selection."""
        slots_raw: list[tuple[Any, cp.RGB]] = []
        if lead is not None:
            slots_raw = cp.extract_color_wheel_slots(lead)
        if not slots_raw:
            for dev in dev_list:
                slots_raw = cp.extract_color_wheel_slots(dev)
                if slots_raw:
                    break

        new_slots = [(str(rng.label), rgb) for rng, rgb in slots_raw]
        if new_slots != self.wheel_slots:
            self.wheel_slots = new_slots
            for child in self.wheel_flow.get_children():
                self.wheel_flow.remove(child)
            for slot_label, slot_rgb in new_slots:
                sw = _Swatch(
                    slot_label,
                    slot_rgb,
                    lambda rgb, lbl=slot_label: self._on_wheel_swatch(lbl, rgb),
                )
                sw.show_all()
                self.wheel_flow.add(sw)
        self.wheel_box.set_visible(bool(new_slots))

    def _rebuild_swatches(self) -> None:
        """Populate swatch_flow according to active manufacturer filter and query."""
        for child in self.swatch_flow.get_children():
            self.swatch_flow.remove(child)
        self.swatch_widgets.clear()

        query = self.gel_search_entry.get_text().strip()
        mode = self.gel_filter_combo.get_active_id() or "quick"

        if mode == "quick" and not query:
            for name, rgb in cp.PRESETS:
                sw = _Swatch(name, rgb, self._on_preset)
                sw.show_all()
                self.swatch_flow.add(sw)
                self.swatch_widgets.append(sw)
        else:
            mfg = "All" if mode in ("quick", "All") else mode
            for gel in cp.filter_gels(query=query, manufacturer=mfg):
                tooltip = (
                    f"{gel.code} · {gel.name} ({gel.manufacturer}) "
                    f"[{gel.category}, Y={gel.transmission_y:.0f}%]"
                )
                sw = _Swatch(
                    tooltip,
                    gel.rgb,
                    self._on_preset,
                    code=gel.code,
                    gel=gel,
                )
                sw.show_all()
                self.swatch_flow.add(sw)
                self.swatch_widgets.append(sw)

        self._update_swatch_badges()

    def _update_swatch_badges(self) -> None:
        """Update ΔE feasibility badges on visible gel swatches for Lead profile."""
        for sw in self.swatch_widgets:
            if sw.gel is None or self._lead_profile is None:
                sw.set_match_badge(None)
                continue
            de, warn, lvl = cp.evaluate_gel_for_profile(
                sw.gel, self._lead_profile, self._swatch_solver
            )
            sw.set_match_badge(lvl, delta_e=de, warning=warn)

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
        rgb = cp.hs_to_rgb(hue, sat)
        cx, cy = cp.srgb_to_xy(*rgb)
        self.cie_xy.set_xy(cx, cy, rgb)
        self._submit(rgb)

    def _on_cie_xy_change(self, x: float, y: float) -> None:
        rgb = cp.xy_to_srgb(x, y)
        hue, sat = cp.rgb_to_hs(*rgb, self._hue)
        self._hue = hue
        self.disc.set_hs(hue, sat, rgb)
        self._submit(rgb)

    def _on_kelvin_or_tint_changed(self, _scale: Gtk.Scale) -> None:
        if self._silent:
            return
        k = self.kelvin.get_value()
        duv = self.tint.get_value()
        cx, cy = cp.kelvin_duv_to_xy(k, duv)
        rgb = cp.xy_to_srgb(cx, cy)
        hue, sat = cp.rgb_to_hs(*rgb, self._hue)
        self._hue = hue
        self.disc.set_hs(hue, sat, rgb)
        self.cie_xy.set_xy(cx, cy, rgb)
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
        return False

    def _on_tint_press(self, _w: Gtk.Widget, _event: Any) -> bool:  # noqa: ANN401
        self._tint_dragging = True
        return False

    def _on_tint_release(
        self,
        _w: Gtk.Widget,
        _event: Any,  # noqa: ANN401
    ) -> bool:
        self._tint_dragging = False
        self._throttle.flush()
        return False

    def _on_emitter_press(self, _w: Gtk.Widget, _event: Any) -> bool:  # noqa: ANN401
        self._emitter_dragging = True
        return False

    def _on_emitter_release(self, _w: Gtk.Widget, _event: Any) -> bool:  # noqa: ANN401
        self._emitter_dragging = False
        return False

    def _on_emitter_scale_changed(self, scale: Gtk.Scale, etype: str) -> None:
        if self._silent:
            return
        level = max(0.0, min(1.0, scale.get_value() / 100.0))
        if self._on_emitter_changed is not None:
            self._on_emitter_changed(etype, level)

    def _on_strategy_combo_changed(self, combo: Gtk.ComboBoxText) -> None:
        if self._silent:
            return
        strat = combo.get_active_id() or "spectral"
        self._swatch_solver.strategy = strat
        self._update_swatch_badges()
        if self._on_strategy_changed is not None:
            self._on_strategy_changed(strat)

    def _on_gel_filter_changed(self, _widget: Gtk.Widget) -> None:
        if self._silent:
            return
        self._rebuild_swatches()

    def _on_gel_search_activate(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip()
        if not query:
            return
        mode = self.gel_filter_combo.get_active_id() or "quick"
        mfg = "All" if mode in ("quick", "All") else mode
        matches = cp.filter_gels(query=query, manufacturer=mfg)
        if matches:
            self._on_preset(matches[0].rgb)

    def _on_wheel_swatch(self, slot_label: str, slot_rgb: cp.RGB) -> None:
        if self._on_wheel_slot_clicked is not None:
            self._on_wheel_slot_clicked(slot_label)
        else:
            self._on_preset(slot_rgb)

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

    def _style_tint_trough(self) -> None:
        css = (
            "#olc-tint trough { min-height: 10px; border-radius: 5px; "
            "background-image: linear-gradient(to right, "
            "rgb(224,96,192) 0%, rgb(240,240,240) 50%, rgb(96,216,112) 100%); }"
        )
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        self.tint.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
