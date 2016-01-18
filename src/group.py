class Group(object):
    def __init__(self, index, channels=array.array('B', [0] * 512), text=""):
        self.index = index
        self.channels = channels
        self.text = text
