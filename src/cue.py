import array
#from olc.dmx import DmxFrame

class Cue(object):
    def __init__(self, index, memory, channels=array.array('B', [0] * 512), time_in=5.0, time_out=5.0, wait=0.0, text=""):
        self.index = index
        self.memory = memory
        self.channels = channels
        self.time_in = time_in
        self.time_out = time_out
        self.wait = wait
        self.text = text

    def set_level(self, channel, level):
        self.channels[channel] = level

    def get_level(self, channel):
        return self.channels[channel]

if __name__ == "__main__":

    channels = array.array('B', [0] * 512)
    for i in range(512):
        channels[i] = int(i/2)
    cue = Cue(1, 10.0, channels, text="Mise")

    print("Step :", cue.index, "Memory :",cue.memory)
    print("Time In :", cue.time_in, "\nTime Out :", cue.time_out)
    print("Text :", cue.text)
    print("")
    for i in range(512):
        print("Chanel :", i+1, "@", cue.channels[i])
