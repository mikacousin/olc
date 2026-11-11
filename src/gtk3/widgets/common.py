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

import enum
import math
import typing

import cairo
import gi

gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Pango, PangoCairo  # noqa: E402


class SystemFontManager:
    """Centralized manager for system/theme font detection and dynamic notifications."""

    _cached_font_name: str | None = None
    _cached_family: str | None = None
    _cached_description: Pango.FontDescription | None = None
    _listeners: list[typing.Callable[[], None]] = []
    _listening_gtk: bool = False

    @classmethod
    def _ensure_listening(cls) -> None:
        if cls._listening_gtk:
            return
        try:
            settings = Gtk.Settings.get_default()
            if settings is not None:
                settings.connect("notify::gtk-font-name", cls._on_font_changed)
                cls._listening_gtk = True
        except Exception:
            pass

    @classmethod
    def _on_font_changed(cls, *args: object) -> None:
        cls._cached_font_name = None
        cls._cached_family = None
        cls._cached_description = None
        FastPangoNumericCache.clear()
        for listener in list(cls._listeners):
            try:
                listener()
            except Exception:
                pass

    @classmethod
    def get_font_name(cls, default: str = "Sans 10") -> str:
        """Get full system font name string (e.g. 'Adwaita Sans 11')."""
        cls._ensure_listening()
        if cls._cached_font_name is None:
            try:
                settings = Gtk.Settings.get_default()
                if settings is not None:
                    name = settings.get_property("gtk-font-name")
                    if name:
                        cls._cached_font_name = name
            except Exception:
                pass
            if cls._cached_font_name is None:
                cls._cached_font_name = default
        return cls._cached_font_name

    @classmethod
    def get_font_description(cls) -> Pango.FontDescription:
        """Get parsed Pango FontDescription for system font."""
        if cls._cached_description is None:
            font_name = cls.get_font_name()
            cls._cached_description = Pango.FontDescription.from_string(font_name)
        return cls._cached_description

    @classmethod
    def get_font_family(cls, default: str = "Sans") -> str:
        """Get system font family name (e.g. 'Adwaita Sans', 'Cantarell')."""
        if cls._cached_family is None:
            desc = cls.get_font_description()
            family = desc.get_family()
            cls._cached_family = family if family else default
        return cls._cached_family

    @classmethod
    def register_listener(cls, callback: typing.Callable[[], None]) -> None:
        """Register a callback to be invoked when the system font changes."""
        cls._ensure_listening()
        if callback not in cls._listeners:
            cls._listeners.append(callback)

    @classmethod
    def unregister_listener(cls, callback: typing.Callable[[], None]) -> None:
        """Unregister a font change listener."""
        if callback in cls._listeners:
            cls._listeners.remove(callback)


def get_system_font_family(default: str = "Sans") -> str:
    """Convenience function returning the system font family name."""
    return SystemFontManager.get_font_family(default)


def get_system_font_description() -> Pango.FontDescription:
    """Convenience function returning the system font Pango.FontDescription."""
    return SystemFontManager.get_font_description()


def create_system_font_description() -> Pango.FontDescription:
    """Return a fresh copy of the system font Pango.FontDescription."""
    desc = get_system_font_description().copy()
    assert desc is not None
    return desc


def register_system_font_listener(callback: typing.Callable[[], None]) -> None:
    """Convenience function to register a system font change listener."""
    SystemFontManager.register_listener(callback)


def create_pango_layout_for_widget(
    cr: cairo.Context,
    text: str = "",
    font_desc: Pango.FontDescription | None = None,
) -> Pango.Layout:
    """Create a Pango.Layout configured with the system font for widget drawing."""
    layout = PangoCairo.create_layout(cr)
    if font_desc is None:
        desc = get_system_font_description().copy()
    else:
        desc = font_desc.copy()
    layout.set_font_description(desc)
    if text:
        layout.set_text(text, -1)
    return layout


def rounded_rectangle_fill(
    cr: cairo.Context, area: tuple[float, float, float, float], radius: float
) -> None:
    """Draw a filled rounded box

    Args:
        cr: cairo context
        area: coordinates (top, bottom, left, right)
        radius: arc radius
    """
    a, b, c, d = area
    cr.arc(a + radius, c + radius, radius, 2 * (math.pi / 2), 3 * (math.pi / 2))
    cr.arc(b - radius, c + radius, radius, 3 * (math.pi / 2), 4 * (math.pi / 2))
    cr.arc(b - radius, d - radius, radius, 0 * (math.pi / 2), 1 * (math.pi / 2))
    cr.arc(a + radius, d - radius, radius, 1 * (math.pi / 2), 2 * (math.pi / 2))
    cr.close_path()
    cr.fill()


def rounded_rectangle(
    cr: cairo.Context, area: tuple[float, float, float, float], radius: float
) -> None:
    """Draw a rounded box

    Args:
        cr: cairo context
        area: coordinates (top, bottom, left, right)
        radius: arc radius
    """
    a, b, c, d = area
    cr.arc(a + radius, c + radius, radius, 2 * (math.pi / 2), 3 * (math.pi / 2))
    cr.arc(b - radius, c + radius, radius, 3 * (math.pi / 2), 4 * (math.pi / 2))
    cr.arc(b - radius, d - radius, radius, 0 * (math.pi / 2), 1 * (math.pi / 2))
    cr.arc(a + radius, d - radius, radius, 1 * (math.pi / 2), 2 * (math.pi / 2))
    cr.close_path()
    cr.stroke()


