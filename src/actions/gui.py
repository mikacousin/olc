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

if typing.TYPE_CHECKING:
    from olc.core.app import CoreApplication


class ZoomAction(Action):
    """Action to change GUI zoom level with undo/redo support."""

    name = "gui.zoom"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.target_zoom: float = 1.0
        self.old_zoom_level: float = 1.0

    def configure(self, target_zoom: float) -> None:
        """Configure the target zoom level.

        Args:
            target_zoom: The target zoom level value.
        """
        self.target_zoom = target_zoom

    def execute(self) -> None:
        self.old_zoom_level = getattr(self.app, "zoom_level", 1.0)
        self.app.zoom_level = self.target_zoom
        self.app.emit("gui.zoom_changed", self.target_zoom)

    def undo(self) -> None:
        self.app.zoom_level = self.old_zoom_level
        self.app.emit("gui.zoom_changed", self.old_zoom_level)

    def redo(self) -> None:
        self.app.zoom_level = self.target_zoom
        self.app.emit("gui.zoom_changed", self.target_zoom)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        return {
            "level": self.target_zoom,
        }


class TabOpenAction(Action):
    """Action to open or activate a GUI tab with undo/redo support."""

    name = "gui.tab_open"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.tab_name: str = ""
        self.notebook_id: str = "playback"
        self.old_active_tab: str = ""
        self.was_closed: bool = False

    def configure(self, tab_name: str, notebook_id: str = "playback") -> None:
        """Configure the action with the tab name and target notebook.

        Args:
            tab_name: The name of the tab to open/activate.
            notebook_id: The ID of the target notebook container.
        """
        self.tab_name = tab_name
        self.notebook_id = notebook_id

    def execute(self) -> None:
        """Execute the action, opening the tab if closed or activating it."""
        nb_id = self.app.tabs.get_notebook_of_tab(self.tab_name)
        if nb_id is not None:
            self.notebook_id = nb_id
            self.was_closed = False
        else:
            self.was_closed = True

        if self.was_closed:
            self.app.tabs.notebooks[self.notebook_id].append(self.tab_name)
        self.old_active_tab = self.app.tabs.active_tabs[self.notebook_id]
        self.app.tabs.active_tabs[self.notebook_id] = self.tab_name

        if self.was_closed:
            self.app.emit("gui.tab_opened", self.tab_name, self.notebook_id)
        self.app.emit("gui.active_tab_changed", self.tab_name, self.notebook_id)

    def undo(self) -> None:
        """Undo the action, closing the tab if it was opened by this action."""
        if self.was_closed:
            if self.tab_name in self.app.tabs.notebooks[self.notebook_id]:
                self.app.tabs.notebooks[self.notebook_id].remove(self.tab_name)
        self.app.tabs.active_tabs[self.notebook_id] = self.old_active_tab

        if self.was_closed:
            self.app.emit("gui.tab_closed", self.tab_name, self.notebook_id)
        self.app.emit("gui.active_tab_changed", self.old_active_tab, self.notebook_id)

    def redo(self) -> None:
        """Redo the action, re-executing the open/activation."""
        if self.was_closed:
            self.app.tabs.notebooks[self.notebook_id].append(self.tab_name)
        self.app.tabs.active_tabs[self.notebook_id] = self.tab_name

        if self.was_closed:
            self.app.emit("gui.tab_opened", self.tab_name, self.notebook_id)
        self.app.emit("gui.active_tab_changed", self.tab_name, self.notebook_id)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return the feedback state metadata."""
        return {
            "tab_name": self.tab_name,
            "notebook_id": self.notebook_id,
        }


class TabCloseAction(Action):
    """Action to close a GUI tab with undo/redo support."""

    name = "gui.tab_close"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.tab_name: str = ""
        self.notebook_id: str = ""
        self.old_index: int = -1
        self.old_active_tab: str = ""
        self.new_active_tab: str = ""

    def configure(self, tab_name: str) -> None:
        """Configure the action with the tab name to close.

        Args:
            tab_name: The name of the tab to close.
        """
        if tab_name in ("playback", "channels"):
            raise ValueError("Default tabs cannot be closed.")
        self.tab_name = tab_name

    def execute(self) -> None:
        """Execute the action, removing the tab and selecting a new active tab."""
        nb_id = self.app.tabs.get_notebook_of_tab(self.tab_name)
        if nb_id is None:
            raise ValueError(f"Tab {self.tab_name} is not open.")

        self.notebook_id = nb_id
        tab_list = self.app.tabs.notebooks[self.notebook_id]
        self.old_index = tab_list.index(self.tab_name)
        self.old_active_tab = self.app.tabs.active_tabs[self.notebook_id]

        if self.old_active_tab == self.tab_name:
            if len(tab_list) > 1:
                # Find the next tab to focus before removal
                temp_list = list(tab_list)
                temp_list.remove(self.tab_name)
                new_idx = min(self.old_index, len(temp_list) - 1)
                self.new_active_tab = temp_list[new_idx]
            else:
                self.new_active_tab = (
                    "channels" if self.notebook_id == "live" else "playback"
                )
        else:
            self.new_active_tab = self.old_active_tab

        # Update state FIRST
        tab_list.remove(self.tab_name)
        self.app.tabs.active_tabs[self.notebook_id] = self.new_active_tab

        # Emit events SECOND
        self.app.emit("gui.tab_closed", self.tab_name, self.notebook_id)
        if self.old_active_tab == self.tab_name:
            self.app.emit(
                "gui.active_tab_changed", self.new_active_tab, self.notebook_id
            )

    def undo(self) -> None:
        """Undo the action, restoring the closed tab at its index."""
        # Update state FIRST
        self.app.tabs.notebooks[self.notebook_id].insert(self.old_index, self.tab_name)
        self.app.tabs.active_tabs[self.notebook_id] = self.old_active_tab

        # Emit events SECOND
        self.app.emit(
            "gui.tab_opened_at", self.tab_name, self.notebook_id, self.old_index
        )
        self.app.emit("gui.active_tab_changed", self.old_active_tab, self.notebook_id)

    def redo(self) -> None:
        """Redo the action, re-executing the close."""
        tab_list = self.app.tabs.notebooks[self.notebook_id]

        # Update state FIRST
        if self.tab_name in tab_list:
            tab_list.remove(self.tab_name)
        self.app.tabs.active_tabs[self.notebook_id] = self.new_active_tab

        # Emit events SECOND
        self.app.emit("gui.tab_closed", self.tab_name, self.notebook_id)
        self.app.emit("gui.active_tab_changed", self.new_active_tab, self.notebook_id)

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return the feedback state metadata."""
        return {
            "tab_name": self.tab_name,
            "notebook_id": self.notebook_id,
        }


