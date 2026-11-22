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
"""GTK3 GUI tests for Hybrid Table view, dynamic F/C/B columns, and swatches."""

# pylint: disable=protected-access, missing-function-docstring, too-many-locals

from __future__ import annotations

import time
from unittest.mock import MagicMock

import cairo
import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from olc.core.selection import SelectAddAction  # noqa: E402
from olc.devices.channel import Channel, ChannelType, FixtureType  # noqa: E402
from olc.devices.device import LightingDevice  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.cue import CuesEditionTab  # noqa: E402
from olc.gtk3.device_inspector import DeviceInspectorWidget  # noqa: E402
from olc.gtk3.widgets.channels_table_view import (  # noqa: E402
    COL_BEAM_TEXT,
    COL_CHANNEL,
    COL_COLOR_FG,
    COL_COLOR_HAS_REF,
    COL_COLOR_TEXT,
    COL_FIXTURE,
    COL_FOCUS_FG,
    COL_FOCUS_TEXT,
    COL_HAS_COLOR,
    COL_SWATCH_B,
    COL_SWATCH_G,
    COL_SWATCH_R,
    DEFAULT_TEXT_HEX,
    MANUAL_CORAL_HEX,
    PALETTE_CYAN_HEX,
)
from olc.show.cue import Cue  # noqa: E402
from olc.show.palette import Palette, PaletteCategory  # noqa: E402
from test.gtk3.conftest import process_events  # noqa: E402

pytestmark = pytest.mark.gui


def _add_dimmer(app_gui: Application, fixture_id: int, address: int) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=fixture_id,
        fixture_type=FixtureType.DIMMER,
        label=f"Dim {fixture_id}",
        manufacturer="Generic",
        model="Dimmer",
    )
    dev.add_channel(
        Channel(universe=1, address=address, channel_type=ChannelType.INTENSITY)
    )
    app_gui.core.lightshow.patch.restore_device(dev)
    return dev


def _add_rgbw_fixture(
    app_gui: Application, fixture_id: int, address: int
) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=fixture_id,
        fixture_type=FixtureType.LED_PAR,
        label=f"LED {fixture_id}",
        manufacturer="Generic",
        model="RGBW",
    )
    dev.add_channel(Channel(universe=1, address=address, channel_type=ChannelType.RED))
    dev.add_channel(
        Channel(universe=1, address=address + 1, channel_type=ChannelType.GREEN)
    )
    dev.add_channel(
        Channel(universe=1, address=address + 2, channel_type=ChannelType.BLUE)
    )
    dev.add_channel(
        Channel(universe=1, address=address + 3, channel_type=ChannelType.WHITE)
    )
    app_gui.core.lightshow.patch.restore_device(dev)
    return dev


def _add_cmy_spot(
    app_gui: Application, fixture_id: int, address: int
) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=fixture_id,
        fixture_type=FixtureType.MOVING_HEAD,
        label=f"Spot {fixture_id}",
        manufacturer="ACME",
        model="CMY Spot",
    )
    dev.add_channel(
        Channel(universe=1, address=address, channel_type=ChannelType.INTENSITY)
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 1,
            channel_type=ChannelType.PAN,
            physical_min=-270.0,
            physical_max=270.0,
        )
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 2,
            channel_type=ChannelType.TILT,
            physical_min=-135.0,
            physical_max=135.0,
        )
    )
    dev.add_channel(
        Channel(universe=1, address=address + 3, channel_type=ChannelType.CYAN)
    )
    dev.add_channel(
        Channel(universe=1, address=address + 4, channel_type=ChannelType.MAGENTA)
    )
    dev.add_channel(
        Channel(universe=1, address=address + 5, channel_type=ChannelType.YELLOW)
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 6,
            channel_type=ChannelType.ZOOM,
            physical_min=10.0,
            physical_max=50.0,
        )
    )
    app_gui.core.lightshow.patch.restore_device(dev)
    return dev


