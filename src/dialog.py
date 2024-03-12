# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2024 Mika Cousin <mika.cousin@gmail.com>
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
from gi.repository import Gtk
from olc.define import App


class ConfirmationDialog(Gtk.Dialog):
    """Confirmation dialog"""

    def __init__(self, text: str):
        super().__init__(title="Confirmation", transient_for=App().window, flags=0)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK,
                         Gtk.ResponseType.OK)

        self.set_default_size(150, 100)

        label = Gtk.Label(label=text)

        box = self.get_content_area()
        box.add(label)
        self.show_all()
