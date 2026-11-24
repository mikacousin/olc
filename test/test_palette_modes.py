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
"""Unit tests for PaletteMode, type_key, hierarchical resolution, and cascade."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.devices.device import LightingDevice
from olc.devices.fixture import FixtureType
from olc.show.cue import Cue
from olc.show.palette import (
    Palette,
    PaletteCategory,
    PaletteManager,
    PaletteMode,
    default_mode_for_category,
    get_channel_type_key,
)
from olc.show.step import Step


def _make_device(
    fixture_id: int,
    *,
    fixture_type: FixtureType = FixtureType.MOVING_HEAD,
    manufacturer: str = "Robe",
    model: str = "MegaPointe",
    mode_name: str = "Mode 1 (39ch)",
    gdtf_id: str = "",
) -> LightingDevice:
    return LightingDevice(
        fixture_id=fixture_id,
        label=f"Fix {fixture_id}",
        fixture_type=fixture_type,
        manufacturer=manufacturer,
        model=model,
        mode_name=mode_name,
        gdtf_id=gdtf_id,
    )


def test_lighting_device_type_key_variants() -> None:
    """Verify canonical type_key generation across GDTF, mfr+model+mode, and generic."""
    dev_gdtf = _make_device(1, gdtf_id="ABC-123", mode_name="Extended")
    assert dev_gdtf.type_key == "gdtf:abc-123::extended"

    dev_gdtf_no_mode = _make_device(2, gdtf_id="ABC-123", mode_name="")
    assert dev_gdtf_no_mode.type_key == "gdtf:abc-123"

    dev_mfr_a = _make_device(3, manufacturer="Robe", model="Esprite", mode_name="16bit")
    dev_mfr_b = _make_device(4, manufacturer="Robe", model="Esprite", mode_name="Basic")
    assert dev_mfr_a.type_key == "robe:esprite::16bit"
    assert dev_mfr_b.type_key == "robe:esprite::basic"
    assert dev_mfr_a.type_key != dev_mfr_b.type_key

    dev_dimmer = _make_device(
        5,
        fixture_type=FixtureType.DIMMER,
        manufacturer="Generic",
        model="",
        mode_name="",
    )
    assert dev_dimmer.type_key == "type:dimmer"


def test_default_mode_for_category() -> None:
    """Verify default PaletteMode mapping per category."""
    assert default_mode_for_category(PaletteCategory.FOCUS) is PaletteMode.SELECTIVE
    assert default_mode_for_category(PaletteCategory.PRESET) is PaletteMode.SELECTIVE
    assert default_mode_for_category(PaletteCategory.COLOR) is PaletteMode.BY_TYPE
    assert default_mode_for_category(PaletteCategory.BEAM) is PaletteMode.BY_TYPE
    assert default_mode_for_category(PaletteCategory.INTENSITY) is PaletteMode.BY_TYPE
    assert default_mode_for_category("color") is PaletteMode.BY_TYPE


def test_palette_hierarchical_resolution_priority() -> None:
    """Verify Selective > By-Type > Universal priority and attribute overlay."""
    type_a = "robe:esprite::16bit"
    type_b = "martin:mac_encore::std"

    pal = Palette(
        category=PaletteCategory.COLOR,
        number=1.0,
        text="Congo",
        mode=PaletteMode.BY_TYPE,
        universal_intensity=0.8,
        universal_values={"color": "#2200aa", "zoom": 0.5},
        by_type_channels={type_a: 0.9},
        by_type_values={type_a: {"color": "#1100cc", "ctc": 3200}},
        channels={2: 0.4},
        device_values={2: {"color": "#0000ff"}},
    )

    # Channel 1 (type_b, no selective, no by_type) -> falls back to Universal
    lvl1, devs1 = pal.resolve_channel(1, type_b)
    assert lvl1 == 0.8
    assert devs1 == {"color": "#2200aa", "zoom": 0.5}

    # Channel 3 (type_a, no selective) -> By-Type overrides Universal on shared keys
    lvl3, devs3 = pal.resolve_channel(3, type_a)
    assert lvl3 == 0.9
    assert devs3 == {"color": "#1100cc", "ctc": 3200, "zoom": 0.5}

    # Channel 2 (type_a, has Selective override on intensity & color)
    lvl2, devs2 = pal.resolve_channel(2, type_a)
    assert lvl2 == 0.4
    assert devs2 == {"color": "#0000ff", "ctc": 3200, "zoom": 0.5}

    assert pal.has_data_for_channel(1, type_b) is True
    assert pal.has_data_for_channel(99, None) is True

    sel_only = Palette(
        category=PaletteCategory.FOCUS,
        number=1.0,
        channels={10: 1.0},
    )
    assert sel_only.has_data_for_channel(10, type_a) is True
    assert sel_only.has_data_for_channel(11, type_a) is False


def test_palette_mode_serialization_roundtrip_and_legacy_compat() -> None:
    """Verify to_dict/from_dict round-trip and backward compatibility."""
    legacy_payload = {
        "category": "focus",
        "number": 5.0,
        "label": "Center",
        "channels": {1: 1.0},
        "device_values": {1: {"pan": 0.5, "tilt": 0.5}},
    }
    legacy = Palette.from_dict(legacy_payload)
    assert legacy.mode is PaletteMode.SELECTIVE
    assert legacy.locked is False
    assert legacy.by_type_channels == {}
    assert legacy.universal_intensity is None
    assert "mode" not in legacy.to_dict()
    assert "locked" not in legacy.to_dict()

    rich = Palette(
        category=PaletteCategory.COLOR,
        number=2.0,
        text="Warm",
        mode=PaletteMode.UNIVERSAL,
        locked=True,
        by_type_channels={"robe:esprite": 0.75},
        by_type_values={"robe:esprite": {"color": "#ffaa44"}},
        universal_intensity=1.0,
        universal_values={"color": "#ff9933"},
    )
    dumped = rich.to_dict()
    restored = Palette.from_dict(dumped)
    assert restored.mode is PaletteMode.UNIVERSAL
    assert restored.locked is True
    assert restored.by_type_channels == {"robe:esprite": 0.75}
    assert restored.by_type_values == {"robe:esprite": {"color": "#ffaa44"}}
    assert restored.universal_intensity == 1.0
    assert restored.universal_values == {"color": "#ff9933"}


def test_cascade_propagation_with_by_type_and_selective_override() -> None:
    """Verify PaletteManager.propagate_update resolves By-Type for patched fixtures."""
    dev1 = _make_device(1, manufacturer="Robe", model="Spiider", mode_name="Std")
    dev2 = _make_device(2, manufacturer="Robe", model="Spiider", mode_name="Std")
    dev3 = _make_device(3, manufacturer="Robe", model="Spiider", mode_name="Std")
    type_key = dev1.type_key

    mgr = PaletteManager()
    cp1 = Palette(
        category=PaletteCategory.COLOR,
        number=1.0,
        text="Blue",
        mode=PaletteMode.BY_TYPE,
        by_type_values={type_key: {"color": "#0000ff"}},
        device_values={3: {"color": "#0022ff"}},  # Selective override on ch 3
    )
    mgr.add(cp1)

    preset1 = Palette(
        category=PaletteCategory.PRESET,
        number=1.0,
        text="Look",
        device_values={2: {"color": "#000000"}, 3: {"color": "#000000"}},
        palette_refs={
            2: {"color": ("color", 1.0)},
            3: {"color": ("color", 1.0)},
        },
    )
    mgr.add(preset1)

    cue1 = Cue(1, 1.0, text="Cue 1")
    cue1.device_values = {
        1: {"color": "#000000"},
        2: {"color": "#000000"},
        3: {"color": "#000000"},
    }
    cue1.palette_refs = {
        1: {"color": ("color", 1.0)},
        2: {"color": ("preset", 1.0)},
        3: {"color": ("color", 1.0)},
    }

    lightshow = MagicMock()
    lightshow.patch.devices = {1: dev1, 2: dev2, 3: dev3}
    lightshow.iter_all_cues.return_value = [cue1]
    lightshow.main_playback.steps = [Step(sequence=0, cue=cue1)]
    lightshow.effects.all.return_value = []
    lightshow.fader_bank.faders = {}

    assert get_channel_type_key(lightshow, 2) == type_key

    # Update By-Type value on cp1 and propagate
    cp1.by_type_values[type_key]["color"] = "#0088ff"
    stats = mgr.propagate_update(lightshow, PaletteCategory.COLOR, 1.0)

    assert stats["presets"] == 1
    assert stats["cues"] == 1
    # Ch 1 & 2 inherit updated By-Type value (directly or via Preset 1)
    assert preset1.device_values[2]["color"] == "#0088ff"
    assert cue1.device_values[1]["color"] == "#0088ff"
    assert cue1.device_values[2]["color"] == "#0088ff"
    # Ch 3 keeps its Selective override
    assert cue1.device_values[3]["color"] == "#0022ff"