def test_table_view_stack_switch_base_columns_and_swatch_render(
    app_gui: Application,
) -> None:
    """Switch to Table format, verify 7 base columns, CMY row data & swatch draw."""
    _add_dimmer(app_gui, 1, 1)
    led = _add_rgbw_fixture(app_gui, 2, 10)
    _add_cmy_spot(app_gui, 3, 20)

    led.set_color_srgb(1.0, 0.2, 0.4)
    app_gui.core.lightshow.palettes.add(
        Palette(
            PaletteCategory.COLOR,
            2.5,
            "Deep Cyan",
            device_values={3: {"cyan": 0.5, "magenta": 0.25, "yellow": 0.0}},
        )
    )
    app_gui.core.action_registry.execute("palette.apply", "color", 2.5, channels=[3])
    process_events()

    assert app_gui.window is not None
    live_cv = app_gui.window.live_view.channels_view
    live_cv.set_view_mode_by_name("Patched")
    process_events()

    assert live_cv.expand_box.get_visible() is False
    assert live_cv.content_stack.get_visible_child_name() == "tiles"

    # Switch to Table via combo index 2
    live_cv.format_combo.set_active(2)
    process_events()

    assert live_cv.get_display_format() == "Table"
    assert live_cv.expand_box.get_visible() is True
    assert live_cv.content_stack.get_visible_child_name() == "table"

    tv = live_cv.table_view
    assert tv.get_column_titles() == [
        "Ch",
        "Fixture / Label",
        "Int",
        "Color",
        "Focus",
        "Beam",
        "Address",
    ]
    assert len(tv.store) == 3

    # Row 0 = Dimmer (no color)
    assert tv.store[0][COL_CHANNEL] == 1
    assert tv.store[0][COL_FIXTURE] == "Dim 1"
    assert tv.store[0][COL_HAS_COLOR] is False

    # Row 2 = CMY Spot with linked Deep Cyan CP 2.5
    assert tv.store[2][COL_CHANNEL] == 3
    assert tv.store[2][COL_HAS_COLOR] is True
    assert tv.store[2][COL_SWATCH_R] == pytest.approx(0.5, abs=0.02)
    assert tv.store[2][COL_SWATCH_G] == pytest.approx(0.75, abs=0.02)
    assert tv.store[2][COL_SWATCH_B] == pytest.approx(1.0, abs=0.02)
    assert tv.store[2][COL_COLOR_HAS_REF] is True
    assert tv.store[2][COL_COLOR_TEXT] == "Deep Cyan"
    assert tv.store[2][COL_COLOR_FG] == PALETTE_CYAN_HEX

    # Exercise ColorSwatchCellRenderer Cairo rendering (both linked & unlinked)
    surface = cairo.ImageSurface(cairo.Format.ARGB32, 60, 40)
    cr = cairo.Context(surface)
    area = Gdk.Rectangle()
    area.x, area.y, area.width, area.height = 0, 0, 28, 22
    assert tv.swatch_renderer.do_get_size(tv.treeview, area) == (0, 0, 24, 18)

    tv.swatch_renderer.has_color = True
    tv.swatch_renderer.rgb = (0.5, 0.75, 1.0)
    tv.swatch_renderer.has_palette_ref = True
    tv.swatch_renderer.is_manual = False
    tv.swatch_renderer.do_render(cr, tv.treeview, area, area, Gtk.CellRendererState(0))

    tv.swatch_renderer.has_palette_ref = False
    tv.swatch_renderer.is_manual = True
    tv.swatch_renderer.do_render(cr, tv.treeview, area, area, Gtk.CellRendererState(0))


def test_table_view_dynamic_expand_fcb_columns_from_patch(
    app_gui: Application,
) -> None:
    """Expand/collapse F/C/B dynamically creates only columns used by the patch."""
    _add_rgbw_fixture(app_gui, 2, 10)
    _add_cmy_spot(app_gui, 3, 20)

    assert app_gui.window is not None
    live_cv = app_gui.window.live_view.channels_view
    live_cv.set_view_mode_by_name("Patched")
    live_cv.set_display_format("Table")
    process_events()

    tv = live_cv.table_view

    # Toggle F -> Pan, Tilt inserted immediately after Focus
    live_cv.expand_focus_btn.set_active(True)
    process_events()
    assert tv.get_column_titles() == [
        "Ch",
        "Fixture / Label",
        "Int",
        "Color",
        "Focus",
        "Pan",
        "Tilt",
        "Beam",
        "Address",
    ]

    # Toggle C -> RGBW + CMY (no Amber/Lime/CCT) inserted immediately after Color
    live_cv.expand_color_btn.set_active(True)
    process_events()
    titles_c = tv.get_column_titles()
    assert "Amber" not in titles_c
    assert "CCT" not in titles_c
    color_idx = titles_c.index("Color")
    assert titles_c[color_idx + 1 : color_idx + 8] == [
        "Red",
        "Green",
        "Blue",
        "White",
        "Cyan",
        "Magenta",
        "Yellow",
    ]

    # Toggle B -> only Zoom (no Shutter/Gobo/Prism yet)
    live_cv.expand_beam_btn.set_active(True)
    process_events()
    titles_b = tv.get_column_titles()
    beam_idx = titles_b.index("Beam")
    assert titles_b[beam_idx + 1] == "Zoom"
    assert "Shutter" not in titles_b

    # Patch a new fixture carrying Amber + Strobe and trigger update -> columns grow
    extra = LightingDevice(
        fixture_id=4,
        fixture_type=FixtureType.LED_PAR,
        label="Wash 4",
        manufacturer="Generic",
        model="AmberStrobe",
    )
    extra.add_channel(Channel(universe=1, address=40, channel_type=ChannelType.AMBER))
    extra.add_channel(Channel(universe=1, address=41, channel_type=ChannelType.STROBE))
    app_gui.core.lightshow.patch.restore_device(extra)
    live_cv.update()
    process_events()

    titles_ext = tv.get_column_titles()
    assert "Amber" in titles_ext
    assert "Shutter" in titles_ext

    # Collapse all back to base 7 columns
    live_cv.expand_focus_btn.set_active(False)
    live_cv.expand_color_btn.set_active(False)
    live_cv.expand_beam_btn.set_active(False)
    process_events()
    assert tv.get_column_titles() == [
        "Ch",
        "Fixture / Label",
        "Int",
        "Color",
        "Focus",
        "Beam",
        "Address",
    ]


