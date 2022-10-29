# -*- coding: utf-8 -*-
# Open Lighting Console
# Copyright (c) 2015-2022 Mika Cousin <mika.cousin@gmail.com>
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

from gi.repository import Gio, GObject, Gtk

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
)
from olc.cue import Cue
from olc.define import MAX_CHANNELS, App
from olc.step import Step


def get_time(string):
    """Convert a string time to float

    Args:
        string (str): format [[hours:]minutes:]seconds[.tenths]

    Returns:
        time in seconds
    """
    if ":" in string:
        tsplit = string.split(":")
        if len(tsplit) == 2:
            time = int(tsplit[0]) * 60 + float(tsplit[1])
        elif len(tsplit) == 3:
            time = int(tsplit[0]) * 3600 + int(tsplit[1]) * 60 + float(tsplit[2])
        else:
            print("Time format Error")
            time = 0
    else:
        time = float(string)

    return time


class Ascii:
    """ASCII file"""

    def __init__(self, filename):
        self.file = filename
        self.basename = self.file.get_basename() if filename else ""
        self.modified = False

    def load(self):
        """Load ASCII file"""
        self.basename = self.file.get_basename()
        try:
            status, contents, _etag_out = self.file.load_contents(None)
            if not status:
                print("Error on load contents")
                return
            contents = contents.decode("iso-8859-1")
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
            # Update display informations
            self._update_ui()
        except GObject.GError as e:
            print("Error: " + str(e))
        self.modified = False

    def save(self):
        """Save ASCII File"""

        stream = self.file.replace("", False, Gio.FileCreateFlags.NONE, None)

        # TODO: to import Fx and Masters in dlight :
        # MANUFACTURER NICOBATS or AVAB
        # CONSOLE      DLIGHT   or CONGO
        # TODO: Masters dans Dlight sont en Time et pas Flash
        stream.write(bytes("IDENT 3:0\n", "utf8"))
        stream.write(bytes("MANUFACTURER MIKA\n", "utf8"))
        stream.write(bytes("CONSOLE OLC\n\n", "utf8"))
        stream.write(bytes("CLEAR ALL\n\n", "utf8"))

        save_main_playback(stream)
        save_chasers(stream)
        save_groups(stream)
        save_congo_groups(stream)
        save_masters(stream)
        save_patch(stream)
        save_independents(stream)
        save_midi_mapping(stream)

        stream.write(bytes("ENDDATA\n", "utf8"))

        stream.close()

        self.modified = False
        App().window.header.set_title(self.basename)

    def _update_ui(self):
        """Update display after file loading"""
        # Set main window's title with the file name
        App().window.header.set_title(self.basename)
        # Set main window's subtitle
        subtitle = (
            "Mem. : 0.0 - Next Mem. : "
            + str(App().sequence.steps[1].cue.memory)
            + " "
            + App().sequence.steps[1].cue.text
        )
        App().window.header.set_subtitle(subtitle)
        # Redraw Crossfade
        App().window.playback.update_xfade_display(0)
        # Redraw Main Playback
        App().window.playback.update_sequence_display()

        # Redraw Group Tab if exist
        if App().group_tab:
            # Remove Old Groups
            App().group_tab.scrolled.remove(App().group_tab.flowbox)
            App().group_tab.flowbox.destroy()
            # Update Group tab
            App().group_tab.populate_tab()
            App().group_tab.channels_view.flowbox.invalidate_filter()
            App().group_tab.flowbox.invalidate_filter()
            App().window.show_all()

        # Redraw Sequences Tab if exist
        if App().sequences_tab:
            App().sequences_tab.liststore1.clear()

            App().sequences_tab.liststore1.append(
                [App().sequence.index, App().sequence.type_seq, App().sequence.text]
            )

            for chaser in App().chasers:
                App().sequences_tab.liststore1.append(
                    [chaser.index, chaser.type_seq, chaser.text]
                )

            App().sequences_tab.treeview1.set_model(App().sequences_tab.liststore1)
            path = Gtk.TreePath.new_first()
            App().sequences_tab.treeview1.set_cursor(path, None, False)
            selection = App().sequences_tab.treeview1.get_selection()
            App().sequences_tab.on_sequence_changed(selection)

        # Redraw Patch Outputs Tab if exist
        if App().patch_outputs_tab:
            App().patch_outputs_tab.flowbox.queue_draw()

        # Redraw Patch Channels Tab if exist
        if App().patch_channels_tab:
            App().patch_channels_tab.flowbox.queue_draw()

        # Redraw List of Memories Tab if exist
        if App().memories_tab:
            App().memories_tab.liststore.clear()
            for mem in App().memories:
                channels = sum(1 for chan in range(MAX_CHANNELS) if mem.channels[chan])
                App().memories_tab.liststore.append(
                    [str(mem.memory), mem.text, channels]
                )
            App().memories_tab.flowbox.invalidate_filter()

        # Redraw Masters if Virtual Console is open
        if App().virtual_console and App().virtual_console.props.visible:
            for master in App().masters:
                if master.page == App().fader_page:
                    text = "master_" + str(
                        master.number + ((App().fader_page - 1) * 10)
                    )
                    App().virtual_console.masters[master.number - 1].text = text
                    App().virtual_console.masters[master.number - 1].set_value(
                        master.value
                    )
                    App().virtual_console.flashes[master.number - 1].label = master.text
            App().virtual_console.masters_pad.queue_draw()

        # Redraw Edit Masters Tab if exist
        if App().masters_tab:
            # Delete
            App().masters_tab.liststore.clear()
            # Redraw
            App().masters_tab.populate_tab()
            App().masters_tab.flowbox.invalidate_filter()

        # Redraw Independents Tab
        if App().inde_tab:
            App().inde_tab.liststore.clear()
            for inde in App().independents.independents:
                App().inde_tab.liststore.append(
                    [inde.number, inde.inde_type, inde.text]
                )
            path = Gtk.TreePath.new_first()
            App().inde_tab.treeview.set_cursor(path, None, False)

        # Redraw Track Channels Tab
        if App().track_channels_tab:
            App().track_channels_tab.populate_steps()
            App().track_channels_tab.flowbox.invalidate_filter()
            App().track_channels_tab.show_all()
            App().track_channels_tab.update_display()

        App().window.live_view.channels_view.flowbox.unselect_all()
        App().window.live_view.channels_view.flowbox.invalidate_filter()
        App().window.last_chan_selected = ""
