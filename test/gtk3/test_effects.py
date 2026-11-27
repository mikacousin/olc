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
"""GTK3 GUI tests for EffectsTab, Cairo 1D/2D visualizer, and FX badges."""

# pylint: disable=protected-access, missing-function-docstring, too-many-locals

from __future__ import annotations

import cairo
import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from olc.core.channel_snapshot import format_family_readout  # noqa: E402
from olc.devices.channel import Channel, ChannelType, FixtureType  # noqa: E402
from olc.devices.device import LightingDevice  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.effects import EffectsTab  # noqa: E402
from olc.gtk3.widgets.channel import _EFFECT_MAGENTA, ChannelWidget  # noqa: E402
from olc.gtk3.widgets.channels_table_view import EFFECT_MAGENTA_HEX  # noqa: E402
from olc.show.effect import BUILTIN_EFFECT_TEMPLATES, DistributeDirection  # noqa: E402
from olc.show.palette import Palette, PaletteCategory  # noqa: E402
from test.gtk3.conftest import process_events  # noqa: E402

pytestmark = pytest.mark.gui


def _patch_spot(app_gui: Application, fixture_id: int, address: int) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=fixture_id,
        fixture_type=FixtureType.MOVING_HEAD,
        label=f"Spot {fixture_id}",
        manufacturer="OLC",
        model="TestSpot",
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
            default_value=128,
        )
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 2,
            channel_type=ChannelType.TILT,
            physical_min=-135.0,
            physical_max=135.0,
            default_value=128,
        )
    )
    dev.add_channel(
        Channel(universe=1, address=address + 3, channel_type=ChannelType.RED)
    )
    dev.add_channel(
        Channel(universe=1, address=address + 4, channel_type=ChannelType.GREEN)
    )
    dev.add_channel(
        Channel(universe=1, address=address + 5, channel_type=ChannelType.BLUE)
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=address + 6,
            channel_type=ChannelType.ZOOM,
            physical_min=10.0,
            physical_max=50.0,
            default_value=64,
        )
    )
    app_gui.core.lightshow.patch.restore_device(dev)
    app_gui.core.lightshow.patch.invalidate_cache()
    return dev


def _draw_widget(widget: Gtk.Widget, width: int = 280, height: int = 220) -> None:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surface)
    widget.do_draw(cr)


def test_effects_tab_open_templates_and_cairo_visualizer(
    app_gui: Application,
) -> None:
    """Test opening EffectsTab, all 10 templates, and Cairo 1D/2D drawing."""
    ls = app_gui.core.lightshow
    ls.effects.clear()

    app_gui.activate_action("effects", None)
    process_events()

    assert app_gui.tabs is not None
    fx_tab = app_gui.tabs.tabs.get("effects")
    assert isinstance(fx_tab, EffectsTab)

    # Empty state draw
    _draw_widget(fx_tab.preview_area)

    # Instantiate all 10 built-in templates from the UI combo
    for idx, tpl_id in enumerate(BUILTIN_EFFECT_TEMPLATES, start=1):
        fx_tab.template_combo.set_active_id(tpl_id)
        eff = fx_tab.create_effect_from_selected_template(number=float(idx))
        assert eff.template_id == tpl_id
        assert ls.effects.get(float(idx)) is not None

    process_events()
    assert len(ls.effects) == 10
    assert len(fx_tab.pool_store) == 10

    # Select Effect 1 (sine_dimmer -> 1D mode) and draw Cairo preview
    fx_tab.select_effect(1.0)
    process_events()
    assert fx_tab.preview_area.effective_mode(fx_tab.get_selected_effect()) == "1d"
    fx_tab.preview_area.step_animation()
    _draw_widget(fx_tab.preview_area)

    # Select Effect 4 (circle -> automatic 2D XY Pan/Tilt mode) and draw Cairo preview
    fx_tab.select_effect(4.0)
    process_events()
    assert fx_tab.preview_area.effective_mode(fx_tab.get_selected_effect()) == "2d"
    fx_tab.preview_area.step_animation()
    _draw_widget(fx_tab.preview_area)


def test_effects_tab_editing_layers_and_global_properties(
    app_gui: Application,
) -> None:
    """Test editing global properties, layers, and Tap Tempo in EffectsTab."""
    ls = app_gui.core.lightshow
    ls.effects.clear()

    app_gui.activate_action("effects", None)
    process_events()
    assert app_gui.tabs is not None
    fx_tab = app_gui.tabs.tabs.get("effects")
    assert isinstance(fx_tab, EffectsTab)

    eff = fx_tab.create_effect(1.0, template_id="circle")
    assert len(eff.layers) == 2

    # Edit global properties, entry/exit modes, and trail via UI controls
    fx_tab.label_entry.set_text("Arena Circle")
    fx_tab.label_entry.activate()
    fx_tab.direction_combo.set_active_id(DistributeDirection.BOUNCE.value)
    fx_tab.groups_spin.set_value(4)
    fx_tab.blocks_spin.set_value(2)
    fx_tab.wings_spin.set_value(2)
    fx_tab.axis_spin.set_value(45.0)
    fx_tab.entry_mode_combo.set_active_id("immediate")
    fx_tab.exit_mode_combo.set_active_id("fade_by_rate")
    fx_tab.trail_spin.set_value(30.0)
    process_events()

    updated = ls.effects.get(1.0)
    assert updated is not None
    assert updated.label == "Arena Circle"
    assert updated.direction == DistributeDirection.BOUNCE
    assert updated.groups == 4
    assert updated.blocks == 2
    assert updated.wings == 2
    assert updated.axis_deg == pytest.approx(45.0)
    assert updated.entry_mode.value == "immediate"
    assert updated.exit_mode.value == "fade_by_rate"
    assert all(ly.duty_cycle == pytest.approx(0.30) for ly in updated.layers)

    # Add and remove a layer
    fx_tab.add_layer("zoom")
    process_events()
    updated = ls.effects.get(1.0)
    assert updated is not None and len(updated.layers) == 3

    # Edit layer size and palette ref via callback handlers
    fx_tab._on_layer_number_edited(Gtk.CellRendererText(), "2", "35.0", "size")
    fx_tab._on_layer_palette_edited(Gtk.CellRendererText(), "2", "BP 1", "low_palette")
    updated = ls.effects.get(1.0)
    assert updated is not None
    assert updated.layers[2].size == pytest.approx(35.0)
    assert updated.layers[2].low_palette == ("beam", 1.0)

    fx_tab.remove_selected_layer()
    process_events()
    updated = ls.effects.get(1.0)
    assert updated is not None and len(updated.layers) == 2

    # Tap tempo
    assert fx_tab.tap_tempo(now=100.0) is None
    bpm = fx_tab.tap_tempo(now=100.5)
    assert bpm == pytest.approx(120.0)


