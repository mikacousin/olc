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

    def execute(self, group_nb: float | None = None) -> None:  # ty: ignore[invalid-method-override]
        """Execute the action, creating a new group.

        Args:
            group_nb: Optional group number.
                      If None, the next available integer is used.
        """
        lightshow = self.app.lightshow

        if group_nb is None:
            group_nb = 1.0 if not lightshow.groups else lightshow.groups[-1].index + 1.0

        self.group_nb = group_nb

        # Prevent duplicate indices
        for group in lightshow.groups:
            if group.index == group_nb:
                raise ValueError(f"Group {group_nb} already exists.")

        # Create new group with empty channel list
        channels: dict[int, int] = {}
        self.created_group = Group(group_nb, channels, str(group_nb))

        # Insert group in ordered fashion by its index
        insert_idx = len(lightshow.groups)
        for i, g in enumerate(lightshow.groups):
            if group_nb < g.index:
                insert_idx = i
                break
        lightshow.groups.insert(insert_idx, self.created_group)
        lightshow.set_modified()

        # Notify subscribers
        self.app.emit("group.created", self.created_group)

    def undo(self) -> None:
        """Undo the group creation, removing the group from the show."""
        if self.created_group and self.created_group in self.app.lightshow.groups:
            self.app.lightshow.groups.remove(self.created_group)
            self.app.lightshow.set_modified()
            self.app.emit("group.deleted", self.created_group)

    def redo(self) -> None:
        """Redo the group creation, re-inserting the group."""
        if self.created_group and self.group_nb is not None:
            lightshow = self.app.lightshow
            insert_idx = len(lightshow.groups)
            for i, g in enumerate(lightshow.groups):
                if self.group_nb < g.index:
                    insert_idx = i
                    break
            lightshow.groups.insert(insert_idx, self.created_group)
            lightshow.set_modified()
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

    def execute(self, group_nb: float) -> None:  # ty: ignore[invalid-method-override]
        """Execute the action, deleting the specified group.

        Args:
            group_nb: The index number of the group to delete.
        """
        lightshow = self.app.lightshow
        self.group_nb = group_nb

        # Find target group
        target_group = None
        target_index = -1
        for i, group in enumerate(lightshow.groups):
            if group.index == group_nb:
                target_group = group
                target_index = i
                break

        if not target_group:
            raise ValueError(f"Group {group_nb} does not exist.")

        self.deleted_group = target_group
        self.deleted_index = target_index

        # Remove from model
        lightshow.groups.pop(target_index)
        lightshow.set_modified()

        # Notify subscribers
        self.app.emit("group.deleted", target_group)

    def undo(self) -> None:
        """Undo the deletion, restoring the group back to its original index."""
        if self.deleted_group and self.deleted_index is not None:
            self.app.lightshow.groups.insert(self.deleted_index, self.deleted_group)
            self.app.lightshow.set_modified()
            self.app.emit("group.created", self.deleted_group)

    def redo(self) -> None:
        """Redo the deletion, removing the group again."""
        if self.deleted_group and self.deleted_group in self.app.lightshow.groups:
            self.app.lightshow.groups.remove(self.deleted_group)
            self.app.lightshow.set_modified()
            self.app.emit("group.deleted", self.deleted_group)
