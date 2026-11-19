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
"""GUI behavior tests for PalettesTab and PaletteTileWidget."""

# pylint: disable=redefined-outer-name, protected-access, too-many-statements, import-outside-toplevel, too-many-locals

from __future__ import annotations

import pathlib
import typing

import cairo
import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from olc.devices.builtin import create_rgb_definition  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.palettes import (  # noqa: E402
    CATEGORY_SPECS,
    PalettesTab,
    PaletteTileWidget,
    extract_palette_preview_rgb,
)
from olc.show.cue import Cue  # noqa: E402
from olc.show.palette import Palette, PaletteCategory  # noqa: E402
from olc.show.step import Step  # noqa: E402

from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip # pylint: disable=wrong-import-order

pytestmark = pytest.mark.gui


def test_palettes_tab_open_categories_and_counts(app_gui: Application) -> None:
    """Test opening PalettesTab, 5 category pages, counts, and Cairo tile drawing."""
    ls = app_gui.core.lightshow
    ls.palettes.clear()
    ls.palettes.add(
        Palette(PaletteCategory.INTENSITY, 1.0, text="Full", channels={1: 1.0})
    )
    ls.palettes.add(
        Palette(
            PaletteCategory.COLOR,
            2.0,
            text="Blue",
            device_values={2: {"color": "#0000FF"}},
        )
    )
    ls.palettes.add(
        Palette(
            PaletteCategory.PRESET,
            5.0,
            text="Look",
            channels={1: 0.75},
            device_values={2: {"color": (255, 0, 128)}},
        )
    )

    app_gui.activate_action("palettes", None)
    process_events()

    assert app_gui.tabs is not None
    pal_tab = app_gui.tabs.tabs.get("palettes")
    assert isinstance(pal_tab, PalettesTab)

    # All 5 category stack pages are present
    for cat, _prefix, title, _accent in CATEGORY_SPECS:
        sw = pal_tab.scrolled_windows[cat]
        assert pal_tab.stack.child_get_property(sw, "title").startswith(title)
    assert "Color (1)" == pal_tab.stack.child_get_property(
        pal_tab.scrolled_windows[PaletteCategory.COLOR], "title"
    )
    assert "Presets (1)" == pal_tab.stack.child_get_property(
        pal_tab.scrolled_windows[PaletteCategory.PRESET], "title"
    )

    # Color preview helper & Cairo drawing (both with and without color swatch)
    cp2 = ls.palettes.get(PaletteCategory.COLOR, 2.0)
    pr5 = ls.palettes.get(PaletteCategory.PRESET, 5.0)
    assert cp2 is not None and pr5 is not None
    assert extract_palette_preview_rgb(cp2) == pytest.approx((0.0, 0.0, 1.0))
    assert extract_palette_preview_rgb(pr5) == pytest.approx((1.0, 0.0, 128 / 255.0))

    pal_tab.set_active_category(PaletteCategory.COLOR)
    process_events()
    assert pal_tab.current_category is PaletteCategory.COLOR
    color_children = pal_tab.flowbox.get_children()
    assert len(color_children) == 1
    tile = typing.cast(Gtk.FlowBoxChild, color_children[0]).get_child()
    assert isinstance(tile, PaletteTileWidget)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 140, 100)
    cr = cairo.Context(surface)
    tile.do_draw(cr)

    # Render an Intensity tile (accent bar without preview_rgb)
    pal_tab.set_active_category(PaletteCategory.INTENSITY)
    process_events()
    int_tile = typing.cast(
        Gtk.FlowBoxChild, pal_tab.flowbox.get_children()[0]
    ).get_child()
    assert isinstance(int_tile, PaletteTileWidget)
    int_tile.do_draw(cr)


