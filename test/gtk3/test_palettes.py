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
import types
import typing

import cairo
import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from olc.devices.builtin import create_rgb_definition  # noqa: E402
from olc.devices.channel import Channel, ChannelType, FixtureType  # noqa: E402
from olc.devices.device import LightingDevice  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.group import GroupTab  # noqa: E402
from olc.gtk3.palettes import (  # noqa: E402
    CATEGORY_SPECS,
    INSP_COL_B,
    INSP_COL_CH,
    INSP_COL_FIXTURE,
    INSP_COL_G,
    INSP_COL_HAS_COLOR,
    INSP_COL_HAS_COLOR_REF,
    INSP_COL_INTENSITY,
    INSP_COL_PARAMS,
    INSP_COL_R,
    INSP_COL_REFS,
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

    # 7. Rename CP 2 via inline popover entry & in-place identity + Undo/Redo
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
    tile_cp2_after_rename = typing.cast(
        Gtk.FlowBoxChild, pal_tab.flowbox.get_children()[0]
    ).get_child()
    assert tile_cp2_after_rename is tile_cp2_fresh

    app_gui.activate_action("undo", None)
    process_events()
    assert cp2.text == ""

    app_gui.activate_action("redo", None)
    process_events()
    assert cp2.text == "Forest Green"

    # Update keeps widget identity too
    pal_tab.flowbox.select_child(
        typing.cast(Gtk.FlowBoxChild, pal_tab.flowbox.get_children()[0])
    )
    rgb_dev.set_color_hex("#123456")
    tile_before_update = typing.cast(
        Gtk.FlowBoxChild, pal_tab.flowbox.get_children()[0]
    ).get_child()
    pal_tab.btn_update.emit("clicked")
    process_events()
    tile_after_update = typing.cast(
        Gtk.FlowBoxChild, pal_tab.flowbox.get_children()[0]
    ).get_child()
    assert tile_after_update is tile_before_update

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
    """Test active_category, Direct Select, Inspector & paned persistence."""
    assert app_gui.tabs is not None

    app_gui.open_palettes()
    app_gui.open_groups()
    process_events()
    pal_tab = app_gui.tabs.tabs.get("palettes")
    grp_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(pal_tab, PalettesTab)
    assert isinstance(grp_tab, GroupTab)

    pal_tab.set_active_category(PaletteCategory.BEAM)
    pal_tab.direct_select_toggle.set_active(True)
    pal_tab.set_inspector_visible(False)
    pal_tab.set_position(210)
    grp_tab.direct_select_toggle.set_active(True)
    grp_tab.set_position(390)
    process_events()

    save_path = str(tmp_path / "palettes_ws.olc")
    app_gui.core.action_registry.execute("show.save", save_path)
    process_events()

    app_gui.tabs.close_physically("palettes")
    app_gui.tabs.close_physically("groups")
    process_events()
    assert app_gui.tabs.tabs.get("palettes") is None

    app_gui.core.action_registry.execute("show.new")
    process_events()

    app_gui.core.action_registry.execute("show.open", save_path)
    process_events()

    restored = app_gui.tabs.tabs.get("palettes")
    restored_grp = app_gui.tabs.tabs.get("groups")
    assert isinstance(restored, PalettesTab)
    assert isinstance(restored_grp, GroupTab)
    assert restored.current_category is PaletteCategory.BEAM
    assert restored.direct_select_toggle.get_active() is True
    assert restored.is_inspector_visible() is False
    assert restored.get_position() == 210
    assert restored_grp.direct_select_toggle.get_active() is True
    assert restored_grp.get_position() == 390


def test_palettes_tab_direct_select_double_click_select_live_and_fallback(
    app_gui: Application,
) -> None:
    """Test Direct Select alias, double-click, Select Live, and empty/disjoint."""
    ls = app_gui.core.lightshow
    ls.palettes.clear()
    dev1 = ls.patch.patch_device(1, create_rgb_definition(), 1, 1, label="LED 1")
    dev2 = ls.patch.patch_device(2, create_rgb_definition(), 1, 10, label="LED 2")
    dev1.set_color_hex("#000000")
    dev2.set_color_hex("#000000")

    ls.palettes.add(
        Palette(
            PaletteCategory.COLOR,
            1.0,
            text="Crimson",
            device_values={1: {"color": "#FF0000"}, 2: {"color": "#FF0000"}},
        )
    )
    ls.palettes.add(Palette(PaletteCategory.COLOR, 2.0, text="EmptyCP"))

    app_gui.activate_action("palettes", None)
    process_events()
    assert app_gui.tabs is not None
    pal_tab = app_gui.tabs.tabs.get("palettes")
    assert isinstance(pal_tab, PalettesTab)
    assert pal_tab.direct_select_toggle is pal_tab.direct_recall_toggle

    pal_tab.set_active_category(PaletteCategory.COLOR)
    process_events()
    children = pal_tab.flowbox.get_children()
    tile1 = typing.cast(Gtk.FlowBoxChild, children[0]).get_child()
    tile2 = typing.cast(Gtk.FlowBoxChild, children[1]).get_child()
    assert isinstance(tile1, PaletteTileWidget)
    assert isinstance(tile2, PaletteTileWidget)

    # 1. Direct Select OFF: single click inspects only without applying Red
    pal_tab.direct_select_toggle.set_active(False)
    app_gui.core.selected_channels = []
    tile1.on_click(
        tile1,
        typing.cast(Gdk.Event, types.SimpleNamespace(type=Gdk.EventType.BUTTON_PRESS)),
    )
    process_events()
    assert dev1.color_srgb.r == pytest.approx(0.0, abs=0.05)

    # 2. Direct Select OFF + double-click + empty Live selection recalls all chs
    tile1.on_click(
        tile1,
        typing.cast(Gdk.Event, types.SimpleNamespace(type=Gdk.EventType(5))),
    )
    process_events()
    assert dev1.color_srgb.r == pytest.approx(1.0, abs=0.05)
    assert dev2.color_srgb.r == pytest.approx(1.0, abs=0.05)

    # 3. Select Live recalls stored channels [1, 2] into Live selection
    app_gui.core.selected_channels = []
    pal_tab.btn_select_live.clicked()
    process_events()
    assert app_gui.core.selected_channels == [1, 2]

    # 4. Disjoint Live selection shows helpful status and touches 0 fixtures
    dev1.set_color_hex("#000000")
    app_gui.core.selected_channels = [99]
    affected = pal_tab.recall_palette(PaletteCategory.COLOR, 1.0)
    process_events()
    assert affected == []
    assert dev1.color_srgb.r == pytest.approx(0.0, abs=0.05)
    assert "CP 1" in pal_tab.details_label.get_text()
    assert "1, 2" in pal_tab.details_label.get_text()

    # 5. Empty palette displays informative message
    app_gui.core.selected_channels = []
    affected_empty = pal_tab.recall_palette(PaletteCategory.COLOR, 2.0)
    process_events()
    assert affected_empty == []
    assert "CP 2" in pal_tab.details_label.get_text()


def test_palettes_tab_inspector_panel_and_channel_removal(
    app_gui: Application,
) -> None:
    """Test Inspector rows, CMY swatches, Select Ch, row-activated, and Remove Ch."""
    ls = app_gui.core.lightshow
    ls.palettes.clear()

    dim = LightingDevice(
        fixture_id=1,
        fixture_type=FixtureType.DIMMER,
        label="Dim 1",
        manufacturer="Generic",
        model="Dimmer",
    )
    dim.add_channel(Channel(universe=1, address=1, channel_type=ChannelType.INTENSITY))
    ls.patch.restore_device(dim)

    spot = LightingDevice(
        fixture_id=2,
        fixture_type=FixtureType.MOVING_HEAD,
        label="Spot 2",
        manufacturer="ACME",
        model="CMY Spot",
    )
    spot.add_channel(Channel(universe=1, address=2, channel_type=ChannelType.INTENSITY))
    spot.add_channel(Channel(universe=1, address=3, channel_type=ChannelType.PAN))
    spot.add_channel(Channel(universe=1, address=4, channel_type=ChannelType.CYAN))
    spot.add_channel(Channel(universe=1, address=5, channel_type=ChannelType.MAGENTA))
    spot.add_channel(Channel(universe=1, address=6, channel_type=ChannelType.YELLOW))
    ls.patch.restore_device(spot)

    ls.palettes.add(
        Palette(
            PaletteCategory.INTENSITY, 1.0, text="Three Quarters", channels={1: 0.75}
        )
    )
    ls.palettes.add(
        Palette(
            PaletteCategory.COLOR,
            2.0,
            text="Cool Cyan",
            device_values={2: {"cyan": 0.5, "magenta": 0.25, "yellow": 0.0}},
        )
    )
    ls.palettes.add(
        Palette(
            PaletteCategory.PRESET,
            5.0,
            text="Preset Look",
            channels={1: 0.75},
            device_values={
                2: {"pan": 30.0, "cyan": 0.5, "magenta": 0.25, "yellow": 0.0}
            },
            palette_refs={
                1: {"intensity": ("intensity", 1.0)},
                2: {
                    "cyan": ("color", 2.0),
                    "magenta": ("color", 2.0),
                    "yellow": ("color", 2.0),
                },
            },
        )
    )

    app_gui.activate_action("palettes", None)
    process_events()
    assert app_gui.tabs is not None
    pal_tab = app_gui.tabs.tabs.get("palettes")
    assert isinstance(pal_tab, PalettesTab)

    pal_tab.set_active_category(PaletteCategory.PRESET)
    process_events()
    pr5_child = typing.cast(Gtk.FlowBoxChild, pal_tab.flowbox.get_children()[0])
    pal_tab.flowbox.select_child(pr5_child)
    process_events()

    assert pal_tab.is_inspector_visible() is True
    assert "PR 5" in pal_tab.inspector_title_label.get_text()
    assert "Preset Look" in pal_tab.inspector_title_label.get_text()
    assert len(pal_tab.inspector_store) == 2

    # Row 0: Ch 1 Dimmer
    r0 = pal_tab.inspector_store[0]
    assert r0[INSP_COL_CH] == 1
    assert r0[INSP_COL_FIXTURE] == "Dim 1"
    assert r0[INSP_COL_INTENSITY] == "75%"
    assert r0[INSP_COL_HAS_COLOR] is False
    assert "IP 1" in r0[INSP_COL_REFS]

    # Row 1: Ch 2 CMY Spot
    r1 = pal_tab.inspector_store[1]
    assert r1[INSP_COL_CH] == 2
    assert r1[INSP_COL_FIXTURE] == "Spot 2"
    assert r1[INSP_COL_HAS_COLOR] is True
    assert r1[INSP_COL_R] == pytest.approx(0.5, abs=0.02)
    assert r1[INSP_COL_G] == pytest.approx(0.75, abs=0.02)
    assert r1[INSP_COL_B] == pytest.approx(1.0, abs=0.02)
    assert r1[INSP_COL_HAS_COLOR_REF] is True
    assert "pan=30°" in r1[INSP_COL_PARAMS]
    assert "CP 2" in r1[INSP_COL_REFS]

    # Select row 0 -> Select Ch selects [1] in Live
    pal_tab.inspector_selection.unselect_all()
    pal_tab.inspector_selection.select_path(Gtk.TreePath.new_from_indices([0]))
    process_events()
    assert pal_tab.btn_inspector_select_ch.get_sensitive() is True
    assert pal_tab.btn_inspector_remove_ch.get_sensitive() is True
    pal_tab.btn_inspector_select_ch.clicked()
    process_events()
    assert app_gui.core.selected_channels == [1]

    # Row activation selects row's channel ([2]) in Live
    col0 = pal_tab.inspector_view.get_column(0)
    assert col0 is not None
    pal_tab.inspector_view.emit(
        "row-activated", Gtk.TreePath.new_from_indices([1]), col0
    )
    process_events()
    assert app_gui.core.selected_channels == [2]

    # Remove Ch removes highlighted ch 1 cleanly with Undo/Redo
    pal_tab.inspector_selection.unselect_all()
    pal_tab.inspector_selection.select_path(Gtk.TreePath.new_from_indices([0]))
    process_events()
    pal_tab.btn_inspector_remove_ch.clicked()
    process_events()

    pr5_model = ls.palettes.get(PaletteCategory.PRESET, 5.0)
    assert pr5_model is not None
    assert 1 not in pr5_model.channels
    assert len(pal_tab.inspector_store) == 1

    app_gui.activate_action("undo", None)
    process_events()
    pr5_undo = ls.palettes.get(PaletteCategory.PRESET, 5.0)
    assert pr5_undo is not None and 1 in pr5_undo.channels
    assert len(pal_tab.inspector_store) == 2

    app_gui.activate_action("redo", None)
    process_events()
    assert len(pal_tab.inspector_store) == 1

    # Toggle visibility via inspector_toggle
    pal_tab.inspector_toggle.set_active(False)
    process_events()
    assert pal_tab.is_inspector_visible() is False
    pal_tab.set_inspector_visible(True)
    process_events()
    assert pal_tab.is_inspector_visible() is True


def test_palettes_tab_keyboard_navigation(
    app_gui: Application,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Left/Right/Up/Down/Q/W navigation across PaletteTileWidgets."""
    ls = app_gui.core.lightshow
    ls.palettes.clear()
    for idx in range(1, 5):
        ls.palettes.add(
            Palette(
                PaletteCategory.COLOR,
                float(idx),
                text=f"C{idx}",
                device_values={1: {"color": "#FFFFFF"}},
            )
        )

    app_gui.activate_action("palettes", None)
    process_events()
    assert app_gui.tabs is not None
    pal_tab = app_gui.tabs.tabs.get("palettes")
    assert isinstance(pal_tab, PalettesTab)
    pal_tab.set_active_category(PaletteCategory.COLOR)
    process_events()

    pal_tab._keypress_right()
    sel = pal_tab.get_selected_palette()
    assert sel is not None and sel.number == 1.0

    pal_tab._keypress_w()
    sel = pal_tab.get_selected_palette()
    assert sel is not None and sel.number == 2.0

    pal_tab._keypress_right()
    sel = pal_tab.get_selected_palette()
    assert sel is not None and sel.number == 3.0

    pal_tab._keypress_left()
    sel = pal_tab.get_selected_palette()
    assert sel is not None and sel.number == 2.0

    pal_tab._keypress_q()
    sel = pal_tab.get_selected_palette()
    assert sel is not None and sel.number == 1.0

    # Exercise Up/Down row lookup deterministically via FlowBox allocations
    children = pal_tab.flowbox.get_children()
    c0 = typing.cast(Gtk.FlowBoxChild, children[0])
    c2 = typing.cast(Gtk.FlowBoxChild, children[2])
    alloc0 = Gdk.Rectangle()
    alloc0.x, alloc0.y, alloc0.width, alloc0.height = 10, 10, 116, 78
    alloc2 = Gdk.Rectangle()
    alloc2.x, alloc2.y, alloc2.width, alloc2.height = 10, 94, 116, 78
    monkeypatch.setattr(c0, "get_allocation", lambda: alloc0)
    monkeypatch.setattr(c2, "get_allocation", lambda: alloc2)
    monkeypatch.setattr(
        pal_tab.flowbox,
        "get_child_at_pos",
        lambda _x, y: c2 if y > 80 else c0,
    )

    pal_tab._keypress_down()
    sel = pal_tab.get_selected_palette()
    assert sel is not None and sel.number == 3.0

    pal_tab._keypress_up()
    sel = pal_tab.get_selected_palette()
    assert sel is not None and sel.number == 1.0
