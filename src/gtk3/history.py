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
"""Undo History tab for Open Lighting Console."""

from __future__ import annotations

import typing
from gettext import gettext as _

from gi.repository import Gtk

if typing.TYPE_CHECKING:
    from olc.core.action import Action
    from olc.gtk3.application import Application, Tabs


class HistoryTab(Gtk.Box):
    """History tab displaying the undo and redo stacks."""

    app: Application
    tabs: Tabs | None
    btn_undo: Gtk.ToolButton
    btn_redo: Gtk.ToolButton
    btn_clear: Gtk.ToolButton
    liststore: Gtk.ListStore
    treeview: Gtk.TreeView

    def __init__(self, app: Application) -> None:
        self.app = app
        self.tabs = app.tabs
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        # Toolbar
        toolbar = Gtk.Toolbar()
        self.pack_start(toolbar, False, False, 0)

        # Undo Button
        self.btn_undo = Gtk.ToolButton(stock_id=Gtk.STOCK_UNDO)
        self.btn_undo.set_tooltip_text(_("Undo last action"))
        self.btn_undo.connect("clicked", self.on_undo_clicked)
        toolbar.insert(self.btn_undo, -1)

        # Redo Button
        self.btn_redo = Gtk.ToolButton(stock_id=Gtk.STOCK_REDO)
        self.btn_redo.set_tooltip_text(_("Redo last undone action"))
        self.btn_redo.connect("clicked", self.on_redo_clicked)
        toolbar.insert(self.btn_redo, -1)

        # Clear Button
        self.btn_clear = Gtk.ToolButton(stock_id=Gtk.STOCK_CLEAR)
        self.btn_clear.set_tooltip_text(_("Clear history"))
        self.btn_clear.connect("clicked", self.on_clear_clicked)
        toolbar.insert(self.btn_clear, -1)

        # Scrolled window
        scrollable = Gtk.ScrolledWindow()
        scrollable.set_vexpand(True)
        scrollable.set_hexpand(True)
        self.pack_start(scrollable, True, True, 0)

        # ListStore: columns are (status, action name, details, is_active)
        self.liststore = Gtk.ListStore(str, str, str, bool)

        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.set_enable_search(False)
        self.treeview.connect("row-activated", self.on_row_activated)
        scrollable.add(self.treeview)

        # Status column
        col_status = Gtk.TreeViewColumn(_("Status"))
        cell_status = Gtk.CellRendererText()
        col_status.pack_start(cell_status, False)
        col_status.add_attribute(cell_status, "text", 0)
        col_status.add_attribute(cell_status, "sensitive", 3)
        self.treeview.append_column(col_status)

        # Action column
        col_action = Gtk.TreeViewColumn(_("Action"))
        cell_action = Gtk.CellRendererText()
        col_action.pack_start(cell_action, True)
        col_action.add_attribute(cell_action, "text", 1)
        col_action.add_attribute(cell_action, "sensitive", 3)
        self.treeview.append_column(col_action)

        # Details column
        col_details = Gtk.TreeViewColumn(_("Details"))
        cell_details = Gtk.CellRendererText()
        col_details.pack_start(cell_details, True)
        col_details.add_attribute(cell_details, "text", 2)
        col_details.add_attribute(cell_details, "sensitive", 3)
        self.treeview.append_column(col_details)

        self.refresh()
        self.show_all()

    def refresh(self) -> None:
        """Refresh the history display from core stacks."""
        self.liststore.clear()

        history = self.app.core.history
        undo_stack = history.undo_stack
        redo_stack = history.redo_stack

        # Check stack sizes to enable/disable buttons
        self.btn_undo.set_sensitive(len(undo_stack) > 0)
        self.btn_redo.set_sensitive(len(redo_stack) > 0)
        self.btn_clear.set_sensitive(len(undo_stack) > 0 or len(redo_stack) > 0)

        # Populate undo stack (active actions)
        for action in undo_stack:
            details = self._format_action_details(action)
            self.liststore.append(["✔", action.name, details, True])

        # Populate redo stack (undone actions)
        for action in reversed(redo_stack):
            details = self._format_action_details(action)
            self.liststore.append(["", action.name, details, False])

    def _format_action_details(self, action: Action) -> str:
        """Format the feedback state metadata of an action."""
        try:
            fb = action.get_feedback_state()
            if fb:
                return ", ".join(f"{k}: {v}" for k, v in fb.items())
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return ""

    def on_undo_clicked(self, _widget: Gtk.ToolButton) -> None:
        """Trigger an undo execution."""
        self.app.core.action_registry.execute("edit.undo")

    def on_redo_clicked(self, _widget: Gtk.ToolButton) -> None:
        """Trigger a redo execution."""
        self.app.core.action_registry.execute("edit.redo")

    def on_clear_clicked(self, _widget: Gtk.ToolButton) -> None:
        """Clear both stacks."""
        self.app.core.history.clear()

    def on_row_activated(
        self,
        _treeview: Gtk.TreeView,
        path: Gtk.TreePath,
        _column: Gtk.TreeViewColumn,
    ) -> None:
        """Jump to the selected action in the history timeline."""
        history = self.app.core.history
        undo_len = len(history.undo_stack)

        indices = path.get_indices()
        if not indices:
            return
        idx = indices[0]

        if idx < undo_len - 1:
            steps = (undo_len - 1) - idx
            for _ in range(steps):
                self.app.core.action_registry.execute("edit.undo")
        elif idx >= undo_len:
            steps = idx - undo_len + 1
            for _ in range(steps):
                self.app.core.action_registry.execute("edit.redo")

    def on_close_icon(self, _widget: Gtk.Widget) -> None:
        """Close the history tab."""
        if self.tabs:
            self.tabs.close("history")
