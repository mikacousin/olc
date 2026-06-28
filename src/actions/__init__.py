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

from olc.actions.channel import (
    LevelMinusAction,
    LevelPlusAction,
    SelectActiveChannelAction,
    SelectAddChannelAction,
    SelectAllChannelsAction,
    SelectNoneChannelsAction,
    SelectRemoveChannelAction,
    SelectThruChannelAction,
    SetChannelLevelAction,
    SetLevelFromCmdAction,
    SetLevelFullAction,
    SetMultiChannelsLevelAction,
)
from olc.actions.cue import (
    CueCopyAction,
    CueDeleteAction,
    CueInsertAction,
    CueRenameAction,
    CueSelectAction,
    CueSetChannelLevelAction,
    CueSetTempChannelsAction,
    CueUpdateAction,
)
from olc.actions.curve import (
    CurveDeleteAction,
    CurveNewAction,
    CurveSetLimitAction,
    CurveUpdatePointsAction,
)
from olc.actions.edit import RedoAction, UndoAction
from olc.actions.fader import (
    FaderAssignAction,
    FaderClearAction,
    FaderSetLevelAction,
    FaderSetPageAction,
)
from olc.actions.group import (
    DeleteGroupAction,
    GroupRenameAction,
    GroupSelectAction,
    GroupSetTempChannelsAction,
    GroupUpdateChannelsAction,
    NewGroupAction,
)
from olc.actions.gui import SwitchTabAction, ZoomAction
from olc.actions.independent import (
    IndependentChangeTypeAction,
    IndependentRenameAction,
    IndependentSetLevelAction,
    IndependentUpdateChannelsAction,
)
from olc.actions.patch import (
    PatchAddOutputAction,
    PatchClearAction,
    PatchSelectOutputAction,
    PatchSet1on1Action,
    PatchSetOutputCurveAction,
    PatchUnpatchOutputAction,
)
from olc.actions.playback import (
    GoAction,
    GoBackAction,
    PauseAction,
    SequenceMinusAction,
    SequencePlusAction,
)
from olc.actions.sequence import (
    SequenceDeleteAction,
    SequenceDeleteStepAction,
    SequenceInsertStepAction,
    SequenceNewAction,
    StepUpdateChannelTimeAction,
    StepUpdateTextAction,
    StepUpdateTimesAction,
)

if typing.TYPE_CHECKING:
    from olc.core.registry import ActionRegistry


def register_all_actions(registry: ActionRegistry) -> None:
    """Import and register all concrete Action subclasses.

    Args:
        registry: The ActionRegistry to register the actions into.
    """
    actions_to_register = [
        SetChannelLevelAction,
        SetMultiChannelsLevelAction,
        SelectActiveChannelAction,
        SelectThruChannelAction,
        SelectAddChannelAction,
        SelectRemoveChannelAction,
        SelectAllChannelsAction,
        SetLevelFromCmdAction,
        SetLevelFullAction,
        LevelPlusAction,
        LevelMinusAction,
        NewGroupAction,
        DeleteGroupAction,
        GroupUpdateChannelsAction,
        GroupRenameAction,
        GroupSelectAction,
        GroupSetTempChannelsAction,
        CueUpdateAction,
        CueDeleteAction,
        CueRenameAction,
        CueCopyAction,
        CueInsertAction,
        CueSelectAction,
        CueSetChannelLevelAction,
        CueSetTempChannelsAction,
        GoAction,
        GoBackAction,
        PauseAction,
        SequencePlusAction,
        SequenceMinusAction,
        UndoAction,
        RedoAction,
        PatchAddOutputAction,
        PatchUnpatchOutputAction,
        PatchClearAction,
        PatchSelectOutputAction,
        PatchSet1on1Action,
        PatchSetOutputCurveAction,
        CurveNewAction,
        CurveDeleteAction,
        CurveUpdatePointsAction,
        CurveSetLimitAction,
        SequenceNewAction,
        SequenceDeleteAction,
        SequenceInsertStepAction,
        SequenceDeleteStepAction,
        StepUpdateTimesAction,
        StepUpdateTextAction,
        StepUpdateChannelTimeAction,
        FaderAssignAction,
        FaderClearAction,
        FaderSetLevelAction,
        FaderSetPageAction,
        SelectNoneChannelsAction,
        IndependentRenameAction,
        IndependentSetLevelAction,
        IndependentUpdateChannelsAction,
        IndependentChangeTypeAction,
        ZoomAction,
        SwitchTabAction,
    ]

    for action_class in actions_to_register:
        registry.register(action_class)