def test_table_view_readout_modes_and_palette_cyan_markers(
    app_gui: Application,
) -> None:
    """Summary & expanded sub-columns follow Readout with cyan/coral markers."""
    _add_cmy_spot(app_gui, 3, 1)
    app_gui.core.lightshow.palettes.add(
        Palette(
            PaletteCategory.FOCUS,
            1.0,
            "US Center",
            device_values={3: {"pan": 20.0, "tilt": -10.0}},
        )
    )
    app_gui.core.lightshow.palettes.add(
        Palette(
            PaletteCategory.COLOR,
            2.5,
            "Deep Cyan",
            device_values={3: {"cyan": 0.5, "magenta": 0.25, "yellow": 0.0}},
        )
    )
    app_gui.core.action_registry.execute("palette.apply", "focus", 1.0, channels=[3])
    app_gui.core.action_registry.execute("palette.apply", "color", 2.5, channels=[3])
    app_gui.core.action_registry.execute(
        "device.set_parameter", "zoom", 24.0, channels=[3], is_physical=True
    )
    process_events()

    assert app_gui.window is not None
    live_cv = app_gui.window.live_view.channels_view
    live_cv.set_view_mode_by_name("Patched")
    live_cv.set_display_format("Table")
    live_cv.set_family_expanded("focus", True)
    live_cv.set_family_expanded("color", True)
    live_cv.set_family_expanded("beam", True)
    process_events()

    tv = live_cv.table_view

    # Auto / Label: Palette labels in Cyan, manual Zoom in Coral
    assert tv.store[0][COL_FOCUS_TEXT] == "US Center"
    assert tv.store[0][COL_FOCUS_FG] == PALETTE_CYAN_HEX
    assert tv.store[0][COL_COLOR_TEXT] == "Deep Cyan"
    assert tv.store[0][COL_COLOR_FG] == PALETTE_CYAN_HEX
    assert "24°" in tv.store[0][COL_BEAM_TEXT]
    assert tv.get_param_cell_data(3, "focus", "pan") == ("US Center", PALETTE_CYAN_HEX)
    assert tv.get_param_cell_data(3, "color", "cyan") == (
        "Deep Cyan",
        PALETTE_CYAN_HEX,
    )
    assert tv.get_param_cell_data(3, "beam", "zoom") == ("24°", MANUAL_CORAL_HEX)

    # Ref mode: concise CP / FP IDs in Cyan
    live_cv.set_readout_mode("Ref")
    process_events()
    assert tv.store[0][COL_FOCUS_TEXT] == "FP 1"
    assert tv.store[0][COL_COLOR_TEXT] == "CP 2.5"
    assert tv.get_param_cell_data(3, "color", "cyan") == ("CP 2.5", PALETTE_CYAN_HEX)

    # Percent mode
    live_cv.set_readout_mode("Percent")
    process_events()
    assert "%" in tv.store[0][COL_COLOR_TEXT]
    pct_cyan, _ = tv.get_param_cell_data(3, "color", "cyan")
    assert pct_cyan == "50%"

    # DMX mode
    live_cv.set_readout_mode("DMX")
    process_events()
    dmx_cyan, fg_dmx = tv.get_param_cell_data(3, "color", "cyan")
    assert int(dmx_cyan) in (127, 128)
    assert fg_dmx in (MANUAL_CORAL_HEX, DEFAULT_TEXT_HEX)


