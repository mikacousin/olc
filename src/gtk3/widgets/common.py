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

import math
import typing

import gi

gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Pango, PangoCairo  # noqa: E402

if typing.TYPE_CHECKING:
    import cairo


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
