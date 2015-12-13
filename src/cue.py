class Cue(object):
    def __init__(self, index, memory, chanels, time_in=5, time_out=5, text=""):
        self.index = index
        self.memory = memory
        self.chanels = chanels
        self.time_in = time_in
        self.time_out = time_out
        self.text = text

if __name__ == "__main__":

    cue = Cue(1, 10.0, [[1,128], [2,50], [5,255], [10,30]], text="Mise")

    print("Step :", cue.index, "Memory :",cue.memory)
    print("Time In :", cue.time_in, "\nTime Out :", cue.time_out)
    print("Text :", cue.text)
    print("")
    for i in cue.chanels:
        print("Chanel :", i[0], "@", i[1])