def test_palettes_tab_record_recall_update_rename_delete(
    app_gui: Application,
) -> None:
    """Test Record, Recall, Update, Rename, Delete, and Direct Recall."""
    ls = app_gui.core.lightshow
    ls.palettes.clear()
    ls.patch.patch_device(2, create_rgb_definition(), 1, 10, label="LED 2")
    rgb_dev = ls.patch.devices[2]
    rgb_dev.set_intensity(1.0)
    rgb_dev.set_color_hex("#FF0000")

    app_gui.activate_action("palettes", None)
    process_events()
    assert app_gui.tabs is not None
    pal_tab = app_gui.tabs.tabs.get("palettes")
    assert isinstance(pal_tab, PalettesTab)

    # 1. Switch to Color and Record Palette 2 using command line buffer
    pal_tab.set_active_category(PaletteCategory.COLOR)
    app_gui.core.selected_channels = [2]
    app_gui.core.commandline.set_string("2")
    pal_tab.btn_record.emit("clicked")
    process_events()

    assert app_gui.core.commandline.get_string() == ""
    cp2 = ls.palettes.get(PaletteCategory.COLOR, 2.0)
    assert cp2 is not None
    assert cp2.device_values[2]["color"].upper() == "#FF0000"

    # 2. Record auto-numbered Color Palette 3 (empty command line) with Blue
    rgb_dev.set_color_hex("#0000FF")
    pal_tab.btn_record.emit("clicked")
    process_events()
    cp3 = ls.palettes.get(PaletteCategory.COLOR, 3.0)
    assert cp3 is not None
    assert cp3.device_values[2]["color"].upper() == "#0000FF"

    # 3. Recall CP 2 via child selection + Recall button
    children = pal_tab.flowbox.get_children()
    assert len(children) == 2
    child_cp2 = typing.cast(Gtk.FlowBoxChild, children[0])
    child_cp3 = typing.cast(Gtk.FlowBoxChild, children[1])

    rgb_dev.set_color_hex("#000000")
    pal_tab.flowbox.select_child(child_cp2)
    process_events()
    assert pal_tab.btn_recall.get_sensitive() is True
    pal_tab.btn_recall.emit("clicked")
    process_events()
    assert rgb_dev.color_srgb.r == pytest.approx(1.0, abs=0.05)

    # 4. Recall CP 3 via flowbox child-activated (double-click / Enter)
    pal_tab.flowbox.emit("child-activated", child_cp3)
    process_events()
    assert rgb_dev.color_srgb.b == pytest.approx(1.0, abs=0.05)

    # 5. Direct Recall toggle on click of CP 2
    pal_tab.direct_recall_toggle.set_active(True)
    tile_cp2 = child_cp2.get_child()
    assert isinstance(tile_cp2, PaletteTileWidget)
    ev = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
    tile_cp2.on_click(tile_cp2, ev)
    process_events()
    assert rgb_dev.color_srgb.r == pytest.approx(1.0, abs=0.05)
    pal_tab.direct_recall_toggle.set_active(False)

    # 6. Update CP 2 with cascade propagation to Preset 10 & Cue 1
    pr10 = Palette(
        category=PaletteCategory.PRESET,
        number=10.0,
        text="Show Look",
        device_values={2: {"color": "#FF0000"}},
        palette_refs={2: {"color": ("color", 2.0)}},
    )
    ls.palettes.add(pr10)
    cue1 = Cue(
        sequence=1,
        number=1.0,
        channels={2: 1.0},
        device_values={2: {"color": "#FF0000"}},
        palette_refs={2: {"color": ("color", 2.0)}},
    )
    ls.cues.add(cue1)
    ls.main_playback.add_step(Step(1, cue=cue1))
    pal_tab.refresh()
    process_events()

    pal_tab.flowbox.select_child(
        typing.cast(Gtk.FlowBoxChild, pal_tab.flowbox.get_children()[0])
    )
    rgb_dev.set_color_hex("#00FF00")
    pal_tab.btn_update.emit("clicked")
    process_events()
    assert cp2.device_values[2]["color"].upper() == "#00FF00"
    assert pr10.device_values[2]["color"].upper() == "#00FF00"
    assert cue1.device_values[2]["color"].upper() == "#00FF00"

    # 7. Rename CP 2 via inline popover entry & Undo/Redo
    tile_cp2_fresh = typing.cast(
        Gtk.FlowBoxChild, pal_tab.flowbox.get_children()[0]
    ).get_child()
    assert isinstance(tile_cp2_fresh, PaletteTileWidget)
    tile_cp2_fresh.open_rename_popover()
    tile_cp2_fresh.rename_entry.set_text("Forest Green")
    tile_cp2_fresh.rename_entry.emit("activate")
    process_events()

    assert cp2.text == "Forest Green"
    assert "Forest Green" in pal_tab.details_label.get_text()

    app_gui.activate_action("undo", None)
    process_events()
    assert cp2.text == ""

    app_gui.activate_action("redo", None)
    process_events()
    assert cp2.text == "Forest Green"

    # 8. Delete CP 2 via _keypress_delete & Undo
    pal_tab.flowbox.select_child(
        typing.cast(Gtk.FlowBoxChild, pal_tab.flowbox.get_children()[0])
    )
    process_events()
    pal_tab._keypress_delete()
    process_events()
    assert ls.palettes.get(PaletteCategory.COLOR, 2.0) is None
    assert len(pal_tab.flowbox.get_children()) == 1

    app_gui.activate_action("undo", None)
    process_events()
    assert ls.palettes.get(PaletteCategory.COLOR, 2.0) is not None
    assert len(pal_tab.flowbox.get_children()) == 2


def test_palettes_tab_workspace_persistence(
    app_gui: Application,
    tmp_path: pathlib.Path,
) -> None:
    """Test active_category retention across close/reopen and show save/open."""
    assert app_gui.tabs is not None

    app_gui.open_palettes()
    process_events()
    pal_tab = app_gui.tabs.tabs.get("palettes")
    assert isinstance(pal_tab, PalettesTab)

    pal_tab.set_active_category(PaletteCategory.BEAM)
    process_events()

    save_path = str(tmp_path / "palettes_ws.olc")
    app_gui.core.action_registry.execute("show.save", save_path)
    process_events()

    app_gui.tabs.close_physically("palettes")
    process_events()
    assert app_gui.tabs.tabs.get("palettes") is None

    app_gui.core.action_registry.execute("show.new")
    process_events()

    app_gui.core.action_registry.execute("show.open", save_path)
    process_events()

    restored = app_gui.tabs.tabs.get("palettes")
    assert isinstance(restored, PalettesTab)
    assert restored.current_category is PaletteCategory.BEAM
