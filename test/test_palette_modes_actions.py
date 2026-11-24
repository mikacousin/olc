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
"""Unit tests for palette mode actions, CLI syntax, and Eos ASCII By-Type import."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio  # noqa: E402

from olc.core.app import CoreApplication  # noqa: E402
from olc.core.parser.executor import CommandResult  # noqa: E402
from olc.devices.channel import Channel, ChannelType  # noqa: E402
from olc.devices.device import LightingDevice  # noqa: E402
from olc.devices.fixture import FixtureType  # noqa: E402
from olc.files.file_type import FileType  # noqa: E402
from olc.files.import_file import ImportFile  # noqa: E402
from olc.show.lightshow import LightShow  # noqa: E402
from olc.show.palette import Palette, PaletteCategory, PaletteMode  # noqa: E402


def _make_app() -> CoreApplication:
    settings = MagicMock()
    settings.get_double.return_value = 5.0
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    return app


def _make_rgb_fixture(
    fixture_id: int,
    *,
    manufacturer: str = "Robe",
    model: str = "Spiider",
    mode_name: str = "Std",
    start_addr: int = 1,
) -> LightingDevice:
    channels = [
        Channel(ChannelType.INTENSITY, 1, start_addr),
        Channel(ChannelType.RED, 1, start_addr + 1),
        Channel(ChannelType.GREEN, 1, start_addr + 2),
        Channel(ChannelType.BLUE, 1, start_addr + 3),
    ]
    return LightingDevice(
        fixture_id=fixture_id,
        label=f"Fix {fixture_id}",
        fixture_type=FixtureType.LED_PAR,
        channels=channels,
        manufacturer=manufacturer,
        model=model,
        mode_name=mode_name,
    )


def test_palette_record_apply_update_by_type_and_universal() -> None:
    """Verify By-Type and Universal record, apply, selective override, and lock."""
    app = _make_app()
    dev1 = _make_rgb_fixture(1, start_addr=1)
    dev2 = _make_rgb_fixture(2, start_addr=5)
    dev3 = _make_rgb_fixture(
        3, manufacturer="Martin", model="Rush", mode_name="16ch", start_addr=9
    )
    app.lightshow.patch.devices = {1: dev1, 2: dev2, 3: dev3}

    # 1. Record By-Type Color Palette 1 using only channel 1
    res = app.action_registry.execute(
        "palette.record",
        "color",
        1.0,
        label="Red",
        device_values={1: {"color": "#ff0000"}},
        mode=PaletteMode.BY_TYPE,
    )
    assert isinstance(res, dict)
    pal = res["palette"]
    assert pal.mode is PaletteMode.BY_TYPE
    assert dev1.type_key in pal.by_type_values
    assert pal.by_type_values[dev1.type_key]["color"] == "#ff0000"
    assert pal.device_values == {}

    # 2. Apply without selection -> affects ch 1 & ch 2 (same type), not ch 3
    affected = app.action_registry.execute("palette.apply", "color", 1.0)
    assert affected == [1, 2]

    # 3. Update with selective_override=True on ch 2 keeps ch 1 By-Type intact
    app.action_registry.execute(
        "palette.update",
        "color",
        1.0,
        device_values={2: {"color": "#ff2200"}},
        selective_override=True,
    )
    assert pal.by_type_values[dev1.type_key]["color"] == "#ff0000"
    assert pal.device_values[2]["color"] == "#ff2200"

    # 4. Record Universal Color Palette 2 using ch 1 -> applies to ch 3 when selected
    res_u = app.action_registry.execute(
        "palette.record",
        "color",
        2.0,
        label="Univ Blue",
        device_values={1: {"color": "#0000ff", "gobo": 3}},
        mode=PaletteMode.UNIVERSAL,
    )
    assert isinstance(res_u, dict)
    pal_u = res_u["palette"]
    assert pal_u.mode is PaletteMode.UNIVERSAL
    assert pal_u.universal_values == {"color": "#0000ff"}

    # Without selection, Universal palette applies to nothing
    assert app.action_registry.execute("palette.apply", "color", 2.0) == []
    # With ch 3 selected, Universal palette applies to ch 3
    assert app.action_registry.execute("palette.apply", "color", 2.0, channels=[3]) == [
        3
    ]

    # 5. Absolute apply does not record palette_refs on live_state
    app.live_state.set_palette_refs(3, {"color": ("color", 1.0)}, mark_manual=True)
    app.action_registry.execute(
        "palette.apply", "color", 2.0, channels=[3], absolute=True
    )
    assert app.live_state.get_palette_ref(3, "color") is None


def test_palette_set_mode_and_locked_actions_with_undo() -> None:
    """Verify palette.set_mode, palette.set_locked, and lock protection."""
    app = _make_app()
    cp = Palette(
        category=PaletteCategory.COLOR,
        number=5.0,
        text="Amber",
        device_values={1: {"color": "#ffaa00"}},
    )
    app.lightshow.palettes.add(cp)

    assert (
        app.action_registry.execute(
            "palette.set_mode", "color", 5.0, PaletteMode.BY_TYPE
        )
        is True
    )
    assert cp.mode is PaletteMode.BY_TYPE

    app.action_registry.execute("edit.undo")
    assert cp.mode is PaletteMode.SELECTIVE

    app.action_registry.execute("edit.redo")
    assert cp.mode is PaletteMode.BY_TYPE

    assert app.action_registry.execute("palette.set_locked", "color", 5.0, True) is True
    assert cp.locked is True

    # Locked palette rejects set_mode, record overwrite, and update
    assert (
        app.action_registry.execute(
            "palette.set_mode", "color", 5.0, PaletteMode.UNIVERSAL
        )
        is False
    )
    assert (
        app.action_registry.execute(
            "palette.update", "color", 5.0, device_values={1: {"color": "#ffffff"}}
        )
        is None
    )
    rec_res = app.action_registry.execute(
        "palette.record", "color", 5.0, device_values={1: {"color": "#ffffff"}}
    )
    assert isinstance(rec_res, dict)
    assert rec_res.get("locked") is True


def _run_cli(app: CoreApplication, cmd: str) -> CommandResult:
    app.commandline.set_string(cmd)
    return app.commandline.execute()


def test_cli_palette_mode_and_absolute_syntax() -> None:
    """Verify CLI parser & executor for BY TYPE, UNIVERSAL, SELECTIVE, ABSOLUTE."""
    app = _make_app()
    dev1 = _make_rgb_fixture(1, start_addr=1)
    dev2 = _make_rgb_fixture(2, start_addr=5)
    app.lightshow.patch.devices = {1: dev1, 2: dev2}
    app.selected_channels = [1]
    dev1.apply_device_values({"color": "#00ff00"})

    res_rec = _run_cli(app, "RECORD COLOR PALETTE 1 BY TYPE")
    assert res_rec.success is True
    cp1 = app.lightshow.palettes.get(PaletteCategory.COLOR, 1.0)
    assert cp1 is not None
    assert cp1.mode is PaletteMode.BY_TYPE
    assert dev1.type_key in cp1.by_type_values

    res_rec_u = _run_cli(app, "RECORD CP 2 UNIVERSAL")
    assert res_rec_u.success is True
    cp2 = app.lightshow.palettes.get(PaletteCategory.COLOR, 2.0)
    assert cp2 is not None
    assert cp2.mode is PaletteMode.UNIVERSAL

    # Selective update via CLI
    dev2.apply_device_values({"color": "#00cc44"})
    app.selected_channels = [2]
    res_upd = _run_cli(app, "UPDATE CP 1 SELECTIVE")
    assert res_upd.success is True
    assert 2 in cp1.device_values

    # Absolute apply via CLI
    app.live_state.set_palette_refs(2, {"color": ("color", 1.0)}, mark_manual=True)
    res_abs = _run_cli(app, "2 CP 1 ABSOLUTE")
    assert res_abs.success is True
    assert app.live_state.get_palette_ref(2, "color") is None

    # Locked palette blocks CLI update
    app.action_registry.execute("palette.set_locked", "color", 1.0, True)
    res_locked = _run_cli(app, "UPDATE CP 1")
    assert res_locked.success is False
    assert "locked" in res_locked.message.lower()


def test_eos_ascii_import_preserves_by_type_marker(tmp_path: Path) -> None:
    """Verify Eos ASCII t-prefixed $$Param tokens promote palette to BY_TYPE."""
    ascii_content = "\n".join(
        [
            "Ident 3:0",
            "Manufacturer ETC",
            "Console Eos",
            "$ParamType 76 5 Diffusion",
            "$Personality 100",
            "   $$Manuf TestBrand",
            "   $$Model Spot_RGB",
            "   $$Footprint 1",
            "   $$PersChan 76 1 1 0 0",
            "$Patch 1 100 1 0 1",
            "$BeamPalette 2",
            "   Text FROST",
            "   $$Param 1 76@t255",
            "EndData",
        ]
    )
    asc_file = tmp_path / "by_type.asc"
    asc_file.write_text(ascii_content, encoding="ascii")

    lightshow = LightShow()
    imported = ImportFile(
        lightshow, Gio.File.new_for_path(str(asc_file)), FileType.ASCII
    )
    imported.parse_sync(auto_import=True)

    bp2 = lightshow.palettes.get(PaletteCategory.BEAM, 2.0)
    assert bp2 is not None
    assert bp2.mode is PaletteMode.BY_TYPE
    assert bp2.by_type_values
    assert any(vals.get("frost") == 1.0 for vals in bp2.by_type_values.values())
