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
from io import StringIO
from charset_normalizer import from_bytes
from gi.repository import Gio, GLib, GObject, Gtk

from olc.ascii_load import AsciiParser
from olc.ascii_save import (
    save_chasers,
    save_congo_groups,
    save_groups,
    save_main_playback,
    save_masters,
    save_patch,
    save_independents,
    save_midi_mapping,
    save_curves,
    save_outputs_curves,
)
from olc.cue import Cue
from olc.define import App
from olc.step import Step


class Ascii:
    """ASCII file"""

    def __init__(self, filename):
        self.file = filename
        self.basename = self.file.get_basename() if filename else ""
        self.modified = False
        self.recent_manager = Gtk.RecentManager.get_default()

    def load(self):
        """Load ASCII file"""
        self.basename = self.file.get_basename()
        try:
            status, contents, _etag_out = self.file.load_contents(None)
            if not status:
                print("Error on load contents")
                return
            contents = str(from_bytes(contents).best())
            file_io = StringIO(contents)
            readlines = file_io.readlines()
            # Parse file
            AsciiParser().parse(readlines)
            # Add Empty Step at the end
            cue = Cue(0, 0.0)
            step = Step(1, cue=cue)
            App().sequence.add_step(step)
            # Position main playback at start
            App().sequence.position = 0
            # Update display information
            self._update_ui()
            self.add_recent_file()
        except GObject.GError as e:
            print(f"Error: {e}")
        self.modified = False

    def save(self):
        """Save ASCII file"""
        stream = self.file.replace("", False, Gio.FileCreateFlags.NONE, None)

        # TODO: to import Effects and Masters in dlight :
        # MANUFACTURER NICOBATS or AVAB
        # CONSOLE      DLIGHT   or CONGO
        # TODO: Masters in Dlight are in Time and not Flash
        stream.write(bytes("IDENT 3:0\n", "utf8"))
        stream.write(bytes("MANUFACTURER MIKA\n", "utf8"))
        stream.write(bytes("CONSOLE OLC\n\n", "utf8"))
        stream.write(bytes("CLEAR ALL\n\n", "utf8"))

        save_main_playback(stream)
        save_chasers(stream)
        save_groups(stream)
        save_congo_groups(stream)
        save_masters(stream)
        save_curves(stream)
        save_patch(stream)
        save_outputs_curves(stream)
        save_independents(stream)
        save_midi_mapping(stream)

        stream.write(bytes("ENDDATA\n", "utf8"))

        stream.close()

        self.modified = False
        App().window.header.set_title(self.basename)
        self.add_recent_file()

    def add_recent_file(self):
        """Add to Recent files

        Raises:
            e: not documented
        """
        uri = self.file.get_uri()
        if uri:
            # We remove the project from recent projects list
            # and then re-add it to this list to make sure it
            # gets positioned at the top of the recent projects list.
            try:
                self.recent_manager.remove_item(uri)
            except GLib.Error as e:
                if e.domain != "gtk-recent-manager-error-quark":
                    raise e
            self.recent_manager.add_item(uri)

    def set_modified(self) -> None:
        """Set file as modified"""
        self.modified = True
        App().window.header.set_title(f"{self.basename}*")

    def _update_ui(self):
        """Update display after file loading"""
        # Set main window's title with the file name
        App().window.header.set_title(self.basename)
        # Set main window's subtitle
        subtitle = (
            f"Mem. : 0.0 - Next Mem. : {App().sequence.steps[1].cue.memory} "
            f"{App().sequence.steps[1].cue.text}"
        )
        App().window.header.set_subtitle(subtitle)
        # Redraw Crossfade
        App().window.playback.update_xfade_display(0)
        # Redraw Main Playback
        App().window.playback.update_sequence_display()

        # Redraw all open tabs
        App().tabs.refresh_all()

        # Redraw Masters if Virtual Console is open
        if App().virtual_console and App().virtual_console.props.visible:
            for master in App().masters:
                if master.page == App().fader_page:
                    text = f"master_{master.number + (App().fader_page - 1) * 10}"
                    App().virtual_console.masters[master.number - 1].text = text
                    App().virtual_console.masters[master.number - 1].set_value(
                        master.value
                    )
                    App().virtual_console.flashes[master.number - 1].label = master.text
            App().virtual_console.masters_pad.queue_draw()
        # Redraw Mackie LCD
        App().midi.messages.lcd.show_masters()

        App().window.live_view.channels_view.flowbox.unselect_all()
        App().window.live_view.channels_view.update()
        App().window.live_view.channels_view.last_selected_channel = ""
