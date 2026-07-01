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

from gi.repository import Gtk

if typing.TYPE_CHECKING:
    from olc.core.commandline import CoreCommandLine
    from olc.gtk3.application import Application
    from olc.gtk3.channel_time import ChanneltimeTab
    from olc.gtk3.cue import CuesEditionTab
    from olc.gtk3.curve import CurvesTab
    from olc.gtk3.fader import FaderTab
    from olc.gtk3.group import GroupTab
    from olc.gtk3.independent import IndependentsTab
    from olc.gtk3.patch_channels import PatchChannelsTab
    from olc.gtk3.patch_outputs import PatchOutputsTab
    from olc.gtk3.sequence import SequenceTab
    from olc.gtk3.track_channels import TrackChannelsTab
    from olc.gtk3.window import Window
    from olc.settings import SettingsTab

    TabWidget = (
        ChanneltimeTab
        | CuesEditionTab
        | CurvesTab
        | FaderTab
        | GroupTab
        | IndependentsTab
        | PatchChannelsTab
        | PatchOutputsTab
        | SequenceTab
        | SettingsTab
        | TrackChannelsTab
    )


class Tabs:
    """Tabs manager

    Attributes:
        tabs: Tabs defined by a unique name and widgets
    """

    tabs: dict[str, TabWidget | None]
    app: Application
    window: Window | None
    commandline: CoreCommandLine

    def __init__(self, app: Application) -> None:
        self.app = app
        self.window = None
        self.commandline = app.core.commandline
        self.default_notebook_id = "playback"

        self.tabs = {
            "channel_time": None,
            "curves": None,
            "faders": None,
            "groups": None,
            "indes": None,
            "memories": None,
            "patch_outputs": None,
            "patch_channels": None,
            "sequences": None,
            "settings": None,
            "track_channels": None,
        }

    def open(
        self,
        tab_name: str,
        widget: typing.Any,  # noqa: ANN401
        label: str,
        *args: object,
        notebook_id: str = "playback",
    ) -> None:
        """Open tab

        Args:
            tab_name: Tab name found in self.tabs
            widget: Widget to open
            label: Tab label
            *args: additional parameters
            notebook_id: Notebook container ID
        """
        if self.window is None:
            return
        if tab_name in ("playback", "channels"):
            tab = (
                self.window.playback.grid
                if tab_name == "playback"
                else self.window.live_view.channels_view
            )
            parent = tab.get_parent()
            if isinstance(parent, Gtk.Notebook):
                page = parent.page_num(tab)
                parent.set_current_page(page)
                parent.grab_focus()
            return

        if tab_name not in self.tabs:
            return
        nb_id = self.default_notebook_id if notebook_id == "playback" else notebook_id
        notebook = self.window.live_view if nb_id == "live" else self.window.playback
        if self.tabs[tab_name] is None:
            self.tabs[tab_name] = widget(*args)
            tab_any = typing.cast(typing.Any, self.tabs[tab_name])
            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect(
                "clicked",
                tab_any.on_close_icon,
            )
            newlabel = Gtk.Box()
            newlabel.pack_start(Gtk.Label(label=label), False, False, 0)
            newlabel.pack_start(button, False, False, 0)
            newlabel.show_all()
            notebook.append_page(tab_any, newlabel)
            notebook.set_tab_reorderable(tab_any, True)
            notebook.set_tab_detachable(tab_any, True)
            self.window.show_all()
            notebook.set_current_page(-1)
        else:
            tab = self.tabs[tab_name]
            assert tab is not None
            parent = tab.get_parent()
            if isinstance(parent, Gtk.Notebook):
                notebook = parent
            page = notebook.page_num(tab)
            notebook.set_current_page(page)
        notebook.grab_focus()

    def close(self, tab_name: str) -> None:
        """Close tab by executing Core Action.

        Args:
            tab_name : Tab name found in self.tabs
        """
        if tab_name not in self.tabs:
            return
        if self.tabs[tab_name]:
            self.app.core.action_registry.execute("gui.tab_close", tab_name)

    def close_physically(self, tab_name: str) -> None:
        """Physically close and remove the tab widget.

        Args:
            tab_name: Tab name to remove.
        """
        if tab_name not in self.tabs:
            return
        if self.tabs[tab_name]:
            self.commandline.set_string("")
            tab = self.tabs[tab_name]
            assert tab is not None
            notebook = tab.get_parent()
            if notebook is not None:
                notebook_nb = typing.cast(Gtk.Notebook, notebook)
                page = notebook_nb.page_num(tab)
                notebook_nb.remove_page(page)
            self.tabs[tab_name] = None

    def move(self, tab_name: str, _from_nb: str, to_nb: str, new_index: int) -> None:
        """Physically move the tab widget between or within notebooks.

        Args:
            tab_name: Tab name.
            _from_nb: Source notebook ID.
            to_nb: Target notebook ID.
            new_index: Target index in notebooks list.
        """
        if self.window is None:
            return

        if tab_name == "playback":
            tab = self.window.playback.grid
        elif tab_name == "channels":
            tab = self.window.live_view.channels_view
        else:
            tab = self.tabs.get(tab_name)

        if not tab:
            return

        to_notebook = self.window.live_view if to_nb == "live" else self.window.playback

        target_physical_index = new_index

        parent = tab.get_parent()
        if parent is not to_notebook:
            parent_nb = (
                typing.cast(Gtk.Notebook, parent) if parent is not None else None
            )
            label = (
                parent_nb.get_tab_label(tab)
                if parent_nb is not None
                else Gtk.Label(label=tab_name)
            )
            if parent is not None:
                typing.cast(Gtk.Notebook, parent).detach_tab(tab)
            to_notebook.append_page(tab, label)
            to_notebook.set_tab_reorderable(tab, True)
            to_notebook.set_tab_detachable(tab, True)

        to_notebook.reorder_child(tab, target_physical_index)
        to_notebook.set_current_page(target_physical_index)
        to_notebook.grab_focus()

    def refresh_all(self) -> None:
        """Refresh all open tabs"""
        for tab in self.tabs.values():
            if tab:
                tab.refresh()
