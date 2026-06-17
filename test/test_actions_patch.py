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
"""Unit tests for DMX Patch actions and Undo/Redo."""

from __future__ import annotations

from unittest.mock import MagicMock

from olc.core.app import CoreApplication


def test_patch_add_output_and_undo_redo() -> None:
    """Test patch.add_output action and its undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch

    # 1. Initialize empty patch
    app.action_registry.execute("patch.clear")
    assert len(patch.outputs) == 0

    patch_events = 0

    def on_patch_changed() -> None:
        nonlocal patch_events
        patch_events += 1

    app.subscribe("patch.changed", on_patch_changed)

    # Add output patch: Channel 5 to Output 10, Universe 1
    app.action_registry.execute("patch.add_output", 5, 10, 1)
    assert patch_events == 1
    assert 1 in patch.outputs
    assert 10 in patch.outputs[1]
    assert patch.outputs[1][10] == [5, 0]  # [channel, curve]
    assert patch.channels[5] == [[10, 1]]

    # Undo add patch
    app.history.undo()
    assert patch_events == 2
    assert 10 not in patch.outputs.get(1, {})

    # Redo add patch
    app.history.redo()
    assert patch_events == 3
    assert patch.outputs[1][10] == [5, 0]

    # Add another patch to the same output: Channel 6 to Output 10, Universe 1
    # This should unpatch Channel 5 from Output 10 first
    app.action_registry.execute("patch.add_output", 6, 10, 1)
    assert patch.outputs[1][10] == [6, 0]
    assert patch.channels[5] == [[None, None]]
    assert patch.channels[6] == [[10, 1]]

    # Undo setting to Channel 6 -> should restore Channel 5 on Output 10
    app.history.undo()
    assert patch.outputs[1][10] == [5, 0]
    assert patch.channels[5] == [[10, 1]]
    assert patch.channels[6] == [[None, None]]

    # Redo -> Channel 6 on Output 10
    app.history.redo()
    assert patch.outputs[1][10] == [6, 0]


def test_patch_unpatch_and_undo_redo() -> None:
    """Test patch.unpatch_output action and its undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch

    app.action_registry.execute("patch.clear")
    app.action_registry.execute("patch.add_output", 6, 10, 1)
    assert patch.outputs[1][10] == [6, 0]

    # Unpatch output 10
    app.action_registry.execute("patch.unpatch_output", 10, 1)
    assert 10 not in patch.outputs.get(1, {})
    assert patch.channels[6] == [[None, None]]

    # Undo unpatch -> restore Channel 6 on Output 10
    app.history.undo()
    assert patch.outputs[1][10] == [6, 0]
    assert patch.channels[6] == [[10, 1]]


def test_patch_set_1on1_and_undo_redo() -> None:
    """Test patch.set_1on1 action and its undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch

    app.action_registry.execute("patch.clear")
    app.action_registry.execute("patch.add_output", 6, 10, 1)

    # Set 1on1 patch
    app.action_registry.execute("patch.set_1on1")
    # Output 1 should be Channel 1, Output 10 should be Channel 10
    assert patch.outputs[1][1] == [1, 0]
    assert patch.outputs[1][10] == [10, 0]

    # Undo 1on1 -> should restore Channel 6 on Output 10 and clear others
    app.history.undo()
    assert patch.outputs[1][10] == [6, 0]
    assert 1 not in patch.outputs.get(1, {})

    # Redo 1on1
    app.history.redo()
    assert patch.outputs[1][1] == [1, 0]
    assert patch.outputs[1][10] == [10, 0]


def test_patch_set_output_curve_and_undo_redo() -> None:
    """Test patch.set_output_curve action and its undo/redo."""
    settings = MagicMock()
    app = CoreApplication(settings)
    patch = app.lightshow.patch

    app.action_registry.execute("patch.set_1on1")
    assert patch.outputs[1][10] == [10, 0]

    # Set output curve
    app.action_registry.execute("patch.set_output_curve", 10, 1, 5)
    assert patch.outputs[1][10] == [10, 5]

    # Undo set output curve
    app.history.undo()
    assert patch.outputs[1][10] == [10, 0]

    # Redo set output curve
    app.history.redo()
    assert patch.outputs[1][10] == [10, 5]
