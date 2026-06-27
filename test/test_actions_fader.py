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
from olc.cue import Cue
from olc.fader import FaderGroup, FaderMain, FaderPreset, FaderSequence, FaderType
from olc.group import Group
from olc.sequence import Sequence


def test_fader_assign_group() -> None:
    """FaderAssignAction assigns a Group to a fader and is undoable."""
    settings = MagicMock()
    app = CoreApplication(settings)

    group = Group(1.0, {1: 200, 2: 150}, "G1")
    app.lightshow.groups.add(group)

    # Initial state: fader 1 page 1 is NONE
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE

    # Assign group 1 to fader page=1, index=1
    app.action_registry.execute("fader.assign", 1, 1, FaderType.GROUP, 1.0)

    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.GROUP
    fader = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(fader, FaderGroup)
    assert fader.contents is group

    # Undo → back to NONE
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE

    # Redo → GROUP again
    app.history.redo()
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.GROUP


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

    group = Group(1.0, {1: 200}, "G1")
    app.lightshow.groups.add(group)

    # First assign a group
    app.action_registry.execute("fader.assign", 1, 1, FaderType.GROUP, 1.0)
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.GROUP

    # Now clear it
    app.action_registry.execute("fader.clear", 1, 1)
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.NONE

    # Undo clear → GROUP restored
    app.history.undo()
    assert app.lightshow.fader_bank.get_fader_type(1, 1) == FaderType.GROUP
    fader = app.lightshow.fader_bank.faders[1][1]
    assert isinstance(fader, FaderGroup)
    assert fader.contents is group

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
