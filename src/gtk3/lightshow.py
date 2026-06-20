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

from gi.repository import GLib, Gtk
from olc.core.lightshow import LightShow

if typing.TYPE_CHECKING:
    from gi.repository import Gio
    from olc.core.app import CoreApplication


class GtkLightShow(LightShow):
    """Subclass of LightShow adding Gtk/Gio file-handling support."""

    file: Gio.File | None
    recent_manager: Gtk.RecentManager

    def __init__(self, app: CoreApplication | None = None) -> None:
        super().__init__(app)
        self.file = None
        self.recent_manager = Gtk.RecentManager.get_default()

    def add_recent_file(self) -> None:
        if not self.file:
            return
        uri = self.file.get_uri()
        if uri:
            try:
                self.recent_manager.remove_item(uri)
            except GLib.Error as e:
                if e.domain != "gtk-recent-manager-error-quark":
                    raise e
            self.recent_manager.add_item(uri)

    def set_modified(self) -> None:
        if self.file:
            self.basename = self.file.get_basename() or ""
            self.file_path = self.file.get_path()
        super().set_modified()

    def set_not_modified(self) -> None:
        if self.file:
            self.basename = self.file.get_basename() or ""
            self.file_path = self.file.get_path()
        super().set_not_modified()
