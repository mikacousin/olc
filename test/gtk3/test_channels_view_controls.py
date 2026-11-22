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
"""GTK3 workflow tests for Flexi modes, controls, shortcuts, VC & persistence."""

# pylint: disable=protected-access, missing-function-docstring, too-many-locals, too-many-statements

from __future__ import annotations

import gzip
import json
import pathlib
from types import SimpleNamespace

import cairo
import gi
import pytest

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from olc.core.selection import SelectRemoveAction  # noqa: E402
from olc.devices.channel import Channel, ChannelType, FixtureType  # noqa: E402
from olc.devices.device import LightingDevice  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.cue import CuesEditionTab  # noqa: E402
from olc.gtk3.group import GroupTab  # noqa: E402
from olc.gtk3.sequence import SequenceTab  # noqa: E402
from olc.gtk3.widgets.channels_table_view import COL_CHANNEL  # noqa: E402
from olc.gtk3.widgets.channels_view import VIEW_MODES, ChannelsView  # noqa: E402
from olc.gtk3.widgets.common import TextAnchor  # noqa: E402
from olc.show.cue import Cue  # noqa: E402
from olc.show.group import Group  # noqa: E402
from olc.show.palette import Palette, PaletteCategory  # noqa: E402
from olc.show.sequence import Sequence  # noqa: E402
from olc.show.step import Step  # noqa: E402
from test.gtk3.conftest import process_events  # noqa: E402

pytestmark = pytest.mark.gui


def _add_dimmer(app_gui: Application, ch: int, addr: int) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=ch,
        fixture_type=FixtureType.DIMMER,
        label=f"Dim {ch}",
        manufacturer="Generic",
        model="Dimmer",
    )
    dev.add_channel(
        Channel(universe=1, address=addr, channel_type=ChannelType.INTENSITY)
    )
    app_gui.core.lightshow.patch.restore_device(dev)
    return dev


def _add_rgb_par(app_gui: Application, ch: int, addr: int) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=ch,
        fixture_type=FixtureType.LED_PAR,
        label=f"Wash {ch}",
        manufacturer="Generic",
        model="RGB Par",
    )
    dev.add_channel(Channel(universe=1, address=addr, channel_type=ChannelType.RED))
    dev.add_channel(
        Channel(universe=1, address=addr + 1, channel_type=ChannelType.GREEN)
    )
    dev.add_channel(
        Channel(universe=1, address=addr + 2, channel_type=ChannelType.BLUE)
    )
    app_gui.core.lightshow.patch.restore_device(dev)
    return dev


def _add_moving_spot(app_gui: Application, ch: int, addr: int) -> LightingDevice:
    dev = LightingDevice(
        fixture_id=ch,
        fixture_type=FixtureType.MOVING_HEAD,
        label=f"Spot {ch}",
        manufacturer="ACME",
        model="Spot 200",
    )
    dev.add_channel(
        Channel(universe=1, address=addr, channel_type=ChannelType.INTENSITY)
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=addr + 1,
            channel_type=ChannelType.PAN,
            physical_min=-270.0,
            physical_max=270.0,
        )
    )
    dev.add_channel(
        Channel(
            universe=1,
            address=addr + 2,
            channel_type=ChannelType.TILT,
            physical_min=-135.0,
            physical_max=135.0,
        )
    )
    app_gui.core.lightshow.patch.restore_device(dev)
    return dev


def _table_channels(channels_view: ChannelsView) -> list[int]:
    return [int(row[COL_CHANNEL]) for row in channels_view.table_view.store]


def test_flexi_devices_selected_manual_filters_and_reactivity(
    app_gui: Application,
) -> None:
    """Verify Devices, Selected, and Manual Flexi filters and live reactivity."""
    assert app_gui.window is not None
    _add_dimmer(app_gui, 1, 1)
    _add_rgb_par(app_gui, 2, 10)
    _add_moving_spot(app_gui, 3, 20)

    pal_red = Palette(
        category=PaletteCategory.COLOR,
        number=1.0,
        text="Red Wash",
        device_values={2: {"red": 1.0, "green": 0.0, "blue": 0.0}},
    )
    app_gui.core.lightshow.palettes.add(pal_red)

    live_cv = app_gui.window.live_view.channels_view
    live_cv.update()
    process_events()

    # 1. Devices Flexi mode: excludes pure dimmer Ch 1, includes Ch 2 & Ch 3
    live_cv.set_view_mode_by_name("Devices")
    process_events()
    assert live_cv.view_mode == VIEW_MODES["Devices"]
    assert live_cv.get_visible_channels() == [2, 3]

    live_cv.set_display_format("Table")
    process_events()
    assert _table_channels(live_cv) == [2, 3]

    # 2. Selected Flexi mode: reactive in both Table and FlowBox
    live_cv.set_view_mode_by_name("Selected")
    process_events()
    assert live_cv.get_visible_channels() == []
    assert _table_channels(live_cv) == []

    app_gui.core.action_registry.execute("channel.select_channels", [1, 3])
    process_events()
    assert live_cv.get_visible_channels() == [1, 3]
    assert _table_channels(live_cv) == [1, 3]

    live_cv.selection_manager.execute_action(SelectRemoveAction, 1)
    process_events()
    assert live_cv.get_visible_channels() == [3]
    assert _table_channels(live_cv) == [3]

    # 3. Manual Flexi mode: reactive on level/device/palette/sneak/record/reset
    live_cv.set_display_format("Compact")
    app_gui.core.action_registry.execute("channel.select_none")
    live_cv.set_view_mode_by_name("Manual")
    process_events()
    assert live_cv.get_visible_channels() == []

    # Manual intensity on Ch 1
    app_gui.core.action_registry.execute("channel.set_level", 1, 0.5)
    process_events()
    assert live_cv.get_visible_channels() == [1]

    # Manual non-intensity parameter on Ch 3 (intensity stays 0)
    app_gui.core.action_registry.execute("device.set_parameter", "pan", 45.0, [3], True)
    process_events()
    assert live_cv.get_visible_channels() == [1, 3]

    # Palette apply on Ch 2
    app_gui.core.action_registry.execute("channel.select_channels", [2])
    app_gui.core.action_registry.execute("palette.apply", "color", 1.0)
    process_events()
    assert live_cv.get_visible_channels() == [1, 2, 3]

    # Sneak cut on Ch 3 removes Ch 3 from Manual
    app_gui.core.action_registry.execute("channel.sneak", [3], 0.0)
    process_events()
    assert live_cv.get_visible_channels() == [1, 2]

    # Record Cue on active step releases manual overrides
    main_pb = app_gui.core.lightshow.main_playback
    cue1 = Cue(sequence=1, number=1.0, channels={})
    app_gui.core.lightshow.cues.add(cue1)
    main_pb.insert_step(1, Step(sequence=1, cue=cue1))
    main_pb.position = 1
    app_gui.core.action_registry.execute("commandline.set", "RECORD CUE 1")
    app_gui.core.action_registry.execute("commandline.execute")
    process_events()
    assert live_cv.get_visible_channels() == []

    # Manual edit again then show.reset_user_levels (Clear) empties Manual
    app_gui.core.action_registry.execute("channel.set_level", 1, 0.8)
    process_events()
    assert live_cv.get_visible_channels() == [1]
    app_gui.core.action_registry.execute("show.reset_user_levels")
    process_events()
    assert live_cv.get_visible_channels() == []


