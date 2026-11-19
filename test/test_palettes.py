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
"""Unit tests for Palette / Preset model and cascade propagation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from olc.core.app import CoreApplication
from olc.show.cue import Cue
from olc.show.fader import FaderPreset
from olc.show.palette import Palette, PaletteCategory, PaletteManager
from olc.show.step import Step


def test_palette_manager_crud_and_serialization() -> None:
    """Test Palette / Preset add, get, delete, listing, and round-trip."""
    mgr = PaletteManager()
    cp1 = Palette(
        category=PaletteCategory.COLOR,
        number=2.0,
        text="Deep Blue",
        device_values={1: {"color": "#0000ff"}},
    )
    cp2 = Palette(
        category=PaletteCategory.COLOR,
        number=1.0,
        text="Red",
        device_values={1: {"color": "#ff0000"}},
    )
    preset1 = Palette(
        category=PaletteCategory.PRESET,
        number=10.0,
        text="Look A",
        channels={1: 0.75},
        device_values={1: {"color": "#0000ff"}},
        palette_refs={1: {"color": ("color", 2.0)}},
    )

    mgr.add(cp1)
    mgr.add(cp2)
    mgr.add(preset1)
    assert len(mgr) == 3

    listed_colors = mgr.list_by_category(PaletteCategory.COLOR)
    assert [p.number for p in listed_colors] == [1.0, 2.0]
    assert mgr.get("color", 2.0) is cp1

    payload = mgr.to_dict()
    mgr2 = PaletteManager()
    mgr2.from_dict(payload)
    assert len(mgr2) == 3
    restored_preset = mgr2.get(PaletteCategory.PRESET, 10.0)
    assert restored_preset is not None
    assert restored_preset.text == "Look A"
    assert restored_preset.channels == {1: 0.75}
    assert restored_preset.palette_refs == {1: {"color": ("color", 2.0)}}

    assert mgr2.delete("color", 1.0) is True
    assert mgr2.delete("color", 1.0) is False
    assert len(mgr2) == 2


def test_palette_propagate_update_cascade_presets_cues_and_faders() -> None:
    """Test cascade propagation: Palette -> Preset -> Cue and FaderPreset."""
    settings = MagicMock()
    settings.get_double.return_value = 5.0
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    ls = app.lightshow

    # Setup initial palettes
    cp = Palette(
        category=PaletteCategory.COLOR,
        number=2.0,
        text="Blue",
        device_values={1: {"color": "#0000ff"}},
    )
    ip = Palette(
        category=PaletteCategory.INTENSITY,
        number=1.0,
        text="Full",
        channels={1: 1.0},
    )
    ls.palettes.add(cp)
    ls.palettes.add(ip)

    # Preset 5 references IP 1 (intensity) and CP 2 (color)
    preset = Palette(
        category=PaletteCategory.PRESET,
        number=5.0,
        text="Wash Blue",
        channels={1: 1.0},
        device_values={1: {"color": "#0000ff"}},
        palette_refs={
            1: {
                "intensity": ("intensity", 1.0),
                "color": ("color", 2.0),
            }
        },
    )
    ls.palettes.add(preset)

    # Cue 1 directly references CP 2; Cue 2 references Preset 5 with "*"
    cue1 = Cue(
        sequence=1,
        number=1.0,
        channels={1: 0.8},
        device_values={1: {"color": "#0000ff"}},
        palette_refs={1: {"color": ("color", 2.0)}},
    )
    cue2 = Cue(
        sequence=1,
        number=2.0,
        channels={1: 1.0},
        device_values={1: {"color": "#0000ff"}},
        palette_refs={1: {"*": ("preset", 5.0)}},
    )
    ls.cues.add(cue1)
    ls.cues.add(cue2)
    ls.main_playback.add_step(Step(1, cue=cue1))
    ls.main_playback.add_step(Step(1, cue=cue2))

    # FaderPreset attached directly to Preset 5
    fader = FaderPreset(1, ls.fader_bank, preset)
    ls.fader_bank.faders[1][1] = fader
    fader.set_level(0.5)
    assert fader.dmx[0] == pytest.approx(0.5)

    # 1. Edit Color Palette 2 -> propagates to Preset 5, Cue 1 & Cue 2 (cascade)
    cp.device_values[1]["color"] = "#00ff88"
    res1 = ls.palettes.propagate_update(ls, PaletteCategory.COLOR, 2.0)
    assert res1["presets"] == 1
    assert res1["cues"] == 2
    assert preset.device_values[1]["color"] == "#00ff88"
    assert cue1.device_values[1]["color"] == "#00ff88"
    assert cue2.device_values[1]["color"] == "#00ff88"

    # 2. Edit Intensity Palette 1 -> cascades to Preset 5 -> Cue 2 & FaderPreset DMX
    ip.channels[1] = 0.6
    res2 = ls.palettes.propagate_update(ls, PaletteCategory.INTENSITY, 1.0)
    assert res2["presets"] == 1
    assert res2["cues"] == 1
    assert res2["faders"] == 1
    assert preset.channels[1] == pytest.approx(0.6)
    assert cue2.channels[1] == pytest.approx(0.6)
    assert float(cue2.channels_array[0]) == pytest.approx(0.6)
    assert fader.dmx[0] == pytest.approx(0.3)


def test_palette_rename_action_undo_redo() -> None:
    """Test palette.rename updates label with Undo/Redo and rejects missing target."""
    settings = MagicMock()
    settings.get_double.return_value = 5.0
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)

    cp = Palette(
        category=PaletteCategory.COLOR,
        number=2.0,
        text="Old Blue",
        device_values={1: {"color": "#0000ff"}},
    )
    app.lightshow.palettes.add(cp)

    events: list[tuple[str, float, str]] = []
    app.subscribe(
        "palette.renamed",
        lambda cat, num, text: events.append((cat, num, text)),
    )

    ok = app.action_registry.execute("palette.rename", "color", 2.0, "Deep Ocean")
    assert ok is True
    assert cp.text == "Deep Ocean"
    assert events == [("color", 2.0, "Deep Ocean")]

    app.action_registry.execute("edit.undo")
    assert cp.text == "Old Blue"

    app.action_registry.execute("edit.redo")
    assert cp.text == "Deep Ocean"

    # Missing palette returns False cleanly without corrupting history
    missing = app.action_registry.execute("palette.rename", "color", 99.0, "Ghost")
    assert missing is False
