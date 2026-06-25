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
"""Headless logical channel selection manager and RPN actions."""

from __future__ import annotations

import typing
from abc import ABC, abstractmethod

from olc.define import MAX_CHANNELS, is_non_nul_int

if typing.TYPE_CHECKING:
    from olc.core.commandline import CoreCommandLine


class SelectionManager:
    """Manages channel selection state, associated actions, and local history."""

    def __init__(
        self,
        commandline: CoreCommandLine,
        on_changed_callback: typing.Optional[typing.Callable[[list[int]], None]] = None,
        history_manager: typing.Optional[typing.Any] = None,  # noqa: ANN401
        get_level_callback: typing.Optional[typing.Callable[[int], int]] = None,
    ) -> None:
        """Initialize the SelectionManager.

        Args:
            commandline: CoreCommandLine logical instance.
            on_changed_callback: Callback invoked when selection changes.
            history_manager: Optional external HistoryManager (e.g. Core history).
            get_level_callback: Callback to get channel intensity levels.
        """
        self.commandline = commandline
        self.selected_channels: list[int] = []
        self.last_selected_channel: typing.Optional[int] = None
        self.on_changed_callback = on_changed_callback
        self.history = history_manager
        self.get_level_callback = get_level_callback

    def execute_action(
        self,
        action_class: typing.Type[SelectionAction],
        *args: object,
        **kwargs: object,
    ) -> None:
        """Instantiate and execute a selection action on this manager.

        Args:
            action_class: The SelectionAction subclass to run.
            *args: Arguments for action configure().
            **kwargs: Keyword arguments for action configure().
        """
        action = action_class(self)
        configure = getattr(action, "configure", None)
        if callable(configure):
            configure(*args, **kwargs)
        action.execute()
        if self.history is not None:
            self.history.push(action)
        self.notify_changed()

    def notify_changed(self) -> None:
        """Invoke the change callback with a copy of current selected channels."""
        if self.on_changed_callback:
            self.on_changed_callback(list(self.selected_channels))


class SelectionAction(ABC):
    """Base class for all actions executing on a SelectionManager."""

    name: str = ""
    can_undo: bool = True

    def __init__(self, manager: SelectionManager) -> None:
        """Initialize the SelectionAction.

        Args:
            manager: The target SelectionManager instance.
        """
        self.manager = manager

    @abstractmethod
    def execute(self) -> None:
        """Execute the action on the manager."""

    @abstractmethod
    def undo(self) -> None:
        """Undo the selection changes."""

    def redo(self) -> None:
        """Redo the selection changes."""
        self.execute()
        self.manager.notify_changed()


class SelectActiveAction(SelectionAction):
    """Action to select a single channel (clears previous selection)."""

    name = "select.active"

    def __init__(self, manager: SelectionManager) -> None:
        super().__init__(manager)
        self.channel: int = 0
        self.old_selection: list[int] = []
        self.old_last: typing.Optional[int] = None

    def configure(self, channel: int = 0) -> None:
        """Configure the action with a channel index.

        If channel is 0, it reads from the commandline.
        """
        self.channel = channel

    def execute(self) -> None:
        self.old_selection = list(self.manager.selected_channels)
        self.old_last = self.manager.last_selected_channel

        chan = self.channel
        if not chan:
            cmd_string = self.manager.commandline.get_string()
            if is_non_nul_int(cmd_string):
                chan = int(cmd_string)
            else:
                return
        self.channel = chan

        if 1 <= chan <= MAX_CHANNELS:
            self.manager.selected_channels = [chan]
            self.manager.last_selected_channel = chan
            self.manager.commandline.set_string("")

    def undo(self) -> None:
        self.manager.selected_channels = list(self.old_selection)
        self.manager.last_selected_channel = self.old_last
        self.manager.notify_changed()


class SelectAddAction(SelectionAction):
    """Action to add a channel to the selection."""

    name = "select.add"

    def __init__(self, manager: SelectionManager) -> None:
        super().__init__(manager)
        self.channel: int = 0
        self.old_selection: list[int] = []
        self.old_last: typing.Optional[int] = None

    def configure(self, channel: int = 0) -> None:
        """Configure the action with a channel index to add.

        If channel is 0, it reads from the commandline.
        """
        self.channel = channel

    def execute(self) -> None:
        self.old_selection = list(self.manager.selected_channels)
        self.old_last = self.manager.last_selected_channel

        chan = self.channel
        if not chan:
            cmd_string = self.manager.commandline.get_string()
            if is_non_nul_int(cmd_string):
                chan = int(cmd_string)
            else:
                return
        self.channel = chan

        if 1 <= chan <= MAX_CHANNELS:
            new_sel = list(self.old_selection)
            if chan not in new_sel:
                new_sel.append(chan)
            self.manager.selected_channels = new_sel
            self.manager.last_selected_channel = chan
            self.manager.commandline.set_string("")

    def undo(self) -> None:
        self.manager.selected_channels = list(self.old_selection)
        self.manager.last_selected_channel = self.old_last
        self.manager.notify_changed()


