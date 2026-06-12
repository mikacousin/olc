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
    from olc.channel_time import ChanneltimeTab
    from olc.cues_edition import CuesEditionTab
    from olc.curve_edition import CurvesTab
    from olc.fader_edition import FaderTab
    from olc.group import GroupTab
    from olc.independents_edition import IndependentsTab
    from olc.patch_channels import PatchChannelsTab
    from olc.patch_outputs import PatchOutputsTab
    from olc.sequence_edition import SequenceTab
    from olc.settings import SettingsTab
    from olc.track_channels import TrackChannelsTab
    from olc.window import Window

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
            tab = self.tabs[tab_name]
            assert tab is not None
            # Label with a close icon
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE, Gtk.IconSize.MENU))
            button.connect(
                "clicked",
                tab.on_close_icon,
            )
            newlabel = Gtk.Box()
            newlabel.pack_start(Gtk.Label(label=label), False, False, 0)
            newlabel.pack_start(button, False, False, 0)
            newlabel.show_all()
            self.window.playback.append_page(tab, newlabel)
            self.window.playback.set_tab_reorderable(tab, True)
            self.window.playback.set_tab_detachable(tab, True)
            self.window.show_all()
            self.window.playback.set_current_page(-1)
        else:
            tab = self.tabs[tab_name]
            assert tab is not None
            page = self.window.playback.page_num(tab)
            self.window.playback.set_current_page(page)
        self.window.playback.grab_focus()

    def close(self, tab_name: str) -> None:
        """Close tab

        Args:
            tab_name : Tab name found in self.tabs
        """
        if self.window and self.tabs[tab_name]:
            self.window.commandline.set_string("")
            tab = self.tabs[tab_name]
            assert tab is not None
            notebook = tab.get_parent()
            if notebook is not None:
                notebook_nb = typing.cast(Gtk.Notebook, notebook)
                page = notebook_nb.page_num(tab)
                notebook_nb.remove_page(page)
            self.tabs[tab_name] = None

    def refresh_all(self) -> None:
        """Refresh all open tabs"""
        for tab in self.tabs.values():
            if tab:
                tab.refresh()
