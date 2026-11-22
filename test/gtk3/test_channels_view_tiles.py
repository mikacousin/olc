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
"""GTK3 GUI tests for channels tiles: Compact/Summary+, Readout, coalescing."""

# pylint: disable=protected-access, missing-function-docstring, too-many-locals

from __future__ import annotations

import time
from unittest.mock import MagicMock

import cairo
import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango  # noqa: E402

from olc.core.channel_snapshot import format_family_readout  # noqa: E402
from olc.devices.channel import Channel, ChannelType, FixtureType  # noqa: E402
from olc.devices.device import LightingDevice  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.cue import CuesEditionTab  # noqa: E402
from olc.gtk3.sequence import SequenceTab  # noqa: E402
from olc.gtk3.widgets import channel as channel_widget_mod  # noqa: E402
from olc.gtk3.widgets.channel import ChannelWidget  # noqa: E402
from olc.gtk3.widgets.common import TextAnchor  # noqa: E402
from olc.gtk3.zoom import zoom  # noqa: E402
from olc.show.cue import Cue  # noqa: E402
from olc.show.palette import Palette, PaletteCategory  # noqa: E402
from olc.show.step import Step  # noqa: E402
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


def _add_rgb_fixture(
    app_gui: Application, fixture_id: int, address: int
) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=fixture_id,
        fixture_type=FixtureType.LED_PAR,
        label=f"LED {fixture_id}",
        manufacturer="Generic",
        model="RGB",
    )
    dev.add_channel(Channel(universe=1, address=address, channel_type=ChannelType.RED))
    dev.add_channel(
        Channel(universe=1, address=address + 1, channel_type=ChannelType.GREEN)
    )
    dev.add_channel(
        Channel(universe=1, address=address + 2, channel_type=ChannelType.BLUE)
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
        Channel(universe=1, address=address + 1, channel_type=ChannelType.PAN)
    )
    dev.add_channel(
        Channel(universe=1, address=address + 2, channel_type=ChannelType.TILT)
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
        Channel(universe=1, address=address + 6, channel_type=ChannelType.ZOOM)
    )
    app_gui.core.lightshow.patch.restore_device(dev)
    return dev


def _draw_to_surface(widget: ChannelWidget) -> None:
    surface = cairo.ImageSurface(cairo.Format.ARGB32, 260, 260)
    cr = cairo.Context(surface)
    widget.do_draw(cr)


