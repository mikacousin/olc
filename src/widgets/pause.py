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

import cairo
from gi.repository import Gtk
from olc.widgets.common import rounded_rectangle, rounded_rectangle_fill

if typing.TYPE_CHECKING:
    from gi.repository import Gdk
    from olc.lightshow import LightShow
    from olc.midi import Midi


# pylint: disable=too-many-instance-attributes
class PauseWidget(Gtk.Button):
    """Pause button widget"""

    __gtype_name__ = "PauseWidget"

    def __init__(
        self,
        label: str = "",
        text: str = "None",
        midi: Midi | None = None,
        lightshow: LightShow | None = None,
    ) -> None:
        super().__init__()
        self.midi = midi
        self.lightshow = lightshow

        self.width = 50
        self.height = 50
        self.radius = 10
        self.font_size = 10

        self.btn_pressed = False
        self.label = label
        self.text = text

        self.set_size_request(self.width, self.height)

        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)

    def on_press(self, _tgt: Gtk.Widget, _ev: Gdk.EventButton) -> None:
        """Button pressed"""
        self.btn_pressed = True
        if self.midi:
            self.midi.messages.notes.send(self.text, 127)

    def on_release(self, _tgt: Gtk.Widget, _ev: Gdk.EventButton) -> None:
        """Button released"""
        # channel, note = App().midi.messages.notes.notes[self.text]
        if self.lightshow and self.lightshow.main_playback.on_go:
            if (
                self.lightshow.main_playback.thread
                and self.lightshow.main_playback.thread.pause.is_set()
            ):
                self.btn_pressed = True
                if self.midi:
                    self.midi.messages.notes.send(self.text, 127)
            elif self.lightshow.main_playback.thread:
                self.btn_pressed = False
                if self.midi:
                    self.midi.messages.notes.send(self.text, 0)
        else:
            self.btn_pressed = False
            if self.midi:
                self.midi.messages.notes.send(self.text, 0)

    def do_draw(self, cr: cairo.Context) -> bool:
        """Draw Pause button, lightshow: LightShow | None = None

        Args:
            cr: Cairo context
        """
        if self.text == "None":
            cr.set_source_rgb(0.4, 0.4, 0.4)
        elif self.btn_pressed:
            if self.midi and self.midi.learning == self.text:
                cr.set_source_rgb(0.2, 0.1, 0.1)
            else:
                cr.set_source_rgb(0.5, 0.3, 0.0)
        elif self.midi and self.midi.learning == self.text:
            cr.set_source_rgb(0.3, 0.2, 0.2)
        else:
            cr.set_source_rgb(0.2, 0.2, 0.2)
        area = (1, self.width - 2, 1, self.height - 2)
        rounded_rectangle_fill(cr, area, self.radius)
        cr.set_source_rgb(0.1, 0.1, 0.1)
        rounded_rectangle(cr, area, self.radius)
        # Draw Text
        if self.text == "None":
            cr.set_source_rgb(0.5, 0.5, 0.5)
        else:
            cr.set_source_rgb(0.8, 0.8, 0.8)
        cr.select_font_face("Monaco", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
        cr.set_font_size(self.font_size)
        (_x, _y, w, h, _dx, _dy) = cr.text_extents(self.label)
        cr.move_to(
            self.width / 2 - w / 2, self.height / 2 - (h - (self.radius * 2)) / 2
        )
        cr.show_text(self.label)
        return False
