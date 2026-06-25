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


class SetChannelLevelAction(Action):
    """Action to set the DMX user-override level of a channel.

    Supports Undo/Redo by capturing the previous user level.
    """

    name = "channel.set_level"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.channel: int = 1
        self.level: int = -1
        self.old_level: int = -1

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

        # Validate channel and level bounds
        if not 1 <= channel <= MAX_CHANNELS:
            raise ValueError(
                f"Channel index must be between 1 and {MAX_CHANNELS}. Got {channel}."
            )
        if not -1 <= level <= 255:
            raise ValueError(f"DMX Level must be between -1 and 255. Got {level}.")

        # Access backend dmx override levels if initialized
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            # Capture the current override level (0-indexed in NumPy array)
            self.old_level = int(backend.dmx.levels["user"][channel - 1])
            # Set the new override level
            backend.dmx.levels["user"][channel - 1] = level
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()
        else:
            self.old_level = -1

        # Emit the event so subscribers (like GUI) can refresh
        self.app.emit("channel.level_changed", channel, level)

    def undo(self) -> None:
        """Undo the channel level change, restoring its previous value."""
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            backend.dmx.levels["user"][self.channel - 1] = self.old_level
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        self.app.emit("channel.level_changed", self.channel, self.old_level)

    def redo(self) -> None:
        """Redo the channel level change."""
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            backend.dmx.levels["user"][self.channel - 1] = self.level
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        self.app.emit("channel.level_changed", self.channel, self.level)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Provides feedback state of the channel."""
        return {
            "channel": self.channel,
            "level": self.level,
            "active": self.level > 0,
        }

    def __repr__(self) -> str:
        return f"<SetChannelLevelAction channel={self.channel} level={self.level}>"


class SelectActiveChannelAction(Action):
    """Action to select a channel logically by reading the commandline."""

    name = "channel.select_active"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_selection: list[int] = []
        self.old_last_selected: typing.Optional[int] = None
        self.new_selection: list[int] = []
        self.new_last_selected: typing.Optional[int] = None

    def execute(self) -> None:
        self.old_selection = list(self.app.selected_channels)
        self.old_last_selected = self.app.last_selected_channel

        cmd_string = self.app.commandline.get_string()
        if is_non_nul_int(cmd_string):
            channel = int(cmd_string)
            if 1 <= channel <= MAX_CHANNELS:
                self.new_selection = [channel]
                self.new_last_selected = channel
            else:
                self.new_selection = []
                self.new_last_selected = None
        else:
            self.new_selection = []
            self.new_last_selected = None

        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.commandline.set_string("")

        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def undo(self) -> None:
        self.app.selected_channels = list(self.old_selection)
        self.app.last_selected_channel = self.old_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def redo(self) -> None:
        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)


class SelectThruChannelAction(Action):
    """Action to select a range of channels logically (Thru)."""

    name = "channel.select_thru"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_selection: list[int] = []
        self.old_last_selected: typing.Optional[int] = None
        self.new_selection: list[int] = []
        self.new_last_selected: typing.Optional[int] = None

    def execute(self) -> None:
        self.old_selection = list(self.app.selected_channels)
        self.old_last_selected = self.app.last_selected_channel

        cmd_string = self.app.commandline.get_string()
        if is_non_nul_int(cmd_string) and self.old_last_selected is not None:
            from_chan = self.old_last_selected
            to_chan = int(cmd_string)
            low = min(from_chan, to_chan)
            high = max(from_chan, to_chan)

            self.new_selection = list(self.old_selection)
            for ch in range(low, high + 1):
                if 1 <= ch <= MAX_CHANNELS and ch not in self.new_selection:
                    self.new_selection.append(ch)
            self.new_last_selected = to_chan
        else:
            self.new_selection = list(self.old_selection)
            self.new_last_selected = self.old_last_selected

        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.commandline.set_string("")

        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def undo(self) -> None:
        self.app.selected_channels = list(self.old_selection)
        self.app.last_selected_channel = self.old_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def redo(self) -> None:
        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)


class SelectAddChannelAction(Action):
    """Action to add a channel logically (+)."""

    name = "channel.select_add"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_selection: list[int] = []
        self.old_last_selected: typing.Optional[int] = None
        self.new_selection: list[int] = []
        self.new_last_selected: typing.Optional[int] = None

    def execute(self) -> None:
        self.old_selection = list(self.app.selected_channels)
        self.old_last_selected = self.app.last_selected_channel

        cmd_string = self.app.commandline.get_string()
        if is_non_nul_int(cmd_string):
            channel = int(cmd_string)
            if 1 <= channel <= MAX_CHANNELS:
                self.new_selection = list(self.old_selection)
                if channel not in self.new_selection:
                    self.new_selection.append(channel)
                self.new_last_selected = channel
            else:
                self.new_selection = list(self.old_selection)
                self.new_last_selected = self.old_last_selected
        else:
            self.new_selection = list(self.old_selection)
            self.new_last_selected = self.old_last_selected

        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.commandline.set_string("")

        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def undo(self) -> None:
        self.app.selected_channels = list(self.old_selection)
        self.app.last_selected_channel = self.old_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def redo(self) -> None:
        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)


class SelectRemoveChannelAction(Action):
    """Action to remove a channel logically (-)."""

    name = "channel.select_remove"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_selection: list[int] = []
        self.old_last_selected: typing.Optional[int] = None
        self.new_selection: list[int] = []
        self.new_last_selected: typing.Optional[int] = None

    def execute(self) -> None:
        self.old_selection = list(self.app.selected_channels)
        self.old_last_selected = self.app.last_selected_channel

        cmd_string = self.app.commandline.get_string()
        if is_non_nul_int(cmd_string):
            channel = int(cmd_string)
            if 1 <= channel <= MAX_CHANNELS:
                self.new_selection = list(self.old_selection)
                if channel in self.new_selection:
                    self.new_selection.remove(channel)
                self.new_last_selected = channel
            else:
                self.new_selection = list(self.old_selection)
                self.new_last_selected = self.old_last_selected
        else:
            self.new_selection = list(self.old_selection)
            self.new_last_selected = self.old_last_selected

        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.commandline.set_string("")

        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def undo(self) -> None:
        self.app.selected_channels = list(self.old_selection)
        self.app.last_selected_channel = self.old_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def redo(self) -> None:
        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)


class SelectAllChannelsAction(Action):
    """Action to select all channels with intensity > 0."""

    name = "channel.select_all"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.old_selection: list[int] = []
        self.old_last_selected: typing.Optional[int] = None
        self.new_selection: list[int] = []
        self.new_last_selected: typing.Optional[int] = None

    def execute(self) -> None:
        self.old_selection = list(self.app.selected_channels)
        self.old_last_selected = self.app.last_selected_channel

        backend = getattr(self.app, "backend", None)
        selected = []
        if backend and backend.dmx:
            for ch in range(1, MAX_CHANNELS + 1):
                level = int(backend.dmx.levels["user"][ch - 1])
                if level > 0:
                    selected.append(ch)

        self.new_selection = selected
        self.new_last_selected = selected[-1] if selected else None

        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def undo(self) -> None:
        self.app.selected_channels = list(self.old_selection)
        self.app.last_selected_channel = self.old_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def redo(self) -> None:
        self.app.selected_channels = list(self.new_selection)
        self.app.last_selected_channel = self.new_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)


class SelectNoneChannelsAction(Action):
    """Action to clear all channel selection."""

    name = "channel.select_none"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.old_selection: list[int] = []
        self.old_last_selected: typing.Optional[int] = None

    def execute(self) -> None:
        """Clear channel selection and notify listeners."""
        self.old_selection = list(self.app.selected_channels)
        self.old_last_selected = self.app.last_selected_channel
        self.app.selected_channels = []
        self.app.last_selected_channel = None
        self.app.commandline.set_string("")
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def undo(self) -> None:
        self.app.selected_channels = list(self.old_selection)
        self.app.last_selected_channel = self.old_last_selected
        self.app.emit("channels.selected_changed", self.app.selected_channels)

    def redo(self) -> None:
        self.app.selected_channels = []
        self.app.last_selected_channel = None
        self.app.emit("channels.selected_changed", self.app.selected_channels)


class SetLevelFromCmdAction(Action):
    """Action to set the level of all selected channels from the commandline."""

    name = "channel.set_level_from_cmd"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channels: list[int] = []
        self.old_levels: dict[int, int] = {}
        self.new_levels: dict[int, int] = {}

    def execute(self) -> None:
        self.channels = list(self.app.selected_channels)
        self.old_levels = {}
        self.new_levels = {}

        cmd_string = self.app.commandline.get_string()
        if not is_int(cmd_string):
            return

        level = int(cmd_string)
        percent = getattr(self.app.settings, "get_boolean", lambda x: False)("percent")
        if percent:
            level = int(round((level / 100) * 255))
        level = min(max(level, 0), 255)

        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch in self.channels:
                old_lvl = int(backend.dmx.levels["user"][ch - 1])
                self.old_levels[ch] = old_lvl
                self.new_levels[ch] = level
                backend.dmx.levels["user"][ch - 1] = level

            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        self.app.commandline.set_string("")

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.new_levels.get(ch, -1))

    def undo(self) -> None:
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch, old_lvl in self.old_levels.items():
                backend.dmx.levels["user"][ch - 1] = old_lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.old_levels.get(ch, -1))

    def redo(self) -> None:
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch, new_lvl in self.new_levels.items():
                backend.dmx.levels["user"][ch - 1] = new_lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.new_levels.get(ch, -1))


class SetLevelFullAction(Action):
    """Action to set the level of all selected channels to 100%."""

    name = "channel.set_level_full"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channels: list[int] = []
        self.old_levels: dict[int, int] = {}
        self.new_levels: dict[int, int] = {}

    def execute(self) -> None:
        self.channels = list(self.app.selected_channels)
        self.old_levels = {}
        self.new_levels = {}

        level = 255

        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch in self.channels:
                old_lvl = int(backend.dmx.levels["user"][ch - 1])
                self.old_levels[ch] = old_lvl
                self.new_levels[ch] = level
                backend.dmx.levels["user"][ch - 1] = level

            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, level)

    def undo(self) -> None:
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch, old_lvl in self.old_levels.items():
                backend.dmx.levels["user"][ch - 1] = old_lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.old_levels.get(ch, -1))

    def redo(self) -> None:
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch, new_lvl in self.new_levels.items():
                backend.dmx.levels["user"][ch - 1] = new_lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.new_levels.get(ch, -1))


class LevelPlusAction(Action):
    """Action to increase the level of all selected channels."""

    name = "channel.level_plus"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channels: list[int] = []
        self.old_levels: dict[int, int] = {}
        self.new_levels: dict[int, int] = {}

    def execute(self) -> None:
        self.channels = list(self.app.selected_channels)
        self.old_levels = {}
        self.new_levels = {}

        step_level = getattr(self.app.settings, "get_int", lambda x: 10)(
            "percent-level"
        )
        percent = getattr(self.app.settings, "get_boolean", lambda x: False)("percent")

        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch in self.channels:
                old_lvl = int(backend.dmx.levels["user"][ch - 1])
                self.old_levels[ch] = old_lvl

                if percent:
                    percent_level = round((old_lvl / 256) * 100) + step_level
                    new_lvl = min(round((percent_level / 100) * 256), 255)
                else:
                    new_lvl = min(old_lvl + step_level, 255)

                self.new_levels[ch] = new_lvl
                backend.dmx.levels["user"][ch - 1] = new_lvl

            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.new_levels.get(ch, -1))

    def undo(self) -> None:
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch, old_lvl in self.old_levels.items():
                backend.dmx.levels["user"][ch - 1] = old_lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.old_levels.get(ch, -1))

    def redo(self) -> None:
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch, new_lvl in self.new_levels.items():
                backend.dmx.levels["user"][ch - 1] = new_lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.new_levels.get(ch, -1))


class LevelMinusAction(Action):
    """Action to decrease the level of all selected channels."""

    name = "channel.level_minus"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.channels: list[int] = []
        self.old_levels: dict[int, int] = {}
        self.new_levels: dict[int, int] = {}

    def execute(self) -> None:
        self.channels = list(self.app.selected_channels)
        self.old_levels = {}
        self.new_levels = {}

        step_level = getattr(self.app.settings, "get_int", lambda x: 10)(
            "percent-level"
        )
        percent = getattr(self.app.settings, "get_boolean", lambda x: False)("percent")

        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch in self.channels:
                old_lvl = int(backend.dmx.levels["user"][ch - 1])
                self.old_levels[ch] = old_lvl

                if percent:
                    percent_level = round((old_lvl / 256) * 100) - step_level
                    new_lvl = max(round((percent_level / 100) * 256), 0)
                else:
                    new_lvl = max(old_lvl - step_level, 0)

                self.new_levels[ch] = new_lvl
                backend.dmx.levels["user"][ch - 1] = new_lvl

            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.new_levels.get(ch, -1))

    def undo(self) -> None:
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch, old_lvl in self.old_levels.items():
                backend.dmx.levels["user"][ch - 1] = old_lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.old_levels.get(ch, -1))

    def redo(self) -> None:
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for ch, new_lvl in self.new_levels.items():
                backend.dmx.levels["user"][ch - 1] = new_lvl
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for ch in self.channels:
            self.app.emit("channel.level_changed", ch, self.new_levels.get(ch, -1))


class SetMultiChannelsLevelAction(Action):
    """Action to set the DMX user-override level of multiple channels at once.

    Supports Undo/Redo by capturing the previous user levels.
    """

    name = "channel.set_multi_levels"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.levels: dict[int, int] = {}
        self.old_levels: dict[int, int] = {}

    def configure(self, levels: dict[int, int]) -> None:
        """Configure the action with a dictionary mapping channel -> level.

        Args:
            levels: A dict of {channel: level} where channel is 1-based
                    and level is DMX intensity (0 to 255, or -1 to release).
        """
        self.levels = levels

    def execute(self) -> None:
        """Execute the action, setting user levels on multiple channels."""
        self.old_levels = {}
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for channel, level in self.levels.items():
                if 1 <= channel <= MAX_CHANNELS:
                    self.old_levels[channel] = int(
                        backend.dmx.levels["user"][channel - 1]
                    )
                    backend.dmx.levels["user"][channel - 1] = level
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for channel, level in self.levels.items():
            self.app.emit("channel.level_changed", channel, level)

    def undo(self) -> None:
        """Undo the multiple channel level changes, restoring their previous values."""
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for channel, old_level in self.old_levels.items():
                backend.dmx.levels["user"][channel - 1] = old_level
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for channel, old_level in self.old_levels.items():
            self.app.emit("channel.level_changed", channel, old_level)

    def redo(self) -> None:
        """Redo the multiple channel level changes."""
        backend = getattr(self.app, "backend", None)
        if backend and backend.dmx:
            for channel, level in self.levels.items():
                backend.dmx.levels["user"][channel - 1] = level
            self.app.lightshow.main_playback.update_channels()
            backend.dmx.set_levels()

        for channel, level in self.levels.items():
            self.app.emit("channel.level_changed", channel, level)
