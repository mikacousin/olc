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
"""Unit tests for ActionRegistry and HistoryManager error cases and boundaries."""

from __future__ import annotations

import typing
from unittest.mock import MagicMock

import pytest
from olc.core.action import Action
from olc.core.app import CoreApplication


class MockAction(Action):
    """Minimal Action implementation used for testing the ActionRegistry."""

    name = "mock.test_action"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.executed = False
        self.undone = False

    def execute(self) -> None:
        self.executed = True

    def undo(self) -> None:
        self.undone = True

    def redo(self) -> None:
        self.executed = True


def test_registry_unregistered_action_errors() -> None:
    """ActionRegistry must raise KeyError for unregistered action operations."""
    settings = MagicMock()
    app = CoreApplication(settings)

    with pytest.raises(KeyError, match="Action 'unknown.action' is not registered"):
        app.action_registry.get("unknown.action")

    with pytest.raises(KeyError, match="Action 'unknown.action' is not registered"):
        app.action_registry.execute("unknown.action")


def test_registry_feedback_exception_isolation() -> None:
    """ActionRegistry feedback propagation must not crash if a binding fails."""
    settings = MagicMock()
    app = CoreApplication(settings)
    app.action_registry.register(MockAction)

    # Mock a crashing binding
    crashing_binding = MagicMock()
    crashing_binding.send_feedback.side_effect = RuntimeError("Feedback failed")

    app.action_registry.register_binding("mock.test_action", crashing_binding)

    # Should execute successfully without throwing the RuntimeError
    app.action_registry.execute("mock.test_action")

    crashing_binding.send_feedback.assert_called_once()


def test_history_manager_boundaries() -> None:
    """HistoryManager must handle empty state undo/redo calls gracefully."""
    settings = MagicMock()
    app = CoreApplication(settings)

    # Undo/redo on empty stacks should be no-ops
    app.history.undo()
    app.history.redo()

    # Register mock action
    app.action_registry.register(MockAction)
    app.action_registry.execute("mock.test_action")

    # Undo once
    app.history.undo()
    action = typing.cast(MockAction, app.action_registry.get("mock.test_action"))
    assert action.undone is True

    # Redo once
    app.history.redo()
    assert action.executed is True
