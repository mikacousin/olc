import array

from gi.repository import Gio

from olc.define import NB_UNIVERSES, MAX_CHANNELS
from olc.customwidgets import ChannelWidget

class Dmx(object):
    def __init__(self, universes, patch, ola_client, sequence, masters, window):
        self.universes = universes
        self.patch = patch
        self.ola_client = ola_client
        self.seq = sequence
        self.masters = masters
        self.window = window

        # les valeurs DMX echangées avec Ola
        self.frame = []
        for universe in range(NB_UNIVERSES):
            self.frame.append(array.array('B', [0] * 512))
        # les valeurs du séquentiel
        self.sequence = array.array('B', [0] * 512)
        # les valeurs modifiées par l'utilisateur
        self.user = array.array('h', [-1] * 512)

    def send(self):
        # Cette fonction envoi les valeurs DMX à Ola en prenant en compte
        # les valeurs actuelles, le sequentiel, les masters et les valeurs entrées par l'utilisateur

        for universe in range(NB_UNIVERSES):
            # Pour chaque output
            for output in range(512):
                # On récupère le channel correspondant
                channel = self.patch.outputs[universe][output]
                # Si il est patché
                if channel:
                    # On part du niveau du séquentiel
                    level = self.sequence[channel-1]
                    self.window.channels[channel-1].color_level_red = 0.9
                    self.window.channels[channel-1].color_level_green = 0.9
                    self.window.channels[channel-1].color_level_blue = 0.9
                    # Si on est pas sur un Go, on utilise les valeurs de l'utilisateur
                    if not self.seq.on_go and self.user[channel-1] != -1:
                        level = self.user[channel-1]
                    # Si c'est le niveau d'un master le plus grand, on l'utilise
                    for master in range(len(self.masters)):
                        if self.masters[master].dmx[channel-1] > level:
                            level = self.masters[master].dmx[channel-1]
                            self.window.channels[channel-1].color_level_red = 0.4
                            self.window.channels[channel-1].color_level_green = 0.7
                            self.window.channels[channel-1].color_level_blue = 0.4

                    # On met à jour le niveau pour cet output
                    self.frame[universe][output] = level

            # On met à jour les valeurs d'Ola
            self.ola_client.SendDmx(universe, self.frame[universe])

class PatchDmx(object):
    """
    To store and manipulate DMX patch
    """
    def __init__(self):
        # TODO: Add level limitation for Outputs (see ascii files)

        # 2 lists to store patch (default 1:1)
        #
        # List of channels
        self.channels = []
        for channel in range(MAX_CHANNELS):
            # TODO: Modify if MAX_CHANNELS > 512
            self.channels.append([[channel + 1], 0])

        self.outputs = []
        for universe in range(NB_UNIVERSES):
            self.outputs.append([])
            for i in range(512):
                if universe == 0:
                    self.outputs[universe].append(i + 1)
                else:
                    self.outputs[universe].append(0)

        """
        for channel in range(MAX_CHANNELS):
            print("Channel", self.channels[channel][0], "Univers", self.channels[channel][1])
        for universe in range(NB_UNIVERSES):
            for i in range(512):
                print("Univers", universe, "Output", self.outputs[universe][i])
        """

    def patch_empty(self):
        """ Set patch to Zero """
        for channel in range(MAX_CHANNELS):
            self.channels[channel] = [[0], 0]
        for universe in range(NB_UNIVERSES):
            for output in range(512):
                self.outputs[universe][output] = 0

    def patch_1on1(self):
        """ Set patch 1:1 """
        for channel in range(MAX_CHANNELS):
            self.channels[channel] = [[channel + 1], 0]
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                self.outputs[univ][output] = output + 1

    def add_output(self, channel, output, univ):
        """ Add an output to a channel """
        if self.channels[channel-1] == [[0], 0]:
            self.channels[channel-1] = [[output], univ]
        else:
            self.channels[channel-1][0].append(output)
            self.channels[channel-1][0] = sorted(self.channels[channel-1][0])
            self.channels[channel-1][1] = univ
        self.outputs[univ][output-1] = channel

    """
    def is_channel_patched(self, channel):
        for out in range(512):
            if self.outputs[out] == channel:
                return out
        return -1
    """

if __name__ == "__main__":

    patch = PatchDmx()

    #for i in range(len(patch.channels)):
    #    print ("channel :", i+1, "output(s) :", patch.channels[i])

    #for i in range(len(patch.outputs)):
    #    print ("output :", i+1, "channel :", patch.outputs[i])

    patch.patch_empty()

    #for i in range(len(patch.channels)):
    #    print ("channel :", i+1, "output(s) :", patch.channels[i])

    #for i in range(len(patch.outputs)):
    #    print ("output :", i+1, "channel :", patch.outputs[i])

    patch.add_output(510, 10)
    patch.add_output(510, 20)

    for i in range(len(patch.channels)):
        print ("channel :", i+1, "output(s) :", patch.channels[i])

    for i in range(len(patch.outputs)):
        print ("output :", i+1, "channel :", patch.outputs[i])
