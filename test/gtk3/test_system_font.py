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
import cairo
import pytest
from gi.repository import Pango

from olc.gtk3.widgets.button import ButtonWidget
from olc.gtk3.widgets.common import (
    SystemFontManager,
    create_pango_layout_for_widget,
    create_system_font_description,
    get_system_font_description,
    get_system_font_family,
    register_system_font_listener,
)
from olc.gtk3.widgets.flash import FlashWidget
from olc.gtk3.widgets.go import GoWidget
from olc.gtk3.widgets.group import GroupWidget
from olc.gtk3.widgets.main_fader import MainFaderWidget
from olc.gtk3.widgets.pause import PauseWidget


def test_system_font_manager_defaults() -> None:
    """Verify SystemFontManager defaults when settings are not present."""
    mgr = SystemFontManager()
    family = mgr.get_font_family()
    assert isinstance(family, str)
    assert len(family) > 0

    desc = mgr.get_font_description()
    assert isinstance(desc, Pango.FontDescription)
    assert desc.get_family() is not None


def test_system_font_helper_functions() -> None:
    """Verify top-level helper functions work cleanly."""
    family = get_system_font_family()
    assert isinstance(family, str)
    assert len(family) > 0

    desc = get_system_font_description()
    assert isinstance(desc, Pango.FontDescription)


def test_create_pango_layout_for_widget() -> None:
    """Verify create_pango_layout_for_widget returns a valid layout."""
    surface = cairo.ImageSurface(cairo.Format.ARGB32, 100, 100)
    cr = cairo.Context(surface)
    layout = create_pango_layout_for_widget(cr, "Test Label")
    assert layout is not None
    assert layout.get_text() == "Test Label"
    assert layout.get_font_description() is not None


def test_system_font_listener_notification() -> None:
    """Verify registering a listener triggers callback on notify."""
    notified: list[bool] = []

    def on_change() -> None:
        notified.append(True)

    SystemFontManager.register_listener(on_change)
    SystemFontManager._on_font_changed()
    assert len(notified) == 1

    register_system_font_listener(on_change)
    SystemFontManager._on_font_changed()
    assert len(notified) == 2

    SystemFontManager.unregister_listener(on_change)
    SystemFontManager._on_font_changed()
    assert len(notified) == 2


@pytest.mark.gui
def test_pango_widgets_draw_without_error() -> None:
    """Verify all Pango-based UI widgets render on Cairo context without error."""
    surface = cairo.ImageSurface(cairo.Format.ARGB32, 200, 200)
    cr = cairo.Context(surface)

    # ButtonWidget (single-line, multiline, shortcut)
    btn1 = ButtonWidget(label="Group", text="10", shortcut_text="G")
    btn1.show_shortcut = True
    btn1.do_draw(cr)

    btn2 = ButtonWidget(label="High\nLevel", text="11", shortcut_text="H")
    btn2.do_draw(cr)

    # FlashWidget
    flash = FlashWidget(label="VeryLongMasterLabel", text="1")
    flash.do_draw(cr)

    # GroupWidget
    group = GroupWidget(
        number=1.0,
        name="SpotlightsFrontStage",
    )
    group.do_draw(cr)

    # PauseWidget
    pause = PauseWidget(label="Pause", text="1", shortcut_text="P")
    pause.show_shortcut = True
    pause.do_draw(cr)

    # GoWidget
    go = GoWidget(shortcut_text="Space")
    go.show_shortcut = True
    go.do_draw(cr)

    # MainFaderWidget
    mf = MainFaderWidget(backend=None)
    mf.do_draw(cr)


@pytest.mark.gui
def test_button_widget_text_centering() -> None:
    """Verify ButtonWidget centers single-digit and long texts horizontally."""
    surface = cairo.ImageSurface(cairo.Format.ARGB32, 50, 50)
    cr = cairo.Context(surface)

    for label in ["1", "7", "Group", "Enter", "⌫", "Channel"]:
        btn = ButtonWidget(label=label, text="test")
        btn.do_draw(cr)

        max_width_px = btn.WIDTH - 8
        layout = create_pango_layout_for_widget(cr, label)
        desc = create_system_font_description()
        desc.set_weight(Pango.Weight.BOLD)
        desc.set_size(int(btn.FONT_SIZE * Pango.SCALE))
        layout.set_font_description(desc)

        _ink, natural_logical = layout.get_pixel_extents()
        if natural_logical.width > max_width_px and natural_logical.width > 0:
            scaled_size = max(
                7.0, btn.FONT_SIZE * (max_width_px / natural_logical.width)
            )
            desc.set_size(int(scaled_size * Pango.SCALE))
            layout.set_font_description(desc)

        layout.set_alignment(Pango.Alignment.CENTER)
        layout.set_width(int(max_width_px * Pango.SCALE))
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)

        ink, _logical = layout.get_pixel_extents()
        layout_x = (btn.WIDTH - max_width_px) / 2.0
        ink_left = layout_x + ink.x
        ink_right = ink_left + ink.width
        ink_center = (ink_left + ink_right) / 2.0

        # Must be centered around WIDTH / 2 (25.0) within 1.5px
        assert abs(ink_center - 25.0) <= 1.5, (
            f"Label {label!r} not centered: center={ink_center}"
        )
