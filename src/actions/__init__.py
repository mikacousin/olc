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
from __future__ import annotations

import typing

from olc.actions.channel import SetChannelLevelAction
from olc.actions.edit import RedoAction, UndoAction
from olc.actions.group import DeleteGroupAction, NewGroupAction
from olc.actions.playback import GoAction, PauseAction

if typing.TYPE_CHECKING:
    from olc.core.registry import ActionRegistry


def register_all_actions(registry: ActionRegistry) -> None:
    """Import and register all concrete Action subclasses.

    Args:
        registry: The ActionRegistry to register the actions into.
    """
    actions_to_register = [
        SetChannelLevelAction,
        NewGroupAction,
        DeleteGroupAction,
        GoAction,
        PauseAction,
        UndoAction,
        RedoAction,
    ]

    for action_class in actions_to_register:
        registry.register(action_class)