class TextAnchor(enum.Enum):
    """Text alignment and anchor point definition."""

    TOP_LEFT = enum.auto()
    TOP_CENTER = enum.auto()
    TOP_RIGHT = enum.auto()
    CENTER_LEFT = enum.auto()
    CENTER = enum.auto()
    CENTER_RIGHT = enum.auto()
    BOTTOM_LEFT = enum.auto()
    BOTTOM_CENTER = enum.auto()
    BOTTOM_RIGHT = enum.auto()
    BASELINE_LEFT = enum.auto()
    BASELINE_CENTER = enum.auto()
    BASELINE_RIGHT = enum.auto()


def draw_pango_layout_anchored(
    cr: cairo.Context,
    layout: Pango.Layout,
    x: float,
    y: float,
    anchor: TextAnchor = TextAnchor.CENTER,
) -> tuple[float, float, int, int]:
    """Draw a Pango.Layout at (x, y) with a strictly preserved anchor.

    Args:
        cr: Cairo context.
        layout: Configured Pango.Layout.
        x: Horizontal anchor position.
        y: Vertical anchor position.
        anchor: TextAnchor mode.

    Returns:
        (draw_x, draw_y, logical_width, logical_height) in device pixels.
    """
    _ink, logical = layout.get_pixel_extents()
    w = logical.width
    h = logical.height
    lx = logical.x
    ly = logical.y

    if anchor in (
        TextAnchor.BASELINE_LEFT,
        TextAnchor.BASELINE_CENTER,
        TextAnchor.BASELINE_RIGHT,
    ):
        baseline = layout.get_iter().get_baseline() / Pango.SCALE
        draw_y = y - baseline
        if anchor == TextAnchor.BASELINE_LEFT:
            draw_x = x - lx
        elif anchor == TextAnchor.BASELINE_RIGHT:
            draw_x = x - w - lx
        else:  # BASELINE_CENTER
            draw_x = x - (w / 2.0) - lx
    elif anchor in (TextAnchor.CENTER, TextAnchor.CENTER_LEFT, TextAnchor.CENTER_RIGHT):
        draw_y = y - (h / 2.0) - ly
        if anchor == TextAnchor.CENTER_LEFT:
            draw_x = x - lx
        elif anchor == TextAnchor.CENTER_RIGHT:
            draw_x = x - w - lx
        else:  # CENTER
            draw_x = x - (w / 2.0) - lx
    elif anchor in (TextAnchor.TOP_LEFT, TextAnchor.TOP_CENTER, TextAnchor.TOP_RIGHT):
        draw_y = y - ly
        if anchor == TextAnchor.TOP_LEFT:
            draw_x = x - lx
        elif anchor == TextAnchor.TOP_RIGHT:
            draw_x = x - w - lx
        else:  # TOP_CENTER
            draw_x = x - (w / 2.0) - lx
    else:  # BOTTOM_LEFT, BOTTOM_CENTER, BOTTOM_RIGHT
        draw_y = y - h - ly
        if anchor == TextAnchor.BOTTOM_LEFT:
            draw_x = x - lx
        elif anchor == TextAnchor.BOTTOM_RIGHT:
            draw_x = x - w - lx
        else:  # BOTTOM_CENTER
            draw_x = x - (w / 2.0) - lx

    cr.move_to(draw_x, draw_y)
    try:
        PangoCairo.show_layout(cr, layout)
    except TypeError:
        # Fallback when cr is a MagicMock in unit tests
        if hasattr(cr, "show_text"):
            cr.show_text(layout.get_text())
    return (draw_x, draw_y, w, h)


class FastPangoNumericCache:
    """O(1) memory cache for recurrent numeric & badge Pango layouts."""

    _cache: dict[tuple[str, float, Pango.Weight, str], Pango.Layout] = {}
    _dummy_surface: cairo.ImageSurface | None = None
    _dummy_cr: cairo.Context | None = None

    @classmethod
    def _get_dummy_cr(cls) -> cairo.Context:
        if cls._dummy_cr is None:
            cls._dummy_surface = cairo.ImageSurface(cairo.Format.ARGB32, 1, 1)
            cls._dummy_cr = cairo.Context(cls._dummy_surface)
        return cls._dummy_cr

    @classmethod
    def get_layout(
        cls,
        text: str,
        font_size_pt: float,
        weight: Pango.Weight = Pango.Weight.NORMAL,
        family: str | None = None,
        cr: cairo.Context | None = None,
    ) -> Pango.Layout:
        """Get or create cached Pango.Layout for discrete numeric or badge string."""
        fam = family or get_system_font_family()
        key = (text, round(font_size_pt, 1), weight, fam)
        layout = cls._cache.get(key)
        if layout is None:
            ctx = cr or cls._get_dummy_cr()
            layout = PangoCairo.create_layout(ctx)
            desc = create_system_font_description()
            if family:
                desc.set_family(family)
            desc.set_weight(weight)
            desc.set_size(int(font_size_pt * Pango.SCALE))
            layout.set_font_description(desc)
            layout.set_text(text, -1)
            cls._cache[key] = layout
        return layout

    @classmethod
    def clear(cls) -> None:
        """Clear the cached layouts."""
        cls._cache.clear()
        cls._dummy_cr = None
        cls._dummy_surface = None


def draw_cached_numeric_text(
    cr: cairo.Context,
    x: float,
    y: float,
    text: str,
    font_size_pt: float,
    weight: Pango.Weight = Pango.Weight.NORMAL,
    anchor: TextAnchor = TextAnchor.CENTER,
    family: str | None = None,
) -> tuple[float, float, int, int]:
    """Draw numeric or badge text using cached layout with exact anchor."""
    layout = FastPangoNumericCache.get_layout(
        text, font_size_pt, weight=weight, family=family, cr=cr
    )
    return draw_pango_layout_anchored(cr, layout, x, y, anchor=anchor)
