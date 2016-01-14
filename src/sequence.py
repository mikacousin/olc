import array
from olc.cue import Cue

class Sequence(object):
    def __init__(self, index, type_seq = "Normal"):
        self.index = index
        self.type_seq = type_seq
        self.cues = []
        self.position = 0
        self.last = 0
        # Liste des channels présent dans le sequentiel
        self.channels = array.array('B', [0] * 512)
        # Flag pour les chasers
        self.run = False

        # create an empty cue 0
        cue = Cue(0, 0, text="Cue 0")
        self.add_cue(cue)

    def add_cue(self, cue):
        self.cues.append(cue)
        self.last = cue.index
        # On enregistre la liste des circuits présents dans la mméoire
        for i in range(512):
            if cue.channels[i] != 0:
                self.channels[i] = 1 # Si présent on le note

if __name__ == "__main__":

    sequence = Sequence(1)

    channels = array.array('B', [0] * 512)
    for i in range(512):
        channels[i] = int(i / 2)
    cue = Cue(1, 1.0, channels, text="Top blabla")
    sequence.add_cue(cue)

    print("Sequence :", sequence.index, "Type :", sequence.type_seq, "\n")
    print("Position in sequence :", sequence.position)
    print("Index of the last Cue :", sequence.last)
    for cue in sequence.cues:
        print("Index :", cue.index)
        print("memory :", cue.memory)
        print("time in :", cue.time_in)
        print("time out :", cue.time_out)
        print("text :", cue.text)
        print("Chanels :")
        for i in range(512):
            print(i+1, "@", cue.channels[i])
        print("")
