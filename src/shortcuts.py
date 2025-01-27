# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2024 Mika Cousin <mika.cousin@gmail.com>
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

from gi.repository import Gio, GLib

if typing.TYPE_CHECKING:
    from gi.repository import Gdk
    from olc.widgets.channels_view import ChannelsView


class Shortcuts:
    """Application shortcuts"""

    def __init__(self, app):
        self.app = app
        # General shortcuts
        self.general = {
            # Application main menu
            "quit": (["<Control>q"], ("app.exit", None)),
            "new": ([""], ("app._new", None)),
            "open": (["<Control>o"], ("app._open", None)),
            "import_file": (["<Shift><Control>o"], ("app._import_file", None)),
            "save": (["<Control>s"], ("app._save", None)),
            "save_as": (["<Shift><Control>s"], ("app._saveas", None)),
            "patch_outputs": (["<Control>p"], ("app.patch_outputs", None)),
            "patch_channels": (["<Shift><Control>p"], ("app._patch_channels", None)),
            "curves": ([""], ("app._curves", None)),
            "memories": ([""], ("app.memories_cb", None)),
            "groups": (["<Shift><Control>g"], ("app.groups_cb", None)),
            "sequences": (["<Control>t"], ("app.sequences", None)),
            "faders": (["<Control>f"], ("app._faders", None)),
            "track_channels": (["<Shift><Control>t"], ("app.track_channels", None)),
            "independents": (["<Control>i"], ("app._independents", None)),
            "virtual_console": (["<Shift><Control>c"], ("app._virtual_console", None)),
            "settings": ([""], ("app._settings", None)),
            "show-help-overlay": ([""], ("app._shortcuts", None)),
            "about": (["F3"], ("app._about", None)),
            "fullscreen": (["F11"], ("app.window.fullscreen_toggle", None)),
            # Sequential
            "go": (["<Control>g"], ("app.lightshow.main_playback.do_go", None)),
            "go_back": (["<Control>b"], ("app.lightshow.main_playback.go_back", None)),
            "pause": (["<Control>z"], ("app.lightshow.main_playback.pause", None))
        }

        # Command-line shortcuts
        self.cmd_line = {
            "empty": (["<Shift>BackSpace"], ("_cmd_empty", None)),
            "previous": (["Up"], ("_cmd_prev", None)),
            "next": (["Down"], ("_cmd_next", None)),
            "channel": (["c"], ("_channel", None)),
            "one": (["1", "KP_1"], ("_number", "i", 1)),
            "two": (["2", "KP_2"], ("_number", "i", 2)),
            "three": (["3", "KP_3"], ("_number", "i", 3)),
            "four": (["4", "KP_4"], ("_number", "i", 4)),
            "five": (["5", "KP_5"], ("_number", "i", 5)),
            "six": (["6", "KP_6"], ("_number", "i", 6)),
            "seven": (["7", "KP_7"], ("_number", "i", 7)),
            "eight": (["8", "KP_8"], ("_number", "i", 8)),
            "nine": (["9", "KP_9"], ("_number", "i", 9)),
            "zero": (["0", "KP_0"], ("_number", "i", 0))
        }

        for key, value in self.general.items():
            self._create_action(key, value[1])
            if value[0][0]:
                self.app.set_accels_for_action(f"app.{key}", value[0])
        for key, value in self.cmd_line.items():
            self._create_action(key, value[1])
            if value[1][1]:
                self.app.set_accels_for_action(f"app.{key}({value[1][2]})", value[0])
            else:
                self.app.set_accels_for_action(f"app.{key}", value[0])

    def _create_action(self, name, func) -> None:
        # Get method
        attributs = func[0].split(".")
        function: Shortcuts | None = self
        for attr in attributs:
            function = getattr(function, attr, None)

        if func[1]:
            action = Gio.SimpleAction.new(name, GLib.VariantType(func[1]))
        else:
            action = Gio.SimpleAction.new(name, None)

        action.connect("activate", function)
        self.app.add_action(action)

    def activate(self) -> None:
        """Activate shortcuts if no editable widget is focused"""
        for key, value in self.cmd_line.items():
            if value[1][1]:
                self.app.set_accels_for_action(f"app.{key}({value[1][2]})", value[0])
            else:
                self.app.set_accels_for_action(f"app.{key}", value[0])

    def desactivate(self) -> None:
        """deactivate shortcuts if editable widget is focused"""
        for key, value in self.cmd_line.items():
            if value[1][1]:
                self.app.set_accels_for_action(f"app.{key}({value[1][2]})", [])
            else:
                self.app.set_accels_for_action(f"app.{key}", [])

    def toggle(self, _widget, event: Gdk.EventFocus) -> None:
        """Toggle Command-line shortcuts

        Args:
            event: Focus event
        """
        if event.in_:
            self.desactivate()
        else:
            self.activate()

    def _get_active_view(self) -> ChannelsView:
        tab = self.app.window.get_active_tab()
        if tab is self.app.window.live_view.channels_view:
            return tab
        print(tab)
        if tab is self.app.tabs.tabs["patch_outputs"]:
            print("patch")
        return tab.channels_view

    def _cmd_prev(self, _action, _param) -> None:
        self.app.window.commandline.prev()

    def _cmd_next(self, _action, _param) -> None:
        self.app.window.commandline.next()

    def _cmd_empty(self, _action, _param) -> None:
        self.app.window.commandline.set_string("")
        view = self._get_active_view()
        view.select_channel(0)

    def _number(self, _action, parameter: int) -> None:
        view = self._get_active_view()
        self.app.window.commandline.add_string(str(parameter), context=view)

    def _channel(self, _action, _parameter) -> None:
        view = self._get_active_view()
        self.app.window.commandline.add_string(" chan ", context=view)
        view.grab_focus()
