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


def test_fader_assign_preset() -> None:
    """FaderAssignAction assigns a Preset to a fader and is undoable."""
    settings = MagicMock()
    app = CoreApplication(settings)

    preset = Palette(
        category=PaletteCategory.PRESET,
        number=1.0,
        text="Preset 1",
        channels={1: 100},
    )
    app.lightshow.palettes.add(preset)

    app.action_registry.execute("fader.assign", 1, 2, FaderType.PRESET, 1.0)

    assert app.lightshow.fader_bank.get_fader_type(1, 2) == FaderType.PRESET
    fader = app.lightshow.fader_bank.faders[1][2]
    assert isinstance(fader, FaderPreset)
    assert fader.contents is preset

    # Undo
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 2) == FaderType.NONE

    # Redo
    app.history.redo()
    assert app.lightshow.fader_bank.get_fader_type(1, 2) == FaderType.PRESET


def test_fader_assign_sequence() -> None:
    """FaderAssignAction assigns a Sequence to a fader and is undoable."""
    settings = MagicMock()
    app = CoreApplication(settings)

    seq = Sequence(2.0, text="Seq 2")
    app.lightshow.sequences.append(seq)

    app.action_registry.execute("fader.assign", 1, 3, FaderType.SEQUENCE, 2.0)

    assert app.lightshow.fader_bank.get_fader_type(1, 3) == FaderType.SEQUENCE
    fader = app.lightshow.fader_bank.faders[1][3]
    assert isinstance(fader, FaderSequence)
    assert fader.contents is seq

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

    # Switch to rate control mode and move fader to 75% (musical rate_scale = 2.0)
    fader.control_mode = "rate"
    app.action_registry.execute("fader.set_level", 1, 1, 0.75)
    active = app.effects_engine.get_active_instances()
    assert active[0].rate_scale == pytest.approx(2.0)

    # Bring fader to 0% in rate mode -> freezes effect (rate_scale = 0.0)
    app.action_registry.execute("fader.set_level", 1, 1, 0.0)
    active = app.effects_engine.get_active_instances()
    assert len(active) == 1
    assert active[0].rate_scale == pytest.approx(0.0)

    # Switch back to size mode and bring fader to 0% -> stops effect
    fader.control_mode = "size"
    app.action_registry.execute("fader.set_level", 1, 1, 0.5)
    app.action_registry.execute("fader.set_level", 1, 1, 0.0)
    assert len(app.effects_engine.get_active_instances()) == 0

    # Undo fader assignment -> back to NONE
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE


def test_fader_effect_both_mode_and_format_target_channels() -> None:
    """FaderEffect supports 'both' scaling mode and concise channel formatting."""
    import pytest

    app = CoreApplication(MagicMock())
    app.action_registry.execute(
        "effect.create", 1.0, "Sine Wave", template_id="sine_dimmer"
    )
    app.selected_channels = [1, 2, 3, 4]
    app.action_registry.execute("fader.assign", 1, 1, FaderType.EFFECT, 1.0)
    fader = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(fader, FaderEffect)

    assert fader.format_target_channels() == "Ch 1..4"
    fader.set_effect_channels([])
    assert fader.format_target_channels() == "Auto (Sel)"
    fader.set_effect_channels([3])
    assert fader.format_target_channels() == "Ch 3"
    fader.set_effect_channels([4, 3, 2])
    assert fader.format_target_channels() == "Ch 4..2"
    fader.set_effect_channels([1, 3, 5])
    assert fader.format_target_channels() == "Ch 1,3,5"
    fader.set_effect_channels([1, 3, 5, 7])
    assert fader.format_target_channels() == "Ch 1,3… (4)"

    # 'both' mode scales size = level and rate = fader_level_to_rate_scale(level)
    fader.set_effect_channels([1, 2])
    fader.set_control_mode("both")
    app.action_registry.execute("fader.set_level", 1, 1, 0.5)
    active = app.effects_engine.get_active_instances()
    assert len(active) == 1
    assert active[0].size_scale == pytest.approx(0.5)
    assert active[0].rate_scale == pytest.approx(1.0)

    app.action_registry.execute("fader.set_level", 1, 1, 0.75)
    active = app.effects_engine.get_active_instances()
    assert active[0].size_scale == pytest.approx(0.75)
    assert active[0].rate_scale == pytest.approx(2.0)