def test_channels_view_displays_fx_badges_in_compact_summary_and_table(
    app_gui: Application,
) -> None:
    """Test FX n badges and Palette + FX readouts in Compact, Summary+, and Table."""
    ls = app_gui.core.lightshow
    ls.effects.clear()
    ls.palettes.clear()
    _patch_spot(app_gui, 1, 1)
    _patch_spot(app_gui, 2, 20)

    # Add Focus Palette 2 ("Stage Center") and Effect 1 ("Circle")
    ls.palettes.add(
        Palette(
            PaletteCategory.FOCUS,
            2.0,
            text="Stage Center",
            device_values={1: {"pan": 20.0, "tilt": -10.0}},
        )
    )
    app_gui.core.action_registry.execute(
        "effect.create", 1.0, template_id="circle", label="Circle"
    )
    app_gui.core.action_registry.execute("palette.apply", "focus", 2.0, channels=[1])
    app_gui.core.action_registry.execute("effect.apply", 1.0, channels=[1, 2])
    process_events()

    assert app_gui.window is not None
    channels_view = app_gui.window.live_view.channels_view
    channels_view.invalidate_all_snapshots()

    snap1 = channels_view.get_channel_snapshot(1)
    assert snap1 is not None
    assert snap1.effect_ref is not None
    assert snap1.effect_ref.short_ref == "FX 1"
    assert snap1.focus.palette_ref is not None
    assert snap1.focus.effect_ref is not None

    # Combined palette + effect readout formatting
    assert format_family_readout(snap1.focus, "Auto") == "Stage Center + FX 1"
    assert format_family_readout(snap1.focus, "Label") == "Stage Center + Circle"
    assert format_family_readout(snap1.focus, "Ref") == "FP 2 + FX 1"

    w1 = channels_view.get_channel_widget(1)
    assert isinstance(w1, ChannelWidget)
    assert w1._get_family_status_rgb(snap1.focus) == _EFFECT_MAGENTA

    # Draw tile in Compact and Summary+ modes
    w1.set_display_format("Compact")
    _draw_widget(w1, 100, 100)
    w1.set_display_format("Summary+")
    _draw_widget(w1, 140, 140)

    # Switch ChannelsView to Table format and check Focus column text & foreground color
    channels_view.set_display_format("Table")
    channels_view.table_view.rebuild_rows(force=True)
    process_events()

    tree_iter = channels_view.table_view._channel_iters.get(1)
    assert tree_iter is not None
    row = channels_view.table_view.store[tree_iter]
    # COL_FOCUS_TEXT = 12, COL_FOCUS_FG = 13
    assert "FX 1" in row[12]
    assert row[13] == EFFECT_MAGENTA_HEX

    # Clean up running effects
    app_gui.core.action_registry.execute("effect.stop")
    channels_view.set_display_format("Compact")
    process_events()


def test_effects_tab_master_bus_selectors(app_gui: Application) -> None:
    """Verify Speed/Rate/Size Master bus selectors in EffectsTab."""
    ls = app_gui.core.lightshow
    ls.effects.clear()

    app_gui.activate_action("effects", None)
    process_events()
    assert app_gui.tabs is not None
    fx_tab = app_gui.tabs.tabs.get("effects")
    assert isinstance(fx_tab, EffectsTab)

    eff = fx_tab.create_effect(1.0, template_id="sine_dimmer")
    fx_tab.select_effect(1.0)
    process_events()

    fx_tab.speed_master_combo.set_active_id("2")
    fx_tab.speed_mult_combo.set_active_id("0.5")
    fx_tab.rate_master_combo.set_active_id("1")
    fx_tab.size_master_combo.set_active_id("3")
    process_events()

    assert eff.speed_master == 2
    assert eff.speed_multiplier == pytest.approx(0.5)
    assert eff.rate_master == 1
    assert eff.size_master == 3

    # Clearing back to "none" sets master fields to None
    fx_tab.speed_master_combo.set_active_id("none")
    fx_tab.rate_master_combo.set_active_id("none")
    fx_tab.size_master_combo.set_active_id("none")
    process_events()

    assert eff.speed_master is None
    assert eff.rate_master is None
    assert eff.size_master is None
