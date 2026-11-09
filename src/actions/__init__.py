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
    ChannelSneakAction,
    ChannelWheelAdjustAction,
    LevelMinusAction,
    LevelPlusAction,
    SelectActiveChannelAction,
    SelectAddChannelAction,
    SelectAllChannelsAction,
    SelectChannelsAction,
    SelectNoneChannelsAction,
    SelectRemoveChannelAction,
    SelectThruChannelAction,
    SetChannelLevelAction,
    SetLevelFromCmdAction,
    SetLevelFullAction,
    SetMultiChannelsLevelAction,
)
from olc.actions.commandline import (
    CommandLineAppendCharAction,
    CommandLineAutocompleteAction,
    CommandLineBackspaceAction,
    CommandLineClearAction,
    CommandLineExecuteAction,
    CommandLineHistoryNextAction,
    CommandLineHistoryPrevAction,
    CommandLineSetAction,
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
from olc.actions.device import (
    DeviceAdjustParameterAction,
    DeviceHomeAction,
    DeviceLocateAction,
    DevicePanTiltAdjustAction,
    DeviceSetColorAction,
    DeviceSetPanTiltAction,
    DeviceSetParameterAction,
)
from olc.actions.dmx import (
    DmxBlackoutAllAction,
    DmxClearUserOutputsAction,
    DmxSetUniverseLevelsAction,
    DmxTestOutputAction,
    UniverseAddAction,
    UniverseBlackoutAction,
    UniverseRemoveAction,
    UniverseSetConfigAction,
    UniverseSetProtocolAction,
)
from olc.actions.edit import RedoAction, UndoAction
from olc.actions.fader import (
    FaderAssignAction,
    FaderClearAction,
    FaderFlashAction,
    FaderSetLevelAction,
    FaderSetPageAction,
)
from olc.actions.fixture import (
    FixtureDeleteAction,
    FixtureImportGdtfAction,
    FixtureUpsertAction,
)
from olc.actions.group import (
    DeleteGroupAction,
    GroupRenameAction,
    GroupSelectAction,
    GroupSetTempChannelsAction,
    GroupUpdateChannelsAction,
    NewGroupAction,
)
from olc.actions.gui import (
    AboutOpenAction,
    FullscreenToggleAction,
    SetDefaultTimeAction,
    SetPercentDisplayAction,
    SetThemeAction,
    ShortcutsOpenAction,
    TabCloseAction,
    TabMoveAction,
    TabOpenAction,
    VirtualConsoleOpenAction,
    ZoomAction,
)
from olc.actions.independent import (
    IndependentChangeTypeAction,
    IndependentRenameAction,
    IndependentSetLevelAction,
    IndependentUpdateChannelsAction,
)
from olc.actions.main_fader import MainFaderSetLevelAction
from olc.actions.midi import (
    MidiAssignMappingAction,
    MidiClearMappingsAction,
    MidiLearnToggleAction,
    MidiPortToggleAction,
    MidiSetPortModeAction,
)
from olc.actions.osc import (
    OscRemoveSubscriberAction,
    OscSetConfigAction,
    OscToggleAction,
    OscToggleStaticClientAction,
)
from olc.actions.park import (
    AddressParkAction,
    AddressUnparkAction,
    ChannelParkAction,
    ChannelUnparkAction,
    ParkUnparkAllAction,
)
from olc.actions.patch import (
    PatchAddOutputAction,
    PatchClearAction,
    PatchDeviceAction,
    PatchSet1on1Action,
    PatchSetDeviceCurveAction,
    PatchSetOutputCurveAction,
    PatchUnpatchDeviceAction,
    PatchUnpatchOutputAction,
)
from olc.actions.playback import (
    GoAction,
    GoBackAction,
    PauseAction,
    PlaybackGotoAction,
    PlaybackManualXFadeAction,
    PlaybackRecordCueAction,
    PlaybackSneakAction,
    PlaybackUpdateActiveStepAction,
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
from olc.actions.show import (
    ShowExportAsciiAction,
    ShowImportAction,
    ShowNewAction,
    ShowOpenAction,
    ShowResetUserLevelsAction,
    ShowSaveAction,
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
        SelectChannelsAction,
        SelectActiveChannelAction,
        SelectThruChannelAction,
        SelectAddChannelAction,
        SelectRemoveChannelAction,
        SelectAllChannelsAction,
        SetLevelFromCmdAction,
        SetLevelFullAction,
        ChannelSneakAction,
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
        PatchDeviceAction,
        PatchUnpatchDeviceAction,
        PatchClearAction,
        PatchSet1on1Action,
        PatchSetDeviceCurveAction,
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
        TabOpenAction,
        TabCloseAction,
        TabMoveAction,
        VirtualConsoleOpenAction,
        FullscreenToggleAction,
        ShortcutsOpenAction,
        AboutOpenAction,
        SetThemeAction,
        SetPercentDisplayAction,
        SetDefaultTimeAction,
        CommandLineAppendCharAction,
        CommandLineAutocompleteAction,
        CommandLineClearAction,
        CommandLineSetAction,
        CommandLineExecuteAction,
        CommandLineBackspaceAction,
        CommandLineHistoryPrevAction,
        CommandLineHistoryNextAction,
        FaderFlashAction,
        PlaybackGotoAction,
        ChannelWheelAdjustAction,
        PlaybackManualXFadeAction,
        PlaybackRecordCueAction,
        PlaybackSneakAction,
        PlaybackUpdateActiveStepAction,
        MidiPortToggleAction,
        MidiSetPortModeAction,
        MidiLearnToggleAction,
        MidiAssignMappingAction,
        MidiClearMappingsAction,
        UniverseAddAction,
        UniverseRemoveAction,
        UniverseBlackoutAction,
        UniverseSetProtocolAction,
        UniverseSetConfigAction,
        DmxSetUniverseLevelsAction,
        DmxTestOutputAction,
        DmxClearUserOutputsAction,
        DmxBlackoutAllAction,
        MainFaderSetLevelAction,
        DevicePanTiltAdjustAction,
        DeviceSetPanTiltAction,
        DeviceSetColorAction,
        DeviceSetParameterAction,
        DeviceAdjustParameterAction,
        DeviceHomeAction,
        DeviceLocateAction,
        FixtureUpsertAction,
        FixtureDeleteAction,
        FixtureImportGdtfAction,
        OscToggleAction,
        OscSetConfigAction,
        OscToggleStaticClientAction,
        OscRemoveSubscriberAction,
        ChannelParkAction,
        ChannelUnparkAction,
        AddressParkAction,
        AddressUnparkAction,
        ParkUnparkAllAction,
        ShowNewAction,
        ShowResetUserLevelsAction,
        ShowOpenAction,
        ShowSaveAction,
        ShowExportAsciiAction,
        ShowImportAction,
    ]

    for action_class in actions_to_register:
        registry.register(action_class)