def test_fader_configure_effect_and_assign_clear_undo_restore() -> None:
    """fader.configure_effect supports undo/redo; assign/clear restore state."""
    app = CoreApplication(MagicMock())
    app.action_registry.execute(
        "effect.create", 1.0, "Sine Wave", template_id="sine_dimmer"
    )
    app.action_registry.execute(
        "effect.create", 2.0, "Candle", template_id="candle_flicker"
    )
    app.selected_channels = [1, 2]
    app.action_registry.execute("fader.assign", 1, 1, FaderType.EFFECT, 1.0)
    fader = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(fader, FaderEffect)
    assert fader.control_mode == "size"
    assert fader.effect_channels == [1, 2]

    # Configure mode + target channels via action
    app.action_registry.execute(
        "fader.configure_effect", 1, 1, control_mode="both", effect_channels=[5, 6, 7]
    )
    assert fader.control_mode == "both"
    assert fader.effect_channels == [5, 6, 7]
    assert fader.format_target_channels() == "Ch 5..7"

    # Clear target channels -> Auto (Sel)
    app.action_registry.execute("fader.configure_effect", 1, 1, effect_channels=[])
    assert fader.effect_channels == []
    assert fader.format_target_channels() == "Auto (Sel)"

    # Undo clear channels
    app.history.undo()
    assert fader.effect_channels == [5, 6, 7]

    # Undo configure_effect ("both", [5, 6, 7]) -> back to ("size", [1, 2])
    app.history.undo()
    assert fader.control_mode == "size"
    assert fader.effect_channels == [1, 2]

    # Redo configure_effect -> back to ("both", [5, 6, 7])
    app.history.redo()
    assert fader.control_mode == "both"
    assert fader.effect_channels == [5, 6, 7]

    # Switching content on same EFFECT type preserves configured mode & channels
    app.selected_channels = [10]
    app.action_registry.execute("fader.assign", 1, 1, FaderType.EFFECT, 2.0)
    reassigned = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(reassigned, FaderEffect)
    assert reassigned.contents is not None
    assert reassigned.contents.number == 2.0
    assert reassigned.control_mode == "both"
    assert reassigned.effect_channels == [5, 6, 7]

    app.history.undo()
    assert app.lightshow.fader_bank.faders[1][1].contents.number == 1.0

    # Overwrite with a different fader type, then undo -> restores mode & channels
    app.action_registry.execute("fader.assign", 1, 1, FaderType.MAIN)
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.MAIN

    app.history.undo()
    restored = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(restored, FaderEffect)
    assert restored.contents is not None
    assert restored.contents.number == 1.0
    assert restored.control_mode == "both"
    assert restored.effect_channels == [5, 6, 7]

    # Clear fader, then undo -> restores control_mode & effect_channels
    app.action_registry.execute("fader.clear", 1, 1)
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE
    app.history.undo()
    restored_after_clear = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(restored_after_clear, FaderEffect)
    assert restored_after_clear.control_mode == "both"
    assert restored_after_clear.effect_channels == [5, 6, 7]