def test_flexi_subclasses_and_filtered_navigation(app_gui: Application) -> None:
    """Verify extended Flexi modes on Cue/Group tabs and Next/Prev in filtered modes."""
    assert app_gui.window is not None
    assert app_gui.tabs is not None
    _add_dimmer(app_gui, 1, 1)
    _add_rgb_par(app_gui, 2, 10)
    _add_moving_spot(app_gui, 3, 20)

    cue1 = Cue(sequence=1, number=1.0, channels={1: 1.0})
    app_gui.core.lightshow.cues.add(cue1)
    app_gui.core.lightshow.groups.append(Group(1.0, [1, 2], "Front"))

    # Live view filtered Next/Prev navigation in Devices and empty Manual
    live_cv = app_gui.window.live_view.channels_view
    live_cv.set_view_mode_by_name("Manual")
    app_gui.core.action_registry.execute("channel.select_none")
    process_events()
    live_cv.select_next()
    live_cv.select_previous()
    assert live_cv.get_selected_channels() == []

    live_cv.set_view_mode_by_name("Devices")
    process_events()
    live_cv.select_next()
    assert live_cv.get_selected_channels() == [2]
    live_cv.select_next()
    assert live_cv.get_selected_channels() == [3]
    live_cv.select_next()
    assert live_cv.get_selected_channels() == [2]
    live_cv.select_previous()
    assert live_cv.get_selected_channels() == [3]

    # CueChannelsView: Devices, Selected, Manual (uncommitted cue_editor level)
    app_gui.open_cues()
    process_events()
    cues_tab = app_gui.tabs.tabs.get("cues")
    assert isinstance(cues_tab, CuesEditionTab)
    app_gui.core.action_registry.execute("cue.select", (1.0, 1))
    app_gui.core.action_registry.execute("cue.set_temp_channels", 1.0, 1, {2: 180})
    process_events()

    cues_cv = cues_tab.channels_view
    cues_cv.set_view_mode_by_name("Devices")
    process_events()
    assert cues_cv.get_visible_channels() == [2, 3]

    cues_cv.set_view_mode_by_name("Manual")
    process_events()
    assert cues_cv.get_visible_channels() == [2]

    cues_cv.selection_manager.selected_channels = [1]
    cues_cv.sync_selection_to_gui([1])
    cues_cv.set_view_mode_by_name("Selected")
    process_events()
    assert cues_cv.get_visible_channels() == [1]

    # GroupChannelsView: Devices, Selected, Manual
    app_gui.open_groups()
    process_events()
    grp_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(grp_tab, GroupTab)
    grp_tab.select_group_graphically(1.0)
    process_events()

    grp_cv = grp_tab.channels_view
    grp_cv.set_view_mode_by_name("Devices")
    process_events()
    assert grp_cv.get_visible_channels() == [2, 3]

    grp_cv.selection_manager.selected_channels = [2]
    grp_cv.sync_selection_to_gui([2])
    grp_cv.set_view_mode_by_name("Selected")
    process_events()
    assert grp_cv.get_visible_channels() == [2]

    grp_cv.set_view_mode_by_name("Manual")
    process_events()
    assert grp_cv.get_visible_channels() == []


