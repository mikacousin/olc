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

from olc.core.action import Action
from olc.define import MAX_CHANNELS, is_int, is_non_nul_int

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class BaseChannelLevelAction(Action):
    """Base class for channel level modification actions."""

    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_levels: dict[int, int] = {}
        self.new_levels: dict[int, int] = {}

    def _apply_levels(self, levels_dict: dict[int, int]) -> None:
        """Apply a dict of {channel: level} to user DMX levels and emit events."""
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch, lvl in levels_dict.items():
                if 1 <= ch <= MAX_CHANNELS:
                    backend.dmx.levels["user"][ch - 1] = lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch, lvl in levels_dict.items():
            self.app.emit("channel.level_changed", ch, lvl)

    def undo(self) -> None:
        """Undo the channel level changes."""
        self._apply_levels(self.old_levels)

    def redo(self) -> None:
        """Redo the channel level changes."""
        self._apply_levels(self.new_levels)


class SetChannelLevelAction(BaseChannelLevelAction):
    """Action to set the DMX user-override level of a channel.

    Supports Undo/Redo by capturing the previous user level.
    """

    name = "channel.set_level"

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.channel: int = 1
        self.level: int = -1

    @property
    def old_level(self) -> int:
        """The previous override level of the channel."""
        return self.old_levels.get(self.channel, -1)

    @old_level.setter
    def old_level(self, val: int) -> None:
        self.old_levels[self.channel] = val

    def configure(self, channel: int, level: int) -> None:
        """Configure the action with the target channel and level.

        Args:
            channel: The 1-indexed channel number (1 to MAX_CHANNELS).
            level: The DMX intensity (0 to 255, or -1 to release override).
        """
        self.channel = channel
        self.level = level

    def execute(self) -> None:
        """Execute the action, setting the DMX channel level."""
        channel = self.channel
        level = self.level

        if not 1 <= channel <= MAX_CHANNELS:
            raise ValueError(
                f"Channel index must be between 1 and {MAX_CHANNELS}. Got {channel}."
            )
        if not -1 <= level <= 255:
            raise ValueError(f"DMX Level must be between -1 and 255. Got {level}.")

        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            self.old_levels[channel] = int(backend.dmx.levels["user"][channel - 1])
        else:
            self.old_levels[channel] = -1

        self.new_levels = {channel: level}
        self._apply_levels(self.new_levels)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the channel."""
        return {
            "channel": self.channel,
            "level": self.level,
            "active": self.level > 0,
        }

    def __repr__(self) -> str:
        return f"<SetChannelLevelAction channel={self.channel} level={self.level}>"


class BaseChannelSelectionAction(Action):
    """Base class for channel selection actions in ActionRegistry."""

    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_selection: list[int] = []
        self.old_last_selected: typing.Optional[int] = None
        self.new_selection: list[int] = []
        self.new_last_selected: typing.Optional[int] = None

    def _save_previous_selection(self) -> None:
        """Capture previous selection state."""
        self.old_selection = list(self.app.selected_channels)
        self.old_last_selected = self.app.last_selected_channel

    def _apply_selection(
        self,
        selection: list[int],
        last_selected: typing.Optional[int],
        clear_cmd: bool = False,
    ) -> None:
        """Apply new selection, optionally clear commandline, and emit event."""
        self.new_selection = list(selection)
        self.new_last_selected = last_selected
        self.app.selected_channels = list(selection)
        self.app.last_selected_channel = last_selected
        if clear_cmd:
            self.app.commandline.set_string("")
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def undo(self) -> None:
        """Restore previous selection."""
        self.app.selected_channels = list(self.old_selection)
        self.app.last_selected_channel = self.old_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def redo(self) -> None:
        """Re-apply new selection."""
        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)


class SelectActiveChannelAction(BaseChannelSelectionAction):
    """Action to select a channel logically by reading the commandline."""

    name = "channel.select_active"

    def execute(self) -> None:
        self._save_previous_selection()

        cmd_string = self.app.commandline.get_string()
        if is_non_nul_int(cmd_string):
            channel = int(cmd_string)
            if 1 <= channel <= MAX_CHANNELS:
                self._apply_selection([channel], channel, clear_cmd=True)
                return

        self._apply_selection([], None, clear_cmd=True)


class SelectThruChannelAction(BaseChannelSelectionAction):
    """Action to select a range of channels logically (Thru)."""

    name = "channel.select_thru"

    def execute(self) -> None:
        self._save_previous_selection()

        cmd_string = self.app.commandline.get_string()
        if is_non_nul_int(cmd_string) and self.old_last_selected is not None:
            from_chan = self.old_last_selected
            to_chan = int(cmd_string)
            low = min(from_chan, to_chan)
            high = max(from_chan, to_chan)

            new_sel = list(self.old_selection)
            for ch in range(low, high + 1):
                if 1 <= ch <= MAX_CHANNELS and ch not in new_sel:
                    new_sel.append(ch)
            self._apply_selection(new_sel, to_chan, clear_cmd=True)
        else:
            self._apply_selection(
                self.old_selection, self.old_last_selected, clear_cmd=True
            )


class SelectAddChannelAction(BaseChannelSelectionAction):
    """Action to add a channel logically (+)."""

    name = "channel.select_add"

    def execute(self) -> None:
        self._save_previous_selection()

        cmd_string = self.app.commandline.get_string()
        if is_non_nul_int(cmd_string):
            channel = int(cmd_string)
            if 1 <= channel <= MAX_CHANNELS:
                new_sel = list(self.old_selection)
                if channel not in new_sel:
                    new_sel.append(channel)
                self._apply_selection(new_sel, channel, clear_cmd=True)
                return

        self._apply_selection(
            self.old_selection, self.old_last_selected, clear_cmd=True
        )


class SelectRemoveChannelAction(BaseChannelSelectionAction):
    """Action to remove a channel logically (-)."""

    name = "channel.select_remove"

    def execute(self) -> None:
        self._save_previous_selection()

        cmd_string = self.app.commandline.get_string()
        if is_non_nul_int(cmd_string):
            channel = int(cmd_string)
            if 1 <= channel <= MAX_CHANNELS:
                new_sel = list(self.old_selection)
                if channel in new_sel:
                    new_sel.remove(channel)
                self._apply_selection(new_sel, channel, clear_cmd=True)
                return

        self._apply_selection(
            self.old_selection, self.old_last_selected, clear_cmd=True
        )


class SelectAllChannelsAction(BaseChannelSelectionAction):
    """Action to select all channels with intensity > 0."""

    name = "channel.select_all"

    def execute(self) -> None:
        self._save_previous_selection()

        backend = getattr(self.app, "backend", None)
        selected = []
        if backend and backend.dmx:
            for ch in range(1, MAX_CHANNELS + 1):
                level = int(backend.dmx.levels["user"][ch - 1])
                if level > 0:
                    selected.append(ch)

        last = selected[-1] if selected else None
        self._apply_selection(selected, last)


class SelectNoneChannelsAction(BaseChannelSelectionAction):
    """Action to clear all channel selection."""

    name = "channel.select_none"

    def execute(self) -> None:
        """Clear channel selection and notify listeners."""
        self._save_previous_selection()
        self._apply_selection([], None, clear_cmd=True)


class BaseSelectedChannelsLevelAction(BaseChannelLevelAction):
    """Base class for actions modifying levels on all currently selected channels."""

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channels: list[int] = []

    def _capture_old_levels(self) -> bool:
        """Capture current user levels for selected channels.

        Returns:
            True if channels were selected and backend is available, False otherwise.
        """
        self.channels = list(self.app.selected_channels)
        self.old_levels = {}
        self.new_levels = {}

        if not self.channels:
            self.can_undo = False
            return False

        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch in self.channels:
                if 1 <= ch <= MAX_CHANNELS:
                    self.old_levels[ch] = int(backend.dmx.levels["user"][ch - 1])
            return True

        self.can_undo = False
        return False


class SetLevelFromCmdAction(BaseSelectedChannelsLevelAction):
    """Action to set the level of all selected channels from the commandline."""

    name = "channel.set_level_from_cmd"

    def execute(self) -> None:
        cmd_string = self.app.commandline.get_string()
        if not is_int(cmd_string):
            return

        level = int(cmd_string)
        percent = getattr(self.app.settings, "get_boolean", lambda x: False)("percent")
        if percent:
            level = int(round((level / 100) * 255))
        level = min(max(level, 0), 255)

        if not self._capture_old_levels():
            return

        self.new_levels = {ch: level for ch in self.channels}
        self.app.commandline.set_string("")
        self._apply_levels(self.new_levels)


class SetLevelFullAction(BaseSelectedChannelsLevelAction):
    """Action to set the level of all selected channels to 100%."""

    name = "channel.set_level_full"

    def execute(self) -> None:
        if not self._capture_old_levels():
            return
        self.new_levels = {ch: 255 for ch in self.channels}
        self._apply_levels(self.new_levels)


class BaseRelativeLevelAction(BaseSelectedChannelsLevelAction):
    """Base class for relative level changes on selected channels."""

    def _apply_delta(self, delta: int, use_percent: bool = False) -> None:
        """Apply a relative offset to selected channel levels."""
        if not self._capture_old_levels():
            return

        step = abs(delta)
        direction = 1 if delta >= 0 else -1

        for ch, old_lvl in self.old_levels.items():
            if use_percent:
                old_pct = round((old_lvl / 256) * 100)
                new_pct = old_pct + (step if direction > 0 else -step)
                new_lvl = min(max(round((new_pct / 100) * 256), 0), 255)
            else:
                new_lvl = min(max(old_lvl + delta, 0), 255)

            if new_lvl != old_lvl:
                self.new_levels[ch] = new_lvl

        if self.new_levels:
            self._apply_levels(self.new_levels)
        else:
            self.can_undo = False


class LevelPlusAction(BaseRelativeLevelAction):
    """Action to increase the level of all selected channels."""

    name = "channel.level_plus"

    def execute(self) -> None:
        step_level = getattr(self.app.settings, "get_int", lambda x: 10)(
            "percent-level"
        )
        percent = getattr(self.app.settings, "get_boolean", lambda x: False)("percent")
        self._apply_delta(+step_level, use_percent=percent)


class LevelMinusAction(BaseRelativeLevelAction):
    """Action to decrease the level of all selected channels."""

    name = "channel.level_minus"

    def execute(self) -> None:
        step_level = getattr(self.app.settings, "get_int", lambda x: 10)(
            "percent-level"
        )
        percent = getattr(self.app.settings, "get_boolean", lambda x: False)("percent")
        self._apply_delta(-step_level, use_percent=percent)


class SetMultiChannelsLevelAction(BaseChannelLevelAction):
    """Action to set the DMX user-override level of multiple channels at once.

    Supports Undo/Redo by capturing the previous user levels.
    """

    name = "channel.set_multi_levels"

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.levels: dict[int, int] = {}

    def configure(self, levels: dict[int, int]) -> None:
        """Configure the action with a dictionary mapping channel -> level.

        Args:
            levels: A dict of {channel: level} where channel is 1-based
                    and level is DMX intensity (0 to 255, or -1 to release).
        """
        self.levels = dict(levels)
        self.new_levels = dict(levels)

    def execute(self) -> None:
        """Execute the action, setting user levels on multiple channels."""
        self.old_levels = {}
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for channel in self.levels:
                if 1 <= channel <= MAX_CHANNELS:
                    self.old_levels[channel] = int(
                        backend.dmx.levels["user"][channel - 1]
                    )
        self.new_levels = dict(self.levels)
        self._apply_levels(self.new_levels)


class ChannelWheelAdjustAction(BaseRelativeLevelAction):
    """Action to adjust the level of selected channels using an encoder wheel."""

    name = "channel.wheel_adjust"

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.step: int = 1
        self.direction: int = 1

    def configure(self, step: int = 1, direction: int = 1) -> None:
        """Configure the step and direction for the wheel adjustment.

        Args:
            step: Step size to adjust the channels by.
            direction: Positive for UP (+step), negative for DOWN (-step).
        """
        self.step = step
        self.direction = direction

    def execute(self) -> None:
        """Execute the wheel level adjustment on selected channels."""
        if self.step < 0:
            delta = self.step
        else:
            delta = self.step if self.direction > 0 else -self.step
        self._apply_delta(delta, use_percent=False)
