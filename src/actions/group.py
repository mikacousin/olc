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

import copy
import typing

from olc.core.action import Action
from olc.group import Group

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class NewGroupAction(Action):
    """Action to create a new group in the lightshow.

    Fully supports Undo/Redo and emits group creation events.
    """

    name = "group.new"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.group_nb: typing.Optional[float] = None
        self.created_group: typing.Optional[Group] = None

    def configure(self, group_nb: float | None = None) -> None:
        """Configure the action with an optional group number.

        Args:
            group_nb: Optional group number.
                      If None, the next available integer is used.
        """
        self.group_nb = group_nb

    def execute(self) -> None:
        """Execute the action, creating a new group."""
        lightshow = self.app.lightshow

        group_nb = self.group_nb
        if group_nb is None:
            group_nb = lightshow.groups.get_next_index()
            self.group_nb = group_nb

        # Prevent duplicate indices
        if lightshow.groups.get(group_nb) is not None:
            raise ValueError(f"Group {group_nb} already exists.")

        # Create new group with empty channel list
        channels: dict[int, int] = {}
        self.created_group = Group(group_nb, channels, str(group_nb))

        # Add group to Groups container (sorted insert)
        lightshow.groups.add(self.created_group)
        lightshow.set_modified()

        # Notify subscribers
        self.app.emit("group.created", self.created_group)

    def undo(self) -> None:
        """Undo the group creation, removing the group from the show."""
        if self.created_group:
            self.app.lightshow.groups.remove(self.created_group)
            self.app.lightshow.set_modified()
            self.app.emit("group.deleted", self.created_group)

    def redo(self) -> None:
        """Redo the group creation, re-inserting the group."""
        if self.created_group:
            self.app.lightshow.groups.add(self.created_group)
            self.app.lightshow.set_modified()
            self.app.emit("group.created", self.created_group)


class DeleteGroupAction(Action):
    """Action to delete an existing group.

    Supports Undo/Redo by retaining the deleted group and index.
    """

    name = "group.delete"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.group_nb: typing.Optional[float] = None
        self.deleted_group: typing.Optional[Group] = None
        self.deleted_index: typing.Optional[int] = None

    def configure(self, group_nb: float) -> None:
        """Configure the action with the group number to delete.

        Args:
            group_nb: The index number of the group to delete.
        """
        self.group_nb = group_nb

    def execute(self) -> None:
        """Execute the action, deleting the specified group."""
        lightshow = self.app.lightshow
        group_nb = self.group_nb
        if group_nb is None:
            raise ValueError("Group number is required.")

        # Find target group
        target_group = lightshow.groups.get(group_nb)
        if not target_group:
            raise ValueError(f"Group {group_nb} does not exist.")

        self.deleted_group = target_group
        try:
            self.deleted_index = list(lightshow.groups).index(target_group)
        except ValueError:
            self.deleted_index = None

        # Remove from model
        lightshow.groups.remove(target_group)
        lightshow.set_modified()

        # Notify subscribers
        self.app.emit("group.deleted", target_group)

    def undo(self) -> None:
        """Undo the deletion, restoring the group back to its original index."""
        if self.deleted_group:
            if self.deleted_index is not None:
                self.app.lightshow.groups.insert(self.deleted_index, self.deleted_group)
            else:
                self.app.lightshow.groups.add(self.deleted_group)
            self.app.lightshow.set_modified()
            self.app.emit("group.created", self.deleted_group)

    def redo(self) -> None:
        """Redo the deletion, removing the group again."""
        if self.deleted_group:
            self.app.lightshow.groups.remove(self.deleted_group)
            self.app.lightshow.set_modified()
            self.app.emit("group.deleted", self.deleted_group)


