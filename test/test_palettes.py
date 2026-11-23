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


def test_palette_propagate_update_counts_and_ticks_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """propagate_update counts effects referencing the palette and ticks when live."""
    settings = MagicMock()
    settings.get_double.return_value = 5.0
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    ls = app.lightshow

    cp1 = Palette(
        category=PaletteCategory.COLOR,
        number=1.0,
        text="Red",
        device_values={1: {"color": "#ff0000"}},
    )
    cp2 = Palette(
        category=PaletteCategory.COLOR,
        number=2.0,
        text="Blue",
        device_values={1: {"color": "#0000ff"}},
    )
    bp3 = Palette(
        category=PaletteCategory.BEAM,
        number=3.0,
        text="Frost",
        device_values={1: {"frost": 0.5}},
    )
    ls.palettes.add(cp1)
    ls.palettes.add(cp2)
    ls.palettes.add(bp3)

    ls.effects.create_from_template("two_color_chase", 1.0, label="Two-Color")

    tick_calls = 0
    orig_tick = app.effects_engine.tick

    def _spy_tick(now: float | None = None) -> bool:
        nonlocal tick_calls
        tick_calls += 1
        return orig_tick(now=now)

    monkeypatch.setattr(app.effects_engine, "tick", _spy_tick)

    # Effect is stopped -> counts effect, does not tick
    cp1.device_values[1]["color"] = "#ff8800"
    res1 = ls.palettes.propagate_update(ls, PaletteCategory.COLOR, 1.0)
    assert res1["effects"] == 1
    assert tick_calls == 0

    # Unrelated and missing palettes count 0 effects
    res_unrelated = ls.palettes.propagate_update(ls, PaletteCategory.BEAM, 3.0)
    assert res_unrelated["effects"] == 0
    res_missing = ls.palettes.propagate_update(ls, PaletteCategory.COLOR, 99.0)
    assert res_missing["effects"] == 0
    assert tick_calls == 0

    # Start effect -> propagate_update triggers live tick
    app.effects_engine.start_effect(1.0, [1])
    tick_calls = 0
    cp2.device_values[1]["color"] = "#00ffaa"
    res2 = ls.palettes.propagate_update(ls, PaletteCategory.COLOR, 2.0)
    assert res2["effects"] == 1
    assert tick_calls == 1


def test_palette_update_action_syncs_and_removes_preset_palette_refs() -> None:
    """Updating a Preset from Live updates new palette_refs & drops overridden refs."""
    from olc.actions import register_all_actions  # noqa: PLC0415
    from olc.devices.builtin import create_rgb_definition  # noqa: PLC0415

    settings = MagicMock()
    settings.get_double.return_value = 5.0
    settings.get_boolean.return_value = True
    app = CoreApplication(settings)
    register_all_actions(app.action_registry)
    ls = app.lightshow
    ls.patch.patch_device(1, create_rgb_definition(), 1, 1, label="RGB 1")

    cp1 = Palette(
        category=PaletteCategory.COLOR,
        number=1.0,
        text="Red",
        device_values={1: {"color": "#ff0000"}},
    )
    cp2 = Palette(
        category=PaletteCategory.COLOR,
        number=2.0,
        text="Blue",
        device_values={1: {"color": "#0000ff"}},
    )
    ls.palettes.add(cp1)
    ls.palettes.add(cp2)

    # Record Preset 5 referencing CP 1
    app.action_registry.execute("palette.apply", "color", 1.0, channels=[1])
    app.action_registry.execute("channel.set_level", 1, 0.9)
    app.action_registry.execute("palette.record", "preset", 5.0, "Look 5", [1])
    preset5 = ls.palettes.get(PaletteCategory.PRESET, 5.0)
    assert preset5 is not None
    assert preset5.palette_refs.get(1, {}).get("color") == ("color", 1.0)

    # Apply CP 2 in Live and Update Preset 5 -> palette_refs switches to CP 2
    app.action_registry.execute("palette.apply", "color", 2.0, channels=[1])
    app.action_registry.execute("palette.update", "preset", 5.0, channels=[1])
    assert preset5.palette_refs.get(1, {}).get("color") == ("color", 2.0)

    # Cascade test: modifying CP 2 now updates Preset 5
    cp2.device_values[1]["color"] = "#0088ff"
    ls.palettes.propagate_update(ls, PaletteCategory.COLOR, 2.0)
    assert preset5.device_values[1]["color"] == "#0088ff"

    # Manual color override in Live breaks ref; updating Preset 5 removes color ref
    app.action_registry.execute("device.set_color", 0.1, 0.9, 0.1, channels=[1])
    app.action_registry.execute("palette.update", "preset", 5.0, channels=[1])
    assert "color" not in preset5.palette_refs.get(1, {})

    # Modifying CP 2 must NO LONGER overwrite Preset 5's manual green
    cp2.device_values[1]["color"] = "#4400ff"
    ls.palettes.propagate_update(ls, PaletteCategory.COLOR, 2.0)
    assert preset5.device_values[1]["color"] != "#4400ff"

    # Undo restores ("color", 2.0) ref; Redo drops it again
    app.history.undo()
    preset5_undo = ls.palettes.get(PaletteCategory.PRESET, 5.0)
    assert preset5_undo is not None
    assert preset5_undo.palette_refs.get(1, {}).get("color") == ("color", 2.0)
    app.history.redo()
    preset5_redo = ls.palettes.get(PaletteCategory.PRESET, 5.0)
    assert preset5_redo is not None
    assert "color" not in preset5_redo.palette_refs.get(1, {})
