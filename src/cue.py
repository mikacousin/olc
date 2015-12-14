from olc.dmx import DmxFrame

class Cue(object):
    def __init__(self, index, memory, dmxframe, time_in=5, time_out=5, text=""):
        self.index = index
        self.memory = memory
        self.chanels = dmxframe
        self.time_in = time_in
        self.time_out = time_out
        self.text = text

if __name__ == "__main__":

    dmx = DmxFrame()
    for i in range(512):
        dmx.set_level(i, int(i/2))
    cue = Cue(1, 10.0, dmx, text="Mise")

    print("Step :", cue.index, "Memory :",cue.memory)
    print("Time In :", cue.time_in, "\nTime Out :", cue.time_out)
    print("Text :", cue.text)
    print("")
    for i in range(512):
        print("Chanel :", i+1, "@", cue.chanels.dmx_frame[i])