class GroupUpdateChannelsAction(Action):
    """Action to update the channels of a group.

    Supports Undo/Redo by retaining a deep copy of the previous channels.
    """

    name = "group.update_channels"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.group_nb: float = 0.0
        self.new_channels: dict[int, int] = {}
        self.old_channels: dict[int, int] = {}

    def configure(self, group_nb: float, channels: dict[int, int]) -> None:
        """Configure the action.

        Args:
            group_nb: The index of the group.
            channels: New channels dict.
        """
        self.group_nb = group_nb
        self.new_channels = dict(channels)

    def execute(self) -> None:
        """Execute the action, replacing group channels."""
        lightshow = self.app.lightshow
        target_group = lightshow.groups.get(self.group_nb)
        if not target_group:
            raise ValueError(f"Group {self.group_nb} does not exist.")

        self.old_channels = copy.deepcopy(target_group.channels)
        target_group.channels = self.new_channels
        lightshow.set_modified()
        lightshow.groups.group_editor.clear(self.group_nb)
        self.app.emit("group.updated", target_group)

    def undo(self) -> None:
        """Undo the action, restoring the previous channels."""
        lightshow = self.app.lightshow
        target_group = lightshow.groups.get(self.group_nb)
        if not target_group:
            return
        target_group.channels = self.old_channels
        lightshow.set_modified()
        self.app.emit("group.updated", target_group)


class GroupRenameAction(Action):
    """Action to rename a group (change its text description).

    Supports Undo/Redo.
    """

    name = "group.rename"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.group_nb: float = 0.0
        self.new_name: str = ""
        self.old_name: str = ""

    def configure(self, group_nb: float, name: str) -> None:
        """Configure the action.

        Args:
            group_nb: The index of the group.
            name: The new name (text).
        """
        self.group_nb = group_nb
        self.new_name = name

    def execute(self) -> None:
        """Execute the action, renaming the group."""
        lightshow = self.app.lightshow
        target_group = lightshow.groups.get(self.group_nb)
        if not target_group:
            raise ValueError(f"Group {self.group_nb} does not exist.")

        self.old_name = target_group.text
        target_group.text = self.new_name
        lightshow.set_modified()
        self.app.emit("group.updated", target_group)

    def undo(self) -> None:
        """Undo the rename, restoring the previous name."""
        lightshow = self.app.lightshow
        target_group = lightshow.groups.get(self.group_nb)
        if not target_group:
            return
        target_group.text = self.old_name
        lightshow.set_modified()
        self.app.emit("group.updated", target_group)


class GroupSelectAction(Action):
    """Action to select a group logically.

    Supports Undo/Redo by storing the previous selected group.
    """

    name = "group.select"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.group_nb: typing.Optional[float] = None
        self.old_group_nb: typing.Optional[float] = None

    def configure(self, group_nb: float | None) -> None:
        """Configure the action with the group number to select.

        Args:
            group_nb: The index of the group to select, or None to unselect.
        """
        self.group_nb = group_nb

    def execute(self) -> None:
        self.old_group_nb = self.app.selected_group
        self.app.selected_group = self.group_nb
        self.app.emit("group.selected_changed", self.group_nb)

    def undo(self) -> None:
        self.app.selected_group = self.old_group_nb
        self.app.emit("group.selected_changed", self.old_group_nb)

    def redo(self) -> None:
        self.app.selected_group = self.group_nb
        self.app.emit("group.selected_changed", self.group_nb)


class GroupSetTempChannelsAction(Action):
    """Action to set temp channel levels in a group, supporting Undo/Redo."""

    name = "group.set_temp_channels"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        """Initialize the Action.

        Args:
            app: The core application instance.
        """
        super().__init__(app)
        self.group_nb: float = 0.0
        self.new_levels: dict[int, int] = {}
        self.old_levels: dict[int, int] = {}

    def configure(self, group_nb: float, channels: dict[int, int]) -> None:
        """Configure the action.

        Args:
            group_nb: The index of the group.
            channels: Dict mapping channel number (1-based) to level (0-255).
        """
        self.group_nb = group_nb
        self.new_levels = dict(channels)

    def execute(self) -> None:
        """Execute the action, storing temp levels."""
        group_editor = self.app.lightshow.groups.group_editor
        levels = group_editor.get_levels(self.group_nb)
        self.old_levels = {}
        for channel in self.new_levels:
            self.old_levels[channel] = int(levels[channel - 1])

        for channel, level in self.new_levels.items():
            group_editor.set_level(self.group_nb, channel, level)

    def undo(self) -> None:
        """Undo the temporary level changes."""
        group_editor = self.app.lightshow.groups.group_editor
        for channel, level in self.old_levels.items():
            group_editor.set_level(self.group_nb, channel, level)

    def redo(self) -> None:
        """Redo the temporary level changes."""
        group_editor = self.app.lightshow.groups.group_editor
        for channel, level in self.new_levels.items():
            group_editor.set_level(self.group_nb, channel, level)
