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
"""Unit tests for Fixture Library actions, user persistence, and patch sync."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.devices.builtin import create_moving_head_definition
from olc.devices.channel import ChannelType
from olc.devices.fixture import (
    ChannelDefinition,
    DmxModeDefinition,
    FixtureDefinition,
    delete_user_fixture,
    get_user_fixtures_dir,
    save_user_fixture,
)


@pytest.fixture
def core_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CoreApplication:
    """Fixture providing CoreApplication with isolated user fixtures dir."""
    user_fixtures = tmp_path / "user_fixtures"
    monkeypatch.setenv("OLC_USER_FIXTURES_DIR", str(user_fixtures))
    app = CoreApplication(MagicMock())
    return app


def test_builtin_fixtures_protection(core_app: CoreApplication) -> None:
    """Built-in fixtures must have is_builtin=True and cannot be modified or deleted."""
    lib = core_app.lightshow.fixture_library
    dimmer = lib.get("Generic", "Dimmer")
    assert dimmer.is_builtin is True

    # Trying to delete built-in definition raises ValueError
    with pytest.raises(ValueError, match="Cannot delete built-in"):
        core_app.action_registry.execute("fixture.delete", "Generic", "Dimmer")

    # Trying to upsert over built-in raises ValueError
    dimmer_mod = dimmer.clone()
    dimmer_mod.notes = "Attempt to overwrite"
    with pytest.raises(ValueError, match="Built-in fixture.*is read-only"):
        core_app.action_registry.execute(
            "fixture.upsert",
            dimmer_mod,
            old_manufacturer="Generic",
            old_model="Dimmer",
        )


def test_user_fixture_persistence_and_loading(
    core_app: CoreApplication, tmp_path: Path
) -> None:
    """User fixture definitions are saved to JSON, reloaded, and can be deleted."""
    custom_def = FixtureDefinition(
        manufacturer="Acme",
        model="Solaris 500",
        notes="Custom LED bar",
        dmx_modes=[
            DmxModeDefinition(
                name="Mode 3ch",
                channel_defs=[
                    ChannelDefinition(ChannelType.RED, offset=0, label="Red"),
                    ChannelDefinition(ChannelType.GREEN, offset=1, label="Green"),
                    ChannelDefinition(ChannelType.BLUE, offset=2, label="Blue"),
                ],
            )
        ],
        is_builtin=False,
    )

    # Save to disk
    saved_path = save_user_fixture(custom_def)
    assert saved_path is not None
    assert saved_path.exists()

    with open(saved_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["manufacturer"] == "Acme"
    assert data["model"] == "Solaris 500"
    assert data["is_builtin"] is False

    # Reload into a fresh library
    from olc.devices.builtin import populate_builtin_library

    fresh_lib = populate_builtin_library()
    loaded_acme = fresh_lib.get("Acme", "Solaris 500")
    assert loaded_acme is not None
    assert loaded_acme.is_builtin is False
    assert len(loaded_acme.dmx_modes) == 1

    # Delete
    deleted = delete_user_fixture("Acme", "Solaris 500")
    assert deleted is True
    assert not saved_path.exists()


def test_fixture_upsert_action_and_undo(core_app: CoreApplication) -> None:
    """FixtureUpsertAction adds custom definition and undoes properly."""
    lib = core_app.lightshow.fixture_library
    custom_def = FixtureDefinition(
        manufacturer="Robe",
        model="Pointe",
        dmx_modes=[
            DmxModeDefinition(
                name="Standard 16ch",
                channel_defs=[
                    ChannelDefinition(ChannelType.PAN, offset=0, label="Pan"),
                    ChannelDefinition(ChannelType.TILT, offset=1, label="Tilt"),
                    ChannelDefinition(ChannelType.INTENSITY, offset=2, label="Dimmer"),
                ],
            )
        ],
        is_builtin=False,
    )

    # Execute creation
    core_app.action_registry.execute("fixture.upsert", custom_def)
    assert "Robe:Pointe" in lib.keys()

    disk_dir = get_user_fixtures_dir()
    expected_file = disk_dir / "Robe__Pointe.json"
    assert expected_file.exists()

    # Modify definition (e.g. rename to Pointe II)
    mod_def = custom_def.clone(new_model="Pointe II")
    core_app.action_registry.execute(
        "fixture.upsert",
        mod_def,
        old_manufacturer="Robe",
        old_model="Pointe",
    )
    assert "Robe:Pointe II" in lib.keys()
    assert "Robe:Pointe" not in lib.keys()
    assert (disk_dir / "Robe__Pointe_II.json").exists()
    assert not expected_file.exists()

    # Undo modification
    core_app.action_registry.execute("edit.undo")
    assert "Robe:Pointe" in lib.keys()
    assert "Robe:Pointe II" not in lib.keys()

    # Undo creation
    core_app.action_registry.execute("edit.undo")
    assert "Robe:Pointe" not in lib.keys()


def test_fixture_delete_action_with_patched_safety(core_app: CoreApplication) -> None:
    """FixtureDeleteAction refuses deletion if devices are patched."""
    lib = core_app.lightshow.fixture_library
    custom_def = FixtureDefinition(
        manufacturer="Showtec",
        model="Sunstrip",
        dmx_modes=[
            DmxModeDefinition(
                name="10ch",
                channel_defs=[
                    ChannelDefinition(
                        ChannelType.INTENSITY, offset=i, label=f"Lamp {i + 1}"
                    )
                    for i in range(10)
                ],
            )
        ],
        is_builtin=False,
    )
    core_app.action_registry.execute("fixture.upsert", custom_def)
    assert "Showtec:Sunstrip" in lib.keys()

    # Patch device #1 using this definition
    core_app.lightshow.patch.patch_device(1, custom_def, 1, 1)

    # Deletion must fail because device 1 uses it
    with pytest.raises(ValueError, match="in use by 1 patched device"):
        core_app.action_registry.execute("fixture.delete", "Showtec", "Sunstrip")

    # Unpatch device #1
    core_app.lightshow.patch.unpatch_device(1)

    # Deletion now succeeds
    core_app.action_registry.execute("fixture.delete", "Showtec", "Sunstrip")
    assert "Showtec:Sunstrip" not in lib.keys()

    # Undo restores definition
    core_app.action_registry.execute("edit.undo")
    assert "Showtec:Sunstrip" in lib.keys()


def test_live_update_synchronizes_patched_devices(core_app: CoreApplication) -> None:
    """Updating FixtureDefinition live updates channels of patched devices."""
    mh_def = create_moving_head_definition().clone(
        new_manufacturer="Custom", new_model="Moving Head"
    )
    core_app.action_registry.execute("fixture.upsert", mh_def)

    # Patch device 1
    core_app.lightshow.patch.patch_device(1, mh_def, 1, 1)
    dev = core_app.lightshow.patch.devices[1]
    dev.set_intensity(0.75)
    dev.set_position_degrees(30.0, -15.0)

    pan_ch = dev.get_channel(ChannelType.PAN)
    assert pan_ch is not None
    assert pan_ch.physical_max == 270.0
    assert dev.intensity == 0.75

    # Clone definition and modify physical bounds and default Home value
    updated_def = mh_def.clone()
    mode = updated_def.default_mode()
    pan_def = mode.channel_defs[0]
    pan_def.physical_max = 540.0
    pan_def.default_value = 40000

    core_app.action_registry.execute(
        "fixture.upsert",
        updated_def,
        old_manufacturer="Custom",
        old_model="Moving Head",
    )

    # Verify that device 1 was live-updated
    updated_dev = core_app.lightshow.patch.devices[1]
    updated_pan_ch = updated_dev.get_channel(ChannelType.PAN)
    assert updated_pan_ch is not None
    assert updated_pan_ch.physical_max == 540.0
    assert updated_pan_ch.default_value == (40000 >> 8) & 0xFF
    assert updated_dev.intensity == 0.75
    assert updated_dev.pan_degrees == pytest.approx(30.0, abs=0.2)
