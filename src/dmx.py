"""DMX module:
    Thread to send channels level to Ola
    DMX patch
"""

import array
import threading

from olc.define import MAX_CHANNELS, NB_UNIVERSES, App


class Dmx(threading.Thread):
    """Thread to send levels to Ola"""

    def __init__(self):
        threading.Thread.__init__(self)
        self.grand_master = 255
        self.frame = []
        # Dimers levels
        self.sequence = array.array("B", [0] * MAX_CHANNELS)
        # User levels
        self.user = array.array("h", [-1] * MAX_CHANNELS)

    def run(self):
        # les valeurs DMX echangées avec Ola
        for _ in range(NB_UNIVERSES):
            self.frame.append(array.array("B", [0] * 512))

    def send(self):
        """Send DMX values to Ola"""
        univ = []  # To store universes changed
        for channel in range(MAX_CHANNELS):
            for i in App().patch.channels[channel]:
                if output := i[0]:
                    # If channel is patched
                    output -= 1
                    universe = i[1]
                    if universe not in univ:
                        univ.append(universe)
                    # Level in Sequence
                    level = self.sequence[channel]
                    App().window.channels_view.channels[channel].color_level = {
                        "red": 0.9,
                        "green": 0.9,
                        "blue": 0.9,
                    }
                    if not App().sequence.on_go and self.user[channel] != -1:
                        # If not on Go, use user level
                        level = self.user[channel]
                    for master in App().masters:
                        # If master level is bigger, use it
                        if master.dmx[channel] > level:
                            level = master.dmx[channel]
                            App().window.channels_view.channels[channel].color_level = {
                                "red": 0.4,
                                "green": 0.7,
                                "blue": 0.4,
                            }
                    # Independents
                    level_inde = -1
                    for inde in App().independents.independents:
                        if channel in inde.channels and inde.dmx[channel] > level_inde:
                            level_inde = inde.dmx[channel]
                    if level_inde != -1:
                        level = level_inde
                        App().window.channels_view.channels[channel].color_level = {
                            "red": 0.4,
                            "green": 0.4,
                            "blue": 0.7,
                        }
                    # Proportional patch level
                    level = level * (App().patch.outputs[universe][output][1] / 100)
                    # Grand Master
                    level = round(level * (self.grand_master / 255))
                    # Update output level
                    self.frame[universe][output] = level
        # Send DMX frames to Ola
        for universe in univ:
            App().ola_thread.ola_client.SendDmx(universe, self.frame[universe])


class PatchDmx:
    """To store and manipulate DMX patch

    Attributes:
        channels (list): list of list of [output, universe]
        outputs (list): list of universes who are list of [channel, level]
    """

    def __init__(self):
        # Default 1:1

        # List of channels
        self.channels = []
        for channel in range(MAX_CHANNELS):
            univ = int(channel / 512)
            chan = channel - (512 * univ)
            self.channels.append([[chan + 1, univ]])
        # List of outputs
        self.outputs = []
        for universe in range(NB_UNIVERSES):
            self.outputs.append([])
            for i in range(512):
                channel = i + (512 * universe) + 1
                if channel <= MAX_CHANNELS:
                    self.outputs[universe].append([channel, 100])
                else:
                    self.outputs[universe].append([0, 100])

        # for channel in range(MAX_CHANNELS):
        #     print("Channel", channel, "Output", self.channels[channel][0][0],
        #     "Univers", self.channels[channel][0][1])
        # for universe in range(NB_UNIVERSES):
        #     for i in range(512):
        #         print("Output", i + 1, "Univers", universe, "Channel",
        #         self.outputs[universe][i][0], "Level",
        #         self.outputs[universe][i][1])

    def patch_empty(self):
        """Set Dimmers patch to Zero"""
        for channel in range(MAX_CHANNELS):
            self.channels[channel] = [[0, 0]]
        for universe in range(NB_UNIVERSES):
            for output in range(512):
                self.outputs[universe][output][0] = 0

    def patch_1on1(self):
        """Set patch 1:1"""
        for channel in range(MAX_CHANNELS):
            univ = int(channel / 512)
            chan = channel - (512 * univ)
            self.channels[channel] = [[chan + 1, univ]]
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                self.outputs[univ][output][0] = output + 1

    def add_output(self, channel, output, univ, level=100):
        """Add an output to a channel

        Args:
            channel: Channel number
            output: Dimmer number
            univ: Universe number
            level: Max level
        """
        if self.channels[channel - 1] == [[0, 0]]:
            self.channels[channel - 1] = [[output, univ]]
        else:
            self.channels[channel - 1].append([output, univ])
            # Sort outputs
            self.channels[channel - 1] = sorted(self.channels[channel - 1])
        self.outputs[univ][output - 1][0] = channel
        self.outputs[univ][output - 1][1] = level
