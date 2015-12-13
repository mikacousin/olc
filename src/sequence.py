from olc.cue import Cue

class Sequence(object):
    def __init__(self, index):
        self.index = index
        self.cues = []

        # create an empty cue 0 
        cue = Cue(0, 0, [0,0]*512, text="Cue 0")
        self.add_cue(cue)

    def add_cue(self, cue):
        self.cues.append(cue)

if __name__ == "__main__":

    sequence = Sequence(1)

    cue = Cue(1, 1.0, [[1, 10], [2, 255], [10, 128], [0, 0]*509], text="Top blabla")
    sequence.add_cue(cue)

    print("Sequence :", sequence.index, "\n")
    for cue in sequence.cues:
        print("Index :", cue.index)
        print("memory :", cue.memory)
        print("time in :", cue.time_in)
        print("time out :", cue.time_out)
        print("text :", cue.text)
        print("Chanels :")
        for i in cue.chanels:
            print(i[0], "@", i[1])
        print("")