def test_channels_controls_shortcuts_vc_and_event_bridge(
    app_gui: Application,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Labels toggle, Data toggle, shortcuts, help-overlay, actions & VC."""
    assert app_gui.window is not None
    win = app_gui.window
    controller = win.key_controller
    _add_moving_spot(app_gui, 1, 1)

    live_cv = win.live_view.channels_view
    live_cv.set_view_mode_by_name("Patched")
    process_events()

    # 1. Labels toggle hides header label in Summary+ and Fixture / Label col in Table
    live_cv.set_display_format("Summary+")
    w1 = live_cv.get_channel_widget(1)
    assert w1 is not None
    drawn_texts: list[str] = []
    orig_draw_text = w1._draw_ellipsized_text

    def spy_draw_text(
        cr_ctx: cairo.Context,
        x: float,
        y: float,
        max_w: float,
        text: str,
        pt: float,
        weight: Pango.Weight = Pango.Weight.NORMAL,
        anchor: TextAnchor = TextAnchor.BASELINE_LEFT,
    ) -> None:
        drawn_texts.append(text)
        orig_draw_text(cr_ctx, x, y, max_w, text, pt, weight=weight, anchor=anchor)

    monkeypatch.setattr(w1, "_draw_ellipsized_text", spy_draw_text)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
    cr = cairo.Context(surface)
    w1.do_draw(cr)
    assert "Spot 1" in drawn_texts

    drawn_texts.clear()
    live_cv.labels_btn.set_active(False)
    assert live_cv.get_show_labels() is False
    w1.do_draw(cr)
    assert "Spot 1" not in drawn_texts

    live_cv.set_display_format("Table")
    process_events()
    assert "Fixture / Label" not in live_cv.table_view.get_column_titles()
    live_cv.set_show_labels(True)
    assert "Fixture / Label" in live_cv.table_view.get_column_titles()
    live_cv.set_display_format("Compact")

    # 2. Data toggle preserves prior Label/Ref choice and obeys percent/DMX pref
    with monkeypatch.context() as mp:
        mp.setattr(
            live_cv,
            "settings",
            SimpleNamespace(get_boolean=lambda k: k == "percent"),
        )
        live_cv.set_readout_mode("Label")
        assert live_cv.toggle_data_mode() == "Percent"
        assert live_cv.toggle_data_mode() == "Label"

        mp.setattr(
            live_cv,
            "settings",
            SimpleNamespace(get_boolean=lambda _k: False),
        )
        live_cv.set_readout_mode("Ref")
        assert live_cv.toggle_data_mode() == "DMX"
        assert live_cv.toggle_data_mode() == "Ref"
    live_cv.set_readout_mode("Auto")

    # 3. Non-conflicting keyboard shortcuts (Alt+Shift+F/D/L and Ctrl+F)
    monkeypatch.setattr(win, "get_active_tab", lambda: live_cv)
    alt_shift = Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.SHIFT_MASK

    assert win._on_key_controller_pressed(controller, Gdk.KEY_f, 0, alt_shift) is True
    assert live_cv.get_display_format() == "Summary+"
    assert win._on_key_controller_pressed(controller, Gdk.KEY_f, 0, alt_shift) is True
    assert live_cv.get_display_format() == "Table"

    assert win._on_key_controller_pressed(controller, Gdk.KEY_d, 0, alt_shift) is True
    assert live_cv.get_readout_mode() == "Percent"
    assert win._on_key_controller_pressed(controller, Gdk.KEY_d, 0, alt_shift) is True
    assert live_cv.get_readout_mode() == "Auto"

    assert win._on_key_controller_pressed(controller, Gdk.KEY_l, 0, alt_shift) is True
    assert live_cv.get_show_labels() is False
    assert win._on_key_controller_pressed(controller, Gdk.KEY_l, 0, alt_shift) is True
    assert live_cv.get_show_labels() is True

    # Cycles all 6 Flexi modes with Ctrl+F
    live_cv.set_view_mode_by_name("All")
    seen_flexi: list[str] = []
    for _ in range(6):
        assert (
            win._on_key_controller_pressed(
                controller, Gdk.KEY_f, 0, Gdk.ModifierType.CONTROL_MASK
            )
            is True
        )
        seen_flexi.append(live_cv.get_view_mode_name())
    assert seen_flexi == ["Patched", "Active", "Devices", "Selected", "Manual", "All"]

    # Shortcuts isolation when a Gtk.Entry has focus
    entry = Gtk.Entry()
    with monkeypatch.context() as mp:
        mp.setattr(win, "get_focus", lambda: entry)
        prev_fmt = live_cv.get_display_format()
        assert (
            win._on_key_controller_pressed(controller, Gdk.KEY_f, 0, alt_shift) is False
        )
        assert live_cv.get_display_format() == prev_fmt

    # 4. help-overlay.ui documents new shortcuts cleanly
    help_path = pathlib.Path(__file__).resolve().parents[2] / "data" / "help-overlay.ui"
    builder = Gtk.Builder()
    builder.add_from_file(str(help_path))
    for obj_id in (
        "filter_channels",
        "channels_format",
        "channels_data",
        "channels_labels",
    ):
        assert builder.get_object(obj_id) is not None

    # 5. Core Actions route via EventBridge to active ChannelsView
    app_gui.core.action_registry.execute("gui.channels_format", "Summary+")
    app_gui.core.action_registry.execute("gui.channels_data", "Label")
    app_gui.core.action_registry.execute("gui.channels_labels", False)
    app_gui.core.action_registry.execute("gui.channels_flexi", "Devices")
    process_events()
    assert live_cv.get_display_format() == "Summary+"
    assert live_cv.get_readout_mode() == "Label"
    assert live_cv.get_show_labels() is False
    assert live_cv.get_view_mode_name() == "Devices"

    # 6. Virtual Console buttons trigger actions and MIDI Learn target selection
    app_gui.open_virtual_console()
    process_events()
    vc = app_gui.virtual_console
    assert vc is not None
    for btn_name in (
        "channels_format",
        "channels_data",
        "channels_labels",
        "channels_flexi",
    ):
        btn = getattr(vc, btn_name)
        assert btn.get_sensitive() is True

    vc.channels_format.emit("clicked")
    vc.channels_data.emit("clicked")
    vc.channels_labels.emit("clicked")
    vc.channels_flexi.emit("clicked")
    process_events()
    assert live_cv.get_display_format() == "Table"
    assert live_cv.get_readout_mode() == "Percent"
    assert live_cv.get_show_labels() is True
    assert live_cv.get_view_mode_name() == "Selected"

    # MIDI Learn selection on Virtual Console buttons
    assert app_gui.core.midi is not None
    for btn_name, expected_target in (
        ("channels_format", "gui.channels_format"),
        ("channels_data", "gui.channels_data"),
        ("channels_labels", "gui.channels_labels"),
        ("channels_flexi", "gui.channels_flexi"),
    ):
        app_gui.core.action_registry.execute("midi.learn_toggle", " ")
        getattr(vc, btn_name).emit("clicked")
        assert app_gui.core.midi.learning == expected_target
    app_gui.core.action_registry.execute("midi.learn_toggle", None)


def test_workspace_persistence_all_channels_settings_and_legacy_backcompat(
    app_gui: Application,
    tmp_path: pathlib.Path,
) -> None:
    """Verify full per-tab persistence and legacy view_mode-only compatibility."""
    assert app_gui.tabs is not None
    assert app_gui.window is not None
    _add_moving_spot(app_gui, 1, 1)

    seq = Sequence(1, text="Main")
    cue1 = Cue(sequence=1, number=1.0, channels={1: 1.0})
    app_gui.core.lightshow.cues.add(cue1)
    seq.add_step(Step(sequence=1, cue=cue1))
    app_gui.core.lightshow.main_playback = seq

    # 1. Configure Live ChannelsView + Cues + Sequences + Groups
    live_cv = app_gui.window.live_view.channels_view
    live_cv.set_view_mode_by_name("Devices")
    live_cv.set_readout_mode("Label")
    live_cv.set_show_labels(False)
    live_cv.set_family_expanded("focus", True)
    live_cv.set_family_expanded("color", True)
    live_cv.set_display_format("Table")

    app_gui.open_cues()
    app_gui.open_sequences()
    app_gui.open_groups()
    process_events()

    cues_tab = app_gui.tabs.tabs.get("cues")
    seq_tab = app_gui.tabs.tabs.get("sequences")
    grp_tab = app_gui.tabs.tabs.get("groups")
    assert isinstance(cues_tab, CuesEditionTab)
    assert isinstance(seq_tab, SequenceTab)
    assert isinstance(grp_tab, GroupTab)

    cues_tab.channels_view.set_view_mode_by_name("Manual")
    cues_tab.channels_view.set_display_format("Summary+")
    cues_tab.channels_view.set_readout_mode("DMX")
    cues_tab.channels_view.set_show_labels(False)

    seq_tab.channels_view.set_view_mode_by_name("Patched")
    seq_tab.channels_view.set_family_expanded("beam", True)
    seq_tab.channels_view.set_display_format("Table")
    seq_tab.channels_view.set_readout_mode("Ref")

    grp_tab.channels_view.set_view_mode_by_name("Selected")
    grp_tab.channels_view.set_display_format("Summary+")
    grp_tab.channels_view.set_show_labels(True)
    process_events()

    # 2. Close & reopen Cues tab -> settings preserved
    app_gui.tabs.close_physically("cues")
    process_events()
    app_gui.open_cues()
    process_events()
    reopened_cues = app_gui.tabs.tabs.get("cues")
    assert isinstance(reopened_cues, CuesEditionTab)
    assert reopened_cues.channels_view.get_view_mode_name() == "Manual"
    assert reopened_cues.channels_view.get_display_format() == "Summary+"
    assert reopened_cues.channels_view.get_readout_mode() == "DMX"
    assert reopened_cues.channels_view.get_show_labels() is False

    # 3. Full save -> new -> open round-trip
    save_path = str(tmp_path / "channels_workspace.olc")
    app_gui.core.action_registry.execute("show.save", save_path)
    process_events()

    app_gui.core.action_registry.execute("show.new")
    process_events()
    assert live_cv.get_view_mode_name() == "All"
    assert live_cv.get_display_format() == "Compact"
    assert live_cv.get_readout_mode() == "Auto"
    assert live_cv.get_show_labels() is True
    assert live_cv.get_expanded_families() == {
        "focus": False,
        "color": False,
        "beam": False,
    }

    app_gui.core.action_registry.execute("show.open", save_path)
    process_events()

    assert live_cv.get_view_mode_name() == "Devices"
    assert live_cv.get_display_format() == "Table"
    assert live_cv.get_readout_mode() == "Label"
    assert live_cv.get_show_labels() is False
    assert live_cv.get_expanded_families() == {
        "focus": True,
        "color": True,
        "beam": False,
    }
    assert "Fixture / Label" not in live_cv.table_view.get_column_titles()
    assert "Pan" in live_cv.table_view.get_column_titles()

    restored_cues = app_gui.tabs.tabs.get("cues")
    restored_seq = app_gui.tabs.tabs.get("sequences")
    restored_grp = app_gui.tabs.tabs.get("groups")
    assert isinstance(restored_cues, CuesEditionTab)
    assert isinstance(restored_seq, SequenceTab)
    assert isinstance(restored_grp, GroupTab)

    assert restored_cues.channels_view.get_view_mode_name() == "Manual"
    assert restored_cues.channels_view.get_display_format() == "Summary+"
    assert restored_cues.channels_view.get_readout_mode() == "DMX"
    assert restored_cues.channels_view.get_show_labels() is False

    assert restored_seq.channels_view.get_view_mode_name() == "Patched"
    assert restored_seq.channels_view.get_display_format() == "Table"
    assert restored_seq.channels_view.get_readout_mode() == "Ref"
    assert restored_seq.channels_view.get_expanded_families()["beam"] is True

    assert restored_grp.channels_view.get_view_mode_name() == "Selected"
    assert restored_grp.channels_view.get_display_format() == "Summary+"
    assert restored_grp.channels_view.get_show_labels() is True

    # 4. Backwards compatibility: legacy workspace with only view_mode
    legacy_path = tmp_path / "legacy_tab_settings_only_view_mode.olc"
    legacy_payload = {
        "application": "olc",
        "version": "0.9.0",
        "patch": {},
        "sequences": {},
        "cues": {},
        "workspace": {
            "version": 1,
            "active_pane": "playback",
            "panes": {
                "live": {"tabs": ["channels"], "active_tab": "channels"},
                "playback": {"tabs": ["playback"], "active_tab": "playback"},
            },
            "tab_settings": {"channels": {"view_mode": "Patched"}},
            "virtual_console": {"open": False},
        },
    }
    with gzip.open(str(legacy_path), "wb") as f:
        f.write(json.dumps(legacy_payload).encode("utf-8"))

    app_gui.core.action_registry.execute("show.open", str(legacy_path))
    process_events()

    assert live_cv.get_view_mode_name() == "Patched"
    assert live_cv.get_display_format() == "Compact"
    assert live_cv.get_readout_mode() == "Auto"
    assert live_cv.get_show_labels() is True
    assert live_cv.get_expanded_families() == {
        "focus": False,
        "color": False,
        "beam": False,
    }