class TabMoveAction(Action):
    """Action to reorder or move a tab between notebooks with undo/redo."""

    name = "gui.tab_move"
    can_undo = True

    def __init__(self, app: CoreApplication) -> None:
        super().__init__(app)
        self.tab_name: str = ""
        self.from_nb: str = ""
        self.to_nb: str = ""
        self.new_index: int = -1
        self.old_index: int = -1
        self.old_from_active_tab: str = ""
        self.old_to_active_tab: str = ""

    def configure(
        self, tab_name: str, from_nb: str, to_nb: str, new_index: int
    ) -> None:
        """Configure the action with source, target, and position.

        Args:
            tab_name: The name of the tab to move.
            from_nb: The source notebook ID.
            to_nb: The target notebook ID.
            new_index: The target index in the target notebook.
        """
        self.tab_name = tab_name
        self.from_nb = from_nb
        self.to_nb = to_nb
        self.new_index = new_index

    def execute(self) -> None:
        """Execute the action, moving the tab from source to target notebook."""
        from_list = self.app.tabs.notebooks[self.from_nb]
        to_list = self.app.tabs.notebooks[self.to_nb]

        if self.tab_name not in from_list:
            raise ValueError(f"Tab {self.tab_name} is not in notebook {self.from_nb}.")

        self.old_index = from_list.index(self.tab_name)
        self.old_from_active_tab = self.app.tabs.active_tabs.get(self.from_nb, "")
        self.old_to_active_tab = self.app.tabs.active_tabs.get(self.to_nb, "")

        # 1. Update list structures
        from_list.remove(self.tab_name)
        target_idx = max(0, min(self.new_index, len(to_list)))
        to_list.insert(target_idx, self.tab_name)

        # 2. Determine new active tabs
        if self.from_nb == self.to_nb:
            new_from_active = self.tab_name
            new_to_active = self.tab_name
        else:
            if self.old_from_active_tab == self.tab_name:
                if from_list:
                    idx = min(self.old_index, len(from_list) - 1)
                    new_from_active = from_list[idx]
                else:
                    new_from_active = ""
            else:
                new_from_active = self.old_from_active_tab

            new_to_active = self.tab_name

        # 3. Apply active tab state
        self.app.tabs.active_tabs[self.from_nb] = new_from_active
        self.app.tabs.active_tabs[self.to_nb] = new_to_active

        # 4. Emit events
        self.app.emit(
            "gui.tab_moved", self.tab_name, self.from_nb, self.to_nb, target_idx
        )
        if self.from_nb == self.to_nb:
            if new_from_active != self.old_from_active_tab:
                self.app.emit("gui.active_tab_changed", new_from_active, self.from_nb)
        else:
            if new_from_active != self.old_from_active_tab:
                self.app.emit("gui.active_tab_changed", new_from_active, self.from_nb)
            if new_to_active != self.old_to_active_tab:
                self.app.emit("gui.active_tab_changed", new_to_active, self.to_nb)

    def undo(self) -> None:
        """Undo the action, returning the tab to its source notebook and index."""
        to_list = self.app.tabs.notebooks[self.to_nb]
        from_list = self.app.tabs.notebooks[self.from_nb]

        if self.tab_name in to_list:
            to_list.remove(self.tab_name)

        from_list.insert(self.old_index, self.tab_name)

        current_from_active = self.app.tabs.active_tabs.get(self.from_nb, "")
        current_to_active = self.app.tabs.active_tabs.get(self.to_nb, "")

        # Apply old active tab state
        self.app.tabs.active_tabs[self.from_nb] = self.old_from_active_tab
        self.app.tabs.active_tabs[self.to_nb] = self.old_to_active_tab

        self.app.emit(
            "gui.tab_moved", self.tab_name, self.to_nb, self.from_nb, self.old_index
        )
        if self.from_nb == self.to_nb:
            if self.old_from_active_tab != current_from_active:
                self.app.emit(
                    "gui.active_tab_changed", self.old_from_active_tab, self.from_nb
                )
        else:
            if self.old_from_active_tab != current_from_active:
                self.app.emit(
                    "gui.active_tab_changed", self.old_from_active_tab, self.from_nb
                )
            if self.old_to_active_tab != current_to_active:
                self.app.emit(
                    "gui.active_tab_changed", self.old_to_active_tab, self.to_nb
                )

    def redo(self) -> None:
        """Redo the action, re-executing the move."""
        self.execute()

    def get_feedback_state(self) -> dict[str, typing.Any]:
        """Return the feedback state metadata."""
        return {
            "tab_name": self.tab_name,
            "from_nb": self.from_nb,
            "to_nb": self.to_nb,
            "new_index": self.new_index,
        }
