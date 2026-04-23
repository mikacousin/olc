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
import typing

from gi.repository import Gtk

if typing.TYPE_CHECKING:
    from olc.window import Window


class Tabs:
    """Tabs manager

    Attributes:
        tabs: Tabs defined by a unique name and widgets
    """

    tabs: dict[str, Gtk.Paned | None]

    def __init__(self, window: Window | None) -> None:
        self.window = window

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
    ) -> None:
        """Open tab

        Args:
            tab_name: Tab name found in self.tabs
            widget: Widget to open
            label: Tab label
            *args: additional parameters
        """
        if self.window is None:
            return
        if self.tabs[tab_name] is None:
            self.tabs[tab_name] = widget(*args)
            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect(
                "clicked",
                self.tabs[tab_name].on_close_icon,
            )
            newlabel = Gtk.Box()
            newlabel.pack_start(Gtk.Label(label=label), False, False, 0)
            newlabel.pack_start(button, False, False, 0)
            newlabel.show_all()
            self.window.playback.append_page(self.tabs[tab_name], newlabel)
            self.window.playback.set_tab_reorderable(self.tabs[tab_name], True)
            self.window.playback.set_tab_detachable(self.tabs[tab_name], True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            page = self.window.playback.page_num(self.tabs[tab_name])
            self.window.playback.set_current_page(page)
        self.window.playback.grab_focus()

    def close(self, tab_name: str) -> None:
        """Close tab

        Args:
            tab_name : Tab name found in self.tabs
        """
        if self.window and self.tabs[tab_name]:
            self.window.commandline.set_string("")
            notebook = self.tabs[tab_name].get_parent()
            page = notebook.page_num(self.tabs[tab_name])
            notebook.remove_page(page)
            self.tabs[tab_name] = None

    def refresh_all(self) -> None:
        """Refresh all open tabs"""
        for tab in self.tabs.values():
            if tab:
                tab.refresh()
