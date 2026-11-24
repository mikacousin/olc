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
"""Unit tests for FixtureLibraryTab GTK3 widget."""

from __future__ import annotations

import pathlib

import gi
import pytest

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, Gtk, Pango  # noqa: E402

from olc.devices.builtin import populate_builtin_library  # noqa: E402
from olc.devices.channel import ChannelType  # noqa: E402
from olc.devices.device import FixtureType  # noqa: E402
from olc.devices.fixture import (  # noqa: E402
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
)
from olc.devices.gdtf import HAS_PYGDTF  # noqa: E402
from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.gtk3.application import Application  # noqa: E402
from olc.gtk3.fixture_library import (  # noqa: E402
    COL_CAT_MANUFACTURER,
    COL_CAT_MODEL,
    COL_CH_FINE,
    COL_CH_HOME,
    COL_CH_LABEL,
    COL_CH_OFFSET,
    COL_CH_UNIT,
    COL_EM_ATTR,
    COL_EM_NAME,
    FixtureLibraryTab,
)

from test.conftest import DATA_DIR  # noqa: E402 # isort: skip
from test.gtk3.conftest import process_events  # noqa: E402 # isort: skip


def test_fixture_library_tab_opens_and_inspects_builtin(app_gui: Application) -> None:
    """Test opening Fixtures tab and verifying read-only state for built-ins."""
    app_gui.activate_action("fixtures", None)
    process_events()

    assert app_gui.tabs is not None
    fixtures_tab = app_gui.tabs.tabs.get("fixtures")
    assert isinstance(fixtures_tab, FixtureLibraryTab)

    # Catalog should contain the 6 built-in fixtures
    assert len(fixtures_tab.cat_store) >= 6

    # Select Generic:Dimmer
    lib = fixtures_tab.fixture_library
    dimmer_def = lib.get("Generic", "Dimmer")
    fixtures_tab.load_definition(dimmer_def)
    process_events()

    assert fixtures_tab.entry_mfg.get_text() == "Generic"
    assert fixtures_tab.entry_model.get_text() == "Dimmer"
    assert fixtures_tab.btn_apply.get_sensitive() is False
    assert fixtures_tab.btn_delete.get_sensitive() is False
    assert "Built-in profile (Read-Only)" in fixtures_tab.lbl_status.get_text()


def test_fixture_library_tab_duplicate_edit_and_apply(app_gui: Application) -> None:
    """Test duplicating a profile, modifying channels/home, and applying to the show."""
    app_gui.activate_action("fixtures", None)
    process_events()

    assert app_gui.tabs is not None
    fixtures_tab = app_gui.tabs.tabs.get("fixtures")
    assert isinstance(fixtures_tab, FixtureLibraryTab)

    # Select Generic:Moving Head Spot
    spot_def = fixtures_tab.fixture_library.get("Generic", "Moving Head Spot")
    fixtures_tab.load_definition(spot_def)
    process_events()

    # Click Duplicate
    fixtures_tab._on_duplicate_clicked(fixtures_tab.btn_duplicate)
    process_events()

    # Active definition should now be a Custom copy and editable
    active = fixtures_tab.active_definition
    assert active is not None
    assert active.manufacturer == "Custom"
    assert "Moving Head Spot" in active.model
    assert active.is_builtin is False
    assert fixtures_tab.btn_apply.get_sensitive() is True

    # Modify channel 1 (Pan) default Home value to 12345
    mode = active.default_mode()
    pan_def = mode.channel_defs[0]
    pan_def.default_value = 12345

    # Click Apply Changes
    fixtures_tab._on_apply_clicked(fixtures_tab.btn_apply)
    process_events()

    saved = fixtures_tab.fixture_library.get(active.manufacturer, active.model)
    assert saved is not None
    assert saved.default_mode().channel_defs[0].default_value == 12345

    # Delete custom copy
    fixtures_tab._on_delete_clicked(fixtures_tab.btn_delete)
    process_events()
    key = f"{active.manufacturer}:{active.model}"
    assert key not in fixtures_tab.fixture_library.keys()


