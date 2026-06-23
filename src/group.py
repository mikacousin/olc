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
from dataclasses import dataclass

from olc.editor import TempChannelsEditor

if typing.TYPE_CHECKING:
    from olc.core.lightshow import LightShow


@dataclass
class Group:
    """A Group is composed of channels at some DMX levels."""

    index: float
    channels: dict[int, int]
    text: str = ""

    def set_text(self, text: str) -> None:
        """Set the group's text description."""
        self.text = text

    def set_channel(self, channel: int, level: int) -> None:
        """Set the DMX level of a channel in the group."""
        self.channels[channel] = level

    def remove_channel(self, channel: int) -> None:
        """Remove a channel from the group."""
        if channel in self.channels:
            del self.channels[channel]

    def get_channel_level(self, channel: int, default: int = 0) -> int:
        """Get the DMX level of a channel, returning default if not present."""
        return self.channels.get(channel, default)

    def get_channels(self) -> dict[int, int]:
        """Return the dictionary of channels and their levels."""
        return self.channels

    def set_channels(self, channels: dict[int, int]) -> None:
        """Set/overwrite the dictionary of channels."""
        self.channels = channels

    def clear(self) -> None:
        """Clear all channels from the group."""
        self.channels.clear()


class Groups:
    """Groups container class.

    Wraps a list of Group objects and acts as a proxy list while providing
    high-level methods for lookup, insertion, and index management.
    """

    def __init__(self, lightshow: LightShow) -> None:
        """Initialize the Groups container.

        Args:
            lightshow: Parent LightShow instance.
        """
        self.lightshow = lightshow
        self._groups: list[Group] = []
        self.group_editor = GroupEditor(lightshow)

    def __len__(self) -> int:
        """Return the number of groups."""
        return len(self._groups)

    def __getitem__(self, index: int) -> Group:
        """Get Group at list position index."""
        return self._groups[index]

    def __delitem__(self, index: int | slice) -> None:
        """Delete Group(s) at list position or slice."""
        del self._groups[index]

    def __iter__(self) -> typing.Iterator[Group]:
        """Iterate over all groups."""
        return iter(self._groups)

    def get(self, index: float) -> Group | None:
        """Retrieve a Group by its unique group number.

        Args:
            index: Group number.

        Returns:
            The matching Group or None.
        """
        for group in self._groups:
            if group.index == index:
                return group
        return None

    def add(self, group: Group) -> None:
        """Add a Group in sorted index order.

        Args:
            group: Group object to add.

        Raises:
            ValueError: If a group with the same index already exists.
        """
        if self.get(group.index) is not None:
            raise ValueError(f"Group with index {group.index} already exists.")

        # Find the insertion index to maintain sorted order
        insert_idx = len(self._groups)
        for i, g in enumerate(self._groups):
            if g.index > group.index:
                insert_idx = i
                break
        self._groups.insert(insert_idx, group)

    def append(self, group: Group) -> None:
        """Append a Group (adds in sorted order).

        Args:
            group: Group object to append.
        """
        self.add(group)

    def remove(self, group: Group) -> None:
        """Remove a Group.

        Args:
            group: Group object to remove.
        """
        if group in self._groups:
            self._groups.remove(group)

    def insert(self, _idx: int, group: Group) -> None:
        """Insert a Group at a specific list index (adds in sorted order instead).

        Args:
            _idx: List index.
            group: Group object.
        """
        # Force sorted order rather than arbitrary position insertion
        self.add(group)

    def pop(self, idx: int) -> Group:
        """Pop a Group at list position idx.

        Args:
            idx: List index to pop.

        Returns:
            The popped Group object.
        """
        return self._groups.pop(idx)

    def clear(self) -> None:
        """Clear all groups."""
        self._groups.clear()

    def get_next_index(self) -> float:
        """Calculate the next available group index.

        Returns:
            The next index (1.0 if empty, else last index + 1.0).
        """
        return 1.0 if not self._groups else self._groups[-1].index + 1.0


class GroupEditor(TempChannelsEditor[float]):
    """Manages the temporary channel levels during group editing, agnostic to the UI."""

    def _notify_changed(self, key: float) -> None:
        """Notify that the group editor state has changed.

        Args:
            key: Identification key of the edited group (index).
        """
        index = key
        if self.lightshow and self.lightshow.app:
            app = self.lightshow.app
            if hasattr(app, "core"):
                app = app.core
            app.emit("group_editor.changed", index)