class SelectRemoveAction(SelectionAction):
    """Action to remove a channel from the selection."""

    name = "select.remove"

    def __init__(self, manager: SelectionManager) -> None:
        super().__init__(manager)
        self.channel: int = 0
        self.old_selection: list[int] = []
        self.old_last: typing.Optional[int] = None

    def configure(self, channel: int = 0) -> None:
        """Configure the action with a channel index to remove.

        If channel is 0, it reads from the commandline.
        """
        self.channel = channel

    def execute(self) -> None:
        self.old_selection = list(self.manager.selected_channels)
        self.old_last = self.manager.last_selected_channel

        chan = self.channel
        if not chan:
            cmd_string = self.manager.commandline.get_string()
            if is_non_nul_int(cmd_string):
                chan = int(cmd_string)
            else:
                return
        self.channel = chan

        if 1 <= chan <= MAX_CHANNELS:
            new_sel = list(self.old_selection)
            if chan in new_sel:
                new_sel.remove(chan)
            self.manager.selected_channels = new_sel
            self.manager.last_selected_channel = chan
            self.manager.commandline.set_string("")

    def undo(self) -> None:
        self.manager.selected_channels = list(self.old_selection)
        self.manager.last_selected_channel = self.old_last
        self.manager.notify_changed()


class SelectThruAction(SelectionAction):
    """Action to select a range of channels (Thru)."""

    name = "select.thru"

    def __init__(self, manager: SelectionManager) -> None:
        super().__init__(manager)
        self.to_channel: int = 0
        self.old_selection: list[int] = []
        self.old_last: typing.Optional[int] = None

    def configure(self, to_channel: int = 0) -> None:
        """Configure the action with the target channel index of the range.

        If to_channel is 0, it reads from the commandline.
        """
        self.to_channel = to_channel

    def execute(self) -> None:
        self.old_selection = list(self.manager.selected_channels)
        self.old_last = self.manager.last_selected_channel

        to_chan = self.to_channel
        if not to_chan:
            cmd_string = self.manager.commandline.get_string()
            if is_non_nul_int(cmd_string):
                to_chan = int(cmd_string)
            else:
                return
        self.to_channel = to_chan

        if self.old_last is not None and 1 <= to_chan <= MAX_CHANNELS:
            from_chan = self.old_last
            low = min(from_chan, to_chan)
            high = max(from_chan, to_chan)

            new_sel = list(self.old_selection)
            for ch in range(low, high + 1):
                if ch not in new_sel:
                    new_sel.append(ch)
            self.manager.selected_channels = new_sel
            self.manager.last_selected_channel = to_chan
            self.manager.commandline.set_string("")

    def undo(self) -> None:
        self.manager.selected_channels = list(self.old_selection)
        self.manager.last_selected_channel = self.old_last
        self.manager.notify_changed()


class SelectAllAction(SelectionAction):
    """Action to select all channels that have an intensity level > 0."""

    name = "select.all"

    def __init__(self, manager: SelectionManager) -> None:
        super().__init__(manager)
        self.old_selection: list[int] = []
        self.old_last: typing.Optional[int] = None

    def execute(self) -> None:
        self.old_selection = list(self.manager.selected_channels)
        self.old_last = self.manager.last_selected_channel

        new_sel = []
        if self.manager.get_level_callback is not None:
            for ch in range(1, MAX_CHANNELS + 1):
                if self.manager.get_level_callback(ch) > 0:
                    new_sel.append(ch)
        self.manager.selected_channels = new_sel

    def undo(self) -> None:
        self.manager.selected_channels = list(self.old_selection)
        self.manager.last_selected_channel = self.old_last
        self.manager.notify_changed()


class SelectNoneAction(SelectionAction):
    """Action to clear channel selection (select none)."""

    name = "select.none"

    def __init__(self, manager: SelectionManager) -> None:
        """Initialize the SelectNoneAction.

        Args:
            manager: The target SelectionManager instance.
        """
        super().__init__(manager)
        self.old_selection: list[int] = []
        self.old_last: typing.Optional[int] = None

    def execute(self) -> None:
        self.old_selection = list(self.manager.selected_channels)
        self.old_last = self.manager.last_selected_channel
        self.manager.selected_channels = []
        self.manager.last_selected_channel = None
        self.manager.commandline.set_string("")

    def undo(self) -> None:
        self.manager.selected_channels = list(self.old_selection)
        self.manager.last_selected_channel = self.old_last
        self.manager.notify_changed()