def test_table_view_coalesced_30fps_targeted_row_updates(
    app_gui: Application,
) -> None:
    """Rapid color transition burst updates only dirty rows once per 30fps tick."""
    rgb1 = _add_rgbw_fixture(app_gui, 1, 1)
    _add_rgbw_fixture(app_gui, 2, 10)

    assert app_gui.window is not None
    live_cv = app_gui.window.live_view.channels_view
    live_cv.set_view_mode_by_name("Patched")
    live_cv.set_display_format("Table")
    process_events()
    live_cv.flush_dirty_channels()
    process_events()

    tv = live_cv.table_view
    w1 = live_cv.get_channel_widget(1)
    assert w1 is not None
    w1.queue_draw = MagicMock(wraps=w1.queue_draw)  # type: ignore[method-assign]

    row_changes: list[int] = []

    def _on_row_changed(
        model: Gtk.TreeModel, _path: Gtk.TreePath, tree_iter: Gtk.TreeIter
    ) -> None:
        row_changes.append(int(model[tree_iter][COL_CHANNEL]))

    handler_id = tv.store.connect("row-changed", _on_row_changed)
    try:
        live_cv._redraw_interval_ms = 25
        for step in range(1, 21):
            frac = step / 20.0
            rgb1.set_color_srgb(1.0 - frac, 0.0, frac)
            app_gui.core.emit("device.color_changed", [1])
        process_events()

        # Coalesced timer is armed; no row-changed flood yet
        assert live_cv._redraw_timer_id is not None
        assert row_changes == []

        time.sleep(0.045)
        process_events()

        assert live_cv._redraw_timer_id is None
        # Only channel 1 updated cleanly once; channel 2 untouched; tile draw skipped
        assert row_changes == [1]
        assert w1.queue_draw.call_count == 0
        assert tv.store[0][COL_SWATCH_R] == pytest.approx(0.0, abs=0.02)
        assert tv.store[0][COL_SWATCH_B] == pytest.approx(1.0, abs=0.02)
    finally:
        tv.store.disconnect(handler_id)


def test_table_view_selection_sync_with_tiles_inspector_and_isolation(
    app_gui: Application,
) -> None:
    """Sync selection across Table <-> FlowBox <-> DeviceInspector and Cue isolation."""
    rgb1 = _add_rgbw_fixture(app_gui, 1, 1)
    _add_cmy_spot(app_gui, 2, 10)
    rgb1.set_color_srgb(0.0, 0.0, 1.0)  # Live ch 1 = Blue

    app_gui.activate_action("device_inspector", None)
    process_events()
    assert app_gui.tabs is not None
    inspector = app_gui.tabs.tabs.get("device_inspector")
    assert isinstance(inspector, DeviceInspectorWidget)

    assert app_gui.window is not None
    live_cv = app_gui.window.live_view.channels_view
    live_cv.set_view_mode_by_name("Patched")
    live_cv.set_display_format("Table")
    process_events()

    tv = live_cv.table_view
    it0 = tv.store.get_iter_first()
    assert it0 is not None
    tv.selection.select_iter(it0)
    process_events()

    assert app_gui.core.selected_channels == [1]
    fb_child0 = live_cv.flowbox.get_child_at_index(0)
    assert fb_child0 is not None and fb_child0.is_selected() is True
    assert [d.fixture_id for d in inspector.selected_devices] == [1]

    # Add ch 2 from Core SelectionManager -> Table + FlowBox + Inspector all sync
    live_cv.selection_manager.execute_action(SelectAddAction, 2)
    process_events()
    assert app_gui.core.selected_channels == [1, 2]
    _model, paths = tv.selection.get_selected_rows()
    assert [int(tv.store[p][COL_CHANNEL]) for p in paths] == [1, 2]
    assert [d.fixture_id for d in inspector.selected_devices] == [1, 2]

    # Switch back to Compact -> selection preserved cleanly
    live_cv.set_display_format("Compact")
    process_events()
    fb_child1 = live_cv.flowbox.get_child_at_index(1)
    assert fb_child0.is_selected() is True
    assert fb_child1 is not None and fb_child1.is_selected() is True

    # CueChannelsView in Table mode stays isolated from Live Blue
    cue = Cue(
        0,
        1.0,
        {1: 0.9},
        "Red Cue",
        device_values={1: {"intensity": 0.9, "color": "#FF0000"}},
    )
    app_gui.core.lightshow.cues.append(cue)
    app_gui.activate_action("cues", None)
    process_events()
    app_gui.core.action_registry.execute("cue.select", (1.0, 0))
    process_events()

    cues_tab = app_gui.tabs.tabs.get("cues")
    assert isinstance(cues_tab, CuesEditionTab)
    cues_tab.channels_view.set_view_mode_by_name("Patched")
    cues_tab.channels_view.set_display_format("Table")
    process_events()

    cues_tv = cues_tab.channels_view.table_view
    assert len(cues_tv.store) == 2
    assert cues_tv.store[0][COL_CHANNEL] == 1
    assert cues_tv.store[0][COL_SWATCH_R] == pytest.approx(1.0, abs=0.02)
    assert cues_tv.store[0][COL_SWATCH_B] == pytest.approx(0.0, abs=0.02)
