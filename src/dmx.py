import array

from olc.customwidgets import ChanelWidget

class Dmx(object):
    def __init__(self, universe, patch, ola_client, sequence, masters, window):
        self.universe = universe
        self.patch = patch
        self.ola_client = ola_client
        self.seq = sequence
        self.masters = masters
        self.window = window

        # les valeurs DMX echangées avec Ola
        self.frame = array.array('B', [0] * 512)
        # les valeurs du séquentiel
        self.sequence = array.array('B', [0] * 512)
        # les valeurs des masters envoyés
        #self.masters = array.array('B', [0] * 512)
        # les valaurs modifiées par l'utilisateur
        self.user = array.array('h', [-1] * 512)

    def send(self):
        # Cette fonction envoi les valeurs DMX à Ola en prenant en compte
        # les valeurs actuelles, le sequentiel, les masters et les valeurs entrées par l'utilisateur

        # Pour chaque output
        for output in range(512):
            # On récupère le channel correspondant
            channel = self.patch.outputs[output]
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
                self.frame[output] = level

        # On met à jour les valeurs d'Ola
        self.ola_client.SendDmx(self.universe, self.frame)

class PatchDmx(object):
    """
    To store and manipulate DMX patch
    """
    def __init__(self):
        self.univers = 0

        # 2 lists to store patch (default 1:1)
        #
        self.channels = []
        self.outputs = []
        for i in range(512):
            self.channels.append([i + 1]) # Liste de liste pour avoir plusieurs outputs sur 1 channel
            self.outputs.append(i + 1)

    def patch_empty(self):
        """ Set patch to Zero """
        for i in range(512):
            self.channels[i] = [0]
            self.outputs[i] = 0

    def patch_1on1(self):
        """ Set patch 1:1 """
        for i in range(512):
            self.channels[i] = [i+1]
            self.outputs[i] = i+1

    def add_output(self, channel, output):
        """ Add an output to a channel """
        if self.channels[channel-1] == [0]:
            self.channels[channel-1] = [output]
        else:
            self.channels[channel-1].append(output)
        self.outputs[output-1] = channel

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
