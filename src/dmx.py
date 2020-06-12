import array

from gi.repository import Gio

from olc.define import NB_UNIVERSES, MAX_CHANNELS


class Dmx:
    def __init__(self, universes, patch, ola_client, sequence, masters, window):
        self.universes = universes
        self.patch = patch
        self.ola_client = ola_client
        self.seq = sequence
        self.masters = masters
        self.window = window
        self.grand_master = 255

        self.app = Gio.Application.get_default()

        # les valeurs DMX echangées avec Ola
        self.frame = []
        for _ in range(NB_UNIVERSES):
            self.frame.append(array.array("B", [0] * 512))
        # les valeurs du séquentiel
        self.sequence = array.array("B", [0] * MAX_CHANNELS)
        # les valeurs modifiées par l'utilisateur
        self.user = array.array("h", [-1] * MAX_CHANNELS)

    def send(self):
        # Cette fonction envoi les valeurs DMX à Ola en prenant en compte
        # les valeurs actuelles, le sequentiel, les masters
        # et les valeurs entrées par l'utilisateur

        for universe in range(NB_UNIVERSES):
            # Pour chaque output
            for output in range(512):
                # On récupère le channel correspondant
                channel = self.patch.outputs[universe][output][0]
                # Si il est patché
                if channel:
                    # On part du niveau du séquentiel
                    level = self.sequence[channel - 1]
                    self.window.channels[channel - 1].color_level_red = 0.9
                    self.window.channels[channel - 1].color_level_green = 0.9
                    self.window.channels[channel - 1].color_level_blue = 0.9
                    # Si on est pas sur un Go,
                    # on utilise les valeurs de l'utilisateur
                    if not self.app.sequence.on_go and self.user[channel - 1] != -1:
                        level = self.user[channel - 1]
                    # Si c'est le niveau d'un master le plus grand,
                    # on l'utilise
                    for master in self.masters:
                        if master.dmx[channel - 1] > level:
                            level = master.dmx[channel - 1]
                            self.window.channels[channel - 1].color_level_red = 0.4
                            self.window.channels[channel - 1].color_level_green = 0.7
                            self.window.channels[channel - 1].color_level_blue = 0.4

                    # Proportional patch level
                    level = level * (self.patch.outputs[universe][output][1] / 100)
                    # Grand Master
                    level = round(level * (self.grand_master / 255))
                    # On met à jour le niveau pour cet output
                    self.frame[universe][output] = level

            # On met à jour les valeurs d'Ola
            self.ola_client.SendDmx(universe, self.frame[universe])


class PatchDmx:
    """
    To store and manipulate DMX patch
    """

    def __init__(self):
        # 2 lists to store patch (default 1:1)
        #
        # List of channels
        self.channels = []
        for channel in range(MAX_CHANNELS):
            univ = int(channel / 512)
            chan = channel - (512 * univ)
            self.channels.append([[chan + 1, univ]])

        self.outputs = []
        for universe in range(NB_UNIVERSES):
            self.outputs.append([])
            for i in range(512):
                channel = i + (512 * universe) + 1
                if channel <= MAX_CHANNELS:
                    self.outputs[universe].append([channel, 100])
                else:
                    self.outputs[universe].append([0, 100])

        """
        for channel in range(MAX_CHANNELS):
            print("Channel", channel, "Output", self.channels[channel][0][0],
            "Univers", self.channels[channel][0][1])
        for universe in range(NB_UNIVERSES):
            for i in range(512):
                print("Output", i + 1, "Univers", universe, "Channel",
                self.outputs[universe][i][0], "Level",
                self.outputs[universe][i][1])
        """

    def patch_empty(self):
        """ Set patch to Zero """
        for channel in range(MAX_CHANNELS):
            self.channels[channel] = [[0, 0]]
        for universe in range(NB_UNIVERSES):
            for output in range(512):
                self.outputs[universe][output][0] = 0

    def patch_1on1(self):
        """ Set patch 1:1 """
        for channel in range(MAX_CHANNELS):
            univ = int(channel / 512)
            chan = channel - (512 * univ)
            self.channels[channel] = [[chan + 1, univ]]
        for univ in range(NB_UNIVERSES):
            for output in range(512):
                self.outputs[univ][output][0] = output + 1

    def add_output(self, channel, output, univ, level=100):
        """ Add an output to a channel """
        if self.channels[channel - 1] == [[0, 0]]:
            self.channels[channel - 1] = [[output, univ]]
        else:
            self.channels[channel - 1].append([output, univ])
            # Sort outputs
            self.channels[channel - 1] = sorted(self.channels[channel - 1])
        self.outputs[univ][output - 1][0] = channel
        self.outputs[univ][output - 1][1] = level
