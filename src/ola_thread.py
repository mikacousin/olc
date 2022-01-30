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
import array
import threading
from functools import partial

from gi.repository import GLib
from ola import OlaClient
from olc.define import NB_UNIVERSES, App


class OlaThread(threading.Thread):
    """Create OlaClient and receive universes updates

    Args:
        universes: list of universes
    """

    def __init__(self, universes):
        threading.Thread.__init__(self)
        self.universes = universes
        self.ola_client = OlaClient.OlaClient()
        self.sock = self.ola_client.GetSocket()

        self.old_frame = [array.array("B", [0] * 512) for _ in range(NB_UNIVERSES)]

    def run(self):
        """Register universes"""
        for univ in self.universes:
            self.ola_client.RegisterUniverse(
                univ, self.ola_client.REGISTER, partial(self.on_dmx, univ)
            )

    def on_dmx(self, univ, dmxframe):
        """Universe updates.

        Args:
            univ (int): universe
            dmxframe (array): 512 bytes with levels outputs
        """
        # Find diff between old and new DMX frames
        diff = [
            (index, e1)
            for index, (e1, e2) in enumerate(zip(dmxframe, self.old_frame[univ]))
            if e1 != e2
        ]
        # Loop on outputs with different level
        for output, level in diff:
            channel = App().patch.outputs[univ][output][0] - 1
            # New level
            App().window.channels_view.channels[channel].level = level
            # Find next level
            if (
                App().sequence.last > 1
                and App().sequence.position < App().sequence.last - 1
            ):
                next_level = (
                    App()
                    .sequence.steps[App().sequence.position + 1]
                    .cue.channels[channel]
                )
            elif App().sequence.last:
                next_level = App().sequence.steps[0].cue.channels[channel]
            else:
                next_level = level
            App().window.channels_view.channels[channel].next_level = next_level
            # Display new levels
            GLib.idle_add(App().window.channels_view.channels[channel].queue_draw)
            if App().patch_outputs_tab:
                GLib.idle_add(
                    App().patch_outputs_tab.outputs[output + (univ * 512)].queue_draw
                )
        # Save DMX frame for next call
        self.old_frame[univ] = dmxframe
