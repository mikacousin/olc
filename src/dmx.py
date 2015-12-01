import array

class DmxFrame(object):
    def __init__(self):
        self.dmx_frame = array.array('B', [0] * 512)

class PatchDmx(object):
    """
    To store and manipulate DMX patch
    """
    def __init___(self):
        self.univers = 0

        # 2 lists to store patch (default 1:1)
        #
        # TODO: les channels peuvent avoir plusieurs outputs
        self.chanels = []
        self.outputs = []
        for i in range(512):
            self.chanels.append(i + 1)
            self.outputs.append(i + 1)

    def patch_empty(self):
        for i in range(512):
            self.chanels[i] = 0
            self.outputs[i] = 0