def test_channels_view_compact_and_summary_plus_rendering(
    app_gui: Application,
) -> None:
    """Test Compact and Summary+ tile modes, CMY preview, badges, and Cairo draw."""
    _add_dimmer(app_gui, 1, 1)
    led = _add_rgb_fixture(app_gui, 2, 10)
    spot = _add_cmy_spot(app_gui, 3, 20)

    led.set_color_srgb(1.0, 0.2, 0.4)
    # CMY -> RGB preview: C=0.5, M=0.25, Y=0.0 => (0.5, 0.75, 1.0)
    spot.set_parameter_normalized(ChannelType.CYAN, 0.5)
    spot.set_parameter_normalized(ChannelType.MAGENTA, 0.25)
    spot.set_parameter_normalized(ChannelType.YELLOW, 0.0)

    app_gui.core.lightshow.palettes.add(
        Palette(
            PaletteCategory.FOCUS,
            1.0,
            "US Center",
            device_values={3: {"pan": 10.0, "tilt": -5.0}},
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
    app_gui.core.action_registry.execute("channel.park", [1], 0.75)
    process_events()

    assert app_gui.window is not None
    live_cv = app_gui.window.live_view.channels_view
    w1 = live_cv.get_channel_widget(1)
    w2 = live_cv.get_channel_widget(2)
    w3 = live_cv.get_channel_widget(3)
    assert w1 is not None and w2 is not None and w3 is not None

    # Default Compact geometry
    assert live_cv.get_display_format() == "Compact"
    assert (w1.width, w1.height) == (80, 80)
    assert w3.has_color_capability() is True
    assert w3.get_preview_rgb() == pytest.approx((0.5, 0.75, 1.0), abs=0.02)

    snap3 = w3.get_snapshot()
    assert snap3 is not None
    assert snap3.focus.palette_ref is not None
    assert snap3.focus.palette_ref.label == "US Center"
    assert snap3.color.palette_ref is not None
    assert snap3.color.palette_ref.label == "Deep Cyan"
    assert snap3.beam.is_manual is True

    _draw_to_surface(w1)
    _draw_to_surface(w2)
    _draw_to_surface(w3)

    # Switch to Summary+ via UI combo box
    live_cv.format_combo.set_active(1)
    process_events()
    assert live_cv.get_display_format() == "Summary+"
    assert w1.display_format == "Summary+"
    assert (w1.width, w1.height) == (128, 124)
    assert (w3.width, w3.height) == (128, 124)

    _draw_to_surface(w1)
    _draw_to_surface(w2)
    _draw_to_surface(w3)

    # Cycle Summary+ -> Table -> Compact
    live_cv.toggle_display_format()
    process_events()
    assert live_cv.get_display_format() == "Table"

    live_cv.toggle_display_format()
    process_events()
    assert live_cv.get_display_format() == "Compact"
    assert (w3.width, w3.height) == (80, 80)


def test_channels_view_readout_modes_and_palette_rename_invalidation(
    app_gui: Application,
) -> None:
    """Test Readout selector formatting and snapshot invalidation on palette.rename."""
    _add_cmy_spot(app_gui, 3, 1)
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
    live_cv.set_display_format("Summary+")
    w3 = live_cv.get_channel_widget(3)
    assert w3 is not None

    expected_modes = ("Auto", "Label", "Ref", "Percent", "DMX")
    for idx, mode_name in enumerate(expected_modes):
        live_cv.readout_combo.set_active(idx)
        process_events()
        assert live_cv.get_readout_mode() == mode_name
        assert w3.readout_mode == mode_name
        _draw_to_surface(w3)

    snap = live_cv.get_channel_snapshot(3)
    assert snap is not None
    assert format_family_readout(snap.color, "label") == "Deep Cyan"
    assert format_family_readout(snap.color, "ref") == "CP 2.5"
    assert "%" in format_family_readout(snap.color, "percent")
    assert format_family_readout(snap.color, "dmx") != ""

    # Renaming the palette must invalidate cached snapshots cleanly
    app_gui.core.action_registry.execute("palette.rename", "color", 2.5, "Cool Ice")
    process_events()
    live_cv.flush_dirty_channels()

    updated_snap = live_cv.get_channel_snapshot(3)
    assert updated_snap is not None
    assert updated_snap.color.palette_ref is not None
    assert updated_snap.color.palette_ref.label == "Cool Ice"


def test_coalesced_30fps_redraws_on_color_transition_burst(
    app_gui: Application,
) -> None:
    """Burst of 20 color events coalesces to 1 targeted redraw per visible widget."""
    rgb1 = _add_rgb_fixture(app_gui, 1, 1)
    _add_rgb_fixture(app_gui, 2, 10)

    assert app_gui.window is not None
    live_cv = app_gui.window.live_view.channels_view
    # Switch to Patched so unpatched ch 3 stays hidden
    live_cv.set_view_mode_by_name("Patched")
    process_events()
    live_cv.flush_dirty_channels()
    process_events()

    w1 = live_cv.get_channel_widget(1)
    w2 = live_cv.get_channel_widget(2)
    w3 = live_cv.get_channel_widget(3)
    assert w1 is not None and w2 is not None and w3 is not None
    fb_child3 = live_cv.flowbox.get_child_at_index(2)
    assert fb_child3 is not None
    assert fb_child3.get_visible() is False

    live_cv.flowbox.queue_draw = MagicMock(wraps=live_cv.flowbox.queue_draw)  # type: ignore[method-assign]
    w1.queue_draw = MagicMock(wraps=w1.queue_draw)  # type: ignore[method-assign]
    w2.queue_draw = MagicMock(wraps=w2.queue_draw)  # type: ignore[method-assign]
    w3.queue_draw = MagicMock(wraps=w3.queue_draw)  # type: ignore[method-assign]

    # Trigger 20 rapid color ticks using real coalesced timer interval (25 ms)
    live_cv._redraw_interval_ms = 25
    for step in range(20):
        rgb1.set_color_srgb(step / 20.0, 0.2, 0.8)
        app_gui.core.emit("device.color_changed", [1])
    process_events()

    # Before timer fires, zero flowbox global redraws and a single timer armed
    assert live_cv.flowbox.queue_draw.call_count == 0
    assert live_cv._redraw_timer_id is not None

    # Allow the 25 ms one-shot GLib timer to fire naturally
    time.sleep(0.045)
    process_events()

    assert live_cv._redraw_timer_id is None
    assert live_cv.flowbox.queue_draw.call_count == 0
    assert w1.queue_draw.call_count == 1
    assert w2.queue_draw.call_count == 0
    assert w3.queue_draw.call_count == 0


def test_cue_and_seq_channels_view_isolation_from_live(
    app_gui: Application,
) -> None:
    """CueChannelsView and SeqChannelsView display Cue/Step colors, never Live."""
    rgb1 = _add_rgb_fixture(app_gui, 1, 1)
    # Live color = Pure Blue
    rgb1.set_color_srgb(0.0, 0.0, 1.0)

    app_gui.core.lightshow.palettes.add(
        Palette(
            PaletteCategory.COLOR,
            1.0,
            "Cue Red",
            device_values={1: {"color": "#FF0000"}},
        )
    )
    cue = Cue(
        0,
        1.0,
        {1: 0.8},
        "Red Cue",
        device_values={1: {"intensity": 0.8, "color": "#FF0000"}},
        palette_refs={1: {"color": ("color", 1.0)}},
    )
    app_gui.core.lightshow.cues.append(cue)

    main_pb = app_gui.core.lightshow.main_playback
    main_pb.steps.clear()
    main_pb.steps.append(Step(sequence=1, cue=Cue(1, 0, {})))
    main_pb.steps.append(Step(sequence=1, cue=cue))
    main_pb.steps.append(Step(sequence=1, cue=Cue(1, 0, {})))
    main_pb.last = len(main_pb.steps)

    # Open Cues & Sequences tabs
    app_gui.activate_action("cues", None)
    app_gui.activate_action("sequences", None)
    process_events()

    app_gui.core.action_registry.execute("cue.select", (1.0, 0))
    process_events()

    assert app_gui.tabs is not None
    assert app_gui.window is not None
    cues_tab = app_gui.tabs.tabs.get("cues")
    seq_tab = app_gui.tabs.tabs.get("sequences")
    assert isinstance(cues_tab, CuesEditionTab)
    assert isinstance(seq_tab, SequenceTab)

    cues_tab.channels_view.set_display_format("Summary+")
    seq_tab.channels_view.set_display_format("Summary+")
    seq_tab.refresh()
    seq_tab.treeview2.set_cursor(Gtk.TreePath.new_from_indices([0]), None, False)
    seq_tab.on_cue_changed(seq_tab.treeview2)
    process_events()

    live_w1 = app_gui.window.live_view.channels_view.get_channel_widget(1)
    cues_w1 = cues_tab.channels_view.get_channel_widget(1)
    seq_w1 = seq_tab.channels_view.get_channel_widget(1)
    assert live_w1 is not None and cues_w1 is not None and seq_w1 is not None

    assert live_w1.get_preview_rgb() == pytest.approx((0.0, 0.0, 1.0), abs=0.02)
    assert cues_w1.get_preview_rgb() == pytest.approx((1.0, 0.0, 0.0), abs=0.02)
    assert seq_w1.get_preview_rgb() == pytest.approx((1.0, 0.0, 0.0), abs=0.02)

    cues_snap = cues_w1.get_snapshot()
    seq_snap = seq_w1.get_snapshot()
    assert cues_snap is not None and cues_snap.color.palette_ref is not None
    assert cues_snap.color.palette_ref.label == "Cue Red"
    assert seq_snap is not None and seq_snap.color.palette_ref is not None
    assert seq_snap.color.palette_ref.label == "Cue Red"

    _draw_to_surface(cues_w1)
    _draw_to_surface(seq_w1)


def test_zoom_scales_compact_and_summary_plus(app_gui: Application) -> None:
    """Verify gui.zoom_changed and zoom() resize both Compact and Summary+ tiles."""
    assert app_gui.window is not None
    live_cv = app_gui.window.live_view.channels_view
    w1 = live_cv.get_channel_widget(1)
    assert w1 is not None

    # Compact at 1.5x
    app_gui.core.emit("gui.zoom_changed", 1.5)
    process_events()
    assert (w1.width, w1.height) == (120, 120)

    # Switch to Summary+ while scaled at 1.5x
    live_cv.set_display_format("Summary+")
    process_events()
    assert (w1.width, w1.height) == (192, 186)

    # Incremental zoom out via zoom()
    zoom("out", app_gui.window)
    process_events()
    assert w1.scale == pytest.approx(1.45, abs=0.001)
    assert (w1.width, w1.height) == (round(128 * 1.45), round(124 * 1.45))

    # Restore scale 1.0 and Compact format
    app_gui.core.emit("gui.zoom_changed", 1.0)
    process_events()
    assert (w1.width, w1.height) == (128, 124)
    live_cv.set_display_format("Compact")
    process_events()
    assert (w1.width, w1.height) == (80, 80)


def test_no_ml_badge_and_compact_ifcb_fallback(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify ML badge removal, Compact F/C/B fallback without snapshot, and API."""
    _add_dimmer(app_gui, 1, 1)
    _add_cmy_spot(app_gui, 3, 20)

    macro_only = LightingDevice(
        fixture_id=4,
        fixture_type=FixtureType.MOVING_HEAD,
        label="Macro Only 4",
        manufacturer="ACME",
        model="Macro Control",
    )
    macro_only.add_channel(
        Channel(universe=1, address=40, channel_type=ChannelType.INTENSITY)
    )
    macro_only.add_channel(
        Channel(universe=1, address=41, channel_type=ChannelType.MACRO)
    )
    macro_only.add_channel(
        Channel(universe=1, address=42, channel_type=ChannelType.RESET)
    )
    app_gui.core.lightshow.patch.restore_device(macro_only)
    app_gui.core.emit("patch.changed")
    process_events()

    assert app_gui.window is not None
    live_cv = app_gui.window.live_view.channels_view
    w1 = live_cv.get_channel_widget(1)
    w3 = live_cv.get_channel_widget(3)
    assert w1 is not None and w3 is not None

    # API backward compatibility
    assert w3.is_moving_head() is True
    assert w1.is_moving_head() is False

    drawn_texts: list[str] = []
    real_draw = channel_widget_mod.draw_cached_numeric_text

    def _spy_draw(
        cr: cairo.Context,
        x: float,
        y: float,
        text: str,
        font_size_pt: float,
        weight: Pango.Weight = Pango.Weight.NORMAL,
        anchor: TextAnchor = TextAnchor.CENTER,
        family: str | None = None,
    ) -> tuple[float, float, int, int]:
        drawn_texts.append(str(text))
        return real_draw(
            cr,
            x,
            y,
            text,
            font_size_pt,
            weight=weight,
            anchor=anchor,
            family=family,
        )

    monkeypatch.setattr(channel_widget_mod, "draw_cached_numeric_text", _spy_draw)

    # 1. LiveChannelsView Compact (with snapshot)
    live_cv.set_display_format("Compact")
    process_events()

    drawn_texts.clear()
    _draw_to_surface(w3)
    assert "ML" not in drawn_texts
    assert {"F", "C", "B"}.issubset(set(drawn_texts))

    drawn_texts.clear()
    _draw_to_surface(w1)
    assert not ({"F", "C", "B", "ML"} & set(drawn_texts))

    # 2. LiveChannelsView Summary+ (with snapshot)
    live_cv.set_display_format("Summary+")
    process_events()

    drawn_texts.clear()
    _draw_to_surface(w3)
    assert "ML" not in drawn_texts

    live_cv.set_display_format("Compact")
    process_events()

    # 3. Standalone ChannelWidget (snap is None fallback, e.g. Group/Inde/CT views)
    standalone_spot = ChannelWidget(3, 0, 0, app_gui, channels_view=None)
    assert standalone_spot.get_snapshot() is None
    drawn_texts.clear()
    _draw_to_surface(standalone_spot)
    assert "ML" not in drawn_texts
    assert {"F", "C", "B"}.issubset(set(drawn_texts))

    # 4. Macro/Reset-only fixture should not produce a false-positive B marker
    standalone_macro = ChannelWidget(4, 0, 0, app_gui, channels_view=None)
    assert standalone_macro.get_snapshot() is None
    drawn_texts.clear()
    _draw_to_surface(standalone_macro)
    assert not ({"F", "C", "B", "ML"} & set(drawn_texts))
