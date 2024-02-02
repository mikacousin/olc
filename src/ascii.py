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
from gi.repository import Gio, GObject
from olc.ascii_load import AsciiParser
from olc.ascii_save import (save_chasers, save_congo_groups, save_curves, save_groups,
                            save_independents, save_main_playback, save_masters,
                            save_midi_mapping, save_outputs_curves, save_patch)
from olc.cue import Cue
from olc.define import App
from olc.step import Step


class Ascii:
    """ASCII file"""

    def __init__(self, filename):
        self.file = filename

    def load(self):
        """Load ASCII file"""
        self.file = App().lightshow.file
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
            App().lightshow.main_playback.add_step(step)
            # Position main playback at start
            App().lightshow.main_playback.position = 0
            # Update display information
            self._update_ui()
            App().lightshow.add_recent_file()
        except GObject.GError as e:
            print(f"Error: {e}")
        App().lightshow.set_not_modified()

    def save(self):
        """Save ASCII file"""
        self.file = App().lightshow.file
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

        App().lightshow.set_not_modified()
        App().lightshow.add_recent_file()

    def _update_ui(self):
        """Update display after file loading"""
        # Set main window's subtitle
        subtitle = (f"Mem. : 0.0 - "
                    f"Next Mem. : {App().lightshow.main_playback.steps[1].cue.memory} "
                    f"{App().lightshow.main_playback.steps[1].cue.text}")
        App().window.header.set_subtitle(subtitle)
        # Redraw Crossfade
        App().window.playback.update_xfade_display(0)
        # Redraw Main Playback
        App().window.playback.update_sequence_display()

        # Redraw all open tabs
        App().tabs.refresh_all()

        # Redraw Masters if Virtual Console is open
        if App().virtual_console and App().virtual_console.props.visible:
            for fader in App().lightshow.faders:
                if fader.page == App().fader_page:
                    text = f"master_{fader.number + (App().fader_page - 1) * 10}"
                    App().virtual_console.masters[fader.number - 1].text = text
                    App().virtual_console.masters[fader.number - 1].set_value(
                        fader.value)
                    App().virtual_console.flashes[fader.number - 1].label = fader.text
            App().virtual_console.masters_pad.queue_draw()
        # Redraw Mackie LCD
        App().midi.messages.lcd.show_masters()

        App().window.live_view.channels_view.flowbox.unselect_all()
        App().window.live_view.channels_view.update()
        App().window.live_view.channels_view.last_selected_channel = ""
