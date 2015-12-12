import array

class DmxFrame(object):
    def __init__(self):
        self.dmx_frame = array.array('B', [0] * 512)

    def set_level(self, output, level):
        self.dmx_frame[output] = level

class PatchDmx(object):
    """
    To store and manipulate DMX patch
    """
    def __init__(self):
        self.univers = 0

        # 2 lists to store patch (default 1:1)
        #
        self.chanels = []
        self.outputs = []
        for i in range(512):
            self.chanels.append([i + 1]) # Liste de liste pour avoir plusieurs outputs sur 1 chanel
            self.outputs.append(i + 1)

    def patch_empty(self):
        """ Set patch to Zero """
        for i in range(512):
            self.chanels[i] = [0]
            self.outputs[i] = 0

    def patch_1on1(self):
        """ Set patch 1:1 """
        for i in range(512):
            self.chanels[i] = [i+1]
            self.outputs[i] = i+1

    def add_output(self, chanel, output):
        """ Add an output to a chanel """
        if self.chanels[chanel-1] == [0]:
            self.chanels[chanel-1] = [output]
        else:
            self.chanels[chanel-1].append(output)
        self.outputs[output-1] = chanel

if __name__ == "__main__":

    patch = PatchDmx()

    #for i in range(len(patch.chanels)):
    #    print ("chanel :", i+1, "output(s) :", patch.chanels[i])

    #for i in range(len(patch.outputs)):
    #    print ("output :", i+1, "chanel :", patch.outputs[i])

    patch.patch_empty()

    #for i in range(len(patch.chanels)):
    #    print ("chanel :", i+1, "output(s) :", patch.chanels[i])

    #for i in range(len(patch.outputs)):
    #    print ("output :", i+1, "chanel :", patch.outputs[i])

    patch.add_output(510, 10)
    patch.add_output(510, 20)

    for i in range(len(patch.chanels)):
        print ("chanel :", i+1, "output(s) :", patch.chanels[i])

    for i in range(len(patch.outputs)):
        print ("output :", i+1, "chanel :", patch.outputs[i])