def test_fader_options_solo_inhibitive_swop_protect_lock_and_undo() -> None:
    """Verify solo_mode, swop_protect, inhibitive, lock, and fader.set_options."""
    import pytest

    from olc.core.dmx_backend import DMXBackend

    app = CoreApplication(MagicMock())
    app.backend = DMXBackend(app.lightshow)
    dmx = app.backend.dmx

    app.action_registry.execute("fader.assign", 1, 1, FaderType.CHANNELS, {1: 1})
    app.action_registry.execute("fader.assign", 1, 2, FaderType.CHANNELS, {2: 1})
    app.action_registry.execute("fader.assign", 1, 3, FaderType.CHANNELS, {3: 1})
    app.action_registry.execute("fader.assign", 1, 4, FaderType.CHANNELS, {4: 1})

    # 1. fader.set_options with Undo/Redo & locked guard
    app.action_registry.execute("fader.set_options", 1, 1, locked=True, solo_mode=True)
    f1 = app.lightshow.fader_bank.faders[1][1]
    assert f1.locked is True
    assert f1.solo_mode is True

    app.action_registry.execute("fader.assign", 1, 1, FaderType.NONE)
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.CHANNELS
    app.action_registry.execute("fader.clear", 1, 1)
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.CHANNELS

    app.history.undo()  # undo fader.set_options
    assert f1.locked is False
    assert f1.solo_mode is False
    app.history.redo()
    assert f1.locked is True
    assert f1.solo_mode is True

    # 2. Proportional Solo + Swop Protect + GM Exempt + Park
    app.action_registry.execute("fader.set_options", 1, 3, swop_protect=True)
    app.action_registry.execute("fader.set_options", 1, 4, exempt_grand_master=True)
    app.lightshow.park.park_channel(5, 0.8)
    dmx.levels["sequence"][5] = 1.0  # Ch 6 driven by sequence

    app.action_registry.execute("fader.set_level", 1, 2, 1.0)
    app.action_registry.execute("fader.set_level", 1, 3, 0.9)
    app.action_registry.execute("fader.set_level", 1, 4, 0.7)

    # Solo fader 1 at 50% -> ducks non-protected fader 2 and sequence ch 6 by 50%
    app.action_registry.execute("fader.set_level", 1, 1, 0.5)
    comp = dmx.get_all_composite_levels()
    assert comp[0] == pytest.approx(0.5)  # Solo fader ch 1
    assert comp[1] == pytest.approx(0.5)  # Ducked fader 2
    assert comp[2] == pytest.approx(0.9)  # Swop-protected fader 3
    assert comp[3] == pytest.approx(0.7)  # GM-exempt fader 4
    assert comp[4] == pytest.approx(0.8)  # Parked ch 5
    assert comp[5] == pytest.approx(0.5)  # Ducked sequence ch 6

    # Swop flash_on -> solo at 100%, non-protected sources ducked to 0.0
    app.action_registry.execute("fader.flash", 1, 1, True)
    comp_swop = dmx.get_all_composite_levels()
    assert comp_swop[0] == pytest.approx(1.0)
    assert comp_swop[1] == pytest.approx(0.0)
    assert comp_swop[2] == pytest.approx(0.9)
    assert comp_swop[3] == pytest.approx(0.7)
    assert comp_swop[4] == pytest.approx(0.8)
    assert comp_swop[5] == pytest.approx(0.0)
    app.action_registry.execute("fader.flash", 1, 1, False)
    app.action_registry.execute("fader.set_level", 1, 1, 0.0)

    # 3. Inhibitive fader caps sequence & normal faders, preserves Park & GM-exempt
    app.action_registry.execute("fader.assign", 1, 5, FaderType.CHANNELS, {2: 1, 6: 1})
    app.action_registry.execute("fader.set_options", 1, 5, inhibitive=True)
    f5 = app.lightshow.fader_bank.faders[1][5]
    assert f5.level == pytest.approx(1.0)  # Defaults to 100% on enable
    app.action_registry.execute("fader.set_level", 1, 5, 0.4)
    comp_inhib = dmx.get_all_composite_levels()
    assert comp_inhib[1] == pytest.approx(0.4)
    assert comp_inhib[5] == pytest.approx(0.4)
    assert comp_inhib[3] == pytest.approx(0.7)
    assert comp_inhib[4] == pytest.approx(0.8)