def test_fixture_library_tab_new_and_filter(app_gui: Application) -> None:
    """Test creating a new profile and filtering in the catalog."""
    fixtures_tab = FixtureLibraryTab(app=app_gui)
    process_events()

    # Create new
    fixtures_tab._on_new_clicked(fixtures_tab.btn_new)
    process_events()

    assert fixtures_tab.active_definition is not None
    assert fixtures_tab.active_definition.manufacturer == "Custom"
    assert "New Fixture" in fixtures_tab.active_definition.model

    # Filter catalog
    fixtures_tab.search_entry.set_text("New Fixture")
    process_events()

    visible_models: list[str] = []
    tree_model = fixtures_tab.cat_tree.get_model()
    assert tree_model is not None
    for row in tree_model:
        visible_models.append(row[COL_CAT_MODEL])
    assert any("New Fixture" in m for m in visible_models)

    # Clear filter
    fixtures_tab.search_entry.set_text("")
    process_events()

    # Clean up created fixture
    fixtures_tab._on_delete_clicked(fixtures_tab.btn_delete)
    process_events()
    fixtures_tab.cleanup()


def test_fixture_library_tab_inspector_panels(app_gui: Application) -> None:
    """Test editing via right-hand Inspector panels for channels and ranges."""
    fixtures_tab = FixtureLibraryTab(app=app_gui)
    process_events()

    # Load Generic:Moving Head Spot
    spot_def = fixtures_tab.fixture_library.get("Generic", "Moving Head Spot")
    fixtures_tab.load_definition(spot_def)
    process_events()

    # Duplicate to make editable
    fixtures_tab._on_duplicate_clicked(fixtures_tab.btn_duplicate)
    process_events()

    # Select first channel (Pan)
    fixtures_tab.channels_tree.get_selection().select_path(Gtk.TreePath.new_first())
    process_events()

    # Channel Inspector should be populated with Pan
    assert fixtures_tab.entry_ch_label.get_text() == "Pan"
    assert fixtures_tab.spin_ch_offset.get_value() == 1.0

    # Modify Pan Home value via Inspector and click Update Channel
    fixtures_tab.spin_ch_home.set_value(45000)
    fixtures_tab._on_update_channel_clicked(fixtures_tab.btn_update_ch)
    process_events()

    active = fixtures_tab.active_definition
    assert active is not None
    assert active.default_mode().channel_defs[0].default_value == 45000

    # Add range slot via Range Inspector
    fixtures_tab.entry_rng_label.set_text("Position A")
    fixtures_tab.spin_rng_min.set_value(0)
    fixtures_tab.spin_rng_max.set_value(127)
    fixtures_tab.spin_rng_snap.set_value(64)
    fixtures_tab._on_add_range_clicked(fixtures_tab.btn_add_rng)
    process_events()

    assert len(active.default_mode().channel_defs[0].ranges) == 1
    assert active.default_mode().channel_defs[0].ranges[0].label == "Position A"

    # Clean up
    fixtures_tab._on_delete_clicked(fixtures_tab.btn_delete)
    process_events()
    fixtures_tab.cleanup()


def test_fixture_library_tab_eos_import_display_and_apply(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Verify FixtureLibraryTab shows Eos fixtures and Apply preserves patch."""
    asc_path = DATA_DIR / "eos_show.asc"

    monkeypatch.setenv("OLC_USER_FIXTURES_DIR", str(tmp_path))

    app_gui.activate_action("fixtures", None)
    process_events()

    assert app_gui.tabs is not None
    fixtures_tab = app_gui.tabs.tabs.get("fixtures")
    assert isinstance(fixtures_tab, FixtureLibraryTab)

    # Fine and Unit columns must be visible in Modes & Channels TreeView
    col_titles = [c.get_title() for c in fixtures_tab.channels_tree.get_columns()]
    assert "Fine" in col_titles
    assert "Unit" in col_titles

    try:
        imported = ImportFile(
            app_gui.core.lightshow,
            Gio.File.new_for_path(str(asc_path)),
            FileType.ASCII,
            tabs=app_gui.tabs,
        )
        imported.parse_sync(auto_import=True)
        process_events()

        # All 9 Eos non-dimmer profiles appear in the catalog store
        cat_keys = {
            (row[COL_CAT_MANUFACTURER], row[COL_CAT_MODEL])
            for row in fixtures_tab.cat_store
        }
        expected_profiles = {
            ("Ayrton", "Ghibli_Extended"),
            ("Ayrton", "Diablo_S_Extended_Pan_540"),
            ("Cameo", "F1_FC_16_CH_Direct_CCT"),
            ("Cameo", "F1_T_5ch"),
            ("Cameo", "Zenit_W_600_2ch"),
            ("Coemar", "ParLite_LED_RGBW"),
            ("Custom", "ParLite_LED_RGBA"),
            ("GLP", "Fusion_XPAR_12Z_M3_Adv"),
            ("OXO_Show_Solutions", "Multibeam_LED_FCW_M4"),
        }
        assert expected_profiles.issubset(cat_keys)

        # Inspect Ayrton Ghibli_Extended channels, 16-bit Fine, Unit, and slash names
        ghibli = fixtures_tab.fixture_library.get("Ayrton", "Ghibli_Extended")
        fixtures_tab.load_definition(ghibli)
        process_events()

        assert len(fixtures_tab.channels_store) == 35
        row0 = fixtures_tab.channels_store[0]
        assert row0[COL_CH_OFFSET] == "1"
        assert row0[COL_CH_FINE] == "2"
        assert row0[COL_CH_LABEL] == "Pan"
        assert row0[COL_CH_HOME] == "32768"
        assert row0[COL_CH_UNIT] == "deg"
        ch_labels = [row[COL_CH_LABEL] for row in fixtures_tab.channels_store]
        assert "Gobo_Index/Speed" in ch_labels
        assert "Beam_Fx_Index/Speed" in ch_labels

        # Inspect Cameo F1_FC_16_CH_Direct_CCT ranges & RGBW Color Profile (Scenario B)
        cameo = fixtures_tab.fixture_library.get("Cameo", "F1_FC_16_CH_Direct_CCT")
        fixtures_tab.load_definition(cameo)
        process_events()

        assert len(fixtures_tab.channels_store) == 11
        assert len(fixtures_tab.emitters_store) == 4

        cameo_labels = [row[COL_CH_LABEL] for row in fixtures_tab.channels_store]
        cct_idx = cameo_labels.index("Color_Temperature")
        fixtures_tab.channels_tree.get_selection().select_path(
            Gtk.TreePath.new_from_indices([cct_idx])
        )
        process_events()
        assert len(fixtures_tab.ranges_store) == 7

        cmix_idx = cameo_labels.index("Color_Mix")
        fixtures_tab.channels_tree.get_selection().select_path(
            Gtk.TreePath.new_from_indices([cmix_idx])
        )
        process_events()
        assert len(fixtures_tab.ranges_store) > 50

        # Apply to Show updates library note without corrupting patched device #41
        dev41_before = app_gui.core.lightshow.patch.get_device(41)
        assert dev41_before is not None
        addrs_before = [(c.universe, c.address) for c in dev41_before.channels]
        assert len(addrs_before) == 16

        fixtures_tab.entry_notes.set_text("Checked Eos")
        fixtures_tab._on_apply_clicked(fixtures_tab.btn_apply)
        process_events()

        updated = fixtures_tab.fixture_library.get("Cameo", "F1_FC_16_CH_Direct_CCT")
        assert updated.notes == "Checked Eos"
        dev41_after = app_gui.core.lightshow.patch.get_device(41)
        assert dev41_after is not None
        assert [(c.universe, c.address) for c in dev41_after.channels] == addrs_before
    finally:
        app_gui.core.lightshow.fixture_library = populate_builtin_library()
        app_gui.core.lightshow.patch.patch_empty()
        app_gui.core.lightshow.palettes.clear()
        app_gui.core.lightshow.groups.clear()
        app_gui.core.lightshow.sequences.clear()
        app_gui.core.lightshow.curves.reset()
        app_gui.core.lightshow.fader_bank.reset_faders()
        app_gui.core.emit("fixture_library.changed")
        app_gui.core.emit("patch.changed")
        process_events()


def test_fixture_library_tab_width_bounded_on_long_gdtf_profile(
    app_gui: Application,
) -> None:
    """Verify long mode names, channel labels, and notes never bloat tab width."""
    fixtures_tab = FixtureLibraryTab(app=app_gui)
    process_events()

    try:
        dimmer_def = fixtures_tab.fixture_library.get("Generic", "Dimmer")
        fixtures_tab.load_definition(dimmer_def)
        process_events()
        base_min_width, _ = fixtures_tab.get_preferred_width()

        long_fdef = FixtureDefinition(
            manufacturer="Robe Lighting",
            model="Robin Arianne 6 Ultra Extended Edition",
            fixture_type=FixtureType.MOVING_HEAD,
            notes="Very long fixture description text " * 12,
            dmx_modes=[
                DmxModeDefinition(
                    name="Mode 3 - Full+ScreenPix Extended 58ch Profile",
                    description="Long DMX mode description string for width test",
                    channel_defs=[
                        ChannelDefinition(
                            ChannelType.PAN,
                            offset=0,
                            fine_offset=1,
                            label="ScreenPixEffectSelectionUltraLongLabel",
                            physical_unit="deg",
                        ),
                        ChannelDefinition(
                            ChannelType.INTENSITY,
                            offset=2,
                            label="Dimmer",
                            physical_unit="%",
                        ),
                    ],
                )
            ],
            is_builtin=False,
        )
        fixtures_tab.load_definition(long_fdef)
        process_events()

        long_min_width, _ = fixtures_tab.get_preferred_width()
        assert long_min_width <= 650
        assert abs(long_min_width - base_min_width) <= 30

        text_cells = [
            c
            for c in fixtures_tab.combo_modes.get_cells()
            if isinstance(c, Gtk.CellRendererText)
        ]
        assert text_cells
        assert all(
            c.get_property("ellipsize") == Pango.EllipsizeMode.END for c in text_cells
        )
        assert fixtures_tab.lbl_status.get_ellipsize() == Pango.EllipsizeMode.END
        assert (
            fixtures_tab.lbl_mode_footprint.get_ellipsize() == Pango.EllipsizeMode.END
        )
        assert fixtures_tab.lbl_range_context.get_ellipsize() == Pango.EllipsizeMode.END
        assert fixtures_tab.lbl_color_info.get_ellipsize() == Pango.EllipsizeMode.END
    finally:
        fixtures_tab.cleanup()


class _FakeFileChooser:
    def __init__(self, filename: str, response: Gtk.ResponseType) -> None:
        self._filename = filename
        self._response = response

    def add_filter(self, _file_filter: object) -> None:
        pass

    def set_modal(self, _modal: bool) -> None:
        pass

    def run(self) -> Gtk.ResponseType:
        return self._response

    def get_filename(self) -> str:
        return self._filename

    def destroy(self) -> None:
        pass


def test_fixture_library_tab_import_gdtf_selects_profile(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Verify clicking GDTF imports, registers, and selects the imported profile."""
    if not HAS_PYGDTF:
        pytest.skip("pygdtf not installed")
    gdtf_path = DATA_DIR / "sample_rgbl_moving_head.gdtf"

    monkeypatch.setenv("OLC_USER_FIXTURES_DIR", str(tmp_path))
    monkeypatch.setattr(
        Gtk.FileChooserNative,
        "new",
        lambda *_args: _FakeFileChooser(str(gdtf_path), Gtk.ResponseType.ACCEPT),
    )

    app_gui.activate_action("fixtures", None)
    process_events()

    assert app_gui.tabs is not None
    fixtures_tab = app_gui.tabs.tabs.get("fixtures")
    assert isinstance(fixtures_tab, FixtureLibraryTab)

    try:
        fixtures_tab._on_import_gdtf_clicked(fixtures_tab.btn_import_gdtf)
        process_events()

        cat_keys = {
            (row[COL_CAT_MANUFACTURER], row[COL_CAT_MODEL])
            for row in fixtures_tab.cat_store
        }
        assert ("OpenLighting", "Test RGBL Wash") in cat_keys

        active = fixtures_tab.active_definition
        assert active is not None
        assert active.manufacturer == "OpenLighting"
        assert active.model == "Test RGBL Wash"
        assert len(active.dmx_modes) == 3

        assert len(fixtures_tab.emitters_store) == 4
        emitters_by_name = {
            row[COL_EM_NAME]: row[COL_EM_ATTR] for row in fixtures_tab.emitters_store
        }
        assert emitters_by_name.get("Lime") == "ColorAdd_GY"
    finally:
        app_gui.core.lightshow.fixture_library = populate_builtin_library()
        app_gui.core.emit("fixture_library.changed")
        process_events()


def test_fixture_library_tab_import_gdtf_shows_error_on_failure(
    app_gui: Application, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Verify GDTF import errors display an error dialog instead of failing silently."""
    missing_path = tmp_path / "missing.gdtf"
    monkeypatch.setattr(
        Gtk.FileChooserNative,
        "new",
        lambda *_args: _FakeFileChooser(str(missing_path), Gtk.ResponseType.ACCEPT),
    )

    app_gui.activate_action("fixtures", None)
    process_events()

    assert app_gui.tabs is not None
    fixtures_tab = app_gui.tabs.tabs.get("fixtures")
    assert isinstance(fixtures_tab, FixtureLibraryTab)

    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        fixtures_tab,
        "_show_error_dialog",
        lambda title, msg: errors.append((title, msg)),
    )

    fixtures_tab._on_import_gdtf_clicked(fixtures_tab.btn_import_gdtf)
    process_events()

    assert len(errors) == 1
    assert errors[0][0]
    assert errors[0][1]


def test_fixture_library_tab_cmy_presets_filter_gamma_and_color_picker(
    app_gui: Application,
) -> None:
    """Verify CMY/CMY+CTO presets, filter/gamma editing, and Color Picker CMY+CTO UX."""
    from olc.devices.builtin import create_cmy_definition
    from olc.devices.channel import Channel, ChannelType
    from olc.devices.device import FixtureType, LightingDevice
    from olc.gtk3.widgets.color_picker import ConsoleColorPicker

    app_gui.activate_action("fixtures", None)
    process_events()

    assert app_gui.tabs is not None
    fixtures_tab = app_gui.tabs.tabs.get("fixtures")
    assert isinstance(fixtures_tab, FixtureLibraryTab)

    # Select Generic CMY Spot from builtin catalog
    cmy_def = create_cmy_definition()
    fixtures_tab.active_definition = cmy_def
    fixtures_tab._refresh_color_emitters()
    process_events()

    assert fixtures_tab.combo_mixing_mode.get_active_id() == "subtractive"
    assert len(fixtures_tab.emitters_store) == 4

    # Apply Preset CMY (3 filters) then Preset CMY+CTO (4 filters)
    fixtures_tab._apply_color_preset("cmy")
    assert cmy_def.color_profile is not None
    assert len(cmy_def.color_profile.filters) == 3
    assert len(fixtures_tab.emitters_store) == 3

    fixtures_tab._apply_color_preset("cmy_cto")
    assert len(cmy_def.color_profile.filters) == 4

    # Preserve spectral_transmission while editing filter CIE x/y/Y and gamma
    cmy_def.color_profile.filters[0].spectral_transmission = [
        (400.0, 0.8),
        (700.0, 0.1),
    ]
    fixtures_tab._refresh_color_emitters()
    fixtures_tab.emitters_tree.get_selection().select_path(Gtk.TreePath.new_first())
    process_events()

    fixtures_tab.spin_em_x.set_value(0.145)
    fixtures_tab.spin_em_gamma.set_value(1.35)
    fixtures_tab._on_update_emitter_clicked(fixtures_tab.btn_update_em)
    process_events()

    edited_cyan = cmy_def.color_profile.filters[0]
    assert edited_cyan.cie.x == pytest.approx(0.145, abs=1e-4)
    assert edited_cyan.gamma == pytest.approx(1.35, abs=1e-3)
    assert edited_cyan.spectral_transmission == [(400.0, 0.8), (700.0, 0.1)]

    # Verify ConsoleColorPicker displays C/M/Y/CTO faders, hexagonal gamut & white point
    picker = ConsoleColorPicker(on_color=lambda *_args: None)
    dev = LightingDevice(
        fixture_id=99,
        label="CMY+CTO Spot",
        fixture_type=FixtureType.MOVING_HEAD,
        channels=[
            Channel(ChannelType.INTENSITY, 1, 1),
            Channel(ChannelType.CYAN, 1, 2),
            Channel(ChannelType.MAGENTA, 1, 3),
            Channel(ChannelType.YELLOW, 1, 4),
            Channel(ChannelType.COLOR_TEMP, 1, 5),
        ],
        color_profile=cmy_def.color_profile,
    )
    picker.set_devices_context(dev, [dev])
    for key in ("cyan", "magenta", "yellow", "color_temp"):
        assert picker.emitter_rows[key].get_visible() is True
    assert picker.emitter_rows["red"].get_visible() is False
    assert picker.strategy_combo.get_sensitive() is False
    assert len(picker.gamut_xy) == 6
    assert picker.cie_xy.white_point_xy is not None
    picker.cleanup()
