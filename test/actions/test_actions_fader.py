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
"""Unit tests for FaderAssignAction and FaderClearAction."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication
from olc.show.cue import Cue
from olc.show.fader import (
    FaderEffect,
    FaderMain,
    FaderPreset,
    FaderSequence,
    FaderType,
)
from olc.show.palette import Palette, PaletteCategory
from olc.show.sequence import Sequence


def test_fader_assign_preset_palette() -> None:
    """FaderAssignAction assigns a Preset palette to a FaderPreset and is undoable."""
    import pytest

    settings = MagicMock()
    app = CoreApplication(settings)

    preset = Palette(
        category=PaletteCategory.PRESET,
        number=1.0,
        text="Preset 1",
        channels={1: 0.8, 2: 0.5},
    )
    app.lightshow.palettes.add(preset)

    # Initial state: fader 1 page 1 is NONE
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE

    # Assign preset 1 to fader page=1, index=1
    app.action_registry.execute("fader.assign", 1, 1, FaderType.PRESET, 1.0)

    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    fader = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(fader, FaderPreset)
    assert fader.contents is preset
    assert fader.channels == {1, 2}

    fader.set_level(0.5)
    assert fader.dmx[0] == pytest.approx(0.4)
    assert fader.dmx[1] == pytest.approx(0.25)

    # Undo → back to NONE
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE

    # Redo → PRESET again
    app.history.redo()
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    assert app.lightshow.fader_bank.faders[1][1].contents is preset


def test_fader_assign_preset_prefers_palette_over_cue() -> None:
    """When Preset N and Cue N both exist, FaderType.PRESET prefers the Preset."""
    settings = MagicMock()
    app = CoreApplication(settings)

    cue5 = Cue(0, 5.0, {1: 1.0}, "Cue 5")
    app.lightshow.cues.append(cue5)
    preset5 = Palette(
        category=PaletteCategory.PRESET,
        number=5.0,
        text="Sub 5",
        channels={2: 0.6},
    )
    app.lightshow.palettes.add(preset5)

    app.action_registry.execute("fader.assign", 1, 1, FaderType.PRESET, 5.0)
    fader = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(fader, FaderPreset)
    assert fader.contents is preset5


def test_fader_assign_preset() -> None:
    """FaderAssignAction assigns a Cue (Preset) to a fader and is undoable."""
    settings = MagicMock()
    app = CoreApplication(settings)

    cue = Cue(0, 1.0, {1: 100}, "Cue 1")
    app.lightshow.cues.append(cue)

    app.action_registry.execute("fader.assign", 1, 2, FaderType.PRESET, 1.0)

    assert app.lightshow.fader_bank.get_fader_type(1, 2) == FaderType.PRESET
    fader = app.lightshow.fader_bank.faders[1][2]
    assert isinstance(fader, FaderPreset)
    assert fader.contents is cue

    # Undo
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 2) == FaderType.NONE

    # Redo
    app.history.redo()
    assert app.lightshow.fader_bank.get_fader_type(1, 2) == FaderType.PRESET


def test_fader_assign_sequence() -> None:
    """FaderAssignAction assigns a Sequence (chaser) to a fader and is undoable."""
    settings = MagicMock()
    app = CoreApplication(settings)

    chaser = Sequence(2.0, "Chaser 2")
    app.lightshow.chasers.append(chaser)

    app.action_registry.execute("fader.assign", 1, 3, FaderType.SEQUENCE, 2.0)

    assert app.lightshow.fader_bank.get_fader_type(1, 3) == FaderType.SEQUENCE
    fader = app.lightshow.fader_bank.faders[1][3]
    assert isinstance(fader, FaderSequence)
    assert fader.contents is chaser

    # Undo
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 3) == FaderType.NONE

    # Redo
    app.history.redo()
    assert app.lightshow.fader_bank.get_fader_type(1, 3) == FaderType.SEQUENCE


def test_fader_assign_main_undoable() -> None:
    """FaderAssignAction for FaderMain is reversible by undo."""
    settings = MagicMock()
    app = CoreApplication(settings)

    app.action_registry.execute("fader.assign", 1, 4, FaderType.MAIN)

    assert app.lightshow.fader_bank.get_fader_type(1, 4) == FaderType.MAIN
    assert isinstance(app.lightshow.fader_bank.faders[1][4], FaderMain)

    # Undo → back to NONE
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 4) == FaderType.NONE

    # Redo → MAIN again
    app.history.redo()
    assert app.lightshow.fader_bank.get_fader_type(1, 4) == FaderType.MAIN


def test_fader_clear() -> None:
    """FaderClearAction resets a fader to NONE and is undoable."""
    settings = MagicMock()
    app = CoreApplication(settings)

    preset = Palette(
        category=PaletteCategory.PRESET,
        number=1.0,
        text="P1",
        channels={1: 0.8},
    )
    app.lightshow.palettes.add(preset)

    # First assign a preset
    app.action_registry.execute("fader.assign", 1, 1, FaderType.PRESET, 1.0)
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET

    # Now clear it
    app.action_registry.execute("fader.clear", 1, 1)
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE

    # Undo clear → PRESET restored
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.PRESET
    fader = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(fader, FaderPreset)
    assert fader.contents is preset

    # Redo clear → NONE again
    app.history.redo()
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE


def test_fader_assign_emits_signal() -> None:
    """FaderAssignAction emits 'fader.changed' with page and index."""
    settings = MagicMock()
    app = CoreApplication(settings)

    received: list[tuple[int, int]] = []
    app.subscribe("fader.changed", lambda page, index: received.append((page, index)))

    app.action_registry.execute("fader.assign", 2, 3, FaderType.NONE)

    assert len(received) == 1
    assert received[0] == (2, 3)


def test_fader_clear_emits_signal() -> None:
    """FaderClearAction emits 'fader.changed' with page and index."""
    settings = MagicMock()
    app = CoreApplication(settings)

    received: list[tuple[int, int]] = []
    app.subscribe("fader.changed", lambda page, index: received.append((page, index)))

    app.action_registry.execute("fader.clear", 1, 5)

    assert len(received) == 1
    assert received[0] == (1, 5)


def test_fader_flash() -> None:
    """FaderFlashAction triggers flash on/off and emits fader.flash_changed."""
    settings = MagicMock()
    app = CoreApplication(settings)

    received: list[tuple[int, bool]] = []
    app.subscribe(
        "fader.flash_changed",
        lambda idx, pressed: received.append((idx, pressed)),
    )

    fader = app.lightshow.fader_bank.faders[1][1]
    fader.flash_on = MagicMock()
    fader.flash_off = MagicMock()

    # Flash ON
    app.action_registry.execute("fader.flash", 1, 1, True)
    fader.flash_on.assert_called_once()
    assert received == [(1, True)]
    action = app.action_registry.get("fader.flash")
    assert action.get_feedback_state() == {"active": True, "index": 1}

    # Flash OFF
    app.action_registry.execute("fader.flash", 1, 1, False)
    fader.flash_off.assert_called_once()
    assert received == [(1, True), (1, False)]
    action = app.action_registry.get("fader.flash")
    assert action.get_feedback_state() == {"active": False, "index": 1}


def test_fader_assign_effect_starts_scales_and_stops() -> None:
    """FaderEffect starts, scales size/rate, flashes, and stops an effect cleanly."""
    import pytest

    app = CoreApplication(MagicMock())
    eff = app.action_registry.execute(
        "effect.create", 1.0, "Sine Wave", template_id="sine_dimmer"
    )
    app.selected_channels = [1, 2, 3, 4]

    # Assign Effect 1 to Fader 1 on Page 1
    app.action_registry.execute("fader.assign", 1, 1, FaderType.EFFECT, 1.0)
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.EFFECT
    fader = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(fader, FaderEffect)
    assert fader.contents is eff
    assert fader.effect_channels == [1, 2, 3, 4]

    # Move fader to 50% -> starts effect with size_scale = 0.5
    app.action_registry.execute("fader.set_level", 1, 1, 0.5)
    active = app.effects_engine.get_active_instances()
    assert len(active) == 1
    assert active[0].effect_number == 1.0
    assert active[0].channels == [1, 2, 3, 4]
    assert active[0].size_scale == pytest.approx(0.5)

    # Flash ON -> pushes size_scale to 1.0
    app.action_registry.execute("fader.flash", 1, 1, True)
    active = app.effects_engine.get_active_instances()
    assert active[0].size_scale == pytest.approx(1.0)

    # Flash OFF -> restores 0.5
    app.action_registry.execute("fader.flash", 1, 1, False)
    active = app.effects_engine.get_active_instances()
    assert active[0].size_scale == pytest.approx(0.5)

    # Switch to rate control mode and move fader to 75% (rate_scale = 1.5)
    fader.control_mode = "rate"
    app.action_registry.execute("fader.set_level", 1, 1, 0.75)
    active = app.effects_engine.get_active_instances()
    assert active[0].rate_scale == pytest.approx(1.5)

    # Bring fader to 0% -> stops effect
    app.action_registry.execute("fader.set_level", 1, 1, 0.0)
    assert len(app.effects_engine.get_active_instances()) == 0

    # Undo fader assignment -> back to NONE
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE
